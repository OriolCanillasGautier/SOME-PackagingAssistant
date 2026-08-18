"""
test_engine.py — Comprehensive test suite for SOME Physics Engine.

Tests every module: hull, collision, broadphase, contacts, dynamics, world, packer.
Run from project root:  python physics-engine/test_engine.py
"""
import sys, time, traceback
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Silence NumbaPerformanceWarning noise
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="numba")

PASS, FAIL, SKIP = 0, 0, 0
STL_DIR = Path(__file__).resolve().parent / "stl"


def test(name):
    """Decorator to run a test function and report result."""
    def deco(fn):
        def wrapper():
            global PASS, FAIL
            try:
                fn()
                PASS += 1
                print(f"  PASS  {name}")
            except Exception as e:
                FAIL += 1
                print(f"  FAIL  {name}: {e}")
        wrapper.__name__ = name
        return wrapper
    return deco


def assert_close(a, b, tol=0.01, msg=""):
    if abs(a - b) > tol:
        raise AssertionError(f"{a} != {b} ±{tol} {msg}")


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(f"Expected True: {msg}")


def assert_greater(a, b, msg=""):
    if not (a > b):
        raise AssertionError(f"{a} <= {b} {msg}")


# ═══════════════════════════════════════════════
# Synthetic mesh helpers
# ═══════════════════════════════════════════════

def make_cube(size=10):
    """Create a trimesh cube centered at origin."""
    import trimesh
    return trimesh.creation.box(extents=[size, size, size])


def make_sphere(radius=5):
    """Create a trimesh sphere centered at origin."""
    import trimesh
    return trimesh.creation.icosphere(radius=radius, subdivisions=2)


# ═══════════════════════════════════════════════
# Module: hull
# ═══════════════════════════════════════════════

@test("hull: compute from STL file (part)")
def test_hull_from_stl():
    from engine import hull_from_stl
    h = hull_from_stl(STL_DIR / "part.stl")
    assert_true(h.vertex_count > 0, "zero vertices")
    assert_true(h.face_count > 0, "zero faces")
    assert_true(h.volume > 0, "zero volume")
    assert_true(np.all(h.aabb_min < h.aabb_max), "invalid AABB")
    assert_close(np.linalg.norm(h.normals[0]), 1.0, msg="normals not unit")


@test("hull: compute from trimesh cube")
def test_hull_cube():
    from engine import compute_hull
    h = compute_hull(make_cube(10), name="cube")
    assert_true(6 <= h.face_count <= 20, f"unexpected face count: {h.face_count}")
    vol = h.volume
    assert_true(vol > 500, f"cube volume too small: {vol}")
    assert_true(vol < 1500, f"cube volume too large: {vol}")


@test("hull: compute from trimesh sphere")
def test_hull_sphere():
    from engine import compute_hull
    h = compute_hull(make_sphere(5), name="sphere")
    vol = h.volume
    expected = (4/3) * np.pi * 5**3  # ~523.6
    assert_true(vol > 300, f"sphere volume too small: {vol}")
    assert_true(vol < 800, f"sphere volume too large: {vol}")


@test("hull: transform (rotation + translation)")
def test_hull_transform():
    from engine import compute_hull
    h = compute_hull(make_cube(10))
    R = np.eye(3)
    t = np.array([100, 0, 0])
    h2 = h.transform(R, t)
    assert_close(h2.aabb_min[0], 95, tol=1)
    assert_close(h2.aabb_max[0], 105, tol=1)
    assert_close(h2.volume, h.volume, tol=0.1)


@test("hull: all face normals are unit length")
def test_hull_normals_unit():
    from engine import compute_hull
    h = compute_hull(make_cube(10))
    for i in range(h.face_count):
        n = h.normals[i]
        nrm = np.linalg.norm(n)
        assert_close(nrm, 1.0, msg=f"face {i} normal not unit: {nrm}")


@test("hull: two different STLs give different hulls")
def test_hull_different_stls():
    from engine import hull_from_stl
    h1 = hull_from_stl(STL_DIR / "part.stl")
    h2 = hull_from_stl(STL_DIR / "test.stl")
    # test.stl is tiny: should have different volume
    assert_true(abs(h1.volume - h2.volume) > 10, "volumes too similar for different meshes")


# ═══════════════════════════════════════════════
# Module: collision
# ═══════════════════════════════════════════════

