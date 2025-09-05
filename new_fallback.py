def _fallback_optimization_new(self, mesh, box_dims_dict, max_pieces, use_floor_mode, margin, floor_separation):
    """Optimització de fallback NOVA i SIMPLIFICADA"""
    import time
    start_time = time.time()
    
    print(f"🔄 Usant optimització de fallback NOVA amb separació {floor_separation}mm")
    
    # === CALCULAR OBB OPTIMITZAT ===
    try:
        obb_result = self._compute_optimized_obb_fallback(mesh)
        obj_dims = obb_result['final_dims']
        oriented_mesh = obb_result['oriented_mesh']
        print(f"✅ Usant dimensions OBB: {obj_dims[0]:.1f} × {obj_dims[1]:.1f} × {obj_dims[2]:.1f}")
        used_obb = True
    except Exception as e:
        print(f"⚠️ Error amb OBB, usant AABB: {e}")
        bounds = mesh.bounds
        obj_dims = bounds[1] - bounds[0]
        oriented_mesh = mesh
        print(f"✅ Usant dimensions AABB: {obj_dims[0]:.1f} × {obj_dims[1]:.1f} × {obj_dims[2]:.1f}")
        used_obb = False
    
    # === ALGORISME DE BIN PACKING SIMPLE I ROBUST ===
    print(f"📦 Iniciant algorisme de bin packing robust...")
    
    # Dimensions del contenidor
    container_length = box_dims_dict['length']
    container_width = box_dims_dict['width'] 
    container_height = box_dims_dict['height']
    
    # Dimensions de la peça (sense marges)
    piece_length = obj_dims[0]
    piece_width = obj_dims[1]
    piece_height = obj_dims[2]
    
    print(f"   Contenidor: {container_length} × {container_width} × {container_height}")
    print(f"   Peça: {piece_length:.1f} × {piece_width:.1f} × {piece_height:.1f}")
    
    # Calcular quantes peces caben en cada dimensió (sense margin)
    pieces_x = int(container_length // piece_length)
    pieces_y = int(container_width // piece_width)
    pieces_z = int(container_height // piece_height)
    
    max_theoretical_pieces = pieces_x * pieces_y * pieces_z
    target_pieces = min(max_pieces if max_pieces else max_theoretical_pieces, max_theoretical_pieces)
    
    print(f"   Graella teòrica: {pieces_x} × {pieces_y} × {pieces_z} = {max_theoretical_pieces} peces")
    print(f"   Objectiu: {target_pieces} peces")
    
    # === GENERAR POSICIONS AMB BOTTOM-LEFT-FRONT ALGORITHM ===
    positions = []
    rotations = []
    pieces_placed = 0
    
    for z in range(pieces_z):
        for y in range(pieces_y):
            for x in range(pieces_x):
                if pieces_placed >= target_pieces:
                    break
                    
                # Calcular posició del centre de la peça
                pos_x = x * piece_length + piece_length / 2
                pos_y = y * piece_width + piece_width / 2
                pos_z = z * piece_height + piece_height / 2
                
                # Verificació ESTRICTA: la peça ha de estar completament dins
                max_x = pos_x + piece_length / 2
                max_y = pos_y + piece_width / 2
                max_z = pos_z + piece_height / 2
                
                if (max_x <= container_length and 
                    max_y <= container_width and 
                    max_z <= container_height):
                    
                    positions.append([pos_x, pos_y, pos_z])
                    rotations.append([0, 0, 0])  # Sense rotació per ara
                    pieces_placed += 1
                    
                    # Debug per les primeres peces
                    if pieces_placed <= 3:
                        print(f"      ✅ Peça {pieces_placed}: centre=({pos_x:.1f}, {pos_y:.1f}, {pos_z:.1f}), límits=({max_x:.1f}, {max_y:.1f}, {max_z:.1f})")
                else:
                    print(f"      ❌ Peça en ({pos_x:.1f}, {pos_y:.1f}, {pos_z:.1f}) surtiria del contenidor")
                    
            if pieces_placed >= target_pieces:
                break
        if pieces_placed >= target_pieces:
            break
    
    # === CALCULAR RESULTATS ===
    total_time = time.time() - start_time
    
    # Calcular eficiència
    piece_volume = piece_length * piece_width * piece_height
    used_volume = len(positions) * piece_volume
    container_volume = container_length * container_width * container_height
    efficiency = (used_volume / container_volume) * 100 if container_volume > 0 else 0
    
    # Preparar resultat
    result = {
        'positions': positions,
        'rotations': rotations,
        'efficiency': efficiency / 100,  # Convertir a fracció
        'pieces_count': len(positions),
        'execution_time': total_time,
        'method': f'fallback_{"OBB" if used_obb else "AABB"}_{"floor" if use_floor_mode else "bulk"}_mode',
        'box_dims': {
            'length': container_length,
            'width': container_width,
            'height': container_height,
            'volume': container_volume
        },
        'obj_dims': {
            'length': piece_length,
            'width': piece_width,
            'height': piece_height,
            'volume': piece_volume
        },
        'used_obb': used_obb,
        'margin': margin,
        'floor_separation': floor_separation,
        'mode': 'floor_mode' if use_floor_mode else 'bulk_mode'
    }
    
    print(f"✅ Optimització de fallback NOVA completada: {len(positions)} peces en {total_time:.2f}s")
    print(f"📊 Eficiència: {efficiency:.1f}% - Volum utilitzat: {used_volume:.0f}/{container_volume:.0f} mm³")
    
    return result
