"""FastAPI application entry point for the Globe3D Studio WebApp."""

import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Ensure the repository's src/ directory is importable even if not installed in editable mode
WEBAPP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(WEBAPP_DIR)
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from globe3d import datasets
from .codegen import generate_python_and_notebook
from .dataset_service import (
    browse_local_files,
    get_datasets_catalog,
    get_media_and_datasets,
    inspect_netcdf_file,
    trigger_dataset_download,
)
from .engine import export_project_model
from .filament_service import generate_palette_response, match_target_color_response
from .magnet_service import create_calibration_test_piece, optimize_and_inspect_magnets
from .models import (
    DatasetDownloadRequest,
    FilamentMatchRequest,
    FilamentsConfigModel,
    GlobeProject,
    InspectNetCDFRequest,
    MagnetTestPieceRequest,
    ReconstructPointsRequest,
    RevealFileRequest,
    WorkspaceConfigUpdateRequest,
    WorkspaceDatasetDuplicateRequest,
    WorkspaceDatasetRegisterRequest,
    WorkspaceProjectDuplicateRequest,
    WorkspaceProjectOpenRequest,
    WorkspaceProjectSaveRequest,
)
from .workspace_service import (
    duplicate_workspace_dataset,
    duplicate_workspace_project,
    generate_dataset_thumbnail,
    get_stored_config,
    list_workspace_datasets,
    list_workspace_projects,
    open_workspace_project,
    register_or_update_dataset,
    save_stored_config,
    save_workspace_project,
)
from .preview_service import (
    evaluate_preview_mesh,
    get_grid_buffer_for_worker,
    render_2d_map_and_colorbar,
)

app = FastAPI(
    title="Globe3D Studio API",
    description="High-performance backend for interactive 3D geophysical & paleogeographic globe design.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PRESETS_DIR = os.path.join(WEBAPP_DIR, "presets")


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    """Health check endpoint reporting repository root and Scotese cache status."""
    scotese_dir = datasets.paleo.find_scotese_data_dir()
    return {
        "status": "ok",
        "repo_root": REPO_ROOT,
        "scotese_cached": scotese_dir is not None,
        "scotese_dir": scotese_dir,
    }


@app.get("/api/presets")
def list_presets() -> Dict[str, Any]:
    """Returns the catalog of all built-in JSON presets."""
    index_path = os.path.join(PRESETS_DIR, "index.json")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return {"presets": data}
            return data

    # Fallback dynamic scan if index.json is missing
    presets = []
    for root, _, files in os.walk(PRESETS_DIR):
        for fn in sorted(files):
            if fn.endswith(".json") and fn != "index.json":
                full_p = os.path.join(root, fn)
                rel_p = os.path.relpath(full_p, PRESETS_DIR).replace("\\", "/")
                preset_id = os.path.splitext(fn)[0]
                try:
                    with open(full_p, "r", encoding="utf-8") as f:
                        doc = json.load(f)
                    meta = doc.get("metadata", {})
                    presets.append({
                        "id": preset_id,
                        "path": rel_p,
                        "name": meta.get("name", preset_id),
                        "description": meta.get("description", ""),
                        "category": meta.get("category", "examples"),
                        "collection": meta.get("collection", "Standard Examples"),
                        "tags": meta.get("tags", []),
                    })
                except Exception:
                    continue
    return {"presets": presets}


@app.get("/api/presets/{preset_id:path}")
def get_preset(preset_id: str) -> Dict[str, Any]:
    """Loads a specific preset JSON by its ID or relative path."""
    candidates = [
        os.path.join(PRESETS_DIR, preset_id),
        os.path.join(PRESETS_DIR, f"{preset_id}.json"),
        os.path.join(PRESETS_DIR, "examples", f"{preset_id}.json"),
        os.path.join(PRESETS_DIR, "paper_recreations", f"{preset_id}.json"),
    ]
    # Also check index.json mapping
    index_path = os.path.join(PRESETS_DIR, "index.json")
    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                idx_data = json.load(f)
            items = idx_data if isinstance(idx_data, list) else idx_data.get("presets", [])
            for item in items:
                if item.get("id") == preset_id and item.get("path"):
                    candidates.insert(0, os.path.join(PRESETS_DIR, item["path"]))
        except Exception:
            pass

    for path in candidates:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            validated = GlobeProject(**raw)
            return validated.model_dump() if hasattr(validated, "model_dump") else validated.dict()

    raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found.")


@app.post("/api/presets/validate")
def validate_preset(project: GlobeProject) -> Dict[str, Any]:
    """Validates and normalizes a GlobeProject JSON payload."""
    dumped = project.model_dump() if hasattr(project, "model_dump") else project.dict()
    return {"valid": True, "project": dumped}


@app.get("/api/presets/{preset_id:path}/thumbnail")
def get_preset_thumbnail(preset_id: str):
    """Returns pre-rendered thumbnail image for a preset."""
    clean_id = os.path.splitext(os.path.basename(preset_id))[0]
    thumb_path = os.path.join(PRESETS_DIR, "thumbnails", f"{clean_id}.png")
    if not os.path.exists(thumb_path):
        try:
            from .scripts.generate_gallery_thumbnails import generate_all_preset_thumbnails
            generate_all_preset_thumbnails()
        except Exception:
            pass

    if os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type="image/png")
    
    # Fallback to example_1
    fallback = os.path.join(PRESETS_DIR, "thumbnails", "example_1_procedural_globe.png")
    if os.path.exists(fallback):
        return FileResponse(fallback, media_type="image/png")
    raise HTTPException(status_code=404, detail="Thumbnail not found")


