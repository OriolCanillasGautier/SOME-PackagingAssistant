"""
Optimitzador avançat amb support per meshes i collision detection
Integra el sistema de meshing amb l'algoritme d'empaquetament existent
"""

import numpy as np
import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from .advanced_meshing import Mesh3D, GeometryToMeshConverter, RotationGenerator, BasicCollisionDetector

@dataclass
class PackedItem:
    """Representa un objecte empaquetat amb la seva posició i orientació."""
    position: np.ndarray     # [x, y, z]
    dimensions: np.ndarray   # [length, width, height] després de rotació
    rotation_name: str       # Nom de la rotació aplicada
    rotation_matrix: np.ndarray  # Matriu de rotació
    mesh: Mesh3D            # Mesh de l'objecte en aquesta orientació
    original_dimensions: np.ndarray  # Dimensions originals
    item_id: int            # ID únic de l'objecte

@dataclass  
class PackingResult:
    """Resultat d'un algoritme d'empaquetament."""
    packed_items: List[PackedItem]
    container_dimensions: np.ndarray
    total_objects: int
    efficiency: float
    volume_used: float
    volume_container: float
    packing_time: float
    algorithm_used: str

class MeshBasedPacker:
    """Empaquetador basat en meshes amb collision detection."""
    
    def __init__(self, container_dims: Dict, object_dims: Dict):
        """Inicialitza l'empaquetador."""
        self.container_dims = container_dims
        self.object_dims = object_dims
        
        # Crear mesh del contenidor
        self.container_mesh = GeometryToMeshConverter.from_box_dimensions(
            container_dims['length'], 
            container_dims['width'], 
            container_dims['height']
        )
        
        # Crear mesh de l'objecte
        self.object_mesh = self._create_object_mesh(object_dims)
        
        # Generar rotacions intel·ligents
        self.rotations = RotationGenerator.get_smart_rotations(self.object_mesh)
        print(f"🔄 Generades {len(self.rotations)} rotacions intel·ligents")
    
    def _create_object_mesh(self, obj_dims: Dict) -> Mesh3D:
        """Crea el mesh de l'objecte segons el seu tipus."""
        shape_type = obj_dims.get('shape_type', 'rectangular')
        length = obj_dims['length']
        width = obj_dims['width'] 
        height = obj_dims['height']
        
        if shape_type == 'cylindrical':
            # Usar el més petit de length/width com a radi
            radius = min(length, width) / 2
            return GeometryToMeshConverter.from_cylinder(radius, height, segments=16)
        elif shape_type == 'advanced_complex':
            # Si tenim geometria complexa, usar el mesh real si està disponible
            geometry_object = obj_dims.get('geometry_object')
            if geometry_object:
                try:
                    return GeometryToMeshConverter.from_complex_geometry(geometry_object)
                except Exception as e:
                    print(f"⚠️  Error convertint geometria complexa: {e}")
                    # Fallback a caixa rectangular
                    return GeometryToMeshConverter.from_box_dimensions(length, width, height)
            else:
                return GeometryToMeshConverter.from_box_dimensions(length, width, height)
        else:
            # Per defecte: caixa rectangular
            return GeometryToMeshConverter.from_box_dimensions(length, width, height)
    
    def pack_with_collision_detection(self, max_items: int = 1000) -> PackingResult:
        """Empaqueta objectes usant collision detection amb meshes."""
        import time
        start_time = time.time()
        
        print(f"🎯 Iniciant empaquetament amb collision detection...")
        print(f"   📦 Contenidor: {self.container_dims}")
        print(f"   📋 Objecte: {self.object_dims}")
        print(f"   🔄 Rotacions disponibles: {len(self.rotations)}")
        
        packed_items = []
        
        # Generar posicions candidates de forma sistemàtica
        positions = self._generate_candidate_positions()
        print(f"   📍 Posicions candidates: {len(positions)}")
        
        items_packed = 0
        
        for pos_idx, position in enumerate(positions):
            if items_packed >= max_items:
                break
            
            # Provar cada rotació en aquesta posició
            best_rotation = None
            best_mesh = None
            
            for rot_name, rot_matrix in self.rotations:
                # Crear mesh rotat
                rotated_mesh = self.object_mesh.transform(
                    translation=position,
                    rotation_matrix=rot_matrix
                )
                
                # Comprovar si cap dins del contenidor
                if not self._fits_in_container(rotated_mesh):
                    continue
                
                # Comprovar col·lisions amb objectes ja empaquetats
                has_collision = False
                for packed_item in packed_items:
                    if BasicCollisionDetector.mesh_collision_detailed(rotated_mesh, packed_item.mesh):
                        has_collision = True
                        break
                
                if not has_collision:
                    best_rotation = (rot_name, rot_matrix)
                    best_mesh = rotated_mesh
                    break
            
            # Si hem trobat una rotació vàlida, empaquetar l'objecte
            if best_rotation:
                rot_name, rot_matrix = best_rotation
                
                # Calcular dimensions després de rotació
                rotated_dimensions = np.array([
                    best_mesh.bounds['length'],
                    best_mesh.bounds['width'], 
                    best_mesh.bounds['height']
                ])
                
                packed_item = PackedItem(
                    position=position,
                    dimensions=rotated_dimensions,
                    rotation_name=rot_name,
                    rotation_matrix=rot_matrix,
                    mesh=best_mesh,
                    original_dimensions=np.array([
                        self.object_dims['length'],
                        self.object_dims['width'],
                        self.object_dims['height']
                    ]),
                    item_id=items_packed
                )
                
                packed_items.append(packed_item)
                items_packed += 1
                
                if items_packed % 10 == 0:
                    print(f"   ✅ Empaquetats {items_packed} objectes...")
        
        # Calcular estadístiques
        packing_time = time.time() - start_time
        volume_used = sum(item.mesh.get_volume() for item in packed_items)
        volume_container = self.container_mesh.get_volume()
        efficiency = (volume_used / volume_container) * 100 if volume_container > 0 else 0
        
        result = PackingResult(
            packed_items=packed_items,
            container_dimensions=np.array([
                self.container_dims['length'],
                self.container_dims['width'],
                self.container_dims['height']
            ]),
            total_objects=len(packed_items),
            efficiency=efficiency,
            volume_used=volume_used,
            volume_container=volume_container,
            packing_time=packing_time,
            algorithm_used="mesh_collision_detection"
        )
        
        print(f"🎉 Empaquetament completat!")
        print(f"   📊 Objectes empaquetats: {result.total_objects}")
        print(f"   ⏱️  Temps: {result.packing_time:.2f}s")
        print(f"   📈 Eficiència: {result.efficiency:.1f}%")
        
        return result
    
    def _generate_candidate_positions(self) -> List[np.ndarray]:
        """Genera posicions candidates de forma sistemàtica."""
        positions = []
        
        # Usar una graella amb resolució adaptiva
        obj_dims = np.array([
            self.object_dims['length'],
            self.object_dims['width'],
            self.object_dims['height']
        ])
        
        # Resolució basada en la mida de l'objecte
        step_size = np.min(obj_dims) * 0.8  # 80% de la dimensió més petita
        
        container_dims = np.array([
            self.container_dims['length'],
            self.container_dims['width'],
            self.container_dims['height']
        ])
        
        # Generar graella 3D
        x_steps = int(container_dims[0] / step_size) + 1
        y_steps = int(container_dims[1] / step_size) + 1
        z_steps = int(container_dims[2] / step_size) + 1
        
        for i in range(x_steps):
            for j in range(y_steps):
                for k in range(z_steps):
                    x = i * step_size
                    y = j * step_size
                    z = k * step_size
                    
                    # Assegurar que no surtem del contenidor
                    if (x < container_dims[0] and 
                        y < container_dims[1] and 
                        z < container_dims[2]):
                        positions.append(np.array([x, y, z]))
        
        # Ordenar posicions per minimitzar buits (bottom-left-front first)
        positions.sort(key=lambda p: (p[2], p[1], p[0]))  # Z, Y, X
        
        return positions
    
    def _fits_in_container(self, mesh: Mesh3D) -> bool:
        """Comprova si un mesh cap dins del contenidor."""
        bounds = mesh.bounds
        
        return (bounds['min_x'] >= 0 and bounds['max_x'] <= self.container_dims['length'] and
                bounds['min_y'] >= 0 and bounds['max_y'] <= self.container_dims['width'] and
                bounds['min_z'] >= 0 and bounds['max_z'] <= self.container_dims['height'])

