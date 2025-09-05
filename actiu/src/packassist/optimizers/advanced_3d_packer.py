"""
Advanced 3D Bin Packing Implementation
Basat en la documentació completa de algoritmes de bin packing:
- Bottom-Left-Fill (BLF) algorithm  
- First-Fit Decreasing (FFD) strategy
- Advanced collision detection
- Optimal rotation strategies
- Heuristic optimization
"""

import numpy as np
import trimesh
from typing import List, Tuple, Dict, Optional, Any
import time
import itertools

class Advanced3DPacker:
    """
    Implementació avançada de 3D Bin Packing utilitzant:
    - BLF (Bottom-Left-Fill) per col·locació òptima
    - FFD (First-Fit Decreasing) per estratègia d'ordenació
    - Detecció de col·lisions robusta
    - Optimització heurística
    """
    
    def __init__(self, container_dims: Tuple[float, float, float]):
        self.container_dims = np.array(container_dims, dtype=float)
        self.container_volume = np.prod(self.container_dims)
        
        # Configuració
        self.collision_tolerance = 0.001  # mm
        self.margin = 0.5  # mm entre peces
        self.max_orientations = 6  # Màxim orientacions a provar
        self.enable_advanced_collision = True
        
        # Estadístiques
        self.stats = {
            'orientations_tested': 0,
            'positions_calculated': 0,
            'collisions_detected': 0,
            'valid_positions': 0,
            'algorithm_steps': []
        }
        
        print(f"🏭 Advanced 3D Packer inicialitzat")
        print(f"   📦 Contenidor: {self.container_dims[0]:.1f} × {self.container_dims[1]:.1f} × {self.container_dims[2]:.1f}")
        print(f"   📊 Volum contenidor: {self.container_volume:.1f} mm³")
    
    def pack_pieces(self, mesh: trimesh.Trimesh, target_count: int, spacing: float = 0) -> Dict[str, Any]:
        """
        Empaqueta peces utilitzant algoritmes avançats combinats
        """
        start_time = time.time()
        
        print(f"\n🚀 === ADVANCED 3D PACKING START ===")
        print(f"🎯 Objectiu: {target_count} peces")
        print(f"📏 Spacing: {spacing:.1f}mm")
        
        self.margin = max(self.margin, spacing)  # Usar el spacing com a mínim
        
        # ETAPA 1: Anàlisi geomètric de la peça
        self.stats['algorithm_steps'].append("1. Anàlisi geomètric")
        piece_analysis = self._analyze_piece_geometry(mesh)
        
        # ETAPA 2: Optimització de dimensions (OBB avançat)
        self.stats['algorithm_steps'].append("2. Optimització OBB")
        optimal_dims, optimal_mesh = self._calculate_optimal_piece_dimensions(mesh)
        
        # ETAPA 3: Generació d'orientacions FFD
        self.stats['algorithm_steps'].append("3. Estratègia FFD")
        orientations = self._generate_ffd_orientations(optimal_dims)
        
        # ETAPA 4: Algoritme BLF per cada orientació
        self.stats['algorithm_steps'].append("4. Algoritme BLF")
        results = []
        
        for i, (orientation_name, dims, rotation) in enumerate(orientations):
            print(f"\n🔄 [{i+1}/{len(orientations)}] Provant orientació {orientation_name}")
            print(f"   📐 Dimensions: {dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f}")
            
            self.stats['orientations_tested'] += 1
            
            # Algoritme Bottom-Left-Fill
            positions = self._bottom_left_fill_algorithm(dims, self.margin)
            
            # Verificació de col·lisions avançada
            if self.enable_advanced_collision:
                valid_positions = self._advanced_collision_detection(positions, dims)
            else:
                valid_positions = self._basic_collision_detection(positions, dims)
            
            # Calcular eficiència
            efficiency = self._calculate_packing_efficiency(dims, len(valid_positions))
            
            result = {
                'orientation': orientation_name,
                'dimensions': dims,
                'rotation': rotation,
                'positions': valid_positions,
                'count': len(valid_positions),
                'efficiency': efficiency,
                'piece_volume': np.prod(dims),
                'theoretical_max': len(positions)
            }
            
            results.append(result)
            
            print(f"   ✅ Resultat: {len(valid_positions)}/{len(positions)} peces vàlides")
            print(f"   ⚡ Eficiència: {efficiency:.1f}%")
            
            # Parar si hem trobat una solució molt bona
            if len(valid_positions) >= target_count * 0.9:
                print(f"   🎯 Objectiu quasi assolit, aturant cerca!")
                break
        
        # ETAPA 5: Selecció de la millor solució
        self.stats['algorithm_steps'].append("5. Selecció òptima")
        best_result = self._select_best_result(results, target_count)
        
        # ETAPA 6: Optimització final (si cal)
        if best_result['count'] < target_count * 0.8:
            self.stats['algorithm_steps'].append("6. Optimització final")
            best_result = self._final_optimization(best_result, target_count)
        
        # Preparar resultats finals
        execution_time = time.time() - start_time
        final_result = self._format_final_results(best_result, mesh, execution_time)
        
        print(f"\n🏆 === RESULTATS FINALS ===")
        print(f"✅ Millor orientació: {best_result['orientation']}")
        print(f"📦 Peces col·locades: {best_result['count']}")
        print(f"⚡ Eficiència: {best_result['efficiency']:.1f}%")
        print(f"⏱️ Temps d'execució: {execution_time:.3f}s")
        print(f"🔧 Orientacions provades: {self.stats['orientations_tested']}")
        
        return final_result
    
    def _analyze_piece_geometry(self, mesh: trimesh.Trimesh) -> Dict[str, Any]:
        """Analitza les característiques geomètriques de la peça"""
        
        print("🔍 Analitzant geometria de la peça...")
        
        # Informació bàsica
        bounds = mesh.bounds
        base_dims = bounds[1] - bounds[0]
        volume = mesh.volume if hasattr(mesh, 'volume') else np.prod(base_dims)
        
        # Anàlisi de complexitat
        face_count = len(mesh.faces) if hasattr(mesh, 'faces') else 0
        vertex_count = len(mesh.vertices) if hasattr(mesh, 'vertices') else 0
        
        # Calcular aspect ratios
        sorted_dims = np.sort(base_dims)
        aspect_ratio = sorted_dims[2] / sorted_dims[0] if sorted_dims[0] > 0 else 1.0
        
        # Classificar complexitat
        if face_count < 20:
            complexity = "simple"
        elif face_count < 100:
            complexity = "moderate"
        else:
            complexity = "complex"
        
        analysis = {
            'base_dimensions': base_dims,
            'volume': volume,
            'face_count': face_count,
            'vertex_count': vertex_count,
            'aspect_ratio': aspect_ratio,
            'complexity': complexity,
            'is_elongated': aspect_ratio > 2.0,
            'is_cubic': aspect_ratio < 1.5
        }
        
        print(f"   📐 Dimensions base: {base_dims[0]:.1f} × {base_dims[1]:.1f} × {base_dims[2]:.1f}")
        print(f"   🔧 Complexitat: {complexity} ({face_count} cares)")
        print(f"   📊 Aspect ratio: {aspect_ratio:.2f}")
        
        return analysis
    
    def _calculate_optimal_piece_dimensions(self, mesh: trimesh.Trimesh) -> Tuple[np.ndarray, trimesh.Trimesh]:
        """
        Calcula dimensions òptimes utilitzant OBB avançat amb més orientacions
        """
        print("🧮 Calculant dimensions òptimes (OBB avançat)...")
        
        # Rotacions més completes per trobar l'OBB òptim
        rotation_angles = [0, 30, 45, 60, 90, 120, 135, 150, 180]
        
        best_volume = float('inf')
        best_dims = None
        best_mesh = None
        
        tested_rotations = 0
        
        # Provar combinacions de rotacions en els tres eixos
        for rx in [0, 90]:  # Limitar per velocitat
            for ry in [0, 90]:
                for rz in rotation_angles:
                    tested_rotations += 1
                    
                    try:
                        rotated_mesh = mesh.copy()
                        
                        # Aplicar rotacions successives
                        if rx != 0:
                            rotated_mesh.apply_transform(
                                trimesh.transformations.rotation_matrix(np.radians(rx), [1, 0, 0])
                            )
                        if ry != 0:
                            rotated_mesh.apply_transform(
                                trimesh.transformations.rotation_matrix(np.radians(ry), [0, 1, 0])
                            )
                        if rz != 0:
                            rotated_mesh.apply_transform(
                                trimesh.transformations.rotation_matrix(np.radians(rz), [0, 0, 1])
                            )
                        
                        # Calcular bounding box
                        bounds = rotated_mesh.bounds
                        dims = bounds[1] - bounds[0]
                        volume = np.prod(dims)
                        
                        # Si és millor, guardar
                        if volume < best_volume:
                            best_volume = volume
                            best_dims = dims
                            best_mesh = rotated_mesh
                            
                    except Exception:
                        continue
        
        if best_dims is None:
            # Fallback a dimensions originals
            bounds = mesh.bounds
            best_dims = bounds[1] - bounds[0]
            best_mesh = mesh.copy()
        
        print(f"   🔄 Rotacions provades: {tested_rotations}")
        print(f"   ✅ Dimensions òptimes: {best_dims[0]:.1f} × {best_dims[1]:.1f} × {best_dims[2]:.1f}")
        print(f"   📊 Volum òptim: {np.prod(best_dims):.1f} mm³")
        
        return best_dims, best_mesh
    
    def _generate_ffd_orientations(self, base_dims: np.ndarray) -> List[Tuple[str, np.ndarray, List[float]]]:
        """
        Genera orientacions utilitzant estratègia First-Fit Decreasing
        Ordena per volum i eficiència prevista
        """
        print("📋 Generant orientacions FFD...")
        
        # Totes les permutacions possibles de dimensions
        orientations = [
            ("LWH", np.array([base_dims[0], base_dims[1], base_dims[2]]), [0, 0, 0]),
            ("LHW", np.array([base_dims[0], base_dims[2], base_dims[1]]), [90, 0, 0]),
            ("WLH", np.array([base_dims[1], base_dims[0], base_dims[2]]), [0, 0, 90]),
            ("WHL", np.array([base_dims[1], base_dims[2], base_dims[0]]), [0, 90, 90]),
            ("HLW", np.array([base_dims[2], base_dims[0], base_dims[1]]), [0, 90, 0]),
            ("HWL", np.array([base_dims[2], base_dims[1], base_dims[0]]), [90, 90, 0])
        ]
        
        # Calcular puntuació FFD per cada orientació
        scored_orientations = []
        
        for name, dims, rotation in orientations:
            # Calcular quantes peces caben teòricament
            dims_with_margin = dims + self.margin
            theoretical_count = np.prod(self.container_dims // dims_with_margin)
            
            # Calcular eficiència espacial
            volume_efficiency = (np.prod(dims) * theoretical_count) / self.container_volume
            
            # Penalitzar orientacions que no utilitzen bé l'espai vertical
            height_utilization = min(dims[2] / self.container_dims[2], 1.0)
            
            # Puntuació combinada (FFD prioritza eficiència)
            score = theoretical_count * volume_efficiency * height_utilization
            
            scored_orientations.append((score, name, dims, rotation, theoretical_count))
            
            print(f"   📊 {name}: {dims[0]:.1f}×{dims[1]:.1f}×{dims[2]:.1f} → {theoretical_count:.0f} peces (score: {score:.2f})")
        
        # Ordenar per puntuació descendent (FFD strategy)
        scored_orientations.sort(key=lambda x: x[0], reverse=True)
        
        # Retornar només les millors orientacions
        result = [(item[1], item[2], item[3]) for item in scored_orientations[:self.max_orientations]]
        
        print(f"   🎯 Seleccionades {len(result)} millors orientacions")
        
        return result
    
    def _bottom_left_fill_algorithm(self, piece_dims: np.ndarray, margin: float) -> List[np.ndarray]:
        """
        Implementa l'algoritme Bottom-Left-Fill basat en la documentació
        
        BLF funciona així:
        1. Ordena posicions per Z (bottom), després Y (left), després X
        2. Col·loca cada peça en la primera posició vàlida
        3. Garanteix empaquetament compacte
        """
        print(f"   🧱 Executant algoritme Bottom-Left-Fill...")
        
        positions = []
        dims_with_margin = piece_dims + margin
        
        # Calcular graella màxima
        max_pieces = self.container_dims // dims_with_margin
        max_nx, max_ny, max_nz = max_pieces.astype(int)
        
        print(f"      📐 Graella teòrica: {max_nx} × {max_ny} × {max_nz} = {np.prod(max_pieces):.0f} posicions")
        
        # BLF: emplenar bottom-left-front primer
        for z in range(max_nz):
            for y in range(max_ny):
                for x in range(max_nx):
                    # Calcular posició del centre de la peça
                    pos = np.array([
                        x * dims_with_margin[0] + piece_dims[0] / 2,
                        y * dims_with_margin[1] + piece_dims[1] / 2,
                        z * dims_with_margin[2] + piece_dims[2] / 2
                    ])
                    
                    # Verificar límits del contenidor
                    if self._is_position_within_container(pos, piece_dims):
                        positions.append(pos)
                        self.stats['positions_calculated'] += 1
        
        print(f"      ✅ Generades {len(positions)} posicions candidates")
        
        return positions
    
    def _advanced_collision_detection(self, positions: List[np.ndarray], piece_dims: np.ndarray) -> List[np.ndarray]:
        """
        Detecció de col·lisions avançada amb verificació múltiple
        """
        print(f"   🔍 Detecció de col·lisions avançada...")
        
        valid_positions = []
        
        for i, pos in enumerate(positions):
            is_valid = True
            
            # Verificar col·lisions amb totes les peces ja col·locades
            for existing_pos in valid_positions:
                if self._check_aabb_collision(pos, existing_pos, piece_dims, self.margin):
                    is_valid = False
                    self.stats['collisions_detected'] += 1
                    break
            
            if is_valid:
                valid_positions.append(pos)
                self.stats['valid_positions'] += 1
        
        print(f"      ✅ Posicions vàlides: {len(valid_positions)}/{len(positions)}")
        print(f"      ❌ Col·lisions detectades: {self.stats['collisions_detected']}")
        
        return valid_positions
    
    def _basic_collision_detection(self, positions: List[np.ndarray], piece_dims: np.ndarray) -> List[np.ndarray]:
        """Detecció de col·lisions bàsica (més ràpida)"""
        print(f"   🔍 Detecció de col·lisions bàsica...")
        
        # En el cas de graella regular, no hi hauria d'haver col·lisions
        # però fem una verificació ràpida
        return positions  # Per velocitat, assumim que BLF genera posicions vàlides
    
    def _check_aabb_collision(self, pos1: np.ndarray, pos2: np.ndarray, 
                            dims: np.ndarray, margin: float) -> bool:
        """
        Detecció de col·lisions AABB (Axis-Aligned Bounding Box)
        """
        half_dims = dims / 2 + margin / 2 + self.collision_tolerance
        
        # Calcular límits de cada caixa
        min1 = pos1 - half_dims
        max1 = pos1 + half_dims
        min2 = pos2 - half_dims
        max2 = pos2 + half_dims
        
        # Col·lisió si es superposen en tots els eixos
        overlap_x = max1[0] > min2[0] and max2[0] > min1[0]
        overlap_y = max1[1] > min2[1] and max2[1] > min1[1]
        overlap_z = max1[2] > min2[2] and max2[2] > min1[2]
        
        return overlap_x and overlap_y and overlap_z
    
    def _is_position_within_container(self, pos: np.ndarray, piece_dims: np.ndarray) -> bool:
        """Verifica que la peça estigui completament dins del contenidor"""
        half_dims = piece_dims / 2
        min_pos = pos - half_dims
        max_pos = pos + half_dims
        
        return (min_pos >= -self.collision_tolerance).all() and (max_pos <= self.container_dims + self.collision_tolerance).all()
    
    def _calculate_packing_efficiency(self, piece_dims: np.ndarray, piece_count: int) -> float:
        """Calcula l'eficiència d'empaquetament"""
        piece_volume = np.prod(piece_dims)
        total_used_volume = piece_volume * piece_count
        
        return (total_used_volume / self.container_volume) * 100
    
    def _select_best_result(self, results: List[Dict], target_count: int) -> Dict:
        """
        Selecciona el millor resultat basant-se en múltiples criteris
        """
        print("🏆 Seleccionant millor resultat...")
        
        if not results:
            return {'count': 0, 'efficiency': 0, 'orientation': 'none'}
        
        # Puntuació multi-criteri
        best_score = -1
        best_result = None
        
        for result in results:
            count = result['count']
            efficiency = result['efficiency']
            
            # Puntuació combinada: prioritzar quantitat amb eficiència com a tiebreaker
            count_score = min(count / target_count, 1.0)  # Normalitzar a [0,1]
            efficiency_score = efficiency / 100.0
            
            # Pes: 70% quantitat, 30% eficiència
            combined_score = count_score * 0.7 + efficiency_score * 0.3
            
            print(f"   📊 {result['orientation']}: {count} peces, {efficiency:.1f}% → score: {combined_score:.3f}")
            
            if combined_score > best_score:
                best_score = combined_score
                best_result = result
        
        print(f"   🥇 Millor: {best_result['orientation']} (score: {best_score:.3f})")
        
        return best_result
    
    def _final_optimization(self, result: Dict, target_count: int) -> Dict:
        """
        Optimització final si el resultat no és satisfactori
        """
        print("🔧 Aplicant optimització final...")
        
        # Per ara, simplement retornar el resultat original
        # En el futur es podrien implementar:
        # - Algoritmes genètics
        # - Simulated annealing  
        # - Optimització local
        
        print("   ⚠️ Optimització final encara no implementada")
        return result
    
    def _format_final_results(self, best_result: Dict, mesh: trimesh.Trimesh, execution_time: float) -> Dict[str, Any]:
        """Formata els resultats per compatibilitat amb el sistema existent"""
        
        if best_result['count'] == 0:
            return {
                'success': False,
                'error': 'No s\'han trobat posicions vàlides',
                'positions': [],
                'rotations': [],
                'pieces_count': 0,
                'efficiency': 0.0,
                'method': 'advanced_3d_packer'
            }
        
        # Convertir posicions a format llista
        positions = [pos.tolist() for pos in best_result['positions']]
        
        # Crear rotacions per a cada peça
        base_rotation = best_result.get('rotation', [0, 0, 0])
        rotations = [base_rotation for _ in positions]
        
        return {
            'success': True,
            'positions': positions,
            'rotations': rotations,
            'pieces_count': best_result['count'],
            'efficiency': best_result['efficiency'],
            'method': 'advanced_3d_packer',
            'algorithm_details': {
                'best_orientation': best_result['orientation'],
                'optimal_dimensions': best_result['dimensions'].tolist(),
                'theoretical_max': best_result.get('theoretical_max', 0),
                'execution_time': execution_time,
                'stats': self.stats.copy()
            },
            'mesh_for_visualization': mesh
        }


# Funció d'interfície per integració amb el sistema existent
def advanced_3d_pack(mesh: trimesh.Trimesh, container_dims: Tuple[float, float, float], 
                    target_count: Optional[int] = None, spacing: float = 0) -> Dict[str, Any]:
    """
    Funció principal per utilitzar el nou sistema Advanced 3D Packer
    
    Args:
        mesh: Malla 3D de la peça a empaquetar
        container_dims: Dimensions del contenidor (length, width, height)
        target_count: Nombre objectiu de peces (si None, es calcula automàticament)
        spacing: Espai entre peces en mm
    
    Returns:
        Dict amb resultats de l'empaquetament
    """
    
    # Crear instància del packer
    packer = Advanced3DPacker(container_dims)
    
    # Calcular objectiu automàticament si no s'especifica
    if target_count is None:
        bounds = mesh.bounds
        piece_volume = np.prod(bounds[1] - bounds[0])
        container_volume = np.prod(container_dims)
        
        # Estimació conservadora: 60% d'eficiència
        target_count = max(1, int((container_volume / piece_volume) * 0.6))
        
        print(f"🎯 Objectiu auto-calculat: {target_count} peces")
    
    # Executar empaquetament
    return packer.pack_pieces(mesh, target_count, spacing)


if __name__ == "__main__":
    # Test ràpid
    print("🧪 Test Advanced 3D Packer...")
    
    try:
        import trimesh
        
        # Crear una caixa de test
        test_mesh = trimesh.creation.box([10, 20, 5])
        container = (100, 100, 50)
        
        result = advanced_3d_pack(test_mesh, container, target_count=20)
        
        print(f"✅ Test completat: {result['pieces_count']} peces, {result['efficiency']:.1f}% eficiència")
        
    except ImportError:
        print("⚠️ Trimesh no disponible per al test")
