import os
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from globe3d.grid import GeographicGrid
from globe3d.displacement import (
    GridDisplacer,
    PointDisplacer,
    LineDisplacer,
    PolygonDisplacer,
    GridColourer,
    ImageColourer,
    ConstantColourer,
    PointColourer,
    LineColourer,
    PolygonColourer,
    select_inward_facing,
    select_outward_facing,
    cartesian_to_spherical,
)
from globe3d.mesh import GlobeModel, generate_sphere_points_fibonacci

def test_grid_displacer():
    # Create a simple grid
    lats = np.linspace(-90, 90, 5)
    lons = np.linspace(-180, 180, 5)
    grid = np.ones((5, 5))  # constant displacement of 1
    
    g = GeographicGrid(lats, lons, grid)
    displacer = GridDisplacer(g)
    
    # Vertices on a sphere of radius 1
    vertices = np.array([
        [1.0, 0.0, 0.0],  # Equator, 0 lon
        [0.0, 1.0, 0.0],  # Equator, 90 lon
        [0.0, 0.0, 1.0]   # North pole
    ])
    
    scale = 0.1
    displaced = displacer(vertices, scale=scale)
    
    # Expected radius is 1.0 + 0.1 * 1.0 = 1.1
    radii = np.linalg.norm(displaced, axis=1)
    assert np.allclose(radii, 1.1)

def test_grid_displacer_reference_level():
    # Create a grid with values from 0 to 10
    lats = np.linspace(-90, 90, 5)
    lons = np.linspace(-180, 180, 5)
    grid = np.ones((5, 5)) * 6.0
    
    g = GeographicGrid(lats, lons, grid)
    # reference level of 5.0 -> displacement should be 6.0 - 5.0 = 1.0
    displacer = GridDisplacer(g, reference_level=5.0)
    
    vertices = np.array([
        [1.0, 0.0, 0.0],
    ])
    
    scale = 0.5
    displaced = displacer(vertices, scale=scale)
    
    # Expected radius is 1.0 + 0.5 * (6.0 - 5.0) = 1.5
    radii = np.linalg.norm(displaced, axis=1)
    assert np.allclose(radii, 1.5)

    # reference level of 7.0 -> displacement should be 6.0 - 7.0 = -1.0
    displacer_neg = GridDisplacer(g, reference_level=7.0)
    displaced_neg = displacer_neg(vertices, scale=scale)
    
    # Expected radius is 1.0 + 0.5 * (6.0 - 7.0) = 0.5
    radii_neg = np.linalg.norm(displaced_neg, axis=1)
    assert np.allclose(radii_neg, 0.5)

def test_grid_colourer():
    # Create a simple grid
    lats = np.linspace(-90, 90, 5)
    lons = np.linspace(-180, 180, 5)
    grid = np.zeros((5, 5)) 
    grid[2, 2] = 1.0  # Center point has value 1
    
    g = GeographicGrid(lats, lons, grid)
    colourer = GridColourer(g, colormap='viridis')
    
    vertices = np.array([
        [1.0, 0.0, 0.0]  # Corresponds roughly to center of grid if mapped correctly
    ])
    
    colors = colourer(vertices)
    
    assert colors.shape == (1, 3)
    assert np.all(colors >= 0.0) and np.all(colors <= 1.0)

@patch('matplotlib.pyplot.imread')
def test_image_colourer(mock_imread):
    # Mock a simple 2x2 image
    img = np.array([
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        [[0.0, 0.0, 1.0], [1.0, 1.0, 1.0]]
    ])
    mock_imread.return_value = img
    
    vertices = np.array([
        [0.0, 0.0, 1.0],   # North Pole
        [0.0, 0.0, -1.0],  # South Pole
        [1.0, 0.0, 0.0]    # Equator, 0 lon
    ])
    
    colourer = ImageColourer('dummy.png')
    colors = colourer(vertices)
    
    assert colors.shape == (3, 3)
    assert np.all(colors >= 0.0) and np.all(colors <= 1.0)
    assert np.any(np.all(colors[0] == img.reshape(-1, 3), axis=1))

