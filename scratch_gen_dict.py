"""Generates working/paleo_globes_workflow.ipynb."""
import json
import re
from pathlib import Path
from globe3d import datasets

maps = datasets.paleo.list_scotese_maps()

active_ages = {0.0, 20.0, 66.0, 90.0, 150.0, 200.0, 250.0, 300.0, 360.0, 420.0, 440.0, 480.0, 540.0}

# Sort maps by age_ma ascending
sorted_maps = sorted(maps, key=lambda m: (m["age_ma"], m["map_id"]))

# Build the PALEO_GLOBES dictionary code string
lines_dict = []
lines_dict.append("PALEO_GLOBES = {")
lines_dict.append("    # =========================================================================")
lines_dict.append("    # ACTIVE SUBSET: KEY GEOLOGICAL EPOCHS & EXTINCTION BOUNDARIES")
lines_dict.append("    # =========================================================================")

active_keys_added = set()

for m in sorted_maps:
    age = m["age_ma"]
    if age in active_ages and age not in active_keys_added:
        active_keys_added.add(age)
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", m["name"].strip().lower()).strip("_")
        key = f"paleo_{int(age):03d}ma_{slug}"
        out_name = f"paleo_{int(age):03d}ma_{slug}_globe.3mf"
        label_text = f"{int(age) if age.is_integer() else age} Ma"
        label_lat = 30.0 if age == 250.0 else (25.0 if age == 200.0 else 20.0)
        label_lon = -140.0
        
        lines_dict.append(f'    "{key}": {{')
        lines_dict.append(f'        "age_ma": {age},')
        lines_dict.append(f'        "map_id": {m["map_id"]},')
        lines_dict.append(f'        "name": "{m["name"]}",')
        lines_dict.append(f'        "label_text": "{label_text}",')
        lines_dict.append(f'        "label_lat": {label_lat},')
        lines_dict.append(f'        "label_lon": {label_lon},')
        lines_dict.append(f'        "label_height_deg": 6.0,')
        lines_dict.append(f'        "label_color": "white",')
        lines_dict.append(f'        "output_filename": "{out_name}",')
        lines_dict.append("    },")

lines_dict.append("")
lines_dict.append("    # =========================================================================")
lines_dict.append("    # ADDITIONAL GEOLOGICAL TIME SLICES (COMMENTED OUT BY DEFAULT)")
lines_dict.append("    # Uncomment any entry below to include it in the batch generation.")
lines_dict.append("    # =========================================================================")

# Group commented entries by Era
current_era = None
seen_commented = set()

for m in sorted_maps:
    age = m["age_ma"]
    map_id = m["map_id"]
    map_key = (age, map_id)
    if age in active_keys_added and map_key not in seen_commented:
        # Check if this exact map was already active
        active_map_ids = [am["map_id"] for am in sorted_maps if am["age_ma"] == age]
        if map_id == active_map_ids[0]:
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
    out_name = f"paleo_{int(age):03d}ma_map{map_id:02d}_globe.3mf"
    label_text = f"{int(age) if age.is_integer() else age} Ma"
    label_lat = 20.0
    label_lon = -140.0

    lines_dict.append(f'    # "{key}": {{')
    lines_dict.append(f'    #     "age_ma": {age},')
    lines_dict.append(f'    #     "map_id": {map_id},')
    lines_dict.append(f'    #     "name": "{m["name"]}",')
    lines_dict.append(f'    #     "label_text": "{label_text}",')
    lines_dict.append(f'    #     "label_lat": {label_lat},')
    lines_dict.append(f'    #     "label_lon": {label_lon},')
    lines_dict.append(f'    #     "label_height_deg": 6.0,')
    lines_dict.append(f'    #     "label_color": "white",')
    lines_dict.append(f'    #     "output_filename": "{out_name}",')
    lines_dict.append("    # },")

lines_dict.append("}")
pal_globes_code = "\n".join(lines_dict)

print(f"Active globes: {len(active_keys_added)}")
print("PALEO_GLOBES code block generated successfully.")
