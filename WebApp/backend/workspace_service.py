import os
import json
import re
import shutil
import time
from typing import Dict, Any, List, Optional
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_FILE_PATH = os.path.expanduser("~/.globe3d_studio_config.json")
DEFAULT_WORKSPACE_DIR = os.path.abspath(os.path.join(REPO_ROOT, "workspace"))


def get_stored_config() -> Dict[str, Any]:
    """Retrieves persistent Studio workspace configuration, falling back to defaults."""
    cfg = {"working_dir": DEFAULT_WORKSPACE_DIR}
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("working_dir"):
                    cfg["working_dir"] = os.path.abspath(data["working_dir"])
        except Exception:
            pass
    ensure_workspace_structure(cfg["working_dir"])
    return cfg


def save_stored_config(working_dir: str) -> Dict[str, Any]:
    """Updates and persists the active working directory."""
    abs_dir = os.path.abspath(working_dir)
    ensure_workspace_structure(abs_dir)
    cfg = {"working_dir": abs_dir, "updated_at": time.time()}
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Warning: could not save config to {CONFIG_FILE_PATH}: {e}")
    return cfg


def ensure_workspace_structure(working_dir: str):
    """Ensures projects/, datasets/, and .download_cache/ subdirectories exist in the working dir."""
    os.makedirs(os.path.join(working_dir, "projects"), exist_ok=True)
    os.makedirs(os.path.join(working_dir, "datasets"), exist_ok=True)
    os.makedirs(os.path.join(working_dir, ".download_cache"), exist_ok=True)
    os.makedirs(os.path.join(working_dir, ".download_cache", "thumbnails"), exist_ok=True)

    registry_path = os.path.join(working_dir, "dataset_registry.json")
    if not os.path.exists(registry_path):
        try:
            with open(registry_path, "w", encoding="utf-8") as f:
                json.dump({"datasets": []}, f, indent=2)
        except Exception:
            pass


def _slugify(text: str) -> str:
    """Converts a string to a filesystem-friendly directory name slug."""
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    s = re.sub(r"[-\s]+", "_", s)
    return s or "untitled_project"


