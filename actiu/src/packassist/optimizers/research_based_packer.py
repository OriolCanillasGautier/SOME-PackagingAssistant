#!/usr/bin/env python3
"""
Research-Based 3D Bin Packing Optimizer
Implementació basada en papers de recerca per objectes sòlids i rígids
"""

import numpy as np
import trimesh
from typing import List, Tuple, Dict, Optional, Any
import time
import random
from dataclasses import dataclass
from enum import Enum

class PackingStrategy(Enum):
    """Estratègies de packing basades en recerca"""
    BOTTOM_LEFT_FILL = "bottom_left_fill"
    BEST_FIT_DECREASING = "best_fit_decreasing"
    FIRST_FIT_DECREASING = "first_fit_decreasing"
    HYBRID_HEURISTIC = "hybrid_heuristic"
    GENETIC_ALGORITHM = "genetic_algorithm"

@dataclass
class SolidObject:
    """Representa un objecte sòlid rígid per al packing"""
    id: int
    dimensions: Tuple[float, float, float]  # L, W, H
    volume: float
    mesh: trimesh.Trimesh
    position: Optional[Tuple[float, float, float]] = None
    rotation: Optional[Tuple[float, float, float]] = None
    is_placed: bool = False

@dataclass
class Container:
    """Contenidor rígid per al packing"""
    dimensions: Tuple[float, float, float]  # L, W, H
    volume: float
    used_volume: float = 0.0
    occupancy_grid: Optional[np.ndarray] = None

class CollisionDetector:
    """Detector de col·lisions per objectes sòlids"""
    
    @staticmethod
    def check_collision_3d(obj1_pos: Tuple[float, float, float], 
                          obj1_dims: Tuple[float, float, float],
                          obj2_pos: Tuple[float, float, float], 
                          obj2_dims: Tuple[float, float, float],
                          margin: float = 0.0) -> bool:
        """
        Detecta col·lisions entre dues caixes rígides amb marge de seguretat
        """
        x1_min, y1_min, z1_min = obj1_pos
        x1_max = x1_min + obj1_dims[0]
        y1_max = y1_min + obj1_dims[1] 
        z1_max = z1_min + obj1_dims[2]
        
        x2_min, y2_min, z2_min = obj2_pos
        x2_max = x2_min + obj2_dims[0]
        y2_max = y2_min + obj2_dims[1]
        z2_max = z2_min + obj2_dims[2]
        
        # Aplicar marge
        return not (x1_max + margin <= x2_min or x2_max + margin <= x1_min or
                   y1_max + margin <= y2_min or y2_max + margin <= y1_min or
                   z1_max + margin <= z2_min or z2_max + margin <= z1_min)
    
    @staticmethod
    def check_container_bounds(obj_pos: Tuple[float, float, float],
                             obj_dims: Tuple[float, float, float],
                             container_dims: Tuple[float, float, float]) -> bool:
        """Verifica que l'objecte estigui dins del contenidor"""
        x, y, z = obj_pos
        obj_l, obj_w, obj_h = obj_dims
        cont_l, cont_w, cont_h = container_dims
        
        return (x >= 0 and y >= 0 and z >= 0 and
                x + obj_l <= cont_l and 
                y + obj_w <= cont_w and 
                z + obj_h <= cont_h)

class BottomLeftFill:
    """Algoritme Bottom-Left Fill optimitzat per objectes sòlids"""
    
    def __init__(self, container: Container, margin: float = 2.0):
        self.container = container
        self.margin = margin
        self.placed_objects: List[SolidObject] = []
        
    def find_bottom_left_position(self, obj: SolidObject) -> Optional[Tuple[float, float, float]]:
        """
        Troba la posició més baixa i a l'esquerra possible per l'objecte
        Implementació basada en recerca per objectes rígids
        """
        obj_l, obj_w, obj_h = obj.dimensions
        cont_l, cont_w, cont_h = self.container.dimensions
        
        # Genera candidats de posició des de baix-esquerra
        candidates = []
        
        # Posició inicial (0,0,0)
        candidates.append((0.0, 0.0, 0.0))
        
        # Posicions basades en objectes ja col·locats
        for placed in self.placed_objects:
            if not placed.is_placed:
                continue
                
            px, py, pz = placed.position
            pl, pw, ph = placed.dimensions
            
            # Candidats adjacents a objectes existents
            candidates.extend([
                (px + pl + self.margin, py, pz),  # A la dreta
                (px, py + pw + self.margin, pz),  # Darrere
                (px, py, pz + ph + self.margin),  # A sobre
                (px + pl + self.margin, py + pw + self.margin, pz),  # Diagonal
                (px, py, 0.0),  # Mateix X,Y però a terra
            ])
        
        # Ordenar candidats per prioritat (Z, Y, X)
        candidates.sort(key=lambda pos: (pos[2], pos[1], pos[0]))
        
        # Provar cada candidat
        for candidate in candidates:
            if self._is_valid_position(obj, candidate):
                return candidate
                
        return None
    
    def _is_valid_position(self, obj: SolidObject, position: Tuple[float, float, float]) -> bool:
        """Verifica si una posició és vàlida per l'objecte"""
        # Verificar límits del contenidor
        if not CollisionDetector.check_container_bounds(position, obj.dimensions, self.container.dimensions):
            return False
        
        # Verificar col·lisions amb objectes existents
        for placed in self.placed_objects:
            if placed.is_placed and CollisionDetector.check_collision_3d(
                position, obj.dimensions, placed.position, placed.dimensions, self.margin):
                return False
        
        return True
    
    def place_object(self, obj: SolidObject) -> bool:
        """Col·loca un objecte utilitzant Bottom-Left Fill"""
        position = self.find_bottom_left_position(obj)
        if position:
            obj.position = position
            obj.is_placed = True
            self.placed_objects.append(obj)
            self.container.used_volume += obj.volume
            return True
        return False

