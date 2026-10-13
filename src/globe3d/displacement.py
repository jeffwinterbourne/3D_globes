"""Displacement and colouring module for the globe3d package.

This module provides object-oriented classes to displace mesh vertices radially
based on grids, points, lines, or polygons, and to assign vertex colors based
on grids, images, or constant values.
"""

import os
import warnings
from typing import Union, Optional, Tuple, List, Callable, Sequence, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.path as mpath
from matplotlib.colors import to_rgb
from scipy.interpolate import RegularGridInterpolator
from tqdm import tqdm
from globe3d.grid import GeographicGrid


def _wrap_longitude(lats, lons, grid):
    """Pads the longitude array and grid for periodic boundary conditions.

    Ensures that the longitude axis extends beyond both -180° and +180° by copying
    data from the opposite edge, allowing RegularGridInterpolator to return valid
    values at every longitude in [-180, 180]. It also normalizes [0, 360] grids to
    [-180, 180] and repairs NaN edge columns.

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

    # Normalize [0, 360] longitude grids to [-180, 180]
    if lons.min() >= -0.1 and lons.max() > 180.0:
        if np.isclose(lons[-1] - lons[0], 360.0):
            lons = lons[:-1]
            grid = grid[:, :-1]
        lons = np.where(lons > 180.0, lons - 360.0, lons)
        sort_idx = np.argsort(lons)
        lons = lons[sort_idx]
        grid = grid[:, sort_idx]

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


_UNIT_TO_METERS = {
    'm': 1.0,
    'meters': 1.0,
    'km': 1000.0,
    'kilometers': 1000.0,
    'cm': 0.01,
    'centimeters': 0.01,
    'mm': 0.001,
    'millimeters': 0.001,
    'ft': 0.3048,
    'feet': 0.3048,
}


def calculate_displacement_scale(model_radius_mm, earth_radius_km=6371.0, vertical_exagg=1.0,
                                 grid_units='m'):
    """Calculates the displacement scale factor for a given model globe radius.

    Converts real-world grid values (in the specified ``grid_units``) to
    millimetres on the model sphere, optionally applying a vertical
    exaggeration factor.

    Args:
        model_radius_mm (float): Desired radius of the un-displaced globe in millimeters.
        earth_radius_km (float, optional): Real-world earth radius in kilometers. Defaults to 6371.0.
        vertical_exagg (float, optional): Vertical exaggeration factor. Defaults to 1.0.
        grid_units (str, optional): Units of the grid data values.  Supported values are
            ``'m'``, ``'meters'``, ``'km'``, ``'kilometers'``, ``'cm'``,
            ``'centimeters'``, ``'mm'``, ``'millimeters'``, ``'ft'``, ``'feet'``.
            Defaults to ``'m'`` (meters).

    Returns:
        float: The scale factor to pass to :meth:`GlobeModel.displace` or
        :meth:`_MeshProxy.displace`.

    Raises:
        ValueError: If ``grid_units`` is not one of the supported unit strings.
    """
    if grid_units not in _UNIT_TO_METERS:
        raise ValueError(
            f"Unknown grid_units '{grid_units}'. "
            f"Supported: {sorted(set(_UNIT_TO_METERS.keys()))}"
        )
    meters_per_unit = _UNIT_TO_METERS[grid_units]
    earth_radius_m = earth_radius_km * 1000.0
    return (model_radius_mm / earth_radius_m) * vertical_exagg * meters_per_unit


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


class ConstantDisplacer(Displacer):
    """Displaces vertices radially by a constant amount."""

    def __init__(self, displacement: float):
        """Initializes a ConstantDisplacer.

        Args:
            displacement (float): Radial displacement in mm.
        """
        self.displacement = float(displacement)

    def __call__(self, vertices: np.ndarray, scale: float = 1.0) -> np.ndarray:
        r, lat, lon = cartesian_to_spherical(vertices)
        eff_disp = self.displacement * scale
        new_r = r + eff_disp

        if np.any(new_r <= 0):
            raise ValueError(
                "Vertex displacement translates point(s) deeper than the origin (new radius <= 0)."
            )

        r_safe = np.where(r == 0.0, 1.0, r)
        new_vertices = (vertices / r_safe[:, None]) * new_r[:, None]
        return new_vertices


class GridDisplacer(Displacer):
    """Displaces vertices radially based on values interpolated from a geographic grid."""

    def __init__(
        self,
        grid_data: GeographicGrid,
        interp_method: str = "linear",
        num_threads: int = -1,
        show_progress: bool = False,
        chunk_size: int = 10000,
        reference_level: float = 0.0,
        coastline_step: float = 0.0,
        step_threshold: float = 0.0,
    ):
        """Initializes a GridDisplacer.

        Args:
            grid_data (GeographicGrid): Geographic grid containing latitude, longitude, and values.
            interp_method (str, optional): Interpolation method ('linear' or 'nearest'). Defaults to 'linear'.
            num_threads (int, optional): Parallel execution thread count. Defaults to -1 (all available).
            show_progress (bool, optional): Show progress bar during displacement. Defaults to False.
            chunk_size (int, optional): Chunk size for parallel interpolation. Defaults to 10000.
            reference_level (float, optional): Reference level about which to center the displacement.
                Values below this level displace inward (negative), and values above displace outward (positive).
                Defaults to 0.0.
            coastline_step (float, optional): Synthetic vertical elevation step added at the coastline
                (values > step_threshold) to make landmasses pop distinctly on 3D printed globes. Defaults to 0.0.
            step_threshold (float, optional): Threshold boundary (typically sea level, 0.0) above which
                coastline_step is applied. Defaults to 0.0.
        """
        if not isinstance(grid_data, GeographicGrid):
            raise TypeError("grid_data must be an instance of GeographicGrid.")
        self.grid_data = grid_data
        self.interp_method = interp_method
        self.num_threads = num_threads
        self.show_progress = show_progress
        self.chunk_size = chunk_size
        self.reference_level = float(reference_level)
        self.coastline_step = float(coastline_step)
        self.step_threshold = float(step_threshold)

    def __call__(self, vertices: np.ndarray, scale: float = 1.0) -> np.ndarray:
        grid_values = self.grid_data.grid
        if self.coastline_step != 0.0:
            grid_values = grid_values.copy()
            continent_mask = grid_values > self.step_threshold
            grid_values[continent_mask] += self.coastline_step

        lats, lons, grid = _wrap_longitude(self.grid_data.lats, self.grid_data.lons, grid_values)
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
            displacement = displacement - self.reference_level
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
                displacement = displacement - self.reference_level
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

    def __call__(self, vertices: np.ndarray, current_colors: np.ndarray = None) -> np.ndarray:
        """Generates RGB colors for the given (N, 3) vertex array.

        Args:
            vertices (numpy.ndarray): (N, 3) vertex array.
            current_colors (numpy.ndarray, optional): Existing vertex colors to layer over.
                Defaults to None.

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
        reference: str = "paleo",
        age: Optional[float] = None,
        plate_model: Optional[object] = None,
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
            reference (str, optional): Coordinate reference system ('paleo' or 'modern').
                Defaults to 'paleo'. If 'modern' and `age` is given, grid is reconstructed.
            age (float, optional): Geological age in Ma if reference='modern'. Defaults to None.
            plate_model (PlateModel, optional): Plate reconstruction model if reference='modern'.
                Defaults to None.
        """
        if not isinstance(grid_data, GeographicGrid):
            raise TypeError("grid_data must be an instance of GeographicGrid.")

        self.reference = reference.lower()
        self.age = age
        self.plate_model = plate_model

        if self.reference == "modern" and self.age is not None and self.age != 0:
            pm = self.plate_model
            if pm is None:
                from globe3d import datasets
                pm = datasets.paleo.scotese_plate_model()
            from globe3d.reconstruction import reconstruct_grid
            grid_data = reconstruct_grid(grid_data, plate_model=pm, age_ma=float(self.age))

        self.grid_data = grid_data
        self.colormap = colormap
        self.norm = norm
        self.vmin = vmin
        self.vmax = vmax
        self.interp_method = interp_method
        self.num_threads = num_threads
        self.show_progress = show_progress
        self.chunk_size = chunk_size

    def __call__(self, vertices: np.ndarray, current_colors: np.ndarray = None) -> np.ndarray:
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
        image: Union[str, object, np.ndarray, None] = None,
        image_path: Optional[str] = None,
        num_threads: int = -1,
        show_progress: bool = False,
        chunk_size: int = 10000,
        reference: str = "paleo",
        age: Optional[float] = None,
        plate_model: Optional[object] = None,
    ):
        """Initializes an ImageColourer.

        Args:
            image (str, PIL.Image.Image, or np.ndarray, optional): Equirectangular image
                as a file path, PIL Image, or NumPy array. Defaults to None.
            image_path (str, optional): Legacy alias for image path. Defaults to None.
            num_threads (int, optional): Parallel threads. Defaults to -1.
            show_progress (bool, optional): Show progress. Defaults to False.
            chunk_size (int, optional): Chunk size. Defaults to 10000.
            reference (str, optional): Coordinate reference system ('paleo' or 'modern').
                Defaults to 'paleo'.
            age (float, optional): Geological age in Ma if reference='modern'. Defaults to None.
            plate_model (PlateModel, optional): Plate reconstruction model if reference='modern'.
                Defaults to None.
        """
        img_source = image if image is not None else image_path
        if img_source is None:
            raise ValueError("Either 'image' or 'image_path' must be provided.")

        self.image = img_source
        self.image_path = img_source if isinstance(img_source, str) else None
        self.num_threads = num_threads
        self.show_progress = show_progress
        self.chunk_size = chunk_size
        self.reference = reference.lower()
        self.age = age
        self.plate_model = plate_model

    def __call__(self, vertices: np.ndarray, current_colors: np.ndarray = None) -> np.ndarray:
        if isinstance(self.image, str):
            img = plt.imread(self.image)
        elif hasattr(self.image, "convert"):  # PIL Image
            img = np.array(self.image.convert("RGB"))
        elif isinstance(self.image, np.ndarray):
            img = self.image.copy()
        else:
            raise TypeError("image must be a file path, PIL.Image.Image, or NumPy array.")

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

    def __call__(self, vertices: np.ndarray, current_colors: np.ndarray = None) -> np.ndarray:
        n = vertices.shape[0]
        return np.tile(self.color, (n, 1))


class PointColourer(Colourer):
    """Assigns RGB colors to vertices based on proximity to Point/MultiPoint geometries and customizable marker shapes."""

    def __init__(
        self,
        points_data: object,
        color: object = (1.0, 0.0, 0.0),
        background_color: object = None,
        radius_degrees: float = 1.0,
        marker_shape: object = "circle",
        marker_thickness: float = 0.2,
        num_threads: int = -1,
    ):
        """Initializes a PointColourer.

        Args:
            points_data (str, GeoDataFrame, or array-like): Path to a shapefile, a GeoDataFrame,
                or an (N, 2) array of (lon, lat).
            color (array-like, optional): RGB color for vertices inside the markers. Defaults to (1.0, 0.0, 0.0).
            background_color (array-like, optional): RGB color for vertices outside the markers. If None,
                preserves existing colors. Defaults to None.
            radius_degrees (float, optional): Size threshold of the markers in degrees. Defaults to 1.0.
            marker_shape (str or callable, optional): Shape of the marker. Supported string values are
                'circle', 'square', 'triangle', 'cross', 'star'. Or a callable with signature
                (x_deg, y_deg, radius_degrees) -> boolean_array. Defaults to 'circle'.
            marker_thickness (float, optional): Relative thickness of the cross marker shape. Defaults to 0.2.
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
            self._gdf = gdf.reset_index(drop=True)
        elif isinstance(points_data, gpd.GeoDataFrame):
            self._gdf = points_data.reset_index(drop=True)
        else:
            pts = np.asarray(points_data)
            if pts.ndim != 2 or pts.shape[1] != 2:
                raise ValueError("points_data array must have shape (N, 2) representing (lon, lat).")
            self._gdf = gpd.GeoDataFrame(
                geometry=gpd.points_from_xy(pts[:, 0], pts[:, 1]),
                crs="EPSG:4326"
            ).reset_index(drop=True)

        if radius_degrees < 0:
            raise ValueError("radius_degrees must be non-negative.")

        self.points_data = points_data
        self.color = np.asarray(color, dtype=np.float64)
        self.background_color = np.asarray(background_color, dtype=np.float64) if background_color is not None else None
        self.radius_degrees = float(radius_degrees)
        self.marker_shape = marker_shape
        self.marker_thickness = float(marker_thickness)
        self.num_threads = num_threads

        if self.color.shape != (3,):
            raise ValueError("color must be a 3-element RGB array-like.")
        if np.any(self.color < 0.0) or np.any(self.color > 1.0):
            raise ValueError("color values must be in the range [0, 1].")
        if self.background_color is not None:
            if self.background_color.shape != (3,):
                raise ValueError("background_color must be a 3-element RGB array-like.")
            if np.any(self.background_color < 0.0) or np.any(self.background_color > 1.0):
                raise ValueError("background_color values must be in the range [0, 1].")

    def __call__(self, vertices: np.ndarray, current_colors: np.ndarray = None) -> np.ndarray:
        if current_colors is not None:
            colors = current_colors.copy()
            if self.background_color is not None:
                colors[:] = self.background_color
        else:
            bg = self.background_color if self.background_color is not None else np.array([1.0, 1.0, 1.0])
            colors = np.tile(bg, (len(vertices), 1))

        if self.radius_degrees <= 0 or len(self._gdf) == 0:
            return colors

        import geopandas as gpd
        buffered_gdf = self._gdf.copy()
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")
            buffered_gdf.geometry = buffered_gdf.geometry.buffer(self.radius_degrees)

        r, lats, lons = cartesian_to_spherical(vertices)
        points_gdf = gpd.GeoDataFrame(
            geometry=gpd.points_from_xy(lons, lats),
            crs=self._gdf.crs
        )

        joined = _parallel_sjoin(points_gdf, buffered_gdf, num_threads=self.num_threads)
        valid_joins = joined[joined['index_right'].notna()]
        if len(valid_joins) == 0:
            return colors

        v_idx = valid_joins.index.values
        p_idx = valid_joins['index_right'].astype(int).values

        orig_lons = self._gdf.geometry.x.values
        orig_lats = self._gdf.geometry.y.values
        lat_P = orig_lats[p_idx]
        lon_P = orig_lons[p_idx]

        lat_V = lats[v_idx]
        lon_V = lons[v_idx]

        lat_V_rad = np.radians(lat_V)
        lon_V_rad = np.radians(lon_V)
        lat_P_rad = np.radians(lat_P)
        lon_P_rad = np.radians(lon_P)

        dlon_rad = lon_V_rad - lon_P_rad
        dlon_rad = (dlon_rad + np.pi) % (2 * np.pi) - np.pi

        x = np.cos(lat_V_rad) * np.sin(dlon_rad)
        y = np.sin(lat_V_rad) * np.cos(lat_P_rad) - np.cos(lat_V_rad) * np.sin(lat_P_rad) * np.cos(dlon_rad)

        x_deg = np.degrees(x)
        y_deg = np.degrees(y)

        if callable(self.marker_shape):
            inside = self.marker_shape(x_deg, y_deg, self.radius_degrees)
        else:
            shape_str = str(self.marker_shape).lower()
            if shape_str == "circle":
                inside = (x_deg**2 + y_deg**2) <= self.radius_degrees**2
            elif shape_str in ("square", "box"):
                inside = (np.abs(x_deg) <= self.radius_degrees) & (np.abs(y_deg) <= self.radius_degrees)
            elif shape_str == "triangle":
                inside = (y_deg >= -self.radius_degrees / 2.0) & (y_deg <= self.radius_degrees - np.sqrt(3.0) * np.abs(x_deg))
            elif shape_str == "cross":
                w = self.marker_thickness * self.radius_degrees
                inside_box = (np.abs(x_deg) <= self.radius_degrees) & (np.abs(y_deg) <= self.radius_degrees)
                inside_bars = (np.abs(x_deg) <= w) | (np.abs(y_deg) <= w)
                inside = inside_box & inside_bars
            elif shape_str == "star":
                theta = np.arctan2(y_deg, x_deg)
                r_val = np.sqrt(x_deg**2 + y_deg**2)
                r_limit = self.radius_degrees * (0.6 + 0.4 * np.cos(5 * theta - np.pi / 2.0))
                inside = r_val <= r_limit
            else:
                raise ValueError(
                    f"Unsupported marker_shape '{self.marker_shape}'. "
                    f"Supported: 'circle', 'square', 'triangle', 'cross', 'star' or a callable."
                )

        inside_v_idx = v_idx[inside]
        colors[inside_v_idx] = self.color
        return colors


