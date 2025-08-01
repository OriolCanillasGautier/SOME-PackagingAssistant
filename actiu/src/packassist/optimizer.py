"""
PackAssist Optimizer - Versió millorada
Sistema d'optimització avançat per bin packing 3D
Basat en la versió estable amb millores de rendiment
"""

import sys
import os
import math
import time

# Configurar path per py3dbp_enhanced
current_dir = os.path.dirname(__file__)
src_dir = os.path.join(current_dir, '..')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from py3dbp_enhanced.main import Packer, Bin, Item
    PY3DBP_AVAILABLE = True
except ImportError:
    PY3DBP_AVAILABLE = False
    print("Warning: py3dbp_enhanced no disponible, usant algorisme bàsic")


def optimize_packing(box_dims, obj_dims, max_attempts=None):
    """
    Optimitza l'empaquetament d'objectes en un contenidor.
    Versió millorada amb millor gestió d'errors i output net.
    """
    try:
        # Convertir a diccionaris si són tuples
        if isinstance(box_dims, tuple):
            box_dims = {'length': box_dims[0], 'width': box_dims[1], 'height': box_dims[2]}
        if isinstance(obj_dims, tuple):
            obj_dims = {'length': obj_dims[0], 'width': obj_dims[1], 'height': obj_dims[2]}
        
        # Extraure informació de forma si està disponible
        obj_shape_type = obj_dims.get('shape_type', 'rectangular')
        obj_volume_factor = obj_dims.get('volume_factor', 1.0)
        box_shape_type = box_dims.get('shape_type', 'rectangular')
        box_volume_factor = box_dims.get('volume_factor', 1.0)
        
        # Detectar geometria complexa
        has_advanced_geometry = obj_dims.get('advanced_geometry', False)
        
        # Mostrar informació del càlcul
        print("\\n" + "="*60)
        print("🧮 CÀLCUL D'EMPAQUETAMENT AVANÇAT")
        print("="*60)
        print(f"📦 Contenidor: {box_dims['length']} × {box_dims['width']} × {box_dims['height']} mm")
        print(f"   Tipus: {box_shape_type}, Factor volum: {box_volume_factor:.3f}")
        
        if has_advanced_geometry:
            print(f"📋 Objecte COMPLEX: {obj_dims['length']} × {obj_dims['width']} × {obj_dims['height']} mm")
            print(f"   🎯 Geometria avançada detectada")
            print(f"   📊 Cares: {obj_dims.get('total_faces', 0)}, Vèrtexs: {obj_dims.get('total_vertices', 0)}")
            print(f"   🔗 Cares paral·leles: {obj_dims.get('parallel_face_pairs', 0)}")
            print(f"   💾 Volum real: {obj_dims.get('real_volume', 0):.2f} mm³")
            print(f"   ⚖️ Factor volum: {obj_volume_factor:.3f}")
            print(f"   🧮 Complexitat: {obj_dims.get('complexity_score', 0):.2f}")
        else:
            print(f"📋 Objecte: {obj_dims['length']} × {obj_dims['width']} × {obj_dims['height']} mm")
            print(f"   Tipus: {obj_shape_type}, Factor volum: {obj_volume_factor:.3f}")
        
        print("="*60)
        
        # Provar empaquetament recursiu amb ompliment d'espais buits
        print("🔍 Provant empaquetament recursiu...")
        recursive_result = calculate_recursive_grid_packing(box_dims, obj_dims, 
                                                           has_complex_geometry=has_advanced_geometry)
        
        # Provar empaquetament 3D tradicional si està disponible
        if PY3DBP_AVAILABLE:
            print("🔍 Provant empaquetament 3D tradicional...")
            traditional_result = _calculate_traditional_packing(box_dims, obj_dims, max_attempts)
        else:
            traditional_result = {'max_objects': 0}
        
        # Utilitzar el millor resultat
        if recursive_result['max_objects'] >= traditional_result['max_objects']:
            print(f"✅ Utilitzant empaquetament recursiu: {recursive_result['max_objects']} objectes")
            final_result = recursive_result
        else:
            print(f"✅ Utilitzant empaquetament 3D: {traditional_result['max_objects']} objectes")
            final_result = traditional_result
        
        print("="*60)
        return final_result
        
    except Exception as e:
        print(f"❌ Error en l'optimització: {str(e)}")
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
    Versió millorada amb suport per geometria complexa.
    """
    try:
        indent = "  " * level
        if level == 0:
            print(f"{indent}🔍 Analitzant espai principal: {box_dims['length']} × {box_dims['width']} × {box_dims['height']}")
        
        if has_complex_geometry and level == 0:
            print(f"{indent}🎯 Usant geometria complexa real")
            geometry_obj = obj_dims.get('geometry_object')
            if geometry_obj:
                print(f"{indent}   📊 Objecte amb geometria avançada")
                print(f"{indent}   🔗 Cares paral·leles: {obj_dims.get('parallel_face_pairs', 0)}")
                print(f"{indent}   📦 Factor volum real: {obj_dims.get('volume_factor', 1.0):.3f}")
        
        # Calcular empaquetament bàsic per aquest espai
        if has_complex_geometry:
            if level == 0:
                print(f"{indent}🔬 Geometria complexa: usant algorisme avançat")
            grid_result = calculate_complex_geometry_packing(box_dims, obj_dims)
        else:
            grid_result = calculate_grid_packing(box_dims, obj_dims)
        
        if grid_result['max_objects'] == 0:
            return grid_result
        
        total_objects = grid_result['max_objects']
        all_bins = grid_result.get('bins', [])
        
        # Trobar espais buits per omplir recursivament
        if level < 2:  # Limitar recursió
            empty_spaces = _find_empty_spaces(box_dims, obj_dims, grid_result)
            
            for space in empty_spaces:
                if level == 0:
                    print(f"{indent}🔄 Analitzant espai buit: {space['length']:.1f} × {space['width']:.1f} × {space['height']:.1f}")
                
                sub_result = calculate_recursive_grid_packing(space, obj_dims, level + 1, 
                                                            "Sub-espai ", has_complex_geometry)
                
                if sub_result['max_objects'] > 0:
                    total_objects += sub_result['max_objects']
                    all_bins.extend(sub_result.get('bins', []))
                    if level == 0:
                        print(f"{indent}✅ Espai buit omplert amb {sub_result['max_objects']} objectes")
        
        # Calcular volums finals
        obj_volume = obj_dims['length'] * obj_dims['width'] * obj_dims['height']
        box_volume = box_dims['length'] * box_dims['width'] * box_dims['height']
        used_volume = total_objects * obj_volume
        efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0
        
        result = {
            'max_objects': total_objects,
            'efficiency': efficiency,
            'box_volume': box_volume,
            'used_volume': used_volume,
            'bins': all_bins,
            'algorithm': 'recursive_grid_advanced' if has_complex_geometry else 'recursive_grid'
        }
        
        return result
        
    except Exception as e:
        print(f"❌ Error en empaquetament recursiu: {str(e)}")
        return {
            'max_objects': 0,
            'efficiency': 0.0,
            'box_volume': 0.0,
            'used_volume': 0.0,
            'bins': [],
            'error': str(e)
        }


def calculate_complex_geometry_packing(box_dims, obj_dims):
    """
    Algorisme específic per geometries complexes.
    Usa informació avançada quan està disponible.
    """
    try:
        # Factor de correcció per geometria complexa
        complexity_factor = obj_dims.get('complexity_score', 1.0)
        volume_factor = obj_dims.get('volume_factor', 1.0)
        
        # Calcular empaquetament base
        base_result = calculate_grid_packing(box_dims, obj_dims)
        
        # Aplicar correcció per complexitat
        if complexity_factor > 1.5:  # Geometria molt complexa
            correction = 0.85  # Reducció del 15%
        elif complexity_factor > 1.2:  # Geometria moderadament complexa
            correction = 0.92  # Reducció del 8%
        else:
            correction = 0.97  # Reducció mínima del 3%
        
        # Aplicar correcció per factor de volum
        volume_correction = min(volume_factor, 1.0)
        total_correction = correction * volume_correction
        
        # Ajustar resultats
        adjusted_objects = int(base_result['max_objects'] * total_correction)
        
        print(f"     🔬 Factor complexitat: {complexity_factor:.2f}")
        print(f"     📦 Factor volum: {volume_factor:.3f}")
        print(f"     ⚖️ Correcció total: {total_correction:.3f}")
        print(f"     📋 Objectes ajustats: {base_result['max_objects']} → {adjusted_objects}")
        
        result = base_result.copy()
        result['max_objects'] = adjusted_objects
        result['algorithm'] = 'complex_geometry'
        
        # Recalcular eficiència
        if result['box_volume'] > 0:
            obj_volume = obj_dims['length'] * obj_dims['width'] * obj_dims['height']
            result['used_volume'] = adjusted_objects * obj_volume
            result['efficiency'] = (result['used_volume'] / result['box_volume']) * 100
        
        return result
        
    except Exception as e:
        print(f"❌ Error en algorisme de geometria complexa: {str(e)}")
        return calculate_grid_packing(box_dims, obj_dims)


def calculate_grid_packing(box_dims, obj_dims):
    """
    Calcula empaquetament en graella bàsic.
    Versió millorada amb millor gestió de dimensions.
    """
    try:
        # Assegurar que tenim diccionaris
        if isinstance(box_dims, tuple):
            box_dims = {'length': box_dims[0], 'width': box_dims[1], 'height': box_dims[2]}
        if isinstance(obj_dims, tuple):
            obj_dims = {'length': obj_dims[0], 'width': obj_dims[1], 'height': obj_dims[2]}
        
        box_length = float(box_dims['length'])
        box_width = float(box_dims['width'])
        box_height = float(box_dims['height'])
        
        obj_length = float(obj_dims['length'])
        obj_width = float(obj_dims['width'])
        obj_height = float(obj_dims['height'])
        
        # Calcular quants objectes caben en cada dimensió
        objects_x = int(box_length // obj_length)
        objects_y = int(box_width // obj_width)
        objects_z = int(box_height // obj_height)
        
        total_objects = objects_x * objects_y * objects_z
        
        # Calcular volums
        box_volume = box_length * box_width * box_height
        obj_volume = obj_length * obj_width * obj_height
        used_volume = total_objects * obj_volume
        efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0
        
        # Crear estructura de bins amb posicions
        bins = []
        if total_objects > 0:
            items = []
            item_id = 0
            
            for x in range(objects_x):
                for y in range(objects_y):
                    for z in range(objects_z):
                        position = [
                            x * obj_length,
                            y * obj_width,
                            z * obj_height
                        ]
                        
                        items.append({
                            'id': item_id,
                            'position': position,
                            'dimensions': [obj_length, obj_width, obj_height],
                            'rotation': [0, 0, 0]
                        })
                        item_id += 1
            
            bins.append({
                'bin': {
                    'id': 0,
                    'dimensions': [box_length, box_width, box_height]
                },
                'items': items
            })
        
        return {
            'max_objects': total_objects,
            'efficiency': efficiency,
            'box_volume': box_volume,
            'used_volume': used_volume,
            'bins': bins,
            'distribution': {
                'x': objects_x,
                'y': objects_y,
                'z': objects_z
            },
            'algorithm': 'grid_packing'
        }
        
    except Exception as e:
        print(f"❌ Error en empaquetament en graella: {str(e)}")
        return {
            'max_objects': 0,
            'efficiency': 0.0,
            'box_volume': 0.0,
            'used_volume': 0.0,
            'bins': [],
            'error': str(e)
        }


def calculate_theoretical_max(box_dims, obj_dims):
    """
    Calcula el màxim teòric d'objectes per volum.
    """
    try:
        if isinstance(box_dims, tuple):
            box_dims = {'length': box_dims[0], 'width': box_dims[1], 'height': box_dims[2]}
        if isinstance(obj_dims, tuple):
            obj_dims = {'length': obj_dims[0], 'width': obj_dims[1], 'height': obj_dims[2]}
        
        box_volume = box_dims['length'] * box_dims['width'] * box_dims['height']
        obj_volume = obj_dims['length'] * obj_dims['width'] * obj_dims['height']
        
        return int(box_volume // obj_volume) if obj_volume > 0 else 0
        
    except Exception as e:
        print(f"❌ Error calculant màxim teòric: {str(e)}")
        return 0


def _calculate_traditional_packing(box_dims, obj_dims, max_attempts=None):
    """
    Empaquetament 3D tradicional usant py3dbp_enhanced.
    """
    try:
        if not PY3DBP_AVAILABLE:
            return {'max_objects': 0, 'error': 'py3dbp_enhanced no disponible'}
        
        # Configurar packer
        packer = Packer()
        
        # Crear contenidor
        bin_name = "Container"
        packer.add_bin(Bin(bin_name, 
                          box_dims['length'], 
                          box_dims['width'], 
                          box_dims['height'], 
                          max_weight=1000000))
        
        # Afegir objectes per provar
        test_quantities = [1000, 500, 100, 50] if max_attempts is None else [max_attempts]
        
        for quantity in test_quantities:
            packer_test = Packer()
            packer_test.add_bin(Bin(bin_name, 
                                   box_dims['length'], 
                                   box_dims['width'], 
                                   box_dims['height'], 
                                   max_weight=1000000))
            
            # Afegir elements
            for i in range(quantity):
                packer_test.add_item(Item(f"Item_{i}", 
                                        obj_dims['length'], 
                                        obj_dims['width'], 
                                        obj_dims['height'], 
                                        weight=1))
            
            # Executar empaquetament
            packer_test.pack(bigger_first=True, distribute_items=True)
            
            # Obtenir resultats
            packed_items = []
            for bin_item in packer_test.bins:
                for item in bin_item.items:
                    packed_items.append({
                        'id': item.name,
                        'position': [item.position[0], item.position[1], item.position[2]],
                        'dimensions': [item.width, item.height, item.depth],
                        'rotation': item.rotation_type
                    })
            
            if len(packed_items) == quantity:
                # Tot va caber, provar amb més
                continue
            else:
                # Hem trobat el límit
                max_objects = len(packed_items)
                break
        else:
            # Tot va caber fins al final
            max_objects = quantity
        
        # Calcular estadístiques
        obj_volume = obj_dims['length'] * obj_dims['width'] * obj_dims['height']
        box_volume = box_dims['length'] * box_dims['width'] * box_dims['height']
        used_volume = max_objects * obj_volume
        efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0
        
        # Crear estructura de bins
        bins = []
        if packed_items:
            bins.append({
                'bin': {
                    'id': 0,
                    'dimensions': [box_dims['length'], box_dims['width'], box_dims['height']]
                },
                'items': packed_items[:max_objects]
            })
        
        return {
            'max_objects': max_objects,
            'efficiency': efficiency,
            'box_volume': box_volume,
            'used_volume': used_volume,
            'bins': bins,
            'algorithm': 'py3dbp_enhanced'
        }
        
    except Exception as e:
        print(f"❌ Error en empaquetament tradicional: {str(e)}")
        return {
            'max_objects': 0,
            'efficiency': 0.0,
            'box_volume': 0.0,
            'used_volume': 0.0,
            'bins': [],
            'error': str(e)
        }


def _find_empty_spaces(box_dims, obj_dims, packing_result):
    """
    Troba espais buits que es poden omplir amb més objectes.
    """
    try:
        empty_spaces = []
        
        # Obtenir distribució
        distribution = packing_result.get('distribution', {})
        objects_x = distribution.get('x', 0)
        objects_y = distribution.get('y', 0)
        objects_z = distribution.get('z', 0)
        
        if objects_x == 0 or objects_y == 0 or objects_z == 0:
            return empty_spaces
        
        # Dimensions utilitzades
        used_length = objects_x * obj_dims['length']
        used_width = objects_y * obj_dims['width']
        used_height = objects_z * obj_dims['height']
        
        # Espais buits en cada dimensió
        remaining_length = box_dims['length'] - used_length
        remaining_width = box_dims['width'] - used_width
        remaining_height = box_dims['height'] - used_height
        
        # Espai al final (dimensió X)
        if remaining_length >= obj_dims['length']:
            empty_spaces.append({
                'length': remaining_length,
                'width': box_dims['width'],
                'height': box_dims['height']
            })
        
        # Espai al costat (dimensió Y)
        if remaining_width >= obj_dims['width']:
            empty_spaces.append({
                'length': used_length,
                'width': remaining_width,
                'height': box_dims['height']
            })
        
        # Espai a dalt (dimensió Z)
        if remaining_height >= obj_dims['height']:
            empty_spaces.append({
                'length': used_length,
                'width': used_width,
                'height': remaining_height
            })
        
        # Filtrar espais massa petits
        min_volume = obj_dims['length'] * obj_dims['width'] * obj_dims['height']
        empty_spaces = [space for space in empty_spaces 
                       if space['length'] * space['width'] * space['height'] >= min_volume]
        
        return empty_spaces
        
    except Exception as e:
        print(f"❌ Error trobant espais buits: {str(e)}")
        return []
