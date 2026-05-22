"""Displacement and colouring module for the globe3d package.

This module provides object-oriented classes to displace mesh vertices radially
based on grids, points, lines, or polygons, and to assign vertex colors based
on grids, images, or constant values.
"""

import os
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import RegularGridInterpolator
from tqdm import tqdm
from globe3d.grid import GeographicGrid


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


class Displacer:
    """Base class for applying radial displacements to vertices."""

    def __call__(self, vertices: np.ndarray, scale: float = 1.0) -> np.ndarray:
        """Applies displacement to a (N, 3) vertex array.

        Args:
            vertices (numpy.ndarray): (N, 3) vertex array in millimeters.
            scale (float, optional): Scaling factor for the displacement. Defaults to 1.0.

        Returns:
            numpy.ndarray: Displaced vertex array of shape (N, 3).
        """
        raise NotImplementedError

    def apply(self, model: "GlobeModel", scale: float = 1.0):
        """Applies displacement to a GlobeModel and records the step in its recipe.

        Args:
            model (GlobeModel): The model to displace.
            scale (float, optional): Multiplier for the displacement. Defaults to 1.0.
        """
        model.displace(self, scale=scale)


class GridDisplacer(Displacer):
    """Displaces vertices radially based on values interpolated from a geographic grid."""

    def __init__(
        self,
        grid_data: GeographicGrid,
        interp_method: str = "linear",
        num_threads: int = -1,
        show_progress: bool = False,
        chunk_size: int = 10000,
    ):
        """Initializes a GridDisplacer.

        Args:
            grid_data (GeographicGrid): Geographic grid containing latitude, longitude, and values.
            interp_method (str, optional): Interpolation method ('linear' or 'nearest'). Defaults to 'linear'.
            num_threads (int, optional): Parallel execution thread count. Defaults to -1 (all available).
            show_progress (bool, optional): Show progress bar during displacement. Defaults to False.
            chunk_size (int, optional): Chunk size for parallel interpolation. Defaults to 10000.
        """
        if not isinstance(grid_data, GeographicGrid):
            raise TypeError("grid_data must be an instance of GeographicGrid.")
        self.grid_data = grid_data
        self.interp_method = interp_method
        self.num_threads = num_threads
        self.show_progress = show_progress
        self.chunk_size = chunk_size

    def __call__(self, vertices: np.ndarray, scale: float = 1.0) -> np.ndarray:
        lats, lons, grid = _wrap_longitude(self.grid_data.lats, self.grid_data.lons, self.grid_data.grid)
        interpolator = RegularGridInterpolator(
            (lats, lons), grid, bounds_error=False, fill_value=None, method=self.interp_method
        )
        n = vertices.shape[0]
        new_vertices = np.empty_like(vertices)

        num_workers = self.num_threads
        if num_workers == -1:
            num_workers = os.cpu_count() or 1
        elif num_workers <= 0:
            num_workers = 1

        def process_chunk(start_idx):
            end_idx = min(start_idx + self.chunk_size, n)
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

        chunk_starts = list(range(0, n, self.chunk_size))

        if num_workers > 1 and len(chunk_starts) > 1:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(process_chunk, start) for start in chunk_starts]
                if self.show_progress:
                    for fut in tqdm(as_completed(futures), total=len(futures), desc="Displacing vertices (parallel)"):
                        start, end, result = fut.result()
                        new_vertices[start:end] = result
                else:
                    for fut in futures:
                        start, end, result = fut.result()
                        new_vertices[start:end] = result
        else:
            if self.show_progress and n > self.chunk_size:
                for start in tqdm(chunk_starts, desc="Displacing vertices"):
                    _, _, result = process_chunk(start)
                    new_vertices[start:start+self.chunk_size] = result
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


def _parallel_sjoin(points_gdf, gdf, num_threads=-1):
    """Performs a spatial join in parallel by chunking the points GeoDataFrame."""
    import pandas as pd
    import geopandas as gpd

    num_workers = num_threads
    if num_workers == -1:
        num_workers = os.cpu_count() or 1
    elif num_workers <= 0:
        num_workers = 1

    num_points = len(points_gdf)
    if num_workers <= 1 or num_points < 10000:
        return gpd.sjoin(points_gdf, gdf, predicate='intersects', how='left')

    chunk_size = (num_points + num_workers - 1) // num_workers

    def run_sjoin(chunk_start):
        chunk_end = min(chunk_start + chunk_size, num_points)
        chunk_gdf = points_gdf.iloc[chunk_start:chunk_end]
        return gpd.sjoin(chunk_gdf, gdf, predicate='intersects', how='left')

    chunk_starts = list(range(0, num_points, chunk_size))
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        results = list(executor.map(run_sjoin, chunk_starts))

    return pd.concat(results)


