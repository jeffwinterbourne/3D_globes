import React, { useEffect, useState } from 'react';
import {
  Globe2,
  FolderOpen,
  Sparkles,
  Layers,
  Database,
  BookOpen,
  Copy,
  Clock,
  PlusCircle,
  FileCode,
  ArrowRight,
  FolderCog,
  RefreshCw,
} from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';

export const LandingPage: React.FC = () => {
  const {
    workingDir,
    fetchWorkspaceConfig,
    setWorkingDir,
    projectsList,
    fetchWorkspaceProjects,
    openWorkspaceProject,
    openWorkspaceProjectAsCopy,
    loadBlankProject,
    setWizardOpen,
    setPresetModalOpen,
    setWorkspaceDataModalOpen,
  } = useProjectStore();

  const [isEditingDir, setIsEditingDir] = useState(false);
  const [dirInput, setDirInput] = useState('');

  useEffect(() => {
    fetchWorkspaceConfig();
    fetchWorkspaceProjects();
  }, []);

  useEffect(() => {
    if (workingDir) {
      setDirInput(workingDir);
    }
  }, [workingDir]);

  const handleApplyDir = () => {
    if (dirInput.trim()) {
      setWorkingDir(dirInput.trim());
      setIsEditingDir(false);
    }
  };

  return (
    <div className="h-screen w-screen bg-slate-950 text-slate-100 flex flex-col overflow-y-auto select-none">
      {/* Top Header */}
      <header className="h-16 px-8 bg-slate-900/80 border-b border-slate-800 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sky-400 to-emerald-500 flex items-center justify-center shadow-lg shadow-sky-500/20">
            <Globe2 className="w-6 h-6 text-slate-950" />
          </div>
          <div>
            <div className="text-base font-extrabold tracking-wide text-white flex items-center gap-2">
              <span>GLOBE3D STUDIO</span>
              <span className="px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-300 text-[11px] font-mono border border-sky-500/30">
                v5.0
              </span>
            </div>
            <div className="text-xs text-slate-400">
              Interactive 3D Printable Geophysical & Paleo CAD
            </div>
          </div>
        </div>

        {/* Working Directory Bar */}
        <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-800 rounded-xl px-3.5 py-1.5 max-w-xl">
          <FolderOpen className="w-4 h-4 text-amber-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
              Working Folder
            </div>
            {isEditingDir ? (
              <div className="flex items-center gap-2 mt-0.5">
                <input
                  type="text"
                  value={dirInput}
                  onChange={(e) => setDirInput(e.target.value)}
                  className="bg-slate-900 border border-sky-500 text-xs px-2 py-0.5 rounded text-white font-mono w-72 focus:outline-none"
                  placeholder="D:\my_workspace"
                />
                <button
                  onClick={handleApplyDir}
                  className="px-2 py-0.5 bg-sky-500 text-slate-950 rounded text-xs font-bold hover:bg-sky-400"
                >
                  Save
                </button>
                <button
                  onClick={() => setIsEditingDir(false)}
                  className="px-2 py-0.5 bg-slate-800 text-slate-300 rounded text-xs hover:bg-slate-700"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <div
                onClick={() => setIsEditingDir(true)}
                className="text-xs font-mono text-slate-200 truncate cursor-pointer hover:text-sky-300 transition"
                title="Click to change folder"
              >
                {workingDir || 'Detecting working directory...'}
              </div>
            )}
          </div>
          <button
            onClick={() => setIsEditingDir(!isEditingDir)}
            className="p-1 text-slate-400 hover:text-amber-300 rounded transition"
            title="Change workspace folder"
          >
            <FolderCog className="w-4 h-4" />
          </button>
          <button
            onClick={() => fetchWorkspaceProjects()}
            className="p-1 text-slate-400 hover:text-sky-300 rounded transition"
            title="Refresh projects list"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 max-w-7xl mx-auto w-full px-8 py-8 flex flex-col gap-8">
        {/* Hero Quick-Start Cards */}
        <section>
          <h2 className="text-xs uppercase tracking-wider text-slate-400 font-bold mb-3">
            Start a Project
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 1. New Project (Wizard) */}
            <div
              onClick={() => setWizardOpen(true)}
              className="group p-5 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-900/60 border border-slate-800 hover:border-sky-500/50 hover:shadow-xl hover:shadow-sky-500/10 cursor-pointer transition flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-xl bg-sky-500/20 text-sky-400 flex items-center justify-center mb-3 group-hover:scale-110 transition">
                  <Sparkles className="w-5 h-5" />
                </div>
                <h3 className="text-sm font-bold text-white group-hover:text-sky-300 transition">
                  New Project (Wizard)
                </h3>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                  Interactive 5-step guided setup: specify geometry, datasets, displacement, colors, and embedded magnets.
                </p>
              </div>
              <div className="mt-4 flex items-center gap-1.5 text-xs font-semibold text-sky-400">
                <span>Start Guided Setup</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
              </div>
            </div>

            {/* 2. New Project (Blank) */}
            <div
              onClick={loadBlankProject}
              className="group p-5 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-900/60 border border-slate-800 hover:border-emerald-500/50 hover:shadow-xl hover:shadow-emerald-500/10 cursor-pointer transition flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center mb-3 group-hover:scale-110 transition">
                  <PlusCircle className="w-5 h-5" />
                </div>
                <h3 className="text-sm font-bold text-white group-hover:text-emerald-300 transition">
                  New Project (Blank)
                </h3>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                  Start with a clean 40mm hollow sphere with zero datasets or displacements. Build custom recipes from scratch.
                </p>
              </div>
              <div className="mt-4 flex items-center gap-1.5 text-xs font-semibold text-emerald-400">
                <span>Open Blank Canvas</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
              </div>
            </div>

            {/* 3. Load from Gallery */}
            <div
              onClick={() => setPresetModalOpen(true)}
              className="group p-5 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-900/60 border border-slate-800 hover:border-purple-500/50 hover:shadow-xl hover:shadow-purple-500/10 cursor-pointer transition flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-xl bg-purple-500/20 text-purple-400 flex items-center justify-center mb-3 group-hover:scale-110 transition">
                  <BookOpen className="w-5 h-5" />
                </div>
                <h3 className="text-sm font-bold text-white group-hover:text-purple-300 transition">
                  Load from Gallery
                </h3>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                  Browse 27 curated scientific presets with pre-rendered visual previews, planetary models, and paleo reconstructions.
                </p>
              </div>
              <div className="mt-4 flex items-center gap-1.5 text-xs font-semibold text-purple-400">
                <span>Browse Presets (27)</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
              </div>
            </div>

            {/* 4. Shared Dataset Manager */}
            <div
              onClick={() => setWorkspaceDataModalOpen(true)}
              className="group p-5 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-900/60 border border-slate-800 hover:border-amber-500/50 hover:shadow-xl hover:shadow-amber-500/10 cursor-pointer transition flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center mb-3 group-hover:scale-110 transition">
                  <Database className="w-5 h-5" />
                </div>
                <h3 className="text-sm font-bold text-white group-hover:text-amber-300 transition">
                  Shared Data Manager
                </h3>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                  Manage user grids and shapefiles across projects. Create zero-copy virtual dataset duplicates with smoothing and math.
                </p>
              </div>
              <div className="mt-4 flex items-center gap-1.5 text-xs font-semibold text-amber-400">
                <span>Manage Datasets</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
              </div>
            </div>
          </div>
        </section>

        {/* Continue a Previous Project Section */}
        <section className="flex-1 flex flex-col min-h-0">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-sky-400" />
              <h2 className="text-xs uppercase tracking-wider text-slate-400 font-bold">
                Continue a Project ({projectsList.length})
              </h2>
            </div>
            <span className="text-xs text-slate-500 font-mono">
              Folder: {workingDir}\projects
            </span>
          </div>

          {projectsList.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center p-12 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800 text-center">
              <FileCode className="w-12 h-12 text-slate-600 mb-3" />
              <h4 className="text-sm font-semibold text-slate-300">
                No projects saved in this workspace yet
              </h4>
              <p className="text-xs text-slate-500 max-w-sm mt-1">
                Click "New Project (Wizard)" or "New Project (Blank)" above, or choose an example from the Presets Gallery.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {projectsList.map((p) => (
                <div
                  key={p.slug}
                  className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-slate-700 transition flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-sm font-bold text-white hover:text-sky-300 transition line-clamp-1">
                        {p.name}
                      </h4>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${
                          p.paleo_enabled
                            ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                            : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        }`}
                      >
                        {p.paleo_enabled ? `${p.paleo_age} Ma` : p.mode}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                      {p.description || 'No description provided.'}
                    </p>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between">
                    <span className="text-[11px] text-slate-500 font-mono">
                      {p.updated_at_iso || 'Recently'}
                    </span>
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => openWorkspaceProjectAsCopy(p.slug)}
                        title="Open as a new copy without modifying the original"
                        className="flex items-center gap-1 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold border border-slate-700 transition"
                      >
                        <Copy className="w-3 h-3" />
                        <span>Copy</span>
                      </button>
                      <button
                        onClick={() => openWorkspaceProject(p.slug)}
                        className="flex items-center gap-1 px-2.5 py-1 rounded bg-sky-500/20 hover:bg-sky-500 text-sky-300 hover:text-slate-950 text-xs font-bold border border-sky-500/30 transition shadow"
                      >
                        <span>Open</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
