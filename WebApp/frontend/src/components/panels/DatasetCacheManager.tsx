import React, { useEffect, useState } from 'react';
import {
  CheckCircle2,
  CloudDownload,
  Database,
  FolderOpen,
  HardDrive,
  RefreshCw,
  X,
} from 'lucide-react';
import { useProjectStore } from '../../store/useProjectStore';

interface DatasetEntry {
  id: string;
  category: string;
  dataset: string;
  name: string;
  description: string;
  cached: boolean;
  size_bytes: number;
  local_path?: string;
  default_params?: Record<string, any>;
}

const FALLBACK_DATASETS: DatasetEntry[] = [
  {
    id: 'paleo.scotese_1d',
    category: 'paleo',
    dataset: 'scotese',
    name: 'Scotese PALEOMAP 1° PaleoDEMs & PaleoAtlas v3 (0–540 Ma)',
    description: '88 deep-time paleogeographic DEMs (1 deg) + PaleoAtlas v3 rasters & PlateModel.',
    cached: false,
    size_bytes: 0,
    default_params: { resolution: '1d' },
  },
  {
    id: 'paleo.scotese_6m',
    category: 'paleo',
    dataset: 'scotese',
    name: 'Scotese PALEOMAP 6-arcmin High-Res PaleoDEMs (0–540 Ma)',
    description: '88 high-resolution (6 arc-minute) PaleoDEMs from Zenodo Record 5460860.',
    cached: false,
    size_bytes: 0,
    default_params: { resolution: '6m' },
  },
  {
    id: 'topography.earth',
    category: 'topography',
    dataset: 'earth',
    name: 'Earth Global Relief (ETOPO 2022 15m)',
    description: 'NOAA ETOPO 2022 global bedrock/surface relief grid.',
    cached: true,
    size_bytes: 14500000,
    default_params: { resolution: '15m' },
  },
  {
    id: 'topography.gebco',
    category: 'topography',
    dataset: 'gebco',
    name: 'GEBCO Global Bathymetry & Relief',
    description: 'Global ocean bathymetry and land topography grid.',
    cached: false,
    size_bytes: 0,
  },
  {
    id: 'topography.mars',
    category: 'topography',
    dataset: 'mars',
    name: 'Mars MOLA Global Topography',
    description: 'Mars Orbiter Laser Altimeter planetary relief.',
    cached: false,
    size_bytes: 0,
  },
  {
    id: 'topography.moon',
    category: 'topography',
    dataset: 'moon',
    name: 'Moon LOLA Global Topography',
    description: 'Lunar Orbiter Laser Altimeter global elevation.',
    cached: false,
    size_bytes: 0,
  },
  {
    id: 'topography.venus',
    category: 'topography',
    dataset: 'venus',
    name: 'Venus Magellan Global Topography',
    description: 'Magellan radar altimetry global relief of Venus.',
    cached: false,
    size_bytes: 0,
  },
  {
    id: 'topography.mercury',
    category: 'topography',
    dataset: 'mercury',
    name: 'Mercury MESSENGER Global Topography',
    description: 'USGS MESSENGER global DEM of Mercury.',
    cached: false,
    size_bytes: 0,
  },
  {
    id: 'tomography.s40rts',
    category: 'tomography',
    dataset: 's40rts',
    name: 'S40RTS Seismic Mantle Tomography',
    description: '3D shear-wave velocity perturbations in the Earth mantle.',
    cached: false,
    size_bytes: 0,
  },
  {
    id: 'geoid.egm2008',
    category: 'geoid',
    dataset: 'egm2008',
    name: 'EGM2008 Global Geoid Undulation',
    description: 'Earth Gravitational Model 2008 geoid height anomaly.',
    cached: false,
    size_bytes: 0,
  },
  {
    id: 'crust.crust1',
    category: 'crust',
    dataset: 'crust1',
    name: 'CRUST1.0 Global Crustal Boundaries',
    description: '1x1 degree global crustal layers and Moho depth.',
    cached: false,
    size_bytes: 0,
  },
  {
    id: 'lithosphere.thickness',
    category: 'lithosphere',
    dataset: 'thickness',
    name: 'LITHO1.0 Lithospheric Thickness & LAB',
    description: 'Global depth to the Lithosphere-Asthenosphere Boundary.',
    cached: false,
    size_bytes: 0,
  },
  {
    id: 'dynamic_topography.hoggard2016',
    category: 'dynamic_topography',
    dataset: 'hoggard2016',
    name: 'Hoggard et al. (2016) Residual Dynamic Topography',
    description: 'Observational residual dynamic topography spot grid.',
    cached: false,
    size_bytes: 0,
  },
  {
    id: 'gravity.bouguer',
    category: 'gravity',
    dataset: 'bouguer',
    name: 'NOAA Global Bouguer Gravity Anomaly',
    description: 'Global Bouguer gravity anomaly grid.',
    cached: false,
    size_bytes: 0,
  },
  {
    id: 'magnetics.emag2',
    category: 'magnetics',
    dataset: 'emag2',
    name: 'EMAG2v3 Global Magnetic Anomalies',
    description: 'Earth Magnetic Anomaly Grid (2-arc-minute resolution).',
    cached: false,
    size_bytes: 0,
  },
  {
    id: 'shapefiles.land',
    category: 'shapefiles',
    dataset: 'land',
    name: 'Natural Earth 1:110m Land Polygons',
    description: 'Global continental and island polygon boundaries.',
    cached: false,
    size_bytes: 0,
  },
  {
    id: 'shapefiles.coastline',
    category: 'shapefiles',
    dataset: 'coastline',
    name: 'Natural Earth 1:110m Coastline Vectors',
    description: 'Global coastline line vectors.',
    cached: false,
    size_bytes: 0,
  },
];

