# Globe3D Studio — Comprehensive UI Overhaul & Workspace Architecture Plan

> **Purpose of this Document**: This specification defines a complete, end-to-end implementation plan for the **Globe3D Studio v5.0 UI Overhaul**. It is written so that an engineering agent or developer can pick it up and implement every backend endpoint, disk layout, state transition, wizard step, gallery thumbnail pipeline, and shared dataset manager without ambiguity.

---

## 1. Architectural Overview & Core Goals

The overhaul transforms **Globe3D Studio** from a single-screen editor that immediately drops into an example into a structured **Project & Workspace CAD Environment** with six core pillars:

1. **Full-Screen Landing Page (`LandingScreen`)**:
   - **Continue a Project**: Browse projects stored in the active Working Directory, view their metadata/thumbnails, open directly, or **Open as Copy**.
   - **New Project (Wizard)**: Guided 5-step interactive setup (Base Geometry $\to$ Datasets $\to$ Displacement $\to$ Colour $\to$ Magnets).
   - **New Project (Blank)**: Immediately initializes a clean, hollow 3D sphere with zero datasets, zero displacements, and neutral styling.
   - **Load from Gallery**: Visual preset gallery with pre-rendered 3D/2D thumbnails for all 27+ built-in examples and paper recreations.
   - **Dataset & Media Manager**: Standalone & modal workspace manager for shared grids, shapefiles, and images with thumbnails, NetCDF variable mapping, default declarative operation pipelines, and zero-copy virtual dataset duplication.
2. **Working Directory & Multi-Project Disk Management**:
   - User-configurable **Working Directory** selectable from the UI (persisted in backend config + `localStorage`).
   - Houses the shared `.download_cache/`, shared user datasets (`datasets/`), and individual project folders (`projects/<project_slug>/`).
3. **Guided 5-Step New Project Wizard (`NewProjectWizardModal`)**:
   - Step-by-step interactive configurator that compiles choices into a valid `GlobeProject` JSON and opens the main Studio editor.
4. **Blank Project Template (`BLANK_GLOBE_PROJECT`)**:
   - Minimalist hollow sphere (`radius: 40mm`, `inner_ratio: 0.5`, `n_points: 500000`, `preview_n_points: 60000`) with empty `grids: {}`, `outer_displacements: []`, `inner_displacements: []`, and a single neutral base `ConstantColourer`.
5. **Pre-Rendered Gallery Thumbnails**:
   - Static & on-demand thumbnail generator producing `.png`/`.webp` previews for all presets in `WebApp/presets/` and user projects.
6. **Zero-Copy Shared Dataset & Pipeline Manager (`WorkspaceDataManager`)**:
   - Manages physical files (`grids`, `shapefiles`, `images`) alongside **Virtual Dataset Profiles** (`dataset_registry.json`).
   - Allows duplicating any dataset into multiple virtual entries with distinct NetCDF variable mappings (`lat_var`, `lon_var`, `data_var`) and default declarative operation chains (`smooth`, `fill`, `math`, `downsample`, `scale_offset`, `airy_moho`) **without duplicating the underlying NetCDF/GeoTIFF/Shapefile on disk**.
7. **Bugfix — Scotese Paleo Catalog `"0 Ma"` Time-Slice Dropdown Bug**:
   - Fixes the bug where all 88 Scotese PALEOMAP time slices in `SimplePaleoPanel.tsx` display as `0 Ma — <name> [Cenozoic]` and snap to `0 Ma` when selected.

---

## 1.5 Bugfix Specification: "Every Paleo Grid is 0 Ma" Dropdown Issue

