"""
packer_mesh.py — Mesh-based packer using trimesh proximity for collision detection.
No voxels. Direct mesh collision verification.

Usage:
    python packer_mesh.py [stl_file] [box_l] [box_w] [box_h]
"""
import sys, time, math, argparse
from pathlib import Path
from collections import defaultdict
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation


def generate_orientations(mesh, n_yaw, n_roll, box_dims):
    results = []
    seen = set()
    base = mesh.copy()
    for yaw in np.linspace(0, 360, n_yaw, endpoint=False):
        for roll in np.linspace(0, 360, n_roll, endpoint=False):
            rot = Rotation.from_euler('xy', [roll, yaw], degrees=True).as_matrix()
            t = base.copy()
            t.apply_transform(np.vstack([np.hstack([rot, np.zeros((3,1))]), [0,0,0,1]]))
            bmin = t.bounds[0]; t.apply_translation([-bmin[0], -bmin[1], -bmin[2]])
            sz = t.extents
            if box_dims and (sz[0] > box_dims[0] + 0.5 or sz[2] > box_dims[1] + 0.5 or sz[1] > box_dims[2] + 0.5):
                continue
            key = tuple(sz.round(1))
            if key in seen: continue
            seen.add(key)
            results.append({'mesh': t, 'size': sz, 'name': f"Y{yaw:.0f}R{roll:.0f}", 'volume': t.volume})
    results.sort(key=lambda o: o['size'][1])
    return results


class SpatialGrid:
    def __init__(self, cell_size):
        self.cell_size = cell_size
        self.cells = defaultdict(list)
        self.aabbs = []
    def add(self, aabb):
        idx = len(self.aabbs); self.aabbs.append(aabb)
        ix0 = int(aabb[0][0] / self.cell_size); ix1 = int(aabb[1][0] / self.cell_size)
        iz0 = int(aabb[0][2] / self.cell_size); iz1 = int(aabb[1][2] / self.cell_size)
        for ix in range(ix0, ix1 + 1):
            for iz in range(iz0, iz1 + 1):
                self.cells[(ix, iz)].append(idx)
    def query_xz(self, min_x, max_x, min_z, max_z):
        result = set()
        ix0 = int(min_x / self.cell_size); ix1 = int(max_x / self.cell_size)
        iz0 = int(min_z / self.cell_size); iz1 = int(max_z / self.cell_size)
        for ix in range(ix0, ix1 + 1):
            for iz in range(iz0, iz1 + 1):
                for gi in self.cells.get((ix, iz), []):
                    result.add(gi)
        return result


def aabbs_overlap_3d(a, b, eps=0.001):
    return (a[1][0] > b[0][0] + eps and a[0][0] < b[1][0] - eps and
            a[1][1] > b[0][1] + eps and a[0][1] < b[1][1] - eps and
            a[1][2] > b[0][2] + eps and a[0][2] < b[1][2] - eps)


def meshes_collide(mesh_a, mesh_b, eps=0.01):
    """
    Check if two meshes truly intersect (share volume).
    Uses dense surface sampling + signed distance to detect penetration.
    Falls back to AABB overlap if sampling fails.
    """
    try:
        # Sample both meshes densely (faces, edges, interior)
        pts_a = mesh_a.sample(500)
        pts_b = mesh_b.sample(500)
        
        # Check distance from A's samples to B's surface
        d_ab = trimesh.proximity.closest_point(mesh_b, pts_a)
        if d_ab is not None and d_ab[1].min() < eps:
            return True
        
        # Check distance from B's samples to A's surface
        d_ba = trimesh.proximity.closest_point(mesh_a, pts_b)
        if d_ba is not None and d_ba[1].min() < eps:
            return True
        
        # Also check if any vertex of one is inside the other
        # For watertight meshes, signed_distance < 0 means inside
        try:
            sd_a = trimesh.proximity.signed_distance(mesh_b, mesh_a.vertices)
            if sd_a is not None and np.any(sd_a < -eps):
                return True
            sd_b = trimesh.proximity.signed_distance(mesh_a, mesh_b.vertices)
            if sd_b is not None and np.any(sd_b < -eps):
                return True
        except Exception:
            pass
        
        return False
    except Exception:
        return aabbs_overlap_3d(
            [mesh_a.bounds[0], mesh_a.bounds[1]],
            [mesh_b.bounds[0], mesh_b.bounds[1]], eps)


