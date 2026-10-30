export type BuilderMode = 'paleo' | 'custom';

export type ActiveTab =
  | 'paleo'
  | 'geometry'
  | 'grids'
  | 'displacers'
  | 'colourers'
  | 'filaments'
  | 'magnets'
  | 'datasets'
  | 'export';

export type ViewMode = 'whole' | 'exploded' | 'upper' | 'lower' | 'outer' | 'inner';

export interface FixIntersectionConfig {
  enabled: boolean;
  min_thickness: number;
  mode: 'inner' | 'outer' | 'both';
}

export interface GeometryConfig {
  method: 'fibonacci' | 'icosahedron';
  n_points: number;
  preview_n_points?: number;
  subdivisions?: number;
  radius: number;
  center: [number, number, number];
  hollow: boolean;
  inner_ratio: number;
  inner_n_points?: number | null;
  inner_thickness?: number | null;
  fix_intersection?: FixIntersectionConfig | null;
}

export interface GridTransform {
  type:
    | 'downsample'
    | 'airy_moho'
    | 'weighted_composite'
    | 'reconstruct'
    | 'scale_offset'
    | 'smooth'
    | 'fill'
    | 'math';
  step_lat?: number;
  step_lon?: number;
  // Airy Isostasy Moho parameters
  ref_thickness?: number;
  rho_c?: number;
  rho_m?: number;
  // Weighted Composite parameters
  grid_b_id?: string;
  weight_a?: number;
  weight_b?: number;
  offset?: number;
  // Reconstruct parameters
  age?: number;
  plate_model?: string;
  // Scale & Offset
  scale?: number;
  // Gaussian smoothing (safe on sphere)
  width_deg?: number;
  // Fill NaNs
  fill_mode?: 'constant' | 'mean' | 'min' | 'max' | 'nearest';
  fill_value?: number;
  // Chainable Math
  math_op?:
    | 'add'
    | 'subtract'
    | 'multiply'
    | 'divide'
    | 'power'
    | 'log'
    | 'log10'
    | 'exp'
    | 'abs'
    | 'negate'
    | 'sqrt'
    | 'clamp';
  operand?: number;
  min_val?: number;
  max_val?: number;
}

export interface GridSourceConfig {
  id?: string;
  source_type: 'online' | 'local' | 'local_or_dataset' | 'synthetic' | 'paleo';
  category?: string;
  name?: string;
  dataset?: string;
  resolution?: string;
  depth?: number;
  layer?: string;
  age?: number;
  map_name?: string;
  local_path?: string;
  fallback_dataset?: {
    category: string;
    name: string;
    resolution?: string;
    depth?: number;
    layer?: string;
    age?: number;
  };
  netcdf_vars?: {
    lat_var?: string;
    lon_var?: string;
    data_var?: string;
  };
  downsample_factor?: number;
  synthetic_type?: 'harmonic_wave' | 'radial_bump' | 'checkerboard';
  synthetic_params?: Record<string, number>;
  transforms?: GridTransform[];
}

export interface DisplacerConfig {
  id: string;
  enabled: boolean;
  type: 'GridDisplacer' | 'ConstantDisplacer' | 'PointDisplacer' | 'LineDisplacer' | 'PolygonDisplacer';
  grid_id?: string;
  scale_mode?: 'physical' | 'direct';
  vertical_exagg?: number;
  vert_exagg?: number;
  grid_units?: 'm' | 'km' | 'cm' | 'mm' | 'ft';
  scale?: number;
  reference_level?: number;
  coastline_step?: number;
  step_threshold?: number;
  interp_method?: 'linear' | 'nearest';
  displacement?: number;
  shapefile?: string;
  local_path?: string;
  points?: Array<[number, number] | { lon: number; lat: number; name?: string }>;
  radius_degrees?: number;
  width_degrees?: number;
  displace_inside?: boolean;
}

export interface ImagePreprocessorStep {
  type: 'undo_hillshading' | 'simplify_image_median' | 'simplify_image_bilateral' | 'simplify_colors';
  enabled: boolean;
  strength?: number;
  kernel_size?: number;
  d?: number;
  sigma_color?: number;
  sigma_space?: number;
  n_colors?: number;
  target_colors?: string[];
  hsv_weights?: [number, number, number];
}

export interface LocationMarker {
  name: string;
  lat: number;
  lon: number;
  symbol?: string;
  color?: string | [number, number, number];
  size?: number;
  radius_degrees?: number;
  rotation_degrees?: number;
  text?: string;
  height_degrees?: number;
}

