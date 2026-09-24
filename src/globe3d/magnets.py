"""Magnet insertion module for the globe3d package.

This module provides the MagnetSettings class and helper functions to optimize
magnet placement on globe hemispheres and perform boolean operations to insert
magnet voids and enclosing material (bosses). It also includes a function to
generate a cylinder test piece for calibration.
"""

import numpy as np
import trimesh
from scipy.spatial import cKDTree


class MagnetSettings:
    """Configuration settings for magnet void and boss insertion in globe hemispheres."""

    def __init__(
        self,
        diameter: float = 5.0,
        height: float = 2.0,
        n_magnets: int = 3,
        position: object = 0.0,
        horizontal_tolerance: float = 0.15,
        vertical_tolerance: float = 0.10,
        vertical_offset: float = 0.20,
        min_thickness: float = 1.5,
        allow_bosses: bool = True,
        min_magnets: int = 2,
        min_angular_spacing: float = 60.0,
        step_degrees: float = 2,
        placement_strategy: str = "cluster_peaks",
        angle_tolerance: float = 0.0,
        add_bosses: object = None,
    ):
        """Initializes a MagnetSettings instance.

        Args:
            diameter (float, optional): Diameter of the cylindrical magnets in mm. Defaults to 5.0.
            height (float, optional): Height of the cylindrical magnets in mm. Defaults to 2.0.
            n_magnets (int, optional): Number of magnets to insert. Defaults to 3.
            position (float or list of float, optional): Initial angle or list of longitude angles. Defaults to 0.0.
            horizontal_tolerance (float, optional): Tolerance added to magnet radius. Defaults to 0.15.
            vertical_tolerance (float, optional): Tolerance added to magnet height. Defaults to 0.10.
            vertical_offset (float, optional): Distance between void and cut plane. Defaults to 0.20.
            min_thickness (float, optional): Minimum surrounding material thickness. Defaults to 1.5.
            allow_bosses (bool, optional): If True, allows adding bosses when the shell is too thin,
                minimizing the number of bosses and the protrusion into the cavity. If False, magnets
                must fit entirely within the solid shell wall without adding any bosses. Defaults to True.
            min_magnets (int, optional): Minimum required magnet pairs. Defaults to 2.
            min_angular_spacing (float, optional): Minimum spacing in degrees between magnet pairs. Defaults to 60.0.
            step_degrees (float, optional): Longitude step size for searching positions. Defaults to 2.
            placement_strategy (str, optional): Strategy for choosing magnet angles when fitting within the shell.
                Options are 'cluster_peaks' (default, places in thickest part of continental regions),
                'uniform' (maximizes spacing uniformity), or 'margin_weighted' (balances spacing
                and clearance margin). Defaults to 'cluster_peaks'.
            angle_tolerance (float, optional): Maximum angular search window in degrees around candidate
                angles when explicit positions are specified. Defaults to 0.0.
            add_bosses (bool, optional): Deprecated alias for ``allow_bosses``. If specified, overrides
                ``allow_bosses`` for backward compatibility. Defaults to None.
        """
        if add_bosses is not None:
            allow_bosses = bool(add_bosses)
        self.diameter = float(diameter)
        self.height = float(height)
        self.n_magnets = int(n_magnets)
        self.position = position
        self.horizontal_tolerance = float(horizontal_tolerance)
        self.vertical_tolerance = float(vertical_tolerance)
        self.vertical_offset = float(vertical_offset)
        self.min_thickness = float(min_thickness)
        self.allow_bosses = bool(allow_bosses)
        self.add_bosses = self.allow_bosses  # Backward compatibility alias
        self.min_magnets = int(min_magnets)
        self.min_angular_spacing = float(min_angular_spacing)
        self.step_degrees = float(step_degrees)
        self.placement_strategy = str(placement_strategy)
        self.angle_tolerance = float(angle_tolerance)


