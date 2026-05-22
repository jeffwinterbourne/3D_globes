import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from globe3d.grid import GeographicGrid

def test_geographic_grid_init():
    # Test valid grid with unsorted coordinates to verify sorting logic
    lats = np.array([10.0, 0.0, 20.0])
    lons = np.array([30.0, -10.0, 20.0])
    grid = np.array([
        [1.0, 2.0, 3.0], # lat 10
        [4.0, 5.0, 6.0], # lat 0
        [7.0, 8.0, 9.0]  # lat 20
    ])

    g = GeographicGrid(lats, lons, grid)
    # Sorted lats: 0, 10, 20. Sorted lons: -10, 20, 30.
    assert np.all(g.lats == np.array([0.0, 10.0, 20.0]))
    assert np.all(g.lons == np.array([-10.0, 20.0, 30.0]))
    
    # Check that grid was permuted properly:
    # Original grid mapping:
    # (lat 10, lon 30) = 1.0, (lat 10, lon -10) = 2.0, (lat 10, lon 20) = 3.0
    # (lat 0, lon 30) = 4.0, (lat 0, lon -10) = 5.0, (lat 0, lon 20) = 6.0
    # (lat 20, lon 30) = 7.0, (lat 20, lon -10) = 8.0, (lat 20, lon 20) = 9.0
    #
    # Sorted grid at:
    # lat 0 (original index 1): lons sorted should be: lon -10 (5.0), lon 20 (6.0), lon 30 (4.0) -> [5.0, 6.0, 4.0]
    # lat 10 (original index 0): lons sorted should be: lon -10 (2.0), lon 20 (3.0), lon 30 (1.0) -> [2.0, 3.0, 1.0]
    # lat 20 (original index 2): lons sorted should be: lon -10 (8.0), lon 20 (9.0), lon 30 (7.0) -> [8.0, 9.0, 7.0]
    expected_grid = np.array([
        [5.0, 6.0, 4.0],
        [2.0, 3.0, 1.0],
        [8.0, 9.0, 7.0]
    ])
    assert np.allclose(g.grid, expected_grid)

def test_geographic_grid_validation():
    # Duplicate lats
    with pytest.raises(ValueError, match="duplicate values"):
        GeographicGrid([1.0, 1.0], [1.0, 2.0], [[1, 2], [3, 4]])

    # Duplicate lons
    with pytest.raises(ValueError, match="duplicate values"):
        GeographicGrid([1.0, 2.0], [1.0, 1.0], [[1, 2], [3, 4]])

    # Invalid dimension
    with pytest.raises(ValueError, match="Latitudes must be a 1D array"):
        GeographicGrid([[1.0]], [1.0], [[1]])

    # Shape mismatch
    with pytest.raises(ValueError, match="Grid shape"):
        GeographicGrid([1.0, 2.0], [1.0, 2.0], [[1], [2]])

@patch('globe3d.grid.Dataset')
def test_list_netcdf_variables(mock_dataset):
    mock_ds = MagicMock()
    mock_ds.variables.keys.return_value = ['lat', 'lon', 'z']
    mock_dataset.return_value.__enter__.return_value = mock_ds
    
    vars = GeographicGrid.list_netcdf_variables('dummy.nc')
    assert vars == ['lat', 'lon', 'z']

@patch('globe3d.grid.Dataset')
def test_from_netcdf(mock_dataset):
    mock_ds = MagicMock()
    
    mock_lat = MagicMock()
    mock_lat.__getitem__.return_value = np.array([0, 1])
    
    mock_lon = MagicMock()
    mock_lon.__getitem__.return_value = np.array([10, 11])
    
    mock_z = MagicMock()
    mock_z.__getitem__.return_value = np.array([[1, 2], [3, 4]])

    mock_ds.variables = {
        'lat': mock_lat,
        'lon': mock_lon,
        'z': mock_z
    }
    mock_dataset.return_value = mock_ds
    
    g = GeographicGrid.from_netcdf('dummy.nc')
    
    assert g.lats.shape == (2,)
    assert g.lons.shape == (2,)
    assert g.grid.shape == (2, 2)

def test_from_tiff():
    import globe3d.grid
    if globe3d.grid.rasterio is None:
        with pytest.raises(ImportError, match="Rasterio is required"):
            GeographicGrid.from_tiff("dummy.tif")
    else:
        with patch('globe3d.grid.rasterio.open') as mock_open:
            mock_src = MagicMock()
            mock_src.read.return_value = np.ones((10, 20))
            mock_open.return_value.__enter__.return_value = mock_src
            
            g = GeographicGrid.from_tiff("dummy.tif")
            assert g.grid.shape == (10, 20)
            assert len(g.lats) == 10
            assert len(g.lons) == 20
