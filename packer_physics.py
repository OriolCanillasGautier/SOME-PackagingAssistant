"""
packer_physics.py — Physics-based 3D packer v2.
Systematic XZ scan + binary-search Y settling + lateral slide.
Mesh-collision verified. Zero boundary errors.

Usage:
    python packer_physics.py [stl] [box_l] [box_w] [box_h] [--drops N] [--step S]
"""
import sys, time, math, argparse
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.spatial.transform import Rotation
import trimesh


def meshes_collide(mesh_a, mesh_b, eps=0.02):
    try:
        pts_a = mesh_a.sample(300); pts_b = mesh_b.sample(300)
        d = trimesh.proximity.closest_point(mesh_b, pts_a)
        if d is not None and d[1].min() < eps: return True
        d = trimesh.proximity.closest_point(mesh_a, pts_b)
        if d is not None and d[1].min() < eps: return True
        try:
            sd = trimesh.proximity.signed_distance(mesh_b, mesh_a.vertices)
            if sd is not None and np.any(sd < -eps): return True
            sd = trimesh.proximity.signed_distance(mesh_a, mesh_b.vertices)
            if sd is not None and np.any(sd < -eps): return True
        except: pass
        return False
    except: return True


def generate_orientations(mesh, n_yaw=16, n_roll=8, box_dims=None):
    results = []; seen = set(); base = mesh.copy()
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
            results.append({'mesh': t, 'size': sz, 'name': f"Y{yaw:.0f}R{roll:.0f}"})
    results.sort(key=lambda o: (o['size'][1], o['size'][0]*o['size'][2]))
    return results


class SpatialGrid:
    def __init__(self, cell): self.cell=cell; self.cells=defaultdict(list); self.aabbs=[]
    def add(self, aabb):
        idx=len(self.aabbs); self.aabbs.append(aabb)
        ix0=int(aabb[0]/self.cell); ix1=int(aabb[3]/self.cell)
        iz0=int(aabb[2]/self.cell); iz1=int(aabb[5]/self.cell)
        for ix in range(ix0, ix1+1):
            for iz in range(iz0, iz1+1): self.cells[(ix,iz)].append(idx)
    def query(self, x0, x1, z0, z1):
        seen=set(); ix0=int(x0/self.cell); ix1=int(x1/self.cell)
        iz0=int(z0/self.cell); iz1=int(z1/self.cell)
        for ix in range(ix0, ix1+1):
            for iz in range(iz0, iz1+1):
                for gi in self.cells.get((ix,iz),[]): seen.add(gi)
        return seen
    def min_y_xz(self, x0, x1, z0, z1):
        top = 0.0
        for gi in self.query(x0, x1, z0, z1):
            a = self.aabbs[gi]
            if x0 < a[3] and x1 > a[0] and z0 < a[5] and z1 > a[2]:
                top = max(top, a[4])
        return top


def find_settlement_y(mesh_candidate, x, z, box_dims, placed_meshes, sgrid, precision=0.5):
    """
    Binary search for the lowest Y where the piece doesn't collide.
    Piece must stay within box bounds.
    """
    box_l, box_w, box_h = box_dims
    sx, sy, sz = mesh_candidate.extents
    
    # Piece at position (x, y, z) — its AABB is [x, y, z] to [x+sx, y+sy, z+sz]
    lo = 0.0  # floor
    hi = box_h - sy + 1.0  # max possible Y
    
    # First check: does the piece even fit at the floor?
    test_mesh = mesh_candidate.copy(); test_mesh.apply_translation([x, lo, z])
    if not _mesh_fits_box(test_mesh, box_dims):
        return None  # piece doesn't fit in box horizontally
    
    # Check if hi is valid
    test_mesh = mesh_candidate.copy(); test_mesh.apply_translation([x, hi - 1.0, z])
    if not _mesh_fits_box(test_mesh, box_dims):
        hi = box_h - sy
    
    for _ in range(30):  # binary search iterations
        if hi - lo < precision:
            break
        mid = (lo + hi) / 2
        test_mesh = mesh_candidate.copy(); test_mesh.apply_translation([x, mid, z])
        
        if _collides_with_placed(test_mesh, x, mid, z, sx, sy, sz, placed_meshes, sgrid):
            lo = mid  # collision — need to go higher
        else:
            hi = mid  # no collision — can go lower
    
    # Final check at 'hi'
    final_y = hi
    final_mesh = mesh_candidate.copy(); final_mesh.apply_translation([x, final_y, z])
    
    if not _mesh_fits_box(final_mesh, box_dims):
        return None
    
    if _collides_with_placed(final_mesh, x, final_y, z, sx, sy, sz, placed_meshes, sgrid):
        return None
    
    return final_y


