/**
 * 地图引擎配置文件
 *
 * 支持两种地图引擎：
 * - arcgis: ArcGIS API for JavaScript
 * - tianditu: 天地图 + Leaflet
 *
 * 切换方式：修改 MAP_PROVIDER 的值
 */

export const MapConfig = {
    // 地图引擎选择：'arcgis' 或 'tianditu'
    MAP_PROVIDER: 'tianditu',

    // 获取当前地图引擎
    getProvider() {
        return this.MAP_PROVIDER;
    },

    // 检查是否使用 ArcGIS
    isArcGIS() {
        return this.MAP_PROVIDER === 'arcgis';
    },

    // 检查是否使用天地图
    isTianditu() {
        return this.MAP_PROVIDER === 'tianditu';
    }
};
