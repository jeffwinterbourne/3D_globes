# Agent Guide - 3D Globes

This document provides context and instructions for AI agents working on the `globe3d` project.  Note that this is a
repo level AGENTS.md - the guidance in 3d_globes/AGENTS.md is complementary to this document and includes important 
information about setting up and using python in the lead developer's environment which should not be included in any
documents within the git repository

## Project Purpose
The `globe3d` library is designed to generate 3D printable models of globes with exaggerated topography. It processes geographic grid data (NetCDF, TIFF) and applies it to spherical meshes, handling displacement, vertex coloring, and hollowing for 3D printing.

## Environment
The project uses a Conda environment named `pygmt`.

**Activation:**
```
conda activate pygmt
```

**Installation:**
The package should be installed in editable mode to facilitate development:
```
pip install -e .
```

**Dependencies:**
- `numpy`, `matplotlib`, `scipy`, `tqdm`, `trimesh`, `cmocean`, `geopandas`
- `netCDF4` (Best installed via Conda: `conda install -c conda-forge netcdf4`)
- `rasterio` (Optional, for TIFF support)

## Code Standards
- **Style**: Follow PEP 8 guidelines.
- **Structure**: Keep code modular. Core logic resides in `src/globe3d/`.
    - `mesh.py`: `GlobeModel` (unified constructor, `_MeshProxy` for inner/outer shells, `configure_magnets()`, `export()`, `export_hemispheres()`), sphere generation, hollowing, splitting.
    - `grid.py`: `GeographicGrid` data loading (NetCDF, TIFF).
    - `displacement.py`: `Displacer` / `Colourer` class hierarchies, unit-aware `calculate_displacement_scale(grid_units=...)`.
    - `magnets.py`: `MagnetSettings`, optimization and insertion of magnet voids and bosses.
    - `io.py`: Low-level STL & OBJ file export (called internally by `GlobeModel.export`).
    - `plot.py`: Visualization.
- **Docstrings**: All functions and classes MUST have complete and up-to-date docstrings (Google or NumPy style) explaining all parameters (including kwargs) and return values. When updating a function's signature, you MUST update its docstring concurrently to ensure documentation standards are met.
- **Type Hinting**: Use type hints where helpful for clarity.
- **Performance & Parallelism**: Write vectorized NumPy operations rather than Python loops for geometric calculations and file exporters. Use CPU-based parallelism (with the `num_threads` parameter, default `-1` for all cores) for intensive interpolation operations.

## Quality & Testing
- **Expectation**: We expect high code quality and reliability. Running tests is an expectation with each iteration to ensure no regression.
- **Testing Framework**: `pytest`.
- **Coverage**: Aim for high test coverage (>90%). All new features must include unit tests.
- **Running Tests**:
  ```
  pytest
  ```
- **Verification**: Before submitting changes, ensure all tests pass and the code is lint-free.

## Documentation Maintenance
- **Requirement**: Both this `agents.md` file and the `DEVELOPER_GUIDE.md` file must be kept live and up-to-date with any major architectural or structural changes. Future agents will rely on both documents to understand the current state of the project.
