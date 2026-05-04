"""
SOME Physics Engine — GPU-accelerated rigid body physics.
CUDA backend via Numba.

Modules:
    hull       — CPU convex hull generation from trimesh
    collision  — GPU SAT narrow-phase collision detection
    broadphase — GPU spatial hashing broad phase
    contacts   — GPU contact manifold generation
    dynamics   — GPU rigid body integration + impulse solver
    world      — CPU orchestrator (step loop, memory mgmt)
"""

# Patch numba PTX version for old NVIDIA drivers
import numba.cuda.cudadrv.driver as _ptx_drv
_ptx_orig = _ptx_drv.CtypesLinker.add_ptx
def _ptx_patched(self, ptx, name='<cudapy-ptx>'):
    import re
    if isinstance(ptx, bytes):
        ptx = re.sub(rb'\.version\s+\d+\.\d+', b'.version 8.2', ptx)
    else:
        ptx = re.sub(r'\.version\s+\d+\.\d+', '.version 8.2', ptx)
    return _ptx_orig(self, ptx, name)
_ptx_drv.CtypesLinker.add_ptx = _ptx_patched

from .hull import HullData, compute_hull, hull_from_stl
from .collision import CollisionDetector
from .broadphase import BroadPhase
from .contacts import ContactGenerator
from .dynamics import DynamicsSolver
from .world import World
