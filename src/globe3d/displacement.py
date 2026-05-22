import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import RegularGridInterpolator
from tqdm import tqdm


def _wrap_longitude(lats, lons, grid):
    """Pads the longitude array and grid for periodic boundary conditions.

    Ensures that the longitude axis extends beyond both -180° and +180° by copying
    data from the opposite edge, allowing RegularGridInterpolator to return valid
    values at every longitude in [-180, 180]. It also repairs NaN edge columns.

    Args:
        lats (numpy.ndarray): 1D array of latitude coordinates.
        lons (numpy.ndarray): 1D array of longitude coordinates.
        grid (numpy.ndarray): 2D array of grid values.

    Returns:
        tuple: (lats, padded_lons, padded_grid).
    """
    if len(lons) < 2:
        return lats, lons, grid

    lons = np.asarray(lons, dtype=np.float64)
    grid = np.array(grid, copy=True)
    step = abs(lons[1] - lons[0])

    first_all_nan = np.all(np.isnan(grid[:, 0]))
    last_all_nan = np.all(np.isnan(grid[:, -1]))
    if first_all_nan and not last_all_nan:
        grid[:, 0] = grid[:, -1]
    elif last_all_nan and not first_all_nan:
        grid[:, -1] = grid[:, 0]

    new_lons = list(lons)
    grid_parts = [grid]
    padded = False

    if lons[-1] <= 180.0:
        new_lons.append(lons[-1] + step)
        grid_parts.append(grid[:, 1:2])
        padded = True

    if lons[0] >= -180.0:
        new_lons.insert(0, lons[0] - step)
        grid_parts.insert(0, grid[:, -2:-1])
        padded = True

    if padded:
        new_lons = np.array(new_lons)
        new_grid = np.concatenate(grid_parts, axis=1)
        return lats, new_lons, new_grid

    return lats, lons, grid


def calculate_displacement_scale(model_radius_mm, earth_radius_km=6371.0, vertical_exagg=1.0):
    """Calculates the displacement scale factor for a given model globe radius.

    Args:
        model_radius_mm (float): Desired radius of the un-displaced globe in millimeters.
        earth_radius_km (float, optional): Real-world earth radius in kilometers. Defaults to 6371.0.
        vertical_exagg (float, optional): Vertical exaggeration factor. Defaults to 1.0.

    Returns:
        float: The scale factor to use in `displace_vertices`.
    """
    earth_radius_m = earth_radius_km * 1000.0
    return (model_radius_mm / earth_radius_m) * vertical_exagg


def cartesian_to_spherical(vertices):
    """Converts Cartesian (x, y, z) coordinates to spherical (r, latitude, longitude) in degrees.

    Args:
        vertices (numpy.ndarray): (n_points, 3) vertex coordinates or a single (3,) vertex coordinate.

    Returns:
        tuple: A tuple containing:
            - r (numpy.ndarray or float): Radial distance from the origin.
            - lats (numpy.ndarray or float): Latitudes in degrees [-90, 90].
            - lons (numpy.ndarray or float): Longitudes in degrees [-180, 180].
    """
    vertices = np.asarray(vertices, dtype=np.float64)
    is_1d = vertices.ndim == 1
    if is_1d:
        vertices = vertices[None, :]

    r = np.linalg.norm(vertices, axis=1)
    r_safe = np.where(r == 0.0, 1.0, r)
    lats = np.degrees(np.arcsin(vertices[:, 2] / r_safe))
    lons = np.degrees(np.arctan2(vertices[:, 1], vertices[:, 0]))

    if is_1d:
        return r[0], lats[0], lons[0]
    return r, lats, lons


