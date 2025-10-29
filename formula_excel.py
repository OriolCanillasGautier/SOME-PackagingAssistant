import gradio as gr
import numpy as np
import pandas as pd
from typing import Tuple, Optional, List
from decimal import Decimal, ROUND_HALF_UP
import math
import tempfile
import os
import threading
import sys
import json
import subprocess
 
# Visualització 3D (Plotly) - opcional (ja no s'utilitza a la UI, però el deixem per fallback si cal)
PLOTLY_SUPPORT = False
try:
    import plotly.graph_objects as go
    PLOTLY_SUPPORT = True
except Exception:
    PLOTLY_SUPPORT = False

# Constants per defecte
# Per defecte, mode exacte (sense marge de seguretat)
DEFAULT_SAFETY_FACTOR = 1.0

# Verificar si trimesh està disponible per processar STL
STL_SUPPORT = False
try:
    import trimesh
    # Test bàsic per verificar que funciona
    test_mesh = trimesh.creation.box()
    _ = test_mesh.bounds
    STL_SUPPORT = True
except ImportError:
    STL_SUPPORT = False
    print("ℹ️ Trimesh no està instal·lat. Per suport STL: pip install trimesh[easy]")
except Exception:
    STL_SUPPORT = False
    print("⚠️ Trimesh instal·lat però amb problemes. Funcionalitat STL desactivada.")

# PyVista per a vistes "exactes" tipus Visualizer3D (imatges estàtiques)
PYVISTA_SUPPORT = False
try:
    import pyvista as pv
    PYVISTA_SUPPORT = True
except Exception:
    PYVISTA_SUPPORT = False

# --- Geometria i transformacions auxiliars (trimesh) -----------------------------------------
import numpy as _np
def _load_trimesh(path: str):
    if not STL_SUPPORT:
        return None
    try:
        m = trimesh.load(path, force='mesh')
        if m is None or not hasattr(m, 'vertices'):
            return None
        if hasattr(m, 'is_empty') and m.is_empty:
            return None
        return m
    except Exception:
        return None

def _canonicalize_to_obb(mesh) -> Tuple[_np.ndarray, _np.ndarray, Tuple[float, float, float]]:
    """Retorna (V, F, extents) on la malla està alineada als eixos segons l'OBB i min→(0,0,0)."""
    # Copiar
    m = mesh.copy()
    # Oriented bounding box
    obb = m.bounding_box_oriented
    T = obb.primitive.transform  # 4x4, obb-local -> world
    # Portar la malla a coordenades OBB locals (alineat amb eixos)
    m.apply_transform(_np.linalg.inv(T))
    # Traslladar perquè min estigui a 0,0,0 i base sobre Z=0
    mins = m.bounds[0]
    m.apply_translation(-mins)
    extents = tuple(float(e) for e in obb.primitive.extents)
    return _np.asarray(m.vertices), _np.asarray(m.faces), extents

def _perm_matrix(ix: int, iy: int, iz: int) -> _np.ndarray:
    """Matriu 3x3 que permuta els eixos segons (ix,iy,iz)."""
    M = _np.zeros((3,3))
    M[0, ix] = 1.0
    M[1, iy] = 1.0
    M[2, iz] = 1.0
    return M

def _apply_permutation(V: _np.ndarray, perm: Tuple[int,int,int]) -> _np.ndarray:
    M = _perm_matrix(*perm)
    V2 = (M @ V.T).T
    # Després de permutar, desplaçar min→0 de nou
    mins = V2.min(axis=0)
    return V2 - mins

def _guess_perm_for_dims(source_extents: Tuple[float,float,float], target_dims: Tuple[float,float,float]) -> Tuple[int,int,int]:
    """Troba la permutació d'índexs de source_extents que més s'assembla a target_dims."""
    from itertools import permutations
    s = _np.array(source_extents)
    t = _np.array(target_dims)
    best = (0,1,2)
    best_err = 1e18
    for perm in permutations([0,1,2]):
        cand = s[list(perm)]
        err = float(_np.sum((_np.array(cand) - t)**2))
        if err < best_err:
            best_err = err
            best = perm
    return best


def extreure_dimensions_stl(file_path: str) -> Tuple[float, float, float]:
    """
    Extreu les dimensions d'un fitxer STL.
    Retorna (llargada, amplada, alçada) en mm.
    """
    if not STL_SUPPORT:
        raise ValueError("Trimesh no està disponible")
    
    try:
        # Carregar el mesh
        mesh = trimesh.load(file_path)
        
        if mesh is None or not hasattr(mesh, 'bounds'):
            raise ValueError("El fitxer STL no s'ha pogut carregar")
        
        if hasattr(mesh, 'is_empty') and mesh.is_empty:
            raise ValueError("El fitxer STL està buit")
            
        # Obtenir dimensions del bounding box
        bounds = mesh.bounds
        if bounds is None or len(bounds) != 2 or len(bounds[0]) != 3:
            raise ValueError("No s'han pogut calcular les dimensions")
            
        dimensions = bounds[1] - bounds[0]  # max - min per cada eix
        
        if any(dim <= 0 for dim in dimensions):
            raise ValueError("Les dimensions calculades no són vàlides")
        
        # Retornar dimensions (assumint que estan en mm)
        return float(dimensions[0]), float(dimensions[1]), float(dimensions[2])
    
    except Exception as e:
        raise ValueError(f"Error processant STL: {str(e)}")


