"""
Magnet insertion module for the globe3d package.

This module provides functions to optimize magnet placement on globe hemispheres
and perform boolean operations to insert magnet voids and enclosing material (bosses).
It also includes a function to generate a cylinder test piece for calibration.
"""

import numpy as np
import trimesh
from scipy.spatial import cKDTree


def _generate_cylinder_check_points(radius, height, num_angles=16, num_heights=5, num_radii=4):
    """
    Generate test points on the boundary and caps of a Z-aligned cylinder.

    The cylinder is centered at (0, 0, 0) and extends from Z = -height to Z = height.
    This is used to check containment of the combined top/bottom magnet boss cylinder.

    Parameters:
      radius (float): Radius of the cylinder.
      height (float): Half-height of the cylinder (extends from -height to +height).
      num_angles (int): Number of angular samples.
      num_heights (int): Number of height samples.
      num_radii (int): Number of radial samples for the caps.

    Returns:
      numpy.ndarray: (N, 3) array of coordinate points.
    """
    angles = np.linspace(0, 2 * np.pi, num=num_angles, endpoint=False)
    heights = np.linspace(-height, height, num=num_heights)
    radii = np.linspace(0, radius, num=num_radii)

    pts = []
    # Points on the outer lateral wall
    for z in heights:
        for alpha in angles:
            pts.append([radius * np.cos(alpha), radius * np.sin(alpha), z])
    # Points on the top and bottom flat faces
    for z in [-height, height]:
        for r in radii[:-1]:  # exclude outer radius since it's in the wall loop
            for alpha in angles:
                pts.append([r * np.cos(alpha), r * np.sin(alpha), z])
    return np.array(pts, dtype=np.float64)


def optimize_magnet_positions(
    longitudes,
    outer_mesh,
    r_enc,
    h_boss,
    bisection_iters=20,
    num_angles=16,
):
    """
    Find the optimal placement for magnets along specific longitude angles.

    For each longitude, finds the furthest distance from the origin in the Z=0 plane
    where a cylinder of radius `r_enc` and height from Z = -`h_boss` to Z = `h_boss`
    lies completely inside the outer displaced surface of the globe.

    Parameters:
      longitudes (list of float): Longitudes (in degrees) to place magnets at.
      outer_mesh (trimesh.Trimesh): Watertight outer globe mesh.
      r_enc (float): Enclosing radius of the plastic boss around the magnet (in mm).
      h_boss (float): Height of the boss from the cut plane (in mm).
      bisection_iters (int): Number of iterations for the binary search.
      num_angles (int): Number of angles to sample on the cylinder check boundaries.

    Returns:
      list of tuple: A list of (x, y) coordinates for the optimized magnet centers.
    """
    # Extract vertices and compute their radial distances (displaced radii)
    vertices = outer_mesh.vertices
    norms = np.linalg.norm(vertices, axis=1)
    
    # Avoid division by zero
    norms_safe = np.where(norms == 0.0, 1.0, norms)
    unit_vertices = vertices / norms_safe[:, None]
    
    # Build cKDTree on the unit vertices for direction-based querying
    kdtree = cKDTree(unit_vertices)

    # Generate local points for containment check
    local_pts = _generate_cylinder_check_points(r_enc, h_boss, num_angles=num_angles)

    # Compute a safe upper bound for distance search based on max vertex distance from origin
    max_radius = np.max(norms)
    high_limit = max_radius - r_enc

    centers = []

    for lon_deg in longitudes:
        theta = np.radians(lon_deg)
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)

        low = 0.0
        high = float(high_limit)
        best_d = 0.0

        def check_containment(d):
            # Shift check points to global coordinates at candidate center
            global_pts = local_pts + np.array([d * cos_t, d * sin_t, 0.0])
            
            # Compute radial distances of global points
            r_pts = np.linalg.norm(global_pts, axis=1)
            r_safe = np.where(r_pts == 0.0, 1.0, r_pts)
            
            # Normalize global points to unit vectors
            unit_pts = global_pts / r_safe[:, None]
            
            # Query the 3 nearest unit vertices
            dists, idxs = kdtree.query(unit_pts, k=3)
            
            # Compute inverse distance weighting (IDW) to interpolate displaced radius
            w = 1.0 / np.maximum(dists, 1e-6)
            w /= np.sum(w, axis=1, keepdims=True)
            
            r_outer = np.sum(norms[idxs] * w, axis=1)
            
            # All check points must be inside the displaced boundary
            return np.all(r_pts <= r_outer)

        # Binary search for optimal distance d
        for _ in range(bisection_iters):
            mid = (low + high) / 2.0
            if check_containment(mid):
                best_d = mid
                low = mid
            else:
                high = mid

        centers.append((best_d * cos_t, best_d * sin_t))

    return centers


