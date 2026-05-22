import numpy as np
import pytest
import trimesh
from unittest.mock import MagicMock, patch
import matplotlib.pyplot as plt

from globe3d.mesh import (
    generate_sphere_points_fibonacci,
    create_hollow_hemispheres
)
from globe3d.magnets import (
    _find_optimal_spacing,
    find_valid_magnet_positions_no_bosses,
    insert_magnets_into_hemispheres
)
from globe3d.displacement import (
    select_inward_facing,
    select_outward_facing,
    modify_vertex_colors,
    modify_vertex_colours
)


def test_find_optimal_spacing():
    """Verify that _find_optimal_spacing finds correct evenly-spaced angles and respects minimum spacing."""
    # Test perfect placement case
    valid_angles = [0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0, 270.0, 300.0, 330.0]
    
    # 3 magnets should be placed at 0, 120, 240 (perfectly spaced) or similar symmetric configuration
    subset = _find_optimal_spacing(valid_angles, k=3, min_spacing=60.0)
    assert subset is not None
    assert len(subset) == 3
    
    # Gaps should be exactly 120
    gaps = [subset[1] - subset[0], subset[2] - subset[1], 360.0 + subset[0] - subset[2]]
    for g in gaps:
        assert pytest.approx(g) == 120.0

    # Test case where some angles are not available
    # Remove 120.0. The best we can do for k=3 should still respect min_spacing=60
    valid_angles_no_120 = [0.0, 30.0, 60.0, 90.0, 150.0, 180.0, 210.0, 240.0, 270.0, 300.0, 330.0]
    subset_no_120 = _find_optimal_spacing(valid_angles_no_120, k=3, min_spacing=60.0)
    assert subset_no_120 is not None
    assert len(subset_no_120) == 3
    # Check that spacing is respected
    assert subset_no_120[1] - subset_no_120[0] >= 60.0
    assert subset_no_120[2] - subset_no_120[1] >= 60.0
    assert 360.0 + subset_no_120[0] - subset_no_120[2] >= 60.0

    # Test unsatisfiable constraint case
    subset_fail = _find_optimal_spacing(valid_angles, k=3, min_spacing=150.0)
    assert subset_fail is None


def test_find_valid_magnet_positions_no_bosses():
    """Verify that find_valid_magnet_positions_no_bosses finds valid positions inside a sphere shell."""
    outer_radius = 50.0
    inner_radius = 35.0
    ov, of = generate_sphere_points_fibonacci(400, outer_radius)
    iv, if_ = generate_sphere_points_fibonacci(200, inner_radius)
    
    outer_mesh = trimesh.Trimesh(vertices=ov, faces=of)
    inner_mesh = trimesh.Trimesh(vertices=iv, faces=if_)
    
    r_enc = 3.5
    h_boss = 4.0
    
    centers, chosen_angles = find_valid_magnet_positions_no_bosses(
        outer_mesh=outer_mesh,
        inner_mesh=inner_mesh,
        r_enc=r_enc,
        h_boss=h_boss,
        step_degrees=10.0,
        n_magnets=3,
        min_magnets=2,
        min_angular_spacing=60.0
    )
    
    assert len(centers) == 3
    assert len(chosen_angles) == 3
    for x, y in centers:
        dist = np.hypot(x, y)
        # Radial distance should be strictly within (inner_radius + r_enc) and (outer_radius - r_enc)
        assert dist > inner_radius + r_enc - 1.0
        assert dist < outer_radius - r_enc + 1.0


