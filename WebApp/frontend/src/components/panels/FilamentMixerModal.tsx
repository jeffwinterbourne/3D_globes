import React, { useEffect, useState } from 'react';
import { Check, Eye, Layers, Palette, Plus, RefreshCw, Sparkles, Trash2, X } from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';
import {
  DEFAULT_FILAMENT_SPOOLS,
  DEFAULT_STARTER_PROJECT,
  FilamentsConfig,
  FilamentSpool,
} from '../../types/globeProject';
import { hexToRgb01, rgb01ToHex } from '../../utils/colormaps';
import { toBackendGlobeProjectPayload } from '../../utils/projectNormalizer';

export interface PaletteSwatch {
  code: string;
  hex: string;
  rgb: [number, number, number];
  layers: string[];
  layer_colors: string[];
}

function buildClient35Palette(spools: FilamentSpool[]): PaletteSwatch[] {
  const s = spools.length >= 4 ? spools : DEFAULT_FILAMENT_SPOOLS.TERRAIN_4;
  // Generate all 35 4-layer combinations with replacement (multiset combinations of 4 from 4 = 35, or ordered top-4 stacks)
  const combos: number[][] = [];
  for (let a = 0; a < 4; a++) {
    for (let b = 0; b < 4; b++) {
      for (let c = 0; c < 4; c++) {
        for (let d = 0; d < 4; d++) {
          if (combos.length < 35 && (a === b || b === c || c === d)) {
            combos.push([a, b, c, d]);
          }
        }
      }
    }
  }
  while (combos.length < 35) {
    combos.push([combos.length % 4, (combos.length + 1) % 4, 0, 1]);
  }

  return combos.slice(0, 35).map((idxs, i) => {
    let r = 0.95,
      g = 0.95,
      b = 0.95;
    const layers: string[] = [];
    const layer_colors: string[] = [];
    for (const spIdx of idxs) {
      const sp = s[spIdx] || s[0];
      layers.push(sp.name);
      layer_colors.push(sp.hex);
      const [sr, sg, sb] = hexToRgb01(sp.hex);
      const alpha = Math.min(0.85, Math.max(0.22, 0.9 / Math.max(0.5, sp.td)));
      r = r * (1 - alpha) + sr * alpha;
      g = g * (1 - alpha) + sg * alpha;
      b = b * (1 - alpha) + sb * alpha;
    }
    const hex = rgb01ToHex([r, g, b]);
    return {
      code: `[${i.toString().padStart(2, '0')}]`,
      hex,
      rgb: [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)],
      layers,
      layer_colors,
    };
  });
}

