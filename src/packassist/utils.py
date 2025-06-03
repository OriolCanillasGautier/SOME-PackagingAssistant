"""
Utilitats per PackAssist
"""
import os
import math
from typing import Dict, List, Tuple, Optional

def create_simple_box_stp(width: float, height: float, depth: float, filename: str) -> bool:
    """
    Crea un fitxer STP simple d'una caixa rectangular.
    
    Args:
        width, height, depth: Dimensions en mm
        filename: Nom del fitxer de sortida
        
    Returns:
        bool: True si s'ha creat correctament
    """
    try:
        import cadquery as cq
        
        # Crear una caixa simple
        box = cq.Workplane("XY").box(width, height, depth)
        
        # Exportar com STP
        cq.exporters.export(box, filename, "STEP")
        
        print(f"✅ Creat fitxer STP: {filename}")
        return True
        
    except Exception as e:
        print(f"❌ Error creant {filename}: {e}")
        return False

def format_dimensions(dims: Dict[str, float]) -> str:
    """Formata les dimensions per mostrar."""
    return f"{dims['length']}×{dims['width']}×{dims['height']} mm"

def calculate_volume(dims: Dict[str, float]) -> float:
    """Calcula el volum a partir de les dimensions."""
    return dims['length'] * dims['width'] * dims['height']

def create_sample_stp_files():
    """Crea fitxers STP de mostra per testing."""
    print("🔧 Creant fitxers STP de mostra...")
    
    # Crear directoris
    os.makedirs("boxes", exist_ok=True)
    os.makedirs("objects", exist_ok=True)
    
    # Definir dimensions de mostra
    sample_boxes = [
        {"name": "box_small.stp", "dims": (100, 100, 50)},
        {"name": "box_medium.stp", "dims": (200, 150, 100)},
        {"name": "box_large.stp", "dims": (300, 250, 200)}
    ]
    
    sample_objects = [
        {"name": "product_small.stp", "dims": (30, 20, 15)},
        {"name": "product_medium.stp", "dims": (50, 40, 25)},
        {"name": "product_large.stp", "dims": (80, 60, 40)}
    ]
    
    # Crear caixes
    for box in sample_boxes:
        filepath = os.path.join("boxes", box["name"])
        if not os.path.exists(filepath):
            w, h, d = box["dims"]
            create_simple_box_stp(w, h, d, filepath)
    
    # Crear objectes
    for obj in sample_objects:
        filepath = os.path.join("objects", obj["name"])
        if not os.path.exists(filepath):
            w, h, d = obj["dims"]
            create_simple_box_stp(w, h, d, filepath)

def update_csv_with_samples():
    """Actualitza el CSV amb les mostres creades."""
    import csv
    
    sample_data = [
        {"type": "box", "name": "Caixa Petita", "file_path": "boxes/box_small.stp"},
        {"type": "box", "name": "Caixa Mitjana", "file_path": "boxes/box_medium.stp"},
        {"type": "box", "name": "Caixa Gran", "file_path": "boxes/box_large.stp"},
        {"type": "object", "name": "Producte Petit", "file_path": "objects/product_small.stp"},
        {"type": "object", "name": "Producte Mitjà", "file_path": "objects/product_medium.stp"},
        {"type": "object", "name": "Producte Gran", "file_path": "objects/product_large.stp"}
    ]
    
    os.makedirs("data", exist_ok=True)
    
    with open("data/index.csv", "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["type", "name", "file_path"])
        writer.writeheader()
        writer.writerows(sample_data)
    
    print("✅ CSV actualitzat amb dades de mostra")

def setup_sample_project():
    """Configura un projecte de mostra complet."""
    print("🚀 Configurant projecte de mostra...")
    create_sample_stp_files()
    update_csv_with_samples()
    print("✅ Projecte de mostra configurat!")
