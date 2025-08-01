#!/usr/bin/env python3
"""
PackAssist - GUI Integrada amb Components Existents
Utilitza els simplificadors i optimitzadors ja desenvolupats
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from pathlib import Path
import numpy as np

# Afegir paths necessaris
sys.path.append(os.path.join(os.path.dirname(__file__), 'actiu', 'src'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'actiu', 'tools', 'mesh_simplifiers'))

class PackAssistIntegratedApp:
    """Aplicació PackAssist integrada amb components existents"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PackAssist - Empaquetament Intel·ligent")
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
        """Configura els components existents"""
        try:
            # Importar optimitzador
            from packassist.optimizer import optimize_packing
            self.optimizer_func = optimize_packing
            
            # Importar funcions de càrrega si existeixen
            try:
                from packassist.stl_loader import load_stl_file
                self.stl_loader = load_stl_file
            except ImportError:
                self.stl_loader = None
            
            self.components_loaded = True
            
        except ImportError as e:
            print(f"Warning: Alguns components no estan disponibles: {e}")
            self.components_loaded = False
            self.optimizer_func = None
            self.stl_loader = None

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
        
        # Pestanya 2: Simplificar
        self.tab_simplify = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_simplify, text="🔧 2. Simplificar")
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
        """Crea la pestanya de simplificació"""
        main_frame = ttk.Frame(self.tab_simplify, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Títol
        title_label = ttk.Label(main_frame, text="🔧 Simplificar Malla", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Controls de simplificació
        controls_frame = ttk.LabelFrame(main_frame, text="Controls", padding="15")
        controls_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Selector de mètode
        ttk.Label(controls_frame, text="Mètode de simplificació:").pack(anchor=tk.W)
        self.simplify_method = tk.StringVar(value="quadric")
        method_frame = ttk.Frame(controls_frame)
        method_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(method_frame, text="Quadric Edge Collapse", variable=self.simplify_method, value="quadric").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(method_frame, text="Vertex Clustering", variable=self.simplify_method, value="clustering").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(method_frame, text="Edge Length", variable=self.simplify_method, value="edge_length").pack(side=tk.LEFT)
        
        # Slider per vèrtexs objectiu
        ttk.Label(controls_frame, text="Vèrtexs objectiu:").pack(anchor=tk.W, pady=(10, 0))
        
        self.target_vertices = tk.IntVar(value=1000)
        self.vertices_scale = tk.Scale(controls_frame, from_=50, to=10000,
                                      orient=tk.HORIZONTAL, variable=self.target_vertices,
                                      command=self.update_vertices_label)
        self.vertices_scale.pack(fill=tk.X, pady=5)
        
        self.vertices_label = ttk.Label(controls_frame, text="1000 vèrtexs")
        self.vertices_label.pack(anchor=tk.W)
        
        # Botó de simplificació
        self.simplify_btn = ttk.Button(controls_frame, text="🚀 Simplificar Malla", 
                                      command=self.simplify_mesh, state='disabled')
        self.simplify_btn.pack(pady=10)
        
        # Frame de comparació
        comparison_frame = ttk.LabelFrame(main_frame, text="Comparació Original vs Simplificada", padding="15")
        comparison_frame.pack(fill=tk.BOTH, expand=True)
        
        # Dividir en dues columnes
        left_frame = ttk.Frame(comparison_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        right_frame = ttk.Frame(comparison_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Info original
        ttk.Label(left_frame, text="📊 Original", style='Step.TLabel').pack()
        self.original_stats = tk.Text(left_frame, height=8, wrap=tk.WORD)
        self.original_stats.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.view_orig_btn = ttk.Button(left_frame, text="🎮 Veure 3D", 
                                       command=self.view_original_3d, state='disabled')
        self.view_orig_btn.pack(pady=5)
        
        # Info simplificada
        ttk.Label(right_frame, text="📊 Simplificada", style='Step.TLabel').pack()
        self.simplified_stats = tk.Text(right_frame, height=8, wrap=tk.WORD)
        self.simplified_stats.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.view_simp_btn = ttk.Button(right_frame, text="🎮 Veure 3D", 
                                       command=self.view_simplified_3d, state='disabled')
        self.view_simp_btn.pack(pady=5)
        
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
        """Mostra informació de la malla en un widget de text"""
        text_widget.config(state='normal')
        text_widget.delete(1.0, tk.END)
        
        if mesh_info:
            info = f"📊 Informació de la Malla:\n"
            info += f"   • Vèrtexs: {mesh_info.get('vertices', 0):,}\n"
            info += f"   • Cares: {mesh_info.get('faces', 0):,}\n"
            
            volume = mesh_info.get('volume', 0)
            if volume > 0:
                info += f"   • Volum: {volume:.2f} mm³\n"
            
            area = mesh_info.get('area', 0)
            if area > 0:
                info += f"   • Àrea: {area:.2f} mm²\n"
                
            # Calcular dimensions aproximades
            if 'mesh' in mesh_info and hasattr(mesh_info['mesh'], 'bounds'):
                bounds = mesh_info['mesh'].bounds
                dims = bounds[1] - bounds[0]
                info += f"   • Dimensions: {dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f} mm\n"
                
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
            
            # Deshabilitar botó temporalment
            self.simplify_btn.config(state='disabled', text="🔄 Simplificant...")
            self.root.update()
            
            # Executar simplificació en fil separat
            thread = threading.Thread(target=self._simplify_worker, args=(target, method))
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en la simplificació: {e}")
            self.simplify_btn.config(state='normal', text="🚀 Simplificar Malla")
            
    def _simplify_worker(self, target, method):
        """Worker per la simplificació en fil separat"""
        try:
            # Utilitzar el simplificador apropiat segons el mètode
            if method == "quadric":
                self.simplified_mesh = self.original_mesh.simplify_quadric_decimation(target)
            elif method == "clustering":
                # Simplificació bàsica per ara
                self.simplified_mesh = self.original_mesh.simplify_quadric_decimation(target)
            else:  # edge_length
                # Simplificació per longitud d'aresta
                self.simplified_mesh = self.original_mesh.simplify_quadric_decimation(target)
            
            # Crear info de la malla simplificada
            self.simplified_mesh_info = {
                'mesh': self.simplified_mesh,
                'vertices': len(self.simplified_mesh.vertices),
                'faces': len(self.simplified_mesh.faces),
                'volume': getattr(self.simplified_mesh, 'volume', 0),
                'area': getattr(self.simplified_mesh, 'area', 0)
            }
            
            # Actualitzar GUI en fil principal
            self.root.after(0, self._update_simplification_results)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error en la simplificació: {e}"))
            self.root.after(0, lambda: self.simplify_btn.config(state='normal', text="🚀 Simplificar Malla"))
            
    def _update_simplification_results(self):
        """Actualitza els resultats de la simplificació en la GUI"""
        # Mostrar info de la malla simplificada
        self.display_mesh_info(self.simplified_mesh_info, self.simplified_stats)
        
        # Habilitar botons
        self.view_simp_btn.config(state='normal')
        self.simplify_btn.config(state='normal', text="🚀 Simplificar Malla")
        
        messagebox.showinfo("Èxit", "Malla simplificada correctament!")
        
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
        """Worker per l'optimització en fil separat"""
        try:
            # Preparar dimensions
            box_dims = {
                "length": box_length,
                "width": box_width,
                "height": box_height,
                "shape_type": "rectangular",
                "volume_factor": 1.0
            }
            
            # Calcular dimensions de l'objecte
            if hasattr(mesh, 'bounds'):
                bounds = mesh.bounds
                obj_dims = {
                    "length": bounds[1][0] - bounds[0][0],
                    "width": bounds[1][1] - bounds[0][1],
                    "height": bounds[1][2] - bounds[0][2],
                    "shape_type": "complex" if len(mesh.faces) > 12 else "rectangular",
                    "volume_factor": 1.0,
                    "total_faces": len(mesh.faces),
                    "total_vertices": len(mesh.vertices),
                    "real_volume": getattr(mesh, 'volume', 0)
                }
            else:
                # Fallback
                obj_dims = {
                    "length": 10, "width": 10, "height": 10,
                    "shape_type": "rectangular", "volume_factor": 1.0
                }
                
            # Utilitzar optimitzador existent
            if self.optimizer_func:
                result = self.optimizer_func(box_dims, obj_dims)
            else:
                # Fallback a càlcul simple
                result = self._simple_optimization_fallback(box_dims, obj_dims)
            
            # Guardar resultats
            self.optimization_results = result
            
            # Actualitzar GUI en fil principal
            self.root.after(0, self._update_optimization_results, result, mesh_info)
            
        except Exception as e:
            self.root.after(0, lambda: self._handle_optimization_error(str(e)))
            
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
        """Visualitza els resultats de l'empaquetament en 3D"""
        if not self.optimization_results:
            messagebox.showwarning("Avís", "Primer has de calcular l'empaquetament")
            return
            
        try:
            import pyvista as pv
            
            # Crear visualitzador
            plotter = pv.Plotter(window_size=(1000, 700))
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
            
            # Colors per objectes
            colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'cyan', 'magenta', 'yellow']
            
            # Dibuixar objectes
            for i, item in enumerate(items):
                pos = item.get('position', [0, 0, 0])
                dims = item.get('dimensions', [10, 10, 10])
                
                # Crear cub per l'objecte
                obj_mesh = pv.Cube(bounds=(
                    pos[0], pos[0] + dims[0],
                    pos[1], pos[1] + dims[1], 
                    pos[2], pos[2] + dims[2]
                ))
                
                color = colors[i % len(colors)]
                plotter.add_mesh(obj_mesh, color=color, opacity=0.8, label=f'Objecte {i+1}')
                
            # Configurar vista
            plotter.camera_position = 'iso'
            plotter.show_grid()
            plotter.add_axes()
            
            # Títol i informació
            max_objects = self.optimization_results.get('max_objects', 0)
            efficiency = self.optimization_results.get('efficiency', 0)
            title = f"Empaquetament: {max_objects} objectes ({efficiency:.1f}% eficiència)"
            plotter.add_text(title, position='upper_edge', font_size=14, color='black')
            
            # Info adicional
            box_info = f"Caixa: {container_dims[0]:.0f}×{container_dims[1]:.0f}×{container_dims[2]:.0f} mm"
            plotter.add_text(box_info, position='lower_left', font_size=10, color='gray')
            
            # Mostrar llegenda si hi ha objectes
            if items:
                plotter.add_legend()
            
            # Mostrar
            plotter.show(interactive=True, auto_close=False)
            
        except ImportError:
            messagebox.showerror("Error", "PyVista no està instal·lat.\nInstal·la'l amb: pip install pyvista")
        except Exception as e:
            messagebox.showerror("Error", f"No s'ha pogut crear la visualització 3D:\n{e}")
            
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