def optimize_packing_with_meshes(box_dims: Dict, obj_dims: Dict, max_items: int = 1000) -> Dict:
    """
    Optimitza l'empaquetament usant meshes i collision detection.
    Manté compatibilitat amb l'API existent.
    """
    try:
        # Crear empaquetador basat en meshes
        packer = MeshBasedPacker(box_dims, obj_dims)
        
        # Executar empaquetament
        result = packer.pack_with_collision_detection(max_items)
        
        # Convertir resultat al format esperat per l'API existent
        bins_data = [{
            'bin': {
                'dimensions': result.container_dimensions.tolist()
            },
            'items': []
        }]
        
        # Convertir items empaquetats
        for item in result.packed_items:
            bins_data[0]['items'].append({
                'position': item.position.tolist(),
                'dimensions': item.dimensions.tolist(),
                'rotation': item.rotation_name,
                'color': f'item_{item.item_id % 8}'
            })
        
        return {
            'max_objects': result.total_objects,
            'efficiency': result.efficiency,
            'box_volume': result.volume_container,
            'used_volume': result.volume_used,
            'bins': bins_data,
            'algorithm': result.algorithm_used,
            'packing_time': result.packing_time,
            'error': None
        }
        
    except Exception as e:
        print(f"❌ Error en empaquetament amb meshes: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'max_objects': 0,
            'efficiency': 0.0,
            'box_volume': 0.0,
            'used_volume': 0.0,
            'bins': [],
            'error': str(e)
        }

def test_mesh_packing():
    """Test de l'empaquetament basat en meshes."""
    print("🧪 Testant empaquetament amb meshes...")
    
    # Definir contenidor i objecte
    box_dims = {
        'length': 1000.0,
        'width': 800.0,
        'height': 600.0,
        'shape_type': 'rectangular',
        'volume_factor': 1.0
    }
    
    obj_dims = {
        'length': 200.0,
        'width': 150.0,
        'height': 100.0,
        'shape_type': 'rectangular',
        'volume_factor': 1.0
    }
    
    # Executar empaquetament
    result = optimize_packing_with_meshes(box_dims, obj_dims, max_items=50)
    
    print(f"\n📊 Resultats:")
    print(f"   Objectes empaquetats: {result['max_objects']}")
    print(f"   Eficiència: {result['efficiency']:.1f}%")
    print(f"   Temps: {result.get('packing_time', 0):.2f}s")
    print(f"   Algoritme: {result.get('algorithm', 'unknown')}")
    
    if result.get('error'):
        print(f"   ❌ Error: {result['error']}")
    else:
        print("   ✅ Empaquetament completat amb èxit!")

if __name__ == "__main__":
    test_mesh_packing()
