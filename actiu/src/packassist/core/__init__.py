"""
Mòdul principal del nucli de PackAssist
"""

from .mesh_loader import MeshLoader
from .mesh_simplifiers import get_mesh_simplifier
from .optimization import PackingOptimizer
from .export import ResultsExporter
from .validation_utils import validate_positions_within_container, filter_valid_positions
from ..optimizers import OBBOptimizer, BulkPackingOptimizer, NormalPackingOptimizer

__all__ = [
    'MeshLoader',
    'get_mesh_simplifier',
    'PackingOptimizer',
    'ResultsExporter',
    'validate_positions_within_container',
    'filter_valid_positions',
    'OBBOptimizer',
    'BulkPackingOptimizer',
    'NormalPackingOptimizer'
]