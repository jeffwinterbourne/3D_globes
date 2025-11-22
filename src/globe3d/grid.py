import numpy as np
from netCDF4 import Dataset
try:
    import rasterio
except ImportError:
    rasterio = None

def list_netcdf_variables(filename):
    """
    Lists variable names in a NetCDF file.

    Parameters:
        filename (str): Path to the NetCDF file.

    Returns:
        list: A list containing the names of the variables in the NetCDF file.
    """
    with Dataset(filename, 'r') as ds:
        variable_names = list(ds.variables.keys())
    return variable_names
    

def load_netcdf_grid(filename, lat_var='lat', lon_var='lon', data_var='z'):
    """
    Loads a grid from a NetCDF file. Assumes the latitudes and longitudes are in WGS84.

    Parameters:
      filename (str): Path to the NetCDF file.
      lat_var, lon_var, data_var (str): Variable names in the file.
    
    Returns:
      lats (1D numpy array), lons (1D numpy array), grid (2D numpy array)
    """
    ds = Dataset(filename)
    lats = np.array(ds.variables[lat_var][:])
    lons = np.array(ds.variables[lon_var][:])
    grid = np.array(ds.variables[data_var][:])
    ds.close()
    return lats, lons, grid


def load_tiff_grid(filename):
    """
    Loads a single-channel 16-bit TIFF image assumed to be in an equirectangular projection.
    The full image is treated as spanning -180 to 180 in longitude and 90 to -90 in latitude.
    
    Parameters:
      filename (str): Path to the TIFF file.
    
    Returns:
      lats (1D numpy array), lons (1D numpy array), grid (2D numpy array)
    """
    if rasterio is None:
        raise ImportError("Rasterio is required for reading TIFF files. Please install it.")
    
    with rasterio.open(filename) as src:
        grid = src.read(1)  # Read first band
        height, width = grid.shape
        # Generate latitude from 90 to -90 and longitude from -180 to 180.
        lats = np.linspace(90, -90, height)
        lons = np.linspace(-180, 180, width)
    return lats, lons, grid
