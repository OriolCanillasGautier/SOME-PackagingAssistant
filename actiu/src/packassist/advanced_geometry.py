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

# Import del nou sistema de simplificació
try:
    from .adaptive_mesh_simplifier import (
        AdaptiveMeshSimplifier, 
        MeshVisualizationWindow,
        create_mesh_simplification_interface,
        SimplifiedMesh
    )
    MESH_SIMPLIFICATION_AVAILABLE = True
    print("[OK] Sistema de simplificació de malla disponible")
except ImportError as e:
    MESH_SIMPLIFICATION_AVAILABLE = False
    print(f"⚠️ Sistema de simplificació no disponible: {e}")

# Flag per controlar debug output
DEBUG_MODE = False

def debug_print(message):
    """Print només si DEBUG_MODE està activat."""
    if DEBUG_MODE:
        print(message)

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
        
        # Nou: Sistema de simplificació adaptatiu
        self.mesh_simplifier: Optional['AdaptiveMeshSimplifier'] = None
        self.current_simplified_mesh: Optional['SimplifiedMesh'] = None
        self.simplification_levels: Dict[int, 'SimplifiedMesh'] = {}
        
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
                    
        debug_print(f"Detectades {len(self.parallel_face_pairs)} parelles de cares paral·leles")
    
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
    
    def initialize_mesh_simplification(self):
        """Inicialitza el sistema de simplificació de malla adaptatiu"""
        if not MESH_SIMPLIFICATION_AVAILABLE:
            debug_print("Sistema de simplificació no disponible")
            return False
        
        if len(self.vertices) < 20:
            debug_print("Geometria massa simple per simplificar")
            return False
        
        try:
            # Convertir cares a format de llista d'índexs
            face_indices = []
            for i, face in enumerate(self.faces):
                # Trobar índexs dels vèrtexs de cada cara
                vertex_indices = []
                for vertex in face.vertices:
                    try:
                        idx = self.vertices.index(vertex)
                        vertex_indices.append(idx)
                    except ValueError:
                        # Vèrtex no trobat, saltar aquesta cara
                        break
                
                if len(vertex_indices) >= 3:  # Mínim per una cara vàlida
                    face_indices.append(vertex_indices)
            
            if len(face_indices) < 4:  # Mínim per una forma 3D
                debug_print("No hi ha prou cares vàlides per simplificar")
                return False
            
            # Crear simplificador
            self.mesh_simplifier = AdaptiveMeshSimplifier(self.vertices, face_indices)
            
            print(f"🔧 Sistema de simplificació inicialitzat:")
            print(f"   📊 Vèrtexs: {len(self.vertices):,}")
            print(f"   🔷 Cares: {len(face_indices):,}")
            print(f"   💾 Volum: {self.real_volume:.2f} mm³")
            
            return True
            
        except Exception as e:
            print(f"❌ Error inicialitzant simplificació: {e}")
            return False
    
    def open_mesh_editor(self):
        """Obre l'editor visual de simplificació de malla"""
        if not self.mesh_simplifier:
            if not self.initialize_mesh_simplification():
                from tkinter import messagebox
                messagebox.showerror("Error", 
                                   "No es pot inicialitzar el sistema de simplificació\\n"
                                   "La geometria pot ser massa simple o hi ha un error.")
                return None
        
        try:
            # Crear interfície de visualització
            visualizer = MeshVisualizationWindow(self.mesh_simplifier)
            window = visualizer.create_window()
            
            print("🎮 Editor de malla obert")
            return visualizer
            
        except Exception as e:
            print(f"❌ Error obrint editor de malla: {e}")
            from tkinter import messagebox
            messagebox.showerror("Error", f"Error obrint editor de malla:\\n{str(e)}")
            return None
    
    def simplify_to_vertex_count(self, target_vertices: int, 
                               preserve_features: bool = True) -> bool:
        """
        Simplifica la geometria a un nombre específic de vèrtexs
        """
        if not self.mesh_simplifier:
            if not self.initialize_mesh_simplification():
                return False
        
        try:
            # Obtenir malla simplificada
            simplified = self.mesh_simplifier.simplify_to_vertex_count(
                target_vertices, preserve_features
            )
            
            self.current_simplified_mesh = simplified
            self.simplification_levels[target_vertices] = simplified
            
            print(f"✅ Geometria simplificada a {len(simplified.vertices)} vèrtexs")
            print(f"   📊 Qualitat volum: {simplified.volume_preservation:.1%}")
            print(f"   📐 Qualitat superfície: {simplified.surface_area_preservation:.1%}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error simplificant geometria: {e}")
            return False
    
    def get_simplified_mesh_info(self) -> Optional[Dict]:
        """Retorna informació de la malla simplificada actual"""
        if not self.current_simplified_mesh:
            return None
        
        mesh = self.current_simplified_mesh
        return {
            'vertices': len(mesh.vertices),
            'faces': len(mesh.faces),
            'original_vertices': mesh.original_vertex_count,
            'original_faces': mesh.original_face_count,
            'simplification_ratio': mesh.simplification_ratio,
            'volume_preservation': mesh.volume_preservation,
            'surface_area_preservation': mesh.surface_area_preservation,
            'vertex_reduction': (1 - mesh.simplification_ratio) * 100,
            'recommended_for_packing': mesh.simplification_ratio > 0.1 and mesh.volume_preservation > 0.7
        }
    
    def get_analysis_summary(self) -> Dict:
        """Retorna un resum complet de l'anàlisi geomètric"""
        summary = {
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
            'surface_area': sum(face.area for face in self.faces),
            
            # Nou: Informació de simplificació
            'supports_mesh_simplification': MESH_SIMPLIFICATION_AVAILABLE and len(self.vertices) >= 20,
            'mesh_simplifier_initialized': self.mesh_simplifier is not None,
            'current_simplified_mesh': self.get_simplified_mesh_info(),
            'available_simplification_levels': list(self.simplification_levels.keys()) if self.simplification_levels else []
        }
        
        return summary


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
            return None
        
        # Convertir a coordenades flotants
        vertices = [(float(p[0]), float(p[1]), float(p[2])) for p in points]
        unique_vertices = list(set(vertices))  # Eliminar duplicats
        
        # Detectar cares des de ADVANCED_FACE o FACE_BOUND
        faces_pattern = r'ADVANCED_FACE\s*\([^)]+\)'
        face_matches = re.findall(faces_pattern, stp_content)
        
        # Si tenim molts punts, crear cares aproximades
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
        
        debug_print(f"Geometria analitzada: {len(geometry.faces)} cares, {len(geometry.vertices)} vèrtexs")
        
        return geometry
        
    except Exception as e:
        print(f"Error en anàlisi avançada de geometria: {e}")
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
            
        print("Calculant importància de cares...")
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
        print(f"Importància calculada per {len(importance_scores)} cares")
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
        
        print(f"Simplificant a {percentage}% ({target_faces} cares)...")
        
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
        
        print(f"Simplificat a {len(simplified.faces)} cares")
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
            return "Molt lent"
        elif face_count > 500:
            return "Lent"
        elif face_count > 100:
            return "Moderat"
        elif face_count > 50:
            return "Ràpid"
        else:
            return "Molt ràpid"


