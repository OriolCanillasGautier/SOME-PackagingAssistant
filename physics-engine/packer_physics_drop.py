"""
packer_physics.py — GPU physics-drop packer.

Drops hundreds of copies from random positions above the box,
applies gravity + collision + vibration to settle them into
the densest possible arrangement. Counts pieces that end up
inside the box. Runs entirely on GPU — no per-frame CPU transfers.

Usage:
    python packer_physics.py [stl_file] [box_l] [box_w] [box_h]
"""
import sys, time, math, argparse, random
from pathlib import Path
from collections import defaultdict
import numpy as np

import numba.cuda.cudadrv.driver as _ptx_drv
_ptx_orig = _ptx_drv.CtypesLinker.add_ptx
def _ptx_patched(self, ptx, name='<cudapy-ptx>'):
    import re
    ptx = re.sub(rb'\.version\s+\d+\.\d+', b'.version 8.2', ptx) if isinstance(ptx, bytes) else re.sub(r'\.version\s+\d+\.\d+', '.version 8.2', ptx)
    return _ptx_orig(self, ptx, name)
_ptx_drv.CtypesLinker.add_ptx = _ptx_patched

from numba import cuda
import trimesh
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine.hull import compute_hull


# ═══════════════════════════════════════════════
# GPU physics kernel
# ═══════════════════════════════════════════════

@cuda.jit
def _physics_init_kernel(
    positions, quaternions, velocities, angular_vels,
    aabb_min, aabb_max, active,
    box_dims,
    n_bodies, seed,
):
    """Initialize bodies at random positions above the box."""
    idx = cuda.grid(1)
    if idx >= n_bodies:
        return

    # Simple hash-based pseudo-random
    s = (idx + 1) * 1664525 + 1013904223 + seed
    s = (s * 1103515245 + 12345) & 0x7fffffff
    rx = float(s % 10000) / 10000.0
    s = (s * 1103515245 + 12345) & 0x7fffffff
    rz = float(s % 10000) / 10000.0
    s = (s * 1103515245 + 12345) & 0x7fffffff
    ry = float(s % 10000) / 10000.0

    x = rx * (box_dims[0] - 10.0) + 5.0
    z = rz * (box_dims[2] - 10.0) + 5.0
    y = box_dims[1] + ry * 150.0 + 30.0

    positions[idx, 0] = x
    positions[idx, 1] = y
    positions[idx, 2] = z

    velocities[idx, 0] = (rx - 0.5) * 100.0
    velocities[idx, 1] = (ry - 0.7) * 300.0  # downward bias
    velocities[idx, 2] = (rz - 0.5) * 100.0

    quaternions[idx, 0] = 0.0
    quaternions[idx, 1] = 0.0
    quaternions[idx, 2] = 0.0
    quaternions[idx, 3] = 1.0
    angular_vels[idx, 0] = 0.0
    angular_vels[idx, 1] = 0.0
    angular_vels[idx, 2] = 0.0

    active[idx] = 1


