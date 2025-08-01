#!/usr/bin/env python3
"""
Instal·lador de dependències per UltraFastMeshSimplifier
"""

import subprocess
import sys
import os

def install_package(package):
    """Instal·la un paquet Python"""
    try:
        print(f"📦 Instal·lant {package}...")
        result = subprocess.run([sys.executable, "-m", "pip", "install", package], 
                              capture_output=True, text=True, check=True)
        print(f"✅ {package} instal·lat correctament")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error instal·lant {package}: {e}")
        print(f"   Sortida: {e.stdout}")
        print(f"   Error: {e.stderr}")
        return False

def main():
    """Instal·la les biblioteques de simplificació de malles"""
    print("🚀 INSTAL·LADOR DE BIBLIOTEQUES PER SIMPLIFICACIÓ DE MALLES")
    print("="*60)
    
    packages = [
        ("pymeshlab", "Biblioteca principal (RECOMANADA) - molt ràpida i potent"),
        ("pyvista", "Visualització i processament de malles"),
        ("trimesh", "Biblioteca lleugera per geometria 3D"),
        # pyfqmr sovint té problemes de compilació, el deixem opcional
    ]
    
    print("📋 Biblioteques a instal·lar:")
    for package, description in packages:
        print(f"   • {package}: {description}")
    
    print("\n⚠️ NOTA: Aquestes instal·lacions poden trigar uns minuts...")
    
    response = input("\n🤔 Vols continuar? (s/N): ").strip().lower()
    if response not in ['s', 'sí', 'si', 'yes', 'y']:
        print("❌ Instal·lació cancel·lada")
        return
    
    print("\n🔧 Iniciant instal·lació...")
    
    success_count = 0
    total_count = len(packages)
    
    for package, description in packages:
        if install_package(package):
            success_count += 1
        print()
    
    # Intentar instal·lar pyfqmr (opcional)
    print("🎯 Intentant instal·lar pyfqmr (opcional, pot fallar)...")
    try:
        install_package("pyfqmr")
        success_count += 1
        total_count += 1
    except:
        print("⚠️ pyfqmr no s'ha pogut instal·lar (normal, necessita compilació)")
    
    print("\n" + "="*60)
    print("📊 RESUM DE LA INSTAL·LACIÓ")
    print("="*60)
    
    if success_count == total_count:
        print("🎉 TOTES LES BIBLIOTEQUES INSTAL·LADES CORRECTAMENT!")
        print("✅ Ja pots utilitzar ultra_fast_mesh_simplifier.py")
    elif success_count > 0:
        print(f"⚠️ {success_count}/{total_count} biblioteques instal·lades")
        print("✅ El simplificador funcionarà amb les biblioteques disponibles")
    else:
        print("❌ NO S'HA POGUT INSTAL·LAR CAP BIBLIOTECA")
        print("🔧 Prova d'instal·lar manualment:")
        print("   pip install pymeshlab")
        print("   pip install pyvista")
        print("   pip install trimesh")
    
    print("\n💡 Per utilitzar el simplificador:")
    print("   python ultra_fast_mesh_simplifier.py")
    print("   o bé:")
    print("   python ultra_fast_mesh_simplifier.py fitxer.stl 1000")

if __name__ == "__main__":
    main()
