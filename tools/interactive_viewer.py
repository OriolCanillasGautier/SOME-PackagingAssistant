#!/usr/bin/env python3
import argparse
import json
import os
import sys

try:
    import numpy as np
except Exception:
    print("[viewer] numpy is required", file=sys.stderr)
    sys.exit(1)

# Optional deps
TRIMESH_SUPPORT = False
try:
    import trimesh
    TRIMESH_SUPPORT = True
except Exception:
    TRIMESH_SUPPORT = False

try:
    import pyvista as pv
except Exception as e:
    print(f"[viewer] pyvista is required: {e}", file=sys.stderr)
    sys.exit(1)

# Helpers for STL alignment
import numpy as _np

def _load_trimesh(path: str):
    if not TRIMESH_SUPPORT:
        return None
    try:
        m = trimesh.load(path, force='mesh')
        if m is None or not hasattr(m, 'vertices'):
            return None
        if hasattr(m, 'is_empty') and m.is_empty:
            return None
        return m
    except Exception:
        return None


def _canonicalize_to_obb(mesh):
    m = mesh.copy()
    obb = m.bounding_box_oriented
    T = obb.primitive.transform
    m.apply_transform(_np.linalg.inv(T))
    mins = m.bounds[0]
    m.apply_translation(-mins)
    extents = tuple(float(e) for e in obb.primitive.extents)
    return _np.asarray(m.vertices), _np.asarray(m.faces), extents


def _perm_matrix(ix: int, iy: int, iz: int):
    M = _np.zeros((3,3))
    M[0, ix] = 1.0
    M[1, iy] = 1.0
    M[2, iz] = 1.0
    return M


def _apply_permutation(V: _np.ndarray, perm):
    M = _perm_matrix(*perm)
    V2 = (M @ V.T).T
    mins = V2.min(axis=0)
    return V2 - mins


def _guess_perm_for_dims(source_extents, target_dims):
    from itertools import permutations
    s = _np.array(source_extents)
    t = _np.array(target_dims)
    best = (0,1,2)
    best_err = 1e18
    for perm in permutations([0,1,2]):
        cand = s[list(perm)]
        err = float(_np.sum((_np.array(cand) - t)**2))
        if err < best_err:
            best_err = err
            best = perm
    return best


def build_scene(plotter, box_dims, piece_dims, distribution, stl_path=None, use_stl=False):
    bl, bw, bh = box_dims
    pl, pw, ph = piece_dims
    nx, ny, nz = distribution

    plotter.set_background("black")
    try:
        plotter.enable_anti_aliasing()
    except Exception:
        pass

    # Container wireframe
    box = pv.Cube(center=(bl/2, bw/2, bh/2), x_length=bl, y_length=bw, z_length=bh)
    plotter.add_mesh(box, style='wireframe', color='#22c55e', line_width=3, name='box')

    # STL preload if requested
    stl_mesh_pv = None
    if use_stl and stl_path and os.path.exists(stl_path) and TRIMESH_SUPPORT:
        tm = _load_trimesh(stl_path)
        if tm is not None:
            try:
                V, F, ext = _canonicalize_to_obb(tm)
                perm = _guess_perm_for_dims(ext, piece_dims)
                V = _apply_permutation(V, perm)
                faces = _np.hstack([_np.full((F.shape[0],1), 3, dtype=_np.int64), F]).ravel()
                stl_mesh_pv = pv.PolyData(V, faces)
            except Exception:
                stl_mesh_pv = None

    total_units = nx * ny * nz
    draw_limit = min(total_units, 300)
    drawn = 0
    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                if drawn >= draw_limit:
                    break
                x0, y0, z0 = ix * pl, iy * pw, iz * ph
                if stl_mesh_pv is not None and total_units <= 120:
                    part = stl_mesh_pv.copy(deep=True)
                    part.translate((x0, y0, z0), inplace=True)
                    plotter.add_mesh(part, color="#3b82f6", specular=0.2, smooth_shading=True, show_edges=True)
                else:
                    cube = pv.Cube(center=(x0 + pl/2, y0 + pw/2, z0 + ph/2), x_length=pl, y_length=pw, z_length=ph)
                    plotter.add_mesh(cube, color="#3b82f6", opacity=0.95, show_edges=True)
                drawn += 1
            if drawn >= draw_limit:
                break
        if drawn >= draw_limit:
            break

    plotter.add_axes()
    try:
        plotter.camera_position = 'iso'
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True, help='Path to JSON scene description')
    args = parser.parse_args()

    with open(args.data, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    box_dims = tuple(cfg.get('box_dims', [100,100,100]))
    piece_dims = tuple(cfg.get('piece_dims', [10,10,10]))
    distribution = tuple(cfg.get('distribution', [1,1,1]))
    stl_path = cfg.get('stl_path', None)
    use_stl = bool(cfg.get('use_stl', False))
    title = cfg.get('title', 'PackAssist - Visor 3D')

    # Try BackgroundPlotter first if available to keep UI responsive
    try:
        import pyvistaqt as pvqt
        plotter = pvqt.BackgroundPlotter(title=title, window_size=(1200, 900), show=True)
        build_scene(plotter, box_dims, piece_dims, distribution, stl_path, use_stl)
        if hasattr(plotter, 'app'):
            plotter.app.exec_()
        else:
            # Fallback idle loop
            import time
            while plotter.app_window.isVisible():
                time.sleep(0.1)
        return
    except Exception:
        pass

    # Fallback to standard Plotter (blocking in this separate process)
    p = pv.Plotter(window_size=(1200, 900))
    p.add_title(title)
    build_scene(p, box_dims, piece_dims, distribution, stl_path, use_stl)
    p.show(interactive=True, auto_close=False)


if __name__ == '__main__':
    main()
