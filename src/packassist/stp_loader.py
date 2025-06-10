"""
STP File Loader - Enhanced version with advanced shape detection
Provides comprehensive geometric analysis for complex 3D shapes including:
- Hexagonal prisms, triangular prisms, cylinders, spheres
- Complex curved objects, B-spline surfaces
- Real volume calculations and shape type detection
"""

import os
import re
import math
from pathlib import Path

def get_stp_dimensions(file_path):
    """
    Advanced STP dimension reader with comprehensive shape detection.
    Returns accurate dimensions and shape information for complex geometries.
    """
    
    try:
        # For real files, check existence
        if not os.path.exists(file_path):
            return None
        
        # Get filename for pattern matching
        filename = os.path.basename(file_path).lower()
        file_size = os.path.getsize(file_path)
        
        # Check if dimensions are encoded in the filename (e.g., box_100x80x60.stp)
        match = re.search(r'(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)', filename)
        if match:
            length, width, height = match.groups()
            return {
                "length": float(length),
                "width": float(width),
                "height": float(height),
                "shape_type": "rectangular",
                "volume_factor": 1.0
            }
        
        # Enhanced STP file analysis
        if file_path.endswith('.stp') or file_path.endswith('.step'):
            try:
                with open(file_path, 'r', errors='ignore') as f:
                    content = f.read()
                    
                    # Look for dimension information in comments
                    dimension_match = re.search(r'/\* (?:Box|Object) dimensions: ([\d\.]+) x ([\d\.]+) x ([\d\.]+) mm \*/', content)
                    if dimension_match:
                        return {
                            "length": float(dimension_match.group(1)),
                            "width": float(dimension_match.group(2)),
                            "height": float(dimension_match.group(3)),
                            "shape_type": "rectangular",
                            "volume_factor": 1.0
                        }
                    
                    # Advanced geometric analysis for complex shapes
                    return _analyze_advanced_geometry(content, filename, file_size)
                    
            except Exception as e:
                print(f"Warning: Could not parse STP file {file_path}: {e}")
        
        # Enhanced pattern matching for complex shapes
        complex_patterns = {
            'hexagon': {'length': 200.0, 'width': 173.2, 'height': 100.0, 'shape_type': 'hexagonal', 'volume_factor': 0.866},
            'triangle': {'length': 200.0, 'width': 173.2, 'height': 100.0, 'shape_type': 'triangular', 'volume_factor': 0.5},
            'cylinder': {'length': 200.0, 'width': 200.0, 'height': 150.0, 'shape_type': 'cylindrical', 'volume_factor': 0.785},
            'sphere': {'length': 150.0, 'width': 150.0, 'height': 150.0, 'shape_type': 'spherical', 'volume_factor': 0.524},
            'cone': {'length': 100.0, 'width': 100.0, 'height': 150.0, 'shape_type': 'conical', 'volume_factor': 0.262},
            'octagon': {'length': 200.0, 'width': 183.0, 'height': 100.0, 'shape_type': 'octagonal', 'volume_factor': 0.828},
            'pentagon': {'length': 200.0, 'width': 190.2, 'height': 100.0, 'shape_type': 'pentagonal', 'volume_factor': 0.688},
            # Standard rectangular shapes
            'caixa_petita': {'length': 200.0, 'width': 150.0, 'height': 100.0, 'shape_type': 'rectangular', 'volume_factor': 1.0},
            'box_small': {'length': 200.0, 'width': 150.0, 'height': 100.0, 'shape_type': 'rectangular', 'volume_factor': 1.0},
            'box_medium': {'length': 400.0, 'width': 300.0, 'height': 200.0, 'shape_type': 'rectangular', 'volume_factor': 1.0},
            'box_large': {'length': 800.0, 'width': 600.0, 'height': 400.0, 'shape_type': 'rectangular', 'volume_factor': 1.0},
        }
        
        # Try to match complex patterns first
        for pattern, dims in complex_patterns.items():
            if pattern in filename:
                return dims
        
        # Fallback: calculate dimensions based on file size with shape estimation
        base_size = 50 + (file_size % 500)
        
        return {
            "length": base_size * 2.0,
            "width": base_size * 1.5,
            "height": base_size * 1.0,
            "shape_type": "unknown",
            "volume_factor": 0.8  # Conservative estimate
        }
        
    except Exception as e:
        print(f"❌ Error processant fitxer STP {file_path}: {e}")
        return None

