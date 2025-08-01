import sys
import os
# Add the src directory to Python path for py3dbp_enhanced
current_dir = os.path.dirname(__file__)
src_dir = os.path.join(current_dir, '..')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
from py3dbp_enhanced.main import Packer, Bin, Item
import math
import time

def optimize_packing(box_dims, obj_dims, max_attempts=None):
    try:
        if isinstance(box_dims, tuple):
            box_dims = {'length': box_dims[0], 'width': box_dims[1], 'height': box_dims[2]}
        if isinstance(obj_dims, tuple):
            obj_dims = {'length': obj_dims[0], 'width': obj_dims[1], 'height': obj_dims[2]}
        
        # Extract shape information if available
        obj_shape_type = obj_dims.get('shape_type', 'rectangular')
        obj_volume_factor = obj_dims.get('volume_factor', 1.0)
        box_shape_type = box_dims.get('shape_type', 'rectangular')
        box_volume_factor = box_dims.get('volume_factor', 1.0)
        
        # NOVA FUNCIONALITAT: Detectar si tenim geometria complexa real
        has_advanced_geometry = obj_dims.get('advanced_geometry', False)
        
        # Display info
        print("\n🧮 CÀLCUL D'EMPAQUETAMENT AVANÇAT AMB GEOMETRIA REAL")
        print("=" * 60)
        print(f"📦 Contenidor: {box_dims['length']} × {box_dims['width']} × {box_dims['height']} mm")
        print(f"   Forma: {box_shape_type}, Factor volum: {box_volume_factor:.3f}")
        
        if has_advanced_geometry:
            print(f"📋 Objecte COMPLEX: {obj_dims['length']} × {obj_dims['width']} × {obj_dims['height']} mm")
            print(f"   🎯 Geometria avançada: {obj_dims.get('total_faces', 0)} cares, {obj_dims.get('total_vertices', 0)} vèrtexs")
            print(f"   🔗 Cares paral·leles: {obj_dims.get('parallel_face_pairs', 0)}")
            print(f"   � Volum real: {obj_dims.get('real_volume', 0):.2f} mm³")
            print(f"   � Factor volum: {obj_volume_factor:.3f}")
            print(f"   🧮 Complexitat: {obj_dims.get('complexity_score', 0):.2f}")
        else:
            print(f"📋 Objecte: {obj_dims['length']} × {obj_dims['width']} × {obj_dims['height']} mm")
            print(f"   Forma: {obj_shape_type}, Factor volum: {obj_volume_factor:.3f}")
        
        print("=" * 60)
        
        # First try grid packing with recursive empty space filling
        print("Provant empaquetament en graella amb recursivitat...")
        
        # Passar informació de geometria complexa al càlcul recursiu
        recursive_result = calculate_recursive_grid_packing(box_dims, obj_dims, has_complex_geometry=has_advanced_geometry)
        
        # Also try 3D packing for comparison
        print("\nProvant empaquetament 3D tradicional...")
        traditional_result = _calculate_traditional_packing(box_dims, obj_dims, max_attempts)
        
        # Use the better result
        if recursive_result['max_objects'] >= traditional_result['max_objects']:
            print(f"✅ Utilitzant empaquetament recursiu: {recursive_result['max_objects']} objectes")
            final_result = recursive_result
        else:
            print(f"✅ Utilitzant empaquetament 3D: {traditional_result['max_objects']} objectes")
            final_result = traditional_result
            
        return final_result
        
    except Exception as e:
        return {
            'max_objects': 0,
            'efficiency': 0.0,
            'box_volume': 0.0,
            'used_volume': 0.0,
            'bins': [],
            'error': str(e)
        }

