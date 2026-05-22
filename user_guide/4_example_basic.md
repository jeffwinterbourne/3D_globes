# 4. Example 1: Basic Globe (Topography only)

This tutorial walks through creating a simple, uncolored 3D globe with surface topography. We will use a Fibonacci sphere and displace the vertices using a standard global elevation grid.

The complete notebook is located at [examples/example_1_basic_globe.ipynb](../examples/example_1_basic_globe.ipynb).

---

## Code Walkthrough

### 1. Import Libraries
We import `globe3d` and helper libraries.
```python
import os
import numpy as np
import matplotlib.pyplot as plt
from globe3d import (
    generate_sphere_points_fibonacci,
    load_netcdf_grid,
    calculate_displacement_scale,
    displace_vertices,
    write_stl_binary
)
```

### 2. Generate a Fibonacci Sphere
We define the sphere parameters. A radius of $40.0\text{ mm}$ (80mm total diameter) is a good size for testing.
```python
# Radius of the model in mm (3D printing units)
model_radius_mm = 40.0

# Generate 5,000 points for a fast demo (use 50,000+ for high detail)
vertices, faces = generate_sphere_points_fibonacci(
    n_points=5000, 
    radius=model_radius_mm
)
print(f"Generated sphere with {vertices.shape[0]} vertices and {faces.shape[0]} faces.")
```

### 3. Load the Elevation Grid
We load the elevation grid from a NetCDF file. We downsample it here to run quickly in Jupyter.
```python
# Path to NetCDF grid (ETOPO)
netcdf_path = "../inputs/ETOPO_2022_v1_60s_N90W180_surface.nc"

# Load grid
lats, lons, grid = load_netcdf_grid(
    netcdf_path, 
    lat_var='lat', 
    lon_var='lon', 
    data_var='z'
)

# Downsample the grid for faster interpolation in this notebook
lat_step, lon_step = 10, 10
lats_ds = lats[::lat_step]
lons_ds = lons[::lon_step]
grid_ds = grid[::lat_step, ::lon_step]

print(f"Original grid shape: {grid.shape}")
print(f"Downsampled grid shape: {grid_ds.shape}")
```

### 4. Calculate Displacement Scale
The physical elevations are in meters, whereas the 3D model is in millimeters. We must scale the elevations so they are visible on a small model. We apply a vertical exaggeration (e.g. 40x):
```python
# Exaggerate topography 40 times to make it feel tactile
vertical_exaggeration = 40.0
earth_radius_km = 6371.0

scale = calculate_displacement_scale(
    model_radius_mm=model_radius_mm,
    earth_radius_km=earth_radius_km,
    vertical_exagg=vertical_exaggeration
)
print(f"Calculated displacement scale factor: {scale}")
```

### 5. Displace Vertices
Now we apply the radial displacement. This translates each vertex outward or inward along its radial vector based on the elevation grid:
```python
displaced_vertices = displace_vertices(
    vertices=vertices,
    lats=lats_ds,
    lons=lons_ds,
    grid=grid_ds,
    scale=scale,
    show_progress=True
)
```

### 6. Visualize the Result
We plot the 3D points using `matplotlib` to verify:
```python
fig = plt.figure(figsize=(8, 8))
ax = fig.add_subplot(111, projection='3d')
# Plot a subset of points for performance
sample_idx = np.random.choice(len(displaced_vertices), 1000, replace=False)
pts = displaced_vertices[sample_idx]
ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2], c=pts[:, 2], cmap='terrain', s=5)
ax.set_title("Basic Globe Topography (3D Preview)")
plt.show()
```

### 7. Export to Binary STL
Save the model as a binary STL file, ready to load into your slicer:
```python
output_dir = "../outputs"
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "example_1_basic_globe.stl")

write_stl_binary(output_path, displaced_vertices, faces)
print(f"Successfully saved STL to {output_path}")
```
