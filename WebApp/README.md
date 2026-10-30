# Globe3D Studio WebApp

**Globe3D Studio** is a full-featured graphical 3D CAD and scientific visualization web application for the `globe3d` Python library. It enables interactive design, deep-time paleogeographic reconstruction (`0–540 Ma`), optical 4-filament color mixing, equatorial magnet optimization, and watertight `.3mf` / `.obj` / `.stl` export for multi-color 3D printing.

---

## Quick Start

### 1. One-Command PowerShell Launcher (Windows)

From PowerShell, run:

```powershell
cd d:\OneDrive\python\3d_globes\git\3D_globes\WebApp
.\start_webapp.ps1
```

The launcher script automatically:
1. Activates the `pygmt` Conda environment (`conda activate pygmt`).
2. Starts the FastAPI backend (`WebApp.backend.main:app`) on `http://127.0.0.1:8000`.
3. Installs frontend dependencies (`npm install`) if needed and launches Vite on `http://localhost:5173`.
4. Opens `http://localhost:5173` in your browser.

---

### 2. Manual Startup (Two Terminals)

#### Terminal 1 — Python FastAPI Backend (`conda activate pygmt`)
```powershell
conda activate pygmt
cd d:\OneDrive\python\3d_globes\git\3D_globes
pip install -r WebApp/backend/requirements.txt
uvicorn WebApp.backend.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Terminal 2 — React + Three.js Frontend
```powershell
cd d:\OneDrive\python\3d_globes\git\3D_globes\WebApp\frontend
npm install
npm run dev
```

Open **`http://localhost:5173`** in your browser. Interactive Swagger API docs are available at **`http://127.0.0.1:8000/docs`**.

---

## Architecture & Hybrid 60fps / Definitive Python Pipeline

```text
WebApp/
├── README.md                       # Documentation & developer guide
├── start_webapp.ps1                # One-command launcher script
├── schemas/
│   └── globe_project.schema.json   # Formal JSON Schema for GlobeProject validation
├── presets/                        # 27 built-in JSON presets (Examples & Paper Recreations)
│   ├── index.json
│   ├── examples/
│   └── paper_recreations/
├── backend/                        # FastAPI server running in `conda activate pygmt`
│   ├── main.py                     # REST API endpoints & static asset serving
│   ├── models.py                   # Pydantic models for GlobeProject
│   ├── engine.py                   # Compiles GlobeProject -> authoritative GlobeModel
│   ├── preview_service.py          # Binary WebGL buffers, grid buffers, 2D map & colorbar
│   ├── magnet_service.py           # 360° equatorial wall profile & zero-boss optimizer
│   ├── filament_service.py         # Kubelka-Munk 35-swatch optical palette & CIE ΔE matcher
│   ├── dataset_service.py          # Online dataset catalog, Zenodo Scotese fetcher & file browser
│   └── codegen.py                  # Converts any GlobeProject into clean .py and .ipynb code
└── frontend/                       # Vite + React 18 + TypeScript + Three.js + TailwindCSS
    ├── src/
    │   ├── types/globeProject.ts   # Complete TypeScript interfaces
    │   ├── store/useProjectStore.ts# Zustand store with Undo/Redo & two-way JSON sync
    │   ├── workers/meshPreviewWorker.ts # 60fps client-side mesh & colour evaluator
    │   ├── components/viewport/    # Three.js GlobeCanvas, Exploded View, 3D Magnet Ring
    │   └── components/panels/      # All 11 Studio Builder Panels & Modals
```

### Two-Tier Rendering Engine
1. **Tier 1 — Instant 60fps Client-Side WebGL Preview**:
   - Evaluates radial displacement (`GridDisplacer`, `vert_exagg`, `coastline_step`, `reference_level`, `ConstantDisplacer`, `PointDisplacer`, `LineDisplacer`, `PolygonDisplacer`), hollow inner cavity (`inner_ratio`, `fix_intersection`), and colormaps (`terrain`, `viridis`, `RdBu_r`, `plasma`, `magma`, `coolwarm`, or 4-filament discrete bands) in real time in the browser.
   - Supports live **Exploded Hemispheres**, **Upper/Lower Only**, **Outer/Inner Shell**, **Cross-Section Clipping Plane**, **Wireframe**, and **3D Equatorial Magnet Ring** inspection.
2. **Tier 2 — Definitive Python `GlobeModel` Engine**:
   - Clicking **"Render Exact High-Res Python Mesh in Viewport"** runs `POST /api/preview/eval` on the Python backend and streams the exact `globe3d` `Float32Array` / `Uint32Array` mesh buffers directly into Three.js.
   - Clicking **"Render & Export Final Python Globe"** runs `POST /api/export/render` to generate watertight `.3mf` (OrcaSlicer / Snapmaker U1 Full-Spectrum multi-color), `.obj` (with vertex RGB), or `.stl` files in `outputs/`.

---

## Key Studio Features

- **Preset Gallery (27 Presets)**: Load all standard example notebooks (`example_1` to `example_6`, `tomo_globe_3d`, `demo_magnets`, `demo_split_globe_image`) and paper recreations (`Airy Isostasy Moho`, `Geoid Composite`, `PREM Earth Interior 3-Shell Set`, `Seismic Matryoshka 3-Shell Set`, `Planetary Topography Earth/Mars/Moon`, and `Game of Globes 20mm Marble`).
- **Simple Paleo Mode (`0–540 Ma`)**: Interactive geological timeline slider with Cenozoic/Mesozoic/Paleozoic badges, all 88 Scotese PALEOMAP time slices, plate tectonic model selector (`Scotese_PALEOMAP`, `Seton2012`, `Muller2016`, `Merdith2021`), live plate reconstruction of modern cities (`/api/paleo/reconstruct-points`), N/S polar caps, and one-click **"Convert to Custom Recipe Stack"**.
- **4-Filament Optical Mixing & Banded Colormap Studio**: Interactive 35-swatch (`[00]`–`[34]`) Kubelka-Munk optical transmission distance (`td`) mixer, CIE $\Delta E$ color matcher, interactive elevation band editor, and 2D equirectangular map + colorbar preview.
- **Equatorial Magnet Studio**: Interactive $360^\circ$ `[d_min, d_max]` wall profile SVG chart, clearance margin table, zero-boss peak optimizer (`/api/magnets/optimize`), and one-click physical calibration test piece generator (`magnet_test_piece.stl`).
- **Live Two-Way JSON & Python Code Generator**: Edit any GUI slider and watch the Monaco JSON editor and generated `.py` / `.ipynb` code update live—or paste/edit JSON in Monaco to immediately update the 3D globe.
