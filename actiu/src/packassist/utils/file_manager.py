"""
Gestió de fitxers i utilitats
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from .config import RESULTS_DIR, DATA_DIR

def generate_timestamp_filename(base_name: str, extension: str = "txt") -> str:
    """Genera un nom de fitxer amb timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}.{extension}"

def save_results_file(content: str, filename: str = None) -> str:
    """Guarda contingut a la carpeta de resultats"""
    if filename is None:
        filename = generate_timestamp_filename("packassist_results")
    
    filepath = RESULTS_DIR / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return str(filepath)

def load_mesh_file(filepath: str):
    """Carrega un fitxer de malla (STL/STP)"""
    import trimesh
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Fitxer no trobat: {filepath}")
    
    try:
        mesh = trimesh.load(filepath)
        if hasattr(mesh, 'vertices') and hasattr(mesh, 'faces'):
            return mesh
        else:
            raise ValueError("El fitxer no conté una malla vàlida")
    except Exception as e:
        raise ValueError(f"Error carregant el fitxer: {e}")

def backup_file(filepath: str) -> str:
    """Crea una còpia de seguretat d'un fitxer"""
    backup_path = f"{filepath}.backup"
    shutil.copy2(filepath, backup_path)
    return backup_path

def clean_old_results(days_to_keep: int = 30):
    """Neteja resultats antics"""
    import time
    current_time = time.time()
    cutoff_time = current_time - (days_to_keep * 24 * 60 * 60)
    
    for file_path in RESULTS_DIR.glob("*"):
        if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
            file_path.unlink()
            print(f"Eliminat fitxer antic: {file_path.name}")
