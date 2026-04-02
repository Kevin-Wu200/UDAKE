/**
 * ArcGIS 地图适配器
 * 使用 ArcGISEngine，封装 ArcGIS API for JavaScript 的地图操作
 */

import { MapAdapter } from './MapAdapter';
import { ArcGISConfig } from '../config/geoscene.config';
import { ArcGISEngine } from '../map/core/ArcGISEngine';
import { MockMapEngine } from '../map/core/MockMapEngine';
import type {
    GeoJSONFeatureCollection,
    SamplingPoint,
    PolygonStyleOptions
} from '../../types/core';
import type {
    AdapterOptions,
    ArcGISLayerStore,
    GraphicsLayer,
    ClickHandler
} from '../../types/adapter';
import type { BaseMapEngine } from '../../types/map-engine';

/**
 * ArcGIS 地图适配器
 * 使用 ArcGISEngine 或 MockMapEngine，封装地图操作
 */
export class ArcGISAdapter extends MapAdapter {
    /** 地图引擎 */
    engine: ArcGISEngine | MockMapEngine | null;

    /** 是否使用 Mock 模式 */
    isMock: boolean;

    /** ArcGIS 视图 */
    view: any;

    /** ArcGIS 地图 */
    map: any;

    /** 图层存储 */
    layers: ArcGISLayerStore;

    /** 图形图层 */
    graphicsLayer: GraphicsLayer | null;

    /** 采样点列表 */
    samplingPoints: SamplingPoint[];

    constructor() {
        super();

        // 根据配置选择引擎
        const config = ArcGISConfig.getConfig();
        this.isMock = config.isMock;
        this.engine = null;

        this.view = null;
        this.map = null;
        this.layers = {};
        this.graphicsLayer = null;
        this.samplingPoints = [];

        console.log(`🗺️ 地图模式: ${this.isMock ? 'Mock 模式' : 'GeoScene 模式'}`);
    }

    /**
     * 初始化地图
     * 根据 isMock 标志选择使用 ArcGISEngine 或 MockMapEngine
     */
    async initMap(containerId: string, _options?: AdapterOptions): Promise<any> {
        // 初始化 ArcGIS 配置
        const config = ArcGISConfig.getConfig();

        if (this.isMock) {
            // 使用 Mock 引擎
            console.log('🗺️ 使用 Mock 地图引擎');
            this.engine = new MockMapEngine({
                center: ArcGISConfig.GEOSCENE_DEFAULT_CENTER as any,
                zoom: ArcGISConfig.GEOSCENE_DEFAULT_ZOOM,
                minZoom: ArcGISConfig.VIEW_OPTIONS.constraints.minZoom,
                maxZoom: ArcGISConfig.VIEW_OPTIONS.constraints.maxZoom
            });

            // 初始化引擎
            await this.engine.init(containerId);

            // 获取 view 和 map 引用
            this.view = this.engine.getView();
            this.map = this.engine.map;

            console.log('✅ Mock 地图初始化完成');

            return this.view;
        } else {
            // 使用 ArcGIS 引擎
            console.log('🗺️ 使用 GeoScene 地图引擎');

            // 设置 GeoScene 配置
            try {
                // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
                const esriConfig: any = await import('@geoscene/core/config');
                (esriConfig.default as any).apiKey = config.apiKey;
                (esriConfig.default as any).portalUrl = config.portalUrl;
            } catch (error) {
                console.warn('GeoScene 配置设置失败，使用默认配置', error);
            }

            // 创建 ArcGISEngine
            this.engine = new ArcGISEngine({
                center: ArcGISConfig.GEOSCENE_DEFAULT_CENTER as any,
                zoom: ArcGISConfig.GEOSCENE_DEFAULT_ZOOM,
                minZoom: ArcGISConfig.VIEW_OPTIONS.constraints.minZoom,
                maxZoom: ArcGISConfig.VIEW_OPTIONS.constraints.maxZoom
            });

            // 初始化引擎
            await this.engine.init(containerId);

            // 获取 view 和 map 引用
            this.view = this.engine.getView();
            this.map = this.engine.map;

            // 初始化 Graphics 图层
            await this.initGraphicsLayer();

            console.log('✅ GeoScene 地图初始化完成');

            return this.view;
        }
    }

