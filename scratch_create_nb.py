"""Build working/paleo_globes_workflow.ipynb with full structure."""
import json
import re
from pathlib import Path
from globe3d import datasets

# 1. Fetch catalog maps
maps = datasets.paleo.list_scotese_maps()
sorted_maps = sorted(maps, key=lambda m: (m["age_ma"], m["map_id"]))

# Active ages subset
active_ages = [0.0, 20.0, 66.0, 90.0, 150.0, 200.0, 250.0, 300.0, 360.0, 420.0, 440.0, 480.0, 540.0]

# Build PALEO_GLOBES dictionary code
lines_dict = []
lines_dict.append("PALEO_GLOBES = {")
lines_dict.append("    # =========================================================================")
lines_dict.append("    # ACTIVE SUBSET: KEY GEOLOGICAL EPOCHS & EXTINCTION BOUNDARIES")
lines_dict.append("    # =========================================================================")

active_keys_added = set()

# Map custom descriptions / labels for active subset
active_info = {
    0.0: {
        "slug": "holocene_modern",
        "name": "Modern (Holocene)",
        "label_text": "0 Ma",
        "label_lat": 20.0,
        "label_lon": -140.0,
        "desc": "Present-day Earth topography, ocean basins, and continental margins.",
    },
    20.0: {
        "slug": "early_miocene",
        "name": "Early Miocene",
        "label_text": "20 Ma",
        "label_lat": 20.0,
        "label_lon": -140.0,
        "desc": "Establishment of Antarctic circumpolar currents; Himalayan and Alpine orogenies.",
    },
    66.0: {
        "slug": "k_pg_boundary",
        "name": "K-Pg Boundary (KT Extinction)",
        "label_text": "66 Ma",
        "label_lat": 20.0,
        "label_lon": -140.0,
        "desc": "Chicxulub asteroid impact & end-Cretaceous extinction of non-avian dinosaurs.",
    },
    90.0: {
        "slug": "mid_cretaceous",
        "name": "Mid-Cretaceous Supergreenhouse",
        "label_text": "90 Ma",
        "label_lat": 20.0,
        "label_lon": -140.0,
        "desc": "Peak global sea levels, Western Interior Seaway, and ice-free poles.",
    },
    150.0: {
        "slug": "late_jurassic",
        "name": "Late Jurassic",
        "label_text": "150 Ma",
        "label_lat": 20.0,
        "label_lon": -140.0,
        "desc": "Breakup of Pangaea; early opening of the Central Atlantic Ocean.",
    },
    200.0: {
        "slug": "triassic_jurassic_boundary",
        "name": "Triassic-Jurassic Boundary",
        "label_text": "200 Ma",
        "label_lat": 25.0,
        "label_lon": -140.0,
        "desc": "End-Triassic mass extinction and Central Atlantic Magmatic Province (CAMP) rifting.",
    },
    250.0: {
        "slug": "permo_triassic_boundary",
        "name": "Permo-Triassic Boundary (Pangaea)",
        "label_text": "250 Ma",
        "label_lat": 30.0,
        "label_lon": -140.0,
        "desc": "Supercontinent Pangaea surrounded by Panthalassa; Great Dying mass extinction.",
    },
    300.0: {
        "slug": "late_pennsylvanian",
        "name": "Late Pennsylvanian (Carboniferous)",
        "label_text": "300 Ma",
        "label_lat": 20.0,
        "label_lon": -140.0,
        "desc": "Extensive equatorial coal swamps, high atmospheric O2, and South Pole glaciation.",
    },
    360.0: {
        "slug": "devono_carboniferous_boundary",
        "name": "Devono-Carboniferous Boundary",
        "label_text": "360 Ma",
        "label_lat": 20.0,
        "label_lon": -140.0,
        "desc": "Hangenberg extinction; early terrestrial vertebrate expansion and forest ecosystems.",
    },
    420.0: {
        "slug": "late_silurian",
        "name": "Late Silurian",
        "label_text": "420 Ma",
        "label_lat": 20.0,
        "label_lon": -140.0,
        "desc": "Caledonian orogeny; emergence of vascular land plants and coral-stromatoporoid reefs.",
    },
    440.0: {
        "slug": "early_silurian_post_ordovician",
        "name": "Early Silurian (Post-Ordovician Extinction)",
        "label_text": "440 Ma",
        "label_lat": 20.0,
        "label_lon": -140.0,
        "desc": "Hirnantian glaciation recovery and Ordovician-Silurian mass extinction aftermath.",
    },
    480.0: {
        "slug": "early_ordovician",
        "name": "Early Ordovician",
        "label_text": "480 Ma",
        "label_lat": 20.0,
        "label_lon": -140.0,
        "desc": "Great Ordovician Biodiversification Event (GOBE); widespread shallow epeiric seas.",
    },
    540.0: {
        "slug": "cambrian_precambrian_boundary",
        "name": "Cambrian-Precambrian Boundary",
        "label_text": "540 Ma",
        "label_lat": 20.0,
        "label_lon": -140.0,
        "desc": "Cambrian Explosion of multicellular animal phyla and mineralized skeletal body plans.",
    },
}

