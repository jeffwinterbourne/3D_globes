import React, { useEffect } from 'react';
import {
  BookOpen,
  Box,
  Code2,
  Database,
  Download,
  Globe2,
  HardDrive,
  Layers,
  Magnet,
  Palette,
  PanelRightClose,
  PanelRightOpen,
  Redo2,
  Sparkles,
  Undo2,
} from 'lucide-react';
import { useProjectStore } from './store/useProjectStore';
import { ActiveTab } from './types/globeProject';
import { GlobeCanvas } from './components/viewport/GlobeCanvas';
import { ViewportToolbar } from './components/viewport/ViewportToolbar';
import { PresetBrowserModal } from './components/panels/PresetBrowserModal';
import { SimplePaleoPanel } from './components/panels/SimplePaleoPanel';
import { GeometryPanel } from './components/panels/GeometryPanel';
import { GridSourcesPanel } from './components/panels/GridSourcesPanel';
import { DisplacerStackPanel } from './components/panels/DisplacerStackPanel';
import { ColourerStackPanel } from './components/panels/ColourerStackPanel';
import {
  FilamentMixerModal,
  FilamentMixerStudioContent,
} from './components/panels/FilamentMixerModal';
import { MagnetStudioPanel } from './components/panels/MagnetStudioPanel';
import {
  DatasetCacheContent,
  DatasetCacheManagerModal,
} from './components/panels/DatasetCacheManager';
import { ExportPanel } from './components/panels/ExportPanel';
import { JsonCodeEditorPanel } from './components/panels/JsonCodeEditorPanel';

const NAV_TABS: { id: ActiveTab; label: string; icon: React.FC<{ className?: string }> }[] = [
  { id: 'paleo', label: 'Paleo', icon: Globe2 },
  { id: 'geometry', label: 'Geometry', icon: Box },
  { id: 'grids', label: 'Grids', icon: Database },
  { id: 'displacers', label: 'Displace', icon: Layers },
  { id: 'colourers', label: 'Colour', icon: Palette },
  { id: 'filaments', label: 'Filaments', icon: Sparkles },
  { id: 'magnets', label: 'Magnets', icon: Magnet },
  { id: 'datasets', label: 'Cache', icon: HardDrive },
  { id: 'export', label: 'Export', icon: Download },
];

