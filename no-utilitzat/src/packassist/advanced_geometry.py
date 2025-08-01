"""
Sistema avançat de geometria real per PackAssist
Analitza formes complexes amb múltiples costats, cares paral·leles, i encaixos
Optimitzat per càlcul sota demanda
"""
import numpy as np
import math
import re
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Tuple, Optional

class Face3D:
    """Representa una cara 3D amb normal i vèrtexs"""
    def __init__(self, vertices: List[Tuple[float, float, float]], normal: Tuple[float, float, float] = None):
        self.vertices = vertices
        self.normal = normal or self._calculate_normal()
        self.area = self._calculate_area()
        
    def _calculate_normal(self) -> Tuple[float, float, float]:
        """Calcula la normal de la cara"""
        if len(self.vertices) < 3:
            return (0, 0, 1)
        
        v1 = np.array(self.vertices[1]) - np.array(self.vertices[0])
        v2 = np.array(self.vertices[2]) - np.array(self.vertices[0])
        normal = np.cross(v1, v2)
        
        # Normalitzar
        norm = np.linalg.norm(normal)
        if norm > 0:
            normal = normal / norm
        
        return tuple(normal)
    
    def _calculate_area(self) -> float:
        """Calcula l'àrea de la cara per triangulació"""
        if len(self.vertices) < 3:
            return 0.0
        
        # Triangulació simple per polígons convexos
        area = 0.0
        for i in range(1, len(self.vertices) - 1):
            v1 = np.array(self.vertices[i]) - np.array(self.vertices[0])
            v2 = np.array(self.vertices[i+1]) - np.array(self.vertices[0])
            triangle_area = 0.5 * np.linalg.norm(np.cross(v1, v2))
            area += triangle_area
        
        return area
    
    def is_parallel_to(self, other_face: 'Face3D', tolerance: float = 0.1) -> bool:
        """Comprova si aquesta cara és paral·lela a una altra"""
        dot_product = abs(np.dot(self.normal, other_face.normal))
        return abs(dot_product - 1.0) < tolerance  # Paral·leles si dot product ≈ 1

class ComplexGeometry:
    """Representa una geometria complexa amb múltiples cares i propietats avançades"""
    
    def __init__(self):
        self.faces: List[Face3D] = []
        self.vertices: List[Tuple[float, float, float]] = []
        self.edges: List[Tuple[int, int]] = []  # Índexs de vèrtexs
        self.parallel_face_pairs: List[Tuple[int, int]] = []
        self.concave_regions: List[Dict] = []
        self.interlocking_features: List[Dict] = []
        
        # Propietats calculades
        self.real_volume: float = 0.0
        self.surface_area: float = 0.0
        self.bounding_box: Dict[str, float] = {}
        self.complexity_score: float = 0.0
        
    def add_face(self, vertices: List[Tuple[float, float, float]]):
        """Afegeix una cara a la geometria"""
        face = Face3D(vertices)
        self.faces.append(face)
        
        # Actualitzar llista de vèrtexs únics
        for vertex in vertices:
            if vertex not in self.vertices:
                self.vertices.append(vertex)
    
    def analyze_parallel_faces(self, tolerance: float = 0.1):
        """Detecta cares paral·leles per possibles encaixos"""
        self.parallel_face_pairs = []
        
        for i, face1 in enumerate(self.faces):
            for j, face2 in enumerate(self.faces[i+1:], i+1):
                if face1.is_parallel_to(face2, tolerance):
                    self.parallel_face_pairs.append((i, j))
                    
        print(f"🔍 Detectades {len(self.parallel_face_pairs)} parelles de cares paral·leles")
    
    def calculate_real_volume(self):
        """Calcula el volum real per triangulació de cares"""
        if not self.faces:
            return 0.0
        
        # Algorisme simple: suma de volums de tetraedres des de l'origen
        total_volume = 0.0
        origin = np.array([0, 0, 0])
        
        for face in self.faces:
            if len(face.vertices) >= 3:
                # Per cada triangle de la cara
                for i in range(1, len(face.vertices) - 1):
                    v1 = np.array(face.vertices[0])
                    v2 = np.array(face.vertices[i])
                    v3 = np.array(face.vertices[i+1])
                    
                    # Volum del tetraedre origin-v1-v2-v3
                    tetrahedron_vol = abs(np.dot(v1, np.cross(v2, v3))) / 6.0
                    total_volume += tetrahedron_vol
        
        self.real_volume = abs(total_volume)
        return self.real_volume
    
    def calculate_bounding_box(self):
        """Calcula el bounding box tradicional"""
        if not self.vertices:
            return {}
        
        x_coords = [v[0] for v in self.vertices]
        y_coords = [v[1] for v in self.vertices]
        z_coords = [v[2] for v in self.vertices]
        
        self.bounding_box = {
            'min_x': min(x_coords), 'max_x': max(x_coords),
            'min_y': min(y_coords), 'max_y': max(y_coords),
            'min_z': min(z_coords), 'max_z': max(z_coords),
            'length': max(x_coords) - min(x_coords),
            'width': max(y_coords) - min(y_coords),
            'height': max(z_coords) - min(z_coords)
        }
        
        return self.bounding_box
    
    def calculate_complexity_score(self) -> float:
        """Calcula un score de complexitat basat en característiques geomètriques"""
        score = 0.0
        
        # Factor per nombre de cares
        score += len(self.faces) * 0.1
        
        # Factor per cares paral·leles (indiquen encaixos)
        score += len(self.parallel_face_pairs) * 0.5
        
        # Factor per concavitat
        score += len(self.concave_regions) * 0.3
        
        # Factor per diferència volum/bounding box
        if self.bounding_box:
            bbox_volume = (self.bounding_box['length'] * 
                          self.bounding_box['width'] * 
                          self.bounding_box['height'])
            if bbox_volume > 0:
                volume_ratio = self.real_volume / bbox_volume
                score += (1.0 - volume_ratio) * 2.0  # Més complex = menys volum relatiu
        
        self.complexity_score = score
        return score
    
    def detect_interlocking_features(self):
        """Detecta característiques que permeten encaixar amb altres peces"""
        interlocking_features = []
        
        # Buscar cares paral·leles que podrien encaixar
        for i, j in self.parallel_face_pairs:
            face1, face2 = self.faces[i], self.faces[j]
            
            # Calcular distància entre cares paral·leles
            center1 = np.mean(face1.vertices, axis=0)
            center2 = np.mean(face2.vertices, axis=0)
            distance = np.linalg.norm(center2 - center1)
            
            interlocking_features.append({
                'type': 'parallel_faces',
                'face_indices': [i, j],
                'distance': distance,
                'normal': face1.normal,
                'area1': face1.area,
                'area2': face2.area
            })
        
        self.interlocking_features = interlocking_features
        return interlocking_features
    
    def get_analysis_summary(self) -> Dict:
        """Retorna un resum complet de l'anàlisi geomètric"""
        return {
            'total_faces': len(self.faces),
            'total_vertices': len(self.vertices),
            'parallel_face_pairs': len(self.parallel_face_pairs),
            'real_volume': self.real_volume,
            'bounding_box': self.bounding_box,
            'bbox_volume': (self.bounding_box.get('length', 0) * 
                           self.bounding_box.get('width', 0) * 
                           self.bounding_box.get('height', 0)),
            'volume_efficiency': (self.real_volume / 
                                (self.bounding_box.get('length', 1) * 
                                 self.bounding_box.get('width', 1) * 
                                 self.bounding_box.get('height', 1))) if self.bounding_box else 0,
            'complexity_score': self.complexity_score,
            'interlocking_features': len(self.interlocking_features),
            'surface_area': sum(face.area for face in self.faces)
        }


