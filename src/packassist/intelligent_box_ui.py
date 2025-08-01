"""
Interfície d'usuari per al Generador Intel·ligent de Caixes
==========================================================

Proporciona una interfície gràfica intuïtiva per configurar i generar
caixes personalitzades amb el sistema intel·ligent.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
from typing import Optional, Callable, Any
import threading
from .intelligent_box_generator import (
    IntelligentBoxGenerator, 
    BoxGenerationResult,
    create_intelligent_box_for_object
)

class IntelligentBoxGeneratorUI:
    """
    Interfície gràfica per al generador intel·ligent de caixes.
    """
    
    def __init__(self, parent: tk.Widget, geometry_object: Any, callback: Optional[Callable] = None):
        """
        Inicialitza la interfície.
        
        Args:
            parent: Widget pare
            geometry_object: Objecte 3D per generar la caixa
            callback: Funció callback quan es generi la caixa
        """
        self.parent = parent
        self.geometry_object = geometry_object
        self.callback = callback
        self.result: Optional[BoxGenerationResult] = None
        self.is_generating = False
        
        # Crear finestra
        self.window = tk.Toplevel(parent)
        self.window.title("🎯 Generador Intel·ligent de Caixes")
        self.window.geometry("600x700")
        self.window.transient(parent)
        self.window.grab_set()
        
        # Configurar estils
        self.setup_styles()
        
        # Crear interfície
        self.create_interface()
        
    def setup_styles(self):
        """Configura els estils de la interfície."""
        style = ttk.Style()
        style.configure('Title.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Subtitle.TLabel', font=('Arial', 10, 'bold'))
        style.configure('Info.TLabel', font=('Arial', 9), foreground='#666666')
        
    def create_interface(self):
        """Crea tots els elements de la interfície."""
        # Frame principal amb scroll
        main_frame = ttk.Frame(self.window, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        row = 0
        
        # Títol
        title_label = ttk.Label(
            main_frame, 
            text="🎯 Generador Intel·ligent de Caixes Personalitzades",
            style='Title.TLabel'
        )
        title_label.grid(row=row, column=0, sticky=tk.W, pady=(0, 10))
        row += 1
        
        # Descripció
        desc_text = ("Crea una caixa personalitzada que s'adapti perfectament al teu objecte 3D. "
                    "Pots especificar el nombre de cares i la qualitat de l'ajust.")
        desc_label = ttk.Label(main_frame, text=desc_text, style='Info.TLabel', wraplength=550)
        desc_label.grid(row=row, column=0, sticky=tk.W, pady=(0, 20))
        row += 1
        
        # Configuració de cares
        faces_frame = ttk.LabelFrame(main_frame, text="⚙️ Configuració de Cares", padding="10")
        faces_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        faces_frame.columnconfigure(1, weight=1)
        row += 1
        
        # Nombre de cares
        ttk.Label(faces_frame, text="Nombre de cares:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.faces_var = tk.IntVar(value=6)
        faces_spinbox = ttk.Spinbox(
            faces_frame, 
            from_=4, 
            to=20, 
            textvariable=self.faces_var,
            width=10
        )
        faces_spinbox.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # Info sobre cares
        faces_info = ttk.Label(
            faces_frame, 
            text="• 6 cares: Caixa rectangular clàssica\n• 8-12 cares: Bona adaptació a formes complexes\n• 16+ cares: Adaptació molt precisa",
            style='Info.TLabel'
        )
        faces_info.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        # Configuració de qualitat
        quality_frame = ttk.LabelFrame(main_frame, text="🎨 Configuració de Qualitat", padding="10")
        quality_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        quality_frame.columnconfigure(1, weight=1)
        row += 1
        
        # Factor de qualitat
        ttk.Label(quality_frame, text="Factor de qualitat:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.quality_var = tk.DoubleVar(value=1.0)
        quality_scale = ttk.Scale(
            quality_frame,
            from_=0.1,
            to=2.0,
            variable=self.quality_var,
            orient=tk.HORIZONTAL
        )
        quality_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        self.quality_label = ttk.Label(quality_frame, text="1.0 (Equilibrat)")
        self.quality_label.grid(row=0, column=2, sticky=tk.W, padx=(10, 0), pady=5)
        
        # Bind per actualitzar etiqueta
        quality_scale.bind("<Motion>", self.update_quality_label)
        quality_scale.bind("<ButtonRelease-1>", self.update_quality_label)
        
        # Info sobre qualitat
        quality_info = ttk.Label(
            quality_frame,
            text="• Baix (0.1-0.5): Generació ràpida, menys precisió\n• Mitjà (0.6-1.4): Equilibri entre velocitat i qualitat\n• Alt (1.5-2.0): Màxima precisió, més lent",
            style='Info.TLabel'
        )
        quality_info.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
        
        # Opcions avançades
        advanced_frame = ttk.LabelFrame(main_frame, text="⚡ Opcions Avançades", padding="10")
        advanced_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        row += 1
        
        # Gestió de concavitats
        self.handle_concavities_var = tk.BooleanVar(value=True)
        concav_check = ttk.Checkbutton(
            advanced_frame,
            text="Gestionar concavitats automàticament",
            variable=self.handle_concavities_var
        )
        concav_check.grid(row=0, column=0, sticky=tk.W, pady=2)
        
        # Mode debug
        self.debug_mode_var = tk.BooleanVar(value=False)
        debug_check = ttk.Checkbutton(
            advanced_frame,
            text="Mode debug (mostrar informació detallada)",
            variable=self.debug_mode_var
        )
        debug_check.grid(row=1, column=0, sticky=tk.W, pady=2)
        
        # Informació de l'objecte
        object_frame = ttk.LabelFrame(main_frame, text="📊 Informació de l'Objecte", padding="10")
        object_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        object_frame.columnconfigure(1, weight=1)
        row += 1
        
        # Mostrar info de l'objecte
        self.create_object_info(object_frame)
        
        # Resultats
        self.results_frame = ttk.LabelFrame(main_frame, text="📈 Resultats", padding="10")
        self.results_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        self.results_frame.columnconfigure(0, weight=1)
        row += 1
        
        self.results_text = tk.Text(
            self.results_frame,
            height=8,
            wrap=tk.WORD,
            font=('Consolas', 9),
            state=tk.DISABLED
        )
        results_scroll = ttk.Scrollbar(self.results_frame, orient=tk.VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=results_scroll.set)
        
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        results_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Inicialitzar amb missatge
        self.update_results("🎯 Configura els paràmetres i prem 'Generar Caixa' per començar.")
        
        # Botons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(15, 0))
        button_frame.columnconfigure(1, weight=1)
        row += 1
        
        # Botó generar
        self.generate_button = ttk.Button(
            button_frame,
            text="🚀 Generar Caixa",
            command=self.generate_box
        )
        self.generate_button.grid(row=0, column=0, padx=(0, 10))
        
        # Barra de progrés
        self.progress = ttk.Progressbar(
            button_frame,
            mode='indeterminate'
        )
        self.progress.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # Botó aplicar/tancar
        self.apply_button = ttk.Button(
            button_frame,
            text="✅ Aplicar i Tancar",
            command=self.apply_and_close,
            state=tk.DISABLED
        )
        self.apply_button.grid(row=0, column=2, padx=(0, 10))
        
        # Botó tancar
        ttk.Button(
            button_frame,
            text="❌ Tancar",
            command=self.close
        ).grid(row=0, column=3)
        
    def create_object_info(self, parent):
        """Crea la secció d'informació de l'objecte."""
        try:
            # Intentar extreure informació de l'objecte
            info_text = "📦 Objecte carregat correctament\n"
            
            # Nombre de cares
            if hasattr(self.geometry_object, 'faces'):
                face_count = len(self.geometry_object.faces)
                info_text += f"🔹 Cares: {face_count:,}\n"
            
            # Nombre de vèrtexs
            if hasattr(self.geometry_object, 'vertices'):
                vertex_count = len(self.geometry_object.vertices)
                info_text += f"🔸 Vèrtexs: {vertex_count:,}\n"
            elif hasattr(self.geometry_object, 'Vertices'):
                vertex_count = len(list(self.geometry_object.Vertices()))
                info_text += f"🔸 Vèrtexs: {vertex_count:,}\n"
            
            # Volum estimat
            if hasattr(self.geometry_object, 'volume'):
                volume = self.geometry_object.volume
                info_text += f"📏 Volum: {volume:.2f} mm³\n"
            elif hasattr(self.geometry_object, 'Volume'):
                volume = self.geometry_object.Volume()
                info_text += f"📏 Volum: {volume:.2f} mm³\n"
            
            # Complexitat estimada
            complexity = self.estimate_complexity()
            info_text += f"🎯 Complexitat: {complexity}\n"
            
        except Exception as e:
            info_text = f"⚠️ Error llegint informació de l'objecte: {e}\n"
        
        info_label = ttk.Label(parent, text=info_text, style='Info.TLabel')
        info_label.grid(row=0, column=0, sticky=tk.W)
        
    def estimate_complexity(self) -> str:
        """Estima la complexitat de l'objecte."""
        try:
            if hasattr(self.geometry_object, 'faces'):
                face_count = len(self.geometry_object.faces)
            elif hasattr(self.geometry_object, 'Faces'):
                face_count = len(list(self.geometry_object.Faces()))
            else:
                return "Desconeguda"
            
            if face_count < 50:
                return "Baixa (objecte simple)"
            elif face_count < 500:
                return "Mitjana (detalls moderats)"
            elif face_count < 2000:
                return "Alta (molts detalls)"
            else:
                return "Molt Alta (geometria complexa)"
                
        except Exception:
            return "Desconeguda"
    
    def update_quality_label(self, event=None):
        """Actualitza l'etiqueta del factor de qualitat."""
        value = self.quality_var.get()
        if value < 0.6:
            text = f"{value:.1f} (Ràpid)"
        elif value < 1.4:
            text = f"{value:.1f} (Equilibrat)"
        else:
            text = f"{value:.1f} (Precís)"
        self.quality_label.config(text=text)
    
    def update_results(self, text: str):
        """Actualitza el text de resultats."""
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, text)
        self.results_text.config(state=tk.DISABLED)
        self.results_text.see(tk.END)
    
    def generate_box(self):
        """Genera la caixa personalitzada en un fil separat."""
        if self.is_generating:
            return
            
        self.is_generating = True
        self.generate_button.config(state=tk.DISABLED)
        self.apply_button.config(state=tk.DISABLED)
        self.progress.start()
        
        # Actualitzar resultats
        self.update_results("🔄 Generant caixa personalitzada...\n\n⏳ Aquest procés pot trigar uns segons segons la complexitat de l'objecte.")
        
        # Executar en fil separat
        thread = threading.Thread(target=self._generate_box_thread)
        thread.daemon = True
        thread.start()
    
    def _generate_box_thread(self):
        """Genera la caixa en un fil separat."""
        try:
            # Obtenir paràmetres
            target_faces = self.faces_var.get()
            quality_factor = self.quality_var.get()
            debug_mode = self.debug_mode_var.get()
            
            # Generar caixa
            self.result = create_intelligent_box_for_object(
                geometry_object=self.geometry_object,
                target_faces=target_faces,
                quality_factor=quality_factor,
                debug_mode=debug_mode
            )
            
            # Actualitzar interfície en el fil principal
            self.window.after(0, self._on_generation_complete)
            
        except Exception as e:
            # Actualitzar amb error en el fil principal
            self.window.after(0, lambda: self._on_generation_error(str(e)))
    
    def _on_generation_complete(self):
        """Callback quan la generació s'ha completat."""
        self.progress.stop()
        self.is_generating = False
        self.generate_button.config(state=tk.NORMAL)
        
        if self.result:
            # Mostrar resultats
            results_text = self._format_results(self.result)
            self.update_results(results_text)
            self.apply_button.config(state=tk.NORMAL)
            
            # Mostrar notificació d'èxit
            messagebox.showinfo(
                "Generació Completada",
                f"✅ Caixa generada amb èxit!\n\n"
                f"🔹 Cares: {self.result.face_count}\n"
                f"📏 Volum: {self.result.box_volume:.2f} mm³\n"
                f"📈 Eficiència: {self.result.efficiency:.1f}%"
            )
        else:
            self.update_results("❌ Error: No s'ha pogut generar la caixa. Prova amb diferents paràmetres.")
            messagebox.showerror("Error", "No s'ha pogut generar la caixa personalitzada.")
    
    def _on_generation_error(self, error_message: str):
        """Callback quan hi ha un error en la generació."""
        self.progress.stop()
        self.is_generating = False
        self.generate_button.config(state=tk.NORMAL)
        
        error_text = f"❌ ERROR EN LA GENERACIÓ\n\n{error_message}\n\n💡 Consells:\n• Prova amb menys cares\n• Redueix el factor de qualitat\n• Comprova que l'objecte sigui vàlid"
        self.update_results(error_text)
        
        messagebox.showerror("Error de Generació", f"Error generant la caixa:\n\n{error_message}")
    
    def _format_results(self, result: BoxGenerationResult) -> str:
        """Formata els resultats per mostrar."""
        text = "✅ CAIXA GENERADA AMB ÈXIT\n"
        text += "=" * 40 + "\n\n"
        
        text += "📊 ESTADÍSTIQUES:\n"
        text += f"🔹 Cares generades: {result.face_count}\n"
        text += f"🔸 Vèrtexs: {len(result.vertices)}\n"
        text += f"📏 Volum de la caixa: {result.box_volume:.2f} mm³\n"
        text += f"📦 Volum original: {result.original_volume:.2f} mm³\n"
        text += f"📈 Eficiència d'espai: {result.efficiency:.1f}%\n"
        text += f"📐 Àrea superficial: {result.surface_area:.2f} mm²\n\n"
        
        text += "🎯 QUALITAT DE L'AJUST:\n"
        if result.efficiency > 80:
            text += "🟢 Excel·lent - La caixa s'adapta molt bé a l'objecte\n"
        elif result.efficiency > 60:
            text += "🟡 Bona - Adaptació acceptable amb marge per millores\n"
        elif result.efficiency > 40:
            text += "🟠 Regular - Considera augmentar el nombre de cares\n"
        else:
            text += "🔴 Baixa - L'objecte té una forma molt complexa\n"
        
        text += "\n💡 CONSELLS PER MILLORAR:\n"
        if result.face_count < 8:
            text += "• Prova amb més cares per millor adaptació\n"
        if result.efficiency < 50:
            text += "• Augmenta el factor de qualitat\n"
            text += "• Activa la gestió de concavitats\n"
        
        text += "\n🚀 Prem 'Aplicar i Tancar' per usar aquesta caixa."
        
        return text
    
    def apply_and_close(self):
        """Aplica el resultat i tanca la finestra."""
        if self.result and self.callback:
            try:
                self.callback(self.result)
            except Exception as e:
                messagebox.showerror("Error", f"Error aplicant el resultat: {e}")
                return
        
        self.close()
    
    def close(self):
        """Tanca la finestra."""
        if self.is_generating:
            if messagebox.askyesno("Confirmació", "La generació està en curs. Vols cancel·lar-la?"):
                self.window.destroy()
        else:
            self.window.destroy()


def create_intelligent_box_dialog(
    parent: tk.Widget, 
    geometry_object: Any, 
    callback: Optional[Callable] = None
) -> IntelligentBoxGeneratorUI:
    """
    Crea i mostra el diàleg del generador intel·ligent de caixes.
    
    Args:
        parent: Widget pare
        geometry_object: Objecte 3D
        callback: Funció callback per quan es generi la caixa
        
    Returns:
        Instància de la interfície
    """
    return IntelligentBoxGeneratorUI(parent, geometry_object, callback)


# Test de la interfície
if __name__ == "__main__":
    # Test bàsic
    root = tk.Tk()
    root.withdraw()  # Amagar finestra principal
    
    # Objecte de prova
    class MockGeometry:
        def __init__(self):
            self.faces = list(range(100))  # 100 cares
            self.vertices = np.random.rand(200, 3) * 10  # 200 vèrtexs
            self.volume = 150.5
    
    test_object = MockGeometry()
    
    def test_callback(result):
        print(f"✅ Callback: Caixa amb {result.face_count} cares generada!")
    
    # Crear diàleg
    dialog = create_intelligent_box_dialog(root, test_object, test_callback)
    
    root.mainloop()
