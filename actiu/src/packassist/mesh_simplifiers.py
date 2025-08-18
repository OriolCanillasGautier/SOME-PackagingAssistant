"""
Funcions de simplificació de malla compatibles amb l'estructura original
"""

import trimesh
import numpy as np

def simplify_mesh_pymeshlab(mesh, target_vertices, preserve_volume=True):
    """Simplifica amb PyMeshLab (alta qualitat)"""
    try:
        import pymeshlab
        
        # Crear conjunt de dades de malla
        mesh_set = pymeshlab.MeshSet()
        
        # Afegir malla original
        mesh_set.add_mesh(pymeshlab.Mesh(mesh.vertices, mesh.faces), "original_mesh")

        # Calcular nombre de cares objectiu
        current_faces = len(mesh.faces)
        current_vertices = len(mesh.vertices)
        
        if current_vertices <= target_vertices:
            return mesh  # No cal reducció
            
        target_faces = int(target_vertices * (current_faces / current_vertices))  # Estimació
        target_faces = max(4, target_faces)  # Assegurar un mínim

        print(f"🔧 Simplificant amb PyMeshLab: {current_faces:,} → ~{target_faces:,} cares")

        # Aplicar filtre de simplificació (decimació quadrica)
        mesh_set.meshing_decimation_quadric_edge_collapse(targetfacenum=target_faces)

        # Obtenir malla simplificada
        simplified_mesh_data = mesh_set.current_mesh()

        # Convertir de nou a trimesh
        simplified_mesh = trimesh.Trimesh(
            vertices=simplified_mesh_data.vertex_matrix(),
            faces=simplified_mesh_data.face_matrix()
        )
        
        print(f"✅ Simplificació PyMeshLab completada: {len(simplified_mesh.vertices)} vèrtexs")
        return simplified_mesh
        
    except Exception as e:
        print(f"Error amb PyMeshLab: {e}")
        raise Exception(f"Error amb PyMeshLab: {e}")

def simplify_mesh_trimesh(mesh, target_vertices, preserve_volume=True):
    """Simplifica amb Trimesh (ràpid)"""
    try:
        current_vertices = len(mesh.vertices)
        current_faces = len(mesh.faces)
        
        if current_vertices <= target_vertices:
            return mesh  # No cal reducció

        # Calcular ratio de reducció (entre 0 i 1)
        reduction_ratio = target_vertices / current_vertices
        target_faces = int(target_vertices * (current_faces / current_vertices))
        
        print(f"🔧 Simplificant amb Trimesh: {current_vertices:,} → ~{target_vertices:,} vèrtexs ({reduction_ratio*100:.1f}% ratio)")

        # Intentar decimació quadric de trimesh
        try:
            simplified = mesh.simplify_quadric_decimation(target_faces)
            
            if simplified is None or len(simplified.vertices) == 0 or not simplified.is_valid:
                print("⚠️ Decimació quadric fallida, usant mètode alternatiu")
                return _simple_mesh_reduction(mesh, target_vertices)
            
            print(f"✅ Simplificació Trimesh completada: {len(simplified.vertices)} vèrtexs")
            return simplified
            
        except Exception as e:
            print(f"⚠️ quadric_decimation error: {e}, usant mètode alternatiu")
            return _simple_mesh_reduction(mesh, target_vertices)
            
    except Exception as e:
        print(f"Error amb Trimesh: {e}")
        raise Exception(f"Error amb Trimesh: {e}")

def _simple_mesh_reduction(mesh, target_vertices):
    """Mètode de reducció simple quan altres mètodes fallen"""
    try:
        current_vertices = len(mesh.vertices)
        if current_vertices <= target_vertices:
            return mesh

        reduction_ratio = target_vertices / current_vertices
        print(f"🔧 Simplificació simple: {current_vertices:,} → ~{target_vertices:,} vèrtexs ({reduction_ratio*100:.1f}% ratio)")

        # Mostreig uniforme de vèrtexs
        vertices = mesh.vertices
        faces = mesh.faces

        # Seleccionar índexs de vèrtexs de manera uniforme
        indices = np.linspace(0, current_vertices - 1, target_vertices, dtype=int)
        indices = np.unique(indices)  # Eliminar duplicats
        
        new_vertices = vertices[indices]

        # Crear mapa de vèrtexs vells a nous
        vertex_map = {old_idx: new_idx for new_idx, old_idx in enumerate(indices)}

        # Filtrar cares que tenen tots els vèrtexs en el nou conjunt
        new_faces = []
        for face in faces:
            if all(v in vertex_map for v in face):
                new_face = [vertex_map[v] for v in face]
                # Verificar que no és degenerada
                if len(set(new_face)) == 3:  # Triangle vàlid
                    new_faces.append(new_face)

        if len(new_faces) == 0:
            print("⚠️ No es poden crear cares vàlides, retornant original")
            return mesh

        # Crear nova malla simplificada
        try:
            simplified_mesh = trimesh.Trimesh(vertices=new_vertices, faces=new_faces)
            
            # Verificar que la malla és vàlida
            if len(simplified_mesh.vertices) == 0 or len(simplified_mesh.faces) == 0:
                print("⚠️ Malla simplificada buida, retornant original")
                return mesh
                
            print(f"✅ Simplificació simple completada: {len(simplified_mesh.vertices)} vèrtexs")
            return simplified_mesh
            
        except Exception as e:
            print(f"⚠️ Error creant malla simplificada: {e}, retornant original")
            return mesh
            
    except Exception as e:
        print(f"⚠️ Error en mètode de reducció simple: {e}")
        return mesh  # Retornar original si falla