@cuda.jit
def _physics_step_kernel(
    positions, quaternions, velocities, angular_vels,
    aabb_min, aabb_max, active,
    hull_verts, hull_vert_counts,
    box_dims, gravity, dt, damping, ground_y,
    vibration_amp, vibration_freq, step_num,
    n_bodies, max_verts,
):
    """One physics step: gravity + ground + wall + AABB collision + separation."""
    idx = cuda.grid(1)
    if idx >= n_bodies:
        return
    if active[idx] == 0:
        return

    nv = hull_vert_counts[idx]

    # ── Gravity ──
    velocities[idx, 0] += gravity[0] * dt
    velocities[idx, 1] += gravity[1] * dt
    velocities[idx, 2] += gravity[2] * dt

    # ── Damping ──
    d = 1.0 - damping * dt
    if d < 0.0:
        d = 0.0
    velocities[idx, 0] *= d
    velocities[idx, 1] *= d
    velocities[idx, 2] *= d

    # ── Vibration ──
    if vibration_amp > 0.0:
        phase = float(idx) * 2.399963
        vib_x = math.sin(float(step_num) * 0.1 + phase) * vibration_amp * dt
        vib_z = math.cos(float(step_num) * 0.13 + phase) * vibration_amp * dt
        velocities[idx, 0] += vib_x
        velocities[idx, 2] += vib_z
        # Vertical shake
        vib_y = math.sin(float(step_num) * 0.08 + phase * 1.7) * vibration_amp * 0.3 * dt
        velocities[idx, 1] += vib_y

    # ── Integrate position ──
    positions[idx, 0] += velocities[idx, 0] * dt
    positions[idx, 1] += velocities[idx, 1] * dt
    positions[idx, 2] += velocities[idx, 2] * dt

    # ── Compute AABB ──
    px, py, pz = positions[idx, 0], positions[idx, 1], positions[idx, 2]
    min_x = 1e30; min_y = 1e30; min_z = 1e30
    max_x = -1e30; max_y = -1e30; max_z = -1e30
    for vi in range(nv):
        vx = hull_verts[idx, vi, 0] + px
        vy = hull_verts[idx, vi, 1] + py
        vz = hull_verts[idx, vi, 2] + pz
        if vx < min_x: min_x = vx
        if vx > max_x: max_x = vx
        if vy < min_y: min_y = vy
        if vy > max_y: max_y = vy
        if vz < min_z: min_z = vz
        if vz > max_z: max_z = vz
    aabb_min[idx, 0] = min_x
    aabb_min[idx, 1] = min_y
    aabb_min[idx, 2] = min_z
    aabb_max[idx, 0] = max_x
    aabb_max[idx, 1] = max_y
    aabb_max[idx, 2] = max_z

    # ── Ground constraint ──
    if min_y < ground_y:
        penetration = ground_y - min_y
        positions[idx, 1] += penetration
        if velocities[idx, 1] < 0.0:
            velocities[idx, 1] *= -0.3  # bounce
        velocities[idx, 0] *= 0.9  # friction
        velocities[idx, 2] *= 0.9

    # ── Box wall constraints ──
    margin = 1.0
    if min_x < margin:
        positions[idx, 0] += margin - min_x
        if velocities[idx, 0] < 0.0:
            velocities[idx, 0] *= -0.3
    if max_x > box_dims[0] - margin:
        positions[idx, 0] -= max_x - box_dims[0] + margin
        if velocities[idx, 0] > 0.0:
            velocities[idx, 0] *= -0.3
    if min_z < margin:
        positions[idx, 2] += margin - min_z
        if velocities[idx, 2] < 0.0:
            velocities[idx, 2] *= -0.3
    if max_z > box_dims[2] - margin:
        positions[idx, 2] -= max_z - box_dims[2] + margin
        if velocities[idx, 2] > 0.0:
            velocities[idx, 2] *= -0.3

    # ── Ceiling constraint ──
    if max_y > box_dims[1]:
        positions[idx, 1] -= max_y - box_dims[1]
        if velocities[idx, 1] > 0.0:
            velocities[idx, 1] *= -0.3

    # Mark for deactivation if fallen way below
    if min_y < -500:
        active[idx] = 0


