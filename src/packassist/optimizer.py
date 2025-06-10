import sys
import os
# Add the src directory to Python path for py3dbp_enhanced
current_dir = os.path.dirname(__file__)
src_dir = os.path.join(current_dir, '..')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
from py3dbp_enhanced.main import Packer, Bin, Item
import math
import signal
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
        
        # Mostrem info de les dimensions    
        print("\n🧮 CÀLCUL D'EMPAQUETAMENT AVANÇAT")
        print("========================================")
        print(f"📦 Contenidor: {box_dims['length']} × {box_dims['width']} × {box_dims['height']} mm")
        print(f"   Forma: {box_shape_type}, Factor volum: {box_volume_factor:.3f}")
        print(f"📋 Objecte: {obj_dims['length']} × {obj_dims['width']} × {obj_dims['height']} mm")
        print(f"   Forma: {obj_shape_type}, Factor volum: {obj_volume_factor:.3f}")
        
        # Show real vs bounding box volume difference
        if obj_volume_factor != 1.0:
            efficiency_gain = (1.0 - obj_volume_factor) * 100
            print(f"🎯 Guany d'eficiència per forma complexa: +{efficiency_gain:.1f}%")
        
        print("========================================\n")
            
        # Per a contenidors grans i objectes petits, necessitem més intents
        # Calculem un nombre raonable basat en el màxim teòric
        if max_attempts is None:
            theoretical = calculate_theoretical_max(box_dims, obj_dims)
            # Utilitzem un límit raonable (millor resultat de grid packing)
            grid_result = calculate_grid_packing(box_dims, obj_dims)
            
            # Si hi ha molts objectes, limitem els intents de l'empaquetament 3D però creem la visualització real
            if grid_result['max_objects'] > 500:
                print(f"⚠️ S'ha detectat un empaquetament gran (>500 objectes). Utilitzarem un algoritme optimitzat per rendiment.")
                print(f"⌛ Generant visualització real basada en l'empaquetament optimitzat...")
                
                # Creem un empaquetament real amb un nombre limitat d'objectes per rendiment
                MAX_REAL_ITEMS = min(200, grid_result['max_objects'])  # Limitem a 200 per rendiment
                print(f"📊 Es processaran {MAX_REAL_ITEMS} objectes amb l'algoritme 3D real")
                print(f"ℹ️ Resultat final estimat: {grid_result['max_objects']} objectes")
            else:
                MAX_REAL_ITEMS = grid_result['max_objects']
            
            # Si són pocs objectes, procedim amb l'empaquetament 3D
            max_attempts = min(MAX_REAL_ITEMS, 500)  # Limitem a 500 objectes per rendiment
            max_attempts = max(max_attempts, 50)  # Mínim 50 intents
            print(f"🔢 Nombre d'intents ajustat: {max_attempts} (màxim teòric: {theoretical})")
        else:
            # Calculate grid result if not done yet
            grid_result = calculate_grid_packing(box_dims, obj_dims)
        
        # Reduced strategies for better performance
        strategies = [
            # Strategy 1: High stability (most reliable)
            {'bigger_first': True, 'fix_point': True, 'check_stable': True, 'support_surface_ratio': 0.85},
            # Strategy 2: Balanced approach
            {'bigger_first': True, 'fix_point': True, 'check_stable': False, 'support_surface_ratio': 0.5},
            # Strategy 3: Aggressive packing (fastest)
            {'bigger_first': True, 'fix_point': False, 'check_stable': False, 'support_surface_ratio': 0.1},
        ]
        
        best_result = None
        best_count = 0
        
        # Reduced orientations - focus on most promising ones
        box_orientations = [
            [box_dims['length'], box_dims['width'], box_dims['height']],  # Original
            [box_dims['width'], box_dims['length'], box_dims['height']],  # Rotate 90°
            [box_dims['height'], box_dims['width'], box_dims['length']],  # Different height
        ]
        
        obj_orientations = [
            [obj_dims['length'], obj_dims['width'], obj_dims['height']],  # Original
            [obj_dims['width'], obj_dims['length'], obj_dims['height']],  # Rotate 90°
            [obj_dims['height'], obj_dims['width'], obj_dims['length']],  # Different height
        ]
        
        print("\n== Provant empaquetament 3D ==")
        
        # Utilitzem la millor orientació de la graella com a guia (si està disponible)
        grid_orientation = grid_result.get('best_orientation') if grid_result and 'best_orientation' in grid_result else None
        
        if grid_orientation:
            # Si tenim una orientació òptima de la graella, la prioritzem
            print(f"ℹ️ Utilitzant l'orientació òptima de graella: {grid_orientation}")
            obj_orientations = [list(grid_orientation)]  # Només provem aquesta orientació
        
        # Només provarem una estratègia per accelerar el procés
        strategy = strategies[0]  # Estratègia d'alta estabilitat
        
        progress_step = max(1, max_attempts // 10)
        for box_orientation in box_orientations:
            for obj_orientation in obj_orientations:
                print(f"🧪 Provant: Box: {box_orientation}, Obj: {obj_orientation}")
                
                packer = Packer()
                box = Bin(
                    partno='Container',
                    WHD=[float(box_orientation[0]), float(box_orientation[1]), float(box_orientation[2])],
                    max_weight=99999.0
                )
                packer.addBin(box)
                
                # Add items with progress feedback
                print(f"⏳ Afegint {max_attempts} objectes...")
                for i in range(max_attempts):
                    obj = Item(
                        f'Product_{i}',
                        'Product',  # Same name for all items
                        'cube',
                        [float(obj_orientation[0]), float(obj_orientation[1]), float(obj_orientation[2])],
                        1.0, 1, 100.0, True, 'lightblue'  # Consistent color for all items
                    )
                    # Mark original dimensions for visual consistency
                    obj.original_width = float(obj_dims['length'])
                    obj.original_height = float(obj_dims['width']) 
                    obj.original_depth = float(obj_dims['height'])
                    # Assignem colors diferents per millor visualització
                    colors = ['lightblue', 'lightgreen', 'lightyellow', 'lightpink', 'lightcyan']
                    obj.original_color = colors[i % len(colors)]
                    packer.addItem(obj)
                    
                    # Show progress
                    if (i + 1) % progress_step == 0 or i == max_attempts - 1:
                        print(f"   → {i+1}/{max_attempts} objectes afegits ({int((i+1)/max_attempts*100)}%)")
                
                print(f"⏳ Empaquetant utilitzant estratègia: {strategy}...")
                packer.pack(**strategy)
                current_count = len(box.items)
                
                # Mostrem el resultat de cada prova per terminal
                print(f"✅ Resultat: {current_count} objectes empaquetats")
                    
                if current_count > best_count:
                    best_count = current_count
                    best_result = {
                        'packer': packer,
                        'box': box,
                        'strategy': strategy,
                        'box_orientation': box_orientation,
                        'obj_orientation': obj_orientation,
                        'count': current_count
                    }
                    print(f"✅ Millor resultat trobat fins ara: {current_count} objectes!")
            
            # Per a grans contenidors, comprovem si el resultat és prou bo per sortir
            if best_count >= max_attempts * 0.8:  # Si empaqueta 80% d'objectes, és prou bo
                print(f"ℹ️ S'ha assolit un resultat suficientment bo (>80%). Finalitzant càlcul.")
                break
        
        # Usar el millor resultat trobat
        if best_result:
            box = best_result['box']
            packed_items = best_result['count']
        else:
            # Fallback a estratègia simple si res funciona
            packer = Packer()
            box = Bin(
                partno='Container',
                WHD=[float(box_dims['length']), float(box_dims['width']), float(box_dims['height'])],
                max_weight=99999.0
            )
            packer.addBin(box)
            
            for i in range(max_attempts):
                obj = Item(
                    f'Product_{i}',
                    'Product',  # Same name for all items
                    'cube',
                    [float(obj_dims['length']), float(obj_dims['width']), float(obj_dims['height'])],
                    1.0, 1, 100.0, True, 'lightblue'  # Consistent color for all items
                )
                # Mark original dimensions for visual consistency
                obj.original_width = float(obj_dims['length'])
                obj.original_height = float(obj_dims['width'])
                obj.original_depth = float(obj_dims['height'])
                obj.original_color = 'lightblue'
                packer.addItem(obj)
            
            packer.pack(bigger_first=True, fix_point=True, check_stable=True, support_surface_ratio=0.75)
            packed_items = len(box.items)
        
        # Calculate final results
        packed_items = len(box.items) if box.items else 0
        
        # Calculate volumes (only once)
        box_volume = box_dims['width'] * box_dims['height'] * box_dims['length']
        obj_volume = obj_dims['width'] * obj_dims['height'] * obj_dims['length']
        
        # Ensure we have grid result
        if 'grid_result' not in locals() or grid_result is None:
            grid_result = calculate_grid_packing(box_dims, obj_dims)
        
        print("\n=== RESULTATS FINALS ===")
        print(f"📊 Empaquetament 3D: {packed_items} objectes")
        print(f"📏 Empaquetament en graella: {grid_result['max_objects']} objectes")
        print(f"📐 Orientació òptima en graella: {grid_result['best_orientation']}")
        
        # Use the better result between 3D packing and grid packing
        if grid_result['max_objects'] > packed_items:
            print(f"✅ Utilitzant resultat d'empaquetament en graella: {grid_result['max_objects']} objectes (millor que 3D: {packed_items})")
            final_count = grid_result['max_objects']
            # Generate grid layout for visualization
            box = _generate_grid_layout(box_dims, obj_dims, grid_result)
        else:
            final_count = packed_items
            print(f"✅ Utilitzant resultat d'empaquetament 3D: {packed_items} objectes (millor que graella: {grid_result['max_objects']})")
        
        # Calculate final metrics
        used_volume = final_count * obj_volume
        efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0
        
        print(f"\n🧮 RESUM DEL CÀLCUL D'EMPAQUETAMENT")
        print(f"========================================")
        print(f"📦 Contenidor: {box_dims['length']} × {box_dims['width']} × {box_dims['height']} mm")
        print(f"📋 Objecte: {obj_dims['length']} × {obj_dims['width']} × {obj_dims['height']} mm")
        print(f"✅ Màxim real (empaquetament): {final_count} unitats")
        print(f"📈 Eficiència d'espai: {round(efficiency, 2)}%")
        print(f"📏 Volum contenidor: {round(box_volume, 2)} mm³")
        print(f"📦 Volum utilitzat: {round(used_volume, 2)} mm³")
        print(f"========================================\n")
        
        bins_info = []
        items_info = []
        
        bin_data = {
            'name': 'Container',
            'dimensions': [box_dims['length'], box_dims['width'], box_dims['height']],
            'volume': box_volume,
            'optimization_info': {
                'strategy_used': best_result['strategy'] if best_result else 'fallback',
                'box_orientation': best_result['box_orientation'] if best_result else 'original',
                'obj_orientation': best_result['obj_orientation'] if best_result else 'original',
                'attempts_tested': len(strategies) * 9  # 3 strategies * 3 box orientations * 3 object orientations
            }
        }
        
        for item in box.items:
            item_data = {
                'name': item.name,
                'position': item.position,
                'dimensions': item.getDimension(),
                'rotation_type': item.rotation_type
            }
            items_info.append(item_data)
        
        bins_info.append({
            'bin': bin_data,
            'items': items_info
        })
        
        return {
            'max_objects': final_count,
            'efficiency': round(efficiency, 2),
            'box_volume': round(box_volume, 2),
            'used_volume': round(used_volume, 2),
            'bins': bins_info,
            'error': None
        }
        
    except Exception as e:
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
