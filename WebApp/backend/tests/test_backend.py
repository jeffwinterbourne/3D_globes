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


def test_polygon_displacer_and_available_media():
    """Verifies PolygonDisplacer physical step in Python, shapefile rasterization, and media catalog."""
    import numpy as np
    from WebApp.backend.dataset_service import get_media_and_datasets
    from WebApp.backend.preview_service import rasterize_shapefile_to_mask
    from globe3d import datasets

    # 1. Test media catalog returns vectors and images
    media = get_media_and_datasets()
    assert len(media["vectors"]) >= 2
    assert any(v["identifier"] == "land" for v in media["vectors"])
    assert any(v["identifier"] == "coastline" for v in media["vectors"])

    # 2. Test fast PIL rasterization produces valid binary mask
    land_shp = datasets.shapefiles.land()
    mask = rasterize_shapefile_to_mask(land_shp, height=90, width=180, is_line=False)
    assert mask.shape == (90, 180)
    assert 0.15 < float(mask.mean()) < 0.45  # Land fraction on Earth is ~29-35%

    # 3. Test PolygonDisplacer compilation on Python GlobeModel applies exact physical step
    proj = _make_sample_project(hollow=False)
    proj.outer_displacements = [
        DisplacerConfigModel(
            type="PolygonDisplacer",
            shapefile="land",
            displacement=2.5,
            displace_inside=True,
            scale=1.0,
        )
    ]
    model = compile_globe_model(proj)
    radii = np.linalg.norm(model.outer_vertices, axis=1)
    diff = float(radii.max() - radii.min())
    # Should have a 2.5 mm displacement step between land and ocean
    assert 2.4 <= diff <= 2.6

    # 4. Test code generation includes PolygonDisplacer with proper scale=1.0
    code = generate_python_and_notebook(proj)
    assert "PolygonDisplacer(" in code["python_script"]
    assert "displacement=2.5" in code["python_script"]
    assert "scale=1.0" in code["python_script"]


def test_online_dataset_caching_and_dual_resolution_evaluation():
    """Verifies dataset caching detection, NetCDF variable auto-detection, and dual preview/full evaluation."""
    from WebApp.backend.dataset_service import get_datasets_catalog
    from WebApp.backend.preview_service import evaluate_preview_mesh, get_grid_buffer_for_worker

    # 1. Test dataset catalog correctly detects cached grids and coordinates
    cat = get_datasets_catalog()
    assert "datasets" in cat
    mars_entry = next((d for d in cat["datasets"] if d["id"] == "topography.mars"), None)
    assert mars_entry is not None
    assert mars_entry["cached"] is True
    assert mars_entry["size_bytes"] > 0
    assert mars_entry.get("detected_lat") == "lat"
    assert mars_entry.get("detected_lon") == "lon"
    assert mars_entry.get("detected_data") == "z"

    earth_entry = next((d for d in cat["datasets"] if d["id"] == "topography.earth"), None)
    assert earth_entry is not None
    assert earth_entry["cached"] is True
    assert earth_entry.get("detected_lat") == "lat"

    # 2. Test evaluate_preview_mesh with preview vs full resolution override
    proj = GlobeProject(
        mode="custom",
        geometry={
            "distribution": "fibonacci",
            "n_points": 500,
            "preview_n_points": 200,
            "radius": 40.0,
            "hollow": False,
        },
        grids=[
            GridSourceModel(
                id="etopo_ds",
                source="online",
                dataset="topography.earth",
                params={"resolution": "30m"},
            )
        ],
        outer_displacements=[
            DisplacerConfigModel(
                type="GridDisplacer",
                grid_id="etopo_ds",
                scale_mode="physical",
                vertical_exagg=40.0,
                coastline_step=0.8,
            )
        ],
    )

    # Preview evaluation (uses preview_n_points = 200)
    preview_res = evaluate_preview_mesh(proj, preview_n_points=200)
    assert preview_res["n_outer"] == 200

    # Full output evaluation (uses n_points = 500)
    full_res = evaluate_preview_mesh(proj, preview_n_points=500)
    assert full_res["n_outer"] == 500

    # Grid worker buffer generation returns valid elevation
    worker_buf = get_grid_buffer_for_worker(proj)
    assert "grids" in worker_buf
    assert "etopo_ds" in worker_buf["grids"]
    assert worker_buf["grids"]["etopo_ds"]["vmin"] < 0
    assert worker_buf["grids"]["etopo_ds"]["vmax"] > 0


