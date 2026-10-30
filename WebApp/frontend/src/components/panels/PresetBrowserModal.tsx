import React, { useEffect, useState } from 'react';
import { BookOpen, Download, FolderOpen, Search, Upload, X } from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';
import { DEFAULT_STARTER_PROJECT, GlobeProject } from '../../types/globeProject';

interface PresetMetadata {
  id: string;
  name: string;
  category: string;
  subcategory?: string;
  description: string;
  path?: string;
}

const FALLBACK_27_PRESETS: PresetMetadata[] = [
  {
    id: 'example_1_basic_globe',
    name: 'Example 1: Basic Solid Topography Globe',
    category: 'Standard Examples',
    description: '40mm Fibonacci sphere (5k pts), 40x ETOPO displacement -> STL',
  },
  {
    id: 'example_2_intermediate_globe',
    name: 'Example 2: Coastline Step & Split Hemispheres',
    category: 'Standard Examples',
    description: '40x ETOPO + 0.8mm LineDisplacer coastline step + solid split hemispheres -> STL',
  },
  {
    id: 'example_3a_magnets_with_bosses',
    name: 'Example 3A: Hollow Globe + 3 Magnets (With Bosses)',
    category: 'Standard Examples',
    description: 'Hollow globe (inner_ratio=0.5), 3 magnets (5x2mm, allow_bosses=True)',
  },
  {
    id: 'example_3b_magnets_no_bosses',
    name: 'Example 3B: Hollow Globe + 3 Magnets (Zero Bosses)',
    category: 'Standard Examples',
    description: 'Hollow globe (inner_ratio=0.5), 3 magnets optimized into thick wall peaks (allow_bosses=False)',
  },
  {
    id: 'example_4_coloured_globe',
    name: 'Example 4: Coloured Globe (Complete Pipeline)',
    category: 'Standard Examples',
    description: 'ETOPO + coastline step + magnets + S40RTS RdBu_r outer + gray inner -> OBJ',
  },
  {
    id: 'example_5_1_constant',
    name: 'Example 5.1: Constant Sky-Blue Colouring',
    category: 'Standard Examples',
    description: 'ConstantColourer [0.1, 0.5, 0.8] on outer surface',
  },
  {
    id: 'example_5_2_image',
    name: 'Example 5.2: Equirectangular Image Texture',
    category: 'Standard Examples',
    description: 'Procedural equirectangular gradient texture + ImageColourer',
  },
  {
    id: 'example_5_3_grid_terrain',
    name: 'Example 5.3: High-Res ETOPO Terrain Colormap',
    category: 'Standard Examples',
    description: '1M-point globe coloured with ETOPO terrain colormap (-5000m to 5000m)',
  },
  {
    id: 'example_5_4_shapefiles_capitals',
    name: 'Example 5.4: Land Polygons & World Capitals',
    category: 'Standard Examples',
    description: 'PolygonColourer (green land, blue ocean) + PointColourer (red stars on 5 capitals)',
  },
  {
    id: 'example_5_5_selective_inner_outer',
    name: 'Example 5.5: Selective Outer Terrain & Red Inner Cavity',
    category: 'Standard Examples',
    description: 'Hollow globe with terrain outer shell and red [1.0, 0.2, 0.2] inner shell',
  },
  {
    id: 'example_6a_paleo_250ma_simple',
    name: 'Example 6A: Pangaea 250 Ma (Simple Paleo Mode)',
    category: 'Standard Examples',
    description: 'Permian-Triassic boundary (250 Ma) with PaleoAtlas texture, Oxford & Baltimore stars, N/S poles',
  },
  {
    id: 'example_6b_paleo_250ma_4filament_3mf',
    name: 'Example 6B: Pangaea 250 Ma (4-Filament Banded 3MF)',
    category: 'Standard Examples',
    description: 'Pangaea 250 Ma with 4-filament 8-band hypsometric colormap & OrcaSlicer .3mf export',
  },
  {
    id: 'tomo_globe_3d',
    name: 'Tomo Globe 3D: Dual-Displaced Mantle & Topography',
    category: 'Standard Examples',
    description: 'Outer displaced by ETOPO + S40RTS + land PolygonDisplacer, inner displaced by S40RTS, 3-band ListedColormap',
  },
  {
    id: 'demo_magnets',
    name: 'Demo Magnets: Production Tomography + Calibration Piece',
    category: 'Standard Examples',
    description: 'Production tomography globe with magnets and calibration test piece workflow',
  },
  {
    id: 'demo_split_globe_image',
    name: 'Demo Split Globe Image: 50x ETOPO + Satellite Texture',
    category: 'Standard Examples',
    description: '50k-pt hollow globe with 50x ETOPO + ImageColourer -> split OBJ hemispheres',
  },
  {
    id: 'airy_isostasy_moho_globe',
    name: 'Airy Isostasy & Moho Root Globe',
    category: 'Paper Recreations',
    description: 'Outer shell displaced by 30x ETOPO, inner shell (inner_ratio=0.75) displaced by Airy Moho depth',
  },
  {
    id: 'geoid_composite_globe',
    name: 'Dynamic Topography & EGM2008 Geoid Composite',
    category: 'Paper Recreations',
    description: 'Weighted composite grid (1.0 * ETOPO + 300.0 * EGM2008) + 40x scale + 0.8mm coastline step',
  },
  {
    id: 'outreach_20mm_marble_globe',
    name: 'Game of Globes: 20mm Marble Cavity Outreach Globe',
    category: 'Paper Recreations',
    description: '40mm outer, 10.2mm cavity (inner_ratio=0.255) for standard glass marble, 50x ETOPO, 3 zero-boss magnets',
  },
  {
    id: '1_prem_mantle_shell',
    name: 'PREM Shell 1: Silicate Mantle Shell (r=40mm)',
    category: 'PREM Earth Interior',
    description: 'Mantle shell (radius=40.0, inner_ratio=0.546, 50x ETOPO, 5x2mm magnets)',
  },
  {
    id: '2_prem_outer_core_shell',
    name: 'PREM Shell 2: Liquid Outer Core Shell (r=21.5mm)',
    category: 'PREM Earth Interior',
    description: 'Outer Core shell (radius=21.5, inner_ratio=0.35, 3x1.5mm magnets)',
  },
  {
    id: '3_prem_inner_core_sphere',
    name: 'PREM Shell 3: Solid Inner Core Sphere (r=7.2mm)',
    category: 'PREM Earth Interior',
    description: 'Solid Inner Core sphere (radius=7.2mm, hollow=False)',
  },
  {
    id: '1_earth_topography_50x',
    name: 'Planetary 1: Earth Topography (r=40mm, 50x)',
    category: 'Planetary Topography',
    description: 'Comparative planetary scale: Earth (radius=40.0mm, 50x ETOPO)',
  },
  {
    id: '2_mars_topography_20x',
    name: 'Planetary 2: Mars MOLA Topography (r=21.3mm, 20x)',
    category: 'Planetary Topography',
    description: 'Comparative planetary scale: Mars (radius=21.3mm, 20x MOLA 30m)',
  },
  {
    id: '3_moon_topography_14x',
    name: 'Planetary 3: Moon LOLA Topography (r=10.9mm, 14x)',
    category: 'Planetary Topography',
    description: 'Comparative planetary scale: Moon (radius=10.9mm, 14x LOLA 30m)',
  },
  {
    id: '1_matryoshka_50km_olivine',
    name: 'Matryoshka Shell 1: 50 km Lithosphere (Olivine YlGn)',
    category: 'Seismic Matryoshka',
    description: '50 km S40RTS depth (radius=40.0mm, inner_ratio=0.7, YlGn outer, gray inner, 5x2mm magnets)',
  },
  {
    id: '2_matryoshka_660km_ringwoodite',
    name: 'Matryoshka Shell 2: 660 km Transition Zone (Ringwoodite Blues)',
    category: 'Seismic Matryoshka',
    description: '660 km S40RTS depth (radius=27.5mm, inner_ratio=0.65, Blues outer, gray inner, 4x1.5mm magnets)',
  },
  {
    id: '3_matryoshka_2850km_bridgmanite',
    name: 'Matryoshka Shell 3: 2850 km Core-Mantle Boundary (YlOrBr)',
    category: 'Seismic Matryoshka',
    description: '2850 km S40RTS depth (radius=17.5mm, solid sphere, YlOrBr outer, 3x1.5mm magnets)',
  },
];

