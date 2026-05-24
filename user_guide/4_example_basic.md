# 4. Example 1: Basic Globe (Topography only)

This tutorial walks through creating a simple, single-color 3D globe with surface topography. We will generate a base sphere, load global elevation data, scale it to tactile dimensions, and export the finished model as a binary STL file—the universal file format for 3D printers.

The complete interactive notebook is located at [examples/example_1_basic_globe.ipynb](../examples/example_1_basic_globe.ipynb).

---

## 🎨 Scientific & Design Context
On a true-scale 80 mm globe, Earth's highest mountain peaks (like Mount Everest) would project outward by less than 0.1 mm—making the surface feel completely smooth to the human touch. To make mountain ranges, ocean trenches, and continental boundaries tactile, we apply a **vertical exaggeration scale factor**. For Earth, a 40× or 50× exaggeration provides a beautiful, hands-on representation of tectonic activity and surface structure without distorting the planetary shape.

---

## 💻 Code Walkthrough

### 1. Import the Library
We import `globe3d`'s object-oriented components along with standard helper libraries.
```python
import numpy as np
import matplotlib.pyplot as plt
from globe3d import (
    GlobeModel,
    GeographicGrid,
    GridDisplacer,
    calculate_displacement_scale
)
```

### 2. Generate the Base Sphere
We define the size of our model in millimeters (standard for 3D printer slicing software). A radius of $40.0\text{ mm}$ (an 80 mm diameter globe) is a perfect desktop size. We will use a Fibonacci lattice of 5,000 points to keep calculations fast while testing.
```python
# Radius of the model in mm (3D printing units)
model_radius_mm = 40.0

# Create a GlobeModel using the unified constructor
model = GlobeModel(method='fibonacci', n_points=5000, radius=model_radius_mm)
print(f"Generated sphere with {model.outer.vertices.shape[0]} vertices and {model.outer.faces.shape[0]} faces.")
```

### 3. Load the Elevation Grid
We load global topography from a NetCDF database. Because raw planetary grids are extremely high resolution, we downsample the grid (selecting every 10th cell) so the interpolation code runs quickly inside Jupyter.
```python
# Path to NetCDF grid (ETOPO)
netcdf_path = "../inputs/ETOPO_2022_v1_60s_N90W180_surface.nc"

# Load latitude, longitude, and data grid arrays
full_grid = GeographicGrid.from_netcdf(netcdf_path, lat_var='lat', lon_var='lon', data_var='z')

# Downsample grid for fast rendering
grid_ds = GeographicGrid(
    lats=full_grid.lats[::10],
    lons=full_grid.lons[::10],
    grid=full_grid.grid[::10, ::10]
)
print(f"Downsampled grid shape: {grid_ds.grid.shape}")
```

### 4. Calculate the Displacement Scale
The ETOPO elevation data is measured in **meters**, while our 3D model is in **millimeters**. We use the helper function `calculate_displacement_scale` to automatically convert units and apply a 40× vertical exaggeration:
```python
# Exaggerate topography 40 times to make it feel tactile
vertical_exaggeration = 40.0
grid_units = 'm'  # Elevation grid is in meters

scale = calculate_displacement_scale(
    model_radius_mm=model_radius_mm,
    vertical_exagg=vertical_exaggeration,
    grid_units=grid_units
)
print(f"Scale factor: {scale}")
```

### 5. Apply the Topography Displacement
Now we apply the radial displacement. This translates each vertex of the sphere inward or outward along its radial vector based on the elevation grid, creating mountains and trenches:
```python
# Apply displacement to the outer shell using a Displacer
model.outer.displace(GridDisplacer(grid_ds, show_progress=True), scale=scale)
print("Displaced model vertices.")
```

### 6. Preview the Result in 3D
We plot the 3D coordinates using `matplotlib` to verify our topography before saving the file:
```python
fig = plt.figure(figsize=(8, 8))
ax = fig.add_subplot(111, projection='3d')

# Plot a subset of 1,000 random points for performance
indices = np.random.choice(len(model.outer.vertices), 1000, replace=False)
pts = model.outer.vertices[indices]

sc = ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2], c=pts[:, 2], cmap='terrain', s=4)
fig.colorbar(sc, ax=ax, label='Z coordinate (mm)')
ax.set_title("Basic Globe Topography preview")
plt.show()
```

### 7. Export for Slicing
Save the model as a binary STL file, ready to load into your slicer:
```python
output_path = "../outputs/example_1_basic_globe.stl"
model.export(output_path)
print(f"Saved STL file to: {output_path}")
```