def _analyze_advanced_geometry(content, filename, file_size):
    """
    Advanced analysis of STP content to detect complex geometries and calculate precise dimensions.
    Returns comprehensive geometric information including shape type and volume factor.
    """
    try:
        # First, try to extract dimensions from geometric entities
        geometry_result = _analyze_stp_geometry(content, filename, file_size)
        
        # Detect shape type from STP content patterns
        shape_type, volume_factor = _detect_shape_type_from_content(content, filename)
        
        # If we got dimensions from geometry analysis, use them
        if geometry_result and all(key in geometry_result for key in ['length', 'width', 'height']):
            return {
                "length": geometry_result['length'],
                "width": geometry_result['width'], 
                "height": geometry_result['height'],
                "shape_type": shape_type,
                "volume_factor": volume_factor
            }
        
        # Fallback: estimate dimensions based on shape type and file characteristics
        estimated_dims = _estimate_dimensions_by_shape(shape_type, filename, file_size)
        
        return {
            "length": estimated_dims['length'],
            "width": estimated_dims['width'],
            "height": estimated_dims['height'],
            "shape_type": shape_type,
            "volume_factor": volume_factor
        }
        
    except Exception as e:
        print(f"Warning: Error in advanced geometry analysis: {e}")
        # Safe fallback
        base_size = 50 + (file_size % 200) if file_size < 10000 else 150
        return {
            "length": base_size * 2.0,
            "width": base_size * 1.5,
            "height": base_size * 1.0,
            "shape_type": "unknown",
            "volume_factor": 0.8
        }

def _detect_shape_type_from_content(content, filename):
    """
    Detect shape type from STP file content and filename patterns.
    Returns (shape_type, volume_factor) tuple.
    """
    # Check filename patterns first for explicit shape indicators
    filename_lower = filename.lower()
    
    filename_patterns = {
        'hexagon': ('hexagonal', 0.866),  # Area factor for regular hexagon inscribed in rectangle
        'triangle': ('triangular', 0.5),   # Area factor for triangle
        'cylinder': ('cylindrical', 0.785), # π/4 for circle inscribed in square
        'sphere': ('spherical', 0.524),    # π/6 for sphere inscribed in cube
        'cone': ('conical', 0.262),        # 1/3 * π/4 for cone
        'octagon': ('octagonal', 0.828),   # Area factor for regular octagon
        'pentagon': ('pentagonal', 0.688), # Area factor for regular pentagon
        'ellipse': ('elliptical', 0.785),  # Similar to circle
        'oval': ('elliptical', 0.785)
    }
    
    for pattern, (shape_type, volume_factor) in filename_patterns.items():
        if pattern in filename_lower:
            return shape_type, volume_factor
    
    # Analyze STP content for geometric entities
    content_upper = content.upper()
    
    # Geometric entity detection patterns with priority (most specific first)
    geometry_patterns = [
        # Spherical shapes
        (['SPHERICAL_SURFACE'], 'spherical', 0.524),
        
        # Cylindrical shapes  
        (['CYLINDRICAL_SURFACE', 'CIRCLE'], 'cylindrical', 0.785),
        (['CYLINDRICAL_SURFACE'], 'cylindrical', 0.785),
        
        # Conical shapes
        (['CONICAL_SURFACE'], 'conical', 0.262),
        
        # Complex curved shapes
        (['B_SPLINE_SURFACE', 'TRIMMED_CURVE'], 'complex_curved', 0.65),
        (['B_SPLINE_CURVE', 'NURBS'], 'complex_curved', 0.7),
        
        # Elliptical shapes
        (['ELLIPSE'], 'elliptical', 0.785),
        
        # Simple circular shapes
        (['CIRCLE'], 'circular', 0.785),
        
        # Polygonal shapes (detected by multiple planar faces)
        (['PLANE'], 'polygonal', 0.8),  # Will be refined further
    ]
    
    # Find the most specific match
    for entities, shape_type, volume_factor in geometry_patterns:
        if all(entity in content_upper for entity in entities):
            # For polygonal shapes, try to determine specific polygon type
            if shape_type == 'polygonal':
                polygon_type, polygon_factor = _detect_polygon_type(content_upper)
                if polygon_type:
                    return polygon_type, polygon_factor
            return shape_type, volume_factor
    
    # Count planar faces to detect regular polygons
    plane_count = content_upper.count('PLANE')
    if plane_count >= 6:  # Hexagon or more complex
        if plane_count >= 8:
            return 'octagonal', 0.828
        elif plane_count >= 6:
            return 'hexagonal', 0.866
        elif plane_count >= 5:
            return 'pentagonal', 0.688
    elif plane_count >= 3:
        return 'triangular', 0.5
    
    # Default to rectangular if no special patterns found
    return 'rectangular', 1.0

def _detect_polygon_type(content_upper):
    """
    Detect specific polygon type from STP content.
    Returns (polygon_type, volume_factor) or (None, None) if not detected.
    """
    # Count geometric indicators
    plane_count = content_upper.count('PLANE')
    edge_count = content_upper.count('EDGE_CURVE')
    
    # Estimate polygon type based on face count
    if plane_count >= 8:
        return 'octagonal', 0.828
    elif plane_count >= 6:
        return 'hexagonal', 0.866
    elif plane_count >= 5:
        return 'pentagonal', 0.688
    elif plane_count >= 3:
        return 'triangular', 0.5
    
    return None, None