def displace_vertices(
    vertices, lats, lons, grid, scale,
    show_progress=False, chunk_size=10000,
    interp_method='linear', num_threads=-1
):
    """Displaces vertices radially based on interpolated values from a geographic grid.

    Converts (x, y, z) coordinates to spherical coordinates (lat, lon), interpolates
    the displacement value from the grid, and scales the radius accordingly.

    Args:
        vertices (numpy.ndarray): (n_points, 3) vertex coordinates.
        lats (numpy.ndarray): 1D array of grid latitudes.
        lons (numpy.ndarray): 1D array of grid longitudes.
        grid (numpy.ndarray): 2D grid of values.
        scale (float): Displacement scale factor.
        show_progress (bool, optional): Whether to display a progress bar. Defaults to False.
        chunk_size (int, optional): Chunk size for progress tracking. Defaults to 10000.
        interp_method (str, optional): Interpolation method ('linear' or 'nearest'). Defaults to 'linear'.
        num_threads (int, optional): Number of parallel threads. Defaults to -1 (all available).

    Returns:
        numpy.ndarray: Displaced vertex coordinates.

    Raises:
        ValueError: If a vertex is displaced deeper than the origin (new radius <= 0).
    """
    import os
    from concurrent.futures import ThreadPoolExecutor, as_completed

    lats, lons, grid = _wrap_longitude(lats, lons, grid)

    interpolator = RegularGridInterpolator((lats, lons), grid, bounds_error=False, fill_value=None, method=interp_method)
    n = vertices.shape[0]
    new_vertices = np.empty_like(vertices)

    if num_threads == -1:
        num_threads = os.cpu_count() or 1
    elif num_threads <= 0:
        num_threads = 1

    def process_chunk(start_idx):
        end_idx = min(start_idx + chunk_size, n)
        chunk = vertices[start_idx:end_idx]
        r, lat, lon = cartesian_to_spherical(chunk)
        pts = np.stack((lat, lon), axis=-1)
        displacement = interpolator(pts)
        displacement = np.nan_to_num(displacement)
        new_r = r + scale * displacement
        if np.any(new_r <= 0):
            raise ValueError(
                "Vertex displacement translates point(s) deeper than the origin (new radius <= 0)."
            )
        r_safe = np.where(r == 0.0, 1.0, r)
        chunk_displaced = (chunk / r_safe[:, None]) * new_r[:, None]
        return start_idx, end_idx, chunk_displaced

    chunk_starts = list(range(0, n, chunk_size))

    if num_threads > 1 and len(chunk_starts) > 1:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(process_chunk, start) for start in chunk_starts]
            if show_progress:
                for fut in tqdm(as_completed(futures), total=len(futures), desc="Displacing vertices (parallel)"):
                    start, end, result = fut.result()
                    new_vertices[start:end] = result
            else:
                for fut in futures:
                    start, end, result = fut.result()
                    new_vertices[start:end] = result
    else:
        if show_progress and n > chunk_size:
            for start in tqdm(chunk_starts, desc="Displacing vertices"):
                _, _, result = process_chunk(start)
                new_vertices[start:start+chunk_size] = result
        else:
            r, lat, lon = cartesian_to_spherical(vertices)
            pts = np.stack((lat, lon), axis=-1)
            displacement = interpolator(pts)
            displacement = np.nan_to_num(displacement)
            new_r = r + scale * displacement
            if np.any(new_r <= 0):
                raise ValueError(
                    "Vertex displacement translates point(s) deeper than the origin (new radius <= 0)."
                )
            r_safe = np.where(r == 0.0, 1.0, r)
            new_vertices = (vertices / r_safe[:, None]) * new_r[:, None]

    return new_vertices


