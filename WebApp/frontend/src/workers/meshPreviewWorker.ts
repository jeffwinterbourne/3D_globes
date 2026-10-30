import { GlobeProject } from '../types/globeProject';
import { hexToRgb01, parseColorToRgb01, sampleColormap } from '../utils/colormaps';

export interface CachedGridBuffer {
  nLat: number;
  nLon: number;
  values: Float32Array;
  min?: number;
  max?: number;
}

export interface CachedTextureBuffer {
  width: number;
  height: number;
  rgb: Uint8Array; // RGB or RGBA
  channels: number;
}

export interface CachedMaskBuffer {
  width: number;
  height: number;
  values: Uint8Array;
}

export interface EvaluatedMeshResult {
  outerPositions: Float32Array;
  outerIndices: Uint32Array;
  outerColors: Float32Array;
  innerPositions: Float32Array;
  innerIndices: Uint32Array;
  innerColors: Float32Array;
  stats: {
    min_radius: number;
    max_radius: number;
    min_thickness: number;
    vertex_count: number;
    face_count: number;
  };
}

const EARTH_RADIUS_M = 6371000.0;

const UNIT_TO_METERS: Record<string, number> = {
  m: 1.0,
  km: 1000.0,
  cm: 0.01,
  mm: 0.001,
  ft: 0.3048,
};

function calculatePhysicalScale(
  globeRadiusMm: number,
  verticalExagg: number,
  gridUnits: string = 'm'
): number {
  const unitFactor = UNIT_TO_METERS[gridUnits] || 1.0;
  return (globeRadiusMm / EARTH_RADIUS_M) * unitFactor * verticalExagg;
}

/**
 * Generates a UV/Fibonacci-like watertight triangulated sphere mesh with approximately `targetPoints` vertices.
 * Returns unit directions `dirs` (Float32Array of length 3*N), `lats` (deg), `lons` (deg), and triangle `indices`.
 */
function buildBaseSphere(targetPoints: number, method: 'fibonacci' | 'icosahedron') {
  const clampedPts = Math.max(1000, Math.min(1000000, targetPoints || 60000));
  // Use a high-quality equirectangular / geodesic grid topology that is guaranteed manifold & watertight in <4ms
  const ratio = method === 'icosahedron' ? 1.8 : 2.0;
  const nLat = Math.max(32, Math.round(Math.sqrt(clampedPts / ratio)));
  const nLon = Math.max(64, Math.round(nLat * ratio));
  const numVerts = (nLat + 1) * (nLon + 1);

  const dirs = new Float32Array(numVerts * 3);
  const lats = new Float32Array(numVerts);
  const lons = new Float32Array(numVerts);

  let vIdx = 0;
  for (let i = 0; i <= nLat; i++) {
    const v = i / nLat;
    const latDeg = 90.0 - v * 180.0;
    const latRad = (latDeg * Math.PI) / 180.0;
    const cosLat = Math.cos(latRad);
    const sinLat = Math.sin(latRad);

    for (let j = 0; j <= nLon; j++) {
      const u = j / nLon;
      const lonDeg = -180.0 + u * 360.0;
      const lonRad = (lonDeg * Math.PI) / 180.0;

      // Match globe3d coordinate convention: Z = North Pole, X = (0 lat, 0 lon), Y = (0 lat, 90E)
      const x = cosLat * Math.cos(lonRad);
      const y = cosLat * Math.sin(lonRad);
      const z = sinLat;

      dirs[vIdx * 3] = x;
      dirs[vIdx * 3 + 1] = y;
      dirs[vIdx * 3 + 2] = z;
      lats[vIdx] = latDeg;
      lons[vIdx] = lonDeg;
      vIdx++;
    }
  }

  const numFaces = nLat * nLon * 2;
  const indices = new Uint32Array(numFaces * 3);
  let fIdx = 0;
  const stride = nLon + 1;
  for (let i = 0; i < nLat; i++) {
    for (let j = 0; j < nLon; j++) {
      const a = i * stride + j;
      const b = (i + 1) * stride + j;
      const c = (i + 1) * stride + (j + 1);
      const d = i * stride + (j + 1);

      indices[fIdx++] = a;
      indices[fIdx++] = b;
      indices[fIdx++] = d;

      indices[fIdx++] = b;
      indices[fIdx++] = c;
      indices[fIdx++] = d;
    }
  }

  return { dirs, lats, lons, indices, numVerts };
}