# ---------------------------------------------------------------------------
# Workspace & Project Management Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/workspace/config")
def workspace_config() -> Dict[str, Any]:
    """Gets active workspace working directory and basic counts."""
    cfg = get_stored_config()
    projects = list_workspace_projects(cfg["working_dir"])
    datasets_list = list_workspace_datasets(cfg["working_dir"])
    return {
        "working_dir": cfg["working_dir"],
        "projects_count": len(projects),
        "datasets_count": len(datasets_list),
    }


@app.post("/api/workspace/config")
def workspace_set_config(req: WorkspaceConfigUpdateRequest) -> Dict[str, Any]:
    """Sets active workspace working directory."""
    if not req.working_dir or not os.path.isabs(req.working_dir):
        raise HTTPException(status_code=400, detail="working_dir must be an absolute filesystem path.")
    cfg = save_stored_config(req.working_dir)
    return {
        "status": "ok",
        "working_dir": cfg["working_dir"],
    }


@app.get("/api/workspace/projects")
def workspace_list_projects(working_dir: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """Lists saved projects inside the workspace projects/ directory."""
    projects = list_workspace_projects(working_dir)
    return {"projects": projects}


@app.post("/api/workspace/projects/save")
def workspace_save_project(req: WorkspaceProjectSaveRequest, working_dir: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """Saves a project to the workspace."""
    try:
        return save_workspace_project(working_dir, req.project, slug=req.slug)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/workspace/projects/open")
def workspace_open_project(req: WorkspaceProjectOpenRequest, working_dir: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """Loads a project from the workspace."""
    try:
        data = open_workspace_project(working_dir, req.slug_or_path)
        return {"project": data}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/workspace/projects/duplicate")
def workspace_duplicate_project(req: WorkspaceProjectDuplicateRequest, working_dir: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """Duplicates a workspace project (Open as Copy)."""
    try:
        return duplicate_workspace_project(working_dir, req.slug, req.new_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/workspace/datasets")
def workspace_list_datasets(working_dir: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """Lists workspace datasets with virtual duplicate profiles."""
    datasets_list = list_workspace_datasets(working_dir)
    return {"datasets": datasets_list}


@app.post("/api/workspace/datasets/register")
def workspace_register_dataset(req: WorkspaceDatasetRegisterRequest, working_dir: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """Updates metadata/default ops for a dataset profile in dataset_registry.json."""
    try:
        entry = register_or_update_dataset(working_dir, req.entry)
        return {"status": "ok", "dataset": entry}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/workspace/datasets/duplicate")
def workspace_duplicate_dataset(req: WorkspaceDatasetDuplicateRequest, working_dir: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """Zero-copy dataset duplication: registers new virtual profile referencing same file."""
    try:
        new_entry = duplicate_workspace_dataset(
            working_dir,
            source_id=req.source_id,
            new_id=req.new_id,
            new_name=req.new_name,
            default_ops=req.default_ops,
        )
        return {"status": "ok", "dataset": new_entry}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/workspace/datasets/{dataset_id}/thumbnail")
def workspace_dataset_thumbnail(dataset_id: str, working_dir: Optional[str] = Query(default=None)):
    """Generates and serves a small 2D PNG thumbnail for a workspace dataset."""
    thumb_path = generate_dataset_thumbnail(working_dir, dataset_id)
    if thumb_path and os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Thumbnail could not be generated.")


@app.get("/api/paleo/catalog")
def get_paleo_catalog() -> Dict[str, Any]:
    """Returns all 88 Scotese PALEOMAP time slices (0-540 Ma) and local cache status."""
    maps = datasets.paleo.list_scotese_maps()
    scotese_dir = datasets.paleo.find_scotese_data_dir()
    return {
        "maps": maps,
        "scotese_dir": scotese_dir,
        "cached": scotese_dir is not None,
    }


@app.post("/api/paleo/reconstruct-points")
def reconstruct_paleo_points(req: ReconstructPointsRequest) -> Dict[str, Any]:
    """Reconstructs modern geographic coordinates to their paleo-positions at the requested age."""
    if not req.locations:
        return {"reconstructed": []}

    pts = [[loc.lat, loc.lon] for loc in req.locations]
    reconstructed_coords = None
    if req.age > 0:
        try:
            pm = datasets.paleo.scotese_plate_model(auto_download=False)
            reconstructed_coords = pm.reconstruct_points(pts, age_ma=float(req.age))
        except Exception:
            reconstructed_coords = None

    results = []
    for i, loc in enumerate(req.locations):
        if reconstructed_coords is not None and i < len(reconstructed_coords):
            plat = round(float(reconstructed_coords[i, 0]), 2)
            plon = round(float(reconstructed_coords[i, 1]), 2)
        else:
            # Approximate continental drift preview fallback if PlateModel is not yet downloaded
            drift_lat = loc.lat - 0.08 * float(req.age) * (1 if loc.lat > 0 else -0.5)
            drift_lon = ((loc.lon + 0.12 * float(req.age) + 180.0) % 360.0) - 180.0
            plat = round(float(max(-89.5, min(89.5, drift_lat))), 2)
            plon = round(float(drift_lon), 2)

        results.append({
            "name": loc.name,
            "color": loc.color,
            "modern_lat": loc.lat,
            "modern_lon": loc.lon,
            "paleo_lat": plat,
            "paleo_lon": plon,
        })

    return {"age": req.age, "reconstructed": results}


@app.post("/api/preview/eval")
def preview_eval(
    project: GlobeProject,
    preview_n_points: Optional[int] = Query(default=None),
) -> Dict[str, Any]:
    """Evaluates the authoritative Python GlobeModel and returns base64 WebGL typed-array buffers."""
    try:
        return evaluate_preview_mesh(project, preview_n_points=preview_n_points)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/preview/grid-data")
def preview_grid_data(project: GlobeProject) -> Dict[str, Any]:
    """Returns downsampled equirectangular elevation & RGB buffers for 60fps WebWorker preview."""
    try:
        return get_grid_buffer_for_worker(project)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/preview/map2d")
def preview_map2d(project: GlobeProject) -> Dict[str, Any]:
    """Renders 2D equirectangular map and colorbar PNG data URLs."""
    try:
        return render_2d_map_and_colorbar(project)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/magnets/optimize")
def magnets_optimize(project: GlobeProject) -> Dict[str, Any]:
    """Computes the 360-degree equatorial cross-section profile and optimizes magnet positions."""
    try:
        return optimize_and_inspect_magnets(project)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/magnets/test-piece")
def magnets_test_piece(req: MagnetTestPieceRequest) -> Dict[str, Any]:
    """Generates a physical magnet calibration test piece STL file."""
    try:
        return create_calibration_test_piece(req, repo_root=REPO_ROOT)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/filaments/palette")
def filaments_palette(cfg: FilamentsConfigModel) -> Dict[str, Any]:
    """Generates all discrete Full-Spectrum optical filament combinations [00]..[34]."""
    try:
        return generate_palette_response(cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/filaments/match")
def filaments_match(req: FilamentMatchRequest) -> Dict[str, Any]:
    """Finds the closest optical filament recipe for a target color using CIE Delta-E."""
    try:
        return match_target_color_response(req.target_hex, req.filaments)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/datasets/catalog")
def datasets_catalog() -> Dict[str, Any]:
    """Lists all online datasets with local cache status and file sizes."""
    return get_datasets_catalog()


@app.get("/api/datasets/available-media")
def datasets_available_media() -> Dict[str, Any]:
    """Returns categorized vector shapefiles, raster images, and local uploaded files."""
    return get_media_and_datasets()


@app.post("/api/datasets/download")
def datasets_download(req: DatasetDownloadRequest) -> Dict[str, Any]:
    """Triggers an online dataset download into the local cache."""
    try:
        return trigger_dataset_download(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/files/browse")
def files_browse(path: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """Browses directories and supported data/image/shapefile files on the local machine."""
    return browse_local_files(path=path, default_root=REPO_ROOT)


@app.post("/api/files/upload")
async def files_upload(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Uploads a user data file (.nc, .tif, .png, .jpg, .svg, .json) to .download_cache/uploads/."""
    upload_dir = os.path.join(datasets._get_cache_dir(), "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename or "uploaded_file")
    dest_path = os.path.abspath(os.path.join(upload_dir, safe_name))
    with open(dest_path, "wb") as out_f:
        shutil.copyfileobj(file.file, out_f)
    return {
        "filename": safe_name,
        "filepath": dest_path,
        "size_bytes": os.path.getsize(dest_path),
    }


@app.post("/api/grids/inspect-netcdf")
def grids_inspect_netcdf(req: InspectNetCDFRequest) -> Dict[str, Any]:
    """Inspects variables and coordinate dimensions inside a local NetCDF file."""
    try:
        return inspect_netcdf_file(req.filepath)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/codegen/python")
def codegen_python(project: GlobeProject) -> Dict[str, str]:
    """Generates standalone Python (.py) and Jupyter Notebook (.ipynb) code for the project."""
    return generate_python_and_notebook(project)


@app.post("/api/export/render")
def export_render(project: GlobeProject) -> Dict[str, Any]:
    """Renders the definitive full-resolution Python GlobeModel and exports .3mf/.obj/.stl."""
    try:
        return export_project_model(project, repo_root=REPO_ROOT)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/exports/download")
def exports_download(path: str = Query(...)):
    """Downloads a generated .3mf, .obj, or .stl file to the browser."""
    abs_p = os.path.abspath(path)
    if not os.path.isfile(abs_p):
        raise HTTPException(status_code=404, detail=f"Exported file not found: {abs_p}")
    return FileResponse(abs_p, filename=os.path.basename(abs_p))


@app.post("/api/exports/reveal")
def exports_reveal(req: RevealFileRequest) -> Dict[str, Any]:
    """Reveals a saved file in Windows File Explorer."""
    abs_p = os.path.abspath(req.path)
    if not os.path.exists(abs_p):
        raise HTTPException(status_code=404, detail=f"Path not found: {abs_p}")
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", abs_p])
        return {"revealed": True, "path": abs_p}
    except Exception as e:
        return {"revealed": False, "error": str(e), "path": abs_p}


# Mount built frontend assets if present
FRONTEND_DIST = os.path.join(WEBAPP_DIR, "frontend", "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
