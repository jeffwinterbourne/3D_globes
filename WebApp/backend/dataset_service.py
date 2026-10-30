"""Dataset catalog, cache status inspection, online downloader, and local filesystem browser."""

import os
from typing import Any, Dict, List, Optional
from netCDF4 import Dataset as NCFile

from globe3d import datasets
from .models import DatasetDownloadRequest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


SUPPORTED_EXTENSIONS = {
    ".nc",
    ".grd",
    ".tif",
    ".tiff",
    ".shp",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".rot",
    ".gpml",
    ".ttf",
    ".otf",
    ".json",
}


def get_datasets_catalog() -> Dict[str, Any]:
    """Returns a comprehensive catalog of all online datasets with local cache status and file sizes.

    Returns:
        dict: Dataset entries, cache_dir, and Scotese directory path.
    """
    cache_dir = datasets._get_cache_dir()
    scotese_dir = datasets.paleo.find_scotese_data_dir()

    import fnmatch

    catalog_specs = [
        {
            "id": "topography.earth",
            "category": "topography",
            "dataset": "earth",
            "name": "Earth Global Relief (ETOPO / GEBCO)",
            "description": "Earth global bedrock/surface relief grid from GMT server or ETOPO.",
            "expected_file": "earth_relief_30m_g.grd",
            "expected_patterns": ["earth_relief_*_g.grd", "ETOPO*.nc", "ETOPO*.grd*"],
            "default_params": {"resolution": "30m"},
        },
        {
            "id": "topography.gebco",
            "category": "topography",
            "dataset": "gebco",
            "name": "GEBCO Global Bathymetry & Relief",
            "description": "Global ocean bathymetry and land topography grid.",
            "expected_file": "gebco_grid.nc",
            "expected_patterns": ["gebco*.nc", "gebco_grid.nc"],
            "default_params": {},
        },
        {
            "id": "topography.mars",
            "category": "topography",
            "dataset": "mars",
            "name": "Mars MOLA Global Topography",
            "description": "Mars Orbiter Laser Altimeter planetary relief.",
            "expected_file": "mars_relief_30m_g.grd",
            "expected_patterns": ["mars_relief_*_g.grd", "Mars_MGS_MOLA*.tif", "mars_relief_30m.nc"],
            "default_params": {"resolution": "30m"},
        },
        {
            "id": "topography.moon",
            "category": "topography",
            "dataset": "moon",
            "name": "Moon LOLA Global Topography",
            "description": "Lunar Orbiter Laser Altimeter global elevation.",
            "expected_file": "moon_relief_30m_g.grd",
            "expected_patterns": ["moon_relief_*_g.grd", "Lunar_LRO_LOLA*.tif", "moon_relief_30m.nc"],
            "default_params": {"resolution": "30m"},
        },
        {
            "id": "topography.venus",
            "category": "topography",
            "dataset": "venus",
            "name": "Venus Magellan Global Topography",
            "description": "Magellan radar altimetry global relief of Venus.",
            "expected_file": "venus_relief_30m_g.grd",
            "expected_patterns": ["venus_relief_*_g.grd", "Venus_Magellan*.nc", "venus_relief_30m.nc"],
            "default_params": {"resolution": "30m"},
        },
        {
            "id": "topography.mercury",
            "category": "topography",
            "dataset": "mercury",
            "name": "Mercury MESSENGER Global Topography",
            "description": "MESSENGER global relief of Mercury.",
            "expected_file": "mercury_relief_30m_g.grd",
            "expected_patterns": ["mercury_relief_*_g.grd", "Mercury_Messenger*.tif"],
            "default_params": {"resolution": "30m"},
        },
        {
            "id": "tomography.s40rts",
            "category": "tomography",
            "dataset": "s40rts",
            "name": "S40RTS Seismic Mantle Tomography",
            "description": "3D shear-wave velocity perturbations in the Earth's mantle.",
            "expected_file": "S40RTS_dvs.nc",
            "expected_patterns": ["S40RTS*.nc"],
            "default_params": {"depth": 2850.0},
        },
        {
            "id": "geoid.egm2008",
            "category": "geoid",
            "dataset": "egm2008",
            "name": "EGM2008 Global Geoid Undulation",
            "description": "Earth Gravitational Model 2008 geoid height anomaly.",
            "expected_file": "us_nga_egm2008_1.tif",
            "expected_patterns": ["*egm2008*.tif", "*egm2008*.nc"],
            "default_params": {"downsample_factor": 5},
        },
        {
            "id": "crust.crust1",
            "category": "crust",
            "dataset": "crust1",
            "name": "CRUST1.0 Global Crustal Boundaries",
            "description": "1x1 degree global crustal layers and Moho depth.",
            "expected_file": "crust1.0.tar.gz",
            "expected_patterns": ["crust1*"],
            "default_params": {"layer": "moho"},
        },
        {
            "id": "lithosphere.thickness",
            "category": "lithosphere",
            "dataset": "thickness",
            "name": "LITHO1.0 Lithospheric Thickness & LAB",
            "description": "Global depth to the Lithosphere-Asthenosphere Boundary.",
            "expected_file": "LITHO1.0.nc",
            "expected_patterns": ["LITHO*.nc"],
            "default_params": {"parameter": "lab"},
        },
        {
            "id": "dynamic_topography.hoggard2016",
            "category": "dynamic_topography",
            "dataset": "hoggard2016",
            "name": "Hoggard et al. (2016) Residual Dynamic Topography",
            "description": "Observational residual dynamic topography spot grid.",
            "expected_file": "spot.dat",
            "expected_patterns": ["spot.dat", "*Hoggard*.csv"],
            "default_params": {"grid_step": 1.0},
        },
        {
            "id": "gravity.bouguer",
            "category": "gravity",
            "dataset": "bouguer",
            "name": "NOAA Global Bouguer Gravity Anomaly",
            "description": "Global Bouguer gravity anomaly grid.",
            "expected_file": "bouguer_anomaly.nc",
            "expected_patterns": ["bouguer*.nc"],
            "default_params": {},
        },
        {
            "id": "magnetics.emag2",
            "category": "magnetics",
            "dataset": "emag2",
            "name": "EMAG2v3 Global Magnetic Anomalies",
            "description": "Earth Magnetic Anomaly Grid (2-arc-minute resolution).",
            "expected_file": "EMAG2_V3_Upward_Continued_GeoTIFF.zip",
            "expected_patterns": ["EMAG2*.zip", "EMAG2*"],
            "default_params": {"downsample_factor": 5},
        },
        {
            "id": "shapefiles.land",
            "category": "shapefiles",
            "dataset": "land",
            "name": "Natural Earth 1:110m Land Polygons",
            "description": "Global continental and island polygon boundaries.",
            "expected_file": "ne_110m_land.zip",
            "expected_patterns": ["ne_110m_land.zip", "ne_110m_land"],
            "default_params": {},
        },
        {
            "id": "shapefiles.coastline",
            "category": "shapefiles",
            "dataset": "coastline",
            "name": "Natural Earth 1:110m Coastline Vectors",
            "description": "Global coastline line vectors.",
            "expected_file": "ne_110m_coastline.zip",
            "expected_patterns": ["ne_110m_coastline.zip", "ne_110m_coastline"],
            "default_params": {},
        },
        {
            "id": "paleo.scotese_1d",
            "category": "paleo",
            "dataset": "scotese",
            "name": "Scotese PALEOMAP 1° PaleoDEMs & PaleoAtlas (0-540 Ma)",
            "description": "88 deep-time paleogeographic DEMs (1 deg) + PaleoAtlas v3 rasters & PlateModel.",
            "expected_file": "scotese",
            "expected_patterns": ["scotese*"],
            "default_params": {"resolution": "1d"},
        },
        {
            "id": "paleo.scotese_6m",
            "category": "paleo",
            "dataset": "scotese",
            "name": "Scotese PALEOMAP 6-arcmin High-Res PaleoDEMs (0-540 Ma)",
            "description": "88 high-resolution (6 arc-minute) PaleoDEMs from Zenodo Record 5460860.",
            "expected_file": "scotese",
            "expected_patterns": ["scotese*"],
            "default_params": {"resolution": "6m"},
        },
    ]

    entries = []
    for spec in catalog_specs:
        fields_meta: Dict[str, Any] = {}
        if spec["category"] == "paleo":
            cached = scotese_dir is not None and os.path.isdir(scotese_dir)
            size_bytes = 0
            local_path = scotese_dir or os.path.join(cache_dir, "scotese")
            if cached and scotese_dir:
                for root, _, files in os.walk(scotese_dir):
                    for fn in files:
                        try:
                            size_bytes += os.path.getsize(os.path.join(root, fn))
                        except OSError:
                            pass
        else:
            pats = spec.get("expected_patterns") or [spec.get("expected_file", "")]
            cached = False
            size_bytes = 0
            local_path = os.path.join(cache_dir, pats[0])

            if os.path.isdir(cache_dir):
                for item in sorted(os.listdir(cache_dir)):
                    for pat in pats:
                        if fnmatch.fnmatch(item.lower(), pat.lower()):
                            p = os.path.join(cache_dir, item)
                            try:
                                if os.path.isfile(p) and os.path.getsize(p) > 0:
                                    cached = True
                                    size_bytes = os.path.getsize(p)
                                    local_path = p
                                    break
                                elif os.path.isdir(p):
                                    sz = sum(os.path.getsize(os.path.join(r, f)) for r, _, fl in os.walk(p) for f in fl)
                                    if sz > 0:
                                        cached = True
                                        size_bytes = sz
                                        local_path = p
                                        break
                            except OSError:
                                pass
                    if cached:
                        break

            if cached and os.path.isfile(local_path) and local_path.endswith((".nc", ".grd")):
                try:
                    insp = inspect_netcdf_file(local_path)
                    fields_meta = {
                        "detected_lat": insp.get("detected_lat"),
                        "detected_lon": insp.get("detected_lon"),
                        "detected_data": insp.get("detected_data"),
                        "dimensions": insp.get("dimensions"),
                        "variables": [v["name"] for v in insp.get("variables", [])],
                    }
                except Exception:
                    pass

        entries.append({
            **spec,
            "cached": bool(cached),
            "size_bytes": int(size_bytes),
            "local_path": local_path,
            **fields_meta,
        })

    return {
        "cache_dir": cache_dir,
        "scotese_dir": scotese_dir,
        "datasets": entries,
    }


