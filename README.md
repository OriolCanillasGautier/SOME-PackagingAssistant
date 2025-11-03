# SOME-PackagingAssistant (Gradio-only)

Single-file Gradio app that performs exact, axis-aligned carton/box packing. Interactive 3D viewer is intentionally excluded.

## Features
- Exact "Excel" style packing: origin at (0,0,0), base at Z=0, axis-aligned grid.
- Safety percent in the Box section: scales the usable box dimensions (50–100%).
- Optional STL upload to auto-detect item dimensions via oriented bounding box (trimesh).
- Quantity and optional weight limit (max box weight).
- Concise summary table with best orientation, counts per axis, total placed, and fill%.

## Quickstart (Windows, PowerShell)

```pwsh
# From repo root
py -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\gradio\requirements.txt

# Run the app
.\.venv\Scripts\python.exe .\app.py
```

## One-click on Windows (.bat)

If you prefer not to type commands, double‑click `scripts/run_windows.bat`. It will:
- create `.venv` if missing,
- upgrade pip and install dependencies from `gradio/requirements.txt`,
- and start the app with that environment.

## CI package (GitHub Actions)
This branch includes a workflow that packages a simple “runner” ZIP with:
- `app.py`, `README.md`, `requirements.txt` (copied from `gradio/requirements.txt`), and `scripts/run_windows.bat`.

Every push to the `Gradio` branch uploads an artifact named `packassist-gradio-windows-runner` you can download from the workflow run.

The app will print a local Gradio URL (usually http://127.0.0.1:7860). Open it in your browser.

## Usage notes
- Units are millimeters. STL units are assumed to be millimeters.
- Safety percent reduces the available internal dimensions uniformly: usable_dim = box_dim * (safety/100).
- Orientation search tries all 6 permutations of the item dimensions and picks the one with the highest capacity.
- If both weight per item and max box weight are provided, the final placed count is capped by weight.

## Limitations
- No external interactive 3D viewer. If you later want a 3D view, we can add a separate lightweight preview or integrate PyVista screenshots.
- No complex heuristics beyond grid packing; irregular shapes are approximated by their oriented bounding box for placement.

## Troubleshooting
- If the app fails to start due to missing packages, re-run the install step:
  ```pwsh
  .\.venv\Scripts\python.exe -m pip install -r .\gradio\requirements.txt
  ```
- If STL fails to load, ensure the file is valid and `trimesh` is installed (it is included in `gradio/requirements.txt`).

## Project layout
- `app.py` — Single-file Gradio application with packing logic and UI.
- `gradio/requirements.txt` — Dependency list used for the app.
- `gradio/interactive_viewer.py` — Not used in this Gradio-only mode.

