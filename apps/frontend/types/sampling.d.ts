/**
 * 采样模块类型定义
 * 定义采样相关的数据结构和接口
 */

import type {
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    SamplingPoint
} from './core';
import type { MapAdapter } from './adapter';

// ========== 坐标输入类型 ==========

/** 坐标获取方式 */
export type CoordinateMode = 'manual' | 'device';

/** 坐标值 */
export interface Coordinate {
    longitude: number;
    latitude: number;
    accuracy?: number;
    timestamp?: string;
}

/** 坐标值和采样值 */
export interface SamplingPointValue extends Coordinate {
    value: number;
}

/** 坐标变化回调 */
export type CoordinateChangeCallback = (position: Coordinate) => void;

/** 坐标解析结果 */
export interface CoordinateParseResult {
    valid: boolean;
    value?: number;
    error?: string;
}

/** 坐标输入状态 */
export interface CoordinateInputState {
    longitude_raw: string;
    longitude: number | null;
    latitude_raw: string;
    latitude: number | null;
    sampleValue_raw: string;
    sampleValue: number | null;
}

/** 坐标输入组件 */
export class CoordinateInput {
    /** 坐标获取方式 */
    mode: CoordinateMode;

    /** 坐标变化回调 */
    onCoordinateChange: CoordinateChangeCallback | null;

    /** 当前位置 */
    currentPosition: Coordinate | null;

    /** 监听 ID（已废弃，保留兼容） */
    watchId: number | null;

    /** 状态 */
    state: CoordinateInputState;

    constructor(mode: CoordinateMode, onCoordinateChange?: CoordinateChangeCallback);

    /** 创建输入面板 */
    createPanel(): HTMLElement;

    /** 创建手动输入界面 */
    protected createManualInput(): HTMLElement;

    /** 创建设备定位界面 */
    protected createDeviceInput(): HTMLElement;

    /** 获取当前位置 */
    getCurrentPosition(): void;

    /** 执行定位获取（内部方法） */
    protected _doGetPosition(): void;

    /** 处理定位成功 */
    protected handlePositionSuccess(position: Coordinate & { accuracy: number }): void;

    /** 处理权限管理模块返回的错误 */
    protected _handlePermissionError(error: any): void;

    /** 验证坐标 */
    validateCoordinate(value: string, type: 'longitude' | 'latitude'): boolean;

    /** 验证采样值 */
    validateSampleValue(value: string): boolean;

    /** 验证经度（已废弃） */
    validateLongitude(value: string): boolean;

    /** 验证纬度（已废弃） */
    validateLatitude(value: string): boolean;

    /** 获取当前坐标和值 */
    getValue(): SamplingPointValue | null;

    /** 清空输入 */
    clear(): void;

    /** 设置坐标值 */
    setValue(position: Coordinate): void;

    /** 销毁组件 */
    destroy(): void;
}

// ========== 采样模式类型 ==========

/** 采样模式 */
export type SamplingMode = 'free' | 'region';

/** 点添加回调 */
export type PointAddedCallback = (pointData: SamplingPointValue) => Promise<void>;

// ========== 自由采样类型 ==========

/** 自由采样组件 */
export class FreeSampling {
    /** 地图视图 */
    view: any;

    /** 点添加回调 */
    onPointAdded: PointAddedCallback | null;

    /** 坐标输入组件 */
    coordinateInput: CoordinateInput | null;

    /** 坐标获取方式 */
    coordinateMode: CoordinateMode;

    constructor(view: any, onPointAdded?: PointAddedCallback);

    /** 创建采样面板 */
    createPanel(coordinateMode?: CoordinateMode): HTMLElement;

    /** 绑定事件 */
    protected bindEvents(container: HTMLElement): void;

    /** 处理坐标变化 */
    protected handleCoordinateChange(position: Coordinate): void;

    /** 添加采样点 */
    addPoint(): Promise<void>;

    /** 清空输入 */
    clearInput(): void;

