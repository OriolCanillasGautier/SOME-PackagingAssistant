"""
Server-side stable-orientation analysis for PackAssist.

No physics engine: a pose is stable iff the piece's centre of mass projects
inside the convex hull of its contact points (the vertices touching the
floor) with a real margin, and the contact is a 2D region rather than a
line/point. The 12 proper axis-aligned rotations are tested, so every face
that can rest flat on the floor is found (a cone: base-down AND base-up on
its rim; a brick: all six faces; etc.). Each stable pose is returned as a
quaternion that maps the ORIGINAL mesh to the aligned (resting) pose.
"""

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation


def axis_aligned_rotations():
    """The 12 proper 3D rotations that map the axes onto ±X/±Y/±Z."""
    axes = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    out, seen = [], set()
    for a in axes:
        for b in axes:
            if abs(np.dot(a, b)) > 1e-9:
                continue
            c = tuple(np.cross(a, b))
            R = np.array([a, b, c], dtype=float)
            if abs(np.linalg.det(R) - 1.0) < 1e-9:
                key = tuple(np.round(R).astype(int).flatten())
                if key not in seen:
                    seen.add(key)
                    out.append(R)
    return out


def _point_in_polygon(px, pz, hull_pts):
    """Ray-casting point-in-polygon on the 2D hull (Nx2, ordered)."""
    n = len(hull_pts)
    inside = False
    j = n - 1
    for i in range(n):
        xi, zi = hull_pts[i]
        xj, zj = hull_pts[j]
        if ((zi > pz) != (zj > pz)) and \
           (px < (xj - xi) * (pz - zi) / (zj - zi) + xi):
            inside = not inside
        j = i
    return inside


def _dist_point_segment(px, pz, ax, az, bx, bz):
    vx, vz = bx - ax, bz - az
    wx, wz = px - ax, pz - az
    L2 = vx * vx + vz * vz
    if L2 < 1e-12:
        return np.hypot(wx, wz)
    t = max(0.0, min(1.0, (wx * vx + wz * vz) / L2))
    return np.hypot(px - (ax + t * vx), pz - (az + t * vz))


def _flat_face_clusters(nrm, centroids, areas, normal_tol=0.97, plane_tol_mm=0.8):
    """Cluster triangles into flat regions by normal direction AND
    coplanarity. Returns [{normal, plane_pt, area, idx}] sorted by area —
    every significant flat face of the mesh, whatever its orientation."""
    clusters = []
    for i in range(len(areas)):
        n = nrm[i]
        if not np.all(np.isfinite(n)):
            continue
        c = centroids[i]
        best = -1
        for k, cl in enumerate(clusters):
            # SIGNED dot: opposite-facing triangles (the two sides of a thin
            # wall) must NEVER share a cluster — with abs() they would
            # accumulate and cancel to a zero-length normal (NaN).
            if float(np.dot(n, cl["normal"])) < normal_tol:
                continue
            d = abs(float(np.dot(c - cl["plane_pt"], cl["normal"])))
            if d > plane_tol_mm:
                continue
            best = k
            break
        if best < 0:
            clusters.append({"normal": n.copy(), "plane_pt": c.copy(),
                             "area": 0.0, "idx": []})
            best = len(clusters) - 1
        cl = clusters[best]
        cl["idx"].append(i)
        cl["area"] += float(areas[i])
        w = float(areas[i])
        cl["normal"] = (cl["normal"] + n * w)
        norm = float(np.linalg.norm(cl["normal"]))
        if norm > 1e-12 and np.isfinite(norm):
            cl["normal"] /= norm
        # (a zero-norm accumulation is numerically impossible with the
        # signed-dot constraint above; guard anyway)
        cl["plane_pt"] = (cl["plane_pt"] * len(cl["idx"]) + c) / (len(cl["idx"]) + 1)
    clusters.sort(key=lambda c: -c["area"])
    # A real flat face has near-parallel triangle normals. Curved surfaces
    # (a cone's side) chain facets whose normals fan out — reject those so
    # they never masquerade as resting faces.
    out = []
    for cl in clusters:
        idx = cl["idx"]
        if len(idx) < 3:
            continue
        avg = cl["normal"] / np.linalg.norm(cl["normal"])
        dev = float(np.degrees(np.arccos(
            np.clip(np.abs(nrm[idx] @ avg), -1, 1))).max())
        if dev > 3.0:
            continue
        out.append(cl)
    return out


