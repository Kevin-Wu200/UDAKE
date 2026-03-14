/**
 * 地图组件类型定义
 */

import {
    Bounds,
    MapInitOptions,
    SamplingPoint,
    GeoJSONFeatureCollection,
    MarkerOptions,
    PolygonStyleOptions
} from './core';

/** 地图适配器接口 */
export interface IMapAdapter {
    initMap(containerId: string, options?: MapInitOptions): Promise<any>;
    getView(): any;
    getEngine(): any;
    addPointsLayer(geojson: GeoJSONFeatureCollection, layerName?: string): Promise<void>;
    addRasterLayer(type: 'prediction' | 'variance', url: string): Promise<void>;
    addMarker(pointData: SamplingPoint): Promise<void>;
    addPolygon(coordinates: number[][][], options?: PolygonStyleOptions): Promise<any>;
    toggleLayer(layerName: string, visible: boolean): void;
    setLayerOpacity(layerName: string, opacity: number): void;
    removeLayer(layerName: string): void;
    clearAllLayers(): void;
    zoomToLayer(layerName: string): void;
    setClickHandler(handler: (graphic: any, mapPoint: any) => void): void;
    getSamplingPoints(): SamplingPoint[];
}

/** 地图引擎基类接口 */
export interface IMapEngine {
    init(container: HTMLElement | string, options?: MapInitOptions): Promise<void>;
    setCenter(center: [number, number]): void;
    getCenter(): [number, number];
    setZoom(zoom: number): void;
    getZoom(): number;
    fitToBounds(bounds: Bounds): void;
    onZoom(callback: (zoom: number) => void): void;
    onMove(callback: (center: [number, number]) => void): void;
    destroy(): void;
}

/** 图层管理器接口 */
export interface ILayerManager {
    addPointsLayer(geojson: GeoJSONFeatureCollection): Promise<void>;
    addRasterLayer(type: string, url: string): Promise<void>;
    toggleLayer(layerName: string, visible: boolean): void;
    setLayerOpacity(layerName: string, opacity: number): void;
    addSamplingPoint(pointData: SamplingPoint): Promise<void>;
    getSamplingPoints(): SamplingPoint[];
    clearAllLayers(): void;
}
