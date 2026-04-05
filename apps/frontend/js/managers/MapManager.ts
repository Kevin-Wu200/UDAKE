import { GeoSceneEngine } from '../map/core/GeoSceneEngine';
import { AMapEngine } from '../map/core/AMapEngine';
import { offlineMapService, type OfflineMapDownloadProgress, type TileCoordinate } from '../map/services/OfflineMapService';
import { GeoUtils } from '../utils/GeoUtils';
import type {
    MapProvider,
    MapMode,
    MapManagerOptions
} from '../../types/sampling';
import type { GeoJSONFeatureCollection } from '../../types/core';
import type { BaseMapEngine } from '../../types/map-engine';

/**
 * 地图管理器
 * 负责创建和管理地图引擎，处理 reset 按钮和模式切换
 */
export class MapManager {
    /** 地图引擎 */
    mapEngine: BaseMapEngine | null;

    /** 当前地图引擎提供商 */
    currentProvider: MapProvider | null;

    /** 地图容器 ID */
    containerId: string | null;

    /** 初始中心点 */
    initialCenter: [number, number] | null;

    /** 初始缩放级别 */
    initialZoom: number | null;

    /** GeoJSON 数据 */
    geojson: GeoJSONFeatureCollection | null;

    /** 地图模式 */
    mode: MapMode;

    /** 重置按钮 */
    resetButton: HTMLElement | null;

    constructor() {
        this.mapEngine = null;
        this.currentProvider = null;
        this.containerId = null;
        this.initialCenter = null;
        this.initialZoom = null;
        this.geojson = null;
        this.mode = 'normal'; // 'normal' 或 'areaSampling'
        this.resetButton = null;
    }

    /**
     * 初始化地图
     * @param provider - 'geoscene' 或 'amap'
     * @param containerId - 容器 ID
     * @param options - 初始化选项
     */
    async init(provider: MapProvider, containerId: string, options: MapManagerOptions = {}): Promise<void> {
        // 保存容器 ID 和提供商
        this.containerId = containerId;
        this.currentProvider = provider;

        // 创建地图引擎
        if (provider === 'geoscene') {
            this.mapEngine = new GeoSceneEngine(options);
        } else if (provider === 'amap') {
            this.mapEngine = new AMapEngine(options);
        } else {
            throw new Error(`不支持的地图引擎: ${provider}`);
        }

        // 初始化地图
        await this.mapEngine.init(containerId, options);

        // 保存初始状态
        this.initialCenter = this.mapEngine.getCenter();
        this.initialZoom = this.mapEngine.getZoom();

        // 如果支持自定义 reset，创建 reset 按钮
        if (this.mapEngine.supportsCustomReset) {
            this.createResetButton(containerId);
        }

        console.log(`✅ MapManager 初始化完成，引擎: ${provider}`);
    }

    /**
     * 切换地图引擎
     * @param provider - 目标地图引擎 'geoscene' 或 'amap'
     * @param options - 初始化选项（可选）
     */
    async switchEngine(provider: MapProvider, options: MapManagerOptions = {}): Promise<void> {
        if (!this.containerId) {
            throw new Error('未找到地图容器 ID，无法切换引擎');
        }

        if (provider === this.currentProvider) {
            console.log(`当前已经是 ${provider} 引擎，无需切换`);
            return;
        }

        console.log(`🔄 开始切换地图引擎: ${this.currentProvider} -> ${provider}`);

        // 保存当前状态
        const currentCenter = this.mapEngine ? this.mapEngine.getCenter() : this.initialCenter;
        const currentZoom = this.mapEngine ? this.mapEngine.getZoom() : this.initialZoom;
        const currentMode = this.mode;
        const currentGeojson = this.geojson;

        // 销毁旧引擎
        if (this.mapEngine) {
            this.mapEngine.destroy();
            this.mapEngine = null;
        }

        // 移除旧的 reset 按钮
        if (this.resetButton && this.resetButton.parentNode) {
            this.resetButton.parentNode.removeChild(this.resetButton);
            this.resetButton = null;
        }

        // 创建新引擎
        try {
            const mergedOptions = {
                ...options,
                center: currentCenter ?? undefined,
                zoom: currentZoom ?? undefined
            };

            await this.init(provider, this.containerId, mergedOptions);

            // 恢复模式
            if (currentMode === 'areaSampling' && currentGeojson) {
                this.enterAreaSamplingMode(currentGeojson);
            }

            console.log(`✅ 地图引擎切换完成: ${provider}`);
        } catch (error) {
            console.error('❌ 地图引擎切换失败:', error);
            // 尝试恢复到旧引擎
            if (this.currentProvider) {
                console.log(`🔄 尝试恢复到原引擎: ${this.currentProvider}`);
                await this.init(this.currentProvider, this.containerId, {
                    center: currentCenter ?? undefined,
                    zoom: currentZoom ?? undefined
                });
                if (currentMode === 'areaSampling' && currentGeojson) {
                    this.enterAreaSamplingMode(currentGeojson);
                }
            }
            throw error;
        }
    }