def trigger_dataset_download(req: DatasetDownloadRequest) -> Dict[str, Any]:
    """Triggers an online download for the specified dataset category and name.

    Args:
        req (DatasetDownloadRequest): Category, dataset name, and parameters.

    Returns:
        dict: Updated dataset status and catalog.
    """
    cat = req.category.lower()
    ds = req.dataset.lower()
    p = dict(req.params or {})

    if cat == "paleo" or ds.startswith("scotese"):
        res = str(p.get("resolution", "1d"))
        datasets.paleo.download_scotese_data(resolution=res, include_atlas=True)
    elif cat == "topography":
        fn = getattr(datasets.topography, ds)
        fn(**p)
    elif cat == "tomography":
        datasets.tomography.s40rts(**p)
    elif cat == "geoid":
        datasets.geoid.egm2008(**p)
    elif cat == "crust":
        datasets.crust.crust1(**p)
    elif cat == "lithosphere":
        datasets.lithosphere.thickness(**p)
    elif cat == "dynamic_topography":
        datasets.dynamic_topography.hoggard2016(**p)
    elif cat == "gravity":
        datasets.gravity.bouguer(**p)
    elif cat == "magnetics":
        datasets.magnetics.emag2(**p)
    elif cat == "shapefiles":
        fn = getattr(datasets.shapefiles, ds)
        fn(**p)
    else:
        raise ValueError(f"Unknown dataset category '{cat}' / '{ds}'.")

    return get_datasets_catalog()


