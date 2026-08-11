# SOME-PackAssist

Version 0.0.5

SOME-PackAssist is a web-based packing calculator with 3D visualization (Three.js) and physics simulation (Rapier.js). It estimates how many parts fit in a box and renders the result interactively.

The application runs directly in the browser (ES Modules + CDN imports). No build step is required.

## Features

### Optimized mode
- Height-map BVH nesting for irregular shapes (async, cancelable)
- Multi-layer grid-optimized Phase 1 + greedy Phase 2
- Gravity-based stable orientation for STL pieces with 6 axis permutations + 36 yaw angles
- Configurable STL placement strategies: stable contact, hybrid, physics-assisted, and legacy
- Support-aware upper-layer validation with stability strictness, side-stacking toggle, and search-effort control
- Material selector with estimated weight (aluminium, steel, plastic, copper, custom)
- Packing gap and weight-limited optimization

### Fast Optimizer mode
- BVH-validated compressed grid with brick pattern support
- Compaction factors down to 40% of bounding box for tight concave nesting
- Instant results — no iterative search

### Bulk mode
- Physics-based simulation with gravity (Rapier.js WASM)
- Multiple refill cycles (up to 4) with lid-press compaction
- Configurable vibration (frequency, amplitude, noise)
- Supports cuboid and STL geometries

### GPU Voxel mode
- CUDA-accelerated sparse-voxel packing via backend server
- Voxelizes each orientation at 0.5mm resolution — handles concave nesting natively
- Dual-GPU support for 2× throughput
- Polling-based async job submission with progress
- Downloads merged STL result and renders in Three.js

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
├── server.py                   # Unified Flask backend (API + static files)
├── web/
│   ├── index.html              # Main application
│   ├── admin.html              # Admin tools (benchmark + orientation tester)
│   ├── historial.html          # Calculation history
│   ├── api/
│   │   └── start-server.php    # Auto-launcher (XAMPP/nginx+PHP)
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
├── output/                     # Timestamped packing results (gitignored)
│   └── YYYY-MM-DD_HHMMSS_*/
│       ├── packed_2d.png
│       ├── packed_3d.png
│       ├── packed_layers.png
│       ├── merged.stl
│       └── info.txt
├── physics-engine/             # GPU/CPU packing engines
│   ├── server.py               # (legacy — now project root server.py)
│   ├── packer_best.py          # CUDA SAT packer with beam search + hierarchical scan
│   ├── packer_gpu_voxel.py     # CUDA sparse-voxel packer (best fill rate)
│   ├── packer_api.py           # (legacy — merged into server.py)
│   ├── packer_gpu.py           # Base CUDA SAT packer
│   ├── packer_cpu.py           # CPU brute-force packer
│   ├── packer_final.py         # CPU voxel occupancy packer
│   ├── packer_physics_drop.py  # CPU physics-based packer
│   ├── engine/                 # Standalone GPU physics engine
│   │   ├── hull.py             # Convex hull generation (CPU, scipy)
│   │   ├── collision.py        # GPU SAT narrow-phase
│   │   ├── broadphase.py       # GPU spatial hashing broad phase
│   │   ├── contacts.py         # GPU contact manifold generation
│   │   ├── dynamics.py         # GPU rigid body integrator + impulse solver
│   │   └── world.py            # Orchestrator (step loop, memory mgmt)
│   ├── PhysicsEngine/          # C# / Silk.NET OpenGL packer (legacy)
│   └── stl/                    # Test STL mesh files
├── mesh_server.py              # (legacy — merged into server.py)
├── pdf_generator.py            # Server-side PDF generation (standalone)
├── env/                        # Python virtual environment
├── implementation.md           # Implementation plan
└── TODO.md                     # Feature backlog
```

## Quick start

### Option A: Flask server (recommended — all features in one command)

```bash
# Install dependencies
pip install flask trimesh numpy scipy numba

# Start the server (serves web/ + API on port 8787)
python3 server.py --port 8787
```

Open `http://localhost:8787`. The server handles everything — static files, mesh simplification, and GPU packing.

### Option B: nginx + systemd (production)

```bash
# 1. Start the backend as a systemd service (auto-starts on boot)
sudo systemctl enable --now packassist

# 2. nginx proxies /api/* to the Flask backend
#    (see /etc/nginx/sites-available/packassist)
```

The backend auto-starts on boot and restarts on crash. The web app is available at your nginx domain (e.g. `packassist.some.local`).

