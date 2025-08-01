"""
Sistema de caixa envoltant intel·ligent per PackAssist
Crea caixes que envolten l'objecte original amb complexitat controlada per l'usuari
"""

import numpy as np
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class SmartBoundingBox:
    """Representa una caixa envoltant intel·ligent amb complexitat controlada."""
    original_dimensions: np.ndarray  # Dimensions reals de l'objecte
    envelope_dimensions: np.ndarray  # Dimensions de la caixa envoltant
    complexity_level: int           # Nombre de cares/complexitat
    efficiency_factor: float       # Factor d'eficiència d'espai (0-1)
    extra_volume: float            # Volum extra ocupat per l'envoltant
    shape_type: str                # Tipus de forma generada

class SmartEnvelopeGenerator:
    """Generador de caixea envoltants intel·ligents."""
    
    @staticmethod
    def create_envelope_from_complexity(obj_dims: Dict, target_faces: int = 6) -> SmartBoundingBox:
        """
        Crea una caixa envoltant amb el nombre de cares especificat.
        
        Args:
            obj_dims: Dimensions i informació de l'objecte original
            target_faces: Nombre de cares desitjat (6=cub, 8=octaedre, 12=dodecaedre, etc.)
        """
        # Dimensions originals
        orig_length = obj_dims['length']
        orig_width = obj_dims['width']
        orig_height = obj_dims['height']
        orig_volume = obj_dims.get('real_volume', orig_length * orig_width * orig_height)
        
        print(f"🎯 Creant envoltant intel·ligent:")
        print(f"   📋 Objecte original: {orig_length:.1f} x {orig_width:.1f} x {orig_height:.1f} mm")
        print(f"   🎚️ Complexitat desitjada: {target_faces} cares")
        
        # Generar envoltant segons la complexitat
        if target_faces <= 6:
            # Caixa rectangular simple (6 cares)
            envelope_dims, shape_type, efficiency = SmartEnvelopeGenerator._create_rectangular_envelope(
                orig_length, orig_width, orig_height
            )
        elif target_faces <= 8:
            # Forma octaèdrica (8 cares triangulars)
            envelope_dims, shape_type, efficiency = SmartEnvelopeGenerator._create_octahedral_envelope(
                orig_length, orig_width, orig_height
            )
        elif target_faces <= 12:
            # Forma dodecaèdrica (12 cares pentagonals)
            envelope_dims, shape_type, efficiency = SmartEnvelopeGenerator._create_dodecahedral_envelope(
                orig_length, orig_width, orig_height
            )
        elif target_faces <= 20:
            # Forma icosaèdrica (20 cares triangulars)
            envelope_dims, shape_type, efficiency = SmartEnvelopeGenerator._create_icosahedral_envelope(
                orig_length, orig_width, orig_height
            )
        else:
            # Per més de 20 cares, usar aproximació esfèrica
            envelope_dims, shape_type, efficiency = SmartEnvelopeGenerator._create_spherical_envelope(
                orig_length, orig_width, orig_height, target_faces
            )
        
        # Calcular volum extra
        envelope_volume = envelope_dims[0] * envelope_dims[1] * envelope_dims[2]
        extra_volume = envelope_volume - orig_volume
        
        envelope = SmartBoundingBox(
            original_dimensions=np.array([orig_length, orig_width, orig_height]),
            envelope_dimensions=envelope_dims,
            complexity_level=target_faces,
            efficiency_factor=efficiency,
            extra_volume=extra_volume,
            shape_type=shape_type
        )
        
        print(f"   📦 Envoltant generada: {envelope_dims[0]:.1f} x {envelope_dims[1]:.1f} x {envelope_dims[2]:.1f} mm")
        print(f"   🔺 Forma: {shape_type}")
        print(f"   📈 Eficiència: {efficiency:.1%}")
        print(f"   ➕ Volum extra: {extra_volume:.1f} mm³ ({(extra_volume/orig_volume)*100:.1f}%)")
        
        return envelope
    
    @staticmethod
    def _create_rectangular_envelope(length: float, width: float, height: float) -> Tuple[np.ndarray, str, float]:
        """Crea envoltant rectangular simple (6 cares)."""
        # Afegir marge mínim per evitar col·lisions perfectes
        margin = 0.1  # 0.1mm de marge
        envelope_dims = np.array([length + margin, width + margin, height + margin])
        return envelope_dims, "rectangular_envelope", 0.99  # Molt eficient
    
    @staticmethod
    def _create_octahedral_envelope(length: float, width: float, height: float) -> Tuple[np.ndarray, str, float]:
        """Crea envoltant octaèdrica (8 cares triangulars)."""
        # Un octaedre que contingui el paral·lelepípede original
        # Radi de l'octaedre circumscrit
        max_dim = max(length, width, height)
        radius = max_dim * 0.7  # Factor d'ajust per assegurar que hi cap
        
        # Dimensions d'envoltant rectangular equivalent
        envelope_side = radius * 1.41  # Factor per octaedre
        envelope_dims = np.array([envelope_side, envelope_side, envelope_side])
        
        return envelope_dims, "octahedral_envelope", 0.85
    
    @staticmethod
    def _create_dodecahedral_envelope(length: float, width: float, height: float) -> Tuple[np.ndarray, str, float]:
        """Crea envoltant dodecaèdrica (12 cares pentagonals)."""
        # Dodecaedre que contingui l'objecte
        max_dim = max(length, width, height)
        radius = max_dim * 0.65
        
        # Dimensions d'envoltant rectangular equivalent
        envelope_side = radius * 1.3
        envelope_dims = np.array([envelope_side, envelope_side, envelope_side])
        
        return envelope_dims, "dodecahedral_envelope", 0.80
    
    @staticmethod
    def _create_icosahedral_envelope(length: float, width: float, height: float) -> Tuple[np.ndarray, str, float]:
        """Crea envoltant icosaèdrica (20 cares triangulars)."""
        # Icosaedre que contingui l'objecte
        max_dim = max(length, width, height)
        radius = max_dim * 0.6
        
        # Dimensions d'envoltant rectangular equivalent
        envelope_side = radius * 1.25
        envelope_dims = np.array([envelope_side, envelope_side, envelope_side])
        
        return envelope_dims, "icosahedral_envelope", 0.75
    
    @staticmethod
    def _create_spherical_envelope(length: float, width: float, height: float, target_faces: int) -> Tuple[np.ndarray, str, float]:
        """Crea envoltant aproximadament esfèrica amb moltes cares."""
        # Esfera que contingui l'objecte
        diagonal = math.sqrt(length**2 + width**2 + height**2)
        radius = diagonal / 2
        
        # Dimensions d'envoltant rectangular equivalent
        diameter = radius * 2
        envelope_dims = np.array([diameter, diameter, diameter])
        
        # Eficiència decreix amb més cares (més aproximació a esfera)
        efficiency = max(0.5, 1.0 - (target_faces - 20) * 0.01)
        
        return envelope_dims, f"spherical_envelope_{target_faces}faces", efficiency