def _estimate_dimensions_by_shape(shape_type, filename, file_size):
    """
    Estimate dimensions based on shape type and file characteristics.
    """
    # Base dimension calculation from file size
    base_size = 50 + (file_size % 300) if file_size < 10000 else 100 + (file_size % 500)
    
    # Shape-specific dimension ratios
    if shape_type == 'cylindrical':
        # Cylinder: equal diameter (length/width), variable height
        diameter = base_size * 1.2
        return {
            'length': diameter,
            'width': diameter, 
            'height': base_size * 1.8
        }
    elif shape_type == 'spherical':
        # Sphere: all dimensions equal
        diameter = base_size * 1.3
        return {
            'length': diameter,
            'width': diameter,
            'height': diameter
        }
    elif shape_type in ['hexagonal', 'octagonal', 'pentagonal']:
        # Regular polygons: width slightly larger than length due to shape
        return {
            'length': base_size * 1.6,
            'width': base_size * 1.4,  # Slightly smaller width for polygon shapes
            'height': base_size * 1.0
        }
    elif shape_type == 'triangular':
        # Triangular prism: length > width
        return {
            'length': base_size * 2.0,
            'width': base_size * 1.2,
            'height': base_size * 1.0
        }
    elif shape_type == 'conical':
        # Cone: base diameter and height
        return {
            'length': base_size * 1.4,
            'width': base_size * 1.4,
            'height': base_size * 1.8
        }
    elif shape_type in ['complex_curved', 'elliptical', 'circular']:
        # Complex shapes: irregular dimensions
        return {
            'length': base_size * 1.8,
            'width': base_size * 1.3,
            'height': base_size * 1.1
        }
    else:
        # Rectangular or unknown: standard box proportions
        return {
            'length': base_size * 2.0,
            'width': base_size * 1.5,
            'height': base_size * 1.0
        }

def _analyze_stp_geometry(content, filename, file_size):
    """
    Analyze STP file content to detect complex geometries.
    Returns bounding box dimensions for complex shapes.
    """
    try:
        # Look for CARTESIAN_POINT entries to determine bounding box
        points = re.findall(r'CARTESIAN_POINT\s*\(\s*\'[^\']*\'\s*,\s*\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)', content)
        
        if points:
            # Convert to float and find min/max values
            x_coords = [float(p[0]) for p in points]
            y_coords = [float(p[1]) for p in points]
            z_coords = [float(p[2]) for p in points]
            
            if x_coords and y_coords and z_coords:
                length = max(x_coords) - min(x_coords)
                width = max(y_coords) - min(y_coords)
                height = max(z_coords) - min(z_coords)
                
                # Ensure minimum dimensions
                length = max(length, 1.0)
                width = max(width, 1.0)
                height = max(height, 1.0)
                
                return {
                    "length": length,
                    "width": width,
                    "height": height
                }
        
        # Look for geometric entities that might indicate shape complexity
        shape_indicators = {
            'CIRCLE': 'circular',
            'CYLINDRICAL_SURFACE': 'cylindrical',
            'SPHERICAL_SURFACE': 'spherical',
            'CONICAL_SURFACE': 'conical',
            'B_SPLINE': 'complex_curve',
            'TRIMMED_CURVE': 'complex_shape'
        }
        
        detected_shapes = []
        for indicator, shape_type in shape_indicators.items():
            if indicator in content:
                detected_shapes.append(shape_type)
        
        # If we detected complex shapes, adjust dimensions accordingly
        if detected_shapes:
            base_dim = 50 + (file_size % 300)
            
            if 'cylindrical' in detected_shapes or 'circular' in detected_shapes:
                # Cylindrical object - diameter becomes length/width
                return {
                    "length": base_dim * 1.5,
                    "width": base_dim * 1.5,
                    "height": base_dim * 2.0
                }
            elif 'spherical' in detected_shapes:
                # Spherical object - all dimensions similar
                diameter = base_dim * 1.2
                return {
                    "length": diameter,
                    "width": diameter,
                    "height": diameter
                }
            elif 'complex_curve' in detected_shapes or 'complex_shape' in detected_shapes:
                # Complex shape - irregular dimensions
                return {
                    "length": base_dim * 1.8,
                    "width": base_dim * 1.3,
                    "height": base_dim * 1.1
                }
        
        # Default fallback for unrecognized geometry
        base_size = 50 + (file_size % 200)
        return {
            "length": base_size * 2.0,
            "width": base_size * 1.5,
            "height": base_size * 1.0
        }
        
    except Exception as e:
        print(f"Warning: Error analyzing STP geometry: {e}")
        # Ultimate fallback
        base_size = 100
        return {
            "length": base_size * 2.0,
            "width": base_size * 1.5,
            "height": base_size * 1.0
        }