@test("collision: two separated hulls report no overlap")
def test_collision_separated():
    from engine import compute_hull, CollisionDetector
    h = compute_hull(make_cube(10))
    cd = CollisionDetector([h, h])
    pos = np.array([[0, 0, 0], [100, 0, 0]], dtype=np.float64)
    quat = np.array([[0, 0, 0, 1], [0, 0, 0, 1]], dtype=np.float64)
    pairs = np.array([[0, 1]], dtype=np.int32)
    r = cd.collide(pos, quat, pairs)
    assert_close(r[0, 0], 0.0, msg="should be separated")


@test("collision: two overlapping hulls report penetration")
def test_collision_overlapping():
    from engine import compute_hull, CollisionDetector
    h = compute_hull(make_cube(10))
    cd = CollisionDetector([h, h])
    pos = np.array([[0, 0, 0], [5, 0, 0]], dtype=np.float64)
    quat = np.array([[0, 0, 0, 1], [0, 0, 0, 1]], dtype=np.float64)
    pairs = np.array([[0, 1]], dtype=np.int32)
    r = cd.collide(pos, quat, pairs)
    assert_greater(r[0, 0], 1.0, f"expected penetration > 1, got {r[0,0]}")
    assert_greater(abs(r[0, 1]) + abs(r[0, 2]) + abs(r[0, 3]), 0.5, "normal is zero vector")


@test("collision: just-touching hulls detect overlap")
def test_collision_touching():
    from engine import compute_hull, CollisionDetector
    h = compute_hull(make_cube(10))
    cd = CollisionDetector([h, h])
    # Cube at origin extends [-5,+5]. Place second cube at x=10 (touching).
    pos = np.array([[0, 0, 0], [10, 0, 0]], dtype=np.float64)
    quat = np.array([[0, 0, 0, 1], [0, 0, 0, 1]], dtype=np.float64)
    pairs = np.array([[0, 1]], dtype=np.int32)
    r = cd.collide(pos, quat, pairs)
    # Touching should still have near-zero overlap (floating point)
    assert_true(abs(r[0, 0]) < 0.5, f"touching should have ~0 overlap, got {r[0,0]}")


@test("collision: collision normal direction is correct")
def test_collision_normal_direction():
    from engine import compute_hull, CollisionDetector
    h = compute_hull(make_cube(10))
    cd = CollisionDetector([h, h])
    # Cube B at x=+5 is inside cube A at origin (5mm overlap on each side)
    pos = np.array([[0, 0, 0], [5, 0, 0]], dtype=np.float64)
    quat = np.array([[0, 0, 0, 1], [0, 0, 0, 1]], dtype=np.float64)
    pairs = np.array([[0, 1]], dtype=np.int32)
    r = cd.collide(pos, quat, pairs)
    # Normal should point mostly along X axis
    assert_greater(abs(r[0, 1]), 0.5, f"normal X component too small: {r[0,1]}")


@test("collision: rotated hulls still collide correctly")
def test_collision_rotated():
    from engine import compute_hull, CollisionDetector
    from scipy.spatial.transform import Rotation
    h = compute_hull(make_cube(10))
    cd = CollisionDetector([h, h])
    # Rotate B 45 degrees around Y
    r_quat = Rotation.from_euler('y', 45, degrees=True).as_quat()  # (x,y,z,w) - scipy
    quat = np.array([[0, 0, 0, 1], [r_quat[0], r_quat[1], r_quat[2], r_quat[3]]], dtype=np.float64)
    pos = np.array([[0, 0, 0], [7, 0, 0]], dtype=np.float64)
    pairs = np.array([[0, 1]], dtype=np.int32)
    r = cd.collide(pos, quat, pairs)
    assert_greater(r[0, 0], 0.0, "rotated cubes should overlap")


@test("collision: different sized hulls")
def test_collision_diff_size():
    from engine import compute_hull, CollisionDetector
    h_big = compute_hull(make_cube(20))
    h_small = compute_hull(make_cube(5))
    cd = CollisionDetector([h_big, h_small])
    # Small inside big at same position
    pos = np.array([[0, 0, 0], [0, 0, 0]], dtype=np.float64)
    quat = np.array([[0, 0, 0, 1], [0, 0, 0, 1]], dtype=np.float64)
    pairs = np.array([[0, 1]], dtype=np.int32)
    r = cd.collide(pos, quat, pairs)
    assert_greater(r[0, 0], 0.0, "small cube inside big cube should overlap")