function buildFallbackPresetProject(meta: PresetMetadata): GlobeProject {
  const base: GlobeProject = JSON.parse(JSON.stringify(DEFAULT_STARTER_PROJECT));
  base.id = meta.id;
  base.name = meta.name;
  base.category = meta.category;
  base.description = meta.description;

  if (meta.id.includes('paleo_250ma')) {
    base.mode = 'paleo';
    base.paleo!.enabled = true;
    base.paleo!.age = 250;
    base.paleo!.color_mode = meta.id.includes('4filament') ? 'filament_banded' : 'paleo_atlas';
  } else if (meta.id === '1_prem_outer_core_shell') {
    base.geometry.radius = 21.5;
    base.geometry.inner_ratio = 0.35;
    base.outer_displacements = [];
    base.colourers = [
      {
        id: 'col_oc',
        enabled: true,
        target: 'all',
        selection: 'all',
        type: 'ConstantColourer',
        color: '#f97316',
      },
    ];
  } else if (meta.id === '3_prem_inner_core_sphere') {
    base.geometry.radius = 7.2;
    base.geometry.hollow = false;
    base.outer_displacements = [];
    base.magnets.enabled = false;
    base.colourers = [
      {
        id: 'col_ic',
        enabled: true,
        target: 'all',
        selection: 'all',
        type: 'ConstantColourer',
        color: '#facc15',
      },
    ];
  } else if (meta.id.includes('mars')) {
    base.geometry.radius = 21.3;
    base.outer_displacements[0].vertical_exagg = 20;
    base.colourers[0].colormap = 'YlOrBr';
  } else if (meta.id.includes('moon')) {
    base.geometry.radius = 10.9;
    base.outer_displacements[0].vertical_exagg = 14;
    base.colourers[0].colormap = 'magma';
  } else if (meta.id.includes('matryoshka_660km')) {
    base.geometry.radius = 27.5;
    base.geometry.inner_ratio = 0.65;
    base.colourers[0].colormap = 'Blues';
  } else if (meta.id.includes('matryoshka_2850km')) {
    base.geometry.radius = 17.5;
    base.geometry.hollow = false;
    base.colourers[0].colormap = 'YlOrBr';
  } else if (meta.id === 'example_5_1_constant') {
    base.colourers = [
      {
        id: 'col_const',
        enabled: true,
        target: 'outer',
        selection: 'all',
        type: 'ConstantColourer',
        color: [0.1, 0.5, 0.8],
      },
    ];
  }
  return base;
}

