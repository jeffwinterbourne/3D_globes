"""Service for Full-Spectrum Optical Filament Mixing palette generation and CIE Delta-E matching."""

from typing import Any, Dict, List
from globe3d.filaments import (
    color_to_hex,
    create_filament_palette,
    delta_e_lab,
    match_filament_color,
    parse_color,
)
from globe3d.presets import FILAMENT_PRESETS
from .models import FilamentsConfigModel


def get_spools_from_config(cfg: FilamentsConfigModel) -> List[Dict[str, Any]]:
    """Extracts normalized physical spool dictionaries from a FilamentsConfigModel.

    Args:
        cfg (FilamentsConfigModel): Filament configuration model.

    Returns:
        list[dict]: Normalized spool dicts with 'name', 'color', 'hex', and 'td'.
    """
    preset_name = (cfg.preset or "custom").upper()
    if preset_name in FILAMENT_PRESETS and preset_name != "CUSTOM":
        raw_spools = FILAMENT_PRESETS[preset_name]
        spools = []
        for s in raw_spools:
            rgb = parse_color(s)
            spools.append({
                "name": s.get("name", "Spool"),
                "color": rgb,
                "hex": color_to_hex(rgb),
                "td": float(s.get("td", 1.0)),
            })
        return spools

    spools = []
    for idx, s in enumerate(cfg.spools):
        rgb = parse_color(s.hex_color)
        spools.append({
            "name": s.name or f"Spool {idx + 1}",
            "color": rgb,
            "hex": color_to_hex(rgb),
            "td": float(s.td),
        })
    if not spools:
        for s in FILAMENT_PRESETS["TERRAIN_4"]:
            rgb = parse_color(s)
            spools.append({
                "name": s["name"],
                "color": rgb,
                "hex": color_to_hex(rgb),
                "td": float(s["td"]),
            })
    return spools


def generate_palette_response(cfg: FilamentsConfigModel) -> Dict[str, Any]:
    """Generates the optical mixing palette with bracketed codes [00]..[NN] and layer stack details.

    Args:
        cfg (FilamentsConfigModel): Filament configuration model.

    Returns:
        dict: Palette response with 'spools' and 'entries'.
    """
    spools = get_spools_from_config(cfg)
    spool_color_by_name = {s["name"]: s["hex"] for s in spools}
    raw_palette = create_filament_palette(spools=spools, total_layers=max(1, min(cfg.top_layers, 6)))

    entries = []
    for idx, item in enumerate(raw_palette):
        code = f"[{idx:02d}]"
        layer_names = [r.get("spool", "Spool") for r in item.get("recipe", [])]
        layer_colors = [spool_color_by_name.get(ln, item["hex"]) for ln in layer_names]
        entries.append({
            "index": idx,
            "code": code,
            "name": item.get("name", f"Mix {idx}"),
            "layers_label": item.get("layers", ""),
            "hex": item["hex"],
            "rgb": list(item["color"]),
            "layers": layer_names,
            "layer_colors": layer_colors,
            "recipe": item.get("recipe", []),
        })

    return {
        "preset": cfg.preset,
        "spools": spools,
        "entries": entries,
    }


def match_target_color_response(target_hex: str, cfg: FilamentsConfigModel) -> Dict[str, Any]:
    """Finds the best matching optical filament recipe and top 5 matches using CIE Delta-E.

    Args:
        target_hex (str): Target color in hex or RGB string format.
        cfg (FilamentsConfigModel): Filament configuration model.

    Returns:
        dict: Best match, delta_e, and top 5 ranked matches.
    """
    palette_data = generate_palette_response(cfg)
    entries = palette_data["entries"]
    tgt_rgb = parse_color(target_hex)

    scored = []
    for entry in entries:
        dist = delta_e_lab(tgt_rgb, entry["rgb"])
        item_copy = dict(entry)
        item_copy["delta_e"] = round(float(dist), 2)
        scored.append(item_copy)

    scored.sort(key=lambda x: x["delta_e"])
    best = scored[0] if scored else None
    return {
        "target_hex": color_to_hex(tgt_rgb),
        "target_rgb": list(tgt_rgb),
        "best_match": best,
        "delta_e": best["delta_e"] if best else None,
        "top_5": scored[:5],
    }
