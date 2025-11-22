import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from globe3d.grid import list_netcdf_variables, load_netcdf_grid

@patch('globe3d.grid.Dataset')
def test_list_netcdf_variables(mock_dataset):
    # Setup mock
    mock_ds = MagicMock()
    mock_ds.variables.keys.return_value = ['lat', 'lon', 'z']
    mock_dataset.return_value.__enter__.return_value = mock_ds
    
    vars = list_netcdf_variables('dummy.nc')
    assert vars == ['lat', 'lon', 'z']

@patch('globe3d.grid.Dataset')
def test_load_netcdf_grid(mock_dataset):
    # Setup mock
    mock_ds = MagicMock()
    
    # Create variable mocks
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
    
    lats, lons, grid = load_netcdf_grid('dummy.nc')
    
    assert lats.shape == (2,)
    assert lons.shape == (2,)
    assert grid.shape == (2, 2)