def assign_vertex_colors(
    vertices, lats, lons, grid, colormap='viridis', norm=None,
    vmin=None, vmax=None, show_progress=False, chunk_size=10000,
    interp_method='linear', num_threads=-1
):
    """Assigns RGB colors to vertices based on values interpolated from a geographic grid.

    Maps normalized grid values to colors using a Matplotlib colormap.

    Args:
        vertices (numpy.ndarray): (n_points, 3) vertex coordinates.
        lats (numpy.ndarray): 1D array of grid latitudes.
        lons (numpy.ndarray): 1D array of grid longitudes.
        grid (numpy.ndarray): 2D grid of values.
        colormap (str or Colormap, optional): Matplotlib colormap name or object. Defaults to 'viridis'.
        norm (callable or Normalize, optional): Normalization object/function.
        vmin (float, optional): Min value for linear normalization.
        vmax (float, optional): Max value for linear normalization.
        show_progress (bool, optional): Whether to display a progress bar. Defaults to False.
        chunk_size (int, optional): Chunk size for progress tracking. Defaults to 10000.
        interp_method (str, optional): Interpolation method. Defaults to 'linear'.
        num_threads (int, optional): Number of parallel threads. Defaults to -1 (all available).

    Returns:
        numpy.ndarray: (n_points, 3) array of RGB colors in [0, 1].
    """
    import os
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if isinstance(colormap, str):
        cmap = plt.get_cmap(colormap)
    else:
        cmap = colormap

    if norm is None:
        if vmin is None:
            vmin = np.nanmin(grid)
        if vmax is None:
            vmax = np.nanmax(grid)

        def normalize(val):
            return (val - vmin) / (vmax - vmin)
        norm = normalize

    lats, lons, grid = _wrap_longitude(lats, lons, grid)
    interpolator = RegularGridInterpolator((lats, lons), grid, bounds_error=False, fill_value=None, method=interp_method)

    n = vertices.shape[0]
    colors = np.empty((n, 3), dtype=np.float64)

    if num_threads == -1:
        num_threads = os.cpu_count() or 1
    elif num_threads <= 0:
        num_threads = 1

    def process_chunk(start_idx):
        end_idx = min(start_idx + chunk_size, n)
        chunk = vertices[start_idx:end_idx]
        _, lat, lon = cartesian_to_spherical(chunk)
        pts = np.stack((lat, lon), axis=-1)
        values = interpolator(pts)
        values = np.nan_to_num(values)
        norm_vals = norm(values)
        chunk_colors = cmap(norm_vals)[:, :3]
        return start_idx, end_idx, chunk_colors

    chunk_starts = list(range(0, n, chunk_size))

    if num_threads > 1 and len(chunk_starts) > 1:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(process_chunk, start) for start in chunk_starts]
            if show_progress:
                for fut in tqdm(as_completed(futures), total=len(futures), desc="Assigning colors (parallel)"):
                    start, end, result = fut.result()
                    colors[start:end] = result
            else:
                for fut in futures:
                    start, end, result = fut.result()
                    colors[start:end] = result
    else:
        if show_progress and n > chunk_size:
            for start in tqdm(chunk_starts, desc="Assigning colors"):
                _, _, result = process_chunk(start)
                colors[start:start+chunk_size] = result
        else:
            _, lat, lon = cartesian_to_spherical(vertices)
            pts = np.stack((lat, lon), axis=-1)
            values = interpolator(pts)
            values = np.nan_to_num(values)
            norm_vals = norm(values)
            colors = cmap(norm_vals)[:, :3]
    return colors


