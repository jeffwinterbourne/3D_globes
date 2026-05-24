# 7. Example 4: Coloured Globe (Complete Pipeline)

This tutorial brings all the features of `globe3d` together. We will build a hollow split globe, displace the outer surface with topography and coastlines, color the outer shell based on a seismic tomography depth slice, color the inner hollow cavity a neutral gray, configure magnet slots with reinforcing bosses, and export the final colored OBJ meshes.

The complete interactive notebook is located at [examples/example_4_coloured_globe.ipynb](../examples/example_4_coloured_globe.ipynb).

---

## 🎨 Scientific & Design Context
This complete pipeline allows you to create highly engaging, multi-textured models. In this example, we represent deep Earth interior structure at the Core-Mantle Boundary (CMB, at 2,850 km depth) from the seismic tomography model SP12RTS.
- **Seismic Tomography Coloring**: High seismic wave velocities (representing cold, dense, sinking slabs) are colored blue. Low velocities (representing hot, light, rising mantle plumes or upwellings) are colored red.
- **Independent Cavity Painting**: Since the interior of the globe is sliced open, we color the internal cavity walls a clean, uniform gray. This prevents the outer scientific dataset colors from bleeding inside, making the model look professional and clear.

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
    GridColourer,
    ConstantColourer,
    calculate_displacement_scale
)
```

### 2. Generate Hollow Sphere
We initialize our model as a hollow sphere. An `inner_ratio` of `0.5` sets the inner cavity's boundary at $50\%$ of the outer radius, leaving a thick, sturdy shell.
```python
model_radius_mm = 40.0

model = GlobeModel(
    n_points=8000,
    radius=model_radius_mm,
    hollow=True,
    inner_ratio=0.5,
)
print(f"Outer shell: {model.outer.vertices.shape[0]} vertices")
print(f"Inner cavity: {model.inner.vertices.shape[0]} vertices")
```

### 3. Apply Topography & Coastline Displacements
We load the elevation grid, scale the elevations to model dimensions (40× exaggeration), and apply the displacements. Then we apply a 0.8 mm coastline step using our vector shapefile:
```python
# Load and downsample ETOPO topography grid
topo_grid = GeographicGrid.from_netcdf(
    "../inputs/ETOPO_2022_v1_60s_N90W180_surface.nc", 'lat', 'lon', 'z'
)
topo_grid_ds = GeographicGrid(
    lats=topo_grid.lats[::10],
    lons=topo_grid.lons[::10],
    grid=topo_grid.grid[::10, ::10]
)

# Scale and apply displacement
topo_units = 'm'
scale = calculate_displacement_scale(
    model_radius_mm, vertical_exagg=40.0, grid_units=topo_units
)
model.outer.displace(GridDisplacer(topo_grid_ds), scale=scale)

# Apply a sharp coastline step
model.outer.displace(LineDisplacer(
    shapefile_path="../inputs/coastlines/ne_110m_coastline.shp",
    displacement=0.8,
    width_degrees=0.5
))
```

### 4. Configure Magnets
We set up magnet settings. We'll use 3 magnets per side, reinforced with plastic bosses because our shell walls are relatively thin:
```python
model.configure_magnets(
    diameter=5.0,
    height=2.0,
    horizontal_tolerance=0.15,
    vertical_tolerance=0.10,
    vertical_offset=0.20,
    min_thickness=1.5,
    n_magnets=3,
    add_bosses=True,
)
```

### 5. Independent Surface Coloring
We load the seismic tomography grid. We color the outward-facing (outer shell) vertices based on the tomography values using a Red-to-Blue colormap (`RdBu_r`). Then we paint the inward-facing (inner cavity) vertices a constant, neutral gray:
```python
# Load tomography grid
tomo_grid = GeographicGrid.from_netcdf(
    "../inputs/s40_depth_slice_2850.grd", 'y', 'x', 'z'
)

# 1. Color outer (outward-facing) surfaces using the tomography dataset
model.outer.colour(
    GridColourer(tomo_grid, colormap='RdBu_r', vmin=-2.0, vmax=2.0),
    selection='outward_facing',
)

# 2. Color inner (inward-facing) cavity surfaces to a solid gray
model.outer.colour(
    ConstantColourer([0.6, 0.6, 0.6]),
    selection='inward_facing',
)
```

### 6. Preview Colored Hemispheres in 3D
We generate the hemispheres and plot their vertices colored according to their assigned RGB values:
```python
# Generate hemispheres for preview
top_half, bottom_half = model.generate_hemispheres(engine='manifold')

fig = plt.figure(figsize=(12, 6))

top_colors = top_half.visual.vertex_colors[:, :3].astype(float) / 255.0
bottom_colors = bottom_half.visual.vertex_colors[:, :3].astype(float) / 255.0

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

### 7. Export as Colored OBJs
Save both hemispheres. When you drag and drop these `.obj` files into Bambu Studio or OrcaSlicer, the slicer reads these vertex colors and maps them directly to your multi-color filament slots:
```python
model.export_hemispheres(
    "../outputs/example_4_top.obj",
    "../outputs/example_4_bottom.obj",
    engine='manifold',
)
print("Colored OBJ hemispheres exported successfully!")
```
