"""Filament mixing, optical layer blending, and banded colormaps for multi-material 3D printing.

This module provides physics-based color prediction and palette generation for 3D printer
filaments, emulating full-spectrum optical layer blending (such as Full Spectrum 3D /
OrcaSlicer-FullSpectrum / Prusa ColorMix) using an empirical Kubelka-Munk polynomial model.
It also provides tools to construct discrete banded colormaps for hypsometric and geological
terrain models.
"""

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from .image import render_2d_array_as_rgb

# Module-level cache for polynomial regression weights
_POLY_DATA = None


def _load_poly_weights() -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Loads and caches polynomial regression weights for pairwise filament mixing.

    Returns:
        tuple: (powers, coefficients, intercept) arrays.
    """
    global _POLY_DATA
    if _POLY_DATA is None:
        asset_path = Path(__file__).parent / "assets" / "filament_poly_weights.npz"
        if not asset_path.exists():
            raise FileNotFoundError(
                f"Filament polynomial weights file not found at {asset_path}. "
                "Ensure package assets are installed correctly."
            )
        data = np.load(asset_path)
        _POLY_DATA = (data["powers"], data["coefficients"], data["intercept"])
    return _POLY_DATA


def parse_color(color: Union[str, Sequence[Union[int, float]], Dict]) -> Tuple[int, int, int]:
    """Parses a color representation into an RGB integer tuple (0-255).

    Supports hex strings ('#RRGGBB', 'RRGGBB'), RGB/RGBA sequences (integers 0-255
    or floats 0.0-1.0), and filament dictionary records.

    Args:
        color (str, sequence, or dict): Input color representation.

    Returns:
        tuple: (R, G, B) integer tuple in the range [0, 255].

    Raises:
        ValueError: If color format is invalid or cannot be parsed.
    """
    if isinstance(color, dict):
        if "color" in color:
            return parse_color(color["color"])
        if "rgb" in color:
            return parse_color(color["rgb"])
        if "hex" in color:
            return parse_color(color["hex"])
        raise ValueError(f"Cannot extract color from dictionary keys: {list(color.keys())}")

    if isinstance(color, str):
        hex_str = color.lstrip("#").strip()
        if len(hex_str) == 3:
            hex_str = "".join(c * 2 for c in hex_str)
        if len(hex_str) == 6:
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            return (r, g, b)
        if len(hex_str) == 8:
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            return (r, g, b)
        raise ValueError(f"Invalid hex color string: '{color}'")

    if isinstance(color, (list, tuple, np.ndarray)):
        if len(color) < 3:
            raise ValueError(f"Color sequence must have at least 3 components, got {len(color)}")
        vals = color[:3]
        if all(isinstance(v, (float, np.floating)) and 0.0 <= v <= 1.0 for v in vals):
            return tuple(int(np.clip(round(v * 255.0), 0, 255)) for v in vals)
        return tuple(int(np.clip(round(v), 0, 255)) for v in vals)

    raise ValueError(f"Unsupported color type: {type(color)}")


def color_to_hex(color: Union[str, Sequence[Union[int, float]], Dict]) -> str:
    """Converts a color into a lowercase 6-digit hex string (#rrggbb).

    Args:
        color: Input color representation.

    Returns:
        str: Hexadecimal color string starting with '#'.
    """
    r, g, b = parse_color(color)
    return f"#{r:02x}{g:02x}{b:02x}"


def rgb_to_lab(rgb: Union[str, Sequence[Union[int, float]], Dict]) -> Tuple[float, float, float]:
    """Converts an sRGB color (0-255) to CIE L*a*b* color space under D65 illuminant.

    Args:
        rgb: Input RGB color.

    Returns:
        tuple: (L, a, b) values in CIE LAB color space.
    """
    r, g, b = parse_color(rgb)

    # Convert sRGB to linear RGB
    def _srgb_to_linear(c_byte: int) -> float:
        c = c_byte / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r_lin = _srgb_to_linear(r)
    g_lin = _srgb_to_linear(g)
    b_lin = _srgb_to_linear(b)

    # Linear RGB to XYZ (D65 white point: Xn=0.95047, Yn=1.00000, Zn=1.08883)
    x = (r_lin * 0.4124564 + g_lin * 0.3575761 + b_lin * 0.1804375) / 0.95047
    y = (r_lin * 0.2126729 + g_lin * 0.7151522 + b_lin * 0.0721750) / 1.00000
    z = (r_lin * 0.0193339 + g_lin * 0.1191920 + b_lin * 0.9503041) / 1.08883

    def _f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0

    fx = _f(x)
    fy = _f(y)
    fz = _f(z)

    l_val = 116.0 * fy - 16.0
    a_val = 500.0 * (fx - fy)
    b_val = 200.0 * (fy - fz)
    return (l_val, a_val, b_val)


def delta_e_lab(
    color1: Union[str, Sequence[Union[int, float]], Dict],
    color2: Union[str, Sequence[Union[int, float]], Dict],
) -> float:
    """Calculates the CIE Delta-E (1976) perceptual color distance between two colors.

    Args:
        color1: First color.
        color2: Second color.

    Returns:
        float: Euclidean distance in CIE LAB space. Values < 2.0 are barely perceptible
            to human vision.
    """
    l1, a1, b1 = rgb_to_lab(color1)
    l2, a2, b2 = rgb_to_lab(color2)
    return float(np.sqrt((l1 - l2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2))


def mix_filament_pair(
    color1: Union[str, Sequence[Union[int, float]], Dict],
    color2: Union[str, Sequence[Union[int, float]], Dict],
    ratio: float = 0.5,
) -> Tuple[int, int, int]:
    """Blends two filament colors using Full-Spectrum optical layer mixing.

    Uses a degree-4 Kubelka-Munk polynomial model (identical to Full Spectrum 3D
    and PolyMixer) predicting the perceived color when alternating thin layers of
    semi-translucent filaments are printed. This preserves chromatic vibrancy (e.g.
    mixing blue + yellow yields bright green instead of muddy gray).

    Args:
        color1: First base filament color (ratio = 0.0).
        color2: Second base filament color (ratio = 1.0).
        ratio (float, optional): Mixing ratio t in [0.0, 1.0], where 0.0 is 100% color1
            and 1.0 is 100% color2. Defaults to 0.5.

    Returns:
        tuple: (R, G, B) integer tuple of the mixed perceived color (0-255).
    """
    c1 = parse_color(color1)
    c2 = parse_color(color2)

    if ratio <= 0.0:
        return c1
    if ratio >= 1.0:
        return c2

    # Check for near-identical colors to avoid polynomial evaluation
    if c1 == c2:
        return c1

    # Check for neutral grayscale mixing
    if abs(c1[0] - c1[1]) <= 1 and abs(c1[1] - c1[2]) <= 1 and abs(c2[0] - c2[1]) <= 1 and abs(c2[1] - c2[2]) <= 1:
        # Linear lightness interpolation for neutrals
        gray = int(np.clip(round((1.0 - ratio) * c1[0] + ratio * c2[0]), 0, 255))
        return (gray, gray, gray)

    powers, coef, intercept = _load_poly_weights()

    x = np.array([c1[0], c1[1], c1[2], c2[0], c2[1], c2[2], float(ratio)], dtype=np.float64)

    # Compute features: product(x_j ** powers_ij)
    feats = np.ones(len(powers), dtype=np.float64)
    for j in range(7):
        col_val = x[j]
        p_col = powers[:, j]
        for exp in (1, 2, 3, 4):
            mask = p_col == exp
            if np.any(mask):
                feats[mask] *= col_val ** exp

    rgb = feats @ coef + intercept
    rgb_clipped = np.clip(np.trunc(rgb), 0, 255).astype(int)
    return (int(rgb_clipped[0]), int(rgb_clipped[1]), int(rgb_clipped[2]))


def mix_filament_pairs_vectorized(
    colors1: np.ndarray,
    colors2: np.ndarray,
    ratios: np.ndarray,
) -> np.ndarray:
    """Vectorized pairwise filament mixing for large batches of color transitions.

    Args:
        colors1 (np.ndarray): (N, 3) array of RGB colors (0-255).
        colors2 (np.ndarray): (N, 3) array of RGB colors (0-255).
        ratios (np.ndarray): (N,) array of mixing ratios in [0.0, 1.0].

    Returns:
        np.ndarray: (N, 3) array of mixed RGB colors with dtype uint8.
    """
    c1 = np.asarray(colors1, dtype=np.float64)
    c2 = np.asarray(colors2, dtype=np.float64)
    t = np.asarray(ratios, dtype=np.float64).reshape(-1, 1)

    n = len(t)
    if c1.shape != (n, 3) or c2.shape != (n, 3):
        raise ValueError("colors1, colors2 and ratios must have matching leading dimension N.")

    powers, coef, intercept = _load_poly_weights()

    x = np.hstack([c1, c2, t])  # (N, 7)

    feats = np.ones((n, len(powers)), dtype=np.float64)
    for j in range(7):
        col = x[:, j:j + 1]
        p_col = powers[:, j]
        for exp in (1, 2, 3, 4):
            mask = p_col == exp
            if np.any(mask):
                feats[:, mask] *= col ** exp

    rgb = feats @ coef + intercept
    rgb_clipped = np.clip(np.trunc(rgb), 0, 255).astype(np.uint8)

    # Enforce exact endpoint constraints
    mask_0 = ratios <= 0.0
    mask_1 = ratios >= 1.0
    if np.any(mask_0):
        rgb_clipped[mask_0] = np.clip(c1[mask_0], 0, 255).astype(np.uint8)
    if np.any(mask_1):
        rgb_clipped[mask_1] = np.clip(c2[mask_1], 0, 255).astype(np.uint8)

    return rgb_clipped


def mix_filaments(
    filaments: Sequence[Union[str, Sequence[Union[int, float]], Dict]],
    weights: Optional[Sequence[float]] = None,
    transmission_distances: Optional[Sequence[float]] = None,
) -> Tuple[int, int, int]:
    """Mixes N filament colors together according to specified weights and transmission properties.

    Emulates multi-filament optical layer blending as per Full Spectrum 3D online:
    - If transmission distances are supplied (or specified as 'td' in filament dicts),
      filament weights are normalized by transmission distance (td): w_i' = w_i / td_i.
    - Achromatic/grayscale blends use energy-conserving linear lightness blending.
    - Chromatic mixtures sequentially fold pairs through the Kubelka-Munk polynomial model.

    Args:
        filaments: Sequence of 1 or more filament color representations (hex, RGB, dict).
        weights (sequence of float, optional): Relative proportion/layer count for each
            filament. If None, equal proportions are used. Defaults to None.
        transmission_distances (sequence of float, optional): Transmission distance (td in mm)
            for each filament. Lower values represent higher opacity. If None, td=1.0 is used.
            Defaults to None.

    Returns:
        tuple: (R, G, B) integer tuple of the resulting mixed color (0-255).
    """
    if not filaments:
        raise ValueError("filaments sequence must contain at least one filament.")

    colors = [parse_color(f) for f in filaments]
    n = len(colors)

    if n == 1:
        return colors[0]

    # Extract weights
    if weights is None:
        w_list = [1.0] * n
    else:
        if len(weights) != n:
            raise ValueError(f"Length of weights ({len(weights)}) must match filaments ({n}).")
        w_list = [float(w) for w in weights]

    # Extract transmission distances
    td_list = []
    if transmission_distances is not None:
        if len(transmission_distances) != n:
            raise ValueError(
                f"Length of transmission_distances ({len(transmission_distances)}) must match filaments ({n})."
            )
        td_list = [max(float(td), 1e-4) for td in transmission_distances]
    else:
        for f in filaments:
            td = 1.0
            if isinstance(f, dict) and "td" in f and f["td"] is not None:
                td = max(float(f["td"]), 1e-4)
            td_list.append(td)

    # Scale weights by transmission distance: effective_w = w / td
    eff_weights = [w / td for w, td in zip(w_list, td_list)]
    total_w = sum(eff_weights)
    if total_w <= 1e-7:
        return colors[0]

    # Check if all colors are neutral grayscale
    all_neutral = all(abs(c[0] - c[1]) <= 2 and abs(c[1] - c[2]) <= 2 for c in colors)
    if all_neutral:
        avg_l = sum(c[0] * w for c, w in zip(colors, eff_weights)) / total_w
        gray = int(np.clip(round(avg_l), 0, 255))
        return (gray, gray, gray)

    # Filter out near-zero weight components
    active = [(c, w) for c, w in zip(colors, eff_weights) if w > 1e-6]
    if not active:
        return colors[0]
    if len(active) == 1:
        return active[0][0]

    # Sequential optical blending fold
    accum_color, accum_w = active[0]
    for next_color, next_w in active[1:]:
        ratio = next_w / (accum_w + next_w)
        accum_color = mix_filament_pair(accum_color, next_color, ratio)
        accum_w += next_w

    return accum_color


# Standard base filament libraries
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


def create_filament_palette(
    spools: Optional[Union[str, Sequence[Union[str, Sequence[Union[int, float]], Dict]]]] = "CMYKW",
    ratios: Optional[Sequence[float]] = None,
    include_tints: bool = True,
    include_shades: bool = True,
) -> List[Dict]:
    """Generates a comprehensive virtual mixing palette from physical filament spools.

    As in Full Spectrum 3D online, this helper takes a set of loaded physical spools
    and computes:
    1. Pure base spools (100% individual filament).
    2. Discrete pairwise mixes across chromatic spools at specified ratio intervals.
    3. Tints (50/50 mix with White spool, if available).
    4. Shades (50/50 mix with Black spool, if available).

    Args:
        spools (str or sequence, optional): Preset name ('CMYKW', 'RBYKW', 'EARTH_TERRAIN')
            or sequence of filament dicts/colors. Defaults to 'CMYKW'.
        ratios (sequence of float, optional): Mixing ratio intervals between 0 and 1.
            Defaults to [0.25, 0.5, 0.75] (corresponding to 1/4, 2/4, and 3/4 layer fractions).
        include_tints (bool, optional): Whether to include 50% white tints. Defaults to True.
        include_shades (bool, optional): Whether to include 50% black shades. Defaults to True.

    Returns:
        list of dict: List of palette entries, each containing:
            - 'name': Descriptive name of the mix.
            - 'color': (R, G, B) integer tuple.
            - 'hex': '#rrggbb' string.
            - 'recipe': List of dicts specifying spools and weights.
    """
    if isinstance(spools, str):
        if spools.upper() not in FILAMENT_PRESETS:
            raise ValueError(
                f"Unknown filament preset '{spools}'. Available: {list(FILAMENT_PRESETS.keys())}"
            )
        spool_list = FILAMENT_PRESETS[spools.upper()]
    else:
        spool_list = list(spools)

    if not spool_list:
        raise ValueError("Spools list cannot be empty.")

    # Normalize spool list to structured dicts
    clean_spools = []
    for idx, s in enumerate(spool_list):
        if isinstance(s, dict):
            name = s.get("name", f"Spool {idx + 1}")
            c = parse_color(s)
            td = s.get("td", 1.0)
        else:
            name = f"Spool {idx + 1}"
            c = parse_color(s)
            td = 1.0
        clean_spools.append({"name": name, "color": c, "td": td, "hex": color_to_hex(c)})

    if ratios is None:
        mix_ratios = [0.25, 0.5, 0.75]
    else:
        mix_ratios = [float(r) for r in ratios if 0.0 < r < 1.0]

    # Identify white and black spools for tints/shades
    white_spool = None
    black_spool = None
    chromatic_spools = []

    for s in clean_spools:
        c = s["color"]
        # Achromatic test (saturation near zero)
        is_neutral = (max(c) - min(c)) <= 15
        if is_neutral and np.mean(c) > 200:
            white_spool = s
        elif is_neutral and np.mean(c) < 50:
            black_spool = s
        else:
            chromatic_spools.append(s)

    palette: List[Dict] = []
    seen_hex = set()

    def _add_entry(name: str, rgb: Tuple[int, int, int], recipe: List[Dict]):
        hex_code = color_to_hex(rgb)
        if hex_code not in seen_hex:
            seen_hex.add(hex_code)
            palette.append({
                "name": name,
                "color": rgb,
                "hex": hex_code,
                "recipe": recipe,
            })

    # 1. Pure base spools
    for s in clean_spools:
        _add_entry(s["name"], s["color"], [{"spool": s["name"], "weight": 1.0}])

    # 2. Pairwise mixtures of chromatic spools
    chrom_mixes = []
    n_chrom = len(chromatic_spools)
    for i in range(n_chrom):
        for j in range(i + 1, n_chrom):
            s1 = chromatic_spools[i]
            s2 = chromatic_spools[j]
            for r in mix_ratios:
                mixed_rgb = mix_filament_pair(s1["color"], s2["color"], r)
                mix_name = f"{s1['name']} {int(round((1-r)*100))}% / {s2['name']} {int(round(r*100))}%"
                mix_recipe = [
                    {"spool": s1["name"], "weight": round(1.0 - r, 2)},
                    {"spool": s2["name"], "weight": round(r, 2)},
                ]
                _add_entry(mix_name, mixed_rgb, mix_recipe)
                chrom_mixes.append((mix_name, mixed_rgb, mix_recipe))

    # 3. Tints with White
    if include_tints and white_spool is not None:
        # Tint pure chromatics
        for s in chromatic_spools:
            tint_rgb = mix_filament_pair(s["color"], white_spool["color"], 0.5)
            _add_entry(
                f"{s['name']} Tint (50% White)",
                tint_rgb,
                [{"spool": s["name"], "weight": 0.5}, {"spool": white_spool["name"], "weight": 0.5}],
            )
        # Tint pairwise mixes
        for mix_name, mix_rgb, mix_recipe in chrom_mixes:
            tint_rgb = mix_filament_pair(mix_rgb, white_spool["color"], 0.5)
            tinted_recipe = [
                {"spool": r["spool"], "weight": round(r["weight"] * 0.5, 2)}
                for r in mix_recipe
            ]
            tinted_recipe.append({"spool": white_spool["name"], "weight": 0.5})
            _add_entry(f"{mix_name} Tint", tint_rgb, tinted_recipe)

    # 4. Shades with Black
    if include_shades and black_spool is not None:
        for s in chromatic_spools:
            shade_rgb = mix_filament_pair(s["color"], black_spool["color"], 0.5)
            _add_entry(
                f"{s['name']} Shade (50% Black)",
                shade_rgb,
                [{"spool": s["name"], "weight": 0.5}, {"spool": black_spool["name"], "weight": 0.5}],
            )
        for mix_name, mix_rgb, mix_recipe in chrom_mixes:
            shade_rgb = mix_filament_pair(mix_rgb, black_spool["color"], 0.5)
            shaded_recipe = [
                {"spool": r["spool"], "weight": round(r["weight"] * 0.5, 2)}
                for r in mix_recipe
            ]
            shaded_recipe.append({"spool": black_spool["name"], "weight": 0.5})
            _add_entry(f"{mix_name} Shade", shade_rgb, shaded_recipe)

    return palette


def match_filament_color(
    target_color: Union[str, Sequence[Union[int, float]], Dict],
    palette: Sequence[Union[Dict, Sequence[Union[int, float]], str]],
) -> Dict:
    """Finds the closest mixed filament color in a palette using perceptual CIE Delta-E.

    Args:
        target_color: Color to match (hex, RGB, or dict).
        palette: Sequence of palette items (from create_filament_palette or list of colors).

    Returns:
        dict: The best matching palette item with added 'delta_e' distance score.
    """
    tgt_rgb = parse_color(target_color)
    best_item = None
    min_dist = float("inf")

    for item in palette:
        item_rgb = parse_color(item)
        dist = delta_e_lab(tgt_rgb, item_rgb)
        if dist < min_dist:
            min_dist = dist
            if isinstance(item, dict):
                best_item = dict(item)
            else:
                best_item = {
                    "color": item_rgb,
                    "hex": color_to_hex(item_rgb),
                    "recipe": [{"spool": "Custom", "weight": 1.0}],
                }

    if best_item is not None:
        best_item["delta_e"] = round(min_dist, 2)
    return best_item or {}


def create_banded_colormap(
    colors: Sequence[Union[str, Sequence[Union[int, float]], Dict]],
    boundaries: Sequence[float],
    name: str = "banded_filament",
) -> Tuple[ListedColormap, BoundaryNorm]:
    """Creates a discrete Matplotlib ListedColormap and BoundaryNorm for multi-color slicing.

    Designed for 3D printing and terrain classification, where continuous data fields
    (elevation, slope, bathymetry) are segmented into distinct filament materials.

    Args:
        colors (sequence): List of N color representations (RGB tuples, hex strings, or dicts).
        boundaries (sequence of float): List of threshold values.
            Can be:
            - Length N - 1: Internal thresholds (e.g., [-2000, 0, 1500] for 4 colors).
            - Length N + 1: Explicit bracket limits [min, b1, ..., b_{N-1}, max].
        name (str, optional): Name for the Matplotlib colormap. Defaults to 'banded_filament'.

    Returns:
        tuple: (ListedColormap, BoundaryNorm) compatible with matplotlib plotting and
            data categorization.

    Raises:
        ValueError: If lengths of colors and boundaries do not conform.
    """
    rgb_list = [parse_color(c) for c in colors]
    n_colors = len(rgb_list)
    b_list = [float(b) for b in boundaries]

    if len(b_list) == n_colors - 1:
        # Construct explicit outer bounds with generous margins for BoundaryNorm
        span = b_list[-1] - b_list[0] if len(b_list) > 1 else max(abs(b_list[0]), 100.0)
        margin = max(span * 0.5, 1000.0)
        norm_boundaries = [b_list[0] - margin] + b_list + [b_list[-1] + margin]
    elif len(b_list) == n_colors + 1:
        norm_boundaries = b_list
    else:
        raise ValueError(
            f"Expected either {n_colors - 1} internal boundaries or {n_colors + 1} explicit "
            f"bracket boundaries for {n_colors} colors; received {len(b_list)}."
        )

    norm_colors = [(r / 255.0, g / 255.0, b / 255.0) for r, g, b in rgb_list]
    cmap = ListedColormap(norm_colors, name=name)
    norm = BoundaryNorm(norm_boundaries, ncolors=n_colors, clip=True)

    return (cmap, norm)


def create_elevation_banded_colormap(
    palette: Union[str, Sequence[Dict]] = "TERRAIN_4",
    boundaries: Optional[Sequence[float]] = None,
    name: str = "elevation_filament_bands",
) -> Tuple[ListedColormap, BoundaryNorm, List[Dict]]:
    """Creates an authentic hypsometric/bathymetric banded colormap mixed from physical filaments.

    Generates 8 standard geological elevation zones from abyssal ocean depths to glaciated
    high peaks, mixed using Full Spectrum optical blending discretised into strict 1/4 layer
    ratios (multiples of 0.25 corresponding to 4 physical layers at 0.10 mm layer height).
    Supports either a 4-filament base bundle (Brown, Dark Blue, White, Dark Green) or
    standard 5-spool CMYKW:

    TERRAIN_4 Zones (default):
    1. Abyssal Plain (< -1500 m): 4/4 Dark Blue (Pure)
    2. Continental Slope (-1500 to -250 m): 2/4 Dark Blue + 1/4 Dark Green + 1/4 White
    3. Continental Shelf & Shallow Seas (-250 to 0 m): 2/4 Dark Blue + 2/4 White
    4. Lowland Plains (0 to 150 m): 4/4 Dark Green (Pure Dark Green)
    5. Interior Savanna & Plains (150 to 450 m): 2/4 Dark Green + 1/4 Brown + 1/4 White
    6. Midlands & Plateaus (450 to 950 m): 2/4 Brown + 1/4 Dark Green + 1/4 White
    7. Mountain Ranges (950 to 1500 m): 4/4 Brown (Pure)
    8. Alpine High Peaks (> 1500 m): 4/4 White (Pure)

    CMYKW Zones:
    1. Abyssal Plain (< -4000 m): 2/4 Cyan + 1/4 Magenta + 1/4 Black
    2. Deep Ocean (-4000 to -2000 m): 3/4 Cyan + 1/4 Magenta
    3. Continental Shelf (-2000 to -200 m): 2/4 Cyan + 1/4 Yellow + 1/4 White
    4. Shallow Coastal Seas (-200 to 0 m): 2/4 Cyan + 2/4 White
    5. Lowland Plains (0 to 500 m): 2/4 Yellow + 1/4 Cyan + 1/4 White
    6. Midlands / Hills (500 to 1500 m): 2/4 Yellow + 1/4 Cyan + 1/4 Magenta
    7. Highlands / Mountains (1500 to 3000 m): 2/4 Yellow + 1/4 Magenta + 1/4 White
    8. Alpine High Peaks (> 3000 m): 4/4 White (Pure)

    Args:
        palette (str or sequence, optional): Base spools preset name ('TERRAIN_4' for brown,
            dark blue, white, dark green; or 'CMYKW') or custom spool sequence.
            Defaults to 'TERRAIN_4'.
        boundaries (sequence of float, optional): Custom 7 internal threshold values in meters.
            Defaults to [-1500.0, -250.0, 0.0, 150.0, 450.0, 950.0, 1500.0] for TERRAIN_4,
            or [-4000.0, -2000.0, -200.0, 0.0, 500.0, 1500.0, 3000.0] for CMYKW.
        name (str, optional): Colormap identifier. Defaults to 'elevation_filament_bands'.

    Returns:
        tuple: (cmap, norm, band_info)
            - cmap: Matplotlib ListedColormap.
            - norm: Matplotlib BoundaryNorm.
            - band_info: List of dicts specifying zone label, elevation range, RGB color, hex,
              and filament mix recipe for each band.
    """
    is_cmyk = isinstance(palette, str) and palette.upper() == "CMYKW"

    if is_cmyk:
        if boundaries is None:
            thresh = [-4000.0, -2000.0, -200.0, 0.0, 500.0, 1500.0, 3000.0]
        else:
            thresh = [float(b) for b in boundaries]

        if len(thresh) != 7:
            raise ValueError(f"Standard elevation banded colormap requires 7 thresholds, got {len(thresh)}.")

        c = (0, 255, 255)
        m = (255, 0, 255)
        y = (255, 255, 0)
        k = (20, 20, 20)
        w = (250, 250, 250)
        band_specs = [
            {
                "name": "Abyssal Plain",
                "range": f"< {thresh[0]:.0f} m",
                "color": mix_filaments([c, m, k], [0.50, 0.25, 0.25]),
                "recipe": [("Cyan", 0.50), ("Magenta", 0.25), ("Black", 0.25)],
                "layers": "2/4 Cyan + 1/4 Magenta + 1/4 Black",
            },
            {
                "name": "Deep Ocean",
                "range": f"{thresh[0]:.0f} to {thresh[1]:.0f} m",
                "color": mix_filaments([c, m], [0.75, 0.25]),
                "recipe": [("Cyan", 0.75), ("Magenta", 0.25)],
                "layers": "3/4 Cyan + 1/4 Magenta",
            },
            {
                "name": "Continental Shelf",
                "range": f"{thresh[1]:.0f} to {thresh[2]:.0f} m",
                "color": mix_filaments([c, y, w], [0.50, 0.25, 0.25]),
                "recipe": [("Cyan", 0.50), ("Yellow", 0.25), ("White", 0.25)],
                "layers": "2/4 Cyan + 1/4 Yellow + 1/4 White",
            },
            {
                "name": "Shallow Coastal Seas",
                "range": f"{thresh[2]:.0f} to {thresh[3]:.0f} m",
                "color": mix_filaments([c, w], [0.50, 0.50]),
                "recipe": [("Cyan", 0.50), ("White", 0.50)],
                "layers": "2/4 Cyan + 2/4 White",
            },
            {
                "name": "Lowland Plains",
                "range": f"{thresh[3]:.0f} to {thresh[4]:.0f} m",
                "color": mix_filaments([y, c, w], [0.50, 0.25, 0.25]),
                "recipe": [("Yellow", 0.50), ("Cyan", 0.25), ("White", 0.25)],
                "layers": "2/4 Yellow + 1/4 Cyan + 1/4 White",
            },
            {
                "name": "Midlands / Hills",
                "range": f"{thresh[4]:.0f} to {thresh[5]:.0f} m",
                "color": mix_filaments([y, c, m], [0.50, 0.25, 0.25]),
                "recipe": [("Yellow", 0.50), ("Cyan", 0.25), ("Magenta", 0.25)],
                "layers": "2/4 Yellow + 1/4 Cyan + 1/4 Magenta",
            },
            {
                "name": "Highlands / Mountains",
                "range": f"{thresh[5]:.0f} to {thresh[6]:.0f} m",
                "color": mix_filaments([y, m, w], [0.50, 0.25, 0.25]),
                "recipe": [("Yellow", 0.50), ("Magenta", 0.25), ("White", 0.25)],
                "layers": "2/4 Yellow + 1/4 Magenta + 1/4 White",
            },
            {
                "name": "Alpine High Peaks",
                "range": f"> {thresh[6]:.0f} m",
                "color": w,
                "recipe": [("White", 1.0)],
                "layers": "4/4 White",
            },
        ]
    else:
        # Default 4 base filaments: Brown, Dark Blue, White, Dark Green
        dark_blue = (18, 52, 120)
        dark_green = (32, 95, 42)
        brown = (142, 68, 28)
        white = (250, 250, 250)

        # If custom spool list provided, match by name or index
        if isinstance(palette, (list, tuple)) and len(palette) >= 4:
            spool_map = {}
            for s in palette:
                if isinstance(s, dict) and "name" in s:
                    spool_map[s["name"].lower()] = parse_color(s)
            if "dark blue" in spool_map or "blue" in spool_map:
                dark_blue = spool_map.get("dark blue", spool_map.get("blue"))
            if "dark green" in spool_map or "green" in spool_map:
                dark_green = spool_map.get("dark green", spool_map.get("green"))
            if "brown" in spool_map:
                brown = spool_map["brown"]
            if "white" in spool_map:
                white = spool_map["white"]

        if boundaries is None:
            thresh = [-1500.0, -250.0, 0.0, 150.0, 450.0, 950.0, 1500.0]
        else:
            thresh = [float(b) for b in boundaries]

        if len(thresh) != 7:
            raise ValueError(f"Standard elevation banded colormap requires 7 thresholds, got {len(thresh)}.")

        band_specs = [
            {
                "name": "Abyssal Plain",
                "range": f"< {thresh[0]:.0f} m",
                "color": dark_blue,
                "recipe": [("Dark Blue", 1.0)],
                "layers": "4/4 Dark Blue",
            },
            {
                "name": "Continental Slope",
                "range": f"{thresh[0]:.0f} to {thresh[1]:.0f} m",
                "color": mix_filaments([dark_blue, dark_green, white], [0.50, 0.25, 0.25]),
                "recipe": [("Dark Blue", 0.50), ("Dark Green", 0.25), ("White", 0.25)],
                "layers": "2/4 Dark Blue + 1/4 Dark Green + 1/4 White",
            },
            {
                "name": "Continental Shelf & Shallow Seas",
                "range": f"{thresh[1]:.0f} to {thresh[2]:.0f} m",
                "color": mix_filaments([dark_blue, white], [0.50, 0.50]),
                "recipe": [("Dark Blue", 0.50), ("White", 0.50)],
                "layers": "2/4 Dark Blue + 2/4 White",
            },
            {
                "name": "Lowland Plains",
                "range": f"{thresh[2]:.0f} to {thresh[3]:.0f} m",
                "color": dark_green,
                "recipe": [("Dark Green", 1.0)],
                "layers": "4/4 Dark Green",
            },
            {
                "name": "Interior Savanna & Plains",
                "range": f"{thresh[3]:.0f} to {thresh[4]:.0f} m",
                "color": mix_filaments([dark_green, brown, white], [0.50, 0.25, 0.25]),
                "recipe": [("Dark Green", 0.50), ("Brown", 0.25), ("White", 0.25)],
                "layers": "2/4 Dark Green + 1/4 Brown + 1/4 White",
            },
            {
                "name": "Midlands & Plateaus",
                "range": f"{thresh[4]:.0f} to {thresh[5]:.0f} m",
                "color": mix_filaments([brown, dark_green, white], [0.50, 0.25, 0.25]),
                "recipe": [("Brown", 0.50), ("Dark Green", 0.25), ("White", 0.25)],
                "layers": "2/4 Brown + 1/4 Dark Green + 1/4 White",
            },
            {
                "name": "Mountain Ranges",
                "range": f"{thresh[5]:.0f} to {thresh[6]:.0f} m",
                "color": brown,
                "recipe": [("Brown", 1.0)],
                "layers": "4/4 Brown",
            },
            {
                "name": "Alpine High Peaks",
                "range": f"> {thresh[6]:.0f} m",
                "color": white,
                "recipe": [("White", 1.0)],
                "layers": "4/4 White",
            },
        ]

    colors = [b["color"] for b in band_specs]
    for b in band_specs:
        b["hex"] = color_to_hex(b["color"])

    cmap, norm = create_banded_colormap(colors, thresh, name=name)
    return (cmap, norm, band_specs)


def apply_banded_colormap(
    data_array: np.ndarray,
    colors: Sequence[Union[str, Sequence[Union[int, float]], Dict]],
    boundaries: Sequence[float],
) -> np.ndarray:
    """Applies a banded colormap to a 2D scalar array, returning a 3D RGB uint8 image.

    Values below the first boundary get the first color; values between successive
    boundaries get the respective colors; values above or equal to the final boundary
    get the last color.

    Args:
        data_array (np.ndarray): 2D array of numerical values (e.g. elevation grid).
        colors (sequence): List of N color representations.
        boundaries (sequence of float): List of N - 1 threshold boundaries.

    Returns:
        np.ndarray: (H, W, 3) array of RGB values with dtype uint8.
    """
    clean_colors = [parse_color(c) for c in colors]
    return render_2d_array_as_rgb(data_array, clean_colors, list(boundaries))


def plot_filament_palette(
    palette: Sequence[Dict],
    title: str = "Filament Palette",
    max_swatches: int = 30,
    figsize: Optional[Tuple[float, float]] = None,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Renders a visual swatch preview of a filament palette with recipe annotations.

    Args:
        palette (sequence of dict): Palette items from create_filament_palette or band_specs.
        title (str, optional): Plot title. Defaults to 'Filament Palette'.
        max_swatches (int, optional): Maximum number of swatches to display. Defaults to 30.
        figsize (tuple, optional): Matplotlib figure dimensions. Defaults to dynamic sizing.
        ax (plt.Axes, optional): Target matplotlib axes. Defaults to None.

    Returns:
        plt.Axes: The rendered matplotlib axes.
    """
    items = list(palette)[:max_swatches]
    n = len(items)
    if n == 0:
        raise ValueError("Palette cannot be empty.")

    if ax is None:
        fig_w = figsize[0] if figsize else min(max(n * 0.8, 8.0), 16.0)
        fig_h = figsize[1] if figsize else 3.5
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    for idx, item in enumerate(items):
        rgb = parse_color(item)
        hex_code = item.get("hex", color_to_hex(rgb))
        name = item.get("name", f"Mix {idx+1}")

        # Draw color bar swatch
        norm_c = [c / 255.0 for c in rgb]
        ax.bar(idx, 1.0, color=norm_c, edgecolor="black", linewidth=0.8, width=0.9)

        # Label hex
        ax.text(
            idx,
            0.5,
            hex_code,
            ha="center",
            va="center",
            rotation=90,
            fontsize=8,
            fontweight="bold",
            color="white" if np.mean(rgb) < 130 else "black",
        )

    ax.set_xticks(range(n))
    labels = [item.get("name", "") for item in items]
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticks([])
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_ylim(0, 1)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
    plt.tight_layout()
    return ax


def plot_banded_colormap_preview(
    cmap: ListedColormap,
    norm: BoundaryNorm,
    boundaries: Sequence[float],
    band_labels: Optional[Sequence[str]] = None,
    title: str = "Banded Colormap Preview",
    figsize: Tuple[float, float] = (10.0, 2.0),
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Displays an annotated horizontal colorbar preview of a discrete banded colormap.

    Args:
        cmap (ListedColormap): The discrete colormap.
        norm (BoundaryNorm): Threshold normalization norm.
        boundaries (sequence of float): Threshold boundaries.
        band_labels (sequence of str, optional): Optional labels for each discrete band.
            Defaults to None.
        title (str, optional): Title for the colorbar preview. Defaults to 'Banded Colormap Preview'.
        figsize (tuple, optional): Dimensions of the figure. Defaults to (10.0, 2.0).
        ax (plt.Axes, optional): Target matplotlib axes. Defaults to None.

    Returns:
        plt.Axes: The rendered matplotlib axes.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)

    cbar = plt.colorbar(
        plt.cm.ScalarMappable(cmap=cmap, norm=norm),
        cax=ax,
        orientation="horizontal",
        ticks=boundaries,
    )
    cbar.set_label(title, fontsize=10, fontweight="bold", labelpad=8)
    cbar.ax.tick_params(labelsize=8)

    if band_labels and len(band_labels) == cmap.N:
        # Place centered labels inside each band
        b_extended = norm.boundaries
        for i, label in enumerate(band_labels):
            mid_val = 0.5 * (b_extended[i] + b_extended[i + 1])
            # Determine contrasting text color
            r, g, b, _ = cmap(i)
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            txt_col = "black" if lum > 0.5 else "white"
            ax.text(
                mid_val,
                0.5,
                label,
                ha="center",
                va="center",
                fontsize=7,
                fontweight="bold",
                color=txt_col,
                transform=cbar.ax.get_xaxis_transform(),
            )

    plt.tight_layout()
    return ax
