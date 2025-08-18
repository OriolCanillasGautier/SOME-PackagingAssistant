#!/usr/bin/env python3
"""
PackAssist - Packaging Assistant Refactoritzat
Versió modular amb estructura millorada
"""

import sys
import os
from pathlib import Path

# Afegir el directori src al path per importar els mòduls
project_root = Path(__file__).parent
src_path = project_root / "actiu" / "src"
sys.path.insert(0, str(src_path))

# Imports principals
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import trimesh
from datetime import datetime

# Imports dels nostres mòduls
from packassist.core import MeshLoader, PackingOptimizer, ResultsExporter
from packassist.gui import Visualizer3D, ExportDialog, VisualizationDialog, ProgressDialog
from packassist.utils import save_results_file, generate_timestamp_filename

class PackAssistApp:
    """Aplicació principal de PackAssist refactoritzada"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PackAssist - Packaging Assistant v2.0")
        self.root.geometry("800x600")
        
        # Components
        self.mesh_loader = MeshLoader()
        self.visualizer = Visualizer3D()
        self.exporter = ResultsExporter()
        
        # Estat de l'aplicació
        self.current_mesh = None
        self.original_mesh = None
        self.stl_file_path = None
        self.optimization_results = None
        
        # Variables de la interfície
        self.container_length = tk.DoubleVar(value=200.0)
        self.container_width = tk.DoubleVar(value=200.0)
        self.container_height = tk.DoubleVar(value=200.0)
        self.target_pieces = tk.IntVar(value=50)
        self.optimization_method = tk.StringVar(value="intelligent")
        
        self._create_interface()
        self._setup_menu()
    
    def _create_interface(self):
        """Crea la interfície d'usuari"""
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurar grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Secció 1: Càrrega de fitxer
        file_frame = ttk.LabelFrame(main_frame, text="📁 Fitxer STL", padding="10")
        file_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.file_label = ttk.Label(file_frame, text="Cap fitxer seleccionat", 
                                   foreground="gray")
        self.file_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        ttk.Button(file_frame, text="🗂️ Carregar STL", 
                  command=self.load_file).grid(row=0, column=1, sticky=tk.E)
        
        file_frame.columnconfigure(0, weight=1)
        
        # Secció 2: Configuració del contenidor
        container_frame = ttk.LabelFrame(main_frame, text="📦 Contenidor", padding="10")
        container_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Grid del contenidor
        ttk.Label(container_frame, text="Longitud (mm):").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(container_frame, textvariable=self.container_length, 
                 width=10).grid(row=0, column=1, padx=(5, 15))
        
        ttk.Label(container_frame, text="Amplada (mm):").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(container_frame, textvariable=self.container_width, 
                 width=10).grid(row=0, column=3, padx=(5, 15))
        
        ttk.Label(container_frame, text="Altura (mm):").grid(row=0, column=4, sticky=tk.W)
        ttk.Entry(container_frame, textvariable=self.container_height, 
                 width=10).grid(row=0, column=5, padx=5)
        
        # Secció 3: Configuració d'optimització
        opt_frame = ttk.LabelFrame(main_frame, text="⚙️ Optimització", padding="10")
        opt_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(opt_frame, text="Peces objectiu:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(opt_frame, textvariable=self.target_pieces, 
                 width=10).grid(row=0, column=1, padx=(5, 15))
        
        ttk.Label(opt_frame, text="Mètode:").grid(row=0, column=2, sticky=tk.W)
        method_combo = ttk.Combobox(opt_frame, textvariable=self.optimization_method,
                                   values=["intelligent", "grid", "random"], 
                                   state="readonly", width=12)
        method_combo.grid(row=0, column=3, padx=5)
        
        # Secció 4: Accions
        actions_frame = ttk.LabelFrame(main_frame, text="🚀 Accions", padding="10")
        actions_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(actions_frame, text="🎯 Optimitzar", 
                  command=self.run_optimization).grid(row=0, column=0, padx=(0, 10))
        
        ttk.Button(actions_frame, text="🎮 Visualitzar 3D", 
                  command=self.visualize_3d_direct).grid(row=0, column=1, padx=(0, 10))
        
        ttk.Button(actions_frame, text="⚙️ Visualització Avançada", 
                  command=self.visualize_3d_options).grid(row=0, column=2, padx=(0, 10))
        
        ttk.Button(actions_frame, text="📤 Exportar", 
                  command=self.export_results).grid(row=0, column=3)
        
        # Secció 5: Resultats
        results_frame = ttk.LabelFrame(main_frame, text="📊 Resultats", padding="10")
        results_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Text area per resultats
        text_frame = ttk.Frame(results_frame)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.results_text = tk.Text(text_frame, height=15, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
    
    def _setup_menu(self):
        """Configura el menú de l'aplicació"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menú Fitxer
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Fitxer", menu=file_menu)
        file_menu.add_command(label="Carregar STL...", command=self.load_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exportar Resultats...", command=self.export_results)
        file_menu.add_separator()
        file_menu.add_command(label="Sortir", command=self.root.quit)
        
        # Menú Visualització
        viz_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Visualització", menu=viz_menu)
        viz_menu.add_command(label="Vista 3D Directa", command=self.visualize_3d_direct)
        viz_menu.add_command(label="Opcions Avançades", command=self.visualize_3d_options)
        
        # Menú Ajuda
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ajuda", menu=help_menu)
        help_menu.add_command(label="Sobre PackAssist", command=self.show_about)
    
    def load_file(self):
        """Carrega un fitxer STL"""
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
            # Mostrar progrés
            progress = ProgressDialog(self.root, "Carregant fitxer...")
            progress.show()
            progress.update(20, "Llegint fitxer...")
            
            # Carregar la malla
            self.original_mesh = self.mesh_loader.load_mesh(filepath)
            progress.update(60, "Processant malla...")
            
            # Preparar per optimització
            self.current_mesh, simplified = self.mesh_loader.prepare_for_optimization(self.original_mesh)
            progress.update(80, "Finalitzant...")
            
            # Actualitzar interfície
            self.stl_file_path = filepath
            filename = os.path.basename(filepath)
            self.file_label.config(text=f"✅ {filename}", foreground="green")
            
            # Mostrar informació
            mesh_info = self.mesh_loader.get_mesh_info(self.current_mesh)
            info_text = f"📁 Fitxer carregat: {filename}\n"
            info_text += f"🔺 Vèrtexs: {mesh_info['vertices_count']:,}\n"
            info_text += f"📐 Cares: {mesh_info['faces_count']:,}\n"
            info_text += f"📏 Dimensions: {mesh_info['dimensions'][0]:.1f} x {mesh_info['dimensions'][1]:.1f} x {mesh_info['dimensions'][2]:.1f} mm\n"
            info_text += f"📦 Volum: {mesh_info['volume']:.1f} mm³\n"
            info_text += f"💧 Estanc: {'Sí' if mesh_info['is_watertight'] else 'No'}\n\n"
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, info_text)
            
            progress.update(100, "Completat!")
            progress.close()
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            messagebox.showerror("Error", f"Error carregant el fitxer:\n{e}")
    
    def run_optimization(self):
        """Executa l'optimització"""
        if not self.current_mesh:
            messagebox.showwarning("Avís", "Primer carrega un fitxer STL")
            return
        
        try:
            # Crear optimitzador
            container_dims = (
                self.container_length.get(),
                self.container_width.get(), 
                self.container_height.get()
            )
            
            optimizer = PackingOptimizer(container_dims)
            
            # Mostrar progrés
            progress = ProgressDialog(self.root, "Optimitzant packaging...")
            progress.show()
            progress.update(10, "Iniciant optimització...")
            
            # Executar optimització
            progress.update(30, f"Aplicant mètode {self.optimization_method.get()}...")
            
            results = optimizer.optimize(
                self.current_mesh,
                self.target_pieces.get(),
                self.optimization_method.get()
            )
            
            progress.update(80, "Processant resultats...")
            
            if results['success']:
                self.optimization_results = results
                
                # Mostrar resultats
                self._display_results(results)
                progress.update(100, "Optimització completada!")
                
                # Guardar resultats automàticament
                self._save_results_to_file(results)
                
            else:
                messagebox.showerror("Error", f"Error en l'optimització:\n{results.get('error', 'Error desconegut')}")
            
            progress.close()
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            messagebox.showerror("Error", f"Error durant l'optimització:\n{e}")
    
    def _display_results(self, results: dict):
        """Mostra els resultats a la interfície"""
        text = f"🎯 OPTIMITZACIÓ COMPLETADA\n"
        text += f"{'='*50}\n\n"
        text += f"📊 Resultats:\n"
        text += f"   • Peces col·locades: {results['pieces_count']}\n"
        text += f"   • Eficiència: {results['efficiency']:.2f}%\n"
        text += f"   • Mètode: {results['method']}\n"
        text += f"   • Temps d'execució: {results['execution_time']:.2f} segons\n\n"
        
        text += f"📦 Contenidor:\n"
        box_dims = results['box_dims']
        text += f"   • Dimensions: {box_dims['length']:.1f} x {box_dims['width']:.1f} x {box_dims['height']:.1f} mm\n"
        text += f"   • Volum total: {box_dims['volume']:.1f} mm³\n\n"
        
        text += f"🔧 Objecte:\n"
        obj_dims = results['obj_dims']
        text += f"   • Dimensions: {obj_dims['length']:.1f} x {obj_dims['width']:.1f} x {obj_dims['height']:.1f} mm\n"
        text += f"   • Volum unitari: {obj_dims['volume']:.1f} mm³\n\n"
        
        text += f"✅ Optimització finalitzada correctament!\n"
        text += f"Usa 'Visualitzar 3D' per veure els resultats o 'Exportar' per guardar-los.\n"
        
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, text)
    
    def _save_results_to_file(self, results: dict):
        """Guarda els resultats automàticament"""
        try:
            filename = generate_timestamp_filename("packassist_results", "txt")
            
            content = f"PackAssist - Resultats d'Optimització\n"
            content += f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            content += f"Fitxer: {os.path.basename(self.stl_file_path) if self.stl_file_path else 'Desconegut'}\n"
            content += f"Mètode: {results['method']}\n"
            content += f"Peces col·locades: {results['pieces_count']}\n"
            content += f"Eficiència: {results['efficiency']:.2f}%\n"
            content += f"Temps d'execució: {results['execution_time']:.2f} segons\n\n"
            
            # Afegir posicions
            content += "Posicions de les peces:\n"
            for i, (pos, rot) in enumerate(zip(results['positions'], results['rotations'])):
                content += f"Peça {i+1}: Pos({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}) "
                content += f"Rot({rot[0]:.0f}°, {rot[1]:.0f}°, {rot[2]:.0f}°)\n"
            
            save_results_file(content, filename)
            print(f"💾 Resultats guardats: {filename}")
            
        except Exception as e:
            print(f"Error guardant resultats: {e}")
    
    def visualize_3d_direct(self):
        """Visualització 3D directa amb defaults intel·ligents"""
        if not self.optimization_results:
            messagebox.showwarning("Avís", "Primer executa l'optimització")
            return
        
        self.visualizer.show_direct_3d(self.optimization_results, self.current_mesh)
    
    def visualize_3d_options(self):
        """Visualització 3D amb diàleg d'opcions"""
        if not self.optimization_results:
            messagebox.showwarning("Avís", "Primer executa l'optimització")
            return
        
        def callback(action, options):
            if action == 'visualize':
                self.visualizer.show_3d_with_options(
                    self.optimization_results, 
                    self.current_mesh,
                    **options
                )
            elif action == 'export':
                self.export_results()
        
        dialog = VisualizationDialog(self.root, self.optimization_results, callback)
        dialog.show()
    
    def export_results(self):
        """Exporta els resultats"""
        if not self.optimization_results:
            messagebox.showwarning("Avís", "Primer executa l'optimització")
            return
        
        def callback(options):
            self._perform_export(options)
        
        dialog = ExportDialog(self.root, self.optimization_results, callback)
        dialog.show()
    
    def _perform_export(self, options: dict):
        """Realitza l'exportació amb les opcions seleccionades"""
        try:
            # Seleccionar directori
            export_dir = filedialog.askdirectory(title="Directori d'exportació")
            if not export_dir:
                return
            
            # Generar nom base
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"packassist_export_{timestamp}"
            
            exported_files = []
            
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
                    self.current_mesh,
                    self.optimization_results['positions'],
                    self.optimization_results['rotations']
                ):
                    exported_files.append(filepath)
            
            if options.get('image'):
                filepath = os.path.join(export_dir, f"{base_name}_3d_view.png")
                if self.exporter.export_3d_image(
                    filepath,
                    self.current_mesh,
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
    
    def show_about(self):
        """Mostra informació sobre l'aplicació"""
        about_text = """PackAssist v2.0 - Packaging Assistant

Aplicació per optimitzar l'empaquetatge de peces 3D.

Característiques:
• Càrrega de fitxers STL/STP
• Algoritmes d'optimització intel·ligents
• Visualització 3D interactiva
• Exportació múltiple formats
• Arquitectura modular millorada

Desenvolupat amb Python, Tkinter, Trimesh i PyVista.
"""
        messagebox.showinfo("Sobre PackAssist", about_text)
    
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