def assign_vertex_colors_image(vertices, image_path, show_progress=False, chunk_size=10000, num_threads=-1):
    """Assigns RGB colors to vertices by sampling from an equirectangular image.

    Args:
        vertices (numpy.ndarray): (n_points, 3) vertex coordinates.
        image_path (str): File path to the image.
        show_progress (bool, optional): Whether to display a progress bar. Defaults to False.
        chunk_size (int, optional): Chunk size for progress tracking. Defaults to 10000.
        num_threads (int, optional): Number of parallel threads. Defaults to -1.

    Returns:
        numpy.ndarray: (n_points, 3) RGB colors in [0, 1].
    """
    import os
    from concurrent.futures import ThreadPoolExecutor, as_completed

    img = plt.imread(image_path)

    if img.dtype == np.uint8:
        img = img.astype(np.float64) / 255.0

    if img.ndim == 2:
        img = np.stack((img,)*3, axis=-1)
    elif img.shape[2] > 3:
        img = img[:, :, :3]

    height, width, _ = img.shape

    n = vertices.shape[0]
    colors = np.empty((n, 3), dtype=np.float64)

    def get_colors_from_chunk(chunk):
        _, lat, lon = cartesian_to_spherical(chunk)

        v = (90 - lat) / 180.0 * (height - 1)
        u = (lon + 180) / 360.0 * (width - 1)

        v_idx = np.clip(np.round(v).astype(int), 0, height - 1)
        u_idx = np.clip(np.round(u).astype(int), 0, width - 1)

        return img[v_idx, u_idx]

    if num_threads == -1:
        num_threads = os.cpu_count() or 1
    elif num_threads <= 0:
        num_threads = 1

    def process_chunk(start_idx):
        end_idx = min(start_idx + chunk_size, n)
        chunk = vertices[start_idx:end_idx]
        chunk_colors = get_colors_from_chunk(chunk)
        return start_idx, end_idx, chunk_colors

    chunk_starts = list(range(0, n, chunk_size))

    if num_threads > 1 and len(chunk_starts) > 1:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(process_chunk, start) for start in chunk_starts]
            if show_progress:
                for fut in tqdm(as_completed(futures), total=len(futures), desc="Assigning image colors (parallel)"):
                    start, end, result = fut.result()
                    colors[start:end] = result
            else:
                for fut in futures:
                    start, end, result = fut.result()
                    colors[start:end] = result
    else:
        if show_progress and n > chunk_size:
            for start in tqdm(chunk_starts, desc="Assigning image colors"):
                _, _, result = process_chunk(start)
                colors[start:start+chunk_size] = result
        else:
            colors = get_colors_from_chunk(vertices)

    return colors


def _parallel_sjoin(points_gdf, gdf, num_threads=-1):
    """Performs a spatial join in parallel by chunking the points GeoDataFrame.

    Args:
        points_gdf (geopandas.GeoDataFrame): GeoDataFrame containing point geometries.
        gdf (geopandas.GeoDataFrame): GeoDataFrame to join with.
        num_threads (int, optional): Number of parallel threads. Defaults to -1.

    Returns:
        pandas.DataFrame: Concatenated spatial join results.
    """
    import os
    import pandas as pd
    import geopandas as gpd
    from concurrent.futures import ThreadPoolExecutor

    if num_threads == -1:
        num_threads = os.cpu_count() or 1
    elif num_threads <= 0:
        num_threads = 1

    num_points = len(points_gdf)
    if num_threads <= 1 or num_points < 10000:
        return gpd.sjoin(points_gdf, gdf, predicate='intersects', how='left')

    chunk_size = (num_points + num_threads - 1) // num_threads

    def run_sjoin(chunk_start):
        chunk_end = min(chunk_start + chunk_size, num_points)
        chunk_gdf = points_gdf.iloc[chunk_start:chunk_end]
        return gpd.sjoin(chunk_gdf, gdf, predicate='intersects', how='left')

    chunk_starts = list(range(0, num_points, chunk_size))
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        results = list(executor.map(run_sjoin, chunk_starts))

    return pd.concat(results)


def _find_points_inside_gdf(vertices, gdf, num_threads=-1):
    """Finds which vertices fall inside the geometries of a GeoDataFrame.

    Args:
        vertices (numpy.ndarray): (n_points, 3) vertex coordinates.
        gdf (geopandas.GeoDataFrame): GeoDataFrame of geometries to check against.
        num_threads (int, optional): Number of parallel threads. Defaults to -1.

    Returns:
        tuple: A tuple containing:
            - inside_mask (numpy.ndarray): Boolean mask of shape (n_points,).
            - r (numpy.ndarray): Radial distance from origin for each vertex.
    """
    import geopandas as gpd

    r, lats, lons = cartesian_to_spherical(vertices)

    points_gdf = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(lons, lats),
        crs=gdf.crs
    )

    joined = _parallel_sjoin(points_gdf, gdf, num_threads=num_threads)
    matched_indices = joined.index[joined['index_right'].notna()].unique()
    inside_mask = np.zeros(len(vertices), dtype=bool)
    inside_mask[matched_indices] = True

    return inside_mask, r