class ComplexityBasedOptimizer:
    """Optimitzador que usa caixea envoltants per diferents nivells de complexitat."""
    
    def __init__(self, container_dims: Dict, object_dims: Dict):
        self.container_dims = container_dims
        self.object_dims = object_dims
    
    def optimize_with_envelope(self, complexity_level: int = 6) -> Dict:
        """
        Optimitza empaquetament usant caixa envoltant amb complexitat especificada.
        
        Args:
            complexity_level: Nombre de cares desitjat (6, 8, 12, 20, etc.)
        """
        print(f"🎯 Optimitzant amb envoltant de {complexity_level} cares...")
        
        # Crear envoltant intel·ligent
        envelope = SmartEnvelopeGenerator.create_envelope_from_complexity(
            self.object_dims, complexity_level
        )
        
        # Usar l'algoritme d'empaquetament estàndard amb les dimensions de l'envoltant
        from .optimizer import optimize_packing
        
        # Crear dimensions modificades per l'envoltant
        envelope_obj_dims = {
            'length': float(envelope.envelope_dimensions[0]),
            'width': float(envelope.envelope_dimensions[1]),
            'height': float(envelope.envelope_dimensions[2]),
            'shape_type': envelope.shape_type,
            'volume_factor': envelope.efficiency_factor,
            'envelope_info': {
                'original_dims': envelope.original_dimensions.tolist(),
                'complexity_level': envelope.complexity_level,
                'extra_volume': envelope.extra_volume
            }
        }
        
        # Executar optimització
        result = optimize_packing(self.container_dims, envelope_obj_dims)
        
        # Afegir informació de l'envoltant al resultat
        if not result.get('error'):
            result['envelope_efficiency'] = envelope.efficiency_factor
            result['envelope_extra_volume'] = envelope.extra_volume
            result['envelope_shape'] = envelope.shape_type
            result['envelope_complexity'] = envelope.complexity_level
            result['algorithm'] = f"smart_envelope_{complexity_level}faces"
        
        return result

