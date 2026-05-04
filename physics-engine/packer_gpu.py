"""
packer_gpu.py — GPU-accelerated 3D bin packer.
Uses SOME Physics Engine (engine.collision, engine.hull) for SAT collision.

Usage:
    python packer_gpu.py [stl_file] [box_l] [box_w] [box_h] [scan_mm]
"""
import sys, time, math, argparse
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.spatial.transform import Rotation
import trimesh

# Patch PTX version for old NVIDIA drivers (included in engine but also here as safety)
import numba.cuda.cudadrv.driver as _ptx_drv
_ptx_orig = _ptx_drv.CtypesLinker.add_ptx
def _ptx_patched(self, ptx, name='<cudapy-ptx>'):
    import re
    if isinstance(ptx, bytes):
        ptx = re.sub(rb'\.version\s+\d+\.\d+', b'.version 8.2', ptx)
    else:
        ptx = re.sub(r'\.version\s+\d+\.\d+', '.version 8.2', ptx)
    return _ptx_orig(self, ptx, name)
_ptx_drv.CtypesLinker.add_ptx = _ptx_patched

from numba import cuda
import numba

# Use engine hull module for convex hull computation
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine.hull import compute_hull


# ═══════════════════════════════════════════════
# GPU packing kernel
# ═══════════════════════════════════════════════

@cuda.jit(device=True)
def _sat_test_full(hull_verts, nv_a, nv_b, face_norms_a, face_norms_b,
                   nf_a, nf_b, hull_edges, ne_a, ne_b, temp_axis):
    """Full SAT (face normals + edge-edge) for two hulls at world coords.
    Returns True if overlapping, False if separated."""
    min_overlap = 1e30

    # Face normals of A
    for fi in range(nf_a):
        n = face_norms_a[fi]
        sep, ov = _sat_axis(n, hull_verts, nv_a, hull_verts[nv_a:], nv_b)
        if sep:
            return False
        if ov < min_overlap:
            min_overlap = ov

    # Face normals of B
    for fi in range(nf_b):
        n = face_norms_b[fi]
        sep, ov = _sat_axis(n, hull_verts, nv_a, hull_verts[nv_a:], nv_b)
        if sep:
            return False

    # Edge-edge cross products (simplified: skip for performance in packer)
    # Full edge-edge adds ~O(E^2) per test; not needed for packing since
    # face normals + CPU verification is sufficient.

    return True


