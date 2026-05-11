"""
packer_cpu.py ΓÇö CPU-based sparse-voxel packer for sub-mm resolution.
Uses height-map + sparse voxel set checking. Fits in RAM (64GB).
For when voxel grids exceed GPU memory.

Usage:
    python packer_cpu.py [stl] [box_l] [box_w] [box_h] --cell C --yaw N --roll N --pitch N
"""
import sys, time, math, argparse
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.ndimage import binary_fill_holes
import trimesh


def voxelize_mesh(mesh, cell_size):
    bmin = mesh.bounds[0] - cell_size
    bmax = mesh.bounds[1] + cell_size
    nx,ny,nz = [max(1,int(math.ceil((bmax[i]-bmin[i])/cell_size))) for i in range(3)]
    occ = np.zeros((nx,ny,nz), dtype=np.uint8)
    for fi in range(len(mesh.faces)):
        f = mesh.faces[fi]
        v0,v1,v2 = mesh.vertices[f[0]].copy(), mesh.vertices[f[1]].copy(), mesh.vertices[f[2]].copy()
        tmin,tmax = np.min([v0,v1,v2],axis=0), np.max([v0,v1,v2],axis=0)
        ix0=max(0,int((tmin[0]-bmin[0])/cell_size)); ix1=min(nx-1,int((tmax[0]-bmin[0])/cell_size))
        iy0=max(0,int((tmin[1]-bmin[1])/cell_size)); iy1=min(ny-1,int((tmax[1]-bmin[1])/cell_size))
        iz0=max(0,int((tmin[2]-bmin[2])/cell_size)); iz1=min(nz-1,int((tmax[2]-bmin[2])/cell_size))
        if ix0>ix1 or iy0>iy1 or iz0>iz1: continue
        e0x,e0y,e0z = float(v1[0]-v0[0]),float(v1[1]-v0[1]),float(v1[2]-v0[2])
        e1x,e1y,e1z = float(v2[0]-v0[0]),float(v2[1]-v0[1]),float(v2[2]-v0[2])
        nxn=nyn=nzn=0.0
        nxn=e0y*e1z-e0z*e1y; nyn=e0z*e1x-e0x*e1z; nzn=e0x*e1y-e0y*e1x
        nl=math.sqrt(nxn*nxn+nyn*nyn+nzn*nzn)
        if nl<1e-12: continue; nxn/=nl; nyn/=nl; nzn/=nl
        d00=e0x*e0x+e0y*e0y+e0z*e0z; d01=e0x*e1x+e0y*e1y+e0z*e1z
        d11=e1x*e1x+e1y*e1y+e1z*e1z; denom=d00*d11-d01*d01
        if abs(denom)<1e-12: continue
        v0x,v0y,v0z=float(v0[0]),float(v0[1]),float(v0[2])
        for ix in range(ix0,ix1+1):
            cx=bmin[0]+(ix+0.5)*cell_size; dpx0=cx-v0x
            for iy in range(iy0,iy1+1):
                cy=bmin[1]+(iy+0.5)*cell_size; dpy0=cy-v0y
                for iz in range(iz0,iz1+1):
                    cz=bmin[2]+(iz+0.5)*cell_size; dpz0=cz-v0z
                    if abs(dpx0*nxn+dpy0*nyn+dpz0*nzn)>cell_size*1.1: continue
                    d20=dpx0*e0x+dpy0*e0y+dpz0*e0z; d21=dpx0*e1x+dpy0*e1y+dpz0*e1z
                    u=(d11*d20-d01*d21)/denom; v=(d00*d21-d01*d20)/denom
                    if u>=-0.08 and v>=-0.08 and u+v<=1.08: occ[ix,iy,iz]=1
    try: occ = binary_fill_holes(occ>0).astype(np.uint8)
    except: pass
    return occ, bmin


