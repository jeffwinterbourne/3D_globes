import React, { useEffect, useState } from 'react';
import {
  X,
  Database,
  Plus,
  Copy,
  Layers,
  Settings2,
  Check,
  Sliders,
  FolderOpen,
  RefreshCw,
  FileSpreadsheet,
  FileCode,
  Sparkles,
} from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';
import { WorkspaceDatasetEntry, GridTransform } from '../../types/globeProject';

export const WorkspaceDataManagerModal: React.FC = () => {
  const {
    isWorkspaceDataModalOpen,
    setWorkspaceDataModalOpen,
    workingDir,
    workspaceDatasets,
    fetchWorkspaceDatasets,
    registerWorkspaceDataset,
    duplicateWorkspaceDataset,
    upsertGrid,
    project,
    setStatusMessage,
  } = useProjectStore();

  const [selectedDsId, setSelectedDsId] = useState<string | null>(null);
  const [duplicateModalOpen, setDuplicateModalOpen] = useState(false);
  const [dupTargetId, setDupTargetId] = useState<string | null>(null);
  const [dupName, setDupName] = useState('');
  const [dupOpSmoothDeg, setDupOpSmoothDeg] = useState(1.5);

  useEffect(() => {
    if (isWorkspaceDataModalOpen) {
      fetchWorkspaceDatasets();
    }
  }, [isWorkspaceDataModalOpen]);

  if (!isWorkspaceDataModalOpen) return null;

  const selectedDs = workspaceDatasets.find((d) => d.id === selectedDsId) || workspaceDatasets[0];

  const handleOpenDuplicate = (ds: WorkspaceDatasetEntry) => {
    setDupTargetId(ds.id);
    setDupName(`${ds.name} (Smoothed)`);
    setDupOpSmoothDeg(1.5);
    setDuplicateModalOpen(true);
  };

  const handleConfirmDuplicate = async () => {
    if (!dupTargetId) return;
    const defaultOps: GridTransform[] = [
      {
        type: 'smooth',
        width_deg: dupOpSmoothDeg,
      },
    ];
    await duplicateWorkspaceDataset(dupTargetId, dupName, defaultOps);
    setDuplicateModalOpen(false);
    setDupTargetId(null);
  };

  const handleInjectIntoProject = (ds: WorkspaceDatasetEntry) => {
    const gridId = ds.id.replace(/[^a-zA-Z0-9_]/g, '_');
    const ops = ds.default_ops || [];
    upsertGrid(gridId, {
      id: gridId,
      source: 'local',
      dataset: ds.physical_path || ds.physical_filename,
      params: {
        lat_var: ds.netcdf_vars?.lat,
        lon_var: ds.netcdf_vars?.lon,
        data_var: ds.netcdf_vars?.data,
      },
      ops: ops,
    });
    setStatusMessage(`Added dataset "${ds.name}" to project grids`);
    setWorkspaceDataModalOpen(false);
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-5xl shadow-2xl flex flex-col overflow-hidden h-[85vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between shrink-0 bg-slate-950/40">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-white">Shared Workspace Data Manager</h3>
                <span className="px-2 py-0.5 rounded-full bg-slate-800 text-[10px] text-slate-300 font-mono">
                  {workspaceDatasets.length} datasets
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono truncate max-w-xl">
                Location: {workingDir}\datasets
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchWorkspaceDatasets()}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              title="Refresh datasets"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              onClick={() => setWorkspaceDataModalOpen(false)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Body Split */}
        <div className="flex-1 flex min-h-0 overflow-hidden">
          {/* Left: Datasets List */}
          <div className="w-1/2 border-r border-slate-800 flex flex-col h-full overflow-hidden">
            <div className="p-3 border-b border-slate-800/80 bg-slate-950/20 flex items-center justify-between text-xs font-semibold text-slate-400">
              <span>Workspace Datasets</span>
              <span className="text-[11px] text-slate-500">Auto-detected from \datasets\</span>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {workspaceDatasets.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full p-8 text-center text-slate-500">
                  <Database className="w-10 h-10 mb-2 opacity-40" />
                  <p className="text-xs font-semibold">No datasets found in workspace</p>
                  <p className="text-[11px] text-slate-600 mt-1 max-w-xs">
                    Drop any NetCDF (.nc/.grd), GeoTIFF (.tif), Shapefile (.shp), or raster into{' '}
                    <code className="text-sky-400">{workingDir}\datasets</code> and click refresh.
                  </p>
                </div>
              ) : (
                workspaceDatasets.map((ds) => {
                  const isSelected = (selectedDs?.id || '') === ds.id;
                  const isVirtual = ds.is_virtual;
                  const sizeMB = (ds.size_bytes / (1024 * 1024)).toFixed(1);

                  return (
                    <div
                      key={ds.id}
                      onClick={() => setSelectedDsId(ds.id)}
                      className={`p-3 rounded-xl border cursor-pointer transition flex items-center justify-between gap-3 ${
                        isSelected
                          ? 'border-sky-500 bg-sky-500/10 text-white shadow'
                          : 'border-slate-800 bg-slate-950/40 text-slate-300 hover:border-slate-700 hover:bg-slate-950/80'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        {/* Thumbnail image or placeholder */}
                        <div className="w-12 h-9 rounded bg-slate-800 border border-slate-700/60 overflow-hidden shrink-0 flex items-center justify-center">
                          <img
                            src={`/api/workspace/datasets/${ds.id}/thumbnail`}
                            alt={ds.name}
                            onError={(e) => {
                              // Hide broken image
                              (e.target as HTMLElement).style.display = 'none';
                            }}
                            className="w-full h-full object-cover"
                          />
                        </div>

                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold truncate text-slate-100">
                              {ds.name}
                            </span>
                            {isVirtual ? (
                              <span className="px-1.5 py-0.2 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[9px] font-mono">
                                Virtual Copy
                              </span>
                            ) : (
                              <span className="px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[9px] font-mono">
                                {ds.file_ext}
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-slate-400 font-mono truncate mt-0.5">
                            {ds.physical_filename} &bull; {sizeMB} MB
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenDuplicate(ds);
                          }}
                          title="Create zero-copy virtual profile with distinct operations"
                          className="p-1.5 rounded-lg bg-slate-800 hover:bg-purple-500/20 text-slate-300 hover:text-purple-300 border border-slate-700 transition"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Right: Selected Dataset Details & Pipelines */}
          <div className="w-1/2 flex flex-col h-full overflow-hidden bg-slate-950/40">
            {selectedDs ? (
              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {/* Dataset Summary Banner */}
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-white">{selectedDs.name}</h4>
                    <span className="text-xs font-mono text-slate-400">ID: {selectedDs.id}</span>
                  </div>
                  <div className="text-xs text-slate-400 font-mono space-y-0.5">
                    <div>File: {selectedDs.physical_filename}</div>
                    <div>Type: {selectedDs.file_type.toUpperCase()}</div>
                    {selectedDs.is_virtual && (
                      <div className="text-purple-300">
                        Zero-copy duplicate referencing shared physical data.
                      </div>
                    )}
                  </div>
                </div>

                {/* NetCDF Coordinate Variables */}
                {selectedDs.file_type === 'grid' && (
                  <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                    <div className="flex items-center gap-2 text-xs font-bold text-slate-200">
                      <Settings2 className="w-4 h-4 text-sky-400" />
                      <span>NetCDF Dimension & Data Variables</span>
                    </div>

                    <div className="grid grid-cols-3 gap-2.5">
                      <div>
                        <label className="block text-[10px] uppercase font-semibold text-slate-400 mb-1">
                          Latitude Variable
                        </label>
                        <input
                          type="text"
                          value={selectedDs.netcdf_vars?.lat || 'lat'}
                          onChange={(e) => {
                            const updatedVars = {
                              ...(selectedDs.netcdf_vars || {}),
                              lat: e.target.value,
                            };
                            registerWorkspaceDataset({
                              id: selectedDs.id,
                              netcdf_vars: updatedVars,
                            });
                          }}
                          className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs text-white font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] uppercase font-semibold text-slate-400 mb-1">
                          Longitude Variable
                        </label>
                        <input
                          type="text"
                          value={selectedDs.netcdf_vars?.lon || 'lon'}
                          onChange={(e) => {
                            const updatedVars = {
                              ...(selectedDs.netcdf_vars || {}),
                              lon: e.target.value,
                            };
                            registerWorkspaceDataset({
                              id: selectedDs.id,
                              netcdf_vars: updatedVars,
                            });
                          }}
                          className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs text-white font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] uppercase font-semibold text-slate-400 mb-1">
                          Data Variable (Z)
                        </label>
                        <input
                          type="text"
                          value={selectedDs.netcdf_vars?.data || 'z'}
                          onChange={(e) => {
                            const updatedVars = {
                              ...(selectedDs.netcdf_vars || {}),
                              data: e.target.value,
                            };
                            registerWorkspaceDataset({
                              id: selectedDs.id,
                              netcdf_vars: updatedVars,
                            });
                          }}
                          className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs text-white font-mono"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Default Declarative Operations */}
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-bold text-slate-200">
                      <Sliders className="w-4 h-4 text-emerald-400" />
                      <span>Default Declarative Pipeline ({selectedDs.default_ops?.length || 0})</span>
                    </div>
                  </div>

                  {(!selectedDs.default_ops || selectedDs.default_ops.length === 0) ? (
                    <div className="text-xs text-slate-500 italic">
                      Raw grid values (no default smoothing or math operations).
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {selectedDs.default_ops.map((op, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between p-2 rounded bg-slate-950 border border-slate-800 text-xs font-mono"
                        >
                          <span className="text-emerald-400 font-semibold">{op.type}</span>
                          <span className="text-slate-400">
                            {op.type === 'smooth' && `width: ${op.width_deg}°`}
                            {op.type === 'fill' && `mode: ${op.fill_mode}`}
                            {op.type === 'math' && `${op.math_op} (${op.operand ?? ''})`}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="pt-2 flex items-center gap-3">
                  <button
                    onClick={() => handleInjectIntoProject(selectedDs)}
                    className="flex-1 py-2 px-4 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 text-xs font-bold flex items-center justify-center gap-2 transition shadow"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Use in Current Project</span>
                  </button>
                  <button
                    onClick={() => handleOpenDuplicate(selectedDs)}
                    className="py-2 px-4 rounded-xl bg-purple-500/20 hover:bg-purple-500 text-purple-300 hover:text-slate-950 border border-purple-500/40 text-xs font-bold flex items-center justify-center gap-2 transition"
                  >
                    <Copy className="w-4 h-4" />
                    <span>Virtual Copy</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-slate-500 text-xs">
                Select a dataset on the left to view and configure its profile.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Zero-Copy Duplicate Modal */}
      {duplicateModalOpen && (
        <div className="fixed inset-0 z-60 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 w-full max-w-md shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-bold text-white flex items-center gap-2">
                <Copy className="w-4 h-4 text-purple-400" />
                <span>Duplicate Dataset Profile (Zero-Copy)</span>
              </h4>
              <button
                onClick={() => setDuplicateModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Creates a new virtual dataset entry with separate default operations without duplicating the underlying file on disk.
            </p>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Virtual Profile Name
              </label>
              <input
                type="text"
                value={dupName}
                onChange={(e) => setDupName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-white"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Gaussian Smoothing: {dupOpSmoothDeg}°
              </label>
              <input
                type="range"
                min={0.5}
                max={10.0}
                step={0.5}
                value={dupOpSmoothDeg}
                onChange={(e) => setDupOpSmoothDeg(Number(e.target.value))}
                className="w-full"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setDuplicateModalOpen(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDuplicate}
                className="px-4 py-1.5 rounded-lg bg-purple-500 hover:bg-purple-400 text-slate-950 text-xs font-bold shadow"
              >
                Create Virtual Copy
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