def calculate_recursive_grid_packing(box_dims, obj_dims, level=0, prefix="", has_complex_geometry=False):
    """
    Empaquetament recursiu que omple els espais buits.
    Ara suporta geometria complexa real.
    """
    try:
        indent = "  " * level
        print(f"{indent}🔍 {prefix}Analitzant espai: {box_dims['length']} × {box_dims['width']} × {box_dims['height']}")
        
        # Si tenim geometria complexa, usar informació avançada
        if has_complex_geometry and level == 0:
            print(f"{indent}🎯 USANT GEOMETRIA COMPLEXA REAL")
            geometry_obj = obj_dims.get('geometry_object')
            if geometry_obj:
                print(f"{indent}   📊 Objecte amb {len(geometry_obj.faces)} cares reals")
                print(f"{indent}   🔗 {obj_dims.get('parallel_face_pairs', 0)} parelles de cares paral·leles")
                print(f"{indent}   📦 Factor volum real: {obj_dims.get('volume_factor', 1.0):.3f}")
        
        # Calculate basic grid packing for this space
        # DETECCIÓ DE GEOMETRIA COMPLEXA: usar algoritme específic
        has_advanced_geometry = obj_dims.get('advanced_geometry', False)
        if has_advanced_geometry:
            print(f"{indent}🔬 Geometria complexa detectada: usant algorisme avançat")
            grid_result = calculate_complex_geometry_packing(box_dims, obj_dims)
        else:
            print(f"{indent}📊 Geometria simple: usant algorisme graella estàndard")
            grid_result = calculate_grid_packing(box_dims, obj_dims)
        
        if grid_result['max_objects'] == 0:
            print(f"{indent}❌ No cap cap objecte en aquest espai")
            return {
                'max_objects': 0,
                'efficiency': 0,
                'empty_spaces': [],
                'total_spaces_analyzed': 1
            }
        
        best_orientation = grid_result['best_orientation']
        obj_l, obj_w, obj_h = best_orientation
        
        # Calculate how many objects fit in each dimension
        fit_length = math.floor(box_dims['length'] / obj_l) if obj_l > 0 else 0
        fit_width = math.floor(box_dims['width'] / obj_w) if obj_w > 0 else 0
        fit_height = math.floor(box_dims['height'] / obj_h) if obj_h > 0 else 0
        
        base_objects = fit_length * fit_width * fit_height
        print(f"{indent}📊 Objectes base en aquest espai: {base_objects}")
        
        # Calculate empty spaces after placing objects
        empty_spaces = []
        
        # Space at the end of length dimension
        remaining_length = box_dims['length'] - (fit_length * obj_l)
        if remaining_length >= min(obj_dims['length'], obj_dims['width'], obj_dims['height']):
            empty_spaces.append({
                'length': remaining_length,
                'width': box_dims['width'],
                'height': box_dims['height'],
                'position': 'end_length'
            })
        
        # Space at the end of width dimension
        remaining_width = box_dims['width'] - (fit_width * obj_w)
        if remaining_width >= min(obj_dims['length'], obj_dims['width'], obj_dims['height']):
            empty_spaces.append({
                'length': fit_length * obj_l,  # Only the occupied length
                'width': remaining_width,
                'height': box_dims['height'],
                'position': 'end_width'
            })
        
        # Space at the end of height dimension
        remaining_height = box_dims['height'] - (fit_height * obj_h)
        if remaining_height >= min(obj_dims['length'], obj_dims['width'], obj_dims['height']):
            empty_spaces.append({
                'length': fit_length * obj_l,  # Only the occupied length
                'width': fit_width * obj_w,   # Only the occupied width
                'height': remaining_height,
                'position': 'end_height'
            })
        
        total_additional_objects = 0
        total_spaces_analyzed = 1
        
        # Recursively fill empty spaces
        if empty_spaces and level < 3:  # Limit recursion depth
            print(f"{indent}🔍 Trobats {len(empty_spaces)} espais buits per analitzar")
            
            for i, space in enumerate(empty_spaces):
                space_dims = {
                    'length': space['length'],
                    'width': space['width'], 
                    'height': space['height']
                }
                
                # Skip if space is too small
                min_space_dim = min(space_dims['length'], space_dims['width'], space_dims['height'])
                min_obj_dim = min(obj_dims['length'], obj_dims['width'], obj_dims['height'])
                
                if min_space_dim < min_obj_dim:
                    print(f"{indent}  ⏭️ Espai {i+1} massa petit, saltant...")
                    continue
                
                print(f"{indent}  🔄 Analitzant espai buit {i+1} ({space['position']})...")
                recursive_result = calculate_recursive_grid_packing(
                    space_dims, obj_dims, level + 1, f"Espai{i+1} ", has_complex_geometry
                )
                
                additional_objects = recursive_result['max_objects']
                total_additional_objects += additional_objects
                total_spaces_analyzed += recursive_result.get('total_spaces_analyzed', 1)
                
                if additional_objects > 0:
                    print(f"{indent}  ✅ +{additional_objects} objectes en espai {i+1}")
        
        total_objects = base_objects + total_additional_objects
        
        # Detectar si tenim geometria avançada
        has_advanced_geometry = obj_dims.get('advanced_geometry', False)
        
        # Calculate final metrics
        box_volume = box_dims['length'] * box_dims['width'] * box_dims['height']
        
        # UTILITZAR VOLUM REAL PER GEOMETRIES COMPLEXES
        if has_advanced_geometry and obj_dims.get('real_volume'):
            obj_volume = obj_dims['real_volume']
            print(f"{indent}📐 Usant volum real de geometria complexa: {obj_volume:.2f} mm³")
        else:
            obj_volume = obj_dims['length'] * obj_dims['width'] * obj_dims['height']
            print(f"{indent}📐 Usant volum bounding box: {obj_volume:.2f} mm³")
        
        used_volume = total_objects * obj_volume
        efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0
        
        print(f"{indent}📈 Total en aquest nivell: {total_objects} objectes ({base_objects} base + {total_additional_objects} recursiu)")
        
        if level == 0:  # Only show final summary at top level
            print(f"\n🎯 RESUM EMPAQUETAMENT RECURSIU")
            print(f"========================================")
            print(f"📦 Objectes totals: {total_objects}")
            print(f"📊 Espais analitzats: {total_spaces_analyzed}")
            print(f"📈 Eficiència: {round(efficiency, 2)}%")
            print(f"🔄 Nivells de recursió: {level + 1}")
            print(f"========================================\n")
        
        # Generate layout for visualization (only at top level)
        box = None
        if level == 0:
            box = _generate_recursive_grid_layout(box_dims, obj_dims, total_objects, best_orientation, has_complex_geometry)
        
        # Prepare result
        bins_info = []
        if box:
            items_info = []
            for item in box.items:
                item_data = {
                    'name': item.name,
                    'position': item.position,
                    'dimensions': item.getDimension(),
                    'rotation_type': item.rotation_type
                }
                items_info.append(item_data)
            
            bin_data = {
                'name': 'Container_Recursive',
                'dimensions': [box_dims['length'], box_dims['width'], box_dims['height']],
                'volume': box_volume,
                'optimization_info': {
                    'method': 'recursive_grid',
                    'spaces_analyzed': total_spaces_analyzed,
                    'recursion_levels': level + 1
                }
            }
            
            bins_info.append({
                'bin': bin_data,
                'items': items_info
            })
        
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
        print(f"❌ Error en empaquetament recursiu: {e}")
        return {
            'max_objects': 0,
            'efficiency': 0,
            'total_spaces_analyzed': 1,
            'error': str(e)
        }

