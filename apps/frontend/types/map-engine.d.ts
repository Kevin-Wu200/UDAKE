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
export interface ArcGISConfig {
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

/** ArcGIS 地图引擎 */
export class ArcGISEngine extends BaseMapEngine {
    /** ArcGIS MapView 实例 */
    view: IMapView | null;

    /** ArcGIS Map 实例 */
    map: IMap | null;

    /** 配置选项 */
    options: ArcGISConfig;

    constructor(options?: ArcGISConfig);

    init(container: HTMLElement | string, options?: MapInitOptions): Promise<void>;
    setCenter(center: [number, number]): void;
    getCenter(): [number, number];
    setZoom(zoom: number): void;
    getZoom(): number;
    fitToBounds(bounds: Bounds): Promise<void>;
    getView(): IMapView | null;
    destroy(): void;
}