def test_dateline_nan_column():
    """Grids with NaN at -180° (common in GMT) must still colour correctly."""
    lats = np.linspace(-90, 90, 5)
    lons = np.linspace(-180, 180, 9)
    grid = np.ones((5, 9)) * 2.0  # uniform non-zero value
    grid[:, 0] = np.nan            # NaN at -180° (GMT convention)

    g = GeographicGrid(lats, lons, grid)
    colourer = GridColourer(g, colormap='viridis', vmin=0, vmax=4)

    # Vertex at lon = -180 (negative x-axis on equator)
    vertices = np.array([
        [-1.0, 0.0, 0.0],  # lon = 180° (or -180° via atan2)
        [1.0, 0.0, 0.0],   # lon = 0° (control)
    ])

    colors = colourer(vertices)

    assert not np.any(np.isnan(colors)), "NaN in colours at dateline"
    assert np.allclose(colors[0], colors[1], atol=0.05)

def test_grid_displacer_deeper_than_origin_error():
    """Check that ValueError is raised when new radius <= 0."""
    lats = np.linspace(-90, 90, 5)
    lons = np.linspace(-180, 180, 5)
    grid = np.ones((5, 5))  # constant displacement of 1
    
    g = GeographicGrid(lats, lons, grid)
    displacer = GridDisplacer(g)
    
    # Vertices on a sphere of radius 1
    vertices = np.array([[1.0, 0.0, 0.0]])
    
    with pytest.raises(ValueError, match="Vertex displacement translates point"):
        displacer(vertices, scale=-1.5)

def test_point_displacer_numpy():
    """Test PointDisplacer using an (N, 2) numpy array of (lon, lat)."""
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

    points = np.array([[10.0, 10.0]])
    displacer = PointDisplacer(points, displacement=1.5, radius_degrees=1.0)
    displaced = displacer(vertices)
    
    radii = np.linalg.norm(displaced, axis=1)
    assert np.allclose(radii[0], 11.5)
    assert np.allclose(radii[1], 10.0)

    # Test ValueError for invalid array shape
    with pytest.raises(ValueError, match="points_data array must have shape"):
        PointDisplacer(np.array([10.0, 10.0]), displacement=1.5)

def test_point_displacer_shapefile(tmp_path):
    """Test PointDisplacer using a shapefile input, raising TypeError for non-points."""
    import geopandas as gpd
    from shapely.geometry import Point, LineString

    gdf_ok = gpd.GeoDataFrame(geometry=[Point(10, 10)], crs="EPSG:4326")
    shp_ok = tmp_path / "pts_ok.shp"
    gdf_ok.to_file(shp_ok)

    lat_1, lon_1 = np.radians(10.0), np.radians(10.0)
    v1 = np.array([
        10.0 * np.cos(lat_1) * np.cos(lon_1),
        10.0 * np.cos(lat_1) * np.sin(lon_1),
        10.0 * np.sin(lat_1)
    ])
    
    displacer = PointDisplacer(str(shp_ok), displacement=2.0, radius_degrees=1.0)
    displaced = displacer(v1.reshape(1, -1))
    assert np.allclose(np.linalg.norm(displaced, axis=1), 12.0)

    gdf_err = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (5, 5)])], crs="EPSG:4326")
    shp_err = tmp_path / "pts_err.shp"
    gdf_err.to_file(shp_err)

    with pytest.raises(TypeError, match="Geometries must be Points or MultiPoints"):
        PointDisplacer(str(shp_err), displacement=2.0)

def test_line_displacer(tmp_path):
    """Test LineDisplacer buffers geometries correctly."""
    import geopandas as gpd
    from shapely.geometry import LineString

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

    displacer = LineDisplacer(str(shp_path), displacement=3.0, width_degrees=0.5)
    displaced = displacer(vertices)
    radii = np.linalg.norm(displaced, axis=1)
    assert np.allclose(radii[0], 13.0)
    assert np.allclose(radii[1], 10.0)