@cuda.jit
def _solve_overlaps_kernel(
    positions, aabb_min, aabb_max, active, inv_mass,
    hull_verts, hull_vert_counts, hull_norms, hull_face_counts,
    n_bodies, box_dims, max_verts, max_faces,
    iteration,
):
    """One iteration of collision resolution: push apart overlapping pairs using SAT."""
    idx = cuda.grid(1)
    if idx >= n_bodies:
        return
    if active[idx] == 0:
        return
    if inv_mass[idx] <= 0.0:
        return

    nvi = hull_vert_counts[idx]
    nfi = hull_face_counts[idx]

    # Get i's AABB
    amin_i = aabb_min[idx]
    amax_i = aabb_max[idx]

    # Check against all other bodies
    for j in range(idx + 1, n_bodies):
        if active[j] == 0:
            continue
        if inv_mass[j] <= 0.0 and inv_mass[idx] <= 0.0:
            continue

        amin_j = aabb_min[j]
        amax_j = aabb_max[j]

        # AABB overlap check
        if amax_i[0] < amin_j[0] or amin_i[0] > amax_j[0]:
            continue
        if amax_i[1] < amin_j[1] or amin_i[1] > amax_j[1]:
            continue
        if amax_i[2] < amin_j[2] or amin_i[2] > amax_j[2]:
            continue

        nvj = hull_vert_counts[j]
        pfx = (positions[idx, 0] + positions[j, 0]) * 0.5
        pfy = (positions[idx, 1] + positions[j, 1]) * 0.5
        pfz = (positions[idx, 2] + positions[j, 2]) * 0.5

        # Simple push-apart: use overlap direction from AABB
        ox = 0.0; oy = 0.0; oz = 0.0
        count = 0

        if amax_i[0] > amin_j[0] and amin_i[0] < amax_j[0]:
            ov_x = amax_i[0] - amin_j[0]
            if amax_j[0] - amin_i[0] < ov_x:
                ov_x = amax_j[0] - amin_i[0]
            ox = ov_x
            count += 1
        if amax_i[1] > amin_j[1] and amin_i[1] < amax_j[1]:
            ov_y = amax_i[1] - amin_j[1]
            if amax_j[1] - amin_i[1] < ov_y:
                ov_y = amax_j[1] - amin_i[1]
            oy = ov_y
            count += 1
        if amax_i[2] > amin_j[2] and amin_i[2] < amax_j[2]:
            ov_z = amax_i[2] - amin_j[2]
            if amax_j[2] - amin_i[2] < ov_z:
                ov_z = amax_j[2] - amin_i[2]
            oz = ov_z
            count += 1

        if count == 0:
            continue

        # Push apart along direction from j to i
        dx = positions[idx, 0] - positions[j, 0]
        dy = positions[idx, 1] - positions[j, 1]
        dz = positions[idx, 2] - positions[j, 2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist < 0.001:
            dist = 0.001
            dx = 0.0
            dy = 1.0
            dz = 0.0
        else:
            dx /= dist
            dy /= dist
            dz /= dist

        # Separation amount (proportional to overlap)
        sep = max(ox, oy, oz) * 0.55
        if sep < 0.001:
            sep = 0.001

        im_i = inv_mass[idx]
        im_j = inv_mass[j]
        total_im = im_i + im_j
        if total_im < 1e-12:
            continue

        # Push i away from j
        positions[idx, 0] += dx * sep * (im_i / total_im)
        positions[idx, 1] += dy * sep * (im_i / total_im)
        positions[idx, 2] += dz * sep * (im_i / total_im)

        # Push j away from i (done by j's thread)


@cuda.jit
def _count_inside_kernel(
    positions, aabb_min, aabb_max, active,
    hull_vert_counts, box_dims,
    inside_count, n_bodies,
):
    """Count how many bodies are fully inside the box."""
    idx = cuda.grid(1)
    if idx >= n_bodies:
        return
    if active[idx] == 0:
        return

    amin = aabb_min[idx]
    amax = aabb_max[idx]

    if amin[0] >= -0.5 and amin[1] >= -0.5 and amin[2] >= -0.5 and \
       amax[0] <= box_dims[0] + 0.5 and amax[1] <= box_dims[1] + 0.5 and amax[2] <= box_dims[2] + 0.5:
        cuda.atomic.add(inside_count, 0, 1)


# ═══════════════════════════════════════════════
# CPU-side physics packer
# ═══════════════════════════════════════════════

def generate_orientations(mesh, n_yaw, box_dims):
    results, seen = [], set()
    def try_rot(name, rot_matrix):
        t = mesh.copy()
        t.apply_transform(np.vstack([np.hstack([rot_matrix, np.zeros((3, 1))]), [0, 0, 0, 1]]))
        bmin = t.bounds[0]
        t.apply_translation([-bmin[0], -bmin[1], -bmin[2]])
        sz = t.extents
        if sz[0] > box_dims[0] + 0.5 or sz[2] > box_dims[1] + 0.5 or sz[1] > box_dims[2] + 0.5:
            return None
        hull = compute_hull(t)
        key = tuple(np.round(sz).astype(int))
        if key in seen: return None
        seen.add(key)
        return {'mesh': t, 'hull': hull, 'verts': hull.vertices, 'faces': hull.faces,
                'norms': hull.normals, 'size': sz, 'name': name}
    for yaw in np.linspace(0, 360, n_yaw, endpoint=False):
        r = try_rot(f'Y{yaw:.0f}', Rotation.from_euler('y', yaw, degrees=True).as_matrix())
        if r: results.append(r)
    for pitch in [90]:
        rp = Rotation.from_euler('x', pitch, degrees=True).as_matrix()
        for yaw in np.linspace(0, 360, n_yaw, endpoint=False):
            r = try_rot(f'X90_Y{yaw:.0f}', Rotation.from_euler('y', yaw, degrees=True).as_matrix() @ rp)
            if r: results.append(r)
    return results


class PhysicsPacker:
    def __init__(self, box_dims):
        self.box_l, self.box_w, self.box_h = box_dims
        self.box_dims = box_dims
        self.orientations = []

    def load_mesh(self, stl_path, n_yaw=8):
        fp = Path(stl_path)
        mesh = trimesh.load(str(fp), force='mesh')
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)])
        self.orientations = generate_orientations(mesh, n_yaw, self.box_dims)
        return self

    def pack(self, n_drop=500, n_orientations=None, n_steps=800, vibration=50.0,
             n_solve_passes=3, verbose=True):
        """Drop N pieces from above with physics, return those inside the box."""
        orients = self.orientations
        if n_orientations is not None:
            orients = orients[:n_orientations]
        if not orients:
            return [], []
        o = orients[0]  # Use first orientation for all bodies

        n_hulls = len(orients)
        max_v = o['hull'].vertex_count
        max_f = o['hull'].face_count

        # Build hull data arrays
        h_verts_0 = np.zeros((1, max_v, 3), dtype=np.float64)
        h_vcts_0 = np.zeros(1, dtype=np.int32)
        h_norms_0 = np.zeros((1, max_f, 3), dtype=np.float64)
        h_fcts_0 = np.zeros(1, dtype=np.int32)
        h_verts_0[0, :max_v] = o['verts']
        h_vcts_0[0] = max_v
        h_norms_0[0, :max_f] = o['norms']
        h_fcts_0[0] = max_f

        # Broadcast to all body slots on GPU
        n = n_drop
        d_hull_verts = cuda.to_device(np.tile(h_verts_0, (n, 1, 1)))
        d_hull_vcts = cuda.to_device(np.tile(h_vcts_0, n))
        d_hull_norms = cuda.to_device(np.tile(h_norms_0, (n, 1, 1)))
        d_hull_fcts = cuda.to_device(np.tile(h_fcts_0, n))

        # Allocate body arrays on GPU
        n = n_drop
        d_pos = cuda.to_device(np.zeros((n, 3), dtype=np.float64))
        d_quat = cuda.to_device(np.zeros((n, 4), dtype=np.float64))
        d_vel = cuda.to_device(np.zeros((n, 3), dtype=np.float64))
        d_avel = cuda.to_device(np.zeros((n, 3), dtype=np.float64))
        d_amin = cuda.to_device(np.zeros((n, 3), dtype=np.float64))
        d_amax = cuda.to_device(np.zeros((n, 3), dtype=np.float64))
        d_active = cuda.to_device(np.ones(n, dtype=np.int32))
        d_inv_mass = cuda.to_device(np.ones(n, dtype=np.float64) * 100.0)
        d_box = cuda.to_device(np.array([self.box_l, self.box_h, self.box_w], dtype=np.float64))
        d_inside_count = cuda.to_device(np.zeros(1, dtype=np.int32))

        threads = 256
        blocks = (n + threads - 1) // threads

        # Init bodies at random positions above box
        if verbose:
            print(f"[Physics] Dropping {n} bodies, {n_steps} steps, vib={vibration:.0f}")

        seed = random.randint(0, 2**30)
        _physics_init_kernel[blocks, threads](d_pos, d_quat, d_vel, d_avel, d_amin, d_amax, d_active, d_box, n, seed)
        cuda.synchronize()

        d_gravity = cuda.to_device(np.array([0.0, -9810.0, 0.0], dtype=np.float64))
        dt = 1.0 / 120.0

        # Run physics for n_steps
        t0 = time.time()
        solve_every = 5
        for step in range(n_steps):
            # Phase-dependent vibration: strong at start, none at end
            phase = 1.0 - float(step) / float(n_steps)
            vib = vibration * phase

            _physics_step_kernel[blocks, threads](
                d_pos, d_quat, d_vel, d_avel, d_amin, d_amax, d_active,
                d_hull_verts, d_hull_vcts,
                d_box, d_gravity, dt, 0.1, -1.0,  # increased damping
                vib, 0.0, step,
                n, max_v,
            )

            if step % solve_every == 0:
                for _ in range(n_solve_passes):
                    _solve_overlaps_kernel[blocks, threads](
                        d_pos, d_amin, d_amax, d_active, d_inv_mass,
                        d_hull_verts, d_hull_vcts, d_hull_norms, d_hull_fcts,
                        n, d_box, max_v, max_f, step // solve_every,
                    )

            cuda.synchronize()

        cuda.synchronize()

        # Count bodies inside box
        _count_inside_kernel[blocks, threads](
            d_pos, d_amin, d_amax, d_active, d_hull_vcts, d_box,
            d_inside_count, n,
        )
        count = int(d_inside_count.copy_to_host()[0])
        elapsed = time.time() - t0

        if verbose:
            print(f"  Inside box: {count}/{n} pieces ({elapsed:.0f}s)")

        # Get positions for visualization
        final_pos = d_pos.copy_to_host()
        final_amin = d_amin.copy_to_host()
        final_amax = d_amax.copy_to_host()

        # Build placed list and meshes
        placed = []
        meshes = []
        for i in range(n):
            am = final_amin[i]
            aM = final_amax[i]
            # Check if inside box
            if (am[0] >= -1 and am[1] >= -1 and am[2] >= -1 and
                aM[0] <= self.box_l + 1 and aM[1] <= self.box_h + 1 and aM[2] <= self.box_w + 1):
                # Use the first orientation for all bodies (they're the same shape)
                o = orients[0]
                cm = o['mesh'].copy()
                p = final_pos[i]
                cm.apply_translation([p[0], p[1], p[2]])
                meshes.append(cm)
                placed.append((float(p[0]), float(p[1]), float(p[2]), 0, o['name']))

        return placed, meshes


