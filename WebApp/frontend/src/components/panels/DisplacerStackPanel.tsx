import React, { useState } from 'react';
import { ArrowDown, ArrowUp, Layers, Plus, Trash2 } from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';
import { DisplacerConfig } from '../../types/globeProject';

export const DisplacerStackPanel: React.FC = () => {
  const { project, setOuterDisplacements, setInnerDisplacements } = useProjectStore();
  const [activeShell, setActiveShell] = useState<'outer' | 'inner'>('outer');
  const [newType, setNewType] = useState<DisplacerConfig['type']>('GridDisplacer');

  const list =
    activeShell === 'outer'
      ? project.outer_displacements || []
      : project.inner_displacements || [];

  const setList = (next: DisplacerConfig[]) => {
    if (activeShell === 'outer') setOuterDisplacements(next);
    else setInnerDisplacements(next);
  };

  const gridIds = Object.keys(project.grids || {});

  const handleAdd = () => {
    const id = `disp_${activeShell}_${Date.now().toString().slice(-4)}`;
    const item: DisplacerConfig = {
      id,
      enabled: true,
      type: newType,
      grid_id: gridIds[0] || 'etopo_ds',
      scale_mode: 'physical',
      vertical_exagg: 40.0,
      grid_units: 'm',
      reference_level: 0.0,
      coastline_step: 0.0,
      step_threshold: 0.0,
      interp_method: 'linear',
      displacement: 0.8,
      scale: 1.0,
      shapefile:
        newType === 'LineDisplacer'
          ? 'dataset:shapefiles.coastline'
          : newType === 'PolygonDisplacer'
          ? 'dataset:shapefiles.land'
          : '',
      radius_degrees: 2.5,
      width_degrees: 0.5,
      displace_inside: true,
    };
    setList([...list, item]);
  };

  const updateItem = (idx: number, patch: Partial<DisplacerConfig>) => {
    const next = [...list];
    next[idx] = { ...next[idx], ...patch };
    setList(next);
  };

  const moveItem = (idx: number, dir: -1 | 1) => {
    const targetIdx = idx + dir;
    if (targetIdx < 0 || targetIdx >= list.length) return;
    const next = [...list];
    const [removed] = next.splice(idx, 1);
    next.splice(targetIdx, 0, removed);
    setList(next);
  };

  return (
    <div className="space-y-4 text-xs">
      {/* Shell Switcher & Add Layer Bar */}
      <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
        <div className="grid grid-cols-2 gap-1.5">
          <button
            onClick={() => setActiveShell('outer')}
            className={`py-1.5 rounded-lg font-semibold border transition ${
              activeShell === 'outer'
                ? 'bg-sky-500/20 border-sky-400 text-sky-300'
                : 'bg-slate-950 border-slate-800 text-slate-400'
            }`}
          >
            Outer Shell ({project.outer_displacements?.length || 0})
          </button>
          <button
            onClick={() => setActiveShell('inner')}
            className={`py-1.5 rounded-lg font-semibold border transition ${
              activeShell === 'inner'
                ? 'bg-amber-500/20 border-amber-400 text-amber-300'
                : 'bg-slate-950 border-slate-800 text-slate-400'
            }`}
          >
            Inner Cavity ({project.inner_displacements?.length || 0})
          </button>
        </div>

        <div className="flex gap-1.5">
          <select
            value={newType}
            onChange={(e) => setNewType(e.target.value as DisplacerConfig['type'])}
            className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-100"
          >
            <option value="GridDisplacer">GridDisplacer (2D GeographicGrid)</option>
            <option value="ConstantDisplacer">ConstantDisplacer (Uniform Offset)</option>
            <option value="LineDisplacer">LineDisplacer (Coastlines / Faults)</option>
            <option value="PolygonDisplacer">PolygonDisplacer (Land / Continents)</option>
            <option value="PointDisplacer">PointDisplacer (Landmarks / Volcanoes)</option>
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

      {/* Displacer Layer Cards */}
      {list.length === 0 && (
        <div className="p-6 text-center rounded-xl border border-dashed border-slate-800 text-slate-500">
          No displacement layers on {activeShell} shell. Click Add above to insert a layer.
        </div>
      )}

      {list.map((item, idx) => {
        const exagg = item.vertical_exagg ?? item.vert_exagg ?? 40;
        const calcScale = (
          ((project.geometry.radius || 40) / 6371000.0) *
          (item.grid_units === 'km' ? 1000 : 1) *
          exagg
        ).toExponential(3);

        return (
          <div
            key={item.id || idx}
            className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5"
          >
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={item.enabled}
                  onChange={(e) => updateItem(idx, { enabled: e.target.checked })}
                />
                <span className="font-bold text-sky-300">{item.type}</span>
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
                  onClick={() => setList(list.filter((_, i) => i !== idx))}
                  className="p-1 text-slate-500 hover:text-rose-400"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {item.type === 'GridDisplacer' && (
              <div className="space-y-2.5">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1">Source Grid ID</label>
                    <select
                      value={item.grid_id || ''}
                      onChange={(e) => updateItem(idx, { grid_id: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                    >
                      {gridIds.map((gid) => (
                        <option key={gid} value={gid}>
                          {gid}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1">Scale Mode</label>
                    <select
                      value={item.scale_mode || 'physical'}
                      onChange={(e) =>
                        updateItem(idx, { scale_mode: e.target.value as 'physical' | 'direct' })
                      }
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                    >
                      <option value="physical">Physical (calculate_displacement_scale)</option>
                      <option value="direct">Direct Scale Factor</option>
                    </select>
                  </div>
                </div>

                {item.scale_mode !== 'direct' ? (
                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-slate-400">
                        Vertical Exaggeration (scale ≈ {calcScale})
                      </span>
                      <span className="font-mono text-sky-400">{exagg}x</span>
                    </div>
                    <input
                      type="range"
                      min={1}
                      max={150}
                      step={1}
                      value={exagg}
                      onChange={(e) =>
                        updateItem(idx, {
                          vertical_exagg: Number(e.target.value),
                          vert_exagg: Number(e.target.value),
                        })
                      }
                      className="w-full"
                    />
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-slate-400">Grid Elevation Units</span>
                      <select
                        value={item.grid_units || 'm'}
                        onChange={(e) => updateItem(idx, { grid_units: e.target.value as any })}
                        className="bg-slate-950 border border-slate-700 rounded px-2 py-0.5 text-slate-200"
                      >
                        <option value="m">Meters (m)</option>
                        <option value="km">Kilometers (km)</option>
                        <option value="cm">Centimeters (cm)</option>
                        <option value="mm">Millimeters (mm)</option>
                        <option value="ft">Feet (ft)</option>
                      </select>
                    </div>
                  </div>
                ) : (
                  <div>
                    <label className="block text-slate-400 mb-1">Direct Scale Factor (mm / unit)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={item.scale ?? 1.0}
                      onChange={(e) => updateItem(idx, { scale: Number(e.target.value) })}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
                    />
                  </div>
                )}

                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1">Ref Level</label>
                    <input
                      type="number"
                      step="100"
                      value={item.reference_level ?? 0}
                      onChange={(e) =>
                        updateItem(idx, { reference_level: Number(e.target.value) })
                      }
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Coast Step (mm)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={item.coastline_step ?? 0}
                      onChange={(e) =>
                        updateItem(idx, { coastline_step: Number(e.target.value) })
                      }
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Step Threshold</label>
                    <input
                      type="number"
                      step="10"
                      value={item.step_threshold ?? 0}
                      onChange={(e) =>
                        updateItem(idx, { step_threshold: Number(e.target.value) })
                      }
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
                    />
                  </div>
                </div>
              </div>
            )}

            {item.type !== 'GridDisplacer' && (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 mb-1">Displacement (mm)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={item.displacement ?? 0.8}
                    onChange={(e) => updateItem(idx, { displacement: Number(e.target.value) })}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
                  />
                </div>
                {(item.type === 'LineDisplacer' || item.type === 'PolygonDisplacer') && (
                  <div>
                    <label className="block text-slate-400 mb-1">Shapefile / Builtin</label>
                    <input
                      type="text"
                      value={item.shapefile || item.local_path || ''}
                      onChange={(e) => updateItem(idx, { shapefile: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
