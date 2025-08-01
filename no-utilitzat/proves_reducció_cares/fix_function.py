#!/usr/bin/env python3
"""
Script per arreglar la funció _update_dimensions_from_intelligent_box
"""

def fix_function():
    """Arregla la funció per preservar la geometria complexa."""
    
    # Llegir el fitxer
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # La funció actual (simplificada per la cerca)
    old_function = '''    def _update_dimensions_from_intelligent_box(self, result):
        """
        Actualitza les dimensions de l'objecte amb la caixa generada.

        Args:
            result: BoxGenerationResult amb la informació de la caixa
        """
        try:
            # Calcular bounding box de la caixa generada
            vertices = result.vertices
            min_coords = np.min(vertices, axis=0)
            max_coords = np.max(vertices, axis=0)

            # Calcular dimensions
            length = max_coords[0] - min_coords[0]
            width = max_coords[1] - min_coords[1]
            height = max_coords[2] - min_coords[2]

            # Actualitzar variables de l'entrada manual
            self.obj_vars[0].set(length)  # Longitud
            self.obj_vars[1].set(width)   # Amplada
            self.obj_vars[2].set(height)  # Altura

            # Actualitzar informació del fitxer
            info_text = (
                f"Caixa Intel·ligent: {length:.1f} x {width:.1f} x {height:.1f} mm | "
                f"{result.face_count} cares, {result.efficiency:.1f}% eficiència 🎯"
            )
            self.file_info_var.set(info_text)

            print(f"🔄 Dimensions actualitzades: {length:.1f} x {width:.1f} x {height:.1f} mm")

        except Exception as e:
            print(f"❌ Error actualitzant dimensions: {e}")
            self.update_status("Error actualitzant dimensions de la caixa generada")'''
    
    # Nova funció millorada
    new_function = '''    def _update_dimensions_from_intelligent_box(self, result):
        """
        Actualitza les dimensions de l'objecte amb la caixa generada.

        Args:
            result: BoxGenerationResult amb la informació de la caixa
        """
        try:
            # Calcular bounding box de la caixa generada
            vertices = result.vertices
            min_coords = np.min(vertices, axis=0)
            max_coords = np.max(vertices, axis=0)

            # Calcular dimensions
            length = max_coords[0] - min_coords[0]
            width = max_coords[1] - min_coords[1]
            height = max_coords[2] - min_coords[2]

            # Actualitzar variables de l'entrada manual
            self.obj_vars[0].set(length)  # Longitud
            self.obj_vars[1].set(width)   # Amplada
            self.obj_vars[2].set(height)  # Altura

            # IMPORTANT: Actualitzar la geometria complexa amb la nova caixa intel·ligent
            if hasattr(self, 'current_complex_geometry'):
                # Crear un nou mesh amb la caixa intel·ligent
                try:
                    import trimesh
                    # Crear mesh de la nova caixa intel·ligent
                    intelligent_mesh = trimesh.Trimesh(vertices=result.vertices, faces=result.faces)
                    
                    # Actualitzar geometria complexa amb informació de la caixa intel·ligent
                    self.current_complex_geometry.update({
                        'length': length,
                        'width': width,
                        'height': height,
                        'shape_type': 'intelligent_box',  # Marcar com caixa intel·ligent
                        'volume_factor': result.efficiency / 100.0,  # Usar eficiència com factor de volum
                        'advanced_geometry': True,
                        'total_faces': result.face_count,
                        'geometry_object': intelligent_mesh,  # Usar el nou mesh
                        'real_volume': result.box_volume,
                        'complexity_score': result.face_count,
                        'intelligent_box_result': result  # Guardar el resultat complet
                    })
                    print(f"🎯 Geometria actualitzada amb caixa intel·ligent de {result.face_count} cares")
                except Exception as mesh_error:
                    print(f"⚠️  Error creant mesh de la caixa: {mesh_error}")
                    # Fallback: actualitzar només les dimensions
                    self.current_complex_geometry.update({
                        'length': length,
                        'width': width,
                        'height': height,
                        'shape_type': 'intelligent_box_simple',
                        'volume_factor': result.efficiency / 100.0
                    })

            # Actualitzar informació del fitxer
            info_text = (
                f"Caixa Intel·ligent: {length:.1f} x {width:.1f} x {height:.1f} mm | "
                f"{result.face_count} cares, {result.efficiency:.1f}% eficiència 🎯"
            )
            self.file_info_var.set(info_text)

            print(f"🔄 Dimensions actualitzades: {length:.1f} x {width:.1f} x {height:.1f} mm")

        except Exception as e:
            print(f"❌ Error actualitzant dimensions: {e}")
            self.update_status("Error actualitzant dimensions de la caixa generada")'''
    
    # Substituir la funció
    if old_function in content:
        new_content = content.replace(old_function, new_function)
        
        # Escriure el fitxer actualitzat
        with open('app.py', 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("✅ Funció actualitzada correctament!")
        return True
    else:
        print("❌ No s'ha trobat la funció exacta per substituir")
        return False

if __name__ == "__main__":
    fix_function()