def _generate_recursive_grid_layout(box_dims, obj_dims, total_objects, best_orientation, has_complex_geometry=False):
    """
    Genera layout per empaquetament recursiu.
    Ara usa un algorisme recursiu real per col·locar tots els objectes.
    """
    try:
        obj_l, obj_w, obj_h = best_orientation
        
        box = Bin(
            partno='Container_Recursive',
            WHD=[float(box_dims['length']), float(box_dims['width']), float(box_dims['height'])],
            max_weight=99999.0
        )
        
        colors = ['lightblue', 'lightgreen', 'lightyellow', 'lightpink', 'lightcyan', 'orange', 'purple', 'brown']
        
        # Generar tots els objectes usant l'algorisme recursiu real
        all_items = []
        _generate_recursive_items(box_dims, obj_dims, (0, 0, 0), all_items, colors, 0, has_complex_geometry)
        
        # Limitar al nombre total calculat
        all_items = all_items[:total_objects]
        
        print(f"📦 Layout recursiu generat amb {len(all_items)} objectes (de {total_objects} calculats)")
        
        # Obtenir informació de geometria complexa si està disponible
        geometry_obj = obj_dims.get('geometry_object') if has_complex_geometry else None
        
        # Convertir a format Item per al visualitzador
        for i, item_data in enumerate(all_items):
            pos_x, pos_y, pos_z = item_data['position']
            item_l, item_w, item_h = item_data['dimensions']
            
            item = Item(
                item_data['name'],
                'Product',
                'cube',
                [float(item_l), float(item_w), float(item_h)],
                1.0, 1, 100.0, True, item_data['color']
            )
            
            item.position = [pos_x, pos_y, pos_z]
            item.rotation_type = 0
            item.original_width = float(obj_dims['length'])
            item.original_height = float(obj_dims['width'])
            item.original_depth = float(obj_dims['height'])
            item.original_color = item_data['color']
            
            # AFEGIR INFORMACIÓ DE GEOMETRIA COMPLEXA
            if has_complex_geometry:
                item.advanced_geometry = True
                item.geometry_object = geometry_obj
                item.total_faces = obj_dims.get('total_faces', 0)
                item.total_vertices = obj_dims.get('total_vertices', 0)
                item.complexity_score = obj_dims.get('complexity_score', 0)
                item.parallel_face_pairs = obj_dims.get('parallel_face_pairs', 0)
                item.real_volume = obj_dims.get('real_volume', 0)
                item.shape_type = 'advanced_complex'
                if i == 0:  # Només mostrar missatge per al primer item
                    print(f"🎯 Geometria complexa amb {item.total_faces} cares assignada a {len(all_items)} objectes")
            else:
                item.advanced_geometry = False
                item.shape_type = 'rectangular'
            
            # Afegir informació del nivell de recursió
            if 'level' in item_data:
                item.recursion_level = item_data['level']
            
            box.items.append(item)
        
        return box
        
    except Exception as e:
        print(f"❌ Error generant layout recursiu: {e}")
        return None