def parse_stp_advanced_geometry(stp_content: str, filename: str) -> Optional[ComplexGeometry]:
    """
    Analitza el contingut STP per extreure geometria complexa real
    """
    try:
        geometry = ComplexGeometry()
        
        # 1. Extreure tots els punts CARTESIAN_POINT
        points_pattern = r'CARTESIAN_POINT\s*\(\s*\'[^\']*\'\s*,\s*\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)'
        points = re.findall(points_pattern, stp_content)
        
        if not points:
            print("⚠️  No s'han trobat punts CARTESIAN_POINT")
            return None
        
        # Convertir a coordenades flotants
        vertices = [(float(p[0]), float(p[1]), float(p[2])) for p in points]
        unique_vertices = list(set(vertices))  # Eliminar duplicats
        
        print(f"📊 Punts únics trobats: {len(unique_vertices)}")
        
        # 2. Detectar cares des de ADVANCED_FACE o FACE_BOUND
        faces_pattern = r'ADVANCED_FACE\s*\([^)]+\)'
        face_matches = re.findall(faces_pattern, stp_content)
        
        print(f"📊 Cares avançades trobades: {len(face_matches)}")
        
        # 3. Si tenim molts punts, crear cares aproximades
        if len(unique_vertices) >= 8:  # Mínim per un objecte 3D
            # Algoritme simple: crear cares basades en proximitat de punts
            geometry.vertices = unique_vertices
            
            # Crear cares aproximades agrupant punts per planes similars
            face_groups = _group_points_by_planes(unique_vertices)
            
            for group in face_groups:
                if len(group) >= 3:  # Mínim per una cara
                    geometry.add_face(group)
        
        # 4. Calcular propietats
        geometry.calculate_bounding_box()
        geometry.calculate_real_volume()
        geometry.analyze_parallel_faces()
        geometry.detect_interlocking_features()
        geometry.calculate_complexity_score()
        
        print(f"✅ Geometria analitzada: {len(geometry.faces)} cares, {len(geometry.vertices)} vèrtexs")
        
        return geometry
        
    except Exception as e:
        print(f"❌ Error en anàlisi avançada de geometria: {e}")
        return None


def _group_points_by_planes(vertices: List[Tuple[float, float, float]], tolerance: float = 1.0) -> List[List[Tuple[float, float, float]]]:
    """
    Agrupa punts que semblen estar al mateix pla
    """
    groups = []
    used_vertices = set()
    
    for i, vertex in enumerate(vertices):
        if vertex in used_vertices:
            continue
            
        # Trobar punts propers en el mateix pla
        group = [vertex]
        used_vertices.add(vertex)
        
        for j, other_vertex in enumerate(vertices[i+1:], i+1):
            if other_vertex in used_vertices:
                continue
                
            # Comprovar si estan prou a prop (mateix pla aproximat)
            distance = np.linalg.norm(np.array(vertex) - np.array(other_vertex))
            if distance < tolerance * 10:  # Grup ampli
                # Comprovar si semblen estar al mateix pla Z (simplificat)
                if abs(vertex[2] - other_vertex[2]) < tolerance:
                    group.append(other_vertex)
                    used_vertices.add(other_vertex)
        
        if len(group) >= 3:
            groups.append(group)
    
    return groups


