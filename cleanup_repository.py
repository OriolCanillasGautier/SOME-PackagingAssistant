#!/usr/bin/env python3
"""
Script per netejar el repositori PackAssist eliminant fitxers duplicats i innecessaris.
Mantén només els fitxers essencials per app.py.
"""

import os
import shutil
from pathlib import Path

def cleanup_repository():
    """Neteja el repositori eliminant fitxers duplicats i innecessaris."""
    
    print("🧹 Iniciant neteja del repositori PackAssist...")
    
    # Fitxers a eliminar (duplicats i innecessaris)
    files_to_remove = [
        "app_gui.py",
        "app_lite.py", 
        "packassist_gui.py",
        "build.py",
        "build_exe.bat",
        "build_exe.spec",
        "cleanup.bat",
        "run_gui.bat",
        "setup_env.bat",
        "requirements_gui.txt"
    ]
    
    # Directoris a eliminar (caches i temporals)
    dirs_to_remove = [
        "__pycache__"
    ]
    
    removed_files = []
    removed_dirs = []
    
    # Eliminar fitxers
    for filename in files_to_remove:
        filepath = Path(filename)
        if filepath.exists():
            try:
                filepath.unlink()
                removed_files.append(filename)
                print(f"  ✅ Eliminat: {filename}")
            except Exception as e:
                print(f"  ❌ Error eliminant {filename}: {e}")
        else:
            print(f"  ⚠️  No trobat: {filename}")
    
    # Eliminar directoris recursivament
    for dirname in dirs_to_remove:
        dirpath = Path(dirname)
        if dirpath.exists() and dirpath.is_dir():
            try:
                shutil.rmtree(dirpath)
                removed_dirs.append(dirname)
                print(f"  ✅ Eliminat directori: {dirname}")
            except Exception as e:
                print(f"  ❌ Error eliminant directori {dirname}: {e}")
        else:
            print(f"  ⚠️  Directori no trobat: {dirname}")
    
    # Buscar i eliminar altres __pycache__ en subdirectoris
    for root, dirs, files in os.walk("."):
        for dir_name in dirs:
            if dir_name == "__pycache__":
                cache_path = Path(root) / dir_name
                try:
                    shutil.rmtree(cache_path)
                    removed_dirs.append(str(cache_path))
                    print(f"  ✅ Eliminat cache: {cache_path}")
                except Exception as e:
                    print(f"  ❌ Error eliminant cache {cache_path}: {e}")
    
    # Resum
    print(f"\n📊 RESUM DE LA NETEJA:")
    print(f"  📄 Fitxers eliminats: {len(removed_files)}")
    print(f"  📁 Directoris eliminats: {len(removed_dirs)}")
    
    if removed_files:
        print(f"\n  Fitxers eliminats:")
        for f in removed_files:
            print(f"    - {f}")
    
    if removed_dirs:
        print(f"\n  Directoris eliminats:")
        for d in removed_dirs:
            print(f"    - {d}")
    
    print(f"\n✅ Neteja completada!")
    print(f"📝 Els fitxers essencials per app.py s'han mantingut intactes.")
    
    # Mostrar fitxers principals restants
    essential_files = [
        "app.py",
        "requirements.txt", 
        "README.md",
        "setup_samples.py",
        "src/",
        "data/",
        "boxes/",
        "objects/"
    ]
    
    print(f"\n📋 FITXERS ESSENCIALS MANTINGUTS:")
    for item in essential_files:
        path = Path(item)
        if path.exists():
            status = "✅"
        else:
            status = "❌"
        print(f"  {status} {item}")

if __name__ == "__main__":
    cleanup_repository()
