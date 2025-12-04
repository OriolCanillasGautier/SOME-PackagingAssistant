#!/usr/bin/env python3
import base64
import gradio as gr
import numpy as np
from typing import Tuple, Optional, List
import tempfile
import os
import sys
import json
import subprocess
from functools import lru_cache
 
# Visualització 3D (Plotly) - opcional (ja no s'utilitza a la UI, però el deixem per fallback si cal)
PLOTLY_SUPPORT = False
go = None
pio = None
try:
    import importlib
    import importlib.util
    if importlib.util.find_spec("plotly.graph_objects") is not None:
        go = importlib.import_module("plotly.graph_objects")
        try:
            pio = importlib.import_module("plotly.io")
        except Exception:
            pio = None
        PLOTLY_SUPPORT = True
    else:
        PLOTLY_SUPPORT = False
except Exception:
    PLOTLY_SUPPORT = False
    go = None
    pio = None

# Constants i utilitats compartides
from packing_core import DEFAULT_SAFETY_FACTOR, calcular_empaquetatge_precis
from mesh_utils import (
    STL_SUPPORT,
    apply_permutation,
    canonicalize_to_obb,
    guess_perm_for_dims,
    load_trimesh,
    processar_stl_upload,
)


def _load_trimesh_cached(path: str):
    """Carrega l'STL usant una petita memòria cau basada en l'mtime."""
    if not STL_SUPPORT:
        return None
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = -1.0
    return _load_trimesh_with_stamp(path, mtime)


@lru_cache(maxsize=8)
def _load_trimesh_with_stamp(path: str, mtime: float):
    return load_trimesh(path)


def _figure_to_fullscreen_link(fig) -> str:
    if not (PLOTLY_SUPPORT and pio and fig is not None):
        return ""
    try:
        html = pio.to_html(fig, include_plotlyjs="cdn", full_html=True)
        encoded = base64.b64encode(html.encode("utf-8")).decode("ascii")
        data_uri = f"data:text/html;base64,{encoded}"
        return (
            f'<a class="fullscreen-link" href="{data_uri}" target="_blank" '
            f'rel="noopener">Pantalla completa 🔎</a>'
        )
    except Exception:
        return ""

# PyVista per a vistes "exactes" tipus Visualizer3D (imatges estàtiques)
PYVISTA_SUPPORT = False
try:
    import pyvista as pv
    PYVISTA_SUPPORT = True
except Exception:
    PYVISTA_SUPPORT = False

