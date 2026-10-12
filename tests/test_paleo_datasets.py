"""Unit tests for paleo datasets catalog and GlobeModel.from_paleo."""

import pytest
import numpy as np
from PIL import Image
from globe3d import datasets, GlobeModel, GridDisplacer, ImageColourer
from globe3d.grid import GeographicGrid


def test_list_scotese_maps():
    """Verifies that scotese_maps metadata catalog is loaded correctly."""
    maps = datasets.paleo.list_scotese_maps()
    assert isinstance(maps, list)
    assert len(maps) >= 88
    # Map 1 should be Holocene
    assert maps[0]["age_ma"] == 0.0
    assert "Holocene" in maps[0]["name"]


def test_grid_displacer_coastline_step():
    """Verifies that coastline_step modifies land elevations above step_threshold."""
    lats = np.array([-45.0, 0.0, 45.0])
    lons = np.array([-90.0, 0.0, 90.0])
    # Values: -100 (ocean), 50 (land), 200 (land)
    grid = np.array([
        [-100.0, 50.0, 200.0],
        [-100.0, 50.0, 200.0],
        [-100.0, 50.0, 200.0],
    ])
    geo_grid = GeographicGrid(lats=lats, lons=lons, grid=grid)

    displacer = GridDisplacer(geo_grid, coastline_step=1000.0, step_threshold=0.0)
    assert displacer.coastline_step == 1000.0

    verts = np.array([[1.0, 0.0, 0.0]])  # Point at lat 0, lon 0 (value is 50.0 + 1000.0 = 1050.0)
    displaced = displacer(verts, scale=0.001)
    # Radius was 1.0, new radius should be 1.0 + 0.001 * 1050.0 = 2.05
    new_r = np.linalg.norm(displaced, axis=1)[0]
    assert pytest.approx(new_r, abs=1e-3) == 2.05


def test_image_colourer_in_memory():
    """Verifies that ImageColourer works with PIL Images and NumPy arrays."""
    # PIL Image
    pil_img = Image.new("RGB", (360, 180), (255, 128, 0))
    colourer_pil = ImageColourer(image=pil_img)
    verts = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    cols = colourer_pil(verts)
    assert cols.shape == (2, 3)
    assert pytest.approx(cols[0, 0], abs=1e-2) == 1.0
    assert pytest.approx(cols[0, 1], abs=1e-2) == 128 / 255.0
    assert pytest.approx(cols[0, 2], abs=1e-2) == 0.0

    # NumPy array
    arr_img = np.zeros((180, 360, 3), dtype=np.uint8)
    arr_img[:, :] = [0, 255, 128]
    colourer_arr = ImageColourer(image=arr_img)
    cols_arr = colourer_arr(verts)
    assert pytest.approx(cols_arr[0, 1], abs=1e-2) == 1.0


def test_globe_model_from_paleo():
    """Verifies end-to-end GlobeModel.from_paleo creation."""
    scotese_dir = datasets.paleo.find_scotese_data_dir()
    if scotese_dir is None:
        pytest.skip("Scotese datasets not found on local machine")

    model = GlobeModel.from_paleo(
        age=250.0,
        radius=50.0,
        n_points=1000,
        hollow=True,
        vert_exagg=20.0,
        coastline_step=500.0,
        mark_poles=True,
        tracked_locations=[{"lat": 51.75, "lon": -1.25, "name": "Oxford"}],
    )
    assert model.outer_vertices.shape == (1000, 3)
    assert model.outer_colors.shape == (1000, 3)
    assert model.inner_vertices is not None


def test_globe_model_from_paleo_custom_texture():
    """Verifies GlobeModel.from_paleo accepts custom texture image/array."""
    scotese_dir = datasets.paleo.find_scotese_data_dir()
    if scotese_dir is None:
        pytest.skip("Scotese datasets not found on local machine")

    custom_img = Image.new("RGB", (360, 180), (30, 85, 40))
    model = GlobeModel.from_paleo(
        age=250.0,
        radius=50.0,
        n_points=500,
        hollow=False,
        texture=custom_img,
        mark_poles=False,
    )
    assert model.outer_vertices.shape == (500, 3)
    assert model.outer_colors.shape == (500, 3)
    # Check that colors reflect custom image green (30/255, 85/255, 40/255)
    assert pytest.approx(model.outer_colors[0, 1], abs=0.05) == 85 / 255.0

