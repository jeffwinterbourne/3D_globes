# Agent Guide - 3D Globes

This document provides context and instructions for AI agents working on the `globe3d` project.

## Project Purpose
The `globe3d` library is designed to generate 3D printable models of globes with exaggerated topography. It processes geographic grid data (NetCDF, TIFF) and applies it to spherical meshes, handling displacement, vertex coloring, and hollowing for 3D printing.

## Environment
The project uses a Conda environment named `pygmt`.

**Activation:**
```bash
conda activate pygmt
```

**Installation:**
The package should be installed in editable mode to facilitate development:
```bash
pip install -e .
```

**Dependencies:**
- `numpy`, `matplotlib`, `scipy`, `tqdm`, `trimesh`, `cmocean`
- `netCDF4` (Best installed via Conda: `conda install -c conda-forge netcdf4`)
- `rasterio` (Optional, for TIFF support)

## Code Standards
- **Style**: Follow PEP 8 guidelines.
- **Structure**: Keep code modular. Core logic resides in `src/globe3d/`.
    - `mesh.py`: Geometry generation and manipulation.
    - `grid.py`: Data loading.
    - `displacement.py`: Topography application.
    - `io.py`: File export.
    - `plot.py`: Visualization.
- **Docstrings**: All functions and classes must have descriptive docstrings (Google or NumPy style) explaining parameters and return values.
- **Type Hinting**: Use type hints where helpful for clarity.

## Quality & Testing
- **Expectation**: We expect high code quality and reliability.
- **Testing Framework**: `pytest`.
- **Coverage**: Aim for high test coverage (>90%). All new features must include unit tests.
- **Running Tests**:
  ```bash
  pytest tests/
  ```
- **Verification**: Before submitting changes, ensure all tests pass and the code is lint-free.