    /**
     * 初始化 Graphics 图层
     */
    async initGraphicsLayer(): Promise<void> {
        if (this.isMock) {
            // Mock 模式下不需要 GraphicsLayer
            console.log('Mock 模式：跳过 GraphicsLayer 初始化');
            return;
        }

        // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
        const GraphicsLayer: any = (await import('@geoscene/core/layers/GraphicsLayer')).default;
        this.graphicsLayer = new GraphicsLayer({
            title: '手动采样点'
        }) as any;
        this.map.add(this.graphicsLayer);
    }

    getView(): any {
        return this.view;
    }

    /**
     * 获取引擎实例
     */
    getEngine(): BaseMapEngine | null {
        return this.engine;
    }

    /**
     * 添加 GeoJSON 点图层
     */
    async addPointsLayer(geojson: GeoJSONFeatureCollection, layerName: string = 'points'): Promise<void> {
        if (this.isMock) {
            // Mock 模式下简化实现
            console.log(`Mock 模式：添加 ${geojson.features.length} 个采样点`);
            // 在 Mock 模式下，我们只是记录日志，不实际添加图层
            return;
        }

        try {
            const [GeoJSONLayer]: [any] = await Promise.all([
                // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
                import('@geoscene/core/layers/GeoJSONLayer').then((m: any) => m.default)
            ]);

            // 创建 Blob URL
            const blob = new Blob([JSON.stringify(geojson)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);

            const layer = new GeoJSONLayer({
                url: url,
                title: '采样点',
                renderer: {
                    type: 'simple',
                    symbol: {
                        type: 'simple-marker',
                        color: [0, 122, 255, 0.8],
                        size: 8,
                        outline: {
                            color: [255, 255, 255],
                            width: 2
                        }
                    }
                },
                popupTemplate: {
                    title: '采样点',
                    content: '{*}'
                }
            });

            this.map.add(layer);
            this.layers[layerName] = layer;

            await layer.when();
            this.view.goTo(layer.fullExtent);
            console.log('✅ 采样点图层加载完成');
        } catch (error) {
            console.error('❌ 加载采样点失败:', error);
            throw error;
        }
    }

    /**
     * 添加栅格图层
     */
    async addRasterLayer(type: 'prediction' | 'variance', url: string): Promise<void> {
        if (this.isMock) {
            // Mock 模式下简化实现
            console.log(`Mock 模式：添加 ${type === 'prediction' ? '预测' : '方差'}栅格图层`);
            // 在 Mock 模式下，我们只是记录日志，不实际添加图层
            return;
        }

        try {
            const [ImageryLayer]: [any] = await Promise.all([
                // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
                import('@geoscene/core/layers/ImageryLayer').then((m: any) => m.default)
            ]);

            // 移除旧图层
            if (this.layers[type]) {
                this.map.remove(this.layers[type]);
            }

            const layer = new ImageryLayer({
                url: url,
                title: type === 'prediction' ? '预测栅格' : '方差栅格',
                opacity: 0.7
            });

            this.map.add(layer);
            this.layers[type] = layer;

            await layer.when();
            console.log(`✅ ${type}栅格图层加载完成`);
        } catch (error) {
            console.error(`❌ 加载${type}栅格失败:`, error);
            throw error;
        }
    }

    /**
     * 添加单个采样点
     */
    async addMarker(pointData: SamplingPoint): Promise<void> {
        if (this.isMock) {
            // Mock 模式下简化实现
            console.log(`Mock 模式：添加采样点 (${pointData.x}, ${pointData.y})`);
            this.samplingPoints.push(pointData);
            return;
        }

        const [Graphic, Point, SimpleMarkerSymbol]: [any, any, any] = await Promise.all([
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            import('@geoscene/core/Graphic').then((m: any) => m.default),
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            import('@geoscene/core/geometry/Point').then((m: any) => m.default),
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            import('@geoscene/core/symbols/SimpleMarkerSymbol').then((m: any) => m.default)
        ]);

        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

        const point = new Point({
            x: pointData.x,
            y: pointData.y,
            spatialReference: this.view.spatialReference
        });

        const symbol = new SimpleMarkerSymbol({
            color: [0, 122, 255, 0.8],
            size: 8,
            outline: {
                color: isDark ? [255, 255, 255] : [255, 255, 255],
                width: 2
            }
        });

        const graphic = new Graphic({
            geometry: point,
            symbol: symbol,
            attributes: {
                value: pointData.value,
                x: pointData.x,
                y: pointData.y
            }
        });

        this.graphicsLayer?.add(graphic);
        this.samplingPoints.push(pointData);

        // 平滑动画
        (graphic.symbol as any).color[3] = 0;
        setTimeout(() => {
            graphic.symbol = symbol;
        }, 50);

        console.log('✅ 采样点已添加:', pointData);
    }

    /**
     * 添加多边形
     */
    async addPolygon(coordinates: number[][][], options: PolygonStyleOptions = {}): Promise<void> {
        if (this.isMock) {
            // Mock 模式下简化实现
            console.log(`Mock 模式：添加多边形 (${coordinates.length} 个环)`);
            return;
        }

        const [Graphic, Polygon, SimpleFillSymbol]: [any, any, any] = await Promise.all([
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            import('@geoscene/core/Graphic').then((m: any) => m.default),
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            import('@geoscene/core/geometry/Polygon').then((m: any) => m.default),
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            import('@geoscene/core/symbols/SimpleFillSymbol').then((m: any) => m.default)
        ]);

        const polygon = new Polygon({
            rings: coordinates,
            spatialReference: this.view.spatialReference
        });

        const symbol = new SimpleFillSymbol({
            color: options.fillColor || [0, 122, 255, 0.2],
            outline: {
                color: options.strokeColor || [0, 122, 255, 1],
                width: options.strokeWidth || 2
            }
        });

        const graphic = new Graphic({
            geometry: polygon,
            symbol: symbol
        });

        this.graphicsLayer?.add(graphic);
    }

    toggleLayer(layerName: string, visible: boolean): void {
        if (this.layers[layerName]) {
            this.layers[layerName].visible = visible;
            console.log(`${layerName}图层: ${visible ? '显示' : '隐藏'}`);
        }
    }

    setLayerOpacity(layerName: string, opacity: number): void {
        if (this.layers[layerName]) {
            this.layers[layerName].opacity = opacity;
        }
    }

    setLayerZIndex(layerName: string, zIndex: number): void {
        if (this.layers[layerName]) {
            this.layers[layerName].listMode = 'show';
            // ArcGIS 图层管理中，Z-index 可以通过图层顺序控制
            // 这里我们重新添加图层来改变层级
            const layer = this.layers[layerName];
            this.map.remove(layer);
            this.map.add(layer, zIndex);
        }
    }

    removeLayer(layerName: string): void {
        if (this.layers[layerName]) {
            this.map.remove(this.layers[layerName]);
            delete this.layers[layerName];
        }
    }

    clearAllLayers(): void {
        if (this.isMock) {
            // Mock 模式下简化实现
            this.layers = {};
            this.samplingPoints = [];
            console.log('Mock 模式：所有图层已清除');
            return;
        }

        for (const [_name, layer] of Object.entries(this.layers)) {
            this.map.remove(layer);
        }
        this.layers = {};

        if (this.graphicsLayer) {
            this.graphicsLayer.removeAll();
        }

        this.samplingPoints = [];
        console.log('✅ 所有图层已清除');
    }

    zoomToLayer(layerName: string): void {
        if (this.layers[layerName] && this.layers[layerName].fullExtent) {
            this.view.goTo(this.layers[layerName].fullExtent);
        }
    }

    setClickHandler(handler: ClickHandler): void {
        if (this.isMock) {
            // Mock 模式下简化实现
            console.log('Mock 模式：点击处理器已设置（无实际功能）');
            return;
        }

        this.view.on('click', async (event: any) => {
            try {
                const response = await this.view.hitTest(event);
                if (response.results.length > 0) {
                    const graphic = response.results[0].graphic;
                    handler(graphic, event.mapPoint);
                }
            } catch (error) {
                console.error('点击查询失败:', error);
            }
        });
    }

    getSamplingPoints(): SamplingPoint[] {
        return this.samplingPoints;
    }

    destroy(): void {
        try {
            this.clearAllLayers();
            this.engine?.destroy();
        } catch (error) {
            console.warn('清理 GeoScene 适配器资源时出现警告:', error);
        } finally {
            this.graphicsLayer = null;
            this.view = null;
            this.map = null;
            this.engine = null;
        }
    }
}
