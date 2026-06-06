"""Tests for the new high-level GlobeModel API (v4.0 refactor).

Covers:
- Unified constructor (method, hollow, inner_ratio, inner_n_points)
- _MeshProxy (model.inner / model.outer) with displace() and colour()
- configure_magnets()
- export() and export_hemispheres()
- calculate_displacement_scale with grid_units
"""

import os
import numpy as np
import pytest
import trimesh

from globe3d.mesh import GlobeModel
from globe3d.grid import GeographicGrid
from globe3d.displacement import (
    GridDisplacer,
    ConstantColourer,
    GridColourer,
    calculate_displacement_scale,
    _UNIT_TO_METERS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_grid():
    """A 5×5 grid of constant 1.0 values spanning the globe."""
    lats = np.linspace(-90, 90, 5)
    lons = np.linspace(-180, 180, 5)
    grid = np.ones((5, 5)) * 1.5
    return GeographicGrid(lats, lons, grid)


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------

class TestConstructor:

    def test_fibonacci_default(self):
        """Default constructor creates a Fibonacci sphere."""
        model = GlobeModel(n_points=200, radius=20.0)
        assert model.outer_vertices.shape == (200, 3)
        assert model.outer_faces.shape[1] == 3
        assert model.inner_vertices is None
        assert model.recipe == []
        assert model._inner_recipe == []

    def test_fibonacci_hollow(self):
        """Constructor with hollow=True creates both outer and inner meshes."""
        model = GlobeModel(n_points=200, radius=20.0, hollow=True,
                           inner_ratio=0.75, inner_n_points=80)
        assert model.outer_vertices.shape[0] == 200
        assert model.inner_vertices is not None
        assert model.inner_vertices.shape[0] == 80
        # Inner radius should be 0.75 * 20 = 15
        inner_radii = np.linalg.norm(model.inner_vertices, axis=1)
        assert np.allclose(inner_radii, 15.0)

    def test_icosahedron_method(self):
        """Constructor with method='icosahedron'."""
        model = GlobeModel(method='icosahedron', subdivisions=2, radius=10.0)
        assert model.outer_vertices.shape[0] > 12
        radii = np.linalg.norm(model.outer_vertices, axis=1)
        assert np.allclose(radii, 10.0)

    def test_icosahedron_requires_subdivisions(self):
        """Icosahedron without subdivisions raises ValueError."""
        with pytest.raises(ValueError, match="subdivisions must be specified"):
            GlobeModel(method='icosahedron', radius=10.0)

    def test_unknown_method_raises(self):
        """Unknown method raises ValueError."""
        with pytest.raises(ValueError, match="Unknown sphere method"):
            GlobeModel(method='cube', n_points=100)

    def test_hollow_default_inner_n_points(self):
        """When inner_n_points is not specified, defaults to n_points // 5."""
        model = GlobeModel(n_points=500, radius=20.0, hollow=True)
        assert model.inner_vertices.shape[0] == 100  # 500 // 5

    def test_from_fibonacci_backward_compat(self):
        """from_fibonacci still works."""
        model = GlobeModel.from_fibonacci(100, radius=20.0)
        assert model.outer_vertices.shape == (100, 3)
        assert model.inner_vertices is None
        assert model.recipe == []
        assert model._inner_recipe == []

    def test_from_icosahedron_backward_compat(self):
        """from_icosahedron still works."""
        model = GlobeModel.from_icosahedron(2, radius=10.0)
        assert model.outer_vertices.shape[0] > 12


# ---------------------------------------------------------------------------
# _MeshProxy tests
# ---------------------------------------------------------------------------

class TestMeshProxy:

    def test_outer_proxy_displace(self, simple_grid):
        """model.outer.displace() displaces outer vertices and records recipe."""
        model = GlobeModel(n_points=100, radius=20.0)
        displacer = GridDisplacer(simple_grid)
        model.outer.displace(displacer, scale=2.0)

        assert len(model.recipe) == 1
        assert model.recipe[0]["type"] == "displacement"
        radii = np.linalg.norm(model.outer_vertices, axis=1)
        assert np.allclose(radii, 23.0)  # 20 + 1.5 * 2.0

    def test_inner_proxy_displace(self, simple_grid):
        """model.inner.displace() displaces inner vertices and records inner recipe."""
        model = GlobeModel(n_points=100, radius=20.0, hollow=True,
                           inner_ratio=0.5, inner_n_points=50)
        displacer = GridDisplacer(simple_grid)
        model.inner.displace(displacer, scale=1.0)

        assert len(model._inner_recipe) == 1
        assert model._inner_recipe[0]["type"] == "displacement"
        assert len(model.recipe) == 0  # outer recipe untouched
        inner_radii = np.linalg.norm(model.inner_vertices, axis=1)
        assert np.allclose(inner_radii, 11.5)  # 10 + 1.5 * 1.0

    def test_inner_proxy_raises_when_not_hollow(self):
        """Accessing model.inner raises ValueError when no inner mesh."""
        model = GlobeModel(n_points=100, radius=20.0)
        with pytest.raises(ValueError, match="Inner geometry is not initialized"):
            _ = model.inner

    def test_outer_proxy_colour(self):
        """model.outer.colour() applies colors to outer vertices."""
        model = GlobeModel(n_points=100, radius=20.0)
        colourer = ConstantColourer([0.0, 1.0, 0.0])
        model.outer.colour(colourer)

        assert model.outer_colors is not None
        assert np.allclose(model.outer_colors, [0.0, 1.0, 0.0])
        assert len(model.recipe) == 1
        assert model.recipe[0]["type"] == "colouring"

    def test_proxy_read_properties(self):
        """Proxy exposes vertices, faces, colors as read-only properties."""
        model = GlobeModel(n_points=100, radius=20.0, hollow=True, inner_n_points=50)

        assert model.outer.vertices is model.outer_vertices
        assert model.outer.faces is model.outer_faces
        assert model.outer.colors is model.outer_colors

        assert model.inner.vertices is model.inner_vertices
        assert model.inner.faces is model.inner_faces

    def test_displace_convenience_alias(self, simple_grid):
        """model.displace() is an alias for model.outer.displace()."""
        model = GlobeModel(n_points=100, radius=20.0)
        displacer = GridDisplacer(simple_grid)
        model.displace(displacer, scale=2.0)

        assert len(model.recipe) == 1
        radii = np.linalg.norm(model.outer_vertices, axis=1)
        assert np.allclose(radii, 23.0)

    def test_outer_proxy_displace_constant(self):
        """model.outer.displace_constant() displaces outer vertices by a constant amount and records recipe."""
        model = GlobeModel(n_points=100, radius=20.0)
        model.outer.displace_constant(1.5, scale=2.0)

        assert len(model.recipe) == 1
        assert model.recipe[0]["type"] == "displacement"
        radii = np.linalg.norm(model.outer_vertices, axis=1)
        assert np.allclose(radii, 23.0)  # 20 + 1.5 * 2.0

    def test_inner_proxy_displace_constant(self):
        """model.inner.displace_constant() displaces inner vertices by a constant amount and records recipe."""
        model = GlobeModel(n_points=100, radius=20.0, hollow=True, inner_ratio=0.5, inner_n_points=50)
        model.inner.displace_constant(1.0, scale=1.5)

        assert len(model._inner_recipe) == 1
        assert model._inner_recipe[0]["type"] == "displacement"
        inner_radii = np.linalg.norm(model.inner_vertices, axis=1)
        assert np.allclose(inner_radii, 11.5)  # 10 + 1.0 * 1.5

    def test_displace_constant_convenience_alias(self):
        """model.displace_constant() is an alias for model.outer.displace_constant()."""
        model = GlobeModel(n_points=100, radius=20.0)
        model.displace_constant(1.5, scale=2.0)

        assert len(model.recipe) == 1
        radii = np.linalg.norm(model.outer_vertices, axis=1)
        assert np.allclose(radii, 23.0)


# ---------------------------------------------------------------------------
# configure_magnets tests
# ---------------------------------------------------------------------------

class TestConfigureMagnets:

    def test_configure_magnets(self):
        """configure_magnets() creates MagnetSettings on the model."""
        model = GlobeModel(n_points=100, radius=20.0)
        model.configure_magnets(diameter=5.0, height=2.0, n_magnets=3)

        assert model.magnet_settings is not None
        assert model.magnet_settings.diameter == 5.0
        assert model.magnet_settings.height == 2.0
        assert model.magnet_settings.n_magnets == 3


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------

class TestExport:

    def test_export_stl(self, tmp_path):
        """export() writes an STL file."""
        model = GlobeModel(n_points=100, radius=20.0)
        path = str(tmp_path / "model.stl")
        model.export(path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0

    def test_export_obj(self, tmp_path):
        """export() writes an OBJ file."""
        model = GlobeModel(n_points=100, radius=20.0)
        colourer = ConstantColourer([1.0, 0.0, 0.0])
        model.colour(colourer)

        path = str(tmp_path / "model.obj")
        model.export(path)
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
            assert content.startswith("# OBJ file")

    def test_export_unsupported_extension(self, tmp_path):
        """export() raises ValueError for unsupported extensions."""
        model = GlobeModel(n_points=100, radius=20.0)
        with pytest.raises(ValueError, match="Unsupported file extension"):
            model.export(str(tmp_path / "model.ply"))

    def test_export_hemispheres_stl(self, tmp_path):
        """export_hemispheres() writes both STL files."""
        model = GlobeModel(n_points=200, radius=20.0, hollow=True, inner_n_points=50)
        top_path = str(tmp_path / "top.stl")
        bot_path = str(tmp_path / "bottom.stl")
        model.export_hemispheres(top_path, bot_path, engine='manifold')

        assert os.path.exists(top_path)
        assert os.path.exists(bot_path)
        assert os.path.getsize(top_path) > 0
        assert os.path.getsize(bot_path) > 0

    def test_export_hemispheres_obj(self, tmp_path):
        """export_hemispheres() writes colored OBJ files."""
        model = GlobeModel(n_points=200, radius=20.0, hollow=True, inner_n_points=50)
        colourer = ConstantColourer([0.0, 0.5, 1.0])
        model.colour(colourer, selection='outward_facing')

        top_path = str(tmp_path / "top.obj")
        bot_path = str(tmp_path / "bottom.obj")
        model.export_hemispheres(top_path, bot_path, engine='manifold')

        assert os.path.exists(top_path)
        assert os.path.exists(bot_path)

        with open(top_path) as f:
            content = f.read()
            assert "v " in content
            assert "f " in content

    def test_export_hemispheres_creates_dirs(self, tmp_path):
        """export_hemispheres() creates output directories if they don't exist."""
        model = GlobeModel(n_points=200, radius=20.0, hollow=True, inner_n_points=50)
        nested_dir = tmp_path / "a" / "b"
        top_path = str(nested_dir / "top.stl")
        bot_path = str(nested_dir / "bottom.stl")
        model.export_hemispheres(top_path, bot_path, engine='manifold')

        assert os.path.exists(top_path)


# ---------------------------------------------------------------------------
# calculate_displacement_scale with grid_units
# ---------------------------------------------------------------------------

class TestDisplacementScale:

    def test_default_meters(self):
        """Default grid_units='m' produces same result as before."""
        scale = calculate_displacement_scale(40.0, earth_radius_km=6371.0, vertical_exagg=1.0)
        expected = 40.0 / (6371.0 * 1000.0)
        assert pytest.approx(scale) == expected

    def test_kilometers(self):
        """grid_units='km' multiplies by 1000."""
        scale_m = calculate_displacement_scale(40.0, vertical_exagg=1.0, grid_units='m')
        scale_km = calculate_displacement_scale(40.0, vertical_exagg=1.0, grid_units='km')
        assert pytest.approx(scale_km / scale_m) == 1000.0

    def test_centimeters(self):
        """grid_units='cm' divides by 100."""
        scale_m = calculate_displacement_scale(40.0, vertical_exagg=1.0, grid_units='m')
        scale_cm = calculate_displacement_scale(40.0, vertical_exagg=1.0, grid_units='cm')
        assert pytest.approx(scale_cm / scale_m) == 0.01

    def test_feet(self):
        """grid_units='ft' uses correct conversion factor."""
        scale_ft = calculate_displacement_scale(40.0, vertical_exagg=1.0, grid_units='ft')
        scale_m = calculate_displacement_scale(40.0, vertical_exagg=1.0, grid_units='m')
        assert pytest.approx(scale_ft / scale_m) == 0.3048

    def test_invalid_units(self):
        """Unknown grid_units raises ValueError."""
        with pytest.raises(ValueError, match="Unknown grid_units"):
            calculate_displacement_scale(40.0, grid_units='furlongs')

    def test_alias_names(self):
        """Long aliases ('meters', 'kilometers', etc.) work."""
        s1 = calculate_displacement_scale(40.0, grid_units='m')
        s2 = calculate_displacement_scale(40.0, grid_units='meters')
        assert s1 == s2

    def test_vertical_exagg_with_units(self):
        """vertical_exagg is applied correctly with non-default units."""
        scale = calculate_displacement_scale(40.0, vertical_exagg=50.0, grid_units='km')
        expected = (40.0 / (6371.0 * 1000.0)) * 50.0 * 1000.0
        assert pytest.approx(scale) == expected


class TestModelPreviewAndErrors:

    def test_thin_shell_magnet_error_propagation(self):
        """Verify that when the shell is too thin to fit magnets, generate_hemispheres raises a ValueError."""
        # Create a thin-shelled model: radius=40, inner_ratio=0.98 -> thickness is ~0.8mm
        model = GlobeModel(n_points=200, radius=40.0, hollow=True, inner_ratio=0.98)
        # Configure magnets without bosses, requiring enclosing radius of 3.5mm
        model.configure_magnets(
            diameter=5.0,
            height=2.0,
            n_magnets=3,
            add_bosses=False,
            min_thickness=1.0,
        )
        # Trying to generate hemispheres should raise ValueError (wrapped in RuntimeError or directly)
        # Since insert_magnets_into_hemispheres raises ValueError, and create_hollow_hemispheres wraps it:
        with pytest.raises(Exception) as excinfo:
            model.generate_hemispheres(engine="manifold")
        
        # Verify the original ValueError's message is preserved
        assert "Globe shell is too thin" in str(excinfo.value)

    def test_export_hemispheres_propagates_magnet_error(self, tmp_path):
        """Verify that export_hemispheres also propagates the thin-shell magnet error."""
        model = GlobeModel(n_points=200, radius=40.0, hollow=True, inner_ratio=0.98)
        model.configure_magnets(
            diameter=5.0,
            height=2.0,
            n_magnets=3,
            add_bosses=False,
            min_thickness=1.0,
        )
        top_path = str(tmp_path / "top.stl")
        bot_path = str(tmp_path / "bottom.stl")
        with pytest.raises(Exception) as excinfo:
            model.export_hemispheres(top_path, bot_path, engine="manifold")
        assert "Globe shell is too thin" in str(excinfo.value)

    def test_preview_method(self):
        """Verify that preview() calls show() on the correct trimesh component."""
        from unittest.mock import patch
        
        model = GlobeModel(n_points=100, radius=20.0, hollow=True, inner_n_points=50)
        
        # 1. Preview outer shell
        with patch('trimesh.Trimesh.show', return_value="outer_scene") as mock_show:
            res = model.preview(part="outer", viewer="gl")
            assert res == "outer_scene"
            mock_show.assert_called_once_with(viewer="gl")
            
        # 2. Preview inner shell
        with patch('trimesh.Trimesh.show', return_value="inner_scene") as mock_show:
            res = model.preview(part="inner")
            assert res == "inner_scene"
            mock_show.assert_called_once()
            
        # 3. Preview upper hemisphere
        with patch('trimesh.Trimesh.show', return_value="upper_scene") as mock_show:
            res = model.preview(part="upper", engine="manifold")
            assert res == "upper_scene"
            mock_show.assert_called_once()
            
        # 4. Preview lower hemisphere
        with patch('trimesh.Trimesh.show', return_value="lower_scene") as mock_show:
            res = model.preview(part="lower", engine="manifold")
            assert res == "lower_scene"
            mock_show.assert_called_once()
            
        # 5. Invalid part raises ValueError
        with pytest.raises(ValueError, match="Unknown part"):
            model.preview(part="invalid_part")