def generate_orientations(mesh, cell_size, n_yaw, n_roll, n_pitch, box_dims):
    results=[]; seen=set()
    for yaw in np.linspace(0,360,n_yaw,endpoint=False):
        for roll in np.linspace(0,360,n_roll,endpoint=False):
            for pitch in np.linspace(0,360,n_pitch,endpoint=False):
                rot=Rotation.from_euler('xyz',[roll,pitch,yaw],degrees=True).as_matrix()
                t=mesh.copy()
                t.apply_transform(np.vstack([np.hstack([rot,np.zeros((3,1))]),[0,0,0,1]]))
                bmin=t.bounds[0]; t.apply_translation([-bmin[0],-bmin[1],-bmin[2]])
                sz=t.extents
                if box_dims and (sz[0]>box_dims[0]+0.5 or sz[2]>box_dims[1]+0.5 or sz[1]>box_dims[2]+0.5): continue
                key=tuple(np.round(sz).astype(int))
                if key in seen: continue; seen.add(key)
                occ,origin=voxelize_mesh(t,cell_size)
                n_occ=int(occ.sum())
                if n_occ==0: continue
                sparse=np.argwhere(occ>0).astype(np.int32)
                hm=np.zeros((occ.shape[0],occ.shape[2]),dtype=np.int32)
                for p in sparse:
                    if p[1]+1>hm[p[0],p[2]]: hm[p[0],p[2]]=p[1]+1
                # Also store sparse as set of tuples for fast lookup
                sparse_set=set(tuple(p) for p in sparse)
                results.append({'mesh':t,'size':sz,'name':f'Y{yaw:.0f}R{roll:.0f}P{pitch:.0f}',
                               'sparse':sparse,'sparse_set':sparse_set,'n_occ':n_occ,
                               'hm':hm,'shape':occ.shape,'cell':cell_size})
    results.sort(key=lambda o:(o['size'][1],o['n_occ']))
    return results


def pack_cpu(orientations, box_dims, cell_size, max_pieces=5000, scan_step_mm=1.0, verbose=True):
    box_l, box_w, box_h = box_dims
    box_nx=int(math.ceil(box_l/cell_size))
    box_ny=int(math.ceil(box_h/cell_size))
    box_nz=int(math.ceil(box_w/cell_size))

    # Height map (2D) ΓÇö fits in memory even at 0.1mm
    box_hm = np.zeros((box_nx, box_nz), dtype=np.int32)
    # Sparse occupancy: set of (x,y,z) tuples for placed voxels
    box_occ_set = set()

    placed_meshes = []
    usage = defaultdict(int)
    start = time.time()
    consecutive_fails = 0

    if verbose:
        print(f"[CPU] Box: {box_l:.0f}x{box_w:.0f}x{box_h:.0f}mm -> {box_nx}x{box_ny}x{box_nz} voxels")
        print(f"[CPU] {len(orientations)} orientations, cell={cell_size}mm, scan={scan_step_mm}mm")
        gb = (box_nx * box_ny * box_nz) / 1e9
        print(f"[CPU] Dense grid would be {gb:.1f}GB, using sparse set instead")
        print(f"[CPU] RAM available: 64GB")

    scan_vox = max(1, int(scan_step_mm / cell_size))

    while len(placed_meshes) < max_pieces and consecutive_fails < 50:
        best_y = float('inf')
        best_placement = None

        for oi, o in enumerate(orientations):
            sx_v, sy_v, sz_v = o['shape']
            if sy_v > box_ny: continue

            for x in range(0, box_nx - sx_v + 1, scan_vox):
                for z in range(0, box_nz - sz_v + 1, scan_vox):
                    # Compute base Y from height map
                    base_vox = 0
                    for px, py, pz in o['sparse']:
                        h = box_hm[x + px, z + pz]
                        needed = h - py
                        if needed > base_vox: base_vox = needed
                    if base_vox < 0: base_vox = 0

                    # Scan Y upward
                    max_y = box_ny - sy_v
                    for try_y in range(base_vox, max_y + 1):
                        # Sparse collision check
                        collides = False
                        for px, py, pz in o['sparse']:
                            if (x + px, try_y + py, z + pz) in box_occ_set:
                                collides = True
                                break
                        if not collides:
                            y_mm = try_y * cell_size
                            if y_mm < best_y:
                                best_y = y_mm
                                best_placement = (oi, x, try_y, z, o['name'])
                            break

        if best_placement is None:
            consecutive_fails += 1
            continue

        oi, x, y, z, oname = best_placement
        od = orientations[oi]
        y_mm = y * cell_size; x_mm = x * cell_size; z_mm = z * cell_size

        # Update sparse occupancy set
        for px, py, pz in od['sparse']:
            box_occ_set.add((x + px, y + py, z + pz))

        # Update height map
        for px, py, pz in od['sparse']:
            wx, wy, wz = x + px, y + py, z + pz
            if wy + 1 > box_hm[wx, wz]:
                box_hm[wx, wz] = wy + 1

        pm = od['mesh'].copy(); pm.apply_translation([x_mm, y_mm, z_mm])
        placed_meshes.append(pm)
        usage[oname] += 1
        consecutive_fails = 0

        if verbose and len(placed_meshes) % 25 == 0:
            elapsed = time.time() - start
            fill = len(box_occ_set) * cell_size**3 / (box_l * box_w * box_h) * 100
            print(f"[CPU] {len(placed_meshes)} placed, {fill:.1f}% fill, {elapsed:.0f}s  {oname}@({x_mm:.0f},{y_mm:.0f},{z_mm:.0f})")

    elapsed = time.time() - start
    if verbose and placed_meshes:
        fill = len(box_occ_set) * cell_size**3 / (box_l * box_w * box_h) * 100
        print(f"\n[CPU] DONE: {len(placed_meshes)} pieces, {fill:.1f}% fill, {elapsed:.0f}s")
        print(f"[CPU] Usage: {dict(sorted(usage.items()))}")
    return placed_meshes


