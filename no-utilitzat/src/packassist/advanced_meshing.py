"""
Sistema avançat de meshing i collision detection per PackAssist
Implementa algoritmes de conversió de geometria a meshes i detecció de col·lisions
"""

import numpy as np
import math
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

@dataclass
class Mesh3D:
    """Representa un mesh 3D amb vèrtexs, cares i normals."""
    vertices: np.ndarray  # N x 3 array de vèrtexs
    faces: np.ndarray     # M x 3 array d'índexs de triangles
    normals: np.ndarray   # M x 3 array de normals de cares
    bounds: Dict[str, float]  # Bounding box
    
    def __post_init__(self):
        """Calcula automàticament normals i bounds si no es proporcionen."""
        if self.normals is None:
            self.normals = self._compute_face_normals()
        if self.bounds is None:
            self.bounds = self._compute_bounds()
    
    def _compute_face_normals(self) -> np.ndarray:
        """Calcula les normals de cada cara."""
        normals = []
        for face in self.faces:
            v0, v1, v2 = self.vertices[face]
            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = np.cross(edge1, edge2)
            norm = np.linalg.norm(normal)
            if norm > 0:
                normal = normal / norm
            else:
                normal = np.array([0, 0, 1])  # Default normal
            normals.append(normal)
        return np.array(normals)
    
    def _compute_bounds(self) -> Dict[str, float]:
        """Calcula el bounding box del mesh."""
        min_coords = np.min(self.vertices, axis=0)
        max_coords = np.max(self.vertices, axis=0)
        return {
            'min_x': min_coords[0], 'max_x': max_coords[0],
            'min_y': min_coords[1], 'max_y': max_coords[1], 
            'min_z': min_coords[2], 'max_z': max_coords[2],
            'length': max_coords[0] - min_coords[0],
            'width': max_coords[1] - min_coords[1],
            'height': max_coords[2] - min_coords[2]
        }
    
    def transform(self, translation: np.ndarray = None, rotation_matrix: np.ndarray = None):
        """Aplica transformacions al mesh."""
        transformed_vertices = self.vertices.copy()
        
        # Aplicar rotació
        if rotation_matrix is not None:
            transformed_vertices = transformed_vertices @ rotation_matrix.T
        
        # Aplicar translació
        if translation is not None:
            transformed_vertices += translation
        
        # Crear nou mesh transformat
        transformed_normals = None
        if rotation_matrix is not None and self.normals is not None:
            transformed_normals = self.normals @ rotation_matrix.T
        
        return Mesh3D(
            vertices=transformed_vertices,
            faces=self.faces.copy(),
            normals=transformed_normals,
            bounds=None  # Es recalcularà automàticament
        )
    
    def get_volume(self) -> float:
        """Calcula el volum del mesh usant divergence theorem."""
        volume = 0.0
        for face in self.faces:
            v0, v1, v2 = self.vertices[face]
            # Volum d'un tetraedre amb vèrtex a l'origen
            volume += np.dot(v0, np.cross(v1, v2)) / 6.0
        return abs(volume)

