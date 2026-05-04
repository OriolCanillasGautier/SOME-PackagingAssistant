"""
contacts.py — Contact manifold generation on GPU.

Given SAT collision results (overlap depth + minimum axis), generates
contact points for the impulse solver.
"""
import numpy as np
from numba import cuda


@cuda.jit(device=True)
def _dot3(a_x, a_y, a_z, b_x, b_y, b_z):
    return a_x * b_x + a_y * b_y + a_z * b_z


@cuda.jit
def _generate_contacts_kernel(
    collision_results,  # [n_pairs, 4] float64: overlap, nx, ny, nz
    pair_indices,       # [n_pairs, 2] int32
    positions,          # [n_bodies, 3] float64
    aabb_min,           # [n_bodies, 3] float64
    aabb_max,           # [n_bodies, 3] float64
    contacts,           # [max_contacts, 8] float64: px, py, pz, nx, ny, nz, depth, (unused)
    contact_count,      # [1] int32
    max_contacts,
):
    idx = cuda.grid(1)
    if idx >= collision_results.shape[0]:
        return

    overlap = collision_results[idx, 0]
    if overlap <= 0.0:
        return

    bi = pair_indices[idx, 0]
    bj = pair_indices[idx, 1]
    nx = collision_results[idx, 1]
    ny = collision_results[idx, 2]
    nz = collision_results[idx, 3]

    # Contact point: midpoint of overlapping AABB region
    # For each axis, the overlap interval midpoint
    px = 0.0
    py = 0.0
    pz = 0.0
    count = 0

    # X-axis midpoint
    if aabb_max[bi, 0] > aabb_min[bj, 0] and aabb_min[bi, 0] < aabb_max[bj, 0]:
        x_min = aabb_min[bi, 0]
        if aabb_min[bj, 0] > x_min:
            x_min = aabb_min[bj, 0]
        x_max = aabb_max[bi, 0]
        if aabb_max[bj, 0] < x_max:
            x_max = aabb_max[bj, 0]
        px += (x_min + x_max) * 0.5
        count += 1

    # Y-axis midpoint
    if aabb_max[bi, 1] > aabb_min[bj, 1] and aabb_min[bi, 1] < aabb_max[bj, 1]:
        y_min = aabb_min[bi, 1]
        if aabb_min[bj, 1] > y_min:
            y_min = aabb_min[bj, 1]
        y_max = aabb_max[bi, 1]
        if aabb_max[bj, 1] < y_max:
            y_max = aabb_max[bj, 1]
        py += (y_min + y_max) * 0.5
        count += 1

    # Z-axis midpoint
    if aabb_max[bi, 2] > aabb_min[bj, 2] and aabb_min[bi, 2] < aabb_max[bj, 2]:
        z_min = aabb_min[bi, 2]
        if aabb_min[bj, 2] > z_min:
            z_min = aabb_min[bj, 2]
        z_max = aabb_max[bi, 2]
        if aabb_max[bj, 2] < z_max:
            z_max = aabb_max[bj, 2]
        pz += (z_min + z_max) * 0.5
        count += 1

    # Fallback: use body centers
    if count == 0:
        px = (positions[bi, 0] + positions[bj, 0]) * 0.5
        py = (positions[bi, 1] + positions[bj, 1]) * 0.5
        pz = (positions[bi, 2] + positions[bj, 2]) * 0.5
    else:
        px /= count
        py /= count
        pz /= count

    # Ensure normal points from B to A
    # (standard convention: resolve along normal from B toward A)
    dot_ba_x = positions[bi, 0] - positions[bj, 0]
    dot_ba_y = positions[bi, 1] - positions[bj, 1]
    dot_ba_z = positions[bi, 2] - positions[bj, 2]
    d = dot_ba_x * nx + dot_ba_y * ny + dot_ba_z * nz
    if d < 0.0:
        nx = -nx
        ny = -ny
        nz = -nz

    pos = cuda.atomic.add(contact_count, 0, 1)
    if pos < max_contacts:
        contacts[pos, 0] = px
        contacts[pos, 1] = py
        contacts[pos, 2] = pz
        contacts[pos, 3] = nx
        contacts[pos, 4] = ny
        contacts[pos, 5] = nz
        contacts[pos, 6] = overlap
        contacts[pos, 7] = float(bi) + float(bj) * 10000.0  # packed body indices


class ContactGenerator:
    """Generates contact manifolds from SAT collision results."""

    def __init__(self):
        pass

    def generate(self, collision_results, pair_indices, positions,
                 aabb_min, aabb_max, max_contacts=100000):
        """Generate contacts from collision results.

        Args:
            collision_results: (n_pairs, 4) from CollisionDetector.collide()
            pair_indices: (n_pairs, 2) int32
            positions: (n_bodies, 3) float64
            aabb_min, aabb_max: (n_bodies, 3) float64

        Returns:
            contacts: (n_contacts, 8) float64 [px, py, pz, nx, ny, nz, depth, body_ids]
        """
        n_pairs = len(collision_results)
        if n_pairs == 0:
            return np.zeros((0, 8), dtype=np.float64)

        threads = 256
        blocks = (n_pairs + threads - 1) // threads

        d_results = cuda.to_device(np.asarray(collision_results, dtype=np.float64))
        d_pairs = cuda.to_device(np.asarray(pair_indices, dtype=np.int32))
        d_pos = cuda.to_device(np.asarray(positions, dtype=np.float64))
        d_amin = cuda.to_device(np.asarray(aabb_min, dtype=np.float64))
        d_amax = cuda.to_device(np.asarray(aabb_max, dtype=np.float64))
        d_contacts = cuda.to_device(np.zeros((max_contacts, 8), dtype=np.float64))
        d_count = cuda.to_device(np.zeros(1, dtype=np.int32))

        _generate_contacts_kernel[blocks, threads](
            d_results, d_pairs, d_pos, d_amin, d_amax,
            d_contacts, d_count, max_contacts,
        )
        cuda.synchronize()

        n = int(d_count.copy_to_host()[0])
        n = min(n, max_contacts)
        if n == 0:
            return np.zeros((0, 8), dtype=np.float64)
        return d_contacts.copy_to_host()[:n]
