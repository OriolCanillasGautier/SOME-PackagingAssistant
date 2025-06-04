#!/usr/bin/env python3
"""
PackAssist 3D - Optimitzador de 3D Bin Packing amb GUI moderna
Sistema integrat per l'optimització d'empaquetament 3D amb interfície gràfica.
"""
import csv
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import matplotlib.pyplot as plt
import datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np
from src.packassist import get_stp_dimensions, validate_stp_file, optimize_packing, calculate_theoretical_max
# Constants
CSV_PATH = "data/index.csv"
ICON_SIZE = 16
class PackAssistGUI:
    """Interfície gràfica principal per PackAssist 3D."""
    def __init__(self, root):  # Corregit: **init** -> __init__
        """Inicialitza la interfície gràfica."""
        self.root = root
        self.root.title("PackAssist 3D - Optimitzador de Bin Packing")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        # Variables de control
        self.is_processing = False
        self.metadata = []
        # Configurar estil modern
        self.setup_styles()
        # Crear interfície
        self.create_widgets()
        # Carregar dades inicials
        self.load_initial_data()
        # Variable per guardar resultats per visualització
        self.optimization_results = None  # Afegit per evitar error en visualize_packing()

    def setup_styles(self):
        """Configura estils moderns per la interfície."""
        style = ttk.Style()
        style.theme_use('clam')
        # Colors moderns
        bg_color = "#f5f5f5"
        accent_color = "#2196F3"
        success_color = "#4CAF50"
        warning_color = "#FF9800"
        error_color = "#F44336"
        # Configurar estils personalitzats
        style.configure('Title.TLabel', font=('Arial', 14, 'bold'))
        style.configure('Header.TLabel', font=('Arial', 11, 'bold'))
        style.configure('Success.TLabel', foreground=success_color)
        style.configure('Warning.TLabel', foreground=warning_color)
        style.configure('Error.TLabel', foreground=error_color)
        self.root.configure(bg=bg_color)

    def create_widgets(self):
        """Crea tots els widgets de la interfície."""
        # Frame principal
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        # Configurar redimensionament
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1)
        # Títol
        title_label = ttk.Label(self.main_frame, text="🎯 PackAssist 3D", style='Title.TLabel')
        title_label.grid(row=0, column=0, pady=(0, 10))
        # Notebook per pestanyes
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        # Crear pestanyes
        self.create_stp_tab()
        self.create_manual_tab()
        self.create_csv_editor_tab()  # NOVA PESTANYA
        self.create_results_tab()
        # Botó de visualització 3D
        self.create_visualization_section()
        # Barra d'estat
        self.create_status_bar(self.main_frame)

    def create_stp_tab(self):
        """Crea la pestanya de fitxers STP."""
        stp_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(stp_frame, text="📁 Fitxers STP")
        # Configurar grid
        stp_frame.columnconfigure(0, weight=1)
        stp_frame.rowconfigure(2, weight=1)
        # Gestió de fitxers
        file_frame = ttk.LabelFrame(stp_frame, text="Gestió de fitxers", padding="10")
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        ttk.Button(file_frame, text="📂 Carregar CSV",
                  command=self.load_csv_file).grid(row=0, column=0, padx=(0, 5))
        self.csv_path_var = tk.StringVar(value=CSV_PATH)
        ttk.Entry(file_frame, textvariable=self.csv_path_var, state='readonly').grid(
            row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        ttk.Button(file_frame, text="🔄 Recarregar",
                  command=self.reload_metadata).grid(row=0, column=2, padx=(5, 0))
        # Control de processat
        control_frame = ttk.LabelFrame(stp_frame, text="Control de processat", padding="10")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Button(control_frame, text="▶️ Processar Tot",
                  command=self.process_all_files).grid(row=0, column=0, padx=(0, 10))
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(control_frame, variable=self.progress_var,
                                          maximum=100, length=200)
        self.progress_bar.grid(row=0, column=1, padx=(10, 10))
        ttk.Button(control_frame, text="⏹️ Aturar",
                  command=self.stop_processing).grid(row=0, column=2, padx=(10, 0))
        # Llista de fitxers
        list_frame = ttk.LabelFrame(stp_frame, text="Fitxers carregats", padding="10")
        list_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        # Treeview per mostrar fitxers
        columns = ('Tipus', 'Nom', 'Fitxer', 'Estat')
        self.file_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        for col in columns:
            self.file_tree.heading(col, text=col)
            self.file_tree.column(col, width=150)
        # Scrollbar per la taula
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        self.file_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

    def create_manual_tab(self):
        """Crea la pestanya d'entrada manual."""
        manual_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(manual_frame, text="🔢 Entrada Manual")
        # Configurar grid
        manual_frame.columnconfigure(0, weight=1)
        manual_frame.columnconfigure(1, weight=1)        # Dimensions del contenidor
        box_frame = ttk.LabelFrame(manual_frame, text="📦 Dimensions del contenidor (cm)", padding="10")
        box_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 5), pady=(0, 10))
        # Selector de caixes importades
        self.box_source_var = tk.StringVar(value="manual")
        ttk.Radiobutton(box_frame, text="Entrada manual", variable=self.box_source_var,
                       value="manual", command=self.toggle_box_input).grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(box_frame, text="Seleccionar de la llista", variable=self.box_source_var,
                       value="imported", command=self.toggle_box_input).grid(row=0, column=1, sticky=tk.W)
        # Frame per selecció de caixes importades
        self.box_selection_frame = ttk.Frame(box_frame)
        self.box_selection_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        ttk.Label(self.box_selection_frame, text="Caixa:").grid(row=0, column=0, sticky=tk.W)
        self.selected_box_var = tk.StringVar()
        self.box_combo = ttk.Combobox(self.box_selection_frame, textvariable=self.selected_box_var,
                                     state="readonly", width=25)
        self.box_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        self.box_combo.bind('<<ComboboxSelected>>', self.on_box_selected)
        self.box_selection_frame.columnconfigure(1, weight=1)
        self.box_selection_frame.grid_remove()  # Inicialment ocult        # Frame per entrada manual de caixes
        self.manual_box_frame = ttk.Frame(box_frame)
        self.manual_box_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        ttk.Label(self.manual_box_frame, text="Longitud (cm):").grid(row=0, column=0, sticky=tk.W)
        self.box_length_var = tk.DoubleVar(value=100.0)
        ttk.Entry(self.manual_box_frame, textvariable=self.box_length_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        ttk.Label(self.manual_box_frame, text="Amplada (cm):").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.box_width_var = tk.DoubleVar(value=80.0)
        ttk.Entry(self.manual_box_frame, textvariable=self.box_width_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))
        ttk.Label(self.manual_box_frame, text="Altura (cm):").grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
        self.box_height_var = tk.DoubleVar(value=60.0)
        ttk.Entry(self.manual_box_frame, textvariable=self.box_height_var).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))
        self.manual_box_frame.columnconfigure(1, weight=1)
        box_frame.columnconfigure(1, weight=1)            # Dimensions de l'objecte
        obj_frame = ttk.LabelFrame(manual_frame, text="📋 Dimensions de l'objecte (cm)", padding="10")
        obj_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), padx=(5, 0), pady=(0, 10))
        # Opcions per introduir dimensions: manual, fitxer o objectes importats
        self.input_method_var = tk.StringVar(value="manual")
        ttk.Radiobutton(obj_frame, text="Entrada manual", variable=self.input_method_var,
                       value="manual", command=self.toggle_input_method).grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(obj_frame, text="Fitxer 3D", variable=self.input_method_var,
                       value="file", command=self.toggle_input_method).grid(row=0, column=1, sticky=tk.W)
        ttk.Radiobutton(obj_frame, text="Objectes importats", variable=self.input_method_var,
                       value="imported", command=self.toggle_input_method).grid(row=1, column=0, columnspan=2, sticky=tk.W)
        # Frame per selecció d'objectes importats
        self.object_selection_frame = ttk.Frame(obj_frame)
        self.object_selection_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        ttk.Label(self.object_selection_frame, text="Objecte:").grid(row=0, column=0, sticky=tk.W)
        self.selected_object_var = tk.StringVar()
        self.object_combo = ttk.Combobox(self.object_selection_frame, textvariable=self.selected_object_var,
                                        state="readonly", width=25)
        self.object_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        self.object_combo.bind('<<ComboboxSelected>>', self.on_object_selected)
        self.object_selection_frame.columnconfigure(1, weight=1)
        self.object_selection_frame.grid_remove()  # Inicialment ocult        # Frame per entrada manual
        self.manual_input_frame = ttk.Frame(obj_frame)
        self.manual_input_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        ttk.Label(self.manual_input_frame, text="Longitud (cm):").grid(row=0, column=0, sticky=tk.W)
        self.obj_length_var = tk.DoubleVar(value=20.0)
        ttk.Entry(self.manual_input_frame, textvariable=self.obj_length_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        ttk.Label(self.manual_input_frame, text="Amplada (cm):").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.obj_width_var = tk.DoubleVar(value=15.0)
        ttk.Entry(self.manual_input_frame, textvariable=self.obj_width_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))
        ttk.Label(self.manual_input_frame, text="Altura (cm):").grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
        self.obj_height_var = tk.DoubleVar(value=10.0)
        ttk.Entry(self.manual_input_frame, textvariable=self.obj_height_var).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))
        self.manual_input_frame.columnconfigure(1, weight=1)
        # Frame per entrada de fitxer
        self.file_input_frame = ttk.Frame(obj_frame)
        self.file_input_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        self.file_path_var = tk.StringVar()
        ttk.Entry(self.file_input_frame, textvariable=self.file_path_var, width=30).grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(self.file_input_frame, text="Explorar...", command=self.browse_3d_file).grid(row=0, column=1)
        # Informació de les dimensions del fitxer
        self.file_info_var = tk.StringVar(value="Dimensions: - x - x - mm")
        ttk.Label(self.file_input_frame, textvariable=self.file_info_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        self.file_input_frame.columnconfigure(0, weight=1)
        self.file_input_frame.grid_remove()  # Inicialment ocult
        obj_frame.columnconfigure(1, weight=1)
        # Botó de càlcul
        calc_frame = ttk.Frame(manual_frame)
        calc_frame.grid(row=1, column=0, columnspan=2, pady=10)
        ttk.Button(calc_frame, text="🧮 Calcular Empaquetament",
                  command=self.calculate_manual).grid(row=0, column=0)
        # Resultats
        results_frame = ttk.LabelFrame(manual_frame, text="📊 Resultats", padding="10")
        results_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        self.manual_results = tk.Text(results_frame, height=15, wrap=tk.WORD)
        manual_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.manual_results.yview)
        self.manual_results.configure(yscrollcommand=manual_scrollbar.set)
        self.manual_results.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        manual_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

    def create_csv_editor_tab(self):
        """Crea la pestanya d'edició CSV - NOVA FUNCIONALITAT"""
        csv_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(csv_frame, text="📝 Editor CSV")
        
        # Configurar grid
        csv_frame.columnconfigure(0, weight=1)
        csv_frame.rowconfigure(1, weight=1)
        
        # Controls superior
        controls_frame = ttk.Frame(csv_frame)
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        controls_frame.columnconfigure(1, weight=1)
        
        ttk.Button(controls_frame, text="🔄 Recarregar CSV", 
                  command=self.reload_csv_data).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(controls_frame, text="➕ Afegir Entrada", 
                  command=self.add_csv_entry).grid(row=0, column=1, padx=5)
        ttk.Button(controls_frame, text="💾 Guardar CSV", 
                  command=self.save_csv_data).grid(row=0, column=2, padx=(5, 0))
        
        # Taula d'edició
        table_frame = ttk.Frame(csv_frame)
        table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        
        # Crear Treeview per la taula
        columns = ("type", "name", "file_path")
        self.csv_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        # Configurar columnes
        self.csv_tree.heading("type", text="Tipus")
        self.csv_tree.heading("name", text="Nom")
        self.csv_tree.heading("file_path", text="Ruta del Fitxer")
        
        self.csv_tree.column("type", width=80, minwidth=80)
        self.csv_tree.column("name", width=200, minwidth=150)
        self.csv_tree.column("file_path", width=300, minwidth=200)
        
        # Scrollbars per la taula
        csv_v_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.csv_tree.yview)
        csv_h_scroll = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.csv_tree.xview)
        self.csv_tree.configure(yscrollcommand=csv_v_scroll.set, xscrollcommand=csv_h_scroll.set)
        
        self.csv_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        csv_v_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        csv_h_scroll.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Bind events per edició
        self.csv_tree.bind("<Double-1>", self.edit_csv_entry)
        self.csv_tree.bind("<Delete>", self.delete_csv_entry)
        
        # Frame per edició d'entrada
        edit_frame = ttk.LabelFrame(csv_frame, text="Editar Entrada", padding="10")
        edit_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        edit_frame.columnconfigure(1, weight=1)
        
        # Camps d'edició
        ttk.Label(edit_frame, text="Tipus:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.edit_type_var = tk.StringVar()
        type_combo = ttk.Combobox(edit_frame, textvariable=self.edit_type_var, 
                                 values=["box", "object"], state="readonly", width=15)
        type_combo.grid(row=0, column=1, sticky=tk.W, padx=(5, 0), pady=(0, 5))
        
        ttk.Label(edit_frame, text="Nom:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        self.edit_name_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.edit_name_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(0, 5))
        
        ttk.Label(edit_frame, text="Ruta:").grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        path_frame = ttk.Frame(edit_frame)
        path_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(0, 5))
        path_frame.columnconfigure(0, weight=1)
        
        self.edit_path_var = tk.StringVar()
        ttk.Entry(path_frame, textvariable=self.edit_path_var).grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(path_frame, text="📁", command=self.browse_file_path).grid(row=0, column=1)
        
        # Botons d'edició
        edit_buttons_frame = ttk.Frame(edit_frame)
        edit_buttons_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(edit_buttons_frame, text="✅ Aplicar Canvis", 
                  command=self.apply_csv_changes).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(edit_buttons_frame, text="❌ Cancel·lar", 
                  command=self.cancel_csv_edit).grid(row=0, column=1, padx=5)
        ttk.Button(edit_buttons_frame, text="🗑️ Eliminar", 
                  command=self.delete_selected_csv_entry).grid(row=0, column=2, padx=(5, 0))
        
        # Variables per control d'edició
        self.editing_csv_item = None
        self.csv_data_modified = False

    def create_results_tab(self):
        """Crea la pestanya de resultats."""
        results_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(results_frame, text="📊 Resultats")
        # Configurar grid
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(1, weight=1)
        # Controls
        controls_frame = ttk.Frame(results_frame)
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Button(controls_frame, text="💾 Exportar Resultats",
                  command=self.export_results).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(controls_frame, text="🗑️ Netejar Resultats",
                  command=self.clear_results).grid(row=0, column=1)
        # Àrea de resultats
        results_text_frame = ttk.LabelFrame(results_frame, text="Resultats detallats", padding="5")
        results_text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        results_text_frame.columnconfigure(0, weight=1)
        results_text_frame.rowconfigure(0, weight=1)
        self.results_text = tk.Text(results_text_frame, wrap=tk.WORD, font=('Consolas', 10))
        results_scrollbar = ttk.Scrollbar(results_text_frame, orient=tk.VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=results_scrollbar.set)
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        results_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

    def create_status_bar(self, parent):
        """Crea la barra d'estat."""
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        status_frame.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="Llest")
        status_label = ttk.Label(status_frame, textvariable=self.status_var)
        status_label.grid(row=0, column=0, sticky=tk.W)
        # Informació del sistema
        info_label = ttk.Label(status_frame, text=f"Python {sys.version.split()[0]} | PackAssist 3D v1.0")
        info_label.grid(row=0, column=1, sticky=tk.E)

    def load_initial_data(self):
        """Carrega les dades inicials."""
        self.update_status("Carregant dades inicials...")
        self.reload_metadata()
        # Inicialitzar taula CSV
        if hasattr(self, 'csv_tree'):
            self.update_csv_tree()

    def update_status(self, message):
        """Actualitza la barra d'estat."""
        self.status_var.set(message)
        self.root.update_idletasks()

    def load_csv_file(self):
        """Carrega un fitxer CSV."""
        filename = filedialog.askopenfilename(
            title="Selecciona fitxer CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=os.path.dirname(CSV_PATH)
        )
        if filename:
            self.csv_path_var.set(filename)
            self.reload_metadata()
    
    # ========================
    # FUNCIONS CSV EDITOR
    # ========================
    
    def reload_csv_data(self):
        """Recarrega les dades del CSV i actualitza la taula CSV."""
        try:
            csv_path = self.csv_path_var.get()
            if not os.path.exists(csv_path):
                messagebox.showwarning("Avís", f"El fitxer CSV no existeix: {csv_path}")
                return
                
            # Carregar dades del CSV
            with open(csv_path, "r", encoding='utf-8') as f:
                self.metadata = list(csv.DictReader(f))
            
            # Actualitzar la taula CSV
            self.update_csv_tree()
            
            # Actualitzar altres components
            self.update_file_tree()
            if hasattr(self, 'box_combo'):
                self.update_box_combo()
            if hasattr(self, 'object_combo'):
                self.update_object_combo()
                
            self.csv_data_modified = False
            self.update_status(f"CSV recarregat: {len(self.metadata)} entrades")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error recarregant CSV: {e}")
            self.update_status("Error recarregant CSV")

    def update_csv_tree(self):
        """Actualitza la taula CSV amb les dades actuals."""
        # Netejar taula
        for item in self.csv_tree.get_children():
            self.csv_tree.delete(item)
        
        # Afegir entrades
        for entry in self.metadata:
            item_id = self.csv_tree.insert("", tk.END, values=(
                entry.get("type", ""),
                entry.get("name", ""),
                entry.get("file_path", "")
            ))

    def add_csv_entry(self):
        """Afegeix una nova entrada al CSV."""
        try:
            # Netejar camps d'edició
            self.edit_type_var.set("box")
            self.edit_name_var.set("")
            self.edit_path_var.set("")
            
            # Mode d'afegir nova entrada
            self.editing_csv_item = None
            self.csv_data_modified = True
            
            # Focus al primer camp
            self.edit_name_var.set("Nova entrada")
            
            self.update_status("Mode afegir: Omple els camps i prem 'Aplicar Canvis'")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error preparant nova entrada: {e}")

    def save_csv_data(self):
        """Guarda les dades actuals al fitxer CSV."""
        try:
            csv_path = self.csv_path_var.get()
            
            # Crear directori si no existeix
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            
            # Guardar al CSV
            with open(csv_path, "w", newline='', encoding='utf-8') as f:
                if self.metadata:
                    fieldnames = ["type", "name", "file_path"]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(self.metadata)
            
            self.csv_data_modified = False
            messagebox.showinfo("Èxit", f"CSV guardat correctament:\n{csv_path}")
            self.update_status("CSV guardat correctament")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error guardant CSV: {e}")
            self.update_status("Error guardant CSV")

    def edit_csv_entry(self, event=None):
        """Inicia l'edició d'una entrada seleccionada."""
        try:
            selection = self.csv_tree.selection()
            if not selection:
                messagebox.showwarning("Avís", "Selecciona una entrada per editar")
                return
            
            item = selection[0]
            values = self.csv_tree.item(item, "values")
            
            if len(values) >= 3:
                # Omplir camps d'edició
                self.edit_type_var.set(values[0])
                self.edit_name_var.set(values[1])
                self.edit_path_var.set(values[2])
                
                # Guardar referència per edició
                self.editing_csv_item = item
                
                self.update_status("Mode edició: Modifica els camps i prem 'Aplicar Canvis'")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error editant entrada: {e}")

    def delete_csv_entry(self, event=None):
        """Elimina l'entrada seleccionada (tecla Delete)."""
        self.delete_selected_csv_entry()

    def apply_csv_changes(self):
        """Aplica els canvis d'edició o afegeix nova entrada."""
        try:
            # Validar camps
            entry_type = self.edit_type_var.get().strip()
            entry_name = self.edit_name_var.get().strip()
            entry_path = self.edit_path_var.get().strip()
            
            if not entry_type or not entry_name or not entry_path:
                messagebox.showwarning("Avís", "Tots els camps són obligatoris")
                return
            
            if entry_type not in ["box", "object"]:
                messagebox.showwarning("Avís", "El tipus ha de ser 'box' o 'object'")
                return
            
            # Crear nova entrada
            new_entry = {
                "type": entry_type,
                "name": entry_name,
                "file_path": entry_path
            }
            
            if self.editing_csv_item:
                # Mode edició: trobar l'índex i actualitzar
                values = self.csv_tree.item(self.editing_csv_item, "values")
                for i, entry in enumerate(self.metadata):
                    if (entry.get("type") == values[0] and 
                        entry.get("name") == values[1] and 
                        entry.get("file_path") == values[2]):
                        self.metadata[i] = new_entry
                        break
                
                # Actualitzar item a la taula
                self.csv_tree.item(self.editing_csv_item, values=(
                    new_entry["type"],
                    new_entry["name"], 
                    new_entry["file_path"]
                ))
                
                self.editing_csv_item = None
                self.update_status("Entrada actualitzada")
                
            else:
                # Mode afegir: afegir al final
                self.metadata.append(new_entry)
                self.csv_tree.insert("", tk.END, values=(
                    new_entry["type"],
                    new_entry["name"],
                    new_entry["file_path"]
                ))
                self.update_status("Nova entrada afegida")
            
            # Marcar com modificat
            self.csv_data_modified = True
            
            # Netejar camps
            self.cancel_csv_edit()
            
            # Actualitzar altres components
            self.update_file_tree()
            if hasattr(self, 'box_combo'):
                self.update_box_combo()
            if hasattr(self, 'object_combo'):
                self.update_object_combo()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error aplicant canvis: {e}")

    def cancel_csv_edit(self):
        """Cancel·la l'edició actual."""
        try:
            # Netejar camps
            self.edit_type_var.set("box")
            self.edit_name_var.set("")
            self.edit_path_var.set("")
            
            # Netejar mode edició
            self.editing_csv_item = None
            
            self.update_status("Edició cancel·lada")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error cancel·lant edició: {e}")

    def delete_selected_csv_entry(self):
        """Elimina l'entrada CSV seleccionada."""
        try:
            selection = self.csv_tree.selection()
            if not selection:
                messagebox.showwarning("Avís", "Selecciona una entrada per eliminar")
                return
            
            item = selection[0]
            values = self.csv_tree.item(item, "values")
            
            # Confirmar eliminació
            if messagebox.askyesno("Confirmar eliminació", 
                                  f"Eliminar entrada:\n"
                                  f"Tipus: {values[0]}\n"
                                  f"Nom: {values[1]}\n"
                                  f"Ruta: {values[2]}"):
                
                # Eliminar de metadata
                for i, entry in enumerate(self.metadata):
                    if (entry.get("type") == values[0] and 
                        entry.get("name") == values[1] and 
                        entry.get("file_path") == values[2]):
                        del self.metadata[i]
                        break
                
                # Eliminar de la taula
                self.csv_tree.delete(item)
                
                # Marcar com modificat
                self.csv_data_modified = True
                
                # Actualitzar altres components
                self.update_file_tree()
                if hasattr(self, 'box_combo'):
                    self.update_box_combo()
                if hasattr(self, 'object_combo'):
                    self.update_object_combo()
                
                self.update_status("Entrada eliminada")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error eliminant entrada: {e}")

    def browse_file_path(self):
        """Obre el diàleg per seleccionar fitxer."""
        try:
            # Oferir opcions: fitxer STP o dimensions personalitzades
            choice = messagebox.askyesnocancel(
                "Seleccionar entrada",
                "Vols seleccionar un fitxer STP existent?\n\n"
                "• Sí: Seleccionar fitxer STP\n"
                "• No: Crear amb dimensions personalitzades\n"
                "• Cancel·lar: Sortir"
            )
            
            if choice is True:
                # Seleccionar fitxer STP existent
                current_path = self.edit_path_var.get()
                initial_dir = os.path.dirname(current_path) if current_path else "."
                
                filename = filedialog.askopenfilename(
                    title="Seleccionar fitxer STP",
                    initialdir=initial_dir,
                    filetypes=[
                        ("Fitxers STP", "*.stp"),
                        ("Tots els fitxers", "*.*")
                    ]
                )
                
                if filename:
                    # Convertir a ruta relativa si és possible
                    try:
                        relative_path = os.path.relpath(filename)
                        self.edit_path_var.set(relative_path)
                    except ValueError:
                        # Si no es pot fer relativa, usar absoluta
                        self.edit_path_var.set(filename)
                        
            elif choice is False:
                # Crear amb dimensions personalitzades
                self.create_custom_box_dialog()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error seleccionant fitxer: {e}")

    def create_custom_box_dialog(self):
        """Crea un diàleg per definir dimensions personalitzades d'una caixa."""
        try:
            # Crear finestra de diàleg
            dialog = tk.Toplevel(self.root)
            dialog.title("Crear Caixa Personalitzada")
            dialog.geometry("400x350")
            dialog.resizable(False, False)
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Centrar finestra
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
            y = (dialog.winfo_screenheight() // 2) - (350 // 2)
            dialog.geometry(f"400x350+{x}+{y}")
              # Variables per dimensions (valors per defecte en cm)
            length_var = tk.DoubleVar(value=30.0)
            width_var = tk.DoubleVar(value=20.0)
            height_var = tk.DoubleVar(value=15.0)
            name_var = tk.StringVar(value="Caixa personalitzada")
            
            # Frame principal
            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Títol
            title_label = ttk.Label(main_frame, text="🔧 Crear Caixa Personalitzada", 
                                   font=('TkDefaultFont', 12, 'bold'))
            title_label.pack(pady=(0, 20))
            
            # Nom de la caixa
            name_frame = ttk.Frame(main_frame)
            name_frame.pack(fill=tk.X, pady=(0, 15))
            ttk.Label(name_frame, text="Nom de la caixa:").pack(anchor=tk.W)
            ttk.Entry(name_frame, textvariable=name_var, width=40).pack(fill=tk.X, pady=(5, 0))
              # Dimensions
            dims_frame = ttk.LabelFrame(main_frame, text="Dimensions (cm)", padding="10")
            dims_frame.pack(fill=tk.X, pady=(0, 15))
            
            # Longitud
            length_frame = ttk.Frame(dims_frame)
            length_frame.pack(fill=tk.X, pady=(0, 10))
            ttk.Label(length_frame, text="Longitud (cm):").pack(side=tk.LEFT)
            length_entry = ttk.Entry(length_frame, textvariable=length_var, width=15)
            length_entry.pack(side=tk.RIGHT)
            
            # Amplada
            width_frame = ttk.Frame(dims_frame)
            width_frame.pack(fill=tk.X, pady=(0, 10))
            ttk.Label(width_frame, text="Amplada (cm):").pack(side=tk.LEFT)
            width_entry = ttk.Entry(width_frame, textvariable=width_var, width=15)
            width_entry.pack(side=tk.RIGHT)
            
            # Altura
            height_frame = ttk.Frame(dims_frame)
            height_frame.pack(fill=tk.X)
            ttk.Label(height_frame, text="Altura (cm):").pack(side=tk.LEFT)
            height_entry = ttk.Entry(height_frame, textvariable=height_var, width=15)
            height_entry.pack(side=tk.RIGHT)
              # Volum calculat
            volume_label = ttk.Label(main_frame, text="", foreground="blue")
            volume_label.pack(pady=(10, 0))
            
            def update_volume(*args):
                try:
                    l, w, h = length_var.get(), width_var.get(), height_var.get()
                    volume = l * w * h  # Volum en cm³
                    volume_label.config(text=f"Volum: {volume:.1f} cm³")
                except:
                    volume_label.config(text="Volum: --- cm³")
            
            # Bind per actualitzar volum
            length_var.trace_add('write', update_volume)
            width_var.trace_add('write', update_volume)
            height_var.trace_add('write', update_volume)
            update_volume()
            
            # Botons
            buttons_frame = ttk.Frame(main_frame)
            buttons_frame.pack(pady=(20, 0))
            
            result = {'created': False}
            
            def create_box():
                try:
                    # Validar dimensions
                    l, w, h = length_var.get(), width_var.get(), height_var.get()
                    name = name_var.get().strip()
                    
                    if not name:
                        messagebox.showerror("Error", "El nom és obligatori")
                        return
                    
                    if l <= 0 or w <= 0 or h <= 0:
                        messagebox.showerror("Error", "Les dimensions han de ser positives")
                        return
                      # Crear fitxer virtual o generar ruta especial (convertir cm a mm per compatibilitat interna)
                    custom_path = f"custom://box/{name.replace(' ', '_')}_{l*10}x{w*10}x{h*10}.virtual"
                    
                    # Guardar les dimensions en un fitxer de metadata (convertir cm a mm)
                    self.save_custom_dimensions(name, l*10, w*10, h*10, custom_path)
                    
                    # Assignar la ruta al camp d'edició
                    self.edit_path_var.set(custom_path)
                    self.edit_name_var.set(name)
                    
                    result['created'] = True
                    dialog.destroy()
                    
                    messagebox.showinfo("Èxit", f"Caixa personalitzada creada:\n"
                                              f"Nom: {name}\n"
                                              f"Dimensions: {l} x {w} x {h} cm\n"
                                              f"Volum: {l*w*h:.1f} cm³")
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Error creant caixa: {e}")
            
            def cancel():
                dialog.destroy()
            
            ttk.Button(buttons_frame, text="✅ Crear Caixa", 
                      command=create_box).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(buttons_frame, text="❌ Cancel·lar", 
                      command=cancel).pack(side=tk.LEFT)
            
            # Focus inicial
            length_entry.focus()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error obrint diàleg: {e}")

    def save_custom_dimensions(self, name, length, width, height, custom_path):
        """Guarda les dimensions personalitzades en un fitxer de metadata."""
        try:
            # Crear directori per metadades personalitzades
            custom_dir = "data/custom"
            os.makedirs(custom_dir, exist_ok=True)
            
            # Fitxer de metadades personalitzades
            metadata_file = os.path.join(custom_dir, "custom_dimensions.json")
            
            # Carregar metadades existents
            custom_metadata = {}
            if os.path.exists(metadata_file):
                import json
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    custom_metadata = json.load(f)
              # Afegir noves dimensions
            custom_metadata[custom_path] = {
                "name": name,
                "length": length,
                "width": width,
                "height": height,
                "volume": length * width * height,  # Volum en mm³ per compatibilitat interna
                "created_at": str(datetime.datetime.now())
            }
            
            # Guardar metadades actualitzades
            import json
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(custom_metadata, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error guardant dimensions personalitzades: {e}")

    def get_custom_dimensions(self, custom_path):
        """Obté les dimensions d'una caixa personalitzada."""
        try:
            metadata_file = "data/custom/custom_dimensions.json"
            if not os.path.exists(metadata_file):
                return None
                
            import json
            with open(metadata_file, 'r', encoding='utf-8') as f:
                custom_metadata = json.load(f)
                
            return custom_metadata.get(custom_path)
        except Exception as e:
            print(f"Error llegint dimensions personalitzades: {e}")
            return None

    def reload_metadata(self):
        """Recarrega les metadades del CSV."""
        csv_path = self.csv_path_var.get()
        try:
            if not os.path.exists(csv_path):
                self.create_sample_data()
                return
            with open(csv_path, "r", encoding='utf-8') as f:
                self.metadata = list(csv.DictReader(f))
            self.update_file_tree()
            # Actualitzar comboboxes si existeixen
            if hasattr(self, 'box_combo'):
                self.update_box_combo()
            if hasattr(self, 'object_combo'):
                self.update_object_combo()
            self.update_status(f"Carregades {len(self.metadata)} entrades del CSV")
        except Exception as e:
            messagebox.showerror("Error", f"Error carregant metadades: {e}")
            self.update_status("Error carregant dades")

    def update_file_tree(self):
        """Actualitza la taula de fitxers."""
        # Netejar taula
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        # Afegir entrades
        for entry in self.metadata:
            file_path = entry.get("file_path", "")
            is_valid = self.validate_entry_file(file_path)
            
            # Determinar l'estat i icona
            if is_valid:
                if file_path.startswith("custom://"):
                    status = "🔧 Personalitzada"
                else:
                    status = "✅ Vàlid"
            else:
                status = "❌ No vàlid"
                
            self.file_tree.insert("", tk.END, values=(
                entry.get("type", ""),
                entry.get("name", ""),
                file_path,
                status
            ))

    def create_sample_data(self):
        """Crea dades de mostra."""
        try:
            # Crear directoris
            os.makedirs("boxes", exist_ok=True)
            os.makedirs("objects", exist_ok=True)
            os.makedirs("data", exist_ok=True)
            # Crear CSV de mostra
            sample_data = [
                {"type": "box", "name": "Caixa Mitjana", "file_path": "boxes/box_medium.stp"},
                {"type": "box", "name": "Caixa Gran", "file_path": "boxes/box_large.stp"},
                {"type": "object", "name": "Producte A", "file_path": "objects/product_a.stp"},
                {"type": "object", "name": "Producte B", "file_path": "objects/product_b.stp"}
            ]
            with open(CSV_PATH, "w", newline='', encoding='utf-8') as f:
                if sample_data:
                    writer = csv.DictWriter(f, fieldnames=sample_data[0].keys())
                    writer.writeheader()
                    writer.writerows(sample_data)
            self.metadata = sample_data
            self.update_file_tree()
            messagebox.showinfo("Dades de mostra",
                              "S'han creat dades de mostra.\n"
                              "Afegeix els teus fitxers STP als directoris 'boxes' i 'objects'.")
            self.update_status("Dades de mostra creades")
        except Exception as e:
            messagebox.showerror("Error", f"Error creant dades de mostra: {e}")

    def process_all_files(self):
        """Processa tots els fitxers STP."""
        if self.is_processing:
            return
        if not self.metadata:
            messagebox.showwarning("Avís", "No hi ha fitxers per processar")
            return        # Filtrar entrades vàlides
        valid_metadata = []
        for entry in self.metadata:
            if entry.get("type") in ["box", "object"] and self.validate_entry_file(entry.get("file_path", "")):
                valid_metadata.append(entry)
        if not valid_metadata:
            messagebox.showwarning("Avís", "No hi ha fitxers vàlids per processar")
            return
        boxes = [m for m in valid_metadata if m["type"] == "box"]
        objects = [m for m in valid_metadata if m["type"] == "object"]
        if not boxes or not objects:
            messagebox.showwarning("Avís", "Es necessiten caixes i objectes per processar")
            return
        # Executar processat en fil separat
        self.is_processing = True
        thread = threading.Thread(target=self._process_files_thread, args=(boxes, objects))
        thread.daemon = True
        thread.start()

    def _process_files_thread(self, boxes, objects):
        """Processa els fitxers en un fil separat."""
        try:
            total_combinations = len(boxes) * len(objects)
            current = 0
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, "🎯 PROCESSANT FITXERS STP\n")
            self.results_text.insert(tk.END, "=" * 50 + "\n\n")
            for box_info in boxes:
                if not self.is_processing:
                    break
                box_dims = self.get_entry_dimensions(box_info["file_path"])
                if not box_dims:
                    continue
                self.results_text.insert(tk.END, f"📦 Contenidor: {box_info['name']}\n")
                self.results_text.insert(tk.END, f"   Dimensions: {box_dims}\n\n")
                for obj_info in objects:
                    if not self.is_processing:
                        break
                    current += 1
                    progress = (current / total_combinations) * 100
                    self.progress_var.set(progress)
                    self.update_status(f"Processant {current}/{total_combinations}: {box_info['name']} + {obj_info['name']}")
                    obj_dims = self.get_entry_dimensions(obj_info["file_path"])
                    if not obj_dims:
                        continue
                    theoretical_max = calculate_theoretical_max(box_dims, obj_dims)
                    result = optimize_packing(box_dims, obj_dims)
                    self.results_text.insert(tk.END, f"  ➕ Objecte: {obj_info['name']}\n")
                    self.results_text.insert(tk.END, f"     📏 Dimensions: {obj_dims}\n")
                    if result["error"]:
                        self.results_text.insert(tk.END, f"     ❌ Error: {result['error']}\n")
                    else:
                        self.results_text.insert(tk.END, f"     🔢 Màxim teòric: {theoretical_max} unitats\n")
                        self.results_text.insert(tk.END, f"     ✅ Màxim real: {result['max_objects']} unitats\n")
                        self.results_text.insert(tk.END, f"     📈 Eficiència: {result['efficiency']}%\n")
                        self.results_text.insert(tk.END, f"     📦 Volum utilitzat: {result['used_volume']:.0f} mm³\n")
                    self.results_text.insert(tk.END, "\n")
                    self.results_text.see(tk.END)
                    self.root.update_idletasks()
                self.results_text.insert(tk.END, "-" * 40 + "\n\n")
            
            if self.is_processing:
                self.results_text.insert(tk.END, "✅ PROCESSAT COMPLETAT!\n")
                # Guardar automàticament els resultats de fitxers STP
                saved_file = self.save_results_to_file()
                if saved_file:
                    self.update_status(f"Processat completat - Guardat a {saved_file}")
                    self.results_text.insert(tk.END, f"💾 Resultats guardats a: {saved_file}\n")
                else:
                    self.update_status("Processat completat")
            else:
                self.results_text.insert(tk.END, "⏹️ PROCESSAT ATURAT\n")
                self.update_status("Processat aturat")
        except Exception as e:
            self.results_text.insert(tk.END, f"❌ ERROR: {e}\n")
            self.update_status("Error durant el processat")
        finally:
            self.is_processing = False
            self.progress_var.set(0)

    def stop_processing(self):
        """Atura el processat."""
        self.is_processing = False
        self.update_status("Aturant processat...")

    def calculate_manual(self):
        """Calcula l'empaquetament manual."""
        try:
            # Obtenir dimensions (en cm, convertir a mm per l'optimitzador)
            box_dims = {
                "length": self.box_length_var.get() * 10,
                "width": self.box_width_var.get() * 10,
                "height": self.box_height_var.get() * 10
            }
            obj_dims = {
                "length": self.obj_length_var.get() * 10,
                "width": self.obj_width_var.get() * 10,
                "height": self.obj_height_var.get() * 10
            }
            # Validar dimensions
            if any(v <= 0 for v in box_dims.values()) or any(v <= 0 for v in obj_dims.values()):
                messagebox.showerror("Error", "Totes les dimensions han de ser positives")
                return

            # Calcular
            self.manual_results.delete(1.0, tk.END)
            results_content = "🧮 CÀLCUL D'EMPAQUETAMENT MANUAL\n"
            results_content += "=" * 40 + "\n\n"
            results_content += f"📦 Contenidor:\n"
            results_content += f"   Longitud: {self.box_length_var.get():.1f} cm\n"
            results_content += f"   Amplada: {self.box_width_var.get():.1f} cm\n"
            results_content += f"   Altura: {self.box_height_var.get():.1f} cm\n\n"
            results_content += f"📋 Objecte:\n"
            results_content += f"   Longitud: {self.obj_length_var.get():.1f} cm\n"
            results_content += f"   Amplada: {self.obj_width_var.get():.1f} cm\n"
            results_content += f"   Altura: {self.obj_height_var.get():.1f} cm\n\n"
            self.manual_results.insert(tk.END, results_content)

            theoretical_max = calculate_theoretical_max(box_dims, obj_dims)
            result = optimize_packing(box_dims, obj_dims)

            results_content = "📊 RESULTATS:\n"
            if result["error"]:
                results_content += f"   ❌ Error: {result['error']}\n"
                self.visualize_btn.config(state=tk.DISABLED)
            else:
                results_content += f"   ✅ Màxim real (3D packing): {result['max_objects']} unitats\n"
                results_content += f"   📈 Eficiència d'espai: {result['efficiency']:.1f}%\n"
                results_content += f"   📏 Volum contenidor: {result['box_volume']/1000:.1f} cm³\n"
                results_content += f"   📦 Volum utilitzat: {result['used_volume']/1000:.1f} cm³\n"
                if result['max_objects'] > 0:
                    self.visualize_btn.config(state=tk.NORMAL)
                else:
                    self.visualize_btn.config(state=tk.DISABLED)

            # Mostrar resultats a pestanya manual
            self.manual_results.insert(tk.END, results_content)

            # Afegir les dades a la pestanya de resultats i guardar
            self.add_to_results_tab(results_content)
            saved_file = self.save_results_to_file()
            if saved_file:
                self.update_status(f"Càlcul manual completat - Guardat a {saved_file}")
            else:
                self.update_status("Càlcul manual completat")
        except ValueError:
            messagebox.showerror("Error", "Introdueix valors numèrics vàlids")
        except Exception as e:
            messagebox.showerror("Error", f"Error durant el càlcul: {e}")

    def export_results(self):
        """Exporta els resultats a un fitxer."""
        content = self.results_text.get(1.0, tk.END)
        if not content.strip():
            messagebox.showwarning("Avís", "No hi ha resultats per exportar")
            return
        filename = filedialog.asksaveasfilename(
            title="Exportar resultats",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Èxit", f"Resultats exportats a:\n{filename}")
                self.update_status("Resultats exportats")
            except Exception as e:
                messagebox.showerror("Error", f"Error exportant resultats: {e}")
    
    def clear_results(self):
        """Neteja els resultats."""
        self.results_text.delete(1.0, tk.END)
        self.update_status("Resultats netejats")

    def toggle_input_method(self):
        """Toggle entre entrada manual, fitxer i objectes importats."""
        method = self.input_method_var.get()
        # Ocultar tots els frames primer
        self.file_input_frame.grid_remove()
        self.manual_input_frame.grid_remove()
        self.object_selection_frame.grid_remove()
        if method == "manual":
            self.manual_input_frame.grid()
        elif method == "file":
            self.file_input_frame.grid()
        elif method == "imported":
            self.object_selection_frame.grid()
            self.update_object_combo()

    def toggle_box_input(self):
        """Toggle entre entrada manual i selecció de caixes importades."""
        method = self.box_source_var.get()
        if method == "manual":
            self.box_selection_frame.grid_remove()
            self.manual_box_frame.grid()
        else:
            self.manual_box_frame.grid_remove()
            self.box_selection_frame.grid()
            self.update_box_combo()

    def update_box_combo(self):
        """Actualitza el combobox de caixes amb les caixes disponibles."""
        boxes = [entry for entry in self.metadata if entry.get("type") == "box"]
        box_names = [f"{box['name']} ({box['file_path']})" for box in boxes]
        self.box_combo['values'] = box_names
        if box_names:
            self.box_combo.set(box_names[0])
            self.on_box_selected(None)

    def update_object_combo(self):
        """Actualitza el combobox d'objectes amb els objectes disponibles."""
        objects = [entry for entry in self.metadata if entry.get("type") == "object"]
        object_names = [f"{obj['name']} ({obj['file_path']})" for obj in objects]
        self.object_combo['values'] = object_names
        if object_names:
            self.object_combo.set(object_names[0])
            self.on_object_selected(None)

    def on_box_selected(self, event):
        """Event quan es selecciona una caixa del combobox."""
        selected = self.selected_box_var.get()
        if not selected:
            return
        # Extreure el nom del fitxer de la selecció
        file_path = selected.split('(')[-1].split(')')[0]
        # Buscar l'entrada corresponent
        box_entry = None
        for entry in self.metadata:
            if entry.get("type") == "box" and entry.get("file_path") == file_path:
                box_entry = entry
                break
        if box_entry:
            # Obtenir dimensions utilitzant la nova funció unificada
            dimensions = self.get_entry_dimensions(file_path)
            if dimensions:
                self.box_length_var.set(dimensions['length'])
                self.box_width_var.set(dimensions['width'])
                self.box_height_var.set(dimensions['height'])

    def on_object_selected(self, event):
        """Event quan es selecciona un objecte del combobox."""
        selected = self.selected_object_var.get()
        if not selected:
            return
        # Extreure el nom del fitxer de la selecció
        file_path = selected.split('(')[-1].split(')')[0]
        # Buscar l'entrada corresponent
        object_entry = None
        for entry in self.metadata:
            if entry.get("type") == "object" and entry.get("file_path") == file_path:
                object_entry = entry
                break
        if object_entry:
            # Obtenir dimensions utilitzant la nova funció unificada
            dimensions = self.get_entry_dimensions(file_path)
            if dimensions:
                self.obj_length_var.set(dimensions['length'])
                self.obj_width_var.set(dimensions['width'])
                self.obj_height_var.set(dimensions['height'])

    def browse_3d_file(self):
        """Obre un diàleg per seleccionar un fitxer 3D (STP/STL)."""
        filetypes = []
        if STL_SUPPORT:
            filetypes.append(("Fitxers 3D", "*.stp;*.step;*.stl"))
            filetypes.append(("Fitxers STL", "*.stl"))
        filetypes.append(("Fitxers STP", "*.stp;*.step"))
        filetypes.append(("Tots els fitxers", "*.*"))
        filepath = filedialog.askopenfilename(
            title="Selecciona un fitxer 3D",
            filetypes=filetypes
        )
        if not filepath:
            return
        self.file_path_var.set(filepath)
        self.update_file_info(filepath)

    def update_file_info(self, filepath):
        """Actualitza la informació de dimensions del fitxer 3D seleccionat."""
        if not filepath:
            self.file_info_var.set("Dimensions: - x - x - mm")
            return
        try:
            # Determinar quin tipus de fitxer és
            if filepath.lower().endswith(('.stp', '.step')):
                dimensions = get_stp_dimensions(filepath)
            elif filepath.lower().endswith('.stl') and STL_SUPPORT:
                dimensions = get_stl_dimensions(filepath)
            else:
                self.file_info_var.set("Format de fitxer no suportat")
                return
            if dimensions:
                info = f"Dimensions: {dimensions['length']} x {dimensions['width']} x {dimensions['height']} mm"
                self.file_info_var.set(info)
                # Actualitzar les variables per les dimensions
                self.obj_length_var.set(dimensions['length'])
                self.obj_width_var.set(dimensions['width'])
                self.obj_height_var.set(dimensions['height'])
            else:
                self.file_info_var.set("Error llegint fitxer")
        except Exception as e:
            self.file_info_var.set(f"Error: {str(e)}")

    def create_visualization_section(self):
        """Crea la secció de visualització 3D."""
        self.viz_frame = ttk.LabelFrame(self.main_frame, text="🎯 Visualització 3D", padding="10")
        self.viz_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)  # Corregit índex de fila        # Botó de visualització
        viz_buttons_frame = ttk.Frame(self.viz_frame)
        viz_buttons_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.visualize_btn = ttk.Button(
            viz_buttons_frame,
            text="📊 Visualitzar Empaquetament",
            command=self.visualize_packing,
            state=tk.DISABLED
        )
        self.visualize_btn.grid(row=0, column=0, padx=5)
        
        # Botó per tancar la visualització
        self.close_viz_btn = ttk.Button(
            viz_buttons_frame,
            text="❌ Tancar Visualització",
            command=self.close_visualization,
            state=tk.DISABLED
        )
        self.close_viz_btn.grid(row=0, column=1, padx=5)
        # Frame per al canvas de matplotlib
        self.canvas_frame = ttk.Frame(self.viz_frame)
        self.canvas_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

    def visualize_packing(self):
        """Mostra la visualització 3D dels resultats d'empaquetament."""
        if not hasattr(self, 'optimization_results') or not self.optimization_results:
            messagebox.showwarning("Advertència", "No hi ha resultats d'optimització per visualitzar.")
            return
        try:
            # Neteja el canvas anterior si existeix
            if hasattr(self, 'canvas'):
                self.canvas.get_tk_widget().destroy()
            if hasattr(self, 'toolbar'):
                self.toolbar.destroy()
            
            # Crear figura de matplotlib
            fig = Figure(figsize=(12, 8), dpi=100)
            results = self.optimization_results
            # Crear subplots per cada bin utilitzat
            num_bins = len(results['bins'])
            cols = min(3, num_bins)  # Màxim 3 columnes
            rows = (num_bins + cols - 1) // cols
            axes = []
            for i, bin_result in enumerate(results['bins']):
                ax = fig.add_subplot(rows, cols, i+1, projection='3d')
                axes.append(ax)
                # Obtenir la informació del bin
                bin_data = bin_result['bin']
                items = bin_result['items']
                # Dibuixar el contenidor (bin)
                self.draw_bin_wireframe(ax, bin_data)
                # Dibuixar els objectes
                for j, item in enumerate(items):
                    self.draw_item_3d(ax, item, j)
                # Configurar l'axes
                ax.set_xlabel('Longitud (mm)')
                ax.set_ylabel('Amplada (mm)')
                ax.set_zlabel('Altura (mm)')
                ax.set_title(f'Contenidor {i+1}: {bin_data["name"]}')
                # Fer els axes iguals
                self.set_axes_equal_3d(ax)
            plt.tight_layout()            # Integrar amb Tkinter
            self.canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            # Afegir barra d'eines
            self.toolbar = NavigationToolbar2Tk(self.canvas, self.canvas_frame)
            self.toolbar.update()
            # Habilitar botó de tancar
            self.close_viz_btn.config(state=tk.NORMAL)
            self.update_status("Visualització 3D generada correctament")
        except Exception as e:
            messagebox.showerror("Error", f"Error generant visualització 3D: {e}")
            print(f"Error detallat: {e}")

    def draw_bin_wireframe(self, ax, bin_data):
        """Dibuixa el wireframe del contenidor."""
        # Assegurar que les dimensions són floats
        w = float(bin_data['dimensions'][0])
        h = float(bin_data['dimensions'][1])
        d = float(bin_data['dimensions'][2])
        # Definir els vèrtexs del cub
        vertices = [
            [0, 0, 0], [w, 0, 0], [w, h, 0], [0, h, 0],  # base inferior
            [0, 0, d], [w, 0, d], [w, h, d], [0, h, d]   # base superior
        ]
        # Definir les arestes
        edges = [
            [0, 1], [1, 2], [2, 3], [3, 0],  # base inferior
            [4, 5], [5, 6], [6, 7], [7, 4],  # base superior
            [0, 4], [1, 5], [2, 6], [3, 7]   # arestes verticals
        ]
        # Dibuixar les arestes
        for edge in edges:
            points = [[v for v in vertices[edge[0]]], [v for v in vertices[edge[1]]]]
            points_x = [p[0] for p in points]
            points_y = [p[1] for p in points]
            points_z = [p[2] for p in points]
            ax.plot3D(points_x, points_y, points_z, color='black', linewidth=2, alpha=0.8)

    def draw_item_3d(self, ax, item, index):
        """Dibuixa un objecte en 3D."""
        pos = item['position']
        dims = item['dimensions']
        # Convertir a floats
        x = float(pos[0])
        y = float(pos[1])
        z = float(pos[2])
        w = float(dims[0])
        h = float(dims[1])
        d = float(dims[2])
        # Coordenades del cub
        vertices = [
            [x, y, z],
            [x+w, y, z],
            [x+w, y+h, z],
            [x, y+h, z],
            [x, y, z+d],
            [x+w, y, z+d],
            [x+w, y+h, z+d],
            [x, y+h, z+d]
        ]
        # Color basat en l'índex
        colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
        color = colors[index % len(colors)]
        # Definir les 6 cares del cub
        faces = [
            [vertices[0], vertices[1], vertices[2], vertices[3]],  # base inferior
            [vertices[4], vertices[5], vertices[6], vertices[7]],  # base superior
            [vertices[0], vertices[1], vertices[5], vertices[4]],  # cara frontal
            [vertices[2], vertices[3], vertices[7], vertices[6]],  # cara posterior
            [vertices[1], vertices[2], vertices[6], vertices[5]],  # cara dreta
            [vertices[4], vertices[7], vertices[3], vertices[0]]   # cara esquerra
        ]
        # Dibuixar cada cara
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        for face in faces:
            poly = Poly3DCollection([face], alpha=0.7, facecolor=color, edgecolor='black')
            ax.add_collection3d(poly)

    def set_axes_equal_3d(self, ax):
        """Fa que els eixos 3D tinguin la mateixa escala."""
        # Obtenir els límits actuals
        x_limits = ax.get_xlim3d()
        y_limits = ax.get_ylim3d()
        z_limits = ax.get_zlim3d()
        # Calcular els rangs
        x_range = abs(x_limits[1] - x_limits[0])
        x_middle = sum(x_limits) / 2
        y_range = abs(y_limits[1] - y_limits[0])
        y_middle = sum(y_limits) / 2
        z_range = abs(z_limits[1] - z_limits[0])
        z_middle = sum(z_limits) / 2
        # El radi del plot és la meitat del rang màxim
        plot_radius = 0.5 * max([x_range, y_range, z_range])
        ax.set_xlim3d([x_middle - plot_radius, x_middle + plot_radius])
        ax.set_ylim3d([y_middle - plot_radius, y_middle + plot_radius])
        ax.set_zlim3d([z_middle - plot_radius, z_middle + plot_radius])

    def close_visualization(self):
        """Tanca la visualització 3D i neteja els recursos."""
        try:
            # Destruir canvas si existeix
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.get_tk_widget().destroy()
                self.canvas = None
            
            # Destruir toolbar si existeix
            if hasattr(self, 'toolbar') and self.toolbar:
                self.toolbar.destroy()
                self.toolbar = None
            
            # Netejar tots els widgets del canvas_frame
            for widget in self.canvas_frame.winfo_children():
                widget.destroy()
            
            # Deshabilitar botó de tancar
            self.close_viz_btn.config(state=tk.DISABLED)
            
            self.update_status("Visualització 3D tancada")
            
        except Exception as e:
            print(f"Error tancant visualització: {e}")
            messagebox.showerror("Error", f"Error tancant visualització: {e}")

    def add_to_results_tab(self, content):
        """Afegeix contingut a la pestanya de resultats per mantenir un històric complet."""
        try:
            # Afegir timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.results_text.insert(tk.END, f"\n[{timestamp}] ")
            self.results_text.insert(tk.END, content)
            self.results_text.insert(tk.END, "\n" + "="*60 + "\n")
            self.results_text.see(tk.END)
        except Exception as e:
            print(f"Error afegint a la pestanya de resultats: {e}")
    
    def save_results_to_file(self, filename=None):
        """Guarda tots els resultats a un fitxer automàticament."""
        if not filename:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/packassist_results_{timestamp}.txt"
        
        try:
            # Crear directori de resultats si no existeix
            os.makedirs("results", exist_ok=True)
            
            content = self.results_text.get(1.0, tk.END)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            return filename
        except Exception as e:
            print(f"Error guardant resultats: {e}")
            return None

    def validate_entry_file(self, file_path):
        """Valida si un fitxer o entrada personalitzada és vàlid."""
        if not file_path:
            return False
            
        # Comprovar si és una caixa personalitzada
        if file_path.startswith("custom://"):
            return self.get_custom_dimensions(file_path) is not None
            
        # Comprovar fitxer STP normal
        return validate_stp_file(file_path)
    
    def get_entry_dimensions(self, file_path):
        """Obté les dimensions d'un fitxer o entrada personalitzada."""
        if not file_path:
            return None
            
        # Comprovar si és una caixa personalitzada
        if file_path.startswith("custom://"):
            custom_dims = self.get_custom_dimensions(file_path)
            if custom_dims:
                return {
                    "length": custom_dims["length"],
                    "width": custom_dims["width"], 
                    "height": custom_dims["height"]
                }
            return None
            
        # Obtenir dimensions de fitxer STP normal
        return get_stp_dimensions(file_path)

    def reload_metadata(self):
        """Recarrega les metadades del CSV."""
        csv_path = self.csv_path_var.get()
        try:
            if not os.path.exists(csv_path):
                self.create_sample_data()
                return
            with open(csv_path, "r", encoding='utf-8') as f:
                self.metadata = list(csv.DictReader(f))
            self.update_file_tree()
            # Actualitzar comboboxes si existeixen
            if hasattr(self, 'box_combo'):
                self.update_box_combo()
            if hasattr(self, 'object_combo'):
                self.update_object_combo()
            self.update_status(f"Carregades {len(self.metadata)} entrades del CSV")
        except Exception as e:
            messagebox.showerror("Error", f"Error carregant metadades: {e}")
            self.update_status("Error carregant dades")

    def update_file_tree(self):
        """Actualitza la taula de fitxers."""
        # Netejar taula
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        # Afegir entrades
        for entry in self.metadata:
            file_path = entry.get("file_path", "")
            is_valid = self.validate_entry_file(file_path)
            
            # Determinar l'estat i icona
            if is_valid:
                if file_path.startswith("custom://"):
                    status = "🔧 Personalitzada"
                else:
                    status = "✅ Vàlid"
            else:
                status = "❌ No vàlid"
                
            self.file_tree.insert("", tk.END, values=(
                entry.get("type", ""),
                entry.get("name", ""),
                file_path,
                status
            ))

    def create_sample_data(self):
        """Crea dades de mostra."""
        try:
            # Crear directoris
            os.makedirs("boxes", exist_ok=True)
            os.makedirs("objects", exist_ok=True)
            os.makedirs("data", exist_ok=True)
            # Crear CSV de mostra
            sample_data = [
                {"type": "box", "name": "Caixa Mitjana", "file_path": "boxes/box_medium.stp"},
                {"type": "box", "name": "Caixa Gran", "file_path": "boxes/box_large.stp"},
                {"type": "object", "name": "Producte A", "file_path": "objects/product_a.stp"},
                {"type": "object", "name": "Producte B", "file_path": "objects/product_b.stp"}
            ]
            with open(CSV_PATH, "w", newline='', encoding='utf-8') as f:
                if sample_data:
                    writer = csv.DictWriter(f, fieldnames=sample_data[0].keys())
                    writer.writeheader()
                    writer.writerows(sample_data)
            self.metadata = sample_data
            self.update_file_tree()
            messagebox.showinfo("Dades de mostra",
                              "S'han creat dades de mostra.\n"
                              "Afegeix els teus fitxers STP als directoris 'boxes' i 'objects'.")
            self.update_status("Dades de mostra creades")
        except Exception as e:
            messagebox.showerror("Error", f"Error creant dades de mostra: {e}")

    def process_all_files(self):
        """Processa tots els fitxers STP."""
        if self.is_processing:
            return
        if not self.metadata:
            messagebox.showwarning("Avís", "No hi ha fitxers per processar")
            return        # Filtrar entrades vàlides
        valid_metadata = []
        for entry in self.metadata:
            if entry.get("type") in ["box", "object"] and self.validate_entry_file(entry.get("file_path", "")):
                valid_metadata.append(entry)
        if not valid_metadata:
            messagebox.showwarning("Avís", "No hi ha fitxers vàlids per processar")
            return
        boxes = [m for m in valid_metadata if m["type"] == "box"]
        objects = [m for m in valid_metadata if m["type"] == "object"]
        if not boxes or not objects:
            messagebox.showwarning("Avís", "Es necessiten caixes i objectes per processar")
            return
        # Executar processat en fil separat
        self.is_processing = True
        thread = threading.Thread(target=self._process_files_thread, args=(boxes, objects))
        thread.daemon = True
        thread.start()

    def _process_files_thread(self, boxes, objects):
        """Processa els fitxers en un fil separat."""
        try:
            total_combinations = len(boxes) * len(objects)
            current = 0
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, "🎯 PROCESSANT FITXERS STP\n")
            self.results_text.insert(tk.END, "=" * 50 + "\n\n")
            for box_info in boxes:
                if not self.is_processing:
                    break
                box_dims = self.get_entry_dimensions(box_info["file_path"])
                if not box_dims:
                    continue
                self.results_text.insert(tk.END, f"📦 Contenidor: {box_info['name']}\n")
                self.results_text.insert(tk.END, f"   Dimensions: {box_dims}\n\n")
                for obj_info in objects:
                    if not self.is_processing:
                        break
                    current += 1
                    progress = (current / total_combinations) * 100
                    self.progress_var.set(progress)
                    self.update_status(f"Processant {current}/{total_combinations}: {box_info['name']} + {obj_info['name']}")
                    obj_dims = self.get_entry_dimensions(obj_info["file_path"])
                    if not obj_dims:
                        continue
                    theoretical_max = calculate_theoretical_max(box_dims, obj_dims)
                    result = optimize_packing(box_dims, obj_dims)
                    self.results_text.insert(tk.END, f"  ➕ Objecte: {obj_info['name']}\n")
                    self.results_text.insert(tk.END, f"     📏 Dimensions: {obj_dims}\n")
                    if result["error"]:
                        self.results_text.insert(tk.END, f"     ❌ Error: {result['error']}\n")
                    else:
                        self.results_text.insert(tk.END, f"     🔢 Màxim teòric: {theoretical_max} unitats\n")
                        self.results_text.insert(tk.END, f"     ✅ Màxim real: {result['max_objects']} unitats\n")
                        self.results_text.insert(tk.END, f"     📈 Eficiència: {result['efficiency']}%\n")
                        self.results_text.insert(tk.END, f"     📦 Volum utilitzat: {result['used_volume']:.0f} mm³\n")
                    self.results_text.insert(tk.END, "\n")
                    self.results_text.see(tk.END)
                    self.root.update_idletasks()
                self.results_text.insert(tk.END, "-" * 40 + "\n\n")
            
            if self.is_processing:
                self.results_text.insert(tk.END, "✅ PROCESSAT COMPLETAT!\n")
                # Guardar automàticament els resultats de fitxers STP
                saved_file = self.save_results_to_file()
                if saved_file:
                    self.update_status(f"Processat completat - Guardat a {saved_file}")
                    self.results_text.insert(tk.END, f"💾 Resultats guardats a: {saved_file}\n")
                else:
                    self.update_status("Processat completat")
            else:
                self.results_text.insert(tk.END, "⏹️ PROCESSAT ATURAT\n")
                self.update_status("Processat aturat")
        except Exception as e:
            self.results_text.insert(tk.END, f"❌ ERROR: {e}\n")
            self.update_status("Error durant el processat")
        finally:
            self.is_processing = False
            self.progress_var.set(0)

    def stop_processing(self):
        """Atura el processat."""
        self.is_processing = False
        self.update_status("Aturant processat...")

    def calculate_manual(self):
        """Calcula l'empaquetament manual."""
        try:
            # Obtenir dimensions (en cm, convertir a mm per l'optimitzador)
            box_dims = {
                "length": self.box_length_var.get() * 10,
                "width": self.box_width_var.get() * 10,
                "height": self.box_height_var.get() * 10
            }
            obj_dims = {
                "length": self.obj_length_var.get() * 10,
                "width": self.obj_width_var.get() * 10,
                "height": self.obj_height_var.get() * 10
            }
            # Validar dimensions
            if any(v <= 0 for v in box_dims.values()) or any(v <= 0 for v in obj_dims.values()):
                messagebox.showerror("Error", "Totes les dimensions han de ser positives")
                return

            # Calcular
            self.manual_results.delete(1.0, tk.END)
            results_content = "🧮 CÀLCUL D'EMPAQUETAMENT MANUAL\n"
            results_content += "=" * 40 + "\n\n"
            results_content += f"📦 Contenidor:\n"
            results_content += f"   Longitud: {self.box_length_var.get():.1f} cm\n"
            results_content += f"   Amplada: {self.box_width_var.get():.1f} cm\n"
            results_content += f"   Altura: {self.box_height_var.get():.1f} cm\n\n"
            results_content += f"📋 Objecte:\n"
            results_content += f"   Longitud: {self.obj_length_var.get():.1f} cm\n"
            results_content += f"   Amplada: {self.obj_width_var.get():.1f} cm\n"
            results_content += f"   Altura: {self.obj_height_var.get():.1f} cm\n\n"
            self.manual_results.insert(tk.END, results_content)

            theoretical_max = calculate_theoretical_max(box_dims, obj_dims)
            result = optimize_packing(box_dims, obj_dims)

            results_content = "📊 RESULTATS:\n"
            if result["error"]:
                results_content += f"   ❌ Error: {result['error']}\n"
                self.visualize_btn.config(state=tk.DISABLED)
            else:
                results_content += f"   ✅ Màxim real (3D packing): {result['max_objects']} unitats\n"
                results_content += f"   📈 Eficiència d'espai: {result['efficiency']:.1f}%\n"
                results_content += f"   📏 Volum contenidor: {result['box_volume']/1000:.1f} cm³\n"
                results_content += f"   📦 Volum utilitzat: {result['used_volume']/1000:.1f} cm³\n"
                if result['max_objects'] > 0:
                    self.visualize_btn.config(state=tk.NORMAL)
                else:
                    self.visualize_btn.config(state=tk.DISABLED)

            # Mostrar resultats a pestanya manual
            self.manual_results.insert(tk.END, results_content)

            # Afegir les dades a la pestanya de resultats i guardar
            self.add_to_results_tab(results_content)
            saved_file = self.save_results_to_file()
            if saved_file:
                self.update_status(f"Càlcul manual completat - Guardat a {saved_file}")
            else:
                self.update_status("Càlcul manual completat")
        except ValueError:
            messagebox.showerror("Error", "Introdueix valors numèrics vàlids")
        except Exception as e:
            messagebox.showerror("Error", f"Error durant el càlcul: {e}")

    def export_results(self):
        """Exporta els resultats a un fitxer."""
        content = self.results_text.get(1.0, tk.END)
        if not content.strip():
            messagebox.showwarning("Avís", "No hi ha resultats per exportar")
            return
        filename = filedialog.asksaveasfilename(
            title="Exportar resultats",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Èxit", f"Resultats exportats a:\n{filename}")
                self.update_status("Resultats exportats")
            except Exception as e:
                messagebox.showerror("Error", f"Error exportant resultats: {e}")
    
    def clear_results(self):
        """Neteja els resultats."""
        self.results_text.delete(1.0, tk.END)
        self.update_status("Resultats netejats")

    def toggle_input_method(self):
        """Toggle entre entrada manual, fitxer i objectes importats."""
        method = self.input_method_var.get()
        # Ocultar tots els frames primer
        self.file_input_frame.grid_remove()
        self.manual_input_frame.grid_remove()
        self.object_selection_frame.grid_remove()
        if method == "manual":
            self.manual_input_frame.grid()
        elif method == "file":
            self.file_input_frame.grid()
        elif method == "imported":
            self.object_selection_frame.grid()
            self.update_object_combo()

    def toggle_box_input(self):
        """Toggle entre entrada manual i selecció de caixes importades."""
        method = self.box_source_var.get()
        if method == "manual":
            self.box_selection_frame.grid_remove()
            self.manual_box_frame.grid()
        else:
            self.manual_box_frame.grid_remove()
            self.box_selection_frame.grid()
            self.update_box_combo()

    def update_box_combo(self):
        """Actualitza el combobox de caixes amb les caixes disponibles."""
        boxes = [entry for entry in self.metadata if entry.get("type") == "box"]
        box_names = [f"{box['name']} ({box['file_path']})" for box in boxes]
        self.box_combo['values'] = box_names
        if box_names:
            self.box_combo.set(box_names[0])
            self.on_box_selected(None)

    def update_object_combo(self):
        """Actualitza el combobox d'objectes amb els objectes disponibles."""
        objects = [entry for entry in self.metadata if entry.get("type") == "object"]
        object_names = [f"{obj['name']} ({obj['file_path']})" for obj in objects]
        self.object_combo['values'] = object_names
        if object_names:
            self.object_combo.set(object_names[0])
            self.on_object_selected(None)

    def on_box_selected(self, event):
        """Event quan es selecciona una caixa del combobox."""
        selected = self.selected_box_var.get()
        if not selected:
            return
        # Extreure el nom del fitxer de la selecció
        file_path = selected.split('(')[-1].split(')')[0]
        # Buscar l'entrada corresponent
        box_entry = None
        for entry in self.metadata:
            if entry.get("type") == "box" and entry.get("file_path") == file_path:
                box_entry = entry
                break
        if box_entry:
            # Obtenir dimensions utilitzant la nova funció unificada
            dimensions = self.get_entry_dimensions(file_path)
            if dimensions:
                self.box_length_var.set(dimensions['length'])
                self.box_width_var.set(dimensions['width'])
                self.box_height_var.set(dimensions['height'])

    def on_object_selected(self, event):
        """Event quan es selecciona un objecte del combobox."""
        selected = self.selected_object_var.get()
        if not selected:
            return
        # Extreure el nom del fitxer de la selecció
        file_path = selected.split('(')[-1].split(')')[0]
        # Buscar l'entrada corresponent
        object_entry = None
        for entry in self.metadata:
            if entry.get("type") == "object" and entry.get("file_path") == file_path:
                object_entry = entry
                break
        if object_entry:
            # Obtenir dimensions utilitzant la nova funció unificada
            dimensions = self.get_entry_dimensions(file_path)
            if dimensions:
                self.obj_length_var.set(dimensions['length'])
                self.obj_width_var.set(dimensions['width'])
                self.obj_height_var.set(dimensions['height'])

    def browse_3d_file(self):
        """Obre un diàleg per seleccionar un fitxer 3D (STP/STL)."""
        filetypes = []
        if STL_SUPPORT:
            filetypes.append(("Fitxers 3D", "*.stp;*.step;*.stl"))
            filetypes.append(("Fitxers STL", "*.stl"))
        filetypes.append(("Fitxers STP", "*.stp;*.step"))
        filetypes.append(("Tots els fitxers", "*.*"))
        filepath = filedialog.askopenfilename(
            title="Selecciona un fitxer 3D",
            filetypes=filetypes
        )
        if not filepath:
            return
        self.file_path_var.set(filepath)
        self.update_file_info(filepath)

    def update_file_info(self, filepath):
        """Actualitza la informació de dimensions del fitxer 3D seleccionat."""
        if not filepath:
            self.file_info_var.set("Dimensions: - x - x - mm")
            return
        try:
            # Determinar quin tipus de fitxer és
            if filepath.lower().endswith(('.stp', '.step')):
                dimensions = get_stp_dimensions(filepath)
            elif filepath.lower().endswith('.stl') and STL_SUPPORT:
                dimensions = get_stl_dimensions(filepath)
            else:
                self.file_info_var.set("Format de fitxer no suportat")
                return
            if dimensions:
                info = f"Dimensions: {dimensions['length']} x {dimensions['width']} x {dimensions['height']} mm"
                self.file_info_var.set(info)
                # Actualitzar les variables per les dimensions
                self.obj_length_var.set(dimensions['length'])
                self.obj_width_var.set(dimensions['width'])
                self.obj_height_var.set(dimensions['height'])
            else:
                self.file_info_var.set("Error llegint fitxer")
        except Exception as e:
            self.file_info_var.set(f"Error: {str(e)}")

    def create_visualization_section(self):
        """Crea la secció de visualització 3D."""
        self.viz_frame = ttk.LabelFrame(self.main_frame, text="🎯 Visualització 3D", padding="10")
        self.viz_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)  # Corregit índex de fila        # Botó de visualització
        viz_buttons_frame = ttk.Frame(self.viz_frame)
        viz_buttons_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.visualize_btn = ttk.Button(
            viz_buttons_frame,
            text="📊 Visualitzar Empaquetament",
            command=self.visualize_packing,
            state=tk.DISABLED
        )
        self.visualize_btn.grid(row=0, column=0, padx=5)
        
        # Botó per tancar la visualització
        self.close_viz_btn = ttk.Button(
            viz_buttons_frame,
            text="❌ Tancar Visualització",
            command=self.close_visualization,
            state=tk.DISABLED
        )
        self.close_viz_btn.grid(row=0, column=1, padx=5)
        # Frame per al canvas de matplotlib
        self.canvas_frame = ttk.Frame(self.viz_frame)
        self.canvas_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

    def visualize_packing(self):
        """Mostra la visualització 3D dels resultats d'empaquetament."""
        if not hasattr(self, 'optimization_results') or not self.optimization_results:
            messagebox.showwarning("Advertència", "No hi ha resultats d'optimització per visualitzar.")
            return
        try:
            # Neteja el canvas anterior si existeix
            if hasattr(self, 'canvas'):
                self.canvas.get_tk_widget().destroy()
            if hasattr(self, 'toolbar'):
                self.toolbar.destroy()
            
            # Crear figura de matplotlib
            fig = Figure(figsize=(12, 8), dpi=100)
            results = self.optimization_results
            # Crear subplots per cada bin utilitzat
            num_bins = len(results['bins'])
            cols = min(3, num_bins)  # Màxim 3 columnes
            rows = (num_bins + cols - 1) // cols
            axes = []
            for i, bin_result in enumerate(results['bins']):
                ax = fig.add_subplot(rows, cols, i+1, projection='3d')
                axes.append(ax)
                # Obtenir la informació del bin
                bin_data = bin_result['bin']
                items = bin_result['items']
                # Dibuixar el contenidor (bin)
                self.draw_bin_wireframe(ax, bin_data)
                # Dibuixar els objectes
                for j, item in enumerate(items):
                    self.draw_item_3d(ax, item, j)
                # Configurar l'axes
                ax.set_xlabel('Longitud (mm)')
                ax.set_ylabel('Amplada (mm)')
                ax.set_zlabel('Altura (mm)')
                ax.set_title(f'Contenidor {i+1}: {bin_data["name"]}')
                # Fer els axes iguals
                self.set_axes_equal_3d(ax)
            plt.tight_layout()            # Integrar amb Tkinter
            self.canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            # Afegir barra d'eines
            self.toolbar = NavigationToolbar2Tk(self.canvas, self.canvas_frame)
            self.toolbar.update()
            # Habilitar botó de tancar
            self.close_viz_btn.config(state=tk.NORMAL)
            self.update_status("Visualització 3D generada correctament")
        except Exception as e:
            messagebox.showerror("Error", f"Error generant visualització 3D: {e}")
            print(f"Error detallat: {e}")

    def draw_bin_wireframe(self, ax, bin_data):
        """Dibuixa el wireframe del contenidor."""
        # Assegurar que les dimensions són floats
        w = float(bin_data['dimensions'][0])
        h = float(bin_data['dimensions'][1])
        d = float(bin_data['dimensions'][2])
        # Definir els vèrtexs del cub
        vertices = [
            [0, 0, 0], [w, 0, 0], [w, h, 0], [0, h, 0],  # base inferior
            [0, 0, d], [w, 0, d], [w, h, d], [0, h, d]   # base superior
        ]
        # Definir les arestes
        edges = [
            [0, 1], [1, 2], [2, 3], [3, 0],  # base inferior
            [4, 5], [5, 6], [6, 7], [7, 4],  # base superior
            [0, 4], [1, 5], [2, 6], [3, 7]   # arestes verticals
        ]
        # Dibuixar les arestes
        for edge in edges:
            points = [[v for v in vertices[edge[0]]], [v for v in vertices[edge[1]]]]
            points_x = [p[0] for p in points]
            points_y = [p[1] for p in points]
            points_z = [p[2] for p in points]
            ax.plot3D(points_x, points_y, points_z, color='black', linewidth=2, alpha=0.8)

    def draw_item_3d(self, ax, item, index):
        """Dibuixa un objecte en 3D."""
        pos = item['position']
        dims = item['dimensions']
        # Convertir a floats
        x = float(pos[0])
        y = float(pos[1])
        z = float(pos[2])
        w = float(dims[0])
        h = float(dims[1])
        d = float(dims[2])
        # Coordenades del cub
        vertices = [
            [x, y, z],
            [x+w, y, z],
            [x+w, y+h, z],
            [x, y+h, z],
            [x, y, z+d],
            [x+w, y, z+d],
            [x+w, y+h, z+d],
            [x, y+h, z+d]
        ]
        # Color basat en l'índex
        colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
        color = colors[index % len(colors)]
        # Definir les 6 cares del cub
        faces = [
            [vertices[0], vertices[1], vertices[2], vertices[3]],  # base inferior
            [vertices[4], vertices[5], vertices[6], vertices[7]],  # base superior
            [vertices[0], vertices[1], vertices[5], vertices[4]],  # cara frontal
            [vertices[2], vertices[3], vertices[7], vertices[6]],  # cara posterior
            [vertices[1], vertices[2], vertices[6], vertices[5]],  # cara dreta
            [vertices[4], vertices[7], vertices[3], vertices[0]]   # cara esquerra
        ]
        # Dibuixar cada cara
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        for face in faces:
            poly = Poly3DCollection([face], alpha=0.7, facecolor=color, edgecolor='black')
            ax.add_collection3d(poly)

    def set_axes_equal_3d(self, ax):
        """Fa que els eixos 3D tinguin la mateixa escala."""
        # Obtenir els límits actuals
        x_limits = ax.get_xlim3d()
        y_limits = ax.get_ylim3d()
        z_limits = ax.get_zlim3d()
        # Calcular els rangs
        x_range = abs(x_limits[1] - x_limits[0])
        x_middle = sum(x_limits) / 2
        y_range = abs(y_limits[1] - y_limits[0])
        y_middle = sum(y_limits) / 2
        z_range = abs(z_limits[1] - z_limits[0])
        z_middle = sum(z_limits) / 2
        # El radi del plot és la meitat del rang màxim
        plot_radius = 0.5 * max([x_range, y_range, z_range])
        ax.set_xlim3d([x_middle - plot_radius, x_middle + plot_radius])
        ax.set_ylim3d([y_middle - plot_radius, y_middle + plot_radius])
        ax.set_zlim3d([z_middle - plot_radius, z_middle + plot_radius])

    def close_visualization(self):
        """Tanca la visualització 3D i neteja els recursos."""
        try:
            # Destruir canvas si existeix
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.get_tk_widget().destroy()
                self.canvas = None
            
            # Destruir toolbar si existeix
            if hasattr(self, 'toolbar') and self.toolbar:
                self.toolbar.destroy()
                self.toolbar = None
            
            # Netejar tots els widgets del canvas_frame
            for widget in self.canvas_frame.winfo_children():
                widget.destroy()
            
            # Deshabilitar botó de tancar
            self.close_viz_btn.config(state=tk.DISABLED)
            
            self.update_status("Visualització 3D tancada")
            
        except Exception as e:
            print(f"Error tancant visualització: {e}")
            messagebox.showerror("Error", f"Error tancant visualització: {e}")

    def add_to_results_tab(self, content):
        """Afegeix contingut a la pestanya de resultats per mantenir un històric complet."""
        try:
            # Afegir timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.results_text.insert(tk.END, f"\n[{timestamp}] ")
            self.results_text.insert(tk.END, content)
            self.results_text.insert(tk.END, "\n" + "="*60 + "\n")
            self.results_text.see(tk.END)
        except Exception as e:
            print(f"Error afegint a la pestanya de resultats: {e}")
    
    def save_results_to_file(self, filename=None):
        """Guarda tots els resultats a un fitxer automàticament."""
        if not filename:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/packassist_results_{timestamp}.txt"
        
        try:
            # Crear directori de resultats si no existeix
            os.makedirs("results", exist_ok=True)
            
            content = self.results_text.get(1.0, tk.END)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            return filename
        except Exception as e:
            print(f"Error guardant resultats: {e}")
            return None

    def validate_entry_file(self, file_path):
        """Valida si un fitxer o entrada personalitzada és vàlid."""
        if not file_path:
            return False
            
        # Comprovar si és una caixa personalitzada
        if file_path.startswith("custom://"):
            return self.get_custom_dimensions(file_path) is not None
            
        # Comprovar fitxer STP normal
        return validate_stp_file(file_path)
    
    def get_entry_dimensions(self, file_path):
        """Obté les dimensions d'un fitxer o entrada personalitzada."""
        if not file_path:
            return None
            
        # Comprovar si és una caixa personalitzada
        if file_path.startswith("custom://"):
            custom_dims = self.get_custom_dimensions(file_path)
            if custom_dims:
                return {
                    "length": custom_dims["length"],
                    "width": custom_dims["width"], 
                    "height": custom_dims["height"]
                }
            return None
            
        # Obtenir dimensions de fitxer STP normal
        return get_stp_dimensions(file_path)