/**
 * UDAKE 图层类型定义
 */

import { IMapAdapterExtended, MapView, MapGraphic, MapPoint } from './app';
import { SamplingPoint, GeoJSONFeatureCollection, PolygonStyleOptions } from './core';

// ========== 图层类型 ==========

/** 图层类型枚举 */
export enum LayerType {
    POINTS = 'points',
    PREDICTION = 'prediction',
    VARIANCE = 'variance',
    UNCERTAINTY = 'uncertainty',
    BOUNDARY = 'boundary',
    MARKER = 'marker'
}

/** 图层状态 */
export enum LayerState {
    IDLE = 'idle',
    LOADING = 'loading',
    LOADED = 'loaded',
    ERROR = 'error'
}

/** 图层配置 */
export interface LayerConfig {
    id: string;
    type: LayerType;
    name: string;
    visible: boolean;
    opacity: number;
    zIndex: number;
    interactive: boolean;
}

/** 栅格图层配置 */
export interface RasterLayerConfig extends LayerConfig {
    type: LayerType.PREDICTION | LayerType.VARIANCE;
    url: string;
    extent?: {
        xmin: number;
        ymin: number;
        xmax: number;
        ymax: number;
    };
}

/** 矢量图层配置 */
export interface VectorLayerConfig extends LayerConfig {
    type: LayerType.POINTS | LayerType.BOUNDARY | LayerType.MARKER;
    geojson?: GeoJSONFeatureCollection;
    data?: SamplingPoint[];
    style?: {
        fillColor?: string;
        strokeColor?: string;
        strokeWidth?: number;
        radius?: number;
        iconUrl?: string;
    };
}

/** 图层元数据 */
export interface LayerMetadata {
    id: string;
    createdAt: number;
    updatedAt: number;
    size?: number;
    bounds?: {
        minLng: number;
        minLat: number;
        maxLng: number;
        maxLat: number;
    };
}

// ========== 图层管理 ==========

/** 图层管理器配置 */
export interface LayerManagerConfig {
    maxVisibleMarkers?: number;          // 最大可见标记数
    enableViewportFilter?: boolean;      // 是否启用视口过滤
    enableMarkerPooling?: boolean;       // 是否启用标记池
    clusterThreshold?: number;           // 聚合阈值
    autoRefresh?: boolean;               // 是否自动刷新
}

/** 视口边界 */
export interface ViewportBounds {
    minLng: number;
    minLat: number;
    maxLng: number;
    maxLat: number;
}

/** 标记池配置 */
export interface MarkerPoolConfig {
    initialSize: number;
    growSize: number;
    maxSize: number;
}

/** 聚合提示配置 */
export interface ClusterHintConfig {
    enabled: boolean;
    position: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
    zIndex: number;
}

/** 图层管理器接口 */
export interface ILayerManager {
    adapter: IMapAdapterExtended;
    view: MapView;
    config: LayerManagerConfig;

    // 图层操作
    addPointsLayer(geojson: GeoJSONFeatureCollection, layerName?: string): Promise<void>;
    addRasterLayer(type: string, url: string): Promise<void>;
    toggleLayer(layerName: string, visible: boolean): void;
    setLayerOpacity(layerName: string, opacity: number): void;
    setRasterOpacity(opacity: number): void;
    removeLayer(layerName: string): void;
    clearAllLayers(): void;

    // 采样点操作
    addSamplingPoint(pointData: SamplingPoint): Promise<void>;
    addMarker(pointData: SamplingPoint): Promise<void>;
    getSamplingPoints(): SamplingPoint[];
    getCurrentMarkerStyle(): { color: string; shape: string };

    // 交互操作
    setupClickHandler(handler: (graphic: MapGraphic, mapPoint: MapPoint) => void): void;
    showInfoPanel(graphic: MapGraphic, mapPoint: MapPoint): void;
    hideInfoPanel(): void;

    // 性能优化
    _refreshVisibleMarkers(): void;
    _updateClusterHint(hiddenCount: number): void;
}

/** 图层事件类型 */
export type LayerEventType =
    | 'add'
    | 'remove'
    | 'visibility-change'
    | 'opacity-change'
    | 'load'
    | 'error'
    | 'click'
    | 'hover';

/** 图层事件 */
export interface LayerEvent {
    type: LayerEventType;
    layerId: string;
    timestamp: number;
    data?: any;
}

/** 图层事件监听器 */
export type LayerEventListener = (event: LayerEvent) => void;

// ========== 图层渲染 ==========

/** 渲染引擎接口 */
export interface IRenderEngine {
    renderLayer(config: LayerConfig): Promise<void>;
    updateLayer(layerId: string, updates: Partial<LayerConfig>): Promise<void>;
    removeLayer(layerId: string): Promise<void>;
    clear(): Promise<void>;
}

/** 渲染选项 */
export interface RenderOptions {
    quality?: 'low' | 'medium' | 'high';
    antialias?: boolean;
    debug?: boolean;
}

/** 样式规则 */
export interface StyleRule {
    property: string;
    condition: (value: any) => boolean;
    style: any;
}

/** 样式表 */
export interface StyleSheet {
    defaultStyle: any;
    rules: StyleRule[];
}

// ========== 图层缓存 ==========

/** 缓存条目 */
export interface LayerCacheEntry {
    config: LayerConfig;
    metadata: LayerMetadata;
    blob?: Blob;
    expiresAt: number;
}

/** 缓存配置 */
export interface LayerCacheConfig {
    maxSize: number;              // 最大缓存条目数
    maxMemory: number;            // 最大内存使用（字节）
    ttl: number;                  // 生存时间（毫秒）
    persistToStorage?: boolean;   // 是否持久化到存储
}

/** 缓存接口 */
export interface ILayerCache {
    get(layerId: string): Promise<LayerCacheEntry | null>;
    set(entry: LayerCacheEntry): Promise<void>;
    delete(layerId: string): Promise<void>;
    clear(): Promise<void>;
    getStats(): {
        size: number;
        memory: number;
        hitRate: number;
    };
}

// ========== 图层导出 ==========

/** 导出格式 */
export type LayerExportFormat = 'geojson' | 'kml' | 'shapefile' | 'mvt' | 'pbf';

/** 导出选项 */
export interface LayerExportOptions {
    format: LayerExportFormat;
    layerIds: string[];
    bounds?: ViewportBounds;
    includeStyles?: boolean;
    compress?: boolean;
}

/** 导出结果 */
export interface LayerExportResult {
    blob: Blob;
    filename: string;
    format: LayerExportFormat;
    size: number;
}

/** 导出器接口 */
export interface ILayerExporter {
    export(options: LayerExportOptions): Promise<LayerExportResult>;
    getSupportedFormats(): LayerExportFormat[];
    validateFormat(format: string): boolean;
}

// ========== 图层过滤 ==========

/** 过滤条件 */
export interface FilterCondition {
    property: string;
    operator: 'eq' | 'ne' | 'gt' | 'lt' | 'gte' | 'lte' | 'in' | 'nin' | 'contains';
    value: any;
}

/** 过滤器接口 */
export interface ILayerFilter {
    addCondition(condition: FilterCondition): void;
    removeCondition(conditionId: string): void;
    clearConditions(): void;
    apply(data: any[]): any[];
    getActiveConditions(): FilterCondition[];
}

/** 空间过滤器 */
export interface ISpatialFilter {
    setBounds(bounds: ViewportBounds): void;
    setBuffer(buffer: number): void;
    filter(data: SamplingPoint[]): SamplingPoint[];
}