"""globe3d: A library for generating 3D printable globes with exaggerated topography.

This library processes geographic grid data (NetCDF, TIFF) and applies it to
spherical meshes, handling displacement, vertex coloring, and hollowing for
3D printing.
"""

from .grid import GeographicGrid
from .displacement import (
    Displacer,
    ConstantDisplacer,
    GridDisplacer,
    PointDisplacer,
    LineDisplacer,
    PolygonDisplacer,
    Colourer,
    GridColourer,
    ImageColourer,
    ConstantColourer,
    PointColourer,
    LineColourer,
    PolygonColourer,
    SymbolColourer,
    PoleLabelColourer,
    select_inward_facing,
    select_outward_facing,
    register_selection_function,
    cartesian_to_spherical,
    calculate_displacement_scale,
)
from .magnets import MagnetSettings, generate_magnet_test_piece
from .mesh import GlobeModel
from .plot import plot_vertex_distribution, plot_globe_preview
from .reconstruction import PlateModel, reconstruct_points, reconstruct_grid
from .image import (
    add_svg_symbol_spherical,
    add_pole_markers,
    undo_hillshading,
    simplify_image_median,
    simplify_image_bilateral,
    simplify_colors,
    render_2d_array_as_rgb,
)
from .filaments import (
    parse_color,
    color_to_hex,
    rgb_to_lab,
    delta_e_lab,
    mix_filament_pair,
    mix_filaments,
    mix_filament_pairs_vectorized,
    create_filament_palette,
    match_filament_color,
    create_banded_colormap,
    create_elevation_banded_colormap,
    apply_banded_colormap,
    plot_filament_palette,
    plot_banded_colormap_preview,
    FILAMENT_PRESETS,
)
from . import datasets
from . import image
from . import reconstruction
from . import filaments

__all__ = [
    "GeographicGrid",
    "Displacer",
    "ConstantDisplacer",
    "GridDisplacer",
    "PointDisplacer",
    "LineDisplacer",
    "PolygonDisplacer",
    "Colourer",
    "GridColourer",
    "ImageColourer",
    "ConstantColourer",
    "PointColourer",
    "LineColourer",
    "PolygonColourer",
    "SymbolColourer",
    "PoleLabelColourer",
    "select_inward_facing",
    "select_outward_facing",
    "register_selection_function",
    "cartesian_to_spherical",
    "calculate_displacement_scale",
    "MagnetSettings",
    "generate_magnet_test_piece",
    "GlobeModel",
    "plot_vertex_distribution",
    "plot_globe_preview",
    "PlateModel",
    "reconstruct_points",
    "reconstruct_grid",
    "add_svg_symbol_spherical",
    "add_pole_markers",
    "undo_hillshading",
    "simplify_image_median",
    "simplify_image_bilateral",
    "simplify_colors",
    "render_2d_array_as_rgb",
    "parse_color",
    "color_to_hex",
    "rgb_to_lab",
    "delta_e_lab",
    "mix_filament_pair",
    "mix_filaments",
    "mix_filament_pairs_vectorized",
    "create_filament_palette",
    "match_filament_color",
    "create_banded_colormap",
    "create_elevation_banded_colormap",
    "apply_banded_colormap",
    "plot_filament_palette",
    "plot_banded_colormap_preview",
    "FILAMENT_PRESETS",
    "datasets",
    "image",
    "reconstruction",
    "filaments",
]

