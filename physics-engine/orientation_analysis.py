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


def _flat_face_clusters(nrm, centroids, areas, normal_tol=0.97, plane_tol_mm=0.8,
                        max_faces=60000):
    """Cluster triangles into flat regions by normal direction AND
    coplanarity. Returns [{normal, plane_pt, area, idx}] sorted by area —
    every significant flat face of the mesh, whatever its orientation.

    VECTORISED: the old implementation scanned every face against every
    cluster in interpreted Python (O(N x C)); on a 150k-triangle part that took
    minutes, which blew the web client's 45s /api/orientations timeout so the
    UI silently fell back to a single pose. Now the biggest faces seed clusters
    and each cluster claims all matching faces in one numpy pass (O(C x N),
    C is tiny). Faces beyond `max_faces` (by area) are dropped first: a flat
    resting face is made of LARGE triangles, so tessellation noise is what gets
    discarded.
    """
    n = len(areas)
    if n == 0:
        return []
    finite = np.isfinite(nrm).all(axis=1)
    order = np.argsort(-areas)
    if n > max_faces:
        order = order[:max_faces]
    unassigned = np.zeros(n, dtype=bool)
    unassigned[order] = finite[order]

    clusters = []
    refined = 0
    for i in order:
        if not unassigned[i]:
            continue
        seed_n = nrm[i]
        seed_c = centroids[i]
        m = unassigned & (nrm @ seed_n >= normal_tol) \
                      & (np.abs((centroids - seed_c) @ seed_n) <= plane_tol_mm)
        # Refine the cluster normal to the area-weighted mean of its members
        # and re-select (a face may chain onto a slightly tilted neighbour),
        # exactly like the incremental average did before. ONLY for the first
        # few clusters: `order` is descending-area, so those are the big faces
        # we actually use, while the long tail (hundreds of tiny clusters on a
        # detailed part) skips the extra full-mesh passes — that refinement
        # was the 30s bottleneck on a 103k-triangle part.
        if refined < 40:
            refined += 1
            for _ in range(3):
                w = areas[m]
                if w.sum() <= 0:
                    break
                avg = (nrm[m] * w[:, None]).sum(axis=0)
                ln = float(np.linalg.norm(avg))
                if ln < 1e-12:
                    break
                avg = avg / ln
                m2 = unassigned & (nrm @ avg >= normal_tol) \
                              & (np.abs((centroids - seed_c) @ avg) <= plane_tol_mm)
                if m2.sum() == m.sum():
                    m = m2
                    break
                m = m2
        idx = np.flatnonzero(m)
        if idx.size == 0:
            unassigned[i] = False
            continue
        w = areas[idx]
        avg = (nrm[idx] * w[:, None]).sum(axis=0)
        ln = float(np.linalg.norm(avg))
        avg = avg / ln if ln > 1e-12 else seed_n
        clusters.append({
            "normal": avg,
            "plane_pt": (centroids[idx] * w[:, None]).sum(axis=0) / max(float(w.sum()), 1e-12),
            "area": float(w.sum()),
            "idx": idx,
        })
        unassigned[idx] = False

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


