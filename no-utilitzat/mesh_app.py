"""
Aplicació simplificada per la simplificació de malla 3D
Centrada només en la funcionalitat de simplificació adaptive de malla
"""

import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Afegir path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

class SimpleMeshApp:
    """Aplicació simple centrada en simplificació de malla"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PackAssist - Editor de Malla 3D")
        self.root.geometry("600x400")
        
        # Variables
        self.current_file_path = None
        
        # Configurar estils
        self.setup_styles()
        
        # Crear interfície
        self.create_interface()
    
    def setup_styles(self):
        """Configura estils moderns"""
        style = ttk.Style()
        
        # Usar tema modern
        available_themes = style.theme_names()
        if 'vista' in available_themes:
            style.theme_use('vista')
        elif 'clam' in available_themes:
            style.theme_use('clam')
        
        # Colors
        style.configure('Title.TLabel', font=('Segoe UI', 16, 'bold'))
        style.configure('Big.TButton', font=('Segoe UI', 12), padding=(20, 10))
    
    def create_interface(self):
        """Crea la interfície principal"""
        # Frame principal
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Títol
        ttk.Label(main_frame, 
                 text="Editor de Simplificació de Malla 3D", 
                 style='Title.TLabel').pack(pady=(0, 30))
        
        # Descripció
        desc_text = ("Carrega un fitxer STP/STEP o crea una malla de prova\n"
                    "per simplificar i optimitzar la geometria 3D")
        ttk.Label(main_frame, text=desc_text, 
                 font=('Segoe UI', 10), justify=tk.CENTER).pack(pady=(0, 40))
        
        # Botons principals
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(expand=True)
        
        # Botó per carregar STP
        ttk.Button(button_frame, 
                  text="Carregar Fitxer STP/STEP", 
                  command=self.load_stp_file,
                  style='Big.TButton').pack(pady=10, fill=tk.X)
        
        # Botó per malla de prova
        ttk.Button(button_frame, 
                  text="Crear Malla de Prova", 
                  command=self.create_test_mesh,
                  style='Big.TButton').pack(pady=10, fill=tk.X)
        
        # Separator
        ttk.Separator(button_frame, orient='horizontal').pack(fill=tk.X, pady=20)
        
        # Botó de demo directe
        ttk.Button(button_frame, 
                  text="Demo Ràpid", 
                  command=self.quick_demo,
                  style='Big.TButton').pack(pady=10, fill=tk.X)
        
        # Status bar
        self.status_var = tk.StringVar(value="Preparat per carregar malla")
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(status_frame, textvariable=self.status_var, 
                 relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X, padx=5, pady=2)
    
    def update_status(self, message):
        """Actualitza la barra d'estat"""
        self.status_var.set(message)
        self.root.update_idletasks()
    
    def load_stp_file(self):
        """Carrega un fitxer STP i obre l'editor"""
        try:
            file_path = filedialog.askopenfilename(
                title="Selecciona un fitxer STP/STEP",
                filetypes=[
                    ("Fitxers STEP/STP", "*.stp *.step *.STP *.STEP"),
                    ("Tots els fitxers", "*.*")
                ]
            )
            
            if not file_path:
                return
            
            self.current_file_path = file_path
            self.update_status(f"Carregant {os.path.basename(file_path)}...")
            
            # Carregar i obrir editor
            self.open_mesh_editor_with_file(file_path)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error carregant fitxer: {e}")
            self.update_status("Error carregant fitxer")
    
    def create_test_mesh(self):
        """Crea una malla de prova i obre l'editor"""
        try:
            self.update_status("Creant malla de prova...")
            
            # Crear malla de prova
            vertices, faces = self.generate_test_mesh()
            
            # Obrir editor amb malla de prova
            self.open_mesh_editor_with_mesh(vertices, faces)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error creant malla de prova: {e}")
            self.update_status("Error creant malla")
    
    def quick_demo(self):
        """Demo ràpid amb malla predefinida"""
        try:
            self.update_status("Iniciant demo ràpid...")
            
            # Importar sistema de test
            from test_mesh_simplification import test_adaptive_mesh_simplifier
            
            # Executar test que obre la interfície visual
            test_adaptive_mesh_simplifier()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en demo: {e}")
            self.update_status("Error en demo")
    
    def generate_test_mesh(self):
        """Genera una malla de prova complexa"""
        import numpy as np
        
        vertices = []
        faces = []
        
        # Crear esfera amb protuberàncies
        n_points = 60
        for i in range(n_points):
            theta = 2 * np.pi * i / n_points
            phi = np.pi * (i % 12) / 12
            
            # Radius amb variacions
            r = 50.0 + 15.0 * np.sin(4 * theta) + 8.0 * np.cos(6 * phi)
            
            x = r * np.sin(phi) * np.cos(theta)
            y = r * np.sin(phi) * np.sin(theta)
            z = r * np.cos(phi)
            
            vertices.append((x, y, z))
        
        # Crear cares triangulars
        n_vertices = len(vertices)
        for i in range(n_vertices - 2):
            if i % 2 == 0:  # Triangles alternats
                faces.append([0, i+1, i+2])
            
            # Connexions addicionals
            if i + 6 < n_vertices:
                faces.append([i, i+3, i+6])
        
        return vertices, faces
    
    def open_mesh_editor_with_file(self, file_path):
        """Obre l'editor de malla amb un fitxer STP"""
        try:
            # Importar sistema de simplificació
            from src.packassist.adaptive_mesh_simplifier import (
                AdaptiveMeshSimplifier, 
                MeshVisualizationWindow
            )
            from test_mesh_simplification import load_stp_mesh
            
            # Carregar malla del fitxer
            self.update_status("Convertint STP a malla...")
            vertices, faces = load_stp_mesh(file_path)
            
            if vertices is None or faces is None:
                raise Exception("No s'ha pogut carregar la geometria del fitxer")
            
            # Crear simplificador
            self.update_status("Inicialitzant editor...")
            simplifier = AdaptiveMeshSimplifier(vertices, faces)
            
            # Crear editor visual
            visualizer = MeshVisualizationWindow(simplifier)
            window = visualizer.create_window()
            
            self.update_status(f"Editor obert - {len(vertices)} vèrtexs carregats")
            
            # Executar editor
            window.mainloop()
            
        except Exception as e:
            raise Exception(f"Error obrint editor: {e}")
    
    def open_mesh_editor_with_mesh(self, vertices, faces):
        """Obre l'editor de malla amb dades de malla"""
        try:
            # Importar sistema de simplificació
            from src.packassist.adaptive_mesh_simplifier import (
                AdaptiveMeshSimplifier, 
                MeshVisualizationWindow
            )
            
            # Crear simplificador
            self.update_status("Inicialitzant editor...")
            simplifier = AdaptiveMeshSimplifier(vertices, faces)
            
            # Crear editor visual
            visualizer = MeshVisualizationWindow(simplifier)
            window = visualizer.create_window()
            
            self.update_status(f"Editor obert - {len(vertices)} vèrtexs")
            
            # Executar editor
            window.mainloop()
            
        except Exception as e:
            raise Exception(f"Error obrint editor: {e}")
    
    def run(self):
        """Executa l'aplicació"""
        try:
            # Verificar que el sistema de malla funciona
            self.update_status("Verificant sistema...")
            
            # Import de prova
            from src.packassist.adaptive_mesh_simplifier import AdaptiveMeshSimplifier
            self.update_status("Sistema de simplificació disponible")
            
            # Executar aplicació
            self.root.mainloop()
            
        except ImportError as e:
            messagebox.showerror("Error del Sistema", 
                               f"No es pot importar el sistema de simplificació:\n{e}")
        except Exception as e:
            messagebox.showerror("Error", f"Error iniciant aplicació: {e}")

def main():
    """Punt d'entrada principal"""
    print("Iniciant PackAssist - Editor de Malla 3D")
    
    try:
        app = SimpleMeshApp()
        app.run()
    except KeyboardInterrupt:
        print("\nAplicació tancada per l'usuari")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