export const PresetBrowserModal: React.FC = () => {
  const {
    isPresetModalOpen,
    setPresetModalOpen,
    project,
    setProject,
    setStatusMessage,
    fetchGridDataFromBackend,
  } = useProjectStore();

  const [presets, setPresets] = useState<PresetMetadata[]>(FALLBACK_27_PRESETS);
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [loadingId, setLoadingId] = useState<string | null>(null);

  useEffect(() => {
    if (!isPresetModalOpen) return;
    fetch('/api/presets')
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.presets) && data.presets.length > 0) {
          setPresets(data.presets);
        }
      })
      .catch(() => {
        // Use fallback 27 presets
      });
  }, [isPresetModalOpen]);

  if (!isPresetModalOpen) return null;

  const categories = [
    'All',
    'Standard Examples',
    'PREM Earth Interior',
    'Seismic Matryoshka',
    'Planetary Topography',
    'Paper Recreations',
  ];

  const normalizeCat = (cat: string, id: string): string => {
    const low = (cat + ' ' + id).toLowerCase();
    if (low.includes('prem') || low.includes('earth_interior')) return 'PREM Earth Interior';
    if (low.includes('matryoshka')) return 'Seismic Matryoshka';
    if (low.includes('planetary') || low.includes('mars') || low.includes('moon'))
      return 'Planetary Topography';
    if (
      low.includes('paper') ||
      low.includes('airy') ||
      low.includes('geoid') ||
      low.includes('game_of_globes') ||
      low.includes('marble')
    )
      return 'Paper Recreations';
    return 'Standard Examples';
  };

  const filtered = presets.filter((p) => {
    const mappedCat = normalizeCat(p.category || '', p.id || '');
    const catMatch = selectedCategory === 'All' || mappedCat === selectedCategory;
    const q = searchQuery.toLowerCase();
    const textMatch =
      !q ||
      p.name.toLowerCase().includes(q) ||
      p.description?.toLowerCase().includes(q) ||
      p.id.toLowerCase().includes(q);
    return catMatch && textMatch;
  });

  const handleLoadPreset = async (meta: PresetMetadata) => {
    setLoadingId(meta.id);
    try {
      const res = await fetch(`/api/presets/${encodeURIComponent(meta.id)}`);
      if (res.ok) {
        const loaded: GlobeProject = await res.json();
        setProject(loaded);
        setStatusMessage(`Loaded preset: ${loaded.name || meta.name}`);
        setPresetModalOpen(false);
        setTimeout(() => fetchGridDataFromBackend(), 50);
        return;
      }
    } catch {
      // Fallback below
    } finally {
      setLoadingId(null);
    }

    const fallback = buildFallbackPresetProject(meta);
    setProject(fallback);
    setStatusMessage(`Loaded preset: ${meta.name}`);
    setPresetModalOpen(false);
  };

  const handleUploadJson = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result)) as GlobeProject;
        setProject(parsed);
        setStatusMessage(`Loaded custom project from ${file.name}`);
        setPresetModalOpen(false);
      } catch (err: any) {
        alert(`Invalid GlobeProject JSON: ${err?.message || 'Parse error'}`);
      }
    };
    reader.readAsText(file);
  };

  const handleDownloadJson = () => {
    const blob = new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${project.id || 'globe_project'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-xl shadow-2xl w-full max-w-5xl max-h-[88vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <BookOpen className="w-5 h-5 text-sky-400" />
            <div>
              <h2 className="text-base font-bold text-white">
                Globe3D Preset Gallery (27 Scientific & Example Configurations)
              </h2>
              <p className="text-xs text-slate-400">
                Load any built-in example notebook or paper recreation as a single-globe editable recipe
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 cursor-pointer border border-slate-700">
              <Upload className="w-3.5 h-3.5 text-sky-400" />
              <span>Upload .json</span>
              <input type="file" accept=".json" className="hidden" onChange={handleUploadJson} />
            </label>
            <button
              onClick={handleDownloadJson}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700"
            >
              <Download className="w-3.5 h-3.5 text-emerald-400" />
              <span>Download Current .json</span>
            </button>
            <button
              onClick={() => setPresetModalOpen(false)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Category Filter & Search */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 bg-slate-950/60 border-b border-slate-800">
          <div className="flex flex-wrap items-center gap-1.5">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition ${
                  selectedCategory === cat
                    ? 'bg-sky-500 text-slate-950 font-semibold'
                    : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search 27 presets..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-sky-500"
            />
          </div>
        </div>

        {/* Preset Cards Grid */}
        <div className="flex-1 overflow-y-auto p-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {filtered.map((item) => {
            const catLabel = normalizeCat(item.category || '', item.id || '');
            const isCurrent = project.id === item.id;
            return (
              <div
                key={item.id}
                className={`flex flex-col justify-between p-4 rounded-xl border transition ${
                  isCurrent
                    ? 'bg-sky-950/30 border-sky-500/70'
                    : 'bg-slate-800/50 border-slate-700/70 hover:border-slate-500 hover:bg-slate-800/80'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="px-2 py-0.5 rounded bg-slate-900 text-[10px] font-semibold text-sky-400 border border-slate-700">
                      {catLabel}
                    </span>
                    <span className="text-[10px] font-mono text-slate-500 truncate max-w-[140px]">
                      {item.id}
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold text-slate-100 mb-1">{item.name}</h3>
                  <p className="text-xs text-slate-400 leading-relaxed mb-3">
                    {item.description}
                  </p>
                </div>

                <button
                  onClick={() => handleLoadPreset(item)}
                  disabled={loadingId === item.id}
                  className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-sky-500/15 hover:bg-sky-500 text-sky-300 hover:text-slate-950 font-semibold text-xs border border-sky-500/30 transition"
                >
                  <FolderOpen className="w-3.5 h-3.5" />
                  <span>{loadingId === item.id ? 'Loading...' : 'Load Preset into Studio'}</span>
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
