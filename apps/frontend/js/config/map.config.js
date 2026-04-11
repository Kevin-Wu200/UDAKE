/**
 * 地图引擎配置文件
 *
 * 目标：
 * 1. 支持运行时注册更多地图引擎；
 * 2. 支持从环境变量读取默认引擎；
 * 3. 在非法配置时自动回退到稳定引擎。
 */

const FALLBACK_PROVIDER = 'geoscene';
const DEFAULT_PROVIDER_FROM_ENV = String(import.meta.env.VITE_MAP_PROVIDER || '').trim().toLowerCase();

const providerLabels = new Map([
    ['geoscene', 'GeoScene'],
    ['amap', '高德']
]);

const registeredProviders = new Set(['geoscene', 'amap']);
if (DEFAULT_PROVIDER_FROM_ENV) {
    registeredProviders.add(DEFAULT_PROVIDER_FROM_ENV);
}

function normalizeProvider(provider) {
    return String(provider || '').trim().toLowerCase();
}

function resolveInitialProvider() {
    if (DEFAULT_PROVIDER_FROM_ENV && registeredProviders.has(DEFAULT_PROVIDER_FROM_ENV)) {
        return DEFAULT_PROVIDER_FROM_ENV;
    }
    return FALLBACK_PROVIDER;
}

export const MapConfig = {
    FALLBACK_PROVIDER,
    MAP_PROVIDER: resolveInitialProvider(),

    // 注册单个引擎类型
    registerProvider(provider, displayName) {
        const normalized = normalizeProvider(provider);
        if (!normalized) {
            return null;
        }

        registeredProviders.add(normalized);
        if (displayName) {
            providerLabels.set(normalized, displayName);
        }
        return normalized;
    },

    // 批量注册引擎类型
    registerProviders(providers = []) {
        for (const provider of providers) {
            this.registerProvider(provider);
        }
    },

    // 获取可用引擎列表
    getAvailableProviders() {
        return Array.from(registeredProviders);
    },

    // 获取引擎显示名称
    getProviderLabel(provider) {
        const normalized = normalizeProvider(provider);
        return providerLabels.get(normalized) || normalized || FALLBACK_PROVIDER;
    },

    // 获取当前引擎（若非法则自动回退）
    getProvider() {
        const current = normalizeProvider(this.MAP_PROVIDER);
        if (!current || !registeredProviders.has(current)) {
            this.MAP_PROVIDER = FALLBACK_PROVIDER;
            return FALLBACK_PROVIDER;
        }
        return current;
    },

    // 设置当前引擎（非法输入时回退）
    setProvider(provider) {
        const normalized = normalizeProvider(provider);
        if (!normalized) {
            this.MAP_PROVIDER = FALLBACK_PROVIDER;
            return this.MAP_PROVIDER;
        }

        if (!registeredProviders.has(normalized)) {
            console.warn(`[MapConfig] 未注册的地图引擎: ${normalized}，回退到 ${FALLBACK_PROVIDER}`);
            this.MAP_PROVIDER = FALLBACK_PROVIDER;
            return this.MAP_PROVIDER;
        }

        this.MAP_PROVIDER = normalized;
        return this.MAP_PROVIDER;
    },

    // 检查引擎是否已注册
    isProviderSupported(provider) {
        const normalized = normalizeProvider(provider);
        return Boolean(normalized) && registeredProviders.has(normalized);
    },

    isGeoScene() {
        return this.getProvider() === 'geoscene';
    },

    isAMap() {
        return this.getProvider() === 'amap';
    }
};