### Option C: XAMPP (Windows)

1. Clone the repository into your XAMPP htdocs directory
2. Open `http://localhost/GitHub/SOME-PackagingAssistant/web/`
3. The Python backend auto-starts via PHP on page load
4. If it doesn't, start manually: `python server.py --port 8787`

### Option D: Python dev server (static only, no API)

```bash
cd web
python -m http.server 5555
```

Then open `http://localhost:5555`. Start the API backend separately: `python3 server.py --port 8787`.

## Backend API

The unified Flask server (`server.py`, port 8787) exposes:

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Web frontend |
| `/api/health` | GET | Server status + GPU info |
| `/api/simplify` | POST | Mesh decimation (PyMeshLab) |
| `/api/pack` | POST | Submit GPU packing job |
| `/api/pack/<id>` | GET | Job status + placement data |
| `/api/pack/<id>/stl` | GET | Download merged STL |
| `/api/pack/<id>/png` | GET | Download preview PNG |
| `/api/jobs` | GET | List recent jobs |

## Caching notice

The web app caches the last result and remembers the current mode/box/packing gap. If you've changed the JavaScript files, add a query string to the script import (e.g., `?v=force_update_42`) or clear the browser cache to ensure the latest code runs.

## GPU-accelerated packers (CLI)

Two GPU packers available in `physics-engine/`:

### SAT packer (fast, convex hulls)

```bash
python3 physics-engine/packer_best.py [stl] [box_l] [box_w] [box_h]
    --method greedy|backtrack
    --beam-width 5
    --hierarchical
    --coarse-step 10 --fine-step 2
    --shrink 0.4
    --compact
    --export-stl
    --seed 42
```

Key options:
- `--beam-width N` — top-K candidates for random selection (1=lowest-Y, 5=explore)
- `--hierarchical` — coarse-to-fine candidate search (43% faster)
- `--shrink F` — hull shrink factor (0.4=aggressive, 1.0=full hull)
- `--compact` — GPU physics settling with 0.8mm/120Hz ground vibration

### Voxel packer (best fill rate, concave-aware)

```bash
python3 physics-engine/packer_gpu_voxel.py [stl] [box_l] [box_w] [box_h]
    --cell 0.5
    --scan-vox 1
    --yaw 8 --roll 4 --pitch 4
    --export-stl
```

Key options:
- `--cell N` — voxel size in mm (0.5=max quality, 1.0=fast)
- `--scan-vox N` — XZ scan step in voxels (1=every voxel, 2=skip 1)

### Benchmark results (6683688 STL, 385×285×150mm)

| Packer | Method | Pieces | Fill | Time |
|---|---|---|---|---|
| SAT GPU | Greedy (beam=1) | 218 | 7.9% | ~60s |
| SAT GPU | Greedy + hierarchical | 213 | 7.7% | ~59s |
| GPU Voxel | 0.5mm cells | **327** | **11.8%** | varies |
| GPU Voxel | 1.0mm cells | ~302 | ~10.9% | faster |

The voxel packer achieves 50% more pieces than SAT because it natively handles concave shapes — no convex hull approximation.

### Architecture

```
packer_best.py (SAT)
├── GPU kernel: batched Y-scanning SAT (all candidates in one launch)
├── pack_greedy(): bottom-deepest + random top-K beam selection
├── pack_backtrack(): remove-last-N, random top-5 reorder, retry
├── hierarchical: coarse-to-fine diverse candidate search
└── compact(): GPU physics settling with high-freq ground vibration

packer_gpu_voxel.py (Voxel)
├── CPU: voxelize each orientation → sparse occupancy + height maps
├── GPU kernel: 3D sparse-voxel collision (bitwise AND-equivalent)
├── Dual-GPU: split candidate scan across 2 GPUs for 2× throughput
└── Placement: lowest-Y greedy, updates box occupancy in-place
```

## Technology

- **Three.js** (WebGL rendering)
- **Rapier.js** (WASM physics)
- **three-mesh-bvh** (BVH acceleration for intersection tests)
- **Flask** (Python backend server)
- **PyMeshLab** (optional, server-side mesh decimation)
- **Numba CUDA** (GPU-accelerated SAT and voxel packing)
- ES Modules (native browser modules, no bundler)
- CSS custom properties with automatic light/dark via `prefers-color-scheme`

## License

Copyright (c) 2025–2026 Oriol Canillas