def test_polygon_displacer(tmp_path):
    """Test PolygonDisplacer and TypeError for non-polygon geometries."""
    import geopandas as gpd
    from shapely.geometry import Polygon, Point

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
    displacer_in = PolygonDisplacer(str(shp_ok), displacement=4.0, displace_inside=True)
    disp_in = displacer_in(vertices)
    radii_in = np.linalg.norm(disp_in, axis=1)
    assert np.allclose(radii_in[0], 14.0)
    assert np.allclose(radii_in[1], 10.0)

    # Case B: displace outside
    displacer_out = PolygonDisplacer(str(shp_ok), displacement=4.0, displace_inside=False)
    disp_out = displacer_out(vertices)
    radii_out = np.linalg.norm(disp_out, axis=1)
    assert np.allclose(radii_out[0], 10.0)
    assert np.allclose(radii_out[1], 14.0)

    gdf_err = gpd.GeoDataFrame(geometry=[Point(5, 5)], crs="EPSG:4326")
    shp_err = tmp_path / "poly_err.shp"
    gdf_err.to_file(shp_err)

    with pytest.raises(TypeError, match="Geometries must be Polygons or MultiPolygons"):
        PolygonDisplacer(str(shp_err), displacement=4.0)

def test_parallel_displacement(tmp_path):
    """Test that all displacement functions yield identical results with num_threads > 1."""
    import geopandas as gpd
    from shapely.geometry import Point, LineString, Polygon

    lats = np.linspace(-90, 90, 5)
    lons = np.linspace(-180, 180, 5)
    grid = np.ones((5, 5))
    vertices = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0]
    ])

    g = GeographicGrid(lats, lons, grid)

    # 1. GridDisplacer
    disp_seq = GridDisplacer(g, num_threads=1)(vertices, 0.1)
    disp_par = GridDisplacer(g, num_threads=2)(vertices, 0.1)
    assert np.allclose(disp_seq, disp_par)

    # 2. GridColourer
    col_seq = GridColourer(g, num_threads=1)(vertices)
    col_par = GridColourer(g, num_threads=2)(vertices)
    assert np.allclose(col_seq, col_par)

    # 3. PointDisplacer
    pts_data = np.array([[0.0, 0.0], [90.0, 0.0]])
    disp_pts_seq = PointDisplacer(pts_data, displacement=1.0, radius_degrees=1.0, num_threads=1)(vertices)
    disp_pts_par = PointDisplacer(pts_data, displacement=1.0, radius_degrees=1.0, num_threads=2)(vertices)
    assert np.allclose(disp_pts_seq, disp_pts_par)

    # 4. LineDisplacer
    gdf_line = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (10, 0)])], crs="EPSG:4326")
    shp_line = tmp_path / "line_par.shp"
    gdf_line.to_file(shp_line)
    disp_line_seq = LineDisplacer(str(shp_line), displacement=1.0, width_degrees=1.0, num_threads=1)(vertices)
    disp_line_par = LineDisplacer(str(shp_line), displacement=1.0, width_degrees=1.0, num_threads=2)(vertices)
    assert np.allclose(disp_line_seq, disp_line_par)

    # 5. PolygonDisplacer
    poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    gdf_poly = gpd.GeoDataFrame(geometry=[poly], crs="EPSG:4326")
    shp_poly = tmp_path / "poly_par.shp"
    gdf_poly.to_file(shp_poly)
    disp_poly_seq = PolygonDisplacer(str(shp_poly), displacement=1.0, displace_inside=True, num_threads=1)(vertices)
    disp_poly_par = PolygonDisplacer(str(shp_poly), displacement=1.0, displace_inside=True, num_threads=2)(vertices)
    assert np.allclose(disp_poly_seq, disp_poly_par)