def displace_by_points(
    vertices: np.ndarray,
    points_data: object,
    displacement: float = 1.0,
    radius_degrees: float = 1.0,
    num_threads: int = -1,
) -> np.ndarray:
    """Displaces vertices radially based on proximity to Point/MultiPoint geometries.

    Args:
        vertices (numpy.ndarray): (n_points, 3) vertex coordinates in millimeters.
        points_data (str or array-like): Path to a shapefile or an (N, 2) array of (lon, lat).
        displacement (float, optional): Radial displacement in mm. Defaults to 1.0.
        radius_degrees (float, optional): Proximity threshold in degrees. Defaults to 1.0.
        num_threads (int, optional): Number of parallel threads. Defaults to -1.

    Returns:
        numpy.ndarray: Displaced vertex coordinates.

    Raises:
        TypeError: If shapefile contains non-Point geometries.
        ValueError: If inputs have invalid dimensions, shapes, or result in new radius <= 0.
    """
    import geopandas as gpd
    import warnings

    if isinstance(points_data, str):
        gdf = gpd.read_file(points_data)
        invalid_types = set(gdf.geometry.geom_type.unique()) - {"Point", "MultiPoint"}
        if invalid_types:
            raise TypeError(
                f"Geometries must be Points or MultiPoints. Found types: {invalid_types}"
            )
    else:
        pts = np.asarray(points_data)
        if pts.ndim != 2 or pts.shape[1] != 2:
            raise ValueError("points_data array must have shape (N, 2) representing (lon, lat).")
        gdf = gpd.GeoDataFrame(
            geometry=gpd.points_from_xy(pts[:, 0], pts[:, 1]),
            crs="EPSG:4326"
        )

    if radius_degrees < 0:
        raise ValueError("radius_degrees must be non-negative.")

    if radius_degrees > 0:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")
            gdf.geometry = gdf.geometry.buffer(radius_degrees)

    inside_mask, r = _find_points_inside_gdf(vertices, gdf, num_threads=num_threads)
    new_r = r + np.where(inside_mask, displacement, 0.0)

    if np.any(new_r <= 0):
        raise ValueError(
            "Vertex displacement translates point(s) deeper than the origin (new radius <= 0)."
        )

    r_safe = np.where(r == 0.0, 1.0, r)
    new_vertices = (vertices / r_safe[:, None]) * new_r[:, None]
    return new_vertices


def displace_near_lines(
    vertices: np.ndarray,
    shapefile_path: str,
    displacement: float = 1.0,
    width_degrees: float = 0.5,
    num_threads: int = -1,
) -> np.ndarray:
    """Displaces vertices radially based on proximity to line or polygon geometries.

    Args:
        vertices (numpy.ndarray): (n_points, 3) vertex coordinates in millimeters.
        shapefile_path (str): Path to the shapefile.
        displacement (float, optional): Radial displacement in mm. Defaults to 1.0.
        width_degrees (float, optional): Distance in degrees to buffer geometries. Defaults to 0.5.
        num_threads (int, optional): Number of parallel threads. Defaults to -1.

    Returns:
        numpy.ndarray: Displaced vertex coordinates.

    Raises:
        ValueError: If width_degrees is negative or if displacement results in new radius <= 0.
    """
    import geopandas as gpd
    import warnings

    gdf = gpd.read_file(shapefile_path)

    if width_degrees < 0:
        raise ValueError("width_degrees must be non-negative.")

    if width_degrees > 0:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")
            gdf.geometry = gdf.geometry.buffer(width_degrees)

    inside_mask, r = _find_points_inside_gdf(vertices, gdf, num_threads=num_threads)
    new_r = r + np.where(inside_mask, displacement, 0.0)

    if np.any(new_r <= 0):
        raise ValueError(
            "Vertex displacement translates point(s) deeper than the origin (new radius <= 0)."
        )

    r_safe = np.where(r == 0.0, 1.0, r)
    new_vertices = (vertices / r_safe[:, None]) * new_r[:, None]
    return new_vertices


