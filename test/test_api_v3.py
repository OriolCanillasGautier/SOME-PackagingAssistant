#!/usr/bin/env python3
"""Focused GPU Voxel Packing API test suite."""
import requests, time, json, sys, os, numpy as np, trimesh

BASE = "http://127.0.0.1:8787"
STL = os.path.join(os.path.dirname(__file__), "..", "physics-engine", "stl", "part.stl")

def submit(params):
    with open(STL, "rb") as f:
        r = requests.post(f"{BASE}/api/pack", files={"stl": f}, data=params, timeout=10)
    r.raise_for_status()
    return r.json()["job_id"]

def poll(jid, timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{BASE}/api/pack/{jid}", timeout=5)
        d = r.json()
        if d.get("status") in ("done", "error"):
            return d
        time.sleep(2)
    return {"status": "timeout", "error_msg": f"Timeout after {timeout}s"}

def verify_placements(placements):
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
        rot[:3,:3] = np.array(p["rotation"])
        m.apply_transform(rot)
        m.apply_translation([p["x"], p["y"], p["z"]])
        meshes.append(m)
    collisions = 0
    for i in range(len(meshes)):
        for j in range(i+1, len(meshes)):
            a,b = meshes[i].bounds, meshes[j].bounds
            if (a[1,0]>b[0,0] and a[0,0]<b[1,0] and a[1,1]>b[0,1] and a[0,1]<b[1,1] and a[1,2]>b[0,2] and a[0,2]<b[1,2]):
                try:
                    d = trimesh.proximity.closest_point(meshes[i], meshes[j].vertices)
                    if d is not None and d[1].min() < 0.001: collisions += 1; break
                    d = trimesh.proximity.closest_point(meshes[j], meshes[i].vertices)
                    if d is not None and d[1].min() < 0.001: collisions += 1; break
                except: pass
    return "PASS" if collisions == 0 else f"{collisions}_collisions"

def run_test(name, params, timeout=180):
    t0 = time.time()
    try:
        jid = submit(params)
        job = poll(jid, timeout)
        elapsed = time.time() - t0
        pieces = job.get("pieces", 0)
        fill = job.get("fill_pct", 0)
        t = job.get("time_s", 0)
        verif = job.get("verified", False)
        coll = verify_placements(job.get("placements", []))
        status = "PASS" if (job["status"]=="done" and pieces>0 and coll=="PASS") else "FAIL"
        box = f'{params.get("box_l")}x{params.get("box_w")}x{params.get("box_h")}'
        print(f"  {'PASS' if status=='PASS' else 'FAIL'} | {name:<32} | box={box:<18} | cell={params.get('cell','-'):<4} | {params.get('method','voxel'):<8} | pcs={pieces:<5} | fill={str(fill)+'%':<9} | {str(t)+'s':<9} | coll={coll}")
        return {"name":name, "status":status, "pieces":pieces, "fill_pct":fill, "time_s":t,
                "verified":verif, "collisions":coll, "elapsed":round(elapsed,1)}
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  FAIL | {name:<32} | ERROR: {str(e)[:80]}")
        return {"name":name, "status":"FAIL", "pieces":0, "fill_pct":0, "time_s":0,
                "verified":False, "collisions":"error", "elapsed":round(elapsed,1), "error":str(e)}

def main():
    print("=" * 115)
    print("  PackAssist API Comprehensive Test Suite")
    print(f"  STL: {os.path.basename(STL)} ({os.path.getsize(STL)} bytes)")
    print("=" * 115)

    # Health check
    try:
        h = requests.get(f"{BASE}/api/health", timeout=5).json()
        print(f"  Server: {h['status']} | CUDA: {h['cuda']} | GPUs: {len(h.get('gpus',[]))} | Jobs active: {h.get('jobs_active',0)}")
    except Exception as e:
        print(f"  SERVER OFFLINE: {e}")
        sys.exit(1)

    results = []

    # ── 1. Voxel: 160³, cell=1.0 ──
    print("\n── 1. Voxel 160³ cell=1.0 ──")
    results.append(run_test("1_voxel_160cube_c1", {"box_l":160,"box_w":160,"box_h":160,"cell":1.0,"method":"voxel"}, 180))
    time.sleep(1)

    # ── 2. Voxel: 200³, cell=1.0 ──
    print("\n── 2. Voxel 200³ cell=1.0 ──")
    results.append(run_test("2_voxel_200cube_c1", {"box_l":200,"box_w":200,"box_h":200,"cell":1.0,"method":"voxel"}, 180))
    time.sleep(1)

    # ── 3. Voxel: 385x285x150, cell=1.0 ──
    print("\n── 3. Voxel 385x285x150 cell=1.0 ──")
    results.append(run_test("3_voxel_385x285_c1", {"box_l":385,"box_w":285,"box_h":150,"cell":1.0,"method":"voxel"}, 180))
    time.sleep(1)

    # ── 4. Voxel: 385x285x150, cell=2.0 ──
    print("\n── 4. Voxel 385x285x150 cell=2.0 ──")
    results.append(run_test("4_voxel_385x285_c2", {"box_l":385,"box_w":285,"box_h":150,"cell":2.0,"method":"voxel"}, 180))
    time.sleep(1)

    # ── 5. Voxel: 200³, cell=2.0 ──
    print("\n── 5. Voxel 200³ cell=2.0 ──")
    results.append(run_test("5_voxel_200cube_c2", {"box_l":200,"box_w":200,"box_h":200,"cell":2.0,"method":"voxel"}, 180))
    time.sleep(1)

    # ── 6. Voxel: 160³, cell=2.0 ──
    print("\n── 6. Voxel 160³ cell=2.0 ──")
    results.append(run_test("6_voxel_160cube_c2", {"box_l":160,"box_w":160,"box_h":160,"cell":2.0,"method":"voxel"}, 180))
    time.sleep(1)

    # ── 7. Voxel: 385x285x150, cell=0.5 (coarse: reduce yaw/roll/pitch) ──
    print("\n── 7. Voxel 385x285x150 cell=0.5 (fast: yaw=4,roll=2,pitch=2) ──")
    results.append(run_test("7_voxel_385x285_c05", {"box_l":385,"box_w":285,"box_h":150,"cell":0.5,"yaw":4,"roll":2,"pitch":2,"method":"voxel"}, 180))
    time.sleep(1)

    # ── 8. Sparrow: 385x285x150 ──
    print("\n── 8. Sparrow 385x285x150 cell=0.5 ──")
    results.append(run_test("8_sparrow_385x285", {"box_l":385,"box_w":285,"box_h":150,"cell":0.5,"yaw":8,"method":"sparrow"}, 180))
    time.sleep(1)

    # ── 9. Sparrow: 200³ ──
    print("\n── 9. Sparrow 200³ cell=1.0 ──")
    results.append(run_test("9_sparrow_200cube", {"box_l":200,"box_w":200,"box_h":200,"cell":1.0,"yaw":8,"method":"sparrow"}, 180))
    time.sleep(1)

    # ── Edge Cases ──
    print("\n── Edge Cases ──")

    # Invalid job
    r = requests.get(f"{BASE}/api/pack/fake-job-id", timeout=5)
    results.append({"name":"10_invalid_job","status":"PASS" if r.status_code==404 else "FAIL",
                    "pieces":"-","fill_pct":"-","time_s":"-","collisions":f"HTTP {r.status_code}"})
    print(f"  {'PASS' if r.status_code==404 else 'FAIL'} | 10_invalid_job -> HTTP {r.status_code}")

    # Missing STL
    r = requests.post(f"{BASE}/api/pack", data={"box_l":100}, timeout=5)
    results.append({"name":"11_missing_stl","status":"PASS" if r.status_code==400 else "FAIL",
                    "pieces":"-","fill_pct":"-","time_s":"-","collisions":f"HTTP {r.status_code}:{r.json().get('error','')}"})
    print(f"  {'PASS' if r.status_code==400 else 'FAIL'} | 11_missing_stl -> HTTP {r.status_code}")

    # Job listing
    r = requests.get(f"{BASE}/api/jobs", timeout=5)
    jd = r.json()
    results.append({"name":"12_job_listing","status":"PASS" if "jobs" in jd else "FAIL",
                    "pieces":f"total={jd.get('total')}","fill_pct":"-","time_s":"-","collisions":"-"})
    print(f"  {'PASS' if 'jobs' in jd else 'FAIL'} | 12_job_listing -> total={jd.get('total')} jobs")

    # Health
    r = requests.get(f"{BASE}/api/health", timeout=5)
    h = r.json()
    results.append({"name":"13_health_final","status":"PASS" if h["status"]=="ok" else "FAIL",
                    "pieces":"-","fill_pct":"-","time_s":"-","collisions":f"ok, cuda={h['cuda']}"})
    print(f"  {'PASS' if h['status']=='ok' else 'FAIL'} | 13_health_final -> {h}")

    # Rapid submit (no crash)
    print("\n── 14. Rapid Submissions (no crash) ──")
    try:
        for i in range(3):
            r = requests.post(f"{BASE}/api/pack",
                files={"stl": open(STL,"rb")},
                data={"box_l":50,"box_w":50,"box_h":50,"cell":2.0,"method":"voxel"},
                timeout=10)
        r.raise_for_status()
        h2 = requests.get(f"{BASE}/api/health", timeout=5).json()
        ok = h2["status"] == "ok"
        results.append({"name":"14_no_crash","status":"PASS" if ok else "FAIL",
                        "pieces":"-","fill_pct":"-","time_s":"-","collisions":"-"})
        print(f"  {'PASS' if ok else 'FAIL'} | 14_no_crash -> health={h2['status']}")
    except Exception as e:
        results.append({"name":"14_no_crash","status":"FAIL","error":str(e)})
        print(f"  FAIL | 14_no_crash -> {e}")

    # ── BENCHMARK TABLE ──
    print("\n")
    print("=" * 115)
    print("  COMPREHENSIVE BENCHMARK RESULTS")
    print("=" * 115)
    hdr = f"  {'#':<3} {'Test':<32} {'Box':<18} {'Cell':<6} {'Method':<10} {'Pieces':<7} {'Fill%':<9} {'Time(s)':<9} {'Collisions':<14} {'Status':<6}"
    print(hdr)
    print("  " + "-" * 112)
    for i, r in enumerate(results, 1):
        pieces = str(r.get("pieces", "-"))
        fill = str(r.get("fill_pct", "-"))
        ts = str(r.get("time_s", "-"))
        coll = str(r.get("collisions", "-"))
        box = r.get("name", "").split("_")[1] if "_" in r.get("name", "") else "-"
        # Try to extract params from name
        name = r["name"]
        print(f"  {i:<3} {name:<32} {r.get('params_box',''):<18} {'':<6} {'':<10} {pieces:<7} {fill:<9} {ts:<9} {coll:<14} {r['status']:<6}")

    passes = sum(1 for r in results if r["status"] == "PASS")
    fails = sum(1 for r in results if r["status"] == "FAIL")
    print("  " + "-" * 112)
    print(f"  TOTAL: {len(results)} tests | {passes} PASS | {fails} FAIL")
    print("=" * 115)

    if fails:
        print("\n  FAILED:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"    {r['name']}: {r.get('error','')}")

if __name__ == "__main__":
    main()
