"""Unit tests for the plate reconstruction module."""

import pytest
import numpy as np
from globe3d.grid import GeographicGrid
from globe3d.reconstruction import PlateModel, reconstruct_points, reconstruct_grid, _check_gplately

try:
    import gplately
    import pygplates
    HAS_GPLATELY = True
except ImportError:
    HAS_GPLATELY = False


@pytest.mark.skipif(not HAS_GPLATELY, reason="gplately or pygplates not installed")
def test_plate_model_initialization_missing_files(tmp_path):
    """Verifies that PlateModel raises FileNotFoundError for non-existent files."""
    rot_file = str(tmp_path / "missing.rot")
    gpml_file = str(tmp_path / "missing.gpml")
    with pytest.raises(FileNotFoundError):
        PlateModel(rot_file, gpml_file)


@pytest.mark.skipif(not HAS_GPLATELY, reason="gplately or pygplates not installed")
def test_reconstruct_points_validation():
    """Verifies point reconstruction input validation."""
    from globe3d import datasets
    scotese_dir = datasets.paleo.find_scotese_data_dir()
    if scotese_dir is None:
        pytest.skip("Scotese datasets not found on local machine")

    pm = datasets.paleo.scotese_plate_model()
    assert pm is not None

    # Valid points (lat, lon)
    oxford = [51.7519, -1.2578]
    rec = pm.reconstruct_points(oxford, 250.0)
    assert rec.shape == (1, 2)
    # At 250 Ma Oxford should be near the equator (approx 10-20 N)
    assert 5.0 <= rec[0, 0] <= 25.0

    # Functional interface
    rec_func = reconstruct_points(oxford, pm, 250.0)
    assert np.allclose(rec, rec_func)

    # Invalid points shape
    with pytest.raises(ValueError):
        pm.reconstruct_points(np.array([1.0, 2.0, 3.0]), 250.0)


@pytest.mark.skipif(not HAS_GPLATELY, reason="gplately or pygplates not installed")
def test_reconstruct_grid():
    """Verifies grid reconstruction on a small synthetic GeographicGrid."""
    from globe3d import datasets
    scotese_dir = datasets.paleo.find_scotese_data_dir()
    if scotese_dir is None:
        pytest.skip("Scotese datasets not found on local machine")

    pm = datasets.paleo.scotese_plate_model()
    lats = np.linspace(-90, 90, 19)
    lons = np.linspace(-180, 180, 37)
    grid_data = np.ones((len(lats), len(lons)), dtype=np.float64)
    geo_grid = GeographicGrid(lats=lats, lons=lons, grid=grid_data)

    rec_grid = pm.reconstruct_grid(geo_grid, age_ma=100.0)
    assert isinstance(rec_grid, GeographicGrid)
    assert rec_grid.grid.shape == geo_grid.grid.shape

    # Array input
    rec_arr = reconstruct_grid(grid_data, pm, age_ma=100.0)
    assert isinstance(rec_arr, np.ndarray)
    assert rec_arr.shape == grid_data.shape
