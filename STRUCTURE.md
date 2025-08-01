# Estructura del Projecte PackAssist

## 📁 Estructura Organitzada

```
SOME-PackagingAssistant/
├── 📄 packassist_simple.py          # ✅ APLICACIÓ PRINCIPAL - Usa aquesta!
├── 📄 requirements.txt              # Dependencies del projecte
├── 📄 README.md                     # Documentació principal
├── 📄 LICENSE                       # Llicència
│
├── 📁 tools/                        # Eines i utilitats
│   └── 📁 mesh_simplifiers/        # Simplificadors de malles STL
│       ├── 📄 advanced_stl_simplifier.py   # ✅ SIMPLIFICADOR GUI COMPLET (NOVA!)
│       ├── 📄 mesh_simplifier_simple.py    # Simplificador principal (sense emojis)
│       └── 📄 ultra_fast_mesh_simplifier.py # Simplificador avançat amb múltiples mètodes
│
├── 📁 tests/                        # Scripts de proves i testing
│   ├── 📄 test_mesh_simplification.py      # Proves de simplificació
│   └── 📄 create_test_objects.py           # Creació d'objectes de prova
│
├── 📁 legacy/                       # Versions antigues (per referència)
│   ├── 📄 app.py                    # Versió anterior de l'aplicació
│   └── 📄 app_new.py               # Altra versió anterior
│
├── 📁 src/                          # Codi font del backend
│   └── 📁 packassist/              # Mòduls principals
│
├── 📁 data/                         # Dades i configuracions
├── 📁 boxes/                        # Fitxers STL de caixes
├── 📁 objects/                      # Fitxers STL d'objectes
├── 📁 results/                      # Resultats dels càlculs
└── 📁 packassist_env/              # Entorn virtual Python
```

## 🚀 Com Usar

### Aplicació Principal
```bash
python packassist_simple.py
```

### Simplificadors de Malles
```bash
# 🎯 RECOMANAT: Simplificador GUI complet amb 3 pestanyes
python tools/mesh_simplifiers/advanced_stl_simplifier.py

# O amb accés directe (launcher opció 3)
stl_simplifier.bat

# Altres versions (per desenvolupament)
python tools/mesh_simplifiers/mesh_simplifier_simple.py
python tools/mesh_simplifiers/ultra_fast_mesh_simplifier.py
```

### Proves i Testing
```bash
# Proves de simplificació
python tests/test_mesh_simplification.py

# Crear objectes de prova
python tests/create_test_objects.py
```

## 📋 Descripció dels Fitxers

### Aplicació Principal
- **`packassist_simple.py`**: Aplicació principal amb 2 pestanyes (Càlcul + Exportació)
  - Calcula quants objectes caben en una caixa
  - Visualització 3D amb matplotlib
  - Exportació d'imatges i dades

### Eines de Simplificació
- **`advanced_stl_simplifier.py`**: ✅ **SIMPLIFICADOR GUI COMPLET** (RECOMANAT)
  - **GUI amb 3 pestanyes**: Simplificació + Visualització + Configuració
  - **4 algoritmes**: PyMeshLab (ultra-ràpid), PyVista, Trimesh, pyfqmr
  - **Visualització 3D**: Original vs simplificat amb comparació
  - **Threading**: Processament en background sense bloquejar GUI
  - **100% GUI**: No necessita terminal
  - **Accés directe**: Disponible via launcher opció 3 o `stl_simplifier.bat`

- **`mesh_simplifier_simple.py`**: Simplificador principal (versió console)
- **`ultra_fast_mesh_simplifier.py`**: Versió terminal amb múltiples algoritmes

### Tests i Proves
- **`test_mesh_simplification.py`**: Script complet de proves
- **`create_test_objects.py`**: Generació d'objectes de prova

### Legacy
- Versions anteriors de l'aplicació mantingudes per referència

## 🔧 Dependencies

Vegeu `requirements.txt` per la llista completa de dependencies.

Principals:
- `pymeshlab`: Simplificació de malles ultra-ràpida
- `matplotlib`: Visualització 3D
- `numpy`: Càlculs numèrics
- `tkinter`: Interfície gràfica (inclòs amb Python)

## 📝 Notes

- **Ús recomanat**: `packassist_simple.py` per l'aplicació principal
- **Simplificació**: Usa el botó "Accelerar càlcul" dins de l'aplicació principal
- **Desenvolupament**: Els fitxers a `tools/` i `tests/` són per desenvolupament avançat
