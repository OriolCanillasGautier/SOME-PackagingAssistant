"""
packer_relief.py — Hybrid 3D packer: grid base layer + greedy cavity filling.
For complex sparse shapes, achieves high density through interleaving.

Usage:
    python packer_relief.py [stl] [box_l] [box_w] [box_h] [--cell C] [--yaw N] [--roll N]
"""
import sys, time, math, argparse
from pathlib import Path
from collections import deque
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation as R
from scipy.ndimage import binary_fill_holes


# ── voxelization ────────────────────────────────────────────────

def voxelize_mesh(mesh, cell_size):
    bmin = mesh.bounds[0] - cell_size
    bmax = mesh.bounds[1] + cell_size
    nx = max(1, int(math.ceil((bmax[0]-bmin[0])/cell_size)))
    ny = max(1, int(math.ceil((bmax[1]-bmin[1])/cell_size)))
    nz = max(1, int(math.ceil((bmax[2]-bmin[2])/cell_size)))
    occ = np.zeros((nx, ny, nz), dtype=np.uint8)

    for face in mesh.faces:
        v0, v1, v2 = mesh.vertices[face]
        tri_min = np.min([v0, v1, v2], axis=0); tri_max = np.max([v0, v1, v2], axis=0)
        ix0 = max(0, int(math.floor((tri_min[0]-bmin[0])/cell_size)))
        ix1 = min(nx-1, int(math.floor((tri_max[0]-bmin[0])/cell_size)))
        iy0 = max(0, int(math.floor((tri_min[1]-bmin[1])/cell_size)))
        iy1 = min(ny-1, int(math.floor((tri_max[1]-bmin[1])/cell_size)))
        iz0 = max(0, int(math.floor((tri_min[2]-bmin[2])/cell_size)))
        iz1 = min(nz-1, int(math.floor((tri_max[2]-bmin[2])/cell_size)))
        e0, e1 = v1-v0, v2-v0
        nrm = np.cross(e0, e1); nl = np.linalg.norm(nrm)
        if nl < 1e-12: continue
        nrm = nrm/nl
        for ix in range(ix0, ix1+1):
            for iy in range(iy0, iy1+1):
                for iz in range(iz0, iz1+1):
                    cx = bmin[0]+(ix+0.5)*cell_size; cy = bmin[1]+(iy+0.5)*cell_size; cz = bmin[2]+(iz+0.5)*cell_size
                    pt = np.array([cx, cy, cz])
                    if abs(np.dot(pt-v0, nrm)) > cell_size*0.9: continue
                    vp = pt-v0
                    d00, d01, d11 = np.dot(e0, e0), np.dot(e0, e1), np.dot(e1, e1)
                    d20, d21 = np.dot(vp, e0), np.dot(vp, e1)
                    denom = d00*d11 - d01*d01
                    if abs(denom) < 1e-12: continue
                    u = (d11*d20 - d01*d21)/denom
                    v = (d00*d21 - d01*d20)/denom
                    if u >= -0.05 and v >= -0.05 and u+v <= 1.05:
                        occ[ix, iy, iz] = 1
    try: occ = binary_fill_holes(occ > 0).astype(np.uint8)
    except Exception: pass
    return occ, bmin


# ── orientations ────────────────────────────────────────────────

