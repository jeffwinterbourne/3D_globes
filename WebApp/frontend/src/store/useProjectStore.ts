import { create } from 'zustand';
import {
  ActiveTab,
  BLANK_GLOBE_PROJECT,
  BuilderMode,
  ColourerConfig,
  DEFAULT_STARTER_PROJECT,
  DisplacerConfig,
  ExportConfig,
  FilamentsConfig,
  GeometryConfig,
  GlobeProject,
  GridSourceConfig,
  MagnetSettingsConfig,
  PaleoConfig,
  ProjectSummary,
  ViewMode,
  WorkspaceConfig,
  WorkspaceDatasetEntry,
} from '../types/globeProject';
import {
  decodeBase64ToFloat32,
  decodeBase64ToUint32,
  decodeBase64ToUint8,
} from '../utils/binaryProtocol';
import {
  normalizeIncomingProject,
  toBackendGlobeProjectPayload,
} from '../utils/projectNormalizer';
import {
  CachedGridBuffer,
  CachedMaskBuffer,
  CachedTextureBuffer,
  EvaluatedMeshResult,
  evaluateProjectMeshClient,
} from '../workers/meshPreviewWorker';

export interface MagnetPlacementDetail {
  index: number;
  angle_deg: number;
  center: [number, number, number];
  d_min_at_angle: number;
  d_max_at_angle: number;
  margin_inner: number;
  margin_outer: number;
  needs_boss: boolean;
  valid: boolean;
}

export interface MagnetOptimizationResult {
  angles_deg: number[];
  profile_deg: number[];
  d_min: number[];
  d_max: number[];
  wall_thickness: number[];
  magnets: MagnetPlacementDetail[];
}

let gridFetchTimer: ReturnType<typeof setTimeout> | null = null;
function scheduleGridFetch(fn: () => void, delayMs = 150) {
  if (gridFetchTimer) clearTimeout(gridFetchTimer);
  gridFetchTimer = setTimeout(fn, delayMs);
}

function sampleEquatorialProfileFromPositions(
  positions: Float32Array,
  fallbackRadius: number
): number[] {
  const bins = new Float64Array(360);
  const counts = new Uint32Array(360);
  const n = positions.length;

  for (let i = 0; i < n; i += 3) {
    const x = positions[i];
    const y = positions[i + 1];
    const z = positions[i + 2];
    const r = Math.hypot(x, y, z);
    if (r < 1e-4) continue;
    // Sample vertices within ~8 degrees of the equator (|z/r| <= 0.14)
    if (Math.abs(z / r) <= 0.14) {
      const lonDeg = (Math.atan2(y, x) * 180.0) / Math.PI;
      const deg = ((Math.round(lonDeg) % 360) + 360) % 360;
      bins[deg] += r;
      counts[deg] += 1;
    }
  }

  const out = new Array<number>(360);
  let validCount = 0;
  for (let d = 0; d < 360; d++) {
    if (counts[d] > 0) {
      out[d] = bins[d] / counts[d];
      validCount++;
    } else {
      out[d] = NaN;
    }
  }

  if (validCount === 0) {
    return new Array<number>(360).fill(fallbackRadius);
  }

  // Fill any empty 1-degree bins from nearest valid neighbors
  for (let d = 0; d < 360; d++) {
    if (Number.isNaN(out[d])) {
      for (let step = 1; step < 180; step++) {
        const left = out[(d - step + 360) % 360];
        const right = out[(d + step) % 360];
        if (!Number.isNaN(left) && !Number.isNaN(right)) {
          out[d] = 0.5 * (left + right);
          break;
        } else if (!Number.isNaN(left)) {
          out[d] = left;
          break;
        } else if (!Number.isNaN(right)) {
          out[d] = right;
          break;
        }
      }
      if (Number.isNaN(out[d])) out[d] = fallbackRadius;
    }
  }
  return out;
}

