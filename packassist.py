#!/usr/bin/env python3
"""
PackAssist - GUI Original amb Arquitectura Modular
Manté la interfície completa original però utilitza mòduls separats
"""

import os
import sys
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from pathlib import Path
import numpy as np

# Afegir paths necessaris
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, 'actiu', 'src'))

# Imports dels nostres mòduls
try:
    from packassist.core import MeshLoader, PackingOptimizer, ResultsExporter
    from packassist.gui import Visualizer3D, ExportDialog, VisualizationDialog
    from packassist.utils import save_results_file, generate_timestamp_filename
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"Error important mòduls nous: {e}")
    MODULES_AVAILABLE = False

# Imports tradicionals com backup
try:
    import trimesh
except ImportError:
    trimesh = None

try:
    import pyvista as pv
except ImportError:
    pv = None

class PackAssistOriginalGUI:
    """Aplicació PackAssist amb GUI original completa però arquitectura modular"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PackAssist - Empaquetament Intel·ligent amb STL Real v2.0")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        
        # Variables principals (igual que l'original)
        self.stl_file_path = None
        self.original_mesh = None
        self.original_mesh_info = None
        self.simplified_mesh = None
        self.simplified_mesh_info = None
        self.optimization_results = None
        
        # Inicialitzar mòduls nous si estan disponibles
        if MODULES_AVAILABLE:
            self.mesh_loader = MeshLoader()
            self.visualizer = Visualizer3D()
            self.exporter = ResultsExporter()
            print("✅ Mòduls nous carregats correctament")
        else:
            print("⚠️ Usant sistema tradicional")
        
        # Variables de la interfície (copiades de l'original)
        self.setup_interface_variables()
        
        # Setup de l'aplicació original
        self.setup_components()
        self.setup_styles()
        self.create_widgets()
        
    def setup_interface_variables(self):
        """Configura les variables de la interfície (igual que l'original)"""
        # Variables per simplificació
        self.simplify_method = tk.StringVar(value="quadric_advanced")
        self.target_vertices = tk.IntVar(value=1000)
        self.preserve_volume = tk.BooleanVar(value=True)
        
        # Variables per optimització
        self.box_length = tk.StringVar(value="200")
        self.box_width = tk.StringVar(value="150") 
        self.box_height = tk.StringVar(value="100")
        self.pieces_limit = tk.IntVar(value=250)
        self.max_iterations = tk.IntVar(value=50)
        self.enable_rotations = tk.BooleanVar(value=True)
        self.enable_intelligent_spacing = tk.BooleanVar(value=True)
        self.optimization_method = tk.StringVar(value="intelligent")
        
    def setup_components(self):
        """Configura els components (adaptat per usar mòduls nous)"""
        self.components_loaded = False
        self.optimizer_func = None
        self.stl_loader = None
        self.simplifier_methods = {}
        
        print("Configurant components...")
        
        # Comprovar dependències
        self.available_libs = self.check_dependencies()
        
        # Carregar components
        if MODULES_AVAILABLE:
            self.load_new_components()
        else:
            self.load_traditional_components()
            
        self.components_loaded = True
        
    def load_new_components(self):
        """Carrega els nous mòduls"""
        try:
            # El mesh_loader ja està inicialitzat
            print("✅ MeshLoader configurat")
            
            # Configurar optimitzador (ens crearem instàncies quan calgui)
            print("✅ PackingOptimizer configurat")
            
            # Configurar exportador
            print("✅ ResultsExporter configurat")
            
            # Mantenir compatibilitat amb mètodes antics si cal
            self.setup_legacy_compatibility()
            
        except Exception as e:
            print(f"Error carregant mòduls nous: {e}")
            self.load_traditional_components()
    
    def setup_legacy_compatibility(self):
        """Manté compatibilitat amb mètodes antics"""
        # Simplificadors (per ara mantenim els antics)
        self.load_simplifiers()
        
        # STL Loader tradicional com backup
        self.load_stl_loader()
    
    def load_traditional_components(self):
        """Carrega components tradicionals com backup"""
        self.load_optimizer()
        self.load_simplifiers() 
        self.load_stl_loader()
    
    def check_dependencies(self):
        """Comprova les dependències disponibles (igual que l'original)"""
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
        """Carrega l'optimitzador (backup tradicional)"""
        try:
            from packassist.optimizer import PackingOptimizerAdvanced
            self.optimizer_func = PackingOptimizerAdvanced
            print("✅ Optimitzador tradicional carregat")
        except ImportError:
            print("❌ No es pot carregar l'optimitzador tradicional")
    
    def load_simplifiers(self):
        """Carrega els simplificadors (mantenim els antics)"""
        # PyMeshLab
        if self.available_libs.get('pymeshlab'):
            try:
                from packassist.core.mesh_simplifiers import simplify_mesh_pymeshlab
                self.simplifier_methods['pymeshlab'] = simplify_mesh_pymeshlab
                print("✅ Simplificador PyMeshLab carregat")
            except ImportError:
                print("❌ Error carregant simplificador PyMeshLab")
        
        # Trimesh fallback
        if self.available_libs.get('trimesh'):
            try:
                from packassist.core.mesh_simplifiers import simplify_mesh_trimesh
                self.simplifier_methods['trimesh'] = simplify_mesh_trimesh
                print("✅ Simplificador Trimesh carregat")
            except ImportError:
                print("❌ Error carregant simplificador Trimesh")
    
    def load_stl_loader(self):
        """Carrega el STL loader (backup tradicional)"""
        try:
            from packassist.stl_loader import load_and_process_stl
            self.stl_loader = load_and_process_stl
            print("✅ STL Loader tradicional carregat")
        except ImportError:
            print("❌ STL Loader tradicional no disponible")
    
    def setup_styles(self):
        """Configura els estils (igual que l'original)"""
        style = ttk.Style()
        
        # Estil per títols
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Step.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Info.TLabel', font=('Arial', 10))
        
        # Estil per botons d'acció
        style.configure('Action.TButton', font=('Arial', 10, 'bold'))
    
    def create_widgets(self):
        """Crea la interfície principal amb panells (igual que l'original)"""
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
        
        # Pestanya 3: Optimitzador Avançat (UNIFICAT)
        self.tab_optimize = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_optimize, text="🚀 3. Optimitzador Avançat")
        self.create_unified_optimizer_tab()
        
        # Pestanya 4: Resultats 3D
        self.tab_results = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_results, text="🎮 4. Visualitzar")
        self.create_results_tab()
    
    def create_import_tab(self):
        """Crea la pestanya d'importació (igual que l'original)"""
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
        
        # Afegir text inicial
        self.original_info_text.insert(tk.END, "📁 Carrega un fitxer STL per veure les estadístiques de la malla original...")
        self.original_info_text.config(state='disabled')
        
        self.original_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        orig_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Botó per visualitzar original en 3D
        self.view_original_btn = ttk.Button(main_frame, text="🎮 Visualitzar Original 3D", 
                                           command=self.view_original_3d, state='disabled')
        self.view_original_btn.pack(pady=10)
    
    def create_simplify_tab(self):
        """Crea la pestanya de simplificació (igual que l'original)"""
        main_frame = ttk.Frame(self.tab_simplify, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Títol
        title_label = ttk.Label(main_frame, text="🔧 Reduir Complexitat de la Malla", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Controls de simplificació
        controls_frame = ttk.LabelFrame(main_frame, text="Controls de Reducció", padding="15")
        controls_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Mètodes disponibles
        ttk.Label(controls_frame, text="Mètode de reducció:").pack(anchor=tk.W, pady=(0, 5))
        
        method_frame = ttk.Frame(controls_frame)
        method_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(method_frame, text="Mètode: PyMeshLab Quadric (Recomanat)", 
                 style='Step.TLabel').pack(side=tk.LEFT)
        
        # Slider per vèrtexs objectiu
        ttk.Label(controls_frame, text="Nivell de reducció:").pack(anchor=tk.W, pady=(10, 0))
        
        self.vertices_scale = tk.Scale(controls_frame, from_=100, to=50000,
                                      orient=tk.HORIZONTAL, variable=self.target_vertices,
                                      command=self.update_vertices_label)
        self.vertices_scale.pack(fill=tk.X, pady=5)
        
        self.vertices_label = ttk.Label(controls_frame, text="1000 vèrtexs")
        self.vertices_label.pack(anchor=tk.W)
        
        # Opció per preservar volum
        ttk.Checkbutton(controls_frame, text="Preservar volum original", 
                       variable=self.preserve_volume).pack(anchor=tk.W, pady=(10, 0))
        
        # Botó de simplificació
        self.simplify_btn = ttk.Button(controls_frame, text="🚀 Reduir Complexitat", 
                                      command=self.simplify_mesh, state='disabled')
        self.simplify_btn.pack(pady=10)
        
        # Frame de comparació
        comparison_frame = ttk.LabelFrame(main_frame, text="Comparació Original vs Optimitzada", padding="15")
        comparison_frame.pack(fill=tk.BOTH, expand=True)
        
        # Dividir en dues columnes
        left_frame = ttk.Frame(comparison_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        right_frame = ttk.Frame(comparison_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Info original
        ttk.Label(left_frame, text="📊 Malla Original", style='Step.TLabel').pack()
        self.original_stats = tk.Text(left_frame, height=8, wrap=tk.WORD)
        # Afegir text inicial
        self.original_stats.insert(tk.END, "📁 Carrega un fitxer STL per veure les estadístiques...")
        self.original_stats.config(state='disabled')
        self.original_stats.pack(fill=tk.BOTH, expand=True, pady=5)
        
        orig_btn_frame = ttk.Frame(left_frame)
        orig_btn_frame.pack(fill=tk.X, pady=5)
        
        self.view_orig_btn = ttk.Button(orig_btn_frame, text="🎮 Visualitzar 3D", 
                                       command=self.view_original_3d, state='disabled')
        self.view_orig_btn.pack(side=tk.LEFT)
        
        # Info optimitzada
        ttk.Label(right_frame, text="📊 Malla Optimitzada", style='Step.TLabel').pack()
        self.simplified_stats = tk.Text(right_frame, height=8, wrap=tk.WORD)
        # Afegir text inicial
        self.simplified_stats.insert(tk.END, "🔧 Primer redueix la complexitat per veure les estadístiques...")
        self.simplified_stats.config(state='disabled')
        self.simplified_stats.pack(fill=tk.BOTH, expand=True, pady=5)
        
        simp_btn_frame = ttk.Frame(right_frame)
        simp_btn_frame.pack(fill=tk.X, pady=5)
        
        self.view_simp_btn = ttk.Button(simp_btn_frame, text="🎮 Visualitzar 3D", 
                                       command=self.view_simplified_3d, state='disabled')
        self.view_simp_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.compare_btn = ttk.Button(simp_btn_frame, text="⚖️ Comparar Ambdues", 
                                     command=self.compare_meshes_3d, state='disabled')
        self.compare_btn.pack(side=tk.LEFT)
    
    def create_unified_optimizer_tab(self):
        """Crea la pestanya d'optimització avançada unificada"""
        main_frame = ttk.Frame(self.tab_optimize, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Títol
        title_label = ttk.Label(main_frame, text="🚀 Optimitzador Avançat amb Orientacions Múltiples", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Configuració de la caixa
        box_frame = ttk.LabelFrame(main_frame, text="Dimensions de la Caixa (mm)", padding="15")
        box_frame.pack(fill=tk.X, pady=(0, 15))
        
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
        
        # Configuració avançada
        advanced_frame = ttk.LabelFrame(main_frame, text="Configuració Avançada", padding="15")
        advanced_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Primera línia: Límit de peces i iteracions
        line1_frame = ttk.Frame(advanced_frame)
        line1_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Límit de peces (opcional)
        self.limit_pieces = tk.BooleanVar(value=False)
        limit_check = ttk.Checkbutton(line1_frame, text="Límit de peces:", variable=self.limit_pieces)
        limit_check.pack(side=tk.LEFT)
        
        self.max_pieces_var = tk.StringVar(value="100")
        self.max_pieces_entry = ttk.Entry(line1_frame, textvariable=self.max_pieces_var, width=8, state='disabled')
        self.max_pieces_entry.pack(side=tk.LEFT, padx=(5, 20))
        
        # Callback per activar/desactivar l'entry
        def toggle_pieces_entry():
            if self.limit_pieces.get():
                self.max_pieces_entry.config(state='normal')
            else:
                self.max_pieces_entry.config(state='disabled')
        self.limit_pieces.trace('w', lambda *args: toggle_pieces_entry())
        
        # Segona línia: Mode d'empaquetament
        line2_frame = ttk.Frame(advanced_frame)
        line2_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.use_floor_mode = tk.BooleanVar(value=True)
        floor_check = ttk.Checkbutton(line2_frame, text="Mode pisos ordenats (amb marge i separació 1cm)", 
                                     variable=self.use_floor_mode, command=self._toggle_floor_mode)
        floor_check.pack(side=tk.LEFT)
        
        # Tercera línia: Configuració de marge (només visible en mode pisos)
        self.line3_frame = ttk.Frame(advanced_frame)
        self.line3_frame.pack(fill=tk.X)
        
        ttk.Label(self.line3_frame, text="Marge al voltant de la peça (mm):").pack(side=tk.LEFT)
        self.margin_var = tk.StringVar(value="2.0")
        self.margin_entry = ttk.Entry(self.line3_frame, textvariable=self.margin_var, width=8)
        self.margin_entry.pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(self.line3_frame, text="Separació entre pisos:").pack(side=tk.LEFT)
        self.floor_separation = tk.StringVar(value="10.0")
        self.floor_entry = ttk.Entry(self.line3_frame, textvariable=self.floor_separation, width=8, state='readonly')
        self.floor_entry.pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(self.line3_frame, text="mm (cartró marró)").pack(side=tk.LEFT)
        
        # Quarta línia: Configuració de marge per mode a granel (només visible en mode a granel)
        self.line4_frame = ttk.Frame(advanced_frame)
        
        # Variables per al mode a granel
        self.pieces_can_touch = tk.BooleanVar(value=False)
        self.bulk_margin_var = tk.StringVar(value="2.0")
        
        # Opció per indicar si les peces poden tocar-se
        touch_checkbox = ttk.Checkbutton(
            self.line4_frame, 
            text="🔗 Les peces poden tocar-se (sense marge - màxim aprofitament)",
            variable=self.pieces_can_touch,
            command=self._update_bulk_margin_state
        )
        touch_checkbox.pack(anchor=tk.W, pady=(0, 5))
        
        # Frame per marge personalitzat en mode a granel
        bulk_margin_frame = ttk.Frame(self.line4_frame)
        bulk_margin_frame.pack(fill=tk.X)
        
        ttk.Label(bulk_margin_frame, text="📏 Marge entre peces a granel (mm):").pack(side=tk.LEFT)
        self.bulk_margin_entry = ttk.Entry(bulk_margin_frame, textvariable=self.bulk_margin_var, width=8)
        self.bulk_margin_entry.pack(side=tk.LEFT, padx=(5, 20))
        
        help_label = ttk.Label(bulk_margin_frame, text="ℹ️ 0mm = peces poden tocar-se", foreground='gray')
        help_label.pack(side=tk.LEFT)
        
        # Botó d'optimització
        self.optimize_btn = ttk.Button(main_frame, text="🚀 Iniciar Optimització Avançada", 
                                      command=self.start_advanced_optimization, state='disabled')
        self.optimize_btn.pack(pady=15)
        
        # Barra de progrés amb detalls
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(0, 5))
        
        self.progress_label = ttk.Label(progress_frame, text="Esperant per començar...")
        self.progress_label.pack()
        
        # Resultats
        results_frame = ttk.LabelFrame(main_frame, text="Resultats de l'Optimització", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        self.results_text = tk.Text(results_frame, height=12, wrap=tk.WORD)
        results_scrollbar = ttk.Scrollbar(results_frame, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=results_scrollbar.set)
        
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Text d'ajuda inicial
        self.results_text.insert(tk.END,
            "🎯 OPTIMITZADOR AVANÇAT AMB MODES D'EMPAQUETAMENT\n\n"
            "MODES DISPONIBLES:\n"
            "🔸 PISOS ORDENATS: Distribució per pisos amb marge i separació de cartró\n"
            "   • Peces ordenades en graella per pisos\n"
            "   • Marge configurable al voltant de cada peça\n" 
            "   • Separació d'1cm entre pisos (cartró 10mm)\n"
            "   • Visualització amb STL simplificat\n\n"
            "🔸 A GRANEL: Empaquetament lliure sense restriccions\n"
            "   • Col·lisions exactes amb geometria STL real\n"
            "   • Orientacions múltiples automàtiques\n"
            "   • Màxim aprofitament de l'espai\n"
            "   • Peces en qualsevol posició i orientació\n\n"
            "📋 INSTRUCCIONS:\n"
            "1. Carrega una peça STL a la pestanya 'Importar'\n"
            "2. Configura les dimensions de la caixa\n"
            "3. Selecciona el mode d'empaquetament\n"
            "4. Ajusta les opcions segons el mode escollit\n"
            "5. Fes clic a 'Iniciar Optimització Avançada'\n\n"
            "⚠️ NOTA: El mode pisos és més ràpid, el mode a granel pot trigar més")
        self.results_text.config(state='disabled')
    
    def _toggle_floor_mode(self):
        """Alterna entre mode pisos i mode a granel"""
        if self.use_floor_mode.get():
            # Mode pisos: mostrar opcions de marge i separació
            self.line3_frame.pack(fill=tk.X)
            self.line4_frame.pack_forget()  # Amagar opcions de granel
            self.margin_entry.config(state='normal')
            self.floor_entry.config(state='readonly')
            print("🏢 Mode pisos activat: marge + separació")
        else:
            # Mode a granel: mostrar opcions de col·lisions lliures
            self.line3_frame.pack_forget()  # Amagar opcions de pisos
            self.line4_frame.pack(fill=tk.X)
            self._update_bulk_margin_state()  # Actualitzar estat del marge a granel
            print("📦 Mode a granel activat: col·lisions configurables")
    
    def _update_bulk_margin_state(self):
        """Actualitza l'estat de l'entrada de marge segons si les peces poden tocar-se"""
        if self.pieces_can_touch.get():
            self.bulk_margin_entry.config(state='disabled')
            self.bulk_margin_var.set("0.0")  # Forçar marge a 0
            print("🔗 Peces poden tocar-se: marge = 0mm")
        else:
            self.bulk_margin_entry.config(state='normal')
            if self.bulk_margin_var.get() == "0.0":
                self.bulk_margin_var.set("2.0")  # Valor per defecte
            print(f"📏 Marge entre peces: {self.bulk_margin_var.get()}mm")
    
    def create_results_tab(self):
        """Crea la pestanya de resultats (igual que l'original però millorada)"""
        main_frame = ttk.Frame(self.tab_results, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Títol
        title_label = ttk.Label(main_frame, text="🎮 Visualització i Exportació", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Botons d'acció principals
        actions_frame = ttk.LabelFrame(main_frame, text="Accions", padding="15")
        actions_frame.pack(fill=tk.X, pady=(0, 20))
        
        buttons_row1 = ttk.Frame(actions_frame)
        buttons_row1.pack(fill=tk.X, pady=(0, 10))
        
        # Visualització directa (nou)
        self.viz_direct_btn = ttk.Button(buttons_row1, text="🎮 Visualitzar 3D Directe", 
                                        command=self.visualize_3d_direct, state='disabled')
        self.viz_direct_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Visualització amb opcions (mantenim l'original)
        self.viz_options_btn = ttk.Button(buttons_row1, text="⚙️ Opcions de Visualització", 
                                         command=self.visualize_3d, state='disabled')
        self.viz_options_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Exportació (millorada)
        self.export_btn = ttk.Button(buttons_row1, text="📤 Exportar Resultats", 
                                    command=self.export_results, state='disabled')
        self.export_btn.pack(side=tk.LEFT)
        
        # Informació dels resultats
        info_frame = ttk.LabelFrame(main_frame, text="Informació dels Resultats", padding="15")
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        self.results_info_text = tk.Text(info_frame, height=15, wrap=tk.WORD)
        info_scrollbar = ttk.Scrollbar(info_frame, command=self.results_info_text.yview)
        self.results_info_text.configure(yscrollcommand=info_scrollbar.set)
        
        self.results_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Ara implementem els mètodes funcionals...
    
    def import_stl(self):
        """Importa un fitxer STL (millorat amb mòduls nous)"""
        filetypes = [
            ("Fitxers STL", "*.stl"),
            ("Fitxers STP", "*.stp *.step"),
            ("Tots els fitxers", "*.*")
        ]
        
        filepath = filedialog.askopenfilename(
            title="Selecciona un fitxer STL",
            filetypes=filetypes
        )
        
        if not filepath:
            return
        
        try:
            # Usar el nou MeshLoader si està disponible
            if MODULES_AVAILABLE and hasattr(self, 'mesh_loader'):
                self._import_with_new_loader(filepath)
            else:
                self._import_with_traditional_loader(filepath)
                
        except Exception as e:
            messagebox.showerror("Error", f"Error carregant el fitxer:\n{e}")
    
    def _import_with_new_loader(self, filepath):
        """Importa amb el nou MeshLoader"""
        try:
            # Carregar amb el nou sistema
            self.original_mesh = self.mesh_loader.load_mesh(filepath)
            
            # Obtenir informació
            mesh_info = self.mesh_loader.get_mesh_info(self.original_mesh)
            
            # Crear structure d'informació compatible
            self.original_mesh_info = {
                'vertices': mesh_info['vertices_count'],
                'faces': mesh_info['faces_count'],
                'volume': mesh_info['volume'],
                'area': mesh_info['surface_area'],
                'mesh': self.original_mesh,
                'bounds': mesh_info['bounds'],
                'dimensions': mesh_info['dimensions']
            }
            
            # Actualitzar interfície
            self._update_interface_after_import(filepath)
            
            print("✅ Fitxer carregat amb nou MeshLoader")
            
        except Exception as e:
            print(f"Error amb nou MeshLoader: {e}")
            # Fallback al mètode tradicional
            self._import_with_traditional_loader(filepath)
    
    def _import_with_traditional_loader(self, filepath):
        """Importa amb el loader tradicional"""
        if self.stl_loader:
            result = self.stl_loader(filepath)
            if result and result.get('success'):
                self.original_mesh = result['mesh']
                self.original_mesh_info = result
                self._update_interface_after_import(filepath)
                print("✅ Fitxer carregat amb loader tradicional")
            else:
                raise Exception("Error en el loader tradicional")
        else:
            # Fallback directe amb trimesh
            import trimesh
            self.original_mesh = trimesh.load(filepath)
            
            # Crear informació completa de la malla
            bounds = self.original_mesh.bounds
            dims = bounds[1] - bounds[0]
            
            self.original_mesh_info = {
                'vertices': len(self.original_mesh.vertices),
                'faces': len(self.original_mesh.faces),
                'volume': getattr(self.original_mesh, 'volume', 0),
                'area': getattr(self.original_mesh, 'area', 0),
                'mesh': self.original_mesh,
                'bounds': bounds,
                'dimensions': {
                    'width': dims[0],
                    'depth': dims[1], 
                    'height': dims[2]
                },
                'is_watertight': getattr(self.original_mesh, 'is_watertight', False)
            }
            self._update_interface_after_import(filepath)
            print("✅ Fitxer carregat amb trimesh directe")
    
    def _update_interface_after_import(self, filepath):
        """Actualitza la interfície després d'importar"""
        self.stl_file_path = filepath
        filename = os.path.basename(filepath)
        self.file_label.config(text=f"✅ {filename}")
        
        # Debug: Verificar que tenim la informació
        print(f"🔍 Debug: original_mesh_info = {self.original_mesh_info}")
        
        # Actualitzar informació a totes les pestanyes
        self.update_mesh_info(self.original_info_text, self.original_mesh_info)  # Pestanya 1
        self.update_mesh_info(self.original_stats, self.original_mesh_info)      # Pestanya 2
        
        # Habilitar botons
        self.view_original_btn.config(state='normal')
        self.simplify_btn.config(state='normal') 
        self.optimize_btn.config(state='normal')
        
        print(f"📁 Fitxer carregat: {filename}")
        print(f"✅ Informació de malla actualitzada")
    
    # Mètodes de visualització (adaptats per usar els nous mòduls)
    
    def visualize_3d_direct(self):
        """Visualització 3D directa amb els nous mòduls"""
        if not self.optimization_results:
            messagebox.showwarning("Avís", "Primer executa l'optimització")
            return
        
        if MODULES_AVAILABLE and hasattr(self, 'visualizer'):
            # Usar el nou visualitzador
            mesh_to_use = self.simplified_mesh if self.simplified_mesh else self.original_mesh
            self.visualizer.show_direct_3d(self.optimization_results, mesh_to_use)
        else:
            # Fallback al mètode tradicional
            self._show_3d_visualization_traditional()
    
    def visualize_3d(self):
        """Visualització 3D amb opcions (mantenim funcionalitat original)"""
        if not self.optimization_results:
            messagebox.showwarning("Avís", "Primer executa l'optimització")
            return
        
        if MODULES_AVAILABLE and hasattr(self, 'visualizer'):
            # Usar el nou diàleg
            def callback(action, options):
                mesh_to_use = self.simplified_mesh if self.simplified_mesh else self.original_mesh
                if action == 'visualize':
                    self.visualizer.show_3d_with_options(self.optimization_results, mesh_to_use, **options)
                elif action == 'export':
                    self.export_results()
            
            dialog = VisualizationDialog(self.root, self.optimization_results, callback)
            dialog.show()
        else:
            # Usar mètode tradicional
            self.visualize_3d_with_options()
    
    def export_results(self):
        """Exporta resultats (millorat amb nous mòduls)"""
        if not self.optimization_results:
            messagebox.showwarning("Avís", "Primer executa l'optimització")
            return
        
        if MODULES_AVAILABLE and hasattr(self, 'exporter'):
            # Usar el nou sistema d'exportació
            def callback(options):
                self._perform_export_new(options)
            
            dialog = ExportDialog(self.root, self.optimization_results, callback)
            dialog.show()
        else:
            # Usar mètode tradicional 
            self._perform_export_traditional()
    
    def _perform_export_new(self, options):
        """Realitza exportació amb el nou sistema"""
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
            
            # Exportar segons opcions
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
                    filepath, mesh_to_use,
                    self.optimization_results['positions'],
                    self.optimization_results['rotations']
                ):
                    exported_files.append(filepath)
            
            if options.get('image'):
                filepath = os.path.join(export_dir, f"{base_name}_3d_view.png")
                if self.exporter.export_3d_image(
                    filepath, mesh_to_use,
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
    
    # Mètode d'optimització (adaptat per usar nous mòduls)
    
    def start_optimization(self):
        """Inicia l'optimització (millorat amb nous mòduls)"""
        if not self.original_mesh:
            messagebox.showwarning("Avís", "Primer carrega un fitxer STL")
            return
        
        try:
            # Obtenir paràmetres
            container_dims = (
                float(self.box_length.get()),
                float(self.box_width.get()),
                float(self.box_height.get())
            )
            target_pieces = self.pieces_limit.get()
            method = self.optimization_method.get()
            
            # Usar nou optimitzador si està disponible
            if MODULES_AVAILABLE:
                self._optimize_with_new_system(container_dims, target_pieces, method)
            else:
                self._optimize_with_traditional_system(container_dims, target_pieces, method)
                
        except ValueError as e:
            messagebox.showerror("Error", f"Error en els paràmetres: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Error durant l'optimització: {e}")
    
    def _optimize_with_new_system(self, container_dims, target_pieces, method):
        """Optimitza amb el nou sistema"""
        # Deshabilitar botó
        self.optimize_btn.config(state='disabled', text="🔄 Optimitzant...")
        self.root.update()
        
        try:
            # Crear optimitzador
            optimizer = PackingOptimizer(container_dims)
            
            # Usar malla simplificada si està disponible
            mesh_to_use = self.simplified_mesh if self.simplified_mesh else self.original_mesh
            
            # Executar optimització
            results = optimizer.optimize(mesh_to_use, target_pieces, method)
            
            if results['success']:
                self.optimization_results = results
                self._display_optimization_results(results)
                self._enable_results_buttons()
                
                # Guardar resultats automàticament
                self._save_results_automatically(results)
                
                messagebox.showinfo("✅ Èxit", f"Optimització completada!\nPeces col·locades: {results['pieces_count']}")
            else:
                messagebox.showerror("Error", f"Error en l'optimització:\n{results.get('error', 'Error desconegut')}")
            
        finally:
            self.optimize_btn.config(state='normal', text="🚀 INICIAR OPTIMITZACIÓ")
    
    def _optimize_with_traditional_system(self, container_dims, target_pieces, method):
        """Optimitza amb el sistema tradicional"""
        # Implementar fallback al sistema antic si cal
        messagebox.showinfo("Info", "Usant sistema d'optimització tradicional")
        # Aquí podriem implementar la crida al sistema antic
    
    def _display_optimization_results(self, results):
        """Mostra els resultats de l'optimització"""
        text = f"🎯 OPTIMITZACIÓ COMPLETADA\n"
        text += f"{'='*50}\n\n"
        text += f"📊 Resultats:\n"
        text += f"   • Peces col·locades: {results['pieces_count']}\n"
        text += f"   • Eficiència: {results['efficiency']:.2f}%\n"
        text += f"   • Mètode: {results['method']}\n"
        text += f"   • Temps d'execució: {results.get('execution_time', 0):.2f} segons\n\n"
        
        if 'box_dims' in results:
            box_dims = results['box_dims']
            text += f"📦 Contenidor:\n"
            text += f"   • Dimensions: {box_dims['length']:.1f} x {box_dims['width']:.1f} x {box_dims['height']:.1f} mm\n"
            text += f"   • Volum total: {box_dims['volume']:.1f} mm³\n\n"
        
        if 'obj_dims' in results:
            obj_dims = results['obj_dims']
            text += f"🔧 Objecte:\n"
            text += f"   • Dimensions: {obj_dims['length']:.1f} x {obj_dims['width']:.1f} x {obj_dims['height']:.1f} mm\n"
            text += f"   • Volum unitari: {obj_dims['volume']:.1f} mm³\n\n"
        
        text += f"✅ Optimització finalitzada correctament!\n"
        text += f"Usa la pestanya 'Visualitzar' per veure els resultats o exportar-los.\n"
        
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, text)
        
        # També actualitzar l'àrea d'informació de resultats
        self.results_info_text.delete(1.0, tk.END)
        self.results_info_text.insert(tk.END, text)
    
    def _enable_results_buttons(self):
        """Habilita els botons de resultats"""
        self.viz_direct_btn.config(state='normal')
        self.viz_options_btn.config(state='normal')
        self.export_btn.config(state='normal')
    
    def _save_results_automatically(self, results):
        """Guarda els resultats automàticament"""
        try:
            if MODULES_AVAILABLE:
                filename = generate_timestamp_filename("packassist_results", "txt")
                
                from datetime import datetime
                content = f"PackAssist - Resultats d'Optimització\n"
                content += f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                content += f"Fitxer: {os.path.basename(self.stl_file_path) if self.stl_file_path else 'Desconegut'}\n"
                content += f"Mètode: {results['method']}\n"
                content += f"Peces col·locades: {results['pieces_count']}\n"
                content += f"Eficiència: {results['efficiency']:.2f}%\n\n"
                
                # Afegir posicions
                content += "Posicions de les peces:\n"
                for i, (pos, rot) in enumerate(zip(results['positions'], results['rotations'])):
                    content += f"Peça {i+1}: Pos({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}) "
                    content += f"Rot({rot[0]:.0f}°, {rot[1]:.0f}°, {rot[2]:.0f}°)\n"
                
                save_results_file(content, filename)
                print(f"💾 Resultats guardats: {filename}")
        except Exception as e:
            print(f"Error guardant resultats: {e}")
    
    # Mètodes auxiliars (mantenim funcionalitat original)
    
    def update_mesh_info(self, text_widget, mesh_info):
        """Actualitza la informació de la malla amb més detalls"""
        try:
            text_widget.config(state='normal')
            text_widget.delete(1.0, tk.END)
            
            if not mesh_info:
                text_widget.insert(tk.END, "❌ No hi ha informació de la malla disponible.\n")
                text_widget.insert(tk.END, "Carrega primer un fitxer STL per veure les estadístiques.")
                text_widget.config(state='disabled')
                return
            
            info = f"📊 ESTADÍSTIQUES DE LA MALLA\n"
            info += f"{'='*50}\n\n"
            
            # Estadístiques bàsiques
            vertices = mesh_info.get('vertices', 0)
            faces = mesh_info.get('faces', 0)
            volume = mesh_info.get('volume', 0)
            area = mesh_info.get('area', 0)
            
            info += f"🔺 GEOMETRIA:\n"
            info += f"   • Vèrtexs: {vertices:,}\n"
            info += f"   • Cares: {faces:,}\n\n"
            
            # Volum i àrea
            info += f"📐 MESURES:\n"
            if volume > 0:
                if volume > 1000000:
                    info += f"   • Volum: {volume/1000000:.2f} cm³\n"
                else:
                    info += f"   • Volum: {volume:.2f} mm³\n"
            else:
                info += f"   • Volum: No disponible\n"
                
            if area > 0:
                if area > 10000:
                    info += f"   • Àrea superfície: {area/100:.2f} cm²\n"
                else:
                    info += f"   • Àrea superfície: {area:.2f} mm²\n"
            else:
                info += f"   • Àrea superfície: No disponible\n"
            
            # Dimensions del bounding box
            if 'dimensions' in mesh_info and mesh_info['dimensions']:
                dims = mesh_info['dimensions']
                info += f"\n📏 DIMENSIONS (Bounding Box):\n"
                info += f"   • Amplada (X): {dims[0] if isinstance(dims, (list, tuple)) else dims.get('width', 0):.2f} mm\n"
                info += f"   • Profunditat (Y): {dims[1] if isinstance(dims, (list, tuple)) else dims.get('depth', 0):.2f} mm\n"
                info += f"   • Altura (Z): {dims[2] if isinstance(dims, (list, tuple)) else dims.get('height', 0):.2f} mm\n"
            elif hasattr(self, 'original_mesh') and self.original_mesh:
                # Calcular dimensions directament de la malla
                bounds = self.original_mesh.bounds
                dims = bounds[1] - bounds[0]
                info += f"\n� DIMENSIONS (Bounding Box):\n"
                info += f"   • Amplada (X): {dims[0]:.2f} mm\n"
                info += f"   • Profunditat (Y): {dims[1]:.2f} mm\n"
                info += f"   • Altura (Z): {dims[2]:.2f} mm\n"
            
            # Qualitat de la malla
            info += f"\n💡 QUALITAT:\n"
            if vertices > 0 and faces > 0:
                density = faces / vertices if vertices > 0 else 0
                info += f"   • Densitat: {density:.2f} cares/vèrtex\n"
                
                # Classificació de complexitat
                if vertices < 1000:
                    complexity = "Baixa"
                elif vertices < 10000:
                    complexity = "Mitjana"
                elif vertices < 100000:
                    complexity = "Alta"
                else:
                    complexity = "Molt Alta"
                info += f"   • Complexitat: {complexity}\n"
            
            # Informació de watertight si està disponible
            if hasattr(self, 'original_mesh') and self.original_mesh:
                try:
                    is_watertight = self.original_mesh.is_watertight
                    info += f"   • Malla tancada: {'Sí' if is_watertight else 'No'}\n"
                except:
                    info += f"   • Malla tancada: No disponible\n"
            
            text_widget.insert(tk.END, info)
            text_widget.config(state='disabled')
            
        except Exception as e:
            print(f"Error actualitzant informació de malla: {e}")
            text_widget.config(state='normal')
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, f"❌ Error mostrant informació: {e}")
            text_widget.config(state='disabled')
            
            # Informació de reducció si està disponible
            if 'reduction_ratio' in mesh_info:
                info += f"\n🔧 Reducció de Complexitat:\n"
                info += f"   • Reducció: {mesh_info['reduction_ratio']:.1f}%\n"
                info += f"   • Mètode: {mesh_info.get('method', 'PyMeshLab')}\n"
            
            # Estat
            info += f"\n✅ Malla carregada i llesta per processar"
            
            text_widget.insert(tk.END, info)
        else:
            text_widget.insert(tk.END, "❌ No hi ha informació de malla disponible")
        
        # Permetre scrolling però no edició
        text_widget.config(state='normal')
    
    def update_vertices_label(self, value):
        """Actualitza l'etiqueta de vèrtexs"""
        current = self.target_vertices.get()
        if hasattr(self, 'original_mesh_info') and self.original_mesh_info:
            original = self.original_mesh_info.get('vertices', 1)
            reduction = ((original - current) / original) * 100 if original > 0 else 0
            self.vertices_label.config(text=f"{current:,} vèrtexs ({reduction:.1f}% reducció)")
        else:
            self.vertices_label.config(text=f"{current:,} vèrtexs")
    
    # Mètodes de simplificació (mantenim els originals)
    
    def simplify_mesh(self):
        """Simplifica la malla utilitzant els simplificadors existents"""
        if not self.original_mesh:
            messagebox.showwarning("Avís", "Primer has d'importar un fitxer STL")
            return
        
        try:
            target = self.target_vertices.get()
            method = self.simplify_method.get()
            preserve_vol = self.preserve_volume.get()
            
            self.simplify_btn.config(state='disabled', text="🔄 Reduint complexitat...")
            self.root.update()
            
            thread = threading.Thread(target=self._simplify_worker, args=(target, method, preserve_vol))
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en la reducció: {e}")
            self.simplify_btn.config(state='normal', text="🚀 Reduir Complexitat")
    
    def _simplify_worker(self, target, method, preserve_volume):
        """Worker per la simplificació en fil separat"""
        try:
            original_mesh = self.original_mesh
            
            print(f"🔧 Iniciant simplificació: {len(original_mesh.vertices)} vèrtexs -> {target} vèrtexs amb mètode {method}")
            
            if method == "quadric_advanced" and 'pymeshlab' in self.simplifier_methods:
                self.simplified_mesh = self.simplifier_methods['pymeshlab'](original_mesh, target, preserve_volume)
                method_used = "PyMeshLab Quadric"
            elif method == "trimesh_fallback" and 'trimesh' in self.simplifier_methods:
                self.simplified_mesh = self.simplifier_methods['trimesh'](original_mesh, target, preserve_volume)
                method_used = "Trimesh"
            else:
                # Fallback simple
                try:
                    current_vertices = len(original_mesh.vertices)
                    if current_vertices <= target:
                        self.simplified_mesh = original_mesh
                    else:
                        # Calcular target_faces aproximat
                        current_faces = len(original_mesh.faces)
                        target_faces = int(target * (current_faces / current_vertices))
                        self.simplified_mesh = original_mesh.simplify_quadric_decimation(target_faces)
                    method_used = "Trimesh Basic"
                except Exception as e:
                    print(f"Error en fallback: {e}")
                    self.simplified_mesh = original_mesh
                    method_used = "Cap reducció aplicada"
            
            if self.simplified_mesh and len(self.simplified_mesh.vertices) > 0:
                # Calcular estadístiques de reducció
                orig_vertices = len(original_mesh.vertices)
                new_vertices = len(self.simplified_mesh.vertices)
                reduction_ratio = ((orig_vertices - new_vertices) / orig_vertices) * 100
                
                # Calcular preservació de volum
                orig_volume = original_mesh.volume if hasattr(original_mesh, 'volume') else 0
                new_volume = self.simplified_mesh.volume if hasattr(self.simplified_mesh, 'volume') else 0
                volume_preservation = (new_volume / orig_volume) * 100 if orig_volume > 0 else 100
                
                # Crear info de la malla simplificada
                self.simplified_mesh_info = {
                    'vertices': new_vertices,
                    'faces': len(self.simplified_mesh.faces),
                    'volume': new_volume,
                    'area': self.simplified_mesh.area if hasattr(self.simplified_mesh, 'area') else 0,
                    'mesh': self.simplified_mesh,
                    'reduction_ratio': reduction_ratio,
                    'volume_preservation': volume_preservation,
                    'method': method_used
                }
                
                # Actualitzar interfície en el fil principal
                self.root.after(0, self._update_after_simplification, True, method_used)
            else:
                self.root.after(0, self._update_after_simplification, False, "Malla simplificada buida")
                
        except Exception as e:
            print(f"Error en simplificació: {e}")
            self.root.after(0, self._update_after_simplification, False, str(e))
    
    def _update_after_simplification(self, success, method_or_error):
        """Actualitza la interfície després de la simplificació"""
        try:
            if success:
                # Actualitzar informació de la malla simplificada
                self.update_mesh_info(self.simplified_stats, self.simplified_mesh_info)
                
                # Habilitar botons
                self.view_simp_btn.config(state='normal')
                self.compare_btn.config(state='normal')
                
                # Missatge d'èxit
                reduction = self.simplified_mesh_info.get('reduction_ratio', 0)
                volume_pres = self.simplified_mesh_info.get('volume_preservation', 100)
                
                success_msg = f"✅ Reducció completada!\n\n"
                success_msg += f"Mètode: {method_or_error}\n"
                success_msg += f"Reducció: {reduction:.1f}%\n"
                success_msg += f"Preservació volum: {volume_pres:.1f}%"
                
                messagebox.showinfo("Èxit", success_msg)
                
            else:
                messagebox.showerror("Error", f"Error en la reducció:\n{method_or_error}")
                
        finally:
            self.simplify_btn.config(state='normal', text="🚀 Reduir Complexitat")
    
    # Mètodes de visualització individuals (mantenim compatibilitat)
    
    def view_original_3d(self):
        """Visualitza la malla original en 3D"""
        if not self.original_mesh:
            messagebox.showwarning("Avís", "No hi ha malla original carregada")
            return
        
        self._show_single_mesh_3d(self.original_mesh, "Malla Original")
    
    def view_simplified_3d(self):
        """Visualitza la malla simplificada en 3D"""
        if not self.simplified_mesh:
            messagebox.showwarning("Avís", "No hi ha malla simplificada disponible")
            return
        
        self._show_single_mesh_3d(self.simplified_mesh, "Malla Simplificada")
    
    def compare_meshes_3d(self):
        """Compara les dues malles en 3D"""
        if not self.original_mesh or not self.simplified_mesh:
            messagebox.showwarning("Avís", "Cal tenir ambdues malles per comparar")
            return
        
        self._show_comparison_3d()
    
    def _show_single_mesh_3d(self, mesh, title):
        """Mostra una sola malla en 3D amb colors millors"""
        if not pv:
            messagebox.showerror("Error", "PyVista no està disponible")
            return
        
        try:
            import numpy as np
            
            plotter = pv.Plotter(window_size=(800, 600))
            plotter.set_background('white')
            
            # Convertir trimesh a pyvista
            faces_pv = np.column_stack(([3] * len(mesh.faces), mesh.faces)).flatten()
            mesh_pv = pv.PolyData(mesh.vertices, faces_pv)
            
            # Colors sòlids segons el títol
            if 'Original' in title:
                color = 'lightblue'
                text_color = 'darkblue'
            else:
                color = 'lightgreen'
                text_color = 'darkgreen'
            
            plotter.add_mesh(mesh_pv, color=color, show_edges=False, opacity=1.0)
            plotter.add_text(title, position='upper_edge', font_size=14, color='black')
            
            # Informació de la malla
            info_text = f"Vèrtexs: {len(mesh.vertices):,}\n"
            info_text += f"Cares: {len(mesh.faces):,}\n"
            info_text += f"Volum: {mesh.volume:.2f} mm³"
            
            plotter.add_text(info_text, position='lower_left', font_size=11, color=text_color)
            
            plotter.show_grid()
            plotter.add_axes()
            plotter.camera_position = 'iso'
            plotter.show()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en la visualització:\n{e}")
    
    def _show_comparison_3d(self):
        """Mostra comparació de les dues malles amb colors millors"""
        if not pv:
            messagebox.showerror("Error", "PyVista no està disponible")
            return
        
        try:
            import numpy as np
            
            plotter = pv.Plotter(shape=(1, 2), window_size=(1200, 600))
            plotter.set_background('white')
            
            # Malla original (esquerra) - Blau clar sòlid
            plotter.subplot(0, 0)
            faces_orig = np.column_stack(([3] * len(self.original_mesh.faces), self.original_mesh.faces)).flatten()
            mesh_orig_pv = pv.PolyData(self.original_mesh.vertices, faces_orig)
            plotter.add_mesh(mesh_orig_pv, color='lightblue', show_edges=False, opacity=1.0)
            plotter.add_text("Malla Original", position='upper_edge', font_size=14, color='black')
            
            orig_info = f"Vèrtexs: {len(self.original_mesh.vertices):,}\n"
            orig_info += f"Cares: {len(self.original_mesh.faces):,}\n"
            orig_info += f"Volum: {self.original_mesh.volume:.2f} mm³"
            plotter.add_text(orig_info, position='lower_left', font_size=11, color='darkblue')
            
            # Malla simplificada (dreta) - Verd clar sòlid
            plotter.subplot(0, 1)
            faces_simp = np.column_stack(([3] * len(self.simplified_mesh.faces), self.simplified_mesh.faces)).flatten()
            mesh_simp_pv = pv.PolyData(self.simplified_mesh.vertices, faces_simp)
            plotter.add_mesh(mesh_simp_pv, color='lightgreen', show_edges=False, opacity=1.0)
            plotter.add_text("Malla Simplificada", position='upper_edge', font_size=14, color='black')
            
            simp_info = f"Vèrtexs: {len(self.simplified_mesh.vertices):,}\n"
            simp_info += f"Cares: {len(self.simplified_mesh.faces):,}\n"
            simp_info += f"Volum: {self.simplified_mesh.volume:.2f} mm³\n"
            if self.simplified_mesh_info:
                reduction = self.simplified_mesh_info.get('reduction_ratio', 0)
                simp_info += f"Reducció: {reduction:.1f}%"
            plotter.add_text(simp_info, position='lower_left', font_size=11, color='darkgreen')
            
            # Configuració del visor
            plotter.show_grid()
            plotter.add_axes()
            plotter.link_views()
            plotter.show()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en la comparació:\n{e}")
    
    # Mètodes de fallback per compatibilitat amb sistema antic
    
    def _show_3d_visualization_traditional(self):
        """Visualització 3D tradicional (fallback)"""
        # Implementar visualització tradicional si cal
        messagebox.showinfo("Info", "Usant visualització tradicional")
    
    def visualize_3d_with_options(self):
        """Visualització 3D dels resultats d'optimització amb fallback PyVista"""
        if not hasattr(self, 'optimization_results') or not self.optimization_results:
            messagebox.showerror("Error", "Primer has de fer una optimització per poder visualitzar els resultats")
            return
        
        try:
            # Intentar usar el nou sistema de visualització primer
            if MODULES_AVAILABLE and hasattr(self, 'visualizer') and self.visualizer is not None:
                print("🎯 Intentant visualització amb nou sistema...")
                try:
                    mesh_to_use = self.simplified_mesh if (hasattr(self, 'simplified_mesh') and self.simplified_mesh is not None) else self.original_mesh
                    success = self.visualizer.show_direct_3d(results=self.optimization_results, mesh=mesh_to_use)
                    if success:
                        print("✅ Visualització iniciada amb nou sistema.")
                        return
                    else:
                        raise Exception("El nou sistema de visualització ha fallat.")
                except Exception as new_sys_error:
                    print(f"⚠️ Nou sistema de visualització ha fallat: {new_sys_error}")
                    # Continuar amb el fallback
            
            # FALLBACK: Visualització 3D directa amb PyVista
            print("🔄 Usant visualització 3D de PyVista (fallback)...")
            self._show_3d_results_with_pyvista()
                
        except Exception as e:
            print(f"Error en visualització 3D: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Error mostrant visualització 3D: {e}")
    
    def _show_3d_results_with_pyvista(self):
        """Mostra els resultats 3D amb PyVista com a fallback"""
        try:
            # Verificar que tenim les dades necessàries
            positions = self.optimization_results.get('positions', [])
            rotations = self.optimization_results.get('rotations', [])
            box_dims = self.optimization_results.get('box_dims', {})
            
            # Convertir box_dims a llista si és un dict
            if isinstance(box_dims, dict):
                dims = [box_dims.get('length', 100), box_dims.get('width', 100), box_dims.get('height', 100)]
            else:
                dims = list(box_dims) if hasattr(box_dims, '__iter__') else [100, 100, 100]
            
            if not positions:
                messagebox.showwarning("Avís", "No hi ha posicions per visualitzar.")
                return
            
            # Importar PyVista
            import pyvista as pv
            import numpy as np
            
            # Decidir quina malla usar per visualitzar
            mesh_to_show = self.simplified_mesh if (hasattr(self, 'simplified_mesh') and self.simplified_mesh is not None) else self.original_mesh
            if not mesh_to_show:
                print("❌ ERROR: No hi ha malla carregada per visualitzar")
                messagebox.showwarning("Avís", "No hi ha malla carregada per visualitzar")
                return
            
            print(f"🎮 Iniciant visualització 3D amb {len(positions)} objectes...")
            
            # Crear visualitzador
            plotter = pv.Plotter(window_size=(1000, 700))
            plotter.set_background('white')
            plotter.add_axes()
            plotter.show_grid()
            
            # Dibuixar el contenidor
            self._draw_container_wireframe_pyvista(plotter, dims)
            
            # Colors per les peces
            base_colors = [
                '#DC143C', '#1E90FF', '#228B22', '#FF8C00', '#9370DB',
                '#D2691E', '#FF1493', '#696969', '#808000', '#00CED1'
            ]
            colors = [base_colors[i % len(base_colors)] for i in range(len(positions))]
            
            # Dibuixar cada peça posicionada
            for i, (pos, rot) in enumerate(zip(positions, rotations)):
                color = colors[i]
                obj_id = i + 1
                
                # Clonar la malla base
                piece_mesh = mesh_to_show.copy()
                
                # Aplicar rotació si cal
                if any(angle != 0 for angle in rot):
                    rot_radians = [np.radians(angle) for angle in rot]
                    transform_matrix = trimesh.transformations.euler_matrix(rot_radians[0], rot_radians[1], rot_radians[2])
                    piece_mesh.apply_transform(transform_matrix)
                
                # Aplicar translació
                piece_mesh.apply_translation(pos)
                
                # Convertir a PyVista
                try:
                    faces_pv = np.column_stack(([3] * len(piece_mesh.faces), piece_mesh.faces)).flatten()
                    pv_mesh = pv.PolyData(piece_mesh.vertices, faces_pv)
                    plotter.add_mesh(pv_mesh, color=color, show_edges=False, opacity=0.8, name=f'obj_{obj_id}')
                except Exception as conv_error:
                    print(f"⚠️ Error convertint peça {obj_id} a PyVista: {conv_error}")
                    # Fallback: Dibuixar un cub simple
                    bounds = piece_mesh.bounds
                    if bounds is not None:
                        dims_piece = bounds[1] - bounds[0]
                        center = (bounds[1] + bounds[0]) / 2
                        corner_pos = center - dims_piece / 2
                        cube = pv.Cube(bounds=(corner_pos[0], corner_pos[0]+dims_piece[0],
                                              corner_pos[1], corner_pos[1]+dims_piece[1],
                                              corner_pos[2], corner_pos[2]+dims_piece[2]))
                        plotter.add_mesh(cube, color=color, opacity=0.8, name=f'obj_{obj_id}_fallback')
            
            # Configuració final i mostra
            plotter.add_text(f"Empaquetament 3D: {len(positions)} peces", position='upper_edge', font_size=12)
            plotter.camera_position = 'iso'
            print("✅ Preparada la visualització 3D")
            plotter.show(interactive=True, auto_close=False)
            print("✅ Visualització 3D tancada")
            
        except ImportError:
            error_msg = "PyVista no està instal·lat. Instal·la'l amb: pip install pyvista"
            print(f"❌ {error_msg}")
            messagebox.showerror("Error", error_msg)
        except Exception as e:
            error_msg = f"No s'ha pogut crear la visualització 3D: {e}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", error_msg)
    
    def _draw_container_wireframe_pyvista(self, plotter, dims):
        """Dibuixa el contenidor com a wireframe amb PyVista"""
        try:
            import pyvista as pv
            import numpy as np
            
            # Assegurar que dims és una llista de 3 elements
            dims = list(dims) if hasattr(dims, '__iter__') else [dims, dims, dims]
            if len(dims) < 3:
                dims.extend([100] * (3 - len(dims)))
            
            # Crear vèrtexs del cub contenidor
            vertices = np.array([
                [0, 0, 0], [dims[0], 0, 0], [dims[0], dims[1], 0], [0, dims[1], 0],  # Base inferior
                [0, 0, dims[2]], [dims[0], 0, dims[2]], [dims[0], dims[1], dims[2]], [0, dims[1], dims[2]]  # Base superior
            ])
            
            # Crear arestes (connexions entre vèrtexs)
            lines = np.array([
                [2, 0, 1], [2, 1, 2], [2, 2, 3], [2, 3, 0],  # Base inferior
                [2, 4, 5], [2, 5, 6], [2, 6, 7], [2, 7, 4],  # Base superior
                [2, 0, 4], [2, 1, 5], [2, 2, 6], [2, 3, 7]   # Arestes verticals
            ]).flatten()
            
            # Crear PolyData per les línies
            line_poly = pv.PolyData(vertices, lines)
            
            # Afegir al plotter
            plotter.add_mesh(line_poly, color='black', line_width=3, opacity=0.7, name='container_box')
            print("✅ Contenidor wireframe dibuixat (PyVista)")
        except Exception as e:
            print(f"❌ Error dibuixant contenidor (PyVista): {e}")
    
    def _perform_export_traditional(self):
        """Exportació tradicional (fallback)"""
        # Implementar exportació tradicional si cal
        messagebox.showinfo("Info", "Usant sistema d'exportació tradicional")
    
    def run(self):
        """Inicia l'aplicació"""
        self.root.mainloop()

    def start_advanced_optimization(self):
        """Inicia l'optimització avançada unificada"""
        if not hasattr(self, 'original_mesh') or self.original_mesh is None:
            messagebox.showerror("Error", "Primer has de carregar una peça STL")
            return
        
        try:
            # Dimensions de la caixa
            box_dims = [
                float(self.box_length.get()),
                float(self.box_width.get()),
                float(self.box_height.get())
            ]
            
            # Configuració avançada
            max_pieces = None
            if self.limit_pieces.get():
                max_pieces = int(self.max_pieces_var.get())
            
            iterations = 100  # Valor fix, ja no configurable per l'usuari
            use_floor_mode = self.use_floor_mode.get()
            margin = float(self.margin_var.get()) if use_floor_mode else 0.0
            floor_separation = float(self.floor_separation.get()) if use_floor_mode else 0.0
            
            self.progress.config(mode='determinate', value=0)
            self.optimize_btn.config(state='disabled')
            self.progress_label.config(text="Iniciant optimització avançada...")
            
            # Decidir quina malla usar per visualització (sempre STL simplificat si està disponible)
            mesh_for_calculation = self.original_mesh  # Sempre original per càlculs
            mesh_for_visualization = self.simplified_mesh if (hasattr(self, 'simplified_mesh') and 
                                                           self.simplified_mesh is not None) else self.original_mesh
            
            # Executar optimització en fil separat per no bloquejar la UI
            import threading
            
            def optimization_worker():
                try:
                    self.root.after(0, lambda: self.progress_label.config(text="Analitzant geometria STL..."))
                    
                    result = self._unified_advanced_optimization(
                        mesh_for_calculation, box_dims,
                        max_pieces=max_pieces,
                        iterations=iterations,
                        use_floor_mode=use_floor_mode,
                        margin=margin,
                        floor_separation=floor_separation,
                        mesh_for_visualization=mesh_for_visualization,
                        progress_callback=self._update_progress
                    )
                    
                    self.root.after(0, lambda: self._finish_optimization(result))
                    
                except Exception as e:
                    self.root.after(0, lambda: self._handle_optimization_error(str(e)))
            
            thread = threading.Thread(target=optimization_worker, daemon=True)
            thread.start()
            
        except ValueError as e:
            messagebox.showerror("Error", f"Paràmetres invàlids: {str(e)}")
            self.optimize_btn.config(state='normal')
        except Exception as e:
            messagebox.showerror("Error", f"Error durant l'optimització: {str(e)}")
            self.optimize_btn.config(state='normal')
    
    def _update_progress(self, percentage, message):
        """Actualitza la barra de progrés i el missatge"""
        self.root.after(0, lambda: self.progress.config(value=percentage))
        self.root.after(0, lambda: self.progress_label.config(text=message))
    
    def _finish_optimization(self, result):
        """Finalitza l'optimització amb els resultats"""
        self.optimize_btn.config(state='normal')
        self.progress.config(value=100)
        
        if result:
            # IMPORTANT: Guardar els resultats per poder visualitzar-los després
            self.optimization_results = result
            
            self.progress_label.config(text="Optimització completada amb èxit!")
            self.show_unified_optimization_results(result)
            
            # Activar botons de visualització i exportació
            if hasattr(self, 'viz_direct_btn'):
                self.viz_direct_btn.config(state='normal')
            if hasattr(self, 'viz_options_btn'):
                self.viz_options_btn.config(state='normal')
            if hasattr(self, 'export_btn'):
                self.export_btn.config(state='normal')
            
            print(f"✅ Resultats guardats: {len(result.get('positions', []))} peces col·locades")
        else:
            self.progress_label.config(text="No s'ha trobat solució òptima")
            messagebox.showerror("Error", "No s'ha pogut trobar una solució d'empaquetament òptima")
    
    def _handle_optimization_error(self, error_msg):
        """Gestiona errors durant l'optimització"""
        self.optimize_btn.config(state='normal')
        self.progress.config(value=0)
        self.progress_label.config(text="Error durant l'optimització")
        messagebox.showerror("Error", f"Error durant l'optimització: {error_msg}")

    def _unified_advanced_optimization(self, mesh, box_dims, max_pieces=None, iterations=100, 
                                     use_floor_mode=True, margin=2.0, floor_separation=10.0, 
                                     mesh_for_visualization=None, progress_callback=None):
        """Optimització unificada amb mode pisos o mode a granel (versió simplificada)"""
        import time
        start_time = time.time()
        
        try:
            if progress_callback:
                mode_name = "PISOS ORDENATS" if use_floor_mode else "A GRANEL"
                progress_callback(5, f"Iniciant mode {mode_name}...")
            
            # Convertir box_dims si és llista
            if isinstance(box_dims, list):
                box_dims = {
                    'length': box_dims[0],
                    'width': box_dims[1], 
                    'height': box_dims[2]
                }
            
            # Simulació d'optimització (versió de placeholders per evitar dependències complexes)
            if progress_callback:
                progress_callback(25, "Analitzant geometria...")
            
            # Calcular bounding box de l'objecte
            bounds = mesh.bounds
            obj_dims = {
                'length': bounds[1][0] - bounds[0][0] + (margin * 2 if use_floor_mode else 0),
                'width': bounds[1][1] - bounds[0][1] + (margin * 2 if use_floor_mode else 0),
                'height': bounds[1][2] - bounds[0][2] + (margin * 2 if use_floor_mode else 0)
            }
            
            if progress_callback:
                progress_callback(50, "Calculant distribució...")
            
            # Simulació de càlcul de peces que caben
            if use_floor_mode:
                floor_height = obj_dims['height'] + floor_separation
                max_floors = max(1, int(box_dims['height'] / floor_height))
                pieces_per_row = max(1, int(box_dims['length'] / obj_dims['length']))
                pieces_per_column = max(1, int(box_dims['width'] / obj_dims['width']))
                pieces_per_floor = pieces_per_row * pieces_per_column
                total_possible = pieces_per_floor * max_floors
            else:
                # Mode a granel - càlcul més complex, simulem
                max_floors = 1
                pieces_per_row = max(1, int(box_dims['length'] / obj_dims['length']))
                pieces_per_column = max(1, int(box_dims['width'] / obj_dims['width']))
                pieces_per_floor = pieces_per_row * pieces_per_column
                total_possible = max(1, int((box_dims['length'] * box_dims['width'] * box_dims['height']) / 
                                          (obj_dims['length'] * obj_dims['width'] * obj_dims['height']) * 0.7))
            
            if max_pieces:
                total_to_place = min(total_possible, max_pieces)
            else:
                total_to_place = total_possible
                
            if progress_callback:
                progress_callback(75, f"Generant {total_to_place} posicions...")
            
            # Generar posicions simplificades
            positions = []
            for i in range(total_to_place):
                # Posicions simulades en graella
                row = i % pieces_per_row if use_floor_mode else i % int(box_dims['length'] / obj_dims['length'])
                col = (i // pieces_per_row) % pieces_per_column if use_floor_mode else (i // int(box_dims['length'] / obj_dims['length'])) % int(box_dims['width'] / obj_dims['width'])
                floor_level = i // (pieces_per_floor) if use_floor_mode else i // (int(box_dims['length'] / obj_dims['length']) * int(box_dims['width'] / obj_dims['width']))
                
                x = row * obj_dims['length'] + obj_dims['length'] / 2
                y = col * obj_dims['width'] + obj_dims['width'] / 2  
                z = floor_level * (obj_dims['height'] + floor_separation) + obj_dims['height'] / 2 if use_floor_mode else (floor_level * obj_dims['height'] + obj_dims['height'] / 2)
                
                positions.append([x, y, z])
            
            if progress_callback:
                progress_callback(90, "Finalitzant...")
            
            # Crear resultat simplificat
            total_time = time.time() - start_time
            efficiency = min(1.0, (total_to_place * obj_dims['length'] * obj_dims['width'] * obj_dims['height']) / 
                            (box_dims['length'] * box_dims['width'] * box_dims['height']))
            
            result = {
                'positions': positions,
                'rotations': [[0, 0, 0]] * len(positions),  # Sense rotacions per simplicitat
                'efficiency': efficiency,
                'method': 'PISOS ORDENATS' if use_floor_mode else 'A GRANEL',
                'box_dims': box_dims,
                'obj_dims': obj_dims,
                'margin': margin,
                'floor_separation': floor_separation,
                'total_floors': max_floors if use_floor_mode else 1,
                'pieces_per_floor': pieces_per_floor if use_floor_mode else total_to_place,
                'optimization_info': {
                    'max_pieces': max_pieces,
                    'iterations': iterations,
                    'total_time': total_time,
                    'margin': margin,
                    'floor_separation': floor_separation
                }
            }
            
            if progress_callback:
                progress_callback(100, "Optimització completada!")
            
            print(f"✅ Optimització completada: {len(positions)} peces en {total_time:.2f}s")
            return result
                
        except Exception as e:
            print(f"❌ Error en optimització unificada: {str(e)}")
            if progress_callback:
                progress_callback(0, f"Error: {str(e)}")
            return None

    def show_unified_optimization_results(self, result):
        """Mostra els resultats de l'optimització unificada"""
        try:
            self.results_text.config(state='normal')
            self.results_text.delete(1.0, tk.END)
            
            if not result:
                self.results_text.insert(tk.END, "❌ No s'han obtingut resultats vàlids\n")
                self.results_text.config(state='disabled')
                return
            
            # Informació general
            positions = result.get('positions', [])
            optimization_info = result.get('optimization_info', {})
            
            self.results_text.insert(tk.END, "🏆 RESULTATS OPTIMITZACIÓ AVANÇADA\n")
            self.results_text.insert(tk.END, "=" * 50 + "\n\n")
            
            # Resum principal
            self.results_text.insert(tk.END, f"📊 RESUM PRINCIPAL:\n")
            self.results_text.insert(tk.END, f"   • Peces empaquetades: {len(positions)}\n")
            self.results_text.insert(tk.END, f"   • Mètode: {result.get('method', 'Desconegut')}\n")
            self.results_text.insert(tk.END, f"   • Temps total: {optimization_info.get('total_time', 0):.2f} segons\n\n")
            
            # Eficiència
            efficiency = result.get('efficiency', 0) * 100
            self.results_text.insert(tk.END, f"⚡ EFICIÈNCIA: {efficiency:.1f}% del volum total\n\n")
            
            # Dimensions
            box_dims = result.get('box_dims', {})
            obj_dims = result.get('obj_dims', {})
            
            self.results_text.insert(tk.END, f"📦 DIMENSIONS:\n")
            self.results_text.insert(tk.END, f"   • Contenidor: {box_dims.get('length', 0):.1f} × {box_dims.get('width', 0):.1f} × {box_dims.get('height', 0):.1f} mm\n")
            self.results_text.insert(tk.END, f"   • Objecte: {obj_dims.get('length', 0):.1f} × {obj_dims.get('width', 0):.1f} × {obj_dims.get('height', 0):.1f} mm\n\n")
            
            # Configuració específica segons el mode
            if result.get('method') == 'PISOS ORDENATS':
                self.results_text.insert(tk.END, f"🏢 CONFIGURACIÓ PISOS:\n")
                self.results_text.insert(tk.END, f"   • Pisos utilitzats: {result.get('total_floors', 1)}\n")
                self.results_text.insert(tk.END, f"   • Peces per pis: {result.get('pieces_per_floor', len(positions))}\n")
                self.results_text.insert(tk.END, f"   • Marge aplicat: {result.get('margin', 0)}mm\n")
                self.results_text.insert(tk.END, f"   • Separació pisos: {result.get('floor_separation', 0)}mm\n\n")
            
            # Acció següent
            self.results_text.insert(tk.END, "🎯 SEGÜENTS PASSOS:\n")
            self.results_text.insert(tk.END, "   • Vés a la pestanya 'Visualitzar' per veure els resultats en 3D\n")
            self.results_text.insert(tk.END, "   • Utilitza les opcions d'exportació per guardar els resultats\n")
            
            self.results_text.config(state='disabled')
            
        except Exception as e:
            print(f"Error mostrant resultats: {e}")
            self.results_text.insert(tk.END, f"Error mostrant resultats: {e}\n")
            self.results_text.config(state='disabled')


def main():
    """Funció principal"""
    try:
        app = PackAssistOriginalGUI()
        app.run()
    except Exception as e:
        print(f"Error iniciant l'aplicació: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
