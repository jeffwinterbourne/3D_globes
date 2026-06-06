import os
import tarfile
import zipfile
import tempfile
import shutil
import numpy as np
import pytest
import netCDF4
from globe3d import datasets
from globe3d.grid import GeographicGrid

try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False


@pytest.fixture
def temp_cache_dir():
    """Fixture that creates and yields a temporary cache directory."""
    d = tempfile.mkdtemp()
    yield d
    try:
        shutil.rmtree(d)
    except OSError:
        pass


def create_mock_3d_netcdf(filepath, lat_var="latitude", lon_var="longitude", data_var="v"):
    """Helper to create a small 3D NetCDF file."""
    with netCDF4.Dataset(filepath, "w", format="NETCDF4") as ds:
        ds.createDimension("depth", 3)
        ds.createDimension(lat_var, 4)
        ds.createDimension(lon_var, 5)

        depths = ds.createVariable("depth", "f4", ("depth",))
        lats = ds.createVariable(lat_var, "f4", (lat_var,))
        lons = ds.createVariable(lon_var, "f4", (lon_var,))
        v = ds.createVariable(data_var, "f4", ("depth", lat_var, lon_var))

        depths[:] = [50.0, 100.0, 200.0]
        lats[:] = [-90.0, -30.0, 30.0, 90.0]
        lons[:] = [-180.0, -90.0, 0.0, 90.0, 180.0]
        # Set values to index for slicing verification
        v[0, :, :] = np.ones((4, 5)) * 10.0
        v[1, :, :] = np.ones((4, 5)) * 20.0
        v[2, :, :] = np.ones((4, 5)) * 30.0


def create_mock_2d_netcdf(filepath, lat_var="lat", lon_var="lon", data_var="z"):
    """Helper to create a small 2D NetCDF file."""
    with netCDF4.Dataset(filepath, "w", format="NETCDF4") as ds:
        ds.createDimension(lat_var, 4)
        ds.createDimension(lon_var, 5)

        lats = ds.createVariable(lat_var, "f4", (lat_var,))
        lons = ds.createVariable(lon_var, "f4", (lon_var,))
        z = ds.createVariable(data_var, "f4", (lat_var, lon_var))

        lats[:] = [-90.0, -30.0, 30.0, 90.0]
        lons[:] = [-180.0, -90.0, 0.0, 90.0, 180.0]
        z[:] = np.arange(20).reshape(4, 5)


def create_mock_geotiff(filepath):
    """Helper to create a small GeoTIFF file if rasterio is available."""
    if not RASTERIO_AVAILABLE:
        return
    from rasterio.transform import from_origin
    data = np.ones((10, 20), dtype=np.float32) * 123.0
    transform = from_origin(-180, 90, 18, 18)
    with rasterio.open(
        filepath,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=data.dtype,
        crs="+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs",
        transform=transform,
    ) as dst:
        dst.write(data, 1)


def test_download_cache_resolution(temp_cache_dir, monkeypatch):
    """Test that caching works and no download is initiated if file exists."""
    dummy_file = os.path.join(temp_cache_dir, "test_file.nc")
    with open(dummy_file, "w") as f:
        f.write("dummy content")

    # Mock urllib.request.urlopen to verify it isn't called when file exists
    def mock_urlopen(req):
        raise AssertionError("urlopen was called but file should have been cached!")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    res = datasets._download_file("http://invalid-url.com/test_file.nc", "test_file.nc", temp_cache_dir)
    assert res == dummy_file
    assert os.path.exists(res)


def test_s40rts(temp_cache_dir, monkeypatch):
    """Test S40RTS seismic tomography download, depth-slicing, and loading."""
    filename = "S40RTS_dvs.nc"
    mock_filepath = os.path.join(temp_cache_dir, filename)
    create_mock_3d_netcdf(mock_filepath)

    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_filepath)

    # Slice at depth close to 100.0 (should pick index 1 where value is 20.0)
    grid = datasets.s40rts(depth=110.0, cache_dir=temp_cache_dir)
    assert isinstance(grid, GeographicGrid)
    assert grid.grid.shape == (4, 5)
    assert np.allclose(grid.grid, 20.0)
    assert np.allclose(grid.lats, [-90.0, -30.0, 30.0, 90.0])
    assert np.allclose(grid.lons, [-180.0, -90.0, 0.0, 90.0, 180.0])