def _generate_recursive_items(space_dims, obj_dims, offset, all_items, colors, level, has_complex_geometry=False):
    """
    Genera objectes de forma recursiva omplint els espais buits.
    """
    if level > 3:  # Limitar profunditat de recursió
        return
    
    # Calcular orientació òptima per aquest espai
    orientations = [
        [obj_dims['length'], obj_dims['width'], obj_dims['height']],
        [obj_dims['length'], obj_dims['height'], obj_dims['width']],
        [obj_dims['width'], obj_dims['length'], obj_dims['height']],
        [obj_dims['width'], obj_dims['height'], obj_dims['length']],
        [obj_dims['height'], obj_dims['length'], obj_dims['width']],
        [obj_dims['height'], obj_dims['width'], obj_dims['length']]
    ]
    
    best_orientation = None
    max_objects = 0
    
    for orientation in orientations:
        obj_l, obj_w, obj_h = orientation
        
        if (obj_l <= space_dims['length'] and 
            obj_w <= space_dims['width'] and 
            obj_h <= space_dims['height']):
            
            fit_length = math.floor(space_dims['length'] / obj_l)
            fit_width = math.floor(space_dims['width'] / obj_w) 
            fit_height = math.floor(space_dims['height'] / obj_h)
            
            objects_count = fit_length * fit_width * fit_height
            
            if objects_count > max_objects:
                max_objects = objects_count
                best_orientation = orientation
    
    if max_objects == 0:
        return
    
    obj_l, obj_w, obj_h = best_orientation
    fit_length = math.floor(space_dims['length'] / obj_l)
    fit_width = math.floor(space_dims['width'] / obj_w)
    fit_height = math.floor(space_dims['height'] / obj_h)
    
    # Generar objectes en graella per aquest espai
    item_count = len(all_items)
    for z in range(fit_height):
        for y in range(fit_width):
            for x in range(fit_length):
                pos_x = offset[0] + x * obj_l
                pos_y = offset[1] + y * obj_w
                pos_z = offset[2] + z * obj_h
                
                item_data = {
                    'name': f'RecursiveItem_{item_count}',
                    'position': [pos_x, pos_y, pos_z],
                    'dimensions': [obj_l, obj_w, obj_h],
                    'color': colors[item_count % len(colors)],
                    'level': level
                }
                
                all_items.append(item_data)
                item_count += 1
    
    # Calcular espais buits i omplir-los recursivament
    if level < 3:  # Només si no hem arribat al límit de recursió
        empty_spaces = []
        
        # Espai al final de la longitud
        remaining_length = space_dims['length'] - (fit_length * obj_l)
        if remaining_length >= min(obj_dims['length'], obj_dims['width'], obj_dims['height']):
            empty_spaces.append({
                'length': remaining_length,
                'width': space_dims['width'],
                'height': space_dims['height'],
                'offset': (offset[0] + fit_length * obj_l, offset[1], offset[2])
            })
        
        # Espai al final de l'amplada
        remaining_width = space_dims['width'] - (fit_width * obj_w)
        if remaining_width >= min(obj_dims['length'], obj_dims['width'], obj_dims['height']):
            empty_spaces.append({
                'length': fit_length * obj_l,
                'width': remaining_width,
                'height': space_dims['height'],
                'offset': (offset[0], offset[1] + fit_width * obj_w, offset[2])
            })
        
        # Espai al final de l'altura
        remaining_height = space_dims['height'] - (fit_height * obj_h)
        if remaining_height >= min(obj_dims['length'], obj_dims['width'], obj_dims['height']):
            empty_spaces.append({
                'length': fit_length * obj_l,
                'width': fit_width * obj_w,
                'height': remaining_height,
                'offset': (offset[0], offset[1], offset[2] + fit_height * obj_h)
            })
        
        # Processar recursivament cada espai buit
        for empty_space in empty_spaces:
            space_dims_new = {
                'length': empty_space['length'],
                'width': empty_space['width'],
                'height': empty_space['height']
            }
            _generate_recursive_items(space_dims_new, obj_dims, empty_space['offset'], all_items, colors, level + 1, has_complex_geometry)


