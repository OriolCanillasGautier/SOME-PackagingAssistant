"""
Diàlegs i finestres emergents
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from typing import Dict, Any, Callable, Optional

class ExportDialog:
    """Diàleg per exportar resultats"""
    
    def __init__(self, parent, results: Dict[str, Any], callback: Callable):
        self.parent = parent
        self.results = results
        self.callback = callback
        self.window = None
    
    def show(self):
        """Mostra el diàleg d'exportació"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("📤 Exportar Resultats")
        self.window.geometry("500x400")
        self.window.resizable(False, False)
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # Centrar finestra
        self.window.geometry("+%d+%d" % (
            self.parent.winfo_rootx() + 50, 
            self.parent.winfo_rooty() + 50
        ))
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Crea els widgets del diàleg"""
        # Variables
        self.export_text = tk.BooleanVar(value=True)
        self.export_csv = tk.BooleanVar(value=False)
        self.export_json = tk.BooleanVar(value=False)
        self.export_stl = tk.BooleanVar(value=False)
        self.export_image = tk.BooleanVar(value=False)
        self.include_viz = tk.BooleanVar(value=False)
        
        # Títol
        title_frame = ttk.Frame(self.window, padding="20")
        title_frame.pack(fill=tk.X)
        
        ttk.Label(title_frame, text="📤 Opcions d'Exportació", 
                 font=('Arial', 14, 'bold')).pack()
        ttk.Label(title_frame, text="Selecciona els formats a exportar:").pack(pady=(5, 0))
        
        # Opcions de format
        options_frame = ttk.LabelFrame(self.window, text="Formats", padding="15")
        options_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        
        ttk.Checkbutton(options_frame, text="📄 Informe detallat (TXT)", 
                       variable=self.export_text).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="📊 Dades tabulars (CSV)", 
                       variable=self.export_csv).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="🔧 Dades estructurades (JSON)", 
                       variable=self.export_json).pack(anchor=tk.W, pady=2)
        
        ttk.Separator(options_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        ttk.Label(options_frame, text="Opcions avançades:", 
                 font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(5, 5))
        
        ttk.Checkbutton(options_frame, text="🎯 STL amb peces posicionades", 
                       variable=self.export_stl).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="📸 Captura de la vista 3D", 
                       variable=self.export_image).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="📈 Incloure visualitzacions", 
                       variable=self.include_viz).pack(anchor=tk.W, pady=2)
        
        # Informació actual
        info_frame = ttk.LabelFrame(self.window, text="Informació", padding="10")
        info_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        positions = self.results.get('positions', [])
        efficiency = self.results.get('efficiency', 0)
        
        info_text = f"• Peces: {len(positions)}\n• Eficiència: {efficiency:.2f}%"
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)
        
        # Botons
        buttons_frame = ttk.Frame(self.window, padding="20")
        buttons_frame.pack(fill=tk.X)
        
        ttk.Button(buttons_frame, text="📤 Exportar", 
                  command=self._do_export).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(buttons_frame, text="❌ Cancel·lar", 
                  command=self.window.destroy).pack(side=tk.RIGHT)
    
    def _do_export(self):
        """Executa l'exportació"""
        options = {
            'text': self.export_text.get(),
            'csv': self.export_csv.get(),
            'json': self.export_json.get(),
            'stl': self.export_stl.get(),
            'image': self.export_image.get(),
            'visualizations': self.include_viz.get()
        }
        
        if not any(options.values()):
            messagebox.showinfo("Avís", "Selecciona almenys una opció")
            return
        
        self.window.destroy()
        self.callback(options)


