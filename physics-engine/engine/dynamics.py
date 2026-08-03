"""
dynamics.py — GPU rigid body dynamics.

Semi-implicit Euler integration, gravity, damping,
Jacobi-style parallel impulse solver with Baumgarte stabilization,
ground-plane constraint, and velocity clamping.
"""
import numpy as np
import math
from numba import cuda


# ═══════════════════════════════════════════════
# GPU kernels
# ═══════════════════════════════════════════════

@cuda.jit
def _integrate_kernel(
    positions, quaternions,
    velocities, angular_vels,
    inv_mass,
    gravity, dt,
    damping_linear, damping_angular,
    n_bodies,
):
    idx = cuda.grid(1)
    if idx >= n_bodies:
        return
    im = inv_mass[idx]
    if im <= 0.0:
        return

    velocities[idx, 0] += gravity[0] * dt
    velocities[idx, 1] += gravity[1] * dt
    velocities[idx, 2] += gravity[2] * dt

    vl = 1.0 - damping_linear * dt
    va = 1.0 - damping_angular * dt
    if vl < 0.0: vl = 0.0
    if va < 0.0: va = 0.0
    velocities[idx, 0] *= vl
    velocities[idx, 1] *= vl
    velocities[idx, 2] *= vl
    angular_vels[idx, 0] *= va
    angular_vels[idx, 1] *= va
    angular_vels[idx, 2] *= va

    positions[idx, 0] += velocities[idx, 0] * dt
    positions[idx, 1] += velocities[idx, 1] * dt
    positions[idx, 2] += velocities[idx, 2] * dt

    wx = angular_vels[idx, 0]
    wy = angular_vels[idx, 1]
    wz = angular_vels[idx, 2]
    qx = quaternions[idx, 0]
    qy = quaternions[idx, 1]
    qz = quaternions[idx, 2]
    qw = quaternions[idx, 3]
    h = dt * 0.5
    qxn = qx + h * (wx * qw + wy * qz - wz * qy)
    qyn = qy + h * (wy * qw + wz * qx - wx * qz)
    qzn = qz + h * (wz * qw + wx * qy - wy * qx)
    qwn = qw + h * (-wx * qx - wy * qy - wz * qz)
    s2 = qxn*qxn + qyn*qyn + qzn*qzn + qwn*qwn
    inv = 1.0
    if s2 > 1e-12:
        s = s2 ** 0.5
        if s > 0.0:
            inv = 1.0 / s
    quaternions[idx, 0] = qxn * inv
    quaternions[idx, 1] = qyn * inv
    quaternions[idx, 2] = qzn * inv
    quaternions[idx, 3] = qwn * inv


@cuda.jit
def _update_aabbs_kernel(
    positions, quaternions,
    hull_verts, hull_vert_counts,
    aabb_min, aabb_max,
    n_bodies, max_verts,
):
    idx = cuda.grid(1)
    if idx >= n_bodies:
        return
    nv = hull_vert_counts[idx]
    if nv <= 0:
        return

    px, py, pz = positions[idx, 0], positions[idx, 1], positions[idx, 2]
    qx, qy, qz, qw = quaternions[idx, 0], quaternions[idx, 1], quaternions[idx, 2], quaternions[idx, 3]

    min_x = 1e30; min_y = 1e30; min_z = 1e30
    max_x = -1e30; max_y = -1e30; max_z = -1e30
    for v in range(nv):
        vx = hull_verts[idx, v, 0]
        vy = hull_verts[idx, v, 1]
        vz = hull_verts[idx, v, 2]
        tx = 2.0*(qy*vz - qz*vy); ty = 2.0*(qz*vx - qx*vz); tz = 2.0*(qx*vy - qy*vx)
        rx = vx + qw*tx + (qy*tz - qz*ty) + px
        ry = vy + qw*ty + (qz*tx - qx*tz) + py
        rz = vz + qw*tz + (qx*ty - qy*tx) + pz
        if rx < min_x: min_x = rx
        if rx > max_x: max_x = rx
        if ry < min_y: min_y = ry
        if ry > max_y: max_y = ry
        if rz < min_z: min_z = rz
        if rz > max_z: max_z = rz
    aabb_min[idx, 0] = min_x
    aabb_min[idx, 1] = min_y
    aabb_min[idx, 2] = min_z
    aabb_max[idx, 0] = max_x
    aabb_max[idx, 1] = max_y
    aabb_max[idx, 2] = max_z


