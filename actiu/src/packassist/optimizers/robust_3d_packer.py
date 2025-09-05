"""
Optimitzador 3D Robust basat en les recomanacions de l'anàlisi
Implementa múltiples algoritmes segons les característiques de l'objecte
"""

import numpy as np
import trimesh
from typing import List, Tuple, Dict, Any, Optional
import time
from scipy.spatial.distance import cdist
from scipy.spatial import ConvexHull

class Robust3DPacker:
    """
    Optimitzador 3D robust que selecciona l'algoritme apropiat
    segons les característiques de l'objecte i contenidor
    """
    
    def __init__(self, container_dims: Tuple[float, float, float]):
        self.container_length, self.container_width, self.container_height = container_dims
        self.container_volume = np.prod(container_dims)
        
        # Configuració
        self.margin = 1.0  # Marge entre peces
        self.collision_tolerance = 0.1  # Tolerància per col·lisions
        self.voxel_resolution = 2.0  # Resolució del grid de voxels
        
        # Estadístiques
        self.stats = {
            'orientations_tested': 0,
            'positions_tested': 0,
            'collisions_detected': 0,
            'algorithm_used': 'none'
        }
    
    def optimize_packing(self, mesh: trimesh.Trimesh, target_pieces: int) -> Dict[str, Any]:
        """
        Optimitza l'empaquetament seleccionant l'algoritme més apropiat
        """
        start_time = time.time()
        
        print("🚀 OPTIMITZADOR 3D ROBUST - Anàlisi inicial")
        print("=" * 60)
        
        # 1. Analitzar característiques de l'objecte
        object_analysis = self._analyze_object_characteristics(mesh)
        print(f"📊 Tipus d'objecte detectat: {object_analysis['type']}")
        print(f"🔍 Complexitat: {object_analysis['complexity']}")
        print(f"📐 Simetria: {object_analysis['symmetry']}")
        
        # 2. Seleccionar algoritme apropiat
        algorithm = self._select_optimal_algorithm(object_analysis)
        print(f"🎯 Algoritme seleccionat: {algorithm}")
        
        # 3. Executar optimització
        result = self._execute_packing_algorithm(mesh, target_pieces, algorithm, object_analysis)
        
        # 4. Afegir informació de l'anàlisi
        result['object_analysis'] = object_analysis
        result['execution_time'] = time.time() - start_time
        result['stats'] = self.stats.copy()
        
        print("=" * 60)
        print(f"✅ Optimització completada en {result['execution_time']:.3f}s")
        print(f"📦 Peces col·locades: {result.get('pieces_count', 0)}")
        print(f"⚡ Eficiència: {result.get('efficiency', 0):.1f}%")
        
        return result
    
    def _analyze_object_characteristics(self, mesh: trimesh.Trimesh) -> Dict[str, Any]:
        """Analitza les característiques de l'objecte per seleccionar l'algoritme"""
        
        # Informació bàsica
        bounds = mesh.bounds
        dimensions = bounds[1] - bounds[0]
        volume = mesh.volume
        area = mesh.area
        face_count = len(mesh.faces)
        
        # Calcular aspecte ratio
        sorted_dims = np.sort(dimensions)
        aspect_ratio = sorted_dims[2] / sorted_dims[0] if sorted_dims[0] > 0 else 1.0
        
        # Determinar tipus d'objecte
        object_type = self._classify_object_type(mesh, dimensions, face_count, aspect_ratio)
        
        # Calcular complexitat geomètrica
        complexity = self._calculate_geometric_complexity(mesh, face_count, aspect_ratio)
        
        # Analitzar simetria
        symmetry = self._analyze_symmetry(mesh, dimensions)
        
        return {
            'type': object_type,
            'complexity': complexity,
            'symmetry': symmetry,
            'dimensions': dimensions,
            'volume': volume,
            'area': area,
            'face_count': face_count,
            'aspect_ratio': aspect_ratio,
            'bounds': bounds
        }
    
    def _classify_object_type(self, mesh: trimesh.Trimesh, dimensions: np.ndarray, 
                            face_count: int, aspect_ratio: float) -> str:
        """Classifica el tipus d'objecte"""
        
        # Objectes molt simples (menys de 12 cares)
        if face_count <= 12:
            if aspect_ratio < 1.5:
                return "simple_cubic"
            else:
                return "simple_elongated"
        
        # Objectes regulars
        elif face_count <= 50 and aspect_ratio < 2.0:
            return "regular_geometric"
        
        # Objectes complexes
        elif face_count <= 200:
            return "moderate_complex"
        
        # Objectes molt complexes
        else:
            return "highly_complex"
    
    def _calculate_geometric_complexity(self, mesh: trimesh.Trimesh, 
                                      face_count: int, aspect_ratio: float) -> str:
        """Calcula la complexitat geomètrica"""
        
        # Factor basat en el nombre de cares
        face_factor = min(face_count / 100.0, 3.0)
        
        # Factor basat en aspect ratio
        ratio_factor = min(aspect_ratio / 2.0, 2.0)
        
        # Factor basat en convexitat
        try:
            convex_hull = mesh.convex_hull
            convexity = mesh.volume / convex_hull.volume if convex_hull.volume > 0 else 0
        except:
            convexity = 0.5
        
        complexity_score = face_factor + ratio_factor + (1 - convexity)
        
        if complexity_score < 1.0:
            return "low"
        elif complexity_score < 2.5:
            return "medium"
        else:
            return "high"
    
    def _analyze_symmetry(self, mesh: trimesh.Trimesh, dimensions: np.ndarray) -> Dict[str, bool]:
        """Analitza la simetria de l'objecte"""
        
        # Simplificat: basat en dimensions
        dim_tolerance = 0.1 * np.max(dimensions)
        
        x_y_symmetric = abs(dimensions[0] - dimensions[1]) < dim_tolerance
        x_z_symmetric = abs(dimensions[0] - dimensions[2]) < dim_tolerance
        y_z_symmetric = abs(dimensions[1] - dimensions[2]) < dim_tolerance
        
        return {
            'x_y_symmetric': x_y_symmetric,
            'x_z_symmetric': x_z_symmetric,
            'y_z_symmetric': y_z_symmetric,
            'highly_symmetric': x_y_symmetric and x_z_symmetric and y_z_symmetric
        }
    
    def _select_optimal_algorithm(self, analysis: Dict[str, Any]) -> str:
        """Selecciona l'algoritme òptim segons l'anàlisi"""
        
        obj_type = analysis['type']
        complexity = analysis['complexity']
        
        # Objectes simples: algoritme de graella optimitzada
        if obj_type in ['simple_cubic', 'simple_elongated'] and complexity == 'low':
            return "optimized_grid"
        
        # Objectes regulars: Bottom-Left-Fill amb orientacions limitades
        elif obj_type == 'regular_geometric' and complexity in ['low', 'medium']:
            return "blf_with_rotations"
        
        # Objectes complexos: algoritme híbrid avançat
        elif complexity == 'high' or obj_type in ['moderate_complex', 'highly_complex']:
            return "hybrid_advanced"
        
        # Per defecte: Bottom-Left-Fill estàndard
        else:
            return "blf_standard"
    
    def _execute_packing_algorithm(self, mesh: trimesh.Trimesh, target_pieces: int, 
                                 algorithm: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Executa l'algoritme d'empaquetament seleccionat"""
        
        self.stats['algorithm_used'] = algorithm
        
        if algorithm == "optimized_grid":
            return self._optimized_grid_packing(mesh, target_pieces, analysis)
        
        elif algorithm == "blf_with_rotations":
            return self._blf_with_rotations_packing(mesh, target_pieces, analysis)
        
        elif algorithm == "hybrid_advanced":
            return self._hybrid_advanced_packing(mesh, target_pieces, analysis)
        
        else:  # blf_standard
            return self._blf_standard_packing(mesh, target_pieces, analysis)
    
    def _optimized_grid_packing(self, mesh: trimesh.Trimesh, target_pieces: int, 
                              analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Empaquetament optimitzat per objectes simples"""
        print("🔧 Executant algoritme de graella optimitzada...")
        
        # Per objectes simples, provar poques orientacions òptimes
        orientations = self._get_simple_orientations(analysis)
        
        best_result = None
        best_count = 0
        
        for orientation_info in orientations:
            oriented_mesh = self._apply_orientation(mesh, orientation_info['rotation'])
            oriented_dims = self._get_mesh_dimensions(oriented_mesh)
            
            # Calcular empaquetament en graella perfecta
            pieces_per_axis = [
                int(self.container_length // (oriented_dims[0] + self.margin)),
                int(self.container_width // (oriented_dims[1] + self.margin)),
                int(self.container_height // (oriented_dims[2] + self.margin))
            ]
            
            total_pieces = np.prod(pieces_per_axis)
            
            if total_pieces > best_count:
                best_count = min(total_pieces, target_pieces)
                best_result = {
                    'oriented_mesh': oriented_mesh,
                    'oriented_dims': oriented_dims,
                    'pieces_per_axis': pieces_per_axis,
                    'rotation': orientation_info['rotation']
                }
        
        if best_result is None:
            return self._create_error_result("No s'ha trobat cap orientació vàlida")
        
        # Generar posicions en graella perfecta
        positions, rotations = self._generate_grid_positions(
            best_result['pieces_per_axis'], 
            best_result['oriented_dims'],
            best_result['rotation'],
            best_count
        )
        
        return self._create_success_result(positions, rotations, best_result['oriented_mesh'])
    
    def _blf_with_rotations_packing(self, mesh: trimesh.Trimesh, target_pieces: int, 
                                  analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Bottom-Left-Fill amb rotacions per objectes regulars"""
        print("🔧 Executant Bottom-Left-Fill amb rotacions...")
        
        # Provar diverses orientacions
        orientations = self._get_moderate_orientations(analysis)
        
        best_result = None
        best_count = 0
        
        for orientation_info in orientations:
            self.stats['orientations_tested'] += 1
            
            oriented_mesh = self._apply_orientation(mesh, orientation_info['rotation'])
            oriented_dims = self._get_mesh_dimensions(oriented_mesh)
            
            # Executar Bottom-Left-Fill
            positions, rotations = self._bottom_left_fill(oriented_dims, orientation_info['rotation'], target_pieces)
            
            if len(positions) > best_count:
                best_count = len(positions)
                best_result = {
                    'positions': positions,
                    'rotations': rotations,
                    'oriented_mesh': oriented_mesh
                }
        
        if best_result is None:
            return self._create_error_result("BLF no ha trobat posicions vàlides")
        
        return self._create_success_result(
            best_result['positions'], 
            best_result['rotations'], 
            best_result['oriented_mesh']
        )
    
    def _hybrid_advanced_packing(self, mesh: trimesh.Trimesh, target_pieces: int, 
                               analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Algoritme híbrid avançat per objectes complexos"""
        print("🔧 Executant algoritme híbrid avançat...")
        
        # Combinar múltiples estratègies
        strategies = [
            ("grid", self._optimized_grid_packing),
            ("blf", self._blf_with_rotations_packing),
            ("advanced_blf", self._advanced_blf_packing)
        ]
        
        best_result = None
        best_count = 0
        
        for strategy_name, strategy_func in strategies:
            try:
                result = strategy_func(mesh, target_pieces, analysis)
                
                if result.get('success', False):
                    piece_count = result.get('pieces_count', 0)
                    if piece_count > best_count:
                        best_count = piece_count
                        best_result = result
                        best_result['strategy_used'] = strategy_name
            except Exception as e:
                print(f"   ⚠️ Estratègia {strategy_name} ha fallat: {e}")
                continue
        
        if best_result is None:
            return self._create_error_result("Totes les estratègies híbrides han fallat")
        
        return best_result
    
    def _blf_standard_packing(self, mesh: trimesh.Trimesh, target_pieces: int, 
                            analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Bottom-Left-Fill estàndard"""
        print("🔧 Executant Bottom-Left-Fill estàndard...")
        
        # Usar orientació per defecte o la millor trobada ràpidament
        oriented_mesh = mesh.copy()
        oriented_dims = analysis['dimensions']
        base_rotation = [0, 0, 0]
        
        positions, rotations = self._bottom_left_fill(oriented_dims, base_rotation, target_pieces)
        
        return self._create_success_result(positions, rotations, oriented_mesh)
    
    def _advanced_blf_packing(self, mesh: trimesh.Trimesh, target_pieces: int, 
                            analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Bottom-Left-Fill avançat amb detecció de col·lisions precisa"""
        print("🔧 Executant BLF avançat amb detecció de col·lisions...")
        
        oriented_mesh = mesh.copy()
        oriented_dims = analysis['dimensions']
        
        positions = []
        rotations = []
        occupied_space = []  # Llista de regions ocupades
        
        # Generar candidats de posició de forma més intel·ligent
        candidates = self._generate_smart_position_candidates(oriented_dims)
        
        for candidate_pos in candidates:
            if len(positions) >= target_pieces:
                break
            
            self.stats['positions_tested'] += 1
            
            # Verificar col·lisions amb detecció precisa
            if self._is_position_valid_advanced(candidate_pos, oriented_dims, occupied_space):
                positions.append(candidate_pos)
                rotations.append([0, 0, 0])  # Rotació base per ara
                
                # Afegir regió ocupada
                occupied_space.append({
                    'position': candidate_pos,
                    'dimensions': oriented_dims
                })
            else:
                self.stats['collisions_detected'] += 1
        
        return self._create_success_result(positions, rotations, oriented_mesh)
    
    # === FUNCIONS AUXILIARS ===
    
    def _get_simple_orientations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Orientacions per objectes simples"""
        return [
            {'rotation': [0, 0, 0], 'name': 'original'},
            {'rotation': [90, 0, 0], 'name': 'rotated_x'},
            {'rotation': [0, 90, 0], 'name': 'rotated_y'},
            {'rotation': [0, 0, 90], 'name': 'rotated_z'}
        ]
    
    def _get_moderate_orientations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Orientacions per objectes regulars"""
        orientations = []
        
        # Orientacions bàsiques
        basic_rotations = [
            [0, 0, 0], [90, 0, 0], [0, 90, 0], [0, 0, 90],
            [90, 90, 0], [90, 0, 90], [0, 90, 90]
        ]
        
        for i, rotation in enumerate(basic_rotations):
            orientations.append({'rotation': rotation, 'name': f'orientation_{i}'})
        
        return orientations
    
    def _apply_orientation(self, mesh: trimesh.Trimesh, rotation: List[float]) -> trimesh.Trimesh:
        """Aplica una rotació a la malla"""
        oriented_mesh = mesh.copy()
        
        if rotation[0] != 0:
            oriented_mesh.apply_transform(
                trimesh.transformations.rotation_matrix(np.radians(rotation[0]), [1, 0, 0])
            )
        if rotation[1] != 0:
            oriented_mesh.apply_transform(
                trimesh.transformations.rotation_matrix(np.radians(rotation[1]), [0, 1, 0])
            )
        if rotation[2] != 0:
            oriented_mesh.apply_transform(
                trimesh.transformations.rotation_matrix(np.radians(rotation[2]), [0, 0, 1])
            )
        
        return oriented_mesh
    
    def _get_mesh_dimensions(self, mesh: trimesh.Trimesh) -> np.ndarray:
        """Obté les dimensions de la malla"""
        bounds = mesh.bounds
        return bounds[1] - bounds[0]
    
    def _generate_grid_positions(self, pieces_per_axis: List[int], piece_dims: np.ndarray, 
                               rotation: List[float], max_pieces: int) -> Tuple[List[List[float]], List[List[float]]]:
        """Genera posicions en graella perfecta"""
        positions = []
        rotations = []
        
        piece_spacing = piece_dims + self.margin
        
        count = 0
        for k in range(pieces_per_axis[2]):
            for j in range(pieces_per_axis[1]):
                for i in range(pieces_per_axis[0]):
                    if count >= max_pieces:
                        break
                    
                    pos = [
                        i * piece_spacing[0] + piece_dims[0] / 2,
                        j * piece_spacing[1] + piece_dims[1] / 2,
                        k * piece_spacing[2] + piece_dims[2] / 2
                    ]
                    
                    positions.append(pos)
                    rotations.append(rotation)
                    count += 1
                
                if count >= max_pieces:
                    break
            if count >= max_pieces:
                break
        
        return positions, rotations
    
    def _bottom_left_fill(self, piece_dims: np.ndarray, base_rotation: List[float], 
                         max_pieces: int) -> Tuple[List[List[float]], List[List[float]]]:
        """Implementació Bottom-Left-Fill"""
        positions = []
        rotations = []
        
        # Grid de posicions candidates
        step_size = min(piece_dims) / 2  # Resolució del grid
        
        x_positions = np.arange(piece_dims[0]/2, self.container_length - piece_dims[0]/2 + step_size, step_size)
        y_positions = np.arange(piece_dims[1]/2, self.container_width - piece_dims[1]/2 + step_size, step_size)
        z_positions = np.arange(piece_dims[2]/2, self.container_height - piece_dims[2]/2 + step_size, step_size)
        
        # Ordenar per Bottom-Left: Z primer, després Y, després X
        for z in z_positions:
            for y in y_positions:
                for x in x_positions:
                    if len(positions) >= max_pieces:
                        break
                    
                    candidate = [x, y, z]
                    
                    if self._is_position_valid_simple(candidate, piece_dims, positions):
                        positions.append(candidate)
                        rotations.append(base_rotation)
                
                if len(positions) >= max_pieces:
                    break
            if len(positions) >= max_pieces:
                break
        
        return positions, rotations
    
    def _generate_smart_position_candidates(self, piece_dims: np.ndarray) -> List[List[float]]:
        """Genera candidats de posició de forma intel·ligent"""
        candidates = []
        
        # Resolució adaptativa segons mida de la peça
        resolution = min(piece_dims) / 3
        
        x_range = np.arange(piece_dims[0]/2, self.container_length - piece_dims[0]/2 + resolution, resolution)
        y_range = np.arange(piece_dims[1]/2, self.container_width - piece_dims[1]/2 + resolution, resolution)
        z_range = np.arange(piece_dims[2]/2, self.container_height - piece_dims[2]/2 + resolution, resolution)
        
        # Prioritzar Bottom-Left-Fill
        for z in z_range:
            for y in y_range:
                for x in x_range:
                    candidates.append([x, y, z])
        
        return candidates
    
    def _is_position_valid_simple(self, position: List[float], piece_dims: np.ndarray, 
                                existing_positions: List[List[float]]) -> bool:
        """Verificació simple de posició vàlida"""
        x, y, z = position
        dx, dy, dz = piece_dims / 2
        
        # Verificar límits del contenidor
        if (x - dx < 0 or x + dx > self.container_length or
            y - dy < 0 or y + dy > self.container_width or
            z - dz < 0 or z + dz > self.container_height):
            return False
        
        # Verificar col·lisions amb peces existents
        for existing_pos in existing_positions:
            if self._boxes_overlap(position, existing_pos, piece_dims, piece_dims):
                return False
        
        return True
    
    def _is_position_valid_advanced(self, position: List[float], piece_dims: np.ndarray, 
                                  occupied_regions: List[Dict]) -> bool:
        """Verificació avançada de posició amb detecció precisa"""
        x, y, z = position
        dx, dy, dz = piece_dims / 2
        
        # Verificar límits del contenidor
        if (x - dx < 0 or x + dx > self.container_length or
            y - dy < 0 or y + dy > self.container_width or
            z - dz < 0 or z + dz > self.container_height):
            return False
        
        # Verificar col·lisions amb regions ocupades
        for region in occupied_regions:
            existing_pos = region['position']
            existing_dims = region['dimensions']
            
            if self._boxes_overlap(position, existing_pos, piece_dims, existing_dims):
                return False
        
        return True
    
    def _boxes_overlap(self, pos1: List[float], pos2: List[float], 
                      dims1: np.ndarray, dims2: np.ndarray) -> bool:
        """Detecta si dues caixes es superposen"""
        # Afegir marge de col·lisió
        margin = self.collision_tolerance
        
        # Calcular límits de cada caixa
        half_dims1 = dims1 / 2 + margin
        half_dims2 = dims2 / 2 + margin
        
        # Verificar solapament en cada eix
        for i in range(3):
            if abs(pos1[i] - pos2[i]) >= (half_dims1[i] + half_dims2[i]):
                return False
        
        return True
    
    def _create_success_result(self, positions: List[List[float]], rotations: List[List[float]], 
                             mesh: trimesh.Trimesh) -> Dict[str, Any]:
        """Crea resultat d'èxit"""
        pieces_count = len(positions)
        piece_volume = mesh.volume if hasattr(mesh, 'volume') else 0
        used_volume = pieces_count * piece_volume
        efficiency = (used_volume / self.container_volume) * 100 if self.container_volume > 0 else 0
        
        return {
            'success': True,
            'positions': positions,
            'rotations': rotations,
            'pieces_count': pieces_count,
            'efficiency': efficiency,
            'method': 'robust_3d_packer',
            'mesh_for_visualization': mesh
        }
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """Crea resultat d'error"""
        return {
            'success': False,
            'error': error_message,
            'positions': [],
            'rotations': [],
            'pieces_count': 0,
            'efficiency': 0.0,
            'method': 'robust_3d_packer'
        }
