/**
 * 地图引擎基类
 * 定义统一的地图操作接口，供 GeoSceneEngine 和 AMapEngine 实现
 */

import type { Bounds, MapInitOptions, ZoomCallback, MoveCallback } from '../../../types/map-engine';

/**
 * 地图引擎抽象基类
 * 定义所有地图引擎必须实现的接口
 */
export abstract class BaseMapEngine {
    /** 是否支持自定义重置 */
    supportsCustomReset: boolean;

    /** 缩放回调列表 */
    protected zoomCallbacks: ZoomCallback[];

    /** 移动回调列表 */
    protected moveCallbacks: MoveCallback[];

    constructor() {
        this.supportsCustomReset = false;
        this.zoomCallbacks = [];
        this.moveCallbacks = [];
    }

    /**
     * 初始化地图
     * @param container - 地图容器元素或 ID
     * @param options - 初始化选项
     * @returns Promise<void>
     */
    abstract init(container: HTMLElement | string, options?: MapInitOptions): Promise<void>;

    /**
     * 设置地图中心点
     * @param center - [lng, lat]
     */
    abstract setCenter(center: [number, number]): void;

    /**
     * 获取地图中心点
     * @returns [lng, lat]
     */
    abstract getCenter(): [number, number];

    /**
     * 设置缩放级别
     * @param zoom - 缩放级别
     */
    abstract setZoom(zoom: number): void;

    /**
     * 获取缩放级别
     * @returns 缩放级别
     */
    abstract getZoom(): number;

    /**
     * 适配到指定边界
     * @param bounds - 边界对象 {minLng, minLat, maxLng, maxLat}
     */
    abstract fitToBounds(bounds: Bounds): void;

    /**
     * 注册缩放变化回调
     * @param callback - 回调函数，参数为新的缩放级别
     */
    onZoom(callback: ZoomCallback): void {
        this.zoomCallbacks.push(callback);
    }

    /**
     * 注册移动回调
     * @param callback - 回调函数，参数为新的中心点
     */
    onMove(callback: MoveCallback): void {
        this.moveCallbacks.push(callback);
    }

    /**
     * 触发缩放回调
     * @param zoom - 新的缩放级别
     */
    protected triggerZoomCallbacks(zoom: number): void {
        this.zoomCallbacks.forEach(callback => callback(zoom));
    }

    /**
     * 触发移动回调
     * @param center - 新的中心点
     */
    protected triggerMoveCallbacks(center: [number, number]): void {
        this.moveCallbacks.forEach(callback => callback(center));
    }

    /**
     * 销毁地图实例
     */
    destroy(): void {
        this.zoomCallbacks = [];
        this.moveCallbacks = [];
    }
}