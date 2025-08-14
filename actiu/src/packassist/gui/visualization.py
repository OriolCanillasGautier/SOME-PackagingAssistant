"""
Mòdul de visualització 3D
"""

import numpy as np
from typing import List, Dict, Any, Optional
import tkinter as tk
from tkinter import messagebox

from ..utils.config import VISUALIZATION_CONFIG, COLOR_PALETTE

class Visualizer3D:
    """Classe per gestionar la visualització 3D"""
    
    def __init__(self):
        self.config = VISUALIZATION_CONFIG
    
    def show_direct_3d(self, results: Dict[str, Any], mesh) -> bool:
        """Mostra directament la visualització 3D amb defaults intel·ligents"""
        positions = results.get('positions', [])
        rotations = results.get('rotations', [])
        box_dims = results.get('box_dims', {})
        
        if not positions:
            messagebox.showwarning("Avís", "No hi ha peces col·locades per visualitzar")
            return False
        
        num_pieces = len(positions)
        
        # Defaults intel·ligents
        show_wireframe = True
        show_labels = num_pieces <= self.config['max_pieces_for_labels']
        use_gradient = num_pieces > self.config['max_pieces_for_gradient']
        
        print(f"🎮 Visualització directa: {num_pieces} peces")
        print(f"   - Etiquetes: {'Sí' if show_labels else 'No'}")
        print(f"   - Gradient: {'Sí' if use_gradient else 'No'}")
        
        return self._render_3d_scene_direct(mesh, positions, rotations, box_dims, 
                                          show_wireframe, show_labels, use_gradient)
    
    def show_3d_with_options(self, results: Dict[str, Any], mesh, **options) -> bool:
        """Mostra la visualització 3D amb opcions personalitzades del diàleg"""
        positions = results.get('positions', [])
        rotations = results.get('rotations', [])
        box_dims = results.get('box_dims', {})
        
        if not positions:
            messagebox.showwarning("Avís", "No hi ha peces col·locades per visualitzar")
            return False
        
        num_pieces = len(positions)
        print(f"🎮 Visualització amb opcions: {num_pieces} peces")
        
        # Extreure opcions amb valors per defecte
        show_wireframe = options.get('show_wireframe', True)
        show_labels = options.get('show_labels', True)
        show_axes = options.get('show_axes', True)
        show_grid = options.get('show_grid', True)
        show_edges = options.get('show_edges', False)
        
        color_scheme = options.get('color_scheme', 'solid')
        background_color = options.get('background_color', 'white')
        window_size = options.get('window_size', '1200x900')
        
        auto_screenshot = options.get('auto_screenshot', False)
        auto_stl_export = options.get('auto_stl_export', False)
        auto_json_export = options.get('auto_json_export', False)
        auto_csv_export = options.get('auto_csv_export', False)
        
        # Parsejar mida de finestra
        try:
            width, height = map(int, window_size.split('x'))
        except:
            width, height = 1200, 900
        
        print(f"   - Colors: {color_scheme}")
        print(f"   - Fons: {background_color}")
        print(f"   - Mida: {width}x{height}")
        
        success = self._render_3d_scene_advanced(mesh, positions, rotations, box_dims, 
                                                show_wireframe, show_labels, show_axes, 
                                                show_grid, show_edges, color_scheme, 
                                                background_color, (width, height))
        
        # Exportacions automàtiques
        if success and (auto_stl_export or auto_json_export or auto_csv_export):
            self._handle_auto_exports(results, mesh, auto_stl_export, 
                                    auto_json_export, auto_csv_export)
        
        return success

    def _render_3d_scene_direct(self, mesh, positions: List, rotations: List, 
                               box_dims: Dict, show_wireframe: bool, show_labels: bool,
                               use_gradient: bool) -> bool:
        """Renderitza l'escena 3D directament"""
        try:
            import pyvista as pv
            
            num_pieces = len(positions)
            print(f"🎮 Renderitzant {num_pieces} peces...")
            
            # Optimització per moltes peces
            if num_pieces > self.config['performance_warning_threshold']:
                response = messagebox.askyesno(
                    "Moltes peces detectades",
                    f"S'han trobat {num_pieces} peces.\n\n"
                    f"Visualitzar totes pot ser lent.\n"
                    f"Vols continuar?\n\n"
                    f"• SÍ: Visualitzar totes\n"
                    f"• NO: Visualitzar només les primeres {self.config['performance_warning_threshold']}"
                )
                if not response:
                    positions = positions[:self.config['performance_warning_threshold']]
                    rotations = rotations[:self.config['performance_warning_threshold']]
                    num_pieces = self.config['performance_warning_threshold']
            
            # Crear visualitzador
            plotter = pv.Plotter(window_size=self.config['default_window_size'])
            plotter.set_background(self.config['background_color'])
            
            # Afegir contenidor (wireframe)
            if box_dims and show_wireframe:
                box = pv.Box(bounds=[0, box_dims['length'], 0, box_dims['width'], 0, box_dims['height']])
                plotter.add_mesh(box, style='wireframe', color='black', line_width=3, opacity=0.5)
            
            # Convertir mesh a PyVista
            base_mesh_pv = self._trimesh_to_pyvista(mesh)
            
            # Renderitzar peces
            if num_pieces <= 50 and not use_gradient:
                self._render_unique_colors(plotter, base_mesh_pv, positions, rotations, show_labels)
            else:
                self._render_gradient_colors(plotter, base_mesh_pv, positions, rotations, show_labels)
            
            # Informació i llegenda
            self._add_scene_info(plotter, num_pieces, use_gradient)
            
            # Configurar vista
            plotter.camera_position = 'iso'
            plotter.show_grid()
            plotter.add_axes()
            
            # Mostrar
            plotter.show(interactive=True, auto_close=False)
            
            return True
            
        except ImportError:
            messagebox.showerror("Error", "PyVista no està instal·lat.\nInstal·la'l amb: pip install pyvista")
            return False
        except Exception as e:
            messagebox.showerror("Error", f"Error en la visualització 3D:\n{e}")
            return False
    
    def _render_3d_scene_with_custom_options(self, mesh, positions: List, rotations: List, 
                                           box_dims: Dict, show_container: bool, 
                                           show_piece_numbers: bool, color_scheme: str) -> bool:
        """Renderitza l'escena 3D amb opcions personalitzades del diàleg"""
        try:
            import pyvista as pv
            
            num_pieces = len(positions)
            print(f"🎮 Renderitzant {num_pieces} peces amb opcions personalitzades...")
            
            # Crear visualitzador
            plotter = pv.Plotter(window_size=(1000, 700))
            plotter.set_background('white')
            plotter.add_axes()
            plotter.show_grid()
            
            # Mostrar contenidor si està activat
            if box_dims and show_container:
                box = pv.Box(bounds=[0, box_dims['length'], 0, box_dims['width'], 0, box_dims['height']])
                plotter.add_mesh(box, style='wireframe', color='black', line_width=3, opacity=0.7)
            
            # Convertir mesh a PyVista
            base_mesh_pv = self._trimesh_to_pyvista(mesh)
            
            # Definir colors segons l'esquema
            if color_scheme == 'blue':
                colors = ['lightblue'] * num_pieces
            elif color_scheme == 'green':
                colors = ['lightgreen'] * num_pieces
            else:  # colorful
                colors = [COLOR_PALETTE[i % len(COLOR_PALETTE)] for i in range(num_pieces)]
            
            # Renderitzar peces
            for i, (pos, rot) in enumerate(zip(positions, rotations)):
                piece_mesh = base_mesh_pv.copy()
                
                # Aplicar rotacions
                piece_mesh = self._apply_rotations(piece_mesh, rot)
                
                # Aplicar translació
                piece_mesh = piece_mesh.translate(pos, inplace=False)
                
                # Afegir malla amb color personalitzat
                plotter.add_mesh(piece_mesh, color=colors[i], opacity=0.8, show_edges=False)
                
                # Afegir números si està activat
                if show_piece_numbers:
                    plotter.add_point_labels([pos], [f'{i+1}'], point_size=8, font_size=10, text_color='black')
            
            # Títol personalitzat
            title = f"PackAssist - {num_pieces} peces"
            if not show_container:
                title += " (sense contenidor)"
            if color_scheme != 'colorful':
                title += f" - Colors {color_scheme}"
            
            plotter.add_text(title, position='upper_edge', font_size=14, color='black')
            
            # Configurar vista
            plotter.camera_position = 'iso'
            
            # Mostrar
            plotter.show(interactive=True, auto_close=False)
            
            return True
            
        except ImportError:
            messagebox.showerror("Error", "PyVista no està instal·lat.\nInstal·la'l amb: pip install pyvista")
            return False
        except Exception as e:
            messagebox.showerror("Error", f"Error en la visualització 3D personalitzada:\n{e}")
            return False
        """Renderitza l'escena 3D"""
        try:
            import pyvista as pv
            
            num_pieces = len(positions)
            print(f"🎮 Renderitzant {num_pieces} peces...")
            
            # Optimització per moltes peces
            if num_pieces > self.config['performance_warning_threshold']:
                response = messagebox.askyesno(
                    "Moltes peces detectades",
                    f"S'han trobat {num_pieces} peces.\n\n"
                    f"Visualitzar totes pot ser lent.\n"
                    f"Vols continuar?\n\n"
                    f"• SÍ: Visualitzar totes\n"
                    f"• NO: Visualitzar només les primeres {self.config['performance_warning_threshold']}"
                )
                if not response:
                    positions = positions[:self.config['performance_warning_threshold']]
                    rotations = rotations[:self.config['performance_warning_threshold']]
                    num_pieces = self.config['performance_warning_threshold']
            
            # Crear visualitzador
            plotter = pv.Plotter(window_size=self.config['default_window_size'])
            plotter.set_background(self.config['background_color'])
            
            # Afegir contenidor (wireframe)
            if box_dims and show_wireframe:
                box = pv.Box(bounds=[0, box_dims['length'], 0, box_dims['width'], 0, box_dims['height']])
                plotter.add_mesh(box, style='wireframe', color='black', line_width=3, opacity=0.5)
            
            # Convertir mesh a PyVista
            base_mesh_pv = self._trimesh_to_pyvista(mesh)
            
            # Renderitzar peces
            if num_pieces <= 50 and not use_gradient:
                self._render_unique_colors(plotter, base_mesh_pv, positions, rotations, show_labels)
            else:
                self._render_gradient_colors(plotter, base_mesh_pv, positions, rotations, show_labels)
            
            # Informació i llegenda
            self._add_scene_info(plotter, num_pieces, use_gradient)
            
            # Configurar vista
            plotter.camera_position = 'iso'
            plotter.show_grid()
            plotter.add_axes()
            
            # Captura automàtica si cal
            if auto_screenshot:
                self._auto_screenshot(plotter)
            
            # Mostrar
            plotter.show(interactive=True, auto_close=False)
            
            return True
            
        except ImportError:
            messagebox.showerror("Error", "PyVista no està instal·lat.\nInstal·la'l amb: pip install pyvista")
            return False
        except Exception as e:
            messagebox.showerror("Error", f"Error en la visualització 3D:\n{e}")
            return False
    
    def _render_unique_colors(self, plotter, base_mesh_pv, positions: List, 
                            rotations: List, show_labels: bool):
        """Renderitza amb colors únics per cada peça (colors sòlids com pestanyes 1 i 2)"""
        for i, (pos, rot) in enumerate(zip(positions, rotations)):
            piece_mesh = base_mesh_pv.copy()
            
            # Aplicar rotacions
            piece_mesh = self._apply_rotations(piece_mesh, rot)
            
            # Aplicar translació
            piece_mesh = piece_mesh.translate(pos, inplace=False)
            
            # Color únic sòlid (com pestanyes 1 i 2)
            color_index = i % len(COLOR_PALETTE)
            color = COLOR_PALETTE[color_index]
            
            # Afegir malla amb colors sòlids
            plotter.add_mesh(piece_mesh, color=color, opacity=1.0, show_edges=False)
            
            # Etiquetes cada 5 peces per no saturar
            if show_labels and i % 5 == 0:
                plotter.add_point_labels([pos], [f"P{i+1}"], point_size=6, font_size=8)
    
    def _render_gradient_colors(self, plotter, base_mesh_pv, positions: List,
                              rotations: List, show_labels: bool):
        """Renderitza amb gradient de colors basat en altura"""
        # Calcular rang d'altures
        z_positions = [pos[2] for pos in positions]
        z_min, z_max = min(z_positions), max(z_positions)
        z_range = z_max - z_min if z_max > z_min else 1
        
        for i, (pos, rot) in enumerate(zip(positions, rotations)):
            piece_mesh = base_mesh_pv.copy()
            
            # Aplicar rotacions
            piece_mesh = self._apply_rotations(piece_mesh, rot)
            
            # Aplicar translació
            piece_mesh = piece_mesh.translate(pos, inplace=False)
            
            # Color basat en altura (gradient blau->vermell)
            height_ratio = (pos[2] - z_min) / z_range
            color = [height_ratio, 0.2, 1.0 - height_ratio]
            
            # Afegir malla
            plotter.add_mesh(piece_mesh, color=color, opacity=0.6, show_edges=False)
            
            # Etiquetes cada 20 peces
            if show_labels and i % 20 == 0:
                plotter.add_point_labels([pos], [f"{i+1}"], point_size=4, font_size=6)
    
    def _apply_rotations(self, mesh, rotations: List[float]):
        """Aplica rotacions a una malla"""
        rx, ry, rz = rotations
        
        if rx != 0:
            mesh = mesh.rotate_x(rx, inplace=False)
        if ry != 0:
            mesh = mesh.rotate_y(ry, inplace=False)
        if rz != 0:
            mesh = mesh.rotate_z(rz, inplace=False)
        
        return mesh
    
    def _trimesh_to_pyvista(self, tmesh):
        """Converteix trimesh a PyVista"""
        import pyvista as pv
        faces_pv = np.column_stack(([3] * len(tmesh.faces), tmesh.faces)).flatten()
        return pv.PolyData(tmesh.vertices, faces_pv)
    
    def _render_3d_scene_advanced(self, mesh, positions: List, rotations: List, 
                                 box_dims: Dict, show_wireframe: bool, show_labels: bool,
                                 show_axes: bool, show_grid: bool, show_edges: bool,
                                 color_scheme: str, background_color: str, 
                                 window_size: tuple) -> bool:
        """Renderitza l'escena 3D amb opcions avançades"""
        try:
            import pyvista as pv
            
            num_pieces = len(positions)
            print(f"🎮 Renderitzant {num_pieces} peces amb opcions avançades...")
            
            # Crear visualitzador amb mida personalitzada
            plotter = pv.Plotter(window_size=window_size)
            plotter.set_background(background_color)
            
            # Afegir eixos si cal
            if show_axes:
                plotter.add_axes()
            
            # Afegir reixa si cal
            if show_grid:
                plotter.show_grid()
            
            # Mostrar contenidor si cal
            if box_dims and show_wireframe:
                box = pv.Box(bounds=[0, box_dims['length'], 0, box_dims['width'], 0, box_dims['height']])
                plotter.add_mesh(box, style='wireframe', color='black', line_width=3, opacity=0.8)
            
            # Convertir mesh a PyVista
            base_mesh_pv = self._trimesh_to_pyvista(mesh)
            
            # Renderitzar peces segons l'esquema de colors
            if color_scheme == 'solid':
                self._render_solid_colors(plotter, base_mesh_pv, positions, rotations, show_labels, show_edges)
            elif color_scheme == 'gradient':
                self._render_gradient_colors_advanced(plotter, base_mesh_pv, positions, rotations, show_labels, show_edges)
            elif color_scheme == 'density':
                self._render_density_colors(plotter, base_mesh_pv, positions, rotations, show_labels, show_edges)
            else:
                # Default: solid colors
                self._render_solid_colors(plotter, base_mesh_pv, positions, rotations, show_labels, show_edges)
            
            # Configurar vista
            plotter.camera_position = 'iso'
            
            # Informació de l'escena
            info_text = f"Peces: {num_pieces} | Colors: {color_scheme} | Fons: {background_color}"
            plotter.add_text(info_text, position='upper_edge', font_size=10, color='black')
            
            # Mostrar
            plotter.show(interactive=True, auto_close=False)
            
            return True
            
        except ImportError:
            messagebox.showerror("Error", "PyVista no està instal·lat.\nInstal·la'l amb: pip install pyvista")
            return False
        except Exception as e:
            messagebox.showerror("Error", f"Error en la visualització 3D:\n{e}")
            return False
    
    def _render_solid_colors(self, plotter, base_mesh_pv, positions: List, 
                           rotations: List, show_labels: bool, show_edges: bool):
        """Renderitza amb colors sòlids (com pestanyes 1 i 2)"""
        for i, (pos, rot) in enumerate(zip(positions, rotations)):
            piece_mesh = base_mesh_pv.copy()
            
            # Aplicar rotacions
            piece_mesh = self._apply_rotations(piece_mesh, rot)
            
            # Aplicar translació
            piece_mesh = piece_mesh.translate(pos, inplace=False)
            
            # Color únic sòlid
            color_index = i % len(COLOR_PALETTE)
            color = COLOR_PALETTE[color_index]
            
            # Afegir malla amb colors sòlids
            plotter.add_mesh(piece_mesh, color=color, opacity=1.0, show_edges=show_edges)
            
            # Etiquetes cada 5 peces per no saturar
            if show_labels and i % 5 == 0:
                plotter.add_point_labels([pos], [f"P{i+1}"], point_size=6, font_size=8)
    
    def _render_gradient_colors_advanced(self, plotter, base_mesh_pv, positions: List,
                                       rotations: List, show_labels: bool, show_edges: bool):
        """Renderitza amb gradient de colors basat en altura"""
        # Calcular rang d'altures
        z_positions = [pos[2] for pos in positions]
        z_min, z_max = min(z_positions), max(z_positions)
        z_range = z_max - z_min if z_max > z_min else 1
        
        for i, (pos, rot) in enumerate(zip(positions, rotations)):
            piece_mesh = base_mesh_pv.copy()
            
            # Aplicar rotacions
            piece_mesh = self._apply_rotations(piece_mesh, rot)
            
            # Aplicar translació
            piece_mesh = piece_mesh.translate(pos, inplace=False)
            
            # Color basat en altura (gradient vertical)
            height_ratio = (pos[2] - z_min) / z_range
            # De blau (baix) a vermell (alt)
            color = [height_ratio, 0.2, 1.0 - height_ratio]
            
            # Afegir malla
            plotter.add_mesh(piece_mesh, color=color, opacity=1.0, show_edges=show_edges)
            
            # Etiquetes cada 10 peces
            if show_labels and i % 10 == 0:
                plotter.add_point_labels([pos], [f"H{pos[2]:.1f}"], point_size=6, font_size=8)
    
    def _render_density_colors(self, plotter, base_mesh_pv, positions: List,
                             rotations: List, show_labels: bool, show_edges: bool):
        """Renderitza amb colors basats en densitat de peces"""
        # Calcular densitat per regions
        density_colors = self._calculate_density_colors(positions)
        
        for i, (pos, rot) in enumerate(zip(positions, rotations)):
            piece_mesh = base_mesh_pv.copy()
            
            # Aplicar rotacions
            piece_mesh = self._apply_rotations(piece_mesh, rot)
            
            # Aplicar translació
            piece_mesh = piece_mesh.translate(pos, inplace=False)
            
            # Color basat en densitat
            color = density_colors[i]
            
            # Afegir malla
            plotter.add_mesh(piece_mesh, color=color, opacity=1.0, show_edges=show_edges)
            
            # Etiquetes cada 8 peces
            if show_labels and i % 8 == 0:
                plotter.add_point_labels([pos], [f"D{i+1}"], point_size=6, font_size=8)
    
    def _calculate_density_colors(self, positions: List) -> List:
        """Calcula colors basats en densitat de peces properes"""
        colors = []
        
        for i, pos in enumerate(positions):
            # Comptar peces properes (en un radi de 50 unitats)
            nearby_count = 0
            for j, other_pos in enumerate(positions):
                if i != j:
                    distance = np.linalg.norm(np.array(pos) - np.array(other_pos))
                    if distance < 50:
                        nearby_count += 1
            
            # Color segons densitat: verd (baixa) a vermell (alta)
            max_density = 10  # Assumir màxim 10 peces properes
            density_ratio = min(nearby_count / max_density, 1.0)
            color = [density_ratio, 1.0 - density_ratio, 0.2]
            colors.append(color)
        
        return colors
    
    def _handle_auto_exports(self, results: Dict, mesh, auto_stl: bool, 
                           auto_json: bool, auto_csv: bool):
        """Gestiona les exportacions automàtiques"""
        try:
            from ..core.export import ResultsExporter
            
            exporter = ResultsExporter()
            formats = []
            
            if auto_stl:
                formats.append('stl')
            if auto_json:
                formats.append('json')
            if auto_csv:
                formats.append('csv')
            
            if formats:
                print(f"📤 Exportant automàticament: {', '.join(formats)}")
                exporter.export_multiple_formats(results, mesh, formats)
                
        except Exception as e:
            print(f"⚠️ Error en exportació automàtica: {e}")

    def _add_scene_info(self, plotter, num_pieces: int, use_gradient: bool):
        """Afegeix informació a l'escena"""
        plotter.add_text(f"PackAssist - {num_pieces} peces visualitzades",
                        position='upper_edge', font_size=14, color='black')
        
        if num_pieces <= 50 and not use_gradient:
            legend_text = "Llegenda:\n• Colors únics per peça\n• Etiquetes cada 5 peces"
        else:
            legend_text = "Llegenda:\n• Gradient per altura\n• Blau=baix, Vermell=alt\n• Etiquetes cada 20 peces"
        
        plotter.add_text(legend_text, position='lower_right', font_size=9, color='darkgreen')
    
    def _auto_screenshot(self, plotter):
        """Captura automàtica de pantalla"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"packassist_3d_{timestamp}.png"
        
        try:
            plotter.screenshot(filename, transparent_background=False)
            print(f"📸 Captura guardada: {filename}")
        except Exception as e:
            print(f"Error capturant pantalla: {e}")