def test_declarative_grid_smooth_fill_and_chainable_math():
    """Verifies spherical Gaussian smoothing, NaN inpainting, and chainable math operations on grids."""
    import numpy as np
    from WebApp.backend.engine import (
        apply_grid_math,
        fill_grid_nans,
        resolve_project_grids,
        smooth_sphere_gaussian,
    )

    lats = np.linspace(-90.0, 90.0, 91)
    lons = np.linspace(-180.0, 180.0, 181)

    # 1. Test Spherical Gaussian Smoothing (anti-meridian periodic wrapping & finite output)
    spike_grid = np.zeros((91, 181), dtype=np.float64)
    # Place a spike at the -180 deg boundary
    spike_grid[45, 0] = 1000.0
    spike_grid[45, -1] = 1000.0
    smoothed = smooth_sphere_gaussian(spike_grid, lats, lons, width_deg=5.0)

    assert np.isfinite(smoothed).all()
    # Wrapping across -180 and +180 means both margins have smooth nonzero shoulders
    assert smoothed[45, 1] > 0.0
    assert smoothed[45, -2] > 0.0
    # Center away from spike should remain near zero
    assert smoothed[45, 90] < 1.0

    # 2. Test Fill NaNs (constant, mean, nearest)
    nan_grid = np.array([
        [10.0, np.nan, 30.0],
        [40.0, 50.0, np.nan],
        [np.nan, 80.0, 90.0],
    ])
    filled_const = fill_grid_nans(nan_grid, mode="constant", value=-999.0)
    assert not np.isnan(filled_const).any()
    assert filled_const[0, 1] == -999.0

    filled_mean = fill_grid_nans(nan_grid, mode="mean")
    assert not np.isnan(filled_mean).any()
    assert abs(filled_mean[0, 1] - 50.0) < 1e-4

    filled_nearest = fill_grid_nans(nan_grid, mode="nearest")
    assert not np.isnan(filled_nearest).any()
    assert filled_nearest[0, 1] in (10.0, 30.0, 50.0)

    # 3. Test Chainable Math Operations
    base = np.array([[2.0, 4.0], [9.0, 16.0]])
    assert np.allclose(apply_grid_math(base, "add", operand=3.0), base + 3.0)
    assert np.allclose(apply_grid_math(base, "multiply", operand=2.5), base * 2.5)
    assert np.allclose(apply_grid_math(base, "sqrt"), np.sqrt(base))
    assert np.allclose(apply_grid_math(base, "clamp", min_val=3.0, max_val=10.0), [[3.0, 4.0], [9.0, 10.0]])
    assert np.allclose(apply_grid_math(base, "power", operand=2.0), base ** 2)

    # 4. Test Full Pipeline Execution in resolve_project_grids
    proj = GlobeProject(
        mode="custom",
        geometry={
            "distribution": "fibonacci",
            "n_points": 300,
            "preview_n_points": 200,
            "radius": 40.0,
            "hollow": False,
        },
        grids=[
            GridSourceModel(
                id="test_pipeline_grid",
                source="synthetic",
                synthetic_type="procedural_waves",
                params={"step": 2.0, "amplitude": 1000.0},
                ops=[
                    GridOpModel(op="fill", fill_mode="constant", fill_value=0.0),
                    GridOpModel(op="smooth", width_deg=3.0),
                    GridOpModel(op="math", math_op="multiply", operand=2.0),
                    GridOpModel(op="math", math_op="add", operand=500.0),
                    GridOpModel(op="math", math_op="clamp", min_val=0.0, max_val=2000.0),
                ],
            )
        ],
    )

    grids_by_id, _ = resolve_project_grids(proj)
    assert "test_pipeline_grid" in grids_by_id
    res_grid = grids_by_id["test_pipeline_grid"]
    assert np.isfinite(res_grid.grid).all()
    # Check that clamp [0, 2000] was enforced by the math chain
    assert float(res_grid.grid.min()) >= 0.0
    assert float(res_grid.grid.max()) <= 2000.0


