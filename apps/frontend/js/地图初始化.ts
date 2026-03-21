/**
 * 地图初始化模块
 * 使用 ArcGIS API for JavaScript
 */

import { IMapAdapter } from '../types/map';
import { MapEngineType } from '../types/core';
import { MapConfig } from './config/map.config.js';

// 动态导入适配器（保留动态导入，因为适配器较大且按需加载）
async function importAdapters() {
    const ArcGISAdapter = await import('./adapters/ArcGISAdapter.js');
    const AMapAdapter = await import('./adapters/AMapAdapter.js');
    return { ArcGISAdapter, AMapAdapter };
}

/**
 * 地图引擎提供商类型
 */
export type MapProvider = 'arcgis' | 'amap';
const MAP_INIT_TIMEOUT_MS = 20000;

function withTimeout<T>(promise: Promise<T>, provider: MapProvider): Promise<T> {
    return Promise.race([
        promise,
        new Promise<never>((_, reject) => {
            setTimeout(() => reject(new Error(`地图引擎初始化超时: ${provider}`)), MAP_INIT_TIMEOUT_MS);
        })
    ]);
}

/**
 * 初始化地图
 * 使用 ArcGIS API for JavaScript 或高德地图
 * @param containerId - 地图容器 ID
 * @returns 地图适配器实例
 */
export async function initializeMap(containerId: string): Promise<IMapAdapter> {
    // 动态导入适配器
    const { ArcGISAdapter, AMapAdapter } = await importAdapters();

    // 获取地图引擎提供商
    const provider: MapProvider = MapConfig.getProvider() as MapProvider;
    console.log(`🗺️ 使用地图引擎: ${provider}`);

    let adapter: IMapAdapter;

    switch (provider) {
        case 'arcgis':
            adapter = new ArcGISAdapter.ArcGISAdapter();
            break;
        case 'amap':
            adapter = new AMapAdapter.AMapAdapter();
            break;
        default:
            throw new Error(`不支持的地图引擎: ${provider}`);
    }

    await withTimeout(adapter.initMap(containerId), provider);

    return adapter;
}

/**
 * 获取当前地图引擎类型
 * @returns 'arcgis' 或 'amap'
 */
export async function getMapProvider(): Promise<MapProvider> {
    const provider = MapConfig.getProvider() as MapProvider;

    if (provider !== 'arcgis' && provider !== 'amap') {
        throw new Error(`无效的地图引擎: ${provider}`);
    }

    return provider;
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
    console.log(`🔄 重新初始化地图，使用引擎: ${provider}`);

    const { ArcGISAdapter, AMapAdapter } = await importAdapters();

    let adapter: IMapAdapter;

    switch (provider) {
        case 'arcgis':
            adapter = new ArcGISAdapter.ArcGISAdapter();
            break;
        case 'amap':
            adapter = new AMapAdapter.AMapAdapter();
            break;
        default:
            throw new Error(`不支持的地图引擎: ${provider}`);
    }

    await withTimeout(adapter.initMap(containerId), provider);

    return adapter;
}
