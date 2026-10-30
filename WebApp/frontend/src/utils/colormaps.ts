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
  inferno: [
    [0.0, 0.0, 0.015],
    [0.106, 0.047, 0.255],
    [0.29, 0.047, 0.42],
    [0.47, 0.11, 0.427],
    [0.647, 0.173, 0.376],
    [0.812, 0.267, 0.275],
    [0.93, 0.412, 0.145],
    [0.984, 0.608, 0.024],
    [0.969, 0.82, 0.24],
    [0.988, 1.0, 0.643],
  ],
  cividis: [
    [0.0, 0.125, 0.302],
    [0.122, 0.216, 0.392],
    [0.251, 0.31, 0.463],
    [0.373, 0.408, 0.522],
    [0.49, 0.51, 0.576],
    [0.608, 0.627, 0.616],
    [0.733, 0.741, 0.639],
    [0.867, 0.871, 0.639],
    [1.0, 0.918, 0.275],
  ],
  turbo: [
    [0.19, 0.07, 0.23],
    [0.27, 0.38, 0.85],
    [0.21, 0.67, 0.98],
    [0.1, 0.89, 0.71],
    [0.45, 0.99, 0.37],
    [0.78, 0.94, 0.2],
    [0.98, 0.73, 0.22],
    [0.96, 0.42, 0.1],
    [0.79, 0.17, 0.02],
    [0.48, 0.02, 0.01],
  ],
  coolwarm: [
    [0.23, 0.299, 0.754],
    [0.554, 0.691, 0.996],
    [0.865, 0.865, 0.865],
    [0.957, 0.603, 0.482],
    [0.706, 0.016, 0.15],
  ],
  seismic: [
    [0.0, 0.0, 0.3],
    [0.0, 0.0, 1.0],
    [1.0, 1.0, 1.0],
    [1.0, 0.0, 0.0],
    [0.3, 0.0, 0.0],
  ],
  gist_earth: [
    [0.0, 0.0, 0.0],
    [0.106, 0.22, 0.369],
    [0.157, 0.478, 0.427],
    [0.259, 0.624, 0.275],
    [0.592, 0.71, 0.243],
    [0.839, 0.702, 0.286],
    [0.659, 0.447, 0.235],
    [1.0, 1.0, 1.0],
  ],
  copper: [
    [0.0, 0.0, 0.0],
    [0.239, 0.149, 0.094],
    [0.478, 0.302, 0.192],
    [0.722, 0.451, 0.29],
    [0.961, 0.604, 0.388],
    [1.0, 0.761, 0.522],
  ],
  jet: [
    [0.0, 0.0, 0.5],
    [0.0, 0.0, 1.0],
    [0.0, 0.5, 1.0],
    [0.0, 1.0, 1.0],
    [0.5, 1.0, 0.5],
    [1.0, 1.0, 0.0],
    [1.0, 0.5, 0.0],
    [1.0, 0.0, 0.0],
    [0.5, 0.0, 0.0],
  ],
  Spectral: [
    [0.62, 0.0, 0.259],
    [0.835, 0.243, 0.31],
    [0.957, 0.427, 0.263],
    [0.996, 0.682, 0.38],
    [0.996, 0.878, 0.545],
    [1.0, 1.0, 0.749],
    [0.902, 0.961, 0.596],
    [0.671, 0.867, 0.643],
    [0.4, 0.761, 0.647],
    [0.196, 0.533, 0.741],
    [0.369, 0.31, 0.635],
  ],
  ocean: [
    [0.0, 0.0, 0.0],
    [0.0, 0.122, 0.247],
    [0.0, 0.373, 0.451],
    [0.039, 0.576, 0.588],
    [0.58, 0.824, 0.741],
    [0.914, 0.847, 0.651],
    [0.933, 0.608, 0.0],
    [1.0, 1.0, 1.0],
  ],
  bone: [
    [0.0, 0.0, 0.0],
    [0.122, 0.145, 0.196],
    [0.243, 0.294, 0.38],
    [0.384, 0.447, 0.553],
    [0.553, 0.62, 0.71],
    [0.729, 0.82, 0.871],
    [1.0, 1.0, 1.0],
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
  none: [
    [0.85, 0.88, 0.9],
    [0.85, 0.88, 0.9],
  ],
};

export interface ColormapDefinition {
  id: string;
  name: string;
  category: 'sequential' | 'diverging' | 'earth' | 'solid';
  gradientCss: string;
}

