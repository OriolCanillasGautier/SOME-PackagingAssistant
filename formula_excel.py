import gradio as gr
import numpy as np
import pandas as pd
from typing import Tuple, Optional
from decimal import Decimal, ROUND_HALF_UP
import math
import tempfile
import os

# Constants per defecte
DEFAULT_SAFETY_FACTOR = 0.85

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
# 📦 RESULTATS DEL CÀLCUL D'EMPAQUETATGE

## 🎯 **Resultat Principal**
- **Unitats teòriques màximes:** {theoretical}
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
            
            obj_l = gr.Number(value=217, label="Llargada (mm)", precision=2, minimum=0.01)
            obj_w = gr.Number(value=106, label="Amplada (mm)", precision=2, minimum=0.01)  
            obj_h = gr.Number(value=50, label="Alçada (mm)", precision=2, minimum=0.01)
            obj_weight = gr.Number(value=0.307, label="Pes (kg)", precision=4, minimum=0.001)
            
            # Missatge d'estat per STL
            stl_status = gr.Markdown("", visible=STL_SUPPORT)
        
        with gr.Column(scale=1, elem_classes=["input-section", "caixa-section"]):
            gr.Markdown("### 📦 **Dimensions de la Caixa** (mm)", elem_classes=["caixa-title"])
            
            box_l = gr.Number(value=1000, label="Llargada (mm)", precision=1, minimum=0.1)
            box_w = gr.Number(value=450, label="Amplada (mm)", precision=1, minimum=0.1)
            box_h = gr.Number(value=400, label="Alçada (mm)", precision=1, minimum=0.1) 
            max_weight = gr.Number(value=60.0, label="Pes màxim (kg)", precision=1, minimum=0.1)
    
    with gr.Row():
        with gr.Column(elem_classes=["input-section", "calcul-section"]):
            gr.Markdown("### ⚙️ **Opcions de Càlcul**")
            
            with gr.Row():
                safety_factor = gr.Slider(
                    minimum=0.5, maximum=1.0, value=DEFAULT_SAFETY_FACTOR, step=0.05,
                    label="Factor de seguretat",
                    interactive=True,
                    scale=2
                )
                calculate_btn = gr.Button("🔍 CALCULAR CAPACITAT", variant="primary", size="lg", scale=1)
    
    with gr.Row():
        with gr.Column(elem_classes=["result-box"]):
            results = gr.Markdown("", label="Resultats")
    
    # Informació de les dades carregades
    gr.Markdown("""
    ---
    ### 💡 **Com utilitzar:**
    1. **Introdueix les dimensions** del teu objecte i la caixa en **mil·límetres**
    2. **O puja un fitxer STL** per extreure dimensions automàticament
    3. **Especifica el pes** de l'objecte i la capacitat màxima de la caixa
    4. **Activa les rotacions** si l'objecte es pot orientar de diferents maneres
    5. **Ajusta el factor de seguretat** segons les teves necessitats (0.85 = 85% de la capacitat teòrica)
    6. **Fes clic a Calcular** per obtenir el resultat òptim
    
    La calculadora provarà totes les orientacions possibles i et donarà la millor solució considerant tant les dimensions com el pes.
    """)
    
    # Connectar l'upload d'STL si està disponible
    if STL_SUPPORT:
        stl_upload.change(
            fn=processar_stl_upload,
            inputs=[stl_upload],
            outputs=[obj_l, obj_w, obj_h, stl_status]
        )
    
    # Connectar el botó
    calculate_btn.click(
        fn=lambda ol, ow, oh, ow_kg, bl, bw, bh, max_kg, safety: calcular_empaquetatge_precis(
            ol, ow, oh, ow_kg, bl, bw, bh, max_kg, True, safety  # Sempre permetre rotacions
        )[0],  # Només retornem el text del resum
        inputs=[obj_l, obj_w, obj_h, obj_weight, box_l, box_w, box_h, max_weight, safety_factor],
        outputs=[results]
    )

if __name__ == "__main__":
    demo.launch(
        show_api=True,
        show_error=True,
        inbrowser=False,
        quiet=False
    )
