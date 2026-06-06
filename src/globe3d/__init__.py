"""globe3d: A library for generating 3D printable globes with exaggerated topography.

This library processes geographic grid data (NetCDF, TIFF) and applies it to
spherical meshes, handling displacement, vertex coloring, and hollowing for
3D printing.
"""

from .grid import GeographicGrid
from .displacement import (
    Displacer,
    GridDisplacer,
    PointDisplacer,
    LineDisplacer,
    PolygonDisplacer,
    Colourer,
    GridColourer,
    ImageColourer,
    ConstantColourer,
    select_inward_facing,
    select_outward_facing,
    register_selection_function,
    cartesian_to_spherical,
    calculate_displacement_scale,
)
from .magnets import MagnetSettings, generate_magnet_test_piece
from .mesh import GlobeModel
from .plot import plot_vertex_distribution
from . import datasets

__all__ = [
    "GeographicGrid",
    "Displacer",
    "GridDisplacer",
    "PointDisplacer",
    "LineDisplacer",
    "PolygonDisplacer",
    "Colourer",
    "GridColourer",
    "ImageColourer",
    "ConstantColourer",
    "select_inward_facing",
    "select_outward_facing",
    "register_selection_function",
    "cartesian_to_spherical",
    "calculate_displacement_scale",
    "MagnetSettings",
    "generate_magnet_test_piece",
    "GlobeModel",
    "plot_vertex_distribution",
    "datasets",
]
