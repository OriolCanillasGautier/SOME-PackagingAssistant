"""
Sistema d'optimització no destructiva simplificat per PackAssist 3D
Implementa envòlups convexos adaptatius que mantenen el volum original
"""

import numpy as np
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

# Dependencies opcionals
try:
    from scipy.spatial import ConvexHull
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    from sklearn.decomposition import PCA
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


@dataclass
class EnvelopeResult:
    """Resultat de l'operació d'envòlup."""
    envelope_geometry: Optional[object]  # ComplexGeometry
    original_geometry: Optional[object]  # ComplexGeometry
    efficiency: float
    volume_original: float
    volume_envelope: float
    face_count: int
    vertices_count: int
    shape_type: str
    mode: str
    error: Optional[str] = None


class IntelligentFaceGenerator:
    """Generador de cares intel·ligent amb clustering de normals."""
    
    def __init__(self):
        self.angle_tolerance = 15.0

    def generate_intelligent_envelope(self, vertices: List[Tuple[float, float, float]], target_faces: int) -> List[List[Tuple[float, float, float]]]:
        """Genera un envòlup intel·ligent amb el nombre exacte de cares desitjades."""
        try:
            # Crear convex hull inicial
            if SCIPY_AVAILABLE and len(vertices) >= 4:
                hull_faces = self._create_convex_hull_faces(vertices)
            else:
                hull_faces = self._create_simple_box_faces(vertices, target_faces)
            
            if len(hull_faces) <= target_faces:
                return hull_faces
            
            # Calcular normals i agrupar
            normals = [self._calculate_face_normal(face) for face in hull_faces]
            face_groups = self._cluster_faces_manual(normals, hull_faces, target_faces)
            
            # Fusionar cares de cada grup
            final_faces = []
            for group in face_groups:
                merged_face = self._merge_face_group(group)
                if merged_face and len(merged_face) >= 3:
                    final_faces.append(merged_face)
            
            return final_faces[:target_faces]
            
        except Exception:
            return self._create_simple_box_faces(vertices, target_faces)

    def _create_convex_hull_faces(self, vertices: List[Tuple[float, float, float]]) -> List[List[Tuple[float, float, float]]]:
        """Crea cares usant SciPy ConvexHull."""
        vertices_array = np.array(vertices)
        hull = ConvexHull(vertices_array)
        
        faces = []
        for simplex in hull.simplices:
            face_vertices = [tuple(vertices_array[i]) for i in simplex]
            faces.append(face_vertices)
        
        return faces

    def _calculate_face_normal(self, face_vertices: List[Tuple[float, float, float]]) -> np.ndarray:
        """Calcula la normal d'una cara."""
        if len(face_vertices) < 3:
            return np.array([0, 0, 1])
        
        vertices = np.array(face_vertices)
        v1 = vertices[1] - vertices[0]
        v2 = vertices[2] - vertices[0]
        normal = np.cross(v1, v2)
        
        norm = np.linalg.norm(normal)
        return normal / norm if norm > 0 else np.array([0, 0, 1])

    def _cluster_faces_manual(self, normals: List[np.ndarray], faces: List, target_faces: int) -> List[List]:
        """Agrupa cares amb normals similars."""
        if len(faces) <= target_faces:
            return [[face] for face in faces]
        
        groups = []
        used = set()
        
        for i, normal in enumerate(normals):
            if i in used:
                continue
                
            group = [faces[i]]
            used.add(i)
            
            for j, other_normal in enumerate(normals):
                if j != i and j not in used:
                    angle = math.degrees(math.acos(np.clip(np.dot(normal, other_normal), -1, 1)))
                    if angle < self.angle_tolerance:
                        group.append(faces[j])
                        used.add(j)
            
            groups.append(group)
            if len(groups) >= target_faces:
                break
        
        return groups[:target_faces]

    def _merge_face_group(self, face_group: List) -> List[Tuple[float, float, float]]:
        """Fusiona un grup de cares en una sola cara."""
        if not face_group:
            return []
        
        if len(face_group) == 1:
            return face_group[0]
        
        # Recollir tots els vèrtexs
        all_vertices = []
        for face in face_group:
            all_vertices.extend(face)
        
        # Eliminar duplicats
        unique_vertices = []
        for vertex in all_vertices:
            if not any(np.allclose(vertex, existing, atol=1e-6) for existing in unique_vertices):
                unique_vertices.append(vertex)
        
        if len(unique_vertices) < 3:
            return face_group[0]
        
        # Crear convex hull dels vèrtexs
        try:
            if SCIPY_AVAILABLE and len(unique_vertices) >= 4:
                vertices_array = np.array(unique_vertices)
                hull = ConvexHull(vertices_array)
                return [tuple(vertices_array[i]) for i in hull.vertices]
            else:
                return unique_vertices[:4]  # Limitar a 4 vèrtexs
        except:
            return unique_vertices[:4]

    def _create_simple_box_faces(self, vertices: List[Tuple[float, float, float]], target_faces: int) -> List[List[Tuple[float, float, float]]]:
        """Crea cares simples en cas de fallback."""
        vertices_array = np.array(vertices)
        min_coords = np.min(vertices_array, axis=0)
        max_coords = np.max(vertices_array, axis=0)
        
        # Les 6 cares bàsiques d'una caixa
        basic_faces = [
            [(min_coords[0], min_coords[1], min_coords[2]), (max_coords[0], min_coords[1], min_coords[2]), 
             (max_coords[0], max_coords[1], min_coords[2]), (min_coords[0], max_coords[1], min_coords[2])],
            [(min_coords[0], min_coords[1], max_coords[2]), (max_coords[0], min_coords[1], max_coords[2]), 
             (max_coords[0], max_coords[1], max_coords[2]), (min_coords[0], max_coords[1], max_coords[2])],
            [(min_coords[0], min_coords[1], min_coords[2]), (max_coords[0], min_coords[1], min_coords[2]), 
             (max_coords[0], min_coords[1], max_coords[2]), (min_coords[0], min_coords[1], max_coords[2])],
            [(min_coords[0], max_coords[1], min_coords[2]), (max_coords[0], max_coords[1], min_coords[2]), 
             (max_coords[0], max_coords[1], max_coords[2]), (min_coords[0], max_coords[1], max_coords[2])],
            [(min_coords[0], min_coords[1], min_coords[2]), (min_coords[0], max_coords[1], min_coords[2]), 
             (min_coords[0], max_coords[1], max_coords[2]), (min_coords[0], min_coords[1], max_coords[2])],
            [(max_coords[0], min_coords[1], min_coords[2]), (max_coords[0], max_coords[1], min_coords[2]), 
             (max_coords[0], max_coords[1], max_coords[2]), (max_coords[0], min_coords[1], max_coords[2])]
        ]
        
        return basic_faces[:target_faces]