export const FilamentMixerStudioContent: React.FC = () => {
  const { project, updateFilaments } = useProjectStore();
  const fil = project.filaments || DEFAULT_STARTER_PROJECT.filaments!;
  const spools = fil.spools || DEFAULT_FILAMENT_SPOOLS.TERRAIN_4;

  const [palette, setPalette] = useState<PaletteSwatch[]>(() => buildClient35Palette(spools));
  const [selectedSwatch, setSelectedSwatch] = useState<PaletteSwatch | null>(null);
  const [targetHex, setTargetHex] = useState<string>('#2b83ba');
  const [matchResult, setMatchResult] = useState<any>(null);
  const [mapPreview, setMapPreview] = useState<{
    map_image_data_url?: string;
    colorbar_image_data_url?: string;
  } | null>(null);
  const [loadingMap, setLoadingMap] = useState(false);

  const syncPalette = async (nextSpools: FilamentSpool[], presetName: string) => {
    const clientSwatches = buildClient35Palette(nextSpools);
    setPalette(clientSwatches);
    try {
      const res = await fetch('/api/filaments/palette', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          enabled: true,
          preset: presetName === 'CUSTOM' ? 'custom' : presetName,
          spools: nextSpools.map((s) => ({
            name: s.name,
            hex_color: s.hex,
            td: s.td,
            brand: 'Generic',
            material: 'PLA',
          })),
          base_layers: 2,
          top_layers: fil.total_layers || 4,
          layer_height: fil.layer_height || 0.08,
          quantize_preview: false,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.entries) && data.entries.length > 0) {
          setPalette(data.entries);
        }
      }
    } catch {
      // Keep client 35-swatch palette
    }
  };

  const updateSpoolsAndBands = (
    nextSpools: FilamentSpool[],
    presetName: FilamentsConfig['preset'] = 'CUSTOM'
  ) => {
    const swatches = buildClient35Palette(nextSpools);
    setPalette(swatches);
    const swatchMap = new Map(swatches.map((s) => [s.code, s.hex]));
    const updatedBands = (fil.bands || []).map((b) => ({
      ...b,
      hex: swatchMap.get(b.code) || b.hex,
    }));
    updateFilaments({
      preset: presetName,
      spools: nextSpools,
      bands: updatedBands,
    });
  };

  useEffect(() => {
    syncPalette(spools, fil.preset);
  }, [fil.preset, JSON.stringify(spools)]);

  const handleMatchColor = async () => {
    try {
      const res = await fetch('/api/filaments/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_hex: targetHex,
          filaments: {
            enabled: true,
            preset: fil.preset === 'CUSTOM' ? 'custom' : fil.preset,
            spools: spools.map((s) => ({
              name: s.name,
              hex_color: s.hex,
              td: s.td,
            })),
            top_layers: 4,
          },
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setMatchResult(data);
        return;
      }
    } catch {
      // Fallback local match
    }
    const [tr, tg, tb] = hexToRgb01(targetHex);
    const scored = palette
      .map((sw) => {
        const [sr, sg, sb] = hexToRgb01(sw.hex);
        const de =
          Math.sqrt((tr - sr) ** 2 + (tg - sg) ** 2 + (tb - sb) ** 2) * 100;
        return { ...sw, delta_e: Number(de.toFixed(1)) };
      })
      .sort((a, b) => a.delta_e - b.delta_e);
    setMatchResult({
      best_match: scored[0],
      delta_e: scored[0]?.delta_e,
      top_5: scored.slice(0, 5),
    });
  };

  const handleRender2DMap = async () => {
    setLoadingMap(true);
    try {
      const res = await fetch('/api/preview/map2d', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(toBackendGlobeProjectPayload(project)),
      });
      if (res.ok) {
        const data = await res.json();
        setMapPreview(data);
      }
    } catch {
      // Ignore offline error
    } finally {
      setLoadingMap(false);
    }
  };

  return (
    <div className="space-y-4 text-xs">
      {/* 1. Preset & 4 Spool Editors */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
        <div className="flex items-center justify-between gap-1">
          <div className="flex items-center gap-1.5 font-semibold text-slate-200 min-w-0">
            <Palette className="w-4 h-4 text-emerald-400 shrink-0" />
            <span className="text-xs truncate">4-Filament Optical Mixing</span>
          </div>
          <label className="flex items-center gap-1.5 cursor-pointer text-emerald-300 font-semibold text-[11px] shrink-0">
            <input
              type="checkbox"
              checked={fil.enabled}
              onChange={(e) => {
                const isEn = e.target.checked;
                const bands = (fil.bands?.length ?? 0) > 0 ? fil.bands : (DEFAULT_STARTER_PROJECT.filaments?.bands || []);
                updateFilaments({ enabled: isEn, bands });
              }}
              className="rounded border-slate-700 text-emerald-500 focus:ring-0 w-3.5 h-3.5"
            />
            <span>Active on Globe</span>
          </label>
        </div>

        <div className="flex flex-wrap gap-1">
          {(['TERRAIN_4', 'CMYKW', 'RBYKW', 'EARTH_TERRAIN', 'CUSTOM'] as const).map(
            (preset) => (
              <button
                key={preset}
                onClick={() => {
                  const nextSpools =
                    preset !== 'CUSTOM' && DEFAULT_FILAMENT_SPOOLS[preset]
                      ? DEFAULT_FILAMENT_SPOOLS[preset]
                      : spools;
                  updateSpoolsAndBands(nextSpools, preset);
                }}
                className={`px-2 py-0.5 rounded-md text-[11px] font-medium border transition ${
                  fil.preset === preset
                    ? 'bg-emerald-500/20 border-emerald-400 text-emerald-300 font-semibold'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                {preset}
              </button>
            )
          )}
        </div>

        <div className="grid grid-cols-1 gap-1.5">
          {spools.map((sp, idx) => (
            <div
              key={idx}
              className="flex items-center gap-2 p-1.5 rounded-lg bg-slate-950 border border-slate-800"
            >
              <input
                type="color"
                value={sp.hex}
                onChange={(e) => {
                  const next = [...spools];
                  next[idx] = { ...sp, hex: e.target.value };
                  updateSpoolsAndBands(next, 'CUSTOM');
                }}
                className="w-6 h-6 rounded cursor-pointer bg-transparent border-0 shrink-0"
              />
              <input
                type="text"
                value={sp.name}
                onChange={(e) => {
                  const next = [...spools];
                  next[idx] = { ...sp, name: e.target.value };
                  updateSpoolsAndBands(next, 'CUSTOM');
                }}
                className="flex-1 min-w-0 bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-slate-100 text-[11px]"
              />
              <div className="flex items-center gap-1 shrink-0">
                <span className="text-[10px] text-slate-400 font-mono">TD:</span>
                <input
                  type="number"
                  step="0.2"
                  min={0.5}
                  max={12}
                  value={sp.td}
                  onChange={(e) => {
                    const next = [...spools];
                    next[idx] = { ...sp, td: Number(e.target.value) };
                    updateSpoolsAndBands(next, 'CUSTOM');
                  }}
                  className="w-12 bg-slate-900 border border-slate-700 rounded px-1 py-0.5 font-mono text-sky-300 text-[11px]"
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 2. Interactive 35-Swatch Optical Palette Grid ([00] - [34]) */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-slate-200">
            35-Swatch Optical Mixing Palette ([00]–[34])
          </span>
          <span className="text-[10px] text-slate-400">
            Click any swatch to inspect 4-layer stack order
          </span>
        </div>

        <div className="grid grid-cols-7 gap-1.5">
          {palette.slice(0, 35).map((sw) => (
            <button
              key={sw.code}
              onClick={() => setSelectedSwatch(sw)}
              style={{ backgroundColor: sw.hex }}
              className={`h-9 rounded-lg border flex flex-col items-center justify-center shadow transition ${
                selectedSwatch?.code === sw.code
                  ? 'ring-2 ring-white border-white scale-105'
                  : 'border-slate-700/80 hover:scale-105'
              }`}
            >
              <span className="px-1 rounded bg-slate-950/75 text-[10px] font-mono text-white">
                {sw.code}
              </span>
            </button>
          ))}
        </div>

        {selectedSwatch && (
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div
                className="w-8 h-8 rounded-lg border border-slate-600"
                style={{ backgroundColor: selectedSwatch.hex }}
              />
              <div>
                <div className="font-mono font-bold text-sky-300">
                  {selectedSwatch.code} — {selectedSwatch.hex}
                </div>
                <div className="text-[11px] text-slate-400">
                  4-Layer Stack: {(selectedSwatch.layers || []).join(' → ')}
                </div>
              </div>
            </div>
            <div className="flex gap-1">
              {(selectedSwatch.layer_colors || []).map((lc, i) => (
                <div
                  key={i}
                  title={`Layer ${i + 1}`}
                  style={{ backgroundColor: lc }}
                  className="w-4 h-6 rounded border border-slate-700"
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 3. CIE Delta-E Color Matcher */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
        <div className="font-semibold text-slate-200 flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          <span>CIE ΔE Optical Color Matcher (/api/filaments/match)</span>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="color"
            value={targetHex}
            onChange={(e) => setTargetHex(e.target.value)}
            className="w-8 h-8 rounded cursor-pointer bg-transparent"
          />
          <input
            type="text"
            value={targetHex}
            onChange={(e) => setTargetHex(e.target.value)}
            className="w-28 bg-slate-950 border border-slate-700 rounded px-2 py-1.5 font-mono text-slate-100"
          />
          <button
            onClick={handleMatchColor}
            className="px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold"
          >
            Find Closest Optical Mix
          </button>
        </div>

        {matchResult?.best_match && (
          <div className="p-2 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div
                className="w-6 h-6 rounded border border-slate-600"
                style={{ backgroundColor: matchResult.best_match.hex }}
              />
              <span className="font-mono font-bold text-emerald-400">
                Best: {matchResult.best_match.code} ({matchResult.best_match.hex})
              </span>
            </div>
            <span className="font-mono text-amber-300">
              ΔE = {matchResult.delta_e}
            </span>
          </div>
        )}
      </div>

      {/* 4. Interactive Banded Colormap Builder */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-slate-200">
            Interactive Banded Hypsometric Colormap ({fil.bands.length} bands)
          </span>
          <button
            onClick={() => {
              const last = fil.bands[fil.bands.length - 1];
              const nextBands = [
                ...fil.bands,
                {
                  threshold: (last?.threshold ?? 0) + 1000,
                  code: palette[0]?.code || '[00]',
                  hex: palette[0]?.hex || '#ffffff',
                  label: 'New Band',
                },
              ];
              updateFilaments({ bands: nextBands, enabled: true });
            }}
            className="flex items-center gap-1 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-300"
          >
            <Plus className="w-3 h-3" />
            <span>Add Band</span>
          </button>
        </div>

        <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
          {fil.bands.map((band, idx) => (
            <div
              key={idx}
              className="grid grid-cols-12 items-center gap-1.5 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1"
            >
              <div
                className="col-span-1 w-5 h-5 rounded border border-slate-600"
                style={{ backgroundColor: band.hex }}
              />
              <input
                type="number"
                step={100}
                value={band.threshold}
                onChange={(e) => {
                  const next = [...fil.bands];
                  next[idx] = { ...band, threshold: Number(e.target.value) };
                  updateFilaments({ bands: next, enabled: true });
                }}
                className="col-span-3 bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 font-mono text-slate-100"
              />
              <select
                value={band.code}
                onChange={(e) => {
                  const found = palette.find((p) => p.code === e.target.value);
                  const next = [...fil.bands];
                  next[idx] = {
                    ...band,
                    code: e.target.value,
                    hex: found?.hex || band.hex,
                  };
                  updateFilaments({ bands: next, enabled: true });
                }}
                className="col-span-3 bg-slate-900 border border-slate-700 rounded px-1 py-0.5 font-mono text-sky-300"
              >
                {palette.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.code} ({p.hex})
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={band.label || ''}
                onChange={(e) => {
                  const next = [...fil.bands];
                  next[idx] = { ...band, label: e.target.value };
                  updateFilaments({ bands: next });
                }}
                className="col-span-4 bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-slate-300"
              />
              <button
                onClick={() => {
                  const next = fil.bands.filter((_, i) => i !== idx);
                  updateFilaments({ bands: next });
                }}
                className="col-span-1 text-slate-500 hover:text-rose-400 flex justify-center"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>

        {/* Live 2D Equirectangular Map + Colorbar Preview */}
        <div className="pt-2 border-t border-slate-800 space-y-2">
          <button
            onClick={handleRender2DMap}
            disabled={loadingMap}
            className="w-full py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sky-300 font-semibold flex items-center justify-center gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingMap ? 'animate-spin' : ''}`} />
            <span>
              {loadingMap
                ? 'Rendering 2D Map & Colorbar...'
                : 'Preview 2D Equirectangular Map & Banded Colorbar (/api/preview/map2d)'}
            </span>
          </button>

          {mapPreview?.map_image_data_url && (
            <div className="space-y-1.5 bg-slate-950 p-2 rounded-lg border border-slate-800">
              <img
                src={mapPreview.map_image_data_url}
                alt="2D Equirectangular Preview"
                className="w-full rounded border border-slate-800"
              />
              {mapPreview.colorbar_image_data_url && (
                <img
                  src={mapPreview.colorbar_image_data_url}
                  alt="Banded Colorbar"
                  className="w-full rounded"
                />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const FilamentMixerModal: React.FC = () => {
  const { isFilamentModalOpen, setFilamentModalOpen } = useProjectStore();
  if (!isFilamentModalOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-xl shadow-2xl w-full max-w-3xl max-h-[88vh] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Palette className="w-5 h-5 text-emerald-400" />
            <h2 className="text-base font-bold text-white">
              Full-Spectrum 4-Filament Optical Mixing & Banded Colormap Studio
            </h2>
          </div>
          <button
            onClick={() => setFilamentModalOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          <FilamentMixerStudioContent />
        </div>
      </div>
    </div>
  );
};
