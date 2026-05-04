"""
broadphase.py — GPU spatial hashing broad phase.

Divides space into a uniform grid. Each body is inserted into cells
overlapping its AABB. For each body, candidate pairs are generated
from neighboring cells.
"""
import numpy as np
from numba import cuda

# ═══════════════════════════════════════════════
# GPU kernels
# ═══════════════════════════════════════════════

@cuda.jit
def _clear_cells_kernel(cell_offsets, cell_counts, n_cells):
    idx = cuda.grid(1)
    if idx < n_cells:
        cell_offsets[idx] = 0
        cell_counts[idx] = 0


@cuda.jit
def _count_cells_kernel(
    aabb_min, aabb_max,  # [n_bodies, 3] float64
    n_bodies,
    cell_size,
    grid_res,             # (nx, ny, nz) int32
    cell_counts,          # [n_cells] int32 — atomically incremented
):
    idx = cuda.grid(1)
    if idx >= n_bodies:
        return

    amin = aabb_min[idx]
    amax = aabb_max[idx]
    cx0 = max(0, int(amin[0] / cell_size))
    cy0 = max(0, int(amin[1] / cell_size))
    cz0 = max(0, int(amin[2] / cell_size))
    cx1 = min(grid_res[0] - 1, int(amax[0] / cell_size))
    cy1 = min(grid_res[1] - 1, int(amax[1] / cell_size))
    cz1 = min(grid_res[2] - 1, int(amax[2] / cell_size))

    for cx in range(cx0, cx1 + 1):
        for cy in range(cy0, cy1 + 1):
            for cz in range(cz0, cz1 + 1):
                cell = cx * grid_res[1] * grid_res[2] + cy * grid_res[2] + cz
                cuda.atomic.add(cell_counts, cell, 1)


@cuda.jit
def _insert_cells_kernel(
    aabb_min, aabb_max,
    n_bodies,
    cell_size,
    grid_res,
    cell_offsets,          # [n_cells] int32 — prefix sum of counts
    cell_counts2,          # [n_cells] int32 — write cursor (reset copy)
    cell_entries,          # [total_entries] int32 — body indices
    max_entries,
):
    idx = cuda.grid(1)
    if idx >= n_bodies:
        return

    amin = aabb_min[idx]
    amax = aabb_max[idx]
    cx0 = max(0, int(amin[0] / cell_size))
    cy0 = max(0, int(amin[1] / cell_size))
    cz0 = max(0, int(amin[2] / cell_size))
    cx1 = min(grid_res[0] - 1, int(amax[0] / cell_size))
    cy1 = min(grid_res[1] - 1, int(amax[1] / cell_size))
    cz1 = min(grid_res[2] - 1, int(amax[2] / cell_size))

    for cx in range(cx0, cx1 + 1):
        for cy in range(cy0, cy1 + 1):
            for cz in range(cz0, cz1 + 1):
                cell = cx * grid_res[1] * grid_res[2] + cy * grid_res[2] + cz
                pos = cuda.atomic.add(cell_counts2, cell, 1)
                entry_idx = cell_offsets[cell] + pos
                if entry_idx < max_entries:
                    cell_entries[entry_idx] = idx


@cuda.jit
def _find_pairs_kernel(
    aabb_min, aabb_max,
    n_bodies,
    cell_size,
    grid_res,
    cell_offsets,
    cell_counts,
    cell_entries,
    max_pairs,
    pairs,                 # [max_pairs, 2] int32 — output
    pair_count,            # [1] int32 — atomic output count
):
    idx = cuda.grid(1)
    if idx >= n_bodies:
        return

    amin = aabb_min[idx]
    amax = aabb_max[idx]
    cx0 = max(0, int(amin[0] / cell_size))
    cy0 = max(0, int(amin[1] / cell_size))
    cz0 = max(0, int(amin[2] / cell_size))
    cx1 = min(grid_res[0] - 1, int(amax[0] / cell_size))
    cy1 = min(grid_res[1] - 1, int(amax[1] / cell_size))
    cz1 = min(grid_res[2] - 1, int(amax[2] / cell_size))

    for cx in range(cx0, cx1 + 1):
        for cy in range(cy0, cy1 + 1):
            for cz in range(cz0, cz1 + 1):
                cell = cx * grid_res[1] * grid_res[2] + cy * grid_res[2] + cz
                start = cell_offsets[cell]
                end = start + cell_counts[cell]
                for e in range(start, end):
                    j = cell_entries[e]
                    if j <= idx:
                        continue
                    # Quick AABB check
                    if not (amax[0] >= aabb_min[j, 0] and amin[0] <= aabb_max[j, 0] and
                            amax[1] >= aabb_min[j, 1] and amin[1] <= aabb_max[j, 1] and
                            amax[2] >= aabb_min[j, 2] and amin[2] <= aabb_max[j, 2]):
                        continue
                    # Write pair
                    pos = cuda.atomic.add(pair_count, 0, 1)
                    if pos < max_pairs:
                        pairs[pos, 0] = idx
                        pairs[pos, 1] = j


