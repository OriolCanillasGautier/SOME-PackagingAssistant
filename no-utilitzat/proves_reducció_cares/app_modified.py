
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter as tk
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
from src.packassist import get_stp_dimensions, validate_stp_file, optimize_packing, calculate_theoretical_max, calculate_grid_packing
from src.packassist.smart_envelope import create_non_destructive_optimizer_dialog

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
        defaults = [2500.0, 1500.0, 1000.0]  
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
        defaults = [200.0, 150.0, 100.0]
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
        
        # Frame per botons
        button_frame = ttk.Frame(self.file_input_frame)
        button_frame.grid(row=0, column=1, sticky=tk.W)
        
        ttk.Button(button_frame, text="Explorar...", command=self._browse_stp_file).grid(row=0, column=0, padx=(0, 5))
        
        # Botó per editar geometria (inicialment deshabilitat)
        self.geometry_editor_button = ttk.Button(
            button_frame, 
            text="🎛️ Editar", 
            command=self._open_geometry_editor,
            state=tk.DISABLED
        )
        self.geometry_editor_button.grid(row=0, column=1, padx=(0, 5))
        
        # NOU: Botó per optimitzador no destructiu
        self.smart_optimizer_button = ttk.Button(
            button_frame,
            text="🎯 Optimitzar",
            command=self._open_smart_optimizer,
            state=tk.DISABLED
        )
        self.smart_optimizer_button.grid(row=0, column=2)
        
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
            self.reload_metadata()    # === FUNCIONS CSV EDITOR ===
    
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
        try:
            from src.packassist.dialog_creator import CreateBoxDialog
            
            # Callback for when a box is created
            def on_box_created(box_data):
                print(f"Debug - Box created: {box_data}")
                self.metadata.append(box_data)
                self._update_csv_tree()
                self.update_file_tree()  # Update main file tree as well
                self.save_csv_data()  # Auto-save after creation
                self.update_status(f"Caixa '{box_data.get('name', '')}' creada i guardada")
            
            # Show the dialog
            CreateBoxDialog(self.root, callback=on_box_created)
            
        except Exception as e:
            error_msg = f"Error creant nova caixa: {e}"
            messagebox.showerror("Error", error_msg)
            print(f"Debug - Error create_new_box: {e}")

    def create_new_object(self):
        """Creates a new object and adds it to the CSV index."""
        try:
            from src.packassist.dialog_creator import CreateObjectDialog
            
            # Callback for when an object is created
            def on_object_created(object_data):
                print(f"Debug - Object created: {object_data}")
                self.metadata.append(object_data)
                self._update_csv_tree()
                self.update_file_tree()  # Update main file tree as well
                self.save_csv_data()  # Auto-save after creation
                self.update_status(f"Objecte '{object_data.get('name', '')}' creat i guardat")
            
            # Show the dialog
            CreateObjectDialog(self.root, callback=on_object_created)
            
        except Exception as e:
            error_msg = f"Error creant nou objecte: {e}"
            messagebox.showerror("Error", error_msg)
            print(f"Debug - Error create_new_object: {e}")

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
            return        # Callback for when dimensions are updated
        def on_dimensions_updated(updated_entry, new_dimensions):
            print(f"Debug - Dimensions updated for {updated_entry.get('name', '')}: {new_dimensions}")
            
            # Find and update the corresponding entry in self.metadata
            # Try to match by original name first, then by modified name
            original_name = entry.get("name", "")
            updated_name = updated_entry.get("name", "")
            
            for i, meta_entry in enumerate(self.metadata):
                # Check if this is the entry we're looking for
                name_match = (meta_entry.get("name") == original_name or 
                             meta_entry.get("name") == updated_name)
                type_match = meta_entry.get("type") == entry.get("type")
                
                if name_match and type_match:
                    # Update the metadata entry with the new information
                    self.metadata[i] = updated_entry.copy()
                    print(f"Debug - Updated metadata entry: {self.metadata[i]}")
                    break
            
            # Refresh UI and save
            self._update_csv_tree()
            self.update_file_tree()
            self.save_csv_data()  # Auto-save after edit
            self.update_status(f"Dimensions actualitzades per '{updated_entry.get('name', '')}'")
            print(f"Debug - CSV saved and UI refreshed")
        
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
        ttk.Button(path_frame, text="Explorar...", command=lambda: self._browse_file_for_entry(path_var)).grid(row=0, column=1, padx=(5, 0))
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Guardar", command=lambda: self._save_new_entry(dialog, type_var, name_var, path_var)).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Cancel·lar", command=dialog.destroy).grid(row=0, column=1, padx=5)
        
        # Configure dialog
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
        try:
            if not name_var.get() or not path_var.get():
                messagebox.showwarning("Avís", "Tots els camps són obligatoris")
                return
            
            new_entry = {
                "type": type_var.get(),
                "name": name_var.get(),
                "file_path": path_var.get()
            }
            
            print(f"Debug - Adding new entry: {new_entry}")
            self.metadata.append(new_entry)
            self._update_csv_tree()
            self.update_file_tree()
            self.save_csv_data()  # Auto-save after adding
            self.update_status(f"Nova entrada '{new_entry['name']}' afegida i guardada")
            dialog.destroy()
            
        except Exception as e:
            error_msg = f"Error guardant nova entrada: {e}"
            messagebox.showerror("Error", error_msg)
            print(f"Debug - Error _save_new_entry: {e}")

    def save_csv_data(self):
        """Guarda les dades del CSV."""
        try:
            csv_path = self.csv_path_var.get()
            if not csv_path:
                messagebox.showwarning("Avís", "No s'ha especificat un fitxer CSV")
                return
                
            # Crear el directori si no existeix
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            
            with open(csv_path, "w", newline='', encoding='utf-8') as f:
                if self.metadata:
                    # Utilitzar els camps estàndard
                    fieldnames = ["type", "name", "file_path"]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    # Escriure cada entrada assegurant-nos que té els camps necessaris
                    for entry in self.metadata:
                        row = {
                            "type": entry.get("type", ""),
                            "name": entry.get("name", ""),
                            "file_path": entry.get("file_path", "")
                        }
                        writer.writerow(row)
                else:
                    # Si no hi ha metadades, crear un fitxer amb capçaleres
                    fieldnames = ["type", "name", "file_path"]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    
            messagebox.showinfo("Èxit", f"Dades guardades correctament a:\n{csv_path}")
            self.update_status("CSV guardat")
            
        except Exception as e:
            error_msg = f"Error guardant CSV: {e}"
            messagebox.showerror("Error", error_msg)
            print(f"Debug - Error save_csv_data: {e}")
            import traceback
            traceback.print_exc()

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
            self.geometry_editor_button.config(state=tk.DISABLED)
            self.smart_optimizer_button.config(state=tk.DISABLED)
            return
        
        try:
            dimensions = get_stp_dimensions(filepath)
            if dimensions:
                # Display dimensions in mm (no longer need to convert)
                length_mm = dimensions['length']
                width_mm = dimensions['width']
                height_mm = dimensions['height']
                
                info = f"Dimensions: {length_mm:.1f} x {width_mm:.1f} x {height_mm:.1f} mm"
                
                # Add shape information if available
                shape_type = dimensions.get('shape_type', 'rectangular')
                if shape_type != 'rectangular':
                    volume_factor = dimensions.get('volume_factor', 1.0)
                    info += f" | Forma: {shape_type} (factor volum: {volume_factor:.3f})"
                
                # Detectar geometria complexa per habilitar editor
                if dimensions.get('advanced_geometry', False):
                    total_faces = dimensions.get('total_faces', 0)
                    if total_faces > 20:  # Geometria complexa
                        info += f" | {total_faces} cares - Geometria complexa 🎛️"
                        self.geometry_editor_button.config(state=tk.NORMAL)
                        self.smart_optimizer_button.config(state=tk.NORMAL)  # NOU: Habilitar optimitzador
                        self.current_complex_geometry = dimensions  # Guardar per l'editor
                        
                        # Mostrar consell sobre el generador intel·ligent
                        if total_faces > 50:
                            self.root.after(500, lambda: self._show_intelligent_box_suggestion(total_faces))
                        
                        # Auto-obrir editor si és molt complexa
                        self._auto_open_geometry_editor_on_import(dimensions)
                    else:
                        info += f" | {total_faces} cares"
                        self.geometry_editor_button.config(state=tk.DISABLED)
                        self.smart_optimizer_button.config(state=tk.DISABLED)
                else:
                    self.geometry_editor_button.config(state=tk.DISABLED)
                    self.smart_optimizer_button.config(state=tk.DISABLED)
                
                self.file_info_var.set(info)
                # Actualitzar variables (now using mm)
                self.obj_vars[0].set(length_mm)
                self.obj_vars[1].set(width_mm)
                self.obj_vars[2].set(height_mm)
            else:
                self.file_info_var.set("Error llegint fitxer STP")
                self.geometry_editor_button.config(state=tk.DISABLED)
                self.smart_optimizer_button.config(state=tk.DISABLED)
        except Exception as e:
            self.file_info_var.set(f"Error: {str(e)}")
            self.geometry_editor_button.config(state=tk.DISABLED)
            self.smart_optimizer_button.config(state=tk.DISABLED)
    
    def _open_geometry_editor(self):
        """Obre l'editor de geometria en temps real OPTIMITZAT"""
        if not hasattr(self, 'current_complex_geometry') or not self.current_complex_geometry:
            messagebox.showerror("Error", "No hi ha geometria complexa carregada")
            return
        
        try:
            # Obtenir l'objecte de geometria
            geometry_object = self.current_complex_geometry.get('geometry_object')
            if not geometry_object:
                messagebox.showwarning("Avís", "No es pot accedir a l'objecte de geometria")
                return
            
            # Crear simplificador NOMÉS quan l'usuari ho demana
            from src.packassist.advanced_geometry import GeometrySimplifier, RealTimeGeometryViewer
            
            print(f"🔧 Creant simplificador per {len(geometry_object.faces)} cares...")
            simplifier = GeometrySimplifier(geometry_object)
            
            # Crear i mostrar l'editor optimitzat
            geometry_viewer = RealTimeGeometryViewer(simplifier)
            editor_window = geometry_viewer.create_interactive_viewer()
            
            print(f"🎛️ Editor obert - Geometria amb {len(geometry_object.faces)} cares")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error obrint l'editor de geometria: {str(e)}")
            print(f"❌ Error obrint editor: {e}")
    
    def _show_intelligent_box_suggestion(self, total_faces):
        """Mostra un consell sobre usar el generador intel·ligent."""
        response = messagebox.askyesno(
            "Geometria Complexa Detectada",
            f"S'ha detectat una geometria amb {total_faces:,} cares.\n\n"
            f"💡 Consell: Per objectes complexos, el Generador Intel·ligent "
            f"pot crear caixes optimitzades que s'adaptin millor a la forma.\n\n"
            f"Vols usar el Generador Intel·ligent ara?",
            icon='question'
        )
        
        if response:
            self._open_smart_optimizer()
    
    def _auto_open_geometry_editor_on_import(self, dimensions):
        """Obre automàticament l'editor si la geometria és molt complexa"""
        if not dimensions or not dimensions.get('advanced_geometry', False):
            return
            
        total_faces = dimensions.get('total_faces', 0)
        
        # Si té moltes cares, preguntar si vol obrir l'editor
        if total_faces > 100:
            response = messagebox.askyesno(
                "Geometria Complexa Detectada",
                f"S'ha detectat una geometria amb {total_faces:,} cares.\n\n"
                f"Vols obrir l'editor de simplificació per optimitzar el rendiment?",
                icon='question'
            )
            
            if response:
                # Esperar un moment perquè la interfície es carregui
                self.root.after(500, self._open_geometry_editor)
    
    def _open_smart_optimizer(self):
        """Obre el Generador Intel·ligent de Caixes Personalitzades."""
        if not hasattr(self, 'current_complex_geometry') or not self.current_complex_geometry:
            messagebox.showwarning("Avís", "No hi ha geometria complexa carregada per optimitzar")
            return
        
        try:
            # Obtenir l'objecte de geometria
            geometry_object = self.current_complex_geometry.get('geometry_object')
            if not geometry_object:
                messagebox.showwarning("Avís", "No es pot accedir a l'objecte de geometria")
                return
            
            print(f"🎯 Obrint Generador Intel·ligent de Caixes per {len(geometry_object.faces)} cares...")
            
            # Callback per quan es generi la caixa
            def on_box_generated(result):
                print(f"✅ Caixa intel·ligent generada: {result.face_count} cares, {result.efficiency:.1f}% eficiència")
                
                # Actualitzar la UI amb els resultats
                self.update_status(f"Caixa generada: {result.face_count} cares, {result.efficiency:.1f}% eficiència")
                
                # Actualitzar les dimensions de l'objecte amb la nova caixa
                self._update_dimensions_from_intelligent_box(result)
                
                # Mostrar informació detallada amb opció de càlcul automàtic
                info_message = (
                    f"🎯 Caixa Intel·ligent Generada\n\n"
                    f"📊 Cares: {result.face_count}\n"
                    f"📏 Volum: {result.box_volume:.2f} mm³\n"
                    f"📈 Eficiència: {result.efficiency:.1f}%\n"
                    f"📐 Àrea: {result.surface_area:.2f} mm²\n\n"
                    f"Les dimensions s'han actualitzat automàticament.\n"
                    f"Vols calcular l'empaquetament amb aquestes noves dimensions?"
                )
                
                # Preguntar si vol calcular automàticament
                response = messagebox.askyesno("Caixa Generada", info_message)
                if response:
                    # Canviar a la pestanya d'entrada manual si no hi és ja
                    self.notebook.select(1)  # Pestanya "Entrada Manual"
                    # Executar càlcul automàticament
                    self.root.after(100, self.calculate_manual)
            
            # Importar i crear el generador intel·ligent
            from src.packassist.intelligent_box_ui import create_intelligent_box_dialog
            
            # Crear el diàleg del generador intel·ligent
            intelligent_box_ui = create_intelligent_box_dialog(
                self.root, 
                geometry_object, 
                callback=on_box_generated
            )
            
            if intelligent_box_ui:
                print("🎯 Generador Intel·ligent de Caixes obert correctament")
            else:
                messagebox.showerror("Error", "No s'ha pogut crear el generador intel·ligent")
                
        except ImportError as e:
            messagebox.showerror(
                "Error d'Importació", 
                f"No s'han pogut carregar els mòduls necessaris:\n{e}\n\n"
                f"Assegura't que tens instal·lades les dependències:\n"
                f"• scikit-learn\n• scipy\n• numpy"
            )
            print(f"❌ Error d'importació: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Error obrint generador intel·ligent: {str(e)}")
            print(f"❌ Error obrint generador intel·ligent: {e}")
            traceback.print_exc()
    
    def _update_dimensions_from_intelligent_box(self, result):
        """
        Actualitza les dimensions de l'objecte amb la caixa generada.

        Args:
            result: BoxGenerationResult amb la informació de la caixa
        """
        try:
            # Calcular bounding box de la caixa generada
            vertices = result.vertices
            min_coords = np.min(vertices, axis=0)
            max_coords = np.max(vertices, axis=0)

            # Calcular dimensions
            length = max_coords[0] - min_coords[0]
            width = max_coords[1] - min_coords[1]
            height = max_coords[2] - min_coords[2]

            # Actualitzar variables de l'entrada manual
            self.obj_vars[0].set(length)  # Longitud
            self.obj_vars[1].set(width)   # Amplada
            self.obj_vars[2].set(height)  # Altura

            # IMPORTANT: Actualitzar la geometria complexa amb la nova caixa intel·ligent
            if hasattr(self, 'current_complex_geometry'):
                # Crear un nou mesh amb la caixa intel·ligent
                try:
                    import trimesh
                    # Crear mesh de la nova caixa intel·ligent
                    intelligent_mesh = trimesh.Trimesh(vertices=result.vertices, faces=result.faces)
                    
                    # Actualitzar geometria complexa amb informació de la caixa intel·ligent
                    self.current_complex_geometry.update({
                        'length': length,
                        'width': width,
                        'height': height,
                        'shape_type': 'intelligent_box',  # Marcar com caixa intel·ligent
                        'volume_factor': result.efficiency / 100.0,  # Usar eficiència com factor de volum
                        'advanced_geometry': True,
                        'total_faces': result.face_count,
                        'geometry_object': intelligent_mesh,  # Usar el nou mesh
                        'real_volume': result.box_volume,
                        'complexity_score': result.face_count,
                        'intelligent_box_result': result  # Guardar el resultat complet
                    })
                    print(f"🎯 Geometria actualitzada amb caixa intel·ligent de {result.face_count} cares")
                except Exception as mesh_error:
                    print(f"⚠️  Error creant mesh de la caixa: {mesh_error}")
                    # Fallback: actualitzar només les dimensions
                    self.current_complex_geometry.update({
                        'length': length,
                        'width': width,
                        'height': height,
                        'shape_type': 'intelligent_box_simple',
                        'volume_factor': result.efficiency / 100.0
                    })

            # Actualitzar informació del fitxer
            info_text = (
                f"Caixa Intel·ligent: {length:.1f} x {width:.1f} x {height:.1f} mm | "
                f"{result.face_count} cares, {result.efficiency:.1f}% eficiència 🎯"
            )
            self.file_info_var.set(info_text)

            print(f"🔄 Dimensions actualitzades: {length:.1f} x {width:.1f} x {height:.1f} mm")

        except Exception as e:
            print(f"❌ Error actualitzant dimensions: {e}")
            self.update_status("Error actualitzant dimensions de la caixa generada")

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
            
            # Convertir a diccionaris amb informació de forma per l'optimització
            box_dims = {
                "length": box_tuple[0],
                "width": box_tuple[1], 
                "height": box_tuple[2],
                "shape_type": "rectangular",  # Manual input assumes rectangular
                "volume_factor": 1.0
            }
            obj_dims = {
                "length": obj_tuple[0],
                "width": obj_tuple[1],
                "height": obj_tuple[2],
                "shape_type": "rectangular",  # Manual input assumes rectangular
                "volume_factor": 1.0
            }
            
            # Calcular
            self.manual_results.delete(1.0, tk.END)
            results_content = self._build_manual_results_content(box_dims, obj_dims)
            
            theoretical_max = calculate_theoretical_max(box_dims, obj_dims)
            result = optimize_packing(box_dims, obj_dims)
            
            results_content += self._build_optimization_results(result, theoretical_max)
            
            self.manual_results.insert(tk.END, results_content)
            
            # Guardar resultats per visualització
            if not result.get("error"):
                self.optimization_results = result
                self.visualize_btn.config(state=tk.NORMAL if result['max_objects'] > 0 else tk.DISABLED)
                
                # Si no caben objectes, suggerir usar el generador intel·ligent
                if result.get('max_objects', 0) == 0:
                    # Comprovar si té geometria complexa carregada
                    if hasattr(self, 'current_complex_geometry') and self.current_complex_geometry:
                        response = messagebox.askyesno(
                            "No caben objectes",
                            f"L'objecte de {obj_dims['length']:.1f}×{obj_dims['width']:.1f}×{obj_dims['height']:.1f} mm "
                            f"no cap en el contenidor de {box_dims['length']:.1f}×{box_dims['width']:.1f}×{box_dims['height']:.1f} mm.\n\n"
                            f"Vols usar el Generador Intel·ligent per crear una caixa optimitzada?"
                        )
                        if response:
                            self._open_smart_optimizer()
                            return
            else:
                self.visualize_btn.config(state=tk.DISABLED)
              # Afegir a la pestanya de resultats
            self._add_to_results_tab(results_content)
            self._save_results_automatically()
            self.update_status("Càlcul manual completat")
            
        except ValueError:
            messagebox.showerror("Error", "Introdueix valors numèrics vàlids")
        except Exception as e:
            messagebox.showerror("Error", f"Error durant el càlcul: {e}")
            
    def _build_manual_results_content(self, box_dims, obj_dims):
        """Construeix el contingut dels resultats manuals."""
        content = "🧮 CÀLCUL D'EMPAQUETAMENT MANUAL\n"
        content += "=" * 40 + "\n\n"
        content += f"📦 Contenidor:\n"
        content += f"   Longitud: {box_dims['length']:.1f} mm\n"
        content += f"   Amplada: {box_dims['width']:.1f} mm\n"
        content += f"   Altura: {box_dims['height']:.1f} mm\n"
        
        # Show container shape if not standard rectangular
        if box_dims.get('shape_type', 'rectangular') != 'rectangular':
            content += f"   Forma: {box_dims['shape_type']} (factor volum: {box_dims.get('volume_factor', 1.0):.3f})\n"
        
        content += "\n📋 Objecte:\n"
        content += f"   Longitud: {obj_dims['length']:.1f} mm\n"
        content += f"   Amplada: {obj_dims['width']:.1f} mm\n"
        content += f"   Altura: {obj_dims['height']:.1f} mm\n"
        
        # Show object shape if not standard rectangular
        if obj_dims.get('shape_type', 'rectangular') != 'rectangular':
            content += f"   Forma: {obj_dims['shape_type']} (factor volum: {obj_dims.get('volume_factor', 1.0):.3f})\n"
        
        content += "\n"
        return content

    def _build_optimization_results(self, result, theoretical_max):
        """Construeix els resultats d'optimització."""
        content = "📊 RESULTATS:\n"
        content += f"   ➕ Màxim teòric (per volum): {theoretical_max} unitats\n"
        
        if result.get("error"):
            content += f"   ❌ Error: {result['error']}\n"
        else:
            content += f"   ✅ Màxim real (3D packing): {result.get('max_objects', 0)} unitats\n"
            content += f"   📈 Eficiència d'espai: {result.get('efficiency', 0):.1f}%\n"
            content += f"   📏 Volum contenidor: {result.get('box_volume', 0):.1f} mm³\n"
            content += f"   📦 Volum utilitzat: {result.get('used_volume', 0):.1f} mm³\n"
        
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
                self.results_text.insert(tk.END, f"   📏 Dimensions: {box_dims['length']:.1f} x {box_dims['width']:.1f} x {box_dims['height']:.1f} mm\n")
                  # Show container shape information if available
                if 'shape_type' in box_dims and box_dims['shape_type'] != 'rectangular':
                    self.results_text.insert(tk.END, f"   🔷 Forma: {box_dims['shape_type']} (factor volum: {box_dims.get('volume_factor', 1.0):.3f})\n")
                
                self.results_text.insert(tk.END, "\n")
                
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
                      # Now both box_dims and obj_dims contain full shape information
                    theoretical_max = calculate_theoretical_max(box_dims, obj_dims)
                    result = optimize_packing(box_dims, obj_dims)
                    
                    self.results_text.insert(tk.END, f"  ➕ Objecte: {obj_info['name']}\n")
                    self.results_text.insert(tk.END, f"     📏 Dimensions: {obj_dims['length']:.1f} x {obj_dims['width']:.1f} x {obj_dims['height']:.1f} mm\n")
                    
                    # Show shape information if available
                    if 'shape_type' in obj_dims and obj_dims['shape_type'] != 'rectangular':
                        self.results_text.insert(tk.END, f"     🔷 Forma: {obj_dims['shape_type']} (factor volum: {obj_dims.get('volume_factor', 1.0):.3f})\n")
                    
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
        """Mostra la visualització 3D integrada amb matplotlib."""
        if not hasattr(self, 'optimization_results') or not self.optimization_results:
            messagebox.showwarning("Advertència", "No hi ha resultats d'optimització per visualitzar.")
            return
            
        try:
            self.update_status("Generant visualització 3D integrada...")
            
            # Crear una nueva ventana para la visualización
            viz_window = tk.Toplevel(self.root)
            viz_window.title("Visualització 3D - PackAssist")
            viz_window.geometry("900x700")
            viz_window.transient(self.root)
            
            # Crear el marco principal
            main_frame = ttk.Frame(viz_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Crear la figura de matplotlib
            fig = Figure(figsize=(10, 8), dpi=100)
            ax = fig.add_subplot(111, projection='3d')
            
            # Obtener datos de la optimización
            bins_data = self.optimization_results.get('bins', [])
            if not bins_data:
                messagebox.showerror("Error", "No hi ha dades de contenidors per visualitzar.")
                viz_window.destroy()
                return
            
            bin_data = bins_data[0]  # Usar el primer contenedor
            bin_info = bin_data['bin']
            items_info = bin_data['items']
              # Dimensiones del contenedor - convertir a float para evitar problemas con Decimal
            container_dims = bin_info['dimensions']
            container_length = float(container_dims[0])
            container_width = float(container_dims[1])
            container_height = float(container_dims[2])
            
            # Dibujar el contenedor (contorno)
            self._draw_container_outline(ax, container_length, container_width, container_height)
            
            # Dibujar los objetos
            colors = ['lightblue', 'lightgreen', 'lightyellow', 'lightpink', 'lightcyan', 'orange', 'purple', 'brown']
            for i, item in enumerate(items_info):
                # Convertir posición y dimensiones a float para evitar problemas con Decimal
                position = [float(x) for x in item['position']]
                dimensions = [float(x) for x in item['dimensions']]
                color = colors[i % len(colors)]
                
                self._draw_3d_box(ax, position, dimensions, color, alpha=0.7)
            
            # Configurar el gráfico
            ax.set_xlabel('Longitud (mm)')
            ax.set_ylabel('Amplada (mm)')
            ax.set_zlabel('Altura (mm)')
            ax.set_title(f'Empaquetament 3D - {len(items_info)} objectes en contenidor')
            
            # Hacer que los ejes tengan la misma escala
            self._set_axes_equal_3d(ax)
            
            # Crear el canvas de matplotlib
            canvas = FigureCanvasTkAgg(fig, main_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Agregar toolbar de navegación
            toolbar = NavigationToolbar2Tk(canvas, main_frame)
            toolbar.update()
            
            # Frame para información y controles
            info_frame = ttk.LabelFrame(main_frame, text="Informació", padding="5")
            info_frame.pack(fill=tk.X, pady=(5, 0))
            
            info_text = f"Contenidor: {container_length} × {container_width} × {container_height} mm\n"
            info_text += f"Objectes empaquetats: {len(items_info)}\n"
            info_text += f"Eficiència: {self.optimization_results.get('efficiency', 0)}%"
            
            ttk.Label(info_frame, text=info_text).pack(anchor=tk.W)
            
            # Botones de control
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(5, 0))
            
            ttk.Button(button_frame, text="💾 Guardar Imatge", 
                      command=lambda: self._save_3d_image(fig)).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="❌ Tancar", 
                      command=viz_window.destroy).pack(side=tk.RIGHT)
            
            self.update_status("Visualització 3D integrada oberta")
            
        except Exception as e:
            error_msg = f"Error obrint visualització 3D: {str(e)}"
            self.update_status("Error en la visualització")
            messagebox.showerror("Error", error_msg)
            print(f"Debug - Error en visualize_packing: {e}")
            import traceback
            traceback.print_exc()

    def close_visualization(self):
        """Funció mantinguda per compatibilitat - el nou sistema gestiona les finestres de forma independent."""
        self.update_status("Sistema de visualització independent activat")

    # === FUNCIONES AUXILIARES PARA VISUALIZACIÓN 3D ===
    
    def _draw_container_outline(self, ax, length, width, height):
        """Dibuja el contorno del contenedor."""
        # Convertir a float para evitar problemas con Decimal
        length, width, height = float(length), float(width), float(height)
        
        # Definir los vértices del contenedor
        vertices = [
            [0, 0, 0], [length, 0, 0], [length, width, 0], [0, width, 0],  # Base inferior
            [0, 0, height], [length, 0, height], [length, width, height], [0, width, height]  # Base superior
        ]
        
        # Definir las aristas del contenedor
        edges = [
            [0, 1], [1, 2], [2, 3], [3, 0],  # Base inferior
            [4, 5], [5, 6], [6, 7], [7, 4],  # Base superior
            [0, 4], [1, 5], [2, 6], [3, 7]   # Aristas verticales
        ]
        
        # Dibujar las aristas
        for edge in edges:
            points = np.array([vertices[edge[0]], vertices[edge[1]]])
            ax.plot3D(points[:, 0], points[:, 1], points[:, 2], 'k-', linewidth=2, alpha=0.8)
    
    def _draw_3d_box(self, ax, position, dimensions, color, alpha=0.7):
        """Dibuja una caja 3D en la posición especificada."""
        # Convertir a float para evitar problemas con Decimal
        x, y, z = float(position[0]), float(position[1]), float(position[2])
        dx, dy, dz = float(dimensions[0]), float(dimensions[1]), float(dimensions[2])
        
        # Definir los vértices de la caja
        vertices = np.array([
            [x, y, z], [x+dx, y, z], [x+dx, y+dy, z], [x, y+dy, z],  # Base inferior
            [x, y, z+dz], [x+dx, y, z+dz], [x+dx, y+dy, z+dz], [x, y+dy, z+dz]  # Base superior
        ])
        
        # Definir las caras de la caja
        faces = [
            [vertices[0], vertices[1], vertices[2], vertices[3]],  # Base inferior
            [vertices[4], vertices[5], vertices[6], vertices[7]],  # Base superior
            [vertices[0], vertices[1], vertices[5], vertices[4]],  # Cara frontal
            [vertices[2], vertices[3], vertices[7], vertices[6]],  # Cara trasera
            [vertices[1], vertices[2], vertices[6], vertices[5]],  # Cara derecha
            [vertices[4], vertices[7], vertices[3], vertices[0]]   # Cara izquierda
        ]
        
        # Crear y agregar las caras
        poly3d = [[tuple(vertex) for vertex in face] for face in faces]
        ax.add_collection3d(Poly3DCollection(poly3d, alpha=alpha, facecolor=color, edgecolor='black', linewidth=0.5))
    
    def _set_axes_equal_3d(self, ax):
        """Hace que los ejes 3D tengan la misma escala."""
        # Obtener los límites actuales
        x_limits = ax.get_xlim3d()
        y_limits = ax.get_ylim3d()
        z_limits = ax.get_zlim3d()
        
        # Calcular rangos
        x_range = abs(x_limits[1] - x_limits[0])
        x_middle = np.mean(x_limits)
        y_range = abs(y_limits[1] - y_limits[0])
        y_middle = np.mean(y_limits)
        z_range = abs(z_limits[1] - z_limits[0])
        z_middle = np.mean(z_limits)
        
        # El radio del plot es la mitad del rango máximo
        plot_radius = 0.5 * max([x_range, y_range, z_range])
        
        # Establecer límites iguales
        ax.set_xlim3d([x_middle - plot_radius, x_middle + plot_radius])
        ax.set_ylim3d([y_middle - plot_radius, y_middle + plot_radius])
        ax.set_zlim3d([z_middle - plot_radius, z_middle + plot_radius])
    
    def _save_3d_image(self, fig):
        """Guarda la imagen 3D como archivo."""
        try:
            filename = filedialog.asksaveasfilename(
                title="Guardar visualització 3D",
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("PDF files", "*.pdf"), ("SVG files", "*.svg"), ("All files", "*.*")]
            )
            
            if filename:
                fig.savefig(filename, dpi=300, bbox_inches='tight')
                messagebox.showinfo("Èxit", f"Imatge guardada a:\n{filename}")
                self.update_status("Imatge 3D guardada")
        except Exception as e:            messagebox.showerror("Error", f"Error guardant la imatge: {e}")

    # === FUNCIONES AUXILIARES ===
    
    def _validate_entry_file(self, file_path):
        """Valida si un fitxer d'entrada existeix."""
        if not file_path:
            return False
            
        # For regular file paths, check if they exist
        return os.path.exists(file_path)

    def _get_entry_dimensions(self, file_path):
        """Obté les dimensions d'un fitxer STP."""
        if not self._validate_entry_file(file_path):
            return None
        try:
            result = get_stp_dimensions(file_path)
            
            # Verificar si és geometria complexa
            if result and result.get('advanced_geometry'):
                complex_geometry = result.get('complex_geometry_object')
                if complex_geometry:
                    self.current_complex_geometry = {
                        'geometry_object': complex_geometry,
                        'face_count': result.get('total_faces', 0),
                        'volume': complex_geometry.get_real_volume(),
                        'bbox': complex_geometry.get_bounding_box()
                    }
            
            return result
        except Exception as e:
            return None

# ...existing code...
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