class LineColourer(Colourer):
    """Assigns RGB colors to vertices based on proximity to line or polygon geometries."""

    def __init__(
        self,
        shapefile_path: object,
        color: object = (1.0, 0.0, 0.0),
        background_color: object = None,
        width_degrees: float = 0.5,
        num_threads: int = -1,
    ):
        """Initializes a LineColourer.

        Args:
            shapefile_path (str or GeoDataFrame): Path to the shapefile or a GeoDataFrame.
            color (array-like, optional): RGB color for vertices inside/near the lines. Defaults to (1.0, 0.0, 0.0).
            background_color (array-like, optional): RGB color outside lines. If None,
                preserves existing colors. Defaults to None.
            width_degrees (float, optional): Distance in degrees to buffer geometries. Defaults to 0.5.
            num_threads (int, optional): Parallel threads. Defaults to -1.
        """
        import geopandas as gpd
        from shapely.geometry import LineString

        if isinstance(shapefile_path, str):
            self._gdf = gpd.read_file(shapefile_path)
        elif isinstance(shapefile_path, gpd.GeoDataFrame):
            self._gdf = shapefile_path
        elif isinstance(shapefile_path, (list, tuple, np.ndarray)):
            if isinstance(shapefile_path, np.ndarray) and shapefile_path.ndim == 2:
                lines = [LineString(shapefile_path)]
            else:
                lines = []
                for item in shapefile_path:
                    arr = np.asarray(item)
                    if arr.ndim != 2 or arr.shape[1] != 2:
                        raise ValueError("Each line array must have shape (N, 2) representing (lon, lat) points.")
                    lines.append(LineString(arr))
            self._gdf = gpd.GeoDataFrame(geometry=lines, crs="EPSG:4326").reset_index(drop=True)
        else:
            raise TypeError("shapefile_path must be a string file path, geopandas GeoDataFrame, or a list/array of (N, 2) coordinates.")

        if width_degrees < 0:
            raise ValueError("width_degrees must be non-negative.")

        self.shapefile_path = shapefile_path
        self.color = np.asarray(color, dtype=np.float64)
        self.background_color = np.asarray(background_color, dtype=np.float64) if background_color is not None else None
        self.width_degrees = float(width_degrees)
        self.num_threads = num_threads

        if self.color.shape != (3,):
            raise ValueError("color must be a 3-element RGB array-like.")
        if np.any(self.color < 0.0) or np.any(self.color > 1.0):
            raise ValueError("color values must be in the range [0, 1].")
        if self.background_color is not None:
            if self.background_color.shape != (3,):
                raise ValueError("background_color must be a 3-element RGB array-like.")
            if np.any(self.background_color < 0.0) or np.any(self.background_color > 1.0):
                raise ValueError("background_color values must be in the range [0, 1].")

    def __call__(self, vertices: np.ndarray, current_colors: np.ndarray = None) -> np.ndarray:
        if current_colors is not None:
            colors = current_colors.copy()
            if self.background_color is not None:
                colors[:] = self.background_color
        else:
            bg = self.background_color if self.background_color is not None else np.array([1.0, 1.0, 1.0])
            colors = np.tile(bg, (len(vertices), 1))

        if len(self._gdf) == 0:
            return colors

        gdf = self._gdf.copy()
        if self.width_degrees > 0:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")
                gdf.geometry = gdf.geometry.buffer(self.width_degrees)

        inside_mask, r = _find_points_inside_gdf(vertices, gdf, num_threads=self.num_threads)
        colors[inside_mask] = self.color
        return colors