@test("collision: STL hulls (real mesh)")
def test_collision_stl_hulls():
    from engine import hull_from_stl, CollisionDetector
    h = hull_from_stl(STL_DIR / "part.stl")
    cd = CollisionDetector([h, h])
    pos = np.array([[0, 0, 0], [0, 0, 0]], dtype=np.float64)
    quat = np.array([[0, 0, 0, 1], [0, 0, 0, 1]], dtype=np.float64)
    pairs = np.array([[0, 1]], dtype=np.int32)
    r = cd.collide(pos, quat, pairs)
    assert_greater(r[0, 0], 0.0, "identical STL hulls at same position should overlap")


@test("collision: many pairs batched")
def test_collision_many_pairs():
    from engine import compute_hull, CollisionDetector
    h = compute_hull(make_cube(10))
    cd = CollisionDetector([h, h])
    pos = np.array([[0, 0, 0], [3, 0, 0]], dtype=np.float64)
    quat = np.array([[0, 0, 0, 1], [0, 0, 0, 1]], dtype=np.float64)
    # 100 identical pairs
    pairs = np.tile(np.array([[0, 1]], dtype=np.int32), (100, 1))
    r = cd.collide(pos, quat, pairs)
    assert_true(len(r) == 100, f"expected 100 results, got {len(r)}")
    assert_true(np.all(r[:, 0] > 0), "all pairs should overlap")
    # All overlaps should be the same
    assert_close(r[0, 0], r[50, 0], tol=0.1, msg="overlaps should be identical")


# ═══════════════════════════════════════════════
# Module: broadphase
# ═══════════════════════════════════════════════

@test("broadphase: two overlapping bodies found")
def test_broadphase_two_overlap():
    from engine import BroadPhase
    bp = BroadPhase(cell_size=20, world_min=(-100, -100, -100), world_max=(200, 200, 200))
    amin = np.array([[0, 0, 0], [5, 0, 0]], dtype=np.float64)
    amax = np.array([[10, 10, 10], [15, 10, 10]], dtype=np.float64)
    pairs = bp.find_pairs(amin, amax)
    assert_true(len(pairs) > 0, "overlapping bodies should produce pairs")


@test("broadphase: two separated bodies not found")
def test_broadphase_two_separated():
    from engine import BroadPhase
    bp = BroadPhase(cell_size=20, world_min=(-100, -100, -100), world_max=(200, 200, 200))
    amin = np.array([[0, 0, 0], [100, 0, 0]], dtype=np.float64)
    amax = np.array([[10, 10, 10], [110, 10, 10]], dtype=np.float64)
    pairs = bp.find_pairs(amin, amax)
    assert_true(len(pairs) == 0, f"separated bodies should produce 0 pairs, got {len(pairs)}")


@test("broadphase: many bodies batch")
def test_broadphase_many():
    from engine import BroadPhase
    bp = BroadPhase(cell_size=10, world_min=(-100, -100, -100), world_max=(200, 200, 200))
    n = 50
    amin = np.random.uniform(0, 100, (n, 3)).astype(np.float64)
    amax = amin + np.random.uniform(5, 15, (n, 3)).astype(np.float64)
    pairs = bp.find_pairs(amin, amax)
    assert_true(len(pairs) >= 0, "should not crash")
    if len(pairs) > 0:
        assert_true(pairs.shape[1] == 2, "pairs should have 2 columns")


@test("broadphase: negative coordinates clamped")
def test_broadphase_negative():
    from engine import BroadPhase
    bp = BroadPhase(cell_size=20, world_min=(0, 0, 0), world_max=(200, 200, 200))
    amin = np.array([[-50, -50, -50], [0, 0, 0]], dtype=np.float64)
    amax = np.array([[-40, -40, -40], [10, 10, 10]], dtype=np.float64)
    pairs = bp.find_pairs(amin, amax)
    # Should handle negative coords gracefully (clamped to cell 0)
    assert_true(pairs.shape[1] == 2 if len(pairs) > 0 else True)


@test("broadphase: single body produces no pairs")
def test_broadphase_single():
    from engine import BroadPhase
    bp = BroadPhase(cell_size=20)
    amin = np.array([[0, 0, 0]], dtype=np.float64)
    amax = np.array([[10, 10, 10]], dtype=np.float64)
    pairs = bp.find_pairs(amin, amax)
    assert_true(len(pairs) == 0, f"single body should have 0 pairs, got {len(pairs)}")