def _find_points_inside_gdf(vertices, gdf, num_threads=-1):
    """Finds which vertices fall inside the geometries of a GeoDataFrame."""
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


class PointDisplacer(Displacer):
    """Displaces vertices radially based on proximity to Point/MultiPoint geometries."""

    def __init__(
        self,
        points_data: object,
        displacement: float = 1.0,
        radius_degrees: float = 1.0,
        num_threads: int = -1,
    ):
        """Initializes a PointDisplacer.

        Args:
            points_data (str or array-like): Path to a shapefile or an (N, 2) array of (lon, lat).
            displacement (float, optional): Base radial displacement in mm. Defaults to 1.0.
            radius_degrees (float, optional): Proximity threshold in degrees. Defaults to 1.0.
            num_threads (int, optional): Parallel threads. Defaults to -1.
        """
        import geopandas as gpd

        if isinstance(points_data, str):
            gdf = gpd.read_file(points_data)
            invalid_types = set(gdf.geometry.geom_type.unique()) - {"Point", "MultiPoint"}
            if invalid_types:
                raise TypeError(
                    f"Geometries must be Points or MultiPoints. Found types: {invalid_types}"
                )
            self._gdf = gdf
        else:
            pts = np.asarray(points_data)
            if pts.ndim != 2 or pts.shape[1] != 2:
                raise ValueError("points_data array must have shape (N, 2) representing (lon, lat).")
            self._gdf = gpd.GeoDataFrame(
                geometry=gpd.points_from_xy(pts[:, 0], pts[:, 1]),
                crs="EPSG:4326"
            )

        if radius_degrees < 0:
            raise ValueError("radius_degrees must be non-negative.")

        self.points_data = points_data
        self.displacement = float(displacement)
        self.radius_degrees = float(radius_degrees)
        self.num_threads = num_threads

    def __call__(self, vertices: np.ndarray, scale: float = 1.0) -> np.ndarray:
        gdf = self._gdf.copy()
        if self.radius_degrees > 0:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")
                gdf.geometry = gdf.geometry.buffer(self.radius_degrees)

        inside_mask, r = _find_points_inside_gdf(vertices, gdf, num_threads=self.num_threads)
        eff_disp = self.displacement * scale
        new_r = r + np.where(inside_mask, eff_disp, 0.0)

        if np.any(new_r <= 0):
            raise ValueError(
                "Vertex displacement translates point(s) deeper than the origin (new radius <= 0)."
            )

        r_safe = np.where(r == 0.0, 1.0, r)
        new_vertices = (vertices / r_safe[:, None]) * new_r[:, None]
        return new_vertices


class LineDisplacer(Displacer):
    """Displaces vertices radially based on proximity to line or polygon geometries."""

    def __init__(
        self,
        shapefile_path: str,
        displacement: float = 1.0,
        width_degrees: float = 0.5,
        num_threads: int = -1,
    ):
        """Initializes a LineDisplacer.

        Args:
            shapefile_path (str): Path to the shapefile.
            displacement (float, optional): Base radial displacement in mm. Defaults to 1.0.
            width_degrees (float, optional): Distance in degrees to buffer geometries. Defaults to 0.5.
            num_threads (int, optional): Parallel threads. Defaults to -1.
        """
        import geopandas as gpd

        gdf = gpd.read_file(shapefile_path)
        if width_degrees < 0:
            raise ValueError("width_degrees must be non-negative.")

        self.shapefile_path = shapefile_path
        self._gdf = gdf
        self.displacement = float(displacement)
        self.width_degrees = float(width_degrees)
        self.num_threads = num_threads

    def __call__(self, vertices: np.ndarray, scale: float = 1.0) -> np.ndarray:
        gdf = self._gdf.copy()
        if self.width_degrees > 0:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")
                gdf.geometry = gdf.geometry.buffer(self.width_degrees)

        inside_mask, r = _find_points_inside_gdf(vertices, gdf, num_threads=self.num_threads)
        eff_disp = self.displacement * scale
        new_r = r + np.where(inside_mask, eff_disp, 0.0)

        if np.any(new_r <= 0):
            raise ValueError(
                "Vertex displacement translates point(s) deeper than the origin (new radius <= 0)."
            )

        r_safe = np.where(r == 0.0, 1.0, r)
        new_vertices = (vertices / r_safe[:, None]) * new_r[:, None]
        return new_vertices