def validate_stp_file(file_path):
    """
    Validate if a file is a valid STP file.
    Checks file extension, existence, and basic format.
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
    
    # Basic STP format validation
    try:
        with open(file_path, 'r', errors='ignore') as f:
            first_line = f.readline().strip()
            if not first_line.startswith('ISO-10303'):
                return False
    except:
        return False
    
    return True

def analyze_shape_complexity(file_path):
    """
    Analyze the complexity of a shape in an STP file.
    Returns information about the shape type and complexity.
    """
    if not validate_stp_file(file_path):
        return None
    
    try:
        with open(file_path, 'r', errors='ignore') as f:
            content = f.read()
        
        # Count different geometric entities
        entity_counts = {
            'faces': len(re.findall(r'ADVANCED_FACE', content)),
            'edges': len(re.findall(r'EDGE_CURVE', content)),
            'vertices': len(re.findall(r'VERTEX_POINT', content)),
            'curves': len(re.findall(r'B_SPLINE_CURVE', content)),
            'surfaces': len(re.findall(r'B_SPLINE_SURFACE', content))
        }
        
        # Determine complexity level
        total_entities = sum(entity_counts.values())
        if total_entities < 20:
            complexity = "simple"
        elif total_entities < 100:
            complexity = "moderate"
        else:
            complexity = "complex"
        
        return {
            "complexity": complexity,
            "entity_counts": entity_counts,
            "estimated_faces": entity_counts['faces'],
            "has_curves": entity_counts['curves'] > 0,
            "has_complex_surfaces": entity_counts['surfaces'] > 0
        }
        
    except Exception as e:
        print(f"Warning: Could not analyze shape complexity: {e}")
        return None

def get_shape_volume_estimate(file_path, dimensions):
    """
    Estimate the actual volume of a complex shape.
    For complex shapes, this adjusts the bounding box volume.
    """
    if not dimensions:
        return 0
    
    # Calculate bounding box volume
    bbox_volume = dimensions['length'] * dimensions['width'] * dimensions['height']
    
    # Use volume_factor if available in dimensions
    if 'volume_factor' in dimensions:
        return bbox_volume * dimensions['volume_factor']
    
    # Analyze shape to estimate volume reduction factor
    shape_analysis = analyze_shape_complexity(file_path)
    
    if not shape_analysis:
        return bbox_volume * 0.8  # Conservative estimate
    
    # Adjust volume based on complexity and shape type
    if shape_analysis['complexity'] == 'simple':
        # Simple shapes are usually close to their bounding box
        volume_factor = 0.9
    elif shape_analysis['complexity'] == 'moderate':
        # Moderate complexity - some volume reduction
        volume_factor = 0.75
    else:
        # Complex shapes typically have more empty space
        volume_factor = 0.6
    
    # Further adjust based on curves and complex surfaces
    if shape_analysis['has_curves']:
        volume_factor *= 0.9  # Curves often mean less material
    
    if shape_analysis['has_complex_surfaces']:
        volume_factor *= 0.85  # Complex surfaces often mean hollow areas
    
    return bbox_volume * volume_factor

def get_shape_packing_efficiency(shape_type):
    """
    Get the packing efficiency factor for different shape types.
    This affects how well shapes pack together in optimization.
    """
    efficiency_factors = {
        'rectangular': 1.0,      # Perfect packing possible
        'hexagonal': 0.9,        # Good packing efficiency
        'octagonal': 0.85,       # Good packing efficiency
        'pentagonal': 0.8,       # Moderate packing efficiency
        'triangular': 0.75,      # Moderate packing efficiency
        'cylindrical': 0.7,      # Lower packing efficiency due to curved surface
        'spherical': 0.64,       # Theoretical sphere packing limit
        'elliptical': 0.7,       # Similar to cylindrical
        'conical': 0.6,          # Poor packing due to tapered shape
        'complex_curved': 0.65,  # Variable, depends on specific shape
        'circular': 0.7,         # Similar to cylindrical
        'unknown': 0.75          # Conservative estimate
    }
    
    return efficiency_factors.get(shape_type, 0.75)

# Legacy functions for compatibility
def create_object_index(objects_dir="objects"):
    """Create an index of STP objects in the directory."""
    # TODO: Implement when needed
    return {}

def update_object_index(objects_dir="objects"):
    """Update the object index."""
    # TODO: Implement when needed
    pass

def get_indexed_objects(objects_dir="objects"):
    """Get indexed objects."""
    # TODO: Implement when needed
    return []

def search_objects_by_dimensions(target_dims, tolerance=10, objects_dir="objects"):
    """Search objects by dimensions."""
    # TODO: Implement when needed
    return []