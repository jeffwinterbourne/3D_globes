export type RGB = [number, number, number]; // [0..1, 0..1, 0..1]

export const COLORMAP_STOPS: Record<string, RGB[]> = {
  terrain: [
    [0.2, 0.2, 0.6],
    [0.0, 0.59, 0.98],
    [0.0, 0.78, 0.42],
    [0.55, 0.89, 0.44],
    [0.99, 0.94, 0.59],
    [0.64, 0.49, 0.36],
    [0.52, 0.36, 0.27],
    [1.0, 1.0, 1.0],
  ],
  viridis: [
    [0.267, 0.005, 0.329],
    [0.283, 0.141, 0.458],
    [0.254, 0.265, 0.53],
    [0.164, 0.471, 0.558],
    [0.135, 0.659, 0.518],
    [0.478, 0.821, 0.318],
    [0.993, 0.906, 0.144],
  ],
  plasma: [
    [0.05, 0.03, 0.528],
    [0.417, 0.001, 0.658],
    [0.693, 0.165, 0.565],
    [0.881, 0.392, 0.383],
    [0.988, 0.652, 0.211],
    [0.94, 0.975, 0.131],
  ],
  magma: [
    [0.001, 0.0, 0.014],
    [0.232, 0.059, 0.438],
    [0.55, 0.161, 0.506],
    [0.869, 0.288, 0.409],
    [0.995, 0.625, 0.427],
    [0.987, 0.991, 0.75],
  ],
  RdBu: [
    [0.404, 0.0, 0.122],
    [0.84, 0.376, 0.302],
    [0.97, 0.97, 0.97],
    [0.263, 0.576, 0.765],
    [0.02, 0.188, 0.38],
  ],
  RdBu_r: [
    [0.02, 0.188, 0.38],
    [0.263, 0.576, 0.765],
    [0.97, 0.97, 0.97],
    [0.84, 0.376, 0.302],
    [0.404, 0.0, 0.122],
  ],
  coolwarm: [
    [0.23, 0.299, 0.754],
    [0.554, 0.691, 0.996],
    [0.865, 0.865, 0.865],
    [0.957, 0.603, 0.482],
    [0.706, 0.016, 0.15],
  ],
  YlGn: [
    [1.0, 1.0, 0.898],
    [0.78, 0.914, 0.753],
    [0.498, 0.788, 0.498],
    [0.192, 0.639, 0.329],
    [0.0, 0.408, 0.216],
  ],
  Blues: [
    [0.969, 0.984, 1.0],
    [0.776, 0.859, 0.937],
    [0.42, 0.682, 0.839],
    [0.129, 0.443, 0.71],
    [0.031, 0.188, 0.42],
  ],
  YlOrBr: [
    [1.0, 1.0, 0.898],
    [0.996, 0.89, 0.569],
    [0.996, 0.6, 0.161],
    [0.8, 0.298, 0.008],
    [0.4, 0.145, 0.024],
  ],
};

export function sampleColormap(name: string, t: number): RGB {
  const stops = COLORMAP_STOPS[name] || COLORMAP_STOPS.terrain;
  const clamped = Math.max(0, Math.min(1, t));
  const scaled = clamped * (stops.length - 1);
  const idx = Math.floor(scaled);
  const frac = scaled - idx;
  if (idx >= stops.length - 1) {
    return stops[stops.length - 1];
  }
  const c0 = stops[idx];
  const c1 = stops[idx + 1];
  return [
    c0[0] + (c1[0] - c0[0]) * frac,
    c0[1] + (c1[1] - c0[1]) * frac,
    c0[2] + (c1[2] - c0[2]) * frac,
  ];
}

export function hexToRgb01(hex: string): RGB {
  const clean = hex.replace('#', '').trim();
  if (clean.length === 3) {
    const r = parseInt(clean[0] + clean[0], 16) / 255;
    const g = parseInt(clean[1] + clean[1], 16) / 255;
    const b = parseInt(clean[2] + clean[2], 16) / 255;
    return [r || 0, g || 0, b || 0];
  }
  const r = parseInt(clean.substring(0, 2), 16) / 255;
  const g = parseInt(clean.substring(2, 4), 16) / 255;
  const b = parseInt(clean.substring(4, 6), 16) / 255;
  return [isNaN(r) ? 0.5 : r, isNaN(g) ? 0.5 : g, isNaN(b) ? 0.5 : b];
}

export function rgb01ToHex(rgb: RGB | number[]): string {
  const r = Math.round(Math.max(0, Math.min(1, rgb[0] ?? 0.5)) * 255);
  const g = Math.round(Math.max(0, Math.min(1, rgb[1] ?? 0.5)) * 255);
  const b = Math.round(Math.max(0, Math.min(1, rgb[2] ?? 0.5)) * 255);
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

export function parseColorToRgb01(c?: [number, number, number] | string | null): RGB {
  if (!c) return [0.7, 0.75, 0.8];
  if (typeof c === 'string') {
    const named: Record<string, string> = {
      red: '#ef4444',
      white: '#f8fafc',
      blue: '#3b82f6',
      green: '#22c55e',
      yellow: '#facc15',
      black: '#0f172a',
      gray: '#94a3b8',
      grey: '#94a3b8',
    };
    return hexToRgb01(named[c.toLowerCase()] || c);
  }
  if (Array.isArray(c) && c.length >= 3) {
    if (c[0] > 1 || c[1] > 1 || c[2] > 1) {
      return [c[0] / 255, c[1] / 255, c[2] / 255];
    }
    return [c[0], c[1], c[2]];
  }
  return [0.7, 0.75, 0.8];
}
