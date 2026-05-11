"""
packer_gpu_voxel.py ΓÇö GPU-accelerated sparse-voxel 3D bin packer.
Voxelizes each piece orientation at 1mm resolution, uploads sparse occupancy to GPU,
tests thousands of (x,z,ori) candidates in parallel via CUDA.

Usage:
    python packer_gpu_voxel.py [stl] [box_l] [box_w] [box_h] [--cell C] [--yaw N] [--roll N] [--pitch N]
"""
import sys, time, math, argparse
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.ndimage import binary_fill_holes
import trimesh
from numba import cuda


# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# CPU: Voxelization
# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def voxelize_mesh(mesh, cell_size):
    """Rasterize mesh faces into 3D volume occupancy."""
    bmin = mesh.bounds[0] - cell_size
    bmax = mesh.bounds[1] + cell_size
    nx = max(1, int(math.ceil((bmax[0] - bmin[0]) / cell_size)))
    ny = max(1, int(math.ceil((bmax[1] - bmin[1]) / cell_size)))
    nz = max(1, int(math.ceil((bmax[2] - bmin[2]) / cell_size)))
    occ = np.zeros((nx, ny, nz), dtype=np.uint8)

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

        # Normal
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

                    # Distance to plane
                    dist = abs(dpx0*nx_n + dpy0*ny_n + dpz0*nz_n)
                    if dist > cell_size * 1.1:
                        continue

                    d20 = dpx0*e0x + dpy0*e0y + dpz0*e0z
                    d21 = dpx0*e1x + dpy0*e1y + dpz0*e1z
                    u = (d11 * d20 - d01 * d21) / denom
                    v = (d00 * d21 - d01 * d20) / denom

                    if u >= -0.08 and v >= -0.08 and u + v <= 1.08:
                        occ[ix, iy, iz] = 1

    try:
        occ = binary_fill_holes(occ > 0).astype(np.uint8)
    except Exception:
        pass
    return occ, bmin


def generate_orientations(mesh, cell_size, n_yaw, n_roll, n_pitch, box_dims):
    """Generate orientations with precomputed sparse voxel data + height maps."""
    results = []; seen = set()
    for yaw in np.linspace(0, 360, n_yaw, endpoint=False):
        for roll in np.linspace(0, 360, n_roll, endpoint=False):
            for pitch in np.linspace(0, 360, n_pitch, endpoint=False):
                rot = Rotation.from_euler('xyz', [roll, pitch, yaw], degrees=True).as_matrix()
                t = mesh.copy()
                t.apply_transform(np.vstack([np.hstack([rot, np.zeros((3, 1))]), [0, 0, 0, 1]]))
                bmin = t.bounds[0]; t.apply_translation([-bmin[0], -bmin[1], -bmin[2]])
                sz = t.extents
                if box_dims and (sz[0] > box_dims[0] + 0.5 or sz[2] > box_dims[1] + 0.5 or
                                 sz[1] > box_dims[2] + 0.5): continue
                key = tuple(np.round(sz).astype(int))
                if key in seen: continue
                seen.add(key)
                occ, origin = voxelize_mesh(t, cell_size)
                n_occ = int(occ.sum())
                if n_occ == 0: continue
                sparse = np.argwhere(occ > 0).astype(np.int32)
                # Height map: max y index for each (x,z) column
                hm = np.zeros((occ.shape[0], occ.shape[2]), dtype=np.int32)
                for p in sparse:
                    if p[1] + 1 > hm[p[0], p[2]]: hm[p[0], p[2]] = p[1] + 1
                results.append({'mesh': t, 'size': sz, 'name': f"Y{yaw:.0f}R{roll:.0f}P{pitch:.0f}",
                               'sparse': sparse, 'n_occ': n_occ, 'hm': hm, 'shape': occ.shape})
    results.sort(key=lambda o: (o['size'][1], o['n_occ']))
    return results


# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# GPU kernel
# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