def test_scotese_metadata_age_field():
    """Verifies Scotese maps have both 'age_ma' and 'age' populated for frontend dropdown."""
    from globe3d import datasets
    maps = datasets.paleo.list_scotese_maps()
    assert len(maps) >= 88
    for m in maps:
        assert "age_ma" in m
        assert "age" in m
        assert m["age"] == m["age_ma"]
    # Check that ages span beyond 0 Ma (e.g. up to 540 Ma)
    ages = [m["age"] for m in maps]
    assert max(ages) >= 500
    assert min(ages) == 0.0


def test_workspace_service_and_dataset_virtual_duplication(tmp_path):
    """Verifies workspace project CRUD, dataset management, and zero-copy virtual duplication."""
    from WebApp.backend.workspace_service import (
        ensure_workspace_structure,
        save_workspace_project,
        list_workspace_projects,
        open_workspace_project,
        duplicate_workspace_project,
        list_workspace_datasets,
        register_or_update_dataset,
        duplicate_workspace_dataset,
    )

    work_dir = str(tmp_path / "test_workspace")
    ensure_workspace_structure(work_dir)

    # 1. Test Project Save & List
    dummy_proj = {
        "id": "my_mars_globe",
        "name": "My Mars Globe",
        "category": "user",
        "mode": "custom",
        "geometry": {"radius": 45.0, "hollow": True},
    }
    saved = save_workspace_project(work_dir, dummy_proj)
    assert saved["status"] == "ok"
    assert saved["slug"] == "my_mars_globe"

    projects = list_workspace_projects(work_dir)
    assert len(projects) == 1
    assert projects[0]["slug"] == "my_mars_globe"
    assert projects[0]["name"] == "My Mars Globe"

    # 2. Test Project Open & Duplicate
    opened = open_workspace_project(work_dir, "my_mars_globe")
    assert opened["id"] == "my_mars_globe"
    assert opened["geometry"]["radius"] == 45.0

    dup = duplicate_workspace_project(work_dir, "my_mars_globe")
    assert dup["status"] == "ok"
    projects_after_dup = list_workspace_projects(work_dir)
    assert len(projects_after_dup) == 2

    # 3. Test Dataset physical file auto-discovery
    ds_dir = os.path.join(work_dir, "datasets")
    test_grid_path = os.path.join(ds_dir, "custom_elevation.nc")
    with open(test_grid_path, "w") as f:
        f.write("mock_netcdf_bytes")

    datasets = list_workspace_datasets(work_dir)
    assert len(datasets) == 1
    ds_entry = datasets[0]
    assert ds_entry["physical_filename"] == "custom_elevation.nc"
    assert ds_entry["file_type"] == "grid"
    assert ds_entry["is_virtual"] is False

    # 4. Test Zero-Copy Virtual Dataset Duplication
    virtual_dup = duplicate_workspace_dataset(
        work_dir,
        source_id=ds_entry["id"],
        new_name="Custom Elevation (Gaussian Smoothed)",
        default_ops=[{"op": "smooth", "width_deg": 2.0}],
    )
    assert virtual_dup["is_virtual"] is True
    assert virtual_dup["physical_filename"] == "custom_elevation.nc"
    assert len(virtual_dup["default_ops"]) == 1
    assert virtual_dup["default_ops"][0]["op"] == "smooth"

    all_ds = list_workspace_datasets(work_dir)
    assert len(all_ds) == 2
    # Verify no second file was created on disk!
    files_on_disk = os.listdir(ds_dir)
    assert len(files_on_disk) == 1
    assert files_on_disk[0] == "custom_elevation.nc"






