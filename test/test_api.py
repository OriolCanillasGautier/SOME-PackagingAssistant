#!/usr/bin/env python3
"""
Comprehensive GPU Voxel Packing API test suite.
Tests all endpoints, multiple box sizes, cell sizes, and the sparrow method.
"""

import requests
import time
import json
import sys
import os
import io
import trimesh
import numpy as np
from collections import defaultdict

BASE = "http://127.0.0.1:8787"
STL_PATH = os.path.join(os.path.dirname(__file__), "..", "physics-engine", "stl", "part.stl")

# ── helpers ──
def submit_stl(stl_path, box_l, box_w, box_h, cell=0.5, yaw=8, roll=4, pitch=4,
               scan_vox=1, method="voxel"):
    with open(stl_path, "rb") as f:
        resp = requests.post(f"{BASE}/api/pack",
            files={"stl": f},
            data={
                "box_l": box_l, "box_w": box_w, "box_h": box_h,
                "cell": cell, "yaw": yaw, "roll": roll, "pitch": pitch,
                "scan_vox": scan_vox, "method": method,
            },
            timeout=10)
    resp.raise_for_status()
    return resp.json()

def poll_job(job_id, timeout=300, interval=2):
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(f"{BASE}/api/pack/{job_id}", timeout=5)
        data = resp.json()
        status = data.get("status")
        if status in ("done", "error"):
            return data
        time.sleep(interval)
    raise TimeoutError(f"Job {job_id[:8]} did not finish within {timeout}s")

