# Developer Guide — globe3d

Welcome to the `globe3d` project. This guide provides a comprehensive architectural walkthrough of the library, its modules, the data pipeline from raw geographic grids to 3D-printable models, and the conventions that keep the codebase healthy.

> **See also:** The repository-level [`AGENTS.md`](AGENTS.md) contains environment setup, Conda activation instructions, and CI/testing commands.

---

## 📖 Overview

`globe3d` is a Python package that turns geographic grid data (elevation, seismic tomography, or any other spherical field) into physical, 3D-printable globe models with exaggerated topography and optional vertex coloring. The typical output is a pair of OBJ hemisphere files, ready for full-color FDM or SLA printing.

### Key capabilities

| Capability | Module | Entry Point(s) |
|---|---|---|
| Sphere mesh generation (Fibonacci & icosahedron) | `mesh.py` | `generate_sphere_points_fibonacci`, `generate_sphere_points_icosahedron` |
| Geographic grid loading (NetCDF & TIFF) | `grid.py` | `load_netcdf_grid`, `load_tiff_grid`, `list_netcdf_variables` |
| Radial displacement of vertices | `displacement.py` | `displace_vertices`, `displace_by_points`, `displace_near_lines`, `displace_by_polygons`, `calculate_displacement_scale` |
| Vertex coloring (grid, image & modifiers) | `displacement.py` | `assign_vertex_colors`, `assign_vertex_colors_image`, `modify_vertex_colors`, `modify_vertex_colours` |
| Mesh hollowing & hemisphere splitting | `mesh.py` | `create_hollow_hemispheres`, `combine_subtractive_globes`, `hollow_mesh`, `split_mesh_hemispheres` |
| Mesh utilities (resize, re-project, chirality) | `mesh.py` | `resize_globe`, `project_vertices_to_sphere`, `invert_chirality`, `compute_scale_factor` |
| File export (STL & OBJ with vertex colors) | `io.py` | `write_stl_binary`, `write_obj_with_vertex_colors` |
| Magnet insertion and test piece generation | `magnets.py` | `insert_magnets_into_hemispheres`, `generate_magnet_test_piece`, `find_valid_magnet_positions_no_bosses` |
| Visual QA | `plot.py` | `plot_vertex_distribution` |

---

## 🏗️ Architecture

### Project layout

```
3D_globes/
├── AGENTS.md                  # Environment & CI guidance for agents
├── DEVELOPER_GUIDE.md         # ← you are here
├── README.md
├── pyproject.toml             # Build config (setuptools)
├── setup.py
├── src/
│   └── globe3d/
│       ├── __init__.py        # Public API re-exports
│       ├── mesh.py            # Sphere generation, hollowing, splitting
│       ├── grid.py            # NetCDF / TIFF data loading
│       ├── displacement.py    # Vertex displacement & coloring
│       ├── magnets.py         # Optimization & insertion of magnets
│       ├── io.py              # STL & OBJ export
│       └── plot.py            # Matplotlib visual checks
├── tests/
│   ├── test_mesh.py
│   ├── test_displacement.py
│   ├── test_grid.py
│   └── test_magnets.py
└── examples/
    ├── tomo_globe_3d.ipynb          # Tomography globe (grid-colored)
    ├── demo_split_globe_image.ipynb # Image-colored demo
    └── demo_magnets.ipynb           # Magnet insertion demo
```

### Dependency graph

```mermaid
graph TD
    subgraph "globe3d"
        MESH["mesh.py"]
        GRID["grid.py"]
        DISP["displacement.py"]
        MAGN["magnets.py"]
        IO["io.py"]
        PLOT["plot.py"]
    end

    GRID -->|"lats, lons, grid"| DISP
    MESH -->|"vertices, faces"| DISP
    DISP -->|"displaced vertices, colors"| MESH
    MESH -->|"combined / split meshes"| IO
    DISP -->|"colors"| IO
    MESH -->|"vertices"| PLOT
    MESH -->|"hollow meshes & outer geometry"| MAGN
    MAGN -->|"meshes with magnets / test pieces"| IO

    NP["numpy"] --> MESH
    NP --> GRID
    NP --> DISP
    NP --> MAGN
    NP --> IO
    NP --> PLOT
    SCIPY["scipy"] --> MESH
    SCIPY --> DISP
    SCIPY --> MAGN
    NETCDF4["netCDF4"] --> GRID
    RASTERIO["rasterio (optional)"] --> GRID
    MPL["matplotlib"] --> DISP
    MPL --> PLOT
    TQDM["tqdm"] --> DISP
    TRIMESH["trimesh"] --> MESH
    TRIMESH --> MAGN
```

