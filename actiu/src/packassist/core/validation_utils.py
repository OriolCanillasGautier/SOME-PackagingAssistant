"""
Utilitats de validació per a PackAssist
"""

import numpy as np
from typing import List, Tuple, Dict, Any

def validate_positions_within_container(positions: List[List[float]], 
                                      container_dims: Tuple[float, float, float],
                                      obj_dims: List[float],
                                      margin: float = 2.0) -> List[bool]:
    """
    Valida que les posicions estiguin dins del contenidor
    
    Args:
        positions: Llista de posicions [x, y, z]
        container_dims: Dimensions del contenidor (length, width, height)
        obj_dims: Dimensions de l'objecte [length, width, height]
        margin: Marge al voltant de l'objecte
        
    Returns:
        Llista de booleans indicant si cada posició és vàlida
    """
    container_length, container_width, container_height = container_dims
    obj_length, obj_width, obj_height = obj_dims
    
    # Dimensions amb marge
    effective_length = obj_length + 2 * margin
    effective_width = obj_width + 2 * margin
    effective_height = obj_height + 2 * margin
    
    valid_positions = []
    
    for pos in positions:
        x, y, z = pos
        
        # Verificar límits del contenidor amb tolerància
        tolerance = 0.001
        half_length = effective_length / 2
        half_width = effective_width / 2
        half_height = effective_height / 2
        
        is_valid = (
            x - half_length >= -tolerance and
            x + half_length <= container_length + tolerance and
            y - half_width >= -tolerance and
            y + half_width <= container_width + tolerance and
            z - half_height >= -tolerance and
            z + half_height <= container_height + tolerance
        )
        
        valid_positions.append(is_valid)
    
    return valid_positions

def filter_valid_positions(positions: List[List[float]], 
                         rotations: List[List[float]],
                         container_dims: Tuple[float, float, float],
                         obj_dims: List[float],
                         margin: float = 2.0) -> Tuple[List[List[float]], List[List[float]]]:
    """
    Filtra les posicions vàlides dins del contenidor
    
    Args:
        positions: Llista de posicions [x, y, z]
        rotations: Llista de rotacions [rx, ry, rz]
        container_dims: Dimensions del contenidor (length, width, height)
        obj_dims: Dimensions de l'objecte [length, width, height]
        margin: Marge al voltant de l'objecte
        
    Returns:
        Tupla amb (posicions_vàlides, rotacions_vàlides)
    """
    valid_mask = validate_positions_within_container(positions, container_dims, obj_dims, margin)
    
    valid_positions = []
    valid_rotations = []
    
    for i, is_valid in enumerate(valid_mask):
        if is_valid:
            valid_positions.append(positions[i])
            valid_rotations.append(rotations[i])
    
    return valid_positions, valid_rotations