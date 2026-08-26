#!/usr/bin/env python3
"""
PackAssist — Unified Backend Server
====================================
Flask server combining mesh simplification (PyMeshLab) + GPU voxel packing (CUDA).

Run:  python server.py [--host 0.0.0.0] [--port 8787]

Endpoints:
    GET  /api/health            — server status + GPU info
    POST /api/simplify           — mesh decimation (PyMeshLab)
    POST /api/pack               — submit GPU packing job
    GET  /api/pack/<job_id>      — job status + placement data
    GET  /api/pack/<job_id>/stl  — download merged STL
    GET  /api/pack/<job_id>/png  — download preview PNG
    GET  /api/jobs               — list recent jobs
"""
import sys, os, io, time, uuid, json, threading, tempfile, traceback, itertools
from contextlib import nullcontext
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file, send_from_directory

# ——————————————————————————————————————————————————————————————————————
# Dependency checks
# ——————————————————————————————————————————————————————————————————————
try:
    import pymeshlab
    HAS_PYMESHLAB = True
except ImportError:
    HAS_PYMESHLAB = False
    print("[server] WARNING: pymeshlab not installed (simplify disabled)")

try:
    from numba import cuda
    HAS_CUDA = cuda.is_available()
    if HAS_CUDA:
        sys.path.insert(0, str(Path(__file__).parent / "physics-engine"))
        from packer_gpu_voxel import generate_orientations, pack, verify
except Exception as e:
    HAS_CUDA = False
    print(f"[server] WARNING: CUDA/GPU packer not available: {e}")

# BestPacker doesn't need CUDA — available unconditionally
sys.path.insert(0, str(Path(__file__).parent / "physics-engine"))
from packer_best import BestPacker

import trimesh
import numpy as np

app = Flask(__name__, static_folder=str(Path(__file__).parent / "web"), static_url_path="")
RESULT_DIR = Path(__file__).parent / "output" / "_api_results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

# CORS — allow frontend from any origin to call the API
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    # The versioned JS/CSS query string is only bumped manually — a stale
    # index.html still points at the OLD main.js, and that's exactly why a
    # laptop (different browser profile / cache) kept showing the old frontend
    # while the server machine (already re-fetched) was fine. Force the
    # browser to revalidate every static asset so it always picks up the
    # current files; a hard refresh once clears the already-cached copy.
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

# Serve the web frontend at /
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
# GPU methods (sparrow/voxel/spectral) run on the GPU, so concurrency is capped
# to avoid exhausting GPU memory/contexts — but a couple can run at once. CPU
# methods (grid/stacking/compartment/multitray) need NO lock and run in parallel.
GPU_SEM = threading.Semaphore(2)

# Methods that drive the GPU (packer_gpu_voxel / Sparrow). Everything else is
# CPU (packer_best) and can run concurrently without touching the GPU.
GPU_METHODS = frozenset({"sparrow", "voxel", "spectral"})

# ——————————————————————————————————————————————————————————————————————
# Mesh simplification (ported from mesh_server.py)
# ——————————————————————————————————————————————————————————————————————

def _meshopt_decimate(mesh, target_ratio):
    """Fastest decimator available: meshoptimizer (the game-engine quadric,
    C++, via a tiny compiled .so + ctypes). ~6x faster than VTK and ~12x
    faster than pymeshlab on 150k-triangle meshes; handles thin-walled
    hollow parts. Same shape, less resolution."""
    import ctypes
    so = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "physics-engine", "meshopt", "decimator.so")
    lib = ctypes.CDLL(so)
    F = ctypes.POINTER(ctypes.c_float)
    U = ctypes.POINTER(ctypes.c_uint32)
    lib.mo_simplify.argtypes = [F, U, F, ctypes.c_int, U, ctypes.c_int,
                                ctypes.c_float, ctypes.c_float]
    lib.mo_simplify.restype = ctypes.c_int

    v = np.ascontiguousarray(mesh.vertices, dtype=np.float32)
    f = np.ascontiguousarray(mesh.faces, dtype=np.uint32)
    v_out = np.zeros(v.shape, dtype=np.float32)
    f_out = np.zeros(f.size, dtype=np.uint32)
    n = lib.mo_simplify(v_out.ctypes.data_as(F), f_out.ctypes.data_as(U),
                        v.ctypes.data_as(F), len(v),
                        f.ctypes.data_as(U), len(f),
                        max(0.01, min(1.0, target_ratio)), 0.01)
    return trimesh.Trimesh(vertices=v_out, faces=f_out[:n].reshape(-1, 3))


def _fast_volume(verts, faces):
    """Signed volume via the numpy cross/dot — much faster than trimesh's."""
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    return float(np.einsum('ij,ij->i', v0, np.cross(v1, v2)).sum() / 6.0)


def _fast_watertight(faces):
    """True iff every undirected edge appears exactly twice (numpy)."""
    e = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]],
                                faces[:, [0, 2]]]), axis=1)
    _, counts = np.unique(e, axis=0, return_counts=True)
    return bool((counts == 2).all())


def _fast_winding_consistent(faces):
    """True iff every oriented edge appears once in each direction."""
    # triangle (v0,v1,v2) has directed edges v0->v1, v1->v2, v2->v0
    e = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]],
                        faces[:, [2, 0]]], axis=0)
    # canonical key = sorted pair; sign = +1 if the direction matches the
    # sorted order, -1 otherwise. Consistent winding => every key sums to 0.
    lo = np.minimum(e[:, 0], e[:, 1])
    hi = np.maximum(e[:, 0], e[:, 1])
    sign = np.where(e[:, 0] < e[:, 1], 1, -1)
    # Compact (lo, hi) pairs to dense IDs BEFORE bincount: the naive
    # lo*1e6+hi key overflows memory for meshes with >~20k vertices
    # (bincount allocates max_key+1 entries -> hundreds of GB).
    _, inv = np.unique(np.stack([lo, hi], axis=1), axis=0, return_inverse=True)
    sums = np.bincount(inv, weights=sign.astype(np.float64))
    return bool(np.all(np.abs(sums) < 0.5))


def _pm_repair(ms, names):
    """Run pymeshlab repair filters defensively: try the typed method then
    the apply_filter fallback. These repairs fix bad topology (non-manifold
    edges, degenerate/duplicate faces) so the decimation cannot tear thin
    walls — they do NOT change the overall shape and do NOT fill holes."""
    for name in names:
        try:
            getattr(ms, name)()
            continue
        except Exception:
            pass
        try:
            ms.apply_filter(name)
        except Exception:
            pass