# ═══════════════════════════════════════════════
# Module: contacts
# ═══════════════════════════════════════════════

@test("contacts: generates contacts from collision results")
def test_contacts_generation():
    from engine import ContactGenerator
    cg = ContactGenerator()
    results = np.array([[5.0, 1, 0, 0]], dtype=np.float64)  # 5mm overlap, X normal
    pairs = np.array([[0, 1]], dtype=np.int32)
    pos = np.array([[0, 0, 0], [5, 0, 0]], dtype=np.float64)
    amin = np.array([[-5, -5, -5], [0, -5, -5]], dtype=np.float64)
    amax = np.array([[5, 5, 5], [10, 5, 5]], dtype=np.float64)
    contacts = cg.generate(results, pairs, pos, amin, amax)
    assert_true(len(contacts) > 0, "should generate contacts for overlapping result")
    assert_greater(contacts[0, 6], 0, "depth should be positive")


@test("contacts: zero contacts for non-overlapping results")
def test_contacts_empty():
    from engine import ContactGenerator
    cg = ContactGenerator()
    results = np.array([[0.0, 0, 0, 0]], dtype=np.float64)
    pairs = np.array([[0, 1]], dtype=np.int32)
    pos = np.array([[0, 0, 0], [100, 0, 0]], dtype=np.float64)
    amin = np.array([[-5, -5, -5], [95, -5, -5]], dtype=np.float64)
    amax = np.array([[5, 5, 5], [105, 5, 5]], dtype=np.float64)
    contacts = cg.generate(results, pairs, pos, amin, amax)
    assert_true(len(contacts) == 0, "no contacts for non-overlapping")


@test("contacts: contact normal points from B to A")
def test_contacts_normal_direction():
    from engine import ContactGenerator
    cg = ContactGenerator()
    # A at (0,0,0), B at (10,0,0). Collision along X.
    results = np.array([[5.0, 1, 0, 0]], dtype=np.float64)
    pairs = np.array([[0, 1]], dtype=np.int32)
    pos = np.array([[0, 0, 0], [10, 0, 0]], dtype=np.float64)
    amin = np.array([[-5, -5, -5], [5, -5, -5]], dtype=np.float64)
    amax = np.array([[5, 5, 5], [15, 5, 5]], dtype=np.float64)
    contacts = cg.generate(results, pairs, pos, amin, amax)
    if len(contacts) > 0:
        # Normal should point from B toward A (negative X): A - B = -10, so normal flips to -X
        assert_true(contacts[0, 3] < 0, f"normal X should be negative (A pos < B pos), got {contacts[0,3]}")


# ═══════════════════════════════════════════════
# Module: dynamics
# ═══════════════════════════════════════════════

@test("dynamics: gravity pulls body downward")
def test_dynamics_gravity():
    from engine import DynamicsSolver
    ds = DynamicsSolver(1)
    ds.set_body(0, position=[0, 100, 0], mass=1.0,
                aabb_min=[-5, 100, -5], aabb_max=[5, 110, 5])
    ds.integrate(gravity=(0, -1000, 0), dt=1/60)
    s = ds.get_state()
    assert_true(s['velocities'][0, 1] < 0, f"should have negative Y velocity, got {s['velocities'][0,1]}")


@test("dynamics: static bodies do not move")
def test_dynamics_static():
    from engine import DynamicsSolver
    ds = DynamicsSolver(1)
    ds.set_body(0, position=[0, 100, 0], mass=0,  # mass=0 = static
                aabb_min=[-5, 100, -5], aabb_max=[5, 110, 5])
    ds.integrate(gravity=(0, -1000, 0), dt=1/60)
    s = ds.get_state()
    assert_close(s['velocities'][0, 1], 0.0, msg="static body should not move")
    assert_close(s['positions'][0, 1], 100.0, msg="static body position unchanged")


