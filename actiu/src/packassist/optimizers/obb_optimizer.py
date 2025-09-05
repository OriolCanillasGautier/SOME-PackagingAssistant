"""
Optimitzador basat en Oriented Bounding Boxes (OBB) per a PackAssist
Implementació precisa seguint les especificacions dels documents de recerca
"""

import numpy as np
import trimesh
from typing import List, Tuple, Dict, Any
import time

class OBBOptimizer:
    """Optimitzador d'empaquetament basat en Oriented Bounding Boxes"""
    
    def __init__(self, container_dims: Tuple[float, float, float]):
        self.container_length, self.container_width, self.container_height = container_dims
        self.container_volume = self.container_length * self.container_width * self.container_height
        self.margin = 2.0  # Marge al voltant de les peces
        self.inter_level_spacing = 2.0  # Espai entre nivells
        self.enable_rotations = True  # Permetre rotacions per optimitzar
        
    def set_margin(self, margin: float):
        """Estableix el marge al voltant de les peces"""
        self.margin = margin
        
    def set_inter_level_spacing(self, spacing: float):
        """Estableix l'espai entre nivells"""
        self.inter_level_spacing = spacing
        
    def set_rotation_mode(self, enable: bool):
        """Habilita o deshabilita rotacions per optimitzar"""
        self.enable_rotations = enable
    
    def optimize_with_obb(self, mesh: trimesh.Trimesh, target_pieces: int) -> Dict[str, Any]:
        """
        Optimitza l'empaquetament utilitzant Oriented Bounding Boxes seguint
        l'estratègia d'empaquetament organitzat amb nivells
        
        Args:
            mesh: Malla de l'objecte a empaquetar
            target_pieces: Nombre de peces a intentar col·locar
            
        Returns:
            Diccionari amb els resultats
        """
        start_time = time.time()
        
        # Calcular Oriented Bounding Box amb un mètode més precís
        print("🔍 Calculant Oriented Bounding Box...")
        canonical_mesh, obb_dims = self._compute_oriented_bounding_box(mesh)
        
        if canonical_mesh is None:
            return self._create_error_result("No s'ha pogut calcular l'OBB")
        
        print(f"🔧 Dimensions OBB: {obb_dims[0]:.2f} × {obb_dims[1]:.2f} × {obb_dims[2]:.2f}")
        
        # Verificar que l'objecte cap al contenidor
        if not self._fits_in_container(obb_dims):
            return self._create_error_result("L'objecte és massa gran per al contenidor")
        
        # Empaquetament en nivells amb algoritme Bottom-Left
        positions, rotations = self._level_based_packing(obb_dims, target_pieces)
        
        execution_time = time.time() - start_time
        placed_count = len(positions)
        
        # Calcular eficiència
        obj_volume = np.prod(obb_dims)
        used_volume = placed_count * obj_volume
        efficiency = (used_volume / self.container_volume) * 100 if self.container_volume > 0 else 0
        
        return self._create_success_result(
            placed_count, efficiency, execution_time,
            obb_dims.tolist(), obj_volume,
            positions, rotations,
            canonical_mesh
        )
    
    def _compute_oriented_bounding_box(self, mesh: trimesh.Trimesh) -> Tuple[trimesh.Trimesh, np.ndarray]:
        """
        Calcula l'OBB canònic amb orientació optimitzada per empaquetament
        Garanteix que l'OBB estigui sempre orientat paral·lel o perpendicular al terra
        per maximitzar l'eficiència d'empaquetament.
        
        Returns:
            Tuple amb (malla_canònica, dimensions_obb)
        """
        try:
            print("🔍 Calculant OBB optimitzat per empaquetament...")
            
            # Calcular l'OBB inicial estàndard
            initial_obb = mesh.bounding_box_oriented
            initial_dims = initial_obb.extents
            initial_volume = np.prod(initial_dims)
            
            print(f"   OBB inicial: {initial_dims[0]:.2f} × {initial_dims[1]:.2f} × {initial_dims[2]:.2f} (vol: {initial_volume:.2f})")
            
            # Provar TOTES les orientacions possibles alineades amb els eixos principals
            # Això garanteix que l'OBB sempre estigui orientat per l'empaquetament
            best_obb = initial_obb
            best_dims = initial_dims
            best_volume = initial_volume
            best_transformation = None
            
            # Matrius de rotació per les 24 orientacions possibles (6 cares × 4 rotacions per cara)
            rotations = [
                # Cara +Z cap amunt (orientació normal)
                [0, 0, 0],
                [0, 0, 90],
                [0, 0, 180],
                [0, 0, 270],
                
                # Cara -Z cap amunt (girat 180° sobre X)
                [180, 0, 0],
                [180, 0, 90],
                [180, 0, 180],
                [180, 0, 270],
                
                # Cara +Y cap amunt (girat 90° sobre X)
                [90, 0, 0],
                [90, 0, 90],
                [90, 0, 180],
                [90, 0, 270],
                
                # Cara -Y cap amunt (girat -90° sobre X)
                [-90, 0, 0],
                [-90, 0, 90],
                [-90, 0, 180],
                [-90, 0, 270],
                
                # Cara +X cap amunt (girat 90° sobre Y)
                [0, 90, 0],
                [0, 90, 90],
                [0, 90, 180],
                [0, 90, 270],
                
                # Cara -X cap amunt (girat -90° sobre Y)
                [0, -90, 0],
                [0, -90, 90],
                [0, -90, 180],
                [0, -90, 270],
            ]
            
            print(f"   Provant {len(rotations)} orientacions per trobar l'OBB més compacte...")
            
            for i, (rx, ry, rz) in enumerate(rotations):
                try:
                    # Crear matriu de transformació
                    transform = trimesh.transformations.compose_matrix(
                        angles=[np.radians(rx), np.radians(ry), np.radians(rz)]
                    )
                    
                    # Aplicar transformació a la malla
                    test_mesh = mesh.copy()
                    test_mesh.apply_transform(transform)
                    
                    # Calcular AABB després de la transformació (que serà el nostre OBB alineat)
                    bounds = test_mesh.bounds
                    test_dims = bounds[1] - bounds[0]
                    test_volume = np.prod(test_dims)
                    
                    # Si aquest OBB és més compacte, l'usem
                    if test_volume < best_volume:
                        print(f"      ✨ Millor OBB trobat! Orientació [{rx}°, {ry}°, {rz}°]: {test_dims[0]:.2f} × {test_dims[1]:.2f} × {test_dims[2]:.2f} (vol: {test_volume:.2f})")
                        best_volume = test_volume
                        best_dims = test_dims
                        best_transformation = transform
                        best_obb = test_mesh.bounding_box
                        
                except Exception as e:
                    print(f"      ⚠️ Error provant orientació [{rx}°, {ry}°, {rz}°]: {e}")
                    continue
            
            # Aplicar la millor transformació trobada
            if best_transformation is not None:
                canonical_mesh = mesh.copy()
                canonical_mesh.apply_transform(best_transformation)
                
                print(f"✅ OBB optimitzat: {best_dims[0]:.2f} × {best_dims[1]:.2f} × {best_dims[2]:.2f}")
                print(f"   Millora de volum: {((initial_volume - best_volume) / initial_volume * 100):.1f}% més compacte")
                
                return canonical_mesh, best_dims
            else:
                print("⚠️ No s'ha trobat millora, usant OBB inicial")
                # Usar l'OBB inicial com a fallback
                canonical_mesh = mesh.copy()
                to_obb = initial_obb.primitive.transform
                canonical_mesh.apply_transform(np.linalg.inv(to_obb))
                
                return canonical_mesh, initial_dims
            
        except Exception as e:
            print(f"❌ Error calculant OBB optimitzat: {e}")
            # Fallback a AABB si tot falla
            bounds = mesh.bounds
            dims = bounds[1] - bounds[0]
            print(f"⚠️ Usant AABB com a fallback: {dims[0]:.2f} × {dims[1]:.2f} × {dims[2]:.2f}")
            return mesh.copy(), dims
    
    def _compute_precise_oriented_bounding_box(self, mesh: trimesh.Trimesh):
        """
        Calcula un Oriented Bounding Box més precís utilitzant tècniques avançades
        segons la documentació de recerca.
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
        Optimitza l'OBB per objectes convexos provant diferents orientacions
        per minimitzar el volum.
        """
        try:
            # Aquesta és una implementació simplificada
            # En una implementació completa, es podria utilitzar una optimització
            # sobre SO(3) com es descriu a la documentació
            
            # Provar diferents rotacions i seleccionar la que minimitza el volum
            best_obb = initial_obb
            best_volume = np.prod(initial_obb.extents)
            
            # Provar un conjunt limitat de rotacions per trobar una millor
            for i in range(10):  # Nombre limitat d'intents
                # Generar una rotació aleatòria petita
                angle = np.random.uniform(-0.1, 0.1)
                axis = np.random.rand(3)
                axis = axis / np.linalg.norm(axis)
                
                # Aplicar la rotació
                rotation_matrix = trimesh.transformations.rotation_matrix(angle, axis)
                mesh_copy = mesh.copy()
                mesh_copy.apply_transform(rotation_matrix)
                
                # Calcular OBB per la malla rotada
                temp_obb = mesh_copy.bounding_box_oriented
                temp_volume = np.prod(temp_obb.extents)
                
                # Si el volum és menor, actualitzar
                if temp_volume < best_volume:
                    best_volume = temp_volume
                    best_obb = temp_obb
            
            return best_obb
        except Exception:
            return initial_obb
    
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
    
    def _level_based_packing(self, obj_dims: np.ndarray, target_pieces: int) -> Tuple[List[List[float]], List[List[float]]]:
        """
        Empaquetament en nivells millorat amb múltiples orientacions per pis
        Cada pis pot tenir una orientació diferent per optimitzar l'espai
        Ara també permet orientacions mixtes dins del mateix pis si és beneficiós
        
        Args:
            obj_dims: Dimensions de l'objecte (length, width, height)
            target_pieces: Nombre de peces a col·locar
            
        Returns:
            Tuple amb (posicions, rotacions)
        """
        positions = []
        rotations = []
        current_z = 0.0
        placed_count = 0
        
        print(f"📦 Empaquetament organitzat en pisos amb optimització avançada d'orientacions")
        print(f"   Dimensions objecte original: {obj_dims[0]:.1f} × {obj_dims[1]:.1f} × {obj_dims[2]:.1f}")
        print(f"   Marge: {self.margin}mm, Espai entre pisos: {self.inter_level_spacing}mm")
        print(f"   Mode rotacions intel·ligents: {'ACTIVAT' if self.enable_rotations else 'DESACTIVAT'}")
        
        level_number = 1
        
        while placed_count < target_pieces:
            print(f"\n🏗️ === ANALITZANT PIS {level_number} ===")
            
            # Estratègia 1: Orientació única per tot el pis (més eficient en espai)
            single_orientation_result = self._try_single_orientation_floor(obj_dims, current_z, target_pieces - placed_count)
            
            # Estratègia 2: Orientacions mixtes dins del pis (més eficient en quantitat)
            mixed_orientation_result = None
            if self.enable_rotations:
                mixed_orientation_result = self._try_mixed_orientation_floor(obj_dims, current_z, target_pieces - placed_count)
            
            # Seleccionar la millor estratègia
            best_strategy = self._select_best_floor_strategy(single_orientation_result, mixed_orientation_result)
            
            if best_strategy is None:
                print(f"⚠️ No es poden col·locar més peces al pis {level_number}")
                break
            
            # Aplicar l'estratègia seleccionada
            level_positions = best_strategy['positions']
            level_rotations = best_strategy['rotations']
            floor_height = best_strategy['floor_height']
            strategy_name = best_strategy['strategy']
            
            # Verificar si hi ha espai vertical suficient
            if current_z + floor_height > self.container_height:
                print(f"⚠️ Espai vertical exhaurit al pis {level_number}")
                break
            
            print(f"✅ Pis {level_number}: Z={current_z:.1f} - {current_z + floor_height:.1f}mm")
            print(f"   Estratègia: {strategy_name}")
            print(f"   Peces col·locades: {len(level_positions)}")
            
            positions.extend(level_positions)
            rotations.extend(level_rotations)
            placed_count += len(level_positions)
            
            level_number += 1
            
            # Moure al següent nivell
            current_z += floor_height + self.inter_level_spacing
        
        print(f"\n📊 === RESUM FINAL ===")
        print(f"📊 Total col·locat: {placed_count} peces en {level_number-1} pisos")
        print(f"🏗️ Altura total utilitzada: {current_z - self.inter_level_spacing:.1f}mm de {self.container_height}mm")
        return positions, rotations
    
    def _try_single_orientation_floor(self, obj_dims: np.ndarray, current_z: float, max_pieces: int) -> Dict[str, Any]:
        """Prova empaquetament amb una sola orientació per tot el pis"""
        best_orientation = self._find_best_floor_orientation(obj_dims, current_z)
        
        if best_orientation is None:
            return None
        
        oriented_dims, floor_rotation = best_orientation
        floor_height = oriented_dims[2]
        
        # Empaquetar amb aquesta orientació
        level_positions, level_rotations = self._pack_floor_with_orientation(
            oriented_dims, current_z, floor_rotation, max_pieces
        )
        
        return {
            'positions': level_positions,
            'rotations': level_rotations,
            'floor_height': floor_height,
            'strategy': f'Orientació única: [{floor_rotation[0]}°, {floor_rotation[1]}°, {floor_rotation[2]}°]',
            'pieces_count': len(level_positions),
            'efficiency_score': len(level_positions)  # Simple: més peces = millor
        }
    
    def _try_mixed_orientation_floor(self, obj_dims: np.ndarray, current_z: float, max_pieces: int) -> Dict[str, Any]:
        """Prova empaquetament amb orientacions mixtes dins del mateix pis"""
        remaining_height = self.container_height - current_z
        
        # Trobar totes les orientacions vàlides per aquest pis
        valid_orientations = []
        orientations = [
            {"dims": [obj_dims[0], obj_dims[1], obj_dims[2]], "rotation": [0, 0, 0], "name": "LxWxH"},
            {"dims": [obj_dims[0], obj_dims[2], obj_dims[1]], "rotation": [90, 0, 0], "name": "LxHxW"},
            {"dims": [obj_dims[1], obj_dims[0], obj_dims[2]], "rotation": [0, 0, 90], "name": "WxLxH"},
            {"dims": [obj_dims[1], obj_dims[2], obj_dims[0]], "rotation": [90, 0, 90], "name": "WxHxL"},
            {"dims": [obj_dims[2], obj_dims[0], obj_dims[1]], "rotation": [0, 90, 0], "name": "HxLxW"},
            {"dims": [obj_dims[2], obj_dims[1], obj_dims[0]], "rotation": [0, 90, 90], "name": "HxWxL"}
        ]
        
        for orientation in orientations:
            if orientation["dims"][2] <= remaining_height:
                valid_orientations.append(orientation)
        
        if len(valid_orientations) <= 1:
            return None  # No hi ha prou orientacions per mixtificar
        
        # Implementació simplificada: alternar entre les dues millors orientacions
        best_1 = max(valid_orientations, key=lambda x: self._calculate_pieces_per_floor(np.array(x["dims"])))
        valid_orientations.remove(best_1)
        best_2 = max(valid_orientations, key=lambda x: self._calculate_pieces_per_floor(np.array(x["dims"])))
        
        # Aquí es podria implementar un algoritme més sofisticat per combinar orientacions
        # Per ara, simplemente retornem None perquè aquesta funcionalitat necessita més desenvolupament
        print("   💡 Mode orientacions mixtes detectat però encara no implementat completament")
        return None
    
    def _select_best_floor_strategy(self, single_result: Dict[str, Any], mixed_result: Dict[str, Any]) -> Dict[str, Any]:
        """Selecciona la millor estratègia entre orientació única i mixta"""
        # Si només tenim una opció
        if single_result is None and mixed_result is None:
            return None
        if single_result is None:
            return mixed_result
        if mixed_result is None:
            return single_result
        
        # Comparar basant-se en el nombre de peces col·locades
        if mixed_result['pieces_count'] > single_result['pieces_count']:
            print("   🎯 Seleccionada estratègia mixta (més peces)")
            return mixed_result
        else:
            print("   🎯 Seleccionada estratègia d'orientació única")
            return single_result
        
        while placed_count < target_pieces:
            # Provar diferents orientacions per aquest pis
            best_orientation = self._find_best_floor_orientation(obj_dims, current_z)
            
            if best_orientation is None:
                print(f"⚠️ No es pot trobar una orientació vàlida per al pis {level_number}")
                break
                
            oriented_dims, floor_rotation = best_orientation
            floor_height = oriented_dims[2]
            
            # Verificar si hi ha espai vertical suficient
            if current_z + floor_height > self.container_height:
                print(f"⚠️ Espai vertical exhaurit al pis {level_number}")
                break
            
            print(f"Pis {level_number}: Z={current_z:.1f} - {current_z + floor_height:.1f}mm")
            print(f"   Orientació escollida: rotació [{floor_rotation[0]}°, {floor_rotation[1]}°, {floor_rotation[2]}°]")
            print(f"   Dimensions orientades: {oriented_dims[0]:.1f} × {oriented_dims[1]:.1f} × {oriented_dims[2]:.1f}")
            
            # Empaquetar peces en aquest pis amb l'orientació escollida
            level_positions, level_rotations = self._pack_floor_with_orientation(
                oriented_dims, current_z, floor_rotation, target_pieces - placed_count
            )
            
            if not level_positions:
                print(f"⚠️ No es poden col·locar peces al pis {level_number}")
                break
            
            positions.extend(level_positions)
            rotations.extend(level_rotations)
            placed_count += len(level_positions)
            
            print(f"✅ Pis {level_number}: {len(level_positions)} peces col·locades")
            level_number += 1
            
            # Moure al següent nivell
            current_z += floor_height + self.inter_level_spacing
        
        print(f"📊 Total col·locat: {placed_count} peces en {level_number-1} pisos")
        return positions, rotations
    
    def _find_best_floor_orientation(self, obj_dims: np.ndarray, current_z: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Troba la millor orientació per a un pis específic
        Prova TOTES les orientacions possibles de la peça per maximitzar l'eficiència
        
        Returns:
            Tuple amb (dimensions_orientades, rotació_[rx, ry, rz]) o None si no hi ha cap orientació vàlida
        """
        best_orientation = None
        best_pieces_per_floor = 0
        remaining_height = self.container_height - current_z
        
        print(f"   🔍 Provant totes les orientacions possibles per al pis")
        print(f"   📏 Dimensions originals: {obj_dims[0]:.1f} × {obj_dims[1]:.1f} × {obj_dims[2]:.1f}")
        print(f"   📐 Espai vertical disponible: {remaining_height:.1f}mm")
        
        # Provar TOTES les orientacions possibles de la peça (6 orientacions principals)
        # Cada orientació representa una forma diferent de col·locar la peça
        orientations = [
            # Orientació 1: LxWxH (normal)
            {"dims": [obj_dims[0], obj_dims[1], obj_dims[2]], "rotation": [0, 0, 0], "name": "LxWxH (normal)"},
            # Orientació 2: LxHxW (girada sobre Y, altura ara és amplada)
            {"dims": [obj_dims[0], obj_dims[2], obj_dims[1]], "rotation": [90, 0, 0], "name": "LxHxW (de costat W->H)"},
            # Orientació 3: WxLxH (girada sobre Z)
            {"dims": [obj_dims[1], obj_dims[0], obj_dims[2]], "rotation": [0, 0, 90], "name": "WxLxH (girada 90°)"},
            # Orientació 4: WxHxL (girada sobre Y i Z)
            {"dims": [obj_dims[1], obj_dims[2], obj_dims[0]], "rotation": [90, 0, 90], "name": "WxHxL (de costat L->H)"},
            # Orientació 5: HxLxW (girada sobre X)
            {"dims": [obj_dims[2], obj_dims[0], obj_dims[1]], "rotation": [0, 90, 0], "name": "HxLxW (de costat W->L)"},
            # Orientació 6: HxWxL (girada sobre X i Z)
            {"dims": [obj_dims[2], obj_dims[1], obj_dims[0]], "rotation": [0, 90, 90], "name": "HxWxL (totalment girada)"}
        ]
        
        for orientation in orientations:
            oriented_dims = np.array(orientation["dims"])
            rotation = np.array(orientation["rotation"])
            name = orientation["name"]
            
            # Verificar si la peça cap verticalment amb aquesta orientació
            if oriented_dims[2] > remaining_height:
                print(f"      ❌ {name}: Altura {oriented_dims[2]:.1f}mm massa gran")
                continue
            
            # Calcular quantes peces caben en aquest pis amb aquesta orientació
            pieces_per_floor = self._calculate_pieces_per_floor(oriented_dims)
            
            print(f"      🔧 {name}: {oriented_dims[0]:.1f}×{oriented_dims[1]:.1f}×{oriented_dims[2]:.1f} → {pieces_per_floor} peces")
            
            if pieces_per_floor > best_pieces_per_floor:
                best_pieces_per_floor = pieces_per_floor
                best_orientation = (oriented_dims, rotation)
                print(f"         ✨ Nova millor orientació! {pieces_per_floor} peces")
        
        if best_orientation:
            oriented_dims, rotation = best_orientation
            print(f"   ✅ Millor orientació: {oriented_dims[0]:.1f}×{oriented_dims[1]:.1f}×{oriented_dims[2]:.1f} amb {best_pieces_per_floor} peces")
            print(f"      Rotació aplicada: [{rotation[0]}°, {rotation[1]}°, {rotation[2]}°]")
        else:
            print(f"   ❌ Cap orientació vàlida trobada per aquest pis")
        
        return best_orientation
    
    def _calculate_pieces_per_floor(self, oriented_dims: np.ndarray) -> int:
        """Calcula quantes peces caben en un pis amb les dimensions donades"""
        # Dimensions amb marge
        piece_length = oriented_dims[0] + self.margin
        piece_width = oriented_dims[1] + self.margin
        
        # Calcular quantes peces caben
        pieces_x = max(0, int(self.container_length // piece_length))
        pieces_y = max(0, int(self.container_width // piece_width))
        
        return pieces_x * pieces_y
    
    def _pack_floor_with_orientation(self, oriented_dims: np.ndarray, z_level: float, 
                                   floor_rotation: np.ndarray, max_pieces: int) -> Tuple[List[List[float]], List[List[float]]]:
        """
        Empaqueta peces en un pis amb una orientació específica
        Utilitza algoritme de Bottom-Left Fill millorat amb rotacions completes
        """
        positions = []
        rotations = []
        
        # Dimensions amb marge
        piece_length = oriented_dims[0] + self.margin
        piece_width = oriented_dims[1] + self.margin
        piece_height = oriented_dims[2]
        
        # Calcular posicions de graella
        pieces_x = int(self.container_length // piece_length)
        pieces_y = int(self.container_width // piece_width)
        
        pieces_placed = 0
        
        print(f"      📐 Graella calculada: {pieces_x} × {pieces_y} = {pieces_x * pieces_y} posicions possibles")
        print(f"      📦 Marge aplicat: {self.margin}mm, Espai final per peça: {piece_length:.1f} × {piece_width:.1f}")
        
        # Algoritme Bottom-Left: omplir de baix a esquerra
        for j in range(pieces_y):  # Y primer (bottom)
            for i in range(pieces_x):  # Després X (left)
                if pieces_placed >= max_pieces:
                    break
                
                # Calcular posició del centre de la peça
                x = i * piece_length + oriented_dims[0] / 2
                y = j * piece_width + oriented_dims[1] / 2
                z = z_level + piece_height / 2
                
                # Verificar que la posició és dins del contenidor
                if (x + oriented_dims[0]/2 <= self.container_length and
                    y + oriented_dims[1]/2 <= self.container_width and
                    z + oriented_dims[2]/2 <= self.container_height):
                    
                    positions.append([x, y, z])
                    # Aplicar la rotació completa de l'orientació del pis
                    rotations.append(floor_rotation.tolist())
                    pieces_placed += 1
                    
                    if pieces_placed == 1:  # Només mostrar detalls de la primera peça
                        print(f"         🎯 Primera peça: pos=({x:.1f}, {y:.1f}, {z:.1f}), rot=[{floor_rotation[0]}°, {floor_rotation[1]}°, {floor_rotation[2]}°]")
                else:
                    print(f"      ❌ Posició ({x:.1f}, {y:.1f}, {z:.1f}) fora de límits")
            
            if pieces_placed >= max_pieces:
                break
        
        if pieces_placed > 0:
            print(f"      ✅ {pieces_placed} peces col·locades en aquest pis")
        
        return positions, rotations
    
    def _create_success_result(self, count: int, efficiency: float, 
                             time_taken: float, obj_dims: List[float], obj_volume: float,
                             positions: List[List[float]], rotations: List[List[float]],
                             canonical_mesh: trimesh.Trimesh) -> Dict[str, Any]:
        """Crea el diccionari de resultats d'èxit"""
        return {
            'success': True,
            'positions': positions.copy(),
            'rotations': rotations.copy(),
            'pieces_count': count,
            'efficiency': efficiency,
            'execution_time': time_taken,
            'method': 'obb_based',
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
            'canonical_mesh': canonical_mesh  # Malla en orientació canònica
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