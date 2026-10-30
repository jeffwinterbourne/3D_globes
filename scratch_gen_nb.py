"""Script to generate working/paleo_globes_workflow.ipynb."""
import json
from pathlib import Path
from globe3d import datasets

# Fetch all maps to construct commented-out entries
maps = datasets.paleo.list_scotese_maps()

# Define the active subset ages
ACTIVE_KEYS = {
    "modern_0ma": 0.0,
    "miocene_20ma": 20.0,
    "kpg_66ma": 66.0,
    "mid_cretaceous_90ma": 90.0,
    "jurassic_150ma": 150.0,
    "triassic_jurassic_200ma": 200.0,
    "permo_triassic_250ma": 250.0,
    "carboniferous_300ma": 300.0,
    "devonian_carboniferous_360ma": 360.0,
    "silurian_420ma": 420.0,
    "ordovician_silurian_440ma": 440.0,
    "ordovician_480ma": 480.0,
    "cambrian_540ma": 540.0,
}

print(f"Loaded {len(maps)} maps from Scotese catalog.")
