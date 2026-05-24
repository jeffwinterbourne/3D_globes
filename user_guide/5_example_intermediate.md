# 5. Example 2: Intermediate Globe (Coastline step & Hemisphere splitting)

This tutorial walks through creating a more advanced globe that combines standard topographic displacement with a sharp, physical boundary step at the coastlines (derived from a vector shapefile). We will then split the displaced model into capped top and bottom hemispheres for easy flat-bed 3D printing.

The complete interactive notebook is located at [examples/example_2_intermediate_globe.ipynb](../examples/example_2_intermediate_globe.ipynb).

---

## 🎨 Scientific & Design Context
When 3D printing long-wavelength models (like seismic tomography or dynamic topography), the surface can become highly distorted. Adding a **coastline step** serves as a vital physical "anchor" or grid reference:
- **Spatial Reference**: It raises the continental landmasses by a constant step (e.g. 0.8 mm), creating a clear, sharp ledge at the coastline. 
- **Tactile Learning**: This allows users (especially those with visual impairments) to immediately orient themselves and identify familiar landmasses (like the UK, Madagascar, or Australia) relative to the underlying geodynamic structures.

---

## 💻 Code Walkthrough

### 1. Import Libraries
We import `globe3d`'s object-oriented components along with standard helper libraries.
```python
import numpy as np
import matplotlib.pyplot as plt
from globe3d import (
    GlobeModel,
    GeographicGrid,
    GridDisplacer,
    LineDisplacer,
    calculate_displacement_scale
)
```

### 2. Base Sphere and Topography
We generate an 8,000-point Fibonacci sphere and apply ETOPO grid elevation displacement (just like in Example 1):
```python
model_radius_mm = 40.0
topo_units = 'm'  # ETOPO elevation data is in meters

# Initialize the model
model = GlobeModel(n_points=8000, radius=model_radius_mm)

# Load and downsample ETOPO grid
full_grid = GeographicGrid.from_netcdf(
    "../inputs/ETOPO_2022_v1_60s_N90W180_surface.nc", 'lat', 'lon', 'z'
)
grid_ds = GeographicGrid(
    lats=full_grid.lats[::10],
    lons=full_grid.lons[::10],
    grid=full_grid.grid[::10, ::10]
)

scale = calculate_displacement_scale(model_radius_mm, vertical_exagg=40.0, grid_units=topo_units)
model.outer.displace(GridDisplacer(grid_ds), scale=scale)
```

### 3. Apply the Coastline Step (Line Displacement)
We load coastlines from a standard Natural Earth shapefile. The `LineDisplacer` identifies all vertices within a given width (in degrees) of a coastline and pushes them outward, creating a tactile ribbon ledge:
```python
# Path to Natural Earth coastlines shapefile
coastline_shp = "../inputs/coastlines/ne_110m_coastline.shp"

# Apply a 0.8 mm step ribbon along the coastline to make borders distinct
model.outer.displace(LineDisplacer(
    shapefile_path=coastline_shp,
    displacement=0.8,   # 0.8 mm step height
    width_degrees=0.5   # 0.5 degrees ribbon width
))
print("Applied coastline step displacement.")
```

### 4. Preview the Split Hemispheres
Before saving, we can preview how the sphere looks when cut along the equator. `generate_hemispheres()` returns two mesh objects capped flat at the cut plane:
```python
# Generate hemispheres for preview (not hollow for this simple example)
top_half, bottom_half = model.generate_hemispheres(hollow=False)

fig = plt.figure(figsize=(12, 6))

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

### 5. Split and Export
Rather than manually splitting and exporting, `GlobeModel.export_hemispheres` cuts the model at the equator, caps the faces, and writes them out to two separate STL files in a single line of code:
```python
model.export_hemispheres(
    "../outputs/example_2_top.stl",
    "../outputs/example_2_bottom.stl",
    hollow=False,
)
print("Hemispheres exported to outputs/")
```
