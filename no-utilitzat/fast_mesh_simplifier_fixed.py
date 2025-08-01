#!/usr/bin/env python3
"""
🚀 SIMPLIFICADOR STL RÀPID I EFICIENT - VERSIÓ CORREGIDA
Utilitza múltiples mètodes per garantir que funcioni sempre
"""

import os
import sys
import time
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

def check_dependencies():
    """Comprova les dependències disponibles"""
    available = {}
    
    # PyMeshLab
    try:
        import pymeshlab
        available['pymeshlab'] = True
        print("✅ PyMeshLab disponible")
    except ImportError:
        available['pymeshlab'] = False
        print("❌ PyMeshLab no disponible")
    
    # PyVista  
    try:
        import pyvista as pv
        available['pyvista'] = True
        print("✅ PyVista disponible")
    except ImportError:
        available['pyvista'] = False
        print("❌ PyVista no disponible")
    
    # Trimesh
    try:
        import trimesh
        available['trimesh'] = True
        print("✅ Trimesh disponible")
    except ImportError:
        available['trimesh'] = False
        print("❌ Trimesh no disponible")
    
    # Open3D
    try:
        import open3d as o3d
        available['open3d'] = True
        print("✅ Open3D disponible")
    except ImportError:
        available['open3d'] = False
        print("❌ Open3D no disponible")
    
    return available

def get_pymeshlab_filters():
    """Llista filtres disponibles en PyMeshLab"""
    try:
        import pymeshlab
        ms = pymeshlab.MeshSet()
        
        print("\n🔍 FILTRES DISPONIBLES EN PYMESHLAB:")
        print("=" * 50)
        
        # Obtenir tots els filtres
        filter_list = []
        try:
            # Intentar obtenir la llista de filtres
            ms.print_filter_list()
        except:
            pass
        
        # Buscar filtres de simplificació coneguts
        simplification_filters = [
            'meshing_decimation_quadric_edge_collapse',
            'simplification_quadric_edge_collapse_decimation', 
            'meshing_simplification_quadric_edge_collapse',
            'simplification_clustering_decimation',
            'meshing_decimation_clustering',
            'simplification_edge_collapse',
            'meshing_remove_duplicate_vertices',
            'meshing_remove_unreferenced_vertices'
        ]
        
        working_filters = []
        for filter_name in simplification_filters:
            try:
                # Crear una malla de prova per testejar el filtre
                test_ms = pymeshlab.MeshSet()
                test_ms.create_cube()
                
                # Intentar aplicar el filtre
                if hasattr(test_ms, filter_name):
                    working_filters.append(filter_name)
                    print(f"✅ {filter_name}")
                else:
                    print(f"❌ {filter_name}")
            except Exception as e:
                print(f"❌ {filter_name} - Error: {str(e)[:50]}")
        
        return working_filters
        
    except Exception as e:
        print(f"❌ Error obtenint filtres: {e}")
        return []

