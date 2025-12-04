# SOME-PackAssist – AI Working Notes

## Project Overview
SOME-PackAssist v0.0.2 is a web-based packing calculator with 3D visualization (Three.js) and physics simulation (Rapier.js). It runs as a static web application served via Nginx on Ubuntu (port 5555).

## Core Layout
```
web/
├── index.html              # Main page
├── css/styles.css          # Styles with light/dark theme
└── js/
    ├── main.js             # Application controller
    ├── packing/calculator.js    # Packing logic (Decimal precision)
    ├── mesh/mesh-utils.js       # STL utilities
    ├── visualization/scene.js   # Three.js scene manager
    ├── physics/physics-world.js # Rapier.js physics engine
    └── report/report-generator.js # PDF report generator
```

## Packing Logic
- `calcularEmpaquetatge` in `calculator.js` is the core function: iterates 6 orientations, returns formatted Markdown and structured data.
- Weight limiting and safety factor are applied after calculating raw capacity.
- All dimensions are in **millimeters**, weights in **kg**.

## Physics Engine (Bulk Mode)
- `BulkSimulation` class in `physics-world.js` handles gravity-based simulation.
- Rapier.js WASM engine with gravity = -9810 mm/s².
- Features: vibration system (5s), auto-capacity detection, piece retry on overflow.
- 20 configurable colors for pieces (`pieceColors` array, limited by `colorCount`).
- Wall thickness = 50mm to prevent pieces escaping.

## 3D Visualization
- `SceneManager` in `scene.js` manages Three.js scene, camera, controls.
- Views: isometric, top, front, right, side, back, left, bottom.
- `setView()` positions camera; `captureView()` in report-generator zooms closer for reports.

## Report Generation
- `ReportGenerator` in `report-generator.js` creates HTML-based PDF reports.
- 2-page layout: Page 1 = info + isometric view, Page 2 = front/top/side views.
- Supports Catalan and English translations.
- Preview modal before download.

## UI Flow
- Mode selector switches between "optimized" (math calculation) and "bulk" (physics simulation).
- Input panels for object dimensions, box dimensions, bulk options.
- Report button opens preview modal with language selection.

## Deployment
- **Production**: Nginx on Ubuntu, port 5555, static file serving from `/var/www/packassist`.
- **Development**: `python3 -m http.server 5555` from `web/` directory.

## Conventions
- UI copy is **Catalan**; match language and emoji headers when extending.
- All dimensions in mm, weights in kg.
- Use ES Modules with CDN imports (Three.js, Rapier.js).
- CSS uses custom properties with automatic dark mode via `prefers-color-scheme`.
- Version: 0.0.2, App name: SOME-PackAssist