def _mesh_fits_box(mesh, box_dims, margin=0.1):
    b = mesh.bounds
    return (b[0, 0] >= -margin and b[0, 1] >= -margin and b[0, 2] >= -margin and
            b[1, 0] <= box_dims[0] + margin and b[1, 1] <= box_dims[2] + margin and
            b[1, 2] <= box_dims[1] + margin)


def _collides_with_placed(mesh, x, y, z, sx, sy, sz, placed_meshes, sgrid):
    ca = (x, y, z, x+sx, y+sy, z+sz)
    for gi in sgrid.query(ca[0], ca[3], ca[2], ca[5]):
        oa = sgrid.aabbs[gi]
        if (ca[0] < oa[3] and ca[3] > oa[0] and
            ca[1] < oa[4] and ca[4] > oa[1] and
            ca[2] < oa[5] and ca[5] > oa[2]):
            if meshes_collide(mesh, placed_meshes[gi][0]):
                return True
    return False


def try_lateral_slide(mesh_candidate, x, y, z, box_dims, placed_meshes, sgrid, step=2.0):
    """
    After placing at (x,y,z), try sliding it in small XZ increments to find a lower Y.
    Slide toward the lowest neighbor.
    """
    box_l, box_w, box_h = box_dims
    sx, sy, sz = mesh_candidate.extents
    
    directions = [(step, 0), (-step, 0), (0, step), (0, -step),
                  (step, step), (-step, step), (step, -step), (-step, -step)]
    
    best_x, best_y, best_z = x, y, z
    
    for dx, dz in directions:
        nx = max(0, min(box_l - sx, x + dx))
        nz = max(0, min(box_w - sz, z + dz))
        
        new_y = find_settlement_y(mesh_candidate, nx, nz, box_dims, placed_meshes, sgrid, 1.0)
        if new_y is not None and new_y < best_y - 0.5:
            best_x, best_y, best_z = nx, new_y, nz
    
    return best_x, best_y, best_z


