/**
 * 图层管理器
 * 管理GeoJSON采样点、预测栅格、方差栅格、不确定性指数图层
 * 支持图层开关、动态色带、点击查询
 * 使用适配器模式，支持多种地图引擎
 * 包含视口过滤、标记池复用、聚合提示等性能优化
 */

import { IMapAdapterExtended, MapView, MapGraphic, MapPoint } from '../types/app';
import { ILayerManager, LayerManagerConfig, ViewportBounds } from '../types/layer';
import { SamplingPoint, GeoJSONFeatureCollection } from '../types/core';

/** 默认配置 */
const DEFAULT_CONFIG: LayerManagerConfig = {
    maxVisibleMarkers: 50,
    enableViewportFilter: true,
    enableMarkerPooling: true,
    clusterThreshold: 0,
    autoRefresh: false
};

export class LayerManager implements ILayerManager {
    public adapter: IMapAdapterExtended;
    public view: MapView;
    public config: LayerManagerConfig;

    // 性能优化配置
    private readonly MAX_VISIBLE_MARKERS: number;
    private allMarkerData: SamplingPoint[] = []; // 所有标记数据
    private visibleGraphics: any[] = []; // 当前可见的 graphic 对象
    private graphicPool: any[] = []; // 标记对象池
    private clusterHint: HTMLElement | null = null; // 聚合提示元素
    private loadingIndicator: HTMLElement | null = null; // 加载提示元素
    private _viewChangeTimer: number | null = null;

    // 视口缓存（优化性能）
    private _viewportCache: {
        bounds: ViewportBounds | null;
        filteredPoints: SamplingPoint[];
        timestamp: number;
    } = {
        bounds: null,
        filteredPoints: [],
        timestamp: 0
    };

    private readonly CACHE_TTL: number = 300; // 缓存有效期300ms

    constructor(adapter: IMapAdapterExtended, config?: Partial<LayerManagerConfig>) {
        this.adapter = adapter;
        this.view = adapter.getView();

        // 应用配置
        this.config = { ...DEFAULT_CONFIG, ...config };
        this.MAX_VISIBLE_MARKERS = this.config.maxVisibleMarkers || 50;

        // 初始化加载指示器
        this._initLoadingIndicator();

        this.setupClickHandler((graphic, mapPoint) => this.showInfoPanel(graphic, mapPoint));
        this._setupViewportListener();
    }

