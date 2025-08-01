#!/usr/bin/env python3
"""
PackAssist - GUI Integrada amb Visualització STL Real
Utilitza els components existents i mostra les peces STL reals
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from pathlib import Path
import numpy as np

# Afegir paths necessaris al principi
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, 'actiu', 'src'))
sys.path.insert(0, os.path.join(current_dir, 'actiu', 'tools', 'mesh_simplifiers'))
sys.path.insert(0, os.path.join(current_dir, 'src'))

# Imports necessaris
try:
    import trimesh
except ImportError:
    trimesh = None

try:
    import pyvista as pv
except ImportError:
    pv = None

class PackAssistIntegratedApp:
    """Aplicació PackAssist integrada amb components existents"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PackAssist - Empaquetament Intel·ligent amb STL Real")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        
        # Variables principals
        self.stl_file_path = None
        self.original_mesh = None
        self.original_mesh_info = None
        self.simplified_mesh = None
        self.simplified_mesh_info = None
        self.optimization_results = None
        
        # Imports dels components existents
        self.setup_components()
        
        # Setup interfície
        self.setup_styles()
        self.create_widgets()
        
    def setup_components(self):
        """Configura els components existents amb millor gestió d'errors"""
        self.components_loaded = False
        self.optimizer_func = None
        self.stl_loader = None
        self.simplifier_methods = {}
        
        print("Configurant components...")
        
        # Comprovar dependències disponibles
        self.available_libs = self.check_dependencies()
        
        # Carregar optimitzador
        self.load_optimizer()
        
        # Carregar simplificadors
        self.load_simplifiers()
        
        # Carregar STL loader
        self.load_stl_loader()
            
        self.components_loaded = True
        
    def check_dependencies(self):
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
        
    def load_optimizer(self):
        """Carrega l'optimitzador des del codi existent"""
        try:
            # Carregar des de packassist.optimizer
            from packassist.optimizer import optimize_packing
            self.optimizer_func = optimize_packing
            print("✅ Optimitzador carregat des de packassist.optimizer")
        except Exception as e:
            print(f"⚠️ No s'ha pogut carregar l'optimitzador: {e}")
            self.optimizer_func = None
            
    def load_simplifiers(self):
        """Carrega els simplificadors disponibles"""
        self.simplifier_methods = {}
        
        # Mètode 1: PyMeshLab (millor qualitat)
        if self.available_libs.get('pymeshlab'):
            self.simplifier_methods['pymeshlab'] = self.simplify_with_pymeshlab
            
        # Mètode 2: Trimesh (ràpid)
        if self.available_libs.get('trimesh'):
            self.simplifier_methods['trimesh'] = self.simplify_with_trimesh
            
        # Mètode 3: Open3D (alternatiu)
        if self.available_libs.get('open3d'):
            self.simplifier_methods['open3d'] = self.simplify_with_open3d
            
        print(f"✅ {len(self.simplifier_methods)} mètodes de simplificació carregats")
        
    def load_stl_loader(self):
        """Carrega el STL loader"""
        try:
            # Usar trimesh com a loader principal
            if self.available_libs.get('trimesh'):
                self.stl_loader = self.load_stl_with_trimesh
                print("✅ STL loader (trimesh) disponible")
            else:
                print("⚠️ STL loader no disponible")
                self.stl_loader = None
        except Exception as e:
            print(f"⚠️ Error carregant STL loader: {e}")
            self.stl_loader = None
            
    def load_stl_with_trimesh(self, file_path):
        """Carrega STL amb trimesh"""
        try:
            mesh = trimesh.load(file_path)
            return {
                'mesh': mesh,
                'vertices': len(mesh.vertices),
                'faces': len(mesh.faces),
                'volume': getattr(mesh, 'volume', 0),
                'area': getattr(mesh, 'area', 0)
            }
        except Exception as e:
            raise Exception(f"Error carregant STL: {e}")
            
    def simplify_with_pymeshlab(self, mesh, target_vertices, preserve_volume=True):
        """Simplifica amb PyMeshLab (millor qualitat)"""
        try:
            import pymeshlab
            
            ms = pymeshlab.MeshSet()
            
            # Convertir trimesh a pymeshlab
            vertices = mesh.vertices
            faces = mesh.faces
            
            pml_mesh = pymeshlab.Mesh(vertices, faces)
            ms.add_mesh(pml_mesh)
            
            # Aplicar simplificació quadric edge collapse
            ms.apply_filter('meshing_decimation_quadric_edge_collapse', 
                           targetfacenum=target_vertices//2)
            
            # Obtenir malla simplificada
            simplified_mesh_data = ms.current_mesh()
            
            # Convertir de nou a trimesh
            simplified_mesh = trimesh.Trimesh(
                vertices=simplified_mesh_data.vertex_matrix(),
                faces=simplified_mesh_data.face_matrix()
            )
            
            return simplified_mesh
            
        except Exception as e:
            raise Exception(f"Error amb PyMeshLab: {e}")
            
    def simplify_with_trimesh(self, mesh, target_vertices, preserve_volume=True):
        """Simplifica amb Trimesh (ràpid)"""
        try:
            # Usar decimació quadric de trimesh
            simplified_mesh = mesh.simplify_quadric_decimation(target_vertices)
            
            if simplified_mesh.is_empty:
                # Fallback amb ratio
                target_faces = max(12, target_vertices // 2)
                simplified_mesh = mesh.simplify_quadric_decimation(face_count=target_faces)
                
            return simplified_mesh
            
        except Exception as e:
            raise Exception(f"Error amb Trimesh: {e}")
            
    def simplify_with_open3d(self, mesh, target_vertices, preserve_volume=True):
        """Simplifica amb Open3D (alternatiu)"""
        try:
            import open3d as o3d
            
            # Convertir trimesh a open3d
            o3d_mesh = o3d.geometry.TriangleMesh()
            o3d_mesh.vertices = o3d.utility.Vector3dVector(mesh.vertices)
            o3d_mesh.triangles = o3d.utility.Vector3iVector(mesh.faces)
            
            # Simplificar
            simplified_o3d = o3d_mesh.simplify_quadric_decimation(target_vertices)
            
            # Convertir de nou a trimesh
            vertices = np.asarray(simplified_o3d.vertices)
            faces = np.asarray(simplified_o3d.triangles)
            
            simplified_mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
            
            return simplified_mesh
            
        except Exception as e:
            raise Exception(f"Error amb Open3D: {e}")

    def setup_styles(self):
        """Configura estils moderns"""
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except:
            pass
            
        self.root.configure(bg='#f8f9fa')
        
        # Estils personalitzats
        style.configure('Title.TLabel', 
                       font=('Arial', 16, 'bold'),
                       background='#f8f9fa',
                       foreground='#2c3e50')
                       
        style.configure('Step.TLabel',
                       font=('Arial', 11, 'bold'),
                       background='#f8f9fa',
                       foreground='#3498db')
                       
        style.configure('Info.TLabel',
                       font=('Arial', 9),
                       background='#f8f9fa',
                       foreground='#7f8c8d')
                       
    def create_widgets(self):
        """Crea la interfície principal amb panells"""
        # Notebook principal amb pestanyes
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pestanya 1: Importar i Visualitzar
        self.tab_import = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_import, text="📂 1. Importar STL")
        self.create_import_tab()
        
        # Pestanya 2: Reduir Complexitat
        self.tab_simplify = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_simplify, text="🔧 2. Reduir Complexitat")
        self.create_simplify_tab()
        
        # Pestanya 3: Optimitzar
        self.tab_optimize = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_optimize, text="⚡ 3. Optimitzar")
        self.create_optimize_tab()
        
        # Pestanya 4: Resultats 3D
        self.tab_results = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_results, text="🎮 4. Visualitzar")
        self.create_results_tab()
        
    def create_import_tab(self):
        """Crea la pestanya d'importació"""
        main_frame = ttk.Frame(self.tab_import, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Títol
        title_label = ttk.Label(main_frame, text="📂 Importar Fitxer STL", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Frame de selecció
        select_frame = ttk.LabelFrame(main_frame, text="Seleccionar Fitxer", padding="15")
        select_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.import_btn = ttk.Button(select_frame, text="🔍 Seleccionar STL", 
                                    command=self.import_stl, width=20)
        self.import_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.file_label = ttk.Label(select_frame, text="Cap fitxer seleccionat")
        self.file_label.pack(side=tk.LEFT)
        
        # Frame d'informació original
        self.original_info_frame = ttk.LabelFrame(main_frame, text="STL Original", padding="15")
        self.original_info_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.original_info_text = tk.Text(self.original_info_frame, height=10, wrap=tk.WORD)
        orig_scrollbar = ttk.Scrollbar(self.original_info_frame, command=self.original_info_text.yview)
        self.original_info_text.configure(yscrollcommand=orig_scrollbar.set)
        
        self.original_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        orig_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Botó per visualitzar original en 3D
        self.view_original_btn = ttk.Button(main_frame, text="🎮 Visualitzar Original 3D", 
                                           command=self.view_original_3d, state='disabled')
        self.view_original_btn.pack(pady=10)
        
    def create_simplify_tab(self):
        """Crea la pestanya de reducció de complexitat"""
        main_frame = ttk.Frame(self.tab_simplify, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Títol
        title_label = ttk.Label(main_frame, text="🔧 Reduir Complexitat de la Malla", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Controls de simplificació
        controls_frame = ttk.LabelFrame(main_frame, text="Controls de Reducció", padding="15")
        controls_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Selector de mètode (amb més opcions)
        ttk.Label(controls_frame, text="Mètode de reducció:").pack(anchor=tk.W)
        self.simplify_method = tk.StringVar(value="quadric_advanced")
        method_frame = ttk.Frame(controls_frame)
        method_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(method_frame, text="Quadric Avançat", variable=self.simplify_method, value="quadric_advanced").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(method_frame, text="Clustering Ràpid", variable=self.simplify_method, value="clustering").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(method_frame, text="Preservar Detalls", variable=self.simplify_method, value="edge_length").pack(side=tk.LEFT)
        
        # Slider per vèrtexs objectiu (millor rang)
        ttk.Label(controls_frame, text="Nivell de reducció:").pack(anchor=tk.W, pady=(10, 0))
        
        self.target_vertices = tk.IntVar(value=1000)
        self.vertices_scale = tk.Scale(controls_frame, from_=100, to=50000,
                                      orient=tk.HORIZONTAL, variable=self.target_vertices,
                                      command=self.update_vertices_label)
        self.vertices_scale.pack(fill=tk.X, pady=5)
        
        self.vertices_label = ttk.Label(controls_frame, text="1000 vèrtexs")
        self.vertices_label.pack(anchor=tk.W)
        
        # Opció per preservar volum
        self.preserve_volume = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls_frame, text="Preservar volum original", 
                       variable=self.preserve_volume).pack(anchor=tk.W, pady=(10, 0))
        
        # Botó de simplificació millorat
        self.simplify_btn = ttk.Button(controls_frame, text="🚀 Reduir Complexitat", 
                                      command=self.simplify_mesh, state='disabled')
        self.simplify_btn.pack(pady=10)
        
        # Frame de comparació amb millor layout
        comparison_frame = ttk.LabelFrame(main_frame, text="Comparació Original vs Optimitzada", padding="15")
        comparison_frame.pack(fill=tk.BOTH, expand=True)
        
        # Dividir en dues columnes amb millor organització
        left_frame = ttk.Frame(comparison_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        right_frame = ttk.Frame(comparison_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Info original
        ttk.Label(left_frame, text="📊 Malla Original", style='Step.TLabel').pack()
        self.original_stats = tk.Text(left_frame, height=8, wrap=tk.WORD)
        self.original_stats.pack(fill=tk.BOTH, expand=True, pady=5)
        
        orig_btn_frame = ttk.Frame(left_frame)
        orig_btn_frame.pack(fill=tk.X, pady=5)
        
        self.view_orig_btn = ttk.Button(orig_btn_frame, text="🎮 Visualitzar 3D", 
                                       command=self.view_original_3d, state='disabled')
        self.view_orig_btn.pack(side=tk.LEFT)
        
        # Info optimitzada
        ttk.Label(right_frame, text="📊 Malla Optimitzada", style='Step.TLabel').pack()
        self.simplified_stats = tk.Text(right_frame, height=8, wrap=tk.WORD)
        self.simplified_stats.pack(fill=tk.BOTH, expand=True, pady=5)
        
        simp_btn_frame = ttk.Frame(right_frame)
        simp_btn_frame.pack(fill=tk.X, pady=5)
        
        self.view_simp_btn = ttk.Button(simp_btn_frame, text="🎮 Visualitzar 3D", 
                                       command=self.view_simplified_3d, state='disabled')
        self.view_simp_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.compare_btn = ttk.Button(simp_btn_frame, text="⚖️ Comparar Ambdues", 
                                     command=self.compare_meshes_3d, state='disabled')
        self.compare_btn.pack(side=tk.LEFT)
        
    def create_optimize_tab(self):
        """Crea la pestanya d'optimització"""
        main_frame = ttk.Frame(self.tab_optimize, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Títol
        title_label = ttk.Label(main_frame, text="⚡ Optimitzar Empaquetament", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Configuració de la caixa
        box_frame = ttk.LabelFrame(main_frame, text="Dimensions de la Caixa (mm)", padding="15")
        box_frame.pack(fill=tk.X, pady=(0, 20))
        
        dims_frame = ttk.Frame(box_frame)
        dims_frame.pack(fill=tk.X)
        
        ttk.Label(dims_frame, text="Llargada:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.box_length = tk.StringVar(value="200")
        ttk.Entry(dims_frame, textvariable=self.box_length, width=10).grid(row=0, column=1, padx=5)
        
        ttk.Label(dims_frame, text="Amplada:").grid(row=0, column=2, sticky=tk.W, padx=(20, 5))
        self.box_width = tk.StringVar(value="150")
        ttk.Entry(dims_frame, textvariable=self.box_width, width=10).grid(row=0, column=3, padx=5)
        
        ttk.Label(dims_frame, text="Altura:").grid(row=0, column=4, sticky=tk.W, padx=(20, 5))
        self.box_height = tk.StringVar(value="100")
        ttk.Entry(dims_frame, textvariable=self.box_height, width=10).grid(row=0, column=5, padx=5)
        
        # Opcions d'optimització
        options_frame = ttk.LabelFrame(main_frame, text="Opcions d'Optimització", padding="15")
        options_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.use_simplified = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Usar malla simplificada (si està disponible)", 
                       variable=self.use_simplified).pack(anchor=tk.W)
        
        self.allow_rotation = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Permetre rotacions automàtiques", 
                       variable=self.allow_rotation).pack(anchor=tk.W)
        
        # Botó d'optimització
        self.optimize_btn = ttk.Button(main_frame, text="🚀 Calcular Empaquetament Òptim", 
                                      command=self.optimize_packing, state='disabled')
        self.optimize_btn.pack(pady=10)
        
        # Barra de progrés
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=10)
        
        # Resultats
        results_frame = ttk.LabelFrame(main_frame, text="Resultats", padding="15")
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        self.results_text = tk.Text(results_frame, height=10, wrap=tk.WORD)
        results_scrollbar = ttk.Scrollbar(results_frame, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=results_scrollbar.set)
        
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def create_results_tab(self):
        """Crea la pestanya de resultats 3D"""
        main_frame = ttk.Frame(self.tab_results, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Títol
        title_label = ttk.Label(main_frame, text="🎮 Visualització 3D del Resultat", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Botons de visualització
        viz_frame = ttk.LabelFrame(main_frame, text="Opcions de Visualització", padding="15")
        viz_frame.pack(fill=tk.X, pady=(0, 20))
        
        btn_frame = ttk.Frame(viz_frame)
        btn_frame.pack(fill=tk.X)
        
        self.visualize_3d_btn = ttk.Button(btn_frame, text="🎮 Visualitzar Empaquetament 3D", 
                                          command=self.visualize_3d, state='disabled')
        self.visualize_3d_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.export_result_btn = ttk.Button(btn_frame, text="💾 Exportar Resultat", 
                                           command=self.export_results, state='disabled')
        self.export_result_btn.pack(side=tk.LEFT)
        
        # Resum final
        summary_frame = ttk.LabelFrame(main_frame, text="Resum Final", padding="15")
        summary_frame.pack(fill=tk.BOTH, expand=True)
        
        self.summary_text = tk.Text(summary_frame, height=15, wrap=tk.WORD)
        summary_scrollbar = ttk.Scrollbar(summary_frame, command=self.summary_text.yview)
        self.summary_text.configure(yscrollcommand=summary_scrollbar.set)
        
        self.summary_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        summary_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Text inicial
        self.summary_text.insert(tk.END, "✨ Benvingut a PackAssist!\n\n")
        self.summary_text.insert(tk.END, "Segueix aquests passos:\n")
        self.summary_text.insert(tk.END, "1. 📂 Importa un fitxer STL\n")
        self.summary_text.insert(tk.END, "2. 🔧 Simplifica la malla (opcional)\n")
        self.summary_text.insert(tk.END, "3. ⚡ Configura i optimitza l'empaquetament\n")
        self.summary_text.insert(tk.END, "4. 🎮 Visualitza els resultats en 3D\n\n")
        self.summary_text.insert(tk.END, "Els resultats es mostraran aquí un cop completat el procés.\n")
        self.summary_text.config(state='disabled')
        
    def import_stl(self):
        """Importa un fitxer STL utilitzant el loader existent"""
        file_path = filedialog.askopenfilename(
            title="Selecciona un fitxer STL",
            filetypes=[
                ("Fitxers STL", "*.stl *.STL"),
                ("Tots els fitxers", "*.*")
            ]
        )
        
        if file_path:
            try:
                self.stl_file_path = file_path
                filename = os.path.basename(file_path)
                self.file_label.config(text=f"📁 {filename}")
                
                # Carregar malla amb trimesh (fallback si no hi ha stl_loader)
                if self.stl_loader:
                    self.original_mesh_info = self.stl_loader(file_path)
                    self.original_mesh = self.original_mesh_info.get('mesh')
                else:
                    # Fallback amb trimesh
                    import trimesh
                    self.original_mesh = trimesh.load(file_path)
                    self.original_mesh_info = {
                        'mesh': self.original_mesh,
                        'vertices': len(self.original_mesh.vertices),
                        'faces': len(self.original_mesh.faces),
                        'volume': getattr(self.original_mesh, 'volume', 0),
                        'area': getattr(self.original_mesh, 'area', 0)
                    }
                
                # Mostrar informació
                self.display_mesh_info(self.original_mesh_info, self.original_info_text)
                self.display_mesh_info(self.original_mesh_info, self.original_stats)
                
                # Habilitar botons
                self.view_original_btn.config(state='normal')
                self.view_orig_btn.config(state='normal')
                self.simplify_btn.config(state='normal')
                self.optimize_btn.config(state='normal')
                
                # Actualitzar slider de simplificació
                max_vertices = self.original_mesh_info.get('vertices', 1000)
                self.vertices_scale.config(to=max_vertices)
                self.target_vertices.set(max_vertices // 2)
                
                messagebox.showinfo("Èxit", f"STL carregat correctament: {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"No s'ha pogut carregar el fitxer STL:\n{e}")
                self.stl_file_path = None
                self.file_label.config(text="❌ Error carregant fitxer")
                
    def display_mesh_info(self, mesh_info, text_widget):
        """Mostra informació detallada de la malla en un widget de text"""
        text_widget.config(state='normal')
        text_widget.delete(1.0, tk.END)
        
        if mesh_info:
            info = f"📊 Informació de la Malla:\n"
            info += f"=" * 30 + "\n"
            info += f"   • Vèrtexs: {mesh_info.get('vertices', 0):,}\n"
            info += f"   • Cares: {mesh_info.get('faces', 0):,}\n"
            
            # Volum
            volume = mesh_info.get('volume', 0)
            if volume > 0:
                if volume > 1000000:
                    info += f"   • Volum: {volume/1000000:.2f} cm³\n"
                else:
                    info += f"   • Volum: {volume:.2f} mm³\n"
            
            # Àrea
            area = mesh_info.get('area', 0)
            if area > 0:
                if area > 10000:
                    info += f"   • Àrea: {area/100:.2f} cm²\n"
                else:
                    info += f"   • Àrea: {area:.2f} mm²\n"
                
            # Calcular dimensions aproximades
            if 'mesh' in mesh_info and hasattr(mesh_info['mesh'], 'bounds'):
                bounds = mesh_info['mesh'].bounds
                dims = bounds[1] - bounds[0]
                info += f"   • Dimensions:\n"
                info += f"     - Llargada: {dims[0]:.1f} mm\n"
                info += f"     - Amplada: {dims[1]:.1f} mm\n"
                info += f"     - Altura: {dims[2]:.1f} mm\n"
                
            # Informació de reducció si està disponible
            if 'reduction_ratio' in mesh_info:
                info += f"\n🔧 Reducció de Complexitat:\n"
                info += f"   • Reducció: {mesh_info['reduction_ratio']:.1f}%\n"
                info += f"   • Mètode: {mesh_info.get('method', 'desconegut')}\n"
                
                if 'volume_preservation' in mesh_info:
                    info += f"   • Preservació volum: {mesh_info['volume_preservation']:.1f}%\n"
                    
            # Qualitat de la malla
            if 'mesh' in mesh_info:
                mesh = mesh_info['mesh']
                info += f"\n📈 Qualitat:\n"
                
                try:
                    if hasattr(mesh, 'is_watertight'):
                        info += f"   • Estanc: {'Sí' if mesh.is_watertight else 'No'}\n"
                    
                    if hasattr(mesh, 'is_valid'):
                        info += f"   • Vàlid: {'Sí' if mesh.is_valid else 'No'}\n"
                        
                    # Densitat de triangles
                    vertices = mesh_info.get('vertices', 1)
                    faces = mesh_info.get('faces', 0)
                    if vertices > 0:
                        density = faces / vertices
                        info += f"   • Densitat: {density:.2f} cares/vèrtex\n"
                        
                except:
                    pass  # Alguns atributs poden no estar disponibles
                
        else:
            info = "No hi ha informació disponible"
            
        text_widget.insert(tk.END, info)
        text_widget.config(state='disabled')
        
    def update_vertices_label(self, value):
        """Actualitza l'etiqueta de vèrtexs"""
        current = self.target_vertices.get()
        if hasattr(self, 'original_mesh_info') and self.original_mesh_info:
            original = self.original_mesh_info.get('vertices', 1)
            reduction = ((original - current) / original) * 100 if original > 0 else 0
            self.vertices_label.config(text=f"{current:,} vèrtexs ({reduction:.1f}% reducció)")
        else:
            self.vertices_label.config(text=f"{current:,} vèrtexs")
            
    def simplify_mesh(self):
        """Simplifica la malla utilitzant els simplificadors existents"""
        if not self.original_mesh:
            messagebox.showwarning("Avís", "Primer has d'importar un fitxer STL")
            return
            
        try:
            # Obtenir paràmetres
            target = self.target_vertices.get()
            method = self.simplify_method.get()
            preserve_vol = self.preserve_volume.get()
            
            # Deshabilitar botó temporalment
            self.simplify_btn.config(state='disabled', text="🔄 Reduint complexitat...")
            self.root.update()
            
            # Executar simplificació en fil separat
            thread = threading.Thread(target=self._simplify_worker, args=(target, method, preserve_vol))
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en la reducció: {e}")
            self.simplify_btn.config(state='normal', text="🚀 Reduir Complexitat")
            
    def _simplify_worker(self, target, method, preserve_volume):
        """Worker per la simplificació en fil separat amb mètodes carregats"""
        try:
            original_mesh = self.original_mesh
            
            # Seleccionar mètode de simplificació
            if method == "quadric_advanced" and 'pymeshlab' in self.simplifier_methods:
                self.simplified_mesh = self.simplifier_methods['pymeshlab'](original_mesh, target, preserve_volume)
                method_used = "PyMeshLab Quadric"
                
            elif method == "clustering" and 'trimesh' in self.simplifier_methods:
                # Per clustering, usar un enfocament específic
                try:
                    # Clustering simple amb trimesh
                    ratio = target / len(original_mesh.vertices) if len(original_mesh.vertices) > 0 else 0.5
                    ratio = max(0.05, min(ratio, 0.95))
                    
                    self.simplified_mesh = self.simplifier_methods['trimesh'](original_mesh, target, preserve_volume)
                    method_used = "Trimesh Clustering"
                except:
                    # Fallback a quadric
                    self.simplified_mesh = self.simplifier_methods['trimesh'](original_mesh, target, preserve_volume)
                    method_used = "Trimesh Quadric (fallback)"
                    
            elif method == "edge_length" and 'open3d' in self.simplifier_methods:
                self.simplified_mesh = self.simplifier_methods['open3d'](original_mesh, target, preserve_volume)
                method_used = "Open3D Edge Length"
                
            else:
                # Usar el primer mètode disponible
                if 'trimesh' in self.simplifier_methods:
                    self.simplified_mesh = self.simplifier_methods['trimesh'](original_mesh, target, preserve_volume)
                    method_used = "Trimesh (fallback)"
                elif 'pymeshlab' in self.simplifier_methods:
                    self.simplified_mesh = self.simplifier_methods['pymeshlab'](original_mesh, target, preserve_volume)
                    method_used = "PyMeshLab (fallback)"
                else:
                    raise Exception("Cap mètode de simplificació disponible")
            
            # Verificar que la malla és vàlida
            if self.simplified_mesh.is_empty or len(self.simplified_mesh.vertices) == 0:
                raise Exception("La malla simplificada està buida")
            
            # Corregir la malla si cal (amb gestió d'errors per compatibilitat)
            try:
                if hasattr(self.simplified_mesh, 'fix_normals'):
                    self.simplified_mesh.fix_normals()
                if hasattr(self.simplified_mesh, 'remove_degenerate_faces'):
                    # Usar mètode actualitzat si està disponible
                    if hasattr(self.simplified_mesh, 'nondegenerate_faces'):
                        degenerate_faces = self.simplified_mesh.nondegenerate_faces()
                        self.simplified_mesh.update_faces(degenerate_faces)
                    # Sinó, ignorar aquest pas
                if hasattr(self.simplified_mesh, 'remove_duplicate_faces'):
                    # Usar mètode actualitzat si està disponible
                    if hasattr(self.simplified_mesh, 'unique_faces'):
                        unique_faces = self.simplified_mesh.unique_faces()
                        self.simplified_mesh.update_faces(unique_faces)
                    # Sinó, ignorar aquest pas
            except Exception as warning:
                print(f"⚠️ Advertència corregint malla: {warning}")
                # Continuar sense correccions
            
            # Crear info de la malla simplificada
            self.simplified_mesh_info = {
                'mesh': self.simplified_mesh,
                'vertices': len(self.simplified_mesh.vertices),
                'faces': len(self.simplified_mesh.faces),
                'volume': getattr(self.simplified_mesh, 'volume', 0),
                'area': getattr(self.simplified_mesh, 'area', 0)
            }
            
            # Calcular estadístiques de qualitat
            original_vertices = len(self.original_mesh.vertices)
            simplified_vertices = len(self.simplified_mesh.vertices)
            reduction_ratio = ((original_vertices - simplified_vertices) / original_vertices) * 100 if original_vertices > 0 else 0
            
            # Verificar preservació de volum si està activada
            if preserve_volume:
                try:
                    original_volume = getattr(self.original_mesh, 'volume', 0)
                    simplified_volume = getattr(self.simplified_mesh, 'volume', 0)
                    
                    if original_volume > 0:
                        volume_preservation = (simplified_volume / original_volume) * 100
                        self.simplified_mesh_info['volume_preservation'] = volume_preservation
                except Exception as e:
                    print(f"⚠️ No s'ha pogut calcular preservació de volum: {e}")
            
            self.simplified_mesh_info['reduction_ratio'] = reduction_ratio
            self.simplified_mesh_info['method'] = method_used
            
            # Actualitzar GUI en fil principal
            self.root.after(0, self._update_simplification_results)
            
        except Exception as e:
            error_msg = f"Error en la reducció de complexitat: {e}"
            print(f"❌ {error_msg}")
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
            self.root.after(0, lambda: self.simplify_btn.config(state='normal', text="🚀 Reduir Complexitat"))
            
    def _update_simplification_results(self):
        """Actualitza els resultats de la simplificació en la GUI"""
        # Mostrar info de la malla simplificada
        self.display_mesh_info(self.simplified_mesh_info, self.simplified_stats)
        
        # Habilitar botons
        self.view_simp_btn.config(state='normal')
        self.compare_btn.config(state='normal')
        self.simplify_btn.config(state='normal', text="🚀 Reduir Complexitat")
        
        # Mostrar missatge d'èxit
        reduction = self.simplified_mesh_info.get('reduction_ratio', 0)
        method = self.simplified_mesh_info.get('method', 'desconegut')
        messagebox.showinfo("Èxit", f"Malla optimitzada correctament!\nReducció: {reduction:.1f}% amb mètode {method}")
        
    def compare_meshes_3d(self):
        """Compara la malla original i la simplificada en una vista dividida"""
        if not self.original_mesh or not self.simplified_mesh:
            messagebox.showwarning("Avís", "Necessites ambdues malles per comparar")
            return
            
        try:
            import pyvista as pv
            
            # Crear visualitzador amb layout dividit
            plotter = pv.Plotter(shape=(1, 2), window_size=(1400, 700))
            plotter.set_background('white')
            
            # Convertir malles a pyvista
            def trimesh_to_pyvista(tmesh):
                faces_with_count = []
                for face in tmesh.faces:
                    faces_with_count.extend([3, face[0], face[1], face[2]])
                return pv.PolyData(tmesh.vertices, faces_with_count)
            
            # Vista esquerra - Original
            plotter.subplot(0, 0)
            original_pv = trimesh_to_pyvista(self.original_mesh)
            plotter.add_mesh(original_pv, color='lightblue', show_edges=True, opacity=0.9)
            plotter.add_text("Malla Original", position='upper_edge', font_size=12)
            
            orig_vertices = len(self.original_mesh.vertices)
            orig_faces = len(self.original_mesh.faces)
            plotter.add_text(f"Vèrtexs: {orig_vertices:,}\nCares: {orig_faces:,}", 
                           position='lower_left', font_size=10, color='gray')
            
            plotter.camera_position = 'iso'
            plotter.show_grid()
            plotter.add_axes()
            
            # Vista dreta - Simplificada
            plotter.subplot(0, 1)
            simplified_pv = trimesh_to_pyvista(self.simplified_mesh)
            plotter.add_mesh(simplified_pv, color='lightcoral', show_edges=True, opacity=0.9)
            plotter.add_text("Malla Optimitzada", position='upper_edge', font_size=12)
            
            simp_vertices = len(self.simplified_mesh.vertices)
            simp_faces = len(self.simplified_mesh.faces)
            reduction = ((orig_vertices - simp_vertices) / orig_vertices) * 100 if orig_vertices > 0 else 0
            
            plotter.add_text(f"Vèrtexs: {simp_vertices:,}\nCares: {simp_faces:,}\nReducció: {reduction:.1f}%", 
                           position='lower_left', font_size=10, color='gray')
            
            plotter.camera_position = 'iso'
            plotter.show_grid()
            plotter.add_axes()
            
            # Sincronitzar càmeres
            plotter.link_views()
            
            # Mostrar
            plotter.show(interactive=True, auto_close=False)
            
        except ImportError:
            messagebox.showerror("Error", "PyVista no està instal·lat.\nInstal·la'l amb: pip install pyvista")
        except Exception as e:
            messagebox.showerror("Error", f"No s'ha pogut crear la comparació 3D:\n{e}")
        
    def optimize_packing(self):
        """Optimitza l'empaquetament utilitzant l'optimitzador existent"""
        if not self.original_mesh:
            messagebox.showwarning("Avís", "Primer has d'importar un fitxer STL")
            return
            
        try:
            # Validar dimensions
            box_length = float(self.box_length.get())
            box_width = float(self.box_width.get())
            box_height = float(self.box_height.get())
            
            if any(dim <= 0 for dim in [box_length, box_width, box_height]):
                raise ValueError("Totes les dimensions han de ser positives")
                
        except ValueError as e:
            messagebox.showerror("Error", f"Dimensions invàlides: {e}")
            return
            
        # Decidir quina malla usar
        mesh_to_use = self.simplified_mesh if (self.use_simplified.get() and self.simplified_mesh) else self.original_mesh
        mesh_info_to_use = self.simplified_mesh_info if (self.use_simplified.get() and self.simplified_mesh_info) else self.original_mesh_info
        
        # Deshabilitar botó i mostrar progrés
        self.optimize_btn.config(state='disabled', text="🔄 Optimitzant...")
        self.progress.start()
        
        # Executar optimització en fil separat
        thread = threading.Thread(target=self._optimize_worker, 
                                 args=(box_length, box_width, box_height, mesh_to_use, mesh_info_to_use))
        thread.daemon = True
        thread.start()
        
    def _optimize_worker(self, box_length, box_width, box_height, mesh, mesh_info):
        """Worker per l'optimització en fil separat amb geometria real"""
        try:
            # Preparar dimensions de la caixa
            box_dims = {
                "length": box_length,
                "width": box_width,
                "height": box_height,
                "shape_type": "rectangular",
                "volume_factor": 1.0
            }
            
            # Calcular dimensions reals de l'objecte STL
            if hasattr(mesh, 'bounds'):
                bounds = mesh.bounds
                obj_dims = {
                    "length": bounds[1][0] - bounds[0][0],
                    "width": bounds[1][1] - bounds[0][1],
                    "height": bounds[1][2] - bounds[0][2],
                    "shape_type": "stl_mesh",  # Indicar que és una malla STL real
                    "volume_factor": 1.0,
                    "total_faces": len(mesh.faces),
                    "total_vertices": len(mesh.vertices),
                    "real_volume": getattr(mesh, 'volume', 0),
                    "mesh_bounds": bounds,
                    "mesh_center": mesh.center_mass if hasattr(mesh, 'center_mass') else ((bounds[0] + bounds[1]) / 2)
                }
            else:
                # Fallback
                obj_dims = {
                    "length": 10, "width": 10, "height": 10,
                    "shape_type": "rectangular", "volume_factor": 1.0
                }
                
            # Utilitzar optimitzador existent si està disponible
            if self.optimizer_func:
                try:
                    result = self.optimizer_func(box_dims, obj_dims)
                    
                    # Afegir informació de la malla a cada item si l'optimitzador retorna posicions
                    if 'bins' in result and result['bins']:
                        for bin_data in result['bins']:
                            if 'items' in bin_data:
                                for item in bin_data['items']:
                                    # Afegir informació de la malla STL real
                                    item['stl_mesh'] = mesh
                                    item['mesh_info'] = mesh_info
                                    item['is_stl'] = True
                                    
                except Exception as e:
                    print(f"Error amb optimitzador avançat: {e}")
                    result = self._advanced_stl_optimization_fallback(box_dims, obj_dims, mesh)
            else:
                # Fallback a optimització avançada pròpia
                result = self._advanced_stl_optimization_fallback(box_dims, obj_dims, mesh)
            
            # Guardar resultats
            self.optimization_results = result
            
            # Actualitzar GUI en fil principal
            self.root.after(0, self._update_optimization_results, result, mesh_info)
            
        except Exception as e:
            self.root.after(0, lambda: self._handle_optimization_error(str(e)))
            
    def _advanced_stl_optimization_fallback(self, box_dims, obj_dims, mesh):
        """Optimització avançada per STL considerant geometria real"""
        try:
            # Obtenir dimensions reals
            obj_length = obj_dims['length']
            obj_width = obj_dims['width'] 
            obj_height = obj_dims['height']
            
            box_length = box_dims['length']
            box_width = box_dims['width']
            box_height = box_dims['height']
            
            # Calcular orientacions possibles (original + 2 rotacions)
            orientations = [
                (obj_length, obj_width, obj_height, [0, 0, 0]),           # Original
                (obj_width, obj_length, obj_height, [0, 0, 90]),         # Rotat 90° Z
                (obj_height, obj_width, obj_length, [90, 0, 0]),         # Rotat 90° X
                (obj_width, obj_height, obj_length, [0, 90, 0]),         # Rotat 90° Y
                (obj_length, obj_height, obj_width, [0, 0, 0]),          # Intercanvi Y-Z
                (obj_height, obj_length, obj_width, [90, 0, 90]),        # Combinada
            ]
            
            best_result = None
            max_pieces = 0
            
            # Provar cada orientació
            for ol, ow, oh, rotation in orientations:
                # Verificar que l'objecte cap en la caixa en aquesta orientació
                if ol <= box_length and ow <= box_width and oh <= box_height:
                    # Calcular quants objectes caben
                    pieces_x = max(1, int(box_length / ol))
                    pieces_y = max(1, int(box_width / ow))
                    pieces_z = max(1, int(box_height / oh))
                    
                    total_pieces = pieces_x * pieces_y * pieces_z
                    
                    if total_pieces > max_pieces:
                        max_pieces = total_pieces
                        
                        # Crear posicions per aquesta orientació
                        items = []
                        for z in range(pieces_z):
                            for y in range(pieces_y):
                                for x in range(pieces_x):
                                    items.append({
                                        'position': [x * ol, y * ow, z * oh],
                                        'dimensions': [ol, ow, oh],
                                        'rotation': rotation,
                                        'stl_mesh': mesh,
                                        'is_stl': True
                                    })
                        
                        # Calcular volums
                        box_volume = box_length * box_width * box_height
                        obj_volume = getattr(mesh, 'volume', ol * ow * oh)
                        used_volume = max_pieces * obj_volume
                        efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0
                        
                        best_result = {
                            'max_objects': max_pieces,
                            'efficiency': efficiency,
                            'box_volume': box_volume,
                            'used_volume': used_volume,
                            'method': 'advanced_stl_optimization',
                            'best_orientation': rotation,
                            'piece_dimensions': [ol, ow, oh],
                            'bins': [{
                                'bin': {'dimensions': [box_length, box_width, box_height]},
                                'items': items
                            }]
                        }
            
            if best_result is None:
                # L'objecte no cap en cap orientació
                return {
                    'max_objects': 0,
                    'efficiency': 0,
                    'error': 'L\'objecte és massa gran per la caixa en qualsevol orientació',
                    'bins': []
                }
                
            return best_result
            
        except Exception as e:
            return {
                'max_objects': 0,
                'efficiency': 0,
                'error': f'Error en optimització STL: {e}',
                'bins': []
            }
            
    def _simple_optimization_fallback(self, box_dims, obj_dims):
        """Optimització simple de fallback"""
        # Calcular quants objectes caben
        objects_x = max(1, int(box_dims['length'] / obj_dims['length']))
        objects_y = max(1, int(box_dims['width'] / obj_dims['width']))
        objects_z = max(1, int(box_dims['height'] / obj_dims['height']))
        
        max_objects = objects_x * objects_y * objects_z
        
        # Calcular volums
        box_volume = box_dims['length'] * box_dims['width'] * box_dims['height']
        obj_volume = obj_dims.get('real_volume', obj_dims['length'] * obj_dims['width'] * obj_dims['height'])
        used_volume = max_objects * obj_volume
        efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0
        
        return {
            'max_objects': max_objects,
            'efficiency': efficiency,
            'box_volume': box_volume,
            'used_volume': used_volume,
            'method': 'simple_grid',
            'bins': [{
                'bin': {'dimensions': [box_dims['length'], box_dims['width'], box_dims['height']]},
                'items': [
                    {
                        'position': [x * obj_dims['length'], y * obj_dims['width'], z * obj_dims['height']],
                        'dimensions': [obj_dims['length'], obj_dims['width'], obj_dims['height']],
                        'rotation': [0, 0, 0]
                    }
                    for z in range(objects_z)
                    for y in range(objects_y)
                    for x in range(objects_x)
                ]
            }]
        }
        
    def _update_optimization_results(self, result, mesh_info):
        """Actualitza els resultats de l'optimització"""
        self.progress.stop()
        self.optimize_btn.config(state='normal', text="🚀 Calcular Empaquetament Òptim")
        
        # Mostrar resultats
        self.results_text.config(state='normal')
        self.results_text.delete(1.0, tk.END)
        
        if result.get("error"):
            self.results_text.insert(tk.END, f"❌ Error en l'optimització: {result['error']}\n")
        else:
            max_objects = result.get('max_objects', 0)
            efficiency = result.get('efficiency', 0)
            
            results = f"🎉 RESULTATS DE L'OPTIMITZACIÓ\n"
            results += f"=" * 40 + "\n\n"
            results += f"📊 Objectes que caben: {max_objects:,}\n"
            results += f"📈 Eficiència: {efficiency:.1f}%\n"
            
            if 'box_volume' in result:
                results += f"📦 Volum caixa: {result['box_volume']:,.0f} mm³\n"
                
            if 'used_volume' in result:
                results += f"📋 Volum utilitzat: {result['used_volume']:,.0f} mm³\n"
                
            method = result.get('method', 'unknown')
            results += f"🔧 Mètode: {method}\n"
            
            if 'bins' in result and result['bins']:
                bin_info = result['bins'][0]
                if 'items' in bin_info:
                    results += f"📍 Posicions calculades: {len(bin_info['items'])}\n"
                    
            results += f"\n✨ Optimització completada amb èxit!\n"
            
            self.results_text.insert(tk.END, results)
            
            # Habilitar visualització
            self.visualize_3d_btn.config(state='normal')
            self.export_result_btn.config(state='normal')
            
            # Actualitzar resum
            self._update_final_summary(result, mesh_info)
            
        self.results_text.config(state='disabled')
        
    def _update_final_summary(self, result, mesh_info):
        """Actualitza el resum final"""
        self.summary_text.config(state='normal')
        self.summary_text.delete(1.0, tk.END)
        
        summary = f"📋 RESUM FINAL DEL PROJECTE\n"
        summary += f"=" * 50 + "\n\n"
        
        # Info del fitxer
        if self.stl_file_path:
            filename = os.path.basename(self.stl_file_path)
            summary += f"📁 Fitxer: {filename}\n\n"
        
        # Info malla original
        if self.original_mesh_info:
            summary += f"📊 Malla Original:\n"
            summary += f"   • Vèrtexs: {self.original_mesh_info.get('vertices', 0):,}\n"
            summary += f"   • Cares: {self.original_mesh_info.get('faces', 0):,}\n"
            if self.original_mesh_info.get('volume', 0) > 0:
                summary += f"   • Volum: {self.original_mesh_info['volume']:.2f} mm³\n"
        
        # Info malla simplificada (si existeix)
        if self.simplified_mesh_info:
            orig_vertices = self.original_mesh_info.get('vertices', 1)
            simp_vertices = self.simplified_mesh_info.get('vertices', 0)
            reduction = ((orig_vertices - simp_vertices) / orig_vertices) * 100 if orig_vertices > 0 else 0
            
            summary += f"\n🔧 Malla Simplificada:\n"
            summary += f"   • Vèrtexs: {simp_vertices:,}\n"
            summary += f"   • Reducció: {reduction:.1f}%\n"
            summary += f"   • Mètode: {self.simplify_method.get()}\n"
        
        # Resultats empaquetament
        if result and not result.get("error"):
            summary += f"\n⚡ Empaquetament:\n"
            summary += f"   • Objectes que caben: {result.get('max_objects', 0):,}\n"
            summary += f"   • Eficiència: {result.get('efficiency', 0):.1f}%\n"
            summary += f"   • Caixa: {self.box_length.get()} × {self.box_width.get()} × {self.box_height.get()} mm\n"
            
        summary += f"\n✅ Procés completat amb èxit!\n"
        summary += f"🎮 Utilitza la visualització 3D per veure el resultat.\n"
        
        self.summary_text.insert(tk.END, summary)
        self.summary_text.config(state='disabled')
        
    def _handle_optimization_error(self, error):
        """Gestiona errors de l'optimització"""
        self.progress.stop()
        self.optimize_btn.config(state='normal', text="🚀 Calcular Empaquetament Òptim")
        
        self.results_text.config(state='normal')
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, f"❌ Error en l'optimització: {error}\n")
        self.results_text.config(state='disabled')
        
        messagebox.showerror("Error", f"Error en l'optimització: {error}")
        
    def view_original_3d(self):
        """Visualitza la malla original en 3D"""
        if not self.original_mesh:
            messagebox.showwarning("Avís", "No hi ha malla original carregada")
            return
            
        self._visualize_mesh_3d(self.original_mesh, "STL Original")
        
    def view_simplified_3d(self):
        """Visualitza la malla simplificada en 3D"""
        if not self.simplified_mesh:
            messagebox.showwarning("Avís", "No hi ha malla simplificada disponible")
            return
            
        self._visualize_mesh_3d(self.simplified_mesh, "STL Simplificada")
        
    def _visualize_mesh_3d(self, mesh, title):
        """Visualitza una malla en 3D"""
        try:
            import pyvista as pv
            
            # Crear visualitzador
            plotter = pv.Plotter(window_size=(800, 600))
            plotter.set_background('white')
            
            # Convertir mesh a pyvista si cal
            if hasattr(mesh, 'vertices') and hasattr(mesh, 'faces'):
                # Crear malla pyvista
                faces_with_count = []
                for face in mesh.faces:
                    faces_with_count.extend([3, face[0], face[1], face[2]])
                
                pv_mesh = pv.PolyData(mesh.vertices, faces_with_count)
            else:
                pv_mesh = mesh
            
            # Afegir malla
            plotter.add_mesh(pv_mesh, color='lightblue', show_edges=True, opacity=0.8)
            
            # Configurar vista
            plotter.camera_position = 'iso'
            plotter.show_grid()
            plotter.add_axes()
            
            # Afegir títol
            plotter.add_text(title, position='upper_edge', font_size=12, color='black')
            
            # Mostrar info
            if hasattr(mesh, 'vertices'):
                info_text = f"Vèrtexs: {len(mesh.vertices):,}\nCares: {len(mesh.faces):,}"
                plotter.add_text(info_text, position='lower_left', font_size=10, color='gray')
            
            # Mostrar
            plotter.show(interactive=True, auto_close=False)
            
        except ImportError:
            messagebox.showerror("Error", "PyVista no està instal·lat.\nInstal·la'l amb: pip install pyvista")
        except Exception as e:
            messagebox.showerror("Error", f"No s'ha pogut visualitzar la malla:\n{e}")
            
    def visualize_3d(self):
        """Visualitza els resultats de l'empaquetament en 3D amb peces STL reals"""
        if not self.optimization_results:
            messagebox.showwarning("Avís", "Primer has de calcular l'empaquetament")
            return
            
        try:
            import pyvista as pv
            
            # Crear visualitzador amb millor configuració
            plotter = pv.Plotter(window_size=(1200, 800))
            plotter.set_background('white')
            
            # Obtenir dades del resultat
            bins_data = self.optimization_results.get('bins', [])
            if not bins_data:
                messagebox.showwarning("Avís", "No hi ha dades de visualització disponibles")
                return
                
            bin_data = bins_data[0]
            items = bin_data.get('items', [])
            container_dims = bin_data.get('bin', {}).get('dimensions', [100, 100, 100])
            
            # Dibuixar contenidor
            container = pv.Cube(bounds=(0, container_dims[0], 0, container_dims[1], 0, container_dims[2]))
            plotter.add_mesh(container, style='wireframe', color='gray', line_width=3, label='Contenidor')
            
            # Determinar quina malla usar per les peces
            mesh_to_show = self.simplified_mesh if (self.use_simplified.get() and self.simplified_mesh) else self.original_mesh
            
            if not mesh_to_show:
                messagebox.showwarning("Avís", "No hi ha malla carregada per visualitzar")
                return
            
            # Convertir trimesh a pyvista
            def trimesh_to_pyvista(tmesh):
                """Converteix una malla trimesh a pyvista"""
                try:
                    # Crear array de cares amb comptador
                    faces_with_count = []
                    for face in tmesh.faces:
                        faces_with_count.extend([3, face[0], face[1], face[2]])
                    
                    return pv.PolyData(tmesh.vertices, faces_with_count)
                except Exception as e:
                    print(f"Error convertint malla: {e}")
                    return None
            
            # Convertir la malla STL a pyvista
            base_pv_mesh = trimesh_to_pyvista(mesh_to_show)
            
            if base_pv_mesh is None:
                messagebox.showerror("Error", "No s'ha pogut convertir la malla per visualització")
                return
            
            # Colors per objectes (més variats)
            colors = ['lightcoral', 'lightblue', 'lightgreen', 'orange', 'plum', 
                     'khaki', 'pink', 'lightcyan', 'wheat', 'lightgray']
            
            # Dibuixar cada peça STL real en la seva posició
            for i, item in enumerate(items):
                try:
                    pos = item.get('position', [0, 0, 0])
                    rotation = item.get('rotation', [0, 0, 0])
                    
                    # Crear còpia de la malla base
                    piece_mesh = base_pv_mesh.copy()
                    
                    # Aplicar rotació si cal
                    if any(r != 0 for r in rotation):
                        # Convertir rotacions de graus a radians si cal
                        rx, ry, rz = [np.radians(r) if abs(r) > 2*np.pi else r for r in rotation]
                        
                        # Aplicar rotacions
                        if rx != 0:
                            piece_mesh = piece_mesh.rotate_x(np.degrees(rx))
                        if ry != 0:
                            piece_mesh = piece_mesh.rotate_y(np.degrees(ry))
                        if rz != 0:
                            piece_mesh = piece_mesh.rotate_z(np.degrees(rz))
                    
                    # Aplicar translació a la posició correcta
                    piece_mesh.translate(pos, inplace=True)
                    
                    # Afegir la peça amb color únic
                    color = colors[i % len(colors)]
                    plotter.add_mesh(
                        piece_mesh, 
                        color=color, 
                        opacity=0.8, 
                        label=f'Peça STL {i+1}',
                        show_edges=True,
                        edge_color='darkgray',
                        line_width=0.5
                    )
                    
                except Exception as e:
                    print(f"Error afegint peça {i}: {e}")
                    # Fallback: crear un cub si la peça STL falla
                    dims = item.get('dimensions', [10, 10, 10])
                    fallback_mesh = pv.Cube(bounds=(
                        pos[0], pos[0] + dims[0],
                        pos[1], pos[1] + dims[1], 
                        pos[2], pos[2] + dims[2]
                    ))
                    color = colors[i % len(colors)]
                    plotter.add_mesh(fallback_mesh, color=color, opacity=0.6, label=f'Peça {i+1} (aprox)')
                
            # Configurar vista i controls
            plotter.camera_position = 'iso'
            plotter.show_grid()
            plotter.add_axes()
            
            # Títol i informació detallada
            max_objects = self.optimization_results.get('max_objects', 0)
            efficiency = self.optimization_results.get('efficiency', 0)
            mesh_type = "optimitzada" if (self.use_simplified.get() and self.simplified_mesh) else "original"
            
            title = f"Empaquetament: {max_objects} peces STL {mesh_type} ({efficiency:.1f}% eficiència)"
            plotter.add_text(title, position='upper_edge', font_size=14, color='black')
            
            # Info de la caixa
            box_info = f"Caixa: {container_dims[0]:.0f}×{container_dims[1]:.0f}×{container_dims[2]:.0f} mm"
            plotter.add_text(box_info, position='lower_left', font_size=10, color='gray')
            
            # Info de la malla
            if mesh_to_show:
                mesh_info = f"Malla {mesh_type}: {len(mesh_to_show.vertices):,} vèrtexs, {len(mesh_to_show.faces):,} cares"
                plotter.add_text(mesh_info, position='lower_right', font_size=10, color='gray')
            
            # Afegir llegenda si hi ha objectes
            if items and len(items) <= 20:  # Només si no hi ha massa objectes
                plotter.add_legend(size=(0.2, 0.3))
            
            # Configurar controls de càmera
            plotter.enable_zoom_style()
            plotter.enable_trackball_style()
            
            # Mostrar amb millor qualitat
            plotter.show(
                interactive=True, 
                auto_close=False,
                screenshot=False
            )
            
        except ImportError:
            messagebox.showerror("Error", "PyVista no està instal·lat.\nInstal·la'l amb: pip install pyvista")
        except Exception as e:
            error_msg = f"No s'ha pogut crear la visualització 3D:\n{e}\n\nRevisa que la malla STL sigui vàlida."
            messagebox.showerror("Error", error_msg)
            print(f"Error detallat en visualització: {e}")
            import traceback
            traceback.print_exc()
            
    def export_results(self):
        """Exporta els resultats a un fitxer"""
        if not self.optimization_results:
            messagebox.showwarning("Avís", "No hi ha resultats per exportar")
            return
            
        try:
            file_path = filedialog.asksaveasfilename(
                title="Guardar resultats",
                defaultextension=".txt",
                filetypes=[
                    ("Fitxers de text", "*.txt"),
                    ("Tots els fitxers", "*.*")
                ]
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("PACKASSIST - RESULTATS D'EMPAQUETAMENT\n")
                    f.write("=" * 50 + "\n\n")
                    
                    # Info del fitxer
                    if self.stl_file_path:
                        f.write(f"Fitxer STL: {os.path.basename(self.stl_file_path)}\n")
                    
                    # Resultats
                    result = self.optimization_results
                    f.write(f"Objectes que caben: {result.get('max_objects', 0)}\n")
                    f.write(f"Eficiència: {result.get('efficiency', 0):.2f}%\n")
                    f.write(f"Volum caixa: {result.get('box_volume', 0):.0f} mm³\n")
                    f.write(f"Volum utilitzat: {result.get('used_volume', 0):.0f} mm³\n")
                    
                    # Dimensions
                    f.write(f"\nDimensions caixa: {self.box_length.get()} × {self.box_width.get()} × {self.box_height.get()} mm\n")
                    
                    # Posicions dels objectes
                    bins_data = result.get('bins', [])
                    if bins_data:
                        items = bins_data[0].get('items', [])
                        f.write(f"\nPosicions dels objectes ({len(items)} total):\n")
                        for i, item in enumerate(items):
                            pos = item.get('position', [0, 0, 0])
                            f.write(f"  Objecte {i+1}: X={pos[0]:.1f}, Y={pos[1]:.1f}, Z={pos[2]:.1f}\n")
                
                messagebox.showinfo("Èxit", f"Resultats exportats a: {file_path}")
                
        except Exception as e:
            messagebox.showerror("Error", f"No s'han pogut exportar els resultats:\n{e}")
        
    def run(self):
        """Executa l'aplicació"""
        self.root.mainloop()

def main():
    """Funció principal"""
    try:
        app = PackAssistIntegratedApp()
        app.run()
    except Exception as e:
        messagebox.showerror("Error Fatal", f"No s'ha pogut iniciar l'aplicació:\n{e}")

if __name__ == "__main__":
    main()