# ═══════════════════════════════════════════════
# CPU prefix sum (serial, small)
# ═══════════════════════════════════════════════

def _prefix_sum(arr):
    out = np.zeros_like(arr)
    s = 0
    for i in range(len(arr)):
        out[i] = s
        s += arr[i]
    return out, s


# ═══════════════════════════════════════════════
# CPU interface
# ═══════════════════════════════════════════════

class BroadPhase:
    """GPU spatial hashing broad phase.

    Divides space into uniform grid cells. Each step, inserts body AABBs
    into cells and generates candidate collision pairs.
    """

    def __init__(self, cell_size: float = 50.0, world_min=(0, 0, 0), world_max=(500, 500, 500)):
        self.cell_size = float(cell_size)
        self.world_min = np.array(world_min, dtype=np.float64)
        self.world_max = np.array(world_max, dtype=np.float64)
        extent = self.world_max - self.world_min
        self.grid_res = tuple(max(1, int(e / cell_size) + 1) for e in extent)
        self.n_cells = self.grid_res[0] * self.grid_res[1] * self.grid_res[2]

    def find_pairs(self, aabb_min: np.ndarray, aabb_max: np.ndarray,
                   max_pairs: int = 100000) -> np.ndarray:
        """Find all candidate pairs from AABB overlaps via spatial grid.

        Args:
            aabb_min: (n_bodies, 3) float64
            aabb_max: (n_bodies, 3) float64
            max_pairs: max pairs to return

        Returns:
            pairs: (n_pairs, 2) int32
        """
        n_bodies = len(aabb_min)
        if n_bodies < 2:
            return np.zeros((0, 2), dtype=np.int32)

        threads = 256
        blocks_body = (n_bodies + threads - 1) // threads

        # Allocate GPU arrays
        d_amin = cuda.to_device(np.asarray(aabb_min, dtype=np.float64))
        d_amax = cuda.to_device(np.asarray(aabb_max, dtype=np.float64))
        d_grid_res = cuda.to_device(np.array(self.grid_res, dtype=np.int32))
        d_cell_counts = cuda.to_device(np.zeros(self.n_cells, dtype=np.int32))
        d_cell_offsets = cuda.to_device(np.zeros(self.n_cells, dtype=np.int32))

        # Pass 1: count bodies per cell
        blocks_cells = (self.n_cells + threads - 1) // threads
        _count_cells_kernel[blocks_body, threads](
            d_amin, d_amax, n_bodies,
            self.cell_size, d_grid_res, d_cell_counts,
        )
        cuda.synchronize()

        # Prefix sum (CPU — grid is small, ~10^3 cells)
        counts = d_cell_counts.copy_to_host()
        offsets, total_entries = _prefix_sum(counts)

        if total_entries == 0:
            return np.zeros((0, 2), dtype=np.int32)

        d_cell_offsets = cuda.to_device(offsets)
        d_cell_counts2 = cuda.to_device(np.zeros(self.n_cells, dtype=np.int32))
        d_cell_entries = cuda.to_device(np.zeros(total_entries, dtype=np.int32))

        # Pass 2: insert bodies into cells
        _insert_cells_kernel[blocks_body, threads](
            d_amin, d_amax, n_bodies,
            self.cell_size, d_grid_res,
            d_cell_offsets, d_cell_counts2, d_cell_entries,
            total_entries,
        )
        cuda.synchronize()

        # Pass 3: find pairs
        d_pairs = cuda.to_device(np.zeros((max_pairs, 2), dtype=np.int32))
        d_pair_count = cuda.to_device(np.zeros(1, dtype=np.int32))

        _find_pairs_kernel[blocks_body, threads](
            d_amin, d_amax, n_bodies,
            self.cell_size, d_grid_res,
            d_cell_offsets, counts,
            d_cell_entries,
            max_pairs, d_pairs, d_pair_count,
        )
        cuda.synchronize()

        n_pairs = int(d_pair_count.copy_to_host()[0])
        n_pairs = min(n_pairs, max_pairs)
        if n_pairs == 0:
            return np.zeros((0, 2), dtype=np.int32)

        return d_pairs.copy_to_host()[:n_pairs]
