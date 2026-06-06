"""Datasets module for the globe3d package.

This module provides fetching, caching, and preprocessing capabilities for several
standard global geophysical datasets, including Earth, Mars, the Moon, Venus,
Mercury, gravity, magnetics, geoids, crustal boundaries, and shapefiles.
"""

import os
import csv
import zipfile
import tarfile
import tempfile
import urllib.request
import gzip
import shutil
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


class TopographyNamespace:
    """Namespace for topographic datasets (Earth, Mars, Moon, Venus, Mercury, Vesta)."""

    def earth(self, resolution="30m", cache_dir=None, url=None):
        """Fetches and loads Earth global relief data (topography + bathymetry).

        Defaults to a fast-loading, low-resolution 30 arc-minute grid from the GMT remote server.
        If resolution is "high", downloads the ETOPO1 bedrock relief grid.

        Args:
            resolution (str, optional): Resolution of the grid. Can be "30m" (default), "10m",
                "05m", "01d", or "high". Defaults to "30m".
            cache_dir (str, optional): Custom cache directory. Defaults to None.
            url (str, optional): Custom download URL. Defaults to None.

        Returns:
            GeographicGrid: Loaded Earth topography grid.
        """
        cache_dir = _get_cache_dir(cache_dir)

        if resolution == "high":
            filename_gz = "ETOPO1_Bed_g_gmt4.grd.gz"
            filename = "ETOPO1_Bed_g_gmt4.grd"
            download_url = url or "https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO1/data/bedrock/grid_registered/netcdf/ETOPO1_Bed_g_gmt4.grd.gz"
            
            filepath_gz = _download_file(download_url, filename_gz, cache_dir)
            filepath = os.path.join(cache_dir, filename)
            
            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                with gzip.open(filepath_gz, 'rb') as f_in:
                    with open(filepath, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            
            return _load_netcdf_grid(filepath)
        else:
            filename = f"earth_relief_{resolution}_g.grd"
            download_url = url or f"https://oceania.generic-mapping-tools.org/server/earth/earth_relief/earth_relief_{resolution}_g.grd"
            filepath = _download_file(download_url, filename, cache_dir)
            return _load_netcdf_grid(filepath)

    def etopo(self, resolution="30m", cache_dir=None, url=None):
        """Fetches and loads NOAA ETOPO Earth global relief data.

        Args:
            resolution (str, optional): Resolution of the grid. Can be "30m" (default), "10m",
                "05m", "01d", or "high". Defaults to "30m".
            cache_dir (str, optional): Custom cache directory. Defaults to None.
            url (str, optional): Custom download URL. Defaults to None.

        Returns:
            GeographicGrid: Loaded ETOPO Earth topography grid.
        """
        return self.earth(resolution=resolution, cache_dir=cache_dir, url=url)

    def gebco(self, downsample_factor=5, cache_dir=None, url=None):
        """Loads a GEBCO global bathymetry grid.

        Note:
            GEBCO datasets are very large and typically require manual download. If url is not
            provided, this method raises a ValueError with download instructions.

        Args:
            downsample_factor (int, optional): Resolution decimation factor. Defaults to 5.
            cache_dir (str, optional): Custom cache directory. Defaults to None.
            url (str, optional): Custom download URL or local filepath. Defaults to None.

        Returns:
            GeographicGrid: Loaded GEBCO grid.
        """
        if not url:
            raise ValueError(
                "GEBCO dataset is very large and must be downloaded manually from the GEBCO Data Store. "
                "Please provide the path or URL to the downloaded NetCDF file using the 'url' parameter."
            )
        if os.path.exists(url):
            return _load_netcdf_grid(url)
        else:
            cache_dir = _get_cache_dir(cache_dir)
            filename = "gebco_grid.nc"
            filepath = _download_file(url, filename, cache_dir)
            return _load_netcdf_grid(filepath)

    def mars(self, resolution="30m", cache_dir=None, url=None):
        """Fetches and loads Mars topography data.

        Defaults to a fast-loading, low-resolution 30 arc-minute grid from the GMT remote server.
        If resolution="high", downloads the full-resolution MOLA DEM GeoTIFF from USGS.

        Args:
            resolution (str, optional): Resolution of the grid. Can be "30m" (default), "10m",
                "05m", "01d", or "high". Defaults to "30m".
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
            return _load_tiff_grid(filepath, downsample_factor=20)
        else:
            filename = f"mars_relief_{resolution}_g.grd"
            download_url = url or f"https://oceania.generic-mapping-tools.org/server/mars/mars_relief/mars_relief_{resolution}_g.grd"
            filepath = _download_file(download_url, filename, cache_dir)
            return _load_netcdf_grid(filepath)

    def moon(self, resolution="30m", cache_dir=None, url=None):
        """Fetches and loads Moon topography data.

        Defaults to a fast-loading, low-resolution 30 arc-minute grid from the GMT remote server.
        If resolution="high", downloads the full-resolution LRO LOLA DEM GeoTIFF from USGS.

        Args:
            resolution (str, optional): Resolution of the grid. Can be "30m" (default), "10m",
                "05m", "01d", or "high". Defaults to "30m".
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
            return _load_tiff_grid(filepath, downsample_factor=50)
        else:
            filename = f"moon_relief_{resolution}_g.grd"
            download_url = url or f"https://oceania.generic-mapping-tools.org/server/moon/moon_relief/moon_relief_{resolution}_g.grd"
            filepath = _download_file(download_url, filename, cache_dir)
            return _load_netcdf_grid(filepath)

    def venus(self, resolution="30m", cache_dir=None, url=None):
        """Fetches and loads Venus topography data.

        Defaults to a fast-loading, low-resolution 30 arc-minute grid from the GMT remote server.
        If resolution="high", downloads the Magellan GTDR NetCDF topography grid.

        Args:
            resolution (str, optional): Resolution of the grid. Can be "30m" (default), "10m",
                "05m", "01d", or "high". Defaults to "30m".
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
            filename = f"venus_relief_{resolution}_g.grd"
            download_url = url or f"https://oceania.generic-mapping-tools.org/server/venus/venus_relief/venus_relief_{resolution}_g.grd"
            filepath = _download_file(download_url, filename, cache_dir)
            return _load_netcdf_grid(filepath)

    def mercury(self, resolution="30m", cache_dir=None, url=None):
        """Fetches and loads Mercury global topography data.

        Defaults to a fast-loading, low-resolution 30 arc-minute grid from the MESSENGER mission.

        Args:
            resolution (str, optional): Resolution of the grid. Can be "30m" (default), "10m",
                "05m", or "01d". Defaults to "30m".
            cache_dir (str, optional): Custom cache directory. Defaults to None.
            url (str, optional): Custom download URL. Defaults to None.

        Returns:
            GeographicGrid: Loaded Mercury topography grid.
        """
        cache_dir = _get_cache_dir(cache_dir)
        filename = f"mercury_relief_{resolution}_g.grd"
        download_url = url or f"https://oceania.generic-mapping-tools.org/server/mercury/mercury_relief/mercury_relief_{resolution}_g.grd"
        filepath = _download_file(download_url, filename, cache_dir)
        return _load_netcdf_grid(filepath)

    def vesta(self):
        """Provides access to Vesta global shape/topography data.

        Raises:
            NotImplementedError: Vesta is highly non-spherical and typically processed from 3D
                shape models (.obj or .ply) directly rather than 2D geographic grids.
        """
        raise NotImplementedError(
            "Vesta is a highly non-spherical, irregular body. It is typically processed from 3D shape models "
            "(.obj or .ply) directly rather than 2D geographic grids. Please refer to NASA PDS or frieger.com "
            "to obtain shape models."
        )


class TomographyNamespace:
    """Namespace for tomography datasets."""

    def s40rts(self, depth=2850.0, cache_dir=None, url=None):
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

        primary_url = url or "https://raw.githubusercontent.com/shuleyu/seismic-tomography-models/master/S40RTS_dvs.nc"
        fallback_url = "http://ds.iris.edu/files/emc/models/S40RTS.nc"

        try:
            filepath = _download_file(primary_url, filename, cache_dir)
        except Exception:
            filepath = _download_file(fallback_url, filename, cache_dir)

        with Dataset(filepath, "r") as ds:
            depths = np.array(ds.variables["depth"][:])
            lats = np.array(ds.variables["latitude"][:])
            lons = np.array(ds.variables["longitude"][:])
            
            depth_idx = np.argmin(np.abs(depths - depth))
            grid = np.array(ds.variables["v"][depth_idx, :, :])

        return GeographicGrid(lats, lons, grid)


class GeoidNamespace:
    """Namespace for geoid undulation datasets."""

    def egm2008(self, downsample_factor=5, cache_dir=None, url=None):
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


class CrustNamespace:
    """Namespace for crustal thickness and Moho datasets."""

    def crust1(self, layer="moho", as_meters=True, cache_dir=None, url=None):
        """Fetches and parses the CRUST1.0 global 1x1 degree crustal boundaries database.

        Args:
            layer (str or int, optional): Layer index (0-8) or name: "surface", "water_bottom",
                "ice_bottom", "moho". Defaults to "moho".
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

        with tarfile.open(filepath, "r:gz") as tar:
            f = tar.extractfile("crust1.bnds")
            if f is None:
                raise ValueError("Could not find crust1.bnds in CRUST1.0 tarball.")
            raw_data = np.loadtxt(f)

        grid = raw_data[:, layer_idx].reshape((180, 360))
        grid = np.flipud(grid)
        lats = np.linspace(-89.5, 89.5, 180)
        lons = np.linspace(-179.5, 179.5, 360)

        if as_meters:
            grid = grid * 1000.0

        return GeographicGrid(lats, lons, grid)


class LithosphereNamespace:
    """Namespace for lithosphere datasets. Can be called directly for backward compatibility."""

    def __call__(self, parameter="total", as_meters=True, cache_dir=None, url=None):
        return self.thickness(parameter=parameter, as_meters=as_meters, cache_dir=cache_dir, url=url)

    def thickness(self, parameter="total", as_meters=True, cache_dir=None, url=None):
        """Fetches and loads the LITHO1.0 global lithospheric thickness model.

        Args:
            parameter (str, optional): The parameter to return:
                - "total" (default): total solid lithospheric thickness (crust + lid)
                - "lid": thickness of the lithospheric mantle lid only
                - "lab": depth to the Lithosphere-Asthenosphere Boundary (LAB) below sea level
            as_meters (bool, optional): Converts values from kilometers to meters. Defaults to True.
            cache_dir (str, optional): Custom cache directory. Defaults to None.
            url (str, optional): Custom download URL. Defaults to None.

        Returns:
            GeographicGrid: Grid representing the requested lithospheric property.
        """
        if parameter not in ["total", "lid", "lab"]:
            raise ValueError("parameter must be one of: 'total', 'lid', 'lab'")

        cache_dir = _get_cache_dir(cache_dir)
        filename = "LITHO1.0.nc"
        download_url = url or "https://ds.iris.edu/files/products/emc/emc-files/LITHO1.0.nc"
        filepath = _download_file(download_url, filename, cache_dir)

        with Dataset(filepath, "r") as ds:
            lats = np.array(ds.variables["latitude"][:])
            lons = np.array(ds.variables["longitude"][:])

            if parameter == "lab":
                grid = np.array(ds.variables["lid_bottom_depth"][:])
            elif parameter == "lid":
                lid_bottom = np.array(ds.variables["lid_bottom_depth"][:])
                lid_top = np.array(ds.variables["lid_top_depth"][:])
                grid = lid_bottom - lid_top
            else:  # total
                lid_bottom = np.array(ds.variables["lid_bottom_depth"][:])
                solid_surface = np.array(ds.variables["lid_top_depth"][:]).copy()
                
                for top_var in [
                    "lower_crust_top_depth",
                    "middle_crust_top_depth",
                    "upper_crust_top_depth",
                    "lower_sediments_top_depth",
                    "middle_sediments_top_depth",
                    "upper_sediments_top_depth",
                    "ice_top_depth",
                    "water_bottom_depth"
                ]:
                    if top_var in ds.variables:
                        val = np.array(ds.variables[top_var][:])
                        mask = ~np.isnan(val)
                        solid_surface[mask] = val[mask]
                
                grid = lid_bottom - solid_surface

            if len(lats) > 1 and lats[1] < lats[0]:
                lats = lats[::-1]
                grid = np.flipud(grid)

            if as_meters:
                grid = grid * 1000.0

            return GeographicGrid(lats, lons, grid)


class DynamicTopographyNamespace:
    """Namespace for dynamic topography datasets. Can be called directly for backward compatibility."""

    def __call__(self, grid_step=1.0, cache_dir=None, url=None):
        return self.hoggard2016(grid_step=grid_step, cache_dir=cache_dir, url=url)

    def hoggard2016(self, grid_step=1.0, cache_dir=None, url=None):
        """Fetches, parses, and grids the Hoggard et al. (2016) Dynamic Topography spot data.

        Args:
            grid_step (float, optional): Spacing of the global interpolation grid in degrees.
                Defaults to 1.0.
            cache_dir (str, optional): Custom cache directory. Defaults to None.
            url (str, optional): Custom download URL. Defaults to None.

        Returns:
            GeographicGrid: Standardized interpolated global dynamic topography grid.
        """
        cache_dir = _get_cache_dir(cache_dir)
        
        filename = "spot.dat" if not url else "Hoggard_etal_2016_Residual_Topography.csv"
        primary_url = url or "https://raw.githubusercontent.com/drhodrid/Davies_etal_NGeo_2019_Datasets/master/hoggard/spot.dat"
        fallback_url = "https://raw.githubusercontent.com/drhodrid/Davies_etal_NGeo_2019_Datasets/master/Observations/Hoggard_etal_2016/Hoggard_etal_2016_Residual_Topography.csv"

        try:
            filepath = _download_file(primary_url, filename, cache_dir)
        except Exception:
            filepath = _download_file(fallback_url, filename, cache_dir)

        raw_lats = []
        raw_lons = []
        raw_vals = []

        with open(filepath, "r", encoding="utf-8") as f:
            first_line = f.readline()
            f.seek(0)
            
            if "," in first_line:
                reader = csv.reader(f)
                header = next(reader)
                lat_col, lon_col, val_col = 0, 1, 2
                
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
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        try:
                            raw_lats.append(float(parts[0]))
                            raw_lons.append(float(parts[1]))
                            raw_vals.append(float(parts[2]) * 1000.0)
                        except ValueError:
                            continue

        import scipy.interpolate
        target_lats = np.arange(-90, 90 + grid_step, grid_step)
        target_lons = np.arange(-180, 180 + grid_step, grid_step)
        lon_mesh, lat_mesh = np.meshgrid(target_lons, target_lats)

        points = np.column_stack((raw_lons, raw_lats))
        grid_val = scipy.interpolate.griddata(
            points, np.array(raw_vals), (lon_mesh, lat_mesh), method="linear"
        )

        if np.any(np.isnan(grid_val)):
            grid_val_nearest = scipy.interpolate.griddata(
                points, np.array(raw_vals), (lon_mesh, lat_mesh), method="nearest"
            )
            grid_val[np.isnan(grid_val)] = grid_val_nearest[np.isnan(grid_val)]

        return GeographicGrid(target_lats, target_lons, grid_val)


class GravityNamespace:
    """Namespace for gravity anomaly datasets. Can be called directly for backward compatibility."""

    def __call__(self, cache_dir=None, url=None):
        return self.bouguer(cache_dir=cache_dir, url=url)

    def bouguer(self, cache_dir=None, url=None):
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


class MagneticsNamespace:
    """Namespace for magnetic anomaly datasets. Can be called directly for backward compatibility."""

    def __call__(self, downsample_factor=5, cache_dir=None, url=None):
        return self.emag2(downsample_factor=downsample_factor, cache_dir=cache_dir, url=url)

    def emag2(self, downsample_factor=5, cache_dir=None, url=None):
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

        with zipfile.ZipFile(filepath, "r") as zip_ref:
            tif_files = [f for f in zip_ref.namelist() if f.lower().endswith(".tif")]
            if not tif_files:
                raise ValueError("No GeoTIFF found inside EMAG2v3 zip archive.")
            
            temp_dir = tempfile.mkdtemp()
            extracted_path = zip_ref.extract(tif_files[0], temp_dir)

        try:
            grid = _load_tiff_grid(extracted_path, downsample_factor=downsample_factor)
        finally:
            try:
                os.remove(extracted_path)
                os.rmdir(temp_dir)
            except OSError:
                pass

        return grid


class ShapefilesNamespace:
    """Namespace for vector shapefile datasets (land, coastline)."""

    def land(self, cache_dir=None, url=None):
        """Fetches and extracts the Natural Earth 1:110m land polygons shapefile.

        Args:
            cache_dir (str, optional): Custom cache directory. Defaults to None.
            url (str, optional): Custom download URL. Defaults to None.

        Returns:
            str: Path to the extracted '.shp' file.
        """
        cache_dir = _get_cache_dir(cache_dir)
        filename = "ne_110m_land.zip"
        url = url or "https://naturalearth.s3.amazonaws.com/110m_physical/ne_110m_land.zip"

        zip_path = _download_file(url, filename, cache_dir)
        extract_dir = os.path.join(cache_dir, "ne_110m_land")
        os.makedirs(extract_dir, exist_ok=True)

        shp_path = os.path.join(extract_dir, "ne_110m_land.shp")
        if not os.path.exists(shp_path):
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

        return shp_path

    def coastline(self, cache_dir=None, url=None):
        """Fetches and extracts the Natural Earth 1:110m coastline lines shapefile.

        Args:
            cache_dir (str, optional): Custom cache directory. Defaults to None.
            url (str, optional): Custom download URL. Defaults to None.

        Returns:
            str: Path to the extracted '.shp' file.
        """
        cache_dir = _get_cache_dir(cache_dir)
        filename = "ne_110m_coastline.zip"
        url = url or "https://naturalearth.s3.amazonaws.com/110m_physical/ne_110m_coastline.zip"

        zip_path = _download_file(url, filename, cache_dir)
        extract_dir = os.path.join(cache_dir, "ne_110m_coastline")
        os.makedirs(extract_dir, exist_ok=True)

        shp_path = os.path.join(extract_dir, "ne_110m_coastline.shp")
        if not os.path.exists(shp_path):
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

        return shp_path


# Instantiate namespaces
topography = TopographyNamespace()
tomography = TomographyNamespace()
geoid = GeoidNamespace()
crust = CrustNamespace()
dynamic_topography = DynamicTopographyNamespace()
gravity = GravityNamespace()
magnetics = MagneticsNamespace()
shapefiles = ShapefilesNamespace()
lithosphere = LithosphereNamespace()


def list_datasets():
    """Lists all available datasets by category in a structured format.

    Returns:
        dict: A dictionary of datasets grouped by category.
    """
    datasets_info = {
        "topography": {
            "earth": "Earth global relief (topography + bathymetry)",
            "etopo": "NOAA ETOPO global relief",
            "gebco": "GEBCO global bathymetry grid",
            "mars": "Mars global topography from MOLA",
            "moon": "Moon global topography from LOLA",
            "venus": "Venus global topography from Magellan",
            "mercury": "Mercury global topography from MESSENGER",
            "vesta": "Vesta asteroid topography loader guide",
        },
        "tomography": {
            "s40rts": "S40RTS global seismic wave velocity perturbations",
        },
        "geoid": {
            "egm2008": "EGM2008 global geoid undulation model",
        },
        "crust": {
            "crust1": "CRUST1.0 global crustal boundary database",
        },
        "dynamic_topography": {
            "hoggard2016": "Hoggard et al. (2016) residual dynamic topography",
        },
        "gravity": {
            "bouguer": "NOAA Bouguer anomaly gravity grid",
        },
        "magnetics": {
            "emag2": "EMAG2v3 global magnetic anomalies grid",
        },
        "shapefiles": {
            "land": "Natural Earth land polygons shapefile (1:110m)",
            "coastline": "Natural Earth coastline lines shapefile (1:110m)",
        },
        "lithosphere": {
            "thickness": "LITHO1.0 global lithospheric thickness model",
        }
    }
    return datasets_info


# Legacy module-level functions for backward compatibility
def s40rts(depth=2850.0, cache_dir=None, url=None):
    """Fetches and loads a 2D depth slice of the S40RTS seismic tomography model."""
    return tomography.s40rts(depth=depth, cache_dir=cache_dir, url=url)


def egm2008(downsample_factor=5, cache_dir=None, url=None):
    """Fetches and loads the EGM2008 Geoid Undulation dataset."""
    return geoid.egm2008(downsample_factor=downsample_factor, cache_dir=cache_dir, url=url)


def crust1(layer="moho", as_meters=True, cache_dir=None, url=None):
    """Fetches and parses the CRUST1.0 global 1x1 degree crustal boundaries database."""
    return crust.crust1(layer=layer, as_meters=as_meters, cache_dir=cache_dir, url=url)


def mars(resolution="30m", cache_dir=None, url=None):
    """Fetches and loads Mars topography data."""
    return topography.mars(resolution=resolution, cache_dir=cache_dir, url=url)


def moon(resolution="30m", cache_dir=None, url=None):
    """Fetches and loads Moon topography data."""
    return topography.moon(resolution=resolution, cache_dir=cache_dir, url=url)


def venus(resolution="30m", cache_dir=None, url=None):
    """Fetches and loads Venus topography data."""
    return topography.venus(resolution=resolution, cache_dir=cache_dir, url=url)
