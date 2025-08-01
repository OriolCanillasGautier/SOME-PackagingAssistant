"""
PackAssist - Aplicació Principal Simplificada
2 pestanyes: Càlcul i Exportació
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


class PackAssistApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PackAssist - Empaquetament Intel·ligent")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)
        
        # Variables
        self.selected_stl = tk.StringVar()
        self.box_width = tk.DoubleVar(value=200.0)
        self.box_height = tk.DoubleVar(value=150.0)
        self.box_depth = tk.DoubleVar(value=100.0)
        self.calculated_objects = 0  # Nombre calculat d'objectes que caben
        self.results_data = None
        
        self.setup_gui()
    
    def setup_gui(self):
        """Configura la interfície gràfica"""
        # Notebook (pestanyes)
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Pestanya 1: Càlcul
        calc_frame = ttk.Frame(notebook)
        notebook.add(calc_frame, text="Càlcul d'Empaquetament")
        self.setup_calc_tab(calc_frame)
        
        # Pestanya 2: Exportació
        export_frame = ttk.Frame(notebook)
        notebook.add(export_frame, text="Exportació de Resultats")
        self.setup_export_tab(export_frame)
    
    def setup_calc_tab(self, parent):
        """Configura la pestanya de càlcul"""
        # Títol
        title_label = ttk.Label(parent, text="Càlcul d'Empaquetament", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=20)
        
        # Frame principal
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Secció 1: Selecció d'objecte STL
        stl_frame = ttk.LabelFrame(main_frame, text="1. Objecte a empaquetar", padding=15)
        stl_frame.pack(fill='x', pady=(0, 15))
        
        # Botó per seleccionar STL
        stl_button_frame = ttk.Frame(stl_frame)
        stl_button_frame.pack(fill='x')
        
        ttk.Button(stl_button_frame, text="Seleccionar fitxer STL", 
                  command=self.select_stl_file, width=20).pack(side='left')
        
        # Info del fitxer seleccionat
        self.stl_info_label = ttk.Label(stl_button_frame, text="Cap fitxer seleccionat", 
                                       foreground='gray')
        self.stl_info_label.pack(side='left', padx=(15, 0))
        
        # Botó de simplificació
        self.simplify_button = ttk.Button(stl_frame, text="Accelerar càlcul (reduir detall del model)", 
                                         command=self.simplify_stl, state='disabled')
        self.simplify_button.pack(pady=(10, 0))
        
        # Secció 2: Configuració de la caixa
        config_frame = ttk.LabelFrame(main_frame, text="2. Dimensions de la caixa contenidora", padding=15)
        config_frame.pack(fill='x', pady=(0, 15))
        
        # Dimensions de la caixa
        box_frame = ttk.LabelFrame(config_frame, text="Defineix les mides de la caixa (mm)", padding=10)
        box_frame.pack(fill='x', pady=(0, 0))
        
        box_grid = ttk.Frame(box_frame)
        box_grid.pack()
        
        ttk.Label(box_grid, text="Amplada:").grid(row=0, column=0, sticky='w', padx=(0, 5))
        ttk.Entry(box_grid, textvariable=self.box_width, width=10).grid(row=0, column=1, padx=5)
        ttk.Label(box_grid, text="mm").grid(row=0, column=2, sticky='w')
        
        ttk.Label(box_grid, text="Alçada:").grid(row=1, column=0, sticky='w', padx=(0, 5), pady=5)
        ttk.Entry(box_grid, textvariable=self.box_height, width=10).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(box_grid, text="mm").grid(row=1, column=2, sticky='w', pady=5)
        
        ttk.Label(box_grid, text="Profunditat:").grid(row=2, column=0, sticky='w', padx=(0, 5))
        ttk.Entry(box_grid, textvariable=self.box_depth, width=10).grid(row=2, column=1, padx=5)
        ttk.Label(box_grid, text="mm").grid(row=2, column=2, sticky='w')
        
        # Secció 3: Càlcul
        calc_button_frame = ttk.Frame(main_frame)
        calc_button_frame.pack(fill='x', pady=20)
        
        self.calc_button = ttk.Button(calc_button_frame, 
                                     text="CALCULAR QUANTS OBJECTES CABEN", 
                                     command=self.calculate_packing,
                                     style='Accent.TButton')
        self.calc_button.pack(expand=True)
        
        # Barra de progrés
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, 
                                           maximum=100)
        self.progress_bar.pack(fill='x', pady=(10, 0))
        self.progress_bar.pack_forget()  # Amagar inicialment
        
        # Resultat
        self.result_label = ttk.Label(main_frame, text="", foreground='green', 
                                     font=("Arial", 12, "bold"))
        self.result_label.pack(pady=10)
    
    def setup_export_tab(self, parent):
        """Configura la pestanya d'exportació"""
        # Títol
        title_label = ttk.Label(parent, text="Exportació de Resultats", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=20)
        
        # Frame principal
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Info dels resultats
        info_frame = ttk.LabelFrame(main_frame, text="Informació dels resultats", padding=15)
        info_frame.pack(fill='x', pady=(0, 15))
        
        self.export_info_label = ttk.Label(info_frame, 
                                          text="No hi ha resultats per exportar.\nPrimer calcula un empaquetament a la pestanya 'Càlcul'.",
                                          foreground='gray')
        self.export_info_label.pack()
        
        # Opcions d'exportació
        self.export_options_frame = ttk.LabelFrame(main_frame, text="Opcions d'exportació", padding=15)
        self.export_options_frame.pack(fill='x', pady=(0, 15))
        
        # Visualització 3D
        ttk.Button(self.export_options_frame, text="Visualitzar en 3D", 
                  command=self.visualize_3d, state='disabled',
                  width=20).pack(pady=5)
        
        # Exportar imatges
        ttk.Button(self.export_options_frame, text="Exportar imatges (12 angles)", 
                  command=self.export_images, state='disabled',
                  width=20).pack(pady=5)
        
        # Exportar dades
        ttk.Button(self.export_options_frame, text="Exportar dades (JSON)", 
                  command=self.export_data, state='disabled',
                  width=20).pack(pady=5)
        
        # Amagar opcions inicialment
        self.export_options_frame.pack_forget()
    
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
                    text=f"{filename} ({size_mb:.1f} MB)",
                    foreground='black'
                )
                
                # Activar botó de simplificació si el fitxer és gran
                if size_mb > 5:  # Més de 5MB
                    self.simplify_button.config(state='normal')
                    self.stl_info_label.config(
                        text=f"{filename} ({size_mb:.1f} MB) - Recomanem accelerar el càlcul",
                        foreground='orange'
                    )
                else:
                    self.simplify_button.config(state='disabled')
                    
            except Exception as e:
                self.stl_info_label.config(
                    text=f"{os.path.basename(file_path)} (error llegint mida)",
                    foreground='red'
                )
    
    def simplify_stl(self):
        """Obre el simplificador STL simple i funcional"""
        if not self.selected_stl.get():
            messagebox.showerror("Error", "Primer selecciona un fitxer STL")
            return
        
        try:
            # Usar el simplificador sense emojis que funciona
            python_cmd = os.path.join("packassist_env", "Scripts", "python.exe")
            if not os.path.exists(python_cmd):
                python_cmd = "python"
            
            # Executar el mesh_simplifier_simple.py des de la nova ubicació
            simplifier_path = os.path.join("tools", "mesh_simplifiers", "mesh_simplifier_simple.py")
            subprocess.Popen([python_cmd, simplifier_path])
            
            messagebox.showinfo(
                "Optimitzador de models", 
                "S'ha obert l'optimitzador de models 3D.\n\n"
                "Després d'optimitzar, torna aquí i selecciona l'STL optimitzat."
            )
        
        except Exception as e:
            messagebox.showerror("Error", f"No s'ha pogut obrir l'optimitzador: {e}")
    
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
        self.result_label.config(text="Calculant quants objectes caben...", foreground='blue')
        
        # Actualitzar GUI
        self.root.update()
        
        try:
            # Simular càlcul (reemplaça amb la lògica real)
            self.simulate_calculation()
            
            # Crear resultats simulats
            self.create_mock_results()
            
            # Actualitzar interfície
            self.result_label.config(
                text=f"Càlcul completat!\n"
                     f"CABEN {self.calculated_objects} objectes en la caixa "
                     f"{self.box_width.get()}x{self.box_height.get()}x{self.box_depth.get()}mm",
                foreground='green'
            )
            
            # Activar pestanya d'exportació
            self.update_export_tab()
            
        except Exception as e:
            self.result_label.config(
                text=f"Error en el càlcul: {e}",
                foreground='red'
            )
        
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
            self.result_label.config(text=step, foreground='blue')
            self.progress_var.set((i + 1) * 20)
            self.root.update()
            time.sleep(0.5)  # Simular treball
    
    def create_mock_results(self):
        """Crea resultats simulats per a la demo"""
        import random
        
        # Simular càlcul de quants objectes caben
        # Basat en dimensions de la caixa i complexitat de l'objecte
        box_volume = self.box_width.get() * self.box_height.get() * self.box_depth.get()
        
        # Estimació simple: objectes més petits = més caben
        estimated_object_volume = min(15000, max(1000, box_volume * 0.1))  # Estimació
        max_objects = max(1, int(box_volume / estimated_object_volume * 0.6))  # Factor d'eficiència
        
        # Simulem que el càlcul troba un nombre òptim
        self.calculated_objects = random.randint(max(1, max_objects - 2), max_objects + 1)
        
        # Generar posicions aleatòries dels objectes que caben
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
        """Actualitza la pestanya d'exportació amb els resultats"""
        if self.results_data:
            # Actualitzar info
            info_text = f"Resultats calculats: {self.results_data['num_objects']} objectes\n"
            info_text += f"Caixa: {self.results_data['box_dimensions'][0]}x{self.results_data['box_dimensions'][1]}x{self.results_data['box_dimensions'][2]}mm\n"
            info_text += f"Eficiència: {self.results_data['efficiency']:.1f}%"
            
            self.export_info_label.config(text=info_text, foreground='black')
            
            # Mostrar opcions d'exportació
            self.export_options_frame.pack(fill='x', pady=(0, 15))
            
            # Activar botons
            for child in self.export_options_frame.winfo_children():
                if isinstance(child, ttk.Button):
                    child.config(state='normal')
    
    def visualize_3d(self):
        """Visualitza els resultats en 3D"""
        if not self.results_data:
            messagebox.showerror("Error", "No hi ha resultats per visualitzar")
            return
        
        try:
            # Crear visualitzador 3D simple
            self.create_3d_visualization()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en la visualització 3D: {e}")
    
    def create_3d_visualization(self):
        """Crea una finestra de visualització 3D"""
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
            
            # Dibuixar objectes com a esferes
            for obj in self.results_data['objects']:
                pos = obj['position']
                ax.scatter(pos[0], pos[1], pos[2], c='red', s=100, alpha=0.7)
                
                # Etiqueta
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
        except Exception as e:
            messagebox.showerror("Error", f"Error creant visualització: {e}")
    
    def export_images(self):
        """Exporta imatges des de diferents angles"""
        if not self.results_data:
            messagebox.showerror("Error", "No hi ha resultats per exportar")
            return
        
        # Seleccionar directori
        output_dir = filedialog.askdirectory(title="Selecciona directori per guardar les imatges")
        if not output_dir:
            return
        
        try:
            self.generate_multiple_view_images(output_dir)
            messagebox.showinfo("Èxit", f"Imatges exportades a:\n{output_dir}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error exportant imatges: {e}")
    
    def generate_multiple_view_images(self, output_dir):
        """Genera imatges des de 12 angles diferents"""
        try:
            import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d import Axes3D
            import numpy as np
            
            # Angles de vista (elevació, azimut)
            views = [
                (20, 0), (20, 30), (20, 60), (20, 90),
                (20, 120), (20, 150), (20, 180), (20, 210),
                (20, 240), (20, 270), (20, 300), (20, 330)
            ]
            
            for i, (elev, azim) in enumerate(views):
                fig = plt.figure(figsize=(10, 8))
                ax = fig.add_subplot(111, projection='3d')
                
                # Dibuixar caixa i objectes (mateix codi que visualize_3d)
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
                    ax.plot3D(points[:, 0], points[:, 1], points[:, 2], 'b-', alpha=0.8, linewidth=2)
                
                # Dibuixar objectes
                for obj in self.results_data['objects']:
                    pos = obj['position']
                    ax.scatter(pos[0], pos[1], pos[2], c='red', s=150, alpha=0.8)
                
                # Configurar vista
                ax.view_init(elev=elev, azim=azim)
                ax.set_xlabel('X (mm)')
                ax.set_ylabel('Y (mm)')
                ax.set_zlabel('Z (mm)')
                ax.set_title(f'Vista {i+1}: Empaquetament ({elev}°, {azim}°)')
                
                # Establir límits
                ax.set_xlim(0, box_dims[0])
                ax.set_ylim(0, box_dims[1])
                ax.set_zlim(0, box_dims[2])
                
                # Guardar imatge
                filename = f"empaquetament_vista_{i+1:02d}_{elev}_{azim}.png"
                filepath = os.path.join(output_dir, filename)
                plt.savefig(filepath, dpi=150, bbox_inches='tight')
                plt.close()
                
                print(f"Imatge guardada: {filename}")
            
        except ImportError:
            raise Exception("matplotlib no està instal·lat. Instal·la'l amb: pip install matplotlib")
    
    def export_data(self):
        """Exporta les dades en format JSON"""
        if not self.results_data:
            messagebox.showerror("Error", "No hi ha resultats per exportar")
            return
        
        # Seleccionar fitxer
        output_file = filedialog.asksaveasfilename(
            title="Guardar dades d'empaquetament",
            defaultextension=".json",
            filetypes=[
                ("Fitxers JSON", "*.json"),
                ("Tots els fitxers", "*.*")
            ]
        )
        
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(self.results_data, f, indent=2, ensure_ascii=False)
                
                messagebox.showinfo("Èxit", f"Dades exportades a:\n{output_file}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Error exportant dades: {e}")
    
    def run(self):
        """Executa l'aplicació"""
        self.root.mainloop()


def main():
    """Funció principal"""
    try:
        app = PackAssistApp()
        app.run()
    except Exception as e:
        print(f"Error iniciant aplicació: {e}")
        messagebox.showerror("Error", f"Error iniciant aplicació: {e}")


if __name__ == "__main__":
    main()