def _vtk_decimate(mesh, target_ratio):
    """Fast C++ decimation via VTK's vtkDecimatePro (quadric edge collapse).
    ~2.5x faster than the pymeshlab quadric on 150k+ triangle meshes AND it
    handles thin-walled hollow parts (tubes) that the other fast C++
    decimator (fast-simplification) refuses to collapse. Same shape, less
    resolution; the winding is normalized afterwards by trimesh."""
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, vtk_to_numpy

    verts = mesh.vertices
    faces = mesh.faces
    pv = vtk.vtkPoints()
    pv.SetData(numpy_to_vtk(np.ascontiguousarray(verts, dtype=np.float64), deep=True))
    n = len(faces)
    legacy = np.empty(n * 4, dtype=np.int64)
    legacy[0::4] = 3
    legacy[1::4] = faces[:, 0]
    legacy[2::4] = faces[:, 1]
    legacy[3::4] = faces[:, 2]
    ca = vtk.vtkCellArray()
    ca.SetCells(n, numpy_to_vtk(legacy, deep=True, array_type=vtk.VTK_ID_TYPE))
    pd = vtk.vtkPolyData()
    pd.SetPoints(pv)
    pd.SetPolys(ca)

    target_faces = max(12, int(n * target_ratio))
    dec = vtk.vtkDecimatePro()
    dec.SetInputData(pd)
    dec.SetTargetReduction(1.0 - target_faces / n)
    dec.PreserveTopologyOn()
    dec.SplitErrorOn() if hasattr(dec, 'SplitErrorOn') else None
    dec.Update()

    out = dec.GetOutput()
    v = vtk_to_numpy(out.GetPoints().GetData())
    arr = vtk_to_numpy(out.GetPolys().GetData())
    # legacy cell format: [3, i0, i1, i2, ...]
    f2 = arr.reshape(-1, 4)[:, 1:].astype(np.int64)
    return trimesh.Trimesh(vertices=v, faces=f2)


def simplify_stl(input_bytes: bytes, target_ratio: float,
                 preserve_features: bool = True,
                 create_envelope: bool = False) -> bytes:
    tmp_out = tmp_in = None
    try:
        # ── Fast path: VTK (C++ quadric) — ~2.5x faster than pymeshlab and
        # handles thin-walled hollow parts. The input is pre-cleaned with
        # trimesh (duplicate-vertex merge only — no shape change), and the
        # output winding is normalized afterwards.
        if target_ratio < 0.999:
            try:
                mesh = trimesh.load(io.BytesIO(input_bytes), file_type="stl",
                                    force="mesh")
                if isinstance(mesh, trimesh.Scene):
                    geoms = [g for g in mesh.geometry.values()
                             if isinstance(g, trimesh.Trimesh)]
                    mesh = trimesh.util.concatenate(geoms) if len(geoms) > 1 else geoms[0]
                in_vol = _fast_volume(mesh.vertices, mesh.faces)
                in_wt = _fast_watertight(mesh.faces)
                out = _meshopt_decimate(mesh, target_ratio)
                # Validate the result (numpy fast checks): a garbage
                # decimation shows up as a large signed-volume change.
                # Only require watertight output if the input was watertight.
                if in_wt and not _fast_watertight(out.faces):
                    raise RuntimeError("meshopt: watertight input produced torn output")
                out_vol = _fast_volume(out.vertices, out.faces)
                if in_vol > 0 and abs(out_vol / in_vol - 1.0) > 0.05:
                    raise RuntimeError("meshopt: volume drift")
                if create_envelope:
                    try:
                        out = out.convex_hull
                    except Exception:
                        pass
                # meshoptimizer preserves the winding — no fix_normals needed.
                return out.export(file_type="stl")
            except Exception:
                pass   # fall through to the VTK path

        # ── VTK fast path (C++ quadric) — the validation above also guards
        # this one.
        if target_ratio < 0.999:
            try:
                mesh = trimesh.load(io.BytesIO(input_bytes), file_type="stl",
                                    force="mesh")
                if isinstance(mesh, trimesh.Scene):
                    geoms = [g for g in mesh.geometry.values()
                             if isinstance(g, trimesh.Trimesh)]
                    mesh = trimesh.util.concatenate(geoms) if len(geoms) > 1 else geoms[0]
                in_vol = _fast_volume(mesh.vertices, mesh.faces)
                in_wt = _fast_watertight(mesh.faces)
                out = _vtk_decimate(mesh, max(0.01, min(1.0, target_ratio)))
                if in_wt and not _fast_watertight(out.faces):
                    raise RuntimeError("vtk: watertight input produced torn output")
                out_vol = _fast_volume(out.vertices, out.faces)
                if in_vol > 0 and abs(out_vol / in_vol - 1.0) > 0.05:
                    raise RuntimeError("vtk: volume drift")
                if create_envelope:
                    try:
                        out = out.convex_hull
                    except Exception:
                        pass
                if not _fast_winding_consistent(out.faces):
                    out.fix_normals()
                return out.export(file_type="stl")
            except Exception:
                pass   # fall through to the pymeshlab path

        if not HAS_PYMESHLAB:
            raise RuntimeError("pymeshlab is not installed")

        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
            f.write(input_bytes)
            tmp_in = f.name

        tmp_out = tmp_in + "_simplified.stl"
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(tmp_in)

        # Repair the input FIRST: real-world STLs (scans) carry duplicated or
        # non-manifold geometry; the quadric collapse then deletes triangles
        # around the bad spots — exactly the "holes in the tube walls" the
        # user saw. Only NON-removing repairs are used (duplicate removal is
        # exact; the non-manifold EDGES repair deletes faces and changes the
        # shape — banned).
        _pm_repair(ms, [
            'meshing_remove_duplicate_vertices',
            'meshing_remove_duplicate_faces',
            'meshing_repair_non_manifold_vertices',
        ])

        original_faces = ms.current_mesh().face_number()
        target_faces = max(12, int(original_faces * target_ratio))

        try:
            ms.meshing_decimation_quadric_edge_collapse(
                targetfacenum=target_faces, preservenormal=preserve_features,
                preservetopology=True, optimalplacement=True, qualitythr=0.5)
        except Exception:
            try:
                ms.apply_filter('simplification_quadric_edge_collapse_decimation',
                                targetfacenum=target_faces, preservenormal=preserve_features,
                                preservetopology=True, optimalplacement=True, qualitythr=0.5)
            except Exception:
                ms.meshing_decimation_clustering(
                    threshold=pymeshlab.AbsoluteValue(
                        ms.current_mesh().bounding_box().diagonal() * 0.01))

        # Post-decimation: no face-removing repairs (they change the shape).
        # The winding fix happens via trimesh fix_normals below.

        # "Create convex envelope (close holes)": replace the result with
        # its convex hull — the packing then treats the piece as its
        # envelope (fast + safe, no concavities to catch).
        if create_envelope:
            try:
                ms.meshing_convex_hull()
            except Exception:
                try:
                    ms.apply_filter('meshing_convex_hull')
                except Exception:
                    pass

        ms.save_current_mesh(tmp_out)
        with open(tmp_out, "rb") as f:
            out_bytes = f.read()

        # Consistent winding: the STL round-trip can leave inverted faces
        # (rendered "half transparent" with backface culling). trimesh's
        # fix_normals orients every manifold shell consistently — same
        # shape, just correct orientation. The shape/volume is unchanged.
        try:
            out_mesh = trimesh.load(io.BytesIO(out_bytes), file_type="stl",
                                    force="mesh")
            if isinstance(out_mesh, trimesh.Scene):
                geoms = [g for g in out_mesh.geometry.values()
                         if isinstance(g, trimesh.Trimesh)]
                out_mesh = trimesh.util.concatenate(geoms) if len(geoms) > 1 else geoms[0]
            out_mesh.fix_normals()
            out_bytes = out_mesh.export(file_type="stl")
        except Exception:
            pass
        return out_bytes
    finally:
        for p in (tmp_in, tmp_out):
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass

# ——————————————————————————————————————————————————————————————————————
# GPU packing job runner
# ——————————————————————————————————————————————————————————————————————

def format_placements(placed, orients):
    """Build the frontend placement dicts from (x,y,z,oi,name) tuples.

    Matches the exact shape the scene renderer consumes: x/y/z in mm, the
    orientation index, the piece name, and the 3x3 row-major rotation matrix
    from the orientation dict. Used both for the final `placements` result and
    for the live `placements_partial` updates while a sparrow job is running.
    """
    placements = []
    for (x, y, z, oi, name) in placed:
        od = orients[oi]
        rot = np.eye(4)
        if "rotation" in od:
            rot[:3, :3] = od["rotation"]
        placements.append({
            "x": round(float(x), 3),
            "y": round(float(y), 3),
            "z": round(float(z), 3),
            "orientation": oi,
            "name": name,
            "rotation": rot[:3, :3].tolist(),
        })
    return placements


def run_packing_job(job: dict, stl_data: bytes, box_dims: tuple, params: dict):
    try:
        method = params.get("method", "sparrow")
        # CPU methods run in parallel (no lock); GPU methods share a bounded
        # semaphore. Keeps the night-long GPU job's slot safe while letting
        # multiple (test) jobs run at once.
        locker = GPU_SEM if method in GPU_METHODS else nullcontext()
        with locker:
            job["status"] = "running"

            mesh = trimesh.load(io.BytesIO(stl_data), file_type='stl', force='mesh')
            if isinstance(mesh, trimesh.Scene):
                mesh = trimesh.util.concatenate(
                    [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)])

            # Estimated total pieces for progress/ETA: box capacity vs the
            # piece volume at a typical fill. Far better than a hard cap;
            # multi-box overrides this with the exact requested total.
            try:
                piece_vol = float(getattr(mesh, "volume", 0) or 0)
            except Exception:
                piece_vol = 0.0
            box_vol = float(box_dims[0] * box_dims[1] * box_dims[2])
            if piece_vol > 0:
                job["expected_pieces"] = max(1, int(box_vol * 0.20 / piece_vol))
            else:
                job["expected_pieces"] = 500

            box_l, box_w, box_h = box_dims
            cell = params.get("cell", 1.0)
            # The voxel size must adapt to the PIECE, not be a fixed number:
            # 1.5mm is ~15% of an 8mm part (way too coarse — cavities and
            # nesting vanish), but fine for a 10cm part. Rule: ~5% of the
            # piece's smallest dimension, clamped to [0.5, 1.0]mm. The
            # client's explicit (finer) cell is honored; anything coarser
            # than the adaptive value is clamped down.
            try:
                b = mesh.bounds
                piece_min_dim = float(min(
                    b[1][0] - b[0][0], b[1][1] - b[0][1], b[1][2] - b[0][2]))
            except Exception:
                piece_min_dim = 20.0
            # Cell rule (both directions):
            #  * SMALL parts: never coarser than ~5% of the piece's smallest
            #    dimension (a 1mm voxel is 12.5% of an 8mm cone and destroys
            #    the stacking/nesting), floor 0.5mm — the client presets are
            #    calibrated for ~30mm parts.
            #  * BIG parts: the UI's mm presets are way too fine (a 279mm
            #    part at 1mm = 3.5M voxels → minutes). Scale the client cell
            #    up with the part size so the voxel count stays bounded.
            try:
                cell = max(0.5, min(
                    float(cell) * max(1.0, piece_min_dim / 30.0),
                    0.05 * piece_min_dim))
            except (TypeError, ValueError):
                cell = max(0.5, min(1.0, 0.05 * piece_min_dim))
            yaw = params.get("yaw", 8)
            roll = params.get("roll", 4)
            pitch = params.get("pitch", 4)
            scan_vox = params.get("scan_vox", 1)
            method = params.get("method", "sparrow")
            fixed_orientation = params.get("fixed_orientation", 0)
            max_pieces = int(params.get("max_pieces", 5000))

            # Stacking/Compartment honor the user's chosen pose: when the
            # client sends a pre-rotated STL, restrict to in-plane spins of
            # that pose (the piece keeps resting on the chosen face).
            if fixed_orientation and method in ("stacking", "compartment", "multitray"):
                yaw = roll = pitch = 1
                packer_fixed_orientation = True
            else:
                packer_fixed_orientation = False

            # Optional explicit in-plane rotation (horizontal-axis ask when
            # re-calculating): 0/90/180/270° spin of the chosen pose. Restricts
            # the spin pool to that exact angle so the user can force e.g. the
            # 90° arrangement that packs ~30 more pieces in a long box.
            horizontal_angle = params.get("horizontal_angle")
            if horizontal_angle not in (None, ""):
                try:
                    horizontal_angle = float(horizontal_angle) % 180
                except (TypeError, ValueError):
                    horizontal_angle = None

            t0 = time.time()

            if method in ("sparrow", "stacking", "compartment", "spectral", "multitray"):
                import random as _random
                seed = params.get("seed", 0) or abs(hash(stl_data)) % (2**31)
                _random.seed(seed)
                packer = BestPacker(box_dims)
                packer._fixed_orientation = packer_fixed_orientation
                packer._smart_stack = bool(int(params.get("smart_stack", 1)))
                # Stacking uses SURFACE-shell voxelization: the pieces are
                # modelled as hard shells, so real nesting works (cones slide
                # into cones, rings interlock, concavities mate). Solid-fill
                # voxels would erase every cavity and make stacking behave
                # like a bounding-box grid.
                if method in ("stacking", "multitray"):
                    packer._surface_shell = True
                if horizontal_angle is not None and packer_fixed_orientation:
                    packer._horizontal_angle = horizontal_angle
                packer.load_mesh_from_data(mesh, n_yaw=yaw)

                def progress_cb(count, elapsed_s, partial_placements=None):
                    if job.get("cancelled"):
                        raise RuntimeError("job cancelled by user")
                    job["pieces"] = count
                    job["time_s"] = round(elapsed_s, 1)
                    # Throttle live placement updates (every 10 pieces) so the
                    # frontend isn't flooded with near-identical payloads.
                    if partial_placements and len(partial_placements) % 10 == 0:
                        job["placements_partial"] = format_placements(
                            partial_placements, packer._sparrow_voxel_data)

                # Use the ADAPTIVE-CLAMPED cell (the raw client value is
                # capped to ~5% of the piece size, floor 0.5 / cap 1.0 — a
                # 1mm voxel is 12.5% of an 8mm part and destroys the
                # stacking).
                vox_cell = cell
                if method == "sparrow":
                    placed_pieces, placed_meshes = packer.pack_sparrow(
                        max_pieces=500, n_workers=4, cell_size=vox_cell, verbose=False,
                        progress_callback=progress_cb, seed=seed)
                elif method == "spectral":
                    # Spectral: FFT-based, CPU — use a coarser cell for speed
                    spectral_cell = max(vox_cell, 2.0)
                    placed_pieces, placed_meshes = packer.pack_spectral(
                        max_pieces=500, cell_size=spectral_cell, verbose=False,
                        progress_callback=progress_cb, seed=seed)
                elif method == "stacking":
                    # C++ column engine (stacking.so): millisecond packing that
                    # nests hollow parts at the physical depth. Falls back to
                    # the Python greedy if the engine is unavailable.
                    placed_pieces, placed_meshes = packer.pack_stacking_cpp(
                        max_pieces=max_pieces, cell_size=vox_cell, verbose=False,
                        progress_callback=progress_cb, wall_thickness=1.0)
                elif method == "multitray":
                    # Multi-tray: pack the same box repeatedly until the
                    # requested piece count is reached (or a tray fits
                    # nothing). Per-tray strategy mirrors the single-box
                    # methods so the user can pick how each box is filled:
                    #   stacking     — free/in-plane stacking (default)
                    #   grid         — axis-aligned grid, no partitions
                    #   compartment  — grid + cardboard partition info per tray
                    #   sparrow      — GPU optimized nesting per tray
                    total_wanted = int(params.get("total_pieces", 1000))
                    tray_method = params.get("tray_method", "stacking")
                    tray_gap = float(params.get("gap", 1.0))
                    job["expected_pieces"] = total_wanted
                    packed_so_far = 0
                    trays = []
                    for tray_no in range(1, 64):
                        remaining = total_wanted - packed_so_far
                        if remaining <= 0:
                            break
                        if tray_method == "sparrow":
                            tray_placed, tray_meshes = packer.pack_sparrow(
                                max_pieces=min(remaining, max_pieces, 2000), n_workers=4,
                                cell_size=vox_cell, verbose=False,
                                progress_callback=progress_cb, seed=seed)
                        elif tray_method in ("grid", "compartment"):
                            # Exact bounding-box grid (same math as the
                            # single-box Graella): gap 0 for grid (boxes
                            # touch), cardboard thickness for compartment.
                            tray_placed, tray_meshes = packer.pack_bbox_grid(
                                gap=tray_gap, verbose=False,
                                progress_callback=progress_cb)
                        else:
                            tray_placed, tray_meshes = packer.pack_stacking(
                                max_pieces=min(remaining, max_pieces), cell_size=vox_cell,
                                verbose=False, progress_callback=progress_cb)
                        if not tray_placed:
                            break
                        # Sparrow may return slightly more than requested
                        # (its max_pieces is a soft target) — trim so the
                        # multi-box total is exact.
                        if len(tray_placed) > remaining:
                            tray_placed = tray_placed[:remaining]
                            tray_meshes = tray_meshes[:remaining]
                        if tray_method == "stacking":
                            from packer_best import refine_subvoxel, descent_stack_contact
                            tray_refined = refine_subvoxel(
                                tray_placed, packer._sparrow_voxel_data,
                                float(packer._sparrow_cell_size), n_rounds=3)
                            tray_refined = descent_stack_contact(
                                tray_refined, packer._sparrow_voxel_data, verbose=False)
                            oris_t = packer._sparrow_voxel_data
                            tray_meshes = []
                            for (x, y, z, oi, name) in tray_refined:
                                cm = oris_t[oi]['mesh'].copy()
                                cm.apply_translation([x, y, z])
                                tray_meshes.append(cm)
                            tray_placed = tray_refined
                        elif tray_method == "sparrow":
                            from packer_best import refine_subvoxel
                            tray_refined = refine_subvoxel(
                                tray_placed, packer._sparrow_voxel_data,
                                float(packer._sparrow_cell_size), n_rounds=3)
                            oris_t = packer._sparrow_voxel_data
                            tray_meshes = []
                            for (x, y, z, oi, name) in tray_refined:
                                cm = oris_t[oi]['mesh'].copy()
                                cm.apply_translation([x, y, z])
                                tray_meshes.append(cm)
                            tray_placed = tray_refined
                        tray_info = {
                            "tray": tray_no,
                            "pieces": len(tray_placed),
                            "fill_pct": round(sum(m.volume for m in tray_meshes) /
                                              (box_l * box_w * box_h) * 100, 1),
                            "placements": format_placements(
                                tray_placed, packer._sparrow_voxel_data),
                        }
                        if (tray_method == "compartment"
                                and getattr(packer, "_compartment_cell", None)):
                            cell_l_mm, cell_w_mm, n_layers, layer_pitch_mm = packer._compartment_cell
                            tray_info["compartment"] = {
                                "cellL": round(float(cell_l_mm), 2),
                                "cellW": round(float(cell_w_mm), 2),
                                "nLayers": int(n_layers),
                                "layerPitch": round(float(layer_pitch_mm), 2),
                            }
                        trays.append(tray_info)
                        packed_so_far += len(tray_placed)
                        placed_pieces = tray_placed
                        placed_meshes = tray_meshes
                    job["trays"] = trays
                else:  # compartment
                    placed_pieces, placed_meshes = packer.pack_bbox_grid(
                        gap=float(params.get("gap", 1.0)), verbose=False,
                        progress_callback=progress_cb)
                elapsed = time.time() - t0
                placed = placed_pieces
            else:
                orients = generate_orientations(mesh, cell, yaw, roll, pitch, box_dims)

                def progress_cb(count, elapsed_s):
                    if job.get("cancelled"):
                        raise RuntimeError("job cancelled by user")
                    job["pieces"] = count
                    job["time_s"] = round(elapsed_s, 1)

                placed_meshes, placed = pack(orients, box_dims, cell,
                                             scan_step_vox=scan_vox, verbose=False,
                                             progress_callback=progress_cb)
                elapsed = time.time() - t0

            # Sub-voxel refinement: slide each piece toward the box origin
            # and drop it into the valleys left by grid quantization, then
            # scale all moves back until the meshes are collision-free.
            # Voxel methods only (they have sparse voxel data per orientation).
            if method in ("sparrow", "stacking", "spectral") and placed_pieces \
                    and not getattr(packer, '_cpp_engine', False):
                from packer_best import refine_subvoxel
                refined_placed = refine_subvoxel(
                    placed_pieces, packer._sparrow_voxel_data,
                    float(packer._sparrow_cell_size), n_rounds=3)
                # Rebuild meshes at the refined positions (positions stay
                # within half a voxel of the grid anchor, so the packing
                # result is unchanged — only tighter).
                oris_here = packer._sparrow_voxel_data
                rm = []
                for (x, y, z, oi, name) in refined_placed:
                    cm = oris_here[oi]['mesh'].copy()
                    cm.apply_translation([x, y, z])
                    rm.append(cm)
                placed_pieces = refined_placed
                placed_meshes = rm
                placed = placed_pieces

            # Stacking contact pass: drop every piece onto the pieces below
            # it until exact mesh contact (FCL) — closes the residual voxel
            # shell gaps so stacked pieces physically touch. Only for SMALL
            # parts: the sub-millimetre gap is invisible on large pieces
            # (>25mm), and the FCL pass costs seconds per hundred pieces.
            if method == "stacking" and placed_pieces \
                    and not getattr(packer, '_cpp_engine', False):
                try:
                    bnd = mesh.bounds
                    pmin_dim = min(bnd[1, 0] - bnd[0, 0],
                                   bnd[1, 1] - bnd[0, 1],
                                   bnd[1, 2] - bnd[0, 2])
                except Exception:
                    pmin_dim = 0.0
                if pmin_dim <= 25.0:
                    from packer_best import descent_stack_contact
                    refined_placed = descent_stack_contact(
                        placed_pieces, packer._sparrow_voxel_data, verbose=False)
                    oris_here = packer._sparrow_voxel_data
                    rm = []
                    for (x, y, z, oi, name) in refined_placed:
                        cm = oris_here[oi]['mesh'].copy()
                        cm.apply_translation([x, y, z])
                        rm.append(cm)
                    placed_pieces = refined_placed
                    placed_meshes = rm
                    placed = placed_pieces

            elapsed = time.time() - t0

            jid = job["job_id"][:8]
            stl_out = RESULT_DIR / f"packed_{jid}.stl"
            png_out = RESULT_DIR / f"packed_{jid}.png"

            if placed_meshes:
                merged = trimesh.util.concatenate(placed_meshes)
                merged.export(str(stl_out))

                import matplotlib
                matplotlib.use("Agg")
                import matplotlib.pyplot as plt
                from matplotlib.patches import Rectangle

                fig, ax = plt.subplots(figsize=(10, 8))
                # The PNG is a quick top-down preview — beyond ~1200 pieces
                # matplotlib rectangle rendering dominates the job time, so
                # draw a uniform sample of the layout instead of every piece.
                png_sample = placed_meshes
                if len(placed_meshes) > 1200:
                    step = len(placed_meshes) / 1200
                    png_sample = [placed_meshes[int(i * step)] for i in range(1200)]
                colors = plt.cm.tab20(np.linspace(0, 1, max(20, len(png_sample))))
                ax.set_xlim(0, box_l)
                ax.set_ylim(0, box_w)
                ax.invert_yaxis()
                for i, m in enumerate(png_sample):
                    b = m.bounds
                    ax.add_patch(Rectangle((b[0, 0], b[0, 2]),
                                 b[1, 0] - b[0, 0], b[1, 2] - b[0, 2],
                                 alpha=0.2, color=colors[i % 20], ec="black", lw=0.2))
                ax.set_xlabel("X (mm)")
                ax.set_ylabel("Z (mm)")
                ax.set_title(f"{len(placed_meshes)} pieces | {box_l:.0f}×{box_w:.0f}×{box_h:.0f}mm")
                ax.set_aspect("equal")
                plt.tight_layout()
                plt.savefig(str(png_out), dpi=100)
                plt.close()

            ok = verify(placed_meshes) if placed_meshes else True

            # Build placement data with orientation transforms
            orients_for_placements = packer._sparrow_voxel_data if method in ("sparrow", "stacking", "compartment", "spectral", "multitray") else orients
            placements = format_placements(placed, orients_for_placements)

            # Populate every result field BEFORE flipping status to "done" so
            # concurrent status polls never observe a partially-written result.
            job["pieces"] = sum(t["pieces"] for t in trays) if job.get("trays") else len(placed_meshes)
            if job.get("trays"):
                job["fill_pct"] = round(sum(t["fill_pct"] for t in job["trays"]) / len(job["trays"]), 1) if job["trays"] else 0
            else:
                job["fill_pct"] = round(sum(m.volume for m in placed_meshes) /
                                        (box_l * box_w * box_h) * 100, 1) if placed_meshes else 0
            job["time_s"] = round(elapsed, 1)
            job["stl_path"] = str(stl_out) if placed_meshes else ""
            job["png_path"] = str(png_out) if placed_meshes else ""
            job["verified"] = ok
            job["placements"] = placements

            # Compartment packing implies a cardboard partition grid — expose
            # the cell pitch + layer pitch so the frontend can render the
            # dividers and shelves at the exact positions pieces are placed.
            if method == "compartment" and getattr(packer, "_compartment_cell", None):
                cell_l_mm, cell_w_mm, n_layers, layer_pitch_mm = packer._compartment_cell
                job["compartment"] = {
                    "cellL": round(float(cell_l_mm), 2),
                    "cellW": round(float(cell_w_mm), 2),
                    "nLayers": int(n_layers),
                    "layerPitch": round(float(layer_pitch_mm), 2),
                }

            # Interlocking analysis: pieces that cannot be lifted straight out
            # of the box (trapped by neighbours above them). Only for the
            # optimized GPU methods (sparrow / spectral), which have sparse
            # voxel data per orientation.
            if method in ("sparrow", "spectral") and placed_pieces:
                from packer_best import detect_interlocking
                vox_cell_used = getattr(packer, "_sparrow_cell_size", None) or cell
                oris_used = getattr(packer, "_sparrow_voxel_data", None) or orients_for_placements
                interlocked = detect_interlocking(placed_pieces, oris_used, float(vox_cell_used))
                job["interlocked"] = {
                    "count": len(interlocked),
                    "indices": interlocked,
                }
            job["status"] = "done"

    except Exception as e:
        job["status"] = "error"
        if job.get("cancelled"):
            job["error_msg"] = "Cancelled by user"
        else:
            job["error_msg"] = f"{e}\n{traceback.format_exc()}"