@cuda.jit
def voxel_pack_kernel(
    candidates,       # [n, 5] float64: x,z,ori, best_y, valid
    all_sparse,       # [total_sparse, 3] int32: all sparse coords concatenated
    all_offsets,      # [n_oris + 1] int32: start index in all_sparse per orientation
    all_hm,           # [total_hm_cells] int32: all height maps concatenated
    all_hm_offsets,   # [n_oris + 1] int32: start index in all_hm per orientation
    all_shapes,       # [n_oris, 3] int32: (sx, sy, sz) per orientation
    box_occ,          # [box_nx, box_ny, box_nz] uint8: 3D occupancy grid
    box_hm,           # [box_nx, box_nz] int32: 2D height map
    box_nx, box_ny, box_nz,  # int
    y_res,            # float: Y scan resolution in voxels
):
    idx = cuda.grid(1)
    if idx >= candidates.shape[0]: return

    x = int(candidates[idx, 0])
    z = int(candidates[idx, 2])
    ori = int(candidates[idx, 1])
    if ori >= all_shapes.shape[0]: return

    sx, sy, sz = all_shapes[ori, 0], all_shapes[ori, 1], all_shapes[ori, 2]
    if x + sx > box_nx or z + sz > box_nz or sy > box_ny:
        return

    # Get sparse coords for this orientation
    off_start = all_offsets[ori]
    off_end = all_offsets[ori + 1]
    n_sparse = off_end - off_start

    # Compute base Y from height map (per-column surface)
    hm_off_start = all_hm_offsets[ori]
    base_vox = 0
    for i in range(off_start, off_end):
        px, py, pz = all_sparse[i, 0], all_sparse[i, 1], all_sparse[i, 2]
        h = box_hm[x + px, z + pz]
        needed = h - py  # py is local Y of this voxel in the piece
        if needed > base_vox:
            base_vox = needed
    if base_vox < 0: base_vox = 0

    # Scan Y upward from base_vox
    max_y = box_ny - sy
    for try_y in range(base_vox, max_y + 1):
        collides = False
        for i in range(off_start, off_end):
            px, py, pz = all_sparse[i, 0], all_sparse[i, 1], all_sparse[i, 2]
            if box_occ[x + px, try_y + py, z + pz]:
                collides = True
                break
        if not collides:
            candidates[idx, 3] = try_y * y_res  # back to mm
            candidates[idx, 4] = 1.0
            return


# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# Main packer
# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def pack(orientations, box_dims, cell_size, max_pieces=5000, scan_step_vox=1, verbose=True):
    box_l, box_w, box_h = box_dims
    box_nx = int(math.ceil(box_l / cell_size))
    box_ny = int(math.ceil(box_h / cell_size))
    box_nz = int(math.ceil(box_w / cell_size))
    
    box_occ = np.zeros((box_nx, box_ny, box_nz), dtype=np.uint8)
    box_hm = np.zeros((box_nx, box_nz), dtype=np.int32)
    
    # Concatenate sparse data for GPU
    all_sparse_list = [o['sparse'] for o in orientations]
    all_offsets = np.zeros(len(orientations) + 1, dtype=np.int32)
    for i, s in enumerate(all_sparse_list):
        all_offsets[i + 1] = all_offsets[i] + len(s)
    all_sparse = np.concatenate(all_sparse_list).astype(np.int32)
    
    all_hm_list = [o['hm'].flatten() for o in orientations]
    all_hm_offsets = np.zeros(len(orientations) + 1, dtype=np.int32)
    for i, h in enumerate(all_hm_list):
        all_hm_offsets[i + 1] = all_hm_offsets[i] + len(h)
    all_hm = np.concatenate(all_hm_list).astype(np.int32)
    
    all_shapes = np.array([o['shape'] for o in orientations], dtype=np.int32)
    
    d_all_sparse = cuda.to_device(all_sparse)
    d_all_offsets = cuda.to_device(all_offsets)
    d_all_hm = cuda.to_device(all_hm)
    d_all_hm_offsets = cuda.to_device(all_hm_offsets)
    d_all_shapes = cuda.to_device(all_shapes)
    d_box_occ = cuda.to_device(box_occ)
    d_box_hm = cuda.to_device(box_hm)
    
    placed = []; placed_meshes = []; usage = {}; start = time.time()
    consecutive_fails = 0
    
    if verbose:
        print(f"[VoxelGPU] Box: {box_l:.0f}x{box_w:.0f}x{box_h:.0f}mm -> {box_nx}x{box_ny}x{box_nz} voxels")
        print(f"[VoxelGPU] {len(orientations)} orientations, cell={cell_size}mm")
        print(f"[VoxelGPU] All sparse: {all_sparse.shape[0]} voxels total")
    
    while len(placed) < max_pieces and consecutive_fails < 50:
        # Build candidate list: every XZ position for every orientation
        candidates = []
        for oi, o in enumerate(orientations):
            sx_v, sy_v, sz_v = o['shape']
            if sy_v > box_ny: continue
            step = max(1, scan_step_vox)
            for x in range(0, box_nx - sx_v + 1, step):
                for z in range(0, box_nz - sz_v + 1, step):
                    candidates.append([float(x), float(oi), float(z), -1.0, 0.0])
        
        if not candidates:
            break
        
        d_candidates = cuda.to_device(np.array(candidates, dtype=np.float64))
        threads = 256
        blocks = (len(candidates) + threads - 1) // threads
        
        voxel_pack_kernel[blocks, threads](
            d_candidates, d_all_sparse, d_all_offsets,
            d_all_hm, d_all_hm_offsets, d_all_shapes,
            d_box_occ, d_box_hm, box_nx, box_ny, box_nz,
            cell_size
        )
        cuda.synchronize()
        
        results = d_candidates.copy_to_host()
        valid = results[:, 4] > 0.5
        
        if not valid.any():
            consecutive_fails += 1
            continue
        
        valid_results = results[valid]
        best_idx = np.argmin(valid_results[:, 3])  # lowest Y
        best = valid_results[best_idx]
        best_x, best_oi, best_z, best_y = int(best[0]), int(best[1]), int(best[2]), best[3]
        
        od = orientations[best_oi]
        sx_v, sy_v, sz_v = od['shape']
        
        # Place in box occupancy
        sp = od['sparse']
        world_sp = sp + np.array([best_x, int(best_y / cell_size), best_z])
        box_occ[world_sp[:, 0], world_sp[:, 1], world_sp[:, 2]] = 1
        
        # Update height map
        for p in sp:
            wx, wy, wz = best_x + p[0], int(best_y / cell_size) + p[1], best_z + p[2]
            if wy + 1 > box_hm[wx, wz]:
                box_hm[wx, wz] = wy + 1
        d_box_occ.copy_to_device(box_occ)
        d_box_hm.copy_to_device(box_hm)
        
        x_mm, y_mm, z_mm = best_x * cell_size, best_y, best_z * cell_size
        pm = od['mesh'].copy(); pm.apply_translation([x_mm, y_mm, z_mm])
        placed.append((x_mm, y_mm, z_mm, best_oi, od['name']))
        placed_meshes.append(pm)
        usage[od['name']] = usage.get(od['name'], 0) + 1
        consecutive_fails = 0
        
        if verbose and len(placed) % 50 == 0:
            elapsed = time.time() - start
            fill = box_occ.sum() * cell_size**3 / (box_l * box_w * box_h) * 100
            print(f"[VoxelGPU] {len(placed)} placed, {fill:.1f}% fill, {elapsed:.0f}s  {od['name']}@({x_mm:.0f},{y_mm:.0f},{z_mm:.0f})")
    
    elapsed = time.time() - start
    if verbose and placed:
        fill = box_occ.sum() * cell_size**3 / (box_l * box_w * box_h) * 100
        print(f"\n[VoxelGPU] DONE: {len(placed)} pieces, {fill:.1f}% fill, {elapsed:.0f}s")
        print(f"[VoxelGPU] Usage: {dict(sorted(usage.items()))}")
    return placed_meshes


# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# Verify + visualize
# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def meshes_collide(a, b, eps=0.01):
    try:
        d = trimesh.proximity.closest_point(a, b.vertices)
        if d is not None and d[1].min() < eps: return True
        d = trimesh.proximity.closest_point(b, a.vertices)
        if d is not None and d[1].min() < eps: return True
        return False
    except: return False

