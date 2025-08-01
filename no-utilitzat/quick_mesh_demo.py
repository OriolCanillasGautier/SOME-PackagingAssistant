#!/usr/bin/env python3
"""
Demostració ràpida del sistema de simplificació de malla
Accés directe sense necessitat de carregar tota l'aplicació
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

# Afegir path per accedir als mòduls
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.packassist.advanced_geometry import AdvancedGeometry
    print("✅ Mòdul Advanced Geometry carregat correctament")
except ImportError as e:
    print(f"❌ Error important Advanced Geometry: {e}")
    sys.exit(1)


def main():
    """Funció principal de demostració ràpida."""
    print("🚀 PackAssist - Demostració Ràpida de Simplificació de Malla")
    print("=" * 60)
    
    # Configurar sistema de geometria
    print("📐 Inicialitzant sistema de geometria...")
    geometry_analyzer = AdvancedGeometry()
    
    try:
        # Inicialitzar sistema de simplificació
        geometry_analyzer.initialize_mesh_simplification()
        print("✅ Sistema de simplificació inicialitzat")
    except Exception as e:
        print(f"❌ Error inicialitzant sistema: {e}")
        return
    
    # Crear finestra de selecció de fitxer
    root = tk.Tk()
    root.withdraw()  # Amagar finestra principal
    
    print("\n📁 Selecciona un fitxer STP per simplificar...")
    
    # Definir tipus de fitxer acceptats
    filetypes = [
        ("Fitxers STP", "*.stp"),
        ("Fitxers STEP", "*.step"),
        ("Tots els fitxers", "*.*")
    ]
    
    # Directori inicial
    initial_dir = "objects"
    if not os.path.exists(initial_dir):
        initial_dir = "."
    
    # Seleccionar fitxer
    file_path = filedialog.askopenfilename(
        title="Selecciona un fitxer STP per simplificar",
        filetypes=filetypes,
        initialdir=initial_dir
    )
    
    if not file_path:
        print("❌ Cap fitxer seleccionat. Sortint...")
        return
    
    print(f"📄 Fitxer seleccionat: {os.path.basename(file_path)}")
    
    try:
        # Obrir editor de simplificació
        print("🔧 Obrint editor de simplificació de malla...")
        geometry_analyzer.open_mesh_editor(file_path)
        print("✅ Editor obert correctament!")
        
    except Exception as e:
        print(f"❌ Error obrint l'editor: {e}")
        messagebox.showerror("Error", f"Error obrint l'editor de simplificació:\n{str(e)}")
    
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
