#!/usr/bin/env python3
"""
PackAssist Launcher - Script principal per iniciar l'aplicació
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Llançador principal de PackAssist"""
    
    print("🚀 PackAssist - Empaquetament Intel·ligent")
    print("=" * 50)
    
    # Verificar entorn virtual
    venv_python = Path("packassist_env") / "Scripts" / "python.exe"
    
    if venv_python.exists():
        python_cmd = str(venv_python)
        print("✅ Utilitzant entorn virtual")
    else:
        python_cmd = "python"
        print("⚠️ Utilitzant Python del sistema")
    
    # Opcions disponibles
    print("\n📋 Opcions disponibles:")
    print("1. 🚀 PackAssist GUI (NOVA INTERFÍCIE - Recomanat)")
    print("2. 🎯 Aplicació Simple (2 pestanyes)")
    print("3. 🔧 Simplificador STL Avançat (GUI completa)")
    print("4. ⚡ Simplificador Ultra Ràpid")
    print("5. 🔧 Simplificador Simple")
    print("6. 🧪 Proves de Simplificació")
    print("7. ❌ Sortir")
    
    while True:
        try:
            choice = input("\n👉 Selecciona una opció (1-7): ").strip()
            
            if choice == "1":
                # Nova GUI
                print("\n🚀 Iniciant PackAssist GUI...")
                subprocess.run([python_cmd, "packassist_gui.py"])
                break
                
            elif choice == "2":
                # Aplicació simple
                print("\n🎯 Iniciant aplicació simple...")
                subprocess.run([python_cmd, "packassist_simple.py"])
                break
                
            elif choice == "3":
                # Simplificador STL Avançat
                print("\n🔧 Iniciant simplificador STL avançat...")
                subprocess.run([python_cmd, "actiu/tools/mesh_simplifiers/advanced_stl_simplifier.py"])
                break
                
            elif choice == "4":
                # Simplificador ultra ràpid
                print("\n⚡ Iniciant simplificador ultra ràpid...")
                subprocess.run([python_cmd, "actiu/tools/mesh_simplifiers/ultra_fast_mesh_simplifier.py"])
                break
                
            elif choice == "5":
                # Simplificador simple
                print("\n🔧 Iniciant simplificador simple...")
                subprocess.run([python_cmd, "actiu/tools/mesh_simplifiers/mesh_simplifier_simple.py"])
                break
                
            elif choice == "6":
                # Proves
                print("\n🧪 Iniciant proves de simplificació...")
                subprocess.run([python_cmd, "actiu/tests/test_mesh_simplification.py"])
                break
                
            elif choice == "7":
                print("\n👋 Sortint...")
                break
                
            else:
                print("❌ Opció no vàlida. Tria entre 1-7.")
                
        except KeyboardInterrupt:
            print("\n\n👋 Sortint...")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            break

if __name__ == "__main__":
    main()