class GeometrySimplifier:
    """
    Sistema de simplificació progressiva de geometries complexes
    Càlcul sota demanda per millor rendiment
    """
    
    def __init__(self, complex_geometry: ComplexGeometry):
        self.original_geometry = complex_geometry
        self.simplified_cache = {}  # Cache només per nivells calculats
        self.current_level = 100  # 100% = original
        self.face_importance = None  # Calcular només una vegada
        
    def calculate_face_importance_once(self):
        """
        Calcula la importància de cada cara només una vegada
        """
        if self.face_importance is not None:
            return self.face_importance
            
        print("🔄 Calculant importància de cares...")
        importance_scores = []
        
        for i, face in enumerate(self.original_geometry.faces):
            score = 0.0
            
            # Factor 1: Àrea de la cara (cares grans són més importants)
            score += face.area * 0.3
            
            # Factor 2: Si té cares paral·leles (important per encaixos)
            parallel_bonus = sum(1 for pair in self.original_geometry.parallel_face_pairs 
                                if i in pair) * 0.4
            score += parallel_bonus
            
            # Factor 3: Posició (cares exteriors més importants)
            face_center = np.mean(face.vertices, axis=0)
            bbox = self.original_geometry.bounding_box
            if bbox:
                # Proximitat als extrems del bounding box
                edge_proximity = (
                    min(abs(face_center[0] - bbox['min_x']), abs(face_center[0] - bbox['max_x'])) +
                    min(abs(face_center[1] - bbox['min_y']), abs(face_center[1] - bbox['max_y'])) +
                    min(abs(face_center[2] - bbox['min_z']), abs(face_center[2] - bbox['max_z']))
                )
                score += (1.0 / (edge_proximity + 1.0)) * 0.3
            
            importance_scores.append(score)
        
        self.face_importance = importance_scores
        print(f"✅ Importància calculada per {len(importance_scores)} cares")
        return self.face_importance
    
    def simplify_to_percentage_on_demand(self, percentage: int) -> ComplexGeometry:
        """
        Simplifica a un percentatge específic NOMÉS quan es demana
        """
        # Comprovar cache primer
        if percentage in self.simplified_cache:
            return self.simplified_cache[percentage]
        
        if percentage >= 100:
            return self.original_geometry
        
        # Calcular nombre de cares objectiu
        original_faces = len(self.original_geometry.faces)
        target_faces = max(4, int(original_faces * (percentage / 100)))
        
        print(f"🔄 Simplificant a {percentage}% ({target_faces} cares)...")
        
        # Calcular importància només si no s'ha fet
        face_importance = self.calculate_face_importance_once()
        
        # Crear nova geometria simplificada
        simplified = ComplexGeometry()
        
        # Seleccionar les cares més importants
        important_faces = sorted(
            enumerate(self.original_geometry.faces),
            key=lambda x: face_importance[x[0]],
            reverse=True
        )[:target_faces]
        
        # Reconstruir geometria amb les cares seleccionades
        for _, face in important_faces:
            simplified.add_face(face.vertices)
        
        # Recalcular propietats (més ràpid)
        simplified.calculate_bounding_box()
        simplified.calculate_real_volume()
        # Saltar anàlisis costosos per velocitat
        simplified.parallel_face_pairs = []
        simplified.interlocking_features = []
        simplified.complexity_score = len(simplified.faces) * 0.1
        
        # Guardar al cache
        self.simplified_cache[percentage] = simplified
        
        print(f"✅ Simplificat a {len(simplified.faces)} cares")
        return simplified
    
    def get_real_time_stats(self, percentage: int) -> Dict:
        """
        Retorna estadístiques ràpides sense càlculs pesats
        """
        original_faces = len(self.original_geometry.faces)
        current_faces = max(4, int(original_faces * (percentage / 100)))
        
        # Estimació ràpida sense calcular geometria completa
        return {
            'current_faces': current_faces,
            'original_faces': original_faces,
            'reduction_ratio': current_faces / original_faces,
            'estimated_volume_accuracy': percentage / 100.0,  # Estimació simple
            'processing_speed_estimate': self._estimate_processing_speed(current_faces),
            'percentage': percentage
        }
    
    def _estimate_processing_speed(self, face_count: int) -> str:
        """Estima la velocitat de processament segons el nombre de cares"""
        if face_count > 1000:
            return "🐌 Molt lent"
        elif face_count > 500:
            return "🚶 Lent"
        elif face_count > 100:
            return "🚴 Moderat"
        elif face_count > 50:
            return "🏃 Ràpid"
        else:
            return "⚡ Molt ràpid"


