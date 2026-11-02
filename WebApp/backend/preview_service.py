"""Preview evaluation service providing binary WebGL buffers, WebWorker grid buffers, and 2D maps."""

import base64
import io
import os
from typing import Any, Dict, List, Optional, Tuple
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.interpolate import RegularGridInterpolator

from globe3d import apply_banded_colormap, create_banded_colormap, datasets, parse_color
from globe3d.displacement import _wrap_longitude
from .engine import (
    _generate_synthetic_grid,
    compile_globe_model,
    resolve_project_grids,
    resolve_shapefile_path,
)
from .filament_service import generate_palette_response
from .models import GlobeProject

_MASK_CACHE: Dict[Tuple[str, int, int, bool, float], np.ndarray] = {}


def rasterize_shapefile_to_mask(
    shp_path: str,
    height: int = 180,
    width: int = 360,
    is_line: bool = False,
    width_deg: float = 1.0,
) -> np.ndarray:
    """Rasterizes a vector shapefile/GeoJSON into an equirectangular uint8 mask array (height x width).
    Values: 1 for inside/line, 0 for outside.
    Row 0 corresponds to +90 deg North, Row (height-1) to -90 deg South.
    Col 0 corresponds to -180 deg Lon, Col (width-1) to +180 deg Lon.
    """
    cache_key = (os.path.abspath(shp_path), height, width, bool(is_line), float(width_deg))
    if cache_key in _MASK_CACHE:
        return _MASK_CACHE[cache_key]

    import geopandas as gpd
    from PIL import Image, ImageDraw

    img = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(img)

    def lonlat_to_xy(lon: float, lat: float) -> Tuple[float, float]:
        x = (lon + 180.0) / 360.0 * (width - 1)
        y = (90.0 - lat) / 180.0 * (height - 1)
        return (x, y)

    try:
        gdf = gpd.read_file(shp_path)
        for geom in gdf.geometry:
            if geom is None or geom.is_empty:
                continue
            if is_line:
                geoms = geom.geoms if hasattr(geom, "geoms") else [geom]
                line_w = max(1, int(round((width_deg / 360.0) * width)))
                for line in geoms:
                    if hasattr(line, "coords"):
                        pts = [lonlat_to_xy(x, y) for x, y in line.coords]
                        if len(pts) >= 2:
                            draw.line(pts, fill=1, width=line_w)
            else:
                geoms = geom.geoms if hasattr(geom, "geoms") else [geom]
                for poly in geoms:
                    if hasattr(poly, "exterior") and poly.exterior:
                        exterior = [lonlat_to_xy(x, y) for x, y in poly.exterior.coords]
                        if len(exterior) >= 3:
                            draw.polygon(exterior, outline=1, fill=1)
                        for interior in getattr(poly, "interiors", []):
                            hole = [lonlat_to_xy(x, y) for x, y in interior.coords]
                            if len(hole) >= 3:
                                draw.polygon(hole, outline=0, fill=0)
    except Exception as e:
        print(f"Error rasterizing shapefile {shp_path}: {e}")

    mask = np.asarray(img, dtype=np.uint8)
    _MASK_CACHE[cache_key] = mask
    return mask


def _array_to_b64(arr: np.ndarray, dtype) -> str:
    """Encodes a contiguous NumPy array into a base64 string."""
    contig = np.ascontiguousarray(arr, dtype=dtype)
    return base64.b64encode(contig.tobytes()).decode("ascii")


