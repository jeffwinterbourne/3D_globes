import numpy as np
import pytest
from globe3d.displacement import displace_vertices, assign_vertex_colors, assign_vertex_colors_image
from unittest.mock import patch

def test_displace_vertices():
    # Create a simple grid
    lats = np.linspace(-90, 90, 5)
    lons = np.linspace(-180, 180, 5)
    grid = np.ones((5, 5)) # constant displacement of 1
    
    # Vertices on a sphere of radius 1
    vertices = np.array([
        [1.0, 0.0, 0.0], # Equator, 0 lon
        [0.0, 1.0, 0.0], # Equator, 90 lon
        [0.0, 0.0, 1.0]  # North pole
    ])
    
    scale = 0.1
    displaced = displace_vertices(vertices, lats, lons, grid, scale)
    
    # Expected radius is 1.0 + 0.1 * 1.0 = 1.1
    radii = np.linalg.norm(displaced, axis=1)
    assert np.allclose(radii, 1.1)

def test_assign_vertex_colors():
    # Create a simple grid
    lats = np.linspace(-90, 90, 5)
    lons = np.linspace(-180, 180, 5)
    grid = np.zeros((5, 5)) 
    grid[2, 2] = 1.0 # Center point has value 1
    
    vertices = np.array([
        [1.0, 0.0, 0.0] # Corresponds roughly to center of grid if mapped correctly
    ])
    
    # Use a simple colormap or mock it? 
    # For now just check output shape and range
    colors = assign_vertex_colors(vertices, lats, lons, grid, colormap='viridis')
    
    assert colors.shape == (1, 3)
    assert np.all(colors >= 0.0) and np.all(colors <= 1.0)

@patch('matplotlib.pyplot.imread')
def test_assign_vertex_colors_image(mock_imread):
    # Mock a simple 2x2 image
    # Top-left (red), Top-right (green)
    # Bottom-left (blue), Bottom-right (white)
    img = np.array([
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        [[0.0, 0.0, 1.0], [1.0, 1.0, 1.0]]
    ])
    mock_imread.return_value = img
    
    # Vertices:
    # 1. North Pole (should map to top row, probably average or one of them depending on longitude)
    # 2. South Pole (bottom row)
    # 3. Equator, 0 lon (center of image horizontally, center vertically)
    
    vertices = np.array([
        [0.0, 0.0, 1.0],   # North Pole
        [0.0, 0.0, -1.0],  # South Pole
        [1.0, 0.0, 0.0]    # Equator, 0 lon
    ])
    
    colors = assign_vertex_colors_image(vertices, 'dummy.png')
    
    assert colors.shape == (3, 3)
    # Check bounds
    assert np.all(colors >= 0.0) and np.all(colors <= 1.0)
    
    # North pole -> lat 90 -> v=0. Should be top row.
    # South pole -> lat -90 -> v=height-1. Should be bottom row.
    # Equator -> lat 0 -> v=height/2.
    
    # Given nearest neighbor and 2x2 image:
    # v=0 -> row 0
    # v=1 -> row 1
    
    # North pole (0,0,1) -> lat 90 -> v=0.
    # Lon is undefined but usually 0 -> u=0.5 -> index 0 or 1.
    # Let's check if it picked a valid color from the image
    assert np.any(np.all(colors[0] == img.reshape(-1, 3), axis=1))


def test_dateline_nan_column():
    """Grids with NaN at -180° (common in GMT) must still colour correctly."""
    lats = np.linspace(-90, 90, 5)
    lons = np.linspace(-180, 180, 9)
    grid = np.ones((5, 9)) * 2.0  # uniform non-zero value
    grid[:, 0] = np.nan            # NaN at -180° (GMT convention)

    # Vertex at lon = -180 (negative x-axis on equator)
    vertices = np.array([
        [-1.0, 0.0, 0.0],  # lon = 180° (or -180° via atan2)
        [1.0, 0.0, 0.0],   # lon = 0° (control)
    ])

    colors = assign_vertex_colors(vertices, lats, lons, grid,
                                  colormap='viridis', vmin=0, vmax=4)

    # Both vertices should get the same colour since grid is uniform (2.0)
    # except for the NaN column which should be repaired.
    assert not np.any(np.isnan(colors)), "NaN in colours at dateline"
    assert np.allclose(colors[0], colors[1], atol=0.05), (
        f"Dateline vertex colour {colors[0]} differs from control {colors[1]}"
    )