def simplify_with_pymeshlab_smart(input_path, output_path, target_vertices):
    """Simplificació intel·ligent amb PyMeshLab"""
    try:
        import pymeshlab
        
        print("🔄 Carregant STL amb PyMeshLab...")
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(input_path)
        
        original_vertices = ms.current_mesh().vertex_number()
        original_faces = ms.current_mesh().face_number()
        
        print(f"📊 Original: {original_vertices:,} vèrtexs, {original_faces:,} cares")
        
        if original_vertices <= target_vertices:
            print("⚠️ La malla ja té menys vèrtexs que l'objectiu")
            ms.save_current_mesh(output_path)
            return True
        
        # Calcular percentatge de reducció
        reduction_ratio = target_vertices / original_vertices
        face_reduction = max(0.1, reduction_ratio * 0.8)  # Reducció més agressiva de cares
        
        print(f"🎯 Objectiu: {target_vertices:,} vèrtexs (reducció {1-reduction_ratio:.1%})")
        
        # Provar diferents mètodes de simplificació
        methods = [
            # Mètode 1: Quadric Edge Collapse moderno
            {
                'name': 'Quadric Edge Collapse (modern)',
                'function': lambda: ms.meshing_decimation_quadric_edge_collapse(
                    targetfacenum=int(original_faces * face_reduction),
                    preservenormal=True,
                    preservetopology=True,
                    optimalplacement=True
                )
            },
            # Mètode 2: Clustering Decimation
            {
                'name': 'Clustering Decimation', 
                'function': lambda: ms.meshing_decimation_clustering(
                    threshold=pymeshlab.Percentage(100 * (1 - reduction_ratio))
                )
            },
            # Mètode 3: Quadric Edge Collapse clàssic
            {
                'name': 'Quadric Edge Collapse (classic)',
                'function': lambda: ms.apply_filter('meshing_decimation_quadric_edge_collapse', 
                                                   targetfacenum=int(original_faces * face_reduction))
            },
            # Mètode 4: Simplificació per clustering
            {
                'name': 'Simplification Clustering',
                'function': lambda: ms.apply_filter('simplification_clustering_decimation',
                                                   threshold=pymeshlab.Percentage(100 * (1 - reduction_ratio)))
            }
        ]
        
        success = False
        for method in methods:
            try:
                print(f"🔄 Provant: {method['name']}")
                
                # Crear còpia de seguretat de la malla
                ms_backup = pymeshlab.MeshSet()
                ms_backup.load_new_mesh(input_path)
                
                # Aplicar mètode
                method['function']()
                
                # Verificar resultat
                new_vertices = ms.current_mesh().vertex_number()
                new_faces = ms.current_mesh().face_number()
                
                if new_vertices > 0 and new_faces > 0:
                    print(f"✅ {method['name']} - {new_vertices:,} vèrtexs, {new_faces:,} cares")
                    
                    # Si estem massa lluny de l'objectiu, provar ajustar
                    if new_vertices > target_vertices * 1.5:
                        print("🔄 Aplicant reducció adicional...")
                        try:
                            additional_reduction = target_vertices / new_vertices
                            ms.meshing_decimation_quadric_edge_collapse(
                                targetfacenum=int(new_faces * additional_reduction * 0.8)
                            )
                            final_vertices = ms.current_mesh().vertex_number()
                            print(f"📉 Després de reducció adicional: {final_vertices:,} vèrtexs")
                        except:
                            pass
                    
                    success = True
                    break
                    
            except Exception as e:
                print(f"❌ {method['name']} falló: {str(e)[:100]}")
                # Restaurar còpia de seguretat
                ms = ms_backup
                continue
        
        if not success:
            print("❌ Tots els mètodes de PyMeshLab han fallat")
            return False
        
        # Neteja final
        try:
            print("🧹 Aplicant neteja final...")
            ms.meshing_remove_duplicate_vertices()
            ms.meshing_remove_unreferenced_vertices()
        except:
            print("⚠️ Neteja parcial aplicada")
        
        # Guardar resultat
        ms.save_current_mesh(output_path)
        
        final_vertices = ms.current_mesh().vertex_number()
        final_faces = ms.current_mesh().face_number()
        
        reduction_achieved = (original_vertices - final_vertices) / original_vertices
        
        print(f"✅ Simplificació completa!")
        print(f"📊 Final: {final_vertices:,} vèrtexs, {final_faces:,} cares")
        print(f"📉 Reducció aconseguida: {reduction_achieved:.1%}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en PyMeshLab: {e}")
        traceback.print_exc()
        return False