for age in active_ages:
    matches = [m for m in sorted_maps if abs(m["age_ma"] - age) < 1e-3]
    if not matches:
        continue
    m = matches[0]
    info = active_info.get(age, {})
    slug = info.get("slug", re.sub(r"[^a-zA-Z0-9]+", "_", m["name"].lower()).strip("_"))
    key = f"paleo_{int(age):03d}ma_{slug}"
    out_name = f"paleo_{int(age):03d}ma_{slug}_globe.3mf"
    active_keys_added.add(age)

    lines_dict.append(f'    "{key}": {{')
    lines_dict.append(f'        "age_ma": {age},')
    lines_dict.append(f'        "map_id": {m["map_id"]},')
    lines_dict.append(f'        "name": "{info.get("name", m["name"])}",')
    lines_dict.append(f'        "label_text": "{info.get("label_text", f"{int(age)} Ma")}",')
    lines_dict.append(f'        "label_lat": {info.get("label_lat", 20.0)},')
    lines_dict.append(f'        "label_lon": {info.get("label_lon", -140.0)},')
    lines_dict.append(f'        "label_height_deg": 6.0,')
    lines_dict.append(f'        "label_color": "white",')
    lines_dict.append(f'        "label_angle": 0.0,')
    lines_dict.append(f'        "description": "{info.get("desc", m["name"])}",')
    lines_dict.append(f'        "output_filename": "{out_name}",')
    lines_dict.append("    },")

lines_dict.append("")
lines_dict.append("    # =========================================================================")
lines_dict.append("    # ADDITIONAL GEOLOGICAL TIME SLICES (COMMENTED OUT BY DEFAULT)")
lines_dict.append("    # Uncomment any entry below to include it in the batch generation.")
lines_dict.append("    # =========================================================================")

current_era = None
seen_commented = set()

for m in sorted_maps:
    age = m["age_ma"]
    map_id = m["map_id"]
    
    # Skip if this is the active map for this age
    if age in active_keys_added:
        active_match = [am for am in sorted_maps if abs(am["age_ma"] - age) < 1e-3][0]
        if map_id == active_match["map_id"]:
            continue

    # Determine Era
    if age < 66.0:
        era = "CENOZOIC ERA (0 — 66 Ma)"
    elif age < 251.9:
        era = "MESOZOIC ERA (66 — 252 Ma)"
    else:
        era = "PALEOZOIC ERA (252 — 540 Ma)"

    if era != current_era:
        current_era = era
        lines_dict.append(f"    # --- {era} ---")

    slug = re.sub(r"[^a-zA-Z0-9]+", "_", m["name"].strip().lower()).strip("_")
    key = f"paleo_{int(age):03d}ma_map{map_id:02d}_{slug}"
    out_name = f"paleo_{int(age):03d}ma_map{map_id:02d}_{slug}_globe.3mf"
    label_text = f"{int(age) if age.is_integer() else age} Ma"

    lines_dict.append(f'    # "{key}": {{')
    lines_dict.append(f'    #     "age_ma": {age},')
    lines_dict.append(f'    #     "map_id": {map_id},')
    lines_dict.append(f'    #     "name": "{m["name"]}",')
    lines_dict.append(f'    #     "label_text": "{label_text}",')
    lines_dict.append(f'    #     "label_lat": 20.0,')
    lines_dict.append(f'    #     "label_lon": -140.0,')
    lines_dict.append(f'    #     "label_height_deg": 6.0,')
    lines_dict.append(f'    #     "label_color": "white",')
    lines_dict.append(f'    #     "label_angle": 0.0,')
    lines_dict.append(f'    #     "description": "{m["name"]}",')
    lines_dict.append(f'    #     "output_filename": "{out_name}",')
    lines_dict.append("    # },")

lines_dict.append("}")
pal_globes_code = "\n".join(lines_dict)

# Build Notebook Cells
cells = []

