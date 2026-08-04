"""
packer_api.py ΓÇö GPU Packer REST API service.
Flask server that accepts STL files, runs the GPU voxel packer,
and returns results asynchronously.

Usage:
    python packer_api.py [--host 0.0.0.0] [--port 8788]
Endpoints:
    POST /api/pack       - Submit a job, returns {job_id}
    GET  /api/pack/<id>  - Get job status + results
    GET  /api/health     - Health check
    GET  /api/jobs       - List all jobs
"""
import sys, os, time, uuid, json, threading, io, base64
from pathlib import Path
from dataclasses import dataclass, field
from flask import Flask, request, jsonify, send_file

# Add parent for GPU packer import
sys.path.insert(0, str(Path(__file__).parent))
from packer_gpu_voxel import (
    generate_orientations, pack, voxelize_mesh, meshes_collide, verify
)
import trimesh
import numpy as np
from numba import cuda

app = Flask(__name__)

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
GPU_LOCK = threading.Lock()  # only one GPU job at a time
RESULT_DIR = Path(__file__).parent / "results"
RESULT_DIR.mkdir(exist_ok=True)


@dataclass
class JobState:
    job_id: str
    status: str = "queued"  # queued | running | done | error
    progress: int = 0
    pieces: int = 0
    fill_pct: float = 0.0
    time_s: float = 0.0
    error_msg: str = ""
    stl_path: str = ""
    png_path: str = ""
    created: float = field(default_factory=time.time)


def run_packing_job(job_id: str, stl_data: bytes, box_dims: tuple, params: dict):
    """Run the GPU packer in a background thread."""
    job = JOBS[job_id]
    try:
        with GPU_LOCK:
            job.status = "running"
            
            # Load STL from bytes
            mesh = trimesh.load(io.BytesIO(stl_data), file_type='stl', force='mesh')
            if isinstance(mesh, trimesh.Scene):
                mesh = trimesh.util.concatenate([g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)])
            
            box_l, box_w, box_h = box_dims
            cell = params.get('cell', 0.5)
            yaw = params.get('yaw', 8)
            roll = params.get('roll', 4)
            pitch = params.get('pitch', 4)
            scan_vox = params.get('scan_vox', 2)
            
            t0 = time.time()
            
            # Generate orientations
            orients = generate_orientations(mesh, cell, yaw, roll, pitch, box_dims)
            
            # Pack
            def progress_callback(count, fill):
                job.progress = count
                job.pieces = count
                job.fill_pct = fill
            
            placed_meshes, placed = pack(orients, box_dims, cell, scan_step_vox=scan_vox, verbose=False)
            
            elapsed = time.time() - t0
            
            # Save results
            job_id_safe = job_id[:8]
            stl_out = RESULT_DIR / f"packed_{job_id_safe}.stl"
            png_out = RESULT_DIR / f"packed_{job_id_safe}.png"
            
            if placed_meshes:
                merged = trimesh.util.concatenate(placed_meshes)
                merged.export(str(stl_out))
                
                # Quick PNG (top view only for API)
                import matplotlib
                matplotlib.use('Agg')
                import matplotlib.pyplot as plt
                from matplotlib.patches import Rectangle
                
                fig, ax = plt.subplots(figsize=(10, 8))
                colors = plt.cm.tab20(np.linspace(0, 1, max(20, len(placed_meshes))))
                ax.set_xlim(0, box_l); ax.set_ylim(0, box_w); ax.invert_yaxis()
                for i, m in enumerate(placed_meshes):
                    b = m.bounds
                    ax.add_patch(Rectangle((b[0,0], b[0,2]), b[1,0]-b[0,0], b[1,2]-b[0,2],
                                          alpha=0.2, color=colors[i%20], ec='black', lw=0.2))
                ax.set_xlabel('X (mm)'); ax.set_ylabel('Z (mm)')
                ax.set_title(f"{len(placed_meshes)} pieces, {box_l:.0f}x{box_w:.0f}x{box_h:.0f}mm")
                ax.set_aspect('equal')
                plt.tight_layout(); plt.savefig(str(png_out), dpi=100); plt.close()
            
            # Verify
            ok = verify(placed_meshes)
            
            job.status = "done"
            job.pieces = len(placed_meshes)
            job.fill_pct = sum(m.volume for m in placed_meshes) / (box_l*box_w*box_h) * 100 if placed_meshes else 0
            job.time_s = elapsed
            job.stl_path = str(stl_out) if placed_meshes else ""
            job.png_path = str(png_out) if placed_meshes else ""
            
            # Build placements array with orientation transforms
            job.placements = []
            for (x, y, z, oi, name), _ in zip(placed, placed_meshes):
                od = orients[oi]
                rot = np.eye(4)
                if 'rotation' in od:
                    rot[:3, :3] = od['rotation']
                job.placements.append({
                    "x": round(float(x), 3),
                    "y": round(float(y), 3),
                    "z": round(float(z), 3),
                    "orientation": oi,
                    "name": name,
                    "rotation": rot[:3, :3].tolist(),
                })
            
    except Exception as e:
        job.status = "error"
        job.error_msg = str(e)


