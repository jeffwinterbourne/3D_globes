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


def test_displace_vertices_deeper_than_origin_error():
    """Check that ValueError is raised when new radius <= 0."""
    lats = np.linspace(-90, 90, 5)
    lons = np.linspace(-180, 180, 5)
    grid = np.ones((5, 5))  # constant displacement of 1
    
    # Vertices on a sphere of radius 1
    vertices = np.array([[1.0, 0.0, 0.0]])
    
    # A negative scale such that 1.0 + (-1.5 * 1.0) = -0.5 <= 0
    with pytest.raises(ValueError, match="Vertex displacement translates point"):
        displace_vertices(vertices, lats, lons, grid, scale=-1.5)




def test_displace_by_points_numpy():
    """Test displace_by_points using an (N, 2) numpy array of (lon, lat)."""
    from globe3d.displacement import displace_by_points
    
    # Vertices corresponding to:
    # 1. lon=10, lat=10 (close to point [10, 10])
    # 2. lon=20, lat=20 (far from point [10, 10])
    lat_1, lon_1 = np.radians(10.0), np.radians(10.0)
    v1 = np.array([
        10.0 * np.cos(lat_1) * np.cos(lon_1),
        10.0 * np.cos(lat_1) * np.sin(lon_1),
        10.0 * np.sin(lat_1)
    ])
    lat_2, lon_2 = np.radians(20.0), np.radians(20.0)
    v2 = np.array([
        10.0 * np.cos(lat_2) * np.cos(lon_2),
        10.0 * np.cos(lat_2) * np.sin(lon_2),
        10.0 * np.sin(lat_2)
    ])
    vertices = np.vstack([v1, v2])

    # Points data: [10, 10]
    points = np.array([[10.0, 10.0]])
    
    displaced = displace_by_points(
        vertices,
        points,
        displacement=1.5,
        radius_degrees=1.0
    )
    
    radii = np.linalg.norm(displaced, axis=1)
    assert np.allclose(radii[0], 11.5)
    assert np.allclose(radii[1], 10.0)

    # Test ValueError for invalid array shape
    with pytest.raises(ValueError, match="points_data array must have shape"):
        displace_by_points(vertices, np.array([10.0, 10.0]), displacement=1.5)


def test_displace_by_points_shapefile(tmp_path):
    """Test displace_by_points using a shapefile input, raising TypeError for non-points."""
    import geopandas as gpd
    from shapely.geometry import Point, LineString
    from globe3d.displacement import displace_by_points

    # 1. Valid Point shapefile
    gdf_ok = gpd.GeoDataFrame(geometry=[Point(10, 10)], crs="EPSG:4326")
    shp_ok = tmp_path / "pts_ok.shp"
    gdf_ok.to_file(shp_ok)

    lat_1, lon_1 = np.radians(10.0), np.radians(10.0)
    v1 = np.array([
        10.0 * np.cos(lat_1) * np.cos(lon_1),
        10.0 * np.cos(lat_1) * np.sin(lon_1),
        10.0 * np.sin(lat_1)
    ])
    
    displaced = displace_by_points(v1.reshape(1, -1), str(shp_ok), displacement=2.0, radius_degrees=1.0)
    assert np.allclose(np.linalg.norm(displaced, axis=1), 12.0)

    # 2. Invalid LineString shapefile (should raise TypeError)
    gdf_err = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (5, 5)])], crs="EPSG:4326")
    shp_err = tmp_path / "pts_err.shp"
    gdf_err.to_file(shp_err)

    with pytest.raises(TypeError, match="Geometries must be Points or MultiPoints"):
        displace_by_points(v1.reshape(1, -1), str(shp_err), displacement=2.0)


def test_displace_near_lines(tmp_path):
    """Test displace_near_lines buffers geometries correctly."""
    import geopandas as gpd
    from shapely.geometry import LineString
    from globe3d.displacement import displace_near_lines

    gdf = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (10, 0)])], crs="EPSG:4326")
    shp_path = tmp_path / "line.shp"
    gdf.to_file(shp_path)

    # Vertex 1: (lon=5, lat=0.1) -> within 0.5 degrees of the line
    lat_1, lon_1 = np.radians(0.1), np.radians(5.0)
    v1 = np.array([
        10.0 * np.cos(lat_1) * np.cos(lon_1),
        10.0 * np.cos(lat_1) * np.sin(lon_1),
        10.0 * np.sin(lat_1)
    ])

    # Vertex 2: (lon=5, lat=2.0) -> outside 0.5 degrees of the line
    lat_2, lon_2 = np.radians(2.0), np.radians(5.0)
    v2 = np.array([
        10.0 * np.cos(lat_2) * np.cos(lon_2),
        10.0 * np.cos(lat_2) * np.sin(lon_2),
        10.0 * np.sin(lat_2)
    ])

    vertices = np.vstack([v1, v2])

    displaced = displace_near_lines(vertices, str(shp_path), displacement=3.0, width_degrees=0.5)
    radii = np.linalg.norm(displaced, axis=1)
    assert np.allclose(radii[0], 13.0)
    assert np.allclose(radii[1], 10.0)


def test_displace_by_polygons(tmp_path):
    """Test displace_by_polygons and TypeError for non-polygon geometries."""
    import geopandas as gpd
    from shapely.geometry import Polygon, Point
    from globe3d.displacement import displace_by_polygons

    # 1. Valid Polygon shapefile
    poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    gdf_ok = gpd.GeoDataFrame(geometry=[poly], crs="EPSG:4326")
    shp_ok = tmp_path / "poly_ok.shp"
    gdf_ok.to_file(shp_ok)

    # Point 1: (lon=5, lat=5) -> inside
    lat_1, lon_1 = np.radians(5.0), np.radians(5.0)
    v1 = np.array([
        10.0 * np.cos(lat_1) * np.cos(lon_1),
        10.0 * np.cos(lat_1) * np.sin(lon_1),
        10.0 * np.sin(lat_1)
    ])

    # Point 2: (lon=20, lat=20) -> outside
    lat_2, lon_2 = np.radians(20.0), np.radians(20.0)
    v2 = np.array([
        10.0 * np.cos(lat_2) * np.cos(lon_2),
        10.0 * np.cos(lat_2) * np.sin(lon_2),
        10.0 * np.sin(lat_2)
    ])

    vertices = np.vstack([v1, v2])

    # Case A: displace inside
    disp_in = displace_by_polygons(vertices, str(shp_ok), displacement=4.0, displace_inside=True)
    radii_in = np.linalg.norm(disp_in, axis=1)
    assert np.allclose(radii_in[0], 14.0)
    assert np.allclose(radii_in[1], 10.0)

    # Case B: displace outside
    disp_out = displace_by_polygons(vertices, str(shp_ok), displacement=4.0, displace_inside=False)
    radii_out = np.linalg.norm(disp_out, axis=1)
    assert np.allclose(radii_out[0], 10.0)
    assert np.allclose(radii_out[1], 14.0)

    # 2. Invalid Point shapefile (should raise TypeError)
    gdf_err = gpd.GeoDataFrame(geometry=[Point(5, 5)], crs="EPSG:4326")
    shp_err = tmp_path / "poly_err.shp"
    gdf_err.to_file(shp_err)

    with pytest.raises(TypeError, match="Geometries must be Polygons or MultiPolygons"):
        displace_by_polygons(vertices, str(shp_err), displacement=4.0)