@pytest.mark.skipif(not RASTERIO_AVAILABLE, reason="rasterio is required for TIFF tests")
def test_egm2008(temp_cache_dir, monkeypatch):
    """Test EGM2008 loading and downsampling."""
    filename = "us_nga_egm2008_1.tif"
    mock_filepath = os.path.join(temp_cache_dir, filename)
    create_mock_geotiff(mock_filepath)

    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_filepath)

    # Test load without downsampling
    grid = datasets.egm2008(downsample_factor=1, cache_dir=temp_cache_dir)
    assert isinstance(grid, GeographicGrid)
    assert grid.grid.shape == (10, 20)
    assert np.allclose(grid.grid, 123.0)

    # Test load with downsampling
    grid_ds = datasets.egm2008(downsample_factor=2, cache_dir=temp_cache_dir)
    assert grid_ds.grid.shape == (5, 10)


def test_crust1(temp_cache_dir, monkeypatch):
    """Test CRUST1.0 extraction, parsing, reshaping, and scaling."""
    filename = "crust1.0.tar.gz"
    mock_filepath = os.path.join(temp_cache_dir, filename)

    # Create dummy crust1.bnds content: 64800 lines of 9 values
    dummy_bnds = []
    for i in range(64800):
        # Set Mohos (index 8) to vary between -10.0 and -50.0
        dummy_bnds.append(f"0.0 -1.0 -1.0 -2.0 -2.0 -2.0 -3.0 -4.0 {-10.0 - (i % 41)}")

    # Compress into a tarball
    with tarfile.open(mock_filepath, "w:gz") as tar:
        bnds_data = "\n".join(dummy_bnds).encode("utf-8")
        tarinfo = tarfile.TarInfo(name="crust1.bnds")
        tarinfo.size = len(bnds_data)
        tar.addfile(tarinfo, fileobj=import_io_helper(bnds_data))

    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_filepath)

    # Load Moho layer (layer=8, standard name "moho")
    grid = datasets.crust1(layer="moho", as_meters=True, cache_dir=temp_cache_dir)
    assert isinstance(grid, GeographicGrid)
    assert grid.grid.shape == (180, 360)
    # Check that lats are ascending (CRUST1.0 sorted descending, reversed by us)
    assert grid.lats[0] == -89.5
    assert grid.lats[-1] == 89.5
    # Scaled to meters (e.g. -10 km becomes -10000 m)
    assert grid.grid.min() <= -10000.0


def import_io_helper(bytes_data):
    """Utility helper to return a BytesIO object."""
    import io
    return io.BytesIO(bytes_data)


def test_dynamic_topography(temp_cache_dir, monkeypatch):
    """Test dynamic topography parsing and gridding from CSV/DAT spot data."""
    # Test space-delimited DAT format (like spot.dat)
    filename = "spot.dat"
    mock_filepath = os.path.join(temp_cache_dir, filename)

    # 4 spot points: (lat, lon, val_in_km, uncertainty)
    spot_data = (
        "45.0 -45.0 1.5 0.1\n"
        "-45.0 45.0 -0.5 0.1\n"
        "0.0 0.0 0.0 0.1\n"
        "80.0 160.0 2.0 0.1\n"
    )
    with open(mock_filepath, "w") as f:
        f.write(spot_data)

    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_filepath)

    grid = datasets.dynamic_topography(grid_step=10.0, cache_dir=temp_cache_dir)
    assert isinstance(grid, GeographicGrid)
    assert grid.grid.shape == (19, 37)  # np.arange(-90, 90+10, 10) has 19, np.arange(-180, 180+10, 10) has 37
    # Values converted to meters: 1.5 km -> 1500 m
    assert np.any(grid.grid >= 1500.0)