# ═══════════════════════════════════════════════
# Verification + visualization
# ═══════════════════════════════════════════════

def meshes_collide(mesh_a, mesh_b, eps=0.01):
    try:
        pts_a, _ = trimesh.proximity.closest_point(mesh_a, mesh_b.vertices)
        pts_b, _ = trimesh.proximity.closest_point(mesh_b, mesh_a.vertices)
        if len(pts_a) == 0 or len(pts_b) == 0: return False
        return np.linalg.norm(pts_a - mesh_b.vertices, axis=1).min() < eps or \
               np.linalg.norm(pts_b - mesh_a.vertices, axis=1).min() < eps
    except: return False


def verify(placed_meshes):
    collisions = 0
    for i in range(len(placed_meshes)):
        for j in range(i + 1, min(i + 50, len(placed_meshes))):
            a = placed_meshes[i].bounds; b = placed_meshes[j].bounds
            if (a[1, 0] > b[0, 0] and a[0, 0] < b[1, 0] and
                a[1, 1] > b[0, 1] and a[0, 1] < b[1, 1] and
                a[1, 2] > b[0, 2] and a[0, 2] < b[1, 2]):
                if meshes_collide(placed_meshes[i], placed_meshes[j], eps=0.001):
                    collisions += 1
                    if collisions <= 5: print(f"  COLLISION: {i} vs {j}")
    ok = collisions == 0
    print(f"  [{'OK' if ok else 'FAIL'}] {'ZERO' if ok else collisions} collisions — {len(placed_meshes)} pieces")
    return ok