export const DatasetCacheContent: React.FC = () => {
  const { setStatusMessage } = useProjectStore();
  const [datasets, setDatasets] = useState<DatasetEntry[]>(FALLBACK_DATASETS);
  const [cacheDir, setCacheDir] = useState<string>('.download_cache');
  const [scoteseDir, setScoteseDir] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [browsePath, setBrowsePath] = useState<string>('');
  const [localFiles, setLocalFiles] = useState<Array<{ name: string; path: string; size_bytes?: number }>>([]);

  const loadCatalog = async () => {
    try {
      const res = await fetch('/api/datasets/catalog');
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.datasets)) {
          setDatasets(data.datasets);
          if (data.cache_dir) setCacheDir(data.cache_dir);
          if (data.scotese_dir) setScoteseDir(data.scotese_dir);
        }
      }
    } catch {
      // Keep fallback list
    }
  };

  const loadLocalFolder = async (path?: string) => {
    try {
      const q = path ? `?path=${encodeURIComponent(path)}` : '';
      const res = await fetch(`/api/files/browse${q}`);
      if (res.ok) {
        const data = await res.json();
        setBrowsePath(data.current_path || '');
        setLocalFiles(data.files || []);
      }
    } catch {
      // Ignore offline error
    }
  };

  useEffect(() => {
    loadCatalog();
    loadLocalFolder();
  }, []);

  const handleDownload = async (item: DatasetEntry) => {
    setDownloadingId(item.id);
    setStatusMessage(`Downloading & caching ${item.name}...`);
    try {
      const res = await fetch('/api/datasets/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category: item.category,
          dataset: item.dataset,
          params: item.default_params || {},
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.datasets)) {
          setDatasets(data.datasets);
        }
        setStatusMessage(`Cached ${item.name} successfully!`);
      }
    } catch (err: any) {
      setStatusMessage(`Download failed: ${err?.message || 'error'}`);
    } finally {
      setDownloadingId(null);
    }
  };

  const formatBytes = (b: number) => {
    if (!b || b <= 0) return 'Not cached';
    if (b > 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)} MB`;
    return `${(b / 1024).toFixed(0)} KB`;
  };

  return (
    <div className="space-y-4 text-xs">
      {/* Cache Directory Info */}
      <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-slate-200 flex items-center gap-1.5">
            <HardDrive className="w-4 h-4 text-sky-400" />
            <span>Local Cache & Zenodo/EarthByte Downloader</span>
          </span>
          <button
            onClick={loadCatalog}
            className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-400"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="text-[11px] font-mono text-slate-400 truncate">
          Cache Dir: {cacheDir}
        </div>
        {scoteseDir && (
          <div className="text-[11px] font-mono text-emerald-400 truncate">
            Scotese Dir: {scoteseDir}
          </div>
        )}
      </div>

      {/* Dataset List */}
      <div className="space-y-2">
        {datasets.map((ds) => (
          <div
            key={ds.id}
            className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 flex items-center justify-between gap-2"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-100 truncate">
                  {ds.name}
                </span>
                {ds.cached ? (
                  <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-mono flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" />
                    {formatBytes(ds.size_bytes)}
                  </span>
                ) : (
                  <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px]">
                    Online
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 truncate mt-0.5">
                {ds.description}
              </p>
            </div>

            <button
              onClick={() => handleDownload(ds)}
              disabled={downloadingId === ds.id}
              className="px-2.5 py-1.5 rounded-lg bg-sky-500/15 hover:bg-sky-500 text-sky-300 hover:text-slate-950 font-semibold border border-sky-500/30 flex items-center gap-1 whitespace-nowrap transition"
            >
              <CloudDownload className="w-3.5 h-3.5" />
              <span>
                {downloadingId === ds.id
                  ? 'Caching...'
                  : ds.cached
                  ? 'Re-verify'
                  : 'Download / Cache Now'}
              </span>
            </button>
          </div>
        ))}
      </div>

      {/* Local Folder Browser */}
      <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
        <div className="flex items-center gap-1.5 font-semibold text-slate-200">
          <FolderOpen className="w-4 h-4 text-amber-400" />
          <span>Local Workspace File Browser</span>
        </div>
        <div className="flex gap-1.5">
          <input
            type="text"
            value={browsePath}
            onChange={(e) => setBrowsePath(e.target.value)}
            placeholder="Local directory path..."
            className="flex-1 bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono text-[11px]"
          />
          <button
            onClick={() => loadLocalFolder(browsePath)}
            className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200"
          >
            Browse
          </button>
        </div>
        {localFiles.length > 0 && (
          <div className="max-h-36 overflow-y-auto bg-slate-950 rounded border border-slate-800 p-1.5 space-y-1">
            {localFiles.map((f) => (
              <div
                key={f.path}
                className="flex items-center justify-between text-[11px] font-mono text-slate-300 px-1.5 py-0.5"
              >
                <span className="truncate">{f.name}</span>
                <span className="text-slate-500">{formatBytes(f.size_bytes || 0)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export const DatasetCacheManagerModal: React.FC = () => {
  const { isDatasetModalOpen, setDatasetModalOpen } = useProjectStore();
  if (!isDatasetModalOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-xl shadow-2xl w-full max-w-3xl max-h-[86vh] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-sky-400" />
            <h2 className="text-base font-bold text-white">
              Online Dataset Catalog & Cache Manager
            </h2>
          </div>
          <button
            onClick={() => setDatasetModalOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          <DatasetCacheContent />
        </div>
      </div>
    </div>
  );
};