def _generate_cylinder_check_points(radius, height, num_angles=16, num_heights=5, num_radii=4):
    """Generates test points on the boundary and caps of a Z-aligned cylinder.

    The cylinder is centered at (0, 0, 0) and extends from Z = -height to Z = height.
    This is used to check containment of the combined top/bottom magnet boss cylinder.

    Args:
        radius (float): Radius of the cylinder.
        height (float): Half-height of the cylinder (extends from -height to +height).
        num_angles (int, optional): Number of angular samples. Defaults to 16.
        num_heights (int, optional): Number of height samples. Defaults to 5.
        num_radii (int, optional): Number of radial samples for the caps. Defaults to 4.

    Returns:
        numpy.ndarray: Array of shape (N, 3) representing coordinate points.
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
    """Finds the optimal radial placement for magnets along specific longitude angles.

    For each longitude, finds the furthest distance from the origin in the Z=0 plane
    where a cylinder of radius `r_enc` and height from Z = -`h_boss` to Z = `h_boss`
    lies completely inside the outer displaced surface of the globe.

    Args:
        longitudes (list of float): Longitudes (in degrees) to place magnets at.
        outer_mesh (trimesh.Trimesh): Watertight outer globe mesh.
        r_enc (float): Enclosing radius of the plastic boss around the magnet (in mm).
        h_boss (float): Height of the boss from the cut plane (in mm).
        bisection_iters (int, optional): Number of iterations for binary search. Defaults to 20.
        num_angles (int, optional): Number of angles to sample on check boundaries. Defaults to 16.

    Returns:
        list of tuple: A list of (x, y) coordinates for the optimized magnet centers.
    """
    vertices = outer_mesh.vertices
    norms = np.linalg.norm(vertices, axis=1)

    norms_safe = np.where(norms == 0.0, 1.0, norms)
    unit_vertices = vertices / norms_safe[:, None]

    kdtree = cKDTree(unit_vertices)
    local_pts = _generate_cylinder_check_points(r_enc, h_boss, num_angles=num_angles)

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
            global_pts = local_pts + np.array([d * cos_t, d * sin_t, 0.0])
            r_pts = np.linalg.norm(global_pts, axis=1)
            r_safe = np.where(r_pts == 0.0, 1.0, r_pts)
            unit_pts = global_pts / r_safe[:, None]

            dists, idxs = kdtree.query(unit_pts, k=3)

            w = 1.0 / np.maximum(dists, 1e-6)
            w /= np.sum(w, axis=1, keepdims=True)

            r_outer = np.sum(norms[idxs] * w, axis=1)
            return np.all(r_pts <= r_outer)

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
    """Finds the subset of k angles from valid_angles that maximizes spacing uniformity.

    Args:
        valid_angles (list of float): List of candidate longitude angles in degrees.
        k (int): Number of angles to select.
        min_spacing (float): Minimum angular spacing required between adjacent selected angles.

    Returns:
        list of float or None: The selected subset of k angles, or None if no valid combination exists.
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
            if best_score < 1e-6:
                return

    for idx in range(len(valid_angles) - k + 1):
        backtrack([valid_angles[idx]], idx + 1)
        if best_score < 1e-6:
            break

    return best_subset


def _group_circular_clusters(valid_angles, step_degrees):
    """Groups valid angles into contiguous circular clusters on the 360-degree circle.

    Args:
        valid_angles (list of float): List of valid candidate longitude angles in degrees.
        step_degrees (float): Longitude step size used during candidate evaluation.

    Returns:
        list of list of float: Contiguous clusters of angles.
    """
    if not valid_angles:
        return []

    valid_angles = sorted(valid_angles)
    step_tol = step_degrees * 1.5

    clusters = []
    curr = [valid_angles[0]]
    for a in valid_angles[1:]:
        if a - curr[-1] <= step_tol:
            curr.append(a)
        else:
            clusters.append(curr)
            curr = [a]
    clusters.append(curr)

    if len(clusters) > 1:
        wrap_gap = 360.0 + valid_angles[0] - valid_angles[-1]
        if wrap_gap <= step_tol:
            clusters[0] = clusters[-1] + clusters[0]
            clusters.pop()

    return clusters


