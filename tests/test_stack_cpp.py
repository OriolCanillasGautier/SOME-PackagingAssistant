import numpy as np, trimesh, ctypes
lib = ctypes.CDLL('/var/www/SOME-PackagingAssistant/physics-engine/stacking/stacking.so')
lib.stack_pieces.restype = ctypes.c_int
lib.stack_pieces.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_int,
    ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.POINTER(ctypes.c_float), ctypes.c_int]
def run(mesh, L,W,H, cell, wt=1.0, maxout=60000):
    v=np.ascontiguousarray(mesh.vertices,dtype=np.float32); f=np.ascontiguousarray(mesh.faces.astype(np.int32),dtype=np.int32)
    out=np.zeros(maxout*7,dtype=np.float32)
    n=lib.stack_pieces(v.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),len(v),
        f.ctypes.data_as(ctypes.POINTER(ctypes.c_int)),len(f), L,W,H, cell, float(wt),
        out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), maxout)
    return n, (out[:n*7].reshape(n,7) if n>0 else np.zeros((0,7)))
cone=trimesh.load('physics-engine/stl/cone.stl', force='mesh')
print("cone dims", np.round(cone.bounds[1]-cone.bounds[0],2), "vol", round(cone.volume,1))
for cell in (1.5, 1.0, 0.5):
    n,pl=run(cone, 50,50,50, cell)   # pass coarse; engine clamps
    ys=pl[:,1] if len(pl) else []
    layers=len(np.unique(np.round(ys,1))) if len(ys) else 0
    print(f"  requested cell={cell}mm: count={n} layers={layers} maxY={ys.max() if len(ys) else 0:.1f}")
