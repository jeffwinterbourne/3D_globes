"""Pydantic data models for GlobeProject JSON configurations and REST API requests."""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StudioBaseModel(BaseModel):
    """Base model that tolerates extra fields and falls back to defaults when None is passed."""

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _strip_none_for_defaulted_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        cleaned = {}
        for k, v in data.items():
            if v is None and k in cls.model_fields:
                field_info = cls.model_fields[k]
                if field_info.default is not None or field_info.default_factory is not None:
                    continue
            cleaned[k] = v
        return cleaned


class ProjectMetadata(StudioBaseModel):
    """Descriptive metadata for a GlobeProject preset or user project."""

    name: str = "Untitled Globe Project"
    description: str = ""
    category: str = "custom"
    collection: Optional[str] = None
    author: str = "Globe3D Studio"
    tags: List[str] = Field(default_factory=list)


class FilamentSpoolModel(StudioBaseModel):
    """Represents a single 3D printer filament spool with optical transmission distance."""

    name: str = "White"
    hex_color: str = "#FFFFFF"
    td: float = 4.0
    brand: str = "Generic"
    material: str = "PLA"


class BandThresholdModel(StudioBaseModel):
    """Single elevation/value band threshold mapped to a filament stack or RGB color."""

    threshold: float = 0.0
    code: str = "[01]"
    color: Optional[str] = None
    label: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_numeric_threshold(cls, data: Any) -> Any:
        if isinstance(data, (int, float)):
            return {"threshold": float(data), "code": "[01]"}
        return data


class TrackedLocationModel(StudioBaseModel):
    """Modern geographic coordinate to reconstruct backward in geological time."""

    name: str = "Location"
    lat: float = 0.0
    lon: float = 0.0
    color: str = "#FF2020"


class PaleoConfigModel(StudioBaseModel):
    """Configuration for Simple Paleo Mode (0-540 Ma deep-time reconstructions)."""

    enabled: bool = False
    age: float = 250.0
    name: Optional[str] = None
    resolution: str = "1d"
    plate_model: str = "Scotese_PALEOMAP"
    rotation_file: Optional[str] = None
    polygons_file: Optional[str] = None
    topology_file: Optional[str] = None
    data_dir: Optional[str] = None
    vert_exagg: float = 30.0
    coastline_step: float = 800.0
    color_mode: str = "paleoatlas"
    cmap: str = "terrain"
    filament_spools: List[FilamentSpoolModel] = Field(
        default_factory=lambda: [
            FilamentSpoolModel(name="White", hex_color="#FFFFFF", td=5.0),
            FilamentSpoolModel(name="Blue", hex_color="#003299", td=3.0),
            FilamentSpoolModel(name="Yellow", hex_color="#FFE600", td=4.5),
            FilamentSpoolModel(name="Red", hex_color="#CC1010", td=3.0),
        ]
    )
    band_thresholds: List[BandThresholdModel] = Field(
        default_factory=lambda: [
            BandThresholdModel(threshold=-4000.0, code="[14]", label="Deep Ocean"),
            BandThresholdModel(threshold=-200.0, code="[12]", label="Mid Ocean"),
            BandThresholdModel(threshold=0.0, code="[11]", label="Continental Shelf"),
            BandThresholdModel(threshold=250.0, code="[27]", label="Lowlands"),
            BandThresholdModel(threshold=1000.0, code="[21]", label="Highlands"),
            BandThresholdModel(threshold=2500.0, code="[31]", label="Mountains"),
            BandThresholdModel(threshold=9000.0, code="[01]", label="Ice / High Peaks"),
        ]
    )
    tracked_locations: List[TrackedLocationModel] = Field(default_factory=list)
    mark_poles: bool = True
    pole_style: str = "ring"
    pole_label_size_deg: float = 6.0
    location_marker_size_deg: float = 4.0


class FixIntersectionConfig(StudioBaseModel):
    """Settings for automatic inner/outer shell intersection resolution."""

    enabled: bool = True
    min_thickness: float = 2.0
    mode: str = "inner"


class GeometryConfig(StudioBaseModel):
    """Base spherical mesh geometry settings."""

    distribution: str = "fibonacci"
    n_points: int = 500000
    preview_n_points: int = 60000
    radius: float = 50.0
    center: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    hollow: bool = True
    inner_ratio: float = 0.88
    inner_n_points: Optional[int] = None
    create_inner_mesh_from_outer_thickness: Optional[float] = None
    fix_intersection: FixIntersectionConfig = Field(default_factory=FixIntersectionConfig)


