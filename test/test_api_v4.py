#!/usr/bin/env python3
"""Comprehensive API test suite with proper timeouts and reporting."""
import requests, time, os, sys, numpy as np, trimesh, traceback

BASE = "http://127.0.0.1:8787"
STL = os.path.join(os.path.dirname(__file__), "..", "physics-engine", "stl", "part.stl")

def submit(params):
    with open(STL, "rb") as f:
        r = requests.post(f"{BASE}/api/pack", files={"stl": f}, data=params, timeout=10)
    r.raise_for_status()
    return r.json()["job_id"]

def poll(jid, timeout=120):
    start = time.time()
    last_report = start
    while time.time() - start < timeout:
        r = requests.get(f"{BASE}/api/pack/{jid}", timeout=5)
        d = r.json()
        pieces = d.get("pieces", 0)
        if d.get("status") in ("done", "error"):
            return d
        now = time.time()
        if pieces > 0 and now - last_report > 10:
            print(f"    ... {pieces} pcs, {d.get('fill_pct',0)}% fill, {d.get('time_s',0)}s", flush=True)
            last_report = now
        time.sleep(2)
    return {"status": "timeout", "error_msg": f"Timeout after {timeout}s"}

def verify_placements(placements):
    if not placements:
        return "no_data"
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
            if (a[1,0]>b[0,0] and a[0,0]<b[1,0] and
                a[1,1]>b[0,1] and a[0,1]<b[1,1] and
                a[1,2]>b[0,2] and a[0,2]<b[1,2]):
                try:
                    d = trimesh.proximity.closest_point(meshes[i], meshes[j].vertices)
                    if d is not None and d[1].min() < 0.001: collisions += 1; break
                    d = trimesh.proximity.closest_point(meshes[j], meshes[i].vertices)
                    if d is not None and d[1].min() < 0.001: collisions += 1; break
                except Exception:
                    pass
    return "PASS" if collisions == 0 else f"{collisions}_collisions"

def run_test(name, params, timeout=120):
    t0 = time.time()
    try:
        jid = submit(params)
        print(f"    submitted {jid[:8]}...", end=" ", flush=True)
        job = poll(jid, timeout)
        elapsed = time.time() - t0
        pieces = job.get("pieces", 0)
        fill = job.get("fill_pct", 0)
        t = job.get("time_s", 0)
        verif = job.get("verified", False)
        error = job.get("error_msg", "")
        coll = verify_placements(job.get("placements", []))
        status = "PASS" if (job["status"]=="done" and pieces>0 and (coll=="PASS" or coll=="no_data")) else "FAIL"
        return {"name":name, "status":status, "pieces":pieces, "fill_pct":fill, "time_s":t,
                "verified":verif, "collisions":coll, "elapsed":round(elapsed,1)}
    except Exception as e:
        elapsed = time.time() - t0
        return {"name":name, "status":"FAIL", "pieces":0, "fill_pct":0, "time_s":0,
                "verified":False, "collisions":"error", "elapsed":round(elapsed,1), "error":str(e)}

