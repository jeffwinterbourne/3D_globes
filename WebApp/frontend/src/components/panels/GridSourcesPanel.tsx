import React, { useEffect, useState } from 'react';
import {
  Calculator,
  CheckCircle2,
  ChevronRight,
  Database,
  FileSearch,
  FolderOpen,
  Image as ImageIcon,
  Layers,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
} from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';
import { DisplacerConfig, ColourerConfig, GridSourceConfig, GridTransform } from '../../types/globeProject';

interface MediaItem {
  id: string;
  name: string;
  type?: string;
  category?: string;
  identifier: string;
  path: string;
  cached?: boolean;
  size_bytes?: number;
  description?: string;
  ext?: string;
}

const ONLINE_DATASET_CATEGORIES: Record<
  string,
  { names: string[]; hasDepth?: boolean; hasLayer?: boolean; hasRes?: boolean }
> = {
  topography: {
    names: ['earth', 'etopo', 'gebco', 'mars', 'moon', 'venus', 'mercury'],
    hasRes: true,
  },
  tomography: { names: ['s40rts'], hasDepth: true },
  geoid: { names: ['egm2008'] },
  crust: { names: ['crust1'], hasLayer: true },
  lithosphere: { names: ['thickness'], hasLayer: true },
  dynamic_topography: { names: ['hoggard2016'] },
  gravity: { names: ['bouguer'] },
  magnetics: { names: ['emag2'] },
  paleo: { names: ['scotese'], hasRes: true },
};