PYVISTA_QT_SUPPORT = False
if PYVISTA_SUPPORT:
    try:
        import pyvistaqt  # type: ignore
        PYVISTA_QT_SUPPORT = True
    except Exception:
        PYVISTA_QT_SUPPORT = False

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
                        stl_limit: int = 200) -> Optional[object]:
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

    mesh_payload = None
    if use_stl and stl_path and STL_SUPPORT:
        mesh_obj = _load_trimesh_cached(stl_path)
        if mesh_obj is not None:
            try:
                V, F, ext = canonicalize_to_obb(mesh_obj)
                perm = guess_perm_for_dims(ext, piece_dims)
                V = apply_permutation(V, perm)
                mesh_payload = (V, F)
            except Exception:
                mesh_payload = None

    # Peces: si es pot, usar STL fins a stl_limit, si no, arestes de cuboide
    drawn = 0
    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                if drawn >= limit_draw:
                    break
                x0, y0, z0 = ix * pl, iy * pw, iz * ph
                if mesh_payload is not None and drawn < stl_limit:
                    try:
                        V, F = mesh_payload
                        Vt = V + np.array([x0, y0, z0])
                        i, j, k = F[:, 0], F[:, 1], F[:, 2]
                        fig.add_trace(
                            go.Mesh3d(
                                x=Vt[:, 0],
                                y=Vt[:, 1],
                                z=Vt[:, 2],
                                i=i,
                                j=j,
                                k=k,
                                color="#3b82f6",
                                opacity=0.8,
                                name="Peça" if drawn == 0 else None,
                                showlegend=(drawn == 0),
                            )
                        )
                    except Exception:
                        px, py, pz = _make_cuboid_edges(x0, y0, z0, pl, pw, ph)
                        fig.add_trace(
                            go.Scatter3d(
                                x=px,
                                y=py,
                                z=pz,
                                mode="lines",
                                line=dict(color="#3b82f6", width=2),
                                name="Peça" if drawn == 0 else None,
                                showlegend=(drawn == 0),
                            )
                        )
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
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=420
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
    if use_stl and stl_path and os.path.exists(stl_path) and STL_SUPPORT:
        mesh_obj = _load_trimesh_cached(stl_path)
        if mesh_obj is not None:
            try:
                V, F, ext = canonicalize_to_obb(mesh_obj)
                perm = guess_perm_for_dims(ext, piece_dims)
                V = apply_permutation(V, perm)
                faces = np.hstack([np.full((F.shape[0], 1), 3, dtype=np.int64), F]).ravel()
                stl_mesh_pv = pv.PolyData(V, faces)
            except Exception:
                stl_mesh_pv = None

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
    """Obre una finestra interactiva en un procés independent (robust per Qt) idèntica a l'escriptori.
    Aquesta versió busca l'script interactiu a diverses rutes (interactive_viewer.py a l'arrel o tools/)."""
    # En mode empaquetat (PyInstaller), no disposem d'un intèrpret Python general per executar l'script extern.
    # Evitem intentar-ho per evitar errors i informem a l'usuari.
    try:
        if getattr(sys, "frozen", False):
            return ("ℹ️ El visor interactiu està desactivat en el mode EXE empaquetat. "
                    "Executa l'aplicació des del codi font per obrir el visor, o demana'ns "
                    "una versió empaquetada específica del visor.")
    except Exception:
        pass
    # Comprovació prèvia de PyVista (evitar obrir procés si no hi ha suport)
    if not PYVISTA_SUPPORT:
        return "ℹ️ PyVista no està instal·lat. Instala-ho amb: pip install pyvista pyvistaqt vtk"
    if not PYVISTA_QT_SUPPORT:
        return "ℹ️ PyVistaQt o els plugins de Qt no estan disponibles en aquest equip. Revisa la instal·lació (pip install pyvistaqt) o usa la vista incrustada."
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

        # Localitzar l'script del visor (preferir arrel, després tools/)
        base_dir = os.path.dirname(__file__)
        candidates = [
            os.path.join(base_dir, "interactive_viewer.py"),
            os.path.join(base_dir, "tools", "interactive_viewer.py"),
        ]
        script_path = None
        for c in candidates:
            if os.path.exists(c):
                script_path = c
                break
        if not script_path:
            return "❌ No s'ha trobat l'script del visor (interactive_viewer.py)."

        # Llançar procés independent
        python_exe = sys.executable
        subprocess.Popen([python_exe, script_path, "--data", json_path], close_fds=True)
        return "Visor interactiu obert en una finestra nova"
    except Exception as e:
        return f"❌ No s'ha pogut obrir el visor interactiu: {e}"


def _open_interactive_viewer(ol: float, ow: float, oh: float, ow_kg: float,
                             bl: float, bw: float, bh: float, max_kg: float,
                             stl_file, safety_percent: int, allow_rotation: bool):
    """Handler de Gradio: calcula i obre el visor interactiu idèntic a l'escriptori."""
    try:
        safety = max(0.5, min(1.0, float(safety_percent) / 100.0))
    except Exception:
        safety = 1.0
    summary, data = calcular_empaquetatge_precis(ol, ow, oh, ow_kg, bl, bw, bh, max_kg, allow_rotation, safety)
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
                                        gen_views: bool, use_stl_views: bool,
                                        allow_rotation: bool = True):
    """Antiga signatura: es manté per compatibilitat, però la UI només usarà un mode simplificat."""
    summary, data = calcular_empaquetatge_precis(ol, ow, oh, ow_kg, bl, bw, bh, max_kg, allow_rotation, safety)
    gallery = []
    if PYVISTA_SUPPORT and data and data.get("best_orientation"):
        dims = data["best_orientation"]["dimensions"]
        nx, ny, nz = [int(p) for p in data["best_orientation"]["distribution"].split("×")]
        stl_path = getattr(stl_file, 'name', None) if stl_file else None
        total_units = nx * ny * nz
        use_mesh = bool(STL_SUPPORT and stl_path and stl_visual_limit > 0)
        try:
            gallery = _build_packing_views_pyvista((bl, bw, bh), tuple(dims), (nx, ny, nz),
                                                   stl_path=stl_path, use_stl=use_mesh)
        except Exception as e:
            summary += f"\n\n⚠️ Error generant vistes PyVista: {e}"
    elif not PYVISTA_SUPPORT:
        summary += "\n\nℹ️ Per a vistes exactes tipus Visualizer3D, instal·la 'pyvista' (pip install pyvista)."
    return summary, None, gallery


