"""
Integració millora per a PackAssist amb optimització OBB avançada
Implementa empaquetament per pisos amb orientacions múltiples i millor gestió espacial
"""

import numpy as np
import trimesh
from typing import List, Tuple, Dict, Any, Optional
import time

# Import absoluts per evitar problemes amb importacions relatives
try:
    from obb_optimizer import OBBOptimizer
    from normal_optimizer import NormalPackingOptimizer
except ImportError:
    # Fallback per quan s'executa des de fora del package
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)
    from obb_optimizer import OBBOptimizer
    from normal_optimizer import NormalPackingOptimizer

class ImprovedOBBPackingSystem:
    """Sistema d'empaquetament millorat amb OBB i orientacions múltiples per pisos"""
    
    def __init__(self, container_dims: Tuple[float, float, float]):
        self.container_length, self.container_width, self.container_height = container_dims
        self.container_volume = self.container_length * self.container_width * self.container_height
        
        # Configuració de l'empaquetament
        self.margin = 2.0
        self.inter_level_spacing = 2.0
        self.enable_multi_orientation = True
        self.enable_smart_rotation = True
        
        # Inicialitzar optimitzadors
        self.obb_optimizer = OBBOptimizer(container_dims)
        self.normal_optimizer = NormalPackingOptimizer(container_dims)
        
    def configure_packing_parameters(self, margin: float = 2.0, spacing: float = 2.0,
                                   multi_orientation: bool = True, smart_rotation: bool = True):
        """Configura els paràmetres d'empaquetament"""
        self.margin = margin
        self.inter_level_spacing = spacing
        self.enable_multi_orientation = multi_orientation
        self.enable_smart_rotation = smart_rotation
        
        # Aplicar configuració als optimitzadors
        self.obb_optimizer.set_margin(margin)
        self.obb_optimizer.set_inter_level_spacing(spacing)
        self.obb_optimizer.set_rotation_mode(smart_rotation)
        
        self.normal_optimizer.set_margin(margin)
        self.normal_optimizer.set_floor_separation(spacing)
    
    def optimize_packing_with_floors(self, mesh: trimesh.Trimesh, target_pieces: int) -> Dict[str, Any]:
        """
        Optimitza l'empaquetament amb estratègia de pisos millorada
        Combina OBB amb orientacions múltiples per maximitzar l'eficiència
        """
        start_time = time.time()
        
        print("🚀 Sistema d'empaquetament millorat amb OBB i orientacions múltiples")
        print("="*80)
        
        # Provar diferents estratègies d'empaquetament
        strategies = []
        
        # Estratègia 1: OBB pur amb orientacions múltiples
        if self.enable_multi_orientation:
            print("📐 Provant estratègia OBB amb orientacions múltiples...")
            obb_result = self._obb_multi_orientation_strategy(mesh, target_pieces)
            strategies.append(('obb_multi_orientation', obb_result))
        
        # Estratègia 2: Híbrida OBB + Normal optimitzat
        print("🔄 Provant estratègia híbrida OBB + Normal...")
        hybrid_result = self._hybrid_obb_normal_strategy(mesh, target_pieces)
        strategies.append(('hybrid_obb_normal', hybrid_result))
        
        # Estratègia 3: Normal amb millores d'orientació
        print("🧠 Provant estratègia normal millorada...")
        normal_result = self._improved_normal_strategy(mesh, target_pieces)
        strategies.append(('improved_normal', normal_result))
        
        # Seleccionar la millor estratègia
        best_strategy = self._select_best_strategy(strategies)
        
        execution_time = time.time() - start_time
        best_strategy['execution_time'] = execution_time
        best_strategy['strategies_tested'] = len(strategies)
        
        print("="*80)
        print(f"✅ Millor estratègia: {best_strategy.get('method', 'unknown')}")
        print(f"📊 Peces col·locades: {best_strategy.get('pieces_count', 0)}")
        print(f"⚡ Eficiència: {best_strategy.get('efficiency', 0):.1f}%")
        print(f"⏱️ Temps d'execució: {execution_time:.3f}s")
        
        return best_strategy
    
    def _obb_multi_orientation_strategy(self, mesh: trimesh.Trimesh, target_pieces: int) -> Dict[str, Any]:
        """Estratègia basada en OBB amb múltiples orientacions per pis"""
        try:
            # Configurar per orientacions múltiples
            self.obb_optimizer.set_rotation_mode(True)
            result = self.obb_optimizer.optimize_with_obb(mesh, target_pieces)
            
            if result.get('success', False):
                result['strategy_type'] = 'obb_multi_orientation'
                result['description'] = 'OBB amb orientacions múltiples per pisos'
            
            return result
        except Exception as e:
            return self._create_error_result(f"Error en estratègia OBB: {e}")
    
    def _hybrid_obb_normal_strategy(self, mesh: trimesh.Trimesh, target_pieces: int) -> Dict[str, Any]:
        """Estratègia híbrida que combina OBB per orientació i Normal per col·locació"""
        try:
            # Primera fase: Calcular OBB òptim
            obb = mesh.bounding_box_oriented
            obj_dims = obb.extents
            
            # Segona fase: Usar l'optimitzador normal amb dimensions OBB
            result = self.normal_optimizer.optimize(mesh, target_pieces, method="intelligent")
            
            if result.get('success', False):
                result['strategy_type'] = 'hybrid_obb_normal'
                result['description'] = 'Híbrida: OBB per orientació + Normal per col·locació'
                result['obb_dims'] = obj_dims.tolist()
            
            return result
        except Exception as e:
            return self._create_error_result(f"Error en estratègia híbrida: {e}")
    
    def _improved_normal_strategy(self, mesh: trimesh.Trimesh, target_pieces: int) -> Dict[str, Any]:
        """Estratègia normal millorada amb orientacions intel·ligents"""
        try:
            result = self.normal_optimizer.optimize(mesh, target_pieces, method="intelligent")
            
            if result.get('success', False):
                result['strategy_type'] = 'improved_normal'
                result['description'] = 'Normal millorat amb orientacions intel·ligents'
            
            return result
        except Exception as e:
            return self._create_error_result(f"Error en estratègia normal: {e}")
    
    def _select_best_strategy(self, strategies: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, Any]:
        """Selecciona la millor estratègia basant-se en múltiples criteris"""
        best_strategy = None
        best_score = -1
        
        print("\n📈 Comparació d'estratègies:")
        print("-" * 60)
        
        for name, result in strategies:
            if not result.get('success', False):
                print(f"❌ {name}: Error - {result.get('error', 'Unknown')}")
                continue
            
            pieces = result.get('pieces_count', 0)
            efficiency = result.get('efficiency', 0)
            
            # Funció de puntuació que combina quantitat i eficiència
            score = pieces * 0.7 + efficiency * 0.3
            
            print(f"📊 {name}:")
            print(f"   Peces: {pieces}, Eficiència: {efficiency:.1f}%, Puntuació: {score:.1f}")
            
            if score > best_score:
                best_score = score
                best_strategy = result
                best_strategy['method'] = result.get('strategy_type', name)
        
        if best_strategy is None:
            return self._create_error_result("Cap estratègia ha funcionat correctament")
        
        return best_strategy
    
    def visualize_floor_organization(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Genera informació detallada sobre l'organització per pisos"""
        if not result.get('success', False):
            return {'error': 'No hi ha resultats vàlids per visualitzar'}
        
        positions = result.get('positions', [])
        if not positions:
            return {'error': 'No hi ha posicions per analitzar'}
        
        # Analitzar distribució per pisos
        floors_info = self._analyze_detailed_floor_distribution(positions, result)
        
        # Afegir informació d'orientacions si està disponible
        rotations = result.get('rotations', [])
        if rotations:
            floors_info['orientation_analysis'] = self._analyze_orientations_by_floor(positions, rotations)
        
        return floors_info
    
    def _analyze_detailed_floor_distribution(self, positions: List[List[float]], 
                                           result: Dict[str, Any]) -> Dict[str, Any]:
        """Analitza en detall la distribució de peces per pisos"""
        obj_dims = result.get('obj_dims', {})
        piece_height = obj_dims.get('height', 0)
        
        if piece_height == 0:
            return {'error': 'No es pot determinar l\'altura de les peces'}
        
        # Agrupar per alturas amb tolerància
        z_values = [pos[2] for pos in positions]
        z_values.sort()
        
        floors = []
        current_floor_z = None
        current_floor_pieces = []
        tolerance = piece_height * 0.1  # 10% d'altura com a tolerància
        
        for i, (pos, z) in enumerate(zip(positions, z_values)):
            if current_floor_z is None or abs(z - current_floor_z) <= tolerance:
                # Mateixa planta
                if current_floor_z is None:
                    current_floor_z = z
                current_floor_pieces.append({'index': i, 'position': pos})
            else:
                # Nova planta
                floors.append({
                    'floor_number': len(floors) + 1,
                    'z_level': current_floor_z,
                    'pieces_count': len(current_floor_pieces),
                    'pieces': current_floor_pieces.copy()
                })
                current_floor_z = z
                current_floor_pieces = [{'index': i, 'position': pos}]
        
        # Afegir última planta
        if current_floor_pieces:
            floors.append({
                'floor_number': len(floors) + 1,
                'z_level': current_floor_z,
                'pieces_count': len(current_floor_pieces),
                'pieces': current_floor_pieces
            })
        
        return {
            'total_floors': len(floors),
            'floors_detail': floors,
            'pieces_distribution': [floor['pieces_count'] for floor in floors],
            'floor_heights': [floor['z_level'] for floor in floors],
            'average_pieces_per_floor': sum(floor['pieces_count'] for floor in floors) / len(floors) if floors else 0
        }
    
    def _analyze_orientations_by_floor(self, positions: List[List[float]], 
                                     rotations: List[List[float]]) -> Dict[str, Any]:
        """Analitza les orientacions per cada pis"""
        # Agrupar rotacions per pis similar a l'anàlisi de posicions
        analysis = {}
        
        # Simplificat: comptar rotacions úniques
        unique_rotations = {}
        for rotation in rotations:
            rot_key = tuple(rotation)
            unique_rotations[rot_key] = unique_rotations.get(rot_key, 0) + 1
        
        return {
            'unique_orientations': len(unique_rotations),
            'rotation_distribution': unique_rotations,
            'has_multiple_orientations': len(unique_rotations) > 1
        }
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """Crea un resultat d'error estandarditzat"""
        return {
            'success': False,
            'error': error_message,
            'positions': [],
            'rotations': [],
            'pieces_count': 0,
            'efficiency': 0.0,
            'method': 'error'
        }