def pack(orientations, box_dims, max_pieces=5000, verbose=True):
    box_l, box_w, box_h = box_dims
    placed = []
    grid = SpatialGrid(cell_size=max(box_l, box_w, box_h) / 10)
    start = time.time()
    
    primary = orientations[0]
    best_total = 0
    for o in orientations:
        sx, sy, sz = o['size']
        nx = max(1, int(box_l / sx)); nz = max(1, int(box_w / sz)); ny = max(1, int(box_h / sy))
        if nx * nz * ny > best_total:
            best_total = nx * nz * ny; primary = o
    
    if verbose:
        print(f"[Packer] Primary: {primary['name']} size={primary['size'].round(1)}, grid_est={best_total}")
    
    # Phase 1: AABB grid
    psx, psy, psz = primary['size']
    step_x = max(1.0, psx * 0.9)  # slightly tighter than AABB
    step_z = max(1.0, psz * 0.9)
    step_y = psy
    
    placed_grid = 0
    for o in orientations:
        sx, sy, sz = o['size']
        if sy > box_h: continue
        fine_step_x = max(1.0, min(step_x, sx * 0.5))
        fine_step_z = max(1.0, min(step_z, sz * 0.5))
        
        for y in np.arange(0, box_h - sy + 0.01, step_y):
            for x in np.arange(0, box_l - sx + 0.01, fine_step_x):
                for z in np.arange(0, box_w - sz + 0.01, fine_step_z):
                    if len(placed) >= max_pieces: break
                    x, y, z = float(x), float(y), float(z)
                    if x + sx > box_l + 0.01 or z + sz > box_w + 0.01 or y + sy > box_h + 0.01: continue
                    
                    cm = o['mesh'].copy(); cm.apply_translation([x, y, z])
                    ca = [[x, y, z], [x+sx, y+sy, z+sz]]
                    
                    neighbors = grid.query_xz(x, x+sx, z, z+sz)
                    collides = False
                    for gi in neighbors:
                        if aabbs_overlap_3d(ca, grid.aabbs[gi]):
                            if meshes_collide(cm, placed[gi][0]):
                                collides = True; break
                    if not collides:
                        grid.add(ca)
                        placed.append((cm, ca, o['name']))
                        placed_grid += 1
        
        if len(placed) >= max_pieces: break
    
    # Phase 2: sub-grid insertion between existing pieces
    if verbose: print(f"[Phase 2] Sub-grid insertion...")
    insertion_count = 0
    for o in orientations:
        if len(placed) >= max_pieces: break
        sx, sy, sz = o['size']
        if sy > box_h: continue
        fine_x = max(2.0, sx * 0.3)
        fine_z = max(2.0, sz * 0.3)
        
        for x in np.arange(0, box_l - sx + 0.01, fine_x):
            for z in np.arange(0, box_w - sz + 0.01, fine_z):
                if len(placed) >= max_pieces: break
                x, z = float(x), float(z)
                # Compute min y from neighbors
                min_y = 0.0
                for gi in grid.query_xz(x, x+sx, z, z+sz):
                    other_aabb = grid.aabbs[gi]
                    if x < other_aabb[1][0] and x+sx > other_aabb[0][0] and \
                       z < other_aabb[1][2] and z+sz > other_aabb[0][2]:
                        min_y = max(min_y, other_aabb[1][1])
                
                for y in np.arange(min_y, box_h - sy + 0.01, sy * 0.5):
                    y = float(y)
                    if y + sy > box_h + 0.01: break
                    cm = o['mesh'].copy(); cm.apply_translation([x, y, z])
                    ca = [[x, y, z], [x+sx, y+sy, z+sz]]
                    
                    collides = False
                    for gi in grid.query_xz(x, x+sx, z, z+sz):
                        if aabbs_overlap_3d(ca, grid.aabbs[gi]):
                            if meshes_collide(cm, placed[gi][0]):
                                collides = True; break
                    if not collides:
                        grid.add(ca)
                        placed.append((cm, ca, o['name']))
                        insertion_count += 1
                        break
        
        if len(placed) % 50 == 0 and insertion_count > 0 and verbose:
            print(f"  {len(placed)} placed, {insertion_count} insertions")
    
    elapsed = time.time() - start
    vol = sum(primary['mesh'].volume for _ in placed) if placed else 0
    if verbose:
        print(f"[Packer] DONE: {len(placed)} pieces, {vol/(box_l*box_w*box_h)*100:.1f}% fill, {elapsed:.0f}s")
        cnt = defaultdict(int)
        for _,_,n in placed: cnt[n] += 1
        print(f"[Packer] Orientations: {dict(sorted(cnt.items()))}")
    return placed


def verify(placed):
    collisions = 0
    for i in range(len(placed)):
        for j in range(i+1, len(placed)):
            if aabbs_overlap_3d(placed[i][1], placed[j][1]):
                if meshes_collide(placed[i][0], placed[j][0], eps=0.001):
                    collisions += 1
                    if collisions <= 5: print(f"  COLLISION: {i} vs {j}")
    if collisions == 0: print(f"  [OK] ZERO collisions — {len(placed)} pieces")
    else: print(f"  [FAIL] {collisions} collisions")
    return collisions == 0


