# SOME-PackAssist

Version 0.0.4

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
- Configurable STL placement strategies: stable contact, hybrid, physics-assisted, and legacy
- Support-aware upper-layer validation with stability strictness, side-stacking toggle, and search-effort control
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
├── physics-engine/             # GPU/CPU packing engines
│   ├── packer_gpu.py           # CUDA-accelerated SAT packer
│   ├── packer_final.py         # CPU voxel occupancy packer
│   ├── packer_physics.py       # CPU physics-based packer
│   ├── engine/                 # Standalone GPU physics engine
│   │   ├── hull.py             # Convex hull generation (CPU, scipy)
│   │   ├── collision.py        # GPU SAT narrow-phase
│   │   ├── broadphase.py       # GPU spatial hashing broad phase
│   │   ├── contacts.py         # GPU contact manifold generation
│   │   ├── dynamics.py         # GPU rigid body integrator + impulse solver
│   │   └── world.py            # Orchestrator (step loop, memory mgmt)
│   ├── PhysicsEngine/          # C# / Silk.NET OpenGL packer (legacy)
│   └── stl/                    # Test STL mesh files
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

## GPU-accelerated packer

Three packers available in `physics-engine/`:

| Packer | Method | Speed | Best for |
|--------|--------|-------|----------|
| `packer_gpu.py` | Greedy DBLF | 30s | Baseline, simple shapes |
| `packer_best.py --method greedy` | Batched GPU DBLF | 14-18s | Faster greedy (same result) |
| `packer_best.py --method backtrack` | Greedy + backtracking | 2-5min | Finding better arrangements |
| `packer_best.py --shrink 0.4` | Shrunk-hull collision proxy | 4-6min | **388 pieces** (was 112) |
| `packer_best.py --compact` | Physics compaction | +time | Post-processing settling |

### Quick test

```bash
source env/bin/activate

# Greedy (fast)
python physics-engine/packer_best.py physics-engine/stl/6683688_simp0.1pct.stl --method greedy

# Backtracking (slower, tries to improve)
python physics-engine/packer_best.py physics-engine/stl/6683688_simp0.1pct.stl --method backtrack

# With physics compaction
python physics-engine/packer_best.py physics-engine/stl/6683688_simp0.1pct.stl --compact
```

### Benchmark results

| Test | Shape | Box | Greedy | Backtrack | Fill |
|------|-------|-----|--------|-----------|------|
| 6683688 | Irregular STL | 385x285x150 | **84 pcs** | 84 pcs | 3.0% (51% of theoretical max¹) |
| Cube 20mm | Procedural cube | 200x200x150 | **500 pcs** | 500 pcs | 66.7% (near-perfect) |

¹ The part is 96.7% empty space within its bounding box — volume fill is a misleading metric.
84 pieces fills the XZ floor 2 layers deep, hitting the physical limit for this shape.

### Architecture

```
packer_best.py
├── GPU kernel: batched Y-scanning SAT (all candidates in one launch)
├── pack_greedy(): bottom-deepest placement
├── pack_backtrack(): remove-last-N, reorder, retry
└── compact(): GPU physics settling via engine/world.py
```

## Technology

- **Three.js** (WebGL rendering)
- **Rapier.js** (WASM physics)
- **three-mesh-bvh** (BVH acceleration for intersection tests)
- **PyMeshLab** (optional, server-side mesh decimation)
- ES Modules (native browser modules, no bundler)
- CSS custom properties with automatic light/dark via `prefers-color-scheme`

## License

Copyright (c) 2025–2026 Oriol Canillas

