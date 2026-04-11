/**
 * 地图初始化模块
 * 使用 ArcGIS API for JavaScript
 */

import { IMapAdapter } from '../types/map';
import { MapConfig } from './config/map.config.js';
import { AppConfig } from './config/AppConfig.js';
import { Logger } from './utils/Logger.js';
import {
    ensureMapEngineRegistryReady,
    getMapEngine,
    getRegisteredMapEngines,
    validateMapProvider,
    type MapProvider
} from './map/MapEngineRegistry.js';

/**
 * 地图引擎初始化超时
 */
const MAP_INIT_TIMEOUT_MS = AppConfig.map.initTimeoutMs;

function withTimeout<T>(promise: Promise<T>, provider: MapProvider): Promise<T> {
    return Promise.race([
        promise,
        new Promise<never>((_, reject) => {
            setTimeout(
                () => reject(new Error(`地图引擎初始化超时(${Math.floor(MAP_INIT_TIMEOUT_MS / 1000)}秒): ${provider}`)),
                MAP_INIT_TIMEOUT_MS
            );
        })
    ]);
}

async function createAdapterAndInitialize(containerId: string, provider: MapProvider): Promise<IMapAdapter> {
    const engine = getMapEngine(provider);
    if (!engine) {
        throw new Error(`未注册的地图引擎: ${provider}`);
    }

    const adapter = await engine.createAdapter();
    await withTimeout(adapter.initMap(containerId), provider);
    return adapter;
}

async function syncProvidersToConfig(): Promise<void> {
    await ensureMapEngineRegistryReady();
    MapConfig.registerProviders(getRegisteredMapEngines().map((engine) => engine.provider));
}

/**
 * 初始化地图
 * 使用 ArcGIS API for JavaScript 或高德地图
 * @param containerId - 地图容器 ID
 * @returns 地图适配器实例
 */
export async function initializeMap(containerId: string): Promise<IMapAdapter> {
    await syncProvidersToConfig();

    const fallbackProvider = MapConfig.FALLBACK_PROVIDER || 'geoscene';
    const requestedProvider = MapConfig.getProvider();
    const provider = validateMapProvider(requestedProvider, fallbackProvider);
    Logger.info('地图初始化', `使用地图引擎: ${provider}`);

    try {
        const adapter = await createAdapterAndInitialize(containerId, provider);
        MapConfig.setProvider(provider);
        return adapter;
    } catch (error) {
        if (provider === fallbackProvider) {
            throw error;
        }

        Logger.warn('地图初始化', `引擎 ${provider} 初始化失败，回退到 ${fallbackProvider}`);
        const fallbackAdapter = await createAdapterAndInitialize(containerId, fallbackProvider);
        MapConfig.setProvider(fallbackProvider);
        return fallbackAdapter;
    }
}

/**
 * 获取当前地图引擎类型
 * @returns 'geoscene' 或 'amap'
 */
export async function getMapProvider(): Promise<MapProvider> {
    await syncProvidersToConfig();
    const provider = validateMapProvider(MapConfig.getProvider(), MapConfig.FALLBACK_PROVIDER || 'geoscene');
    MapConfig.setProvider(provider);
    return provider;
}

/**
 * 获取可用地图引擎列表
 */
export async function getAvailableMapProviders(): Promise<Array<{ provider: MapProvider; displayName: string }>> {
    await syncProvidersToConfig();
    return getRegisteredMapEngines().map((engine) => ({
        provider: engine.provider,
        displayName: engine.displayName
    }));
}

/**
 * 重新初始化地图（切换引擎后使用）
 * @param containerId - 地图容器 ID
 * @param provider - 目标地图引擎
 */
export async function reinitializeMap(
    containerId: string,
    provider: MapProvider
): Promise<IMapAdapter> {
    await syncProvidersToConfig();

    const fallbackProvider = MapConfig.FALLBACK_PROVIDER || 'geoscene';
    const targetProvider = validateMapProvider(provider, fallbackProvider);
    Logger.info('地图初始化', `重新初始化地图，使用引擎: ${targetProvider}`);

    try {
        const adapter = await createAdapterAndInitialize(containerId, targetProvider);
        MapConfig.setProvider(targetProvider);
        return adapter;
    } catch (error) {
        if (targetProvider === fallbackProvider) {
            throw error;
        }

        Logger.warn('地图初始化', `引擎 ${targetProvider} 初始化失败，回退到 ${fallbackProvider}`);
        const fallbackAdapter = await createAdapterAndInitialize(containerId, fallbackProvider);
        MapConfig.setProvider(fallbackProvider);
        return fallbackAdapter;
    }
}