def verify(placed_meshes):
    collisions = 0
    for i in range(len(placed_meshes)):
        for j in range(i+1, len(placed_meshes)):
            a, b = placed_meshes[i].bounds, placed_meshes[j].bounds
            if (a[1,0]>b[0,0] and a[0,0]<b[1,0] and a[1,1]>b[0,1] and a[0,1]<b[1,1] and a[1,2]>b[0,2] and a[0,2]<b[1,2]):
                if meshes_collide(placed_meshes[i], placed_meshes[j], 0.001):
                    collisions += 1
                    if collisions <= 5: print(f"  COLLISION: {i} vs {j}")
    ok = collisions == 0
    print(f"  [{'OK' if ok else 'FAIL'}] {'ZERO' if ok else collisions} collisions - {len(placed_meshes)} pieces")
    return ok

def visualize(placed_meshes, box_dims, output_path):
    """Generate HD multi-angle visualization + interactive 3D view."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    
    box_l, box_w, box_h = box_dims
    fig = plt.figure(figsize=(24, 18))
    fig.suptitle(f"Voxel GPU Packing — {len(placed_meshes)} pieces, Box: {box_l:.0f}x{box_w:.0f}x{box_h:.0f}mm",
                 fontsize=16, fontweight='bold', y=0.98)
    
    colors = plt.cm.tab20(np.linspace(0, 1, max(20, len(placed_meshes))))
    
    # 3x2 grid of views
    views = [
        ("Top View (XZ)", (0, 0), 'xz'),
        ("Front View (XY)", (0, 1), 'xy'),
        ("Right View (ZY)", (1, 0), 'zy'),
        ("Isometric (3D-like)", (1, 1), 'iso'),
        ("Height Map (density)", (2, 0), 'hm_density'),
        ("Slice Map (Y layers)", (2, 1), 'hm_layers'),
    ]
    
    for title, (row, col), view in views:
        ax = fig.add_subplot(3, 2, row * 2 + col + 1)
        ax.set_title(title, fontsize=12, fontweight='bold')
        
        if view == 'xz':
            ax.set_xlim(0, box_l); ax.set_ylim(0, box_w); ax.invert_yaxis()
            for i, m in enumerate(placed_meshes):
                b = m.bounds; c = colors[i % 20]
                ax.add_patch(Rectangle((b[0,0], b[0,2]), b[1,0]-b[0,0], b[1,2]-b[0,2],
                                       alpha=0.12+0.2*b[1,1]/box_h, color=c, ec='black', lw=0.15))
            # Grid lines every 50mm
            for gx in np.arange(0, box_l, 50): ax.axvline(gx, color='gray', alpha=0.15, lw=0.5)
            for gz in np.arange(0, box_w, 50): ax.axhline(gz, color='gray', alpha=0.15, lw=0.5)
            ax.set_xlabel('X (mm)'); ax.set_ylabel('Z (mm)'); ax.set_aspect('equal')
            
        elif view == 'xy':
            ax.set_xlim(0, box_l); ax.set_ylim(0, box_h)
            for m in placed_meshes:
                b = m.bounds; c = colors[0]
                ax.add_patch(Rectangle((b[0,0], b[0,1]), b[1,0]-b[0,0], b[1,1]-b[0,1],
                                       alpha=0.12, color=c, ec='black', lw=0.15))
            for gx in np.arange(0, box_l, 50): ax.axvline(gx, color='gray', alpha=0.15, lw=0.5)
            for gy in np.arange(0, box_h, 50): ax.axhline(gy, color='gray', alpha=0.15, lw=0.5)
            ax.set_xlabel('X (mm)'); ax.set_ylabel('Y (mm)'); ax.set_aspect('equal')
            
        elif view == 'zy':
            ax.set_xlim(0, box_w); ax.set_ylim(0, box_h)
            for m in placed_meshes:
                b = m.bounds; c = colors[0]
                ax.add_patch(Rectangle((b[0,2], b[0,1]), b[1,2]-b[0,2], b[1,1]-b[0,1],
                                       alpha=0.12, color=c, ec='black', lw=0.15))
            for gz in np.arange(0, box_w, 50): ax.axvline(gz, color='gray', alpha=0.15, lw=0.5)
            for gy in np.arange(0, box_h, 50): ax.axhline(gy, color='gray', alpha=0.15, lw=0.5)
            ax.set_xlabel('Z (mm)'); ax.set_ylabel('Y (mm)'); ax.set_aspect('equal')
            
        elif view == 'iso':
            # Isometric-like projection: show X and Z with Y as color/alpha
            ax.set_xlim(0, box_l); ax.set_ylim(0, box_w)
            for i, m in enumerate(placed_meshes):
                b = m.bounds; c = colors[i % 20]
                h = b[1, 1]
                # Show AABB with color and height-based alpha
                w = b[1,0]-b[0,0]; d = b[1,2]-b[0,2]
                ax.add_patch(Rectangle((b[0,0], b[0,2]), w, d,
                                       alpha=0.15+0.3*(h/box_h), color=c, ec='black', lw=0.15))
                # Label every 50th piece
                if i % 50 == 0:
                    ax.text(b[0,0]+w/2, b[0,2]+d/2, f"y={h:.0f}", fontsize=5, ha='center', va='center')
            ax.set_xlabel('X (mm)'); ax.set_ylabel('Z (mm)'); ax.set_aspect('equal')
            ax.set_title(f"Isometric — darkest=low, brightest=high", fontsize=11)
            
        elif view == 'hm_density':
            # Piece count density map (how many pieces overlap each XZ cell)
            hm_density = np.zeros((int(box_l//5)+1, int(box_w//5)+1))
            for m in placed_meshes:
                b = m.bounds
                ix0, ix1 = int(b[0,0]/5), min(hm_density.shape[0]-1, int(b[1,0]/5))
                iz0, iz1 = int(b[0,2]/5), min(hm_density.shape[1]-1, int(b[1,2]/5))
                hm_density[ix0:ix1+1, iz0:iz1+1] += 1
            im = ax.imshow(hm_density.T, origin='lower', cmap='plasma',
                          extent=[0, box_l, 0, box_w], aspect='equal')
            plt.colorbar(im, ax=ax, label='Pieces overlapping', shrink=0.8)
            ax.set_xlabel('X (mm)'); ax.set_ylabel('Z (mm)')
            
        elif view == 'hm_layers':
            # Average Y height per XZ cell
            hm = np.zeros((int(box_l//5)+1, int(box_w//5)+1)); cnt = np.zeros_like(hm)
            for m in placed_meshes:
                b = m.bounds
                ix0, iz0 = int(b[0,0]/5), int(b[0,2]/5)
                ix1 = min(hm.shape[0]-1, int(b[1,0]/5))
                iz1 = min(hm.shape[1]-1, int(b[1,2]/5))
                hm[ix0:ix1+1, iz0:iz1+1] += b[1,1]; cnt[ix0:ix1+1, iz0:iz1+1] += 1
            nz = cnt > 0
            if nz.any(): hm[nz] /= cnt[nz]
            im = ax.imshow(hm.T, origin='lower', cmap='YlOrRd',
                          extent=[0, box_l, 0, box_w], aspect='equal')
            # Add contour lines for height levels
            X = np.linspace(0, box_l, hm.shape[0])
            Z = np.linspace(0, box_w, hm.shape[1])
            ax.contour(X, Z, hm.T, levels=5, colors='black', alpha=0.3, linewidths=0.5)
            plt.colorbar(im, ax=ax, label='Avg height (mm)', shrink=0.8)
            ax.set_xlabel('X (mm)'); ax.set_ylabel('Z (mm)')
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')
    print(f"[Viz] HD visualization saved to {output_path}")
    plt.close()
    
    # Also export merged STL for 3D viewing
    stl_path = output_path.replace('.png', '_merged.stl')
    try:
        merged = trimesh.util.concatenate(placed_meshes)
        merged.export(stl_path)
        print(f"[Viz] Merged STL export saved to {stl_path}")
    except Exception as e:
        print(f"[Viz] STL export skipped: {e}")
    
    # Try interactive 3D view
    try:
        scene = trimesh.Scene()
        for i, m in enumerate(placed_meshes):
            mesh_copy = m.copy()
            r, g, b = plt.cm.tab20(i % 20)[:3]
            mesh_copy.visual.face_colors = [int(r*255), int(g*255), int(b*255), 200]
            scene.add_geometry(mesh_copy, node_name=f"piece_{i}")
        # Add box wireframe
        box_verts = np.array([
            [0,0,0],[box_l,0,0],[box_l,0,box_w],[0,0,box_w],[0,0,0],
            [0,box_h,0],[box_l,box_h,0],[box_l,box_h,box_w],[0,box_h,box_w],[0,box_h,0]
        ])
        box_lines = trimesh.path.Path3D(entities=[trimesh.path.entities.Line(np.arange(10))],
                                        vertices=box_verts, colors=[0,255,0,255])
        scene.add_geometry(box_lines)
        # Show interactive window (blocks until closed)
        scene.show(background=[30,30,40,255])
        print(f"[Viz] Interactive 3D viewer closed")
    except Exception as e:
        print(f"[Viz] 3D viewer skipped (headless?): {e}")

def main():
    p = argparse.ArgumentParser(description="GPU Voxel Packer")
    p.add_argument("stl", nargs="?", default=None)
    p.add_argument("box_l", nargs="?", type=float, default=385)
    p.add_argument("box_w", nargs="?", type=float, default=285)
    p.add_argument("box_h", nargs="?", type=float, default=150)
    p.add_argument("--cell", type=float, default=1.5)
    p.add_argument("--scan-vox", type=int, default=1, help="XZ scan step in voxels (1=every voxel, 2=skip 1)")
    p.add_argument("--yaw", type=int, default=8); p.add_argument("--roll", type=int, default=4)
    p.add_argument("--pitch", type=int, default=4)
    p.add_argument("--output", type=str, default="packed_gpu_voxel.png")
    args = p.parse_args()
    box_dims = (args.box_l, args.box_w, args.box_h)
    cell = args.cell

    if not cuda.is_available():
        print("ERROR: CUDA not available"); sys.exit(1)

    if args.stl:
        fp = Path(args.stl)
        if not fp.exists(): print(f"ERROR: {fp}"); sys.exit(1)
        mesh = trimesh.load(str(fp), force='mesh')
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)])
        if mesh is None: print("ERROR"); sys.exit(1)
        print(f"Loaded: {fp.name}  {len(mesh.vertices)}v  {mesh.volume:.0f}mm3")
    else:
        v = np.array([[0,0,20],[0,0,0],[0,-20,0],[0,-20,20],[40,0,0],[40,-20,0]], dtype=np.float64)
        f = np.array([[0,1,2],[0,2,3],[4,0,5],[5,0,3],[1,4,2],[2,4,5],[4,1,0],[2,5,3]], dtype=np.int32)
        mesh = trimesh.Trimesh(vertices=v, faces=f); box_dims = (200, 200, 150)
        print("Built-in triangle")

    print(f"Generating orientations ({args.yaw}yaw x {args.roll}roll x {args.pitch}pitch, {cell}mm cells)...")
    t0 = time.time()
    orients = generate_orientations(mesh, cell, args.yaw, args.roll, args.pitch, box_dims)
    print(f"  {len(orients)} orientations ({time.time()-t0:.1f}s)")
    for o in orients[:6]: print(f"    {o['name']:>16s}  size={o['size'].round(1)}  occ={o['n_occ']}cells")

    print(f"\nPacking (GPU voxel)...")
    t0 = time.time()
    placed_meshes = pack(orients, box_dims, cell, scan_step_vox=args.scan_vox, verbose=True)
    print(f"\nVerifying...")
    ok = verify(placed_meshes)
    print(f"\nVisualizing...")
    visualize(placed_meshes, box_dims, args.output)
    print(f"\nTotal: {time.time()-t0:.0f}s, {len(placed_meshes)} pieces, {'PASS' if ok else 'FAIL'}")

if __name__ == "__main__":
    main()