def processar_stl_upload(stl_file):
    """Processa un fitxer STL pujat i retorna les dimensions en mm."""
    if stl_file is None or not STL_SUPPORT:
        return None, None, None, "No s'ha pujat cap fitxer STL o trimesh no està disponible"
    
    try:
        # Extreure dimensions del STL
        stl_l, stl_w, stl_h = extreure_dimensions_stl(stl_file.name)
        
        # Convertir de mm a mm (ja estan en mm, però assegurem precisió)
        return (
            round(stl_l, 2),
            round(stl_w, 2), 
            round(stl_h, 2),
            f"✅ Dimensions extretes: {stl_l:.2f}×{stl_w:.2f}×{stl_h:.2f} mm"
        )
    except Exception as e:
        return None, None, None, f"❌ Error: {str(e)}"

def calcular_empaquetatge_precis(
    obj_l: float, obj_w: float, obj_h: float, obj_weight: float,
    box_l: float, box_w: float, box_h: float, max_weight: float,
    allow_rotation: bool = True, safety_factor: float = DEFAULT_SAFETY_FACTOR
) -> Tuple[str, dict]:
    """
    Calcula amb alta precisió quantes unitats caben en una caixa.
    Retorna el resultat formatejat i un diccionari amb les dades.
    """
    
    # Validacions bàsiques
    if any(v <= 0 for v in [obj_l, obj_w, obj_h, obj_weight, box_l, box_w, box_h, max_weight]):
        return "❌ Tots els valors han de ser majors que 0.", {}
    
    if obj_weight > max_weight:
        return "❌ El pes d'una sola unitat supera la capacitat màxima de la caixa.", {}
    
    # Usar Decimal per màxima precisió
    obj_dims = [Decimal(str(obj_l)), Decimal(str(obj_w)), Decimal(str(obj_h))]
    box_dims = [Decimal(str(box_l)), Decimal(str(box_w)), Decimal(str(box_h))]
    obj_weight_d = Decimal(str(obj_weight))
    max_weight_d = Decimal(str(max_weight))
    
    # Generar totes les orientacions possibles si està permès
    if allow_rotation:
        orientations = [
            (obj_dims[0], obj_dims[1], obj_dims[2]),  # Original
            (obj_dims[0], obj_dims[2], obj_dims[1]),  # Rotar Y
            (obj_dims[1], obj_dims[0], obj_dims[2]),  # Rotar Z
            (obj_dims[1], obj_dims[2], obj_dims[0]),  # Rotar XY
            (obj_dims[2], obj_dims[0], obj_dims[1]),  # Rotar XZ
            (obj_dims[2], obj_dims[1], obj_dims[0]),  # Rotar YZ
        ]
        orientation_names = [
            "Original (L×W×H)",
            "Rotació Y (L×H×W)", 
            "Rotació Z (W×L×H)",
            "Rotació XY (W×H×L)",
            "Rotació XZ (H×L×W)",
            "Rotació YZ (H×W×L)"
        ]
    else:
        orientations = [(obj_dims[0], obj_dims[1], obj_dims[2])]
        orientation_names = ["Original (L×W×H)"]
    
    best_fit = 0
    best_config = None
    all_orientations = []
    
    for i, (ol, ow, oh) in enumerate(orientations):
        # Calcular quantes unitats caben per cada dimensió
        fit_l = int(box_dims[0] // ol) if ol <= box_dims[0] else 0
        fit_w = int(box_dims[1] // ow) if ow <= box_dims[1] else 0  
        fit_h = int(box_dims[2] // oh) if oh <= box_dims[2] else 0
        
        total_units = fit_l * fit_w * fit_h
        total_weight = float(total_units * obj_weight_d)
        
        # Calcular eficiències
        vol_obj = float(ol * ow * oh)
        vol_box = float(box_dims[0] * box_dims[1] * box_dims[2])
        vol_efficiency = (total_units * vol_obj / vol_box * 100) if vol_box > 0 else 0
        weight_efficiency = (total_weight / float(max_weight_d) * 100) if max_weight_d > 0 else 0
        
        orientation_data = {
            "name": orientation_names[i],
            "dimensions": (float(ol), float(ow), float(oh)),
            "units": total_units,
            "distribution": f"{fit_l}×{fit_w}×{fit_h}",
            "weight": total_weight,
            "vol_efficiency": vol_efficiency,
            "weight_efficiency": weight_efficiency,
            "fits_weight": total_weight <= float(max_weight_d)
        }
        all_orientations.append(orientation_data)
        
        # Comprovar si aquesta orientació és millor
        if total_units > 0 and total_weight <= float(max_weight_d):
            if total_units > best_fit:
                best_fit = total_units
                best_config = orientation_data.copy()
        
        # Si supera el pes, calcular màxim per pes
        elif total_units > 0:
            max_by_weight = int(max_weight_d // obj_weight_d)
            if max_by_weight > best_fit:
                # Trobar distribució òptima per aquest nombre d'unitats
                best_dist = optimize_by_weight(fit_l, fit_w, fit_h, max_by_weight)
                if best_dist and best_dist[3] > best_fit:
                    best_fit = best_dist[3]
                    best_config = {
                        "name": f"{orientation_names[i]} (Limitat per pes)",
                        "dimensions": (float(ol), float(ow), float(oh)),
                        "units": best_dist[3],
                        "distribution": f"{best_dist[0]}×{best_dist[1]}×{best_dist[2]}",
                        "weight": float(best_dist[3] * obj_weight_d),
                        "vol_efficiency": (best_dist[3] * vol_obj / vol_box * 100),
                        "weight_efficiency": (float(best_dist[3] * obj_weight_d) / float(max_weight_d) * 100),
                        "fits_weight": True,
                        "limited_by": "weight"
                    }
    
    if best_fit == 0:
        debug = create_debug_info(all_orientations, float(max_weight_d), float(obj_weight_d))
        return f"❌ No cap cap unitat a la caixa.\n\n{debug}", {}
    
    # Aplicar factor de seguretat
    real_fit = max(1, int(Decimal(str(best_fit)) * Decimal(str(safety_factor))))
    
    # Generar resum
    summary = create_summary(best_fit, real_fit, best_config, safety_factor, all_orientations)
    
    return summary, {
        "theoretical_units": best_fit,
        "real_units": real_fit,
        "best_orientation": best_config,
        "all_orientations": all_orientations
    }


# --- Utilitats de visualització 3D -----------------------------------------------------------
def _make_cuboid_edges(x: float, y: float, z: float, dx: float, dy: float, dz: float):
    """Construeix les línies d'arestes d'un cuboide per a Plotly Scatter3d."""
    # 8 vèrtexs
    pts = np.array([
        [x,     y,     z    ],
        [x+dx,  y,     z    ],
        [x+dx,  y+dy,  z    ],
        [x,     y+dy,  z    ],
        [x,     y,     z+dz ],
        [x+dx,  y,     z+dz ],
        [x+dx,  y+dy,  z+dz ],
        [x,     y+dy,  z+dz ],
    ])
    # arestes (parelles d'índexs)
    edges = [
        (0,1),(1,2),(2,3),(3,0),  # base
        (4,5),(5,6),(6,7),(7,4),  # top
        (0,4),(1,5),(2,6),(3,7)   # verticals
    ]
    x_lines, y_lines, z_lines = [], [], []
    for a,b in edges:
        x_lines.extend([pts[a,0], pts[b,0], None])
        y_lines.extend([pts[a,1], pts[b,1], None])
        z_lines.extend([pts[a,2], pts[b,2], None])
    return x_lines, y_lines, z_lines


def _build_packing_plot(box_dims: Tuple[float, float, float],
                        piece_dims: Tuple[float, float, float],
                        distribution: Tuple[int, int, int],
                        limit_draw: int = 300,
                        stl_path: Optional[str] = None,
                        use_stl: bool = False,
                        stl_limit: int = 20) -> Optional["go.Figure"]:
    """Crea una figura Plotly amb la caixa i les peces empaquetades com cuboides.
    Si no hi ha suport Plotly, retorna None.
    """
    if not PLOTLY_SUPPORT:
        return None
    bl, bw, bh = box_dims
    pl, pw, ph = piece_dims
    nx, ny, nz = distribution
    total_units = nx * ny * nz

    fig = go.Figure()

    # Caixa (arestes)
    cx, cy, cz = _make_cuboid_edges(0, 0, 0, bl, bw, bh)
    fig.add_trace(go.Scatter3d(x=cx, y=cy, z=cz, mode="lines",
                               line=dict(color="black", width=4), name="Caixa"))

    # Peces: si es pot, usar STL fins a stl_limit, si no, arestes de cuboide
    drawn = 0
    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                if drawn >= limit_draw:
                    break
                x0, y0, z0 = ix * pl, iy * pw, iz * ph
                if use_stl and stl_path and drawn < stl_limit and STL_SUPPORT:
                    try:
                        tm = _load_trimesh(stl_path)
                        if tm is not None:
                            V, F, ext = _canonicalize_to_obb(tm)
                            perm = _guess_perm_for_dims(ext, piece_dims)
                            V = _apply_permutation(V, perm)
                            Vt = V + _np.array([x0, y0, z0])
                            i, j, k = F[:,0], F[:,1], F[:,2]
                            fig.add_trace(go.Mesh3d(x=Vt[:,0], y=Vt[:,1], z=Vt[:,2], i=i, j=j, k=k,
                                                    color="#3b82f6", opacity=0.8, name="Peça" if drawn==0 else None,
                                                    showlegend=(drawn==0)))
                        else:
                            raise ValueError("mesh load failed")
                    except Exception:
                        px, py, pz = _make_cuboid_edges(x0, y0, z0, pl, pw, ph)
                        fig.add_trace(go.Scatter3d(x=px, y=py, z=pz, mode="lines",
                                                   line=dict(color="#3b82f6", width=2),
                                                   name="Peça" if drawn == 0 else None,
                                                   showlegend=(drawn == 0)))
                else:
                    px, py, pz = _make_cuboid_edges(x0, y0, z0, pl, pw, ph)
                    fig.add_trace(go.Scatter3d(x=px, y=py, z=pz, mode="lines",
                                               line=dict(color="#3b82f6", width=2),
                                               name="Peça" if drawn == 0 else None,
                                               showlegend=(drawn == 0)))
                drawn += 1
            if drawn >= limit_draw:
                break
        if drawn >= limit_draw:
            break

    # Configurar eixos i càmera
    fig.update_layout(
        scene=dict(
            xaxis=dict(title="L", nticks=6, range=[0, bl], backgroundcolor="white"),
            yaxis=dict(title="W", nticks=6, range=[0, bw], backgroundcolor="white"),
            zaxis=dict(title="H", nticks=6, range=[0, bh], backgroundcolor="white"),
            aspectmode="data",
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        title=f"Vista 3D — {min(total_units, limit_draw)} de {total_units} peces visibles",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig


def _compute_plot_from_inputs(ol: float, ow: float, oh: float, ow_kg: float,
                              bl: float, bw: float, bh: float, max_kg: float, safety: float):
    """Antic helper de Plotly: es manté per compatibilitat, però no s'utilitza a la UI simplificada."""
    summary, _ = calcular_empaquetatge_precis(ol, ow, oh, ow_kg, bl, bw, bh, max_kg, True, safety)
    return summary, None


def _build_packing_views_pyvista(box_dims: Tuple[float, float, float],
                                 piece_dims: Tuple[float, float, float],
                                 distribution: Tuple[int, int, int],
                                 stl_path: Optional[str] = None,
                                 use_stl: bool = False,
                                 limit_draw: int = 400,
                                 background: str = "black") -> List[str]:
    """Crea 6–8 imatges (vistes) amb PyVista que imiten el Visualizer3D.
    Retorna llista de rutes de fitxer a imatges PNG temporals.
    """
    if not PYVISTA_SUPPORT:
        return []

    bl, bw, bh = box_dims
    pl, pw, ph = piece_dims
    nx, ny, nz = distribution

    # Preparar plotter i estil per paritat amb Visualizer3D (escriptori)
    plotter = pv.Plotter(off_screen=True, window_size=(1200, 900))
    plotter.set_background(background)
    try:
        plotter.enable_anti_aliasing()
    except Exception:
        pass

    # Caixa com a wireframe (verd intens, gruix 3)
    box = pv.Cube(center=(bl/2, bw/2, bh/2), x_length=bl, y_length=bw, z_length=bh)
    plotter.add_mesh(box, style='wireframe', color='#22c55e', line_width=3, name='box')

    # Carregar STL i alinear a OBB si s'ha de fer servir
    stl_mesh_pv = None
    obb_ext = None
    if use_stl and stl_path and os.path.exists(stl_path) and STL_SUPPORT:
        tm = _load_trimesh(stl_path)
        if tm is not None:
            try:
                V, F, ext = _canonicalize_to_obb(tm)
                # Ajustar a l'orientació Excel (piece_dims)
                perm = _guess_perm_for_dims(ext, piece_dims)
                V = _apply_permutation(V, perm)
                # Crear PolyData
                faces = _np.hstack([_np.full((F.shape[0],1), 3, dtype=_np.int64), F]).ravel()
                stl_mesh_pv = pv.PolyData(V, faces)
                obb_ext = (float(V[:,0].max()), float(V[:,1].max()), float(V[:,2].max()))
            except Exception:
                stl_mesh_pv = None
                obb_ext = None

    # Afegir peces
    drawn = 0
    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                if drawn >= limit_draw:
                    break
                x0, y0, z0 = ix * pl, iy * pw, iz * ph
                if use_stl and stl_mesh_pv is not None and (nx*ny*nz) <= 60:
                    part = stl_mesh_pv.copy(deep=True)
                    part.translate((x0, y0, z0), inplace=True)
                    plotter.add_mesh(part, color="#3b82f6", specular=0.2, smooth_shading=True, show_edges=True)
                else:
                    # Cuboide peça
                    cube = pv.Cube(center=(x0 + pl/2, y0 + pw/2, z0 + ph/2),
                                   x_length=pl, y_length=pw, z_length=ph)
                    plotter.add_mesh(cube, color="#3b82f6", opacity=0.95, show_edges=True)
                drawn += 1
            if drawn >= limit_draw:
                break
        if drawn >= limit_draw:
            break

    # Vistes
    center = (bl/2, bw/2, bh/2)
    # Presets de càmera ajustats per semblança amb 'iso', 'top', etc.
    iso_mult = 2.2
    side_mult = 3.0
    top_mult = 2.8
    views = [
        ("Iso", dict(position=(bl*iso_mult, bw*iso_mult, bh*iso_mult), focal_point=center, viewup=(0,0,1))),
        ("Top", dict(position=(center[0], center[1], bh*top_mult), focal_point=center, viewup=(0,1,0))),
        ("Front", dict(position=(center[0], bw*side_mult, center[2]), focal_point=center, viewup=(0,0,1))),
        ("Right", dict(position=(bl*side_mult, center[1], center[2]), focal_point=center, viewup=(0,0,1))),
        ("Back", dict(position=(center[0], -bw*side_mult, center[2]), focal_point=center, viewup=(0,0,1))),
        ("Left", dict(position=(-bl*side_mult, center[1], center[2]), focal_point=center, viewup=(0,0,1))),
        ("Bottom", dict(position=(center[0], center[1], -bh*top_mult), focal_point=center, viewup=(0,1,0))),
    ]

    out_files: List[str] = []
    for name, cam in views:
        try:
            plotter.camera_position = (cam['position'], cam['focal_point'], cam['viewup'])
            plotter.reset_camera()
            # Guardar imatge temporal
            fd, path = tempfile.mkstemp(prefix=f"view_{name}_", suffix=".png")
            os.close(fd)
            plotter.screenshot(path)
            out_files.append(path)
        except Exception:
            continue

    plotter.close()
    return out_files


def _launch_interactive_viewer(box_dims: Tuple[float, float, float],
                               piece_dims: Tuple[float, float, float],
                               distribution: Tuple[int, int, int],
                               stl_path: Optional[str] = None,
                               use_stl: bool = False,
                               title: str = "PackAssist - Visor 3D") -> str:
    """Obre una finestra interactiva en un procés independent (robust per Qt) idèntica a l'escriptori."""
    # Preparar dades en un JSON temporal
    try:
        data = {
            "box_dims": list(box_dims),
            "piece_dims": list(piece_dims),
            "distribution": list(distribution),
            "stl_path": stl_path if (stl_path and os.path.exists(stl_path)) else None,
            "use_stl": bool(use_stl),
            "title": title,
        }
        fd, json_path = tempfile.mkstemp(prefix="packassist_viewer_", suffix=".json")
        os.close(fd)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        # Localitzar l'script del visor
        script_path = os.path.join(os.path.dirname(__file__), "tools", "interactive_viewer.py")
        if not os.path.exists(script_path):
            return "❌ No s'ha trobat l'script del visor (tools/interactive_viewer.py)."

        # Llançar procés independent
        python_exe = sys.executable
        subprocess.Popen([python_exe, script_path, "--data", json_path], close_fds=True)
        return "✅ Visor interactiu obert en una finestra nova (procés separat)"
    except Exception as e:
        return f"❌ No s'ha pogut obrir el visor interactiu: {e}"


def _open_interactive_viewer(ol: float, ow: float, oh: float, ow_kg: float,
                             bl: float, bw: float, bh: float, max_kg: float,
                             stl_file, safety_percent: int):
    """Handler de Gradio: calcula i obre el visor interactiu idèntic a l'escriptori."""
    try:
        safety = max(0.5, min(1.0, float(safety_percent) / 100.0))
    except Exception:
        safety = 1.0
    summary, data = calcular_empaquetatge_precis(ol, ow, oh, ow_kg, bl, bw, bh, max_kg, True, safety)
    if not data or not data.get("best_orientation"):
        return summary + "\n\nℹ️ No hi ha dades per visualitzar.", ""
    dims = data["best_orientation"]["dimensions"]
    nx, ny, nz = [int(p) for p in data["best_orientation"]["distribution"].split("×")]
    stl_path = getattr(stl_file, 'name', None) if stl_file else None
    use_mesh = bool(STL_SUPPORT and stl_path and (nx*ny*nz) <= 100)
    status = _launch_interactive_viewer((bl, bw, bh), tuple(dims), (nx, ny, nz), stl_path=stl_path, use_stl=use_mesh)
    return summary, status


def _compute_plot_and_views_from_inputs(ol: float, ow: float, oh: float, ow_kg: float,
                                        bl: float, bw: float, bh: float, max_kg: float,
                                        stl_file, safety: float,
                                        gen_views: bool, use_stl_views: bool):
    """Antiga signatura: es manté per compatibilitat, però la UI només usarà un mode simplificat."""
    summary, data = calcular_empaquetatge_precis(ol, ow, oh, ow_kg, bl, bw, bh, max_kg, True, safety)
    gallery = []
    if PYVISTA_SUPPORT and data and data.get("best_orientation"):
        dims = data["best_orientation"]["dimensions"]
        nx, ny, nz = [int(p) for p in data["best_orientation"]["distribution"].split("×")]
        stl_path = getattr(stl_file, 'name', None) if stl_file else None
        total_units = nx * ny * nz
        use_mesh = bool(STL_SUPPORT and stl_path and total_units <= 60)
        try:
            gallery = _build_packing_views_pyvista((bl, bw, bh), tuple(dims), (nx, ny, nz),
                                                   stl_path=stl_path, use_stl=use_mesh)
        except Exception as e:
            summary += f"\n\n⚠️ Error generant vistes PyVista: {e}"
    elif not PYVISTA_SUPPORT:
        summary += "\n\nℹ️ Per a vistes exactes tipus Visualizer3D, instal·la 'pyvista' (pip install pyvista)."
    return summary, None, gallery

def _compute_summary_and_views_single_mode(ol: float, ow: float, oh: float, ow_kg: float,
                                           bl: float, bw: float, bh: float, max_kg: float,
                                           stl_file, safety_percent: int):
    """Mode únic: permet ajustar el percentatge de seguretat (50–100%). Retorna només el resum."""
    try:
        safety = max(0.5, min(1.0, float(safety_percent) / 100.0))
    except Exception:
        safety = 1.0
    summary, data = calcular_empaquetatge_precis(ol, ow, oh, ow_kg, bl, bw, bh, max_kg, True, safety)
    return summary


def optimize_by_weight(max_l: int, max_w: int, max_h: int, target_units: int) -> Optional[Tuple[int, int, int, int]]:
    """Troba la millor distribució per un nombre màxim d'unitats."""
    best_dist = None
    best_score = 0
    
    for l in range(1, max_l + 1):
        for w in range(1, max_w + 1):
            h = min(max_h, target_units // (l * w))
            if h >= 1:
                units = l * w * h
                if units <= target_units:
                    # Prioritzar menys alçada i més unitats
                    score = units - h * 0.01
                    if score > best_score:
                        best_score = score
                        best_dist = (l, w, h, units)
    
    return best_dist


def create_debug_info(orientations: list, max_weight: float, obj_weight: float) -> str:
    """Crea informació de debug quan no cap res."""
    debug = "📋 **Orientacions provades:**\n"
    max_by_weight = int(max_weight / obj_weight) if obj_weight > 0 else 0
    
    for ori in orientations:
        status = "✅" if ori["fits_weight"] else "⚖️"
        debug += f"   {status} **{ori['name']}**: {ori['units']} unitats ({ori['distribution']}) - Pes: {ori['weight']:.2f}kg\n"
    
    debug += f"\n💡 **Diagnòstic:**\n"
    debug += f"   • Capacitat màxima: {max_weight:.1f} kg\n"
    debug += f"   • Pes per unitat: {obj_weight:.3f} kg\n"
    debug += f"   • Màxim teòric per pes: {max_by_weight} unitats\n"
    
    if any(ori["units"] > 0 for ori in orientations):
        if max_by_weight > 0:
            debug += f"\n✅ **Solució**: {max_by_weight} unitats limitades per pes"
        else:
            debug += f"\n❌ **Problema**: El pes individual és massa alt"
    else:
        debug += f"\n❌ **Problema**: Les dimensions són massa grans per la caixa"
    
    return debug


def create_summary(theoretical: int, real: int, config: dict, safety: float, all_orientations: list) -> str:
    """Crea el resum final dels resultats."""
    
    # Informació principal
    summary = f"""
# 📦 RESULTATS

## 🎯 **Resultat Principal**
- **Unitats teòriques màximes:** {theoretical}**(per volum)**
- **Unitats reals (seguretat {safety:.0%}):** {real}
- **Orientació òptima:** {config['name']}
- **Distribució:** {config['distribution']} (L×W×H)

## ⚖️ **Anàlisi de Pes i Volum**
- **Pes total:** {config['weight']:.2f} kg
- **Eficiència volumètrica:** {config.get('vol_efficiency', 0):.1f}%
- **Eficiència de pes:** {config.get('weight_efficiency', 0):.1f}%

## 📐 **Dimensions de l'Orientació Òptima**
- **Llargada:** {config['dimensions'][0]:.2f} cm
- **Amplada:** {config['dimensions'][1]:.2f} cm  
- **Alçada:** {config['dimensions'][2]:.2f} cm
"""

    # Factor limitant
    if config.get('limited_by') == 'weight':
        summary += "\n⚖️ **Factor limitant:** PES (no dimensions)\n"
    
    # Taula de comparació d'orientacions
    if len(all_orientations) > 1:
        summary += "\n## 📊 **Comparació d'Orientacions**\n"
        summary += "| Orientació | Unitats | Distribució | Pes (kg) | Vol (%) | Pes (%) |\n"
        summary += "|------------|---------|-------------|----------|---------|----------|\n"
        
        for ori in all_orientations:
            status = "✅" if ori["fits_weight"] else "❌"
            summary += f"| {status} {ori['name']} | {ori['units']} | {ori['distribution']} | {ori['weight']:.1f} | {ori['vol_efficiency']:.1f} | {ori['weight_efficiency']:.1f} |\n"
    
    return summary


# Interfície Gradio simplificada i elegant
with gr.Blocks(
    title="📦 Calculadora de Capacitat - Simple i Precisa",
    theme=gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="gray",
        neutral_hue="slate"
    ),
    analytics_enabled=False,
    css="""
    /* Ocultar footer de Gradio completament */
    .gradio-container footer,
    .footer,
    .gradio-footer,
    [data-testid="footer"],
    .gradio-app footer,
    footer,
    .built-with {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* Ocultar enllaços d'API i configuració */
    .gradio-link,
    .api-link,
    .config-link {
        display: none !important;
    }
    
    /* Variables de color */
    :root {
        --bg-primary: #1a1a1a;
        --bg-secondary: #2d2d2d;
        --bg-card: #363636;
        --text-primary: #ffffff;
        --text-secondary: #cccccc;
        --accent-blue: #3b82f6;
        --accent-green: #10b981;
        --border-color: #4a5568;
    }
    
    /* Fons principal */
    .gradio-container, .gradio-app {
        background: var(--bg-primary) !important;
        color: var(--text-primary) !important;
    }
    
    /* Contenidor principal */
    .main-container { 
        max-width: 1200px; 
        margin: 0 auto; 
        color: var(--text-primary) !important;
    }
    
    /* Seccions d'input */
    .input-section { 
        background: var(--bg-card) !important; 
        padding: 25px !important; 
        border-radius: 12px !important; 
        border: 1px solid var(--border-color) !important;
        margin: 15px 0 !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3) !important;
    }
    
    /* Secció objecte amb accent blau */
    .objecte-section {
        border-left: 4px solid var(--accent-blue) !important;
        background: linear-gradient(135deg, var(--bg-card), rgba(59, 130, 246, 0.05)) !important;
    }
    
    /* Secció caixa amb accent verd */
    .caixa-section {
        border-left: 4px solid var(--accent-green) !important;
        background: linear-gradient(135deg, var(--bg-card), rgba(16, 185, 129, 0.05)) !important;
    }
    
    /* Forms diferents per cada secció */
    .objecte-section .form {
        border: 1px solid rgba(59, 130, 246, 0.2) !important;
        border-radius: 8px !important;
        padding: 15px !important;
        background: rgba(59, 130, 246, 0.02) !important;
    }
    
    .caixa-section .form {
        border: 1px solid rgba(16, 185, 129, 0.2) !important;
        border-radius: 8px !important;
        padding: 15px !important;
        background: rgba(16, 185, 129, 0.02) !important;
    }
    
    /* Inputs amb colors temàtics */
    .objecte-section input:focus {
        border-color: var(--accent-blue) !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3) !important;
    }
    
    .caixa-section input:focus {
        border-color: var(--accent-green) !important;
        box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.3) !important;
    }
    
    /* Secció càlcul amb accent groc */
    .calcul-section {
        border-left: 4px solid #fbbf24 !important;
        background: linear-gradient(135deg, var(--bg-card), rgba(251, 191, 36, 0.05)) !important;
    }
    
    .calcul-section .gradio-slider input[type="range"] {
        accent-color: #fbbf24 !important;
    }
    
    /* Capçaleres */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary) !important;
    }
    
    /* Labels i text */
    label, .gradio-label, p, span, div {
        color: var(--text-primary) !important;
    }
    
    /* Inputs */
    input, select, textarea {
        background: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 6px !important;
    }
    
    input:focus, select:focus, textarea:focus {
        border-color: var(--accent-blue) !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3) !important;
    }
    
    /* Botons */
    .gradio-button {
        background: var(--accent-blue) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 12px 24px !important;
    }
    
    .gradio-button:hover {
        background: #2563eb !important;
        transform: translateY(-1px) !important;
    }
    
    .gradio-slider {
        color: var(--text-primary) !important;
    }
    
    .gradio-slider input[type="range"] {
        accent-color: var(--accent-blue) !important;
    }
    
    /* Botó STL compacte */
    .stl-upload {
        max-height: 45px !important;
        min-height: 45px !important;
        max-width: 100px !important;
        background: var(--bg-secondary) !important;
        border: 1px solid var(--accent-blue) !important;
        border-radius: 6px !important;
    }
    
    /* Control específic del component file */
    .stl-upload .block {
        max-height: 45px !important;
        min-height: 45px !important;
        background: var(--bg-secondary) !important;
        border: 1px solid var(--accent-blue) !important;
        border-radius: 6px !important;
    }
    
    /* Label del STL més petit */
    .stl-upload label {
        font-size: 11px !important;
        font-weight: 600 !important;
        color: var(--accent-blue) !important;
        padding: 2px 4px !important;
    }
    
    /* Botó interior més compacte */
    .stl-upload button {
        font-size: 10px !important;
        padding: 4px 8px !important;
        min-height: 30px !important;
        max-height: 30px !important;
        background: transparent !important;
        border: none !important;
    }
    
    /* Ocultar icones i text innecessari */
    .stl-upload .icon-wrap,
    .stl-upload .or,
    .stl-upload button > div > span:first-child {
        display: none !important;
    }
    
    /* Només mostrar el text principal */
    .stl-upload button .wrap {
        font-size: 10px !important;
        line-height: 1.2 !important;
    }
    
    /* Àrea de resultats */
    .result-box { 
        background: var(--bg-card) !important; 
        border-left: 4px solid var(--accent-green) !important; 
        padding: 25px !important; 
        border-radius: 12px !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
    }
    
    /* Markdown content */
    .gradio-markdown {
        background: transparent !important;
        color: var(--text-primary) !important;
    }
    
    .gradio-markdown h1, .gradio-markdown h2, .gradio-markdown h3 {
        color: var(--accent-blue) !important;
    }
    
    /* Taules */
    table {
        background: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
    }
    
    th {
        background: var(--accent-blue) !important;
        color: white !important;
    }
    
    td {
        border: 1px solid var(--border-color) !important;
    }
    
    /* Separadors */
    hr {
        border-color: var(--border-color) !important;
    }
    
    /* Ajustar títol caixa per igualar alçada del botó STL */
    .caixa-title {
        margin-bottom: 20px !important; /* Reduït per millor equilibri */
        padding-bottom: 0 !important;
    }
    
    /* Millor alineació del botó STL */
    .stl-upload {
        align-self: flex-start !important; /* Alinear al principi */
        margin-top: 8px !important; /* Petit ajust vertical */
    }
    """
) as demo:
    
    gr.Markdown("""
    <div style="text-align: center; padding: 30px; background: linear-gradient(135deg, #3b82f6, #1e40af); border-radius: 15px; margin-bottom: 30px; box-shadow: 0 8px 25px rgba(59, 130, 246, 0.3);">
        <h1 style="color: white; margin: 0; font-size: 36px; font-weight: 800;">📦 Calculadora de Capacitat de Peces</h1>
        <p style="color: rgba(255, 255, 255, 0.9); margin: 10px 0 0 0; font-size: 18px;">Càlcul basat en l'Excel - Oriol Canillas</p>
    </div>
    """, elem_classes=["main-container"])
    
    with gr.Row():
        with gr.Column(scale=1, elem_classes=["input-section", "objecte-section"]):
            with gr.Row():
                with gr.Column(scale=3):
                    gr.Markdown("### 📏 **Dimensions de l'Objecte** (mm)")
                with gr.Column(scale=1):
                    if STL_SUPPORT:
                        stl_upload = gr.File(
                            label="STL", 
                            file_types=[".stl", ".STL"],
                            file_count="single",
                            elem_classes=["stl-upload"],
                            container=False,
                            height=45
                        )
                    else:
                        stl_upload = gr.File(visible=False)
            
            obj_l = gr.Number(value=50, label="Llargada (mm)", precision=2, minimum=0.01)
            obj_w = gr.Number(value=67, label="Amplada (mm)", precision=2, minimum=0.01)  
            obj_h = gr.Number(value=50, label="Alçada (mm)", precision=2, minimum=0.01)
            obj_weight = gr.Number(value=0.100, label="Pes (kg)", precision=4, minimum=0.001)
            
            # Missatge d'estat per STL
            stl_status = gr.Markdown("", visible=STL_SUPPORT)
        
        with gr.Column(scale=1, elem_classes=["input-section", "caixa-section"]):
            gr.Markdown("### 📦 **Dimensions de la Caixa** (mm)", elem_classes=["caixa-title"])
            
            box_l = gr.Number(value=100, label="Llargada (mm)", precision=1, minimum=0.1)
            box_w = gr.Number(value=150, label="Amplada (mm)", precision=1, minimum=0.1)
            box_h = gr.Number(value=200, label="Alçada (mm)", precision=1, minimum=0.1) 
            max_weight = gr.Number(value=2.0, label="Pes màxim (kg)", precision=1, minimum=0.1)
            # % de seguretat dins del bloc de la caixa
            safety_percent = gr.Slider(
                minimum=50,
                maximum=100,
                value=int(DEFAULT_SAFETY_FACTOR * 100),
                step=1,
                label="Percentatge de seguretat (%)",
                interactive=True,
            )
    
    with gr.Row():
        with gr.Column(elem_classes=["input-section", "calcul-section"]):
            with gr.Row():
                calculate_btn = gr.Button("🔍 CALCULAR CAPACITAT", variant="primary", size="lg")
    
    with gr.Row():
        with gr.Column(elem_classes=["result-box"]):
            results = gr.Markdown("", label="Resultats")
    
    # (galeria eliminada per simplificar la UI)
    # Estat del visor interactiu
    with gr.Row():
        with gr.Column():
            viewer_status = gr.Markdown(visible=True)
    
    # Informació de les dades carregades
    gr.Markdown("""
    ---
    ### 💡 **Com utilitzar:**
    1. **Introdueix les dimensions** del teu objecte i la caixa en **mil·límetres**
    2. **O puja un fitxer STL** per extreure dimensions automàticament
    3. **Especifica el pes** de l'objecte i la capacitat màxima de la caixa
    4. **Activa les rotacions** si l'objecte es pot orientar de diferents maneres
    5. **Ajusta el percentatge de seguretat** a la secció de la **caixa** (100% = exacte, 85% = marge)
    6. **Fes clic a Calcular** per obtenir el resultat i s'obrirà el visor interactiu en una finestra nova.
    
    La calculadora provarà totes les orientacions possibles i et donarà la millor solució considerant tant les dimensions com el pes.
    """)
    
    # Connectar l'upload d'STL si està disponible
    if STL_SUPPORT:
        stl_upload.change(
            fn=processar_stl_upload,
            inputs=[stl_upload],
            outputs=[obj_l, obj_w, obj_h, stl_status]
        )
    
    # Connectar el botó (mode únic)
    calculate_btn.click(
        fn=_compute_summary_and_views_single_mode,
        inputs=[obj_l, obj_w, obj_h, obj_weight, box_l, box_w, box_h, max_weight, stl_upload, safety_percent],
        outputs=[results]
    )
    # Obrir automàticament el visor interactiu després de calcular
    calculate_btn.click(
        fn=_open_interactive_viewer,
        inputs=[obj_l, obj_w, obj_h, obj_weight, box_l, box_w, box_h, max_weight, stl_upload, safety_percent],
        outputs=[results, viewer_status]
    )
    # (El botó manual per obrir el visor s'ha eliminat; el visor s'obre automàticament després de calcular.)

if __name__ == "__main__":
    demo.launch(
        show_api=True,
        show_error=True,
        inbrowser=True,
        quiet=False
    )
