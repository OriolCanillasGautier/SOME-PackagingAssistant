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
    Returns dimensions based on filename patterns, file size, or embedded data.
    In a real implementation, this would parse STP files properly.
    """
    if not os.path.exists(file_path):
        return None
    
    try:
        # Handle virtual and custom files
        if file_path.startswith("custom://"):
            # Check if dimensions are in the custom_dimensions.json file
            custom_file = os.path.join("data", "custom", "custom_dimensions.json")
            if os.path.exists(custom_file):
                import json
                with open(custom_file, "r", encoding="utf-8") as f:
                    try:
                        custom_data = json.load(f)
                        if file_path in custom_data:
                            return {
                                "length": custom_data[file_path].get("length", 100.0),
                                "width": custom_data[file_path].get("width", 100.0),
                                "height": custom_data[file_path].get("height", 100.0)
                            }
                    except:
                        pass
            
            # Parse dimensions from the file path itself
            import re
            match = re.search(r'(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)', file_path)
            if match:
                length, width, height = match.groups()
                return {
                    "length": float(length),
                    "width": float(width),
                    "height": float(height)
                }
            
            return None
        
        # Get filename for pattern matching
        filename = os.path.basename(file_path).lower()
        file_size = os.path.getsize(file_path)
        
        # Check if dimensions are encoded in the filename (e.g., box_100x80x60.stp)
        import re
        match = re.search(r'(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)', filename)
        if match:
            length, width, height = match.groups()
            return {
                "length": float(length),
                "width": float(width),
                "height": float(height)
            }
        
        # Check if the file contains dimension information
        if file_path.endswith('.stp') or file_path.endswith('.step'):
            try:
                with open(file_path, 'r', errors='ignore') as f:
                    content = f.read()
                    # Look for dimension information in the file
                    dimension_match = re.search(r'/\* (?:Box|Object) dimensions: ([\d\.]+) x ([\d\.]+) x ([\d\.]+) mm \*/', content)
                    if dimension_match:
                        return {
                            "length": float(dimension_match.group(1)),
                            "width": float(dimension_match.group(2)),
                            "height": float(dimension_match.group(3))
                        }
            except:
                pass
        
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
    Checks file extension, existence, and custom formats.
    """
    if not file_path:
        return False
    
    # Handle virtual files
    if file_path.startswith("custom://"):
        # Check if dimensions are in the custom dimensions json
        custom_file = os.path.join("data", "custom", "custom_dimensions.json")
        if os.path.exists(custom_file):
            import json
            try:
                with open(custom_file, "r", encoding="utf-8") as f:
                    custom_data = json.load(f)
                    return file_path in custom_data
            except:
                return False
                
        # Also check if we can extract dimensions from the path itself
        import re
        match = re.search(r'(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)', file_path)
        return bool(match)
    
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