class PolygonColourer(Colourer):
    """Assigns RGB colors to vertices depending on whether they fall inside/outside closed polygons."""

    def __init__(
        self,
        shapefile_path: object,
        color: object = (1.0, 0.0, 0.0),
        background_color: object = None,
        flood_inside: bool = True,
        num_threads: int = -1,
    ):
        """Initializes a PolygonColourer.

        Args:
            shapefile_path (str or GeoDataFrame): Path to shapefile containing Polygon/MultiPolygon geometries, or GeoDataFrame.
            color (array-like, optional): RGB color for the flooded region. Defaults to (1.0, 0.0, 0.0).
            background_color (array-like, optional): RGB color for the non-flooded region. If None,
                preserves existing colors. Defaults to None.
            flood_inside (bool, optional): If True, flood points inside polygons. If False,
                flood points outside. Defaults to True.
            num_threads (int, optional): Parallel threads. Defaults to -1.
        """
        import geopandas as gpd
        from shapely.geometry import Polygon

        if isinstance(shapefile_path, str):
            gdf = gpd.read_file(shapefile_path)
            invalid_types = set(gdf.geometry.geom_type.unique()) - {"Polygon", "MultiPolygon"}
            if invalid_types:
                raise TypeError(
                    f"Geometries must be Polygons or MultiPolygons. Found types: {invalid_types}"
                )
        elif isinstance(shapefile_path, gpd.GeoDataFrame):
            gdf = shapefile_path
            invalid_types = set(gdf.geometry.geom_type.unique()) - {"Polygon", "MultiPolygon"}
            if invalid_types:
                raise TypeError(
                    f"Geometries must be Polygons or MultiPolygons. Found types: {invalid_types}"
                )
        elif isinstance(shapefile_path, (list, tuple, np.ndarray)):
            if isinstance(shapefile_path, np.ndarray) and shapefile_path.ndim == 2:
                polys = [Polygon(shapefile_path)]
            else:
                polys = []
                for item in shapefile_path:
                    arr = np.asarray(item)
                    if arr.ndim != 2 or arr.shape[1] != 2:
                        raise ValueError("Each polygon array must have shape (N, 2) representing (lon, lat) points.")
                    polys.append(Polygon(arr))
            gdf = gpd.GeoDataFrame(geometry=polys, crs="EPSG:4326").reset_index(drop=True)
        else:
            raise TypeError("shapefile_path must be a string file path, geopandas GeoDataFrame, or a list/array of (N, 2) coordinates.")

        self.shapefile_path = shapefile_path
        self._gdf = gdf
        self.color = np.asarray(color, dtype=np.float64)
        self.background_color = np.asarray(background_color, dtype=np.float64) if background_color is not None else None
        self.flood_inside = bool(flood_inside)
        self.num_threads = num_threads

        if self.color.shape != (3,):
            raise ValueError("color must be a 3-element RGB array-like.")
        if np.any(self.color < 0.0) or np.any(self.color > 1.0):
            raise ValueError("color values must be in the range [0, 1].")
        if self.background_color is not None:
            if self.background_color.shape != (3,):
                raise ValueError("background_color must be a 3-element RGB array-like.")
            if np.any(self.background_color < 0.0) or np.any(self.background_color > 1.0):
                raise ValueError("background_color values must be in the range [0, 1].")

    def __call__(self, vertices: np.ndarray, current_colors: np.ndarray = None) -> np.ndarray:
        if current_colors is not None:
            colors = current_colors.copy()
            if self.background_color is not None:
                colors[:] = self.background_color
        else:
            bg = self.background_color if self.background_color is not None else np.array([1.0, 1.0, 1.0])
            colors = np.tile(bg, (len(vertices), 1))

        if len(self._gdf) == 0:
            return colors

        inside_mask, r = _find_points_inside_gdf(vertices, self._gdf, num_threads=self.num_threads)

        if self.flood_inside:
            apply_mask = inside_mask
        else:
            apply_mask = ~inside_mask

        colors[apply_mask] = self.color
        return colors


