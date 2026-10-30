"""Authoritative globe3d compilation and execution engine for GlobeProject JSON configurations."""

import os
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image

from globe3d import (
    ConstantColourer,
    ConstantDisplacer,
    GeographicGrid,
    GlobeModel,
    GridColourer,
    GridDisplacer,
    ImageColourer,
    LineColourer,
    LineDisplacer,
    MagnetSettings,
    PointColourer,
    PointDisplacer,
    PoleLabelColourer,
    PolygonColourer,
    PolygonDisplacer,
    SymbolColourer,
    TextColourer,
    apply_banded_colormap,
    calculate_displacement_scale,
    create_banded_colormap,
    datasets,
    parse_color,
    reconstruct_grid,
)
from globe3d.image import (
    add_pole_markers,
    add_svg_symbol_spherical,
    simplify_colors,
    simplify_image_bilateral,
    simplify_image_median,
    undo_hillshading,
)
from .filament_service import generate_palette_response, get_spools_from_config
from .models import (
    ColourerConfigModel,
    DisplacerConfigModel,
    GlobeProject,
    GridSourceModel,
)

# In-memory cache of loaded base grids keyed by (source, dataset, filepath, params_repr)
_GRID_CACHE: Dict[str, Tuple[GeographicGrid, Optional[str], Optional[Dict[str, Any]]]] = {}


def _generate_synthetic_grid(synthetic_type: str = "procedural_waves", params: Optional[Dict[str, Any]] = None) -> GeographicGrid:
    """Generates a fast procedural/synthetic GeographicGrid for examples or offline testing.

    Args:
        synthetic_type (str, optional): Type of procedural pattern. Defaults to 'procedural_waves'.
        params (dict, optional): Optional parameters (amplitude, frequency, etc.).

    Returns:
        GeographicGrid: Synthetic global grid (-90..90, -180..180).
    """
    p = params or {}
    step = float(p.get("step", 1.0))
    lats = np.arange(-90.0, 90.0 + step * 0.5, step)
    lons = np.arange(-180.0, 180.0 + step * 0.5, step)
    lon_m, lat_m = np.meshgrid(lons, lats)
    lat_r = np.radians(lat_m)
    lon_r = np.radians(lon_m)

    amp = float(p.get("amplitude", 3000.0))
    st = (synthetic_type or "procedural_waves").lower()
    if st in ("harmonic", "spherical_harmonics", "waves", "procedural_waves"):
        n_lat = int(p.get("n_lat", 4))
        n_lon = int(p.get("n_lon", 5))
        data = amp * (
            0.6 * np.sin(n_lat * lat_r) * np.cos(n_lon * lon_r)
            + 0.4 * np.cos((n_lat + 2) * lat_r) * np.sin((n_lon + 2) * lon_r)
        )
    elif st in ("continents", "synthetic_earth"):
        data = amp * (
            0.5 * np.sin(2.0 * lat_r) * np.cos(2.0 * lon_r)
            + 0.35 * np.cos(3.0 * lat_r) * np.sin(3.0 * lon_r)
            + 0.15 * np.sin(5.0 * lat_r) * np.cos(4.0 * lon_r)
        )
    elif st in ("prem_shell", "constant", "flat"):
        val = float(p.get("value", 0.0))
        data = np.full_like(lat_m, val)
    else:
        data = amp * np.sin(3.0 * lat_r) * np.cos(4.0 * lon_r)

    return GeographicGrid(lats, lons, data)


