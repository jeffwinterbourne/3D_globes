import React, { useState } from 'react';
import { ArrowDown, ArrowUp, Palette, Plus, Sparkles, Trash2 } from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';
import { ColourerConfig } from '../../types/globeProject';
import { BUILTIN_COLORMAPS, getColormapCssGradient, parseColorToRgb01, rgb01ToHex } from '../../utils/colormaps';

export const ColourerStackPanel: React.FC = () => {
  const { project, setColourers, setFilamentModalOpen } = useProjectStore();
  const [newType, setNewType] = useState<ColourerConfig['type']>('GridColourer');

  const list = project.colourers || [];
  const gridIds = Object.keys(project.grids || {});

  const handleAdd = () => {
    const id = `col_${Date.now().toString().slice(-4)}`;
    const item: ColourerConfig = {
      id,
      enabled: true,
      target: 'outer',
      selection: 'outward_facing',
      blend_mode: 'replace',
      type: newType,
      grid_id: gridIds[0] || 'etopo_ds',
      colormap_mode: 'continuous',
      colormap: 'terrain',
      vmin: -6000,
      vmax: 5000,
      color: [0.2, 0.6, 0.9],
      radius_degrees: 3.0,
      width_degrees: 0.6,
      symbol: 'star',
      locations: [{ name: 'Oxford', lat: 51.75, lon: -1.25, color: '#ef4444', size: 2.5 }],
      north_color: '#ef4444',
      south_color: '#3b82f6',
      north_symbol: 'N',
      south_symbol: 'S',
      text: 'PANGAEA',
      lat: 0,
      lon: 0,
      height_degrees: 8,
      preprocessors: [],
    };
    setColourers([...list, item]);
  };

  const updateItem = (idx: number, patch: Partial<ColourerConfig>) => {
    const next = [...list];
    next[idx] = { ...next[idx], ...patch };
    setColourers(next);
  };

  const moveItem = (idx: number, dir: -1 | 1) => {
    const targetIdx = idx + dir;
    if (targetIdx < 0 || targetIdx >= list.length) return;
    const next = [...list];
    const [removed] = next.splice(idx, 1);
    next.splice(targetIdx, 0, removed);
    setColourers(next);
  };

  return (
    <div className="space-y-4 text-xs">
      {/* Add Colourer Layer Bar */}
      <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-slate-200 flex items-center gap-1.5">
            <Palette className="w-4 h-4 text-emerald-400" />
            <span>Colouring Layer Stack ({list.length})</span>
          </span>
          <button
            onClick={() => setFilamentModalOpen(true)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 font-semibold text-[11px]"
          >
            <Sparkles className="w-3 h-3" />
            <span>4-Filament Mixer</span>
          </button>
        </div>

        <div className="flex gap-1.5">
          <select
            value={newType}
            onChange={(e) => setNewType(e.target.value as ColourerConfig['type'])}
            className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-100"
          >
            <option value="GridColourer">GridColourer (Colormap / Banded)</option>
            <option value="ImageColourer">ImageColourer (Raster + Preprocessors)</option>
            <option value="ConstantColourer">ConstantColourer (Solid RGB)</option>
            <option value="PolygonColourer">PolygonColourer (Land / Shapefile)</option>
            <option value="LineColourer">LineColourer (Coastlines / Borders)</option>
            <option value="PointColourer">PointColourer (Capitals / Markers)</option>
            <option value="SymbolColourer">SymbolColourer (Gnomonic Vector Stamp)</option>
            <option value="PoleLabelColourer">PoleLabelColourer (N / S Polar Caps)</option>
            <option value="TextColourer">TextColourer (Spherical Typography)</option>
          </select>
          <button
            onClick={handleAdd}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add</span>
          </button>
        </div>
      </div>

      {/* Colourer Cards */}
      {list.map((col, idx) => {
        const hexVal = rgb01ToHex(parseColorToRgb01(col.color));
        return (
          <div
            key={col.id || idx}
            className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5"
          >
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={col.enabled}
                  onChange={(e) => updateItem(idx, { enabled: e.target.checked })}
                />
                <span className="font-bold text-emerald-300">{col.type}</span>
                <span className="text-[10px] font-mono text-slate-500">#{idx + 1}</span>
              </div>

              <div className="flex items-center gap-1">
                <button
                  onClick={() => moveItem(idx, -1)}
                  className="p-1 text-slate-400 hover:text-white"
                >
                  <ArrowUp className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => moveItem(idx, 1)}
                  className="p-1 text-slate-400 hover:text-white"
                >
                  <ArrowDown className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setColourers(list.filter((_, i) => i !== idx))}
                  className="p-1 text-slate-500 hover:text-rose-400"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Target, Selection & Blend Mode */}
            <div className="grid grid-cols-3 gap-1.5">
              <div>
                <label className="block text-[10px] text-slate-400 mb-0.5">Target Shell</label>
                <select
                  value={col.target || 'outer'}
                  onChange={(e) => updateItem(idx, { target: e.target.value as any })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-slate-200"
                >
                  <option value="outer">outer</option>
                  <option value="inner">inner</option>
                  <option value="all">all</option>
                </select>
              </div>
              <div>
                <label className="block text-[10px] text-slate-400 mb-0.5">Face Selection</label>
                <select
                  value={col.selection || 'all'}
                  onChange={(e) => updateItem(idx, { selection: e.target.value as any })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-slate-200"
                >
                  <option value="all">all</option>
                  <option value="outward_facing">outward_facing</option>
                  <option value="inward_facing">inward_facing</option>
                </select>
              </div>
              <div>
                <label className="block text-[10px] text-slate-400 mb-0.5">Blend Mode</label>
                <select
                  value={col.blend_mode || 'replace'}
                  onChange={(e) => updateItem(idx, { blend_mode: e.target.value as any })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-slate-200"
                >
                  <option value="replace">replace</option>
                  <option value="multiply">multiply</option>
                  <option value="overlay">overlay</option>
                </select>
              </div>
            </div>

            {/* Specific Controls by Type */}
            {col.type === 'GridColourer' && (
              <div className="space-y-2 pt-1">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1">Grid ID</label>
                    <select
                      value={col.grid_id || ''}
                      onChange={(e) => updateItem(idx, { grid_id: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1"
                    >
                      {gridIds.map((gid) => (
                        <option key={gid} value={gid}>
                          {gid}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Colormap Mode</label>
                    <select
                      value={col.colormap_mode || 'continuous'}
                      onChange={(e) =>
                        updateItem(idx, { colormap_mode: e.target.value as any })
                      }
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1"
                    >
                      <option value="continuous">Continuous</option>
                      <option value="discrete">Discrete Bins</option>
                      <option value="banded">4-Filament Banded</option>
                      <option value="listed">ListedColormap</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1">Colormap</label>
                    <select
                      value={col.colormap || 'terrain'}
                      onChange={(e) => updateItem(idx, { colormap: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                    >
                      {BUILTIN_COLORMAPS.map((cm) => (
                        <option key={cm.id} value={cm.id}>
                          {cm.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">vmin</label>
                    <input
                      type="number"
                      value={col.vmin ?? -6000}
                      onChange={(e) => updateItem(idx, { vmin: Number(e.target.value) })}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">vmax</label>
                    <input
                      type="number"
                      value={col.vmax ?? 5000}
                      onChange={(e) => updateItem(idx, { vmax: Number(e.target.value) })}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
                    />
                  </div>
                </div>

                {/* Visual Colorbar Gradient Preview */}
                <div className="p-2 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5">
                  <div className="flex items-center justify-between text-[10px] font-mono">
                    <span className="text-slate-400">
                      vmin: <strong className="text-sky-300">{col.vmin ?? -6000}</strong>
                    </span>
                    <span className="text-slate-200 font-semibold">{col.colormap || 'terrain'}</span>
                    <span className="text-slate-400">
                      vmax: <strong className="text-emerald-300">{col.vmax ?? 5000}</strong>
                    </span>
                  </div>
                  <div
                    className="h-4 w-full rounded-md border border-slate-700/80 shadow-inner"
                    style={{ background: getColormapCssGradient(col.colormap || 'terrain') }}
                    title={`Active Colormap: ${col.colormap || 'terrain'}`}
                  />
                </div>
              </div>
            )}

            {col.type === 'ImageColourer' && (
              <div className="space-y-2 pt-1">
                <div>
                  <label className="block text-slate-400 mb-1">Image Source / Preset</label>
                  <select
                    value={
                      !col.image_path
                        ? 'paleo_raster'
                        : col.image_path.includes('world_topo')
                        ? 'world_topo'
                        : col.image_path.includes('coastline')
                        ? 'coastline_img'
                        : 'custom'
                    }
                    onChange={(e) => {
                      if (e.target.value === 'paleo_raster') {
                        updateItem(idx, { image_source: 'paleo_atlas', image_path: '' });
                      } else if (e.target.value === 'world_topo') {
                        updateItem(idx, { image_source: 'local', image_path: 'context/height_maps/world_topo.png' });
                      } else if (e.target.value === 'coastline_img') {
                        updateItem(idx, { image_source: 'local', image_path: 'context/height_maps/coastline.png' });
                      } else {
                        updateItem(idx, { image_source: 'local', image_path: col.image_path || '' });
                      }
                    }}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 mb-1.5"
                  >
                    <option value="paleo_raster">Scotese PaleoAtlas Active Epoch Texture</option>
                    <option value="world_topo">Earth Relief Texture (world_topo.png)</option>
                    <option value="coastline_img">Coastline Mask Texture (coastline.png)</option>
                    <option value="custom">Custom Image Path / Upload...</option>
                  </select>
                  {col.image_path && (
                    <input
                      type="text"
                      placeholder="Path to equirectangular image (.jpg / .png)..."
                      value={col.image_path || ''}
                      onChange={(e) => updateItem(idx, { image_path: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono text-[11px]"
                    />
                  )}
                </div>
                <div className="p-2 rounded bg-slate-950 border border-slate-800 space-y-1">
                  <div className="text-[11px] font-semibold text-slate-300">
                    Image Preprocessors (globe3d.image)
                  </div>
                  {[
                    { type: 'undo_hillshading', label: 'undo_hillshading (De-light relief)' },
                    { type: 'simplify_image_median', label: 'simplify_image_median' },
                    { type: 'simplify_image_bilateral', label: 'simplify_image_bilateral' },
                    { type: 'simplify_colors', label: 'simplify_colors (Palette Quantize)' },
                  ].map((pp) => {
                    const active = (col.preprocessors || []).some(
                      (p) => p.type === pp.type && p.enabled
                    );
                    return (
                      <label key={pp.type} className="flex items-center gap-2 text-slate-400">
                        <input
                          type="checkbox"
                          checked={active}
                          onChange={(e) => {
                            const others = (col.preprocessors || []).filter(
                              (p) => p.type !== pp.type
                            );
                            if (e.target.checked) {
                              others.push({ type: pp.type as any, enabled: true });
                            }
                            updateItem(idx, { preprocessors: others });
                          }}
                        />
                        <span>{pp.label}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}

            {col.type === 'PolygonColourer' && (
              <div className="space-y-2 pt-1 border-t border-slate-800/80">
                <div>
                  <label className="block text-slate-400 mb-1">Polygon Shapefile / Dataset</label>
                  <select
                    value={
                      !col.shapefile || col.shapefile === 'land' || col.shapefile === 'dataset:shapefiles.land'
                        ? 'land'
                        : col.shapefile === 'coastline' || col.shapefile === 'dataset:shapefiles.coastline'
                        ? 'coastline'
                        : 'custom'
                    }
                    onChange={(e) => {
                      if (e.target.value === 'land') updateItem(idx, { shapefile: 'land' });
                      else if (e.target.value === 'coastline') updateItem(idx, { shapefile: 'coastline' });
                      else updateItem(idx, { shapefile: col.shapefile || '' });
                    }}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 mb-1.5"
                  >
                    <option value="land">Natural Earth Land Polygons (1:110m Built-in)</option>
                    <option value="coastline">Natural Earth Coastlines (1:110m Built-in)</option>
                    <option value="custom">Custom Shapefile / GeoJSON Path...</option>
                  </select>
                  {col.shapefile && col.shapefile !== 'land' && col.shapefile !== 'coastline' && col.shapefile !== 'dataset:shapefiles.land' && col.shapefile !== 'dataset:shapefiles.coastline' && (
                    <input
                      type="text"
                      placeholder="Absolute or relative path to .shp / .geojson..."
                      value={col.shapefile}
                      onChange={(e) => updateItem(idx, { shapefile: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono text-[11px]"
                    />
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1">Flood Region</label>
                    <select
                      value={col.flood_inside !== false ? 'inside' : 'outside'}
                      onChange={(e) => updateItem(idx, { flood_inside: e.target.value === 'inside' })}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200"
                    >
                      <option value="inside">Inside Polygons (Land)</option>
                      <option value="outside">Outside Polygons (Oceans)</option>
                    </select>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="block text-slate-400 mb-1">Fill Color</span>
                      <input
                        type="color"
                        value={hexVal}
                        onChange={(e) => updateItem(idx, { color: e.target.value })}
                        className="w-10 h-7 rounded bg-slate-950 border border-slate-700 cursor-pointer"
                      />
                    </div>
                    <div>
                      <span className="block text-slate-400 mb-1">Background</span>
                      <input
                        type="color"
                        value={typeof col.background_color === 'string' ? col.background_color : '#1e3a8a'}
                        onChange={(e) => updateItem(idx, { background_color: e.target.value })}
                        className="w-10 h-7 rounded bg-slate-950 border border-slate-700 cursor-pointer"
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {col.type === 'LineColourer' && (
              <div className="space-y-2 pt-1 border-t border-slate-800/80">
                <div>
                  <label className="block text-slate-400 mb-1">Line Shapefile / Dataset</label>
                  <select
                    value={
                      !col.shapefile || col.shapefile === 'coastline' || col.shapefile === 'dataset:shapefiles.coastline'
                        ? 'coastline'
                        : col.shapefile === 'land' || col.shapefile === 'dataset:shapefiles.land'
                        ? 'land'
                        : 'custom'
                    }
                    onChange={(e) => {
                      if (e.target.value === 'coastline') updateItem(idx, { shapefile: 'coastline' });
                      else if (e.target.value === 'land') updateItem(idx, { shapefile: 'land' });
                      else updateItem(idx, { shapefile: col.shapefile || '' });
                    }}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 mb-1.5"
                  >
                    <option value="coastline">Natural Earth Coastlines (1:110m Built-in)</option>
                    <option value="land">Natural Earth Land Polygons (1:110m Built-in)</option>
                    <option value="custom">Custom Line Shapefile...</option>
                  </select>
                  {col.shapefile && col.shapefile !== 'coastline' && col.shapefile !== 'land' && col.shapefile !== 'dataset:shapefiles.coastline' && col.shapefile !== 'dataset:shapefiles.land' && (
                    <input
                      type="text"
                      placeholder="Absolute or relative path to .shp / .geojson..."
                      value={col.shapefile}
                      onChange={(e) => updateItem(idx, { shapefile: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono text-[11px]"
                    />
                  )}
                </div>
                <div className="grid grid-cols-2 gap-2 items-center">
                  <div>
                    <label className="block text-slate-400 mb-1">Line Width (°)</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0.1"
                      max="15"
                      value={col.width_degrees ?? 0.8}
                      onChange={(e) => updateItem(idx, { width_degrees: Number(e.target.value) })}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Line Color</span>
                    <input
                      type="color"
                      value={hexVal}
                      onChange={(e) => updateItem(idx, { color: e.target.value })}
                      className="w-10 h-7 rounded bg-slate-950 border border-slate-700 cursor-pointer"
                    />
                  </div>
                </div>
              </div>
            )}

            {(col.type === 'ConstantColourer' ||
              col.type === 'PointColourer' ||
              col.type === 'SymbolColourer') && (
              <div className="flex items-center justify-between pt-1">
                <span className="text-slate-400">Layer Color</span>
                <input
                  type="color"
                  value={hexVal}
                  onChange={(e) => updateItem(idx, { color: e.target.value })}
                  className="w-10 h-6 rounded bg-slate-950 border border-slate-700 cursor-pointer"
                />
              </div>
            )}

            {col.type === 'PoleLabelColourer' && (
              <div className="grid grid-cols-3 gap-2 pt-1">
                <div>
                  <label className="block text-slate-400 mb-1">Cap Radius (°)</label>
                  <input
                    type="number"
                    step="0.5"
                    value={col.radius_degrees ?? 4.5}
                    onChange={(e) =>
                      updateItem(idx, { radius_degrees: Number(e.target.value) })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">North Symbol</label>
                  <input
                    type="text"
                    value={col.north_symbol || 'N'}
                    onChange={(e) => updateItem(idx, { north_symbol: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">South Symbol</label>
                  <input
                    type="text"
                    value={col.south_symbol || 'S'}
                    onChange={(e) => updateItem(idx, { south_symbol: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1"
                  />
                </div>
              </div>
            )}

            {col.type === 'TextColourer' && (
              <div className="grid grid-cols-3 gap-2 pt-1">
                <div>
                  <label className="block text-slate-400 mb-1">Text Label</label>
                  <input
                    type="text"
                    value={col.text || 'EARTH'}
                    onChange={(e) => updateItem(idx, { text: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Lat / Lon (°)</label>
                  <div className="flex gap-1">
                    <input
                      type="number"
                      value={col.lat ?? 0}
                      onChange={(e) => updateItem(idx, { lat: Number(e.target.value) })}
                      className="w-1/2 bg-slate-950 border border-slate-700 rounded px-1 py-1"
                    />
                    <input
                      type="number"
                      value={col.lon ?? 0}
                      onChange={(e) => updateItem(idx, { lon: Number(e.target.value) })}
                      className="w-1/2 bg-slate-950 border border-slate-700 rounded px-1 py-1"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Height (°)</label>
                  <input
                    type="number"
                    value={col.height_degrees ?? 8}
                    onChange={(e) =>
                      updateItem(idx, { height_degrees: Number(e.target.value) })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1"
                  />
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
