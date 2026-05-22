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


def _find_optimal_spacing(valid_angles, k, min_spacing):
    """
    Find the subset of k angles from valid_angles that maximizes spacing uniformity.

    Parameters:
      valid_angles (list of float): Available angles in degrees.
      k (int): Number of angles to choose.
      min_spacing (float): Minimum angular spacing between any two chosen angles.

    Returns:
      list of float or None: The optimal subset of angles, or None if no valid subset exists.
    """
    if len(valid_angles) < k:
        return None

    valid_angles = sorted(valid_angles)
    best_score = float('inf')
    best_subset = None

    def backtrack(curr_subset, start_idx):
        nonlocal best_score, best_subset
        if len(curr_subset) == k:
            gap_last = 360.0 + curr_subset[0] - curr_subset[-1]
            if gap_last < min_spacing:
                return
            gaps = []
            for i in range(k - 1):
                gaps.append(curr_subset[i+1] - curr_subset[i])
            gaps.append(gap_last)
            score = sum((g - 360.0 / k) ** 2 for g in gaps)
            if score < best_score:
                best_score = score
                best_subset = list(curr_subset)
            return

        for i in range(start_idx, len(valid_angles)):
            angle = valid_angles[i]
            if angle - curr_subset[-1] < min_spacing:
                continue
            remaining_needed = k - len(curr_subset)
            if (360.0 + curr_subset[0] - angle) < remaining_needed * min_spacing:
                continue
            curr_subset.append(angle)
            backtrack(curr_subset, i + 1)
            curr_subset.pop()

    # Loop over possible starting angles
    for idx in range(len(valid_angles) - k + 1):
        backtrack([valid_angles[idx]], idx + 1)

    return best_subset