class GridOpModel(StudioBaseModel):
    """Single declarative grid operation in a GridSource pipeline."""

    op: str = "downsample"
    factor: int = 2
    t0_km: float = 30.0
    ocean_scale: float = 5.5
    land_scale: float = 6.5
    inputs: List[Dict[str, Any]] = Field(default_factory=list)
    normalize: bool = True
    clamp_min: Optional[float] = None
    clamp_max: Optional[float] = None
    age: float = 100.0
    plate_model: str = "Scotese_PALEOMAP"
    scale: float = 1.0
    offset: float = 0.0

    # Spherical Gaussian smoothing
    width_deg: float = 2.0

    # Fill NaNs
    fill_mode: str = "constant"  # "constant", "mean", "min", "max", "nearest"
    fill_value: float = 0.0

    # Chainable Math
    math_op: str = "multiply"  # "add", "subtract", "multiply", "divide", "power", "log", "log10", "exp", "abs", "negate", "sqrt", "clamp"
    operand: float = 1.0
    min_val: Optional[float] = None
    max_val: Optional[float] = None


class GridSourceModel(StudioBaseModel):
    """Declarative specification for loading or computing a GeographicGrid."""

    id: str = "grid_0"
    source: str = "online"
    dataset: Optional[str] = "topography.earth"
    params: Dict[str, Any] = Field(default_factory=dict)
    filepath: Optional[str] = None
    lat_var: Optional[str] = None
    lon_var: Optional[str] = None
    data_var: Optional[str] = None
    synthetic_type: Optional[str] = "procedural_waves"
    ops: List[GridOpModel] = Field(default_factory=list)


class DisplacerConfigModel(StudioBaseModel):
    """Declarative specification for a single radial mesh displacement layer."""

    type: str = "GridDisplacer"
    enabled: bool = True
    grid_id: Optional[str] = None
    scale_mode: str = "auto_exagg"
    scale: float = 1.0
    vert_exagg: float = 30.0
    data_unit: str = "m"
    max_displacement_mm: float = 5.0
    reference_level: float = 0.0
    coastline_step: float = 0.0
    step_threshold: float = 0.0
    value: float = 0.0
    points: List[Any] = Field(default_factory=list)
    lines: List[Any] = Field(default_factory=list)
    polygons: List[Any] = Field(default_factory=list)
    shapefile: Optional[str] = None
    radius_deg: float = 5.0
    width_deg: float = 2.0
    profile: str = "gaussian"
    height: float = 2.0
    displacement: Optional[float] = None
    displace_inside: bool = True
    mode: str = "add"


class ImagePreprocessorModel(StudioBaseModel):
    """Declarative specification for an image pre-processing step before ImageColourer."""

    op: str = "undo_hillshading"
    detail_Suppression: float = 0.6
    kernel_size: int = 5
    d: int = 9
    sigma_color: float = 75.0
    sigma_space: float = 75.0
    n_colors: int = 8
    svg_path: Optional[str] = None
    lat: float = 0.0
    lon: float = 0.0
    size_deg: float = 8.0
    color: Optional[Any] = None
    rotation_deg: float = 0.0
    pole_style: str = "ring"
    pole_size_deg: float = 6.0


class ColourerConfigModel(StudioBaseModel):
    """Declarative specification for a single mesh vertex colouring layer."""

    type: str = "GridColourer"
    enabled: bool = True
    target: str = "outer"
    selection: str = "all"
    blend_mode: str = "replace"
    opacity: float = 1.0
    grid_id: Optional[str] = None
    cmap: str = "terrain"
    vmin: Optional[float] = None
    vmax: Optional[float] = None
    symmetric: bool = False
    use_banded_levels: bool = False
    levels: List[float] = Field(default_factory=list)
    colors: List[Any] = Field(default_factory=list)
    image_source: str = "local"
    image_path: Optional[str] = None
    preprocessors: List[ImagePreprocessorModel] = Field(default_factory=list)
    color: Any = "#3B82F6"
    points: List[Any] = Field(default_factory=list)
    lines: List[Any] = Field(default_factory=list)
    polygons: List[Any] = Field(default_factory=list)
    shapefile: Optional[str] = None
    flood_inside: bool = True
    background_color: Optional[str] = None
    radius_deg: float = 3.0
    width_deg: float = 1.5
    feather_deg: float = 0.5
    symbol: str = "star"
    lat: float = 0.0
    lon: float = 0.0
    size_deg: float = 6.0
    rotation_deg: float = 0.0
    text: str = "EARTH"
    font_path: Optional[str] = None
    mark_north: bool = True
    mark_south: bool = True
    north_text: str = "N"
    south_text: str = "S"


