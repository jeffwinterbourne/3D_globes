import React from 'react';
import { Box, CircleDot, Layers, ShieldAlert } from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';

export const GeometryPanel: React.FC = () => {
  const { project, updateGeometry } = useProjectStore();
  const geom = project.geometry;

  const fixCfg = geom.fix_intersection || {
    enabled: false,
    min_thickness: 1.5,
    mode: 'inner' as const,
  };

  return (
    <div className="space-y-4 text-xs">
      {/* 1. Base Sphere Sampling & Resolution */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
        <h3 className="font-semibold text-slate-200 flex items-center gap-1.5">
          <Box className="w-4 h-4 text-sky-400" />
          <span>Base Sphere Distribution & Resolution</span>
        </h3>

        <div className="grid grid-cols-2 gap-2">
          {(['fibonacci', 'icosahedron'] as const).map((m) => (
            <button
              key={m}
              onClick={() => updateGeometry({ method: m })}
              className={`py-2 px-3 rounded-lg font-medium border capitalize transition ${
                geom.method === m
                  ? 'bg-sky-500/20 border-sky-400 text-sky-300 font-semibold'
                  : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {m} Sphere
            </button>
          ))}
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-slate-400">Final Export Vertex Count (n_points)</span>
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min={500}
                max={10000000}
                step={25000}
                value={geom.n_points || 500000}
                onChange={(e) => {
                  const v = Math.max(500, Math.min(10000000, Number(e.target.value) || 500000));
                  updateGeometry({ n_points: v });
                }}
                title="Type up to 10,000,000 (10M) final export vertices"
                className="w-28 bg-slate-950 border border-slate-700 rounded px-2 py-0.5 font-mono text-sky-400 text-right"
              />
              <span className="text-[10px] text-slate-500">pts (max 10M)</span>
            </div>
          </div>
          <input
            type="range"
            min={5000}
            max={2500000}
            step={25000}
            value={Math.min(2500000, geom.n_points || 500000)}
            onChange={(e) => updateGeometry({ n_points: Number(e.target.value) })}
            className="w-full"
          />
          <div className="flex justify-between text-[10px] text-slate-500 mt-1">
            <button
              onClick={() => updateGeometry({ n_points: 100000 })}
              className="hover:text-sky-400"
            >
              100k (Fast)
            </button>
            <button
              onClick={() => updateGeometry({ n_points: 500000 })}
              className="hover:text-sky-400"
            >
              500k (Default)
            </button>
            <button
              onClick={() => updateGeometry({ n_points: 1000000 })}
              className="hover:text-sky-400"
            >
              1M (High-Res)
            </button>
            <button
              onClick={() => updateGeometry({ n_points: 2500000 })}
              className="hover:text-sky-400"
            >
              2.5M (Ultra)
            </button>
            <button
              onClick={() => updateGeometry({ n_points: 5000000 })}
              className="hover:text-sky-400"
            >
              5M (Extreme)
            </button>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-slate-400">Interactive 3D Preview Vertices</span>
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min={1000}
                max={1000000}
                step={5000}
                value={geom.preview_n_points || 60000}
                onChange={(e) => {
                  const v = Math.max(1000, Math.min(1000000, Number(e.target.value) || 60000));
                  updateGeometry({ preview_n_points: v });
                }}
                title="Type up to 1,000,000 (1M) preview vertices"
                className="w-24 bg-slate-950 border border-slate-700 rounded px-2 py-0.5 font-mono text-emerald-400 text-right"
              />
              <span className="text-[10px] text-slate-500">pts (max 1M)</span>
            </div>
          </div>
          <input
            type="range"
            min={5000}
            max={250000}
            step={5000}
            value={Math.min(250000, geom.preview_n_points || 60000)}
            onChange={(e) => updateGeometry({ preview_n_points: Number(e.target.value) })}
            className="w-full"
          />
          <div className="flex justify-between text-[10px] text-slate-500 mt-1">
            <button
              onClick={() => updateGeometry({ preview_n_points: 25000 })}
              className="hover:text-emerald-400"
            >
              25k (Light)
            </button>
            <button
              onClick={() => updateGeometry({ preview_n_points: 60000 })}
              className="hover:text-emerald-400"
            >
              60k (Default)
            </button>
            <button
              onClick={() => updateGeometry({ preview_n_points: 150000 })}
              className="hover:text-emerald-400"
            >
              150k (Fine)
            </button>
            <button
              onClick={() => updateGeometry({ preview_n_points: 250000 })}
              className="hover:text-emerald-400"
            >
              250k (Slider Max)
            </button>
            <button
              onClick={() => updateGeometry({ preview_n_points: 1000000 })}
              className="hover:text-emerald-400"
            >
              1M (Stress Test)
            </button>
          </div>
        </div>
      </div>

      {/* 2. Physical Dimensions & Center */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
        <h3 className="font-semibold text-slate-200 flex items-center gap-1.5">
          <CircleDot className="w-4 h-4 text-emerald-400" />
          <span>Physical Radius & Origin (mm)</span>
        </h3>

        <div>
          <div className="flex justify-between mb-1">
            <span className="text-slate-400">Outer Reference Radius (mm)</span>
            <span className="font-mono text-sky-400">{geom.radius} mm</span>
          </div>
          <input
            type="range"
            min={5}
            max={150}
            step={0.5}
            value={geom.radius}
            onChange={(e) => updateGeometry({ radius: Number(e.target.value) })}
            className="w-full"
          />
        </div>

        <div>
          <label className="block text-slate-400 mb-1">Center Coordinates [X, Y, Z] (mm)</label>
          <div className="grid grid-cols-3 gap-2">
            {[0, 1, 2].map((idx) => (
              <input
                key={idx}
                type="number"
                step="0.5"
                value={geom.center?.[idx] ?? 0}
                onChange={(e) => {
                  const nextCenter: [number, number, number] = [
                    geom.center?.[0] ?? 0,
                    geom.center?.[1] ?? 0,
                    geom.center?.[2] ?? 0,
                  ];
                  nextCenter[idx] = Number(e.target.value);
                  updateGeometry({ center: nextCenter });
                }}
                className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono"
              />
            ))}
          </div>
        </div>
      </div>

      {/* 3. Hollowing & Inner Cavity Shell */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-slate-200 flex items-center gap-1.5">
            <Layers className="w-4 h-4 text-amber-400" />
            <span>Hollow Shell & Inner Cavity</span>
          </h3>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={geom.hollow}
              onChange={(e) => updateGeometry({ hollow: e.target.checked })}
            />
            <span className="font-semibold text-slate-200">Hollow Globe</span>
          </label>
        </div>

        {geom.hollow && (
          <div className="space-y-3 pt-1">
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-slate-400">Inner Radius Ratio (inner_ratio)</span>
                <span className="font-mono text-amber-400">
                  {geom.inner_ratio} ({(geom.radius * geom.inner_ratio).toFixed(1)} mm)
                </span>
              </div>
              <input
                type="range"
                min={0.15}
                max={0.92}
                step={0.01}
                value={geom.inner_ratio}
                onChange={(e) =>
                  updateGeometry({
                    inner_ratio: Number(e.target.value),
                    inner_thickness: null,
                  })
                }
                className="w-full"
              />
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="block text-slate-400 mb-1">
                  create_inner_mesh(thickness mm)
                </label>
                <input
                  type="number"
                  step="0.5"
                  placeholder="Optional (uses ratio if blank)"
                  value={geom.inner_thickness ?? ''}
                  onChange={(e) =>
                    updateGeometry({
                      inner_thickness: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Inner Vertex Count Override</label>
                <input
                  type="number"
                  step="1000"
                  placeholder="Same as outer if blank"
                  value={geom.inner_n_points ?? ''}
                  onChange={(e) =>
                    updateGeometry({
                      inner_n_points: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 4. Shell Intersection & Minimum Wall Thickness Guard */}
      {geom.hollow && (
        <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-slate-200 flex items-center gap-1.5">
              <ShieldAlert className="w-4 h-4 text-rose-400" />
              <span>Intersection Guard (fix_intersection)</span>
            </h3>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={fixCfg.enabled}
                onChange={(e) =>
                  updateGeometry({
                    fix_intersection: { ...fixCfg, enabled: e.target.checked },
                  })
                }
              />
              <span className="text-slate-300">Enforce Min Wall</span>
            </label>
          </div>

          {fixCfg.enabled && (
            <div className="grid grid-cols-2 gap-2.5 pt-1">
              <div>
                <label className="block text-slate-400 mb-1">Min Wall Thickness (mm)</label>
                <input
                  type="number"
                  step="0.1"
                  min={0.4}
                  max={15}
                  value={fixCfg.min_thickness}
                  onChange={(e) =>
                    updateGeometry({
                      fix_intersection: {
                        ...fixCfg,
                        min_thickness: Number(e.target.value),
                      },
                    })
                  }
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Adjustment Mode</label>
                <select
                  value={fixCfg.mode}
                  onChange={(e) =>
                    updateGeometry({
                      fix_intersection: {
                        ...fixCfg,
                        mode: e.target.value as 'inner' | 'outer' | 'both',
                      },
                    })
                  }
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                >
                  <option value="inner">Push Inner Cavity Inward ('inner')</option>
                  <option value="outer">Push Outer Surface Outward ('outer')</option>
                  <option value="both">Split Adjustment Equally ('both')</option>
                </select>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