def displace_by_polygons(
    vertices: np.ndarray,
    shapefile_path: str,
    displacement: float = 1.0,
    displace_inside: bool = True,
    num_threads: int = -1,
) -> np.ndarray:
    """Displaces vertices radially depending on whether they fall inside/outside closed polygons.

    Args:
        vertices (numpy.ndarray): (n_points, 3) vertex coordinates in millimeters.
        shapefile_path (str): Path to shapefile containing Polygon/MultiPolygon geometries.
        displacement (float, optional): Radial displacement in mm. Defaults to 1.0.
        displace_inside (bool, optional): If True, displace points inside polygons. If False,
            displace points outside. Defaults to True.
        num_threads (int, optional): Number of parallel threads. Defaults to -1.

    Returns:
        numpy.ndarray: Displaced vertex coordinates.

    Raises:
        TypeError: If shapefile contains geometries other than Polygon/MultiPolygon.
        ValueError: If displacement translates any point deeper than origin (new radius <= 0).
    """
    import geopandas as gpd

    gdf = gpd.read_file(shapefile_path)
    invalid_types = set(gdf.geometry.geom_type.unique()) - {"Polygon", "MultiPolygon"}
    if invalid_types:
        raise TypeError(
            f"Geometries must be Polygons or MultiPolygons. Found types: {invalid_types}"
        )

    inside_mask, r = _find_points_inside_gdf(vertices, gdf, num_threads=num_threads)

    if displace_inside:
        apply_mask = inside_mask
    else:
        apply_mask = ~inside_mask

    new_r = r + np.where(apply_mask, displacement, 0.0)

    if np.any(new_r <= 0):
        raise ValueError(
            "Vertex displacement translates point(s) deeper than the origin (new radius <= 0)."
        )

    r_safe = np.where(r == 0.0, 1.0, r)
    new_vertices = (vertices / r_safe[:, None]) * new_r[:, None]
    return new_vertices


def select_inward_facing(vertices, faces, **kwargs):
    """Selects vertices that form inward-facing faces.

    Args:
        vertices (numpy.ndarray): (N, 3) vertex coordinates.
        faces (numpy.ndarray): (F, 3) face-index array.
        **kwargs: Extra arguments, including 'center' (defaults to (0,0,0)).

    Returns:
        numpy.ndarray: 1D array of unique vertex indices.
    """
    if faces is None:
        raise ValueError("faces must be provided for selecting inward-facing vertices.")
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]

    normals = np.cross(v1 - v0, v2 - v0)
    center = np.asarray(kwargs.get('center', (0.0, 0.0, 0.0)), dtype=np.float64)
    centroids = (v0 + v1 + v2) / 3.0 - center

    dot_products = np.sum(normals * centroids, axis=1)
    inward_faces = faces[dot_products < 0]

    return np.unique(inward_faces)


def select_outward_facing(vertices, faces, **kwargs):
    """Selects vertices that form outward-facing faces.

    Args:
        vertices (numpy.ndarray): (N, 3) vertex coordinates.
        faces (numpy.ndarray): (F, 3) face-index array.
        **kwargs: Extra arguments, including 'center' (defaults to (0,0,0)).

    Returns:
        numpy.ndarray: 1D array of unique vertex indices.
    """
    if faces is None:
        raise ValueError("faces must be provided for selecting outward-facing vertices.")
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]

    normals = np.cross(v1 - v0, v2 - v0)
    center = np.asarray(kwargs.get('center', (0.0, 0.0, 0.0)), dtype=np.float64)
    centroids = (v0 + v1 + v2) / 3.0 - center

    dot_products = np.sum(normals * centroids, axis=1)
    outward_faces = faces[dot_products > 0]

    return np.unique(outward_faces)