class PolygonDisplacer(Displacer):
    """Displaces vertices radially depending on whether they fall inside/outside closed polygons."""

    def __init__(
        self,
        shapefile_path: str,
        displacement: float = 1.0,
        displace_inside: bool = True,
        num_threads: int = -1,
    ):
        """Initializes a PolygonDisplacer.

        Args:
            shapefile_path (str): Path to shapefile containing Polygon/MultiPolygon geometries.
            displacement (float, optional): Base radial displacement in mm. Defaults to 1.0.
            displace_inside (bool, optional): If True, displace points inside polygons. If False,
                displace points outside. Defaults to True.
            num_threads (int, optional): Parallel threads. Defaults to -1.
        """
        import geopandas as gpd

        gdf = gpd.read_file(shapefile_path)
        invalid_types = set(gdf.geometry.geom_type.unique()) - {"Polygon", "MultiPolygon"}
        if invalid_types:
            raise TypeError(
                f"Geometries must be Polygons or MultiPolygons. Found types: {invalid_types}"
            )

        self.shapefile_path = shapefile_path
        self._gdf = gdf
        self.displacement = float(displacement)
        self.displace_inside = bool(displace_inside)
        self.num_threads = num_threads

    def __call__(self, vertices: np.ndarray, scale: float = 1.0) -> np.ndarray:
        inside_mask, r = _find_points_inside_gdf(vertices, self._gdf, num_threads=self.num_threads)

        if self.displace_inside:
            apply_mask = inside_mask
        else:
            apply_mask = ~inside_mask

        eff_disp = self.displacement * scale
        new_r = r + np.where(apply_mask, eff_disp, 0.0)

        if np.any(new_r <= 0):
            raise ValueError(
                "Vertex displacement translates point(s) deeper than the origin (new radius <= 0)."
            )

        r_safe = np.where(r == 0.0, 1.0, r)
        new_vertices = (vertices / r_safe[:, None]) * new_r[:, None]
        return new_vertices


class Colourer:
    """Base class for assigning colors to vertices."""

    def __call__(self, vertices: np.ndarray) -> np.ndarray:
        """Generates RGB colors for the given (N, 3) vertex array.

        Args:
            vertices (numpy.ndarray): (N, 3) vertex array.

        Returns:
            numpy.ndarray: (N, 3) RGB color array with values in [0, 1].
        """
        raise NotImplementedError

    def apply(
        self,
        model: "GlobeModel",
        target: str = "outer",
        selection=None,
        selection_kwargs=None,
    ):
        """Applies coloring to a GlobeModel and records the step in its recipe.

        Args:
            model (GlobeModel): The model to color.
            target (str, optional): Target to color ("outer" or "inner"). Defaults to "outer".
            selection (str, callable, or array-like, optional): Vertex subset selection.
                Can be a string (e.g. 'inward_facing'), a callable, or indices.
            selection_kwargs (dict, optional): Additional kwargs for the selection function.
        """
        model.colour(self, target=target, selection=selection, selection_kwargs=selection_kwargs)


class GridColourer(Colourer):
    """Assigns RGB colors to vertices based on interpolation from a geographic grid."""

    def __init__(
        self,
        grid_data: GeographicGrid,
        colormap="viridis",
        norm=None,
        vmin=None,
        vmax=None,
        interp_method: str = "linear",
        num_threads: int = -1,
        show_progress: bool = False,
        chunk_size: int = 10000,
    ):
        """Initializes a GridColourer.

        Args:
            grid_data (GeographicGrid): Geographic grid.
            colormap (str or Colormap, optional): Matplotlib colormap name or object. Defaults to 'viridis'.
            norm (callable or Normalize, optional): Normalization object/function.
            vmin (float, optional): Min value for linear normalization.
            vmax (float, optional): Max value for linear normalization.
            interp_method (str, optional): Interpolation method. Defaults to 'linear'.
            num_threads (int, optional): Parallel threads. Defaults to -1.
            show_progress (bool, optional): Show progress bar. Defaults to False.
            chunk_size (int, optional): Chunk size for progress tracking. Defaults to 10000.
        """
        if not isinstance(grid_data, GeographicGrid):
            raise TypeError("grid_data must be an instance of GeographicGrid.")
        self.grid_data = grid_data
        self.colormap = colormap
        self.norm = norm
        self.vmin = vmin
        self.vmax = vmax
        self.interp_method = interp_method
        self.num_threads = num_threads
        self.show_progress = show_progress
        self.chunk_size = chunk_size

    def __call__(self, vertices: np.ndarray) -> np.ndarray:
        if isinstance(self.colormap, str):
            cmap = plt.get_cmap(self.colormap)
        else:
            cmap = self.colormap

        lats, lons, grid = _wrap_longitude(self.grid_data.lats, self.grid_data.lons, self.grid_data.grid)

        if self.norm is None:
            vmin = self.vmin if self.vmin is not None else np.nanmin(grid)
            vmax = self.vmax if self.vmax is not None else np.nanmax(grid)

            def normalize(val):
                # Suppress divide-by-zero warnings for uniform grid values (vmin == vmax)
                if vmin == vmax:
                    return np.zeros_like(val)
                return (val - vmin) / (vmax - vmin)
            norm_func = normalize
        else:
            norm_func = self.norm

        interpolator = RegularGridInterpolator(
            (lats, lons), grid, bounds_error=False, fill_value=None, method=self.interp_method
        )

        n = vertices.shape[0]
        colors = np.empty((n, 3), dtype=np.float64)

        num_workers = self.num_threads
        if num_workers == -1:
            num_workers = os.cpu_count() or 1
        elif num_workers <= 0:
            num_workers = 1

        def process_chunk(start_idx):
            end_idx = min(start_idx + self.chunk_size, n)
            chunk = vertices[start_idx:end_idx]
            _, lat, lon = cartesian_to_spherical(chunk)
            pts = np.stack((lat, lon), axis=-1)
            values = interpolator(pts)
            values = np.nan_to_num(values)
            norm_vals = norm_func(values)
            chunk_colors = cmap(norm_vals)[:, :3]
            return start_idx, end_idx, chunk_colors

        chunk_starts = list(range(0, n, self.chunk_size))

        if num_workers > 1 and len(chunk_starts) > 1:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(process_chunk, start) for start in chunk_starts]
                if self.show_progress:
                    for fut in tqdm(as_completed(futures), total=len(futures), desc="Assigning colors (parallel)"):
                        start, end, result = fut.result()
                        colors[start:end] = result
                else:
                    for fut in futures:
                        start, end, result = fut.result()
                        colors[start:end] = result
        else:
            if self.show_progress and n > self.chunk_size:
                for start in tqdm(chunk_starts, desc="Assigning colors"):
                    _, _, result = process_chunk(start)
                    colors[start:start+self.chunk_size] = result
            else:
                _, lat, lon = cartesian_to_spherical(vertices)
                pts = np.stack((lat, lon), axis=-1)
                values = interpolator(pts)
                values = np.nan_to_num(values)
                norm_vals = norm_func(values)
                colors = cmap(norm_vals)[:, :3]

        return colors


