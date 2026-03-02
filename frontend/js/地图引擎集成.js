/**
 * 地图引擎集成示例
 * 展示如何使用 MapManager 和 ZoomControl
 */

import { MapManager } from './managers/MapManager.js';
import { ZoomControl } from './components/ZoomControl.js';
import { MapConfig } from './config/map.config.js';

/**
 * 使用新引擎架构初始化地图
 * @param {string} containerId - 容器 ID
 * @param {Object} options - 初始化选项
 * @returns {Promise<Object>} {manager, zoomControl}
 */
export async function initializeMapWithEngine(containerId, options = {}) {
    const provider = MapConfig.getProvider();
    console.log(`🗺️ 使用地图引擎: ${provider}`);

    // 创建 MapManager
    const manager = new MapManager();

    // 初始化地图
    await manager.init(provider, containerId, options);

    // 创建缩放控件
    const zoomControl = new ZoomControl(manager.getEngine(), {
        minZoom: options.minZoom || 1,
        maxZoom: options.maxZoom || 18
    });
    zoomControl.create(containerId);

    console.log('✅ 地图引擎集成完成');

    return {
        manager,
        zoomControl,
        engine: manager.getEngine()
    };
}

/**
 * 示例：进入区域采样模式
 * @param {MapManager} manager - MapManager 实例
 * @param {Object} geojson - GeoJSON 数据
 */
export function enterAreaSamplingMode(manager, geojson) {
    manager.enterAreaSamplingMode(geojson);
    console.log('✅ 已进入区域采样模式');
}

/**
 * 示例：退出区域采样模式
 * @param {MapManager} manager - MapManager 实例
 */
export function exitAreaSamplingMode(manager) {
    manager.enterNormalMode();
    console.log('✅ 已退出区域采样模式');
}
