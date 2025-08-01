"""
Simplificador de malles STL ultra-ràpid - Versió sense emojis per Windows
"""

import os
import time
import struct
import tkinter as tk
from tkinter import filedialog, messagebox


class MeshSimplifierSimple:
    def __init__(self):
        self.available_methods = []
        self.current_method = None
        self.check_dependencies()
    
    def check_dependencies(self):
        """Comprova quines biblioteques estan disponibles"""
        print("Comprovant biblioteques disponibles...")
        
        # PyMeshLab (més ràpid i potent)
        try:
            import pymeshlab
            self.available_methods.append(('pymeshlab', 'PyMeshLab (RECOMANAT)'))
            print("PyMeshLab disponible (RECOMANAT)")
        except ImportError:
            print("PyMeshLab no disponible")
        
        # PyVista amb fast-simplification
        try:
            import pyvista as pv
            self.available_methods.append(('pyvista', 'PyVista'))
            print("PyVista disponible")
        except ImportError:
            print("PyVista no disponible")
        
        # Trimesh
        try:
            import trimesh
            self.available_methods.append(('trimesh', 'Trimesh'))
            print("Trimesh disponible")
        except ImportError:
            print("Trimesh no disponible")
        
        # pyfqmr
        try:
            import pyfqmr
            self.available_methods.append(('pyfqmr', 'pyfqmr'))
            print("pyfqmr disponible")
        except ImportError:
            print("pyfqmr no disponible")
        
        if not self.available_methods:
            print("Cap biblioteca de simplificació disponible!")
            print("Instal·la almenys pymeshlab: pip install pymeshlab")
            return
        
        # Seleccionar el millor mètode disponible
        if any(method[0] == 'pymeshlab' for method in self.available_methods):
            self.current_method = 'pymeshlab'
            print("Utilitzant PyMeshLab (més ràpid)")
        else:
            self.current_method = self.available_methods[0][0]
            print(f"Utilitzant {self.available_methods[0][1]}")
    
    def load_stl(self, stl_path):
        """Carrega un fitxer STL"""
        print(f"Carregant STL...")
        
        if not os.path.exists(stl_path):
            raise FileNotFoundError(f"Fitxer no trobat: {stl_path}")
        
        if self._is_binary_stl(stl_path):
            print("Format: STL Binary")
            return self._load_binary_stl(stl_path)
        else:
            print("Format: STL ASCII")
            return self._load_ascii_stl(stl_path)
    
    def _is_binary_stl(self, stl_path):
        """Detecta si un STL és binari"""
        try:
            with open(stl_path, 'rb') as f:
                header = f.read(80)
                if header.startswith(b'solid '):
                    f.seek(0)
                    try:
                        first_part = f.read(1024).decode('ascii', errors='ignore')
                        if 'facet normal' in first_part and 'vertex' in first_part:
                            return False
                    except:
                        pass
                return True
        except:
            return True
    
    def _load_binary_stl(self, stl_path):
        """Carrega STL binari"""
        vertices = []
        faces = []
        vertex_map = {}
        
        try:
            with open(stl_path, 'rb') as f:
                f.read(80)  # Saltar header
                triangle_count = struct.unpack('<I', f.read(4))[0]
                print(f"Original: {triangle_count*3:,} vèrtexs, {triangle_count:,} cares")
                
                for i in range(triangle_count):
                    f.read(12)  # Saltar normal
                    
                    face_vertices = []
                    for j in range(3):
                        x, y, z = struct.unpack('<fff', f.read(12))
                        vertex = (round(x, 6), round(y, 6), round(z, 6))
                        
                        if vertex not in vertex_map:
                            vertex_map[vertex] = len(vertices)
                            vertices.append(vertex)
                        
                        face_vertices.append(vertex_map[vertex])
                    
                    faces.append(face_vertices)
                    f.read(2)  # Saltar attribute count
                
                print(f"Després de deduplicació: {len(vertices):,} vèrtexs, {len(faces):,} cares")
                return vertices, faces
                
        except Exception as e:
            print(f"Error llegint STL binari: {e}")
            return [], []
    
    def _load_ascii_stl(self, stl_path):
        """Carrega STL ASCII"""
        vertices = []
        faces = []
        vertex_map = {}
        
        try:
            with open(stl_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            triangle_count = 0
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                if line.startswith('facet normal'):
                    triangle_count += 1
                    face_vertices = []
                    i += 1  # Saltar "outer loop"
                    
                    while i < len(lines):
                        line = lines[i].strip()
                        
                        if line.startswith('vertex'):
                            parts = line.split()
                            if len(parts) >= 4:
                                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                                vertex = (round(x, 6), round(y, 6), round(z, 6))
                                
                                if vertex not in vertex_map:
                                    vertex_map[vertex] = len(vertices)
                                    vertices.append(vertex)
                                
                                face_vertices.append(vertex_map[vertex])
                        
                        elif line.startswith('endfacet'):
                            if len(face_vertices) == 3:
                                faces.append(face_vertices)
                            break
                        
                        i += 1
                
                i += 1
            
            print(f"Original: {len(vertices):,} vèrtexs, {len(faces):,} cares")
            return vertices, faces
            
        except Exception as e:
            print(f"Error llegint STL ASCII: {e}")
            return [], []
    
    def simplify_pymeshlab(self, vertices, faces, target_vertices):
        """Simplifica usant PyMeshLab"""
        try:
            import pymeshlab
            ms = pymeshlab.MeshSet()
            
            # Crear mesh
            vertex_matrix = [[v[0], v[1], v[2]] for v in vertices]
            face_matrix = [[f[0], f[1], f[2]] for f in faces]
            
            mesh = pymeshlab.Mesh(vertex_matrix, face_matrix)
            ms.add_mesh(mesh)
            
            original_vertices = len(vertices)
            original_faces = len(faces)
            
            # Provar diferents mètodes de simplificació
            success = False
            
            # Mètode 1: Clustering decimation
            try:
                threshold = max(0.1, (target_vertices / original_vertices) * 2)
                ms.apply_filter('meshing_decimation_clustering', threshold=threshold)
                print("Simplificació clustering aplicada")
                success = True
            except:
                pass
            
            # Mètode 2: Quadric edge collapse (si clustering no va bé)
            if not success:
                try:
                    target_faces = min(target_vertices * 2, original_faces)
                    ms.apply_filter('meshing_decimation_quadric_edge_collapse', targetfacenum=target_faces)
                    print("Simplificació quadric edge collapse aplicada")
                    success = True
                except:
                    pass
            
            # Mètode 3: Simplificació per percentatge
            if not success:
                try:
                    percentage = max(0.1, target_vertices / original_vertices)
                    ms.apply_filter('meshing_decimation_quadric_edge_collapse', targetperc=percentage)
                    print("Simplificació per percentatge aplicada")
                    success = True
                except:
                    pass
            
            if not success:
                print("Cap mètode de PyMeshLab ha funcionat")
                return vertices, faces
            
            # Obtenir resultat
            simplified_mesh = ms.current_mesh()
            new_vertices = simplified_mesh.vertex_matrix().tolist()
            new_faces = simplified_mesh.face_matrix().tolist()
            
            # Convertir a format original
            new_vertices = [(v[0], v[1], v[2]) for v in new_vertices]
            new_faces = [[int(f[0]), int(f[1]), int(f[2])] for f in new_faces]
            
            print(f"Reduït a: {len(new_vertices):,} vèrtexs, {len(new_faces):,} cares")
            return new_vertices, new_faces
            
        except Exception as e:
            print(f"Error amb PyMeshLab: {e}")
            return vertices, faces
    
    def simplify_pyvista(self, vertices, faces, target_vertices):
        """Simplifica usant PyVista"""
        try:
            import pyvista as pv
            import numpy as np
            
            # Crear mesh PyVista
            points = np.array(vertices)
            faces_pv = []
            for face in faces:
                faces_pv.extend([3, face[0], face[1], face[2]])
            
            mesh = pv.PolyData(points, faces_pv)
            
            # Simplificar
            ratio = target_vertices / len(vertices)
            simplified = mesh.decimate(ratio)
            
            # Convertir resultat
            new_vertices = simplified.points.tolist()
            new_faces = []
            
            for i in range(simplified.n_faces):
                face = simplified.get_cell(i)
                if face.size == 3:
                    new_faces.append(face.point_ids.tolist())
            
            print(f"Reduït a: {len(new_vertices):,} vèrtexs, {len(new_faces):,} cares")
            return new_vertices, new_faces
            
        except Exception as e:
            print(f"Error amb PyVista: {e}")
            return vertices, faces
    
    def simplify_trimesh(self, vertices, faces, target_vertices):
        """Simplifica usant Trimesh"""
        try:
            import trimesh
            
            # Crear mesh
            mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
            
            # Simplificar
            ratio = target_vertices / len(vertices)
            simplified = mesh.simplify_quadric_decimation(face_count=int(len(faces) * ratio))
            
            new_vertices = simplified.vertices.tolist()
            new_faces = simplified.faces.tolist()
            
            print(f"Reduït a: {len(new_vertices):,} vèrtexs, {len(new_faces):,} cares")
            return new_vertices, new_faces
            
        except Exception as e:
            print(f"Error amb Trimesh: {e}")
            return vertices, faces
    
    def simplify(self, stl_path, target_vertices):
        """Simplifica un STL"""
        if not self.available_methods:
            raise Exception("Cap biblioteca de simplificació disponible")
        
        # Carregar STL
        vertices, faces = self.load_stl(stl_path)
        if not vertices or not faces:
            raise Exception("No s'ha pogut carregar l'STL")
        
        print(f"Aplicant simplificació amb {self.current_method}...")
        start_time = time.time()
        
        # Aplicar simplificació segons el mètode disponible
        if self.current_method == 'pymeshlab':
            new_vertices, new_faces = self.simplify_pymeshlab(vertices, faces, target_vertices)
        elif self.current_method == 'pyvista':
            new_vertices, new_faces = self.simplify_pyvista(vertices, faces, target_vertices)
        elif self.current_method == 'trimesh':
            new_vertices, new_faces = self.simplify_trimesh(vertices, faces, target_vertices)
        else:
            new_vertices, new_faces = vertices, faces
        
        end_time = time.time()
        print(f"Temps de simplificació: {end_time - start_time:.2f} segons")
        
        return new_vertices, new_faces
    
    def save_stl(self, vertices, faces, output_path):
        """Guarda un STL simplificat"""
        print(f"Guardant STL simplificat...")
        
        try:
            with open(output_path, 'wb') as f:
                # Header
                header = b'STL simplified by PackAssist' + b'\0' * (80 - 28)
                f.write(header)
                
                # Nombre de triangles
                f.write(struct.pack('<I', len(faces)))
                
                # Triangles
                for face in faces:
                    # Normal (dummy)
                    f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                    
                    # Vèrtexs
                    for vertex_idx in face:
                        if vertex_idx < len(vertices):
                            v = vertices[vertex_idx]
                            f.write(struct.pack('<fff', float(v[0]), float(v[1]), float(v[2])))
                        else:
                            f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                    
                    # Attribute count
                    f.write(struct.pack('<H', 0))
            
            print(f"STL guardat: {output_path}")
            return True
            
        except Exception as e:
            print(f"Error guardant STL: {e}")
            return False


def create_gui():
    """Crea interfície gràfica simple"""
    root = tk.Tk()
    root.title("Simplificador STL Ràpid")
    root.geometry("600x400")
    
    # Variables
    selected_file = tk.StringVar()
    target_vertices = tk.IntVar(value=500)
    
    # Crear simplificador
    try:
        simplifier = MeshSimplifierSimple()
        if not simplifier.available_methods:
            messagebox.showerror("Error", "No hi ha biblioteques de simplificació disponibles!\nInstal·la pymeshlab: pip install pymeshlab")
            return
    except Exception as e:
        messagebox.showerror("Error", f"Error inicialitzant simplificador: {e}")
        return
    
    def select_file():
        file_path = filedialog.askopenfilename(
            title="Selecciona fitxer STL",
            filetypes=[("Fitxers STL", "*.stl"), ("Tots els fitxers", "*.*")]
        )
        if file_path:
            selected_file.set(file_path)
            # Mostrar info del fitxer
            try:
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                info_label.config(text=f"Fitxer: {os.path.basename(file_path)}\nMida: {size_mb:.1f} MB")
            except:
                info_label.config(text=f"Fitxer: {os.path.basename(file_path)}")
    
    def simplify_file():
        if not selected_file.get():
            messagebox.showerror("Error", "Selecciona un fitxer STL primer")
            return
        
        try:
            # Simplificar
            vertices, faces = simplifier.simplify(selected_file.get(), target_vertices.get())
            
            # Generar nom de sortida
            input_path = selected_file.get()
            name, ext = os.path.splitext(input_path)
            output_path = f"{name}_simplified_{len(vertices)}v{ext}"
            
            # Guardar
            if simplifier.save_stl(vertices, faces, output_path):
                messagebox.showinfo("Èxit", f"STL simplificat guardat:\n{output_path}")
            else:
                messagebox.showerror("Error", "No s'ha pogut guardar l'STL")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error en la simplificació:\n{e}")
    
    # Interfície
    tk.Label(root, text="Simplificador STL Ràpid", font=("Arial", 16, "bold")).pack(pady=10)
    
    # Info del simplificador
    methods_text = ", ".join([method[1] for method in simplifier.available_methods])
    tk.Label(root, text=f"Mètodes disponibles: {methods_text}", 
             font=("Arial", 10)).pack(pady=5)
    
    # Selecció de fitxer
    file_frame = tk.Frame(root)
    file_frame.pack(pady=20, padx=20, fill='x')
    
    tk.Button(file_frame, text="Seleccionar STL", command=select_file, 
              width=15, height=2).pack(side='left')
    
    info_label = tk.Label(file_frame, text="Cap fitxer seleccionat", 
                          font=("Arial", 10), anchor='w')
    info_label.pack(side='left', padx=(10, 0), fill='x', expand=True)
    
    # Configuració
    config_frame = tk.Frame(root)
    config_frame.pack(pady=20)
    
    tk.Label(config_frame, text="Vèrtexs objectiu:", font=("Arial", 12)).pack()
    
    vertex_frame = tk.Frame(config_frame)
    vertex_frame.pack(pady=5)
    
    tk.Scale(vertex_frame, from_=50, to=5000, orient='horizontal', 
             variable=target_vertices, length=300).pack()
    
    tk.Label(vertex_frame, textvariable=target_vertices, 
             font=("Arial", 10, "bold")).pack()
    
    # Botó de simplificació
    tk.Button(root, text="SIMPLIFICAR", command=simplify_file, 
              font=("Arial", 14, "bold"), bg='#4CAF50', fg='white',
              width=20, height=2).pack(pady=30)
    
    # Instruccions
    instructions = """Instruccions:
1. Selecciona un fitxer STL
2. Estableix el nombre objectiu de vèrtexs
3. Clica SIMPLIFICAR
4. El resultat es guardarà amb '_simplified' al nom"""
    
    tk.Label(root, text=instructions, font=("Arial", 10), 
             justify='left', anchor='w').pack(pady=20, padx=20)
    
    return root


def main():
    """Funció principal"""
    print("Simplificador STL RÀPID inicialitzat")
    
    try:
        app = create_gui()
        if app:
            app.mainloop()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