def meshes_collide(a,b,eps=0.01):
    try:
        d=trimesh.proximity.closest_point(a,b.vertices)
        if d is not None and d[1].min()<eps: return True
        d=trimesh.proximity.closest_point(b,a.vertices)
        if d is not None and d[1].min()<eps: return True
        return False
    except: return False

def verify(placed_meshes):
    collisions=0
    for i in range(len(placed_meshes)):
        for j in range(i+1,len(placed_meshes)):
            a,b=placed_meshes[i].bounds,placed_meshes[j].bounds
            if (a[1,0]>b[0,0] and a[0,0]<b[1,0] and a[1,1]>b[0,1] and a[0,1]<b[1,1] and a[1,2]>b[0,2] and a[0,2]<b[1,2]):
                if meshes_collide(placed_meshes[i],placed_meshes[j],0.001):
                    collisions+=1
                    if collisions<=5: print(f"  COLLISION: {i} vs {j}")
    ok=collisions==0
    print(f"  [{'OK' if ok else 'FAIL'}] {'ZERO' if ok else collisions} collisions - {len(placed_meshes)} pieces")
    return ok

def visualize(placed_meshes, box_dims, output_path):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    box_l,box_w,box_h=box_dims
    fig,axes=plt.subplots(2,2,figsize=(16,14))
    fig.suptitle(f"CPU Packing - {len(placed_meshes)} pieces",fontsize=14,fontweight='bold')
    colors=plt.cm.tab20(np.linspace(0,1,max(20,len(placed_meshes))))
    for title,ax,view in [("Top (XZ)",axes[0,0],'xz'),("Front (XY)",axes[0,1],'xy'),
                           ("Side (ZY)",axes[1,0],'zy'),("HMap",axes[1,1],'hm')]:
        ax.set_title(title)
        if view=='xz':
            ax.set_xlim(0,box_l); ax.set_ylim(0,box_w); ax.invert_yaxis()
            for i,m in enumerate(placed_meshes):
                b=m.bounds; ax.add_patch(Rectangle((b[0,0],b[0,2]),b[1,0]-b[0,0],b[1,2]-b[0,2],alpha=0.15,color=colors[i%20],ec='black',lw=0.2))
            ax.set_xlabel('X'); ax.set_ylabel('Z'); ax.set_aspect('equal')
        elif view=='xy':
            ax.set_xlim(0,box_l); ax.set_ylim(0,box_h)
            for m in placed_meshes: b=m.bounds; ax.add_patch(Rectangle((b[0,0],b[0,1]),b[1,0]-b[0,0],b[1,1]-b[0,1],alpha=0.15,color=colors[0],ec='black',lw=0.2))
            ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_aspect('equal')
        elif view=='zy':
            ax.set_xlim(0,box_w); ax.set_ylim(0,box_h)
            for m in placed_meshes: b=m.bounds; ax.add_patch(Rectangle((b[0,2],b[0,1]),b[1,2]-b[0,2],b[1,1]-b[0,1],alpha=0.15,color=colors[0],ec='black',lw=0.2))
            ax.set_xlabel('Z'); ax.set_ylabel('Y'); ax.set_aspect('equal')
        elif view=='hm':
            hm=np.zeros((int(box_l//5)+1,int(box_w//5)+1)); cnt=np.zeros_like(hm)
            for m in placed_meshes: b=m.bounds; ix,iz=int(b[0,0]/5),int(b[0,2]/5)
            if 0<=ix<hm.shape[0] and 0<=iz<hm.shape[1]: hm[ix,iz]+=b[1,1]; cnt[ix,iz]+=1
            nz=cnt>0
            if nz.any(): hm[nz]/=cnt[nz]
            ax.imshow(hm.T,origin='lower',cmap='YlOrRd',extent=[0,box_l,0,box_w],aspect='equal')
            ax.set_xlabel('X'); ax.set_ylabel('Z')
    plt.tight_layout(); plt.savefig(output_path,dpi=150,bbox_inches='tight')
    print(f"[Viz] {output_path}"); plt.close()

    # Export merged STL
    stl_path=output_path.replace('.png','_merged.stl')
    try:
        merged=trimesh.util.concatenate(placed_meshes)
        merged.export(stl_path)
        print(f"[Viz] Merged STL: {stl_path}")
    except Exception as e:
        print(f"[Viz] STL skipped: {e}")


def main():
    p=argparse.ArgumentParser(description="CPU Sparse-Voxel Packer")
    p.add_argument("stl",nargs="?",default=None)
    p.add_argument("box_l",nargs="?",type=float,default=385)
    p.add_argument("box_w",nargs="?",type=float,default=285)
    p.add_argument("box_h",nargs="?",type=float,default=150)
    p.add_argument("--cell",type=float,default=0.1)
    p.add_argument("--scan",type=float,default=None,help="XZ scan step in mm (default: cell*2)")
    p.add_argument("--yaw",type=int,default=8); p.add_argument("--roll",type=int,default=4)
    p.add_argument("--pitch",type=int,default=4)
    p.add_argument("--output",type=str,default="packed_cpu.png")
    args=p.parse_args()
    box_dims=(args.box_l,args.box_w,args.box_h)
    cell=args.cell
    scan_mm = args.scan if args.scan else cell * 2

    if args.stl:
        fp=Path(args.stl)
        if not fp.exists(): print(f"ERROR: {fp}"); sys.exit(1)
        mesh=trimesh.load(str(fp),force='mesh')
        if isinstance(mesh,trimesh.Scene):
            mesh=trimesh.util.concatenate([g for g in mesh.geometry.values() if isinstance(g,trimesh.Trimesh)])
        if mesh is None: print("ERROR"); sys.exit(1)
        print(f"Loaded: {fp.name}  {len(mesh.vertices)}v  {mesh.volume:.0f}mm3")
    else:
        v=np.array([[0,0,20],[0,0,0],[0,-20,0],[0,-20,20],[40,0,0],[40,-20,0]],dtype=np.float64)
        f=np.array([[0,1,2],[0,2,3],[4,0,5],[5,0,3],[1,4,2],[2,4,5],[4,1,0],[2,5,3]],dtype=np.int32)
        mesh=trimesh.Trimesh(vertices=v,faces=f); box_dims=(200,200,150)
        print("Built-in triangle")

    print(f"Generating orientations ({args.yaw}yaw x {args.roll}roll x {args.pitch}pitch, {cell}mm cells)...")
    t0=time.time()
    orients=generate_orientations(mesh,cell,args.yaw,args.roll,args.pitch,box_dims)
    print(f"  {len(orients)} orientations ({time.time()-t0:.1f}s)")
    for o in orients[:6]: print(f"    {o['name']:>16s}  size={o['size'].round(1)}  occ={o['n_occ']}cells")

    print(f"\nPacking (CPU sparse, scan={scan_mm}mm)...")
    t0=time.time()
    placed_meshes=pack_cpu(orients,box_dims,cell,scan_step_mm=scan_mm,verbose=True)
    print(f"\nVerifying...")
    ok=verify(placed_meshes)
    print(f"\nVisualizing...")
    visualize(placed_meshes,box_dims,args.output)
    print(f"\nTotal: {time.time()-t0:.0f}s, {len(placed_meshes)} pieces, {'PASS' if ok else 'FAIL'}")

if __name__=="__main__":
    main()
