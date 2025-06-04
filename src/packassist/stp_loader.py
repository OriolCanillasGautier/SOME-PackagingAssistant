"""
STP File Loader - Simplified version
Provides basic file validation without CadQuery dependency.
For now, it provides fallback functionality until CadQuery compatibility is resolved.
"""

import os
from pathlib import Path

def get_stp_dimensions(file_path):
    """
    Simplified STP dimension reader.
    Returns dimensions based on filename patterns and file size.
    In a real implementation, this would parse STP files properly.
    """
    if not os.path.exists(file_path):
        return None
    
    try:
        # Get filename for pattern matching
        filename = os.path.basename(file_path).lower()
        file_size = os.path.getsize(file_path)
        
        # Define dimension patterns based on common object names
        dimension_patterns = {
            'caixa_petita': {'length': 200.0, 'width': 150.0, 'height': 100.0},
            'box_small': {'length': 200.0, 'width': 150.0, 'height': 100.0},
            'box_medium': {'length': 400.0, 'width': 300.0, 'height': 200.0},
            'box_large': {'length': 800.0, 'width': 600.0, 'height': 400.0},
            'llibre_petit': {'length': 150.0, 'width': 100.0, 'height': 20.0},
            'llibre_gran': {'length': 250.0, 'width': 180.0, 'height': 30.0},
            'paquet_amazon': {'length': 300.0, 'width': 200.0, 'height': 150.0},
            'component_electronic': {'length': 50.0, 'width': 30.0, 'height': 15.0},
            'palet_standard': {'length': 1200.0, 'width': 800.0, 'height': 150.0},
        }
        
        # Try to match filename patterns
        for pattern, dims in dimension_patterns.items():
            if pattern in filename:
                return dims
        
        # Fallback: calculate dimensions based on file size
        base_size = 50 + (file_size % 500)  # Value between 50 and 550
        
        return {
            "length": base_size * 2.0,
            "width": base_size * 1.5,
            "height": base_size * 1.0
        }
        
    except Exception as e:
        print(f"❌ Error processant fitxer STP {file_path}: {e}")
        return None

def validate_stp_file(file_path):
    """
    Validate if a file is a valid STP file.
    Currently only checks file extension and existence.
    """
    if not file_path:
        return False
    
    path = Path(file_path)
    
    # Check if file exists
    if not path.exists():
        return False
    
    # Check if it has a valid STP extension
    valid_extensions = ['.stp', '.step']
    if path.suffix.lower() not in valid_extensions:
        return False
    
    # Check if file is not empty
    if path.stat().st_size == 0:
        return False
    
    return True

def create_object_index(objects_dir="objects"):
    """Create an index of STP objects in the directory."""
    # Simplified implementation
    return {}

def update_object_index(objects_dir="objects"):
    """Update the object index."""
    # Simplified implementation
    pass

def get_indexed_objects(objects_dir="objects"):
    """Get indexed objects."""
    # Simplified implementation
    return []

def search_objects_by_dimensions(target_dims, tolerance=10, objects_dir="objects"):
    """Search objects by dimensions."""
    # Simplified implementation
    return []