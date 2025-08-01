"""
Sistema Avançat de Simplificació de Malla per PackAssist
Implementa algoritmes de remeshing adaptatiu per reduir complexitat geomètrica
mantenint la forma original (no conversió a rectangles)
"""

import numpy as np
import math
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import time
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

@dataclass
class SimplifiedMesh:
    """Representa una malla simplificada"""
    vertices: List[Tuple[float, float, float]]
    faces: List[List[int]]  # Índexs de vèrtexs per cada cara
    original_vertex_count: int
    original_face_count: int
    simplification_ratio: float
    volume_preservation: float
    surface_area_preservation: float

class AdaptiveMeshSimplifier:
    """
    Sistema de simplificació adaptatiu que manté la forma original
    Utilitza tècniques similars a OpenFOAM però optimitzades per bin packing
    """
    
    def __init__(self, original_vertices: List[Tuple[float, float, float]], 
                 original_faces: List[List[int]]):
        self.original_vertices = np.array(original_vertices)
        self.original_faces = original_faces
        self.original_volume = self._calculate_volume()
        self.original_surface_area = self._calculate_surface_area()
        
        # Cache per diferents nivells de simplificació
        self.simplified_meshes = {}
        
        print(f"🔬 Mesh original: {len(self.original_vertices)} vèrtexs, {len(self.original_faces)} cares")
        print(f"📦 Volum original: {self.original_volume:.2f} mm³")
        print(f"📐 Superfície original: {self.original_surface_area:.2f} mm²")

    def simplify_to_vertex_count(self, target_vertices: int, 
                               preserve_features: bool = True) -> SimplifiedMesh:
        """
        Simplifica la malla a un nombre específic de vèrtexs mantenint la forma
        """
        # Verificar cache
        cache_key = f"{target_vertices}_{preserve_features}"
        if cache_key in self.simplified_meshes:
            return self.simplified_meshes[cache_key]
        
        print(f"🔄 Simplificant a {target_vertices} vèrtexs...")
        start_time = time.time()
        
        # Assegurar mínim de vèrtexs per una forma 3D
        target_vertices = max(target_vertices, 8)
        
        if target_vertices >= len(self.original_vertices):
            # No cal simplificar
            simplified = SimplifiedMesh(
                vertices=[(v[0], v[1], v[2]) for v in self.original_vertices],
                faces=self.original_faces.copy(),
                original_vertex_count=len(self.original_vertices),
                original_face_count=len(self.original_faces),
                simplification_ratio=1.0,
                volume_preservation=1.0,
                surface_area_preservation=1.0
            )
            self.simplified_meshes[cache_key] = simplified
            return simplified
        
        # Algoritme de simplificació adaptatiu
        simplified_vertices, simplified_faces = self._adaptive_simplification(
            target_vertices, preserve_features
        )
        
        # Calcular mètriques de qualitat
        simplified_volume = self._calculate_volume_from_mesh(simplified_vertices, simplified_faces)
        simplified_surface = self._calculate_surface_area_from_mesh(simplified_vertices, simplified_faces)
        
        simplified = SimplifiedMesh(
            vertices=[(v[0], v[1], v[2]) for v in simplified_vertices],
            faces=simplified_faces,
            original_vertex_count=len(self.original_vertices),
            original_face_count=len(self.original_faces),
            simplification_ratio=target_vertices / len(self.original_vertices),
            volume_preservation=simplified_volume / self.original_volume if self.original_volume > 0 else 0,
            surface_area_preservation=simplified_surface / self.original_surface_area if self.original_surface_area > 0 else 0
        )
        
        # Guardar al cache
        self.simplified_meshes[cache_key] = simplified
        
        process_time = time.time() - start_time
        print(f"✅ Simplificació completada en {process_time:.2f}s")
        print(f"   📊 Vèrtexs: {len(simplified.vertices)} ({simplified.simplification_ratio:.1%})")
        print(f"   📦 Preservació volum: {simplified.volume_preservation:.1%}")
        print(f"   📐 Preservació superfície: {simplified.surface_area_preservation:.1%}")
        
        return simplified

    def _adaptive_simplification(self, target_vertices: int, 
                                preserve_features: bool) -> Tuple[np.ndarray, List[List[int]]]:
        """
        Algoritme principal de simplificació adaptatiu
        """
        current_vertices = self.original_vertices.copy()
        current_faces = [face.copy() for face in self.original_faces]
        
        # 1. Detectar característiques importants (arestes, cantonades)
        important_vertices = set()
        if preserve_features:
            important_vertices = self._detect_feature_vertices(current_vertices, current_faces)
            print(f"🎯 Detectades {len(important_vertices)} característiques importants")
        
        # 2. Calcular importància de cada vèrtex
        vertex_importance = self._calculate_vertex_importance(current_vertices, current_faces, important_vertices)
        
        # 3. Simplificació iterativa
        while len(current_vertices) > target_vertices:
            # Trobar el vèrtex menys important que es pot eliminar
            removable_vertex = self._find_least_important_removable_vertex(
                current_vertices, current_faces, vertex_importance, important_vertices
            )
            
            if removable_vertex is None:
                print("⚠️ No es poden eliminar més vèrtexs sense trencar la topologia")
                break
            
            # Eliminar vèrtex i retriangular la zona
            current_vertices, current_faces = self._remove_vertex_and_retriangulate(
                current_vertices, current_faces, removable_vertex
            )
            
            # Actualitzar importància si cal
            if len(current_vertices) % 100 == 0:  # Recalcular cada 100 vèrtexs
                vertex_importance = self._calculate_vertex_importance(
                    current_vertices, current_faces, important_vertices
                )
        
        return current_vertices, current_faces

    def _detect_feature_vertices(self, vertices: np.ndarray, 
                               faces: List[List[int]]) -> set:
        """
        Detecta vèrtexs que representen característiques importants de la forma
        """
        important = set()
        
        # 1. Vèrtexs en arestes pronunciades (angle gran entre cares adjacents)
        vertex_normals = self._calculate_vertex_normals(vertices, faces)
        
        for i, vertex in enumerate(vertices):
            # Trobar cares que contenen aquest vèrtex
            adjacent_faces = [face for face in faces if i in face]
            
            if len(adjacent_faces) < 2:
                continue
            
            # Calcular angles entre cares adjacents
            max_angle = 0
            for j, face1 in enumerate(adjacent_faces):
                for face2 in adjacent_faces[j+1:]:
                    normal1 = self._calculate_face_normal(vertices, face1)
                    normal2 = self._calculate_face_normal(vertices, face2)
                    
                    dot_product = np.clip(np.dot(normal1, normal2), -1, 1)
                    angle = math.acos(abs(dot_product))
                    max_angle = max(max_angle, angle)
            
            # Si l'angle és gran, és una aresta important
            if max_angle > math.pi / 3:  # 60 graus
                important.add(i)
        
        # 2. Vèrtexs extrems (bounding box)
        bbox_vertices = self._find_bounding_box_vertices(vertices)
        important.update(bbox_vertices)
        
        return important

    def _calculate_vertex_importance(self, vertices: np.ndarray, 
                                   faces: List[List[int]], 
                                   important_vertices: set) -> np.ndarray:
        """
        Calcula la importància de cada vèrtex per decidir l'ordre d'eliminació
        """
        importance = np.zeros(len(vertices))
        
        for i, vertex in enumerate(vertices):
            score = 0.0
            
            # 1. Vèrtexs marcats com importants tenen prioritat màxima
            if i in important_vertices:
                score += 1000.0
            
            # 2. Curvatura local (més curvatura = més important)
            local_curvature = self._calculate_local_curvature(vertices, faces, i)
            score += local_curvature * 100.0
            
            # 3. Distància al centre (vèrtexs exteriors més importants)
            center = np.mean(vertices, axis=0)
            distance_to_center = np.linalg.norm(vertex - center)
            max_distance = np.max([np.linalg.norm(v - center) for v in vertices])
            if max_distance > 0:
                score += (distance_to_center / max_distance) * 50.0
            
            # 4. Connectivitat (vèrtexs amb moltes connexions més importants)
            connectivity = len([face for face in faces if i in face])
            score += connectivity * 10.0
            
            importance[i] = score
        
        return importance

    def _find_least_important_removable_vertex(self, vertices: np.ndarray, 
                                             faces: List[List[int]], 
                                             importance: np.ndarray,
                                             protected: set) -> Optional[int]:
        """
        Troba el vèrtex menys important que es pot eliminar sense trencar la topologia
        """
        # Ordenar vèrtexs per importància (menys important primer)
        vertex_indices = list(range(len(vertices)))
        vertex_indices.sort(key=lambda i: importance[i])
        
        for vertex_idx in vertex_indices:
            if vertex_idx in protected:
                continue
            
            # Verificar si es pot eliminar sense trencar la topologia
            if self._can_remove_vertex(vertices, faces, vertex_idx):
                return vertex_idx
        
        return None

    def _can_remove_vertex(self, vertices: np.ndarray, 
                          faces: List[List[int]], vertex_idx: int) -> bool:
        """
        Verifica si un vèrtex es pot eliminar sense trencar la topologia
        """
        # Trobar cares que contenen aquest vèrtex
        containing_faces = [i for i, face in enumerate(faces) if vertex_idx in face]
        
        if len(containing_faces) < 3:
            return True  # Vèrtex poc connectat, es pot eliminar
        
        # Verificar que la zona resultant es pot retriangular correctament
        neighbor_vertices = set()
        for face_idx in containing_faces:
            face = faces[face_idx]
            for v in face:
                if v != vertex_idx:
                    neighbor_vertices.add(v)
        
        # Si té molts veïns, pot ser complicat retriangular
        if len(neighbor_vertices) > 8:
            return False
        
        return True

    def _remove_vertex_and_retriangulate(self, vertices: np.ndarray, 
                                       faces: List[List[int]], 
                                       vertex_idx: int) -> Tuple[np.ndarray, List[List[int]]]:
        """
        Elimina un vèrtex i retriangula la zona afectada
        """
        # Trobar cares que contenen el vèrtex
        containing_faces = [i for i, face in enumerate(faces) if vertex_idx in face]
        
        # Obtenir vèrtexs veïns
        neighbor_vertices = set()
        for face_idx in containing_faces:
            face = faces[face_idx]
            for v in face:
                if v != vertex_idx:
                    neighbor_vertices.add(v)
        
        neighbor_list = list(neighbor_vertices)
        
        # Eliminar cares que contenen el vèrtex
        new_faces = [face for i, face in enumerate(faces) if i not in containing_faces]
        
        # Retriangular la zona buida
        if len(neighbor_list) >= 3:
            # Ordenar veïns per posició angular per crear triangulació coherent
            center = np.mean([vertices[v] for v in neighbor_list], axis=0)
            neighbor_list.sort(key=lambda v: math.atan2(
                vertices[v][1] - center[1], vertices[v][0] - center[0]
            ))
            
            # Crear triangles en ventall
            for i in range(len(neighbor_list) - 2):
                new_triangle = [neighbor_list[0], neighbor_list[i+1], neighbor_list[i+2]]
                new_faces.append(new_triangle)
        
        # Eliminar el vèrtex i reindexar
        new_vertices = np.delete(vertices, vertex_idx, axis=0)
        
        # Actualitzar índexs en les cares
        for face in new_faces:
            for i, v in enumerate(face):
                if v > vertex_idx:
                    face[i] = v - 1
        
        return new_vertices, new_faces

    def _calculate_local_curvature(self, vertices: np.ndarray, 
                                 faces: List[List[int]], vertex_idx: int) -> float:
        """
        Calcula la curvatura local en un vèrtex
        """
        # Trobar cares adjacents
        adjacent_faces = [face for face in faces if vertex_idx in face]
        
        if len(adjacent_faces) < 2:
            return 0.0
        
        # Calcular normals de cares adjacents
        normals = []
        for face in adjacent_faces:
            normal = self._calculate_face_normal(vertices, face)
            normals.append(normal)
        
        # Calcular variància de normals com a mesura de curvatura
        if len(normals) < 2:
            return 0.0
        
        mean_normal = np.mean(normals, axis=0)
        curvature = np.mean([np.linalg.norm(normal - mean_normal) for normal in normals])
        
        return curvature

    def _calculate_face_normal(self, vertices: np.ndarray, face: List[int]) -> np.ndarray:
        """Calcula la normal d'una cara"""
        if len(face) < 3:
            return np.array([0, 0, 1])
        
        v1 = vertices[face[1]] - vertices[face[0]]
        v2 = vertices[face[2]] - vertices[face[0]]
        normal = np.cross(v1, v2)
        
        norm = np.linalg.norm(normal)
        if norm > 0:
            normal = normal / norm
        
        return normal

    def _calculate_vertex_normals(self, vertices: np.ndarray, 
                                faces: List[List[int]]) -> List[np.ndarray]:
        """Calcula normals per cada vèrtex"""
        vertex_normals = [np.zeros(3) for _ in vertices]
        
        for face in faces:
            face_normal = self._calculate_face_normal(vertices, face)
            for vertex_idx in face:
                vertex_normals[vertex_idx] += face_normal
        
        # Normalitzar
        for i, normal in enumerate(vertex_normals):
            norm = np.linalg.norm(normal)
            if norm > 0:
                vertex_normals[i] = normal / norm
        
        return vertex_normals

    def _find_bounding_box_vertices(self, vertices: np.ndarray) -> set:
        """Troba vèrtexs que formen el bounding box"""
        important = set()
        
        # Extrems en cada eix
        for axis in range(3):
            min_idx = np.argmin(vertices[:, axis])
            max_idx = np.argmax(vertices[:, axis])
            important.add(min_idx)
            important.add(max_idx)
        
        return important

    def _calculate_volume(self) -> float:
        """Calcula el volum de la malla original"""
        return self._calculate_volume_from_mesh(self.original_vertices, self.original_faces)

    def _calculate_volume_from_mesh(self, vertices: np.ndarray, 
                                  faces: List[List[int]]) -> float:
        """Calcula volum d'una malla per triangulació"""
        total_volume = 0.0
        origin = np.array([0, 0, 0])
        
        for face in faces:
            if len(face) >= 3:
                # Calcular volum del tetraedre origin-v1-v2-v3 per cada triangle
                for i in range(len(face) - 2):
                    v1 = vertices[face[0]]
                    v2 = vertices[face[i+1]]
                    v3 = vertices[face[i+2]]
                    
                    # Volum tetraedre = |det(v1,v2,v3)| / 6
                    volume = abs(np.dot(v1, np.cross(v2, v3))) / 6.0
                    total_volume += volume
        
        return abs(total_volume)

    def _calculate_surface_area(self) -> float:
        """Calcula l'àrea de superfície de la malla original"""
        return self._calculate_surface_area_from_mesh(self.original_vertices, self.original_faces)

    def _calculate_surface_area_from_mesh(self, vertices: np.ndarray, 
                                        faces: List[List[int]]) -> float:
        """Calcula àrea de superfície d'una malla"""
        total_area = 0.0
        
        for face in faces:
            if len(face) >= 3:
                # Calcular àrea per triangulació
                for i in range(len(face) - 2):
                    v1 = vertices[face[0]]
                    v2 = vertices[face[i+1]]
                    v3 = vertices[face[i+2]]
                    
                    # Àrea triangle = 0.5 * |cross product|
                    area = 0.5 * np.linalg.norm(np.cross(v2 - v1, v3 - v1))
                    total_area += area
        
        return total_area


