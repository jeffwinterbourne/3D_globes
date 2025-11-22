# globe3d

A Python library for creating 3D models of globes with surfaces perturbed by geographic displacement grids.

## Features

*   **Sphere Generation**: Create spheres using Fibonacci lattice or subdivided icosahedron.
*   **Displacement**: Displace vertices based on NetCDF or TIFF grids.
*   **Coloring**: Assign vertex colors based on grid values.
*   **Hollowing**: Create hollow globes for 3D printing.
*   **Export**: Save models as binary STL or OBJ with vertex colors.

## Installation

1.  Clone the repository:
    ```bash
    ```bash
    pip install .
    ```

## Usage

See `notebooks/demo_fibonacci.ipynb` for a complete example.

### Basic Example

```python
from globe3d import generate_sphere_points_fibonacci, displace_vertices, write_stl_binary
import numpy as np

# 1. Generate sphere
vertices, faces = generate_sphere_points_fibonacci(n_points=10000, radius=1.0)

# 2. Create dummy grid (replace with load_netcdf_grid)
lats = np.linspace(-90, 90, 180)
lons = np.linspace(-180, 180, 360)
grid = np.zeros((180, 360))
grid[90, 180] = 0.1 # Bump

# 3. Displace
vertices = displace_vertices(vertices, lats, lons, grid, scale=1.0)

# 4. Export
write_stl_binary("globe.stl", vertices, faces)
```

## Requirements

*   numpy
*   matplotlib
*   scipy
*   tqdm
*   netCDF4
*   rasterio (optional, for TIFF support)
*   trimesh
*   cmocean