class GeometryToMeshConverter:
    """Converteix geometries complexes a meshes optimitzats."""
    
    @staticmethod
    def from_complex_geometry(complex_geometry) -> Mesh3D:
        """Converteix ComplexGeometry a Mesh3D."""
        from .advanced_geometry import ComplexGeometry
        
        if not isinstance(complex_geometry, ComplexGeometry):
            raise ValueError("Input must be ComplexGeometry instance")
        
        # Extreure tots els vèrtexs únics
        all_vertices = []
        vertex_to_index = {}
        
        for vertex in complex_geometry.vertices:
            if vertex not in vertex_to_index:
                vertex_to_index[vertex] = len(all_vertices)
                all_vertices.append(vertex)
        
        vertices_array = np.array(all_vertices)
        
        # Convertir cares a triangles
        triangular_faces = []
        for face in complex_geometry.faces:
            face_vertices = face.vertices
            if len(face_vertices) >= 3:
                # Triangular fan approach per cares amb més de 3 vèrtexs
                for i in range(1, len(face_vertices) - 1):
                    triangle = [
                        vertex_to_index[face_vertices[0]],
                        vertex_to_index[face_vertices[i]],
                        vertex_to_index[face_vertices[i + 1]]
                    ]
                    triangular_faces.append(triangle)
        
        faces_array = np.array(triangular_faces)
        
        return Mesh3D(
            vertices=vertices_array,
            faces=faces_array,
            normals=None,  # Es calcularà automàticament
            bounds=None
        )
    
    @staticmethod
    def from_box_dimensions(length: float, width: float, height: float) -> Mesh3D:
        """Crea un mesh d'una caixa rectangular."""
        # Definir els 8 vèrtexs d'una caixa
        vertices = np.array([
            [0, 0, 0], [length, 0, 0], [length, width, 0], [0, width, 0],  # Base inferior
            [0, 0, height], [length, 0, height], [length, width, height], [0, width, height]  # Base superior
        ])
        
        # Definir les 12 cares triangulars (2 triangles per cara de cub)
        faces = np.array([
            # Base inferior (Z=0)
            [0, 1, 2], [0, 2, 3],
            # Base superior (Z=height)
            [4, 6, 5], [4, 7, 6],
            # Cara frontal (Y=0)
            [0, 5, 1], [0, 4, 5],
            # Cara posterior (Y=width)
            [2, 7, 3], [2, 6, 7],
            # Cara dreta (X=length)
            [1, 6, 2], [1, 5, 6],
            # Cara esquerra (X=0)
            [0, 3, 7], [0, 7, 4]
        ])
        
        return Mesh3D(
            vertices=vertices,
            faces=faces,
            normals=None,
            bounds=None
        )
    
    @staticmethod
    def from_cylinder(radius: float, height: float, segments: int = 16) -> Mesh3D:
        """Crea un mesh d'un cilindre."""
        vertices = []
        faces = []
        
        # Crear vèrtexs de la base inferior i superior
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            vertices.append([x, y, 0])      # Base inferior
            vertices.append([x, y, height]) # Base superior
        
        # Afegir centres de les bases
        vertices.append([0, 0, 0])      # Centre base inferior
        vertices.append([0, 0, height]) # Centre base superior
        
        vertices = np.array(vertices)
        
        center_bottom = len(vertices) - 2
        center_top = len(vertices) - 1
        
        # Crear cares laterals
        for i in range(segments):
            next_i = (i + 1) % segments
            bottom_1 = i * 2
            bottom_2 = next_i * 2
            top_1 = i * 2 + 1
            top_2 = next_i * 2 + 1
            
            # Dos triangles per cada segment lateral
            faces.append([bottom_1, top_1, bottom_2])
            faces.append([bottom_2, top_1, top_2])
        
        # Crear cares de les bases
        for i in range(segments):
            next_i = (i + 1) % segments
            # Base inferior
            faces.append([center_bottom, i * 2, next_i * 2])
            # Base superior
            faces.append([center_top, next_i * 2 + 1, i * 2 + 1])
        
        return Mesh3D(
            vertices=vertices,
            faces=np.array(faces),
            normals=None,
            bounds=None
        )