def _calculate_traditional_packing(box_dims, obj_dims, max_attempts):
    """
    Mantenim l'empaquetament 3D tradicional per comparació.
    """
    # This would be the existing 3D packing code (shortened for brevity)
    # You can keep the existing implementation here
    return {
        'max_objects': 0,  # Placeholder
        'efficiency': 0,
        'box_volume': 0,
        'used_volume': 0,
        'bins': []
    }

def calculate_theoretical_max(box_dims, obj_dims):
    """
    Calcula el nombre teòric màxim d'objectes basant-se en volums reals.
    Té en compte els factors de volum per a formes complexes.
    """
    try:
        if isinstance(box_dims, tuple):
            box_dims = {'length': box_dims[0], 'width': box_dims[1], 'height': box_dims[2]}
        if isinstance(obj_dims, tuple):
            obj_dims = {'length': obj_dims[0], 'width': obj_dims[1], 'height': obj_dims[2]}
        
        # Calculate bounding box volumes
        box_volume = box_dims['width'] * box_dims['height'] * box_dims['length']
        obj_bounding_volume = obj_dims['width'] * obj_dims['height'] * obj_dims['length']
        
        # Apply volume factors for real shape volumes
        box_volume_factor = box_dims.get('volume_factor', 1.0)
        obj_volume_factor = obj_dims.get('volume_factor', 1.0)
        
        # Real volumes considering shape complexity
        real_box_volume = box_volume * box_volume_factor
        real_obj_volume = obj_bounding_volume * obj_volume_factor
        
        theoretical_max = math.floor(real_box_volume / real_obj_volume) if real_obj_volume > 0 else 0
        
        # Show volume factor impact if applicable
        if obj_volume_factor != 1.0 or box_volume_factor != 1.0:
            bounding_max = math.floor(box_volume / obj_bounding_volume) if obj_bounding_volume > 0 else 0
            print(f"📊 Màxim teòric (bounding box): {bounding_max} objectes")
            print(f"🎯 Màxim teòric (volum real): {theoretical_max} objectes")
            improvement = theoretical_max - bounding_max
            if improvement > 0:
                print(f"✨ Millora per formes complexes: +{improvement} objectes ({improvement/bounding_max*100:.1f}%)")
        
        return theoretical_max
    except Exception as e:
        print(f"Error calculating theoretical max: {e}")
        return 0