    /**
     * 获取当前地图引擎提供商
     */
    getProvider(): MapProvider | null {
        return this.currentProvider;
    }

    /**
     * 创建 reset 按钮
     */
    protected createResetButton(containerId: string | HTMLElement): void {
        const container = typeof containerId === 'string'
            ? document.getElementById(containerId)
            : containerId;

        if (!container) return;

        // 创建按钮
        this.resetButton = document.createElement('div');
        this.resetButton.className = 'map-reset-btn';
        this.resetButton.innerHTML = '⟲';
        this.resetButton.title = '重置视图';

        // 样式
        this.resetButton.style.cssText = `
            position: absolute;
            top: 10px;
            right: 10px;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.9);
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 20px;
            color: #333;
            z-index: 1000;
            transition: all 0.2s;
        `;

        // Hover 效果
        this.resetButton.addEventListener('mouseenter', () => {
            if (this.resetButton) {
                this.resetButton.style.background = 'rgba(255, 255, 255, 1)';
                this.resetButton.style.transform = 'scale(1.1)';
            }
        });

        this.resetButton.addEventListener('mouseleave', () => {
            if (this.resetButton) {
                this.resetButton.style.background = 'rgba(255, 255, 255, 0.9)';
                this.resetButton.style.transform = 'scale(1)';
            }
        });

        // 点击事件
        this.resetButton.addEventListener('click', () => {
            this.handleReset();
        });

        container.appendChild(this.resetButton);
    }

    /**
     * 处理 reset 按钮点击
     */
    protected handleReset(): void {
        if (!this.mapEngine) return;

        if (this.mode === 'normal') {
            // 普通模式：回到初始位置
            this.mapEngine.setCenter(this.initialCenter!);
            this.mapEngine.setZoom(this.initialZoom!);
        } else if (this.mode === 'areaSampling' && this.geojson) {
            // 区域采样模式：适配 GeoJSON 范围
            try {
                const bounds = GeoUtils.calculateBoundsFromGeoJSON(this.geojson);
                const expandedBounds = GeoUtils.expandBounds(bounds, 0.1);
                this.mapEngine.fitToBounds(expandedBounds);
            } catch (error) {
                console.error('适配 GeoJSON 范围失败:', error);
                // 回退到初始位置
                this.mapEngine.setCenter(this.initialCenter!);
                this.mapEngine.setZoom(this.initialZoom!);
            }
        }
    }

    /**
     * 切换到区域采样模式
     * @param geojson - GeoJSON 数据
     */
    enterAreaSamplingMode(geojson: GeoJSONFeatureCollection): void {
        this.mode = 'areaSampling';
        this.geojson = geojson;

        if (!this.mapEngine) return;

        // 自动适配到 GeoJSON 范围
        try {
            const bounds = GeoUtils.calculateBoundsFromGeoJSON(geojson);
            const expandedBounds = GeoUtils.expandBounds(bounds, 0.1);
            this.mapEngine.fitToBounds(expandedBounds);
        } catch (error) {
            console.error('适配 GeoJSON 范围失败:', error);
        }
    }

    /**
     * 切换到普通模式
     */
    enterNormalMode(): void {
        this.mode = 'normal';
        this.geojson = null;
    }

    /**
     * 获取地图引擎
     */
    getEngine(): BaseMapEngine | null {
        return this.mapEngine;
    }

    /**
     * 销毁
     */
    destroy(): void {
        if (this.resetButton && this.resetButton.parentNode) {
            this.resetButton.parentNode.removeChild(this.resetButton);
        }

        if (this.mapEngine) {
            this.mapEngine.destroy();
        }
    }

    /**
     * 创建离线地图下载任务（矩形区域）
     */
    async createOfflineMapTask(
        params: {
            name: string;
            bbox: [number, number, number, number];
            minZoom: number;
            maxZoom: number;
            version?: string;
            tileTemplate?: string;
        },
        onProgress?: (progress: OfflineMapDownloadProgress) => void
    ): Promise<string> {
        return offlineMapService.createRegionDownloadTask(params, onProgress);
    }

    /**
     * 暂停离线地图下载任务
     */
    pauseOfflineMapTask(taskId: string): boolean {
        return offlineMapService.pauseTask(taskId);
    }

    /**
     * 恢复离线地图下载任务
     */
    async resumeOfflineMapTask(taskId: string): Promise<boolean> {
        return offlineMapService.resumeTask(taskId);
    }

    /**
     * 获取离线地图存储统计
     */
    async getOfflineMapStorageStats(): Promise<{
        totalTiles: number;
        totalBytes: number;
        maxBytes: number;
        usageRate: number;
        memoryHitRate: number;
        memoryHits: number;
        diskHits: number;
        misses: number;
    }> {
        return offlineMapService.getStorageStats();
    }

    /**
     * 从离线缓存读取瓦片
     */
    async getOfflineTile(tile: TileCoordinate, version: string = 'v1'): Promise<Blob | null> {
        return offlineMapService.getTile(tile, version);
    }
}
