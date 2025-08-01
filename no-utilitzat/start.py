#!/usr/bin/env python3
"""
PackAssist - Executar l'aplicació principal
"""

import os
import sys
import subprocess

def main():
    """Executa l'aplicació PackAssist"""
    try:
        # Assegurar-se que estem al directori correcte
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # Executar l'aplicació principal
        subprocess.run([sys.executable, "packassist.py"], check=True)
        
    except KeyboardInterrupt:
        print("\n👋 Aplicació tancada per l'usuari")
    except Exception as e:
        print(f"❌ Error executant l'aplicació: {e}")
        input("Premeu Enter per sortir...")

if __name__ == "__main__":
    main()