def browse_local_files(path: Optional[str] = None, default_root: Optional[str] = None) -> Dict[str, Any]:
    """Lists directories and supported geospatial/image/font files in a local folder.

    Args:
        path (str, optional): Directory path to browse. Defaults to repository root.
        default_root (str, optional): Fallback directory path.

    Returns:
        dict: Current path, parent path, directories, and matching files.
    """
    target = path if (path and os.path.isdir(path)) else (default_root or os.getcwd())
    target = os.path.abspath(target)
    parent = os.path.dirname(target)

    dirs: List[Dict[str, Any]] = []
    files: List[Dict[str, Any]] = []

    try:
        for entry in sorted(os.scandir(target), key=lambda e: (not e.is_dir(), e.name.lower())):
            if entry.name.startswith(".") and entry.name != ".download_cache":
                continue
            if entry.is_dir():
                dirs.append({"name": entry.name, "path": entry.path})
            elif entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    try:
                        sz = entry.stat().st_size
                    except OSError:
                        sz = 0
                    files.append({
                        "name": entry.name,
                        "path": entry.path,
                        "ext": ext,
                        "size_bytes": sz,
                    })
    except PermissionError:
        pass

    return {
        "current_path": target,
        "parent_path": parent if parent != target else None,
        "directories": dirs,
        "files": files,
    }