def _parse_color_float(color: Union[str, Sequence[Union[int, float]], np.ndarray]) -> np.ndarray:
    """Parses arbitrary color specification into an RGB float array in [0.0, 1.0]."""
    if isinstance(color, (tuple, list, np.ndarray)) and len(color) >= 3:
        vals = [float(x) for x in color[:3]]
        if any(v > 1.0 for v in vals):
            return np.array([v / 255.0 for v in vals], dtype=np.float64)
        return np.array(vals, dtype=np.float64)
    from matplotlib.colors import to_rgb
    return np.array(to_rgb(color), dtype=np.float64)


def _get_symbol_path(symbol: Union[str, Sequence[Tuple[float, float]], np.ndarray]) -> mpath.Path:
    """Returns a normalized mpath.Path centered at origin with bounding radius 1.0."""
    if isinstance(symbol, (list, tuple, np.ndarray)):
        pts = np.asarray(symbol, dtype=np.float64)
        if pts.ndim != 2 or pts.shape[1] != 2:
            raise ValueError("Polygon points must have shape (N, 2).")
    elif isinstance(symbol, str):
        sym_lower = symbol.lower()
        if sym_lower == "circle":
            theta = np.linspace(0, 2 * np.pi, 64)
            pts = np.column_stack([np.cos(theta), np.sin(theta)])
        elif sym_lower == "square":
            pts = np.array([[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0], [-1.0, -1.0]])
        elif sym_lower == "triangle":
            pts = np.array([[0.0, 1.0], [-0.866, -0.5], [0.866, -0.5], [0.0, 1.0]])
        elif sym_lower == "cross":
            pts = np.array([
                [-0.3, 1.0], [0.3, 1.0], [0.3, 0.3], [1.0, 0.3], [1.0, -0.3], [0.3, -0.3],
                [0.3, -1.0], [-0.3, -1.0], [-0.3, -0.3], [-1.0, -0.3], [-1.0, 0.3], [-0.3, 0.3],
                [-0.3, 1.0]
            ])
        else:
            from globe3d.image import _get_builtin_asset_path, _parse_svg_to_points
            asset_path = _get_builtin_asset_path(symbol) or symbol
            raw_pts = _parse_svg_to_points(asset_path)
            if not raw_pts:
                raise ValueError(f"Could not parse symbol '{symbol}' as SVG or recognized shape.")
            pts = np.asarray(raw_pts, dtype=np.float64)
            # In SVG, y coordinates increase downwards, so invert y for Cartesian/spherical tangent plane
            pts = np.column_stack([pts[:, 0], -pts[:, 1]])
    else:
        raise TypeError(f"Unsupported symbol type: {type(symbol)}")

    cx = (pts[:, 0].min() + pts[:, 0].max()) / 2.0
    cy = (pts[:, 1].min() + pts[:, 1].max()) / 2.0
    centered_x = pts[:, 0] - cx
    centered_y = pts[:, 1] - cy
    max_r = np.max(np.hypot(centered_x, centered_y))
    if max_r < 1e-7:
        max_r = 1.0
    norm_pts = np.column_stack([centered_x / max_r, centered_y / max_r])
    return mpath.Path(norm_pts)


