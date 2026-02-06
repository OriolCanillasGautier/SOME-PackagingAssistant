# SOME-PackAssist

Version 0.0.2

SOME-PackAssist is a static web application that estimates how many parts fit in a box, with an interactive 3D preview (Three.js) and an optional physics-based bulk simulation (Rapier.js).

The application runs directly in the browser (ES Modules + CDN imports). No build step is required.

## Features

Optimized mode
- Mathematical capacity calculation (box and part dimensions)
- Optional rotation (multiple orientations)
- Weight limit and safety factor
- STL support for 3D preview and optimized placement visualization

Bulk mode
- Physics-based simulation with gravity (Rapier.js)
- Supports complex STL meshes
- Automatic capacity detection (bulk fill)
- Vibration settling and configurable drop parameters

PDF report
- Report generation with multiple views (isometric, front, top, side)
- Preview before download
- Catalan and English layouts

## Units

- Dimensions: millimeters (mm)
- Weight: kilograms (kg)
- STL files are assumed to be authored in mm

## Project structure

```
SOME-PackagingAssistant/
├── web/
│   ├── index.html
│   ├── historial.html
│   ├── css/
│   ├── js/
│   │   ├── main.js
│   │   ├── packing/
│   │   ├── mesh/
│   │   ├── visualization/
│   │   ├── physics/
│   │   ├── report/
│   │   └── storage/
│   └── library/
└── .github/
    └── copilot-instructions.md
```

## Quick start (local)

From the repository root:

```bash
cd web
python3 -m http.server 5555
```

Then open:

http://localhost:5555

Alternative (Node.js):

```bash
npx serve -l 5555 web
```

## Deployment notes (Nginx)

The production setup is a standard static site served by Nginx on port 5555, with `web/` as the document root.

## Technology

- Three.js (WebGL)
- Rapier.js (WASM physics)
- ES Modules (native browser modules)
- CSS custom properties with automatic light/dark via `prefers-color-scheme`

## License

Copyright (c) 2025 Oriol Canillas