export const App: React.FC = () => {
  const {
    project,
    updateProject,
    activeTab,
    setActiveTab,
    setBuilderMode,
    isRightDrawerOpen,
    setRightDrawerOpen,
    setPresetModalOpen,
    setFilamentModalOpen,
    setDatasetModalOpen,
    undo,
    redo,
    past,
    future,
    fetchGridDataFromBackend,
  } = useProjectStore();

  // Attempt initial sync of downsampled grid buffers when app mounts
  useEffect(() => {
    fetchGridDataFromBackend();
  }, []);

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-950 text-slate-100 overflow-hidden">
      {/* Top Studio Header Bar */}
      <header className="h-13 px-4 py-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between gap-3 shrink-0 z-20">
        {/* Left: Brand & Editable Project Title */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-sky-400 to-emerald-500 flex items-center justify-center shadow">
              <Globe2 className="w-5 h-5 text-slate-950" />
            </div>
            <div>
              <div className="text-xs font-extrabold tracking-wide text-white flex items-center gap-1.5">
                <span>GLOBE3D STUDIO</span>
                <span className="px-1.5 py-0.2 rounded bg-sky-500/20 text-sky-300 text-[10px] font-mono">
                  v4.0
                </span>
              </div>
              <div className="text-[10px] text-slate-400">
                Scientific 3D Printable Geophysical & Paleo CAD
              </div>
            </div>
          </div>

          <div className="h-6 w-px bg-slate-800 mx-1" />

          <input
            type="text"
            value={project.name}
            onChange={(e) =>
              updateProject((d) => {
                d.name = e.target.value;
                return d;
              }, false)
            }
            className="bg-slate-950/90 border border-slate-700/80 hover:border-slate-600 focus:border-sky-500 rounded-lg px-2.5 py-1 text-xs font-semibold text-slate-100 w-64 focus:outline-none"
          />

          <button
            onClick={() => setPresetModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/15 hover:bg-sky-500 text-sky-300 hover:text-slate-950 border border-sky-500/30 text-xs font-semibold transition"
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Presets Gallery (27)</span>
          </button>
        </div>

        {/* Center: Mode Switcher (Simple Paleo Mode vs Custom Recipe Builder) */}
        <div className="hidden lg:flex items-center bg-slate-950 p-1 rounded-lg border border-slate-800">
          <button
            onClick={() => setBuilderMode('paleo')}
            className={`px-3 py-1 rounded-md text-xs font-semibold transition ${
              project.mode === 'paleo'
                ? 'bg-sky-500 text-slate-950 shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Simple Paleo Mode (0–540 Ma)
          </button>
          <button
            onClick={() => setBuilderMode('custom')}
            className={`px-3 py-1 rounded-md text-xs font-semibold transition ${
              project.mode === 'custom'
                ? 'bg-emerald-500 text-slate-950 shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Custom Recipe Stack
          </button>
        </div>

        {/* Right: Undo/Redo, Quick Modals & JSON/Code Drawer Toggle */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={undo}
            disabled={past.length === 0}
            title="Undo"
            className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 disabled:opacity-35 border border-slate-700"
          >
            <Undo2 className="w-4 h-4" />
          </button>
          <button
            onClick={redo}
            disabled={future.length === 0}
            title="Redo"
            className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 disabled:opacity-35 border border-slate-700"
          >
            <Redo2 className="w-4 h-4" />
          </button>

          <button
            onClick={() => setFilamentModalOpen(true)}
            className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-emerald-300 border border-slate-700 text-xs font-medium"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>4-Filament Studio</span>
          </button>

          <button
            onClick={() => setDatasetModalOpen(true)}
            className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-sky-300 border border-slate-700 text-xs font-medium"
          >
            <Database className="w-3.5 h-3.5" />
            <span>Datasets</span>
          </button>

          <button
            onClick={() => setRightDrawerOpen(!isRightDrawerOpen)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-semibold transition ${
              isRightDrawerOpen
                ? 'bg-sky-500/20 border-sky-500/40 text-sky-300'
                : 'bg-slate-800 border-slate-700 text-slate-300 hover:text-white'
            }`}
          >
            <Code2 className="w-3.5 h-3.5" />
            <span>JSON / Python</span>
            {isRightDrawerOpen ? (
              <PanelRightClose className="w-3.5 h-3.5" />
            ) : (
              <PanelRightOpen className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </header>

      {/* Main 3-Column Studio Workspace */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* Column 1: Left Builder Sidebar (Icon Rail + Active Panel) */}
        <aside className="w-[410px] shrink-0 flex bg-slate-950 border-r border-slate-800 h-full overflow-hidden">
          {/* Vertical Icon Tab Rail */}
          <nav className="w-16 shrink-0 bg-slate-900/90 border-r border-slate-800 py-2 flex flex-col items-center gap-1 overflow-y-auto">
            {NAV_TABS.map((t) => {
              const Icon = t.icon;
              const isActive = activeTab === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id)}
                  className={`w-13 py-2 px-1 rounded-xl flex flex-col items-center justify-center gap-1 transition ${
                    isActive
                      ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 font-semibold shadow'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="text-[10px] leading-none">{t.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Active Control Panel Content */}
          <div className="flex-1 overflow-y-auto p-3.5">
            {activeTab === 'paleo' && <SimplePaleoPanel />}
            {activeTab === 'geometry' && <GeometryPanel />}
            {activeTab === 'grids' && <GridSourcesPanel />}
            {activeTab === 'displacers' && <DisplacerStackPanel />}
            {activeTab === 'colourers' && <ColourerStackPanel />}
            {activeTab === 'filaments' && <FilamentMixerStudioContent />}
            {activeTab === 'magnets' && <MagnetStudioPanel />}
            {activeTab === 'datasets' && <DatasetCacheContent />}
            {activeTab === 'export' && <ExportPanel />}
          </div>
        </aside>

        {/* Column 2: Center Interactive 3D Viewport */}
        <main className="flex-1 relative min-w-0 h-full overflow-hidden">
          <ViewportToolbar />
          <GlobeCanvas />
        </main>

        {/* Column 3: Collapsible Right Drawer (Live JSON / Python Code / 2D Map) */}
        {isRightDrawerOpen && (
          <section className="w-[420px] shrink-0 h-full overflow-hidden">
            <JsonCodeEditorPanel />
          </section>
        )}
      </div>

      {/* Studio Modals */}
      <PresetBrowserModal />
      <FilamentMixerModal />
      <DatasetCacheManagerModal />
    </div>
  );
};

export default App;