class RealTimeGeometryViewer:
    """
    Visualitzador en temps real optimitzat
    """
    
    def __init__(self, geometry_simplifier: GeometrySimplifier):
        self.simplifier = geometry_simplifier
        self.current_geometry = None
        self.viewer_window = None
        self.is_calculating = False
        
    def create_interactive_viewer(self):
        """
        Crea la finestra interactiva optimitzada
        """
        import tkinter as tk
        from tkinter import ttk
        
        self.viewer_window = tk.Toplevel()
        self.viewer_window.title("Editor de Complexitat Geomètrica")
        self.viewer_window.geometry("1000x700")
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
            text=f"Simplificació: {len(self.simplifier.original_geometry.faces)} cares originals",
            style='Title.TLabel'
        )
        title_label.pack(pady=(0, 15))
        
        # Control de simplificació
        control_frame = ttk.LabelFrame(main_frame, text="Control de Detall", padding="15")
        control_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Barra lliscant amb millor resolució
        scale_frame = ttk.Frame(control_frame)
        scale_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(scale_frame, text="Mínim detall").pack(side=tk.LEFT)
        ttk.Label(scale_frame, text="Màxim detall").pack(side=tk.RIGHT)
        
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
        
        # Informació en temps real
        info_frame = ttk.Frame(control_frame)
        info_frame.pack(fill=tk.X, pady=10)
        
        self.faces_label = ttk.Label(info_frame, text="", style='Info.TLabel')
        self.faces_label.pack(side=tk.LEFT, padx=(0, 20))
        
        self.speed_label = ttk.Label(info_frame, text="", style='Info.TLabel')
        self.speed_label.pack(side=tk.LEFT, padx=(0, 20))
        
        self.status_label = ttk.Label(info_frame, text="Llest", style='Info.TLabel')
        self.status_label.pack(side=tk.RIGHT)
        
        # Botons d'acció
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            button_frame, 
            text="Aplicar Simplificació", 
            command=self._apply_simplification
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame, 
            text="Restaurar Original", 
            command=self._restore_original
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame, 
            text="Tancar", 
            command=self.viewer_window.destroy
        ).pack(side=tk.RIGHT)
        
        # Àrea d'informació
        info_text_frame = ttk.LabelFrame(main_frame, text="Informació", padding="10")
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
    
    def _on_scale_change(self, value):
        """Callback optimitzat quan canvia la barra"""
        if self.is_calculating:
            return  # Ignorar si ja està calculant
            
        percentage = int(float(value))
        
        # Actualitzar estadístiques ràpides
        stats = self.simplifier.get_real_time_stats(percentage)
        
        # Actualitzar labels instantàniament
        self.faces_label.config(
            text=f"Cares: {stats['current_faces']:,} / {stats['original_faces']:,} "
                 f"({stats['reduction_ratio']:.1%})"
        )
        
        self.speed_label.config(text=f"Velocitat: {stats['processing_speed_estimate']}")
        
        # Programar càlcul real amb retard per evitar càlculs innecessaris
        if hasattr(self, '_calculation_timer'):
            self.viewer_window.after_cancel(self._calculation_timer)
        
        self._calculation_timer = self.viewer_window.after(300, lambda: self._calculate_geometry(percentage))
    
    def _calculate_geometry(self, percentage):
        """Calcula la geometria amb indicador de progrés"""
        if self.is_calculating:
            return
            
        self.is_calculating = True
        self.status_label.config(text="Calculant...")
        self.viewer_window.update()
        
        try:
            # Calcular geometria simplificada
            simplified_geometry = self.simplifier.simplify_to_percentage_on_demand(percentage)
            self.current_geometry = simplified_geometry
            
            # Actualitzar informació detallada
            self._update_info_display(percentage)
            
            self.status_label.config(text="Calculat")
            
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}")
            print(f"Error calculant geometria: {e}")
        
        finally:
            self.is_calculating = False
    
    def _update_info_display(self, percentage):
        """Actualitza la informació detallada"""
        self.info_text.delete(1.0, tk.END)
        
        original = self.simplifier.original_geometry
        
        info = f"""GEOMETRIA ORIGINAL:
═══════════════════════════════════════════
Cares totals: {len(original.faces):,}
Vèrtexs: {len(original.vertices):,}
Volum real: {original.real_volume:,.2f} mm³
Cares paral·leles: {len(original.parallel_face_pairs)}
Score complexitat: {original.complexity_score:.2f}

CONFIGURACIÓ ACTUAL:
═══════════════════════════════════════════
Nivell de detall: {percentage}%
Cares objetivo: {max(4, int(len(original.faces) * (percentage / 100))):,}
Velocitat estimada: {self.simplifier._estimate_processing_speed(max(4, int(len(original.faces) * (percentage / 100))))}

CONSELLS:
═══════════════════════════════════════════
• 90-100%: Qualitat màxima, processament lent
• 50-90%: Bon balanç qualitat/velocitat  
• 20-50%: Processament ràpid, qualitat acceptable
• 10-20%: Velocitat màxima, qualitat mínima
"""
        
        if hasattr(self, 'current_geometry') and self.current_geometry:
            current = self.current_geometry
            info += f"""
GEOMETRIA SIMPLIFICADA:
═══════════════════════════════════════════
Cares actuals: {len(current.faces):,}
Volum: {current.real_volume:,.2f} mm³
Reducció: {(1 - len(current.faces)/len(original.faces))*100:.1f}%
"""
        
        self.info_text.insert(tk.END, info)
    
    def _apply_simplification(self):
        """Aplica la simplificació actual"""
        if self.current_geometry:
            # TODO: Integrar amb el sistema principal
            print(f"Aplicant simplificació: {len(self.current_geometry.faces)} cares")
            messagebox.showinfo("Aplicat", f"Simplificació aplicada: {len(self.current_geometry.faces)} cares")
    
    def _restore_original(self):
        """Restaura la geometria original"""
        self.detail_var.set(100)
        self.current_geometry = self.simplifier.original_geometry
        self._update_info_display(100)
        print("Restaurada geometria original")


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
            print(f"Creant sistema de simplificació per {len(geometry.faces)} cares")
            try:
                simplifier = GeometrySimplifier(geometry)
                # NO cridem generate_simplification_levels() - sistema on-demand
                print("Sistema de simplificació preparat (càlcul sota demanda)")
            except Exception as e:
                print(f"Error creant simplificador: {e}")
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
        print(f"Error analitzant geometria real: {e}")
        return None