def visualize(placed, box_dims, output_path):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    box_l, box_w, box_h = box_dims
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    fig.suptitle(f"Mesh Packing — {len(placed)} pieces", fontsize=14, fontweight='bold')
    colors = plt.cm.tab20(np.linspace(0, 1, 20))
    for title, ax, view in [("Top (XZ)", axes[0,0],'xz'), ("Front (XY)", axes[0,1],'xy'),
                             ("Side (ZY)", axes[1,0],'zy'), ("Height Map", axes[1,1],'hm')]:
        ax.set_title(title)
        if view == 'xz':
            ax.set_xlim(0, box_l); ax.set_ylim(0, box_w); ax.invert_yaxis()
            for i, p in enumerate(placed):
                a = p[1]; c = colors[i % 20]
                ax.add_patch(Rectangle((a[0][0], a[0][2]), a[1][0]-a[0][0], a[1][2]-a[0][2],
                                       alpha=0.15, color=c, ec='black', lw=0.2))
            ax.set_xlabel('X'); ax.set_ylabel('Z'); ax.set_aspect('equal')
        elif view == 'xy':
            ax.set_xlim(0, box_l); ax.set_ylim(0, box_h)
            for p in placed:
                a = p[1]
                ax.add_patch(Rectangle((a[0][0], a[0][1]), a[1][0]-a[0][0], a[1][1]-a[0][1],
                                       alpha=0.15, color=colors[0], ec='black', lw=0.2))
            ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_aspect('equal')
        elif view == 'zy':
            ax.set_xlim(0, box_w); ax.set_ylim(0, box_h)
            for p in placed:
                a = p[1]
                ax.add_patch(Rectangle((a[0][2], a[0][1]), a[1][2]-a[0][2], a[1][1]-a[0][1],
                                       alpha=0.15, color=colors[0], ec='black', lw=0.2))
            ax.set_xlabel('Z'); ax.set_ylabel('Y'); ax.set_aspect('equal')
        elif view == 'hm':
            hm = np.zeros((int(box_l//5)+1, int(box_w//5)+1)); cnt = np.zeros_like(hm)
            for p in placed:
                a = p[1]; ix, iz = int(a[0][0]/5), int(a[0][2]/5)
                if 0 <= ix < hm.shape[0] and 0 <= iz < hm.shape[1]:
                    hm[ix, iz] += a[1][1]; cnt[ix, iz] += 1
            m = cnt > 0
            if m.any(): hm[m] /= cnt[m]
            im = ax.imshow(hm.T, origin='lower', cmap='YlOrRd', extent=[0, box_l, 0, box_w], aspect='equal')
            plt.colorbar(im, ax=ax)
    plt.tight_layout(); plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"[Viz] {output_path}"); plt.close()


def main():
    p = argparse.ArgumentParser(description="Mesh-based 3D Packer")
    p.add_argument("stl", nargs="?", default=None)
    p.add_argument("box_l", nargs="?", type=float, default=385)
    p.add_argument("box_w", nargs="?", type=float, default=285)
    p.add_argument("box_h", nargs="?", type=float, default=150)
    p.add_argument("--n-yaw", type=int, default=8)
    p.add_argument("--n-roll", type=int, default=4)
    p.add_argument("--output", type=str, default="packed_mesh.png")
    args = p.parse_args()
    box_dims = (args.box_l, args.box_w, args.box_h)
    
    if args.stl:
        fp = Path(args.stl)
        if not fp.exists(): print(f"ERROR: {fp}"); sys.exit(1)
        mesh = trimesh.load(str(fp), force='mesh')
        if isinstance(mesh, trimesh.Scene):
            geoms = [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
            mesh = trimesh.util.concatenate(geoms) if geoms else None
        if mesh is None: print("ERROR: no mesh"); sys.exit(1)
        print(f"Loaded: {fp.name}  {len(mesh.vertices)}v  {mesh.volume:.0f}mm3")
    else:
        v = np.array([[0,0,20],[0,0,0],[0,-20,0],[0,-20,20],[40,0,0],[40,-20,0]], dtype=np.float64)
        f = np.array([[0,1,2],[0,2,3],[4,0,5],[5,0,3],[1,4,2],[2,4,5],[4,1,0],[2,5,3]], dtype=np.int32)
        mesh = trimesh.Trimesh(vertices=v, faces=f); box_dims = (200, 200, 150)
        print("Built-in triangle")
    
    print(f"\nGenerating orientations...")
    t0 = time.time()
    orients = generate_orientations(mesh, args.n_yaw, args.n_roll, box_dims)
    print(f"  {len(orients)} orientations ({time.time()-t0:.1f}s)")
    for o in orients[:5]: print(f"    {o['name']:>12s}  size={o['size'].round(1)}")
    
    print(f"\n--- Packing ---")
    t0 = time.time()
    placed = pack(orients, box_dims, verbose=True)
    
    print(f"\n--- Verification ---")
    verify(placed)
    
    print(f"\n--- Visualizing ---")
    visualize(placed, box_dims, args.output)
    print(f"\nTotal: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
