import React, { useEffect, useState } from 'react';
import {
  Compass,
  Globe2,
  Layers,
  MapPin,
  Palette,
  Plus,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';
import { DEFAULT_STARTER_PROJECT } from '../../types/globeProject';

interface ScoteseSlice {
  age: number;
  name: string;
  era: 'Cenozoic' | 'Mesozoic' | 'Paleozoic';
}

const SCOTESE_88_SLICES: ScoteseSlice[] = [
  { age: 0, name: 'Present Day (Holocene)', era: 'Cenozoic' },
  { age: 10, name: 'Late Miocene (10 Ma)', era: 'Cenozoic' },
  { age: 20, name: 'Early Miocene (20 Ma)', era: 'Cenozoic' },
  { age: 30, name: 'Oligocene (30 Ma)', era: 'Cenozoic' },
  { age: 40, name: 'Middle Eocene (40 Ma)', era: 'Cenozoic' },
  { age: 50, name: 'Early Eocene (50 Ma)', era: 'Cenozoic' },
  { age: 66, name: 'K-Pg Boundary (Chicxulub Impact, 66 Ma)', era: 'Mesozoic' },
  { age: 90, name: 'Mid-Cretaceous Turonian (90 Ma)', era: 'Mesozoic' },
  { age: 120, name: 'Early Cretaceous Aptian (120 Ma)', era: 'Mesozoic' },
  { age: 150, name: 'Late Jurassic Tithonian (150 Ma)', era: 'Mesozoic' },
  { age: 180, name: 'Early Jurassic Toarcian (180 Ma)', era: 'Mesozoic' },
  { age: 200, name: 'Triassic-Jurassic Boundary (200 Ma)', era: 'Mesozoic' },
  { age: 220, name: 'Late Triassic Norian (220 Ma)', era: 'Mesozoic' },
  { age: 250, name: 'Permian-Triassic Boundary (Pangaea, 250 Ma)', era: 'Paleozoic' },
  { age: 280, name: 'Early Permian Artinskian (280 Ma)', era: 'Paleozoic' },
  { age: 300, name: 'Late Carboniferous (Coal Swamps, 300 Ma)', era: 'Paleozoic' },
  { age: 340, name: 'Early Carboniferous Visean (340 Ma)', era: 'Paleozoic' },
  { age: 380, name: 'Late Devonian Frasnian (380 Ma)', era: 'Paleozoic' },
  { age: 420, name: 'Late Silurian Pridoli (420 Ma)', era: 'Paleozoic' },
  { age: 450, name: 'Late Ordovician Katian (450 Ma)', era: 'Paleozoic' },
  { age: 500, name: 'Late Cambrian Furongian (500 Ma)', era: 'Paleozoic' },
  { age: 540, name: 'Early Cambrian Terreneuvian (540 Ma)', era: 'Paleozoic' },
];

export const SimplePaleoPanel: React.FC = () => {
  const {
    project,
    updatePaleo,
    convertPaleoToCustomRecipe,
    setFilamentModalOpen,
  } = useProjectStore();

  const paleo = project.paleo || DEFAULT_STARTER_PROJECT.paleo!;
  const [catalogSlices, setCatalogSlices] = useState<ScoteseSlice[]>(SCOTESE_88_SLICES);
  const [reconstructedCoords, setReconstructedCoords] = useState<
    Record<string, { paleo_lat: number; paleo_lon: number }>
  >({});

  const [newCityName, setNewCityName] = useState('');
  const [newCityLat, setNewCityLat] = useState('51.5');
  const [newCityLon, setNewCityLon] = useState('-0.12');

  useEffect(() => {
    fetch('/api/paleo/catalog')
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.maps) && data.maps.length > 0) {
          const mapped: ScoteseSlice[] = data.maps.map((m: any) => {
            const age = Number(m.age_ma ?? m.age ?? 0);
            const era =
              age <= 66 ? 'Cenozoic' : age <= 252 ? 'Mesozoic' : 'Paleozoic';
            return {
              age,
              name: m.name || m.title || `${age} Ma`,
              era,
            };
          });
          setCatalogSlices(mapped);
        }
      })
      .catch(() => {});
  }, []);

  // Live plate reconstruction of tracked modern cities via /api/paleo/reconstruct-points
  useEffect(() => {
    const locs = paleo.tracked_locations || [];
    if (locs.length === 0) return;

    fetch('/api/paleo/reconstruct-points', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        age: paleo.age,
        plate_model: paleo.plate_model || 'Scotese_PALEOMAP',
        locations: locs.map((l) => ({ name: l.name, lat: l.lat, lon: l.lon })),
      }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.reconstructed)) {
          const nextMap: Record<string, { paleo_lat: number; paleo_lon: number }> = {};
          for (const item of data.reconstructed) {
            nextMap[item.name] = {
              paleo_lat: Number(item.paleo_lat?.toFixed(2) ?? item.lat ?? 0),
              paleo_lon: Number(item.paleo_lon?.toFixed(2) ?? item.lon ?? 0),
            };
          }
          setReconstructedCoords(nextMap);
        }
      })
      .catch(() => {
        // Approximate drift fallback when offline
        const nextMap: Record<string, { paleo_lat: number; paleo_lon: number }> = {};
        for (const l of locs) {
          nextMap[l.name] = {
            paleo_lat: Number((l.lat - paleo.age * 0.14).toFixed(1)),
            paleo_lon: Number((l.lon + paleo.age * 0.08).toFixed(1)),
          };
        }
        setReconstructedCoords(nextMap);
      });
  }, [paleo.age, paleo.plate_model, paleo.tracked_locations]);

  const currentEra =
    paleo.age <= 66 ? 'Cenozoic' : paleo.age <= 252 ? 'Mesozoic' : 'Paleozoic';

  const eraColor =
    currentEra === 'Cenozoic'
      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
      : currentEra === 'Mesozoic'
      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
      : 'bg-purple-500/20 text-purple-300 border-purple-500/40';

  const handleAddLocation = () => {
    if (!newCityName.trim()) return;
    const next = [
      ...(paleo.tracked_locations || []),
      {
        name: newCityName.trim(),
        lat: parseFloat(newCityLat) || 0,
        lon: parseFloat(newCityLon) || 0,
        symbol: 'star',
        color: '#ef4444',
        size: 2.5,
      },
    ];
    updatePaleo({ tracked_locations: next });
    setNewCityName('');
  };

  const handleRemoveLocation = (idx: number) => {
    const next = (paleo.tracked_locations || []).filter((_, i) => i !== idx);
    updatePaleo({ tracked_locations: next });
  };

  return (
    <div className="space-y-4 text-xs">
      {/* Header Banner */}
      <div className="p-3 rounded-xl bg-gradient-to-br from-sky-950/60 to-slate-900 border border-sky-500/30">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-1.5 font-bold text-sky-300 text-sm">
            <Globe2 className="w-4 h-4" />
            <span>Simple Paleo Mode (GlobeModel.from_paleo)</span>
          </div>
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${eraColor}`}>
            {currentEra} ({paleo.age} Ma)
          </span>
        </div>
        <p className="text-slate-400 text-[11px]">
          Streamlined deep-time tectonic reconstruction (0–540 Ma) with automatic Zenodo/EarthByte Scotese PaleoDEM & PaleoAtlas caching.
        </p>
      </div>

      {/* 1. Geological Time Slider & 88-Slice Map Selector */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
        <div className="flex items-center justify-between">
          <label className="font-semibold text-slate-200">Geological Age (0 – 540 Ma)</label>
          <span className="font-mono text-sm font-bold text-sky-400">{paleo.age} Ma</span>
        </div>

        <input
          type="range"
          min={0}
          max={540}
          step={5}
          value={paleo.age}
          onChange={(e) => updatePaleo({ age: Number(e.target.value) })}
          className="w-full"
        />

        <div className="flex justify-between text-[10px] text-slate-400 font-medium">
          <span className="text-amber-300">0 Ma (Cenozoic)</span>
          <span className="text-emerald-300">66–252 Ma (Mesozoic)</span>
          <span className="text-purple-300">252–540 Ma (Paleozoic)</span>
        </div>

        <div>
          <label className="block text-slate-400 mb-1">Scotese PALEOMAP Time Slice (88 Maps)</label>
          <select
            value={paleo.age}
            onChange={(e) => updatePaleo({ age: Number(e.target.value) })}
            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-100"
          >
            {catalogSlices.map((s, idx) => (
              <option key={`${s.age}_${s.name}_${idx}`} value={s.age}>
                {s.age} Ma — {s.name} [{s.era}]
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-2.5">
          <div>
            <label className="block text-slate-400 mb-1">DEM Resolution</label>
            <select
              value={paleo.resolution}
              onChange={(e) => updatePaleo({ resolution: e.target.value as '6m' | '1d' })}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-100"
            >
              <option value="1d">1° x 1° (Fast / Standard)</option>
              <option value="6m">6 arc-min (High Detail)</option>
            </select>
          </div>

          <div>
            <label className="block text-slate-400 mb-1">Plate Tectonic Model</label>
            <select
              value={paleo.plate_model}
              onChange={(e) => updatePaleo({ plate_model: e.target.value })}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-100"
            >
              <option value="Scotese_PALEOMAP">Scotese_PALEOMAP</option>
              <option value="Seton2012">Seton2012</option>
              <option value="Muller2016">Muller2016</option>
              <option value="Merdith2021">Merdith2021 (1 Ga – 0 Ma)</option>
              <option value="custom">Custom .rot / .gpml</option>
            </select>
          </div>
        </div>

        {paleo.plate_model === 'custom' && (
          <div className="grid grid-cols-1 gap-2 pt-1">
            <input
              type="text"
              placeholder="Path to custom .rot rotation file..."
              value={paleo.custom_rot_path || ''}
              onChange={(e) => updatePaleo({ custom_rot_path: e.target.value })}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200"
            />
            <input
              type="text"
              placeholder="Path to custom .gpml topology file..."
              value={paleo.custom_gpml_path || ''}
              onChange={(e) => updatePaleo({ custom_gpml_path: e.target.value })}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200"
            />
          </div>
        )}
      </div>

      {/* 2. Relief Exaggeration & Coastline Step */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
        <h3 className="font-semibold text-slate-200 flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-sky-400" />
          <span>Paleo Relief & Coastline Step</span>
        </h3>

        <div>
          <div className="flex justify-between mb-1">
            <span className="text-slate-400">Vertical Exaggeration</span>
            <span className="font-mono text-sky-400">{paleo.vert_exagg}x</span>
          </div>
          <input
            type="range"
            min={1}
            max={120}
            step={1}
            value={paleo.vert_exagg}
            onChange={(e) => updatePaleo({ vert_exagg: Number(e.target.value) })}
            className="w-full"
          />
        </div>

        <div>
          <div className="flex justify-between mb-1">
            <span className="text-slate-400">Coastline Elevation Step (m equiv.)</span>
            <span className="font-mono text-sky-400">{paleo.coastline_step} m</span>
          </div>
          <input
            type="range"
            min={0}
            max={3000}
            step={100}
            value={paleo.coastline_step}
            onChange={(e) => updatePaleo({ coastline_step: Number(e.target.value) })}
            className="w-full"
          />
        </div>
      </div>

      {/* 3. Colouring Mode Toggle */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
        <h3 className="font-semibold text-slate-200 flex items-center gap-1.5">
          <Palette className="w-3.5 h-3.5 text-emerald-400" />
          <span>Paleo Surface Colouring Mode</span>
        </h3>

        <div className="grid grid-cols-3 gap-1.5">
          {[
            { id: 'paleo_atlas', label: 'PaleoAtlas RGB' },
            { id: 'filament_banded', label: '4-Filament Banded' },
            { id: 'scientific_cmap', label: 'Scientific Cmap' },
          ].map((m) => (
            <button
              key={m.id}
              onClick={() => updatePaleo({ color_mode: m.id as any })}
              className={`py-1.5 px-2 rounded-lg font-medium border text-center transition ${
                paleo.color_mode === m.id
                  ? 'bg-sky-500/20 border-sky-400 text-sky-300 font-semibold'
                  : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        {paleo.color_mode === 'paleo_atlas' && (
          <div className="flex items-center justify-between pt-1">
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={paleo.undo_shading}
                onChange={(e) => updatePaleo({ undo_shading: e.target.checked })}
              />
              <span>Undo Baked Hillshading (undo_hillshading)</span>
            </label>
          </div>
        )}

        {paleo.color_mode === 'filament_banded' && (
          <button
            onClick={() => setFilamentModalOpen(true)}
            className="w-full py-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 font-semibold transition"
          >
            Open 4-Filament Optical Mixing & Banded Colormap Studio
          </button>
        )}

        {paleo.color_mode === 'scientific_cmap' && (
          <div>
            <label className="block text-slate-400 mb-1">Scientific Colormap</label>
            <select
              value={paleo.colormap || 'terrain'}
              onChange={(e) => updatePaleo({ colormap: e.target.value })}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-100"
            >
              <option value="terrain">terrain</option>
              <option value="viridis">viridis</option>
              <option value="plasma">plasma</option>
              <option value="magma">magma</option>
              <option value="RdBu_r">RdBu_r</option>
              <option value="coolwarm">coolwarm</option>
            </select>
          </div>
        )}
      </div>

      {/* 4. Tracked Modern Landmarks & Pole Markers */}
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-slate-200 flex items-center gap-1.5">
            <MapPin className="w-3.5 h-3.5 text-rose-400" />
            <span>Tracked Modern Locations & Pole Markers</span>
          </h3>
          <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={paleo.mark_poles}
              onChange={(e) => updatePaleo({ mark_poles: e.target.checked })}
            />
            <span>Mark N/S Poles</span>
          </label>
        </div>

        <div className="space-y-1.5">
          {(paleo.tracked_locations || []).map((loc, idx) => {
            const recon = reconstructedCoords[loc.name];
            return (
              <div
                key={idx}
                className="flex items-center justify-between bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5"
              >
                <div>
                  <div className="font-semibold text-slate-200 flex items-center gap-1.5">
                    <span
                      className="w-2.5 h-2.5 rounded-full inline-block"
                      style={{ backgroundColor: String(loc.color || '#ef4444') }}
                    />
                    <span>{loc.name}</span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      (Modern: {loc.lat}°, {loc.lon}°)
                    </span>
                  </div>
                  {recon && (
                    <div className="text-[10px] font-mono text-emerald-400">
                      → Reconstructed @ {paleo.age} Ma: {recon.paleo_lat}°, {recon.paleo_lon}°
                    </div>
                  )}
                </div>
                <button
                  onClick={() => handleRemoveLocation(idx)}
                  className="p-1 text-slate-500 hover:text-rose-400"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })}
        </div>

        {/* Add City Form */}
        <div className="grid grid-cols-12 gap-1.5 pt-1">
          <input
            type="text"
            placeholder="City (e.g. London)"
            value={newCityName}
            onChange={(e) => setNewCityName(e.target.value)}
            className="col-span-5 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
          />
          <input
            type="number"
            step="0.1"
            placeholder="Lat"
            value={newCityLat}
            onChange={(e) => setNewCityLat(e.target.value)}
            className="col-span-3 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
          />
          <input
            type="number"
            step="0.1"
            placeholder="Lon"
            value={newCityLon}
            onChange={(e) => setNewCityLon(e.target.value)}
            className="col-span-3 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
          />
          <button
            onClick={handleAddLocation}
            title="Add Modern Landmark"
            className="col-span-1 flex items-center justify-center bg-sky-500 hover:bg-sky-400 text-slate-950 rounded font-bold"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* 5. Convert to Custom Recipe Stack Button */}
      <button
        onClick={convertPaleoToCustomRecipe}
        className="w-full py-2.5 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-100 font-semibold flex items-center justify-center gap-2 transition shadow"
      >
        <Layers className="w-4 h-4 text-sky-400" />
        <span>Convert to Custom Recipe Stack (Editable Layers)</span>
      </button>
    </div>
  );
};
