#!/usr/bin/env python3
"""
Comprehensive GPU Voxel Packing API test suite.
"""

import requests
import time
import json
import sys
import os
import numpy as np
import trimesh

BASE = "http://127.0.0.1:8787"
STL = os.path.join(os.path.dirname(__file__), "..", "physics-engine", "stl", "6683688_simp0.1pct.stl")

def submit(job):
    with open(STL, "rb") as f:
        r = requests.post(f"{BASE}/api/pack", files={"stl": f}, data=job["params"],
                          timeout=10)
    r.raise_for_status()
    job["jid"] = r.json()["job_id"]
    job["submitted"] = time.time()

def poll(job, timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{BASE}/api/pack/{job['jid']}", timeout=5)
        d = r.json()
        if d.get("status") in ("done", "error"):
            job.update(d)
            return
        time.sleep(2)
    raise TimeoutError(f"Job timed out after {timeout}s")

def verify_collisions(placements):
    if not placements:
        return "no_placements"
    try:
        base = trimesh.load(STL, file_type='stl', force='mesh')
        if isinstance(base, trimesh.Scene):
            base = trimesh.util.concatenate([g for g in base.geometry.values() if isinstance(g, trimesh.Trimesh)])
    except Exception as e:
        return f"load:{e}"

    meshes = []
    for p in placements:
        m = base.copy()
        rot = np.eye(4)
        rot[:3, :3] = np.array(p["rotation"])
        m.apply_transform(rot)
        m.apply_translation([p["x"], p["y"], p["z"]])
        meshes.append(m)

    collisions = 0
    for i in range(len(meshes)):
        for j in range(i + 1, len(meshes)):
            a, b = meshes[i].bounds, meshes[j].bounds
            if (a[1,0]>b[0,0] and a[0,0]<b[1,0] and
                a[1,1]>b[0,1] and a[0,1]<b[1,1] and
                a[1,2]>b[0,2] and a[0,2]<b[1,2]):
                try:
                    d = trimesh.proximity.closest_point(meshes[i], meshes[j].vertices)
                    if d is not None and d[1].min() < 0.001:
                        collisions += 1
                        break
                    d = trimesh.proximity.closest_point(meshes[j], meshes[i].vertices)
                    if d is not None and d[1].min() < 0.001:
                        collisions += 1
                        break
                except Exception:
                    pass
    return "PASS" if collisions == 0 else f"{collisions}_collisions"

def test(name, params, timeout=180):
    job = {"name": name, "params": params}
    t0 = time.time()
    try:
        submit(job)
        poll(job, timeout)
        elapsed = time.time() - t0
        collisions = "—"
        if job.get("placements"):
            collisions = verify_collisions(job["placements"])
        status = "PASS" if (job.get("status") == "done" and
                           job.get("pieces", 0) > 0 and
                           collisions == "PASS") else "FAIL"
        pieces = job.get("pieces", "?")
        fill = job.get("fill_pct", "?")
        t = job.get("time_s", "?")
        print(f"  {'PASS' if status=='PASS' else 'FAIL'} | {name:<35} | {str(params.get('box','')):<18} | cell={params.get('cell',''):<4} | {params.get('method','voxel'):<8} | pcs={pieces:<5} | fill={str(fill)+'%':<8} | {str(t)+'s':<8} | coll={collisions}")
        return {
            "name": name, "params": params, "status": status,
            "pieces": pieces, "fill_pct": fill, "time_s": t,
            "collisions": collisions, "elapsed": round(elapsed, 1),
            "error": job.get("error_msg", ""), "verified": job.get("verified", False),
        }
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  FAIL | {name:<35} | error={str(e)[:80]}")
        return {
            "name": name, "params": params, "status": "FAIL",
            "pieces": 0, "fill_pct": 0, "time_s": 0,
            "collisions": "error", "elapsed": round(elapsed, 1),
            "error": str(e), "verified": False,
        }

def main():
    print("=" * 110)
    print("  PackAssist GPU Voxel Packing — Full API Test Suite")
    print(f"  STL: {os.path.basename(STL)} ({os.path.getsize(STL)} bytes)")
    print("=" * 110)

    # ── Quick health check ──
    try:
        h = requests.get(f"{BASE}/api/health", timeout=5).json()
        print(f"  Health: {h['status']} | CUDA: {h['cuda']} | PyMeshLab: {h['pymeshlab']} | GPUs: {len(h.get('gpus',[]))}")
    except Exception as e:
        print(f"  Health: ERROR - {e}")
        sys.exit(1)

    results = []

    # Define test cases
    tests = [
        # (name, params_dict)
        ("1. voxel_385x285x150_cell0.5", {"box_l":385,"box_w":285,"box_h":150,"cell":0.5,"yaw":8,"roll":4,"pitch":4,"scan_vox":1,"method":"voxel"}),
        ("2. voxel_160cube_cell0.5",    {"box_l":160,"box_w":160,"box_h":160,"cell":0.5,"yaw":8,"roll":4,"pitch":4,"scan_vox":1,"method":"voxel"}),
        ("3. voxel_200cube_cell0.5",    {"box_l":200,"box_w":200,"box_h":200,"cell":0.5,"yaw":8,"roll":4,"pitch":4,"scan_vox":1,"method":"voxel"}),
        ("4. voxel_385x285x150_cell1.0",{"box_l":385,"box_w":285,"box_h":150,"cell":1.0,"yaw":8,"roll":4,"pitch":4,"scan_vox":1,"method":"voxel"}),
        ("5. voxel_385x285x150_cell2.0",{"box_l":385,"box_w":285,"box_h":150,"cell":2.0,"yaw":8,"roll":4,"pitch":4,"scan_vox":1,"method":"voxel"}),
        ("6. sparrow_385x285x150",      {"box_l":385,"box_w":285,"box_h":150,"cell":0.5,"yaw":8,"roll":4,"pitch":4,"scan_vox":1,"method":"sparrow"}),
    ]

    for name, params in tests:
        print(f"\n── {name} ──")
        r = test(name, params, timeout=180)
        results.append(r)
        # Brief pause between jobs
        time.sleep(1)

    # ── Edge case tests ──
    print("\n── Edge Cases ──")

    # Invalid job ID
    try:
        r = requests.get(f"{BASE}/api/pack/nonexistent-id", timeout=5)
        ok = r.status_code == 404
        results.append({"name": "7. invalid_job_id", "status": "PASS" if ok else "FAIL",
                        "pieces":"—","fill_pct":"—","time_s":"—","collisions":f"HTTP {r.status_code}"})
        print(f"  {'PASS' if ok else 'FAIL'} | invalid_job_id -> HTTP {r.status_code}")
    except Exception as e:
        results.append({"name": "7. invalid_job_id", "status": "FAIL", "error": str(e)})

    # Missing STL
    try:
        r = requests.post(f"{BASE}/api/pack", data={"box_l": 100}, timeout=5)
        ok = r.status_code == 400
        results.append({"name": "8. missing_stl", "status": "PASS" if ok else "FAIL",
                        "pieces":"—","fill_pct":"—","time_s":"—","collisions":f"HTTP {r.status_code}"})
        print(f"  {'PASS' if ok else 'FAIL'} | missing_stl -> HTTP {r.status_code}")
    except Exception as e:
        results.append({"name": "8. missing_stl", "status": "FAIL", "error": str(e)})

    # Job listing
    try:
        r = requests.get(f"{BASE}/api/jobs", timeout=5)
        jd = r.json()
        ok = "jobs" in jd and jd.get("gpu_available") == True
        results.append({"name": "9. job_listing", "status": "PASS" if ok else "FAIL",
                        "pieces":f"total={jd.get('total')}","fill_pct":"—","time_s":"—","collisions":"—"})
        print(f"  {'PASS' if ok else 'FAIL'} | job_listing -> total={jd.get('total')} jobs")
    except Exception as e:
        results.append({"name": "9. job_listing", "status": "FAIL", "error": str(e)})

    # Health final
    try:
        h = requests.get(f"{BASE}/api/health", timeout=5).json()
        ok = h.get("status") == "ok"
        results.append({"name": "10. health_final", "status": "PASS" if ok else "FAIL",
                        "pieces":"—","fill_pct":"—","time_s":"—","collisions":h.get("status","")})
        print(f"  {'PASS' if ok else 'FAIL'} | health_final -> {h}")
    except Exception as e:
        results.append({"name": "10. health_final", "status": "FAIL", "error": str(e)})

    # No crash: rapid submission
    print("\n── No Crash: Rapid Submissions ──")
    try:
        for i in range(3):
            with open(STL, "rb") as f:
                r = requests.post(f"{BASE}/api/pack",
                    files={"stl": f},
                    data={"box_l":50,"box_w":50,"box_h":50,"cell":2.0,"method":"voxel"},
                    timeout=10)
            assert r.status_code == 200
        h2 = requests.get(f"{BASE}/api/health", timeout=5).json()
        ok = h2.get("status") == "ok"
        results.append({"name": "11. no_crash", "status": "PASS" if ok else "FAIL",
                        "pieces":"—","fill_pct":"—","time_s":"—","collisions":"—"})
        print(f"  {'PASS' if ok else 'FAIL'} | no_crash -> health={h2.get('status')}")
    except Exception as e:
        results.append({"name": "11. no_crash", "status": "FAIL", "error": str(e)})

    # ── BENCHMARK TABLE ──
    print("\n")
    print("=" * 110)
    print("  COMPREHENSIVE BENCHMARK RESULTS")
    print("=" * 110)
    print(f"  {'#':<3} {'Test':<35} {'Box':<18} {'Cell':<6} {'Method':<10} {'Pieces':<7} {'Fill%':<9} {'Time(s)':<9} {'Collisions':<14} {'Status':<6}")
    print("  " + "-" * 105)
    for i, r in enumerate(results, 1):
        p = r.get("params", {})
        box = f"{p.get('box_l','')}x{p.get('box_w','')}x{p.get('box_h','')}" if "box_l" in p else "—"
        cell = str(p.get("cell", "—"))
        method = p.get("method", "—")
        pieces = str(r.get("pieces", "—"))
        fill = str(r.get("fill_pct", "—"))
        ts = str(r.get("time_s", "—"))
        coll = str(r.get("collisions", "—"))
        print(f"  {i:<3} {r['name']:<35} {box:<18} {cell:<6} {method:<10} {pieces:<7} {fill:<9} {ts:<9} {coll:<14} {r['status']:<6}")

    passes = sum(1 for r in results if r["status"] == "PASS")
    fails = sum(1 for r in results if r["status"] == "FAIL")
    print("  " + "-" * 105)
    print(f"  TOTAL: {len(results)} tests | {passes} PASS | {fails} FAIL")
    print("=" * 110)

    if fails:
        print("\n  FAILED TESTS:")
        for r in results:
            if r["status"] == "FAIL":
                err = r.get("error", "")
                print(f"    FAIL {r['name']}: {err[:120]}")

if __name__ == "__main__":
    main()
