import sys, time
sys.path.insert(0, 'C:/xampp/htdocs/GitHub/SOME-PackagingAssistant')
from packer_relief import *
import numpy as np
import trimesh

cell = 3.0
fp = r'C:\xampp\htdocs\GitHub\SOME-PackagingAssistant\web\library\6683688_reduit.stl'
print(f"Loading {fp}...")
mesh = trimesh.load(fp, force='mesh')
if isinstance(mesh, trimesh.Scene):
    geoms = [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
    mesh = trimesh.util.concatenate(geoms)
print(f"Mesh: {len(mesh.vertices)}v, {len(mesh.faces)}f, extents={mesh.extents.round(1)}")

print("Voxelizing one orientation at 3mm...")
t0 = time.time()
occ, origin = voxelize_mesh(mesh, cell)
print(f"  Done in {time.time()-t0:.1f}s, shape={occ.shape}, occupied={occ.sum()} cells")

print("Generating 2 orientations...")
t0 = time.time()
orients = generate_orientations(mesh, n_yaw=2, n_roll=2, cell_size=cell, box_dims=(385,285,150))
print(f"  {len(orients)} orientations in {time.time()-t0:.1f}s")
for o in orients:
    sm = o['size_mm']
    print(f"    {o['name']} size=[{sm[0]:.1f},{sm[1]:.1f},{sm[2]:.1f}] occ={o['occupied']}")
