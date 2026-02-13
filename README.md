# SOME-PackAssist

Version 0.0.3

SOME-PackAssist is a web-based packing calculator with 3D visualization (Three.js) and physics simulation (Rapier.js). It estimates how many parts fit in a box and renders the result interactively.

The application runs directly in the browser (ES Modules + CDN imports). No build step is required.

## Features

### Optimized mode
- Grid-based capacity calculation (6 orientations)
- STL/OBJ mesh support with real-volume computation
- Height-map nesting for irregular shapes (async, cancelable)
- Gravity-based stable orientation for STL pieces (settled pose + yaw search)
- Stable orientation is precomputed on STL load/simplify and reused in calculations (faster recalculation)
- Multiple gravity-stable bases are sampled and evaluated (better packing for asymmetric shapes)
- Material selector with estimated weight (aluminium, steel, plastic, copper, custom)
- Packing gap (spacing between pieces)
- Weight-limited optimization

### Bulk mode
- Physics-based simulation with gravity (Rapier.js WASM)
- Automatic capacity detection
- Multiple refill cycles (up to 4) with lid-press compaction
- Configurable vibration (frequency, amplitude, noise)
- Supports cuboid and STL geometries

### Mesh simplification
- Server-side decimation via PyMeshLab (best quality)
- Client-side fallback via Three.js SimplifyModifier
- Interactive preview with before/after comparison
- Convex-hull envelope option

### PDF reports
- Multi-view captures (isometric, front, top, side)
- Preview before download
- Catalan and English layouts
- Includes estimated material weight when configured

## Units

- Dimensions: millimeters (mm)
- Weight: kilograms (kg)
- STL files are assumed to be authored in mm

## Project structure

```
SOME-PackagingAssistant/
├── web/
│   ├── admin.html             # Admin tools (benchmark + orientation tester)
│   ├── index.html              # Main application
│   ├── historial.html          # Calculation history
│   ├── api/
│   │   └── start-server.php    # Auto-launcher for mesh_server.py
│   ├── css/
│   │   └── styles.css          # Styles (light/dark theme)
│   ├── js/
│   │   ├── main.js             # Application controller
│   │   ├── packing/
│   │   │   └── calculator.js   # Grid packing algorithm
│   │   ├── mesh/
│   │   │   ├── mesh-utils.js       # STL/OBJ loading, volume, stable-base
│   │   │   ├── mesh-simplifier.js  # Two-tier mesh simplification
│   │   │   └── simplification-modal.js
│   │   ├── visualization/
│   │   │   └── scene.js        # Three.js scene + height-map packing
│   │   ├── physics/
│   │   │   └── physics-world.js # Rapier.js physics engine
│   │   ├── report/
│   │   │   └── report-generator.js
│   │   └── storage/
│   │       ├── storage-manager.js
│   │       └── server-storage.js
│   └── library/                # STL library files
├── mesh_server.py              # PyMeshLab simplification micro-server
├── pdf_generator.py            # Server-side PDF generation (standalone)
├── env/                        # Python virtual environment
├── implementation.md           # Implementation plan
└── TODO.md                     # Feature backlog
```

## Quick start

### Option A: XAMPP (recommended for full features)

1. Clone the repository into your XAMPP htdocs directory:
   ```
   cd C:\xampp\htdocs\GitHub
   git clone <repo-url> SOME-PackagingAssistant
   ```

2. Open the application at:
   ```
   http://localhost/GitHub/SOME-PackagingAssistant/web/
   ```

3. Admin tools (benchmark, orientation tester, mesh inspector, weight check + watertight/leak check):
   ```
   http://localhost/GitHub/SOME-PackagingAssistant/web/admin.html
   ```

4. The mesh simplification server starts automatically on page load via PHP.
   If it doesn't (check the browser console), start it manually:
   ```
   cd SOME-PackagingAssistant
   env\Scripts\python.exe mesh_server.py
   ```

### Option B: Python dev server

```bash
cd web
python -m http.server 5555
```

Then open `http://localhost:5555`. Note: mesh simplification server must be started separately.

### Option C: Node.js

```bash
npx serve -l 5555 web
```

## Mesh simplification server

The optional Python server (`mesh_server.py`) provides high-quality mesh decimation using PyMeshLab. The browser falls back to a JS-only simplifier when the server is unavailable.

### Setup

```bash
# Create virtual environment (one-time)
python -m venv env

# Activate (Windows)
env\Scripts\activate

# Install dependencies
pip install pymeshlab

# Run the server
python mesh_server.py
```

The server listens on port 8787 by default. Endpoints:
- `GET /api/health` — status check
- `POST /api/simplify` — simplify an STL (body = binary STL, header `X-Target-Ratio` or query `?ratio=0.5`)

When running under XAMPP, the server is started automatically via `web/api/start-server.php` on page load.

## Technology

- **Three.js** (WebGL rendering)
- **Rapier.js** (WASM physics)
- **three-mesh-bvh** (BVH acceleration for intersection tests)
- **PyMeshLab** (optional, server-side mesh decimation)
- ES Modules (native browser modules, no bundler)
- CSS custom properties with automatic light/dark via `prefers-color-scheme`

## License

Copyright (c) 2025–2026 Oriol Canillas

