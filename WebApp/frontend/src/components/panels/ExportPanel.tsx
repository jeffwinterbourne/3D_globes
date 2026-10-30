import React, { useState } from 'react';
import {
  CheckCircle2,
  Cpu,
  Download,
  ExternalLink,
  FileBox,
  FolderOpen,
  Scissors,
} from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';
import { toBackendGlobeProjectPayload } from '../../utils/projectNormalizer';

interface ExportedFileInfo {
  filename: string;
  saved_path: string;
  size_bytes: number;
  download_url: string;
}

export const ExportPanel: React.FC = () => {
  const {
    project,
    updateExport,
    renderExactPythonMesh,
    isEvaluatingPython,
    setStatusMessage,
  } = useProjectStore();

  const exp = project.export;
  const [isExporting, setIsExporting] = useState(false);
  const [exportedFiles, setExportedFiles] = useState<ExportedFileInfo[]>([]);
  const [exportError, setExportError] = useState<string | null>(null);

  const handleRenderAndExport = async () => {
    setIsExporting(true);
    setExportError(null);
    setStatusMessage('Rendering & exporting full-resolution Python GlobeModel...');
    try {
      const res = await fetch('/api/export/render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(toBackendGlobeProjectPayload(project)),
      });
      if (!res.ok) {
        const errDoc = await res.json().catch(() => ({}));
        throw new Error(errDoc.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setExportedFiles(data.files || []);
      setStatusMessage(
        `Export complete: ${(data.files || []).length} file(s) written to ${exp.output_dir || 'outputs/'}`
      );
    } catch (err: any) {
      setExportError(err?.message || 'Failed to run Python export');
      setStatusMessage(`Export error: ${err?.message || 'backend error'}`);
    } finally {
      setIsExporting(false);
    }
  };

  const handleRevealInExplorer = async (savedPath: string) => {
    try {
      await fetch('/api/exports/reveal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: savedPath }),
      });
    } catch {
      // Ignore error
    }
  };

  return (
    <div className="space-y-4 text-xs">
      {/* 1. Split Hemispheres vs Whole Globe */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
        <div className="flex items-center gap-1.5 font-semibold text-slate-200">
          <Scissors className="w-4 h-4 text-sky-400" />
          <span>Hemisphere Split & CSG Boolean Mode</span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => updateExport({ mode: 'hemispheres' })}
            className={`py-2 px-3 rounded-lg font-medium border transition ${
              exp.mode === 'hemispheres'
                ? 'bg-sky-500/20 border-sky-400 text-sky-300 font-semibold'
                : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            Split Hemispheres (N / S)
          </button>
          <button
            onClick={() => updateExport({ mode: 'whole' })}
            className={`py-2 px-3 rounded-lg font-medium border transition ${
              exp.mode === 'whole'
                ? 'bg-sky-500/20 border-sky-400 text-sky-300 font-semibold'
                : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            Whole Unsplit Globe
          </button>
        </div>

        {exp.mode === 'hemispheres' && (
          <div className="grid grid-cols-2 gap-2 pt-1">
            <div>
              <label className="block text-slate-400 mb-1">Boolean CSG Engine</label>
              <select
                value={exp.engine || 'manifold'}
                onChange={(e) => updateExport({ engine: e.target.value as any })}
                className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1"
              >
                <option value="manifold">manifold3d (Fast & Watertight)</option>
                <option value="blender">Blender Subprocess</option>
              </select>
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Build Plate Offset (mm)</label>
              <input
                type="number"
                value={exp.offset_distance ?? 85}
                onChange={(e) =>
                  updateExport({ offset_distance: Number(e.target.value) })
                }
                className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
              />
            </div>
          </div>
        )}
      </div>

      {/* 2. File Format Selector (.3mf / .obj / .stl) */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
        <div className="flex items-center gap-1.5 font-semibold text-slate-200">
          <FileBox className="w-4 h-4 text-emerald-400" />
          <span>3D Print File Format</span>
        </div>

        <div className="grid grid-cols-3 gap-1.5">
          {[
            { id: '3mf', label: '.3MF (Multi-Color)', desc: 'OrcaSlicer / Snapmaker U1' },
            { id: 'obj', label: '.OBJ (Vertex RGB)', desc: 'Wavefront + Colors' },
            { id: 'stl', label: '.STL (Binary)', desc: 'Standard Monochrome' },
          ].map((fmt) => (
            <button
              key={fmt.id}
              onClick={() =>
                updateExport({
                  format: fmt.id as any,
                  filename: `${(exp.filename || project.id || 'globe').replace(/\.(3mf|obj|stl)$/i, '')}.${fmt.id}`,
                })
              }
              className={`p-2 rounded-lg border text-left transition ${
                exp.format === fmt.id
                  ? 'bg-emerald-500/20 border-emerald-400 text-emerald-300'
                  : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              <div className="font-bold">{fmt.label}</div>
              <div className="text-[10px] opacity-80">{fmt.desc}</div>
            </button>
          ))}
        </div>

        {exp.mode === 'hemispheres' && (
          <div className="flex items-center justify-between pt-1">
            <span className="text-slate-300">Hemisphere File Packaging</span>
            <select
              value={exp.single_file_3mf ? 'single' : 'dual'}
              onChange={(e) =>
                updateExport({ single_file_3mf: e.target.value === 'single' })
              }
              className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200"
            >
              <option value="single">Single Combined File (Both Halves on Plate)</option>
              <option value="dual">Dual Separate Files (_top & _bottom)</option>
            </select>
          </div>
        )}

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-slate-400 mb-1">Filename Prefix</label>
            <input
              type="text"
              value={exp.filename || `${project.id}.${exp.format}`}
              onChange={(e) => updateExport({ filename: e.target.value })}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
            />
          </div>
          <div>
            <label className="block text-slate-400 mb-1">Output Directory</label>
            <input
              type="text"
              value={exp.output_dir || 'outputs'}
              onChange={(e) => updateExport({ output_dir: e.target.value })}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono"
            />
          </div>
        </div>
      </div>

      {/* 3. Primary Render & Export Actions */}
      <div className="space-y-2.5">
        <button
          onClick={() => renderExactPythonMesh()}
          disabled={isEvaluatingPython}
          className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-600 text-sky-300 font-semibold flex items-center justify-center gap-2 transition"
        >
          <Cpu className="w-4 h-4" />
          <span>
            {isEvaluatingPython
              ? 'Evaluating Python Mesh...'
              : 'Preview Definitive Python Mesh in 3D Viewport'}
          </span>
        </button>

        <button
          onClick={handleRenderAndExport}
          disabled={isExporting}
          className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-500 to-sky-500 hover:from-emerald-400 hover:to-sky-400 text-slate-950 font-bold text-sm flex items-center justify-center gap-2 shadow-lg transition disabled:opacity-50"
        >
          <Download className="w-4 h-4" />
          <span>
            {isExporting
              ? 'Rendering & Writing 3D Print Files...'
              : `Render & Export Final Python Globe (.${exp.format.toUpperCase()})`}
          </span>
        </button>
      </div>

      {exportError && (
        <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-500/50 text-rose-200">
          {exportError}
        </div>
      )}

      {/* 4. Exported Files Download & Reveal List */}
      {exportedFiles.length > 0 && (
        <div className="p-3.5 rounded-xl bg-emerald-950/30 border border-emerald-500/40 space-y-2.5">
          <div className="flex items-center gap-1.5 font-bold text-emerald-300">
            <CheckCircle2 className="w-4 h-4" />
            <span>Exported 3D Print Files Ready</span>
          </div>

          {exportedFiles.map((f) => (
            <div
              key={f.saved_path}
              className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono font-semibold text-slate-100">
                  {f.filename}
                </span>
                <span className="text-[10px] font-mono text-slate-400">
                  {((f.size_bytes || 0) / (1024 * 1024)).toFixed(2)} MB
                </span>
              </div>
              <div className="text-[10px] font-mono text-slate-500 truncate">
                {f.saved_path}
              </div>
              <div className="flex gap-2">
                <a
                  href={f.download_url}
                  download={f.filename}
                  className="flex-1 py-1.5 rounded bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-center flex items-center justify-center gap-1"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Browser Download</span>
                </a>
                <button
                  onClick={() => handleRevealInExplorer(f.saved_path)}
                  className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 flex items-center gap-1"
                >
                  <FolderOpen className="w-3.5 h-3.5 text-amber-400" />
                  <span>Reveal in File Explorer</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
