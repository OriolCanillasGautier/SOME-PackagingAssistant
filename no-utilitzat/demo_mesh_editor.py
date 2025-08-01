"""
Demo de l'Editor Visual de Simplificació de Malla
Obre l'interfície gràfica per simplificar geometries complexes
"""

import sys
import os
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Afegir path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def create_complex_test_object():
    """Crea un objecte de prova més complex amb molts vèrtexs"""
    print("🔨 Generant objecte complex de prova...")
    
    vertices = []
    faces = []
    
    # Crear una superfície ondulada complexa
    resolution = 20  # Augmentar per més complexitat
    
    for i in range(resolution):
        for j in range(resolution):
            # Coordenades base
            x = (i / resolution) * 100 - 50
            y = (j / resolution) * 100 - 50
            
            # Superfície ondulada complexa
            z1 = 10 * np.sin(0.3 * x) * np.cos(0.3 * y)
            z2 = 5 * np.sin(0.1 * (x*x + y*y))
            z3 = 3 * np.cos(0.5 * x) * np.sin(0.5 * y)
            z = z1 + z2 + z3
            
            vertices.append((x, y, z))
            
            # Afegir capa inferior
            vertices.append((x, y, z - 20))
    
    # Crear cares triangulars per connectar la superfície
    n = resolution
    vertex_idx = 0
    
    for i in range(resolution - 1):
        for j in range(resolution - 1):
            # Índexs dels vèrtexs del quadrat actual
            tl = i * n + j  # top-left
            tr = i * n + (j + 1)  # top-right
            bl = (i + 1) * n + j  # bottom-left
            br = (i + 1) * n + (j + 1)  # bottom-right
            
            # Dos triangles per quadrat (superfície superior)
            faces.append([tl, tr, bl])
            faces.append([tr, br, bl])
            
            # Superfície inferior (amb offset)
            offset = len(vertices) // 2
            faces.append([tl + offset, bl + offset, tr + offset])
            faces.append([tr + offset, bl + offset, br + offset])
    
    print(f"   📊 Objecte generat: {len(vertices)} vèrtexs, {len(faces)} cares")
    return vertices, faces


def open_mesh_editor_demo():
    """Obre l'editor de malla amb un objecte de prova"""
    try:
        from src.packassist.adaptive_mesh_simplifier import (
            AdaptiveMeshSimplifier, 
            MeshVisualizationWindow
        )
        
        print("🔧 Creant objecte de prova...")
        vertices, faces = create_complex_test_object()
        
        print("🚀 Inicialitzant editor de malla...")
        simplifier = AdaptiveMeshSimplifier(vertices, faces)
        
        print("🎮 Obrint interfície visual...")
        visualizer = MeshVisualizationWindow(simplifier)
        window = visualizer.create_window()
        
        # Afegir informació a la finestra
        window.title("Demo PackAssist - Editor de Simplificació de Malla")
        
        print("✅ Editor obert! Usa els controls per simplificar la malla.")
        print("💡 Prova diferents nivells de vèrtexs i observa com canvia la qualitat.")
        
        # Executar loop principal
        window.mainloop()
        
    except Exception as e:
        print(f"❌ Error obrint editor: {e}")
        import traceback
        traceback.print_exc()


