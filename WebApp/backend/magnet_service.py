"""Magnet optimization, equatorial cross-section profiling, and calibration test piece service."""

import os
from typing import Any, Dict, List
import numpy as np
from scipy.spatial import cKDTree

from globe3d.magnets import (
    find_valid_magnet_positions_no_bosses,
    generate_magnet_test_piece,
    optimize_magnet_positions,
)
from .engine import compile_globe_model
from .models import GlobeProject, MagnetTestPieceRequest


def optimize_and_inspect_magnets(project: GlobeProject) -> Dict[str, Any]:
    """Evaluates the 360-degree equatorial cross-section profile and optimizes magnet positions.

    Args:
        project (GlobeProject): Project configuration.

    Returns:
        dict: 360-degree radial profile (d_min, d_max, wall_thickness), optimized angles,
            3D magnet centers, clearance margins, and needs_boss flags.
    """
    preview_pts = min(int(project.geometry.preview_n_points or 20000), 35000)
    model = compile_globe_model(project, n_points_override=preview_pts)

    mag = project.magnets
    r_void = float(mag.diameter) / 2.0 + float(mag.clearance)
    h_void = float(mag.height) + float(mag.clearance)
    v_offset = float(getattr(mag, "embed_depth", 0.2) or 0.2)
    r_enc = r_void + float(mag.min_margin)
    h_boss = v_offset + h_void + float(mag.min_margin)

    # Sample equatorial radial profile (0..359 deg) for outer and inner shells
    outer_v = model.outer_vertices
    outer_r = np.linalg.norm(outer_v, axis=1)
    outer_u = outer_v / np.where(outer_r[:, None] == 0, 1.0, outer_r[:, None])
    outer_tree = cKDTree(outer_u)

    has_inner = model.inner_vertices is not None
    if has_inner:
        inner_v = model.inner_vertices
        inner_r = np.linalg.norm(inner_v, axis=1)
        inner_u = inner_v / np.where(inner_r[:, None] == 0, 1.0, inner_r[:, None])
        inner_tree = cKDTree(inner_u)
    else:
        inner_r = np.zeros(1)
        inner_tree = None

    profile_deg = list(range(360))
    thetas = np.radians(profile_deg)
    eq_dirs = np.column_stack([np.cos(thetas), np.sin(thetas), np.zeros_like(thetas)])

    _, idx_out = outer_tree.query(eq_dirs)
    d_max_arr = outer_r[idx_out]

    if has_inner and inner_tree is not None:
        _, idx_in = inner_tree.query(eq_dirs)
        d_min_arr = inner_r[idx_in]
    else:
        d_min_arr = np.zeros_like(d_max_arr)

    wall_arr = d_max_arr - d_min_arr

    # Determine magnet angles & centers
    count = max(1, int(mag.count))
    allow_bosses = float(mag.boss_thickness) > 0

    chosen_angles: List[float] = []
    centers_xy: List[Any] = []
    boss_flags: List[bool] = []

    outer_tm = model.to_trimesh(part="outer")
    if has_inner:
        try:
            inner_tm = model.to_trimesh(part="inner")
            cand_angles = (
                [float(a % 360.0) for a in mag.manual_angles]
                if (mag.manual_angles and len(mag.manual_angles) > 0 and not mag.Optimize_positions)
                else None
            )
            centers_xy, chosen_lons, boss_flags = find_valid_magnet_positions_no_bosses(
                outer_mesh=outer_tm,
                inner_mesh=inner_tm,
                r_enc=r_enc,
                h_boss=h_boss,
                step_degrees=2.0,
                n_magnets=len(cand_angles) if cand_angles else count,
                min_magnets=len(cand_angles) if cand_angles else max(1, min(count, 2)),
                min_angular_spacing=10.0 if cand_angles else max(15.0, 240.0 / count),
                candidate_angles=cand_angles,
                allow_bosses=True,
                return_details=True,
            )
            chosen_angles = [float(a % 360.0) for a in chosen_lons]
        except Exception:
            chosen_angles = []

    if not chosen_angles:
        if mag.manual_angles and len(mag.manual_angles) > 0 and not mag.Optimize_positions:
            chosen_angles = [float(a % 360.0) for a in mag.manual_angles]
        else:
            chosen_angles = [float((i * 360.0) / count) for i in range(count)]
        # Use 3D cylinder containment bisection so bosses never protrude outside outer_tm
        opt_centers = optimize_magnet_positions(
            longitudes=chosen_angles,
            outer_mesh=outer_tm,
            r_enc=r_enc,
            h_boss=h_boss,
        )
        centers_xy = []
        boss_flags = []
        for ang, (ox, oy) in zip(chosen_angles, opt_centers):
            idx_deg = int(round(ang)) % 360
            d_max_safe = float(np.hypot(ox, oy))
            d_min_safe = float(d_min_arr[idx_deg]) + r_enc if has_inner else 0.0
            rad = np.radians(ang)
            if has_inner and d_min_safe <= d_max_safe:
                best_d = 0.5 * (d_min_safe + d_max_safe)
                needs_b = False
            else:
                best_d = d_max_safe
                needs_b = bool(has_inner)
            centers_xy.append((best_d * float(np.cos(rad)), best_d * float(np.sin(rad))))
            boss_flags.append(needs_b)

    magnets_list = []
    for i, ang in enumerate(chosen_angles):
        idx_deg = int(round(ang)) % 360
        d_in = float(d_min_arr[idx_deg])
        d_out = float(d_max_arr[idx_deg])
        cx, cy = centers_xy[i] if i < len(centers_xy) else (0.0, 0.0)
        r_center = float(np.hypot(cx, cy))
        r_outer_corner = float(np.hypot(r_center + r_void, v_offset + h_void))
        margin_inner = float((r_center - r_void) - d_in)
        margin_outer = float(d_out - r_outer_corner)
        needs_boss = bool(boss_flags[i]) if i < len(boss_flags) else (margin_inner < mag.min_margin)
        valid = bool(margin_outer >= float(mag.min_margin) * 0.5 and (allow_bosses or not needs_boss))

        magnets_list.append({
            "index": i,
            "angle_deg": round(float(ang), 2),
            "center": [round(float(cx), 3), round(float(cy), 3), 0.0],
            "r_center": round(r_center, 3),
            "d_min_at_angle": round(d_in, 3),
            "d_max_at_angle": round(d_out, 3),
            "margin_inner": round(margin_inner, 3),
            "margin_outer": round(margin_outer, 3),
            "needs_boss": needs_boss,
            "valid": valid,
        })

    return {
        "angles_deg": [m["angle_deg"] for m in magnets_list],
        "profile_deg": profile_deg,
        "d_min": [round(float(v), 3) for v in d_min_arr],
        "d_max": [round(float(v), 3) for v in d_max_arr],
        "wall_thickness": [round(float(v), 3) for v in wall_arr],
        "r_void": round(r_void, 3),
        "r_enc": round(r_enc, 3),
        "magnets": magnets_list,
    }


def create_calibration_test_piece(req: MagnetTestPieceRequest, repo_root: str) -> Dict[str, Any]:
    """Generates a cylindrical STL calibration test piece for verifying physical magnet fit.

    Args:
        req (MagnetTestPieceRequest): Magnet dimensions and clearance tolerances.
        repo_root (str): Repository root path.

    Returns:
        dict: Saved file path, size, and download URL.
    """
    out_dir = req.output_dir or "outputs"
    if not os.path.isabs(out_dir):
        out_dir = os.path.join(repo_root, out_dir)
    os.makedirs(out_dir, exist_ok=True)

    filename = f"magnet_test_piece_{req.diameter:.1f}x{req.height:.1f}mm.stl"
    out_path = os.path.abspath(os.path.join(out_dir, filename))

    generate_magnet_test_piece(
        diameter=float(req.diameter),
        height=float(req.height),
        horizontal_tolerance=float(req.clearance),
        vertical_tolerance=float(req.clearance),
        output_path=out_path,
    )

    return {
        "filename": filename,
        "saved_path": out_path,
        "size_bytes": os.path.getsize(out_path) if os.path.exists(out_path) else 0,
        "download_url": f"/api/exports/download?path={out_path}",
    }
