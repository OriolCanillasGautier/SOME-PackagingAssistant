"""
world.py — Physics world orchestrator.

Manages the full physics pipeline:
  broad phase → narrow phase (SAT) → contact generation → dynamics solver
"""
import time
import numpy as np

from .hull import HullData, compute_hull, hull_from_stl
from .collision import CollisionDetector
from .broadphase import BroadPhase
from .contacts import ContactGenerator
from .dynamics import DynamicsSolver


class World:
    """GPU-accelerated physics world."""

    def __init__(self, cell_size=50.0, gravity=(0, -9810, 0),
                 vibration_amplitude=0.0, vibration_frequency=0.0):
        self.gravity = tuple(gravity)
        self.cell_size = cell_size
        self.vibration_amplitude = vibration_amplitude
        self.vibration_frequency = vibration_frequency
        self.bodies: list[dict] = []
        self.hulls: list[HullData] = []
        self._collision_detector = None
        self._broadphase = None
        self._contact_generator = ContactGenerator()
        self._dynamics = None
        self._step_count = 0
        self._stats = {"broad_ms": 0, "narrow_ms": 0, "contacts_ms": 0, "solve_ms": 0}

        # Cached state from last step
        self._last_positions = None
        self._last_aabbs = None

    def add_body(self, stl_path=None, hull: HullData = None, position=(0, 0, 0),
                 quaternion=(0, 0, 0, 1), mass=1.0, name=""):
        if hull is None and stl_path is not None:
            hull = hull_from_stl(stl_path, name=name or stl_path)
        if hull is None:
            raise ValueError("Either stl_path or hull must be provided")

        body_idx = len(self.bodies)
        pos = np.array(position, dtype=np.float64)
        quat = np.array(quaternion, dtype=np.float64)
        aabb_min = hull.aabb_min + pos
        aabb_max = hull.aabb_max + pos
        volume = hull.volume
        if mass > 0 and volume > 0:
            radius_eq = (3 * volume / (4 * np.pi)) ** (1 / 3)
            I = 0.4 * mass * radius_eq * radius_eq
        else:
            I = 1.0

        body = {
            "hull_idx": body_idx,
            "hull": hull,
            "position": pos,
            "quaternion": quat,
            "mass": mass,
            "inertia": (I, I, I),
            "aabb_min": aabb_min,
            "aabb_max": aabb_max,
            "name": name or hull.name,
        }
        self.bodies.append(body)
        self.hulls.append(hull)
        self._collision_detector = None
        self._dynamics = None
        return body_idx

    def _init_engine(self):
        if self._collision_detector is not None:
            return
        self._collision_detector = CollisionDetector(self.hulls)
        self._broadphase = BroadPhase(cell_size=self.cell_size)
        n = len(self.bodies)
        self._dynamics = DynamicsSolver(n)
        self._dynamics._vibration_amplitude = self.vibration_amplitude
        self._dynamics._vibration_frequency = self.vibration_frequency
        for i, b in enumerate(self.bodies):
            self._dynamics.set_body(
                i, b["position"], b["quaternion"],
                b["mass"], b["inertia"],
                b["aabb_min"], b["aabb_max"],
            )

    def step(self, dt=1/60, n_solver_iterations=4, baumgarte=0.2):
        self._init_engine()
        n = len(self.bodies)
        if n == 0:
            return

        t_frame = time.time()

        # 1. Integrate
        self._dynamics.integrate(gravity=self.gravity, dt=dt,
                                 damping_linear=0.05, damping_angular=0.05)

        # 2. Ground constraint (with vibration for granular compaction)
        self._dynamics.apply_ground(ground_y=0.0,
                                    time=self._step_count * dt)

        # 3. Update AABBs
        self._dynamics.update_aabbs(
            self._collision_detector.d_hverts,
            self._collision_detector.d_hvcts,
            self._collision_detector.max_verts,
        )

        # 4. Download needed state (avoid double download)
        positions, quaternions, aabb_min, aabb_max = self._dynamics.get_positions_aabbs()
        self._last_positions = positions
        self._last_aabbs = (aabb_min, aabb_max)

        # 5. Broad phase
        t0 = time.time()
        pairs = self._broadphase.find_pairs(aabb_min, aabb_max)
        self._stats["broad_ms"] = (time.time() - t0) * 1000

        # 6. Narrow phase
        t0 = time.time()
        if len(pairs) > 0:
            collision_results = self._collision_detector.collide(positions, quaternions, pairs)
        else:
            collision_results = np.zeros((0, 4), dtype=np.float64)
        self._stats["narrow_ms"] = (time.time() - t0) * 1000

        # 7. Contact generation
        t0 = time.time()
        contacts = np.zeros((0, 8), dtype=np.float64)
        if len(collision_results) > 0:
            overlapping = collision_results[:, 0] > 0.0
            if overlapping.any():
                ov_pairs = pairs[overlapping]
                ov_results = collision_results[overlapping]
                contacts = self._contact_generator.generate(
                    ov_results, ov_pairs, positions, aabb_min, aabb_max,
                )
        self._stats["contacts_ms"] = (time.time() - t0) * 1000

        # 8. Resolve contacts
        t0 = time.time()
        self._dynamics.solve_contacts(contacts, dt, baumgarte=baumgarte,
                                      n_iterations=n_solver_iterations)
        self._dynamics.clamp_velocities()
        self._stats["solve_ms"] = (time.time() - t0) * 1000

        self._step_count += 1
        total_ms = (time.time() - t_frame) * 1000
        self._stats["total_ms"] = total_ms

    def get_state(self):
        if self._dynamics is None:
            return {"step": 0, "bodies": [], "stats": dict(self._stats)}
        dyn_state = self._dynamics.get_state()
        bodies = []
        for i, b in enumerate(self.bodies):
            bodies.append({
                "name": b["name"],
                "position": dyn_state["positions"][i].tolist(),
                "quaternion": dyn_state["quaternions"][i].tolist(),
                "aabb_min": dyn_state["aabb_min"][i].tolist(),
                "aabb_max": dyn_state["aabb_max"][i].tolist(),
                "velocity": dyn_state["velocities"][i].tolist(),
                "mass": b["mass"],
            })
        return {
            "step": self._step_count,
            "bodies": bodies,
            "stats": dict(self._stats),
        }

    def get_stats(self):
        return dict(self._stats)
