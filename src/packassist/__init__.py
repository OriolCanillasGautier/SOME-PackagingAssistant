"""
PackAssist - Mòdul principal d'inicialització
Aquest mòdul gestiona la importació de les funcions principals de PackAssist.
Amb fallback per a funcions que necessiten CadQuery quan aquest no està disponible.
"""

# Import dialog classes
try:
    from .dialog_creator import CreateBoxDialog, CreateObjectDialog, EditDimensionsDialog
except ImportError as e:
    print(f"❌ Error importing dialog creator: {e}")

try:
    # Primer intentem importar des del mòdul complet
    from .stp_loader import get_stp_dimensions, validate_stp_file
    STP_SUPPORT = True
    # Intentem importar funcions STL
    try:
        from .stl_loader import get_stl_dimensions, validate_stl_file
        STL_SUPPORT = True
        print("✅ Mòdul 'cadquery' disponible: utilitzant versió completa de STP/STL loader")
    except ImportError:
        STL_SUPPORT = False
        print("✅ Mòdul 'cadquery' disponible: utilitzant versió completa de STP loader")
except ImportError:
    # Si falla, utilitzem funcions de fallback
    STP_SUPPORT = False
    STL_SUPPORT = False
    
    def get_stp_dimensions(filepath):
        """Fallback function when CadQuery is not available."""
        print(f"⚠️ CadQuery not available - cannot read STP file: {filepath}")
        return None
    
    def validate_stp_file(filepath):
        """Fallback function when CadQuery is not available."""
        return False
    
    def get_stl_dimensions(filepath):
        """Fallback function when STL support is not available."""
        print(f"⚠️ STL support not available - cannot read STL file: {filepath}")
        return None
    
    def validate_stl_file(filepath):
        """Fallback function when STL support is not available."""
        return False
    
    print("⚠️ Mòdul 'cadquery' no disponible: utilitzant funcions de fallback")

# Exportem altres mòduls i funcions necessàries
# Import optimization functions
from .optimizer import optimize_packing, calculate_theoretical_max, calculate_grid_packing

# La visualización 3D ahora se maneja directamente desde app.py
# No necesitamos importar visualizadores externos