class ResearchBasedPacker:
    """Packer principal basat en recerca per objectes sòlids"""
    
    def __init__(self, container_dimensions: Tuple[float, float, float], margin: float = 2.0):
        self.container = Container(container_dimensions, 
                                 container_dimensions[0] * container_dimensions[1] * container_dimensions[2])
        self.margin = margin
        self.packing_strategies = {
            PackingStrategy.BOTTOM_LEFT_FILL: self._pack_with_blf,
            PackingStrategy.BEST_FIT_DECREASING: self._pack_with_bfd,
            PackingStrategy.FIRST_FIT_DECREASING: self._pack_with_ffd,
            PackingStrategy.HYBRID_HEURISTIC: self._pack_with_hybrid
        }
    
    def pack_objects(self, mesh: trimesh.Trimesh, num_objects: int, 
                    strategy: PackingStrategy = PackingStrategy.HYBRID_HEURISTIC) -> Dict[str, Any]:
        """
        Empaqueta objectes sòlids utilitzant l'estratègia especificada
        """
        start_time = time.time()
        
        # Crear objectes sòlids
        objects = self._create_solid_objects(mesh, num_objects)
        
        # Aplicar estratègia de packing
        packer_func = self.packing_strategies.get(strategy, self._pack_with_hybrid)
        placed_objects = packer_func(objects)
        
        # Calcular resultats
        execution_time = time.time() - start_time
        efficiency = (self.container.used_volume / self.container.volume) * 100
        
        return {
            'success': True,
            'placed_objects': placed_objects,
            'positions': [obj.position for obj in placed_objects if obj.is_placed],
            'rotations': [obj.rotation or (0, 0, 0) for obj in placed_objects if obj.is_placed],
            'pieces_count': len([obj for obj in placed_objects if obj.is_placed]),
            'efficiency': efficiency,
            'execution_time': execution_time,
            'algorithm_used': f'Research-Based {strategy.value}',
            'container_dimensions': list(self.container.dimensions),
            'used_volume': self.container.used_volume,
            'total_volume': self.container.volume
        }
    
    def _create_solid_objects(self, mesh: trimesh.Trimesh, num_objects: int) -> List[SolidObject]:
        """Crea objectes sòlids a partir de la malla STL"""
        bounds = mesh.bounds
        dimensions = tuple(bounds[1] - bounds[0])
        volume = float(mesh.volume) if hasattr(mesh, 'volume') else np.prod(dimensions)
        
        objects = []
        for i in range(num_objects):
            obj = SolidObject(
                id=i,
                dimensions=dimensions,
                volume=volume,
                mesh=mesh.copy(),
                rotation=(0, 0, 0)  # Objectes rígids sense rotació inicial
            )
            objects.append(obj)
        
        return objects
    
    def _update_mesh_info(self, mesh: trimesh.Trimesh) -> Dict[str, Any]:
        """Actualitza la informació del mesh per a compatibilitat"""
        bounds = mesh.bounds
        dimensions = bounds[1] - bounds[0]
        volume = mesh.volume if hasattr(mesh, 'volume') and mesh.volume > 0 else np.prod(dimensions)
        
        return {
            'dimensions': dimensions,
            'volume': volume,
            'bounds': bounds
        }
    
    def _pack_with_blf(self, objects: List[SolidObject]) -> List[SolidObject]:
        """Packing amb Bottom-Left Fill"""
        blf = BottomLeftFill(self.container, self.margin)
        
        # Ordenar per volum descendent (millor per BLF)
        objects.sort(key=lambda x: x.volume, reverse=True)
        
        for obj in objects:
            blf.place_object(obj)
        
        return objects
    
    def _pack_with_bfd(self, objects: List[SolidObject]) -> List[SolidObject]:
        """Best Fit Decreasing per objectes sòlids"""
        # Ordenar per volum descendent
        objects.sort(key=lambda x: x.volume, reverse=True)
        
        placed = []
        for obj in objects:
            best_position = self._find_best_fit_position(obj, placed)
            if best_position:
                obj.position = best_position
                obj.is_placed = True
                placed.append(obj)
                self.container.used_volume += obj.volume
        
        return objects
    
    def _pack_with_ffd(self, objects: List[SolidObject]) -> List[SolidObject]:
        """First Fit Decreasing per objectes sòlids"""
        # Similar a BFD però para en el primer encaix vàlid
        objects.sort(key=lambda x: x.volume, reverse=True)
        
        placed = []
        for obj in objects:
            first_position = self._find_first_fit_position(obj, placed)
            if first_position:
                obj.position = first_position
                obj.is_placed = True
                placed.append(obj)
                self.container.used_volume += obj.volume
        
        return objects
    
    def _pack_with_hybrid(self, objects: List[SolidObject]) -> List[SolidObject]:
        """Algoritme híbrid que combina diverses estratègies"""
        # Prova BLF primer, després BFD per objectes restants
        blf_result = self._pack_with_blf(objects.copy())
        blf_count = len([obj for obj in blf_result if obj.is_placed])
        
        # Reset container per provar BFD
        self.container.used_volume = 0.0
        for obj in objects:
            obj.is_placed = False
            obj.position = None
        
        bfd_result = self._pack_with_bfd(objects.copy())
        bfd_count = len([obj for obj in bfd_result if obj.is_placed])
        
        # Retornar el millor resultat
        return blf_result if blf_count >= bfd_count else bfd_result
    
    def _find_best_fit_position(self, obj: SolidObject, placed: List[SolidObject]) -> Optional[Tuple[float, float, float]]:
        """Troba la millor posició per Best Fit"""
        # Implementació simplificada - es pot millorar amb heurístiques més avançades
        return self._find_first_fit_position(obj, placed)
    
    def _find_first_fit_position(self, obj: SolidObject, placed: List[SolidObject]) -> Optional[Tuple[float, float, float]]:
        """Troba la primera posició vàlida"""
        obj_l, obj_w, obj_h = obj.dimensions
        cont_l, cont_w, cont_h = self.container.dimensions
        
        # Pas de cerca (resolució)
        step = 1.0  # mm
        
        # Cerca des de baix-esquerra
        for z in np.arange(0, cont_h - obj_h + step, step):
            for y in np.arange(0, cont_w - obj_w + step, step):
                for x in np.arange(0, cont_l - obj_l + step, step):
                    position = (float(x), float(y), float(z))
                    
                    if self._is_position_valid(obj, position, placed):
                        return position
        
        return None
    
    def _is_position_valid(self, obj: SolidObject, position: Tuple[float, float, float], 
                          placed: List[SolidObject]) -> bool:
        """Verifica validesa de posició"""
        # Verificar límits del contenidor
        if not CollisionDetector.check_container_bounds(position, obj.dimensions, self.container.dimensions):
            return False
        
        # Verificar col·lisions
        for placed_obj in placed:
            if placed_obj.is_placed and CollisionDetector.check_collision_3d(
                position, obj.dimensions, placed_obj.position, placed_obj.dimensions, self.margin):
                return False
        
        return True

