# Development & Testing

This document covers how to run and test all components.

## Web App

```bash
# Option 1: Via XAMPP (Windows)
# Place the project in C:\xampp\htdocs\GitHub\SOME-PackagingAssistant\
# Then open: http://localhost/GitHub/SOME-PackagingAssistant/web/

# Option 2: Python dev server (any OS)
cd web
python -m http.server 5555
# Open: http://localhost:5555

# Option 3: PHP built-in server
php -S localhost:8080 -t web/
```

## Physics Engine (C# / .NET)

Interactive 3D visual packer with custom SAT collision detection and OpenGL rendering.

### Prerequisites
- .NET 6 SDK or later
- GPU with OpenGL 3.3 support

### Setup & Run

```bash
cd physics-engine/PhysicsEngine

# Restore NuGet packages
dotnet restore

# Run with a specific STL file
dotnet run -- "../stl/yourfile.stl" 385 285 150 5

# Arguments: [stl_path] [box_l] [box_w] [box_h] [scan_step_mm]
# scan_step_mm: lower = finer scan = slower but more precise (default 5)
```

### Controls
| Key / Action | What it does |
|---|---|
| **N** | Place next piece (best-found position) |
| **Space** | Toggle auto-placement |
| **R** | Reset (clear all pieces) |
| **Left mouse drag** | Orbit camera |
| **Scroll wheel** | Zoom |

### How it works
1. Loads STL, generates 8 yaw orientations (0°, 45°, 90°, ..., 315°)
2. For each piece: scans all XZ positions at `scan_step_mm` resolution, tries each orientation, binary-searches for lowest Y where SAT collision test passes
3. Places piece at globally best (lowest Y) position
4. On completion, runs pairwise collision check on all placed pieces and prints overlaps

---

## GPU Packer (Python + Numba CUDA)

CUDA-accelerated batch packer. Uses GPU for parallel SAT collision testing.

### Prerequisites
- NVIDIA GPU with CUDA 11+ (Quadro, GeForce, etc.)
- Python 3.9+

### Setup

```bash
# Install dependencies
pip install numba trimesh scipy numpy matplotlib

# Verify CUDA is available
python -c "from numba import cuda; print(cuda.is_available(), cuda.get_current_device().name)"
```

### Run

```bash
cd physics-engine

# Basic usage
python packer_gpu.py "stl/yourfile.stl" 385 285 150 5

# Full argument list
python packer_gpu.py [stl_path] [box_l] [box_w] [box_h] [scan_mm] --yaw 8 --yres 2.0 --output result.png
```

| Argument | Default | Description |
|---|---|---|
| `stl_path` | *(required)* | Path to STL file |
| `box_l` | 385 | Box length X (mm) |
| `box_w` | 285 | Box width Z (mm) |
| `box_h` | 150 | Box height Y (mm) |
| `scan_mm` | 5 | XZ scan step (mm) |
| `--yaw` | 8 | Number of yaw orientations |
| `--yres` | 2 | Y scan resolution (mm) |
| `--output` | packed_gpu.png | Output visualization |

### How it works
1. **CPU**: Loads STL, generates yaw orientations, precomputes face normals
2. **GPU**: Launches thousands of threads — each tests one candidate (x, z, orientation). Each thread does SAT collision against all placed pieces, scans Y upward, finds first valid Y
3. **CPU verification**: Best GPU candidate is verified with trimesh `closest_point` (ground truth) before placement
4. Output: `packed_gpu.png` (4-view visualization) + console log with piece count and overlaps

### Performance notes
- On a Quadro P2200 (1280 cores): ~10-100x faster than CPU
- 5mm scan step with 8 orientations in a 385x285x150 box: ~20K candidates per piece
- Each candidate tests against all placed pieces (O(n*m) SAT tests)
- Total time scales roughly linearly with scan resolution

---

## Testing the algorithms

### Quick validation (right triangle)
```bash
# Should achieve ~350 pieces in 200x200x150 box (AABB optimal)
python packer_gpu.py --yaw 4 200 200 150 5
```

### Real part (thin bracket)
```bash
# Target: 320-350 pieces in 385x285x150 box
python packer_gpu.py "stl/part.stl" 385 285 150 5
```

### Interpreting results
- **Fill %**: Volume of placed pieces / box volume. The maximum is the piece's AABB fill ratio (6.1% for part)
- **Overlaps**: If the verification step reports collisions, the GPU SAT approximations missed them (try reducing `--yres`)
- **Performance**: If too slow, increase `scan_mm` to 10 or 15 for faster (but less dense) results
