"""globe3d: A library for generating 3D printable globes with exaggerated topography.

This library processes geographic grid data (NetCDF, TIFF) and applies it to
spherical meshes, handling displacement, vertex coloring, and hollowing for
3D printing.
"""

from .mesh import (
    generate_sphere_points_fibonacci,
    generate_sphere_points_icosahedron,
    resize_globe,
    hollow_mesh,
    combine_subtractive_globes,
    compute_scale_factor,
    invert_chirality,
    split_mesh_hemispheres,
    create_hollow_hemispheres
)
from .grid import (
    list_netcdf_variables,
    load_netcdf_grid,
    load_tiff_grid
)
from .displacement import (
    displace_vertices,
    displace_by_points,
    displace_near_lines,
    displace_by_polygons,
    assign_vertex_colors,
    assign_vertex_colors_image,
    calculate_displacement_scale,
    cartesian_to_spherical,
    modify_vertex_colors,
    modify_vertex_colours,
    select_inward_facing,
    select_outward_facing,
    register_selection_function
)
from .io import (
    write_stl_binary,
    write_obj_with_vertex_colors
)
from .plot import (
    plot_vertex_distribution
)
from .magnets import (
    insert_magnets_into_hemispheres,
    generate_magnet_test_piece,
    find_valid_magnet_positions_no_bosses
)

__all__ = [
    "generate_sphere_points_fibonacci",
    "generate_sphere_points_icosahedron",
    "resize_globe",
    "hollow_mesh",
    "combine_subtractive_globes",
    "compute_scale_factor",
    "invert_chirality",
    "split_mesh_hemispheres",
    "create_hollow_hemispheres",
    "list_netcdf_variables",
    "load_netcdf_grid",
    "load_tiff_grid",
    "displace_vertices",
    "displace_by_points",
    "displace_near_lines",
    "displace_by_polygons",
    "assign_vertex_colors",
    "assign_vertex_colors_image",
    "cartesian_to_spherical",
    "modify_vertex_colors",
    "modify_vertex_colours",
    "select_inward_facing",
    "select_outward_facing",
    "register_selection_function",
    "write_stl_binary",
    "write_obj_with_vertex_colors",
    "plot_vertex_distribution",
    "insert_magnets_into_hemispheres",
    "generate_magnet_test_piece",
    "find_valid_magnet_positions_no_bosses",
]