# Funció principal d'interface
def pack_with_research_algorithms(mesh: trimesh.Trimesh, 
                                container_dimensions: Tuple[float, float, float],
                                target_pieces: int,
                                margin: float = 2.0,
                                strategy: str = "hybrid") -> Dict[str, Any]:
    """
    Interface principal per utilitzar algoritmes de recerca
    """
    try:
        # Mapear estratègia
        strategy_map = {
            "bottom_left": PackingStrategy.BOTTOM_LEFT_FILL,
            "best_fit": PackingStrategy.BEST_FIT_DECREASING, 
            "first_fit": PackingStrategy.FIRST_FIT_DECREASING,
            "hybrid": PackingStrategy.HYBRID_HEURISTIC
        }
        
        packing_strategy = strategy_map.get(strategy, PackingStrategy.HYBRID_HEURISTIC)
        
        # Crear packer
        packer = ResearchBasedPacker(container_dimensions, margin)
        
        # Executar packing
        result = packer.pack_objects(mesh, target_pieces, packing_strategy)
        
        print(f"🔬 Research-Based Packer completat:")
        print(f"   Estratègia: {strategy}")
        print(f"   Peces col·locades: {result['pieces_count']}/{target_pieces}")
        print(f"   Eficiència: {result['efficiency']:.1f}%")
        print(f"   Temps: {result['execution_time']:.3f}s")
        
        return result
        
    except Exception as e:
        print(f"❌ Error en Research-Based Packer: {e}")
        return {
            'success': False,
            'error': str(e),
            'pieces_count': 0,
            'efficiency': 0.0,
            'positions': [],
            'rotations': []
        }