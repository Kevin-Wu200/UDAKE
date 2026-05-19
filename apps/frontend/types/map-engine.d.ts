/**
 * 地图引擎类型定义
 * 定义地图引擎的抽象接口和具体实现
 */

import { Bounds, MapInitOptions } from './core';

// 重新导出核心类型
export type { Bounds, MapInitOptions };

// ========== 地图引擎接口 ==========

/** 地图回调函数类型 */
export type ZoomCallback = (zoom: number) => void;
export type MoveCallback = (center: [number, number]) => void;

/** 路线类型 */
export type RouteType = 'driving' | 'walking' | 'transfer';

/** 地图视图抽象接口 */
export interface IMapView {
    center: { longitude: number; latitude: number };
    zoom: number;
    spatialReference: any;
    ui: {
        components: string[];
        add(widget: any, position: string): void;
    };
    destroy(): void;
    when(): Promise<void>;
    watch(property: string, callback: (newValue: any) => void): any;
    goTo(options: any): Promise<void>;
}

/** 地图实例抽象接口 */
export interface IMap {
    basemap: string;
    destroy(): void;
}

/** 地图引擎接口 */
export interface BaseMapEngine {
    /** 是否支持自定义重置 */
    supportsCustomReset: boolean;

    /**
     * 初始化地图
     * @param container - 地图容器元素或 ID
     * @param options - 初始化选项
     */
    init(container: HTMLElement | string, options?: MapInitOptions): Promise<void>;

    /**
     * 设置地图中心点
     * @param center - [lng, lat]
     */
    setCenter(center: [number, number]): void;

    /**
     * 获取地图中心点
     * @returns [lng, lat]
     */
    getCenter(): [number, number];

    /**
     * 设置缩放级别
     * @param zoom - 缩放级别
     */
    setZoom(zoom: number): void;

    /**
     * 获取缩放级别
     * @returns 缩放级别
     */
    getZoom(): number;

    /**
     * 适配到指定边界
     * @param bounds - 边界对象
     */
    fitToBounds(bounds: Bounds): void;

    /**
     * 注册缩放变化回调
     * @param callback - 回调函数
     */
    onZoom(callback: ZoomCallback): void;

    /**
     * 注册移动回调
     * @param callback - 回调函数
     */
    onMove(callback: MoveCallback): void;

    /**
     * 销毁地图实例
     */
    destroy(): void;
}

// ========== ArcGIS 特定类型 ==========

/** ArcGIS 地图引擎配置 */
export interface GeoSceneConfig {
    basemap?: string;
    center?: [number, number];
    zoom?: number;
    minZoom?: number;
    maxZoom?: number;
}

/** ArcGIS 扩展边界 */
export interface ArcGISExtent {
    xmin: number;
    ymin: number;
    xmax: number;
    ymax: number;
    spatialReference: any;
}

// ========== Canvas 引擎特定类型 ==========

/** 高斯-克吕格投影带类型 */
export type GKBandType = '3-degree' | '6-degree';

/** GK 投影配置 */
export interface GKProjectionConfig {
    /** 中央经线（度），不指定则根据中心点自动计算 */
    centralMeridian?: number;
    /** 带类型，默认 3 度带 */
    bandType?: GKBandType;
    /** 椭球参数：长半轴（米），默认 WGS84 */
    semiMajorAxis?: number;
    /** 椭球参数：扁率倒数，默认 WGS84 */
    inverseFlattening?: number;
    /** 东偏移（米），默认 500000 */
    falseEasting?: number;
    /** 北偏移（米），默认 0 */
    falseNorthing?: number;
}

/** 画布引擎配置 */
export interface CanvasEngineConfig {
    /** GK 投影配置 */
    projection?: GKProjectionConfig;
    /** 初始中心点 [lng, lat] */
    center?: [number, number];
    /** 初始缩放级别 */
    zoom?: number;
    /** 最小缩放 */
    minZoom?: number;
    /** 最大缩放 */
    maxZoom?: number;
    /** 栅格图层 API 基础 URL（ArcGIS ImageryLayer Export Image） */
    imageryBaseUrl?: string;
    /** 是否启用深色模式 */
    darkMode?: boolean;
}

/** GK 平面坐标（米） */
export interface GKCoordinate {
    /** 东向坐标 (Easting) */
    x: number;
    /** 北向坐标 (Northing) */
    y: number;
}

/** 画布视口边界（GK 坐标） */
export interface CanvasViewportBounds {
    /** 最小东向坐标 */
    minX: number;
    /** 最小北向坐标 */
    minY: number;
    /** 最大东向坐标 */
    maxX: number;
    /** 最大北向坐标 */
    maxY: number;
}

/** ArcGIS 地图引擎 */
export class GeoSceneEngine extends BaseMapEngine {
    /** ArcGIS MapView 实例 */
    view: IMapView | null;

    /** ArcGIS Map 实例 */
    map: IMap | null;

    /** 配置选项 */
    options: GeoSceneConfig;

    constructor(options?: GeoSceneConfig);

    init(container: HTMLElement | string, options?: MapInitOptions): Promise<void>;
    setCenter(center: [number, number]): void;
    getCenter(): [number, number];
    setZoom(zoom: number): void;
    getZoom(): number;
    fitToBounds(bounds: Bounds): Promise<void>;
    getView(): IMapView | null;
    destroy(): void;
}