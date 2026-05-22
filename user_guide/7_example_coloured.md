# 7. Example 4: Coloured Globe (Complete Pipeline)

This tutorial brings all features of `globe3d` together. We will build a hollow split globe, displace the outer surface with topography and coastlines, color the outer shell based on a seismic tomography depth slice, color the inner hollow shell a neutral gray, insert magnet slots, and export the final colored OBJ files.

The complete notebook is located at [examples/example_4_coloured_globe.ipynb](../examples/example_4_coloured_globe.ipynb).

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
    create_hollow_hemispheres,
    assign_vertex_colors,
    modify_vertex_colors,
    write_obj_with_vertex_colors
)
```

### 2. Generate Base Spheres
We generate a high-detail outer sphere and a coarser inner sphere:
```python
model_radius_mm = 40.0

# 8,000 points for a fast demo (use 100,000+ for high detail)
outer_v, outer_f = generate_sphere_points_fibonacci(n_points=8000, radius=model_radius_mm)
inner_v, inner_f = generate_sphere_points_fibonacci(n_points=2000, radius=model_radius_mm * 0.75)
```

### 3. Apply Topography & Coastline Displacements
```python
# Load topography grid (ETOPO)
topo_lats, topo_lons, topo_grid = load_netcdf_grid("../inputs/ETOPO_2022_v1_60s_N90W180_surface.nc", 'lat', 'lon', 'z')
topo_lats_ds, topo_lons_ds, topo_grid_ds = topo_lats[::10], topo_lons[::10], topo_grid[::10, ::10]

# Displace outer shell
scale = calculate_displacement_scale(model_radius_mm, earth_radius_km=6371.0, vertical_exagg=40.0)
outer_v = displace_vertices(outer_v, topo_lats_ds, topo_lons_ds, topo_grid_ds, scale)

# Apply coastline step
outer_v = displace_near_lines(
    vertices=outer_v,
    shapefile_path="../inputs/coastlines/ne_110m_coastline.shp",
    displacement=0.8,
    width_degrees=0.5
)
```

### 4. Split and Hollow with Magnets
We split the outer shell and subtract the inner shell while inserting magnet voids:
```python
magnet_params = {
    'magnet_diameter': 5.0,
    'magnet_height': 2.0,
    'h_tol': 0.15,
    'v_tol': 0.10,
    'v_offset': 0.20,
    'min_thick': 1.5,
    'n_magnets': 3,
    'add_bosses': True  # Add reinforcing bosses
}

top_half, bottom_half = create_hollow_hemispheres(
    outer_vertices=outer_v,
    outer_faces=outer_f,
    inner_vertices=inner_v,
    inner_faces=inner_f,
    engine='manifold',
    magnet_params=magnet_params
)
```

### 5. Independent Surface Coloring
Now we color the vertices. We assign colors to the outer surface from a seismic tomography grid, and then recolor the inner cavity vertices to a neutral grey.

```python
# Load tomography grid
tomo_lats, tomo_lons, tomo_grid = load_netcdf_grid("../inputs/s40_depth_slice_2850.grd", 'y', 'x', 'z')

# 5.1 Assign default colors to all vertices on the top hemisphere based on tomography
top_colors = assign_vertex_colors(
    vertices=top_half.vertices,
    lats=tomo_lats,
    lons=tomo_lons,
    grid=tomo_grid,
    colormap='RdBu_r',  # Red-White-Blue colormap
    vmin=-2.0,
    vmax=2.0
)

# 5.2 Recolor only the inward-facing vertices (the hollow cavity) to a neutral grey [0.6, 0.6, 0.6]
top_colors = modify_vertex_colors(
    vertices=top_half.vertices,
    colors=top_colors,
    selection_function='inward_facing',
    faces=top_half.faces,
    constant_color=[0.6, 0.6, 0.6]
)

# 5.3 Repeat for the bottom hemisphere
bottom_colors = assign_vertex_colors(
    vertices=bottom_half.vertices,
    lats=tomo_lats,
    lons=tomo_lons,
    grid=tomo_grid,
    colormap='RdBu_r',
    vmin=-2.0,
    vmax=2.0
)
bottom_colors = modify_vertex_colors(
    vertices=bottom_half.vertices,
    colors=bottom_colors,
    selection_function='inward_facing',
    faces=bottom_half.faces,
    constant_color=[0.6, 0.6, 0.6]
)
```

### 6. Visualize the Colors
Let's verify that the outer surface has the tomography texture while the inside is flat gray:
```python
fig = plt.figure(figsize=(10, 5))

# Top half colored preview
ax1 = fig.add_subplot(121, projection='3d')
pts_top = top_half.vertices
ax1.scatter(pts_top[:, 0], pts_top[:, 1], pts_top[:, 2], c=top_colors, s=2)
ax1.set_title("Colored Top Hemisphere")

# Bottom half colored preview
ax2 = fig.add_subplot(122, projection='3d')
pts_bot = bottom_half.vertices
ax2.scatter(pts_bot[:, 0], pts_bot[:, 1], pts_bot[:, 2], c=bottom_colors, s=2)
ax2.set_title("Colored Bottom Hemisphere")

plt.show()
```

### 7. Export as OBJs with Vertex Colors
Export both models. Slicers like Bambu Studio will read these vertex colors directly:
```python
output_dir = "../outputs"
os.makedirs(output_dir, exist_ok=True)

write_obj_with_vertex_colors(
    filename=os.path.join(output_dir, "example_4_top.obj"),
    vertices=top_half.vertices,
    faces=top_half.faces,
    colors=top_colors
)

write_obj_with_vertex_colors(
    filename=os.path.join(output_dir, "example_4_bottom.obj"),
    vertices=bottom_half.vertices,
    faces=bottom_half.faces,
    colors=bottom_colors
)
print("Saved colored hemispheres to OBJ format.")
```
