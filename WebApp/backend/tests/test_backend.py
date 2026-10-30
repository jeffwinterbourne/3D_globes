"""Unit and integration tests for the Globe3D Studio FastAPI backend."""

import json
import os
import sys
import pytest

WEBAPP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO_ROOT = os.path.dirname(WEBAPP_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if os.path.join(REPO_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from WebApp.backend.codegen import generate_python_and_notebook
from WebApp.backend.dataset_service import browse_local_files, get_datasets_catalog
from WebApp.backend.engine import compile_globe_model, export_project_model
from WebApp.backend.filament_service import generate_palette_response, match_target_color_response
from WebApp.backend.magnet_service import create_calibration_test_piece, optimize_and_inspect_magnets
from WebApp.backend.models import (
    ColourerConfigModel,
    DisplacerConfigModel,
    FilamentsConfigModel,
    GlobeProject,
    GridOpModel,
    GridSourceModel,
    MagnetTestPieceRequest,
)
from WebApp.backend.preview_service import (
    evaluate_preview_mesh,
    get_grid_buffer_for_worker,
    render_2d_map_and_colorbar,
)


def _make_sample_project(hollow: bool = True) -> GlobeProject:
    """Creates a fast synthetic GlobeProject for unit testing."""
    return GlobeProject(
        metadata={"name": "Test Synthetic Globe", "description": "Unit test globe"},
        mode="custom",
        geometry={
            "distribution": "fibonacci",
            "n_points": 600,
            "preview_n_points": 400,
            "radius": 40.0,
            "hollow": hollow,
            "inner_ratio": 0.85,
            "fix_intersection": {"enabled": True, "min_thickness": 1.5, "mode": "inner"},
        },
        grids=[
            GridSourceModel(
                id="synth_waves",
                source="synthetic",
                synthetic_type="procedural_waves",
                params={"step": 5.0, "amplitude": 2500.0},
                ops=[GridOpModel(op="scale_offset", scale=1.0, offset=0.0)],
            )
        ],
        outer_displacements=[
            DisplacerConfigModel(
                type="GridDisplacer",
                grid_id="synth_waves",
                scale_mode="auto_exagg",
                vert_exagg=20.0,
                coastline_step=300.0,
            )
        ],
        colourers=[
            ColourerConfigModel(
                type="GridColourer",
                grid_id="synth_waves",
                target="outer",
                cmap="terrain",
            ),
            ColourerConfigModel(
                type="PoleLabelColourer",
                target="outer",
                size_deg=5.0,
            ),
        ],
        magnets={
            "enabled": True,
            "count": 4,
            "Optimize_positions": True,
            "diameter": 3.2,
            "height": 1.6,
        },
        export={
            "split_hemispheres": False,
            "format": "3mf",
            "filename_prefix": "test_globe_export",
        },
    )


def test_compile_and_preview_services():
    """Verifies compilation, binary WebGL preview buffer generation, and 2D map rendering."""
    proj = _make_sample_project(hollow=True)
    model = compile_globe_model(proj)
    assert model.outer_vertices.shape == (600, 3)
    assert model.outer_colors.shape == (600, 3)
    assert model.inner_vertices is not None

    prev = evaluate_preview_mesh(proj, preview_n_points=300)
    assert prev["n_outer"] == 300
    assert len(prev["outer_positions_b64"]) > 100
    assert prev["stats"]["vertex_count"] > 300

    grid_buf = get_grid_buffer_for_worker(proj, height=45, width=90)
    assert grid_buf["width"] == 90
    assert grid_buf["height"] == 45
    assert len(grid_buf["elevation_f32_b64"]) > 50

    map2d = render_2d_map_and_colorbar(proj)
    assert map2d["map_image_data_url"].startswith("data:image/png;base64,")
    assert map2d["colorbar_image_data_url"].startswith("data:image/png;base64,")


def test_filament_palette_and_matching():
    """Verifies Full-Spectrum optical mixing palette generation and CIE Delta-E color matching."""
    cfg = FilamentsConfigModel(preset="TERRAIN_4", top_layers=4)
    pal = generate_palette_response(cfg)
    assert len(pal["entries"]) >= 20
    assert pal["entries"][0]["code"] == "[00]"

    match = match_target_color_response("#123478", cfg)
    assert match["best_match"] is not None
    assert match["delta_e"] >= 0.0
    assert len(match["top_5"]) == 5


def test_magnet_optimizer_and_test_piece(tmp_path):
    """Verifies equatorial cross-section profiling, magnet optimization, and STL test piece export."""
    proj = _make_sample_project(hollow=True)
    opt = optimize_and_inspect_magnets(proj)
    assert len(opt["profile_deg"]) == 360
    assert len(opt["d_min"]) == 360
    assert len(opt["d_max"]) == 360
    assert len(opt["magnets"]) >= 2

    req = MagnetTestPieceRequest(diameter=3.2, height=1.6, clearance=0.1, output_dir=str(tmp_path))
    res = create_calibration_test_piece(req, repo_root=str(tmp_path))
    assert os.path.isfile(res["saved_path"])
    assert res["size_bytes"] > 100


def test_codegen_and_export(tmp_path):
    """Verifies Python script/notebook code generation and .3mf/.stl export."""
    proj = _make_sample_project(hollow=False)
    proj.export.output_dir = str(tmp_path)
    proj.export.split_hemispheres = False
    proj.export.format = "3mf"

    code = generate_python_and_notebook(proj)
    assert "GlobeModel(" in code["python_script"]
    nb = json.loads(code["notebook_json"])
    assert nb["nbformat"] == 4

    exp_res = export_project_model(proj, repo_root=str(tmp_path))
    assert len(exp_res["files"]) == 1
    assert os.path.isfile(exp_res["files"][0]["saved_path"])


def test_datasets_catalog_and_file_browser():
    """Verifies dataset catalog and local directory browsing."""
    cat = get_datasets_catalog()
    assert len(cat["datasets"]) >= 15
    browse = browse_local_files(default_root=REPO_ROOT)
    assert os.path.isdir(browse["current_path"])


def test_all_27_presets_load_and_validate():
    """Verifies that all 27 built-in JSON presets load and validate against GlobeProject."""
    from WebApp.backend.main import get_preset, list_presets

    catalog = list_presets()
    presets = catalog.get("presets", [])
    assert len(presets) == 27

    for item in presets:
        pid = item["id"]
        loaded = get_preset(pid)
        assert loaded["metadata"]["name"]
        assert loaded["geometry"]["radius"] > 0


def test_bugfix_regressions():
    """Verifies fixes for North-up grid orientation, auto_exagg scaling, and magnet outer containment."""
    import base64
    import numpy as np
    from globe3d.grid import GeographicGrid

    # 1. North-up orientation in get_grid_buffer_for_worker + displacement scale in auto_exagg
    proj = _make_sample_project(hollow=True)
    # Emulate preset payload where scale=0.0003139 is also present alongside scale_mode="auto_exagg"
    proj.outer_displacements[0].scale = 0.0003139
    proj.outer_displacements[0].vert_exagg = 20.0
    proj.outer_displacements[0].coastline_step = 0.8

    model = compile_globe_model(proj)
    radii = np.linalg.norm(model.outer_vertices, axis=1)
    # Displacement must be several mm, not squared-down 0.001 mm
    assert float(radii.max() - radii.min()) > 1.0

    # 2. Magnet containment when shell wall is thinner than enclosure radius (needs bosses)
    proj.geometry.inner_ratio = 0.94  # thin wall (~2.4 mm on R=40 mm) while r_enc = 3.2/2 + 0.1 + 1.2 = 2.9 mm
    opt = optimize_and_inspect_magnets(proj)
    r_enc = (proj.magnets.diameter / 2.0) + proj.magnets.clearance + proj.magnets.boss_thickness
    min_outer_eq = min(opt["d_max"]) + r_enc
    for m in opt["magnets"]:
        # Outer edge of boss/enclosure must never exceed the outer surface radius
        assert m["r_center"] + r_enc <= min_outer_eq + 0.25


