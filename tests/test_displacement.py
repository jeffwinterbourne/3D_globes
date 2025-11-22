import numpy as np
import pytest
from globe3d.displacement import displace_vertices, assign_vertex_colors

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
