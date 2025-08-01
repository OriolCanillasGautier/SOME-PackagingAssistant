#!/usr/bin/env python3
"""
Script per trobar i mostrar la funció _update_dimensions_from_intelligent_box
"""

def find_function_in_file():
    """Troba la funció en app.py i la mostra."""
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Buscar la funció
        start_line = None
        for i, line in enumerate(lines):
            if 'def _update_dimensions_from_intelligent_box' in line:
                start_line = i
                break
        
        if start_line is None:
            print("❌ Funció no trobada")
            return
        
        print(f"🔍 Funció trobada a la línia {start_line + 1}")
        
        # Trobar el final de la funció (següent def o final del fitxer)
        end_line = len(lines)
        for i in range(start_line + 1, len(lines)):
            if lines[i].strip().startswith('def ') and not lines[i].strip().startswith('def _'):
                end_line = i
                break
            if lines[i].strip().startswith('# ==='):
                end_line = i
                break
        
        print(f"📏 Funció fins la línia {end_line}")
        print("📝 Contingut de la funció:")
        print("-" * 50)
        
        for i in range(start_line, min(end_line, start_line + 30)):
            print(f"{i+1:4d}: {lines[i].rstrip()}")
        
        return start_line, end_line
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None

if __name__ == "__main__":
    find_function_in_file()