def create_mesh_simplification_demo(vertices: List[Tuple[float, float, float]], 
                                  faces_data: List[List[int]]) -> Optional['MeshVisualizationWindow']:
    """
    Funció de demostració per crear directament l'editor de malla
    Útil per proves i integració ràpida
    """
    if not MESH_SIMPLIFICATION_AVAILABLE:
        print("❌ Sistema de simplificació de malla no disponible")
        return None
    
    try:
        print("🔧 Creant demo de simplificació de malla...")
        
        # Crear simplificador directament
        simplifier = AdaptiveMeshSimplifier(vertices, faces_data)
        
        # Crear visualitzador
        visualizer = MeshVisualizationWindow(simplifier)
        window = visualizer.create_window()
        
        print("✅ Demo de simplificació llest!")
        return visualizer
        
    except Exception as e:
        print(f"❌ Error creant demo: {e}")
        return None


def open_mesh_editor_for_stp(file_path: str) -> Optional['MeshVisualizationWindow']:
    """
    Obre l'editor de malla directament per un fitxer STP
    """
    try:
        print(f"🔍 Analitzant {file_path} per simplificació...")
        
        # Analitzar geometria
        analysis = analyze_stp_real_geometry(file_path)
        if not analysis:
            print("❌ No s'ha pogut analitzar la geometria")
            return None
        
        geometry_obj = analysis.get('geometry_object')
        if not geometry_obj:
            print("❌ No s'ha trobat objecte de geometria")
            return None
        
        # Obrir editor
        return geometry_obj.open_mesh_editor()
        
    except Exception as e:
        print(f"❌ Error obrint editor per STP: {e}")
        return None


