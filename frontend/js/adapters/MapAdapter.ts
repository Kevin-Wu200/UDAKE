/**
 * 地图适配器接口
 * 定义统一的地图操作方法，供 ArcGIS 和高德地图适配器实现
 */

import type {
    GeoJSONFeatureCollection,
    SamplingPoint,
    PolygonStyleOptions
} from '../../types/core';
import type {
    AdapterOptions,
    ClickHandler
} from '../../types/adapter';

/**
 * 地图适配器抽象类
 * 定义统一的地图操作方法
 */
export abstract class MapAdapter {
    /**
     * 初始化地图
     * @param containerId - 地图容器 ID
     * @param options - 初始化选项
     * @returns 地图视图对象
     */
    abstract initMap(containerId: string, options?: AdapterOptions): Promise<any>;

    /**
     * 获取地图视图对象
     * @returns 地图视图
     */
    abstract getView(): any;

    /**
     * 添加 GeoJSON 点图层
     * @param geojson - GeoJSON 数据
     * @param layerName - 图层名称
     */
    abstract addPointsLayer(geojson: GeoJSONFeatureCollection, layerName?: string): Promise<void>;

    /**
     * 添加栅格图层
     * @param type - 图层类型（prediction/variance）
     * @param url - 栅格数据 URL
     */
    abstract addRasterLayer(type: 'prediction' | 'variance', url: string): Promise<void>;

    /**
     * 添加单个采样点
     * @param pointData - 点数据 {x, y, value}
     */
    abstract addMarker(pointData: SamplingPoint): Promise<void>;

    /**
     * 添加多边形
     * @param coordinates - 多边形坐标数组
     * @param options - 样式选项
     */
    abstract addPolygon(coordinates: number[][][], options?: PolygonStyleOptions): Promise<any>;

    /**
     * 切换图层可见性
     * @param layerName - 图层名称
     * @param visible - 是否可见
     */
    abstract toggleLayer(layerName: string, visible: boolean): void;

    /**
     * 设置图层透明度
     * @param layerName - 图层名称
     * @param opacity - 透明度 (0-1)
     */
    abstract setLayerOpacity(layerName: string, opacity: number): void;

    /**
     * 设置图层Z轴索引
     * @param layerName - 图层名称
     * @param zIndex - Z轴索引
     */
    abstract setLayerZIndex(layerName: string, zIndex: number): void;

    /**
     * 移除图层
     * @param layerName - 图层名称
     */
    abstract removeLayer(layerName: string): void;

    /**
     * 清除所有图层
     */
    abstract clearAllLayers(): void;

    /**
     * 缩放到图层范围
     * @param layerName - 图层名称
     */
    abstract zoomToLayer(layerName: string): void;

    /**
     * 设置点击事件处理器
     * @param handler - 点击事件处理函数
     */
    abstract setClickHandler(handler: ClickHandler): void;

    /**
     * 获取采样点数据
     * @returns 采样点数组
     */
    abstract getSamplingPoints(): SamplingPoint[];
}