#!/usr/bin/env python3
"""
Script per instal·lar suport complet per fitxers STP/STEP
Instal·la FreeCAD, Open3D, Trimesh i altres dependències
"""

import subprocess
import sys
import os
import platform

def install_package(package_name, pip_name=None):
    """Instal·la un paquet de Python"""
    if pip_name is None:
        pip_name = package_name
    
    try:
        __import__(package_name)
        print(f"✅ {package_name} ja està instal·lat")
        return True
    except ImportError:
        print(f"📦 Instal·lant {package_name}...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', pip_name])
            print(f"✅ {package_name} instal·lat correctament")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Error instal·lant {package_name}: {e}")
            return False

def install_freecad():
    """Instal·la FreeCAD segons el sistema operatiu"""
    print("\n🔧 Instal·lant FreeCAD...")
    
    system = platform.system().lower()
    
    if system == "windows":
        print("📌 Per Windows, descarrega FreeCAD des de: https://www.freecad.org/downloads.php")
        print("📌 O instal·la amb conda: conda install -c conda-forge freecad")
        
        # Provar conda si està disponible
        try:
            subprocess.check_call(['conda', 'install', '-c', 'conda-forge', 'freecad', '-y'])
            print("✅ FreeCAD instal·lat amb conda")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️ Conda no disponible o error. Instal·la FreeCAD manualment.")
            return False
    
    elif system == "linux":
        print("📌 Per Linux Ubuntu/Debian:")
        print("   sudo apt update && sudo apt install freecad")
        
        try:
            subprocess.check_call(['sudo', 'apt', 'update'])
            subprocess.check_call(['sudo', 'apt', 'install', 'freecad', '-y'])
            print("✅ FreeCAD instal·lat amb apt")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️ Error amb apt. Prova manualment: sudo apt install freecad")
            return False
    
    elif system == "darwin":  # macOS
        print("📌 Per macOS:")
        print("   brew install freecad")
        
        try:
            subprocess.check_call(['brew', 'install', 'freecad'])
            print("✅ FreeCAD instal·lat amb brew")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️ Homebrew no disponible. Descarrega FreeCAD des de freecad.org")
            return False
    
    return False

def test_stp_loading():
    """Prova la càrrega d'STP"""
    print("\n🧪 Provant càrrega STP...")
    
    # Provar FreeCAD
    try:
        import FreeCAD
        print("✅ FreeCAD importat correctament")
        
        # Crear document de prova
        doc = FreeCAD.newDocument("test")
        print("✅ Document FreeCAD creat")
        FreeCAD.closeDocument("test")
        print("✅ FreeCAD funcionant correctament")
        return True
        
    except ImportError:
        print("❌ FreeCAD no disponible per importar")
        return False
    except Exception as e:
        print(f"❌ Error provant FreeCAD: {e}")
        return False

def main():
    """Funció principal d'instal·lació"""
    print("🚀 INSTAL·LACIÓ DE SUPORT STP/STEP")
    print("=" * 50)
    
    success_count = 0
    total_packages = 0
    
    # Paquets Python essencials
    python_packages = [
        ('numpy', 'numpy'),
        ('scipy', 'scipy'),
        ('trimesh', 'trimesh'),
        ('open3d', 'open3d'),
    ]
    
    print("\n📦 Instal·lant paquets Python...")
    for package, pip_name in python_packages:
        total_packages += 1
        if install_package(package, pip_name):
            success_count += 1
    
    # FreeCAD (el més important)
    print("\n🔧 Instal·lant FreeCAD...")
    total_packages += 1
    if install_freecad():
        success_count += 1
    
    # Provar funcionament
    print("\n🧪 Provant funcionament...")
    if test_stp_loading():
        print("🎉 STP suport instal·lat i funcionant!")
    else:
        print("⚠️ Instal·lació parcial. Alguns components no funcionen.")
    
    # Resum
    print(f"\n📊 Resum: {success_count}/{total_packages} components instal·lats")
    
    if success_count == total_packages:
        print("🎉 Instal·lació completa! Ara pots carregar fitxers STP.")
    else:
        print("⚠️ Instal·lació incompleta. Revisa els errors anteriors.")
        print("\n💡 Alternatives:")
        print("   1. Converteix STP a STL amb FreeCAD manualment")
        print("   2. Usa el sistema de malles de prova (ja funciona)")
        print("   3. Instal·la FreeCAD manualment des de freecad.org")

if __name__ == "__main__":
    main()
