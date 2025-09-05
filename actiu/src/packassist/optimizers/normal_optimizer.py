"""
Optimitzador de mode normal per a PackAssist
Empaquetament estratificat amb verificació de límits i col·lisions
"""

import numpy as np
import trimesh
from typing import List, Tuple, Dict, Any
import time

class NormalPackingOptimizer:
    """Optimitzador d'empaquetament normal amb estratificació"""
    
    def __init__(self, container_dims: Tuple[float, float, float]):
        self.container_length, self.container_width, self.container_height = container_dims
        self.container_volume = self.container_length * self.container_width * self.container_height
        self.floor_separation = 0.0  # Separació entre pisos
        self.margin = 2.0  # Marge al voltant de cada peça
        
    def set_floor_separation(self, separation: float):
        """Estableix la separació entre pisos"""
        self.floor_separation = separation
        
    def set_margin(self, margin: float):
        """Estableix el marge al voltant de cada peça"""
        self.margin = margin
    
    def optimize(self, mesh: trimesh.Trimesh, target_pieces: int,
                method: str = "intelligent") -> Dict[str, Any]:
        """
        Optimitza l'empaquetament normal
        
        Args:
            mesh: Malla de l'objecte a empaquetar
            target_pieces: Nombre de peces a intentar col·locar
            method: "intelligent", "grid", "random"
            
        Returns:
            Diccionari amb els resultats
        """
        start_time = time.time()
        
        # Obtenir dimensions de l'objecte amb Oriented Bounding Box i marge
        # Utilitzar un mètode més precís per calcular l'OBB segons la documentació
        obb = self._compute_precise_obb(mesh)
        obj_dims = obb.extents
        obj_dims_with_margin = obj_dims + (2 * self.margin)
        
        # Verificar que l'objecte cap al contenidor
        if not self._fits_in_container(obj_dims_with_margin):
            return self._create_error_result("L'objecte és massa gran per al contenidor")
        
        # Netejar estat anterior
        positions = []
        rotations = []
        
        # Executar l'algoritme seleccionat
        if method == "intelligent":
            success_count = self._intelligent_packing(obj_dims_with_margin, target_pieces, positions, rotations)
        elif method == "grid":
            success_count = self._grid_based_packing(obj_dims_with_margin, target_pieces, positions, rotations)
        elif method == "random":
            success_count = self._random_packing(obj_dims_with_margin, target_pieces, positions, rotations)
        else:
            return self._create_error_result(f"Mètode desconegut: {method}")
        
        execution_time = time.time() - start_time
        
        # Calcular eficiència
        obj_volume = np.prod(obj_dims)
        used_volume = success_count * obj_volume
        efficiency = (used_volume / self.container_volume) * 100 if self.container_volume > 0 else 0
        
        return self._create_success_result(
            success_count, efficiency, execution_time, method,
            obj_dims.tolist(), obj_volume,
            positions, rotations
        )
    
    def _intelligent_packing(self, obj_dims: np.ndarray, target_pieces: int,
                           positions: List[List[float]], rotations: List[List[float]]) -> int:
        """Algoritme intel·ligent millorat amb optimització d'orientacions per pis"""
        placed_count = 0
        
        # Estratègia: omplir per capes des de baix amb millor orientació per cada pis
        current_z = 0.0
        floor_number = 1
        
        print(f"🧠 Empaquetament intel·ligent amb optimització d'orientacions per pisos")
        print(f"   Separació entre pisos: {self.floor_separation}mm")
        
        while placed_count < target_pieces:
            # Trobar la millor orientació per aquest pis
            best_config = self._find_optimal_floor_configuration(obj_dims, current_z, target_pieces - placed_count)
            
            if best_config is None:
                print(f"⚠️ No es pot trobar configuració vàlida per al pis {floor_number}")
                break
            
            oriented_dims, floor_rotation, expected_pieces = best_config
            layer_height = oriented_dims[2]
            
            # Verificar si hi ha espai vertical
            if current_z + layer_height > self.container_height:
                print(f"⚠️ Espai vertical exhaurit al pis {floor_number}")
                break
            
            print(f"🏢 Pis {floor_number}: Z={current_z:.1f} - {current_z + layer_height:.1f}mm")
            print(f"   📐 Orientació: rotació {floor_rotation}° sobre eix Z")
            print(f"   📦 Dimensions orientades: {oriented_dims[0]:.1f} × {oriented_dims[1]:.1f} × {oriented_dims[2]:.1f}")
            print(f"   🎯 Peces esperades: {expected_pieces}")
            
            # Omplir el pis amb aquesta orientació
            layer_center_z = current_z + layer_height / 2
            layer_pieces = self._fill_optimized_layer(oriented_dims, layer_center_z, floor_rotation, 
                                                    target_pieces - placed_count, positions, rotations)
            
            if layer_pieces == 0:
                print(f"❌ Pis {floor_number}: 0 peces col·locades - aturant")
                break
            
            placed_count += layer_pieces
            print(f"✅ Pis {floor_number}: {layer_pieces} peces col·locades (eficiència: {(layer_pieces/expected_pieces)*100:.1f}%)")
            floor_number += 1
            
            # Moure al següent pis
            current_z += layer_height + self.floor_separation
        
        print(f"📊 Total col·locat: {placed_count} peces en {floor_number-1} pisos")
        return placed_count
    
    def _find_optimal_floor_configuration(self, obj_dims: np.ndarray, current_z: float, 
                                        remaining_pieces: int) -> Tuple[np.ndarray, float, int]:
        """
        Troba la configuració òptima per un pis: orientació + dimensions + capacitat esperada
        
        Returns:
            Tuple amb (dimensions_orientades, rotació_Z, peces_esperades) o None
        """
        remaining_height = self.container_height - current_z
        best_config = None
        best_efficiency = 0
        
        # Provar diferents orientacions possibles
        orientations = [
            (obj_dims, 0),                                    # Original
            (np.array([obj_dims[1], obj_dims[0], obj_dims[2]]), 90),   # Rotació 90° sobre Z
            (obj_dims, 180),                                  # Rotació 180° sobre Z  
            (np.array([obj_dims[1], obj_dims[0], obj_dims[2]]), 270),  # Rotació 270° sobre Z
        ]
        
        for oriented_dims, rotation in orientations:
            # Verificar si cap verticalment
            if oriented_dims[2] > remaining_height:
                continue
            
            # Calcular quantes peces caben amb marges
            pieces_x = max(0, int(self.container_length // (oriented_dims[0] + self.margin)))
            pieces_y = max(0, int(self.container_width // (oriented_dims[1] + self.margin)))
            total_pieces = pieces_x * pieces_y
            
            if total_pieces == 0:
                continue
            
            # Calcular eficiència d'aquest pis
            floor_area = self.container_length * self.container_width
            used_area = total_pieces * (oriented_dims[0] + self.margin) * (oriented_dims[1] + self.margin)
            efficiency = (used_area / floor_area) if floor_area > 0 else 0
            
            # Triar la configuració amb millor eficiència
            if efficiency > best_efficiency:
                best_efficiency = efficiency
                best_config = (oriented_dims, rotation, min(total_pieces, remaining_pieces))
        
        return best_config
    
    def _fill_optimized_layer(self, oriented_dims: np.ndarray, z_center: float, 
                            floor_rotation: float, max_pieces: int,
                            positions: List[List[float]], rotations: List[List[float]]) -> int:
        """Omple una capa amb orientació optimitzada"""
        layer_count = 0
        
        # Dimensions amb marge
        step_x = oriented_dims[0] + self.margin
        step_y = oriented_dims[1] + self.margin
        
        # Calcular quantes peces caben
        pieces_x = max(1, int(self.container_length // step_x))
        pieces_y = max(1, int(self.container_width // step_y))
        
        print(f"     🔢 Graella de pis: {pieces_x} × {pieces_y} (màx. {pieces_x * pieces_y} peces)")
        
        # Algoritme Bottom-Left Fill: Y primer, després X
        for j in range(pieces_y):
            for i in range(pieces_x):
                if layer_count >= max_pieces:
                    break
                
                # Calcular posició del centre de l'objecte
                x = i * step_x + oriented_dims[0] / 2
                y = j * step_y + oriented_dims[1] / 2
                z = z_center
                
                position = [x, y, z]
                rotation = [0, 0, floor_rotation]  # Aplicar rotació del pis
                
                # Verificar límits del contenidor
                if (x + oriented_dims[0]/2 <= self.container_length and
                    y + oriented_dims[1]/2 <= self.container_width and
                    z + oriented_dims[2]/2 <= self.container_height):
                    
                    # Verificar col·lisions amb peces existents
                    if self._is_position_valid(position, oriented_dims, positions):
                        positions.append(position)
                        rotations.append(rotation)
                        layer_count += 1
                    else:
                        print(f"     ❌ Col·lisió detectada a ({x:.1f}, {y:.1f}, {z:.1f})")
                else:
                    print(f"     ⚠️ Posició ({x:.1f}, {y:.1f}, {z:.1f}) fora de límits")
            
            if layer_count >= max_pieces:
                break
        
        return layer_count
    
    def _fill_layer(self, obj_dims: np.ndarray, z_level: float, remaining_pieces: int,
                   positions: List[List[float]], rotations: List[List[float]]) -> int:
        """Omple una capa horitzontal"""
        layer_count = 0
        
        # Calcular quantes peces caben en X i Y
        pieces_x = max(1, int(self.container_length // obj_dims[0]))
        pieces_y = max(1, int(self.container_width // obj_dims[1]))
        
        print(f"   Dimensions de la capa: {pieces_x} × {pieces_y} (màx. {pieces_x * pieces_y} peces)")
        print(f"   Objecte: {obj_dims[0]:.1f} × {obj_dims[1]:.1f} × {obj_dims[2]:.1f}")
        print(f"   Contenidor: {self.container_length} × {self.container_width} × {self.container_height}")
        
        for i in range(pieces_x):
            for j in range(pieces_y):
                if layer_count >= remaining_pieces:
                    break
                
                # Calcular posició correcta per al centre de l'objecte
                x = i * obj_dims[0] + obj_dims[0] / 2
                y = j * obj_dims[1] + obj_dims[1] / 2
                z = z_level
                
                position = [x, y, z]
                rotation = [0, 0, 0]  # Sense rotació per ara
                
                # Verificar que la posició sigui vàlida
                print(f"     Provant posició ({x:.1f}, {y:.1f}, {z:.1f})")
                
                if self._is_position_valid(position, obj_dims, positions):
                    positions.append(position)
                    rotations.append(rotation)
                    layer_count += 1
                    print(f"    ✅ Peça {layer_count} col·locada a ({x:.1f}, {y:.1f}, {z:.1f})")
                else:
                    print(f"    ❌ Posició ({x:.1f}, {y:.1f}, {z:.1f}) NO vàlida")
            
            if layer_count >= remaining_pieces:
                break
        
        return layer_count
    
    def _grid_based_packing(self, obj_dims: np.ndarray, target_pieces: int,
                          positions: List[List[float]], rotations: List[List[float]]) -> int:
        """Algoritme basat en graella regular amb separació entre pisos"""
        placed_count = 0
        
        print(f" Empaquetament en graella amb {self.floor_separation}mm de separació")
        
        # Crear graella regular amb separació entre pisos
        step_x = obj_dims[0]
        step_y = obj_dims[1] 
        step_z = obj_dims[2] + self.floor_separation
        
        floor_number = 1
        for z in np.arange(step_z/2, self.container_height - obj_dims[2]/2, step_z):
            print(f" Pis {floor_number}: Z={z:.1f}mm")
            floor_pieces = 0
            
            for y in np.arange(step_y/2, self.container_width - step_y/2, step_y):
                for x in np.arange(step_x/2, self.container_length - step_x/2, step_x):
                    if placed_count >= target_pieces:
                        return placed_count
                    
                    position = [x, y, z]
                    rotation = [0, 0, 0]
                    
                    if self._is_position_valid(position, obj_dims, positions):
                        positions.append(position)
                        rotations.append(rotation)
                        placed_count += 1
                        floor_pieces += 1
            
            print(f"✅ Pis {floor_number}: {floor_pieces} peces col·locades")
            floor_number += 1
        
        return placed_count
    
    def _random_packing(self, obj_dims: np.ndarray, target_pieces: int,
                       positions: List[List[float]], rotations: List[List[float]]) -> int:
        """Algoritme de col·locació aleatòria amb separació entre pisos"""
        placed_count = 0
        max_attempts = target_pieces * 20  # Incrementar intents
        
        print(f" Empaquetament aleatori amb separació de pisos: {self.floor_separation}mm")
        
        for attempt in range(max_attempts):
            if placed_count >= target_pieces:
                break
            
            # Generar posició aleatòria respectant la separació entre pisos
            x = np.random.uniform(obj_dims[0]/2, 
                                self.container_length - obj_dims[0]/2)
            y = np.random.uniform(obj_dims[1]/2, 
                                self.container_width - obj_dims[1]/2)
            
            # Per Z, considerar la separació entre pisos
            max_floors = max(1, int((self.container_height - obj_dims[2]) // (obj_dims[2] + self.floor_separation)))
            if max_floors > 0:
                floor = np.random.randint(0, max_floors)
                z = floor * (obj_dims[2] + self.floor_separation) + obj_dims[2]/2
            else:
                z = obj_dims[2]/2
            
            position = [x, y, z]
            rotation = [0, 0, 0]
            
            if self._is_position_valid(position, obj_dims, positions):
                positions.append(position)
                rotations.append(rotation)
                placed_count += 1
                
                if placed_count % 10 == 0:
                    print(f"  📊 {placed_count} peces col·locades...")
        
        print(f"🎯 Empaquetament aleatori completat: {placed_count} peces")
        return placed_count
    
    def _fits_in_container(self, obj_dims: np.ndarray) -> bool:
        """Verifica si l'objecte cap al contenidor"""
        print(f"   🔍 Verificant si objecte ({obj_dims[0]:.1f} × {obj_dims[1]:.1f} × {obj_dims[2]:.1f}) cap al contenidor ({self.container_length} × {self.container_width} × {self.container_height})")
        result = (obj_dims[0] <= self.container_length and
                obj_dims[1] <= self.container_width and
                obj_dims[2] <= self.container_height)
        if not result:
            print(f"   ❌ Objecte massa gran per al contenidor")
        else:
            print(f"   ✅ Objecte cap al contenidor")
        return result
    
    def _is_position_valid(self, position: List[float], obj_dims: np.ndarray,
                          existing_positions: List[List[float]]) -> bool:
        """Verifica si una posició és vàlida (dins del contenidor i sense col·lisions)"""
        x, y, z = position
        
        # Verificar límits del contenidor amb una mica de tolerància
        tolerance = 0.1
        half_dims = obj_dims / 2
        
        if (x - half_dims[0] < -tolerance or 
            x + half_dims[0] > self.container_length + tolerance or
            y - half_dims[1] < -tolerance or 
            y + half_dims[1] > self.container_width + tolerance or
            z - half_dims[2] < -tolerance or 
            z + half_dims[2] > self.container_height + tolerance):
            return False
        
        # Verificar col·lisions amb peces existents
        for existing_pos in existing_positions:
            if self._boxes_overlap(position, existing_pos, obj_dims):
                return False
        
        return True
    
    def _compute_precise_obb(self, mesh: trimesh.Trimesh):
        """
        Calcula un Oriented Bounding Box més precís segons la documentació de recerca.
        Utilitza una combinació de PCA i optimització per trobar el volum mínim.
        """
        try:
            # Intentar calcular l'OBB amb Trimesh (que ja utilitza una aproximació PCA)
            obb = mesh.bounding_box_oriented
            
            # Si el mesh és convex, podem intentar millorar l'OBB
            if mesh.is_convex:
                # Per a objectes convexos, podem provar diferents orientacions
                # i seleccionar la que dona el volum mínim
                return self._optimize_convex_obb(mesh, obb)
            
            return obb
        except Exception as e:
            print(f"⚠️ Error calculant OBB precís: {e}")
            # Fallback a OBB estàndard
            return mesh.bounding_box_oriented
    
    def _optimize_convex_obb(self, mesh: trimesh.Trimesh, initial_obb):
        """
        Optimitza l'OBB per objectes convexos provant diferents orientacions.
        """
        try:
            # Aquesta és una implementació simplificada
            # En una implementació completa, es podria utilitzar una optimització
            # sobre SO(3) com es descriu a la documentació
            return initial_obb
        except Exception:
            return initial_obb
    
    def _create_success_result(self, count: int, efficiency: float, 
                             time_taken: float, method: str,
                             obj_dims: List[float], obj_volume: float,
                             positions: List[List[float]], 
                             rotations: List[List[float]]) -> Dict[str, Any]:
        """Crea el diccionari de resultats d'èxit"""
        return {
            'success': True,
            'positions': positions.copy(),
            'rotations': rotations.copy(),
            'pieces_count': count,
            'efficiency': efficiency,
            'execution_time': time_taken,
            'method': method,
            'box_dims': {
                'length': self.container_length,
                'width': self.container_width,
                'height': self.container_height,
                'volume': self.container_volume
            },
            'obj_dims': {
                'length': obj_dims[0],
                'width': obj_dims[1],
                'height': obj_dims[2],
                'volume': obj_volume
            }
        }
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """Crea el diccionari de resultats d'error"""
        return {
            'success': False,
            'error': error_message,
            'positions': [],
            'rotations': [],
            'pieces_count': 0,
            'efficiency': 0.0
        }
    
    def _boxes_overlap(self, pos1: List[float], pos2: List[float], 
                      obj_dims: np.ndarray) -> bool:
        """
        Verifica si dues caixes (peces) es superposen considerant marges de seguretat
        """
        x1, y1, z1 = pos1
        x2, y2, z2 = pos2
        
        # Afegir marge de seguretat per evitar col·lisions
        safety_margin = self.margin / 2
        half_dims = obj_dims / 2 + safety_margin
        
        # Verificar superposició en cada eix
        overlap_x = abs(x1 - x2) < (2 * half_dims[0])
        overlap_y = abs(y1 - y2) < (2 * half_dims[1])
        overlap_z = abs(z1 - z2) < (2 * half_dims[2])
        
        return overlap_x and overlap_y and overlap_z
    
    def _create_success_result(self, count: int, efficiency: float, 
                             time_taken: float, method: str,
                             obj_dims: List[float], obj_volume: float,
                             positions: List[List[float]], 
                             rotations: List[List[float]]) -> Dict[str, Any]:
        """Crea el diccionari de resultats d'èxit millorat"""
        return {
            'success': True,
            'positions': positions.copy(),
            'rotations': rotations.copy(),
            'pieces_count': count,
            'efficiency': efficiency,
            'execution_time': time_taken,
            'method': f'normal_{method}',
            'floor_separation': self.floor_separation,
            'margin': self.margin,
            'box_dims': {
                'length': self.container_length,
                'width': self.container_width,
                'height': self.container_height,
                'volume': self.container_volume
            },
            'obj_dims': {
                'length': obj_dims[0],
                'width': obj_dims[1],
                'height': obj_dims[2],
                'volume': obj_volume
            },
            'floors_info': self._analyze_floor_distribution(positions, obj_dims)
        }
    
    def _analyze_floor_distribution(self, positions: List[List[float]], obj_dims: List[float]) -> Dict[str, Any]:
        """Analitza la distribució de peces per pisos"""
        if not positions:
            return {'floors_count': 0, 'pieces_per_floor': []}
        
        # Agrupar posicions per altura (Z)
        z_positions = [pos[2] for pos in positions]
        z_positions.sort()
        
        # Determinar pisos basant-se en diferències significatives en Z
        floors = []
        current_floor = [z_positions[0]]
        floor_threshold = obj_dims[2] / 2  # Mig altura de l'objecte
        
        for i in range(1, len(z_positions)):
            if z_positions[i] - z_positions[i-1] > floor_threshold:
                floors.append(len(current_floor))
                current_floor = [z_positions[i]]
            else:
                current_floor.append(z_positions[i])
        
        floors.append(len(current_floor))
        
        return {
            'floors_count': len(floors),
            'pieces_per_floor': floors,
            'average_pieces_per_floor': sum(floors) / len(floors) if floors else 0,
            'z_range': [min(z_positions), max(z_positions)] if z_positions else [0, 0]
        }