### Root Cause
1. In [`src/globe3d/datasets.py`](file:///d:/OneDrive/python/3d_globes/git/3D_globes/src/globe3d/datasets.py#L834-L848) (`PaleoNamespace._load_metadata()`), `scotese_maps.csv` has columns `age_ma,map_id,name,dem_file_6min,dem_file_1deg,raster_file`. Each record dictionary exposes `r["age_ma"] = float(r["age_ma"])`, **not** `r["age"]`.
2. In [`WebApp/frontend/src/components/panels/SimplePaleoPanel.tsx`](file:///d:/OneDrive/python/3d_globes/git/3D_globes/WebApp/frontend/src/components/panels/SimplePaleoPanel.tsx#L68-L80), the `/api/paleo/catalog` response mapper reads:
   ```ts
   const age = Number(m.age ?? 0);
   ```
   Because `m.age` is `undefined`, `age` evaluates to `0` for all 88 slices, and `era` (`age <= 66 ? 'Cenozoic' : ...`) evaluates to `'Cenozoic'` for every single entry! Furthermore, because `<option key={s.age} value={s.age}>` has `value={0}` for all 88 options, selecting any option in the dropdown sets `paleo.age = 0`.

### Fix to Implement
1. **Backend (`src/globe3d/datasets.py` line 844)**:
   - Set both `r["age_ma"] = float(r["age_ma"])` and `r["age"] = float(r["age_ma"])` in `PaleoNamespace._load_metadata()`.
2. **Frontend (`WebApp/frontend/src/components/panels/SimplePaleoPanel.tsx` lines 69–78 & 150–160)**:
   - Update the catalog mapper to read `const age = Number(m.age_ma ?? m.age ?? 0);`.
   - Use a composite key `key={`${s.age}_${s.name}`}` on the `<option>` elements (since a few Scotese slices share nearby or identical ages) and allow selecting by slice index or `(age, name)` so both `paleo.age` and `paleo.name` update accurately when a time slice is chosen.

---

## 2. Working Directory & On-Disk File Hierarchy

### 2.1 Directory Layout
When a user selects a Working Directory (defaulting to `<REPO_ROOT>/workspace` or user-specified path such as `D:/Globe3D_Workspace`), the backend enforces and maintains the following directory structure:

```text
<WORKING_DIR>/
├── workspace_settings.json          # Active workspace metadata, recent projects list
├── dataset_registry.json            # Shared dataset definitions, NetCDF field mappings, virtual duplicates & default ops
├── .download_cache/                 # Shared online dataset cache (ETOPO, Mars, S40RTS, EGM2008, Scotese, Natural Earth)
├── datasets/                        # User-imported / shared local files available across ALL projects in this working dir
│   ├── grids/                       # .nc, .grd, .tif, .tiff
│   ├── vectors/                     # .shp (+ .shx, .dbf, .prj), .geojson
│   ├── images/                      # .png, .jpg, .svg
│   └── thumbnails/                  # Auto-generated 256x128 equirectangular preview PNGs keyed by dataset ID
└── projects/                        # One subfolder per saved user project
    ├── my_tectonic_globe/
    │   ├── project.json             # Canonical GlobeProject JSON
    │   ├── thumbnail.png            # 400x400 or 320x240 preview snapshot of the globe
    │   ├── exports/                 # Generated .3mf, .stl, .obj, .py, .ipynb outputs for this project
    │   └── local_assets/            # Optional project-private overrides (if any)
    └── paleo_jurassic_150ma/
        ├── project.json
        ├── thumbnail.png
        └── exports/
```

### 2.2 Global Backend Pointer (`~/.globe3d_studio_config.json`)
To remember the user's chosen `working_dir` across server restarts:
- Store a lightweight config file at `WebApp/backend/.studio_config.json` (and fallback `~/.globe3d_studio.json`):
  ```json
  {
    "working_dir": "D:/OneDrive/python/3d_globes/workspace",
    "recent_working_dirs": [
      "D:/OneDrive/python/3d_globes/workspace"
    ]
  }
  ```
- Whenever `working_dir` changes via `POST /api/workspace/select-dir`:
  1. Update `datasets._DEFAULT_CACHE_DIR` (or pass `cache_dir = os.path.join(working_dir, ".download_cache")` to all `globe3d.datasets` calls).
  2. Scan `<working_dir>/projects/*/project.json` to return the updated project list.
  3. Scan `<working_dir>/dataset_registry.json` and `<working_dir>/datasets/` to update the shared dataset catalog.

---

## 3. Shared Dataset Registry & Zero-Copy Virtual Duplication

### 3.1 Concept: Physical Storage vs. Dataset Profiles
A major requirement (Goal #6) is:
> *"Data manager manages the user grids / shapefiles included in the working folder, including a preview thumbnail, and each can be opened to change settings including fields for netcdf, default declarative operations. Datasets can be duplicated with different declarative operations without replicating the underlying data on disk."*

To achieve this cleanly:
- **Physical File**: Stored once on disk in `<working_dir>/datasets/grids/my_data.nc` or `<working_dir>/.download_cache/earth_relief_30m_g.grd`.
- **Dataset Profile (`WorkspaceDatasetEntry`)**: Stored in `<working_dir>/dataset_registry.json`. Multiple profiles can point to the exact same `physical_path`!

### 3.2 `WorkspaceDatasetEntry` Schema (`dataset_registry.json`)
```json
{
  "datasets": [
    {
      "id": "etopo_raw",
      "name": "Earth Relief 30m (Raw)",
      "kind": "grid",
      "source_type": "online",
      "online_category": "topography",
      "online_name": "earth",
      "online_params": { "resolution": "30m" },
      "physical_path": ".download_cache/earth_relief_30m_g.grd",
      "parent_dataset_id": null,
      "netcdf_vars": {
        "lat_var": "lat",
        "lon_var": "lon",
        "data_var": "z"
      },
      "default_ops": [],
      "cmap_preview": "terrain",
      "thumbnail_path": "datasets/thumbnails/etopo_raw.png",
      "stats": {
        "shape": [361, 721],
        "vmin": -7809.3,
        "vmax": 5430.0,
        "has_nans": false
      },
      "updated_at": "2026-10-30T16:30:00Z"
    },
    {
      "id": "etopo_smoothed_3deg",
      "name": "Earth Relief 30m (3° Spherical Smooth + Clamped)",
      "kind": "grid",
      "source_type": "online",
      "online_category": "topography",
      "online_name": "earth",
      "online_params": { "resolution": "30m" },
      "physical_path": ".download_cache/earth_relief_30m_g.grd",
      "parent_dataset_id": "etopo_raw",
      "netcdf_vars": {
        "lat_var": "lat",
        "lon_var": "lon",
        "data_var": "z"
      },
      "default_ops": [
        { "op": "fill", "fill_mode": "nearest", "fill_value": 0.0 },
        { "op": "smooth", "width_deg": 3.0 },
        { "op": "math", "math_op": "clamp", "min_val": -6000.0, "max_val": 6000.0 }
      ],
      "cmap_preview": "terrain",
      "thumbnail_path": "datasets/thumbnails/etopo_smoothed_3deg.png",
      "stats": {
        "shape": [361, 721],
        "vmin": -6000.0,
        "vmax": 4812.4,
        "has_nans": false
      },
      "updated_at": "2026-10-30T16:35:00Z"
    }
  ]
}
```

### 3.3 How Duplication Works
When the user clicks **"Duplicate Dataset"** on `etopo_raw` in the Dataset Manager:
1. A new `WorkspaceDatasetEntry` is created in `dataset_registry.json` with a new `id` (e.g. `etopo_raw_copy_1`), `parent_dataset_id: "etopo_raw"`, and the **same `physical_path`**.
2. Zero bytes of grid/shapefile data are copied on disk.
3. The user opens the duplicate's settings drawer in the Dataset Manager, customizes its `default_ops` (e.g., adds `smooth(width_deg=4.0)` and `math(log10)`), and clicks **Save & Update Thumbnail**.
4. The backend evaluates `_load_base_grid` + `default_ops`, computes updated `stats` (`vmin`, `vmax`), and renders a dedicated 256×128 thumbnail PNG (`datasets/thumbnails/etopo_raw_copy_1.png`) showing the effect of the declarative operations!
5. When a user adds this dataset to any project (in the Wizard or in the Studio's Datasets tab), the project's `GridSourceConfig` inherits the `physical_path`, `netcdf_vars`, and `default_ops` (which can still be further tweaked per-project if desired).

---

## 4. Backend Implementation Plan (`WebApp/backend/`)

### 4.1 New Module: `WebApp/backend/workspace_service.py`
Create `WebApp/backend/workspace_service.py` with the following functions:

1. **`get_workspace_state() -> Dict[str, Any]`**:
   - Reads `.studio_config.json` to get `working_dir`.
   - Ensures `<working_dir>/.download_cache`, `<working_dir>/datasets/{grids,vectors,images,thumbnails}`, and `<working_dir>/projects` exist.
   - Returns `{ "working_dir": ..., "recent_working_dirs": [...], "projects": list_workspace_projects(), "datasets": list_workspace_datasets() }`.

2. **`set_working_directory(path: str) -> Dict[str, Any]`**:
   - Validates/creates `path` on disk.
   - Updates `.studio_config.json` and prepends `path` to `recent_working_dirs`.
   - Updates `globe3d.datasets` cache directory resolution so `_get_cache_dir()` points to `<working_dir>/.download_cache`.
   - Auto-discovers any existing `.nc`, `.grd`, `.tif`, `.shp`, `.png` files in `<working_dir>/datasets/` and registers them in `dataset_registry.json` if not already present.
   - Returns the new `get_workspace_state()`.

3. **`list_workspace_projects() -> List[Dict[str, Any]]`**:
   - Scans `<working_dir>/projects/*/project.json`.
   - Returns a list of project summaries sorted by `updated_at` descending:
     ```json
     {
       "slug": "my_tectonic_globe",
       "name": "My Tectonic Globe",
       "description": "Hollow globe with 40x ETOPO...",
       "mode": "custom",
       "updated_at": "2026-10-30T16:20:00Z",
       "created_at": "2026-10-29T12:00:00Z",
       "thumbnail_url": "/api/workspace/projects/my_tectonic_globe/thumbnail",
       "grid_count": 2,
       "hollow": true,
       "radius_mm": 40.0
     }
     ```

4. **`create_or_save_project(slug: str, project: GlobeProject, thumbnail_b64: Optional[str] = None) -> Dict[str, Any]`**:
   - Saves `<working_dir>/projects/<slug>/project.json`.
   - If `thumbnail_b64` is provided (captured from the Three.js canvas on save) or missing, saves/generates `thumbnail.png`.

5. **`copy_workspace_project(source_slug: str, new_name: str) -> Dict[str, Any]`**:
   - Implements **"Open as Copy"** (Goal #2).
   - Creates `<working_dir>/projects/<new_slug>/`, copies `project.json` and `thumbnail.png`, updates `project.id = new_slug` and `project.name = new_name`, and returns the new project payload ready to load in the editor.

6. **`delete_workspace_project(slug: str) -> Dict[str, Any]`**:
   - Removes `<working_dir>/projects/<slug>/` after confirmation.

7. **`list_workspace_datasets() -> List[Dict[str, Any]]`**:
   - Reads `<working_dir>/dataset_registry.json` + merges any newly dropped files in `<working_dir>/datasets/` + online cached datasets in `<working_dir>/.download_cache/`.
   - Ensures each entry has a generated 2D preview thumbnail URL (`/api/workspace/datasets/{dataset_id}/thumbnail`).

8. **`upsert_workspace_dataset(entry: WorkspaceDatasetEntry) -> Dict[str, Any]`**:
   - Updates NetCDF variable names (`lat_var`, `lon_var`, `data_var`), `name`, `cmap_preview`, and `default_ops` (`smooth`, `fill`, `math`, `downsample`, `scale_offset`, `airy_moho`).
   - Re-evaluates the grid pipeline (`_load_base_grid` + `default_ops`), updates `stats` (`vmin`, `vmax`, `shape`, `has_nans`), and regenerates the dataset's preview thumbnail PNG.

9. **`duplicate_workspace_dataset(dataset_id: str, new_name: Optional[str] = None) -> Dict[str, Any]`**:
   - Clones the metadata entry in `dataset_registry.json` with a new unique `id` and `parent_dataset_id = dataset_id`.
   - Points to the **exact same `physical_path`** on disk without copying the file.
   - Generates a separate thumbnail for the duplicate so subsequent changes to its `default_ops` visually distinguish it from its parent.

10. **`render_dataset_thumbnail(entry: WorkspaceDatasetEntry) -> str`**:
    - For `kind == "grid"`: Loads the grid using `entry.netcdf_vars`, executes `entry.default_ops` using `resolve_grid_ops()`, maps with `entry.cmap_preview` (default `'terrain'` or `'viridis'`), and saves a crisp `256x128` PNG to `<working_dir>/datasets/thumbnails/<id>.png`.
    - For `kind == "vector"`: Rasterizes the shapefile via `rasterize_shapefile_to_mask(height=128, width=256)` in emerald on a dark slate ocean background and saves to `<id>.png`.
    - For `kind == "image"`: Resizes the image to `256x128` and saves to `<id>.png`.

### 4.2 New & Updated FastAPI Endpoints (`WebApp/backend/main.py`)
Add the following routes to `WebApp/backend/main.py`:

| Method | Route | Description |
| :--- | :--- | :--- |
| `GET` | `/api/workspace/state` | Returns `working_dir`, `recent_working_dirs`, `projects`, and `datasets`. |
| `POST` | `/api/workspace/working-dir` | Sets the active `working_dir` (or creates it) and returns updated workspace state. |
| `GET` | `/api/workspace/projects` | Lists all projects in `<working_dir>/projects/`. |
| `GET` | `/api/workspace/projects/{slug}` | Loads a saved project's `GlobeProject` JSON. |
| `POST` | `/api/workspace/projects/{slug}` | Saves/updates a project's `project.json` and optional `thumbnail_b64`. |
| `POST` | `/api/workspace/projects/{slug}/copy` | Duplicates a project into a new folder (`Open as Copy`) and returns the new project. |
| `DELETE` | `/api/workspace/projects/{slug}` | Deletes a project folder. |
| `GET` | `/api/workspace/projects/{slug}/thumbnail` | Serves `projects/<slug>/thumbnail.png` (or generates a fallback 2D/3D preview). |
| `GET` | `/api/workspace/datasets` | Lists all shared workspace dataset profiles (physical + virtual duplicates). |
| `POST` | `/api/workspace/datasets` | Creates or updates a `WorkspaceDatasetEntry` (NetCDF vars, `default_ops`, name) & refreshes thumbnail. |
| `POST` | `/api/workspace/datasets/{id}/duplicate` | Creates a zero-copy virtual duplicate with its own `default_ops` pipeline. |
| `DELETE` | `/api/workspace/datasets/{id}` | Removes a virtual dataset profile (or deletes physical file if requested and no other profile references it). |
| `GET` | `/api/workspace/datasets/{id}/thumbnail` | Serves the rendered 256×128 thumbnail showing the dataset with its `default_ops` applied. |
| `GET` | `/api/presets/{preset_id}/thumbnail` | Serves the pre-rendered thumbnail for a gallery preset. |

---

## 5. Pre-Rendered Gallery Thumbnails Pipeline (Goal #5)

### 5.1 Pre-Rendering Script: `WebApp/backend/scripts/generate_gallery_thumbnails.py`
Create a standalone batch script (and automatic fallback on `/api/presets/{preset_id}/thumbnail`) that renders a clean `240x240` 3D orthographic globe snapshot (or `240x160` card preview) for every preset in `WebApp/presets/index.json`:
- Uses `compile_globe_model(project, n_points_override=15000)` + `matplotlib` 3D `Poly3DCollection` or spherical orthographic projection shaded with a directional light source $L = normalize([1, -1, 1])$.
- Saves static thumbnails to `WebApp/presets/thumbnails/<preset_id>.png`.
- Update `WebApp/presets/index.json` so each preset entry includes `"thumbnail": "/api/presets/<preset_id>/thumbnail"`.

---

## 6. Frontend State & Navigation Overhaul (`WebApp/frontend/src/`)

### 6.1 Application Screen State (`useProjectStore.ts`)
Extend `ProjectStoreState` in `WebApp/frontend/src/store/useProjectStore.ts`:

```ts
export type AppScreen = 'landing' | 'editor';

export interface WorkspaceProjectSummary {
  slug: string;
  name: string;
  description: string;
  mode: 'paleo' | 'custom';
  updated_at: string;
  thumbnail_url: string;
  hollow: boolean;
  radius_mm: number;
  grid_count: number;
}

export interface WorkspaceDatasetProfile {
  id: string;
  name: string;
  kind: 'grid' | 'vector' | 'image';
  source_type: 'online' | 'local';
  online_category?: string;
  online_name?: string;
  online_params?: Record<string, any>;
  physical_path: string;
  parent_dataset_id?: string | null;
  netcdf_vars?: { lat_var: string; lon_var: string; data_var: string };
  default_ops: GridTransform[];
  cmap_preview?: string;
  thumbnail_url: string;
  stats?: {
    shape?: number[];
    vmin?: number;
    vmax?: number;
    has_nans?: boolean;
  };
}
```

Add store properties & actions:
- `appScreen: 'landing' | 'editor'` (defaults to `'landing'` on startup!)
- `activeProjectSlug: string | null`
- `workingDir: string`
- `recentWorkingDirs: string[]`
- `workspaceProjects: WorkspaceProjectSummary[]`
- `workspaceDatasets: WorkspaceDatasetProfile[]`
- `isWizardOpen: boolean`
- `isWorkspaceDataManagerOpen: boolean`
- Actions:
  - `setAppScreen(screen: 'landing' | 'editor')`
  - `fetchWorkspaceState()`
  - `setWorkingDirectory(path: string)`
  - `openWorkspaceProject(slug: string, asCopy?: boolean)`
  - `saveCurrentProjectToWorkspace(slug?: string)`
  - `startNewBlankProject()`
  - `startProjectFromWizard(wizardState: WizardConfig)`
  - `duplicateWorkspaceDataset(id: string, newName?: string)`
  - `updateWorkspaceDataset(profile: WorkspaceDatasetProfile)`

---

## 7. Detailed UI Component Specifications

### 7.1 Component 1: Landing Page (`WebApp/frontend/src/components/landing/LandingPage.tsx`)
When `appScreen === 'landing'`, render a modern, dark-themed CAD Launchpad instead of the 3D editor:

1. **Top Workspace Bar**:
   - Displays **Active Working Directory** badge (e.g. `D:\OneDrive\python\3d_globes\workspace`) with a **"Change Working Folder..."** button (opens a directory browser modal using `/api/files/browse`) and a quick dropdown of `recentWorkingDirs`.
   - Shows cache status pill (`14 datasets cached`, `X projects found`).

2. **5 Primary Action Cards / Sections**:
   - **Action Card A — New Project (Guided Wizard)**:
     - Prominent primary card with wand icon. Clicking opens `NewProjectWizardModal`.
   - **Action Card B — New Project (Blank Globe)**:
     - Initializes `BLANK_GLOBE_PROJECT` (40mm hollow sphere, 0 datasets, 0 displacements, neutral slate-white outer / gray inner ConstantColourer) and transitions `appScreen` $\to$ `'editor'`.
   - **Action Card C — Load from Gallery**:
     - Opens the visual `PresetGalleryView` (inline tab or full modal) showing all 27+ examples with their **pre-rendered thumbnails**.
   - **Action Card D — Dataset & Media Manager**:
     - Opens `WorkspaceDataManagerModal` to inspect, configure NetCDF variables, define default declarative operations (`smooth`, `fill`, `math`), and create zero-copy virtual duplicates.
   - **Main Section — Continue a Project (`WorkspaceProjectsGrid`)**:
     - Displays all projects inside `<working_dir>/projects/`.
     - Each project card shows:
       - Pre-rendered thumbnail (`thumbnail.png`)
       - Project Title, Slug, Last Modified timestamp
       - Badges: `Hollow / Solid`, `Radius mm`, `Mode (Modern / Paleo)`, `# Grids`
       - Primary Button: **Open Project**
       - Secondary Button: **Open as Copy** (prompts or auto-increments name, calls `POST /api/workspace/projects/{slug}/copy`, and opens the copy in the editor)
       - Delete icon button with confirmation.

---

### 7.2 Component 2: 5-Step New Project Wizard (`WebApp/frontend/src/components/wizard/NewProjectWizardModal.tsx`)
A clean, linear 5-step modal with a progress stepper at the top and a live summary sidebar on the right:

#### **Step 1: Base Geometry & Globe Mode**
- **Project Name & Folder Slug**: Text input (e.g. `"My Himalayan Relief Globe"`).
- **Globe Mode**:
  - `Modern Geophysical / Planetary Globe` (Default)
  - `Deep-Time Paleogeographic Globe (Scotese 0–540 Ma)` (reveals Age slider `0–540 Ma`)
- **Sphere Structure**:
  - Toggle: `Hollow Shell` (default `true`) vs `Solid Sphere` (`false`)
  - `Outer Reference Radius (mm)`: Slider & input (default `40 mm`, range `15–200 mm`)
  - `Inner Cavity Ratio` (if hollow): Slider (default `0.50`, or explicit wall thickness in `mm`)
  - `Enforce Minimum Wall Thickness Guard`: Checkbox (default `true`, `1.8 mm`)
  - `Mesh Resolution`: Preset buttons for Preview (`60k`) and Final Export (`500k` Standard, `1M` High, `2.5M` Ultra).

#### **Step 2: Datasets Selection**
- Lets the user toggle one or more datasets to include in the project from two tabs:
  - **Workspace & User Datasets** (from `<working_dir>/dataset_registry.json`, including any custom virtual duplicates with pre-configured `smooth`/`fill`/`math` pipelines, each shown with its thumbnail).
  - **Built-in Online Catalog** (Earth ETOPO, Mars MOLA, Moon LOLA, Venus, Mercury, S40RTS Tomography, EGM2008 Geoid, CRUST1.0 Moho, LITHO1.0 LAB, Natural Earth Land/Coastline Shapefiles).
- Option to select "None (Start without datasets)".

#### **Step 3: Radial Displacement Setup**
- **Which surfaces should be displaced?**
  - Radio cards:
    1. `Outer Surface Only` (Default)
    2. `Inner Surface Only` (e.g. inverted Moho / LAB cavity)
    3. `Both Outer and Inner Surfaces` (e.g. Topography on outer + Moho or Tomography on inner)
    4. `No Displacement (Smooth Sphere)`
- For each active surface (Outer / Inner):
  - Select which Dataset (from Step 2) drives the displacement.
  - `Vertical Exaggeration`: Slider (e.g. `40x` default for topography) or Physical Step (`mm` for Polygon/Line shapefiles).
  - `Coastline Step (mm)`: Optional step boost at sea level (default `0.8 mm` or `0.0 mm`).

#### **Step 4: Surface Colouring Setup**
- **Colour Application Mode**:
  - `Outer Surface Only`
  - `Separate Colouring for Outer & Inner Surfaces` (Default when Hollow)
  - `Uniform / Single Filament (Monochrome)`
- **Outer Surface Colour Method**:
  - `Continuous Colormap from Grid` (select Grid + colormap e.g. `terrain`, `viridis`, `roma`, with `vmin`/`vmax`)
  - `Banded 4-Filament Optical Palette` (select 4 spools for AMS/Snapmaker multi-color printing)
  - `Raster Image Texture` (select image or PaleoAtlas)
  - `Vector Polygon Fill` (e.g. Land/Ocean two-tone)
- **Inner Surface Colour Method** (if Separate):
  - `Solid Neutral Filament` (color picker, default `#cbd5e1`)
  - `Grid Colormap` (e.g. `seismic` for inner tomography/Moho)
- **Optional Overlays**:
  - Checkboxes: `Add North/South Pole Labels`, `Highlight Coastlines`.

#### **Step 5: Embedded Magnets & Split Hemispheres**
- **Hemisphere Splitting & Magnets**:
  - Toggle: `Split into Upper & Lower Hemispheres with Embedded Magnets` (Default `true` if Hollow) vs `Single Unsplit Piece`.
- When enabled:
  - `Magnet Count`: Slider (`3` to `12`, default `6`)
  - `Magnet Dimensions (mm)`: Quick presets (`3×2 mm`, `4×2 mm`, `5×2 mm`, `6×3 mm`) + custom `Diameter (mm)` and `Height (mm)` inputs.
  - `Clearance (mm)`: Default `0.15 mm`.
  - `Auto-Optimize Positions Along Equator`: Checkbox (default `true` — places magnets in thickest equatorial ridges).
- **Finish Button ("Create & Open in Studio")**:
  - Compiles the wizard state into a `GlobeProject`, saves it to `<working_dir>/projects/<slug>/project.json`, loads it into `useProjectStore`, fetches grid buffers, and transitions to `appScreen = 'editor'`.

---

### 7.3 Component 3: Blank Project Initializer (Goal #4)
In `WebApp/frontend/src/types/globeProject.ts`, define `BLANK_GLOBE_PROJECT`:
```ts
export const BLANK_GLOBE_PROJECT: GlobeProject = {
  $schema: '../schemas/globe_project.schema.json',
  id: 'blank_globe_project',
  name: 'Untitled Blank Globe',
  category: 'custom',
  description: 'Blank hollow globe with no datasets or displacements.',
  mode: 'custom',
  geometry: {
    method: 'fibonacci',
    n_points: 500000,
    preview_n_points: 60000,
    radius: 40.0,
    center: [0.0, 0.0, 0.0],
    hollow: true,
    inner_ratio: 0.5,
    inner_n_points: null,
    fix_intersection: {
      enabled: true,
      min_thickness: 1.8,
      mode: 'inner',
    },
  },
  grids: {},
  outer_displacements: [],
  inner_displacements: [],
  colourers: [
    {
      id: 'col_outer_base',
      enabled: true,
      target: 'outer',
      selection: 'all',
      type: 'ConstantColourer',
      color: '#e2e8f0',
    },
    {
      id: 'col_inner_base',
      enabled: true,
      target: 'inner',
      selection: 'all',
      type: 'ConstantColourer',
      color: '#64748b',
    },
  ],
  magnets: {
    enabled: false,
    count: 6,
    diameter: 4.0,
    height: 2.0,
    clearance: 0.15,
    wall_thickness: 1.2,
    under_thickness: 0.8,
    optimize_positions: true,
    min_spacing_deg: 25.0,
    strategy: 'even',
  },
  export: {
    format: '3mf',
    split_hemispheres: false,
    filename_prefix: 'blank_globe',
  },
};
```

---

### 7.4 Component 4: Gallery Browser with Pre-Rendered Thumbnails (Goal #5)
Update `WebApp/frontend/src/components/panels/PresetBrowserModal.tsx`:
- Add a `48x48` or `80x80` rounded thumbnail image on the left of every preset card (`<img src={`/api/presets/${item.id}/thumbnail`} />`).
- Include a fallback SVG globe icon while loading.
- Allow opening any gallery preset either:
  - **"Open in Studio"** (creates a new working copy in `<working_dir>/projects/` or loads into editor)
  - **"Save Copy to Workspace"**

---

### 7.5 Component 5: Workspace Dataset & Media Manager (Goal #6)
Create `WebApp/frontend/src/components/datasets/WorkspaceDataManagerModal.tsx` (accessible both from the Landing Page and the top header bar inside the Studio Editor):

- **Left Pane — Dataset Cards List**:
  - Filter tabs: `All`, `Grids (.nc/.tif)`, `Vectors (.shp/.geojson)`, `Images (.png/.jpg)`, `Online Cache`.
  - `+ Import File to Working Dir` button (uploads to `<working_dir>/datasets/...` and registers in `dataset_registry.json`).
  - Each card displays:
    - **256×128 Preview Thumbnail** (reflecting its active declarative operations!)
    - Dataset Name & ID badge
    - Physical file path (with a `"Virtual Duplicate"` badge if `parent_dataset_id != null` showing it shares disk storage with its parent)
    - Dimensions & Value range (`vmin .. vmax`)
    - Action buttons: **Configure**, **Duplicate (Zero-Copy)**, **Add to Active Project**, **Delete**.

- **Right Pane — Dataset Inspector & Default Declarative Operations Editor**:
  - When a dataset is selected:
    1. **Profile Name & ID**: Editable name (e.g. `"ETOPO 30m — 3° Smoothed"`).
    2. **Underlying File Path (Read-Only / Shared)**: Shows exact path on disk and how many virtual profiles share this file.
    3. **NetCDF Coordinate & Variable Mapping** (for `.nc` / `.grd`):
       - Auto-inspected dropdowns for `lat_var`, `lon_var`, and `data_var` (allows selecting specific variables in multi-variable NetCDF files like `LITHO1.0.nc` or `S40RTS_dvs.nc`).
    4. **Default Declarative Operations Stack**:
       - Full interactive operation builder (`smooth`, `fill`, `math`, `downsample`, `scale_offset`, `airy_moho`).
       - Reorder (Move Up / Move Down), Add, Remove.
    5. **Live Preview & Stats Refresh**:
       - Clicking **"Apply & Render Preview"** runs the declarative pipeline on the backend, updates the 2D equirectangular thumbnail and `vmin`/`vmax` histogram, and saves to `dataset_registry.json`.

---

### 7.6 Studio Header Bar Updates (`WebApp/frontend/src/App.tsx`)
In the Studio Editor (`appScreen === 'editor'`):
- Add a **"← Home / Projects"** button on the far left of the header bar to return to `LandingPage`.
- Add a **"Save Project"** button (saves `project.json` + captures a canvas thumbnail to `<working_dir>/projects/<slug>/`).
- Display the current `workingDir` and `activeProjectSlug` in a subtle breadcrumb under the project title.

---

## 8. Step-by-Step Execution Sequence for Implementing Agent

An agent implementing this plan should execute in the following 8 phases:

### Phase 0: Scotese Paleo Catalog `"0 Ma"` Bugfix
1. In `src/globe3d/datasets.py` (`PaleoNamespace._load_metadata()`), set both `r["age_ma"] = float(r["age_ma"])` and `r["age"] = float(r["age_ma"])`.
2. In `WebApp/frontend/src/components/panels/SimplePaleoPanel.tsx`, update the `/api/paleo/catalog` mapper to `const age = Number(m.age_ma ?? m.age ?? 0);` and use unique composite keys `key={`${s.age}_${s.name}`}` on `<option>` elements.

### Phase 1: Backend Workspace & Dataset Registry Service
1. Create `WebApp/backend/workspace_service.py` implementing working directory selection, `.studio_config.json` persistence, `projects/` scanning, project copy (`Open as Copy`), and `dataset_registry.json` management with zero-copy duplication.
2. Update `src/globe3d/datasets.py` `_get_cache_dir()` to respect an environment variable or module-level override `GLOBE3D_CACHE_DIR` set by `workspace_service.set_working_directory()`.
3. Add dataset thumbnail generation (`render_dataset_thumbnail`) using `_load_base_grid` + `resolve_grid_ops`.
4. Register all `/api/workspace/*` endpoints in `WebApp/backend/main.py`.

### Phase 2: Gallery Thumbnail Pre-Renderer
1. Create `WebApp/backend/scripts/generate_gallery_thumbnails.py` and generate `WebApp/presets/thumbnails/<preset_id>.png` for all 27 presets.
2. Add `GET /api/presets/{preset_id}/thumbnail` in `WebApp/backend/main.py`.

### Phase 3: Frontend Store & Blank Project Template
1. Add `BLANK_GLOBE_PROJECT` to `WebApp/frontend/src/types/globeProject.ts`.
2. Extend `useProjectStore.ts` with `appScreen`, `workingDir`, `workspaceProjects`, `workspaceDatasets`, and workspace CRUD actions.

### Phase 4: Landing Page & Working Directory Picker
1. Create `WebApp/frontend/src/components/landing/LandingPage.tsx` with the Working Directory selector bar, the 5 main launch actions, and the **Continue a Project** grid (with **Open** and **Open as Copy**).
2. Wire `App.tsx` to render `LandingPage` when `appScreen === 'landing'` and the Studio Editor when `appScreen === 'editor'`, with a **Home / Projects** navigation button and **Save Project** action in the header.

### Phase 5: 5-Step New Project Wizard & Gallery Thumbnails
1. Create `WebApp/frontend/src/components/wizard/NewProjectWizardModal.tsx` implementing the 5 steps (`Base Geometry`, `Datasets`, `Displacement`, `Colour`, `Magnets`).
2. Update `PresetBrowserModal.tsx` to display the pre-rendered thumbnails for every gallery example.

### Phase 6: Shared Dataset Manager with Zero-Copy Duplication
1. Create `WebApp/frontend/src/components/datasets/WorkspaceDataManagerModal.tsx` with thumbnail cards, NetCDF variable selectors (`lat_var`, `lon_var`, `data_var`), default declarative operation chains (`smooth`, `fill`, `math`, etc.), and zero-copy dataset duplication.
2. Update `GridSourcesPanel.tsx` so users can one-click insert any configured Workspace Dataset Profile (inheriting its NetCDF vars and default declarative ops) into the active project.

### Phase 7: Automated Verification
1. Add unit tests in `WebApp/backend/tests/test_backend.py` testing:
   - Working directory switching & project listing
   - Project saving and **Open as Copy**
   - Dataset registration, NetCDF variable override, default declarative ops evaluation, and zero-copy virtual dataset duplication
   - Gallery thumbnail serving
2. Run `pytest WebApp/backend/tests/test_backend.py` (in `conda activate pygmt`) and `npm run build` in `WebApp/frontend`.
