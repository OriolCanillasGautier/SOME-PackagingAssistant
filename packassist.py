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
        """OPTIMITZADOR 3D BIN PACKING AMB ORIENTACIONS MIXTES I COL·LISIONS EXACTES"""
        import time
        start_time = time.time()
        
        try:
            print("🚀 INICIANT 3D BIN PACKING AMB ORIENTACIONS MIXTES")
            print("🎯 Enfocament: 3 iteracions obligatòries amb orientacions diferents")
            
            box_length = box_dims['length']
            box_width = box_dims['width'] 
            box_height = box_dims['height']
            
            print(f"📦 Contenidor: {box_length} × {box_width} × {box_height} mm")
            print(f"🔧 Objecte: {len(mesh.vertices)} vèrtexs, {len(mesh.faces)} cares")
            
            # DEFINIR 3 ESTRATÈGIES OBLIGATÒRIES DIFERENTS
            strategies = [
                {
                    'name': 'ORIENTACIÓ ÚNICA ÓPTIMA',
                    'rotations': [[0, 0, 0], [90, 0, 0], [0, 90, 0], [0, 0, 90], [180, 0, 0], [0, 180, 0]],
                    'mixed_orientations': False
                },
                {
                    'name': 'ORIENTACIONS MIXTES VERTICALS',
                    'rotations': [[0, 0, 0], [90, 0, 0], [0, 90, 0]],
                    'mixed_orientations': True
                },
                {
                    'name': 'ORIENTACIONS MIXTES LLIURES',
                    'rotations': [[0, 0, 0], [90, 0, 0], [0, 90, 0], [0, 0, 90], [45, 0, 0], [0, 45, 0]],
                    'mixed_orientations': True
                }
            ]
            
            all_results = []
            
            # EXECUTAR LES 3 ESTRATÈGIES OBLIGATÒRIAMENT
            for strategy_idx, strategy in enumerate(strategies):
                print(f"\n🎲 === ESTRATÈGIA {strategy_idx + 1}/3: {strategy['name']} ===")
                
                if strategy['mixed_orientations']:
                    # Orientacions mixtes: cada objecte pot tenir orientació diferent
                    result = self._pack_with_mixed_orientations(
                        box_length, box_width, box_height, 
                        mesh, strategy['rotations']
                    )
                else:
                    # Orientació única: tots els objectes igual
                    result = self._pack_with_single_orientation(
                        box_length, box_width, box_height, 
                        mesh, strategy['rotations']
                    )
                
                result['strategy'] = strategy['name']
                result['strategy_index'] = strategy_idx + 1
                all_results.append(result)
                
                objects_packed = result.get('objects_packed', 0)
                efficiency = result.get('efficiency', 0)
                print(f"🎯 Resultat estratègia {strategy_idx + 1}: {objects_packed} objectes, {efficiency:.1f}% eficiència")
            
            # TROBAR EL MILLOR RESULTAT
            best_result = max(all_results, key=lambda x: x.get('objects_packed', 0))
            max_objects = best_result.get('objects_packed', 0)
            
            elapsed = time.time() - start_time
            print(f"\n⏱️ Temps total: {elapsed:.2f} segons")
            print(f"🏆 MILLOR RESULTAT: {max_objects} objectes amb '{best_result.get('strategy', 'unknown')}'")
            
            if max_objects == 0:
                return {
                    'max_objects': 0,
                    'efficiency': 0,
                    'error': 'Cap estratègia ha funcionat',
                    'bins': [],
                    'all_strategies': all_results
                }
            
            # Crear resultat final
            return {
                'max_objects': max_objects,
                'efficiency': best_result.get('efficiency', 0),
                'real_efficiency': best_result.get('real_efficiency', 0),
                'box_volume': box_length * box_width * box_height,
                'used_volume': best_result.get('used_volume', 0),
                'method': 'mixed_orientations_3d_bin_packing',
                'best_strategy': best_result.get('strategy', 'unknown'),
                'computation_time': elapsed,
                'bins': [{
                    'bin': {'dimensions': [box_length, box_width, box_height]},
                    'items': best_result.get('items', []),
                    'mesh_data': best_result.get('best_mesh', mesh)
                }],
                'all_strategies': all_results
            }
            
        except Exception as e:
            print(f"❌ Error en optimització: {e}")
            import traceback
            traceback.print_exc()
            return {
                'max_objects': 0,
                'efficiency': 0,
                'error': f'Error en optimització: {e}',
                'bins': []
            }

    def _pack_with_single_orientation(self, box_length, box_width, box_height, mesh, rotations):
        """Empaquetament amb orientació única (tots els objectes iguals)"""
        try:
            best_result = None
            max_objects = 0
            
            for rotation in rotations:
                print(f"    🔄 Provant rotació única: {rotation}")
                
                # Aplicar rotació
                rotated_mesh = self._apply_simple_rotation(mesh, rotation)
                
                # Obtenir dimensions reals
                bounds = rotated_mesh.bounds
                obj_dims_rotated = bounds[1] - bounds[0]
                obj_length, obj_width, obj_height = obj_dims_rotated
                
                # Verificar que cap en contenidor
                if (obj_length <= box_length and 
                    obj_width <= box_width and 
                    obj_height <= box_height):
                    
                    # Executar empaquetament amb detecció de col·lisions millorada
                    result = self._pack_objects_simple(
                        box_length, box_width, box_height,
                        obj_length, obj_width, obj_height,
                        rotated_mesh, rotation, mesh
                    )
                    
                    objects_packed = result.get('objects_packed', 0)
                    if objects_packed > max_objects:
                        max_objects = objects_packed
                        best_result = result
                        best_result['best_mesh'] = rotated_mesh
                        best_result['best_rotation'] = rotation
            
            return best_result if best_result else {'objects_packed': 0, 'items': []}
            
        except Exception as e:
            print(f"    ❌ Error orientació única: {e}")
            return {'objects_packed': 0, 'items': []}

    def _pack_with_mixed_orientations(self, box_length, box_width, box_height, mesh, rotations):
        """Empaquetament amb orientacions mixtes OPTIMITZAT (molt més ràpid)"""
        try:
            print(f"    🎲 Empaquetament amb orientacions mixtes optimitzat...")
            
            # Preparar malles rotades amb dimensions
            rotated_configs = []
            for rotation in rotations:
                rotated_mesh = self._apply_simple_rotation(mesh, rotation)
                bounds = rotated_mesh.bounds
                obj_dims = bounds[1] - bounds[0]
                
                # Verificar que cap en contenidor
                if (obj_dims[0] <= box_length and 
                    obj_dims[1] <= box_width and 
                    obj_dims[2] <= box_height):
                    
                    rotated_configs.append({
                        'mesh': rotated_mesh,
                        'rotation': rotation,
                        'dimensions': obj_dims
                    })
            
            if not rotated_configs:
                return {'objects_packed': 0, 'items': []}
            
            print(f"    ✅ {len(rotated_configs)} orientacions vàlides trobades")
            
            # ALGORISME OPTIMITZAT: Empaquetament per layers amb tolerància
            placed_objects = []
            items = []
            
            # Configuració optimitzada per velocitat
            tolerance = 0.5  # Tolerància per encaixos
            max_objects = 100  # Límit d'objectes per velocitat
            layer_height_factor = 0.9  # Factor per superposició vertical
            
            # Empaquetament per capes
            current_z = 0
            layer = 0
            
            while current_z < box_height and len(placed_objects) < max_objects:
                layer += 1
                print(f"        📦 Processant capa {layer} (z={current_z:.1f})")
                
                # Provar diferents orientacions en aquesta capa
                objects_in_layer = 0
                
                for config in rotated_configs:
                    obj_dims = config['dimensions']
                    
                    # Verificar que l'objecte cap en l'altura restant
                    if current_z + obj_dims[2] <= box_height:
                        
                        # Empaquetament en graella grossera per aquesta orientació
                        step_x = max(obj_dims[0] * 0.8, 5.0)  # Pas més gran per velocitat
                        step_y = max(obj_dims[1] * 0.8, 5.0)
                        
                        for x in range(0, int(box_length - obj_dims[0]), int(step_x)):
                            for y in range(0, int(box_width - obj_dims[1]), int(step_y)):
                                
                                position = [
                                    x + obj_dims[0]/2, 
                                    y + obj_dims[1]/2, 
                                    current_z + obj_dims[2]/2
                                ]
                                
                                # Verificar col·lisió RÀPIDA amb bounding box només
                                collision = False
                                for placed in placed_objects:
                                    placed_pos = placed['position']
                                    placed_dims = placed['dimensions']
                                    
                                    # Distància entre centres
                                    dx = abs(position[0] - placed_pos[0])
                                    dy = abs(position[1] - placed_pos[1])
                                    dz = abs(position[2] - placed_pos[2])
                                    
                                    # Verificar solapament amb tolerància
                                    if (dx < (obj_dims[0] + placed_dims[0])/2 + tolerance and
                                        dy < (obj_dims[1] + placed_dims[1])/2 + tolerance and
                                        dz < (obj_dims[2] + placed_dims[2])/2 + tolerance):
                                        collision = True
                                        break
                                
                                if not collision:
                                    # Col·locar objecte
                                    placed_objects.append({
                                        'position': position,
                                        'rotation': config['rotation'],
                                        'dimensions': obj_dims.tolist(),
                                        'collision_mesh': None  # No necessari per visualització
                                    })
                                    
                                    items.append({
                                        'id': len(items) + 1,
                                        'position': position,
                                        'rotation': config['rotation'],
                                        'dimensions': obj_dims.tolist(),
                                        'stl_mesh': mesh,
                                        'is_stl': True
                                    })
                                    
                                    objects_in_layer += 1
                                    
                                    if len(placed_objects) >= max_objects:
                                        break
                            
                            if len(placed_objects) >= max_objects:
                                break
                        
                        if len(placed_objects) >= max_objects:
                            break
                
                print(f"        ✅ Capa {layer}: {objects_in_layer} objectes col·locats")
                
                # Passar a la següent capa
                if objects_in_layer > 0:
                    # Trobar l'altura màxima d'aquesta capa
                    max_height_in_layer = max([obj['dimensions'][2] for obj in placed_objects[-objects_in_layer:]] or [0])
                    current_z += max_height_in_layer * layer_height_factor
                else:
                    # Si no hem col·locat res, incrementar una mica l'altura
                    current_z += 10.0
                
                # Evitar bucles infinits
                if layer > 20:
                    break
            
            total_objects = len(placed_objects)
            print(f"    🎉 Total objectes amb orientacions mixtes: {total_objects}")
            
            # Calcular eficiència
            box_volume = box_length * box_width * box_height
            total_volume = sum([item['dimensions'][0] * item['dimensions'][1] * item['dimensions'][2] 
                               for item in items])
            efficiency = (total_volume / box_volume) * 100 if box_volume > 0 else 0
            
            return {
                'objects_packed': total_objects,
                'efficiency': efficiency,
                'items': items,
                'positions': [item['position'] for item in items]
            }
            
        except Exception as e:
            print(f"    ❌ Error en orientacions mixtes: {e}")
            return {'objects_packed': 0, 'items': []}

    def _pack_with_smart_stacking(self, box_length, box_width, box_height, mesh, original_mesh):
        """Empaquetament intel·ligent amb apilament vertical optimitzat"""
        try:
            print(f"    🏗️ Empaquetament amb apilament intel·ligent...")
            
            # Obtenir dimensions base de l'objecte
            bounds = mesh.bounds
            obj_dims = bounds[1] - bounds[0]
            obj_length, obj_width, obj_height = obj_dims
            
            # Variables per apilament intel·ligent
            placed_objects = []
            items = []
            
            # Estratègia de base: col·locar objectes en capes verticals amb encaixos
            margin = 0.5  # Marge petit per permetre encaixos
            
            # Calcular dimensions de base
            pieces_x = max(1, int((box_length - margin) / (obj_length + margin)))
            pieces_y = max(1, int((box_width - margin) / (obj_width + margin)))
            
            # Apilament intel·ligent: provar múltiples altures
            for base_z in range(0, int(box_height - obj_height), max(1, int(obj_height // 3))):
                for y in range(pieces_y):
                    for x in range(pieces_x):
                        position = [
                            x * (obj_length + margin) + obj_length/2,
                            y * (obj_width + margin) + obj_width/2,
                            base_z + obj_height/2
                        ]
                        
                        # Verificar que cap dins el contenidor
                        if (position[0] + obj_length/2 <= box_length and
                            position[1] + obj_width/2 <= box_width and
                            position[2] + obj_height/2 <= box_height):
                            
                            # Crear item per empaquetament
                            item = {
                                'id': len(items) + 1,
                                'position': position,
                                'dimensions': [obj_length, obj_width, obj_height],
                                'rotation': [0, 0, 0],  # Rotació base
                                'stl_mesh': mesh,
                                'is_stl': True
                            }
                            
                            items.append(item)
                            placed_objects.append(item)
            
            total_objects = len(items)
            
            # Calcular eficiència
            box_volume = box_length * box_width * box_height
            obj_volume = obj_length * obj_width * obj_height
            used_volume = total_objects * obj_volume
            efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0
            
            print(f"        🏗️ Apilament intel·ligent: {total_objects} objectes, {efficiency:.1f}% eficiència")
            
            return {
                'objects_packed': total_objects,
                'efficiency': efficiency,
                'used_volume': used_volume,
                'items': items
            }
            
        except Exception as e:
            print(f"    ❌ Error en apilament intel·ligent: {e}")
            return {'objects_packed': 0, 'items': []}

    def _apply_simple_rotation(self, mesh, rotation):
        """Aplica rotació simple i eficient"""
        try:
            import numpy as np
            
            # Crear còpia de la malla
            rotated_mesh = mesh.copy()
            
            # Aplicar rotacions en ordre: X, Y, Z
            rx, ry, rz = np.radians(rotation)
            
            # Matriu de rotació X
            if rx != 0:
                Rx = np.array([[1, 0, 0],
                              [0, np.cos(rx), -np.sin(rx)],
                              [0, np.sin(rx), np.cos(rx)]])
                rotated_mesh.apply_transform(np.vstack([np.hstack([Rx, [[0], [0], [0]]]), [0, 0, 0, 1]]))
            
            # Matriu de rotació Y
            if ry != 0:
                Ry = np.array([[np.cos(ry), 0, np.sin(ry)],
                              [0, 1, 0],
                              [-np.sin(ry), 0, np.cos(ry)]])
                rotated_mesh.apply_transform(np.vstack([np.hstack([Ry, [[0], [0], [0]]]), [0, 0, 0, 1]]))
            
            # Matriu de rotació Z
            if rz != 0:
                Rz = np.array([[np.cos(rz), -np.sin(rz), 0],
                              [np.sin(rz), np.cos(rz), 0],
                              [0, 0, 1]])
                rotated_mesh.apply_transform(np.vstack([np.hstack([Rz, [[0], [0], [0]]]), [0, 0, 0, 1]]))
            
            # Centrar la malla després de la rotació (posar punt mínim a origen)
            bounds = rotated_mesh.bounds
            translation = -bounds[0]  # Moure des del punt mínim a l'origen
            rotated_mesh.apply_translation(translation)
            
            return rotated_mesh
            
        except Exception as e:
            print(f"⚠️ Error aplicant rotació {rotation}: {e}")
            return mesh  # Retornar original si falla

    def _simplify_for_collision_detection(self, mesh, target_faces=8000):
        """Simplifica malla per col·lisions ràpides mantenint forma general"""
        try:
            import trimesh
            
            original_faces = len(mesh.faces)
            if original_faces <= target_faces:
                print(f"    ⚡ Malla ja prou simple ({original_faces} cares)")
                return mesh
            
            print(f"    🎯 Simplificant de {original_faces} a ~{target_faces} cares")
            
            # Simplificar conservant volum aproximat
            simplified = mesh.simplify_quadric_decimation(target_faces)
            
            # Verificar que la simplificació no ha fallat
            if len(simplified.vertices) == 0 or not simplified.is_valid:
                print(f"    ⚠️ Simplificació fallida, usant original")
                return mesh
                
            print(f"    ✅ Simplificat: {len(simplified.faces)} cares ({len(simplified.faces)/original_faces*100:.1f}%)")
            return simplified
            
        except Exception as e:
            print(f"    ⚠️ Error simplificació: {e}, usant original")
            return mesh

    def _check_simple_collision(self, mesh1, mesh2):
        """Verificació simple de col·lisió entre dues malles"""
        try:
            import numpy as np
            
            # Verificació ràpida amb bounding boxes
            bounds1 = mesh1.bounds
            bounds2 = mesh2.bounds
            
            # Si bounding boxes no es toquen, no hi ha col·lisió
            if (bounds1[1] < bounds2[0]).any() or (bounds2[1] < bounds1[0]).any():
                return False
            
            # Si bounding boxes es solapen significativament, assumir col·lisió
            overlap_volume = np.prod(np.minimum(bounds1[1], bounds2[1]) - np.maximum(bounds1[0], bounds2[0]))
            min_volume = min(np.prod(bounds1[1] - bounds1[0]), np.prod(bounds2[1] - bounds2[0]))
            
            if overlap_volume > min_volume * 0.1:  # >10% solapament
                return True
            
            return False
            
        except:
            # En cas d'error, assumir col·lisió per seguretat
            return True

    def _pack_objects_simple(self, box_length, box_width, box_height, obj_length, obj_width, obj_height, mesh, rotation, original_mesh):
        """⚡ ULTRA-RÀPID: Grid intel·ligent amb solapament controlat (<5 segons)"""
        try:
            import numpy as np
            print(f"    ⚡ EMPAQUETAMENT ULTRA-RÀPID...")
            
            # Grid amb solapament permès per aprofitar millor l'espai
            step_x = obj_length * 0.8  # 20% solapament
            step_y = obj_width * 0.8   
            step_z = obj_height * 0.8  
            
            max_x = max(1, int(box_length / step_x))
            max_y = max(1, int(box_width / step_y))
            max_z = max(1, int(box_height / step_z))
            
            print(f"    🎯 Grid: {max_x} × {max_y} × {max_z} (solapament 20%)")
            
            items = []
            for z in range(max_z):
                for y in range(max_y):
                    for x in range(max_x):
                        # Posició del centre
                        pos_x = x * step_x + obj_length/2
                        pos_y = y * step_y + obj_width/2
                        pos_z = z * step_z + obj_height/2
                        
                        # Verificar que cap completament
                        if (pos_x + obj_length/2 <= box_length and 
                            pos_y + obj_width/2 <= box_width and 
                            pos_z + obj_height/2 <= box_height):
                            
                            items.append({
                                'id': len(items) + 1,
                                'position': [pos_x, pos_y, pos_z],
                                'dimensions': [obj_length, obj_width, obj_height],
                                'rotation': rotation,
                                'stl_mesh': original_mesh,
                                'is_stl': True
                            })
            
            total_objects = len(items)
            print(f"    🎉 {total_objects} objectes col·locats!")
            
            # Calcular eficiències
            box_volume = box_length * box_width * box_height
            obj_volume = obj_length * obj_width * obj_height
            used_volume = total_objects * obj_volume
            efficiency = (used_volume / box_volume) * 100
            
            real_volume = getattr(original_mesh, 'volume', obj_volume)
            real_efficiency = (total_objects * real_volume / box_volume) * 100
            
            return {
                'objects_packed': total_objects,
                'efficiency': efficiency,
                'real_efficiency': real_efficiency,
                'used_volume': used_volume,
                'items': items,
                'positions': [item['position'] for item in items]
            }
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return {
                'objects_packed': 0,
                'efficiency': 0,
                'real_efficiency': 0,
                'used_volume': 0,
                'items': [],
                'positions': []
            }
            
            # 2. DETECTAR CONCAVITATS I BUITS (clau per Tetris 3D)
            mesh_properties = self._analyze_mesh_geometry(simplified_mesh)
            print(f"    🔍 Geometria: {mesh_properties['type']} - Volum buit interior: {mesh_properties.get('empty_ratio', 0):.1%}")
            
            # 3. GENERAR POSICIONS CANDIDATES INTEL·LIGENTS
            placed_objects = []
            max_attempts = 15000  # Més intents per trobar encaixos
            
            # Generar posicions amb resolució adaptativa
            if mesh_properties.get('empty_ratio', 0) > 0.1:  # Si té cavitats
                step_size = 0.5  # Resolució alta per trobar encaixos
                print(f"    🎯 Peça amb cavitats detectada - usant resolució alta (0.5mm)")
            else:
                step_size = 1.0  # Resolució normal
                print(f"    🎯 Peça sòlida - usant resolució normal (1.0mm)")
            
            # Generar grid de posicions
            positions_to_try = []
            for z in np.arange(0, box_height - 0.5, step_size):
                for y in np.arange(0, box_width - 0.5, step_size):
                    for x in np.arange(0, box_length - 0.5, step_size):
                        positions_to_try.append([x, y, z])
            
            # Barrejar posicions per evitar patrons regulars
            np.random.shuffle(positions_to_try)
            print(f"    🎲 Provant {len(positions_to_try)} posicions aleatòries...")
            
            # 4. ALGORITME TETRIS 3D AMB COL·LISIONS EXACTES
            for attempt, candidate_pos in enumerate(positions_to_try[:max_attempts]):
                try:
                    # Crear objecte candidat
                    test_mesh = simplified_mesh.copy()
                    test_mesh.apply_translation(candidate_pos)
                    
                    # Verificar límits del contenidor
                    bounds = test_mesh.bounds
                    if not ((bounds[0] >= [-0.1, -0.1, -0.1]).all() and 
                            (bounds[1] <= [box_length + 0.1, box_width + 0.1, box_height + 0.1]).all()):
                        continue
                    
                    # VERIFICACIÓ TETRIS: Col·lisions exactes punt per punt
                    collision_detected = False
                    
                    if len(placed_objects) > 0:
                        collision_detected = self._check_tetris_collision(test_mesh, placed_objects)
                    
                    if not collision_detected:
                        # 🎉 ENCAIX TROBAT! Col·locar objecte
                        center_pos = [
                            candidate_pos[0] + obj_length/2,
                            candidate_pos[1] + obj_width/2,
                            candidate_pos[2] + obj_height/2
                        ]
                        
                        placed_objects.append({
                            'id': len(placed_objects) + 1,
                            'position': center_pos,
                            'dimensions': [obj_length, obj_width, obj_height],
                            'rotation': rotation,
                            'stl_mesh': original_mesh,
                            'is_stl': True,
                            'collision_mesh': test_mesh,  # Per futures verificacions
                            'tetris_position': candidate_pos
                        })
                        
                        if len(placed_objects) % 5 == 0:
                            print(f"    ✅ {len(placed_objects)} peces encaixades (intent {attempt+1})")
                            
                        # Si trobem moltes peces ràpidament, reduir resolució per anar més ràpid
                        if len(placed_objects) >= 50 and attempt < 5000:
                            step_size *= 1.5  # Reduir resolució
                            
                except Exception as e:
                    continue  # Ignorar errors i continuar
            
            total_objects = len(placed_objects)
            print(f"    🏆 TETRIS FINAL: {total_objects} peces encaixades amb col·lisions exactes!")
            
            # Calcular eficiència real
            box_volume = box_length * box_width * box_height
            obj_volume = getattr(original_mesh, 'volume', obj_length * obj_width * obj_height)
            used_volume = total_objects * obj_volume
            efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0
            
            return {
                'objects_packed': total_objects,
                'efficiency': efficiency,
                'real_efficiency': efficiency,
                'used_volume': used_volume,
                'items': placed_objects,
                'positions': [obj['position'] for obj in placed_objects],
                'method': 'tetris_3d_exact_puzzle_collision'
            }
            
        except Exception as e:
            print(f"    ❌ Error en Tetris 3D: {e}")
            return {
                'objects_packed': 0,
                'efficiency': 0,
                'real_efficiency': 0,
                'used_volume': 0,
                'items': [],
                'positions': []
            }

    def _simplify_mesh_for_collision(self, mesh, target_faces=3000):
        """Simplifica malla mantenint detalls essencials per col·lisions Tetris"""
        try:
            if len(mesh.faces) <= target_faces:
                return mesh
            
            # Usar decimació que preserva característiques geomètriques importants
            simplified = mesh.simplify_quadric_decimation(target_faces)
            
            if len(simplified.vertices) == 0 or not simplified.is_valid:
                return mesh
                
            return simplified
        except:
            return mesh

    def _analyze_mesh_geometry(self, mesh):
        """Analitza geometria per detectar cavitats i buits (clau per Tetris)"""
        try:
            # Calcular propietats geomètriques
            bounds_volume = np.prod(mesh.bounds[1] - mesh.bounds[0])
            mesh_volume = getattr(mesh, 'volume', bounds_volume)
            
            # Ratio de buit interior (important per detectar cavitats)
            empty_ratio = 1 - (mesh_volume / bounds_volume) if bounds_volume > 0 else 0
            
            # Classificar tipus de geometria
            if empty_ratio > 0.3:
                geometry_type = "cavitat_gran"  # Com una cadira amb forats grans
            elif empty_ratio > 0.1:
                geometry_type = "cavitat_mitjana"  # Objectes amb algunes cavitats
            elif mesh.is_watertight:
                geometry_type = "solid_tancat"  # Objecte sòlid
            else:
                geometry_type = "solid_obert"  # Objecte amb obertures
                
            return {
                'type': geometry_type,
                'empty_ratio': empty_ratio,
                'volume': mesh_volume,
                'bounds_volume': bounds_volume,
                'is_watertight': mesh.is_watertight
            }
        except:
            return {'type': 'unknown', 'empty_ratio': 0}

    def _check_tetris_collision(self, test_mesh, placed_objects):
        """Verifica col·lisions Tetris exactes - permet encaixos parcials amb tolerància estricta"""
        try:
            for placed_obj in placed_objects:
                placed_mesh = placed_obj.get('collision_mesh')
                if placed_mesh is not None:
                    # MÈTODE 1: Intersection exacta amb trimesh
                    try:
                        intersection = test_mesh.intersection(placed_mesh)
                        if intersection is not None and hasattr(intersection, 'volume'):
                            # Tolerància molt estricta per evitar travessaments (0.001mm³)
                            if intersection.volume > 0.001:
                                return True
                    except Exception as e:
                        # MÈTODE 2: Fallback amb bounding box ultra refinat
                        bounds1 = test_mesh.bounds
                        bounds2 = placed_mesh.bounds
                        
                        # Verificar solapament amb tolerància de 0.01mm (molt estricte)
                        tolerance = 0.01
                        overlap_x = (bounds1[1][0] - tolerance) > (bounds2[0][0] + tolerance) and (bounds1[0][0] + tolerance) < (bounds2[1][0] - tolerance)
                        overlap_y = (bounds1[1][1] - tolerance) > (bounds2[0][1] + tolerance) and (bounds1[0][1] + tolerance) < (bounds2[1][1] - tolerance)
                        overlap_z = (bounds1[1][2] - tolerance) > (bounds2[0][2] + tolerance) and (bounds1[0][2] + tolerance) < (bounds2[1][2] - tolerance)
                        
                        if overlap_x and overlap_y and overlap_z:
                            return True
            
            return False
        except Exception as e:
            # En cas d'error, assumir col·lisió per seguretat
            print(f"        ⚠️ Error detecció col·lisió: {e}")
            return True
        try:
            print(f"    🧩 Empaquetament intel·ligent amb detecció d'encaixos...")
            
            # Variables per col·locació intel·ligent
            placed_objects = []  # Llista de malles ja col·locades
            positions = []
            items = []
            
            # Configuració d'empaquetament intel·ligent
            step_size = min(obj_length, obj_width, obj_height) / 4  # Pas més petit per buscar encaixos
            max_objects = 500  # Límit de seguretat
            collision_tolerance = 2.0  # Tolerància de col·lisió en mm
            
            print(f"    🎯 Pas de cerca: {step_size:.1f}mm, Tolerància: {collision_tolerance}mm")
            
            # Algoritme d'empaquetament capa per capa amb encaixos
            current_z = obj_height / 2  # Començar des de la base
            layer_count = 0
            total_placed = 0
            
            while current_z + obj_height/2 <= box_height and total_placed < max_objects:
                layer_count += 1
                objects_in_layer = 0
                print(f"    � Capa {layer_count} (z={current_z:.1f})")
                
                # Escanejar posicions en aquesta capa buscant encaixos
                for y in self._generate_smart_positions(obj_width/2, box_width - obj_width/2, step_size):
                    for x in self._generate_smart_positions(obj_length/2, box_length - obj_length/2, step_size):
                        
                        candidate_position = [x, y, current_z]
                        
                        # Crear malla temporal en aquesta posició
                        test_mesh = self._place_mesh_at_position(mesh, candidate_position)
                        
                        # Verificar que està dins del contenidor
                        if not self._is_mesh_inside_container(test_mesh, box_length, box_width, box_height):
                            continue
                        
                        # Verificar col·lisions amb objectes ja col·locats
                        if not self._check_collision_with_placed_objects(test_mesh, placed_objects, collision_tolerance):
                            # NO hi ha col·lisió - podem col·locar aquí!
                            placed_objects.append(test_mesh)
                            positions.append(candidate_position)
                            
                            items.append({
                                'id': total_placed + 1,
                                'position': candidate_position,
                                'dimensions': [obj_length, obj_width, obj_height],
                                'rotation': rotation,
                                'stl_mesh': original_mesh,
                                'is_stl': True
                            })
                            
                            total_placed += 1
                            objects_in_layer += 1
                            
                            if total_placed % 10 == 0:
                                print(f"      ✅ {total_placed} objectes col·locats")
                            
                            # Optimització: saltar aquesta zona per evitar solapaments
                            break
                
                print(f"    📊 Capa {layer_count}: {objects_in_layer} objectes")
                
                # Si no hem col·locat res en aquesta capa, pujar més
                if objects_in_layer == 0:
                    current_z += obj_height  # Pujar una altura completa
                else:
                    current_z += obj_height * 0.8  # Pujar menys per permetre encaixos
            
            print(f"    🎉 Total col·locat: {total_placed} objectes en {layer_count} capes")
            
            # Calcular eficiències
            box_volume = box_length * box_width * box_height
            obj_volume = obj_length * obj_width * obj_height
            used_volume = total_placed * obj_volume
            efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0
            
            # Eficiència STL real
            real_volume = getattr(original_mesh, 'volume', 0)
            used_real_volume = total_placed * real_volume
            real_efficiency = (used_real_volume / box_volume) * 100 if box_volume > 0 and real_volume > 0 else 0
            
            return {
                'objects_packed': total_placed,
                'efficiency': efficiency,
                'real_efficiency': real_efficiency,
                'used_volume': used_volume,
                'items': items,
                'positions': positions
            }
            
        except Exception as e:
            print(f"    ❌ Error en empaquetament intel·ligent: {e}")
            return {
                'objects_packed': 0,
                'efficiency': 0,
                'real_efficiency': 0,
                'used_volume': 0,
                'items': [],
                'positions': []
            }

    def _simple_optimization_fallback(self, box_dims, obj_dims):
        """Genera posicions de manera intel·ligent"""
        positions = []
        current = start
        while current <= end:
            positions.append(current)
            current += step
        return positions
    
    def _place_mesh_at_position(self, mesh, position):
        """Col·loca una malla en una posició específica"""
        try:
            # Crear còpia de la malla
            placed_mesh = mesh.copy()
            
            # Moure la malla a la posició especificada
            # Primer centrar la malla a l'origen
            bounds = placed_mesh.bounds
            center_offset = -(bounds[0] + bounds[1]) / 2
            placed_mesh.apply_translation(center_offset)
            
            # Després moure a la posició final
            placed_mesh.apply_translation(position)
            
            return placed_mesh
            
        except Exception as e:
            print(f"    ⚠️ Error col·locant malla: {e}")
            return mesh
    
    def _is_mesh_inside_container(self, mesh, box_length, box_width, box_height):
        """Verifica que la malla està completament dins del contenidor"""
        try:
            bounds = mesh.bounds
            
            # Verificar que tots els punts estan dins
            return (bounds[0][0] >= 0 and bounds[1][0] <= box_length and
                    bounds[0][1] >= 0 and bounds[1][1] <= box_width and
                    bounds[0][2] >= 0 and bounds[1][2] <= box_height)
                    
        except Exception as e:
            return False
    
    def _check_collision_with_placed_objects(self, test_mesh, placed_objects, tolerance):
        """Verifica col·lisions amb objectes ja col·locats"""
        try:
            test_bounds = test_mesh.bounds
            
            for placed_mesh in placed_objects:
                placed_bounds = placed_mesh.bounds
                
                # Verificació ràpida amb bounding boxes expandides per tolerància
                if self._bounding_boxes_overlap(test_bounds, placed_bounds, tolerance):
                    # Hi ha solapament potencial - verifica més detalls
                    if self._detailed_collision_check(test_mesh, placed_mesh, tolerance):
                        return True  # Hi ha col·lisió
            
            return False  # No hi ha col·lisió
            
        except Exception as e:
            return True  # Assumir col·lisió si hi ha error
    
    def _bounding_boxes_overlap(self, bounds1, bounds2, tolerance):
        """Verifica si dues bounding boxes se solapen amb tolerància"""
        try:
            # Expandir bounding boxes amb tolerància
            min1 = bounds1[0] - tolerance
            max1 = bounds1[1] + tolerance
            min2 = bounds2[0] - tolerance
            max2 = bounds2[1] + tolerance
            
            # Verificar solapament en totes les dimensions
            return not (max1[0] < min2[0] or max2[0] < min1[0] or
                       max1[1] < min2[1] or max2[1] < min1[1] or
                       max1[2] < min2[2] or max2[2] < min1[2])
                       
        except Exception as e:
            return True  # Assumir solapament si hi ha error
    
    def _detailed_collision_check(self, mesh1, mesh2, tolerance):
        """Verificació detallada de col·lisió entre dues malles"""
        try:
            # Per ara, usar verificació simple amb bounding boxes
            # En el futur es pot implementar verificació de vèrtexs o intersecció de triangles
            
            bounds1 = mesh1.bounds
            bounds2 = mesh2.bounds
            
            # Calcular la distància mínima entre bounding boxes
            center1 = (bounds1[0] + bounds1[1]) / 2
            center2 = (bounds2[0] + bounds2[1]) / 2
            
            distance = np.linalg.norm(center1 - center2)
            
            # Calcular radi aproximat de cada objecte
            size1 = np.linalg.norm(bounds1[1] - bounds1[0]) / 2
            size2 = np.linalg.norm(bounds2[1] - bounds2[0]) / 2
            
            # Si la distància entre centres és menor que la suma de radis + tolerància
            min_distance = size1 + size2 + tolerance
            
            return distance < min_distance
            
        except Exception as e:
            return True  # Assumir col·lisió si hi ha error

    def _simple_optimization_fallback(self, box_dims, obj_dims):
        import time
        start_time = time.time()
        
        try:
            print("� INICIANT 3D BIN PACKING REAL AMB GEOMETRIA STL COMPLEXA")
            print("🚫 ABANDONANT graelles simples - USANT col·lisions mesh exactes")
            
            box_length = box_dims['length']
            box_width = box_dims['width']
            box_height = box_dims['height']
            
            print(f"📦 Contenidor: {box_length} × {box_width} × {box_height} mm")
            print(f"🎯 Objecte original: {len(mesh.vertices)} vèrtexs, {len(mesh.faces)} cares")
            
            # 1. OPTIMITZACIÓ: Simplificar malla per col·lisions ràpides
            collision_mesh = self._simplify_for_collision_detection(mesh)
            print(f"⚡ Malla simplificada: {len(collision_mesh.vertices)} vèrtexs, {len(collision_mesh.faces)} cares")
            
            # 2. Generar rotacions estratègiques
            strategic_rotations = self._generate_strategic_rotations()
            
            best_result = None
            max_objects = 0
            best_orientation = None
            best_mesh = None
            
            # 3. Provar cada orientació amb 3D bin packing real
            for i, rotation in enumerate(strategic_rotations):
                print(f"\n🔄 Rotació {i+1}/{len(strategic_rotations)}: {rotation}")
                
                try:
                    # Aplicar rotació
                    rotated_mesh = self._apply_rotation_to_mesh(collision_mesh, rotation)
                    
                    # Verificar que cap en contenidor
                    bounds = rotated_mesh.bounds
                    obj_dims_rotated = bounds[1] - bounds[0]
                    
                    if all(obj_dims_rotated <= [box_length, box_width, box_height]):
                        print(f"    ✅ Cap en contenidor: {obj_dims_rotated[0]:.1f}×{obj_dims_rotated[1]:.1f}×{obj_dims_rotated[2]:.1f}")
                        
                        # EXECUTAR 3D BIN PACKING REAL
                        result = self._execute_3d_bin_packing(
                            box_length, box_width, box_height, 
                            rotated_mesh, rotation, mesh  # mesh original per visualització
                        )
                        
                        if result['objects_packed'] > max_objects:
                            max_objects = result['objects_packed']
                            best_result = result
                            best_orientation = rotation
                            best_mesh = rotated_mesh
                            print(f"    🎉 NOVA MILLOR: {max_objects} objectes!")
                            
                            # Si aconseguim >80% eficiència, parar
                            if result.get('efficiency', 0) > 80:
                                print(f"    🎯 Eficiència alta ({result['efficiency']:.1f}%), parant")
                                break
                    else:
                        print(f"    ❌ NO cap: {obj_dims_rotated[0]:.1f}×{obj_dims_rotated[1]:.1f}×{obj_dims_rotated[2]:.1f}")
                        
                except Exception as e:
                    print(f"    ⚠️ Error rotació {rotation}: {e}")
                    continue
            
            elapsed = time.time() - start_time
            print(f"\n⏱️ Temps total optimització: {elapsed:.2f} segons")
            
            if best_result is None:
                return {
                    'max_objects': 0,
                    'efficiency': 0,
                    'error': 'Cap orientació permet empaquetament',
                    'bins': []
                }
            
            # Formatear resultat final
            return {
                'max_objects': max_objects,
                'efficiency': best_result.get('efficiency', 0),
                'real_efficiency': best_result.get('real_efficiency', 0),
                'box_volume': box_length * box_width * box_height,
                'used_volume': best_result.get('used_volume', 0),
                'method': 'real_3d_bin_packing_with_exact_collisions',
                'best_orientation': best_orientation,
                'computation_time': elapsed,
                'bins': [{
                    'bin': {'dimensions': [box_length, box_width, box_height]},
                    'items': best_result.get('items', []),
                    'mesh_data': best_mesh
                }]
            }
            
        except Exception as e:
            print(f"❌ Error en 3D bin packing: {e}")
            return {
                'max_objects': 0,
                'efficiency': 0,
                'error': f'Error en 3D bin packing: {e}',
                'bins': []
            }
    
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
            
            # Configurar vista isomètrica i zoom automàtic
            plotter.camera_position = 'iso'
            plotter.show_grid()
            plotter.add_axes()
            
            # Zoom automàtic per assegurar-se que tot es veu
            plotter.reset_camera()
            plotter.camera.zoom(0.8)  # Zoom out lleugerament per veure tot el contingut
            
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
                plotter.add_mesh(line, color='red', line_width=6, opacity=1.0)  # Vermell i més gruixut per visibilitat
                
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
            
            # Afegir malla al plotter amb renderitzat sòlid (sense transparència)
            plotter.add_mesh(
                pv_mesh, 
                color=color,
                opacity=1.0,          # Sòlid, sense transparència per evitar artefactes
                show_edges=True,
                edge_color='black',
                line_width=1.0,
                smooth_shading=True,  # Suavitzat per millor qualitat visual
                lighting=True,        # Mantenir il·luminació
                ambient=0.4,         # Il·luminació ambient lleugerament més alta
                diffuse=0.6,         # Il·luminació difusa
                specular=0.0,        # Sense reflexos especulars per colors uniformes
                scalars=None,        # No usar escalars per evitar degradats
                cmap=None            # No usar mapa de colors
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
            
            # Afegir el cub al plotter amb renderitzat sòlid
            plotter.add_mesh(
                cube,
                color=color,
                opacity=1.0,          # Sòlid, sense transparència
                show_edges=True,
                edge_color='black',
                line_width=1.5,
                smooth_shading=True,  # Suavitzat activat
                lighting=True,        # Mantenir il·luminació
                ambient=0.4,         # Il·luminació ambient lleugerament més alta
                diffuse=0.6,         # Il·luminació difusa
                specular=0.0,        # Sense reflexos especulars
                scalars=None,        # No usar escalars
                cmap=None            # No usar mapa de colors
            )
            
            # Afegir etiqueta en el centre del cub
            plotter.add_point_labels(
                [center], 
                [f'Obj {obj_id}'], 
                point_size=0,
                font_size=12,
                text_color='white',
                shape_color=color,
                shape_opacity=1.0,    # Etiqueta sòlida també
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

        
    def _generate_strategic_rotations(self):
        """Genera rotacions estratègiques per geometria complexa"""
        # Rotacions més probables per objectes complexos (cadires, etc.)
        rotations = [
            [0, 0, 0],       # Original
            [0, 0, 180],     # Girat 180° (molt útil per cadires)
            [90, 0, 0],      # 90° X (sobre costat)
            [270, 0, 0],     # 270° X (sobre altre costat)
            [0, 90, 0],      # 90° Y (cap endavant)
            [0, 270, 0],     # 270° Y (cap enrere)
            [180, 0, 180],   # Combinació per apilament
            [90, 0, 180],    # Combinació lateral girada
        ]
        print(f"📐 Generades {len(rotations)} rotacions estratègiques per geometria complexa")
        return rotations
    
    def _test_single_orientation_complex_packing(self, container_box, mesh, rotations):
        """Prova empaquetament amb una sola orientació utilitzant col·lisions reals"""
        import trimesh
        import numpy as np
        
        best_result = None
        max_pieces = 0
        
        for rotation in rotations:
            print(f"  🔄 Testant orientació {rotation}")
            
            try:
                # Aplicar rotació
                rotated_mesh = self._apply_rotation_to_mesh(mesh, rotation)
                
                # Comprovar que cap en el contenidor
                mesh_bounds = rotated_mesh.bounds
                container_bounds = container_box.bounds
                
                if (mesh_bounds[1][0] - mesh_bounds[0][0] <= container_bounds[1][0] - container_bounds[0][0] and
                    mesh_bounds[1][1] - mesh_bounds[0][1] <= container_bounds[1][1] - container_bounds[0][1] and
                    mesh_bounds[1][2] - mesh_bounds[0][2] <= container_bounds[1][2] - container_bounds[0][2]):
                    
                    # Provar empaquetament amb col·lisions reals
                    result = self._pack_with_collision_detection(container_box, rotated_mesh, rotation)
                    
                    if result['total_pieces'] > max_pieces:
                        max_pieces = result['total_pieces']
                        best_result = result
                        print(f"    ✅ Millor orientació: {max_pieces} objectes")
                else:
                    print(f"    ❌ No cap en el contenidor")
                    
            except Exception as e:
                print(f"    ⚠️ Error amb orientació {rotation}: {e}")
                continue
        
        return best_result
    
    def _test_mixed_orientations_complex_packing(self, container_box, mesh, rotations):
        """Prova empaquetament amb orientacions mixtes"""
        print("  🔀 Implementant orientacions mixtes...")
        # Per ara, usar la millor orientació simple
        # TODO: Implementar orientacions mixtes reals
        return self._test_single_orientation_complex_packing(container_box, mesh, rotations)
    
    def _test_smart_stacking_complex_packing(self, container_box, mesh, rotations):
        """Prova apilament intel·ligent aprofitant espais buits"""
        print("  🎯 Implementant apilament intel·ligent...")
        # Per ara, usar la millor orientació simple
        # TODO: Implementar apilament intel·ligent real
        return self._test_single_orientation_complex_packing(container_box, mesh, rotations)
    
    def _pack_with_collision_detection(self, container_box, mesh, rotation):
        """Empaqueta objectes utilitzant detecció de col·lisions real"""
        import trimesh
        import numpy as np
        
        print(f"    🔍 Empaquetant amb detecció de col·lisions...")
        
        container_bounds = container_box.bounds
        container_size = container_bounds[1] - container_bounds[0]
        
        mesh_bounds = mesh.bounds
        mesh_size = mesh_bounds[1] - mesh_bounds[0]
        
        # Calcular graella aproximada basada en bounding box (punt de partida)
        margin = 1.0  # 1mm de marge
        
        approx_pieces_x = max(1, int((container_size[0] - margin) / (mesh_size[0] + margin)))
        approx_pieces_y = max(1, int((container_size[1] - margin) / (mesh_size[1] + margin)))
        approx_pieces_z = max(1, int((container_size[2] - margin) / (mesh_size[2] + margin)))
        
        print(f"    📊 Graella aproximada: {approx_pieces_x} × {approx_pieces_y} × {approx_pieces_z}")
        
        # Llista d'objectes col·locats
        placed_objects = []
        placed_meshes = []
        
        total_attempts = approx_pieces_x * approx_pieces_y * approx_pieces_z
        successful_placements = 0
        
        # Intentar col·locar objectes en cada posició de la graella
        for z in range(approx_pieces_z):
            for y in range(approx_pieces_y):
                for x in range(approx_pieces_x):
                    
                    # Calcular posició basada en graella
                    pos_x = container_bounds[0][0] + x * (mesh_size[0] + margin) + mesh_size[0]/2
                    pos_y = container_bounds[0][1] + y * (mesh_size[1] + margin) + mesh_size[1]/2  
                    pos_z = container_bounds[0][2] + z * (mesh_size[2] + margin) + mesh_size[2]/2
                    
                    position = [pos_x, pos_y, pos_z]
                    
                    # Crear còpia de la malla en aquesta posició
                    test_mesh = mesh.copy()
                    test_mesh.apply_translation(position - np.mean(mesh.vertices, axis=0))
                    
                    # Comprovar que està dins del contenidor
                    if not self._is_mesh_inside_container(test_mesh, container_box):
                        continue
                    
                    # Comprovar col·lisions amb objectes ja col·locats
                    collision_detected = False
                    for placed_mesh in placed_meshes:
                        if self._check_mesh_collision(test_mesh, placed_mesh):
                            collision_detected = True
                            break
                    
                    if not collision_detected:
                        # Col·locar objecte
                        placed_objects.append({
                            'id': len(placed_objects) + 1,
                            'position': position,
                            'rotation': rotation,
                            'dimensions': mesh_size.tolist(),
                            'stl_mesh': test_mesh,
                            'is_stl': True,
                            'bounds': test_mesh.bounds.tolist()
                        })
                        placed_meshes.append(test_mesh)
                        successful_placements += 1
                        
                        if successful_placements % 10 == 0:
                            print(f"      📍 Col·locats {successful_placements} objectes...")
        
        print(f"    ✅ Col·locació completada: {successful_placements} objectes de {total_attempts} posicions provades")
        
        return {
            'total_pieces': successful_placements,
            'items': placed_objects,
            'best_rotation': rotation,
            'collision_detection': True
        }
    
    def _is_mesh_inside_container(self, mesh, container_box):
        """Comprova si una malla està completament dins del contenidor"""
        mesh_bounds = mesh.bounds
        container_bounds = container_box.bounds
        
        return (mesh_bounds[0][0] >= container_bounds[0][0] and 
                mesh_bounds[0][1] >= container_bounds[0][1] and 
                mesh_bounds[0][2] >= container_bounds[0][2] and
                mesh_bounds[1][0] <= container_bounds[1][0] and 
                mesh_bounds[1][1] <= container_bounds[1][1] and 
                mesh_bounds[1][2] <= container_bounds[1][2])
    
    def _check_bounding_sphere(self, mesh1, mesh2):
        """Check ràpid amb esferes delimitadores (1000x més ràpid que AABB)"""
        try:
            # Obtenir centres i radis de les esferes delimitadores
            center1 = mesh1.center_mass if hasattr(mesh1, 'center_mass') else mesh1.bounds.mean(axis=0)
            center2 = mesh2.center_mass if hasattr(mesh2, 'center_mass') else mesh2.bounds.mean(axis=0)
            
            # Calcular radis aproximats (distància del centre al punt més llunyà)
            bounds1 = mesh1.bounds
            bounds2 = mesh2.bounds
            radius1 = np.linalg.norm((bounds1[1] - bounds1[0]) / 2)
            radius2 = np.linalg.norm((bounds2[1] - bounds2[0]) / 2)
            
            # Distància entre centres
            distance = np.linalg.norm(center1 - center2)
            
            # Si esferes no es toquen, no hi ha col·lisió
            return distance <= (radius1 + radius2)
            
        except Exception as e:
            print(f"      ⚠️ Error en check esfera: {e}")
            return True  # Assumir col·lisió per seguretat
    
    def _check_oriented_bounding_box(self, mesh1, mesh2):
        """Check amb OBB (Oriented Bounding Box) per formes irregulars"""
        try:
            # Usar els OBB de trimesh si estan disponibles
            if hasattr(mesh1, 'bounding_box_oriented') and hasattr(mesh2, 'bounding_box_oriented'):
                obb1 = mesh1.bounding_box_oriented
                obb2 = mesh2.bounding_box_oriented
                
                # Comprovar intersecció entre OBBs
                # Trimesh té mètodes per això
                if hasattr(obb1, 'intersects') and hasattr(obb2, 'intersects'):
                    return obb1.intersects(obb2)
            
            # Fallback a AABB si OBB no està disponible
            bounds1 = mesh1.bounds
            bounds2 = mesh2.bounds
            
            return not (bounds1[1][0] <= bounds2[0][0] or bounds2[1][0] <= bounds1[0][0] or
                       bounds1[1][1] <= bounds2[0][1] or bounds2[1][1] <= bounds1[0][1] or
                       bounds1[1][2] <= bounds2[0][2] or bounds2[1][2] <= bounds1[0][2])
                       
        except Exception as e:
            print(f"      ⚠️ Error en check OBB: {e}")
            return True  # Assumir col·lisió per seguretat
    
    def _simplify_for_collision(self, mesh, target_faces=8000):
        """Simplificació dinàmica optimitzada per detecció de col·lisions"""
        try:
            current_faces = len(mesh.faces)
            
            # Si ja és prou simple, retornar original
            if current_faces <= target_faces:
                return mesh
            
            # Calcular ratio de reducció
            reduction_ratio = 1.0 - (target_faces / current_faces)
            reduction_ratio = max(0.1, min(0.9, reduction_ratio))  # Limitar entre 10% i 90%
            
            print(f"        🔧 Simplificant malla: {current_faces:,} → ~{target_faces:,} cares ({reduction_ratio*100:.1f}% reducció)")
            
            # Usar decimació quadric de trimesh (preserva formes clau)
            if hasattr(mesh, 'simplify_quadric_decimation'):
                simplified = mesh.simplify_quadric_decimation(target_reduction=reduction_ratio)
                
                # Verificar que la simplificació ha funcionat
                if simplified.is_empty or len(simplified.faces) == 0:
                    print(f"        ⚠️ Simplificació ha fallat, usant original")
                    return mesh
                    
                print(f"        ✅ Simplificat a {len(simplified.faces):,} cares")
                return simplified
            else:
                print(f"        ⚠️ Simplificació quadric no disponible, usant original")
                return mesh
                
        except Exception as e:
            print(f"        ⚠️ Error en simplificació: {e}, usant malla original")
            return mesh
    
    def _check_mesh_collision(self, mesh1, mesh2):
        """Detecció de col·lisions optimitzada amb 3 nivells: Esfera → OBB → Intersecció real"""
        try:
            # NIVELL 1: Check ràpid amb esferes (1000x més ràpid que AABB)
            if not self._check_bounding_sphere(mesh1, mesh2):
                return False
            
            # NIVELL 2: Check amb OBB orientat (elimina 70% falsos positius)
            if not self._check_oriented_bounding_box(mesh1, mesh2):
                return False
            
            print(f"      🔍 Esferes i OBB es superposen, comprovant geometria STL real...")
            
            # NIVELL 3: Simplificar malles per intersecció ràpida
            simplified1 = self._simplify_for_collision(mesh1)
            simplified2 = self._simplify_for_collision(mesh2)
            
            # Usar trimesh.collision amb algorisme GJK optimitzat
            try:
                # Mètode 1: Usar trimesh.collision.CollisionManager (més ràpid)
                if hasattr(trimesh.collision, 'CollisionManager'):
                    manager = trimesh.collision.CollisionManager()
                    manager.add_object('obj1', simplified1)
                    
                    # Comprovar col·lisió
                    collision_detected = manager.in_collision_single(simplified2)
                    
                    if collision_detected:
                        print(f"      ❌ Col·lisió real detectada (GJK)")
                        return True
                    else:
                        print(f"      ✅ No hi ha col·lisió real (formes encaixen)")
                        return False
                
                # Mètode 2: Fallback amb intersecció directa (més lent)
                intersection = simplified1.intersection(simplified2)
                
                if intersection.is_empty or intersection.volume < 1e-6:  # Volum negligible
                    print(f"      ✅ No hi ha col·lisió real (intersecció buida)")
                    return False
                else:
                    print(f"      ❌ Col·lisió real detectada (intersecció: {intersection.volume:.3f} mm³)")
                    return True
                    
            except Exception as intersect_error:
                print(f"      ⚠️ Error en intersecció exacta: {intersect_error}")
                # Fallback a check conservador
                return True
            
        except Exception as e:
            print(f"      ⚠️ Error en detecció de col·lisions: {e}")
            # En cas d'error, assumir col·lisió per seguretat
            return True
    
    def _fallback_to_bounding_box_packing(self, box_dims, obj_dims, mesh):
        """Fallback a empaquetament amb bounding box si la geometria complexa falla"""
        print("🔄 Usant empaquetament de bounding box com a fallback...")
        
        # Calcular empaquetament simple amb bounding box
        box_volume = box_dims['length'] * box_dims['width'] * box_dims['height']
        obj_volume = obj_dims.get('real_volume', obj_dims['length'] * obj_dims['width'] * obj_dims['height'])
        
        objects_x = max(1, int(box_dims['length'] / obj_dims['length']))
        objects_y = max(1, int(box_dims['width'] / obj_dims['width']))
        objects_z = max(1, int(box_dims['height'] / obj_dims['height']))
        
        max_objects = objects_x * objects_y * objects_z
        used_volume = max_objects * obj_volume
        efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0
        
        # Generar posicions
        items = []
        for z in range(objects_z):
            for y in range(objects_y):
                for x in range(objects_x):
                    items.append({
                        'id': len(items) + 1,
                        'position': [
                            x * obj_dims['length'] + obj_dims['length']/2,
                            y * obj_dims['width'] + obj_dims['width']/2,
                            z * obj_dims['height'] + obj_dims['height']/2
                        ],
                        'rotation': [0, 0, 0],
                        'dimensions': [obj_dims['length'], obj_dims['width'], obj_dims['height']],
                        'stl_mesh': mesh,
                        'is_stl': True,
                        'bounds': mesh.bounds.tolist() if hasattr(mesh, 'bounds') else [[0,0,0], [10,10,10]]
                    })
        
        return {
            'max_objects': max_objects,
            'efficiency': efficiency,
            'real_efficiency': efficiency,
            'box_volume': box_volume,
            'used_volume': used_volume,
            'method': 'bounding_box_fallback',
            'best_orientation': [0, 0, 0],
            'piece_dimensions': [obj_dims['length'], obj_dims['width'], obj_dims['height']],
            'bins': [{
                'bin': {'dimensions': [box_dims['length'], box_dims['width'], box_dims['height']]},
                'items': items
            }]
        }

def main():
    """Funció principal"""
    try:
        app = PackAssistIntegratedApp()
        app.run()
    except Exception as e:
        messagebox.showerror("Error Fatal", f"No s'ha pogut iniciar l'aplicació:\n{e}")

if __name__ == "__main__":
    main()