export interface ColourerConfig {
  id: string;
  enabled: boolean;
  target: 'outer' | 'inner' | 'all';
  selection: 'all' | 'outward_facing' | 'inward_facing';
  blend_mode?: 'replace' | 'multiply' | 'add' | 'overlay';
  type:
    | 'GridColourer'
    | 'ImageColourer'
    | 'ConstantColourer'
    | 'PointColourer'
    | 'LineColourer'
    | 'PolygonColourer'
    | 'SymbolColourer'
    | 'PoleLabelColourer'
    | 'TextColourer';
  // GridColourer
  grid_id?: string;
  colormap_mode?: 'continuous' | 'discrete' | 'banded' | 'listed';
  colormap?: string;
  vmin?: number;
  vmax?: number;
  n_bins?: number;
  listed_colors?: Array<string | [number, number, number]>;
  thresholds?: number[];
  // ImageColourer
  image_source?: 'local' | 'paleo_atlas' | 'procedural_gradient';
  image_path?: string;
  paleo_age?: number;
  preprocessors?: ImagePreprocessorStep[];
  // Constant / Vector Colourers
  color?: [number, number, number] | string;
  background_color?: [number, number, number] | string | null;
  shapefile?: string;
  local_path?: string;
  points?: Array<[number, number]>;
  radius_degrees?: number;
  width_degrees?: number;
  flood_inside?: boolean;
  marker_shape?: 'circle' | 'square' | 'triangle' | 'cross' | 'star';
  marker_thickness?: number;
  // Symbol / Pole / Text Colourers
  symbol?: string;
  locations?: LocationMarker[];
  reference?: 'modern' | 'paleo';
  age?: number;
  plate_model?: string;
  north_color?: [number, number, number] | string;
  south_color?: [number, number, number] | string;
  north_symbol?: string;
  south_symbol?: string;
  rotation_degrees?: number;
  text?: string;
  lat?: number;
  lon?: number;
  height_degrees?: number;
  angle?: number;
  fill?: boolean;
  fill_color?: [number, number, number] | string;
  stroke?: boolean;
  stroke_width?: number;
  stroke_color?: [number, number, number] | string;
  font?: string;
  font_weight?: 'normal' | 'bold';
  font_style?: 'normal' | 'italic';
}

export interface FilamentSpool {
  name: string;
  hex: string;
  td: number;
}

export interface FilamentBand {
  threshold: number;
  code: string;
  hex: string;
  label?: string;
}

export interface FilamentsConfig {
  enabled: boolean;
  preset: 'TERRAIN_4' | 'CMYKW' | 'RBYKW' | 'EARTH_TERRAIN' | 'CUSTOM';
  spools: FilamentSpool[];
  total_layers: number;
  layer_height: number;
  bands: FilamentBand[];
  vmin: number;
  vmax: number;
}

export interface MagnetSettingsConfig {
  enabled: boolean;
  diameter: number;
  height: number;
  n_magnets: number;
  position: number | number[];
  horizontal_tolerance: number;
  vertical_tolerance: number;
  vertical_offset: number;
  min_thickness: number;
  allow_bosses: boolean;
  min_magnets: number;
  min_angular_spacing: number;
  step_degrees: number;
  placement_strategy: 'cluster_peaks' | 'uniform' | 'margin_weighted';
  angle_tolerance: number;
}

export interface PaleoConfig {
  enabled: boolean;
  age: number;
  map_name?: string;
  resolution: '6m' | '1d';
  plate_model: string;
  custom_rot_path?: string;
  custom_gpml_path?: string;
  vert_exagg: number;
  coastline_step: number;
  color_mode: 'paleo_atlas' | 'filament_banded' | 'scientific_cmap';
  colormap?: string;
  undo_shading: boolean;
  palette_colors?: number | null;
  mark_poles: boolean;
  tracked_locations: LocationMarker[];
}

export interface ExportConfig {
  mode: 'hemispheres' | 'whole';
  part?: 'outer' | 'inner' | 'combined';
  format: '3mf' | 'obj' | 'stl';
  single_file_3mf?: boolean;
  filename?: string;
  top_filename?: string;
  bottom_filename?: string;
  output_dir?: string;
  hollow: boolean;
  thickness?: number | null;
  engine: 'manifold' | 'blender';
  plane_normal: [number, number, number];
  plane_origin: [number, number, number];
  flip_bottom: boolean;
  offset_distance: number;
  include_color: boolean;
  fix_normals: boolean;
  printer_profile?: string;
  color_tolerance?: number;
}

export interface GlobeProject {
  $schema?: string;
  id: string;
  name: string;
  category: string;
  description: string;
  mode: BuilderMode;
  paleo?: PaleoConfig;
  geometry: GeometryConfig;
  grids: Record<string, GridSourceConfig>;
  outer_displacements: DisplacerConfig[];
  inner_displacements: DisplacerConfig[];
  colourers: ColourerConfig[];
  filaments?: FilamentsConfig;
  magnets: MagnetSettingsConfig;
  export: ExportConfig;
}

