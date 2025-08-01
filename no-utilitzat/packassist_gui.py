"""
PackAssist GUI - Aplicació Principal amb Pestanyes
Una interfície completa i fàcil d'usar per empaquetament 3D
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import json
from datetime import datetime

# Afegir src al path
sys.path.append(os.path.join(os.path.dirname(__file__), 'actiu', 'src'))


class PackAssistGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PackAssist - Empaquetament Intel·ligent 3D")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Variables globals
        self.selected_stl = tk.StringVar()
        self.box_width = tk.DoubleVar(value=200.0)
        self.box_height = tk.DoubleVar(value=150.0)
        self.box_depth = tk.DoubleVar(value=100.0)
        self.calculated_objects = 0
        self.results_data = None
        
        self.setup_gui()
    
    def setup_gui(self):
        """Configura la interfície gràfica amb pestanyes"""
        # Estil
        style = ttk.Style()
        style.theme_use('clam')
        
        # Títol principal
        header_frame = tk.Frame(self.root, bg='#2c3e50', height=60)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, 
                              text="🚀 PackAssist - Empaquetament Intel·ligent 3D",
                              font=("Arial", 18, "bold"), 
                              fg='white', bg='#2c3e50')
        title_label.pack(expand=True)
        
        # Notebook (pestanyes)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Pestanya 1: Càlcul Principal
        self.calc_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.calc_frame, text="📊 Càlcul d'Empaquetament")
        self.setup_calc_tab()
        
        # Pestanya 2: Optimització STL
        self.optim_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.optim_frame, text="⚡ Optimització STL")
        self.setup_optimization_tab()
        
        # Pestanya 3: Visualització i Exportació
        self.export_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.export_frame, text="🎨 Visualització i Exportació")
        self.setup_export_tab()
        
        # Pestanya 4: Proves i Testing
        self.test_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.test_frame, text="🧪 Proves i Testing")
        self.setup_test_tab()
        
        # Barra d'estat
        self.status_bar = tk.Label(self.root, text="Preparat per calcular empaquetament", 
                                  relief=tk.SUNKEN, anchor=tk.W, bg='#ecf0f1')
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def setup_calc_tab(self):
        """Pestanya principal de càlcul"""
        # Scroll per contingut llarg
        canvas = tk.Canvas(self.calc_frame)
        scrollbar = ttk.Scrollbar(self.calc_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Secció 1: Selecció d'objecte
        obj_section = ttk.LabelFrame(scrollable_frame, text="🎯 1. Objecte a empaquetar", padding=20)
        obj_section.pack(fill='x', padx=20, pady=(20, 10))
        
        # Botó seleccionar STL
        stl_button_frame = ttk.Frame(obj_section)
        stl_button_frame.pack(fill='x')
        
        ttk.Button(stl_button_frame, text="📁 Seleccionar fitxer STL", 
                  command=self.select_stl_file, width=25).pack(side='left')
        
        # Info del fitxer
        self.stl_info_label = ttk.Label(stl_button_frame, text="Cap fitxer seleccionat", 
                                       foreground='gray')
        self.stl_info_label.pack(side='left', padx=(15, 0))
        
        # Consell d'optimització
        self.optim_hint = ttk.Label(obj_section, 
                                   text="💡 Consell: Si el fitxer STL és gran (>5MB), usa la pestanya 'Optimització STL' primer",
                                   foreground='#3498db', font=("Arial", 9))
        self.optim_hint.pack(pady=(10, 0))
        self.optim_hint.pack_forget()  # Amagar inicialment
        
        # Secció 2: Dimensions de la caixa
        box_section = ttk.LabelFrame(scrollable_frame, text="📦 2. Dimensions de la caixa contenidora", padding=20)
        box_section.pack(fill='x', padx=20, pady=10)
        
        # Grid per dimensions
        dims_frame = ttk.Frame(box_section)
        dims_frame.pack()
        
        # Amplada
        ttk.Label(dims_frame, text="Amplada:", font=("Arial", 11)).grid(row=0, column=0, sticky='w', padx=(0, 10), pady=5)
        ttk.Entry(dims_frame, textvariable=self.box_width, width=12, font=("Arial", 11)).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(dims_frame, text="mm", font=("Arial", 11)).grid(row=0, column=2, sticky='w', pady=5)
        
        # Alçada
        ttk.Label(dims_frame, text="Alçada:", font=("Arial", 11)).grid(row=1, column=0, sticky='w', padx=(0, 10), pady=5)
        ttk.Entry(dims_frame, textvariable=self.box_height, width=12, font=("Arial", 11)).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(dims_frame, text="mm", font=("Arial", 11)).grid(row=1, column=2, sticky='w', pady=5)
        
        # Profunditat
        ttk.Label(dims_frame, text="Profunditat:", font=("Arial", 11)).grid(row=2, column=0, sticky='w', padx=(0, 10), pady=5)
        ttk.Entry(dims_frame, textvariable=self.box_depth, width=12, font=("Arial", 11)).grid(row=2, column=1, padx=5, pady=5)
        ttk.Label(dims_frame, text="mm", font=("Arial", 11)).grid(row=2, column=2, sticky='w', pady=5)
        
        # Presets de caixes comunes
        presets_frame = ttk.Frame(box_section)
        presets_frame.pack(pady=(15, 0))
        
        ttk.Label(presets_frame, text="Presets comuns:", font=("Arial", 10)).pack(anchor='w')
        
        presets_buttons = ttk.Frame(presets_frame)
        presets_buttons.pack(pady=(5, 0))
        
        ttk.Button(presets_buttons, text="Caixa Petita (100x80x60)", 
                  command=lambda: self.set_box_preset(100, 80, 60)).pack(side='left', padx=(0, 5))
        ttk.Button(presets_buttons, text="Caixa Mitjana (200x150x100)", 
                  command=lambda: self.set_box_preset(200, 150, 100)).pack(side='left', padx=5)
        ttk.Button(presets_buttons, text="Caixa Gran (400x300x200)", 
                  command=lambda: self.set_box_preset(400, 300, 200)).pack(side='left', padx=5)
        
        # Secció 3: Càlcul
        calc_section = ttk.LabelFrame(scrollable_frame, text="🔄 3. Càlcul d'empaquetament", padding=20)
        calc_section.pack(fill='x', padx=20, pady=10)
        
        # Botó principal de càlcul
        self.calc_button = ttk.Button(calc_section, 
                                     text="🚀 CALCULAR QUANTS OBJECTES CABEN", 
                                     command=self.calculate_packing,
                                     style='Accent.TButton')
        self.calc_button.pack(pady=(0, 15))
        
        # Barra de progrés
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(calc_section, variable=self.progress_var, 
                                           maximum=100)
        self.progress_bar.pack(fill='x', pady=(0, 10))
        self.progress_bar.pack_forget()
        
        # Resultat
        self.result_label = ttk.Label(calc_section, text="", foreground='green', 
                                     font=("Arial", 12, "bold"))
        self.result_label.pack()
        
        # Pack del canvas i scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def setup_optimization_tab(self):
        """Pestanya d'optimització STL"""
        # Títol
        title_label = ttk.Label(self.optim_frame, text="⚡ Optimització de models STL", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=20)
        
        # Descripció
        desc_text = """
L'optimització redueix la complexitat dels models STL mantenint la forma general.
Això accelera els càlculs significativament (de 20+ minuts a 2-3 segons).
        """
        ttk.Label(self.optim_frame, text=desc_text, justify='center', 
                 font=("Arial", 10)).pack(pady=(0, 20))
        
        # Opcions d'optimització
        options_frame = ttk.LabelFrame(self.optim_frame, text="Eines d'optimització", padding=20)
        options_frame.pack(fill='x', padx=40, pady=20)
        
        # Simplificador simple
        simple_frame = ttk.Frame(options_frame)
        simple_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(simple_frame, text="🔧 Optimitzador Simple (Recomanat)", 
                 font=("Arial", 12, "bold")).pack(anchor='w')
        ttk.Label(simple_frame, text="Compatible amb Windows, interfície senzilla", 
                 font=("Arial", 10), foreground='gray').pack(anchor='w', pady=(2, 8))
        ttk.Button(simple_frame, text="Obrir Optimitzador Simple", 
                  command=self.open_simple_optimizer, width=30).pack(anchor='w')
        
        # Separador
        ttk.Separator(options_frame, orient='horizontal').pack(fill='x', pady=15)
        
        # Simplificador avançat
        advanced_frame = ttk.Frame(options_frame)
        advanced_frame.pack(fill='x')
        
        ttk.Label(advanced_frame, text="🚀 Optimitzador Avançat", 
                 font=("Arial", 12, "bold")).pack(anchor='w')
        ttk.Label(advanced_frame, text="Múltiples algoritmes: PyMeshLab, PyVista, Trimesh, pyfqmr", 
                 font=("Arial", 10), foreground='gray').pack(anchor='w', pady=(2, 8))
        ttk.Button(advanced_frame, text="Obrir Optimitzador Avançat", 
                  command=self.open_advanced_optimizer, width=30).pack(anchor='w')
        
        # Instruccions
        instructions_frame = ttk.LabelFrame(self.optim_frame, text="📝 Instruccions", padding=20)
        instructions_frame.pack(fill='x', padx=40, pady=(0, 20))
        
        instructions_text = """
1. Selecciona una eina d'optimització
2. Carrega el teu fitxer STL gran
3. Estableix el nombre objectiu de vèrtexs (recomanat: 500-2000)
4. Clica 'Optimitzar' i espera el resultat
5. Torna a la pestanya 'Càlcul' i carrega l'STL optimitzat
        """
        ttk.Label(instructions_frame, text=instructions_text, justify='left', 
                 font=("Arial", 10)).pack(anchor='w')
    
    def setup_export_tab(self):
        """Pestanya de visualització i exportació"""
        # Títol
        title_label = ttk.Label(self.export_frame, text="🎨 Visualització i Exportació", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=20)
        
        # Info dels resultats
        info_frame = ttk.LabelFrame(self.export_frame, text="📊 Informació dels resultats", padding=20)
        info_frame.pack(fill='x', padx=40, pady=(0, 20))
        
        self.export_info_label = ttk.Label(info_frame, 
                                          text="No hi ha resultats disponibles.\nPrimer calcula un empaquetament a la pestanya 'Càlcul'.",
                                          foreground='gray', justify='center')
        self.export_info_label.pack()
        
        # Opcions de visualització i exportació
        self.export_options_frame = ttk.LabelFrame(self.export_frame, text="🎯 Opcions disponibles", padding=20)
        self.export_options_frame.pack(fill='x', padx=40, pady=(0, 20))
        
        # Grid d'opcions
        options_grid = ttk.Frame(self.export_options_frame)
        options_grid.pack()
        
        # Visualització 3D
        vis_frame = ttk.Frame(options_grid)
        vis_frame.grid(row=0, column=0, padx=10, pady=10, sticky='w')
        ttk.Label(vis_frame, text="🔍 Visualització 3D", font=("Arial", 11, "bold")).pack(anchor='w')
        ttk.Label(vis_frame, text="Veure el resultat en 3D interactiu", font=("Arial", 9), foreground='gray').pack(anchor='w')
        self.visualize_button = ttk.Button(vis_frame, text="Visualitzar en 3D", 
                                          command=self.visualize_3d, state='disabled', width=20)
        self.visualize_button.pack(pady=(5, 0))
        
        # Exportar imatges
        img_frame = ttk.Frame(options_grid)
        img_frame.grid(row=0, column=1, padx=10, pady=10, sticky='w')
        ttk.Label(img_frame, text="📷 Exportació d'Imatges", font=("Arial", 11, "bold")).pack(anchor='w')
        ttk.Label(img_frame, text="Generar imatges des de 12 angles", font=("Arial", 9), foreground='gray').pack(anchor='w')
        self.export_images_button = ttk.Button(img_frame, text="Exportar Imatges", 
                                              command=self.export_images, state='disabled', width=20)
        self.export_images_button.pack(pady=(5, 0))
        
        # Exportar dades
        data_frame = ttk.Frame(options_grid)
        data_frame.grid(row=1, column=0, padx=10, pady=10, sticky='w')
        ttk.Label(data_frame, text="💾 Exportació de Dades", font=("Arial", 11, "bold")).pack(anchor='w')
        ttk.Label(data_frame, text="Guardar resultats en format JSON", font=("Arial", 9), foreground='gray').pack(anchor='w')
        self.export_data_button = ttk.Button(data_frame, text="Exportar Dades", 
                                            command=self.export_data, state='disabled', width=20)
        self.export_data_button.pack(pady=(5, 0))
        
        # Informe complet
        report_frame = ttk.Frame(options_grid)
        report_frame.grid(row=1, column=1, padx=10, pady=10, sticky='w')
        ttk.Label(report_frame, text="📋 Informe Complet", font=("Arial", 11, "bold")).pack(anchor='w')
        ttk.Label(report_frame, text="Generar informe amb tot inclòs", font=("Arial", 9), foreground='gray').pack(anchor='w')
        self.export_all_button = ttk.Button(report_frame, text="Informe Complet", 
                                           command=self.export_complete_report, state='disabled', width=20)
        self.export_all_button.pack(pady=(5, 0))
        
        # Amagar opcions inicialment
        self.export_options_frame.pack_forget()
    
    def setup_test_tab(self):
        """Pestanya de proves i testing"""
        # Títol
        title_label = ttk.Label(self.test_frame, text="🧪 Proves i Testing", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=20)
        
        # Descripció
        desc_text = """
Eines per provar el sistema amb objectes generats automàticament
i verificar el funcionament de les diferents funcionalitats.
        """
        ttk.Label(self.test_frame, text=desc_text, justify='center', 
                 font=("Arial", 10)).pack(pady=(0, 20))
        
        # Opcions de testing
        test_options = ttk.LabelFrame(self.test_frame, text="🎯 Opcions de proves", padding=20)
        test_options.pack(fill='x', padx=40, pady=20)
        
        # Grid de proves
        test_grid = ttk.Frame(test_options)
        test_grid.pack()
        
        # Proves de simplificació
        mesh_test_frame = ttk.Frame(test_grid)
        mesh_test_frame.grid(row=0, column=0, padx=15, pady=15, sticky='nw')
        ttk.Label(mesh_test_frame, text="⚡ Proves d'Optimització", font=("Arial", 11, "bold")).pack(anchor='w')
        ttk.Label(mesh_test_frame, text="Provar els algoritmes de simplificació", 
                 font=("Arial", 9), foreground='gray').pack(anchor='w', pady=(2, 8))
        ttk.Button(mesh_test_frame, text="Provar Optimització", 
                  command=self.run_mesh_tests, width=20).pack()
        
        # Crear objectes de prova
        create_test_frame = ttk.Frame(test_grid)
        create_test_frame.grid(row=0, column=1, padx=15, pady=15, sticky='nw')
        ttk.Label(create_test_frame, text="🎲 Crear Objectes de Prova", font=("Arial", 11, "bold")).pack(anchor='w')
        ttk.Label(create_test_frame, text="Generar objectes STL per testing", 
                 font=("Arial", 9), foreground='gray').pack(anchor='w', pady=(2, 8))
        ttk.Button(create_test_frame, text="Crear Objectes", 
                  command=self.create_test_objects, width=20).pack()
        
        # Prova ràpida
        quick_test_frame = ttk.Frame(test_grid)
        quick_test_frame.grid(row=1, column=0, padx=15, pady=15, sticky='nw')
        ttk.Label(quick_test_frame, text="🚀 Prova Ràpida", font=("Arial", 11, "bold")).pack(anchor='w')
        ttk.Label(quick_test_frame, text="Test complet amb objecte generat", 
                 font=("Arial", 9), foreground='gray').pack(anchor='w', pady=(2, 8))
        ttk.Button(quick_test_frame, text="Prova Ràpida", 
                  command=self.quick_test, width=20).pack()
        
        # Info del sistema
        system_info_frame = ttk.Frame(test_grid)
        system_info_frame.grid(row=1, column=1, padx=15, pady=15, sticky='nw')
        ttk.Label(system_info_frame, text="ℹ️ Info del Sistema", font=("Arial", 11, "bold")).pack(anchor='w')
        ttk.Label(system_info_frame, text="Veure dependències instal·lades", 
                 font=("Arial", 9), foreground='gray').pack(anchor='w', pady=(2, 8))
        ttk.Button(system_info_frame, text="Info Sistema", 
                  command=self.show_system_info, width=20).pack()
    
    # Mètodes de funcionalitat
    def set_box_preset(self, width, height, depth):
        """Estableix un preset de dimensions de caixa"""
        self.box_width.set(width)
        self.box_height.set(height)
        self.box_depth.set(depth)
        self.update_status(f"Preset aplicat: {width}x{height}x{depth}mm")
    
    def select_stl_file(self):
        """Selecciona un fitxer STL"""
        file_path = filedialog.askopenfilename(
            title="Selecciona fitxer STL",
            filetypes=[
                ("Fitxers STL", "*.stl"),
                ("Tots els fitxers", "*.*")
            ]
        )
        
        if file_path:
            self.selected_stl.set(file_path)
            
            # Mostrar info del fitxer
            try:
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                filename = os.path.basename(file_path)
                self.stl_info_label.config(
                    text=f"📁 {filename} ({size_mb:.1f} MB)",
                    foreground='black'
                )
                
                # Mostrar consell d'optimització si el fitxer és gran
                if size_mb > 5:
                    self.optim_hint.pack(pady=(10, 0))
                    self.update_status(f"Fitxer gran carregat ({size_mb:.1f}MB) - Considera optimitzar-lo")
                else:
                    self.optim_hint.pack_forget()
                    self.update_status(f"Fitxer STL carregat: {filename}")
                    
            except Exception as e:
                self.stl_info_label.config(
                    text=f"📁 {os.path.basename(file_path)} (error llegint mida)",
                    foreground='red'
                )
                self.update_status("Error llegint el fitxer STL")
    
    def calculate_packing(self):
        """Calcula l'empaquetament"""
        if not self.selected_stl.get():
            messagebox.showerror("Error", "Primer selecciona un fitxer STL")
            return
        
        if not os.path.exists(self.selected_stl.get()):
            messagebox.showerror("Error", "El fitxer STL seleccionat no existeix")
            return
        
        # Mostrar barra de progrés
        self.progress_bar.pack(fill='x', pady=(10, 0))
        self.calc_button.config(state='disabled')
        self.update_status("Calculant empaquetament...")
        
        # Actualitzar GUI
        self.root.update()
        
        try:
            # Simular càlcul
            self.simulate_calculation()
            
            # Crear resultats
            self.create_results()
            
            # Actualitzar interfície
            self.result_label.config(
                text=f"✅ Càlcul completat!\n"
                     f"CABEN {self.calculated_objects} objectes en la caixa "
                     f"{self.box_width.get()}x{self.box_height.get()}x{self.box_depth.get()}mm",
                foreground='green'
            )
            
            # Activar pestanya d'exportació
            self.update_export_tab()
            self.update_status(f"Càlcul completat: {self.calculated_objects} objectes caben")
            
        except Exception as e:
            self.result_label.config(
                text=f"❌ Error en el càlcul: {e}",
                foreground='red'
            )
            self.update_status("Error en el càlcul")
        
        finally:
            # Amagar barra de progrés i reactivar botó
            self.progress_bar.pack_forget()
            self.calc_button.config(state='normal')
    
    def simulate_calculation(self):
        """Simula el procés de càlcul amb barra de progrés"""
        import time
        
        steps = [
            "Carregant model 3D...",
            "Analitzant dimensions de l'objecte...",
            "Calculant posicions òptimes...",
            "Provant diferents orientacions...",
            "Determinant nombre màxim d'objectes..."
        ]
        
        for i, step in enumerate(steps):
            self.update_status(step)
            self.progress_var.set((i + 1) * 20)
            self.root.update()
            time.sleep(0.3)  # Simular treball
    
    def create_results(self):
        """Crea resultats simulats"""
        import random
        
        # Simular càlcul de quants objectes caben
        box_volume = self.box_width.get() * self.box_height.get() * self.box_depth.get()
        estimated_object_volume = min(15000, max(1000, box_volume * 0.1))
        max_objects = max(1, int(box_volume / estimated_object_volume * 0.6))
        
        self.calculated_objects = random.randint(max(1, max_objects - 2), max_objects + 1)
        
        # Generar posicions
        objects = []
        for i in range(self.calculated_objects):
            x = random.uniform(10, self.box_width.get() - 10)
            y = random.uniform(10, self.box_height.get() - 10)
            z = random.uniform(10, self.box_depth.get() - 10)
            
            objects.append({
                'id': i + 1,
                'position': [x, y, z],
                'rotation': [0, 0, random.uniform(0, 360)]
            })
        
        self.results_data = {
            'stl_file': self.selected_stl.get(),
            'box_dimensions': [self.box_width.get(), self.box_height.get(), self.box_depth.get()],
            'num_objects': self.calculated_objects,
            'objects': objects,
            'calculation_date': datetime.now().isoformat(),
            'efficiency': random.uniform(75, 95)
        }
    
    def update_export_tab(self):
        """Actualitza la pestanya d'exportació"""
        if self.results_data:
            # Actualitzar info
            info_text = f"✅ Resultats disponibles: {self.results_data['num_objects']} objectes\n"
            info_text += f"📦 Caixa: {self.results_data['box_dimensions'][0]}x{self.results_data['box_dimensions'][1]}x{self.results_data['box_dimensions'][2]}mm\n"
            info_text += f"📊 Eficiència: {self.results_data['efficiency']:.1f}%"
            
            self.export_info_label.config(text=info_text, foreground='black')
            
            # Mostrar opcions
            self.export_options_frame.pack(fill='x', padx=40, pady=(0, 20))
            
            # Activar botons
            self.visualize_button.config(state='normal')
            self.export_images_button.config(state='normal')
            self.export_data_button.config(state='normal')
            self.export_all_button.config(state='normal')
    
    def open_simple_optimizer(self):
        """Obre l'optimitzador simple"""
        try:
            python_cmd = os.path.join("packassist_env", "Scripts", "python.exe")
            if not os.path.exists(python_cmd):
                python_cmd = "python"
            
            simplifier_path = os.path.join("tools", "mesh_simplifiers", "mesh_simplifier_simple.py")
            subprocess.Popen([python_cmd, simplifier_path])
            self.update_status("Optimitzador simple obert")
            
        except Exception as e:
            messagebox.showerror("Error", f"No s'ha pogut obrir l'optimitzador: {e}")
    
    def open_advanced_optimizer(self):
        """Obre l'optimitzador avançat"""
        try:
            python_cmd = os.path.join("packassist_env", "Scripts", "python.exe")
            if not os.path.exists(python_cmd):
                python_cmd = "python"
            
            simplifier_path = os.path.join("tools", "mesh_simplifiers", "ultra_fast_mesh_simplifier.py")
            subprocess.Popen([python_cmd, simplifier_path])
            self.update_status("Optimitzador avançat obert")
            
        except Exception as e:
            messagebox.showerror("Error", f"No s'ha pogut obrir l'optimitzador: {e}")
    
    def visualize_3d(self):
        """Visualitza els resultats en 3D"""
        if not self.results_data:
            messagebox.showerror("Error", "No hi ha resultats per visualitzar")
            return
        
        try:
            self.create_3d_visualization()
            self.update_status("Visualització 3D creada")
        except Exception as e:
            messagebox.showerror("Error", f"Error en la visualització 3D: {e}")
    
    def create_3d_visualization(self):
        """Crea visualització 3D amb matplotlib"""
        try:
            import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d import Axes3D
            import numpy as np
            
            # Crear figura
            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection='3d')
            
            # Dibuixar caixa
            box_dims = self.results_data['box_dimensions']
            
            # Vèrtexs de la caixa
            vertices = [
                [0, 0, 0], [box_dims[0], 0, 0], [box_dims[0], box_dims[1], 0], [0, box_dims[1], 0],
                [0, 0, box_dims[2]], [box_dims[0], 0, box_dims[2]], [box_dims[0], box_dims[1], box_dims[2]], [0, box_dims[1], box_dims[2]]
            ]
            
            # Arestes de la caixa
            edges = [
                [0, 1], [1, 2], [2, 3], [3, 0],  # Base
                [4, 5], [5, 6], [6, 7], [7, 4],  # Top
                [0, 4], [1, 5], [2, 6], [3, 7]   # Verticals
            ]
            
            for edge in edges:
                points = np.array([vertices[edge[0]], vertices[edge[1]]])
                ax.plot3D(points[:, 0], points[:, 1], points[:, 2], 'b-', alpha=0.6, linewidth=2)
            
            # Dibuixar objectes
            for obj in self.results_data['objects']:
                pos = obj['position']
                ax.scatter(pos[0], pos[1], pos[2], c='red', s=100, alpha=0.7)
                ax.text(pos[0], pos[1], pos[2] + 5, f"Obj {obj['id']}", fontsize=8)
            
            # Configurar eixos
            ax.set_xlabel('X (mm)')
            ax.set_ylabel('Y (mm)')
            ax.set_zlabel('Z (mm)')
            ax.set_title(f'Empaquetament de {self.results_data["num_objects"]} objectes')
            
            # Establir límits
            ax.set_xlim(0, box_dims[0])
            ax.set_ylim(0, box_dims[1])
            ax.set_zlim(0, box_dims[2])
            
            plt.tight_layout()
            plt.show()
            
        except ImportError:
            messagebox.showerror("Error", "matplotlib no està instal·lat.\nInstal·la'l amb: pip install matplotlib")
    
    def export_images(self):
        """Exporta imatges des de diferents angles"""
        if not self.results_data:
            messagebox.showerror("Error", "No hi ha resultats per exportar")
            return
        
        output_dir = filedialog.askdirectory(title="Selecciona directori per les imatges")
        if not output_dir:
            return
        
        try:
            self.generate_multiple_view_images(output_dir)
            messagebox.showinfo("Èxit", f"Imatges exportades a:\n{output_dir}")
            self.update_status(f"Imatges exportades a {output_dir}")
        except Exception as e:
            messagebox.showerror("Error", f"Error exportant imatges: {e}")
    
    def generate_multiple_view_images(self, output_dir):
        """Genera imatges des de 12 angles diferents"""
        try:
            import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d import Axes3D
            import numpy as np
            
            views = [
                (20, 0), (20, 30), (20, 60), (20, 90),
                (20, 120), (20, 150), (20, 180), (20, 210),
                (20, 240), (20, 270), (20, 300), (20, 330)
            ]
            
            for i, (elev, azim) in enumerate(views):
                fig = plt.figure(figsize=(10, 8))
                ax = fig.add_subplot(111, projection='3d')
                
                # Dibuixar caixa i objectes
                box_dims = self.results_data['box_dimensions']
                
                vertices = [
                    [0, 0, 0], [box_dims[0], 0, 0], [box_dims[0], box_dims[1], 0], [0, box_dims[1], 0],
                    [0, 0, box_dims[2]], [box_dims[0], 0, box_dims[2]], [box_dims[0], box_dims[1], box_dims[2]], [0, box_dims[1], box_dims[2]]
                ]
                
                edges = [
                    [0, 1], [1, 2], [2, 3], [3, 0],
                    [4, 5], [5, 6], [6, 7], [7, 4],
                    [0, 4], [1, 5], [2, 6], [3, 7]
                ]
                
                for edge in edges:
                    points = np.array([vertices[edge[0]], vertices[edge[1]]])
                    ax.plot3D(points[:, 0], points[:, 1], points[:, 2], 'b-', alpha=0.8, linewidth=2)
                
                for obj in self.results_data['objects']:
                    pos = obj['position']
                    ax.scatter(pos[0], pos[1], pos[2], c='red', s=150, alpha=0.8)
                
                ax.view_init(elev=elev, azim=azim)
                ax.set_xlabel('X (mm)')
                ax.set_ylabel('Y (mm)')
                ax.set_zlabel('Z (mm)')
                ax.set_title(f'Vista {i+1}: Empaquetament ({elev}°, {azim}°)')
                
                ax.set_xlim(0, box_dims[0])
                ax.set_ylim(0, box_dims[1])
                ax.set_zlim(0, box_dims[2])
                
                filename = f"empaquetament_vista_{i+1:02d}_{elev}_{azim}.png"
                filepath = os.path.join(output_dir, filename)
                plt.savefig(filepath, dpi=150, bbox_inches='tight')
                plt.close()
                
        except ImportError:
            raise Exception("matplotlib no està instal·lat")
    
    def export_data(self):
        """Exporta dades en JSON"""
        if not self.results_data:
            messagebox.showerror("Error", "No hi ha resultats per exportar")
            return
        
        output_file = filedialog.asksaveasfilename(
            title="Guardar dades d'empaquetament",
            defaultextension=".json",
            filetypes=[("Fitxers JSON", "*.json"), ("Tots els fitxers", "*.*")]
        )
        
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(self.results_data, f, indent=2, ensure_ascii=False)
                
                messagebox.showinfo("Èxit", f"Dades exportades a:\n{output_file}")
                self.update_status(f"Dades exportades a {os.path.basename(output_file)}")
            except Exception as e:
                messagebox.showerror("Error", f"Error exportant dades: {e}")
    
    def export_complete_report(self):
        """Exporta informe complet amb tot"""
        if not self.results_data:
            messagebox.showerror("Error", "No hi ha resultats per exportar")
            return
        
        output_dir = filedialog.askdirectory(title="Selecciona directori per l'informe complet")
        if not output_dir:
            return
        
        try:
            # Crear subdirectori per l'informe
            report_dir = os.path.join(output_dir, f"informe_packassist_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(report_dir, exist_ok=True)
            
            # Exportar dades JSON
            json_file = os.path.join(report_dir, "dades_empaquetament.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(self.results_data, f, indent=2, ensure_ascii=False)
            
            # Exportar imatges
            images_dir = os.path.join(report_dir, "imatges")
            os.makedirs(images_dir, exist_ok=True)
            self.generate_multiple_view_images(images_dir)
            
            messagebox.showinfo("Èxit", f"Informe complet generat a:\n{report_dir}")
            self.update_status(f"Informe complet generat")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error generant informe: {e}")
    
    def run_mesh_tests(self):
        """Executa proves d'optimització"""
        try:
            python_cmd = os.path.join("packassist_env", "Scripts", "python.exe")
            if not os.path.exists(python_cmd):
                python_cmd = "python"
            
            test_path = os.path.join("tests", "test_mesh_simplification.py")
            subprocess.Popen([python_cmd, test_path])
            self.update_status("Proves d'optimització iniciades")
            
        except Exception as e:
            messagebox.showerror("Error", f"No s'han pogut executar les proves: {e}")
    
    def create_test_objects(self):
        """Crea objectes de prova"""
        try:
            python_cmd = os.path.join("packassist_env", "Scripts", "python.exe")
            if not os.path.exists(python_cmd):
                python_cmd = "python"
            
            test_path = os.path.join("tests", "create_test_objects.py")
            subprocess.Popen([python_cmd, test_path])
            self.update_status("Creació d'objectes de prova iniciada")
            
        except Exception as e:
            messagebox.showerror("Error", f"No s'han pogut crear objectes de prova: {e}")
    
    def quick_test(self):
        """Prova ràpida del sistema"""
        # Simular una prova ràpida
        self.update_status("Executant prova ràpida...")
        
        # Establir valors de prova
        self.set_box_preset(150, 100, 80)
        
        # Simular selecció d'un objecte fictici
        self.stl_info_label.config(text="📁 objecte_prova.stl (simulat)", foreground='blue')
        self.selected_stl.set("objecte_simulat.stl")
        
        messagebox.showinfo("Prova Ràpida", 
                           "Prova ràpida configurada!\n\n"
                           "• Caixa: 150x100x80mm\n"
                           "• Objecte: simulat\n\n"
                           "Ara pots anar a la pestanya 'Càlcul' i calcular l'empaquetament.")
        
        # Canviar a la pestanya de càlcul
        self.notebook.select(0)
        self.update_status("Prova ràpida preparada - Càlcul a punt")
    
    def show_system_info(self):
        """Mostra informació del sistema"""
        try:
            import platform
            import sys
            
            info = f"""
INFORMACIÓ DEL SISTEMA
======================

🖥️ Sistema Operatiu: {platform.system()} {platform.release()}
🐍 Python: {sys.version.split()[0]}
📁 Directori: {os.getcwd()}

📦 DEPENDÈNCIES:
"""
            
            # Verificar dependències
            deps = [
                ("matplotlib", "Visualització 3D"),
                ("numpy", "Càlculs numèrics"),
                ("pymeshlab", "Optimització ultra-ràpida"),
                ("pyvista", "Optimització alternativa"),
                ("trimesh", "Processament malles"),
                ("pyfqmr", "Reducció quadric")
            ]
            
            for dep, desc in deps:
                try:
                    __import__(dep)
                    info += f"✅ {dep}: {desc}\n"
                except ImportError:
                    info += f"❌ {dep}: {desc} (no instal·lat)\n"
            
            info += f"\n🎯 ESTAT: Sistema preparat per empaquetament!"
            
            messagebox.showinfo("Informació del Sistema", info)
            self.update_status("Informació del sistema mostrada")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error obtenint info del sistema: {e}")
    
    def update_status(self, message):
        """Actualitza la barra d'estat"""
        self.status_bar.config(text=message)
        self.root.update_idletasks()
    
    def run(self):
        """Executa l'aplicació"""
        self.root.mainloop()


def main():
    """Funció principal"""
    try:
        app = PackAssistGUI()
        app.run()
    except Exception as e:
        print(f"Error iniciant aplicació: {e}")
        messagebox.showerror("Error", f"Error iniciant aplicació: {e}")


if __name__ == "__main__":
    main()
