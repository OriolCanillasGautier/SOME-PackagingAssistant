#!/usr/bin/env python3
"""
Ultra Fast Mesh Simplifier
Utilitza múltiples biblioteques per simplificar malles STL de forma ràpida i eficient
"""

import os
import sys
import time
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import struct
from pathlib import Path

class UltraFastMeshSimplifier:
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
            print("✅ PyVista disponible")
        except ImportError:
            print("❌ PyVista no disponible")
        
        # Trimesh
        try:
            import trimesh
            self.available_methods.append(('trimesh', 'Trimesh'))
            print("✅ Trimesh disponible")
        except ImportError:
            print("❌ Trimesh no disponible")
        
        # pyfqmr (Fast Quadric Mesh Reduction)
        try:
            import pyfqmr
            self.available_methods.append(('pyfqmr', 'Fast Quadric Mesh Reduction'))
            print("✅ pyfqmr disponible")
        except ImportError:
            print("❌ pyfqmr no disponible")
        
        if not self.available_methods:
            print("❌ Cap biblioteca de simplificació disponible!")
            print("💡 Instal·la alguna amb:")
            print("   pip install pymeshlab")
            print("   pip install pyvista")
            print("   pip install trimesh")
            print("   pip install pyfqmr")
            return False
        
        # Seleccionar mètode per defecte (preferir PyMeshLab)
        if any(method[0] == 'pymeshlab' for method in self.available_methods):
            self.current_method = 'pymeshlab'
            print("🚀 Utilitzant PyMeshLab (més ràpid)")
        else:
            self.current_method = self.available_methods[0][0]
            print(f"🚀 Utilitzant {self.available_methods[0][1]}")
        
        return True
    
    def load_stl(self, file_path):
        """Carrega un fitxer STL de forma eficient"""
        print(f"📁 Carregant STL...")
        
        try:
            # Detectar format
            with open(file_path, 'rb') as f:
                header = f.read(80)
                is_binary = not header.startswith(b'solid ')
            
            if is_binary:
                return self._load_binary_stl(file_path)
            else:
                return self._load_ascii_stl(file_path)
                
        except Exception as e:
            print(f"❌ Error carregant STL: {e}")
            return None, None
    
    def _load_binary_stl(self, file_path):
        """Carrega STL binari de forma optimitzada"""
        try:
            with open(file_path, 'rb') as f:
                # Saltar header
                f.read(80)
                
                # Nombre de triangles
                num_triangles = struct.unpack('<I', f.read(4))[0]
                
                # Llegir tots els triangles d'una vegada
                triangles_data = f.read(num_triangles * 50)  # 50 bytes per triangle
                
                vertices = []
                faces = []
                vertex_map = {}
                
                for i in range(num_triangles):
                    offset = i * 50
                    # Saltar normal (12 bytes)
                    triangle_offset = offset + 12
                    
                    face_vertices = []
                    for j in range(3):
                        vertex_offset = triangle_offset + j * 12
                        x, y, z = struct.unpack('<fff', triangles_data[vertex_offset:vertex_offset + 12])
                        vertex = (round(x, 6), round(y, 6), round(z, 6))  # Arrodonir per deduplicació
                        
                        if vertex not in vertex_map:
                            vertex_map[vertex] = len(vertices)
                            vertices.append(vertex)
                        
                        face_vertices.append(vertex_map[vertex])
                    
                    faces.append(face_vertices)
                
                print(f"📊 Original: {len(vertices):,} vèrtexs, {len(faces):,} cares")
                return np.array(vertices), np.array(faces)
                
        except Exception as e:
            print(f"❌ Error llegint STL binari: {e}")
            return None, None
    
    def _load_ascii_stl(self, file_path):
        """Carrega STL ASCII"""
        try:
            vertices = []
            faces = []
            vertex_map = {}
            
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                if line.startswith('facet normal'):
                    face_vertices = []
                    i += 1  # outer loop
                    
                    # Llegir 3 vèrtexs
                    for _ in range(3):
                        i += 1
                        if i < len(lines):
                            vertex_line = lines[i].strip()
                            if vertex_line.startswith('vertex'):
                                parts = vertex_line.split()
                                if len(parts) >= 4:
                                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                                    vertex = (round(x, 6), round(y, 6), round(z, 6))
                                    
                                    if vertex not in vertex_map:
                                        vertex_map[vertex] = len(vertices)
                                        vertices.append(vertex)
                                    
                                    face_vertices.append(vertex_map[vertex])
                    
                    if len(face_vertices) == 3:
                        faces.append(face_vertices)
                
                i += 1
            
            print(f"📊 Original: {len(vertices):,} vèrtexs, {len(faces):,} cares")
            return np.array(vertices), np.array(faces)
            
        except Exception as e:
            print(f"❌ Error llegint STL ASCII: {e}")
            return None, None
    
    def simplify_pymeshlab(self, vertices, faces, target_vertices):
        """Simplificació amb PyMeshLab (més ràpid)"""
        try:
            import pymeshlab
            
            print("🔄 Aplicant simplificació amb PyMeshLab...")
            
            # Crear MeshSet
            ms = pymeshlab.MeshSet()
            
            # Crear malla
            mesh = pymeshlab.Mesh(vertices, faces)
            ms.add_mesh(mesh)
            
            # Intentar múltiples mètodes de simplificació
            original_vertices = len(vertices)
            target_ratio = target_vertices / original_vertices
            
            success = False
            
            # Mètode 1: Clustering simplification
            try:
                ms.apply_filter('meshing_decimation_clustering', threshold=pymeshlab.Percentage(100 - target_ratio * 100))
                success = True
                print("✅ Simplificació clustering aplicada")
            except:
                pass
            
            # Mètode 2: Quadric edge collapse (si el clustering no funciona)
            if not success:
                try:
                    ms.apply_filter('meshing_decimation_quadric_edge_collapse', targetfacenum=int(len(faces) * target_ratio))
                    success = True
                    print("✅ Simplificació quadric edge collapse aplicada")
                except:
                    pass
            
            # Mètode 3: Simplificació per percentatge
            if not success:
                try:
                    ms.apply_filter('meshing_decimation_quadric_edge_collapse_with_texture', targetperc=target_ratio)
                    success = True
                    print("✅ Simplificació per percentatge aplicada")
                except:
                    pass
            
            if not success:
                print("❌ Cap mètode de PyMeshLab ha funcionat")
                return None, None
            
            # Obtenir malla simplificada
            simplified_mesh = ms.current_mesh()
            new_vertices = simplified_mesh.vertex_matrix()
            new_faces = simplified_mesh.face_matrix()
            
            print(f"📉 Reduït a: {len(new_vertices):,} vèrtexs, {len(new_faces):,} cares")
            return new_vertices, new_faces
            
        except Exception as e:
            print(f"❌ Error amb PyMeshLab: {e}")
            return None, None
    
    def simplify_pyvista(self, vertices, faces, target_vertices):
        """Simplificació amb PyVista"""
        try:
            import pyvista as pv
            
            print("🔄 Aplicant simplificació amb PyVista...")
            
            # Crear malla PyVista
            mesh = pv.PolyData(vertices, np.column_stack([np.full(len(faces), 3), faces]))
            
            # Calcular ratio de reducció
            reduction = 1.0 - (target_vertices / len(vertices))
            
            # Aplicar simplificació
            simplified = mesh.decimate(reduction)
            
            new_vertices = simplified.points
            new_faces = simplified.faces.reshape(-1, 4)[:, 1:4]  # Eliminar el primer column (nombre de punts)
            
            print(f"📉 Reduït a: {len(new_vertices):,} vèrtexs, {len(new_faces):,} cares")
            return new_vertices, new_faces
            
        except Exception as e:
            print(f"❌ Error amb PyVista: {e}")
            return None, None
    
    def simplify_trimesh(self, vertices, faces, target_vertices):
        """Simplificació amb Trimesh"""
        try:
            import trimesh
            
            print("🔄 Aplicant simplificació amb Trimesh...")
            
            # Crear malla Trimesh
            mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
            
            # Aplicar simplificació
            simplified = mesh.simplify_quadric_decimation(target_vertices)
            
            print(f"📉 Reduït a: {len(simplified.vertices):,} vèrtexs, {len(simplified.faces):,} cares")
            return simplified.vertices, simplified.faces
            
        except Exception as e:
            print(f"❌ Error amb Trimesh: {e}")
            return None, None
    
    def simplify_pyfqmr(self, vertices, faces, target_vertices):
        """Simplificació amb pyfqmr (Fast Quadric Mesh Reduction)"""
        try:
            import pyfqmr
            
            print("🔄 Aplicant simplificació amb pyfqmr...")
            
            # Configurar simplificador
            mesh_simplifier = pyfqmr.Simplify()
            mesh_simplifier.setMesh(vertices, faces)
            mesh_simplifier.simplify_mesh(target_count=target_vertices, aggressiveness=7, preserve_border=True)
            
            new_vertices, new_faces, _ = mesh_simplifier.getMesh()
            
            print(f"📉 Reduït a: {len(new_vertices):,} vèrtexs, {len(new_faces):,} cares")
            return new_vertices, new_faces
            
        except Exception as e:
            print(f"❌ Error amb pyfqmr: {e}")
            return None, None
    
    def simplify_mesh(self, vertices, faces, target_vertices):
        """Simplifica la malla amb el mètode seleccionat"""
        start_time = time.time()
        
        if self.current_method == 'pymeshlab':
            result = self.simplify_pymeshlab(vertices, faces, target_vertices)
        elif self.current_method == 'pyvista':
            result = self.simplify_pyvista(vertices, faces, target_vertices)
        elif self.current_method == 'trimesh':
            result = self.simplify_trimesh(vertices, faces, target_vertices)
        elif self.current_method == 'pyfqmr':
            result = self.simplify_pyfqmr(vertices, faces, target_vertices)
        else:
            print(f"❌ Mètode desconegut: {self.current_method}")
            return None, None
        
        elapsed = time.time() - start_time
        print(f"⏱️ Temps de simplificació: {elapsed:.2f} segons")
        
        return result
    
    def save_stl(self, vertices, faces, output_path):
        """Guarda la malla simplificada com STL binari"""
        try:
            print(f"💾 Guardant STL simplificat...")
            
            with open(output_path, 'wb') as f:
                # Header (80 bytes)
                header = b'Simplified with UltraFastMeshSimplifier' + b'\0' * (80 - 39)
                f.write(header)
                
                # Nombre de triangles
                num_triangles = len(faces)
                f.write(struct.pack('<I', num_triangles))
                
                # Triangles
                for face in faces:
                    # Calcular normal
                    v1, v2, v3 = vertices[face[0]], vertices[face[1]], vertices[face[2]]
                    edge1 = v2 - v1
                    edge2 = v3 - v1
                    normal = np.cross(edge1, edge2)
                    normal = normal / (np.linalg.norm(normal) + 1e-8)
                    
                    # Escriure normal
                    f.write(struct.pack('<fff', normal[0], normal[1], normal[2]))
                    
                    # Escriure vèrtexs
                    for vertex_idx in face:
                        vertex = vertices[vertex_idx]
                        f.write(struct.pack('<fff', vertex[0], vertex[1], vertex[2]))
                    
                    # Attribute byte count
                    f.write(struct.pack('<H', 0))
            
            print(f"✅ STL guardat: {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error guardant STL: {e}")
            return False

