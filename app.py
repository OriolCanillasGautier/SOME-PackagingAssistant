#!/usr/bin/env python3
"""
PackAssist 3D - Optimitzador de 3D Bin Packing amb GUI moderna
Sistema integrat per l'optimització d'empaquetament 3D amb interfície gràfica.
Versió optimitzada i reduïda.
"""
import csv
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
from src.packassist import get_stp_dimensions, validate_stp_file, optimize_packing, calculate_theoretical_max

# Constants
CSV_PATH = "data/index.csv"

class PackAssistGUI:
    """Interfície gràfica principal per PackAssist 3D."""
    
    def __init__(self, root):
        """Inicialitza la interfície gràfica."""
        self.root = root
        self.root.title("PackAssist 3D - Optimitzador de Bin Packing")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Variables de control
        self.is_processing = False
        self.metadata = []
        self.optimization_results = None
        
        # Configurar estil modern
        self._setup_styles()
        # Crear interfície
        self._create_widgets()
        # Carregar dades inicials
        self._load_initial_data()

    def _setup_styles(self):
        """Configura estils moderns per la interfície."""
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Title.TLabel', font=('Arial', 14, 'bold'))
        style.configure('Header.TLabel', font=('Arial', 11, 'bold'))
        self.root.configure(bg="#f5f5f5")

    def _create_widgets(self):
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
        ttk.Label(self.main_frame, text="🎯 PackAssist 3D", style='Title.TLabel').grid(row=0, column=0, pady=(0, 10))
        
        # Notebook per pestanyes
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Crear pestanyes
        self._create_stp_tab()
        self._create_manual_tab()
        self._create_csv_editor_tab()
        self._create_results_tab()
        
        # Visualització 3D
        self._create_visualization_section()
        # Barra d'estat
        self._create_status_bar()

    def _create_stp_tab(self):
        """Crea la pestanya de fitxers STP."""
        stp_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(stp_frame, text="📁 Fitxers STP")
        stp_frame.columnconfigure(0, weight=1)
        stp_frame.rowconfigure(2, weight=1)
        
        # Gestió de fitxers
        file_frame = ttk.LabelFrame(stp_frame, text="Gestió de fitxers", padding="10")
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        
        ttk.Button(file_frame, text="📂 Carregar CSV", command=self.load_csv_file).grid(row=0, column=0, padx=(0, 5))
        self.csv_path_var = tk.StringVar(value=CSV_PATH)
        ttk.Entry(file_frame, textvariable=self.csv_path_var, state='readonly').grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        ttk.Button(file_frame, text="🔄 Recarregar", command=self.reload_metadata).grid(row=0, column=2, padx=(5, 0))
        
        # Control de processat
        control_frame = ttk.LabelFrame(stp_frame, text="Control de processat", padding="10")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(control_frame, text="▶️ Processar Tot", command=self.process_all_files).grid(row=0, column=0, padx=(0, 10))
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(control_frame, variable=self.progress_var, maximum=100, length=200)
        self.progress_bar.grid(row=0, column=1, padx=(10, 10))
        ttk.Button(control_frame, text="⏹️ Aturar", command=self.stop_processing).grid(row=0, column=2, padx=(10, 0))
        
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
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        self.file_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

    def _create_manual_tab(self):
        """Crea la pestanya d'entrada manual."""
        manual_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(manual_frame, text="🔢 Entrada Manual")
        manual_frame.columnconfigure(0, weight=1)
        manual_frame.columnconfigure(1, weight=1)
        
        # Dimensions del contenidor
        self._create_box_input_section(manual_frame)
        # Dimensions de l'objecte
        self._create_object_input_section(manual_frame)
        
        # Botó de càlcul
        ttk.Button(manual_frame, text="🧮 Calcular Empaquetament", command=self.calculate_manual).grid(row=1, column=0, columnspan=2, pady=10)
        
        # Resultats
        self._create_manual_results_section(manual_frame)

    def _create_box_input_section(self, parent):
        """Crea la secció d'entrada de dimensions del contenidor."""
        box_frame = ttk.LabelFrame(parent, text="📦 Dimensions del contenidor (mm)", padding="10")
        box_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 5), pady=(0, 10))
        box_frame.columnconfigure(1, weight=1)
        
        # Selector de caixes
        self.box_source_var = tk.StringVar(value="manual")
        ttk.Radiobutton(box_frame, text="Entrada manual", variable=self.box_source_var, value="manual", command=self._toggle_box_input).grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(box_frame, text="Seleccionar de la llista", variable=self.box_source_var, value="imported", command=self._toggle_box_input).grid(row=0, column=1, sticky=tk.W)
        
        # Frame per selecció importada
        self.box_selection_frame = ttk.Frame(box_frame)
        self.box_selection_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        ttk.Label(self.box_selection_frame, text="Caixa:").grid(row=0, column=0, sticky=tk.W)
        self.selected_box_var = tk.StringVar()
        self.box_combo = ttk.Combobox(self.box_selection_frame, textvariable=self.selected_box_var, state="readonly", width=25)
        self.box_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        self.box_combo.bind('<<ComboboxSelected>>', self._on_box_selected)
        self.box_selection_frame.grid_remove()
        
        # Frame per entrada manual
        self.manual_box_frame = ttk.Frame(box_frame)
        self.manual_box_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        self.manual_box_frame.columnconfigure(1, weight=1)
        labels = ["Longitud (mm):", "Amplada (mm):", "Altura (mm):"]
        defaults = [1000.0, 800.0, 600.0]  # Converted from cm to mm (multiplied by 10)
        self.box_vars = []
        
        for i, (label, default) in enumerate(zip(labels, defaults)):
            ttk.Label(self.manual_box_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=(5 if i > 0 else 0, 0))
            var = tk.DoubleVar(value=default)
            self.box_vars.append(var)
            ttk.Entry(self.manual_box_frame, textvariable=var).grid(row=i, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5 if i > 0 else 0, 0))

    def _create_object_input_section(self, parent):
        """Crea la secció d'entrada de dimensions de l'objecte."""
        obj_frame = ttk.LabelFrame(parent, text="📋 Dimensions de l'objecte (mm)", padding="10")
        obj_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), padx=(5, 0), pady=(0, 10))
        obj_frame.columnconfigure(1, weight=1)
        
        # Opcions d'entrada
        self.input_method_var = tk.StringVar(value="manual")
        ttk.Radiobutton(obj_frame, text="Entrada manual", variable=self.input_method_var, value="manual", command=self._toggle_input_method).grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(obj_frame, text="Fitxer STP", variable=self.input_method_var, value="file", command=self._toggle_input_method).grid(row=0, column=1, sticky=tk.W)
        ttk.Radiobutton(obj_frame, text="Objectes importats", variable=self.input_method_var, value="imported", command=self._toggle_input_method).grid(row=1, column=0, columnspan=2, sticky=tk.W)
        
        # Frame per selecció importada
        self.object_selection_frame = ttk.Frame(obj_frame)
        self.object_selection_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        ttk.Label(self.object_selection_frame, text="Objecte:").grid(row=0, column=0, sticky=tk.W)
        self.selected_object_var = tk.StringVar()
        self.object_combo = ttk.Combobox(self.object_selection_frame, textvariable=self.selected_object_var, state="readonly", width=25)
        self.object_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        self.object_combo.bind('<<ComboboxSelected>>', self._on_object_selected)
        self.object_selection_frame.grid_remove()
        
        # Frame per entrada manual
        self.manual_input_frame = ttk.Frame(obj_frame)
        self.manual_input_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        self.manual_input_frame.columnconfigure(1, weight=1)
        
        labels = ["Longitud (mm):", "Amplada (mm):", "Altura (mm):"]
        defaults = [200.0, 150.0, 100.0]  # Converted from cm to mm (multiplied by 10)
        self.obj_vars = []
        
        for i, (label, default) in enumerate(zip(labels, defaults)):
            ttk.Label(self.manual_input_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=(5 if i > 0 else 0, 0))
            var = tk.DoubleVar(value=default)
            self.obj_vars.append(var)
            ttk.Entry(self.manual_input_frame, textvariable=var).grid(row=i, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5 if i > 0 else 0, 0))
        
        # Frame per entrada de fitxer STP
        self.file_input_frame = ttk.Frame(obj_frame)
        self.file_input_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        self.file_input_frame.columnconfigure(0, weight=1)
        
        self.file_path_var = tk.StringVar()
        ttk.Entry(self.file_input_frame, textvariable=self.file_path_var, width=30).grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(self.file_input_frame, text="Explorar...", command=self._browse_stp_file).grid(row=0, column=1)
        
        self.file_info_var = tk.StringVar(value="Dimensions: - x - x - cm")
        ttk.Label(self.file_input_frame, textvariable=self.file_info_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        self.file_input_frame.grid_remove()

    def _create_manual_results_section(self, parent):
        """Crea la secció de resultats manuals."""
        results_frame = ttk.LabelFrame(parent, text="📊 Resultats", padding="10")
        results_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        self.manual_results = tk.Text(results_frame, height=15, wrap=tk.WORD)
        manual_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.manual_results.yview)
        self.manual_results.configure(yscrollcommand=manual_scrollbar.set)
        self.manual_results.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        manual_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

    def _create_csv_editor_tab(self):
        """Crea la pestanya d'edició CSV."""
        csv_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(csv_frame, text="📝 Editor CSV")
        csv_frame.columnconfigure(0, weight=1)
        csv_frame.rowconfigure(1, weight=1)
        
        # Controls
        controls_frame = ttk.Frame(csv_frame)
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(controls_frame, text="🔄 Recarregar CSV", command=self.reload_csv_data).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(controls_frame, text="➕ Afegir Entrada", command=self.add_csv_entry).grid(row=0, column=1, padx=5)
        ttk.Button(controls_frame, text="📦 Nova Caixa", command=self.create_new_box).grid(row=0, column=2, padx=5)
        ttk.Button(controls_frame, text="🧩 Nou Objecte", command=self.create_new_object).grid(row=0, column=3, padx=5)
        ttk.Button(controls_frame, text="✏️ Editar", command=self.edit_selected_item).grid(row=0, column=4, padx=5)
        ttk.Button(controls_frame, text="💾 Guardar CSV", command=self.save_csv_data).grid(row=0, column=5, padx=(5, 0))
        
        # Taula d'edició
        table_frame = ttk.Frame(csv_frame)
        table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        
        columns = ("type", "name", "file_path")
        self.csv_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        self.csv_tree.heading("type", text="Tipus")
        self.csv_tree.heading("name", text="Nom")
        self.csv_tree.heading("file_path", text="Ruta del Fitxer")
        
        self.csv_tree.column("type", width=80, minwidth=80)
        self.csv_tree.column("name", width=200, minwidth=150)
        self.csv_tree.column("file_path", width=300, minwidth=200)
        
        csv_v_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.csv_tree.yview)
        self.csv_tree.configure(yscrollcommand=csv_v_scroll.set)
        self.csv_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        csv_v_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Enable double-click to edit
        self.csv_tree.bind("<Double-1>", lambda event: self.edit_selected_item())

    def _create_results_tab(self):
        """Crea la pestanya de resultats."""
        results_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(results_frame, text="📊 Resultats")
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(1, weight=1)
        
        # Controls
        controls_frame = ttk.Frame(results_frame)
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(controls_frame, text="💾 Exportar Resultats", command=self.export_results).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(controls_frame, text="🗑️ Netejar Resultats", command=self.clear_results).grid(row=0, column=1)
        
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

    def _create_visualization_section(self):
        """Crea la secció de visualització 3D."""
        self.viz_frame = ttk.LabelFrame(self.main_frame, text="🎯 Visualització 3D", padding="10")
        self.viz_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        viz_buttons_frame = ttk.Frame(self.viz_frame)
        viz_buttons_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.visualize_btn = ttk.Button(viz_buttons_frame, text="📊 Visualitzar Empaquetament", command=self.visualize_packing, state=tk.DISABLED)
        self.visualize_btn.grid(row=0, column=0, padx=5)
        
        self.close_viz_btn = ttk.Button(viz_buttons_frame, text="❌ Tancar Visualització", command=self.close_visualization, state=tk.DISABLED)
        self.close_viz_btn.grid(row=0, column=1, padx=5)
        
        self.canvas_frame = ttk.Frame(self.viz_frame)
        self.canvas_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

    def _create_status_bar(self):
        """Crea la barra d'estat."""
        status_frame = ttk.Frame(self.main_frame)
        status_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        status_frame.columnconfigure(0, weight=1)
        
        self.status_var = tk.StringVar(value="Llest")
        ttk.Label(status_frame, textvariable=self.status_var).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(status_frame, text=f"Python {sys.version.split()[0]} | PackAssist 3D v1.0").grid(row=0, column=1, sticky=tk.E)

    # === FUNCIONS DE GESTIÓ DE DADES ===
    
    def _load_initial_data(self):
        """Carrega les dades inicials."""
        self.update_status("Carregant dades inicials...")
        self.reload_metadata()

    def update_status(self, message):
        """Actualitza la barra d'estat."""
        self.status_var.set(message)
        self.root.update_idletasks()

    def reload_metadata(self):
        """Recarrega les metadades del CSV."""
        csv_path = self.csv_path_var.get()
        try:
            if not os.path.exists(csv_path):
                self._create_sample_data()
                return
            
            with open(csv_path, "r", encoding='utf-8') as f:
                self.metadata = list(csv.DictReader(f))
            
            self.update_file_tree()
            if hasattr(self, 'box_combo'):
                self._update_box_combo()
            if hasattr(self, 'object_combo'):
                self._update_object_combo()
            self.update_status(f"Carregades {len(self.metadata)} entrades del CSV")
        except Exception as e:
            messagebox.showerror("Error", f"Error carregant metadades: {e}")
            self.update_status("Error carregant dades")

    def update_file_tree(self):
        """Actualitza la taula de fitxers."""
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        for entry in self.metadata:
            file_path = entry.get("file_path", "")
            status = "✅ Vàlid" if self._validate_entry_file(file_path) else "❌ No vàlid"
            self.file_tree.insert("", tk.END, values=(
                entry.get("type", ""),
                entry.get("name", ""),
                file_path,
                status
            ))

    def _create_sample_data(self):
        """Crea dades de mostra."""
        try:
            os.makedirs("boxes", exist_ok=True)
            os.makedirs("objects", exist_ok=True)
            os.makedirs("data", exist_ok=True)
            
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
            messagebox.showinfo("Dades de mostra", "S'han creat dades de mostra.\nAfegeix els teus fitxers STP als directoris 'boxes' i 'objects'.")
            self.update_status("Dades de mostra creades")
        except Exception as e:
            messagebox.showerror("Error", f"Error creant dades de mostra: {e}")

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

    # === FUNCIONS CSV EDITOR ===
    
    def reload_csv_data(self):
        """Recarrega les dades del CSV per l'editor."""
        self.reload_metadata()
        self._update_csv_tree()

    def _update_csv_tree(self):
        """Actualitza la taula del CSV editor."""
        for item in self.csv_tree.get_children():
            self.csv_tree.delete(item)
        
        for entry in self.metadata:
            self.csv_tree.insert("", tk.END, values=(
                entry.get("type", ""),
                entry.get("name", ""),
                entry.get("file_path", "")
            ))

    def create_new_box(self):
        """Creates a new box and adds it to the CSV index."""
        from src.packassist.dialog_creator import CreateBoxDialog
        
        # Callback for when a box is created
        def on_box_created(box_data):
            self.metadata.append(box_data)
            self._update_csv_tree()
            self.reload_metadata()
        
        # Show the dialog
        CreateBoxDialog(self.root, callback=on_box_created)

    def create_new_object(self):
        """Creates a new object and adds it to the CSV index."""
        from src.packassist.dialog_creator import CreateObjectDialog
        
        # Callback for when an object is created
        def on_object_created(object_data):
            self.metadata.append(object_data)
            self._update_csv_tree()
            self.reload_metadata()
        
        # Show the dialog
        CreateObjectDialog(self.root, callback=on_object_created)

    def edit_selected_item(self):
        """Edit dimensions of the selected item."""
        from src.packassist.dialog_creator import EditDimensionsDialog
        
        # Get selected item
        selection = self.csv_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "No item selected")
            return
        
        # Get selected item data
        item_id = selection[0]
        item_values = self.csv_tree.item(item_id, "values")
        if not item_values:
            return
        
        # Find corresponding metadata entry
        entry = None
        for meta in self.metadata:
            if (meta.get("type") == item_values[0] and 
                meta.get("name") == item_values[1] and 
                meta.get("file_path") == item_values[2]):
                entry = meta
                break
        
        if not entry:
            messagebox.showwarning("Warning", "Could not find metadata for selected item")
            return
        
        # Get dimensions for the selected item
        dimensions = self._get_entry_dimensions(entry.get("file_path"))
        if not dimensions:
            messagebox.showerror("Error", "Could not read dimensions for the selected item")
            return
        
        # Callback for when dimensions are updated
        def on_dimensions_updated(entry, new_dimensions):
            # Refresh metadata and UI
            self.reload_metadata()
        
        # Show the dialog
        EditDimensionsDialog(self.root, entry, dimensions, callback=on_dimensions_updated)

    def add_csv_entry(self):
        """Afegeix una nova entrada al CSV."""
        # Diàleg simple per afegir entrada
        dialog = tk.Toplevel(self.root)
        dialog.title("Afegir Nova Entrada")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Variables
        type_var = tk.StringVar(value="object")
        name_var = tk.StringVar()
        path_var = tk.StringVar()
        
        # Interface
        ttk.Label(dialog, text="Tipus:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        type_combo = ttk.Combobox(dialog, textvariable=type_var, values=["box", "object"], state="readonly")
        type_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Label(dialog, text="Nom:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(dialog, textvariable=name_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Label(dialog, text="Ruta fitxer:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        path_frame = ttk.Frame(dialog)
        path_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        path_frame.columnconfigure(0, weight=1)
        
        ttk.Entry(path_frame, textvariable=path_var).grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Button(path_frame, text="...", command=lambda: self._browse_file_for_entry(path_var)).grid(row=0, column=1, padx=(5, 0))
        
        # Botons
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Guardar", command=lambda: self._save_new_entry(dialog, type_var, name_var, path_var)).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Cancel·lar", command=dialog.destroy).grid(row=0, column=1, padx=5)
        
        dialog.columnconfigure(1, weight=1)

    def _browse_file_for_entry(self, path_var):
        """Explora fitxers STP per l'entrada."""
        filepath = filedialog.askopenfilename(
            title="Selecciona fitxer STP",
            filetypes=[("Fitxers STP", "*.stp;*.step"), ("Tots els fitxers", "*.*")]
        )
        if filepath:
            path_var.set(filepath)

    def _save_new_entry(self, dialog, type_var, name_var, path_var):
        """Guarda la nova entrada."""
        if not name_var.get() or not path_var.get():
            messagebox.showwarning("Avís", "Tots els camps són obligatoris")
            return
        
        new_entry = {
            "type": type_var.get(),
            "name": name_var.get(),
            "file_path": path_var.get()
        }
        self.metadata.append(new_entry)
        self._update_csv_tree()
        dialog.destroy()

    def save_csv_data(self):
        """Guarda les dades del CSV."""
        try:
            with open(self.csv_path_var.get(), "w", newline='', encoding='utf-8') as f:
                if self.metadata:
                    writer = csv.DictWriter(f, fieldnames=self.metadata[0].keys())
                    writer.writeheader()
                    writer.writerows(self.metadata)
            messagebox.showinfo("Èxit", "Dades guardades correctament")
            self.update_status("CSV guardat")
        except Exception as e:
            messagebox.showerror("Error", f"Error guardant CSV: {e}")

    # === FUNCIONS D'ENTRADA MANUAL ===
    
    def _toggle_input_method(self):
        """Toggle entre mètodes d'entrada d'objectes."""
        method = self.input_method_var.get()
        self.file_input_frame.grid_remove()
        self.manual_input_frame.grid_remove()
        self.object_selection_frame.grid_remove()
        
        if method == "manual":
            self.manual_input_frame.grid()
        elif method == "file":
            self.file_input_frame.grid()
        elif method == "imported":
            self.object_selection_frame.grid()
            self._update_object_combo()

    def _toggle_box_input(self):
        """Toggle entre mètodes d'entrada de caixes."""
        method = self.box_source_var.get()
        if method == "manual":
            self.box_selection_frame.grid_remove()
            self.manual_box_frame.grid()
        else:
            self.manual_box_frame.grid_remove()
            self.box_selection_frame.grid()
            self._update_box_combo()

    def _update_box_combo(self):
        """Actualitza el combobox de caixes."""
        boxes = [entry for entry in self.metadata if entry.get("type") == "box"]
        box_names = [f"{box['name']} ({box['file_path']})" for box in boxes]
        self.box_combo['values'] = box_names
        if box_names:
            self.box_combo.set(box_names[0])
            self._on_box_selected(None)

    def _update_object_combo(self):
        """Actualitza el combobox d'objectes."""
        objects = [entry for entry in self.metadata if entry.get("type") == "object"]
        object_names = [f"{obj['name']} ({obj['file_path']})" for obj in objects]
        self.object_combo['values'] = object_names
        if object_names:
            self.object_combo.set(object_names[0])
            self._on_object_selected(None)
            
    def _on_box_selected(self, event):
        """Event quan es selecciona una caixa."""
        selected = self.selected_box_var.get()
        if not selected:
            return
        
        file_path = selected.split('(')[-1].split(')')[0]
        dimensions = self._get_entry_dimensions(file_path)
        if dimensions:            # Use millimeters directly (no conversion needed)
            self.box_vars[0].set(dimensions['length'])
            self.box_vars[1].set(dimensions['width'])
            self.box_vars[2].set(dimensions['height'])
            
    def _on_object_selected(self, event):
        """Event quan es selecciona un objecte."""
        selected = self.selected_object_var.get()
        if not selected:
            return
        
        file_path = selected.split('(')[-1].split(')')[0]
        dimensions = self._get_entry_dimensions(file_path)
        if dimensions:
            # Use millimeters directly (no conversion needed)
            self.obj_vars[0].set(dimensions['length'])
            self.obj_vars[1].set(dimensions['width'])
            self.obj_vars[2].set(dimensions['height'])

    def _browse_stp_file(self):
        """Explora fitxers STP."""
        filepath = filedialog.askopenfilename(
            title="Selecciona un fitxer STP",
            filetypes=[("Fitxers STP", "*.stp;*.step"), ("Tots els fitxers", "*.*")]
        )
        if filepath:
            self.file_path_var.set(filepath)
            self._update_file_info(filepath)
            
    def _update_file_info(self, filepath):
        """Actualitza la informació del fitxer STP."""
        if not filepath:
            self.file_info_var.set("Dimensions: - x - x - mm")
            return
        
        try:
            dimensions = get_stp_dimensions(filepath)
            if dimensions:
                # Display dimensions in mm (no longer need to convert)
                length_mm = dimensions['length']
                width_mm = dimensions['width']
                height_mm = dimensions['height']
                
                info = f"Dimensions: {length_mm:.1f} x {width_mm:.1f} x {height_mm:.1f} mm"
                self.file_info_var.set(info)
                  # Actualitzar variables (now using mm)
                self.obj_vars[0].set(length_mm)
                self.obj_vars[1].set(width_mm)
                self.obj_vars[2].set(height_mm)
            else:
                self.file_info_var.set("Error llegint fitxer STP")
        except Exception as e:
            self.file_info_var.set(f"Error: {str(e)}")

    # === FUNCIONS DE CÀLCUL ===
    def calculate_manual(self):
        """Calcula l'empaquetament manual."""
        try:
            # Obtenir dimensions com a tuples (ara ja estem utilitzant mm directament)
            box_tuple = (
                self.box_vars[0].get(),  # length
                self.box_vars[1].get(),  # width  
                self.box_vars[2].get()   # height
            )
            obj_tuple = (
                self.obj_vars[0].get(),  # length
                self.obj_vars[1].get(),  # width
                self.obj_vars[2].get()   # height
            )
            
            # Validar dimensions
            if any(v <= 0 for v in box_tuple) or any(v <= 0 for v in obj_tuple):
                messagebox.showerror("Error", "Totes les dimensions han de ser positives")
                return
            
            # Convertir a diccionaris per la visualització
            box_dims = {
                "length": box_tuple[0],
                "width": box_tuple[1], 
                "height": box_tuple[2]
            }
            obj_dims = {
                "length": obj_tuple[0],
                "width": obj_tuple[1],
                "height": obj_tuple[2]
            }
            
            # Calcular
            self.manual_results.delete(1.0, tk.END)
            results_content = self._build_manual_results_content(box_dims, obj_dims)
            
            theoretical_max = calculate_theoretical_max(box_tuple, obj_tuple)
            result = optimize_packing(box_tuple, obj_tuple)
            
            results_content += self._build_optimization_results(result, theoretical_max)
            
            self.manual_results.insert(tk.END, results_content)
            
            # Guardar resultats per visualització
            if not result.get("error"):
                self.optimization_results = result
                self.visualize_btn.config(state=tk.NORMAL if result['max_objects'] > 0 else tk.DISABLED)
            else:
                self.visualize_btn.config(state=tk.DISABLED)
            
            # Afegir a la pestanya de resultats
            self._add_to_results_tab(results_content)
            self._save_results_automatically()
            self.update_status("Càlcul manual completat")
            
        except ValueError:            messagebox.showerror("Error", "Introdueix valors numèrics vàlids")
        except Exception as e:
            messagebox.showerror("Error", f"Error durant el càlcul: {e}")
            
    def _build_manual_results_content(self, box_dims, obj_dims):
        """Construeix el contingut dels resultats manuals."""
        content = "🧮 CÀLCUL D'EMPAQUETAMENT MANUAL\n"
        content += "=" * 40 + "\n\n"
        content += f"📦 Contenidor:\n"
        content += f"   Longitud: {box_dims['length']:.1f} mm\n"
        content += f"   Amplada: {box_dims['width']:.1f} mm\n"
        content += f"   Altura: {box_dims['height']:.1f} mm\n\n"
        content += f"📋 Objecte:\n"
        content += f"   Longitud: {obj_dims['length']:.1f} mm\n"
        content += f"   Amplada: {obj_dims['width']:.1f} mm\n"
        content += f"   Altura: {obj_dims['height']:.1f} mm\n\n"
        return content

    def _build_optimization_results(self, result, theoretical_max):
        """Construeix els resultats d'optimització."""
        content = "📊 RESULTATS:\n"
        content += f"   ➕ Màxim teòric (per volum): {theoretical_max} unitats\n"
        
        if result["error"]:
            content += f"   ❌ Error: {result['error']}\n"
        else:
            content += f"   ✅ Màxim real (3D packing): {result['max_objects']} unitats\n"
            content += f"   📈 Eficiència d'espai: {result['efficiency']:.1f}%\n"
            content += f"   📏 Volum contenidor: {result['box_volume']:.1f} mm³\n"
            content += f"   📦 Volum utilitzat: {result['used_volume']:.1f} mm³\n"
        
        return content

    # === FUNCIONS DE PROCESSAMENT ===
    
    def process_all_files(self):
        """Processa tots els fitxers STP."""
        if self.is_processing:
            return
        
        if not self.metadata:
            messagebox.showwarning("Avís", "No hi ha fitxers per processar")
            return
        
        valid_metadata = [entry for entry in self.metadata 
                         if entry.get("type") in ["box", "object"] and 
                         self._validate_entry_file(entry.get("file_path", ""))]
        
        if not valid_metadata:
            messagebox.showwarning("Avís", "No hi ha fitxers vàlids per processar")
            return
        
        boxes = [m for m in valid_metadata if m["type"] == "box"]
        objects = [m for m in valid_metadata if m["type"] == "object"]
        
        if not boxes or not objects:
            messagebox.showwarning("Avís", "Es necessiten caixes i objectes per processar")
            return
        
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
                
                box_dims = self._get_entry_dimensions(box_info["file_path"])
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
                    obj_dims = self._get_entry_dimensions(obj_info["file_path"])
                    if not obj_dims:
                        continue
                    
                    # Convertir dimensions a tuples per l'optimitzador
                    box_tuple = (box_dims['length'], box_dims['width'], box_dims['height'])
                    obj_tuple = (obj_dims['length'], obj_dims['width'], obj_dims['height'])
                    
                    theoretical_max = calculate_theoretical_max(box_tuple, obj_tuple)
                    result = optimize_packing(box_tuple, obj_tuple)
                    
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
                self._save_results_automatically()
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

    # === FUNCIONS DE RESULTATS ===
    
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

    def _add_to_results_tab(self, content):
        """Afegeix contingut a la pestanya de resultats."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.results_text.insert(tk.END, f"\n[{timestamp}] ")
            self.results_text.insert(tk.END, content)
            self.results_text.insert(tk.END, "\n" + "="*60 + "\n")
            self.results_text.see(tk.END)
        except Exception as e:
            print(f"Error afegint a la pestanya de resultats: {e}")

    def _save_results_automatically(self):
        """Guarda els resultats automàticament."""
        try:
            os.makedirs("results", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/packassist_results_{timestamp}.txt"
            
            content = self.results_text.get(1.0, tk.END)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.update_status(f"Resultats guardats automàticament a {filename}")
        except Exception as e:
            print(f"Error guardant resultats automàticament: {e}")

    # === FUNCIONS DE VISUALITZACIÓ 3D ===
    
    def visualize_packing(self):
        """Mostra la visualització 3D dels resultats d'empaquetament."""
        if not hasattr(self, 'optimization_results') or not self.optimization_results:
            messagebox.showwarning("Advertència", "No hi ha resultats d'optimització per visualitzar.")
            return
        try:
            # Import matplotlib for 3D visualization
            import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d import Axes3D
            from mpl_toolkits.mplot3d.art3d import Poly3DCollection
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
            
            # Clear previous visualization
            for widget in self.canvas_frame.winfo_children():
                widget.destroy()
            
            # Get container and object dimensions from current values
            box_dims = (
                self.box_vars[0].get(),  # length
                self.box_vars[1].get(),  # width
                self.box_vars[2].get()   # height
            )
            obj_dims = (
                self.obj_vars[0].get(),  # length
                self.obj_vars[1].get(),  # width
                self.obj_vars[2].get()   # height
            )
            
            # Create 3D plot
            fig = plt.figure(figsize=(10, 8))
            ax = fig.add_subplot(111, projection='3d')
            
            # Draw container wireframe
            self._draw_container_wireframe(ax, box_dims)
            
            # Calculate and draw packed objects
            max_objects = self.optimization_results.get('max_objects', 0)
            if max_objects > 0:
                self._draw_packed_objects(ax, box_dims, obj_dims, max_objects)
            
            # Set labels and title
            ax.set_xlabel('Longitud (mm)')
            ax.set_ylabel('Amplada (mm)')
            ax.set_zlabel('Altura (mm)')
            ax.set_title(f'Visualització 3D - {max_objects} objectes empaquetats\n'
                        f'Eficiència: {self.optimization_results.get("efficiency", 0):.1f}%')
            
            # Make axes equal
            self._set_axes_equal_3d(ax)
            
            # Create canvas
            self.canvas = FigureCanvasTkAgg(fig, self.canvas_frame)
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Add toolbar
            self.toolbar = NavigationToolbar2Tk(self.canvas, self.canvas_frame)
            self.toolbar.update()
            
            self.close_viz_btn.config(state=tk.NORMAL)
            self.update_status("Visualització 3D generada correctament")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error generant visualització 3D: {e}")
            self.update_status("Error en la visualització 3D")
            
            self.toolbar = NavigationToolbar2Tk(self.canvas, self.canvas_frame)
            self.toolbar.update()
            
            self.close_viz_btn.config(state=tk.NORMAL)
            self.update_status("Visualització 3D generada correctament")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error generant visualització 3D: {e}")

    def _draw_container_wireframe(self, ax, box_dims):
        """Dibuixa el wireframe del contenidor."""
        w, h, d = box_dims
        
        # Vèrtexs del contenidor
        vertices = [
            [0, 0, 0], [w, 0, 0], [w, h, 0], [0, h, 0],
            [0, 0, d], [w, 0, d], [w, h, d], [0, h, d]
        ]
        
        # Arestes del contenidor
        edges = [
            [0, 1], [1, 2], [2, 3], [3, 0],  # base inferior
            [4, 5], [5, 6], [6, 7], [7, 4],  # base superior
            [0, 4], [1, 5], [2, 6], [3, 7]   # arestes verticals
        ]
        
        for edge in edges:
            points = [vertices[edge[0]], vertices[edge[1]]]
            ax.plot3D([p[0] for p in points], [p[1] for p in points], [p[2] for p in points], 
                     color='black', linewidth=2, alpha=0.8)

    def _draw_packed_objects(self, ax, box_dims, obj_dims, max_objects):
        """Dibuixa els objectes empaquetats de forma optimitzada."""
        box_w, box_h, box_d = box_dims
        obj_w, obj_h, obj_d = obj_dims
        
        # Calcular quants objectes caben en cada dimensió
        objects_x = int(box_w // obj_w)
        objects_y = int(box_h // obj_h) 
        objects_z = int(box_d // obj_d)
        
        # Calcular posicions dels objectes
        placed = 0
        colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
        
        for z in range(objects_z):
            if placed >= max_objects:
                break
            for y in range(objects_y):
                if placed >= max_objects:
                    break
                for x in range(objects_x):
                    if placed >= max_objects:
                        break
                    
                    # Posició de l'objecte
                    pos_x = x * obj_w
                    pos_y = y * obj_h
                    pos_z = z * obj_d
                    
                    # Dibuixar l'objecte
                    self._draw_3d_box(ax, (pos_x, pos_y, pos_z), obj_dims, colors[placed % len(colors)])
                    placed += 1

    def _draw_3d_box(self, ax, position, dimensions, color):
        """Dibuixa una caixa 3D en una posició determinada."""
        x, y, z = position
        w, h, d = dimensions
        
        # Vèrtexs de la caixa
        vertices = [
            [x, y, z], [x+w, y, z], [x+w, y+h, z], [x, y+h, z],
            [x, y, z+d], [x+w, y, z+d], [x+w, y+h, z+d], [x, y+h, z+d]
        ]
        
        # Cares de la caixa
        faces = [
            [vertices[0], vertices[1], vertices[2], vertices[3]],  # base inferior
            [vertices[4], vertices[5], vertices[6], vertices[7]],  # base superior
            [vertices[0], vertices[1], vertices[5], vertices[4]],  # cara frontal
            [vertices[2], vertices[3], vertices[7], vertices[6]],  # cara posterior
            [vertices[1], vertices[2], vertices[6], vertices[5]],  # cara dreta
            [vertices[4], vertices[7], vertices[3], vertices[0]]   # cara esquerra
        ]
        
        for face in faces:
            poly = Poly3DCollection([face], alpha=0.7, facecolor=color, edgecolor='black', linewidth=0.5)
            ax.add_collection3d(poly)

    def _draw_bin_wireframe(self, ax, bin_data):
        """Dibuixa el wireframe del contenidor."""
        w, h, d = [float(dim) for dim in bin_data['dimensions']]
        
        # Vèrtexs del cub
        vertices = [
            [0, 0, 0], [w, 0, 0], [w, h, 0], [0, h, 0],
            [0, 0, d], [w, 0, d], [w, h, d], [0, h, d]
        ]
        
        # Arestes
        edges = [
            [0, 1], [1, 2], [2, 3], [3, 0],  # base inferior
            [4, 5], [5, 6], [6, 7], [7, 4],  # base superior
            [0, 4], [1, 5], [2, 6], [3, 7]   # arestes verticals
        ]
        
        for edge in edges:
            points = [vertices[edge[0]], vertices[edge[1]]]
            ax.plot3D([p[0] for p in points], [p[1] for p in points], [p[2] for p in points], 
                     color='black', linewidth=2, alpha=0.8)

    def _draw_item_3d(self, ax, item, index):
        """Dibuixa un objecte en 3D."""
        pos = item['position']
        dims = item['dimensions']
        
        x, y, z = [float(p) for p in pos]
        w, h, d = [float(dim) for dim in dims]
        
        # Vèrtexs del cub
        vertices = [
            [x, y, z], [x+w, y, z], [x+w, y+h, z], [x, y+h, z],
            [x, y, z+d], [x+w, y, z+d], [x+w, y+h, z+d], [x, y+h, z+d]
        ]
        
        # Colors
        colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
        color = colors[index % len(colors)]
        
        # Cares del cub
        faces = [
            [vertices[0], vertices[1], vertices[2], vertices[3]],  # base inferior
            [vertices[4], vertices[5], vertices[6], vertices[7]],  # base superior
            [vertices[0], vertices[1], vertices[5], vertices[4]],  # cara frontal
            [vertices[2], vertices[3], vertices[7], vertices[6]],  # cara posterior
            [vertices[1], vertices[2], vertices[6], vertices[5]],  # cara dreta
            [vertices[4], vertices[7], vertices[3], vertices[0]]   # cara esquerra
        ]
        
        for face in faces:
            poly = Poly3DCollection([face], alpha=0.7, facecolor=color, edgecolor='black')
            ax.add_collection3d(poly)

    def _set_axes_equal_3d(self, ax):
        """Fa que els eixos 3D tinguin la mateixa escala."""
        limits = [ax.get_xlim3d(), ax.get_ylim3d(), ax.get_zlim3d()]
        ranges = [abs(lim[1] - lim[0]) for lim in limits]
        middles = [sum(lim) / 2 for lim in limits]
        
        plot_radius = max(ranges) * 0.5
        
        ax.set_xlim3d([middles[0] - plot_radius, middles[0] + plot_radius])
        ax.set_ylim3d([middles[1] - plot_radius, middles[1] + plot_radius])
        ax.set_zlim3d([middles[2] - plot_radius, middles[2] + plot_radius])

    def close_visualization(self):
        """Tanca la visualització 3D."""
        try:
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.get_tk_widget().destroy()
                self.canvas = None
            
            if hasattr(self, 'toolbar') and self.toolbar:
                self.toolbar.destroy()
                self.toolbar = None
            
            for widget in self.canvas_frame.winfo_children():
                widget.destroy()
            
            self.close_viz_btn.config(state=tk.DISABLED)
            self.update_status("Visualització 3D tancada")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error tancant visualització: {e}")

    # === FUNCIONS AUXILIARS ===
    
    def _validate_entry_file(self, file_path):
        """Valida si un fitxer STP és vàlid."""
        if not file_path:
            return False
        return validate_stp_file(file_path)

    def _get_entry_dimensions(self, file_path):
        """Obté les dimensions d'un fitxer STP."""
        if not file_path:
            return None
        return get_stp_dimensions(file_path)


def main():
    """Funció principal."""
    try:
        from src.packassist import get_stp_dimensions, validate_stp_file, optimize_packing, calculate_theoretical_max
    except ImportError as e:
        print(f"❌ Error important mòduls: {e}")
        print("Assegura't que els mòduls de packassist estiguin disponibles")
        return
    
    root = tk.Tk()
    app = PackAssistGUI(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n👋 Sortint...")
        root.quit()


if __name__ == "__main__":
    main()
