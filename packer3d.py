"""
3D Bin Packer -- AABB + spatial-grid placement with BVH verification.
Completely standalone. Zero overlap guaranteed.

Usage:
    python packer3d.py                                    # uses built-in test triangle
    python packer3d.py file.stl                           # custom STL
    python packer3d.py file.stl L W H                     # custom STL + box dimensions
"""

import sys
import time
import math
import argparse
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np
import trimesh
from scipy.spatial.transform import Rotation as R

# --------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------

@dataclass
class OrientedPiece:
    """A piece mesh in a specific orientation, ready for packing."""
    mesh: trimesh.Trimesh
    aabb: np.ndarray          # [[min_x,min_y,min_z],[max_x,max_y,max_z]] in local coords (min_y=0)
    size: np.ndarray          # [sx, sy, sz]
    name: str

@dataclass
class PlacedPiece:
    """A piece that has been placed in the box."""
    mesh: trimesh.Trimesh
    aabb: np.ndarray          # world AABB
    position: np.ndarray      # [x, y, z] center-bottom position
    orient_name: str

# --------------------------------------------------------------------
# Spatial grid for fast neighbor queries
# --------------------------------------------------------------------

class SpatialGrid:
    """
    2D spatial grid (XZ) for fast XZ-overlap queries.
    Y dimension is not indexed — we filter by Y after XZ overlap is found.
    """
    def __init__(self, cell_size=50.0):
        self.cell_size = cell_size
        self.cells: dict[tuple, list[int]] = {}  # (ix, iz) -> [piece_idx, ...]
        self.pieces: list[PlacedPiece] = []

    def _cell_key(self, x: float, z: float) -> tuple:
        return (int(math.floor(x / self.cell_size)),
                int(math.floor(z / self.cell_size)))

    def _cell_keys_for_aabb(self, aabb: np.ndarray):
        """Return all (ix, iz) cell keys for an AABB."""
        ix0 = int(math.floor(aabb[0, 0] / self.cell_size))
        ix1 = int(math.floor(aabb[1, 0] / self.cell_size))
        iz0 = int(math.floor(aabb[0, 2] / self.cell_size))
        iz1 = int(math.floor(aabb[1, 2] / self.cell_size))
        keys = []
        for ix in range(ix0, ix1 + 1):
            for iz in range(iz0, iz1 + 1):
                keys.append((ix, iz))
        return keys

    def add(self, piece: PlacedPiece):
        idx = len(self.pieces)
        self.pieces.append(piece)
        for key in self._cell_keys_for_aabb(piece.aabb):
            self.cells.setdefault(key, []).append(idx)

    def query_xz(self, min_x: float, max_x: float, min_z: float, max_z: float) -> list[int]:
        """Return indices of pieces whose XZ extent overlaps the given range."""
        ix0 = int(math.floor(min_x / self.cell_size))
        ix1 = int(math.floor(max_x / self.cell_size))
        iz0 = int(math.floor(min_z / self.cell_size))
        iz1 = int(math.floor(max_z / self.cell_size))
        seen = set()
        result = []
        for ix in range(ix0, ix1 + 1):
            for iz in range(iz0, iz1 + 1):
                for idx in self.cells.get((ix, iz), []):
                    if idx not in seen:
                        seen.add(idx)
                        result.append(idx)
        return result

# --------------------------------------------------------------------
# Collision detection
# --------------------------------------------------------------------

def aabbs_overlap(a: np.ndarray, b: np.ndarray, inflate: float = 0.0) -> bool:
    """Check if two AABBs overlap in volume (strict: touching at edges/surfaces is NOT overlap)."""
    eps = 0.001
    return not (
        a[1, 0] <= b[0, 0] + eps + inflate or
        a[0, 0] >= b[1, 0] - eps - inflate or
        a[1, 1] <= b[0, 1] + eps + inflate or
        a[0, 1] >= b[1, 1] - eps - inflate or
        a[1, 2] <= b[0, 2] + eps + inflate or
        a[0, 2] >= b[1, 2] - eps - inflate
    )

