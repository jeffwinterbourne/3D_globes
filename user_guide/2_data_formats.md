# 2. Data Formats & Requirements

This page details the types of files `globe3d` uses, explaining both the **scientific inputs** (how data is stored by researchers) and the **3D manufacturing outputs** (how data is structured for 3D printers).

---

## 🗺️ Input Grid Formats (Topography / Tomography)

Geophysical features (like mountains, trenches, or temperature anomalies in the mantle) are represented as global grids of values. `globe3d` supports the two most common scientific grid formats:

### 1. NetCDF (Network Common Data Form) — `.nc` or `.grd`
NetCDF is the standard file format for global elevation, oceanography, and geophysics (used for datasets like ETOPO or GMT grids). It is highly efficient because it packages coordinate arrays and data values together.
- **Structure**: Contains axes for longitude (usually $-180^\circ$ to $180^\circ$ or $0^\circ$ to $360^\circ$), latitude ($-90^\circ$ to $90^\circ$), and a 2D grid containing the values (e.g. elevation in meters, or seismic velocity anomaly in percent).
- **How to Load It**:
  ```python
  from globe3d import GeographicGrid
  # Load the grid and specify which variables represent lat, lon, and data
  grid = GeographicGrid.from_netcdf(
      "inputs/ETOPO_2022_v1_60s_N90W180_surface.nc",
      lat_var="lat", lon_var="lon", data_var="z"
  )
  ```

### 2. GeoTIFF / TIFF — `.tif` or `.tiff`
Many planetary missions and mapping agencies publish elevation data as grayscale TIFF images. A GeoTIFF is a standard image that contains built-in coordinate metadata.
- **Structure**: Assumes a standard **equirectangular (Plate Carrée)** projection (a simple flat grid mapping directly to latitude and longitude).
- **How to Load It**:
  ```python
  from globe3d import GeographicGrid
  grid = GeographicGrid.from_tiff("inputs/my_elevation_grid.tif")
  ```

---

## 🎨 Input Image Formats (Surface Coloring)

If you want to print your globes in color (or view them in a colored preview), you can use standard image files (like PNG or JPEG).
- **Requirement**: The image must be in an **equirectangular (Plate Carrée)** map projection (meaning the width-to-height ratio must be exactly 2:1).
- **How it works**: The library calculates the geographic coordinates (latitude and longitude) of each 3D point on your sphere, maps them to the corresponding pixel coordinate $(u, v)$ on the image, and extracts the color:
  $$u = \frac{\text{lon} + 180}{360} \times (\text{width} - 1)$$
  $$v = \frac{90 - \text{lat}}{180} \times (\text{height} - 1)$$
- **Coloring the sphere**:
  ```python
  # Assign colors from an image to the outer surface of your model
  model.outer.assign_colors_from_image("inputs/earth_color_map.png")
  ```

---

## 💾 Output 3D File Formats

Once your 3D globe is generated in Python, you need to save it in a format that your 3D printing software (the "slicer") can read.

### 1. Binary STL (Stereolithography) — `.stl`
STL is the universal language of 3D printing. It represents the 3D surface as a collection of triangles.
- **Color Support**: **No**. Suitable for single-color filaments.
- **Best Use Case**: Solid or hollow single-material globes.
- **How to Export**:
  ```python
  # Exports the outer shell as a standard STL
  model.outer.export_stl("outputs/globe.stl")
  ```

### 2. Wavefront OBJ — `.obj`
OBJ files store 3D geometry alongside vertex attributes, including color.
- **Color Support**: **Yes**. It writes the RGB color code directly alongside each vertex coordinate (`v x y z r g b`).
- **Best Use Case**: Multi-color or multi-material 3D printing. Modern slicers (like Bambu Studio, OrcaSlicer, or PrusaSlicer) read these vertex colors and map them to different colored filaments.
- **How to Export**:
  ```python
  # Save a colored model (OBJ format is called automatically when using export on a colored model)
  model.export("outputs/globe.obj")
  ```

---

## 📐 Coordinate Systems & Conventions

Under the hood, `globe3d` does its math in standard 3D Cartesian coordinates $(x, y, z)$ measured in millimeters, centered on the globe:
- **Origin $(0,0,0)$**: The exact center of the sphere.
- **X-axis**: Points toward the Prime Meridian ($0^\circ$ longitude) at the equator.
- **Y-axis**: Points toward $90^\circ\text{E}$ longitude at the equator.
- **Z-axis**: Points toward the North Pole ($90^\circ\text{N}$).

Converting between 3D model space and geographic coordinates is done using standard spherical formulas:
- **Radius $r$**: $r = \sqrt{x^2 + y^2 + z^2}$
- **Latitude $\text{lat}$**: $\text{lat} = \arcsin\left(\frac{z}{r}\right) \times \frac{180}{\pi}$
- **Longitude $\text{lon}$**: $\text{lon} = \text{atan2}(y, x) \times \frac{180}{\pi}$

### Triangle Winding (Chirality)
For a 3D printer to slice a model, it must know what is the **outside** of the object (solid plastic) and what is the **inside** (hollow air). In 3D graphics, this is defined by the order of the triangle's corners:
- **Counter-Clockwise (CCW)**: Points outward (defines the outer shell of the globe).
- **Clockwise (CW)**: Points inward (defines the interior walls of a hollow cavity).
The library handles this automatically when creating hollow shells, but understanding it helps when diagnosing mesh errors in your slicer.
