"""
PackAssist 3D - Versió Millorada
Sistema avançat d'optimització de bin packing amb visualització 3D
Basat en la versió estable amb millores estètiques i funcionals
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import traceback
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
import sys
import os
import csv

# Afegir el directori src al path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Importar el widget del simplificador STL ultra-ràpid
from stl_simplifier_widget import create_stl_simplifier_tab

from src.packassist import (
    get_stp_dimensions, 
    validate_stp_file, 
    optimize_packing, 
    calculate_theoretical_max, 
    calculate_grid_packing
)

# Import del sistema de geometria avançada
from src.packassist.advanced_geometry import ComplexGeometry

# Constants
CSV_PATH = "data/index.csv"

class ModernPackAssistGUI:
    """Interfície gràfica moderna i millorada per PackAssist 3D."""
    
    def __init__(self, root):
        """Inicialitza la interfície gràfica moderna."""
        self.root = root
        self.root.title("PackAssist 3D Pro - Optimitzador Avançat de Bin Packing")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)
        
        # Variables de control
        self.is_processing = False
        self.metadata = []
        self.optimization_results = None
        self.current_viz_window = None
        
        # Configurar sistema de ComplexGeometry amb simplificació de malla
        self.geometry_analyzer = ComplexGeometry()
        self.geometry_analyzer.initialize_mesh_simplification()
        
        # Configurar tema modern
        self._setup_modern_theme()
        
        # Crear interfície
        self._create_modern_interface()
        
        # Carregar dades inicials
        self._load_initial_data()

    def _setup_modern_theme(self):
        """Configura un tema modern i elegant."""
        style = ttk.Style()
        
        # Utilitzar tema modern disponible
        available_themes = style.theme_names()
        if 'vista' in available_themes:
            style.theme_use('vista')
        elif 'xpnative' in available_themes:
            style.theme_use('xpnative')
        else:
            style.theme_use('clam')
        
        # Colors moderns
        self.colors = {
            'primary': '#2E3440',
            'secondary': '#3B4252', 
            'accent': '#5E81AC',
            'success': '#A3BE8C',
            'warning': '#EBCB8B',
            'danger': '#BF616A',
            'light': '#ECEFF4',
            'medium': '#D8DEE9',
            'dark': '#4C566A'
        }
        
        # Configurar estils personalitzats
        style.configure('Title.TLabel', 
                       font=('Segoe UI', 16, 'bold'),
                       foreground=self.colors['primary'])
        
        style.configure('Header.TLabel', 
                       font=('Segoe UI', 12, 'bold'),
                       foreground=self.colors['secondary'])
        
        style.configure('Modern.TButton',
                       font=('Segoe UI', 10),
                       padding=(10, 5))
        
        style.configure('Success.TButton',
                       font=('Segoe UI', 10, 'bold'))
        
        # Configurar finestra principal
        self.root.configure(bg=self.colors['light'])

    def _create_modern_interface(self):
        """Crea la interfície moderna amb millor organització."""
        # Frame principal amb padding elegant
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Títol principal
        title_frame = ttk.Frame(main_container)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(title_frame, 
                 text="PackAssist 3D Pro", 
                 style='Title.TLabel').pack(side=tk.LEFT)
        
        ttk.Label(title_frame,
                 text="Optimitzador Avançat de Bin Packing",
                 font=('Segoe UI', 11),
                 foreground=self.colors['dark']).pack(side=tk.LEFT, padx=(10, 0))
        
        # Notebook amb pestanyes modernes
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Pestanya 1: Càlcul Manual
        self._create_manual_tab()
        
        # Pestanya 2: Simplificador STL Ultra-ràpid ⚡
        self._create_stl_simplifier_tab()
        
        # Pestanya 3: Gestió de Fitxers STP
        self._create_files_tab()
        
        # Pestanya 4: Resultats i Visualització
        self._create_results_tab()
        
        # Barra d'estat moderna
        self._create_modern_statusbar(main_container)

    def _create_manual_tab(self):
        """Crea la pestanya de càlcul manual amb disseny modern."""
        manual_frame = ttk.Frame(self.notebook)
        self.notebook.add(manual_frame, text="  Càlcul Manual  ")
        
        # Contenidor amb scroll
        canvas = tk.Canvas(manual_frame, bg=self.colors['light'])
        scrollbar = ttk.Scrollbar(manual_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Configurar dimensions del contenidor
        self._create_container_section(scrollable_frame)
        
        # Configurar dimensions de l'objecte
        self._create_object_section(scrollable_frame)
        
        # Secció de resultats
        self._create_calculation_results_section(scrollable_frame)

    def _create_container_section(self, parent):
        """Crea la secció de configuració del contenidor."""
        container_frame = ttk.LabelFrame(parent, text="  Dimensions del Contenidor (mm)  ", padding="15")
        container_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Grid layout per les dimensions
        dims_frame = ttk.Frame(container_frame)
        dims_frame.pack(fill=tk.X)
        
        # Longitud
        ttk.Label(dims_frame, text="Longitud:", font=('Segoe UI', 10)).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.box_length = tk.StringVar(value="2500")
        length_entry = ttk.Entry(dims_frame, textvariable=self.box_length, font=('Segoe UI', 10), width=12)
        length_entry.grid(row=0, column=1, padx=(0, 20))
        
        # Amplada
        ttk.Label(dims_frame, text="Amplada:", font=('Segoe UI', 10)).grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.box_width = tk.StringVar(value="1500")
        width_entry = ttk.Entry(dims_frame, textvariable=self.box_width, font=('Segoe UI', 10), width=12)
        width_entry.grid(row=0, column=3, padx=(0, 20))
        
        # Altura
        ttk.Label(dims_frame, text="Altura:", font=('Segoe UI', 10)).grid(row=0, column=4, sticky=tk.W, padx=(0, 10))
        self.box_height = tk.StringVar(value="1000")
        height_entry = ttk.Entry(dims_frame, textvariable=self.box_height, font=('Segoe UI', 10), width=12)
        height_entry.grid(row=0, column=5)

    def _create_object_section(self, parent):
        """Crea la secció de configuració de l'objecte."""
        object_frame = ttk.LabelFrame(parent, text="  Dimensions de l'Objecte (mm)  ", padding="15")
        object_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Opcions d'entrada
        input_frame = ttk.Frame(object_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.input_method = tk.StringVar(value="manual")
        
        ttk.Radiobutton(input_frame, text="Entrada Manual", 
                       variable=self.input_method, value="manual",
                       command=self._toggle_input_method).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Radiobutton(input_frame, text="Seleccionar des de Fitxers STP", 
                       variable=self.input_method, value="file",
                       command=self._toggle_input_method).pack(side=tk.LEFT)
        
        # Frame per entrada manual
        self.manual_entry_frame = ttk.Frame(object_frame)
        self.manual_entry_frame.pack(fill=tk.X, pady=(10, 0))
        
        dims_frame = ttk.Frame(self.manual_entry_frame)
        dims_frame.pack(fill=tk.X)
        
        # Dimensions manuals
        ttk.Label(dims_frame, text="Longitud:", font=('Segoe UI', 10)).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.obj_length = tk.StringVar(value="200")
        ttk.Entry(dims_frame, textvariable=self.obj_length, font=('Segoe UI', 10), width=12).grid(row=0, column=1, padx=(0, 20))
        
        ttk.Label(dims_frame, text="Amplada:", font=('Segoe UI', 10)).grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.obj_width = tk.StringVar(value="150")
        ttk.Entry(dims_frame, textvariable=self.obj_width, font=('Segoe UI', 10), width=12).grid(row=0, column=3, padx=(0, 20))
        
        ttk.Label(dims_frame, text="Altura:", font=('Segoe UI', 10)).grid(row=0, column=4, sticky=tk.W, padx=(0, 10))
        self.obj_height = tk.StringVar(value="100")
        ttk.Entry(dims_frame, textvariable=self.obj_height, font=('Segoe UI', 10), width=12).grid(row=0, column=5)
        
        # Frame per selecció de fitxer
        self.file_entry_frame = ttk.Frame(object_frame)
        
        file_select_frame = ttk.Frame(self.file_entry_frame)
        file_select_frame.pack(fill=tk.X)
        
        ttk.Label(file_select_frame, text="Seleccionar Objecte:", font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        self.object_combo = ttk.Combobox(file_select_frame, width=40, font=('Segoe UI', 10))
        self.object_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.object_combo.bind('<<ComboboxSelected>>', self._on_object_selected)
        
        ttk.Button(file_select_frame, text="Actualitzar Llista", 
                  command=self._update_object_combo, style='Modern.TButton').pack(side=tk.LEFT)
        
        # Botó de càlcul
        calc_frame = ttk.Frame(object_frame)
        calc_frame.pack(fill=tk.X, pady=(15, 0))
        
        calc_button = ttk.Button(calc_frame, text="Calcular Empaquetament", 
                               command=self.calculate_manual, style='Success.TButton')
        calc_button.pack(pady=10)

    def _create_calculation_results_section(self, parent):
        """Crea la secció de resultats del càlcul."""
        results_frame = ttk.LabelFrame(parent, text="  Resultats del Càlcul  ", padding="15")
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        # Text widget amb scroll per mostrar resultats
        text_frame = ttk.Frame(results_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.results_text = tk.Text(text_frame, 
                                   wrap=tk.WORD, 
                                   font=('Consolas', 10),
                                   bg='white',
                                   relief='sunken',
                                   borderwidth=1)
        
        results_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=results_scrollbar.set)
        
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Missatge inicial
        welcome_msg = """Benvingut a PackAssist 3D Pro!

Aquest sistema avançat d'optimització de bin packing us permet:

• Calcular empaquetament òptim per objectes simples i complexos
• Visualitzar resultats en 3D amb alta qualitat
• Gestionar fitxers STP amb geometries avançades
• Exportar resultats detallats

Per començar:
1. Configureu les dimensions del contenidor
2. Introduïu les dimensions de l'objecte (manual o des de fitxer STP)
3. Premeu 'Calcular Empaquetament'
4. Visualitzeu els resultats a la pestanya 'Resultats'

El sistema detectarà automàticament si l'objecte té geometria complexa i aplicarà
l'algorisme d'optimització més adequat.
"""
        self.results_text.insert(tk.END, welcome_msg)
        self.results_text.config(state=tk.DISABLED)

    def _create_stl_simplifier_tab(self):
        """Crea la pestanya del simplificador STL ultra-ràpid."""
        try:
            stl_frame, simplifier_widget = create_stl_simplifier_tab(self.notebook)
            self.stl_simplifier_widget = simplifier_widget
        except Exception as e:
            # Si hi ha error, crear pestanya bàsica amb missatge d'error
            stl_frame = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(stl_frame, text="⚡ Simplificador STL")
            
            error_label = ttk.Label(stl_frame, 
                text=f"Error carregant simplificador STL ultra-ràpid:\n{str(e)}\n\nAssegura't que els fitxers necessaris existeixen:\n• ultra_fast_mesh_simplifier.py\n• stl_simplifier_widget.py",
                foreground='red', 
                justify=tk.CENTER,
                font=('Arial', 10))
            error_label.pack(expand=True)
            print(f"Error carregant simplificador STL: {e}")

    def _create_files_tab(self):
        """Crea la pestanya de gestió de fitxers STP."""
        stp_frame = ttk.Frame(self.notebook)
        self.notebook.add(stp_frame, text="  Fitxers STP  ")
        
        # Controls superiors
        controls_frame = ttk.Frame(stp_frame)
        controls_frame.pack(fill=tk.X, padx=15, pady=15)
        
        ttk.Button(controls_frame, text="Actualitzar Llista", 
                  command=self.reload_metadata, style='Modern.TButton').pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(controls_frame, text="Afegir Fitxer", 
                  command=self.add_csv_entry, style='Modern.TButton').pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(controls_frame, text="Editar Seleccionat", 
                  command=self.edit_selected_item, style='Modern.TButton').pack(side=tk.LEFT, padx=(0, 10))
        
        # NOVA FUNCIONALITAT: Botó de simplificació de malla
        ttk.Button(controls_frame, text="Simplificar Malla", 
                  command=self.open_mesh_simplification, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(controls_frame, text="Guardar Canvis", 
                  command=self.save_csv_data, style='Success.TButton').pack(side=tk.RIGHT)
        
        # Taula de fitxers
        table_frame = ttk.Frame(stp_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # Crear Treeview amb estil modern
        columns = ("nom", "tipus", "dimensions", "complexitat", "estat")
        self.file_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        
        # Configurar columnes
        self.file_tree.heading("nom", text="Nom del Fitxer")
        self.file_tree.heading("tipus", text="Tipus")
        self.file_tree.heading("dimensions", text="Dimensions (L×A×H mm)")
        self.file_tree.heading("complexitat", text="Complexitat")
        self.file_tree.heading("estat", text="Estat")
        
        self.file_tree.column("nom", width=250)
        self.file_tree.column("tipus", width=80)
        self.file_tree.column("dimensions", width=180)
        self.file_tree.column("complexitat", width=120)
        self.file_tree.column("estat", width=120)
        
        # Event de doble clic per obrir simplificació
        self.file_tree.bind("<Double-1>", self.on_file_double_click)
        
        # Scrollbars
        tree_scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        tree_scrollbar_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.file_tree.xview)
        
        self.file_tree.configure(yscrollcommand=tree_scrollbar_y.set, xscrollcommand=tree_scrollbar_x.set)
        
        # Pack treeview i scrollbars
        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

    def _create_results_tab(self):
        """Crea la pestanya de resultats i visualització."""
        results_frame = ttk.Frame(self.notebook)
        self.notebook.add(results_frame, text="  Resultats i Visualització  ")
        
        # Controls de visualització
        viz_controls = ttk.LabelFrame(results_frame, text="  Controls de Visualització  ", padding="10")
        viz_controls.pack(fill=tk.X, padx=15, pady=15)
        
        controls_grid = ttk.Frame(viz_controls)
        controls_grid.pack(fill=tk.X)
        
        self.visualize_btn = ttk.Button(controls_grid, text="Generar Visualització 3D", 
                                       command=self.visualize_packing, 
                                       style='Success.TButton', state=tk.DISABLED)
        self.visualize_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(controls_grid, text="Exportar Resultats", 
                  command=self.export_results, style='Modern.TButton').pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(controls_grid, text="Guardar Configuració", 
                  command=self._save_configuration, style='Modern.TButton').pack(side=tk.RIGHT)
        
        # Àrea de resultats detallats
        details_frame = ttk.LabelFrame(results_frame, text="  Resultats Detallats  ", padding="10")
        details_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # Text widget per resultats amb format millorat
        results_container = ttk.Frame(details_frame)
        results_container.pack(fill=tk.BOTH, expand=True)
        
        self.detailed_results_text = tk.Text(results_container,
                                           wrap=tk.WORD,
                                           font=('Consolas', 10),
                                           bg='white',
                                           relief='sunken',
                                           borderwidth=1)
        
        detailed_scrollbar = ttk.Scrollbar(results_container, orient=tk.VERTICAL, 
                                         command=self.detailed_results_text.yview)
        self.detailed_results_text.configure(yscrollcommand=detailed_scrollbar.set)
        
        self.detailed_results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detailed_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _create_modern_statusbar(self, parent):
        """Crea una barra d'estat moderna."""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Separador elegant
        separator = ttk.Separator(status_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=(0, 5))
        
        # Barra d'estat amb informació
        self.status_var = tk.StringVar(value="Sistema llest - PackAssist 3D Pro carregat correctament")
        
        status_content = ttk.Frame(status_frame)
        status_content.pack(fill=tk.X)
        
        ttk.Label(status_content, textvariable=self.status_var, 
                 font=('Segoe UI', 9), foreground=self.colors['dark']).pack(side=tk.LEFT)
        
        # Indicador de versió
        ttk.Label(status_content, text="v2.0 Pro", 
                 font=('Segoe UI', 9, 'bold'), 
                 foreground=self.colors['accent']).pack(side=tk.RIGHT)

    # === MÈTODES DE CONTROL ===
    
    def _toggle_input_method(self):
        """Canvia entre entrada manual i selecció de fitxer."""
        if self.input_method.get() == "manual":
            self.file_entry_frame.pack_forget()
            self.manual_entry_frame.pack(fill=tk.X, pady=(10, 0))
        else:
            self.manual_entry_frame.pack_forget()
            self.file_entry_frame.pack(fill=tk.X, pady=(10, 0))
            self._update_object_combo()

    def _update_object_combo(self):
        """Actualitza la llista d'objectes disponibles."""
        try:
            if hasattr(self, 'metadata') and self.metadata:
                names = [item['name'] for item in self.metadata if item.get('type') == 'object']
                self.object_combo['values'] = names
                if names:
                    self.object_combo.set(names[0])
                    self._on_object_selected(None)
        except Exception as e:
            print(f"Error actualitzant combo: {e}")

    def _on_object_selected(self, event):
        """Gestiona la selecció d'un objecte del combo."""
        try:
            selected = self.object_combo.get()
            if selected and hasattr(self, 'metadata'):
                for item in self.metadata:
                    if item['name'] == selected:
                        file_path = item['path']
                        dimensions = self._get_file_dimensions(file_path)
                        if dimensions:
                            # Actualitzar camps de dimensions (si existeixen)
                            pass  # Implementar si es necessita
                        break
        except Exception as e:
            print(f"Error en selecció d'objecte: {e}")

    def _get_file_dimensions(self, file_path):
        """Obté les dimensions d'un fitxer STP."""
        try:
            return get_stp_dimensions(file_path)
        except Exception as e:
            print(f"Error obtenint dimensions: {e}")
            return None

    def update_status(self, message):
        """Actualitza la barra d'estat."""
        self.status_var.set(message)
        self.root.update_idletasks()

    # === MÈTODES DE CÀLCUL ===
    
    def calculate_manual(self):
        """Realitza el càlcul d'empaquetament manual."""
        if self.is_processing:
            return
            
        try:
            self.is_processing = True
            self.update_status("Processant càlcul d'empaquetament...")
            
            # Obtenir dimensions del contenidor
            box_dims = {
                'length': float(self.box_length.get()),
                'width': float(self.box_width.get()),
                'height': float(self.box_height.get())
            }
            
            # Obtenir dimensions de l'objecte segons el mètode seleccionat
            if self.input_method.get() == "manual":
                obj_dims = {
                    'length': float(self.obj_length.get()),
                    'width': float(self.obj_width.get()),
                    'height': float(self.obj_height.get())
                }
            else:
                # Obtenir des de fitxer seleccionat
                selected = self.object_combo.get()
                if not selected:
                    messagebox.showwarning("Atenció", "Seleccioneu un objecte de la llista")
                    return
                
                file_path = None
                for item in self.metadata:
                    if item['name'] == selected:
                        file_path = item['path']
                        break
                
                if not file_path:
                    messagebox.showerror("Error", "No s'ha trobat el fitxer seleccionat")
                    return
                
                dimensions = self._get_file_dimensions(file_path)
                if not dimensions:
                    messagebox.showerror("Error", "No s'han pogut obtenir les dimensions del fitxer")
                    return
                
                obj_dims = {
                    'length': dimensions['length'],
                    'width': dimensions['width'], 
                    'height': dimensions['height']
                }
            
            # Executar optimització en thread separat
            def run_optimization():
                try:
                    # Calcular màxim teòric
                    theoretical_max = calculate_theoretical_max(box_dims, obj_dims)
                    
                    # Executar optimització
                    result = optimize_packing(box_dims, obj_dims)
                    
                    # Actualitzar interfície des del thread principal
                    self.root.after(0, self._update_calculation_results, result, theoretical_max, box_dims, obj_dims)
                    
                except Exception as e:
                    error_msg = f"Error en l'optimització: {str(e)}"
                    self.root.after(0, self._show_calculation_error, error_msg)
            
            # Executar en thread separat
            thread = threading.Thread(target=run_optimization)
            thread.daemon = True
            thread.start()
            
        except ValueError as e:
            messagebox.showerror("Error", "Les dimensions han de ser números vàlids")
            self.is_processing = False
        except Exception as e:
            messagebox.showerror("Error", f"Error en el càlcul: {str(e)}")
            self.is_processing = False

    def _update_calculation_results(self, result, theoretical_max, box_dims, obj_dims):
        """Actualitza els resultats del càlcul a la interfície."""
        try:
            self.optimization_results = result
            
            # Preparar text de resultats
            results_text = self._format_calculation_results(result, theoretical_max, box_dims, obj_dims)
            
            # Actualitzar text widget
            self.results_text.config(state=tk.NORMAL)
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, results_text)
            self.results_text.config(state=tk.DISABLED)
            
            # Actualitzar resultats detallats
            detailed_text = self._format_detailed_results(result, box_dims, obj_dims)
            self.detailed_results_text.delete(1.0, tk.END)
            self.detailed_results_text.insert(tk.END, detailed_text)
            
            # Activar botó de visualització
            self.visualize_btn.config(state=tk.NORMAL)
            
            # Canviar a pestanya de resultats
            self.notebook.select(2)
            
            self.update_status(f"Càlcul completat - {result.get('max_objects', 0)} objectes empaquetats")
            
        except Exception as e:
            self._show_calculation_error(f"Error mostrant resultats: {str(e)}")
        finally:
            self.is_processing = False

    def _show_calculation_error(self, error_msg):
        """Mostra un error de càlcul."""
        messagebox.showerror("Error de Càlcul", error_msg)
        self.update_status("Error en el càlcul")
        self.is_processing = False

    def _format_calculation_results(self, result, theoretical_max, box_dims, obj_dims):
        """Formata els resultats per mostrar."""
        content = f"""RESULTATS DEL CÀLCUL D'EMPAQUETAMENT

Configuració:
{"="*50}
Contenidor: {box_dims['length']} × {box_dims['width']} × {box_dims['height']} mm
Objecte: {obj_dims['length']} × {obj_dims['width']} × {obj_dims['height']} mm

Resultats:
{"="*50}
Màxim teòric (per volum): {theoretical_max} unitats
"""
        
        if result.get('error'):
            content += f"Error: {result['error']}\n"
        else:
            content += f"""Objectes empaquetats: {result.get('max_objects', 0)}
Eficiència d'espai: {result.get('efficiency', 0):.1f}%
Volum contenidor: {result.get('box_volume', 0):,.0f} mm³
Volum utilitzat: {result.get('used_volume', 0):,.0f} mm³

Distribució:
{"="*50}
"""
            bins_data = result.get('bins', [])
            if bins_data:
                bin_data = bins_data[0]
                items = bin_data.get('items', [])
                content += f"Contenidor 1: {len(items)} objectes\n"
                
                for i, item in enumerate(items[:10]):  # Mostrar primer 10
                    pos = item.get('position', [0, 0, 0])
                    content += f"  Objecte {i+1}: posició ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})\n"
                
                if len(items) > 10:
                    content += f"  ... i {len(items) - 10} objectes més\n"
            
        content += f"\nProces completat: {datetime.now().strftime('%H:%M:%S')}"
        return content

    def _format_detailed_results(self, result, box_dims, obj_dims):
        """Formata resultats detallats."""
        detailed = f"""ANÀLISI DETALLAT DE L'EMPAQUETAMENT

Informació del Contenidor:
{"="*60}
Dimensions: {box_dims['length']} × {box_dims['width']} × {box_dims['height']} mm
Volum total: {box_dims['length'] * box_dims['width'] * box_dims['height']:,.0f} mm³

Informació de l'Objecte:
{"="*60}
Dimensions: {obj_dims['length']} × {obj_dims['width']} × {obj_dims['height']} mm
Volum unitari: {obj_dims['length'] * obj_dims['width'] * obj_dims['height']:,.0f} mm³

Resultats de l'Optimització:
{"="*60}
"""
        
        if not result.get('error'):
            detailed += f"""Algoritme utilitzat: Optimització 3D avançada
Objectes empaquetats: {result.get('max_objects', 0)}
Eficiència aconseguida: {result.get('efficiency', 0):.2f}%
Volum utilitzat: {result.get('used_volume', 0):,.0f} mm³
Volum lliure: {result.get('box_volume', 0) - result.get('used_volume', 0):,.0f} mm³

Distribució per Contenidors:
{"="*60}
"""
            bins = result.get('bins', [])
            for i, bin_data in enumerate(bins):
                items = bin_data.get('items', [])
                detailed += f"\nContenidor {i+1}:\n"
                detailed += f"  Objectes: {len(items)}\n"
                detailed += f"  Utilització: {len(items) * obj_dims['length'] * obj_dims['width'] * obj_dims['height']:,.0f} mm³\n"
                
                # Mostrar posicions detallades
                for j, item in enumerate(items):
                    pos = item.get('position', [0, 0, 0])
                    dims = item.get('dimensions', [obj_dims['length'], obj_dims['width'], obj_dims['height']])
                    detailed += f"    Objecte {j+1}: posició ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}) "
                    detailed += f"dimensions ({dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f})\n"
        else:
            detailed += f"Error en l'optimització: {result['error']}\n"
        
        detailed += f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return detailed

    # === MÈTODES DE VISUALITZACIÓ ===
    
    def visualize_packing(self):
        """Crea visualització 3D moderna i millorada."""
        if not hasattr(self, 'optimization_results') or not self.optimization_results:
            messagebox.showwarning("Atenció", "No hi ha resultats per visualitzar.")
            return
            
        try:
            self.update_status("Generant visualització 3D avançada...")
            
            # Tancar visualització anterior si existeix
            if self.current_viz_window:
                try:
                    self.current_viz_window.destroy()
                except:
                    pass
            
            # Crear nova finestra de visualització
            self.current_viz_window = tk.Toplevel(self.root)
            self.current_viz_window.title("Visualització 3D Avançada - PackAssist Pro")
            self.current_viz_window.geometry("1000x800")
            self.current_viz_window.transient(self.root)
            
            # Frame principal amb padding
            main_frame = ttk.Frame(self.current_viz_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Crear figura matplotlib millorada
            fig = Figure(figsize=(12, 9), dpi=100, facecolor='white')
            ax = fig.add_subplot(111, projection='3d')
            
            # Obtenir dades
            bins_data = self.optimization_results.get('bins', [])
            if not bins_data:
                messagebox.showerror("Error", "No hi ha dades de contenidors.")
                self.current_viz_window.destroy()
                return
            
            bin_data = bins_data[0]
            bin_info = bin_data['bin']
            items_info = bin_data['items']
            
            # Dimensions del contenidor
            container_dims = bin_info['dimensions']
            container_length = float(container_dims[0])
            container_width = float(container_dims[1])
            container_height = float(container_dims[2])
            
            # Dibuixar contenidor amb millor estil
            self._draw_modern_container(ax, container_length, container_width, container_height)
            
            # Dibuixar objectes amb colors atractius
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', 
                     '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9']
            
            for i, item in enumerate(items_info):
                position = [float(x) for x in item['position']]
                dimensions = [float(x) for x in item['dimensions']]
                color = colors[i % len(colors)]
                
                self._draw_modern_3d_box(ax, position, dimensions, color, alpha=0.8)
            
            # Configuració avançada del gràfic
            ax.set_xlabel('Longitud (mm)', fontsize=12, fontweight='bold')
            ax.set_ylabel('Amplada (mm)', fontsize=12, fontweight='bold')
            ax.set_zlabel('Altura (mm)', fontsize=12, fontweight='bold')
            
            # Títol informatiu
            efficiency = self.optimization_results.get('efficiency', 0)
            ax.set_title(f'Empaquetament 3D Optimitzat\\n{len(items_info)} objectes - Eficiència: {efficiency:.1f}%', 
                        fontsize=14, fontweight='bold', pad=20)
            
            # Estil millorat dels eixos
            ax.grid(True, alpha=0.3)
            self._set_axes_equal_3d(ax)
            
            # Configurar vista inicial òptima
            ax.view_init(elev=20, azim=45)
            
            # Canvas matplotlib
            canvas = FigureCanvasTkAgg(fig, main_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Toolbar de navegació
            toolbar = NavigationToolbar2Tk(canvas, main_frame)
            toolbar.update()
            
            # Panell d'informació i controls
            self._create_visualization_controls(main_frame, container_length, 
                                              container_width, container_height, 
                                              len(items_info), fig)
            
            self.update_status("Visualització 3D generada correctament")
            
        except Exception as e:
            error_msg = f"Error en la visualització: {str(e)}"
            self.update_status("Error en la visualització")
            messagebox.showerror("Error", error_msg)
            print(f"Debug - Error en visualització: {e}")
            traceback.print_exc()

    def _draw_modern_container(self, ax, length, width, height):
        """Dibuixa un contenidor amb estil modern."""
        # Vèrtexs del contenidor
        vertices = [
            [0, 0, 0], [length, 0, 0], [length, width, 0], [0, width, 0],
            [0, 0, height], [length, 0, height], [length, width, height], [0, width, height]
        ]
        
        # Arestes amb estil millorat
        edges = [
            [0, 1], [1, 2], [2, 3], [3, 0],  # Base inferior
            [4, 5], [5, 6], [6, 7], [7, 4],  # Base superior
            [0, 4], [1, 5], [2, 6], [3, 7]   # Arestes verticals
        ]
        
        # Dibuixar arestes amb millor estil
        for edge in edges:
            points = np.array([vertices[edge[0]], vertices[edge[1]]])
            ax.plot3D(points[:, 0], points[:, 1], points[:, 2], 
                     color='#2C3E50', linewidth=2.5, alpha=0.9)
        
        # Afegir plans semi-transparents per millor visualització
        # Base del contenidor
        base_vertices = [vertices[0], vertices[1], vertices[2], vertices[3]]
        ax.add_collection3d(Poly3DCollection([base_vertices], alpha=0.1, 
                                           facecolor='#BDC3C7', edgecolor='none'))

    def _draw_modern_3d_box(self, ax, position, dimensions, color, alpha=0.8):
        """Dibuixa una caixa 3D amb estil modern millorat."""
        x, y, z = float(position[0]), float(position[1]), float(position[2])
        dx, dy, dz = float(dimensions[0]), float(dimensions[1]), float(dimensions[2])
        
        # Vèrtexs de la caixa
        vertices = np.array([
            [x, y, z], [x+dx, y, z], [x+dx, y+dy, z], [x, y+dy, z],
            [x, y, z+dz], [x+dx, y, z+dz], [x+dx, y+dy, z+dz], [x, y+dy, z+dz]
        ])
        
        # Cares de la caixa
        faces = [
            [vertices[0], vertices[1], vertices[2], vertices[3]],  # Base inferior
            [vertices[4], vertices[5], vertices[6], vertices[7]],  # Base superior
            [vertices[0], vertices[1], vertices[5], vertices[4]],  # Cara frontal
            [vertices[2], vertices[3], vertices[7], vertices[6]],  # Cara posterior
            [vertices[1], vertices[2], vertices[6], vertices[5]],  # Cara dreta
            [vertices[4], vertices[7], vertices[3], vertices[0]]   # Cara esquerra
        ]
        
        # Crear col·lecció 3D amb millor estil
        poly3d = [[tuple(vertex) for vertex in face] for face in faces]
        collection = Poly3DCollection(poly3d, alpha=alpha, facecolor=color, 
                                    edgecolor='#2C3E50', linewidth=0.8)
        ax.add_collection3d(collection)

    def _set_axes_equal_3d(self, ax):
        """Fa que els eixos 3D tinguin la mateixa escala."""
        x_limits = ax.get_xlim3d()
        y_limits = ax.get_ylim3d()
        z_limits = ax.get_zlim3d()
        
        x_range = abs(x_limits[1] - x_limits[0])
        y_range = abs(y_limits[1] - y_limits[0])
        z_range = abs(z_limits[1] - z_limits[0])
        
        # Trobar el rang màxim i centrar els eixos
        max_range = max(x_range, y_range, z_range)
        
        x_mid = (x_limits[1] + x_limits[0]) * 0.5
        y_mid = (y_limits[1] + y_limits[0]) * 0.5
        z_mid = (z_limits[1] + z_limits[0]) * 0.5
        
        ax.set_xlim3d([x_mid - max_range/2, x_mid + max_range/2])
        ax.set_ylim3d([y_mid - max_range/2, y_mid + max_range/2])
        ax.set_zlim3d([z_mid - max_range/2, z_mid + max_range/2])

    def _create_visualization_controls(self, parent, container_length, container_width, 
                                     container_height, item_count, fig):
        """Crea controls avançats per la visualització."""
        # Panell d'informació
        info_frame = ttk.LabelFrame(parent, text="  Informació del Resultat  ", padding="10")
        info_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Grid d'informació
        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill=tk.X)
        
        # Columna 1
        col1 = ttk.Frame(info_grid)
        col1.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(col1, text=f"Contenidor: {container_length:.0f} × {container_width:.0f} × {container_height:.0f} mm", 
                 font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W)
        ttk.Label(col1, text=f"Objectes empaquetats: {item_count}", 
                 font=('Segoe UI', 10)).pack(anchor=tk.W)
        
        # Columna 2
        col2 = ttk.Frame(info_grid)
        col2.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        efficiency = self.optimization_results.get('efficiency', 0)
        ttk.Label(col2, text=f"Eficiència: {efficiency:.1f}%", 
                 font=('Segoe UI', 10, 'bold')).pack(anchor=tk.E)
        
        used_volume = self.optimization_results.get('used_volume', 0)
        ttk.Label(col2, text=f"Volum utilitzat: {used_volume:,.0f} mm³", 
                 font=('Segoe UI', 10)).pack(anchor=tk.E)
        
        # Controls de la visualització
        controls_frame = ttk.Frame(info_frame)
        controls_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(controls_frame, text="Guardar Imatge", 
                  command=lambda: self._save_3d_image(fig), 
                  style='Modern.TButton').pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(controls_frame, text="Vista Frontal", 
                  command=lambda: self._set_view(fig.axes[0], 0, 0), 
                  style='Modern.TButton').pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(controls_frame, text="Vista Lateral", 
                  command=lambda: self._set_view(fig.axes[0], 0, 90), 
                  style='Modern.TButton').pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(controls_frame, text="Vista Superior", 
                  command=lambda: self._set_view(fig.axes[0], 90, 0), 
                  style='Modern.TButton').pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(controls_frame, text="Tancar", 
                  command=self.current_viz_window.destroy, 
                  style='Modern.TButton').pack(side=tk.RIGHT)

    def _set_view(self, ax, elev, azim):
        """Estableix una vista específica."""
        ax.view_init(elev=elev, azim=azim)
        ax.figure.canvas.draw()

    def _save_3d_image(self, fig):
        """Guarda la imatge 3D."""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("PDF files", "*.pdf"), ("All files", "*.*")],
                title="Guardar visualització 3D"
            )
            if filename:
                fig.savefig(filename, dpi=300, bbox_inches='tight', 
                           facecolor='white', edgecolor='none')
                self.update_status(f"Imatge guardada: {filename}")
                messagebox.showinfo("Guardat", f"Imatge guardada correctament:\\n{filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Error guardant imatge: {str(e)}")

    # === MÈTODES AUXILIARS ===
    
    def _load_initial_data(self):
        """Carrega dades inicials."""
        try:
            self.reload_metadata()
            self.update_status("Aplicació carregada correctament")
        except Exception as e:
            print(f"Error carregant dades inicials: {e}")

    def reload_metadata(self):
        """Recarrega metadades dels fitxers."""
        self.metadata = []
        if os.path.exists(CSV_PATH):
            try:
                with open(CSV_PATH, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    self.metadata = list(reader)
                self._update_file_tree()
            except Exception as e:
                print(f"Error carregant CSV: {e}")
                messagebox.showerror("Error", f"Error carregant el fitxer CSV: {e}")
    
    def open_mesh_simplification(self):
        """Obre l'editor de simplificació de malla per al fitxer seleccionat."""
        if not hasattr(self, 'file_tree') or not self.file_tree.selection():
            messagebox.showwarning("Selecciona un fitxer", 
                                 "Si us plau, selecciona un fitxer de la llista per simplificar.")
            return
        
        selected = self.file_tree.selection()[0]
        item = self.file_tree.item(selected)
        filename = item['values'][0]
        
        # Buscar el fitxer corresponent en les carpetes d'objectes
        stp_path = self._find_stp_file(filename)
        
        if not stp_path:
            messagebox.showerror("Fitxer no trobat", 
                               f"No es pot trobar el fitxer STP: {filename}")
            return
        
        try:
            # Obrir l'editor de simplificació de malla
            self.geometry_analyzer.open_mesh_editor(stp_path)
            
        except Exception as e:
            messagebox.showerror("Error", 
                               f"Error en obrir l'editor de simplificació:\n{str(e)}")
            print(f"Error detallat: {traceback.format_exc()}")
    
    def on_file_double_click(self, event):
        """Maneja el doble clic en un fitxer per obrir la simplificació."""
        self.open_mesh_simplification()
    
    def _find_stp_file(self, filename):
        """Troba el path complet d'un fitxer STP."""
        search_paths = ['objects', 'boxes']
        
        for folder in search_paths:
            if os.path.exists(folder):
                for file in os.listdir(folder):
                    if file == filename:
                        return os.path.join(folder, file)
        
        return None

    def _update_file_tree(self):
        """Actualitza l'arbre de fitxers."""
        if hasattr(self, 'file_tree'):
            # Netejar arbre
            for item in self.file_tree.get_children():
                self.file_tree.delete(item)
            
            # Afegir elements
            for item in self.metadata:
                name = item.get('name', 'Unknown')
                type_val = item.get('type', 'Unknown')
                dimensions = f"{item.get('length', 0)} × {item.get('width', 0)} × {item.get('height', 0)}"
                
                # Calcular complexitat basada en el volum
                try:
                    length = float(item.get('length', 0))
                    width = float(item.get('width', 0))
                    height = float(item.get('height', 0))
                    volume = length * width * height
                    
                    if volume > 1000000:  # > 1m³
                        complexity = "Alta"
                    elif volume > 100000:  # > 100L
                        complexity = "Mitjana"
                    else:
                        complexity = "Baixa"
                except:
                    complexity = "N/A"
                
                status = "Vàlid" if self._validate_file(item.get('path', '')) else "No vàlid"
                
                self.file_tree.insert('', 'end', values=(name, type_val, dimensions, complexity, status))

    def _validate_file(self, file_path):
        """Valida si un fitxer existeix."""
        return os.path.exists(file_path) if file_path else False

    # Mètodes bàsics per compatibilitat
    def add_csv_entry(self):
        messagebox.showinfo("Info", "Funcionalitat en desenvolupament")
    
    def edit_selected_item(self):
        messagebox.showinfo("Info", "Funcionalitat en desenvolupament")
    
    def save_csv_data(self):
        """Guarda les dades CSV"""
        try:
            with open(self.csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                if self.metadata:
                    fieldnames = self.metadata[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(self.metadata)
            messagebox.showinfo("Guardat", "Dades guardades correctament")
        except Exception as e:
            messagebox.showerror("Error", f"Error guardant: {e}")

    def open_mesh_simplification(self):
        """Obre l'editor de simplificació de malla"""
        selected = self.file_tree.selection()
        if not selected:
            messagebox.showwarning("Atenció", "Selecciona un fitxer STP de la llista")
            return
        
        item = self.file_tree.item(selected[0])
        filename = item['values'][0]
        
        # Buscar el fitxer en les carpetes d'objectes
        file_path = None
        for folder in ['objects', 'boxes']:
            potential_path = os.path.join(folder, filename)
            if os.path.exists(potential_path):
                file_path = potential_path
                break
        
        if not file_path:
            messagebox.showerror("Error", f"No es pot trobar el fitxer: {filename}")
            return
        
        try:
            self.geometry_analyzer.open_mesh_editor(file_path)
        except Exception as e:
            messagebox.showerror("Error", f"Error obrint l'editor de malla: {e}")

    def on_file_double_click(self, event):
        """Gestiona el doble clic en un fitxer per obrir simplificació"""
        self.open_mesh_simplification()

    def _update_file_tree(self):
        """Actualitza la visualització de fitxers amb informació de complexitat"""
        # Esborrar contingut anterior
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        # Afegir fitxers
        for entry in self.metadata:
            complexity = "Baixa"
            if 'complexity' in entry:
                complexity = entry['complexity']
            elif 'dimensions' in entry:
                try:
                    dims = entry['dimensions'].split('x')
                    if len(dims) >= 3:
                        volume = float(dims[0]) * float(dims[1]) * float(dims[2])
                        if volume > 100000:
                            complexity = "Alta"
                        elif volume > 10000:
                            complexity = "Mitjana"
                except:
                    complexity = "Desconeguda"
            
            self.file_tree.insert("", "end", values=(
                entry.get('filename', ''),
                entry.get('type', 'object'),
                entry.get('dimensions', ''),
                complexity,
                entry.get('status', 'OK')
            ))
    
    def export_results(self):
        messagebox.showinfo("Info", "Funcionalitat en desenvolupament")
    
    def _save_configuration(self):
        messagebox.showinfo("Info", "Configuració guardada")


def main():
    """Funció principal per executar l'aplicació."""
    try:
        root = tk.Tk()
        app = ModernPackAssistGUI(root)
        
        # Configurar tancament elegant
        def on_closing():
            try:
                if hasattr(app, 'current_viz_window') and app.current_viz_window:
                    app.current_viz_window.destroy()
            except:
                pass
            root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Executar aplicació
        root.mainloop()
        
    except Exception as e:
        print(f"Error iniciant aplicació: {e}")
        traceback.print_exc()
        messagebox.showerror("Error Crític", f"Error iniciant PackAssist 3D Pro:\\n{str(e)}")


if __name__ == "__main__":
    main()
