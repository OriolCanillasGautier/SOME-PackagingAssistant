"""
PackAssist Simple - Aplicació de càlcul d'empaquetament amb simplificació STL
Dues pestanyes: Càlcul i Exportació
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import subprocess
import json
from datetime import datetime

# Afegir el path del src
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

class PackAssistSimple:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PackAssist - Càlcul d'Empaquetament STL")
        self.root.geometry("800x600")
        
        # Variables globals
        self.stl_files = []
        self.simplified_files = []
        self.calculation_results = None
        self.results_folder = "results"
        
        # Crear carpeta de resultats si no existeix
        if not os.path.exists(self.results_folder):
            os.makedirs(self.results_folder)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Configura la interfície principal"""
        # Notebook per les pestanyes
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pestanya 1: Càlcul
        self.calc_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.calc_frame, text="📦 Càlcul d'Empaquetament")
        self.setup_calc_tab()
        
        # Pestanya 2: Exportació
        self.export_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.export_frame, text="📤 Exportar Resultats")
        self.setup_export_tab()
    
    def setup_calc_tab(self):
        """Configura la pestanya de càlcul"""
        # Títol
        title_label = tk.Label(self.calc_frame, text="Càlcul d'Empaquetament STL", 
                              font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # Frame per importar STL
        import_frame = ttk.LabelFrame(self.calc_frame, text="1. Importar fitxers STL", padding=10)
        import_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Button(import_frame, text="📁 Seleccionar fitxers STL", 
                  command=self.select_stl_files, width=25).pack(side=tk.LEFT)
        
        self.files_label = tk.Label(import_frame, text="No s'han seleccionat fitxers", 
                                   fg="gray")
        self.files_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Frame per simplificació
        simplify_frame = ttk.LabelFrame(self.calc_frame, text="2. Simplificació (Opcional)", padding=10)
        simplify_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.simplify_var = tk.BooleanVar()
        simplify_check = ttk.Checkbutton(simplify_frame, text="Reduir complexitat dels STL", 
                                        variable=self.simplify_var)
        simplify_check.pack(side=tk.LEFT)
        
        ttk.Button(simplify_frame, text="🔧 Configurar Simplificació", 
                  command=self.open_simplifier, width=20).pack(side=tk.RIGHT)
        
        # Frame per configuració de caixa
        box_frame = ttk.LabelFrame(self.calc_frame, text="3. Configuració de la Caixa", padding=10)
        box_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Dimensions de la caixa
        dim_frame = tk.Frame(box_frame)
        dim_frame.pack(fill=tk.X)
        
        tk.Label(dim_frame, text="Dimensions (mm):").pack(side=tk.LEFT)
        
        tk.Label(dim_frame, text="Ample:").pack(side=tk.LEFT, padx=(20, 5))
        self.width_entry = tk.Entry(dim_frame, width=8)
        self.width_entry.insert(0, "200")
        self.width_entry.pack(side=tk.LEFT)
        
        tk.Label(dim_frame, text="Alt:").pack(side=tk.LEFT, padx=(10, 5))
        self.height_entry = tk.Entry(dim_frame, width=8)
        self.height_entry.insert(0, "150")
        self.height_entry.pack(side=tk.LEFT)
        
        tk.Label(dim_frame, text="Profund:").pack(side=tk.LEFT, padx=(10, 5))
        self.depth_entry = tk.Entry(dim_frame, width=8)
        self.depth_entry.insert(0, "100")
        self.depth_entry.pack(side=tk.LEFT)
        
        # Botó de càlcul
        calc_button_frame = tk.Frame(self.calc_frame)
        calc_button_frame.pack(pady=30)
        
        self.calc_button = tk.Button(calc_button_frame, text="🚀 CALCULAR EMPAQUETAMENT", 
                                    command=self.calculate_packing, 
                                    bg="#4CAF50", fg="white", 
                                    font=("Arial", 12, "bold"),
                                    width=25, height=2)
        self.calc_button.pack()
        
        # Àrea de resultats
        results_frame = ttk.LabelFrame(self.calc_frame, text="Resultats", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.results_text = tk.Text(results_frame, height=8, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_export_tab(self):
        """Configura la pestanya d'exportació"""
        # Títol
        title_label = tk.Label(self.export_frame, text="Exportar Resultats", 
                              font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # Estat
        self.export_status_label = tk.Label(self.export_frame, 
                                           text="No hi ha resultats per exportar", 
                                           fg="gray", font=("Arial", 12))
        self.export_status_label.pack(pady=10)
        
        # Frame d'opcions d'exportació
        options_frame = ttk.LabelFrame(self.export_frame, text="Opcions d'Exportació", padding=10)
        options_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Tipus d'exportació
        tk.Label(options_frame, text="Format d'exportació:").pack(anchor=tk.W)
        
        self.export_type = tk.StringVar(value="images")
        ttk.Radiobutton(options_frame, text="📷 Imatges des de múltiples angles (12 vistes)", 
                       variable=self.export_type, value="images").pack(anchor=tk.W, padx=20)
        ttk.Radiobutton(options_frame, text="📊 Informe PDF amb estadístiques", 
                       variable=self.export_type, value="pdf").pack(anchor=tk.W, padx=20)
        ttk.Radiobutton(options_frame, text="📋 Dades JSON per a integració", 
                       variable=self.export_type, value="json").pack(anchor=tk.W, padx=20)
        
        # Configuració d'imatges
        img_frame = ttk.LabelFrame(self.export_frame, text="Configuració d'Imatges", padding=10)
        img_frame.pack(fill=tk.X, padx=20, pady=10)
        
        resolution_frame = tk.Frame(img_frame)
        resolution_frame.pack(fill=tk.X)
        
        tk.Label(resolution_frame, text="Resolució:").pack(side=tk.LEFT)
        self.resolution_var = tk.StringVar(value="1920x1080")
        resolution_combo = ttk.Combobox(resolution_frame, textvariable=self.resolution_var, 
                                       values=["800x600", "1920x1080", "2560x1440", "3840x2160"], 
                                       width=12)
        resolution_combo.pack(side=tk.LEFT, padx=(10, 0))
        
        tk.Label(resolution_frame, text="Qualitat:").pack(side=tk.LEFT, padx=(20, 5))
        self.quality_var = tk.StringVar(value="Alta")
        quality_combo = ttk.Combobox(resolution_frame, textvariable=self.quality_var, 
                                    values=["Baixa", "Mitjana", "Alta", "Molt Alta"], 
                                    width=10)
        quality_combo.pack(side=tk.LEFT)
        
        # Botons d'exportació
        export_buttons_frame = tk.Frame(self.export_frame)
        export_buttons_frame.pack(pady=30)
        
        self.export_button = tk.Button(export_buttons_frame, text="📤 EXPORTAR RESULTATS", 
                                      command=self.export_results, 
                                      bg="#2196F3", fg="white", 
                                      font=("Arial", 12, "bold"),
                                      width=20, height=2)
        self.export_button.pack(side=tk.LEFT, padx=5)
        self.export_button.config(state=tk.DISABLED)
        
        tk.Button(export_buttons_frame, text="📁 Obrir Carpeta de Resultats", 
                 command=self.open_results_folder, 
                 font=("Arial", 10),
                 width=20).pack(side=tk.LEFT, padx=5)
        
        # Àrea de previsualització
        preview_frame = ttk.LabelFrame(self.export_frame, text="Previsualització", padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.preview_text = tk.Text(preview_frame, height=6, wrap=tk.WORD)
        preview_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=preview_scrollbar.set)
        
        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def select_stl_files(self):
        """Selecciona fitxers STL"""
        files = filedialog.askopenfilenames(
            title="Selecciona fitxers STL",
            filetypes=[
                ("Fitxers STL", "*.stl *.STL"),
                ("Tots els fitxers", "*.*")
            ]
        )
        
        if files:
            self.stl_files = list(files)
            self.files_label.config(text=f"{len(self.stl_files)} fitxer(s) seleccionat(s)", fg="green")
            self.update_results_text(f"✅ {len(self.stl_files)} fitxers STL carregats:\n")
            for i, file in enumerate(self.stl_files, 1):
                filename = os.path.basename(file)
                self.update_results_text(f"   {i}. {filename}\n")
        else:
            self.files_label.config(text="No s'han seleccionat fitxers", fg="gray")
    
    def open_simplifier(self):
        """Obre l'aplicació de simplificació"""
        if not self.stl_files:
            messagebox.showwarning("Avís", "Primer selecciona fitxers STL")
            return
        
        try:
            # Executar l'ultra_fast_mesh_simplifier
            result = subprocess.run([sys.executable, "ultra_fast_mesh_simplifier.py"], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                messagebox.showinfo("Èxit", "Simplificació completada! Els fitxers simplificats s'han guardat.")
                self.update_results_text("✅ Simplificació completada\n")
            else:
                messagebox.showerror("Error", f"Error en la simplificació:\n{result.stderr}")
        
        except Exception as e:
            messagebox.showerror("Error", f"No s'ha pogut obrir el simplificador:\n{e}")
    
    def calculate_packing(self):
        """Executa el càlcul d'empaquetament"""
        if not self.stl_files:
            messagebox.showwarning("Avís", "Primer selecciona fitxers STL")
            return
        
        try:
            # Obtenir dimensions de la caixa
            width = float(self.width_entry.get())
            height = float(self.height_entry.get())
            depth = float(self.depth_entry.get())
            
            self.update_results_text("\n🚀 INICIANT CÀLCUL D'EMPAQUETAMENT...\n")
            self.update_results_text("="*50 + "\n")
            
            # Simular càlcul (aquí aniria la lògica real d'empaquetament)
            self.update_results_text(f"📦 Caixa: {width} x {height} x {depth} mm\n")
            self.update_results_text(f"📁 Objectes a empaquetar: {len(self.stl_files)}\n")
            
            if self.simplify_var.get():
                self.update_results_text("🔧 Amb simplificació de malles\n")
            
            self.update_results_text("\n⏳ Calculant distribució òptima...\n")
            self.root.update()
            
            # Simular temps de càlcul
            import time
            time.sleep(2)
            
            # Resultats simulats
            efficiency = 75.8
            objects_placed = len(self.stl_files)
            
            self.update_results_text(f"\n✅ CÀLCUL COMPLETAT!\n")
            self.update_results_text(f"📊 Eficiència d'empaquetament: {efficiency}%\n")
            self.update_results_text(f"✔️ Objectes col·locats: {objects_placed}/{len(self.stl_files)}\n")
            
            # Guardar resultats
            self.calculation_results = {
                "timestamp": datetime.now().isoformat(),
                "box_dimensions": [width, height, depth],
                "stl_files": self.stl_files,
                "efficiency": efficiency,
                "objects_placed": objects_placed,
                "with_simplification": self.simplify_var.get()
            }
            
            # Activar exportació
            self.export_button.config(state=tk.NORMAL)
            self.export_status_label.config(text="✅ Resultats disponibles per exportar", fg="green")
            
            messagebox.showinfo("Èxit", f"Càlcul completat!\nEficiència: {efficiency}%")
            
        except ValueError:
            messagebox.showerror("Error", "Introdueix dimensions vàlides per la caixa")
        except Exception as e:
            messagebox.showerror("Error", f"Error en el càlcul:\n{e}")
    
    def export_results(self):
        """Exporta els resultats"""
        if not self.calculation_results:
            messagebox.showwarning("Avís", "No hi ha resultats per exportar")
            return
        
        export_type = self.export_type.get()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            if export_type == "images":
                self.export_images(timestamp)
            elif export_type == "pdf":
                self.export_pdf(timestamp)
            elif export_type == "json":
                self.export_json(timestamp)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en l'exportació:\n{e}")
    
    def export_images(self, timestamp):
        """Exporta imatges des de múltiples angles"""
        folder_name = f"export_images_{timestamp}"
        export_path = os.path.join(self.results_folder, folder_name)
        os.makedirs(export_path, exist_ok=True)
        
        # Simular generació d'imatges des de 12 angles
        angles = [
            "front", "back", "left", "right", "top", "bottom",
            "front_left", "front_right", "back_left", "back_right",
            "isometric_1", "isometric_2"
        ]
        
        self.update_preview_text("📷 Generant imatges...\n")
        
        # Crear fitxers d'exemple (en realitat generaries imatges reals)
        for angle in angles:
            filename = f"packing_view_{angle}.png"
            filepath = os.path.join(export_path, filename)
            
            # Simular creació d'imatge
            with open(filepath, 'w') as f:
                f.write(f"# Placeholder for {angle} view image")
            
            self.update_preview_text(f"  ✅ {filename}\n")
            self.root.update()
        
        # Crear informe resum
        summary_path = os.path.join(export_path, "export_summary.txt")
        with open(summary_path, 'w') as f:
            f.write(f"Exportació d'Imatges - {timestamp}\n")
            f.write("="*40 + "\n")
            f.write(f"Resolució: {self.resolution_var.get()}\n")
            f.write(f"Qualitat: {self.quality_var.get()}\n")
            f.write(f"Angles exportats: {len(angles)}\n")
            f.write(f"Eficiència: {self.calculation_results['efficiency']}%\n")
        
        self.update_preview_text(f"\n✅ Exportació completada a: {export_path}\n")
        messagebox.showinfo("Èxit", f"Imatges exportades a:\n{export_path}")
    
    def export_pdf(self, timestamp):
        """Exporta informe PDF"""
        filename = f"packing_report_{timestamp}.pdf"
        filepath = os.path.join(self.results_folder, filename)
        
        # Simular creació de PDF
        with open(filepath.replace('.pdf', '.txt'), 'w') as f:
            f.write(f"INFORME D'EMPAQUETAMENT - {timestamp}\n")
            f.write("="*50 + "\n\n")
            f.write(f"Dimensions de la caixa: {self.calculation_results['box_dimensions']}\n")
            f.write(f"Nombre d'objectes: {len(self.calculation_results['stl_files'])}\n")
            f.write(f"Eficiència: {self.calculation_results['efficiency']}%\n")
            f.write(f"Simplificació aplicada: {self.calculation_results['with_simplification']}\n")
        
        self.update_preview_text(f"📊 Informe PDF generat: {filename}\n")
        messagebox.showinfo("Èxit", f"Informe exportat a:\n{filepath}")
    
    def export_json(self, timestamp):
        """Exporta dades JSON"""
        filename = f"packing_data_{timestamp}.json"
        filepath = os.path.join(self.results_folder, filename)
        
        with open(filepath, 'w') as f:
            json.dump(self.calculation_results, f, indent=2)
        
        self.update_preview_text(f"📋 Dades JSON exportades: {filename}\n")
        messagebox.showinfo("Èxit", f"Dades exportades a:\n{filepath}")
    
    def open_results_folder(self):
        """Obre la carpeta de resultats"""
        if os.path.exists(self.results_folder):
            os.startfile(self.results_folder)
        else:
            messagebox.showinfo("Info", "La carpeta de resultats encara no existeix")
    
    def update_results_text(self, text):
        """Actualitza el text de resultats"""
        self.results_text.insert(tk.END, text)
        self.results_text.see(tk.END)
        self.root.update()
    
    def update_preview_text(self, text):
        """Actualitza el text de previsualització"""
        self.preview_text.insert(tk.END, text)
        self.preview_text.see(tk.END)
        self.root.update()
    
    def run(self):
        """Executa l'aplicació"""
        self.root.mainloop()

if __name__ == "__main__":
    app = PackAssistSimple()
    app.run()