def _load_base_grid(grid_cfg: GridSourceModel) -> Tuple[GeographicGrid, Optional[str], Optional[Dict[str, Any]]]:
    """Loads a raw GeographicGrid from an online dataset, local file, synthetic generator, or paleo catalog.

    Args:
        grid_cfg (GridSourceModel): Grid source configuration.

    Returns:
        tuple: (GeographicGrid, optional_texture_path, optional_metadata)
    """
    cache_key = f"{grid_cfg.source}:{grid_cfg.dataset}:{grid_cfg.filepath}:{grid_cfg.synthetic_type}:{sorted((grid_cfg.params or {}).items())}"
    if cache_key in _GRID_CACHE:
        g, tex, meta = _GRID_CACHE[cache_key]
        return GeographicGrid(g.lats.copy(), g.lons.copy(), g.grid.copy()), tex, meta

    tex_path = None
    meta = None
    src = (grid_cfg.source or "online").lower()
    params = dict(grid_cfg.params or {})

    if src == "synthetic":
        grid = _generate_synthetic_grid(grid_cfg.synthetic_type or "procedural_waves", params)
    elif src in ("local", "local_or_dataset"):
        local_exists = bool(grid_cfg.filepath and os.path.exists(grid_cfg.filepath))
        if local_exists:
            ext = os.path.splitext(grid_cfg.filepath)[1].lower()
            if ext in (".tif", ".tiff"):
                grid = datasets._load_tiff_grid(
                    grid_cfg.filepath,
                    downsample_factor=int(params.get("downsample_factor", 1)),
                )
            else:
                grid = datasets._load_netcdf_grid(
                    grid_cfg.filepath,
                    lat_var=grid_cfg.lat_var,
                    lon_var=grid_cfg.lon_var,
                    data_var=grid_cfg.data_var,
                )
        elif grid_cfg.dataset:
            # Fall back to specified online dataset instead of procedural grid
            ds_name = (grid_cfg.dataset or "topography.earth").lower()
            try:
                if ds_name in ("topography.earth", "earth"):
                    grid = datasets.topography.earth(**params)
                elif ds_name in ("topography.etopo", "etopo"):
                    grid = datasets.topography.etopo(**params)
                elif ds_name in ("topography.gebco", "gebco"):
                    grid = datasets.topography.gebco(**params)
                elif ds_name in ("topography.mars", "mars"):
                    grid = datasets.topography.mars(**params)
                elif ds_name in ("topography.moon", "moon"):
                    grid = datasets.topography.moon(**params)
                elif ds_name in ("topography.venus", "venus"):
                    grid = datasets.topography.venus(**params)
                elif ds_name in ("topography.mercury", "mercury"):
                    grid = datasets.topography.mercury(**params)
                elif ds_name in ("tomography.s40rts", "s40rts"):
                    grid = datasets.tomography.s40rts(**params)
                elif ds_name in ("geoid.egm2008", "egm2008"):
                    grid = datasets.geoid.egm2008(**params)
                elif ds_name in ("crust.crust1", "crust1"):
                    grid = datasets.crust.crust1(**params)
                elif ds_name in ("lithosphere.thickness", "lithosphere"):
                    grid = datasets.lithosphere.thickness(**params)
                elif ds_name in ("dynamic_topography.hoggard2016", "hoggard2016", "dynamic_topography"):
                    grid = datasets.dynamic_topography.hoggard2016(**params)
                elif ds_name in ("gravity.bouguer", "bouguer", "gravity"):
                    grid = datasets.gravity.bouguer(**params)
                elif ds_name in ("magnetics.emag2", "emag2", "magnetics"):
                    grid = datasets.magnetics.emag2(**params)
                elif ds_name in ("paleo.scotese", "scotese"):
                    grid, tex_path, meta = datasets.paleo.scotese(**params)
                else:
                    grid = _generate_synthetic_grid("continents", params)
            except Exception as e:
                print(f"[engine] Warning: fallback dataset '{ds_name}' failed ({e}), using synthetic grid.")
                grid = _generate_synthetic_grid("continents", params)
        else:
            grid = _generate_synthetic_grid("continents", params)
    elif src == "paleo":
        age = float(params.get("age", 250.0))
        res = str(params.get("resolution", "1d"))
        data_dir = params.get("data_dir")
        try:
            grid, tex_path, meta = datasets.paleo.scotese(age=age, resolution=res, data_dir=data_dir)
        except Exception:
            grid = _generate_synthetic_grid("continents", {"amplitude": 3500.0})
    else:
        # Online dataset e.g. "topography.earth", "tomography.s40rts", "geoid.egm2008", "crust.crust1"
        ds_name = (grid_cfg.dataset or "topography.earth").lower()
        try:
            if ds_name in ("topography.earth", "earth"):
                grid = datasets.topography.earth(**params)
            elif ds_name in ("topography.etopo", "etopo"):
                grid = datasets.topography.etopo(**params)
            elif ds_name in ("topography.gebco", "gebco"):
                grid = datasets.topography.gebco(**params)
            elif ds_name in ("topography.mars", "mars"):
                grid = datasets.topography.mars(**params)
            elif ds_name in ("topography.moon", "moon"):
                grid = datasets.topography.moon(**params)
            elif ds_name in ("topography.venus", "venus"):
                grid = datasets.topography.venus(**params)
            elif ds_name in ("topography.mercury", "mercury"):
                grid = datasets.topography.mercury(**params)
            elif ds_name in ("tomography.s40rts", "s40rts"):
                grid = datasets.tomography.s40rts(**params)
            elif ds_name in ("geoid.egm2008", "egm2008"):
                grid = datasets.geoid.egm2008(**params)
            elif ds_name in ("crust.crust1", "crust1"):
                grid = datasets.crust.crust1(**params)
            elif ds_name in ("lithosphere.thickness", "lithosphere"):
                grid = datasets.lithosphere.thickness(**params)
            elif ds_name in ("dynamic_topography.hoggard2016", "hoggard2016", "dynamic_topography"):
                grid = datasets.dynamic_topography.hoggard2016(**params)
            elif ds_name in ("gravity.bouguer", "bouguer", "gravity"):
                grid = datasets.gravity.bouguer(**params)
            elif ds_name in ("magnetics.emag2", "emag2", "magnetics"):
                grid = datasets.magnetics.emag2(**params)
            elif ds_name in ("paleo.scotese", "scotese"):
                grid, tex_path, meta = datasets.paleo.scotese(**params)
            else:
                grid = _generate_synthetic_grid("continents", params)
        except Exception as e:
            print(f"[engine] Warning: dataset '{ds_name}' failed ({e}), using synthetic grid.")
            grid = _generate_synthetic_grid("continents", params)

    _GRID_CACHE[cache_key] = (grid, tex_path, meta)
    return GeographicGrid(grid.lats.copy(), grid.lons.copy(), grid.grid.copy()), tex_path, meta