class RotationGenerator:
    """Genera rotacions intel·ligents per objectes 3D."""
    
    @staticmethod
    def get_standard_rotations() -> List[Tuple[str, np.ndarray]]:
        """Retorna les 24 rotacions estàndard d'un cub."""
        rotations = []
        
        # Matrius de rotació bàsiques
        def rx(angle):
            c, s = np.cos(angle), np.sin(angle)
            return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
        
        def ry(angle):
            c, s = np.cos(angle), np.sin(angle)
            return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
        
        def rz(angle):
            c, s = np.cos(angle), np.sin(angle)
            return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        
        # 24 rotacions diferents (grup de simetria del cub)
        angles = [0, np.pi/2, np.pi, 3*np.pi/2]
        
        for i, angle_x in enumerate([0, np.pi/2, np.pi, 3*np.pi/2]):
            for j, angle_y in enumerate([0, np.pi/2, np.pi, 3*np.pi/2]):
                for k, angle_z in enumerate([0, np.pi/2]):
                    rotation_matrix = rz(angle_z) @ ry(angle_y) @ rx(angle_x)
                    name = f"R{i}{j}{k}"
                    rotations.append((name, rotation_matrix))
        
        return rotations[:24]  # Limitar a 24 rotacions úniques
    
    @staticmethod
    def get_smart_rotations(mesh: Mesh3D) -> List[Tuple[str, np.ndarray]]:
        """Genera rotacions intel·ligents basades en la geometria del mesh."""
        rotations = []
        
        # Començar amb rotacions estàndard
        standard_rots = RotationGenerator.get_standard_rotations()
        
        # Filtrar rotacions que donin dimensions similars
        unique_dimensions = set()
        
        for name, rot_matrix in standard_rots:
            # Aplicar rotació als vèrtexs
            rotated_vertices = mesh.vertices @ rot_matrix.T
            
            # Calcular noves dimensions
            min_coords = np.min(rotated_vertices, axis=0)
            max_coords = np.max(rotated_vertices, axis=0)
            dimensions = max_coords - min_coords
            
            # Arrodonir dimensions per evitar duplicats
            dim_key = tuple(np.round(sorted(dimensions), decimals=2))
            
            if dim_key not in unique_dimensions:
                unique_dimensions.add(dim_key)
                rotations.append((name, rot_matrix))
        
        return rotations