# Cell 0: Header Markdown
cells.append({
    "cell_type": "markdown",
    "metadata": {},
    "source": [
        "# 🌍 Deep-Time Paleo-Globes Batch Workflow\n",
        "### Standardized Multi-Globe Generation Across Geological Time (0 – 540 Ma)\n",
        "\n",
        "This workflow notebook automates the creation of a complete, physical set of 3D printable paleo-globes across deep geological time (0 to 540 Ma), following the modeling standards, optical filament mixing, and vertex colouring architecture demonstrated in [`example_6_paleo_globe.ipynb`](../examples/example_6_paleo_globe.ipynb).\n",
        "\n",
        "---\n",
        "\n",
        "### 📐 Standardized Plotting Scale & Configuration:\n",
        "To ensure every globe can be directly compared when printed and displayed side-by-side:\n",
        "1. **Geometric Standardization**: All globes share the exact same physical radius (40.0 mm / 80 mm diameter), mesh point count (500k vertices), hollow shell ratio (0.9, giving a 4.0 mm wall thickness), and vertical exaggeration (35× with 1000 m coastline step enhancement).\n",
        "2. **Optical Multi-Filament Hypsometric Colormap**: All globes share the exact same 4 physical AMS base spools (Brown, Dark Blue, White, Dark Green) and identical discrete elevation thresholds (Abyssal, Deep sea, Shelf, Lowlands, High ground, Low mountains, High mountains, Alpine), ensuring hypsometric heights mean the exact same color across 540 million years of continental drift.\n",
        "3. **Cartographic Standard**: North ('N') and South ('S') polar glyphs via spherical tangent-plane projection (`PoleLabelColourer`), custom age text labels (`TextColourer`) positioned in open ocean basins, and optional plate-reconstructed modern landmarks (`SymbolColourer` via `PlateModel`).\n",
        "4. **Unified Configuration Cell**: The single cell below defines all global settings and the `PALEO_GLOBES` dictionary. An active subset of key geological times (including Modern / 0 Ma, K-Pg, Pangaea, Cambrian, etc.) is enabled by default, while all other ~95 Scotese PALEOMAP time slices are catalogued and commented out for easy selective activation.\n",
        "5. **Output Destination**: All exported 3MF packages (with embedded OrcaSlicer multi-material project recipes, flat equatorial split surfaces, and virtual filament palettes) are saved into a dedicated subfolder of the output directory: `outputs/paleo_globes/`."
    ]
})

# Cell 1: Environment & Imports
cells.append({
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [
        "%load_ext autoreload\n",
        "%autoreload 2\n",
        "\n",
        "import os\n",
        "import sys\n",
        "import time\n",
        "from pathlib import Path\n",
        "import numpy as np\n",
        "import matplotlib.pyplot as plt\n",
        "from PIL import Image\n",
        "\n",
        "import globe3d\n",
        "from globe3d import (\n",
        "    GlobeModel,\n",
        "    GeographicGrid,\n",
        "    GridDisplacer,\n",
        "    GridColourer,\n",
        "    ImageColourer,\n",
        "    SymbolColourer,\n",
        "    PoleLabelColourer,\n",
        "    TextColourer,\n",
        "    PlateModel,\n",
        "    datasets,\n",
        "    calculate_displacement_scale,\n",
        "    create_filament_palette,\n",
        "    create_banded_colormap,\n",
        "    apply_banded_colormap,\n",
        "    plot_filament_palette,\n",
        "    plot_banded_colormap_preview,\n",
        "    InteractiveColormapBuilder,\n",
        "    write_3mf,\n",
        ")\n",
        "\n",
        "print(f\"globe3d version: {getattr(globe3d, '__version__', '0.1.0')}\")"
    ]
})