def resolve_project_grids(project: GlobeProject) -> Tuple[Dict[str, GeographicGrid], Dict[str, Optional[str]]]:
    """Resolves and executes all declarative grid pipelines in a GlobeProject.

    Args:
        project (GlobeProject): Project configuration.

    Returns:
        tuple: (grids_by_id, textures_by_id)
    """
    grids_by_id: Dict[str, GeographicGrid] = {}
    textures_by_id: Dict[str, Optional[str]] = {}

    for g_cfg in project.grids:
        grid, tex_path, _ = _load_base_grid(g_cfg)

        for op in g_cfg.ops:
            if op.op == "downsample":
                factor = max(1, int(op.factor))
                if factor > 1:
                    grid = GeographicGrid(
                        grid.lats[::factor],
                        grid.lons[::factor],
                        grid.grid[::factor, ::factor],
                    )
            elif op.op == "scale_offset":
                grid = GeographicGrid(
                    grid.lats,
                    grid.lons,
                    grid.grid * float(op.scale) + float(op.offset),
                )
            elif op.op == "airy_moho":
                # Airy isostatic Moho depth calculation from surface elevation grid (in meters)
                # Land (>0): depth = -t0_km*1000 - land_scale * h
                # Ocean (<0): depth = -t0_km*1000 - ocean_scale * h (thinning crust)
                elev = grid.grid
                t0_m = -abs(float(op.t0_km)) * 1000.0
                moho = np.where(
                    elev >= 0.0,
                    t0_m - float(op.land_scale) * elev,
                    t0_m - float(op.ocean_scale) * elev,
                )
                grid = GeographicGrid(grid.lats, grid.lons, moho)
            elif op.op == "composite":
                if op.inputs:
                    accum = np.zeros_like(grid.grid, dtype=np.float64)
                    for inp in op.inputs:
                        ref_id = inp.get("grid_id")
                        w = float(inp.get("weight", 1.0))
                        ref_grid = grids_by_id.get(ref_id, grid)
                        arr = ref_grid.grid.astype(np.float64)
                        if op.normalize:
                            std = float(np.nanstd(arr))
                            if std > 1e-8:
                                arr = (arr - float(np.nanmean(arr))) / std
                        if arr.shape == accum.shape:
                            accum += w * arr
                    if op.clamp_min is not None:
                        accum = np.maximum(accum, float(op.clamp_min))
                    if op.clamp_max is not None:
                        accum = np.minimum(accum, float(op.clamp_max))
                    grid = GeographicGrid(grid.lats, grid.lons, accum)
            elif op.op == "reconstruct":
                try:
                    pm = datasets.paleo.scotese_plate_model()
                    grid = reconstruct_grid(grid, plate_model=pm, age_ma=float(op.age))
                except Exception:
                    pass

        grids_by_id[g_cfg.id] = grid
        textures_by_id[g_cfg.id] = tex_path

    # Always provide a default 'default' grid if none were declared
    if not grids_by_id:
        default_grid = _generate_synthetic_grid("continents", {"amplitude": 3500.0})
        grids_by_id["default"] = default_grid
        textures_by_id["default"] = None

    return grids_by_id, textures_by_id