function computeClientMagnetProfile(
  project: GlobeProject,
  meshData: EvaluatedMeshResult
): MagnetOptimizationResult {
  const mag = project.magnets;
  const baseR = project.geometry.radius || 40.0;
  const innerR = project.geometry.hollow
    ? project.geometry.inner_thickness
      ? Math.max(2.0, baseR - project.geometry.inner_thickness)
      : baseR * (project.geometry.inner_ratio || 0.5)
    : 0.0;

  const rawOut =
    meshData?.outerPositions && meshData.outerPositions.length >= 9
      ? sampleEquatorialProfileFromPositions(meshData.outerPositions, baseR)
      : new Array<number>(360).fill(baseR);

  const rawIn =
    project.geometry.hollow && meshData?.innerPositions && meshData.innerPositions.length >= 9
      ? sampleEquatorialProfileFromPositions(meshData.innerPositions, innerR)
      : new Array<number>(360).fill(project.geometry.hollow ? innerR : 0.0);

  const profile_deg: number[] = [];
  const d_min: number[] = [];
  const d_max: number[] = [];
  const wall_thickness: number[] = [];

  for (let deg = 0; deg < 360; deg++) {
    profile_deg.push(deg);
    const rOut = rawOut[deg];
    const rIn = project.geometry.hollow ? rawIn[deg] : 0.0;
    d_min.push(Number(rIn.toFixed(3)));
    d_max.push(Number(rOut.toFixed(3)));
    wall_thickness.push(Number((rOut - rIn).toFixed(3)));
  }

  const holeRadius =
    (mag.diameter || 5.0) * 0.5 + (mag.horizontal_tolerance ?? 0.15);
  const hVoid = (mag.height || 2.0) + (mag.vertical_tolerance ?? 0.1);
  const vOffset = mag.vertical_offset ?? 0.2;
  const minThick = mag.min_thickness ?? 1.5;
  const rEnc = holeRadius + minThick;
  const hBoss = vOffset + hVoid + minThick;

  // Angular half-width of the boss cylinder footprint on the equator
  const footprintDeg = Math.max(
    1,
    Math.ceil((rEnc / Math.max(5.0, baseR)) * (180.0 / Math.PI))
  );

  // Compute 3D cylinder containment bounds [dMinSafe, dMaxSafe] at every degree
  const dMaxSafeArr = new Float64Array(360);
  const dMinSafeArr = new Float64Array(360);

  for (let deg = 0; deg < 360; deg++) {
    let minROutFootprint = d_max[deg];
    let maxRInFootprint = d_min[deg];
    for (let off = -footprintDeg; off <= footprintDeg; off++) {
      const idx = (deg + off + 360) % 360;
      if (d_max[idx] < minROutFootprint) minROutFootprint = d_max[idx];
      if (d_min[idx] > maxRInFootprint) maxRInFootprint = d_min[idx];
    }
    // Outer corner of boss is at (d + rEnc, +-hBoss). To stay inside sphere of radius minROutFootprint:
    // sqrt((d + rEnc)^2 + hBoss^2) <= minROutFootprint  =>  d <= sqrt(minROutFootprint^2 - hBoss^2) - rEnc
    const maxChord = Math.sqrt(Math.max(0.0, minROutFootprint * minROutFootprint - hBoss * hBoss));
    dMaxSafeArr[deg] = Math.max(0.0, maxChord - rEnc);
    dMinSafeArr[deg] = project.geometry.hollow ? maxRInFootprint + rEnc : 0.0;
  }

  const nMag = Math.max(1, mag.n_magnets || 3);
  const angles_deg: number[] = [];
  if (Array.isArray(mag.position) && mag.position.length > 0) {
    for (const a of mag.position) {
      angles_deg.push(((a % 360) + 360) % 360);
    }
  } else {
    const startAngle = typeof mag.position === 'number' ? mag.position : 0;
    for (let k = 0; k < nMag; k++) {
      const targetAng = (((startAngle + (k * 360) / nMag) % 360) + 360) % 360;
      // Nudge within a small window if angle_tolerance > 0 or to find local thickness peak
      const windowDeg = Math.min(20, Math.floor(120 / nMag));
      let bestAng = targetAng;
      let bestMargin = -Infinity;
      for (let off = -windowDeg; off <= windowDeg; off += 2) {
        const cand = (Math.round(targetAng + off) + 360) % 360;
        const m = dMaxSafeArr[cand] - dMinSafeArr[cand] - Math.abs(off) * 0.01;
        if (m > bestMargin) {
          bestMargin = m;
          bestAng = cand;
        }
      }
      angles_deg.push(bestAng);
    }
  }

  const magnets: MagnetPlacementDetail[] = angles_deg.map((ang, idx) => {
    const degIdx = Math.floor(((ang % 360) + 360) % 360) % 360;
    const dMinAt = d_min[degIdx] ?? innerR;
    const dMaxAt = d_max[degIdx] ?? baseR;
    const dMaxSafe = dMaxSafeArr[degIdx];
    const dMinSafe = dMinSafeArr[degIdx];

    let midR: number;
    let needsBoss: boolean;
    if (project.geometry.hollow && dMinSafe <= dMaxSafe) {
      // Fits cleanly inside solid shell without a boss: center in the available range
      midR = 0.5 * (dMinSafe + dMaxSafe);
      needsBoss = false;
    } else {
      // Place at dMaxSafe so the boss is 100% contained inside the outer surface
      midR = dMaxSafe;
      needsBoss = Boolean(project.geometry.hollow);
    }

    const rOuterVoidCorner = Math.hypot(midR + holeRadius, vOffset + hVoid);
    const marginOuter = dMaxAt - rOuterVoidCorner;
    const marginInner = midR - holeRadius - dMinAt;
    const valid =
      marginOuter >= minThick * 0.5 && (mag.allow_bosses || !needsBoss);
    const rad = (ang * Math.PI) / 180;
    const cx = midR * Math.cos(rad);
    const cy = midR * Math.sin(rad);
    return {
      index: idx,
      angle_deg: Number(ang.toFixed(1)),
      center: [Number(cx.toFixed(2)), Number(cy.toFixed(2)), 0],
      d_min_at_angle: Number(dMinAt.toFixed(2)),
      d_max_at_angle: Number(dMaxAt.toFixed(2)),
      margin_inner: Number(marginInner.toFixed(2)),
      margin_outer: Number(marginOuter.toFixed(2)),
      needs_boss: needsBoss,
      valid,
    };
  });

  return {
    angles_deg,
    profile_deg,
    d_min,
    d_max,
    wall_thickness,
    magnets,
  };
}

