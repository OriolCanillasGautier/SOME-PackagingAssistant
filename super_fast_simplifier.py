#!/usr/bin/env python3
"""
🚀 SIMPLIFICADOR STL SUPER RÀPID - VERSIÓ SENSE PROBLEMES
Utilitza PyVista que és el més fiable per a simplificació ràpida
"""

import os
import sys
import time
import traceback
from pathlib import Path

def check_and_install_dependencies():
    """Comprova i instal·la dependències si és necessari"""
    required = {'pyvista': 'pyvista'}
    
    available = {}
    for name, package in required.items():
        try:
            __import__(package)
            available[name] = True
            print(f"✅ {name} disponible")
        except ImportError:
            available[name] = False
            print(f"❌ {name} no disponible")
    
    return available

def simplify_with_pyvista_direct(input_path, target_vertices=500):
    """Simplificació directa amb PyVista - EL MÉS RÀPID"""
    try:
        import pyvista as pv
        
        print(f"🚀 Carregant {os.path.basename(input_path)} amb PyVista...")
        
        # Carregar mesh
        mesh = pv.read(input_path)
        original_vertices = mesh.n_points
        original_faces = mesh.n_cells
        
        print(f"📊 Original: {original_vertices:,} vèrtexs, {original_faces:,} cares")
        
        if original_vertices <= target_vertices:
            print("⚠️ La malla ja té menys vèrtexs que l'objectiu")
            return mesh, 0
        
        # Calcular reducció necessària
        reduction_ratio = 1.0 - (target_vertices / original_vertices)
        reduction_ratio = max(0.1, min(0.95, reduction_ratio))
        
        print(f"🎯 Objectiu: {target_vertices:,} vèrtexs")
        print(f"📉 Reducció: {reduction_ratio:.1%}")
        
        # SIMPLIFICACIÓ RÀPIDA
        start_time = time.time()
        simplified = mesh.decimate(reduction_ratio)
        end_time = time.time()
        
        final_vertices = simplified.n_points
        final_faces = simplified.n_cells
        actual_reduction = (original_vertices - final_vertices) / original_vertices
        
        print(f"✅ SIMPLIFICACIÓ COMPLETA en {end_time - start_time:.2f}s!")
        print(f"📊 Final: {final_vertices:,} vèrtexs, {final_faces:,} cares")
        print(f"📉 Reducció real: {actual_reduction:.1%}")
        
        return simplified, end_time - start_time
        
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return None, 0

def simplify_with_trimesh_direct(input_path, target_vertices=500):
    """Simplificació directa amb Trimesh"""
    try:
        import trimesh
        
        print(f"🚀 Carregant {os.path.basename(input_path)} amb Trimesh...")
        
        # Carregar mesh
        mesh = trimesh.load_mesh(input_path)
        original_vertices = len(mesh.vertices)
        original_faces = len(mesh.faces)
        
        print(f"📊 Original: {original_vertices:,} vèrtexs, {original_faces:,} cares")
        
        if original_vertices <= target_vertices:
            print("⚠️ La malla ja té menys vèrtexs que l'objectiu")
            return mesh, 0
        
        print(f"🎯 Objectiu: {target_vertices:,} vèrtexs")
        
        # SIMPLIFICACIÓ RÀPIDA
        start_time = time.time()
        simplified = mesh.simplify_quadric_decimation(face_count=target_vertices * 2)
        end_time = time.time()
        
        final_vertices = len(simplified.vertices)
        final_faces = len(simplified.faces)
        actual_reduction = (original_vertices - final_vertices) / original_vertices
        
        print(f"✅ SIMPLIFICACIÓ COMPLETA en {end_time - start_time:.2f}s!")
        print(f"📊 Final: {final_vertices:,} vèrtexs, {final_faces:,} cares")
        print(f"📉 Reducció real: {actual_reduction:.1%}")
        
        return simplified, end_time - start_time
        
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return None, 0

def main():
    """Funció principal super simple"""
    print("🚀 SIMPLIFICADOR STL SUPER RÀPID")
    print("=" * 50)
    
    # Comprovar dependències
    available = check_and_install_dependencies()
    
    if not available.get('pyvista') and not available.get('trimesh'):
        print("\n❌ Necessites PyVista o Trimesh!")
        print("💡 Instal·la amb:")
        print("   pip install pyvista")
        print("   o")
        print("   pip install trimesh")
        return
    
    # Trobar fitxer STL
    input_file = None
    stl_files = list(Path('.').glob('*.stl')) + list(Path('.').glob('**/*.stl'))
    
    if stl_files:
        # Usar l'últim fitxer STL trobat
        input_file = str(stl_files[-1])
        print(f"📁 Fitxer trobat automàticament: {os.path.basename(input_file)}")
    else:
        print("❌ No s'han trobat fitxers STL en el directori actual")
        print("💡 Posa un fitxer .stl en aquest directori i torna a executar")
        return
    
    # Configuració objectius
    targets = [500, 1000, 2000, 5000]
    
    for target in targets:
        print(f"\n{'='*50}")
        print(f"🎯 PROVA AMB {target:,} VÈRTEXS")
        print(f"{'='*50}")
        
        # Generar nom de sortida
        input_path = Path(input_file)
        output_file = str(input_path.with_stem(f"{input_path.stem}_simplified_{target}"))
        
        # Provar PyVista primer (més ràpid)
        if available.get('pyvista'):
            print("🔄 Provant amb PyVista...")
            simplified, duration = simplify_with_pyvista_direct(input_file, target)
            
            if simplified is not None:
                simplified.save(output_file)
                print(f"💾 Guardat: {os.path.basename(output_file)}")
                print(f"⏱️ Temps total: {duration:.2f}s")
                continue
        
        # Si PyVista falla, provar Trimesh
        if available.get('trimesh'):
            print("🔄 Provant amb Trimesh...")
            simplified, duration = simplify_with_trimesh_direct(input_file, target)
            
            if simplified is not None:
                simplified.export(output_file)
                print(f"💾 Guardat: {os.path.basename(output_file)}")
                print(f"⏱️ Temps total: {duration:.2f}s")
                continue
        
        print(f"❌ No s'ha pogut simplificar a {target:,} vèrtexs")
    
    print(f"\n🎉 PROCÉS COMPLETAT!")
    print("📁 Revisa els fitxers generats amb sufixe '_simplified_XXX'")

if __name__ == "__main__":
    main()
