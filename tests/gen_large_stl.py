import sys, trimesh
# Dense UV sphere -> ~150k tris (not the user's part; synthetic perf probe)
sph = trimesh.creation.uv_sphere(count=(260, 180))  # many quads -> tris
print("verts", len(sph.vertices), "faces", len(sph.faces))
sph.export("tests/large_mesh.stl")
print("wrote", len(sph.faces), "tris to tests/large_mesh.stl")