# ——————————————————————————————————————————————————————————————————————
# Ranked Box Options ("Comparar caixes") — cost-per-part across box sizes
# ——————————————————————————————————————————————————————————————————————

def piece_fits_box(mesh, box_dims):
    """Cheap fit check: does any axis-permutation of the part bbox fit the box?

    Used to skip obviously-too-small boxes BEFORE launching an expensive packing
    run. The packing engine explores more rotations than pure axis permutations,
    so this is a heuristic guard, not an exact capacity test.
    """
    box_l, box_w, box_h = box_dims
    b = mesh.bounds
    dims = (b[1, 0] - b[0, 0], b[1, 1] - b[0, 1], b[1, 2] - b[0, 2])
    if min(dims) > min(box_l, box_w, box_h) + 0.5:
        return False
    for (l, w, h) in set(itertools.permutations(dims)):
        if l <= box_l + 0.5 and w <= box_w + 0.5 and h <= box_h + 0.5:
            return True
    return False


def run_boxes_job(job: dict, stl_data: bytes, boxes: list, params: dict):
    """Run the packing for every candidate box sequentially, rank by cost/part.

    Uses the SAME packer machinery as /api/pack (BestPacker.pack_sparrow or the
    GPU voxel packer) with coarse settings (cell 2.0) so each box stays well
    under ~60s. GPU-bound (sparrow/voxel/spectral) runs share the GPU semaphore;
    the box comparison keeps a GPU slot for its whole run.
    """
    try:
        method = params.get("method", "sparrow")
        cell = params.get("cell", 2.0)
        piece_weight = params.get("piece_weight", 0.0)
        box_cost = params.get("box_cost", 0.0)
        packaging_cost = params.get("packaging_cost", 0.0)
        freight_per_kg = params.get("freight_per_kg", 0.0)
        freight_per_m3 = params.get("freight_per_m3", 0.0)

        with GPU_SEM:
            job["status"] = "running"

            mesh = trimesh.load(io.BytesIO(stl_data), file_type='stl', force='mesh')
            if isinstance(mesh, trimesh.Scene):
                mesh = trimesh.util.concatenate(
                    [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)])

            total = len(boxes)
            results = []
            for idx, (box_l, box_w, box_h) in enumerate(boxes):
                job["progress"] = {"current": idx, "total": total}
                job["current_box"] = [box_l, box_w, box_h]

                def skip(reason):
                    results.append({
                        "box_l": box_l, "box_w": box_w, "box_h": box_h,
                        "pieces": 0, "fill_pct": 0, "weight_kg": 0,
                        "cost_per_part": None, "total_cost": 0,
                        "skipped": True, "reason": reason,
                    })

                if not piece_fits_box(mesh, (box_l, box_w, box_h)):
                    skip("too_small")
                    continue

                t0 = time.time()
                try:
                    if method == "sparrow":
                        packer = BestPacker((box_l, box_w, box_h))
                        packer.load_mesh_from_data(mesh, n_yaw=8)
                        try:
                            b = mesh.bounds
                            pmin = float(min(b[1][0]-b[0][0], b[1][1]-b[0][1], b[1][2]-b[0][2]))
                        except Exception:
                            pmin = 20.0
                        box_cell = max(0.5, min(
                            float(cell) * max(1.0, pmin / 30.0),
                            0.05 * pmin))
                        placed_sparrow, placed_meshes = packer.pack_sparrow(
                            max_pieces=500, n_workers=4, cell_size=box_cell, verbose=False)
                        placed_meshes = placed_meshes or []
                    else:
                        if not HAS_CUDA:
                            raise RuntimeError("CUDA/GPU voxel packer not available")
                        orients = generate_orientations(mesh, cell, 8, 4, 4, (box_l, box_w, box_h))
                        placed_meshes, placed = pack(orients, (box_l, box_w, box_h), cell,
                                                     scan_step_vox=2, verbose=False)
                        placed_meshes = placed_meshes or []
                except Exception:
                    skip("error")
                    continue

                pieces = len(placed_meshes)
                if pieces == 0:
                    skip("no_fit")
                    continue

                box_vol = box_l * box_w * box_h
                fill_pct = round(sum(m.volume for m in placed_meshes) / box_vol * 100, 1) if box_vol else 0
                weight_kg = round(pieces * piece_weight, 3)

                freight_total = 0.0
                if freight_per_kg > 0:
                    freight_total = weight_kg * freight_per_kg
                elif freight_per_m3 > 0:
                    freight_total = (box_vol / 1e9) * freight_per_m3

                total_cost = round(box_cost + packaging_cost + freight_total, 3)
                cost_per_part = round(total_cost / pieces, 4) if pieces else None
                results.append({
                    "box_l": box_l, "box_w": box_w, "box_h": box_h,
                    "pieces": pieces,
                    "fill_pct": fill_pct,
                    "weight_kg": weight_kg,
                    "cost_per_part": cost_per_part,
                    "total_cost": total_cost,
                    "time_s": round(time.time() - t0, 1),
                    "skipped": False,
                })

            # Best first (ascending cost/part); skipped boxes fall to the end.
            results.sort(key=lambda r: r["cost_per_part"] if r.get("cost_per_part") is not None else float('inf'))

            job["boxes"] = results
            job["progress"] = {"current": total, "total": total}
            job["current_box"] = []
            job["status"] = "done"

    except Exception as e:
        job["status"] = "error"
        job["error_msg"] = f"{e}\n{traceback.format_exc()}"