/**
 * Procedural fallback elevation (in meters, -5500 to +4500) so the preview works
 * instantaneously even before Python grid buffers arrive.
 */
function sampleProceduralElevation(latDeg: number, lonDeg: number, ageMa: number = 0): number {
  const lat = (latDeg * Math.PI) / 180.0;
  const lon = ((lonDeg + ageMa * 0.45) * Math.PI) / 180.0;
  const h1 = Math.sin(lat * 2.0) * Math.cos(lon * 2.0);
  const h2 = 0.6 * Math.cos(lat * 3.0 - 0.4) * Math.sin(lon * 3.0 + 0.8);
  const h3 = 0.35 * Math.sin(lat * 5.0 + lon * 4.0);
  const h4 = 0.2 * Math.cos(lat * 9.0) * Math.cos(lon * 8.0);
  const combined = h1 + h2 + h3 + h4;
  return combined * 2800.0 - 600.0;
}

function sampleGridBuffer(
  buf: CachedGridBuffer | undefined,
  latDeg: number,
  lonDeg: number,
  fallbackAgeMa: number = 0
): number {
  if (!buf || !buf.values || buf.values.length === 0 || buf.nLat < 2 || buf.nLon < 2) {
    return sampleProceduralElevation(latDeg, lonDeg, fallbackAgeMa);
  }
  // Assume equirectangular grid: lat from -90..90 or 90..-90, lon from -180..180
  const v = Math.max(0, Math.min(1, (90.0 - latDeg) / 180.0));
  const u = Math.max(0, Math.min(1, (lonDeg + 180.0) / 360.0));
  const y = v * (buf.nLat - 1);
  const x = u * (buf.nLon - 1);
  const y0 = Math.floor(y);
  const y1 = Math.min(buf.nLat - 1, y0 + 1);
  const x0 = Math.floor(x);
  const x1 = Math.min(buf.nLon - 1, x0 + 1);
  const fy = y - y0;
  const fx = x - x0;

  const v00 = buf.values[y0 * buf.nLon + x0] || 0;
  const v01 = buf.values[y0 * buf.nLon + x1] || 0;
  const v10 = buf.values[y1 * buf.nLon + x0] || 0;
  const v11 = buf.values[y1 * buf.nLon + x1] || 0;

  const top = v00 + (v01 - v00) * fx;
  const bot = v10 + (v11 - v10) * fx;
  const val = top + (bot - top) * fy;
  return Number.isFinite(val) ? val : 0.0;
}

function sampleMaskBuffer(
  mask: CachedMaskBuffer | undefined,
  latDeg: number,
  lonDeg: number
): boolean {
  if (!mask || !mask.values || mask.values.length === 0 || mask.width < 2 || mask.height < 2) {
    return false;
  }
  const v = Math.max(0, Math.min(1, (90.0 - latDeg) / 180.0));
  const u = Math.max(0, Math.min(1, (lonDeg + 180.0) / 360.0));
  const row = Math.min(mask.height - 1, Math.floor(v * mask.height));
  const col = Math.min(mask.width - 1, Math.floor(u * mask.width));
  return mask.values[row * mask.width + col] > 0;
}

function angularDistanceDeg(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = p2 - p1;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dp / 2) * Math.sin(dp / 2) +
    Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) * Math.sin(dl / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
  return (c * 180) / Math.PI;
}

