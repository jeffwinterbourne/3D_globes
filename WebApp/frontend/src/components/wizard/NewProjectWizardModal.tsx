import React, { useState } from 'react';
import {
  X,
  ChevronRight,
  ChevronLeft,
  Check,
  Box,
  Database,
  Layers,
  Palette,
  Magnet,
  Globe2,
  Sparkles,
} from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';
import { GlobeProject } from '../../types/globeProject';

interface WizardState {
  // Step 1: Base Geometry & Mode
  name: string;
  isPaleo: boolean;
  paleoAge: number;
  radius: number;
  hollow: boolean;
  innerRatio: number;
  resolution: 'draft' | 'standard' | 'high';

  // Step 2: Dataset
  selectedDataset: string;

  // Step 3: Displacement
  displaceTarget: 'outer' | 'inner' | 'both' | 'none';
  vertExagg: number;
  coastlineStep: number;

  // Step 4: Colour
  colormap: string;
  applyInnerColor: boolean;

  // Step 5: Magnets
  magnetsEnabled: boolean;
  nMagnets: number;
  magnetDiameter: number;
  magnetHeight: number;
}

const DEFAULT_WIZARD_STATE: WizardState = {
  name: 'My New Globe',
  isPaleo: false,
  paleoAge: 250,
  radius: 40,
  hollow: true,
  innerRatio: 0.5,
  resolution: 'standard',
  selectedDataset: 'topography.earth',
  displaceTarget: 'outer',
  vertExagg: 40,
  coastlineStep: 0.8,
  colormap: 'terrain',
  applyInnerColor: true,
  magnetsEnabled: true,
  nMagnets: 3,
  magnetDiameter: 5.0,
  magnetHeight: 2.0,
};

const DATASET_OPTIONS = [
  { id: 'topography.earth', name: 'Earth Topography & Bathymetry (ETOPO 2022)', cat: 'topography' },
  { id: 'topography.mars', name: 'Mars MOLA Topography', cat: 'planetary' },
  { id: 'topography.moon', name: 'Moon LOLA Lunar Relief', cat: 'planetary' },
  { id: 'topography.venus', name: 'Venus Magellan Radar Topography', cat: 'planetary' },
  { id: 'topography.mercury', name: 'Mercury Messenger Elevation', cat: 'planetary' },
  { id: 'synthetic.wave', name: 'Procedural Spherical Harmonic Wave (No download)', cat: 'synthetic' },
];

