"""Debug script to trace the packing algorithm step by step."""
import sys
sys.path.insert(0, 'C:/xampp/htdocs/GitHub/SOME-PackagingAssistant')
import numpy as np
from packer3d import *

mesh = make_test_triangle()
box_dims = (100, 100, 100)
orientations = generate_orientations(mesh, n_yaw=4, use_roll_flip=True)
print(f"Orientations:")
for op in orientations:
    print(f"  {op.name}: size={op.size}, aabb={op.aabb.tolist()}")

# Run pack step by step with verbose output
box_l, box_w, box_h = box_dims
scored_orientations = []
for op in orientations:
    flat_score = compute_flat_base_score(op.mesh)
    scored_orientations.append((flat_score, op.size[1], op))
scored_orientations.sort(key=lambda x: (-x[0], x[1]))

grid = SpatialGrid(cell_size=20)
step = 100  # Large step to simplify

placed = []
for i in range(20):
    best_score = float('inf')
    best_op = None
    best_x = best_y = best_z = 0.0

    for _, _, orient in scored_orientations:
        sx, sy, sz = orient.size
        for ix in range(int((box_l - sx) / step) + 1):
            x = ix * step
            for iz in range(int((box_w - sz) / step) + 1):
                z = iz * step

                # Compute min_y
                min_x = x + orient.aabb[0, 0]
                max_x = x + orient.aabb[1, 0]
                min_z = z + orient.aabb[0, 2]
                max_z = z + orient.aabb[1, 2]
                neighbors = grid.query_xz(min_x, max_x, min_z, max_z)
                
                y = 0.0
                for nidx in neighbors:
                    other = grid.pieces[nidx]
                    if max_x > other.aabb[0, 0] and min_x < other.aabb[1, 0]:
                        if max_z > other.aabb[0, 2] and min_z < other.aabb[1, 2]:
                            y = max(y, other.aabb[1, 1])

                if i < 5:
                    print(f"  i={i} {orient.name} x={x} z={z}: neighbors={len(neighbors)} min_y={y} sy={sy} box_h={box_h} fits={y+sy <= box_h}")

                if y + sy > box_h:
                    continue

                score = y * 1000
                if score < best_score:
                    best_score = score
                    best_op = orient
                    best_x, best_y, best_z = x, y, z

    if best_op is None:
        print(f"Piece {i}: no position found, breaking")
        break

    pp = PlacedPiece(
        mesh=best_op.mesh.copy(),
        aabb=np.array([
            [best_x + best_op.aabb[0, 0], best_y + best_op.aabb[0, 1], best_z + best_op.aabb[0, 2]],
            [best_x + best_op.aabb[1, 0], best_y + best_op.aabb[1, 1], best_z + best_op.aabb[1, 2]],
        ]),
        position=np.array([best_x, best_y, best_z]),
        orient_name=best_op.name,
    )

    print(f"Piece {i}: {best_op.name} at ({best_x:.0f}, {best_y:.0f}, {best_z:.0f}) AABB=[{pp.aabb[0].tolist()}, {pp.aabb[1].tolist()}]")

    # Check that it doesn't overlap with any placed piece
    if i > 0:
        for j, other in enumerate(placed):
            if (pp.aabb[1, 0] > other.aabb[0, 0] and pp.aabb[0, 0] < other.aabb[1, 0] and
                pp.aabb[1, 1] > other.aabb[0, 1] and pp.aabb[0, 1] < other.aabb[1, 1] and
                pp.aabb[1, 2] > other.aabb[0, 2] and pp.aabb[0, 2] < other.aabb[1, 2]):
                print(f"  WARNING: AABB overlap with piece {j}!")

    placed.append(pp)
    grid.add(pp)

# Final verify
print(f"\nFinal: {len(placed)} pieces placed")
ok, overlaps = verify_no_overlap(placed)
print(f"No overlap: {ok}, overlaps: {overlaps}")