class VisualizationDialog:
    """Diàleg per opcions de visualització 3D"""
    
    def __init__(self, parent, results: Dict[str, Any], callback: Callable):
        self.parent = parent
        self.results = results
        self.callback = callback
        self.window = None
    
    def show(self):
        """Mostra el diàleg de visualització"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("🎮 Opcions de Visualització 3D")
        self.window.geometry("600x650")
        self.window.resizable(False, False)
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # Centrar finestra
        self.window.geometry("+%d+%d" % (
            self.parent.winfo_rootx() + 50,
            self.parent.winfo_rooty() + 50
        ))
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Crea els widgets del diàleg"""
        # Variables d'opcions visuals
        self.show_wireframe = tk.BooleanVar(value=True)
        self.show_labels = tk.BooleanVar(value=True)
        self.use_gradient = tk.BooleanVar(value=False)
        self.show_axes = tk.BooleanVar(value=True)
        self.show_grid = tk.BooleanVar(value=True)
        self.show_edges = tk.BooleanVar(value=False)
        
        # Variables de colors i estil
        self.color_scheme = tk.StringVar(value="solid")
        self.background_color = tk.StringVar(value="white")
        self.window_size = tk.StringVar(value="1200x900")
        
        # Variables d'exportació
        self.auto_screenshot = tk.BooleanVar(value=False)
        self.auto_stl_export = tk.BooleanVar(value=False)
        self.auto_json_export = tk.BooleanVar(value=False)
        self.auto_csv_export = tk.BooleanVar(value=False)
        
        # Títol
        title_frame = ttk.Frame(self.window, padding="20")
        title_frame.pack(fill=tk.X)
        
        ttk.Label(title_frame, text="🎮 Configuració Avançada de Visualització", 
                 font=('Arial', 14, 'bold')).pack()
        
        positions = self.results.get('positions', [])
        num_pieces = len(positions)
        efficiency = self.results.get('efficiency', 0)
        ttk.Label(title_frame, text=f"Preparant {num_pieces} peces • Eficiència: {efficiency:.1f}%").pack(pady=(5, 0))
        
        # Crear notebook per pestanyes
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        
        # Pestanya 1: Opcions visuals
        viz_frame = ttk.Frame(notebook, padding="15")
        notebook.add(viz_frame, text="🎨 Visual")
        
        ttk.Checkbutton(viz_frame, text="📐 Wireframe del contenidor", 
                       variable=self.show_wireframe).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(viz_frame, text="🏷️ Etiquetes de peces", 
                       variable=self.show_labels).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(viz_frame, text="📏 Eixos de coordenades", 
                       variable=self.show_axes).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(viz_frame, text="📊 Reixa de fons", 
                       variable=self.show_grid).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(viz_frame, text="🔲 Vores de peces", 
                       variable=self.show_edges).pack(anchor=tk.W, pady=2)
        
        # Esquema de colors
        color_frame = ttk.LabelFrame(viz_frame, text="Colors", padding="10")
        color_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Radiobutton(color_frame, text="🎨 Colors sòlids (recomanat)", 
                       variable=self.color_scheme, value="solid").pack(anchor=tk.W)
        ttk.Radiobutton(color_frame, text="🌈 Gradient per altura", 
                       variable=self.color_scheme, value="gradient").pack(anchor=tk.W)
        ttk.Radiobutton(color_frame, text="🎯 Color per densitat", 
                       variable=self.color_scheme, value="density").pack(anchor=tk.W)
        
        # Pestanya 2: Configuració
        config_frame = ttk.Frame(notebook, padding="15")
        notebook.add(config_frame, text="⚙️ Configuració")
        
        # Fons
        bg_frame = ttk.LabelFrame(config_frame, text="Color de fons", padding="10")
        bg_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Radiobutton(bg_frame, text="⬜ Blanc", 
                       variable=self.background_color, value="white").pack(anchor=tk.W)
        ttk.Radiobutton(bg_frame, text="⬛ Negre", 
                       variable=self.background_color, value="black").pack(anchor=tk.W)
        ttk.Radiobutton(bg_frame, text="🌫️ Gris", 
                       variable=self.background_color, value="gray").pack(anchor=tk.W)
        
        # Mida de finestra
        size_frame = ttk.LabelFrame(config_frame, text="Mida de finestra", padding="10")
        size_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Radiobutton(size_frame, text="📱 Petita (800x600)", 
                       variable=self.window_size, value="800x600").pack(anchor=tk.W)
        ttk.Radiobutton(size_frame, text="💻 Mitjana (1200x900)", 
                       variable=self.window_size, value="1200x900").pack(anchor=tk.W)
        ttk.Radiobutton(size_frame, text="🖥️ Gran (1600x1200)", 
                       variable=self.window_size, value="1600x1200").pack(anchor=tk.W)
        
        # Pestanya 3: Exportació automàtica
        export_frame = ttk.Frame(notebook, padding="15")
        notebook.add(export_frame, text="📤 Exportació")
        
        ttk.Checkbutton(export_frame, text="📸 Capturar screenshot PNG", 
                       variable=self.auto_screenshot).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(export_frame, text="🎯 Exportar STL posicionat", 
                       variable=self.auto_stl_export).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(export_frame, text="📋 Exportar dades JSON", 
                       variable=self.auto_json_export).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(export_frame, text="📊 Exportar taula CSV", 
                       variable=self.auto_csv_export).pack(anchor=tk.W, pady=2)
        
        ttk.Label(export_frame, text="💡 Els fitxers s'exportaran automàticament\ndespués de la visualització", 
                 foreground='blue', justify=tk.CENTER).pack(pady=(10, 0))
        
        # Advertència si moltes peces
        positions = self.results.get('positions', [])
        num_pieces = len(positions)
        if num_pieces > 200:
            warning_frame = ttk.LabelFrame(self.window, text="⚠️ Advertència", padding="10")
            warning_frame.pack(fill=tk.X, padx=20, pady=(10, 0))
            
            warning_text = f"{num_pieces} peces detectades.\nLa visualització pot ser lenta."
            ttk.Label(warning_frame, text=warning_text, foreground='orange').pack()
            
            # Deshabilitar etiquetes per defecte
            self.show_labels.set(False)
        
        # Botons
        buttons_frame = ttk.Frame(self.window, padding="20")
        buttons_frame.pack(fill=tk.X)
        
        ttk.Button(buttons_frame, text="✅ Aplicar i Visualitzar", 
                  command=self._do_visualize).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(buttons_frame, text="📤 Només Exportar", 
                  command=self._export_only).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(buttons_frame, text="❌ Cancel·lar", 
                  command=self.window.destroy).pack(side=tk.LEFT)
    
    def _do_visualize(self):
        """Executa la visualització amb totes les opcions configurades"""
        options = {
            # Opcions visuals bàsiques
            'show_wireframe': self.show_wireframe.get(),
            'show_labels': self.show_labels.get(),
            'show_axes': self.show_axes.get(),
            'show_grid': self.show_grid.get(),
            'show_edges': self.show_edges.get(),
            
            # Esquema de colors
            'color_scheme': self.color_scheme.get(),
            'use_gradient': self.color_scheme.get() == 'gradient',
            
            # Configuració de finestra
            'background_color': self.background_color.get(),
            'window_size': self.window_size.get(),
            
            # Exportació automàtica
            'auto_screenshot': self.auto_screenshot.get(),
            'auto_stl_export': self.auto_stl_export.get(),
            'auto_json_export': self.auto_json_export.get(),
            'auto_csv_export': self.auto_csv_export.get()
        }
        
        self.window.destroy()
        self.callback('visualize', options)
    
    def _export_only(self):
        """Només exporta sense visualitzar"""
        export_options = {
            'auto_stl_export': self.auto_stl_export.get(),
            'auto_json_export': self.auto_json_export.get(),
            'auto_csv_export': self.auto_csv_export.get(),
            'auto_screenshot': False  # No screenshot sense visualització
        }
        
        self.window.destroy()
        self.callback('export', export_options)