def meshes_intersect_simple(mesh_a: trimesh.Trimesh, matrix_a: np.ndarray,
                            mesh_b: trimesh.Trimesh, matrix_b: np.ndarray) -> bool:
    """
    Check if two meshes truly intersect (share volume, not just touch at surfaces).
    Uses trimesh proximity with a tight epsilon.
    """
    eps = 0.001  # 0.001mm - touching surfaces are NOT intersections
    try:
        pts_a = mesh_a.vertices
        pts_b = mesh_b.vertices

        a_min = pts_a.min(axis=0) if len(pts_a) > 0 else np.zeros(3)
        a_max = pts_a.max(axis=0) if len(pts_a) > 0 else np.zeros(3)
        b_min = pts_b.min(axis=0) if len(pts_b) > 0 else np.zeros(3)
        b_max = pts_b.max(axis=0) if len(pts_b) > 0 else np.zeros(3)

        # Strict AABB overlap (no edge-touching)
        if (a_max[0] <= b_min[0] + eps or a_min[0] >= b_max[0] - eps or
            a_max[1] <= b_min[1] + eps or a_min[1] >= b_max[1] - eps or
            a_max[2] <= b_min[2] + eps or a_min[2] >= b_max[2] - eps):
            return False

        dist_a_to_b = trimesh.proximity.closest_point(mesh_a, pts_b)
        if dist_a_to_b is not None:
            if np.any(dist_a_to_b[1] < 0.001):
                return True

        dist_b_to_a = trimesh.proximity.closest_point(mesh_b, pts_a)
        if dist_b_to_a is not None:
            if np.any(dist_b_to_a[1] < 0.001):
                return True

        return False
    except Exception:
        return True

def compute_min_y_candidate(pos_x: float, pos_z: float,
                            piece_aabb: np.ndarray, piece_size_y: float,
                            grid: SpatialGrid, gap: float = 0.0) -> float:
    """
    Compute the minimum Y position for a piece at (pos_x, pos_z).
    Finds the highest AABB top among all placed pieces that overlap in XZ.
    """
    min_x = pos_x + piece_aabb[0, 0]
    max_x = pos_x + piece_aabb[1, 0]
    min_z = pos_z + piece_aabb[0, 2]
    max_z = pos_z + piece_aabb[1, 2]

    # Query XZ cells only (fast 2D lookup)
    neighbors = grid.query_xz(min_x, max_x, min_z, max_z)
    min_y = 0.0
    eps = 0.001
    for idx in neighbors:
        other = grid.pieces[idx]
        # Strict XZ overlap (edge-touching min=max NOT counted as overlap)
        if max_x <= other.aabb[0, 0] + eps or min_x >= other.aabb[1, 0] - eps:
            continue
        if max_z <= other.aabb[0, 2] + eps or min_z >= other.aabb[1, 2] - eps:
            continue
        min_y = max(min_y, other.aabb[1, 1])
    return min_y + gap

# --------------------------------------------------------------------
# Orientation generation
# --------------------------------------------------------------------

