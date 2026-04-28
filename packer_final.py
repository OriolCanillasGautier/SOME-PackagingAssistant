"""
packer_final.py — Complete 3D bin packer.
Volume-accurate voxel occupancy. Deepest-cavity-first placement.
Mesh collision verification. Ready for GPU offload.

Usage:
    python packer_final.py [stl] [box_l] [box_w] [box_h]
"""
import sys, time, math, argparse
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.ndimage import binary_fill_holes
import trimesh


# ═══════════════════════════════════════════════
# Mesh volume voxelization (GPU-ready: per-face)
# ═══════════════════════════════════════════════

def voxelize(mesh, cell_size):
    """Rasterize mesh faces into dense 3D occupancy, then fill interior."""
    bmin = mesh.bounds[0] - cell_size
    bmax = mesh.bounds[1] + cell_size
    nx = max(1, int(math.ceil((bmax[0]-bmin[0])/cell_size)))
    ny = max(1, int(math.ceil((bmax[1]-bmin[1])/cell_size)))
    nz = max(1, int(math.ceil((bmax[2]-bmin[2])/cell_size)))
    occ = np.zeros((nx, ny, nz), dtype=np.uint8)
    
    for a, b, c in mesh.faces:
        v0, v1, v2 = mesh.vertices[a], mesh.vertices[b], mesh.vertices[c]
        tmin = np.min([v0, v1, v2], axis=0); tmax = np.max([v0, v1, v2], axis=0)
        ix0 = max(0, int((tmin[0]-bmin[0])/cell_size)); ix1 = min(nx-1, int((tmax[0]-bmin[0])/cell_size))
        iy0 = max(0, int((tmin[1]-bmin[1])/cell_size)); iy1 = min(ny-1, int((tmax[1]-bmin[1])/cell_size))
        iz0 = max(0, int((tmin[2]-bmin[2])/cell_size)); iz1 = min(nz-1, int((tmax[2]-bmin[2])/cell_size))
        e0, e1 = v1-v0, v2-v0; nrm = np.cross(e0, e1); nl = np.linalg.norm(nrm)
        if nl < 1e-12: continue
        nrm /= nl
        for ix in range(ix0, ix1+1):
            cx = bmin[0]+(ix+0.5)*cell_size
            for iy in range(iy0, iy1+1):
                cy = bmin[1]+(iy+0.5)*cell_size
                for iz in range(iz0, iz1+1):
                    cz = bmin[2]+(iz+0.5)*cell_size
                    pt = np.array([cx, cy, cz])
                    if abs(np.dot(pt-v0, nrm)) > cell_size*0.9: continue
                    vp = pt-v0
                    d00=np.dot(e0,e0); d01=np.dot(e0,e1); d11=np.dot(e1,e1); d20=np.dot(vp,e0); d21=np.dot(vp,e1)
                    denom = d00*d11 - d01*d01
                    if abs(denom) < 1e-12: continue
                    u=(d11*d20-d01*d21)/denom; v=(d00*d21-d01*d20)/denom
                    if u >= -0.05 and v >= -0.05 and u+v <= 1.05:
                        occ[ix, iy, iz] = 1
    try:
        occ = binary_fill_holes(occ > 0).astype(np.uint8)
    except: pass
    return occ, bmin


# ═══════════════════════════════════════════════
# Collision detection
# ═══════════════════════════════════════════════

def meshes_collide(mesh_a, mesh_b, eps=0.01, samples=500):
    try:
        pts_a = mesh_a.sample(samples); pts_b = mesh_b.sample(samples)
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


# ═══════════════════════════════════════════════
# Orientations
# ═══════════════════════════════════════════════