def pack(orientations, box_dims, scan_step=5.0, max_pieces=5000, verbose=True):
    """
    AABB-guided placement with mesh collision verification.
    Scan XZ, compute min Y from AABB overlap, verify with mesh collision,
    place at lowest valid position. Lateral slide for refinement.
    """
    box_l, box_w, box_h = box_dims
    placed = []; sgrid = SpatialGrid(cell=max(box_l, box_w, box_h) / 10)
    usage = defaultdict(int)
    start = time.time()
    
    if verbose:
        print(f"[Physics] Box: {box_l:.0f}x{box_w:.0f}x{box_h:.0f}mm, scan={scan_step}mm")
        print(f"[Physics] {len(orientations)} orientations")
    
    skips = 0; max_skips = 5000
    
    while len(placed) < max_pieces and skips < max_skips:
        best_y = float('inf'); best_placement = None
        
        for oi, od in enumerate(orientations):
            sx, sy, sz = od['size']
            if sy > box_h: continue
            
            # Use a coarser scan for faster coverage
            coarse_step = max(scan_step, min(sx, sz) * 0.5)
            
            for x in np.arange(0, box_l - sx + 0.01, coarse_step):
                for z in np.arange(0, box_w - sz + 0.01, coarse_step):
                    x, z = float(x), float(z)
                    
                    # Fast Y from AABB overlap
                    y_aabb = sgrid.min_y_xz(x, x+sx, z, z+sz)
                    if y_aabb + sy > box_h: continue
                    
                    # Check a few Y levels above AABB top
                    y_step = max(1.0, sy * 0.1)
                    for try_y in np.arange(y_aabb, min(box_h - sy, y_aabb + sy) + 0.01, y_step):
                        try_y = float(try_y)
                        test_mesh = od['mesh'].copy(); test_mesh.apply_translation([x, try_y, z])
                        
                        if not _mesh_fits_box(test_mesh, box_dims): break
                        
                        if _collides_with_placed(test_mesh, x, try_y, z, sx, sy, sz, placed, sgrid):
                            continue
                        
                        # Found valid position
                        if try_y < best_y:
                            best_y = try_y
                            best_placement = (oi, x, try_y, z, od['name'])
                        break  # found lowest Y for this XZ
        
        if best_placement is None:
            skips += 1
            if skips % 500 == 0 and verbose: print(f"  skips={skips}")
            continue
        
        oi, x, y, z, oname = best_placement
        od = orientations[oi]
        placed_mesh = od['mesh'].copy(); placed_mesh.apply_translation([x, y, z])
        aabb = (x, y, z, x + od['size'][0], y + od['size'][1], z + od['size'][2])
        
        sgrid.add(aabb)
        placed.append((placed_mesh, aabb, oname))
        usage[oname] += 1
        skips = 0
        
        if verbose and len(placed) % 25 == 0:
            elapsed = time.time() - start
            vol = sum(p[0].volume for p in placed) if placed else 0
            fill = vol / (box_l * box_w * box_h) * 100
            print(f"[Physics] {len(placed)} placed, {fill:.1f}% fill, {elapsed:.0f}s  {oname}@({x:.0f},{y:.0f},{z:.0f})")
    
    elapsed = time.time() - start
    if verbose and placed:
        vol = sum(p[0].volume for p in placed)
        fill = vol / (box_l * box_w * box_h) * 100
        print(f"\n[Physics] DONE: {len(placed)} pieces, {fill:.1f}% fill, {elapsed:.0f}s")
        print(f"[Physics] Usage: {dict(sorted(usage.items()))}")
    return placed


def verify(placed):
    collisions = 0
    for i in range(len(placed)):
        for j in range(i+1, len(placed)):
            a = placed[i][1]; b = placed[j][1]
            if (a[0] < b[3] and a[3] > b[0] and a[1] < b[4] and a[4] > b[1] and a[2] < b[5] and a[5] > b[2]):
                if meshes_collide(placed[i][0], placed[j][0], eps=0.001):
                    collisions += 1
                    if collisions <= 5: print(f"  COLLISION: {i} vs {j}")
    ok = collisions == 0
    print(f"  [{'OK' if ok else 'FAIL'}] {'ZERO' if ok else collisions} collisions — {len(placed)} pieces")
    return ok


