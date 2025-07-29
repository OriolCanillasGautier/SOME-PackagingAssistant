"""
Visualitzador 3D natiu integrat per PackAssist
Finestra Tkinter amb matplotlib que combina la potència visual web amb la integració nativa
"""
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
import math


class NativePackingVisualizer:
    def __init__(self, optimization_result):
        """
        Inicialitza el visualitzador natiu amb els resultats de l'optimització
        
        Args:
            optimization_result: Diccionari amb els resultats de optimize_packing()
        """
        self.result = optimization_result
        self.window = None
        self.canvas = None
        self.toolbar = None
        
    def show_window(self):
        """Mostra la finestra de visualització nativa"""
        if not self.result or not self.result.get('bins'):
            messagebox.showerror("Error", "No hi ha dades vàlides per visualitzar")
            return
            
        # Crear finestra principal
        self.window = tk.Toplevel()
        self.window.title("🎯 PackAssist 3D - Visualització Interactiva")
        self.window.geometry("1200x800")
        self.window.minsize(800, 600)
        
        # Configurar estil modern
        self._setup_window_style()
        
        # Crear layout principal
        self._create_layout()
        
        # Generar visualització 3D
        self._create_3d_visualization()
        
        # Fer la finestra modal i centrada
        self.window.transient()
        self.window.grab_set()
        self._center_window()
        
    def _setup_window_style(self):
        """Configura l'estil modern de la finestra"""
        self.window.configure(bg="#f0f0f0")
        style = ttk.Style()
        style.configure('Modern.TFrame', background='#f0f0f0')
        style.configure('Header.TLabel', font=('Arial', 12, 'bold'), background='#f0f0f0')
        style.configure('Info.TLabel', font=('Arial', 10), background='#f0f0f0')
        
    def _create_layout(self):
        """Crea el layout principal de la finestra"""
        # Frame principal
        main_frame = ttk.Frame(self.window, style='Modern.TFrame', padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header amb informació
        self._create_header(main_frame)
        
        # Frame per la visualització 3D
        viz_frame = ttk.Frame(main_frame, style='Modern.TFrame')
        viz_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Frame per la canvas matplotlib
        self.canvas_frame = ttk.Frame(viz_frame, style='Modern.TFrame')
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Frame per botons
        button_frame = ttk.Frame(main_frame, style='Modern.TFrame')
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="🔄 Actualitzar Vista", 
                  command=self._refresh_view).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="💾 Exportar Imatge", 
                  command=self._export_image).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="❌ Tancar", 
                  command=self.window.destroy).pack(side=tk.RIGHT)
                  
    def _create_header(self, parent):
        """Crea el header amb informació de l'optimització"""
        header_frame = ttk.Frame(parent, style='Modern.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Títol principal
        title_label = ttk.Label(header_frame, text="📦 Visualització 3D - Empaquetament Optimitzat", 
                               style='Header.TLabel')
        title_label.pack(anchor=tk.W)
        
        # Informació estadística
        info_frame = ttk.Frame(header_frame, style='Modern.TFrame')
        info_frame.pack(fill=tk.X, pady=(5, 0))
        
        # Estadístiques principals
        max_objects = self.result.get('max_objects', 0)
        efficiency = self.result.get('efficiency', 0)
        used_volume = self.result.get('used_volume', 0)
        box_volume = self.result.get('box_volume', 0)
        
        stats_text = f"📊 Objectes empaquetats: {max_objects} | 📈 Eficiència: {efficiency:.1f}% | 📐 Volum utilitzat: {used_volume:,.0f} mm³ / {box_volume:,.0f} mm³"
        
        stats_label = ttk.Label(info_frame, text=stats_text, style='Info.TLabel')
        stats_label.pack(anchor=tk.W)
        
        # Informació d'optimització si està disponible
        if self.result.get('bins') and len(self.result['bins']) > 0:
            bin_info = self.result['bins'][0]
            if bin_info.get('bin', {}).get('optimization_info'):
                opt_info = bin_info['bin']['optimization_info']
                strategy = opt_info.get('strategy_used', 'Unknown')
                attempts = opt_info.get('attempts_tested', 'Unknown')
                
                opt_text = f"🔧 Estratègia: {strategy} | 🔄 Intents testejats: {attempts}"
                opt_label = ttk.Label(info_frame, text=opt_text, style='Info.TLabel')
                opt_label.pack(anchor=tk.W, pady=(2, 0))
        
    def _create_3d_visualization(self):
        """Crea la visualització 3D amb matplotlib"""
        try:
            # Crear figura matplotlib
            fig = Figure(figsize=(12, 9), dpi=100, facecolor='white')
            ax = fig.add_subplot(111, projection='3d')
            
            # Configurar fons i estil
            ax.xaxis.pane.fill = False
            ax.yaxis.pane.fill = False
            ax.zaxis.pane.fill = False
            ax.xaxis.pane.set_edgecolor('gray')
            ax.yaxis.pane.set_edgecolor('gray')
            ax.zaxis.pane.set_edgecolor('gray')
            ax.xaxis.pane.set_alpha(0.1)
            ax.yaxis.pane.set_alpha(0.1)
            ax.zaxis.pane.set_alpha(0.1)
            
            # Obtenir dades
            bin_info = self.result['bins'][0]
            bin_data = bin_info['bin']
            items = bin_info['items']
            
            # Dimensions del contenidor
            container_dims = bin_data['dimensions']
            container_length, container_width, container_height = container_dims
            
            # Dibuixar contenidor (wireframe modern)
            self._draw_modern_container(ax, container_length, container_width, container_height)
            
            # Dibuixar objectes empaquetats
            self._draw_packed_objects(ax, items)
            
            # Configurar eixos i etiquetes
            ax.set_xlabel('Longitud (mm)', fontsize=10, fontweight='bold')
            ax.set_ylabel('Amplada (mm)', fontsize=10, fontweight='bold')
            ax.set_zlabel('Altura (mm)', fontsize=10, fontweight='bold')
            
            # Títol de la visualització
            max_objects = len(items)
            efficiency = self.result.get('efficiency', 0)
            ax.set_title(f'Empaquetament 3D: {max_objects} objectes (Eficiència: {efficiency:.1f}%)', 
                        fontsize=12, fontweight='bold', pad=20)
            
            # Fer els eixos proporcionals
            self._set_axes_equal_3d(ax)
            
            # Configurar vista inicial
            ax.view_init(elev=20, azim=45)
            
            # Crear canvas i toolbar
            self.canvas = FigureCanvasTkAgg(fig, self.canvas_frame)
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Toolbar de navegació
            self.toolbar = NavigationToolbar2Tk(self.canvas, self.canvas_frame)
            self.toolbar.update()
            
            # Configurar el toolbar amb estil modern
            self.toolbar.config(bg='#f0f0f0')
            
        except Exception as e:
            messagebox.showerror("Error", f"Error creant visualització 3D: {e}")
            
    def _draw_modern_container(self, ax, length, width, height):
        """Dibuixa un contenidor modern amb wireframe elegante"""
        # Vèrtexs del contenidor
        vertices = np.array([
            [0, 0, 0], [length, 0, 0], [length, width, 0], [0, width, 0],  # base inferior
            [0, 0, height], [length, 0, height], [length, width, height], [0, width, height]  # base superior
        ])
        
        # Arestes del contenidor
        edges = [
            [0, 1], [1, 2], [2, 3], [3, 0],  # base inferior
            [4, 5], [5, 6], [6, 7], [7, 4],  # base superior
            [0, 4], [1, 5], [2, 6], [3, 7]   # arestes verticals
        ]
        
        # Dibuixar arestes amb estil modern
        for edge in edges:
            points = vertices[edge]
            ax.plot3D(points[:, 0], points[:, 1], points[:, 2], 
                     color='#2c3e50', linewidth=2.5, alpha=0.8)
        
        # Afegir corners destacats
        for vertex in vertices:
            ax.scatter(vertex[0], vertex[1], vertex[2], 
                      color='#e74c3c', s=30, alpha=0.8)
                      
    def _draw_packed_objects(self, ax, items):
        """Dibuixa els objectes empaquetats amb colors moderns i suport per geometria complexa"""
        # Paleta de colors moderna
        modern_colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
            '#A8E6CF', '#FFD93D', '#6BCF7F', '#4D96FF', '#FF9FF3',
            '#F368E0', '#FF8E53', '#54A0FF', '#5F27CD', '#00D2D3',
            '#FF3838', '#2ED573', '#FFA502', '#3742FA', '#FF6348',
            '#7BED9F', '#70A1FF', '#5352ED', '#FF4757', '#2F3542',
            '#57606F', '#FFC048', '#FF5722', '#8E44AD', '#E91E63'
        ]
        
        for index, item in enumerate(items):
            # Obtenir posició i dimensions
            position = item['position']
            dimensions = item['dimensions']
            
            x, y, z = [float(p) for p in position]
            w, h, d = [float(dim) for dim in dimensions]
            
            # Color modern per l'objecte
            color = modern_colors[index % len(modern_colors)]
            
            # Comprovar si l'objecte té geometria complexa
            has_complex_geometry = (hasattr(item, 'real_geometry') or 
                                  (hasattr(item, 'shape_type') and 
                                   'complex' in str(item.get('shape_type', ''))))
            
            if has_complex_geometry:
                print(f"🎨 Dibuixant objecte complex {index+1}")
                self._draw_complex_geometry_object(ax, (x, y, z), (w, h, d), color, index, item)
            else:
                # Dibuixar objecte 3D amb estil modern tradicional
                self._draw_modern_3d_box(ax, (x, y, z), (w, h, d), color, index)
            
    def _draw_modern_3d_box(self, ax, position, dimensions, color, index):
        """Dibuixa una caixa 3D amb estil modern"""
        x, y, z = position
        w, h, d = dimensions
        
        # Vèrtexs de la caixa
        vertices = np.array([
            [x, y, z], [x+w, y, z], [x+w, y+h, z], [x, y+h, z],         # base inferior
            [x, y, z+d], [x+w, y, z+d], [x+w, y+h, z+d], [x, y+h, z+d] # base superior
        ])
        
        # Cares de la caixa
        faces = [
            [vertices[0], vertices[1], vertices[2], vertices[3]],  # base inferior
            [vertices[4], vertices[5], vertices[6], vertices[7]],  # base superior
            [vertices[0], vertices[1], vertices[5], vertices[4]],  # cara frontal
            [vertices[2], vertices[3], vertices[7], vertices[6]],  # cara posterior
            [vertices[1], vertices[2], vertices[6], vertices[5]],  # cara dreta
            [vertices[4], vertices[7], vertices[3], vertices[0]]   # cara esquerra
        ]
        
        # Dibuixar cares amb transparència
        for face in faces:
            poly = Poly3DCollection([face], alpha=0.7, facecolor=color, 
                                  edgecolor='white', linewidth=1.5)
            ax.add_collection3d(poly)
        
        # Afegir número de l'objecte al centre
        center_x, center_y, center_z = x + w/2, y + h/2, z + d/2
        ax.text(center_x, center_y, center_z, str(index + 1), 
               fontsize=8, ha='center', va='center', weight='bold', color='white')
    
    def _draw_complex_geometry_object(self, ax, position, dimensions, color, index, item_data):
        """Dibuixa un objecte amb geometria complexa real"""
        try:
            x, y, z = position
            w, h, d = dimensions
            
            # Detectar si tenim geometria avançada
            has_advanced_geometry = item_data.get('advanced_geometry', False)
            geometry_obj = item_data.get('geometry_object')
            
            if has_advanced_geometry and geometry_obj:
                print(f"🎯 Dibuixant geometria complexa amb {item_data.get('total_faces', 0)} cares")
                
                # Intentar dibuixar geometria complexa real
                try:
                    if hasattr(geometry_obj, 'faces') and len(geometry_obj.faces) > 0:
                        # Seleccionar només un subconjunt de cares per rendiment
                        max_faces_to_draw = min(50, len(geometry_obj.faces))
                        selected_faces = geometry_obj.faces[:max_faces_to_draw]
                        
                        for face in selected_faces:
                            if hasattr(face, 'vertices') and len(face.vertices) >= 3:
                                # Escalar vèrtexs dins del bounding box
                                scaled_vertices = []
                                for vertex in face.vertices:
                                    scaled_v = (
                                        x + vertex[0] * w / 100,  # Assumir escala normalitzada
                                        y + vertex[1] * h / 100,
                                        z + vertex[2] * d / 100
                                    )
                                    scaled_vertices.append(scaled_v)
                                
                                # Crear polígon 3D
                                poly = Poly3DCollection([scaled_vertices], 
                                                      alpha=0.6, 
                                                      facecolor=color,
                                                      edgecolor='black', 
                                                      linewidth=0.5)
                                ax.add_collection3d(poly)
                        
                        print(f"✅ Dibuixades {max_faces_to_draw} de {len(geometry_obj.faces)} cares")
                        return  # Geometria complexa dibuixada amb èxit
                    
                except Exception as e:
                    print(f"⚠️  Error renderitzant geometria complexa: {e}")
                
                # Fallback: forma aproximada basada en complexitat
                complexity = item_data.get('complexity_score', 1.0)
                if complexity > 10:
                    self._draw_high_complexity_shape(ax, position, dimensions, color, complexity)
                    return
            
            # Fallback: dibuixar com a forma aproximada basada en el tipus
            shape_type = str(item_data.get('shape_type', 'rectangular'))
            
            if 'complex' in shape_type:
                # Dibuixar com un polígon aproximat
                faces_count = item_data.get('faces_count', 8)
                self._draw_complex_approximated_shape(ax, position, dimensions, color, faces_count)
            else:
                # Dibuixar com a caixa tradicional
                self._draw_modern_3d_box(ax, position, dimensions, color, index)
                
        except Exception as e:
            print(f"⚠️  Error dibuixant geometria complexa: {e}")
            # Fallback a caixa simple
            self._draw_modern_3d_box(ax, position, dimensions, color, index)
    
    def _draw_high_complexity_shape(self, ax, position, dimensions, color, complexity):
        """Dibuixa una forma que indica alta complexitat visual"""
        x, y, z = position
        w, h, d = dimensions
        
        # Crear una forma facetada que suggereix complexitat
        num_facets = min(int(complexity / 2), 12)  # Màxim 12 facetes
        
        # Base octogonal o similar
        angles = np.linspace(0, 2*np.pi, num_facets, endpoint=False)
        radius_x, radius_y = w/3, h/3
        center_x, center_y = x + w/2, y + h/2
        
        # Crear vèrtexs de la base
        base_vertices = []
        for angle in angles:
            vx = center_x + radius_x * np.cos(angle)
            vy = center_y + radius_y * np.sin(angle)
            base_vertices.append([vx, vy, z])
        
        # Crear vèrtexs del sostre
        top_vertices = []
        for angle in angles:
            vx = center_x + radius_x * 0.8 * np.cos(angle)  # Lleugerament més petit
            vy = center_y + radius_y * 0.8 * np.sin(angle)
            top_vertices.append([vx, vy, z + d])
        
        # Dibuixar cares laterals
        for i in range(num_facets):
            next_i = (i + 1) % num_facets
            face_vertices = [
                base_vertices[i],
                base_vertices[next_i],
                top_vertices[next_i],
                top_vertices[i]
            ]
            
            poly = Poly3DCollection([face_vertices], 
                                  alpha=0.7, 
                                  facecolor=color,
                                  edgecolor='darkred', 
                                  linewidth=1)
            ax.add_collection3d(poly)
        
        # Dibuixar base i sostre
        base_poly = Poly3DCollection([base_vertices], alpha=0.8, facecolor=color, edgecolor='darkred')
        top_poly = Poly3DCollection([top_vertices], alpha=0.8, facecolor=color, edgecolor='darkred')
        ax.add_collection3d(base_poly)
        ax.add_collection3d(top_poly)
    
    def _draw_complex_approximated_shape(self, ax, position, dimensions, color, faces_count):
        """Dibuixa una forma poligonal aproximada basada en el nombre de cares"""
        x, y, z = position
        w, h, d = dimensions
        
        # Crear un polígon regular en la base
        angles = np.linspace(0, 2*np.pi, faces_count, endpoint=False)
        radius_x, radius_y = w/2, h/2
        center_x, center_y = x + w/2, y + h/2
        
        # Vèrtexs de la base
        base_vertices = []
        top_vertices = []
        
        for angle in angles:
            base_x = center_x + radius_x * np.cos(angle)
            base_y = center_y + radius_y * np.sin(angle)
            base_vertices.append([base_x, base_y, z])
            top_vertices.append([base_x, base_y, z + d])
        
        # Dibuixar base i top
        base_poly = Poly3DCollection([base_vertices], alpha=0.7, facecolor=color, edgecolor='white')
        top_poly = Poly3DCollection([top_vertices], alpha=0.7, facecolor=color, edgecolor='white')
        ax.add_collection3d(base_poly)
        ax.add_collection3d(top_poly)
        
        # Dibuixar cares laterals
        for i in range(len(base_vertices)):
            next_i = (i + 1) % len(base_vertices)
            side_face = [
                base_vertices[i],
                base_vertices[next_i],
                top_vertices[next_i],
                top_vertices[i]
            ]
            side_poly = Poly3DCollection([side_face], alpha=0.7, facecolor=color, edgecolor='white')
            ax.add_collection3d(side_poly)
    
    def _set_axes_equal_3d(self, ax):
        """Fa que els eixos 3D tinguin la mateixa escala"""
        limits = [ax.get_xlim3d(), ax.get_ylim3d(), ax.get_zlim3d()]
        ranges = [abs(lim[1] - lim[0]) for lim in limits]
        middles = [sum(lim) / 2 for lim in limits]
        
        plot_radius = max(ranges) * 0.5
        
        ax.set_xlim3d([middles[0] - plot_radius, middles[0] + plot_radius])
        ax.set_ylim3d([middles[1] - plot_radius, middles[1] + plot_radius])
        ax.set_zlim3d([middles[2] - plot_radius, middles[2] + plot_radius])
        
    def _center_window(self):
        """Centra la finestra a la pantalla"""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        pos_x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        pos_y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{pos_x}+{pos_y}')
        
    def _refresh_view(self):
        """Actualitza la vista 3D"""
        if self.canvas:
            # Regenerar la visualització
            for widget in self.canvas_frame.winfo_children():
                widget.destroy()
            self._create_3d_visualization()
            
    def _export_image(self):
        """Exporta la visualització com a imatge"""
        if self.canvas:
            try:
                from tkinter import filedialog
                filename = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    filetypes=[("PNG files", "*.png"), ("PDF files", "*.pdf"), ("SVG files", "*.svg")],
                    title="Exportar visualització"
                )
                if filename:
                    self.canvas.figure.savefig(filename, dpi=300, bbox_inches='tight')
                    messagebox.showinfo("Èxit", f"Visualització exportada com: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Error exportant imatge: {e}")


def show_native_packing_visualization(optimization_result):
    """
    Funció principal per mostrar la visualització nativa integrada
    
    Args:
        optimization_result: Resultat de optimize_packing()
    """
    try:
        visualizer = NativePackingVisualizer(optimization_result)
        visualizer.show_window()
        return visualizer
    except Exception as e:
        messagebox.showerror("Error", f"Error mostrant visualització: {e}")
        return None