def generate_orientations(mesh, n_yaw, n_roll, box_dims, cell):
    """Generate orientations with pre-voxelized occupancy data."""
    results = []; seen = set(); base = mesh.copy()
    for yaw in np.linspace(0, 360, n_yaw, endpoint=False):
        for roll in np.linspace(0, 360, n_roll, endpoint=False):
            rot = Rotation.from_euler('xy', [roll, yaw], degrees=True).as_matrix()
            t = base.copy()
            t.apply_transform(np.vstack([np.hstack([rot, np.zeros((3,1))]), [0,0,0,1]]))
            bmin = t.bounds[0]; t.apply_translation([-bmin[0], -bmin[1], -bmin[2]])
            sz = t.extents
            if box_dims and (sz[0] > box_dims[0]+0.5 or sz[2] > box_dims[1]+0.5 or sz[1] > box_dims[2]+0.5): continue
            key = tuple(sz.round(1))
            if key in seen: continue
            seen.add(key)
            occ, origin = voxelize(t, cell)
            sparse = np.argwhere(occ > 0)
            hm = np.zeros((occ.shape[0], occ.shape[2]), dtype=np.int32)
            for p in sparse:
                if p[1]+1 > hm[p[0], p[2]]: hm[p[0], p[2]] = p[1]+1
            results.append({'mesh':t, 'size':sz, 'name':f"Y{yaw:.0f}R{roll:.0f}",
                           'occ':occ, 'sparse':sparse, 'hm':hm, 'origin':origin, 'occupied':int(occ.sum())})
    results.sort(key=lambda o: o['size'][1])
    return results


# ═══════════════════════════════════════════════
# Spatial grid
# ═══════════════════════════════════════════════

class SpatialGrid:
    def __init__(self, cell): self.cell=cell; self.cells=defaultdict(list); self.aabbs=[]
    def add(self, aabb):
        idx=len(self.aabbs); self.aabbs.append(aabb)
        ix0=int(aabb[0]/self.cell); ix1=int(aabb[3]/self.cell)
        iz0=int(aabb[2]/self.cell); iz1=int(aabb[5]/self.cell)
        for ix in range(ix0, ix1+1):
            for iz in range(iz0, iz1+1): self.cells[(ix,iz)].append(idx)
    def query(self, x0, x1, z0, z1):
        seen=set();
        ix0=int(x0/self.cell); ix1=int(x1/self.cell); iz0=int(z0/self.cell); iz1=int(z1/self.cell)
        for ix in range(ix0, ix1+1):
            for iz in range(iz0, iz1+1):
                for gi in self.cells.get((ix,iz),[]): seen.add(gi)
        return seen
    def min_y_xz(self, x0, x1, z0, z1):
        top=0.0
        for gi in self.query(x0, x1, z0, z1):
            a=self.aabbs[gi]
            if x0<a[3] and x1>a[0] and z0<a[5] and z1>a[2]: top=max(top, a[4])
        return top


# ═══════════════════════════════════════════════
# Main packer
# ═══════════════════════════════════════════════

