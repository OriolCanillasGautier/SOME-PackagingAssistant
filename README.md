# SOME-PackagingAssistant (Gradio UI)

Single-file Gradio app that replicates the Excel-based packing calculator with inline 3D preview and optional PyVista viewer.

## Features
- Exact "Excel" style packing: origin at (0,0,0), base at Z=0, axis-aligned grid.
- Safety slider applies a reduction factor to the **final unit count** (50–100%) and now has an explicit "Permet girar" toggle to lock orientation when needed.
- Optional STL upload (trimesh) that auto-fills the object dimensions and feeds the Plotly/PyVista previews.
- Plotly inline viewer can spawn a fullscreen tab and lets you tune how many STL instances are rendered (default 200) for heavier meshes.
- Inline Plotly scene plus an optional external PyVista/Qt viewer (when available).
- Shared packing core (`packing_core.py`) keeps the Gradio UI and legacy script in sync, avoiding drift.

## Quickstart (Windows, PowerShell)

```pwsh
# From repo root
py -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Run the app
.\.venv\Scripts\python.exe .\app.py
```

## One-click on Windows (.bat)

Double‑click `run_gradio.bat`. It will:
- create `.venv` if missing,
- upgrade pip and install dependencies from `requirements.txt`,
- launch `app.py` with that environment.

## CI package (GitHub Actions)
Every push to the `Gradio` branch publishes an artifact named `packassist-gradio-windows-runner` that bundles `app.py`, `README.md`, `requirements.txt`, and `run_gradio.bat`.

When the app starts it prints a local Gradio URL (usually http://127.0.0.1:7860). Open it in your browser.

## Usage notes
- Units are millimeters everywhere (STL files are assumed to be mm as well).
- Safety percent reduces the final recommended unit count; it no longer shrinks box dimensions silently.
- Orientation search tries all 6 permutations only when "Permet girar" is enabled.
- Use the "Límit de peces STL visibles" slider to cap how many STL copies are drawn in Plotly (useful for dense layouts); the fullscreen link opens the same figure in a dedicated browser tab.
- Weight limits remain enforced: if total weight exceeds the box limit the result is capped accordingly.
- Plotly is optional; if it is missing you still get the textual summary. PyVista/PyVistaQt are only needed for the external viewer button.

## Limitations
- Packing remains grid/axis-aligned; irregular shapes are approximated by their oriented bounding box.
- STL rendering in Plotly is limited to the first ~20 instances for performance reasons (PyVista button is better for dense previews).

## Troubleshooting
- If dependencies are missing, re-run: `python -m pip install -r requirements.txt` inside the virtual environment.
- STL issues are almost always invalid meshes; ensure the file is manifold and exported in millimeters.
- To enable the external viewer install `pyvista`, `pyvistaqt`, and `vtk` in the same environment.

## Project layout
- `app.py` — Gradio application + Plotly inline preview + viewer launcher.
- `formula_excel.py` — Legacy UI kept for reference.
- `interactive_viewer.py` — PyVista/Qt standalone viewer used by `app.py` when the button is pressed.
- `packing_core.py` — Shared packing logic (Decimal precision, summaries, weight heuristics).
- `mesh_utils.py` — STL helpers, trimesh OBB alignment, and upload processors.
- `requirements.txt` — Dependency list for the Gradio app and viewer.