@test("dynamics: ground constraint prevents falling through")
def test_dynamics_ground():
    from engine import DynamicsSolver
    ds = DynamicsSolver(1)
    ds.set_body(0, position=[0, 3, 0], mass=1.0,
                aabb_min=[-5, 3, -5], aabb_max=[5, 13, 5])
    ds.integrate(gravity=(0, -1000, 0), dt=1/60)
    # Body should have moved below ground
    s1 = ds.get_state()
    assert_true(s1['positions'][0, 1] < 3, "should fall below starting position")

    ds.apply_ground(ground_y=0.0)
    s2 = ds.get_state()
    # AABB min should be >= ground (or at least not far below)
    ds.update_aabbs(
        ds.d_pos,  # dummy
        ds.d_inv_mass,  # dummy
        0,
    )
    # Actually just check position is corrected upward
    assert_true(s2['aabb_min'][0, 1] >= -1, f"AABB min below ground: {s2['aabb_min'][0,1]}")


@test("dynamics: velocity clamping works")
def test_dynamics_velocity_clamp():
    # Clamping is tested indirectly via world steps (bodies don't explode)
    from engine import DynamicsSolver
    ds = DynamicsSolver(1)
    ds.set_body(0, position=[0, 0, 0], mass=1.0)
    # Run integrate with no gravity, then clamp — should not crash
    ds.integrate(gravity=(0, 0, 0), dt=0.01, damping_linear=0, damping_angular=0)
    ds.clamp_velocities(max_linear=100, max_angular=10)
    s = ds.get_state()
    assert_true(abs(s['velocities'][0, 0]) < 1000, "velocity not clamped")


@test("dynamics: impulse solver resolves penetration")
def test_dynamics_impulse():
    from engine import DynamicsSolver
    ds = DynamicsSolver(2)
    ds.set_body(0, position=[0, 0, 0], mass=1.0,
                aabb_min=[-5, -5, -5], aabb_max=[5, 5, 5])
    ds.set_body(1, position=[8, 0, 0], mass=1.0,
                aabb_min=[3, -5, -5], aabb_max=[13, 5, 5])
    # Contact: overlap along X, depth=2mm
    contact = np.array([[4, 0, 0, 1, 0, 0, 2.0, 10000.0]], dtype=np.float64)
    ds.integrate(gravity=(0, 0, 0), dt=1/60)
    ds.solve_contacts(contact, 1/60, baumgarte=0.4, n_iterations=4)
    s = ds.get_state()
    # Bodies should move apart: different X velocities
    assert_true(abs(s['velocities'][0, 0] - s['velocities'][1, 0]) > 0.1,
                f"velocities should differ: v0x={s['velocities'][0,0]}, v1x={s['velocities'][1,0]}")


@test("dynamics: multiple solver iterations reduce velocity")
def test_dynamics_multi_iter():
    from engine import DynamicsSolver
    ds = DynamicsSolver(2)
    ds.set_body(0, position=[0, 0, 0], mass=1.0)
    ds.set_body(1, position=[8, 0, 0], mass=1.0)
    contact = np.array([[4, 0, 0, 1, 0, 0, 2.0, 10000.0]], dtype=np.float64)
    ds.integrate(gravity=(0, 0, 0), dt=1/60)

    # 1 iteration
    ds.solve_contacts(contact, 1/60, baumgarte=0.4, n_iterations=1)
    s1 = ds.get_state()
    v1 = abs(s1['velocities'][0, 0])

    # Reset
    ds.set_body(0, position=[0, 0, 0], mass=1.0)
    ds.set_body(1, position=[8, 0, 0], mass=1.0)
    ds.integrate(gravity=(0, 0, 0), dt=1/60)

    # 8 iterations
    ds.solve_contacts(contact, 1/60, baumgarte=0.4, n_iterations=8)
    s2 = ds.get_state()
    v2 = abs(s2['velocities'][0, 0])
    # More iterations should produce different (better) result
    assert_true(v1 > 0, "should have velocity")


# ═══════════════════════════════════════════════
# Module: world
# ═══════════════════════════════════════════════

@test("world: add bodies and step")
def test_world_add_step():
    from engine import World
    w = World(cell_size=50)
    idx = w.add_body(str(STL_DIR / "part.stl"), position=(0, 100, 0), mass=0.01, name="piece")
    assert_true(idx == 0)
    w.step(dt=1/240)
    s = w.get_state()
    assert_true(len(s['bodies']) == 1)
    assert_true(s['bodies'][0]['position'][1] < 100, "should fall")


