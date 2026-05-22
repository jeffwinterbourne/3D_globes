# 5. Example 2: Intermediate Globe (Coastline step & Hemisphere splitting)

This tutorial walks through creating a globe that combines topography displacement with a sharp boundary step at the coastlines (derived from a shapefile), and splits the mesh into capped top and bottom hemispheres for easy flat-bed 3D printing.

The complete notebook is located at [examples/example_2_intermediate_globe.ipynb](../examples/example_2_intermediate_globe.ipynb).

---

## Code Walkthrough

### 1. Import Libraries
```python
import os
import numpy as np
import matplotlib.pyplot as plt
import trimesh
from globe3d import (
    generate_sphere_points_fibonacci,
    load_netcdf_grid,
    calculate_displacement_scale,
    displace_vertices,
    displace_near_lines,
    split_mesh_hemispheres
)
```

### 2. Base Sphere and Topography
We first generate our sphere and apply ETOPO grid displacement (just like in Example 1):
```python
model_radius_mm = 40.0
vertices, faces = generate_sphere_points_fibonacci(n_points=8000, radius=model_radius_mm)

# Load and downsample ETOPO grid
netcdf_path = "../inputs/ETOPO_2022_v1_60s_N90W180_surface.nc"
lats, lons, grid = load_netcdf_grid(netcdf_path, 'lat', 'lon', 'z')
lats_ds, lons_ds, grid_ds = lats[::10], lons[::10], grid[::10, ::10]

scale = calculate_displacement_scale(model_radius_mm, earth_radius_km=6371.0, vertical_exagg=40.0)
vertices = displace_vertices(vertices, lats_ds, lons_ds, grid_ds, scale)
```

### 3. Add Coastline Step (Shapefile Displacement)
To make coastlines stand out physically, we can apply a sharp step (e.g. 0.8 mm) using a global coastline shapefile. This displaces vertices that are near the coastlines:
```python
# Path to Natural Earth coastlines shapefile
coastline_shp = "../inputs/coastlines/ne_110m_coastline.shp"

# Apply a 0.8 mm step ribbon along the coastline to make borders distinct
vertices = displace_near_lines(
    vertices=vertices,
    shapefile_path=coastline_shp,
    displacement=0.8,         # 0.8 mm step height
    width_degrees=0.5         # 0.5 degrees ribbon width
)
```

### 4. Create Mesh Object
We construct a watertight `trimesh.Trimesh` object from our displaced vertices and faces:
```python
mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
mesh.fix_normals()
print(f"Mesh is watertight: {mesh.is_watertight}")
```

### 5. Split into Hemispheres
We use `split_mesh_hemispheres` to cut the mesh at the equator (`normal=(0, 0, 1)`). This caps both halves so they have a flat, solid face that can sit on the 3D printer bed:
```python
top_half, bottom_half = split_mesh_hemispheres(
    mesh=mesh,
    normal=(0, 0, 1),
    origin=(0, 0, 0)
)

print(f"Top half is watertight: {top_half.is_watertight}")
print(f"Bottom half is watertight: {bottom_half.is_watertight}")
```

### 6. Visualize Hemispheres
Let's verify that we have two independent halves:
```python
fig = plt.figure(figsize=(10, 5))

# Top half preview
ax1 = fig.add_subplot(121, projection='3d')
pts_top = top_half.vertices
ax1.scatter(pts_top[:, 0], pts_top[:, 1], pts_top[:, 2], c=pts_top[:, 2], cmap='viridis', s=2)
ax1.set_title("Top Hemisphere")

# Bottom half preview
ax2 = fig.add_subplot(122, projection='3d')
pts_bot = bottom_half.vertices
ax2.scatter(pts_bot[:, 0], pts_bot[:, 1], pts_bot[:, 2], c=pts_bot[:, 2], cmap='viridis', s=2)
ax2.set_title("Bottom Hemisphere")

plt.show()
```

### 7. Export Halves
We export each hemisphere as a separate STL file:
```python
output_dir = "../outputs"
os.makedirs(output_dir, exist_ok=True)

top_half.export(os.path.join(output_dir, "example_2_top.stl"))
bottom_half.export(os.path.join(output_dir, "example_2_bottom.stl"))
print("Saved top and bottom hemispheres.")
```