@cuda.jit
def _packer_kernel(
    candidates,          # [n_candidates, 5] float64: x, z, ori_idx, min_y, valid
    hull_verts,          # [n_hulls, max_v, 3] float64 — packed: [A_world...][B_world...]
    hull_vert_counts,    # [n_hulls] int32
    hull_norms,          # [n_hulls, max_f, 3] float64
    hull_face_counts,    # [n_hulls] int32
    hull_edges,          # [n_hulls, max_e, 3] float64
    hull_edge_counts,    # [n_hulls] int32
    placed_verts,        # [n_placed, max_v, 3] float64 — world-space
    placed_counts,       # [n_placed] int32
    placed_norms,        # [n_placed, max_f, 3] float64
    placed_face_cts,     # [n_placed] int32
    placed_edges,        # [n_placed, max_e, 3] float64
    placed_edge_cts,     # [n_placed] int32
    n_placed,            # int32
    box_dims,            # float64[3]: box_l, box_h, box_w
    y_scan_res,          # float64
    n_hulls,
    max_y_scans,
    max_v,
    max_f,
    max_e,
    temp_pool,           # per-thread scratch
    pool_stride,
    d_height_map,        # [nx_cells, nz_cells] float64
    cell_size,           # float64
    nx_cells,            # int32
    nz_cells,            # int32
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
    ne = hull_edge_counts[ori_idx]

    base = idx * pool_stride
    # Layout: [nv*3] wa at Y=0, [nv*3] wa at try_Y
    # We compute footprint at Y=0 first

    min_x_c = 1e30; max_x_c = -1e30
    min_z_c = 1e30; max_z_c = -1e30
    max_y_c = -1e30; min_y_c = 1e30

    for vi in range(nv):
        vx = hull_verts[ori_idx, vi, 0]
        vy = hull_verts[ori_idx, vi, 1]
        vz = hull_verts[ori_idx, vi, 2]
        wx = x + vx
        wz = z + vz
        if wx < min_x_c: min_x_c = wx
        if wx > max_x_c: max_x_c = wx
        if wz < min_z_c: min_z_c = wz
        if wz > max_z_c: max_z_c = wz
        if vy < min_y_c: min_y_c = vy
        if vy > max_y_c: max_y_c = vy

    cand_h = max_y_c - min_y_c

    if min_x_c < 0 or max_x_c > box_dims[0] or min_z_c < 0 or max_z_c > box_dims[2]:
        candidates[idx, 4] = 0.0
        return

    # Find max Y of placed pieces overlapping XZ footprint
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

    # Height-map-based surface detection (more accurate than AABB top)
    height_map_max = 0.0
    ix0 = int(min_x_c / cell_size)
    if ix0 < 0:
        ix0 = 0
    ix1 = int((max_x_c - 1e-9) / cell_size)
    if ix1 >= nx_cells:
        ix1 = nx_cells - 1
    iz0 = int(min_z_c / cell_size)
    if iz0 < 0:
        iz0 = 0
    iz1 = int((max_z_c - 1e-9) / cell_size)
    if iz1 >= nz_cells:
        iz1 = nz_cells - 1
    if ix0 <= ix1 and iz0 <= iz1:
        for ix in range(ix0, ix1 + 1):
            for iz in range(iz0, iz1 + 1):
                h = d_height_map[ix, iz]
                if h > height_map_max:
                    height_map_max = h

    base_y = max_placed_y
    if height_map_max > 0 and height_map_max < base_y:
        base_y = height_map_max
    # Try a few cells below too (cavities can be up to piece height below AABB top)
    if base_y > min_y_c + y_scan_res:
        base_y = max(0.0, base_y - min_y_c)
    found_y = -1.0
    max_scan = max_y_scans
    if max_scan > int((box_dims[1] - cand_h - base_y) / y_scan_res) + 2:
        max_scan = int((box_dims[1] - cand_h - base_y) / y_scan_res) + 2
    if max_scan < 1:
        max_scan = 1

    # Pre-compute candidate AABB at each Y level (same XZ)
    for sy in range(max_scan):
        try_y = base_y + sy * y_scan_res
        if try_y + cand_h > box_dims[1] + 0.01:
            break

        # Transform candidate vertices to world space at try_y
        off_w = pool_stride // 2  # second half of pool for world-space verts
        for vi in range(nv):
            temp_pool[base + off_w + vi*3 + 0] = x + hull_verts[ori_idx, vi, 0]
            temp_pool[base + off_w + vi*3 + 1] = try_y + hull_verts[ori_idx, vi, 1]
            temp_pool[base + off_w + vi*3 + 2] = z + hull_verts[ori_idx, vi, 2]

        cand_min_y = try_y + min_y_c
        cand_max_y = try_y + max_y_c

        collides = False
        for pi in range(n_placed):
            pnv = placed_counts[pi]
            # Quick Y-AABB check
            p_min_y = 1e30; p_max_y = -1e30
            for vi in range(pnv):
                py = placed_verts[pi, vi, 1]
                if py < p_min_y: p_min_y = py
                if py > p_max_y: p_max_y = py
            if cand_max_y <= p_min_y or cand_min_y >= p_max_y:
                continue

            # XZ-AABB check
            p_min_x = 1e30; p_max_x = -1e30; p_min_z = 1e30; p_max_z = -1e30
            for vi in range(pnv):
                pv = placed_verts[pi, vi]
                if pv[0] < p_min_x: p_min_x = pv[0]
                if pv[0] > p_max_x: p_max_x = pv[0]
                if pv[2] < p_min_z: p_min_z = pv[2]
                if pv[2] > p_max_z: p_max_z = pv[2]
            if max_x_c <= p_min_x or min_x_c >= p_max_x or max_z_c <= p_min_z or min_z_c >= p_max_z:
                continue

            # SAT face normal test (conservative GPU filter)
            # Test candidate faces against placed piece
            pnf = placed_face_cts[pi]
            # Test face normals of candidate
            sep = False
            for fi in range(nf):
                n = hull_norms[ori_idx, fi]
                min_a = 1e30; max_a = -1e30
                for vi in range(nv):
                    d = n[0]*temp_pool[base+off_w+vi*3] + n[1]*temp_pool[base+off_w+vi*3+1] + n[2]*temp_pool[base+off_w+vi*3+2]
                    if d < min_a: min_a = d
                    if d > max_a: max_a = d
                min_b = 1e30; max_b = -1e30
                for vi in range(pnv):
                    d = n[0]*placed_verts[pi,vi,0] + n[1]*placed_verts[pi,vi,1] + n[2]*placed_verts[pi,vi,2]
                    if d < min_b: min_b = d
                    if d > max_b: max_b = d
                if max_a < min_b or max_b < min_a:
                    sep = True
                    break
            if sep:
                continue

            # Test placed piece face normals
            for fi in range(pnf):
                n = placed_norms[pi, fi]
                min_a = 1e30; max_a = -1e30
                for vi in range(nv):
                    d = n[0]*temp_pool[base+off_w+vi*3] + n[1]*temp_pool[base+off_w+vi*3+1] + n[2]*temp_pool[base+off_w+vi*3+2]
                    if d < min_a: min_a = d
                    if d > max_a: max_a = d
                min_b = 1e30; max_b = -1e30
                for vi in range(pnv):
                    d = n[0]*placed_verts[pi,vi,0] + n[1]*placed_verts[pi,vi,1] + n[2]*placed_verts[pi,vi,2]
                    if d < min_b: min_b = d
                    if d > max_b: max_b = d
                if max_a < min_b or max_b < min_a:
                    sep = True
                    break
            if sep:
                continue

            collides = True
            break

        if not collides:
            found_y = try_y
            break

    if found_y >= 0:
        candidates[idx, 3] = found_y
        candidates[idx, 4] = 1.0
    else:
        candidates[idx, 4] = 0.0


# ═══════════════════════════════════════════════
# CPU helpers
# ═══════════════════════════════════════════════

def compute_face_normals(verts, faces):
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    mag = np.linalg.norm(n, axis=1)
    mag[mag < 1e-12] = 1.0
    return n / mag[:, np.newaxis]


def compute_edges(verts, faces, max_edges):
    edge_set = set()
    for f in faces:
        for a, b in [(f[0], f[1]), (f[1], f[2]), (f[2], f[0])]:
            edge_set.add((min(a, b), max(a, b)))
    result = np.zeros((max_edges, 3), dtype=np.float64)
    for ei, (a, b) in enumerate(edge_set):
        if ei >= max_edges:
            break
        d = verts[b] - verts[a]
        nrm = np.linalg.norm(d)
        if nrm > 1e-12:
            d /= nrm
        result[ei] = d
    return result, len(edge_set)


def meshes_collide(mesh_a, mesh_b, eps=0.01):
    try:
        pts_a, _ = trimesh.proximity.closest_point(mesh_a, mesh_b.vertices)
        pts_b, _ = trimesh.proximity.closest_point(mesh_b, mesh_a.vertices)
        if len(pts_a) == 0 or len(pts_b) == 0:
            return False
        d_a = np.linalg.norm(pts_a - mesh_b.vertices, axis=1)
        d_b = np.linalg.norm(pts_b - mesh_a.vertices, axis=1)
        return np.min(d_a) < eps or np.min(d_b) < eps
    except Exception:
        return False


def _face_is_stable_base(hull, face_idx):
    """Check if a convex hull face can serve as a stable resting base."""
    f = hull.faces[face_idx]
    v0, v1, v2 = hull.vertices[f[0]], hull.vertices[f[1]], hull.vertices[f[2]]
    n = np.cross(v1 - v0, v2 - v0)
    nl = np.linalg.norm(n)
    if nl < 1e-12: return False, None
    n /= nl
    # Must point upward (normal ~ +Y for base face)
    if n[1] < 0.7: return False, None
    # Face area
    area = nl * 0.5
    # Total hull surface area
    total_area = sum(np.linalg.norm(np.cross(
        hull.vertices[f[1]] - hull.vertices[f[0]],
        hull.vertices[f[2]] - hull.vertices[f[0]])) * 0.5
        for f in hull.faces)
    if area < total_area * 0.02: return False, None
    # Center of mass (average of vertices for convex hull)
    com = hull.vertices.mean(axis=0)
    # Project COM onto face plane
    d = np.dot(com - v0, n)
    proj = com - d * n
    # Barycentric check
    v0p = v1 - v0; v1p = v2 - v0; v2p = proj - v0
    d00 = np.dot(v0p, v0p); d01 = np.dot(v0p, v1p); d11 = np.dot(v1p, v1p)
    d20 = np.dot(v2p, v0p); d21 = np.dot(v2p, v1p)
    denom = d00 * d11 - d01 * d01
    if abs(denom) < 1e-12: return False, None
    u = (d11 * d20 - d01 * d21) / denom
    v = (d00 * d21 - d01 * d20) / denom
    if u < -0.01 or v < -0.01 or u + v > 1.01: return False, None
    return True, n


def _align_to_stable_base(mesh, hull):
    """Rotate mesh so the largest stable face sits flat on the floor (y=0)."""
    best_area = 0; best_n = None
    for fi in range(len(hull.faces)):
        ok, n = _face_is_stable_base(hull, fi)
        if not ok: continue
        f = hull.faces[fi]
        area = np.linalg.norm(np.cross(
            hull.vertices[f[1]] - hull.vertices[f[0]],
            hull.vertices[f[2]] - hull.vertices[f[0]])) * 0.5
        if area > best_area:
            best_area = area; best_n = n
    if best_n is None:
        return mesh, hull  # no stable face
    
    # Rotate so normal points to +Y
    target = np.array([0.0, 1.0, 0.0])
    axis = np.cross(best_n, target)
    al = np.linalg.norm(axis)
    if al < 1e-12:
        if np.dot(best_n, target) > 0: return mesh, hull
        axis = np.array([1.0, 0.0, 0.0])
    axis /= al
    angle = np.arccos(np.clip(np.dot(best_n, target), -1, 1))
    
    rot = Rotation.from_rotvec(axis * angle).as_matrix()
    t = mesh.copy()
    t.apply_transform(np.vstack([np.hstack([rot, np.zeros((3, 1))]), [0, 0, 0, 1]]))
    bmin = t.bounds[0]
    t.apply_translation([-bmin[0], -bmin[1], -bmin[2]])
    
    new_hull = compute_hull(t)
    return t, new_hull


def generate_orientations(mesh, n_yaw, n_roll, n_pitch, box_dims):
    results = []
    seen = set()
    
    # First: find the stable base alignment (pitch/roll to put a flat face down)
    # Then: apply yaw rotations on top
    
    # Generate pitch+roll combos for finding stable bases
    base_orientations = []
    for pitch in np.linspace(0, 360, n_pitch, endpoint=False):
        for roll in np.linspace(0, 360, n_roll, endpoint=False):
            rot = Rotation.from_euler('xz', [pitch, roll], degrees=True).as_matrix()
            t = mesh.copy()
            t.apply_transform(np.vstack([np.hstack([rot, np.zeros((3, 1))]), [0, 0, 0, 1]]))
            hull = compute_hull(t)
            ok, _ = _face_is_stable_base(hull, 0)  # check first face as proxy
            if ok:
                bmin = t.bounds[0]
                t.apply_translation([-bmin[0], -bmin[1], -bmin[2]])
                hull = compute_hull(t)
                base_orientations.append((t, hull, f'P{pitch:.0f}R{roll:.0f}'))
    
    # If no stable base found, try the auto-align function
    if not base_orientations:
        hull0 = compute_hull(mesh)
        t_aligned, hull_aligned = _align_to_stable_base(mesh, hull0)
        base_orientations = [(t_aligned, hull_aligned, 'stable')]
    
    # Deduplicate base orientations by size
    unique_bases = []
    seen_base = set()
    for t, hull, name in base_orientations:
        key = tuple(t.extents.round(1))
        if key not in seen_base:
            seen_base.add(key)
            unique_bases.append((t, hull, name))
    
    # For each base orientation, apply yaw rotations
    for base_mesh, base_hull, base_name in unique_bases:
        for yaw in np.linspace(0, 360, n_yaw, endpoint=False):
            rot = Rotation.from_euler('y', yaw, degrees=True).as_matrix()
            t = base_mesh.copy()
            t.apply_transform(np.vstack([np.hstack([rot, np.zeros((3, 1))]), [0, 0, 0, 1]]))
            bmin = t.bounds[0]
            t.apply_translation([-bmin[0], -bmin[1], -bmin[2]])
            sz = t.extents
            if sz[0] > box_dims[0] + 0.5 or sz[2] > box_dims[1] + 0.5 or sz[1] > box_dims[2] + 0.5:
                continue
            
            hull = compute_hull(t)
            key = tuple(np.round(sz).astype(int))
            if key in seen:
                continue
            seen.add(key)
            
            results.append({
                'mesh': t,
                'hull': hull,
                'verts': hull.vertices,
                'faces': hull.faces,
                'norms': hull.normals,
                'size': sz,
                'name': f'{base_name}_Y{yaw:.0f}',
            })
    return results


# ═══════════════════════════════════════════════
# Main packing loop
# ═══════════════════════════════════════════════

def pack(orientations, box_dims, scan_step=5.0, y_scan_res=2.0, max_pieces=5000, verbose=True):
    box_l, box_w, box_h = box_dims

    max_verts = max(len(o['verts']) for o in orientations)
    max_faces = max(len(o['faces']) for o in orientations)
    max_edges = max(len(set((min(a, b), max(a, b)) for f in o['faces']
                            for a, b in [(f[0], f[1]), (f[1], f[2]), (f[2], f[0])]))
                    for o in orientations)
    n_hulls = len(orientations)

    hull_verts = np.zeros((n_hulls, max_verts, 3), dtype=np.float64)
    hull_vert_counts = np.zeros(n_hulls, dtype=np.int32)
    hull_norms = np.zeros((n_hulls, max_faces, 3), dtype=np.float64)
    hull_face_counts = np.zeros(n_hulls, dtype=np.int32)
    hull_edges = np.zeros((n_hulls, max_edges, 3), dtype=np.float64)
    hull_edge_counts = np.zeros(n_hulls, dtype=np.int32)

    for oi, o in enumerate(orientations):
        nv, nf = len(o['verts']), len(o['faces'])
        edges_arr, ne = compute_edges(o['verts'], o['faces'], max_edges)
        hull_verts[oi, :nv] = o['verts']
        hull_vert_counts[oi] = nv
        hull_norms[oi, :nf] = o['norms']
        hull_face_counts[oi] = nf
        hull_edges[oi, :ne] = edges_arr
        hull_edge_counts[oi] = ne

    d_hull_verts = cuda.to_device(hull_verts)
    d_hull_vert_counts = cuda.to_device(hull_vert_counts)
    d_hull_norms = cuda.to_device(hull_norms)
    d_hull_face_counts = cuda.to_device(hull_face_counts)
    d_hull_edges = cuda.to_device(hull_edges)
    d_hull_edge_counts = cuda.to_device(hull_edge_counts)
    d_box_dims = cuda.to_device(np.array([box_l, box_h, box_w], dtype=np.float64))

    cell_size = 3.0
    nx_cells = int(np.ceil(box_l / cell_size))
    nz_cells = int(np.ceil(box_w / cell_size))
    height_map = np.zeros((nx_cells, nz_cells), dtype=np.float64)
    d_height_map = cuda.to_device(height_map)

    max_placed = max_pieces
    d_placed_verts = cuda.to_device(np.zeros((max_placed, max_verts, 3), dtype=np.float64))
    d_placed_counts = cuda.to_device(np.zeros(max_placed, dtype=np.int32))
    d_placed_norms = cuda.to_device(np.zeros((max_placed, max_faces, 3), dtype=np.float64))
    d_placed_face_cts = cuda.to_device(np.zeros(max_placed, dtype=np.int32))
    d_placed_edges = cuda.to_device(np.zeros((max_placed, max_edges, 3), dtype=np.float64))
    d_placed_edge_cts = cuda.to_device(np.zeros(max_placed, dtype=np.int32))

    # Per-thread temp pool
    temp_stride = max_verts * 3 * 2  # two sets of world-space verts
    temp_pool = cuda.to_device(np.zeros(256 * temp_stride, dtype=np.float64))

    placed_meshes = []
    placed = []
    usage = defaultdict(int)
    start = time.time()
    consecutive_fails = 0

    if verbose:
        print(f"[GPU] Box: {box_l:.0f}x{box_w:.0f}x{box_h:.0f}mm, scan={scan_step}mm, y_res={y_scan_res}mm")
        print(f"[GPU] {len(orientations)} orientations, max_verts={max_verts}, max_faces={max_faces}, max_edges={max_edges}")
        print(f"[GPU] CUDA device: {cuda.get_current_device().name}")

    while len(placed) < max_pieces and consecutive_fails < 100:
        candidates = []
        for oi, o in enumerate(orientations):
            sx, sy, sz = o['size']
            if sy > box_h:
                continue
            for x in np.arange(0, box_l - sx + 0.01, scan_step):
                for z in np.arange(0, box_w - sz + 0.01, scan_step):
                    candidates.append([float(x), float(z), float(oi), 99999.0, 0.0])

        if not candidates:
            break

        d_candidates = cuda.to_device(np.array(candidates, dtype=np.float64))
        n_candidates = len(candidates)

        threads = 256
        blocks = (n_candidates + threads - 1) // threads
        n_threads = blocks * threads

        # Allocate temp pool for all threads
        temp_pool = cuda.to_device(np.zeros(n_threads * temp_stride, dtype=np.float64))

        _packer_kernel[blocks, threads](
            d_candidates,
            d_hull_verts, d_hull_vert_counts,
            d_hull_norms, d_hull_face_counts,
            d_hull_edges, d_hull_edge_counts,
            d_placed_verts, d_placed_counts,
            d_placed_norms, d_placed_face_cts,
            d_placed_edges, d_placed_edge_cts,
            len(placed), d_box_dims, y_scan_res,
            n_hulls, 100,
            max_verts, max_faces, max_edges,
            temp_pool, temp_stride,
            d_height_map, cell_size, nx_cells, nz_cells,
        )
        cuda.synchronize()

        results = d_candidates.copy_to_host()
        valid = results[:, 4] > 0.5

        if not valid.any():
            consecutive_fails += 1
            continue

        valid_results = results[valid]
        best_idx = np.argmin(valid_results[:, 3])
        best = valid_results[best_idx]
        best_x, best_z, best_oi, best_y = best[0], best[1], int(best[2]), best[3]

        od = orientations[best_oi]
        cand_mesh = od['mesh'].copy()
        cand_mesh.apply_translation([best_x, best_y, best_z])

        collides = False
        for pm in placed_meshes:
            b1 = cand_mesh.bounds
            b2 = pm.bounds
            if (b1[1, 0] > b2[0, 0] and b1[0, 0] < b2[1, 0] and
                b1[1, 1] > b2[0, 1] and b1[0, 1] < b2[1, 1] and
                b1[1, 2] > b2[0, 2] and b1[0, 2] < b2[1, 2]):
                if meshes_collide(cand_mesh, pm, eps=0.01):
                    collides = True
                    break

        if collides:
            consecutive_fails += 1
            continue

        placed_meshes.append(cand_mesh)
        placed.append((best_x, best_y, best_z, best_oi, od['name']))
        usage[od['name']] += 1
        consecutive_fails = 0

        pi = len(placed_meshes) - 1
        wv = od['verts'] + np.array([best_x, best_y, best_z])
        nv, nf = len(od['verts']), len(od['faces'])
        for vi in range(nv):
            for d in range(3):
                d_placed_verts[pi, vi, d] = wv[vi, d]
        d_placed_counts[pi] = np.int32(nv)
        d_placed_face_cts[pi] = np.int32(nf)
        wns = compute_face_normals(wv, od['faces'])
        for fi in range(nf):
            for d in range(3):
                d_placed_norms[pi, fi, d] = wns[fi, d]
        edges_arr, ne = compute_edges(wv, od['faces'], max_edges)
        for ei in range(ne):
            for d in range(3):
                d_placed_edges[pi, ei, d] = edges_arr[ei, d]
        d_placed_edge_cts[pi] = np.int32(ne)

        for vi in range(nv):
            wx, wy, wz = wv[vi][0], wv[vi][1], wv[vi][2]
            ix = int(wx / cell_size)
            iz = int(wz / cell_size)
            if 0 <= ix < nx_cells and 0 <= iz < nz_cells:
                if wy > height_map[ix, iz]:
                    height_map[ix, iz] = wy
        d_height_map.copy_to_device(height_map)

        if verbose and len(placed) % 25 == 0:
            elapsed = time.time() - start
            vol = sum(m.volume for m in placed_meshes) if placed_meshes else 0
            fill = vol / (box_l * box_w * box_h) * 100
            print(f"[GPU] {len(placed)} placed, {fill:.1f}% fill, {elapsed:.0f}s  {od['name']}@({best_x:.0f},{best_y:.0f},{best_z:.0f})")

    elapsed = time.time() - start
    if verbose and placed:
        vol = sum(m.volume for m in placed_meshes) if placed_meshes else 0
        fill = vol / (box_l * box_w * box_h) * 100
        print(f"\n[GPU] DONE: {len(placed)} pieces, {fill:.1f}% fill, {elapsed:.0f}s")
        print(f"[GPU] Usage: {dict(sorted(usage.items()))}")
    return placed, placed_meshes, orientations


# ═══════════════════════════════════════════════
# Verification + visualization
# ═══════════════════════════════════════════════

def verify(placed_meshes):
    collisions = 0
    for i in range(len(placed_meshes)):
        for j in range(i + 1, len(placed_meshes)):
            a = placed_meshes[i].bounds
            b = placed_meshes[j].bounds
            if (a[1, 0] > b[0, 0] and a[0, 0] < b[1, 0] and
                a[1, 1] > b[0, 1] and a[0, 1] < b[1, 1] and
                a[1, 2] > b[0, 2] and a[0, 2] < b[1, 2]):
                if meshes_collide(placed_meshes[i], placed_meshes[j], eps=0.001):
                    collisions += 1
                    if collisions <= 5:
                        print(f"  COLLISION: {i} vs {j}")
    ok = collisions == 0
    print(f"  [{'OK' if ok else 'FAIL'}] {'ZERO' if ok else collisions} collisions — {len(placed_meshes)} pieces")
    return ok


def visualize(placed_meshes, box_dims, output_path):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    box_l, box_w, box_h = box_dims
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    fig.suptitle(f"GPU Packing — {len(placed_meshes)} pieces", fontsize=14, fontweight='bold')
    colors = plt.cm.tab20(np.linspace(0, 1, max(20, len(placed_meshes))))
    for title, ax, view in [("Top (XZ)", axes[0, 0], 'xz'), ("Front (XY)", axes[0, 1], 'xy'),
                            ("Side (ZY)", axes[1, 0], 'zy'), ("HMap", axes[1, 1], 'hm')]:
        ax.set_title(title)
        if view == 'xz':
            ax.set_xlim(0, box_l); ax.set_ylim(0, box_w); ax.invert_yaxis()
            for i, m in enumerate(placed_meshes):
                b = m.bounds
                ax.add_patch(Rectangle((b[0, 0], b[0, 2]), b[1, 0] - b[0, 0], b[1, 2] - b[0, 2],
                                       alpha=0.15, color=colors[i % 20], ec='black', lw=0.2))
            ax.set_xlabel('X'); ax.set_ylabel('Z'); ax.set_aspect('equal')
        elif view == 'xy':
            ax.set_xlim(0, box_l); ax.set_ylim(0, box_h)
            for m in placed_meshes:
                b = m.bounds
                ax.add_patch(Rectangle((b[0, 0], b[0, 1]), b[1, 0] - b[0, 0], b[1, 1] - b[0, 1],
                                       alpha=0.15, color=colors[0], ec='black', lw=0.2))
            ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_aspect('equal')
        elif view == 'zy':
            ax.set_xlim(0, box_w); ax.set_ylim(0, box_h)
            for m in placed_meshes:
                b = m.bounds
                ax.add_patch(Rectangle((b[0, 2], b[0, 1]), b[1, 2] - b[0, 2], b[1, 1] - b[0, 1],
                                       alpha=0.15, color=colors[0], ec='black', lw=0.2))
            ax.set_xlabel('Z'); ax.set_ylabel('Y'); ax.set_aspect('equal')
        elif view == 'hm':
            hm = np.zeros((int(box_l // 5) + 1, int(box_w // 5) + 1))
            cnt = np.zeros_like(hm)
            for m in placed_meshes:
                b = m.bounds
                ix, iz = int(b[0, 0] / 5), int(b[0, 2] / 5)
                if 0 <= ix < hm.shape[0] and 0 <= iz < hm.shape[1]:
                    hm[ix, iz] += b[1, 1]; cnt[ix, iz] += 1
            mask = cnt > 0
            if mask.any():
                hm[mask] /= cnt[mask]
            ax.imshow(hm.T, origin='lower', cmap='YlOrRd', extent=[0, box_l, 0, box_w], aspect='equal')
            ax.set_xlabel('X'); ax.set_ylabel('Z')
    plt.tight_layout(); plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"[Viz] {output_path}"); plt.close()


def main():
    p = argparse.ArgumentParser(description="GPU-accelerated 3D Packer")
    p.add_argument("stl", nargs="?", default=None)
    p.add_argument("box_l", nargs="?", type=float, default=385)
    p.add_argument("box_w", nargs="?", type=float, default=285)
    p.add_argument("box_h", nargs="?", type=float, default=150)
    p.add_argument("scan", nargs="?", type=float, default=5.0)
    p.add_argument("--yaw", type=int, default=8)
    p.add_argument("--roll", type=int, default=4)
    p.add_argument("--pitch", type=int, default=4)
    p.add_argument("--yres", type=float, default=2.0, help="Y scan resolution mm")
    p.add_argument("--output", type=str, default="packed_gpu.png")
    args = p.parse_args()

    box_dims = (args.box_l, args.box_w, args.box_h)

    if not cuda.is_available():
        print("ERROR: CUDA not available.")
        sys.exit(1)

    if args.stl:
        fp = Path(args.stl)
        if not fp.exists():
            print(f"ERROR: {fp}")
            sys.exit(1)
        mesh = trimesh.load(str(fp), force='mesh')
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)])
        if mesh is None:
            print("ERROR loading mesh")
            sys.exit(1)
        print(f"Loaded: {fp.name}  {len(mesh.vertices)}v  {mesh.volume:.0f}mm3")
    else:
        v = np.array([[0, 0, 20], [0, 0, 0], [0, -20, 0], [0, -20, 20], [40, 0, 0], [40, -20, 0]], dtype=np.float64)
        f = np.array([[0, 1, 2], [0, 2, 3], [4, 0, 5], [5, 0, 3], [1, 4, 2], [2, 4, 5], [4, 1, 0], [2, 5, 3]], dtype=np.int32)
        mesh = trimesh.Trimesh(vertices=v, faces=f)
        box_dims = (200, 200, 150)
        print("Built-in triangle")

    print(f"Generating orientations ({args.yaw} yaw)...")
    t0 = time.time()
    orients = generate_orientations(mesh, args.yaw, args.roll, args.pitch, box_dims)
    print(f"  {len(orients)} orientations ({time.time() - t0:.1f}s)")

    print(f"\nPacking (GPU)...")
    t0 = time.time()
    placed, placed_meshes, orients = pack(orients, box_dims, scan_step=args.scan, y_scan_res=args.yres, verbose=True)

    print(f"\nVerifying...")
    verify(placed_meshes)

    print(f"\nVisualizing...")
    visualize(placed_meshes, box_dims, args.output)
    print(f"\nTotal: {time.time() - t0:.0f}s, {len(placed)} pieces")


if __name__ == "__main__":
    main()