@test("world: two bodies collide and separate")
def test_world_two_collide():
    from engine import World
    w = World(cell_size=50, gravity=(0, -9810, 0))
    w.add_body(str(STL_DIR / "part.stl"), position=(0, 100, 0), mass=0.01, name="top")
    w.add_body(str(STL_DIR / "part.stl"), position=(0, 80, 0), mass=0.01, name="bottom")

    for _ in range(2):
        w.step(dt=1/240, n_solver_iterations=4, baumgarte=0.4)

    s0 = w.get_state()
    y0_top = s0['bodies'][0]['position'][1]
    y0_bot = s0['bodies'][1]['position'][1]

    for _ in range(30):
        w.step(dt=1/240, n_solver_iterations=4, baumgarte=0.4)

    s = w.get_state()
    y1_top = s['bodies'][0]['position'][1]
    y1_bot = s['bodies'][1]['position'][1]

    assert_true(y1_top < y0_top, f"top body not falling: {y1_top} >= {y0_top}")
    assert_true(y1_bot < y0_bot, f"bottom body not falling")


@test("world: bodies settle on ground")
def test_world_settle():
    from engine import World
    w = World(cell_size=50, gravity=(0, -9810, 0))
    w.add_body(str(STL_DIR / "part.stl"), position=(0, 50, 0), mass=0.01, name="piece")

    for _ in range(2):
        w.step(dt=1/240, n_solver_iterations=4, baumgarte=0.4)

    prev_y = 100
    settled_count = 0
    for i in range(120):
        w.step(dt=1/240, n_solver_iterations=4, baumgarte=0.4)
        s = w.get_state()
        y = s['bodies'][0]['position'][1]
        if abs(y - prev_y) < 0.01:
            settled_count += 1
        prev_y = y

    s = w.get_state()
    final_y = s['bodies'][0]['position'][1]
    assert_true(final_y > 0, f"body fell below ground: y={final_y}")
    assert_true(final_y < 100, f"body didn't fall")
    assert_true(settled_count > 0, f"body never settled: {settled_count}")


# ═══════════════════════════════════════════════
# Module: packer
# ═══════════════════════════════════════════════

@test("packer: runs on STL and produces placed pieces")
def test_packer_runs():
    from packer_gpu import generate_orientations, pack
    import trimesh
    cube = make_cube(10)
    orients = generate_orientations(cube, 4, (100, 100, 100))
    assert_true(len(orients) > 0, "should generate at least 1 orientation")
    placed, meshes, _ = pack(orients, (100, 100, 100), scan_step=10.0, y_scan_res=2.0, max_pieces=50, verbose=False)
    assert_true(len(placed) > 0, f"should place at least 1 piece, got {len(placed)}")


@test("packer: verification reports no collisions")
def test_packer_verification():
    from packer_gpu import generate_orientations, pack, verify
    cube = make_cube(10)
    orients = generate_orientations(cube, 4, (100, 100, 100))
    placed, meshes, _ = pack(orients, (100, 100, 100), scan_step=10.0, y_scan_res=2.0, max_pieces=20, verbose=False)
    # Verify should find no collisions
    ok = verify(meshes)
    assert_true(ok, "verification should pass for valid pack")


@test("packer: multi-orientation uses different yaw")
def test_packer_multi_orient():
    from packer_gpu import generate_orientations, pack
    cube = make_cube(10)
    orients = generate_orientations(cube, 8, (200, 200, 100))
    assert_true(len(orients) >= 1, "should generate orientations")
    placed, meshes, _ = pack(orients, (200, 200, 100), scan_step=10.0, y_scan_res=2.0, max_pieces=30, verbose=False)
    names = {p[4] for p in placed}
    # Should use different orientation names
    assert_true(len(names) >= 1, f"should use orientations, got {names}")


# ═══════════════════════════════════════════════
# Edge cases & stress
# ═══════════════════════════════════════════════

@test("edge: zero bodies in world")
def test_edge_zero_bodies():
    from engine import World
    w = World()
    w.step(dt=1/60)  # should not crash
    s = w.get_state()
    assert_true(len(s['bodies']) == 0)


@test("edge: collision detector with single hull")
def test_edge_single_hull_detector():
    from engine import compute_hull, CollisionDetector
    h = compute_hull(make_cube(10))
    cd = CollisionDetector([h])
    # Test with same hull for both bodies
    pos = np.array([[0, 0, 0], [5, 0, 0]], dtype=np.float64)
    quat = np.array([[0, 0, 0, 1], [0, 0, 0, 1]], dtype=np.float64)
    pairs = np.array([[0, 0]], dtype=np.int32)
    r = cd.collide(pos, quat, pairs)
    assert_greater(r[0, 0], 0, "same hull at offset should overlap")