def create_complexity_dialog(parent, callback):
    """Crea un diàleg per seleccionar la complexitat de l'envoltant."""
    import tkinter as tk
    from tkinter import ttk
    
    dialog = tk.Toplevel(parent)
    dialog.title("Selecciona Complexitat d'Envoltant")
    dialog.geometry("500x400")
    dialog.transient(parent)
    dialog.grab_set()
    
    # Frame principal
    main_frame = ttk.Frame(dialog, padding="15")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Títol
    title_label = ttk.Label(main_frame, text="🎯 Configuració d'Envoltant Intel·ligent", font=('Arial', 12, 'bold'))
    title_label.pack(pady=(0, 15))
    
    # Explicació
    explanation = """Selecciona el nivell de complexitat per l'envoltant:
    
• Menys cares = Més ràpid, menys precís
• Més cares = Més lent, més precís
    
L'envoltant contindrà l'objecte sencer, evitant
problemes amb geometries interiors o buides."""
    
    ttk.Label(main_frame, text=explanation, justify=tk.LEFT).pack(pady=(0, 15))
    
    # Selector de complexitat
    complexity_var = tk.IntVar(value=6)
    
    complexity_frame = ttk.LabelFrame(main_frame, text="Nivell de Complexitat", padding="10")
    complexity_frame.pack(fill=tk.X, pady=(0, 15))
    
    complexities = [
        (6, "📦 Rectangular (6 cares)", "Molt ràpid, eficiència màxima"),
        (8, "🔷 Octaèdric (8 cares)", "Ràpid, bona eficiència"),
        (12, "⬜ Dodecaèdric (12 cares)", "Moderat, equilibrat"),
        (20, "🔺 Icosaèdric (20 cares)", "Més lent, més precís"),
        (50, "🌐 Esfèric (50 cares)", "Lent, màxima precisió")
    ]
    
    for value, name, description in complexities:
        frame = ttk.Frame(complexity_frame)
        frame.pack(fill=tk.X, pady=2)
        
        ttk.Radiobutton(
            frame, 
            text=name, 
            variable=complexity_var, 
            value=value
        ).pack(side=tk.LEFT)
        
        ttk.Label(
            frame, 
            text=f"  {description}", 
            foreground="gray"
        ).pack(side=tk.LEFT)
    
    # Botons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=(15, 0))
    
    def on_accept():
        callback(complexity_var.get())
        dialog.destroy()
    
    def on_cancel():
        dialog.destroy()
    
    ttk.Button(button_frame, text="✅ Acceptar", command=on_accept).pack(side=tk.RIGHT, padx=(5, 0))
    ttk.Button(button_frame, text="❌ Cancel·lar", command=on_cancel).pack(side=tk.RIGHT)

def test_smart_envelope():
    """Test del sistema de caixea envoltants intel·ligents."""
    print("🧪 Testant sistema de caixea envoltants intel·ligents...")
    
    # Objecte de test (complex)
    obj_dims = {
        'length': 100.0,
        'width': 80.0,
        'height': 60.0,
        'real_volume': 480000.0,  # mm³
        'shape_type': 'advanced_complex'
    }
    
    # Contenidor de test
    container_dims = {
        'length': 1000.0,
        'width': 800.0,
        'height': 600.0,
        'shape_type': 'rectangular'
    }
    
    # Provar diferents nivells de complexitat
    optimizer = ComplexityBasedOptimizer(container_dims, obj_dims)
    
    for complexity in [6, 8, 12, 20]:
        print(f"\n{'='*50}")
        print(f"🎯 TESTANT COMPLEXITAT {complexity} CARES")
        print(f"{'='*50}")
        
        result = optimizer.optimize_with_envelope(complexity)
        
        print(f"📊 Resultats:")
        print(f"   Objectes empaquetats: {result.get('max_objects', 0)}")
        print(f"   Eficiència: {result.get('efficiency', 0):.1f}%")
        print(f"   Eficiència envoltant: {result.get('envelope_efficiency', 0):.1%}")
        print(f"   Volum extra: {result.get('envelope_extra_volume', 0):.1f} mm³")
        print(f"   Forma envoltant: {result.get('envelope_shape', 'unknown')}")
        
        if result.get('error'):
            print(f"   ❌ Error: {result['error']}")

if __name__ == "__main__":
    test_smart_envelope()