def pack(orientations, box_dims, cell, max_pieces=5000, verbose=True):
    box_l, box_w, box_h = box_dims
    nx = int(math.ceil(box_l/cell)); ny = int(math.ceil(box_h/cell)); nz = int(math.ceil(box_w/cell))
    box_occ = np.zeros((nx, ny, nz), dtype=np.uint8)
    box_hm = np.zeros((nx, nz), dtype=np.int32)
    placed = []
    sgrid = SpatialGrid(cell=max(box_l,box_w,box_h)/10)
    usage = defaultdict(int)
    start = time.time()
    skips = 0; max_skips = nx * nz * 20
    
    if verbose:
        print(f"[Packer] Box: {box_l:.0f}x{box_w:.0f}x{box_h:.0f}mm -> {nx}x{ny}x{nz} voxels")
        print(f"[Packer] {len(orientations)} orientations")
    
    # Phase 1: Grid base layer (perfect AABB packing)
    if verbose: print("[Phase 1] Grid placement...")
    primary = orientations[0]  # shortest
    psx, psy, psz = primary['size']
    px_v = int(math.floor(psx / cell))
    py_v = int(math.floor(psy / cell))
    pz_v = int(math.floor(psz / cell))
    
    grid_count = 0
    for gy in range(0, ny - py_v + 1, py_v):
        y_mm_grid = gy * cell
        if y_mm_grid + psy > box_h: continue
        for gx in range(0, nx - px_v + 1, px_v):
            x_mm_grid = gx * cell
            if x_mm_grid + psx > box_l: continue
            for gz in range(0, nz - pz_v + 1, pz_v):
                z_mm_grid = gz * cell
                if z_mm_grid + psz > box_w: continue
                od = primary
                ox, oy, oz = od['occ'].shape
                if gx+ox > nx or gy+oy > ny or gz+oz > nz: continue
                sub = box_occ[gx:gx+ox, gy:gy+oy, gz:gz+oz]
                if np.any(sub & od['occ']): continue
                box_occ[gx:gx+ox, gy:gy+oy, gz:gz+oz] |= od['occ']
                for p in od['sparse']:
                    wx, wy, wz = gx+p[0], gy+p[1], gz+p[2]
                    if wy+1 > box_hm[wx, wz]: box_hm[wx, wz] = wy+1
                x_mm, y_mm, z_mm = x_mm_grid, y_mm_grid, z_mm_grid
                pm = od['mesh'].copy(); pm.apply_translation([x_mm, y_mm, z_mm])
                aabb = (x_mm, y_mm, z_mm, x_mm+psx, y_mm+psy, z_mm+psz)
                sgrid.add(aabb)
                placed.append((pm, aabb, od['name']))
                usage[od['name']] += 1
                grid_count += 1
    if verbose: print(f"  Grid: {grid_count} pieces placed")
    
    # Phase 2: Cavity fill (greedy deepest-first)
    if verbose: print("[Phase 2] Cavity filling...")
    
    while len(placed) < max_pieces and skips < max_skips:
        idx = np.argmin(box_hm)
        bx = idx // nz; bz = idx % nz
        if box_hm[bx, bz] >= ny: break
        
        best_score = float('inf'); best = None
        
        for oi, od in enumerate(orientations):
            ox, oy, oz = od['occ'].shape
            x_end_v = bx + ox; z_end_v = bz + oz
            if x_end_v > nx or z_end_v > nz: continue
            if oy > ny: continue
            
            x_mm = bx * cell; x1_mm = x_end_v * cell
            z_mm = bz * cell; z1_mm = z_end_v * cell
            
            # Start Y from AABB top of neighbors
            y_aabb = sgrid.min_y_xz(x_mm, x1_mm, z_mm, z1_mm)
            y_v = int(y_aabb / cell)
            
            # Scan up to find first non-colliding Y
            for try_y in range(y_v, ny - oy + 1):
                sub = box_occ[bx:bx+ox, try_y:try_y+oy, bz:bz+oz]
                if np.any(sub & od['occ']): continue
                
                # Mesh collision verification (sparse neighbors)
                y_mm = try_y * cell; y1_mm = y_mm + od['size'][1]
                cand = od['mesh'].copy(); cand.apply_translation([x_mm, y_mm, z_mm])
                ca = (x_mm, y_mm, z_mm, x1_mm, y1_mm, z1_mm)
                collides = False
                for gi in sgrid.query(x_mm, x1_mm, z_mm, z1_mm):
                    oa = sgrid.aabbs[gi]
                    if ca[0]<oa[3] and ca[3]>oa[0] and ca[1]<oa[4] and ca[4]>oa[1] and ca[2]<oa[5] and ca[5]>oa[2]:
                        if meshes_collide(cand, placed[gi][0], samples=200):
                            collides = True; break
                if not collides:
                    score = try_y * 10000 + bx * 10 + bz + usage.get(od['name'], 0)*0.5
                    if score < best_score: best_score=score; best=(oi, bx, try_y, bz, od['name'])
                    break  # found a Y, done with this orientation
        
        if best is None:
            box_hm[bx, bz] = ny
            skips += 1
            continue
        
        oi, bx, by, bz, oname = best
        od = orientations[oi]
        ox, oy, oz = od['occ'].shape
        x_mm = bx * cell; y_mm = by * cell; z_mm = bz * cell
        
        # Place in box occupancy
        box_occ[bx:bx+ox, by:by+oy, bz:bz+oz] |= od['occ']
        
        # Update height map from voxelized piece
        for p in od['sparse']:
            wx, wy, wz = bx+p[0], by+p[1], bz+p[2]
            if wy+1 > box_hm[wx, wz]: box_hm[wx, wz] = wy+1
        
        pm = od['mesh'].copy(); pm.apply_translation([x_mm, y_mm, z_mm])
        aabb = (x_mm, y_mm, z_mm, x_mm+od['size'][0], y_mm+od['size'][1], z_mm+od['size'][2])
        sgrid.add(aabb)
        placed.append((pm, aabb, oname)); usage[oname] += 1; skips = 0
        
        if verbose and len(placed) % 50 == 0:
            elapsed = time.time()-start
            fill = (box_occ.sum() / (nx*ny*nz)) * 100
            print(f"[Packer] {len(placed)} placed, {fill:.1f}% fill, {elapsed:.0f}s  {oname}@({x_mm:.0f},{y_mm:.0f},{z_mm:.0f})")
    
    elapsed = time.time()-start
    if verbose:
        fill = (box_occ.sum() / (nx*ny*nz)) * 100
        print(f"\n[Packer] DONE: {len(placed)} pieces, {fill:.1f}% fill, {elapsed:.0f}s")
        print(f"[Packer] Usage: {dict(sorted(usage.items()))}")
    return placed