def _compute_displacer_scale(disp_cfg: DisplacerConfigModel, radius: float, grid: Optional[GeographicGrid] = None) -> float:
    """Computes the numeric displacement scale factor for a DisplacerConfigModel.

    Args:
        disp_cfg (DisplacerConfigModel): Displacer configuration.
        radius (float): Base globe radius in mm.
        grid (GeographicGrid, optional): Associated grid if applicable.

    Returns:
        float: Numeric scale factor.
    """
    if disp_cfg.scale_mode == "explicit":
        return float(disp_cfg.scale)
    if disp_cfg.scale_mode == "max_displacement_mm" and grid is not None:
        max_abs = float(np.nanmax(np.abs(grid.grid)))
        if max_abs > 1e-8:
            return float(disp_cfg.max_displacement_mm) / max_abs
        return 1.0
    # Default: 'auto_exagg' using unit-aware calculate_displacement_scale
    unit = disp_cfg.data_unit if disp_cfg.data_unit in ("m", "km", "cm", "mm", "ft") else "m"
    base_scale = calculate_displacement_scale(radius, grid_units=unit)
    return float(base_scale * disp_cfg.vert_exagg)


def resolve_shapefile_path(shp: Optional[str], default_type: str = "land") -> Optional[str]:
    """Resolves a shapefile identifier, filename, or relative path to an absolute path."""
    val = str(shp).strip() if shp else ""
    if not val or val.lower() in ("default", "builtin", "land", "natural_earth_land", "ne_110m_land"):
        if default_type == "coastline" or "coast" in val.lower():
            return datasets.shapefiles.coastline()
        return datasets.shapefiles.land()
    if val.lower() in ("coastline", "coastlines", "ne_110m_coastline"):
        return datasets.shapefiles.coastline()
    if os.path.isfile(val):
        return os.path.abspath(val)
    from .dataset_service import REPO_ROOT
    for root_dir in (REPO_ROOT, datasets._get_cache_dir(), os.path.join(datasets._get_cache_dir(), "uploads")):
        cand = os.path.join(root_dir, val)
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    return datasets.shapefiles.coastline() if default_type == "coastline" else datasets.shapefiles.land()


def resolve_image_path(img_path: Optional[str]) -> Optional[str]:
    """Resolves an image path, filename, or cache upload to an absolute path."""
    if not img_path or not str(img_path).strip():
        return None
    val = str(img_path).strip()
    if os.path.isfile(val):
        return os.path.abspath(val)
    from .dataset_service import REPO_ROOT
    for root_dir in (
        REPO_ROOT,
        os.path.join(REPO_ROOT, "context", "height_maps"),
        os.path.join(REPO_ROOT, "outputs"),
        datasets._get_cache_dir(),
        os.path.join(datasets._get_cache_dir(), "uploads"),
    ):
        cand = os.path.join(root_dir, val)
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    return None


def _apply_displacers(
    target_proxy,
    displacers: List[DisplacerConfigModel],
    grids_by_id: Dict[str, GeographicGrid],
    radius: float,
):
    """Applies a list of declarative displacer layers to a shell proxy (model.outer or model.inner)."""
    first_grid = next(iter(grids_by_id.values()))
    for d_cfg in displacers:
        if not d_cfg.enabled:
            continue
        dtype = d_cfg.type
        if dtype == "GridDisplacer":
            g = grids_by_id.get(d_cfg.grid_id or "", first_grid)
            scale = _compute_displacer_scale(d_cfg, radius, g)
            raw_coast = float(d_cfg.coastline_step)
            # In the UI & presets, custom GridDisplacer coastline_step <= 20 is specified in model mm
            # (e.g. 0.8 mm), whereas GridDisplacer adds coastline_step to grid values before multiplying by scale.
            if 0.0 < abs(raw_coast) <= 20.0 and 1e-9 < abs(scale) < 0.05:
                eff_coast_step = raw_coast / scale
            else:
                eff_coast_step = raw_coast
            disp = GridDisplacer(
                g,
                reference_level=float(d_cfg.reference_level),
                coastline_step=eff_coast_step,
                step_threshold=float(d_cfg.step_threshold),
            )
            target_proxy.displace(disp, scale=scale)
        elif dtype == "ConstantDisplacer":
            disp_val = float(d_cfg.displacement if d_cfg.displacement is not None else d_cfg.value)
            eff_scale = float(d_cfg.scale) if (d_cfg.scale_mode in ("explicit", "direct") and abs(d_cfg.scale) >= 0.001) else 1.0
            disp = ConstantDisplacer(disp_val)
            target_proxy.displace(disp, scale=eff_scale)
        elif dtype == "PointDisplacer":
            pts_src = resolve_shapefile_path(d_cfg.shapefile, default_type="land") if d_cfg.shapefile else d_cfg.points
            if pts_src:
                disp_val = float(d_cfg.displacement if d_cfg.displacement is not None else d_cfg.height)
                eff_scale = float(d_cfg.scale) if (d_cfg.scale_mode in ("explicit", "direct") and abs(d_cfg.scale) >= 0.001) else 1.0
                disp = PointDisplacer(
                    pts_src,
                    displacement=disp_val,
                    radius_degrees=float(d_cfg.radius_deg),
                )
                target_proxy.displace(disp, scale=eff_scale)
        elif dtype == "LineDisplacer":
            shp = resolve_shapefile_path(d_cfg.shapefile, default_type="coastline")
            if shp and os.path.exists(shp):
                disp_val = float(d_cfg.displacement if d_cfg.displacement is not None else d_cfg.height)
                eff_scale = float(d_cfg.scale) if (d_cfg.scale_mode in ("explicit", "direct") and abs(d_cfg.scale) >= 0.001) else 1.0
                disp = LineDisplacer(
                    shp,
                    displacement=disp_val,
                    width_degrees=float(d_cfg.width_deg),
                )
                target_proxy.displace(disp, scale=eff_scale)
        elif dtype == "PolygonDisplacer":
            shp = resolve_shapefile_path(d_cfg.shapefile, default_type="land")
            if shp and os.path.exists(shp):
                disp_val = float(d_cfg.displacement if d_cfg.displacement is not None else d_cfg.height)
                eff_inside = bool(d_cfg.displace_inside if hasattr(d_cfg, "displace_inside") and d_cfg.displace_inside is not None else True)
                eff_scale = float(d_cfg.scale) if (d_cfg.scale_mode in ("explicit", "direct") and abs(d_cfg.scale) >= 0.001) else 1.0
                disp = PolygonDisplacer(
                    shp,
                    displacement=disp_val,
                    displace_inside=eff_inside,
                )
                target_proxy.displace(disp, scale=eff_scale)