export const DEFAULT_FILAMENT_SPOOLS: Record<string, FilamentSpool[]> = {
  TERRAIN_4: [
    { name: 'Brown', hex: '#7c4d2b', td: 2.2 },
    { name: 'Dark Blue', hex: '#1b4f9c', td: 2.0 },
    { name: 'White', hex: '#f8fafc', td: 4.5 },
    { name: 'Dark Green', hex: '#2d6a4f', td: 2.4 },
  ],
  CMYKW: [
    { name: 'Cyan', hex: '#00aeef', td: 3.2 },
    { name: 'Magenta', hex: '#ec008c', td: 3.0 },
    { name: 'Yellow', hex: '#fff200', td: 4.0 },
    { name: 'White', hex: '#ffffff', td: 4.8 },
  ],
  RBYKW: [
    { name: 'Red', hex: '#e11d48', td: 2.8 },
    { name: 'Blue', hex: '#2563eb', td: 2.5 },
    { name: 'Yellow', hex: '#facc15', td: 4.0 },
    { name: 'White', hex: '#ffffff', td: 4.5 },
  ],
  EARTH_TERRAIN: [
    { name: 'Navy Ocean', hex: '#0f3460', td: 1.8 },
    { name: 'Forest Green', hex: '#2b7a0b', td: 2.5 },
    { name: 'Ochre Sand', hex: '#d4a373', td: 3.5 },
    { name: 'Snow White', hex: '#ffffff', td: 4.5 },
  ],
};

export const DEFAULT_STARTER_PROJECT: GlobeProject = {
  $schema: '../schemas/globe_project.schema.json',
  id: 'example_4_coloured_globe',
  name: 'Example 4: Coloured Globe (Complete Pipeline)',
  category: 'examples',
  description:
    'Hollow globe with 40x ETOPO topography, 0.8mm coastline step, 3 magnets with bosses, and terrain/tomography outer colouring.',
  mode: 'custom',
  paleo: {
    enabled: false,
    age: 250.0,
    resolution: '1d',
    plate_model: 'Scotese_PALEOMAP',
    vert_exagg: 40.0,
    coastline_step: 1000.0,
    color_mode: 'paleo_atlas',
    colormap: 'terrain',
    undo_shading: true,
    palette_colors: null,
    mark_poles: true,
    tracked_locations: [
      { name: 'Oxford', lat: 51.752, lon: -1.2577, symbol: 'star', color: '#ef4444', size: 2.5 },
      { name: 'Baltimore', lat: 39.2904, lon: -76.6122, symbol: 'star', color: '#facc15', size: 2.5 },
    ],
  },
  geometry: {
    method: 'fibonacci',
    n_points: 500000,
    preview_n_points: 60000,
    radius: 40.0,
    center: [0.0, 0.0, 0.0],
    hollow: true,
    inner_ratio: 0.5,
    inner_n_points: null,
    fix_intersection: {
      enabled: true,
      min_thickness: 1.8,
      mode: 'inner',
    },
  },
  grids: {
    etopo_ds: {
      source_type: 'online',
      category: 'topography',
      name: 'earth',
      resolution: '30m',
      fallback_dataset: { category: 'topography', name: 'earth', resolution: '30m' },
      netcdf_vars: { lat_var: 'lat', lon_var: 'lon', data_var: 'z' },
      transforms: [],
    },
  },
  outer_displacements: [
    {
      id: 'disp_topo',
      enabled: true,
      type: 'GridDisplacer',
      grid_id: 'etopo_ds',
      scale_mode: 'physical',
      vertical_exagg: 40.0,
      grid_units: 'm',
      reference_level: 0.0,
      coastline_step: 0.8,
      step_threshold: 0.0,
      interp_method: 'linear',
    },
  ],
  inner_displacements: [],
  colourers: [
    {
      id: 'col_outer_terrain',
      enabled: true,
      target: 'outer',
      selection: 'outward_facing',
      type: 'GridColourer',
      grid_id: 'etopo_ds',
      colormap_mode: 'continuous',
      colormap: 'terrain',
      vmin: -6000.0,
      vmax: 5000.0,
    },
    {
      id: 'col_inner_gray',
      enabled: true,
      target: 'inner',
      selection: 'all',
      type: 'ConstantColourer',
      color: [0.55, 0.58, 0.62],
    },
  ],
  filaments: {
    enabled: false,
    preset: 'TERRAIN_4',
    spools: DEFAULT_FILAMENT_SPOOLS.TERRAIN_4,
    total_layers: 4,
    layer_height: 0.08,
    vmin: -6000,
    vmax: 4500,
    bands: [
      { threshold: -6000, code: '[15]', hex: '#1b4f9c', label: 'Abyssal Ocean' },
      { threshold: -3500, code: '[16]', hex: '#3b6db3', label: 'Deep Ocean' },
      { threshold: -200, code: '[18]', hex: '#7aa2d6', label: 'Continental Shelf' },
      { threshold: 0, code: '[34]', hex: '#2d6a4f', label: 'Lowland Forest' },
      { threshold: 500, code: '[31]', hex: '#52875b', label: 'Upland Plains' },
      { threshold: 1500, code: '[09]', hex: '#8f6b47', label: 'Highlands' },
      { threshold: 2800, code: '[01]', hex: '#7c4d2b', label: 'Mountain Peaks' },
      { threshold: 4000, code: '[20]', hex: '#f8fafc', label: 'Alpine Snow' },
    ],
  },
  magnets: {
    enabled: true,
    diameter: 5.0,
    height: 2.0,
    n_magnets: 3,
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
    filename: 'globe_model.3mf',
    top_filename: 'globe_top.obj',
    bottom_filename: 'globe_bottom.obj',
    output_dir: 'outputs',
    hollow: true,
    engine: 'manifold',
    plane_normal: [0.0, 0.0, 1.0],
    plane_origin: [0.0, 0.0, 0.0],
    flip_bottom: true,
    offset_distance: 85.0,
    include_color: true,
    fix_normals: true,
    printer_profile: 'snapmaker_u1',
    color_tolerance: 8.0,
  },
};