interface ProjectStoreState {
  project: GlobeProject;
  past: GlobeProject[];
  future: GlobeProject[];
  activeTab: ActiveTab;
  viewMode: ViewMode;
  wireframe: boolean;
  clippingPlane: boolean;
  clippingOffset: number;
  explodeDistance: number;
  showMagnetRing: boolean;
  showAxes: boolean;
  autoRotate: boolean;
  unlitMode: boolean;
  previewMode: 'fast_webgl' | 'exact_python';
  isRightDrawerOpen: boolean;
  isPresetModalOpen: boolean;
  isFilamentModalOpen: boolean;
  isDatasetModalOpen: boolean;
  isEvaluatingPython: boolean;
  statusMessage: string;
  jsonError: string | null;

  gridBuffers: Record<string, CachedGridBuffer>;
  maskBuffers: Record<string, CachedMaskBuffer>;
  textureBuffer: CachedTextureBuffer | null;
  meshData: EvaluatedMeshResult;
  magnetAnalysis: MagnetOptimizationResult;

  // Workspace & Navigation
  currentView: 'landing' | 'editor';
  isWizardOpen: boolean;
  isWorkspaceDataModalOpen: boolean;
  workingDir: string;
  projectsList: ProjectSummary[];
  workspaceDatasets: WorkspaceDatasetEntry[];
  currentProjectSlug: string | null;

  // Actions
  setCurrentView: (view: 'landing' | 'editor') => void;
  setWizardOpen: (open: boolean) => void;
  setWorkspaceDataModalOpen: (open: boolean) => void;
  fetchWorkspaceConfig: () => Promise<void>;
  setWorkingDir: (dir: string) => Promise<void>;
  fetchWorkspaceProjects: () => Promise<void>;
  openWorkspaceProject: (slug: string) => Promise<void>;
  openWorkspaceProjectAsCopy: (slug: string) => Promise<void>;
  saveCurrentProjectToWorkspace: (slug?: string) => Promise<void>;
  loadBlankProject: () => void;
  fetchWorkspaceDatasets: () => Promise<void>;
  registerWorkspaceDataset: (entry: Partial<WorkspaceDatasetEntry>) => Promise<void>;
  duplicateWorkspaceDataset: (sourceId: string, newName?: string, defaultOps?: any[]) => Promise<void>;

  setActiveTab: (tab: ActiveTab) => void;
  setViewMode: (mode: ViewMode) => void;
  setWireframe: (v: boolean) => void;
  setClippingPlane: (v: boolean) => void;
  setClippingOffset: (v: number) => void;
  setExplodeDistance: (v: number) => void;
  setShowMagnetRing: (v: boolean) => void;
  setShowAxes: (v: boolean) => void;
  setAutoRotate: (v: boolean) => void;
  setUnlitMode: (v: boolean) => void;
  setRightDrawerOpen: (v: boolean) => void;
  setPresetModalOpen: (v: boolean) => void;
  setFilamentModalOpen: (v: boolean) => void;
  setDatasetModalOpen: (v: boolean) => void;
  setStatusMessage: (msg: string) => void;