def _compute_summary_and_inline_plot(ol: float, ow: float, oh: float, ow_kg: float,
                                     bl: float, bw: float, bh: float, max_kg: float,
                                     stl_file, safety_percent: int, allow_rotation: bool,
                                     stl_visual_limit: float):
    """Calcula la solució i construeix una vista 3D incrustada (Plotly) per al navegador."""
    try:
        safety = max(0.5, min(1.0, float(safety_percent) / 100.0))
    except Exception:
        safety = 1.0

    summary, data = calcular_empaquetatge_precis(ol, ow, oh, ow_kg, bl, bw, bh, max_kg, allow_rotation, safety)

    inline_plot = None
    status_msg = ""
    fullscreen_link = ""

    if data and data.get("best_orientation"):
        dims = data["best_orientation"]["dimensions"]
        distribution_text = data["best_orientation"].get("distribution", "0×0×0")
        try:
            nx, ny, nz = (int(part) for part in distribution_text.split("×"))
        except Exception:
            nx = ny = nz = 0

        stl_path = getattr(stl_file, "name", None) if stl_file else None
        total_units = nx * ny * nz
        use_mesh = bool(STL_SUPPORT and stl_path and total_units <= 60)

        if PLOTLY_SUPPORT:
            try:
                inline_plot = _build_packing_plot(
                    (bl, bw, bh), tuple(dims), (nx, ny, nz),
                    stl_path=stl_path if use_mesh else None,
                    use_stl=use_mesh,
                    stl_limit=int(max(0, stl_visual_limit)),
                )
                if inline_plot is not None:
                    status_msg = "✅ Vista 3D incrustada al navegador. Usa el botó inferior per obrir el visor PyVista opcional."
                else:
                    status_msg = "ℹ️ Plotly no està disponible. Instal·la'l amb: pip install plotly."
            except Exception as exc:
                status_msg = f"⚠️ Error renderitzant la vista 3D: {exc}"
        else:
            status_msg = "ℹ️ Plotly no està disponible. Instal·la'l amb: pip install plotly."
    else:
        status_msg = "ℹ️ Cap configuració vàlida per visualitzar. Revisa les dimensions i el pes."

    fullscreen_component = gr.update(value="", visible=False)
    if inline_plot is not None:
        fullscreen_link = _figure_to_fullscreen_link(inline_plot)
        fullscreen_component = gr.update(value=fullscreen_link, visible=bool(fullscreen_link))

    return summary, inline_plot, status_msg, fullscreen_component


def _compute_summary_and_views_single_mode(ol: float, ow: float, oh: float, ow_kg: float,
                                           bl: float, bw: float, bh: float, max_kg: float,
                                           stl_file, safety_percent: int, allow_rotation: bool,
                                           stl_visual_limit: float):
    """Mode únic: permet ajustar el percentatge de seguretat (50–100%). Retorna només el resum."""
    summary, _, _, _ = _compute_summary_and_inline_plot(
        ol, ow, oh, ow_kg, bl, bw, bh, max_kg,
        stl_file, safety_percent, allow_rotation, stl_visual_limit,
    )
    return summary


