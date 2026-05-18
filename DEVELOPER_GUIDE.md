# Developer Guide - 3D Globes

Welcome to the `globe3d` project! This guide provides an overview of the architecture and workflow for developing and maintaining the codebase.

## 📖 Overview

`globe3d` is a Python package designed to generate 3D models of globes, applying real-world geographic elevation data to deform the sphere, adding coloring, and processing the mesh (hollowing, splitting) for 3D printing or rendering.

## 🏗️ Architecture

The core modules are located in `src/globe3d/`:

1. **`mesh.py`**: Handles base geometry creation (Fibonacci spheres, subdivided icosahedrons). It also handles global mesh operations like resizing, chirality inversion, hollowing, and hemisphere splitting.
2. **`grid.py`**: Utilities for loading global grid data such as NetCDF or TIFF (e.g., ETOPO elevation data).
3. **`displacement.py`**: Applies real-world elevation grids to deform the spherical vertices. Includes helpers to calculate appropriate scaling factors (like converting 6371km Earth radius to a millimeter-scale model). Also handles vertex coloring mapping.
4. **`io.py`**: Input/Output operations for exporting models to `.stl` and `.obj` formats. Includes specialized functions to write OBJ files with vertex colors.
5. **`plot.py`**: Provides visual checks for point distribution and vertex density using `matplotlib`.

## 🛠️ Typical Workflow

1. **Generate a Base Sphere**: Use `generate_sphere_points_fibonacci(n_points, radius_mm)` to create a dense, uniformly distributed base sphere of the desired printable size.
2. **Load the Elevation Grid**: Use `load_netcdf_grid()` to get the global displacement field.
3. **Displace Vertices**: Use `calculate_displacement_scale()` to find the correct scalar, then deform the vertices using `displace_vertices()`.
4. **Assign Vertex Colors (Optional)**: Map a 2D image (e.g., satellite imagery or a procedural gradient) onto the 3D vertices using `assign_vertex_colors_image()`.
5. **Mesh Processing**: Combine vertices and faces into a `trimesh.Trimesh` object. Apply hollowing or use `split_mesh_hemispheres()` to prepare the model for flat-bed 3D printing.
6. **Export**: Export using `write_obj_with_vertex_colors()` or export as STL.

## 🧪 Testing

Continuous testing is vital to maintaining `globe3d`. We rely on `pytest`. 
- **Requirement**: **Always run tests** after every significant change or iteration to ensure no regressions occur.
- Run tests via `pytest` from the root directory.

## 🤝 Keeping Documentation Live

This `DEVELOPER_GUIDE.md` and the repository-level `agents.md` must be kept up-to-date with any structural or architectural changes. Future agents should review both documents to quickly onboard onto the project.