def insert_magnets_into_hemispheres(
    top_mesh,
    bottom_mesh,
    outer_vertices,
    outer_faces,
    diameter,
    height,
    n_magnets=3,
    position=0.0,
    horizontal_tolerance=0.1,
    vertical_tolerance=0.1,
    vertical_offset=0.2,
    min_thickness=1.5,
    engine=None,
):
    """
    Inserts magnet voids and enclosing material into the top and bottom hemispheres.

    The function determines the optimal XY locations for magnet pairs, constructs
    the surrounding plastic bosses, and subtracts the cylinder voids.

    Parameters:
      top_mesh (trimesh.Trimesh): Capped, hollow top hemisphere mesh.
      bottom_mesh (trimesh.Trimesh): Capped, hollow bottom hemisphere mesh.
      outer_vertices (numpy.ndarray or trimesh.Trimesh): Displaced outer shell vertices
        or the pre-built outer trimesh.Trimesh.
      outer_faces (numpy.ndarray or None): Outer shell face indices (None if outer_vertices is a Trimesh).
      diameter (float): Diameter of the cylindrical magnets (in mm).
      height (float): Height/thickness of the cylindrical magnets (in mm).
      n_magnets (int): Number of magnets per hemisphere (evenly spaced).
      position (float or list/array of float): Initial angle/longitude (in degrees)
        or an exact list of longitudes to place magnets at.
      horizontal_tolerance (float): Radial tolerance to add to the magnet radius (in mm).
      vertical_tolerance (float): Vertical tolerance to add to the magnet height (in mm).
      vertical_offset (float): Minimum distance between the magnet void and the hemisphere cut (in mm).
      min_thickness (float): Minimum wall thickness of plastic surrounding the magnet (in mm).
      engine (str, optional): Boolean engine for trimesh.

    Returns:
      tuple of trimesh.Trimesh: (top_mesh_with_magnets, bottom_mesh_with_magnets)
    """
    # 1. Determine target longitudes
    if isinstance(position, (int, float, np.integer, np.floating)):
        longitudes = [position + i * (360.0 / n_magnets) for i in range(n_magnets)]
    else:
        longitudes = list(position)

    # Wrap longitudes to [-180, 180] range
    longitudes = [(l + 180) % 360 - 180 for l in longitudes]

    # 2. Compute void and boss dimensions
    r_void = diameter / 2.0 + horizontal_tolerance
    h_void = height + vertical_tolerance

    r_enc = r_void + min_thickness
    h_boss = vertical_offset + h_void + min_thickness

    # 3. Build/use outer mesh to check containment
    if isinstance(outer_vertices, trimesh.Trimesh):
        outer_mesh = outer_vertices
    else:
        outer_mesh = trimesh.Trimesh(vertices=outer_vertices, faces=outer_faces)
        outer_mesh.fix_normals()

    # 4. Find optimal XY positions
    centers = optimize_magnet_positions(
        longitudes=longitudes,
        outer_mesh=outer_mesh,
        r_enc=r_enc,
        h_boss=h_boss,
    )

    top_bosses = []
    top_voids = []
    bottom_bosses = []
    bottom_voids = []

    # 5. Construct meshes for bosses and voids
    for x, y in centers:
        # --- Top Hemisphere ---
        # Boss cylinder goes from Z=0 to Z=h_boss
        tb = trimesh.creation.cylinder(radius=r_enc, height=h_boss)
        tb.apply_translation([x, y, h_boss / 2.0])
        top_bosses.append(tb)

        # Void cylinder goes from Z=vertical_offset to Z=vertical_offset+h_void
        tv = trimesh.creation.cylinder(radius=r_void, height=h_void)
        tv.apply_translation([x, y, vertical_offset + h_void / 2.0])
        top_voids.append(tv)

        # --- Bottom Hemisphere ---
        # Boss cylinder goes from Z=-h_boss to Z=0
        bb = trimesh.creation.cylinder(radius=r_enc, height=h_boss)
        bb.apply_translation([x, y, -h_boss / 2.0])
        bottom_bosses.append(bb)

        # Void cylinder goes from Z=-(vertical_offset+h_void) to Z=-vertical_offset
        bv = trimesh.creation.cylinder(radius=r_void, height=h_void)
        bv.apply_translation([x, y, -(vertical_offset + h_void / 2.0)])
        bottom_voids.append(bv)

    # 6. Perform boolean operations
    bool_kwargs = {}
    if engine is not None:
        bool_kwargs['engine'] = engine

    top_with_bosses = trimesh.boolean.union([top_mesh] + top_bosses, **bool_kwargs)
    if top_with_bosses is None:
        raise ValueError("Boolean union of top hemisphere and magnet bosses failed.")

    top_final = trimesh.boolean.difference([top_with_bosses] + top_voids, **bool_kwargs)
    if top_final is None:
        raise ValueError("Boolean subtraction of top magnet voids failed.")

    bottom_with_bosses = trimesh.boolean.union([bottom_mesh] + bottom_bosses, **bool_kwargs)
    if bottom_with_bosses is None:
        raise ValueError("Boolean union of bottom hemisphere and magnet bosses failed.")

    bottom_final = trimesh.boolean.difference([bottom_with_bosses] + bottom_voids, **bool_kwargs)
    if bottom_final is None:
        raise ValueError("Boolean subtraction of bottom magnet voids failed.")

    return top_final, bottom_final


