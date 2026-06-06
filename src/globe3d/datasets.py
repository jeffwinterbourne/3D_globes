"""Datasets module for the globe3d package.

This module provides fetching, caching, and preprocessing capabilities for several
standard global geophysical datasets, including Earth, Mars, the Moon, and Venus.
"""

import os
import csv
import zipfile
import tarfile
import tempfile
import urllib.request
import numpy as np
from netCDF4 import Dataset
from tqdm import tqdm
from globe3d.grid import GeographicGrid

try:
    import rasterio
    from rasterio.enums import Resampling
except ImportError:
    rasterio = None


def _get_cache_dir(cache_dir=None):
    """Determines the download cache directory path.

    Args:
        cache_dir (str, optional): Custom cache directory. Defaults to None.

    Returns:
        str: Absolute path to the cache directory.
    """
    if cache_dir is not None:
        return os.path.abspath(cache_dir)
    # Default to .download_cache in the repository root
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, ".download_cache")


def _download_file(url, filename, cache_dir):
    """Downloads a file from a URL to the cache directory with progress bar and custom UA.

    Args:
        url (str): The source URL to download.
        filename (str): The local name of the file to save.
        cache_dir (str): The directory to save the file in.

    Returns:
        str: Absolute path to the downloaded file.

    Raises:
        urllib.error.URLError: If the download fails.
    """
    os.makedirs(cache_dir, exist_ok=True)
    filepath = os.path.join(cache_dir, filename)

    # Check if file already exists and is non-empty
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return filepath

    # Set up Request with User-Agent to avoid 403 Forbidden errors
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    
    # Download with progress bar
    try:
        with urllib.request.urlopen(req) as response:
            total_size = int(response.headers.get("content-length", 0))
            block_size = 8192
            
            with open(filepath, "wb") as f:
                with tqdm(total=total_size, unit="B", unit_scale=True, desc=filename) as pbar:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        f.write(buffer)
                        pbar.update(len(buffer))
    except Exception as e:
        # Clean up partial download if failed
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        raise e

    return filepath


def _load_netcdf_grid(filepath, lat_var=None, lon_var=None, data_var=None):
    """Loads a 2D geographic grid from a NetCDF file, automatically detecting variables.

    Args:
        filepath (str): Path to the NetCDF file.
        lat_var (str, optional): Variable name for latitude. Defaults to None.
        lon_var (str, optional): Variable name for longitude. Defaults to None.
        data_var (str, optional): Variable name for grid data. Defaults to None.

    Returns:
        GeographicGrid: Loaded geographic grid.
    """
    with Dataset(filepath, "r") as ds:
        # Detect latitude variable
        if lat_var is None:
            for candidate in ["lat", "latitude", "y"]:
                if candidate in ds.variables:
                    lat_var = candidate
                    break
        if lat_var is None:
            raise ValueError(f"Could not automatically detect latitude variable. Available: {list(ds.variables.keys())}")

        # Detect longitude variable
        if lon_var is None:
            for candidate in ["lon", "longitude", "x"]:
                if candidate in ds.variables:
                    lon_var = candidate
                    break
        if lon_var is None:
            raise ValueError(f"Could not automatically detect longitude variable. Available: {list(ds.variables.keys())}")

        # Detect data variable
        if data_var is None:
            for candidate in ["z", "v", "bouguer", "dvs", "dvs_percent"]:
                if candidate in ds.variables:
                    data_var = candidate
                    break
        if data_var is None:
            for name, var in ds.variables.items():
                if name not in [lat_var, lon_var] and len(var.shape) >= 2:
                    data_var = name
                    break
        if data_var is None:
            raise ValueError(f"Could not automatically detect data variable. Available: {list(ds.variables.keys())}")

        lats = np.array(ds.variables[lat_var][:])
        lons = np.array(ds.variables[lon_var][:])
        grid = np.array(ds.variables[data_var][:])

        if grid.ndim == 3:
            raise ValueError(f"NetCDF grid is 3D with shape {grid.shape}. Please slice it first.")

        return GeographicGrid(lats, lons, grid)


