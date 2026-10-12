"""Unit tests for filament optical mixing, palettes, and banded colormaps."""

import numpy as np
import pytest
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import trimesh
from globe3d.filaments import (
    parse_color,
    color_to_hex,
    rgb_to_lab,
    delta_e_lab,
    mix_filament_pair,
    mix_filament_pairs_vectorized,
    mix_filaments,
    create_filament_palette,
    match_filament_color,
    create_banded_colormap,
    create_elevation_banded_colormap,
    apply_banded_colormap,
    plot_filament_palette,
    plot_banded_colormap_preview,
    InteractiveColormapBuilder,
    FILAMENT_PRESETS,
)
from globe3d.plot import plot_globe_preview


def test_parse_color():
    assert parse_color("#ff0000") == (255, 0, 0)
    assert parse_color("00ff00") == (0, 255, 0)
    assert parse_color("#00f") == (0, 0, 255)
    assert parse_color((255, 128, 0)) == (255, 128, 0)
    assert parse_color([1.0, 0.5, 0.0]) == (255, 128, 0)
    assert parse_color({"color": "#00ffff"}) == (0, 255, 255)
    assert parse_color({"rgb": (10, 20, 30)}) == (10, 20, 30)
    assert parse_color({"hex": "#123456"}) == (18, 52, 86)

    with pytest.raises(ValueError):
        parse_color("invalid_color")
    with pytest.raises(ValueError):
        parse_color((1, 2))


def test_color_to_hex():
    assert color_to_hex((255, 0, 128)) == "#ff0080"
    assert color_to_hex("#00ff00") == "#00ff00"


def test_rgb_to_lab_and_delta_e():
    lab_white = rgb_to_lab((255, 255, 255))
    assert abs(lab_white[0] - 100.0) < 1.0  # L* should be ~100
    lab_black = rgb_to_lab((0, 0, 0))
    assert abs(lab_black[0] - 0.0) < 1.0  # L* should be ~0

    # Distance to itself is 0
    assert delta_e_lab((100, 150, 200), (100, 150, 200)) == 0.0

    # Red vs Pink should be closer than Red vs Blue
    dist_pink = delta_e_lab((255, 0, 0), (255, 150, 150))
    dist_blue = delta_e_lab((255, 0, 0), (0, 0, 255))
    assert dist_pink < dist_blue


def test_mix_filament_pair_endpoints():
    c1 = (0, 33, 133)
    c2 = (252, 211, 0)

    # Endpoint exactness
    assert mix_filament_pair(c1, c2, ratio=0.0) == c1
    assert mix_filament_pair(c1, c2, ratio=-0.1) == c1
    assert mix_filament_pair(c1, c2, ratio=1.0) == c2
    assert mix_filament_pair(c1, c2, ratio=1.5) == c2


def test_mix_filament_pair_blue_yellow_yields_green():
    # Canonical Kubelka-Munk test: Blue + Yellow = Green (not gray!)
    blue = (0, 33, 133)
    yellow = (252, 211, 0)
    green = mix_filament_pair(blue, yellow, ratio=0.5)

    assert green == (47, 141, 56)
    # Green channel should clearly dominate over red and blue
    assert green[1] > green[0]
    assert green[1] > green[2]


def test_mix_filament_pair_grayscale():
    # Mixing two neutral grays should produce linear neutral gray
    gray1 = (50, 50, 50)
    gray2 = (200, 200, 200)
    mixed = mix_filament_pair(gray1, gray2, ratio=0.5)
    assert mixed == (125, 125, 125)


def test_mix_filament_pairs_vectorized():
    blue = np.array([0, 33, 133])
    yellow = np.array([252, 211, 0])

    c1 = np.tile(blue, (5, 1))
    c2 = np.tile(yellow, (5, 1))
    ratios = np.array([0.0, 0.25, 0.5, 0.75, 1.0])

    vec_res = mix_filament_pairs_vectorized(c1, c2, ratios)
    assert vec_res.shape == (5, 3)

    # Compare each entry with scalar mix_filament_pair
    for i, r in enumerate(ratios):
        scalar_res = mix_filament_pair(tuple(blue), tuple(yellow), ratio=float(r))
        assert tuple(vec_res[i]) == scalar_res


