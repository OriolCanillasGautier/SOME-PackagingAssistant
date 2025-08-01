# 🚀 PackAssist - Aplicació Simple d'Empaquetament Intel·ligent

**Aplicació unificada i simple per optimitzar l'empaquetament de peces 3D**

## ✨ Què fa PackAssist?

PackAssist és una aplicació **simple i directa** que t'ajuda a calcular quantes peces caben dins una caixa de manera òptima.

### 🎯 Workflow Simple
1. **📂 Importa** un fitxer STL de la teva peça
2. **� Simplifica** la malla (opcional) amb visualitzador 3D integrat
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

## 📁 Estructura Ultra Neta

```
SOME-PackagingAssistant/
├── 🚀 launch.py                    # PUNT D'ENTRADA PRINCIPAL
├── 📱 packassist_gui.py            # Aplicació GUI completa
├── 📱 packassist_simple.py         # Aplicació simple (2 pestanyes)
├── 📄 requirements.txt             # Dependencies
├── 📄 LICENSE                      # Llicència
│
├── 📁 actiu/                       # ✅ TOT EL CODI FUNCIONAL
│   ├── src/packassist/             # Mòduls principals
│   ├── tools/mesh_simplifiers/     # Simplificadors de malles
│   ├── tests/                      # Scripts de proves
│   ├── data/, boxes/, objects/     # Dades del projecte
│   └── results/                    # Resultats dels càlculs
│
├── 📁 documentacio/                # 📖 DOCUMENTACIÓ COMPLETA
├── 📁 no-utilitzat/                # 🗄️ FITXERS ANTICS
└── 📁 packassist_env/              # 🐍 ENTORN VIRTUAL
```

## 🎯 Opcions del Launcher

Executa `python launch.py` i tria:

1. **🚀 PackAssist GUI** - Interfície completa (RECOMANAT)
2. **🎯 Aplicació Simple** - 2 pestanyes bàsiques  
3. **🔧 Simplificador STL Avançat** - GUI amb 3 pestanyes
4. **⚡ Simplificador Ultra Ràpid** - Terminal amb múltiples algoritmes
5. **🔧 Simplificador Simple** - Versió bàsica
6. **🧪 Proves de Simplificació** - Testing avançat
7. **❌ Sortir**

## 🔧 Funcionalitats Principals

### ✅ Completament Operatives:
- **Empaquetament 3D** amb algoritmes optimitzats
- **Visualització 3D** amb PyVista i matplotlib  
- **Suport STP/STL** per geometries complexes
- **Simplificació de malles** ultra-ràpida (4 algoritmes)
- **GUI avançada** amb threading per rendiment
- **Exportació** d'imatges i dades

### 🎯 Característiques Destacades:
- **Sistema unificat**: Un sol launcher per tot
- **Estructura neta**: Només 3 carpetes + essencials
- **Alt rendiment**: Threading i optimització automàtica
- **Multiplataforma**: Python pur, sense dependencies de .bat

## 📦 Instal·lació

```bash
# 1. Clonar repositori
git clone https://github.com/OriolCanillasGautier/SOME-PackagingAssistant.git
cd SOME-PackagingAssistant

# 2. Instal·lar dependencies
pip install -r requirements.txt

# 3. Executar
python launch.py
```

## 🚀 Ús Ràpid

### Empaquetament Bàsic:
```bash
python launch.py  # → Opció 1 o 2
```

### Simplificació de Malles STL:
```bash  
python launch.py  # → Opció 3 (GUI recomanat)
```

### Desenvolupament/Testing:
```bash
python launch.py  # → Opció 6 (proves)
```

## 📦 Dependencies Principals

- `pymeshlab` - Simplificació ultra-ràpida
- `pyvista` - Visualització 3D avançada
- `matplotlib` - Gràfics i visualització
- `tkinter` - Interfície gràfica (inclòs amb Python)
- `trimesh` - Processament de malles
- `numpy` - Càlculs numèrics

## 🔍 Neteja Realitzada (Agost 2025)

### ✅ Reorganització Ultra Neta:
- **Eliminats .bat**: No necessaris, Python funciona directament
- **3 carpetes úniques**: actiu/, documentacio/, no-utilitzat/
- **Launcher unificat**: Un sol punt d'entrada
- **Paths corregits**: Tots els imports actualitzats
- **Estructura clara**: Només l'essencial a l'arrel

### 🗂️ Sistema de Carpetes:
- **`actiu/`**: Tot el codi i dades que es fan servir
- **`documentacio/`**: Tota la documentació consolidada  
- **`no-utilitzat/`**: Versions antigues i experiments

## 💡 Notes Importants

- **Un sol punt d'entrada**: `python launch.py`
- **Sense .bat**: Sistema 100% Python, multiplataforma
- **Estructura neta**: Només 3 carpetes + fitxers essencials
- **100% funcional**: Totes les característiques mantingudes

## 🆘 Resolució de Problemes

```bash
# Si hi ha errors:
1. Verifica entorn virtual: packassist_env/Scripts/activate
2. Instal·la dependencies: pip install -r requirements.txt  
3. Executa launcher: python launch.py
4. Consulta documentacio/ per més detalls
```

## 📞 Suport

- **Documentació**: Carpeta `documentacio/`
- **Esquema actual**: `ESQUEMA_ACTUAL.md`
- **Proves**: Launcher opció 6

---

**✨ Sistema completament reorganitzat per màxima simplicitat i eficiència ✨**