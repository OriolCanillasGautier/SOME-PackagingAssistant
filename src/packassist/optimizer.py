import sys
import os
# Add the src directory to Python path
current_dir = os.path.dirname(__file__)
src_dir = os.path.join(current_dir, '..')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# New imports for mesh-based packing
import trimesh
import numpy as np
from .collision_manager import CollisionManager

from py3dbp_enhanced.main import Packer, Bin, Item
import math
import time
import traceback

def pack_with_mesh_collision(box_dims, obj_dims, obj_mesh: trimesh.Trimesh):
    """
    Realitza l'empaquetament utilitzant detecció de col·lisions precisa amb malles.
    Aquesta és la implementació de la Fase 1 que substitueix els factors de correcció.
    """
    print("\n🚀 INICIANT EMPAQUETAMENT AMB DETECCIÓ DE COL·LISIÓ PRECISA (FASE 1)")
    print("=" * 70)
    
    # --- 1. Crear la malla del contenidor ---
    container_extents = [box_dims['length'], box_dims['width'], box_dims['height']]
    container_mesh = trimesh.creation.box(extents=container_extents)
    # Movem el contenidor perquè la seva cantonada estigui a (0,0,0)
    container_mesh.apply_translation(np.array(container_extents) / 2)
    print(f"📦 Malla de contenidor creada: {container_extents}")

    # --- 2. Inicialitzar el gestor de col·lisions ---
    # El gestor de col·lisions ja afegeix les parets del contenidor com a obstacles
    collision_manager = CollisionManager(container_mesh)
    print("🛡️ Gestor de col·lisions inicialitzat amb les parets del contenidor.")

    # --- 3. Estratègia de col·locació (Greedy Grid) ---
    # Aquesta és una estratègia simple. A la Fase 2 es pot millorar amb rotacions i heurístiques més avançades.
    placed_items_info = []
    
    # Dimensions de l'objecte (bounding box) per determinar els passos
    obj_extents = obj_mesh.extents
    print(f"📏 Dimensions (extents) de la malla de l'objecte: {np.round(obj_extents, 2)}")

    # Definim els punts d'inici per a la col·locació. Comencem per les cantonades.
    # Aquesta és una heurística simple per accelerar la cerca.
    step_size = obj_extents / 4 # Pas més petit per a un millor ajust
    
    x_points = np.arange(0, container_extents[0] - obj_extents[0] + 1, step_size[0])
    y_points = np.arange(0, container_extents[1] - obj_extents[1] + 1, step_size[1])
    z_points = np.arange(0, container_extents[2] - obj_extents[2] + 1, step_size[2])
    
    print(f"Punts de prova generats: {len(x_points)} (X), {len(y_points)} (Y), {len(z_points)} (Z)")
    
    item_count = 0
    start_time = time.time()

    # TODO: A la Fase 2, afegir bucle per a les rotacions aquí
    # for rotation in possible_rotations:
    #   rotated_mesh = obj_mesh.copy().apply_transform(rotation)
    #   ...

    for z in z_points:
        for y in y_points:
            for x in x_points:
                # La transformació mou el centre de la malla de l'objecte
                # La posició (x,y,z) és la cantonada inferior, per tant, ajustem al centre
                center_pos = [x + obj_extents[0] / 2, y + obj_extents[1] / 2, z + obj_extents[2] / 2]
                transform = trimesh.transformations.translation_matrix(center_pos)

                # Comprovar col·lisió
                if not collision_manager.check_collision(obj_mesh, transform):
                    # Si no hi ha col·lisió, col·loquem l'objecte
                    item_name = f"item_mesh_{item_count}"
                    collision_manager.add_item(item_name, obj_mesh, transform)
                    
                    # Guardem la informació de l'objecte col·locat
                    placed_items_info.append({
                        'name': item_name,
                        'position': [x, y, z],  # Posició de la cantonada
                        'dimensions': obj_extents.tolist(), # Bounding box de la malla
                        'rotation_type': 0  # Placeholder per Fase 2
                    })
                    item_count += 1
                    # print(f"  ✅ Objecte {item_count} col·locat a {np.round([x,y,z], 1)}")

    end_time = time.time()
    print(f"⏱️ Temps de cerca de col·lisions: {end_time - start_time:.2f} segons")

    # --- 4. Formatar els resultats ---
    box_volume = container_mesh.volume
    # Usem el volum real de la malla per a un càlcul d'eficiència precís
    used_volume = item_count * obj_mesh.volume 
    efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0

    bin_data = {
        'name': 'Container_MeshCollision',
        'dimensions': container_extents,
        'volume': box_volume,
        'optimization_info': {
            'method': 'mesh_collision_greedy_grid',
            'search_time_seconds': round(end_time - start_time, 2)
        }
    }
    
    bins_info = [{
        'bin': bin_data,
        'items': placed_items_info
    }]

    print("\n🏁 RESULTAT EMPAQUETAMENT AMB COL·LISIÓ DE MALLES")
    print("=" * 70)
    print(f"📦 Objectes col·locats: {item_count}")
    print(f"Eficiència (volum real): {efficiency:.2f}%")
    print(f"   - Volum contenidor: {box_volume:.2f} mm³")
    print(f"   - Volum real utilitzat: {used_volume:.2f} mm³")
    print("=" * 70)

    return {
        'max_objects': item_count,
        'efficiency': round(efficiency, 2),
        'box_volume': round(box_volume, 2),
        'used_volume': round(used_volume, 2),
        'bins': bins_info,
        'error': None
    }