def analyze_stable_orientations(mesh, band=0.3, verbose=False, min_face_frac=0.002, min_face_area=20.0, relaxed=False):
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
        # mesh.centroid is the exact mass-centroid; the convex-hull centroid is
        # only the ENVELOPE centre, which is wrong for a hollow/irregular part
        # (its actual mass is off-centre) and wrongly rejected stable poses as
        # "COM outside hull". Use the true volume centroid when we have a
        # watertight mesh, and only fall back to the hull centroid for open STL
        # shells (where mesh.centroid is a surface-biased approximation).
        if getattr(mesh, 'is_watertight', False):
            com_orig = np.asarray(mesh.centroid, dtype=float)
        else:
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
    # Cap the flat-face candidates: each one costs a full-mesh rotation plus a
    # support-hull test, and a detailed part yields hundreds of small clusters.
    # `clusters` is already sorted by area descending, so the biggest faces win.
    MAX_FLAT_CANDIDATES = 24
    flat_used = 0
    for cl in clusters:
        if cl["area"] < min_cluster_area:
            continue
        if flat_used >= MAX_FLAT_CANDIDATES:
            break
        flat_used += 1
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
                    # A degenerate/co-linear footprint ConvexHull shouldn't drop
                    # the pose entirely (that's why complex parts showed 0
                    # orientations). Fall back to the footprint's bounding box as
                    # the support hull; the client gravity-run decides real
                    # stability, so we only need a non-empty support here.
                    if len(fpts) >= 3:
                        hp = np.array([[fpts[:, 0].min(), fpts[:, 1].min()],
                                       [fpts[:, 0].max(), fpts[:, 1].min()],
                                       [fpts[:, 0].max(), fpts[:, 1].max()],
                                       [fpts[:, 0].min(), fpts[:, 1].max()]], dtype=float)
                    else:
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

            n_hull = len(hp)
            inside = _point_in_polygon(cx, cz, hp)
            min_dist = min(
                _dist_point_segment(cx, cz, hp[i, 0], hp[i, 1],
                                    hp[(i + 1) % n_hull, 0], hp[(i + 1) % n_hull, 1])
                for i in range(n_hull))
            margin = min_dist / max(1e-6, max(hx, hz))
            # Signed: positive if COM inside the support hull, negative outside.
            signed_margin = margin if inside else -margin

            # Two tiers, surfacing ALL plausible poses while labelling honestly:
            #   stable   → a genuine resting base (roomy, level, COM well inside).
            #   possible → a marginal rest — a rim/edge/thin base, or a pose the
            #               part balances on (COM at/slightly beyond the support
            #               edge). The strict COM-in-hull check was dropping every
            #               pose except 1-2 for off-centre parts, so we surface
            #               edge-balanced rests here (labelled "Possible"). Reject
            #               only when the COM is clearly beyond the support.
            # Propose generously: surface EVERY candidate pose (even marginal /
            # off-centre ones, up to the COM being half-way beyond the support).
            # The client gravity-run decides true stability, so the server just
            # proposes a broad, honest set — it no longer silently drops a part
            # to 0-1 poses just because its mass is off-centre.
            possible = not (contact_area < 0.05 or shape_ratio < 0.02 or signed_margin < -0.5)
            stable = not (contact_area < 1.0 or shape_ratio < 0.2 or signed_margin < 0.02)
            if not possible:
                continue

            dims = vr.max(axis=0) - vr.min(axis=0)
            quat = Rotation.from_matrix(R).as_quat()   # [x, y, z, w]
            results.append({
                "quaternion": [float(q) for q in quat],
                "dims": [float(d) for d in dims],
                "contactArea": round(contact_area, 2),
                "shapeRatio": round(shape_ratio, 3),
                "margin": round(margin, 3),
                "stable": bool(stable),
                "_R": R,
            })
        except Exception:
            # A single degenerate candidate must never kill the whole
            # analysis (the other 11+ poses are still valid).
            continue

    # Dedup by the resting face: the original-frame direction that the pose
    # aligned to -Y = -R[1] (the negated second row of R).
    #
    # MIRROR merge: a symmetric part resting on the +face vs the -face of the
    # SAME face pair is the same physical rest, so those merge — but ONLY when
    # they share the same AXIS. The previous rule merged on (sorted dims +
    # contact area) alone, which collapsed a CUBE's six faces into a single
    # card (every face has identical dims and area) and hid genuinely
    # different orientations of asymmetric parts.
    dedup, seen_dir, seen_key = [], [], []
    for r in sorted(results, key=lambda x: -x["contactArea"]):
        d = -r["_R"][1]
        k = tuple(sorted(round(v, 1) for v in r["dims"]))
        dup = any(np.degrees(np.arccos(np.clip(np.dot(d, s), -1, 1))) < 15 for s in seen_dir)
        if not dup:
            for (sdir, sk, sc) in seen_key:
                same_axis = abs(float(np.dot(d, sdir))) > 0.97
                if (same_axis
                        and abs(k[0]-sk[0]) < 0.6 and abs(k[1]-sk[1]) < 0.6 and abs(k[2]-sk[2]) < 0.6
                        and abs(r["contactArea"] - sc) < 0.10 * max(1.0, sc)):
                    dup = True
                    break
        if dup:
            continue
        seen_dir.append(d)
        seen_key.append((d, k, r["contactArea"]))
        rr = dict(r)
        rr.pop("_R")
        dedup.append(rr)
    if verbose:
        print(f"[Orientations] {len(results)} candidates -> {len(dedup)} unique stable poses")
    return dedup