def test_gravity(temp_cache_dir, monkeypatch):
    """Test gravity NetCDF loading."""
    filename = "bouguer_anomaly.nc"
    mock_filepath = os.path.join(temp_cache_dir, filename)
    create_mock_2d_netcdf(mock_filepath, lat_var="lat", lon_var="lon", data_var="bouguer")

    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_filepath)

    grid = datasets.gravity(cache_dir=temp_cache_dir)
    assert isinstance(grid, GeographicGrid)
    assert grid.grid.shape == (4, 5)


@pytest.mark.skipif(not RASTERIO_AVAILABLE, reason="rasterio is required for TIFF tests")
def test_magnetics(temp_cache_dir, monkeypatch):
    """Test magnetics ZIP extraction and loading."""
    filename = "EMAG2_V3_Upward_Continued_GeoTIFF.zip"
    mock_filepath = os.path.join(temp_cache_dir, filename)

    # Create dummy GeoTIFF inside zip
    temp_tif = os.path.join(temp_cache_dir, "EMAG2_V3_Upward_Continued.tif")
    create_mock_geotiff(temp_tif)

    with zipfile.ZipFile(mock_filepath, "w") as zip_ref:
        zip_ref.write(temp_tif, "EMAG2_V3_Upward_Continued.tif")
    os.remove(temp_tif)

    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_filepath)

    grid = datasets.magnetics(downsample_factor=1, cache_dir=temp_cache_dir)
    assert isinstance(grid, GeographicGrid)
    assert grid.grid.shape == (10, 20)


def test_planetary_topography_lowres(temp_cache_dir, monkeypatch):
    """Test Mars, Moon, and Venus low-res NetCDF loading from GMT servers."""
    # Test Mars 30m grid
    mars_filename = "mars_relief_30m_g.grd"
    mock_mars_path = os.path.join(temp_cache_dir, mars_filename)
    create_mock_2d_netcdf(mock_mars_path, lat_var="lat", lon_var="lon", data_var="z")

    # Verify that the URL passed contains mars
    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_mars_path)

    grid_mars = datasets.mars(resolution="30m", cache_dir=temp_cache_dir)
    assert isinstance(grid_mars, GeographicGrid)
    assert grid_mars.grid.shape == (4, 5)

    # Test Moon 30m grid
    moon_filename = "moon_relief_30m_g.grd"
    mock_moon_path = os.path.join(temp_cache_dir, moon_filename)
    create_mock_2d_netcdf(mock_moon_path, lat_var="lat", lon_var="lon", data_var="z")
    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_moon_path)

    grid_moon = datasets.moon(resolution="30m", cache_dir=temp_cache_dir)
    assert isinstance(grid_moon, GeographicGrid)
    assert grid_moon.grid.shape == (4, 5)

    # Test Venus 30m grid
    venus_filename = "venus_relief_30m_g.grd"
    mock_venus_path = os.path.join(temp_cache_dir, venus_filename)
    create_mock_2d_netcdf(mock_venus_path, lat_var="lat", lon_var="lon", data_var="z")
    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_venus_path)

    grid_venus = datasets.venus(resolution="30m", cache_dir=temp_cache_dir)
    assert isinstance(grid_venus, GeographicGrid)
    assert grid_venus.grid.shape == (4, 5)


def test_list_datasets():
    info = datasets.list_datasets()
    assert isinstance(info, dict)
    assert "topography" in info
    assert "tomography" in info
    assert "shapefiles" in info
    assert info["topography"]["earth"] == "Earth global relief (topography + bathymetry)"


def test_hierarchical_tomography(temp_cache_dir, monkeypatch):
    filename = "S40RTS_dvs.nc"
    mock_filepath = os.path.join(temp_cache_dir, filename)
    create_mock_3d_netcdf(mock_filepath)
    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_filepath)

    grid = datasets.tomography.s40rts(depth=110.0, cache_dir=temp_cache_dir)
    assert isinstance(grid, GeographicGrid)
    assert grid.grid.shape == (4, 5)


def test_hierarchical_topography_mars(temp_cache_dir, monkeypatch):
    filename = "mars_relief_30m_g.grd"
    mock_filepath = os.path.join(temp_cache_dir, filename)
    create_mock_2d_netcdf(mock_filepath, lat_var="lat", lon_var="lon", data_var="z")
    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_filepath)

    grid = datasets.topography.mars(resolution="30m", cache_dir=temp_cache_dir)
    assert isinstance(grid, GeographicGrid)