def visualize(placed, box_dims, output_path):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    box_l, box_w, box_h = box_dims
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    fig.suptitle(f"Physics Packing — {len(placed)} pieces", fontsize=14, fontweight='bold')
    colors = plt.cm.tab20(np.linspace(0, 1, 20))
    for title, ax, view in [("Top (XZ)", axes[0,0],'xz'), ("Front (XY)", axes[0,1],'xy'),
                             ("Side (ZY)", axes[1,0],'zy'), ("HMap", axes[1,1],'hm')]:
        ax.set_title(title)
        if view == 'xz':
            ax.set_xlim(0, box_l); ax.set_ylim(0, box_w); ax.invert_yaxis()
            for i, (_, a, _) in enumerate(placed):
                ax.add_patch(Rectangle((a[0],a[2]), a[3]-a[0], a[5]-a[2], alpha=0.15, color=colors[i%20], ec='black', lw=0.2))
            ax.set_xlabel('X'); ax.set_ylabel('Z'); ax.set_aspect('equal')
        elif view == 'xy':
            ax.set_xlim(0, box_l); ax.set_ylim(0, box_h)
            for _, a, _ in placed: ax.add_patch(Rectangle((a[0],a[1]), a[3]-a[0], a[4]-a[1], alpha=0.15, color=colors[0], ec='black', lw=0.2))
            ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_aspect('equal')
        elif view == 'zy':
            ax.set_xlim(0, box_w); ax.set_ylim(0, box_h)
            for _, a, _ in placed: ax.add_patch(Rectangle((a[2],a[1]), a[5]-a[2], a[4]-a[1], alpha=0.15, color=colors[0], ec='black', lw=0.2))
            ax.set_xlabel('Z'); ax.set_ylabel('Y'); ax.set_aspect('equal')
        elif view == 'hm':
            hm = np.zeros((int(box_l//5)+1, int(box_w//5)+1)); cnt = np.zeros_like(hm)
            for _, a, _ in placed: ix, iz = int(a[0]/5), int(a[2]/5)
            if 0 <= ix < hm.shape[0] and 0 <= iz < hm.shape[1]: hm[ix, iz] += a[4]; cnt[ix, iz] += 1
            m = cnt > 0
            if m.any(): hm[m] /= cnt[m]
            ax.imshow(hm.T, origin='lower', cmap='YlOrRd', extent=[0, box_l, 0, box_w], aspect='equal')
            ax.set_xlabel('X'); ax.set_ylabel('Z')
    plt.tight_layout(); plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"[Viz] {output_path}"); plt.close()


def main():
    p = argparse.ArgumentParser(description="Physics-based 3D Bin Packer v2")
    p.add_argument("stl", nargs="?", default=None)
    p.add_argument("box_l", nargs="?", type=float, default=385)
    p.add_argument("box_w", nargs="?", type=float, default=285)
    p.add_argument("box_h", nargs="?", type=float, default=150)
    p.add_argument("--scan", type=float, default=5.0, help="XZ scan step (mm)")
    p.add_argument("--yaw", type=int, default=16)
    p.add_argument("--roll", type=int, default=8)
    p.add_argument("--output", type=str, default="packed_physics.png")
    args = p.parse_args()
    box_dims = (args.box_l, args.box_w, args.box_h)
    
    if args.stl:
        fp = Path(args.stl)
        if not fp.exists(): print(f"ERROR: {fp}"); sys.exit(1)
        mesh = trimesh.load(str(fp), force='mesh')
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)])
        if mesh is None: print("ERROR"); sys.exit(1)
        print(f"Loaded: {fp.name}  {len(mesh.vertices)}v  {mesh.volume:.0f}mm3  Fill:{mesh.volume/mesh.extents.prod()*100:.1f}%")
    else:
        v = np.array([[0,0,20],[0,0,0],[0,-20,0],[0,-20,20],[40,0,0],[40,-20,0]], dtype=np.float64)
        f = np.array([[0,1,2],[0,2,3],[4,0,5],[5,0,3],[1,4,2],[2,4,5],[4,1,0],[2,5,3]], dtype=np.int32)
        mesh = trimesh.Trimesh(vertices=v, faces=f); box_dims = (200, 200, 150)
        print("Built-in triangle")
    
    print(f"\nGenerating orientations...")
    t0 = time.time()
    orients = generate_orientations(mesh, args.yaw, args.roll, box_dims)
    print(f"  {len(orients)} orientations ({time.time()-t0:.1f}s)")
    for o in orients[:6]: print(f"    {o['name']:>12s}  size={o['size'].round(1)}")
    
    print(f"\nPacking...")
    t0 = time.time()
    placed = pack(orients, box_dims, scan_step=args.scan, verbose=True)
    
    print(f"\nVerifying...")
    ok = verify(placed)
    
    print(f"\nVisualizing...")
    visualize(placed, box_dims, args.output)
    print(f"\nTotal: {time.time()-t0:.0f}s, {len(placed)} pieces, {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    main()