@cuda.jit
def _ground_constraint_kernel(
    positions, velocities, inv_mass, aabb_min,
    ground_y, vibration_amplitude, vibration_frequency, time, n_bodies,
):
    idx = cuda.grid(1)
    if idx >= n_bodies:
        return
    im = inv_mass[idx]
    if im <= 0.0:
        return
    min_y = aabb_min[idx, 1]
    effective_ground = ground_y + vibration_amplitude * math.sin(time * vibration_frequency)
    if min_y < effective_ground:
        penetration = effective_ground - min_y
        positions[idx, 1] += penetration
        if velocities[idx, 1] < 0.0:
            velocities[idx, 1] = 0.0


@cuda.jit
def _clamp_velocity_kernel(velocities, angular_vels, inv_mass, max_linear, max_angular, n_bodies):
    idx = cuda.grid(1)
    if idx >= n_bodies:
        return
    if inv_mass[idx] <= 0.0:
        return
    v = velocities[idx]
    spd2 = v[0]*v[0] + v[1]*v[1] + v[2]*v[2]
    max2 = max_linear * max_linear
    if spd2 > max2:
        scale = max_linear / (spd2 ** 0.5)
        v[0] *= scale; v[1] *= scale; v[2] *= scale
    av = angular_vels[idx]
    aspd2 = av[0]*av[0] + av[1]*av[1] + av[2]*av[2]
    maxa2 = max_angular * max_angular
    if aspd2 > maxa2:
        scale = max_angular / (aspd2 ** 0.5)
        av[0] *= scale; av[1] *= scale; av[2] *= scale


@cuda.jit
def _solve_contacts_kernel(
    positions, quaternions,
    velocities, angular_vels,
    inv_mass, inv_inertia,
    contacts, contact_count, dt, baumgarte,
    n_bodies,
):
    idx = cuda.grid(1)
    if idx >= contact_count:
        return

    px = contacts[idx, 0]; py = contacts[idx, 1]; pz = contacts[idx, 2]
    nx = contacts[idx, 3]; ny = contacts[idx, 4]; nz = contacts[idx, 5]
    depth = contacts[idx, 6]
    packed = contacts[idx, 7]
    bi = int(packed) % 10000
    bj = int(packed / 10000.0)
    if bi >= n_bodies or bj >= n_bodies:
        return
    im_i = inv_mass[bi]; im_j = inv_mass[bj]
    if im_i <= 0.0 and im_j <= 0.0:
        return

    rix = px - positions[bi, 0]; riy = py - positions[bi, 1]; riz = pz - positions[bi, 2]
    rjx = px - positions[bj, 0]; rjy = py - positions[bj, 1]; rjz = pz - positions[bj, 2]

    wi = angular_vels[bi]
    vix = velocities[bi, 0] + wi[1]*riz - wi[2]*riy
    viy = velocities[bi, 1] + wi[2]*rix - wi[0]*riz
    viz = velocities[bi, 2] + wi[0]*riy - wi[1]*rix

    wj = angular_vels[bj]
    vjx = velocities[bj, 0] + wj[1]*rjz - wj[2]*rjy
    vjy = velocities[bj, 1] + wj[2]*rjx - wj[0]*rjz
    vjz = velocities[bj, 2] + wj[0]*rjy - wj[1]*rjx

    dvx = vix - vjx; dvy = viy - vjy; dvz = viz - vjz
    vn = dvx*nx + dvy*ny + dvz*nz

    bias = 0.0
    if depth > 0.0:
        bias = baumgarte / dt * max(0.0, depth - 0.001)
    if vn > -1e-6 and bias <= 0.0:
        return

    effective_mass = im_i + im_j
    if effective_mass < 1e-12:
        return

    jn = (-vn + bias) / effective_mass
    if jn < 0.0:
        jn = 0.0

    jx = jn * nx; jy = jn * ny; jz = jn * nz

    if im_i > 0.0:
        velocities[bi, 0] += jx * im_i
        velocities[bi, 1] += jy * im_i
        velocities[bi, 2] += jz * im_i
        iix = inv_inertia[bi, 0]; iiy = inv_inertia[bi, 1]; iiz = inv_inertia[bi, 2]
        angular_vels[bi, 0] += (riy*jz - riz*jy) * iix
        angular_vels[bi, 1] += (riz*jx - rix*jz) * iiy
        angular_vels[bi, 2] += (rix*jy - riy*jx) * iiz
    if im_j > 0.0:
        velocities[bj, 0] -= jx * im_j
        velocities[bj, 1] -= jy * im_j
        velocities[bj, 2] -= jz * im_j
        iix = inv_inertia[bj, 0]; iiy = inv_inertia[bj, 1]; iiz = inv_inertia[bj, 2]
        angular_vels[bj, 0] -= (rjy*jz - rjz*jy) * iix
        angular_vels[bj, 1] -= (rjz*jx - rjx*jz) * iiy
        angular_vels[bj, 2] -= (rjx*jy - rjy*jx) * iiz