def _resolve_band_colors(project: GlobeProject, raw_colors: List[Any]) -> List[Tuple[int, int, int]]:
    """Resolves color strings or bracketed filament codes ('[01]', '#RRGGBB') into RGB tuples."""
    palette_resp = generate_palette_response(project.filaments)
    by_code = {e["code"]: tuple(e["rgb"]) for e in palette_resp["entries"]}
    resolved = []
    for c in raw_colors:
        if isinstance(c, str) and c.strip() in by_code:
            resolved.append(by_code[c.strip()])
        else:
            try:
                resolved.append(parse_color(c))
            except Exception:
                resolved.append((128, 128, 128))
    return resolved


def _apply_colourers(
    model: GlobeModel,
    project: GlobeProject,
    grids_by_id: Dict[str, GeographicGrid],
    textures_by_id: Dict[str, Optional[str]],
):
    """Applies all enabled declarative colourer layers to a GlobeModel."""
    first_grid = next(iter(grids_by_id.values()))
    first_tex = next(iter(textures_by_id.values()))

    for c_cfg in project.colourers:
        if not c_cfg.enabled:
            continue
        ctype = c_cfg.type
        target = c_cfg.target if c_cfg.target in ("outer", "inner", "all") else "outer"
        if target == "inner" and model.inner_vertices is None:
            continue
        selection = None if c_cfg.selection == "all" else c_cfg.selection

        colourer_obj = None
        if ctype == "GridColourer":
            g = grids_by_id.get(c_cfg.grid_id or "", first_grid)
            if c_cfg.use_banded_levels and c_cfg.colors and c_cfg.levels:
                rgb_list = _resolve_band_colors(project, c_cfg.colors)
                if len(c_cfg.levels) == len(rgb_list) - 1 or len(c_cfg.levels) == len(rgb_list) + 1:
                    cmap_obj, norm_obj = create_banded_colormap(rgb_list, c_cfg.levels)
                    colourer_obj = GridColourer(g, colormap=cmap_obj, norm=norm_obj)
            if colourer_obj is None:
                vmin = c_cfg.vmin
                vmax = c_cfg.vmax
                if c_cfg.symmetric and vmin is None and vmax is None:
                    abs_max = float(np.nanmax(np.abs(g.grid)))
                    vmin, vmax = -abs_max, abs_max
                colourer_obj = GridColourer(g, colormap=c_cfg.cmap or "terrain", vmin=vmin, vmax=vmax)

        elif ctype == "ImageColourer":
            img_path = resolve_image_path(c_cfg.image_path)
            if not img_path:
                img_path = textures_by_id.get(c_cfg.grid_id or "", first_tex)
            if img_path and os.path.exists(img_path):
                img = Image.open(img_path).convert("RGBA")
            else:
                # Render a fallback equirectangular texture from the primary grid
                cmap_rgb = apply_banded_colormap(
                    first_grid,
                    [(18, 52, 120), (110, 190, 205), (45, 95, 50), (142, 68, 28), (250, 250, 250)],
                    [-2500.0, 0.0, 500.0, 1500.0],
                )
                img = Image.fromarray(cmap_rgb).convert("RGBA")

            for prep in c_cfg.preprocessors:
                if prep.op in ("undo_hillshading",):
                    img = undo_hillshading(img, strength=float(prep.detail_Suppression))
                elif prep.op in ("simplify_image_median", "median_filter"):
                    img = simplify_image_median(img, size=max(3, int(prep.kernel_size)))
                elif prep.op in ("simplify_image_bilateral", "bilateral_filter"):
                    img = simplify_image_bilateral(img)
                elif prep.op in ("simplify_colors", "quantize_colors"):
                    palette_resp = generate_palette_response(project.filaments)
                    pal_colors = [tuple(e["rgb"]) for e in palette_resp["entries"][: max(2, int(prep.n_colors))]]
                    img = simplify_colors(img, pal_colors)
                elif prep.op in ("add_svg_symbol_spherical", "add_svg_symbol"):
                    img = add_svg_symbol_spherical(
                        img,
                        lat=float(prep.lat),
                        lon=float(prep.lon),
                        svg_source=prep.svg_path or "star",
                        size_degrees=float(prep.size_deg),
                        color=prep.color or "red",
                        rotation_degrees=float(prep.rotation_deg),
                    )
                elif prep.op in ("add_pole_markers",):
                    img = add_pole_markers(img, size_degrees=float(prep.pole_size_deg))

            colourer_obj = ImageColourer(image=img)

        elif ctype == "ConstantColourer":
            rgb = parse_color(c_cfg.color)
            colourer_obj = ConstantColourer((rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0))

        elif ctype == "PointColourer":
            pts_src = resolve_shapefile_path(c_cfg.shapefile, default_type="land") if c_cfg.shapefile else c_cfg.points
            if pts_src:
                rgb = parse_color(c_cfg.color)
                colourer_obj = PointColourer(
                    pts_src,
                    color=(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0),
                    radius_degrees=float(c_cfg.radius_deg),
                )

        elif ctype == "LineColourer":
            shp = resolve_shapefile_path(c_cfg.shapefile, default_type="coastline")
            if shp and os.path.exists(shp):
                rgb = parse_color(c_cfg.color)
                colourer_obj = LineColourer(
                    shp,
                    color=(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0),
                    width_degrees=float(c_cfg.width_deg),
                )

        elif ctype == "PolygonColourer":
            shp = resolve_shapefile_path(c_cfg.shapefile, default_type="land")
            if shp and os.path.exists(shp):
                rgb = parse_color(c_cfg.color)
                fg_rgb = (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
                bg_tuple = None
                if c_cfg.background_color:
                    bg_rgb = parse_color(c_cfg.background_color)
                    bg_tuple = (bg_rgb[0] / 255.0, bg_rgb[1] / 255.0, bg_rgb[2] / 255.0)
                colourer_obj = PolygonColourer(
                    shp,
                    color=fg_rgb,
                    background_color=bg_tuple,
                    flood_inside=bool(c_cfg.flood_inside),
                )

        elif ctype == "SymbolColourer":
            colourer_obj = SymbolColourer(
                symbol=c_cfg.symbol or "star",
                lat=float(c_cfg.lat),
                lon=float(c_cfg.lon),
                radius_degrees=float(c_cfg.size_deg),
                color=c_cfg.color or "red",
                rotation_degrees=float(c_cfg.rotation_deg),
            )

        elif ctype == "PoleLabelColourer":
            colourer_obj = PoleLabelColourer(
                radius_degrees=float(c_cfg.size_deg),
                north_color=c_cfg.color if c_cfg.mark_north else None,
                south_color=c_cfg.color if c_cfg.mark_south else None,
                north_symbol=c_cfg.north_text or "N",
                south_symbol=c_cfg.south_text or "S",
            )

        elif ctype == "TextColourer":
            colourer_obj = TextColourer(
                text=c_cfg.text or "EARTH",
                lat=float(c_cfg.lat),
                lon=float(c_cfg.lon),
                height_degrees=float(c_cfg.size_deg),
                angle=float(c_cfg.rotation_deg),
                color=c_cfg.color or "white",
                font=c_cfg.font_path,
            )

        if colourer_obj is not None:
            model.colour(colourer_obj, target=target, selection=selection)


def compile_globe_model(project: GlobeProject, n_points_override: Optional[int] = None) -> GlobeModel:
    """Compiles a GlobeProject into an authoritative globe3d.GlobeModel instance.

    Supports both 'paleo' Simple Paleo Mode and 'custom' multi-layer Recipe Mode.

    Args:
        project (GlobeProject): Project configuration.
        n_points_override (int, optional): Optional override for outer vertex count
            (e.g. for fast preview evaluation). Defaults to None.

    Returns:
        GlobeModel: Fully displaced and coloured GlobeModel.
    """
    geom = project.geometry
    n_pts = int(n_points_override if n_points_override is not None else geom.n_points)
    n_pts = max(100, n_pts)

    if project.mode == "paleo" or project.paleo_config.enabled:
        pc = project.paleo_config
        tracked = [
            {
                "name": loc.name,
                "lat": loc.lat,
                "lon": loc.lon,
                "color": loc.color,
                "size": pc.location_marker_size_deg,
            }
            for loc in pc.tracked_locations
        ]

        custom_texture = None
        if pc.color_mode == "banded_4filament":
            try:
                grid, _, _ = datasets.paleo.scotese(
                    age=pc.age,
                    name=pc.name,
                    resolution=pc.resolution,
                    data_dir=pc.data_dir,
                )
            except Exception:
                grid = _generate_synthetic_grid("continents", {"amplitude": 3500.0})

            palette_resp = generate_palette_response(project.filaments)
            by_code = {e["code"]: tuple(e["rgb"]) for e in palette_resp["entries"]}
            bands = pc.band_thresholds
            colors = []
            thresholds = []
            for i, b in enumerate(bands):
                if b.color:
                    colors.append(parse_color(b.color))
                else:
                    colors.append(by_code.get(b.code, (128, 128, 128)))
                if i < len(bands) - 1:
                    thresholds.append(float(b.threshold))
            if len(colors) >= 2 and len(thresholds) == len(colors) - 1:
                custom_texture = apply_banded_colormap(grid, colors, thresholds)

        try:
            model = GlobeModel.from_paleo(
                age=pc.age,
                radius=geom.radius,
                n_points=n_pts,
                hollow=geom.hollow,
                inner_ratio=geom.inner_ratio,
                vert_exagg=pc.vert_exagg,
                coastline_step=pc.coastline_step,
                mark_poles=pc.mark_poles,
                tracked_locations=tracked,
                data_dir=pc.data_dir,
                method=geom.distribution,
                texture=custom_texture,
            )
        except Exception:
            # Fallback if offline and Scotese files aren't cached yet
            model = GlobeModel(
                method=geom.distribution,
                n_points=n_pts,
                radius=geom.radius,
                hollow=geom.hollow,
                inner_ratio=geom.inner_ratio,
            )
            grid = _generate_synthetic_grid("continents", {"amplitude": 3500.0})
            scale = calculate_displacement_scale(geom.radius, grid_units="m") * pc.vert_exagg
            model.outer.displace(GridDisplacer(grid, coastline_step=pc.coastline_step), scale=scale)
            model.outer.colour(GridColourer(grid, colormap=pc.cmap or "terrain"))
            if pc.mark_poles:
                model.outer.colour(PoleLabelColourer(radius_degrees=pc.pole_label_size_deg))

    else:
        inner_n = geom.inner_n_points
        if inner_n is not None and n_points_override is not None:
            inner_n = min(inner_n, n_pts)

        model = GlobeModel(
            method=geom.distribution,
            n_points=n_pts,
            radius=geom.radius,
            center=tuple(geom.center[:3]) if len(geom.center) >= 3 else (0.0, 0.0, 0.0),
            hollow=geom.hollow and geom.create_inner_mesh_from_outer_thickness is None,
            inner_ratio=geom.inner_ratio,
            inner_n_points=inner_n,
        )

        grids_by_id, textures_by_id = resolve_project_grids(project)

        # Apply outer displacements
        _apply_displacers(model.outer, project.outer_displacements, grids_by_id, geom.radius)

        # Create inner mesh from displaced outer mesh if requested
        if geom.hollow and geom.create_inner_mesh_from_outer_thickness is not None:
            model.create_inner_mesh(float(geom.create_inner_mesh_from_outer_thickness))

        # Apply inner displacements
        if model.inner_vertices is not None and project.inner_displacements:
            _apply_displacers(
                model.inner,
                project.inner_displacements,
                grids_by_id,
                geom.radius * geom.inner_ratio,
            )

        # Apply colourers
        _apply_colourers(model, project, grids_by_id, textures_by_id)

        # Ensure default colors exist if no colourer was enabled
        if model.outer_colors is None:
            first_grid = next(iter(grids_by_id.values()))
            model.outer.colour(GridColourer(first_grid, colormap="terrain"))

    if model.inner_vertices is not None and model.inner_colors is None:
        model.inner_colors = np.ones((len(model.inner_vertices), 3), dtype=np.float64)

    # Fix shell intersections if configured
    if geom.hollow and model.inner_vertices is not None and geom.fix_intersection.enabled:
        model.fix_intersection(
            min_thickness=float(geom.fix_intersection.min_thickness),
            mode=geom.fix_intersection.mode,
        )

    # Configure magnets if enabled
    mag = project.magnets
    if mag.enabled:
        strategy = "equally_spaced"
        position_arg: Any = "auto" if mag.Optimize_positions else (mag.manual_angles or mag.count)
        model.configure_magnets(
            diameter=float(mag.diameter),
            height=float(mag.height),
            n_magnets=int(mag.count),
            position=position_arg,
            horizontal_tolerance=float(mag.clearance),
            vertical_tolerance=float(mag.clearance),
            min_thickness=float(mag.min_margin),
            allow_bosses=float(mag.boss_thickness) > 0,
            placement_strategy=strategy,
        )

    return model


def export_project_model(project: GlobeProject, repo_root: str) -> Dict[str, Any]:
    """Compiles the full-resolution Python GlobeModel and exports to .3mf, .obj, or .stl.

    Args:
        project (GlobeProject): Project configuration.
        repo_root (str): Path to the repository root for resolving relative output directories.

    Returns:
        dict: Export summary with saved file paths, sizes, download URLs, and mesh stats.
    """
    model = compile_globe_model(project)
    exp = project.export

    out_dir = exp.output_dir or "outputs"
    if not os.path.isabs(out_dir):
        out_dir = os.path.join(repo_root, out_dir)
    os.makedirs(out_dir, exist_ok=True)

    ext = f".{exp.format.lower().lstrip('.')}"
    prefix = (exp.filename_prefix or "globe_model").strip()

    base_filaments = get_spools_from_config(project.filaments) if project.filaments.enabled else None
    palette_entries = (
        generate_palette_response(project.filaments)["entries"] if project.filaments.enabled else None
    )

    exported_paths: List[str] = []

    if exp.split_hemispheres:
        if ext == ".3mf" and not exp.dual_files:
            out_path = os.path.join(out_dir, f"{prefix}_hemispheres{ext}")
            model.export_hemispheres(
                top_filename=out_path,
                bottom_filename=None,
                hollow=project.geometry.hollow,
                base_filaments=base_filaments,
                palette=palette_entries,
            )
            exported_paths.append(out_path)
        else:
            top_path = os.path.join(out_dir, f"{prefix}_north{ext}")
            bot_path = os.path.join(out_dir, f"{prefix}_south{ext}")
            model.export_hemispheres(
                top_filename=top_path,
                bottom_filename=bot_path,
                hollow=project.geometry.hollow,
                base_filaments=base_filaments,
                palette=palette_entries,
            )
            exported_paths.extend([top_path, bot_path])
    else:
        part = "combined" if (project.geometry.hollow and model.inner_vertices is not None) else "outer"
        out_path = os.path.join(out_dir, f"{prefix}{ext}")
        model.export(
            filename=out_path,
            part=part,
            include_color=True,
            base_filaments=base_filaments,
            palette=palette_entries,
            object_name=prefix,
        )
        exported_paths.append(out_path)

    files_info = []
    for p in exported_paths:
        abs_p = os.path.abspath(p)
        size_b = os.path.getsize(abs_p) if os.path.exists(abs_p) else 0
        files_info.append({
            "filename": os.path.basename(abs_p),
            "saved_path": abs_p,
            "size_bytes": size_b,
            "download_url": f"/api/exports/download?path={abs_p}",
        })

    r_outer = np.linalg.norm(model.outer_vertices, axis=1)
    r_inner = (
        np.linalg.norm(model.inner_vertices, axis=1)
        if model.inner_vertices is not None
        else np.zeros(1)
    )
    return {
        "files": files_info,
        "stats": {
            "vertex_count": int(
                len(model.outer_vertices)
                + (len(model.inner_vertices) if model.inner_vertices is not None else 0)
            ),
            "face_count": int(
                len(model.outer_faces)
                + (len(model.inner_faces) if model.inner_faces is not None else 0)
            ),
            "min_radius": round(float(np.min(r_outer)), 3),
            "max_radius": round(float(np.max(r_outer)), 3),
            "min_inner_radius": round(float(np.min(r_inner)), 3) if model.inner_vertices is not None else None,
        },
    }
