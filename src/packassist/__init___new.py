"""
PackAssist - Mòdul d'inicialització millorat
Sistema avançat de bin packing amb suport per geometries complexes
"""

# Import dialog classes
try:
    from .dialog_creator import CreateBoxDialog, CreateObjectDialog, EditDimensionsDialog
except ImportError as e:
    print(f"Error importing dialog creator: {e}")

try:
    # Intentar importar funcions STP
    from .stp_loader import get_stp_dimensions, validate_stp_file
    STP_SUPPORT = True
    print("Suport STP activat")
    
    # Intentar importar funcions STL
    try:
        from .stl_loader import get_stl_dimensions, validate_stl_file
        STL_SUPPORT = True
        print("Suport STL activat")
    except ImportError:
        STL_SUPPORT = False
        
        def get_stl_dimensions(filepath):
            """Fallback function quan STL no està disponible."""
            print(f"STL support no disponible: {filepath}")
            return None
        
        def validate_stl_file(filepath):
            """Fallback function quan STL no està disponible."""
            return False
            
except ImportError:
    # Fallback functions quan CadQuery no està disponible
    STP_SUPPORT = False
    STL_SUPPORT = False
    
    def get_stp_dimensions(filepath):
        """Fallback function quan CadQuery no està disponible."""
        print(f"CadQuery no disponible - no es pot llegir STP: {filepath}")
        return None
    
    def validate_stp_file(filepath):
        """Fallback function quan CadQuery no està disponible."""
        return False
    
    def get_stl_dimensions(filepath):
        """Fallback function quan STL no està disponible."""
        print(f"STL support no disponible: {filepath}")
        return None
    
    def validate_stl_file(filepath):
        """Fallback function quan STL no està disponible."""
        return False
    
    print("CadQuery no disponible: utilitzant funcions de fallback")

# Import optimization functions
from .optimizer import optimize_packing, calculate_theoretical_max, calculate_grid_packing

# Exportar funcions principals
__all__ = [
    'get_stp_dimensions',
    'validate_stp_file', 
    'get_stl_dimensions',
    'validate_stl_file',
    'optimize_packing',
    'calculate_theoretical_max',
    'calculate_grid_packing',
    'STP_SUPPORT',
    'STL_SUPPORT'
]
