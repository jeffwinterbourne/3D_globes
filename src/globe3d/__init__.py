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
    select_inward_facing,
    select_outward_facing,
    register_selection_function,
    cartesian_to_spherical,
    calculate_displacement_scale,
)
from .magnets import MagnetSettings, generate_magnet_test_piece
from .mesh import GlobeModel
from .plot import plot_vertex_distribution
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
from . import datasets
from . import image
from . import reconstruction

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
    "select_inward_facing",
    "select_outward_facing",
    "register_selection_function",
    "cartesian_to_spherical",
    "calculate_displacement_scale",
    "MagnetSettings",
    "generate_magnet_test_piece",
    "GlobeModel",
    "plot_vertex_distribution",
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
    "datasets",
    "image",
    "reconstruction",
]
