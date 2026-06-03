/**
 * ArcGIS 地图适配器
 * 使用 GeoSceneEngine，封装 ArcGIS API for JavaScript 的地图操作
 */

import { MapAdapter } from './MapAdapter';
import { GeoSceneConfig } from '../config/geoscene.config';
import { GeoSceneEngine } from '../map/core/GeoSceneEngine';
import { MockMapEngine } from '../map/core/MockMapEngine';
import type {
    GeoJSONFeatureCollection,
    SamplingPoint,
    PolygonStyleOptions
} from '../../types/core';
import type {
    AdapterOptions,
    GeoSceneLayerStore,
    GraphicsLayer,
    ClickHandler
} from '../../types/adapter';
import type { BaseMapEngine } from '../../types/map-engine';

/**
 * ArcGIS 地图适配器
 * 使用 GeoSceneEngine 或 MockMapEngine，封装地图操作
 */
export class GeoSceneAdapter extends MapAdapter {
    /** 地图引擎 */
    engine: GeoSceneEngine | MockMapEngine | null;

    /** 是否使用 Mock 模式 */
    isMock: boolean;

    /** ArcGIS 视图 */
    view: any;

    /** ArcGIS 地图 */
    map: any;

    /** 图层存储 */
    layers: GeoSceneLayerStore;

    /** 图形图层 */
    graphicsLayer: GraphicsLayer | null;

    /** 采样点列表 */
    samplingPoints: SamplingPoint[];

