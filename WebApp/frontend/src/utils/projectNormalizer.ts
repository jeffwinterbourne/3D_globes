import {
  DEFAULT_STARTER_PROJECT,
  GlobeProject,
  GridSourceConfig,
} from '../types/globeProject';

/**
 * Normalizes any incoming preset JSON (whether in backend Pydantic GlobeProject shape
 * or frontend GlobeProject shape) so the UI controls and WebWorker have every field populated.
 */
export function normalizeIncomingProject(raw: any): GlobeProject {
  if (!raw || typeof raw !== 'object') {
    return JSON.parse(JSON.stringify(DEFAULT_STARTER_PROJECT));
  }

  const base: GlobeProject = JSON.parse(JSON.stringify(DEFAULT_STARTER_PROJECT));
  const meta = raw.metadata || {};

  const id =
    raw.id ||
    (meta.name ? meta.name.toLowerCase().replace(/[^a-z0-9]+/g, '_') : base.id);
  const name = raw.name || meta.name || base.name;
  const category = raw.category || meta.collection || meta.category || base.category;
  const description = raw.description || meta.description || base.description;
  const mode = raw.mode === 'paleo' ? 'paleo' : 'custom';

  // Normalize Paleo
  const pc = raw.paleo || raw.paleo_config || {};
  const colorModeMap: Record<string, 'paleo_atlas' | 'filament_banded' | 'scientific_cmap'> = {
    paleoatlas: 'paleo_atlas',
    paleo_atlas: 'paleo_atlas',
    banded_4filament: 'filament_banded',
    filament_banded: 'filament_banded',
    colormap: 'scientific_cmap',
    scientific_cmap: 'scientific_cmap',
  };

  const paleo = {
    ...base.paleo!,
    enabled: Boolean(pc.enabled ?? mode === 'paleo'),
    age: Number(pc.age ?? 250),
    resolution: (pc.resolution === '6m' ? '6m' : '1d') as '6m' | '1d',
    plate_model: pc.plate_model || 'Scotese_PALEOMAP',
    vert_exagg: Number(pc.vert_exagg ?? 40),
    coastline_step: Number(pc.coastline_step ?? 800),
    color_mode: colorModeMap[pc.color_mode] || 'paleo_atlas',
    colormap: pc.colormap || pc.cmap || 'terrain',
    undo_shading: Boolean(pc.undo_shading ?? true),
    mark_poles: Boolean(pc.mark_poles ?? true),
    tracked_locations: Array.isArray(pc.tracked_locations)
      ? pc.tracked_locations
      : base.paleo!.tracked_locations,
  };

  // Normalize Geometry
  const rg = raw.geometry || {};
  const geometry = {
    ...base.geometry,
    method: ((rg.method || rg.distribution) === 'icosahedron'
      ? 'icosahedron'
      : 'fibonacci') as 'fibonacci' | 'icosahedron',
    n_points: Number(rg.n_points ?? 500000),
    preview_n_points: Number(rg.preview_n_points ?? 60000),
    radius: Number(rg.radius ?? 40),
    center: (Array.isArray(rg.center) && rg.center.length === 3
      ? rg.center
      : [0, 0, 0]) as [number, number, number],
    hollow: Boolean(rg.hollow ?? true),
    inner_ratio: Number(rg.inner_ratio ?? 0.5),
    inner_n_points: rg.inner_n_points ?? null,
    inner_thickness:
      rg.inner_thickness ?? rg.create_inner_mesh_from_outer_thickness ?? null,
    fix_intersection: rg.fix_intersection || base.geometry.fix_intersection,
  };

  // Normalize Grids (accept either array of GridSourceModel or Record<string, GridSourceConfig>)
  const grids: Record<string, GridSourceConfig> = {};
  if (Array.isArray(raw.grids)) {
    for (const g of raw.grids) {
      const gid = g.id || `grid_${Object.keys(grids).length + 1}`;
      const dsParts = (g.dataset || 'topography.earth').split('.');
      grids[gid] = {
        id: gid,
        source_type: g.source || g.source_type || 'online',
        category: dsParts[0] || 'topography',
        name: dsParts[1] || 'earth',
        dataset: g.dataset,
        resolution: g.params?.resolution || '30m',
        depth: g.params?.depth,
        layer: g.params?.layer,
        age: g.params?.age,
        local_path: g.filepath || g.local_path,
        netcdf_vars: {
          lat_var: g.lat_var || 'lat',
          lon_var: g.lon_var || 'lon',
          data_var: g.data_var || 'z',
        },
        transforms: Array.isArray(g.ops)
          ? g.ops.map((op: any) => ({
              type: op.op === 'composite' ? 'weighted_composite' : op.op || 'downsample',
              step_lat: op.factor || 2,
              step_lon: op.factor || 2,
              ref_thickness: (op.t0_km || 30) * 1000,
              age: op.age,
              plate_model: op.plate_model,
              scale: op.scale,
              offset: op.offset,
            }))
          : [],
      };
    }
  } else if (raw.grids && typeof raw.grids === 'object') {
    Object.assign(grids, raw.grids);
  }
  if (Object.keys(grids).length === 0) {
    Object.assign(grids, base.grids);
  }

  // Normalize Displacements
  const firstGridId = Object.keys(grids)[0] || 'etopo_ds';
  const normDisp = (arr: any[], prefix: string) =>
    (Array.isArray(arr) ? arr : []).map((d, idx) => ({
      id: d.id || `${prefix}_${idx + 1}`,
      enabled: Boolean(d.enabled ?? true),
      type: d.type || 'GridDisplacer',
      grid_id: d.grid_id || firstGridId,
      scale_mode: (d.scale_mode === 'explicit' || d.scale_mode === 'direct'
        ? 'direct'
        : 'physical') as 'physical' | 'direct',
      vertical_exagg: Number(d.vertical_exagg ?? d.vert_exagg ?? 40),
      vert_exagg: Number(d.vert_exagg ?? d.vertical_exagg ?? 40),
      grid_units: (d.grid_units || d.data_unit || 'm') as any,
      scale: Number(d.scale ?? 1.0),
      reference_level: Number(d.reference_level ?? 0),
      coastline_step: Number(d.coastline_step ?? 0),
      step_threshold: Number(d.step_threshold ?? 0),
      displacement: Number(d.displacement ?? d.value ?? d.height ?? 0.8),
      displace_inside: d.displace_inside !== false,
      shapefile: d.shapefile || '',
      radius_degrees: Number(d.radius_degrees ?? d.radius_deg ?? 3.0),
      width_degrees: Number(d.width_degrees ?? d.width_deg ?? 1.0),
    }));

  const outer_displacements = normDisp(
    raw.outer_displacements || base.outer_displacements,
    'disp_out'
  );
  const inner_displacements = normDisp(raw.inner_displacements || [], 'disp_in');

  // Normalize Colourers
  const colourers = (Array.isArray(raw.colourers) ? raw.colourers : base.colourers).map(
    (c: any, idx: number) => ({
      id: c.id || `col_${idx + 1}`,
      enabled: Boolean(c.enabled ?? true),
      target: c.target || 'outer',
      selection: c.selection || 'all',
      blend_mode: c.blend_mode || 'replace',
      type: c.type || 'GridColourer',
      grid_id: c.grid_id || firstGridId,
      colormap_mode: c.use_banded_levels
        ? (Array.isArray(c.colors) && c.colors.length > 0 && Array.isArray(c.levels) && c.levels.length > 0 ? 'listed' : 'banded')
        : c.colormap_mode || 'continuous',
      colormap: c.colormap || c.cmap || 'terrain',
      vmin: c.vmin ?? -6000,
      vmax: c.vmax ?? 5000,
      listed_colors: Array.isArray(c.listed_colors)
        ? c.listed_colors
        : Array.isArray(c.colors) && c.colors.length > 0
        ? c.colors
        : undefined,
      thresholds: Array.isArray(c.thresholds)
        ? c.thresholds
        : Array.isArray(c.levels) && c.levels.length > 0
        ? c.levels
        : undefined,
      color: c.color ?? '#3b82f6',
      image_path: c.image_path || '',
      points: Array.isArray(c.points) ? c.points : undefined,
      locations: Array.isArray(c.locations) ? c.locations : undefined,
      radius_degrees: Number(c.radius_degrees ?? c.radius_deg ?? c.size_deg ?? 3.0),
      width_degrees: Number(c.width_degrees ?? c.width_deg ?? 1.0),
      symbol: c.symbol || 'star',
      text: c.text || 'EARTH',
      lat: Number(c.lat ?? 0),
      lon: Number(c.lon ?? 0),
      height_degrees: Number(c.height_degrees ?? c.size_deg ?? 6.0),
      north_symbol: c.north_symbol || c.north_text || 'N',
      south_symbol: c.south_symbol || c.south_text || 'S',
      preprocessors: Array.isArray(c.preprocessors)
        ? c.preprocessors.map((p: any) => ({
            type: p.type || p.op || 'undo_hillshading',
            enabled: Boolean(p.enabled ?? true),
          }))
        : [],
    })
  );

  // Normalize Magnets
  const rm = raw.magnets || {};
  const hasExplicitAngles =
    Array.isArray(rm.manual_angles) &&
    rm.manual_angles.length > 0 &&
    rm.Optimize_positions !== true &&
    rm.optimize_positions !== true;
  const magnets = {
    ...base.magnets,
    enabled: Boolean(rm.enabled ?? true),
    diameter: Number(rm.diameter ?? 5.0),
    height: Number(rm.height ?? 2.0),
    n_magnets: Number(rm.n_magnets ?? rm.count ?? 3),
    position: hasExplicitAngles
      ? rm.manual_angles
      : Array.isArray(rm.position) && rm.position.length > 0
      ? rm.position
      : Number(typeof rm.position === 'number' ? rm.position : 0),
    horizontal_tolerance: Number(rm.horizontal_tolerance ?? rm.clearance ?? 0.15),
    vertical_tolerance: Number(rm.vertical_tolerance ?? rm.clearance ?? 0.1),
    vertical_offset: Number(rm.vertical_offset ?? rm.embed_depth ?? 0.2),
    min_thickness: Number(rm.min_thickness ?? rm.min_margin ?? 1.5),
    allow_bosses:
      rm.allow_bosses !== undefined
        ? Boolean(rm.allow_bosses)
        : Number(rm.boss_thickness ?? 1.2) > 0,
  };

  // Normalize Export
  const re = raw.export || {};
  const exportCfg = {
    ...base.export,
    mode: (re.split_hemispheres === false || re.mode === 'whole'
      ? 'whole'
      : 'hemispheres') as 'hemispheres' | 'whole',
    format: (re.format || '3mf') as '3mf' | 'obj' | 'stl',
    single_file_3mf: re.dual_files !== undefined ? !re.dual_files : true,
    filename: re.filename || `${re.filename_prefix || id}.${re.format || '3mf'}`,
    output_dir: re.output_dir || 'outputs',
  };

  return {
    ...base,
    id,
    name,
    category,
    description,
    mode,
    paleo,
    geometry,
    grids,
    outer_displacements,
    inner_displacements,
    colourers,
    magnets,
    export: exportCfg,
  };
}