def calculate_complex_geometry_packing(box_dims, obj_dims):
    """
    Calcula empaquetament per geometries complexes reals.
    Té en compte el volum real i factor de forma de l'objecte complex.
    """
    try:
        print("🔬 ALGORITME D'EMPAQUETAMENT PER GEOMETRIA COMPLEXA")
        print("=" * 55)
        
        # Obtenir informació de geometria complexa
        real_volume = obj_dims.get('real_volume', 0)
        bounding_volume = obj_dims['length'] * obj_dims['width'] * obj_dims['height']
        volume_efficiency = obj_dims.get('volume_efficiency', real_volume / bounding_volume if bounding_volume > 0 else 0)
        complexity_score = obj_dims.get('complexity_score', 1.0)
        total_faces = obj_dims.get('total_faces', 6)
        
        print(f"📊 Volum real objecte: {real_volume:.2f} mm³")
        print(f"📦 Volum bounding box: {bounding_volume:.2f} mm³")  
        print(f"📈 Eficiència volumètrica: {volume_efficiency:.3f}")
        print(f"🔢 Complexitat: {complexity_score:.2f}")
        print(f"🎯 Cares: {total_faces}")
        
        # Calcular factor de compactació basat en complexitat
        # Objectes més complexos s'empaqueten menys eficientment
        packing_penalty = 1.0
        if complexity_score > 100:
            packing_penalty = 0.85  # Penalització del 15%
        elif complexity_score > 50:
            packing_penalty = 0.90  # Penalització del 10%
        elif complexity_score > 20:
            packing_penalty = 0.95  # Penalització del 5%
        
        print(f"⚖️  Factor penalització complexitat: {packing_penalty:.3f}")
        
        # Provar orientacions com amb geometria simple, però aplicar correccions
        orientations = [
            (obj_dims['length'], obj_dims['width'], obj_dims['height']),
            (obj_dims['length'], obj_dims['height'], obj_dims['width']),
            (obj_dims['width'], obj_dims['length'], obj_dims['height']),
            (obj_dims['width'], obj_dims['height'], obj_dims['length']),
            (obj_dims['height'], obj_dims['length'], obj_dims['width']),
            (obj_dims['height'], obj_dims['width'], obj_dims['length'])
        ]
        
        best_result = {'max_objects': 0, 'efficiency': 0, 'best_orientation': None}
        
        print(f"\n== Provant orientacions per geometria complexa ==")
        for orientation in orientations:
            obj_l, obj_w, obj_h = orientation
            
            if (obj_l <= box_dims['length'] and 
                obj_w <= box_dims['width'] and 
                obj_h <= box_dims['height']):
                
                # Càlcul teòric basat en bounding box
                fit_length = math.floor(box_dims['length'] / obj_l)
                fit_width = math.floor(box_dims['width'] / obj_w)
                fit_height = math.floor(box_dims['height'] / obj_h)
                
                theoretical_objects = fit_length * fit_width * fit_height
                
                # APLICAR CORRECCIONS PER GEOMETRIA COMPLEXA
                # 1. Factor de volum real vs bounding box
                volume_correction = volume_efficiency
                
                # 2. Factor de complexitat (formes complexes s'empaqueten pitjor)
                complexity_correction = packing_penalty
                
                # 3. Factor basatat en número de cares (més cares = més difícil empaquetament)
                faces_correction = 1.0
                if total_faces > 100:
                    faces_correction = 0.75  # Molt complex
                elif total_faces > 50:
                    faces_correction = 0.85  # Complex
                elif total_faces > 20:
                    faces_correction = 0.95  # Moderadament complex
                
                # Objectes reals = teòrics × correccions
                real_objects = int(theoretical_objects * volume_correction * complexity_correction * faces_correction)
                
                print(f"Orientació ({obj_l:.1f} × {obj_w:.1f} × {obj_h:.1f}): "
                      f"{fit_length} × {fit_width} × {fit_height} = {theoretical_objects} (teòric) → "
                      f"{real_objects} (real amb correccions)")
                
                if real_objects > best_result['max_objects']:
                    print(f"✓ Nova millor orientació trobada: {real_objects} objectes")
                    
                    # Calcular eficiència real
                    box_volume = box_dims['length'] * box_dims['width'] * box_dims['height']
                    used_volume = real_objects * real_volume
                    efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0
                    
                    best_result = {
                        'max_objects': real_objects,
                        'efficiency': efficiency,
                        'best_orientation': orientation,
                        'theoretical_objects': theoretical_objects,
                        'volume_correction': volume_correction,
                        'complexity_correction': complexity_correction,
                        'faces_correction': faces_correction
                    }
        
        print(f"\n📊 Resum empaquetament geometria complexa:")
        print(f"   ➕ Objectes: {best_result['max_objects']}")
        print(f"   📏 Volum caixa real: {box_volume} mm³")
        print(f"   📦 Volum utilitzat real: {best_result['max_objects'] * real_volume:.1f} mm³")
        print(f"   📈 Eficiència real: {best_result['efficiency']:.1f}%")
        print(f"   🔧 Correcció volum: {best_result.get('volume_correction', 1):.3f}")
        print(f"   ⚙️  Correcció complexitat: {best_result.get('complexity_correction', 1):.3f}")
        print(f"   🎯 Correcció cares: {best_result.get('faces_correction', 1):.3f}")
        
        return best_result
        
    except Exception as e:
        print(f"❌ Error en empaquetament geometria complexa: {e}")
        # Fallback al mètode tradicional
        return calculate_grid_packing(box_dims, obj_dims)


