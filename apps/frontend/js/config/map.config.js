/**
 * 地图引擎配置文件
 *
 * 支持两种地图引擎：
 * - geoscene: GeoScene Maps SDK for JavaScript
 * - amap: 高德地图 JS API
 *
 * 切换方式：修改 MAP_PROVIDER 的值
 */

export const MapConfig = {
    // 地图引擎选择：'arcgis' 或 'amap'
    MAP_PROVIDER: 'arcgis',

    // 获取当前地图引擎
    getProvider() {
        return this.MAP_PROVIDER;
    },

    // 检查是否使用 GeoScene
    isGeoScene() {
        return this.MAP_PROVIDER === 'arcgis';
    },

    // 检查是否使用高德地图
    isAMap() {
        return this.MAP_PROVIDER === 'amap';
    }
};
