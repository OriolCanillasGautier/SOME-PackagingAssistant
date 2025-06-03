import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from py3dbp_enhanced.main import Packer, Bin, Item
import math

def optimize_packing(box_dims, obj_dims, max_attempts=100):
    """
    Calcula el nombre màxim d'objectes que caben en una caixa.
    
    Args:
        box_dims: Dict amb claus 'width', 'height', 'length'
        obj_dims: Dict amb claus 'width', 'height', 'length' 
        max_attempts: Nombre màxim d'objectes a intentar empaquetar
        
    Returns:
        Dict amb informació del resultat de l'empaquetament
    """
    try:
        # Validar dimensions
        if not all(key in box_dims for key in ['width', 'height', 'length']):
            raise ValueError("box_dims ha de tenir les claus: width, height, length")
        if not all(key in obj_dims for key in ['width', 'height', 'length']):
            raise ValueError("obj_dims ha de tenir les claus: width, height, length")
            
        # Verificar que l'objecte cap a la caixa
        if (obj_dims["width"] > box_dims["width"] or 
            obj_dims["height"] > box_dims["height"] or 
            obj_dims["length"] > box_dims["length"]):
            return {
                "max_objects": 0,
                "efficiency": 0.0,
                "box_volume": box_dims["width"] * box_dims["height"] * box_dims["length"],
                "used_volume": 0.0,
                "error": "L'objecte és massa gran per la caixa"
            }
        
        packer = Packer()

        # Crear caixa (bin) - py3dbp usa (name, width, height, depth, max_weight)
        box = Bin(
            name="Container",
            width=float(box_dims["width"]),
            height=float(box_dims["height"]),
            depth=float(box_dims["length"]),
            max_weight=99999.0  # Pes màxim arbitrari
        )
        packer.add_bin(box)

        # Afegir múltiples còpies de l'objecte
        for i in range(max_attempts):
            obj = Item(
                name=f"Product_{i}",
                width=float(obj_dims["width"]),
                height=float(obj_dims["height"]),
                depth=float(obj_dims["length"]),
                weight=1.0  # Pes arbitrari
            )
            packer.add_item(obj)

        packer.pack()
        
        # Calcular informació de l'empaquetament
        packed_items = len(box.items)
        box_volume = box_dims["width"] * box_dims["height"] * box_dims["length"]
        obj_volume = obj_dims["width"] * obj_dims["height"] * obj_dims["length"]
        used_volume = packed_items * obj_volume
        efficiency = (used_volume / box_volume) * 100 if box_volume > 0 else 0
        
        return {
            "max_objects": packed_items,
            "efficiency": round(efficiency, 2),
            "box_volume": round(box_volume, 2),
            "used_volume": round(used_volume, 2),
            "error": None
        }
        
    except Exception as e:
        return {
            "max_objects": 0,
            "efficiency": 0.0,
            "box_volume": 0.0,
            "used_volume": 0.0,
            "error": str(e)
        }

def calculate_theoretical_max(box_dims, obj_dims):
    """
    Calcula el nombre teòric màxim d'objectes basant-se només en volums.
    Això dóna una estimació optimista.
    """
    try:
        box_volume = box_dims["width"] * box_dims["height"] * box_dims["length"]
        obj_volume = obj_dims["width"] * obj_dims["height"] * obj_dims["length"]
        return math.floor(box_volume / obj_volume) if obj_volume > 0 else 0
    except:
        return 0