class BasicCollisionDetector:
    """Detector de col·lisions bàsic per meshes."""
    
    @staticmethod
    def bounding_box_collision(mesh1: Mesh3D, mesh2: Mesh3D) -> bool:
        """Detecta col·lisió entre bounding boxes."""
        b1, b2 = mesh1.bounds, mesh2.bounds
        
        # Comprovar solapament en cada eix
        x_overlap = b1['max_x'] > b2['min_x'] and b2['max_x'] > b1['min_x']
        y_overlap = b1['max_y'] > b2['min_y'] and b2['max_y'] > b1['min_y']
        z_overlap = b1['max_z'] > b2['min_z'] and b2['max_z'] > b1['min_z']
        
        return x_overlap and y_overlap and z_overlap
    
    @staticmethod
    def mesh_collision_detailed(mesh1: Mesh3D, mesh2: Mesh3D) -> bool:
        """Detecta col·lisió detallada entre meshes (versió simplificada)."""
        # Primer: comprovar bounding boxes
        if not BasicCollisionDetector.bounding_box_collision(mesh1, mesh2):
            return False
        
        # Segon: comprovar interseccions de triangles (implementació bàsica)
        # Per ara, utilitzem una aproximació amb punts de mostratge
        return BasicCollisionDetector._sample_based_collision(mesh1, mesh2)
    
    @staticmethod
    def _sample_based_collision(mesh1: Mesh3D, mesh2: Mesh3D, samples: int = 100) -> bool:
        """Detecta col·lisió basada en mostratge de punts."""
        # Generar punts de mostra dins del primer mesh
        b1 = mesh1.bounds
        
        for _ in range(samples):
            # Punt aleatori dins del bounding box del mesh1
            x = np.random.uniform(b1['min_x'], b1['max_x'])
            y = np.random.uniform(b1['min_y'], b1['max_y'])
            z = np.random.uniform(b1['min_z'], b1['max_z'])
            point = np.array([x, y, z])
            
            # Comprovar si el punt està dins dels dos meshes
            if (BasicCollisionDetector._point_in_mesh_approx(point, mesh1) and
                BasicCollisionDetector._point_in_mesh_approx(point, mesh2)):
                return True
        
        return False
    
    @staticmethod
    def _point_in_mesh_approx(point: np.ndarray, mesh: Mesh3D) -> bool:
        """Aproximació ràpida per determinar si un punt està dins d'un mesh."""
        # Implementació simplificada: usar bounding box + algunes comprovacions
        bounds = mesh.bounds
        
        # Primer: comprovar si està dins del bounding box
        if not (bounds['min_x'] <= point[0] <= bounds['max_x'] and
                bounds['min_y'] <= point[1] <= bounds['max_y'] and
                bounds['min_z'] <= point[2] <= bounds['max_z']):
            return False
        
        # Segon: ray casting simplificat (només en Z)
        intersections = 0
        for face in mesh.faces:
            vertices = mesh.vertices[face]
            if BasicCollisionDetector._ray_triangle_intersection_z(point, vertices):
                intersections += 1
        
        # Punt dins si nombre d'interseccions és imparell
        return intersections % 2 == 1
    
    @staticmethod
    def _ray_triangle_intersection_z(point: np.ndarray, triangle: np.ndarray) -> bool:
        """Detecta intersecció entre un raig vertical i un triangle."""
        v0, v1, v2 = triangle
        
        # Comprovar si el triangle està per sobre del punt
        if max(v0[2], v1[2], v2[2]) <= point[2]:
            return False
        
        # Comprovar si el punt (x,y) està dins del triangle (x,y)
        # Usar coordenades baricèntriques
        def sign(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
        
        d1 = sign(point[:2], v0[:2], v1[:2])
        d2 = sign(point[:2], v1[:2], v2[:2])
        d3 = sign(point[:2], v2[:2], v0[:2])
        
        has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
        has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
        
        return not (has_neg and has_pos)

def test_meshing_system():
    """Test del sistema de meshing."""
    print("🧪 Testant sistema de meshing avançat...")
    
    # Test 1: Crear mesh de caixa
    print("\n1️⃣ Test creació mesh de caixa...")
    box_mesh = GeometryToMeshConverter.from_box_dimensions(100, 80, 60)
    print(f"   ✅ Mesh creat: {len(box_mesh.vertices)} vèrtexs, {len(box_mesh.faces)} cares")
    print(f"   📦 Bounds: {box_mesh.bounds}")
    print(f"   📊 Volum: {box_mesh.get_volume():.2f} mm³")
    
    # Test 2: Crear mesh de cilindre
    print("\n2️⃣ Test creació mesh de cilindre...")
    cylinder_mesh = GeometryToMeshConverter.from_cylinder(50, 100, 12)
    print(f"   ✅ Mesh creat: {len(cylinder_mesh.vertices)} vèrtexs, {len(cylinder_mesh.faces)} cares")
    print(f"   📊 Volum: {cylinder_mesh.get_volume():.2f} mm³")
    
    # Test 3: Rotacions intel·ligents
    print("\n3️⃣ Test rotacions intel·ligents...")
    rotations = RotationGenerator.get_smart_rotations(box_mesh)
    print(f"   ✅ Generades {len(rotations)} rotacions úniques")
    
    # Test 4: Detecció de col·lisions
    print("\n4️⃣ Test detecció de col·lisions...")
    # Crear dues caixes que es toquen
    box1 = box_mesh
    box2_transformed = box_mesh.transform(translation=np.array([50, 0, 0]))
    
    collision = BasicCollisionDetector.bounding_box_collision(box1, box2_transformed)
    print(f"   🔍 Col·lisió bounding box: {collision}")
    
    detailed_collision = BasicCollisionDetector.mesh_collision_detailed(box1, box2_transformed)
    print(f"   🔍 Col·lisió detallada: {detailed_collision}")
    
    print("\n✅ Tots els tests completats!")

if __name__ == "__main__":
    test_meshing_system()
