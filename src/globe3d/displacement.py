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


def displace_vertices(vertices, lats, lons, grid, scale, show_progress=False, chunk_size=10000, interp_method='linear'):
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
    
    Returns:
      new_vertices: numpy array with displaced vertices.
    """
    lats, lons, grid = _wrap_longitude(lats, lons, grid)
    
    # Set up the interpolator (axes: (lat, lon))
    interpolator = RegularGridInterpolator((lats, lons), grid, bounds_error=False, fill_value=None, method=interp_method)
    n = vertices.shape[0]
    new_vertices = np.empty_like(vertices)
    
    if show_progress and n > chunk_size:
        for i in tqdm(range(0, n, chunk_size), desc="Displacing vertices"):
            chunk = vertices[i:i+chunk_size]
            r = np.linalg.norm(chunk, axis=1)
            lat = np.degrees(np.arcsin(chunk[:, 2] / r))
            lon = np.degrees(np.arctan2(chunk[:, 1], chunk[:, 0]))
            pts = np.stack((lat, lon), axis=-1)
            displacement = interpolator(pts)
            displacement = np.nan_to_num(displacement)
            new_r = r + scale * displacement
            new_vertices[i:i+chunk_size] = (chunk / r[:, None]) * new_r[:, None]
    else:
        r = np.linalg.norm(vertices, axis=1)
        lat = np.degrees(np.arcsin(vertices[:, 2] / r))
        lon = np.degrees(np.arctan2(vertices[:, 1], vertices[:, 0]))
        pts = np.stack((lat, lon), axis=-1)
        displacement = interpolator(pts)
        displacement = np.nan_to_num(displacement)
        new_r = r + scale * displacement
        new_vertices = (vertices / r[:, None]) * new_r[:, None]
    return new_vertices


def assign_vertex_colors(vertices, lats, lons, grid, colormap='viridis', norm=None, vmin=None, vmax=None, show_progress=False, chunk_size=10000, interp_method='linear'):
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

    Returns:
      colors: (n_points x 3) numpy array of RGB colors in [0,1].
    """

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
    if show_progress and n > chunk_size:
        for i in tqdm(range(0, n, chunk_size), desc="Assigning colors"):
            chunk = vertices[i:i+chunk_size]
            r = np.linalg.norm(chunk, axis=1)
            lat = np.degrees(np.arcsin(chunk[:, 2] / r))
            lon = np.degrees(np.arctan2(chunk[:, 1], chunk[:, 0]))
            pts = np.stack((lat, lon), axis=-1)
            values = interpolator(pts)
            values = np.nan_to_num(values)
            norm_vals = norm(values)
            colors[i:i+chunk_size] = cmap(norm_vals)[:, :3]  # extract RGB only
    else:
        r = np.linalg.norm(vertices, axis=1)
        lat = np.degrees(np.arcsin(vertices[:, 2] / r))
        lon = np.degrees(np.arctan2(vertices[:, 1], vertices[:, 0]))
        pts = np.stack((lat, lon), axis=-1)
        values = interpolator(pts)
        values = np.nan_to_num(values)
        norm_vals = norm(values)
        colors = cmap(norm_vals)[:, :3]
    return colors


def assign_vertex_colors_image(vertices, image_path, show_progress=False, chunk_size=10000):
    """
    Assigns an RGB color to each vertex by sampling from an equirectangular image.

    Parameters:
      vertices: (n_points x 3) array.
      image_path (str): Path to the image file.
      show_progress (bool): Whether to process in chunks with a progress bar.
      chunk_size (int): Chunk size for progress bar processing.

    Returns:
      colors: (n_points x 3) numpy array of RGB colors in [0,1].
    """
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
        # Avoid division by zero
        r[r == 0] = 1.0
        
        # Calculate lat/lon
        lat = np.degrees(np.arcsin(chunk[:, 2] / r))
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

    if show_progress and n > chunk_size:
        for i in tqdm(range(0, n, chunk_size), desc="Assigning image colors"):
            chunk = vertices[i:i+chunk_size]
            colors[i:i+chunk_size] = get_colors_from_chunk(chunk)
    else:
        colors = get_colors_from_chunk(vertices)
        
    return colors
