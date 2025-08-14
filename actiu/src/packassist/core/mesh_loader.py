"""
Càrrega i processament de fitxers de malla (STL, STP)
"""

import os
import trimesh
import numpy as np
from typing import Optional, Tuple, Dict, Any

class MeshLoader:
    """Classe per carregar i processar malles 3D"""
    
    def __init__(self):
        self.supported_formats = ['.stl', '.stp', '.step', '.obj', '.ply']
    
    def load_mesh(self, filepath: str) -> trimesh.Trimesh:
        """Carrega una malla des d'un fitxer"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Fitxer no trobat: {filepath}")
        
        file_ext = os.path.splitext(filepath)[1].lower()
        
        if file_ext not in self.supported_formats:
            raise ValueError(f"Format no suportat: {file_ext}")
        
        try:
            # Carregar la malla
            mesh = trimesh.load(filepath)
            
            # Verificar que és una malla vàlida
            if not isinstance(mesh, trimesh.Trimesh):
                if hasattr(mesh, 'geometry') and len(mesh.geometry) > 0:
                    # Combinar geometries múltiples
                    mesh = trimesh.util.concatenate([geom for geom in mesh.geometry.values()])
                else:
                    raise ValueError("El fitxer no conté geometria vàlida")
            
            # Validar la malla
            if not self._validate_mesh(mesh):
                raise ValueError("La malla no és vàlida")
            
            # Normalitzar la malla
            mesh = self._normalize_mesh(mesh)
            
            return mesh
            
        except Exception as e:
            raise ValueError(f"Error carregant el fitxer: {e}")
    
    def _validate_mesh(self, mesh: trimesh.Trimesh) -> bool:
        """Valida que la malla sigui correcta"""
        if mesh is None:
            return False
        
        if not hasattr(mesh, 'vertices') or not hasattr(mesh, 'faces'):
            return False
        
        if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
            return False
        
        return True
    
    def _normalize_mesh(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """Normalitza la malla (centrar, orientar correctament)"""
        # Crear una còpia
        normalized_mesh = mesh.copy()
        
        # Reparar la malla si cal
        if not normalized_mesh.is_watertight:
            try:
                normalized_mesh.fill_holes()
            except:
                pass  # Si no es pot reparar, continuem
        
        # Assegurar orientació correcta de les normals
        try:
            normalized_mesh.fix_normals()
        except:
            pass
        
        return normalized_mesh
    
    def get_mesh_info(self, mesh: trimesh.Trimesh) -> Dict[str, Any]:
        """Obté informació sobre la malla"""
        if not mesh:
            return {}
        
        bounds = mesh.bounds
        dimensions = bounds[1] - bounds[0]
        
        return {
            'vertices_count': len(mesh.vertices),
            'faces_count': len(mesh.faces),
            'volume': float(mesh.volume) if mesh.is_volume else 0.0,
            'surface_area': float(mesh.area),
            'bounds': bounds.tolist(),
            'dimensions': dimensions.tolist(),
            'center': mesh.center_mass.tolist(),
            'is_watertight': mesh.is_watertight,
            'is_volume': mesh.is_volume
        }
    
    def simplify_mesh(self, mesh: trimesh.Trimesh, target_faces: int = 1000) -> trimesh.Trimesh:
        """Simplifica la malla per millorar el rendiment"""
        if len(mesh.faces) <= target_faces:
            return mesh.copy()
        
        try:
            # Intentar simplificació amb trimesh
            simplified = mesh.simplify_quadric_decimation(target_faces)
            
            if self._validate_mesh(simplified):
                return simplified
            else:
                # Si la simplificació falla, retornar l'original
                return mesh.copy()
                
        except Exception:
            # Si hi ha error, retornar l'original
            return mesh.copy()
    
    def prepare_for_optimization(self, mesh: trimesh.Trimesh) -> Tuple[trimesh.Trimesh, trimesh.Trimesh]:
        """Prepara la malla per optimització (original + simplificada)"""
        # Malla original normalitzada
        original = self._normalize_mesh(mesh)
        
        # Malla simplificada per visualització/càlcul ràpid
        simplified = self.simplify_mesh(original, target_faces=2000)
        
        return original, simplified
