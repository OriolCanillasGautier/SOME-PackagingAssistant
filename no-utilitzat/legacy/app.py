import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import threading
import os
import csv
import sys
import traceback
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pyvista as pv
from pyvistaqt import BackgroundPlotter
import trimesh

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
        ttk.Label(self.main_frame, text="PackAssist 3D", style='Title.TLabel').grid(row=0, column=0, pady=(0, 10))
        
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
        self.notebook.add(stp_frame, text="Fitxers STP")
        stp_frame.columnconfigure(0, weight=1)
        stp_frame.rowconfigure(2, weight=1)
        
        # Gestió de fitxers
        file_frame = ttk.LabelFrame(stp_frame, text="Gestió de fitxers", padding="10")
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        
        ttk.Button(file_frame, text="📂 Carregar CSV", command=self.load_csv_file).grid(row=0, column=0, padx=(0, 5))
        self.csv_path_var = tk.StringVar(value=CSV_PATH)
        ttk.Entry(file_frame, textvariable=self.csv_path_var, state='readonly').grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        ttk.Button(file_frame, text="Recarregar", command=self.reload_metadata).grid(row=0, column=2, padx=(5, 0))
        
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
        box_frame = ttk.LabelFrame(parent, text="Dimensions del contenidor (mm)", padding="10")
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
        obj_frame = ttk.LabelFrame(parent, text="Dimensions de l'objecte (mm)", padding="10")
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
            text="Optimitzar",
            command=self._open_smart_optimizer,
            state=tk.DISABLED
        )
        self.smart_optimizer_button.grid(row=0, column=2)
        
        self.file_info_var = tk.StringVar(value="Dimensions: - x - x - cm")
        ttk.Label(self.file_input_frame, textvariable=self.file_info_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        self.file_input_frame.grid_remove()

    def _create_manual_results_section(self, parent):
        """Crea la secció de resultats manuals."""
        results_frame = ttk.LabelFrame(parent, text="Resultats", padding="10")
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
        
        ttk.Button(controls_frame, text="Recarregar CSV", command=self.reload_csv_data).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(controls_frame, text="Afegir Entrada", command=self.add_csv_entry).grid(row=0, column=1, padx=5)
        ttk.Button(controls_frame, text="Nova Caixa", command=self.create_new_box).grid(row=0, column=2, padx=5)
        ttk.Button(controls_frame, text="Nou Objecte", command=self.create_new_object).grid(row=0, column=3, padx=5)
        ttk.Button(controls_frame, text="Editar", command=self.edit_selected_item).grid(row=0, column=4, padx=5)
        ttk.Button(controls_frame, text="Guardar CSV", command=self.save_csv_data).grid(row=0, column=5, padx=(5, 0))
        
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
        self.notebook.add(results_frame, text="Resultats")
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(1, weight=1)
        
        # Controls
        controls_frame = ttk.Frame(results_frame)
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(controls_frame, text="Exportar Resultats", command=self.export_results).grid(row=0, column=0, padx=(0, 10))
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
        self.viz_frame = ttk.LabelFrame(self.main_frame, text="Visualització 3D", padding="10")
        self.viz_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        viz_buttons_frame = ttk.Frame(self.viz_frame)
        viz_buttons_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.visualize_btn = ttk.Button(viz_buttons_frame, text="Visualitzar Empaquetament", command=self.visualize_packing, state=tk.DISABLED)
        self.visualize_btn.grid(row=0, column=0, padx=5)
        
        self.close_viz_btn = ttk.Button(viz_buttons_frame, text="Tancar Visualització", command=self.close_visualization, state=tk.DISABLED)
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
            status = "Valid" if self._validate_entry_file(file_path) else "No valid"
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

    def _get_entry_dimensions(self, file_path):
        """Obté les dimensions d'una entrada del CSV amb suport per geometria complexa."""
        if not hasattr(self, 'metadata') or not self.metadata:
            return None
        
        for entry in self.metadata:
            if entry.get('file_path', '') == file_path:
                # Si hi ha dimensions al CSV, usar-les
                if all(key in entry for key in ['length', 'width', 'height']):
                    try:
                        base_dims = {
                            'length': float(entry['length']),
                            'width': float(entry['width']),
                            'height': float(entry['height']),
                            'shape_type': 'rectangular',  # Per defecte
                            'volume_factor': 1.0
                        }
                        
                        # Intentar carregar geometria avançada si és un fitxer STP
                        if file_path.lower().endswith('.stp') and os.path.exists(file_path):
                            try:
                                from src.packassist.advanced_geometry import analyze_stp_real_geometry
                                advanced_analysis = analyze_stp_real_geometry(file_path)
                                
                                if advanced_analysis and advanced_analysis.get('total_faces', 0) > 6:
                                    print(f"GEOMETRIA COMPLEXA detectada: {advanced_analysis['total_faces']} cares")
                                    base_dims.update({
                                        'shape_type': 'complex',
                                        'advanced_geometry': True,
                                        'geometry_analysis': advanced_analysis,
                                        'total_faces': advanced_analysis['total_faces'],
                                        'volume_factor': advanced_analysis.get('volume_efficiency', 1.0),
                                        'complexity_score': advanced_analysis.get('complexity_score', 0.0)
                                    })
                                    # Guardar la geometria complexa per visualització posterior
                                    self.current_complex_geometry = advanced_analysis
                                else:
                                    print(f"GEOMETRIA SIMPLE detectada per {file_path}")
                            except Exception as e:
                                print(f"Error analitzant geometria avançada de {file_path}: {e}")
                                
                        return base_dims
                        
                    except (ValueError, TypeError):
                        pass
                
                # Si no hi ha dimensions al CSV, intentar carregar del fitxer STP
                if os.path.exists(file_path):
                    try:
                        from src.packassist.stp_loader import load_stp_file
                        stp_result = load_stp_file(file_path)
                        if stp_result and 'bounding_box' in stp_result:
                            bbox = stp_result['bounding_box']
                            return {
                                'length': bbox.get('length', 0),
                                'width': bbox.get('width', 0),
                                'height': bbox.get('height', 0),
                                'shape_type': 'rectangular',
                                'volume_factor': 1.0
                            }
                    except Exception as e:
                        print(f"Error carregant dimensions de {file_path}: {e}")
                
                break
        
        return None

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
            
            print(f"Creating simplifier for {len(geometry_object.faces)} faces...")
            simplifier = GeometrySimplifier(geometry_object)
            
            # Crear i mostrar l'editor optimitzat
            geometry_viewer = RealTimeGeometryViewer(simplifier)
            editor_window = geometry_viewer.create_interactive_viewer()
            
            print(f"🎛️ Editor obert - Geometria amb {len(geometry_object.faces)} cares")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error obrint l'editor de geometria: {str(e)}")
            print(f"ERROR: Error opening editor: {e}")
    
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
            
            print(f"Opening Intelligent Box Generator for {len(geometry_object.faces)} faces...")
            
            # Callback per quan es generi la caixa
            def on_box_generated(result):
                print(f"SUCCESS: Intelligent box generated: {result.face_count} faces, {result.efficiency:.1f}% efficiency")
                
                # Actualitzar la UI amb els resultats
                self.update_status(f"Caixa generada: {result.face_count} cares, {result.efficiency:.1f}% eficiència")
                
                # Actualitzar les dimensions de l'objecte amb la nova caixa
                self._update_dimensions_from_intelligent_box(result)
                
                # Mostrar informació detallada
                info_message = (
                    f"🎯 Caixa Intel·ligent Generada\n\n"
                    f"📊 Cares: {result.face_count}\n"
                    f"📏 Volum: {result.box_volume:.2f} mm³\n"
                    f"📈 Eficiència: {result.efficiency:.1f}%\n"
                    f"📐 Àrea: {result.surface_area:.2f} mm²\n\n"
                    f"Les dimensions s'han actualitzat automàticament."
                )
                messagebox.showinfo("Caixa Generada", info_message)
            
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
      
    # === FUNCIONS DE VISUALITZACIÓ 3D (NOVA VERSIÓ AMB PYVISTA) ===
    
    def visualize_packing(self):
        """Mostra la visualització 3D amb PyVista, renderitzant malles reals."""
        if not hasattr(self, 'optimization_results') or not self.optimization_results:
            messagebox.showwarning("Advertència", "No hi ha resultats d'optimització per visualitzar.")
            return

        if self.optimization_results.get("error"):
            messagebox.showerror("Error", f"No es pot visualitzar un resultat amb error: {self.optimization_results['error']}")
            return

        try:
            self.update_status("Generant visualització 3D amb PyVista...")

            # Crear plotter PyVista normal (sense integració Tkinter)
            plotter = pv.Plotter(title="Visualització 3D de l'Empaquetament - PackAssist")
            plotter.background_color = 'white'
            
            # --- 1. Dibuixar el contenidor ---
            bin_data = self.optimization_results.get('bins', [{}])[0].get('bin', {})
            if not bin_data:
                messagebox.showerror("Error", "No s'han trobat dades del contenidor en els resultats.")
                plotter.close()
                return
            
            container_dims = bin_data.get('dimensions')
            if not container_dims:
                 messagebox.showerror("Error", "No s'han trobat les dimensions del contenidor.")
                 plotter.close()
                 return

            container_mesh = pv.Cube(bounds=(0, container_dims[0], 0, container_dims[1], 0, container_dims[2]))
            plotter.add_mesh(container_mesh, style='wireframe', color='gray', line_width=5, label='Contenidor')

            # --- 2. Dibuixar els objectes empaquetats ---
            items_info = self.optimization_results.get('bins', [{}])[0].get('items', [])
            if not items_info:
                messagebox.showwarning("Avís", "No s'han trobat objectes empaquetats per visualitzar.")
                # Encara mostrem el contenidor buit
                plotter.camera_position = 'iso'
                plotter.show_grid()
                plotter.add_axes()
                plotter.add_legend()
                plotter.set_background('white')
                plotter.show(interactive=True)
                return

            # Obtenir la malla de l'objecte original
            obj_mesh = None
            obj_dims = self.optimization_results.get('obj_dims', {})
            
            # Primer, intentar usar la geometria complexa si està disponible
            if hasattr(self, 'current_complex_geometry') and self.current_complex_geometry:
                try:
                    geom_obj = self.current_complex_geometry.get('geometry_object')
                    if geom_obj:
                        # Convertir ComplexGeometry a PyVista mesh
                        vertices = []
                        faces = []
                        face_count = 0
                        
                        for face in geom_obj.faces:
                            if len(face.vertices) >= 3:
                                # Afegir vèrtexs de la cara
                                face_vertices = []
                                for vertex in face.vertices:
                                    vertices.append(vertex)
                                    face_vertices.append(len(vertices) - 1)
                                
                                # Crear triangles per la cara (triangulació simple)
                                for i in range(1, len(face_vertices) - 1):
                                    faces.extend([3, face_vertices[0], face_vertices[i], face_vertices[i+1]])
                        
                        if vertices and faces:
                            import numpy as np
                            vertices_array = np.array(vertices)
                            faces_array = np.array(faces)
                            obj_mesh = pv.PolyData(vertices_array, faces_array)
                            print(f"DEBUG: Usant geometria complexa amb {len(geom_obj.faces)} cares")
                        else:
                            print("DEBUG: No s'han pogut extreure cares vàlides de la geometria complexa")
                except Exception as e:
                    print(f"DEBUG: Error processant geometria complexa: {e}")
            
            # Si no tenim geometria complexa, crear un cub amb les dimensions correctes
            if obj_mesh is None and obj_dims and all(k in obj_dims for k in ['length', 'width', 'height']):
                # Crear cub amb les dimensions reals
                obj_length = obj_dims['length']
                obj_width = obj_dims['width'] 
                obj_height = obj_dims['height']
                obj_mesh = pv.Cube(bounds=(
                    -obj_length/2, obj_length/2,
                    -obj_width/2, obj_width/2, 
                    -obj_height/2, obj_height/2
                ))
                print(f"DEBUG: Cub creat amb dimensions: {obj_length} x {obj_width} x {obj_height}")
            elif obj_mesh is None:
                # Fallback amb dimensions per defecte
                obj_mesh = pv.Cube(bounds=(-0.5, 0.5, -0.5, 0.5, -0.5, 0.5))
                print("DEBUG: Usant cub per defecte")

            colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
            
            print(f"DEBUG: Visualitzant {len(items_info)} objectes")
            
            for i, item in enumerate(items_info):
                pos = item.get('position', [0, 0, 0])
                dims = item.get('dimensions', [1, 1, 1]) # Bounding box de l'item
                
                print(f"DEBUG: Objecte {i+1} - Posició: {pos}, Dimensions: {dims}")
                
                if not pos or len(pos) != 3:
                    print(f"WARNING: Posició invalida per objecte {i+1}: {pos}")
                    continue
                    
                if not dims or len(dims) != 3:
                    print(f"WARNING: Dimensions invalides per objecte {i+1}: {dims}")
                    continue

                # Crear una còpia de la malla per aquest objecte
                item_mesh = obj_mesh.copy()

                # Posicionar l'objecte: la posició és la cantonada inferior esquerra
                # Ajustem al centre de l'objecte per a la visualització
                center_pos = [
                    pos[0] + dims[0]/2, 
                    pos[1] + dims[1]/2, 
                    pos[2] + dims[2]/2
                ]
                
                item_mesh.translate(center_pos, inplace=True)
                
                # Afegir l'objecte al plotter amb color
                color = colors[i % len(colors)]
                plotter.add_mesh(item_mesh, color=color, opacity=0.8, show_edges=True, label=f'Objecte {i+1}')
                
                print(f"DEBUG: Objecte {i+1} col·locat al centre: {center_pos}")

            # --- 3. Configuració final del plotter ---
            plotter.camera_position = 'iso'
            plotter.show_grid()
            plotter.add_axes()
            plotter.add_legend()
            plotter.set_background('white')
            
            # Mostrar la visualització
            plotter.show(interactive=True)
            
            self.update_status(f"Visualització 3D generada per a {len(items_info)} objectes.")
            self.close_viz_btn.config(state=tk.NORMAL)
            self.current_plotter = plotter # Guardem referència per tancar-lo

        except Exception as e:
            messagebox.showerror("Error de Visualització", f"No s'ha pogut generar la visualització 3D:\n{e}")
            print(f"❌ Error en visualize_packing: {e}")
            traceback.print_exc()
            self.update_status("Error generant visualització")

    def close_visualization(self):
        """Tanca la finestra de visualització de PyVista."""
        if hasattr(self, 'current_plotter') and self.current_plotter:
            try:
                # Tanca la finestra del plotter i neteja recursos
                self.current_plotter.close()
                self.current_plotter = None
                self.update_status("Visualització tancada")
                self.close_viz_btn.config(state=tk.DISABLED)
                print("✅ Finestra de PyVista tancada correctament.")
            except Exception as e:
                print(f"❌ Error tancant la visualització de PyVista: {e}")
        else:
            self.update_status("No hi ha cap visualització activa per tancar")

    # === FUNCIONES AUXILIARES PARA VISUALIZACIÓN 3D ===
    
    def _draw_container_outline(self, ax, length, width, height):
        # Aquesta funció ja no és necessària amb PyVista, però la mantenim per si de cas
        # ... (codi original)
        pass
    
    def _draw_3d_box(self, ax, position, dimensions, color, alpha=0.7):
        # Aquesta funció ja no és necessària amb PyVista
        pass

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