# Funcions d'utilitat per integració amb el sistema principal
def get_simplified_geometry_for_packing(complex_geometry: 'ComplexGeometry', 
                                      max_vertices: int = 500) -> Optional[Dict]:
    """
    Retorna una geometria simplificada optimitzada per bin packing
    """
    if not complex_geometry.mesh_simplifier:
        if not complex_geometry.initialize_mesh_simplification():
            return None
    
    # Simplificar mantenint característiques
    success = complex_geometry.simplify_to_vertex_count(max_vertices, preserve_features=True)
    if not success:
        return None
    
    mesh_info = complex_geometry.get_simplified_mesh_info()
    if not mesh_info or not mesh_info['recommended_for_packing']:
        print("⚠️ La malla simplificada pot no ser adequada per packing")
    
    # Retornar dades en format compatible amb el sistema de packing
    simplified_mesh = complex_geometry.current_simplified_mesh
    
    return {
        'vertices': simplified_mesh.vertices,
        'faces': [[int(idx) for idx in face] for face in simplified_mesh.faces],
        'bounding_box': complex_geometry.bounding_box,
        'volume': simplified_mesh.volume_preservation * complex_geometry.real_volume,
        'quality_metrics': {
            'vertex_reduction': mesh_info['vertex_reduction'],
            'volume_preservation': mesh_info['volume_preservation'],
            'surface_preservation': mesh_info['surface_area_preservation'],
            'recommended': mesh_info['recommended_for_packing']
        },
        'packing_hints': {
            'complexity_level': 'simplified',
            'collision_detection': 'mesh_based',
            'rotation_support': True,
            'interlocking_possible': len(complex_geometry.parallel_face_pairs) > 0
        }
    }


def create_mesh_editor_button_for_gui(parent_widget, geometry_object: 'ComplexGeometry'):
    """
    Crea un botó per obrir l'editor de malla en una GUI existent
    """
    import tkinter as tk
    from tkinter import ttk
    
    def open_editor():
        try:
            visualizer = geometry_object.open_mesh_editor()
            if visualizer:
                print("🎮 Editor de malla obert des de GUI")
        except Exception as e:
            print(f"❌ Error obrint editor: {e}")
    
    # Verificar si es pot usar
    can_simplify = (
        MESH_SIMPLIFICATION_AVAILABLE and 
        len(geometry_object.vertices) >= 20
    )
    
    if can_simplify:
        button_text = f"Simplificar Malla ({len(geometry_object.vertices):,} vèrtexs)"
        button_state = tk.NORMAL
    else:
        button_text = "Simplificació no disponible"
        button_state = tk.DISABLED
    
    button = ttk.Button(
        parent_widget,
        text=button_text,
        command=open_editor,
        state=button_state
    )
    
    return button