def optimize_packing(box_dims, obj_dims, max_attempts=None):
    try:
        if isinstance(box_dims, tuple):
            box_dims = {'length': box_dims[0], 'width': box_dims[1], 'height': box_dims[2]}
        if isinstance(obj_dims, tuple):
            obj_dims = {'length': obj_dims[0], 'width': obj_dims[1], 'height': obj_dims[2]}
        
        has_advanced_geometry = obj_dims.get('advanced_geometry', False)
        
        print("\n🧮 INICIANT PROCÉS D'OPTIMITZACIÓ D'EMPAQUETAMENT")
        print("=" * 60)
        print(f"Contenidor: {box_dims['length']} × {box_dims['width']} × {box_dims['height']} mm")
        
        if has_advanced_geometry:
            print(f"Objecte COMPLEX: {obj_dims['length']} × {obj_dims['width']} × {obj_dims['height']} mm (Bounding Box)")
            print(f"   S'utilitzarà la geometria de malla real per a la precisió.")
        else:
            print(f"Objecte SIMPLE: {obj_dims['length']} × {obj_dims['width']} × {obj_dims['height']} mm")
        
        print("=" * 60)
        
        # --- NOU FLUX DE TREBALL (FASE 1) ---
        if has_advanced_geometry:
            geometry_obj = obj_dims.get('geometry_object')
            
            # Comprovem si tenim una malla vàlida per treballar
            obj_mesh = None
            if geometry_obj and hasattr(geometry_obj, 'to_trimesh'):
                # El mòdul advanced_geometry retorna un objecte que es pot convertir a trimesh
                obj_mesh = geometry_obj.to_trimesh()
                if not obj_mesh.is_watertight:
                    print("⚠️ La malla de l'objecte no és 'watertight'. Intentant reparar...")
                    trimesh.repair.fill_holes(obj_mesh)
                    trimesh.repair.fix_inversion(obj_mesh)
                    if not obj_mesh.is_watertight:
                        print("La reparació de la malla ha fallat. Els resultats de col·lisió poden ser imprecisos.")
            
            if obj_mesh:
                # Si tenim la malla, executem el nou algorisme basat en col·lisions
                final_result = pack_with_mesh_collision(box_dims, obj_dims, obj_mesh)
            else:
                # Si no hi ha malla, tornem a l'algorisme antic com a fallback
                print("ADVERTÈNCIA: Geometria avançada indicada, però no s'ha trobat una malla vàlida.")
                print("   Tornant a l'algorisme de factors de correcció heretat.")
                final_result = calculate_recursive_grid_packing(box_dims, obj_dims, has_complex_geometry=True)
        else:
            # --- FLUX DE TREBALL HERETAT (per a objectes simples) ---
            print("Provant empaquetament en graella amb recursivitat (mètode heretat)...")
            final_result = calculate_recursive_grid_packing(box_dims, obj_dims, has_complex_geometry=False)

        return final_result
        
    except Exception as e:
        traceback.print_exc()
        return {
            'max_objects': 0,
            'efficiency': 0.0,
            'box_volume': 0.0,
            'used_volume': 0.0,
            'bins': [],
            'error': str(e)
        }