# Cell 2: SINGLE CONFIGURATION CELL (Global Settings + PALEO_GLOBES Dictionary)
config_source = f"""# =============================================================================
# GLOBAL SETTINGS (APPLIED UNIFORMLY TO ALL GLOBES)
# =============================================================================
GLOBAL_SETTINGS = {{
    # --- Globe Geometry & Mesh Resolution ---
    "model_radius_mm": 40.0,            # Outer reference radius (80.0 mm / 3.15 inch outer diameter)
    "n_points": 500_000,                # Outer shell vertex count (500k vertices provides crisp detail & fast batch generation)
    "hollow": True,                     # Hollow inner shell for material minimization & magnet joint cavity
    "inner_ratio": 0.9,                 # Inner radius ratio (36.0 mm inner radius = 4.0 mm solid wall thickness)
    
    # --- Topographic Displacement Scale & Standardization ---
    "vertical_exaggeration": 35.0,      # Vertical exaggeration factor (consistent across all globes)
    "coastline_step": 1000.0,           # Coastline step height enhancement in meters (accentuates shallow shelf edges)
    "grid_units": "m",                  # Real-world grid units ('m' for meters)
    
    # --- Polar Markers & Typography ---
    "add_pole_labels": True,            # Add North ('N') and South ('S') polar glyphs
    "pole_label_radius_deg": 6.0,       # Size of polar glyphs in degrees
    "pole_label_color": "white",        # Color of polar glyphs
    
    # --- Deep-Time Landmark Tracking ---
    "track_landmarks": True,            # Reconstruct modern cities backwards through continental drift via PlateModel
    "landmarks": [
        {{"name": "Oxford, UK",     "modern_lat": 51.7519, "modern_lon": -1.2578,  "symbol": "star",  "color": "white", "radius_degrees": 2.5}},
        {{"name": "Baltimore, USA", "modern_lat": 39.2904, "modern_lon": -76.6122, "symbol": "cross", "color": "white", "radius_degrees": 2.5}},
    ],
    
    # --- Base Filament Spools (4 AMS Slots) ---
    "base_filaments": [
        {{"name": "Brown",      "color": [90, 50, 30],    "td": 1.0}},
        {{"name": "Dark Blue",  "color": [20, 40, 95],    "td": 1.0}},
        {{"name": "White",      "color": [245, 245, 245], "td": 2.0}},
        {{"name": "Dark Green", "color": [30, 85, 45],    "td": 1.0}},
    ],
    
    # --- Discrete Hypsometric Elevation Bands (Applied Uniformly) ---
    "elevation_bands": [
        {{"index": 1,  "threshold": -2500, "name": "Abyssal"}},
        {{"index": 13, "threshold": -500,  "name": "Deep sea"}},
        {{"index": 16, "threshold": 0,     "name": "Continental Shelf"}},
        {{"index": 3,  "threshold": 300,   "name": "Lowlands"}},
        {{"index": 19, "threshold": 600,   "name": "High ground"}},
        {{"index": 9,  "threshold": 1000,  "name": "Low mountains"}},
        {{"index": 5,  "threshold": 1500,  "name": "High mountains"}},
        {{"index": 2,  "threshold": None,  "name": "Very high"}},
    ],
    
    # --- Export & Output Directory ---
    "output_subfolder": "paleo_globes", # Dedicated subfolder within output/
    "export_format": "3mf",             # Single-file multi-material 3MF package containing both hemispheres
    "boolean_engine": "manifold",       # Mesh boolean engine for equatorial hemisphere splitting
}}

# =============================================================================
# DICTIONARY OF ALL GLOBES TO CREATE
# Active subset contains the primary geological times; the remaining are commented out.
# =============================================================================
{pal_globes_code}

# Compute displacement scale factor applying to all models
scale_factor = calculate_displacement_scale(
    GLOBAL_SETTINGS["model_radius_mm"],
    vertical_exagg=GLOBAL_SETTINGS["vertical_exaggeration"],
    grid_units=GLOBAL_SETTINGS["grid_units"],
)

print("=" * 80)
print("CONFIGURATION SUMMARY (APPLIED TO ALL GLOBES)")
print("=" * 80)
print(f"  * Model Outer Radius:       {{GLOBAL_SETTINGS['model_radius_mm']}} mm ({{GLOBAL_SETTINGS['model_radius_mm'] * 2}} mm diameter)")
print(f"  * Inner Shell Radius:       {{GLOBAL_SETTINGS['model_radius_mm'] * GLOBAL_SETTINGS['inner_ratio']}} mm (Wall: {{GLOBAL_SETTINGS['model_radius_mm'] * (1 - GLOBAL_SETTINGS['inner_ratio']):.1f}} mm)")
print(f"  * Mesh Points per Shell:    {{GLOBAL_SETTINGS['n_points']:,}} vertices")
print(f"  * Vertical Exaggeration:    {{GLOBAL_SETTINGS['vertical_exaggeration']}}x")
print(f"  * Standard Scale Factor:    {{scale_factor:.6e}} mm/m")
print(f"  * Coastline Step Height:    {{GLOBAL_SETTINGS['coastline_step']}} m")
print(f"  * Output Destination:       outputs/{{GLOBAL_SETTINGS['output_subfolder']}}/")
print(f"  * Active Globes in Batch:   {{len(PALEO_GLOBES)}}")
print("-" * 80)
for k, g in PALEO_GLOBES.items():
    print(f"    [{{k}}] {{g['age_ma']:>5.1f}} Ma | {{g['name']:<42}} | Label: {{g['label_text']}} @ ({{g['label_lat']}} deg, {{g['label_lon']}} deg)")
print("=" * 80)
"""