    /** 销毁组件 */
    destroy(): void;
}

// ========== 区域采样类型 ==========

/** 边界多边形 */
export interface BoundaryPolygon {
    type: 'Feature';
    geometry: GeoJSONFeature['geometry'];
    properties: Record<string, any>;
}

/** 边界图层 */
export interface BoundaryLayer {
    title?: string;
}

/** 区域采样组件 */
export class RegionSampling {
    /** 地图视图或适配器 */
    view: any;

    /** 适配器 */
    adapter: MapAdapter | null;

    /** 点添加回调 */
    onPointAdded: PointAddedCallback | null;

    /** 坐标输入组件 */
    coordinateInput: CoordinateInput | null;

    /** 坐标获取方式 */
    coordinateMode: CoordinateMode;

    /** 边界多边形 */
    boundaryPolygon: BoundaryPolygon | null;

    /** 边界图层 */
    boundaryLayer: BoundaryLayer | null;

    /** 地图提供者 */
    mapProvider: 'arcgis';

    constructor(viewOrAdapter: any, onPointAdded?: PointAddedCallback);

    /** 创建采样面板 */
    createPanel(coordinateMode?: CoordinateMode): HTMLElement;

    /** 绑定边界上传事件 */
    protected bindBoundaryUploadEvents(container: HTMLElement): void;

    /** 处理边界上传 */
    handleBoundaryUpload(fileInput: HTMLInputElement): Promise<void>;

    /** 在地图上显示边界 */
    protected displayBoundary(polygon: BoundaryPolygon): Promise<void>;

    /** ArcGIS 显示边界 */
    protected displayBoundaryArcGIS(polygon: BoundaryPolygon): Promise<void>;

    /** 获取多边形环坐标 */
    protected getPolygonRings(geometry: GeoJSONFeature['geometry']): number[][][];

    /** 显示采样输入区域 */
    protected showSamplingSection(): void;

    /** 处理坐标变化 */
    protected handleCoordinateChange(position: Coordinate): void;

    /** 添加采样点 */
    addPoint(): Promise<void>;

    /** 检查点是否在边界内 */
    protected isPointInBoundary(point: Coordinate): boolean;

    /** 获取多边形坐标数组 */
    protected getPolygonCoordinates(): number[][];

    /** 清空输入 */
    clearInput(): void;

    /** 获取边界多边形 */
    getBoundaryPolygon(): BoundaryPolygon | null;

    /** 销毁组件 */
    destroy(): void;
}

// ========== 地图管理器类型 ==========

/** 地图提供者 */
export type MapProvider = 'arcgis' | 'geoscene' | 'amap';

/** 地图模式 */
export type MapMode = 'normal' | 'areaSampling';

/** 地图管理器选项 */
export interface MapManagerOptions {
    center?: [number, number];
    zoom?: number;
    [key: string]: any;
}

/** 地图管理器 */
export class MapManager {
    /** 地图引擎 */
    mapEngine: any;

    /** 初始中心点 */
    initialCenter: [number, number] | null;

    /** 初始缩放级别 */
    initialZoom: number | null;

    /** GeoJSON 数据 */
    geojson: GeoJSONFeatureCollection | null;

    /** 地图模式 */
    mode: MapMode;

    /** 重置按钮 */
    resetButton: HTMLElement | null;

    constructor();

    /** 初始化地图 */
    init(provider: MapProvider, containerId: string, options?: MapManagerOptions): Promise<void>;

    /** 创建 reset 按钮 */
    protected createResetButton(containerId: string | HTMLElement): void;

    /** 处理 reset 按钮点击 */
    protected handleReset(): void;

    /** 切换到区域采样模式 */
    enterAreaSamplingMode(geojson: GeoJSONFeatureCollection): void;

    /** 切换到普通模式 */
    enterNormalMode(): void;

    /** 获取地图引擎 */
    getEngine(): any;

    /** 销毁 */
    destroy(): void;
}
