/**
 * 地图初始化模块
 * 使用 ArcGIS API for JavaScript
 */

import { IMapAdapter } from '../types/map';
import { MapEngineType } from '../types/core';

// 动态导入配置和适配器
async function importConfig() {
    return import('./config/map.config.js');
}

async function importAdapters() {
    const ArcGISAdapter = await import('./adapters/ArcGISAdapter.js');
    const AMapAdapter = await import('./adapters/AMapAdapter.js');
    return { ArcGISAdapter, AMapAdapter };
}

/**
 * 地图引擎提供商类型
 */
export type MapProvider = 'arcgis' | 'amap';

/**
 * 初始化地图
 * 使用 ArcGIS API for JavaScript 或高德地图
 * @param containerId - 地图容器 ID
 * @returns 地图适配器实例
 */
export async function initializeMap(containerId: string): Promise<IMapAdapter> {
    // 动态导入依赖
    const { MapConfig } = await importConfig();
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

    await adapter.initMap(containerId);

    return adapter;
}

/**
 * 获取当前地图引擎类型
 * @returns 'arcgis' 或 'amap'
 */
export async function getMapProvider(): Promise<MapProvider> {
    const { MapConfig } = await importConfig();
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

    await adapter.initMap(containerId);

    return adapter;
}