def find_valid_magnet_positions_no_bosses(
    outer_mesh,
    inner_mesh,
    r_enc,
    h_boss,
    step_degrees=2,
    n_magnets=3,
    min_magnets=2,
    min_angular_spacing=60.0,
    candidate_angles=None,
    bisection_iters=20,
    num_angles=16,
):
    """
    Find valid magnet positions in the globe shell without adding bosses/material.

    Steps around the model in step_degrees increments and tests whether a cylinder
    of radius r_enc and height from -h_boss to h_boss can be completely inserted
    within the solid part of the hollowed globe (inside outer mesh, outside inner mesh).
    Then finds the subset of valid locations that spaces them as evenly as possible.

    Parameters:
      outer_mesh (trimesh.Trimesh): Watertight outer globe mesh.
      inner_mesh (trimesh.Trimesh): Watertight inner globe mesh.
      r_enc (float): Enclosing radius of the magnet void + min thickness.
      h_boss (float): Enclosing height of the void.
      step_degrees (float): Longitude step size in degrees.
      n_magnets (int): Target number of magnet pairs.
      min_magnets (int): Minimum required magnet pairs.
      min_angular_spacing (float): Minimum angle between magnet pairs.
      candidate_angles (list of float, optional): Custom list of candidate angles to test.
      bisection_iters (int): Number of iterations for the binary search.
      num_angles (int): Number of angles to sample on the cylinder check boundaries.

    Returns:
      tuple of (list, list): A tuple (centers, chosen_angles) where:
        - centers is a list of (x, y) coordinates for the optimized magnet centers.
        - chosen_angles is a list of the corresponding chosen longitude angles in degrees.
    """
    outer_verts = outer_mesh.vertices
    outer_norms = np.linalg.norm(outer_verts, axis=1)
    outer_norms_safe = np.where(outer_norms == 0.0, 1.0, outer_norms)
    outer_unit = outer_verts / outer_norms_safe[:, None]
    kdtree_outer = cKDTree(outer_unit)

    inner_verts = inner_mesh.vertices
    inner_norms = np.linalg.norm(inner_verts, axis=1)
    inner_norms_safe = np.where(inner_norms == 0.0, 1.0, inner_norms)
    inner_unit = inner_verts / inner_norms_safe[:, None]
    kdtree_inner = cKDTree(inner_unit)

    local_pts = _generate_cylinder_check_points(r_enc, h_boss, num_angles=num_angles)

    max_outer_radius = np.max(outer_norms)
    max_inner_radius = np.max(inner_norms)

    low_limit = max_inner_radius + r_enc
    high_limit = max_outer_radius - r_enc

    if low_limit > high_limit:
        raise ValueError(
            f"Globe shell is too thin to fit magnets of enclosing radius {r_enc:.2f} mm "
            f"without adding bosses. Max inner radius: {max_inner_radius:.2f} mm, "
            f"Max outer radius: {max_outer_radius:.2f} mm."
        )

    if candidate_angles is None:
        candidate_angles = np.arange(0.0, 360.0, step_degrees)

    valid_angles = []
    valid_centers = {}

    for angle_deg in candidate_angles:
        angle_wrapped = (angle_deg % 360.0 + 360.0) % 360.0
        theta = np.radians(angle_wrapped)
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)

        low = float(low_limit)
        high = float(high_limit)
        best_d = 0.0

        def check_containment(d):
            global_pts = local_pts + np.array([d * cos_t, d * sin_t, 0.0])
            r_pts = np.linalg.norm(global_pts, axis=1)
            r_safe = np.where(r_pts == 0.0, 1.0, r_pts)
            unit_pts = global_pts / r_safe[:, None]

            # Outer containment
            dists_out, idxs_out = kdtree_outer.query(unit_pts, k=3)
            w_out = 1.0 / np.maximum(dists_out, 1e-6)
            w_out /= np.sum(w_out, axis=1, keepdims=True)
            r_outer = np.sum(outer_norms[idxs_out] * w_out, axis=1)

            # Inner containment
            dists_in, idxs_in = kdtree_inner.query(unit_pts, k=3)
            w_in = 1.0 / np.maximum(dists_in, 1e-6)
            w_in /= np.sum(w_in, axis=1, keepdims=True)
            r_inner = np.sum(inner_norms[idxs_in] * w_in, axis=1)

            return np.all((r_pts <= r_outer) & (r_pts >= r_inner))

        # Binary search
        for _ in range(bisection_iters):
            mid = (low + high) / 2.0
            if check_containment(mid):
                best_d = mid
                low = mid
            else:
                high = mid

        if best_d > 0.0 and check_containment(best_d):
            if angle_wrapped not in valid_centers:
                valid_angles.append(angle_wrapped)
                valid_centers[angle_wrapped] = (best_d * cos_t, best_d * sin_t)

    chosen_subset = None
    for k in range(n_magnets, min_magnets - 1, -1):
        subset = _find_optimal_spacing(valid_angles, k, min_angular_spacing)
        if subset is not None:
            chosen_subset = subset
            break

    if chosen_subset is None:
        raise ValueError(
            f"Could not place at least {min_magnets} magnet pairs satisfying "
            f"the min_angular_spacing of {min_angular_spacing} degrees and containment constraints."
        )

    centers = [valid_centers[angle] for angle in chosen_subset]
    return centers, chosen_subset


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
    add_bosses=True,
    min_magnets=2,
    min_angular_spacing=60.0,
    step_degrees=2,
    inner_vertices=None,
    inner_faces=None,
):
    """
    Inserts magnet voids and optionally enclosing material (bosses) into the hemispheres.

    Parameters:
      top_mesh (trimesh.Trimesh): Capped, hollow top hemisphere mesh.
      bottom_mesh (trimesh.Trimesh): Capped, hollow bottom hemisphere mesh.
      outer_vertices (numpy.ndarray or trimesh.Trimesh): Displaced outer shell vertices
        or the pre-built outer trimesh.Trimesh.
      outer_faces (numpy.ndarray or None): Outer shell face indices.
      diameter (float): Diameter of the cylindrical magnets (in mm).
      height (float): Height/thickness of the cylindrical magnets (in mm).
      n_magnets (int): Number of magnets per hemisphere.
      position (float or list/array of float): Initial angle/longitude (in degrees)
        or an exact list of longitudes to place magnets at.
      horizontal_tolerance (float): Radial tolerance to add to the magnet radius (in mm).
      vertical_tolerance (float): Vertical tolerance to add to the magnet height (in mm).
      vertical_offset (float): Minimum distance between the magnet void and the hemisphere cut (in mm).
      min_thickness (float): Minimum wall thickness of plastic surrounding the magnet (in mm).
      engine (str, optional): Boolean engine for trimesh.
      add_bosses (bool): If True, construct and add surrounding plastic bosses. If False, only subtract voids.
      min_magnets (int): Minimum required magnet pairs (only used if add_bosses=False).
      min_angular_spacing (float): Minimum spacing between magnet pairs in degrees.
      step_degrees (float): Incremental step in degrees for global position search.
      inner_vertices (numpy.ndarray or trimesh.Trimesh, optional): Inner shell vertices or pre-built Trimesh.
      inner_faces (numpy.ndarray, optional): Inner shell face indices.

    Returns:
      tuple of trimesh.Trimesh: (top_mesh_with_magnets, bottom_mesh_with_magnets)
    """
    # 1. Compute void and boss dimensions
    r_void = diameter / 2.0 + horizontal_tolerance
    h_void = height + vertical_tolerance

    r_enc = r_void + min_thickness
    h_boss = vertical_offset + h_void + min_thickness

    # 2. Build/use outer mesh to check containment
    if isinstance(outer_vertices, trimesh.Trimesh):
        outer_mesh = outer_vertices
    else:
        outer_mesh = trimesh.Trimesh(vertices=outer_vertices, faces=outer_faces)
        outer_mesh.fix_normals()

    # 3. Find optimal XY positions
    if add_bosses:
        if isinstance(position, (int, float, np.integer, np.floating)):
            longitudes = [position + i * (360.0 / n_magnets) for i in range(n_magnets)]
        else:
            longitudes = list(position)

        longitudes = [(l + 180) % 360 - 180 for l in longitudes]

        centers = optimize_magnet_positions(
            longitudes=longitudes,
            outer_mesh=outer_mesh,
            r_enc=r_enc,
            h_boss=h_boss,
        )
    else:
        if inner_vertices is None:
            raise ValueError("inner_vertices must be provided for magnet placement without adding bosses.")
        if isinstance(inner_vertices, trimesh.Trimesh):
            inner_mesh = inner_vertices
        else:
            inner_mesh = trimesh.Trimesh(vertices=inner_vertices, faces=inner_faces)
            inner_mesh.fix_normals()

        if isinstance(position, (int, float, np.integer, np.floating)):
            cand_angles = None
            n_mag = n_magnets
            min_mag = min_magnets
        else:
            cand_angles = list(position)
            n_mag = len(cand_angles)
            min_mag = len(cand_angles)

        centers, chosen_lons = find_valid_magnet_positions_no_bosses(
            outer_mesh=outer_mesh,
            inner_mesh=inner_mesh,
            r_enc=r_enc,
            h_boss=h_boss,
            step_degrees=step_degrees,
            n_magnets=n_mag,
            min_magnets=min_mag,
            min_angular_spacing=min_angular_spacing,
            candidate_angles=cand_angles,
        )

    top_bosses = []
    top_voids = []
    bottom_bosses = []
    bottom_voids = []

    # 4. Construct meshes for bosses and voids
    for x, y in centers:
        if add_bosses:
            tb = trimesh.creation.cylinder(radius=r_enc, height=h_boss)
            tb.apply_translation([x, y, h_boss / 2.0])
            top_bosses.append(tb)

        tv = trimesh.creation.cylinder(radius=r_void, height=h_void)
        tv.apply_translation([x, y, vertical_offset + h_void / 2.0])
        top_voids.append(tv)

        if add_bosses:
            bb = trimesh.creation.cylinder(radius=r_enc, height=h_boss)
            bb.apply_translation([x, y, -h_boss / 2.0])
            bottom_bosses.append(bb)

        bv = trimesh.creation.cylinder(radius=r_void, height=h_void)
        bv.apply_translation([x, y, -(vertical_offset + h_void / 2.0)])
        bottom_voids.append(bv)

    # 5. Perform boolean operations
    bool_kwargs = {}
    if engine is not None:
        bool_kwargs['engine'] = engine

    if add_bosses:
        top_with_bosses = trimesh.boolean.union([top_mesh] + top_bosses, **bool_kwargs)
        if top_with_bosses is None:
            raise ValueError("Boolean union of top hemisphere and magnet bosses failed.")
    else:
        top_with_bosses = top_mesh

    top_final = trimesh.boolean.difference([top_with_bosses] + top_voids, **bool_kwargs)
    if top_final is None:
        raise ValueError("Boolean subtraction of top magnet voids failed.")

    if add_bosses:
        bottom_with_bosses = trimesh.boolean.union([bottom_mesh] + bottom_bosses, **bool_kwargs)
        if bottom_with_bosses is None:
            raise ValueError("Boolean union of bottom hemisphere and magnet bosses failed.")
    else:
        bottom_with_bosses = bottom_mesh

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
