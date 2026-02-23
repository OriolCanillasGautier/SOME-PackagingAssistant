# SOME-PackAssist – AI Working Notes

## Project Overview
SOME-PackAssist v0.0.3 is a web-based packing calculator with 3D visualization (Three.js) and physics simulation (Rapier.js). It runs as a static web application served via XAMPP Apache (or any HTTP server).

## Core Layout
```
web/
├── index.html              # Main page
├── css/styles.css          # Styles with light/dark theme
├── api/start-server.php    # Auto-launcher for mesh_server.py
└── js/
    ├── main.js             # Application controller
    ├── packing/calculator.js    # Packing logic (grid + weight optimization)
    ├── mesh/mesh-utils.js       # STL/OBJ loading, volume, stable-base detection
    ├── mesh/mesh-simplifier.js  # Two-tier mesh simplification (server + JS fallback)
    ├── mesh/simplification-modal.js # Interactive simplification UI
    ├── visualization/scene.js   # Three.js scene manager + height-map packing
    ├── physics/physics-world.js # Rapier.js physics engine
    ├── report/report-generator.js # PDF report generator
    └── storage/                 # IndexedDB + server storage
```

## Packing Logic
- `calcularEmpaquetatge` in `calculator.js` is the core function: iterates 6 orientations, returns formatted HTML summary and structured data.
- Weight limiting is applied after calculating raw capacity via `optimizeByWeight()`.
- For STL heightmap mode, grid results are overridden with actual placement count.
- `createSummary()` is exported and called from `main.js` with final count + material weight.
- All dimensions are in **millimeters**, weights in **kg**.

## Physics Engine (Bulk Mode)
- `BulkSimulation` class in `physics-world.js` handles gravity-based simulation.
- Rapier.js WASM engine with gravity = -9810 mm/s².
- Features: vibration system, auto-capacity detection, piece retry on overflow.
- Up to 4 refill cycles with lid-press compaction.
- 20 configurable colors for pieces (`pieceColors` array, limited by `colorCount`).
- Wall thickness = 50mm to prevent pieces escaping.

## 3D Visualization
- `SceneManager` in `scene.js` manages Three.js scene, camera, controls.
- Height-map nesting: `addPackedSTLHeightMapAsync()` — async, abortable, uses InstancedMesh.
- Views: isometric, top, front, right, side, back, left, bottom.
- `setView()` positions camera; `captureView()` in report-generator zooms closer for reports.

## Mesh Simplification
- `MeshSimplifier` tries PyMeshLab server first, falls back to JS `SimplifyModifier`.
- Server auto-started via `web/api/start-server.php` (XAMPP/Apache with PHP).
- `mesh_server.py` listens on port 8787, uses Quadric-Edge-Collapse.

## Report Generation
- `ReportGenerator` in `report-generator.js` creates HTML-based PDF reports.
- 2-page layout: Page 1 = info + isometric view, Page 2 = front/top/side views.
- Includes estimated material weight when configured.
- Supports Catalan and English translations.
- Preview modal before download.

## UI Flow
- Mode selector switches between "optimized" (math calculation) and "bulk" (physics simulation).
- Input panels for object dimensions, box dimensions, bulk options.
- Material selector for estimated weight (aluminium, steel, plastic, copper, custom).
- Progress bar with phase labels + cancel button during calculation.
- Report button opens preview modal with language selection.

## Deployment
- **XAMPP**: Apache serves `web/` at `http://localhost/GitHub/SOME-PackagingAssistant/web/`. PHP auto-starts `mesh_server.py`.
- **Development**: `python -m http.server 5555` from `web/` directory (mesh_server separate).

## Conventions
- UI copy is **Catalan**; match language and emoji headers when extending.
- All dimensions in mm, weights in kg.
- Use ES Modules with CDN imports (Three.js, Rapier.js).
- CSS uses custom properties with automatic dark mode via `prefers-color-scheme`.
- Version: 0.0.4, App name: SOME-PackAssist

## Development Workflow
- Maintain `TODO.md` with pending tasks, linked to file locations.
- Use `implementation.md` to document technical decisions and changes.
- Update `README.md` whenever modifying features, deployment steps, or project structure.
- Keep all three files in sync with code changes.