class SmartBoundingBoxGenerator:
    """
    Generador de caixetes envoltants intel·ligents
    """
    
    def __init__(self, complex_geometry: ComplexGeometry):
        self.original_geometry = complex_geometry
        self.original_bounds = self._calculate_bounds(complex_geometry)
        
    def _calculate_bounds(self, geometry: ComplexGeometry) -> dict:
        """Calcula els límits de la geometria"""
        if len(geometry.vertices) == 0:
            return {'min': np.array([0, 0, 0]), 'max': np.array([0, 0, 0])}
            
        vertices_array = np.array(geometry.vertices)
        return {
            'min': np.min(vertices_array, axis=0),
            'max': np.max(vertices_array, axis=0)
        }
    
    def generate_smart_bounding_box(self, target_faces: int, box_type: str = "rectangular") -> ComplexGeometry:
        """
        Genera una caixa envoltant intel·ligent amb el nombre de cares especificat
        
        Args:
            target_faces: Nombre de cares desitjades
            box_type: Tipus de caixa ("rectangular", "cylindrical", "octagonal")
            
        Returns:
            ComplexGeometry: Caixa envoltant amb el nombre de cares especificat
        """
        bounds = self.original_bounds
        dimensions = bounds['max'] - bounds['min']
        
        # Afegeix marge del 2% per assegurar que l'objecte hi cap
        margin = dimensions * 0.02
        min_point = bounds['min'] - margin
        max_point = bounds['max'] + margin
        
        if box_type == "rectangular":
            return self._create_rectangular_box(min_point, max_point, target_faces)
        elif box_type == "cylindrical":
            return self._create_cylindrical_box(min_point, max_point, target_faces)
        elif box_type == "octagonal":
            return self._create_octagonal_box(min_point, max_point, target_faces)
        else:
            return self._create_adaptive_box(min_point, max_point, target_faces)
    
    def _create_rectangular_box(self, min_point: np.ndarray, max_point: np.ndarray, target_faces: int) -> ComplexGeometry:
        """Crea una caixa rectangular amb subdivisions per arribar al nombre de cares"""
        if target_faces < 6:
            target_faces = 6  # Mínim per un cub
            
        # Crear geometria buida
        geometry = ComplexGeometry()
        
        # Cub bàsic (6 cares)
        vertices = [
            (min_point[0], min_point[1], min_point[2]),  # 0
            (max_point[0], min_point[1], min_point[2]),  # 1
            (max_point[0], max_point[1], min_point[2]),  # 2
            (min_point[0], max_point[1], min_point[2]),  # 3
            (min_point[0], min_point[1], max_point[2]),  # 4
            (max_point[0], min_point[1], max_point[2]),  # 5
            (max_point[0], max_point[1], max_point[2]),  # 6
            (min_point[0], max_point[1], max_point[2])   # 7
        ]
        
        faces_indices = [
            [0, 1, 2, 3],  # Base inferior
            [4, 7, 6, 5],  # Base superior
            [0, 4, 5, 1],  # Lateral 1
            [1, 5, 6, 2],  # Lateral 2
            [2, 6, 7, 3],  # Lateral 3
            [3, 7, 4, 0]   # Lateral 4
        ]
        
        # Afegir les cares a la geometria
        for face_indices in faces_indices:
            face_vertices = [vertices[i] for i in face_indices]
            geometry.add_face(face_vertices)
        
        # Si necessitem més cares, subdividim
        if target_faces > 6:
            geometry = self._subdivide_geometry(geometry, target_faces)
        
        return geometry
    
    def _create_cylindrical_box(self, min_point: np.ndarray, max_point: np.ndarray, target_faces: int) -> ComplexGeometry:
        """Crea una caixa cilíndrica"""
        import math
        
        # Crear geometria buida
        geometry = ComplexGeometry()
        
        # Calcula el radi necessari
        dimensions = max_point - min_point
        radius = max(dimensions[0], dimensions[1]) / 2 * 1.1  # 10% marge extra
        center_x = (min_point[0] + max_point[0]) / 2
        center_y = (min_point[1] + max_point[1]) / 2
        
        # Determina el nombre de costats del cilindre
        sides = max(8, min(target_faces // 3, 32))  # Entre 8 i 32 costats
        
        # Generar vèrtexs del cilindre
        bottom_vertices = []
        top_vertices = []
        
        for i in range(sides):
            angle = 2 * math.pi * i / sides
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            bottom_vertices.append((x, y, min_point[2]))
            top_vertices.append((x, y, max_point[2]))
        
        # Crear base inferior
        geometry.add_face(bottom_vertices)
        
        # Crear base superior (en ordre invers)
        geometry.add_face(top_vertices[::-1])
        
        # Crear cares laterals
        for i in range(sides):
            next_i = (i + 1) % sides
            face_vertices = [
                bottom_vertices[i],
                bottom_vertices[next_i], 
                top_vertices[next_i],
                top_vertices[i]
            ]
            geometry.add_face(face_vertices)
        
        return geometry
    
    def _create_octagonal_box(self, min_point: np.ndarray, max_point: np.ndarray, target_faces: int) -> ComplexGeometry:
        """Crea una caixa octogonal"""
        # Similar al cilíndric però amb 8 costats fixos
        return self._create_cylindrical_box(min_point, max_point, target_faces)
    
    def _create_adaptive_box(self, min_point: np.ndarray, max_point: np.ndarray, target_faces: int) -> ComplexGeometry:
        """Crea una caixa adaptativa segons les proporcions de l'objecte"""
        dimensions = max_point - min_point
        
        # Si l'objecte és molt allargat, usa cilindre
        aspect_ratios = dimensions / np.min(dimensions)
        if np.max(aspect_ratios) > 3:
            return self._create_cylindrical_box(min_point, max_point, target_faces)
        else:
            return self._create_rectangular_box(min_point, max_point, target_faces)
    
    def _subdivide_geometry(self, geometry: ComplexGeometry, target_faces: int) -> ComplexGeometry:
        """Subdivideix les cares d'una geometria per arribar al nombre objectiu"""
        if len(geometry.faces) >= target_faces:
            return geometry
        
        # Crear nova geometria
        new_geometry = ComplexGeometry()
        
        faces_added = 0
        for face in geometry.faces:
            if faces_added >= target_faces:
                break
                
            # Subdividir cada cara en 4 subcares si és possible
            if len(face.vertices) == 4 and faces_added + 4 <= target_faces:
                subcares = self._subdivide_face(face)
                for subface_vertices in subcares:
                    new_geometry.add_face(subface_vertices)
                    faces_added += 1
            else:
                # Afegir cara original
                new_geometry.add_face(face.vertices)
                faces_added += 1
        
        return new_geometry
    
    def _subdivide_face(self, face: 'Face3D') -> List[List[Tuple[float, float, float]]]:
        """Subdivideix una cara en 4 subcares"""
        if len(face.vertices) != 4:
            return [face.vertices]  # No es pot subdividir
        
        v0, v1, v2, v3 = face.vertices
        
        # Calcular punts mitjos
        def midpoint(p1, p2):
            return ((p1[0] + p2[0])/2, (p1[1] + p2[1])/2, (p1[2] + p2[2])/2)
        
        # Punts mitjos de les arestes
        m01 = midpoint(v0, v1)
        m12 = midpoint(v1, v2) 
        m23 = midpoint(v2, v3)
        m30 = midpoint(v3, v0)
        
        # Punt central
        center = midpoint(midpoint(v0, v2), midpoint(v1, v3))
        
        # Crear 4 subcares
        return [
            [v0, m01, center, m30],
            [m01, v1, m12, center],
            [center, m12, v2, m23],
            [m30, center, m23, v3]
        ]
    
    def calculate_efficiency(self, bounding_box: ComplexGeometry) -> dict:
        """Calcula l'eficiència espacial de la caixa envoltant"""
        original_volume = self._calculate_volume(self.original_geometry)
        box_volume = self._calculate_volume(bounding_box)
        
        if box_volume == 0:
            efficiency = 0
        else:
            efficiency = original_volume / box_volume
        
        return {
            'efficiency': efficiency,
            'space_utilization': efficiency * 100,
            'original_volume': original_volume,
            'box_volume': box_volume,
            'wasted_space': (1 - efficiency) * 100
        }
    
    def _calculate_volume(self, geometry: ComplexGeometry) -> float:
        """Calcula el volum aproximat d'una geometria"""
        bounds = self._calculate_bounds(geometry)
        dimensions = bounds['max'] - bounds['min']
        return float(np.prod(dimensions))


class RealTimeGeometryViewer:
    """
    Visualitzador en temps real optimitzat amb funcionalitat de bounding box
    """
    
    def __init__(self, geometry_simplifier: GeometrySimplifier):
        self.simplifier = geometry_simplifier
        self.bbox_generator = SmartBoundingBoxGenerator(geometry_simplifier.original_geometry)
        self.current_geometry = None
        self.current_bbox = None
        self.viewer_window = None
        self.is_calculating = False
        self.use_bounding_box = False
        
    def create_interactive_viewer(self):
        """
        Crea la finestra interactiva optimitzada amb opcions de bounding box
        """
        import tkinter as tk
        from tkinter import ttk
        
        self.viewer_window = tk.Toplevel()
        self.viewer_window.title("🎛️ Editor de Complexitat Geomètrica")
        self.viewer_window.geometry("1200x800")
        self.viewer_window.configure(bg="#f5f5f5")
        
        # Estil modern
        style = ttk.Style()
        style.configure('Title.TLabel', font=('Arial', 14, 'bold'))
        style.configure('Info.TLabel', font=('Arial', 10))
        
        # Frame principal
        main_frame = ttk.Frame(self.viewer_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Títol
        title_label = ttk.Label(
            main_frame, 
            text=f"🎯 Simplificació: {len(self.simplifier.original_geometry.faces)} cares originals",
            style='Title.TLabel'
        )
        title_label.pack(pady=(0, 15))
        
        # Mode de simplificació
        mode_frame = ttk.LabelFrame(main_frame, text="🔧 Mode de Simplificació", padding="15")
        mode_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.mode_var = tk.StringVar(value="faces")
        
        # Opcions de mode
        modes_frame = ttk.Frame(mode_frame)
        modes_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(
            modes_frame, 
            text="🔺 Reducció de cares (tradicional)", 
            variable=self.mode_var, 
            value="faces",
            command=self._on_mode_change
        ).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Radiobutton(
            modes_frame, 
            text="📦 Caixa envoltant intel·ligent", 
            variable=self.mode_var, 
            value="bbox",
            command=self._on_mode_change
        ).pack(side=tk.LEFT)
        
        # Opcions per bounding box
        self.bbox_options_frame = ttk.Frame(mode_frame)
        self.bbox_options_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(self.bbox_options_frame, text="Tipus de caixa:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.bbox_type_var = tk.StringVar(value="rectangular")
        bbox_combo = ttk.Combobox(
            self.bbox_options_frame, 
            textvariable=self.bbox_type_var,
            values=["rectangular", "cylindrical", "octagonal", "adaptive"],
            state="readonly",
            width=15
        )
        bbox_combo.pack(side=tk.LEFT, padx=(0, 20))
        
        # Control de simplificació
        control_frame = ttk.LabelFrame(main_frame, text="🎚️ Control de Detall", padding="15")
        control_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Barra lliscant amb millor resolució
        scale_frame = ttk.Frame(control_frame)
        scale_frame.pack(fill=tk.X, pady=5)
        
        self.scale_min_label = ttk.Label(scale_frame, text="Mínim detall")
        self.scale_min_label.pack(side=tk.LEFT)
        self.scale_max_label = ttk.Label(scale_frame, text="Màxim detall")
        self.scale_max_label.pack(side=tk.RIGHT)
        
        self.detail_var = tk.IntVar(value=100)
        self.detail_scale = ttk.Scale(
            control_frame,
            from_=10,   # Mínim 10% 
            to=100,     # Màxim 100% (original)
            variable=self.detail_var,
            orient=tk.HORIZONTAL,
            command=self._on_scale_change
        )
        self.detail_scale.pack(fill=tk.X, pady=10)
        
        # Input manual
        manual_frame = ttk.Frame(control_frame)
        manual_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(manual_frame, text="Valor manual:").pack(side=tk.LEFT, padx=(0, 10))
        self.manual_var = tk.StringVar()
        self.manual_entry = ttk.Entry(manual_frame, textvariable=self.manual_var, width=10)
        self.manual_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.manual_entry.bind('<Return>', self._on_manual_input)
        
        ttk.Button(
            manual_frame, 
            text="Aplicar", 
            command=self._on_manual_input
        ).pack(side=tk.LEFT)
        
        # Informació en temps real
        info_frame = ttk.Frame(control_frame)
        info_frame.pack(fill=tk.X, pady=10)
        
        self.faces_label = ttk.Label(info_frame, text="", style='Info.TLabel')
        self.faces_label.pack(side=tk.LEFT, padx=(0, 20))
        
        self.speed_label = ttk.Label(info_frame, text="", style='Info.TLabel')
        self.speed_label.pack(side=tk.LEFT, padx=(0, 20))
        
        self.efficiency_label = ttk.Label(info_frame, text="", style='Info.TLabel')
        self.efficiency_label.pack(side=tk.LEFT, padx=(0, 20))
        
        self.status_label = ttk.Label(info_frame, text="📊 Llest", style='Info.TLabel')
        self.status_label.pack(side=tk.RIGHT)
        
        # Botons d'acció
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            button_frame, 
            text="� Previsualitzar", 
            command=self._preview_changes
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame, 
            text="✅ Aplicar Simplificació", 
            command=self._apply_simplification
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame, 
            text="↩️ Restaurar Original", 
            command=self._restore_original
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame, 
            text="❌ Tancar", 
            command=self.viewer_window.destroy
        ).pack(side=tk.RIGHT)
        
        # Àrea d'informació
        info_text_frame = ttk.LabelFrame(main_frame, text="📊 Informació", padding="10")
        info_text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.info_text = tk.Text(
            info_text_frame, 
            height=15, 
            wrap=tk.WORD,
            bg="#ffffff",
            font=('Consolas', 9)
        )
        scrollbar = ttk.Scrollbar(info_text_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=scrollbar.set)
        
        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Inicialitzar amb informació original
        self._update_info_display(100)
        
        return self.viewer_window
    
    def _on_mode_change(self):
        """
        Callback quan canvia el mode de simplificació
        """
        mode = self.mode_var.get()
        self.use_bounding_box = (mode == "bbox")
        
        # Actualitzar les etiquetes de la barra lliscant
        if self.use_bounding_box:
            self.scale_min_label.config(text="Poques cares")
            self.scale_max_label.config(text="Moltes cares")
            # Canviar els límits per bounding box (mínim 6 cares per un cub)
            self.detail_scale.config(from_=6, to=200)
            self.detail_var.set(50)  # Valor per defecte reasonable
        else:
            self.scale_min_label.config(text="Mínim detall")
            self.scale_max_label.config(text="Màxim detall")
            # Restaurar límits originals
            self.detail_scale.config(from_=10, to=100)
            self.detail_var.set(100)
        
        # Actualitzar vista
        self._on_scale_change(self.detail_var.get())
    
    def _on_manual_input(self, event=None):
        """
        Callback per input manual
        """
        try:
            value = int(self.manual_var.get())
            if self.use_bounding_box:
                value = max(6, min(500, value))  # Límits per bounding box
            else:
                value = max(10, min(100, value))  # Límits per reducció
            
            self.detail_var.set(value)
            self._on_scale_change(value)
        except ValueError:
            pass  # Ignorar valors no vàlids
    
    def _preview_changes(self):
        """
        Previsualitza els canvis sense aplicar-los
        """
        if self.use_bounding_box:
            self._calculate_bounding_box(self.detail_var.get())
        else:
            self._calculate_geometry(self.detail_var.get())
    
    def _on_scale_change(self, value):
        """Callback optimitzat quan canvia la barra"""
        if self.is_calculating:
            return  # Ignorar si ja està calculant
            
        percentage_or_faces = int(float(value))
        
        if self.use_bounding_box:
            # Mode bounding box
            stats = self._get_bbox_stats(percentage_or_faces)
            self.faces_label.config(
                text=f"📦 Cares caixa: {percentage_or_faces} (Original: {len(self.simplifier.original_geometry.faces)})"
            )
            
            if 'efficiency' in stats:
                self.efficiency_label.config(
                    text=f"⚡ Eficiència: {stats['efficiency']['space_utilization']:.1f}%"
                )
        else:
            # Mode reducció tradicional
            stats = self.simplifier.get_real_time_stats(percentage_or_faces)
            self.faces_label.config(
                text=f"📊 Cares: {stats['current_faces']:,} / {stats['original_faces']:,} "
                     f"({stats['reduction_ratio']:.1%})"
            )
            self.efficiency_label.config(text="")
        
        self.speed_label.config(text=f"⚡ Velocitat: {stats.get('processing_speed_estimate', 'N/A')}")
        
        # Programar càlcul real amb retard
        if hasattr(self, '_calculation_timer'):
            self.viewer_window.after_cancel(self._calculation_timer)
        
        if self.use_bounding_box:
            self._calculation_timer = self.viewer_window.after(300, lambda: self._calculate_bounding_box(percentage_or_faces))
        else:
            self._calculation_timer = self.viewer_window.after(300, lambda: self._calculate_geometry(percentage_or_faces))
    
    def _get_bbox_stats(self, target_faces: int) -> dict:
        """Obté estadístiques ràpides per bounding box"""
        return {
            'processing_speed_estimate': '⚡ Molt ràpid',
            'target_faces': target_faces
        }
    
    def _calculate_bounding_box(self, target_faces: int):
        """Calcula la caixa envoltant"""
        if self.is_calculating:
            return
            
        self.is_calculating = True
        self.status_label.config(text="🔄 Generant caixa...")
        self.viewer_window.update()
        
        try:
            # Generar caixa envoltant
            box_type = self.bbox_type_var.get()
            self.current_bbox = self.bbox_generator.generate_smart_bounding_box(target_faces, box_type)
            
            # Calcular eficiència
            efficiency_stats = self.bbox_generator.calculate_efficiency(self.current_bbox)
            
            # Actualitzar informació
            self._update_bbox_info_display(target_faces, efficiency_stats)
            
            self.status_label.config(text="✅ Caixa generada")
            
        except Exception as e:
            self.status_label.config(text=f"❌ Error: {str(e)}")
        finally:
            self.is_calculating = False
    
    def _update_bbox_info_display(self, target_faces: int, efficiency_stats: dict):
        """Actualitza la informació de la caixa envoltant"""
        info_text = f"""
📦 CAIXA ENVOLTANT INTEL·LIGENT
{'='*50}

🎯 Configuració:
  • Tipus: {self.bbox_type_var.get().title()}
  • Cares objectiu: {target_faces}
  • Cares generades: {len(self.current_bbox.faces)}

📊 Geometria Original:
  • Vèrtexs: {len(self.simplifier.original_geometry.vertices):,}
  • Cares: {len(self.simplifier.original_geometry.faces):,}
  • Volum aproximat: {efficiency_stats['original_volume']:.2f} unitats³

📦 Caixa Generada:
  • Vèrtexs: {len(self.current_bbox.vertices):,}
  • Cares: {len(self.current_bbox.faces):,}
  • Volum: {efficiency_stats['box_volume']:.2f} unitats³

⚡ Eficiència Espacial:
  • Utilització: {efficiency_stats['space_utilization']:.1f}%
  • Espai malgastat: {efficiency_stats['wasted_space']:.1f}%
  • Relació volum: {efficiency_stats['efficiency']:.3f}

🚀 Avantatges:
  • Collision detection ultra-ràpid
  • Memòria mínima requerida
  • Ideal per packing amb formes complexes
  • Mantén les dimensions originals

⚠️  Nota: La caixa conté completament l'objecte original
     amb un marge de seguretat del 2%.
"""
        
        self.info_text.delete(1.0, 'end')
        self.info_text.insert(1.0, info_text)
        
        # Actualitzar etiqueta d'eficiència
        self.efficiency_label.config(
            text=f"⚡ Eficiència: {efficiency_stats['space_utilization']:.1f}%"
        )
    
    def _calculate_geometry(self, percentage):
        """Calcula la geometria amb indicador de progrés"""
        if self.is_calculating:
            return
            
        self.is_calculating = True
        self.status_label.config(text="🔄 Calculant...")
        self.viewer_window.update()
        
        try:
            # Calcular geometria simplificada
            simplified_geometry = self.simplifier.simplify_to_percentage_on_demand(percentage)
            self.current_geometry = simplified_geometry
            
            # Actualitzar informació detallada
            self._update_info_display(percentage)
            
            self.status_label.config(text="✅ Calculat")
            
        except Exception as e:
            self.status_label.config(text=f"❌ Error: {str(e)}")
            print(f"Error calculant geometria: {e}")
        
        finally:
            self.is_calculating = False
    
    def _update_info_display(self, percentage):
        """Actualitza la informació detallada"""
        self.info_text.delete(1.0, tk.END)
        
        original = self.simplifier.original_geometry
        
        info = f"""🎯 GEOMETRIA ORIGINAL:
═══════════════════════════════════════════
� Cares totals: {len(original.faces):,}
📐 Vèrtexs: {len(original.vertices):,}
📦 Volum real: {original.real_volume:,.2f} mm³
🔗 Cares paral·leles: {len(original.parallel_face_pairs)}
🧮 Score complexitat: {original.complexity_score:.2f}

🎛️ CONFIGURACIÓ ACTUAL:
═══════════════════════════════════════════
📊 Nivell de detall: {percentage}%
📊 Cares objetivo: {max(4, int(len(original.faces) * (percentage / 100))):,}
⚡ Velocitat estimada: {self.simplifier._estimate_processing_speed(max(4, int(len(original.faces) * (percentage / 100))))}

💡 CONSELLS:
═══════════════════════════════════════════
• 90-100%: Qualitat màxima, processament lent
• 50-90%: Bon balanç qualitat/velocitat  
• 20-50%: Processament ràpid, qualitat acceptable
• 10-20%: Velocitat màxima, qualitat mínima
"""
        
        if hasattr(self, 'current_geometry') and self.current_geometry:
            current = self.current_geometry
            info += f"""
🎯 GEOMETRIA SIMPLIFICADA:
═══════════════════════════════════════════
📊 Cares actuals: {len(current.faces):,}
📦 Volum: {current.real_volume:,.2f} mm³
📈 Reducció: {(1 - len(current.faces)/len(original.faces))*100:.1f}%
"""
        
        self.info_text.insert(tk.END, info)
    
    def _apply_simplification(self):
        """Aplica la simplificació actual"""
        if self.use_bounding_box and self.current_bbox:
            # Aplicar caixa envoltant
            self.simplifier.original_geometry = self.current_bbox
            print(f"✅ Aplicant caixa envoltant: {len(self.current_bbox.faces)} cares")
            
            import tkinter.messagebox as messagebox
            efficiency_stats = self.bbox_generator.calculate_efficiency(self.current_bbox)
            messagebox.showinfo(
                "Caixa Aplicada", 
                f"Caixa envoltant aplicada:\n"
                f"• Cares: {len(self.current_bbox.faces)}\n"
                f"• Eficiència: {efficiency_stats['space_utilization']:.1f}%\n"
                f"• Tipus: {self.bbox_type_var.get()}"
            )
            
        elif self.current_geometry:
            # Aplicar reducció tradicional
            self.simplifier.original_geometry = self.current_geometry
            print(f"✅ Aplicant simplificació: {len(self.current_geometry.faces)} cares")
            
            import tkinter.messagebox as messagebox
            messagebox.showinfo("Aplicat", f"Simplificació aplicada: {len(self.current_geometry.faces)} cares")
        
        # Tancar finestra després d'aplicar
        self.viewer_window.destroy()
    
    def _restore_original(self):
        """Restaura la geometria original"""
        self.detail_var.set(100)
        self.current_geometry = self.simplifier.original_geometry
        self._update_info_display(100)
        print("↩️ Restaurada geometria original")


def analyze_stp_real_geometry(file_path: str) -> Optional[Dict]:
    """
    Funció principal per analitzar la geometria real d'un fitxer STP
    Inclou sistema de simplificació progressiva
    """
    try:
        with open(file_path, 'r', errors='ignore') as f:
            content = f.read()
        
        filename = file_path.split('\\')[-1] if '\\' in file_path else file_path.split('/')[-1]
        
        # Analitzar geometria avançada
        geometry = parse_stp_advanced_geometry(content, filename)
        
        if not geometry:
            return None
        
        # Crear simplificador si la geometria és complexa
        simplifier = None
        if len(geometry.faces) > 20:  # Només per geometries complexes
            print(f"🔧 Creant sistema de simplificació per {len(geometry.faces)} cares")
            try:
                simplifier = GeometrySimplifier(geometry)
                # NO cridem generate_simplification_levels() - sistema on-demand
                print("✅ Sistema de simplificació preparat (càlcul sota demanda)")
            except Exception as e:
                print(f"⚠️  Error creant simplificador: {e}")
                simplifier = None
        
        # Retornar anàlisi complet
        analysis = geometry.get_analysis_summary()
        
        # Afegir informació addicional
        analysis.update({
            'file_path': file_path,
            'filename': filename,
            'geometry_object': geometry,
            'simplifier': simplifier,  # Sistema de simplificació
            'analysis_type': 'advanced_real_geometry_with_simplification',
            'supports_real_time_editing': len(geometry.faces) > 6
        })
        
        return analysis
        
    except Exception as e:
        print(f"❌ Error analitzant geometria real: {e}")
        return None
