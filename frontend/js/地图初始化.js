import { MapConfig } from './config/map.config.js';
import { ArcGISAdapter } from './adapters/ArcGISAdapter.js';
import { AMapAdapter } from './adapters/AMapAdapter.js';

/**
 * 初始化地图
 * 根据配置自动选择地图引擎（ArcGIS 或高德地图）
 * @param {string} containerId - 地图容器 ID
 * @returns {Promise<MapAdapter>} 地图适配器实例
 */
export async function initializeMap(containerId) {
    const provider = MapConfig.getProvider();
    console.log(`🗺️ 使用地图引擎: ${provider}`);

    let adapter;

    if (provider === 'arcgis') {
        adapter = new ArcGISAdapter();
    } else if (provider === 'amap') {
        adapter = new AMapAdapter();
    } else {
        throw new Error(`不支持的地图引擎: ${provider}`);
    }

    await adapter.initMap(containerId);

    return adapter;
}

/**
 * 获取当前地图引擎类型
 * @returns {string} 'arcgis' 或 'amap'
 */
export function getMapProvider() {
    return MapConfig.getProvider();
}