def _open_viewer_only_status(ol: float, ow: float, oh: float, ow_kg: float,
                             bl: float, bw: float, bh: float, max_kg: float,
                             stl_file, safety_percent: int, allow_rotation: bool):
    """Obre el visor interactiu i retorna només l'estat, sense modificar el resum."""
    try:
        safety = max(0.5, min(1.0, float(safety_percent) / 100.0))
    except Exception:
        safety = 1.0
    # Reutilitzem el càlcul per obtenir la millor distribució
    _, data = calcular_empaquetatge_precis(ol, ow, oh, ow_kg, bl, bw, bh, max_kg, allow_rotation, safety)
    if not data or not data.get("best_orientation"):
        return "ℹ️ Cap configuració vàlida per visualitzar. Revisa les dimensions i el pes."
    if not PYVISTA_QT_SUPPORT:
        return "ℹ️ PyVistaQt no està disponible en aquest equip. Fes servir la vista incrustada o instal·la pyvistaqt/Qt."
    dims = data["best_orientation"]["dimensions"]
    nx, ny, nz = [int(p) for p in data["best_orientation"]["distribution"].split("×")]
    stl_path = getattr(stl_file, 'name', None) if stl_file else None
    use_mesh = bool(STL_SUPPORT and stl_path and (nx*ny*nz) <= 100)
    status = _launch_interactive_viewer((bl, bw, bh), tuple(dims), (nx, ny, nz), stl_path=stl_path, use_stl=use_mesh)
    return status



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
        --bg-primary: #f8fafc;
        --bg-secondary: #ffffff;
        --bg-card: #e2e8f0;
        --text-primary: #111827;
        --text-secondary: #334155;
        --accent-blue: #2563eb;
        --accent-green: #059669;
        --border-color: #cbd5f5;
    }

    @media (prefers-color-scheme: dark) {
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

    .fullscreen-link {
        display: inline-block;
        margin-top: 6px;
        padding: 6px 12px;
        border-radius: 8px;
        background: var(--accent-blue);
        color: white !important;
        text-decoration: none;
        font-weight: 600;
    }

    .fullscreen-link:hover {
        opacity: 0.9;
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
            allow_rotation = gr.Checkbox(value=True, label="Permet girar l'objecte (6 orientacions)")
            stl_visual_limit = gr.Slider(
                minimum=10,
                maximum=600,
                value=200,
                step=10,
                label="Límit de peces STL visibles (Plotly)",
                interactive=True,
            )
            
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
            viewer_plot = gr.Plot(label="Vista 3D incrustada", height=480)
            viewer_status = gr.Markdown(
                "ℹ️ Calcula per veure la vista 3D incrustada."
                + (" Si prefereixes el visor PyVista en finestra separada, prem el botó inferior." if PYVISTA_QT_SUPPORT else " PyVistaQt no està disponible en aquest equip."),
                visible=True,
            )
            viewer_fullscreen_link = gr.HTML("", visible=False)

    with gr.Row():
        with gr.Column():
            open_viewer_btn = gr.Button("🖼️ Obrir visor 3D (PyVista)", variant="secondary", visible=PYVISTA_SUPPORT and PYVISTA_QT_SUPPORT)
    
    # Informació de les dades carregades
    gr.Markdown("""
    ---
    ### 💡 **Com utilitzar:**
    1. **Introdueix les dimensions** del teu objecte i la caixa en **mil·límetres**
    2. **O puja un fitxer STL** per extreure dimensions automàticament
    3. **Especifica el pes** de l'objecte i la capacitat màxima de la caixa
    4. **Activa o desactiva “Permet girar”** segons si vols provar totes les orientacions
    5. **Ajusta el percentatge de seguretat** (aplica un factor al resultat final; 85% = més marge)
    6. **Defineix el límit de peces STL** visibles al Plotly si treballes amb malles (per defecte 200)
    7. **Fes clic a Calcular** per obtenir el resum i una vista 3D interactiva al navegador (Plotly)
    8. **Prem "Obrir visor 3D (PyVista)"** si vols la finestra externa (requereix PyVista + PyVistaQt amb plugins Qt)
    
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
        fn=_compute_summary_and_inline_plot,
        inputs=[
            obj_l, obj_w, obj_h, obj_weight,
            box_l, box_w, box_h, max_weight,
            stl_upload, safety_percent, allow_rotation, stl_visual_limit,
        ],
        outputs=[results, viewer_plot, viewer_status, viewer_fullscreen_link]
    )

    # Botó opcional per obrir el visor interactiu basat en PyVista
    open_viewer_btn.click(
        fn=_open_viewer_only_status,
        inputs=[obj_l, obj_w, obj_h, obj_weight, box_l, box_w, box_h, max_weight, stl_upload, safety_percent, allow_rotation],
        outputs=[viewer_status]
    )
    # (El visor PyVista és opcional; la vista Plotly incrustada funciona encara que PyVista no estigui instal·lat.)

if __name__ == "__main__":
    demo.launch(
        show_api=True,
        show_error=True,
        inbrowser=True,
        quiet=False
    )