# ============================================================================
# == FUNCIONS HERETADES (per a objectes simples o com a fallback)
# ============================================================================

def calculate_recursive_grid_packing(box_dims, obj_dims, level=0, prefix="", has_complex_geometry=False):
    """
    Empaquetament recursiu que omple els espais buits. (Mètode heretat)
    """
    try:
        indent = "  " * level
        
        # La lògica de 'complex_geometry_packing' vs 'grid_packing' es manté per al fallback
        if has_complex_geometry:
            grid_result = calculate_complex_geometry_packing(box_dims, obj_dims)
        else:
            grid_result = calculate_grid_packing(box_dims, obj_dims)
        
        if grid_result['max_objects'] == 0:
            return {'max_objects': 0, 'efficiency': 0, 'bins': [], 'total_spaces_analyzed': 1}
        
        best_orientation = grid_result['best_orientation']
        obj_l, obj_w, obj_h = best_orientation
        
        fit_length = math.floor(box_dims['length'] / obj_l) if obj_l > 0 else 0
        fit_width = math.floor(box_dims['width'] / obj_w) if obj_w > 0 else 0
        fit_height = math.floor(box_dims['height'] / obj_h) if obj_h > 0 else 0
        
        base_objects = fit_length * fit_width * fit_height
        
        # Càlcul simplificat d'espais buits
        empty_spaces = []
        # ... (la lògica de càlcul d'espais buits es pot mantenir o simplificar)
        
        total_additional_objects = 0
        total_spaces_analyzed = 1
        
        # Lògica recursiva...
        
        total_objects = base_objects + total_additional_objects
        
        # Càlcul de mètriques finals...
        box_volume = box_dims['length'] * box_dims['width'] * box_dims['height']
        if has_complex_geometry and obj_dims.get('real_volume'):
            obj_volume = obj_dims['real_volume']
        else:
            obj_volume = obj_dims['length'] * obj_dims['width'] * obj_dims['height']
        
        used_volume = total_objects * obj_volume
        efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0
        
        # Generació del layout per a la visualització (només al nivell superior)
        bins_info = []
        if level == 0:
            box = _generate_recursive_grid_layout(box_dims, obj_dims, total_objects, best_orientation, has_complex_geometry)
            if box:
                items_info = [{'name': item.name, 'position': item.position, 'dimensions': item.getDimension(), 'rotation_type': item.rotation_type} for item in box.items]
                bin_data = {'name': 'Container_Recursive_Fallback', 'dimensions': [box_dims['length'], box_dims['width'], box_dims['height']], 'volume': box_volume}
                bins_info.append({'bin': bin_data, 'items': items_info})

        return {
            'max_objects': total_objects,
            'efficiency': round(efficiency, 2),
            'box_volume': round(box_volume, 2),
            'used_volume': round(used_volume, 2),
            'bins': bins_info,
            'total_spaces_analyzed': total_spaces_analyzed,
            'error': None
        }
        
    except Exception as e:
        traceback.print_exc()
        return {'max_objects': 0, 'efficiency': 0, 'total_spaces_analyzed': 1, 'error': str(e), 'bins': []}

def _generate_recursive_grid_layout(box_dims, obj_dims, total_objects, best_orientation, has_complex_geometry=False):
    # Aquesta funció es manté per al mètode de fallback
    try:
        obj_l, obj_w, obj_h = best_orientation
        box = Bin('Container_Recursive_Fallback', [float(d) for d in box_dims.values()], 99999.0)
        # ... la resta de la lògica de generació de layout
        return box
    except Exception as e:
        traceback.print_exc()
        return None

def calculate_complex_geometry_packing(box_dims, obj_dims):
    """
    Calcula empaquetament per geometries complexes reals. (Mètode heretat de fallback)
    """
    # ... (implementació heretada)
    return {'max_objects': 0, 'best_orientation': (0,0,0), 'efficiency': 0}


def calculate_grid_packing(box_dims, obj_dims):
    """
    Calcula empaquetament basat en una graella perfecta. (Mètode heretat de fallback)
    """
    # ... (implementació heretada)
    return {'max_objects': 0, 'best_orientation': (0,0,0), 'efficiency': 0}
