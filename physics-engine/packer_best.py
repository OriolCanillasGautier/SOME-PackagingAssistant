"""
packer_best.py — Best-possible 3D bin packer with backtracking.

Strategy: Batched GPU Y-scanning + iterative backtracking.
  - Stage 1: GPU finds lowest Y for ALL candidates in one launch
  - Stage 2: Pick best candidate, place, update GPU, repeat
  - Stage 3: Backtrack — remove last N pieces, try different order
  - Stage 4: Physics compaction (optional)

Usage:
    python packer_best.py [stl_file] [box_l] [box_w] [box_h] [scan_mm]
"""
import sys, time, math, argparse, heapq, random
from pathlib import Path
from collections import defaultdict
from datetime import datetime
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
# GPU kernel: batched Y-scanning + SAT (all candidates in one launch)
# ═══════════════════════════════════════════════

@cuda.jit
def _packer_kernel(
    candidates,          # [n_cand, 5] float64: x, z, ori_idx, min_y, valid
    hull_verts,          # [n_hulls, max_v, 3] float64
    hull_vert_counts,    # [n_hulls] int32
    hull_norms,          # [n_hulls, max_f, 3] float64
    hull_face_counts,    # [n_hulls] int32
    placed_verts,        # [n_placed, max_v, 3] float64 — world-space
    placed_counts,       # [n_placed] int32
    placed_norms,        # [n_placed, max_f, 3] float64
    placed_face_cts,     # [n_placed] int32
    n_placed,            # int32
    box_dims,            # float64[3]: box_l, box_h, box_w
    y_scan_res,          # float64
    n_hulls,
    max_y_scans,
    max_v,
    max_f,
):
    idx = cuda.grid(1)
    if idx >= candidates.shape[0]:
        return

    x = candidates[idx, 0]
    z = candidates[idx, 1]
    ori_idx = int(candidates[idx, 2])
    if ori_idx >= n_hulls:
        return

    nv = hull_vert_counts[ori_idx]
    nf = hull_face_counts[ori_idx]

    min_x_c = 1e30; max_x_c = -1e30
    min_z_c = 1e30; max_z_c = -1e30
    max_y_c = -1e30; min_y_c = 1e30

    for vi in range(nv):
        vx = hull_verts[ori_idx, vi, 0] + x
        vz = hull_verts[ori_idx, vi, 2] + z
        vy = hull_verts[ori_idx, vi, 1]
        if vx < min_x_c: min_x_c = vx
        if vx > max_x_c: max_x_c = vx
        if vz < min_z_c: min_z_c = vz
        if vz > max_z_c: max_z_c = vz
        if vy < min_y_c: min_y_c = vy
        if vy > max_y_c: max_y_c = vy

    cand_h = max_y_c - min_y_c

    if min_x_c < 0 or max_x_c > box_dims[0] or min_z_c < 0 or max_z_c > box_dims[2]:
        candidates[idx, 4] = 0.0
        return

    max_placed_y = 0.0
    for pi in range(n_placed):
        pnv = placed_counts[pi]
        p_min_x = 1e30; p_max_x = -1e30; p_min_z = 1e30; p_max_z = -1e30; p_max_y = -1e30
        for vi in range(pnv):
            pv = placed_verts[pi, vi]
            if pv[0] < p_min_x: p_min_x = pv[0]
            if pv[0] > p_max_x: p_max_x = pv[0]
            if pv[2] < p_min_z: p_min_z = pv[2]
            if pv[2] > p_max_z: p_max_z = pv[2]
            if pv[1] > p_max_y: p_max_y = pv[1]
        if max_x_c > p_min_x and min_x_c < p_max_x and max_z_c > p_min_z and min_z_c < p_max_z:
            if p_max_y > max_placed_y:
                max_placed_y = p_max_y

    base_y = max_placed_y
    found_y = -1.0
    max_scan = max_y_scans
    limit = int((box_dims[1] - cand_h - base_y) / y_scan_res) + 2
    if limit < max_scan:
        max_scan = limit
    if max_scan < 1:
        max_scan = 1

    for sy in range(max_scan):
        try_y = base_y + sy * y_scan_res
        if try_y + cand_h > box_dims[1] + 0.01:
            break

        cand_min_y = try_y + min_y_c
        cand_max_y = try_y + max_y_c

        collides = False
        for pi in range(n_placed):
            pnv = placed_counts[pi]
            pnf = placed_face_cts[pi]

            p_min_y = 1e30; p_max_y = -1e30
            for vi in range(pnv):
                py = placed_verts[pi, vi, 1]
                if py < p_min_y: p_min_y = py
                if py > p_max_y: p_max_y = py
            if cand_max_y <= p_min_y or cand_min_y >= p_max_y:
                continue

            # SAT: candidate face normals
            sep = False
            for fi in range(nf):
                n = hull_norms[ori_idx, fi]
                min_a = 1e30; max_a = -1e30
                for vi in range(nv):
                    d = n[0] * (hull_verts[ori_idx, vi, 0] + x) + \
                        n[1] * (hull_verts[ori_idx, vi, 1] + try_y) + \
                        n[2] * (hull_verts[ori_idx, vi, 2] + z)
                    if d < min_a: min_a = d
                    if d > max_a: max_a = d
                min_b = 1e30; max_b = -1e30
                for vi in range(pnv):
                    pv = placed_verts[pi, vi]
                    d = n[0] * pv[0] + n[1] * pv[1] + n[2] * pv[2]
                    if d < min_b: min_b = d
                    if d > max_b: max_b = d
                if max_a < min_b or max_b < min_a:
                    sep = True; break
            if sep: continue

            # SAT: placed face normals
            for fi in range(pnf):
                n = placed_norms[pi, fi]
                min_a = 1e30; max_a = -1e30
                for vi in range(nv):
                    d = n[0] * (hull_verts[ori_idx, vi, 0] + x) + \
                        n[1] * (hull_verts[ori_idx, vi, 1] + try_y) + \
                        n[2] * (hull_verts[ori_idx, vi, 2] + z)
                    if d < min_a: min_a = d
                    if d > max_a: max_a = d
                min_b = 1e30; max_b = -1e30
                for vi in range(pnv):
                    pv = placed_verts[pi, vi]
                    d = n[0] * pv[0] + n[1] * pv[1] + n[2] * pv[2]
                    if d < min_b: min_b = d
                    if d > max_b: max_b = d
                if max_a < min_b or max_b < min_a:
                    sep = True; break
            if sep: continue

            collides = True; break

        if not collides:
            found_y = try_y; break

    if found_y >= 0:
        candidates[idx, 3] = found_y
        candidates[idx, 4] = 1.0
    else:
        candidates[idx, 4] = 0.0


# ═══════════════════════════════════════════════
# GPU kernel: voxel occupancy collision (ported from packer_gpu_voxel.py)
# ═══════════════════════════════════════════════

@cuda.jit
def _voxel_pack_kernel(
    candidates,
    all_sparse,
    all_offsets,
    all_hm,
    all_hm_offsets,
    all_shapes,
    box_occ,
    box_hm,
    box_nx, box_ny, box_nz,
    y_res,
    y_limit,
):
    idx = cuda.grid(1)
    if idx >= candidates.shape[0]:
        return

    x = int(candidates[idx, 0])
    z = int(candidates[idx, 2])
    ori = int(candidates[idx, 1])
    if ori >= all_shapes.shape[0]:
        return

    sx, sy, sz = all_shapes[ori, 0], all_shapes[ori, 1], all_shapes[ori, 2]
    if x + sx > box_nx or z + sz > box_nz or sy > box_ny:
        return

    off_start = all_offsets[ori]
    off_end = all_offsets[ori + 1]

    hm_off_start = all_hm_offsets[ori]
    base_vox = 0
    for i in range(off_start, off_end):
        px = all_sparse[i, 0]
        py = all_sparse[i, 1]
        pz = all_sparse[i, 2]
        h = box_hm[x + px, z + pz]
        needed = h - py
        if needed > base_vox:
            base_vox = needed
    if base_vox < 0:
        base_vox = 0

    max_y = box_ny - sy
    if base_vox > max_y:
        return

    # Scan from y=0 up to min(base_vox, y_limit): the height map only bounds the
    # solid top of each column, so a piece may nest into a cavity/valley below it
    # (the base_vox "resting" height is a conservative overestimate).  When a
    # nested fit is found below base_vox we take it — this fills interior gaps
    # the plain falling-sand scan would leave behind.
    limit = y_limit
    if base_vox < limit:
        limit = base_vox
    for try_y in range(0, limit + 1):
        collides = False
        for ii in range(off_start, off_end):
            px = all_sparse[ii, 0]
            py = all_sparse[ii, 1]
            pz = all_sparse[ii, 2]
            if box_occ[x + px, try_y + py, z + pz]:
                collides = True
                break
        if not collides:
            candidates[idx, 3] = try_y * y_res
            candidates[idx, 4] = 1.0
            return

    # No nested fit within the sweep window: rest on top of the terrain.
    # base_vox is guaranteed collision-free (every piece voxel sits at or above
    # its column's height map, which is the max occupied +1).
    candidates[idx, 3] = base_vox * y_res
    candidates[idx, 4] = 1.0


# ═══════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════

