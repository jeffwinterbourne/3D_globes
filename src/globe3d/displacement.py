import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import RegularGridInterpolator
from tqdm import tqdm

def _wrap_longitude(lats, lons, grid):
    """
    Pad the longitude array and grid for periodic (dateline) boundary
    conditions so that ``RegularGridInterpolator`` returns valid values
    at every longitude in [-180, 180].

    The function always ensures that the longitude axis extends *beyond*
    both -180° and +180° by copying data from the opposite edge.  This
    handles grids that already span [-180, 180] (where the first and
    last columns represent the same meridian), grids that span
    [0, 360], and grids with arbitrary start/end longitudes.

    It also repairs NaN edge columns that arise when ±180° are the
    same meridian and only one side has data (common in GMT grids).
    """
    if len(lons) < 2:
        return lats, lons, grid

    lons = np.asarray(lons, dtype=np.float64)
    grid = np.array(grid, copy=True)  # avoid mutating caller's array
    step = abs(lons[1] - lons[0])

    # --- Repair NaN edge columns ----------------------------------------
    # Some grids store NaN at -180° because ±180° are physically the same
    # meridian and data is only stored at +180° (or vice-versa).  Fill
    # any fully-NaN edge column from the opposite edge before padding.
    first_all_nan = np.all(np.isnan(grid[:, 0]))
    last_all_nan = np.all(np.isnan(grid[:, -1]))
    if first_all_nan and not last_all_nan:
        grid[:, 0] = grid[:, -1]
    elif last_all_nan and not first_all_nan:
        grid[:, -1] = grid[:, 0]

    # --- Pad beyond ±180° for interpolation -----------------------------
    new_lons = list(lons)
    grid_parts = [grid]
    padded = False

    # Pad right side: ensure coverage beyond +180.
    if lons[-1] <= 180.0:
        new_lons.append(lons[-1] + step)
        grid_parts.append(grid[:, 1:2])
        padded = True

    # Pad left side: ensure coverage beyond -180.
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
    """
    Calculates the displacement scale factor given a model globe radius and the Earth's radius.
    
    Parameters:
      model_radius_mm (float): The desired radius of the un-displaced globe in millimeters.
      earth_radius_km (float): The real-world radius that the grid elevations are relative to in kilometers 
                                  (default is Earth's mean radius of 6371.0 km).
      vertical_exagg (float): Vertical exaggeration factor.
      
    Returns:
      float: The scale factor to use in `displace_vertices`.
    """
    earth_radius_m = earth_radius_km * 1000.0
    return (model_radius_mm / earth_radius_m) * vertical_exagg


def displace_vertices(
    vertices, lats, lons, grid, scale,
    show_progress=False, chunk_size=10000,
    interp_method='linear', num_threads=-1
):
    """
    Displaces each vertex radially using an interpolated displacement from a geographic grid.

    For each vertex:
      - Convert (x,y,z) to (lat, lon)
      - Interpolate the grid value
      - Compute new radius = old radius + scale * grid_value
      - Update vertex = (unit vector) * new radius

    Parameters:
      vertices: (n_points x 3) numpy array.
      lats, lons: 1D arrays corresponding to the grid.
      grid: 2D array of grid values.
      scale: Scalar multiplier.
      show_progress (bool): If True, process in chunks with a progress bar.
      chunk_size (int): Number of vertices per chunk if progress is enabled.
      interp_method (str): Interpolation method for RegularGridInterpolator (default is 'linear').
      num_threads (int): Number of threads for parallel processing (default is -1, which uses all cores).
    
    Returns:
      new_vertices: numpy array with displaced vertices.
    """
    import os
    from concurrent.futures import ThreadPoolExecutor, as_completed

    lats, lons, grid = _wrap_longitude(lats, lons, grid)
    
    # Set up the interpolator (axes: (lat, lon))
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
        r = np.linalg.norm(chunk, axis=1)
        r_safe = np.where(r == 0.0, 1.0, r)
        lat = np.degrees(np.arcsin(chunk[:, 2] / r_safe))
        lon = np.degrees(np.arctan2(chunk[:, 1], chunk[:, 0]))
        pts = np.stack((lat, lon), axis=-1)
        displacement = interpolator(pts)
        displacement = np.nan_to_num(displacement)
        new_r = r + scale * displacement
        if np.any(new_r <= 0):
            raise ValueError(
                "Vertex displacement translates point(s) deeper than the origin (new radius <= 0)."
            )
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
            r = np.linalg.norm(vertices, axis=1)
            r_safe = np.where(r == 0.0, 1.0, r)
            lat = np.degrees(np.arcsin(vertices[:, 2] / r_safe))
            lon = np.degrees(np.arctan2(vertices[:, 1], vertices[:, 0]))
            pts = np.stack((lat, lon), axis=-1)
            displacement = interpolator(pts)
            displacement = np.nan_to_num(displacement)
            new_r = r + scale * displacement
            if np.any(new_r <= 0):
                raise ValueError(
                    "Vertex displacement translates point(s) deeper than the origin (new radius <= 0)."
                )
            new_vertices = (vertices / r_safe[:, None]) * new_r[:, None]

    return new_vertices