    /**
     * 初始化加载指示器
     */
    private _initLoadingIndicator(): void {
        this.loadingIndicator = document.createElement('div');
        this.loadingIndicator.className = 'map-loading-indicator';
        this.loadingIndicator.innerHTML = '<div class="loading-spinner"></div><span>正在更新地图...</span>';
        this.loadingIndicator.style.cssText = `
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(255, 255, 255, 0.95);
            padding: 16px 24px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            display: none;
            z-index: 1000;
            font-size: 14px;
            color: #333;
            gap: 10px;
            align-items: center;
        `;

        const mapContainer = document.querySelector('.map-container');
        if (mapContainer) {
            mapContainer.appendChild(this.loadingIndicator);
        }

        // 添加加载动画样式
        const style = document.createElement('style');
        style.textContent = `
            .map-loading-indicator .loading-spinner {
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #3498db;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * 显示加载提示
     */
    private _showLoading(): void {
        if (this.loadingIndicator) {
            this.loadingIndicator.style.display = 'flex';
        }
    }

    /**
     * 隐藏加载提示
     */
    private _hideLoading(): void {
        if (this.loadingIndicator) {
            this.loadingIndicator.style.display = 'none';
        }
    }

    /**
     * 监听视口变化，节流刷新可见标记
     */
    private _setupViewportListener(): void {
        const view = this.view;
        if (!view) return;

        const onViewChange = () => {
            if (this._viewChangeTimer !== null) {
                clearTimeout(this._viewChangeTimer);
            }
            this._viewChangeTimer = window.setTimeout(() => {
                this._refreshVisibleMarkers();
            }, 200);
        };

        // ArcGIS MapView
        if (view.watch) {
            view.watch('extent', onViewChange);
            view.watch('zoom', onViewChange);
        }
        // 高德地图
        if (view.on && typeof view.getCenter === 'function') {
            view.on('moveend', onViewChange);
            view.on('zoomend', onViewChange);
        }
    }

    /**
     * 获取当前视口边界
     */
    private _getViewportBounds(): ViewportBounds | null {
        const view = this.view;

        // ArcGIS
        if (view.extent) {
            const ext = view.extent;
            return {
                minLng: ext.xmin,
                minLat: ext.ymin,
                maxLng: ext.xmax,
                maxLat: ext.ymax
            };
        }

        // 高德
        if (view.getBounds) {
            const bounds = view.getBounds();
            const sw = bounds.getSouthWest();
            const ne = bounds.getNorthEast();
            return {
                minLng: sw.lng,
                minLat: sw.lat,
                maxLng: ne.lng,
                maxLat: ne.lat
            };
        }

        return null;
    }

    /**
     * 判断点是否在视口内
     */
    private _isInViewport(point: SamplingPoint, bounds: ViewportBounds): boolean {
        if (!bounds) return true;
        return (
            point.x >= bounds.minLng &&
            point.x <= bounds.maxLng &&
            point.y >= bounds.minLat &&
            point.y <= bounds.maxLat
        );
    }

    /**
     * 刷新视口内可见标记（核心性能优化）
     */
    _refreshVisibleMarkers(): void {
        // 数量少，无需过滤
        if (this.allMarkerData.length <= this.MAX_VISIBLE_MARKERS) {
            this._updateClusterHint(0);
            return;
        }

        // 显示加载提示
        this._showLoading();

        // 使用 requestAnimationFrame 确保UI更新
        requestAnimationFrame(() => {
            const bounds = this._getViewportBounds();
            if (!bounds) {
                this._updateClusterHint(0);
                this._hideLoading();
                return;
            }

            // 检查缓存
            const now = Date.now();
            const cachedBounds = this._viewportCache.bounds;
            const isCacheValid =
                cachedBounds !== null &&
                Math.abs(cachedBounds.minLng - bounds.minLng) < 0.001 &&
                Math.abs(cachedBounds.maxLng - bounds.maxLng) < 0.001 &&
                Math.abs(cachedBounds.minLat - bounds.minLat) < 0.001 &&
                Math.abs(cachedBounds.maxLat - bounds.maxLat) < 0.001 &&
                (now - this._viewportCache.timestamp) < this.CACHE_TTL;

            let inView: SamplingPoint[];

            if (isCacheValid) {
                // 使用缓存数据
                inView = this._viewportCache.filteredPoints;
            } else {
                // 重新计算并更新缓存
                inView = this.allMarkerData.filter((p) =>
                    this._isInViewport(p, bounds)
                );
                this._viewportCache = {
                    bounds: bounds,
                    filteredPoints: inView,
                    timestamp: now
                };
            }

            // 超出限制时只显示前 N 个
            const toShow = inView.slice(0, this.MAX_VISIBLE_MARKERS);
            const hiddenCount = inView.length - toShow.length;

            // 回收当前可见标记到对象池
            this._recycleAllVisible();

            // 从池中取出或创建标记
            toShow.forEach((data) => {
                this._showMarkerFromPool(data);
            });

            this._updateClusterHint(hiddenCount);

            // 隐藏加载提示
            this._hideLoading();
        });
    }

    /**
     * 回收所有可见标记到对象池
     */
    private _recycleAllVisible(): void {
        this.visibleGraphics.forEach((g) => {
            if (this.adapter.graphicsLayer && this.adapter.graphicsLayer.remove) {
                this.adapter.graphicsLayer.remove(g);
            }
            this.graphicPool.push(g);
        });
        this.visibleGraphics = [];
    }

    /**
     * 从对象池取出标记并显示
     */
    private async _showMarkerFromPool(pointData: SamplingPoint): Promise<void> {
        // 直接通过适配器添加（适配器内部处理 graphic 创建）
        await this.adapter.addMarker(pointData);
    }

    /**
     * 更新聚合提示
     */
    _updateClusterHint(hiddenCount: number): void {
        if (!this.clusterHint) {
            this.clusterHint = document.createElement('div');
            this.clusterHint.className = 'cluster-hint';
            const mapContainer = document.querySelector('.map-container');
            if (mapContainer) {
                mapContainer.appendChild(this.clusterHint);
            }
        }

        if (hiddenCount > 0) {
            this.clusterHint.textContent = `视口内还有 ${hiddenCount} 个采样点未显示，请放大地图查看`;
            this.clusterHint.style.display = 'block';
        } else {
            this.clusterHint.style.display = 'none';
        }
    }

    /**
     * 添加GeoJSON采样点图层
     */
    async addPointsLayer(
        geojson: GeoJSONFeatureCollection,
        layerName?: string
    ): Promise<void> {
        await this.adapter.addPointsLayer(geojson, layerName || 'points');
    }

    /**
     * 添加栅格图层（预测或方差）
     */
    async addRasterLayer(type: 'prediction' | 'variance', url: string): Promise<void> {
        await this.adapter.addRasterLayer(type, url);
    }

    /**
     * 切换图层可见性
     */
    toggleLayer(layerName: string, visible: boolean): void {
        this.adapter.toggleLayer(layerName, visible);
    }

    /**
     * 设置图层透明度
     */
    setLayerOpacity(layerName: string, opacity: number): void {
        this.adapter.setLayerOpacity(layerName, opacity);
    }

    /**
     * 设置点击查询处理器
     */
    setupClickHandler(
        handler: (graphic: MapGraphic, mapPoint: MapPoint) => void
    ): void {
        this.adapter.setClickHandler(handler);
    }

    /**
     * 显示信息浮窗
     */
    showInfoPanel(graphic: MapGraphic, mapPoint: MapPoint): void {
        const infoPanel = document.getElementById('info-panel');
        const infoContent = document.getElementById('info-content');

        if (!infoPanel || !infoContent) return;

        let content = `<p><strong>坐标:</strong> ${mapPoint.longitude.toFixed(6)}, ${mapPoint.latitude.toFixed(6)}</p>`;

        if (graphic && graphic.attributes) {
            for (const [key, value] of Object.entries(graphic.attributes)) {
                if (key !== 'OBJECTID' && key !== 'FID') {
                    content += `<p><strong>${key}:</strong> ${value}</p>`;
                }
            }
        }

        infoContent.innerHTML = content;
        infoPanel.style.display = 'block';
    }

    /**
     * 隐藏信息浮窗
     */
    hideInfoPanel(): void {
        const infoPanel = document.getElementById('info-panel');
        if (infoPanel) {
            infoPanel.style.display = 'none';
        }
    }

    /**
     * 添加单个采样点（带性能优化）
     */
    async addSamplingPoint(pointData: SamplingPoint): Promise<void> {
        this.allMarkerData.push(pointData);

        // 数量未超限直接添加
        if (this.allMarkerData.length <= this.MAX_VISIBLE_MARKERS) {
            await this.adapter.addMarker(pointData);
        } else {
            // 超限后触发视口过滤
            this._refreshVisibleMarkers();
        }
    }

    /**
     * 添加单个标记
     */
    async addMarker(pointData: SamplingPoint): Promise<void> {
        await this.adapter.addMarker(pointData);
    }

    /**
     * 移除指定图层
     */
    removeLayer(layerName: string): void {
        this.adapter.removeLayer(layerName);
    }

    /**
     * 获取所有采样点数据
     */
    getSamplingPoints(): SamplingPoint[] {
        return this.adapter.getSamplingPoints();
    }

    /**
     * 移除所有图层
     */
    clearAllLayers(): void {
        this.allMarkerData = [];
        this.visibleGraphics = [];
        this.graphicPool = [];
        this._updateClusterHint(0);
        this.adapter.clearAllLayers();
    }
}

// 导出类型以供其他模块使用
export type { LayerManagerConfig, ViewportBounds };