def evaluate_preview_mesh(project: GlobeProject, preview_n_points: Optional[int] = None) -> Dict[str, Any]:
    """Evaluates the authoritative Python GlobeModel and returns base64 typed-array buffers.

    Args:
        project (GlobeProject): Project configuration.
        preview_n_points (int, optional): Vertex count override. Defaults to None (uses
            project.geometry.preview_n_points or project.geometry.n_points).

    Returns:
        dict: Base64 buffers for outer/inner positions, indices, colors, and mesh statistics.
    """
    n_pts = int(preview_n_points or project.geometry.preview_n_points or project.geometry.n_points)
    model = compile_globe_model(project, n_points_override=n_pts)

    outer_v = model.outer_vertices
    outer_f = model.outer_faces
    outer_c = (
        model.outer_colors
        if model.outer_colors is not None
        else np.ones((len(outer_v), 3), dtype=np.float32)
    )

    r_outer = np.linalg.norm(outer_v, axis=1)
    min_r = float(np.min(r_outer))
    max_r = float(np.max(r_outer))

    has_inner = model.inner_vertices is not None and model.inner_faces is not None
    if has_inner:
        inner_v = model.inner_vertices
        inner_f = model.inner_faces
        inner_c = (
            model.inner_colors
            if model.inner_colors is not None
            else np.ones((len(inner_v), 3), dtype=np.float32)
        )
        r_inner = np.linalg.norm(inner_v, axis=1)
        min_thickness = float(np.min(r_outer) - np.max(r_inner))
    else:
        inner_v = np.zeros((0, 3), dtype=np.float32)
        inner_f = np.zeros((0, 3), dtype=np.uint32)
        inner_c = np.zeros((0, 3), dtype=np.float32)
        min_thickness = min_r

    return {
        "n_outer": int(len(outer_v)),
        "n_inner": int(len(inner_v)),
        "outer_positions_b64": _array_to_b64(outer_v, np.float32),
        "outer_indices_b64": _array_to_b64(outer_f, np.uint32),
        "outer_colors_b64": _array_to_b64(outer_c, np.float32),
        "inner_positions_b64": _array_to_b64(inner_v, np.float32) if has_inner else "",
        "inner_indices_b64": _array_to_b64(inner_f, np.uint32) if has_inner else "",
        "inner_colors_b64": _array_to_b64(inner_c, np.float32) if has_inner else "",
        "stats": {
            "min_radius": round(min_r, 3),
            "max_radius": round(max_r, 3),
            "min_thickness": round(min_thickness, 3),
            "vertex_count": int(len(outer_v) + len(inner_v)),
            "face_count": int(len(outer_f) + len(inner_f)),
        },
    }