def test_select_inward_outward_facing_vertices():
    """Verify that selection functions correctly identify inward vs outward facing vertices on concentric spheres."""
    ov, of = generate_sphere_points_fibonacci(100, radius=20.0)
    
    inward = select_inward_facing(ov, of)
    outward = select_outward_facing(ov, of)
    
    assert len(inward) == 0
    assert len(outward) == len(ov)

    of_inverted = of[:, [0, 2, 1]]
    inward_inv = select_inward_facing(ov, of_inverted)
    outward_inv = select_outward_facing(ov, of_inverted)
    
    assert len(inward_inv) == len(ov)
    assert len(outward_inv) == 0

def test_constant_colourer_and_model_coloring():
    """Verify ConstantColourer modifies correct subsets of colors via GlobeModel."""
    vertices = np.array([
        [10.0, 0.0, 0.0],  # vertex 0
        [-10.0, 0.0, 0.0], # vertex 1
        [0.0, 10.0, 0.0],  # vertex 2
        [0.0, -10.0, 0.0], # vertex 3
    ], dtype=np.float64)
    
    faces = np.array([[0, 2, 1], [0, 1, 3]])
    model = GlobeModel(_vertices=vertices, _faces=faces)
    
    # Custom selection function
    def dummy_select(v, f, **kwargs):
        return np.where(v[:, 0] > 0)[0]
        
    colourer = ConstantColourer([1.0, 0.5, 0.0])
    model.colour(colourer, selection=dummy_select)
    
    assert np.allclose(model.outer_colors[0], [1.0, 0.5, 0.0])
    assert np.allclose(model.outer_colors[1], [1.0, 1.0, 1.0]) # Uncolored remains white
    assert np.allclose(model.outer_colors[2], [1.0, 1.0, 1.0])
    assert np.allclose(model.outer_colors[3], [1.0, 1.0, 1.0])

def test_cartesian_to_spherical():
    """Verify that cartesian_to_spherical computes correct r, lat, lon values."""
    # Single point test (1D array)
    v_1d = np.array([0.0, 10.0, 0.0])
    r, lat, lon = cartesian_to_spherical(v_1d)
    assert pytest.approx(r) == 10.0
    assert pytest.approx(lat) == 0.0
    assert pytest.approx(lon) == 90.0

    # Multi-point test (2D array)
    vertices = np.array([
        [1.0, 0.0, 0.0],  # Equator, 0 lon
        [0.0, 0.0, 1.0],  # North Pole
        [0.0, 0.0, -1.0], # South Pole
        [0.0, 0.0, 0.0]   # Origin
    ])
    r_arr, lat_arr, lon_arr = cartesian_to_spherical(vertices)

    assert r_arr.shape == (4,)
    assert lat_arr.shape == (4,)
    assert lon_arr.shape == (4,)

    assert np.allclose(r_arr, [1.0, 1.0, 1.0, 0.0])
    assert np.allclose(lat_arr, [0.0, 90.0, -90.0, 0.0])
    assert pytest.approx(lon_arr[0]) == 0.0