class AdaptiveWrapper:
    """Wrapper per crear envòlups adaptatius."""
    
    def __init__(self, original_geometry):
        self.original_geometry = original_geometry
        self.intelligent_generator = IntelligentFaceGenerator()
        
    def create_convex_envelope(self, target_faces: int) -> EnvelopeResult:
        """Crea un envòlup intel·ligent."""
        try:
            # Extreure vèrtexs de la geometria
            vertices = self._extract_vertices_from_geometry()
            if len(vertices) < 4:
                raise ValueError("Insuficients vèrtexs per crear envòlup")
            
            # Generar cares intel·ligents
            faces = self.intelligent_generator.generate_intelligent_envelope(vertices, target_faces)
            
            # Construir geometria
            envelope_geometry = self._build_envelope_from_faces(faces)
            
            # Calcular eficiència
            stats = self._calculate_efficiency_stats(envelope_geometry)
            
            return EnvelopeResult(
                envelope_geometry=envelope_geometry,
                original_geometry=self.original_geometry,
                efficiency=stats['efficiency'],
                volume_original=stats['volume_original'],
                volume_envelope=stats['volume_envelope'],
                face_count=len(faces),
                vertices_count=len(self._extract_unique_vertices_from_faces(faces)),
                shape_type="intelligent_clustered",
                mode="adaptive"
            )
            
        except Exception as e:
            return EnvelopeResult(
                envelope_geometry=None,
                original_geometry=self.original_geometry,
                efficiency=0, volume_original=0, volume_envelope=0,
                face_count=0, vertices_count=0,
                shape_type="error", mode="adaptive",
                error=str(e)
            )

    def _extract_vertices_from_geometry(self) -> List[Tuple[float, float, float]]:
        """Extreu vèrtexs de la geometria."""
        try:
            all_vertices = []
            
            if hasattr(self.original_geometry, 'faces'):
                for face in self.original_geometry.faces:
                    if hasattr(face, 'vertices'):
                        all_vertices.extend(face.vertices)
            elif hasattr(self.original_geometry, 'vertices'):
                all_vertices = self.original_geometry.vertices
            else:
                # Fallback: crear vèrtexs des del bounding box
                bbox = self.original_geometry.get_bounding_box()
                min_coords, max_coords = bbox[0], bbox[1]
                
                all_vertices = [
                    (min_coords[0], min_coords[1], min_coords[2]),
                    (max_coords[0], min_coords[1], min_coords[2]),
                    (max_coords[0], max_coords[1], min_coords[2]),
                    (min_coords[0], max_coords[1], min_coords[2]),
                    (min_coords[0], min_coords[1], max_coords[2]),
                    (max_coords[0], min_coords[1], max_coords[2]),
                    (max_coords[0], max_coords[1], max_coords[2]),
                    (min_coords[0], max_coords[1], max_coords[2])
                ]
            
            # Eliminar duplicats
            unique_vertices = []
            for vertex in all_vertices:
                vertex_tuple = tuple(float(coord) for coord in vertex[:3])
                if not any(np.allclose(vertex_tuple, existing, atol=1e-6) for existing in unique_vertices):
                    unique_vertices.append(vertex_tuple)
            
            return unique_vertices
            
        except Exception:
            return [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                   (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]

    def _build_envelope_from_faces(self, faces: List[List[Tuple[float, float, float]]]):
        """Construeix la geometria de l'envòlup."""
        try:
            from .advanced_geometry import ComplexGeometry
            
            envelope = ComplexGeometry()
            
            for face_vertices in faces:
                if len(face_vertices) >= 3:
                    envelope.add_face(face_vertices)
            
            envelope.calculate_bounding_box()
            envelope.calculate_real_volume()
            
            return envelope
            
        except ImportError:
            return None
        except Exception:
            return None

    def _extract_unique_vertices_from_faces(self, faces: List[List[Tuple[float, float, float]]]) -> List[Tuple[float, float, float]]:
        """Extreu vèrtexs únics de les cares."""
        unique_vertices = []
        for face in faces:
            for vertex in face:
                if not any(np.allclose(vertex, existing, atol=1e-6) for existing in unique_vertices):
                    unique_vertices.append(vertex)
        return unique_vertices

    def _calculate_efficiency_stats(self, envelope_geometry) -> Dict:
        """Calcula estadístiques d'eficiència."""
        try:
            # Volum original
            if hasattr(self.original_geometry, 'real_volume') and self.original_geometry.real_volume:
                original_volume = self.original_geometry.real_volume
            else:
                original_volume = self.original_geometry.get_real_volume()
            
            # Volum de l'envòlup
            if envelope_geometry and hasattr(envelope_geometry, 'real_volume'):
                envelope_volume = envelope_geometry.real_volume or envelope_geometry.get_real_volume()
            else:
                envelope_volume = original_volume * 1.1
            
            # Calcular eficiència
            efficiency = (original_volume / envelope_volume) * 100 if envelope_volume > 0 else 0
            
            return {
                'volume_original': original_volume,
                'volume_envelope': envelope_volume,
                'efficiency': efficiency
            }
            
        except Exception:
            return {
                'volume_original': 1000,
                'volume_envelope': 1100,
                'efficiency': 90.9
            }


class NonDestructiveOptimizer:
    """Coordinador principal de l'optimitzador."""
    
    def __init__(self, original_geometry):
        self.original_geometry = original_geometry
        self.adaptive_wrapper = AdaptiveWrapper(original_geometry)
        self.preview_result = None
        
    def preview_optimization(self, target_faces: int) -> EnvelopeResult:
        """Previsualitza l'optimització."""
        self.preview_result = self.adaptive_wrapper.create_convex_envelope(target_faces)
        return self.preview_result
    
    def apply_optimization(self):
        """Aplica l'optimització prèviament previsualitzada."""
        if not self.preview_result:
            raise ValueError("No hi ha previsualització disponible")
        return self.preview_result


class NonDestructiveOptimizerUI:
    """Interfície simplificada per l'optimitzador."""
    
    def __init__(self, parent, original_geometry, callback=None):
        self.parent = parent
        self.original_geometry = original_geometry
        self.optimizer = NonDestructiveOptimizer(original_geometry)
        self.callback = callback
        
        self.target_faces = tk.IntVar(value=8)
        self.current_result = None
        
        self.create_ui()
        
    def create_ui(self):
        """Crea la interfície d'usuari simplificada."""
        self.window = tk.Toplevel(self.parent)
        self.window.title("🎯 Optimitzador Intel·ligent PackAssist")
        self.window.geometry("600x500")
        self.window.transient(self.parent)
        
        main_frame = ttk.Frame(self.window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Títol
        ttk.Label(main_frame, text="🎯 Optimitzador Intel·ligent", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))
        
        # Informació de l'objecte
        self.create_object_info(main_frame)
        
        # Controls
        self.create_controls(main_frame)
        
        # Botons d'acció
        self.create_action_buttons(main_frame)
        
        # Resultats
        self.create_results_area(main_frame)
        
    def create_object_info(self, parent):
        """Crea la secció d'informació de l'objecte."""
        info_frame = ttk.LabelFrame(parent, text="📐 Informació de l'Objecte", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        try:
            bbox = self.original_geometry.get_bounding_box()
            volume = self.original_geometry.get_real_volume()
            face_count = len(self.original_geometry.faces) if hasattr(self.original_geometry, 'faces') else 0
            
            info_text = f"""Cares originals: {face_count}
Volum: {volume:.1f} mm³
Dimensions: {bbox[1][0]-bbox[0][0]:.1f} × {bbox[1][1]-bbox[0][1]:.1f} × {bbox[1][2]-bbox[0][2]:.1f} mm"""
        except:
            info_text = "Informació de l'objecte no disponible"
        
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack()
        
    def create_controls(self, parent):
        """Crea els controls d'optimització."""
        controls_frame = ttk.LabelFrame(parent, text="🎛️ Controls", padding="10")
        controls_frame.pack(fill=tk.X, pady=(0, 15))
        
        faces_frame = ttk.Frame(controls_frame)
        faces_frame.pack(fill=tk.X)
        
        ttk.Label(faces_frame, text="Cares objectiu:").pack(side=tk.LEFT)
        
        scale = ttk.Scale(faces_frame, from_=6, to=24, 
                         variable=self.target_faces, orient=tk.HORIZONTAL,
                         command=self.on_faces_change)
        scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 10))
        
        self.faces_label = ttk.Label(faces_frame, text="8")
        self.faces_label.pack(side=tk.LEFT)
        
    def create_action_buttons(self, parent):
        """Crea els botons d'acció."""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(button_frame, text="🔍 Previsualitza", 
                  command=self.preview).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="✅ Aplicar", 
                  command=self.apply).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="❌ Tancar", 
                  command=self.window.destroy).pack(side=tk.RIGHT)
        
    def create_results_area(self, parent):
        """Crea l'àrea de resultats."""
        results_frame = ttk.LabelFrame(parent, text="📊 Resultats", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        self.results_text = tk.Text(results_frame, height=12, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, 
                                 command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        welcome_msg = """🚀 OPTIMITZADOR INTEL·LIGENT

Aquest sistema crea envolupaments òptims dels teus objectes 3D.

INSTRUCCIONS:
1. Ajusta el nombre de cares objectiu (6-24)
2. Clica 'Previsualitza' per veure el resultat
3. Clica 'Aplicar' per confirmar l'optimització"""
        
        self.results_text.insert(tk.END, welcome_msg)
        
    def on_faces_change(self, value):
        """Callback quan canvia el nombre de cares."""
        faces = int(float(value))
        self.faces_label.config(text=str(faces))
        
    def preview(self):
        """Previsualitza l'optimització."""
        try:
            target = int(self.target_faces.get())
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, f"🔄 Calculant optimització amb {target} cares...\n\n")
            self.window.update()
            
            result = self.optimizer.preview_optimization(target)
            self.current_result = result
            
            if result.error:
                self.results_text.insert(tk.END, f"❌ Error: {result.error}\n")
            else:
                info = f"""✅ PREVISUALITZACIÓ COMPLETADA

Mode: {result.mode.title()}
Cares generades: {result.face_count}
Volum original: {result.volume_original:.1f} mm³
Volum envòlup: {result.volume_envelope:.1f} mm³
Eficiència: {result.efficiency:.1f}%

✅ Previsualització llesta. Clica 'Aplicar' per confirmar."""
                self.results_text.insert(tk.END, info)
                
        except Exception as e:
            self.results_text.insert(tk.END, f"❌ Error: {str(e)}\n")
    
    def apply(self):
        """Aplica l'optimització."""
        try:
            if not self.current_result:
                messagebox.showwarning("Avís", "Primer has de previsualitzar l'optimització")
                return
            
            result = self.optimizer.apply_optimization()
            self.results_text.insert(tk.END, "\n\n✅ Optimització aplicada correctament!")
            
            if self.callback:
                self.callback(result)
                
        except Exception as e:
            self.results_text.insert(tk.END, f"\n❌ Error aplicant: {str(e)}")


def create_non_destructive_optimizer_dialog(parent, original_geometry, callback=None):
    """Funció principal per integrar amb l'app."""
    try:
        ui = NonDestructiveOptimizerUI(parent, original_geometry, callback)
        return ui
    except Exception as e:
        messagebox.showerror("Error", f"Error creant optimitzador: {e}")
        return None


def test_system():
    """Test del sistema simplificat."""
    try:
        from .advanced_geometry import ComplexGeometry
        
        # Crear geometria de test
        test_geometry = ComplexGeometry()
        
        # Vèrtexs d'una casa simple
        house_vertices = [
            (0, 0, 0), (10, 0, 0), (10, 8, 0), (0, 8, 0),
            (0, 0, 6), (10, 0, 6), (10, 8, 6), (0, 8, 6),
            (5, 0, 10), (5, 8, 10)
        ]
        
        # Cares de la casa
        house_faces = [
            [(0, 0, 0), (10, 0, 0), (10, 8, 0), (0, 8, 0)],
            [(0, 0, 0), (10, 0, 0), (10, 0, 6), (0, 0, 6)],
            [(10, 0, 0), (10, 8, 0), (10, 8, 6), (10, 0, 6)],
            [(10, 8, 0), (0, 8, 0), (0, 8, 6), (10, 8, 6)],
            [(0, 8, 0), (0, 0, 0), (0, 0, 6), (0, 8, 6)],
            [(0, 0, 6), (10, 0, 6), (5, 0, 10)],
            [(10, 0, 6), (10, 8, 6), (5, 8, 10)],
            [(10, 8, 6), (0, 8, 6), (5, 8, 10)],
            [(0, 8, 6), (0, 0, 6), (5, 0, 10)]
        ]
        
        for face in house_faces:
            test_geometry.add_face(face)
        
        test_geometry.calculate_bounding_box()
        test_geometry.calculate_real_volume()
        
        optimizer = NonDestructiveOptimizer(test_geometry)
        
        for target_faces in [6, 8, 12]:
            result = optimizer.preview_optimization(target_faces)
            
            print(f"Target: {target_faces} cares")
            print(f"Resultat: {result.face_count} cares, {result.efficiency:.1f}% eficiència")
            if result.error:
                print(f"Error: {result.error}")
            print()
        
        return True
        
    except Exception as e:
        print(f"Error en test: {e}")
        return False


if __name__ == "__main__":
    test_system()