export const NewProjectWizardModal: React.FC = () => {
  const { isWizardOpen, setWizardOpen, saveCurrentProjectToWorkspace, setProject, setCurrentView } =
    useProjectStore();
  const [step, setStep] = useState<number>(1);
  const [form, setForm] = useState<WizardState>(DEFAULT_WIZARD_STATE);

  if (!isWizardOpen) return null;

  const handleFinish = async () => {
    const nPoints =
      form.resolution === 'draft' ? 100000 : form.resolution === 'high' ? 1000000 : 500000;

    const newProject: GlobeProject = {
      $schema: '../../schemas/globe_project.schema.json',
      id: form.name.toLowerCase().replace(/[^a-z0-9]/g, '_'),
      name: form.name,
      category: 'user',
      description: `Created via New Project Wizard (${form.isPaleo ? `${form.paleoAge} Ma Paleo` : form.selectedDataset})`,
      mode: form.isPaleo ? 'paleo' : 'custom',
      paleo: {
        enabled: form.isPaleo,
        age: form.paleoAge,
        resolution: '1d',
        plate_model: 'Scotese_PALEOMAP',
        vert_exagg: form.vertExagg,
        coastline_step: form.coastlineStep * 1000,
        color_mode: 'palette',
        colormap: form.colormap,
        undo_shading: true,
        palette_colors: null,
        mark_poles: true,
        tracked_locations: [],
      },
      geometry: {
        method: 'fibonacci',
        n_points: nPoints,
        preview_n_points: 60000,
        radius: form.radius,
        center: [0, 0, 0],
        hollow: form.hollow,
        inner_ratio: form.hollow ? form.innerRatio : 0.0,
        inner_n_points: null,
        fix_intersection: {
          enabled: true,
          min_thickness: 1.8,
          mode: 'inner',
        },
      },
      custom_recipe: {
        grids: form.isPaleo
          ? []
          : [
              form.selectedDataset.startsWith('synthetic')
                ? {
                    id: 'base_grid',
                    source: 'synthetic',
                    synthetic_type: 'spherical_harmonics',
                    params: { step: 1.0 },
                  }
                : {
                    id: 'base_grid',
                    source: 'online',
                    dataset: form.selectedDataset,
                    params: { resolution: '30m' },
                  },
            ],
        outer_displacements:
          !form.isPaleo && (form.displaceTarget === 'outer' || form.displaceTarget === 'both')
            ? [
                {
                  id: 'outer_disp',
                  type: 'GridDisplacer',
                  grid_id: 'base_grid',
                  scale: form.vertExagg,
                  target: 'outer',
                  smooth: false,
                  coastline_step: form.coastlineStep,
                  normalize: true,
                },
              ]
            : [],
        inner_displacements:
          !form.isPaleo && (form.displaceTarget === 'inner' || form.displaceTarget === 'both')
            ? [
                {
                  id: 'inner_disp',
                  type: 'GridDisplacer',
                  grid_id: 'base_grid',
                  scale: form.vertExagg * 0.5,
                  target: 'inner',
                  smooth: false,
                  coastline_step: 0,
                  normalize: true,
                },
              ]
            : [],
        colourers: form.isPaleo
          ? []
          : [
              {
                id: 'outer_color',
                type: 'GridColourer',
                grid_id: 'base_grid',
                target: 'outer',
                colormap: form.colormap,
                undo_shading: true,
              },
            ],
      },
      filaments: {
        enabled: false,
        preset: 'TERRAIN_4',
        spools: [],
        total_layers: 4,
        layer_height: 0.08,
        vmin: -6000,
        vmax: 4500,
        bands: [],
      },
      magnets: {
        enabled: form.magnetsEnabled,
        diameter: form.magnetDiameter,
        height: form.magnetHeight,
        n_magnets: form.nMagnets,
        position: 0.0,
        horizontal_tolerance: 0.15,
        vertical_tolerance: 0.1,
        vertical_offset: 0.2,
        min_thickness: 1.5,
        allow_bosses: true,
        min_magnets: 2,
        min_angular_spacing: 60.0,
        step_degrees: 2.0,
        placement_strategy: 'cluster_peaks',
        angle_tolerance: 0.0,
      },
      export: {
        mode: 'hemispheres',
        format: '3mf',
        single_file_3mf: true,
        filename: `${form.name.toLowerCase().replace(/[^a-z0-9]/g, '_')}.3mf`,
        top_filename: 'top.obj',
        bottom_filename: 'bottom.obj',
        output_dir: 'outputs',
        hollow: form.hollow,
        engine: 'manifold',
        plane_normal: [0, 0, 1],
        plane_origin: [0, 0, 0],
        flip_bottom: true,
        offset_distance: 85,
        include_color: true,
        fix_normals: true,
        printer_profile: 'snapmaker_u1',
        color_tolerance: 8,
      },
    };

    setProject(newProject);
    setWizardOpen(false);
    setCurrentView('editor');
    await saveCurrentProjectToWorkspace(newProject.id);
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl shadow-2xl flex flex-col overflow-hidden max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-sky-500/20 text-sky-400 flex items-center justify-center">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">New Project Wizard</h3>
              <p className="text-xs text-slate-400">Step {step} of 5</p>
            </div>
          </div>
          <button
            onClick={() => setWizardOpen(false)}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Step Progress Bar */}
        <div className="grid grid-cols-5 border-b border-slate-800 text-[11px] font-semibold">
          {[
            { id: 1, label: 'Geometry', icon: Box },
            { id: 2, label: 'Dataset', icon: Database },
            { id: 3, label: 'Displace', icon: Layers },
            { id: 4, label: 'Colour', icon: Palette },
            { id: 5, label: 'Magnets', icon: Magnet },
          ].map((item) => {
            const Icon = item.icon;
            const isDone = step > item.id;
            const isCurr = step === item.id;
            return (
              <div
                key={item.id}
                onClick={() => setStep(item.id)}
                className={`py-2 px-3 flex items-center justify-center gap-1.5 cursor-pointer transition border-b-2 ${
                  isCurr
                    ? 'border-sky-500 bg-sky-500/10 text-sky-300'
                    : isDone
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-slate-500 hover:text-slate-300'
                }`}
              >
                {isDone ? <Check className="w-3.5 h-3.5" /> : <Icon className="w-3.5 h-3.5" />}
                <span className="hidden sm:inline">{item.label}</span>
              </div>
            );
          })}
        </div>

        {/* Step Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-4">
          {step === 1 && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Project Name
                </label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
                  placeholder="e.g. 40mm Earth Relief Globe"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div
                  onClick={() => setForm({ ...form, isPaleo: false })}
                  className={`p-4 rounded-xl border cursor-pointer transition ${
                    !form.isPaleo
                      ? 'border-sky-500 bg-sky-500/10 text-white'
                      : 'border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  <Globe2 className="w-5 h-5 mb-2 text-sky-400" />
                  <div className="text-xs font-bold">Modern / Planetary Globe</div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    Earth, Mars, Moon, Venus or custom geophysical grids.
                  </div>
                </div>

                <div
                  onClick={() => setForm({ ...form, isPaleo: true })}
                  className={`p-4 rounded-xl border cursor-pointer transition ${
                    form.isPaleo
                      ? 'border-purple-500 bg-purple-500/10 text-white'
                      : 'border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  <Layers className="w-5 h-5 mb-2 text-purple-400" />
                  <div className="text-xs font-bold">Deep-Time Paleo Globe</div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    Scotese PALEOMAP reconstructions (0 to 540 Ma).
                  </div>
                </div>
              </div>

              {form.isPaleo && (
                <div className="p-3 bg-purple-500/10 border border-purple-500/30 rounded-xl space-y-2">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-purple-300">Geological Age</span>
                    <span className="text-white font-mono">{form.paleoAge} Ma</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={540}
                    step={5}
                    value={form.paleoAge}
                    onChange={(e) => setForm({ ...form, paleoAge: Number(e.target.value) })}
                    className="w-full"
                  />
                </div>
              )}

              <div className="grid grid-cols-2 gap-3 pt-2">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Outer Radius: {form.radius} mm
                  </label>
                  <input
                    type="range"
                    min={20}
                    max={120}
                    value={form.radius}
                    onChange={(e) => setForm({ ...form, radius: Number(e.target.value) })}
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Shell Type
                  </label>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setForm({ ...form, hollow: true })}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-semibold border ${
                        form.hollow
                          ? 'border-sky-500 bg-sky-500/20 text-sky-300'
                          : 'border-slate-800 bg-slate-950 text-slate-400'
                      }`}
                    >
                      Hollow
                    </button>
                    <button
                      type="button"
                      onClick={() => setForm({ ...form, hollow: false })}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-semibold border ${
                        !form.hollow
                          ? 'border-sky-500 bg-sky-500/20 text-sky-300'
                          : 'border-slate-800 bg-slate-950 text-slate-400'
                      }`}
                    >
                      Solid
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-3">
              <label className="block text-xs font-semibold text-slate-300">
                Choose Base Geophysical Dataset
              </label>
              <div className="grid grid-cols-1 gap-2">
                {DATASET_OPTIONS.map((ds) => (
                  <div
                    key={ds.id}
                    onClick={() => setForm({ ...form, selectedDataset: ds.id })}
                    className={`p-3 rounded-xl border cursor-pointer flex items-center justify-between transition ${
                      form.selectedDataset === ds.id
                        ? 'border-sky-500 bg-sky-500/10 text-white'
                        : 'border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div>
                      <div className="text-xs font-bold text-slate-200">{ds.name}</div>
                      <div className="text-[10px] text-slate-500 uppercase">{ds.cat}</div>
                    </div>
                    {form.selectedDataset === ds.id && (
                      <Check className="w-4 h-4 text-sky-400 shrink-0" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Displacement Target
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { id: 'outer', label: 'Outer Shell Only' },
                    { id: 'both', label: 'Outer & Inner Cavity' },
                    { id: 'none', label: 'No Displacement' },
                  ].map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => setForm({ ...form, displaceTarget: t.id as any })}
                      className={`py-2 px-3 rounded-xl text-xs font-semibold border transition ${
                        form.displaceTarget === t.id
                          ? 'border-sky-500 bg-sky-500/20 text-sky-300'
                          : 'border-slate-800 bg-slate-950 text-slate-400'
                      }`}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-semibold mb-1">
                  <span className="text-slate-300">Vertical Exaggeration</span>
                  <span className="text-sky-400 font-mono">{form.vertExagg}x</span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={80}
                  value={form.vertExagg}
                  onChange={(e) => setForm({ ...form, vertExagg: Number(e.target.value) })}
                  className="w-full"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs font-semibold mb-1">
                  <span className="text-slate-300">Coastline Step (0.0 to 2.0 mm)</span>
                  <span className="text-sky-400 font-mono">{form.coastlineStep} mm</span>
                </div>
                <input
                  type="range"
                  min={0.0}
                  max={2.0}
                  step={0.1}
                  value={form.coastlineStep}
                  onChange={(e) => setForm({ ...form, coastlineStep: Number(e.target.value) })}
                  className="w-full"
                />
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4">
              <label className="block text-xs font-semibold text-slate-300">
                Hypsometric Colormap
              </label>
              <div className="grid grid-cols-2 gap-2.5">
                {[
                  { id: 'terrain', name: 'Terrain (Earth Relief)' },
                  { id: 'viridis', name: 'Viridis (Scientific)' },
                  { id: 'magma', name: 'Magma (Planetary)' },
                  { id: 'gist_earth', name: 'Gist Earth (Paleo Classic)' },
                  { id: 'seismic', name: 'Seismic (Diverging)' },
                  { id: 'turbo', name: 'Turbo (High Contrast)' },
                ].map((c) => (
                  <div
                    key={c.id}
                    onClick={() => setForm({ ...form, colormap: c.id })}
                    className={`p-3 rounded-xl border cursor-pointer flex items-center justify-between transition ${
                      form.colormap === c.id
                        ? 'border-sky-500 bg-sky-500/20 text-sky-200'
                        : 'border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <span className="text-xs font-bold">{c.name}</span>
                    {form.colormap === c.id && <Check className="w-4 h-4 text-sky-400" />}
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 5 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950 border border-slate-800">
                <div>
                  <div className="text-xs font-bold text-white">Embed Equatorial Magnets</div>
                  <div className="text-[11px] text-slate-400">
                    Voids in equatorial rim to snap hemispheres together.
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={form.magnetsEnabled}
                  onChange={(e) => setForm({ ...form, magnetsEnabled: e.target.checked })}
                  className="w-4 h-4 rounded text-sky-500"
                />
              </div>

              {form.magnetsEnabled && (
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                      Count
                    </label>
                    <input
                      type="number"
                      min={2}
                      max={8}
                      value={form.nMagnets}
                      onChange={(e) => setForm({ ...form, nMagnets: Number(e.target.value) })}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                      Diameter (mm)
                    </label>
                    <input
                      type="number"
                      step={0.5}
                      value={form.magnetDiameter}
                      onChange={(e) => setForm({ ...form, magnetDiameter: Number(e.target.value) })}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                      Height (mm)
                    </label>
                    <input
                      type="number"
                      step={0.5}
                      value={form.magnetHeight}
                      onChange={(e) => setForm({ ...form, magnetHeight: Number(e.target.value) })}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white"
                    />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Navigation */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between">
          <button
            onClick={() => setStep(Math.max(1, step - 1))}
            disabled={step === 1}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 text-xs font-semibold transition"
          >
            <ChevronLeft className="w-4 h-4" />
            <span>Back</span>
          </button>

          {step < 5 ? (
            <button
              onClick={() => setStep(step + 1)}
              className="flex items-center gap-1 px-4 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 text-xs font-bold transition shadow"
            >
              <span>Next</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleFinish}
              className="flex items-center gap-1.5 px-5 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-sky-500 hover:from-emerald-400 hover:to-sky-400 text-slate-950 text-xs font-extrabold transition shadow-lg shadow-emerald-500/20"
            >
              <Check className="w-4 h-4" />
              <span>Create & Open Project</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
