import cadquery as cq
import os
import json
from pathlib import Path
import hashlib
from datetime import datetime

def get_stl_dimensions(file_path):
    """
    Carrega un fitxer STL i retorna les dimensions de la caixa de límits.
    
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
            
        # Carregar el fitxer
        shape = cq.importers.importStl(file_path)
        
        # Verificar que s'ha carregat correctament
        if shape is None:
            raise ValueError("No s'ha pogut carregar la geometria del fitxer")
            
        bbox = shape.val().BoundingBox()
        
        # Verificar que les dimensions són vàlides
        if bbox.xlen <= 0 or bbox.ylen <= 0 or bbox.zlen <= 0:
            raise ValueError("Les dimensions del model no són vàlides")
            
        return {
            "length": round(bbox.xlen, 2),
            "width": round(bbox.ylen, 2),
            "height": round(bbox.zlen, 2),
            "volume": round(bbox.xlen * bbox.ylen * bbox.zlen, 2)
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
            
        # Intentar carregar el fitxer
        shape = cq.importers.importStl(file_path)
        return shape is not None
    except:
        return False
