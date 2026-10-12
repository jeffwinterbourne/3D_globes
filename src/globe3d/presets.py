"""Preset configurations, default elevation bands, and physical filament spool libraries.

Keeping presets in this module decouples calculation logic from hardcoded domain data,
enabling easy customization, additions, and external configuration loading.
"""

from typing import Dict, List, Tuple, Union

# Standard physical filament libraries
FILAMENT_PRESETS: Dict[str, List[Dict[str, Union[str, Tuple[int, int, int], float]]]] = {
    "TERRAIN_4": [
        {"name": "Brown", "color": (142, 68, 28), "td": 0.8},
        {"name": "Dark Blue", "color": (18, 52, 120), "td": 1.0},
        {"name": "White", "color": (250, 250, 250), "td": 1.5},
        {"name": "Dark Green", "color": (32, 95, 42), "td": 0.9},
    ],
    "CMYKW": [
        {"name": "Cyan", "color": (0, 255, 255), "td": 1.0},
        {"name": "Magenta", "color": (255, 0, 255), "td": 1.0},
        {"name": "Yellow", "color": (255, 255, 0), "td": 1.0},
        {"name": "Black", "color": (20, 20, 20), "td": 0.5},
        {"name": "White", "color": (250, 250, 250), "td": 1.5},
    ],
    "RBYKW": [
        {"name": "Red", "color": (255, 0, 0), "td": 1.0},
        {"name": "Blue", "color": (0, 0, 255), "td": 1.0},
        {"name": "Yellow", "color": (255, 255, 0), "td": 1.0},
        {"name": "Black", "color": (20, 20, 20), "td": 0.5},
        {"name": "White", "color": (250, 250, 250), "td": 1.5},
    ],
    "EARTH_TERRAIN": [
        {"name": "Deep Ocean Blue", "color": (24, 66, 104), "td": 1.0},
        {"name": "Shelf Cyan", "color": (110, 190, 205), "td": 1.2},
        {"name": "Lowland Green", "color": (45, 95, 50), "td": 0.9},
        {"name": "Highland Ochre", "color": (175, 120, 60), "td": 0.8},
        {"name": "Peak Snow White", "color": (250, 250, 250), "td": 1.5},
    ],
}
FILAMENT_PRESETS["EARTH_4"] = FILAMENT_PRESETS["TERRAIN_4"]
FILAMENT_PRESETS["TERRAIN"] = FILAMENT_PRESETS["TERRAIN_4"]
FILAMENT_PRESETS["EARTH"] = FILAMENT_PRESETS["TERRAIN_4"]

# Default internal elevation boundaries in meters for standard banded colormaps
DEFAULT_ELEVATION_BOUNDARIES: Dict[str, List[float]] = {
    "TERRAIN_4": [-2500.0, -200.0, 0.0, 300.0, 600.0, 1000.0, 1500.0],
    "CMYKW": [-4000.0, -2000.0, -200.0, 0.0, 500.0, 1500.0, 3000.0],
}

# Default 8-band hypsometric configuration for InteractiveColormapBuilder and paleo models
DEFAULT_ELEVATION_BANDS: List[Dict[str, Union[int, float, str, None]]] = [
    {"index": 1,  "threshold": -2500, "name": "Abyssal"},
    {"index": 13, "threshold": -200,  "name": "Deep sea"},
    {"index": 16, "threshold": 0,     "name": "Continental Shelf"},
    {"index": 3,  "threshold": 300,   "name": "Lowlands"},
    {"index": 32, "threshold": 600,   "name": "High ground"},
    {"index": 29, "threshold": 1000,  "name": "Low mountains"},
    {"index": 5,  "threshold": 1500,  "name": "High mountains"},
    {"index": 2,  "threshold": None,  "name": "Very high"},
]