export const GridSourcesPanel: React.FC = () => {
  const {
    project,
    setProject,
    upsertGrid,
    removeGrid,
    fetchGridDataFromBackend,
    setDatasetModalOpen,
    setStatusMessage,
  } = useProjectStore();

  const [activeSection, setActiveSection] = useState<'grids' | 'vectors' | 'images' | 'browse'>('grids');
  const [newGridId, setNewGridId] = useState('');
  const [inspectInfo, setInspectInfo] = useState<Record<string, any>>({});
  const [browseFiles, setBrowseFiles] = useState<string[]>([]);
  const [browsingGridId, setBrowsingGridId] = useState<string | null>(null);

  // Available media from backend
  const [vectors, setVectors] = useState<MediaItem[]>([
    {
      id: 'builtin_land',
      name: 'Natural Earth 1:110m Land Polygons (Built-in)',
      type: 'polygon',
      category: 'Built-in Vectors',
      identifier: 'land',
      path: '.download_cache/ne_110m_land/ne_110m_land.shp',
      cached: true,
      description: 'Standard continental landmass polygons for PolygonDisplacer & PolygonColourer.',
    },
    {
      id: 'builtin_coastline',
      name: 'Natural Earth 1:110m Coastlines (Built-in)',
      type: 'line',
      category: 'Built-in Vectors',
      identifier: 'coastline',
      path: '.download_cache/ne_110m_coastline/ne_110m_coastline.shp',
      cached: true,
      description: 'Coastline vectors for LineDisplacer & LineColourer.',
    },
  ]);
  const [images, setImages] = useState<MediaItem[]>([
    {
      id: 'img_world_topo',
      name: 'world_topo.png',
      identifier: 'context/height_maps/world_topo.png',
      path: 'context/height_maps/world_topo.png',
      ext: '.png',
      category: 'Built-in Textures',
    },
    {
      id: 'img_coastline',
      name: 'coastline.png',
      identifier: 'context/height_maps/coastline.png',
      path: 'context/height_maps/coastline.png',
      ext: '.png',
      category: 'Built-in Textures',
    },
  ]);
  const [currentBrowseDir, setCurrentBrowseDir] = useState<string>('');
  const [browseDirs, setBrowseDirs] = useState<Array<{ name: string; path: string }>>([]);
  const [dirFiles, setDirFiles] = useState<Array<{ name: string; path: string; ext: string; size_bytes?: number }>>([]);
  const [isUploading, setIsUploading] = useState(false);

  const loadMedia = async () => {
    try {
      const res = await fetch('/api/datasets/available-media');
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.vectors) && data.vectors.length > 0) setVectors(data.vectors);
        if (Array.isArray(data.images) && data.images.length > 0) setImages(data.images);
      }
    } catch {
      // offline fallback
    }
  };

  const loadDirectory = async (path?: string) => {
    try {
      const q = path ? `?path=${encodeURIComponent(path)}` : '';
      const res = await fetch(`/api/files/browse${q}`);
      if (res.ok) {
        const data = await res.json();
        setCurrentBrowseDir(data.current_path || '');
        setBrowseDirs(data.directories || []);
        setDirFiles(data.files || []);
      }
    } catch {
      // offline fallback
    }
  };

  useEffect(() => {
    loadMedia();
    loadDirectory();
  }, []);

  const rawGrids = (project.grids || (project as any).custom_recipe?.grids || {}) as any;
  const gridEntries: [string, GridSourceConfig][] = Array.isArray(rawGrids)
    ? rawGrids.map((g: any, i: number) => [
        g.id || `grid_${i + 1}`,
        {
          id: g.id || `grid_${i + 1}`,
          source_type: g.source || g.source_type || 'online',
          category: (g.dataset || 'topography.earth').split('.')[0] || 'topography',
          name: (g.dataset || 'topography.earth').split('.')[1] || 'earth',
          dataset: g.dataset,
          resolution: g.params?.resolution || g.resolution || '30m',
          depth: g.params?.depth ?? g.depth,
          layer: g.params?.layer ?? g.layer,
          age: g.params?.age ?? g.age,
          local_path: g.filepath || g.local_path,
          netcdf_vars: g.netcdf_vars || { lat_var: 'lat', lon_var: 'lon', data_var: 'z' },
          transforms: g.transforms || g.ops || [],
        },
      ])
    : Object.entries(rawGrids);

  const handleAddGrid = () => {
    const cleanId = (newGridId.trim() || `grid_${gridEntries.length + 1}`).replace(
      /[^a-zA-Z0-9_]/g,
      '_'
    );
    upsertGrid(cleanId, {
      source_type: 'online',
      category: 'topography',
      name: 'earth',
      resolution: '30m',
      transforms: [],
    });
    setNewGridId('');
  };

  const handleInspectNetcdf = async (gridId: string, filepath?: string) => {
    if (!filepath) return;
    try {
      const res = await fetch('/api/grids/inspect-netcdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filepath }),
      });
      if (res.ok) {
        const data = await res.json();
        setInspectInfo((prev) => ({ ...prev, [gridId]: data }));
        if (data.detected_lat || data.detected_lon || data.detected_data) {
          const current = project.grids[gridId];
          upsertGrid(gridId, {
            ...current,
            netcdf_vars: {
              lat_var: data.detected_lat || 'lat',
              lon_var: data.detected_lon || 'lon',
              data_var: data.detected_data || 'z',
            },
          });
        }
      }
    } catch {
      setStatusMessage('Could not inspect NetCDF variables (backend offline)');
    }
  };

  const handleUploadFileToCache = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    setStatusMessage(`Uploading ${file.name}...`);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch('/api/files/upload', { method: 'POST', body: form });
      if (res.ok) {
        const data = await res.json();
        setStatusMessage(`Uploaded ${data.filename} (${Math.round((data.size_bytes || 0) / 1024)} KB)`);
        loadMedia();
        loadDirectory(currentBrowseDir);
      }
    } catch (err: any) {
      setStatusMessage(`Upload failed: ${err.message || 'error'}`);
    } finally {
      setIsUploading(false);
    }
  };

  // One-click actions from Datasets into Displacers & Colourers
  const addAsPolygonDisplacer = (shapefile: string) => {
    const currentDisps = project.outer_displacements || [];
    const newDisp: DisplacerConfig = {
      id: `disp_poly_${Date.now().toString().slice(-4)}`,
      enabled: true,
      type: 'PolygonDisplacer',
      shapefile,
      displacement: 1.0,
      displace_inside: true,
      scale: 1.0,
      scale_mode: 'direct',
    };
    setProject({
      ...project,
      outer_displacements: [...currentDisps, newDisp],
    });
    setStatusMessage(`Added PolygonDisplacer (${shapefile}) to Outer Shell!`);
  };

  const addAsPolygonColourer = (shapefile: string) => {
    const currentCols = project.colourers || [];
    const newCol: ColourerConfig = {
      id: `col_poly_${Date.now().toString().slice(-4)}`,
      enabled: true,
      type: 'PolygonColourer',
      target: 'outer',
      selection: 'all',
      shapefile,
      color: '#22c55e',
      background_color: '#1e3a8a',
      flood_inside: true,
    };
    setProject({
      ...project,
      colourers: [...currentCols, newCol],
    });
    setStatusMessage(`Added PolygonColourer (${shapefile}) to Colourer Stack!`);
  };

  const addAsLineDisplacer = (shapefile: string) => {
    const currentDisps = project.outer_displacements || [];
    const newDisp: DisplacerConfig = {
      id: `disp_line_${Date.now().toString().slice(-4)}`,
      enabled: true,
      type: 'LineDisplacer',
      shapefile,
      displacement: 0.8,
      width_degrees: 0.8,
      scale: 1.0,
      scale_mode: 'direct',
    };
    setProject({
      ...project,
      outer_displacements: [...currentDisps, newDisp],
    });
    setStatusMessage(`Added LineDisplacer (${shapefile}) to Outer Shell!`);
  };

  const addAsImageColourer = (imagePath: string) => {
    const currentCols = project.colourers || [];
    const newCol: ColourerConfig = {
      id: `col_img_${Date.now().toString().slice(-4)}`,
      enabled: true,
      type: 'ImageColourer',
      target: 'outer',
      selection: 'all',
      image_source: 'local',
      image_path: imagePath,
      preprocessors: [],
    };
    setProject({
      ...project,
      colourers: [...currentCols, newCol],
    });
    setStatusMessage(`Added ImageColourer (${imagePath}) to Colourer Stack!`);
  };

  const addTransform = (gridId: string, type: GridTransform['type']) => {
    const current = project.grids[gridId];
    if (!current) return;
    const transforms = current.transforms || [];
    const next: GridTransform = { type };
    if (type === 'downsample') {
      next.step_lat = 10;
      next.step_lon = 10;
    } else if (type === 'airy_moho') {
      next.ref_thickness = 30000;
      next.rho_c = 2670;
      next.rho_m = 3300;
    } else if (type === 'weighted_composite') {
      next.weight_a = 1.0;
      next.weight_b = 300.0;
      next.grid_b_id = Object.keys(project.grids).find((k) => k !== gridId);
    } else if (type === 'reconstruct') {
      next.age = 100.0;
      next.plate_model = 'Scotese_PALEOMAP';
    } else if (type === 'scale_offset') {
      next.scale = 1.0;
      next.offset = 0.0;
    } else if (type === 'smooth') {
      next.width_deg = 2.0;
    } else if (type === 'fill') {
      next.fill_mode = 'constant';
      next.fill_value = 0.0;
    } else if (type === 'math') {
      next.math_op = 'multiply';
      next.operand = 1.0;
    }
    upsertGrid(gridId, { ...current, transforms: [...transforms, next] });
  };

  const handleBrowseLocal = async (gridId: string) => {
    setBrowsingGridId(gridId);
    try {
      const res = await fetch('/api/files/browse?path=..');
      if (res.ok) {
        const data = await res.json();
        const files = (data.files || data.entries || []).map((f: any) =>
          typeof f === 'string' ? f : f.path || f.name
        );
        setBrowseFiles(files);
      }
    } catch {
      setBrowseFiles([
        '../inputs/ETOPO_2022_v1_60s_N90W180_surface.nc',
        '../inputs/s40_depth_slice_2850.grd',
        '../inputs/EGM2008_geoid.nc',
      ]);
    }
  };

  const handleUploadGridFile = async (
    gridId: string,
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch('/api/files/upload', { method: 'POST', body: form });
      if (res.ok) {
        const data = await res.json();
        const current = project.grids[gridId];
        upsertGrid(gridId, { ...current, source_type: 'local', local_path: data.filepath });
        setStatusMessage(`Uploaded ${file.name} -> ${data.filepath}`);
      }
    } catch {
      const current = project.grids[gridId];
      upsertGrid(gridId, {
        ...current,
        source_type: 'local',
        local_path: `.download_cache/uploads/${file.name}`,
      });
    }
  };

  return (
    <div className="space-y-4 text-xs">
      {/* Unified Dataset & Media Navigation Tabs */}
      <div className="grid grid-cols-4 gap-1 p-1 bg-slate-950/80 rounded-xl border border-slate-800">
        <button
          onClick={() => setActiveSection('grids')}
          className={`py-1.5 px-2 rounded-lg font-semibold flex items-center justify-center gap-1.5 transition ${
            activeSection === 'grids'
              ? 'bg-sky-500/20 text-sky-300 border border-sky-400/40 shadow'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          <span>Grids</span>
        </button>
        <button
          onClick={() => setActiveSection('vectors')}
          className={`py-1.5 px-2 rounded-lg font-semibold flex items-center justify-center gap-1.5 transition ${
            activeSection === 'vectors'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/40 shadow'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Vectors</span>
        </button>
        <button
          onClick={() => setActiveSection('images')}
          className={`py-1.5 px-2 rounded-lg font-semibold flex items-center justify-center gap-1.5 transition ${
            activeSection === 'images'
              ? 'bg-purple-500/20 text-purple-300 border border-purple-400/40 shadow'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <ImageIcon className="w-3.5 h-3.5" />
          <span>Images</span>
        </button>
        <button
          onClick={() => setActiveSection('browse')}
          className={`py-1.5 px-2 rounded-lg font-semibold flex items-center justify-center gap-1.5 transition ${
            activeSection === 'browse'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-400/40 shadow'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <FolderOpen className="w-3.5 h-3.5" />
          <span>Browse</span>
        </button>
      </div>

      {/* SECTION 1: VECTORS & SHAPEFILES */}
      {activeSection === 'vectors' && (
        <div className="space-y-3">
          <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-emerald-300 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-emerald-400" />
                <span>Vector Shapefiles & Boundaries ({vectors.length})</span>
              </span>
              <button
                onClick={loadMedia}
                className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-emerald-400"
                title="Refresh vector list"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
            <p className="text-[11px] text-slate-400">
              Apply continental land polygons, coastlines, or custom GeoJSON/Shapefiles directly to the
              Displacer stack (PolygonDisplacer / LineDisplacer) or Colourer stack.
            </p>
          </div>

          <div className="space-y-2.5">
            {vectors.map((vec) => (
              <div
                key={vec.id}
                className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-1.5 font-bold text-slate-200">
                      <span>{vec.name}</span>
                      <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px] uppercase font-mono">
                        {vec.type}
                      </span>
                    </div>
                    <div className="text-[11px] font-mono text-slate-400 truncate max-w-[280px]">
                      {vec.identifier}
                    </div>
                  </div>
                  {vec.cached && (
                    <span className="flex items-center gap-1 text-[10px] text-emerald-400 font-semibold">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>Ready</span>
                    </span>
                  )}
                </div>

                {vec.description && (
                  <p className="text-[11px] text-slate-400">{vec.description}</p>
                )}

                <div className="grid grid-cols-2 gap-1.5 pt-1 border-t border-slate-800">
                  {vec.type === 'line' ? (
                    <>
                      <button
                        onClick={() => addAsLineDisplacer(vec.identifier)}
                        className="py-1 px-2 rounded-lg bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 border border-sky-400/30 font-semibold text-[11px]"
                      >
                        + LineDisplacer
                      </button>
                      <button
                        onClick={() => {
                          const currentCols = project.colourers || [];
                          setProject({
                            ...project,
                            colourers: [
                              ...currentCols,
                              {
                                id: `col_line_${Date.now().toString().slice(-4)}`,
                                enabled: true,
                                type: 'LineColourer',
                                target: 'outer',
                                selection: 'all',
                                shapefile: vec.identifier,
                                color: '#0f172a',
                                width_degrees: 0.8,
                              },
                            ],
                          });
                          setStatusMessage(`Added LineColourer (${vec.name})!`);
                        }}
                        className="py-1 px-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-400/30 font-semibold text-[11px]"
                      >
                        + LineColourer
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => addAsPolygonDisplacer(vec.identifier)}
                        className="py-1 px-2 rounded-lg bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 border border-sky-400/30 font-semibold text-[11px]"
                      >
                        + PolygonDisplacer
                      </button>
                      <button
                        onClick={() => addAsPolygonColourer(vec.identifier)}
                        className="py-1 px-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-400/30 font-semibold text-[11px]"
                      >
                        + PolygonColourer
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION 2: IMAGES & TEXTURES */}
      {activeSection === 'images' && (
        <div className="space-y-3">
          <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-purple-300 flex items-center gap-1.5">
                <ImageIcon className="w-4 h-4 text-purple-400" />
                <span>Surface Images & Planetary Maps ({images.length})</span>
              </span>
              <button
                onClick={loadMedia}
                className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-purple-400"
                title="Refresh images"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
            <p className="text-[11px] text-slate-400">
              Apply equirectangular textures, satellite relief, and Scotese PaleoAtlas maps directly to
              the vertex Colourer stack (ImageColourer) with optional hillshade removal.
            </p>
          </div>

          <div className="space-y-2.5">
            {images.map((img) => (
              <div
                key={img.id}
                className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-bold text-slate-200">{img.name}</div>
                    <div className="text-[11px] font-mono text-slate-400 truncate max-w-[280px]">
                      {img.identifier}
                    </div>
                  </div>
                  {img.size_bytes ? (
                    <span className="text-[10px] font-mono text-slate-400">
                      {Math.round(img.size_bytes / 1024)} KB
                    </span>
                  ) : null}
                </div>

                <div className="pt-1 border-t border-slate-800">
                  <button
                    onClick={() => addAsImageColourer(img.identifier)}
                    className="w-full py-1.5 px-3 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 border border-purple-400/30 font-semibold text-[11px] flex items-center justify-center gap-1.5"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Apply as ImageColourer Layer</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION 3: BROWSE & UPLOAD LOCAL FILES */}
      {activeSection === 'browse' && (
        <div className="space-y-3">
          {/* File Upload Box */}
          <div className="p-3.5 rounded-xl bg-slate-900/90 border border-dashed border-slate-700 space-y-2 text-center">
            <Upload className="w-6 h-6 text-sky-400 mx-auto" />
            <div>
              <span className="font-semibold text-slate-200">Upload Dataset to Project Cache</span>
              <p className="text-[11px] text-slate-400">
                Supports .shp, .geojson, .tif, .tiff, .nc, .grd, .png, .jpg
              </p>
            </div>
            <label className="inline-block px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold cursor-pointer">
              <span>{isUploading ? 'Uploading...' : 'Choose File to Upload'}</span>
              <input
                type="file"
                className="hidden"
                accept=".shp,.geojson,.gpkg,.nc,.grd,.tif,.tiff,.png,.jpg,.jpeg,.json"
                onChange={handleUploadFileToCache}
              />
            </label>
          </div>

          {/* Directory Navigation */}
          <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-amber-300 flex items-center gap-1.5">
                <FolderOpen className="w-4 h-4 text-amber-400" />
                <span>Filesystem Browser</span>
              </span>
              <button
                onClick={() => loadDirectory(currentBrowseDir)}
                className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-amber-400"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="text-[11px] font-mono text-slate-400 truncate bg-slate-950 p-1.5 rounded border border-slate-800">
              {currentBrowseDir}
            </div>

            {/* Sub-directories */}
            {browseDirs.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                <button
                  onClick={() => loadDirectory(`${currentBrowseDir}/..`)}
                  className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono text-[10px]"
                >
                  .. (Up)
                </button>
                {browseDirs.map((d) => (
                  <button
                    key={d.path}
                    onClick={() => loadDirectory(d.path)}
                    className="px-2 py-0.5 rounded bg-slate-950 hover:bg-slate-800 border border-slate-700 text-slate-300 font-mono text-[10px] flex items-center gap-1"
                  >
                    <span>📁 {d.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Discovered files in folder */}
          <div className="space-y-1.5">
            {dirFiles.length === 0 && (
              <div className="p-4 text-center text-slate-500 rounded-xl bg-slate-900/50 border border-slate-800">
                No supported dataset or image files in this folder.
              </div>
            )}
            {dirFiles.map((f) => (
              <div
                key={f.path}
                className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 flex items-center justify-between"
              >
                <div className="truncate mr-2">
                  <div className="font-bold text-slate-200 text-[11px] truncate">{f.name}</div>
                  <div className="text-[10px] font-mono text-slate-500 truncate">{f.path}</div>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  {['.nc', '.grd', '.tif', '.tiff'].includes(f.ext) && (
                    <button
                      onClick={() => {
                        const newId = f.name.replace(/[^a-zA-Z0-9_]/g, '_');
                        upsertGrid(newId, {
                          source_type: 'local',
                          local_path: f.path,
                          transforms: [],
                        });
                        setActiveSection('grids');
                        setStatusMessage(`Loaded ${f.name} as grid '${newId}'!`);
                      }}
                      className="px-2 py-1 rounded bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 border border-sky-400/30 text-[10px] font-semibold"
                    >
                      Use as Grid
                    </button>
                  )}
                  {['.shp', '.geojson'].includes(f.ext) && (
                    <button
                      onClick={() => {
                        addAsPolygonDisplacer(f.path);
                        setStatusMessage(`Applied ${f.name} to PolygonDisplacer!`);
                      }}
                      className="px-2 py-1 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-400/30 text-[10px] font-semibold"
                    >
                      Use as Shapefile
                    </button>
                  )}
                  {['.png', '.jpg', '.jpeg'].includes(f.ext) && (
                    <button
                      onClick={() => {
                        addAsImageColourer(f.path);
                        setStatusMessage(`Applied ${f.name} to ImageColourer!`);
                      }}
                      className="px-2 py-1 rounded bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 border border-purple-400/30 text-[10px] font-semibold"
                    >
                      Use as Image
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION 4: GRIDS & DEM PIPELINES */}
      {activeSection === 'grids' && (
        <div className="space-y-4">
          {/* Header & Add Grid Bar */}
          <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 font-semibold text-slate-200">
                <Database className="w-4 h-4 text-sky-400" />
                <span>Named GeographicGrids ({gridEntries.length})</span>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => setDatasetModalOpen(true)}
                  className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 border border-slate-700 text-[11px]"
                >
                  Cache Manager
                </button>
                <button
                  onClick={() => fetchGridDataFromBackend()}
                  title="Sync grid buffers from Python"
                  className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-slate-700"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            <div className="flex gap-1.5">
              <input
                type="text"
                placeholder="New grid ID (e.g. moho_grid, tomo_2850)..."
                value={newGridId}
                onChange={(e) => setNewGridId(e.target.value)}
                className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-100"
              />
              <button
                onClick={handleAddGrid}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Grid</span>
              </button>
            </div>
          </div>

      {/* Grid List */}
      {gridEntries.map(([gridId, cfg]) => {
        const activeCat = cfg.category || cfg.fallback_dataset?.category || 'topography';
        const catSpec =
          ONLINE_DATASET_CATEGORIES[activeCat] ||
          ONLINE_DATASET_CATEGORIES.topography;

        return (
          <div
            key={gridId}
            className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3"
          >
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-sky-500/20 border border-sky-500/40 font-mono font-bold text-sky-300">
                  {gridId}
                </span>
                <select
                  value={cfg.source_type}
                  onChange={(e) =>
                    upsertGrid(gridId, {
                      ...cfg,
                      source_type: e.target.value as GridSourceConfig['source_type'],
                    })
                  }
                  className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200"
                >
                  <option value="online">Online Dataset Catalog</option>
                  <option value="local_or_dataset">Local File + Dataset Fallback</option>
                  <option value="local">Local File (.nc / .grd / .tif)</option>
                  <option value="paleo">Paleo Scotese DEM</option>
                  <option value="synthetic">Synthetic / Procedural Wave</option>
                </select>
              </div>

              <button
                onClick={() => removeGrid(gridId)}
                className="p-1 text-slate-500 hover:text-rose-400"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>

            {/* Online Dataset Selector */}
            {(cfg.source_type === 'online' || cfg.source_type === 'local_or_dataset') && (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 mb-1">Dataset Category</label>
                  <select
                    value={cfg.category || cfg.fallback_dataset?.category || 'topography'}
                    onChange={(e) => {
                      const nextCat = e.target.value;
                      const firstDs = ONLINE_DATASET_CATEGORIES[nextCat]?.names[0] || 'earth';
                      upsertGrid(gridId, {
                        ...cfg,
                        category: nextCat,
                        name: firstDs,
                        dataset: `${nextCat}.${firstDs}`,
                      });
                    }}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                  >
                    {Object.keys(ONLINE_DATASET_CATEGORIES).map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Dataset Name</label>
                  <select
                    value={cfg.name || cfg.fallback_dataset?.name || catSpec.names[0]}
                    onChange={(e) => {
                      const nextName = e.target.value;
                      upsertGrid(gridId, {
                        ...cfg,
                        name: nextName,
                        dataset: `${activeCat}.${nextName}`,
                      });
                    }}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                  >
                    {catSpec.names.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </div>

                {catSpec.hasRes && (
                  <div>
                    <label className="block text-slate-400 mb-1">Resolution</label>
                    <select
                      value={cfg.resolution || '30m'}
                      onChange={(e) =>
                        upsertGrid(gridId, { ...cfg, resolution: e.target.value })
                      }
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                    >
                      {activeCat === 'paleo' ? (
                        <>
                          <option value="1d">1d (1 degree)</option>
                          <option value="6m">6m (6 arc-min)</option>
                        </>
                      ) : (
                        <>
                          <option value="01d">01d (1 degree / ~110km)</option>
                          <option value="30m">30m (30 arc-min / ~55km)</option>
                          <option value="15m">15m (15 arc-min / ~28km)</option>
                          <option value="10m">10m (10 arc-min / ~18km)</option>
                        </>
                      )}
                    </select>
                  </div>
                )}

                {catSpec.hasDepth && (
                  <div>
                    <label className="block text-slate-400 mb-1">S40RTS Depth (km)</label>
                    <input
                      type="number"
                      step={50}
                      min={50}
                      max={2890}
                      value={cfg.depth ?? cfg.fallback_dataset?.depth ?? 2850}
                      onChange={(e) =>
                        upsertGrid(gridId, { ...cfg, depth: Number(e.target.value) })
                      }
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono"
                    />
                  </div>
                )}

                {catSpec.hasLayer && (
                  <div>
                    <label className="block text-slate-400 mb-1">CRUST1.0 / Litho Layer</label>
                    <select
                      value={cfg.layer || 'moho'}
                      onChange={(e) => upsertGrid(gridId, { ...cfg, layer: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                    >
                      <option value="moho">moho</option>
                      <option value="surface">surface</option>
                      <option value="water_bottom">water_bottom</option>
                      <option value="ice_bottom">ice_bottom</option>
                      <option value="upper_crust_bottom">upper_crust_bottom</option>
                      <option value="middle_crust_bottom">middle_crust_bottom</option>
                      <option value="total">total (LITHO1.0)</option>
                      <option value="lab">lab (LITHO1.0)</option>
                    </select>
                  </div>
                )}
              </div>
            )}

            {/* Local File Picker + Drag/Drop Upload + NetCDF Inspector */}
            {(cfg.source_type === 'local' || cfg.source_type === 'local_or_dataset') && (
              <div className="space-y-2 pt-1">
                <label className="block text-slate-400">Local NetCDF / GeoTIFF Path</label>
                <div className="flex gap-1.5">
                  <input
                    type="text"
                    value={cfg.local_path || ''}
                    onChange={(e) =>
                      upsertGrid(gridId, { ...cfg, local_path: e.target.value })
                    }
                    placeholder="../inputs/ETOPO_2022_v1_60s_N90W180_surface.nc"
                    className="flex-1 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono text-[11px]"
                  />
                  <button
                    onClick={() => handleBrowseLocal(gridId)}
                    title="Browse Local Files"
                    className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200"
                  >
                    <FolderOpen className="w-3.5 h-3.5" />
                  </button>
                  <label
                    title="Upload Local File"
                    className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sky-300 cursor-pointer flex items-center"
                  >
                    <Upload className="w-3.5 h-3.5" />
                    <input
                      type="file"
                      accept=".nc,.grd,.tif,.tiff"
                      className="hidden"
                      onChange={(e) => handleUploadGridFile(gridId, e)}
                    />
                  </label>
                  <button
                    onClick={() => handleInspectNetcdf(gridId, cfg.local_path)}
                    title="Inspect NetCDF Variables"
                    className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-emerald-400 flex items-center gap-1"
                  >
                    <FileSearch className="w-3.5 h-3.5" />
                    <span>Inspect</span>
                  </button>
                </div>

                {browsingGridId === gridId && browseFiles.length > 0 && (
                  <div className="p-2 rounded bg-slate-950 border border-slate-700 max-h-28 overflow-y-auto space-y-1">
                    {browseFiles.map((fp) => (
                      <button
                        key={fp}
                        onClick={() => {
                          upsertGrid(gridId, { ...cfg, local_path: fp });
                          setBrowsingGridId(null);
                        }}
                        className="block w-full text-left font-mono text-[11px] text-sky-300 hover:bg-slate-800 px-1.5 py-0.5 rounded"
                      >
                        {fp}
                      </button>
                    ))}
                  </div>
                )}

                <div className="grid grid-cols-3 gap-1.5">
                  <input
                    type="text"
                    placeholder="lat_var (lat)"
                    value={cfg.netcdf_vars?.lat_var || ''}
                    onChange={(e) =>
                      upsertGrid(gridId, {
                        ...cfg,
                        netcdf_vars: { ...cfg.netcdf_vars, lat_var: e.target.value },
                      })
                    }
                    className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono"
                  />
                  <input
                    type="text"
                    placeholder="lon_var (lon)"
                    value={cfg.netcdf_vars?.lon_var || ''}
                    onChange={(e) =>
                      upsertGrid(gridId, {
                        ...cfg,
                        netcdf_vars: { ...cfg.netcdf_vars, lon_var: e.target.value },
                      })
                    }
                    className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono"
                  />
                  <input
                    type="text"
                    placeholder="data_var (z)"
                    value={cfg.netcdf_vars?.data_var || ''}
                    onChange={(e) =>
                      upsertGrid(gridId, {
                        ...cfg,
                        netcdf_vars: { ...cfg.netcdf_vars, data_var: e.target.value },
                      })
                    }
                    className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono"
                  />
                </div>

                {inspectInfo[gridId] && (
                  <div className="text-[10px] font-mono text-emerald-400 bg-slate-950 p-1.5 rounded border border-slate-800">
                    Vars: {(inspectInfo[gridId].variables || []).join(', ')}
                  </div>
                )}
              </div>
            )}

            {/* Paleo Scotese DEM Source */}
            {cfg.source_type === 'paleo' && (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 mb-1">Scotese Age (Ma)</label>
                  <input
                    type="number"
                    min={0}
                    max={540}
                    step={5}
                    value={cfg.age ?? 250}
                    onChange={(e) =>
                      upsertGrid(gridId, { ...cfg, age: Number(e.target.value) })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Resolution</label>
                  <select
                    value={cfg.resolution || '1d'}
                    onChange={(e) =>
                      upsertGrid(gridId, { ...cfg, resolution: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100"
                  >
                    <option value="1d">1d (1°)</option>
                    <option value="6m">6m (6 arc-min)</option>
                  </select>
                </div>
              </div>
            )}

            {/* Declarative Grid Transforms Pipeline */}
            <div className="pt-2 border-t border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-medium flex items-center gap-1">
                  <Calculator className="w-3.5 h-3.5 text-amber-400" />
                  <span>Declarative Grid Operations</span>
                </span>
                <select
                  value=""
                  onChange={(e) => {
                    if (e.target.value) {
                      addTransform(gridId, e.target.value as GridTransform['type']);
                    }
                  }}
                  className="bg-slate-950 border border-slate-700 rounded px-2 py-0.5 text-[11px] text-sky-300"
                >
                  <option value="">+ Add Transform...</option>
                  <option value="smooth">Gaussian Smoothing (Spherical deg)</option>
                  <option value="fill">Fill NaNs / Missing Data</option>
                  <option value="math">Math Operation (+, -, *, /, pow, log, exp...)</option>
                  <option value="downsample">Downsample [::step_lat, ::step_lon]</option>
                  <option value="scale_offset">Scale & Offset</option>
                  <option value="airy_moho">Airy Isostasy Moho Calculator</option>
                  <option value="weighted_composite">Weighted Grid Compositor</option>
                  <option value="reconstruct">GPlately Reconstruct Grid</option>
                </select>
              </div>

              {(cfg.transforms || []).map((tr, tIdx) => (
                <div
                  key={tIdx}
                  className="p-2 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-amber-300 text-[11px]">
                      {tr.type.toUpperCase()}
                    </span>
                    <button
                      onClick={() => {
                        const nextT = (cfg.transforms || []).filter((_, i) => i !== tIdx);
                        upsertGrid(gridId, { ...cfg, transforms: nextT });
                      }}
                      className="text-slate-500 hover:text-rose-400"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>

                  {tr.type === 'downsample' && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <span className="text-[10px] text-slate-400">step_lat</span>
                        <input
                          type="number"
                          min={1}
                          value={tr.step_lat ?? 10}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, step_lat: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400">step_lon</span>
                        <input
                          type="number"
                          min={1}
                          value={tr.step_lon ?? 10}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, step_lon: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                    </div>
                  )}

                  {tr.type === 'airy_moho' && (
                    <div className="grid grid-cols-3 gap-1.5">
                      <div>
                        <span className="text-[10px] text-slate-400">Ref Moho (m)</span>
                        <input
                          type="number"
                          value={tr.ref_thickness ?? 30000}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, ref_thickness: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400">rho_c</span>
                        <input
                          type="number"
                          value={tr.rho_c ?? 2800}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, rho_c: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400">rho_m</span>
                        <input
                          type="number"
                          value={tr.rho_m ?? 3300}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, rho_m: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                    </div>
                  )}

                  {tr.type === 'weighted_composite' && (
                    <div className="grid grid-cols-3 gap-1.5">
                      <div>
                        <span className="text-[10px] text-slate-400">Grid B ID</span>
                        <input
                          type="text"
                          value={tr.grid_b_id || ''}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, grid_b_id: e.target.value };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400">Weight A</span>
                        <input
                          type="number"
                          value={tr.weight_a ?? 1}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, weight_a: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400">Weight B</span>
                        <input
                          type="number"
                          value={tr.weight_b ?? 300}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, weight_b: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5"
                        />
                      </div>
                    </div>
                  )}

                  {tr.type === 'smooth' && (
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-slate-400">Filter Width (degrees on sphere)</span>
                        <span className="font-mono text-emerald-400 font-bold">{tr.width_deg ?? 2.0}°</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min={0.2}
                          max={25.0}
                          step={0.2}
                          value={tr.width_deg ?? 2.0}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, width_deg: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="flex-1 accent-emerald-500"
                        />
                        <input
                          type="number"
                          min={0.1}
                          max={45.0}
                          step={0.5}
                          value={tr.width_deg ?? 2.0}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, width_deg: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-16 bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-center font-mono text-xs"
                        />
                      </div>
                      <p className="text-[10px] text-slate-500">
                        Spherical Gaussian filter: wraps periodically across longitudes and scales by cos(lat) to preserve true metric width near poles.
                      </p>
                    </div>
                  )}

                  {tr.type === 'fill' && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <span className="text-[10px] text-slate-400">Fill Mode</span>
                        <select
                          value={tr.fill_mode || 'constant'}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = {
                              ...tr,
                              fill_mode: e.target.value as GridTransform['fill_mode'],
                            };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-1 text-slate-200 text-xs"
                        >
                          <option value="constant">Constant Value</option>
                          <option value="mean">Grid Mean</option>
                          <option value="min">Grid Min</option>
                          <option value="max">Grid Max</option>
                          <option value="nearest">Nearest-Neighbor (EDT Inpaint)</option>
                        </select>
                      </div>
                      {(!tr.fill_mode || tr.fill_mode === 'constant') && (
                        <div>
                          <span className="text-[10px] text-slate-400">Fill Value</span>
                          <input
                            type="number"
                            step={1}
                            value={tr.fill_value ?? 0.0}
                            onChange={(e) => {
                              const nextT = [...(cfg.transforms || [])];
                              nextT[tIdx] = { ...tr, fill_value: Number(e.target.value) };
                              upsertGrid(gridId, { ...cfg, transforms: nextT });
                            }}
                            className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-slate-100 text-xs font-mono"
                          />
                        </div>
                      )}
                    </div>
                  )}

                  {tr.type === 'math' && (
                    <div className="space-y-1.5">
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <span className="text-[10px] text-slate-400">Operation</span>
                          <select
                            value={tr.math_op || 'multiply'}
                            onChange={(e) => {
                              const nextT = [...(cfg.transforms || [])];
                              nextT[tIdx] = {
                                ...tr,
                                math_op: e.target.value as GridTransform['math_op'],
                              };
                              upsertGrid(gridId, { ...cfg, transforms: nextT });
                            }}
                            className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-1 text-slate-200 text-xs"
                          >
                            <option value="add">Add (x + operand)</option>
                            <option value="subtract">Subtract (x - operand)</option>
                            <option value="multiply">Multiply (x * operand)</option>
                            <option value="divide">Divide (x / operand)</option>
                            <option value="power">Power (x ^ operand)</option>
                            <option value="log">Natural Log ln(x)</option>
                            <option value="log10">Logarithm log10(x)</option>
                            <option value="exp">Exponential exp(x)</option>
                            <option value="abs">Absolute Value |x|</option>
                            <option value="negate">Negate (-x)</option>
                            <option value="sqrt">Square Root sqrt(x)</option>
                            <option value="clamp">Clamp / Clip [min, max]</option>
                          </select>
                        </div>

                        {['add', 'subtract', 'multiply', 'divide', 'power'].includes(
                          tr.math_op || 'multiply'
                        ) && (
                          <div>
                            <span className="text-[10px] text-slate-400">Operand</span>
                            <input
                              type="number"
                              step={0.1}
                              value={tr.operand ?? 1.0}
                              onChange={(e) => {
                                const nextT = [...(cfg.transforms || [])];
                                nextT[tIdx] = { ...tr, operand: Number(e.target.value) };
                                upsertGrid(gridId, { ...cfg, transforms: nextT });
                              }}
                              className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-slate-100 text-xs font-mono"
                            />
                          </div>
                        )}
                      </div>

                      {tr.math_op === 'clamp' && (
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <span className="text-[10px] text-slate-400">Min Threshold</span>
                            <input
                              type="number"
                              value={tr.min_val ?? -5000}
                              onChange={(e) => {
                                const nextT = [...(cfg.transforms || [])];
                                nextT[tIdx] = { ...tr, min_val: Number(e.target.value) };
                                upsertGrid(gridId, { ...cfg, transforms: nextT });
                              }}
                              className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-slate-100 text-xs font-mono"
                            />
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-400">Max Threshold</span>
                            <input
                              type="number"
                              value={tr.max_val ?? 5000}
                              onChange={(e) => {
                                const nextT = [...(cfg.transforms || [])];
                                nextT[tIdx] = { ...tr, max_val: Number(e.target.value) };
                                upsertGrid(gridId, { ...cfg, transforms: nextT });
                              }}
                              className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-slate-100 text-xs font-mono"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {tr.type === 'scale_offset' && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <span className="text-[10px] text-slate-400">Scale Factor</span>
                        <input
                          type="number"
                          step={0.1}
                          value={tr.scale ?? 1.0}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, scale: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-slate-100 text-xs font-mono"
                        />
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400">Offset</span>
                        <input
                          type="number"
                          step={1.0}
                          value={tr.offset ?? 0.0}
                          onChange={(e) => {
                            const nextT = [...(cfg.transforms || [])];
                            nextT[tIdx] = { ...tr, offset: Number(e.target.value) };
                            upsertGrid(gridId, { ...cfg, transforms: nextT });
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-slate-100 text-xs font-mono"
                        />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
        </div>
      )}
    </div>
  );
};