  setProject: (next: GlobeProject | any, recordHistory?: boolean) => void;
  updateProject: (updater: (draft: GlobeProject) => GlobeProject, recordHistory?: boolean) => void;
  setBuilderMode: (mode: BuilderMode) => void;
  updateGeometry: (patch: Partial<GeometryConfig>) => void;
  updatePaleo: (patch: Partial<PaleoConfig>) => void;
  updateMagnets: (patch: Partial<MagnetSettingsConfig>) => void;
  updateFilaments: (patch: Partial<FilamentsConfig>) => void;
  updateExport: (patch: Partial<ExportConfig>) => void;
  upsertGrid: (id: string, cfg: GridSourceConfig) => void;
  removeGrid: (id: string) => void;
  setOuterDisplacements: (list: DisplacerConfig[]) => void;
  setInnerDisplacements: (list: DisplacerConfig[]) => void;
  setColourers: (list: ColourerConfig[]) => void;
  convertPaleoToCustomRecipe: () => void;

  undo: () => void;
  redo: () => void;

  recomputeFastPreview: (overridePoints?: number) => void;
  fetchGridDataFromBackend: () => Promise<void>;
  renderExactPythonMesh: (mode?: 'preview' | 'full') => Promise<void>;
  optimizeMagnetsBackend: () => Promise<void>;
}

const initialMesh = evaluateProjectMeshClient(DEFAULT_STARTER_PROJECT, {});
const initialMagnets = computeClientMagnetProfile(DEFAULT_STARTER_PROJECT, initialMesh);

