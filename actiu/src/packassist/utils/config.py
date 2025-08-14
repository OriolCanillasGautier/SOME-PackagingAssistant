"""
Configuració i constants per PackAssist
"""

import os
from pathlib import Path

# Directoris del projecte
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "actiu" / "results"
DATA_DIR = PROJECT_ROOT / "actiu" / "data"
OBJECTS_DIR = PROJECT_ROOT / "actiu" / "objects"
BOXES_DIR = PROJECT_ROOT / "actiu" / "boxes"

# Configuració de visualització
VISUALIZATION_CONFIG = {
    'default_window_size': (1200, 900),
    'background_color': 'white',
    'max_pieces_for_labels': 100,
    'max_pieces_for_gradient': 50,
    'performance_warning_threshold': 200,
    'optimization_threshold': 200
}

# Configuració d'exportació
EXPORT_CONFIG = {
    'timestamp_format': "%Y%m%d_%H%M%S",
    'default_formats': ['txt'],
    'image_format': 'png',
    'mesh_format': 'stl'
}

# Colors per visualització (colors sòlids i vibrantes com les pestanyes 1 i 2)
COLOR_PALETTE = [
    '#DC143C',  # Crimson
    '#1E90FF',  # DodgerBlue
    '#228B22',  # ForestGreen
    '#FF8C00',  # DarkOrange
    '#9370DB',  # MediumPurple
    '#D2691E',  # Chocolate
    '#FF1493',  # DeepPink
    '#696969',  # DimGray
    '#808000',  # Olive
    '#00CED1',  # DarkTurquoise
    '#B22222',  # FireBrick
    '#4169E1',  # RoyalBlue
    '#32CD32',  # LimeGreen
    '#FF6347',  # Tomato
    '#8A2BE2',  # BlueViolet
    '#CD853F',  # Peru
    '#FF69B4',  # HotPink
    '#2F4F4F',  # DarkSlateGray
    '#DAA520',  # GoldenRod
    '#48D1CC'   # MediumTurquoise
]

# Assegurar que els directoris existeixen
for directory in [RESULTS_DIR, DATA_DIR, OBJECTS_DIR, BOXES_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
