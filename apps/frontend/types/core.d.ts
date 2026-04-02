/**
 * UDAKE 核心类型定义
 * 公共数据结构和接口
 */

// ========== 坐标和地理 ==========

/** 经纬度坐标 */
export interface Coordinate {
    longitude: number;
    latitude: number;
}

/** 采样点数据 */
export interface SamplingPoint {
    x: number;
    y: number;
    value: number;
    timestamp?: string;
}

/** 地理边界 */
export interface Bounds {
    minLng: number;
    minLat: number;
    maxLng: number;
    maxLat: number;
}

/** GeoJSON 几何类型 */
export type GeometryType = 'Point' | 'MultiPoint' | 'LineString' | 'MultiLineString' | 'Polygon' | 'MultiPolygon';

/** GeoJSON Geometry */
export interface GeoJSONGeometry {
    type: GeometryType;
    coordinates: any[];
}

/** GeoJSON Feature */
export interface GeoJSONFeature {
    type: 'Feature';
    geometry: GeoJSONGeometry;
    properties: Record<string, any>;
}

/** GeoJSON FeatureCollection */
export interface GeoJSONFeatureCollection {
    type: 'FeatureCollection';
    features: GeoJSONFeature[];
}

// ========== 项目 ==========

/** 采样模式 */
export type SamplingMode = 'free' | 'region';

/** 坐标获取方式 */
export type CoordinateMode = 'manual' | 'device';

/** 项目配置 */
export interface ProjectConfig {
    sampling_mode: SamplingMode;
    coordinate_mode: CoordinateMode;
    boundary_polygon?: GeoJSONFeature | null;
    points?: SamplingPoint[];
}

/** 项目数据 */
export interface ProjectData {
    sampling_mode: SamplingMode;
    coordinate_mode: CoordinateMode;
    boundary_polygon: GeoJSONFeature | null;
    points: SamplingPoint[];
    crs: string;
    created_at: string;
    updated_at: string;
}

// ========== 插值参数 ==========

/** 克里金方法 */
export type KrigingMethod = 'ordinary' | 'universal' | 'block';

/** 变异函数模型 */
export type VariogramModel = 'spherical' | 'exponential' | 'gaussian';

/** 插值参数 */
export interface KrigingParams {
    points: SamplingPoint[];
    method: KrigingMethod;
    variogram_model: VariogramModel;
    grid_resolution: number;
    nlags?: number;
    nugget?: number;
    sill?: number;
    range?: number;
    enable_cross_validation: boolean;
}

// ========== 任务状态 ==========

/** 任务状态值 */
export type TaskStatusValue = 'pending' | 'running' | 'completed' | 'failed';

/** 任务状态 */
export interface TaskStatus {
    status: TaskStatusValue;
    progress: number;
    error?: string;
    task_id?: string;
    _polling?: PollingMeta;
}

/** 轮询元数据 */
export interface PollingMeta {
    count: number;
    interval: number;
    stalled: boolean;
    elapsed: number;
}

/** 带轮询元数据的任务状态 */
export interface EnrichedTaskStatus extends TaskStatus {
    _polling?: PollingMeta;
}

// ========== API 响应 ==========

/** 上传响应 */
export interface UploadResponse {
    data_id: string;
    point_count: number;
    fields: string[];
}

/** 启动插值响应 */
export interface StartKrigingResponse {
    task_id: string;
    status: string;
}

/** 预测/方差结果 */
export interface ResultResponse {
    geotiff_url: string;
    geojson?: GeoJSONFeatureCollection;
    statistics?: Record<string, number>;
}

// ========== 错误处理 ==========

/** 错误类型 */
export type ErrorType =
    | 'geojson_format'
    | 'coordinate_format'
    | 'point_out_of_bounds'
    | 'geolocation_failed'
    | 'permission_denied'
    | 'invalid_polygon'
    | 'network_error'
    | 'validation_error'
    | 'server_error'
    | 'timeout_error'
    | 'file_too_large'
    | 'unsupported_format'
    | 'interpolation_failed'
    | 'insufficient_points'
    | 'export_failed';