cells.append({
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [line + "\n" for line in config_source.split("\n")]
})

# Cell 3: Markdown for Palette & Colormap
cells.append({
    "cell_type": "markdown",
    "metadata": {},
    "source": [
        "## 1. Optical Filament Palette & Discrete Hypsometric Colormap\n",
        "\n",
        "Using the 4 base physical filament spools loaded into the AMS, `globe3d.filaments` computes a Kubelka-Munk optical polynomial model predicting perceived optical mixing across micro-layers.\n",
        "The cell below compiles all 35 available mixtures and builds the standardized discrete banded colormap (`cmap`, `norm`) used uniformly across all globes."
    ]
})

# Cell 4: Code for Palette & Colormap Preview
cells.append({
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [
        "# 1. Generate full-spectrum discrete optical mixing palette\n",
        "palette_4 = create_filament_palette(\n",
        "    GLOBAL_SETTINGS[\"base_filaments\"],\n",
        "    ratios=[0.25, 0.5, 0.75],\n",
        "    include_tints=False,\n",
        ")\n",
        "\n",
        "# 2. Extract colors and thresholds for discrete elevation colormap\n",
        "selected_colors = [palette_4[b[\"index\"]][\"color\"] for b in GLOBAL_SETTINGS[\"elevation_bands\"]]\n",
        "thresholds = [b[\"threshold\"] for b in GLOBAL_SETTINGS[\"elevation_bands\"] if b[\"threshold\"] is not None]\n",
        "band_names = [b[\"name\"] for b in GLOBAL_SETTINGS[\"elevation_bands\"]]\n",
        "\n",
        "# 3. Create banded colormap and boundary norm\n",
        "cmap, norm = create_banded_colormap(selected_colors, thresholds)\n",
        "\n",
        "# 4. Plot swatch palette and discrete colorbar preview\n",
        "fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 5), gridspec_kw={\"height_ratios\": [2.5, 1]})\n",
        "plot_filament_palette(palette_4, title=\"4-Filament Optical Palette (Index Labeled for Selection)\", max_swatches=len(palette_4), ax=ax1)\n",
        "plot_banded_colormap_preview(cmap, norm, thresholds, band_labels=band_names, title=\"Standard Discrete Elevation Bands\", ax=ax2)\n",
        "plt.tight_layout()\n",
        "plt.show()"
    ]
})

# Cell 5: Markdown for Plate Model
cells.append({
    "cell_type": "markdown",
    "metadata": {},
    "source": [
        "## 2. Plate Tectonic Reconstruction Model\n",
        "\n",
        "To provide spatial continuity across geological epochs, `datasets.paleo.scotese_plate_model()` integrates GPlately / PyGPlates with the Scotese PALEOMAP plate tectonic model.\n",
        "This allows modern landmark coordinates (e.g. Oxford, UK and Baltimore, USA) to be tracked backwards through continental drift to each globe's specific geological epoch."
    ]
})

# Cell 6: Code for Plate Model
cells.append({
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [
        "pm = None\n",
        "if GLOBAL_SETTINGS[\"track_landmarks\"]:\n",
        "    try:\n",
        "        pm = datasets.paleo.scotese_plate_model()\n",
        "        print(\"Successfully loaded Scotese PALEOMAP Global Plate Model.\")\n",
        "        print(\"\\nSample Landmark Drift Tracking (Oxford, UK):\")\n",
        "        oxford_modern = [51.7519, -1.2578]\n",
        "        for age in [0.0, 66.0, 150.0, 250.0, 420.0, 540.0]:\n",
        "            pt = pm.reconstruct_points(oxford_modern, age_ma=age)[0]\n",
        "            print(f\"  {age:>5.1f} Ma: lat={pt[0]:>6.2f}°, lon={pt[1]:>7.2f}°\")\n",
        "    except Exception as e:\n",
        "        print(f\"Note: PlateModel unavailable ({e}). Continuing with landmark tracking disabled.\")\n",
        "        pm = None"
    ]
})