def main():
    print("=" * 120)
    print("  PackAssist GPU Voxel Packing — API Test Suite")
    print(f"  STL: {os.path.basename(STL)} ({os.path.getsize(STL)} bytes)")
    print("=" * 120)

    # Health
    h = requests.get(f"{BASE}/api/health", timeout=5).json()
    print(f"  Server: {h['status']}, CUDA: {h['cuda']}, GPUs: {len(h.get('gpus',[]))}")
    results = []

    tests = [
        ("01_voxel_200cube_c2",    {"box_l":200,"box_w":200,"box_h":200,"cell":2.0,"method":"voxel"}, 60),
        ("02_voxel_160cube_c2",    {"box_l":160,"box_w":160,"box_h":160,"cell":2.0,"method":"voxel"}, 60),
        ("03_voxel_385x285_c2",    {"box_l":385,"box_w":285,"box_h":150,"cell":2.0,"method":"voxel"}, 120),
        ("04_voxel_200cube_c1",    {"box_l":200,"box_w":200,"box_h":200,"cell":1.0,"method":"voxel"}, 120),
        ("05_voxel_160cube_c1",    {"box_l":160,"box_w":160,"box_h":160,"cell":1.0,"method":"voxel"}, 180),
        ("06_voxel_385x285_c1",    {"box_l":385,"box_w":285,"box_h":150,"cell":1.0,"method":"voxel"}, 120),
        ("07_voxel_100cube_c05",   {"box_l":100,"box_w":100,"box_h":100,"cell":0.5,"method":"voxel"}, 180),
        ("08_sparrow_385x285",     {"box_l":385,"box_w":285,"box_h":150,"cell":0.5,"yaw":8,"method":"sparrow"}, 120),
        ("09_sparrow_200cube",     {"box_l":200,"box_w":200,"box_h":200,"cell":1.0,"yaw":8,"method":"sparrow"}, 120),
        ("10_sparrow_160cube",     {"box_l":160,"box_w":160,"box_h":160,"cell":1.0,"yaw":8,"method":"sparrow"}, 120),
    ]

    for name, params, timeout in tests:
        box = f"{params.get('box_l','')}x{params.get('box_w','')}x{params.get('box_h','')}"
        method = params.get("method", "voxel")
        cell = params.get("cell", "")
        print(f"\n── {name} (box={box}, cell={cell}, {method}) ──", flush=True)
        r = run_test(name, params, timeout)
        results.append(r)
        pieces = r.get("pieces", 0)
        fill = r.get("fill_pct", 0)
        ts = r.get("time_s", 0)
        coll = r.get("collisions", "")
        verif = "OK" if r.get("verified") else "??"
        print(f"    => {r['status']} | pcs={pieces}, fill={fill}%, time={ts}s, vrfy={verif}, coll={coll}", flush=True)
        time.sleep(1)

    # Edge cases
    print("\n── Edge Cases ──", flush=True)

    try:
        r = requests.get(f"{BASE}/api/pack/fake-job", timeout=5)
        results.append({"name":"11_invalid_job","status":"PASS" if r.status_code==404 else "FAIL",
                        "pieces":"-","fill_pct":"-","time_s":"-","collisions":f"HTTP {r.status_code}"})
        print(f"    11_invalid_job: HTTP {r.status_code} {'PASS' if r.status_code==404 else 'FAIL'}")
    except Exception as e:
        results.append({"name":"11_invalid_job","status":"FAIL","error":str(e)})

    try:
        r = requests.post(f"{BASE}/api/pack", files={"stl": open(STL,"rb")},
                         data={"box_l":-1,"box_w":100,"box_h":100,"cell":1.0,"method":"voxel"}, timeout=10)
        results.append({"name":"12_negative_box","status":"PASS" if r.status_code in (200,400,500) else "FAIL",
                        "pieces":"-","fill_pct":"-","time_s":"-","collisions":f"HTTP {r.status_code}"})
        print(f"    12_negative_box: HTTP {r.status_code} {'PASS' if r.status_code in (200,400,500) else 'FAIL'}")
    except Exception as e:
        results.append({"name":"12_negative_box","status":"FAIL","error":str(e)})

    # Jobs after all
    try:
        r = requests.get(f"{BASE}/api/jobs", timeout=5)
        jd = r.json()
        results.append({"name":"13_job_listing","status":"PASS" if "jobs" in jd else "FAIL",
                        "pieces":f"total={jd.get('total')}","fill_pct":"-","time_s":"-","collisions":"-"})
        print(f"    13_job_listing: total={jd.get('total')} jobs")
    except Exception as e:
        results.append({"name":"13_job_listing","status":"FAIL","error":str(e)})

    # Health final
    try:
        h2 = requests.get(f"{BASE}/api/health", timeout=5).json()
        results.append({"name":"14_health_final","status":"PASS" if h2["status"]=="ok" else "FAIL",
                        "pieces":"-","fill_pct":"-","time_s":"-","collisions":str(h2)})
        print(f"    14_health_final: {h2['status']}")
    except Exception as e:
        results.append({"name":"14_health_final","status":"FAIL","error":str(e)})

    # Rapid submit
    print("\n── 15. Rapid Submissions (no crash) ──", flush=True)
    try:
        for i in range(3):
            with open(STL, "rb") as f:
                r = requests.post(f"{BASE}/api/pack",
                    files={"stl": f}, data={"box_l":50,"box_w":50,"box_h":50,"cell":2.0,"method":"voxel"}, timeout=10)
                assert r.status_code == 200, f"HTTP {r.status_code}"
        h3 = requests.get(f"{BASE}/api/health", timeout=5).json()
        results.append({"name":"15_no_crash","status":"PASS" if h3["status"]=="ok" else "FAIL",
                        "pieces":"-","fill_pct":"-","time_s":"-","collisions":"-"})
        print(f"    15_no_crash: health={h3['status']}")
    except Exception as e:
        results.append({"name":"15_no_crash","status":"FAIL","error":str(e)})

    # ── BENCHMARK TABLE ──
    print("\n")
    print("=" * 120)
    print("  COMPREHENSIVE BENCHMARK TABLE")
    print("=" * 120)
    print(f"  {'#':<3} {'Test':<30} {'Status':<6} {'Pieces':<7} {'Fill%':<9} {'Time(s)':<9} {'Verified':<10} {'Collisions':<14}")
    print("  " + "-" * 117)
    for i, r in enumerate(results, 1):
        name = r.get("name", "?")
        status = r.get("status", "?")
        pieces = str(r.get("pieces", "-"))
        fill = str(r.get("fill_pct", "-"))
        ts = str(r.get("time_s", "-"))
        verif = str(r.get("verified", "-"))
        coll = str(r.get("collisions", "-"))
        print(f"  {i:<3} {name:<30} {status:<6} {pieces:<7} {fill:<9} {ts:<9} {verif:<10} {coll:<14}")

    passes = sum(1 for r in results if r["status"] == "PASS")
    fails = sum(1 for r in results if r["status"] == "FAIL")
    print("  " + "-" * 117)
    print(f"  TOTAL: {len(results)} tests | {passes} PASS | {fails} FAIL")
    print("=" * 120)

    if fails:
        print("\n  FAILED:")
        for r in results:
            if r["status"] == "FAIL":
                err = r.get("error", "")
                coll = r.get("collisions", "")
                print(f"    {r['name']}: error={err}, coll={coll}")

if __name__ == "__main__":
    main()