def _load_tiff_grid(filepath, downsample_factor=1):
    """Loads a single-channel TIFF image using rasterio with optional downsampling.

    Args:
        filepath (str): Path to the GeoTIFF file.
        downsample_factor (int, optional): Decimation factor for resolution reduction. Defaults to 1.

    Returns:
        GeographicGrid: Loaded geographic grid.

    Raises:
        ImportError: If rasterio is not installed.
    """
    if rasterio is None:
        raise ImportError("rasterio is required for loading TIFF files. Please install it.")

    with rasterio.open(filepath) as src:
        if downsample_factor <= 1:
            grid = src.read(1)
            height, width = grid.shape
        else:
            new_height = int(src.height // downsample_factor)
            new_width = int(src.width // downsample_factor)
            grid = src.read(
                1,
                out_shape=(new_height, new_width),
                resampling=Resampling.bilinear
            )
            height, width = new_height, new_width

        # Retrieve geographic bounds if available, fallback to global bounds
        bounds = src.bounds
        if bounds and not (bounds.left == 0.0 and bounds.right == 1.0 and bounds.bottom == 0.0 and bounds.top == 1.0):
            lats = np.linspace(bounds.top, bounds.bottom, height)
            lons = np.linspace(bounds.left, bounds.right, width)
        else:
            lats = np.linspace(90, -90, height)
            lons = np.linspace(-180, 180, width)

    return GeographicGrid(lats, lons, grid)


def s40rts(depth=2850.0, cache_dir=None, url=None):
    """Fetches and loads a 2D depth slice of the S40RTS seismic tomography model.

    Args:
        depth (float, optional): The depth in km to slice the model at. Defaults to 2850.0.
        cache_dir (str, optional): Custom cache directory. Defaults to None.
        url (str, optional): Custom URL to download S40RTS.nc from. Defaults to None.

    Returns:
        GeographicGrid: Loaded 2D seismic tomography velocity perturbation slice.
    """
    cache_dir = _get_cache_dir(cache_dir)
    filename = "S40RTS_dvs.nc"

    # Default URLs (using working raw GitHub mirror as primary due to official 404)
    primary_url = url or "https://raw.githubusercontent.com/shuleyu/seismic-tomography-models/master/S40RTS_dvs.nc"
    fallback_url = "http://ds.iris.edu/files/emc/models/S40RTS.nc"

    try:
        filepath = _download_file(primary_url, filename, cache_dir)
    except Exception:
        # Fall back to official URL if custom/mirror fails
        filepath = _download_file(fallback_url, filename, cache_dir)

    with Dataset(filepath, "r") as ds:
        # S40RTS.nc standard variables are 'depth', 'latitude', 'longitude', 'v'
        depths = np.array(ds.variables["depth"][:])
        lats = np.array(ds.variables["latitude"][:])
        lons = np.array(ds.variables["longitude"][:])
        
        # Find closest depth index
        depth_idx = np.argmin(np.abs(depths - depth))
        grid = np.array(ds.variables["v"][depth_idx, :, :])

    return GeographicGrid(lats, lons, grid)


def egm2008(downsample_factor=5, cache_dir=None, url=None):
    """Fetches and loads the EGM2008 Geoid Undulation dataset.

    Args:
        downsample_factor (int, optional): Resolution decimation factor. Defaults to 5.
        cache_dir (str, optional): Custom cache directory. Defaults to None.
        url (str, optional): Custom download URL. Defaults to None.

    Returns:
        GeographicGrid: Loaded global geoid undulation model.
    """
    cache_dir = _get_cache_dir(cache_dir)
    filename = "us_nga_egm2008_1.tif"
    url = url or "https://s3-eu-west-1.amazonaws.com/download.agisoft.com/gtg/us_nga_egm2008_1.tif"

    filepath = _download_file(url, filename, cache_dir)
    return _load_tiff_grid(filepath, downsample_factor=downsample_factor)


def dynamic_topography(grid_step=1.0, cache_dir=None, url=None):
    """Fetches, parses, and grids the Hoggard et al. (2016) Dynamic Topography spot data.

    Args:
        grid_step (float, optional): Spacing of the global interpolation grid in degrees. Defaults to 1.0.
        cache_dir (str, optional): Custom cache directory. Defaults to None.
        url (str, optional): Custom download URL. Defaults to None.

    Returns:
        GeographicGrid: Standardized interpolated global dynamic topography grid.
    """
    cache_dir = _get_cache_dir(cache_dir)
    
    # Default to spot.dat because the user's requested CSV URL returns a 404
    filename = "spot.dat" if not url else "Hoggard_etal_2016_Residual_Topography.csv"
    primary_url = url or "https://raw.githubusercontent.com/drhodrid/Davies_etal_NGeo_2019_Datasets/master/hoggard/spot.dat"
    fallback_url = "https://raw.githubusercontent.com/drhodrid/Davies_etal_NGeo_2019_Datasets/master/Observations/Hoggard_etal_2016/Hoggard_etal_2016_Residual_Topography.csv"

    try:
        filepath = _download_file(primary_url, filename, cache_dir)
    except Exception:
        filepath = _download_file(fallback_url, filename, cache_dir)

    # Parse latitude, longitude, and values (residual topography)
    raw_lats = []
    raw_lons = []
    raw_vals = []

    with open(filepath, "r", encoding="utf-8") as f:
        first_line = f.readline()
        f.seek(0)
        
        # Detect delimiter: CSV vs space-separated DAT
        if "," in first_line:
            reader = csv.reader(f)
            # Check for header
            header = next(reader)
            lat_col, lon_col, val_col = 0, 1, 2
            
            # Map column names if headers exist
            for idx, h in enumerate(header):
                hl = h.lower()
                if "lat" in hl:
                    lat_col = idx
                elif "lon" in hl or "lng" in hl:
                    lon_col = idx
                elif "res" in hl or "topo" in hl or "value" in hl or "anomaly" in hl:
                    val_col = idx
            
            for row in reader:
                if len(row) > max(lat_col, lon_col, val_col):
                    try:
                        raw_lats.append(float(row[lat_col]))
                        raw_lons.append(float(row[lon_col]))
                        raw_vals.append(float(row[val_col]))
                    except ValueError:
                        continue
        else:
            # Space-separated file: spot.dat has columns (lat, lon, value_in_km, uncertainty)
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 3:
                    try:
                        raw_lats.append(float(parts[0]))
                        raw_lons.append(float(parts[1]))
                        # spot.dat values are in km, convert to meters
                        raw_vals.append(float(parts[2]) * 1000.0)
                    except ValueError:
                        continue

    # Setup interpolation target grid
    import scipy.interpolate
    target_lats = np.arange(-90, 90 + grid_step, grid_step)
    target_lons = np.arange(-180, 180 + grid_step, grid_step)
    lon_mesh, lat_mesh = np.meshgrid(target_lons, target_lats)

    # Grid the data using SciPy linear interpolation
    points = np.column_stack((raw_lons, raw_lats))
    grid_val = scipy.interpolate.griddata(
        points, np.array(raw_vals), (lon_mesh, lat_mesh), method="linear"
    )

    # Fill NaNs outside the convex hull using nearest neighbor interpolation
    if np.any(np.isnan(grid_val)):
        grid_val_nearest = scipy.interpolate.griddata(
            points, np.array(raw_vals), (lon_mesh, lat_mesh), method="nearest"
        )
        grid_val[np.isnan(grid_val)] = grid_val_nearest[np.isnan(grid_val)]

    return GeographicGrid(target_lats, target_lons, grid_val)


def crust1(layer="moho", as_meters=True, cache_dir=None, url=None):
    """Fetches and parses the CRUST1.0 global 1x1 degree crustal boundaries database.

    Args:
        layer (str or int, optional): Layer index (0-8) or name: "surface", "water_bottom", "ice_bottom", "moho". Defaults to "moho".
        as_meters (bool, optional): Converts layer values from km to meters. Defaults to True.
        cache_dir (str, optional): Custom cache directory. Defaults to None.
        url (str, optional): Custom download URL. Defaults to None.

    Returns:
        GeographicGrid: Grid representing the requested crustal boundary.
    """
    cache_dir = _get_cache_dir(cache_dir)
    filename = "crust1.0.tar.gz"
    url = url or "https://igppweb.ucsd.edu/~gabi/crust1/crust1.0.tar.gz"

    filepath = _download_file(url, filename, cache_dir)

    # Resolve layer index
    layer_map = {
        "surface": 0,
        "topography": 0,
        "water_bottom": 1,
        "bathymetry": 1,
        "ice_bottom": 2,
        "upper_sediment_bottom": 3,
        "middle_sediment_bottom": 4,
        "lower_sediment_bottom": 5,
        "upper_crust_bottom": 6,
        "middle_crust_bottom": 7,
        "moho": 8,
        "lower_crust_bottom": 8,
    }

    if isinstance(layer, str):
        layer_idx = layer_map.get(layer.lower())
        if layer_idx is None:
            raise ValueError(f"Invalid layer name. Choose from: {list(layer_map.keys())}")
    else:
        layer_idx = int(layer)
        if not (0 <= layer_idx <= 8):
            raise ValueError("Layer index must be between 0 and 8.")

    # Extract and parse crust1.bnds in memory
    with tarfile.open(filepath, "r:gz") as tar:
        f = tar.extractfile("crust1.bnds")
        if f is None:
            raise ValueError("Could not find crust1.bnds in CRUST1.0 tarball.")
        raw_data = np.loadtxt(f)

    # crust1.bnds has 64800 rows representing a 180x360 grid (1x1 degree).
    # Rows are ordered from 89.5 N down to -89.5 N (descending).
    # Longitudes are from -179.5 to 179.5 (ascending).
    grid = raw_data[:, layer_idx].reshape((180, 360))

    # Reverse latitude rows to match GeographicGrid sorted-ascending requirement
    grid = np.flipud(grid)
    lats = np.linspace(-89.5, 89.5, 180)
    lons = np.linspace(-179.5, 179.5, 360)

    if as_meters:
        # Convert km to meters
        grid = grid * 1000.0

    return GeographicGrid(lats, lons, grid)


def gravity(cache_dir=None, url=None):
    """Fetches and loads the global Gravity Bouguer Anomaly grid from NOAA.

    Args:
        cache_dir (str, optional): Custom cache directory. Defaults to None.
        url (str, optional): Custom download URL. Defaults to None.

    Returns:
        GeographicGrid: Loaded Bouguer anomaly gravity grid.
    """
    cache_dir = _get_cache_dir(cache_dir)
    filename = "bouguer_anomaly.nc"
    url = url or "https://coastwatch.pfeg.noaa.gov/erddap/griddap/hawaii_soest_7386_62c6_9d63.nc?bouguer[(-89.9):1:(89.9)][(-179.9):1:(179.9)]"

    filepath = _download_file(url, filename, cache_dir)
    return _load_netcdf_grid(filepath)


def magnetics(downsample_factor=5, cache_dir=None, url=None):
    """Fetches and loads the EMAG2v3 global magnetic anomalies grid.

    Args:
        downsample_factor (int, optional): Resolution decimation factor. Defaults to 5.
        cache_dir (str, optional): Custom cache directory. Defaults to None.
        url (str, optional): Custom download URL. Defaults to None.

    Returns:
        GeographicGrid: Loaded magnetic anomalies grid.
    """
    cache_dir = _get_cache_dir(cache_dir)
    filename = "EMAG2_V3_Upward_Continued_GeoTIFF.zip"
    url = url or "https://www.ngdc.noaa.gov/mgg/geology/data/magnetic_anomalies/EMAG2/EMAG2_v3/EMAG2_V3_Upward_Continued_GeoTIFF.zip"

    filepath = _download_file(url, filename, cache_dir)

    # Extract the GeoTIFF to a temporary directory
    with zipfile.ZipFile(filepath, "r") as zip_ref:
        tif_files = [f for f in zip_ref.namelist() if f.lower().endswith(".tif")]
        if not tif_files:
            raise ValueError("No GeoTIFF found inside EMAG2v3 zip archive.")
        
        temp_dir = tempfile.mkdtemp()
        extracted_path = zip_ref.extract(tif_files[0], temp_dir)

    try:
        grid = _load_tiff_grid(extracted_path, downsample_factor=downsample_factor)
    finally:
        # Clean up extracted file
        try:
            os.remove(extracted_path)
            os.rmdir(temp_dir)
        except OSError:
            pass

    return grid


def mars(resolution="30m", cache_dir=None, url=None):
    """Fetches and loads Mars topography data.

    Defaults to a fast-loading, low-resolution 30 arc-minute grid from the GMT remote server.
    If resolution="high", downloads the full-resolution MOLA DEM GeoTIFF from USGS.

    Args:
        resolution (str, optional): Resolution of the grid. Can be "30m" (default), "10m", "05m", "01d", or "high". Defaults to "30m".
        cache_dir (str, optional): Custom cache directory. Defaults to None.
        url (str, optional): Custom download URL. Defaults to None.

    Returns:
        GeographicGrid: Loaded Mars topography grid.
    """
    cache_dir = _get_cache_dir(cache_dir)

    if resolution == "high":
        filename = "Mars_MGS_MOLA_DEM_mosaic_global_463m.tif"
        download_url = url or "https://astropedia.astrogeology.usgs.gov/download/Mars/GlobalSurveyor/MOLA/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif"
        filepath = _download_file(download_url, filename, cache_dir)
        # Force a default downsampling of 20 for full-res files to avoid OOM
        return _load_tiff_grid(filepath, downsample_factor=20)
    else:
        # Download low/medium resolution NetCDF from GMT remote data server
        filename = f"mars_relief_{resolution}_g.grd"
        download_url = url or f"https://oceania.generic-mapping-tools.org/server/mars/mars_relief/mars_relief_{resolution}_g.grd"
        filepath = _download_file(download_url, filename, cache_dir)
        return _load_netcdf_grid(filepath)


def moon(resolution="30m", cache_dir=None, url=None):
    """Fetches and loads Moon topography data.

    Defaults to a fast-loading, low-resolution 30 arc-minute grid from the GMT remote server.
    If resolution="high", downloads the full-resolution LRO LOLA DEM GeoTIFF from USGS.

    Args:
        resolution (str, optional): Resolution of the grid. Can be "30m" (default), "10m", "05m", "01d", or "high". Defaults to "30m".
        cache_dir (str, optional): Custom cache directory. Defaults to None.
        url (str, optional): Custom download URL. Defaults to None.

    Returns:
        GeographicGrid: Loaded Moon topography grid.
    """
    cache_dir = _get_cache_dir(cache_dir)

    if resolution == "high":
        filename = "Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif"
        download_url = url or "https://planetarymaps.usgs.gov/mosaic/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif"
        filepath = _download_file(download_url, filename, cache_dir)
        # Force a default downsampling of 50 for the massive 8GB lunar file to avoid OOM
        return _load_tiff_grid(filepath, downsample_factor=50)
    else:
        # Download low/medium resolution NetCDF from GMT remote data server
        filename = f"moon_relief_{resolution}_g.grd"
        download_url = url or f"https://oceania.generic-mapping-tools.org/server/moon/moon_relief/moon_relief_{resolution}_g.grd"
        filepath = _download_file(download_url, filename, cache_dir)
        return _load_netcdf_grid(filepath)


def venus(resolution="30m", cache_dir=None, url=None):
    """Fetches and loads Venus topography data.

    Defaults to a fast-loading, low-resolution 30 arc-minute grid from the GMT remote server.
    If resolution="high", downloads the Magellan GTDR NetCDF topography grid.

    Args:
        resolution (str, optional): Resolution of the grid. Can be "30m" (default), "10m", "05m", "01d", or "high". Defaults to "30m".
        cache_dir (str, optional): Custom cache directory. Defaults to None.
        url (str, optional): Custom download URL. Defaults to None.

    Returns:
        GeographicGrid: Loaded Venus topography grid.
    """
    cache_dir = _get_cache_dir(cache_dir)

    if resolution == "high":
        filename = "Venus_Magellan_Topography_Global_4641m_v02.nc"
        download_url = url or "https://ftp.soest.hawaii.edu/pwessel/Venus_Magellan_Topography_Global_4641m_v02.nc"
        filepath = _download_file(download_url, filename, cache_dir)
        return _load_netcdf_grid(filepath)
    else:
        # Download low/medium resolution NetCDF from GMT remote data server
        filename = f"venus_relief_{resolution}_g.grd"
        download_url = url or f"https://oceania.generic-mapping-tools.org/server/venus/venus_relief/venus_relief_{resolution}_g.grd"
        filepath = _download_file(download_url, filename, cache_dir)
        return _load_netcdf_grid(filepath)