class ProgressDialog:
    """Diàleg de progrés per operacions llargues"""
    
    def __init__(self, parent, title: str = "Processant..."):
        self.parent = parent
        self.title = title
        self.window = None
        self.progress_var = None
        self.status_var = None
    
    def show(self):
        """Mostra el diàleg de progrés"""
        self.window = tk.Toplevel(self.parent)
        self.window.title(self.title)
        self.window.geometry("400x150")
        self.window.resizable(False, False)
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # Centrar
        self.window.geometry("+%d+%d" % (
            self.parent.winfo_rootx() + 100,
            self.parent.winfo_rooty() + 100
        ))
        
        # Variables
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="Iniciant...")
        
        # Widgets
        frame = ttk.Frame(self.window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, textvariable=self.status_var, 
                 font=('Arial', 10)).pack(pady=(0, 10))
        
        progress_bar = ttk.Progressbar(frame, variable=self.progress_var, 
                                     maximum=100, length=300)
        progress_bar.pack(pady=(0, 10))
        
        ttk.Button(frame, text="Cancel·lar", 
                  command=self.close).pack()
    
    def update(self, progress: float, status: str):
        """Actualitza el progrés"""
        if self.window:
            self.progress_var.set(progress)
            self.status_var.set(status)
            self.window.update()
    
    def close(self):
        """Tanca el diàleg"""
        if self.window:
            self.window.destroy()
            self.window = None