def compute_face_normals(verts, faces):
    v0 = verts[faces[:, 0]]; v1 = verts[faces[:, 1]]; v2 = verts[faces[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    mag = np.linalg.norm(n, axis=1)
    mag[mag < 1e-12] = 1.0
    return n / mag[:, np.newaxis]


# ═══════════════════════════════════════════════
# InaccessibilityPoles — fast collision proxy
# ═══════════════════════════════════════════════

def compute_inaccessibility_poles(vertices, faces, n_poles=5):
    """Compute the N largest empty spheres inside a convex hull.
    Used as a fast collision proxy: if two meshes' poles don't overlap,
    the meshes definitely don't collide (conservative reject).
    Inspired by JonasTollenaere/sparrow-3d (LGPL-3.0)."""
    from scipy.spatial import ConvexHull as SPConvexHull
    import heapq

    verts = np.asarray(vertices, dtype=np.float64)
    if len(verts) < 4:
        center = verts.mean(axis=0)
        r = 0 if len(verts) < 2 else np.max(np.linalg.norm(verts - center, axis=1)) * 0.5
        return [(center.tolist(), float(r))]

    try:
        hull = SPConvexHull(verts)
        hull_verts = verts[hull.vertices]
        hull_normals = hull.equations[:, :3]
        hull_offsets = hull.equations[:, 3]
    except Exception:
        center = verts.mean(axis=0)
        r = np.max(np.linalg.norm(verts - center, axis=1)) * 0.3
        return [(center.tolist(), float(r))]

    def signed_distance(point):
        """Signed distance from point to convex hull surface."""
        d = hull_normals @ point + hull_offsets
        max_d = np.max(d)
        if max_d <= 0:
            return -np.min(np.abs(d))  # outside
        return np.min(d[d > 0])  # inside → positive

    aabb_min = hull_verts.min(axis=0)
    aabb_max = hull_verts.max(axis=0)
    extent = aabb_max - aabb_min
    side = float(np.max(extent))
    aabb_size = side * 0.6
    aabb_center = (aabb_min + aabb_max) / 2.0
    aabb_half = np.array([side, side, side]) * 0.5
    eps = side * 1e-4

    poles = []

    for _ in range(n_poles):
        queue = []
        center_point = aabb_center
        init_d = signed_distance(center_point)
        for prev in poles:
            pc = np.array(prev[0]); pr = prev[1]
            pd = float(np.linalg.norm(center_point - pc)) - pr
            if pd < init_d: init_d = pd
        best_point, best_d = center_point, max(0.0, float(init_d))
        heapq.heappush(queue, (-(best_d + side * 0.87), tuple(aabb_center - aabb_half), tuple(aabb_center + aabb_half)))

        while queue:
            neg_potential, bb_min_t, bb_max_t = heapq.heappop(queue)
            bb_min = np.array(bb_min_t); bb_max = np.array(bb_max_t)
            b_center = (bb_min + bb_max) * 0.5
            b_half_size = float(np.linalg.norm(bb_max - bb_min)) * 0.25
            if b_half_size < eps: continue

            potential = -neg_potential
            if potential < best_d + eps: break

            for cx in [bb_min[0], b_center[0], bb_max[0]]:
                for cy in [bb_min[1], b_center[1], bb_max[1]]:
                    for cz in [bb_min[2], b_center[2], bb_max[2]]:
                        pt = np.array([cx, cy, cz])
                        d = signed_distance(pt)
                        for prev in poles:
                            pc = np.array(prev[0]); pr = prev[1]
                            pd = float(np.linalg.norm(pt - pc)) - pr
                            if pd < d: d = pd
                        if d > best_d:
                            best_d = d; best_point = pt

            if best_d + b_half_size < best_d + eps: continue
            child_half = b_half_size * 0.5
            for ox in [-child_half, 0, child_half]:
                for oy in [-child_half, 0, child_half]:
                    for oz in [-child_half, 0, child_half]:
                        if abs(ox) + abs(oy) + abs(oz) < 1e-12: continue
                        c = b_center + np.array([ox, oy, oz])
                        d = signed_distance(c)
                        for prev in poles:
                            pc = np.array(prev[0]); pr = prev[1]
                            pd = float(np.linalg.norm(c - pc)) - pr
                            if pd < d: d = pd
                        pot = d + float(np.linalg.norm(np.array([ox, oy, oz])))
                        if pot > best_d - eps:
                            cmin = c - child_half; cmax = c + child_half
                            heapq.heappush(queue, (-pot, tuple(cmin), tuple(cmax)))

        if best_d > 0:
            poles.append((best_point.tolist(), float(best_d)))
        else:
            poles.append((best_point.tolist(), 0.0))

    return poles


def poles_collide(poles_a, transform_a, poles_b, transform_b):
    """Check if any pair of poles (in world space) overlap.
    Returns True if poles overlap (potential collision, need full check).
    Returns False if no overlap (definitely no collision — fast reject)."""
    if not poles_a or not poles_b:
        return True  # can't reject → assume collision
    for ca, ra in poles_a:
        wa = np.array(ca) + transform_a
        for cb, rb in poles_b:
            wb = np.array(cb) + transform_b
            if np.linalg.norm(wa - wb) < ra + rb:
                return True
    return False


def generate_orientations(mesh, n_yaw, box_dims, use_pitch_roll=True, shrink=0.4):
    results, seen = [], set()

    def try_rotation(name, rot_matrix):
        t = mesh.copy()
        t.apply_transform(np.vstack([np.hstack([rot_matrix, np.zeros((3, 1))]), [0, 0, 0, 1]]))
        bmin = t.bounds[0]
        t.apply_translation([-bmin[0], -bmin[1], -bmin[2]])
        sz = t.extents
        if sz[0] > box_dims[0] + 0.5 or sz[2] > box_dims[1] + 0.5 or sz[1] > box_dims[2] + 0.5:
            return None
        hull = compute_hull(t)
        key = tuple(np.round(sz).astype(int))
        if key in seen:
            return None
        seen.add(key)
        result = {'mesh': t, 'hull': hull, 'verts': hull.vertices, 'faces': hull.faces,
                  'norms': hull.normals, 'size': sz, 'name': name}
        # Compute shrunk collision proxy
        if shrink < 1.0:
            center = hull.vertices.mean(axis=0)
            sv = center + (hull.vertices - center) * shrink
            if len(sv) >= 4:
                try:
                    tmp = trimesh.Trimesh(vertices=np.asarray(sv, dtype=np.float64))
                    sh = compute_hull(tmp)
                    result['coll_verts'] = sh.vertices
                    result['coll_faces'] = sh.faces
                    result['coll_norms'] = sh.normals
                except Exception:
                    result['coll_verts'] = hull.vertices
                    result['coll_faces'] = hull.faces
                    result['coll_norms'] = hull.normals
            else:
                result['coll_verts'] = hull.vertices
                result['coll_faces'] = hull.faces
                result['coll_norms'] = hull.normals
        else:
            result['coll_verts'] = hull.vertices
            result['coll_faces'] = hull.faces
            result['coll_norms'] = hull.normals
        # InaccessibilityPoles: fast collision proxy (computed on demand, ~4s/orientation)
        result['poles'] = []  # disabled by default — enable with --poles flag
        return result

    # Yaw rotations (around Y axis)
    for yaw in np.linspace(0, 360, n_yaw, endpoint=False):
        rot = Rotation.from_euler('y', yaw, degrees=True).as_matrix()
        r = try_rotation(f'Y{yaw:.0f}', rot)
        if r: results.append(r)

    if use_pitch_roll:
        # Also try rotating to lie flat (around X) then yaw
        for pitch in [90]:
            rot_p = Rotation.from_euler('x', pitch, degrees=True).as_matrix()
            for yaw in np.linspace(0, 360, n_yaw, endpoint=False):
                rot_y = Rotation.from_euler('y', yaw, degrees=True).as_matrix()
                rot = rot_y @ rot_p
                r = try_rotation(f'X{pitch:.0f}_Y{yaw:.0f}', rot)
                if r: results.append(r)

        # Try rotating around Z then yaw
        for roll in [90]:
            rot_r = Rotation.from_euler('z', roll, degrees=True).as_matrix()
            for yaw in np.linspace(0, 360, n_yaw // 2, endpoint=False):
                rot_y = Rotation.from_euler('y', yaw, degrees=True).as_matrix()
                rot = rot_y @ rot_r
                r = try_rotation(f'Z{roll:.0f}_Y{yaw:.0f}', rot)
                if r: results.append(r)

    return results


_FCL_AVAILABLE = False
try:
    if hasattr(trimesh, 'collision') and hasattr(trimesh.collision, 'CollisionManager'):
        trimesh.collision.CollisionManager()  # test instantiation
        _FCL_AVAILABLE = True
except Exception:
    pass


# Meshes with fewer faces than this use the CPU voxelizer (kernel-launch/JIT
# overhead dominates below this; measured crossover ~ a few hundred faces).
_GPU_VOXEL_MIN_FACES = 512

def meshes_collide(mesh_a, mesh_b, eps=0.01):
    try:
        if _FCL_AVAILABLE:
            m = trimesh.collision.CollisionManager()
            m.add_object('a', mesh_a)
            m.add_object('b', mesh_b)
            in_collision, _ = m.in_collision_internal(return_names=True, return_data=False)
            if in_collision:
                return True
        # Fallback: vertex proximity check
        pts_a, _ = trimesh.proximity.closest_point(mesh_a, mesh_b.vertices)
        pts_b, _ = trimesh.proximity.closest_point(mesh_b, mesh_a.vertices)
        if len(pts_a) == 0 or len(pts_b) == 0: return False
        return np.linalg.norm(pts_a - mesh_b.vertices, axis=1).min() < eps or \
               np.linalg.norm(pts_b - mesh_a.vertices, axis=1).min() < eps
    except Exception:
        return False


@cuda.jit(device=True)
def _tri_box_axis_test(cx, cy, cz, hx, hy, hz, a0, a1, a2, b0, b1, b2, c0, c1, c2, ax, ay, az):
    """SAT projection test of triangle (a,b,c) and box (center c, half h) on axis (ax,ay,az)."""
    pa = (a0 - cx) * ax + (a1 - cy) * ay + (a2 - cz) * az
    pb = (b0 - cx) * ax + (b1 - cy) * ay + (b2 - cz) * az
    pc = (c0 - cx) * ax + (c1 - cy) * ay + (c2 - cz) * az
    tmin = min(pa, pb, pc)
    tmax = max(pa, pb, pc)
    r = hx * abs(ax) + hy * abs(ay) + hz * abs(az)
    return not (tmax < -r or tmin > r)


@cuda.jit(device=True)
def _tri_voxel_overlap(v0, v1, v2, cx, cy, cz, half):
    """Conservative triangle-vs-voxel overlap (Schwarz & Seidel SAT, 13 axes).
    Returns True if the triangle overlaps the voxel whose center is (cx,cy,cz)."""
    h = half
    # Triangle edges
    e0x = v1[0] - v0[0]; e0y = v1[1] - v0[1]; e0z = v1[2] - v0[2]
    e1x = v2[0] - v0[0]; e1y = v2[1] - v0[1]; e1z = v2[2] - v0[2]
    e2x = v2[0] - v1[0]; e2y = v2[1] - v1[1]; e2z = v2[2] - v1[2]

    a0 = v0[0]; a1 = v0[1]; a2 = v0[2]
    b0 = v1[0]; b1 = v1[1]; b2 = v1[2]
    c0 = v2[0]; c1 = v2[1]; c2 = v2[2]

    # Box face normals (3)
    if not _tri_box_axis_test(cx, cy, cz, h, h, h, a0, a1, a2, b0, b1, b2, c0, c1, c2, 1.0, 0.0, 0.0):
        return False
    if not _tri_box_axis_test(cx, cy, cz, h, h, h, a0, a1, a2, b0, b1, b2, c0, c1, c2, 0.0, 1.0, 0.0):
        return False
    if not _tri_box_axis_test(cx, cy, cz, h, h, h, a0, a1, a2, b0, b1, b2, c0, c1, c2, 0.0, 0.0, 1.0):
        return False
    # Triangle normal
    nx = e0y * e1z - e0z * e1y
    ny = e0z * e1x - e0x * e1z
    nz = e0x * e1y - e0y * e1x
    nl = math.sqrt(nx * nx + ny * ny + nz * nz)
    if nl > 1e-12:
        nx /= nl; ny /= nl; nz /= nl
        if not _tri_box_axis_test(cx, cy, cz, h, h, h, a0, a1, a2, b0, b1, b2, c0, c1, c2, nx, ny, nz):
            return False
    # Edge × box-axis cross products (9)
    for (ex, ey, ez) in ((e0x, e0y, e0z), (e1x, e1y, e1z), (e2x, e2y, e2z)):
        for (wx, wy, wz) in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
            ax = ey * wz - ez * wy
            ay = ez * wx - ex * wz
            az = ex * wy - ey * wx
            if abs(ax) + abs(ay) + abs(az) < 1e-12:
                continue
            if not _tri_box_axis_test(cx, cy, cz, h, h, h, a0, a1, a2, b0, b1, b2, c0, c1, c2, ax, ay, az):
                return False
    return True


@cuda.jit
def _voxelize_surface_kernel(verts, faces, occ, nx, ny, nz, bmin, cell):
    """One thread per triangle: mark every voxel the triangle overlaps (conservative)."""
    fi = cuda.grid(1)
    if fi >= faces.shape[0]:
        return
    f0 = faces[fi, 0]; f1 = faces[fi, 1]; f2 = faces[fi, 2]
    v0 = (verts[f0, 0], verts[f0, 1], verts[f0, 2])
    v1 = (verts[f1, 0], verts[f1, 1], verts[f1, 2])
    v2 = (verts[f2, 0], verts[f2, 1], verts[f2, 2])
    half = cell * 0.5
    # Triangle AABB in voxel space
    tminx = min(v0[0], v1[0], v2[0])
    tmaxx = max(v0[0], v1[0], v2[0])
    tminy = min(v0[1], v1[1], v2[1])
    tmaxy = max(v0[1], v1[1], v2[1])
    tminz = min(v0[2], v1[2], v2[2])
    tmaxz = max(v0[2], v1[2], v2[2])
    ix0 = int((tminx - bmin[0]) / cell)
    ix1 = int((tmaxx - bmin[0]) / cell) + 1
    iy0 = int((tminy - bmin[1]) / cell)
    iy1 = int((tmaxy - bmin[1]) / cell) + 1
    iz0 = int((tminz - bmin[2]) / cell)
    iz1 = int((tmaxz - bmin[2]) / cell) + 1
    if ix0 < 0: ix0 = 0
    if iy0 < 0: iy0 = 0
    if iz0 < 0: iz0 = 0
    if ix1 > nx - 1: ix1 = nx - 1
    if iy1 > ny - 1: iy1 = ny - 1
    if iz1 > nz - 1: iz1 = nz - 1
    for iz in range(iz0, iz1 + 1):
        cz = bmin[2] + (iz + 0.5) * cell
        for iy in range(iy0, iy1 + 1):
            cy = bmin[1] + (iy + 0.5) * cell
            for ix in range(ix0, ix1 + 1):
                cx = bmin[0] + (ix + 0.5) * cell
                if _tri_voxel_overlap(v0, v1, v2, cx, cy, cz, half):
                    idx = (ix * ny + iy) * nz + iz
                    cuda.atomic.max(occ, idx, 1)


def voxelize_mesh(mesh, cell_size):
    """Rasterize mesh faces into 3D sparse occupancy data.
    Returns (sparse_voxels, origin_mm) where sparse_voxels is [N,3] int32
    local voxel indices and origin_mm is the mm position of voxel (0,0,0).

    Uses the GPU conservative voxelizer (Schwarz & Seidel: SAT triangle-vs-voxel
    test, one thread per face) for meshes with >= _GPU_VOXEL_MIN_FACES faces,
    falling back to the CPU point-in-triangle rasterizer otherwise. Both paths
    run binary_fill_holes afterwards to turn the surface shell into solid
    occupancy."""
    bmin = mesh.bounds[0] - cell_size
    bmax = mesh.bounds[1] + cell_size
    nx = max(1, int(math.ceil((bmax[0] - bmin[0]) / cell_size)))
    ny = max(1, int(math.ceil((bmax[1] - bmin[1]) / cell_size)))
    nz = max(1, int(math.ceil((bmax[2] - bmin[2]) / cell_size)))
    occ = np.zeros((nx, ny, nz), dtype=np.uint8)

    # GPU conservative surface voxelization (Schwarz & Seidel). The SAT test
    # marks every voxel a triangle overlaps — no gaps in the surface shell, so
    # binary_fill_holes always fills the true interior. GPU only pays off for
    # meshes with enough faces to hide kernel-launch/JIT overhead; tiny meshes
    # use the CPU point-in-triangle rasterizer instead.
    gpu_used = False
    n_faces = int(len(mesh.faces))
    if n_faces >= _GPU_VOXEL_MIN_FACES:
        try:
            if cuda.is_available():
                verts = np.ascontiguousarray(mesh.vertices, dtype=np.float64)
                faces = np.ascontiguousarray(mesh.faces, dtype=np.int32)
                occ_flat = np.zeros(nx * ny * nz, dtype=np.int32)
                d_verts = cuda.to_device(verts)
                d_faces = cuda.to_device(faces)
                d_occ = cuda.to_device(occ_flat)
                d_bmin = cuda.to_device(np.ascontiguousarray(bmin, dtype=np.float64))
                threads = 256
                blocks = max(1, (n_faces + threads - 1) // threads)
                _voxelize_surface_kernel[blocks, threads](d_verts, d_faces, d_occ,
                                                          nx, ny, nz, d_bmin, float(cell_size))
                cuda.synchronize()
                occ_flat = d_occ.copy_to_host()
                occ = occ_flat.reshape(nx, ny, nz).astype(np.uint8)
                gpu_used = True
        except Exception:
            gpu_used = False
            occ = np.zeros((nx, ny, nz), dtype=np.uint8)

    if not gpu_used:
        _voxelize_mesh_cpu(mesh, cell_size, occ, bmin, nx, ny, nz)

    try:
        from scipy.ndimage import binary_fill_holes
        occ = binary_fill_holes(occ > 0).astype(np.uint8)
    except Exception:
        pass

    sparse = np.argwhere(occ > 0).astype(np.int32)
    return sparse, bmin


def _voxelize_mesh_cpu(mesh, cell_size, occ, bmin, nx, ny, nz):
    """Reference CPU rasterizer: point-in-triangle test at voxel centers."""
    for fi in range(len(mesh.faces)):
        f = mesh.faces[fi]
        v0 = mesh.vertices[f[0]].copy()
        v1 = mesh.vertices[f[1]].copy()
        v2 = mesh.vertices[f[2]].copy()

        tri_min = np.minimum(np.minimum(v0, v1), v2)
        tri_max = np.maximum(np.maximum(v0, v1), v2)

        ix0 = max(0, int((tri_min[0] - bmin[0]) / cell_size))
        ix1 = min(nx - 1, int((tri_max[0] - bmin[0]) / cell_size))
        iy0 = max(0, int((tri_min[1] - bmin[1]) / cell_size))
        iy1 = min(ny - 1, int((tri_max[1] - bmin[1]) / cell_size))
        iz0 = max(0, int((tri_min[2] - bmin[2]) / cell_size))
        iz1 = min(nz - 1, int((tri_max[2] - bmin[2]) / cell_size))

        if ix0 > ix1 or iy0 > iy1 or iz0 > iz1:
            continue

        e0x, e0y, e0z = float(v1[0]-v0[0]), float(v1[1]-v0[1]), float(v1[2]-v0[2])
        e1x, e1y, e1z = float(v2[0]-v0[0]), float(v2[1]-v0[1]), float(v2[2]-v0[2])

        nx_n = e0y*e1z - e0z*e1y
        ny_n = e0z*e1x - e0x*e1z
        nz_n = e0x*e1y - e0y*e1x
        nl = math.sqrt(nx_n*nx_n + ny_n*ny_n + nz_n*nz_n)
        if nl < 1e-12:
            continue
        nx_n /= nl; ny_n /= nl; nz_n /= nl

        d00 = e0x*e0x + e0y*e0y + e0z*e0z
        d01 = e0x*e1x + e0y*e1y + e0z*e1z
        d11 = e1x*e1x + e1y*e1y + e1z*e1z
        denom = d00 * d11 - d01 * d01
        if abs(denom) < 1e-12:
            continue

        v0x, v0y, v0z = float(v0[0]), float(v0[1]), float(v0[2])

        for ix in range(ix0, ix1 + 1):
            cx = bmin[0] + (ix + 0.5) * cell_size
            dpx0 = cx - v0x
            for iy in range(iy0, iy1 + 1):
                cy = bmin[1] + (iy + 0.5) * cell_size
                dpy0 = cy - v0y
                for iz in range(iz0, iz1 + 1):
                    cz = bmin[2] + (iz + 0.5) * cell_size
                    dpz0 = cz - v0z

                    dist = abs(dpx0*nx_n + dpy0*ny_n + dpz0*nz_n)
                    if dist > cell_size * 1.1:
                        continue

                    d20 = dpx0*e0x + dpy0*e0y + dpz0*e0z
                    d21 = dpx0*e1x + dpy0*e1y + dpz0*e1z
                    u = (d11 * d20 - d01 * d21) / denom
                    v = (d00 * d21 - d01 * d20) / denom

                    if u >= -0.08 and v >= -0.08 and u + v <= 1.08:
                        occ[ix, iy, iz] = 1


def generate_sparrow_voxel_orientations(mesh, cell_size, n_yaw=8, n_roll=4, n_pitch=4, box_dims=None):
    results, seen = [], set()
    for yaw in np.linspace(0, 360, n_yaw, endpoint=False):
        for roll in np.linspace(0, 360, n_roll, endpoint=False):
            for pitch in np.linspace(0, 360, n_pitch, endpoint=False):
                rot = Rotation.from_euler('xyz', [roll, pitch, yaw], degrees=True).as_matrix()
                t = mesh.copy()
                t.apply_transform(np.vstack([np.hstack([rot, np.zeros((3, 1))]), [0, 0, 0, 1]]))
                bmin_orig = t.bounds[0]
                t.apply_translation([-bmin_orig[0], -bmin_orig[1], -bmin_orig[2]])
                sz = t.extents
                if box_dims and (sz[0] > box_dims[0] + 0.5 or sz[2] > box_dims[2] + 0.5 or
                                 sz[1] > box_dims[1] + 0.5):
                    continue
                key = tuple(np.round(sz).astype(int))
                if key in seen:
                    continue
                seen.add(key)
                sparse, origin = voxelize_mesh(t, cell_size)
                n_occ = int(len(sparse))
                if n_occ == 0:
                    continue
                shift_x = int(sparse[:, 0].min())
                shift_y = int(sparse[:, 1].min())
                shift_z = int(sparse[:, 2].min())
                sparse_shifted = sparse - np.array([shift_x, shift_y, shift_z], dtype=np.int32)
                sx_v = int(sparse_shifted[:, 0].max() + 1)
                sy_v = int(sparse_shifted[:, 1].max() + 1)
                sz_v = int(sparse_shifted[:, 2].max() + 1)
                shape = (sx_v, sy_v, sz_v)
                hm = np.zeros((shape[0], shape[2]), dtype=np.int32)
                for p in sparse_shifted:
                    if p[1] + 1 > hm[p[0], p[2]]:
                        hm[p[0], p[2]] = p[1] + 1
                results.append({
                    'mesh': t, 'size': sz, 'name': f"Y{yaw:.0f}R{roll:.0f}P{pitch:.0f}",
                    'sparse': sparse_shifted, 'n_occ': n_occ,
                    'hm': hm, 'shape': shape,
                    'rotation': rot,
                })
    results.sort(key=lambda o: (o['size'][1], o['n_occ']))
    return results


# ═══════════════════════════════════════════════
# Best Packer
# ═══════════════════════════════════════════════

class BestPacker:
    def __init__(self, box_dims, scan_step=5.0, y_scan_res=2.0):
        self.box_l, self.box_w, self.box_h = box_dims
        self.box_dims = box_dims
        self.scan_step = scan_step
        self.y_scan_res = y_scan_res
        self.orientations = []
        self._max_v = self._max_f = 0
        self._d_hull_verts = self._d_hull_vcts = self._d_hull_norms = self._d_hull_fcts = None
        self._d_box_dims = None
        self._d_placed_verts = self._d_placed_counts = self._d_placed_norms = self._d_placed_face_cts = None
        self._max_placed = 2000
        self._rng = None
        # Hierarchical search defaults
        self.coarse_step = 10.0
        self.fine_step = 2.0
        self.coarse_top = 40
        self.coarse_per_orientation = 8
        self.coarse_min_distance = 15.0

    def load_mesh(self, stl_path, n_yaw=8, shrink=0.4):
        fp = Path(stl_path)
        mesh = trimesh.load(str(fp), force='mesh')
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)])
        self._load_orientations(mesh, n_yaw, shrink)

    def load_mesh_from_data(self, trimesh_mesh, n_yaw=8, shrink=0.4):
        self._load_orientations(trimesh_mesh, n_yaw, shrink)

    def _load_orientations(self, mesh, n_yaw, shrink):
        self._source_mesh = mesh
        self.orientations = generate_orientations(mesh, n_yaw, self.box_dims, shrink=shrink)
        self._max_v = max(len(o.get('coll_verts', o['verts'])) for o in self.orientations)
        self._max_f = max(len(o.get('coll_faces', o['faces'])) for o in self.orientations)
        self._init_gpu_buffers()

    def _init_gpu_buffers(self):
        n = len(self.orientations); mv = self._max_v; mf = self._max_f
        hv = np.zeros((n, mv, 3), dtype=np.float64); hvc = np.zeros(n, dtype=np.int32)
        hn = np.zeros((n, mf, 3), dtype=np.float64); hfc = np.zeros(n, dtype=np.int32)
        for i, o in enumerate(self.orientations):
            cv = o.get('coll_verts', o['verts'])
            cn = o.get('coll_norms', o['norms'])
            cf = o.get('coll_faces', o['faces'])
            nv, nf = len(cv), len(cf)
            hv[i, :nv] = cv; hvc[i] = nv
            hn[i, :nf] = cn; hfc[i] = nf
        self._d_hull_verts = cuda.to_device(hv); self._d_hull_vcts = cuda.to_device(hvc)
        self._d_hull_norms = cuda.to_device(hn); self._d_hull_fcts = cuda.to_device(hfc)
        self._d_box_dims = cuda.to_device(np.array([self.box_l, self.box_h, self.box_w], dtype=np.float64))
        self._d_placed_verts = cuda.to_device(np.zeros((self._max_placed, mv, 3), dtype=np.float64))
        self._d_placed_counts = cuda.to_device(np.zeros(self._max_placed, dtype=np.int32))
        self._d_placed_norms = cuda.to_device(np.zeros((self._max_placed, mf, 3), dtype=np.float64))
        self._d_placed_face_cts = cuda.to_device(np.zeros(self._max_placed, dtype=np.int32))

    def _generate_candidates(self, step=None):
        s = step if step is not None else self.scan_step
        cands = []
        for oi, o in enumerate(self.orientations):
            sx, _, sz = o['size']
            for x in np.arange(0, self.box_l - sx + 0.01, s):
                for z in np.arange(0, self.box_w - sz + 0.01, s):
                    cands.append([float(x), float(z), float(oi), 99999.0, 0.0])
        return np.array(cands, dtype=np.float64) if cands else np.zeros((0, 5), dtype=np.float64)

    def _gpu_scan(self, n_placed, candidates=None, verbose=False):
        """One GPU launch: find min Y for all candidates. Returns valid candidates with Y."""
        cand_array = candidates if candidates is not None else self._generate_candidates()
        n_cand = len(cand_array)
        if n_cand == 0:
            return np.zeros((0, 5))

        d_cand = cuda.to_device(cand_array)
        threads = 256
        blocks = (n_cand + threads - 1) // threads

        _packer_kernel[blocks, threads](
            d_cand,
            self._d_hull_verts, self._d_hull_vcts,
            self._d_hull_norms, self._d_hull_fcts,
            self._d_placed_verts, self._d_placed_counts,
            self._d_placed_norms, self._d_placed_face_cts,
            n_placed,
            self._d_box_dims, self.y_scan_res,
            len(self.orientations), 100,
            self._max_v, self._max_f,
        )
        cuda.synchronize()
        results = d_cand.copy_to_host()
        return results[results[:, 4] > 0.5]

    # ── Hierarchical coarse-to-fine candidate search ──

    def _select_diverse_candidates(self, valid, top_global=40, top_per_orientation=8, min_distance=15.0):
        if len(valid) == 0:
            return np.zeros((0, 5))

        valid = valid[np.argsort(valid[:, 3])]
        if self._rng is None:
            self._rng = np.random.RandomState(42)

        selected = []
        orient_counts = defaultdict(int)

        for row in valid:
            x, z, oi, y = float(row[0]), float(row[1]), int(row[2]), float(row[3])

            if len(selected) >= top_global:
                break
            if orient_counts[oi] >= top_per_orientation:
                continue

            too_close = False
            for sx, sz, _, _ in selected:
                if (x - sx) ** 2 + (z - sz) ** 2 < min_distance ** 2:
                    too_close = True
                    break
            if too_close:
                continue

            selected.append((x, z, oi, y))
            orient_counts[oi] += 1

        return np.array([[x, z, oi, y, 1.0] for x, z, oi, y in selected], dtype=np.float64)

    def _refine_candidates(self, selected, fine_step=2.0, radius=10.0):
        refined = []
        seen = set()

        for row in selected:
            cx, cz, oi = float(row[0]), float(row[1]), int(row[2])
            o = self.orientations[oi]
            sx, _, sz = o['size']

            for dx in np.arange(-radius, radius + 0.01, fine_step):
                for dz in np.arange(-radius, radius + 0.01, fine_step):
                    x = cx + dx
                    z = cz + dz
                    if x < 0 or x > self.box_l - sx + 0.01:
                        continue
                    if z < 0 or z > self.box_w - sz + 0.01:
                        continue

                    key = (round(x, 3), round(z, 3), oi)
                    if key in seen:
                        continue
                    seen.add(key)
                    refined.append([float(x), float(z), float(oi), 99999.0, 0.0])

        return np.array(refined, dtype=np.float64) if refined else np.zeros((0, 5), dtype=np.float64)

    def _choose_best(self, valid, placed_count=0):
        if len(valid) == 0:
            return None

        y_min = valid[:, 3].min()
        scores = valid[:, 3].copy()
        if placed_count > 0:
            norm_heights = valid[:, 3] / max(1.0, self.box_h)
            scores = scores + 0.02 * self.box_h * norm_heights

        best_idx = np.argmin(scores)
        return valid[best_idx]

    def _explore_local(self, x, y, z, oi, placed, meshes, n_samples=50):
        """Generate local perturbations around (x,y,z) and return best non-colliding position by composite score."""
        o = self.orientations[oi]
        sx, sy, sz = o['size']
        candidate_poles = o.get('poles', [])
        local_max_h = 0
        for px, py, pz, poi_p, _ in placed:
            top = py + self.orientations[poi_p]['size'][1]
            if top > local_max_h: local_max_h = top

        best_score = float('inf')
        best_xyz = (x, y, z)
        found_any = False
        half_window = self.scan_step * 2

        for i in range(n_samples):
            if i < 20:
                dx = (random.random() - 0.5) * half_window * 2
                dy = (random.random() - 0.5) * half_window * 0.5
                dz = (random.random() - 0.5) * half_window * 2
            else:
                j = (i - 20) % 6
                k = (i - 20) // 6
                dx = (j - 2.5) * self.scan_step * 0.3
                dy = 0
                dz = (k - 2.5) * self.scan_step * 0.3

            nx, ny, nz = x + dx, max(0, y + dy), z + dz
            if nx < 0 or nz < 0 or nx + sx > self.box_l or nz + sz > self.box_w: continue
            if ny + sy > self.box_h: continue

            cm = o['mesh'].copy(); cm.apply_translation([nx, ny, nz])
            collides = False
            for pi, (px_p, py_p, pz_p, poi_p, _) in enumerate(placed):
                b1, b2 = cm.bounds, meshes[pi].bounds
                if not (b1[1,0] > b2[0,0] and b1[0,0] < b2[1,0] and
                        b1[1,1] > b2[0,1] and b1[0,1] < b2[1,1] and
                        b1[1,2] > b2[0,2] and b1[0,2] < b2[1,2]): continue
                placed_poles = self.orientations[poi_p].get('poles', [])
                if candidate_poles and placed_poles:
                    if not poles_collide(candidate_poles, np.array([nx, ny, nz]),
                                        placed_poles, np.array([px_p, py_p, pz_p])): continue
                if meshes_collide(cm, meshes[pi]): collides = True; break
            if collides: continue

            new_max_h = max(local_max_h, ny + sy)
            height_increase = max(0, new_max_h - local_max_h)
            score = ny + 0.10 * height_increase + 0.005 * ((nx - self.box_l/2)**2 + (nz - self.box_w/2)**2) / max(1, self.box_l)

            if score < best_score:
                best_score = score
                best_xyz = (nx, ny, nz)
                found_any = True

        return best_xyz, found_any

    def _place_piece_gpu(self, pi, x, y, z, oi):
        o = self.orientations[oi]
        wv = o['verts'] + np.array([x, y, z])
        for vi in range(len(o['verts'])):
            for d in range(3):
                self._d_placed_verts[pi, vi, d] = wv[vi, d]
        self._d_placed_counts[pi] = np.int32(len(o['verts']))
        self._d_placed_face_cts[pi] = np.int32(len(o['faces']))
        wns = compute_face_normals(wv, o['faces'])
        for fi in range(len(o['faces'])):
            for d in range(3):
                self._d_placed_norms[pi, fi, d] = wns[fi, d]

    # ── Voxel occupancy helpers (for sparrow collision detection) ──

    def _ensure_voxel_data(self, cell_size):
        if hasattr(self, '_voxel_data') and self._voxel_data is not None \
           and getattr(self, '_voxel_cell_size', 0) == cell_size:
            return
        self._voxel_cell_size = cell_size
        self._voxel_data = []
        for o in self.orientations:
            sparse, origin = voxelize_mesh(o['mesh'], cell_size)
            occ = np.zeros(o['mesh'].extents.round().astype(int) + 5, dtype=np.uint8)
            sx_v = int(math.ceil(o['size'][0] / cell_size)) + 2
            sy_v = int(math.ceil(o['size'][1] / cell_size)) + 2
            sz_v = int(math.ceil(o['size'][2] / cell_size)) + 2
            shape = (max(1, sx_v), max(1, sy_v), max(1, sz_v))
            hm = np.zeros((shape[0], shape[2]), dtype=np.int32)
            for p in sparse:
                py = p[1]
                if py + 1 > hm[p[0], p[2]]:
                    hm[p[0], p[2]] = py + 1
            self._voxel_data.append({
                'sparse': sparse, 'origin': origin,
                'shape': shape, 'hm': hm, 'n_occ': len(sparse),
            })
        self._init_gpu_voxel_buffers()
        return self._voxel_data

    def _init_gpu_voxel_buffers(self):
        vd = self._voxel_data
        all_sparse_list = [d['sparse'] for d in vd]
        all_hm_list = [d['hm'].flatten() for d in vd]
        all_shapes = np.array([d['shape'] for d in vd], dtype=np.int32)
        all_offsets = np.zeros(len(vd) + 1, dtype=np.int32)
        all_hm_offsets = np.zeros(len(vd) + 1, dtype=np.int32)
        for i in range(len(vd)):
            all_offsets[i + 1] = all_offsets[i] + len(all_sparse_list[i])
            all_hm_offsets[i + 1] = all_hm_offsets[i] + len(all_hm_list[i])
        self._voxel_all_sparse = np.concatenate(all_sparse_list).astype(np.int32)
        self._voxel_all_hm = np.concatenate(all_hm_list).astype(np.int32)
        self._voxel_all_shapes = all_shapes
        self._voxel_all_offsets = all_offsets
        self._voxel_all_hm_offsets = all_hm_offsets
        self._d_voxel_all_sparse = cuda.to_device(self._voxel_all_sparse)
        self._d_voxel_all_offsets = cuda.to_device(self._voxel_all_offsets)
        self._d_voxel_all_hm = cuda.to_device(self._voxel_all_hm)
        self._d_voxel_all_hm_offsets = cuda.to_device(self._voxel_all_hm_offsets)
        self._d_voxel_all_shapes = cuda.to_device(self._voxel_all_shapes)

    def _mark_in_grid(self, grid, piece_id, x, y, z, oi, cell_size):
        vd = self._voxel_data[oi]
        sparse, origin = vd['sparse'], vd['origin']
        ox = int(round((x + origin[0]) / cell_size))
        oy = int(round((y + origin[1]) / cell_size))
        oz = int(round((z + origin[2]) / cell_size))
        wv = sparse + np.array([ox, oy, oz], dtype=np.int32)
        gx, gy, gz = wv[:, 0], wv[:, 1], wv[:, 2]
        sh = grid.shape
        m = (gx >= 0) & (gx < sh[0]) & (gy >= 0) & (gy < sh[1]) & (gz >= 0) & (gz < sh[2])
        grid[gx[m], gy[m], gz[m]] = piece_id

    def _item_collides_in_grid(self, grid, piece_id, x, y, z, oi, cell_size):
        vd = self._voxel_data[oi]
        sparse, origin = vd['sparse'], vd['origin']
        ox = int(round((x + origin[0]) / cell_size))
        oy = int(round((y + origin[1]) / cell_size))
        oz = int(round((z + origin[2]) / cell_size))
        wv = sparse + np.array([ox, oy, oz], dtype=np.int32)
        gx, gy, gz = wv[:, 0], wv[:, 1], wv[:, 2]
        sh = grid.shape
        m = (gx >= 0) & (gx < sh[0]) & (gy >= 0) & (gy < sh[1]) & (gz >= 0) & (gz < sh[2])
        vals = grid[gx[m], gy[m], gz[m]]
        return np.any((vals != 0) & (vals != piece_id))

    def _clear_from_grid(self, grid, piece_id, x, y, z, oi, cell_size):
        vd = self._voxel_data[oi]
        sparse, origin = vd['sparse'], vd['origin']
        ox = int(round((x + origin[0]) / cell_size))
        oy = int(round((y + origin[1]) / cell_size))
        oz = int(round((z + origin[2]) / cell_size))
        wv = sparse + np.array([ox, oy, oz], dtype=np.int32)
        gx, gy, gz = wv[:, 0], wv[:, 1], wv[:, 2]
        sh = grid.shape
        m = (gx >= 0) & (gx < sh[0]) & (gy >= 0) & (gy < sh[1]) & (gz >= 0) & (gz < sh[2])
        gx, gy, gz = gx[m], gy[m], gz[m]
        pos = (gx, gy, gz)
        mask = grid[pos] == piece_id
        if mask.any():
            grid[gx[mask], gy[mask], gz[mask]] = 0

    def _check_occupied(self, grid, x, y, z, sparse, origin, cell_size):
        ox = int(round((x + origin[0]) / cell_size))
        oy = int(round((y + origin[1]) / cell_size))
        oz = int(round((z + origin[2]) / cell_size))
        wv = sparse + np.array([ox, oy, oz], dtype=np.int32)
        gx, gy, gz = wv[:, 0], wv[:, 1], wv[:, 2]
        sh = grid.shape
        m = (gx >= 0) & (gx < sh[0]) & (gy >= 0) & (gy < sh[1]) & (gz >= 0) & (gz < sh[2])
        return np.any(grid[gx[m], gy[m], gz[m]] != 0)

    # ── Greedy baseline ──

    def pack_greedy(self, max_pieces=500, verbose=True, beam_width=5, hierarchical=False, explore_local=False):
        placed, meshes = [], []
        consecutive = 0
        t0 = time.time()

        if hierarchical and verbose:
            print(f"[Hierarchical] coarse_step={self.coarse_step}, fine_step={self.fine_step}, "
                  f"top={self.coarse_top}, per_orient={self.coarse_per_orientation}, "
                  f"min_dist={self.coarse_min_distance}")

        while len(placed) < max_pieces and consecutive < 20:
            if hierarchical:
                coarse = self._generate_candidates(step=self.coarse_step)
                valid = self._gpu_scan(len(placed), candidates=coarse)
                if len(valid) == 0:
                    consecutive += 1
                    continue
                selected = self._select_diverse_candidates(
                    valid,
                    top_global=self.coarse_top,
                    top_per_orientation=self.coarse_per_orientation,
                    min_distance=self.coarse_min_distance,
                )
                refined = self._refine_candidates(selected, fine_step=self.fine_step, radius=self.coarse_step)
                valid = self._gpu_scan(len(placed), candidates=refined)
                if len(valid) == 0:
                    consecutive += 1
                    continue
                best_row = self._choose_best(valid, len(placed))
                if best_row is None:
                    consecutive += 1
                    continue
                x, z, oi, y = best_row[0], best_row[1], int(best_row[2]), best_row[3]
                if verbose and len(placed) == 0:
                    print(f"  [coarse] {len(coarse):,} candidates → {len(valid)} valid, "
                          f"selected {len(selected)}, refined {len(refined):,}")
            else:
                valid = self._gpu_scan(len(placed))
                if len(valid) == 0:
                    consecutive += 1
                    continue
                top_n = min(beam_width, len(valid))
                top = valid[np.argsort(valid[:, 3])[:top_n]]
                best = top[random.randint(0, len(top) - 1)]
                x, z, oi, y = best[0], best[1], int(best[2]), best[3]

            # Local exploration: try perturbations to find a better non-colliding position
            if explore_local and placed:
                (x, y, z), found = self._explore_local(x, y, z, oi, placed, meshes)
                if not found:
                    consecutive += 1
                    continue

            o = self.orientations[oi]

            cm = o['mesh'].copy(); cm.apply_translation([x, y, z])
            candidate_poles = o.get('poles', [])
            collides = False
            for pi, (px, py, pz, poi, _) in enumerate(placed):
                b1, b2 = cm.bounds, meshes[pi].bounds
                if (b1[1, 0] > b2[0, 0] and b1[0, 0] < b2[1, 0] and
                    b1[1, 1] > b2[0, 1] and b1[0, 1] < b2[1, 1] and
                    b1[1, 2] > b2[0, 2] and b1[0, 2] < b2[1, 2]):
                    placed_poles = self.orientations[poi].get('poles', [])
                    if candidate_poles and placed_poles:
                        if not poles_collide(candidate_poles, np.array([x, y, z]),
                                            placed_poles, np.array([px, py, pz])):
                            continue  # fast reject: poles don't overlap
                    if meshes_collide(cm, meshes[pi]): collides = True; break
            if collides: continue

            meshes.append(cm); placed.append((x, y, z, oi, o['name']))
            self._place_piece_gpu(len(placed) - 1, x, y, z, oi)
            consecutive = 0

            if verbose and len(placed) % 25 == 0:
                vol = sum(m.volume for m in meshes)
                fill = vol / (self.box_l * self.box_w * self.box_h) * 100
                print(f"  [{len(placed)}] {fill:.1f}% fill, {time.time()-t0:.0f}s")

        elapsed = time.time() - t0
        if verbose and placed:
            vol = sum(m.volume for m in meshes)
            fill = vol / (self.box_l * self.box_w * self.box_h) * 100
            print(f"  DONE: {len(placed)} pieces, {fill:.1f}% fill, {elapsed:.0f}s")
        return placed, meshes

    # ── Backtracking optimizer ──

    def pack_backtrack(self, max_pieces=500, backtrack_depth=5, n_attempts=20, verbose=True):
        """Greedy with backtracking: remove last N pieces, try different order."""
        # First, do full greedy
        placed, meshes = self.pack_greedy(max_pieces, verbose=False)
        best_placed = list(placed)
        best_meshes = list(meshes)

        if verbose:
            vol = sum(m.volume for m in meshes)
            fill = vol / (self.box_l * self.box_w * self.box_h) * 100
            print(f"[Backtrack] Baseline: {len(placed)} pieces, {fill:.1f}% fill")

        n_placed = len(placed)
        improved = True
        attempts = 0

        while improved and attempts < n_attempts:
            improved = False
            attempts += 1

            for d in range(1, min(backtrack_depth + 1, n_placed + 1)):
                # Remove last d pieces
                keep = n_placed - d
                sub_placed = placed[:keep]
                sub_meshes = meshes[:keep]

                # Re-upload kept pieces to GPU
                for pi in range(keep):
                    x, y, z, oi, _ = sub_placed[pi]
                    self._place_piece_gpu(pi, x, y, z, oi)

                # Try to pack more starting from this state
                consecutive = 0
                while len(sub_placed) < max_pieces and consecutive < 20:
                    valid = self._gpu_scan(len(sub_placed))
                    if len(valid) == 0:
                        consecutive += 1
                        continue

                    # Randomly choose among top candidates (not just the best)
                    top_n = min(5, len(valid))
                    top = valid[np.argsort(valid[:, 3])[:top_n]]
                    best = top[random.randint(0, len(top) - 1)]
                    x, z, oi, y = best[0], best[1], int(best[2]), best[3]
                    o = self.orientations[oi]

                    cm = o['mesh'].copy(); cm.apply_translation([x, y, z])
                    candidate_poles = o.get('poles', [])
                    collides = False
                    for pi, pm in enumerate(sub_meshes):
                        b1, b2 = cm.bounds, pm.bounds
                        if (b1[1, 0] > b2[0, 0] and b1[0, 0] < b2[1, 0] and
                            b1[1, 1] > b2[0, 1] and b1[0, 1] < b2[1, 1] and
                            b1[1, 2] > b2[0, 2] and b1[0, 2] < b2[1, 2]):
                            placed_poles = self.orientations[sub_placed[pi][3]].get('poles', [])
                            if candidate_poles and placed_poles:
                                if not poles_collide(candidate_poles, np.array([x, y, z]),
                                                    placed_poles, np.array([sub_placed[pi][0], sub_placed[pi][1], sub_placed[pi][2]])):
                                    continue
                            if meshes_collide(cm, pm): collides = True; break
                    if collides: continue

                    sub_meshes.append(cm); sub_placed.append((x, y, z, oi, o['name']))
                    self._place_piece_gpu(len(sub_placed) - 1, x, y, z, oi)
                    consecutive = 0

                if len(sub_placed) > len(best_placed):
                    improved = True
                    best_placed = list(sub_placed)
                    best_meshes = list(sub_meshes)
                    vol = sum(m.volume for m in sub_meshes)
                    fill = vol / (self.box_l * self.box_w * self.box_h) * 100
                    if verbose:
                        print(f"  [{attempts}] Improved: {len(sub_placed)} pieces, {fill:.1f}% fill (d={d})")
                    placed = best_placed
                    meshes = best_meshes
                    n_placed = len(placed)
                    break  # restart from the better state

        if verbose:
            vol = sum(m.volume for m in best_meshes)
            fill = vol / (self.box_l * self.box_w * self.box_h) * 100
            print(f"  FINAL: {len(best_placed)} pieces, {fill:.1f}% fill, {attempts} attempts")
        return best_placed, best_meshes

    # ── Physics compaction (Stage 3) ──

    def compact(self, placed, placed_meshes, n_steps=120, verbose=True):
        if len(placed) == 0:
            return placed, placed_meshes

        from engine.world import World
        if verbose:
            print(f"[Compact] {len(placed)} pieces, {n_steps} steps")

        # Use the engine World for physics (with vibration to break arching)
        w = World(cell_size=self.scan_step * 4, gravity=(0, -9810, 0),
                  vibration_amplitude=0.8, vibration_frequency=120.0)

        stl_path = str(Path(__file__).resolve().parent / "stl" / "part.stl")
        for pi, (x, y, z, oi, name) in enumerate(placed):
            w.add_body(stl_path, position=(x, y + 5.0, z), mass=0.01, name=f"p{pi}")

        for _ in range(2):
            w.step(dt=1/240, n_solver_iterations=4, baumgarte=0.4)
        for _ in range(n_steps):
            w.step(dt=1/240, n_solver_iterations=4, baumgarte=0.4)

        s = w.get_state()
        compacted, compacted_meshes = [], []
        for i, b in enumerate(s['bodies']):
            pos = b['position']
            oi = placed[i][3]
            o = self.orientations[oi]
            cm = o['mesh'].copy(); cm.apply_translation([pos[0], pos[1], pos[2]])
            compacted.append((float(pos[0]), float(pos[1]), float(pos[2]), oi, placed[i][4]))
            compacted_meshes.append(cm)
        return compacted, compacted_meshes

    # ── Layer packer ──

    def pack_layers(self, max_pieces=1000, verbose=True):
        """Pack layer by layer, picking the best orientation per layer."""
        placed, meshes = [], []
        current_y = 0.0
        t0 = time.time()
        if verbose:
            print(f"[Layers] {len(self.orientations)} orientations")

        while len(placed) < max_pieces and current_y < self.box_h:
            best_ori, best_count = -1, 0
            best_layer_placed, best_layer_meshes = [], []

            for oi, o in enumerate(self.orientations):
                sy = o['size'][1]
                if current_y + sy > self.box_h:
                    continue
                lp, lm = self._fill_one_layer(oi, placed, meshes)
                if len(lp) > best_count:
                    best_count = len(lp)
                    best_ori = oi
                    best_layer_placed, best_layer_meshes = lp, lm

            if best_count == 0:
                current_y += self.y_scan_res
                continue

            for p, m in zip(best_layer_placed, best_layer_meshes):
                placed.append(p)
                meshes.append(m)
                pi = len(placed) - 1
                self._place_piece_gpu(pi, p[0], p[1], p[2], p[3])

            top_y = max(p[1] + self.orientations[p[3]]['size'][1] for p in best_layer_placed)
            current_y = max(current_y, top_y)

            if verbose:
                elapsed = time.time() - t0
                vol = sum(m.volume for m in meshes)
                fill = vol / (self.box_l * self.box_w * self.box_h) * 100
                nm = self.orientations[best_ori]['name']
                print(f"  Y~{current_y:.0f}mm: +{best_count}pcs ({nm}) → {len(placed)} total, {fill:.1f}% fill, {elapsed:.0f}s")

        elapsed = time.time() - t0
        if verbose and placed:
            vol = sum(m.volume for m in meshes)
            fill = vol / (self.box_l * self.box_w * self.box_h) * 100
            print(f"  DONE: {len(placed)} pieces, {fill:.1f}% fill, {elapsed:.0f}s")
        return placed, meshes

    def _fill_one_layer(self, oi, existing_placed, existing_meshes):
        o = self.orientations[oi]
        sx, sz = o['size'][0], o['size'][2]
        lp, lm = [], []

        # Upload existing to GPU
        for pi in range(min(len(existing_placed), self._max_placed)):
            p = existing_placed[pi]
            po = self.orientations[p[3]]
            wv = po['verts'] + np.array([p[0], p[1], p[2]])
            for vi in range(len(po['verts'])):
                for d in range(3):
                    self._d_placed_verts[pi, vi, d] = wv[vi, d]
            self._d_placed_counts[pi] = np.int32(len(po['verts']))
            self._d_placed_face_cts[pi] = np.int32(len(po['faces']))
            wns = compute_face_normals(wv, po['faces'])
            for fi in range(len(po['faces'])):
                for d in range(3):
                    self._d_placed_norms[pi, fi, d] = wns[fi, d]

        consecutive = 0
        while consecutive < 20:
            cands = [[float(x), float(z), float(oi), 99999.0, 0.0]
                     for x in np.arange(0, self.box_l - sx + 0.01, self.scan_step)
                     for z in np.arange(0, self.box_w - sz + 0.01, self.scan_step)]
            if not cands:
                break

            d_cand = cuda.to_device(np.array(cands, dtype=np.float64))
            threads = 256
            blocks = (len(cands) + threads - 1) // threads
            _packer_kernel[blocks, threads](
                d_cand, self._d_hull_verts, self._d_hull_vcts,
                self._d_hull_norms, self._d_hull_fcts,
                self._d_placed_verts, self._d_placed_counts,
                self._d_placed_norms, self._d_placed_face_cts,
                len(existing_placed) + len(lp),
                self._d_box_dims, self.y_scan_res,
                len(self.orientations), 100, self._max_v, self._max_f,
            )
            cuda.synchronize()
            results = d_cand.copy_to_host()
            valid = results[results[:, 4] > 0.5]
            if len(valid) == 0:
                consecutive += 1
                continue

            top_n = min(5, len(valid))
            top = valid[np.argsort(valid[:, 3])[:top_n]]
            best = top[random.randint(0, len(top) - 1)]
            x, z, y = best[0], best[1], best[3]
            cm = o['mesh'].copy(); cm.apply_translation([x, y, z])
            candidate_poles = o.get('poles', [])
            all_meshes = existing_meshes + lm
            all_placed = existing_placed + lp
            collides = False
            for pi, pm in enumerate(all_meshes):
                b1, b2 = cm.bounds, pm.bounds
                if (b1[1,0] > b2[0,0] and b1[0,0] < b2[1,0] and
                    b1[1,1] > b2[0,1] and b1[0,1] < b2[1,1] and
                    b1[1,2] > b2[0,2] and b1[0,2] < b2[1,2]):
                    placed_poles = self.orientations[all_placed[pi][3]].get('poles', [])
                    if candidate_poles and placed_poles:
                        if not poles_collide(candidate_poles, np.array([x, y, z]),
                                            placed_poles, np.array([all_placed[pi][0], all_placed[pi][1], all_placed[pi][2]])):
                            continue
                    if meshes_collide(cm, pm): collides = True; break
            if collides: continue

            lm.append(cm); lp.append((x, y, z, oi, o['name']))
            lpi = len(existing_placed) + len(lp) - 1
            wv = o['verts'] + np.array([x, y, z])
            for vi in range(len(o['verts'])):
                for d in range(3):
                    self._d_placed_verts[lpi, vi, d] = wv[vi, d]
            self._d_placed_counts[lpi] = np.int32(len(o['verts']))
            self._d_placed_face_cts[lpi] = np.int32(len(o['faces']))
            wns = compute_face_normals(wv, o['faces'])
            for fi in range(len(o['faces'])):
                for d in range(3):
                    self._d_placed_norms[lpi, fi, d] = wns[fi, d]
            consecutive = 0

        return lp, lm

    # ── Sparrow: GPU-accelerated voxel packing ──

    def _gpu_voxel_scan_all(self, box_occ, box_hm, nx_vox, ny_vox, nz_vox, step_vox=1,
                            y_limit=64, x_offset=0, z_offset=0):
        cand_parts = []
        for oi, vd in enumerate(self._sparrow_voxel_data):
            sx_v, sy_v, sz_v = vd['shape']
            if sy_v > ny_vox:
                continue
            xs = np.arange(x_offset, nx_vox - sx_v + 1, step_vox, dtype=np.float64)
            zs = np.arange(z_offset, nz_vox - sz_v + 1, step_vox, dtype=np.float64)
            nx, nz = len(xs), len(zs)
            if nx == 0 or nz == 0:
                continue
            n = nx * nz
            cand = np.zeros((n, 5), dtype=np.float64)
            cand[:, 0] = np.repeat(xs, nz)
            cand[:, 1] = float(oi)
            cand[:, 2] = np.tile(zs, nx)
            cand[:, 3] = -1.0
            cand[:, 4] = 0.0
            cand_parts.append(cand)
        if not cand_parts:
            return np.zeros((0, 5))
        cand_array = np.concatenate(cand_parts)
        n_cand = len(cand_array)
        d_cand = cuda.to_device(cand_array)
        d_box_occ = cuda.to_device(box_occ)
        d_box_hm = cuda.to_device(box_hm)
        threads = 256
        blocks = (n_cand + threads - 1) // threads
        _voxel_pack_kernel[blocks, threads](
            d_cand,
            self._d_sparrow_sparse,
            self._d_sparrow_offsets,
            self._d_sparrow_hm,
            self._d_sparrow_hm_offsets,
            self._d_sparrow_shapes,
            d_box_occ,
            d_box_hm,
            nx_vox, ny_vox, nz_vox,
            self._sparrow_cell_size,
            y_limit,
        )
        cuda.synchronize()
        return d_cand.copy_to_host()

    def pack_sparrow(self, max_pieces=500, n_workers=4, n_iterations=200, cell_size=None, verbose=True,
                     progress_callback=None, beam_width=8, seed=None):
        if cell_size is None:
            cell_size = 1.0
        if seed is not None:
            random.seed(seed)
        source = getattr(self, '_source_mesh', None)
        if source is None:
            if verbose:
                print("[Sparrow] No source mesh, falling back to greedy")
            return self.pack_greedy(max_pieces, verbose)

        n_yaw = 8
        n_roll = 4
        n_pitch = 4
        if verbose:
            print(f"[Sparrow] Generating voxel orientations (yaw={n_yaw} roll={n_roll} pitch={n_pitch})...", end=" ", flush=True)
        t0_ori = time.time()
        sparrow_oris = generate_sparrow_voxel_orientations(
            source, cell_size, n_yaw=n_yaw, n_roll=n_roll, n_pitch=n_pitch,
            box_dims=(self.box_l, self.box_w, self.box_h),
        )
        if verbose:
            print(f"{len(sparrow_oris)} orientations ({time.time()-t0_ori:.1f}s)", flush=True)

        if not sparrow_oris:
            if verbose:
                print("[Sparrow] No valid orientations, falling back to greedy")
            return self.pack_greedy(max_pieces, verbose)

        self._sparrow_voxel_data = sparrow_oris
        self._sparrow_cell_size = cell_size

        all_sparse_list = [d['sparse'] for d in sparrow_oris]
        all_hm_list = [d['hm'].flatten() for d in sparrow_oris]
        all_shapes = np.array([d['shape'] for d in sparrow_oris], dtype=np.int32)
        all_offsets = np.zeros(len(sparrow_oris) + 1, dtype=np.int32)
        all_hm_offsets = np.zeros(len(sparrow_oris) + 1, dtype=np.int32)
        for i in range(len(sparrow_oris)):
            all_offsets[i + 1] = all_offsets[i] + len(all_sparse_list[i])
            all_hm_offsets[i + 1] = all_hm_offsets[i] + len(all_hm_list[i])
        self._d_sparrow_sparse = cuda.to_device(np.concatenate(all_sparse_list).astype(np.int32))
        self._d_sparrow_offsets = cuda.to_device(all_offsets)
        self._d_sparrow_hm = cuda.to_device(np.concatenate(all_hm_list).astype(np.int32))
        self._d_sparrow_hm_offsets = cuda.to_device(all_hm_offsets)
        self._d_sparrow_shapes = cuda.to_device(all_shapes)

        n_items = min(max_pieces, 500)
        if verbose:
            print(f"[Sparrow] GPU: {n_items} items, cell={cell_size}mm, "
                  f"{len(sparrow_oris)} orientations, {n_workers} workers", flush=True)

        best_placed, best_meshes = [], []
        best_count = 0
        t0 = time.time()

        nx_vox = int(math.ceil(self.box_l / cell_size))
        ny_vox = int(math.ceil(self.box_h / cell_size))
        nz_vox = int(math.ceil(self.box_w / cell_size))

        # Nesting scan window (voxels): base_vox is the falling-sand resting height,
        # but scanning y from 0..min(base_vox, y_limit) also finds cavity/valley fits
        # below the height map, filling interior gaps. 40% of box height (~64mm in a
        # 160mm box) was empirically the sweet spot for the falling-sand terrain.
        nest_y_limit = max(4, int(round(0.4 * self.box_h / cell_size)))
        # How many lowest-Y candidates to place per GPU scan. Each scan is the
        # expensive step, so placing a small batch of mutually non-overlapping
        # pieces per scan keeps the total scan count low without hurting quality.
        batch_size = 6

        for worker in range(n_workers):
            box_occ = np.zeros((nx_vox, ny_vox, nz_vox), dtype=np.uint8)
            box_hm = np.zeros((nx_vox, nz_vox), dtype=np.int32)
            placed_w = []
            meshes_w = []
            consecutive = 0
            iter_count = 0
            # Deterministic per-worker candidate-grid offset so repeated workers
            # probe slightly different arrangements (best-of-N kept below).
            x_offset = worker % 2
            z_offset = (worker // 2) % 2

            while len(placed_w) < n_items and consecutive < 30 and iter_count < n_iterations:
                iter_count += 1

                results = self._gpu_voxel_scan_all(box_occ, box_hm, nx_vox, ny_vox, nz_vox, 1,
                                                   y_limit=nest_y_limit,
                                                   x_offset=x_offset, z_offset=z_offset)
                valid = results[:, 4] > 0.5
                if not valid.any():
                    consecutive += 1
                    continue
                consecutive = 0

                # Place up to `batch_size` lowest-Y candidates from this scan in
                # one go. Candidates are mutually checked against the updated
                # occupancy grid, so a batch never overlaps itself or the box.
                order = np.argsort(results[valid][:, 3])
                valid_results = results[valid]
                placed_batch = 0
                for bi in order:
                    if placed_batch >= batch_size:
                        break
                    best = valid_results[bi]
                    best_x, best_oi, best_z, best_y_vox = int(best[0]), int(best[1]), int(best[2]), best[3]
                    best_y_mm = best_y_vox

                    vd = sparrow_oris[best_oi]
                    sp = vd['sparse']
                    by_vox = int(best_y_mm / cell_size)
                    world_sp = sp + np.array([best_x, by_vox, best_z])
                    if box_occ[world_sp[:, 0], world_sp[:, 1], world_sp[:, 2]].any():
                        continue

                    box_occ[world_sp[:, 0], world_sp[:, 1], world_sp[:, 2]] = 1

                    for p in sp:
                        wx, wy, wz = best_x + p[0], by_vox + p[1], best_z + p[2]
                        if wy + 1 > box_hm[wx, wz]:
                            box_hm[wx, wz] = wy + 1

                    x_mm = best_x * cell_size
                    z_mm = best_z * cell_size
                    cm = vd['mesh'].copy()
                    cm.apply_translation([x_mm, best_y_mm, z_mm])
                    meshes_w.append(cm)
                    placed_w.append((x_mm, best_y_mm, z_mm, best_oi, vd['name']))
                    placed_batch += 1

                    if progress_callback and len(placed_w) % 5 == 0:
                        progress_callback(max(best_count, len(placed_w)), time.time() - t0, list(placed_w))

                    if verbose and len(placed_w) % 50 == 0:
                        elapsed = time.time() - t0
                        fill = box_occ.sum() * cell_size**3 / (self.box_l * self.box_w * self.box_h) * 100
                        print(f"  [Worker {worker+1}] {len(placed_w)} pieces, {fill:.1f}% fill, {elapsed:.0f}s",
                              flush=True)

            if len(placed_w) > best_count:
                best_count = len(placed_w)
                best_placed = list(placed_w)
                best_meshes = list(meshes_w)
                if verbose:
                    vol = sum(m.volume for m in meshes_w)
                    fill = vol / (self.box_l * self.box_w * self.box_h) * 100
                    print(f"  [Worker {worker+1}] done: {len(placed_w)} pieces, {fill:.1f}% fill, iter={iter_count}",
                          flush=True)

        elapsed = time.time() - t0
        vol = sum(m.volume for m in best_meshes) if best_meshes else 0
        fill = vol / (self.box_l * self.box_w * self.box_h) * 100 if vol > 0 else 0
        if verbose:
            print(f"  [Sparrow] DONE: {best_count} pieces, {fill:.1f}% fill, {elapsed:.0f}s", flush=True)
        return best_placed, best_meshes

    # ── Shared voxel setup for Stacking / Compartment ──

    def _prepare_voxel_orients(self, cell_size, verbose=False):
        """Generate sparrow-style voxel orientations and upload GPU buffers.
        Sets self._sparrow_voxel_data / self._sparrow_cell_size (read by
        server.py for placement data). Returns the orientation list or None.
        When self._fixed_orientation is set, only in-plane spins of the
        user's chosen pose are generated (the mesh is already pre-rotated to
        the chosen pose; the piece keeps resting on the same face but can
        rotate freely in the floor plane, which is what real nesting needs).
        When self._horizontal_angle is set, only the spin closest to that
        angle is kept (used by the re-optimize "ask horizontal orientation"
        flow, e.g. force the 90° arrangement)."""
        source = getattr(self, '_source_mesh', None)
        if source is None:
            return None
        t0 = time.time()
        if getattr(self, '_fixed_orientation', False):
            n_yaw = 1
            n_roll = 1
            n_pitch = 8
        else:
            n_yaw, n_roll, n_pitch = 8, 4, 4
        oris = generate_sparrow_voxel_orientations(
            source, cell_size, n_yaw=n_yaw, n_roll=n_roll, n_pitch=n_pitch,
            box_dims=(self.box_l, self.box_w, self.box_h),
        )
        if verbose:
            print(f"  {len(oris)} orientations ({time.time()-t0:.1f}s)", flush=True)
        if not oris:
            return None
        ha = getattr(self, '_horizontal_angle', None)
        if ha is not None:
            best_oi = min(range(len(oris)),
                          key=lambda i: abs(float(oris[i]['name'].split('P')[-1]) - ha))
            oris = [oris[best_oi]]
            if verbose:
                print(f"  horizontal_angle={ha}° -> {oris[0]['name']}", flush=True)
        self._sparrow_voxel_data = oris
        self._sparrow_cell_size = cell_size

        all_sparse_list = [d['sparse'] for d in oris]
        all_hm_list = [d['hm'].flatten() for d in oris]
        all_shapes = np.array([d['shape'] for d in oris], dtype=np.int32)
        all_offsets = np.zeros(len(oris) + 1, dtype=np.int32)
        all_hm_offsets = np.zeros(len(oris) + 1, dtype=np.int32)
        for i in range(len(oris)):
            all_offsets[i + 1] = all_offsets[i] + len(all_sparse_list[i])
            all_hm_offsets[i + 1] = all_hm_offsets[i] + len(all_hm_list[i])
        self._d_sparrow_sparse = cuda.to_device(np.concatenate(all_sparse_list).astype(np.int32))
        self._d_sparrow_offsets = cuda.to_device(all_offsets)
        self._d_sparrow_hm = cuda.to_device(np.concatenate(all_hm_list).astype(np.int32))
        self._d_sparrow_hm_offsets = cuda.to_device(all_hm_offsets)
        self._d_sparrow_shapes = cuda.to_device(all_shapes)
        return oris

    @staticmethod
    def _pick_min_footprint_ori(oris, nx_vox, ny_vox, nz_vox):
        """Smallest (size_x × size_z) orientation that still fits in the voxel box."""
        best_oi, best_fp = -1, float('inf')
        for oi, o in enumerate(oris):
            sx, sy, sz = o['shape']
            if sx > nx_vox or sy > ny_vox or sz > nz_vox:
                continue
            fp = o['size'][0] * o['size'][2]
            if fp < best_fp:
                best_fp, best_oi = fp, oi
        return best_oi

    @staticmethod
    def _pick_stack_ori(oris, nx_vox, ny_vox, nz_vox):
        """Pick the orientation that packs the MOST pieces per full column:
        score = (max layers per column) × (columns that fit on the floor)."""
        best_oi, best_score = -1, -1.0
        for oi, o in enumerate(oris):
            sx, sy, sz = o['shape']
            if sx > nx_vox or sy > ny_vox or sz > nz_vox:
                continue
            layers = max(1, ny_vox // max(1, sy))
            cols_x = max(1, nx_vox // max(1, sx))
            cols_z = max(1, nz_vox // max(1, sz))
            score = layers * cols_x * cols_z
            if score > best_score:
                best_score, best_oi = score, oi
        return best_oi

    @staticmethod
    def _pick_compartment_ori(oris, box_l, box_h, box_w, cell_size, gap=None):
        """Pick the orientation that maximizes the compartment grid:
        score = (cells along L) × (cells along W) × (max layers in H).
        Fills the box far better than min-footprint alone."""
        if gap is None:
            gap = cell_size
        best_oi, best_score = -1, -1.0
        for oi, o in enumerate(oris):
            sx_mm, sy_mm, sz_mm = o['size']
            if sx_mm > box_l + 0.01 or sy_mm > box_h + 0.01 or sz_mm > box_w + 0.01:
                continue
            step_l = sx_mm + gap
            step_w = sz_mm + gap
            n_cells_l = max(1, int((box_l - sx_mm + 0.01) // step_l) + 1)
            n_cells_w = max(1, int((box_w - sz_mm + 0.01) // step_w) + 1)
            n_layers = max(1, int(box_h // max(0.01, sy_mm + gap)))
            score = n_cells_l * n_cells_w * n_layers
            if score > best_score:
                best_score, best_oi = score, oi
        return best_oi

    # ── Stacking: columns that nest, tiled across the box ──

    def pack_stacking(self, max_pieces=500, cell_size=None, verbose=True, progress_callback=None):
        if cell_size is None:
            cell_size = 1.5
        oris = self._prepare_voxel_orients(cell_size, verbose)
        if oris is None:
            if verbose:
                print("[Stacking] No source/orientations, falling back to greedy")
            return self.pack_greedy(max_pieces, verbose)

        nx_vox = int(math.ceil(self.box_l / cell_size))
        ny_vox = int(math.ceil(self.box_h / cell_size))
        nz_vox = int(math.ceil(self.box_w / cell_size))

        # Pick the orientation that packs the most pieces per full column
        # (max layers × columns that fit the floor), then valley-nest within
        # that single orientation. With the user's chosen pose this runs over
        # the in-plane spins of that pose, so the piece rests on the same
        # face but the longest axis is turned to fill the box best.
        best_oi = self._pick_stack_ori(oris, nx_vox, ny_vox, nz_vox)
        if best_oi < 0:
            if verbose:
                print("[Stacking] No orientation fits the box, falling back to greedy")
            return self.pack_greedy(max_pieces, verbose)
        vd = oris[best_oi]

        # Smart stacking: small in-plane rotation variants (±1°, ±2°) of the
        # chosen orientation. A flat piece with a protuberance (e.g. a ring
        # with a bump) nests tighter when the bump can rotate out of the way
        # layer by layer — the packer tries every variant at each placement
        # and takes the one that nests LOWEST (ties keep the base pose).
        # Only for the fixed-pose path: free orientation already explores
        # coarse angles, and the variants only make sense around one pose.
        variants = None
        if getattr(self, '_fixed_orientation', False) and getattr(self, '_smart_stack', True):
            variants = [vd]
            for ang in (1.0, -1.0, 2.0, -2.0):
                var = _inplane_rotated_variant(vd, ang, cell_size)
                if var is not None:
                    variants.append(var)
            # Register variants in the shared orientation list so placements,
            # refinement and the final mesh rebuild all stay consistent.
            self._sparrow_voxel_data = oris + variants[1:]
            if verbose:
                print(f"[Stacking] smart stacking: {len(variants)} in-plane variants", flush=True)

        sp = vd['sparse']
        sx_v, sy_v, sz_v = vd['shape']
        px, py, pz = sp[:, 0], sp[:, 1], sp[:, 2]

        if variants is not None:
            v_sparse = [v['sparse'] for v in variants]
            v_px = [v['sparse'][:, 0] for v in variants]
            v_py = [v['sparse'][:, 1] for v in variants]
            v_pz = [v['sparse'][:, 2] for v in variants]
            v_shape = [v['shape'] for v in variants]
            v_hm = [v['hm'] for v in variants]
            v_mesh = [v['mesh'] for v in variants]
            v_name = [v['name'] for v in variants]
            v_oi = [best_oi] + [len(oris) + k - 1 for k in range(1, len(variants))]
            max_sy = max(s[1] for s in v_shape)
            # Variants can be 1-2 voxels larger than the base after rotation
            # re-gridding — scan bounds use the widest footprint so no
            # variant ever indexes outside the box grid.
            scan_sx = max(s[0] for s in v_shape)
            scan_sz = max(s[2] for s in v_shape)
        else:
            scan_sx, scan_sz = sx_v, sz_v

        box_occ = np.zeros((nx_vox, ny_vox, nz_vox), dtype=np.uint8)
        box_hm = np.zeros((nx_vox, nz_vox), dtype=np.int32)
        # Per-anchor cache of the last placement base. Occupancy only grows,
        # so the lowest free y in a column is monotonic: a new piece can nest
        # at most the piece's own height into the piece below. Scanning from
        # base_prev - max_height instead of 0 keeps the valley scan O(piece
        # height) instead of O(column depth) — the dominant cost for flat
        # parts stacked dozens of layers deep.
        base_cache = np.zeros((nx_vox, nz_vox), dtype=np.int32) if variants is None else {}
        placed, meshes = [], []
        t0 = time.time()

        if verbose:
            print(f"[Stacking] cell={cell_size}mm, orientation '{vd['name']}' "
                  f"footprint {vd['size'][0]:.0f}x{vd['size'][2]:.0f}, height {vd['size'][1]:.0f}",
                  flush=True)

        # Scan every voxel position (concave parts interleave in adjacent
        # columns). For each position, stack pieces with valley nesting until
        # no more fit, then move on.
        for gx in range(0, nx_vox - scan_sx + 1):
            if len(placed) >= max_pieces:
                break
            for gz in range(0, nz_vox - scan_sz + 1):
                if len(placed) >= max_pieces:
                    break
                cx, cz = gx + px, gz + pz
                while len(placed) < max_pieces:
                    # Rim height (top of the tallest column of the stack below)
                    rim = int((box_hm[cx, cz] - py).max())
                    if rim < 0:
                        rim = 0
                    if variants is not None:
                        if rim + max_sy > ny_vox:
                            break
                    elif rim + sy_v > ny_vox:
                        break
                    # Valley nesting: scan from the cached lower bound up to
                    # the rim and take the LOWEST collision-free position —
                    # pieces drop into the concave cavity of the piece below
                    # instead of resting on the rim. Cap at rim so we never
                    # float. Occupancy only grows, so the lowest free y for a
                    # GIVEN footprint is monotonic — but the cache must be
                    # per variant: rotated variants have slightly different
                    # footprints and can nest lower than the base pose's.
                    if variants is None:
                        scan_lo = int(base_cache[gx, gz])
                        base = None
                        for try_y in range(scan_lo, rim + 1):
                            wy = try_y + py
                            if not box_occ[cx, wy, cz].any():
                                base = try_y
                                break
                        if base is None:
                            break
                        v_sel = 0
                    else:
                        base_v = None
                        # A rotated variant must nest MEANINGFULLY lower to be
                        # worth the pattern disruption: at least 25% of the
                        # piece's voxel height (min 1 cell). Flat parts
                        # (thin pieces) benefit hugely from a 1-cell win;
                        # bulky parts would just get a noisier pattern.
                        gain_required = max(1, v_shape[0][1] // 4)
                        for vi in range(len(variants)):
                            if rim + v_shape[vi][1] > ny_vox:
                                continue
                            scan_lo = int(base_cache.get((gx, gz, vi), 0))
                            for try_y in range(scan_lo, rim + 1):
                                wy = try_y + v_py[vi]
                                if not box_occ[gx + v_px[vi], wy, gz + v_pz[vi]].any():
                                    if (vi == 0 and (base_v is None or try_y < base_v[0])) or (
                                        vi != 0 and (base_v is None
                                                     or try_y + gain_required <= base_v[0])):
                                        base_v = (try_y, vi)
                                    break
                        if base_v is None:
                            break
                        base, v_sel = base_v
                    if variants is None:
                        base_cache[gx, gz] = base
                    else:
                        base_cache[(gx, gz, v_sel)] = base
                    wy = base + (py if variants is None else v_py[v_sel])
                    cx_v = cx if variants is None else gx + v_px[v_sel]
                    cz_v = cz if variants is None else gz + v_pz[v_sel]
                    box_occ[cx_v, wy, cz_v] = 1
                    hm_v = vd['hm'] if variants is None else v_hm[v_sel]
                    sh_x = sx_v if variants is None else v_shape[v_sel][0]
                    sh_z = sz_v if variants is None else v_shape[v_sel][2]
                    box_hm[gx:gx + sh_x, gz:gz + sh_z] = np.maximum(
                        box_hm[gx:gx + sh_x, gz:gz + sh_z], base + hm_v)
                    x_mm = gx * cell_size
                    y_mm = base * cell_size
                    z_mm = gz * cell_size
                    oi_sel = best_oi if variants is None else v_oi[v_sel]
                    name_sel = vd['name'] if variants is None else v_name[v_sel]
                    cm = (vd['mesh'] if variants is None else v_mesh[v_sel]).copy()
                    cm.apply_translation([x_mm, y_mm, z_mm])
                    placed.append((x_mm, y_mm, z_mm, oi_sel, name_sel))
                    meshes.append(cm)
                    if progress_callback and len(placed) % 5 == 0:
                        progress_callback(len(placed), time.time() - t0, list(placed))
                    if verbose and len(placed) % 100 == 0:
                        fill = box_occ.sum() * cell_size**3 / (self.box_l * self.box_w * self.box_h) * 100
                        print(f"  {len(placed)} pieces, {fill:.1f}% fill, {time.time()-t0:.0f}s", flush=True)

        elapsed = time.time() - t0
        vol = sum(m.volume for m in meshes)
        fill = vol / (self.box_l * self.box_w * self.box_h) * 100
        if verbose:
            print(f"  [Stacking] DONE: {len(placed)} pieces, {fill:.1f}% fill, {elapsed:.0f}s", flush=True)
        return placed, meshes

    # ── Bounding-box grid (Graella / Compartment) ──

    def pack_bbox_grid(self, gap=0.0, verbose=True, progress_callback=None):
        """Exact axis-aligned bounding-box grid — the same math as the
        frontend's planar Graella: piece pitch = bounding box + gap, layers =
        floor(boxH / (bbH + gap)). Tries the pose as-is and its 90° in-plane
        swap. With gap 0 the boxes touch exactly; with the cardboard
        thickness as gap the cells match the divider pitch.

        Registers the two orientations (0° / 90°, mesh min-corner at origin)
        in self._sparrow_voxel_data so placement formatting and the final
        mesh rebuild work unchanged. Returns (placed, meshes) — the meshes
        are already positioned; callers must NOT re-run voxel refinement."""
        src = getattr(self, '_source_mesh', None)
        if src is None:
            if verbose:
                print("[Grid] No source mesh, falling back to greedy")
            return self.pack_greedy(5000, verbose)

        def _norm(mesh):
            b = mesh.bounds
            mesh.apply_translation(-b[0])
            return mesh

        m0 = _norm(src.copy())
        b0 = m0.bounds
        d0 = (b0[1][0] - b0[0][0], b0[1][1] - b0[0][1], b0[1][2] - b0[0][2])
        rot0 = np.eye(3)

        m90 = src.copy()
        tr = trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0],
                                                     src.bounds.mean(axis=0))
        m90.apply_transform(tr)
        m90 = _norm(m90)
        b90 = m90.bounds
        d90 = (b90[1][0] - b90[0][0], b90[1][1] - b90[0][1], b90[1][2] - b90[0][2])
        rot90 = trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0], [0, 0, 0])[:3, :3]

        candidates = [(m0, rot0, d0, 'Graella 0°'), (m90, rot90, d90, 'Graella 90°')]
        scored = []
        for mesh, rot, (pl, pw, ph), name in candidates:
            if pl > self.box_l + 0.01 or ph > self.box_h + 0.01 or pw > self.box_w + 0.01:
                continue
            nx = int((self.box_l - pl + 1e-6) // (pl + gap)) + 1
            nz = int((self.box_w - pw + 1e-6) // (pw + gap)) + 1
            ny = max(1, int(self.box_h // max(0.01, ph + gap)))
            scored.append((nx * nz * ny, nx, nz, ny, mesh, rot, name, pl, pw, ph))
        if not scored:
            if verbose:
                print("[Grid] Nothing fits, falling back to greedy")
            return self.pack_greedy(5000, verbose)

        scored.sort(key=lambda e: -e[0])
        _score, nx, nz, ny, mesh, rot, name, pl, pw, ph = scored[0]

        # Register the two grid orientations for the placement pipeline.
        grid_oris = [
            {'mesh': m0, 'rotation': rot0, 'name': 'Graella 0°', 'size': d0, 'shape': (1, 1, 1), 'sparse': None, 'hm': None},
            {'mesh': m90, 'rotation': rot90, 'name': 'Graella 90°', 'size': d90, 'shape': (1, 1, 1), 'sparse': None, 'hm': None},
        ]
        self._sparrow_voxel_data = grid_oris
        self._sparrow_cell_size = 1.0
        used_oi = 0 if (pl, pw, ph) == d0 else 1

        placed, meshes = [], []
        t0 = time.time()
        for k in range(ny):
            for j in range(nz):
                for i in range(nx):
                    x = i * (pl + gap)
                    y = k * (ph + gap)
                    z = j * (pw + gap)
                    cm = mesh.copy()
                    cm.apply_translation([x, y, z])
                    placed.append((round(x, 3), round(y, 3), round(z, 3), used_oi, name))
                    meshes.append(cm)
                    if progress_callback and len(placed) % 100 == 0:
                        progress_callback(len(placed), time.time() - t0, list(placed))
        self._compartment_cell = (pl + gap, pw + gap, ny, ph + gap)
        if verbose:
            print(f"  [Grid] DONE: {len(placed)} pieces ({nx}×{nz}×{ny}), gap={gap}mm, "
                  f"{time.time() - t0:.1f}s", flush=True)
        return placed, meshes

    # ── Compartment: one part per clean grid cell ──

    def pack_compartment(self, max_pieces=500, cell_size=None, verbose=True, progress_callback=None, gap=None):
        if cell_size is None:
            cell_size = 1.5
        # Inter-piece gap: contact (0) for the plain grid, the cardboard
        # thickness for compartment packing, or one voxel by default so the
        # voxel shells never touch.
        if gap is None:
            gap = cell_size
        oris = self._prepare_voxel_orients(cell_size, verbose)
        if oris is None:
            if verbose:
                print("[Compartment] No source/orientations, falling back to greedy")
            return self.pack_greedy(max_pieces, verbose)

        nx_vox = int(math.ceil(self.box_l / cell_size))
        ny_vox = int(math.ceil(self.box_h / cell_size))
        nz_vox = int(math.ceil(self.box_w / cell_size))

        best_oi = self._pick_compartment_ori(oris, self.box_l, self.box_h, self.box_w, cell_size, gap)
        if best_oi < 0:
            if verbose:
                print("[Compartment] No orientation fits the box, falling back to greedy")
            return self.pack_greedy(max_pieces, verbose)
        vd = oris[best_oi]
        sp = vd['sparse']
        sx_mm, sy_mm, sz_mm = vd['size']
        sx_v, sy_v, sz_v = vd['shape']
        px, py, pz = sp[:, 0], sp[:, 1], sp[:, 2]

        step_x = max(sx_v, int(round((sx_mm + gap) / cell_size)))
        step_z = max(sz_v, int(round((sz_mm + gap) / cell_size)))
        n_layers = max(1, int(self.box_h // max(0.01, sy_mm + gap)))
        if n_layers > 12:
            n_layers = 12  # practical cap: shelves get impractically thin above

        box_occ = np.zeros((nx_vox, ny_vox, nz_vox), dtype=np.uint8)
        box_hm = np.zeros((nx_vox, nz_vox), dtype=np.int32)
        placed, meshes = [], []
        t0 = time.time()

        if verbose:
            print(f"[Compartment] cell={cell_size}mm, gap={gap}mm, "
                  f"footprint {sx_mm:.0f}x{sz_mm:.0f}, height {sy_mm:.0f}, {n_layers} layer(s)",
                  flush=True)

        for gx in range(0, nx_vox - sx_v + 1, step_x):
            if len(placed) >= max_pieces:
                break
            for gz in range(0, nz_vox - sz_v + 1, step_z):
                if len(placed) >= max_pieces:
                    break
                for layer in range(n_layers):
                    if len(placed) >= max_pieces:
                        break
                    base = layer * sy_v
                    wy = base + py
                    cx, cz = gx + px, gz + pz
                    if box_occ[cx, wy, cz].any():
                        break
                    box_occ[cx, wy, cz] = 1
                    box_hm[gx:gx + sx_v, gz:gz + sz_v] = np.maximum(
                        box_hm[gx:gx + sx_v, gz:gz + sz_v], base + vd['hm'])
                    x_mm = gx * cell_size
                    y_mm = base * cell_size
                    z_mm = gz * cell_size
                    cm = vd['mesh'].copy()
                    cm.apply_translation([x_mm, y_mm, z_mm])
                    placed.append((x_mm, y_mm, z_mm, best_oi, vd['name']))
                    meshes.append(cm)
                    if progress_callback and len(placed) % 5 == 0:
                        progress_callback(len(placed), time.time() - t0, list(placed))
                    if verbose and len(placed) % 100 == 0:
                        fill = box_occ.sum() * cell_size**3 / (self.box_l * self.box_w * self.box_h) * 100
                        print(f"  {len(placed)} pieces, {fill:.1f}% fill, {time.time()-t0:.0f}s", flush=True)

        elapsed = time.time() - t0
        vol = sum(m.volume for m in meshes)
        fill = vol / (self.box_l * self.box_w * self.box_h) * 100
        # Record the cell grid (mm pitch + layers) so the frontend can render
        # the cardboard partition grid that compartment packing implies.
        self._compartment_cell = (step_x * cell_size, step_z * cell_size, n_layers, sy_v * cell_size)
        if verbose:
            print(f"  [Compartment] DONE: {len(placed)} pieces, {fill:.1f}% fill, {elapsed:.0f}s", flush=True)
        return placed, meshes

    # ── Spectral packing (FFT-based, Inkbit paper) ──

    def pack_spectral(self, max_pieces=500, cell_size=None, verbose=True,
                      progress_callback=None, seed=None, edt_every=10, phi_mode='manhattan'):
        """FFT-based spectral packing (Cui et al., ACM TOG 2023).

        For each orientation: one FFT correlation yields the collision metric
        (overlap count) at EVERY voxel offset, and another yields the proximity
        metric (fit tightness via distance transform). The best offset is the
        minimum of cost = proximity + height-penalty among collision-free
        offsets. Greedy placement of the (single) part type.

        edt_every: recompute the (expensive, single-threaded) 3D Euclidean
        distance transform of the free space only every `edt_every` placements
        and reuse it in between. The collision metric is still exact every
        iteration; only the soft proximity ranking uses a (few-placements-old)
        distance field, which is a mild perturbation of the greedy order.

        phi_mode: 'edt' uses scipy's exact Euclidean distance transform;
        'manhattan' uses the much cheaper L1 (taxicab) chamfer distance
        transform, recomputed fresh every iteration. The proximity field is a
        soft heuristic (the hard collision test is unchanged), so swapping the
        metric only perturbs the greedy ordering of equally-collision-free
        offsets.
        """
        from scipy import ndimage as _ndi
        from scipy.fft import rfftn as _rfftn, irfftn as _irfftn

        if seed is not None:
            random.seed(seed)
        source = getattr(self, '_source_mesh', None)
        if source is None:
            return self.pack_greedy(max_pieces, verbose)
        if cell_size is None:
            cell_size = 2.0

        oris = self._prepare_voxel_orients(cell_size, verbose=verbose)
        if not oris:
            return self.pack_greedy(max_pieces, verbose)

        nx_vox = max(2, int(math.ceil(self.box_l / cell_size)))
        ny_vox = max(2, int(math.ceil(self.box_h / cell_size)))
        nz_vox = max(2, int(math.ceil(self.box_w / cell_size)))

        # Padded grid for linear (non-circular) correlation. Only offsets
        # t in [0, nx-sx] etc. are ever read, which only needs b indices up
        # to nx-1 < PX, so PX == nx_vox already gives wrap-free exact results
        # for the whole valid region. We still round each axis up to a
        # FFT-friendly (7-smooth) size so pocketfft never falls back to the
        # slow prime (Bluestein) path (nx_vox=193 etc. are prime). The pad
        # region beyond the box stays zeroed and never wraps into the read
        # range, so results are identical to the previous 2*nx zero padding.
        def _smooth(n):
            while True:
                x = n
                for p in (2, 3, 5, 7):
                    while x % p == 0:
                        x //= p
                if x == 1:
                    return n
                n += 1
        PX, PY, PZ = _smooth(nx_vox), _smooth(ny_vox), _smooth(nz_vox)
        s_omega = np.zeros((PX, PY, PZ), dtype=np.float32)

        # Tray walls: mark the interior boundary as occupied so objects
        # cannot be placed sticking out of the tray.
        s_omega[0, :, :] = 1
        s_omega[nx_vox - 1, :, :] = 1
        s_omega[:, 0, :] = 1
        s_omega[:, ny_vox - 1, :] = 1
        s_omega[:, :, 0] = 1
        s_omega[:, :, nz_vox - 1] = 1

        # Precompute orientation voxel grids + their FFTs (constant across
        # placements). Limit to a handful of orientations — FFTs dominate cost.
        ori_info = []
        for oi, o in enumerate(oris):
            sx, sy, sz = o['shape']
            if sx > nx_vox - 2 or sy > ny_vox - 2 or sz > nz_vox - 2:
                continue
            sp = o['sparse']
            s_a = np.zeros((PX, PY, PZ), dtype=np.float32)
            s_a[sp[:, 0], sp[:, 1], sp[:, 2]] = 1
            f_a = _rfftn(s_a, axes=(0, 1, 2), workers=-1)
            ori_info.append((oi, o, (sx, sy, sz), f_a))
            if len(ori_info) >= 4:
                break
        if not ori_info:
            return self.pack_greedy(max_pieces, verbose)

        placed, meshes = [], []
        t0 = time.time()
        height_penalty_p = 0.05
        consecutive = 0
        axes = (0, 1, 2)
        shape = (PX, PY, PZ)

        while len(placed) < max_pieces and consecutive < 10:
            # FFT of occupancy (with walls + pieces) and of its distance transform
            f_omega = _rfftn(s_omega, axes=axes, workers=-1)
            if phi_mode == 'manhattan':
                # L1 (taxicab) chamfer distance of the free space — ~10x
                # cheaper than the Euclidean EDT and refreshed every iteration.
                phi = _ndi.distance_transform_cdt(s_omega == 0, metric='taxicab').astype(np.float32)
                f_phi = _rfftn(phi, axes=axes, workers=-1)
            elif (len(placed) % edt_every == 0) or consecutive > 0:
                phi = _ndi.distance_transform_edt(s_omega == 0).astype(np.float32)
                f_phi = _rfftn(phi, axes=axes, workers=-1)

            best_cost = float('inf')
            best = None  # (oi, qx, qy, qz)

            for oi, o, (sx, sy, sz), f_a in ori_info:
                # Collision metric: overlap count at every offset
                zeta = _irfftn(np.conj(f_a) * f_omega, s=shape, axes=axes, workers=-1)
                # Proximity metric: distance sum at every offset
                rho = _irfftn(np.conj(f_a) * f_phi, s=shape, axes=axes, workers=-1)

                max_x = nx_vox - sx
                max_y = ny_vox - sy
                max_z = nz_vox - sz
                if max_x <= 0 or max_y <= 0 or max_z <= 0:
                    continue

                zc = zeta[:max_x + 1, :max_y + 1, :max_z + 1]
                rc = rho[:max_x + 1, :max_y + 1, :max_z + 1]

                free = np.where(zc <= 0.5)
                if free[0].size == 0:
                    continue

                # Height penalty: discourage tall stacks (y = height axis)
                y_norm = free[1] / max(1.0, ny_vox)
                cost = rc[free] + height_penalty_p * (y_norm ** 3)

                k = int(np.argmin(cost))
                c = float(cost[k])
                if c < best_cost:
                    best_cost = c
                    best = (oi, int(free[0][k]), int(free[1][k]), int(free[2][k]))

            if best is None:
                consecutive += 1
                continue

            oi, qx, qy, qz = best
            od = oris[oi]
            sp = od['sparse']
            # Mark occupancy
            s_omega[qx + sp[:, 0], qy + sp[:, 1], qz + sp[:, 2]] = 1

            x_mm = qx * cell_size
            y_mm = qy * cell_size
            z_mm = qz * cell_size
            cm = od['mesh'].copy()
            cm.apply_translation([x_mm, y_mm, z_mm])
            meshes.append(cm)
            placed.append((x_mm, y_mm, z_mm, oi, od['name']))
            consecutive = 0

            if progress_callback and len(placed) % 5 == 0:
                progress_callback(len(placed), time.time() - t0, list(placed))
            if verbose and len(placed) % 25 == 0:
                fill = sum(m.volume for m in meshes) / (self.box_l * self.box_w * self.box_h) * 100
                print(f"  [Spectral] {len(placed)} pieces, {fill:.1f}% fill, {time.time()-t0:.0f}s", flush=True)

        elapsed = time.time() - t0
        vol = sum(m.volume for m in meshes)
        fill = vol / (self.box_l * self.box_w * self.box_h) * 100
        if verbose:
            print(f"  [Spectral] DONE: {len(placed)} pieces, {fill:.1f}% fill, {elapsed:.0f}s", flush=True)
        return placed, meshes

    # ── Full pipeline ──

    def pack(self, method='backtrack', max_beams=8, max_pieces=500, compact=False, verbose=True, beam_width=5, hierarchical=False, explore_local=False, sparrow_workers=4, voxel_cell=1.0, progress_callback=None, seed=None):
        t0 = time.time()

        if method == 'sparrow':
            placed, meshes = self.pack_sparrow(max_pieces, n_workers=sparrow_workers, n_iterations=max_pieces * 40, cell_size=voxel_cell, verbose=verbose, progress_callback=progress_callback, seed=seed)
        elif method == 'spectral':
            placed, meshes = self.pack_spectral(max_pieces, cell_size=voxel_cell, verbose=verbose, progress_callback=progress_callback, seed=seed)
        elif method == 'stacking':
            placed, meshes = self.pack_stacking(max_pieces, cell_size=voxel_cell, verbose=verbose, progress_callback=progress_callback)
        elif method == 'compartment':
            placed, meshes = self.pack_compartment(max_pieces, cell_size=voxel_cell, verbose=verbose, progress_callback=progress_callback)
        elif method == 'greedy':
            placed, meshes = self.pack_greedy(max_pieces, verbose, beam_width=beam_width, hierarchical=hierarchical, explore_local=explore_local)
        elif method == 'layers':
            placed, meshes = self.pack_layers(max_pieces, verbose)
        else:
            placed, meshes = self.pack_backtrack(max_pieces, backtrack_depth=8, n_attempts=30, verbose=verbose)

        if compact and len(placed) > 0:
            placed, meshes = self.compact(placed, meshes, verbose=verbose)

        elapsed = time.time() - t0
        if verbose and placed:
            vol = sum(m.volume for m in meshes)
            fill = vol / (self.box_l * self.box_w * self.box_h) * 100
            print(f"\nTotal: {len(placed)} pieces, {fill:.1f}% fill, {elapsed:.0f}s", flush=True)
        return placed, meshes


# ═══════════════════════════════════════════════
# Verification + visualization
# ═══════════════════════════════════════════════

def _column_extents(sp, offset, axis):
    """Per-column extents of a piece's voxels in GLOBAL float coordinates.

    sp: local sparse voxel indices (N,3); offset: (ox, oy, oz) float voxel
    offset of the piece's origin; axis: 0/1/2 = the slide axis. Returns a
    dict mapping the OTHER two global coords (floats) -> (min, max) extent
    along the axis. Used for exact pure-translation collision limits.
    """
    g = sp.astype(np.float64) + np.asarray(offset, dtype=np.float64)
    o1, o2 = [k for k in range(3) if k != axis]
    col = g[:, o1] * 10000.0 + g[:, o2]
    order = np.argsort(col, kind='stable')
    ks = col[order]
    vs = g[order, axis]
    starts = np.r_[0, np.flatnonzero(ks[1:] != ks[:-1]) + 1]
    cols = ks[starts]
    mins = np.minimum.reduceat(vs, starts)
    maxs = np.maximum.reduceat(vs, starts)
    return dict(zip(cols, zip(mins, maxs)))


def _inplane_rotated_variant(vd, angle_deg, cell_size):
    """Rotate a voxel orientation's sparse shell by `angle_deg` around the
    vertical (Y) axis and re-discretize onto the same voxel grid.

    Cheap alternative to re-voxelizing a rotated mesh — accurate enough for
    small angles (±1-2°) where the rotated shape shifts by a voxel or two.
    Returns a new orientation dict (sparse/shape/hm/size/mesh/name/rotation)
    compatible with the packing pipeline, or None on degenerate input.
    """
    sp = vd.get('sparse')
    if sp is None or len(sp) < 3:
        return None
    th = math.radians(angle_deg)
    c, s = math.cos(th), math.sin(th)
    cx = (sp[:, 0].min() + sp[:, 0].max()) / 2.0
    cz = (sp[:, 2].min() + sp[:, 2].max()) / 2.0
    dx = sp[:, 0].astype(np.float64) - cx
    dz = sp[:, 2].astype(np.float64) - cz
    rx = c * dx - s * dz + cx
    rz = s * dx + c * dz + cz
    new = np.stack([np.rint(rx).astype(np.int32), sp[:, 1],
                    np.rint(rz).astype(np.int32)], axis=1)
    new -= new.min(axis=0)
    new = np.unique(new, axis=0)
    shape = tuple(int(v) + 1 for v in new.max(axis=0))
    hm = np.zeros((shape[0], shape[2]), dtype=np.int32)
    hm[new[:, 0], new[:, 2]] = np.maximum(hm[new[:, 0], new[:, 2]], new[:, 1])

    mesh = None
    if vd.get('mesh') is not None:
        mesh = vd['mesh'].copy()
        b = mesh.bounds
        mx = (b[0][0] + b[1][0]) / 2.0
        mz = (b[0][2] + b[1][2]) / 2.0
        rot = trimesh.transformations.rotation_matrix(th, [0, 1, 0], [mx, 0, mz])
        mesh.apply_transform(rot)

    rotation = None
    if vd.get('rotation') is not None:
        rv = trimesh.transformations.rotation_matrix(th, [0, 1, 0], [0, 0, 0])[:3, :3]
        rotation = (rv @ np.asarray(vd['rotation'])).tolist()

    return {
        'mesh': mesh,
        'size': tuple(float(v) * cell_size for v in shape),
        'name': f"{vd.get('name', 'variant')}{angle_deg:+.0f}d",
        'sparse': new,
        'n_occ': int(len(new)),
        'hm': hm,
        'shape': shape,
        'rotation': rotation,
    }


def refine_subvoxel(placed, oris, cell_size, n_rounds=3, verbose=False):
    """Tighten voxel placements at sub-voxel precision.

    Each piece is slid toward the box origin (-x, -z) and dropped down (-y)
    by the exact amount that keeps it collision-free against every other
    piece (pure-translation column test: a piece may move until its low end
    touches the highest opposing voxel in a shared column). Moves are capped
    at half a voxel so pieces stay anchored to their grid slot (the whole
    point is sub-voxel refinement, not re-packing). Pieces are processed in
    reverse placement order (top of each stack first) and the x/z/y pass is
    repeated `n_rounds` times so pieces can nest into valleys opened up by
    earlier drops.

    Returns a NEW placed list (x_mm, y_mm, z_mm, oi, name) with refined
    continuous coordinates. Callers must rebuild meshes from the new
    positions. Works on the 'sparse' voxel data (voxel methods only).
    """
    n = len(placed)
    if n < 2:
        return list(placed)

    # Large packings: refinement is O(n²) per round and the FCL safety pass
    # builds a collision manager over every mesh. Beyond these sizes the
    # sub-voxel tightening isn't worth the wait — the grid placements are
    # already collision-free, just not fully tightened.
    if n > 1000:
        return list(placed)
    if n > 600:
        n_rounds = 1
    max_cell = float(cell_size)
    half = 0.5 * max_cell
    bbox = [None] * n  # global (xmin, xmax, ymin, ymax, zmin, zmax)
    offsets = [None] * n  # float voxel offsets (ox, oy, oz)
    exts = [None] * n    # [x-col map, y-col map, z-col map]

    for i, (x_mm, y_mm, z_mm, oi, _name) in enumerate(placed):
        sp = oris[oi]['sparse']
        off = np.array([x_mm, y_mm, z_mm], dtype=np.float64) / max_cell
        offsets[i] = off
        exts[i] = [_column_extents(sp, off, 0), _column_extents(sp, off, 1),
                   _column_extents(sp, off, 2)]
        gmin = sp.min(axis=0).astype(np.float64) + off
        gmax = sp.max(axis=0).astype(np.float64) + off
        bbox[i] = (gmin[0], gmax[0], gmin[1], gmax[1], gmin[2], gmax[2])

    def slide_allowed(i, axis):
        """Max move of piece i along `axis` toward the box origin (voxel
        units) before touching any other piece, capped at half a voxel from
        the original anchor. Exact for pure translation."""
        o1, o2 = [k for k in range(3) if k != axis]
        b = bbox[i]
        lim = b[axis] if axis == 0 else (b[2] if axis == 1 else b[4])
        cur = exts[i][axis]
        best = lim
        for j in range(n):
            if j == i:
                continue
            bj = bbox[j]
            # column overlap requires overlap in the two non-axis dims
            if bj[2 * o1] > b[2 * o1 + 1] or b[2 * o1] > bj[2 * o1 + 1]:
                continue
            if bj[2 * o2] > b[2 * o2 + 1] or b[2 * o2] > bj[2 * o2 + 1]:
                continue
            ej = exts[j][axis]
            # iterate the smaller map
            if len(cur) <= len(ej):
                sm, lg = cur, ej
            else:
                sm, lg = ej, cur
            for k, (lo, hi) in sm.items():
                v = lg.get(k)
                if v is None:
                    continue
                d = lo - v[1]  # move until i's low end touches j's high end
                if d < best:
                    best = d
                    if best <= 0:
                        return 0.0
        return max(0.0, best)

    def apply_move(i, axis, delta):
        """Shift piece i by `delta` voxels toward the box origin along
        `axis`; update all state."""
        off = offsets[i]
        b = bbox[i]
        b = list(b)
        b[2 * axis] -= delta
        b[2 * axis + 1] -= delta
        bbox[i] = tuple(b)
        sp = oris[placed[i][3]]['sparse']
        off = list(off)
        off[axis] -= delta
        offsets[i] = off
        exts[i] = [_column_extents(sp, off, 0), _column_extents(sp, off, 1),
                   _column_extents(sp, off, 2)]

    # Cap moves to half a voxel from the ORIGINAL anchor so the piece stays
    # in its grid slot. Anchors are the starting offsets.
    def anchor_lim(i, axis):
        base = placed[i][axis] / max_cell
        return offsets[i][axis] - base + half  # may move down to base - half

    for _round in range(n_rounds):
        moved_any = 0.0
        for i in range(n - 1, -1, -1):  # top of stack first
            for axis in (0, 2, 1):      # x, z, then y (drop last)
                d = slide_allowed(i, axis)
                d = min(d, anchor_lim(i, axis))
                if d > 1e-6:
                    apply_move(i, axis, d)
                    moved_any += d
        if verbose:
            print(f"  [Refine] round {_round + 1}: {moved_any:.2f} voxels moved")
        if moved_any < 1e-4:
            break

    refined = []
    for i, (x_mm, y_mm, z_mm, oi, name) in enumerate(placed):
        ox, oy, oz = offsets[i]
        refined.append((ox * max_cell, oy * max_cell, oz * max_cell, oi, name))

    # Mesh-level safety: the voxel shells carry an overhang vs the real
    # meshes, so voxel-touching can still overlap surfaces. Scale ALL moves
    # down until the refined meshes are collision-free (monotone: k=0 gives
    # the original collision-free packing). FCL is the same oracle the
    # server's verify() uses.
    moves = [tuple(refined[i][a] - placed[i][a] for a in range(3))
             for i in range(n)]
    if _FCL_AVAILABLE and n <= 800 and any(any(abs(m) > 1e-9 for m in mv) for mv in moves):
        has_mesh = all('mesh' in oris[placed[i][3]] for i in range(n))
        if has_mesh:
            def _colliding(k):
                try:
                    from trimesh.collision import CollisionManager
                except Exception:
                    return True
                cm = CollisionManager()
                for i in range(n):
                    mi = oris[placed[i][3]]['mesh'].copy()
                    mi.apply_translation([placed[i][0] + k * moves[i][0],
                                          placed[i][1] + k * moves[i][1],
                                          placed[i][2] + k * moves[i][2]])
                    cm.add_object(f'p{i}', mi)
                try:
                    names, _ = cm.in_collision_internal(return_names=True, return_data=False)
                    return bool(names)
                except Exception:
                    return True

            k = 1.0
            while k > 0.05 and _colliding(k):
                k *= 0.5
            if k < 1.0:
                refined = [tuple(placed[i][a] + k * moves[i][a] for a in range(3))
                           + (placed[i][3], placed[i][4]) for i in range(n)]
    return refined


def descent_stack_contact(placed, oris, max_drop=3.0, n_max=1200, verbose=False):
    """Drop each piece straight down onto the pieces below it until EXACT
    mesh contact (FCL), closing the residual voxel-shell gaps so stacked
    pieces visually touch. Pieces are processed top-down; each piece only
    moves downward and only until the first contact, so the result stays
    collision-free by construction.

    Uses a spatial hash over the XZ plane so each piece only tests the
    pieces in its neighbourhood instead of the whole packing.

    Returns a NEW placed list with refined y positions. Callers must rebuild
    meshes from the returned positions.
    """
    n = len(placed)
    if n < 2 or n > n_max:
        return placed

    if not _FCL_AVAILABLE:
        return placed
    try:
        from trimesh.collision import CollisionManager
    except Exception:
        return placed

    meshes = []
    bounds = []
    for (x, y, z, oi, _name) in placed:
        m = oris[oi]['mesh'].copy()
        m.apply_translation([x, y, z])
        meshes.append(m)
        bounds.append(m.bounds)

    fx = float(np.median([(b[1][0] - b[0][0]) for b in bounds])) or 10.0
    fz = float(np.median([(b[1][2] - b[0][2]) for b in bounds])) or 10.0
    buckets = {}
    for i, b in enumerate(bounds):
        key = (int((b[0][0] + b[1][0]) / 2.0 // fx), int((b[0][2] + b[1][2]) / 2.0 // fz))
        buckets.setdefault(key, []).append(i)

    out = [list(p) for p in placed]
    t0 = time.time()
    moved = 0

    for key, members in buckets.items():
        cand_all = []
        seen = set()
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for j in buckets.get((key[0] + dx, key[1] + dz), ()):
                    if j not in seen:
                        seen.add(j)
                        cand_all.append(j)
        members_sorted = sorted(members, key=lambda i: -out[i][1])
        for i in members_sorted:
            pi = out[i]
            b = bounds[i]
            cands = [j for j in cand_all
                     if j != i and out[j][1] < pi[1] - 1e-6
                     and bounds[j][0][0] < b[1][0] and b[0][0] < bounds[j][1][0]
                     and bounds[j][0][2] < b[1][2] and b[0][2] < bounds[j][1][2]]
            if not cands:
                continue
            # The contact is decided by the highest pieces below — keep the
            # top 30 by y (exact: any piece lower than the 30th can only be
            # reached after hitting one of these). Massively cheaper FCL.
            if len(cands) > 30:
                cands = sorted(cands, key=lambda j: -out[j][1])[:30]
            # Already resting on the highest candidate → skip the probes.
            support_top = max(bounds[j][1][1] for j in cands)
            if support_top + 0.06 >= b[0][1]:
                continue
            cm = CollisionManager()
            for j in cands:
                cm.add_object(f'p{j}', meshes[j])
            piece = oris[placed[i][3]]['mesh'].copy()
            lo, hi = 0.0, min(max_drop, pi[1])
            for _ in range(6):
                mid = (lo + hi) / 2.0
                pm = piece.copy()
                pm.apply_translation([pi[0], pi[1] - mid, pi[2]])
                try:
                    hits = cm.in_collision_single(pm, return_names=False)
                except Exception:
                    hits = True
                if hits:
                    lo = mid
                else:
                    hi = mid
            drop = max(0.0, hi - 0.02)
            if drop > 0.03:
                out[i][1] = pi[1] - drop
                nm = meshes[i].copy()
                nm.apply_translation([0, -drop, 0])
                meshes[i] = nm
                bounds[i] = nm.bounds
                moved += 1

    if verbose:
        print(f"  [Contact] {moved}/{n} pieces tightened, {time.time()-t0:.1f}s", flush=True)
    return [tuple(p) for p in out]


def detect_interlocking(placed, oris, cell_size):
    """Detect pieces that cannot be removed from the box by lifting straight
    up (vertical interlock).

    A piece is removable iff no other piece occupies any voxel above it in a
    shared (x,z) column — the straight-up lift is collision-free. Pieces are
    removed greedily in any order (top of a stack comes out first, then the
    piece below becomes removable). Whatever is left at the end is truly
    interlocked: it is trapped by neighbours above it in every possible
    removal sequence.

    `placed` is the (x_mm, y_mm, z_mm, oi, name) list; `oris` the orientation
    list with 'sparse' local voxel indices; `cell_size` the voxel pitch.
    Returns a sorted list of placement indices that are interlocked.
    """
    n = len(placed)
    if n < 2:
        return []

    # Per-piece column extents: (x,z) -> (min_y, max_y) in global voxel coords
    cols = []
    bboxes = []
    for (x_mm, y_mm, z_mm, oi, _name) in placed:
        sp = oris[oi]['sparse']
        ox = int(round(x_mm / cell_size))
        oy = int(round(y_mm / cell_size))
        oz = int(round(z_mm / cell_size))
        g = sp + np.array([ox, oy, oz], dtype=np.int32)
        bboxes.append((int(g[:, 0].min()), int(g[:, 0].max()),
                       int(g[:, 1].min()), int(g[:, 1].max()),
                       int(g[:, 2].min()), int(g[:, 2].max())))
        cmap = {}
        for p in g:
            k = (int(p[0]), int(p[2]))
            if k in cmap:
                lo, hi = cmap[k]
                if p[1] < lo: lo = int(p[1])
                if p[1] > hi: hi = int(p[1])
                cmap[k] = (lo, hi)
            else:
                cmap[k] = (int(p[1]), int(p[1]))
        cols.append(cmap)

    # blockers[i] = set of pieces j that have a voxel above some voxel of i
    # in a shared column -> j blocks i's straight-up lift.
    blockers = [set() for _ in range(n)]
    for i in range(n):
        x0i, x1i, _y0i, _y1i, z0i, z1i = bboxes[i]
        ci = cols[i]
        for j in range(i + 1, n):
            x0j, x1j, _y0j, _y1j, z0j, z1j = bboxes[j]
            # no shared (x,z) column -> no possible interaction
            if x1i < x0j or x1j < x0i or z1i < z0j or z1j < z0i:
                continue
            cj = cols[j]
            # iterate the smaller map; keep track of which map is which
            if len(ci) <= len(cj):
                sm, sm_is_i = ci, True
                lg = cj
            else:
                sm, sm_is_i = cj, False
                lg = ci
            block_i = block_j = False
            for k, (lo, hi) in sm.items():
                v = lg.get(k)
                if v is None:
                    continue
                # in this shared (x,z) column, sm spans [lo, hi],
                # lg spans [v[0], v[1]]
                if sm_is_i:
                    # j above i in this column -> j blocks i's lift
                    if v[1] > lo and not block_i:
                        block_i = True
                    # i above j -> i blocks j's lift
                    if hi > v[0] and not block_j:
                        block_j = True
                else:
                    # i above j in this column -> i blocks j's lift
                    if v[1] > lo and not block_j:
                        block_j = True
                    # j above i -> j blocks i's lift
                    if hi > v[0] and not block_i:
                        block_i = True
                if block_i and block_j:
                    break
            if block_i:
                blockers[i].add(j)
            if block_j:
                blockers[j].add(i)

    # Greedy removal: repeatedly lift out every piece with no remaining blocker.
    remaining = set(range(n))
    changed = True
    while changed:
        changed = False
        for i in sorted(remaining):
            if not (blockers[i] & remaining):
                remaining.discard(i)
                changed = True
    return sorted(remaining)


def verify(placed_meshes):
    collisions = 0
    for i in range(len(placed_meshes)):
        for j in range(i + 1, len(placed_meshes)):
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


def visualize(placed_meshes, box_dims, output_prefix="packed"):
    """Generate multiple visualization PNGs."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from mpl_toolkits.mplot3d import Axes3D
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    box_l, box_w, box_h = box_dims
    colors = plt.cm.tab20(np.linspace(0, 1, max(20, len(placed_meshes))))
    n = len(placed_meshes)

    # ── 1. 2x2 grid: top/front/side/heatmap ──
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    fig.suptitle(f"Packing — {n} pieces  |  Box {box_l:.0f}x{box_w:.0f}x{box_h:.0f}mm",
                 fontsize=14, fontweight='bold')
    for title, ax, view in [("Top (XZ)", axes[0, 0], 'xz'), ("Front (XY)", axes[0, 1], 'xy'),
                            ("Side (ZY)", axes[1, 0], 'zy'), ("Height Map", axes[1, 1], 'hm')]:
        ax.set_title(title)
        if view == 'xz':
            ax.set_xlim(0, box_l); ax.set_ylim(0, box_w); ax.invert_yaxis()
            for i, m in enumerate(placed_meshes):
                b = m.bounds
                ax.add_patch(Rectangle((b[0, 0], b[0, 2]), b[1, 0] - b[0, 0], b[1, 2] - b[0, 2],
                                       alpha=0.15, color=colors[i % 20], ec='black', lw=0.2))
            ax.set_xlabel('X mm'); ax.set_ylabel('Z mm'); ax.set_aspect('equal')
        elif view == 'xy':
            ax.set_xlim(0, box_l); ax.set_ylim(0, box_h)
            for m in placed_meshes:
                b = m.bounds
                ax.add_patch(Rectangle((b[0, 0], b[0, 1]), b[1, 0] - b[0, 0], b[1, 1] - b[0, 1],
                                       alpha=0.15, color=colors[0], ec='black', lw=0.2))
            ax.set_xlabel('X mm'); ax.set_ylabel('Y mm'); ax.set_aspect('equal')
        elif view == 'zy':
            ax.set_xlim(0, box_w); ax.set_ylim(0, box_h)
            for m in placed_meshes:
                b = m.bounds
                ax.add_patch(Rectangle((b[0, 2], b[0, 1]), b[1, 2] - b[0, 2], b[1, 1] - b[0, 1],
                                       alpha=0.15, color=colors[0], ec='black', lw=0.2))
            ax.set_xlabel('Z mm'); ax.set_ylabel('Y mm'); ax.set_aspect('equal')
        elif view == 'hm':
            hm = np.zeros((int(box_l // 5) + 1, int(box_w // 5) + 1)); cnt = np.zeros_like(hm)
            for m in placed_meshes:
                b = m.bounds
                ix, iz = int(b[0, 0] / 5), int(b[0, 2] / 5)
                if 0 <= ix < hm.shape[0] and 0 <= iz < hm.shape[1]:
                    hm[ix, iz] += b[1, 1]; cnt[ix, iz] += 1
            mask = cnt > 0
            if mask.any(): hm[mask] /= cnt[mask]
            im = ax.imshow(hm.T, origin='lower', cmap='YlOrRd', extent=[0, box_l, 0, box_w], aspect='equal')
            plt.colorbar(im, ax=ax, label='Max height mm')
            ax.set_xlabel('X mm'); ax.set_ylabel('Z mm')
    plt.tight_layout()
    f2d = f"{output_prefix}_2d.png"
    plt.savefig(f2d, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[Viz] {f2d}")

    # ── 2. 3D view with mesh faces ──
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection='3d')
    ax.set_title(f"3D View — {n} pieces", fontsize=14, fontweight='bold')

    # Draw box
    corners = np.array([[0, 0, 0], [box_l, 0, 0], [box_l, box_h, 0], [0, box_h, 0],
                        [0, 0, box_w], [box_l, 0, box_w], [box_l, box_h, box_w], [0, box_h, box_w]])
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
             (0, 4), (1, 5), (2, 6), (3, 7)]
    for e in edges:
        ax.plot3D(*zip(corners[e[0]], corners[e[1]]), color='gray', alpha=0.5, lw=0.5)

    # Render each piece as semi-transparent mesh faces (downsampled for performance)
    for i, m in enumerate(placed_meshes):
        color_rgba = list(colors[i % 20][:3]) + [0.25]
        if m.faces is not None and len(m.faces) > 0:
            face_idx = np.arange(len(m.faces))
            if len(face_idx) > 500:
                face_idx = np.random.choice(face_idx, 500, replace=False)
            polys = Poly3DCollection(m.vertices[m.faces[face_idx]], alpha=0.2,
                                     facecolor=colors[i % 20], edgecolor='none', linewidth=0)
            ax.add_collection3d(polys)
        else:
            v = m.vertices
            if len(v) > 200:
                v = v[np.random.choice(len(v), 200, replace=False)]
            ax.scatter(v[:, 0], v[:, 1], v[:, 2], s=1, color=colors[i % 20], alpha=0.5)

    ax.set_xlabel('X mm'); ax.set_ylabel('Y mm'); ax.set_zlabel('Z mm')
    ax.set_xlim(0, box_l); ax.set_ylim(0, box_h); ax.set_zlim(0, box_w)
    ax.view_init(elev=20, azim=-60)
    f3d = f"{output_prefix}_3d.png"
    plt.tight_layout()
    plt.savefig(f3d, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[Viz] {f3d}")

    # ── 3. Layer-by-layer breakdown ──
    if n > 5:
        layers = {}
        for i, m in enumerate(placed_meshes):
            layer = int(m.bounds[0, 1] // 20)  # group by 20mm Y bands
            layers.setdefault(layer, []).append(i)

        n_layers = len(layers)
        if n_layers > 1:
            cols = min(4, n_layers)
            rows = (n_layers + cols - 1) // cols
            fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 3 * rows))
            if rows == 1 and cols == 1:
                axes = np.array([[axes]])
            elif rows == 1:
                axes = axes.reshape(1, -1)
            elif cols == 1:
                axes = axes.reshape(-1, 1)

            fig.suptitle(f"Layer Breakdown — {n} pieces in {n_layers} layers", fontsize=13, fontweight='bold')
            for li, (layer_y, idxs) in enumerate(sorted(layers.items())):
                r, c = li // cols, li % cols
                ax = axes[r, c] if rows > 1 or cols > 1 else axes[0, 0] if axes.ndim == 1 else axes[r][c]
                ax.set_xlim(0, box_l); ax.set_ylim(0, box_w); ax.invert_yaxis()
                ax.set_title(f"Y band {layer_y*20}-{(layer_y+1)*20}mm ({len(idxs)} pcs)")
                for i in idxs:
                    b = placed_meshes[i].bounds
                    ax.add_patch(Rectangle((b[0, 0], b[0, 2]), b[1, 0] - b[0, 0], b[1, 2] - b[0, 2],
                                           alpha=0.2, color=colors[i % 20], ec='black', lw=0.1))
                ax.set_aspect('equal')
            # Hide unused subplots
            for li in range(n_layers, rows * cols):
                r, c = li // cols, li % cols
                ax = axes[r, c] if rows > 1 or cols > 1 else axes[0] if axes.ndim == 1 else axes[r][c]
                ax.axis('off')
            plt.tight_layout()
            flayer = f"{output_prefix}_layers.png"
            plt.savefig(flayer, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"[Viz] {flayer}")


# ═══════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="Best 3D Bin Packer")
    p.add_argument("stl", nargs="?", default=None)
    p.add_argument("box_l", nargs="?", type=float, default=385)
    p.add_argument("box_w", nargs="?", type=float, default=285)
    p.add_argument("box_h", nargs="?", type=float, default=150)
    p.add_argument("scan", nargs="?", type=float, default=5.0)
    p.add_argument("--yaw", type=int, default=8)
    p.add_argument("--yres", type=float, default=2.0)
    p.add_argument("--shrink", type=float, default=0.4, help="Hull shrink factor (0.4=aggressive, 1.0=full hull)")
    p.add_argument("--method", type=str, default="backtrack", choices=["greedy", "backtrack", "layers", "sparrow", "stacking", "compartment", "spectral"])
    p.add_argument("--compact", action="store_true")
    p.add_argument("--beam-width", type=int, default=5, help="Top-K candidates for random selection (1=lowest-Y, 5=explore)")
    p.add_argument("--hierarchical", action="store_true", help="Coarse-to-fine candidate search")
    p.add_argument("--coarse-step", type=float, default=10.0, help="Coarse grid step (mm)")
    p.add_argument("--fine-step", type=float, default=2.0, help="Fine refinement step (mm)")
    p.add_argument("--coarse-top", type=int, default=40, help="Max global candidates to keep from coarse pass")
    p.add_argument("--coarse-per-orientation", type=int, default=8, help="Max candidates per orientation")
    p.add_argument("--coarse-min-distance", type=float, default=15.0, help="Min XZ distance between kept candidates (mm)")
    p.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    p.add_argument("--export-stl", action="store_true", help="Export merged STL of all placed pieces")
    p.add_argument("--explore-local", action="store_true", help="Local perturbation search around each placement (sparrow-style)")
    p.add_argument("--sparrow-workers", type=int, default=1, help="Parallel attempts per batch (higher = more robust but slower)")
    p.add_argument("--voxel-cell", type=float, default=1.5, help="Voxel cell size in mm for sparrow collision grid (1.0=higher precision, 2.0=faster)")
    p.add_argument("--output", type=str, default="packed_best.png")
    args = p.parse_args()

    box_dims = (args.box_l, args.box_w, args.box_h)

    if not cuda.is_available():
        print("ERROR: CUDA not available."); sys.exit(1)

    packer = BestPacker(box_dims, scan_step=args.scan, y_scan_res=args.yres)

    if args.stl:
        fp = Path(args.stl)
        if not fp.exists():
            print(f"ERROR: {fp}"); sys.exit(1)
        print(f"Loading: {fp.name}...", flush=True)
        packer.load_mesh(str(fp), n_yaw=args.yaw, shrink=args.shrink)
    else:
        v = np.array([[0, 0, 20], [0, 0, 0], [0, -20, 0], [0, -20, 20], [40, 0, 0], [40, -20, 0]], dtype=np.float64)
        f = np.array([[0, 1, 2], [0, 2, 3], [4, 0, 5], [5, 0, 3], [1, 4, 2], [2, 4, 5], [4, 1, 0], [2, 5, 3]], dtype=np.int32)
        mesh = trimesh.Trimesh(vertices=v, faces=f)
        box_dims = (200, 200, 150)
        packer.box_l, packer.box_w, packer.box_h = box_dims
        packer.box_dims = box_dims
        packer.orientations = generate_orientations(mesh, args.yaw, box_dims)
        packer._max_v = max(o['hull'].vertex_count for o in packer.orientations)
        packer._max_f = max(o['hull'].face_count for o in packer.orientations)
        packer._init_gpu_buffers()
        print("Built-in triangle")

    if args.seed is not None:
        random.seed(args.seed)
        packer._rng = np.random.RandomState(args.seed)

    # Configure hierarchical search
    packer.coarse_step = args.coarse_step
    packer.fine_step = args.fine_step
    packer.coarse_top = args.coarse_top
    packer.coarse_per_orientation = args.coarse_per_orientation
    packer.coarse_min_distance = args.coarse_min_distance

    # Create timestamped output directory
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_name = f"{ts}_{args.method}"
    if args.hierarchical:
        run_name += f"_hier{args.coarse_step:.0f}-{args.fine_step:.0f}"
    if args.beam_width != 5:
        run_name += f"_beam{args.beam_width}"
    if args.compact:
        run_name += "_compact"
    out_dir = Path(__file__).resolve().parent.parent / "output" / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_prefix = str(out_dir / "packed")

    print(f"\nPacking ({args.method})...", flush=True)
    t_start = time.time()
    placed, meshes = packer.pack(method=args.method, max_pieces=500, compact=args.compact, verbose=True, beam_width=args.beam_width, hierarchical=args.hierarchical, explore_local=args.explore_local, sparrow_workers=args.sparrow_workers, voxel_cell=args.voxel_cell)
    elapsed = time.time() - t_start

    if meshes:
        print("\nVerifying...")
        verify(meshes)
        print("\nVisualizing...")
        visualize(meshes, box_dims, out_prefix)
        if args.export_stl or args.output.endswith('.stl'):
            merged = trimesh.util.concatenate(meshes)
            stl_path = str(out_dir / "merged.stl")
            merged.export(stl_path)
            print(f"[STL] {stl_path} ({len(merged.vertices):,} verts, {len(merged.faces):,} faces)")

        # Write run info
        info = [
            f"Run: {run_name}",
            f"Date: {datetime.now().isoformat()}",
            f"STL: {args.stl}",
            f"Box: {args.box_l}x{args.box_w}x{args.box_h}mm",
            f"Method: {args.method}",
            f"Scan step: {args.scan}mm, Y-res: {args.yres}mm",
            f"Yaw: {args.yaw}, Shrink: {args.shrink}",
            f"Beam width: {args.beam_width}",
            f"Hierarchical: {args.hierarchical}",
            f"  Coarse step: {args.coarse_step}, Fine step: {args.fine_step}",
            f"  Top: {args.coarse_top}, Per orient: {args.coarse_per_orientation}, Min dist: {args.coarse_min_distance}",
            f"Explore local: {args.explore_local}",
            f"Compact: {args.compact}",
            f"Sparrow workers: {args.sparrow_workers if args.method == 'sparrow' else 'N/A'}",
            f"Voxel cell: {args.voxel_cell if args.method in ('sparrow', 'stacking', 'compartment') else 'N/A'}mm",
            f"Seed: {args.seed}",
            f"",
            f"Result: {len(placed)} pieces, {sum(m.volume for m in meshes)/(box_dims[0]*box_dims[1]*box_dims[2])*100:.1f}% fill",
            f"Time: {elapsed:.0f}s",
        ]
        (out_dir / "info.txt").write_text("\n".join(info))
        print(f"[Info] {out_dir}/info.txt")
if __name__ == "__main__":
    main()