def analyze_stable_orientations(mesh, band=0.3, verbose=False, min_face_frac=0.002, min_face_area=50.0, relaxed=False):
    """Return the stable resting orientations of a trimesh.

    Two passes:
      * every significant FLAT face of the mesh (any orientation) is tested
        as a resting base — a skewed triangle prism's base, a brick's small
        end, etc.;
      * the 12 axis-aligned rotations catch curved/rim rests (a cone
        standing base-up on its open rim).
    Returns a list of dicts: {quaternion: [x,y,z,w], dims: [l,w,h],
    contactArea, supportArea, shapeRatio, margin}, sorted by contactArea
    descending. The quaternion maps the ORIGINAL mesh to the resting pose.
    """
    verts = mesh.vertices
    faces = mesh.faces
    if verts is None or faces is None or len(faces) == 0:
        return []

    tris = verts[faces]
    e1 = tris[:, 1] - tris[:, 0]
    e2 = tris[:, 2] - tris[:, 0]
    cr = np.cross(e1, e2)
    areas = np.linalg.norm(cr, axis=1) * 0.5
    nrm = cr / np.maximum(areas[:, None] * 2, 1e-12)
    centroids = tris.mean(axis=1)

    try:
        # The VOLUME centroid is what stability needs. For watertight meshes
        # mesh.centroid is exact; for open STL shells it is the surface
        # centroid (badly biased for long prisms) — use the convex hull's
        # volume centroid instead, which is stable for both.
        com_orig = np.asarray(mesh.convex_hull.centroid, dtype=float)
    except Exception:
        try:
            com_orig = np.asarray(mesh.centroid, dtype=float)
        except Exception:
            com_orig = verts.mean(axis=0)
    if not np.all(np.isfinite(com_orig)):
        com_orig = verts.mean(axis=0)

    total_area = float(areas.sum())
    candidates = []   # list of (R, contact_area, cluster_triangle_idx)

    def add_pose(R, contact_area, cl_idx=None):
        candidates.append((np.asarray(R, dtype=float), float(contact_area), cl_idx))

    # ── Pass 1: every significant flat face ──
    clusters = _flat_face_clusters(nrm, centroids, areas)
    # 'Significant' must scale with the part: 1% of total area silently
    # drops every face of a part that is mostly curved (e.g. a 279mm
    # housing whose flat mounting faces are each <1% of the surface).
    # Use a small fraction of the total with an absolute floor (a face
    # smaller than a fingernail is not a resting face anyway).
    min_cluster_area = max(min_face_area, total_area * min_face_frac)
    for cl in clusters:
        if cl["area"] < min_cluster_area:
            continue
        face_n = cl["normal"]
        outward = cl["plane_pt"] - com_orig
        if float(np.dot(outward, face_n)) < 0:
            face_n = -face_n
        R = Rotation.align_vectors([[0, -1, 0]], [face_n])[0].as_matrix()
        add_pose(R, cl["area"], np.asarray(cl["idx"], dtype=int))

    # ── Pass 2: the 12 axis-aligned rotations (curved/rim rests) ──
    for R in axis_aligned_rotations():
        add_pose(R, 0.0)

    # ── Evaluate every candidate pose ──
    results = []
    for R, cl_area, cl_idx in candidates:
        try:
            vr = verts @ R.T
            mn = vr.min(axis=0)
            vr = vr - mn
            vy = vr[:, 1]

            minY = float(vy.min())
            band_top = minY + band

            tri_min_y = vy[faces].min(axis=1)
            tri_max_y = vy[faces].max(axis=1)
            y_span = tri_max_y - tri_min_y
            frac = np.where(y_span < 1e-6, 1.0,
                            np.clip((band_top - tri_min_y) / np.maximum(y_span, 1e-9), 0, 1))
            n_rot_y = (nrm @ R.T)[:, 1]
            contact = (tri_min_y <= band_top) & (n_rot_y < -0.05)
            contact_area = float(np.sum(areas[contact] * (-n_rot_y[contact]) * frac[contact]))

            # Support hull: for a flat-face rest the FULL face is the contact
            # (the band would only catch a sliver of a large face, and the
            # tessellation fragments the face into sub-clusters that each miss
            # the COM). Curved/rim rests use the band vertices.
            if cl_idx is not None and len(cl_idx) >= 3:
                fpts = np.unique(vr[faces[cl_idx]][:, :, [0, 2]].reshape(-1, 2), axis=0)
                if len(fpts) >= 3:
                    try:
                        hull = ConvexHull(fpts)
                        hp = fpts[hull.vertices]
                        contact_area = max(contact_area, cl_area)
                    except Exception:
                        hp = None
                else:
                    hp = None
                if hp is None:
                    continue
            else:
                band_pts = np.unique(vr[vy <= band_top][:, [0, 2]], axis=0)
                if len(band_pts) < 3:
                    continue
                try:
                    hull = ConvexHull(band_pts)
                except Exception:
                    continue
                hp = band_pts[hull.vertices]
            hx = float(hp[:, 0].max() - hp[:, 0].min())
            hz = float(hp[:, 1].max() - hp[:, 1].min())
            shape_ratio = min(hx, hz) / max(1e-6, max(hx, hz))

            com_rot = com_orig @ R.T - mn
            cx, cz = float(com_rot[0]), float(com_rot[2])

            if not _point_in_polygon(cx, cz, hp):
                if verbose:
                    dims_l = (vr.max(axis=0) - vr.min(axis=0))
                    print(f"[Orientations]   reject: COM ({cx:.0f},{cz:.0f}) outside hull "
                          f"dims={np.round(dims_l,1)} hull={hx:.0f}x{hz:.0f} contact={contact_area:.0f}")
                continue
            n_hull = len(hp)
            min_dist = min(
                _dist_point_segment(cx, cz, hp[i, 0], hp[i, 1],
                                    hp[(i + 1) % n_hull, 0], hp[(i + 1) % n_hull, 1])
                for i in range(n_hull))
            margin = min_dist / max(1e-6, max(hx, hz))

            # Strict (default): a real rest needs a decent base. Relaxed (opted
            # in via the "possible orientations" toggle): surface the marginal
            # candidates too — narrow-but-long bases (a plate on its edge), and
            # borderline rests — which the client labels "Possible".
            if relaxed:
                if contact_area < 0.1 or shape_ratio < 0.03 or margin < 0.001:
                    continue
            elif contact_area < 1.0 or shape_ratio < 0.2 or margin < 0.02:
                continue

            dims = vr.max(axis=0) - vr.min(axis=0)
            quat = Rotation.from_matrix(R).as_quat()   # [x, y, z, w]
            results.append({
                "quaternion": [float(q) for q in quat],
                "dims": [float(d) for d in dims],
                "contactArea": round(contact_area, 2),
                "shapeRatio": round(shape_ratio, 3),
                "margin": round(margin, 3),
                "_R": R,
            })
        except Exception:
            # A single degenerate candidate must never kill the whole
            # analysis (the other 11+ poses are still valid).
            continue

    # Dedup by the resting face: the original-frame direction that the pose
    # aligned to -Y = -R[1] (the negated second row of R).
    dedup, seen = [], []
    for r in sorted(results, key=lambda x: -x["contactArea"]):
        d = -r["_R"][1]
        if any(np.degrees(np.arccos(np.clip(np.dot(d, s), -1, 1))) < 15 for s in seen):
            continue
        seen.append(d)
        rr = dict(r)
        rr.pop("_R")
        dedup.append(rr)
    if verbose:
        print(f"[Orientations] {len(results)} candidates -> {len(dedup)} unique stable poses")
    return dedup