def test_mix_filaments_single_and_multi():
    c = (0, 255, 255)
    m = (255, 0, 255)
    y = (255, 255, 0)

    # Single
    assert mix_filaments([c]) == c

    # Multi equal weights
    mixed = mix_filaments([c, y], [0.5, 0.5])
    assert mixed[1] > mixed[0]  # Greenish

    # Transmission distances scaling
    # Higher td = more translucent = lower effective weighting
    res_opaque_y = mix_filaments([c, y], [0.5, 0.5], transmission_distances=[1.0, 0.5])
    res_translucent_y = mix_filaments([c, y], [0.5, 0.5], transmission_distances=[1.0, 2.0])
    # Opaque yellow should pull color more toward yellow (higher red channel)
    assert res_opaque_y[0] > res_translucent_y[0]


def test_create_filament_palette():
    palette = create_filament_palette("CMYKW", ratios=[0.33, 0.5, 0.67])
    assert len(palette) > 10

    for item in palette:
        assert "name" in item
        assert "color" in item
        assert "hex" in item
        assert "recipe" in item
        assert len(item["color"]) == 3
        assert item["hex"].startswith("#")

    # Custom spools
    custom_spools = [
        {"name": "Navy", "color": (10, 30, 80)},
        {"name": "Gold", "color": (220, 180, 20)},
        {"name": "Snow", "color": (250, 250, 250)},
    ]
    custom_pal = create_filament_palette(custom_spools)
    assert len(custom_pal) >= 3


def test_match_filament_color():
    palette = create_filament_palette("CMYKW")
    target_green = (50, 160, 50)
    match = match_filament_color(target_green, palette)

    assert "color" in match
    assert "delta_e" in match
    assert match["delta_e"] < 40.0  # Should find a close green blend


def test_create_banded_colormap():
    colors = ["#0000ff", "#00ffff", "#00ff00", "#ff0000"]
    internal_boundaries = [-1000.0, 0.0, 1000.0]

    cmap, norm = create_banded_colormap(colors, internal_boundaries)
    assert cmap.N == 4

    # Explicit bracket boundaries
    explicit_boundaries = [-5000.0, -1000.0, 0.0, 1000.0, 5000.0]
    cmap2, norm2 = create_banded_colormap(colors, explicit_boundaries)
    assert cmap2.N == 4

    with pytest.raises(ValueError):
        create_banded_colormap(colors, [0.0])


def test_create_elevation_banded_colormap():
    cmap, norm, band_specs = create_elevation_banded_colormap("CMYKW")
    assert cmap.N == 8
    assert len(band_specs) == 8

    for b in band_specs:
        assert "name" in b
        assert "range" in b
        assert "color" in b
        assert "hex" in b
        assert "recipe" in b


def test_apply_banded_colormap():
    grid = np.array([
        [-5000.0, -3000.0],
        [-100.0, 1200.0],
    ])
    cmap, norm, band_specs = create_elevation_banded_colormap()
    colors = [b["color"] for b in band_specs]
    boundaries = [-4000.0, -2000.0, -200.0, 0.0, 500.0, 1500.0, 3000.0]

    rgb_img = apply_banded_colormap(grid, colors, boundaries)
    assert rgb_img.shape == (2, 2, 3)
    assert rgb_img.dtype == np.uint8
    # Top-left should be abyssal plain color
    assert tuple(rgb_img[0, 0]) == band_specs[0]["color"]


def test_plot_helpers():
    palette = create_filament_palette("CMYKW")[:5]
    ax = plot_filament_palette(palette)
    assert ax is not None
    plt.close("all")

    cmap, norm, bands = create_elevation_banded_colormap()
    labels = [b["name"] for b in bands]
    ax_cb = plot_banded_colormap_preview(
        cmap, norm, [-4000, -2000, -200, 0, 500, 1500, 3000], band_labels=labels
    )
    assert ax_cb is not None
    plt.close("all")


