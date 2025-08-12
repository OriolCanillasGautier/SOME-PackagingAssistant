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
        
        # Open3D (eliminat - no necessari)
        available['open3d'] = False
        print("❌ Open3D no utilitzat (simplificació optimitzada)")
            
        return available
        
    def load_optimizer(self):
        """Carrega l'optimitzador des del codi existent"""
        try:
            # Afegir el path correcte per l'optimitzador
            import sys
            optimizer_path = os.path.join(current_dir, 'src')
            if optimizer_path not in sys.path:
                sys.path.insert(0, optimizer_path)
            
            # Carregar des de packassist.optimizer
            from packassist.optimizer import optimize_packing
            self.optimizer_func = optimize_packing
            print("✅ Optimitzador carregat des de src/packassist.optimizer")
        except Exception as e:
            print(f"⚠️ No s'ha pogut carregar l'optimitzador: {e}")
            self.optimizer_func = None
            
    def load_simplifiers(self):
        """Carrega els simplificadors disponibles"""
        self.simplifier_methods = {}
        
        # Mètode principal: PyMeshLab (millor qualitat) 
        if self.available_libs.get('pymeshlab'):
            self.simplifier_methods['pymeshlab'] = self.simplify_with_pymeshlab
            
        # Mètode alternatiu: Trimesh (funcional i ràpid)
        if self.available_libs.get('trimesh'):
            self.simplifier_methods['trimesh'] = self.simplify_with_trimesh
            
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
            # Intentar decimació quadric de trimesh
            try:
                # Calcular ratio de reducció (entre 0 i 1)
                current_vertices = len(mesh.vertices)
                if current_vertices <= target_vertices:
                    return mesh  # No cal reducció
                    
                target_reduction = 1.0 - (target_vertices / current_vertices)
                target_reduction = max(0.01, min(0.99, target_reduction))  # Assegurar límits
                
                simplified_mesh = mesh.simplify_quadric_decimation(target_reduction=target_reduction)
                
                if simplified_mesh.is_empty or len(simplified_mesh.vertices) == 0:
                    # Fallback amb reducció més conservadora
                    conservative_reduction = min(0.5, target_reduction)
                    simplified_mesh = mesh.simplify_quadric_decimation(target_reduction=conservative_reduction)
                    
                return simplified_mesh
                
            except (ImportError, ModuleNotFoundError) as import_error:
                # Si fast_simplification no està disponible, usar mètode alternatiu
                if "fast_simplification" in str(import_error):
                    print(f"⚠️ fast_simplification no disponible, usant mètode alternatiu")
                    return self._simple_mesh_reduction(mesh, target_vertices)
                else:
                    raise import_error
                    
        except Exception as e:
            raise Exception(f"Error amb Trimesh: {e}")
            
    def _simple_mesh_reduction(self, mesh, target_vertices):
        """Mètode de reducció simple quan fast_simplification no està disponible"""
        try:
            # Calcular ratio de reducció
            current_vertices = len(mesh.vertices)
            if current_vertices <= target_vertices:
                return mesh
                
            reduction_ratio = target_vertices / current_vertices
            
            # Usar subdivide i després simplificar per mostreig
            vertices = mesh.vertices
            faces = mesh.faces
            
            # Mostreig uniforme de vèrtexs
            indices = np.linspace(0, current_vertices - 1, target_vertices, dtype=int)
            new_vertices = vertices[indices]
            
            # Crear mapa de vèrtexs vells a nous
            vertex_map = {old_idx: new_idx for new_idx, old_idx in enumerate(indices)}
            
            # Filtrar cares que tenen tots els vèrtexs en el nou conjunt
            new_faces = []
            for face in faces:
                if all(v in vertex_map for v in face):
                    new_face = [vertex_map[v] for v in face]
                    # Verificar que no és degenerada
                    if len(set(new_face)) == 3:
                        new_faces.append(new_face)
            
            # Si no tenim prou cares, crear un subconjunt mínim
            if len(new_faces) < 4:
                # Crear tetraedre mínim
                if len(new_vertices) >= 4:
                    new_faces = [[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]]
                elif len(new_vertices) >= 3:
                    new_faces = [[0, 1, 2]]
                else:
                    # Tornar la malla original si és massa petita
                    return mesh
            
            simplified_mesh = trimesh.Trimesh(vertices=new_vertices, faces=new_faces)
            
            # Verificar que la malla és vàlida
            if simplified_mesh.is_empty or len(simplified_mesh.vertices) == 0:
                return mesh  # Retornar original si la simplificació falla
                
            return simplified_mesh
            
        except Exception as e:
            print(f"⚠️ Error en reducció simple: {e}")
            return mesh  # Retornar original com a fallback

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
        
        # Selector de mètode (simplificat)
        ttk.Label(controls_frame, text="Mètode de reducció:").pack(anchor=tk.W)
        self.simplify_method = tk.StringVar(value="quadric_advanced")
        method_frame = ttk.Frame(controls_frame)
        method_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(method_frame, text="PyMeshLab Quadric (Recomanat)", variable=self.simplify_method, value="quadric_advanced").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(method_frame, text="Trimesh Alternatiu", variable=self.simplify_method, value="trimesh_fallback").pack(side=tk.LEFT)
        
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
        """Worker per la simplificació en fil separat amb mètodes simplificats"""
        try:
            original_mesh = self.original_mesh
            
            # Seleccionar mètode de simplificació (només els que funcionen)
            if method == "quadric_advanced" and 'pymeshlab' in self.simplifier_methods:
                self.simplified_mesh = self.simplifier_methods['pymeshlab'](original_mesh, target, preserve_volume)
                method_used = "PyMeshLab Quadric"
                
            elif method == "trimesh_fallback" and 'trimesh' in self.simplifier_methods:
                self.simplified_mesh = self.simplifier_methods['trimesh'](original_mesh, target, preserve_volume)
                method_used = "Trimesh Alternatiu"
                
            else:
                # Fallback automàtic: primer PyMeshLab, després Trimesh
                if 'pymeshlab' in self.simplifier_methods:
                    self.simplified_mesh = self.simplifier_methods['pymeshlab'](original_mesh, target, preserve_volume)
                    method_used = "PyMeshLab Quadric (auto)"
                elif 'trimesh' in self.simplifier_methods:
                    self.simplified_mesh = self.simplifier_methods['trimesh'](original_mesh, target, preserve_volume)
                    method_used = "Trimesh (auto)"
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
            if False:  # TEMPORALMENT DESHABILITAT per provar el meu algoritme STL millorat
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
                # Usar sempre l'optimització avançada STL pròpia
                print("🔍 Usant optimitzador STL avançat propi amb rotacions intel·ligents...")
                result = self._advanced_stl_optimization_fallback(box_dims, obj_dims, mesh)
            
            # Guardar resultats
            self.optimization_results = result
            
            # Actualitzar GUI en fil principal
            self.root.after(0, self._update_optimization_results, result, mesh_info)
            
        except Exception as e:
            self.root.after(0, lambda: self._handle_optimization_error(str(e)))
            
    def _advanced_stl_optimization_fallback(self, box_dims, obj_dims, mesh):
        """Optimització avançada per STL considerant geometria real amb rotacions intel·ligents progressives"""
        try:
            print("🔍 Iniciant optimització avançada amb geometria STL real...")
            
            box_length = box_dims['length']
            box_width = box_dims['width']
            box_height = box_dims['height']
            
            # Generar totes les rotacions possibles
            all_rotations = self._generate_rotation_combinations()
            
            best_result = None
            max_pieces = 0
            best_config = None
            
            # Optimització progressiva amb fases
            rotation_phases = [
                ("� Fase bàsica", 8),      # 8 rotacions més probables
                ("⚡ Fase estàndard", 16),   # Fins a 16 rotacions
                ("🎯 Fase completa", -1)     # Totes les rotacions si cal
            ]
            
            initial_max_pieces = 0
            
            for phase_name, max_rotations in rotation_phases:
                rotations_to_test = all_rotations[:max_rotations] if max_rotations > 0 else all_rotations
                print(f"\n{phase_name} - Testant {len(rotations_to_test)} orientacions...")
                
                phase_best_pieces = 0
                
                # Provar cada rotació de la fase
                for i, rotation in enumerate(rotations_to_test):
                    try:
                        print(f"    🔄 Testant rotació {i+1}/{len(rotations_to_test)}: {rotation}")
                        
                        # Aplicar rotació a la malla
                        rotated_mesh = self._apply_rotation_to_mesh(mesh, rotation)
                        
                        # Calcular noves dimensions amb la rotació
                        bounds = rotated_mesh.bounds
                        obj_length = bounds[1][0] - bounds[0][0]
                        obj_width = bounds[1][1] - bounds[0][1] 
                        obj_height = bounds[1][2] - bounds[0][2]
                        
                        print(f"      📐 Dimensions rotades: {obj_length:.1f} × {obj_width:.1f} × {obj_height:.1f} mm")
                        
                        # Verificar que cap en la caixa
                        if obj_length <= box_length and obj_width <= box_width and obj_height <= box_height:
                            print(f"      ✅ L'objecte cap en la caixa!")
                            
                            # Calcular empaquetament per aquesta orientació
                            result = self._calculate_stl_packing(
                                box_length, box_width, box_height,
                                obj_length, obj_width, obj_height,
                                rotated_mesh, rotation
                            )
                            
                            if result['total_pieces'] > phase_best_pieces:
                                phase_best_pieces = result['total_pieces']
                            
                            if result['total_pieces'] > max_pieces:
                                max_pieces = result['total_pieces']
                                best_result = result
                                best_config = {
                                    'rotation': rotation,
                                    'dimensions': [obj_length, obj_width, obj_height],
                                    'mesh': rotated_mesh
                                }
                                print(f"      🎉 NOVA MILLOR CONFIGURACIÓ: {max_pieces} objectes!")
                                
                                # Si millorem molt (>50% més objectes), continuar amb aquesta fase
                                if max_pieces > initial_max_pieces * 1.5:
                                    print(f"        🎯 Gran millora! Continuant amb més rotacions...")
                        else:
                            print(f"      ❌ L'objecte NO cap: {obj_length:.1f} > {box_length} o {obj_width:.1f} > {box_width} o {obj_height:.1f} > {box_height}")
                        
                    except Exception as e:
                        print(f"      ⚠️ Error amb rotació {rotation}: {e}")
                        continue
                
                print(f"  📊 Millor resultat fase: {phase_best_pieces} objectes")
                
                # Si la primera fase és 0, provar més rotacions
                if phase_name == "🚀 Fase bàsica":
                    initial_max_pieces = phase_best_pieces
                    if initial_max_pieces == 0:
                        print("    🔄 Cap objecte col·locat, provant més orientacions...")
                        continue
                
                # Si no hi ha millora significativa de la fase anterior, parar
                if phase_best_pieces > 0 and max_pieces > 0:
                    improvement_ratio = phase_best_pieces / max_pieces if max_pieces > 0 else 0
                    if improvement_ratio < 1.1 and phase_name != "🎯 Fase completa":  # Menys del 10% millora
                        print(f"    ⏭️ Poca millora ({improvement_ratio:.2f}x), saltant fases següents")
                        break
                
                # Si ja tenim una eficiència molt alta, parar
                if max_pieces > 0:
                    box_volume = box_length * box_width * box_height
                    # Usar eficiència de bounding box per decidir si parar
                    best_bbox_dims = best_config['dimensions'] if best_config else [10, 10, 10]
                    obj_bbox_volume = best_bbox_dims[0] * best_bbox_dims[1] * best_bbox_dims[2]
                    estimated_efficiency = (max_pieces * obj_bbox_volume / box_volume) * 100 if box_volume > 0 else 0
                    if estimated_efficiency > 85:
                        print(f"    🎯 Eficiència alta estimada ({estimated_efficiency:.1f}%), parant optimització")
                        break
            
            if best_result is None:
                return {
                    'max_objects': 0,
                    'efficiency': 0,
                    'error': 'L\'objecte és massa gran per la caixa en qualsevol orientació',
                    'bins': []
                }
            
            # Crear resultat final
            box_volume = box_length * box_width * box_height
            
            # MILLORAT: Usar volum de bounding box en lloc de volum STL real 
            # (molts STL són buits per dins i donen eficiències irrellevants)
            obj_bbox_volume = (best_config['dimensions'][0] * 
                             best_config['dimensions'][1] * 
                             best_config['dimensions'][2])
            used_bbox_volume = max_pieces * obj_bbox_volume
            efficiency = (used_bbox_volume / box_volume) * 100 if box_volume > 0 else 0
            
            # També calcular eficiència real STL per comparació
            obj_real_volume = getattr(mesh, 'volume', 0)
            used_real_volume = max_pieces * obj_real_volume
            real_efficiency = (used_real_volume / box_volume) * 100 if box_volume > 0 else 0
            
            final_result = {
                'max_objects': max_pieces,
                'efficiency': efficiency,  # Eficiència basada en bounding box (pràctica)
                'real_efficiency': real_efficiency,  # Eficiència basada en volum STL real
                'box_volume': box_volume,
                'used_volume': used_bbox_volume,  # Volum de bounding boxes utilitzat
                'used_real_volume': used_real_volume,  # Volum STL real utilitzat
                'obj_bbox_volume': obj_bbox_volume,  # Volum individual bounding box
                'obj_real_volume': obj_real_volume,  # Volum STL real individual
                'method': 'advanced_stl_geometry_packing_progressive',
                'best_orientation': best_config['rotation'],
                'piece_dimensions': best_config['dimensions'],
                'bins': [{
                    'bin': {'dimensions': [box_length, box_width, box_height]},
                    'items': best_result['items'],
                    'mesh_data': best_config['mesh']
                }]
            }
            
            print(f"🎉 Optimització completada: {max_pieces} objectes")
            print(f"📊 Eficiència pràctica (bounding box): {efficiency:.1f}%")
            print(f"📊 Eficiència real STL (volum): {real_efficiency:.1f}%")
            return final_result
            
        except Exception as e:
            print(f"❌ Error en optimització avançada: {e}")
            return {
                'max_objects': 0,
                'efficiency': 0,
                'error': f'Error en optimització STL: {e}',
                'bins': []
            }
            
    def _generate_rotation_combinations(self):
        """Genera combinacions de rotacions optimitzades (començant per les més probables)"""
        rotations = []
        
        # Fase 1: Rotacions més probables (24 rotacions bàsiques)
        # Orientacions principals de 90°
        basic_90_rotations = [
            [0, 0, 0],     # Original
            [90, 0, 0],    # Rotat 90° X  
            [180, 0, 0],   # Rotat 180° X
            [270, 0, 0],   # Rotat 270° X
            [0, 90, 0],    # Rotat 90° Y
            [0, 180, 0],   # Rotat 180° Y
            [0, 270, 0],   # Rotat 270° Y
            [0, 0, 90],    # Rotat 90° Z
            [0, 0, 180],   # Rotat 180° Z
            [0, 0, 270],   # Rotat 270° Z
            # Combinacions de 2 eixos més comunes
            [90, 90, 0],   
            [90, 0, 90],   
            [0, 90, 90],   
            [90, 90, 90],  
            [180, 90, 0],  
            [90, 180, 0],  
            [180, 180, 0], 
            [90, 270, 0],  
            [270, 90, 0],  
            [180, 0, 90],  
            [0, 180, 90],  
            [90, 0, 180],  
            [0, 90, 180],  
            [270, 180, 90] 
        ]
        
        rotations.extend(basic_90_rotations)
        
        # Fase 2: Rotacions de 45° per refinament (només si necessari)
        # Afegir algunes rotacions de 45° estratègiques
        refinement_45_rotations = [
            [45, 0, 0],    # 45° X
            [0, 45, 0],    # 45° Y
            [0, 0, 45],    # 45° Z
            [45, 45, 0],   # 45° XY
            [45, 0, 45],   # 45° XZ
            [0, 45, 45],   # 45° YZ
            [135, 0, 0],   # 135° X
            [0, 135, 0],   # 135° Y
            [0, 0, 135],   # 135° Z
        ]
        
        rotations.extend(refinement_45_rotations)
        
        # Eliminar duplicats
        unique_rotations = []
        for rot in rotations:
            # Normalitzar angles (0-360)
            normalized = [angle % 360 for angle in rot]
            if normalized not in unique_rotations:
                unique_rotations.append(normalized)
        
        print(f"📐 Generades {len(unique_rotations)} rotacions optimitzades")
        return unique_rotations
    
    def _apply_rotation_to_mesh(self, mesh, rotation):
        """Aplica una rotació a la malla STL i la centra correctament"""
        try:
            import numpy as np
            
            # Crear còpia de la malla
            rotated_mesh = mesh.copy()
            
            # Aplicar rotacions en ordre: X, Y, Z
            rx, ry, rz = np.radians(rotation)
            
            # Matriu de rotació X
            if rx != 0:
                Rx = trimesh.transformations.rotation_matrix(rx, [1, 0, 0])
                rotated_mesh.apply_transform(Rx)
            
            # Matriu de rotació Y
            if ry != 0:
                Ry = trimesh.transformations.rotation_matrix(ry, [0, 1, 0])
                rotated_mesh.apply_transform(Ry)
            
            # Matriu de rotació Z
            if rz != 0:
                Rz = trimesh.transformations.rotation_matrix(rz, [0, 0, 1])
                rotated_mesh.apply_transform(Rz)
            
            # IMPORTANT: Centrar la malla després de la rotació
            # Moure la malla perquè el seu punt mínim sigui (0,0,0)
            bounds = rotated_mesh.bounds
            translation = -bounds[0]  # Moure des del punt mínim a l'origen
            rotated_mesh.apply_translation(translation)
            
            return rotated_mesh
            
        except Exception as e:
            print(f"⚠️ Error aplicant rotació {rotation}: {e}")
            return mesh  # Retornar original si falla
    
    def _calculate_stl_packing(self, box_length, box_width, box_height, 
                              obj_length, obj_width, obj_height, mesh, rotation):
        """Calcula l'empaquetament òptim per una orientació específica amb posicions correctes SIN SUPERPOSICIÓ"""
        try:
            # Calcular quants objectes caben en cada dimensió amb marge de seguretat
            margin = 0.1  # 0.1mm de marge entre objectes
            
            pieces_x = max(1, int((box_length + margin) / (obj_length + margin)))
            pieces_y = max(1, int((box_width + margin) / (obj_width + margin)))
            pieces_z = max(1, int((box_height + margin) / (obj_height + margin)))
            
            print(f"    🔢 Graella calculada: {pieces_x} × {pieces_y} × {pieces_z}")
            print(f"    📐 Objecte: {obj_length:.1f} × {obj_width:.1f} × {obj_height:.1f} mm")
            
            # Generar posicions per cada objecte SIN SUPERPOSICIÓ
            items = []
            object_id = 0
            
            for z in range(pieces_z):
                for y in range(pieces_y):
                    for x in range(pieces_x):
                        # Calcular posició de la cantonada inferior esquerra de cada objecte
                        start_x = x * (obj_length + margin)
                        start_y = y * (obj_width + margin)
                        start_z = z * (obj_height + margin)
                        
                        # Calcular el centre de l'objecte
                        center_x = start_x + obj_length/2
                        center_y = start_y + obj_width/2  
                        center_z = start_z + obj_height/2
                        
                        # Verificar que l'objecte complet cap dins del contenidor
                        if (start_x + obj_length <= box_length and 
                            start_y + obj_width <= box_width and 
                            start_z + obj_height <= box_height):
                            
                            position = [center_x, center_y, center_z]
                            
                            items.append({
                                'id': object_id,
                                'position': position,
                                'dimensions': [obj_length, obj_width, obj_height],
                                'rotation': rotation,
                                'stl_mesh': mesh,
                                'is_stl': True,
                                'bounds': {
                                    'min': [start_x, start_y, start_z],
                                    'max': [start_x + obj_length, start_y + obj_width, start_z + obj_height]
                                }
                            })
                            
                            print(f"      ✅ Objecte {object_id+1}: centre({center_x:.1f}, {center_y:.1f}, {center_z:.1f})")
                            object_id += 1
                        else:
                            print(f"      ❌ Objecte no cap: posició ({start_x:.1f}, {start_y:.1f}, {start_z:.1f})")
            
            total_pieces = len(items)
            print(f"    📊 Total objectes col·locats: {total_pieces}")
            
            return {
                'total_pieces': total_pieces,
                'items': items,
                'grid': [pieces_x, pieces_y, pieces_z],
                'utilization': {
                    'x': (pieces_x * (obj_length + margin)) / box_length,
                    'y': (pieces_y * (obj_width + margin)) / box_width,
                    'z': (pieces_z * (obj_height + margin)) / box_height
                }
            }
            
        except Exception as e:
            print(f"⚠️ Error calculant empaquetament: {e}")
            return {'total_pieces': 0, 'items': []}
            
    def _try_mixed_orientations_packing(self, box_dims, mesh):
        """Prova empaquetament amb orientacions mixtes (futur desenvolupament)"""
        # TODO: Implementar empaquetament amb objectes en diferents orientacions
        # Això seria el següent nivell d'optimització
        pass
            
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
            real_efficiency = result.get('real_efficiency', 0)
            
            results = f"🎉 RESULTATS DE L'OPTIMITZACIÓ\n"
            results += f"=" * 40 + "\n\n"
            results += f"📊 Objectes que caben: {max_objects:,}\n"
            results += f"📈 Eficiència pràctica (espai ocupat): {efficiency:.1f}%\n"
            results += f"📉 Eficiència real STL (volum sòlid): {real_efficiency:.1f}%\n"
            
            if 'box_volume' in result:
                results += f"📦 Volum caixa: {result['box_volume']:,.0f} mm³\n"
                
            if 'used_volume' in result:
                results += f"📋 Espai ocupat (bounding boxes): {result['used_volume']:,.0f} mm³\n"
                
            if 'used_real_volume' in result:
                results += f"📐 Volum STL real utilitzat: {result['used_real_volume']:,.0f} mm³\n"
                
            method = result.get('method', 'unknown')
            results += f"🔧 Mètode: {method}\n"
            
            # Mostrar informació de la rotació òptima
            if 'best_orientation' in result:
                rotation = result['best_orientation']
                results += f"🔄 Rotació òptima: {rotation[0]}°, {rotation[1]}°, {rotation[2]}°\n"
                
            if 'piece_dimensions' in result:
                dims = result['piece_dimensions']
                results += f"📐 Dimensions rotades: {dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f} mm\n"
            
            if 'bins' in result and result['bins']:
                bin_info = result['bins'][0]
                if 'items' in bin_info:
                    results += f"📍 Posicions calculades: {len(bin_info['items'])}\n"
                    
                    # Mostrar informació de la graella si està disponible
                    first_item = bin_info['items'][0] if bin_info['items'] else None
                    if first_item and 'bounds' in first_item:
                        results += f"📋 Empaquetament intel·ligent amb geometria STL real\n"
                    
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
            summary += f"   • Eficiència pràctica: {result.get('efficiency', 0):.1f}%\n"
            if 'real_efficiency' in result:
                summary += f"   • Eficiència real STL: {result.get('real_efficiency', 0):.1f}%\n"
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
        """Visualitza els resultats de l'empaquetament en 3D amb PyVista"""
        print("🎮 ===== INICIANT VISUALITZACIÓ 3D (PYVISTA) =====")
        
        if not self.optimization_results:
            print("❌ ERROR: No hi ha optimization_results")
            messagebox.showwarning("Avís", "Primer has de calcular l'empaquetament")
            return
            
        try:
            import pyvista as pv
            import numpy as np
            import numpy as np
            import traceback
            
            print("🔍 Verificant dades de l'optimització...")
            
            # Verificar dades dels resultats
            bins_data = self.optimization_results.get('bins', [])
            print(f"📋 Bins data trobat: {len(bins_data)} bins")
            
            if not bins_data:
                print("❌ ERROR: No hi ha dades de bins")
                messagebox.showwarning("Avís", "No hi ha dades de visualització disponibles")
                return
                
            bin_data = bins_data[0]
            items = bin_data.get('items', [])
            container_dims = bin_data.get('bin', {}).get('dimensions', [100, 100, 100])
            
            print(f"📦 Contenidor: {container_dims[0]} × {container_dims[1]} × {container_dims[2]} mm")
            print(f"📋 Items trobats: {len(items)}")
            
            if len(items) == 0:
                print("❌ ERROR: No hi ha items per visualitzar")
                messagebox.showwarning("Avís", "No hi ha objectes per visualitzar")
                return
            
            # Debug: mostrar primer item
            if items:
                first_item = items[0]
                print(f"🔍 Primer item: {list(first_item.keys())}")
                print(f"   - position: {first_item.get('position', 'MISSING')}")
                print(f"   - rotation: {first_item.get('rotation', 'MISSING')}")
                print(f"   - dimensions: {first_item.get('dimensions', 'MISSING')}")
                print(f"   - stl_mesh: {'YES' if first_item.get('stl_mesh') else 'NO'}")
            
            # Crear plotter PyVista amb configuració optimitzada
            print("🎨 Creant plotter PyVista...")
            plotter = pv.Plotter(window_size=(1200, 900))
            plotter.set_background('white')
            
            # Configurar il·luminació uniforme per colors consistents
            plotter.enable_anti_aliasing()  # Anti-aliasing per millor qualitat
            
            # Configurar colors més distintius i uniformes
            colors = [
                '#DC143C',  # Crimson (vermell)
                '#1E90FF',  # DodgerBlue (blau)
                '#228B22',  # ForestGreen (verd)
                '#FF8C00',  # DarkOrange (taronja)
                '#9370DB',  # MediumPurple (lila)
                '#D2691E',  # Chocolate (marró)
                '#FF1493',  # DeepPink (rosa)
                '#696969',  # DimGray (gris)
                '#808000',  # Olive (oliva)
                '#00CED1'   # DarkTurquoise (turquesa)
            ]
            
            # Determinar quina malla usar
            mesh_to_show = self.simplified_mesh if (self.use_simplified.get() and self.simplified_mesh) else self.original_mesh
            
            if not mesh_to_show:
                print("❌ ERROR: No hi ha malla carregada")
                messagebox.showwarning("Avís", "No hi ha malla carregada per visualitzar")
                return
            
            print(f"🔧 Usant malla: {'simplificada' if self.simplified_mesh and self.use_simplified.get() else 'original'}")
            
            # Dibuixar contenidor com a wireframe
            print("📦 Dibuixant contenidor...")
            self._draw_container_wireframe_pyvista(plotter, container_dims)
            
            # Processem cada objecte
            print(f"🔧 Processant {len(items)} objectes...")
            pieces_added = 0
            
            for i, item in enumerate(items):
                print(f"\n🔸 === PROCESSANT OBJECTE {i+1}/{len(items)} ===")
                try:
                    # Convertir numpy arrays a llistes Python normals
                    pos = item.get('position', [0, 0, 0])
                    if hasattr(pos, 'tolist'):
                        pos = pos.tolist()
                    elif hasattr(pos[0], 'item'):
                        pos = [float(p.item()) if hasattr(p, 'item') else float(p) for p in pos]
                    else:
                        pos = [float(p) for p in pos]
                    
                    rotation = item.get('rotation', [0, 0, 0])
                    if hasattr(rotation, 'tolist'):
                        rotation = rotation.tolist()
                    elif hasattr(rotation[0], 'item'):
                        rotation = [float(r.item()) if hasattr(r, 'item') else float(r) for r in rotation]
                    else:
                        rotation = [float(r) for r in rotation]
                    
                    dimensions = item.get('dimensions', [10, 10, 10])
                    if hasattr(dimensions, 'tolist'):
                        dimensions = dimensions.tolist()
                    elif hasattr(dimensions[0], 'item'):
                        dimensions = [float(d.item()) if hasattr(d, 'item') else float(d) for d in dimensions]
                    else:
                        dimensions = [float(d) for d in dimensions]
                    
                    print(f"   📍 Posició neta: {pos}")
                    print(f"   📐 Dimensions netes: {dimensions}")
                    
                    # CANVI: Mostrar STL real amb PyVista per millor rendiment
                    stl_mesh = item.get('stl_mesh')
                    if stl_mesh and hasattr(stl_mesh, 'vertices'):
                        print(f"   🎨 Usant visualització STL real amb PyVista...")
                        # Aplicar rotació a la malla si cal
                        rotated_mesh = self._apply_rotation_to_mesh(stl_mesh, rotation)
                        # Usar posició central per STL
                        self._draw_stl_mesh_pyvista(plotter, rotated_mesh, pos, colors[i % len(colors)], i+1)
                    else:
                        # Fallback: usar cub si no hi ha malla STL
                        print(f"   🔲 Fallback: usant visualització amb cub rectangular...")
                        corner_pos = [
                            pos[0] - dimensions[0]/2,  # x: centre - amplada/2 = cantonada esquerra
                            pos[1] - dimensions[1]/2,  # y: centre - altura/2 = cantonada frontal  
                            pos[2] - dimensions[2]/2   # z: centre - profunditat/2 = cantonada inferior
                        ]
                        corner_pos = [max(0, c) for c in corner_pos]
                        self._draw_cube_pyvista(plotter, corner_pos, dimensions, colors[i % len(colors)], i+1)
                    
                    pieces_added += 1
                    print(f"   ✅ Objecte {i+1} afegit correctament")
                    
                except Exception as e:
                    print(f"   ❌ ERROR processant objecte {i+1}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"\n📊 RESUM: {pieces_added}/{len(items)} objectes afegits correctament")
            
            # Configurar vista i títol
            print("🎨 Configurant vista...")
            max_objects = self.optimization_results.get('max_objects', 0)
            efficiency = self.optimization_results.get('efficiency', 0)
            real_efficiency = self.optimization_results.get('real_efficiency', 0)
            
            title = f"Empaquetament: {max_objects} objectes - "
            title += f"Eficiència: {efficiency:.1f}% (pràctica) | {real_efficiency:.1f}% (volum STL)"
            
            # Configurar vista isomètrica
            plotter.camera_position = 'iso'
            plotter.show_grid()
            plotter.add_axes()
            
            # Afegir títol
            plotter.add_text(title, position='upper_edge', font_size=12, color='black')
            
            print("🚀 Mostrant finestra PyVista...")
            
            # Mostrar la visualització
            plotter.show(interactive=True, auto_close=False)
            
            print("✅ Visualització 3D completada - finestra hauria de ser visible!")
            
        except ImportError as e:
            print("❌ ERROR: PyVista no està disponible")
            messagebox.showerror("Error", f"PyVista no està instal·lat:\n{e}")
        except Exception as e:
            error_msg = f"Error crític en visualització 3D: {e}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"No s'ha pogut crear la visualització 3D:\n{e}")
    
    def _draw_container_wireframe_pyvista(self, plotter, dims):
        """Dibuixa el contenidor com a wireframe amb PyVista"""
        try:
            import pyvista as pv
            import numpy as np
            
            # Crear les vèrtexs del contenidor
            vertices = np.array([
                [0, 0, 0], [dims[0], 0, 0], [dims[0], dims[1], 0], [0, dims[1], 0],  # Base inferior
                [0, 0, dims[2]], [dims[0], 0, dims[2]], [dims[0], dims[1], dims[2]], [0, dims[1], dims[2]]  # Base superior
            ])
            
            # Definir les arestes del contenidor
            edges = [
                # Base inferior
                [0, 1], [1, 2], [2, 3], [3, 0],
                # Base superior  
                [4, 5], [5, 6], [6, 7], [7, 4],
                # Arestes verticals
                [0, 4], [1, 5], [2, 6], [3, 7]
            ]
            
            # Crear línies per cada aresta
            for edge in edges:
                line_points = vertices[edge]
                line = pv.Line(line_points[0], line_points[1])
                plotter.add_mesh(line, color='black', line_width=3, opacity=0.8)
                
            print("   ✅ Contenidor wireframe PyVista dibuixat")
            
        except Exception as e:
            print(f"   ❌ Error dibuixant contenidor PyVista: {e}")
    
    def _draw_container_wireframe(self, ax, dims):
        """Dibuixa el contenidor com a wireframe"""
        try:
            import numpy as np
            
            # Definir les vèrtexs del contenidor
            vertices = [
                [0, 0, 0], [dims[0], 0, 0], [dims[0], dims[1], 0], [0, dims[1], 0],  # Base inferior
                [0, 0, dims[2]], [dims[0], 0, dims[2]], [dims[0], dims[1], dims[2]], [0, dims[1], dims[2]]  # Base superior
            ]
            
            # Definir les arestes del contenidor
            edges = [
                # Base inferior
                [0, 1], [1, 2], [2, 3], [3, 0],
                # Base superior  
                [4, 5], [5, 6], [6, 7], [7, 4],
                # Arestes verticals
                [0, 4], [1, 5], [2, 6], [3, 7]
            ]
            
            # Dibuixar cada aresta
            for edge in edges:
                points = np.array([vertices[edge[0]], vertices[edge[1]]])
                ax.plot3D(points[:, 0], points[:, 1], points[:, 2], 'k-', linewidth=2, alpha=0.6)
                
            print("   ✅ Contenidor wireframe dibuixat")
            
        except Exception as e:
            print(f"   ❌ Error dibuixant contenidor: {e}")
    
    def _draw_stl_mesh_matplotlib(self, ax, mesh, position, color, obj_id):
        """Dibuixa una malla STL amb matplotlib optimitzada"""
        try:
            import numpy as np
            from mpl_toolkits.mplot3d.art3d import Poly3DCollection
            
            # Convertir posició a array numpy normal
            position = np.array([float(p) for p in position])
            
            # Obtenir vèrtexs i cares de la malla
            vertices = mesh.vertices
            faces = mesh.faces
            
            print(f"      🔧 Malla STL: {len(vertices)} vèrtexs, {len(faces)} cares")
            
            # La malla ja està centrada a l'origen després de _apply_rotation_to_mesh
            # Només cal aplicar la translació al centre desitjat
            mesh_center = np.mean(vertices, axis=0)  # Centre actual de la malla
            translation = position - mesh_center  # Vector per moure al centre desitjat
            
            # Aplicar translació als vèrtexs
            translated_vertices = vertices + translation
            
            print(f"      📍 Centre malla: {mesh_center}, Posició objectiu: {position}")
            print(f"      🔄 Translació aplicada: {translation}")
            
            # Optimització: Reduir cares per visualització fluida
            max_faces_to_show = 300  # Augmentat lleugerament per millor qualitat
            if len(faces) > max_faces_to_show:
                step = max(1, len(faces) // max_faces_to_show)
                selected_faces = faces[::step]
                print(f"      📉 Mostrant {len(selected_faces)}/{len(faces)} cares per rendiment")
            else:
                selected_faces = faces
            
            # Crear polígons per cada cara seleccionada
            polygons = []
            valid_polygons = 0
            
            for face in selected_faces:
                try:
                    # Verificar que la cara té 3 vèrtexs vàlids
                    if len(face) == 3 and all(0 <= idx < len(translated_vertices) for idx in face):
                        polygon = translated_vertices[face]
                        # Verificar que el polígon no té NaN o infinits
                        if not np.any(np.isnan(polygon)) and not np.any(np.isinf(polygon)):
                            polygons.append(polygon)
                            valid_polygons += 1
                except Exception as face_error:
                    print(f"        ⚠️ Error en cara: {face_error}")
                    continue
            
            if valid_polygons == 0:
                print(f"      ❌ No s'han pogut processar cares vàlides, usant cub")
                # Fallback: dibuixar com a cub
                bounds = mesh.bounds if hasattr(mesh, 'bounds') else [[0,0,0], [10,10,10]]
                dims = bounds[1] - bounds[0]
                # Convertir posició central a cantonada pel cub
                corner_pos = position - dims/2
                self._draw_cube_matplotlib(ax, corner_pos.tolist(), dims.tolist(), color, obj_id)
                return
            
            print(f"      📊 Processades {valid_polygons} cares vàlides")
            
            # Crear col·lecció de polígons amb configuració millorada
            poly3d = Poly3DCollection(
                polygons, 
                alpha=0.85,  # Lleugerament més opac per millor visibilitat
                facecolor=color, 
                edgecolor='darkgray', 
                linewidths=0.1  # Línies més visibles
            )
            ax.add_collection3d(poly3d)
            
            # Afegir etiqueta en el centre de l'objecte
            ax.text(position[0], position[1], position[2], f'STL {obj_id}', 
                   fontsize=10, color='white', weight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='black', alpha=0.7))
            
            print(f"      ✅ Malla STL dibuixada amb {valid_polygons} cares")
            
        except Exception as e:
            print(f"      ❌ Error dibuixant malla STL: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: dibuixar com a cub
            try:
                bounds = mesh.bounds if hasattr(mesh, 'bounds') else [[0,0,0], [10,10,10]]
                dims = bounds[1] - bounds[0]
                # Convertir posició central a cantonada pel cub
                corner_pos = position - dims/2 if hasattr(position, '__len__') else [position-5, position-5, position-5]
                position_list = corner_pos.tolist() if hasattr(corner_pos, 'tolist') else [float(corner_pos[0]), float(corner_pos[1]), float(corner_pos[2])]
                dims_list = [float(d) for d in dims] if hasattr(dims, '__iter__') else [10, 10, 10]
                self._draw_cube_matplotlib(ax, position_list, dims_list, color, obj_id)
            except Exception as fallback_error:
                print(f"      ❌ Error en fallback cub: {fallback_error}")
    
    def _draw_stl_mesh_pyvista(self, plotter, mesh, position, color, obj_id):
        """Dibuixa una malla STL amb PyVista per millor rendiment"""
        try:
            import pyvista as pv
            import numpy as np
            
            # Convertir posició a array numpy normal
            position = np.array([float(p) for p in position])
            
            # Obtenir vèrtexs i cares de la malla
            vertices = mesh.vertices
            faces = mesh.faces
            
            print(f"      🔧 Malla STL: {len(vertices)} vèrtexs, {len(faces)} cares")
            
            # La malla ja està centrada a l'origen després de _apply_rotation_to_mesh
            # Només cal aplicar la translació al centre desitjat
            mesh_center = np.mean(vertices, axis=0)  # Centre actual de la malla
            translation = position - mesh_center  # Vector per moure al centre desitjat
            
            # Aplicar translació als vèrtexs
            translated_vertices = vertices + translation
            
            print(f"      📍 Centre malla: {mesh_center}, Posició objectiu: {position}")
            print(f"      🔄 Translació aplicada: {translation}")
            
            # Crear malla PyVista
            # PyVista necessita faces amb format [n_points, p0, p1, p2, ...]
            faces_with_count = []
            for face in faces:
                if len(face) == 3:  # Triangles
                    faces_with_count.extend([3, face[0], face[1], face[2]])
                else:
                    print(f"        ⚠️ Cara no triangular ignorada: {len(face)} vèrtexs")
            
            if len(faces_with_count) == 0:
                print(f"      ❌ No hi ha cares vàlides, usant cub")
                bounds = mesh.bounds if hasattr(mesh, 'bounds') else [[0,0,0], [10,10,10]]
                dims = bounds[1] - bounds[0]
                corner_pos = position - dims/2
                self._draw_cube_pyvista(plotter, corner_pos.tolist(), dims.tolist(), color, obj_id)
                return
            
            # Crear PolyData de PyVista
            pv_mesh = pv.PolyData(translated_vertices, faces_with_count)
            
            # Afegir malla al plotter amb color uniforme
            plotter.add_mesh(
                pv_mesh, 
                color=color,
                opacity=0.85,
                show_edges=True,
                edge_color='darkgray',
                line_width=0.5,
                smooth_shading=False,  # Desactivar suavitzat per colors uniformes
                lighting=True,         # Mantenir il·luminació
                ambient=0.3,          # Il·luminació ambient
                diffuse=0.7,          # Il·luminació difusa
                specular=0.1,         # Il·luminació especular mínima
                scalars=None,         # No usar escalars per evitar degradats
                cmap=None             # No usar mapa de colors
            )
            
            # Afegir etiqueta en el centre de l'objecte
            plotter.add_point_labels(
                [position], 
                [f'STL {obj_id}'], 
                point_size=0,  # No mostrar el punt, només l'etiqueta
                font_size=12,
                text_color='white',
                shape_color='black',
                shape_opacity=0.7,
                pickable=False
            )
            
            print(f"      ✅ Malla STL PyVista dibuixada amb {len(faces)} cares")
            
        except Exception as e:
            print(f"      ❌ Error dibuixant malla STL PyVista: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: dibuixar com a cub
            try:
                bounds = mesh.bounds if hasattr(mesh, 'bounds') else [[0,0,0], [10,10,10]]
                dims = bounds[1] - bounds[0]
                corner_pos = position - dims/2 if hasattr(position, '__len__') else [position-5, position-5, position-5]
                position_list = corner_pos.tolist() if hasattr(corner_pos, 'tolist') else [float(corner_pos[0]), float(corner_pos[1]), float(corner_pos[2])]
                dims_list = [float(d) for d in dims] if hasattr(dims, '__iter__') else [10, 10, 10]
                self._draw_cube_pyvista(plotter, position_list, dims_list, color, obj_id)
            except Exception as fallback_error:
                print(f"      ❌ Error en fallback cub PyVista: {fallback_error}")
    
    def _draw_cube_pyvista(self, plotter, position, dimensions, color, obj_id):
        """Dibuixa un cub amb PyVista posicionat per cantonades"""
        try:
            import pyvista as pv
            import numpy as np
            
            # Convertir tots els valors a float Python normals
            position = [float(p) for p in position]
            dimensions = [float(d) for d in dimensions]
            
            print(f"      🔲 Creant cub PyVista: cantonada={position}, dims={dimensions}")
            
            # Crear cub centrat a l'origen
            cube = pv.Cube()
            
            # Escalar el cub a les dimensions desitjades
            cube.scale([dimensions[0], dimensions[1], dimensions[2]], inplace=True)
            
            # Calcular el centre del cub basant-se en la cantonada i dimensions
            center = [
                position[0] + dimensions[0]/2,
                position[1] + dimensions[1]/2,
                position[2] + dimensions[2]/2
            ]
            
            # Trasladar el cub al centre calculat
            cube.translate(center, inplace=True)
            
            # Afegir el cub al plotter amb color uniforme
            plotter.add_mesh(
                cube,
                color=color,
                opacity=0.8,
                show_edges=True,
                edge_color='black',
                line_width=2,
                smooth_shading=False,  # Desactivar suavitzat per colors uniformes
                lighting=True,         # Mantenir il·luminació
                ambient=0.3,          # Il·luminació ambient
                diffuse=0.7,          # Il·luminació difusa
                specular=0.1,         # Il·luminació especular mínima
                scalars=None,         # No usar escalars
                cmap=None             # No usar mapa de colors
            )
            
            # Afegir etiqueta en el centre del cub
            plotter.add_point_labels(
                [center], 
                [f'Obj {obj_id}'], 
                point_size=0,
                font_size=12,
                text_color='white',
                shape_color=color,
                shape_opacity=0.8,
                pickable=False
            )
            
            print(f"      ✅ Cub PyVista posicionat correctament: centre {center}")
            
        except Exception as e:
            print(f"      ❌ Error dibuixant cub PyVista: {e}")
            import traceback
            traceback.print_exc()
    
    def _draw_cube_matplotlib(self, ax, position, dimensions, color, obj_id):
        """Dibuixa un cub posicionat per cantonades (no centrat) per evitar que surti fora"""
        try:
            import numpy as np
            from mpl_toolkits.mplot3d.art3d import Poly3DCollection
            
            # Convertir tots els valors a float Python normals
            position = [float(p) for p in position]
            dimensions = [float(d) for d in dimensions]
            
            print(f"      🔲 Creant cub: cantonada={position}, dims={dimensions}")
            
            # CANVI IMPORTANT: position és la cantonada inferior esquerra, NO el centre
            # Això assegura que l'objecte està dins del contenidor
            corner = np.array(position)
            dims = np.array(dimensions)
            
            # Calcular les 8 vèrtexs del cub des de la cantonada
            vertices = [
                # Base inferior (z = corner[2])
                corner,                                           # (x, y, z)
                corner + [dims[0], 0, 0],                        # (x+w, y, z)
                corner + [dims[0], dims[1], 0],                  # (x+w, y+h, z)
                corner + [0, dims[1], 0],                        # (x, y+h, z)
                # Base superior (z = corner[2] + dims[2])
                corner + [0, 0, dims[2]],                        # (x, y, z+d)
                corner + [dims[0], 0, dims[2]],                  # (x+w, y, z+d)
                corner + [dims[0], dims[1], dims[2]],            # (x+w, y+h, z+d)
                corner + [0, dims[1], dims[2]]                   # (x, y+h, z+d)
            ]
            
            # Definir les 6 cares del cub
            faces = [
                [vertices[0], vertices[1], vertices[2], vertices[3]],  # Base inferior
                [vertices[4], vertices[5], vertices[6], vertices[7]],  # Base superior
                [vertices[0], vertices[1], vertices[5], vertices[4]],  # Cara frontal
                [vertices[2], vertices[3], vertices[7], vertices[6]],  # Cara posterior
                [vertices[1], vertices[2], vertices[6], vertices[5]],  # Cara dreta
                [vertices[4], vertices[7], vertices[3], vertices[0]]   # Cara esquerra
            ]
            
            # Crear col·lecció de polígons
            poly3d = Poly3DCollection(
                faces, 
                alpha=0.8, 
                facecolor=color, 
                edgecolor='black', 
                linewidths=1.5
            )
            ax.add_collection3d(poly3d)
            
            # Calcular centre per l'etiqueta
            center = corner + dims/2
            
            # Afegir etiqueta en el centre del cub
            ax.text(center[0], center[1], center[2], f'Obj {obj_id}', 
                   fontsize=10, color='white', weight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.8))
            
            print(f"      ✅ Cub posicionat correctament: cantonada {position} + dimensions {dimensions}")
            
        except Exception as e:
            print(f"      ❌ Error dibuixant cub: {e}")
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