class SymbolColourer(Colourer):
    """Assigns discrete colors to vertices within 2D symbols projected onto the globe sphere.

    Projects geometric shapes (such as 'star', 'circle', 'square', 'triangle', 'cross',
    'N', 'S') or arbitrary SVG paths directly onto the spherical mesh using local
    gnomonic tangent-plane projection. This provides mathematically exact,
    singularity-free placement across all latitudes including both geographic poles.

    Positions can be specified either in paleo coordinates (default) or modern
    geographic coordinates that are dynamically reconstructed to paleo coordinates
    using a PlateModel and age.
    """

    def __init__(
        self,
        symbol: Union[str, Sequence[Tuple[float, float]], np.ndarray] = "star",
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        locations: Optional[Sequence[Union[Tuple[float, float], Dict]]] = None,
        radius_degrees: float = 2.5,
        color: Union[str, Sequence[Union[int, float]]] = "red",
        reference: str = "paleo",
        age: Optional[float] = None,
        plate_model: Optional[object] = None,
        rotation_degrees: float = 0.0,
    ):
        """Initializes a SymbolColourer.

        Args:
            symbol (str or sequence, optional): Built-in symbol ('star', 'circle',
                'square', 'triangle', 'cross', 'N', 'S'), path to an SVG file, or
                an (N, 2) sequence of Cartesian polygon points. Defaults to 'star'.
            lat (float, optional): Center latitude in degrees for a single symbol.
                Defaults to None.
            lon (float, optional): Center longitude in degrees for a single symbol.
                Defaults to None.
            locations (sequence of tuple or dict, optional): Multiple target locations.
                Each element can be a (lat, lon) tuple or a dict specifying
                `{'lat': ..., 'lon': ..., 'symbol': ..., 'color': ..., 'radius_degrees': ..., 'rotation_degrees': ...}`.
                Defaults to None.
            radius_degrees (float, optional): Angular radius of the symbol on the globe
                in degrees. Defaults to 2.5.
            color (str or sequence, optional): RGB color for vertices inside the symbol.
                Can be a color name, hex code, or 3-element sequence in [0, 1] or [0, 255].
                Defaults to 'red'.
            reference (str, optional): Coordinate reference system — ``'paleo'`` (default)
                or ``'modern'``. If ``'modern'`` and `age` is provided, coordinates are
                reconstructed using `plate_model`.
            age (float, optional): Geological age in Ma if `reference='modern'`. Defaults to None.
            plate_model (PlateModel, optional): Plate reconstruction model if `reference='modern'`.
                If None and `reference='modern'`, loads the default Scotese PALEOMAP model.
                Defaults to None.
            rotation_degrees (float, optional): In-plane rotation angle in degrees
                (positive rotates counter-clockwise in tangent plane). Defaults to 0.0.

        Raises:
            ValueError: If neither `lat`/`lon` nor `locations` is provided.
        """
        self.default_symbol = symbol
        self.default_radius_degrees = float(radius_degrees)
        self.default_color = color
        self.reference = reference.lower()
        self.age = age
        self.plate_model = plate_model
        self.default_rotation_degrees = float(rotation_degrees)

        if locations is not None:
            self.locations = list(locations)
        elif lat is not None and lon is not None:
            self.locations = [{
                "lat": float(lat),
                "lon": float(lon),
                "symbol": symbol,
                "color": color,
                "radius_degrees": self.default_radius_degrees,
                "rotation_degrees": self.default_rotation_degrees,
            }]
        else:
            raise ValueError("Either 'lat' and 'lon', or 'locations' must be provided to SymbolColourer.")

    def __call__(self, vertices: np.ndarray, current_colors: np.ndarray = None) -> np.ndarray:
        """Assigns symbol colors to vertices falling inside the projected boundaries.

        Args:
            vertices (np.ndarray): (N, 3) Cartesian vertex coordinates in mm.
            current_colors (np.ndarray, optional): (N, 3) existing vertex colors in [0, 1].
                If provided, existing colors outside the symbol are preserved. Defaults to None.

        Returns:
            np.ndarray: (N, 3) updated RGB vertex colors in range [0, 1].
        """
        n = vertices.shape[0]
        if current_colors is not None:
            colors = np.array(current_colors, dtype=np.float64, copy=True)
        else:
            colors = np.ones((n, 3), dtype=np.float64)

        if n == 0 or len(self.locations) == 0:
            return colors

        r = np.linalg.norm(vertices, axis=1)
        r_safe = np.where(r == 0.0, 1.0, r)
        u_v = vertices / r_safe[:, None]

        path_cache = {}

        pm = self.plate_model
        if self.reference == "modern" and self.age is not None and self.age != 0:
            if pm is None:
                from globe3d import datasets
                pm = datasets.paleo.scotese_plate_model()

        for loc in self.locations:
            if isinstance(loc, (tuple, list)):
                loc_lat, loc_lon = float(loc[0]), float(loc[1])
                loc_sym = self.default_symbol
                loc_col = self.default_color
                loc_rad = self.default_radius_degrees
                loc_rot = self.default_rotation_degrees
            elif isinstance(loc, dict):
                loc_lat = float(loc.get("lat", loc.get("latitude")))
                loc_lon = float(loc.get("lon", loc.get("longitude")))
                loc_sym = loc.get("symbol", self.default_symbol)
                loc_col = loc.get("color", self.default_color)
                loc_rad = float(loc.get("radius_degrees", loc.get("size", self.default_radius_degrees)))
                loc_rot = float(loc.get("rotation_degrees", self.default_rotation_degrees))
            else:
                continue

            if self.reference == "modern" and self.age is not None and self.age != 0 and pm is not None:
                rec_pt = pm.reconstruct_points([[loc_lat, loc_lon]], age_ma=float(self.age))
                center_lat = float(rec_pt[0, 0])
                center_lon = float(rec_pt[0, 1])
            else:
                center_lat = loc_lat
                center_lon = loc_lon

            cache_key = loc_sym if isinstance(loc_sym, str) else id(loc_sym)
            if cache_key not in path_cache:
                path_cache[cache_key] = _get_symbol_path(loc_sym)
            poly_path = path_cache[cache_key]

            col_rgb = _parse_color_float(loc_col)

            lat_r = np.radians(center_lat)
            lon_r = np.radians(center_lon)

            if center_lat >= 89.9999:
                c = np.array([0.0, 0.0, 1.0])
                ex = np.array([0.0, 1.0, 0.0])
                ey = np.array([-1.0, 0.0, 0.0])
            elif center_lat <= -89.9999:
                c = np.array([0.0, 0.0, -1.0])
                ex = np.array([0.0, 1.0, 0.0])
                ey = np.array([1.0, 0.0, 0.0])
            else:
                c = np.array([np.cos(lat_r) * np.cos(lon_r), np.cos(lat_r) * np.sin(lon_r), np.sin(lat_r)])
                ey = np.array([-np.sin(lat_r) * np.cos(lon_r), -np.sin(lat_r) * np.sin(lon_r), np.cos(lat_r)])
                ex = np.array([-np.sin(lon_r), np.cos(lon_r), 0.0])

            if loc_rot != 0.0:
                rot_rad = np.radians(loc_rot)
                cos_a, sin_a = np.cos(rot_rad), np.sin(rot_rad)
                ex_prime = cos_a * ex + sin_a * ey
                ey_prime = -sin_a * ex + cos_a * ey
                ex, ey = ex_prime, ey_prime

            theta_max_rad = np.radians(loc_rad)
            cos_cutoff = np.cos(theta_max_rad)
            cos_thetas = np.dot(u_v, c)
            cand_mask = cos_thetas >= cos_cutoff
            cand_indices = np.where(cand_mask)[0]

            if len(cand_indices) > 0:
                cos_cand = cos_thetas[cand_indices, None]
                p_tangent = (u_v[cand_indices] / cos_cand) - c[None, :]
                x_local = np.dot(p_tangent, ex)
                y_local = np.dot(p_tangent, ey)
                tan_theta = np.tan(theta_max_rad)
                if tan_theta > 1e-7:
                    u = x_local / tan_theta
                    v = y_local / tan_theta
                    inside = poly_path.contains_points(np.column_stack([u, v]))
                    if np.any(inside):
                        colors[cand_indices[inside]] = col_rgb

        return colors


