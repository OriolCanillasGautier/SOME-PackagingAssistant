# PackAssist - 3D Bin Packing Optimizer

Una eina per optimitzar l'empaquetament 3D que calcula dinàmicament el nombre màxim d'objectes que poden encaixar en un contenidor personalitzat.

## 🎯 Objectius del Projecte

- **Pont entre visió i implementació**: Permet l'entrada manual de dimensions o càrrega de models 3D (fitxers STP)
- **Valor estratègic**: Facilita decisions basades en dades sobre disseny de contenidors i col·locació d'objectes
- **Escalabilitat i flexibilitat**: Disseny modular que suporta futures millores com GUI, processament en lot, o algoritmes avançats

## 🚀 Funcionalitats

### ✅ Implementades
- **Entrada flexible**: Dimensions manual o fitxers STP
- **Optimització 3D**: Utilitza algoritmes de bin packing per càlcul real
- **Anàlisi comparativa**: Compara màxim teòric vs. real
- **Gestió d'errors robusta**: Validació completa d'entrades
- **Interfície interactiva**: Menú de consola amigable
- **Informes detallats**: Eficiència d'espai, volums utilitzats, etc.

### 🔮 Futures millores
- GUI amb PyQt o Tkinter
- Visualització 3D dels resultats
- Exportació de resultats (PDF, Excel)
- Algoritmes ML per optimització topològica
- API REST per integració
- Processament en lot

## 📋 Requisits del Sistema

- Python 3.8+
- Windows/Linux/macOS
- Memòria: 4GB RAM mínim
- Espai: 2GB per dependències

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

### Error: "ModuleNotFoundError: No module named 'cadquery'"
```bash
pip install cadquery==2.3.0
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