# ——————————————————————————————————————————————————————————————————————
# API Endpoints
# ——————————————————————————————————————————————————————————————————————

@app.route("/api/health")
def health():
    gpus = []
    if HAS_CUDA:
        try:
            for i in range(cuda.get_device_count()):
                dev = cuda.get_current_device()
                gpus.append({"id": i, "name": dev.name.decode()})
        except Exception:
            pass
    return jsonify({
        "status": "ok",
        "pymeshlab": HAS_PYMESHLAB,
        "cuda": HAS_CUDA,
        "gpus": gpus,
        "jobs_active": sum(1 for j in JOBS.values() if j["status"] in ("queued", "running")),
    })


@app.route("/api/simplify", methods=["POST"])
def simplify():
    if not HAS_PYMESHLAB:
        return jsonify({"error": "pymeshlab not installed"}), 503

    data = request.get_data()
    if not data:
        return jsonify({"error": "No STL data in body"}), 400

    try:
        ratio = float(request.headers.get("X-Target-Ratio",
                    request.args.get("ratio", "0.5")))
    except ValueError:
        ratio = 0.5
    features = request.args.get("features", "1") not in ("0", "false", "")
    envelope = request.args.get("envelope", "0") not in ("0", "false", "")

    try:
        result = simplify_stl(data, max(0.01, min(1.0, ratio)),
                              preserve_features=features,
                              create_envelope=envelope)
        return result, 200, {"Content-Type": "application/octet-stream"}
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/orientations", methods=["POST"])
def orientations():
    """Server-side stable-orientation analysis (no physics engine, no
    browser load). Returns every unique stable resting pose: a cone gives
    base-down + base-up (on its rim), a brick all six faces, etc. Each
    entry carries a quaternion mapping the ORIGINAL mesh to the resting
    pose (face exactly horizontal) plus the aligned dims."""
    if "stl" not in request.files:
        return jsonify({"error": "Missing 'stl' file"}), 400
    stl_data = request.files["stl"].read()
    try:
        mesh = trimesh.load(io.BytesIO(stl_data), file_type="stl", force="mesh")
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(
                [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)])
        from orientation_analysis import analyze_stable_orientations
        # Complex/scanned meshes (tens of thousands of triangles with noisy
        # normals) defeat the flat-face clustering on the raw geometry.
        # Simplify internally FIRST (the decimated mesh has clean flat
        # faces) and run the analysis on that — the returned quaternions
        # apply to the original mesh unchanged (decimation preserves the
        # pose).
        n_faces = len(mesh.faces) if hasattr(mesh, "faces") else 0
        if n_faces > 20000:
            # pymeshlab's load_new_mesh accepts only a FILE PATH (not a
            # file-like object — a BytesIO raises and leaves the analysis
            # grinding on the raw 150k-tri mesh for minutes).
            simple = None
            if HAS_PYMESHLAB:
                try:
                    tmp = tempfile.NamedTemporaryFile(suffix=".stl", delete=False)
                    tmp.write(stl_data)
                    tmp.close()
                    target = max(5000, int(n_faces * 0.1))
                    ms = pymeshlab.MeshSet()
                    ms.load_new_mesh(tmp.name)
                    ms.meshing_decimation_quadric_edge_collapse(
                        targetfacenum=target, preserveboundary=True)
                    v = ms.current_mesh().vertex_matrix()
                    f = ms.current_mesh().face_matrix()
                    if len(f) > 0 and len(v) > 0:
                        simple = trimesh.Trimesh(vertices=v, faces=f, process=False)
                    try:
                        os.unlink(tmp.name)
                    except Exception:
                        pass
                except Exception:
                    try:
                        os.unlink(tmp.name)
                    except Exception:
                        pass
            # Fallback: the meshopt/VTK pipeline (also fast, C++).
            if simple is None:
                try:
                    simple = trimesh.load(io.BytesIO(simplify_stl(
                        stl_data, max(0.05, 5000 / n_faces))),
                        file_type="stl", force="mesh")
                    if isinstance(simple, trimesh.Scene):
                        simple = trimesh.util.concatenate(
                            [g for g in simple.geometry.values()
                             if isinstance(g, trimesh.Trimesh)])
                except Exception:
                    simple = None
            if simple is not None and len(simple.faces) > 0:
                mesh = simple
        relaxed = request.form.get("relaxed", "").lower() in ("1", "true", "yes", "on")
        poses = analyze_stable_orientations(mesh, relaxed=relaxed)
        return jsonify({"orientations": poses})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/pack", methods=["POST"])
