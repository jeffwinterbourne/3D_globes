import React, { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Magnet,
  Sparkles,
  Wrench,
} from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';

export const MagnetStudioPanel: React.FC = () => {
  const {
    project,
    updateMagnets,
    magnetAnalysis,
    optimizeMagnetsBackend,
    setStatusMessage,
  } = useProjectStore();

  const mag = project.magnets;
  const [testPieceResult, setTestPieceResult] = useState<{
    filename?: string;
    saved_path?: string;
    download_url?: string;
  } | null>(null);
  const [generatingTest, setGeneratingTest] = useState(false);

  const handleGenerateTestPiece = async () => {
    setGeneratingTest(true);
    try {
      const res = await fetch('/api/magnets/test-piece', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          diameter: mag.diameter,
          height: mag.height,
          clearance: mag.horizontal_tolerance,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setTestPieceResult(data);
        setStatusMessage(`Generated calibration test piece: ${data.filename}`);
      }
    } catch {
      setTestPieceResult({
        filename: `magnet_test_piece_${mag.diameter}x${mag.height}mm.stl`,
        saved_path: `outputs/magnet_test_piece_${mag.diameter}x${mag.height}mm.stl`,
        download_url: `/api/exports/download?path=outputs/magnet_test_piece_${mag.diameter}x${mag.height}mm.stl`,
      });
    } finally {
      setGeneratingTest(false);
    }
  };

  // Build SVG path for 360° Equatorial Cross-Section [d_min, d_max]
  const maxR = Math.max(45, (project.geometry.radius || 40) * 1.15);
  const scaleSvg = 105 / maxR;

  const outerPoints = (magnetAnalysis.d_max || [])
    .map((r, deg) => {
      const rad = (deg * Math.PI) / 180;
      const x = 120 + r * scaleSvg * Math.cos(rad);
      const y = 120 - r * scaleSvg * Math.sin(rad);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  const innerPoints = (magnetAnalysis.d_min || [])
    .map((r, deg) => {
      const rad = (deg * Math.PI) / 180;
      const x = 120 + r * scaleSvg * Math.cos(rad);
      const y = 120 - r * scaleSvg * Math.sin(rad);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <div className="space-y-4 text-xs">
      {/* 1. Enable & Auto-Optimize Header */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold text-slate-200">
            <Magnet className="w-4 h-4 text-emerald-400" />
            <span>Equatorial Magnet Studio</span>
          </div>
          <label className="flex items-center gap-1.5 cursor-pointer font-semibold text-emerald-300">
            <input
              type="checkbox"
              checked={mag.enabled}
              onChange={(e) => updateMagnets({ enabled: e.target.checked })}
            />
            <span>Enable Magnets</span>
          </label>
        </div>

        <button
          onClick={() => optimizeMagnetsBackend()}
          className="w-full py-2 px-3 rounded-lg bg-gradient-to-r from-sky-500 to-emerald-500 hover:from-sky-400 hover:to-emerald-400 text-slate-950 font-bold flex items-center justify-center gap-1.5 shadow transition"
        >
          <Sparkles className="w-4 h-4" />
          <span>Auto-Optimize Positions (Zero-Boss Peak Search)</span>
        </button>
      </div>

      {/* 2. Interactive 360° Equatorial Cross-Section SVG Visualizer */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-slate-200">
            360° Equatorial Wall Cross-Section [d_min, d_max]
          </span>
          <div className="flex items-center gap-2 text-[10px]">
            <span className="flex items-center gap-1 text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400" /> Valid
            </span>
            <span className="flex items-center gap-1 text-amber-400">
              <span className="w-2 h-2 rounded-full bg-amber-400" /> Boss
            </span>
            <span className="flex items-center gap-1 text-rose-400">
              <span className="w-2 h-2 rounded-full bg-rose-400" /> Invalid
            </span>
          </div>
        </div>

        <div className="flex justify-center bg-slate-950 rounded-xl border border-slate-800 p-2">
          <svg width="240" height="240" viewBox="0 0 240 240">
            {/* Reference axes */}
            <line x1="10" y1="120" x2="230" y2="120" stroke="#1e293b" strokeWidth="1" />
            <line x1="120" y1="10" x2="120" y2="230" stroke="#1e293b" strokeWidth="1" />

            {/* Outer displaced wall polygon */}
            {outerPoints && (
              <polygon
                points={outerPoints}
                fill="#0284c7"
                fillOpacity="0.22"
                stroke="#38bdf8"
                strokeWidth="1.5"
              />
            )}

            {/* Inner cavity polygon */}
            {project.geometry.hollow && innerPoints && (
              <polygon
                points={innerPoints}
                fill="#090d16"
                stroke="#64748b"
                strokeWidth="1.2"
                strokeDasharray="3 2"
              />
            )}

            {/* Magnet footprints */}
            {(magnetAnalysis.magnets || []).map((m) => {
              const mx = 120 + m.center[0] * scaleSvg;
              const my = 120 - m.center[1] * scaleSvg;
              const mr = Math.max(
                4,
                ((mag.diameter * 0.5 + mag.horizontal_tolerance) * scaleSvg)
              );
              const color = !m.valid
                ? '#ef4444'
                : m.needs_boss
                ? '#f59e0b'
                : '#10b981';

              return (
                <g key={m.index}>
                  {m.needs_boss && (
                    <circle
                      cx={mx}
                      cy={my}
                      r={mr + mag.min_thickness * scaleSvg}
                      fill="none"
                      stroke="#f59e0b"
                      strokeWidth="1.2"
                      strokeDasharray="2 2"
                    />
                  )}
                  <circle
                    cx={mx}
                    cy={my}
                    r={mr}
                    fill={color}
                    fillOpacity="0.7"
                    stroke="#ffffff"
                    strokeWidth="1"
                  />
                  <text
                    x={mx}
                    y={my + 3}
                    textAnchor="middle"
                    fill="#ffffff"
                    fontSize="8"
                    fontWeight="bold"
                  >
                    {m.index + 1}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Magnet Angles & Margins Readout Table */}
        <div className="space-y-1.5">
          {(magnetAnalysis.magnets || []).map((m, idx) => (
            <div
              key={m.index}
              className="flex items-center justify-between bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5"
            >
              <div className="flex items-center gap-2">
                {m.valid && !m.needs_boss ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <AlertTriangle
                    className={`w-3.5 h-3.5 ${
                      m.needs_boss ? 'text-amber-400' : 'text-rose-400'
                    }`}
                  />
                )}
                <span className="font-mono font-bold text-slate-200">
                  #{m.index + 1}
                </span>
                <input
                  type="number"
                  step={2}
                  min={0}
                  max={359}
                  value={m.angle_deg}
                  onChange={(e) => {
                    const nextAngles = (magnetAnalysis.magnets || []).map((item, i) =>
                      i === idx ? Number(e.target.value) : item.angle_deg
                    );
                    updateMagnets({ position: nextAngles });
                  }}
                  className="w-16 bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 font-mono text-sky-300"
                />
                <span className="text-slate-500">deg</span>
              </div>

              <div className="text-[10px] font-mono text-right">
                <span className="text-slate-400">
                  In: {m.margin_inner}mm | Out: {m.margin_outer}mm{' '}
                </span>
                {m.needs_boss && (
                  <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 ml-1">
                    Boss
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 3. Magnet Dimensions & Tolerances */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
        <div className="font-semibold text-slate-200">
          Magnet Dimensions & Clearances (mm)
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-slate-400 mb-1">Magnet Count (n_magnets)</label>
            <input
              type="number"
              min={1}
              max={16}
              value={mag.n_magnets}
              onChange={(e) =>
                updateMagnets({
                  n_magnets: Number(e.target.value),
                  position: 0,
                })
              }
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
            />
          </div>
          <div>
            <label className="block text-slate-400 mb-1">Placement Strategy</label>
            <select
              value={mag.placement_strategy || 'cluster_peaks'}
              onChange={(e) =>
                updateMagnets({ placement_strategy: e.target.value as any })
              }
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1"
            >
              <option value="cluster_peaks">cluster_peaks</option>
              <option value="uniform">uniform</option>
              <option value="margin_weighted">margin_weighted</option>
            </select>
          </div>
          <div>
            <label className="block text-slate-400 mb-1">Diameter (mm)</label>
            <input
              type="number"
              step="0.2"
              value={mag.diameter}
              onChange={(e) => updateMagnets({ diameter: Number(e.target.value) })}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
            />
          </div>
          <div>
            <label className="block text-slate-400 mb-1">Height (mm)</label>
            <input
              type="number"
              step="0.2"
              value={mag.height}
              onChange={(e) => updateMagnets({ height: Number(e.target.value) })}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
            />
          </div>
          <div>
            <label className="block text-slate-400 mb-1">Radial Clearance (mm)</label>
            <input
              type="number"
              step="0.05"
              value={mag.horizontal_tolerance}
              onChange={(e) =>
                updateMagnets({ horizontal_tolerance: Number(e.target.value) })
              }
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
            />
          </div>
          <div>
            <label className="block text-slate-400 mb-1">Min Wall Margin (mm)</label>
            <input
              type="number"
              step="0.1"
              value={mag.min_thickness}
              onChange={(e) =>
                updateMagnets({ min_thickness: Number(e.target.value) })
              }
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
            />
          </div>
        </div>

        <label className="flex items-center gap-2 pt-1 cursor-pointer text-slate-300">
          <input
            type="checkbox"
            checked={mag.allow_bosses}
            onChange={(e) => updateMagnets({ allow_bosses: e.target.checked })}
          />
          <span>Allow Interior Support Bosses when Wall is Thin (allow_bosses)</span>
        </label>
      </div>

      {/* 4. Calibration Test Piece Generator */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
        <div className="flex items-center gap-1.5 font-semibold text-slate-200">
          <Wrench className="w-3.5 h-3.5 text-amber-400" />
          <span>Physical Fit Calibration Test Piece</span>
        </div>
        <button
          onClick={handleGenerateTestPiece}
          disabled={generatingTest}
          className="w-full py-2 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-amber-300 font-semibold flex items-center justify-center gap-1.5 transition"
        >
          <Download className="w-3.5 h-3.5" />
          <span>
            {generatingTest
              ? 'Generating Test Piece...'
              : 'Generate Calibration Test Piece (.stl)'}
          </span>
        </button>

        {testPieceResult?.download_url && (
          <a
            href={testPieceResult.download_url}
            download={testPieceResult.filename}
            className="block text-center py-1.5 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 font-semibold"
          >
            Download {testPieceResult.filename}
          </a>
        )}
      </div>
    </div>
  );
};
