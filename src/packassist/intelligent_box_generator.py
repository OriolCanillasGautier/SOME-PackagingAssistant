"""
Generador Intel·ligent de Caixes Personalitzades
=================================================

Implementa l'algorisme per crear caixes amb un nombre específic de cares
que s'adaptin perfectament a objectes 3D complexos.

Basat en:
1. Convex Hull inicial
2. Clustering de normals amb K-means
3. Fusió intel·ligent de cares
4. Construcció de politop optimitzat
"""

import numpy as np
import trimesh
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize
from scipy.spatial import ConvexHull
import logging
from typing import Tuple, List, Optional, Dict, Any
from dataclasses import dataclass

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BoxGenerationResult:
    """Resultat de la generació de caixa personalitzada."""
    vertices: np.ndarray
    faces: np.ndarray
    volume: float
    surface_area: float
    face_count: int
    efficiency: float
    original_volume: float
    box_volume: float

class IntelligentBoxGenerator:
    """
    Generador intel·ligent de caixes personalitzades que s'adapten
    perfectament a objectes 3D complexos.
    """
    
    def __init__(self, debug_mode: bool = False):
        """
        Inicialitza el generador.
        
        Args:
            debug_mode: Si True, mostra informació de debug detallada
        """
        self.debug_mode = debug_mode
        self.logger = logger
        
    def generate_custom_box(
        self, 
        geometry_object: Any, 
        target_faces: int = 6,
        quality_factor: float = 1.0,
        handle_concavities: bool = True
    ) -> BoxGenerationResult:
        """
        Genera una caixa personalitzada per a un objecte 3D.
        
        Args:
            geometry_object: Objecte 3D (STL/STP)
            target_faces: Nombre de cares desitjades per la caixa
            quality_factor: Factor de qualitat (0.1-2.0)
            handle_concavities: Si gestionar concavitats automàticament
            
        Returns:
            BoxGenerationResult amb la caixa generada
        """
        try:
            self.logger.info(f"🎯 Generant caixa personalitzada amb {target_faces} cares")
            
            # 1. Extreure punts de l'objecte
            points = self._extract_points_from_geometry(geometry_object)
            if len(points) == 0:
                raise ValueError("No s'han pogut extreure punts de l'objecte")
                
            original_volume = self._calculate_original_volume(geometry_object)
            
            # 2. Detectar si l'objecte té concavitats
            is_concave = self._detect_concavities(points) if handle_concavities else False
            
            if is_concave:
                self.logger.info("🔍 Objecte amb concavitats detectades - Usant estratègia avançada")
                result = self._generate_box_for_concave_object(
                    geometry_object, points, target_faces, quality_factor
                )
            else:
                self.logger.info("📦 Objecte convex - Usant estratègia estàndard")
                result = self._generate_box_standard(
                    points, target_faces, quality_factor
                )
            
            # 3. Afegir informació del volum original
            result.original_volume = original_volume
            result.efficiency = (original_volume / result.box_volume) * 100
            
            self.logger.info(f"✅ Caixa generada: {result.face_count} cares, eficiència {result.efficiency:.1f}%")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error generant caixa personalitzada: {e}")
            raise
    
    def _extract_points_from_geometry(self, geometry_object: Any) -> np.ndarray:
        """
        Extreu punts de l'objecte geomètric.
        
        Args:
            geometry_object: Objecte 3D
            
        Returns:
            Array de punts 3D
        """
        try:
            if hasattr(geometry_object, 'vertices'):
                # Objecte trimesh
                return np.array(geometry_object.vertices)
            elif hasattr(geometry_object, 'Vertices'):
                # Objecte CadQuery/FreeCAD
                vertices = []
                for vertex in geometry_object.Vertices():
                    vertices.append([vertex.X, vertex.Y, vertex.Z])
                return np.array(vertices)
            elif hasattr(geometry_object, 'points'):
                # Array de punts directe
                return np.array(geometry_object.points)
            else:
                # Intentar conversió automàtica
                return self._try_automatic_point_extraction(geometry_object)
                
        except Exception as e:
            self.logger.error(f"Error extraient punts: {e}")
            return np.array([])
    
    def _try_automatic_point_extraction(self, geometry_object: Any) -> np.ndarray:
        """Intenta extreure punts automàticament de diferents formats."""
        try:
            # Provar diferents mètodes segons el tipus d'objecte
            if hasattr(geometry_object, 'faces'):
                # Extreure vèrtexs de les cares
                vertices = []
                for face in geometry_object.faces:
                    if hasattr(face, 'vertices'):
                        for vertex in face.vertices():
                            vertices.append([vertex.X, vertex.Y, vertex.Z])
                return np.array(vertices) if vertices else np.array([])
            
            # Més mètodes d'extracció aquí...
            return np.array([])
            
        except Exception:
            return np.array([])
    
    def _calculate_original_volume(self, geometry_object: Any) -> float:
        """Calcula el volum original de l'objecte."""
        try:
            if hasattr(geometry_object, 'volume'):
                return float(geometry_object.volume)
            elif hasattr(geometry_object, 'Volume'):
                return float(geometry_object.Volume())
            else:
                # Estimació basada en convex hull
                points = self._extract_points_from_geometry(geometry_object)
                if len(points) > 3:
                    hull = ConvexHull(points)
                    return hull.volume * 0.7  # Factor d'estimació per concavitats
                return 0.0
        except Exception:
            return 0.0
    
    def _detect_concavities(self, points: np.ndarray) -> bool:
        """
        Detecta si l'objecte té concavitats significatives.
        
        Args:
            points: Punts de l'objecte
            
        Returns:
            True si té concavitats
        """
        try:
            if len(points) < 4:
                return False
                
            # Crear convex hull
            hull = ConvexHull(points)
            hull_volume = hull.volume
            
            # Crear mesh dels punts originals
            try:
                # Intentar crear mesh amb alpha shape
                import alphashape
                alpha_shape = alphashape.alphashape(points, 0.1)
                if hasattr(alpha_shape, 'volume'):
                    original_volume = alpha_shape.volume
                    # Si la diferència és gran, hi ha concavitats
                    concavity_ratio = (hull_volume - original_volume) / hull_volume
                    return concavity_ratio > 0.1  # 10% de diferència
            except ImportError:
                pass
            
            # Mètode alternatiu: comptar punts dins/fora del hull
            interior_points = 0
            for point in points:
                if self._point_inside_convex_hull(point, hull):
                    interior_points += 1
            
            exterior_ratio = (len(points) - interior_points) / len(points)
            return exterior_ratio > 0.05  # 5% de punts exteriors
            
        except Exception as e:
            self.logger.warning(f"Error detectant concavitats: {e}")
            return False
    
    def _point_inside_convex_hull(self, point: np.ndarray, hull: ConvexHull) -> bool:
        """Comprova si un punt està dins de la convex hull."""
        try:
            for eq in hull.equations:
                if np.dot(eq[:-1], point) + eq[-1] > 1e-6:
                    return False
            return True
        except Exception:
            return True
    
    def _generate_box_standard(
        self, 
        points: np.ndarray, 
        target_faces: int,
        quality_factor: float
    ) -> BoxGenerationResult:
        """
        Genera caixa per objectes convexos (estratègia estàndard).
        
        Args:
            points: Punts de l'objecte
            target_faces: Nombre de cares objectiu
            quality_factor: Factor de qualitat
            
        Returns:
            BoxGenerationResult
        """
        try:
            # 1. Calcular Convex Hull inicial
            hull = ConvexHull(points)
            self.logger.info(f"📐 Convex hull inicial: {len(hull.simplices)} cares")
            
            # 2. Extreure normals de les cares
            normals = []
            face_areas = []
            
            for simplex in hull.simplices:
                # Calcular normal de la cara
                v0, v1, v2 = points[simplex]
                normal = np.cross(v1 - v0, v2 - v0)
                normal = normal / np.linalg.norm(normal)
                normals.append(normal)
                
                # Calcular àrea de la cara
                area = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0))
                face_areas.append(area)
            
            normals = np.array(normals)
            face_areas = np.array(face_areas)
            
            # 3. Clustering de normals ponderat per àrea
            if target_faces >= len(normals):
                # Si demanem més cares de les que té, usar totes
                cluster_labels = np.arange(len(normals))
                n_clusters = len(normals)
            else:
                # K-means clustering amb pesos per àrea
                kmeans = KMeans(
                    n_clusters=target_faces, 
                    init='k-means++',
                    n_init=10,
                    random_state=42
                )
                cluster_labels = kmeans.fit_predict(normals, sample_weight=face_areas)
                n_clusters = target_faces
            
            self.logger.info(f"🎯 Agrupant {len(normals)} cares en {n_clusters} grups")
            
            # 4. Generar noves cares fusionades
            new_faces = []
            for cluster_id in range(n_clusters):
                cluster_mask = cluster_labels == cluster_id
                cluster_normals = normals[cluster_mask]
                cluster_areas = face_areas[cluster_mask]
                
                # Normal mitjana ponderada per àrea
                avg_normal = np.average(cluster_normals, axis=0, weights=cluster_areas)
                avg_normal = avg_normal / np.linalg.norm(avg_normal)
                
                # Trobar punt de suport (més llunyà en direcció de la normal)
                projections = np.dot(points, avg_normal)
                support_point = points[np.argmax(projections)]
                
                # Definir pla: normal · x = normal · support_point
                d = np.dot(avg_normal, support_point)
                new_faces.append((avg_normal, d))
            
            # 5. Construir politop amb intersecció de plans
            vertices = self._intersect_planes_to_vertices(new_faces)
            
            if len(vertices) < 4:
                # Fallback: usar bounding box orientat
                return self._generate_oriented_bounding_box(points, target_faces)
            
            # 6. Crear ConvexHull final
            final_hull = ConvexHull(vertices)
            
            # 7. Calcular mètriques
            box_volume = final_hull.volume
            surface_area = final_hull.area
            
            return BoxGenerationResult(
                vertices=final_hull.points,
                faces=final_hull.simplices,
                volume=box_volume,
                surface_area=surface_area,
                face_count=len(final_hull.simplices),
                efficiency=0.0,  # S'actualitzarà després
                original_volume=0.0,  # S'actualitzarà després
                box_volume=box_volume
            )
            
        except Exception as e:
            self.logger.error(f"Error en generació estàndard: {e}")
            # Fallback a bounding box
            return self._generate_oriented_bounding_box(points, target_faces)
    
    def _intersect_planes_to_vertices(self, planes: List[Tuple[np.ndarray, float]]) -> np.ndarray:
        """
        Troba els vèrtexs d'un politop definit per la intersecció de plans.
        
        Args:
            planes: Llista de (normal, distància) per cada pla
            
        Returns:
            Array de vèrtexs
        """
        try:
            # Mètode simplificat: generar punts candidats amb interseccions de 3 plans
            vertices = []
            n = len(planes)
            
            for i in range(n):
                for j in range(i + 1, n):
                    for k in range(j + 1, n):
                        # Intersecció de 3 plans
                        A = np.array([planes[i][0], planes[j][0], planes[k][0]])
                        b = np.array([planes[i][1], planes[j][1], planes[k][1]])
                        
                        try:
                            vertex = np.linalg.solve(A, b)
                            
                            # Verificar que el punt està dins de tots els plans
                            valid = True
                            for normal, d in planes:
                                if np.dot(normal, vertex) > d + 1e-6:
                                    valid = False
                                    break
                            
                            if valid:
                                vertices.append(vertex)
                                
                        except np.linalg.LinAlgError:
                            continue
            
            return np.array(vertices) if vertices else np.array([])
            
        except Exception as e:
            self.logger.error(f"Error intersecant plans: {e}")
            return np.array([])
    
    def _generate_oriented_bounding_box(
        self, 
        points: np.ndarray, 
        target_faces: int
    ) -> BoxGenerationResult:
        """
        Genera una bounding box orientada com a fallback.
        
        Args:
            points: Punts de l'objecte
            target_faces: Nombre de cares (ignorat, sempre 6)
            
        Returns:
            BoxGenerationResult
        """
        try:
            # PCA per trobar orientació principal
            centroid = np.mean(points, axis=0)
            centered_points = points - centroid
            
            # Matriu de covariança
            cov_matrix = np.cov(centered_points.T)
            eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
            
            # Ordenar per eigenvalues descendents
            idx = np.argsort(eigenvalues)[::-1]
            eigenvectors = eigenvectors[:, idx]
            
            # Transformar punts al sistema de coordenades principal
            transformed_points = centered_points @ eigenvectors
            
            # Trobar límits
            min_coords = np.min(transformed_points, axis=0)
            max_coords = np.max(transformed_points, axis=0)
            
            # Crear vèrtexs de la caixa
            box_vertices = []
            for x in [min_coords[0], max_coords[0]]:
                for y in [min_coords[1], max_coords[1]]:
                    for z in [min_coords[2], max_coords[2]]:
                        # Transformar de tornada
                        vertex = np.array([x, y, z]) @ eigenvectors.T + centroid
                        box_vertices.append(vertex)
            
            box_vertices = np.array(box_vertices)
            
            # Crear ConvexHull de la caixa
            hull = ConvexHull(box_vertices)
            
            return BoxGenerationResult(
                vertices=hull.points,
                faces=hull.simplices,
                volume=hull.volume,
                surface_area=hull.area,
                face_count=len(hull.simplices),
                efficiency=0.0,
                original_volume=0.0,
                box_volume=hull.volume
            )
            
        except Exception as e:
            self.logger.error(f"Error generant bounding box orientada: {e}")
            raise
    
    def _generate_box_for_concave_object(
        self,
        geometry_object: Any,
        points: np.ndarray,
        target_faces: int,
        quality_factor: float
    ) -> BoxGenerationResult:
        """
        Genera caixa per objectes amb concavitats (estratègia avançada).
        
        Utilitza segmentació convexa i fusió de caixes individuals.
        """
        try:
            self.logger.info("🔧 Aplicant estratègia per objectes concaus")
            
            # 1. Intentar segmentació convexa
            convex_parts = self._decompose_to_convex_parts(geometry_object)
            
            if len(convex_parts) <= 1:
                # Si no es pot segmentar, usar estratègia estàndard
                return self._generate_box_standard(points, target_faces, quality_factor)
            
            # 2. Generar caixa per cada part convexa
            part_boxes = []
            faces_per_part = max(3, target_faces // len(convex_parts))
            
            for i, part in enumerate(convex_parts):
                part_points = self._extract_points_from_geometry(part)
                if len(part_points) > 3:
                    part_box = self._generate_box_standard(
                        part_points, faces_per_part, quality_factor
                    )
                    part_boxes.append(part_box)
            
            # 3. Fusionar caixes individuals
            if len(part_boxes) == 1:
                return part_boxes[0]
            else:
                return self._merge_boxes(part_boxes, target_faces)
                
        except Exception as e:
            self.logger.error(f"Error en estratègia per objectes concaus: {e}")
            # Fallback a estratègia estàndard
            return self._generate_box_standard(points, target_faces, quality_factor)
    
    def _decompose_to_convex_parts(self, geometry_object: Any) -> List[Any]:
        """
        Descompon un objecte concau en parts convexes.
        
        Returns:
            Llista de parts convexes
        """
        try:
            # Aquesta és una implementació simplificada
            # En una implementació real, usaríem algoritmes com V-HACD
            
            # Per ara, retornem l'objecte original com a única part
            return [geometry_object]
            
        except Exception:
            return [geometry_object]
    
    def _merge_boxes(
        self, 
        boxes: List[BoxGenerationResult], 
        target_faces: int
    ) -> BoxGenerationResult:
        """
        Fusiona múltiples caixes en una de sola.
        
        Args:
            boxes: Llista de caixes a fusionar
            target_faces: Nombre de cares objectiu
            
        Returns:
            Caixa fusionada
        """
        try:
            # Combinar tots els vèrtexs
            all_vertices = []
            for box in boxes:
                all_vertices.extend(box.vertices)
            
            all_vertices = np.array(all_vertices)
            
            # Crear ConvexHull de tots els vèrtexs
            merged_hull = ConvexHull(all_vertices)
            
            # Si té massa cares, simplificar
            if len(merged_hull.simplices) > target_faces:
                # Aplicar simplificació
                simplified_result = self._generate_box_standard(
                    all_vertices, target_faces, 1.0
                )
                return simplified_result
            
            # Calcular mètriques combinades
            total_volume = sum(box.box_volume for box in boxes)
            total_surface = sum(box.surface_area for box in boxes)
            
            return BoxGenerationResult(
                vertices=merged_hull.points,
                faces=merged_hull.simplices,
                volume=merged_hull.volume,
                surface_area=merged_hull.area,
                face_count=len(merged_hull.simplices),
                efficiency=0.0,
                original_volume=0.0,
                box_volume=merged_hull.volume
            )
            
        except Exception as e:
            self.logger.error(f"Error fusionant caixes: {e}")
            # Retornar la primera caixa com a fallback
            return boxes[0] if boxes else None


def create_intelligent_box_for_object(
    geometry_object: Any,
    target_faces: int = 6,
    quality_factor: float = 1.0,
    debug_mode: bool = False
) -> Optional[BoxGenerationResult]:
    """
    Funció principal per crear una caixa intel·ligent per un objecte 3D.
    
    Args:
        geometry_object: Objecte 3D (STL/STP)
        target_faces: Nombre de cares desitjades (4-20 recomanat)
        quality_factor: Factor de qualitat 0.1-2.0 (més alt = millor qualitat)
        debug_mode: Mostrar informació de debug
        
    Returns:
        BoxGenerationResult o None si hi ha error
        
    Example:
        >>> result = create_intelligent_box_for_object(my_object, target_faces=8)
        >>> print(f"Caixa generada amb {result.face_count} cares, eficiència {result.efficiency:.1f}%")
    """
    try:
        generator = IntelligentBoxGenerator(debug_mode=debug_mode)
        return generator.generate_custom_box(
            geometry_object=geometry_object,
            target_faces=target_faces,
            quality_factor=quality_factor,
            handle_concavities=True
        )
    except Exception as e:
        logger.error(f"❌ Error creant caixa intel·ligent: {e}")
        return None


# Test i exemple d'ús
if __name__ == "__main__":
    # Exemple d'ús amb punts de prova
    np.random.seed(42)
    test_points = np.random.rand(100, 3) * 10
    
    # Crear objecte simulat
    class MockGeometry:
        def __init__(self, points):
            self.points = points
            self.volume = 100.0
    
    test_object = MockGeometry(test_points)
    
    # Generar caixa
    result = create_intelligent_box_for_object(
        test_object, 
        target_faces=8, 
        debug_mode=True
    )
    
    if result:
        print(f"✅ Test completat:")
        print(f"   Cares: {result.face_count}")
        print(f"   Volum: {result.box_volume:.2f}")
        print(f"   Eficiència: {result.efficiency:.1f}%")