# ═══════════════ API Endpoints ═══════════════

@app.route('/api/health')
def health():
    gpus = []
    try:
        cuda.detect()
        for i in range(cuda.get_device_count()):
            dev = cuda.get_current_device()
            gpus.append({"id": i, "name": dev.name.decode()})
    except Exception as e:
        gpus = [{"error": str(e)}]
    return jsonify({
        "status": "ok",
        "gpus": gpus,
        "jobs_active": sum(1 for j in JOBS.values() if j.status in ("queued", "running"))
    })


@app.route('/api/pack', methods=['POST'])
def submit_pack():
    # Parse STL file
    if 'stl' not in request.files:
        return jsonify({"error": "Missing 'stl' file"}), 400
    
    stl_file = request.files['stl']
    stl_data = stl_file.read()
    
    # Parse box dimensions
    box_l = float(request.form.get('box_l', 385))
    box_w = float(request.form.get('box_w', 285))
    box_h = float(request.form.get('box_h', 150))
    
    # Parse optional params
    params = {
        'cell': float(request.form.get('cell', 0.5)),
        'yaw': int(request.form.get('yaw', 8)),
        'roll': int(request.form.get('roll', 4)),
        'pitch': int(request.form.get('pitch', 4)),
        'scan_vox': int(request.form.get('scan_vox', 2)),
    }
    
    job_id = str(uuid.uuid4())
    job = JobState(job_id=job_id)
    
    with JOBS_LOCK:
        JOBS[job_id] = job
    
    thread = threading.Thread(
        target=run_packing_job,
        args=(job_id, stl_data, (box_l, box_w, box_h), params),
        daemon=True
    )
    thread.start()
    
    return jsonify({
        "job_id": job_id,
        "status": "queued",
        "box": [box_l, box_w, box_h],
        "params": params,
        "check_url": f"/api/pack/{job_id}"
    })


@app.route('/api/pack/<job_id>')
def get_pack_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    result = {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "pieces": job.pieces,
        "fill_pct": round(job.fill_pct, 1),
        "time_s": round(job.time_s, 1),
    }
    
    if job.status == "done":
        result["stl_url"] = f"/api/pack/{job_id}/stl"
        result["png_url"] = f"/api/pack/{job_id}/png"
        result["placements"] = job.placements
    elif job.status == "error":
        result["error"] = job.error_msg
    
    return jsonify(result)


@app.route('/api/pack/<job_id>/stl')
def get_pack_stl(job_id):
    job = JOBS.get(job_id)
    if not job or not job.stl_path:
        return jsonify({"error": "Not found"}), 404
    return send_file(job.stl_path, mimetype='application/octet-stream',
                     as_attachment=True, download_name=f"packed_{job_id[:8]}.stl")


@app.route('/api/pack/<job_id>/png')
def get_pack_png(job_id):
    job = JOBS.get(job_id)
    if not job or not job.png_path:
        return jsonify({"error": "Not found"}), 404
    return send_file(job.png_path, mimetype='image/png')


@app.route('/api/jobs')
def list_jobs():
    jobs_list = [{
        "job_id": j.job_id,
        "status": j.status,
        "pieces": j.pieces,
        "fill_pct": round(j.fill_pct, 1),
        "time_s": round(j.time_s, 1),
        "created": j.created,
    } for j in sorted(JOBS.values(), key=lambda j: -j.created)[:20]]
    return jsonify({"jobs": jobs_list, "total": len(JOBS)})


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description="GPU Packer API Server")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8788)
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()
    
    print(f"\n  GPU Packer API")
    print(f"  http://{args.host}:{args.port}")
    print(f"  Health: http://{args.host}:{args.port}/api/health")
    print(f"  Submit: POST http://{args.host}:{args.port}/api/pack\n")
    
    app.run(host=args.host, port=args.port, debug=args.debug)
