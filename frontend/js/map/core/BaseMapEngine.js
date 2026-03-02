/**
 * 地图引擎基类
 * 定义统一的地图操作接口，供 TiandituEngine 和 ArcGISEngine 实现
 */
export class BaseMapEngine {
    constructor() {
        this.supportsCustomReset = false;
        this.zoomCallbacks = [];
        this.moveCallbacks = [];
    }

    /**
     * 初始化地图
     * @param {HTMLElement|string} container - 地图容器元素或 ID
     * @param {Object} options - 初始化选项
     * @param {Array<number>} options.center - 中心点 [lng, lat]
     * @param {number} options.zoom - 缩放级别
     * @returns {Promise<void>}
     */
    async init(container, options = {}) {
        throw new Error('init() 必须由子类实现');
    }

    /**
     * 设置地图中心点
     * @param {Array<number>} center - [lng, lat]
     */
    setCenter(center) {
        throw new Error('setCenter() 必须由子类实现');
    }

    /**
     * 获取地图中心点
     * @returns {Array<number>} [lng, lat]
     */
    getCenter() {
        throw new Error('getCenter() 必须由子类实现');
    }

    /**
     * 设置缩放级别
     * @param {number} zoom - 缩放级别
     */
    setZoom(zoom) {
        throw new Error('setZoom() 必须由子类实现');
    }

    /**
     * 获取缩放级别
     * @returns {number}
     */
    getZoom() {
        throw new Error('getZoom() 必须由子类实现');
    }

    /**
     * 适配到指定边界
     * @param {Object} bounds - 边界对象 {minLng, minLat, maxLng, maxLat}
     */
    fitToBounds(bounds) {
        throw new Error('fitToBounds() 必须由子类实现');
    }

    /**
     * 注册缩放变化回调
     * @param {Function} callback - 回调函数，参数为新的缩放级别
     */
    onZoom(callback) {
        this.zoomCallbacks.push(callback);
    }

    /**
     * 注册移动回调
     * @param {Function} callback - 回调函数，参数为新的中心点
     */
    onMove(callback) {
        this.moveCallbacks.push(callback);
    }

    /**
     * 触发缩放回调
     * @param {number} zoom - 新的缩放级别
     */
    triggerZoomCallbacks(zoom) {
        this.zoomCallbacks.forEach(callback => callback(zoom));
    }

    /**
     * 触发移动回调
     * @param {Array<number>} center - 新的中心点
     */
    triggerMoveCallbacks(center) {
        this.moveCallbacks.forEach(callback => callback(center));
    }

    /**
     * 销毁地图实例
     */
    destroy() {
        this.zoomCallbacks = [];
        this.moveCallbacks = [];
    }
}
