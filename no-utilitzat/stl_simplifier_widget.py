"""
Widget de simplificació STL integrat per PackAssist
Versió simplificada només amb funcionalitat essencial
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
import time

class STLSimplifierWidget:
    """Widget simple per simplificar fitxers STL"""
    
    def __init__(self, parent_frame):
        """Inicialitza el widget"""
        self.parent = parent_frame
        self.current_file = None
        self.processing = False
        
        # Variables
        self.file_var = tk.StringVar(value="No s'ha seleccionat cap fitxer")
        self.target_vertices_var = tk.StringVar(value="1000")
        self.status_var = tk.StringVar(value="Preparat")
        
        self._create_ui()
    
    def _create_ui(self):
        """Crea la interfície del widget"""
        # Frame principal
        main_frame = ttk.LabelFrame(self.parent, text="🔧 Simplificador STL Ultra-Ràpid", padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Selecció de fitxer
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(file_frame, text="Fitxer STL:").pack(anchor=tk.W)
        
        file_entry_frame = ttk.Frame(file_frame)
        file_entry_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Entry(file_entry_frame, textvariable=self.file_var, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(file_entry_frame, text="📂 Seleccionar", command=self._select_file).pack(side=tk.RIGHT)
        
        # Configuració
        config_frame = ttk.Frame(main_frame)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(config_frame, text="Vèrtexs objectiu:").pack(anchor=tk.W)
        
        target_frame = ttk.Frame(config_frame)
        target_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Entry(target_frame, textvariable=self.target_vertices_var, width=10).pack(side=tk.LEFT)
        ttk.Label(target_frame, text="(recomanat: 500-2000 per càlculs ràpids)").pack(side=tk.LEFT, padx=(10, 0))
        
        # Botó de simplificació
        ttk.Button(main_frame, text="⚡ SIMPLIFICAR STL", command=self._simplify_stl, style='Accent.TButton').pack(pady=10)
        
        # Estat
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X)
        
        ttk.Label(status_frame, text="Estat:").pack(anchor=tk.W)
        ttk.Label(status_frame, textvariable=self.status_var, foreground='blue').pack(anchor=tk.W, pady=(5, 0))
        
        # Informació
        info_frame = ttk.LabelFrame(main_frame, text="ℹ️ Informació", padding="10")
        info_frame.pack(fill=tk.X, pady=(10, 0))
        
        info_text = """• Redueix la complexitat de fitxers STL massivament
• Típic: 100,000+ vèrtexs → 500-2000 vèrtexs en segons
• El fitxer simplificat es guarda amb '_simplified' al nom
• Perfecte per fer càlculs d'empaquetament més ràpids"""
        
        ttk.Label(info_frame, text=info_text, wraplength=500, justify=tk.LEFT).pack()
    
    def _select_file(self):
        """Selecciona un fitxer STL"""
        file_path = filedialog.askopenfilename(
            title="Selecciona un fitxer STL",
            filetypes=[
                ("Fitxers STL", "*.stl *.STL"),
                ("Tots els fitxers", "*.*")
            ]
        )
        
        if file_path:
            self.current_file = file_path
            filename = os.path.basename(file_path)
            
            # Mostrar informació del fitxer
            try:
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                self.file_var.set(f"{filename} ({size_mb:.1f} MB)")
                self.status_var.set("Fitxer carregat, preparat per simplificar")
            except:
                self.file_var.set(filename)
                self.status_var.set("Fitxer seleccionat")
    
    def _simplify_stl(self):
        """Simplifica el fitxer STL seleccionat"""
        if not self.current_file:
            messagebox.showwarning("Atenció", "Selecciona primer un fitxer STL")
            return
        
        if self.processing:
            messagebox.showinfo("Informació", "Ja hi ha una simplificació en procés")
            return
        
        try:
            target_vertices = int(self.target_vertices_var.get())
            if target_vertices < 50 or target_vertices > 50000:
                messagebox.showwarning("Atenció", "El nombre de vèrtexs ha d'estar entre 50 i 50000")
                return
        except ValueError:
            messagebox.showerror("Error", "Introdueix un nombre vàlid de vèrtexs")
            return
        
        # Executar simplificació en thread separat
        thread = threading.Thread(target=self._run_simplification, args=(target_vertices,))
        thread.daemon = True
        thread.start()
    
    def _run_simplification(self, target_vertices):
        """Executa la simplificació en background"""
        self.processing = True
        
        try:
            self.status_var.set("🔄 Simplificant... això pot trigar uns segons")
            
            # Importar el simplificador
            from ultra_fast_mesh_simplifier import FastMeshSimplifier
            
            # Crear simplificador
            simplifier = FastMeshSimplifier()
            
            # Executar simplificació
            result = simplifier.simplify_file(self.current_file, target_vertices)
            
            if result:
                output_file = result.get('output_file', 'fitxer simplificat')
                original_vertices = result.get('original_vertices', 0)
                final_vertices = result.get('final_vertices', 0)
                processing_time = result.get('processing_time', 0)
                
                self.status_var.set(f"✅ Completat! {original_vertices:,} → {final_vertices:,} vèrtexs en {processing_time:.1f}s")
                
                # Mostrar diàleg de èxit
                messagebox.showinfo(
                    "Simplificació Completada",
                    f"✅ STL simplificat correctament!\n\n"
                    f"📊 Original: {original_vertices:,} vèrtexs\n"
                    f"📉 Simplificat: {final_vertices:,} vèrtexs\n"
                    f"⏱️ Temps: {processing_time:.1f} segons\n"
                    f"💾 Guardat: {os.path.basename(output_file)}"
                )
            else:
                self.status_var.set("❌ Error en la simplificació")
                messagebox.showerror("Error", "No s'ha pogut simplificar el fitxer STL")
                
        except ImportError:
            self.status_var.set("❌ Mòdul simplificador no disponible")
            messagebox.showerror(
                "Error", 
                "No s'ha trobat el mòdul 'ultra_fast_mesh_simplifier'.\n"
                "Assegura't que està instal·lat correctament."
            )
        except Exception as e:
            self.status_var.set(f"❌ Error: {str(e)}")
            messagebox.showerror("Error", f"Error durant la simplificació:\n{str(e)}")
        finally:
            self.processing = False


def create_stl_simplifier_tab(notebook):
    """Crea una pestanya amb el simplificador STL"""
    # Crear frame per la pestanya
    stl_frame = ttk.Frame(notebook, padding="10")
    notebook.add(stl_frame, text="⚡ Simplificador STL")
    
    # Crear widget simplificador
    simplifier_widget = STLSimplifierWidget(stl_frame)
    
    return stl_frame, simplifier_widget


if __name__ == "__main__":
    # Test del widget
    root = tk.Tk()
    root.title("Test STL Simplifier Widget")
    root.geometry("600x500")
    
    # Crear notebook de prova
    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Afegir pestanya simplificador
    create_stl_simplifier_tab(notebook)
    
    root.mainloop()
