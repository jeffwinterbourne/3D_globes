"""Unit tests for the image preprocessing and spherical SVG symbol module."""

import pytest
import numpy as np
from PIL import Image
from globe3d.image import (
    _ensure_rgba_color,
    _normalize_lon_180,
    destination_point,
    great_circle_interpolate,
    add_svg_symbol_spherical,
    add_pole_markers,
    undo_hillshading,
    simplify_image_median,
    simplify_image_bilateral,
    simplify_colors,
    render_2d_array_as_rgb,
)


def test_ensure_rgba_color():
    """Verifies color normalization and clamping."""
    assert _ensure_rgba_color((255, 0, 0)) == (255, 0, 0, 255)
    assert _ensure_rgba_color((0.0, 1.0, 0.0)) == (0, 255, 0, 255)
    assert _ensure_rgba_color((100, 150, 200, 128)) == (100, 150, 200, 128)
    with pytest.raises(ValueError):
        _ensure_rgba_color((255, 0))


def test_normalize_lon_180():
    """Verifies longitude wrapping to (-180, 180]."""
    assert _normalize_lon_180(0.0) == 0.0
    assert _normalize_lon_180(180.0) == 180.0
    assert _normalize_lon_180(-180.0) == 180.0
    assert _normalize_lon_180(190.0) == -170.0
    assert _normalize_lon_180(-190.0) == 170.0


def test_destination_point():
    """Verifies spherical destination point calculation."""
    # Moving 10 degrees north from equator
    lat, lon = destination_point(0.0, 0.0, 10.0, 0.0)
    assert pytest.approx(lat, abs=1e-3) == 10.0
    assert pytest.approx(lon, abs=1e-3) == 0.0

    # Moving 10 degrees east from equator
    lat, lon = destination_point(0.0, 0.0, 10.0, 90.0)
    assert pytest.approx(lat, abs=1e-3) == 0.0
    assert pytest.approx(lon, abs=1e-3) == 10.0


def test_great_circle_interpolate():
    """Verifies great circle arc interpolation."""
    pts = great_circle_interpolate((0.0, 0.0), (0.0, 10.0), 3)
    assert len(pts) == 5
    assert pts[0] == (0.0, 0.0)
    assert pts[-1] == (0.0, 10.0)
    # Midpoint should be approximately 0 lat, 5 lon
    assert pytest.approx(pts[2][0], abs=1e-3) == 0.0
    assert pytest.approx(pts[2][1], abs=1e-3) == 5.0


def test_add_svg_symbol_spherical():
    """Verifies rendering SVG symbols on equirectangular images."""
    base = Image.new("RGB", (360, 180), (50, 50, 50))
    result = add_svg_symbol_spherical(
        base,
        svg_source="star",
        center_lat_deg=0.0,
        center_lon_deg=0.0,
        symbol_radius_degrees=10.0,
        fill_color=(255, 0, 0, 255),
    )
    assert isinstance(result, Image.Image)
    assert result.size == (360, 180)
    # The center pixel at lat 0, lon 0 should be red
    # In 360x180: x = 180, y = 90
    px = result.getpixel((180, 90))
    assert px[0] == 255
    assert px[1] == 0
    assert px[2] == 0


def test_add_pole_markers():
    """Verifies adding North and South pole markers."""
    base = Image.new("RGB", (360, 180), (100, 100, 100))
    result = add_pole_markers(base, marker_size_degrees=5.0)
    assert isinstance(result, Image.Image)
    assert result.size == (360, 180)


def test_undo_hillshading():
    """Verifies hillshade reduction in HSL space."""
    # Create an image with varying lightness
    img = Image.new("RGB", (50, 50), (200, 100, 50))
    flat = undo_hillshading(img, strength=0.8)
    assert isinstance(flat, Image.Image)
    assert flat.size == (50, 50)


def test_simplify_image_median_and_bilateral():
    """Verifies median and bilateral image filtering."""
    img = Image.new("RGB", (50, 50), (100, 150, 200))
    med = simplify_image_median(img, kernel_size=5)
    assert isinstance(med, Image.Image)

    bil = simplify_image_bilateral(img, d=5, sigma_color=50, sigma_space=50)
    assert isinstance(bil, Image.Image)


def test_simplify_colors():
    """Verifies quantization to target RGB filament palette."""
    img = Image.new("RGB", (20, 20), (250, 10, 10))  # Almost pure red
    palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    quantized = simplify_colors(img, palette)
    # Every pixel should map exactly to (255, 0, 0)
    px = quantized.getpixel((10, 10))
    assert px == (255, 0, 0)


def test_render_2d_array_as_rgb():
    """Verifies converting 2D scalar arrays to RGB."""
    arr = np.array([
        [-10.0, 5.0],
        [15.0, 50.0],
    ])
    colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0)]
    boundaries = [0.0, 20.0]
    rgb = render_2d_array_as_rgb(arr, colors, boundaries)
    assert rgb.shape == (2, 2, 3)
    # -10 < 0 -> Blue (0, 0, 255)
    assert tuple(rgb[0, 0]) == (0, 0, 255)
    # 5.0 in [0, 20) -> Green (0, 255, 0)
    assert tuple(rgb[0, 1]) == (0, 255, 0)
    # 50.0 >= 20 -> Red (255, 0, 0)
    assert tuple(rgb[1, 1]) == (255, 0, 0)