def get_grid_buffer_for_worker(project: GlobeProject, height: int = 180, width: int = 360) -> Dict[str, Any]:
    """Produces a standardized (height, width) equirectangular elevation & RGB buffer for the WebWorker.

    Args:
        project (GlobeProject): Project configuration.
        height (int, optional): Latitude samples (-90 to +90). Defaults to 180.
        width (int, optional): Longitude samples (-180 to +180). Defaults to 360.

    Returns:
        dict: Grid dimensions, value bounds, base64 Float32 elevation buffer, and base64 Uint8 RGB buffer.
    """
    grids_out: Dict[str, Any] = {}
    target_lats = np.linspace(90.0, -90.0, height)
    target_lons = np.linspace(-180.0, 180.0, width)
    lon_m, lat_m = np.meshgrid(target_lons, target_lats)
    sample_pts = np.stack((lat_m, lon_m), axis=-1)

    def _sample_north_up(g_obj):
        w_lats, w_lons, w_grid = _wrap_longitude(
            g_obj.lats, g_obj.lons, np.nan_to_num(g_obj.grid)
        )
        interp_fn = RegularGridInterpolator(
            (w_lats, w_lons),
            w_grid,
            bounds_error=False,
            fill_value=None,
        )
        return interp_fn(sample_pts).astype(np.float32)

    tex_path = None
    if project.mode == "paleo" or project.paleo_config.enabled:
        pc = project.paleo_config
        try:
            grid, tex_path, _ = datasets.paleo.scotese(
                age=pc.age,
                name=pc.name,
                resolution=pc.resolution,
                data_dir=pc.data_dir,
            )
        except Exception:
            grid = _generate_synthetic_grid("continents", {"amplitude": 3500.0})
        sampled_elev = _sample_north_up(grid)
        for g_cfg in project.grids:
            grids_out[g_cfg.id] = {
                "width": width,
                "height": height,
                "vmin": round(float(np.min(sampled_elev)), 2),
                "vmax": round(float(np.max(sampled_elev)), 2),
                "elevation_f32_b64": _array_to_b64(sampled_elev, np.float32),
            }
    else:
        grids_by_id, textures_by_id = resolve_project_grids(project)
        grid = next(iter(grids_by_id.values()))
        tex_path = next(iter(textures_by_id.values()))
        sampled_elev = None
        for gid, g_obj in grids_by_id.items():
            s_elev = _sample_north_up(g_obj)
            if sampled_elev is None:
                sampled_elev = s_elev
            grids_out[gid] = {
                "width": width,
                "height": height,
                "vmin": round(float(np.min(s_elev)), 2),
                "vmax": round(float(np.max(s_elev)), 2),
                "elevation_f32_b64": _array_to_b64(s_elev, np.float32),
            }
        if sampled_elev is None:
            sampled_elev = _sample_north_up(grid)

    # Also build an RGB texture (height x width x 3, row 0 = +90 deg North to match target_lats)
    if tex_path and os.path.exists(tex_path) and (
        project.mode != "paleo" or project.paleo_config.color_mode == "paleoatlas"
    ):
        img = Image.open(tex_path).convert("RGB").resize((width, height))
        rgb_arr = np.asarray(img, dtype=np.uint8)
    else:
        cmap_name = (
            project.paleo_config.cmap
            if project.mode == "paleo"
            else (project.colourers[0].cmap if project.colourers else "terrain")
        )
        vmin = float(np.nanmin(sampled_elev))
        vmax = float(np.nanmax(sampled_elev))
        span = (vmax - vmin) if vmax > vmin else 1.0
        norm_v = np.clip((sampled_elev - vmin) / span, 0.0, 1.0)
        cmap = plt.get_cmap(cmap_name or "terrain")
        rgb_arr = (cmap(norm_v)[:, :, :3] * 255.0).astype(np.uint8)

    # Collect and rasterize vector shapefiles for preview displacers & colourers
    masks_out: Dict[str, Any] = {}
    try:
        land_shp = datasets.shapefiles.land()
        land_m = rasterize_shapefile_to_mask(land_shp, height=height, width=width, is_line=False)
        masks_out["land"] = {
            "width": width,
            "height": height,
            "mask_u8_b64": _array_to_b64(land_m, np.uint8),
        }
        masks_out["default"] = masks_out["land"]
    except Exception:
        pass

    try:
        coast_shp = datasets.shapefiles.coastline()
        coast_m = rasterize_shapefile_to_mask(coast_shp, height=height, width=width, is_line=True, width_deg=1.5)
        masks_out["coastline"] = {
            "width": width,
            "height": height,
            "mask_u8_b64": _array_to_b64(coast_m, np.uint8),
        }
    except Exception:
        pass

    for d in (project.outer_displacements or []) + (project.inner_displacements or []):
        if d.enabled and d.type in ("PolygonDisplacer", "LineDisplacer") and d.shapefile:
            shp_p = resolve_shapefile_path(d.shapefile, default_type="land" if d.type == "PolygonDisplacer" else "coastline")
            if shp_p and os.path.isfile(shp_p) and d.shapefile not in masks_out:
                m = rasterize_shapefile_to_mask(shp_p, height=height, width=width, is_line=(d.type == "LineDisplacer"), width_deg=float(getattr(d, "width_deg", 1.5)))
                masks_out[d.shapefile] = {
                    "width": width,
                    "height": height,
                    "mask_u8_b64": _array_to_b64(m, np.uint8),
                }

    for c in project.colourers or []:
        if c.enabled and c.type in ("PolygonColourer", "LineColourer") and c.shapefile:
            shp_p = resolve_shapefile_path(c.shapefile, default_type="land" if c.type == "PolygonColourer" else "coastline")
            if shp_p and os.path.isfile(shp_p) and c.shapefile not in masks_out:
                m = rasterize_shapefile_to_mask(shp_p, height=height, width=width, is_line=(c.type == "LineColourer"), width_deg=float(getattr(c, "width_deg", 1.5)))
                masks_out[c.shapefile] = {
                    "width": width,
                    "height": height,
                    "mask_u8_b64": _array_to_b64(m, np.uint8),
                }

    return {
        "width": width,
        "height": height,
        "vmin": round(float(np.min(sampled_elev)), 2),
        "vmax": round(float(np.max(sampled_elev)), 2),
        "elevation_f32_b64": _array_to_b64(sampled_elev, np.float32),
        "rgb_u8_b64": _array_to_b64(rgb_arr, np.uint8),
        "grids": grids_out,
        "masks": masks_out,
    }


