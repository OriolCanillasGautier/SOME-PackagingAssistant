"""
PackAssist - Mòdul principal d'inicialització
Aquest mòdul gestiona la importació de les funcions principals de PackAssist.
Amb fallback per a funcions que necessiten CadQuery quan aquest no està disponible.
"""

try:
    # Primer intentem importar des del mòdul complet
    from .stp_loader import get_stp_dimensions, validate_stp_file
    # Intentem importar funcions STL
    try:
        from .stl_loader import get_stl_dimensions, validate_stl_file
        print("✅ Mòdul 'cadquery' disponible: utilitzant versió completa de STP/STL loader")
    except ImportError:
        print("✅ Mòdul 'cadquery' disponible: utilitzant versió completa de STP loader")
except ImportError:
    # Si falla, utilitzem la versió simplificada
    from .stp_loader_simple import get_stp_dimensions, validate_stp_file
    print("⚠️ Mòdul 'cadquery' no disponible: utilitzant versió simplificada de STP loader")

# Exportem altres mòduls i funcions necessàries
try:
    from .optimizer import optimize_packing, calculate_theoretical_max
except ImportError as e:
    print(f"❌ Error important mòdul 'optimizer': {e}")