def test_plot_globe_preview():
    # Create simple dummy sphere trimesh
    sphere = trimesh.creation.icosphere(subdivisions=2, radius=10.0)
    sphere.visual.vertex_colors = np.random.randint(0, 255, (len(sphere.vertices), 4), dtype=np.uint8)

    ax = plot_globe_preview(sphere, elev=15.0, azim=45.0, sample_size=50)
    assert ax is not None
    plt.close("all")


def test_create_filament_palette_strict_4_layer():
    palette = create_filament_palette("TERRAIN_4", total_layers=4)
    # 4 spools combined across 4 layers = binom(4+4-1, 4) = binom(7,4) = 35 combinations
    assert len(palette) == 35

    for item in palette:
        assert "name" in item
        assert "layers" in item
        assert "color" in item
        assert "hex" in item
        assert "recipe" in item

        # Verify integer layer sums
        total_layers = sum(r.get("layers", 0) for r in item["recipe"])
        assert total_layers == 4

        # Verify weight sums to 1.0
        total_weight = sum(r["weight"] for r in item["recipe"])
        assert abs(total_weight - 1.0) < 1e-4

    # Verify pure spools exist
    names = [item["name"] for item in palette]
    assert "Brown" in names
    assert "Dark Blue" in names
    assert "White" in names
    assert "Dark Green" in names


def test_plot_filament_palette_show_index():
    palette = create_filament_palette("TERRAIN_4", total_layers=4)[:4]

    # Test with show_index=True (default)
    fig, ax = plt.subplots()
    plot_filament_palette(palette, show_index=True, ax=ax)
    texts_idx = [t.get_text() for t in ax.texts]
    assert texts_idx == ["0", "1", "2", "3"]
    plt.close("all")

    # Test with show_index=False (shows hex code)
    fig, ax = plt.subplots()
    plot_filament_palette(palette, show_index=False, ax=ax)
    texts_hex = [t.get_text() for t in ax.texts]
    assert all(h.startswith("#") for h in texts_hex)
    plt.close("all")


def test_interactive_colormap_builder():
    palette = create_filament_palette("TERRAIN_4", total_layers=4)
    dem_dummy = np.linspace(-5000, 5000, 400).reshape((20, 20))

    # Initialize builder
    builder = InteractiveColormapBuilder(palette, dem_grid=dem_dummy)
    assert builder.container is not None
    assert len(builder.color_dropdowns) == 8
    assert len(builder.thresh_inputs) == 8

    # Verify get_colormap returns correct structures
    cmap, norm, colors, thresholds, band_names = builder.get_colormap()
    assert cmap.N == 8
    assert len(colors) == 8
    assert len(thresholds) == 7
    assert len(band_names) == 8
    assert band_names[0] == "Abyssal"
    assert thresholds[0] == -2500

    # Test changing a dropdown value
    builder.color_dropdowns[0].value = 3
    builder._on_change(None)
    cmap2, norm2, colors2, thresholds2, band_names2 = builder.get_colormap()
    assert colors2[0] == palette[3]["color"]

    # Verify single-image preview widget
    assert hasattr(builder, "preview_image")
    assert len(builder.preview_image.value) > 0

    # Test Add Band
    builder._on_add_band(None)
    assert len(builder.bands_config) == 9
    assert len(builder.rows) == 9
    assert len(builder.preview_image.value) > 0

    # Test Delete Band
    builder._delete_band(2)
    assert len(builder.bands_config) == 8
    assert len(builder.rows) == 8

    # Test Sort Bands
    builder.thresh_inputs[0].value = 8000
    builder._on_sort_bands(None)
    assert builder.bands_config[-2]["threshold"] == 8000

    # Test Reset Bands
    builder._on_reset_bands(None)
    assert len(builder.bands_config) == 8
    assert builder.bands_config[0]["threshold"] == -2500

    # Test custom bands
    custom_bands = [
        {"index": 0, "threshold": 0, "name": "Sea"},
        {"index": 1, "threshold": None, "name": "Land"},
    ]
    custom_builder = InteractiveColormapBuilder(palette, default_bands=custom_bands)
    cmap_c, norm_c, colors_c, thresh_c, names_c = custom_builder.get_colormap()
    assert cmap_c.N == 2
    assert len(thresh_c) == 1
    assert names_c == ["Sea", "Land"]
    plt.close("all")