def download_stl(job_id, dest_path):
    resp = requests.get(f"{BASE}/api/pack/{job_id}/stl", timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(resp.content)
    return dest_path

def meshes_collide(a, b, eps=0.001):
    try:
        d = trimesh.proximity.closest_point(a, b.vertices)
        if d is not None and d[1].min() < eps:
            return True
        d = trimesh.proximity.closest_point(b, a.vertices)
        if d is not None and d[1].min() < eps:
            return True
        return False
    except Exception:
        return "error"

def verify_stl_no_collisions(stl_path):
    if stl_path is None:
        return "no_stl"
    mesh = trimesh.load(stl_path, file_type='stl', force='mesh')
    if isinstance(mesh, trimesh.Scene):
        meshes = [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
    else:
        # Need to decompose into pieces somehow — if merged, we can't easily split
        # Just report that we loaded the merged STL
        return "merged_single_mesh"

def verify_placements_no_collisions(placements, stl_path):
    """Load STL, apply each placement transform, check collisions."""
    if stl_path is None or not placements:
        return "no_data"
    try:
        base_mesh = trimesh.load(STL_PATH, file_type='stl', force='mesh')
        if isinstance(base_mesh, trimesh.Scene):
            base_mesh = trimesh.util.concatenate(
                [g for g in base_mesh.geometry.values() if isinstance(g, trimesh.Trimesh)])
    except Exception as e:
        return f"load_error:{e}"

    pieces = []
    for p in placements:
        m = base_mesh.copy()
        rot = np.eye(4)
        rot[:3, :3] = np.array(p["rotation"])
        m.apply_transform(rot)
        m.apply_translation([p["x"], p["y"], p["z"]])
        pieces.append(m)

    collisions = 0
    for i in range(len(pieces)):
        for j in range(i + 1, len(pieces)):
            a, b = pieces[i].bounds, pieces[j].bounds
            if (a[1, 0] > b[0, 0] and a[0, 0] < b[1, 0] and
                a[1, 1] > b[0, 1] and a[0, 1] < b[1, 1] and
                a[1, 2] > b[0, 2] and a[0, 2] < b[1, 2]):
                result = meshes_collide(pieces[i], pieces[j])
                if result == True:
                    collisions += 1
                elif result == "error":
                    return "collision_check_error"

    return "PASS" if collisions == 0 else f"{collisions}_collisions"


# ════════════════════════════════════════════════════════════
# TEST SUITE
# ════════════════════════════════════════════════════════════

RESULTS = []

def record(name, params, result, status="PASS"):
    RESULTS.append({
        "test": name,
        "params": params,
        "result": result,
        "status": status,
    })
    marker = "✓" if status == "PASS" else "✗"
    print(f"  {marker} {name}: {result}")

def main():
    print("=" * 70)
    print("  PackAssist GPU Voxel Packing — Full API Test Suite")
    print("=" * 70)

    # ── 0. Check STL exists ──
    if not os.path.exists(STL_PATH):
        print(f"ERROR: STL not found at {STL_PATH}")
        sys.exit(1)

    stl_size = os.path.getsize(STL_PATH)
    print(f"  STL: {os.path.basename(STL_PATH)} ({stl_size} bytes)")
    print()

    # ── 1. Health check ──
    print("─ 1. Health Endpoint ─")
    try:
        r = requests.get(f"{BASE}/api/health", timeout=5)
        h = r.json()
        record("health", {}, h, "PASS" if h.get("status") == "ok" else "FAIL")
    except Exception as e:
        record("health", {}, str(e), "FAIL")

    # ── 2. Job listing (empty) ─
    print("\n─ 2. Job Listing ─")
    try:
        r = requests.get(f"{BASE}/api/jobs", timeout=5)
        jd = r.json()
        record("job_listing", {}, f"total={jd.get('total')}, jobs={len(jd.get('jobs', []))}", "PASS" if "jobs" in jd else "FAIL")
    except Exception as e:
        record("job_listing", {}, str(e), "FAIL")

    # ── 3. Basic voxel pack (default box) ─
    print("\n─ 3. Default Voxel Pack (385x285x150, cell=0.5) ─")
    try:
        res = submit_stl(STL_PATH, 385, 285, 150, cell=0.5, method="voxel")
        jid = res["job_id"]
        print(f"    Submitted: {jid[:8]}...")
        job = poll_job(jid, timeout=300)
        stl_path = download_stl(jid, f"/tmp/packed_{jid[:8]}.stl")
        collision_result = verify_placements_no_collisions(job.get("placements", []), STL_PATH)
        summary = f"pieces={job['pieces']}, fill={job['fill_pct']}%, time={job['time_s']}s, verified={job['verified']}, collisions={collision_result}"
        st = "PASS" if (job["status"] == "done" and job["pieces"] > 0 and collision_result == "PASS") else "FAIL"
        record("voxel_default", {"box":"385x285x150","cell":0.5}, summary, st)
    except Exception as e:
        record("voxel_default", {"box":"385x285x150","cell":0.5}, str(e), "FAIL")

    # ── 4. Box: 160³ ─
    print("\n─ 4. Box 160³ (cell=0.5) ─")
    try:
        res = submit_stl(STL_PATH, 160, 160, 160, cell=0.5, method="voxel")
        jid = res["job_id"]
        print(f"    Submitted: {jid[:8]}...")
        job = poll_job(jid, timeout=300)
        collision_result = verify_placements_no_collisions(job.get("placements", []), STL_PATH)
        summary = f"pieces={job['pieces']}, fill={job['fill_pct']}%, time={job['time_s']}s, collisions={collision_result}"
        st = "PASS" if job["status"] == "done" and collision_result == "PASS" else "FAIL"
        record("voxel_160cube", {"box":"160x160x160","cell":0.5}, summary, st)
    except Exception as e:
        record("voxel_160cube", {"box":"160x160x160","cell":0.5}, str(e), "FAIL")

    # ── 5. Box: 200³ ─
    print("\n─ 5. Box 200³ (cell=0.5) ─")
    try:
        res = submit_stl(STL_PATH, 200, 200, 200, cell=0.5, method="voxel")
        jid = res["job_id"]
        print(f"    Submitted: {jid[:8]}...")
        job = poll_job(jid, timeout=300)
        collision_result = verify_placements_no_collisions(job.get("placements", []), STL_PATH)
        summary = f"pieces={job['pieces']}, fill={job['fill_pct']}%, time={job['time_s']}s, collisions={collision_result}"
        st = "PASS" if job["status"] == "done" and collision_result == "PASS" else "FAIL"
        record("voxel_200cube", {"box":"200x200x200","cell":0.5}, summary, st)
    except Exception as e:
        record("voxel_200cube", {"box":"200x200x200","cell":0.5}, str(e), "FAIL")

    # ── 6. Box: 385x285x150 ─
    print("\n─ 6. Box 385x285x150 (cell=0.5) ─")
    try:
        res = submit_stl(STL_PATH, 385, 285, 150, cell=0.5, method="voxel")
        jid = res["job_id"]
        print(f"    Submitted: {jid[:8]}...")
        job = poll_job(jid, timeout=300)
        collision_result = verify_placements_no_collisions(job.get("placements", []), STL_PATH)
        summary = f"pieces={job['pieces']}, fill={job['fill_pct']}%, time={job['time_s']}s, collisions={collision_result}"
        st = "PASS" if job["status"] == "done" and collision_result == "PASS" else "FAIL"
        record("voxel_385x285x150", {"box":"385x285x150","cell":0.5}, summary, st)
    except Exception as e:
        record("voxel_385x285x150", {"box":"385x285x150","cell":0.5}, str(e), "FAIL")

    # ── 7. Cell size: 0.5 (already done above) ─
    # ── 8. Cell size: 1.0 ─
    print("\n─ 8. Cell size 1.0 (385x285x150) ─")
    try:
        res = submit_stl(STL_PATH, 385, 285, 150, cell=1.0, method="voxel")
        jid = res["job_id"]
        print(f"    Submitted: {jid[:8]}...")
        job = poll_job(jid, timeout=300)
        collision_result = verify_placements_no_collisions(job.get("placements", []), STL_PATH)
        summary = f"pieces={job['pieces']}, fill={job['fill_pct']}%, time={job['time_s']}s, collisions={collision_result}"
        st = "PASS" if job["status"] == "done" and collision_result == "PASS" else "FAIL"
        record("voxel_cell1.0", {"box":"385x285x150","cell":1.0}, summary, st)
    except Exception as e:
        record("voxel_cell1.0", {"box":"385x285x150","cell":1.0}, str(e), "FAIL")

    # ── 9. Cell size: 2.0 ─
    print("\n─ 9. Cell size 2.0 (385x285x150) ─")
    try:
        res = submit_stl(STL_PATH, 385, 285, 150, cell=2.0, method="voxel")
        jid = res["job_id"]
        print(f"    Submitted: {jid[:8]}...")
        job = poll_job(jid, timeout=300)
        collision_result = verify_placements_no_collisions(job.get("placements", []), STL_PATH)
        summary = f"pieces={job['pieces']}, fill={job['fill_pct']}%, time={job['time_s']}s, collisions={collision_result}"
        st = "PASS" if job["status"] == "done" and collision_result == "PASS" else "FAIL"
        record("voxel_cell2.0", {"box":"385x285x150","cell":2.0}, summary, st)
    except Exception as e:
        record("voxel_cell2.0", {"box":"385x285x150","cell":2.0}, str(e), "FAIL")

    # ── 10. Sparrow method ─
    print("\n─ 10. Sparrow Method (385x285x150) ─")
    try:
        res = submit_stl(STL_PATH, 385, 285, 150, cell=0.5, method="sparrow")
        jid = res["job_id"]
        print(f"    Submitted: {jid[:8]}...")
        job = poll_job(jid, timeout=300)
        collision_result = verify_placements_no_collisions(job.get("placements", []), STL_PATH)
        summary = f"pieces={job['pieces']}, fill={job['fill_pct']}%, time={job['time_s']}s, collisions={collision_result}"
        st = "PASS" if job["status"] == "done" and collision_result == "PASS" else "FAIL"
        record("sparrow_default", {"box":"385x285x150","cell":0.5}, summary, st)
    except Exception as e:
        record("sparrow_default", {"box":"385x285x150","cell":0.5}, str(e), "FAIL")

    # ── 11. Edge cases: invalid job ID ─
    print("\n─ 11. Invalid Job ID ─")
    try:
        r = requests.get(f"{BASE}/api/pack/nonexistent-job-id", timeout=5)
        record("invalid_job_id", {}, f"status={r.status_code}", "PASS" if r.status_code == 404 else "FAIL")
    except Exception as e:
        record("invalid_job_id", {}, str(e), "FAIL")

    # ── 12. Missing STL (POST without file) ─
    print("\n─ 12. POST without STL file ─")
    try:
        r = requests.post(f"{BASE}/api/pack", data={"box_l": 100}, timeout=5)
        record("missing_stl", {}, f"status={r.status_code}, msg={r.json().get('error','')}", "PASS" if r.status_code == 400 else "FAIL")
    except Exception as e:
        record("missing_stl", {}, str(e), "FAIL")

    # ── 13. No crash / hang: submit multiple quick jobs sequentially ─
    print("\n─ 13. Rapid sequential submissions (no crash) ─")
    try:
        for i in range(3):
            res = submit_stl(STL_PATH, 100, 100, 100, cell=2.0, method="voxel")
            # Don't wait for completion, just verify submission works
        r = requests.get(f"{BASE}/api/health", timeout=5)
        record("no_crash_rapid_submit", {}, f"health={r.json()['status']}, active={r.json().get('jobs_active',0)}", "PASS" if r.json()['status'] == 'ok' else "FAIL")
    except Exception as e:
        record("no_crash_rapid_submit", {}, str(e), "FAIL")

    # ── 14. Health check after all tests ─
    print("\n─ 14. Health Endpoint (final) ─")
    try:
        r = requests.get(f"{BASE}/api/health", timeout=5)
        h = r.json()
        record("health_final", {}, h, "PASS" if h.get("status") == "ok" else "FAIL")
    except Exception as e:
        record("health_final", {}, str(e), "FAIL")

    # ── 15. Job listing after all tests ─
    print("\n─ 15. Job Listing (final) ─")
    try:
        r = requests.get(f"{BASE}/api/jobs", timeout=5)
        jd = r.json()
        record("job_listing_final", {}, f"total={jd.get('total')}, done={sum(1 for j in jd.get('jobs',[]) if j['status']=='done')}, running={sum(1 for j in jd.get('jobs',[]) if j['status']=='running')}", "PASS")
    except Exception as e:
        record("job_listing_final", {}, str(e), "FAIL")

    # ── Print summary table ─
    print("\n")
    print("=" * 100)
    print("  BENCHMARK RESULTS TABLE")
    print("=" * 100)
    print(f"{'#':<3} {'Test':<30} {'Box':<20} {'Cell':<8} {'Method':<8} {'Pieces':<8} {'Fill%':<8} {'Time(s)':<8} {'Collisions':<16} {'Status':<6}")
    print("-" * 100)
    for i, r in enumerate(RESULTS, 1):
        params = r.get("params", {})
        result = r.get("result", "")
        box = params.get("box", "—")
        cell = params.get("cell", "—")
        method = params.get("method", "—")
        # Parse result string
        pieces = fill = time_s = collisions = "—"
        if isinstance(result, str) and "pieces=" in result:
            for part in result.split(", "):
                kv = part.split("=", 1)
                if len(kv) == 2:
                    k, v = kv
                    if k == "pieces": pieces = v
                    elif k == "fill": fill = v
                    elif k == "time": time_s = v
                    elif k == "collisions": collisions = v
        elif isinstance(result, dict):
            pieces = str(result.get("pieces", "—"))
            fill = str(result.get("fill_pct", "—"))
            time_s = str(result.get("time_s", "—"))
        print(f"{i:<3} {r['test']:<30} {box:<20} {str(cell):<8} {method:<8} {pieces:<8} {fill:<8} {time_s:<8} {collisions:<16} {r['status']:<6}")

    passes = sum(1 for r in RESULTS if r["status"] == "PASS")
    fails = sum(1 for r in RESULTS if r["status"] == "FAIL")
    print("-" * 100)
    print(f"  TOTAL: {len(RESULTS)} tests | {passes} PASS | {fails} FAIL")
    print("=" * 100)

    if fails:
        print("\n  FAILED TESTS:")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"    ✗ {r['test']}: {r.get('result', '')}")


if __name__ == "__main__":
    main()