    constructor() {
        super();

        // 根据配置选择引擎
        const config = GeoSceneConfig.getConfig();
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
     * 根据 isMock 标志选择使用 GeoSceneEngine 或 MockMapEngine
     */
    async initMap(containerId: string, _options?: AdapterOptions): Promise<any> {
        // 初始化 ArcGIS 配置
        const config = GeoSceneConfig.getConfig();

        if (this.isMock) {
            // 使用 Mock 引擎
            console.log('🗺️ 使用 Mock 地图引擎');
            this.engine = new MockMapEngine({
                center: GeoSceneConfig.GEOSCENE_DEFAULT_CENTER as any,
                zoom: GeoSceneConfig.GEOSCENE_DEFAULT_ZOOM,
                minZoom: GeoSceneConfig.VIEW_OPTIONS.constraints.minZoom,
                maxZoom: GeoSceneConfig.VIEW_OPTIONS.constraints.maxZoom
            });

            // 初始化引擎
            await this.engine.init(containerId);

            // 获取 view 和 map 引用
            this.view = this.engine.getView();
            this.map = this.engine.map;

            console.log('✅ Mock 地图初始化完成');

            return this.view;
        } else {
            // 使用 GeoScene 引擎
            console.log('🗺️ 使用 GeoScene 地图引擎');

            // 设置 GeoScene 配置
            try {
                // @ts-ignore - GeoScene 模块通过 global.d.ts 声明
                const esriConfig: any = await import('@geoscene/core/config');
                (esriConfig.default as any).portalUrl = config.portalUrl;

                // 根据认证模式配置
                if (config.authMode === 'enterprise') {
                    // Enterprise 模式：使用 IdentityManager 进行企业认证
                    console.log('🔐 使用 GeoScene Enterprise 认证模式');
                    await this._setupEnterpriseAuth(esriConfig.default, config);
                } else {
                    // API Key 模式
                    if (config.apiKey) {
                        (esriConfig.default as any).apiKey = config.apiKey;
                        console.log('🔑 使用 GeoScene API Key 认证');
                    }
                }
            } catch (error) {
                console.warn('GeoScene 配置设置失败，使用默认配置', error);
            }

            // 创建 GeoSceneEngine
            this.engine = new GeoSceneEngine({
                center: GeoSceneConfig.GEOSCENE_DEFAULT_CENTER as any,
                zoom: GeoSceneConfig.GEOSCENE_DEFAULT_ZOOM,
                minZoom: GeoSceneConfig.VIEW_OPTIONS.constraints.minZoom,
                maxZoom: GeoSceneConfig.VIEW_OPTIONS.constraints.maxZoom
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
     * 设置 GeoScene Enterprise 认证
     * 使用 IdentityManager + ServerInfo 进行企业门户 Token 认证
     */
    private async _setupEnterpriseAuth(esriConfig: any, config: any): Promise<void> {
        try {
            // @ts-ignore - GeoScene 模块通过 global.d.ts 声明
            const IdentityManager: any = await import('@geoscene/core/identity/IdentityManager');
            // @ts-ignore - GeoScene 模块通过 global.d.ts 声明
            const ServerInfo: any = await import('@geoscene/core/identity/ServerInfo');
            // @ts-ignore - GeoScene 模块通过 global.d.ts 声明
            const OAuthInfo: any = await import('@geoscene/core/identity/OAuthInfo');

            const portalUrl = config.portalUrl || 'https://www.geoscene.cn';

            // 配置 OAuthInfo
            const oauthInfo = new OAuthInfo.default({
                appId: 'udake-geoscene-app',
                portalUrl: portalUrl,
                popup: false  // 使用服务器端认证而非弹出窗口
            });

            IdentityManager.default.registerOAuthInfos([oauthInfo]);

            // 使用用户名密码生成 Token
            const serverInfo = new ServerInfo.default({
                server: portalUrl,
                tokenServiceUrl: config.tokenUrl || `${portalUrl}/sharing/rest/generateToken`
            });

            const tokenResponse = await IdentityManager.default.generateToken(serverInfo, {
                username: config.username,
                password: config.password
            });

            if (tokenResponse && tokenResponse.token) {
                IdentityManager.default.registerToken({
                    server: portalUrl,
                    token: tokenResponse.token,
                    expires: tokenResponse.expires,
                    ssl: tokenResponse.ssl
                });
                console.log('✅ GeoScene Enterprise Token 获取成功');
            } else {
                console.warn('⚠️ GeoScene Enterprise Token 获取失败，回退为访客模式');
            }
        } catch (error) {
            console.warn('⚠️ GeoScene Enterprise 认证失败，回退为访客模式:', error);
            // 即使企业认证失败，也允许地图以访客模式加载
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
     * 优先使用 ImageryLayer 加载栅格数据，失败时降级为 GeoJSON 点渲染
     */
    async addRasterLayer(type: 'prediction' | 'variance', url: string): Promise<void> {
        if (this.isMock) {
            console.log(`Mock 模式：添加 ${type === 'prediction' ? '预测' : '方差'}栅格图层`);
            return;
        }

        // 移除旧图层
        if (this.layers[type]) {
            this.map.remove(this.layers[type]);
        }
        // 移除旧的 GeoJSON 降级图层
        if (this.layers[`geojson_${type}`]) {
            this.map.remove(this.layers[`geojson_${type}`]);
        }

        try {
            const [ImageryLayer]: [any] = await Promise.all([
                // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
                import('@geoscene/core/layers/ImageryLayer').then((m: any) => m.default)
            ]);

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
            console.warn(`${type}栅格图层加载失败，尝试 GeoJSON 点渲染降级:`, (error as Error).message);
            try {
                const taskId = url.split('/').pop()?.split('.')[0]?.split('_')[0];
                if (taskId) {
                    const geojsonUrl = url.replace(/\.tif$/, '.geojson');
                    const fullGeojsonUrl = geojsonUrl.startsWith('http') ? geojsonUrl : `${window.location.origin}${geojsonUrl}`;
                    const response = await fetch(fullGeojsonUrl, { mode: 'cors' });
                    if (response.ok) {
                        const geojson = await response.json();
                        if (geojson.features) {
                            await this._renderGeoJSONPoints(geojson, type);
                        }
                    }
                }
            } catch (geojsonError) {
                console.warn(`GeoJSON 降级渲染也失败:`, (geojsonError as Error).message);
            }
        }
    }

    /**
     * 将 GeoJSON 点数据渲染为彩色标记（栅格降级方案）
     * 使用 SimpleMarkerSymbol + Graphic 在地图上绘制颜色分级标记
     */
    private async _renderGeoJSONPoints(geojson: GeoJSONFeatureCollection, type: 'prediction' | 'variance'): Promise<void> {
        const layerKey = `geojson_${type}`;

        // 计算值范围用于颜色映射
        const values: number[] = [];
        for (const f of geojson.features) {
            const v = f.properties?.value ?? f.properties?.[type];
            if (v !== null && v !== undefined && isFinite(v)) {
                values.push(v);
            }
        }
        if (values.length === 0) return;

        const minVal = Math.min(...values);
        const maxVal = Math.max(...values);
        const span = maxVal - minVal || 1;

        const [Graphic, Point, SimpleMarkerSymbol]: [any, any, any] = await Promise.all([
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            import('@geoscene/core/Graphic').then((m: any) => m.default),
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            import('@geoscene/core/geometry/Point').then((m: any) => m.default),
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            import('@geoscene/core/symbols/SimpleMarkerSymbol').then((m: any) => m.default)
        ]);

        const graphics: any[] = [];
        const MAX_POINTS = 5000;

        for (let i = 0; i < Math.min(geojson.features.length, MAX_POINTS); i++) {
            const feature = geojson.features[i];
            const coords = feature.geometry?.coordinates;
            if (!coords || coords.length < 2) continue;

            const value = feature.properties?.value ?? feature.properties?.[type] ?? 0;
            const normalizedValue = (value - minVal) / span;
            const color = this._valueToColor(normalizedValue);

            const point = new Point({
                x: coords[0],
                y: coords[1],
                spatialReference: this.view.spatialReference
            });

            const symbol = new SimpleMarkerSymbol({
                color: color,
                size: 4 + normalizedValue * 8,
                outline: {
                    color: [255, 255, 255, 0.3],
                    width: 0.5
                }
            });

            const graphic = new Graphic({
                geometry: point,
                symbol: symbol,
                attributes: {
                    value: value,
                    type: type
                }
            });

            graphics.push(graphic);
        }

        // 使用 GraphicsLayer 管理大量标记
        const [GraphicsLayer]: [any] = await Promise.all([
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            import('@geoscene/core/layers/GraphicsLayer').then((m: any) => m.default)
        ]);

        // 替换旧图层
        if (this.layers[layerKey]) {
            this.map.remove(this.layers[layerKey]);
        }

        const graphicsLayer = new GraphicsLayer({
            title: type === 'prediction' ? '预测值(GeoJSON降级)' : '方差值(GeoJSON降级)',
            graphics: graphics
        });

        this.map.add(graphicsLayer);
        this.layers[layerKey] = graphicsLayer;

        console.log(`✅ GeoJSON 点渲染完成(${type}): ${graphics.length} 个点`);
    }

    /**
     * 根据归一化值(0-1)返回 RGBA 颜色数组（蓝绿红渐变）
     * 与 AMapAdapter._valueToColor 保持一致的配色方案
     */
    private _valueToColor(normalizedValue: number): [number, number, number, number] {
        let r: number, g: number, b: number;
        if (normalizedValue < 0.5) {
            // 蓝色 -> 绿色
            r = Math.floor(normalizedValue * 2 * 255);
            g = Math.floor(100 + normalizedValue * 2 * 155);
            b = Math.floor(255 - normalizedValue * 2 * 155);
        } else {
            // 绿色 -> 红色
            const t = (normalizedValue - 0.5) * 2;
            r = Math.min(255, Math.floor(100 + t * 155));
            g = Math.floor(255 - t * 155);
            b = Math.floor(100 - t * 100);
        }
        return [r, g, b, 0.7];
    }

    /**
     * 添加单个采样点
     * 支持从 pointData.style 读取颜色和形状配置
     */
    async addMarker(pointData: SamplingPoint): Promise<void> {
        if (this.isMock) {
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

        // 从 pointData.style 读取样式，否则使用默认值
        const style = pointData.style;
        const hexColor = style?.color || '#007AFF';
        const shape = (style?.shape || 'circle') as string;

        // 解析 hex 颜色为 RGBA 数组
        const color = this._hexToRgba(hexColor, 0.8);

        // 映射形状到 GeoScene SimpleMarkerSymbol style
        const GEOSCENE_SHAPE_MAP: Record<string, string> = {
            circle: 'circle',
            square: 'square',
            triangle: 'triangle',
            diamond: 'diamond',
            star: 'cross'  // GeoScene 无原生 star，用 cross 近似
        };

        const point = new Point({
            x: pointData.x,
            y: pointData.y,
            spatialReference: this.view.spatialReference
        });

        const symbol = new SimpleMarkerSymbol({
            color: color,
            size: 10,
            style: GEOSCENE_SHAPE_MAP[shape] || 'circle',
            outline: {
                color: [255, 255, 255, 1],
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

        console.log('✅ 采样点已添加:', pointData, '样式:', shape, hexColor);
    }

    /**
     * 将 hex 颜色字符串转换为 RGBA 数组
     */
    private _hexToRgba(hex: string, alpha: number): [number, number, number, number] {
        const clean = hex.replace('#', '');
        const r = parseInt(clean.substring(0, 2), 16);
        const g = parseInt(clean.substring(2, 4), 16);
        const b = parseInt(clean.substring(4, 6), 16);
        return [r, g, b, alpha];
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