def test_point_colourer_shapes(tmp_path):
    """Test PointColourer with different marker shapes and custom callable."""
    # Vertex at (lon=10, lat=10)
    lat_rad, lon_rad = np.radians(10.0), np.radians(10.0)
    v1 = np.array([
        10.0 * np.cos(lat_rad) * np.cos(lon_rad),
        10.0 * np.cos(lat_rad) * np.sin(lon_rad),
        10.0 * np.sin(lat_rad)
    ])
    
    # Vertex at (lon=10.5, lat=10.0) -> offset in lon by 0.5 degrees
    lon_rad2 = np.radians(10.5)
    v2 = np.array([
        10.0 * np.cos(lat_rad) * np.cos(lon_rad2),
        10.0 * np.cos(lat_rad) * np.sin(lon_rad2),
        10.0 * np.sin(lat_rad)
    ])
    
    # Vertex at (lon=10.0, lat=12.0) -> offset in lat by 2.0 degrees (outside 1.0 deg radius)
    lat_rad3 = np.radians(12.0)
    v3 = np.array([
        10.0 * np.cos(lat_rad3) * np.cos(lon_rad),
        10.0 * np.cos(lat_rad3) * np.sin(lon_rad),
        10.0 * np.sin(lat_rad3)
    ])

    vertices = np.vstack([v1, v2, v3])
    points = np.array([[10.0, 10.0]])
    
    c_red = [1.0, 0.0, 0.0]
    c_white = [1.0, 1.0, 1.0]

    # Test circular shape
    colourer_circle = PointColourer(points, color=c_red, background_color=c_white, radius_degrees=1.0, marker_shape='circle')
    colors = colourer_circle(vertices)
    assert np.allclose(colors[0], c_red)
    assert np.allclose(colors[1], c_red)
    assert np.allclose(colors[2], c_white)

    # Test square shape
    colourer_square = PointColourer(points, color=c_red, background_color=c_white, radius_degrees=1.0, marker_shape='square')
    colors = colourer_square(vertices)
    assert np.allclose(colors[0], c_red)
    assert np.allclose(colors[1], c_red)
    assert np.allclose(colors[2], c_white)

    # Test triangle shape
    colourer_triangle = PointColourer(points, color=c_red, background_color=c_white, radius_degrees=1.0, marker_shape='triangle')
    colors = colourer_triangle(vertices)
    assert np.allclose(colors[0], c_red)
    assert np.allclose(colors[1], c_red)
    assert np.allclose(colors[2], c_white)

    # Test cross shape
    colourer_cross = PointColourer(points, color=c_red, background_color=c_white, radius_degrees=1.0, marker_shape='cross', marker_thickness=0.2)
    colors = colourer_cross(vertices)
    assert np.allclose(colors[0], c_red)
    assert np.allclose(colors[1], c_red)
    assert np.allclose(colors[2], c_white)

    # Test star shape
    colourer_star = PointColourer(points, color=c_red, background_color=c_white, radius_degrees=1.0, marker_shape='star')
    colors = colourer_star(vertices)
    assert np.allclose(colors[0], c_red)
    assert np.allclose(colors[2], c_white)

    # Test custom callable shape
    def custom_marker(x_deg, y_deg, radius_degrees):
        return x_deg < 0

    colourer_custom = PointColourer(points, color=c_red, background_color=c_white, radius_degrees=1.0, marker_shape=custom_marker)
    colors = colourer_custom(vertices)
    assert np.allclose(colors[0], c_white)
    assert np.allclose(colors[1], c_white)
    assert np.allclose(colors[2], c_white)


def test_line_colourer(tmp_path):
    """Test LineColourer works with shapefile and GeoDataFrame input."""
    import geopandas as gpd
    from shapely.geometry import LineString

    gdf = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (10, 0)])], crs="EPSG:4326")
    shp_path = tmp_path / "test_line_colour.shp"
    gdf.to_file(shp_path)

    # Vertex 1: (lon=5, lat=0.1) -> near line
    lat_1, lon_1 = np.radians(0.1), np.radians(5.0)
    v1 = np.array([
        10.0 * np.cos(lat_1) * np.cos(lon_1),
        10.0 * np.cos(lat_1) * np.sin(lon_1),
        10.0 * np.sin(lat_1)
    ])

    # Vertex 2: (lon=5, lat=2.0) -> far from line
    lat_2, lon_2 = np.radians(2.0), np.radians(5.0)
    v2 = np.array([
        10.0 * np.cos(lat_2) * np.cos(lon_2),
        10.0 * np.cos(lat_2) * np.sin(lon_2),
        10.0 * np.sin(lat_2)
    ])

    vertices = np.vstack([v1, v2])
    c_red = [1.0, 0.0, 0.0]
    c_white = [1.0, 1.0, 1.0]

    # Test path input
    lc_path = LineColourer(str(shp_path), color=c_red, background_color=c_white, width_degrees=0.5)
    colors = lc_path(vertices)
    assert np.allclose(colors[0], c_red)
    assert np.allclose(colors[1], c_white)

    # Test GeoDataFrame input
    lc_gdf = LineColourer(gdf, color=c_red, background_color=c_white, width_degrees=0.5)
    colors_gdf = lc_gdf(vertices)
    assert np.allclose(colors_gdf[0], c_red)
    assert np.allclose(colors_gdf[1], c_white)


