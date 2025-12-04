"""Helpers for STL handling and trimesh-based geometry operations."""
from __future__ import annotations

from typing import Tuple

import numpy as np

STL_SUPPORT = False
try:  # pragma: no cover - optional dependency
    import trimesh  # type: ignore

    _test_mesh = trimesh.creation.box()
    _ = _test_mesh.bounds
    STL_SUPPORT = True
except ImportError:
    trimesh = None  # type: ignore
    STL_SUPPORT = False
except Exception:
    trimesh = None  # type: ignore
    STL_SUPPORT = False


def load_trimesh(path: str):
    """Load an STL/mesh file if trimesh is available."""
    if not STL_SUPPORT or trimesh is None:
        return None
    try:
        mesh = trimesh.load(path, force="mesh")
        if mesh is None or not hasattr(mesh, "vertices"):
            return None
        if getattr(mesh, "is_empty", False):
            return None
        return mesh
    except Exception:
        return None


def canonicalize_to_obb(mesh):
    """Align the mesh to its oriented bounding box (OBB) and move min to origin."""
    m = mesh.copy()
    obb = m.bounding_box_oriented
    transform = obb.primitive.transform
    m.apply_transform(np.linalg.inv(transform))
    mins = m.bounds[0]
    m.apply_translation(-mins)
    extents = tuple(float(e) for e in obb.primitive.extents)
    return np.asarray(m.vertices), np.asarray(m.faces), extents


def perm_matrix(ix: int, iy: int, iz: int) -> np.ndarray:
    mat = np.zeros((3, 3))
    mat[0, ix] = 1.0
    mat[1, iy] = 1.0
    mat[2, iz] = 1.0
    return mat


def apply_permutation(vertices: np.ndarray, perm: Tuple[int, int, int]) -> np.ndarray:
    """Permute vertex axes and re-anchor to the origin."""
    mat = perm_matrix(*perm)
    transformed = (mat @ vertices.T).T
    mins = transformed.min(axis=0)
    return transformed - mins


def guess_perm_for_dims(source_extents: Tuple[float, float, float], target_dims: Tuple[float, float, float]):
    from itertools import permutations

    s = np.array(source_extents)
    t = np.array(target_dims)
    best = (0, 1, 2)
    best_err = float("inf")
    for perm in permutations([0, 1, 2]):
        candidate = s[list(perm)]
        err = float(np.sum((candidate - t) ** 2))
        if err < best_err:
            best_err = err
            best = perm
    return best


def extreure_dimensions_stl(file_path: str) -> Tuple[float, float, float]:
    if not STL_SUPPORT or trimesh is None:
        raise ValueError("Trimesh no està disponible")
    mesh = load_trimesh(file_path)
    if mesh is None or not hasattr(mesh, "bounds"):
        raise ValueError("El fitxer STL no s'ha pogut carregar")
    bounds = mesh.bounds
    if bounds is None or len(bounds) != 2 or len(bounds[0]) != 3:
        raise ValueError("No s'han pogut calcular les dimensions")
    dimensions = bounds[1] - bounds[0]
    if any(dim <= 0 for dim in dimensions):
        raise ValueError("Les dimensions calculades no són vàlides")
    return float(dimensions[0]), float(dimensions[1]), float(dimensions[2])


def processar_stl_upload(stl_file):
    """Process a user-uploaded STL file and return Gradio-friendly outputs."""
    if stl_file is None or not STL_SUPPORT:
        return None, None, None, "No s'ha pujat cap fitxer STL o trimesh no està disponible"
    try:
        stl_l, stl_w, stl_h = extreure_dimensions_stl(stl_file.name)
        return (
            round(stl_l, 2),
            round(stl_w, 2),
            round(stl_h, 2),
            f"✅ Dimensions extretes: {stl_l:.2f}×{stl_w:.2f}×{stl_h:.2f} mm",
        )
    except Exception as exc:
        return None, None, None, f"❌ Error: {exc}"


__all__ = [
    "STL_SUPPORT",
    "apply_permutation",
    "canonicalize_to_obb",
    "extreure_dimensions_stl",
    "guess_perm_for_dims",
    "load_trimesh",
    "perm_matrix",
    "processar_stl_upload",
]
