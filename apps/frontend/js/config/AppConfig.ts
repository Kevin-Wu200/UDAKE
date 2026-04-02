/**
 * 统一运行时配置
 */

export interface RuntimeAppConfig {
    map: {
        initTimeoutMs: number;
        switchTimeoutMs: number;
    };
    api: {
        version: string;
        versionHeader: string;
    };
    features: {
        enableBehaviorTracking: boolean;
    };
}

function readEnv(key: string): string | undefined {
    try {
        const env = (import.meta as ImportMeta & { env?: Record<string, string> }).env;
        if (!env) {
            return undefined;
        }
        return env[key];
    } catch {
        return undefined;
    }
}

function parseNumber(value: string | undefined, fallback: number): number {
    if (!value) {
        return fallback;
    }
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function parseBoolean(value: string | undefined, fallback: boolean): boolean {
    if (value === undefined) {
        return fallback;
    }
    return value === 'true';
}

function parseStringList(value: string | undefined, fallback: string[]): string[] {
    if (!value) {
        return fallback;
    }
    try {
        const parsed = JSON.parse(value) as unknown;
        if (Array.isArray(parsed)) {
            return parsed.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
        }
    } catch {
        return value
            .split(',')
            .map(item => item.trim())
            .filter(Boolean);
    }
    return fallback;
}

function resolveFrontendUrl(): string {
    return readEnv('VITE_FRONTEND_URL')
        || `http://${readEnv('VITE_IPCONFIG') || 'localhost'}:${readEnv('VITE_FRONTEND_PORT') || readEnv('FRONTEND_PORT') || '5173'}`;
}

export const AppConfig: RuntimeAppConfig = {
    map: {
        initTimeoutMs: parseNumber(readEnv('VITE_MAP_INIT_TIMEOUT_MS'), 15000),
        switchTimeoutMs: parseNumber(readEnv('VITE_MAP_SWITCH_TIMEOUT_MS'), 12000)
    },
    api: {
        version: readEnv('VITE_API_VERSION') || '2026-03',
        versionHeader: readEnv('VITE_API_VERSION_HEADER') || 'X-API-Version'
    },
    features: {
        enableBehaviorTracking: parseBoolean(readEnv('VITE_ENABLE_BEHAVIOR_TRACKING'), true)
    }
};

export const DEFAULT_MAP_CONFIG = {
    geoscene: {
        apiKey: 'YOUR_ARCGIS_API_KEY_HERE',
        portalUrl: 'https://www.arcgis.com',
        env: 'development',
        defaultBasemap: 'arcgis-topographic',
        defaultCenter: [139.767125, 35.681236] as [number, number],
        defaultZoom: 10,
        isMock: true
    },
    amap: {
        apiKey: 'YOUR_AMAP_API_KEY_HERE',
        securityCode: null as string | null,
        defaultCenter: [119.72170376, 30.26262781] as [number, number],
        defaultZoom: 18
    },
    tianditu: {
        apiKey: 'YOUR_TIANDITU_API_KEY_HERE',
        token: null as string | null
    }
};

export const DEFAULT_APP_LIMITS = {
    appName: '智能不确定性驱动空间决策平台',
    version: '1.0.0',
    debug: true,
    corsOrigins: parseStringList(readEnv('VITE_CORS_ORIGINS'), [resolveFrontendUrl()]),
    maxFileSize: 100,
    maxConcurrentTasks: 5,
    taskTimeout: 3600
};

export const DEFAULT_AI_CONFIG = {
    cacheEnabled: true,
    maxBatchSize: 100,
    modelPath: null as string | null
};