def generate_orientations(mesh, n_yaw, n_roll, cell_size, box_dims):
    orientations = []
    seen = set(); base = mesh.copy()
    for yaw in np.linspace(0, 360, n_yaw, endpoint=False):
        for roll in np.linspace(0, 360, n_roll, endpoint=False):
            rot = R.from_euler('xy', [roll, yaw], degrees=True).as_matrix()
            t = base.copy()
            t.apply_transform(np.vstack([np.hstack([rot, np.zeros((3,1))]), [0,0,0,1]]))
            bmin = t.bounds[0]; t.apply_translation([-bmin[0], -bmin[1], -bmin[2]])
            sm = t.extents
            if box_dims and (sm[0]>box_dims[0]+0.5 or sm[2]>box_dims[1]+0.5 or sm[1]>box_dims[2]+0.5): continue
            key = tuple(sm.round(1))
            if key in seen: continue
            seen.add(key)
            occ, origin = voxelize_mesh(t, cell_size)
            occ_n = int(occ.sum())
            if occ_n == 0: continue
            sparse = np.argwhere(occ > 0)
            hm = np.zeros((occ.shape[0], occ.shape[2]), dtype=np.int32)
            col_mins = np.full((occ.shape[0], occ.shape[2]), 99999, dtype=np.int32)
            for p in sparse:
                px, py, pz = p
                if py+1 > hm[px, pz]: hm[px, pz] = py+1
                if py < col_mins[px, pz]: col_mins[px, pz] = py
            col_mins[col_mins == 99999] = 0
            orientations.append({
                'occ': occ, 'sparse': sparse, 'hm': hm, 'col_mins': col_mins,
                'name': f"Y{yaw:.0f}_R{roll:.0f}", 'size_mm': sm,
                'size_vox': occ.shape, 'occupied': occ_n, 'mesh': t,
            })
    orientations.sort(key=lambda o: (o['size_mm'][1], o['occupied']))
    return orientations


# ── packing: grid base + cavity fill ────────────────────────────

def pack(orientations, box_dims, cell_size, max_pieces=5000, verbose=True):
    box_l, box_w, box_h = box_dims
    box_nx = int(math.ceil(box_l/cell_size))
    box_ny = int(math.ceil(box_h/cell_size))
    box_nz = int(math.ceil(box_w/cell_size))
    box_occ = np.zeros((box_nx, box_ny, box_nz), dtype=np.uint8)
    box_hm = np.zeros((box_nx, box_nz), dtype=np.int32)
    placed = []; usage = {}; start = time.time()

    if verbose:
        print(f"[Packer] Box: {box_l}x{box_w}x{box_h} -> {box_nx}x{box_ny}x{box_nz} voxels, cell={cell_size}mm")
        print(f"[Packer] {len(orientations)} orientations")

    def try_place_at(x, z, oi):
        """Try to place orientation oi at voxel position (x,z). Returns (y, world_coords) or None."""
        od = orientations[oi]; sx, sy, sz = od['size_vox']
        if x + sx > box_nx or z + sz > box_nz or sy > box_ny: return None
        x_sl, z_sl = slice(x, x+sx), slice(z, z+sz)
        sub_hm = box_hm[x_sl, z_sl]
        mask = od['hm'] > 0
        base_y = 0 if not mask.any() else max(0, int((sub_hm[mask] - od['col_mins'][mask]).max()))
        if base_y + sy > box_ny: return None

        for try_y in range(base_y, box_ny - sy + 1):
            w = od['sparse'] + np.array([x, try_y, z])
            if not box_occ[w[:,0], w[:,1], w[:,2]].any():
                return (try_y, w)
            if try_y - base_y > 20: break  # don't search too far
        return None

    def commit(x, y, z, oi):
        od = orientations[oi]
        w = od['sparse'] + np.array([x, y, z])
        box_occ[w[:,0], w[:,1], w[:,2]] = 1
        for p in od['sparse']:
            wy = y + p[1]
            if wy >= box_hm[x+p[0], z+p[2]]:
                box_hm[x+p[0], z+p[2]] = wy + 1
        placed.append((x*cell_size, y*cell_size, z*cell_size, oi, od['name']))
        usage[od['name']] = usage.get(od['name'], 0) + 1

    def report():
        if len(placed) % 50 == 0 and len(placed) > 0:
            elapsed = time.time() - start
            nfree = box_nx * box_nz - np.count_nonzero(box_hm > 0)
            print(f"[Packer] {len(placed)} placed, {elapsed:.0f}s  free={nfree} cells")

    # ── Phase 1: Grid placement for the best orientation ──
    if verbose: print("[Phase 1] Grid base layer...")
    primary = orientations[0]  # shortest (best for layers)
    sx, sy, sz = primary['size_vox']
    if sx > 0 and sz > 0:
        step_x = sx  # tight packing (voxel-level AABB)
        step_z = sz
        for ix in range(0, box_nx - sx + 1, step_x):
            for iz in range(0, box_nz - sz + 1, step_z):
                if len(placed) >= max_pieces: break
                res = try_place_at(ix, iz, 0)
                if res:
                    commit(ix, res[0], iz, 0)
        if verbose: print(f"  Grid: {len(placed)} pieces placed")

    # ── Phase 2: Cavity filling (greedy, check all unfilled positions) ──
    if verbose: print("[Phase 2] Cavity filling...")
    free_cells = list(zip(*np.where(box_hm == 0)))
    # Sort by position (fill from one corner)
    free_cells.sort(key=lambda p: (p[0], p[1]))

    tried = set()
    idx = 0
    while idx < len(free_cells) and len(placed) < max_pieces:
        x, z = free_cells[idx]
        if (x, z) in tried:
            idx += 1
            continue
        if box_hm[x, z] >= box_ny:
            tried.add((x, z))
            idx += 1
            continue

        best_res = None
        best_score = float('inf')
        for oi in range(len(orientations)):
            res = try_place_at(x, z, oi)
            if res:
                y = res[0]
                score = y * 1000 + usage.get(orientations[oi]['name'], 0) * 0.5
                if score < best_score:
                    best_score = score
                    best_res = (oi, x, y, z)

        if best_res:
            oi, x, y, z = best_res
            commit(x, y, z, oi)
            # Refresh free cells near this position
            if len(placed) % 20 == 0:
                free_cells = list(zip(*np.where(box_hm == 0)))
                free_cells.sort(key=lambda p: (p[0], p[1]))
                idx = 0
                tried.clear()
            report()
        else:
            tried.add((x, z))
            idx += 1
            if idx % 5000 == 0 and verbose:
                print(f"  scanned {idx}/{len(free_cells)} cells, {len(placed)} placed")

    elapsed = time.time() - start
    if verbose and len(placed) > 0:
        vol_fill = sum(orientations[p[3]]['occupied'] for p in placed) * cell_size**3
        print(f"\n[Packer] DONE: {len(placed)} pieces, {vol_fill/(box_l*box_w*box_h)*100:.1f}% fill, {elapsed:.0f}s")
        print(f"[Packer] Usage: { {k:v for k,v in sorted(usage.items()) if v>0} }")
    return placed, orientations, box_occ


