"""Plate reconstruction module for the globe3d package.

This module integrates plate tectonic reconstruction capabilities using GPlately
and PyGPlates to reconstruct geographic points, vectors, and raster grids across
deep geological time.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple, Union, List
import numpy as np

try:
    import gplately
    import pygplates
except ImportError:
    gplately = None
    pygplates = None

from globe3d.grid import GeographicGrid


def _check_gplately():
    """Verifies that gplately and pygplates are installed."""
    if gplately is None or pygplates is None:
        raise ImportError(
            "Plate reconstruction requires 'gplately' and 'pygplates'. "
            "Please install them via Conda: conda install -c conda-forge gplately pygplates"
        )


class PlateModel:
    """Represents a plate tectonic reconstruction model.

    Wraps a GPlately PlateReconstruction object to manage rotation models,
    topological plate polygons, and static boundaries, facilitating point
    and raster reconstruction across geological time (Ma).

    Attributes:
        rotation_file (str): Path to the plate rotation model file (.rot).
        topology_file (str): Path to the plate boundary topologies (.gpml).
        static_polygons_file (str): Path to static plate polygons (.gpml).
        model (gplately.PlateReconstruction): Underlying GPlately reconstruction model.
        name (str): Identifying name for the plate model.
    """

    def __init__(
        self,
        rotation_file: str,
        topology_file: str,
        static_polygons_file: Optional[str] = None,
        name: str = "custom",
    ):
        """Initializes a PlateModel with rotation and boundary files.

        Args:
            rotation_file (str): Path to the rotation model file (.rot).
            topology_file (str): Path to topology features file (e.g., .gpml).
            static_polygons_file (str, optional): Path to static polygons file.
                If None, uses topology_file for static polygons. Defaults to None.
            name (str, optional): Human-readable name for the model. Defaults to 'custom'.

        Raises:
            ImportError: If gplately or pygplates is not installed.
            FileNotFoundError: If rotation or topology files do not exist.
        """
        _check_gplately()

        if not os.path.exists(rotation_file):
            raise FileNotFoundError(f"Rotation model file not found: {rotation_file}")
        if not os.path.exists(topology_file):
            raise FileNotFoundError(f"Topology features file not found: {topology_file}")

        self.rotation_file = rotation_file
        self.topology_file = topology_file
        self.static_polygons_file = static_polygons_file or topology_file
        self.name = name

        if not os.path.exists(self.static_polygons_file):
            raise FileNotFoundError(f"Static polygons file not found: {self.static_polygons_file}")

        self.model = gplately.PlateReconstruction(
            self.rotation_file,
            self.topology_file,
            self.static_polygons_file,
        )

    @classmethod
    def from_files(
        cls,
        rotation_file: str,
        topology_file: str,
        static_polygons_file: Optional[str] = None,
        name: str = "custom",
    ) -> PlateModel:
        """Loads a plate model from local rotation and topology files.

        Args:
            rotation_file (str): Path to the rotation file (.rot).
            topology_file (str): Path to the topology features file (.gpml).
            static_polygons_file (str, optional): Path to static polygons. Defaults to None.
            name (str, optional): Name of the model. Defaults to 'custom'.

        Returns:
            PlateModel: Initialized plate model.
        """
        return cls(
            rotation_file=rotation_file,
            topology_file=topology_file,
            static_polygons_file=static_polygons_file,
            name=name,
        )

    @classmethod
    def from_server(cls, model_name: str = "Muller2019") -> PlateModel:
        """Fetches and initializes a plate model from the GPlately DataServer.

        Args:
            model_name (str, optional): Name of the model on the data server
                (e.g., 'Muller2019', 'Merdith2021', 'Cao2020'). Defaults to 'Muller2019'.

        Returns:
            PlateModel: Initialized plate model downloaded from the data server.

        Raises:
            ImportError: If gplately is not installed.
        """
        _check_gplately()
        server = gplately.DataServer(model_name)
        rotation_file, topology_file, static_polygons_file = server.get_plate_reconstruction_files()

        return cls(
            rotation_file=rotation_file,
            topology_file=topology_file,
            static_polygons_file=static_polygons_file,
            name=model_name,
        )

    def reconstruct_points(
        self,
        points_lat_lon: Union[np.ndarray, List[Tuple[float, float]], Tuple[float, float]],
        age_ma: float,
    ) -> np.ndarray:
        """Reconstructs geographic points back to their paleo-positions at a given age.

        Args:
            points_lat_lon (array-like): (N, 2) array, list of (lat, lon) pairs,
                or a single (lat, lon) pair representing modern coordinates in degrees.
            age_ma (float): Reconstruction age in millions of years ago (Ma).

        Returns:
            np.ndarray: (N, 2) array of reconstructed [latitude, longitude] in degrees.

        Raises:
            ValueError: If points cannot be parsed into an (N, 2) coordinate array.
        """
        pts = np.asarray(points_lat_lon, dtype=np.float64)
        if pts.ndim == 1 and pts.shape[0] == 2:
            pts = pts.reshape(1, 2)
        elif pts.ndim != 2 or pts.shape[1] != 2:
            raise ValueError("points_lat_lon must be an (N, 2) array of [latitude, longitude].")

        lats_1d = pts[:, 0]
        lons_1d = pts[:, 1]

        # GPlately Points expects (plate_reconstruction, lons, lats)
        gpoints = gplately.Points(self.model, lons_1d, lats_1d)
        reconstructed = gpoints.reconstruct(time=float(age_ma))

        rec_lats = np.asarray(reconstructed.lats, dtype=np.float64)
        rec_lons = np.asarray(reconstructed.lons, dtype=np.float64)

        return np.column_stack((rec_lats, rec_lons))

    def reconstruct_grid(
        self,
        grid_data: Union[GeographicGrid, np.ndarray],
        age_ma: float,
        extent: Tuple[float, float, float, float] = (-180.0, 180.0, -90.0, 90.0),
        origin: str = "lower",
        fill_value: float = np.nan,
    ) -> Union[GeographicGrid, np.ndarray]:
        """Reconstructs a 2D scalar geographic grid to a specified geological age.

        Args:
            grid_data (GeographicGrid or np.ndarray): Modern raster grid to reconstruct.
                If GeographicGrid, respects its latitude and longitude axes.
            age_ma (float): Geological reconstruction age in millions of years (Ma).
            extent (tuple, optional): Geographic extent (min_lon, max_lon, min_lat, max_lat).
                Defaults to (-180.0, 180.0, -90.0, 90.0).
            origin (str, optional): Vertical raster origin, 'lower' or 'upper'. Defaults to 'lower'.
            fill_value (float, optional): Fill value for unassigned or masked regions. Defaults to np.nan.

        Returns:
            GeographicGrid or np.ndarray: Reconstructed grid in the same type as input.
        """
        is_geographic_grid = isinstance(grid_data, GeographicGrid)

        if is_geographic_grid:
            raw_grid = grid_data.grid
            lats = grid_data.lats
            lons = grid_data.lons
            grid_extent = (float(lons.min()), float(lons.max()), float(lats.min()), float(lats.max()))
        else:
            raw_grid = np.asarray(grid_data)
            grid_extent = extent

        modern_raster = gplately.Raster(
            data=raw_grid,
            plate_reconstruction=self.model,
            extent=grid_extent,
            origin=origin,
        )

        partitioning_features = self.model.topology_features or self.model.static_polygons
        reconstructed_raster = modern_raster.reconstruct(
            time=float(age_ma),
            partitioning_features=partitioning_features,
        )

        data = reconstructed_raster.data
        if isinstance(data, np.ma.MaskedArray):
            reconstructed_array = data.filled(fill_value)
        else:
            reconstructed_array = np.asarray(data)

        if is_geographic_grid:
            return GeographicGrid(lats=grid_data.lats, lons=grid_data.lons, grid=reconstructed_array)
        return reconstructed_array


def reconstruct_points(
    points_lat_lon: Union[np.ndarray, List[Tuple[float, float]], Tuple[float, float]],
    plate_model: PlateModel,
    age_ma: float,
) -> np.ndarray:
    """Functional interface to reconstruct geographic points to a given geological time.

    Args:
        points_lat_lon (array-like): (N, 2) array or sequence of [latitude, longitude].
        plate_model (PlateModel): Loaded plate reconstruction model.
        age_ma (float): Reconstruction age in millions of years (Ma).

    Returns:
        np.ndarray: (N, 2) array of reconstructed [latitude, longitude].
    """
    if not isinstance(plate_model, PlateModel):
        raise TypeError("plate_model must be an instance of PlateModel.")
    return plate_model.reconstruct_points(points_lat_lon, age_ma)


def reconstruct_grid(
    grid_data: Union[GeographicGrid, np.ndarray],
    plate_model: PlateModel,
    age_ma: float,
    extent: Tuple[float, float, float, float] = (-180.0, 180.0, -90.0, 90.0),
    origin: str = "lower",
    fill_value: float = np.nan,
) -> Union[GeographicGrid, np.ndarray]:
    """Functional interface to reconstruct a geographic raster grid to a given geological time.

    Args:
        grid_data (GeographicGrid or np.ndarray): Modern grid dataset.
        plate_model (PlateModel): Loaded plate reconstruction model.
        age_ma (float): Reconstruction age in millions of years (Ma).
        extent (tuple, optional): Geographic extent (min_lon, max_lon, min_lat, max_lat).
            Defaults to (-180.0, 180.0, -90.0, 90.0).
        origin (str, optional): Vertical origin ('lower' or 'upper'). Defaults to 'lower'.
        fill_value (float, optional): Value for empty regions. Defaults to np.nan.

    Returns:
        GeographicGrid or np.ndarray: Reconstructed raster grid.
    """
    if not isinstance(plate_model, PlateModel):
        raise TypeError("plate_model must be an instance of PlateModel.")
    return plate_model.reconstruct_grid(
        grid_data=grid_data,
        age_ma=age_ma,
        extent=extent,
        origin=origin,
        fill_value=fill_value,
    )
