"""Image preprocessing and spherical vector symbol rendering for globe textures.

This module provides tools to preprocess equirectangular texture maps for 3D printing
(e.g., hillshade removal, noise smoothing, color quantization to filament palettes)
and project vector SVG symbols (location pins, pole markers) spherically onto globe maps.
"""

from __future__ import annotations

import os
import math
import xml.etree.ElementTree as ET
from typing import Union, List, Tuple, Optional
import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from svg.path import parse_path, Line, QuadraticBezier, CubicBezier, Arc
except ImportError:
    parse_path = None

VERY_SMALL_NUMBER = 1e-7
DEFAULT_SVG_SAMPLES_PER_SEGMENT = 5


def _ensure_rgba_color(color_tuple: tuple, default_alpha: int = 255) -> Tuple[int, int, int, int]:
    """Ensures a color tuple is in (R, G, B, A) format with integer components (0-255).

    Args:
        color_tuple (tuple): RGB or RGBA tuple with values in 0-255 or 0.0-1.0.
        default_alpha (int, optional): Default alpha if not provided. Defaults to 255.

    Returns:
        tuple[int, int, int, int]: (R, G, B, A) integers from 0 to 255.
    """
    if not isinstance(color_tuple, (list, tuple)) or len(color_tuple) not in [3, 4]:
        raise ValueError("Color must be a 3-element (RGB) or 4-element (RGBA) sequence.")

    # Convert normalized float (0.0 - 1.0) to 0 - 255 if applicable
    vals = list(color_tuple)
    if any(isinstance(v, float) and 0.0 <= v <= 1.0 for v in vals) and all(v <= 1.0 for v in vals):
        vals = [int(round(v * 255)) for v in vals]
    else:
        vals = [int(round(v)) for v in vals]

    r, g, b = vals[:3]
    a = vals[3] if len(vals) == 4 else int(round(default_alpha))

    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    a = max(0, min(255, a))

    return (r, g, b, a)


def _normalize_lon_180(lon: float) -> float:
    """Normalizes longitude to (-180, 180] degrees."""
    normalized = ((lon + 180.0) % 360.0) - 180.0
    return 180.0 if normalized == -180.0 else normalized


def destination_point(
    lat1_deg: float, lon1_deg: float, distance_deg: float, bearing_deg: float
) -> Tuple[float, float]:
    """Calculates destination point given start point, angular distance, and initial bearing.

    Args:
        lat1_deg (float): Initial latitude in degrees.
        lon1_deg (float): Initial longitude in degrees.
        distance_deg (float): Angular distance traveled across sphere in degrees.
        bearing_deg (float): Initial bearing (clockwise from north) in degrees.

    Returns:
        tuple[float, float]: (destination_latitude_deg, destination_longitude_deg).
    """
    lat1_rad = math.radians(lat1_deg)
    lon1_rad = math.radians(lon1_deg)
    bearing_rad = math.radians(bearing_deg)
    angular_dist_rad = math.radians(distance_deg)

    sin_lat1 = math.sin(lat1_rad)
    cos_lat1 = math.cos(lat1_rad)
    sin_d = math.sin(angular_dist_rad)
    cos_d = math.cos(angular_dist_rad)

    sin_lat2 = sin_lat1 * cos_d + cos_lat1 * sin_d * math.cos(bearing_rad)
    sin_lat2 = max(-1.0, min(1.0, sin_lat2))
    lat2_rad = math.asin(sin_lat2)

    y = math.sin(bearing_rad) * sin_d * cos_lat1
    x = cos_d - sin_lat1 * sin_lat2
    lon2_rad = lon1_rad + math.atan2(y, x)

    lat2_deg = math.degrees(lat2_rad)
    lon2_deg = math.degrees(lon2_rad)
    return (lat2_deg, _normalize_lon_180(lon2_deg))


