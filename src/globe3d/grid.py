"""Grid loading module for the globe3d package.

This module provides the GeographicGrid class to load, validate, and manage
geographic grid data (elevation, seismic velocity anomaly, etc.) from NetCDF
and TIFF files.
"""

import numpy as np
from netCDF4 import Dataset

try:
    import rasterio
except ImportError:
    rasterio = None


class GeographicGrid:
    """Represents a geographic grid dataset with latitudes, longitudes, and values.

    Attributes:
        lats (numpy.ndarray): 1D array of latitude coordinates in degrees, sorted ascending.
        lons (numpy.ndarray): 1D array of longitude coordinates in degrees, sorted ascending.
        grid (numpy.ndarray): 2D array of grid values of shape (len(lats), len(lons)).
    """

    def __init__(self, lats, lons, grid):
        """Initializes a GeographicGrid with latitudes, longitudes, and a data grid.

        Coordinates are automatically sorted ascending to satisfy interpolation
        requirements, and the data grid is permuted accordingly.

        Args:
            lats (array-like): 1D array of latitude coordinates.
            lons (array-like): 1D array of longitude coordinates.
            grid (array-like): 2D array of grid values.

        Raises:
            ValueError: If input dimensions are incorrect, or if grid shape does not
                match latitudes and longitudes, or if coordinates have duplicate values.
        """
        self.lats = np.asarray(lats, dtype=np.float64)
        self.lons = np.asarray(lons, dtype=np.float64)
        self.grid = np.asarray(grid, dtype=np.float64)

        if self.lats.ndim != 1:
            raise ValueError("Latitudes must be a 1D array.")
        if self.lons.ndim != 1:
            raise ValueError("Longitudes must be a 1D array.")
        if self.grid.ndim != 2:
            raise ValueError("Grid must be a 2D array.")

        if self.grid.shape != (len(self.lats), len(self.lons)):
            raise ValueError(
                f"Grid shape {self.grid.shape} does not match (len(lats), len(lons)) "
                f"which is ({len(self.lats)}, {len(self.lons)})."
            )

        # Handle duplicate values (not allowed for interpolator)
        if len(self.lats) > 1 and len(np.unique(self.lats)) != len(self.lats):
            raise ValueError("Latitudes must not contain duplicate values.")
        if len(self.lons) > 1 and len(np.unique(self.lons)) != len(self.lons):
            raise ValueError("Longitudes must not contain duplicate values.")

        # Sort latitudes ascending and rearrange grid
        if len(self.lats) > 1 and not np.all(np.diff(self.lats) > 0):
            idx = np.argsort(self.lats)
            self.lats = self.lats[idx]
            self.grid = self.grid[idx, :]

        # Sort longitudes ascending and rearrange grid
        if len(self.lons) > 1 and not np.all(np.diff(self.lons) > 0):
            idx = np.argsort(self.lons)
            self.lons = self.lons[idx]
            self.grid = self.grid[:, idx]

    @classmethod
    def from_netcdf(cls, filename, lat_var='lat', lon_var='lon', data_var='z'):
        """Loads a geographic grid from a NetCDF file.

        Args:
            filename (str): Path to the NetCDF file.
            lat_var (str, optional): Variable name for latitude. Defaults to 'lat'.
            lon_var (str, optional): Variable name for longitude. Defaults to 'lon'.
            data_var (str, optional): Variable name for data value. Defaults to 'z'.

        Returns:
            GeographicGrid: An instance of GeographicGrid.
        """
        ds = Dataset(filename)
        lats = np.array(ds.variables[lat_var][:])
        lons = np.array(ds.variables[lon_var][:])
        grid = np.array(ds.variables[data_var][:])
        ds.close()
        return cls(lats, lons, grid)

    @classmethod
    def from_tiff(cls, filename):
        """Loads a geographic grid from a single-channel TIFF image in an equirectangular projection.

        The image is assumed to span -180 to 180 in longitude and 90 to -90 in latitude.

        Args:
            filename (str): Path to the TIFF file.

        Returns:
            GeographicGrid: An instance of GeographicGrid.

        Raises:
            ImportError: If rasterio is not installed.
        """
        if rasterio is None:
            raise ImportError("Rasterio is required for reading TIFF files. Please install it.")

        with rasterio.open(filename) as src:
            grid = src.read(1)
            height, width = grid.shape
            lats = np.linspace(90, -90, height)
            lons = np.linspace(-180, 180, width)
        return cls(lats, lons, grid)

    @staticmethod
    def list_netcdf_variables(filename):
        """Lists variable names in a NetCDF file.

        Args:
            filename (str): Path to the NetCDF file.

        Returns:
            list: A list containing the names of the variables in the NetCDF file.
        """
        with Dataset(filename, 'r') as ds:
            variable_names = list(ds.variables.keys())
        return variable_names
