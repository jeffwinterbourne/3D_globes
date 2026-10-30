import React from 'react';
import {
  Box,
  Cpu,
  Eye,
  Grid as GridIcon,
  Layers,
  Magnet,
  RotateCw,
  Scissors,
  Sparkles,
  Sun,
} from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';
import { ViewMode } from '../../types/globeProject';

export const ViewportToolbar: React.FC = () => {
  const {
    project,
    viewMode,
    setViewMode,
    wireframe,
    setWireframe,
    clippingPlane,
    setClippingPlane,
    clippingOffset,
    setClippingOffset,
    explodeDistance,
    setExplodeDistance,
    showMagnetRing,
    setShowMagnetRing,
    showAxes,
    setShowAxes,
    autoRotate,
    setAutoRotate,
    unlitMode,
    setUnlitMode,
    previewMode,
    isEvaluatingPython,
    renderExactPythonMesh,
    updateGeometry,
    meshData,
    statusMessage,
  } = useProjectStore();

  const viewModes: { id: ViewMode; label: string }[] = [
    { id: 'whole', label: 'Whole' },
    { id: 'exploded', label: 'Exploded Hemispheres' },
    { id: 'upper', label: 'Upper Only' },
    { id: 'lower', label: 'Lower Only' },
    { id: 'outer', label: 'Outer Shell' },
    { id: 'inner', label: 'Inner Shell' },
  ];

  const previewPts = project.geometry.preview_n_points || 60000;

  return (
    <>
      {/* Top Viewport Overlay Bar */}
      <div className="absolute top-3 left-3 right-3 z-10 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
        {/* View Mode Selector Pills */}
        <div className="flex flex-wrap items-center gap-1 bg-slate-900/90 backdrop-blur-md border border-slate-700/80 rounded-lg p-1 shadow-lg pointer-events-auto">
          {viewModes.map((vm) => (
            <button
              key={vm.id}
              onClick={() => setViewMode(vm.id)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                viewMode === vm.id
                  ? 'bg-sky-500 text-slate-950 font-semibold shadow-sm'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              }`}
            >
              {vm.label}
            </button>
          ))}
        </div>

        {/* Toggle Tools & Exact Python Render Action */}
        <div className="flex flex-wrap items-center gap-1.5 bg-slate-900/90 backdrop-blur-md border border-slate-700/80 rounded-lg p-1 shadow-lg pointer-events-auto">
          <button
            onClick={() => setClippingPlane(!clippingPlane)}
            title="Cross-Section Clipping Plane"
            className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition ${
              clippingPlane
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Scissors className="w-3.5 h-3.5" />
            <span>Cross-Section Clip</span>
          </button>

          <button
            onClick={() => setWireframe(!wireframe)}
            title="Toggle Wireframe Overlay"
            className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition ${
              wireframe
                ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40'
                : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Box className="w-3.5 h-3.5" />
            <span>Wireframe</span>
          </button>

          <button
            onClick={() => setShowMagnetRing(!showMagnetRing)}
            title="Toggle 3D Equatorial Magnet Ring"
            className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition ${
              showMagnetRing
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Magnet className="w-3.5 h-3.5" />
            <span>Magnet Ring</span>
          </button>

          <button
            onClick={() => setUnlitMode(!unlitMode)}
            title="Toggle Shaded Relief vs Flat Unlit Colors"
            className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition ${
              unlitMode
                ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
                : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Sun className="w-3.5 h-3.5" />
            <span>{unlitMode ? 'Flat Unlit' : 'Shaded'}</span>
          </button>

          <button
            onClick={() => setShowAxes(!showAxes)}
            title="Toggle Grid & Pole Markers"
            className={`p-1.5 rounded text-xs transition ${
              showAxes ? 'text-sky-400 bg-slate-800' : 'text-slate-400 hover:bg-slate-800'
            }`}
          >
            <GridIcon className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setAutoRotate(!autoRotate)}
            title="Auto-Rotate Camera"
            className={`p-1.5 rounded text-xs transition ${
              autoRotate ? 'text-sky-400 bg-slate-800' : 'text-slate-400 hover:bg-slate-800'
            }`}
          >
            <RotateCw className="w-3.5 h-3.5" />
          </button>

          <div className="h-4 w-px bg-slate-700 mx-0.5" />

          {/* Split Python Render Options */}
          <div className="flex items-center gap-1 bg-slate-800/80 p-0.5 rounded border border-slate-700">
            <button
              onClick={() => renderExactPythonMesh('preview')}
              disabled={isEvaluatingPython}
              title={`Render preview resolution with python (${(
                project.geometry.preview_n_points || 60000
              ).toLocaleString()} vertices)`}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow transition disabled:opacity-50"
            >
              <Cpu className="w-3.5 h-3.5" />
              <span>
                {isEvaluatingPython ? 'Rendering...' : 'Python Preview'}
              </span>
            </button>

            <button
              onClick={() => renderExactPythonMesh('full')}
              disabled={isEvaluatingPython}
              title={`Render full output resolution with python (${(
                project.geometry.n_points || 500000
              ).toLocaleString()} vertices)`}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold shadow transition disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>
                {isEvaluatingPython ? 'Rendering...' : 'Python Full Res'}
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Contextual Sliders when Exploded or Cross-Section Clip is active */}
      {(viewMode === 'exploded' || clippingPlane) && (
        <div className="absolute top-16 left-3 z-10 flex items-center gap-4 bg-slate-900/90 backdrop-blur-md border border-slate-700/80 rounded-lg px-3 py-2 shadow-lg">
          {viewMode === 'exploded' && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-400 font-medium">Explode Gap:</span>
              <input
                type="range"
                min={0}
                max={60}
                step={1}
                value={explodeDistance}
                onChange={(e) => setExplodeDistance(Number(e.target.value))}
                className="w-24"
              />
              <span className="font-mono text-sky-400 w-10">{explodeDistance} mm</span>
            </div>
          )}
          {clippingPlane && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-400 font-medium">Clip Offset:</span>
              <input
                type="range"
                min={-(project.geometry.radius || 40)}
                max={project.geometry.radius || 40}
                step={0.5}
                value={clippingOffset}
                onChange={(e) => setClippingOffset(Number(e.target.value))}
                className="w-24"
              />
              <span className="font-mono text-amber-400 w-12">{clippingOffset} mm</span>
            </div>
          )}
        </div>
      )}

      {/* Bottom Viewport Status & Stats Bar */}
      <div className="absolute bottom-3 left-3 right-3 z-10 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
        {/* Left: Engine Mode & Preview Resolution Slider */}
        <div className="flex flex-wrap items-center gap-3 bg-slate-900/90 backdrop-blur-md border border-slate-700/80 rounded-lg px-3 py-1.5 shadow-lg pointer-events-auto text-xs">
          <div className="flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                previewMode === 'exact_python' ? 'bg-emerald-400' : 'bg-sky-400'
              }`}
            />
            <span className="font-semibold text-slate-200">
              {previewMode === 'exact_python'
                ? 'Exact Python GlobeModel Mesh'
                : 'Fast 60fps WebGL Preview'}
            </span>
          </div>

          <div className="h-3.5 w-px bg-slate-700" />

          <div className="flex items-center gap-2">
            <span className="text-slate-400">Preview Vertices:</span>
            <input
              type="range"
              min={5000}
              max={250000}
              step={5000}
              value={Math.min(250000, previewPts)}
              onChange={(e) => updateGeometry({ preview_n_points: Number(e.target.value) })}
              className="w-24"
            />
            <input
              type="number"
              min={1000}
              max={1000000}
              step={5000}
              value={previewPts}
              onChange={(e) => {
                const v = Math.max(1000, Math.min(1000000, Number(e.target.value) || 60000));
                updateGeometry({ preview_n_points: v });
              }}
              title="Type up to 1,000,000 (1M) preview vertices"
              className="w-20 bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 font-mono text-sky-400 text-[11px]"
            />
            <span className="font-mono text-sky-400 text-[11px]">
              ({previewPts >= 1000000 ? `${(previewPts / 1000000).toFixed(2)}M` : `${Math.round(previewPts / 1000)}k`})
            </span>
          </div>

          <div className="hidden xl:block text-slate-400 truncate max-w-xs">
            {statusMessage}
          </div>
        </div>

        {/* Right: Live Mesh Telemetry Badge */}
        <div className="flex flex-wrap items-center gap-3 bg-slate-900/90 backdrop-blur-md border border-slate-700/80 rounded-lg px-3 py-1.5 shadow-lg pointer-events-auto text-xs font-mono">
          <div>
            <span className="text-slate-400">Verts: </span>
            <span className="text-slate-100">
              {meshData.stats.vertex_count.toLocaleString()}
            </span>
          </div>
          <div>
            <span className="text-slate-400">Faces: </span>
            <span className="text-slate-100">
              {meshData.stats.face_count.toLocaleString()}
            </span>
          </div>
          <div>
            <span className="text-slate-400">Radius: </span>
            <span className="text-sky-300">
              {meshData.stats.min_radius}–{meshData.stats.max_radius} mm
            </span>
          </div>
          <div>
            <span className="text-slate-400">Min Wall: </span>
            <span
              className={
                meshData.stats.min_thickness < 1.5 ? 'text-amber-400 font-bold' : 'text-emerald-400'
              }
            >
              {meshData.stats.min_thickness} mm
            </span>
          </div>
        </div>
      </div>
    </>
  );
};
