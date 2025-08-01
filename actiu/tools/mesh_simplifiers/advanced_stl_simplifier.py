"""
PackAssist - Simplificador STL Avançat amb GUI
Combina la potència de processament dels múltiples algoritmes amb una interfície gràfica completa
"""

import os
import sys
import time
import struct
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
from pathlib import Path
import threading

class AdvancedSTLSimplifier:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PackAssist - Simplificador STL Avançat")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Variables
        self.selected_file = tk.StringVar()
        self.target_vertices = tk.IntVar(value=1000)
        self.selected_method = tk.StringVar()
        self.current_vertices = None
        self.current_faces = None
        self.simplified_vertices = None
        self.simplified_faces = None
        
        # Estat del processament
        self.is_processing = False
        
        # Comprovar mètodes disponibles
        self.available_methods = []
        self.check_dependencies()
        
        if self.available_methods:
            self.selected_method.set(self.available_methods[0][0])
        
        # Configurar GUI
        self.setup_gui()
        
        # Debug info
        print("🚀 Simplificador STL Avançat inicialitzat")
        print(f"📊 Mètodes disponibles: {[name for _, name in self.available_methods]}")
    
    def check_dependencies(self):
        """Comprova quines biblioteques estan disponibles"""
        print("🔍 Comprovant biblioteques disponibles...")
        
        # PyMeshLab (més ràpid i potent)
        try:
            import pymeshlab
            self.available_methods.append(('pymeshlab', 'PyMeshLab (ULTRA RÀPID)'))
            print("✅ PyMeshLab disponible")
        except ImportError:
            print("❌ PyMeshLab no disponible")
        
        # PyVista
        try:
            import pyvista as pv
            self.available_methods.append(('pyvista', 'PyVista'))
            print("✅ PyVista disponible")
        except ImportError:
            print("❌ PyVista no disponible")
        
        # Trimesh
        try:
            import trimesh
            self.available_methods.append(('trimesh', 'Trimesh'))
            print("✅ Trimesh disponible")
        except ImportError:
            print("❌ Trimesh no disponible")
        
        # pyfqmr
        try:
            import pyfqmr
            self.available_methods.append(('pyfqmr', 'pyfqmr (Fast Quadric)'))
            print("✅ pyfqmr disponible")
        except ImportError:
            print("❌ pyfqmr no disponible")
        
        if not self.available_methods:
            print("❌ Cap biblioteca de simplificació disponible!")
            messagebox.showerror(
                "Error Dependencies",
                "Cap biblioteca de simplificació disponible!\n\n"
                "Instal·la almenys una:\n"
                "• pip install pymeshlab (RECOMANAT)\n"
                "• pip install pyvista\n"
                "• pip install trimesh\n"
                "• pip install pyfqmr"
            )
    
    def setup_gui(self):
        """Configura la interfície gràfica"""
        # Crear notebook amb pestanyes
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Pestanya 1: Simplificació
        simplify_frame = ttk.Frame(notebook)
        notebook.add(simplify_frame, text="🔧 Simplificació STL")
        self.setup_simplify_tab(simplify_frame)
        
        # Pestanya 2: Visualització
        viz_frame = ttk.Frame(notebook)
        notebook.add(viz_frame, text="👁️ Visualització 3D")
        self.setup_visualization_tab(viz_frame)
        
        # Pestanya 3: Configuració
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="⚙️ Configuració")
        self.setup_config_tab(config_frame)
    
    def setup_simplify_tab(self, parent):
        """Configura la pestanya de simplificació"""
        # Títol
        title_label = ttk.Label(parent, text="Simplificador STL Avançat", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=20)
        
        # Frame principal
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Secció 1: Selecció de fitxer
        file_frame = ttk.LabelFrame(main_frame, text="1. Seleccionar fitxer STL", padding=15)
        file_frame.pack(fill='x', pady=(0, 15))
        
        file_button_frame = ttk.Frame(file_frame)
        file_button_frame.pack(fill='x')
        
        ttk.Button(file_button_frame, text="📁 Seleccionar STL", 
                  command=self.select_file, width=20).pack(side='left')
        
        self.file_info_label = ttk.Label(file_button_frame, text="Cap fitxer seleccionat", 
                                        foreground='gray')
        self.file_info_label.pack(side='left', padx=(15, 0))
        
        # Informació detallada del fitxer
        self.file_details_label = ttk.Label(file_frame, text="", foreground='blue')
        self.file_details_label.pack(pady=(10, 0))
        
        # Secció 2: Configuració de simplificació
        config_frame = ttk.LabelFrame(main_frame, text="2. Configuració de simplificació", padding=15)
        config_frame.pack(fill='x', pady=(0, 15))
        
        # Mètode de simplificació
        method_frame = ttk.Frame(config_frame)
        method_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(method_frame, text="Algoritme:").pack(side='left')
        
        if self.available_methods:
            method_combo = ttk.Combobox(method_frame, textvariable=self.selected_method,
                                       values=[method for method, _ in self.available_methods],
                                       state="readonly", width=20)
            method_combo.pack(side='left', padx=10)
            method_combo.bind('<<ComboboxSelected>>', self.on_method_change)
        
        self.method_info_label = ttk.Label(method_frame, text="", foreground='blue')
        self.method_info_label.pack(side='left', padx=(15, 0))
        
        # Nombre objectiu de vèrtexs
        target_frame = ttk.Frame(config_frame)
        target_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Label(target_frame, text="Vèrtexs objectiu:").pack(side='left')
        target_spinbox = ttk.Spinbox(target_frame, from_=50, to=100000, 
                                    textvariable=self.target_vertices, width=10)
        target_spinbox.pack(side='left', padx=10)
        
        # Botons d'accions ràpides
        quick_frame = ttk.Frame(config_frame)
        quick_frame.pack(fill='x', pady=(15, 0))
        
        ttk.Label(quick_frame, text="Accions ràpides:").pack(side='left')
        
        ttk.Button(quick_frame, text="50%", command=lambda: self.set_quick_target(0.5),
                  width=8).pack(side='left', padx=5)
        ttk.Button(quick_frame, text="25%", command=lambda: self.set_quick_target(0.25),
                  width=8).pack(side='left', padx=5)
        ttk.Button(quick_frame, text="10%", command=lambda: self.set_quick_target(0.10),
                  width=8).pack(side='left', padx=5)
        
        # Secció 3: Processament
        process_frame = ttk.LabelFrame(main_frame, text="3. Processament", padding=15)
        process_frame.pack(fill='x', pady=(0, 15))
        
        # Botó principal
        self.process_button = ttk.Button(process_frame, text="🚀 SIMPLIFICAR",
                                        command=self.start_simplification,
                                        style='Accent.TButton')
        self.process_button.pack(pady=10)
        
        # Barra de progrés
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(process_frame, variable=self.progress_var,
                                           maximum=100, mode='indeterminate')
        self.progress_bar.pack(fill='x', pady=(10, 5))
        self.progress_bar.pack_forget()
        
        # Estat del processament
        self.status_label = ttk.Label(process_frame, text="Llest per començar", 
                                     foreground='green')
        self.status_label.pack(pady=5)
        
        # Secció 4: Resultats
        results_frame = ttk.LabelFrame(main_frame, text="4. Resultats", padding=15)
        results_frame.pack(fill='x', pady=(0, 15))
        
        self.results_text = tk.Text(results_frame, height=8, wrap=tk.WORD, 
                                   state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        
        self.results_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Botons d'exportació
        export_frame = ttk.Frame(main_frame)
        export_frame.pack(fill='x', pady=15)
        
        self.save_button = ttk.Button(export_frame, text="💾 Guardar STL simplificat",
                                     command=self.save_simplified, state='disabled')
        self.save_button.pack(side='left', padx=5)
        
        self.visualize_button = ttk.Button(export_frame, text="👁️ Visualitzar",
                                          command=self.switch_to_visualization, state='disabled')
        self.visualize_button.pack(side='left', padx=5)
    
    def setup_visualization_tab(self, parent):
        """Configura la pestanya de visualització 3D"""
        # Títol
        title_label = ttk.Label(parent, text="Visualització 3D", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=20)
        
        # Frame principal
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Controls de visualització
        controls_frame = ttk.LabelFrame(main_frame, text="Controls de visualització", padding=15)
        controls_frame.pack(fill='x', pady=(0, 15))
        
        controls_grid = ttk.Frame(controls_frame)
        controls_grid.pack()
        
        # Botó per visualització original
        self.viz_original_button = ttk.Button(controls_grid, text="🔍 Original",
                                             command=self.visualize_original, state='disabled')
        self.viz_original_button.grid(row=0, column=0, padx=5, pady=5)
        
        # Botó per visualització simplificada
        self.viz_simplified_button = ttk.Button(controls_grid, text="🔍 Simplificat",
                                               command=self.visualize_simplified, state='disabled')
        self.viz_simplified_button.grid(row=0, column=1, padx=5, pady=5)
        
        # Botó per comparació
        self.viz_compare_button = ttk.Button(controls_grid, text="⚖️ Comparar",
                                            command=self.visualize_compare, state='disabled')
        self.viz_compare_button.grid(row=0, column=2, padx=5, pady=5)
        
        # Informació de visualització
        self.viz_info_label = ttk.Label(main_frame, 
                                       text="Carrega i simplifica un STL per veure la visualització 3D.",
                                       foreground='gray')
        self.viz_info_label.pack(pady=20)
        
        # Frame per matplotlib (es crearà dinàmicament)
        self.viz_canvas_frame = ttk.Frame(main_frame)
        self.viz_canvas_frame.pack(fill='both', expand=True)
    
    def setup_config_tab(self, parent):
        """Configura la pestanya de configuració"""
        # Títol
        title_label = ttk.Label(parent, text="Configuració", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=20)
        
        # Frame principal
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Informació dels mètodes
        methods_frame = ttk.LabelFrame(main_frame, text="Mètodes de simplificació disponibles", padding=15)
        methods_frame.pack(fill='x', pady=(0, 15))
        
        methods_text = tk.Text(methods_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        methods_scrollbar = ttk.Scrollbar(methods_frame, orient="vertical", command=methods_text.yview)
        methods_text.configure(yscrollcommand=methods_scrollbar.set)
        
        # Omplir informació dels mètodes
        methods_text.config(state=tk.NORMAL)
        methods_info = self.get_methods_info()
        methods_text.insert(tk.END, methods_info)
        methods_text.config(state=tk.DISABLED)
        
        methods_text.pack(side='left', fill='both', expand=True)
        methods_scrollbar.pack(side='right', fill='y')
        
        # Configuració avançada
        advanced_frame = ttk.LabelFrame(main_frame, text="Configuració avançada", padding=15)
        advanced_frame.pack(fill='x', pady=(15, 0))
        
        # Checkbox per mantenir fronteres
        self.preserve_borders = tk.BooleanVar(value=True)
        ttk.Checkbutton(advanced_frame, text="Preservar fronteres de la malla",
                       variable=self.preserve_borders).pack(anchor='w', pady=5)
        
        # Checkbox per mantenir textures
        self.preserve_textures = tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced_frame, text="Preservar informació de textures",
                       variable=self.preserve_textures).pack(anchor='w', pady=5)
        
        # Nivell d'agressivitat
        aggressiveness_frame = ttk.Frame(advanced_frame)
        aggressiveness_frame.pack(fill='x', pady=10)
        
        ttk.Label(aggressiveness_frame, text="Agressivitat (0-10):").pack(side='left')
        
        self.aggressiveness = tk.IntVar(value=7)
        aggressiveness_scale = ttk.Scale(aggressiveness_frame, from_=0, to=10,
                                        variable=self.aggressiveness, orient='horizontal')
        aggressiveness_scale.pack(side='left', fill='x', expand=True, padx=10)
        
        self.aggressiveness_label = ttk.Label(aggressiveness_frame, text="7")
        self.aggressiveness_label.pack(side='left')
        
        aggressiveness_scale.configure(command=self.update_aggressiveness_label)
    
    def get_methods_info(self):
        """Retorna informació detallada dels mètodes"""
        info = "📊 MÈTODES DE SIMPLIFICACIÓ DISPONIBLES:\n\n"
        
        for method, name in self.available_methods:
            info += f"🔹 {name}\n"
            
            if method == 'pymeshlab':
                info += "   • Ultra ràpid i eficient\n"
                info += "   • Múltiples algoritmes integrats\n"
                info += "   • Millor preservació de la geometria\n"
                info += "   • RECOMANAT per models complexos\n"
            elif method == 'pyvista':
                info += "   • Bon equilibri velocitat/qualitat\n"
                info += "   • Funciona bé amb malles regulars\n"
                info += "   • Bon suport per visualització\n"
            elif method == 'trimesh':
                info += "   • Lleuger i ràpid\n"
                info += "   • Ideal per operacions batch\n"
                info += "   • Bona integració amb altres eines\n"
            elif method == 'pyfqmr':
                info += "   • Algoritme quadric de qualitat\n"
                info += "   • Preserva bé les característiques\n"
                info += "   • Configurable per diferents necessitats\n"
            
            info += "\n"
        
        if not self.available_methods:
            info += "❌ Cap mètode disponible!\n\n"
            info += "Instal·la almenys una biblioteca:\n"
            info += "• pip install pymeshlab (RECOMANAT)\n"
            info += "• pip install pyvista\n"
            info += "• pip install trimesh\n"
            info += "• pip install pyfqmr\n"
        
        return info
    
    def update_aggressiveness_label(self, value):
        """Actualitza l'etiqueta d'agressivitat"""
        self.aggressiveness_label.config(text=str(int(float(value))))
    
    def on_method_change(self, event=None):
        """Quan canvia el mètode seleccionat"""
        method = self.selected_method.get()
        method_name = next((name for m, name in self.available_methods if m == method), "")
        self.method_info_label.config(text=f"Actiu: {method_name}")
        print(f"🔄 Mètode canviat a: {method_name}")
    
    def select_file(self):
        """Selecciona un fitxer STL"""
        file_path = filedialog.askopenfilename(
            title="Selecciona fitxer STL",
            filetypes=[
                ("Fitxers STL", "*.stl *.STL"),
                ("Tots els fitxers", "*.*")
            ]
        )
        
        if file_path:
            self.selected_file.set(file_path)
            self.load_file_info(file_path)
            print(f"📁 Fitxer seleccionat: {os.path.basename(file_path)}")
    
    def load_file_info(self, file_path):
        """Carrega i mostra informació del fitxer"""
        try:
            # Informació bàsica del fitxer
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            filename = os.path.basename(file_path)
            
            self.file_info_label.config(
                text=f"{filename} ({size_mb:.1f} MB)",
                foreground='black'
            )
            
            # Carregar malla per obtenir estadístiques
            self.status_label.config(text="Analitzant fitxer STL...", foreground='blue')
            self.root.update()
            
            vertices, faces = self.load_stl(file_path)
            
            if vertices is not None and faces is not None:
                self.current_vertices = vertices
                self.current_faces = faces
                
                # Mostrar estadístiques detallades
                details = f"📊 Estadístiques: {len(vertices):,} vèrtexs, {len(faces):,} triangles"
                
                # Calcular volum aproximat
                if len(vertices) > 0:
                    bbox = [
                        (np.min(vertices[:, 0]), np.max(vertices[:, 0])),
                        (np.min(vertices[:, 1]), np.max(vertices[:, 1])),
                        (np.min(vertices[:, 2]), np.max(vertices[:, 2]))
                    ]
                    volume = (bbox[0][1] - bbox[0][0]) * (bbox[1][1] - bbox[1][0]) * (bbox[2][1] - bbox[2][0])
                    details += f"\n📦 Volum aproximat: {volume:.2f} mm³"
                
                self.file_details_label.config(text=details)
                
                # Suggerir valor objectiu
                suggested_target = max(100, len(vertices) // 4)
                self.target_vertices.set(suggested_target)
                
                # Activar botons
                self.viz_original_button.config(state='normal')
                
                self.status_label.config(text="Fitxer carregat correctament", foreground='green')
                
                print(f"✅ STL carregat: {len(vertices)} vèrtexs, {len(faces)} triangles")
            else:
                self.file_details_label.config(text="❌ Error llegint el fitxer STL")
                self.status_label.config(text="Error carregant fitxer", foreground='red')
                
        except Exception as e:
            self.file_details_label.config(text=f"❌ Error: {str(e)}")
            self.status_label.config(text="Error carregant fitxer", foreground='red')
            print(f"❌ Error carregant fitxer: {e}")
    
    def set_quick_target(self, percentage):
        """Estableix un objectiu ràpid basat en percentatge"""
        if self.current_vertices is not None:
            target = max(50, int(len(self.current_vertices) * percentage))
            self.target_vertices.set(target)
            print(f"🎯 Objectiu establert a {percentage*100}%: {target} vèrtexs")
    
    def start_simplification(self):
        """Inicia el procés de simplificació en un thread separat"""
        if not self.selected_file.get():
            messagebox.showerror("Error", "Selecciona un fitxer STL primer!")
            return
        
        if self.current_vertices is None:
            messagebox.showerror("Error", "Carrega un fitxer vàlid primer!")
            return
        
        if not self.available_methods:
            messagebox.showerror("Error", "No hi ha mètodes de simplificació disponibles!")
            return
        
        target = self.target_vertices.get()
        if target >= len(self.current_vertices):
            messagebox.showwarning("Advertència", 
                                 f"El nombre objectiu ({target}) ha de ser menor que l'original ({len(self.current_vertices)})!")
            return
        
        # Iniciar processament en thread separat
        self.is_processing = True
        self.process_button.config(state='disabled')
        self.progress_bar.pack(fill='x', pady=(10, 5))
        self.progress_bar.start()
        
        thread = threading.Thread(target=self.run_simplification)
        thread.daemon = True
        thread.start()
    
    def run_simplification(self):
        """Executa la simplificació (corre en thread separat)"""
        try:
            start_time = time.time()
            
            # Actualitzar status
            self.root.after(0, lambda: self.status_label.config(
                text="Simplificant malla...", foreground='blue'))
            
            # Aplicar simplificació
            method = self.selected_method.get()
            target = self.target_vertices.get()
            
            print(f"🚀 Iniciant simplificació amb {method}")
            print(f"🎯 Objectiu: {target} vèrtexs (des de {len(self.current_vertices)})")
            
            if method == 'pymeshlab':
                simplified_vertices, simplified_faces = self.simplify_pymeshlab(
                    self.current_vertices, self.current_faces, target)
            elif method == 'pyvista':
                simplified_vertices, simplified_faces = self.simplify_pyvista(
                    self.current_vertices, self.current_faces, target)
            elif method == 'trimesh':
                simplified_vertices, simplified_faces = self.simplify_trimesh(
                    self.current_vertices, self.current_faces, target)
            elif method == 'pyfqmr':
                simplified_vertices, simplified_faces = self.simplify_pyfqmr(
                    self.current_vertices, self.current_faces, target)
            else:
                raise Exception(f"Mètode desconegut: {method}")
            
            elapsed = time.time() - start_time
            
            if simplified_vertices is not None and simplified_faces is not None:
                self.simplified_vertices = simplified_vertices
                self.simplified_faces = simplified_faces
                
                # Calcular estadístiques
                original_count = len(self.current_vertices)
                final_count = len(simplified_vertices)
                reduction_percent = ((original_count - final_count) / original_count) * 100
                
                # Actualitzar GUI des del thread principal
                self.root.after(0, self.on_simplification_success, 
                               original_count, final_count, reduction_percent, elapsed)
                
                print(f"✅ Simplificació completada en {elapsed:.2f}s")
                print(f"📊 {original_count:,} → {final_count:,} vèrtexs ({reduction_percent:.1f}% reducció)")
            else:
                self.root.after(0, self.on_simplification_error, "La simplificació ha fallat")
                
        except Exception as e:
            self.root.after(0, self.on_simplification_error, str(e))
            print(f"❌ Error en simplificació: {e}")
    
    def on_simplification_success(self, original_count, final_count, reduction_percent, elapsed):
        """Callback quan la simplificació és exitosa"""
        # Parar barra de progrés
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        
        # Actualitzar status
        self.status_label.config(text="Simplificació completada!", foreground='green')
        
        # Mostrar resultats
        results_text = f"""✅ SIMPLIFICACIÓ COMPLETADA!

📊 Estadístiques:
• Original: {original_count:,} vèrtexs
• Simplificat: {final_count:,} vèrtexs  
• Reducció: {reduction_percent:.1f}%
• Temps: {elapsed:.2f} segons

🎯 Mètode utilitzat: {next(name for method, name in self.available_methods if method == self.selected_method.get())}

💡 Ara pots visualitzar el resultat o guardar l'STL simplificat.
"""
        
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(1.0, results_text)
        self.results_text.config(state=tk.DISABLED)
        
        # Activar botons
        self.save_button.config(state='normal')
        self.visualize_button.config(state='normal')
        self.viz_simplified_button.config(state='normal')
        self.viz_compare_button.config(state='normal')
        
        # Reactivar botó de processament
        self.process_button.config(state='normal')
        self.is_processing = False
    
    def on_simplification_error(self, error_message):
        """Callback quan hi ha error en la simplificació"""
        # Parar barra de progrés
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        
        # Actualitzar status
        self.status_label.config(text="Error en la simplificació", foreground='red')
        
        # Mostrar error
        error_text = f"""❌ ERROR EN LA SIMPLIFICACIÓ

{error_message}

💡 Suggeriments:
• Prova amb un altre mètode de simplificació
• Augmenta el nombre objectiu de vèrtexs
• Verifica que el fitxer STL sigui vàlid
"""
        
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(1.0, error_text)
        self.results_text.config(state=tk.DISABLED)
        
        # Reactivar botó de processament
        self.process_button.config(state='normal')
        self.is_processing = False
        
        messagebox.showerror("Error", f"Error en la simplificació:\n{error_message}")
    
    def switch_to_visualization(self):
        """Canvia a la pestanya de visualització"""
        # Trobar la pestanya de visualització i activar-la
        for i in range(3):  # 3 pestanyes
            tab_text = self.root.nametowidget(f".!notebook.!frame{i+1 if i > 0 else ''}")
            # Intentar accedir a la pestanya i activar-la
            try:
                notebook = self.root.children['!notebook']
                notebook.select(1)  # Pestanya 1 (0-indexed) és la visualització
                break
            except:
                pass
    
    # Mètodes de simplificació (copiats del ultra_fast_mesh_simplifier.py)
    def simplify_pymeshlab(self, vertices, faces, target_vertices):
        """Simplificació amb PyMeshLab"""
        try:
            import pymeshlab
            
            print("🔄 Aplicant simplificació amb PyMeshLab...")
            
            ms = pymeshlab.MeshSet()
            mesh = pymeshlab.Mesh(vertices, faces)
            ms.add_mesh(mesh)
            
            # Múltiples estratègies de simplificació
            original_vertices = len(vertices)
            target_ratio = target_vertices / original_vertices
            
            success = False
            
            # Estratègia 1: Clustering
            try:
                ms.apply_filter('meshing_decimation_clustering', 
                               threshold=pymeshlab.Percentage(100 - target_ratio * 100))
                success = True
                print("✅ Clustering aplicat")
            except:
                pass
            
            # Estratègia 2: Quadric edge collapse
            if not success:
                try:
                    ms.apply_filter('meshing_decimation_quadric_edge_collapse', 
                                   targetfacenum=int(len(faces) * target_ratio))
                    success = True
                    print("✅ Quadric edge collapse aplicat")
                except:
                    pass
            
            if not success:
                return None, None
            
            simplified_mesh = ms.current_mesh()
            new_vertices = simplified_mesh.vertex_matrix()
            new_faces = simplified_mesh.face_matrix()
            
            return new_vertices, new_faces
            
        except Exception as e:
            print(f"❌ Error amb PyMeshLab: {e}")
            return None, None
    
    def simplify_pyvista(self, vertices, faces, target_vertices):
        """Simplificació amb PyVista"""
        try:
            import pyvista as pv
            
            print("🔄 Aplicant simplificació amb PyVista...")
            
            mesh = pv.PolyData(vertices, np.column_stack([np.full(len(faces), 3), faces]))
            reduction = 1.0 - (target_vertices / len(vertices))
            simplified = mesh.decimate(reduction)
            
            new_vertices = simplified.points
            new_faces = simplified.faces.reshape(-1, 4)[:, 1:4]
            
            return new_vertices, new_faces
            
        except Exception as e:
            print(f"❌ Error amb PyVista: {e}")
            return None, None
    
    def simplify_trimesh(self, vertices, faces, target_vertices):
        """Simplificació amb Trimesh"""
        try:
            import trimesh
            
            print("🔄 Aplicant simplificació amb Trimesh...")
            
            mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
            simplified = mesh.simplify_quadric_decimation(target_vertices)
            
            return simplified.vertices, simplified.faces
            
        except Exception as e:
            print(f"❌ Error amb Trimesh: {e}")
            return None, None
    
    def simplify_pyfqmr(self, vertices, faces, target_vertices):
        """Simplificació amb pyfqmr"""
        try:
            import pyfqmr
            
            print("🔄 Aplicant simplificació amb pyfqmr...")
            
            mesh_simplifier = pyfqmr.Simplify()
            mesh_simplifier.setMesh(vertices, faces)
            mesh_simplifier.simplify_mesh(
                target_count=target_vertices, 
                aggressiveness=self.aggressiveness.get(),
                preserve_border=self.preserve_borders.get()
            )
            
            new_vertices, new_faces, _ = mesh_simplifier.getMesh()
            
            return new_vertices, new_faces
            
        except Exception as e:
            print(f"❌ Error amb pyfqmr: {e}")
            return None, None
    
    def load_stl(self, file_path):
        """Carrega un fitxer STL"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(80)
                is_binary = not header.startswith(b'solid ')
            
            if is_binary:
                return self._load_binary_stl(file_path)
            else:
                return self._load_ascii_stl(file_path)
                
        except Exception as e:
            print(f"❌ Error carregant STL: {e}")
            return None, None
    
    def _load_binary_stl(self, file_path):
        """Carrega STL binari"""
        try:
            with open(file_path, 'rb') as f:
                f.read(80)  # Header
                num_triangles = struct.unpack('<I', f.read(4))[0]
                
                vertices = []
                faces = []
                vertex_map = {}
                
                for i in range(num_triangles):
                    f.read(12)  # Skip normal
                    
                    face_vertices = []
                    for j in range(3):
                        x, y, z = struct.unpack('<fff', f.read(12))
                        vertex = (round(x, 6), round(y, 6), round(z, 6))
                        
                        if vertex not in vertex_map:
                            vertex_map[vertex] = len(vertices)
                            vertices.append(vertex)
                        
                        face_vertices.append(vertex_map[vertex])
                    
                    faces.append(face_vertices)
                    f.read(2)  # Skip attribute
                
                return np.array(vertices), np.array(faces)
                
        except Exception as e:
            print(f"❌ Error llegint STL binari: {e}")
            return None, None
    
    def _load_ascii_stl(self, file_path):
        """Carrega STL ASCII"""
        try:
            vertices = []
            faces = []
            vertex_map = {}
            
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                if line.startswith('facet normal'):
                    face_vertices = []
                    i += 1  # Skip outer loop
                    
                    for _ in range(3):
                        i += 1
                        if i < len(lines):
                            vertex_line = lines[i].strip()
                            if vertex_line.startswith('vertex'):
                                parts = vertex_line.split()
                                if len(parts) >= 4:
                                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                                    vertex = (round(x, 6), round(y, 6), round(z, 6))
                                    
                                    if vertex not in vertex_map:
                                        vertex_map[vertex] = len(vertices)
                                        vertices.append(vertex)
                                    
                                    face_vertices.append(vertex_map[vertex])
                    
                    if len(face_vertices) == 3:
                        faces.append(face_vertices)
                
                i += 1
            
            return np.array(vertices), np.array(faces)
            
        except Exception as e:
            print(f"❌ Error llegint STL ASCII: {e}")
            return None, None
    
    def save_simplified(self):
        """Guarda l'STL simplificat"""
        if self.simplified_vertices is None or self.simplified_faces is None:
            messagebox.showerror("Error", "No hi ha malla simplificada per guardar!")
            return
        
        # Suggerir nom de fitxer
        original_path = Path(self.selected_file.get())
        suggested_name = f"{original_path.stem}_simplified_{len(self.simplified_vertices)}v{original_path.suffix}"
        
        output_file = filedialog.asksaveasfilename(
            title="Guardar STL simplificat",
            initialname=suggested_name,
            defaultextension=".stl",
            filetypes=[
                ("Fitxers STL", "*.stl"),
                ("Tots els fitxers", "*.*")
            ]
        )
        
        if output_file:
            try:
                self.save_stl_binary(self.simplified_vertices, self.simplified_faces, output_file)
                messagebox.showinfo("Èxit", f"STL simplificat guardat:\n{os.path.basename(output_file)}")
                print(f"💾 STL guardat: {output_file}")
            except Exception as e:
                messagebox.showerror("Error", f"Error guardant STL:\n{str(e)}")
                print(f"❌ Error guardant STL: {e}")
    
    def save_stl_binary(self, vertices, faces, output_path):
        """Guarda STL en format binari"""
        with open(output_path, 'wb') as f:
            # Header
            header = b'Simplified STL from PackAssist' + b'\0' * (80 - 30)
            f.write(header)
            
            # Nombre de triangles
            f.write(struct.pack('<I', len(faces)))
            
            # Triangles
            for face in faces:
                # Calcular normal
                v1, v2, v3 = vertices[face[0]], vertices[face[1]], vertices[face[2]]
                edge1 = v2 - v1
                edge2 = v3 - v1
                normal = np.cross(edge1, edge2)
                normal = normal / (np.linalg.norm(normal) + 1e-8)
                
                # Escriure normal
                f.write(struct.pack('<fff', normal[0], normal[1], normal[2]))
                
                # Escriure vèrtexs
                for vertex_idx in face:
                    vertex = vertices[vertex_idx]
                    f.write(struct.pack('<fff', vertex[0], vertex[1], vertex[2]))
                
                # Attribute count
                f.write(struct.pack('<H', 0))
    
    def visualize_original(self):
        """Visualitza la malla original"""
        if self.current_vertices is None or self.current_faces is None:
            messagebox.showerror("Error", "No hi ha malla original per visualitzar!")
            return
        
        self.create_3d_visualization(self.current_vertices, self.current_faces, "Malla Original")
    
    def visualize_simplified(self):
        """Visualitza la malla simplificada"""
        if self.simplified_vertices is None or self.simplified_faces is None:
            messagebox.showerror("Error", "No hi ha malla simplificada per visualitzar!")
            return
        
        self.create_3d_visualization(self.simplified_vertices, self.simplified_faces, "Malla Simplificada")
    
    def visualize_compare(self):
        """Visualitza comparació entre original i simplificada"""
        if (self.current_vertices is None or self.current_faces is None or 
            self.simplified_vertices is None or self.simplified_faces is None):
            messagebox.showerror("Error", "Necessites tant la malla original com la simplificada!")
            return
        
        self.create_comparison_visualization()
    
    def create_3d_visualization(self, vertices, faces, title):
        """Crea visualització 3D amb matplotlib"""
        try:
            import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d import Axes3D
            from mpl_toolkits.mplot3d.art3d import Poly3DCollection
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            
            # Netejar canvas anterior
            for widget in self.viz_canvas_frame.winfo_children():
                widget.destroy()
            
            # Crear figura
            fig = plt.figure(figsize=(10, 8))
            ax = fig.add_subplot(111, projection='3d')
            
            # Preparar triangles per visualització
            triangles = []
            for face in faces:
                if len(face) >= 3:
                    triangle = [vertices[face[0]], vertices[face[1]], vertices[face[2]]]
                    triangles.append(triangle)
            
            # Crear col·lecció de polígons 3D
            poly_collection = Poly3DCollection(triangles, alpha=0.7, facecolor='lightblue', 
                                              edgecolor='navy', linewidth=0.1)
            ax.add_collection3d(poly_collection)
            
            # Configurar eixos
            all_vertices = np.array(vertices)
            ax.set_xlim(all_vertices[:, 0].min(), all_vertices[:, 0].max())
            ax.set_ylim(all_vertices[:, 1].min(), all_vertices[:, 1].max())
            ax.set_zlim(all_vertices[:, 2].min(), all_vertices[:, 2].max())
            
            ax.set_xlabel('X (mm)')
            ax.set_ylabel('Y (mm)')
            ax.set_zlabel('Z (mm)')
            ax.set_title(f'{title}\n{len(vertices):,} vèrtexs, {len(faces):,} triangles')
            
            # Integrar amb tkinter
            canvas = FigureCanvasTkAgg(fig, self.viz_canvas_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)
            
            # Actualitzar info
            self.viz_info_label.config(
                text=f"Mostrant: {title} - {len(vertices):,} vèrtexs",
                foreground='black'
            )
            
            print(f"👁️ Visualització creada: {title}")
            
        except ImportError:
            messagebox.showerror("Error", "matplotlib no està instal·lat!")
        except Exception as e:
            messagebox.showerror("Error", f"Error creant visualització:\n{str(e)}")
            print(f"❌ Error en visualització: {e}")
    
    def create_comparison_visualization(self):
        """Crea visualització de comparació"""
        try:
            import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d import Axes3D
            from mpl_toolkits.mplot3d.art3d import Poly3DCollection
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            
            # Netejar canvas anterior
            for widget in self.viz_canvas_frame.winfo_children():
                widget.destroy()
            
            # Crear figura amb subplots
            fig = plt.figure(figsize=(15, 7))
            
            # Subplot 1: Original
            ax1 = fig.add_subplot(121, projection='3d')
            
            triangles_orig = []
            for face in self.current_faces:
                if len(face) >= 3:
                    triangle = [self.current_vertices[face[0]], 
                               self.current_vertices[face[1]], 
                               self.current_vertices[face[2]]]
                    triangles_orig.append(triangle)
            
            poly_orig = Poly3DCollection(triangles_orig, alpha=0.7, facecolor='lightcoral', 
                                        edgecolor='darkred', linewidth=0.1)
            ax1.add_collection3d(poly_orig)
            
            # Subplot 2: Simplificat
            ax2 = fig.add_subplot(122, projection='3d')
            
            triangles_simp = []
            for face in self.simplified_faces:
                if len(face) >= 3:
                    triangle = [self.simplified_vertices[face[0]], 
                               self.simplified_vertices[face[1]], 
                               self.simplified_vertices[face[2]]]
                    triangles_simp.append(triangle)
            
            poly_simp = Poly3DCollection(triangles_simp, alpha=0.7, facecolor='lightblue', 
                                        edgecolor='darkblue', linewidth=0.1)
            ax2.add_collection3d(poly_simp)
            
            # Configurar eixos (mateix rang per ambdós)
            all_orig = np.array(self.current_vertices)
            all_simp = np.array(self.simplified_vertices)
            
            min_vals = np.minimum(all_orig.min(axis=0), all_simp.min(axis=0))
            max_vals = np.maximum(all_orig.max(axis=0), all_simp.max(axis=0))
            
            for ax in [ax1, ax2]:
                ax.set_xlim(min_vals[0], max_vals[0])
                ax.set_ylim(min_vals[1], max_vals[1])
                ax.set_zlim(min_vals[2], max_vals[2])
                ax.set_xlabel('X (mm)')
                ax.set_ylabel('Y (mm)')
                ax.set_zlabel('Z (mm)')
            
            ax1.set_title(f'Original\n{len(self.current_vertices):,} vèrtexs')
            ax2.set_title(f'Simplificat\n{len(self.simplified_vertices):,} vèrtexs')
            
            plt.tight_layout()
            
            # Integrar amb tkinter
            canvas = FigureCanvasTkAgg(fig, self.viz_canvas_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)
            
            # Actualitzar info
            reduction = ((len(self.current_vertices) - len(self.simplified_vertices)) / 
                        len(self.current_vertices)) * 100
            self.viz_info_label.config(
                text=f"Comparació - Reducció: {reduction:.1f}%",
                foreground='black'
            )
            
            print("👁️ Visualització de comparació creada")
            
        except ImportError:
            messagebox.showerror("Error", "matplotlib no està instal·lat!")
        except Exception as e:
            messagebox.showerror("Error", f"Error creant comparació:\n{str(e)}")
            print(f"❌ Error en comparació: {e}")
    
    def run(self):
        """Executa l'aplicació"""
        self.root.mainloop()


def main():
    """Funció principal"""
    print("🚀 Iniciant PackAssist - Simplificador STL Avançat")
    
    try:
        app = AdvancedSTLSimplifier()
        app.run()
    except Exception as e:
        print(f"❌ Error iniciant aplicació: {e}")
        messagebox.showerror("Error", f"Error iniciant aplicació:\n{str(e)}")


if __name__ == "__main__":
    main()
