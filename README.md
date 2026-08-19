# SOME-PackAssist

Version 0.0.5

SOME-PackAssist is a web-based packing calculator with 3D visualization (Three.js), physics simulation (Rapier.js), and GPU-accelerated packing. It estimates how many parts fit in a box and renders the result interactively.

The frontend runs directly in the browser (ES Modules + CDN imports). The Python backend (Flask) serves the static files, runs mesh simplification, and executes GPU packing jobs asynchronously.

## Web modes

| Mode | Description |
|---|---|
| **Optimized** | Heightmap BVH nesting for irregular shapes (async, cancelable) |
| **Fast Optimizer** | BVH-validated compressed grid, brick-pattern support, instant results |
| **Bulk** | Physics simulation with gravity (Rapier.js WASM), refill cycles, vibration |
| **GPU** | CUDA backend via server — **Sparrow** (fast GPU voxel kernel, default) or **Voxel** (max-precision dense scan) |

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

### GPU mode
- Sparrow backend (default): CUDA sparse-voxel kernel from `packer_best.py` — fast, recommended for the web
- Voxel backend: `packer_gpu_voxel.py` at 0.5–2.0mm resolution for maximum fill rate
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

## Backend

The project uses a single unified Flask server (`server.py`, port 8787) that serves both the web frontend and the API.

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Web frontend |
| `/api/health` | GET | Server status + GPU info |
| `/api/simplify` | POST | Mesh decimation (PyMeshLab) |
| `/api/pack` | POST | Submit GPU packing job (adaptive resolution + ETA) |
| `/api/pack/<id>` | GET | Job status + placement data |
| `/api/pack/<id>/stl` | GET | Download merged STL |
| `/api/pack/<id>/png` | GET | Download preview PNG |
| `/api/jobs` | GET | List recent jobs |

Deployment options:
- **systemd service** (`packassist.service`) — auto-starts on boot, restarts on crash
- **nginx reverse proxy** (`sites-available/packassist`) — proxies `/api/*` to `127.0.0.1:8787`, serves static files, 10-min proxy timeouts

## GPU-accelerated packers (CLI)

Two GPU packers available in `physics-engine/`:

### Sparrow GPU kernel (`packer_best.py`)

```bash
python3 physics-engine/packer_best.py [stl] [box_l] [box_w] [box_h]
    --method sparrow          # GPU voxel kernel (default for web)
    --method greedy|backtrack # SAT-based fallback methods
    --voxel-cell 1.5          # voxel size for sparrow collision grid (mm)
    --yaw 8 --yres 2.0
    --shrink 0.4
    --sparrow-workers 1
    --export-stl
    --seed 42
```

- `--method sparrow` — batched GPU sparse-voxel Y-scanning; natively handles concave nesting. On a 385×285×150mm box it packs **296 pieces at 10.7% fill in ~57s**; on a 160³mm box it packs **62 pieces in ~2.8s**.
- `--method greedy` / `--method backtrack` — SAT packer with beam search, hierarchical coarse-to-fine scan, and hull-shrink compaction.

### Voxel packer (`packer_gpu_voxel.py`)

```bash
python3 physics-engine/packer_gpu_voxel.py [stl] [box_l] [box_w] [box_h]
    --cell 0.5        # voxel size in mm (0.5=max quality, 1.0=fast)
    --scan-vox 1      # XZ scan step in voxels (1=every voxel, 2=skip 1)
    --yaw 8 --roll 4 --pitch 4
    --export-stl
```

- Best fill rate — 273–327 pieces at 11.8% fill with 0.5mm cells.
- Dual-GPU support: splits candidate scan across 2 GPUs for 2× throughput.

### Adaptive resolution (web `/api/pack`)

The server scales job parameters automatically to keep responses practical:
- **`scan_vox` auto-scaling** — increases XZ scan step (1→2→4→8) until the estimated time fits
- **Cell auto-adjust** — if still too slow, bumps the voxel cell (up to 4.0mm) and reports `cell_adjusted_from`
- **Live ETA** — model-based estimate returned at submit (`estimated_time`) and shown in the UI
- **10-minute watchdog** — any job still queued/running after 600s is marked as errored so the frontend stops polling

## Benchmark results

All benchmark numbers were measured with a single **undisclosed reference
part** (irregular concave shape, ~28×37×97mm) — no part name or STL is
published. Different parts give different counts/fills/times.

| Packer | Method | Box (mm) | Pieces | Fill | Time |
|---|---|---|---|---|---|
| Sparrow GPU | `--method sparrow` (voxel cell 1.5mm) | 385×285×150 | **296** | **10.7%** | ~57s |
| Sparrow GPU | `--method sparrow` | 160³ | 62 | — | ~2.8s |
| GPU Voxel | 0.5mm cells | 385×285×150 | 273–327 | 11.8% | slowest |
| SAT GPU | Greedy (beam=1) | 385×285×150 | 218 | 7.9% | ~60s |
| SAT GPU | Greedy + hierarchical | 385×285×150 | 213 | 7.7% | ~59s |