def create_gui():
    """Crea la interfície gràfica"""
    simplifier = UltraFastMeshSimplifier()
    
    if not simplifier.available_methods:
        messagebox.showerror("Error", "No hi ha biblioteques de simplificació disponibles!")
        return
    
    root = tk.Tk()
    root.title("Ultra Fast Mesh Simplifier")
    root.geometry("600x500")
    
    # Variables
    file_path = tk.StringVar()
    target_vertices = tk.IntVar(value=1000)
    selected_method = tk.StringVar(value=simplifier.current_method)
    
    # Estat
    current_vertices = None
    current_faces = None
    
    def select_file():
        path = filedialog.askopenfilename(
            title="Selecciona fitxer STL",
            filetypes=[("STL files", "*.stl"), ("All files", "*.*")]
        )
        if path:
            file_path.set(path)
            
            # Mostrar informació del fitxer
            try:
                size_mb = os.path.getsize(path) / (1024 * 1024)
                info_label.config(text=f"📁 Fitxer seleccionat: {os.path.basename(path)}\n📊 Mida del fitxer: {size_mb:.1f} MB")
            except:
                info_label.config(text=f"📁 Fitxer seleccionat: {os.path.basename(path)}")
    
    def change_method():
        simplifier.current_method = selected_method.get()
        method_name = next(name for method, name in simplifier.available_methods if method == selected_method.get())
        method_label.config(text=f"🎯 Mètode actiu: {method_name}")
    
    def simplify():
        nonlocal current_vertices, current_faces
        
        if not file_path.get():
            messagebox.showerror("Error", "Selecciona un fitxer STL primer!")
            return
        
        try:
            # Actualizar interfície
            progress_bar.config(mode='indeterminate')
            progress_bar.start()
            root.update()
            
            print("\n" + "="*50)
            print("🚀 INICIANT SIMPLIFICACIÓ...")
            print("="*50)
            
            # Carregar malla
            current_vertices, current_faces = simplifier.load_stl(file_path.get())
            
            if current_vertices is None:
                messagebox.showerror("Error", "No s'ha pogut carregar el fitxer STL!")
                return
            
            # Simplificar
            target = target_vertices.get()
            if target >= len(current_vertices):
                messagebox.showwarning("Advertència", f"El nombre objectiu ({target}) és major o igual que l'original ({len(current_vertices)})!")
                return
            
            simplified_vertices, simplified_faces = simplifier.simplify_mesh(current_vertices, current_faces, target)
            
            if simplified_vertices is None:
                messagebox.showerror("Error", "La simplificació ha fallat!")
                return
            
            # Guardar resultat
            input_path = Path(file_path.get())
            output_path = input_path.parent / f"{input_path.stem}_simplified_{len(simplified_vertices)}v{input_path.suffix}"
            
            if simplifier.save_stl(simplified_vertices, simplified_faces, str(output_path)):
                # Calcular estadístiques
                original_count = len(current_vertices)
                final_count = len(simplified_vertices)
                reduction_percent = ((original_count - final_count) / original_count) * 100
                
                result_text = f"""✅ SIMPLIFICACIÓ COMPLETADA!

📊 Estadístiques:
   • Original: {original_count:,} vèrtexs
   • Simplificat: {final_count:,} vèrtexs
   • Reducció: {reduction_percent:.1f}%

💾 Fitxer guardat:
   {output_path.name}"""
                
                messagebox.showinfo("Èxit", result_text)
                print("\n" + "="*50)
                print("✅ SIMPLIFICACIÓ COMPLETADA!")
                print("="*50)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error durant la simplificació:\n{str(e)}")
            print(f"❌ Error: {e}")
        
        finally:
            progress_bar.stop()
            progress_bar.config(mode='determinate')
    
    # Interfície
    title_label = tk.Label(root, text="🚀 Simplificador STL RÀPID", font=("Arial", 16, "bold"))
    title_label.pack(pady=10)
    
    methods_text = "📊 Mètodes disponibles: " + ", ".join([method for method, _ in simplifier.available_methods])
    methods_label = tk.Label(root, text=methods_text, font=("Arial", 10))
    methods_label.pack(pady=5)
    
    method_name = next(name for method, name in simplifier.available_methods if method == simplifier.current_method)
    method_label = tk.Label(root, text=f"🎯 Mètode actiu: {method_name}", font=("Arial", 10), fg="blue")
    method_label.pack(pady=5)
    
    # Selecció de mètode
    method_frame = tk.Frame(root)
    method_frame.pack(pady=10)
    
    tk.Label(method_frame, text="Mètode de simplificació:", font=("Arial", 10)).pack(side=tk.LEFT)
    
    method_combo = ttk.Combobox(method_frame, textvariable=selected_method, 
                               values=[method for method, _ in simplifier.available_methods],
                               state="readonly", width=15)
    method_combo.pack(side=tk.LEFT, padx=10)
    method_combo.bind('<<ComboboxSelected>>', lambda e: change_method())
    
    # Selecció de fitxer
    file_frame = tk.Frame(root)
    file_frame.pack(pady=10, padx=20, fill=tk.X)
    
    tk.Button(file_frame, text="📁 Seleccionar Fitxer STL", command=select_file, 
             font=("Arial", 12), bg="#4CAF50", fg="white").pack(side=tk.LEFT)
    
    info_label = tk.Label(root, text="Cap fitxer seleccionat", font=("Arial", 10), fg="gray")
    info_label.pack(pady=5)
    
    # Nombre objectiu de vèrtexs
    target_frame = tk.Frame(root)
    target_frame.pack(pady=10)
    
    tk.Label(target_frame, text="🎯 Nombre objectiu de vèrtexs:", font=("Arial", 12)).pack(side=tk.LEFT)
    
    target_entry = tk.Entry(target_frame, textvariable=target_vertices, font=("Arial", 12), width=10)
    target_entry.pack(side=tk.LEFT, padx=10)
    
    # Botó de simplificació
    simplify_button = tk.Button(root, text="🚀 SIMPLIFICAR", command=simplify,
                               font=("Arial", 14, "bold"), bg="#FF9800", fg="white",
                               width=20, height=2)
    simplify_button.pack(pady=20)
    
    # Barra de progrés
    progress_bar = ttk.Progressbar(root, mode='determinate')
    progress_bar.pack(pady=10, padx=20, fill=tk.X)
    
    # Instruccions
    instructions = """📝 Instruccions:
1. Selecciona un fitxer STL
2. Estableix el nombre objectiu de vèrtexs
3. Clica SIMPLIFICAR
4. El resultat es guardarà amb '_simplified' al nom"""
    
    instructions_label = tk.Label(root, text=instructions, font=("Arial", 10), 
                                 justify=tk.LEFT, bg="#f0f0f0", relief=tk.SUNKEN)
    instructions_label.pack(pady=10, padx=20, fill=tk.X)
    
    root.mainloop()

def main():
    """Funció principal"""
    if len(sys.argv) > 1:
        # Mode línia de comandos
        file_path = sys.argv[1]
        target = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
        
        simplifier = UltraFastMeshSimplifier()
        
        if not simplifier.available_methods:
            print("❌ Cap biblioteca disponible!")
            return
        
        print(f"🚀 Simplificant {file_path}")
        print(f"🎯 Objectiu: {target} vèrtexs")
        
        # Carregar
        vertices, faces = simplifier.load_stl(file_path)
        if vertices is None:
            return
        
        # Simplificar
        simplified_vertices, simplified_faces = simplifier.simplify_mesh(vertices, faces, target)
        if simplified_vertices is None:
            return
        
        # Guardar
        input_path = Path(file_path)
        output_path = input_path.parent / f"{input_path.stem}_simplified_{len(simplified_vertices)}v{input_path.suffix}"
        simplifier.save_stl(simplified_vertices, simplified_faces, str(output_path))
        
        print(f"✅ Completat: {output_path}")
    else:
        # Mode GUI
        create_gui()

if __name__ == "__main__":
    main()