def _find_margin_weighted_spacing(valid_angles, valid_margins, k, min_spacing, margin_weight=50.0):
    """Finds the subset of k angles balancing spacing uniformity and wall clearance margin.

    Args:
        valid_angles (list of float): List of valid candidate longitude angles in degrees.
        valid_margins (dict): Mapping from angle to clearance margin in mm.
        k (int): Number of angles to select.
        min_spacing (float): Minimum angular spacing required between adjacent selected angles.
        margin_weight (float, optional): Weighting coefficient for clearance margin. Defaults to 50.0.

    Returns:
        list of float or None: The selected subset of k angles, or None if no valid combination exists.
    """
    if len(valid_angles) < k:
        return None

    valid_angles = sorted(valid_angles)
    best_score = float('inf')
    best_subset = None
    target_gap = 360.0 / k

    def backtrack(curr_subset, start_idx):
        nonlocal best_score, best_subset
        if len(curr_subset) == k:
            gap_last = 360.0 + curr_subset[0] - curr_subset[-1]
            if gap_last < min_spacing:
                return
            gaps = [curr_subset[i+1] - curr_subset[i] for i in range(k - 1)] + [gap_last]
            spacing_cost = sum((g - target_gap) ** 2 for g in gaps)
            margin_bonus = sum(valid_margins[a] for a in curr_subset) * margin_weight
            score = spacing_cost - margin_bonus
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
    placement_strategy="cluster_peaks",
    angle_tolerance=0.0,
    allow_bosses=False,
    add_bosses=None,
    return_details=False,
):
    """Finds valid magnet positions in the globe shell, optionally allowing bosses when needed.

    Tests candidate longitude angles on the equatorial splitting plane (Z = 0)
    to determine whether a cylinder of radius r_enc and height from -h_boss to +h_boss
    can be contained within the solid shell of the hollowed globe (inside
    outer_mesh and outside inner_mesh).

    Uses a dual-bisection search to find the valid radial range [d_min, d_max]
    at each candidate angle:
    - If d_min <= d_max, the magnet fits cleanly inside the solid shell without a boss.
      The void is placed at d = (d_min + d_max) / 2 to maximize plastic clearance.
    - If d_min > d_max and allow_bosses is True, the void is placed at d = d_max to
      minimize how much the boss protrudes into the inner cavity, minimizing added material.

    When allow_bosses is True:
    - The algorithm first searches for valid combinations that require zero bosses.
    - If not enough zero-boss positions are available, it optimizes a multi-objective
      cost function that minimizes the number of bosses required, minimizes the
      cavity protrusion depth (material added), and balances angular spacing uniformity.

    Supports multiple placement strategies for zero-boss positioning:
    - 'cluster_peaks' (default): Groups adjacent valid longitudes into contiguous
      bands (continental regions) and selects the peak clearance point in each band,
      maximizing wall thickness. Falls back to uniform spacing if fewer clusters exist
      than requested magnets.
    - 'uniform': Purely maximizes angular spacing uniformity among valid angles.
    - 'margin_weighted': Balances spacing uniformity with clearance margin.

    Args:
        outer_mesh (trimesh.Trimesh): Watertight outer globe mesh.
        inner_mesh (trimesh.Trimesh): Watertight inner globe mesh.
        r_enc (float): Enclosing radius of the magnet void + min thickness in mm.
        h_boss (float): Enclosing height of the void in mm.
        step_degrees (float, optional): Longitude step size in degrees. Defaults to 2.
        n_magnets (int, optional): Target number of magnet pairs. Defaults to 3.
        min_magnets (int, optional): Minimum required magnet pairs. Defaults to 2.
        min_angular_spacing (float, optional): Minimum angle between magnet pairs. Defaults to 60.0.
        candidate_angles (list of float, optional): Custom list of candidate angles to test.
        bisection_iters (int, optional): Iterations for binary search. Defaults to 20.
        num_angles (int, optional): Number of angles to sample on check boundaries. Defaults to 16.
        placement_strategy (str, optional): Strategy for selecting angles ('cluster_peaks',
            'uniform', or 'margin_weighted'). Defaults to 'cluster_peaks'.
        angle_tolerance (float, optional): Maximum angular search window in degrees around candidate
            angles when explicit positions are specified. Defaults to 0.0.
        allow_bosses (bool, optional): If True, allows placing bosses when the shell is too thin,
            minimizing boss count and protrusion. If False, raises ValueError if the void cannot
            fit within the solid shell. Defaults to False.
        add_bosses (bool, optional): Deprecated alias for ``allow_bosses``. Defaults to None.
        return_details (bool, optional): If True, returns a 3-element tuple (centers, chosen_angles,
            boss_flags). If False, returns (centers, chosen_angles). Defaults to False.

    Returns:
        tuple: A tuple (centers, chosen_angles) or (centers, chosen_angles, boss_flags) where:
            - centers (list of tuple): (x, y) coordinates for optimized magnet centers.
            - chosen_angles (list of float): Corresponding chosen longitude angles.
            - boss_flags (list of bool, optional): Present if return_details is True. Indicates
              whether each magnet requires an added boss cylinder.

    Raises:
        ValueError: If no candidate positions can fit the magnet void, or if fewer than
            min_magnets can be placed satisfying min_angular_spacing and containment constraints.
    """
    if add_bosses is not None:
        allow_bosses = bool(add_bosses)

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

    min_inner_radius = float(np.min(inner_norms))
    max_outer_radius = float(np.max(outer_norms))

    def eval_margins(d, cos_t, sin_t):
        global_pts = local_pts + np.array([d * cos_t, d * sin_t, 0.0])
        r_pts = np.linalg.norm(global_pts, axis=1)
        r_safe = np.where(r_pts == 0.0, 1.0, r_pts)
        unit_pts = global_pts / r_safe[:, None]

        dists_out, idxs_out = kdtree_outer.query(unit_pts, k=3)
        w_out = 1.0 / np.maximum(dists_out, 1e-6)
        w_out /= np.sum(w_out, axis=1, keepdims=True)
        r_outer = np.sum(outer_norms[idxs_out] * w_out, axis=1)

        dists_in, idxs_in = kdtree_inner.query(unit_pts, k=3)
        w_in = 1.0 / np.maximum(dists_in, 1e-6)
        w_in /= np.sum(w_in, axis=1, keepdims=True)
        r_inner = np.sum(inner_norms[idxs_in] * w_in, axis=1)

        in_margin = float(np.min(r_pts - r_inner))
        out_margin = float(np.min(r_outer - r_pts))
        return in_margin, out_margin

    def evaluate_single_angle(angle_deg):
        angle_wrapped = (angle_deg % 360.0 + 360.0) % 360.0
        theta = np.radians(angle_wrapped)
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)

        # 1. Bisect for d_max (outer containment)
        low = min_inner_radius
        high = max_outer_radius
        for _ in range(bisection_iters):
            mid = (low + high) / 2.0
            _, out_m = eval_margins(mid, cos_t, sin_t)
            if out_m >= 0.0:
                low = mid
            else:
                high = mid
        d_max = low

        # 2. Bisect for d_min (inner clearance)
        low = min_inner_radius
        high = max_outer_radius
        for _ in range(bisection_iters):
            mid = (low + high) / 2.0
            in_m, _ = eval_margins(mid, cos_t, sin_t)
            if in_m >= 0.0:
                high = mid
            else:
                low = mid
        d_min = high

        if d_min <= d_max:
            # Fits inside solid shell without boss!
            best_d = (d_min + d_max) / 2.0
            in_m, out_m = eval_margins(best_d, cos_t, sin_t)
            margin = min(in_m, out_m)
            needs_boss = False
            protrusion = 0.0
        else:
            # Needs boss! Place at d_max to minimize protrusion into inner cavity
            best_d = d_max
            in_m, out_m = eval_margins(best_d, cos_t, sin_t)
            needs_boss = True
            protrusion = max(0.0, -in_m)
            margin = -protrusion

        center = (best_d * cos_t, best_d * sin_t)
        return {
            "angle": angle_wrapped,
            "center": center,
            "best_d": best_d,
            "needs_boss": needs_boss,
            "protrusion": protrusion,
            "margin": margin,
        }

    explicit_candidate_list = candidate_angles is not None
    if explicit_candidate_list:
        test_angles = list(candidate_angles)
    else:
        test_angles = np.arange(0.0, 360.0, step_degrees)

    evaluated_candidates = []
    for a in test_angles:
        res = evaluate_single_angle(a)
        if explicit_candidate_list and angle_tolerance > 0.0:
            if not allow_bosses and res["needs_boss"]:
                # Try to nudge to a 0-boss position
                best_nudge = None
                best_margin = -float("inf")
                nudge_steps = np.arange(
                    -angle_tolerance, angle_tolerance + step_degrees / 2.0, step_degrees
                )
                for offset in nudge_steps:
                    n_res = evaluate_single_angle(a + offset)
                    if not n_res["needs_boss"] and n_res["margin"] > best_margin:
                        best_margin = n_res["margin"]
                        best_nudge = n_res
                if best_nudge is not None:
                    res = best_nudge
            elif allow_bosses and res["needs_boss"]:
                # Try to nudge to a 0-boss or smaller protrusion position
                best_nudge = res
                best_cost = (
                    (10000.0 if res["needs_boss"] else 0.0)
                    + res["protrusion"] * 100.0
                    - res["margin"]
                )
                nudge_steps = np.arange(
                    -angle_tolerance, angle_tolerance + step_degrees / 2.0, step_degrees
                )
                for offset in nudge_steps:
                    n_res = evaluate_single_angle(a + offset)
                    cost = (
                        (10000.0 if n_res["needs_boss"] else 0.0)
                        + n_res["protrusion"] * 100.0
                        - n_res["margin"]
                    )
                    if cost < best_cost:
                        best_cost = cost
                        best_nudge = n_res
                res = best_nudge

        if not allow_bosses and res["needs_boss"]:
            continue
        evaluated_candidates.append(res)

    if not evaluated_candidates:
        raise ValueError(
            f"Globe shell is too thin to fit magnets of enclosing radius {r_enc:.2f} mm "
            f"without adding bosses at any candidate position. "
            f"Min inner radius: {min_inner_radius:.2f} mm, Max outer radius: {max_outer_radius:.2f} mm."
        )

    if explicit_candidate_list:
        if len(evaluated_candidates) < len(test_angles):
            raise ValueError(
                f"Could not fit all requested candidate angles without adding bosses."
            )
        chosen_subset = [c["angle"] for c in evaluated_candidates]
        centers = [c["center"] for c in evaluated_candidates]
        boss_flags = [c["needs_boss"] for c in evaluated_candidates]
        if return_details:
            return centers, chosen_subset, boss_flags
        return centers, chosen_subset

    zero_boss_cands = [c for c in evaluated_candidates if not c["needs_boss"]]
    zero_boss_angles = [c["angle"] for c in zero_boss_cands]
    margins_map = {c["angle"]: c["margin"] for c in evaluated_candidates}
    centers_map = {c["angle"]: c["center"] for c in evaluated_candidates}
    boss_map = {c["angle"]: c["needs_boss"] for c in evaluated_candidates}

    chosen_subset = None

    for k in range(n_magnets, min_magnets - 1, -1):
        # Stage 1: Try placing k magnets with 0 bosses
        if len(zero_boss_angles) >= k:
            if placement_strategy == "cluster_peaks":
                clusters = _group_circular_clusters(zero_boss_angles, step_degrees)
                if len(clusters) >= k:
                    peak_angles = [max(cl, key=lambda a: margins_map[a]) for cl in clusters]
                    sub = _find_optimal_spacing(peak_angles, k, min_angular_spacing)
                    if sub is not None:
                        chosen_subset = sub
                        break
                sub = _find_optimal_spacing(zero_boss_angles, k, min_angular_spacing)
                if sub is not None:
                    chosen_subset = sub
                    break
            elif placement_strategy == "margin_weighted":
                sub = _find_margin_weighted_spacing(
                    zero_boss_angles, margins_map, k, min_angular_spacing
                )
                if sub is not None:
                    chosen_subset = sub
                    break
            else:  # "uniform"
                sub = _find_optimal_spacing(zero_boss_angles, k, min_angular_spacing)
                if sub is not None:
                    chosen_subset = sub
                    break

        # Stage 2: If no 0-boss combination satisfies spacing, allow bosses if permitted
        if allow_bosses:
            best_cost = (float("inf"), float("inf"), float("inf"))
            best_sub = None
            target_gap = 360.0 / k
            all_cands = sorted(evaluated_candidates, key=lambda c: c["angle"])

            def backtrack(curr, start_idx, curr_bosses, curr_protrusion, curr_margin):
                nonlocal best_cost, best_sub
                if curr_bosses > best_cost[0]:
                    return
                if curr_bosses == best_cost[0] and curr_protrusion > best_cost[1]:
                    return
                if len(curr) == k:
                    gap_last = 360.0 + curr[0]["angle"] - curr[-1]["angle"]
                    if gap_last < min_angular_spacing:
                        return
                    gaps = [curr[i + 1]["angle"] - curr[i]["angle"] for i in range(k - 1)] + [gap_last]
                    spacing_cost = sum((g - target_gap) ** 2 for g in gaps)
                    cost = (
                        curr_bosses,
                        round(curr_protrusion, 4),
                        spacing_cost - 0.1 * curr_margin,
                    )
                    if cost < best_cost:
                        best_cost = cost
                        best_sub = [c["angle"] for c in curr]
                    return

                rem = k - len(curr)
                for i in range(start_idx, len(all_cands)):
                    c = all_cands[i]
                    if c["angle"] - curr[-1]["angle"] < min_angular_spacing:
                        continue
                    if (360.0 + curr[0]["angle"] - c["angle"]) < rem * min_angular_spacing:
                        continue
                    curr.append(c)
                    backtrack(
                        curr,
                        i + 1,
                        curr_bosses + (1 if c["needs_boss"] else 0),
                        curr_protrusion + c["protrusion"],
                        curr_margin + c["margin"],
                    )
                    curr.pop()

            for idx in range(len(all_cands) - k + 1):
                c0 = all_cands[idx]
                backtrack(
                    [c0],
                    idx + 1,
                    1 if c0["needs_boss"] else 0,
                    c0["protrusion"],
                    c0["margin"],
                )

            if best_sub is not None:
                chosen_subset = best_sub
                break

    if chosen_subset is None:
        raise ValueError(
            f"Could not place at least {min_magnets} magnet pairs satisfying "
            f"the min_angular_spacing of {min_angular_spacing} degrees and containment constraints."
        )

    centers = [centers_map[a] for a in chosen_subset]
    boss_flags = [boss_map[a] for a in chosen_subset]
    if return_details:
        return centers, chosen_subset, boss_flags
    return centers, chosen_subset