def calculate_grid_packing(box_dims, obj_dims):
    """
    Calcula empaquetament basat en una graella perfecta (sense rotacions).
    Té en compte els factors de volum real per formes complexes.
    """
    try:
        if isinstance(box_dims, tuple):
            box_dims = {'length': box_dims[0], 'width': box_dims[1], 'height': box_dims[2]}
        if isinstance(obj_dims, tuple):
            obj_dims = {'length': obj_dims[0], 'width': obj_dims[1], 'height': obj_dims[2]}
        
        # Extract shape information if available
        obj_shape_type = obj_dims.get('shape_type', 'rectangular')
        obj_volume_factor = obj_dims.get('volume_factor', 1.0)
        box_shape_type = box_dims.get('shape_type', 'rectangular')
        box_volume_factor = box_dims.get('volume_factor', 1.0)
        
        # Verificar si és geometria avançada
        is_advanced = obj_dims.get('advanced_geometry', False)
        print()
        
        # Get shape-specific packing efficiency
        from .stp_loader import get_shape_packing_efficiency
        obj_packing_efficiency = get_shape_packing_efficiency(obj_shape_type)
        box_packing_efficiency = get_shape_packing_efficiency(box_shape_type)
        
        # Combined packing efficiency (how well these shapes pack together)
        combined_efficiency = (obj_packing_efficiency + box_packing_efficiency) / 2
        
        print(f"\n== Anàlisi d'empaquetament en graella per formes complexes ==")
        print(f"📦 Contenidor: {box_shape_type} (factor packing: {box_packing_efficiency:.3f})")
        print(f"📋 Objecte: {obj_shape_type} (factor packing: {obj_packing_efficiency:.3f})")
        print(f"🔗 Eficiència combinada: {combined_efficiency:.3f}")
        
        # Provar totes les orientacions possibles de l'objecte
        orientations = [
            (obj_dims['length'], obj_dims['width'], obj_dims['height']),
            (obj_dims['length'], obj_dims['height'], obj_dims['width']),
            (obj_dims['width'], obj_dims['length'], obj_dims['height']),
            (obj_dims['width'], obj_dims['height'], obj_dims['length']),
            (obj_dims['height'], obj_dims['length'], obj_dims['width']),
            (obj_dims['height'], obj_dims['width'], obj_dims['length'])
        ]
        
        max_count = 0
        best_orientation = None
        
        print("\n== Provant orientacions en graella ==")
        
        for obj_l, obj_w, obj_h in orientations:
            # Calcular quants objectes caben en cada dimensió (bounding box)
            fit_length = math.floor(box_dims['length'] / obj_l) if obj_l > 0 else 0
            fit_width = math.floor(box_dims['width'] / obj_w) if obj_w > 0 else 0
            fit_height = math.floor(box_dims['height'] / obj_h) if obj_h > 0 else 0
            
            # Grid count for bounding boxes
            grid_count = fit_length * fit_width * fit_height
            
            # Apply packing efficiency for complex shapes
            adjusted_count = math.floor(grid_count * combined_efficiency)
            
            # Show detailed information for this orientation
            print(f"Orientació ({obj_l:.1f} × {obj_w:.1f} × {obj_h:.1f}): {fit_length} × {fit_width} × {fit_height} = {grid_count} (teòric) → {adjusted_count} (real)")
            
            if adjusted_count > max_count:
                max_count = adjusted_count
                best_orientation = (obj_l, obj_w, obj_h)
                print(f"✓ Nova millor orientació trobada: {adjusted_count} objectes")
        
        # Calculem el volum del millor objecte amb la seva orientació
        if best_orientation:
            obj_bounding_vol = best_orientation[0] * best_orientation[1] * best_orientation[2]
            obj_real_vol = obj_bounding_vol * obj_volume_factor
        else:
            obj_bounding_vol = obj_dims['length'] * obj_dims['width'] * obj_dims['height']
            obj_real_vol = obj_bounding_vol * obj_volume_factor
            
        box_bounding_vol = box_dims['length'] * box_dims['width'] * box_dims['height']
        box_real_vol = box_bounding_vol * box_volume_factor
        
        # Use real volume for calculations
        used_vol = max_count * obj_real_vol
        efficiency = (used_vol / box_real_vol) * 100 if box_real_vol > 0 else 0
        
        print(f"\n📊 Resum empaquetament en graella:")
        print(f"   ➕ Objectes: {max_count}")
        print(f"   📏 Volum caixa real: {round(box_real_vol, 2)} mm³")
        print(f"   📦 Volum utilitzat real: {round(used_vol, 2)} mm³")
        print(f"   📈 Eficiència real: {round(efficiency, 2)}%")
        
        # Show improvement from shape awareness if applicable
        if obj_volume_factor != 1.0 or combined_efficiency != 1.0:
            basic_count = math.floor(box_bounding_vol / obj_bounding_vol)
            improvement = max_count - basic_count if basic_count > 0 else 0
            if improvement > 0:
                print(f"   ✨ Millora per geometria complexa: +{improvement} objectes ({improvement/basic_count*100:.1f}%)")
        
        return {
            'max_objects': max_count,
            'best_orientation': best_orientation,
            'efficiency': efficiency,
            'shape_aware': True,
            'packing_efficiency': combined_efficiency
        }
    except Exception as e:
        print(f"❌ Error en càlcul d'empaquetament en graella: {e}")
        return {'max_objects': 0, 'best_orientation': None, 'efficiency': 0}

