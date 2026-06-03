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
     * 添加栅格图层
     * 高德地图通过 ImageLayer 加载渲染后的 GeoTIFF 预览图
     * 或使用 GeoJSON 点数据进行可视化
     */
    async addRasterLayer(type, url) {
        try {
            // 构建 GeoTIFF 的完整 URL
            const fullUrl = url.startsWith('http') ? url : `${window.location.origin}${url}`;
            
            // 尝试使用 ImageLayer 加载 GeoTIFF（需要服务端返回可渲染格式）
            const imageLayer = new AMap.ImageLayer({
                url: fullUrl,
                bounds: this.map.getBounds(),
                zooms: [3, 18],
                opacity: 0.6
            });

            const layerKey = `raster_${type}`;
            if (this.layers[layerKey]) {
                this.map.remove(this.layers[layerKey]);
            }

            imageLayer.setMap(this.map);
            this.layers[layerKey] = imageLayer;
            console.log(`✅ 栅格图层(${type})已添加`);
        } catch (error) {
            console.warn(`栅格图层(${type})加载失败，尝试 GeoJSON 点渲染:`, error.message);
            // 降级方案：尝试加载对应的 GeoJSON 文件进行点渲染
            try {
                const taskId = url.split('/').pop()?.split('_')[0];
                if (taskId) {
                    const geojsonUrl = url.replace(/\.tif$/, '.geojson');
                    const fullGeojsonUrl = geojsonUrl.startsWith('http') ? geojsonUrl : `${window.location.origin}${geojsonUrl}`;
                    const response = await fetch(fullGeojsonUrl, { mode: 'cors' });
                    if (response.ok) {
                        const geojson = await response.json();
                        if (geojson.features) {
                            this._renderGeoJSONPoints(geojson, type);
                        }
                    }
                }
            } catch (geojsonError) {
                console.warn(`GeoJSON 降级渲染也失败:`, geojsonError.message);
            }
        }
    }

    /**
     * 将 GeoJSON 点数据渲染为地图上的彩色点
     */
    _renderGeoJSONPoints(geojson, type) {
        const layerKey = `geojson_${type}`;
        if (this.layers[layerKey]) {
            this.map.remove(this.layers[layerKey]);
        }

        // 计算值范围用于颜色映射
        const values = geojson.features
            .map(f => f.properties?.value ?? f.properties?.[type])
            .filter(v => v !== null && v !== undefined && isFinite(v));
        
        const minVal = Math.min(...values);
        const maxVal = Math.max(...values);
        const span = maxVal - minVal || 1;

        // 为每个点创建标记
        const markers = geojson.features.map((feature, _index) => {
            const coords = feature.geometry?.coordinates;
            if (!coords || coords.length < 2) return null;

            const value = feature.properties?.value ?? feature.properties?.[type] ?? 0;
            const normalizedValue = (value - minVal) / span;
            
            // 颜色映射：蓝(低) -> 绿(中) -> 红(高)
            const color = this._valueToColor(normalizedValue);

            return new AMap.CircleMarker({
                center: [coords[0], coords[1]],
                radius: 4 + normalizedValue * 8,
                fillColor: color,
                fillOpacity: 0.6,
                strokeColor: color,
                strokeWeight: 1,
                strokeOpacity: 0.3,
                zIndex: Math.floor(normalizedValue * 100)
            });
        }).filter(Boolean);

        if (markers.length > 0) {
            // 使用 OverlayGroup 管理大量标记以提高性能
            const group = new AMap.OverlayGroup(markers.slice(0, 5000)); // 限制最多 5000 个点
            group.setMap(this.map);
            this.layers[layerKey] = group;
            console.log(`✅ GeoJSON 点渲染完成(${type}): ${Math.min(markers.length, 5000)} 个点`);
        }
    }

    /**
     * 根据值(0-1)返回颜色（蓝绿红渐变）
     */
    _valueToColor(normalizedValue) {
        let r, g, b;
        if (normalizedValue < 0.5) {
            // 蓝色 -> 绿色
            r = Math.floor(normalizedValue * 2 * 255);
            g = Math.floor(100 + normalizedValue * 2 * 155);
            b = Math.floor(255 - normalizedValue * 2 * 155);
        } else {
            // 绿色 -> 红色
            const t = (normalizedValue - 0.5) * 2;
            r = Math.floor(255);
            g = Math.floor(255 - t * 255);
            b = Math.floor(100 - t * 100);
        }
        return `rgb(${r},${g},${b})`;
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
     * 设置图层Z轴索引
     */
    setLayerZIndex(_layerName, _zIndex) {
        console.warn('高德地图暂不支持通过适配器设置图层Z轴索引');
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
        if (this.engine) {
            this.engine.clearMarkers();
            this.engine.clearPolygons();
        }
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

    /**
     * 销毁适配器资源
     */
    destroy() {
        try {
            this.clearAllLayers();
            if (this.engine && typeof this.engine.destroy === 'function') {
                this.engine.destroy();
            }
        } catch (error) {
            console.warn('清理高德适配器资源时出现警告:', error);
        } finally {
            this.engine = null;
            this.view = null;
            this.map = null;
            this.layers = {};
            this.samplingPoints = [];
        }
    }
}