def simplify_with_pyvista(input_path, output_path, target_vertices):
    """Simplificació amb PyVista"""
    try:
        import pyvista as pv
        
        print("🔄 Carregant STL amb PyVista...")
        mesh = pv.read(input_path)
        
        original_vertices = mesh.n_points
        print(f"📊 Original: {original_vertices:,} vèrtexs")
        
        if original_vertices <= target_vertices:
            print("⚠️ La malla ja té menys vèrtexs que l'objectiu")
            mesh.save(output_path)
            return True
        
        # Calcular fracció de reducció
        reduction_fraction = 1.0 - (target_vertices / original_vertices)
        reduction_fraction = max(0.05, min(0.95, reduction_fraction))  # Limitar entre 5% i 95%
        
        print(f"🎯 Objectiu: {target_vertices:,} vèrtexs (reducció {reduction_fraction:.1%})")
        
        # Aplicar simplificació
        print("🔄 Aplicant simplificació...")
        simplified = mesh.decimate(reduction_fraction)
        
        final_vertices = simplified.n_points
        reduction_achieved = (original_vertices - final_vertices) / original_vertices
        
        print(f"✅ Simplificació completa!")
        print(f"📊 Final: {final_vertices:,} vèrtexs")
        print(f"📉 Reducció aconseguida: {reduction_achieved:.1%}")
        
        # Guardar
        simplified.save(output_path)
        return True
        
    except Exception as e:
        print(f"❌ Error en PyVista: {e}")
        return False

def simplify_with_trimesh(input_path, output_path, target_vertices):
    """Simplificació amb Trimesh"""
    try:
        import trimesh
        
        print("🔄 Carregant STL amb Trimesh...")
        mesh = trimesh.load_mesh(input_path)
        
        original_vertices = len(mesh.vertices)
        print(f"📊 Original: {original_vertices:,} vèrtexs")
        
        if original_vertices <= target_vertices:
            print("⚠️ La malla ja té menys vèrtexs que l'objectiu")
            mesh.export(output_path)
            return True
        
        print(f"🎯 Objectiu: {target_vertices:,} vèrtexs")
        
        # Simplificar amb Trimesh
        print("🔄 Aplicant simplificació...")
        simplified = mesh.simplify_quadric_decimation(face_count=target_vertices * 2)
        
        final_vertices = len(simplified.vertices)
        reduction_achieved = (original_vertices - final_vertices) / original_vertices
        
        print(f"✅ Simplificació completa!")
        print(f"📊 Final: {final_vertices:,} vèrtexs")
        print(f"📉 Reducció aconseguida: {reduction_achieved:.1%}")
        
        # Guardar
        simplified.export(output_path)
        return True
        
    except Exception as e:
        print(f"❌ Error en Trimesh: {e}")
        return False

def simplify_with_open3d(input_path, output_path, target_vertices):
    """Simplificació amb Open3D"""
    try:
        import open3d as o3d
        
        print("🔄 Carregant STL amb Open3D...")
        mesh = o3d.io.read_triangle_mesh(input_path)
        
        original_vertices = len(mesh.vertices)
        print(f"📊 Original: {original_vertices:,} vèrtexs")
        
        if original_vertices <= target_vertices:
            print("⚠️ La malla ja té menys vèrtexs que l'objectiu")
            o3d.io.write_triangle_mesh(output_path, mesh)
            return True
        
        print(f"🎯 Objectiu: {target_vertices:,} vèrtexs")
        
        # Simplificar
        print("🔄 Aplicant simplificació...")
        simplified = mesh.simplify_quadric_decimation(target_number_of_triangles=target_vertices)
        
        final_vertices = len(simplified.vertices)
        reduction_achieved = (original_vertices - final_vertices) / original_vertices
        
        print(f"✅ Simplificació completa!")
        print(f"📊 Final: {final_vertices:,} vèrtexs")
        print(f"📉 Reducció aconseguida: {reduction_achieved:.1%}")
        
        # Guardar
        o3d.io.write_triangle_mesh(output_path, simplified)
        return True
        
    except Exception as e:
        print(f"❌ Error en Open3D: {e}")
        return False

class FastMeshSimplifierGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🚀 Simplificador STL Ràpid - VERSIÓ CORREGIDA")
        self.root.geometry("800x600")
        
        self.input_path = None
        self.output_path = None
        
        self.available_methods = check_dependencies()
        self.setup_ui()
    
    def setup_ui(self):
        # Títol
        title = tk.Label(self.root, text="🚀 Simplificador STL RÀPID - VERSIÓ CORREGIDA", 
                        font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Frame de mètodes
        methods_frame = tk.LabelFrame(self.root, text="Mètodes Disponibles", font=("Arial", 12))
        methods_frame.pack(fill="x", padx=10, pady=5)
        
        self.method_var = tk.StringVar()
        methods = []
        
        if self.available_methods.get('pymeshlab'):
            methods.append(("PyMeshLab (Recomanat)", "pymeshlab"))
        if self.available_methods.get('pyvista'):
            methods.append(("PyVista", "pyvista"))
        if self.available_methods.get('trimesh'):
            methods.append(("Trimesh", "trimesh"))
        if self.available_methods.get('open3d'):
            methods.append(("Open3D", "open3d"))
        
        if not methods:
            tk.Label(methods_frame, text="❌ Cap mètode disponible! Instal·la: pip install pymeshlab pyvista trimesh open3d",
                    fg="red").pack(pady=5)
        else:
            for i, (label, value) in enumerate(methods):
                rb = tk.Radiobutton(methods_frame, text=label, variable=self.method_var, value=value)
                rb.pack(anchor="w", padx=10)
                if i == 0:  # Seleccionar el primer per defecte
                    rb.select()
        
        # Frame de fitxer
        file_frame = tk.LabelFrame(self.root, text="Selecció de Fitxer", font=("Arial", 12))
        file_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Button(file_frame, text="📁 Seleccionar Fitxer STL", 
                 command=self.select_input_file).pack(pady=5)
        
        self.file_label = tk.Label(file_frame, text="Cap fitxer seleccionat", fg="gray")
        self.file_label.pack(pady=5)
        
        # Frame de configuració
        config_frame = tk.LabelFrame(self.root, text="Configuració", font=("Arial", 12))
        config_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(config_frame, text="Nombre objectiu de vèrtexs:").pack(anchor="w", padx=10)
        
        self.target_var = tk.StringVar(value="5000")
        target_frame = tk.Frame(config_frame)
        target_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Entry(target_frame, textvariable=self.target_var, width=10).pack(side="left")
        
        # Botons ràpids
        quick_frame = tk.Frame(target_frame)
        quick_frame.pack(side="left", padx=(10, 0))
        
        quick_values = [500, 1000, 2000, 5000, 10000]
        for val in quick_values:
            tk.Button(quick_frame, text=str(val), width=5,
                     command=lambda v=val: self.target_var.set(str(v))).pack(side="left", padx=2)
        
        # Frame d'acció
        action_frame = tk.Frame(self.root)
        action_frame.pack(fill="x", padx=10, pady=20)
        
        self.simplify_btn = tk.Button(action_frame, text="🚀 SIMPLIFICAR", 
                                     command=self.simplify_mesh, 
                                     font=("Arial", 14, "bold"),
                                     bg="#4CAF50", fg="white")
        self.simplify_btn.pack(pady=10)
        
        # Debug frame
        debug_frame = tk.LabelFrame(self.root, text="Debug PyMeshLab", font=("Arial", 12))
        debug_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Button(debug_frame, text="🔍 Llistar Filtres PyMeshLab", 
                 command=self.debug_pymeshlab).pack(pady=5)
        
        # Frame de log
        log_frame = tk.LabelFrame(self.root, text="Log", font=("Arial", 12))
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10)
        scrollbar = tk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def log(self, message):
        """Afegeix missatge al log"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        print(message)  # També imprimir a consola
    
    def select_input_file(self):
        """Selecciona fitxer d'entrada"""
        file_path = filedialog.askopenfilename(
            title="Selecciona fitxer STL",
            filetypes=[("Fitxers STL", "*.stl *.STL"), ("Tots", "*.*")]
        )
        
        if file_path:
            self.input_path = file_path
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
            
            display_text = f"📁 {os.path.basename(file_path)} ({file_size:.1f} MB)"
            self.file_label.config(text=display_text, fg="black")
            
            # Generar nom de sortida
            input_path = Path(file_path)
            self.output_path = str(input_path.with_stem(f"{input_path.stem}_simplified"))
    
    def debug_pymeshlab(self):
        """Debug PyMeshLab filtres"""
        self.log("🔍 ANALITZANT FILTRES PYMESHLAB...")
        if not self.available_methods.get('pymeshlab'):
            self.log("❌ PyMeshLab no està disponible")
            return
        
        working_filters = get_pymeshlab_filters()
        self.log(f"✅ Filtres de simplificació trobats: {len(working_filters)}")
        for f in working_filters:
            self.log(f"   • {f}")
    
    def simplify_mesh(self):
        """Simplifica la malla"""
        if not self.input_path:
            messagebox.showerror("Error", "Selecciona un fitxer STL primer")
            return
        
        try:
            target_vertices = int(self.target_var.get())
            if target_vertices <= 0:
                raise ValueError("El nombre de vèrtexs ha de ser positiu")
        except ValueError as e:
            messagebox.showerror("Error", f"Nombre de vèrtexs invàlid: {e}")
            return
        
        method = self.method_var.get()
        if not method:
            messagebox.showerror("Error", "Selecciona un mètode de simplificació")
            return
        
        self.log(f"🚀 INICIANT SIMPLIFICACIÓ AMB {method.upper()}...")
        self.log(f"📁 Fitxer: {os.path.basename(self.input_path)}")
        self.log(f"🎯 Objectiu: {target_vertices:,} vèrtexs")
        self.log("=" * 50)
        
        start_time = time.time()
        success = False
        
        # Redirigir stdout al log
        import sys
        original_stdout = sys.stdout
        
        class LogRedirect:
            def write(self, text):
                if text.strip():
                    self.parent.log(text.strip())
                original_stdout.write(text)
                
            def flush(self):
                original_stdout.flush()
        
        log_redirect = LogRedirect()
        log_redirect.parent = self
        sys.stdout = log_redirect
        
        try:
            if method == "pymeshlab":
                success = simplify_with_pymeshlab_smart(self.input_path, self.output_path, target_vertices)
            elif method == "pyvista":
                success = simplify_with_pyvista(self.input_path, self.output_path, target_vertices)
            elif method == "trimesh":
                success = simplify_with_trimesh(self.input_path, self.output_path, target_vertices)
            elif method == "open3d":
                success = simplify_with_open3d(self.input_path, self.output_path, target_vertices)
        
        finally:
            sys.stdout = original_stdout
        
        elapsed_time = time.time() - start_time
        
        if success:
            self.log(f"✅ SIMPLIFICACIÓ COMPLETADA en {elapsed_time:.1f}s")
            self.log(f"💾 Fitxer guardat: {os.path.basename(self.output_path)}")
            
            messagebox.showinfo("Èxit", 
                               f"Simplificació completada!\n"
                               f"Temps: {elapsed_time:.1f}s\n"
                               f"Fitxer: {os.path.basename(self.output_path)}")
        else:
            self.log(f"❌ SIMPLIFICACIÓ FALLIDA després de {elapsed_time:.1f}s")
            messagebox.showerror("Error", "La simplificació ha fallat. Revisa el log per més detalls.")
    
    def run(self):
        self.root.mainloop()

def main():
    """Funció principal"""
    print("🚀 SIMPLIFICADOR STL RÀPID - VERSIÓ CORREGIDA")
    print("=" * 60)
    
    # Comprovar dependències
    available = check_dependencies()
    
    if not any(available.values()):
        print("\n❌ Cap llibreria de simplificació disponible!")
        print("💡 Instal·la almenys una d'aquestes:")
        print("   pip install pymeshlab")
        print("   pip install pyvista")
        print("   pip install trimesh")
        print("   pip install open3d")
        return
    
    # Llançar GUI
    app = FastMeshSimplifierGUI()
    app.run()

if __name__ == "__main__":
    main()