def submit_pack():
    if "stl" not in request.files:
        return jsonify({"error": "Missing 'stl' file"}), 400

    stl_data = request.files["stl"].read()
    box_l = float(request.form.get("box_l", 385))
    box_w = float(request.form.get("box_w", 285))
    box_h = float(request.form.get("box_h", 150))

    params = {
        "cell": float(request.form.get("cell", 1.0)),
        "yaw": int(request.form.get("yaw", 8)),
        "roll": int(request.form.get("roll", 4)),
        "pitch": int(request.form.get("pitch", 4)),
        "scan_vox": int(request.form.get("scan_vox", 0)),
        "method": request.form.get("method", "sparrow"),
        "seed": int(request.form.get("seed", 0)),
        "fixed_orientation": int(request.form.get("fixed_orientation", 0)),
        "horizontal_angle": request.form.get("horizontal_angle"),
        "total_pieces": int(request.form.get("total_pieces", 1000)),
        "max_pieces": min(20000, int(request.form.get("max_pieces", 5000))),
        "tray_method": request.form.get("tray_method", "stacking"),
        "gap": float(request.form.get("gap", 1.0)),
        "cardboard_mm": float(request.form.get("cardboard_mm", 0)),
    }

    # ── Adaptive resolution: prefer scan-step scaling over cell bumping ──
    method = params["method"]
    cell = params["cell"]
    requested_cell = cell

    # Empirically measured model with Y-scan depth factor:
    # 160³@0.5mm ≈ 4.4s/pc, 160³@1mm ≈ 0.33s/pc,
    # 385x285x150@1mm ≈ 1.5s/pc, @2mm ≈ 0.2s/pc
    def estimate_eta_s(c, sv):
        floor_cand = (box_l / c) * (box_w / c) / (sv ** 2)
        piece_vox = (28 / c) * (37 / c) * (97 / c)
        box_ny = box_h / c
        y_scan_depth = 1 + box_ny / 3
        per_piece = floor_cand * 19 * piece_vox * y_scan_depth / 3.9e13
        n_placements = min(500, (box_l * box_w * box_h) / (28 * 37 * 97) * 3)
        return max(1.0, per_piece * n_placements)

    if method == "voxel":
        scan_step = params["scan_vox"] if params["scan_vox"] > 0 else 1
        # Scale scan step until fast enough (keeps cell resolution)
        for candidate_step in (1, 2, 4, 8):
            if estimate_eta_s(cell, candidate_step) < 60:
                scan_step = candidate_step
                break
        else:
            scan_step = 8
        # If still too slow, bump the cell
        while estimate_eta_s(cell, scan_step) > 60 and cell < 4.0:
            cell = min(4.0, cell * 1.5)
        params["cell"] = cell
        params["scan_vox"] = scan_step
        if cell != requested_cell:
            params["cell_adjusted_from"] = requested_cell

    # ETA estimate based on final (adjusted) params. For the fast methods the
    # piece volume gives a much better idea of the box total than any fixed
    # number — show the expected piece count instead of a made-up time, and
    # let the live ETA (real pace × remaining) take over after the first few
    # pieces are placed.
    if method in ("stacking", "compartment", "multitray", "grid"):
        try:
            pm = trimesh.load(io.BytesIO(stl_data), file_type='stl', force='mesh')
            if isinstance(pm, trimesh.Scene):
                pm = trimesh.util.concatenate(
                    [g for g in pm.geometry.values() if isinstance(g, trimesh.Trimesh)])
            pv = float(getattr(pm, "volume", 0) or 0)
            expected = max(1, int(box_l * box_w * box_h * 0.20 / pv)) if pv > 0 else 0
        except Exception:
            expected = 0
        if method == "multitray":
            expected = params.get("total_pieces", 1000)
        if expected > 0:
            eta_s = max(2, expected * 0.02)
            eta_label = f"~{expected} peces"
        else:
            eta_s = 2
            eta_label = "2s"
    elif method == "sparrow":
        box_vol = box_l * box_w * box_h
        eta_s = max(2, min(120, box_vol / 40000))
        eta_label = f"{eta_s:.0f}s"
    elif method == "spectral":
        # Spectral: ~3s per placement at 2mm cell, ~80-120 placements
        box_vol = box_l * box_w * box_h
        n_place = min(150, max(20, box_vol / (28 * 37 * 97) * 0.5))
        eta_s = max(10, n_place * 2.5)
        if eta_s > 60:
            eta_label = f"{eta_s/60:.1f}min"
        else:
            eta_label = f"{eta_s:.0f}s"
    else:
        eta_s = max(2, estimate_eta_s(cell, params["scan_vox"]))
        if eta_s > 60:
            eta_label = f"{eta_s/60:.1f}min"
        else:
            eta_label = f"{eta_s:.0f}s"
    estimated_time = {"seconds": round(eta_s, 1), "label": eta_label}

    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "status": "queued",
        "pieces": 0,
        "expected_pieces": 0,
        "fill_pct": 0,
        "time_s": 0,
        "stl_path": "",
        "png_path": "",
        "placements": [],
        "placements_partial": [],
        "verified": False,
        "created": time.time(),
    }

    with JOBS_LOCK:
        JOBS[job_id] = job

    threading.Thread(target=run_packing_job,
                     args=(job, stl_data, (box_l, box_w, box_h), params),
                     daemon=True).start()

    # Watchdog: safety net only — long calculations (a full night) are a
    # legitimate use case, so the cap is 12h, not 10 minutes. The frontend
    # shows live progress and lets the user cancel explicitly.
    def watchdog():
        time.sleep(43200)
        if job["status"] in ("queued", "running"):
            job["status"] = "error"
            job["error_msg"] = ("Timeout after 12 hours.")

    threading.Thread(target=watchdog, daemon=True).start()

    return jsonify({
        "job_id": job_id,
        "status": "queued",
        "box": [box_l, box_w, box_h],
        "params": params,
        "estimated_time": estimated_time,
        "check_url": f"/api/pack/{job_id}",
    })


