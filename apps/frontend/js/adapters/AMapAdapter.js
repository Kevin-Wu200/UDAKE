/* global AMap */
import { MapAdapter } from './MapAdapter.js';
import { AMapEngine } from '../map/core/AMapEngine.js';

/**
 * 高德地图适配器
 * 将高德地图 API 适配到统一的地图接口
 */
export class AMapAdapter extends MapAdapter {
    constructor() {
        super();
        this.engine = null;
        this.view = null;
        this.map = null;
        this.layers = {};
        this.samplingPoints = [];
    }

    /**
     * 初始化地图
     */
    async initMap(containerId, options = {}) {
        // 创建 AMapEngine
        this.engine = new AMapEngine({
            center: options.center || [116.39, 39.9],
            zoom: options.zoom || 5
        });

        // 初始化引擎
        await this.engine.init(containerId, options);

        // 获取地图实例
        this.map = this.engine.map;
        this.view = this.map; // 高德地图中 map 即为 view

        console.log('✅ 高德地图适配器初始化完成');
        return this.view;
    }

    /**
     * 获取 view（兼容 ArcGIS 接口）
     */
    getView() {
        return this.view;
    }

    /**
     * 获取地图引擎
     */
    getEngine() {
        return this.engine;
    }

    /**
     * 添加 GeoJSON 点图层
     */
    async addPointsLayer(geojson, layerName = 'points') {
        try {
            // 解析 GeoJSON 并添加 Marker
            const features = geojson.type === 'FeatureCollection'
                ? geojson.features
                : [geojson];

            features.forEach(feature => {
                if (feature.geometry.type === 'Point') {
                    const [lng, lat] = feature.geometry.coordinates;
                    const marker = this.engine.addMarker([lng, lat], {
                        title: '采样点',
                        data: feature.properties
                    });

                    // 保存到图层
                    if (!this.layers[layerName]) {
                        this.layers[layerName] = [];
                    }
                    this.layers[layerName].push(marker);
                }
            });

            console.log('✅ 采样点图层加载完成');
        } catch (error) {
            console.error('❌ 加载采样点失败:', error);
            throw error;
        }
    }

    /**
     * 添加栅格图层（高德地图暂不支持，预留接口）
     */
    async addRasterLayer(_type, _url) {
        console.warn('高德地图暂不支持栅格图层');
    }

    /**
     * 添加单个采样点
     */
    async addMarker(pointData) {
        this.engine.addMarker([pointData.x, pointData.y], {
            title: `值: ${pointData.value}`,
            data: pointData
        });

        this.samplingPoints.push(pointData);
        console.log('✅ 采样点已添加:', pointData);
    }

    /**
     * 添加多边形
     */
    async addPolygon(coordinates, options = {}) {
        // 转换坐标格式
        let path;
        if (Array.isArray(coordinates[0][0])) {
            // coordinates 是 rings 格式 [[[lng, lat], ...]]
            path = coordinates[0].map(coord => [coord[0], coord[1]]);
        } else {
            // coordinates 已经是 path 格式 [[lng, lat], ...]
            path = coordinates;
        }

        const polygon = new AMap.Polygon({
            path: path,
            strokeColor: options.strokeColor || '#007AFF',
            strokeWeight: options.strokeWidth || 2,
            strokeOpacity: options.strokeOpacity || 1,
            fillColor: options.fillColor || [0, 122, 255, 0.1],
            fillOpacity: options.fillOpacity || 0.1
        });

        this.map.add(polygon);

        // 保存到图层
        if (!this.layers['polygons']) {
            this.layers['polygons'] = [];
        }
        this.layers['polygons'].push(polygon);

        // 自动缩放到多边形
        this.map.setFitView([polygon]);

        return polygon;
    }

    /**
     * 切换图层显示/隐藏
     */
    toggleLayer(layerName, visible) {
        if (this.layers[layerName]) {
            const markers = this.layers[layerName];
            markers.forEach(marker => {
                if (visible) {
                    marker.show();
                } else {
                    marker.hide();
                }
            });
            console.log(`${layerName}图层: ${visible ? '显示' : '隐藏'}`);
        }
    }

    /**
     * 设置图层透明度
     */
    setLayerOpacity(_layerName, _opacity) {
        console.warn('高德地图 Marker 不支持透明度设置');
    }

    /**
     * 移除图层
     */
    removeLayer(layerName) {
        if (this.layers[layerName]) {
            const markers = this.layers[layerName];
            markers.forEach(marker => {
                this.map.remove(marker);
            });
            delete this.layers[layerName];
        }
    }

    /**
     * 清除所有图层
     */
    clearAllLayers() {
        for (const markers of Object.values(this.layers)) {
            if (Array.isArray(markers)) {
                markers.forEach(marker => this.map.remove(marker));
            }
        }
        this.layers = {};
        this.engine.clearMarkers();
        this.engine.clearPolygons();
        this.samplingPoints = [];
        console.log('✅ 所有图层已清除');
    }

    /**
     * 缩放到图层
     */
    zoomToLayer(layerName) {
        if (this.layers[layerName]) {
            const markers = this.layers[layerName];
            if (markers.length > 0) {
                this.map.setFitView(markers);
            }
        }
    }

    /**
     * 设置点击事件处理器
     */
    setClickHandler(handler) {
        this.map.on('click', (event) => {
            const lnglat = event.lnglat;
            handler(null, { lng: lnglat.lng, lat: lnglat.lat });
        });
    }

    /**
     * 获取采样点
     */
    getSamplingPoints() {
        return this.samplingPoints;
    }
}
