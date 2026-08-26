import sys, numpy as np, trimesh
sys.path.insert(0, 'physics-engine')
from orientation_analysis import analyze_stable_orientations
TF = trimesh.transformations
def dims(t): return np.round(t.bounds[1]-t.bounds[0],1)

# 1) The real hollow test cone -> MUST give exactly 1 (open-rim rest)
cone = trimesh.load('physics-engine/stl/cone.stl', force='mesh')
p = analyze_stable_orientations(cone, verbose=False)
print(f"CONE -> {len(p)} orientations (want 1)")
for q in p:
    mq = TF.quaternion_matrix(np.array(q['quaternion']))
    print("   dims", dims(cone.copy().apply_transform(mq)), "area", q['contactArea'], "margin", q['margin'], "shape", q['shapeRatio'])

# 2) Solid box -> 6
box = trimesh.creation.box(extents=[100,258,95])
print("\nSOLID BOX ->", len(analyze_stable_orientations(box, verbose=False)), "(want 6)")

# 3) Bowed near-flat plate -> Pass 3 should recover the bowed-face horizontal rest
L,T,W = 120.0,4.0,60.0
plate = trimesh.creation.box(extents=[L,T,W])
v = plate.vertices.copy()
# slight cylindrical bow so the top/bottom normals vary up to ~6deg (fails coplanarity)
xn = (v[:,0]-v[:,0].min())/(v[:,0].max()-v[:,0].min())
v[:,1] = v[:,1] + 3.0*np.sin(xn*np.pi)
bowed = trimesh.Trimesh(vertices=v, faces=plate.faces, process=True)
pb = analyze_stable_orientations(bowed, verbose=False)
print(f"\nBOWED PLATE -> {len(pb)} orientations")
for q in pb:
    mq = TF.quaternion_matrix(np.array(q['quaternion']))
    print("   dims", dims(bowed.copy().apply_transform(mq)), "area", q['contactArea'], "margin", q['margin'], "shape", q['shapeRatio'])