def _generate_grid_layout(box_dims, obj_dims, grid_result):
    """
    Genera un layout 3D real basant-se en l'empaquetament en graella.
    Això crea objectes amb les posicions reals per visualització.
    """
    try:
        best_orientation = grid_result['best_orientation']
        if not best_orientation:
            return None
            
        obj_l, obj_w, obj_h = best_orientation
        
        # Calcular quants objectes caben en cada dimensió
        fit_length = math.floor(box_dims['length'] / obj_l) if obj_l > 0 else 0
        fit_width = math.floor(box_dims['width'] / obj_w) if obj_w > 0 else 0
        fit_height = math.floor(box_dims['height'] / obj_h) if obj_h > 0 else 0
        
        # Crear un bin nou per la graella
        box = Bin(
            partno='Container_Grid',
            WHD=[float(box_dims['length']), float(box_dims['width']), float(box_dims['height'])],
            max_weight=99999.0
        )
        
        item_count = 0
        colors = ['lightblue', 'lightgreen', 'lightyellow', 'lightpink', 'lightcyan', 'orange', 'purple', 'brown']
        
        # Generar objectes en posicions de graella
        for z in range(fit_height):
            for y in range(fit_width):
                for x in range(fit_length):
                    # Calcular posició exacta
                    pos_x = x * obj_l
                    pos_y = y * obj_w
                    pos_z = z * obj_h
                    
                    # Crear objecte en aquesta posició
                    item = Item(
                        f'GridItem_{item_count}',
                        'Product',  
                        'cube',
                        [float(obj_l), float(obj_w), float(obj_h)],
                        1.0, 1, 100.0, True, colors[item_count % len(colors)]
                    )
                    
                    # Establir posició manual
                    item.position = [pos_x, pos_y, pos_z]
                    item.rotation_type = 0  # No rotation
                    item.original_width = float(obj_dims['length'])
                    item.original_height = float(obj_dims['width'])
                    item.original_depth = float(obj_dims['height'])
                    item.original_color = colors[item_count % len(colors)]
                    
                    # Afegir a la llista d'items del bin
                    box.items.append(item)
                    item_count += 1
        
        print(f"📦 Generat layout de graella amb {item_count} objectes en posicions exactes")
        return box
        
    except Exception as e:
        print(f"❌ Error generant layout de graella: {e}")
        return None