# Cell 7: Markdown for Standardized Globe Builder Function
cells.append({
    "cell_type": "markdown",
    "metadata": {},
    "source": [
        "## 3. Standardized Globe Builder Function\n",
        "\n",
        "The function below implements the standardized assembly pipeline for any single globe:\n",
        "1. Loads the Scotese PaleoDEM elevation grid and metadata.\n",
        "2. Calculates the exact displacement scale factor.\n",
        "3. Generates base hollowed spherical mesh.\n",
        "4. Applies topographic displacement with coastline step enhancement.\n",
        "5. Applies discrete hypsometric coloring directly onto vertices.\n",
        "6. Adds undistorted polar glyphs ('N' and 'S').\n",
        "7. Adds custom age text label at the specified ocean coordinates.\n",
        "8. Reconstructs and colors modern landmark coordinates in deep time."
    ]
})

# Cell 8: Code for Standardized Globe Builder Function
cells.append({
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [
        "def build_paleo_globe(globe_key, config, global_settings, plate_model, colormap, boundary_norm, palette):\n",
        "    \"\"\"Builds a standardized GlobeModel for a single geological time slice.\n",
        "    \n",
        "    Args:\n",
        "        globe_key (str): Unique dictionary key.\n",
        "        config (dict): Globe configuration dictionary (age_ma, label_text, coords, etc.).\n",
        "        global_settings (dict): Shared global settings dictionary.\n",
        "        plate_model (PlateModel or None): Plate tectonic model for coordinate tracking.\n",
        "        colormap (Colormap): Banded matplotlib colormap.\n",
        "        boundary_norm (Normalize): Boundary norm for elevation thresholds.\n",
        "        palette (list[dict]): Virtual filament optical mixing palette.\n",
        "        \n",
        "    Returns:\n",
        "        tuple[GlobeModel, dict]: (constructed_model, metadata_dict)\n",
        "    \"\"\"\n",
        "    age_ma = config[\"age_ma\"]\n",
        "    t_start = time.time()\n",
        "    \n",
        "    # 1. Fetch PaleoDEM elevation grid\n",
        "    dem_grid, texture_path, meta = datasets.paleo.scotese(age_ma)\n",
        "    actual_age = meta.get(\"age_ma\", age_ma)\n",
        "    \n",
        "    # 2. Instantiate base hollowed sphere\n",
        "    model = GlobeModel(\n",
        "        method=\"fibonacci\",\n",
        "        n_points=global_settings[\"n_points\"],\n",
        "        radius=global_settings[\"model_radius_mm\"],\n",
        "        hollow=global_settings[\"hollow\"],\n",
        "        inner_ratio=global_settings[\"inner_ratio\"],\n",
        "    )\n",
        "    \n",
        "    # 3. Apply uniform topographic displacement scale\n",
        "    scale = calculate_displacement_scale(\n",
        "        global_settings[\"model_radius_mm\"],\n",
        "        vertical_exagg=global_settings[\"vertical_exaggeration\"],\n",
        "        grid_units=global_settings[\"grid_units\"],\n",
        "    )\n",
        "    model.outer.displace(\n",
        "        GridDisplacer(dem_grid, coastline_step=global_settings[\"coastline_step\"]),\n",
        "        scale=scale,\n",
        "    )\n",
        "    \n",
        "    # 4. Apply discrete hypsometric vertex colouring\n",
        "    model.colour(GridColourer(dem_grid, colormap=colormap, norm=boundary_norm))\n",
        "    \n",
        "    # 5. Add polar markers ('N' and 'S')\n",
        "    if global_settings.get(\"add_pole_labels\", True):\n",
        "        model.outer.colour(\n",
        "            PoleLabelColourer(\n",
        "                radius_degrees=global_settings.get(\"pole_label_radius_deg\", 6.0),\n",
        "                north_color=global_settings.get(\"pole_label_color\", \"white\"),\n",
        "                south_color=global_settings.get(\"pole_label_color\", \"white\"),\n",
        "            )\n",
        "        )\n",
        "    \n",
        "    # 6. Add customized age text label\n",
        "    if config.get(\"label_text\"):\n",
        "        model.outer.colour(\n",
        "            TextColourer(\n",
        "                text=config[\"label_text\"],\n",
        "                lat=config.get(\"label_lat\", 20.0),\n",
        "                lon=config.get(\"label_lon\", -140.0),\n",
        "                height_degrees=config.get(\"label_height_deg\", 6.0),\n",
        "                color=config.get(\"label_color\", \"white\"),\n",
        "                angle=config.get(\"label_angle\", 0.0),\n",
        "                reference=\"paleo\",\n",
        "                font_weight=\"bold\",\n",
        "            )\n",
        "        )\n",
        "        \n",
        "    # 7. Add plate-reconstructed modern landmarks\n",
        "    if global_settings.get(\"track_landmarks\", False) and plate_model is not None:\n",
        "        for lm in global_settings.get(\"landmarks\", []):\n",
        "            try:\n",
        "                model.outer.colour(\n",
        "                    SymbolColourer(\n",
        "                        symbol=lm.get(\"symbol\", \"star\"),\n",
        "                        lat=lm[\"modern_lat\"],\n",
        "                        lon=lm[\"modern_lon\"],\n",
        "                        reference=\"modern\",\n",
        "                        age=actual_age,\n",
        "                        plate_model=plate_model,\n",
        "                        color=lm.get(\"color\", \"white\"),\n",
        "                        radius_degrees=lm.get(\"radius_degrees\", 2.5),\n",
        "                    )\n",
        "                )\n",
        "            except Exception as ex:\n",
        "                print(f\"  [Warning] Could not reconstruct landmark {lm.get('name')}: {ex}\")\n",
        "                \n",
        "    elapsed = time.time() - t_start\n",
        "    meta[\"build_time_s\"] = elapsed\n",
        "    return model, meta\n",
        "\n",
        "print(\"Standardized globe builder function compiled successfully.\")"
    ]
})

