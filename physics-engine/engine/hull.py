"""
hull.py — CPU convex hull generation from trimesh meshes.

Uses scipy.spatial.ConvexHull to compute convex hulls from arbitrary
triangle meshes. Results are cached and reusable across engine operations.
"""
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np


@dataclass
class HullData:
    vertices: np.ndarray      # (N, 3) float64  — hull vertices in local space
    faces: np.ndarray         # (M, 3) int32    — triangle indices
    normals: np.ndarray       # (M, 3) float64  — face normals (unit length)
    aabb_min: np.ndarray      # (3,) float64
    aabb_max: np.ndarray      # (3,) float64
    name: str = ""
    _volume: float = 0.0

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    @property
    def face_count(self) -> int:
        return len(self.faces)

    @property
    def aabb(self):
        return self.aabb_min, self.aabb_max

    @property
    def extents(self) -> np.ndarray:
        return self.aabb_max - self.aabb_min

    @property
    def volume(self) -> float:
        if self._volume > 0:
            return self._volume
        return convex_hull_volume(self.vertices, self.faces)

    def transform(self, R: np.ndarray, t: np.ndarray) -> "HullData":
        v = self.vertices @ R.T + t
        n = self.normals @ R.T
        return HullData(
            vertices=v,
            faces=self.faces.copy(),
            normals=n,
            aabb_min=v.min(axis=0),
            aabb_max=v.max(axis=0),
            name=self.name,
        )


def compute_hull(mesh: "trimesh.Trimesh", name: str = "") -> HullData:
    from scipy.spatial import ConvexHull
    pts = np.asarray(mesh.vertices, dtype=np.float64)
    hull = ConvexHull(pts)
    verts = pts[hull.vertices]
    # Remap simplices: old indices → new 0..N-1 indices
    old_to_new = {old: new for new, old in enumerate(hull.vertices)}
    faces = np.array([[old_to_new[i] for i in s] for s in hull.simplices], dtype=np.int32)
    aabb_min = verts.min(axis=0).astype(np.float64).copy()
    aabb_max = verts.max(axis=0).astype(np.float64).copy()
    normals = _compute_face_normals(verts, faces)
    # Fix face winding: all normals should point outward
    center = verts.mean(axis=0)
    for i, f in enumerate(faces):
        v0, v1, v2 = verts[f[0]], verts[f[1]], verts[f[2]]
        centroid = (v0 + v1 + v2) / 3.0
        if np.dot(normals[i], centroid - center) < 0:
            faces[i] = [f[0], f[2], f[1]]  # flip winding
            normals[i] = -normals[i]
    return HullData(
        vertices=verts,
        faces=faces,
        normals=normals,
        aabb_min=aabb_min,
        aabb_max=aabb_max,
        name=name,
        _volume=float(hull.volume),
    )


def hull_from_stl(path: str | Path, name: str = "") -> HullData:
    import trimesh
    fp = Path(path)
    mesh = trimesh.load(str(fp), force="mesh")
    if isinstance(mesh, trimesh.Scene):
        geom = [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not geom:
            raise ValueError(f"No triangle meshes in {fp}")
        mesh = trimesh.util.concatenate(geom)
    if name:
        pass
    else:
        name = fp.stem
    return compute_hull(mesh, name)


def _compute_face_normals(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    e1 = v1 - v0
    e2 = v2 - v0
    n = np.cross(e1, e2)
    mag = np.linalg.norm(n, axis=1)
    mag[mag < 1e-12] = 1.0
    return n / mag[:, np.newaxis]


def convex_hull_volume(verts: np.ndarray, faces: np.ndarray) -> float:
    """Compute convex hull volume by summing signed tetrahedra from an interior point."""
    if len(verts) == 0 or len(faces) == 0:
        return 0.0
    # Use centroid as interior reference point
    ref = np.mean(verts, axis=0)
    total = 0.0
    for f in faces:
        v0 = verts[f[0]] - ref
        v1 = verts[f[1]] - ref
        v2 = verts[f[2]] - ref
        total += np.dot(v0, np.cross(v1, v2))
    return float(abs(total) / 6.0)
