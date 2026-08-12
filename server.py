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
import sys, os, io, time, uuid, json, threading, tempfile, traceback
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file

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
        sys.path.insert(0, str(Path(__file__).parent / "physics-engine"))
        from packer_best import BestPacker, generate_orientations as gen_orient_best, compute_face_normals
except Exception as e:
    HAS_CUDA = False
    print(f"[server] WARNING: CUDA/GPU packer not available: {e}")

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
    return response

# Serve the web frontend at /
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
GPU_LOCK = threading.Lock()

# ——————————————————————————————————————————————————————————————————————
# Mesh simplification (ported from mesh_server.py)
# ——————————————————————————————————————————————————————————————————————

def simplify_stl(input_bytes: bytes, target_ratio: float) -> bytes:
    if not HAS_PYMESHLAB:
        raise RuntimeError("pymeshlab is not installed")

    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        f.write(input_bytes)
        tmp_in = f.name

    tmp_out = tmp_in + "_simplified.stl"
    try:
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(tmp_in)

        original_faces = ms.current_mesh().face_number()
        target_faces = max(12, int(original_faces * target_ratio))

        try:
            ms.meshing_decimation_quadric_edge_collapse(
                targetfacenum=target_faces, preservenormal=True,
                preservetopology=True, optimalplacement=True, qualitythr=0.5)
        except Exception:
            try:
                ms.apply_filter('simplification_quadric_edge_collapse_decimation',
                                targetfacenum=target_faces, preservenormal=True,
                                preservetopology=True, optimalplacement=True)
            except Exception:
                ms.meshing_decimation_clustering(
                    threshold=pymeshlab.AbsoluteValue(
                        ms.current_mesh().bounding_box().diagonal() * 0.01))

        ms.save_current_mesh(tmp_out)
        with open(tmp_out, "rb") as f:
            return f.read()
    finally:
        for p in (tmp_in, tmp_out):
            try:
                os.unlink(p)
            except OSError:
                pass

# ——————————————————————————————————————————————————————————————————————
# GPU packing job runner
# ——————————————————————————————————————————————————————————————————————

def run_packing_job(job: dict, stl_data: bytes, box_dims: tuple, params: dict):
    try:
        with GPU_LOCK:
            job["status"] = "running"

            mesh = trimesh.load(io.BytesIO(stl_data), file_type='stl', force='mesh')
            if isinstance(mesh, trimesh.Scene):
                mesh = trimesh.util.concatenate(
                    [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)])

            box_l, box_w, box_h = box_dims
            cell = params.get("cell", 0.5)
            yaw = params.get("yaw", 8)
            roll = params.get("roll", 4)
            pitch = params.get("pitch", 4)
            scan_vox = params.get("scan_vox", 1)
            method = params.get("method", "voxel")

            t0 = time.time()

            if method == "sparrow":
                import random as _random
                _random.seed(abs(hash(stl_data)) % (2**31))
                packer = BestPacker(box_dims)
                packer.load_mesh_from_data(mesh, n_yaw=yaw)
                placed_sparrow, placed_meshes = packer.pack_sparrow(
                    max_pieces=500, n_workers=1, verbose=False)
                elapsed = time.time() - t0
                placed = placed_sparrow
            else:
                orients = generate_orientations(mesh, cell, yaw, roll, pitch, box_dims)
                placed_meshes, placed = pack(orients, box_dims, cell,
                                             scan_step_vox=scan_vox, verbose=False)
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
                colors = plt.cm.tab20(np.linspace(0, 1, max(20, len(placed_meshes))))
                ax.set_xlim(0, box_l)
                ax.set_ylim(0, box_w)
                ax.invert_yaxis()
                for i, m in enumerate(placed_meshes):
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

            job["status"] = "done"
            job["pieces"] = len(placed_meshes)
            job["fill_pct"] = round(sum(m.volume for m in placed_meshes) /
                                    (box_l * box_w * box_h) * 100, 1) if placed_meshes else 0
            job["time_s"] = round(elapsed, 1)
            job["stl_path"] = str(stl_out) if placed_meshes else ""
            job["png_path"] = str(png_out) if placed_meshes else ""
            job["verified"] = ok

            # Build placement data with orientation transforms
            job["placements"] = []
            orients_for_placements = packer.orientations if method == "sparrow" else orients
            for (x, y, z, oi, name), _ in zip(placed, placed_meshes):
                od = orients_for_placements[oi]
                rot = np.eye(4)
                if "rotation" in od:
                    rot[:3, :3] = od["rotation"]
                job["placements"].append({
                    "x": round(float(x), 3),
                    "y": round(float(y), 3),
                    "z": round(float(z), 3),
                    "orientation": oi,
                    "name": name,
                    "rotation": rot[:3, :3].tolist(),
                })

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

    try:
        result = simplify_stl(data, max(0.01, min(1.0, ratio)))
        return result, 200, {"Content-Type": "application/octet-stream"}
    except Exception as e:
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
        "cell": float(request.form.get("cell", 0.5)),
        "yaw": int(request.form.get("yaw", 8)),
        "roll": int(request.form.get("roll", 4)),
        "pitch": int(request.form.get("pitch", 4)),
        "scan_vox": int(request.form.get("scan_vox", 1)),
        "method": request.form.get("method", "voxel"),
    }

    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "status": "queued",
        "pieces": 0,
        "fill_pct": 0,
        "time_s": 0,
        "stl_path": "",
        "png_path": "",
        "placements": [],
        "verified": False,
        "created": time.time(),
    }

    with JOBS_LOCK:
        JOBS[job_id] = job

    threading.Thread(target=run_packing_job,
                     args=(job, stl_data, (box_l, box_w, box_h), params),
                     daemon=True).start()

    return jsonify({
        "job_id": job_id,
        "status": "queued",
        "box": [box_l, box_w, box_h],
        "params": params,
        "check_url": f"/api/pack/{job_id}",
    })


@app.route("/api/pack/<job_id>")
def get_pack_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    result = {
        "job_id": job["job_id"],
        "status": job["status"],
        "pieces": job["pieces"],
        "fill_pct": job["fill_pct"],
        "time_s": job["time_s"],
        "verified": job["verified"],
    }

    if job["status"] == "done":
        result["stl_url"] = f"/api/pack/{job_id}/stl"
        result["png_url"] = f"/api/pack/{job_id}/png"
        result["placements"] = job["placements"]
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


@app.route("/api/jobs")
def list_jobs():
    jobs_list = [{
        "job_id": j["job_id"][:8] + "...",
        "status": j["status"],
        "pieces": j["pieces"],
        "fill_pct": j["fill_pct"],
        "time_s": j["time_s"],
        "created": j["created"],
    } for j in sorted(JOBS.values(), key=lambda j: -j["created"])[:20]]
    return jsonify({"jobs": jobs_list, "total": len(JOBS), "gpu_available": HAS_CUDA})


# ——————————————————————————————————————————————————————————————————————
# CLI
# ——————————————————————————————————————————————————————————————————————

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