The voxel-based methods (Sparrow / GPU Voxel) pack ~50% more pieces than SAT because they natively handle concave shapes — no convex hull approximation.

### Architecture

```
packer_best.py (SAT)
├── GPU kernel: batched Y-scanning SAT (all candidates in one launch)
├── pack_greedy(): bottom-deepest + random top-K beam selection
├── pack_backtrack(): remove-last-N, random top-5 reorder, retry
├── pack_sparrow(): batched GPU sparse-voxel Y-scanning (concave-aware)
├── hierarchical: coarse-to-fine diverse candidate search
└── compact(): GPU physics settling with high-freq ground vibration

packer_gpu_voxel.py (Voxel)
├── CPU: voxelize each orientation → sparse occupancy + height maps
├── GPU kernel: 3D sparse-voxel collision (bitwise AND-equivalent)
├── Dual-GPU: split candidate scan across 2 GPUs for 2× throughput
└── Placement: lowest-Y greedy, updates box occupancy in-place
```

## Credits

The canonical references are the list below (tracked in this README). Full
paper PDFs live in `research/` locally — that folder is git-ignored (large
binaries), but if this project helped you, please credit the original
authors.

- **JonasTollenaere** (KU Leuven) — the separation + compression strategy in `sparrow-3d` (and MeshCore) inspired the Sparrow GPU packing algorithm in this project (`sparrow-3d` is LGPL-3.0; the Python implementation here is original work that draws on the published approach).
- **Cui, Rong, Chen & Matusik (SIGGRAPH 2023)** — *Dense, Interlocking-Free and Scalable Spectral Packing of Generic 3D Objects* — basis of the spectral packing method.
- **Schwarz & Seidel (SIGGRAPH Asia 2010)** — *Fast Parallel Surface and Solid Voxelization on GPUs* — basis of the GPU voxelization kernel.
- **Gardeyn et al. (2025)** — *An open-source heuristic to reboot 2D nesting research* — the original `sparrow` 2D nesting algorithm.

## Project structure

```
SOME-PackagingAssistant/
├── server.py                   # Unified Flask backend (API + static files, port 8787)
├── web/
│   ├── index.html              # Main application
│   ├── admin.html              # Admin tools (benchmark + orientation tester)
│   ├── benchmark.html          # Benchmark runner
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
│   ├── locales/                # i18n (ca, en)
│   └── library/                # User STL library (generated, gitignored)
├── output/                     # Timestamped packing results (gitignored)
│   └── YYYY-MM-DD_HHMMSS_<method>/
│       ├── info.txt            # Run metadata (box, method, params, result)
│       ├── packed_2d.png
│       ├── packed_3d.png
│       └── packed_layers.png
├── physics-engine/             # GPU/CPU packing engines
│   ├── packer_best.py          # CUDA SAT + Sparrow voxel packer
│   ├── packer_gpu_voxel.py     # CUDA sparse-voxel packer (best fill rate)
│   ├── packer_gpu.py           # Base CUDA SAT packer
│   ├── packer_cpu.py           # CPU brute-force packer
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
├── pdf_generator.py            # Server-side PDF generation (standalone)
├── test/                       # Endpoint + benchmark test scripts
├── env/                        # Python virtual environment
├── implementation.md           # Implementation plan
└── TODO.md                     # Feature backlog
```

## Output directory

Each packing run (web or CLI) is written to a timestamped folder under `output/`:

```
output/2026-08-12_153507_sparrow/
├── info.txt            # box, method, parameters, piece count, fill %, time
├── packed_2d.png       # top-down occupancy preview
├── packed_3d.png       # isometric render of the packed box
└── packed_layers.png   # layer-by-layer breakdown
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

## Caching notice

The web app caches the last result and remembers the current mode/box/packing gap. If you've changed the JavaScript files, add a query string to the script import (e.g., `?v=force_update_42`) or clear the browser cache to ensure the latest code runs.

## Technology

- **Three.js** (WebGL rendering)
- **Rapier.js** (WASM physics)
- **three-mesh-bvh** (BVH acceleration for intersection tests)
- **Flask** (Python backend server)
- **PyMeshLab** (optional, server-side mesh decimation)
- **Numba CUDA** (GPU-accelerated SAT, Sparrow, and voxel packing)
- ES Modules (native browser modules, no bundler)
- CSS custom properties with automatic light/dark via `prefers-color-scheme`

## License

Copyright (c) 2025–2026 Oriol Canillas