Modules are intentionally loosely coupled: `grid.py` knows nothing about meshes, `displacement.py` knows nothing about file formats, and `io.py` knows nothing about grids. Communication happens through numpy arrays passed by the caller (typically a notebook).

---

## 🔬 Module-by-Module Reference

### `mesh.py` — Geometry Generation & Processing

This is the largest module (~413 lines) and carries all geometry logic. It has **no dependency on geographic data** — it operates purely on 3D vertex arrays and face index arrays.

#### Sphere generation strategies

| Function | Algorithm | Vertex count control | Notes |
|---|---|---|---|
| `generate_sphere_points_fibonacci(n_points, radius, center)` | [Fibonacci lattice](https://en.wikipedia.org/wiki/Fibonacci_lattice) | Exact (`n_points`) | Near-uniform density; faces computed via `scipy.spatial.ConvexHull`. Preferred for production globes (e.g. 1 million points). |
| `generate_sphere_points_icosahedron(subdivisions, radius, center)` | Recursive midpoint subdivision of an icosahedron | Grows as `10 × 4^s + 2` where `s` = subdivisions | Perfectly uniform triangle area; vertex count grows exponentially. |

Both return `(vertices, faces)` where `vertices` is `(N, 3)` float64 and `faces` is `(F, 3)` int32. Both generators call `trimesh.fix_normals()` internally to guarantee outward-facing winding order.

> [!NOTE]
> `scipy.spatial.ConvexHull` (used by the Fibonacci generator) does **not** guarantee consistent face winding. Without the `fix_normals` post-processing, the resulting mesh can have negative volume (inward-facing normals), which causes slicer artefacts and boolean operation failures.

**Internal helpers** (not exported through `__init__.py`):
- `create_icosahedron(radius, center)` — creates the base 12-vertex / 20-face icosahedron.
- `subdivide_icosahedron(vertices, faces, radius, center)` — one level of Loop-style subdivision with a midpoint cache to prevent duplicate vertices.
- `midpoint(v1, v2)` — simple vector average.
- `project_vertices_to_sphere(vertices, radius, center)` — re-normalises a set of vertices back onto an ideal sphere. Useful after operations that may have perturbed exact radii.

#### Mesh manipulation utilities

| Function | Purpose |
|---|---|
| `resize_globe(vertices, scale, origin)` | Scales vertices relative to a given origin point. |
| `invert_chirality(faces)` | Reverses the winding order (columns 1 and 2 swapped) of every triangle. This flips all face normals. |
| `compute_scale_factor(vertices, desired_cube_size)` | Calculates a uniform scale factor to fit a vertex cloud inside a bounding cube of a desired side length. |

#### Hollowing

There are **three hollowing strategies**, suited to different use cases:

1. **Boolean hemisphere pipeline** (`create_hollow_hemispheres`) — **The recommended approach for 3D printing.** Splits the displaced outer mesh into two capped hemispheres *first*, then boolean-subtracts the inner sphere from each half using `trimesh.boolean.difference`. If `magnet_params` (a dictionary) is supplied, it automatically calls `insert_magnets_into_hemispheres` to place and insert magnets on the flat mating surface. This produces properly manifold, watertight hollow hemispheres with correct annular cap faces and magnet slots. The boolean engine creates its own triangulation for the annular cap ring.

2. **Subtractive combination** (`combine_subtractive_globes`) — A fast, deterministic approach that concatenates outer and inner face arrays with inverted chirality on the inner shell. Suitable for **whole-globe visualisation** (e.g. viewing in MeshLab) but **not for split-and-print workflows** — see warning below.

3. **Boolean difference** (`hollow_mesh`) — Uses `trimesh.boolean.difference` on the whole globe. More geometrically correct than subtractive combination but significantly slower. Accepts optional pre-built inner mesh data, or generates one automatically via `create_inner_mesh`.

> [!WARNING]
> **Do not combine `combine_subtractive_globes` with `split_mesh_hemispheres` for 3D printing.** When `slice_plane(cap=True)` cuts a pre-hollowed mesh, the cap fills the entire cross-section (both outer and inner circles), sealing the inner cavity. The slicer then treats the hemisphere as solid. Use `create_hollow_hemispheres` instead, which splits *before* hollowing.

`create_inner_mesh(outer_vertices, outer_faces, thickness)` scales the outer mesh down about its bounding-box centre so that the thinnest wall is `thickness` units.

#### Hemisphere splitting

`split_mesh_hemispheres(mesh, normal, origin)` uses `trimesh.Trimesh.slice_plane` to cut a mesh into two halves along a plane (default: the equator, `normal=(0,0,1)`). Both halves are **capped** so they can be printed flat-side-down.

> [!NOTE]
> For hollow globe printing, prefer `create_hollow_hemispheres` which handles splitting *and* hollowing in the correct order.

---

### `grid.py` — Data Loading

A thin, focused module (~63 lines) responsible for reading geographic grids into the `(lats, lons, grid)` triple that the rest of the library consumes.

| Function | Format | Notes |
|---|---|---|
| `list_netcdf_variables(filename)` | NetCDF4 | Convenience helper: returns a list of variable name strings in the file. |
| `load_netcdf_grid(filename, lat_var, lon_var, data_var)` | NetCDF4 | Default variable names are `lat`, `lon`, `z` (matching ETOPO conventions). Caller must supply the correct names for other datasets (e.g. `y`, `x`, `z` for GMT grids). |
| `load_tiff_grid(filename)` | GeoTIFF | Reads the first band. Assumes an equirectangular projection spanning -180°→180° longitude, 90°→-90° latitude. Requires `rasterio`. |

All loaders return:
- `lats`: 1-D array, **must be sorted** (ascending) for `RegularGridInterpolator`.
- `lons`: 1-D array, sorted ascending.
- `grid`: 2-D array of shape `(len(lats), len(lons))`.

---

### `displacement.py` — Radial Displacement & Vertex Coloring

This is where the geographic data meets the 3D geometry (~229 lines).

#### Coordinate conventions

The library uses a right-handed Cartesian system centred at the origin:
- **x** → 0° longitude (prime meridian)
- **y** → 90° E longitude
- **z** → north pole

Conversion from Cartesian to geographic:
```
r   = ‖(x, y, z)‖
lat = arcsin(z / r)       (degrees)
lon = atan2(y, x)          (degrees)
```

This convention is consistent across `displace_vertices`, `assign_vertex_colors`, `assign_vertex_colors_image`, and `plot_vertex_distribution`.

#### Dateline wrapping (`_wrap_longitude`)

An internal helper that pads the longitude axis and grid to handle interpolation across the ±180° dateline. It replicates the first/last column of the grid at the opposite boundary with appropriate longitude offsets so that `RegularGridInterpolator` has continuous data across the seam.

#### Displacement pipeline

```python
scale = calculate_displacement_scale(model_radius_mm, earth_radius_km, vertical_exagg)
vertices = displace_vertices(vertices, lats, lons, grid, scale)
```

**`calculate_displacement_scale(model_radius_mm, earth_radius_km, vertical_exagg)`**

Computes: `(model_radius_mm / (earth_radius_km × 1000)) × vertical_exagg`

This converts real-world elevation values (in metres, relative to the reference radius) into millimetre-scale displacements on the model, multiplied by the vertical exaggeration factor. Typical exaggeration values for a printable globe are 20–50×.

**`displace_vertices(vertices, lats, lons, grid, scale, ...)`**

For each vertex:
1. Compute current radius `r` and geographic coordinates `(lat, lon)`.
2. Interpolate the grid value at `(lat, lon)` using `scipy.interpolate.RegularGridInterpolator`.
3. Compute new radius: `r_new = r + scale × grid_value`.
4. Rescale the vertex: `vertex_new = unit_vector × r_new`.

Supports chunked processing with a `tqdm` progress bar (controlled by `show_progress` and `chunk_size` parameters). The interpolation method can be changed via `interp_method` (default: `'linear'`).

#### Vertex coloring

Two independent coloring strategies:

**`assign_vertex_colors(vertices, lats, lons, grid, colormap, norm, vmin, vmax, ...)`**

Samples a *different* grid (e.g. seismic velocity anomaly) at each vertex's geographic location via `RegularGridInterpolator`, normalises the value, and maps it through a `matplotlib` colormap. Supports:
- Custom `Normalize` objects (e.g. `BoundaryNorm` for discrete classes).
- Custom `vmin`/`vmax` for linear normalisation.
- Both named colormaps (`'viridis'`) and `Colormap` objects (including discretised ones via `plt.get_cmap('RdBu_r', 7)`).

Returns `(N, 3)` RGB float64 array in [0, 1].

**`assign_vertex_colors_image(vertices, image_path, ...)`**

Samples an **equirectangular image file** at each vertex using nearest-neighbour lookup. The image coordinate mapping is:
```
v = (90 - lat) / 180 × (height - 1)    (row index, north→south)
u = (lon + 180) / 360 × (width - 1)    (column index, west→east)
```

Handles uint8, float, grayscale, and RGBA inputs automatically. Returns `(N, 3)` RGB float64 in [0, 1].

**`modify_vertex_colors(vertices, colors, selection_function, faces=None, selection_function_kwargs=None, ...)`**
*(Alias: `modify_vertex_colours`)*

Modifies vertex colors selectively. Accepts a selection function or a registered name (e.g. `'inward_facing'`, `'outward_facing'`) to obtain indices of vertices that should be affected, then applies either a grid, an image, or a constant color to those vertices, returning the fully modified color array.

**Selection Functions & Registry:**
- `select_inward_facing(vertices, faces, **kwargs)`: Vectorized function returning indices of vertices belonging to inward-facing faces ($\mathbf{n} \cdot \mathbf{c} < 0$).
- `select_outward_facing(vertices, faces, **kwargs)`: Vectorized function returning indices of vertices belonging to outward-facing faces ($\mathbf{n} \cdot \mathbf{c} > 0$).
- `register_selection_function(name, func)`: Registers a custom selection callable to the global `SELECTION_REGISTRY`.

---

### `magnets.py` — Magnet Insertion & Position Optimization

This module manages the placement and insertion of magnets into globe hemispheres so they can be magnetically assembled. It uses bisection search to find the optimal magnet positions directly from the outer 3D geometry of the globe, with no dependency on raw grids or scale parameters.

#### Position Optimization

**`optimize_magnet_positions(longitudes, outer_mesh, r_enc, h_boss, bisection_iters)`**

For each target longitude on the equatorial cut plane, this function uses a bisection search (binary search) to find the maximum distance $d$ from the origin where a boss cylinder of radius `r_enc` and height `h_boss` is completely contained within the outer sphere's displaced surface.
- Checks containment at multiple check-points on the top and bottom caps of the boss cylinder.
- Uses `outer_mesh.contains(global_pts)` to perform fast and precise geometric containment checks directly on the watertight displaced outer mesh.
- Returns a list of optimized `(x, y)` center coordinates.

**`find_valid_magnet_positions_no_bosses(outer_mesh, inner_mesh, r_enc, h_boss, step_degrees=2, n_magnets=3, min_magnets=2, min_angular_spacing=60.0, ...)`**

Steps around the model cut-plane in `step_degrees` increments and checks containment of a candidate magnet void completely within the solid shell of the hollowed globe (inside `outer_mesh` and outside `inner_mesh`). It then uses a backtracking optimization algorithm to find a subset of candidate angles that maximizes spacing uniformity while respecting `min_angular_spacing`. Raises `ValueError` if fewer than `min_magnets` can be placed.

#### Magnet Insertion

**`insert_magnets_into_hemispheres(top_mesh, bottom_mesh, outer_vertices, outer_faces, diameter, height, n_magnets, position, ...)`**

Orchestrates the boolean modification of the top and bottom hollow hemispheres:
1. Determines longitudes for the magnets (either a single start longitude with `n_magnets` spaced evenly, or a custom list of positions).
2. Optimizes the magnet centers on the XY cut plane:
   - If `add_bosses=True`, utilizes `optimize_magnet_positions`.
   - If `add_bosses=False` (magnet placement without adding material/bosses), utilizes `find_valid_magnet_positions_no_bosses` to find positions directly in the solid shell.
3. Generates the boss cylinders (if `add_bosses=True`) and void cylinders for each position:
   - For the top hemisphere, bosses are unioned (if added) and voids are subtracted from the solid shell.
   - For the bottom hemisphere, the same coordinate bosses are unioned (if added) and corresponding voids are subtracted.
4. Performs these boolean operations using the `trimesh` boolean module.
5. Returns a tuple of `(top_mesh_with_magnets, bottom_mesh_with_magnets)`.

#### Calibration Test Piece

**`generate_magnet_test_piece(diameter, height, horizontal_tolerance, vertical_tolerance, vertical_offset, min_thickness, output_path)`**

Generates a simple cylinder containing a single magnet void. Useful for test-printing to verify tolerances before printing a large globe.

---

### `io.py` — File Export

Two export formats (~96 lines), chosen based on whether vertex colors are needed:

#### `write_stl_binary(filename, vertices, faces)`

Writes a standard binary STL. Each triangle is stored with its computed face normal (cross product of two edge vectors). No color support — suitable for single-material prints.

#### `write_obj_with_vertex_colors(filename, vertices, faces, colors, center, fix_normals)`

Writes an OBJ file using the vertex-color extension (`v x y z r g b`). OBJ indices are 1-based.

> [!IMPORTANT]
> The `fix_normals` parameter defaults to **False**.  For manifold meshes from boolean operations (e.g. `create_hollow_hemispheres`), normals are already correct and must **not** be overridden — `fix_face_chirality` would flip the inner shell's faces outward, destroying the manifold and causing slicers to fill the hollow.  Set `fix_normals=True` only for simple convex meshes.

**Internal helper:**

`fix_face_chirality(vertices, faces, center)` iterates over every face, computes the face normal via cross product, and checks whether the normal points toward or away from `center` (via dot product with the centroid-to-centre vector). Faces pointing inward are flipped by swapping the last two vertex indices.

---

### `plot.py` — Visual QA

A single utility function (~31 lines):

**`plot_vertex_distribution(vertices, title, sample_size)`**

Converts vertex positions to `(lat, lon)` and plots them as a scatter plot. For large meshes, a random subset of `sample_size` points is shown to keep rendering fast.

---

### `__init__.py` — Public API

Re-exports all user-facing functions from the four core modules. The `__all__` list controls star-imports. Only the following are considered public API:

From **mesh**: `generate_sphere_points_fibonacci`, `generate_sphere_points_icosahedron`, `resize_globe`, `hollow_mesh`, `combine_subtractive_globes`, `compute_scale_factor`, `invert_chirality`, `split_mesh_hemispheres`, `create_hollow_hemispheres`

From **grid**: `list_netcdf_variables`, `load_netcdf_grid`, `load_tiff_grid`

From **displacement**: `displace_vertices`, `displace_by_points`, `displace_near_lines`, `displace_by_polygons`, `assign_vertex_colors`, `assign_vertex_colors_image`, `calculate_displacement_scale`, `modify_vertex_colors`, `modify_vertex_colours`, `select_inward_facing`, `select_outward_facing`, `register_selection_function`

From **io**: `write_stl_binary`, `write_obj_with_vertex_colors`

From **plot**: `plot_vertex_distribution`

From **magnets**: `insert_magnets_into_hemispheres`, `generate_magnet_test_piece`, `find_valid_magnet_positions_no_bosses`

Internal helpers (`create_icosahedron`, `subdivide_icosahedron`, `midpoint`, `project_vertices_to_sphere`, `create_inner_mesh`, `fix_face_chirality`, `_wrap_longitude`, `optimize_magnet_positions`) are **not** exported and should not be imported directly by users.

---

## 🔄 End-to-End Pipeline

The following diagram shows the full data-flow for producing a 3D-printable, colored, hollow, split globe:

```mermaid
flowchart TD
    A["1. Generate outer sphere<br/><code>generate_sphere_points_fibonacci(n, radius_mm)</code>"] --> B
    A2["Generate inner sphere<br/><code>generate_sphere_points_fibonacci(n_inner, radius_mm * inner_scale)</code>"] --> F

    B["2. Load geographic grid<br/><code>load_netcdf_grid(file)</code>"] --> C

    C["3. Calculate displacement scale<br/><code>calculate_displacement_scale(radius_mm, earth_r_km, exagg)</code>"] --> D

    D["4. Displace outer vertices<br/><code>displace_vertices(vertices, lats, lons, grid, scale)</code>"] --> E

    E["4.5. Displace near lines / polygons (optional)<br/><code>displace_near_lines(vertices, shp, displacement, width_degrees)</code>"] --> F

    F["5. Split outer & boolean hollow<br/><code>create_hollow_hemispheres(outer_v, outer_f, inner_v, inner_f)</code>"] --> G

    G["6. Assign colors to each half<br/><code>assign_vertex_colors(half.vertices, ...)</code><br/>or <code>assign_vertex_colors_image(...)</code>"] --> H

    H["7. Export to outputs/ folder<br/><code>write_obj_with_vertex_colors(file, v, f, colors)</code>"]
```

### Step-by-step (with reference parameters)

#### 1. Generate base spheres

```python
outer_vertices, outer_faces = generate_sphere_points_fibonacci(1_000_000, model_radius_mm)
inner_vertices, inner_faces = generate_sphere_points_fibonacci(20_000, model_radius_mm * 0.8)
```

The outer sphere uses a high vertex count for surface detail; the inner sphere can be much coarser since it only defines the void boundary. `inner_scale` (0.8 here) controls wall thickness as a fraction of the radius.

#### 2. Load the geographic grid

```python
topo_lats, topo_lons, topo_grid = load_netcdf_grid(
    "ETOPO_2022_v1_60s_N90W180_surface.nc",
    lat_var='lat', lon_var='lon', data_var='z'
)
```

For the coloring grid (if separate from the displacement grid):

```python
c_lats, c_lons, c_grid = load_netcdf_grid(
    "s40_depth_slice_2850.grd",
    lat_var='y', lon_var='x', data_var='z'
)
```

#### 3. Calculate displacement scale

```python
scale = calculate_displacement_scale(model_radius_mm, earth_radius_km=6371.0, vertical_exagg=30)
```

#### 4. Displace outer vertices

```python
outer_vertices = displace_vertices(
    outer_vertices, topo_lats, topo_lons, topo_grid, scale, show_progress=True
)
```

Only the outer shell is displaced. The inner shell remains a smooth sphere.

> [!IMPORTANT]
> **Displacement Validation**: All displacement functions (`displace_vertices`, `displace_by_points`, `displace_near_lines`, and `displace_by_polygons`) validate that no vertex is translated deeper than or to the origin. If a negative displacement exceeds the vertex's current distance from the origin (new radius <= 0), a `ValueError` is raised to prevent invalid mesh topologies.

#### 4.5. Specialized Shapefile & Coordinate Displacement (optional)

Depending on the geometry type, you can use one of three tailored functions:

##### A. Points & Coordinate Lists (`displace_by_points`)
Displaces vertices close to discrete points (either a shapefile containing Point/MultiPoint geometries or an `(N, 2)` array/list of `(lon, lat)`):
```python
outer_vertices = displace_by_points(
    outer_vertices,
    points_data="../inputs/my_points.shp",  # or numpy array [[lon1, lat1], ...]
    displacement=1.5,
    radius_degrees=1.0
)
```

##### B. Lines & Borders (`displace_near_lines`)
Displaces vertices close to (within a specified ribbon width of) line or polygon boundaries:
```python
outer_vertices = displace_near_lines(
    outer_vertices,
    shapefile_path="../inputs/coastlines/ne_110m_coastline.shp",
    displacement=1.0,
    width_degrees=0.5
)
```

##### C. Closed Polygons (`displace_by_polygons`)
Displaces vertices inside or outside closed polygons (Polygons/MultiPolygons):
```python
outer_vertices = displace_by_polygons(
    outer_vertices,
    shapefile_path="../inputs/land/ne_110m_land.shp",
    displacement=1.0,
    displace_inside=True  # True to displace inside land, False for oceans
)
```

#### 5. Split and hollow into hemispheres

```python
top_half, bottom_half = create_hollow_hemispheres(
    outer_vertices, outer_faces,
    inner_vertices, inner_faces,
    engine='manifold'       # recommended boolean engine
)
```

This single call handles the correct order of operations internally:
1. Splits the displaced outer shell at the equator with a capped plane cut.
2. Boolean-subtracts the smooth inner sphere from each half.
3. Returns two watertight, manifold hollow hemispheres.

The `manifold` boolean engine creates its own triangulation for the annular cap
(the flat ring between the outer and inner shells), so no additional cap
refinement is needed.

#### 6. Color each hemisphere

Colors should be applied **after** splitting because the split operation creates new vertices at the cut plane that weren't in the original mesh.

```python
# Grid-based coloring
top_colors = assign_vertex_colors(
    top_half.vertices, c_lats, c_lons, c_grid,
    colormap=plt.get_cmap('RdBu_r', 7), vmin=-2, vmax=2
)

# OR image-based coloring
top_colors = assign_vertex_colors_image(top_half.vertices, '../outputs/demo_texture.png')
```

#### 7. Export

```python
write_obj_with_vertex_colors('../outputs/globe_top.obj', top_half.vertices, top_half.faces, top_colors)
write_obj_with_vertex_colors('../outputs/globe_bottom.obj', bottom_half.vertices, bottom_half.faces, bottom_colors)
```

---

## 📓 Notebook Workflows

Two example notebooks live in `examples/`:

### `tomo_globe_3d.ipynb`

Demonstrates the **tomography globe** workflow — a globe with ETOPO topography displacement, a 1mm step at the coastlines, and vertex colors derived from a seismic tomography depth slice (e.g. S40RTS at 2850 km depth). This notebook uses `assign_vertex_colors` with:
- A `BoundaryNorm` for discrete classification (`blue / white / red`), or
- A discretised continuous colormap (`plt.get_cmap('RdBu_r', 7)`).

The notebook includes a 2D preview (`pcolormesh`) of the color grid before applying it to the 3D model.

### `demo_split_globe_image.ipynb`

Demonstrates **image-based coloring** using `assign_vertex_colors_image`. It programmatically generates a test equirectangular gradient image, generates a displaced sphere, hollows it using the subtractive approach with `resize_globe` and `combine_subtractive_globes`, splits it, and exports as OBJ to the `outputs/` directory.

Both notebooks use `%autoreload 2` for iterative development.

---

## 📐 Key Concepts & Design Decisions

### Coordinate system

The library uses a **right-handed Cartesian** system centred at the origin, with the z-axis through the north pole. This matches the mathematical convention for spherical coordinates and ensures consistency with `ConvexHull` and `trimesh`.

### Units

The canonical working unit is **millimetres** for model space (radii, displacements) because 3D printers universally use mm. Real-world data is assumed to be in **metres** for elevation / depth (the standard for datasets like ETOPO). The `calculate_displacement_scale` function handles the km→m→mm conversion internally.

### Why three hollowing approaches?

**Boolean hemisphere pipeline** (`create_hollow_hemispheres`) is the recommended approach for 3D printing. It splits the outer mesh first, then boolean-subtracts the inner sphere from each half. This produces properly manifold, watertight hemispheres. The boolean operation is performed by the `manifold3d` engine (or Blender as a fallback).

**Subtractive combination** (`combine_subtractive_globes`) is fast and deterministic — it simply concatenates vertex and face arrays with inverted chirality on the inner shell. It produces a mesh that *looks* hollow and is suitable for whole-globe visualisation. However, **it cannot be combined with `split_mesh_hemispheres`** for 3D printing because the equatorial cap seals the inner cavity.

**Boolean difference** (`hollow_mesh`) performs a whole-globe boolean subtraction. Useful for exporting a complete hollow globe without splitting, but slower and more fragile than the subtractive approach.

### Face chirality

In STL and OBJ, the **winding order** of a triangle's vertices determines the direction of its face normal (right-hand rule). Outward-pointing normals are essential for correct slicer behaviour. The library handles this in several places:
1. `generate_sphere_points_fibonacci` / `generate_sphere_points_icosahedron` — use `_fix_sphere_normals()`, a fast vectorised dot-product check, to guarantee outward normals.
2. `invert_chirality` — used by `combine_subtractive_globes` to flip the inner shell's normals inward.
3. `fix_face_chirality` — available via `write_obj_with_vertex_colors(fix_normals=True)` for simple convex meshes. **Not applied by default** to avoid destroying manifold geometry from boolean operations.
4. `create_hollow_hemispheres` — calls `trimesh.fix_normals()` on both input meshes before boolean operations.

### Vertex colors in OBJ

The OBJ format does not have a formal vertex color standard, but a widely supported convention appends `r g b` values to each `v` line: `v x y z r g b`. This is supported by MeshLab, Blender, and PrusaSlicer / BambuStudio / OrcaSlicer.

### Fibonacci vs icosahedron

| | Fibonacci | Icosahedron |
|---|---|---|
| **Density uniformity** | Very good (near-uniform) | Excellent (exactly uniform triangles) |
| **Vertex count control** | Continuous (any `n`) | Discrete (exponential growth with subdivisions) |
| **Typical use** | High-resolution production globes | Lower-resolution or algorithmically regular meshes |
| **Face generation** | `ConvexHull` (may produce slivers near poles) | Recursive subdivision (all triangles similar) |

For 3D printing, the Fibonacci lattice at ~1M points is the standard choice.

---

## 🧪 Testing

The test suite lives in `tests/` and uses `pytest`.

### Test coverage by module

| Test file | Module | Key tests |
|---|---|---|
| `test_mesh.py` | `mesh.py` | Fibonacci generation (vertex count, radii), icosahedron subdivision, outward-facing normals (positive volume), `resize_globe`, `compute_scale_factor`, `project_vertices_to_sphere`, `create_inner_mesh`, `split_mesh_hemispheres` (watertightness, z-bounds), `create_hollow_hemispheres` (watertight, correct volume, z-bounds) |
| `test_displacement.py` | `displacement.py` | `displace_vertices` (constant grid → predictable radius change), `assign_vertex_colors` (output shape & range), `assign_vertex_colors_image` (mocked image, coordinate mapping) |
| `test_grid.py` | `grid.py` | `list_netcdf_variables` and `load_netcdf_grid` using mocked `netCDF4.Dataset` |
| `test_io.py` | `io.py` | `write_stl_binary` (binary validation, size check, normals), `fix_face_chirality` (vectorized chirality checking), `write_obj_with_vertex_colors` (correct format, lines count) |
| `test_magnets.py` | `magnets.py` | `optimize_magnet_positions` (bisection distance check), `insert_magnets_into_hemispheres` (watertightness, volume bounds), `generate_magnet_test_piece` (height/radius bounds, watertightness) |

### Running tests

```bash
conda activate pygmt
pytest
```

### Testing philosophy

- External data dependencies (NetCDF files, images) are **mocked** so tests run without large data files.
- Geometry tests verify invariants (e.g. all vertices lie on the sphere, bounding box shrinks after inner mesh creation) rather than comparing exact floating-point coordinates.

---

## ⚡ Performance Optimization (Vectorization & Parallelization)

To support high-resolution meshes (e.g., millions of vertices/faces) and rapid generation cycles, `globe3d` uses high-performance CPU optimizations:

### 1. Vectorized Geometry Generation
- Recursive subdivision (`subdivide_icosahedron`) and face normal alignment (`_fix_sphere_normals`, `fix_face_chirality`) are implemented using vectorized NumPy matrix operations. This avoids slow Python loops, reducing generation times for level 6/7 spheres to milliseconds.

### 2. Parallelized Grid Interpolation
- Geographic grid lookup and interpolation (`displace_vertices`, `assign_vertex_colors`, shapefile-based functions) are parallelized on the CPU using a `ThreadPoolExecutor` or `_parallel_sjoin`.
- All displacement functions accept a `num_threads` argument:
  - `num_threads=-1` (default): Uses all available CPU cores.
  - `num_threads=1`: Synchronous single-threaded execution.
  - `num_threads=N`: Restricts execution to `N` worker threads.

### 3. Vectorized File Writers
- `write_stl_binary`: Uses a structured NumPy array (`np.dtype`) to serialize and write binary STL facets in a single call to `file.write()`, accelerating disk I/O.
- `write_obj_with_vertex_colors`: Replaces slow loop-based file writing with `np.savetxt`, formatting and flushing coordinates, colors, and faces in bulk.

---

## ⚓ Git Hook: Notebook Output Stripping

To keep the repository size small and avoid diff conflicts, a pre-commit hook automatically strips all outputs and execution counts from Jupyter notebooks (`.ipynb` files) staged for commit.

- **Hook location**: `.git/hooks/pre-commit` (which calls `.git/hooks/strip_notebooks.py`).
- **Behavior**: Detects staged `.ipynb` files, sets `"outputs"` to `[]` and `"execution_count"` to `null` for all code cells, and automatically re-stages the cleaned notebooks before the commit finishes.

---

## 🤝 Keeping Documentation Live

Both this `DEVELOPER_GUIDE.md` and the repository-level `AGENTS.md` must be kept up-to-date with any structural or architectural changes. When you:

- Add or rename a public function → update the module reference table and `__init__.py` exports list in this guide.
- Change the pipeline order or add a new step → update the pipeline diagram and step-by-step walkthrough.
- Introduce a new module → add a section under "Module-by-Module Reference" and update the dependency graph.
- Change testing patterns or add a test file → update the testing section.

Future agents and contributors should review both documents to quickly onboard onto the project.