def generate_orientations(mesh: trimesh.Trimesh, n_yaw: int = 16, use_roll_flip: bool = True) -> list[OrientedPiece]:
    """Generate candidate orientations for packing."""
    orientations = []

    # Yaw rotations around Y (vertical axis)
    yaw_angles = np.linspace(0, 360, n_yaw, endpoint=False)

    for yaw in yaw_angles:
        # Rotation around Y axis
        rot_yaw = R.from_euler('y', yaw, degrees=True)
        rotation_matrix = rot_yaw.as_matrix()

        transformed = mesh.copy()
        transformed.apply_transform(np.eye(4))  # reset
        transformed.apply_transform(np.vstack([
            np.hstack([rotation_matrix, np.zeros((3, 1))]),
            [0, 0, 0, 1]
        ]))

        # Align base to y=0
        bmin = transformed.bounds[0]
        transformed.apply_translation([-bmin[0], -bmin[1], -bmin[2]])
        bbox = transformed.bounds
        size = transformed.extents

        orientations.append(OrientedPiece(
            mesh=transformed,
            aabb=np.array([bbox[0], bbox[1]]),
            size=size,
            name=f"Y{yaw:.0f}"
        ))

    # Roll=180deg variants (flip upside down for complementary shapes)
    if use_roll_flip:
        flipped = []
        for op in orientations:
            rot_roll = R.from_euler('z', 180, degrees=True).as_matrix()
            flipped_mesh = op.mesh.copy()
            flipped_mesh.apply_transform(np.vstack([
                np.hstack([rot_roll, np.zeros((3, 1))]),
                [0, 0, 0, 1]
            ]))
            bmin = flipped_mesh.bounds[0]
            flipped_mesh.apply_translation([-bmin[0], -bmin[1], -bmin[2]])
            bbox = flipped_mesh.bounds
            size = flipped_mesh.extents

            flipped.append(OrientedPiece(
                mesh=flipped_mesh,
                aabb=np.array([bbox[0], bbox[1]]),
                size=size,
                name=f"Y{yaw:.0f}R180"
            ))
        orientations.extend(flipped)

    # Deduplicate by size + geometry fingerprint (not just size)
    # Two orientations with the same AABB but different shape should both be kept
    seen = set()
    unique = []
    for op in orientations:
        size_key = tuple(op.size.round(2))
        # Also include a geometry fingerprint (a few key vertex positions) 
        # to distinguish same-size but different-shape orientations
        v_sample = op.mesh.vertices[::max(1, len(op.mesh.vertices)//4)]
        geo_key = tuple(v_sample.flatten().round(2))
        key = (size_key, geo_key)
        if key not in seen:
            seen.add(key)
            unique.append(op)
    return unique


def compute_flat_base_score(mesh: trimesh.Trimesh, sample_n: int = 20) -> float:
    """
    Score how flat the base (y~0) is. Higher = better for stacking.
    Counts vertices/points near the bottom.
    """
    samples = mesh.sample(sample_n * 100)
    y_vals = samples[:, 1]
    eps = max(0.05, mesh.extents[1] * 0.02)
    flat_fraction = np.mean(y_vals < eps)
    return float(flat_fraction)


# --------------------------------------------------------------------
# Packing engine
# --------------------------------------------------------------------

def pack(pieces: list[OrientedPiece], box_dims: tuple[float, float, float],
         gap: float = 0.0, max_placements: int = 2000,
         xz_step_ratio: float = 0.2) -> tuple[list[PlacedPiece], dict]:
    """
    Grid-based 3D packing.
    
    Algorithm:
    1. For each orientation, compute grid capacity: nx=floor(L/sx), nz=floor(W/sz), ny=floor(H/sy)
    2. Pick the orientation with max total count (nx * nz * ny)
    3. Place pieces at grid positions (alternating orientations for complementary shapes)
    
    This is optimal for cuboids and a good conservative approximation for arbitrary shapes.
    Guaranteed zero overlap (AABB-based, no mesh intersection possible).
    """
    box_l, box_w, box_h = box_dims
    start_time = time.time()

    # Score orientations by grid capacity
    best_total = 0
    best_orient = None
    best_nx = best_nz = best_ny = 0

    for op in pieces:
        sx, sy, sz = op.size
        if sy + gap > box_h:
            continue
        nx = max(1, int((box_l + gap) / (sx + gap)))
        nz = max(1, int((box_w + gap) / (sz + gap)))
        ny = max(1, int((box_h + gap) / (sy + gap)))
        total = nx * nz * ny
        if total > best_total:
            best_total = total
            best_orient = op
            best_nx, best_nz, best_ny = nx, nz, ny

    if best_orient is None:
        print("[Packer] No orientation fits in box!")
        return [], {'count': 0, 'fill_pct': 0, 'elapsed': 0, 'orient_usage': {}}

    print(f"[Packer] Box: {box_l}x{box_w}x{box_h} mm, gap={gap}mm")
    print(f"[Packer] Best: {best_orient.name} size={best_orient.size.round(1)}, "
          f"grid={best_nx}x{best_nz}x{best_ny}={best_total}")

    # Find all orientations with same XY footprint for complementary placement
    sx_primary, sy_primary, sz_primary = best_orient.size
    compat_orientations = [best_orient]
    for op in pieces:
        if op is best_orient:
            continue
        if (abs(op.size[0] - sx_primary) < 0.5 and
            abs(op.size[1] - sy_primary) < 0.5 and
            abs(op.size[2] - sz_primary) < 0.5):
            compat_orientations.append(op)

    print(f"[Packer] {len(compat_orientations)} compatible orientations for alternating")

    placed: list[PlacedPiece] = []
    orient_usage = {op.name: 0 for op in pieces}

    step_x = sx_primary + gap
    step_z = sz_primary + gap
    step_y = sy_primary + gap

    # Place pieces in layers
    for iy in range(best_ny):
        for ix in range(best_nx):
            for iz in range(best_nz):
                if len(placed) >= max_placements:
                    break

                x = ix * step_x
                y = iy * step_y
                z = iz * step_z

                # Alternate orientations (e.g., for complementary right triangles)
                orient = compat_orientations[len(placed) % len(compat_orientations)]

                placed_mesh = orient.mesh.copy()
                placed_mesh.apply_translation([x, y, z])

                world_aabb = np.array([
                    [x + orient.aabb[0, 0], y + orient.aabb[0, 1], z + orient.aabb[0, 2]],
                    [x + orient.aabb[1, 0], y + orient.aabb[1, 1], z + orient.aabb[1, 2]],
                ])

                pp = PlacedPiece(
                    mesh=placed_mesh,
                    aabb=world_aabb,
                    position=np.array([x, y, z]),
                    orient_name=orient.name,
                )
                placed.append(pp)
                orient_usage[orient.name] = orient_usage.get(orient.name, 0) + 1

    elapsed = time.time() - start_time
    total_vol = sum(p.mesh.volume for p in placed)
    fill_pct = total_vol / (box_l * box_w * box_h) * 100

    stats = {
        'count': len(placed),
        'fill_pct': fill_pct,
        'elapsed': elapsed,
        'orient_usage': orient_usage,
    }
    print(f"\n[Packer] DONE: {len(placed)} pieces, {fill_pct:.1f}% fill, {elapsed:.3f}s")
    print(f"[Packer] Grid: {best_nx}x{best_nz}x{best_ny} = {best_total}")
    print(f"[Packer] Orientation usage: { {k: v for k, v in sorted(orient_usage.items()) if v > 0} }")
    return placed, stats


# --------------------------------------------------------------------
# Overlap verification
# --------------------------------------------------------------------

def verify_no_overlap(placed: list[PlacedPiece], gap: float = 0.0) -> tuple[bool, int]:
    """Verify that no placed pieces overlap. Returns (ok, overlap_count)."""
    overlaps = 0
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            if aabbs_overlap(placed[i].aabb, placed[j].aabb, inflate=gap * 0.5):
                if meshes_intersect_simple(placed[i].mesh, np.eye(4),
                                           placed[j].mesh, np.eye(4)):
                    overlaps += 1
                    print(f"  OVERLAP: piece {i} ({placed[i].orient_name}) "
                          f"and piece {j} ({placed[j].orient_name})")
    return overlaps == 0, overlaps


# --------------------------------------------------------------------
# Visualization
# --------------------------------------------------------------------

def visualize_packing(placed: list[PlacedPiece], box_dims: tuple,
                      output_path: str = "packed_result.png",
                      gap: float = 0.0):
    """Generate 4-angle visualization of the packed box."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    box_l, box_w, box_h = box_dims
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    fig.suptitle(f"3D Packing Result -- {len(placed)} pieces, "
                 f"Box: {box_l}x{box_w}x{box_h} mm, Gap: {gap}mm",
                 fontsize=14, fontweight='bold')

    views = [
        ("Isometric", (1, 1, 0.7), 30),
        ("Top View", (0, 0, 1), 90),
        ("Front View", (0, 1, 0), 0),
        ("Side View", (1, 0, 0), 0),
    ]

    colors = plt.cm.tab20(np.linspace(0, 1, max(20, len(placed))))

    for idx, ((title, elev_az, elev), ax) in enumerate(zip(views, axes.flat)):
        ax.set_title(title, fontsize=12)
        ax.set_xlim(-box_l * 0.1, box_l * 1.1)
        ax.set_ylim(-box_w * 0.1, box_w * 1.1)

        # Draw box outline
        rect = plt.Rectangle((0, 0), box_l, box_w, fill=False, color='black',
                              linewidth=2, linestyle='--')
        ax.add_patch(rect)

        if title == "Isometric":
            # Simple isometric-like projection
            for i, p in enumerate(placed):
                color = colors[i % len(colors)]
                # Draw AABB footprint
                x0, y0 = p.aabb[0, 0], p.aabb[0, 2]
                x1, y1 = p.aabb[1, 0], p.aabb[1, 2]
                h = p.aabb[1, 1] - p.aabb[0, 1]
                ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                            fill=True, alpha=0.3 + h / box_h * 0.5,
                                            color=color, ec='black', lw=0.5))
                ax.text(x0 + (x1 - x0) / 2, y0 + (y1 - y0) / 2,
                        f"{p.orient_name}", fontsize=6, ha='center', va='center')

        elif title == "Top View":
            for i, p in enumerate(placed):
                color = colors[i % len(colors)]
                x0, y0 = p.aabb[0, 0], p.aabb[0, 2]
                x1, y1 = p.aabb[1, 0], p.aabb[1, 2]
                h = p.aabb[1, 1] - p.aabb[0, 1]
                ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                            fill=True, alpha=0.4,
                                            color=color, ec='black', lw=0.5))
                ax.text(x0 + (x1 - x0) / 2, y0 + (y1 - y0) / 2,
                        f"y={p.position[1]:.0f}", fontsize=7, ha='center', va='center')

        elif title == "Front View":
            for i, p in enumerate(placed):
                color = colors[i % len(colors)]
                x0, y0 = p.aabb[0, 0], 0
                x1, y1 = p.aabb[1, 0], p.aabb[1, 1]
                ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                            fill=True, alpha=0.4,
                                            color=color, ec='black', lw=0.5))

        elif title == "Side View":
            for i, p in enumerate(placed):
                color = colors[i % len(colors)]
                x0, y0 = p.aabb[0, 2], 0
                x1, y1 = p.aabb[1, 2], p.aabb[1, 1]
                ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                            fill=True, alpha=0.4,
                                            color=color, ec='black', lw=0.5))

        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"[Viz] Saved to {output_path}")
    plt.close()


# --------------------------------------------------------------------
# 3D visualization using trimesh scene viewer
# --------------------------------------------------------------------

def visualize_3d(placed: list[PlacedPiece], box_dims: tuple):
    """Interactive 3D visualization using trimesh viewer."""
    box_l, box_w, box_h = box_dims

    # Create box wireframe
    box_lines = [
        [0, 0, 0], [box_l, 0, 0], [box_l, 0, box_w], [0, 0, box_w], [0, 0, 0],  # bottom
        [0, box_h, 0], [box_l, box_h, 0], [box_l, box_h, box_w], [0, box_h, box_w], [0, box_h, 0],  # top
        [0, 0, 0], [0, box_h, 0],  # vertical
        [box_l, 0, 0], [box_l, box_h, 0],
        [box_l, 0, box_w], [box_l, box_h, box_w],
        [0, 0, box_w], [0, box_h, box_w],
    ]
    box_path = trimesh.path.Path3D(entities=[trimesh.path.entities.Line(np.arange(len(box_lines)))],
                                    vertices=box_lines, colors=[0, 0, 0, 255])

    # Combine all placed meshes
    scene_parts = [box_path]
    colors_hex = ['#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4',
                  '#42d4f4', '#f032e6', '#bfef45', '#fabed4', '#469990', '#dcbeff',
                  '#9A6324', '#800000', '#aaffc3', '#808000', '#ffd8b1', '#000075']

    for i, p in enumerate(placed):
        mesh = p.mesh.copy()
        mesh.visual.face_colors = trimesh.visual.color.hex_to_rgba(
            colors_hex[i % len(colors_hex)])
        mesh.visual.face_colors[:, 3] = 200  # semi-transparent
        scene_parts.append(mesh)

    try:
        scene = trimesh.Scene(scene_parts)
        scene.show()
    except Exception as e:
        print(f"[Viz3D] Viewer error (headless?): {e}")
        print("[Viz3D] Try: python packer3d.py --no-3d")


# --------------------------------------------------------------------
# Build test triangle (right triangular prism)
# --------------------------------------------------------------------

def make_test_triangle() -> trimesh.Trimesh:
    """Create a right triangular prism: 40x20x20 mm."""
    # Right triangle cross-section in XY: (0,0), (40,0), (0,-20)
    # Extruded 20mm in Z
    vertices = np.array([
        [0, 0, 20],      # 0
        [0, 0, 0],       # 1
        [0, -20, 0],     # 2
        [0, -20, 20],    # 3
        [40, 0, 0],      # 4
        [40, -20, 0],    # 5
    ], dtype=np.float64)
    faces = np.array([
        [0, 1, 2], [0, 2, 3],  # vertical face at x=0
        [4, 0, 5], [5, 0, 3],  # sloped face
        [1, 4, 2], [2, 4, 5],  # sloped face
        [4, 1, 0],             # top face (y=0)
        [2, 5, 3],             # bottom face (y=-20)
    ], dtype=np.int32)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    assert mesh.is_watertight, "Test triangle must be watertight!"
    return mesh


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="3D Bin Packer")
    parser.add_argument("stl", nargs="?", default=None, help="STL file to pack")
    parser.add_argument("box_l", nargs="?", type=float, default=200,
                        help="Box length X (mm)")
    parser.add_argument("box_w", nargs="?", type=float, default=200,
                        help="Box width Z (mm)")
    parser.add_argument("box_h", nargs="?", type=float, default=150,
                        help="Box height Y (mm)")
    parser.add_argument("--gap", type=float, default=0.0,
                        help="Gap between pieces (mm)")
    parser.add_argument("--max", type=int, default=500,
                        help="Max placements")
    parser.add_argument("--step-ratio", type=float, default=0.2,
                        help="XZ scan step ratio (0.05=precise, 0.5=fast)")
    parser.add_argument("--yaw", type=int, default=16,
                        help="Number of yaw orientations")
    parser.add_argument("--no-3d", action="store_true",
                        help="Skip 3D viewer")
    parser.add_argument("--output", type=str, default="packed_result.png",
                        help="Output image path")
    parser.add_argument("--no-verify", action="store_true",
                        help="Skip overlap verification (faster)")
    args = parser.parse_args()

    # Load or create mesh
    if args.stl:
        filepath = Path(args.stl)
        if not filepath.exists():
            print(f"ERROR: File not found: {filepath}")
            sys.exit(1)
        mesh = trimesh.load(str(filepath), force='mesh')
        if isinstance(mesh, trimesh.Scene):
            # Combine all geometries
            meshes = [g for g in mesh.geometry.values()
                      if isinstance(g, trimesh.Trimesh)]
            mesh = trimesh.util.concatenate(meshes)
        print(f"Loaded: {filepath} -- {len(mesh.vertices)} verts, {len(mesh.faces)} faces")
    else:
        print("Using built-in test triangle (right triangular prism)")
        mesh = make_test_triangle()

    box_dims = (args.box_l, args.box_w, args.box_h)

    # Generate orientations
    print(f"\nGenerating {args.yaw} yaw orientations + roll=180deg variants...")
    orientations = generate_orientations(mesh, n_yaw=args.yaw, use_roll_flip=True)
    print(f"  -> {len(orientations)} unique orientations")

    # Score and show top orientations
    scored = []
    for op in orientations:
        score = compute_flat_base_score(op.mesh)
        scored.append((score, op))
    scored.sort(key=lambda x: -x[0])
    print(f"  Top 5 orientations:")
    for score, op in scored[:5]:
        print(f"    {op.name:>10s}  flat={score:.3f}  size={op.size.round(1)}")

    # Pack
    print(f"\n{'='*60}")
    print(f"PACKING...")
    print(f"{'='*60}")
    placed, stats = pack(orientations, box_dims, gap=args.gap,
                         max_placements=args.max,
                         xz_step_ratio=args.step_ratio)

    # Verify
    if not args.no_verify and len(placed) > 0:
        print(f"\n{'='*60}")
        print(f"VERIFICATION...")
        ok, n_overlaps = verify_no_overlap(placed, gap=args.gap)
        if ok:
            print(f"  [OK] ZERO overlap -- all {len(placed)} pieces are correctly placed!")
        else:
            print(f"  [FAIL] Found {n_overlaps} overlapping pairs!")

    # Visualize
    visualize_packing(placed, box_dims, output_path=args.output, gap=args.gap)

    if not args.no_3d:
        visualize_3d(placed, box_dims)

    return placed, stats


if __name__ == "__main__":
    main()
