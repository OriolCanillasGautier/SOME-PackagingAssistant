# 🚀 PackAssist - Intelligent 3D Packaging Assistant

**A unified and powerful application to optimize 3D part packaging with advanced algorithms and visualization**

## ✨ What does PackAssist do?

PackAssist is an **intelligent and user-friendly** application that helps you calculate how many 3D parts fit inside a box optimally, with advanced visualization and mesh processing capabilities.

### 🎯 Key Features
- **3D Packaging Optimization** with multiple advanced algorithms
- **STL/STP File Support** for complex 3D geometries
- **Mesh Simplification** ultra-fast with multiple algorithms
- **3D Visualization** with PyVista and matplotlib  
- **Advanced GUI** with threading for performance
- **Oriented Bounding Box (OBB)** for optimal dimensions calculation
- **Export Capabilities** for images, data, and positioned STL files

## 🚀 How to Run

```bash
python packassist.py
```

## 📁 Project Structure

```
SOME-PackagingAssistant/
├── 🚀 packassist.py                 # Main application with enhanced GUI
├── 📄 requirements.txt              # Dependencies
├── 📄 packassist_config.json        # Visualization configuration
├── 📄 LICENSE                       # License
├── 📄 README.md                     # This file
│
├── 📁 actiu/                        # ✅ ACTIVE CODE AND DATA
│   ├── src/packassist/              # Core modules
│   │   ├── core/                    # Core functionality modules
│   │   ├── gui/                     # GUI components
│   │   ├── optimizers/              # Advanced packing algorithms
│   │   └── utils/                   # Utility functions
│   ├── boxes/                       # Box definitions
│   ├── data/                        # Project data
│   ├── objects/                     # 3D objects
│   └── results/                     # Calculation results
│
├── 📁 documentacio/                 # 📖 COMPLETE DOCUMENTATION
└── 📁 proves/                       # Test scripts
```

## 🔧 Main Features

### ✅ Fully Operational:
- **Advanced 3D Packaging** with optimized algorithms
- **Multi-algorithm Mesh Simplification** (PyMeshLab, PyVista, Trimesh, pyfqmr)
- **3D Visualization** with PyVista and matplotlib
- **STL/STP Support** for complex geometries
- **Threading** for responsive GUI performance
- **Oriented Bounding Box (OBB)** for optimal dimensions calculation
- **Export Capabilities** (Images, JSON, CSV, positioned STL)

### 🎯 Advanced Optimization Algorithms:
- **Floor Mode**: Organized floor-based packing with configurable margins and separation
- **Bulk Mode**: Free-form packing with collision detection
- **Intelligent Packing**: Advanced algorithms for optimal arrangement
- **OBB Integration**: Oriented Bounding Box for better packaging efficiency

## 📦 Installation

```bash
# 1. Clone repository
git clone https://github.com/OriolCanillasGautier/SOME-PackagingAssistant.git
cd SOME-PackagingAssistant

# 2. Create virtual environment (recommended)
python -m venv packassist_env
source packassist_env/bin/activate  # Linux/Mac
# or
packassist_env\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python packassist.py
```

## 🎮 Quick Usage

### Basic Packaging Workflow:
1. **📂 Import** an STL file of your part
2. **🔧 Simplify** the mesh (optional) with integrated 3D viewer
3. **📦 Configure** box dimensions and packing parameters
4. **⚡ Calculate** optimal packaging with advanced algorithms
5. **🎮 Visualize** the result in 3D with customizable options

### Packing Modes:
- **Floor Mode**: Organized grid-based packing with configurable floor separation and margins
- **Bulk Mode**: Free-form packing with collision detection and configurable piece spacing

## 🧠 Intelligent Features

### Oriented Bounding Box (OBB)
The OBB functionality automatically calculates the optimal orientation of parts for better packaging efficiency. This is enabled by default when loading STL meshes.

### Mesh Simplification
Ultra-fast mesh simplification with multiple algorithms:
- **PyMeshLab**: Fastest simplification with high quality
- **Trimesh**: Built-in simplification algorithms
- **PyVista**: Visualization-based simplification
- **pyfqmr**: Fast quadric mesh reduction

### Advanced Packing Algorithms
Multiple packing strategies for different use cases:
- **Intelligent Mode**: Advanced algorithms for optimal arrangement
- **Grid Mode**: Structured grid-based packing
- **Random Mode**: Randomized packing for testing

## 📦 Main Dependencies

- `pymeshlab` - Ultra-fast mesh simplification
- `pyvista` - Advanced 3D visualization
- `matplotlib` - Graphics and visualization
- `tkinter` - Graphical interface (included with Python)
- `trimesh` - Mesh processing
- `numpy` - Numerical calculations
- `cadquery` - CAD operations
- `py3dbp` - 3D bin packing algorithm
- `open3d` - Optional Oriented Bounding Box calculation
- `pybullet` - Physics simulation for collision detection

## 💡 Configuration

The application uses `packassist_config.json` for visualization settings:
- **Color schemes**: Density-based or solid colors
- **Wireframe settings**: Container visualization options
- **Camera settings**: Default viewing angles
- **Lighting**: Ambient and diffuse lighting controls

## 📤 Export Capabilities

- **Images**: 3D screenshots in PNG format
- **JSON Data**: Complete results with positions and rotations
- **CSV Tables**: Tabular data for spreadsheet import
- **Positioned STL**: STL files with parts in calculated positions

## 🆘 Troubleshooting

```bash
# If there are errors:
1. Check virtual environment: source packassist_env/bin/activate (Linux/Mac) or packassist_env\Scripts\activate (Windows)
2. Install dependencies: pip install -r requirements.txt  
3. Run application: python packassist.py
4. Check documentation in documentacio/ for more details
```

## 📚 Additional Documentation

See the `documentacio/` folder for detailed technical documentation:
- `STRUCTURE.md` - Complete project structure details
- `MESH_SIMPLIFICATION_README.md` - Mesh simplification guide
- `informe_obb_integration.md` - OBB integration report

## 📞 Support

- **Documentation**: `documentacio/` folder
- **Issues**: Report on GitHub repository

---

**✨ Advanced 3D packaging system with intelligent optimization algorithms ✨**