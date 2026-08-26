import sys, numpy as np, trimesh
sys.path.insert(0, 'physics-engine')
from orientation_analysis import analyze_stable_orientations
TF = trimesh.transformations
def dims(t): return np.round(t.bounds[1]-t.bounds[0],1)

for label, m in [
    ("SPHERE", trimesh.creation.icosphere(subdivisions=2)),
    ("ELLIPSOID", trimesh.creation.icosphere(subdivisions=2).apply_scale([1,0.5,0.8])),
]:
    p = analyze_stable_orientations(m, verbose=False)
    print(f"{label} -> {len(p)} stable orientations (a rolling body should be ~0)")
    for q in p[:6]:
        mq = TF.quaternion_matrix(np.array(q['quaternion']))
        print("   dims", dims(m.copy().apply_transform(mq)), "area", q['contactArea'], "margin", q['margin'], "shape", q['shapeRatio'])

# A cylinder resting on its side should be UNSTABLE (rolls), on its flat ends STABLE.
cyl = trimesh.creation.cylinder(radius=10, height=30, sections=48)
p = analyze_stable_orientations(cyl, verbose=False)
print("\nCYLINDER r=10 h=30 ->", len(p), "stable orientations (want: 2 flat ends, NOT the side)")
for q in p:
    mq = TF.quaternion_matrix(np.array(q['quaternion']))
    print("   dims", dims(cyl.copy().apply_transform(mq)), "area", q['contactArea'], "margin", q['margin'], "shape", q['shapeRatio'])