class PoleLabelColourer(Colourer):
    """Assigns discrete colors to vertices at the North and/or South poles.

    Applies spherical tangent-plane projection for polar indicators (default 'N' at
    North Pole and 'S' at South Pole), completely eliminating equirectangular distortion
    and pole singularity artifacts.

    Args:
        radius_degrees (float, optional): Angular radius of the polar marker in degrees. Defaults to 3.0.
        north_color (str or sequence, optional): RGB color for North pole label. If None,
            North pole is not labeled. Defaults to 'red'.
        south_color (str or sequence, optional): RGB color for South pole label. If None,
            defaults to north_color. Defaults to None.
        north_symbol (str, optional): Symbol for North pole. Defaults to 'N'.
        south_symbol (str, optional): Symbol for South pole. Defaults to 'S'.
        reference (str, optional): Coordinate reference system ('paleo' or 'modern'). Defaults to 'paleo'.
        age (float, optional): Geological age in Ma if reference='modern'. Defaults to None.
        plate_model (PlateModel, optional): Plate reconstruction model if reference='modern'. Defaults to None.
        rotation_degrees (float, optional): In-plane rotation angle in degrees. Defaults to 0.0.
    """

    def __init__(
        self,
        radius_degrees: float = 3.0,
        north_color: Optional[Union[str, Sequence[Union[int, float]]]] = "red",
        south_color: Optional[Union[str, Sequence[Union[int, float]]]] = None,
        north_symbol: str = "N",
        south_symbol: str = "S",
        reference: str = "paleo",
        age: Optional[float] = None,
        plate_model: Optional[object] = None,
        rotation_degrees: float = 0.0,
    ):
        self.radius_degrees = float(radius_degrees)
        self.north_color = north_color
        self.south_color = south_color if south_color is not None else north_color
        self.north_symbol = north_symbol
        self.south_symbol = south_symbol
        self.reference = reference
        self.age = age
        self.plate_model = plate_model
        self.rotation_degrees = float(rotation_degrees)

    def __call__(self, vertices: np.ndarray, current_colors: np.ndarray = None) -> np.ndarray:
        colors = np.array(current_colors, dtype=np.float64, copy=True) if current_colors is not None else np.ones((len(vertices), 3), dtype=np.float64)

        if self.north_color is not None:
            c_north = SymbolColourer(
                symbol=self.north_symbol,
                lat=90.0,
                lon=0.0,
                radius_degrees=self.radius_degrees,
                color=self.north_color,
                reference=self.reference,
                age=self.age,
                plate_model=self.plate_model,
                rotation_degrees=self.rotation_degrees,
            )
            colors = c_north(vertices, current_colors=colors)

        if self.south_color is not None:
            c_south = SymbolColourer(
                symbol=self.south_symbol,
                lat=-90.0,
                lon=0.0,
                radius_degrees=self.radius_degrees,
                color=self.south_color,
                reference=self.reference,
                age=self.age,
                plate_model=self.plate_model,
                rotation_degrees=self.rotation_degrees,
            )
            colors = c_south(vertices, current_colors=colors)

        return colors


_TEXT_GEOM_CACHE: Dict[Tuple, Tuple[object, float]] = {}


def _get_text_normalized_geometry(
    text: str,
    font: Optional[str] = None,
    font_weight: str = "normal",
    font_style: str = "normal",
) -> Tuple[object, float]:
    """Extracts, validates, and normalizes text glyph paths into a centered Shapely geometry.

    Converts text characters to vector contours via Matplotlib TextPath, evaluates
    winding and nesting parity to cleanly differentiate glyph fills from inner holes
    (e.g. in '0', 'A', '8'), and scales the geometry to unit height centered at (0, 0).

    Args:
        text (str): String to convert into 2D polygon geometry.
        font (str, optional): TrueType/OpenType font file path (.ttf, .otf) or font family name.
        font_weight (str, optional): Font weight ('normal', 'bold'). Defaults to 'normal'.
        font_style (str, optional): Font style ('normal', 'italic'). Defaults to 'normal'.

    Returns:
        tuple: (norm_geom, max_r_norm) where `norm_geom` is a Shapely Polygon or
            MultiPolygon centered at (0, 0) with vertical height equal to 1.0,
            and `max_r_norm` is the maximum bounding radius from origin.
    """
    cache_key = (text, str(font), str(font_weight), str(font_style))
    if cache_key in _TEXT_GEOM_CACHE:
        return _TEXT_GEOM_CACHE[cache_key]

    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath
    import shapely.geometry as sgeom
    import shapely.ops as sops
    import shapely.affinity as saff

    if not text or not text.strip():
        empty_geom = sgeom.Polygon()
        _TEXT_GEOM_CACHE[cache_key] = (empty_geom, 1.0)
        return empty_geom, 1.0

    if font is not None:
        if os.path.isfile(font):
            fp = FontProperties(fname=font)
        else:
            fp = FontProperties(family=font, weight=font_weight, style=font_style)
    else:
        fp = FontProperties(family="sans-serif", weight=font_weight, style=font_style)

    tp = TextPath((0, 0), text, prop=fp)
    polys = tp.to_polygons()
    poly_objects = [sgeom.Polygon(p) for p in polys if len(p) >= 3]
    if not poly_objects:
        empty_geom = sgeom.Polygon()
        _TEXT_GEOM_CACHE[cache_key] = (empty_geom, 1.0)
        return empty_geom, 1.0

    outers = []
    holes = []
    for i, p in enumerate(poly_objects):
        pt = sgeom.Point(p.exterior.coords[0])
        depth = sum(1 for j, other in enumerate(poly_objects) if i != j and other.contains(pt))
        if depth % 2 == 0:
            outers.append(p)
        else:
            holes.append(p)

    geom = sops.unary_union(outers)
    if holes:
        geom = geom.difference(sops.unary_union(holes))

    if geom.is_empty:
        _TEXT_GEOM_CACHE[cache_key] = (geom, 1.0)
        return geom, 1.0

    minx, miny, maxx, maxy = geom.bounds
    dy = maxy - miny
    if dy < 1e-7:
        dy = 1.0
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0

    norm_geom = saff.translate(geom, xoff=-cx, yoff=-cy)
    norm_geom = saff.scale(norm_geom, xfact=1.0 / dy, yfact=1.0 / dy, origin=(0, 0))

    nb = norm_geom.bounds
    max_r_norm = float(np.hypot(max(abs(nb[0]), abs(nb[2])), max(abs(nb[1]), abs(nb[3]))))

    _TEXT_GEOM_CACHE[cache_key] = (norm_geom, max_r_norm)
    return norm_geom, max_r_norm