def register_selection_function(name, func):
    """Registers a custom vertex selection function.

    Args:
        name (str): Name of the selection function.
        func (callable): The selection function.
    """
    SELECTION_REGISTRY[name] = func


SELECTION_REGISTRY = {
    'inward_facing': select_inward_facing,
    'outward_facing': select_outward_facing,
}


def modify_vertex_colors(
    vertices,
    colors,
    selection_function,
    faces=None,
    selection_function_kwargs=None,
    lats=None,
    lons=None,
    grid=None,
    colormap='viridis',
    norm=None,
    vmin=None,
    vmax=None,
    image_path=None,
    constant_color=None,
    show_progress=False,
    chunk_size=10000,
    interp_method='linear',
    num_threads=-1,
):
    """Modifies colors of a selected subset of vertices.

    Args:
        vertices (numpy.ndarray): (N, 3) vertex array.
        colors (numpy.ndarray): (N, 3) original RGB colors.
        selection_function (str or callable): registered name or callable selection function.
        faces (numpy.ndarray, optional): (F, 3) face-index array. Required for normal checks.
        selection_function_kwargs (dict, optional): Extra keyword arguments for the selection function.
        lats (numpy.ndarray, optional): 1D latitudes.
        lons (numpy.ndarray, optional): 1D longitudes.
        grid (numpy.ndarray, optional): 2D grid of values.
        colormap (str or Colormap, optional): Colormap to use. Defaults to 'viridis'.
        norm (Normalize, optional): Normalization object.
        vmin (float, optional): Min bounds for normalization.
        vmax (float, optional): Max bounds for normalization.
        image_path (str, optional): Image path for color mapping.
        constant_color (array-like, optional): Constant RGB in [0, 1].
        show_progress (bool, optional): Show progress. Defaults to False.
        chunk_size (int, optional): Chunk size for calculation. Defaults to 10000.
        interp_method (str, optional): Interpolation method. Defaults to 'linear'.
        num_threads (int, optional): Number of parallel threads. Defaults to -1.

    Returns:
        numpy.ndarray: (N, 3) modified RGB colors.
    """
    if isinstance(selection_function, str):
        if selection_function not in SELECTION_REGISTRY:
            raise ValueError(
                f"Selection function '{selection_function}' not found in registry. "
                f"Available functions: {list(SELECTION_REGISTRY.keys())}"
            )
        select_func = SELECTION_REGISTRY[selection_function]
    elif callable(selection_function):
        select_func = selection_function
    else:
        raise TypeError("selection_function must be a string or a callable.")

    kwargs = selection_function_kwargs or {}
    selected_indices = select_func(vertices, faces, **kwargs)

    if len(selected_indices) == 0:
        return colors.copy()

    if constant_color is not None:
        c_val = np.asarray(constant_color, dtype=np.float64)
        if c_val.shape != (3,):
            raise ValueError("constant_color must be a 3-element RGB array-like.")
        new_colors = np.tile(c_val, (len(selected_indices), 1))
    elif image_path is not None:
        new_colors = assign_vertex_colors_image(
            vertices=vertices[selected_indices],
            image_path=image_path,
            show_progress=show_progress,
            chunk_size=chunk_size,
            num_threads=num_threads,
        )
    elif grid is not None:
        new_colors = assign_vertex_colors(
            vertices=vertices[selected_indices],
            lats=lats,
            lons=lons,
            grid=grid,
            colormap=colormap,
            norm=norm,
            vmin=vmin,
            vmax=vmax,
            show_progress=show_progress,
            chunk_size=chunk_size,
            interp_method=interp_method,
            num_threads=num_threads,
        )
    else:
        raise ValueError(
            "Must provide one of constant_color, image_path, or grid parameters to recolor vertices."
        )

    modified_colors = colors.copy()
    modified_colors[selected_indices] = new_colors
    return modified_colors


modify_vertex_colours = modify_vertex_colors