def render_2d_map_and_colorbar(project: GlobeProject) -> Dict[str, Any]:
    """Renders 2D equirectangular map and colorbar PNG data URLs matching the active globe colouring.

    Args:
        project (GlobeProject): Project configuration.

    Returns:
        dict: Data URLs for the 2D map and colorbar images, plus value bounds and band metadata.
    """
    grids_by_id, textures_by_id = resolve_project_grids(project)
    default_grid = next(iter(grids_by_id.values()))
    default_tex = next(iter(textures_by_id.values()))
    grid = default_grid
    tex_path = default_tex

    if project.mode == "paleo" or project.paleo_config.enabled:
        try:
            grid, tex_path, _ = datasets.paleo.scotese(
                age=project.paleo_config.age,
                resolution=project.paleo_config.resolution,
                data_dir=project.paleo_config.data_dir,
            )
        except Exception:
            grid = default_grid

    palette_resp = generate_palette_response(project.filaments)
    by_code = {e["code"]: tuple(e["rgb"]) for e in palette_resp["entries"]}

    bands_out = []
    rgb_map = None
    cmap_obj = plt.get_cmap("terrain")
    vmin_val = float(np.nanmin(grid.grid))
    vmax_val = float(np.nanmax(grid.grid))
    norm_obj = plt.Normalize(vmin=vmin_val, vmax=vmax_val)

    def _build_banded_from_pc():
        nonlocal rgb_map, cmap_obj, norm_obj, bands_out
        pc = project.paleo_config
        colors = []
        thresholds = []
        for i, b in enumerate(pc.band_thresholds):
            rgb = parse_color(b.color) if b.color else by_code.get(b.code, (128, 128, 128))
            colors.append(rgb)
            bands_out.append({
                "threshold": b.threshold,
                "code": b.code,
                "label": b.label or f"Band {i + 1}",
                "rgb": list(rgb),
            })
            if i < len(pc.band_thresholds) - 1:
                thresholds.append(float(b.threshold))
        if len(colors) >= 2 and len(thresholds) == len(colors) - 1:
            rgb_map = apply_banded_colormap(grid, colors, thresholds)
            cmap_obj, norm_obj = create_banded_colormap(colors, thresholds)

    if project.mode == "paleo" or project.paleo_config.enabled:
        pc = project.paleo_config
        if pc.color_mode == "banded_4filament" or project.filaments.enabled:
            _build_banded_from_pc()
        elif pc.color_mode == "paleoatlas" and tex_path and os.path.exists(tex_path):
            pil_img = Image.open(tex_path).convert("RGB")
            rgb_map = np.asarray(pil_img, dtype=np.uint8)
            cmap_obj = plt.get_cmap(pc.cmap or "terrain")
            norm_obj = plt.Normalize(vmin=vmin_val, vmax=vmax_val)
        else:
            cmap_obj = plt.get_cmap(pc.cmap or "terrain")
            span = (vmax_val - vmin_val) if vmax_val > vmin_val else 1.0
            norm_v = np.clip((np.flipud(grid.grid) - vmin_val) / span, 0.0, 1.0)
            norm_obj = plt.Normalize(vmin=vmin_val, vmax=vmax_val)
            rgb_map = (cmap_obj(norm_v)[:, :, :3] * 255.0).astype(np.uint8)
    else:
        # Custom recipe mode: inspect enabled outer/all colourers
        if project.filaments.enabled and project.paleo_config.band_thresholds:
            _build_banded_from_pc()
        else:
            outer_cols = [
                c for c in project.colourers
                if c.enabled and c.target in ("outer", "all")
            ]
            primary_col = outer_cols[0] if outer_cols else (project.colourers[0] if project.colourers else None)
            for c in outer_cols:
                if c.type in ("GridColourer", "ImageColourer", "PolygonColourer", "ConstantColourer"):
                    primary_col = c
                    break

            if primary_col is not None:
                if primary_col.type == "GridColourer":
                    grid = grids_by_id.get(primary_col.grid_id or "", default_grid)
                    g_min = float(np.nanmin(grid.grid))
                    g_max = float(np.nanmax(grid.grid))
                    if primary_col.use_banded_levels and primary_col.colors and primary_col.levels:
                        colors = []
                        for c_item in primary_col.colors:
                            if isinstance(c_item, str) and c_item.strip() in by_code:
                                colors.append(by_code[c_item.strip()])
                            else:
                                try:
                                    colors.append(parse_color(c_item))
                                except Exception:
                                    colors.append((128, 128, 128))
                        lvls = [float(x) for x in primary_col.levels]
                        if len(lvls) == len(colors) + 1:
                            thresholds = lvls[1:-1]
                        elif len(lvls) == len(colors):
                            thresholds = lvls[:-1]
                        else:
                            thresholds = lvls[: max(0, len(colors) - 1)]
                        if len(colors) >= 2 and len(thresholds) == len(colors) - 1:
                            rgb_map = apply_banded_colormap(grid, colors, thresholds)
                            cmap_obj, norm_obj = create_banded_colormap(colors, thresholds)
                            for idx_b, col_rgb in enumerate(colors):
                                th_val = thresholds[idx_b] if idx_b < len(thresholds) else g_max
                                bands_out.append({
                                    "threshold": th_val,
                                    "code": str(primary_col.colors[idx_b]),
                                    "label": f"Band {idx_b + 1}",
                                    "rgb": list(col_rgb),
                                })
                    if rgb_map is None:
                        g_span = max(g_max - g_min, 1e-6)
                        vmin_val = float(primary_col.vmin) if primary_col.vmin is not None else g_min
                        vmax_val = float(primary_col.vmax) if primary_col.vmax is not None else g_max
                        c_span = vmax_val - vmin_val
                        if c_span <= 0 or c_span > 5.0 * g_span or c_span < 0.35 * g_span or vmax_val < g_min or vmin_val > g_max:
                            vmin_val, vmax_val = g_min, g_max
                        if primary_col.symmetric and (primary_col.vmin is None or vmin_val == g_min):
                            abs_m = max(abs(g_min), abs(g_max), 1e-6)
                            vmin_val, vmax_val = -abs_m, abs_m
                        span = (vmax_val - vmin_val) if vmax_val > vmin_val else 1.0
                        norm_v = np.clip((np.flipud(grid.grid) - vmin_val) / span, 0.0, 1.0)
                        try:
                            cmap_obj = plt.get_cmap(primary_col.cmap or "terrain")
                        except Exception:
                            cmap_obj = plt.get_cmap("terrain")
                        norm_obj = plt.Normalize(vmin=vmin_val, vmax=vmax_val)
                        rgb_map = (cmap_obj(norm_v)[:, :, :3] * 255.0).astype(np.uint8)

                elif primary_col.type == "ImageColourer":
                    img_p = primary_col.image_path or default_tex
                    if img_p and os.path.exists(img_p):
                        pil_img = Image.open(img_p).convert("RGB")
                        rgb_map = np.asarray(pil_img, dtype=np.uint8)
                elif primary_col.type == "ConstantColourer":
                    c_rgb = parse_color(primary_col.color or "#3b82f6")
                    rgb_map = np.full((180, 360, 3), c_rgb, dtype=np.uint8)
                elif primary_col.type == "PolygonColourer":
                    fg_rgb = parse_color(primary_col.color or "#22c55e")
                    bg_rgb = parse_color(primary_col.background_color) if primary_col.background_color else (30, 64, 175)
                    shp_p = resolve_shapefile_path(primary_col.shapefile, default_type="land")
                    poly_m = rasterize_shapefile_to_mask(shp_p, height=180, width=360, is_line=False)
                    rgb_map = np.full((180, 360, 3), bg_rgb, dtype=np.uint8)
                    inside = bool(primary_col.flood_inside)
                    if inside:
                        rgb_map[poly_m > 0] = fg_rgb
                    else:
                        rgb_map[poly_m == 0] = fg_rgb

    if rgb_map is None:
        vmin_val = float(np.nanmin(grid.grid))
        vmax_val = float(np.nanmax(grid.grid))
        span = (vmax_val - vmin_val) if vmax_val > vmin_val else 1.0
        norm_v = np.clip((np.flipud(grid.grid) - vmin_val) / span, 0.0, 1.0)
        cmap_obj = plt.get_cmap("terrain")
        norm_obj = plt.Normalize(vmin=vmin_val, vmax=vmax_val)
        rgb_map = (cmap_obj(norm_v)[:, :, :3] * 255.0).astype(np.uint8)

    # Encode 2D map as PNG data URL
    pil_map = Image.fromarray(rgb_map)
    if pil_map.width > 720:
        pil_map = pil_map.resize((720, 360))
    map_buf = io.BytesIO()
    pil_map.save(map_buf, format="PNG")
    map_b64 = base64.b64encode(map_buf.getvalue()).decode("ascii")

    # Render colorbar as PNG data URL
    fig, ax = plt.subplots(figsize=(7.5, 1.1), dpi=110)
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")
    cb = plt.colorbar(
        plt.cm.ScalarMappable(cmap=cmap_obj, norm=norm_obj),
        cax=ax,
        orientation="horizontal",
    )
    cb.ax.tick_params(colors="#e2e8f0", labelsize=8)
    cb.outline.set_edgecolor("#475569")
    plt.tight_layout()
    cbar_buf = io.BytesIO()
    fig.savefig(cbar_buf, format="PNG", facecolor=fig.get_facecolor())
    plt.close(fig)
    cbar_b64 = base64.b64encode(cbar_buf.getvalue()).decode("ascii")

    return {
        "map_image_data_url": f"data:image/png;base64,{map_b64}",
        "colorbar_image_data_url": f"data:image/png;base64,{cbar_b64}",
        "vmin": round(vmin_val, 2),
        "vmax": round(vmax_val, 2),
        "bands": bands_out,
    }