class ImageColourer(Colourer):
    """Assigns RGB colors to vertices by sampling from an equirectangular image."""

    def __init__(
        self,
        image_path: str,
        num_threads: int = -1,
        show_progress: bool = False,
        chunk_size: int = 10000,
    ):
        """Initializes an ImageColourer.

        Args:
            image_path (str): File path to the image.
            num_threads (int, optional): Parallel threads. Defaults to -1.
            show_progress (bool, optional): Show progress. Defaults to False.
            chunk_size (int, optional): Chunk size. Defaults to 10000.
        """
        self.image_path = image_path
        self.num_threads = num_threads
        self.show_progress = show_progress
        self.chunk_size = chunk_size

    def __call__(self, vertices: np.ndarray) -> np.ndarray:
        img = plt.imread(self.image_path)

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

        num_workers = self.num_threads
        if num_workers == -1:
            num_workers = os.cpu_count() or 1
        elif num_workers <= 0:
            num_workers = 1

        def process_chunk(start_idx):
            end_idx = min(start_idx + self.chunk_size, n)
            chunk = vertices[start_idx:end_idx]
            chunk_colors = get_colors_from_chunk(chunk)
            return start_idx, end_idx, chunk_colors

        chunk_starts = list(range(0, n, self.chunk_size))

        if num_workers > 1 and len(chunk_starts) > 1:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(process_chunk, start) for start in chunk_starts]
                if self.show_progress:
                    for fut in tqdm(as_completed(futures), total=len(futures), desc="Assigning image colors (parallel)"):
                        start, end, result = fut.result()
                        colors[start:end] = result
                else:
                    for fut in futures:
                        start, end, result = fut.result()
                        colors[start:end] = result
        else:
            if self.show_progress and n > self.chunk_size:
                for start in tqdm(chunk_starts, desc="Assigning image colors"):
                    _, _, result = process_chunk(start)
                    colors[start:start+self.chunk_size] = result
            else:
                colors = get_colors_from_chunk(vertices)

        return colors


class ConstantColourer(Colourer):
    """Assigns a constant color to vertices."""

    def __init__(self, color: object):
        """Initializes with a constant RGB color.

        Args:
            color (array-like): 3-element RGB in range [0, 1].
        """
        c_val = np.asarray(color, dtype=np.float64)
        if c_val.shape != (3,):
            raise ValueError("constant_color must be a 3-element RGB array-like.")
        if np.any(c_val < 0.0) or np.any(c_val > 1.0):
            raise ValueError("color values must be in the range [0, 1].")
        self.color = c_val

    def __call__(self, vertices: np.ndarray) -> np.ndarray:
        n = vertices.shape[0]
        return np.tile(self.color, (n, 1))


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
