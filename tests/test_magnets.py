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
    find_valid_magnet_positions_no_bosses,
    find_optimized_magnet_positions,
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


def test_find_valid_magnet_positions_variable_thickness():
    """Verify that find_valid_magnet_positions_no_bosses succeeds when the shell has variable thickness.

    Specifically tests when max_inner_radius + r_enc > max_outer_radius - r_enc globally,
    but local continental regions are thick enough to house the magnets.
    """
    outer_radius = 45.0
    ov, of = generate_sphere_points_fibonacci(600, outer_radius)

    # Create an inner shell with variable depth:
    # On one side (x > 0, e.g. continental root), inner radius is deep (32 mm).
    # On the other side (x < 0, e.g. oceanic crust), inner radius is shallow (41 mm).
    iv, if_ = generate_sphere_points_fibonacci(600, 36.5)
    r_in = np.linalg.norm(iv, axis=1)
    unit_iv = iv / r_in[:, None]
    var_r_in = 36.5 - 4.5 * unit_iv[:, 0]  # varies from 32 mm (at x = +1) to 41 mm (at x = -1)
    iv = unit_iv * var_r_in[:, None]

    outer_mesh = trimesh.Trimesh(vertices=ov, faces=of)
    inner_mesh = trimesh.Trimesh(vertices=iv, faces=if_)

    r_enc = 3.45
    h_boss = 3.10

    # Verify global condition that previously caused immediate crash:
    assert np.max(var_r_in) + r_enc > outer_radius - r_enc

    # Strategy: cluster_peaks
    centers, chosen_angles = find_valid_magnet_positions_no_bosses(
        outer_mesh=outer_mesh,
        inner_mesh=inner_mesh,
        r_enc=r_enc,
        h_boss=h_boss,
        step_degrees=5.0,
        n_magnets=2,
        min_magnets=1,
        min_angular_spacing=30.0,
        placement_strategy="cluster_peaks",
    )
    assert len(centers) >= 1
    assert len(chosen_angles) == len(centers)

    # Strategy: margin_weighted
    centers_mw, chosen_angles_mw = find_valid_magnet_positions_no_bosses(
        outer_mesh=outer_mesh,
        inner_mesh=inner_mesh,
        r_enc=r_enc,
        h_boss=h_boss,
        step_degrees=5.0,
        n_magnets=2,
        min_magnets=1,
        min_angular_spacing=30.0,
        placement_strategy="margin_weighted",
    )
    assert len(centers_mw) >= 1

    # Strategy: uniform
    centers_u, chosen_angles_u = find_valid_magnet_positions_no_bosses(
        outer_mesh=outer_mesh,
        inner_mesh=inner_mesh,
        r_enc=r_enc,
        h_boss=h_boss,
        step_degrees=5.0,
        n_magnets=2,
        min_magnets=1,
        min_angular_spacing=30.0,
        placement_strategy="uniform",
    )
    assert len(centers_u) >= 1


def test_candidate_angles_with_tolerance_nudge():
    """Verify that candidate_angles can be nudged using angle_tolerance."""
    outer_radius = 45.0
    ov, of = generate_sphere_points_fibonacci(400, outer_radius)
    iv, if_ = generate_sphere_points_fibonacci(400, 35.0)

    # Push inner shell outward tightly around longitude 90 deg so 90 deg is too thin
    r_in = np.linalg.norm(iv, axis=1)
    unit_iv = iv / r_in[:, None]
    var_r_in = np.where(unit_iv[:, 1] > 0.98, 43.0, 35.0)
    iv = unit_iv * var_r_in[:, None]

    outer_mesh = trimesh.Trimesh(vertices=ov, faces=of)
    inner_mesh = trimesh.Trimesh(vertices=iv, faces=if_)

    r_enc = 3.0
    h_boss = 2.5

    # At exact lon 90, it should fail without tolerance
    with pytest.raises(ValueError):
        find_valid_magnet_positions_no_bosses(
            outer_mesh=outer_mesh,
            inner_mesh=inner_mesh,
            r_enc=r_enc,
            h_boss=h_boss,
            candidate_angles=[90.0],
            angle_tolerance=0.0,
        )

    # With angle_tolerance=25.0, it should nudge away from 90 to a thick region
    centers, chosen_angles = find_valid_magnet_positions_no_bosses(
        outer_mesh=outer_mesh,
        inner_mesh=inner_mesh,
        r_enc=r_enc,
        h_boss=h_boss,
        candidate_angles=[90.0],
        angle_tolerance=25.0,
        step_degrees=2.0,
    )
    assert len(centers) == 1
    assert abs(chosen_angles[0] - 90.0) > 0.1