def verify(placed):
    collisions = 0
    for i in range(len(placed)):
        for j in range(i+1, len(placed)):
            a_i=placed[i][1]; a_j=placed[j][1]
            if a_i[0]<a_j[3] and a_i[3]>a_j[0] and a_i[1]<a_j[4] and a_i[4]>a_j[1] and a_i[2]<a_j[5] and a_i[5]>a_j[2]:
                if meshes_collide(placed[i][0], placed[j][0], eps=0.001):
                    collisions += 1
                    if collisions <= 5: print(f"  COLLISION: {i}({placed[i][2]}) vs {j}({placed[j][2]})")
    ok = collisions == 0
    print(f"  [{'OK' if ok else 'FAIL'}] {'ZERO' if ok else collisions} collisions — {len(placed)} pieces")
    return ok


def visualize(placed, box_dims, output_path):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    box_l,box_w,box_h = box_dims
    fig,axes = plt.subplots(2,2,figsize=(16,14))
    fig.suptitle(f"3D Packing — {len(placed)} pieces, {box_l:.0f}x{box_w:.0f}x{box_h:.0f}mm",fontsize=14,fontweight='bold')
    colors = plt.cm.tab20(np.linspace(0,1,20))
    for title,ax,view in [("Top",axes[0,0],'xz'),("Front",axes[0,1],'xy'),("Side",axes[1,0],'zy'),("HMap",axes[1,1],'hm')]:
        ax.set_title(title)
        if view=='xz':
            ax.set_xlim(0,box_l); ax.set_ylim(0,box_w); ax.invert_yaxis()
            for i,(_,a,_) in enumerate(placed): ax.add_patch(Rectangle((a[0],a[2]),a[3]-a[0],a[5]-a[2],alpha=0.15,color=colors[i%20],ec='black',lw=0.2))
            ax.set_xlabel('X'); ax.set_ylabel('Z'); ax.set_aspect('equal')
        elif view=='xy':
            ax.set_xlim(0,box_l); ax.set_ylim(0,box_h)
            for _,a,_ in placed: ax.add_patch(Rectangle((a[0],a[1]),a[3]-a[0],a[4]-a[1],alpha=0.15,color=colors[0],ec='black',lw=0.2))
            ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_aspect('equal')
        elif view=='zy':
            ax.set_xlim(0,box_w); ax.set_ylim(0,box_h)
            for _,a,_ in placed: ax.add_patch(Rectangle((a[2],a[1]),a[5]-a[2],a[4]-a[1],alpha=0.15,color=colors[0],ec='black',lw=0.2))
            ax.set_xlabel('Z'); ax.set_ylabel('Y'); ax.set_aspect('equal')
        elif view=='hm':
            hm=np.zeros((int(box_l//5)+1,int(box_w//5)+1)); cnt=np.zeros_like(hm)
            for _,a,_ in placed: ix,iz=int(a[0]/5),int(a[2]/5)
            if 0<=ix<hm.shape[0] and 0<=iz<hm.shape[1]: hm[ix,iz]+=a[4]; cnt[ix,iz]+=1
            m=cnt>0
            if m.any(): hm[m]/=cnt[m]
            ax.imshow(hm.T,origin='lower',cmap='YlOrRd',extent=[0,box_l,0,box_w],aspect='equal'); ax.set_xlabel('X'); ax.set_ylabel('Z')
    plt.tight_layout(); plt.savefig(output_path,dpi=150,bbox_inches='tight'); print(f"[Viz] {output_path}"); plt.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("stl", nargs="?", default=None)
    p.add_argument("box_l", nargs="?", type=float, default=385)
    p.add_argument("box_w", nargs="?", type=float, default=285)
    p.add_argument("box_h", nargs="?", type=float, default=150)
    p.add_argument("--cell", type=float, default=2.0)
    p.add_argument("--yaw", type=int, default=8)
    p.add_argument("--roll", type=int, default=4)
    p.add_argument("--max", type=int, default=5000)
    p.add_argument("--output", type=str, default="packed_final.png")
    args = p.parse_args()
    box_dims = (args.box_l, args.box_w, args.box_h)
    
    if args.stl:
        fp=Path(args.stl)
        if not fp.exists(): print(f"ERROR {fp}"); sys.exit(1)
        mesh=trimesh.load(str(fp), force='mesh')
        if isinstance(mesh, trimesh.Scene):
            mesh=trimesh.util.concatenate([g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)])
        if mesh is None: print("ERROR"); sys.exit(1)
        print(f"Loaded: {fp.name} {len(mesh.vertices)}v {mesh.volume:.0f}mm3 Fill:{mesh.volume/mesh.extents.prod()*100:.1f}%")
    else:
        v=np.array([[0,0,20],[0,0,0],[0,-20,0],[0,-20,20],[40,0,0],[40,-20,0]], dtype=np.float64)
        f=np.array([[0,1,2],[0,2,3],[4,0,5],[5,0,3],[1,4,2],[2,4,5],[4,1,0],[2,5,3]], dtype=np.int32)
        mesh=trimesh.Trimesh(vertices=v, faces=f); box_dims=(200,200,150)
        print("Built-in triangle")
    
    print(f"\nGenerating orientations ({args.yaw}yaw x {args.roll}roll, {args.cell}mm cells)...")
    t0=time.time(); orients=generate_orientations(mesh, args.yaw, args.roll, box_dims, args.cell)
    print(f"  {len(orients)} orientations ({time.time()-t0:.1f}s)")
    for o in orients[:6]: print(f"    {o['name']:>12s} size={o['size'].round(1)} occ={o['occupied']}cells")
    
    print(f"\nPacking...")
    t0=time.time(); placed=pack(orients, box_dims, args.cell, max_pieces=args.max, verbose=True)
    print(f"\nVerification..."); ok=verify(placed)
    print(f"\nVisualizing..."); visualize(placed, box_dims, args.output)
    print(f"\nTotal: {time.time()-t0:.0f}s, {len(placed)} pieces, {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    main()
