/**
 * 地图适配器类型定义
 * 定义地图适配器的抽象接口和具体实现
 */

import type {
    GeoJSONFeatureCollection,
    SamplingPoint,
    Bounds,
    MarkerOptions,
    PolygonStyleOptions
} from './core';
import type { BaseMapEngine } from './map-engine';

// ========== 适配器配置类型 ==========

/** 适配器选项 */
export interface AdapterOptions {
    center?: [number, number];
    zoom?: number;
    [key: string]: any;
}

/** 点击事件处理器类型 */
export type ClickHandler = (graphic: any, mapPoint: any) => void;

// ========== 适配器接口 ==========

/** 地图适配器抽象类 */
export abstract class MapAdapter {
    /** 初始化地图 */
    abstract initMap(containerId: string, options?: AdapterOptions): Promise<any>;

    /** 获取地图视图对象 */
    abstract getView(): any;

    /** 添加 GeoJSON 点图层 */
    abstract addPointsLayer(geojson: GeoJSONFeatureCollection, layerName?: string): Promise<void>;

    /** 添加栅格图层 */
    abstract addRasterLayer(type: 'prediction' | 'variance', url: string): Promise<void>;

    /** 添加单个采样点 */
    abstract addMarker(pointData: SamplingPoint): Promise<void>;

    /** 添加多边形 */
    abstract addPolygon(coordinates: number[][][], options?: PolygonStyleOptions): Promise<any>;

    /** 切换图层可见性 */
    abstract toggleLayer(layerName: string, visible: boolean): void;

    /** 设置图层透明度 */
    abstract setLayerOpacity(layerName: string, opacity: number): void;

    /** 移除图层 */
    abstract removeLayer(layerName: string): void;

    /** 清除所有图层 */
    abstract clearAllLayers(): void;

    /** 缩放到图层范围 */
    abstract zoomToLayer(layerName: string): void;

    /** 设置点击事件处理器 */
    abstract setClickHandler(handler: ClickHandler): void;

    /** 获取采样点数据 */
    abstract getSamplingPoints(): SamplingPoint[];
}

// ========== ArcGIS 适配器特定类型 ==========

/** ArcGIS 适配器图层存储 */
export interface ArcGISLayerStore {
    [layerName: string]: any;
}

/** ArcGIS 图形图层 */
export interface GraphicsLayer {
    title: string;
    graphics: any[];
    add(graphic: any): void;
    removeAll(): void;
}

/** ArcGIS 适配器 */
export class ArcGISAdapter extends MapAdapter {
    /** ArcGIS 地图引擎 */
    engine: any;

    /** ArcGIS 视图 */
    view: any;

    /** ArcGIS 地图 */
    map: any;

    /** 图层存储 */
    layers: ArcGISLayerStore;

    /** 图形图层 */
    graphicsLayer: GraphicsLayer | null;

    /** 采样点列表 */
    samplingPoints: SamplingPoint[];

    constructor();

    initMap(containerId: string, options?: AdapterOptions): Promise<any>;
    initGraphicsLayer(): Promise<void>;
    getView(): any;
    getEngine(): any;
    addPointsLayer(geojson: GeoJSONFeatureCollection, layerName?: string): Promise<void>;
    addRasterLayer(type: 'prediction' | 'variance', url: string): Promise<void>;
    addMarker(pointData: SamplingPoint): Promise<void>;
    addPolygon(coordinates: number[][][], options?: PolygonStyleOptions): Promise<void>;
    toggleLayer(layerName: string, visible: boolean): void;
    setLayerOpacity(layerName: string, opacity: number): void;
    removeLayer(layerName: string): void;
    clearAllLayers(): void;
    zoomToLayer(layerName: string): void;
    setClickHandler(handler: ClickHandler): void;
    getSamplingPoints(): SamplingPoint[];
}