export interface WorkspaceConfig {
  working_dir: string;
  projects_count: number;
  datasets_count: number;
}

export interface ProjectSummary {
  slug: string;
  id: string;
  name: string;
  description: string;
  category: string;
  mode: 'custom' | 'paleo';
  paleo_enabled: boolean;
  paleo_age: number;
  updated_at: number;
  updated_at_iso: string;
  path: string;
  has_thumbnail: boolean;
}

export interface WorkspaceDatasetEntry {
  id: string;
  name: string;
  physical_filename: string;
  physical_path?: string;
  file_type: 'grid' | 'vector' | 'raster';
  file_ext: string;
  size_bytes: number;
  netcdf_vars?: {
    lat?: string;
    lon?: string;
    data?: string;
  } | null;
  default_ops?: GridTransform[];
  parent_dataset_id?: string | null;
  is_virtual?: boolean;
  exists?: boolean;
  created_at?: number;
}

export const BLANK_GLOBE_PROJECT: GlobeProject = {
  $schema: '../../schemas/globe_project.schema.json',
  id: 'blank_globe',
  name: 'New Blank Globe',
  category: 'user',
  description: 'Clean hollow base globe with no datasets or displacements applied.',
  mode: 'custom',
  paleo: {
    enabled: false,
    age: 0,
    resolution: '1d',
    plate_model: 'Scotese_PALEOMAP',
    vert_exagg: 40,
    coastline_step: 1000,
    color_mode: 'scientific_cmap',
    colormap: 'terrain',
    undo_shading: true,
    palette_colors: null,
    mark_poles: true,
    tracked_locations: [],
  },
  geometry: {
    method: 'fibonacci',
    n_points: 500000,
    preview_n_points: 60000,
    radius: 40,
    center: [0, 0, 0],
    hollow: true,
    inner_ratio: 0.5,
    inner_n_points: null,
    fix_intersection: {
      enabled: true,
      min_thickness: 1.8,
      mode: 'inner',
    },
  },
  grids: {},
  outer_displacements: [],
  inner_displacements: [],
  colourers: [],
  filaments: {
    enabled: false,
    preset: 'TERRAIN_4',
    spools: DEFAULT_FILAMENT_SPOOLS.TERRAIN_4,
    total_layers: 4,
    layer_height: 0.08,
    vmin: -6000,
    vmax: 4500,
    bands: DEFAULT_STARTER_PROJECT.filaments?.bands || [],
  },
  magnets: {
    enabled: true,
    diameter: 5.0,
    height: 2.0,
    n_magnets: 3,
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
    filename: 'blank_globe.3mf',
    top_filename: 'blank_top.obj',
    bottom_filename: 'blank_bottom.obj',
    output_dir: 'outputs',
    hollow: true,
    engine: 'manifold',
    plane_normal: [0.0, 0.0, 1.0],
    plane_origin: [0.0, 0.0, 0.0],
    flip_bottom: true,
    offset_distance: 85.0,
    include_color: true,
    fix_normals: true,
    printer_profile: 'snapmaker_u1',
    color_tolerance: 8.0,
  },
};