# ── verify, visualize, main (same as before) ────────────────────

def verify(placed, orientations, box_occ):
    if box_occ.max() <= 1:
        print("  [OK] ZERO voxel overlap!"); return True
    print(f"  [FAIL] {int((box_occ>1).sum())} overlapping voxels"); return False

def visualize(placed, orientations, box_dims, box_occ, cell_size, output_path):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    box_l, box_w, box_h = box_dims
    fig, axes = plt.subplots(2, 2, figsize=(16,14))
    fig.suptitle(f"Packing — {len(placed)} pieces, Box: {box_l:.0f}x{box_w:.0f}x{box_h:.0f}mm", fontsize=14, fontweight='bold')
    colors = plt.cm.tab20(np.linspace(0, 1, max(20, len(orientations))))
    views = [("Top View (XZ)", axes[0,0],'xz'), ("Front View (XY)", axes[0,1],'xy'),
             ("Side View (ZY)", axes[1,0],'zy'), ("Height Map", axes[1,1],'hm')]
    for title, ax, view in views:
        ax.set_title(title)
        if view == 'xz':
            ax.set_xlim(0,box_l); ax.set_ylim(0,box_w); ax.invert_yaxis()
            for i,(x,y,z,oi,_) in enumerate(placed):
                op=orientations[oi]; c=colors[oi%len(colors)]
                ax.add_patch(Rectangle((x,z), op['size_mm'][0], op['size_mm'][2], alpha=0.12+0.3*y/box_h, color=c, ec='black', lw=0.2))
            ax.set_xlabel('X'); ax.set_ylabel('Z'); ax.set_aspect('equal')
        elif view == 'xy':
            ax.set_xlim(0,box_l); ax.set_ylim(0,box_h)
            for x,y,z,oi,_ in placed:
                op=orientations[oi]; c=colors[oi%len(colors)]
                ax.add_patch(Rectangle((x,y), op['size_mm'][0], op['size_mm'][1], alpha=0.12, color=c, ec='black', lw=0.2))
            ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_aspect('equal')
        elif view == 'zy':
            ax.set_xlim(0,box_w); ax.set_ylim(0,box_h)
            for x,y,z,oi,_ in placed:
                op=orientations[oi]; c=colors[oi%len(colors)]
                ax.add_patch(Rectangle((z,y), op['size_mm'][2], op['size_mm'][1], alpha=0.12, color=c, ec='black', lw=0.2))
            ax.set_xlabel('Z'); ax.set_ylabel('Y'); ax.set_aspect('equal')
        elif view == 'hm':
            hm_mean = np.zeros((int(box_l//5)+1, int(box_w//5)+1)); cnt = np.zeros_like(hm_mean)
            for x,y,z,oi,_ in placed:
                ix,iz = int(x/5), int(z/5)
                if 0<=ix<hm_mean.shape[0] and 0<=iz<hm_mean.shape[1]: hm_mean[ix,iz]+=y; cnt[ix,iz]+=1
            nz_mask = cnt>0
            if nz_mask.any(): hm_mean[nz_mask] /= cnt[nz_mask]
            im = ax.imshow(hm_mean.T, origin='lower', cmap='YlOrRd', extent=[0,box_l,0,box_w], aspect='equal')
            ax.set_xlabel('X'); ax.set_ylabel('Z'); plt.colorbar(im, ax=ax, label='Avg height (mm)')
    plt.tight_layout(); plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"[Viz] Saved {output_path}"); plt.close()

def main():
    p = argparse.ArgumentParser(description="3D Voxel Packer — hybrid grid + cavity")
    p.add_argument("stl", nargs="?", default=None)
    p.add_argument("box_l", nargs="?", type=float, default=385)
    p.add_argument("box_w", nargs="?", type=float, default=285)
    p.add_argument("box_h", nargs="?", type=float, default=150)
    p.add_argument("--cell", type=float, default=2.0)
    p.add_argument("--yaw", type=int, default=8)
    p.add_argument("--roll", type=int, default=4)
    p.add_argument("--max", type=int, default=5000)
    p.add_argument("--output", type=str, default="packed_relief.png")
    args = p.parse_args()
    box_dims = (args.box_l, args.box_w, args.box_h); cell = args.cell

    if args.stl:
        fp = Path(args.stl)
        if not fp.exists(): print(f"ERROR: not found: {fp}"); sys.exit(1)
        mesh = trimesh.load(str(fp), force='mesh')
        if isinstance(mesh, trimesh.Scene):
            geoms = [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
            mesh = trimesh.util.concatenate(geoms) if geoms else None
        if mesh is None: print("ERROR: no mesh"); sys.exit(1)
        print(f"Loaded: {fp.name}  {len(mesh.vertices)}v {mesh.volume:.0f}mm3")
    else:
        v = np.array([[0,0,20],[0,0,0],[0,-20,0],[0,-20,20],[40,0,0],[40,-20,0]], dtype=np.float64)
        f = np.array([[0,1,2],[0,2,3],[4,0,5],[5,0,3],[1,4,2],[2,4,5],[4,1,0],[2,5,3]], dtype=np.int32)
        mesh = trimesh.Trimesh(vertices=v, faces=f); box_dims = (200, 200, 150)
        print("Using built-in triangle")

    print(f"\n--- Generating orientations ({args.yaw}yaw x {args.roll}roll) at {cell}mm ---")
    t0 = time.time()
    orients = generate_orientations(mesh, args.yaw, args.roll, cell, box_dims)
    print(f"  {len(orients)} orientations ({time.time()-t0:.1f}s)")
    for o in orients[:5]: print(f"    {o['name']:>12s}  size={o['size_mm'].round(1)}  occ={o['occupied']}cells")

    print(f"\n--- Packing ---")
    t0 = time.time()
    placed, orients, box_occ = pack(orients, box_dims, cell, args.max, verbose=True)
    print(f"\n--- Verification ---"); verify(placed, orients, box_occ)
    print(f"\n--- Visualizing ---"); visualize(placed, orients, box_dims, box_occ, cell, args.output)
    print(f"\nTotal: {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
