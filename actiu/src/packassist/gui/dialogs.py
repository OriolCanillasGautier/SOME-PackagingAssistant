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
        
        # Usar variables persistents del parent si existeixen
        # Comprovació més simple per evitar problemes
        self.persistent_vars = hasattr(parent, 'viz_show_wireframe')
        
        print(f"🔧 Debug variables persistents:")
        print(f"   Parent type: {type(parent).__name__}")
        print(f"   Té viz_show_wireframe: {hasattr(parent, 'viz_show_wireframe')}")
        print(f"   Té viz_show_labels: {hasattr(parent, 'viz_show_labels')}")
        print(f"   Té viz_container_color: {hasattr(parent, 'viz_container_color')}")
        print(f"   Variables persistents detectades: {self.persistent_vars}")
        
        if self.persistent_vars:
            print(f"✅ Variables persistents trobades!")
            if hasattr(parent, 'viz_show_wireframe'):
                print(f"   viz_show_wireframe = {parent.viz_show_wireframe.get()}")
        else:
            print("❌ Variables persistents NO trobades")
            print(f"   Atributs parent amb 'viz_': {[attr for attr in dir(parent) if attr.startswith('viz_')]}")
    
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
        # Carregar configuració del JSON MESTRA del parent si està disponible
        json_config = getattr(self.parent, 'json_config', None)
        
        if json_config:
            # PRIORITAT: Usar configuració del JSON MESTRA
            print(f"🔧 Carregant configuració del JSON MESTRA:")
            print(f"   Color scheme: {json_config.get('color_scheme', 'density')}")
            print(f"   Wireframe color: {json_config.get('wireframe_color', 'blue')}")
            print(f"   Background: {json_config.get('background_color', 'white')}")
            
            # Crear variables basades en la configuració JSON
            self.show_wireframe = tk.BooleanVar(value=json_config.get('show_wireframe', True))
            self.show_labels = tk.BooleanVar(value=json_config.get('show_labels', True))
            self.use_gradient = tk.BooleanVar(value=json_config.get('color_scheme', 'density') == 'gradient')
            self.auto_screenshot = tk.BooleanVar(value=json_config.get('auto_screenshot', False))
            self.auto_stl_export = tk.BooleanVar(value=json_config.get('auto_stl_export', False))
            self.container_color = tk.StringVar(value=json_config.get('wireframe_color', 'blue'))
            self.piece_opacity = tk.DoubleVar(value=json_config.get('piece_opacity', 1.0))
            self.background_color = tk.StringVar(value=json_config.get('background_color', 'white'))
            # Variables addicionals del JSON
            self.show_axes = tk.BooleanVar(value=json_config.get('show_axes', True))
            self.show_grid = tk.BooleanVar(value=json_config.get('show_grid', True))
            self.show_edges = tk.BooleanVar(value=json_config.get('show_edges', False))
            self.window_size = tk.StringVar(value=json_config.get('window_size', '1200x900'))
            
        elif self.persistent_vars:
            # FALLBACK: Usar variables del parent (persistents durant l'execució)
            self.show_wireframe = self.parent.viz_show_wireframe
            self.show_labels = self.parent.viz_show_labels
            self.use_gradient = self.parent.viz_use_gradient
            self.auto_screenshot = self.parent.viz_auto_screenshot
            self.auto_stl_export = self.parent.viz_auto_stl_export
            self.container_color = self.parent.viz_container_color
            self.piece_opacity = self.parent.viz_piece_opacity
            self.background_color = self.parent.viz_background_color
            # Variables addicionals persistents
            self.show_axes = self.parent.viz_show_axes
            self.show_grid = self.parent.viz_show_grid
            self.show_edges = self.parent.viz_show_edges
            self.window_size = self.parent.viz_window_size
            print(f"🔧 Carregant configuració persistent (fallback):")
            print(f"   Wireframe: {self.show_wireframe.get()}")
            print(f"   Etiquetes: {self.show_labels.get()}")
            print(f"   Gradient: {self.use_gradient.get()}")
            print(f"   Color caixa: {self.container_color.get()}")
            print(f"   Eixos: {self.show_axes.get()}")
            print(f"   Reixa: {self.show_grid.get()}")
        else:
            # ÚLTIM RECURS: Variables temporals per defecte
            self.show_wireframe = tk.BooleanVar(value=True)
            self.show_labels = tk.BooleanVar(value=True)
            self.use_gradient = tk.BooleanVar(value=False)
            self.auto_screenshot = tk.BooleanVar(value=False)
            self.auto_stl_export = tk.BooleanVar(value=False)
            self.container_color = tk.StringVar(value="black")
            self.piece_opacity = tk.DoubleVar(value=1.0)
            self.background_color = tk.StringVar(value="white")
            # Variables addicionals sempre temporals
            self.show_axes = tk.BooleanVar(value=True)
            self.show_grid = tk.BooleanVar(value=True)
            self.show_edges = tk.BooleanVar(value=False)
            self.window_size = tk.StringVar(value="1200x900")
            print("🔧 Usant configuració temporal per defecte (últim recurs)")
        
        # Variables sempre temporals
        self.auto_json_export = tk.BooleanVar(value=False)
        self.auto_csv_export = tk.BooleanVar(value=False)
        
        # Configurar color_scheme basant-se en use_gradient
        initial_scheme = "gradient" if self.use_gradient.get() else "solid"
        self.color_scheme = tk.StringVar(value=initial_scheme)
        
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
        
        # Seleccionar esquema de colors de peces
        color_scheme_frame = ttk.Frame(color_frame)
        color_scheme_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Crear variable temporal per esquema de colors
        self.color_scheme = tk.StringVar(value="solid" if not self.use_gradient.get() else "gradient")
        
        ttk.Label(color_scheme_frame, text="Esquema de peces:", font=('Arial', 9, 'bold')).pack(anchor=tk.W)
        ttk.Radiobutton(color_scheme_frame, text="🎨 Colors sòlids (recomanat)", 
                       variable=self.color_scheme, value="solid").pack(anchor=tk.W)
        ttk.Radiobutton(color_scheme_frame, text="🌈 Gradient per altura", 
                       variable=self.color_scheme, value="gradient").pack(anchor=tk.W)
        ttk.Radiobutton(color_scheme_frame, text="🎯 Color per densitat", 
                       variable=self.color_scheme, value="density").pack(anchor=tk.W)
        
        # Color de la caixa contenidora
        container_color_frame = ttk.Frame(color_frame)
        container_color_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(container_color_frame, text="Color de la caixa:", font=('Arial', 9, 'bold')).pack(anchor=tk.W)
        ttk.Radiobutton(container_color_frame, text="⬛ Negre", 
                       variable=self.container_color, value="black").pack(anchor=tk.W)
        ttk.Radiobutton(container_color_frame, text="⬜ Blanc", 
                       variable=self.container_color, value="white").pack(anchor=tk.W)
        ttk.Radiobutton(container_color_frame, text="🟢 Verd", 
                       variable=self.container_color, value="green").pack(anchor=tk.W)
        ttk.Radiobutton(container_color_frame, text="🔵 Blau", 
                       variable=self.container_color, value="blue").pack(anchor=tk.W)
        ttk.Radiobutton(container_color_frame, text="🔴 Vermell", 
                       variable=self.container_color, value="red").pack(anchor=tk.W)
        
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
        
        # Separador
        ttk.Separator(export_frame, orient='horizontal').pack(fill=tk.X, pady=(15, 10))
        
        # Exportació manual immediata
        manual_frame = ttk.LabelFrame(export_frame, text="Exportació Manual", padding="10")
        manual_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Crear frame per botons
        buttons_export_frame = ttk.Frame(manual_frame)
        buttons_export_frame.pack(fill=tk.X)
        
        ttk.Button(buttons_export_frame, text="📸 Exportar Imatge", 
                  command=self._export_screenshot).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_export_frame, text="📋 Exportar JSON", 
                  command=self._export_json).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_export_frame, text="📊 Exportar CSV", 
                  command=self._export_csv).pack(side=tk.LEFT, padx=(0, 5))
                  
        ttk.Label(manual_frame, text="✨ Utilitza la configuració de visualització actual", 
                 foreground='green', font=('Arial', 8)).pack(pady=(5, 0))
        
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
        # PRIORITAT: Guardar configuració al JSON MESTRA del parent
        if hasattr(self.parent, 'json_config') and self.parent.json_config is not None:
            self.parent.json_config.update({
                'show_wireframe': self.show_wireframe.get(),
                'show_labels': self.show_labels.get(),
                'color_scheme': 'gradient' if self.color_scheme.get() == 'gradient' else 'density',
                'auto_screenshot': self.auto_screenshot.get(),
                'auto_stl_export': self.auto_stl_export.get(),
                'wireframe_color': self.container_color.get(),
                'piece_opacity': self.piece_opacity.get(),
                'background_color': self.background_color.get(),
                'show_axes': self.show_axes.get(),
                'show_grid': self.show_grid.get(),
                'show_edges': self.show_edges.get(),
                'window_size': self.window_size.get()
            })
            
            # Guardar el JSON a disc
            if hasattr(self.parent, 'save_config_to_json'):
                self.parent.save_config_to_json()
                print("🔧 Configuració guardada al JSON MESTRA i a disc")
            else:
                print("🔧 Configuració guardada al JSON MESTRA (no es pot guardar a disc)")
        
        # FALLBACK: Guardar configuració en variables persistents si existeixen
        if self.persistent_vars:
            # Actualitzar les variables del parent per mantenir-les
            self.parent.viz_show_wireframe.set(self.show_wireframe.get())
            self.parent.viz_show_labels.set(self.show_labels.get())
            self.parent.viz_use_gradient.set(self.color_scheme.get() == 'gradient')
            self.parent.viz_auto_screenshot.set(self.auto_screenshot.get())
            self.parent.viz_auto_stl_export.set(self.auto_stl_export.get())
            self.parent.viz_container_color.set(self.container_color.get())
            self.parent.viz_piece_opacity.set(self.piece_opacity.get())
            self.parent.viz_background_color.set(self.background_color.get())
            # Guardar variables addicionals
            self.parent.viz_show_axes.set(self.show_axes.get())
            self.parent.viz_show_grid.set(self.show_grid.get())
            self.parent.viz_show_edges.set(self.show_edges.get())
            self.parent.viz_window_size.set(self.window_size.get())
            print("🔧 Configuració també guardada a variables persistents del parent")
        else:
            print("🔧 Configuració només al JSON (parent no té variables persistents)")
        
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
            'container_color': self.container_color.get(),
            'piece_opacity': self.piece_opacity.get(),
            
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

    def _export_screenshot(self):
        """Exporta screenshot amb configuració actual"""
        options = self._get_current_options()
        options['export_screenshot'] = True
        self.callback('export_manual', options)
        
    def _export_json(self):
        """Exporta JSON amb configuració actual"""
        options = self._get_current_options()
        options['export_json'] = True
        self.callback('export_manual', options)
        
    def _export_csv(self):
        """Exporta CSV amb configuració actual"""
        options = self._get_current_options()
        options['export_csv'] = True
        self.callback('export_manual', options)
    
    def _get_current_options(self):
        """Obté les opcions actuals del diàleg"""
        return {
            'show_wireframe': self.show_wireframe.get(),
            'show_labels': self.show_labels.get(),
            'show_axes': self.show_axes.get(),
            'show_grid': self.show_grid.get(),
            'show_edges': self.show_edges.get(),
            'color_scheme': self.color_scheme.get(),
            'use_gradient': self.color_scheme.get() == 'gradient',
            'container_color': self.container_color.get(),
            'piece_opacity': self.piece_opacity.get(),
            'background_color': self.background_color.get(),
            'window_size': self.window_size.get(),
        }


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