def open_stp_file_editor():
    """Obre l'editor per un fitxer STP seleccionat"""
    try:
        from src.packassist.stp_loader import (
            get_mesh_simplification_info,
            open_mesh_simplification_for_file
        )
        
        # Crear finestra simple per seleccionar fitxer
        root = tk.Tk()
        root.withdraw()  # Amagar finestra principal
        
        # Seleccionar fitxer
        file_path = filedialog.askopenfilename(
            title="Seleccionar fitxer STP/STEP",
            filetypes=[
                ("Fitxers STP", "*.stp"),
                ("Fitxers STEP", "*.step"),
                ("Tots els fitxers", "*.*")
            ]
        )
        
        if not file_path:
            print("❌ No s'ha seleccionat cap fitxer")
            return
        
        print(f"📁 Carregant: {file_path}")
        
        # Verificar si es pot simplificar
        info = get_mesh_simplification_info(file_path)
        
        if not info or not info.get('available'):
            reason = info.get('reason', 'Error desconegut') if info else 'Error analitzant fitxer'
            messagebox.showerror("Error", f"No es pot simplificar aquest fitxer:\\n\\n{reason}")
            return
        
        print(f"✅ Fitxer vàlid:")
        print(f"   📊 Vèrtexs: {info['original_vertices']:,}")
        print(f"   🔷 Cares: {info['original_faces']:,}")
        print(f"   🎯 Recomanat: {info['recommended_target']} vèrtexs")
        
        # Obrir editor
        print("🚀 Obrint editor...")
        editor = open_mesh_simplification_for_file(file_path)
        
        if editor:
            print("🎮 Editor obert per fitxer STP!")
        else:
            messagebox.showerror("Error", "No s'ha pogut obrir l'editor per aquest fitxer")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        messagebox.showerror("Error", f"Error obrint editor STP:\\n{str(e)}")


def create_demo_menu():
    """Crea un menú per seleccionar el tipus de demo"""
    root = tk.Tk()
    root.title("PackAssist - Demo de Simplificació de Malla")
    root.geometry("500x300")
    root.configure(bg="#f5f5f5")
    
    # Estil
    style = ttk.Style()
    style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
    style.configure('Subtitle.TLabel', font=('Arial', 11))
    style.configure('Demo.TButton', font=('Arial', 11), padding=(20, 10))
    
    # Frame principal
    main_frame = ttk.Frame(root, padding="30")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Títol
    title_label = ttk.Label(
        main_frame,
        text="Sistema de Simplificació de Malla",
        style='Title.TLabel'
    )
    title_label.pack(pady=(0, 10))
    
    subtitle_label = ttk.Label(
        main_frame,
        text="Redueix la complexitat de geometries 3D mantenint la forma original",
        style='Subtitle.TLabel'
    )
    subtitle_label.pack(pady=(0, 30))
    
    # Descripció
    desc_text = """Aquest sistema permet:
• Reduir de 40.000 vèrtexs a 100-500 per millor rendiment
• Mantenir la forma real (no conversió a rectangles)
• Control visual amb barra lliscant de complexitat
• Preservació de característiques importants
• Optimització per bin packing"""
    
    desc_label = ttk.Label(main_frame, text=desc_text, justify=tk.LEFT)
    desc_label.pack(pady=(0, 20))
    
    # Botons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=10)
    
    demo_btn = ttk.Button(
        button_frame,
        text="Demo amb Objecte de Prova",
        command=lambda: [root.destroy(), open_mesh_editor_demo()],
        style='Demo.TButton'
    )
    demo_btn.pack(fill=tk.X, pady=5)
    
    file_btn = ttk.Button(
        button_frame,
        text="Obrir Fitxer STP/STEP",
        command=lambda: [root.destroy(), open_stp_file_editor()],
        style='Demo.TButton'
    )
    file_btn.pack(fill=tk.X, pady=5)
    
    # Informació
    info_frame = ttk.LabelFrame(main_frame, text="Informació", padding="10")
    info_frame.pack(fill=tk.X, pady=(20, 0))
    
    info_text = """💡 Consells d'ús:
• Per objectes > 10.000 vèrtexs: reduir a 500-1000
• Per objectes > 1.000 vèrtexs: reduir a 200-500
• Mantenir "Preservar característiques" activat
• Qualitat volum > 70% és recomanada per packing"""
    
    info_label = ttk.Label(info_frame, text=info_text, font=('Consolas', 9))
    info_label.pack(anchor=tk.W)
    
    # Executar
    root.mainloop()


if __name__ == "__main__":
    print("🚀 DEMO DEL SISTEMA DE SIMPLIFICACIÓ DE MALLA")
    print("="*50)
    print("Selecciona una opció al menú que s'obrirà...")
    
    try:
        create_demo_menu()
    except KeyboardInterrupt:
        print("\\n👋 Demo cancel·lat per l'usuari")
    except Exception as e:
        print(f"❌ Error en demo: {e}")
        import traceback
        traceback.print_exc()