def inspect_netcdf_file(filepath: str) -> Dict[str, Any]:
    """Inspects variables, shapes, and auto-detected coordinate/data names in a NetCDF file.

    Args:
        filepath (str): Path to the local NetCDF (.nc or .grd) file.

    Returns:
        dict: Variables list, dimensions, and detected lat/lon/data variable names.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"NetCDF file not found: {filepath}")

    with NCFile(filepath, "r") as ds:
        variables = []
        for name, var in ds.variables.items():
            variables.append({
                "name": name,
                "dimensions": list(var.dimensions),
                "shape": list(var.shape),
                "dtype": str(var.dtype),
            })

        lat_var = next((c for c in ["lat", "latitude", "y"] if c in ds.variables), None)
        lon_var = next((c for c in ["lon", "longitude", "x"] if c in ds.variables), None)
        data_var = next((c for c in ["z", "v", "bouguer", "dvs"] if c in ds.variables), None)
        if data_var is None:
            for name, var in ds.variables.items():
                if name not in (lat_var, lon_var) and len(var.shape) >= 2:
                    data_var = name
                    break

        dims = {k: int(len(v)) for k, v in ds.dimensions.items()}

    return {
        "filepath": filepath,
        "dimensions": dims,
        "variables": variables,
        "detected_lat": lat_var,
        "detected_lon": lon_var,
        "detected_data": data_var,
    }


def get_media_and_datasets() -> Dict[str, Any]:
    """Discovers and categorizes all available vectors (shapefiles/GeoJSON), raster images,
    and user uploads across the project and cache directories.
    """
    cache_dir = datasets._get_cache_dir()
    uploads_dir = os.path.join(cache_dir, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    land_shp = os.path.join(cache_dir, "ne_110m_land", "ne_110m_land.shp")
    coast_shp = os.path.join(cache_dir, "ne_110m_coastline", "ne_110m_coastline.shp")

    vectors: List[Dict[str, Any]] = [
        {
            "id": "builtin_land",
            "name": "Natural Earth 1:110m Land Polygons (Built-in)",
            "type": "polygon",
            "category": "Built-in Vectors",
            "identifier": "land",
            "path": land_shp,
            "cached": os.path.isfile(land_shp),
            "description": "Standard continental landmass polygons for PolygonDisplacer & PolygonColourer.",
        },
        {
            "id": "builtin_coastline",
            "name": "Natural Earth 1:110m Coastlines (Built-in)",
            "type": "line",
            "category": "Built-in Vectors",
            "identifier": "coastline",
            "path": coast_shp,
            "cached": os.path.isfile(coast_shp),
            "description": "Coastline vectors for LineDisplacer & LineColourer.",
        },
    ]

    vector_seen = {os.path.abspath(v["path"]) for v in vectors if v.get("path")}
    for search_root in (uploads_dir, cache_dir, REPO_ROOT):
        if not os.path.isdir(search_root):
            continue
        for root, dirs, files in os.walk(search_root):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "dist", "__pycache__", ".ipynb_checkpoints")]
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext in (".shp", ".geojson", ".gpkg"):
                    fpath = os.path.abspath(os.path.join(root, fn))
                    if fpath not in vector_seen:
                        vector_seen.add(fpath)
                        vectors.append({
                            "id": f"vec_{len(vectors)}",
                            "name": fn,
                            "type": "polygon" if ("poly" in fn.lower() or "land" in fn.lower()) else "line",
                            "category": "Local / Uploaded Vectors",
                            "identifier": fpath,
                            "path": fpath,
                            "cached": True,
                            "size_bytes": os.path.getsize(fpath),
                            "description": f"Vector geometry ({ext})",
                        })

    images: List[Dict[str, Any]] = []
    img_seen = set()
    for search_root in (
        os.path.join(REPO_ROOT, "context", "height_maps"),
        os.path.join(REPO_ROOT, "outputs"),
        uploads_dir,
        datasets.paleo.find_scotese_data_dir() or "",
    ):
        if not search_root or not os.path.isdir(search_root):
            continue
        for root, dirs, files in os.walk(search_root):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "dist", "__pycache__", ".ipynb_checkpoints")]
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
                    fpath = os.path.abspath(os.path.join(root, fn))
                    if fpath not in img_seen:
                        img_seen.add(fpath)
                        images.append({
                            "id": f"img_{len(images)}",
                            "name": fn,
                            "category": "Equirectangular & Surface Images",
                            "identifier": fpath,
                            "path": fpath,
                            "size_bytes": os.path.getsize(fpath),
                            "ext": ext,
                        })

    return {
        "cache_dir": cache_dir,
        "uploads_dir": uploads_dir,
        "vectors": vectors,
        "images": images,
    }
