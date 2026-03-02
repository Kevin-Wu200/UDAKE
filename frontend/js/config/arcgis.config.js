/**
 * ArcGIS API for JavaScript 配置文件
 *
 * 重要说明：
 * 1. 当前使用占位符API Key，未来替换真实Key时仅需修改此文件
 * 2. 若API Key为空，自动启用Mock模式
 * 3. 禁止在其他文件中硬编码ArcGIS配置
 */

export const ArcGISConfig = {
    // API Key配置
    API_KEY: "YOUR_ARCGIS_API_KEY_PLACEHOLDER",

    // Portal配置
    PORTAL_URL: "https://www.arcgis.com",

    // 环境配置
    ENV: "development",

    // 底图配置
    ARCGIS_LIGHT_BASEMAP: "arcgis-topographic",
    ARCGIS_DARK_BASEMAP: "arcgis-dark-gray",

    // 默认地图配置
    ARCGIS_DEFAULT_CENTER: [139.767125, 35.681236], // 东京
    ARCGIS_DEFAULT_ZOOM: 10,

    // 地图视图配置
    VIEW_OPTIONS: {
        constraints: {
            minZoom: 3,
            maxZoom: 18
        }
    },

    // Mock模式检测
    isMockMode() {
        return !this.API_KEY || this.API_KEY === "YOUR_ARCGIS_API_KEY_PLACEHOLDER";
    },

    // 获取配置信息
    getConfig() {
        if (this.isMockMode()) {
            console.warn("⚠️ ArcGIS API Key 未配置，当前为 Mock 模式");
        }
        return {
            apiKey: this.API_KEY,
            portalUrl: this.PORTAL_URL,
            env: this.ENV,
            isMock: this.isMockMode()
        };
    }
};