def generate_magnet_test_piece(
    diameter,
    height,
    horizontal_tolerance=0.1,
    vertical_tolerance=0.1,
    vertical_offset=0.2,
    min_thickness=1.5,
    output_path=None,
):
    """
    Generates a Z-aligned cylindrical test piece for calibrating magnet fits.

    The outer cylinder has a radius of `r_enc + 2mm` to provide stability on the print bed.
    The void is centered in XY and starts at `vertical_offset` from the bottom Z=0 plane.

    Parameters:
      diameter (float): Magnet diameter (in mm).
      height (float): Magnet height/thickness (in mm).
      horizontal_tolerance (float): Radial tolerance to add to the magnet radius (in mm).
      vertical_tolerance (float): Vertical tolerance to add to the magnet height (in mm).
      vertical_offset (float): Distance from the bottom of the test piece to the void (in mm).
      min_thickness (float): Minimum surrounding plastic wall/roof thickness (in mm).
      output_path (str, optional): File path to export the test piece mesh as STL or OBJ.

    Returns:
      trimesh.Trimesh: The generated test piece mesh.
    """
    r_void = diameter / 2.0 + horizontal_tolerance
    h_void = height + vertical_tolerance

    r_enc = r_void + min_thickness
    h_boss = vertical_offset + h_void + min_thickness

    # Outer cylinder with +2.0 mm radius for stability
    r_outer = r_enc + 2.0
    outer_cyl = trimesh.creation.cylinder(radius=r_outer, height=h_boss)
    outer_cyl.apply_translation([0.0, 0.0, h_boss / 2.0])

    # Inner void cylinder
    void_cyl = trimesh.creation.cylinder(radius=r_void, height=h_void)
    void_cyl.apply_translation([0.0, 0.0, vertical_offset + h_void / 2.0])

    # Subtract the void from the outer cylinder
    test_piece = trimesh.boolean.difference([outer_cyl, void_cyl])
    if test_piece is None:
        raise ValueError("Boolean subtraction for test piece generation failed.")

    if output_path:
        test_piece.export(output_path)

    return test_piece