/** 错误等级 */
export type ErrorLevel = 'FATAL' | 'SEVERE' | 'WARNING' | 'INFO';

/** 错误详情 */
export interface ErrorDetail {
    code?: string;
    level?: ErrorLevel;
    message: string;
    suggestion?: string;
    example?: string;
    icon?: string;
    solutions?: string[];
    helpLink?: string;
    retryable?: boolean;
}

/** 错误日志条目 */
export interface ErrorLogEntry {
    type: ErrorType;
    code?: string;
    level?: ErrorLevel;
    message: string;
    timestamp: string;
    url: string;
    stack?: string;
    count?: number;
    firstSeenAt?: string;
    lastSeenAt?: string;
    suggestion?: string;
}

/** 验证结果 */
export interface ValidationResult {
    valid: boolean;
    error?: string;
    errors?: string[];
}

// ========== 地图引擎 ==========

/** 地图引擎类型 */
export type MapEngineType = 'arcgis';

/** 地图初始化选项 */
export interface MapInitOptions {
    center?: [number, number];
    zoom?: number;
    minZoom?: number;
    maxZoom?: number;
}

/** 标记选项 */
export interface MarkerOptions {
    title?: string;
    data?: Record<string, any>;
}

/** 多边形样式选项 */
export interface PolygonStyleOptions {
    fillColor?: number[] | string;
    strokeColor?: number[] | string;
    strokeWidth?: number;
    strokeOpacity?: number;
    fillOpacity?: number;
}

// ========== 状态管理 ==========

/** 全局应用状态 */
export interface AppState {
    project: ProjectData | null;
    taskId: string | null;
    taskStatus: TaskStatus | null;
    dataId: string | null;
    mapEngine: MapEngineType;
    darkMode: boolean;
    sidebarOpen: boolean;
    layout: LayoutConfig;
    units: UnitConfig;
    defaultParams: DefaultParamsConfig;
}

// ========== 布局配置 ==========

/** 面板位置 */
export type PanelPosition = 'left' | 'right' | 'top' | 'bottom' | 'floating';

/** 面板信息 */
export interface PanelInfo {
    id: string;
    visible: boolean;
    position: PanelPosition;
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    collapsed?: boolean;
}

/** 布局配置 */
export interface LayoutConfig {
    panels: Record<string, PanelInfo>;
    activeLayout: string;
    savedLayouts: Record<string, Record<string, PanelInfo>>;
}

// ========== 单位配置 ==========

/** 坐标系统 */
export type CoordinateSystem = 'wgs84' | 'gcj02' | 'bd09';

/** 长度单位 */
export type LengthUnit = 'm' | 'km' | 'ft' | 'mi';

/** 面积单位 */
export type AreaUnit = 'm2' | 'km2' | 'ha' | 'ac';

/** 单位配置 */
export interface UnitConfig {
    coordinateSystem: CoordinateSystem;
    lengthUnit: LengthUnit;
    areaUnit: AreaUnit;
}

// ========== 默认参数配置 ==========

/** 参数预设类型 */
export type ParamPresetType = 'environment' | 'agriculture' | 'geology' | 'custom';

/** 参数配置 */
export interface ParamConfig {
    id: string;
    name: string;
    description: string;
    presetType: ParamPresetType;
    krigingParams: KrigingParams;
    createdAt: string;
    updatedAt: string;
}

/** 默认参数配置 */
export interface DefaultParamsConfig {
    activeConfig: string | null;
    configs: Record<string, ParamConfig>;
    presets: Record<ParamPresetType, ParamConfig>;
}

/** 状态变化监听器 */
export type StateListener<T = any> = (newValue: T, oldValue: T, key: string) => void;

// ========== 表单验证 ==========

/** 表单验证规则 */
export interface FormValidationRules {
    required?: string;
    pattern?: RegExp;
    patternMsg?: string;
    custom?: (value: string) => { valid: boolean; message?: string; level?: 'success' | 'warning' | 'error' };
}

/** 表单字段状态 */
export type FieldState = 'idle' | 'success' | 'warning' | 'error';

/** 轮询优先级 */
export type PollingPriority = 'high' | 'normal' | 'low';
