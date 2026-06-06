# 🎨 9. Model Colouring

The `globe3d` library provides a powerful, modular coloring system. By combining different `Colourer` classes, you can paint scientific data, planetary textures, custom boundaries, or marker icons directly onto the globe's 3D mesh. When exported to the OBJ format, these colors are written as vertex colors, which multi-material slicers (like Bambu Studio or OrcaSlicer) can read to automate multi-color 3D printing.

---

## 🎨 The Colourer Class Hierarchy

All coloring operations are handled by subclasses of `Colourer`. Every colourer implements a `__call__(vertices)` method that takes a numpy array of 3D Cartesian coordinates and returns an `(N, 3)` array of RGB colors with values scaled in the range `[0.0, 1.0]`.

### 1. Constant Colouring (`ConstantColourer`)
The simplest colourer paints all given vertices a uniform RGB color. This is useful for coloring the base background of a globe or applying a solid gray/white finish to internal hollowed cavities.
```python
from globe3d import ConstantColourer

# Paint red color [R, G, B]
red_paint = ConstantColourer([1.0, 0.0, 0.0])
model.outer.colour(red_paint)
```

### 2. Equirectangular Image Sampling (`ImageColourer`)
Samples colors from a standard 2D equirectangular image (like a NASA satellite planetary map or a JPEG texture). The library converts the 3D vertex coordinates into spherical coordinates (lat, lon) and maps them to the corresponding pixel in the image.
```python
from globe3d import ImageColourer

# Sample colors from a planetary image texture
earth_texture = ImageColourer("earth_satellite.jpg")
model.outer.colour(earth_texture)
```

### 3. Grid-Based Color Mapping (`GridColourer`)
Interpolates values from a scientific geographic grid (`GeographicGrid` loaded from NetCDF or TIFF) and maps those values to colors using a Matplotlib colormap.
```python
from globe3d import GridColourer, GeographicGrid

# Load tomography or topography grid
topo_grid = GeographicGrid.from_netcdf("topo.nc", "lat", "lon", "z")

# Map topography values using the 'terrain' colormap
grid_painter = GridColourer(topo_grid, colormap='terrain', vmin=-6000, vmax=6000)
model.outer.colour(grid_painter)
```

### 4. Vector Shapefiles & Coordinate Arrays
You can apply colors using geographic vector data. The library supports loading shapefiles via file paths or passing coordinates directly as NumPy arrays.

* **Point Markers (`PointColourer`)**: Paints customizable marker symbols at point coordinates.
  * *Supported Shapes*: `"circle"`, `"square"`, `"triangle"`, `"cross"`, `"star"`, or a custom callable with signature `(x_deg, y_deg, radius_degrees) -> boolean_array`.
  * *Array Input*: An `(N, 2)` array of `(lon, lat)` pairs.
  * *Tangent Plane Projection*: To prevent distortion of marker shapes at high latitudes or poles, coordinates are projected onto a local tangent plane before drawing the shape.
  
* **Custom Width Lines (`LineColourer`)**: Paints lines of a customizable width (buffered by `width_degrees`).
  * *Array Input*: A list of `(N, 2)` arrays of `(lon, lat)` pairs representing line segments.

* **Polygon Flooding (`PolygonColourer`)**: Floods the interior or exterior region of closed polygons.
  * *Array Input*: A list of `(N, 2)` arrays of `(lon, lat)` pairs representing closed rings.

```python
import numpy as np
from globe3d import PointColourer, LineColourer, PolygonColourer

# 1. Paint red stars (0.5 degrees radius) at populous capitals (lon, lat)
capitals = np.array([
    [139.6917, 35.6895],  # Tokyo
    [77.2090, 28.6139]    # Delhi
])
star_painter = PointColourer(capitals, color=[1.0, 0.0, 0.0], radius_degrees=0.5, marker_shape="star")
model.outer.colour(star_painter)

# 2. Paint a custom path with 1.0 degree width
path = [np.array([[-10, 0], [0, 10], [10, 0]])]
line_painter = LineColourer(path, color=[0.0, 1.0, 0.0], width_degrees=1.0)
model.outer.colour(line_painter)

# 3. Flood inside a square polygon with green, ocean remains default
land_poly = [np.array([[-30, -30], [30, -30], [30, 30], [-30, 30], [-30, -30]])]
flood_painter = PolygonColourer(land_poly, color=[0.1, 0.8, 0.2], flood_inside=True)
model.outer.colour(flood_painter)
```

---

## 🎯 Restricting Which Area is Coloured

By default, calling `model.outer.colour(colouring)` colors every vertex on the outer shell. You can target specific subsets of vertices using the `selection` parameter:

* **Outward-Facing Vertices (`selection='outward_facing'`)**: Colors only vertices forming faces that point outward (the external globe surface).
* **Inward-Facing Vertices (`selection='inward_facing'`)**: Colors only vertices on faces that point inward (the inner hollow cavity walls).
* **Custom Index Array**: Pass a list or array of integer vertex indices.
* **Custom Selection Callable**: Pass a function `(vertices, faces, **kwargs)` that returns indices.

```python
# Paint the outer surface using topography grid colors
model.outer.colour(GridColourer(topo_grid, colormap='terrain'), selection='outward_facing')

# Paint the inside hollow cavity walls a professional neutral dark gray
model.outer.colour(ConstantColourer([0.2, 0.2, 0.2]), selection='inward_facing')
```