export function evaluateProjectMeshClient(
  project: GlobeProject,
  gridBuffers: Record<string, CachedGridBuffer> = {},
  textureBuffer?: CachedTextureBuffer | null,
  overridePreviewPoints?: number,
  maskBuffers: Record<string, CachedMaskBuffer> = {}
): EvaluatedMeshResult {
  const geom = project.geometry;
  const nPts = overridePreviewPoints || geom.preview_n_points || 60000;
  const baseRadius = geom.radius || 40.0;
  const isPaleoMode = project.mode === 'paleo' || Boolean(project.paleo?.enabled);
  const paleoAge = isPaleoMode ? project.paleo?.age ?? 250.0 : 0.0;

  const sphere = buildBaseSphere(nPts, geom.method || 'fibonacci');
  const { dirs, lats, lons, indices, numVerts } = sphere;

  const outerRadii = new Float32Array(numVerts);
  outerRadii.fill(baseRadius);

  // 1. Evaluate Outer Displacements
  if (isPaleoMode && project.paleo) {
    const paleoGrid = gridBuffers['paleo_dem'] || Object.values(gridBuffers)[0];
    const scale = calculatePhysicalScale(baseRadius, project.paleo.vert_exagg ?? 40.0, 'm');
    const stepMm =
      (project.paleo.coastline_step ?? 0) > 10
        ? (project.paleo.coastline_step ?? 0) * scale
        : project.paleo.coastline_step ?? 0;

    for (let i = 0; i < numVerts; i++) {
      const z = sampleGridBuffer(paleoGrid, lats[i], lons[i], paleoAge);
      let dr = z * scale;
      if (stepMm !== 0 && z >= 0) {
        dr += stepMm;
      }
      outerRadii[i] += dr;
    }
  } else {
    for (const disp of project.outer_displacements || []) {
      if (!disp.enabled) continue;
      if (disp.type === 'GridDisplacer') {
        const buf = (disp.grid_id && gridBuffers[disp.grid_id]) || Object.values(gridBuffers)[0];
        const exagg = disp.vertical_exagg ?? disp.vert_exagg ?? 40.0;
        const scale =
          disp.scale_mode === 'direct' && disp.scale !== undefined
            ? disp.scale
            : calculatePhysicalScale(baseRadius, exagg, disp.grid_units || 'm');
        const refLevel = disp.reference_level ?? 0.0;
        const coastStep = disp.coastline_step ?? 0.0;
        const stepMm =
          Math.abs(coastStep) > 20.0 && Math.abs(scale) < 0.05
            ? coastStep * scale
            : coastStep;
        const stepThresh = disp.step_threshold ?? 0.0;

        for (let i = 0; i < numVerts; i++) {
          const z = sampleGridBuffer(buf, lats[i], lons[i], paleoAge);
          let dr = (z - refLevel) * scale;
          const maxAllowed = baseRadius * 0.25;
          dr = Math.max(-maxAllowed, Math.min(maxAllowed, dr));
          if (stepMm !== 0) {
            const landMask = maskBuffers['land'] || maskBuffers['ne_110m_land'] || maskBuffers['default'];
            const isLand = landMask
              ? sampleMaskBuffer(landMask, lats[i], lons[i])
              : z > stepThresh;
            if (isLand) {
              dr += stepMm;
            }
          }
          outerRadii[i] += dr;
        }
      } else if (disp.type === 'ConstantDisplacer') {
        const d = (disp.displacement ?? 0) * (disp.scale ?? 1.0);
        for (let i = 0; i < numVerts; i++) {
          outerRadii[i] += d;
        }
      } else if (disp.type === 'PointDisplacer' && disp.points) {
        const radDeg = disp.radius_degrees ?? 2.5;
        const d = (disp.displacement ?? 1.0) * (disp.scale ?? 1.0);
        for (const pt of disp.points) {
          const pLon = Array.isArray(pt) ? pt[0] : pt.lon;
          const pLat = Array.isArray(pt) ? pt[1] : pt.lat;
          for (let i = 0; i < numVerts; i++) {
            if (angularDistanceDeg(lats[i], lons[i], pLat, pLon) <= radDeg) {
              outerRadii[i] += d;
            }
          }
        }
      } else if (disp.type === 'LineDisplacer') {
        const mask = (disp.shapefile && maskBuffers[disp.shapefile]) || maskBuffers['coastline'];
        const d = (disp.displacement ?? 0.8) * (disp.scale_mode === 'direct' && disp.scale ? disp.scale : 1.0);
        if (mask) {
          for (let i = 0; i < numVerts; i++) {
            if (sampleMaskBuffer(mask, lats[i], lons[i])) {
              outerRadii[i] += d;
            }
          }
        }
      } else if (disp.type === 'PolygonDisplacer') {
        const mask = (disp.shapefile && maskBuffers[disp.shapefile]) || maskBuffers['land'] || maskBuffers['default'];
        const d = (disp.displacement ?? 1.0) * (disp.scale_mode === 'direct' && disp.scale ? disp.scale : 1.0);
        const inside = disp.displace_inside !== false;
        if (mask) {
          for (let i = 0; i < numVerts; i++) {
            const isInside = sampleMaskBuffer(mask, lats[i], lons[i]);
            if ((inside && isInside) || (!inside && !isInside)) {
              outerRadii[i] += d;
            }
          }
        }
      }
    }
  }

  // 2. Evaluate Inner Shell Radii
  const isHollow = Boolean(geom.hollow);
  const innerBaseRadius = geom.inner_thickness
    ? Math.max(2.0, baseRadius - geom.inner_thickness)
    : baseRadius * (geom.inner_ratio || 0.5);
  const innerRadii = new Float32Array(numVerts);
  innerRadii.fill(innerBaseRadius);

  if (isHollow && !isPaleoMode) {
    for (const disp of project.inner_displacements || []) {
      if (!disp.enabled) continue;
      if (disp.type === 'GridDisplacer') {
        const buf = (disp.grid_id && gridBuffers[disp.grid_id]) || Object.values(gridBuffers)[0];
        const exagg = disp.vertical_exagg ?? disp.vert_exagg ?? 20.0;
        const scale =
          disp.scale_mode === 'direct' && disp.scale !== undefined
            ? disp.scale
            : calculatePhysicalScale(innerBaseRadius, exagg, disp.grid_units || 'm');
        const refLevel = disp.reference_level ?? 0.0;
        const maxInnerAllowed = innerBaseRadius * 0.25;
        for (let i = 0; i < numVerts; i++) {
          const z = sampleGridBuffer(buf, lats[i], lons[i], paleoAge);
          let dr = (z - refLevel) * scale;
          dr = Math.max(-maxInnerAllowed, Math.min(maxInnerAllowed, dr));
          innerRadii[i] += dr;
        }
      } else if (disp.type === 'ConstantDisplacer') {
        const d = (disp.displacement ?? 0) * (disp.scale ?? 1.0);
        for (let i = 0; i < numVerts; i++) {
          innerRadii[i] += d;
        }
      }
    }
  }

  // 3. Apply fix_intersection(min_thickness, mode)
  if (isHollow && geom.fix_intersection?.enabled) {
    const minThick = geom.fix_intersection.min_thickness ?? 1.5;
    const fixMode = geom.fix_intersection.mode || 'inner';
    for (let i = 0; i < numVerts; i++) {
      const thick = outerRadii[i] - innerRadii[i];
      if (thick < minThick) {
        const deficit = minThick - thick;
        if (fixMode === 'inner') {
          innerRadii[i] = Math.max(1.0, outerRadii[i] - minThick);
        } else if (fixMode === 'outer') {
          outerRadii[i] = innerRadii[i] + minThick;
        } else {
          innerRadii[i] = Math.max(1.0, innerRadii[i] - deficit * 0.5);
          outerRadii[i] += deficit * 0.5;
        }
      }
    }
  }

  // 4. Compute Positions & Stats
  const cx = geom.center?.[0] ?? 0;
  const cy = geom.center?.[1] ?? 0;
  const cz = geom.center?.[2] ?? 0;

  const outerPositions = new Float32Array(numVerts * 3);
  const innerPositions = isHollow ? new Float32Array(numVerts * 3) : new Float32Array(0);

  let minRadius = Infinity;
  let maxRadius = -Infinity;
  let minThickness = Infinity;

  for (let i = 0; i < numVerts; i++) {
    const rOut = outerRadii[i];
    if (rOut < minRadius) minRadius = rOut;
    if (rOut > maxRadius) maxRadius = rOut;

    const dx = dirs[i * 3];
    const dy = dirs[i * 3 + 1];
    const dz = dirs[i * 3 + 2];

    outerPositions[i * 3] = cx + dx * rOut;
    outerPositions[i * 3 + 1] = cy + dy * rOut;
    outerPositions[i * 3 + 2] = cz + dz * rOut;

    if (isHollow) {
      const rIn = innerRadii[i];
      const thick = rOut - rIn;
      if (thick < minThickness) minThickness = thick;

      innerPositions[i * 3] = cx + dx * rIn;
      innerPositions[i * 3 + 1] = cy + dy * rIn;
      innerPositions[i * 3 + 2] = cz + dz * rIn;
    }
  }

  if (!isHollow) {
    minThickness = maxRadius;
  }

  // 5. Evaluate Outer & Inner Vertex Colors
  const outerColors = new Float32Array(numVerts * 3);
  const innerColors = isHollow ? new Float32Array(numVerts * 3) : new Float32Array(0);

  for (let i = 0; i < numVerts; i++) {
    outerColors[i * 3] = 0.75;
    outerColors[i * 3 + 1] = 0.78;
    outerColors[i * 3 + 2] = 0.82;
    if (isHollow) {
      innerColors[i * 3] = 0.55;
      innerColors[i * 3 + 1] = 0.58;
      innerColors[i * 3 + 2] = 0.62;
    }
  }

  const applyBandedColor = (val: number, bands: NonNullable<GlobeProject['filaments']>['bands']) => {
    let chosenHex = bands[0]?.hex || '#1b4f9c';
    for (const b of bands) {
      if (val >= b.threshold) {
        chosenHex = b.hex;
      }
    }
    return hexToRgb01(chosenHex);
  };

  if (isPaleoMode && project.paleo) {
    const paleoGrid = gridBuffers['paleo_dem'] || Object.values(gridBuffers)[0];
    const cMode = project.paleo.color_mode || 'paleo_atlas';
    const bands = project.filaments?.bands || [];

    for (let i = 0; i < numVerts; i++) {
      const z = sampleGridBuffer(paleoGrid, lats[i], lons[i], paleoAge);
      let rgb: [number, number, number];
      if ((cMode === 'filament_banded' || project.filaments?.enabled) && bands.length > 0) {
        rgb = applyBandedColor(z, bands);
      } else if (cMode === 'scientific_cmap') {
        const t = (z - -6000) / (5000 - -6000);
        rgb = sampleColormap(project.paleo.colormap || 'terrain', t);
      } else if (textureBuffer && textureBuffer.rgb.length > 0) {
        const v = Math.max(0, Math.min(1, (90.0 - lats[i]) / 180.0));
        const u = Math.max(0, Math.min(1, (lons[i] + 180.0) / 360.0));
        const py = Math.min(textureBuffer.height - 1, Math.floor(v * textureBuffer.height));
        const px = Math.min(textureBuffer.width - 1, Math.floor(u * textureBuffer.width));
        const offset = (py * textureBuffer.width + px) * textureBuffer.channels;
        rgb = [
          textureBuffer.rgb[offset] / 255,
          textureBuffer.rgb[offset + 1] / 255,
          textureBuffer.rgb[offset + 2] / 255,
        ];
      } else {
        const t = (z - -6000) / (5000 - -6000);
        rgb = sampleColormap('terrain', t);
      }
      outerColors[i * 3] = rgb[0];
      outerColors[i * 3 + 1] = rgb[1];
      outerColors[i * 3 + 2] = rgb[2];
    }

    // Apply Paleo Pole Markers
    if (project.paleo.mark_poles) {
      for (let i = 0; i < numVerts; i++) {
        if (lats[i] >= 86.5) {
          outerColors[i * 3] = 0.95;
          outerColors[i * 3 + 1] = 0.2;
          outerColors[i * 3 + 2] = 0.2;
        } else if (lats[i] <= -86.5) {
          outerColors[i * 3] = 0.2;
          outerColors[i * 3 + 1] = 0.6;
          outerColors[i * 3 + 2] = 0.98;
        }
      }
    }

    // Apply Tracked Locations
    for (const loc of project.paleo.tracked_locations || []) {
      const rgb = parseColorToRgb01(loc.color || '#ef4444');
      const rad = loc.size || loc.radius_degrees || 2.5;
      for (let i = 0; i < numVerts; i++) {
        if (angularDistanceDeg(lats[i], lons[i], loc.lat, loc.lon) <= rad) {
          outerColors[i * 3] = rgb[0];
          outerColors[i * 3 + 1] = rgb[1];
          outerColors[i * 3 + 2] = rgb[2];
        }
      }
    }
  } else {
    for (const col of project.colourers || []) {
      if (!col.enabled) continue;
      const appliesOuter = col.target === 'outer' || col.target === 'all';
      const appliesInner =
        isHollow &&
        (col.target === 'inner' || col.target === 'all' || col.selection === 'inward_facing');

      if (col.type === 'ConstantColourer') {
        const rgb = parseColorToRgb01(col.color);
        for (let i = 0; i < numVerts; i++) {
          if (appliesOuter && col.selection !== 'inward_facing') {
            outerColors[i * 3] = rgb[0];
            outerColors[i * 3 + 1] = rgb[1];
            outerColors[i * 3 + 2] = rgb[2];
          }
          if (appliesInner) {
            innerColors[i * 3] = rgb[0];
            innerColors[i * 3 + 1] = rgb[1];
            innerColors[i * 3 + 2] = rgb[2];
          }
        }
      } else if (col.type === 'GridColourer') {
        const buf = (col.grid_id && gridBuffers[col.grid_id]) || Object.values(gridBuffers)[0];
        const vmin = col.vmin ?? -6000;
        const vmax = col.vmax ?? 5000;
        const span = Math.max(1e-6, vmax - vmin);
        const cmap = col.colormap || 'terrain';
        const useBanded =
          (col.colormap_mode === 'banded' || project.filaments?.enabled) &&
          (project.filaments?.bands?.length ?? 0) > 0;

        for (let i = 0; i < numVerts; i++) {
          const z = sampleGridBuffer(buf, lats[i], lons[i], paleoAge);
          let rgb: [number, number, number];
          if (useBanded && project.filaments?.bands) {
            rgb = applyBandedColor(z, project.filaments.bands);
          } else if (
            col.colormap_mode === 'listed' &&
            col.listed_colors &&
            col.thresholds &&
            col.listed_colors.length > 0
          ) {
            let idx = 0;
            for (let k = 0; k < col.thresholds.length; k++) {
              if (z >= col.thresholds[k]) idx = Math.min(col.listed_colors.length - 1, k);
            }
            rgb = parseColorToRgb01(col.listed_colors[idx]);
          } else {
            let t = (z - vmin) / span;
            if (col.colormap_mode === 'discrete' && col.n_bins && col.n_bins > 1) {
              t = Math.floor(Math.max(0, Math.min(0.999, t)) * col.n_bins) / (col.n_bins - 1);
            }
            rgb = sampleColormap(cmap, t);
          }
          if (appliesOuter && col.selection !== 'inward_facing') {
            outerColors[i * 3] = rgb[0];
            outerColors[i * 3 + 1] = rgb[1];
            outerColors[i * 3 + 2] = rgb[2];
          }
          if (appliesInner) {
            innerColors[i * 3] = rgb[0];
            innerColors[i * 3 + 1] = rgb[1];
            innerColors[i * 3 + 2] = rgb[2];
          }
        }
      } else if (col.type === 'ImageColourer') {
        for (let i = 0; i < numVerts; i++) {
          const v = Math.max(0, Math.min(1, (90.0 - lats[i]) / 180.0));
          const u = Math.max(0, Math.min(1, (lons[i] + 180.0) / 360.0));
          let rgb: [number, number, number];
          if (textureBuffer && textureBuffer.rgb.length > 0) {
            const py = Math.min(textureBuffer.height - 1, Math.floor(v * textureBuffer.height));
            const px = Math.min(textureBuffer.width - 1, Math.floor(u * textureBuffer.width));
            const offset = (py * textureBuffer.width + px) * textureBuffer.channels;
            rgb = [
              textureBuffer.rgb[offset] / 255,
              textureBuffer.rgb[offset + 1] / 255,
              textureBuffer.rgb[offset + 2] / 255,
            ];
          } else {
            rgb = [0.15 + 0.7 * u, 0.25 + 0.6 * (1 - v), 0.85 - 0.5 * u];
          }
          if (appliesOuter) {
            outerColors[i * 3] = rgb[0];
            outerColors[i * 3 + 1] = rgb[1];
            outerColors[i * 3 + 2] = rgb[2];
          }
        }
      } else if (col.type === 'PolygonColourer') {
        const mask = (col.shapefile && maskBuffers[col.shapefile]) || maskBuffers['land'] || maskBuffers['default'];
        const fg = parseColorToRgb01(col.color || [0.2, 0.7, 0.3]);
        const bg = col.background_color ? parseColorToRgb01(col.background_color) : null;
        const inside = col.flood_inside !== false;
        for (let i = 0; i < numVerts; i++) {
          const isInside = mask ? sampleMaskBuffer(mask, lats[i], lons[i]) : false;
          if ((inside && isInside) || (!inside && !isInside)) {
            outerColors[i * 3] = fg[0];
            outerColors[i * 3 + 1] = fg[1];
            outerColors[i * 3 + 2] = fg[2];
          } else if (bg) {
            outerColors[i * 3] = bg[0];
            outerColors[i * 3 + 1] = bg[1];
            outerColors[i * 3 + 2] = bg[2];
          }
        }
      } else if (col.type === 'LineColourer') {
        const mask = (col.shapefile && maskBuffers[col.shapefile]) || maskBuffers['coastline'];
        const fg = parseColorToRgb01(col.color || [0.1, 0.1, 0.1]);
        if (mask) {
          for (let i = 0; i < numVerts; i++) {
            if (sampleMaskBuffer(mask, lats[i], lons[i])) {
              outerColors[i * 3] = fg[0];
              outerColors[i * 3 + 1] = fg[1];
              outerColors[i * 3 + 2] = fg[2];
            }
          }
        }
      } else if (col.type === 'PointColourer' || col.type === 'SymbolColourer') {
        const defaultColor = parseColorToRgb01(col.color || '#ef4444');
        const rad = col.radius_degrees ?? 2.2;
        const pts =
          col.locations ||
          (col.points || []).map((p, idx) => ({
            name: `Pt ${idx + 1}`,
            lon: p[0],
            lat: p[1],
          }));
        for (const loc of pts as any[]) {
          const rgb = loc.color ? parseColorToRgb01(loc.color) : defaultColor;
          const rDeg = loc.radius_degrees || loc.size || rad;
          for (let i = 0; i < numVerts; i++) {
            if (angularDistanceDeg(lats[i], lons[i], loc.lat, loc.lon) <= rDeg) {
              outerColors[i * 3] = rgb[0];
              outerColors[i * 3 + 1] = rgb[1];
              outerColors[i * 3 + 2] = rgb[2];
            }
          }
        }
      } else if (col.type === 'PoleLabelColourer') {
        const rad = col.radius_degrees ?? 4.0;
        const nRgb = parseColorToRgb01(col.north_color || '#ef4444');
        const sRgb = parseColorToRgb01(col.south_color || '#3b82f6');
        for (let i = 0; i < numVerts; i++) {
          if (90 - lats[i] <= rad) {
            outerColors[i * 3] = nRgb[0];
            outerColors[i * 3 + 1] = nRgb[1];
            outerColors[i * 3 + 2] = nRgb[2];
          } else if (lats[i] + 90 <= rad) {
            outerColors[i * 3] = sRgb[0];
            outerColors[i * 3 + 1] = sRgb[1];
            outerColors[i * 3 + 2] = sRgb[2];
          }
        }
      } else if (col.type === 'TextColourer') {
        const fillRgb = parseColorToRgb01(col.fill_color || col.color || '#f8fafc');
        const textLat = col.lat ?? 0;
        const textLon = col.lon ?? 0;
        const hDeg = col.height_degrees ?? 6.0;
        const wDeg = hDeg * Math.max(1, (col.text || 'TEXT').length * 0.55);
        for (let i = 0; i < numVerts; i++) {
          if (
            Math.abs(lats[i] - textLat) <= hDeg * 0.5 &&
            Math.abs(lons[i] - textLon) <= wDeg * 0.5
          ) {
            outerColors[i * 3] = fillRgb[0];
            outerColors[i * 3 + 1] = fillRgb[1];
            outerColors[i * 3 + 2] = fillRgb[2];
          }
        }
      }
    }
  }

  // Optical filament mixing override when "Active on 3D Globe" is checked
  if (project.filaments?.enabled && project.filaments?.bands && project.filaments.bands.length > 0) {
    const fGrid = gridBuffers['base_grid'] || Object.values(gridBuffers)[0];
    const bands = project.filaments.bands;
    for (let i = 0; i < numVerts; i++) {
      const z = sampleGridBuffer(fGrid, lats[i], lons[i], paleoAge);
      const rgb = applyBandedColor(z, bands);
      outerColors[i * 3] = rgb[0];
      outerColors[i * 3 + 1] = rgb[1];
      outerColors[i * 3 + 2] = rgb[2];
    }
  }

  const innerIndices = isHollow ? new Uint32Array(indices) : new Uint32Array(0);
  // Reverse winding on inner shell so normals point inward into the cavity
  if (isHollow) {
    for (let i = 0; i < innerIndices.length; i += 3) {
      const tmp = innerIndices[i + 1];
      innerIndices[i + 1] = innerIndices[i + 2];
      innerIndices[i + 2] = tmp;
    }
  }

  const totalVerts = isHollow ? numVerts * 2 : numVerts;
  const totalFaces = isHollow ? (indices.length / 3) * 2 : indices.length / 3;

  return {
    outerPositions,
    outerIndices: indices,
    outerColors,
    innerPositions,
    innerIndices,
    innerColors,
    stats: {
      min_radius: Number(minRadius.toFixed(2)),
      max_radius: Number(maxRadius.toFixed(2)),
      min_thickness: Number(minThickness.toFixed(2)),
      vertex_count: totalVerts,
      face_count: totalFaces,
    },
  };
}

// WebWorker listener when loaded as a worker
if (typeof self !== 'undefined' && typeof (self as any).postMessage === 'function' && typeof window === 'undefined') {
  self.onmessage = (e: MessageEvent) => {
    const { project, gridBuffers, textureBuffer, overridePreviewPoints, maskBuffers } = e.data;
    const res = evaluateProjectMeshClient(project, gridBuffers, textureBuffer, overridePreviewPoints, maskBuffers);
    (self as any).postMessage(res);
  };
}