def great_circle_interpolate(
    p1_geo: Tuple[float, float], p2_geo: Tuple[float, float], num_intermediate_points: int
) -> List[Tuple[float, float]]:
    """Interpolates points along a great circle path between two geographic coordinates.

    Args:
        p1_geo (tuple): (lat1, lon1) in degrees.
        p2_geo (tuple): (lat2, lon2) in degrees.
        num_intermediate_points (int): Number of intermediate points to generate.

    Returns:
        list[tuple[float, float]]: Interpolated (lat, lon) coordinates including start and end.
    """
    lat1_deg, lon1_deg = p1_geo
    lat2_deg, lon2_deg = p2_geo

    if num_intermediate_points <= 0 or (abs(lat1_deg - lat2_deg) < VERY_SMALL_NUMBER and abs(lon1_deg - lon2_deg) < VERY_SMALL_NUMBER):
        return [p1_geo, p2_geo]

    lat1_rad = math.radians(lat1_deg)
    lon1_rad = math.radians(lon1_deg)
    lat2_rad = math.radians(lat2_deg)
    lon2_rad = math.radians(lon2_deg)

    # Angular distance via Haversine
    d_lat = lat2_rad - lat1_rad
    d_lon = lon2_rad - lon1_rad
    a = math.sin(d_lat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(d_lon / 2)**2
    a = max(0.0, min(1.0, a))
    delta_rad = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    if delta_rad < VERY_SMALL_NUMBER:
        return [p1_geo, p2_geo]

    sin_delta = math.sin(delta_rad)
    interpolated_points = [p1_geo]

    for i in range(1, num_intermediate_points + 1):
        f = float(i) / (num_intermediate_points + 1)
        A = math.sin((1 - f) * delta_rad) / sin_delta
        B = math.sin(f * delta_rad) / sin_delta

        x = A * math.cos(lat1_rad) * math.cos(lon1_rad) + B * math.cos(lat2_rad) * math.cos(lon2_rad)
        y = A * math.cos(lat1_rad) * math.sin(lon1_rad) + B * math.cos(lat2_rad) * math.sin(lon2_rad)
        z = A * math.sin(lat1_rad) + B * math.sin(lat2_rad)

        lat_rad_interp = math.atan2(z, math.sqrt(x**2 + y**2))
        lon_rad_interp = math.atan2(y, x)

        interpolated_points.append((math.degrees(lat_rad_interp), _normalize_lon_180(math.degrees(lon_rad_interp))))

    interpolated_points.append(p2_geo)
    return interpolated_points


def _parse_svg_path(path_d: str, samples_per_segment: int) -> List[Tuple[float, float]]:
    """Parses an SVG path 'd' attribute string into a list of (x, y) coordinates."""
    if parse_path is None:
        raise ImportError("svg.path is required to parse SVG files. Please install it via pip.")

    points = []
    try:
        path_obj = parse_path(path_d)
    except Exception:
        return []

    if not path_obj:
        return []

    for segment in path_obj:
        start_coord = (segment.start.real, segment.start.imag)
        if not points or (abs(points[-1][0] - start_coord[0]) > VERY_SMALL_NUMBER or abs(points[-1][1] - start_coord[1]) > VERY_SMALL_NUMBER):
            points.append(start_coord)

        if isinstance(segment, Line):
            points.append((segment.end.real, segment.end.imag))
        elif isinstance(segment, (QuadraticBezier, CubicBezier, Arc)):
            num_samples = max(1, samples_per_segment)
            for i in range(1, num_samples + 1):
                t = i / float(num_samples)
                try:
                    p = segment.point(t)
                    points.append((p.real, p.imag))
                except Exception:
                    if i == num_samples and hasattr(segment, 'end'):
                        points.append((segment.end.real, segment.end.imag))
                    break

    if not points:
        return []

    # Deduplicate consecutive points
    unique_points = [points[0]]
    for i in range(1, len(points)):
        if abs(points[i][0] - points[i-1][0]) > VERY_SMALL_NUMBER or abs(points[i][1] - points[i-1][1]) > VERY_SMALL_NUMBER:
            unique_points.append(points[i])
    return unique_points


def _parse_svg_to_points(svg_source: str, samples_per_segment: int = DEFAULT_SVG_SAMPLES_PER_SEGMENT) -> List[Tuple[float, float]]:
    """Parses SVG XML content or file path into a list of 2D Cartesian boundary points."""
    all_points = []
    try:
        if os.path.exists(svg_source):
            tree = ET.parse(svg_source)
            root = tree.getroot()
        else:
            root = ET.fromstring(svg_source)

        for elem in root.iter():
            tag_name = elem.tag.split('}')[-1]
            if tag_name == 'path':
                d_attr = elem.get('d')
                if d_attr:
                    pts = _parse_svg_path(d_attr, samples_per_segment)
                    all_points.extend(pts)
            elif tag_name in ['polygon', 'polyline']:
                pts_str = elem.get('points')
                if pts_str:
                    pairs = pts_str.strip().split()
                    for pair in pairs:
                        coords = pair.split(',')
                        if len(coords) == 2:
                            try:
                                all_points.append((float(coords[0]), float(coords[1])))
                            except ValueError:
                                pass
                    if tag_name == 'polygon' and all_points:
                        all_points.append(all_points[0])
    except Exception as e:
        raise ValueError(f"Failed to parse SVG: {e}")

    return all_points


def _is_point_in_polygon(x: float, y: float, poly: List[Tuple[float, float]]) -> bool:
    """Point-in-polygon test using ray-casting algorithm."""
    n = len(poly)
    inside = False
    p1x, p1y = poly[0]
    for i in range(n + 1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def _get_builtin_asset_path(symbol_name: str) -> Optional[str]:
    """Resolves builtin asset filename (e.g. 'N', 'S', 'star')."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "assets", f"{symbol_name}.svg"),
        os.path.join(base_dir, "assets", f"{symbol_name}_logo.svg"),
        os.path.join(base_dir, "assets", symbol_name),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def add_svg_symbol_spherical(
    base_image: Union[str, Image.Image, np.ndarray],
    svg_source: str,
    center_lat_deg: float,
    center_lon_deg: float,
    symbol_radius_degrees: float,
    fill_color: tuple = (255, 0, 0, 255),
    interpolation_factor: int = 10,
    svg_samples_per_curve_segment: int = DEFAULT_SVG_SAMPLES_PER_SEGMENT,
) -> Image.Image:
    """Renders an SVG symbol onto an equirectangular image at specified geographic coordinates.

    Scales the symbol to a target angular radius on the sphere, projects its boundary points
    using great-circle geometry, and rasterizes the polygon onto the map.

    Args:
        base_image (str, PIL.Image.Image, or np.ndarray): Base equirectangular texture image.
        svg_source (str): Path to an SVG file, builtin name ('N', 'S', 'star'), or raw SVG XML string.
        center_lat_deg (float): Center latitude on the sphere (-90 to 90).
        center_lon_deg (float): Center longitude on the sphere (-180 to 180).
        symbol_radius_degrees (float): Angular radius of the symbol in degrees.
        fill_color (tuple, optional): RGB or RGBA fill color (0-255). Defaults to (255, 0, 0, 255).
        interpolation_factor (int, optional): Intermediate points per great-circle arc. Defaults to 10.
        svg_samples_per_curve_segment (int, optional): Samples per curve segment. Defaults to 5.

    Returns:
        PIL.Image.Image: RGBA PIL Image with the symbol rendered.
    """
    if isinstance(base_image, str):
        img = Image.open(base_image).convert("RGBA")
    elif isinstance(base_image, np.ndarray):
        if base_image.dtype != np.uint8 and base_image.max() <= 1.0:
            base_image = (base_image * 255).astype(np.uint8)
        img = Image.fromarray(base_image).convert("RGBA")
    elif isinstance(base_image, Image.Image):
        img = base_image.copy().convert("RGBA")
    else:
        raise TypeError("base_image must be a file path, PIL Image, or NumPy array.")

    width, height = img.size
    rgba_fill = _ensure_rgba_color(fill_color)

    # Check for builtin symbol
    resolved_svg = _get_builtin_asset_path(svg_source) or svg_source

    svg_points = _parse_svg_to_points(resolved_svg, svg_samples_per_curve_segment)
    if len(svg_points) < 3:
        return img

    # Compute center and scaling in SVG coordinates
    xs = [p[0] for p in svg_points]
    ys = [p[1] for p in svg_points]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0

    # Max radius from center in SVG coords
    radii = [math.hypot(x - cx, y - cy) for x, y in svg_points]
    max_svg_radius = max(radii) if radii else 1.0
    if max_svg_radius < VERY_SMALL_NUMBER:
        return img

    # Transform SVG points into spherical (lat, lon) coordinates
    geo_polygon = []
    for x, y in svg_points:
        dx = x - cx
        dy = y - cy
        r_frac = math.hypot(dx, dy) / max_svg_radius
        angular_dist = r_frac * symbol_radius_degrees
        # Bearing: SVG y is downwards, so -dy maps to north (upwards)
        bearing = math.degrees(math.atan2(dx, -dy)) % 360.0
        pt_geo = destination_point(center_lat_deg, center_lon_deg, angular_dist, bearing)
        geo_polygon.append(pt_geo)

    # Densify polygon edges using great-circle interpolation
    densified_geo = []
    for i in range(len(geo_polygon)):
        p1 = geo_polygon[i]
        p2 = geo_polygon[(i + 1) % len(geo_polygon)]
        interp = great_circle_interpolate(p1, p2, interpolation_factor)
        densified_geo.extend(interp[:-1])
    densified_geo.append(geo_polygon[0])

    # Convert geo polygon to pixel coordinates
    # Equirectangular mapping:
    # px = (lon + 180) / 360 * (width - 1)
    # py = (90 - lat) / 180 * (height - 1)
    pixel_polygon = []
    for lat, lon in densified_geo:
        px = (lon + 180.0) / 360.0 * (width - 1)
        py = (90.0 - lat) / 180.0 * (height - 1)
        pixel_polygon.append((px, py))

    # Bounding box of the symbol in pixel space
    min_px = max(0, int(math.floor(min(p[0] for p in pixel_polygon))))
    max_px = min(width - 1, int(math.ceil(max(p[0] for p in pixel_polygon))))
    min_py = max(0, int(math.floor(min(p[1] for p in pixel_polygon))))
    max_py = min(height - 1, int(math.ceil(max(p[1] for p in pixel_polygon))))

    # Draw using PIL ImageDraw polygon or direct pixel assignment
    from PIL import ImageDraw
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.polygon(pixel_polygon, fill=rgba_fill)

    # Composite onto base image
    img = Image.alpha_composite(img, overlay)
    return img


def add_pole_markers(
    base_image: Union[str, Image.Image, np.ndarray],
    marker_size_degrees: float = 2.5,
    color: tuple = (255, 0, 0, 255),
    north_symbol: str = "N",
    south_symbol: str = "S",
) -> Image.Image:
    """Adds North and South pole indicator symbols to an equirectangular image.

    Args:
        base_image (str, PIL.Image.Image, or np.ndarray): Base equirectangular texture.
        marker_size_degrees (float, optional): Angular radius in degrees. Defaults to 2.5.
        color (tuple, optional): RGBA color tuple. Defaults to (255, 0, 0, 255).
        north_symbol (str, optional): SVG symbol or builtin name for North pole. Defaults to 'N'.
        south_symbol (str, optional): SVG symbol or builtin name for South pole. Defaults to 'S'.

    Returns:
        PIL.Image.Image: Texture image with North and South pole markers burned in.
    """
    img = add_svg_symbol_spherical(
        base_image,
        svg_source=north_symbol,
        center_lat_deg=89.9999,
        center_lon_deg=0.0,
        symbol_radius_degrees=marker_size_degrees,
        fill_color=color,
    )
    img = add_svg_symbol_spherical(
        img,
        svg_source=south_symbol,
        center_lat_deg=-89.9999,
        center_lon_deg=0.0,
        symbol_radius_degrees=marker_size_degrees,
        fill_color=color,
    )
    return img


def undo_hillshading(
    image: Union[str, Image.Image, np.ndarray],
    strength: float = 0.5,
) -> Image.Image:
    """Reduces baked-in hillshading in an atlas map by adjusting Lightness in HSL space.

    Args:
        image (str, PIL.Image.Image, or np.ndarray): Input image.
        strength (float, optional): Flattening strength from 0.0 (no change) to 1.0 (flat lightness).
            Defaults to 0.5.

    Returns:
        PIL.Image.Image: Image with hillshading shadows suppressed.
    """
    if isinstance(image, str):
        pil_img = Image.open(image)
    elif isinstance(image, np.ndarray):
        pil_img = Image.fromarray(image)
    else:
        pil_img = image.copy()

    has_alpha = pil_img.mode in ("RGBA", "LA") or ("transparency" in pil_img.info)
    alpha = pil_img.convert("RGBA").getchannel("A") if has_alpha else None

    rgb_img = pil_img.convert("RGB")
    rgb_arr = np.array(rgb_img)

    if cv2 is not None:
        hls = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2HLS)
        l_channel = hls[:, :, 1].astype(np.float32)
        mid_gray = 127.5
        adjusted_l = np.clip(l_channel * (1.0 - strength) + mid_gray * strength, 0, 255).astype(np.uint8)
        hls[:, :, 1] = adjusted_l
        res_rgb_arr = cv2.cvtColor(hls, cv2.COLOR_HLS2RGB)
        res_rgb = Image.fromarray(res_rgb_arr, "RGB")
    else:
        hsv_img = rgb_img.convert("HSV")
        h, s, v_channel = hsv_img.split()
        v_arr = np.array(v_channel, dtype=np.float32)
        adjusted_v = np.clip(v_arr * (1.0 - strength) + 127.5 * strength, 0, 255).astype(np.uint8)
        processed_hsv = Image.merge("HSV", (h, s, Image.fromarray(adjusted_v, mode="L")))
        res_rgb = processed_hsv.convert("RGB")

    if alpha is not None:
        res_rgb.putalpha(alpha)
    return res_rgb


def simplify_image_median(
    image: Union[str, Image.Image, np.ndarray],
    kernel_size: int = 11,
) -> Image.Image:
    """Smooths image noise and removes micro-islands using a median filter.

    Preserves alpha channel if present.

    Args:
        image (str, PIL.Image.Image, or np.ndarray): Input image.
        kernel_size (int, optional): Size of median filter kernel (must be odd). Defaults to 11.

    Returns:
        PIL.Image.Image: Smoothed image.
    """
    if isinstance(image, str):
        pil_img = Image.open(image)
    elif isinstance(image, np.ndarray):
        pil_img = Image.fromarray(image)
    else:
        pil_img = image.copy()

    if kernel_size % 2 == 0:
        kernel_size += 1

    has_alpha = pil_img.mode in ("RGBA", "LA")
    alpha = pil_img.convert("RGBA").getchannel("A") if has_alpha else None

    rgb_img = pil_img.convert("RGB")

    if cv2 is not None:
        cv_img = np.array(rgb_img)
        blurred = cv2.medianBlur(cv_img, kernel_size)
        res = Image.fromarray(blurred, "RGB")
    else:
        from PIL import ImageFilter
        res = rgb_img.filter(ImageFilter.MedianFilter(size=kernel_size))

    if alpha is not None:
        res.putalpha(alpha)
    return res


def simplify_image_bilateral(
    image: Union[str, Image.Image, np.ndarray],
    d: int = 9,
    sigma_color: int = 75,
    sigma_space: int = 75,
) -> Image.Image:
    """Applies edge-preserving bilateral smoothing to flatten plateaus while preserving sharp coastlines.

    Args:
        image (str, PIL.Image.Image, or np.ndarray): Input image.
        d (int, optional): Diameter of each pixel neighborhood. Defaults to 9.
        sigma_color (int, optional): Filter sigma in the color space. Defaults to 75.
        sigma_space (int, optional): Filter sigma in the coordinate space. Defaults to 75.

    Returns:
        PIL.Image.Image: Bilaterally smoothed image.
    """
    if isinstance(image, str):
        pil_img = Image.open(image)
    elif isinstance(image, np.ndarray):
        pil_img = Image.fromarray(image)
    else:
        pil_img = image.copy()

    has_alpha = pil_img.mode in ("RGBA", "LA")
    alpha = pil_img.convert("RGBA").getchannel("A") if has_alpha else None

    rgb_img = pil_img.convert("RGB")

    if cv2 is not None:
        cv_img = np.array(rgb_img)
        filtered = cv2.bilateralFilter(cv_img, d, sigma_color, sigma_space)
        res = Image.fromarray(filtered, "RGB")
    else:
        # Fallback if cv2 not available
        res = simplify_image_median(rgb_img, kernel_size=d if d % 2 == 1 else d + 1)

    if alpha is not None:
        res.putalpha(alpha)
    return res


def simplify_colors(
    image: Union[str, Image.Image, np.ndarray],
    target_colors_rgb: List[Tuple[int, int, int]],
    hsv_weights: Tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> Image.Image:
    """Quantizes image colors to a discrete set of palette colors using weighted HSV distance.

    Ideal for multi-material / multi-filament 3D printing (e.g., Bambu AMS / Prusa MMU)
    to eliminate stray color transitions.

    Args:
        image (str, PIL.Image.Image, or np.ndarray): Input image.
        target_colors_rgb (list of tuples): List of (R, G, B) integer tuples (0-255).
        hsv_weights (tuple, optional): (H_weight, S_weight, V_weight) weighting factors. Defaults to (1.0, 1.0, 1.0).

    Returns:
        PIL.Image.Image: Color-quantized PIL Image.
    """
    if isinstance(image, str):
        pil_img = Image.open(image)
    elif isinstance(image, np.ndarray):
        pil_img = Image.fromarray(image)
    else:
        pil_img = image.copy()

    if not target_colors_rgb:
        raise ValueError("target_colors_rgb must contain at least one color.")

    has_alpha = pil_img.mode in ("RGBA", "LA")
    alpha = pil_img.convert("RGBA").getchannel("A") if has_alpha else None

    rgb_img = pil_img.convert("RGB")
    hsv_img = rgb_img.convert("HSV")
    hsv_array = np.array(hsv_img, dtype=np.float32)
    h, w, _ = hsv_array.shape
    pixels_hsv = hsv_array.reshape(-1, 3)

    # Convert target palette to HSV array
    palette_hsv = []
    for col in target_colors_rgb:
        c_rgb = Image.new("RGB", (1, 1), col)
        c_hsv = c_rgb.convert("HSV").getpixel((0, 0))
        palette_hsv.append(c_hsv)
    targets_hsv = np.array(palette_hsv, dtype=np.float32)

    h_pix = pixels_hsv[:, 0:1]
    s_pix = pixels_hsv[:, 1:2]
    v_pix = pixels_hsv[:, 2:3]

    h_tgt = targets_hsv[np.newaxis, :, 0]
    s_tgt = targets_hsv[np.newaxis, :, 1]
    v_tgt = targets_hsv[np.newaxis, :, 2]

    # Circular hue distance in PIL (0 to 255)
    dh = np.abs(h_pix - h_tgt)
    hue_dist = np.minimum(dh, 256.0 - dh)
    sat_dist = np.abs(s_pix - s_tgt)
    val_dist = np.abs(v_pix - v_tgt)

    w_h, w_s, w_v = hsv_weights
    total_dist = w_h * hue_dist + w_s * sat_dist + w_v * val_dist

    nearest_idx = np.argmin(total_dist, axis=1)

    # Map directly back to target RGB palette
    targets_rgb = np.array(target_colors_rgb, dtype=np.uint8)
    output_rgb = targets_rgb[nearest_idx].reshape(h, w, 3)

    res = Image.fromarray(output_rgb, "RGB")
    if alpha is not None:
        res.putalpha(alpha)
    return res


def render_2d_array_as_rgb(
    data_array: np.ndarray,
    colors: List[Tuple[int, int, int]],
    boundaries: List[float],
) -> np.ndarray:
    """Renders a 2D scalar array into an RGB image mapped through discrete boundary thresholds.

    Args:
        data_array (np.ndarray): 2D array of numerical values.
        colors (list of tuple): List of N RGB tuples (0-255).
        boundaries (list of float): List of N-1 threshold boundaries.

    Returns:
        np.ndarray: (H, W, 3) array of RGB values with dtype uint8.
    """
    arr = np.asarray(data_array, dtype=np.float64)
    if arr.ndim != 2:
        raise ValueError("data_array must be a 2D array.")

    if len(colors) != len(boundaries) + 1:
        raise ValueError(
            f"Length of colors ({len(colors)}) must be exactly len(boundaries) + 1 ({len(boundaries) + 1})."
        )

    h, w = arr.shape
    out = np.zeros((h, w, 3), dtype=np.uint8)

    # Convert colors to clean uint8 tuples
    clean_colors = [_ensure_rgba_color(c)[:3] for c in colors]

    # Digitize values into bin indices
    indices = np.digitize(arr, boundaries)  # 0 to len(boundaries)

    palette = np.array(clean_colors, dtype=np.uint8)
    out = palette[indices]

    return out


def create_banded_colormap(*args, **kwargs):
    """Creates a discrete ListedColormap and BoundaryNorm for multi-color slicing.

    See :func:`globe3d.filaments.create_banded_colormap` for full documentation.
    """
    from .filaments import create_banded_colormap as _cb
    return _cb(*args, **kwargs)


def apply_banded_colormap(*args, **kwargs):
    """Applies a banded colormap to a 2D scalar array, returning an RGB uint8 image.

    See :func:`globe3d.filaments.apply_banded_colormap` for full documentation.
    """
    from .filaments import apply_banded_colormap as _ab
    return _ab(*args, **kwargs)