class FilamentsConfigModel(StudioBaseModel):
    """Full-Spectrum Optical Filament Mixing settings for multi-color 3MF printing."""

    enabled: bool = True
    preset: str = "TERRAIN_4"
    spools: List[FilamentSpoolModel] = Field(
        default_factory=lambda: [
            FilamentSpoolModel(name="White", hex_color="#FFFFFF", td=5.0),
            FilamentSpoolModel(name="Blue", hex_color="#003299", td=3.0),
            FilamentSpoolModel(name="Yellow", hex_color="#FFE600", td=4.5),
            FilamentSpoolModel(name="Red", hex_color="#CC1010", td=3.0),
        ]
    )
    base_layers: int = 2
    top_layers: int = 4
    layer_height: float = 0.08
    quantize_preview: bool = False


class MagnetsConfigModel(StudioBaseModel):
    """Equatorial magnet recess and automatic position optimization settings."""

    enabled: bool = True
    count: int = 8
    Optimize_positions: bool = True
    diameter: float = 3.2
    height: float = 1.6
    clearance: float = 0.1
    min_margin: float = 0.8
    boss_thickness: float = 1.2
    manual_angles: Optional[List[float]] = None
    magnet_type: str = "cylindrical"
    width: float = 5.0
    length: float = 5.0
    embed_depth: float = 0.0


class ExportConfigModel(StudioBaseModel):
    """Mesh splitting and file export settings."""

    split_hemispheres: bool = True
    format: str = "3mf"
    dual_files: bool = False
    filament_mode: str = "full_spectrum"
    output_dir: str = "outputs"
    filename_prefix: str = "globe_model"


class GlobeProject(StudioBaseModel):
    """Root schema for a complete Globe3D Studio project or preset."""

    schema_version: str = "1.0"
    metadata: ProjectMetadata = Field(default_factory=ProjectMetadata)
    mode: str = "custom"
    paleo_config: PaleoConfigModel = Field(default_factory=PaleoConfigModel)
    geometry: GeometryConfig = Field(default_factory=GeometryConfig)
    grids: List[GridSourceModel] = Field(default_factory=list)
    outer_displacements: List[DisplacerConfigModel] = Field(default_factory=list)
    inner_displacements: List[DisplacerConfigModel] = Field(default_factory=list)
    colourers: List[ColourerConfigModel] = Field(default_factory=list)
    filaments: FilamentsConfigModel = Field(default_factory=FilamentsConfigModel)
    magnets: MagnetsConfigModel = Field(default_factory=MagnetsConfigModel)
    export: ExportConfigModel = Field(default_factory=ExportConfigModel)


class ReconstructPointsRequest(BaseModel):
    """Request payload for reconstructing modern locations to a geological age."""

    age: float = 250.0
    plate_model: str = "Scotese_PALEOMAP"
    locations: List[TrackedLocationModel] = Field(default_factory=list)


class MagnetTestPieceRequest(BaseModel):
    """Request payload for generating a magnet calibration test piece STL."""

    diameter: float = 3.2
    height: float = 1.6
    clearance: float = 0.1
    output_dir: str = "outputs"


class FilamentMatchRequest(BaseModel):
    """Request payload for matching a target hex color against the optical filament palette."""

    target_hex: str = "#2B83BA"
    filaments: FilamentsConfigModel = Field(default_factory=FilamentsConfigModel)


class DatasetDownloadRequest(BaseModel):
    """Request payload for triggering an online dataset download."""

    category: str
    dataset: str
    params: Dict[str, Any] = Field(default_factory=dict)


class InspectNetCDFRequest(BaseModel):
    """Request payload for inspecting variables inside a NetCDF file."""

    filepath: str


class RevealFileRequest(BaseModel):
    """Request payload for revealing a file in Windows File Explorer."""

    path: str
