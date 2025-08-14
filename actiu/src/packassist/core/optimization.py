"""
Algoritmes d'optimització de packaging millorats
Aquest mòdul substitueix la lògica antiga amb algoritmes més eficients i nets
"""

import numpy as np
import trimesh
from typing import List, Tuple, Dict, Any, Optional
import time
from concurrent.futures import ThreadPoolExecutor
import math

class BoundingBox:
    """Classe per representar una bounding box"""
    def __init__(self, min_point: np.ndarray, max_point: np.ndarray):
        self.min = min_point
        self.max = max_point
        self.dimensions = max_point - min_point
        self.volume = np.prod(self.dimensions)
        self.center = (min_point + max_point) / 2

class PackingOptimizer:
    """Optimitzador de packaging millorat amb algoritmes eficients"""
    
    def __init__(self, container_dims: Tuple[float, float, float]):
        self.container_length, self.container_width, self.container_height = container_dims
        self.container_volume = self.container_length * self.container_width * self.container_height
        
        # Grids per col·lisió ràpida
        self.grid_resolution = 5.0  # mm per cel·la
        self.occupied_grid = set()
        
        # Resultats
        self.placed_pieces = []
        self.positions = []
        self.rotations = []
    
    def optimize(self, mesh: trimesh.Trimesh, target_pieces: int, 
                method: str = "intelligent") -> Dict[str, Any]:
        """
        Optimitza el packaging amb el mètode especificat
        
        Args:
            mesh: Malla de l'objecte a empaquetar
            target_pieces: Nombre de peces a intentar col·locar
            method: "intelligent", "grid", "random"
        
        Returns:
            Diccionari amb els resultats
        """
        start_time = time.time()
        
        # Obtenir bounding box de l'objecte
        obj_bbox = self._get_mesh_bbox(mesh)
        
        # Verificar que l'objecte cap al contenidor
        if not self._fits_in_container(obj_bbox):
            return self._create_error_result("L'objecte és massa gran per al contenidor")
        
        # Netejar estat anterior
        self._reset_state()
        
        # Executar l'algoritme seleccionat
        if method == "intelligent":
            success_count = self._intelligent_packing(mesh, obj_bbox, target_pieces)
        elif method == "grid":
            success_count = self._grid_based_packing(mesh, obj_bbox, target_pieces)
        elif method == "random":
            success_count = self._random_packing(mesh, obj_bbox, target_pieces)
        else:
            return self._create_error_result(f"Mètode desconegut: {method}")
        
        execution_time = time.time() - start_time
        
        # Calcular eficiència
        used_volume = success_count * obj_bbox.volume
        efficiency = (used_volume / self.container_volume) * 100
        
        return self._create_success_result(
            success_count, efficiency, execution_time, method, obj_bbox
        )
    
    def _intelligent_packing(self, mesh: trimesh.Trimesh, obj_bbox: BoundingBox, 
                           target_pieces: int) -> int:
        """Algoritme intel·ligent basat en optimització espacial"""
        placed_count = 0
        
        # Estratègia: omplir per capes des de baix
        current_z = 0
        layer_height = obj_bbox.dimensions[2]
        
        while current_z + layer_height <= self.container_height and placed_count < target_pieces:
            layer_pieces = self._fill_layer(obj_bbox, current_z, target_pieces - placed_count)
            placed_count += layer_pieces
            
            if layer_pieces == 0:
                break  # No es poden col·locar més peces
            
            current_z += layer_height
        
        return placed_count
    
    def _fill_layer(self, obj_bbox: BoundingBox, z_level: float, remaining_pieces: int) -> int:
        """Omple una capa horitzontal"""
        layer_count = 0
        
        # Calcular quantes peces caben en X i Y
        pieces_x = int(self.container_length // obj_bbox.dimensions[0])
        pieces_y = int(self.container_width // obj_bbox.dimensions[1])
        
        for i in range(pieces_x):
            for j in range(pieces_y):
                if layer_count >= remaining_pieces:
                    break
                
                x = i * obj_bbox.dimensions[0] + obj_bbox.dimensions[0] / 2
                y = j * obj_bbox.dimensions[1] + obj_bbox.dimensions[1] / 2
                z = z_level + obj_bbox.dimensions[2] / 2
                
                position = [x, y, z]
                rotation = [0, 0, 0]  # Sense rotació per ara
                
                if self._is_position_valid(position, obj_bbox):
                    self.positions.append(position)
                    self.rotations.append(rotation)
                    self._mark_space_occupied(position, obj_bbox)
                    layer_count += 1
            
            if layer_count >= remaining_pieces:
                break
        
        return layer_count
    
    def _grid_based_packing(self, mesh: trimesh.Trimesh, obj_bbox: BoundingBox,
                          target_pieces: int) -> int:
        """Algoritme basat en graella regular"""
        placed_count = 0
        
        # Crear graella regular
        step_x = obj_bbox.dimensions[0]
        step_y = obj_bbox.dimensions[1] 
        step_z = obj_bbox.dimensions[2]
        
        for z in np.arange(step_z/2, self.container_height - step_z/2, step_z):
            for y in np.arange(step_y/2, self.container_width - step_y/2, step_y):
                for x in np.arange(step_x/2, self.container_length - step_x/2, step_x):
                    if placed_count >= target_pieces:
                        return placed_count
                    
                    position = [x, y, z]
                    rotation = [0, 0, 0]
                    
                    if self._is_position_valid(position, obj_bbox):
                        self.positions.append(position)
                        self.rotations.append(rotation)
                        placed_count += 1
        
        return placed_count
    
    def _random_packing(self, mesh: trimesh.Trimesh, obj_bbox: BoundingBox,
                       target_pieces: int) -> int:
        """Algoritme de col·locació aleatòria amb verificació"""
        placed_count = 0
        max_attempts = target_pieces * 10  # Límit d'intents
        
        for attempt in range(max_attempts):
            if placed_count >= target_pieces:
                break
            
            # Generar posició aleatòria
            x = np.random.uniform(obj_bbox.dimensions[0]/2, 
                                self.container_length - obj_bbox.dimensions[0]/2)
            y = np.random.uniform(obj_bbox.dimensions[1]/2, 
                                self.container_width - obj_bbox.dimensions[1]/2)
            z = np.random.uniform(obj_bbox.dimensions[2]/2, 
                                self.container_height - obj_bbox.dimensions[2]/2)
            
            position = [x, y, z]
            rotation = [0, 0, 0]
            
            if self._is_position_valid(position, obj_bbox):
                self.positions.append(position)
                self.rotations.append(rotation)
                self._mark_space_occupied(position, obj_bbox)
                placed_count += 1
        
        return placed_count
    
    def _get_mesh_bbox(self, mesh: trimesh.Trimesh) -> BoundingBox:
        """Calcula la bounding box d'una malla"""
        bounds = mesh.bounds
        return BoundingBox(bounds[0], bounds[1])
    
    def _fits_in_container(self, obj_bbox: BoundingBox) -> bool:
        """Verifica si l'objecte cap al contenidor"""
        return (obj_bbox.dimensions[0] <= self.container_length and
                obj_bbox.dimensions[1] <= self.container_width and
                obj_bbox.dimensions[2] <= self.container_height)
    
    def _is_position_valid(self, position: List[float], obj_bbox: BoundingBox) -> bool:
        """Verifica si una posició és vàlida (dins del contenidor i sense col·lisions)"""
        x, y, z = position
        
        # Verificar límits del contenidor
        if (x - obj_bbox.dimensions[0]/2 < 0 or x + obj_bbox.dimensions[0]/2 > self.container_length or
            y - obj_bbox.dimensions[1]/2 < 0 or y + obj_bbox.dimensions[1]/2 > self.container_width or
            z - obj_bbox.dimensions[2]/2 < 0 or z + obj_bbox.dimensions[2]/2 > self.container_height):
            return False
        
        # Verificar col·lisions amb peces existents (simplificat)
        for existing_pos in self.positions:
            if self._boxes_overlap(position, existing_pos, obj_bbox):
                return False
        
        return True
    
    def _boxes_overlap(self, pos1: List[float], pos2: List[float], 
                      bbox: BoundingBox, margin: float = 1.0) -> bool:
        """Verifica si dues bounding boxes se superposen"""
        for i in range(3):
            distance = abs(pos1[i] - pos2[i])
            min_distance = bbox.dimensions[i] + margin
            
            if distance < min_distance:
                continue
            else:
                return False  # No es superposen en aquesta dimensió
        
        return True  # Es superposen en totes les dimensions
    
    def _mark_space_occupied(self, position: List[float], obj_bbox: BoundingBox):
        """Marca l'espai com ocupat en la graella"""
        # Implementació simplificada - podria expandir-se per millor precisió
        grid_x = int(position[0] // self.grid_resolution)
        grid_y = int(position[1] // self.grid_resolution)
        grid_z = int(position[2] // self.grid_resolution)
        
        self.occupied_grid.add((grid_x, grid_y, grid_z))
    
    def _reset_state(self):
        """Reinicia l'estat de l'optimitzador"""
        self.positions = []
        self.rotations = []
        self.placed_pieces = []
        self.occupied_grid = set()
    
    def _create_success_result(self, count: int, efficiency: float, 
                             time_taken: float, method: str, obj_bbox: BoundingBox) -> Dict[str, Any]:
        """Crea el diccionari de resultats d'èxit"""
        return {
            'success': True,
            'positions': self.positions.copy(),
            'rotations': self.rotations.copy(),
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
                'length': obj_bbox.dimensions[0],
                'width': obj_bbox.dimensions[1],
                'height': obj_bbox.dimensions[2],
                'volume': obj_bbox.volume
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