@app.route("/api/pack/<job_id>/cancel", methods=["POST"])
def cancel_pack(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "unknown job"}), 404
    job["cancelled"] = True
    if job["status"] in ("queued", "running"):
        job["status"] = "error"
        job["error_msg"] = "Cancelled by user"
    return jsonify({"status": "cancelled"})


@app.route("/api/pack/<job_id>")
def get_pack_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    result = {
        "job_id": job["job_id"],
        "status": job["status"],
        "pieces": job["pieces"],
        "expected_pieces": job.get("expected_pieces", 0),
        "fill_pct": job["fill_pct"],
        "time_s": job["time_s"],
        "verified": job["verified"],
    }

    if job["status"] == "running":
        # Live packing preview (sparrow only) — the partial placement list the
        # frontend renders incrementally while the job is still packing.
        result["placements_partial"] = job.get("placements_partial") or []
    elif job["status"] == "done":
        result["stl_url"] = f"/api/pack/{job_id}/stl"
        result["png_url"] = f"/api/pack/{job_id}/png"
        result["placements"] = job["placements"]
        if job.get("compartment"):
            result["compartment"] = job["compartment"]
        if job.get("interlocked"):
            result["interlocked"] = job["interlocked"]
        if job.get("trays"):
            result["trays"] = job["trays"]
    elif job["status"] == "error":
        result["error"] = job.get("error_msg", "Unknown error")

    return jsonify(result)


