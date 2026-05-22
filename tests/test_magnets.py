import numpy as np
import pytest
import trimesh
from globe3d.mesh import (
    generate_sphere_points_fibonacci,
    create_hollow_hemispheres
)
from globe3d.magnets import (
    MagnetSettings,
    optimize_magnet_positions,
    insert_magnets_into_hemispheres,
    generate_magnet_test_piece,
    _find_optimal_spacing,
    find_valid_magnet_positions_no_bosses
)


def test_optimize_magnet_positions():
    """Verify that optimization along longitude lines works and finds expected positions on a sphere."""
    radius = 50.0  # 50mm radius
    # Generate outer sphere mesh
    v, f = generate_sphere_points_fibonacci(1000, radius)
    outer_mesh = trimesh.Trimesh(vertices=v, faces=f)
    
    r_enc = 4.0
    h_boss = 5.0
    
    longitudes = [0.0, 90.0, -180.0]
    
    centers = optimize_magnet_positions(
        longitudes=longitudes,
        outer_mesh=outer_mesh,
        r_enc=r_enc,
        h_boss=h_boss,
        bisection_iters=15
    )
    
    assert len(centers) == len(longitudes)
    
    # For a perfect sphere, the maximum radius is radius.
    # Because of the cylinder height h_boss, the top/bottom outer corners of the cylinder
    # are furthest from the origin. They must satisfy: sqrt((d + r_enc)**2 + h_boss**2) <= radius
    # which gives: d <= sqrt(radius**2 - h_boss**2) - r_enc
    expected_d = np.sqrt(radius**2 - h_boss**2) - r_enc
    
    # Check each center matches expected distance and angle
    for (x, y), lon_deg in zip(centers, longitudes):
        dist = np.hypot(x, y)
        # Should be very close to expected distance (within bisection tolerance)
        assert pytest.approx(dist, abs=0.5) == expected_d
        
        angle_rad = np.radians(lon_deg)
        expected_x = expected_d * np.cos(angle_rad)
        expected_y = expected_d * np.sin(angle_rad)
        assert pytest.approx(x, abs=0.5) == expected_x
        assert pytest.approx(y, abs=0.5) == expected_y


def test_insert_magnets_into_hemispheres():
    """Test the end-to-end pipeline of cutting, hollowing, and inserting magnets."""
    outer_radius = 40.0
    inner_radius = 32.0
    ov, of = generate_sphere_points_fibonacci(1000, outer_radius)
    iv, if_ = generate_sphere_points_fibonacci(500, inner_radius)

    # 1. Create hollow hemispheres
    top, bottom = create_hollow_hemispheres(
        ov, of, iv, if_, engine='manifold'
    )
    
    assert top is not None
    assert bottom is not None
    
    # 2. Insert magnets (3 magnets at position 30.0 -> 30, 150, 270)
    top_mag, bottom_mag = insert_magnets_into_hemispheres(
        top_mesh=top,
        bottom_mesh=bottom,
        outer_vertices=ov,
        outer_faces=of,
        diameter=5.0,
        height=2.0,
        n_magnets=3,
        position=30.0,
        horizontal_tolerance=0.1,
        vertical_tolerance=0.1,
        vertical_offset=0.2,
        min_thickness=1.5,
        engine='manifold'
    )
    
    # Check that they are watertight and manifold
    assert top_mag.is_watertight
    assert bottom_mag.is_watertight
    
    # Verify that the meshes are valid and have positive volume
    assert top_mag.volume > 0
    assert bottom_mag.volume > 0
    
    # Check that the bounds of the modified meshes are still correct
    assert top_mag.bounds[0][2] >= -0.01
    assert bottom_mag.bounds[1][2] <= 0.01


def test_create_hollow_hemispheres_with_magnet_params():
    """Verify that create_hollow_hemispheres integrates magnet insertion via magnet_params."""
    outer_radius = 40.0
    inner_radius = 32.0
    ov, of = generate_sphere_points_fibonacci(1000, outer_radius)
    iv, if_ = generate_sphere_points_fibonacci(500, inner_radius)

    magnet_params = MagnetSettings(
        diameter=5.0,
        height=2.0,
        horizontal_tolerance=0.15,
        vertical_tolerance=0.10,
        vertical_offset=0.20,
        min_thickness=1.5,
        n_magnets=3,
        position=0.0
    )

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


def test_generate_magnet_test_piece():
    """Verify that generating the calibration test piece works and produces expected geometry."""
    diameter = 5.0
    height = 2.0
    horizontal_tolerance = 0.15
    vertical_tolerance = 0.1
    vertical_offset = 0.3
    min_thickness = 1.6
    
    test_piece = generate_magnet_test_piece(
        diameter=diameter,
        height=height,
        horizontal_tolerance=horizontal_tolerance,
        vertical_tolerance=vertical_tolerance,
        vertical_offset=vertical_offset,
        min_thickness=min_thickness
    )
    
    assert test_piece is not None
    assert test_piece.is_watertight
    assert test_piece.volume > 0.0
    
    # Expected cylinder dimensions
    r_void = diameter / 2.0 + horizontal_tolerance  # 2.5 + 0.15 = 2.65
    r_enc = r_void + min_thickness  # 2.65 + 1.6 = 4.25
    r_outer = r_enc + 2.0  # 6.25
    h_boss = vertical_offset + (height + vertical_tolerance) + min_thickness  # 0.3 + 2.1 + 1.6 = 4.0
    
    # Check heights and bounds
    # Height should be h_boss
    extents = test_piece.bounding_box.extents
    assert pytest.approx(extents[2], abs=1e-3) == h_boss
    # Radius in X and Y should be r_outer, so extents in X and Y should be 2 * r_outer
    assert pytest.approx(extents[0], abs=1e-3) == 2 * r_outer
    assert pytest.approx(extents[1], abs=1e-3) == 2 * r_outer


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

    magnet_params = MagnetSettings(
        diameter=4.0,
        height=1.5,
        horizontal_tolerance=0.1,
        vertical_tolerance=0.1,
        vertical_offset=0.2,
        min_thickness=1.2,
        n_magnets=3,
        min_magnets=2,
        min_angular_spacing=60.0,
        step_degrees=10.0,
        add_bosses=False
    )

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