def test_polygon_colourer(tmp_path):
    """Test PolygonColourer works inside and outside with shapefile and GeoDataFrame input."""
    import geopandas as gpd
    from shapely.geometry import Polygon

    poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    gdf = gpd.GeoDataFrame(geometry=[poly], crs="EPSG:4326")
    shp_path = tmp_path / "test_poly_colour.shp"
    gdf.to_file(shp_path)

    # Vertex 1: (lon=5, lat=5) -> inside
    lat_1, lon_1 = np.radians(5.0), np.radians(5.0)
    v1 = np.array([
        10.0 * np.cos(lat_1) * np.cos(lon_1),
        10.0 * np.cos(lat_1) * np.sin(lon_1),
        10.0 * np.sin(lat_1)
    ])

    # Vertex 2: (lon=20, lat=20) -> outside
    lat_2, lon_2 = np.radians(20.0), np.radians(20.0)
    v2 = np.array([
        10.0 * np.cos(lat_2) * np.cos(lon_2),
        10.0 * np.cos(lat_2) * np.sin(lon_2),
        10.0 * np.sin(lat_2)
    ])

    vertices = np.vstack([v1, v2])
    c_red = [1.0, 0.0, 0.0]
    c_white = [1.0, 1.0, 1.0]

    # Test flood inside
    pc_in = PolygonColourer(gdf, color=c_red, background_color=c_white, flood_inside=True)
    colors_in = pc_in(vertices)
    assert np.allclose(colors_in[0], c_red)
    assert np.allclose(colors_in[1], c_white)

    # Test flood outside
    pc_out = PolygonColourer(gdf, color=c_red, background_color=c_white, flood_inside=False)
    colors_out = pc_out(vertices)
    assert np.allclose(colors_out[0], c_white)
    assert np.allclose(colors_out[1], c_red)


def test_parallel_colouring(tmp_path):
    """Test that coloring classes give identical results with single and multi-threading."""
    import geopandas as gpd
    from shapely.geometry import LineString, Polygon

    vertices = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0]
    ])

    c_red = [1.0, 0.0, 0.0]
    c_white = [1.0, 1.0, 1.0]

    # 1. PointColourer
    pts = np.array([[0.0, 0.0], [90.0, 0.0]])
    pc_seq = PointColourer(pts, color=c_red, background_color=c_white, radius_degrees=1.0, num_threads=1)(vertices)
    pc_par = PointColourer(pts, color=c_red, background_color=c_white, radius_degrees=1.0, num_threads=2)(vertices)
    assert np.allclose(pc_seq, pc_par)

    # 2. LineColourer
    gdf_line = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (10, 0)])], crs="EPSG:4326")
    lc_seq = LineColourer(gdf_line, color=c_red, background_color=c_white, width_degrees=1.0, num_threads=1)(vertices)
    lc_par = LineColourer(gdf_line, color=c_red, background_color=c_white, width_degrees=1.0, num_threads=2)(vertices)
    assert np.allclose(lc_seq, lc_par)

    # 3. PolygonColourer
    poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    gdf_poly = gpd.GeoDataFrame(geometry=[poly], crs="EPSG:4326")
    pc_poly_seq = PolygonColourer(gdf_poly, color=c_red, background_color=c_white, flood_inside=True, num_threads=1)(vertices)
    pc_poly_par = PolygonColourer(gdf_poly, color=c_red, background_color=c_white, flood_inside=True, num_threads=2)(vertices)
    assert np.allclose(pc_poly_seq, pc_poly_par)