# ═══════════════════════════════════════════════
# CPU interface
# ═══════════════════════════════════════════════

class DynamicsSolver:
    """GPU rigid body dynamics solver."""

    def __init__(self, n_bodies: int, max_contacts: int = 100000):
        self.n_bodies = n_bodies
        self.max_contacts = max_contacts
        self._max_linear = 5000.0   # mm/s
        self._max_angular = 50.0    # rad/s
        self._vibration_amplitude = 0.0
        self._vibration_frequency = 0.0

        # Keep CPU mirrors for efficient set_body
        self._pos = np.zeros((n_bodies, 3), dtype=np.float64)
        self._quat = np.zeros((n_bodies, 4), dtype=np.float64)
        self._quat[:, 3] = 1.0
        self._vel = np.zeros((n_bodies, 3), dtype=np.float64)
        self._avel = np.zeros((n_bodies, 3), dtype=np.float64)
        self._imass = np.zeros(n_bodies, dtype=np.float64)
        self._iinertia = np.zeros((n_bodies, 3), dtype=np.float64)
        self._amin = np.zeros((n_bodies, 3), dtype=np.float64)
        self._amax = np.zeros((n_bodies, 3), dtype=np.float64)

        self.d_pos = cuda.to_device(self._pos)
        self.d_quat = cuda.to_device(self._quat)
        self.d_vel = cuda.to_device(self._vel)
        self.d_avel = cuda.to_device(self._avel)
        self.d_inv_mass = cuda.to_device(self._imass)
        self.d_inv_inertia = cuda.to_device(self._iinertia)
        self.d_aabb_min = cuda.to_device(self._amin)
        self.d_aabb_max = cuda.to_device(self._amax)
        self.d_gravity = cuda.to_device(np.zeros(3, dtype=np.float64))
        self._d_contacts = None

        self._dirty = True

    def set_body(self, i, position, quaternion=None, mass=1.0, inertia=None,
                 aabb_min=None, aabb_max=None):
        self._pos[i] = position
        if quaternion is not None:
            self._quat[i] = quaternion
        else:
            self._quat[i] = [0, 0, 0, 1]
        self._imass[i] = 1.0 / mass if mass > 0 else 0.0
        if inertia is not None:
            self._iinertia[i] = [1.0/v if v > 0 else 0.0 for v in inertia]
        if aabb_min is not None:
            self._amin[i] = aabb_min
        if aabb_max is not None:
            self._amax[i] = aabb_max
        self._dirty = True

    def _upload(self):
        if not self._dirty:
            return
        self.d_pos = cuda.to_device(self._pos)
        self.d_quat = cuda.to_device(self._quat)
        self.d_vel = cuda.to_device(self._vel)
        self.d_avel = cuda.to_device(self._avel)
        self.d_inv_mass = cuda.to_device(self._imass)
        self.d_inv_inertia = cuda.to_device(self._iinertia)
        self.d_aabb_min = cuda.to_device(self._amin)
        self.d_aabb_max = cuda.to_device(self._amax)
        self._dirty = False

    def get_state(self):
        return {
            'positions': self.d_pos.copy_to_host(),
            'quaternions': self.d_quat.copy_to_host(),
            'velocities': self.d_vel.copy_to_host(),
            'angular_vels': self.d_avel.copy_to_host(),
            'aabb_min': self.d_aabb_min.copy_to_host(),
            'aabb_max': self.d_aabb_max.copy_to_host(),
        }

    def get_positions_aabbs(self):
        """Fast download: only positions, quaternions, AABBs (for collision pipeline)."""
        return (
            self.d_pos.copy_to_host(),
            self.d_quat.copy_to_host(),
            self.d_aabb_min.copy_to_host(),
            self.d_aabb_max.copy_to_host(),
        )

    def integrate(self, gravity=(0, -9810, 0), dt=1/60, damping_linear=0.1, damping_angular=0.1):
        self._upload()
        self.d_gravity = cuda.to_device(np.array(gravity, dtype=np.float64))
        threads = 256
        blocks = (self.n_bodies + threads - 1) // threads
        _integrate_kernel[blocks, threads](
            self.d_pos, self.d_quat, self.d_vel, self.d_avel,
            self.d_inv_mass,
            self.d_gravity, dt, damping_linear, damping_angular,
            self.n_bodies,
        )
        cuda.synchronize()

    def apply_ground(self, ground_y=0.0, time=0.0):
        threads = 256
        blocks = (self.n_bodies + threads - 1) // threads
        _ground_constraint_kernel[blocks, threads](
            self.d_pos, self.d_vel, self.d_inv_mass, self.d_aabb_min,
            ground_y, self._vibration_amplitude, self._vibration_frequency,
            time, self.n_bodies,
        )
        cuda.synchronize()

    def clamp_velocities(self, max_linear=None, max_angular=None):
        ml = max_linear if max_linear is not None else self._max_linear
        ma = max_angular if max_angular is not None else self._max_angular
        threads = 256
        blocks = (self.n_bodies + threads - 1) // threads
        _clamp_velocity_kernel[blocks, threads](
            self.d_vel, self.d_avel, self.d_inv_mass, ml, ma, self.n_bodies,
        )
        cuda.synchronize()

    def solve_contacts(self, contacts, dt, baumgarte=0.2, n_iterations=4):
        n = len(contacts)
        if n == 0:
            return
        # Re-upload contacts each time (they change each frame)
        cdata = np.asarray(contacts, dtype=np.float64)
        if self._d_contacts is None or self._d_contacts.shape[0] < n:
            self._d_contacts = cuda.to_device(np.zeros((max(n, 1024), 8), dtype=np.float64))
        self._d_contacts[:n] = cdata

        threads = 256
        blocks = (n + threads - 1) // threads
        for _ in range(n_iterations):
            _solve_contacts_kernel[blocks, threads](
                self.d_pos, self.d_quat, self.d_vel, self.d_avel,
                self.d_inv_mass, self.d_inv_inertia,
                self._d_contacts, n, dt, baumgarte,
                self.n_bodies,
            )
            cuda.synchronize()

    def update_aabbs(self, hull_verts, hull_vert_counts, max_verts):
        threads = 256
        blocks = (self.n_bodies + threads - 1) // threads
        _update_aabbs_kernel[blocks, threads](
            self.d_pos, self.d_quat,
            hull_verts, hull_vert_counts,
            self.d_aabb_min, self.d_aabb_max,
            self.n_bodies, max_verts,
        )
        cuda.synchronize()
