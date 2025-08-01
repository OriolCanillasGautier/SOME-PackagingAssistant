"""
Sistema de simplificació de malla STL RÀPID i EFICIENT
Utilitza biblioteques optimitzades per processar malles grans ràpidament
"""

import os
import sys
import time
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

def install_required_packages():
    """Instal·la les llibreries necessàries per simplificació ràpida"""
    import subprocess
    
    packages = [
        "pymeshlab",      # MeshLab per Python - molt ràpid
        "pyvista",        # Per fast-simplification 
        "trimesh",        # Alternativa lleugera
    ]
    
    for package in packages:
        try:
            __import__(package)
            print(f"✅ {package} ja està instal·lat")
        except ImportError:
            print(f"📦 Instal·lant {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"✅ {package} instal·lat correctament")
            except subprocess.CalledProcessError as e:
                print(f"❌ Error instal·lant {package}: {e}")

class FastMeshSimplifier:
    """Simplificador de malla ULTRA RÀPID"""
    
    def __init__(self):
        self.method = None
        self.available_methods = []
        self._detect_available_methods()
    
    def _detect_available_methods(self):
        """Detecta quines llibreries de simplificació estan disponibles"""
        
        # PyMeshLab - RECOMANAT (més ràpid)
        try:
            import pymeshlab
            self.available_methods.append("pymeshlab")
            print("✅ PyMeshLab disponible (RECOMANAT)")
        except ImportError:
            print("⚠️ PyMeshLab no disponible")
        
        # PyVista amb fast-simplification
        try:
            import pyvista as pv
            self.available_methods.append("pyvista")
            print("✅ PyVista disponible")
        except ImportError:
            print("⚠️ PyVista no disponible")
        
        # Trimesh - alternativa lleugera
        try:
            import trimesh
            self.available_methods.append("trimesh")
            print("✅ Trimesh disponible")
        except ImportError:
            print("⚠️ Trimesh no disponible")
        
        if not self.available_methods:
            print("❌ Cap mètode de simplificació ràpid disponible!")
            print("📦 Executant instal·lació automàtica...")
            install_required_packages()
            self._detect_available_methods()
        
        # Seleccionar millor mètode
        if "pymeshlab" in self.available_methods:
            self.method = "pymeshlab"
            print("🚀 Utilitzant PyMeshLab (més ràpid)")
        elif "pyvista" in self.available_methods:
            self.method = "pyvista"
            print("🚀 Utilitzant PyVista")
        elif "trimesh" in self.available_methods:
            self.method = "trimesh"
            print("🚀 Utilitzant Trimesh")
    
    def simplify_stl_file(self, input_path, target_vertices, output_path=None):
        """
        Simplifica un fitxer STL ràpidament
        
        Args:
            input_path: Camí al fitxer STL original
            target_vertices: Nombre objectiu de vèrtexs
            output_path: Camí per guardar el resultat (opcional)
        
        Returns:
            dict amb informació del resultat
        """
        start_time = time.time()
        
        print(f"🚀 Simplificant {os.path.basename(input_path)}")
        print(f"🎯 Objectiu: {target_vertices:,} vèrtexs")
        
        if self.method == "pymeshlab":
            return self._simplify_with_pymeshlab(input_path, target_vertices, output_path)
        elif self.method == "pyvista":
            return self._simplify_with_pyvista(input_path, target_vertices, output_path)
        elif self.method == "trimesh":
            return self._simplify_with_trimesh(input_path, target_vertices, output_path)
        else:
            raise RuntimeError("Cap mètode de simplificació disponible!")
    
    def _simplify_with_pymeshlab(self, input_path, target_vertices, output_path):
        """Simplificació ultra ràpida amb PyMeshLab"""
        import pymeshlab
        
        # Crear MeshSet
        ms = pymeshlab.MeshSet()
        
        # Carregar STL
        print("📁 Carregant STL...")
        ms.load_new_mesh(input_path)
        
        original_vertices = ms.current_mesh().vertex_number()
        original_faces = ms.current_mesh().face_number()
        
        print(f"📊 Original: {original_vertices:,} vèrtexs, {original_faces:,} cares")
        
        # Calcular percentatge de reducció
        reduction_ratio = target_vertices / original_vertices
        
        if reduction_ratio >= 1.0:
            print("⚠️ No cal simplificació (objectiu >= original)")
            return {
                'success': True,
                'original_vertices': original_vertices,
                'final_vertices': original_vertices,
                'reduction_ratio': 1.0,
                'time_seconds': 0,
                'method': 'pymeshlab',
                'output_path': output_path
            }
        
        print(f"🔄 Aplicant simplificació quadric edge collapse...")
        print(f"📉 Reducció: {reduction_ratio:.1%}")
        
        # Aplicar simplificació quadric edge collapse (MOLT RÀPID)
        ms.apply_filter('simplification_quadric_edge_collapse_decimation',
                       targetfacenum=int(target_vertices * 2),  # Aproximadament 2 cares per vèrtex
                       preservenormal=True,
                       preservetopology=True,
                       qualitythr=0.3,
                       preserveboundary=True)
        
        final_vertices = ms.current_mesh().vertex_number()
        final_faces = ms.current_mesh().face_number()
        
        print(f"✅ Simplificat: {final_vertices:,} vèrtexs, {final_faces:,} cares")
        
        # Guardar resultat
        if output_path:
            ms.save_current_mesh(output_path)
            print(f"💾 Guardat: {output_path}")
        
        elapsed = time.time() - start_time
        print(f"⏱️ Temps: {elapsed:.2f} segons")
        
        return {
            'success': True,
            'original_vertices': original_vertices,
            'final_vertices': final_vertices,
            'reduction_ratio': final_vertices / original_vertices,
            'time_seconds': elapsed,
            'method': 'pymeshlab',
            'output_path': output_path
        }
    
    def _simplify_with_pyvista(self, input_path, target_vertices, output_path):
        """Simplificació amb PyVista"""
        import pyvista as pv
        
        print("📁 Carregant STL amb PyVista...")
        mesh = pv.read(input_path)
        
        original_vertices = mesh.n_points
        print(f"📊 Original: {original_vertices:,} vèrtexs")
        
        # Calcular reducció
        reduction = 1.0 - (target_vertices / original_vertices)
        reduction = max(0.0, min(0.99, reduction))  # Limitar entre 0-99%
        
        print(f"🔄 Aplicant fast simplification...")
        print(f"📉 Reducció: {reduction:.1%}")
        
        # Aplicar simplificació
        simplified = mesh.decimate(reduction)
        
        final_vertices = simplified.n_points
        print(f"✅ Simplificat: {final_vertices:,} vèrtexs")
        
        # Guardar
        if output_path:
            simplified.save(output_path)
            print(f"💾 Guardat: {output_path}")
        
        elapsed = time.time() - start_time
        print(f"⏱️ Temps: {elapsed:.2f} segons")
        
        return {
            'success': True,
            'original_vertices': original_vertices,
            'final_vertices': final_vertices,
            'reduction_ratio': final_vertices / original_vertices,
            'time_seconds': elapsed,
            'method': 'pyvista',
            'output_path': output_path
        }
    
    def _simplify_with_trimesh(self, input_path, target_vertices, output_path):
        """Simplificació amb Trimesh"""
        import trimesh
        
        print("📁 Carregant STL amb Trimesh...")
        mesh = trimesh.load(input_path)
        
        original_vertices = len(mesh.vertices)
        print(f"📊 Original: {original_vertices:,} vèrtexs")
        
        print(f"🔄 Aplicant simplificació...")
        
        # Trimesh simplification
        simplified = mesh.simplify_quadric_decimation(target_vertices)
        
        final_vertices = len(simplified.vertices)
        print(f"✅ Simplificat: {final_vertices:,} vèrtexs")
        
        # Guardar
        if output_path:
            simplified.export(output_path)
            print(f"💾 Guardat: {output_path}")
        
        elapsed = time.time() - start_time
        print(f"⏱️ Temps: {elapsed:.2f} segons")
        
        return {
            'success': True,
            'original_vertices': original_vertices,
            'final_vertices': final_vertices,
            'reduction_ratio': final_vertices / original_vertices,
            'time_seconds': elapsed,
            'method': 'trimesh',
            'output_path': output_path
        }

class SimplificationGUI:
    """Interfície gràfica per simplificació ràpida"""
    
    def __init__(self):
        self.simplifier = FastMeshSimplifier()
        self.input_file = None
        self.setup_gui()
    
    def setup_gui(self):
        """Crear interfície"""
        self.root = tk.Tk()
        self.root.title("Simplificador STL RÀPID")
        self.root.geometry("600x500")
        
        # Arxiu d'entrada
        frame_input = ttk.Frame(self.root)
        frame_input.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(frame_input, text="Fitxer STL:").pack(anchor='w')
        
        frame_file = ttk.Frame(frame_input)
        frame_file.pack(fill='x')
        
        self.file_var = tk.StringVar()
        ttk.Entry(frame_file, textvariable=self.file_var, state='readonly').pack(side='left', fill='x', expand=True)
        ttk.Button(frame_file, text="Seleccionar", command=self.select_file).pack(side='right', padx=(5,0))
        
        # Opcions de simplificació
        frame_options = ttk.LabelFrame(self.root, text="Opcions de simplificació")
        frame_options.pack(fill='x', padx=10, pady=5)
        
        # Vèrtexs objectiu
        ttk.Label(frame_options, text="Vèrtexs objectiu:").pack(anchor='w')
        self.target_var = tk.StringVar(value="10000")
        ttk.Entry(frame_options, textvariable=self.target_var).pack(fill='x', pady=(0,5))
        
        # Botons ràpids
        frame_quick = ttk.Frame(frame_options)
        frame_quick.pack(fill='x')
        
        ttk.Button(frame_quick, text="10K", command=lambda: self.target_var.set("10000")).pack(side='left', padx=(0,5))
        ttk.Button(frame_quick, text="5K", command=lambda: self.target_var.set("5000")).pack(side='left', padx=(0,5))
        ttk.Button(frame_quick, text="1K", command=lambda: self.target_var.set("1000")).pack(side='left', padx=(0,5))
        ttk.Button(frame_quick, text="500", command=lambda: self.target_var.set("500")).pack(side='left')
        
        # Informació
        self.info_text = tk.Text(self.root, height=15, width=70)
        self.info_text.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.info_text)
        scrollbar.pack(side='right', fill='y')
        self.info_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.info_text.yview)
        
        # Botons d'acció
        frame_buttons = ttk.Frame(self.root)
        frame_buttons.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(frame_buttons, text="SIMPLIFICAR", command=self.simplify_mesh).pack(side='left', padx=(0,5))
        ttk.Button(frame_buttons, text="Netejar", command=self.clear_log).pack(side='left', padx=(0,5))
        ttk.Button(frame_buttons, text="Sortir", command=self.root.quit).pack(side='right')
        
        # Log inicial
        self.log("🚀 Simplificador STL RÀPID inicialitzat")
        self.log(f"📊 Mètodes disponibles: {', '.join(self.simplifier.available_methods)}")
        self.log(f"🎯 Mètode actiu: {self.simplifier.method}")
        self.log("")
        self.log("📝 Instruccions:")
        self.log("1. Selecciona un fitxer STL")
        self.log("2. Estableix el nombre objectiu de vèrtexs")
        self.log("3. Clica SIMPLIFICAR")
        self.log("4. El resultat es guardarà amb '_simplified' al nom")
    
    def log(self, message):
        """Afegir missatge al log"""
        self.info_text.insert(tk.END, message + "\n")
        self.info_text.see(tk.END)
        self.root.update()
    
    def clear_log(self):
        """Netejar log"""
        self.info_text.delete(1.0, tk.END)
    
    def select_file(self):
        """Seleccionar fitxer STL"""
        file_path = filedialog.askopenfilename(
            title="Selecciona fitxer STL",
            filetypes=[
                ("Fitxers STL", "*.stl *.STL"),
                ("Tots els fitxers", "*.*")
            ]
        )
        
        if file_path:
            self.input_file = file_path
            self.file_var.set(file_path)
            self.log(f"📁 Fitxer seleccionat: {os.path.basename(file_path)}")
            
            # Mostrar informació del fitxer
            try:
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                self.log(f"📊 Mida del fitxer: {size_mb:.1f} MB")
            except:
                pass
    
    def simplify_mesh(self):
        """Executar simplificació"""
        if not self.input_file:
            messagebox.showerror("Error", "Selecciona primer un fitxer STL!")
            return
        
        try:
            target_vertices = int(self.target_var.get())
            if target_vertices <= 0:
                raise ValueError("El nombre de vèrtexs ha de ser positiu")
        except ValueError as e:
            messagebox.showerror("Error", f"Nombre de vèrtexs invàlid: {e}")
            return
        
        # Generar nom de sortida
        base_name = os.path.splitext(self.input_file)[0]
        output_file = f"{base_name}_simplified_{target_vertices}v.stl"
        
        self.log("")
        self.log("🚀 INICIANT SIMPLIFICACIÓ...")
        self.log("="*50)
        
        try:
            # Executar simplificació
            result = self.simplifier.simplify_stl_file(
                self.input_file, 
                target_vertices, 
                output_file
            )
            
            if result['success']:
                self.log("")
                self.log("✅ SIMPLIFICACIÓ COMPLETADA!")
                self.log(f"📊 Vèrtexs: {result['original_vertices']:,} → {result['final_vertices']:,}")
                self.log(f"📉 Reducció: {(1-result['reduction_ratio']):.1%}")
                self.log(f"⏱️ Temps: {result['time_seconds']:.2f} segons")
                self.log(f"💾 Fitxer guardat: {os.path.basename(output_file)}")
                
                # Preguntar si obrir carpeta
                if messagebox.askyesno("Èxit", "Simplificació completada!\n\nVols obrir la carpeta amb el resultat?"):
                    import subprocess
                    subprocess.Popen(f'explorer /select,"{output_file}"')
            
            else:
                self.log("❌ Error en la simplificació")
                messagebox.showerror("Error", "Ha fallat la simplificació")
        
        except Exception as e:
            error_msg = f"❌ Error: {e}"
            self.log(error_msg)
            messagebox.showerror("Error", error_msg)
    
    def run(self):
        """Executar interfície"""
        self.root.mainloop()

def quick_simplify(input_path, target_vertices):
    """Simplificació ràpida des de línia de comandes"""
    print("🚀 SIMPLIFICACIÓ RÀPIDA STL")
    print("="*40)
    
    simplifier = FastMeshSimplifier()
    
    # Generar nom de sortida
    base_name = os.path.splitext(input_path)[0]
    output_path = f"{base_name}_simplified_{target_vertices}v.stl"
    
    result = simplifier.simplify_stl_file(input_path, target_vertices, output_path)
    
    if result['success']:
        print("\n✅ ÈXIT!")
        print(f"📁 Fitxer simplificat: {output_path}")
        return output_path
    else:
        print("\n❌ ERROR!")
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Línia de comandes
        input_file = sys.argv[1]
        target = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
        quick_simplify(input_file, target)
    else:
        # Interfície gràfica
        app = SimplificationGUI()
        app.run()
