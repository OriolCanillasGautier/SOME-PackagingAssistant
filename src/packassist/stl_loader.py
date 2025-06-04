import os
import struct
import numpy as np
from pathlib import Path

def get_stl_dimensions(file_path):
    """
    Carrega un fitxer STL i retorna les dimensions de la caixa de límits.
    Implementació simplificada que llegeix directament el fitxer STL.
    
    Args:
        file_path: Ruta al fitxer STL
        
    Returns:
        Dict amb dimensions o None si hi ha error
    """
    try:
        # Verificar que el fitxer existeix
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"El fitxer {file_path} no existeix")
            
        # Verificar extensió
        if not file_path.lower().endswith('.stl'):
            raise ValueError("El fitxer ha de ser un STL")
            
        # Llegir fitxer STL i calcular bounding box
        vertices = read_stl_vertices(file_path)
        
        if len(vertices) == 0:
            raise ValueError("No s'han trobat vèrtexs al fitxer STL")
            
        # Calcular bounding box
        min_coords = np.min(vertices, axis=0)
        max_coords = np.max(vertices, axis=0)
        
        dimensions = max_coords - min_coords
        
        # Verificar que les dimensions són vàlides
        if any(d <= 0 for d in dimensions):
            raise ValueError("Les dimensions del model no són vàlides")
            
        return {
            "length": round(float(dimensions[0]), 2),
            "width": round(float(dimensions[1]), 2),
            "height": round(float(dimensions[2]), 2),
            "volume": round(float(dimensions[0] * dimensions[1] * dimensions[2]), 2)
        }
        
    except FileNotFoundError as e:
        print(f"❌ Fitxer no trobat: {e}")
        return None
    except ValueError as e:
        print(f"❌ Error de validació: {e}")
        return None
    except Exception as e:
        print(f"❌ Error en processar el fitxer STL: {str(e)}")
        return None

def validate_stl_file(file_path):
    """
    Valida si un fitxer STL es pot carregar correctament.
    
    Args:
        file_path: Ruta al fitxer STL
        
    Returns:
        Bool indicant si el fitxer és vàlid
    """
    try:
        if not os.path.exists(file_path):
            return False
        if not file_path.lower().endswith('.stl'):
            return False
              # Intentar llegir el fitxer
        vertices = read_stl_vertices(file_path)
        return len(vertices) > 0
    except:
        return False

def read_stl_vertices(file_path):
    """
    Llegeix els vèrtexs d'un fitxer STL binari o ASCII.
    
    Args:
        file_path: Ruta al fitxer STL
        
    Returns:
        Array numpy amb els vèrtexs
    """
    with open(file_path, 'rb') as f:
        # Llegir els primers 80 bytes (header)
        header = f.read(80)
        
        # Intentar llegir com STL binari
        try:
            # Llegir nombre de triangles
            num_triangles = struct.unpack('<I', f.read(4))[0]
            
            vertices = []
            for i in range(num_triangles):
                # Saltar normal vector (12 bytes)
                f.read(12)
                
                # Llegir 3 vèrtexs (cada un 3 floats de 4 bytes)
                for j in range(3):
                    vertex = struct.unpack('<fff', f.read(12))
                    vertices.append(vertex)
                
                # Saltar attribute byte count (2 bytes)
                f.read(2)
            
            return np.array(vertices)
            
        except:
            # Si falla, intentar llegir com ASCII
            return read_stl_ascii(file_path)

def read_stl_ascii(file_path):
    """
    Llegeix un fitxer STL ASCII.
    
    Args:
        file_path: Ruta al fitxer STL
        
    Returns:
        Array numpy amb els vèrtexs
    """
    vertices = []
    
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('vertex'):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                        vertices.append([x, y, z])
                    except ValueError:
                        continue
    
    return np.array(vertices) if vertices else np.array([])
