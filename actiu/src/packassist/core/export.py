"""
Funcions d'exportació de resultats
"""

import os
import json
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional
import trimesh
import numpy as np

from ..utils.config import EXPORT_CONFIG
from ..utils.file_manager import generate_timestamp_filename

class ResultsExporter:
    """Classe per exportar resultats d'optimització"""
    
    def __init__(self):
        self.timestamp_format = EXPORT_CONFIG['timestamp_format']
    
    def export_detailed_report(self, filepath: str, results: Dict[str, Any], 
                             include_visualizations: bool = False) -> bool:
        """Exporta un informe detallat en format text"""
        try:
            positions = results.get('positions', [])
            rotations = results.get('rotations', [])
            efficiency = results.get('efficiency', 0)
            method = results.get('method', 'desconegut')
            box_dims = results.get('box_dims', {})
            obj_dims = results.get('obj_dims', {})
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("PACKASSIST - INFORME DE RESULTATS\n")
                f.write("=" * 60 + "\n\n")
                
                f.write(f"Data d'exportació: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
                f.write(f"Mètode d'optimització: {method}\n")
                f.write(f"Eficiència aconseguida: {efficiency:.2f}%\n")
                f.write(f"Nombre de peces col·locades: {len(positions)}\n\n")
                
                # Dimensions del contenidor
                if box_dims:
                    f.write("DIMENSIONS DEL CONTENIDOR:\n")
                    f.write("-" * 30 + "\n")
                    f.write(f"Longitud: {box_dims.get('length', 0):.2f} mm\n")
                    f.write(f"Amplada: {box_dims.get('width', 0):.2f} mm\n")
                    f.write(f"Altura: {box_dims.get('height', 0):.2f} mm\n")
                    volume_box = box_dims.get('length', 0) * box_dims.get('width', 0) * box_dims.get('height', 0)
                    f.write(f"Volum total: {volume_box:.2f} mm³\n\n")
                
                # Dimensions de l'objecte
                if obj_dims:
                    f.write("DIMENSIONS DE L'OBJECTE:\n")
                    f.write("-" * 30 + "\n")
                    f.write(f"Longitud: {obj_dims.get('length', 0):.2f} mm\n")
                    f.write(f"Amplada: {obj_dims.get('width', 0):.2f} mm\n")
                    f.write(f"Altura: {obj_dims.get('height', 0):.2f} mm\n")
                    volume_obj = obj_dims.get('volume', 0)
                    f.write(f"Volum: {volume_obj:.2f} mm³\n\n")
                
                # Detalls de cada peça
                f.write("POSICIONS DE LES PECES:\n")
                f.write("-" * 30 + "\n")
                f.write("Peça | X (mm) | Y (mm) | Z (mm) | Rot.X | Rot.Y | Rot.Z\n")
                f.write("-" * 60 + "\n")
                
                for i, (pos, rot) in enumerate(zip(positions, rotations)):
                    f.write(f"{i+1:4d} | {pos[0]:6.1f} | {pos[1]:6.1f} | {pos[2]:6.1f} | "
                           f"{rot[0]:5.0f} | {rot[1]:5.0f} | {rot[2]:5.0f}\n")
                
                f.write("\n" + "=" * 60 + "\n")
                f.write("Fi de l'informe\n")
                f.write("=" * 60 + "\n")
            
            return True
            
        except Exception as e:
            print(f"Error exportant informe detallat: {e}")
            return False
    
    def export_csv_data(self, filepath: str, positions: List, rotations: List) -> bool:
        """Exporta dades en format CSV"""
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Capçalera
                writer.writerow(['Peça', 'X_mm', 'Y_mm', 'Z_mm', 'Rotació_X', 'Rotació_Y', 'Rotació_Z'])
                
                # Dades
                for i, (pos, rot) in enumerate(zip(positions, rotations)):
                    writer.writerow([i+1, pos[0], pos[1], pos[2], rot[0], rot[1], rot[2]])
            
            return True
            
        except Exception as e:
            print(f"Error exportant CSV: {e}")
            return False
    
    def export_json_data(self, filepath: str, results: Dict[str, Any]) -> bool:
        """Exporta dades en format JSON estructurat"""
        try:
            # Preparar dades serializables
            export_data = {
                'metadata': {
                    'export_date': datetime.now().isoformat(),
                    'version': '1.0',
                    'software': 'PackAssist'
                },
                'optimization_results': {
                    'efficiency': results.get('efficiency', 0),
                    'method': results.get('method', 'unknown'),
                    'pieces_count': len(results.get('positions', [])),
                    'box_dimensions': results.get('box_dims', {}),
                    'object_dimensions': results.get('obj_dims', {})
                },
                'pieces': []
            }
            
            # Afegir dades de cada peça
            positions = results.get('positions', [])
            rotations = results.get('rotations', [])
            
            for i, (pos, rot) in enumerate(zip(positions, rotations)):
                piece_data = {
                    'id': i + 1,
                    'position': {'x': pos[0], 'y': pos[1], 'z': pos[2]},
                    'rotation': {'x': rot[0], 'y': rot[1], 'z': rot[2]}
                }
                export_data['pieces'].append(piece_data)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Error exportant JSON: {e}")
            return False
    
    def export_positioned_stl(self, filepath: str, original_mesh: trimesh.Trimesh, 
                            positions: List, rotations: List) -> bool:
        """Exporta un STL amb totes les peces posicionades"""
        try:
            combined_meshes = []
            
            for pos, rot in zip(positions, rotations):
                # Crear còpia de la malla
                piece_mesh = original_mesh.copy()
                
                # Aplicar rotacions
                if rot[0] != 0:
                    piece_mesh = piece_mesh.apply_transform(
                        trimesh.transformations.rotation_matrix(np.radians(rot[0]), [1, 0, 0])
                    )
                if rot[1] != 0:
                    piece_mesh = piece_mesh.apply_transform(
                        trimesh.transformations.rotation_matrix(np.radians(rot[1]), [0, 1, 0])
                    )
                if rot[2] != 0:
                    piece_mesh = piece_mesh.apply_transform(
                        trimesh.transformations.rotation_matrix(np.radians(rot[2]), [0, 0, 1])
                    )
                
                # Aplicar translació
                piece_mesh = piece_mesh.apply_translation(pos)
                combined_meshes.append(piece_mesh)
            
            # Combinar totes les malles
            if combined_meshes:
                final_mesh = trimesh.util.concatenate(combined_meshes)
                final_mesh.export(filepath)
                return True
            
            return False
            
        except Exception as e:
            print(f"Error exportant STL posicionat: {e}")
            return False
    
    def export_3d_image(self, filepath: str, mesh: trimesh.Trimesh, 
                       positions: List, rotations: List) -> bool:
        """Exporta una imatge de la visualització 3D"""
        try:
            import pyvista as pv
            import numpy as np
            
            # Crear visualitzador sense mostrar
            plotter = pv.Plotter(off_screen=True, window_size=(1920, 1080))
            plotter.set_background('white')
            
            # Convertir trimesh a pyvista
            def trimesh_to_pyvista(tmesh):
                faces_pv = np.column_stack(([3] * len(tmesh.faces), tmesh.faces)).flatten()
                return pv.PolyData(tmesh.vertices, faces_pv)
            
            base_mesh_pv = trimesh_to_pyvista(mesh)
            
            # Afegir cada peça
            for i, (pos, rot) in enumerate(zip(positions, rotations)):
                piece_mesh = base_mesh_pv.copy()
                
                # Aplicar transformacions
                if rot != [0, 0, 0]:
                    rx, ry, rz = rot
                    if rx != 0:
                        piece_mesh = piece_mesh.rotate_x(rx, inplace=False)
                    if ry != 0:
                        piece_mesh = piece_mesh.rotate_y(ry, inplace=False)
                    if rz != 0:
                        piece_mesh = piece_mesh.rotate_z(rz, inplace=False)
                
                piece_mesh = piece_mesh.translate(pos, inplace=False)
                
                # Color basat en altura
                z_positions = [p[2] for p in positions]
                z_min, z_max = min(z_positions), max(z_positions)
                z_range = z_max - z_min if z_max > z_min else 1
                height_ratio = (pos[2] - z_min) / z_range
                color = [height_ratio, 0.2, 1.0 - height_ratio]
                
                plotter.add_mesh(piece_mesh, color=color, opacity=0.8)
            
            plotter.camera_position = 'iso'
            plotter.screenshot(filepath, transparent_background=False)
            plotter.close()
            
            return True
            
        except ImportError:
            print("PyVista no disponible per exportar imatges")
            return False
        except Exception as e:
            print(f"Error exportant imatge 3D: {e}")
            return False