def test_insert_magnets_no_bosses_end_to_end():
    """Verify hollowing and magnet placement without bosses runs successfully."""
    outer_radius = 40.0
    inner_radius = 30.0
    ov, of = generate_sphere_points_fibonacci(500, outer_radius)
    iv, if_ = generate_sphere_points_fibonacci(200, inner_radius)

    magnet_params = {
        'magnet_diameter': 4.0,
        'magnet_height': 1.5,
        'h_tol': 0.1,
        'v_tol': 0.1,
        'v_offset': 0.2,
        'min_thick': 1.2,
        'n_magnets': 3,
        'min_magnets': 2,
        'min_angular_spacing': 60.0,
        'step_degrees': 10.0,
        'add_bosses': False
    }

    top_mag, bottom_mag = create_hollow_hemispheres(
        ov, of, iv, if_,
        engine='manifold',
        magnet_params=magnet_params
    )

    assert top_mag is not None
    assert bottom_mag is not None
    assert top_mag.is_watertight
    assert bottom_mag.is_watertight
    assert top_mag.volume > 0
    assert bottom_mag.volume > 0


def test_select_inward_outward_facing_vertices():
    """Verify that selection functions correctly identify inward vs outward facing vertices on concentric spheres."""
    # Outer sphere: normals point outwards
    ov, of = generate_sphere_points_fibonacci(100, radius=20.0)
    
    # Inward selection on a standard outward-facing sphere should yield 0 vertices
    # because all normals point outward (dot product > 0)
    inward = select_inward_facing(ov, of)
    outward = select_outward_facing(ov, of)
    
    assert len(inward) == 0
    assert len(outward) == len(ov)

    # If we invert the winding order of the faces, the normals point inward (dot product < 0)
    of_inverted = of[:, [0, 2, 1]]
    inward_inv = select_inward_facing(ov, of_inverted)
    outward_inv = select_outward_facing(ov, of_inverted)
    
    assert len(inward_inv) == len(ov)
    assert len(outward_inv) == 0


def test_modify_vertex_colors():
    """Verify modify_vertex_colors modifies correct subsets of colors."""
    # Set up dummy vertices and colors
    vertices = np.array([
        [10.0, 0.0, 0.0],  # vertex 0
        [-10.0, 0.0, 0.0], # vertex 1
        [0.0, 10.0, 0.0],  # vertex 2
        [0.0, -10.0, 0.0], # vertex 3
    ], dtype=np.float64)
    
    colors = np.zeros((4, 3), dtype=np.float64)  # All black initial colors
    
    # Custom selection function
    def dummy_select(v, f, **kwargs):
        # Select indices where X > 0 (vertex 0 only)
        return np.where(v[:, 0] > 0)[0]
        
    # Test constant coloring
    mod_colors = modify_vertex_colors(
        vertices=vertices,
        colors=colors,
        selection_function=dummy_select,
        constant_color=[1.0, 0.5, 0.0]
    )
    
    assert np.allclose(mod_colors[0], [1.0, 0.5, 0.0])
    assert np.allclose(mod_colors[1], [0.0, 0.0, 0.0])
    assert np.allclose(mod_colors[2], [0.0, 0.0, 0.0])
    assert np.allclose(mod_colors[3], [0.0, 0.0, 0.0])
    
    # Test grid-based coloring (via mocked RegularGridInterpolator or simple data)
    lats = np.array([-90.0, 90.0])
    lons = np.array([-180.0, 180.0])
    grid = np.array([[0.5, 0.5], [1.0, 1.0]])  # Constant high/low grid
    
    mod_colors_grid = modify_vertex_colors(
        vertices=vertices,
        colors=colors,
        selection_function=dummy_select,
        lats=lats,
        lons=lons,
        grid=grid,
        colormap='gray'
    )
    
    # Vertex 0 (lat=0, lon=0) is modified, others remain black
    assert not np.allclose(mod_colors_grid[0], [0.0, 0.0, 0.0])
    assert np.allclose(mod_colors_grid[1], [0.0, 0.0, 0.0])

    # Test British spelling alias
    mod_colors_alias = modify_vertex_colours(
        vertices=vertices,
        colors=colors,
        selection_function=dummy_select,
        constant_color=[0.0, 1.0, 1.0]
    )
    assert np.allclose(mod_colors_alias[0], [0.0, 1.0, 1.0])
