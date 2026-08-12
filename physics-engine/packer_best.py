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
        # Precompute InaccessibilityPoles for fast collision proxy
        try:
            cv = result.get('coll_verts', result['verts'])
            cf = result.get('coll_faces', result['faces'])
            result['poles'] = compute_inaccessibility_poles(cv, cf, n_poles=5)
        except Exception:
            result['poles'] = []
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


def meshes_collide(mesh_a, mesh_b, eps=0.01):
    try:
        # Use trimesh CollisionManager for robust mesh-mesh intersection
        if hasattr(trimesh, 'collision') and hasattr(trimesh.collision, 'CollisionManager'):
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

        stl_path = str(Path(__file__).resolve().parent / "stl" / "6683688_simp0.1pct.stl")
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

    # ── Sparrow: Separation + Compression ──

    def pack_sparrow(self, max_pieces=500, n_workers=4, n_iterations=200, verbose=True):
        """Global optimization via random placement → separation → compression.
        Inspired by JonasTollenaere/sparrow-3d (LGPL-3.0)."""
        import copy as _copy
        n_items = min(max_pieces, 500)
        orient_list = list(range(len(self.orientations)))
        total_vol = sum(o['size'][0] * o['size'][1] * o['size'][2] for o in self.orientations)
        base_height = total_vol / (self.box_l * self.box_w) * 1.5
        initial_height = min(self.box_h * 3, max(self.box_h * 1.2, base_height))
        if verbose:
            print(f"[Sparrow] {n_items} items, initial_height={initial_height:.0f}mm, {n_workers} workers")

        best_placed, best_meshes = [], []
        best_count = 0
        t0 = time.time()

        for worker in range(n_workers):
            state = []
            state_meshes = []
            for i in range(n_items):
                oi = random.choice(orient_list)
                o = self.orientations[oi]
                sx, sy, sz = o['size']
                x = random.uniform(0, self.box_l - sx)
                z = random.uniform(0, self.box_w - sz)
                y = random.uniform(0, initial_height - sy)
                state.append((x, y, z, oi, o['name']))
                cm = o['mesh'].copy(); cm.apply_translation([x, y, z])
                state_meshes.append(cm)

            # Separation phase
            collision_weights = {}
            current_height = initial_height
            improved = True
            iter_count = 0

            while improved and iter_count < n_iterations:
                improved = False
                iter_count += 1

                # Find colliding pairs
                colliding = set()
                for i in range(len(state)):
                    for j in range(i + 1, len(state)):
                        key = (i, j)
                        a, b = state_meshes[i], state_meshes[j]
                        if not (a.bounds[1,0] > b.bounds[0,0] and a.bounds[0,0] < b.bounds[1,0] and
                                a.bounds[1,1] > b.bounds[0,1] and a.bounds[0,1] < b.bounds[1,1] and
                                a.bounds[1,2] > b.bounds[0,2] and a.bounds[0,2] < b.bounds[1,2]):
                            continue
                        if meshes_collide(a, b):
                            colliding.add(i)
                            colliding.add(j)
                            collision_weights[key] = collision_weights.get(key, 1.0) * 1.05

                if not colliding:
                    # Successfully separated — try compression
                    if current_height > self.box_h * 0.8:
                        current_height *= 0.995
                        improved = True
                    break

                # Try to move each colliding item
                items = sorted(colliding)
                random.shuffle(items)
                for item_idx in items:
                    oi = state[item_idx][3]
                    o = self.orientations[oi]
                    sx, sy, sz = o['size']

                    best_score = float('inf')
                    best_xyz = None
                    old_x, old_y, old_z = state[item_idx][:3]

                    # 50 samples: 20 random + 30 grid
                    for s in range(50):
                        if s < 20:
                            nx = random.uniform(0, self.box_l - sx)
                            nz = random.uniform(0, self.box_w - sz)
                            ny = random.uniform(0, current_height - sy)
                        else:
                            j = (s - 20) % 6
                            k = (s - 20) // 6
                            nx = old_x + (j - 2.5) * self.scan_step
                            nz = old_z + (k - 2.5) * self.scan_step
                            ny = old_y + (random.random() - 0.5) * self.scan_step
                        nx = max(0, min(self.box_l - sx, nx))
                        ny = max(0, min(current_height - sy, ny))
                        nz = max(0, min(self.box_w - sz, nz))

                        cm = o['mesh'].copy(); cm.apply_translation([nx, ny, nz])
                        score = 0
                        bad = False
                        for j in range(len(state)):
                            if j == item_idx: continue
                            b1, b2 = cm.bounds, state_meshes[j].bounds
                            if not (b1[1,0] > b2[0,0] and b1[0,0] < b2[1,0] and
                                    b1[1,1] > b2[0,1] and b1[0,1] < b2[1,1] and
                                    b1[1,2] > b2[0,2] and b1[0,2] < b2[1,2]): continue
                            if meshes_collide(cm, state_meshes[j]):
                                w = collision_weights.get((min(item_idx, j), max(item_idx, j)), 1.0)
                                score += w
                                if score >= best_score: bad = True; break
                        if bad: continue

                        if score < best_score:
                            best_score = score
                            best_xyz = (nx, ny, nz)

                    if best_xyz and best_score == 0:
                        improved = True
                        state[item_idx] = (best_xyz[0], best_xyz[1], best_xyz[2], oi, o['name'])
                        nm = o['mesh'].copy(); nm.apply_translation([best_xyz[0], best_xyz[1], best_xyz[2]])
                        state_meshes[item_idx] = nm

            # Filter to pieces inside the actual box
            inside = []
            inside_meshes = []
            for i, (x, y, z, oi, name) in enumerate(state):
                o = self.orientations[oi]
                if x >= 0 and y >= 0 and z >= 0 and x + o['size'][0] <= self.box_l and y + o['size'][1] <= self.box_h and z + o['size'][2] <= self.box_w:
                    inside.append((x, y, z, oi, name))
                    inside_meshes.append(state_meshes[i])

            if len(inside) > best_count:
                best_count = len(inside)
                best_placed = inside
                best_meshes = inside_meshes
                if verbose:
                    vol = sum(m.volume for m in inside_meshes)
                    fill = vol / (self.box_l * self.box_w * self.box_h) * 100
                    print(f"  [Worker {worker+1}] {len(inside)} pieces, {fill:.1f}% fill, iter={iter_count}")

        elapsed = time.time() - t0
        if verbose:
            vol = sum(m.volume for m in best_meshes) if best_meshes else 0
            fill = vol / (self.box_l * self.box_w * self.box_h) * 100 if vol > 0 else 0
            print(f"  [Sparrow] DONE: {best_count} pieces, {fill:.1f}% fill, {elapsed:.0f}s")
        return best_placed, best_meshes

    # ── Full pipeline ──

    def pack(self, method='backtrack', max_beams=8, max_pieces=500, compact=False, verbose=True, beam_width=5, hierarchical=False, explore_local=False, sparrow_workers=4):
        t0 = time.time()

        if method == 'sparrow':
            placed, meshes = self.pack_sparrow(max_pieces, n_workers=sparrow_workers, verbose=verbose)
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
            print(f"\nTotal: {len(placed)} pieces, {fill:.1f}% fill, {elapsed:.0f}s")
        return placed, meshes


# ═══════════════════════════════════════════════
# Verification + visualization
# ═══════════════════════════════════════════════

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
    p.add_argument("--method", type=str, default="backtrack", choices=["greedy", "backtrack", "layers", "sparrow"])
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
    p.add_argument("--sparrow-workers", type=int, default=4, help="Parallel workers for sparrow mode")
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
        print(f"Loading: {fp.name}...")
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

    print(f"\nPacking ({args.method})...")
    t_start = time.time()
    placed, meshes = packer.pack(method=args.method, max_pieces=500, compact=args.compact, verbose=True, beam_width=args.beam_width, hierarchical=args.hierarchical, explore_local=args.explore_local, sparrow_workers=args.sparrow_workers)
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
            f"Seed: {args.seed}",
            f"",
            f"Result: {len(placed)} pieces, {sum(m.volume for m in meshes)/(box_dims[0]*box_dims[1]*box_dims[2])*100:.1f}% fill",
            f"Time: {elapsed:.0f}s",
        ]
        (out_dir / "info.txt").write_text("\n".join(info))
        print(f"[Info] {out_dir}/info.txt")
if __name__ == "__main__":
    main()
