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

    def load_mesh(self, stl_path, n_yaw=8, shrink=0.4):
        fp = Path(stl_path)
        mesh = trimesh.load(str(fp), force='mesh')
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)])
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

    def _generate_candidates(self):
        cands = []
        for oi, o in enumerate(self.orientations):
            sx, _, sz = o['size']
            for x in np.arange(0, self.box_l - sx + 0.01, self.scan_step):
                for z in np.arange(0, self.box_w - sz + 0.01, self.scan_step):
                    cands.append([float(x), float(z), float(oi), 99999.0, 0.0])
        return np.array(cands, dtype=np.float64) if cands else np.zeros((0, 5), dtype=np.float64)

    def _gpu_scan(self, n_placed, verbose=False):
        """One GPU launch: find min Y for all candidates. Returns valid candidates with Y."""
        cand_array = self._generate_candidates()
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

    def pack_greedy(self, max_pieces=500, verbose=True, beam_width=5):
        placed, meshes = [], []
        consecutive = 0
        t0 = time.time()

        while len(placed) < max_pieces and consecutive < 20:
            valid = self._gpu_scan(len(placed))
            if len(valid) == 0:
                consecutive += 1
                continue

            top_n = min(beam_width, len(valid))
            top = valid[np.argsort(valid[:, 3])[:top_n]]
            best = top[random.randint(0, len(top) - 1)]
            x, z, oi, y = best[0], best[1], int(best[2]), best[3]
            o = self.orientations[oi]

            cm = o['mesh'].copy(); cm.apply_translation([x, y, z])
            collides = False
            for pm in meshes:
                b1, b2 = cm.bounds, pm.bounds
                if (b1[1, 0] > b2[0, 0] and b1[0, 0] < b2[1, 0] and
                    b1[1, 1] > b2[0, 1] and b1[0, 1] < b2[1, 1] and
                    b1[1, 2] > b2[0, 2] and b1[0, 2] < b2[1, 2]):
                    if meshes_collide(cm, pm): collides = True; break
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
                    collides = False
                    for pm in sub_meshes:
                        b1, b2 = cm.bounds, pm.bounds
                        if (b1[1, 0] > b2[0, 0] and b1[0, 0] < b2[1, 0] and
                            b1[1, 1] > b2[0, 1] and b1[0, 1] < b2[1, 1] and
                            b1[1, 2] > b2[0, 2] and b1[0, 2] < b2[1, 2]):
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
            collides = False
            for pm in existing_meshes + lm:
                b1, b2 = cm.bounds, pm.bounds
                if (b1[1,0] > b2[0,0] and b1[0,0] < b2[1,0] and
                    b1[1,1] > b2[0,1] and b1[0,1] < b2[1,1] and
                    b1[1,2] > b2[0,2] and b1[0,2] < b2[1,2]):
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

    # ── Full pipeline ──

    def pack(self, method='backtrack', max_beams=8, max_pieces=500, compact=False, verbose=True, beam_width=5):
        t0 = time.time()

        if method == 'greedy':
            placed, meshes = self.pack_greedy(max_pieces, verbose, beam_width=beam_width)
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

    # ── 2. 3D wireframe view ──
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

    # Plot each piece as a scatter of its vertices
    for i, m in enumerate(placed_meshes):
        v = m.vertices
        if len(v) > 200:
            idx = np.random.choice(len(v), 200, replace=False)
            v = v[idx]
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
    p.add_argument("--method", type=str, default="backtrack", choices=["greedy", "backtrack", "layers"])
    p.add_argument("--compact", action="store_true")
    p.add_argument("--beam-width", type=int, default=5, help="Top-K candidates for random selection (1=lowest-Y, 5=explore)")
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

    print(f"\nPacking ({args.method})...")
    placed, meshes = packer.pack(method=args.method, max_pieces=500, compact=args.compact, verbose=True, beam_width=args.beam_width)

    if meshes:
        print("\nVerifying...")
        verify(meshes)
        print("\nVisualizing...")
        visualize(meshes, box_dims, args.output.replace('.png', ''))


if __name__ == "__main__":
    main()