# Cell 9: Markdown for Batch Generation & 3MF Export
cells.append({
    "cell_type": "markdown",
    "metadata": {},
    "source": [
        "## 4. Batch Generation & Multi-Color 3MF Export\n",
        "\n",
        "The cell below executes the batch workflow:\n",
        "1. Locates or creates the dedicated output subfolder `outputs/paleo_globes/` (or `output/paleo_globes/`).\n",
        "2. Iterates over each active item in `PALEO_GLOBES`.\n",
        "3. Builds the standardized model using `build_paleo_globe`.\n",
        "4. Slices the model into Northern and Southern hemispheres with flat equatorial mating planes.\n",
        "5. Exports a single-file 3MF package containing both hemispheres positioned side-by-side on the print bed with full OrcaSlicer multi-material project recipes.\n",
        "6. Caches the generated models in `generated_models` for interactive in-notebook 3D WebGL inspection."
    ]
})

# Cell 10: Code for Batch Execution Loop
cells.append({
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [
        "# Determine output subfolder relative to workspace root\n",
        "repo_root = Path.cwd().parent if Path.cwd().name == \"working\" else Path.cwd()\n",
        "output_base = repo_root / \"outputs\" if (repo_root / \"outputs\").exists() else (repo_root / \"output\" if (repo_root / \"output\").exists() else repo_root / \"outputs\")\n",
        "output_dir = output_base / GLOBAL_SETTINGS[\"output_subfolder\"]\n",
        "output_dir.mkdir(parents=True, exist_ok=True)\n",
        "\n",
        "print(f\"Target Output Subfolder: {output_dir.resolve()}\")\n",
        "print(f\"Total Active Globes to Generate: {len(PALEO_GLOBES)}\\n\")\n",
        "\n",
        "generated_models = {}\n",
        "batch_start = time.time()\n",
        "\n",
        "for idx, (key, cfg) in enumerate(PALEO_GLOBES.items(), 1):\n",
        "    print(f\"[{idx}/{len(PALEO_GLOBES)}] Generating {cfg['name']} ({cfg['age_ma']} Ma)...\")\n",
        "    \n",
        "    # 1. Build standardized model\n",
        "    model, meta = build_paleo_globe(\n",
        "        key,\n",
        "        cfg,\n",
        "        GLOBAL_SETTINGS,\n",
        "        pm,\n",
        "        cmap,\n",
        "        norm,\n",
        "        palette_4,\n",
        "    )\n",
        "    generated_models[key] = model\n",
        "    \n",
        "    # 2. Export hemispheres packaged into single 3MF file\n",
        "    out_path = output_dir / cfg[\"output_filename\"]\n",
        "    t_exp = time.time()\n",
        "    model.export_hemispheres(\n",
        "        top_filename=str(out_path),\n",
        "        bottom_filename=None,  # Single-file packaging with both Northern & Southern hemispheres\n",
        "        base_filaments=GLOBAL_SETTINGS[\"base_filaments\"],\n",
        "        palette=palette_4,\n",
        "        engine=GLOBAL_SETTINGS[\"boolean_engine\"],\n",
        "    )\n",
        "    exp_time = time.time() - t_exp\n",
        "    file_size_mb = out_path.stat().st_size / (1024 * 1024)\n",
        "    \n",
        "    print(f\"    -> Built in {meta['build_time_s']:.2f}s | Exported 3MF in {exp_time:.2f}s | Size: {file_size_mb:.2f} MB\")\n",
        "    print(f\"    -> Saved: {out_path.name}\\n\")\n",
        "\n",
        "total_elapsed = time.time() - batch_start\n",
        "print(\"=\" * 80)\n",
        "print(f\"BATCH WORKFLOW COMPLETE!\")\n",
        "print(f\"Successfully generated and exported {len(generated_models)} standardized paleo-globes in {total_elapsed:.1f}s ({total_elapsed/60:.2f} min).\")\n",
        "print(f\"All output files are saved in: {output_dir.resolve()}\")\n",
        "print(\"=\" * 80)"
    ]
})

