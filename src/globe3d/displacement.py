import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import RegularGridInterpolator
from tqdm import tqdm

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
    
    Returns:
      new_vertices: numpy array with displaced vertices.
    """
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


def assign_vertex_colors(vertices, lats, lons, grid, colormap='viridis', vmin=None, vmax=None, show_progress=False, chunk_size=10000, interp_method='linear'):
    """
    Assigns an RGB color to each vertex by interpolating grid values (e.g., for surface properties)
    and then mapping normalized values to a matplotlib colormap.

    Parameters:
      vertices: (n_points x 3) array.
      lats, lons, grid: Geographic grid data used for color assignment.
      colormap (str): matplotlib colormap name.
      vmin, vmax: Normalization range. If not provided, uses grid min and max.
      show_progress (bool): Whether to process in chunks with a progress bar.
      chunk_size (int): Chunk size for progress bar processing.

    Returns:
      colors: (n_points x 3) numpy array of RGB colors in [0,1].
    """

    if isinstance(colormap, str):
        cmap = plt.get_cmap(colormap)
    else:
        cmap = colormap
    
    if vmin is None:
        vmin = np.nanmin(grid)
    if vmax is None:
        vmax = np.nanmax(grid)
    
    # Normalization function for scalar values.
    def normalize(val):
        return (val - vmin) / (vmax - vmin)
    
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
            norm_vals = normalize(values)
            colors[i:i+chunk_size] = cmap(norm_vals)[:, :3]  # extract RGB only
    else:
        r = np.linalg.norm(vertices, axis=1)
        lat = np.degrees(np.arcsin(vertices[:, 2] / r))
        lon = np.degrees(np.arctan2(vertices[:, 1], vertices[:, 0]))
        pts = np.stack((lat, lon), axis=-1)
        values = interpolator(pts)
        values = np.nan_to_num(values)
        norm_vals = normalize(values)
        colors = cmap(norm_vals)[:, :3]
    return colors