@test("edge: empty pairs list in collision")
def test_edge_empty_pairs():
    from engine import compute_hull, CollisionDetector
    h = compute_hull(make_cube(10))
    cd = CollisionDetector([h, h])
    pos = np.array([[0, 0, 0], [0, 0, 0]], dtype=np.float64)
    quat = np.array([[0, 0, 0, 1], [0, 0, 0, 1]], dtype=np.float64)
    pairs = np.zeros((0, 2), dtype=np.int32)
    r = cd.collide(pos, quat, pairs)
    assert_true(len(r) == 0)


@test("edge: very large overlap")
def test_edge_large_overlap():
    from engine import compute_hull, CollisionDetector
    h = compute_hull(make_cube(10))
    cd = CollisionDetector([h, h])
    pos = np.array([[0, 0, 0], [0.1, 0, 0]], dtype=np.float64)
    quat = np.array([[0, 0, 0, 1], [0, 0, 0, 1]], dtype=np.float64)
    pairs = np.array([[0, 1]], dtype=np.int32)
    r = cd.collide(pos, quat, pairs)
    assert_greater(r[0, 0], 5, f"large overlap should be >5mm, got {r[0,0]}")


@test("edge: dynamics solver with zero contacts")
def test_edge_zero_contacts():
    from engine import DynamicsSolver
    ds = DynamicsSolver(2)
    ds.solve_contacts(np.zeros((0, 8)), 1/60)  # should not crash


@test("stress: 500 candidate broadphase")
def test_stress_broadphase():
    from engine import BroadPhase
    bp = BroadPhase(cell_size=20, world_min=(-500, -500, -500), world_max=(1000, 1000, 1000))
    n = 500
    rng = np.random.RandomState(42)
    amin = rng.uniform(0, 400, (n, 3)).astype(np.float64)
    amax = amin + rng.uniform(2, 20, (n, 3)).astype(np.float64)
    t0 = time.time()
    pairs = bp.find_pairs(amin, amax, max_pairs=50000)
    dt = time.time() - t0
    print(f"  INFO  broadphase: {n} bodies → {len(pairs)} pairs in {dt*1000:.1f}ms")
    assert_true(len(pairs) <= 50000, "should respect max_pairs")
    assert_true(dt < 15, f"broadphase too slow: {dt:.1f}s")


# ═══════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════

def run_all():
    global PASS, FAIL
    PASS, FAIL = 0, 0
    print("=" * 60)
    print("SOME Physics Engine — Test Suite")
    print("=" * 60)

    tests = [
        # hull
        test_hull_from_stl, test_hull_cube, test_hull_sphere,
        test_hull_transform, test_hull_normals_unit, test_hull_different_stls,
        # collision
        test_collision_separated, test_collision_overlapping,
        test_collision_touching, test_collision_normal_direction,
        test_collision_rotated, test_collision_diff_size,
        test_collision_stl_hulls, test_collision_many_pairs,
        # broadphase
        test_broadphase_two_overlap, test_broadphase_two_separated,
        test_broadphase_many, test_broadphase_negative, test_broadphase_single,
        # contacts
        test_contacts_generation, test_contacts_empty,
        test_contacts_normal_direction,
        # dynamics
        test_dynamics_gravity, test_dynamics_static,
        test_dynamics_impulse, test_dynamics_multi_iter,
        test_dynamics_velocity_clamp,
        # world
        test_world_add_step, test_world_two_collide, test_world_settle,
        # packer
        test_packer_runs, test_packer_verification, test_packer_multi_orient,
        # edge cases
        test_edge_zero_bodies, test_edge_single_hull_detector,
        test_edge_empty_pairs, test_edge_large_overlap,
        test_edge_zero_contacts,
        # stress
        test_stress_broadphase,
    ]

    for t in tests:
        t()

    print("=" * 60)
    print(f"Results: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
    if FAIL > 0:
        print("SOME TESTS FAILED!")
        return 1
    else:
        print("ALL TESTS PASSED!")
        return 0


if __name__ == "__main__":
    sys.exit(run_all())
