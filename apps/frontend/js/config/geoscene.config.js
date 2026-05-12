/**
 * GeoScene Maps SDK for JavaScript 配置文件
 *
 * 重要说明：
 * 1. 支持两种认证模式：apikey (API Key) 和 enterprise (企业账号)
 * 2. Enterprise 模式使用 GeoScene 企业服务器进行身份认证
 * 3. 若认证信息无效，自动启用Mock模式
 * 4. 禁止在其他文件中硬编码GeoScene配置
 */

/**
 * 从 import.meta.env 读取 VITE_* 环境变量
 */
function _readEnv(key, fallback = "") {
    try {
        const env = import.meta.env || {};
        return env[key] || fallback;
    } catch {
        return fallback;
    }
}

// 默认配置（优先从环境变量读取，无法获取时使用硬编码默认值）
const DEFAULT_CONFIG = {
    API_KEY: _readEnv("VITE_GEOSCENE_API_KEY", ""),
    AUTH_MODE: _readEnv("VITE_GEOSCENE_AUTH_MODE", "apikey"),  // "apikey" | "enterprise"
    USERNAME: _readEnv("VITE_GEOSCENE_USERNAME", ""),
    PASSWORD: _readEnv("VITE_GEOSCENE_PASSWORD", ""),
    PORTAL_URL: _readEnv("VITE_GEOSCENE_PORTAL_URL", "https://www.geoscene.cn"),
    TOKEN_URL: _readEnv("VITE_GEOSCENE_TOKEN_URL", ""),
    ENV: _readEnv("VITE_GEOSCENE_ENV", "development"),
    GEOSCENE_LIGHT_BASEMAP: "arcgis-topographic",
    GEOSCENE_DARK_BASEMAP: "arcgis-dark-gray",
    GEOSCENE_DEFAULT_CENTER: [139.767125, 35.681236], // 东京
    GEOSCENE_DEFAULT_ZOOM: 10,
    VIEW_OPTIONS: {
        constraints: {
            minZoom: 3,
            maxZoom: 18
        }
    }
};

// 当前配置（从后端获取或使用默认值）
let currentConfig = { ...DEFAULT_CONFIG };

export const GeoSceneConfig = {
    // API Key配置
    get API_KEY() {
        return currentConfig.API_KEY;
    },

    // 认证模式
    get AUTH_MODE() {
        return currentConfig.AUTH_MODE;
    },

    // Enterprise 认证
    get USERNAME() {
        return currentConfig.USERNAME;
    },

    get PASSWORD() {
        return currentConfig.PASSWORD;
    },

    // Portal配置
    get PORTAL_URL() {
        return currentConfig.PORTAL_URL;
    },

    // Token服务URL
    get TOKEN_URL() {
        return currentConfig.TOKEN_URL;
    },

    // 环境配置
    get ENV() {
        return currentConfig.ENV;
    },

    // 底图配置
    get GEOSCENE_LIGHT_BASEMAP() {
        return currentConfig.GEOSCENE_LIGHT_BASEMAP;
    },

    get GEOSCENE_DARK_BASEMAP() {
        return currentConfig.GEOSCENE_DARK_BASEMAP;
    },

    // 默认地图配置
    get GEOSCENE_DEFAULT_CENTER() {
        return currentConfig.GEOSCENE_DEFAULT_CENTER;
    },

    get GEOSCENE_DEFAULT_ZOOM() {
        return currentConfig.GEOSCENE_DEFAULT_ZOOM;
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
        if (config && config.geoscene) {
            currentConfig = {
                API_KEY: config.geoscene.apiKey || DEFAULT_CONFIG.API_KEY,
                AUTH_MODE: config.geoscene.authMode || DEFAULT_CONFIG.AUTH_MODE,
                USERNAME: config.geoscene.username || DEFAULT_CONFIG.USERNAME,
                PASSWORD: config.geoscene.password || DEFAULT_CONFIG.PASSWORD,
                PORTAL_URL: config.geoscene.portalUrl || DEFAULT_CONFIG.PORTAL_URL,
                TOKEN_URL: config.geoscene.tokenUrl || DEFAULT_CONFIG.TOKEN_URL,
                ENV: config.geoscene.env || DEFAULT_CONFIG.ENV,
                GEOSCENE_LIGHT_BASEMAP: config.geoscene.defaultBasemap || DEFAULT_CONFIG.GEOSCENE_LIGHT_BASEMAP,
                GEOSCENE_DARK_BASEMAP: "arcgis-dark-gray",
                GEOSCENE_DEFAULT_CENTER: config.geoscene.defaultCenter || DEFAULT_CONFIG.GEOSCENE_DEFAULT_CENTER,
                GEOSCENE_DEFAULT_ZOOM: config.geoscene.defaultZoom || DEFAULT_CONFIG.GEOSCENE_DEFAULT_ZOOM,
                VIEW_OPTIONS: DEFAULT_CONFIG.VIEW_OPTIONS
            };
            console.log('✅ GeoScene 配置已从后端更新');
        }
    },

    // Mock模式检测
    isMockMode() {
        if (this.AUTH_MODE === 'enterprise') {
            // Enterprise 模式下检查用户名密码是否有效
            return !this.USERNAME || !this.PASSWORD;
        }
        // API Key 模式
        if (!this.API_KEY || this.API_KEY === "YOUR_GEOSCENE_API_KEY_HERE") {
            return true;
        }
        return false;
    },

    // 获取配置信息
    getConfig() {
        if (this.isMockMode()) {
            console.warn("⚠️ GeoScene API Key 未配置，当前为 Mock 模式");
        }
        return {
            apiKey: this.API_KEY,
            authMode: this.AUTH_MODE,
            username: this.USERNAME,
            password: this.PASSWORD,
            portalUrl: this.PORTAL_URL,
            tokenUrl: this.TOKEN_URL,
            env: this.ENV,
            isMock: this.isMockMode()
        };
    }
};