def assign_vertex_colors(
    vertices, lats, lons, grid, colormap='viridis', norm=None,
    vmin=None, vmax=None, show_progress=False, chunk_size=10000,
    interp_method='linear', num_threads=-1
):
    """
    Assigns an RGB color to each vertex by interpolating grid values (e.g., for surface properties)
    and then mapping normalized values to a matplotlib colormap.

    Parameters:
      vertices: (n_points x 3) array.
      lats, lons, grid: Geographic grid data used for color assignment.
      colormap (str or Colormap): matplotlib colormap name or object.
      norm (callable or Normalize, optional): Normalization function or object. If not provided, linear normalization is used.
      vmin, vmax: Normalization range. If not provided, uses grid min and max.
      show_progress (bool): Whether to process in chunks with a progress bar.
      chunk_size (int): Chunk size for progress bar processing.
      interp_method (str): Interpolation method for RegularGridInterpolator (default is 'linear').
      num_threads (int): Number of threads for parallel processing (default is -1, which uses all cores).

    Returns:
      colors: (n_points x 3) numpy array of RGB colors in [0,1].
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
        
        # Normalization function for scalar values.
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
        r = np.linalg.norm(chunk, axis=1)
        r_safe = np.where(r == 0.0, 1.0, r)
        lat = np.degrees(np.arcsin(chunk[:, 2] / r_safe))
        lon = np.degrees(np.arctan2(chunk[:, 1], chunk[:, 0]))
        pts = np.stack((lat, lon), axis=-1)
        values = interpolator(pts)
        values = np.nan_to_num(values)
        norm_vals = norm(values)
        chunk_colors = cmap(norm_vals)[:, :3]  # extract RGB only
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
            r = np.linalg.norm(vertices, axis=1)
            r_safe = np.where(r == 0.0, 1.0, r)
            lat = np.degrees(np.arcsin(vertices[:, 2] / r_safe))
            lon = np.degrees(np.arctan2(vertices[:, 1], vertices[:, 0]))
            pts = np.stack((lat, lon), axis=-1)
            values = interpolator(pts)
            values = np.nan_to_num(values)
            norm_vals = norm(values)
            colors = cmap(norm_vals)[:, :3]
    return colors


def assign_vertex_colors_image(vertices, image_path, show_progress=False, chunk_size=10000, num_threads=-1):
    """
    Assigns an RGB color to each vertex by sampling from an equirectangular image.

    Parameters:
      vertices: (n_points x 3) array.
      image_path (str): Path to the image file.
      show_progress (bool): Whether to process in chunks with a progress bar.
      chunk_size (int): Chunk size for progress bar processing.
      num_threads (int): Number of threads for parallel processing (default is -1, which uses all cores).

    Returns:
      colors: (n_points x 3) numpy array of RGB colors in [0,1].
    """
    import os
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Load image
    img = plt.imread(image_path)
    
    # Handle different image formats (e.g. RGBA, uint8 vs float)
    if img.dtype == np.uint8:
        img = img.astype(np.float64) / 255.0
    
    # Ensure we have at least RGB
    if img.ndim == 2: # Grayscale
        img = np.stack((img,)*3, axis=-1)
    elif img.shape[2] > 3: # RGBA
        img = img[:, :, :3]
        
    height, width, _ = img.shape
    
    n = vertices.shape[0]
    colors = np.empty((n, 3), dtype=np.float64)
    
    def get_colors_from_chunk(chunk):
        r = np.linalg.norm(chunk, axis=1)
        r_safe = np.where(r == 0.0, 1.0, r)
        
        # Calculate lat/lon
        lat = np.degrees(np.arcsin(chunk[:, 2] / r_safe))
        lon = np.degrees(np.arctan2(chunk[:, 1], chunk[:, 0]))
        
        # Map to image coordinates
        # Lat: 90 -> 0, -90 -> height-1
        # Lon: -180 -> 0, 180 -> width-1
        
        v = (90 - lat) / 180.0 * (height - 1)
        u = (lon + 180) / 360.0 * (width - 1)
        
        # Nearest neighbor interpolation for simplicity
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


def displace_by_points(
    vertices: np.ndarray,
    points_data: object,
    displacement: float = 1.0,
    radius_degrees: float = 1.0,
    num_threads: int = -1,
) -> np.ndarray:
    """
    Displaces vertices radially if they are within a search radius (in degrees)
    of Point/MultiPoint geometries.

    Parameters:
      vertices (np.ndarray): (n_points x 3) vertex coordinates in millimeters.
      points_data (str or array-like): Path to a shapefile containing Point/MultiPoint
        geometries, or an (N, 2) array/list of (lon, lat) coordinates.
      displacement (float): Radial displacement to apply to vertices within radius (in mm).
      radius_degrees (float): Search radius in decimal degrees.
      num_threads (int): Number of threads for parallel processing (default is -1, which uses all cores).

    Returns:
      np.ndarray: Displaced (n_points x 3) vertex coordinates.

    Raises:
      TypeError: If points_data is a shapefile containing non-Point/MultiPoint geometries.
      ValueError: If points_data has invalid shape, radius_degrees < 0, or if displacement
        translates any point deeper than the origin (new radius <= 0).
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

    r = np.linalg.norm(vertices, axis=1)
    r_safe = np.where(r == 0.0, 1.0, r)

    lats = np.degrees(np.arcsin(vertices[:, 2] / r_safe))
    lons = np.degrees(np.arctan2(vertices[:, 1], vertices[:, 0]))

    points_gdf = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(lons, lats),
        crs=gdf.crs
    )

    joined = _parallel_sjoin(points_gdf, gdf, num_threads=num_threads)
    matched_indices = joined.index[joined['index_right'].notna()].unique()
    inside_mask = np.zeros(len(vertices), dtype=bool)
    inside_mask[matched_indices] = True

    new_r = r + np.where(inside_mask, displacement, 0.0)

    if np.any(new_r <= 0):
        raise ValueError(
            "Vertex displacement translates point(s) deeper than the origin (new radius <= 0)."
        )

    new_vertices = (vertices / r_safe[:, None]) * new_r[:, None]
    return new_vertices


