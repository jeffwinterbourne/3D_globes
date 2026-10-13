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
    - `mesh.py`: `GlobeModel` (unified constructor, `_MeshProxy` for inner/outer shells, `GlobeModel.from_paleo()`, `configure_magnets()`, `export()`, `export_hemispheres()`), sphere generation, hollowing, splitting.
    - `grid.py`: `GeographicGrid` data loading (NetCDF, TIFF).
    - `displacement.py`: `Displacer` / `Colourer` class hierarchies, `GridDisplacer` (with `coastline_step`), `ImageColourer` (file, PIL Image, array), `SymbolColourer` (tangent-plane gnomonic projection, SVG/polygon support, `reference='modern'|'paleo'`), `PoleLabelColourer` (undistorted polar 'N'/'S' glyphs), `TextColourer` (typographic text with TTF font, `height_degrees`, `angle`, fill/stroke styling, paleo/modern coordinates), unit-aware `calculate_displacement_scale(grid_units=...)`.
    - `reconstruction.py`: `PlateModel` (`gplately`/`pygplates` integration), deep-time coordinate and raster reconstruction (`reconstruct_points()`, `reconstruct_grid()`).
    - `image.py`: Spherical vector symbol rendering (`add_svg_symbol_spherical()`, `add_pole_markers()`), texture preprocessing for 3D printing (`undo_hillshading()`, `simplify_image_median()`, `simplify_image_bilateral()`, `simplify_colors()`, `render_2d_array_as_rgb()`).
    - `datasets.py`: Builtin catalog and fetchers for Earth, planetary, geophysics, and `datasets.paleo` (Scotese PALEOMAP PaleoDEMs, PaleoAtlas textures, plate models).
    - `filaments.py`: Full-spectrum optical filament mixing (`mix_filament_pair()`, `mix_filaments()`, `create_filament_palette()`, `match_filament_color()`), banded hypsometric colormaps (`create_banded_colormap()`, `create_elevation_banded_colormap()`, `apply_banded_colormap()`), swatch and colorbar plotting (`plot_filament_palette()`, `plot_banded_colormap_preview()`).
    - `presets.py`: Centralized domain presets, base filament libraries (`FILAMENT_PRESETS`), default elevation zones (`DEFAULT_ELEVATION_BANDS`, `DEFAULT_ELEVATION_BOUNDARIES`), and printer hardware templates (`get_printer_profile()`). Defaults and presets must never be baked directly into computational code.
    - `widgets.py`: Interactive Jupyter notebook widgets and GUI components (`InteractiveColormapBuilder`).
    - `magnets.py`: `MagnetSettings` (`allow_bosses`), multi-objective optimization and insertion of magnet voids with boss count and material minimization.
    - `io.py`: Low-level STL, OBJ, and 3MF file export (with OrcaSlicer / Snapmaker U1 multi-color FullSpectrum filament mixing, 16-slot ceiling enforcement, white snapping, layer interleaving, and hardware profile integration).
    - `plot.py`: Visualization (`plot_vertex_distribution()`, `plot_globe_preview()`).
- **Separation of Backend and Frontend**: Core calculation and geometry modules (`filaments.py`, `mesh.py`, `displacement.py`, `grid.py`, `io.py`) must strictly remain headless backend logic with no direct GUI or `ipywidgets` dependencies. All interactive UI, Jupyter widgets, and frontend components must reside in dedicated frontend modules (`widgets.py`). Presets and defaults must be maintained in `presets.py`.
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