class MeshVisualizationWindow:
    """
    Finestra de visualització 3D amb controls de simplificació en temps real
    """
    
    def __init__(self, mesh_simplifier: AdaptiveMeshSimplifier):
        self.simplifier = mesh_simplifier
        self.current_mesh = None
        self.window = None
        self.figure = None
        self.ax = None
        self.canvas = None
        
        # Controls
        self.vertex_count_var = None
        self.preserve_features_var = None
        
        # Estado
        self.is_updating = False
        self.update_timer = None

    def create_window(self):
        """Crea la finestra de visualització amb controls"""
        self.window = tk.Toplevel()
        self.window.title("Simplificació de Malla Adaptatiu - PackAssist Pro")
        self.window.geometry("1400x800")
        
        # Frame principal
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Panel de controls (esquerra)
        controls_frame = self._create_controls_panel(main_frame)
        controls_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Panel de visualització (dreta)
        viz_frame = self._create_visualization_panel(main_frame)
        viz_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Inicialitzar amb malla original
        self._update_visualization(len(self.simplifier.original_vertices))
        
        return self.window

    def _create_controls_panel(self, parent):
        """Crea el panel de controls"""
        frame = ttk.LabelFrame(parent, text="Controls de Simplificació", padding="15")
        frame.configure(width=350)
        
        # Informació original
        info_frame = ttk.LabelFrame(frame, text="Malla Original", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        original_info = f"""Vèrtexs: {len(self.simplifier.original_vertices):,}
Cares: {len(self.simplifier.original_faces):,}
Volum: {self.simplifier.original_volume:.2f} mm³
Superfície: {self.simplifier.original_surface_area:.2f} mm²"""
        
        ttk.Label(info_frame, text=original_info, 
                 font=('Consolas', 9)).pack(anchor=tk.W)
        
        # Control de nombre de vèrtexs
        vertex_frame = ttk.LabelFrame(frame, text="Nombre de Vèrtexs Objectiu", padding="10")
        vertex_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Barra lliscant logarítmica per millor control
        self.vertex_count_var = tk.IntVar(value=len(self.simplifier.original_vertices))
        
        # Etiquetes de rang
        range_frame = ttk.Frame(vertex_frame)
        range_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(range_frame, text="8 vèrtexs", font=('Arial', 8)).pack(side=tk.LEFT)
        ttk.Label(range_frame, text=f"{len(self.simplifier.original_vertices):,} vèrtexs", 
                 font=('Arial', 8)).pack(side=tk.RIGHT)
        
        # Barra lliscant amb escala logarítmica
        self.vertex_scale = ttk.Scale(
            vertex_frame,
            from_=8,
            to=len(self.simplifier.original_vertices),
            variable=self.vertex_count_var,
            orient=tk.HORIZONTAL,
            command=self._on_vertex_count_change
        )
        self.vertex_scale.pack(fill=tk.X, pady=5)
        
        # Display del valor actual
        self.vertex_display = ttk.Label(vertex_frame, 
                                       text=f"Actual: {self.vertex_count_var.get():,} vèrtexs",
                                       font=('Arial', 10, 'bold'))
        self.vertex_display.pack(pady=5)
        
        # Botons de preset
        preset_frame = ttk.Frame(vertex_frame)
        preset_frame.pack(fill=tk.X, pady=5)
        
        presets = [
            ("Ultra detall (90%)", 0.9),
            ("Alt detall (70%)", 0.7),
            ("Detall mitjà (50%)", 0.5),
            ("Baix detall (25%)", 0.25),
            ("Mínim (100 vèrtexs)", 100)
        ]
        
        for text, ratio in presets:
            if isinstance(ratio, float):
                target = int(len(self.simplifier.original_vertices) * ratio)
            else:
                target = ratio
            
            btn = ttk.Button(preset_frame, text=text,
                           command=lambda t=target: self._set_vertex_count(t))
            btn.pack(fill=tk.X, pady=1)
        
        # Opcions avançades
        options_frame = ttk.LabelFrame(frame, text="Opcions Avançades", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Preservar característiques - ja definit a sobre
        # self.preserve_features_var = tk.BooleanVar(value=True)
        preserve_check = ttk.Checkbutton(options_frame, 
                                       text="Preservar característiques geomètriques",
                                       variable=self.preserve_features_var,
                                       command=self._on_options_change)
        preserve_check.pack(anchor=tk.W, pady=2)
        
        # Control de transparència
        transparency_frame = ttk.LabelFrame(frame, text="Visualització", padding="10")
        transparency_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Transparència de l'envelope
        ttk.Label(transparency_frame, text="Transparència envelope:").pack(anchor=tk.W)
        self.transparency_var = tk.DoubleVar(value=0.7)
        self.transparency_scale = ttk.Scale(
            transparency_frame,
            from_=0.1,
            to=1.0,
            variable=self.transparency_var,
            orient=tk.HORIZONTAL,
            command=self._on_transparency_change
        )
        self.transparency_scale.pack(fill=tk.X, pady=2)
        
        # Mostrar objecte interior
        self.show_interior_var = tk.BooleanVar(value=True)
        interior_check = ttk.Checkbutton(transparency_frame,
                                       text="Mostrar objecte interior (si disponible)",
                                       variable=self.show_interior_var,
                                       command=self._on_visualization_change)
        interior_check.pack(anchor=tk.W, pady=2)
        
        # Mode de visualització
        viz_mode_frame = ttk.Frame(transparency_frame)
        viz_mode_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(viz_mode_frame, text="Mode:").pack(side=tk.LEFT)
        self.viz_mode_var = tk.StringVar(value="envelope")
        viz_modes = [("Només envelope", "envelope"), 
                    ("Envelope + interior", "both"), 
                    ("Comparació", "comparison")]
        
        for text, mode in viz_modes:
            ttk.Radiobutton(viz_mode_frame, text=text, variable=self.viz_mode_var,
                           value=mode, command=self._on_visualization_change).pack(anchor=tk.W)
        options_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.preserve_features_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, 
                       text="Preservar característiques importants",
                       variable=self.preserve_features_var,
                       command=self._on_options_change).pack(anchor=tk.W)
        
        # Informació de la malla actual
        self.current_info_frame = ttk.LabelFrame(frame, text="Malla Actual", padding="10")
        self.current_info_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.current_info_label = ttk.Label(self.current_info_frame, 
                                           text="Carregant...",
                                           font=('Consolas', 9))
        self.current_info_label.pack(anchor=tk.W)
        
        # Botons d'acció
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(button_frame, text="Aplicar Simplificació",
                  command=self._apply_simplification).pack(fill=tk.X, pady=2)
        
        ttk.Button(button_frame, text="Exportar Malla",
                  command=self._export_mesh).pack(fill=tk.X, pady=2)
        
        ttk.Button(button_frame, text="Restaurar Original",
                  command=self._restore_original).pack(fill=tk.X, pady=2)
        
        ttk.Button(button_frame, text="Tancar",
                  command=self.window.destroy).pack(fill=tk.X, pady=2)
        
        return frame

    def _create_visualization_panel(self, parent):
        """Crea el panel de visualització 3D"""
        frame = ttk.LabelFrame(parent, text="Visualització 3D", padding="10")
        
        # Crear figura matplotlib
        self.figure = Figure(figsize=(10, 8), dpi=100)
        self.ax = self.figure.add_subplot(111, projection='3d')
        
        # Canvas
        self.canvas = FigureCanvasTkAgg(self.figure, frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Toolbar
        toolbar_frame = ttk.Frame(frame)
        toolbar_frame.pack(fill=tk.X, pady=(5, 0))
        
        from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
        toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        toolbar.update()
        
        return frame

    def _on_vertex_count_change(self, value):
        """Callback quan canvia el nombre de vèrtexs"""
        vertex_count = int(float(value))
        self.vertex_display.config(text=f"Actual: {vertex_count:,} vèrtexs")
        
        # Programar actualització amb retard per evitar càlculs excessius
        if self.update_timer:
            self.window.after_cancel(self.update_timer)
        
        self.update_timer = self.window.after(500, lambda: self._update_visualization(vertex_count))

    def _on_options_change(self):
        """Callback quan canvien les opcions"""
        if not self.is_updating:
            vertex_count = self.vertex_count_var.get()
            self._update_visualization(vertex_count)

    def _set_vertex_count(self, target):
        """Estableix un nombre específic de vèrtexs"""
        self.vertex_count_var.set(target)
        self._update_visualization(target)

    def _update_visualization(self, vertex_count):
        """Actualitza la visualització amb la nova malla"""
        if self.is_updating:
            return
        
        self.is_updating = True
        self.current_info_label.config(text="Calculant...")
        self.window.update()
        
        try:
            # Simplificar malla
            preserve_features = self.preserve_features_var.get()
            self.current_mesh = self.simplifier.simplify_to_vertex_count(
                vertex_count, preserve_features
            )
            
            # Actualitzar visualització 3D
            self._draw_mesh_3d()
            
            # Actualitzar informació
            self._update_current_info()
            
        except Exception as e:
            print(f"Error actualitzant visualització: {e}")
            self.current_info_label.config(text=f"Error: {str(e)}")
        
        finally:
            self.is_updating = False

    def _draw_mesh_3d(self):
        """Dibuixa la malla en 3D amb transparència i objecte interior"""
        self.ax.clear()
        
        if not self.current_mesh:
            return
        
        vertices = np.array(self.current_mesh.vertices)
        faces = self.current_mesh.faces
        
        # Obtenir mode de visualització i transparència
        transparency = getattr(self, 'transparency_var', None)
        alpha = transparency.get() if transparency else 0.7
        
        viz_mode = getattr(self, 'viz_mode_var', None)
        mode = viz_mode.get() if viz_mode else "envelope"
        
        show_interior = getattr(self, 'show_interior_var', None)
        show_interior_flag = show_interior.get() if show_interior else False
        
        # 1. Dibuixar objecte interior si està disponible i activat
        if show_interior_flag and mode in ["both", "comparison"]:
            self._draw_interior_object()
        
        # 2. Dibuixar envelope principal
        if mode in ["envelope", "both", "comparison"]:
            # Crear col·lecció de polígons 3D
            polygons = []
            for face in faces:
                if len(face) >= 3:
                    polygon = [vertices[i] for i in face]
                    polygons.append(polygon)
            
            # Color segons la qualitat
            quality = self.current_mesh.volume_preservation
            if quality > 0.9:
                color = '#2ECC71'  # Verd (excel·lent)
            elif quality > 0.7:
                color = '#F39C12'  # Taronja (bo)
            elif quality > 0.5:
                color = '#E74C3C'  # Vermell (acceptable)
            else:
                color = '#8E44AD'  # Morat (mínim)
            
            # Configurar transparència segons el mode
            if mode == "envelope":
                envelope_alpha = max(0.3, alpha)  # Mínim 30% per veure la forma
            else:
                envelope_alpha = alpha  # Usar valor del slider
            
            poly3d = Poly3DCollection(polygons, alpha=envelope_alpha, 
                                     facecolor=color, edgecolor='#2C3E50', 
                                     linewidth=0.8 if mode == "envelope" else 0.5)
            self.ax.add_collection3d(poly3d)
        
        # Configurar eixos
        if len(vertices) > 0:
            # Ajustar límits
            margin = 0.1
            x_range = [vertices[:, 0].min(), vertices[:, 0].max()]
            y_range = [vertices[:, 1].min(), vertices[:, 1].max()]
            z_range = [vertices[:, 2].min(), vertices[:, 2].max()]
            
            x_margin = (x_range[1] - x_range[0]) * margin
            y_margin = (y_range[1] - y_range[0]) * margin
            z_margin = (z_range[1] - z_range[0]) * margin
            
            self.ax.set_xlim(x_range[0] - x_margin, x_range[1] + x_margin)
            self.ax.set_ylim(y_range[0] - y_margin, y_range[1] + y_margin)
            self.ax.set_zlim(z_range[0] - z_margin, z_range[1] + z_margin)
        
        # Etiquetes
        self.ax.set_xlabel('X (mm)')
        self.ax.set_ylabel('Y (mm)')
        self.ax.set_zlabel('Z (mm)')
        
        # Títol amb informació
        reduction = (1 - self.current_mesh.simplification_ratio) * 100
        self.ax.set_title(f'Malla Simplificada - {len(vertices):,} vèrtexs\\n'
                         f'Reducció: {reduction:.1f}% | Qualitat: {quality:.1%}')
        
        # Actualitzar canvas
        self.canvas.draw()

    def _draw_interior_object(self):
        """Dibuixa l'objecte interior simulat per verificar que cap dins l'envelope"""
        # Simular punts de l'objecte interior (això hauria de venir dels test meshes)
        # Per ara creem una aproximació basada en la malla actual
        vertices = np.array(self.current_mesh.vertices)
        
        if len(vertices) == 0:
            return
        
        # Calcular centre i dimensions de l'envelope
        center = np.mean(vertices, axis=0)
        x_range = vertices[:, 0].max() - vertices[:, 0].min()
        y_range = vertices[:, 1].max() - vertices[:, 1].min()
        z_range = vertices[:, 2].max() - vertices[:, 2].min()
        
        # Crear objecte interior simulat (70% de la mida de l'envelope)
        scale_factor = 0.7
        interior_points = []
        
        # Objecte 1: caixa irregular
        n_points = 20
        for i in range(n_points):
            x = center[0] + (np.random.random() - 0.5) * x_range * scale_factor
            y = center[1] + (np.random.random() - 0.5) * y_range * scale_factor
            z = center[2] + (np.random.random() - 0.5) * z_range * scale_factor
            interior_points.append([x, y, z])
        
        # Objecte 2: forma cilíndrica
        n_cylinder = 15
        radius = min(x_range, y_range) * scale_factor * 0.3
        for i in range(n_cylinder):
            angle = 2 * np.pi * i / n_cylinder
            x = center[0] + radius * np.cos(angle)
            y = center[1] + radius * np.sin(angle)
            z = center[2] + (np.random.random() - 0.5) * z_range * scale_factor
            interior_points.append([x, y, z])
        
        interior_points = np.array(interior_points)
        
        # Dibuixar punts interiors
        self.ax.scatter(interior_points[:, 0], interior_points[:, 1], interior_points[:, 2],
                       c='red', s=20, alpha=0.8, marker='o', label='Objecte interior')
        
        # Dibuixar wireframe de connexions entre punts propers
        for i, point1 in enumerate(interior_points):
            for j, point2 in enumerate(interior_points[i+1:], i+1):
                dist = np.linalg.norm(point1 - point2)
                if dist < max(x_range, y_range, z_range) * 0.3:  # Només connexions curtes
                    self.ax.plot([point1[0], point2[0]], 
                               [point1[1], point2[1]], 
                               [point1[2], point2[2]], 
                               'r-', alpha=0.3, linewidth=0.5)

    def _on_transparency_change(self, event=None):
        """Handler per canvis de transparència"""
        if not self.is_updating:
            self._draw_mesh_3d()

    def _on_visualization_change(self, event=None):
        """Handler per canvis de mode de visualització"""
        if not self.is_updating:
            self._draw_mesh_3d()

    def _on_options_change(self, event=None):
        """Handler per canvis d'opcions avançades"""
        if not self.is_updating:
            # Recalcular amb les noves opcions
            current_target = self.vertex_count_var.get()
            self._update_visualization(current_target)

    def _update_current_info(self):
        """Actualitza la informació de la malla actual"""
        if not self.current_mesh:
            return
        
        reduction = (1 - self.current_mesh.simplification_ratio) * 100
        
        info = f"""Vèrtexs: {len(self.current_mesh.vertices):,} (-{reduction:.1f}%)
Cares: {len(self.current_mesh.faces):,}
Preservació volum: {self.current_mesh.volume_preservation:.1%}
Preservació superfície: {self.current_mesh.surface_area_preservation:.1%}
Ratio simplificació: {self.current_mesh.simplification_ratio:.1%}"""
        
        self.current_info_label.config(text=info)

    def _apply_simplification(self):
        """Aplica la simplificació actual al sistema principal"""
        if self.current_mesh:
            # TODO: Integrar amb el sistema principal de PackAssist
            print(f"Aplicant malla simplificada: {len(self.current_mesh.vertices)} vèrtexs")
            from tkinter import messagebox
            messagebox.showinfo("Aplicat", 
                               f"Malla simplificada aplicada:\\n"
                               f"• Vèrtexs: {len(self.current_mesh.vertices):,}\\n"
                               f"• Qualitat: {self.current_mesh.volume_preservation:.1%}")

    def _export_mesh(self):
        """Exporta la malla simplificada"""
        if self.current_mesh:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".obj",
                filetypes=[("OBJ files", "*.obj"), ("STL files", "*.stl")],
                title="Exportar malla simplificada"
            )
            if filename:
                # TODO: Implementar exportació
                print(f"Exportant a {filename}")

    def _restore_original(self):
        """Restaura la malla original"""
        self.vertex_count_var.set(len(self.simplifier.original_vertices))
        self._update_visualization(len(self.simplifier.original_vertices))


def create_mesh_simplification_interface(vertices: List[Tuple[float, float, float]], 
                                       faces: List[List[int]]) -> MeshVisualizationWindow:
    """
    Funció principal per crear la interfície de simplificació de malla
    """
    print("🔧 Creant sistema de simplificació de malla...")
    
    # Crear simplificador
    simplifier = AdaptiveMeshSimplifier(vertices, faces)
    
    # Crear interfície de visualització
    visualizer = MeshVisualizationWindow(simplifier)
    window = visualizer.create_window()
    
    print("✅ Sistema de simplificació llest!")
    return visualizer


# Funció d'integració amb advanced_geometry.py
def integrate_with_advanced_geometry():
    """
    Integra el sistema de simplificació amb el mòdul advanced_geometry
    """
    # Aquesta funció s'anirà trucant des de advanced_geometry.py
    pass