def displace_near_lines(
    vertices: np.ndarray,
    shapefile_path: str,
    displacement: float = 1.0,
    width_degrees: float = 0.5,
    num_threads: int = -1,
) -> np.ndarray:
    """
    Displaces vertices radially if they are close to (within width_degrees of)
    line or polygon geometries.

    Parameters:
      vertices (np.ndarray): (n_points x 3) vertex coordinates in millimeters.
      shapefile_path (str): Path to the shapefile.
      displacement (float): Radial displacement to apply (in mm).
      width_degrees (float): Distance (in degrees) to buffer the geometries.
      num_threads (int): Number of threads for parallel processing (default is -1, which uses all cores).

    Returns:
      np.ndarray: Displaced (n_points x 3) vertex coordinates.

    Raises:
      ValueError: If width_degrees < 0, or if displacement translates any point
        deeper than the origin (new radius <= 0).
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

    r = np.linalg.norm(vertices, axis=1)
    r_safe = np.where(r == 0.0, 1.0, r)

    lats = np.degrees(np.arcsin(vertices[:, 2] / r_safe))
    lons = np.degrees(np.arctan2(vertices[:, 1], vertices[:, 0]))

    points_gdf = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(lons, lats),
        crs=gdf.crs
    )

    joined = _parallel_sjoin(points_gdf, gdf, num_threads=num_threads)
    matched_indices = joined.index[joined['index_right'].notna()].unique()
    inside_mask = np.zeros(len(vertices), dtype=bool)
    inside_mask[matched_indices] = True

    new_r = r + np.where(inside_mask, displacement, 0.0)

    if np.any(new_r <= 0):
        raise ValueError(
            "Vertex displacement translates point(s) deeper than the origin (new radius <= 0)."
        )

    new_vertices = (vertices / r_safe[:, None]) * new_r[:, None]
    return new_vertices


def displace_by_polygons(
    vertices: np.ndarray,
    shapefile_path: str,
    displacement: float = 1.0,
    displace_inside: bool = True,
    num_threads: int = -1,
) -> np.ndarray:
    """
    Displaces vertices radially depending on whether they are inside or outside closed polygons.

    Parameters:
      vertices (np.ndarray): (n_points x 3) vertex coordinates in millimeters.
      shapefile_path (str): Path to the shapefile containing Polygon/MultiPolygon geometries.
      displacement (float): Radial displacement to apply (in mm).
      displace_inside (bool): If True, displace points inside polygons. If False,
        displace points outside polygons.
      num_threads (int): Number of threads for parallel processing (default is -1, which uses all cores).

    Returns:
      np.ndarray: Displaced (n_points x 3) vertex coordinates.

    Raises:
      TypeError: If shapefile contains non-Polygon/MultiPolygon geometries.
      ValueError: If displacement translates any point deeper than the origin (new radius <= 0).
    """
    import geopandas as gpd

    gdf = gpd.read_file(shapefile_path)
    invalid_types = set(gdf.geometry.geom_type.unique()) - {"Polygon", "MultiPolygon"}
    if invalid_types:
        raise TypeError(
            f"Geometries must be Polygons or MultiPolygons. Found types: {invalid_types}"
        )

    r = np.linalg.norm(vertices, axis=1)
    r_safe = np.where(r == 0.0, 1.0, r)

    lats = np.degrees(np.arcsin(vertices[:, 2] / r_safe))
    lons = np.degrees(np.arctan2(vertices[:, 1], vertices[:, 0]))

    points_gdf = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(lons, lats),
        crs=gdf.crs
    )

    joined = _parallel_sjoin(points_gdf, gdf, num_threads=num_threads)
    matched_indices = joined.index[joined['index_right'].notna()].unique()
    inside_mask = np.zeros(len(vertices), dtype=bool)
    inside_mask[matched_indices] = True

    if displace_inside:
        apply_mask = inside_mask
    else:
        apply_mask = ~inside_mask

    new_r = r + np.where(apply_mask, displacement, 0.0)

    if np.any(new_r <= 0):
        raise ValueError(
            "Vertex displacement translates point(s) deeper than the origin (new radius <= 0)."
        )

    new_vertices = (vertices / r_safe[:, None]) * new_r[:, None]
    return new_vertices
