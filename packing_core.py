"""Core packing logic shared across the Gradio UI and legacy helpers."""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional, Tuple

DEFAULT_SAFETY_FACTOR = 1.0


def optimize_by_weight(max_l: int, max_w: int, max_h: int, target_units: int) -> Optional[Tuple[int, int, int, int]]:
    """Troba la millor distribució limitada per pes, prioritzant menys alçada."""
    best_dist: Optional[Tuple[int, int, int, int]] = None
    best_score = float("-inf")

    for l in range(1, max_l + 1):
        for w in range(1, max_w + 1):
            h = min(max_h, target_units // (l * w))
            if h < 1:
                continue
            units = l * w * h
            if units > target_units:
                continue
            score = units - (h * 0.01)
            if score > best_score:
                best_score = score
                best_dist = (l, w, h, units)

    return best_dist


def create_debug_info(orientations: List[Dict[str, object]], max_weight: float, obj_weight: float) -> str:
    """Construeix un resum d'orientacions provades quan no cap cap peça."""
    debug = "📋 **Orientacions provades:**\n"
    max_by_weight = int(max_weight / obj_weight) if obj_weight > 0 else 0

    for ori in orientations:
        status = "✅" if ori.get("fits_weight") else "⚖️"
        debug += (
            f"   {status} **{ori['name']}**: {ori['units']} unitats "
            f"({ori['distribution']}) - Pes: {ori['weight']:.2f}kg\n"
        )

    debug += "\n💡 **Diagnòstic:**\n"
    debug += f"   • Capacitat màxima: {max_weight:.1f} kg\n"
    debug += f"   • Pes per unitat: {obj_weight:.3f} kg\n"
    debug += f"   • Màxim teòric per pes: {max_by_weight} unitats\n"

    if any(ori.get("units", 0) > 0 for ori in orientations):
        if max_by_weight > 0:
            debug += f"\n✅ **Solució**: {max_by_weight} unitats limitades per pes"
        else:
            debug += "\n❌ **Problema**: El pes individual és massa alt"
    else:
        debug += "\n❌ **Problema**: Les dimensions són massa grans per la caixa"

    return debug


def create_summary(
    theoretical: int,
    real: int,
    config: Dict[str, object],
    safety: float,
    all_orientations: List[Dict[str, object]],
) -> str:
    """Genera el resum final en Markdown."""
    dims = config.get("dimensions", (0.0, 0.0, 0.0)) if config else (0.0, 0.0, 0.0)
    summary = f"""
# 📦 RESULTATS

## 🎯 **Resultat Principal**
- **Unitats teòriques màximes:** {theoretical} **(per volum)**
- **Unitats reals (seguretat {safety:.0%}):** {real}
- **Orientació òptima:** {config.get('name', '—') if config else '—'}
- **Distribució:** {config.get('distribution', '0×0×0') if config else '0×0×0'} (L×W×H)

## ⚖️ **Anàlisi de Pes i Volum**
- **Pes total:** {config.get('weight', 0.0):.2f} kg
- **Eficiència volumètrica:** {config.get('vol_efficiency', 0.0):.1f}%
- **Eficiència de pes:** {config.get('weight_efficiency', 0.0):.1f}%

## 📐 **Dimensions de l'Orientació Òptima**
- **Llargada:** {dims[0]:.2f} mm
- **Amplada:** {dims[1]:.2f} mm  
- **Alçada:** {dims[2]:.2f} mm
"""

    if config and config.get("limited_by") == "weight":
        summary += "\n⚖️ **Factor limitant:** PES (no dimensions)\n"

    if len(all_orientations) > 1:
        summary += "\n## 📊 **Comparació d'Orientacions**\n"
        summary += "| Orientació | Unitats | Distribució | Pes (kg) | Vol (%) | Pes (%) |\n"
        summary += "|------------|---------|-------------|----------|---------|---------|\n"
        for ori in all_orientations:
            status = "✅" if ori.get("fits_weight") else "❌"
            summary += (
                f"| {status} {ori['name']} | {ori['units']} | {ori['distribution']} | "
                f"{ori['weight']:.1f} | {ori['vol_efficiency']:.1f} | {ori['weight_efficiency']:.1f} |\n"
            )

    return summary


def calcular_empaquetatge_precis(
    obj_l: float,
    obj_w: float,
    obj_h: float,
    obj_weight: float,
    box_l: float,
    box_w: float,
    box_h: float,
    max_weight: float,
    allow_rotation: bool = True,
    safety_factor: float = DEFAULT_SAFETY_FACTOR,
) -> Tuple[str, Dict[str, object]]:
    """Calcula la configuració òptima amb decimals per precisió."""
    if any(v <= 0 for v in [obj_l, obj_w, obj_h, obj_weight, box_l, box_w, box_h, max_weight]):
        return "❌ Tots els valors han de ser majors que 0.", {}
    if obj_weight > max_weight:
        return "❌ El pes d'una sola unitat supera la capacitat màxima de la caixa.", {}

    obj_dims = [Decimal(str(obj_l)), Decimal(str(obj_w)), Decimal(str(obj_h))]
    box_dims = [Decimal(str(box_l)), Decimal(str(box_w)), Decimal(str(box_h))]
    obj_weight_d = Decimal(str(obj_weight))
    max_weight_d = Decimal(str(max_weight))

    if allow_rotation:
        orientations = [
            (obj_dims[0], obj_dims[1], obj_dims[2]),
            (obj_dims[0], obj_dims[2], obj_dims[1]),
            (obj_dims[1], obj_dims[0], obj_dims[2]),
            (obj_dims[1], obj_dims[2], obj_dims[0]),
            (obj_dims[2], obj_dims[0], obj_dims[1]),
            (obj_dims[2], obj_dims[1], obj_dims[0]),
        ]
        orientation_names = [
            "Original (L×W×H)",
            "Rotació Y (L×H×W)",
            "Rotació Z (W×L×H)",
            "Rotació XY (W×H×L)",
            "Rotació XZ (H×L×W)",
            "Rotació YZ (H×W×L)",
        ]
    else:
        orientations = [(obj_dims[0], obj_dims[1], obj_dims[2])]
        orientation_names = ["Sense rotació"]

    best_fit = 0
    best_config: Optional[Dict[str, object]] = None
    all_orientations: List[Dict[str, object]] = []

    for i, (ol, ow, oh) in enumerate(orientations):
        fit_l = int(box_dims[0] // ol) if ol <= box_dims[0] else 0
        fit_w = int(box_dims[1] // ow) if ow <= box_dims[1] else 0
        fit_h = int(box_dims[2] // oh) if oh <= box_dims[2] else 0

        total_units = fit_l * fit_w * fit_h
        total_weight = float(Decimal(total_units) * obj_weight_d)

        vol_obj = float(ol * ow * oh)
        vol_box = float(box_dims[0] * box_dims[1] * box_dims[2])
        vol_efficiency = (total_units * vol_obj / vol_box * 100) if vol_box > 0 else 0.0
        weight_efficiency = (total_weight / float(max_weight_d) * 100) if max_weight_d > 0 else 0.0

        orientation_data: Dict[str, object] = {
            "name": orientation_names[i],
            "dimensions": (float(ol), float(ow), float(oh)),
            "units": total_units,
            "distribution": f"{fit_l}×{fit_w}×{fit_h}",
            "weight": total_weight,
            "vol_efficiency": vol_efficiency,
            "weight_efficiency": weight_efficiency,
            "fits_weight": total_weight <= float(max_weight_d),
        }
        all_orientations.append(orientation_data)

        if total_units > 0 and total_weight <= float(max_weight_d) and total_units > best_fit:
            best_fit = total_units
            best_config = orientation_data.copy()
            continue

        if total_units <= 0:
            continue

        max_by_weight = int(max_weight_d // obj_weight_d)
        if max_by_weight <= best_fit:
            continue
        best_dist = optimize_by_weight(fit_l, fit_w, fit_h, max_by_weight)
        if not best_dist or best_dist[3] <= best_fit:
            continue
        best_fit = best_dist[3]
        best_config = {
            "name": f"{orientation_names[i]} (Limitat per pes)",
            "dimensions": (float(ol), float(ow), float(oh)),
            "units": best_dist[3],
            "distribution": f"{best_dist[0]}×{best_dist[1]}×{best_dist[2]}",
            "weight": float(Decimal(best_dist[3]) * obj_weight_d),
            "vol_efficiency": (best_dist[3] * vol_obj / vol_box * 100) if vol_box > 0 else 0.0,
            "weight_efficiency": (float(Decimal(best_dist[3]) * obj_weight_d) / float(max_weight_d) * 100)
            if max_weight_d > 0
            else 0.0,
            "fits_weight": True,
            "limited_by": "weight",
        }

    if best_fit == 0 or not best_config:
        debug = create_debug_info(all_orientations, float(max_weight_d), float(obj_weight_d))
        return f"❌ No cap cap unitat a la caixa.\n\n{debug}", {}

    safety_factor = max(0.0, min(1.0, safety_factor))
    real_fit = max(1, int(Decimal(best_fit) * Decimal(str(safety_factor))))
    real_fit = min(real_fit, best_fit)

    summary = create_summary(best_fit, real_fit, best_config, safety_factor, all_orientations)
    return summary, {
        "theoretical_units": best_fit,
        "real_units": real_fit,
        "best_orientation": best_config,
        "all_orientations": all_orientations,
    }