@app.route("/api/pack/<job_id>/stl")
def get_pack_stl(job_id):
    job = JOBS.get(job_id)
    if not job or not job.get("stl_path"):
        return jsonify({"error": "STL not found"}), 404
    return send_file(job["stl_path"], mimetype="application/octet-stream",
                     as_attachment=True, download_name=f"packed_{job_id[:8]}.stl")


@app.route("/api/pack/<job_id>/png")
def get_pack_png(job_id):
    job = JOBS.get(job_id)
    if not job or not job.get("png_path"):
        return jsonify({"error": "PNG not found"}), 404
    return send_file(job["png_path"], mimetype="image/png")


@app.route("/api/boxes", methods=["POST"])
def submit_boxes():
    """Ranked Box Options: pack the STL into MULTIPLE box sizes and rank by cost/part.

    Form fields:
        stl            — STL file (required)
        boxes          — optional JSON array of [l, w, h] (mm). If omitted the
                         legacy box_l/box_w/box_h fields are used.
        method         — "sparrow" (default, coarse cell 2.0) or "voxel"
        piece_weight   — kg per piece (from material) for freight weight
        box_cost       — € per box (e.g. carton price)
        packaging_cost — € per box (dunnage/tape)
        freight_per_kg — € per kg of content (alternative to m3)
        freight_per_m3 — € per m3 of box volume (alternative to kg)
    """
    if "stl" not in request.files:
        return jsonify({"error": "Missing 'stl' file"}), 400

    stl_data = request.files["stl"].read()

    boxes = []
    boxes_raw = request.form.get("boxes")
    if boxes_raw:
        try:
            parsed = json.loads(boxes_raw)
            for b in parsed:
                if isinstance(b, dict):
                    boxes.append([float(b.get("l", 0)), float(b.get("w", 0)), float(b.get("h", 0))])
                elif len(b) == 3:
                    boxes.append([float(b[0]), float(b[1]), float(b[2])])
        except Exception as e:
            return jsonify({"error": f"Invalid 'boxes' JSON: {e}"}), 400
    if not boxes:
        boxes = [[
            float(request.form.get("box_l", 385)),
            float(request.form.get("box_w", 285)),
            float(request.form.get("box_h", 150)),
        ]]
    boxes = [b for b in boxes if b[0] > 0 and b[1] > 0 and b[2] > 0]
    if not boxes:
        return jsonify({"error": "No valid boxes provided"}), 400

    try:
        params = {
            "method": request.form.get("method", "sparrow"),
            "cell": float(request.form.get("cell", 2.0) or 2.0),
            "piece_weight": float(request.form.get("piece_weight", 0) or 0),
            "box_cost": float(request.form.get("box_cost", 0) or 0),
            "packaging_cost": float(request.form.get("packaging_cost", 0) or 0),
            "freight_per_kg": float(request.form.get("freight_per_kg", 0) or 0),
            "freight_per_m3": float(request.form.get("freight_per_m3", 0) or 0),
        }
    except ValueError as e:
        return jsonify({"error": f"Invalid cost/weight value: {e}"}), 400

    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "kind": "boxes",
        "status": "queued",
        "boxes": [],
        "progress": {"current": 0, "total": len(boxes)},
        "current_box": boxes[0],
        "cost_config": {
            "box_cost": params["box_cost"],
            "packaging_cost": params["packaging_cost"],
            "freight_per_kg": params["freight_per_kg"],
            "freight_per_m3": params["freight_per_m3"],
            "piece_weight": params["piece_weight"],
            "method": params["method"],
            "cell": params["cell"],
        },
        "created": time.time(),
    }

    with JOBS_LOCK:
        JOBS[job_id] = job

    threading.Thread(target=run_boxes_job,
                     args=(job, stl_data, boxes, params),
                     daemon=True).start()

    return jsonify({
        "job_id": job_id,
        "status": "queued",
        "boxes_count": len(boxes),
        "check_url": f"/api/boxes/{job_id}",
    })


@app.route("/api/boxes/<job_id>")
def get_boxes_status(job_id):
    job = JOBS.get(job_id)
    if not job or job.get("kind") != "boxes":
        return jsonify({"error": "Job not found"}), 404

    result = {
        "job_id": job["job_id"],
        "status": job["status"],
        "boxes": job.get("boxes") or [],
        "progress": job.get("progress"),
        "current_box": job.get("current_box"),
        "cost_config": job.get("cost_config"),
    }
    if job["status"] == "error":
        result["error"] = job.get("error_msg", "Unknown error")
    return jsonify(result)


@app.route("/api/jobs")
def list_jobs():
    jobs_list = [{
        "job_id": j["job_id"][:8] + "...",
        "status": j["status"],
        "pieces": j.get("pieces", 0),
        "fill_pct": j.get("fill_pct", 0),
        "time_s": j.get("time_s", 0),
        "created": j.get("created", 0),
        "kind": j.get("kind", "pack"),
    } for j in sorted(JOBS.values(), key=lambda j: -j.get("created", 0))[:20]]
    return jsonify({"jobs": jobs_list, "total": len(JOBS), "gpu_available": HAS_CUDA})


# ——————————————————————————————————————————————————————————————————————
# CLI
# ——————————————————————————————————————————————————————————————————————

@app.route("/api/report/export", methods=["POST"])
def report_export():
    """DOCX / XLSX export of the packing report — same content as the PDF
    (mirrors the sections and value formatting of report-generator.js), in
    an editable format. Word/Excel reflow the layout, so the mm-exact print
    layout is only available in the PDF, but the data is identical."""
    try:
        body = request.get_json(force=True)
        fmt = (body.get("format") or "docx").lower()
        data = body.get("data") or {}
        views = body.get("views") or {}
        from report_export import build_docx, build_xlsx
        if fmt == "xlsx":
            payload = build_xlsx(data, views)
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ext = "xlsx"
        else:
            payload = build_docx(data, views)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = "docx"
        name = (data.get("stlFileName") or "informe").replace(".stl", "").replace(".STL", "")
        return send_file(
            io.BytesIO(payload),
            mimetype=mime,
            as_attachment=True,
            download_name=f"{name}_{fmt}.{ext}",
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="PackAssist Unified Backend")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()

    print(f"\n  PackAssist Server")
    print(f"  http://{args.host}:{args.port}")
    print(f"  Health:     GET  /api/health")
    print(f"  Simplify:   POST /api/simplify")
    print(f"  GPU Pack:   POST /api/pack  (form: stl + box_l/w/h + cell)")
    print(f"  Job status: GET  /api/pack/<id>\n")
    print(f"  PyMeshLab:  {'✓' if HAS_PYMESHLAB else '✗ (simplify disabled)'}")
    print(f"  CUDA/GPU:   {'✓' if HAS_CUDA else '✗ (packer disabled)'}\n")

    app.run(host=args.host, port=args.port, debug=args.debug)