class TextColourer(Colourer):
    """Assigns discrete colors to vertices within 2D text strings projected onto the globe sphere.

    Renders text glyphs directly onto the spherical mesh using local gnomonic tangent-plane
    projection. This provides mathematically exact, singularity-free placement across all
    latitudes including the polar regions.

    Supports:
        - TrueType / OpenType font files (.ttf, .otf) or system font families.
        - Configurable text height in degrees on the spherical globe.
        - In-plane rotation angle (in degrees).
        - Direct fill and stroke styling with separate color assignments.
        - Center placement in either Paleo coordinates (default) or Modern geographic coordinates
          dynamically reconstructed to paleo coordinates using a PlateModel and age.
    """

    def __init__(
        self,
        text: str = "",
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        locations: Optional[Sequence[Union[Tuple[float, float], Dict]]] = None,
        height_degrees: float = 4.0,
        size_degrees: Optional[float] = None,
        angle: float = 0.0,
        rotation_degrees: Optional[float] = None,
        color: Union[str, Sequence[Union[int, float]], np.ndarray] = "white",
        fill: bool = True,
        fill_color: Optional[Union[str, Sequence[Union[int, float]], np.ndarray]] = None,
        stroke: Optional[Union[bool, float]] = None,
        stroke_width: Optional[float] = None,
        stroke_color: Union[str, Sequence[Union[int, float]], np.ndarray] = "black",
        font: Optional[str] = None,
        font_weight: str = "normal",
        font_style: str = "normal",
        reference: str = "paleo",
        age: Optional[float] = None,
        plate_model: Optional[object] = None,
    ):
        """Initializes a TextColourer.

        Args:
            text (str, optional): Text string to project onto the globe. Defaults to "".
            lat (float, optional): Center latitude in degrees for single-label placement. Defaults to None.
            lon (float, optional): Center longitude in degrees for single-label placement. Defaults to None.
            locations (sequence of tuple or dict, optional): Multiple target locations.
                Each element can be a `(lat, lon)` tuple or a dict overriding any label property
                (`'lat'`, `'lon'`, `'text'`, `'color'`, `'height_degrees'`, `'angle'`, `'fill'`,
                `'fill_color'`, `'stroke'`, `'stroke_width'`, `'stroke_color'`, `'font'`,
                `'font_weight'`, `'font_style'`). Defaults to None.
            height_degrees (float, optional): Angular height of the text in degrees. Defaults to 4.0.
            size_degrees (float, optional): Alias for `height_degrees`. Defaults to None.
            angle (float, optional): In-plane rotation angle in degrees (positive rotates counter-clockwise
                in the tangent plane). Defaults to 0.0.
            rotation_degrees (float, optional): Alias for `angle`. Defaults to None.
            color (str or sequence, optional): Text color. Defaults to "white".
            fill (bool, optional): Whether to fill the interior of the text glyphs. Defaults to True.
            fill_color (str or sequence, optional): Color for the glyph fill. If None,
                defaults to `color`. Defaults to None.
            stroke (bool or float, optional): Stroke outline toggle or width in degrees. If float,
                specifies stroke width in degrees. If True, enables stroke with default width
                (0.1 * height_degrees). If False or None (and `stroke_width` is None), stroke is
                disabled. Defaults to None.
            stroke_width (float, optional): Stroke outline width in degrees. If provided and `stroke`
                is not False, stroke is enabled. Defaults to None.
            stroke_color (str or sequence, optional): Color for the stroke outline. Defaults to "black".
            font (str, optional): Path to a TrueType / OpenType font file (.ttf / .otf) or a font
                family name (e.g. 'sans-serif', 'Arial', 'DejaVu Sans'). Defaults to None.
            font_weight (str, optional): Font weight (e.g. 'normal', 'bold'). Defaults to 'normal'.
            font_style (str, optional): Font style (e.g. 'normal', 'italic'). Defaults to 'normal'.
            reference (str, optional): Coordinate reference system — `'paleo'` (default) or `'modern'`.
                If `'modern'` and `age` is provided, coordinates are dynamically reconstructed using
                `plate_model`.
            age (float, optional): Geological age in Ma if `reference='modern'`. Defaults to None.
            plate_model (PlateModel, optional): Plate reconstruction model if `reference='modern'`.
                If None and `reference='modern'`, loads the default Scotese PALEOMAP model. Defaults to None.

        Raises:
            ValueError: If neither `lat`/`lon` nor `locations` is provided.
        """
        self.default_text = str(text)
        self.default_height_degrees = float(size_degrees if size_degrees is not None else height_degrees)
        self.default_angle = float(rotation_degrees if rotation_degrees is not None else angle)
        self.default_color = color
        self.default_fill = bool(fill)
        self.default_fill_color = fill_color if fill_color is not None else color
        self.default_stroke_color = stroke_color
        self.default_font = font
        self.default_font_weight = font_weight
        self.default_font_style = font_style
        self.reference = reference.lower()
        self.age = age
        self.plate_model = plate_model

        if stroke_width is not None:
            self.default_stroke_width = float(stroke_width)
            self.default_stroke_enabled = (stroke is not False)
        elif isinstance(stroke, (int, float)) and stroke > 0:
            self.default_stroke_width = float(stroke)
            self.default_stroke_enabled = True
        elif stroke is True:
            self.default_stroke_width = float(self.default_height_degrees) * 0.1
            self.default_stroke_enabled = True
        else:
            self.default_stroke_width = 0.0
            self.default_stroke_enabled = False

        if locations is not None:
            self.locations = list(locations)
        elif lat is not None and lon is not None:
            self.locations = [{
                "lat": float(lat),
                "lon": float(lon),
                "text": self.default_text,
                "color": self.default_color,
                "height_degrees": self.default_height_degrees,
                "angle": self.default_angle,
                "fill": self.default_fill,
                "fill_color": self.default_fill_color,
                "stroke": self.default_stroke_enabled,
                "stroke_width": self.default_stroke_width,
                "stroke_color": self.default_stroke_color,
                "font": self.default_font,
                "font_weight": self.default_font_weight,
                "font_style": self.default_font_style,
            }]
        else:
            raise ValueError("Either 'lat' and 'lon', or 'locations' must be provided to TextColourer.")

    def __call__(self, vertices: np.ndarray, current_colors: np.ndarray = None) -> np.ndarray:
        """Assigns text colors to mesh vertices falling inside the projected glyphs and strokes.

        Args:
            vertices (np.ndarray): (N, 3) Cartesian vertex coordinates in mm.
            current_colors (np.ndarray, optional): (N, 3) existing vertex colors in [0, 1].
                If provided, existing colors outside the text are preserved. Defaults to None.

        Returns:
            np.ndarray: (N, 3) updated RGB vertex colors in range [0, 1].
        """
        n = vertices.shape[0]
        if current_colors is not None:
            colors = np.array(current_colors, dtype=np.float64, copy=True)
        else:
            colors = np.ones((n, 3), dtype=np.float64)

        if n == 0 or len(self.locations) == 0:
            return colors

        import shapely
        import shapely.affinity as saff

        r = np.linalg.norm(vertices, axis=1)
        r_safe = np.where(r == 0.0, 1.0, r)
        u_v = vertices / r_safe[:, None]

        pm = self.plate_model
        if self.reference == "modern" and self.age is not None and self.age != 0:
            if pm is None:
                from globe3d import datasets
                pm = datasets.paleo.scotese_plate_model()

        for loc in self.locations:
            if isinstance(loc, (tuple, list)):
                loc_lat, loc_lon = float(loc[0]), float(loc[1])
                loc_text = self.default_text
                loc_h = self.default_height_degrees
                loc_ang = self.default_angle
                loc_fill = self.default_fill
                loc_fill_col = self.default_fill_color
                loc_stroke_on = self.default_stroke_enabled
                loc_stroke_w = self.default_stroke_width
                loc_stroke_col = self.default_stroke_color
                loc_font = self.default_font
                loc_font_w = self.default_font_weight
                loc_font_s = self.default_font_style
            elif isinstance(loc, dict):
                loc_lat = float(loc.get("lat", loc.get("latitude")))
                loc_lon = float(loc.get("lon", loc.get("longitude")))
                loc_text = str(loc.get("text", self.default_text))
                loc_h = float(loc.get("height_degrees", loc.get("size_degrees", self.default_height_degrees)))
                loc_ang = float(loc.get("angle", loc.get("rotation_degrees", self.default_angle)))
                loc_fill = bool(loc.get("fill", self.default_fill))
                loc_fill_col = loc.get("fill_color", loc.get("color", self.default_fill_color))
                loc_stroke_col = loc.get("stroke_color", self.default_stroke_color)
                loc_font = loc.get("font", self.default_font)
                loc_font_w = loc.get("font_weight", self.default_font_weight)
                loc_font_s = loc.get("font_style", self.default_font_style)

                loc_stroke_val = loc.get("stroke", None)
                loc_sw_val = loc.get("stroke_width", None)
                if loc_sw_val is not None:
                    loc_stroke_w = float(loc_sw_val)
                    loc_stroke_on = (loc_stroke_val is not False)
                elif isinstance(loc_stroke_val, (int, float)) and loc_stroke_val > 0:
                    loc_stroke_w = float(loc_stroke_val)
                    loc_stroke_on = True
                elif loc_stroke_val is True:
                    loc_stroke_w = float(loc_h) * 0.1
                    loc_stroke_on = True
                elif loc_stroke_val is False:
                    loc_stroke_w = 0.0
                    loc_stroke_on = False
                else:
                    loc_stroke_on = self.default_stroke_enabled
                    loc_stroke_w = self.default_stroke_width
            else:
                continue

            if not loc_text or (not loc_fill and not loc_stroke_on):
                continue

            norm_geom, max_r_norm = _get_text_normalized_geometry(
                loc_text, font=loc_font, font_weight=loc_font_w, font_style=loc_font_s
            )
            if norm_geom.is_empty:
                continue

            if self.reference == "modern" and self.age is not None and self.age != 0 and pm is not None:
                rec_pt = pm.reconstruct_points([[loc_lat, loc_lon]], age_ma=float(self.age))
                center_lat = float(rec_pt[0, 0])
                center_lon = float(rec_pt[0, 1])
            else:
                center_lat = loc_lat
                center_lon = loc_lon

            lat_r = np.radians(center_lat)
            lon_r = np.radians(center_lon)

            if center_lat >= 89.9999:
                c = np.array([0.0, 0.0, 1.0])
                ex = np.array([0.0, 1.0, 0.0])
                ey = np.array([-1.0, 0.0, 0.0])
            elif center_lat <= -89.9999:
                c = np.array([0.0, 0.0, -1.0])
                ex = np.array([0.0, 1.0, 0.0])
                ey = np.array([1.0, 0.0, 0.0])
            else:
                c = np.array([np.cos(lat_r) * np.cos(lon_r), np.cos(lat_r) * np.sin(lon_r), np.sin(lat_r)])
                ey = np.array([-np.sin(lat_r) * np.cos(lon_r), -np.sin(lat_r) * np.sin(lon_r), np.cos(lat_r)])
                ex = np.array([-np.sin(lon_r), np.cos(lon_r), 0.0])

            if loc_ang != 0.0:
                rot_rad = np.radians(loc_ang)
                cos_a, sin_a = np.cos(rot_rad), np.sin(rot_rad)
                ex_prime = cos_a * ex + sin_a * ey
                ey_prime = -sin_a * ex + cos_a * ey
                ex, ey = ex_prime, ey_prime

            H_tangent = np.tan(np.radians(loc_h))
            if H_tangent <= 1e-7:
                continue

            tangent_geom = saff.scale(norm_geom, xfact=H_tangent, yfact=H_tangent, origin=(0, 0))

            stroke_geom = None
            if loc_stroke_on and loc_stroke_w > 0:
                W_tangent = np.tan(np.radians(loc_stroke_w))
                if loc_fill:
                    stroke_geom = tangent_geom.buffer(W_tangent)
                    max_r = (max_r_norm * H_tangent) + W_tangent
                else:
                    stroke_geom = tangent_geom.boundary.buffer(W_tangent / 2.0)
                    max_r = (max_r_norm * H_tangent) + (W_tangent / 2.0)
            else:
                max_r = max_r_norm * H_tangent

            theta_max_rad = min(np.arctan(max_r) * 1.05, np.pi * 0.499)
            cos_cutoff = np.cos(theta_max_rad)
            cos_thetas = np.dot(u_v, c)
            cand_mask = cos_thetas >= cos_cutoff
            cand_indices = np.where(cand_mask)[0]

            if len(cand_indices) > 0:
                cos_cand = cos_thetas[cand_indices, None]
                p_tangent = (u_v[cand_indices] / cos_cand) - c[None, :]
                x_local = np.dot(p_tangent, ex)
                y_local = np.dot(p_tangent, ey)

                if stroke_geom is not None:
                    stroke_rgb = _parse_color_float(loc_stroke_col)
                    in_stroke = shapely.contains_xy(stroke_geom, x_local, y_local)
                    if np.any(in_stroke):
                        colors[cand_indices[in_stroke]] = stroke_rgb

                if loc_fill:
                    fill_rgb = _parse_color_float(loc_fill_col)
                    in_fill = shapely.contains_xy(tangent_geom, x_local, y_local)
                    if np.any(in_fill):
                        colors[cand_indices[in_fill]] = fill_rgb

        return colors


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
