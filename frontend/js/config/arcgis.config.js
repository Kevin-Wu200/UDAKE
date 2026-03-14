/**
 * ArcGIS API for JavaScript 配置文件
 *
 * 重要说明：
 * 1. 当前支持从后端动态获取API Key
 * 2. 若API Key为空，自动启用Mock模式
 * 3. 禁止在其他文件中硬编码ArcGIS配置
 */

// 默认配置（当无法从后端获取时使用）
const DEFAULT_CONFIG = {
    API_KEY: "YOUR_ARCGIS_API_KEY_HERE",
    PORTAL_URL: "https://www.arcgis.com",
    ENV: "development",
    ARCGIS_LIGHT_BASEMAP: "arcgis-topographic",
    ARCGIS_DARK_BASEMAP: "arcgis-dark-gray",
    ARCGIS_DEFAULT_CENTER: [139.767125, 35.681236], // 东京
    ARCGIS_DEFAULT_ZOOM: 10,
    VIEW_OPTIONS: {
        constraints: {
            minZoom: 3,
            maxZoom: 18
        }
    }
};

// 当前配置（从后端获取或使用默认值）
let currentConfig = { ...DEFAULT_CONFIG };

export const ArcGISConfig = {
    // API Key配置
    get API_KEY() {
        return currentConfig.API_KEY;
    },

    // Portal配置
    get PORTAL_URL() {
        return currentConfig.PORTAL_URL;
    },

    // 环境配置
    get ENV() {
        return currentConfig.ENV;
    },

    // 底图配置
    get ARCGIS_LIGHT_BASEMAP() {
        return currentConfig.ARCGIS_LIGHT_BASEMAP;
    },

    get ARCGIS_DARK_BASEMAP() {
        return currentConfig.ARCGIS_DARK_BASEMAP;
    },

    // 默认地图配置
    get ARCGIS_DEFAULT_CENTER() {
        return currentConfig.ARCGIS_DEFAULT_CENTER;
    },

    get ARCGIS_DEFAULT_ZOOM() {
        return currentConfig.ARCGIS_DEFAULT_ZOOM;
    },

    // 地图视图配置
    get VIEW_OPTIONS() {
        return currentConfig.VIEW_OPTIONS;
    },

    /**
     * 从后端更新配置
     * @param {Object} config - 从后端获取的配置对象
     */
    updateConfig(config) {
        if (config && config.arcgis) {
            currentConfig = {
                API_KEY: config.arcgis.apiKey || DEFAULT_CONFIG.API_KEY,
                PORTAL_URL: config.arcgis.portalUrl || DEFAULT_CONFIG.PORTAL_URL,
                ENV: config.arcgis.env || DEFAULT_CONFIG.ENV,
                ARCGIS_LIGHT_BASEMAP: config.arcgis.defaultBasemap || DEFAULT_CONFIG.ARCGIS_LIGHT_BASEMAP,
                ARCGIS_DARK_BASEMAP: "arcgis-dark-gray",
                ARCGIS_DEFAULT_CENTER: config.arcgis.defaultCenter || DEFAULT_CONFIG.ARCGIS_DEFAULT_CENTER,
                ARCGIS_DEFAULT_ZOOM: config.arcgis.defaultZoom || DEFAULT_CONFIG.ARCGIS_DEFAULT_ZOOM,
                VIEW_OPTIONS: DEFAULT_CONFIG.VIEW_OPTIONS
            };
            console.log('✅ ArcGIS 配置已从后端更新');
        }
    },

    // Mock模式检测
    isMockMode() {
        return !this.API_KEY || this.API_KEY === "YOUR_ARCGIS_API_KEY_HERE";
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
