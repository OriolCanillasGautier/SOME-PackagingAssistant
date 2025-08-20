# 🚀 PackAssist - Intelligent 3D Packaging Assistant

**A unified and simple application to optimize 3D part packaging**

## ✨ What does PackAssist do?

PackAssist is a **simple and direct** application that helps you calculate how many parts fit inside a box optimally.

### 🎯 Simple Workflow
1. **📂 Import** an STL file of your part
2. **✂️ Simplify** the mesh (optional) with integrated 3D viewer
3. **📦 Configure** box dimensions
4. **⚡ Calculate** optimal packaging automatically
5. **🎮 Visualize** the result in 3D

## 🚀 How to Run

### Method 1: Direct Execution
```bash
python packassist.py
```

### Method 2: Using the Modular Version
```bash
python packassist_modular.py
```

## 📁 Project Structure

```
SOME-PackagingAssistant/
├── 🚀 packassist.py                 # Main application with original GUI
├── 📱 packassist_modular.py         # Modular version of the application
├── 📱 packassist_new.py             # New experimental version
├── 📄 requirements.txt              # Dependencies
├── 📄 LICENSE                       # License
├── 📄 README.md                     # This file
│
├── 📁 actiu/                        # ✅ ACTIVE CODE AND DATA
│   ├── src/packassist/              # Core modules
│   │   ├── core/                    # Core functionality modules
│   │   ├── gui/                     # GUI components
│   │   └── utils/                   # Utility functions
│   ├── boxes/                       # Box definitions
│   ├── data/                        # Project data
│   ├── objects/                     # 3D objects
│   ├── results/                     # Calculation results
│   └── tools/                       # Additional tools
│
├── 📁 documentacio/                 # 📖 COMPLETE DOCUMENTATION
├── 📁 no-utilitzat/                 # 🗄️ OLD FILES
└── 📁 packassist_env/               # 🐍 VIRTUAL ENVIRONMENT
```

## 🔧 Main Features

### ✅ Fully Operational:
- **3D Packaging** with optimized algorithms
- **3D Visualization** with PyVista and matplotlib  
- **STP/STL Support** for complex geometries
- **Mesh Simplification** ultra-fast (multiple algorithms)
- **Advanced GUI** with threading for performance
- **Export** images and data

### 🎯 Key Features:
- **Modular Architecture**: Clean separation of concerns
- **High Performance**: Threading and automatic optimization
- **Cross-platform**: Pure Python, no .bat dependencies
- **Extensible Design**: Easy to add new features

## 📦 Installation

```bash
# 1. Clone repository
git clone https://github.com/OriolCanillasGautier/SOME-PackagingAssistant.git
cd SOME-PackagingAssistant

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python packassist.py
```

## 🚀 Quick Usage

### Basic Packaging:
```bash
python packassist.py
```

### Modular Version:
```bash
python packassist_modular.py
```

## 📦 Main Dependencies

- `pymeshlab` - Ultra-fast mesh simplification
- `pyvista` - Advanced 3D visualization
- `matplotlib` - Graphics and visualization
- `tkinter` - Graphical interface (included with Python)
- `trimesh` - Mesh processing
- `numpy` - Numerical calculations
- `cadquery` - CAD operations
- `py3dbp` - 3D bin packing algorithm

## 💡 Important Notes

- **Modular Design**: Core functionality separated into modules
- **Multiple Entry Points**: Different versions for different needs
- **Clean Structure**: Organized folder structure
- **100% Functional**: All features maintained

## 🆘 Troubleshooting

```bash
# If there are errors:
1. Check virtual environment: source packassist_env/bin/activate (Linux/Mac) or packassist_env\Scripts\activate (Windows)
2. Install dependencies: pip install -r requirements.txt  
3. Run application: python packassist.py
4. Check documentation in documentacio/ for more details
```

## 📞 Support

- **Documentation**: `documentacio/` folder
- **Testing**: Run with pytest for unit tests
- **Issues**: Report on GitHub repository

---

**✨ Completely reorganized system for maximum simplicity and efficiency ✨**