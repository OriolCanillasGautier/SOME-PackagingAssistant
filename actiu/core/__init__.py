"""
PackAssist Core - Mòduls principals de l'aplicació
"""

__version__ = "2.0.0"
__author__ = "Oriol Canillas"

import sys
import os

# Afegir path dels optimitzadors
current_dir = os.path.dirname(os.path.abspath(__file__))
optimizers_path = os.path.join(current_dir, '..', 'src', 'packassist', 'optimizers')
if optimizers_path not in sys.path:
    sys.path.insert(0, optimizers_path)

# Imports dels mòduls principals
try:
    # Importar optimitzadors millorats
    from normal_optimizer import NormalPackingOptimizer
    from bulk_optimizer import BulkPackingOptimizer  
    from obb_optimizer import OBBOptimizer
    from improved_obb_integration import ImprovedOBBPackingSystem
    from robust_3d_packer import Robust3DPacker  # Nou optimitzador robust
    
    # Clase MeshLoader simple per compatibilitat
    class MeshLoader:
        @staticmethod
        def load_mesh(filepath):
            """Carrega una malla 3D"""
            try:
                import trimesh
                return trimesh.load(filepath)
            except:
                return None
    
    # Classe ResultsExporter simple per compatibilitat
    class ResultsExporter:
        @staticmethod
        def export_results(results, filename):
            """Exporta els resultats a un fitxer"""
            with open(filename, 'w') as f:
                f.write(str(results))
            return True
    
    __all__ = ['NormalPackingOptimizer', 'BulkPackingOptimizer', 'OBBOptimizer', 
               'ImprovedOBBPackingSystem', 'Robust3DPacker', 'MeshLoader', 'ResultsExporter']
    
except ImportError as e:
    print(f"Error carregant optimitzadors de packassist.core: {e}")
    # Definir classes buides per evitar errors
    class NormalPackingOptimizer:
        def __init__(self, *args, **kwargs):
            pass
    
    class BulkPackingOptimizer:
        def __init__(self, *args, **kwargs):
            pass
    
    class OBBOptimizer:
        def __init__(self, *args, **kwargs):
            pass
    
    class MeshLoader:
        def __init__(self, *args, **kwargs):
            pass
    
    class ResultsExporter:
        def __init__(self, *args, **kwargs):
            pass
    
    __all__ = []