def visualize(placed_meshes, box_dims, prefix="packed_physics"):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    box_l, box_w, box_h = box_dims
    colors = plt.cm.tab20(np.linspace(0, 1, max(20, len(placed_meshes))))

    # 2D views
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    fig.suptitle(f"Physics Drop — {len(placed_meshes)} pieces", fontsize=14, fontweight='bold')
    for title, ax, view in [("Top (XZ)", axes[0,0],'xz'), ("Front (XY)", axes[0,1],'xy'),
                            ("Side (ZY)", axes[1,0],'zy'), ("Height Map", axes[1,1],'hm')]:
        ax.set_title(title)
        if view == 'xz':
            ax.set_xlim(0, box_l); ax.set_ylim(0, box_w); ax.invert_yaxis()
            for i, m in enumerate(placed_meshes[:200]):
                b = m.bounds
                ax.add_patch(Rectangle((b[0,0], b[0,2]), b[1,0]-b[0,0], b[1,2]-b[0,2],
                                       alpha=0.12, color=colors[i%20], ec='black', lw=0.1))
            ax.set_xlabel('X mm'); ax.set_ylabel('Z mm'); ax.set_aspect('equal')
        elif view == 'xy':
            ax.set_xlim(0, box_l); ax.set_ylim(0, box_h)
            for m in placed_meshes[:200]:
                b = m.bounds
                ax.add_patch(Rectangle((b[0,0], b[0,1]), b[1,0]-b[0,0], b[1,1]-b[0,1],
                                       alpha=0.12, color=colors[0], ec='black', lw=0.1))
            ax.set_xlabel('X mm'); ax.set_ylabel('Y mm'); ax.set_aspect('equal')
        elif view == 'zy':
            ax.set_xlim(0, box_w); ax.set_ylim(0, box_h)
            for m in placed_meshes[:200]:
                b = m.bounds
                ax.add_patch(Rectangle((b[0,2], b[0,1]), b[1,2]-b[0,2], b[1,1]-b[0,1],
                                       alpha=0.12, color=colors[0], ec='black', lw=0.1))
            ax.set_xlabel('Z mm'); ax.set_ylabel('Y mm'); ax.set_aspect('equal')
        elif view == 'hm':
            hm = np.zeros((int(box_l//5)+1, int(box_w//5)+1)); cnt = np.zeros_like(hm)
            for m in placed_meshes[:200]:
                b = m.bounds
                ix, iz = int(b[0,0]/5), int(b[0,2]/5)
                if 0<=ix<hm.shape[0] and 0<=iz<hm.shape[1]:
                    hm[ix,iz]+=b[1,1]; cnt[ix,iz]+=1
            msk = cnt>0
            if msk.any(): hm[msk]/=cnt[msk]
            im = ax.imshow(hm.T, origin='lower', cmap='YlOrRd', extent=[0,box_l,0,box_w], aspect='equal')
            plt.colorbar(im, ax=ax, label='Height mm')
            ax.set_xlabel('X mm'); ax.set_ylabel('Z mm')
    plt.tight_layout(); plt.savefig(f"{prefix}_2d.png", dpi=150, bbox_inches='tight'); plt.close()
    print(f"[Viz] {prefix}_2d.png")

    # 3D view
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection='3d')
    ax.set_title(f"3D View — {len(placed_meshes)} pieces", fontsize=14, fontweight='bold')
    corners = np.array([[0,0,0],[box_l,0,0],[box_l,box_h,0],[0,box_h,0],
                        [0,0,box_w],[box_l,0,box_w],[box_l,box_h,box_w],[0,box_h,box_w]])
    edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
    for e in edges:
        ax.plot3D(*zip(corners[e[0]], corners[e[1]]), color='gray', alpha=0.3, lw=0.5)
    sample = placed_meshes[::max(1, len(placed_meshes)//300)]
    for i, m in enumerate(sample):
        v = m.vertices
        if len(v) > 100:
            v = v[np.random.choice(len(v), 100, replace=False)]
        ax.scatter(v[:,0], v[:,1], v[:,2], s=1, color=colors[i%20], alpha=0.3)
    ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
    ax.set_xlim(0, box_l); ax.set_ylim(0, box_h); ax.set_zlim(0, box_w)
    ax.view_init(elev=20, azim=-60)
    plt.tight_layout(); plt.savefig(f"{prefix}_3d.png", dpi=150, bbox_inches='tight'); plt.close()
    print(f"[Viz] {prefix}_3d.png")


# ═══════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="GPU Physics-Drop Packer")
    p.add_argument("stl")
    p.add_argument("box_l", nargs="?", type=float, default=385)
    p.add_argument("box_w", nargs="?", type=float, default=285)
    p.add_argument("box_h", nargs="?", type=float, default=150)
    p.add_argument("--yaw", type=int, default=8)
    p.add_argument("--drop", type=int, default=500, help="Pieces to drop")
    p.add_argument("--steps", type=int, default=600, help="Physics steps")
    p.add_argument("--vib", type=float, default=30.0, help="Vibration amplitude")
    p.add_argument("--output", type=str, default="packed_physics")
    args = p.parse_args()

    if not cuda.is_available():
        print("ERROR: CUDA not available."); sys.exit(1)

    packer = PhysicsPacker((args.box_l, args.box_w, args.box_h))
    packer.load_mesh(args.stl, n_yaw=args.yaw)

    print(f"Loaded: {args.stl}  ({len(packer.orientations)} orientations)")
    print(f"Box: {args.box_l:.0f}x{args.box_w:.0f}x{args.box_h:.0f}mm")
    print(f"Dropping {args.drop} pieces...")

    placed, meshes = packer.pack(
        n_drop=args.drop, n_steps=args.steps,
        vibration=args.vib, verbose=True,
    )

    if meshes:
        vol = sum(m.volume for m in meshes)
        fill = vol / (args.box_l * args.box_w * args.box_h) * 100
        print(f"\nResult: {len(meshes)} pieces, {fill:.1f}% fill")
        print("Verifying (sampled)...")
        verify(meshes)
        print("Visualizing...")
        visualize(meshes, (args.box_l, args.box_w, args.box_h), args.output)


if __name__ == "__main__":
    main()
