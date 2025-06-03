#!/usr/bin/env python3
"""
PackAssist 3D - Optimitzador de 3D Bin Packing amb GUI moderna
Sistema integrat per l'optimització d'empaquetament 3D amb interfície gràfica.
"""
import csv
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from src.packassist import get_stp_dimensions, validate_stp_file, optimize_packing, calculate_theoretical_max

# Constants
CSV_PATH = "data/index.csv"
ICON_SIZE = 16

class PackAssistGUI:
    """Interfície gràfica principal per PackAssist 3D."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("PackAssist 3D - Optimitzador de Bin Packing")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Variables de control
        self.is_processing = False
        self.metadata = []
        
        # Configurar estil modern
        self.setup_styles()
        
        # Crear interfície
        self.create_widgets()
        
        # Carregar dades inicials
        self.load_initial_data()
    
    def setup_styles(self):
        """Configura estils moderns per la interfície."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Colors moderns
        bg_color = "#f5f5f5"
        accent_color = "#2196F3"
        success_color = "#4CAF50"
        warning_color = "#FF9800"
        error_color = "#F44336"
        
        # Configurar estils personalitzats
        style.configure('Title.TLabel', font=('Arial', 14, 'bold'))
        style.configure('Header.TLabel', font=('Arial', 11, 'bold'))
        style.configure('Success.TLabel', foreground=success_color)
        style.configure('Warning.TLabel', foreground=warning_color)
        style.configure('Error.TLabel', foreground=error_color)
        
        self.root.configure(bg=bg_color)
    
    def create_widgets(self):
        """Crea tots els widgets de la interfície."""
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurar redimensionament
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Títol
        title_label = ttk.Label(main_frame, text="🎯 PackAssist 3D", style='Title.TLabel')
        title_label.grid(row=0, column=0, pady=(0, 10))
        
        # Notebook per pestanyes
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Crear pestanyes
        self.create_stp_tab()
        self.create_manual_tab()
        self.create_results_tab()
        
        # Barra d'estat
        self.create_status_bar(main_frame)
    
    def create_stp_tab(self):
        """Crea la pestanya de fitxers STP."""
        stp_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(stp_frame, text="📁 Fitxers STP")
        
        # Configurar grid
        stp_frame.columnconfigure(0, weight=1)
        stp_frame.rowconfigure(2, weight=1)
        
        # Gestió de fitxers
        file_frame = ttk.LabelFrame(stp_frame, text="Gestió de fitxers", padding="10")
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        
        ttk.Button(file_frame, text="📂 Carregar CSV", 
                  command=self.load_csv_file).grid(row=0, column=0, padx=(0, 5))
        
        self.csv_path_var = tk.StringVar(value=CSV_PATH)
        ttk.Entry(file_frame, textvariable=self.csv_path_var, state='readonly').grid(
            row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        
        ttk.Button(file_frame, text="🔄 Recarregar", 
                  command=self.reload_metadata).grid(row=0, column=2, padx=(5, 0))
        
        # Control de processat
        control_frame = ttk.LabelFrame(stp_frame, text="Control de processat", padding="10")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(control_frame, text="▶️ Processar Tot", 
                  command=self.process_all_files).grid(row=0, column=0, padx=(0, 10))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(control_frame, variable=self.progress_var, 
                                          maximum=100, length=200)
        self.progress_bar.grid(row=0, column=1, padx=(10, 10))
        
        ttk.Button(control_frame, text="⏹️ Aturar", 
                  command=self.stop_processing).grid(row=0, column=2, padx=(10, 0))
        
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
        
        # Scrollbar per la taula
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        
        self.file_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    def create_manual_tab(self):
        """Crea la pestanya d'entrada manual."""
        manual_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(manual_frame, text="🔢 Entrada Manual")
        
        # Configurar grid
        manual_frame.columnconfigure(0, weight=1)
        manual_frame.columnconfigure(1, weight=1)
        
        # Dimensions del contenidor
        box_frame = ttk.LabelFrame(manual_frame, text="📦 Dimensions del contenidor (mm)", padding="10")
        box_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 5), pady=(0, 10))
        
        ttk.Label(box_frame, text="Longitud:").grid(row=0, column=0, sticky=tk.W)
        self.box_length_var = tk.DoubleVar(value=1000.0)
        ttk.Entry(box_frame, textvariable=self.box_length_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        ttk.Label(box_frame, text="Amplada:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.box_width_var = tk.DoubleVar(value=800.0)
        ttk.Entry(box_frame, textvariable=self.box_width_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))
        
        ttk.Label(box_frame, text="Altura:").grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
        self.box_height_var = tk.DoubleVar(value=600.0)
        ttk.Entry(box_frame, textvariable=self.box_height_var).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))
        
        box_frame.columnconfigure(1, weight=1)
        
        # Dimensions de l'objecte
        obj_frame = ttk.LabelFrame(manual_frame, text="📋 Dimensions de l'objecte (mm)", padding="10")
        obj_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), padx=(5, 0), pady=(0, 10))
        
        ttk.Label(obj_frame, text="Longitud:").grid(row=0, column=0, sticky=tk.W)
        self.obj_length_var = tk.DoubleVar(value=200.0)
        ttk.Entry(obj_frame, textvariable=self.obj_length_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        ttk.Label(obj_frame, text="Amplada:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.obj_width_var = tk.DoubleVar(value=150.0)
        ttk.Entry(obj_frame, textvariable=self.obj_width_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))
        
        ttk.Label(obj_frame, text="Altura:").grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
        self.obj_height_var = tk.DoubleVar(value=100.0)
        ttk.Entry(obj_frame, textvariable=self.obj_height_var).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))
        
        obj_frame.columnconfigure(1, weight=1)
        
        # Botó de càlcul
        calc_frame = ttk.Frame(manual_frame)
        calc_frame.grid(row=1, column=0, columnspan=2, pady=10)
        
        ttk.Button(calc_frame, text="🧮 Calcular Empaquetament", 
                  command=self.calculate_manual).grid(row=0, column=0)
        
        # Resultats
        results_frame = ttk.LabelFrame(manual_frame, text="📊 Resultats", padding="10")
        results_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        self.manual_results = tk.Text(results_frame, height=15, wrap=tk.WORD)
        manual_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.manual_results.yview)
        self.manual_results.configure(yscrollcommand=manual_scrollbar.set)
        
        self.manual_results.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        manual_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    def create_results_tab(self):
        """Crea la pestanya de resultats."""
        results_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(results_frame, text="📊 Resultats")
        
        # Configurar grid
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(1, weight=1)
        
        # Controls
        controls_frame = ttk.Frame(results_frame)
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(controls_frame, text="💾 Exportar Resultats", 
                  command=self.export_results).grid(row=0, column=0, padx=(0, 10))
        
        ttk.Button(controls_frame, text="🗑️ Netejar Resultats", 
                  command=self.clear_results).grid(row=0, column=1)
        
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
    
    def create_status_bar(self, parent):
        """Crea la barra d'estat."""
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        status_frame.columnconfigure(0, weight=1)
        
        self.status_var = tk.StringVar(value="Llest")
        status_label = ttk.Label(status_frame, textvariable=self.status_var)
        status_label.grid(row=0, column=0, sticky=tk.W)
        
        # Informació del sistema
        info_label = ttk.Label(status_frame, text=f"Python {sys.version.split()[0]} | PackAssist 3D v1.0")
        info_label.grid(row=0, column=1, sticky=tk.E)
    
    def load_initial_data(self):
        """Carrega les dades inicials."""
        self.update_status("Carregant dades inicials...")
        self.reload_metadata()
    
    def update_status(self, message):
        """Actualitza la barra d'estat."""
        self.status_var.set(message)
        self.root.update_idletasks()
    
    def load_csv_file(self):
        """Carrega un fitxer CSV."""
        filename = filedialog.askopenfilename(
            title="Selecciona fitxer CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=os.path.dirname(CSV_PATH)
        )
        
        if filename:
            self.csv_path_var.set(filename)
            self.reload_metadata()
    
    def reload_metadata(self):
        """Recarrega les metadades del CSV."""
        csv_path = self.csv_path_var.get()
        
        try:
            if not os.path.exists(csv_path):
                self.create_sample_data()
                return
            
            with open(csv_path, "r", encoding='utf-8') as f:
                self.metadata = list(csv.DictReader(f))
            
            self.update_file_tree()
            self.update_status(f"Carregades {len(self.metadata)} entrades del CSV")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error carregant metadades: {e}")
            self.update_status("Error carregant dades")
    
    def update_file_tree(self):
        """Actualitza la taula de fitxers."""
        # Netejar taula
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        # Afegir entrades
        for entry in self.metadata:
            file_path = entry.get("file_path", "")
            status = "✅ Vàlid" if validate_stp_file(file_path) else "❌ No vàlid"
            
            self.file_tree.insert("", tk.END, values=(
                entry.get("type", ""),
                entry.get("name", ""),
                file_path,
                status
            ))
    
    def create_sample_data(self):
        """Crea dades de mostra."""
        try:
            # Crear directoris
            os.makedirs("boxes", exist_ok=True)
            os.makedirs("objects", exist_ok=True)
            os.makedirs("data", exist_ok=True)
            
            # Crear CSV de mostra
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
            
            messagebox.showinfo("Dades de mostra", 
                              "S'han creat dades de mostra.\n"
                              "Afegeix els teus fitxers STP als directoris 'boxes' i 'objects'.")
            
            self.update_status("Dades de mostra creades")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error creant dades de mostra: {e}")
    
    def process_all_files(self):
        """Processa tots els fitxers STP."""
        if self.is_processing:
            return
        
        if not self.metadata:
            messagebox.showwarning("Avís", "No hi ha fitxers per processar")
            return
        
        # Filtrar entrades vàlides
        valid_metadata = []
        for entry in self.metadata:
            if entry.get("type") in ["box", "object"] and validate_stp_file(entry.get("file_path", "")):
                valid_metadata.append(entry)
        
        if not valid_metadata:
            messagebox.showwarning("Avís", "No hi ha fitxers vàlids per processar")
            return
        
        boxes = [m for m in valid_metadata if m["type"] == "box"]
        objects = [m for m in valid_metadata if m["type"] == "object"]
        
        if not boxes or not objects:
            messagebox.showwarning("Avís", "Es necessiten caixes i objectes per processar")
            return
        
        # Executar processat en fil separat
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
                
                box_dims = get_stp_dimensions(box_info["file_path"])
                if not box_dims:
                    continue
                
                self.results_text.insert(tk.END, f"📦 Contenidor: {box_info['name']}\n")
                self.results_text.insert(tk.END, f"   Dimensions: {box_dims}\n\n")
                
                for obj_info in objects:
                    if not self.is_processing:
                        break
                    
                    current += 1
                    progress = (current / total_combinations) * 100
                    self.progress_var.set(progress)
                    
                    self.update_status(f"Processant {current}/{total_combinations}: {box_info['name']} + {obj_info['name']}")
                    
                    obj_dims = get_stp_dimensions(obj_info["file_path"])
                    if not obj_dims:
                        continue
                    
                    theoretical_max = calculate_theoretical_max(box_dims, obj_dims)
                    result = optimize_packing(box_dims, obj_dims)
                    
                    self.results_text.insert(tk.END, f"  ➕ Objecte: {obj_info['name']}\n")
                    self.results_text.insert(tk.END, f"     📏 Dimensions: {obj_dims}\n")
                    
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
    
    def calculate_manual(self):
        """Calcula l'empaquetament manual."""
        try:
            # Obtenir dimensions
            box_dims = {
                "length": self.box_length_var.get(),
                "width": self.box_width_var.get(),
                "height": self.box_height_var.get()
            }
            
            obj_dims = {
                "length": self.obj_length_var.get(),
                "width": self.obj_width_var.get(),
                "height": self.obj_height_var.get()
            }
            
            # Validar dimensions
            if any(v <= 0 for v in box_dims.values()) or any(v <= 0 for v in obj_dims.values()):
                messagebox.showerror("Error", "Totes les dimensions han de ser positives")
                return
            
            # Calcular
            self.manual_results.delete(1.0, tk.END)
            self.manual_results.insert(tk.END, "🧮 CÀLCUL D'EMPAQUETAMENT MANUAL\n")
            self.manual_results.insert(tk.END, "=" * 40 + "\n\n")
            
            self.manual_results.insert(tk.END, f"📦 Contenidor:\n")
            self.manual_results.insert(tk.END, f"   Longitud: {box_dims['length']:.1f} mm\n")
            self.manual_results.insert(tk.END, f"   Amplada: {box_dims['width']:.1f} mm\n")
            self.manual_results.insert(tk.END, f"   Altura: {box_dims['height']:.1f} mm\n\n")
            
            self.manual_results.insert(tk.END, f"📋 Objecte:\n")
            self.manual_results.insert(tk.END, f"   Longitud: {obj_dims['length']:.1f} mm\n")
            self.manual_results.insert(tk.END, f"   Amplada: {obj_dims['width']:.1f} mm\n")
            self.manual_results.insert(tk.END, f"   Altura: {obj_dims['height']:.1f} mm\n\n")
            
            theoretical_max = calculate_theoretical_max(box_dims, obj_dims)
            result = optimize_packing(box_dims, obj_dims)
            
            self.manual_results.insert(tk.END, "📊 RESULTATS:\n")
            self.manual_results.insert(tk.END, f"   ➕ Màxim teòric (per volum): {theoretical_max} unitats\n")
            
            if result["error"]:
                self.manual_results.insert(tk.END, f"   ❌ Error: {result['error']}\n")
            else:
                self.manual_results.insert(tk.END, f"   ✅ Màxim real (3D packing): {result['max_objects']} unitats\n")
                self.manual_results.insert(tk.END, f"   📈 Eficiència d'espai: {result['efficiency']:.1f}%\n")
                self.manual_results.insert(tk.END, f"   📏 Volum contenidor: {result['box_volume']:.0f} mm³\n")
                self.manual_results.insert(tk.END, f"   📦 Volum utilitzat: {result['used_volume']:.0f} mm³\n")
            
            self.update_status("Càlcul manual completat")
            
        except ValueError:
            messagebox.showerror("Error", "Introdueix valors numèrics vàlids")
        except Exception as e:
            messagebox.showerror("Error", f"Error durant el càlcul: {e}")
    
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


def main():
    """Funció principal."""
    # Verificar dependències
    try:
        from src.packassist import get_stp_dimensions, validate_stp_file, optimize_packing, calculate_theoretical_max
    except ImportError as e:
        print(f"❌ Error important mòduls: {e}")
        print("Assegura't que els mòduls de packassist estiguin disponibles")
        return
    
    # Crear i executar interfície
    root = tk.Tk()
    app = PackAssistGUI(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n👋 Sortint...")
        root.quit()


if __name__ == "__main__":
    main()
