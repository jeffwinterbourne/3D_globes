import React, { useState } from 'react';
import {
  Calculator,
  Database,
  FileSearch,
  FolderOpen,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
} from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';
import { GridSourceConfig, GridTransform } from '../../types/globeProject';

const ONLINE_DATASET_CATEGORIES: Record<
  string,
  { names: string[]; hasDepth?: boolean; hasLayer?: boolean; hasRes?: boolean }
> = {
  topography: {
    names: ['earth', 'etopo', 'gebco', 'mars', 'moon', 'venus', 'mercury'],
    hasRes: true,
  },
  tomography: { names: ['s40rts'], hasDepth: true },
  geoid: { names: ['egm2008'] },
  crust: { names: ['crust1'], hasLayer: true },
  lithosphere: { names: ['thickness'], hasLayer: true },
  dynamic_topography: { names: ['hoggard2016'] },
  gravity: { names: ['bouguer'] },
  magnetics: { names: ['emag2'] },
  paleo: { names: ['scotese'], hasRes: true },
};

export const GridSourcesPanel: React.FC = () => {
  const {
    project,
    upsertGrid,
    removeGrid,
    fetchGridDataFromBackend,
    setDatasetModalOpen,
    setStatusMessage,
  } = useProjectStore();

  const [newGridId, setNewGridId] = useState('');
  const [inspectInfo, setInspectInfo] = useState<Record<string, any>>({});
  const [browseFiles, setBrowseFiles] = useState<string[]>([]);
  const [browsingGridId, setBrowsingGridId] = useState<string | null>(null);

  const gridEntries = Object.entries(project.grids || {});

  const handleAddGrid = () => {
    const cleanId = (newGridId.trim() || `grid_${gridEntries.length + 1}`).replace(
      /[^a-zA-Z0-9_]/g,
      '_'
    );
    upsertGrid(cleanId, {
      source_type: 'online',
      category: 'topography',
      name: 'earth',
      resolution: '30m',
      transforms: [],
    });
    setNewGridId('');
  };

  const handleInspectNetcdf = async (gridId: string, filepath?: string) => {
    if (!filepath) return;
    try {
      const res = await fetch('/api/grids/inspect-netcdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filepath }),
      });
      if (res.ok) {
        const data = await res.json();
        setInspectInfo((prev) => ({ ...prev, [gridId]: data }));
        if (data.detected_lat || data.detected_lon || data.detected_data) {
          const current = project.grids[gridId];
          upsertGrid(gridId, {
            ...current,
            netcdf_vars: {
              lat_var: data.detected_lat || 'lat',
              lon_var: data.detected_lon || 'lon',
              data_var: data.detected_data || 'z',
            },
          });
        }
      }
    } catch {
      setStatusMessage('Could not inspect NetCDF variables (backend offline)');
    }
  };

  const handleBrowseLocal = async (gridId: string) => {
    setBrowsingGridId(gridId);
    try {
      const res = await fetch('/api/files/browse?path=..');
      if (res.ok) {
        const data = await res.json();
        const files = (data.files || data.entries || []).map((f: any) =>
          typeof f === 'string' ? f : f.path || f.name
        );
        setBrowseFiles(files);
      }
    } catch {
      setBrowseFiles([
        '../inputs/ETOPO_2022_v1_60s_N90W180_surface.nc',
        '../inputs/s40_depth_slice_2850.grd',
        '../inputs/EGM2008_geoid.nc',
      ]);
    }
  };

  const handleUploadGridFile = async (
    gridId: string,
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch('/api/files/upload', { method: 'POST', body: form });
      if (res.ok) {
        const data = await res.json();
        const current = project.grids[gridId];
        upsertGrid(gridId, { ...current, source_type: 'local', local_path: data.filepath });
        setStatusMessage(`Uploaded ${file.name} -> ${data.filepath}`);
      }
    } catch {
      const current = project.grids[gridId];
      upsertGrid(gridId, {
        ...current,
        source_type: 'local',
        local_path: `.download_cache/uploads/${file.name}`,
      });
    }
  };

  const addTransform = (gridId: string, type: GridTransform['type']) => {
    const current = project.grids[gridId];
    const nextTransforms = [...(current.transforms || [])];
    if (type === 'downsample') {
      nextTransforms.push({ type: 'downsample', step_lat: 10, step_lon: 10 });
    } else if (type === 'airy_moho') {
      nextTransforms.push({
        type: 'airy_moho',
        ref_thickness: 30000,
        rho_c: 2800,
        rho_m: 3300,
      });
    } else if (type === 'weighted_composite') {
      const otherId = Object.keys(project.grids).find((k) => k !== gridId) || gridId;
      nextTransforms.push({
        type: 'weighted_composite',
        grid_b_id: otherId,
        weight_a: 1.0,
        weight_b: 300.0,
        offset: 0.0,
      });
    } else if (type === 'reconstruct') {
      nextTransforms.push({
        type: 'reconstruct',
        age: 250.0,
        plate_model: 'Scotese_PALEOMAP',
      });
    } else if (type === 'scale_offset') {
      nextTransforms.push({ type: 'scale_offset', scale: 1.0, offset: 0.0 });
    }
    upsertGrid(gridId, { ...current, transforms: nextTransforms });
  };

  return (
    <div className="space-y-4 text-xs">
      {/* Header & Add Grid Bar */}
      <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 font-semibold text-slate-200">
            <Database className="w-4 h-4 text-sky-400" />
            <span>Named GeographicGrids ({gridEntries.length})</span>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setDatasetModalOpen(true)}
              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 border border-slate-700 text-[11px]"
            >
              Dataset Cache
            </button>
            <button
              onClick={() => fetchGridDataFromBackend()}
              title="Sync grid buffers from Python"
              className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-slate-700"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <div className="flex gap-1.5">
          <input
            type="text"
            placeholder="New grid ID (e.g. moho_grid, tomo_2850)..."
            value={newGridId}
            onChange={(e) => setNewGridId(e.target.value)}
            className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-100"
          />
          <button
            onClick={handleAddGrid}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Grid</span>
          </button>
        </div>
      </div>

      {/* Grid List */}
      {gridEntries.map(([gridId, cfg]) => {
        const catSpec =
          ONLINE_DATASET_CATEGORIES[cfg.category || 'topography'] ||
          ONLINE_DATASET_CATEGORIES.topography;

        return (
          <div
            key={gridId}
            className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3"
          >
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-sky-500/20 border border-sky-500/40 font-mono font-bold text-sky-300">
                  {gridId}
                </span>
                <select
                  value={cfg.source_type}
                  onChange={(e) =>
                    upsertGrid(gridId, {
                      ...cfg,
                      source_type: e.target.value as GridSourceConfig['source_type'],
                    })
                  }
                  className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200"
                >
                  <option value="online">Online Dataset Catalog</option>
                  <option value="local_or_dataset">Local File + Dataset Fallback</option>
                  <option value="local">Local File (.nc / .grd / .tif)</option>
                  <option value="paleo">Paleo Scotese DEM</option>
                  <option value="synthetic">Synthetic / Procedural Wave</option>
                </select>
              </div>

              <button
                onClick={() => removeGrid(gridId)}
                className="p-1 text-slate-500 hover:text-rose-400"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>

            {/* Online Dataset Selector */}
            {(cfg.source_type === 'online' || cfg.source_type === 'local_or_dataset') && (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 mb-1">Dataset Category</label>
                  <select
                    value={cfg.category || cfg.fallback_dataset?.category || 'topography'}
                    onChange={(e) => {
                      const nextCat = e.target.value;
                      const firstDs = ONLINE_DATASET_CATEGORIES[nextCat]?.names[0] || 'earth';
                      upsertGrid(gridId, {
                        ...cfg,
                        category: nextCat,
                        name: firstDs,
                      });
                    }}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                  >
                    {Object.keys(ONLINE_DATASET_CATEGORIES).map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Dataset Name</label>
                  <select
                    value={cfg.name || cfg.fallback_dataset?.name || catSpec.names[0]}
                    onChange={(e) => upsertGrid(gridId, { ...cfg, name: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                  >
                    {catSpec.names.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </div>

                {catSpec.hasRes && (
                  <div>
                    <label className="block text-slate-400 mb-1">Resolution</label>
                    <select
                      value={cfg.resolution || '30m'}
                      onChange={(e) =>
                        upsertGrid(gridId, { ...cfg, resolution: e.target.value })
                      }
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                    >
                      <option value="1d">1d (1 degree)</option>
                      <option value="30m">30m (30 arc-min)</option>
                      <option value="15m">15m (15 arc-min)</option>
                      <option value="6m">6m (6 arc-min)</option>
                    </select>
                  </div>
                )}

                {catSpec.hasDepth && (
                  <div>
                    <label className="block text-slate-400 mb-1">S40RTS Depth (km)</label>
                    <input
                      type="number"
                      step={50}
                      min={50}
                      max={2890}
                      value={cfg.depth ?? cfg.fallback_dataset?.depth ?? 2850}
                      onChange={(e) =>
                        upsertGrid(gridId, { ...cfg, depth: Number(e.target.value) })
                      }
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono"
                    />
                  </div>
                )}

                {catSpec.hasLayer && (
                  <div>
                    <label className="block text-slate-400 mb-1">CRUST1.0 / Litho Layer</label>
                    <select
                      value={cfg.layer || 'moho'}
                      onChange={(e) => upsertGrid(gridId, { ...cfg, layer: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                    >
                      <option value="moho">moho</option>
                      <option value="surface">surface</option>
                      <option value="water_bottom">water_bottom</option>
                      <option value="ice_bottom">ice_bottom</option>
                      <option value="upper_crust_bottom">upper_crust_bottom</option>
                      <option value="middle_crust_bottom">middle_crust_bottom</option>
                      <option value="total">total (LITHO1.0)</option>
                      <option value="lab">lab (LITHO1.0)</option>
                    </select>
                  </div>
                )}
              </div>
            )}

            {/* Local File Picker + Drag/Drop Upload + NetCDF Inspector */}
            {(cfg.source_type === 'local' || cfg.source_type === 'local_or_dataset') && (
              <div className="space-y-2 pt-1">
                <label className="block text-slate-400">Local NetCDF / GeoTIFF Path</label>
                <div className="flex gap-1.5">
                  <input
                    type="text"
                    value={cfg.local_path || ''}
                    onChange={(e) =>
                      upsertGrid(gridId, { ...cfg, local_path: e.target.value })
                    }
                    placeholder="../inputs/ETOPO_2022_v1_60s_N90W180_surface.nc"
                    className="flex-1 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono text-[11px]"
                  />
                  <button
                    onClick={() => handleBrowseLocal(gridId)}
                    title="Browse Local Files"
                    className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200"
                  >
                    <FolderOpen className="w-3.5 h-3.5" />
                  </button>
                  <label
                    title="Upload Local File"
                    className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sky-300 cursor-pointer flex items-center"
                  >
                    <Upload className="w-3.5 h-3.5" />
                    <input
                      type="file"
                      accept=".nc,.grd,.tif,.tiff"
                      className="hidden"
                      onChange={(e) => handleUploadGridFile(gridId, e)}
                    />
                  </label>
                  <button
                    onClick={() => handleInspectNetcdf(gridId, cfg.local_path)}
                    title="Inspect NetCDF Variables"
                    className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-emerald-400 flex items-center gap-1"
                  >
                    <FileSearch className="w-3.5 h-3.5" />
                    <span>Inspect</span>
                  </button>
                </div>

                {browsingGridId === gridId && browseFiles.length > 0 && (
                  <div className="p-2 rounded bg-slate-950 border border-slate-700 max-h-28 overflow-y-auto space-y-1">
                    {browseFiles.map((fp) => (
                      <button
                        key={fp}
                        onClick={() => {
                          upsertGrid(gridId, { ...cfg, local_path: fp });
                          setBrowsingGridId(null);
                        }}
                        className="block w-full text-left font-mono text-[11px] text-sky-300 hover:bg-slate-800 px-1.5 py-0.5 rounded"
                      >
                        {fp}
                      </button>
                    ))}
                  </div>
                )}

                <div className="grid grid-cols-3 gap-1.5">
                  <input
                    type="text"
                    placeholder="lat_var (lat)"
                    value={cfg.netcdf_vars?.lat_var || ''}
                    onChange={(e) =>
                      upsertGrid(gridId, {
                        ...cfg,
                        netcdf_vars: { ...cfg.netcdf_vars, lat_var: e.target.value },
                      })
                    }
                    className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono"
                  />
                  <input
                    type="text"
                    placeholder="lon_var (lon)"
                    value={cfg.netcdf_vars?.lon_var || ''}
                    onChange={(e) =>
                      upsertGrid(gridId, {
                        ...cfg,
                        netcdf_vars: { ...cfg.netcdf_vars, lon_var: e.target.value },
                      })
                    }
                    className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono"
                  />
                  <input
                    type="text"
                    placeholder="data_var (z)"
                    value={cfg.netcdf_vars?.data_var || ''}
                    onChange={(e) =>
                      upsertGrid(gridId, {
                        ...cfg,
                        netcdf_vars: { ...cfg.netcdf_vars, data_var: e.target.value },
                      })
                    }
                    className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono"
                  />
                </div>

                {inspectInfo[gridId] && (
                  <div className="text-[10px] font-mono text-emerald-400 bg-slate-950 p-1.5 rounded border border-slate-800">
                    Vars: {(inspectInfo[gridId].variables || []).join(', ')}
                  </div>
                )}
              </div>
            )}

            {/* Paleo Scotese DEM Source */}
            {cfg.source_type === 'paleo' && (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 mb-1">Scotese Age (Ma)</label>
                  <input
                    type="number"
                    min={0}
                    max={540}
                    step={5}
                    value={cfg.age ?? 250}
                    onChange={(e) =>
                      upsertGrid(gridId, { ...cfg, age: Number(e.target.value) })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Resolution</label>
                  <select
                    value={cfg.resolution || '1d'}
                    onChange={(e) =>
                      upsertGrid(gridId, { ...cfg, resolution: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                  >
                    <option value="1d">1d (1°)</option>
                    <option value="6m">6m (6 arc-min)</option>
                  </select>
                </div>
              </div>
            )}

            {/* Declarative Grid Transforms Pipeline */}
            <div className="pt-2 border-t border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-medium flex items-center gap-1">
                  <Calculator className="w-3.5 h-3.5 text-amber-400" />
                  <span>Declarative Grid Operations</span>
                </span>
                <select
                  value=""
                  onChange={(e) => {
                    if (e.target.value) {
                      addTransform(gridId, e.target.value as GridTransform['type']);
                    }
                  }}
                  className="bg-slate-950 border border-slate-700 rounded px-2 py-0.5 text-[11px] text-sky-300"
                >
                  <option value="">+ Add Transform...</option>
                  <option value="downsample">Downsample [::step_lat, ::step_lon]</option>
                  <option value="airy_moho">Airy Isostasy Moho Calculator</option>
                  <option value="weighted_composite">Weighted Grid Compositor</option>
                  <option value="reconstruct">GPlately Reconstruct Grid</option>
                  <option value="scale_offset">Scale & Offset</option>
                </select>
              </div>

              {(cfg.transforms || []).map((tr, tIdx) => (
                <div
                  key={tIdx}
                  className="p-2 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-amber-300 text-[11px]">
                      {tr.type.toUpperCase()}
                    </span>
                    <button
                      onClick={() => {
                        const nextT = (cfg.transforms || []).filter((_, i) => i !== tIdx);
                        upsertGrid(gridId, { ...cfg, transforms: nextT });
                      }}
                      className="text-slate-500 hover:text-rose-400"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>

                  {tr.type === 'downsample' && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <span className="text-[10px] text-slate-400">step_lat</span>
                        <input
                          type="number"
                          min={1}
                          value={tr.step_lat ?? 10}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, step_lat: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400">step_lon</span>
                        <input
                          type="number"
                          min={1}
                          value={tr.step_lon ?? 10}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, step_lon: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                    </div>
                  )}

                  {tr.type === 'airy_moho' && (
                    <div className="grid grid-cols-3 gap-1.5">
                      <div>
                        <span className="text-[10px] text-slate-400">Ref Moho (m)</span>
                        <input
                          type="number"
                          value={tr.ref_thickness ?? 30000}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, ref_thickness: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400">rho_c</span>
                        <input
                          type="number"
                          value={tr.rho_c ?? 2800}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, rho_c: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400">rho_m</span>
                        <input
                          type="number"
                          value={tr.rho_m ?? 3300}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, rho_m: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                    </div>
                  )}

                  {tr.type === 'weighted_composite' && (
                    <div className="grid grid-cols-3 gap-1.5">
                      <div>
                        <span className="text-[10px] text-slate-400">Grid B ID</span>
                        <input
                          type="text"
                          value={tr.grid_b_id || ''}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, grid_b_id: e.target.value };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400">Weight A</span>
                        <input
                          type="number"
                          value={tr.weight_a ?? 1}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, weight_a: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400">Weight B</span>
                        <input
                          type="number"
                          value={tr.weight_b ?? 300}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, weight_b: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};
