import { MapAdapter } from './MapAdapter.js';
import { ArcGISConfig } from '../config/arcgis.config.js';
import { ArcGISEngine } from '../map/core/ArcGISEngine.js';

/**
 * ArcGIS 地图适配器
 * 使用 ArcGISEngine，封装 ArcGIS API for JavaScript 的地图操作
 */
export class ArcGISAdapter extends MapAdapter {
    constructor() {
        super();

        // 使用新的 ArcGISEngine
        this.engine = null;

        this.view = null;
        this.map = null;
        this.layers = {};
        this.graphicsLayer = null;
        this.samplingPoints = [];
    }

    /**
     * 初始化 ArcGIS 地图
     */
    async initMap(containerId) {
        // 初始化 ArcGIS 配置
        const config = ArcGISConfig.getConfig();

        // 如果有 API Key 且不是占位符，则设置
        if (!config.isMock) {
            try {
                const esriConfig = await import('https://js.arcgis.com/4.28/@arcgis/core/config.js');
                esriConfig.default.apiKey = config.apiKey;
                esriConfig.default.portalUrl = config.portalUrl;
            } catch (error) {
                console.warn('ArcGIS 配置设置失败，使用默认配置', error);
            }
        }

        // 创建 ArcGISEngine
        this.engine = new ArcGISEngine({
            center: ArcGISConfig.ARCGIS_DEFAULT_CENTER,
            zoom: ArcGISConfig.ARCGIS_DEFAULT_ZOOM,
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

        console.log('✅ ArcGIS 地图初始化完成（使用 ArcGISEngine）', config.isMock ? '(Mock模式)' : '');

        return this.view;
    }

    /**
     * 初始化 Graphics 图层
     */
    async initGraphicsLayer() {
        const GraphicsLayer = (await import('https://js.arcgis.com/4.28/@arcgis/core/layers/GraphicsLayer.js')).default;
        this.graphicsLayer = new GraphicsLayer({
            title: '手动采样点'
        });
        this.map.add(this.graphicsLayer);
    }

    getView() {
        return this.view;
    }

    /**
     * 获取引擎实例
     */
    getEngine() {
        return this.engine;
    }

    /**
     * 添加 GeoJSON 点图层
     */
    async addPointsLayer(geojson, layerName = 'points') {
        try {
            const [GeoJSONLayer] = await Promise.all([
                import('https://js.arcgis.com/4.28/@arcgis/core/layers/GeoJSONLayer.js')
            ].map(p => p.then(m => m.default)));

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
    async addRasterLayer(type, url) {
        try {
            const [ImageryLayer] = await Promise.all([
                import('https://js.arcgis.com/4.28/@arcgis/core/layers/ImageryLayer.js')
            ].map(p => p.then(m => m.default)));

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
    async addMarker(pointData) {
        const [Graphic, Point, SimpleMarkerSymbol] = await Promise.all([
            import('https://js.arcgis.com/4.28/@arcgis/core/Graphic.js'),
            import('https://js.arcgis.com/4.28/@arcgis/core/geometry/Point.js'),
            import('https://js.arcgis.com/4.28/@arcgis/core/symbols/SimpleMarkerSymbol.js')
        ].map(p => p.then(m => m.default)));

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

        this.graphicsLayer.add(graphic);
        this.samplingPoints.push(pointData);

        // 平滑动画
        graphic.symbol.color[3] = 0;
        setTimeout(() => {
            graphic.symbol = symbol;
        }, 50);

        console.log('✅ 采样点已添加:', pointData);
    }

    /**
     * 添加多边形
     */
    async addPolygon(coordinates, options = {}) {
        const [Graphic, Polygon, SimpleFillSymbol] = await Promise.all([
            import('https://js.arcgis.com/4.28/@arcgis/core/Graphic.js'),
            import('https://js.arcgis.com/4.28/@arcgis/core/geometry/Polygon.js'),
            import('https://js.arcgis.com/4.28/@arcgis/core/symbols/SimpleFillSymbol.js')
        ].map(p => p.then(m => m.default)));

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

        this.graphicsLayer.add(graphic);
    }

    toggleLayer(layerName, visible) {
        if (this.layers[layerName]) {
            this.layers[layerName].visible = visible;
            console.log(`${layerName}图层: ${visible ? '显示' : '隐藏'}`);
        }
    }

    setLayerOpacity(layerName, opacity) {
        if (this.layers[layerName]) {
            this.layers[layerName].opacity = opacity;
        }
    }

    removeLayer(layerName) {
        if (this.layers[layerName]) {
            this.map.remove(this.layers[layerName]);
            delete this.layers[layerName];
        }
    }

    clearAllLayers() {
        for (const [name, layer] of Object.entries(this.layers)) {
            this.map.remove(layer);
        }
        this.layers = {};
        if (this.graphicsLayer) {
            this.graphicsLayer.removeAll();
        }
        this.samplingPoints = [];
        console.log('✅ 所有图层已清除');
    }

    zoomToLayer(layerName) {
        if (this.layers[layerName] && this.layers[layerName].fullExtent) {
            this.view.goTo(this.layers[layerName].fullExtent);
        }
    }

    setClickHandler(handler) {
        this.view.on('click', async (event) => {
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

    getSamplingPoints() {
        return this.samplingPoints;
    }
}
