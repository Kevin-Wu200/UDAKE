/**
 * 地图适配器接口
 * 定义统一的地图操作方法，供 ArcGIS 和天地图适配器实现
 */

export class MapAdapter {
    /**
     * 初始化地图
     * @param {string} containerId - 地图容器 ID
     * @returns {Promise<Object>} 地图视图对象
     */
    async initMap(containerId) {
        throw new Error('initMap() 必须由子类实现');
    }

    /**
     * 获取地图视图对象
     * @returns {Object} 地图视图
     */
    getView() {
        throw new Error('getView() 必须由子类实现');
    }

    /**
     * 添加 GeoJSON 点图层
     * @param {Object} geojson - GeoJSON 数据
     * @param {string} layerName - 图层名称
     * @returns {Promise<void>}
     */
    async addPointsLayer(geojson, layerName) {
        throw new Error('addPointsLayer() 必须由子类实现');
    }

    /**
     * 添加栅格图层
     * @param {string} type - 图层类型（prediction/variance）
     * @param {string} url - 栅格数据 URL
     * @returns {Promise<void>}
     */
    async addRasterLayer(type, url) {
        throw new Error('addRasterLayer() 必须由子类实现');
    }

    /**
     * 添加单个采样点
     * @param {Object} pointData - 点数据 {x, y, value}
     * @returns {Promise<void>}
     */
    async addMarker(pointData) {
        throw new Error('addMarker() 必须由子类实现');
    }

    /**
     * 添加多边形
     * @param {Array} coordinates - 多边形坐标数组
     * @param {Object} options - 样式选项
     * @returns {Promise<void>}
     */
    async addPolygon(coordinates, options) {
        throw new Error('addPolygon() 必须由子类实现');
    }

    /**
     * 切换图层可见性
     * @param {string} layerName - 图层名称
     * @param {boolean} visible - 是否可见
     */
    toggleLayer(layerName, visible) {
        throw new Error('toggleLayer() 必须由子类实现');
    }

    /**
     * 设置图层透明度
     * @param {string} layerName - 图层名称
     * @param {number} opacity - 透明度 (0-1)
     */
    setLayerOpacity(layerName, opacity) {
        throw new Error('setLayerOpacity() 必须由子类实现');
    }

    /**
     * 移除图层
     * @param {string} layerName - 图层名称
     */
    removeLayer(layerName) {
        throw new Error('removeLayer() 必须由子类实现');
    }

    /**
     * 清除所有图层
     */
    clearAllLayers() {
        throw new Error('clearAllLayers() 必须由子类实现');
    }

    /**
     * 缩放到图层范围
     * @param {string} layerName - 图层名称
     */
    zoomToLayer(layerName) {
        throw new Error('zoomToLayer() 必须由子类实现');
    }

    /**
     * 设置点击事件处理器
     * @param {Function} handler - 点击事件处理函数
     */
    setClickHandler(handler) {
        throw new Error('setClickHandler() 必须由子类实现');
    }

    /**
     * 获取采样点数据
     * @returns {Array} 采样点数组
     */
    getSamplingPoints() {
        throw new Error('getSamplingPoints() 必须由子类实现');
    }
}
