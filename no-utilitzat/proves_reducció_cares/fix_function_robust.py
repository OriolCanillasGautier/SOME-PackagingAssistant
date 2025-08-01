#!/usr/bin/env python3
"""
Script per arreglar la funció _update_dimensions_from_intelligent_box amb una estratègia diferent
"""

def fix_function_robust():
    """Arregla la funció localitzant-la per línies."""
    
    # Llegir el fitxer
    with open('app.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Buscar la funció
    start_line = None
    for i, line in enumerate(lines):
        if 'def _update_dimensions_from_intelligent_box' in line:
            start_line = i
            break
    
    if start_line is None:
        print("❌ Funció no trobada")
        return False
    
    # Trobar el final de la funció
    end_line = len(lines)
    indent_level = len(lines[start_line]) - len(lines[start_line].lstrip())
    
    for i in range(start_line + 1, len(lines)):
        line = lines[i]
        if line.strip() == "":
            continue
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= indent_level and line.strip():
            end_line = i
            break
    
    print(f"🔍 Funció trobada des de la línia {start_line + 1} fins a {end_line}")
    
    # Nova funció
    new_function_lines = [
        "    def _update_dimensions_from_intelligent_box(self, result):\n",
        "        \"\"\"\n",
        "        Actualitza les dimensions de l'objecte amb la caixa generada.\n",
        "\n",
        "        Args:\n",
        "            result: BoxGenerationResult amb la informació de la caixa\n",
        "        \"\"\"\n",
        "        try:\n",
        "            # Calcular bounding box de la caixa generada\n",
        "            vertices = result.vertices\n",
        "            min_coords = np.min(vertices, axis=0)\n",
        "            max_coords = np.max(vertices, axis=0)\n",
        "\n",
        "            # Calcular dimensions\n",
        "            length = max_coords[0] - min_coords[0]\n",
        "            width = max_coords[1] - min_coords[1]\n",
        "            height = max_coords[2] - min_coords[2]\n",
        "\n",
        "            # Actualitzar variables de l'entrada manual\n",
        "            self.obj_vars[0].set(length)  # Longitud\n",
        "            self.obj_vars[1].set(width)   # Amplada\n",
        "            self.obj_vars[2].set(height)  # Altura\n",
        "\n",
        "            # IMPORTANT: Actualitzar la geometria complexa amb la nova caixa intel·ligent\n",
        "            if hasattr(self, 'current_complex_geometry'):\n",
        "                # Crear un nou mesh amb la caixa intel·ligent\n",
        "                try:\n",
        "                    import trimesh\n",
        "                    # Crear mesh de la nova caixa intel·ligent\n",
        "                    intelligent_mesh = trimesh.Trimesh(vertices=result.vertices, faces=result.faces)\n",
        "                    \n",
        "                    # Actualitzar geometria complexa amb informació de la caixa intel·ligent\n",
        "                    self.current_complex_geometry.update({\n",
        "                        'length': length,\n",
        "                        'width': width,\n",
        "                        'height': height,\n",
        "                        'shape_type': 'intelligent_box',  # Marcar com caixa intel·ligent\n",
        "                        'volume_factor': result.efficiency / 100.0,  # Usar eficiència com factor de volum\n",
        "                        'advanced_geometry': True,\n",
        "                        'total_faces': result.face_count,\n",
        "                        'geometry_object': intelligent_mesh,  # Usar el nou mesh\n",
        "                        'real_volume': result.box_volume,\n",
        "                        'complexity_score': result.face_count,\n",
        "                        'intelligent_box_result': result  # Guardar el resultat complet\n",
        "                    })\n",
        "                    print(f\"🎯 Geometria actualitzada amb caixa intel·ligent de {result.face_count} cares\")\n",
        "                except Exception as mesh_error:\n",
        "                    print(f\"⚠️  Error creant mesh de la caixa: {mesh_error}\")\n",
        "                    # Fallback: actualitzar només les dimensions\n",
        "                    self.current_complex_geometry.update({\n",
        "                        'length': length,\n",
        "                        'width': width,\n",
        "                        'height': height,\n",
        "                        'shape_type': 'intelligent_box_simple',\n",
        "                        'volume_factor': result.efficiency / 100.0\n",
        "                    })\n",
        "\n",
        "            # Actualitzar informació del fitxer\n",
        "            info_text = (\n",
        "                f\"Caixa Intel·ligent: {length:.1f} x {width:.1f} x {height:.1f} mm | \"\n",
        "                f\"{result.face_count} cares, {result.efficiency:.1f}% eficiència 🎯\"\n",
        "            )\n",
        "            self.file_info_var.set(info_text)\n",
        "\n",
        "            print(f\"🔄 Dimensions actualitzades: {length:.1f} x {width:.1f} x {height:.1f} mm\")\n",
        "\n",
        "        except Exception as e:\n",
        "            print(f\"❌ Error actualitzant dimensions: {e}\")\n",
        "            self.update_status(\"Error actualitzant dimensions de la caixa generada\")\n",
        "\n"
    ]
    
    # Substituir les línies
    new_lines = lines[:start_line] + new_function_lines + lines[end_line:]
    
    # Escriure el fitxer
    with open('app.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print("✅ Funció actualitzada correctament!")
    return True

if __name__ == "__main__":
    fix_function_robust()