def test_magnet_settings_allow_bosses_alias():
    """Verify that allow_bosses and add_bosses alias work symmetrically in MagnetSettings."""
    # Default is allow_bosses=True
    s1 = MagnetSettings()
    assert s1.allow_bosses is True
    assert s1.add_bosses is True

    # allow_bosses=False
    s2 = MagnetSettings(allow_bosses=False)
    assert s2.allow_bosses is False
    assert s2.add_bosses is False

    # add_bosses=False (backward compatibility alias)
    s3 = MagnetSettings(add_bosses=False)
    assert s3.allow_bosses is False
    assert s3.add_bosses is False

    # add_bosses=True overrides allow_bosses if explicitly specified
    s4 = MagnetSettings(allow_bosses=False, add_bosses=True)
    assert s4.allow_bosses is True
    assert s4.add_bosses is True


def test_allow_bosses_thin_shell():
    """Verify that allow_bosses=True places bosses on thin shells while allow_bosses=False raises ValueError."""
    ov, of = generate_sphere_points_fibonacci(300, 40.0)
    iv, if_ = generate_sphere_points_fibonacci(300, 39.0)
    om = trimesh.Trimesh(vertices=ov, faces=of)
    im = trimesh.Trimesh(vertices=iv, faces=if_)

    # allow_bosses=False must raise ValueError on thin shell
    with pytest.raises(ValueError, match="too thin"):
        find_valid_magnet_positions_no_bosses(
            om, im, r_enc=3.45, h_boss=3.10, n_magnets=3, allow_bosses=False
        )

    # allow_bosses=True must succeed and flag all magnets as requiring bosses
    centers, angles, boss_flags = find_valid_magnet_positions_no_bosses(
        om, im, r_enc=3.45, h_boss=3.10, n_magnets=3, min_angular_spacing=60.0,
        allow_bosses=True, return_details=True
    )
    assert len(centers) == 3
    assert len(angles) == 3
    assert all(boss_flags)  # All 3 require bosses in a 1mm shell


def test_allow_bosses_minimizes_boss_count_and_protrusion():
    """Verify that allow_bosses minimizes the number of bosses needed and protrusion depth.

    Tests variable-thickness model:
    - For n_magnets=2: both fit in thick regions, so 0 bosses are needed.
    - For n_magnets=3: requires 1 boss in thin region, so exactly 1 boss is created.
    """
    outer_radius = 45.0
    ov, of = generate_sphere_points_fibonacci(500, outer_radius)

    # Shell is thick around x > 0 (inner radius 32mm) and thin around x < 0 (inner radius 41mm)
    iv, if_ = generate_sphere_points_fibonacci(500, 36.5)
    r_in = np.linalg.norm(iv, axis=1)
    unit_iv = iv / r_in[:, None]
    var_r_in = 36.5 - 4.5 * unit_iv[:, 0]
    iv = unit_iv * var_r_in[:, None]

    om = trimesh.Trimesh(vertices=ov, faces=of)
    im = trimesh.Trimesh(vertices=iv, faces=if_)

    r_enc = 3.45
    h_boss = 3.10

    # 1. When n_magnets=2 with min_angular_spacing=30: fits with 0 bosses
    centers2, angles2, boss_flags2 = find_optimized_magnet_positions(
        om, im, r_enc=r_enc, h_boss=h_boss, step_degrees=5.0,
        n_magnets=2, min_magnets=2, min_angular_spacing=30.0,
        allow_bosses=True, return_details=True
    )
    assert len(centers2) == 2
    assert sum(boss_flags2) == 0

    # 2. When n_magnets=3 with min_angular_spacing=110: cannot fit all 3 in thick region (half-sphere)
    # The algorithm must pick exactly 1 boss in the thin region and 2 zero-boss magnets in the thick region
    centers3, angles3, boss_flags3 = find_optimized_magnet_positions(
        om, im, r_enc=r_enc, h_boss=h_boss, step_degrees=5.0,
        n_magnets=3, min_magnets=3, min_angular_spacing=110.0,
        allow_bosses=True, return_details=True
    )
    assert len(centers3) == 3
    assert sum(boss_flags3) == 1


def test_insert_magnets_with_allow_bosses_pipeline():
    """Verify that insert_magnets_into_hemispheres works end-to-end with allow_bosses."""
    outer_radius = 42.0
    inner_radius = 35.0
    ov, of = generate_sphere_points_fibonacci(500, outer_radius)
    iv, if_ = generate_sphere_points_fibonacci(300, inner_radius)

    top, bottom = create_hollow_hemispheres(ov, of, iv, if_, engine='manifold')

    # Configure with allow_bosses=True (thick enough for 0 bosses)
    settings_no_boss = MagnetSettings(
        n_magnets=3,
        diameter=4.0,
        height=1.5,
        min_thickness=1.0,
        allow_bosses=True,
    )
    top_res, bot_res = insert_magnets_into_hemispheres(
        top_mesh=top,
        bottom_mesh=bottom,
        outer_vertices=ov,
        outer_faces=of,
        inner_vertices=iv,
        inner_faces=if_,
        settings=settings_no_boss,
        engine='manifold',
    )
    assert top_res.is_watertight
    assert bot_res.is_watertight
    assert top_res.volume > 0
    assert bot_res.volume > 0