def list_workspace_projects(working_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists all saved projects in the workspace projects/ directory, ordered by modified time."""
    if not working_dir:
        working_dir = get_stored_config()["working_dir"]
    ensure_workspace_structure(working_dir)

    projects_dir = os.path.join(working_dir, "projects")
    results = []

    if not os.path.exists(projects_dir):
        return results

    for entry in os.listdir(projects_dir):
        entry_path = os.path.join(projects_dir, entry)
        if os.path.isdir(entry_path):
            project_json_path = os.path.join(entry_path, "project.json")
            if os.path.exists(project_json_path):
                try:
                    mtime = os.path.getmtime(project_json_path)
                    with open(project_json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    results.append({
                        "slug": entry,
                        "id": data.get("id", entry),
                        "name": data.get("name", entry),
                        "description": data.get("description", ""),
                        "category": data.get("category", "user"),
                        "mode": data.get("mode", "custom"),
                        "paleo_enabled": bool(data.get("paleo", {}).get("enabled", False)),
                        "paleo_age": data.get("paleo", {}).get("age", 0),
                        "updated_at": mtime,
                        "updated_at_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)),
                        "path": project_json_path,
                        "has_thumbnail": os.path.exists(os.path.join(entry_path, "thumbnail.png")),
                    })
                except Exception as e:
                    print(f"Error reading project at {project_json_path}: {e}")

    results.sort(key=lambda x: x["updated_at"], reverse=True)
    return results


def save_workspace_project(working_dir: Optional[str], project_data: Dict[str, Any], slug: Optional[str] = None) -> Dict[str, Any]:
    """Saves a project definition to <working_dir>/projects/<slug>/project.json."""
    if not working_dir:
        working_dir = get_stored_config()["working_dir"]
    ensure_workspace_structure(working_dir)

    if not slug:
        slug = _slugify(project_data.get("name") or project_data.get("id") or "project")

    project_dir = os.path.join(working_dir, "projects", slug)
    os.makedirs(project_dir, exist_ok=True)
    project_json_path = os.path.join(project_dir, "project.json")

    with open(project_json_path, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=2)

    return {
        "status": "ok",
        "slug": slug,
        "path": project_json_path,
        "name": project_data.get("name", slug),
        "updated_at": os.path.getmtime(project_json_path),
    }


def open_workspace_project(working_dir: Optional[str], slug_or_path: str) -> Dict[str, Any]:
    """Loads a project JSON either from a slug or an absolute filepath."""
    if not working_dir:
        working_dir = get_stored_config()["working_dir"]

    if os.path.isabs(slug_or_path) and os.path.exists(slug_or_path):
        target_path = slug_or_path
    else:
        target_path = os.path.join(working_dir, "projects", slug_or_path, "project.json")

    if not os.path.exists(target_path):
        raise FileNotFoundError(f"Project not found at: {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        project_dict = json.load(f)

    return project_dict


def duplicate_workspace_project(working_dir: Optional[str], source_slug: str, new_name: Optional[str] = None) -> Dict[str, Any]:
    """Creates a copy of an existing project under a new slug and modified name."""
    if not working_dir:
        working_dir = get_stored_config()["working_dir"]

    orig = open_workspace_project(working_dir, source_slug)
    base_name = new_name or f"{orig.get('name', source_slug)} (Copy)"
    new_slug = _slugify(base_name)

    # Avoid slug collisions
    counter = 1
    target_slug = new_slug
    while os.path.exists(os.path.join(working_dir, "projects", target_slug)):
        target_slug = f"{new_slug}_{counter}"
        counter += 1

    duplicated_data = dict(orig)
    duplicated_data["name"] = base_name
    duplicated_data["id"] = target_slug

    return save_workspace_project(working_dir, duplicated_data, slug=target_slug)


# ---------------------------------------------------------------------------
# Shared Dataset Registry & Zero-Copy Virtual Duplication
# ---------------------------------------------------------------------------

def _load_dataset_registry(working_dir: str) -> Dict[str, Any]:
    """Loads dataset_registry.json from the workspace."""
    reg_path = os.path.join(working_dir, "dataset_registry.json")
    if os.path.exists(reg_path):
        try:
            with open(reg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"datasets": []}


def _save_dataset_registry(working_dir: str, registry_data: Dict[str, Any]):
    """Persists dataset_registry.json."""
    reg_path = os.path.join(working_dir, "dataset_registry.json")
    with open(reg_path, "w", encoding="utf-8") as f:
        json.dump(registry_data, f, indent=2)


def list_workspace_datasets(working_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Scans <working_dir>/datasets/ and merges physical files with dataset_registry.json.
    
    Automatically registers any uncataloged physical file.
    Supports zero-copy virtual datasets that point to the same physical file.
    """
    if not working_dir:
        working_dir = get_stored_config()["working_dir"]
    ensure_workspace_structure(working_dir)

    datasets_dir = os.path.join(working_dir, "datasets")
    registry = _load_dataset_registry(working_dir)
    existing_entries = {entry["id"]: entry for entry in registry.get("datasets", [])}
    
    modified = False

    # Scan physical files
    if os.path.exists(datasets_dir):
        for fname in os.listdir(datasets_dir):
            fpath = os.path.join(datasets_dir, fname)
            if not os.path.isfile(fpath):
                continue
            
            ext = os.path.splitext(fname)[1].lower()
            if ext not in [".nc", ".grd", ".tif", ".tiff", ".geojson", ".shp", ".png", ".jpg", ".jpeg", ".svg"]:
                continue

            file_id = os.path.splitext(fname)[0].replace(" ", "_").lower()
            
            # Check if any registered entry already references this physical filename
            matched = any(e.get("physical_filename") == fname for e in existing_entries.values())
            if not matched:
                # Auto-register this file
                kind = "grid" if ext in [".nc", ".grd", ".tif", ".tiff"] else ("vector" if ext in [".geojson", ".shp"] else "raster")
                new_entry = {
                    "id": file_id,
                    "name": fname.replace("_", " ").title(),
                    "physical_filename": fname,
                    "file_type": kind,
                    "file_ext": ext,
                    "size_bytes": os.path.getsize(fpath),
                    "netcdf_vars": None,
                    "default_ops": [],
                    "parent_dataset_id": None,
                    "created_at": time.time(),
                }

                if ext in [".nc", ".grd"]:
                    try:
                        from WebApp.backend.dataset_service import inspect_netcdf_file
                        info = inspect_netcdf_file(fpath)
                        new_entry["netcdf_vars"] = {
                            "lat": info.get("detected_lat"),
                            "lon": info.get("detected_lon"),
                            "data": info.get("detected_data"),
                        }
                    except Exception:
                        pass

                existing_entries[file_id] = new_entry
                modified = True

    if modified:
        registry["datasets"] = list(existing_entries.values())
        _save_dataset_registry(working_dir, registry)

    # Attach live existence and full paths
    result = []
    for item in existing_entries.values():
        entry = dict(item)
        phys = entry.get("physical_filename") or ""
        phys_path = os.path.join(datasets_dir, phys)
        entry["physical_path"] = phys_path
        entry["exists"] = os.path.exists(phys_path)
        if entry["exists"]:
            entry["size_bytes"] = os.path.getsize(phys_path)
        entry["is_virtual"] = bool(entry.get("parent_dataset_id"))
        result.append(entry)

    result.sort(key=lambda x: x["name"])
    return result


def register_or_update_dataset(working_dir: Optional[str], entry: Dict[str, Any]) -> Dict[str, Any]:
    """Updates metadata (netcdf_vars, default_ops, name, etc.) for a dataset in dataset_registry.json."""
    if not working_dir:
        working_dir = get_stored_config()["working_dir"]
    ensure_workspace_structure(working_dir)

    registry = _load_dataset_registry(working_dir)
    entries = registry.get("datasets", [])
    
    target_id = entry.get("id")
    if not target_id:
        raise ValueError("Dataset entry must contain an 'id'.")

    idx = next((i for i, e in enumerate(entries) if e.get("id") == target_id), None)
    if idx is not None:
        entries[idx].update(entry)
    else:
        entries.append(entry)

    registry["datasets"] = entries
    _save_dataset_registry(working_dir, registry)
    return entry


def duplicate_workspace_dataset(
    working_dir: Optional[str],
    source_id: str,
    new_id: Optional[str] = None,
    new_name: Optional[str] = None,
    default_ops: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Zero-copy dataset duplication!
    
    Creates a new virtual dataset entry referencing the SAME underlying physical file
    on disk, but with separate default operations, netcdf variable configuration, and naming.
    """
    if not working_dir:
        working_dir = get_stored_config()["working_dir"]
    ensure_workspace_structure(working_dir)

    datasets = list_workspace_datasets(working_dir)
    source = next((d for d in datasets if d["id"] == source_id), None)
    if not source:
        raise ValueError(f"Source dataset '{source_id}' not found.")

    parent_id = source.get("parent_dataset_id") or source_id
    gen_id = new_id or f"{source_id}_copy"
    gen_name = new_name or f"{source.get('name', source_id)} (Virtual Copy)"

    # Ensure uniqueness of id
    existing_ids = {d["id"] for d in datasets}
    counter = 1
    final_id = gen_id
    while final_id in existing_ids:
        final_id = f"{gen_id}_{counter}"
        counter += 1

    new_entry = {
        "id": final_id,
        "name": gen_name,
        "physical_filename": source["physical_filename"],
        "file_type": source.get("file_type", "grid"),
        "file_ext": source.get("file_ext", ""),
        "size_bytes": source.get("size_bytes", 0),
        "netcdf_vars": dict(source.get("netcdf_vars") or {}),
        "default_ops": default_ops if default_ops is not None else list(source.get("default_ops") or []),
        "parent_dataset_id": parent_id,
        "created_at": time.time(),
    }

    register_or_update_dataset(working_dir, new_entry)
    new_entry["physical_path"] = source.get("physical_path")
    new_entry["exists"] = source.get("exists", True)
    new_entry["is_virtual"] = True
    return new_entry


def generate_dataset_thumbnail(working_dir: Optional[str], dataset_id: str) -> Optional[str]:
    """Generates a small 2D PNG thumbnail for a workspace dataset and returns its filesystem path."""
    if not working_dir:
        working_dir = get_stored_config()["working_dir"]
    ensure_workspace_structure(working_dir)

    thumb_dir = os.path.join(working_dir, ".download_cache", "thumbnails")
    thumb_path = os.path.join(thumb_dir, f"{dataset_id}.png")

    if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
        return thumb_path

    datasets = list_workspace_datasets(working_dir)
    ds = next((d for d in datasets if d["id"] == dataset_id), None)
    if not ds or not ds.get("exists"):
        return None

    physical_path = ds["physical_path"]
    file_type = ds.get("file_type")
    ext = ds.get("file_ext", "").lower()

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(2.5, 1.3), dpi=80)
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        ax.axis("off")

        if file_type == "raster" or ext in [".png", ".jpg", ".jpeg"]:
            from PIL import Image
            img = Image.open(physical_path)
            img.thumbnail((200, 100))
            img.save(thumb_path, "PNG")
            plt.close(fig)
            return thumb_path

        elif file_type == "grid" or ext in [".nc", ".grd", ".tif", ".tiff"]:
            try:
                import xarray as xr
                with xr.open_dataset(physical_path) as ds_xr:
                    data_var = (ds.get("netcdf_vars") or {}).get("data")
                    if not data_var or data_var not in ds_xr.data_vars:
                        # pick first 2D data var
                        for vname, var in ds_xr.data_vars.items():
                            if len(var.shape) >= 2:
                                data_var = vname
                                break
                    if data_var and data_var in ds_xr:
                        arr = ds_xr[data_var].values
                        # downsample
                        step_y = max(1, arr.shape[0] // 80)
                        step_x = max(1, arr.shape[1] // 160)
                        sub = arr[::step_y, ::step_x]
                        ax.imshow(sub, cmap="terrain", origin="lower", aspect="auto")
                        fig.savefig(thumb_path, format="png", bbox_inches="tight", pad_inches=0)
                        plt.close(fig)
                        return thumb_path
            except Exception:
                pass

        # Fallback placeholder thumbnail
        ax.text(0.5, 0.5, ds.get("name", dataset_id)[:16], color="#94a3b8", ha="center", va="center", fontsize=8)
        ax.set_facecolor("#1e293b")
        fig.patch.set_facecolor("#0f172a")
        fig.savefig(thumb_path, format="png", bbox_inches="tight", pad_inches=0)
        plt.close(fig)
        return thumb_path
    except Exception as e:
        print(f"Failed to generate thumbnail for {dataset_id}: {e}")
        return None
