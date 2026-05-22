# 2. Data Formats & Requirements

This page details the files and data structures `globe3d` uses, including input grids, textures, coordinate systems, and 3D printable files.

---

## 🗺️ Input Grid Formats (Topography / Tomography)

Topography grids specify the radial elevation or displacement at any given point on the globe. `globe3d` supports two primary categories of grids:

### 1. NetCDF (Network Common Data Form) — `.nc` or `.grd`
NetCDF is the standard file format for global elevation and scientific planetary grids (such as ETOPO or GMT grids).
- **Structure**: Contains coordinate axes for latitude (e.g. `lat` or `y`) and longitude (e.g. `lon` or `x`), and a 2D array of grid values (e.g. `z` or `elevation`).
- **Loading**: Use the `load_netcdf_grid` function:
  ```python
  from globe3d import load_netcdf_grid
  lats, lons, grid = load_netcdf_grid(
      "inputs/ETOPO_2022_v1_60s_N90W180_surface.nc",
      lat_var="lat", lon_var="lon", data_var="z"
  )
  ```
- **Requirements**: Longitude should cover $[-180^\circ, 180^\circ]$ or $[0^\circ, 360^\circ]$, and latitude should cover $[-90^\circ, 90^\circ]$. Both axes must be sorted ascending.

### 2. GeoTIFF / TIFF — `.tif` or `.tiff`
Standard images with spatial metadata can be loaded as grids.
- **Structure**: Assumes an equirectangular (Plate Carrée) projection spanning $-180^\circ \text{ to } 180^\circ$ longitude and $90^\circ \text{ to } -90^\circ$ latitude.
- **Loading**: Use the `load_tiff_grid` function:
  ```python
  from globe3d import load_tiff_grid
  lats, lons, grid = load_tiff_grid("inputs/my_elevation_grid.tif")
  ```

---

## 🎨 Input Image Formats (Vertex Texturing)

You can color your 3D globes using any standard image file (such as PNG or JPEG).
- **Requirement**: The image must be an **equirectangular (Plate Carrée)** map projection (width-to-height ratio of 2:1).
- **Coordinate Mapping**: The library maps each 3D vertex to its geographic latitude and longitude, and then calculates the pixel coordinates $(u, v)$ on the image:
  $$u = \frac{\text{lon} + 180}{360} \times (\text{width} - 1)$$
  $$v = \frac{90 - \text{lat}}{180} \times (\text{height} - 1)$$
- **Loading & Coloring**: Done automatically via `assign_vertex_colors_image`:
  ```python
  from globe3d import assign_vertex_colors_image
  colors = assign_vertex_colors_image(vertices, "inputs/earth_color_map.png")
  ```

---

## 💾 Output 3D File Formats

`globe3d` exports models into two main formats suited for 3D printing:

### 1. Binary STL (Stereolithography) — `.stl`
STL is the most common format for 3D printing.
- **Color Support**: **No**. Suitable for single-color/single-material filaments.
- **Use Case**: Solid or hollow globes printed with a single filament.
- **Exporting**:
  ```python
  from globe3d import write_stl_binary
  write_stl_binary("outputs/globe.stl", vertices, faces)
  ```

### 2. Wavefront OBJ — `.obj`
OBJ supports vertex colors directly within the file.
- **Color Support**: **Yes**. It writes the vertex coordinates followed by RGB values: `v x y z r g b` (where $r, g, b$ are in the range $[0.0, 1.0]$).
- **Use Case**: Multi-color or multi-material 3D printing (supported by Bambu Studio, OrcaSlicer, and PrusaSlicer).
- **Exporting**:
  ```python
  from globe3d import write_obj_with_vertex_colors
  write_obj_with_vertex_colors("outputs/globe.obj", vertices, faces, colors)
  ```

---

## 📐 Coordinate Systems & Conventions

`globe3d` performs calculations in a right-handed Cartesian coordinate system:
- **Origin $(0,0,0)$**: The center of the globe.
- **X-axis**: Points toward $0^\circ$ longitude (Prime Meridian) at the equator.
- **Y-axis**: Points toward $90^\circ\text{E}$ longitude at the equator.
- **Z-axis**: Points toward the North Pole ($90^\circ\text{N}$).

### Coordinate Conversion Formulas
For a vertex at $(x, y, z)$:
- **Radius $r$**: $r = \sqrt{x^2 + y^2 + z^2}$
- **Latitude $\text{lat}$**: $\text{lat} = \arcsin\left(\frac{z}{r}\right) \times \frac{180}{\pi}$
- **Longitude $\text{lon}$**: $\text{lon} = \text{atan2}(y, x) \times \frac{180}{\pi}$

### Normal Vector Conventions
In `globe3d`, triangles have a specific **chirality** (winding order). By default, the vertices of each triangle are ordered counter-clockwise when viewed from the outside, which makes normal vectors point outward.
- **Outer Shell**: Normals point outwards (positive volume).
- **Inner Shell (Hollow Cavity)**: Normals point inwards (negative volume), achieved by reversing the triangle winding order using `invert_chirality`.