/**
 * Converts a frontend GlobeProject into a payload that satisfies the backend
 * Pydantic `GlobeProject` model in `WebApp/backend/models.py`.
 */
export function toBackendGlobeProjectPayload(project: GlobeProject): any {
  const p = project.paleo || DEFAULT_STARTER_PROJECT.paleo!;
  const f = project.filaments || DEFAULT_STARTER_PROJECT.filaments!;

  const gridsArray = Object.entries(project.grids || {}).map(([gid, g]) => {
    const sourceMap: Record<string, string> = {
      online: 'online',
      local_or_dataset: 'local_or_dataset',
      local: 'local',
      paleo: 'paleo',
      synthetic: 'synthetic',
    };
    const cat = g.category || g.fallback_dataset?.category || 'topography';
    const nm = g.name || g.fallback_dataset?.name || 'earth';
    return {
      id: gid,
      source: sourceMap[g.source_type] || 'online',
      dataset: g.dataset || `${cat}.${nm}`,
      params: {
        ...(g.resolution ? { resolution: g.resolution } : {}),
        ...(g.depth !== undefined ? { depth: g.depth } : {}),
        ...(g.layer ? { layer: g.layer } : {}),
        ...(g.age !== undefined ? { age: g.age } : {}),
      },
      filepath: g.local_path || null,
      lat_var: g.netcdf_vars?.lat_var || null,
      lon_var: g.netcdf_vars?.lon_var || null,
      data_var: g.netcdf_vars?.data_var || null,
      synthetic_type: g.synthetic_type || 'procedural_waves',
      ops: (g.transforms || []).map((tr) => ({
        op: tr.type === 'weighted_composite' ? 'composite' : tr.type,
        factor: tr.step_lat || 2,
        t0_km: (tr.ref_thickness || 30000) / 1000,
        age: tr.age || 100,
        plate_model: tr.plate_model || 'Scotese_PALEOMAP',
        scale: tr.scale ?? 1.0,
        offset: tr.offset ?? 0.0,
        width_deg: tr.width_deg ?? 2.0,
        fill_mode: tr.fill_mode ?? 'constant',
        fill_value: tr.fill_value ?? 0.0,
        math_op: tr.math_op ?? 'multiply',
        operand: tr.operand ?? 1.0,
        min_val: tr.min_val ?? null,
        max_val: tr.max_val ?? null,
      })),
    };
  });

  const mapDisp = (d: any) => ({
    type: d.type || 'GridDisplacer',
    enabled: Boolean(d.enabled ?? true),
    grid_id: d.grid_id || gridsArray[0]?.id || 'etopo_ds',
    scale_mode: d.scale_mode === 'direct' ? 'explicit' : 'auto_exagg',
    scale: Number(d.scale ?? 1.0),
    vert_exagg: Number(d.vertical_exagg ?? d.vert_exagg ?? 40.0),
    data_unit: d.grid_units || 'm',
    reference_level: Number(d.reference_level ?? 0.0),
    coastline_step: Number(d.coastline_step ?? 0.0),
    step_threshold: Number(d.step_threshold ?? 0.0),
    value: Number(d.displacement ?? 0.8),
    height: Number(d.displacement ?? 0.8),
    displacement: Number(d.displacement ?? 0.8),
    displace_inside: d.displace_inside !== false,
    shapefile: d.shapefile || null,
    radius_deg: Number(d.radius_degrees ?? 3.0),
    width_deg: Number(d.width_degrees ?? 1.0),
  });

  const colorModeToBackend: Record<string, string> = {
    paleo_atlas: 'paleoatlas',
    filament_banded: 'banded_4filament',
    scientific_cmap: 'colormap',
  };

  return {
    schema_version: '1.0',
    metadata: {
      name: project.name || 'Globe Project',
      description: project.description || '',
      category: project.category || 'custom',
      collection: project.category || 'Standard Examples',
      author: 'Globe3D Studio',
      tags: [],
    },
    mode: project.mode || 'custom',
    paleo_config: {
      enabled: Boolean(p.enabled || project.mode === 'paleo'),
      age: Number(p.age ?? 250.0),
      resolution: p.resolution || '1d',
      plate_model: p.plate_model || 'Scotese_PALEOMAP',
      vert_exagg: Number(p.vert_exagg ?? 40.0),
      coastline_step: Number(p.coastline_step ?? 800.0),
      color_mode: colorModeToBackend[p.color_mode] || 'paleoatlas',
      cmap: p.colormap || 'terrain',
      filament_spools: (f.spools || []).map((s) => ({
        name: s.name,
        hex_color: s.hex,
        td: Number(s.td ?? 3.0),
        brand: 'Generic',
        material: 'PLA',
      })),
      band_thresholds: (f.bands || []).map((b) => ({
        threshold: Number(b.threshold),
        code: b.code,
        color: b.hex,
        label: b.label || '',
      })),
      tracked_locations: (p.tracked_locations || []).map((loc) => ({
        name: loc.name,
        lat: Number(loc.lat),
        lon: Number(loc.lon),
        color: typeof loc.color === 'string' ? loc.color : '#FF2020',
      })),
      mark_poles: Boolean(p.mark_poles ?? true),
    },
    geometry: {
      distribution: project.geometry.method || 'fibonacci',
      n_points: Number(project.geometry.n_points || 500000),
      preview_n_points: Number(project.geometry.preview_n_points || 60000),
      radius: Number(project.geometry.radius || 40.0),
      center: project.geometry.center || [0, 0, 0],
      hollow: Boolean(project.geometry.hollow ?? true),
      inner_ratio: Number(project.geometry.inner_ratio || 0.5),
      inner_n_points: project.geometry.inner_n_points || null,
      create_inner_mesh_from_outer_thickness: project.geometry.inner_thickness || null,
      fix_intersection: project.geometry.fix_intersection || {
        enabled: true,
        min_thickness: 1.8,
        mode: 'inner',
      },
    },
    grids: gridsArray,
    outer_displacements: (project.outer_displacements || []).map(mapDisp),
    inner_displacements: (project.inner_displacements || []).map(mapDisp),
    colourers: (project.colourers || []).map((c) => ({
      type: c.type || 'GridColourer',
      enabled: Boolean(c.enabled ?? true),
      target: c.target || 'outer',
      selection: c.selection || 'all',
      blend_mode: c.blend_mode || 'replace',
      opacity: 1.0,
      grid_id: c.grid_id || gridsArray[0]?.id || 'etopo_ds',
      cmap: c.colormap || 'terrain',
      vmin: c.vmin ?? -6000,
      vmax: c.vmax ?? 5000,
      use_banded_levels: c.colormap_mode === 'banded' || c.colormap_mode === 'listed',
      levels: c.thresholds || [],
      colors: c.listed_colors || [],
      points: c.points || [],
      image_source: c.image_source === 'paleo_atlas' ? 'paleo_raster' : 'local',
      image_path: c.image_path || null,
      preprocessors: (c.preprocessors || [])
        .filter((pp) => pp.enabled)
        .map((pp) => ({
          op: pp.type,
          detail_Suppression: pp.strength ?? 0.6,
          kernel_size: pp.kernel_size ?? 5,
          d: pp.d ?? 9,
          sigma_color: pp.sigma_color ?? 75,
          sigma_space: pp.sigma_space ?? 75,
          n_colors: pp.n_colors ?? 8,
        })),
      color: c.color ?? '#3B82F6',
      background_color: c.background_color || null,
      flood_inside: c.flood_inside !== false,
      shapefile: c.shapefile || null,
      radius_deg: Number(c.radius_degrees ?? 3.0),
      width_deg: Number(c.width_degrees ?? 1.5),
      symbol: c.symbol || 'star',
      lat: Number(c.lat ?? 0),
      lon: Number(c.lon ?? 0),
      size_deg: Number(c.height_degrees ?? c.radius_degrees ?? 6.0),
      text: c.text || 'EARTH',
      north_text: c.north_symbol || 'N',
      south_text: c.south_symbol || 'S',
    })),
    filaments: {
      enabled: Boolean(f.enabled),
      preset: f.preset === 'CUSTOM' ? 'custom' : f.preset || 'TERRAIN_4',
      spools: (f.spools || []).map((s) => ({
        name: s.name,
        hex_color: s.hex,
        td: Number(s.td ?? 3.0),
        brand: 'Generic',
        material: 'PLA',
      })),
      base_layers: 2,
      top_layers: Number(f.total_layers || 4),
      layer_height: Number(f.layer_height || 0.08),
      quantize_preview: false,
    },
    magnets: {
      enabled: Boolean(project.magnets.enabled),
      count: Number(project.magnets.n_magnets || 3),
      Optimize_positions: !Array.isArray(project.magnets.position),
      diameter: Number(project.magnets.diameter || 5.0),
      height: Number(project.magnets.height || 2.0),
      clearance: Number(project.magnets.horizontal_tolerance || 0.15),
      min_margin: Number(project.magnets.min_thickness || 1.2),
      boss_thickness: project.magnets.allow_bosses ? 1.5 : 0.0,
      manual_angles: Array.isArray(project.magnets.position)
        ? project.magnets.position
        : null,
      magnet_type: 'cylindrical',
    },
    export: {
      split_hemispheres: project.export.mode !== 'whole',
      format: project.export.format || '3mf',
      dual_files: !project.export.single_file_3mf,
      filament_mode: 'full_spectrum',
      output_dir: project.export.output_dir || 'outputs',
      filename_prefix: (project.export.filename || project.id || 'globe_model').replace(
        /\.(3mf|obj|stl)$/i,
        ''
      ),
    },
  };
}
