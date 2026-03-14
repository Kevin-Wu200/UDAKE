/**
 * 地图引擎集成模块
 * 展示如何使用 MapManager 和 ZoomControl
 */

import { IMapEngine } from '../types/map';
import { GeoJSONFeature } from '../types/core';

/** 初始化选项接口 */
interface InitializeMapOptions {
    center?: [number, number];
    zoom?: number;
    minZoom?: number;
    maxZoom?: number;
}

/** 初始化结果接口 */
interface InitializeMapResult {
    manager: any;
    zoomControl: any;
    engine: IMapEngine;
}

/** MapManager 接口（简化版） */
interface IMapManager {
    init(provider: string, containerId: string, options?: InitializeMapOptions): Promise<void>;
    getEngine(): IMapEngine;
    enterAreaSamplingMode(geojson: GeoJSONFeature): void;
    enterNormalMode(): void;
}

/** ZoomControl 接口（简化版） */
interface IZoomControl {
    create(containerId: string): void;
}

// 动态导入依赖
async function importManagersAndControls() {
    const [MapManagerModule, ZoomControlModule, MapConfigModule] = await Promise.all([
        import('./managers/MapManager.js'),
        import('./components/ZoomControl.js'),
        import('./config/map.config.js')
    ]);
    return {
        MapManager: MapManagerModule.MapManager,
        ZoomControl: ZoomControlModule.ZoomControl,
        MapConfig: MapConfigModule.MapConfig
    };
}

/**
 * 使用新引擎架构初始化地图
 * @param containerId - 容器 ID
 * @param options - 初始化选项
 * @returns {manager, zoomControl, engine}
 */
export async function initializeMapWithEngine(
    containerId: string,
    options: InitializeMapOptions = {}
): Promise<InitializeMapResult> {
    const { MapManager, ZoomControl, MapConfig } = await importManagersAndControls();

    const provider = MapConfig.getProvider();
    console.log(`🗺️ 使用地图引擎: ${provider}`);

    // 创建 MapManager
    const manager: IMapManager = new MapManager() as any;

    // 初始化地图
    await manager.init(provider, containerId, options);

    // 创建缩放控件
    const zoomControl: IZoomControl = new ZoomControl(manager.getEngine(), {
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
 * @param manager - MapManager 实例
 * @param geojson - GeoJSON 数据
 */
export function enterAreaSamplingMode(manager: IMapManager, geojson: GeoJSONFeature): void {
    manager.enterAreaSamplingMode(geojson);
    console.log('✅ 已进入区域采样模式');
}

/**
 * 示例：退出区域采样模式
 * @param manager - MapManager 实例
 */
export function exitAreaSamplingMode(manager: IMapManager): void {
    manager.enterNormalMode();
    console.log('✅ 已退出区域采样模式');
}

// 导出类型
export type { InitializeMapOptions, InitializeMapResult };