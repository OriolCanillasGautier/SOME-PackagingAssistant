#!/usr/bin/env python3
"""
Script de construcció per PackAssist 3D
Automatitza la creació de l'executable amb PyInstaller
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, description):
    """Executa una comanda i mostra el resultat."""
    print(f"\n🔧 {description}")
    print("-" * 50)
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completat")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error en {description}")
        print(f"Codi d'error: {e.returncode}")
        if e.stdout:
            print(f"Sortida: {e.stdout}")
        if e.stderr:
            print(f"Error: {e.stderr}")
        return False

def check_dependencies():
    """Verifica que totes les dependències estiguin instal·lades."""
    print("🔍 Verificant dependències...")
    
    try:
        import tkinter
        print("✅ tkinter disponible")
    except ImportError:
        print("❌ tkinter no disponible")
        return False
    
    try:
        import PyInstaller
        print("✅ PyInstaller disponible")
    except ImportError:
        print("❌ PyInstaller no disponible - instal·lant...")
        if not run_command("pip install pyinstaller", "Instal·lació de PyInstaller"):
            return False
    
    # Verificar mòduls locals
    try:
        from src.packassist.stp_loader import get_stp_dimensions
        from src.packassist.optimizer import optimize_packing
        print("✅ Mòduls PackAssist disponibles")
    except ImportError as e:
        print(f"❌ Error important mòduls PackAssist: {e}")
        return False
    
    return True

def create_pyinstaller_spec():
    """Crea l'arxiu .spec per PyInstaller."""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src', 'src'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PackAssist3D',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
'''
    
    with open('PackAssist3D.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("✅ Fitxer .spec creat")

def build_executable():
    """Construeix l'executable."""
    print("\n🚀 CONSTRUCCIÓ DE L'EXECUTABLE")
    print("=" * 50)
    
    # Verificar dependències
    if not check_dependencies():
        print("❌ Dependències no satisfetes")
        return False
    
    # Crear directori de construcció si no existeix
    os.makedirs("dist", exist_ok=True)
    
    # Crear fitxer .spec
    create_pyinstaller_spec()
    
    # Construir amb PyInstaller
    if not run_command("pyinstaller --clean PackAssist3D.spec", "Construcció amb PyInstaller"):
        return False
    
    # Verificar que l'executable s'ha creat
    exe_path = Path("dist/PackAssist3D.exe")
    if exe_path.exists():
        file_size = exe_path.stat().st_size / (1024 * 1024)  # MB
        print(f"✅ Executable creat: {exe_path}")
        print(f"📊 Mida: {file_size:.1f} MB")
        
        # Crear directori d'exemple si no existeix
        example_dir = Path("dist/example_data")
        if not example_dir.exists():
            example_dir.mkdir()
            print("✅ Directori d'exemple creat")
        
        return True
    else:
        print("❌ L'executable no s'ha creat correctament")
        return False

def cleanup():
    """Neteja fitxers temporals."""
    print("\n🧹 Netejant fitxers temporals...")
    
    temp_dirs = ["build", "__pycache__"]
    temp_files = ["PackAssist3D.spec"]
    
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"✅ Eliminat: {temp_dir}")
    
    for temp_file in temp_files:
        if os.path.exists(temp_file):
            os.remove(temp_file)
            print(f"✅ Eliminat: {temp_file}")

def main():
    """Funció principal del script de construcció."""
    print("🎯 PACKASSIST 3D - SCRIPT DE CONSTRUCCIÓ")
    print("=" * 50)
    
    # Canviar al directori del script
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    try:
        # Construir executable
        if build_executable():
            print("\n🎉 CONSTRUCCIÓ COMPLETADA AMB ÈXIT!")
            print("=" * 50)
            print("📁 L'executable es troba a: dist/PackAssist3D.exe")
            print("💡 Pots distribuir el fitxer executable de forma independent")
            
            # Preguntar si vol netejar
            response = input("\n🧹 Vols netejar els fitxers temporals? (s/n): ")
            if response.lower() in ['s', 'y', 'yes', 'sí']:
                cleanup()
        else:
            print("\n❌ CONSTRUCCIÓ FALLIDA")
            print("=" * 50)
            print("Revisa els errors anteriors i torna-ho a intentar")
            
    except KeyboardInterrupt:
        print("\n👋 Construcció interrompuda per l'usuari")
    except Exception as e:
        print(f"\n❌ Error inesperat: {e}")

if __name__ == "__main__":
    main()