def test_hierarchical_topography_earth(temp_cache_dir, monkeypatch):
    filename = "earth_relief_30m_g.grd"
    mock_filepath = os.path.join(temp_cache_dir, filename)
    create_mock_2d_netcdf(mock_filepath, lat_var="lat", lon_var="lon", data_var="z")
    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_filepath)

    grid = datasets.topography.earth(resolution="30m", cache_dir=temp_cache_dir)
    assert isinstance(grid, GeographicGrid)


def test_topography_mercury(temp_cache_dir, monkeypatch):
    filename = "mercury_relief_30m_g.grd"
    mock_filepath = os.path.join(temp_cache_dir, filename)
    create_mock_2d_netcdf(mock_filepath, lat_var="lat", lon_var="lon", data_var="z")
    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_filepath)

    grid = datasets.topography.mercury(resolution="30m", cache_dir=temp_cache_dir)
    assert isinstance(grid, GeographicGrid)


def test_topography_etopo(temp_cache_dir, monkeypatch):
    filename = "earth_relief_30m_g.grd"
    mock_filepath = os.path.join(temp_cache_dir, filename)
    create_mock_2d_netcdf(mock_filepath, lat_var="lat", lon_var="lon", data_var="z")
    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_filepath)

    grid = datasets.topography.etopo(resolution="30m", cache_dir=temp_cache_dir)
    assert isinstance(grid, GeographicGrid)


def test_topography_vesta():
    with pytest.raises(NotImplementedError):
        datasets.topography.vesta()


def test_topography_gebco(temp_cache_dir, monkeypatch):
    # Test ValueError without url
    with pytest.raises(ValueError, match="GEBCO dataset is very large"):
        datasets.topography.gebco()

    # Test with local file mock
    filename = "gebco_grid.nc"
    mock_filepath = os.path.join(temp_cache_dir, filename)
    create_mock_2d_netcdf(mock_filepath, lat_var="lat", lon_var="lon", data_var="z")

    grid = datasets.topography.gebco(url=mock_filepath)
    assert isinstance(grid, GeographicGrid)


def test_shapefiles(temp_cache_dir, monkeypatch):
    # Mock download to return a zipped dummy file
    mock_zip = os.path.join(temp_cache_dir, "ne_110m_land.zip")
    with zipfile.ZipFile(mock_zip, "w") as zf:
        zf.writestr("ne_110m_land.shp", "dummy content")

    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_zip)

    # Test land shapefile
    shp_path = datasets.shapefiles.land(cache_dir=temp_cache_dir)
    assert shp_path.endswith("ne_110m_land.shp")
    assert os.path.exists(shp_path)

    # Test coastline shapefile
    mock_zip_coast = os.path.join(temp_cache_dir, "ne_110m_coastline.zip")
    with zipfile.ZipFile(mock_zip_coast, "w") as zf:
        zf.writestr("ne_110m_coastline.shp", "dummy content")
    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_zip_coast)

    shp_path_coast = datasets.shapefiles.coastline(cache_dir=temp_cache_dir)
    assert shp_path_coast.endswith("ne_110m_coastline.shp")
    assert os.path.exists(shp_path_coast)


def test_callable_namespaces(temp_cache_dir, monkeypatch):
    # Test that datasets.gravity is callable (delegates to gravity.bouguer)
    filename = "bouguer_anomaly.nc"
    mock_filepath = os.path.join(temp_cache_dir, filename)
    create_mock_2d_netcdf(mock_filepath, lat_var="lat", lon_var="lon", data_var="bouguer")
    monkeypatch.setattr(datasets, "_download_file", lambda url, fname, cdir: mock_filepath)

    grid = datasets.gravity(cache_dir=temp_cache_dir)
    assert isinstance(grid, GeographicGrid)

    # Test that datasets.gravity.bouguer is also callable
    grid2 = datasets.gravity.bouguer(cache_dir=temp_cache_dir)
    assert isinstance(grid2, GeographicGrid)