export const useProjectStore = create<ProjectStoreState>((set, get) => ({
  project: DEFAULT_STARTER_PROJECT,
  past: [],
  future: [],
  activeTab: 'geometry',
  viewMode: 'whole',
  wireframe: false,
  clippingPlane: false,
  clippingOffset: 0,
  explodeDistance: 22,
  showMagnetRing: true,
  showAxes: true,
  autoRotate: false,
  unlitMode: false,
  previewMode: 'fast_webgl',
  isRightDrawerOpen: true,
  isPresetModalOpen: false,
  isFilamentModalOpen: false,
  isDatasetModalOpen: false,
  isWizardOpen: false,
  isWorkspaceDataModalOpen: false,
  isEvaluatingPython: false,
  statusMessage: 'Ready — 60fps WebGL Preview Active',
  jsonError: null,

  currentView: 'landing',
  workingDir: '',
  projectsList: [],
  workspaceDatasets: [],
  currentProjectSlug: null,

  setCurrentView: (view) => set({ currentView: view }),
  setWizardOpen: (open) => set({ isWizardOpen: open }),
  setWorkspaceDataModalOpen: (open) => set({ isWorkspaceDataModalOpen: open }),

  fetchWorkspaceConfig: async () => {
    try {
      const res = await fetch('/api/workspace/config');
      if (!res.ok) return;
      const data = await res.json();
      if (data && data.working_dir) {
        set({ workingDir: data.working_dir });
      }
    } catch {}
  },

  setWorkingDir: async (dir: string) => {
    try {
      const res = await fetch('/api/workspace/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ working_dir: dir }),
      });
      if (res.ok) {
        const data = await res.json();
        set({ workingDir: data.working_dir });
        get().fetchWorkspaceProjects();
        get().fetchWorkspaceDatasets();
      }
    } catch {}
  },

  fetchWorkspaceProjects: async () => {
    try {
      const res = await fetch('/api/workspace/projects');
      if (!res.ok) return;
      const data = await res.json();
      if (data && Array.isArray(data.projects)) {
        set({ projectsList: data.projects });
      }
    } catch {}
  },

  openWorkspaceProject: async (slug: string) => {
    try {
      set({ statusMessage: `Opening project ${slug}...` });
      const res = await fetch('/api/workspace/projects/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug_or_path: slug }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data && data.project) {
        const normalized = normalizeIncomingProject(data.project);
        set({
          project: normalized,
          past: [],
          future: [],
          currentProjectSlug: slug,
          currentView: 'editor',
          statusMessage: `Opened ${normalized.name || slug}`,
        });
        get().fetchGridDataFromBackend();
      }
    } catch (err: any) {
      set({ statusMessage: `Failed to open project: ${err.message}` });
    }
  },

  openWorkspaceProjectAsCopy: async (slug: string) => {
    try {
      set({ statusMessage: `Duplicating project ${slug}...` });
      const res = await fetch('/api/workspace/projects/duplicate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data && data.slug) {
        await get().fetchWorkspaceProjects();
        await get().openWorkspaceProject(data.slug);
      }
    } catch (err: any) {
      set({ statusMessage: `Failed to duplicate project: ${err.message}` });
    }
  },

  saveCurrentProjectToWorkspace: async (slug?: string) => {
    const { project, currentProjectSlug } = get();
    const targetSlug = slug || currentProjectSlug || undefined;
    try {
      set({ statusMessage: 'Saving project to workspace...' });
      const res = await fetch('/api/workspace/projects/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project: toBackendGlobeProjectPayload(project), slug: targetSlug }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data && data.slug) {
        set({
          currentProjectSlug: data.slug,
          statusMessage: `Project saved successfully (${data.slug})`,
        });
        get().fetchWorkspaceProjects();
      }
    } catch (err: any) {
      set({ statusMessage: `Save failed: ${err.message}` });
    }
  },

  loadBlankProject: () => {
    const fresh = JSON.parse(JSON.stringify(BLANK_GLOBE_PROJECT));
    set({
      project: fresh,
      past: [],
      future: [],
      currentProjectSlug: null,
      currentView: 'editor',
      statusMessage: 'Loaded blank hollow globe project',
    });
    get().recomputeFastPreview();
  },

  fetchWorkspaceDatasets: async () => {
    try {
      const res = await fetch('/api/workspace/datasets');
      if (!res.ok) return;
      const data = await res.json();
      if (data && Array.isArray(data.datasets)) {
        set({ workspaceDatasets: data.datasets });
      }
    } catch {}
  },

  registerWorkspaceDataset: async (entry: Partial<WorkspaceDatasetEntry>) => {
    try {
      const res = await fetch('/api/workspace/datasets/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entry }),
      });
      if (res.ok) {
        get().fetchWorkspaceDatasets();
      }
    } catch {}
  },

  duplicateWorkspaceDataset: async (sourceId: string, newName?: string, defaultOps?: any[]) => {
    try {
      set({ statusMessage: 'Creating virtual dataset profile...' });
      const res = await fetch('/api/workspace/datasets/duplicate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: sourceId, new_name: newName, default_ops: defaultOps }),
      });
      if (res.ok) {
        set({ statusMessage: 'Virtual dataset profile created (0-byte overhead)' });
        get().fetchWorkspaceDatasets();
      }
    } catch (err: any) {
      set({ statusMessage: `Failed to duplicate dataset: ${err.message}` });
    }
  },

  gridBuffers: {},
  maskBuffers: {},
  textureBuffer: null,
  meshData: initialMesh,
  magnetAnalysis: initialMagnets,

  setActiveTab: (tab) => set({ activeTab: tab }),
  setViewMode: (mode) => set({ viewMode: mode }),
  setWireframe: (v) => set({ wireframe: v }),
  setClippingPlane: (v) => set({ clippingPlane: v }),
  setClippingOffset: (v) => set({ clippingOffset: v }),
  setExplodeDistance: (v) => set({ explodeDistance: v }),
  setShowMagnetRing: (v) => set({ showMagnetRing: v }),
  setShowAxes: (v) => set({ showAxes: v }),
  setAutoRotate: (v) => set({ autoRotate: v }),
  setUnlitMode: (v) => set({ unlitMode: v }),
  setRightDrawerOpen: (v) => set({ isRightDrawerOpen: v }),
  setPresetModalOpen: (v) => set({ isPresetModalOpen: v }),
  setFilamentModalOpen: (v) => set({ isFilamentModalOpen: v }),
  setDatasetModalOpen: (v) => set({ isDatasetModalOpen: v }),
  setStatusMessage: (msg) => set({ statusMessage: msg }),

  setProject: (rawNext, recordHistory = true) => {
    const state = get();
    const next = normalizeIncomingProject(rawNext);
    const past = recordHistory ? [...state.past.slice(-25), state.project] : state.past;
    const meshData = evaluateProjectMeshClient(next, state.gridBuffers, state.textureBuffer, undefined, state.maskBuffers);
    const magnetAnalysis = computeClientMagnetProfile(next, meshData);
    set({
      project: next,
      past,
      future: recordHistory ? [] : state.future,
      previewMode: 'fast_webgl',
      meshData,
      magnetAnalysis,
      jsonError: null,
    });
  },

  updateProject: (updater, recordHistory = true) => {
    const state = get();
    const cloned = JSON.parse(JSON.stringify(state.project)) as GlobeProject;
    const next = updater(cloned);
    state.setProject(next, recordHistory);
  },

  setBuilderMode: (mode) => {
    const state = get();
    state.updateProject((draft) => {
      draft.mode = mode;
      if (!draft.paleo) {
        draft.paleo = JSON.parse(JSON.stringify(DEFAULT_STARTER_PROJECT.paleo));
      }
      draft.paleo!.enabled = mode === 'paleo';
      return draft;
    });
    set({ activeTab: mode === 'paleo' ? 'paleo' : 'geometry' });
    scheduleGridFetch(() => get().fetchGridDataFromBackend());
  },

  updateGeometry: (patch) => {
    get().updateProject((draft) => {
      draft.geometry = { ...draft.geometry, ...patch };
      return draft;
    });
  },

  updatePaleo: (patch) => {
    const prevAge = get().project.paleo?.age;
    const prevRes = get().project.paleo?.resolution;
    get().updateProject((draft) => {
      draft.paleo = {
        ...(draft.paleo || DEFAULT_STARTER_PROJECT.paleo!),
        ...patch,
      };
      return draft;
    });
    if (patch.age !== undefined && patch.age !== prevAge) {
      scheduleGridFetch(() => get().fetchGridDataFromBackend());
    } else if (patch.resolution !== undefined && patch.resolution !== prevRes) {
      scheduleGridFetch(() => get().fetchGridDataFromBackend());
    }
  },

  updateMagnets: (patch) => {
    get().updateProject((draft) => {
      draft.magnets = { ...draft.magnets, ...patch };
      return draft;
    });
  },

  updateFilaments: (patch) => {
    get().updateProject((draft) => {
      draft.filaments = {
        ...(draft.filaments || DEFAULT_STARTER_PROJECT.filaments!),
        ...patch,
      };
      return draft;
    });
  },

  updateExport: (patch) => {
    get().updateProject((draft) => {
      draft.export = { ...draft.export, ...patch };
      return draft;
    });
  },

  upsertGrid: (id, cfg) => {
    get().updateProject((draft) => {
      draft.grids = { ...draft.grids, [id]: cfg };
      return draft;
    });
    scheduleGridFetch(() => get().fetchGridDataFromBackend());
  },

  removeGrid: (id) => {
    get().updateProject((draft) => {
      const nextGrids = { ...draft.grids };
      delete nextGrids[id];
      draft.grids = nextGrids;
      return draft;
    });
  },

  setOuterDisplacements: (list) => {
    get().updateProject((draft) => {
      draft.outer_displacements = list;
      return draft;
    });
  },

  setInnerDisplacements: (list) => {
    get().updateProject((draft) => {
      draft.inner_displacements = list;
      return draft;
    });
  },

  setColourers: (list) => {
    get().updateProject((draft) => {
      draft.colourers = list;
      return draft;
    });
  },

  convertPaleoToCustomRecipe: () => {
    const state = get();
    const p = state.project.paleo || DEFAULT_STARTER_PROJECT.paleo!;
    state.updateProject((draft) => {
      draft.mode = 'custom';
      if (draft.paleo) draft.paleo.enabled = false;
      const gridId = `scotese_${Math.round(p.age)}ma`;
      draft.grids[gridId] = {
        source_type: 'paleo',
        category: 'paleo',
        name: 'scotese',
        age: p.age,
        resolution: p.resolution,
      };
      draft.outer_displacements = [
        {
          id: 'disp_paleo_dem',
          enabled: true,
          type: 'GridDisplacer',
          grid_id: gridId,
          scale_mode: 'physical',
          vertical_exagg: p.vert_exagg,
          grid_units: 'm',
          reference_level: 0.0,
          coastline_step:
            p.coastline_step > 10
              ? Number(
                  ((p.coastline_step * draft.geometry.radius * p.vert_exagg) / 6371000).toFixed(2)
                )
              : p.coastline_step,
          step_threshold: 0.0,
          interp_method: 'linear',
        },
      ];
      const nextColourers: ColourerConfig[] = [];
      if (p.color_mode === 'paleo_atlas') {
        nextColourers.push({
          id: 'col_paleo_atlas',
          enabled: true,
          target: 'outer',
          selection: 'outward_facing',
          type: 'ImageColourer',
          image_source: 'paleo_atlas',
          paleo_age: p.age,
          preprocessors: p.undo_shading
            ? [{ type: 'undo_hillshading', enabled: true, strength: 0.8 }]
            : [],
        });
      } else {
        nextColourers.push({
          id: 'col_paleo_grid',
          enabled: true,
          target: 'outer',
          selection: 'outward_facing',
          type: 'GridColourer',
          grid_id: gridId,
          colormap_mode: p.color_mode === 'filament_banded' ? 'banded' : 'continuous',
          colormap: p.colormap || 'terrain',
          vmin: -6000,
          vmax: 5000,
        });
      }
      if (p.tracked_locations && p.tracked_locations.length > 0) {
        nextColourers.push({
          id: 'col_paleo_landmarks',
          enabled: true,
          target: 'outer',
          selection: 'outward_facing',
          type: 'SymbolColourer',
          symbol: 'star',
          reference: 'modern',
          age: p.age,
          plate_model: p.plate_model,
          locations: p.tracked_locations,
        });
      }
      if (p.mark_poles) {
        nextColourers.push({
          id: 'col_paleo_poles',
          enabled: true,
          target: 'outer',
          selection: 'outward_facing',
          type: 'PoleLabelColourer',
          radius_degrees: 4.5,
          north_color: '#ef4444',
          south_color: '#3b82f6',
          north_symbol: 'N',
          south_symbol: 'S',
          reference: 'paleo',
          age: p.age,
          plate_model: p.plate_model,
        });
      }
      draft.colourers = nextColourers;
      return draft;
    });
    set({
      activeTab: 'displacers',
      statusMessage: `Converted ${p.age} Ma Paleo configuration into explicit Custom Layer Recipe`,
    });
  },

  undo: () => {
    const state = get();
    if (state.past.length === 0) return;
    const prev = state.past[state.past.length - 1];
    const nextPast = state.past.slice(0, -1);
    const meshData = evaluateProjectMeshClient(prev, state.gridBuffers, state.textureBuffer, undefined, state.maskBuffers);
    set({
      project: prev,
      past: nextPast,
      future: [state.project, ...state.future],
      meshData,
      magnetAnalysis: computeClientMagnetProfile(prev, meshData),
    });
  },

  redo: () => {
    const state = get();
    if (state.future.length === 0) return;
    const next = state.future[0];
    const nextFuture = state.future.slice(1);
    const meshData = evaluateProjectMeshClient(next, state.gridBuffers, state.textureBuffer, undefined, state.maskBuffers);
    set({
      project: next,
      past: [...state.past, state.project],
      future: nextFuture,
      meshData,
      magnetAnalysis: computeClientMagnetProfile(next, meshData),
    });
  },

  recomputeFastPreview: (overridePoints) => {
    const state = get();
    const meshData = evaluateProjectMeshClient(
      state.project,
      state.gridBuffers,
      state.textureBuffer,
      overridePoints,
      state.maskBuffers
    );
    set({
      meshData,
      previewMode: 'fast_webgl',
      magnetAnalysis: computeClientMagnetProfile(state.project, meshData),
    });
  },

  fetchGridDataFromBackend: async () => {
    const state = get();
    try {
      set({ statusMessage: 'Syncing downsampled grid buffers from Python backend...' });
      const res = await fetch('/api/preview/grid-data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(toBackendGlobeProjectPayload(state.project)),
      });
      if (!res.ok) return;
      const data = await res.json();
      const nextGridBuffers: Record<string, CachedGridBuffer> = { ...state.gridBuffers };

      if (data.grids && typeof data.grids === 'object') {
        for (const [gid, gInfo] of Object.entries<any>(data.grids)) {
          const b64 = gInfo?.elevation_f32_b64 || gInfo?.values_b64 || gInfo?.grid_b64;
          if (b64) {
            nextGridBuffers[gid] = {
              nLat: gInfo.height || data.height || 180,
              nLon: gInfo.width || data.width || 360,
              values: decodeBase64ToFloat32(b64),
              min: gInfo.vmin ?? data.vmin,
              max: gInfo.vmax ?? data.vmax,
            };
          }
        }
      }

      if (data.elevation_f32_b64 || data.values_b64 || data.grid_b64) {
        const vals = decodeBase64ToFloat32(
          data.elevation_f32_b64 || data.values_b64 || data.grid_b64
        );
        const firstId = Object.keys(state.project.grids)[0] || 'default';
        if (!nextGridBuffers[firstId]) {
          nextGridBuffers[firstId] = {
            nLat: data.height || data.n_lat || 180,
            nLon: data.width || data.n_lon || 360,
            values: vals,
            min: data.vmin,
            max: data.vmax,
          };
        }
        if (state.project.mode === 'paleo' || state.project.paleo?.enabled) {
          nextGridBuffers['paleo_dem'] = {
            nLat: data.height || data.n_lat || 180,
            nLon: data.width || data.n_lon || 360,
            values: vals,
            min: data.vmin,
            max: data.vmax,
          };
        }
      }

      let nextTexture = state.textureBuffer;
      if (data.rgb_u8_b64 || data.texture_b64) {
        nextTexture = {
          width: data.width || data.texture_width || 360,
          height: data.height || data.texture_height || 180,
          rgb: decodeBase64ToUint8(data.rgb_u8_b64 || data.texture_b64),
          channels: data.texture_channels || 3,
        };
      }

      const nextMaskBuffers: Record<string, CachedMaskBuffer> = { ...state.maskBuffers };
      if (data.masks && typeof data.masks === 'object') {
        for (const [mid, mInfo] of Object.entries<any>(data.masks)) {
          const b64 = mInfo?.mask_u8_b64 || mInfo?.values_b64;
          if (b64) {
            nextMaskBuffers[mid] = {
              width: mInfo.width || data.width || 360,
              height: mInfo.height || data.height || 180,
              values: decodeBase64ToUint8(b64),
            };
          }
        }
      }

      const currentProj = get().project;
      const meshData = evaluateProjectMeshClient(
        currentProj,
        nextGridBuffers,
        nextTexture,
        undefined,
        nextMaskBuffers
      );
      const magnetAnalysis = computeClientMagnetProfile(currentProj, meshData);
      set({
        gridBuffers: nextGridBuffers,
        maskBuffers: nextMaskBuffers,
        textureBuffer: nextTexture,
        meshData,
        magnetAnalysis,
        statusMessage: '60fps WebGL Preview Active (Synced with Python grids)',
      });
    } catch {
      // Offline or backend still starting; client procedural fallback continues seamlessly
    }
  },

  renderExactPythonMesh: async (mode: 'preview' | 'full' = 'preview') => {
    const state = get();
    const targetPts =
      mode === 'full'
        ? state.project.geometry.n_points || 500000
        : state.project.geometry.preview_n_points || 60000;
    const modeLabel = mode === 'full' ? 'Full Output' : 'Preview';
    set({
      isEvaluatingPython: true,
      statusMessage: `Running definitive Python GlobeModel evaluation (${modeLabel} — ${targetPts.toLocaleString()} pts)...`,
    });
    try {
      const res = await fetch(`/api/preview/eval?preview_n_points=${targetPts}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(toBackendGlobeProjectPayload(state.project)),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      const outerPositions = decodeBase64ToFloat32(data.outer_positions_b64);
      const outerIndices = decodeBase64ToUint32(data.outer_indices_b64);
      const outerColors = decodeBase64ToFloat32(data.outer_colors_b64);
      const innerPositions = decodeBase64ToFloat32(data.inner_positions_b64);
      const innerIndices = decodeBase64ToUint32(data.inner_indices_b64);
      const innerColors = decodeBase64ToFloat32(data.inner_colors_b64);

      if (outerPositions.length > 0 && outerIndices.length > 0) {
        const exactMesh: EvaluatedMeshResult = {
          outerPositions,
          outerIndices,
          outerColors,
          innerPositions,
          innerIndices,
          innerColors,
          stats: data.stats || state.meshData.stats,
        };
        const magnetAnalysis = computeClientMagnetProfile(state.project, exactMesh);
        set({
          meshData: exactMesh,
          magnetAnalysis,
          previewMode: 'exact_python',
          isEvaluatingPython: false,
          statusMessage: `Definitive Python Mesh Active (${modeLabel} — ${(
            data.stats?.vertex_count || outerPositions.length / 3
          ).toLocaleString()} vertices)`,
        });
      } else {
        set({
          isEvaluatingPython: false,
          statusMessage: 'Python evaluation returned empty buffers; keeping WebGL mesh.',
        });
      }
    } catch (err: any) {
      set({
        isEvaluatingPython: false,
        statusMessage: `Python backend unreachable (${err?.message || 'error'}) — showing client 3D mesh`,
      });
    }
  },

  optimizeMagnetsBackend: async () => {
    const state = get();
    set({ statusMessage: 'Optimizing equatorial magnet placement via Python backend...' });
    try {
      const res = await fetch('/api/magnets/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(toBackendGlobeProjectPayload(state.project)),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: MagnetOptimizationResult = await res.json();
      if (data && Array.isArray(data.magnets)) {
        set({
          magnetAnalysis: data,
          statusMessage: `Magnet optimization complete: ${data.magnets.length} positions evaluated`,
        });
        if (Array.isArray(data.angles_deg) && data.angles_deg.length > 0) {
          state.updateMagnets({ position: data.angles_deg });
        }
      }
    } catch {
      const fallback = computeClientMagnetProfile(state.project, state.meshData);
      set({
        magnetAnalysis: fallback,
        statusMessage: 'Computed equatorial magnet optimization profile locally',
      });
    }
  },
}));