export const BUILTIN_COLORMAPS: ColormapDefinition[] = [
  {
    id: 'terrain',
    name: 'Terrain (Earth Relief / Bathymetry)',
    category: 'earth',
    gradientCss:
      'linear-gradient(to right, #333399 0%, #0096fa 20%, #00c76b 35%, #8ce370 50%, #fcf096 65%, #a37d5c 80%, #ffffff 100%)',
  },
  {
    id: 'viridis',
    name: 'Viridis (Scientific Standard)',
    category: 'sequential',
    gradientCss:
      'linear-gradient(to right, #440154, #482878, #3e4a89, #31688e, #26828e, #1f9e89, #35b779, #6ece58, #b5de2b, #fde725)',
  },
  {
    id: 'plasma',
    name: 'Plasma (Vibrant Warm)',
    category: 'sequential',
    gradientCss:
      'linear-gradient(to right, #0d0887, #46039f, #7201a8, #9c179e, #bd3786, #d8576b, #ed7953, #fb9f3a, #fdca26, #f0f921)',
  },
  {
    id: 'inferno',
    name: 'Inferno (Black-Red-Yellow)',
    category: 'sequential',
    gradientCss:
      'linear-gradient(to right, #000004, #1b0c41, #4a0c6b, #781c6d, #a52c60, #cf4446, #ed6925, #fb9b06, #f7d13d, #fcffa4)',
  },
  {
    id: 'magma',
    name: 'Magma (Dark Purple to Pale Yellow)',
    category: 'sequential',
    gradientCss:
      'linear-gradient(to right, #000004, #180f3d, #440f76, #721f81, #9e2f7f, #cd4071, #f1605d, #fd9668, #feca8d, #fcfdbf)',
  },
  {
    id: 'cividis',
    name: 'Cividis (Colorblind Friendly)',
    category: 'sequential',
    gradientCss:
      'linear-gradient(to right, #00204d, #1f3764, #404f76, #5f6885, #7d8293, #9ba09d, #bbbda3, #dddea3, #ffea46)',
  },
  {
    id: 'turbo',
    name: 'Turbo (High Contrast Rainbow)',
    category: 'sequential',
    gradientCss:
      'linear-gradient(to right, #30123b, #4662d8, #35abfb, #1ae4b6, #72fe5e, #c8ef34, #faba39, #f66a1a, #cb2b04, #7a0403)',
  },
  {
    id: 'coolwarm',
    name: 'Coolwarm (Diverging Blue-Red)',
    category: 'diverging',
    gradientCss:
      'linear-gradient(to right, #3b4cc0, #688aef, #99baff, #c9d8ef, #edd1c2, #f7a889, #e26952, #b40426)',
  },
  {
    id: 'seismic',
    name: 'Seismic (Diverging Navy-White-Red)',
    category: 'diverging',
    gradientCss: 'linear-gradient(to right, #00004c, #0000ff, #ffffff, #ff0000, #4c0000)',
  },
  {
    id: 'gist_earth',
    name: 'Gist Earth (Classic Earth & Paleo)',
    category: 'earth',
    gradientCss:
      'linear-gradient(to right, #000000, #1b385e, #287a6d, #429f46, #97b53e, #d6b349, #a8723c, #ffffff)',
  },
  {
    id: 'copper',
    name: 'Copper (Warm Bronze & Metallic)',
    category: 'sequential',
    gradientCss:
      'linear-gradient(to right, #000000, #3d2618, #7a4d31, #b8734a, #f59a63, #ffc285)',
  },
  {
    id: 'jet',
    name: 'Jet (Classic Rainbow)',
    category: 'sequential',
    gradientCss: 'linear-gradient(to right, #00007f, #0000ff, #00ffff, #ffff00, #ff0000, #7f0000)',
  },
  {
    id: 'Spectral',
    name: 'Spectral (Diverging Multi-Hue)',
    category: 'diverging',
    gradientCss:
      'linear-gradient(to right, #9e0142, #d53e4f, #f46d43, #fdae61, #fee08b, #ffffbf, #e6f598, #abdda4, #66c2a5, #3288bd, #5e4fa2)',
  },
  {
    id: 'ocean',
    name: 'Ocean (Deep Marine)',
    category: 'earth',
    gradientCss:
      'linear-gradient(to right, #000000, #001f3f, #005f73, #0a9396, #94d2bd, #e9d8a6, #ee9b00, #ffffff)',
  },
  {
    id: 'bone',
    name: 'Bone (Cool Monochrome)',
    category: 'sequential',
    gradientCss:
      'linear-gradient(to right, #000000, #1f2532, #3e4b61, #62728d, #8d9eb5, #bad1de, #ffffff)',
  },
  {
    id: 'none',
    name: 'None (Constant Neutral Solid)',
    category: 'solid',
    gradientCss: 'linear-gradient(to right, #cbd5e1, #cbd5e1)',
  },
];

export function getColormapCssGradient(name: string): string {
  const match = BUILTIN_COLORMAPS.find((c) => c.id.toLowerCase() === (name || '').toLowerCase());
  if (match) return match.gradientCss;
  const stops = COLORMAP_STOPS[name] || COLORMAP_STOPS.terrain;
  const parts = stops.map((c, i) => {
    const pct = Math.round((i / (stops.length - 1)) * 100);
    return `${rgb01ToHex(c)} ${pct}%`;
  });
  return `linear-gradient(to right, ${parts.join(', ')})`;
}

export function sampleColormap(name: string, t: number): RGB {
  if ((name || '').toLowerCase() === 'none') {
    return [0.85, 0.88, 0.9];
  }
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
      none: '#cbd5e1',
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
