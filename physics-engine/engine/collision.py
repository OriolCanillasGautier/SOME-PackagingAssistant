"""
collision.py — GPU SAT narrow-phase collision detection.

Provides full Separating Axis Theorem testing including face normals and
edge-edge cross products. Batched many-vs-many on CUDA.
"""
import numpy as np
import math as _m
from numba import cuda

from .hull import HullData

# ═══════════════════════════════════════════════
# GPU device functions
# ═══════════════════════════════════════════════

@cuda.jit(device=True)
def _dot3(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

@cuda.jit(device=True)
def _cross3(a, b, out):
    out[0] = a[1] * b[2] - a[2] * b[1]
    out[1] = a[2] * b[0] - a[0] * b[2]
    out[2] = a[0] * b[1] - a[1] * b[0]

@cuda.jit(device=True)
def _norm3(v):
    l = _m.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if l > 1e-12:
        v[0] /= l
        v[1] /= l
        v[2] /= l
    return l

@cuda.jit(device=True)
def _sat_axis(axis, wa, wa_len, wb, wb_len):
    min_a = 1e30
    max_a = -1e30
    for i in range(wa_len):
        d = axis[0] * wa[i, 0] + axis[1] * wa[i, 1] + axis[2] * wa[i, 2]
        if d < min_a:
            min_a = d
        if d > max_a:
            max_a = d
    min_b = 1e30
    max_b = -1e30
    for i in range(wb_len):
        d = axis[0] * wb[i, 0] + axis[1] * wb[i, 1] + axis[2] * wb[i, 2]
        if d < min_b:
            min_b = d
        if d > max_b:
            max_b = d
    if max_a < min_b or max_b < min_a:
        return True, 0.0
    overlap = max_a - min_b
    if max_b - min_a < overlap:
        overlap = max_b - min_a
    return False, overlap

@cuda.jit(device=True)
def _quat_rotate(q, vx, vy, vz):
    qx, qy, qz, qw = q[0], q[1], q[2], q[3]
    tx = 2.0 * (qy * vz - qz * vy)
    ty = 2.0 * (qz * vx - qx * vz)
    tz = 2.0 * (qx * vy - qy * vx)
    rx = vx + qw * tx + (qy * tz - qz * ty)
    ry = vy + qw * ty + (qz * tx - qx * tz)
    rz = vz + qw * tz + (qx * ty - qy * tx)
    return rx, ry, rz


# ═══════════════════════════════════════════════
# Batch collision kernel
# ═══════════════════════════════════════════════

@cuda.jit
def _batch_collide_kernel(
    hull_verts,          # [n_hulls, max_v, 3] float64
    hull_vert_counts,    # [n_hulls] int32
    hull_norms,          # [n_hulls, max_f, 3] float64
    hull_face_counts,    # [n_hulls] int32
    hull_edges,          # [n_hulls, max_e, 3] float64
    hull_edge_counts,    # [n_hulls] int32
    positions,           # [n_bodies, 3] float64
    quaternions,         # [n_bodies, 4] float64 (x,y,z,w)
    pairs,               # [n_pairs, 2] int32
    results,             # [n_pairs, 4] float64: overlap, nx, ny, nz
    max_v,
    max_f,
    max_e,
    temp_pool,           # [n_threads, pool_size] float64 scratch
    pool_stride,         # stride per thread in temp_pool
):
    idx = cuda.grid(1)
    if idx >= pairs.shape[0]:
        return

    bi = pairs[idx, 0]
    bj = pairs[idx, 1]
    hi = bi
    hj = bj

    nvi = hull_vert_counts[hi]
    nvj = hull_vert_counts[hj]
    nfi = hull_face_counts[hi]
    nfj = hull_face_counts[hj]
    nei = hull_edge_counts[hi]
    nej = hull_edge_counts[hj]

    pos_i = positions[bi]
    pos_j = positions[bj]
    quat_i = quaternions[bi]
    quat_j = quaternions[bj]

    # Thread-local scratch from pool
    base = idx * pool_stride
    # Layout: [nvi * 3] wa, [nvj * 3] wb, [nfi * 3] na, [nfj * 3] nb

    # Transform A vertices
    for v in range(nvi):
        hv = hull_verts[hi, v]
        rx, ry, rz = _quat_rotate(quat_i, hv[0], hv[1], hv[2])
        temp_pool[base + v * 3 + 0] = rx + pos_i[0]
        temp_pool[base + v * 3 + 1] = ry + pos_i[1]
        temp_pool[base + v * 3 + 2] = rz + pos_i[2]

    # Transform A normals
    off_na = nvi * 3
    for f in range(nfi):
        hn = hull_norms[hi, f]
        rx, ry, rz = _quat_rotate(quat_i, hn[0], hn[1], hn[2])
        temp_pool[base + off_na + f * 3 + 0] = rx
        temp_pool[base + off_na + f * 3 + 1] = ry
        temp_pool[base + off_na + f * 3 + 2] = rz

    # Transform B vertices
    off_b = off_na + nfi * 3
    for v in range(nvj):
        hv = hull_verts[hj, v]
        rx, ry, rz = _quat_rotate(quat_j, hv[0], hv[1], hv[2])
        temp_pool[base + off_b + v * 3 + 0] = rx + pos_j[0]
        temp_pool[base + off_b + v * 3 + 1] = ry + pos_j[1]
        temp_pool[base + off_b + v * 3 + 2] = rz + pos_j[2]

    # Transform B normals
    off_nb = off_b + nvj * 3
    for f in range(nfj):
        hn = hull_norms[hj, f]
        rx, ry, rz = _quat_rotate(quat_j, hn[0], hn[1], hn[2])
        temp_pool[base + off_nb + f * 3 + 0] = rx
        temp_pool[base + off_nb + f * 3 + 1] = ry
        temp_pool[base + off_nb + f * 3 + 2] = rz

    min_overlap = 1e30
    best_x = 0.0
    best_y = 0.0
    best_z = 1.0

    # Helper to read vertex from temp pool
    # wa is at base + v*3, wb is at base + off_b + v*3
    # For SAT axis, we need to project. Instead of indexed read helpers, inline.

    # Test face normals of A
    for f in range(nfi):
        nx = temp_pool[base + off_na + f * 3 + 0]
        ny = temp_pool[base + off_na + f * 3 + 1]
        nz = temp_pool[base + off_na + f * 3 + 2]

        min_a = 1e30
        max_a = -1e30
        for v in range(nvi):
            d = nx * temp_pool[base + v * 3 + 0] + ny * temp_pool[base + v * 3 + 1] + nz * temp_pool[base + v * 3 + 2]
            if d < min_a: min_a = d
            if d > max_a: max_a = d
        min_b = 1e30
        max_b = -1e30
        for v in range(nvj):
            d = nx * temp_pool[base + off_b + v * 3 + 0] + ny * temp_pool[base + off_b + v * 3 + 1] + nz * temp_pool[base + off_b + v * 3 + 2]
            if d < min_b: min_b = d
            if d > max_b: max_b = d

        if max_a < min_b or max_b < min_a:
            results[idx, 0] = 0.0
            return
        ov = max_a - min_b
        if max_b - min_a < ov:
            ov = max_b - min_a
        if ov < min_overlap:
            min_overlap = ov
            best_x = nx
            best_y = ny
            best_z = nz

    # Test face normals of B
    for f in range(nfj):
        nx = temp_pool[base + off_nb + f * 3 + 0]
        ny = temp_pool[base + off_nb + f * 3 + 1]
        nz = temp_pool[base + off_nb + f * 3 + 2]

        min_a = 1e30
        max_a = -1e30
        for v in range(nvi):
            d = nx * temp_pool[base + v * 3 + 0] + ny * temp_pool[base + v * 3 + 1] + nz * temp_pool[base + v * 3 + 2]
            if d < min_a: min_a = d
            if d > max_a: max_a = d
        min_b = 1e30
        max_b = -1e30
        for v in range(nvj):
            d = nx * temp_pool[base + off_b + v * 3 + 0] + ny * temp_pool[base + off_b + v * 3 + 1] + nz * temp_pool[base + off_b + v * 3 + 2]
            if d < min_b: min_b = d
            if d > max_b: max_b = d

        if max_a < min_b or max_b < min_a:
            results[idx, 0] = 0.0
            return
        ov = max_a - min_b
        if max_b - min_a < ov:
            ov = max_b - min_a
        if ov < min_overlap:
            min_overlap = ov
            best_x = nx
            best_y = ny
            best_z = nz

    # Test edge-edge cross products
    for ei in range(nei):
        eix = hull_edges[hi, ei, 0]
        eiy = hull_edges[hi, ei, 1]
        eiz = hull_edges[hi, ei, 2]
        for ej in range(nej):
            ejx = hull_edges[hj, ej, 0]
            ejy = hull_edges[hj, ej, 1]
            ejz = hull_edges[hj, ej, 2]
            # cross product
            cx = eiy * ejz - eiz * ejy
            cy = eiz * ejx - eix * ejz
            cz = eix * ejy - eiy * ejx
            ln = _m.sqrt(cx * cx + cy * cy + cz * cz)
            if ln < 1e-12:
                continue
            cx /= ln
            cy /= ln
            cz /= ln

            min_a = 1e30
            max_a = -1e30
            for v in range(nvi):
                d = cx * temp_pool[base + v * 3 + 0] + cy * temp_pool[base + v * 3 + 1] + cz * temp_pool[base + v * 3 + 2]
                if d < min_a: min_a = d
                if d > max_a: max_a = d
            min_b = 1e30
            max_b = -1e30
            for v in range(nvj):
                d = cx * temp_pool[base + off_b + v * 3 + 0] + cy * temp_pool[base + off_b + v * 3 + 1] + cz * temp_pool[base + off_b + v * 3 + 2]
                if d < min_b: min_b = d
                if d > max_b: max_b = d

            if max_a < min_b or max_b < min_a:
                results[idx, 0] = 0.0
                return
            ov = max_a - min_b
            if max_b - min_a < ov:
                ov = max_b - min_a
            if ov < min_overlap:
                min_overlap = ov
                best_x = cx
                best_y = cy
                best_z = cz

    results[idx, 0] = min_overlap
    results[idx, 1] = best_x
    results[idx, 2] = best_y
    results[idx, 3] = best_z


# ═══════════════════════════════════════════════
# CPU interface
# ═══════════════════════════════════════════════

class CollisionDetector:
    """GPU-accelerated SAT collision detector."""

    def __init__(self, hulls: list[HullData]):
        self.n_hulls = len(hulls)
        self.max_verts = max(h.vertex_count for h in hulls) if hulls else 0
        self.max_faces = max(h.face_count for h in hulls) if hulls else 0
        self.max_edges = max(self._edge_count(h) for h in hulls) if hulls else 0

        n = self.n_hulls
        mv = self.max_verts
        mf = self.max_faces
        me = self.max_edges

        hverts = np.zeros((n, mv, 3), dtype=np.float64)
        hvcts = np.zeros(n, dtype=np.int32)
        hnorms = np.zeros((n, mf, 3), dtype=np.float64)
        hfcts = np.zeros(n, dtype=np.int32)
        hedges = np.zeros((n, me, 3), dtype=np.float64)
        hects = np.zeros(n, dtype=np.int32)

        for i, h in enumerate(hulls):
            nv = h.vertex_count
            nf = h.face_count
            ne = self._edge_count(h)
            hverts[i, :nv] = h.vertices
            hvcts[i] = nv
            hnorms[i, :nf] = h.normals
            hfcts[i] = nf
            hedges[i, :ne] = self._compute_edges(h)
            hects[i] = ne

        self.d_hverts = cuda.to_device(hverts)
        self.d_hvcts = cuda.to_device(hvcts)
        self.d_hnorms = cuda.to_device(hnorms)
        self.d_hfcts = cuda.to_device(hfcts)
        self.d_hedges = cuda.to_device(hedges)
        self.d_hects = cuda.to_device(hects)

        # Per-thread scratch pool size: (nv + nf) * 3 per hull, for both A and B
        self.pool_stride = (mv + mf) * 3 * 2
        self._temp_pool = None

    def _edge_count(self, hull: HullData) -> int:
        faces = hull.faces
        edges = set()
        for f in faces:
            for a, b in [(f[0], f[1]), (f[1], f[2]), (f[2], f[0])]:
                edges.add((min(a, b), max(a, b)))
        return len(edges)

    def _compute_edges(self, hull: HullData) -> np.ndarray:
        verts = hull.vertices
        faces = hull.faces
        edges = set()
        for f in faces:
            for a, b in [(f[0], f[1]), (f[1], f[2]), (f[2], f[0])]:
                edges.add((min(a, b), max(a, b)))
        result = np.zeros((self.max_edges, 3), dtype=np.float64)
        for ei, (a, b) in enumerate(edges):
            if ei >= self.max_edges:
                break
            d = verts[b] - verts[a]
            n = np.linalg.norm(d)
            if n > 1e-12:
                d /= n
            result[ei] = d
        return result

    def collide(self, positions, quaternions, pairs):
        n_pairs = len(pairs)
        if n_pairs == 0:
            return np.zeros((0, 4), dtype=np.float64)

        threads = 256
        blocks = (n_pairs + threads - 1) // threads
        n_threads = blocks * threads

        # Allocate temp pool for all threads
        pool_size = n_threads * self.pool_stride
        if self._temp_pool is None or self._temp_pool.size < pool_size:
            self._temp_pool = cuda.to_device(np.zeros(pool_size, dtype=np.float64))

        d_pos = cuda.to_device(np.asarray(positions, dtype=np.float64))
        d_quat = cuda.to_device(np.asarray(quaternions, dtype=np.float64))
        d_pairs = cuda.to_device(np.asarray(pairs, dtype=np.int32))
        d_results = cuda.to_device(np.zeros((n_pairs, 4), dtype=np.float64))

        _batch_collide_kernel[blocks, threads](
            self.d_hverts, self.d_hvcts,
            self.d_hnorms, self.d_hfcts,
            self.d_hedges, self.d_hects,
            d_pos, d_quat, d_pairs, d_results,
            self.max_verts, self.max_faces, self.max_edges,
            self._temp_pool, self.pool_stride,
        )
        cuda.synchronize()
        return d_results.copy_to_host()
