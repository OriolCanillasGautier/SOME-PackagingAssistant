#!/usr/bin/env python3
"""
PackAssist - GUI Original amb Arquitectura Modular
Manté la mateixa interfície completa però amb codi organitzat en mòduls
"""

import os
import sys
import time
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

# Imports dels nostres mòduls nous
try:
    from packassist.core import MeshLoader, PackingOptimizer, ResultsExporter
    from packassist.gui import Visualizer3D
    from packassist.utils import save_results_file, generate_timestamp_filename
    print("✅ Mòduls nous carregats correctament")
except ImportError as e:
    print(f"❌ Error carregant mòduls nous: {e}")
    # Fallback a funcions integrades
    MeshLoader = None

# Imports necessaris originals
try:
    import trimesh
except ImportError:
    trimesh = None

try:
    import pyvista as pv
except ImportError:
    pv = None

class PackAssistApp:
    """Aplicació PackAssist amb GUI original i arquitectura modular"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PackAssist - Empaquetament Intel·ligent v2.0 (Modular)")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        
        # Variables principals (mantenim les mateixes que abans)
        self.stl_file_path = None
        self.original_mesh = None
        self.original_mesh_info = None
        self.simplified_mesh = None
        self.simplified_mesh_info = None
        self.optimization_results = None
        
        # Components modulars
        self.mesh_loader = MeshLoader() if MeshLoader else None
        self.visualizer = Visualizer3D() if 'Visualizer3D' in globals() else None
        self.exporter = ResultsExporter() if 'ResultsExporter' in globals() else None
        
        # Setup interfície (mantenim la mateixa)
        self.setup_styles()
        self.create_widgets()
        self.setup_components()
        
    def setup_components(self):
        """Configura els components existents amb millor gestió d'errors"""
        self.components_loaded = False
        self.optimizer_func = None
        self.stl_loader = None
        self.simplifier_methods = {}
        
        print("Configurant components...")
        
        # Comprovar dependències disponibles
        self.available_libs = self.check_dependencies()
        
        # Carregar optimitzador (mantenim el sistema antic com a fallback)
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
        
        return available
    
    def load_optimizer(self):
        """Carrega l'optimitzador (nou o antic)"""
        try:
            # Intentar usar el nou primer
            if PackingOptimizer:
                print("✅ Optimitzador nou carregat")
                return
        except:
            pass
        
        # Fallback a l'optimitzador antic
        try:
            from packassist.optimizer import optimizar_empaquetado
            self.optimizer_func = optimizar_empaquetado
            print("✅ Optimitzador antic carregat com a fallback")
        except ImportError:
            print("❌ No s'ha pogut carregar cap optimitzador")
    
    def load_simplifiers(self):
        """Carrega els simplificadors disponibles"""
        # Intentar carregar diferents mètodes de simplificació
        simplifier_paths = [
            'fast_mesh_simplifier_fixed',
            'adaptive_mesh_simplifier', 
            'super_fast_simplifier'
        ]
        
        for simplifier_name in simplifier_paths:
            try:
                module = __import__(simplifier_name)
                if hasattr(module, 'simplify_mesh'):
                    self.simplifier_methods[simplifier_name] = module.simplify_mesh
                    print(f"✅ Simplificador {simplifier_name} carregat")
            except ImportError:
                print(f"❌ Simplificador {simplifier_name} no disponible")
    
    def load_stl_loader(self):
        """Carrega el STL loader (nou o antic)"""
        try:
            # Usar el nou primer
            if self.mesh_loader:
                print("✅ STL Loader nou disponible")
                return
        except:
            pass
        
        # Fallback a l'antic
        try:
            from packassist.stl_loader import STLLoader
            self.stl_loader = STLLoader()
            print("✅ STL Loader antic carregat com a fallback")
        except ImportError:
            print("❌ No s'ha pogut carregar cap STL loader")
    
    def setup_styles(self):
        """Configura els estils de la interfície (mantenim els mateixos)"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configurar colors personalitzats
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), foreground='#2E86AB')
        style.configure('Subtitle.TLabel', font=('Arial', 10, 'bold'), foreground='#A23B72')
        style.configure('Success.TLabel', foreground='#06A77D')
        style.configure('Warning.TLabel', foreground='#F18F01')
        style.configure('Error.TLabel', foreground='#C73E1D')
    
    def create_widgets(self):
        """Crea tots els widgets de la interfície (mantenim la mateixa estructura)"""
        # Crear notebook principal
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pestanya 1: Càrrega i Simplificació
        self.tab1 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1, text="🗂️ Fitxer STL")
        self.create_file_tab()
        
        # Pestanya 2: Configuració Contenidor
        self.tab2 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2, text="📦 Contenidor")
        self.create_container_tab()
        
        # Pestanya 3: Optimització  
        self.tab3 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab3, text="🎯 Optimització")
        self.create_optimization_tab()
        
        # Pestanya 4: Resultats i Visualització
        self.tab4 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab4, text="📊 Resultats")
        self.create_results_tab()
        
        # Pestanya 5: Exportació
        self.tab5 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab5, text="📤 Exportació")
        self.create_export_tab()
    
    def create_file_tab(self):
        """Crea la pestanya de càrrega de fitxers (mantenim la mateixa)"""
        # Frame principal amb scroll
        canvas = tk.Canvas(self.tab1)
        scrollbar = ttk.Scrollbar(self.tab1, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Títol
        title_label = ttk.Label(scrollable_frame, text="📁 Càrrega i Processament de Fitxer STL", 
                               style='Title.TLabel')
        title_label.pack(pady=(10, 20))
        
        # Secció 1: Selecció de fitxer
        file_frame = ttk.LabelFrame(scrollable_frame, text="Selecció de Fitxer", padding="15")
        file_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        # Frame per botó i etiqueta
        file_controls = ttk.Frame(file_frame)
        file_controls.pack(fill=tk.X)
        
        self.load_button = ttk.Button(file_controls, text="🗂️ Carregar STL/STP", 
                                     command=self.load_stl_file, width=20)
        self.load_button.pack(side=tk.LEFT)
        
        self.file_status_label = ttk.Label(file_controls, text="Cap fitxer seleccionat", 
                                          foreground="gray")
        self.file_status_label.pack(side=tk.LEFT, padx=(15, 0))
        
        # Secció 2: Informació del fitxer
        info_frame = ttk.LabelFrame(scrollable_frame, text="Informació del Fitxer", padding="15")
        info_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        self.file_info_text = tk.Text(info_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        info_scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self.file_info_text.yview)
        self.file_info_text.configure(yscrollcommand=info_scrollbar.set)
        
        self.file_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Secció 3: Simplificació (mantenim les mateixes opcions)
        simplify_frame = ttk.LabelFrame(scrollable_frame, text="Simplificació de Malla", padding="15")
        simplify_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        # Controls de simplificació
        simplify_controls = ttk.Frame(simplify_frame)
        simplify_controls.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(simplify_controls, text="Percentatge de cares a mantenir:").pack(side=tk.LEFT)
        
        self.simplification_var = tk.DoubleVar(value=50.0)
        simplify_scale = ttk.Scale(simplify_controls, from_=10, to=100, 
                                  variable=self.simplification_var, orient=tk.HORIZONTAL)
        simplify_scale.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        
        self.simplify_percentage_label = ttk.Label(simplify_controls, text="50%")
        self.simplify_percentage_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Callback per actualitzar percentatge
        def update_percentage(*args):
            self.simplify_percentage_label.config(text=f"{self.simplification_var.get():.0f}%")
        
        self.simplification_var.trace('w', update_percentage)
        
        # Mètode de simplificació
        method_frame = ttk.Frame(simplify_frame)
        method_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(method_frame, text="Mètode:").pack(side=tk.LEFT)
        
        self.simplify_method_var = tk.StringVar(value="automatic")
        methods = ["automatic", "pymeshlab", "fast", "adaptive"]
        method_combo = ttk.Combobox(method_frame, textvariable=self.simplify_method_var, 
                                   values=methods, state="readonly", width=15)
        method_combo.pack(side=tk.LEFT, padx=(10, 0))
        
        # Botó de simplificació
        simplify_button_frame = ttk.Frame(simplify_frame)
        simplify_button_frame.pack(fill=tk.X)
        
        self.simplify_button = ttk.Button(simplify_button_frame, text="🔧 Simplificar Malla",
                                         command=self.simplify_mesh, state=tk.DISABLED)
        self.simplify_button.pack(side=tk.LEFT)
        
        self.auto_simplify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(simplify_button_frame, text="Simplificació automàtica en carregar",
                       variable=self.auto_simplify_var).pack(side=tk.LEFT, padx=(20, 0))
        
        # Secció 4: Informació de la malla simplificada
        simplified_info_frame = ttk.LabelFrame(scrollable_frame, text="Malla Simplificada", padding="15")
        simplified_info_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        self.simplified_info_text = tk.Text(simplified_info_frame, height=6, wrap=tk.WORD, state=tk.DISABLED)
        simplified_scrollbar = ttk.Scrollbar(simplified_info_frame, orient=tk.VERTICAL, 
                                           command=self.simplified_info_text.yview)
        self.simplified_info_text.configure(yscrollcommand=simplified_scrollbar.set)
        
        self.simplified_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        simplified_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_container_tab(self):
        """Crea la pestanya de configuració del contenidor (mantenim la mateixa)"""
        # Frame principal
        main_frame = ttk.Frame(self.tab2)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Títol
        title_label = ttk.Label(main_frame, text="📦 Configuració del Contenidor", 
                               style='Title.TLabel')
        title_label.pack(pady=(0, 30))
        
        # Secció de dimensions
        dimensions_frame = ttk.LabelFrame(main_frame, text="Dimensions del Contenidor (mm)", 
                                        padding="20")
        dimensions_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Grid per les dimensions
        dimensions_grid = ttk.Frame(dimensions_frame)
        dimensions_grid.pack()
        
        # Variables per les dimensions
        self.container_length = tk.DoubleVar(value=200.0)
        self.container_width = tk.DoubleVar(value=200.0)  
        self.container_height = tk.DoubleVar(value=200.0)
        
        # Longitud
        ttk.Label(dimensions_grid, text="Longitud (X):").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        length_entry = ttk.Entry(dimensions_grid, textvariable=self.container_length, width=15)
        length_entry.grid(row=0, column=1, padx=(0, 20))
        ttk.Label(dimensions_grid, text="mm").grid(row=0, column=2, sticky=tk.W)
        
        # Amplada
        ttk.Label(dimensions_grid, text="Amplada (Y):").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(10, 0))
        width_entry = ttk.Entry(dimensions_grid, textvariable=self.container_width, width=15)
        width_entry.grid(row=1, column=1, padx=(0, 20), pady=(10, 0))
        ttk.Label(dimensions_grid, text="mm").grid(row=1, column=2, sticky=tk.W, pady=(10, 0))
        
        # Altura
        ttk.Label(dimensions_grid, text="Altura (Z):").grid(row=2, column=0, sticky=tk.W, padx=(0, 5), pady=(10, 0))
        height_entry = ttk.Entry(dimensions_grid, textvariable=self.container_height, width=15)
        height_entry.grid(row=2, column=1, padx=(0, 20), pady=(10, 0))
        ttk.Label(dimensions_grid, text="mm").grid(row=2, column=2, sticky=tk.W, pady=(10, 0))
        
        # Informació calculada
        info_frame = ttk.LabelFrame(main_frame, text="Informació Calculada", padding="20")
        info_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.container_info_label = ttk.Label(info_frame, text="", justify=tk.LEFT)
        self.container_info_label.pack(anchor=tk.W)
        
        # Actualitzar informació quan canviïn les dimensions
        def update_container_info(*args):
            length = self.container_length.get()
            width = self.container_width.get()
            height = self.container_height.get()
            volume = length * width * height
            
            info_text = f"Volum del contenidor: {volume:,.0f} mm³ ({volume/1000000:.3f} litres)\n"
            info_text += f"Àrea de la base: {length * width:,.0f} mm² ({(length * width)/100:.1f} cm²)\n"
            info_text += f"Perímetre de la base: {2*(length + width):.1f} mm"
            
            self.container_info_label.config(text=info_text)
        
        self.container_length.trace('w', update_container_info)
        self.container_width.trace('w', update_container_info)
        self.container_height.trace('w', update_container_info)
        
        # Cridar una vegada per inicialitzar
        update_container_info()
        
        # Presets de contenidors
        presets_frame = ttk.LabelFrame(main_frame, text="Contenidors Predefinits", padding="20")
        presets_frame.pack(fill=tk.X)
        
        presets_grid = ttk.Frame(presets_frame)
        presets_grid.pack()
        
        # Definir presets
        presets = [
            ("Caixa Petita", 150, 150, 100),
            ("Caixa Mitjana", 300, 200, 150),
            ("Caixa Gran", 500, 300, 200),
            ("Palet Europeu", 1200, 800, 200),
            ("Contenidor 20'", 6058, 2438, 2591)
        ]
        
        for i, (name, l, w, h) in enumerate(presets):
            row = i // 3
            col = i % 3
            
            def make_preset_command(length, width, height):
                return lambda: self.set_container_preset(length, width, height)
            
            preset_button = ttk.Button(presets_grid, text=name, 
                                     command=make_preset_command(l, w, h))
            preset_button.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W+tk.E)
        
        # Configurar grid
        for i in range(3):
            presets_grid.columnconfigure(i, weight=1)
    
    def create_optimization_tab(self):
        """Crea la pestanya d'optimització (mantenim la mateixa però amb opcions per mòduls nous)"""
        # Frame principal amb scroll
        canvas = tk.Canvas(self.tab3)
        scrollbar = ttk.Scrollbar(self.tab3, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Títol
        title_label = ttk.Label(scrollable_frame, text="🎯 Configuració d'Optimització", 
                               style='Title.TLabel')
        title_label.pack(pady=(10, 20))
        
        # Secció 1: Paràmetres bàsics
        basic_frame = ttk.LabelFrame(scrollable_frame, text="Paràmetres Bàsics", padding="15")
        basic_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        # Nombre de peces objectiu
        pieces_frame = ttk.Frame(basic_frame)
        pieces_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(pieces_frame, text="Nombre de peces objectiu:").pack(side=tk.LEFT)
        
        self.target_pieces = tk.IntVar(value=50)
        pieces_spinbox = ttk.Spinbox(pieces_frame, from_=1, to=1000, 
                                   textvariable=self.target_pieces, width=10)
        pieces_spinbox.pack(side=tk.LEFT, padx=(10, 0))
        
        # Algorisme d'optimització (AFEGIM OPCIONS NOVES)
        algorithm_frame = ttk.Frame(basic_frame)
        algorithm_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(algorithm_frame, text="Algorisme:").pack(side=tk.LEFT)
        
        self.optimization_algorithm = tk.StringVar(value="intelligent")
        # Afegim els nous algorismes als originals
        algorithms = ["intelligent", "grid", "random", "genetic", "simulated_annealing", "hybrid"]
        algorithm_combo = ttk.Combobox(algorithm_frame, textvariable=self.optimization_algorithm,
                                     values=algorithms, state="readonly", width=20)
        algorithm_combo.pack(side=tk.LEFT, padx=(10, 0))
        
        # Temps màxim d'execució
        time_frame = ttk.Frame(basic_frame)
        time_frame.pack(fill=tk.X)
        
        ttk.Label(time_frame, text="Temps màxim (segons):").pack(side=tk.LEFT)
        
        self.max_time = tk.IntVar(value=60)
        time_spinbox = ttk.Spinbox(time_frame, from_=10, to=600, 
                                 textvariable=self.max_time, width=10)
        time_spinbox.pack(side=tk.LEFT, padx=(10, 0))
        
        # Secció 2: Paràmetres avançats (mantenim els originals)
        advanced_frame = ttk.LabelFrame(scrollable_frame, text="Paràmetres Avançats", padding="15")
        advanced_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        # Variables avançades
        self.enable_rotation = tk.BooleanVar(value=True)
        self.collision_precision = tk.DoubleVar(value=1.0)
        self.optimization_precision = tk.DoubleVar(value=1.0)
        
        ttk.Checkbutton(advanced_frame, text="Permetre rotacions de peces",
                       variable=self.enable_rotation).pack(anchor=tk.W, pady=(0, 5))
        
        # Precisió de col·lisions
        collision_frame = ttk.Frame(advanced_frame)
        collision_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(collision_frame, text="Precisió col·lisions:").pack(side=tk.LEFT)
        collision_scale = ttk.Scale(collision_frame, from_=0.1, to=5.0,
                                  variable=self.collision_precision, orient=tk.HORIZONTAL)
        collision_scale.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        
        self.collision_label = ttk.Label(collision_frame, text="1.0")
        self.collision_label.pack(side=tk.LEFT)
        
        def update_collision_label(*args):
            self.collision_label.config(text=f"{self.collision_precision.get():.1f}")
        
        self.collision_precision.trace('w', update_collision_label)
        
        # Precisió d'optimització
        opt_precision_frame = ttk.Frame(advanced_frame)
        opt_precision_frame.pack(fill=tk.X)
        
        ttk.Label(opt_precision_frame, text="Precisió optimització:").pack(side=tk.LEFT)
        opt_scale = ttk.Scale(opt_precision_frame, from_=0.1, to=5.0,
                            variable=self.optimization_precision, orient=tk.HORIZONTAL)
        opt_scale.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        
        self.opt_precision_label = ttk.Label(opt_precision_frame, text="1.0")
        self.opt_precision_label.pack(side=tk.LEFT)
        
        def update_opt_precision_label(*args):
            self.opt_precision_label.config(text=f"{self.optimization_precision.get():.1f}")
        
        self.optimization_precision.trace('w', update_opt_precision_label)
        
        # Secció 3: Execució
        execution_frame = ttk.LabelFrame(scrollable_frame, text="Execució", padding="15")
        execution_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # Botó d'optimització principal
        self.optimize_button = ttk.Button(execution_frame, text="🚀 Iniciar Optimització",
                                        command=self.run_optimization, state=tk.DISABLED)
        self.optimize_button.pack(pady=(0, 10))
        
        # Opcions d'execució
        options_frame = ttk.Frame(execution_frame)
        options_frame.pack(fill=tk.X)
        
        self.show_progress = tk.BooleanVar(value=True)
        self.auto_visualize = tk.BooleanVar(value=False)
        
        ttk.Checkbutton(options_frame, text="Mostrar progrés en temps real",
                       variable=self.show_progress).pack(anchor=tk.W)
        ttk.Checkbutton(options_frame, text="Visualitzar automàticament al completar",
                       variable=self.auto_visualize).pack(anchor=tk.W)
        
        # Barra de progrés
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(execution_frame, variable=self.progress_var,
                                          maximum=100, length=400)
        self.progress_bar.pack(pady=(10, 5), fill=tk.X)
        
        self.progress_label = ttk.Label(execution_frame, text="Llest per optimitzar")
        self.progress_label.pack()
    
    def create_results_tab(self):
        """Crea la pestanya de resultats (mantenim la mateixa)"""
        # Frame principal
        main_frame = ttk.Frame(self.tab4)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Títol
        title_label = ttk.Label(main_frame, text="📊 Resultats i Visualització", 
                               style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Frame per botons d'acció
        actions_frame = ttk.Frame(main_frame)
        actions_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Botons de visualització
        self.visualize_button = ttk.Button(actions_frame, text="🎮 Visualitzar 3D",
                                         command=self.visualize_3d, state=tk.DISABLED)
        self.visualize_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.visualize_options_button = ttk.Button(actions_frame, text="⚙️ Opcions de Visualització",
                                                 command=self.visualize_3d_with_options, state=tk.DISABLED)
        self.visualize_options_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Separador
        ttk.Separator(actions_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Botons d'exportació  
        self.export_button = ttk.Button(actions_frame, text="📤 Exportar",
                                       command=self.export_results, state=tk.DISABLED)
        self.export_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Àrea de resultats
        results_frame = ttk.LabelFrame(main_frame, text="Resum de Resultats", padding="15")
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        # Text per mostrar resultats
        self.results_text = tk.Text(results_frame, wrap=tk.WORD, state=tk.DISABLED)
        results_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, 
                                        command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=results_scrollbar.set)
        
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_export_tab(self):
        """Crea la pestanya d'exportació (mantenim la mateixa)"""
        # Frame principal
        main_frame = ttk.Frame(self.tab5)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Títol
        title_label = ttk.Label(main_frame, text="📤 Exportació de Resultats", 
                               style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Opcions d'exportació
        options_frame = ttk.LabelFrame(main_frame, text="Formats d'Exportació", padding="15")
        options_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Variables per opcions
        self.export_text = tk.BooleanVar(value=True)
        self.export_csv = tk.BooleanVar(value=False)
        self.export_json = tk.BooleanVar(value=False)
        self.export_stl = tk.BooleanVar(value=False)
        self.export_image = tk.BooleanVar(value=False)
        
        # Checkboxes
        ttk.Checkbutton(options_frame, text="📄 Informe de text (.txt)",
                       variable=self.export_text).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="📊 Dades CSV (.csv)",
                       variable=self.export_csv).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="🔧 Dades JSON (.json)",
                       variable=self.export_json).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="🎯 STL amb peces posicionades (.stl)",
                       variable=self.export_stl).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="📸 Imatge de la visualització (.png)",
                       variable=self.export_image).pack(anchor=tk.W, pady=2)
        
        # Directori d'exportació
        dir_frame = ttk.LabelFrame(main_frame, text="Directori d'Exportació", padding="15")
        dir_frame.pack(fill=tk.X, pady=(0, 20))
        
        dir_controls = ttk.Frame(dir_frame)
        dir_controls.pack(fill=tk.X)
        
        self.export_dir_var = tk.StringVar(value="actiu/results")
        
        ttk.Label(dir_controls, text="Directori:").pack(side=tk.LEFT)
        ttk.Entry(dir_controls, textvariable=self.export_dir_var, width=40).pack(side=tk.LEFT, 
                                                                                padx=(10, 5), fill=tk.X, expand=True)
        ttk.Button(dir_controls, text="📁 Navegar", 
                  command=self.select_export_directory).pack(side=tk.RIGHT)
        
        # Botó d'exportació
        export_action_frame = ttk.Frame(main_frame)
        export_action_frame.pack(fill=tk.X)
        
        self.export_all_button = ttk.Button(export_action_frame, text="📤 Exportar Seleccionats",
                                          command=self.perform_export, state=tk.DISABLED)
        self.export_all_button.pack()

    # Ara afegim tots els mètodes originals però adaptats per usar els mòduls nous
    
    def load_stl_file(self):
        """Carrega un fitxer STL (adaptat per usar MeshLoader nou)"""
        filetypes = [
            ("Fitxers STL", "*.stl"),
            ("Fitxers STP", "*.stp"),
            ("Fitxers STEP", "*.step"),
            ("Tots els fitxers suportats", "*.stl *.stp *.step"),
            ("Tots els fitxers", "*.*")
        ]
        
        filepath = filedialog.askopenfilename(
            title="Selecciona un fitxer 3D",
            filetypes=filetypes
        )
        
        if not filepath:
            return
        
        try:
            # Usar el MeshLoader nou si està disponible
            if self.mesh_loader:
                self.original_mesh = self.mesh_loader.load_mesh(filepath)
                self.original_mesh_info = self.mesh_loader.get_mesh_info(self.original_mesh)
            else:
                # Fallback a trimesh directament
                self.original_mesh = trimesh.load(filepath)
                self.original_mesh_info = self._get_mesh_info_fallback(self.original_mesh)
            
            self.stl_file_path = filepath
            
            # Actualitzar interfície
            filename = os.path.basename(filepath)
            self.file_status_label.config(text=f"✅ {filename}", style='Success.TLabel')
            
            # Mostrar informació
            self._display_file_info()
            
            # Simplificació automàtica si està habilitada
            if self.auto_simplify_var.get():
                self.simplify_mesh()
            
            # Habilitar botons
            self.simplify_button.config(state=tk.NORMAL)
            self.optimize_button.config(state=tk.NORMAL)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error carregant el fitxer:\n{e}")
            self.file_status_label.config(text="❌ Error carregant fitxer", style='Error.TLabel')
    
    def _get_mesh_info_fallback(self, mesh):
        """Fallback per obtenir informació de la malla si no tenim MeshLoader"""
        bounds = mesh.bounds
        dimensions = bounds[1] - bounds[0]
        
        return {
            'vertices_count': len(mesh.vertices),
            'faces_count': len(mesh.faces),
            'volume': float(mesh.volume) if hasattr(mesh, 'volume') else 0.0,
            'surface_area': float(mesh.area) if hasattr(mesh, 'area') else 0.0,
            'bounds': bounds.tolist(),
            'dimensions': dimensions.tolist(),
            'center': mesh.center_mass.tolist() if hasattr(mesh, 'center_mass') else [0, 0, 0],
            'is_watertight': mesh.is_watertight if hasattr(mesh, 'is_watertight') else False,
            'is_volume': mesh.is_volume if hasattr(mesh, 'is_volume') else False
        }
    
    def _display_file_info(self):
        """Mostra la informació del fitxer carregat"""
        if not self.original_mesh_info:
            return
        
        info_text = f"📁 Fitxer: {os.path.basename(self.stl_file_path)}\n\n"
        info_text += f"📊 Estadístiques de la malla:\n"
        info_text += f"   • Vèrtexs: {self.original_mesh_info['vertices_count']:,}\n"
        info_text += f"   • Cares: {self.original_mesh_info['faces_count']:,}\n"
        info_text += f"   • Volum: {self.original_mesh_info['volume']:.2f} mm³\n"
        info_text += f"   • Àrea superfície: {self.original_mesh_info['surface_area']:.2f} mm²\n\n"
        
        dimensions = self.original_mesh_info['dimensions']
        info_text += f"📏 Dimensions:\n"
        info_text += f"   • Longitud (X): {dimensions[0]:.2f} mm\n"
        info_text += f"   • Amplada (Y): {dimensions[1]:.2f} mm\n"
        info_text += f"   • Altura (Z): {dimensions[2]:.2f} mm\n\n"
        
        info_text += f"🔍 Propietats:\n"
        info_text += f"   • Estanc: {'Sí' if self.original_mesh_info['is_watertight'] else 'No'}\n"
        info_text += f"   • Volum vàlid: {'Sí' if self.original_mesh_info['is_volume'] else 'No'}\n"
        
        self.file_info_text.config(state=tk.NORMAL)
        self.file_info_text.delete(1.0, tk.END)
        self.file_info_text.insert(1.0, info_text)
        self.file_info_text.config(state=tk.DISABLED)
    
    def simplify_mesh(self):
        """Simplifica la malla (adaptat per usar MeshLoader nou)"""
        if not self.original_mesh:
            messagebox.showwarning("Avís", "Primer carrega un fitxer STL")
            return
        
        try:
            target_percentage = self.simplification_var.get() / 100.0
            target_faces = int(self.original_mesh_info['faces_count'] * target_percentage)
            
            # Usar MeshLoader nou si està disponible
            if self.mesh_loader:
                self.simplified_mesh = self.mesh_loader.simplify_mesh(self.original_mesh, target_faces)
                self.simplified_mesh_info = self.mesh_loader.get_mesh_info(self.simplified_mesh)
            else:
                # Fallback a simplificació bàsica
                try:
                    self.simplified_mesh = self.original_mesh.simplify_quadric_decimation(target_faces)
                    self.simplified_mesh_info = self._get_mesh_info_fallback(self.simplified_mesh)
                except:
                    # Si falla, usar l'original
                    self.simplified_mesh = self.original_mesh.copy()
                    self.simplified_mesh_info = self.original_mesh_info.copy()
            
            # Mostrar informació de la malla simplificada
            self._display_simplified_info()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error simplificant la malla:\n{e}")
    
    def _display_simplified_info(self):
        """Mostra la informació de la malla simplificada"""
        if not self.simplified_mesh_info:
            return
        
        original_faces = self.original_mesh_info['faces_count']
        simplified_faces = self.simplified_mesh_info['faces_count']
        reduction_percentage = ((original_faces - simplified_faces) / original_faces) * 100
        
        info_text = f"🔧 Malla simplificada creada\n\n"
        info_text += f"📊 Reducció de complexitat:\n"
        info_text += f"   • Cares originals: {original_faces:,}\n"
        info_text += f"   • Cares simplificades: {simplified_faces:,}\n"
        info_text += f"   • Reducció: {reduction_percentage:.1f}%\n\n"
        
        info_text += f"📏 Dimensions mantingudes:\n"
        dimensions = self.simplified_mesh_info['dimensions']
        info_text += f"   • Longitud: {dimensions[0]:.2f} mm\n"
        info_text += f"   • Amplada: {dimensions[1]:.2f} mm\n"
        info_text += f"   • Altura: {dimensions[2]:.2f} mm\n"
        
        self.simplified_info_text.config(state=tk.NORMAL)
        self.simplified_info_text.delete(1.0, tk.END)
        self.simplified_info_text.insert(1.0, info_text)
        self.simplified_info_text.config(state=tk.DISABLED)
    
    def set_container_preset(self, length, width, height):
        """Estableix un preset de contenidor"""
        self.container_length.set(length)
        self.container_width.set(width)
        self.container_height.set(height)
    
    def run_optimization(self):
        """Executa l'optimització (adaptat per usar PackingOptimizer nou)"""
        if not self.original_mesh:
            messagebox.showwarning("Avís", "Primer carrega un fitxer STL")
            return
        
        # Usar la malla simplificada si està disponible, sinó l'original
        mesh_to_use = self.simplified_mesh if self.simplified_mesh else self.original_mesh
        
        try:
            # Crear optimitzador nou si està disponible
            if PackingOptimizer:
                container_dims = (
                    self.container_length.get(),
                    self.container_width.get(),
                    self.container_height.get()
                )
                
                optimizer = PackingOptimizer(container_dims)
                
                # Executar optimització
                self.optimization_results = optimizer.optimize(
                    mesh_to_use,
                    self.target_pieces.get(),
                    self.optimization_algorithm.get()
                )
                
                if self.optimization_results['success']:
                    self._display_optimization_results()
                    self._enable_result_buttons()
                    
                    # Guardar resultats automàticament
                    self._save_optimization_results()
                    
                    # Visualització automàtica si està habilitada
                    if self.auto_visualize.get():
                        self.visualize_3d()
                else:
                    messagebox.showerror("Error", f"Error en l'optimització:\n{self.optimization_results.get('error', 'Error desconegut')}")
            
            else:
                # Fallback a l'optimitzador antic
                messagebox.showinfo("Informació", "Usant optimitzador llegat. Funcionalitat limitada.")
                # Aquí podríem cridar l'optimitzador antic si cal
        
        except Exception as e:
            messagebox.showerror("Error", f"Error durant l'optimització:\n{e}")
    
    def _display_optimization_results(self):
        """Mostra els resultats de l'optimització"""
        if not self.optimization_results:
            return
        
        results_text = f"🎯 OPTIMITZACIÓ COMPLETADA\n"
        results_text += f"{'='*50}\n\n"
        
        results_text += f"📊 Resultats principals:\n"
        results_text += f"   • Peces col·locades: {self.optimization_results['pieces_count']}\n"
        results_text += f"   • Eficiència: {self.optimization_results['efficiency']:.2f}%\n"
        results_text += f"   • Mètode utilitzat: {self.optimization_results['method']}\n"
        results_text += f"   • Temps d'execució: {self.optimization_results.get('execution_time', 0):.2f} segons\n\n"
        
        box_dims = self.optimization_results.get('box_dims', {})
        results_text += f"📦 Contenidor:\n"
        results_text += f"   • Dimensions: {box_dims.get('length', 0):.1f} x {box_dims.get('width', 0):.1f} x {box_dims.get('height', 0):.1f} mm\n"
        results_text += f"   • Volum total: {box_dims.get('volume', 0):.1f} mm³\n\n"
        
        obj_dims = self.optimization_results.get('obj_dims', {})
        results_text += f"🔧 Objecte:\n"
        results_text += f"   • Dimensions unitàries: {obj_dims.get('length', 0):.1f} x {obj_dims.get('width', 0):.1f} x {obj_dims.get('height', 0):.1f} mm\n"
        results_text += f"   • Volum unitari: {obj_dims.get('volume', 0):.1f} mm³\n\n"
        
        results_text += f"✅ Optimització finalitzada amb èxit!\n"
        results_text += f"Utilitza els botons de visualització i exportació per veure i guardar els resultats.\n"
        
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(1.0, results_text)
        self.results_text.config(state=tk.DISABLED)
    
    def _enable_result_buttons(self):
        """Habilita els botons de resultats"""
        self.visualize_button.config(state=tk.NORMAL)
        self.visualize_options_button.config(state=tk.NORMAL)
        self.export_button.config(state=tk.NORMAL)
        self.export_all_button.config(state=tk.NORMAL)
    
    def _save_optimization_results(self):
        """Guarda els resultats automàticament"""
        try:
            if save_results_file and generate_timestamp_filename:
                # Usar les funcions noves
                filename = generate_timestamp_filename("packassist_results", "txt")
                
                content = f"PackAssist - Resultats d'Optimització\n"
                content += f"Fitxer: {os.path.basename(self.stl_file_path) if self.stl_file_path else 'Desconegut'}\n"
                content += f"Mètode: {self.optimization_results['method']}\n"
                content += f"Peces: {self.optimization_results['pieces_count']}\n"
                content += f"Eficiència: {self.optimization_results['efficiency']:.2f}%\n\n"
                
                # Afegir posicions
                positions = self.optimization_results.get('positions', [])
                rotations = self.optimization_results.get('rotations', [])
                
                for i, (pos, rot) in enumerate(zip(positions, rotations)):
                    content += f"Peça {i+1}: Pos({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}) "
                    content += f"Rot({rot[0]:.0f}°, {rot[1]:.0f}°, {rot[2]:.0f}°)\n"
                
                save_results_file(content, filename)
                print(f"💾 Resultats guardats: {filename}")
            
        except Exception as e:
            print(f"Error guardant resultats: {e}")
    
    def visualize_3d(self):
        """Visualització 3D directa (adaptat per usar Visualizer3D nou)"""
        if not self.optimization_results:
            messagebox.showwarning("Avís", "Primer executa l'optimització")
            return
        
        try:
            mesh_to_use = self.simplified_mesh if self.simplified_mesh else self.original_mesh
            
            # Usar Visualizer3D nou si està disponible
            if self.visualizer:
                self.visualizer.show_direct_3d(self.optimization_results, mesh_to_use)
            else:
                # Fallback a visualització antiga
                self._visualize_3d_fallback()
        
        except Exception as e:
            messagebox.showerror("Error", f"Error en la visualització:\n{e}")
    
    def visualize_3d_with_options(self):
        """Visualització 3D amb opcions (adaptat per usar Visualizer3D nou)"""
        if not self.optimization_results:
            messagebox.showwarning("Avís", "Primer executa l'optimització")
            return
        
        try:
            mesh_to_use = self.simplified_mesh if self.simplified_mesh else self.original_mesh
            
            # Usar Visualizer3D nou si està disponible
            if self.visualizer:
                # Crear diàleg d'opcions o usar el mètode existent
                self.visualizer.show_3d_with_options(
                    self.optimization_results, 
                    mesh_to_use,
                    show_wireframe=True,
                    show_labels=True,
                    use_gradient=False
                )
            else:
                # Fallback a diàleg antic
                self._visualize_3d_options_fallback()
        
        except Exception as e:
            messagebox.showerror("Error", f"Error en la visualització:\n{e}")
    
    def _visualize_3d_fallback(self):
        """Fallback per visualització sense mòduls nous"""
        messagebox.showinfo("Informació", "Visualització amb funcionalitat limitada")
    
    def _visualize_3d_options_fallback(self):
        """Fallback per visualització amb opcions sense mòduls nous"""
        messagebox.showinfo("Informació", "Opcions de visualització no disponibles")
    
    def export_results(self):
        """Exporta els resultats (adaptat per usar ResultsExporter nou)"""
        if not self.optimization_results:
            messagebox.showwarning("Avís", "Primer executa l'optimització")
            return
        
        try:
            if self.exporter:
                # Usar ExportDialog nou
                from packassist.gui import ExportDialog
                
                def callback(options):
                    self._perform_modular_export(options)
                
                dialog = ExportDialog(self.root, self.optimization_results, callback)
                dialog.show()
            else:
                # Fallback a exportació antigua
                self.perform_export()
        
        except Exception as e:
            messagebox.showerror("Error", f"Error preparant l'exportació:\n{e}")
    
    def _perform_modular_export(self, options):
        """Realitza l'exportació amb el sistema modular nou"""
        try:
            # Seleccionar directori
            export_dir = filedialog.askdirectory(title="Directori d'exportació")
            if not export_dir:
                return
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"packassist_export_{timestamp}"
            
            exported_files = []
            mesh_to_use = self.simplified_mesh if self.simplified_mesh else self.original_mesh
            
            # Exportar segons les opcions
            if options.get('text'):
                filepath = os.path.join(export_dir, f"{base_name}.txt")
                if self.exporter.export_detailed_report(filepath, self.optimization_results):
                    exported_files.append(filepath)
            
            if options.get('csv'):
                filepath = os.path.join(export_dir, f"{base_name}.csv")
                if self.exporter.export_csv_data(
                    filepath, 
                    self.optimization_results['positions'],
                    self.optimization_results['rotations']
                ):
                    exported_files.append(filepath)
            
            if options.get('json'):
                filepath = os.path.join(export_dir, f"{base_name}.json")
                if self.exporter.export_json_data(filepath, self.optimization_results):
                    exported_files.append(filepath)
            
            if options.get('stl'):
                filepath = os.path.join(export_dir, f"{base_name}_positioned.stl")
                if self.exporter.export_positioned_stl(
                    filepath,
                    mesh_to_use,
                    self.optimization_results['positions'],
                    self.optimization_results['rotations']
                ):
                    exported_files.append(filepath)
            
            if options.get('image'):
                filepath = os.path.join(export_dir, f"{base_name}_3d_view.png")
                if self.exporter.export_3d_image(
                    filepath,
                    mesh_to_use,
                    self.optimization_results['positions'],
                    self.optimization_results['rotations']
                ):
                    exported_files.append(filepath)
            
            # Mostrar resultats
            if exported_files:
                files_list = "\n".join([f"• {os.path.basename(f)}" for f in exported_files])
                messagebox.showinfo(
                    "✅ Exportació completada",
                    f"S'han exportat {len(exported_files)} fitxers:\n\n{files_list}"
                )
            else:
                messagebox.showwarning("⚠️ Cap fitxer exportat", "No s'ha pogut exportar cap fitxer")
        
        except Exception as e:
            messagebox.showerror("Error", f"Error durant l'exportació:\n{e}")
    
    def perform_export(self):
        """Exportació amb sistema antic com a fallback"""
        messagebox.showinfo("Informació", "Usant sistema d'exportació llegat")
    
    def select_export_directory(self):
        """Selecciona el directori d'exportació"""
        directory = filedialog.askdirectory(title="Selecciona directori d'exportació")
        if directory:
            self.export_dir_var.set(directory)
    
    def run(self):
        """Inicia l'aplicació"""
        self.root.mainloop()


def main():
    """Funció principal"""
    try:
        app = PackAssistApp()
        app.run()
    except Exception as e:
        print(f"Error iniciant l'aplicació: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
