# PackAssist - Empaquetament Intel·ligent 3D

Una aplicació completa per calcular quants objectes caben en una caixa definida, amb visualització 3D i optimització de malles STL.

## 🚀 Ús Ràpid

### Aplicació Principal (Recomanat)
```bash
# Windows
packassist.bat

# O manualment
python packassist_simple.py
```

### Launcher Complet
```bash
# Windows
start.bat

# O manualment  
python launch.py
```

## 📁 Estructura del Projecte

```
📄 packassist_simple.py          # ✅ APLICACIÓ PRINCIPAL
📄 launch.py                     # Launcher amb menú d'opcions
📄 packassist.bat               # Accés ràpid Windows
📄 start.bat                    # Launcher Windows

📁 tools/                        # Eines i utilitats
  └── mesh_simplifiers/         # Simplificadors STL
      ├── mesh_simplifier_simple.py    # Simplificador principal
      └── ultra_fast_mesh_simplifier.py # Simplificador avançat

📁 tests/                       # Scripts de proves
📁 legacy/                      # Versions anteriors
📁 src/                         # Backend del projecte
```

Vegeu `STRUCTURE.md` per més detalls.

## 🎯 Funcionalitats Principals

### ✅ Aplicació Principal (`packassist_simple.py`)
- **Càlcul intel·ligent**: Determina automàticament quants objectes caben
- **Visualització 3D**: Mostra el resultat amb matplotlib
- **Optimització STL**: Botó per accelerar càlculs amb models complexos
- **Exportació múltiple**: Imatges des de 12 angles + dades JSON
- **Interfície clara**: 2 pestanyes (Càlcul + Exportació)

### � Simplificadors de Malles
- **Ultra-ràpid**: Redueix temps de 20+ minuts a 2-3 segons
- **Múltiples algoritmes**: PyMeshLab, PyVista, Trimesh, pyfqmr
- **Compatibilitat Windows**: Versió sense emojis per terminals Windows

## 📋 Requisits

- Python 3.8+
- Windows/Linux/macOS
- Dependencies: vegeu `requirements.txt`

## 🛠️ Instal·lació

### 1. Clonar el repositori
```bash
git clone <repository-url>
cd SOME-PackagingAssistant
```

### 2. Crear entorn virtual (recomanat)
```bash
python -m venv packassist
# Windows
packassist\Scripts\activate
# Linux/macOS  
source packassist/bin/activate
```

### 3. Instal·lar dependències
```bash
pip install -r requirements.txt
```

### 4. Configurar dades de mostra (opcional)
```bash
python setup_samples.py
```

## 🎮 Ús de l'Aplicació

### Execució principal
```bash
python app.py
```

### Opcions disponibles

#### 1. **Mode fitxers STP**
- Utilitza el fitxer `data/index.csv` per definir caixes i objectes
- Carrega models 3D automàticament
- Processa múltiples combinacions

#### 2. **Mode entrada manual**
- Introdueix dimensions directament
- Ideal per prototips ràpids
- No requereix fitxers STP

#### 3. **Sortir**
- Tanca l'aplicació

## 📁 Estructura del Projecte

```
SOME-PackagingAssistant/
├── app.py                 # Aplicació principal
├── setup_samples.py       # Configuració de mostra
├── requirements.txt       # Dependències
├── data/
│   └── index.csv         # Metadades de fitxers
├── boxes/                # Fitxers STP de contenidors
├── objects/              # Fitxers STP d'objectes
└── src/packassist/
    ├── __init__.py
    ├── stp_loader.py     # Càrrega de fitxers STP
    ├── optimizer.py      # Algoritmes d'optimització
    └── utils.py          # Utilitats generals
```

## 📊 Format del CSV

El fitxer `data/index.csv` ha de tenir aquesta estructura:

```csv
type,name,file_path
box,Caixa Petita,boxes/box_small.stp
box,Caixa Gran,boxes/box_large.stp
object,Producte A,objects/product_a.stp
object,Producte B,objects/product_b.stp
```

### Camps:
- **type**: "box" o "object"
- **name**: Nom descriptiu
- **file_path**: Ruta relativa al fitxer STP

## 🔧 Exemples d'Ús

### Exemple 1: Entrada Manual
```
📦 Introdueix les dimensions del contenidor:
Longitud (mm): 200
Amplada (mm): 150
Altura (mm): 100

📋 Introdueix les dimensions de l'objecte:
Longitud (mm): 50
Amplada (mm): 30
Altura (mm): 25
```

### Resultat:
```
📊 RESULTATS:
  ➕ Màxim teòric (per volum): 16 unitats
  ✅ Màxim real (3D packing): 12 unitats
  📈 Eficiència d'espai: 75.00%
  📏 Volum contenidor: 3000000.00 mm³
  📦 Volum utilitzat: 2250000.00 mm³
```

### Exemple 2: Fitxers STP
Carrega automàticament tots els models definits al CSV i mostra:
```
📦 Contenidor: Caixa Mitjana | Dimensions: {'length': 200.0, 'width': 150.0, 'height': 100.0, 'volume': 3000000.0}
  ➕ Objecte: Producte Petit
     📏 Dimensions: {'length': 30.0, 'width': 20.0, 'height': 15.0, 'volume': 9000.0}
     🔢 Màxim teòric: 333 unitats
     ✅ Màxim real: 280 unitats  
     📈 Eficiència: 84.00%
```

## 🧪 Testing

Per executar els tests (quan estiguin implementats):
```bash
pytest tests/
```

## 🚧 Resolució de Problemes

### Error instal·lació de paquets des de requirements.txt
```bash
pip install --only-binary :all: -r requirements.txt
```

### Error: "El fitxer index.csv no existeix"
```bash
python setup_samples.py
```

### Error: "Fitxer STP no vàlid"
- Verifica que els fitxers .stp existeixen
- Comprova les rutes al CSV
- Assegura't que els fitxers no estan corruptes

### Problemes de rendiment
- Redueix `max_attempts` a `optimizer.py`
- Utilitza dimensions més petites per testing
- Augmenta la RAM disponible

## 🤝 Contribucions

1. Fork del projecte
2. Crea una branca de funcionalitat
3. Commit dels canvis
4. Push a la branca
5. Obre un Pull Request

## 📄 Llicència

[Inclou aquí la informació de llicència]

## 📞 Suport

Per problemes o suggeriments:
- Obre un issue al repositori
- Contacta amb l'equip de desenvolupament

---

**Desenvolupat amb ❤️ per optimitzar l'eficiència d'empaquetament**
