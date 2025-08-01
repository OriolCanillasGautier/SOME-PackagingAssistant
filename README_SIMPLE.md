# 🚀 PackAssist - Aplicació Simple d'Empaquetament Intel·ligent

**Aplicació unificada i simple per optimitzar l'empaquetament de peces 3D**

## ✨ Què fa PackAssist?

PackAssist és una aplicació **simple i directa** que t'ajuda a calcular quantes peces caben dins una caixa de manera òptima.

### 🎯 Workflow Simple
1. **📂 Importa** un fitxer STL de la teva peça
2. **🔧 Simplifica** la malla (opcional) amb visualitzador 3D integrat
3. **📦 Configura** les dimensions de la caixa
4. **⚡ Calcula** l'empaquetament òptim automàticament
5. **🎮 Visualitza** el resultat en 3D

## 🚀 Com Executar

### Mètode 1: Executar Directament
```bash
python start.py
```

### Mètode 2: Executar l'Aplicació Principal
```bash
python packassist.py
```

## 📋 Requisits

### Dependències Essencials
```bash
pip install tkinter numpy trimesh
```

### Dependències Opcionals (per funcionalitat avançada)
```bash
pip install pymeshlab pyvista
```

## 🎮 Com Usar l'Aplicació

### STEP 1: Importar STL 📂
- Clica "Seleccionar STL" 
- Tria el teu fitxer .stl
- Veuràs la informació de la malla: vèrtexs, cares, volum

### STEP 2: Simplificar (Opcional) 🔧  
- Si la malla té massa poligons, clica "Obrir Simplificador 3D"
- Ajusta el nombre de vèrtexs amb el slider
- Simplifica i accepta els canvis
- **Visualitzador 3D integrat** per veure els canvis en temps real

### STEP 3: Configurar Caixa 📦
- Introdueix les dimensions de la caixa en mm
- Format: Llargada × Amplada × Altura
- Exemple: 200 × 150 × 100

### STEP 4: Optimitzar ⚡
- Clica "🚀 Calcular Empaquetament Òptim"
- L'algoritme calcularà automàticament:
  - Quantes peces caben
  - Eficiència d'empaquetament
  - Posicions òptimes

### Visualització 3D 🎮
- Un cop calculat, clica "🎮 Visualitzar 3D"
- Veuràs la caixa i les peces col·locades
- Navegació 3D interactiva

## 🏗️ Estructura del Projecte

```
PackAssist/
├── packassist.py          # 🎯 APLICACIÓ PRINCIPAL
├── start.py              # 🚀 Executar simple
├── README.md             # 📖 Aquesta documentació
├── requirements.txt      # 📦 Dependències
├── actiu/               # 📂 Codi actiu
│   ├── src/packassist/  # 🛠️ Motors d'optimització
│   └── tools/           # 🔧 Eines auxiliars
├── documentacio/        # 📚 Documentació
└── no-utilitzat/        # 🗄️ Codi legacy
```

## 🎯 Característiques Principals

### ✅ Integració Completa
- **Una sola aplicació** - no cal escollir entre múltiples eines
- **Workflow lineal** - segueix els passos 1→2→3→4
- **Visualització integrada** - tot en una finestra

### 🔧 Simplificador Avançat
- **4 algoritmes** de simplificació diferents
- **Visualitzador 3D** en temps real
- **Control precís** del nivell de detall
- **Preservació del volum** intel·ligent

### ⚡ Optimitzador Intel·ligent
- **Algoritmes avançats** de bin packing
- **Múltiples orientacions** automàtiques
- **Optimització de rotacions**
- **Cálcul d'eficiència** precís

### 🎮 Visualització 3D
- **PyVista integrat** per visualització professional
- **Navegació interactiva** 3D
- **Colors diferenciats** per cada peça
- **Vista isomètrica** automàtica

## 🛠️ Funcionalitats Tècniques

### Formats Suportats
- **STL** (ASCII i Binary)
- **Mètrica** en mil·límetres
- **Precisió** decimal completa

### Algoritmes Integrats
- **Simplificació**: Quadric Edge Collapse, Clustering, Edge Length
- **Empaquetament**: Bottom-Left Fill, Best Fit, Genetic Algorithm
- **Visualització**: Rendering en temps real amb PyVista

### Gestió d'Errors Robusta
- **Fallbacks automàtics** si falten dependències
- **Validació d'entrada** completa
- **Missatges d'error** clars en català
- **Recuperació automàtica** d'errors no crítics

## 🎓 Exemples d'Ús

### Cas Típic: Peces Petites
```
📂 Peça: widget_petit.stl (5x3x2 cm)
📦 Caixa: 30x20x15 cm  
⚡ Resultat: 60 peces (85% eficiència)
```

### Cas Avançat: Peça Complexa
```
📂 Peça: engranatge_complex.stl (2M poligons)
🔧 Simplifica: 50K poligons (preserva 98% volum)
📦 Caixa: 25x25x10 cm
⚡ Resultat: 12 peces (78% eficiència)
🎮 Visualitza: Posicions optimitzades en 3D
```

## 🆘 Resolució de Problemes

### Error: "Trimesh no està instal·lat"
```bash
pip install trimesh
```

### Error: "PyVista no està instal·lat" 
```bash
pip install pyvista
```

### Error: Malla buida o corrupta
- Verifica que el fitxer STL sigui vàlid
- Prova obrir-lo amb altre software 3D primer

### Error: Dimensions invàlides
- Assegura't que totes les dimensions siguin positives
- Usa punts decimals, no comes (ex: 10.5 no 10,5)

## 🎯 Avantatges de l'Aplicació Unificada

### ✅ Per a l'Usuari
- **Un sol fitxer** per executar - `python start.py`
- **Interfície intuïtiva** amb passos clars
- **No cal escollir** entre múltiples aplicacions
- **Workflow lògic** i seqüencial

### ✅ Tecnològicament
- **Codi centralitzat** en un sol fitxer
- **Gestió d'errors robusta** amb fallbacks
- **Dependències opcionals** - funciona amb el mínim
- **Modular internament** però simple externament

---

## 🚀 Començar Ara

1. **Descarrega** o clona el repositori
2. **Instal·la** dependències: `pip install trimesh numpy`
3. **Executa**: `python start.py`
4. **Importa** el teu STL i segueix els passos!

**🎯 Simple, directe, efectiu - PackAssist fa que l'empaquetament 3D sigui fàcil!**
