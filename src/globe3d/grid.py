import numpy as np
from netCDF4 import Dataset

try:
    import rasterio
except ImportError:
    rasterio = None


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


def load_netcdf_grid(filename, lat_var='lat', lon_var='lon', data_var='z'):
    """Loads a grid from a NetCDF file.

    Assumes the latitudes and longitudes are in WGS84.

    Args:
        filename (str): Path to the NetCDF file.
        lat_var (str, optional): Variable name for latitude. Defaults to 'lat'.
        lon_var (str, optional): Variable name for longitude. Defaults to 'lon'.
        data_var (str, optional): Variable name for data value. Defaults to 'z'.

    Returns:
        tuple: A tuple containing:
            - lats (numpy.ndarray): 1D array of latitude coordinates.
            - lons (numpy.ndarray): 1D array of longitude coordinates.
            - grid (numpy.ndarray): 2D array of grid values.
    """
    ds = Dataset(filename)
    lats = np.array(ds.variables[lat_var][:])
    lons = np.array(ds.variables[lon_var][:])
    grid = np.array(ds.variables[data_var][:])
    ds.close()
    return lats, lons, grid


def load_tiff_grid(filename):
    """Loads a single-channel TIFF image in an equirectangular projection.

    The image is assumed to span -180 to 180 in longitude and 90 to -90 in latitude.

    Args:
        filename (str): Path to the TIFF file.

    Returns:
        tuple: A tuple containing:
            - lats (numpy.ndarray): 1D array of latitude coordinates.
            - lons (numpy.ndarray): 1D array of longitude coordinates.
            - grid (numpy.ndarray): 2D array of grid values.

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
    return lats, lons, grid