# Cell 11: Markdown for Interactive 3D WebGL Inspection
cells.append({
    "cell_type": "markdown",
    "metadata": {},
    "source": [
        "## 5. Interactive 3D WebGL Inspection\n",
        "\n",
        "You can inspect any of the generated globes directly inside the notebook using `model.preview()`.\n",
        "This interactive WebGL viewer supports orbiting, panning, zooming, and inspecting both whole globes and split hemispheres (e.g. `part='upper'` to verify wall thickness, equatorial mating surfaces, and internal hollowing)."
    ]
})

# Cell 12: Code for Interactive Preview
cells.append({
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [
        "# Select which globe to preview:\n",
        "preview_key = \"paleo_000ma_holocene_modern\" if \"paleo_000ma_holocene_modern\" in generated_models else list(PALEO_GLOBES.keys())[0]\n",
        "\n",
        "if preview_key in generated_models:\n",
        "    print(f\"Launching interactive 3D WebGL preview of: {PALEO_GLOBES[preview_key]['name']} ({PALEO_GLOBES[preview_key]['age_ma']} Ma)\")\n",
        "    generated_models[preview_key].preview()\n",
        "else:\n",
        "    print(f\"Globe '{preview_key}' not found in generated_models. Please run the batch generation cell above.\")"
    ]
})

# Cell 13: Code for Hemisphere Preview
cells.append({
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [
        "# Preview Northern hemisphere showing flat equatorial mating plane & hollowed inner cavity\n",
        "if preview_key in generated_models:\n",
        "    print(f\"Previewing Northern hemisphere for: {PALEO_GLOBES[preview_key]['name']}\")\n",
        "    generated_models[preview_key].preview(part=\"upper\")"
    ]
})

# Cell 14: Markdown for 3D Printing Recommendations
cells.append({
    "cell_type": "markdown",
    "metadata": {},
    "source": [
        "## 6. Slicing & 3D Printing Guidelines for Multi-Material Printers (OrcaSlicer / Bambu Studio)\n",
        "\n",
        "### 🖨️ Printer & Slicer Setup:\n",
        "1. **Importing the 3MF Files**:\n",
        "   - Open **OrcaSlicer** (or Bambu Studio) and load any exported `.3mf` file from `outputs/paleo_globes/`.\n",
        "   - When prompted, select **\"Open as Project\"** so all physical base spools, virtual mixed filament recipes, and object color associations are automatically restored.\n",
        "2. **Physical Filament Spools (AMS Slots 1–4)**:\n",
        "   - **Slot 1**: Brown PLA (`#5a321e`, td = 1.0 mm)\n",
        "   - **Slot 2**: Dark Blue PLA (`#14285f`, td = 1.0 mm)\n",
        "   - **Slot 3**: White PLA (`#f5f5f5`, td = 2.0 mm)\n",
        "   - **Slot 4**: Dark Green PLA (`#1e552d`, td = 1.0 mm)\n",
        "3. **Print Settings**:\n",
        "   - **Layer Height**: 0.08 mm or 0.12 mm for maximum optical mixing resolution across alternating micro-layers.\n",
        "   - **Orientation**: Both hemispheres are pre-oriented flat on their equatorial mating planes on the print bed for optimal bed adhesion without supports.\n",
        "   - **Infill**: 15% Gyroid infill within the 4 mm hollow shell walls.\n",
        "   - **Brim**: 5 mm outer brim recommended for edge adhesion."
    ]
})

nb = {
    "cells": cells,
    "metadata": {
        "language_info": {
            "name": "python",
            "version": "3.10.6"
        },
        "kernelspec": {
            "display_name": "Python (pygmt)",
            "language": "python",
            "name": "pygmt"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

target_path = Path("working/paleo_globes_workflow.ipynb")
target_path.parent.mkdir(parents=True, exist_ok=True)
with open(target_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

print(f"Successfully wrote {target_path} ({target_path.stat().st_size:,} bytes) with {len(cells)} cells.")