find_optimized_magnet_positions = find_valid_magnet_positions_no_bosses


def insert_magnets_into_hemispheres(
    top_mesh,
    bottom_mesh,
    outer_vertices,
    outer_faces,
    diameter=5.0,
    height=2.0,
    n_magnets=3,
    position=0.0,
    horizontal_tolerance=0.15,
    vertical_tolerance=0.10,
    vertical_offset=0.20,
    min_thickness=1.5,
    engine=None,
    allow_bosses=True,
    min_magnets=2,
    min_angular_spacing=60.0,
    step_degrees=2,
    inner_vertices=None,
    inner_faces=None,
    settings=None,
    placement_strategy="cluster_peaks",
    angle_tolerance=0.0,
    add_bosses=None,
):
    """Inserts magnet voids and optionally enclosing material (bosses) into the hemispheres.

    Can be configured either via keyword parameters or by passing a MagnetSettings object.
    When bosses are allowed, minimizes the number of bosses needed and the material added.

    Args:
        top_mesh (trimesh.Trimesh): Capped, hollow top hemisphere mesh.
        bottom_mesh (trimesh.Trimesh): Capped, hollow bottom hemisphere mesh.
        outer_vertices (numpy.ndarray or trimesh.Trimesh): Outer shell vertices or pre-built outer Trimesh.
        outer_faces (numpy.ndarray or None): Outer shell face indices.
        diameter (float, optional): Diameter of the cylindrical magnets in mm. Defaults to 5.0.
        height (float, optional): Height of the cylindrical magnets in mm. Defaults to 2.0.
        n_magnets (int, optional): Number of magnets per hemisphere. Defaults to 3.
        position (float or list of float, optional): Initial angle or list of longitudes to place magnets at. Defaults to 0.0.
        horizontal_tolerance (float, optional): Radial tolerance to add to the magnet radius. Defaults to 0.15.
        vertical_tolerance (float, optional): Vertical tolerance to add to the magnet height. Defaults to 0.10.
        vertical_offset (float, optional): Distance between magnet void and cut plane. Defaults to 0.20.
        min_thickness (float, optional): Minimum surrounding plastic thickness in mm. Defaults to 1.5.
        engine (str, optional): Boolean engine for trimesh. Defaults to None.
        allow_bosses (bool, optional): If True, allows adding bosses when the shell is too thin,
            minimizing the number of bosses and the protrusion into the cavity. If False, magnets
            must fit entirely within the solid shell wall without adding any bosses. Defaults to True.
        min_magnets (int, optional): Minimum required magnet pairs. Defaults to 2.
        min_angular_spacing (float, optional): Minimum spacing in degrees between magnet pairs. Defaults to 60.0.
        step_degrees (float, optional): Longitude step size for search. Defaults to 2.
        inner_vertices (numpy.ndarray or trimesh.Trimesh, optional): Inner shell vertices or pre-built inner Trimesh. Defaults to None.
        inner_faces (numpy.ndarray, optional): Inner shell face indices. Defaults to None.
        settings (MagnetSettings, optional): A MagnetSettings instance containing configuration values. Defaults to None.
        placement_strategy (str, optional): Strategy for selecting angles ('cluster_peaks',
            'uniform', or 'margin_weighted'). Defaults to 'cluster_peaks'.
        angle_tolerance (float, optional): Maximum angular search window in degrees around candidate
            angles when explicit positions are specified. Defaults to 0.0.
        add_bosses (bool, optional): Deprecated alias for ``allow_bosses``. Defaults to None.

    Returns:
        tuple: (top_mesh_with_magnets, bottom_mesh_with_magnets) as trimesh.Trimesh objects.
    """
    if settings is not None:
        diameter = settings.diameter
        height = settings.height
        n_magnets = settings.n_magnets
        position = settings.position
        horizontal_tolerance = settings.horizontal_tolerance
        vertical_tolerance = settings.vertical_tolerance
        vertical_offset = settings.vertical_offset
        min_thickness = settings.min_thickness
        allow_bosses = getattr(settings, "allow_bosses", getattr(settings, "add_bosses", True))
        min_magnets = settings.min_magnets
        min_angular_spacing = settings.min_angular_spacing
        step_degrees = settings.step_degrees
        placement_strategy = getattr(settings, "placement_strategy", placement_strategy)
        angle_tolerance = getattr(settings, "angle_tolerance", angle_tolerance)
    elif add_bosses is not None:
        allow_bosses = bool(add_bosses)

    r_void = diameter / 2.0 + horizontal_tolerance
    h_void = height + vertical_tolerance

    r_enc = r_void + min_thickness
    h_boss = vertical_offset + h_void + min_thickness

    if isinstance(outer_vertices, trimesh.Trimesh):
        outer_mesh = outer_vertices
    else:
        outer_mesh = trimesh.Trimesh(vertices=outer_vertices, faces=outer_faces)
        outer_mesh.fix_normals()

    if inner_vertices is None:
        if not allow_bosses:
            raise ValueError("inner_vertices must be provided for magnet placement without adding bosses.")
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
        boss_flags = [True] * len(centers)
    else:
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

        centers, chosen_lons, boss_flags = find_valid_magnet_positions_no_bosses(
            outer_mesh=outer_mesh,
            inner_mesh=inner_mesh,
            r_enc=r_enc,
            h_boss=h_boss,
            step_degrees=step_degrees,
            n_magnets=n_mag,
            min_magnets=min_mag,
            min_angular_spacing=min_angular_spacing,
            candidate_angles=cand_angles,
            placement_strategy=placement_strategy,
            angle_tolerance=angle_tolerance,
            allow_bosses=allow_bosses,
            return_details=True,
        )

    top_bosses = []
    top_voids = []
    bottom_bosses = []
    bottom_voids = []

    for (x, y), needs_boss in zip(centers, boss_flags):
        if needs_boss:
            tb = trimesh.creation.cylinder(radius=r_enc, height=h_boss)
            tb.apply_translation([x, y, h_boss / 2.0])
            top_bosses.append(tb)

            bb = trimesh.creation.cylinder(radius=r_enc, height=h_boss)
            bb.apply_translation([x, y, -h_boss / 2.0])
            bottom_bosses.append(bb)

        tv = trimesh.creation.cylinder(radius=r_void, height=h_void)
        tv.apply_translation([x, y, vertical_offset + h_void / 2.0])
        top_voids.append(tv)

        bv = trimesh.creation.cylinder(radius=r_void, height=h_void)
        bv.apply_translation([x, y, -(vertical_offset + h_void / 2.0)])
        bottom_voids.append(bv)

    bool_kwargs = {}
    if engine is not None:
        bool_kwargs['engine'] = engine

    if top_bosses:
        top_with_bosses = trimesh.boolean.union([top_mesh] + top_bosses, **bool_kwargs)
        if top_with_bosses is None:
            raise ValueError("Boolean union of top hemisphere and magnet bosses failed.")
    else:
        top_with_bosses = top_mesh

    top_final = trimesh.boolean.difference([top_with_bosses] + top_voids, **bool_kwargs)
    if top_final is None:
        raise ValueError("Boolean subtraction of top magnet voids failed.")

    if bottom_bosses:
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
    """Generates a Z-aligned cylindrical test piece for calibrating magnet fits.

    The outer cylinder has a radius of `r_enc + 2mm` to provide stability on the print bed.
    The void is centered in XY and starts at `vertical_offset` from the bottom Z=0 plane.

    Args:
        diameter (float): Magnet diameter in mm.
        height (float): Magnet height/thickness in mm.
        horizontal_tolerance (float, optional): Radial tolerance to add. Defaults to 0.1.
        vertical_tolerance (float, optional): Vertical tolerance to add. Defaults to 0.1.
        vertical_offset (float, optional): Distance from bottom to void. Defaults to 0.2.
        min_thickness (float, optional): Minimum wall/roof thickness. Defaults to 1.5.
        output_path (str, optional): File path to export test piece mesh. Defaults to None.

    Returns:
        trimesh.Trimesh: The generated test piece mesh.
    """
    r_void = diameter / 2.0 + horizontal_tolerance
    h_void = height + vertical_tolerance

    r_enc = r_void + min_thickness
    h_boss = vertical_offset + h_void + min_thickness

    r_outer = r_enc + 2.0
    outer_cyl = trimesh.creation.cylinder(radius=r_outer, height=h_boss)
    outer_cyl.apply_translation([0.0, 0.0, h_boss / 2.0])

    void_cyl = trimesh.creation.cylinder(radius=r_void, height=h_void)
    void_cyl.apply_translation([0.0, 0.0, vertical_offset + h_void / 2.0])

    test_piece = trimesh.boolean.difference([outer_cyl, void_cyl])
    if test_piece is None:
        raise ValueError("Boolean subtraction for test piece generation failed.")

    if output_path:
        test_piece.export(output_path)

    return test_piece
