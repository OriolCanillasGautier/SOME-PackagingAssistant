"""
Optimitzador bàsic per a PackAssist
Manteniment de compatibilitat amb l'aplicació existent
"""

import numpy as np
import trimesh
from typing import List, Tuple, Dict, Any
import time

class PackingOptimizer:
    """Optimitzador d'empaquetament bàsic per mantenir compatibilitat"""
    
    def __init__(self, container_dims: Tuple[float, float, float]):
        self.container_length, self.container_width, self.container_height = container_dims
        self.container_volume = self.container_length * self.container_width * self.container_height
        self.floor_separation = 0.0
        self.margin = 2.0
        
    def set_floor_separation(self, separation: float):
        """Estableix la separació entre pisos"""
        self.floor_separation = separation
        
    def set_margin(self, margin: float):
        """Estableix el marge"""
        self.margin = margin
    
    def optimize(self, mesh: trimesh.Trimesh, target_pieces: int,
                method: str = "intelligent") -> Dict[str, Any]:
        """
        Optimitza l'empaquetament
        
        Args:
            mesh: Malla de l'objecte
            target_pieces: Nombre de peces a col·locar
            method: Mètode d'optimització
            
        Returns:
            Diccionari amb resultats
        """
        start_time = time.time()
        
        # Obtenir dimensions reals de l'objecte
        bounds = mesh.bounds
        obj_dims_real = bounds[1] - bounds[0]
        
        # Dimensions amb marge només per a la verificació de col·locació
        obj_dims_with_margin = obj_dims_real + (2 * self.margin)
        
        # Verificar que cap al contenidor (amb marge)
        if not self._fits_in_container(obj_dims_with_margin):
            return self._create_error_result("L'objecte és massa gran per al contenidor")
        
        # Netejar llista de posicions
        positions = []
        rotations = []
        
        # Empaquetament estratificat bàsic
        placed_count = self._intelligent_packing(obj_dims_real, target_pieces, positions, rotations)
        
        execution_time = time.time() - start_time
        
        # Calcular eficiència
        obj_volume = np.prod(obj_dims_real)
        used_volume = placed_count * obj_volume
        efficiency = (used_volume / self.container_volume) * 100 if self.container_volume > 0 else 0
        
        return self._create_success_result(
            placed_count, efficiency, execution_time, method,
            obj_dims_real.tolist(), obj_volume,
            positions, rotations
        )
    
    def _intelligent_packing(self, obj_dims_real: np.ndarray, target_pieces: int,
                           positions: List[List[float]], rotations: List[List[float]]) -> int:
        """Empaquetament intel·ligent estratificat"""
        placed_count = 0
        
        # Estratègia: omplir per capes des de baix
        layer_height = obj_dims_real[2]
        current_z = layer_height / 2  # Posició Z del centre de la primera capa
        floor_number = 1
        
        print(f" Empaquetament intel·ligent amb separació de pisos: {self.floor_separation}mm")
        
        while current_z + layer_height/2 <= self.container_height and placed_count < target_pieces:
            print(f" Pis {floor_number}: Z={current_z - layer_height/2:.1f} - {current_z + layer_height/2:.1f}mm")
            layer_pieces = self._fill_layer(obj_dims_real, current_z, target_pieces - placed_count, positions, rotations)
            placed_count += layer_pieces
            
            if layer_pieces == 0:
                print(f"✅ Pis {floor_number}: {layer_pieces} peces col·locades")
                break  # No es poden col·locar més peces
            
            print(f"✅ Pis {floor_number}: {layer_pieces} peces col·locades")
            floor_number += 1
            
            # Calcular la posició Z per la propera capa
            current_z += layer_height + self.floor_separation
        
        print(f"⚠️ No es poden col·locar més peces, aturant...")
        print(f" Total col·locat: {placed_count} peces en {floor_number-1} pisos")
        return placed_count
    
    def _fill_layer(self, obj_dims_real: np.ndarray, z_level: float, remaining_pieces: int,
                   all_positions: List[List[float]], all_rotations: List[List[float]]) -> int:
        """Omple una capa horitzontal"""
        layer_count = 0
        current_positions = all_positions[:]  # Còpia de les posicions existents
        
        # Calcular quantes peces caben en X i Y amb dimensions reals
        pieces_x = max(1, int(self.container_length // obj_dims_real[0]))
        pieces_y = max(1, int(self.container_width // obj_dims_real[1]))
        
        print(f"   Dimensions de la capa: {pieces_x} × {pieces_y} (màx. {pieces_x * pieces_y} peces)")
        print(f"   Objecte: {obj_dims_real[0]:.1f} × {obj_dims_real[1]:.1f} × {obj_dims_real[2]:.1f}")
        print(f"   Contenidor: {self.container_length} × {self.container_width} × {self.container_height}")
        
        for i in range(pieces_x):
            for j in range(pieces_y):
                if layer_count >= remaining_pieces:
                    break
                
                # Calcular posició correcta per al centre de l'objecte
                x = i * obj_dims_real[0] + obj_dims_real[0] / 2
                y = j * obj_dims_real[1] + obj_dims_real[1] / 2
                z = z_level
                
                position = [x, y, z]
                rotation = [0, 0, 0]  # Sense rotació per ara
                
                # Verificar que la posició sigui vàlida
                print(f"     Provant posició ({x:.1f}, {y:.1f}, {z:.1f})")
                
                if self._is_position_valid_with_existing(position, obj_dims_real, current_positions):
                    all_positions.append(position)
                    all_rotations.append(rotation)
                    current_positions.append(position)  # Actualitzar còpia local
                    layer_count += 1
                    print(f"    ✅ Peça {layer_count} col·locada a ({x:.1f}, {y:.1f}, {z:.1f})")
                else:
                    print(f"    ❌ Posició ({x:.1f}, {y:.1f}, {z:.1f}) NO vàlida")
            
            if layer_count >= remaining_pieces:
                break
        
        return layer_count
    
    def _fits_in_container(self, obj_dims: np.ndarray) -> bool:
        """Verifica si l'objecte cap al contenidor"""
        return (obj_dims[0] <= self.container_length and
                obj_dims[1] <= self.container_width and
                obj_dims[2] <= self.container_height)
    
    def _is_position_valid_strict(self, position: List[float], obj_dims: np.ndarray) -> bool:
        """Verifica si una posició és vàlida amb verificació estricta de límits"""
        x, y, z = position
        
        # Verificació estricta: la peça ha d'estar completament dins del contenidor
        # Afegir una mica de tolerància per evitar errors de coma flotant
        tolerance = 0.001
        half_x = obj_dims[0] / 2
        half_y = obj_dims[1] / 2
        half_z = obj_dims[2] / 2
        
        # Verificar límits del contenidor
        if (x - half_x < -tolerance or 
            x + half_x > self.container_length + tolerance or
            y - half_y < -tolerance or 
            y + half_y > self.container_width + tolerance or
            z - half_z < -tolerance or 
            z + half_z > self.container_height + tolerance):
            return False
        
        # No verificar col·lisions amb peces existents en aquest nivell bàsic
        # Això es fa al nivell superior
        return True
    
    def _is_position_valid_with_existing(self, position: List[float], obj_dims_real: np.ndarray, 
                                       existing_positions: List[List[float]]) -> bool:
        """Verifica si una posició és vàlida amb les posicions existents"""
        x, y, z = position
        
        # Verificació estricta: la peça ha d'estar completament dins del contenidor
        # Afegir una mica de tolerància per evitar errors de coma flotant
        tolerance = 0.001
        half_x = obj_dims_real[0] / 2
        half_y = obj_dims_real[1] / 2
        half_z = obj_dims_real[2] / 2
        
        # Verificar límits del contenidor
        if (x - half_x < -tolerance or 
            x + half_x > self.container_length + tolerance or
            y - half_y < -tolerance or 
            y + half_y > self.container_width + tolerance or
            z - half_z < -tolerance or 
            z + half_z > self.container_height + tolerance):
            return False
        
        # Verificar col·lisions amb peces existents amb marge de separació
        separation_margin = max(0.5, self.floor_separation / 4)  # Marge mínim
        for existing_pos in existing_positions:
            if self._boxes_overlap(position, existing_pos, obj_dims_real, separation_margin):
                return False
        
        return True
    
    def _boxes_overlap(self, pos1: List[float], pos2: List[float], 
                      obj_dims_real: np.ndarray, margin: float = 1.0) -> bool:
        """Verifica si dues bounding boxes se superposen"""
        # Calcular distància mínima amb marge
        min_distances = obj_dims_real + margin
        
        for i in range(3):
            distance = abs(pos1[i] - pos2[i])
            if distance < min_distances[i]:
                continue  # Solapen en aquesta dimensió
            else:
                return False  # No solapen en aquesta dimensió
        
        return True  # Solapen en totes les dimensions
    
    def _create_success_result(self, count: int, efficiency: float, 
                             time_taken: float, method: str,
                             obj_dims: List[float], obj_volume: float,
                             positions: List[List[float]], 
                             rotations: List[List[float]]) -> Dict[str, Any]:
        """Crea el diccionari de resultats d'èxit"""
        # Recalcular l'eficiència amb les dimensions reals de la bounding box
        real_obj_volume = np.prod(obj_dims)
        used_volume = count * real_obj_volume
        real_efficiency = (used_volume / self.container_volume) * 100 if self.container_volume > 0 else 0
        
        return {
            'success': True,
            'positions': positions.copy(),
            'rotations': rotations.copy(),
            'pieces_count': count,
            'efficiency': real_efficiency,
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