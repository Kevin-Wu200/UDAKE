import { BaseMapEngine } from './BaseMapEngine.js';
import { initAMap } from '../../config/amap.config.js';

/**
 * 高德地图引擎
 * 使用高德 JS API v2.0 实现地图功能
 */
export class AMapEngine extends BaseMapEngine {
    constructor(options = {}) {
        super();
        this.supportsCustomReset = true;

        // 初始状态
        this.initialCenter = null;
        this.initialZoom = null;

        // 地图实例
        this.map = null;

        // 图层管理
        this.polygons = [];
        this.markers = [];
    }

    /**
     * 初始化地图
     * 使用新的 amap.config.js 配置
     */
    async init(container, options = {}) {
        // 获取容器 ID
        let containerId;
        if (typeof container === 'string') {
            containerId = container;
        } else {
            containerId = container.id;
        }

        if (!containerId) {
            throw new Error('地图容器 ID 不存在');
        }

        // 使用新的配置方法初始化地图
        this.map = await initAMap(containerId);

        // 保存初始状态
        this.initialCenter = this.map.getCenter();
        this.initialZoom = this.map.getZoom();

        // 应用自定义配置
        if (options.zoom) {
            this.map.setZoom(options.zoom);
        }
        if (options.center) {
            this.map.setCenter(options.center);
        }

        // 设置地图属性
        this.map.setStatus({
            resizeEnable: true,
            animateEnable: true,
            zoomEnable: true
        });

        // 设置缩放范围
        this.map.setZooms([3, 18]);

        // 绑定事件
        this.map.on('zoomend', () => {
            this.triggerZoomCallbacks(this.map.getZoom());
        });

        this.map.on('moveend', () => {
            const center = this.map.getCenter();
            this.triggerMoveCallbacks([center.lng, center.lat]);
        });

        console.log('✅ 高德地图引擎初始化完成');
    }

    /**
     * 设置中心点
     */
    setCenter(center) {
        if (Array.isArray(center)) {
            this.map.setCenter(center);
        } else {
            this.map.setCenter([center.lng, center.lat]);
        }
    }

    /**
     * 获取中心点
     */
    getCenter() {
        const center = this.map.getCenter();
        return [center.lng, center.lat];
    }

    /**
     * 设置缩放级别
     */
    setZoom(zoom) {
        this.map.setZoom(zoom);
    }

    /**
     * 获取缩放级别
     */
    getZoom() {
        return this.map.getZoom();
    }

    /**
     * 适配到指定边界
     */
    fitToBounds(bounds) {
        const { minLng, minLat, maxLng, maxLat } = bounds;
        const amapBounds = new AMap.Bounds(
            [minLng, minLat],
            [maxLng, maxLat]
        );
        this.map.setBounds(amapBounds);
    }

    /**
     * 添加 Polygon（区域采样）
     */
    addPolygon(geojson) {
        // 清除旧的 polygon
        this.clearPolygons();

        // 解析 GeoJSON
        const coordinates = this.parseGeoJSONCoordinates(geojson);

        if (coordinates.length === 0) {
            console.warn('GeoJSON 无有效坐标');
            return;
        }

        // 创建 Polygon
        coordinates.forEach(path => {
            const polygon = new AMap.Polygon({
                path: path,
                strokeColor: '#3366FF',
                strokeWeight: 2,
                strokeOpacity: 0.8,
                fillColor: '#3366FF',
                fillOpacity: 0.2
            });

            this.map.add(polygon);
            this.polygons.push(polygon);
        });

        // 自动适配视图
        if (this.polygons.length > 0) {
            this.map.setFitView(this.polygons);
        }
    }

    /**
     * 解析 GeoJSON 坐标
     */
    parseGeoJSONCoordinates(geojson) {
        const coordinates = [];

        if (geojson.type === 'FeatureCollection') {
            geojson.features.forEach(feature => {
                const coords = this.extractCoordinates(feature.geometry);
                if (coords) coordinates.push(...coords);
            });
        } else if (geojson.type === 'Feature') {
            const coords = this.extractCoordinates(geojson.geometry);
            if (coords) coordinates.push(...coords);
        } else {
            const coords = this.extractCoordinates(geojson);
            if (coords) coordinates.push(...coords);
        }

        return coordinates;
    }

    /**
     * 提取几何坐标
     */
    extractCoordinates(geometry) {
        if (!geometry) return null;

        switch (geometry.type) {
            case 'Polygon':
                return geometry.coordinates.map(ring =>
                    ring.map(coord => [coord[0], coord[1]])
                );
            case 'MultiPolygon':
                return geometry.coordinates.flatMap(polygon =>
                    polygon.map(ring => ring.map(coord => [coord[0], coord[1]]))
                );
            default:
                return null;
        }
    }

    /**
     * 清除所有 Polygon
     */
    clearPolygons() {
        this.polygons.forEach(polygon => {
            this.map.remove(polygon);
        });
        this.polygons = [];
    }

    /**
     * 添加采样点 Marker
     */
    addMarker(position, options = {}) {
        const marker = new AMap.Marker({
            position: position,
            icon: options.icon,
            title: options.title,
            extData: options.data
        });

        this.map.add(marker);
        this.markers.push(marker);

        return marker;
    }

    /**
     * 批量添加采样点
     */
    addMarkers(points) {
        points.forEach(point => {
            this.addMarker(point.position, point.options);
        });
    }

    /**
     * 清除所有 Marker
     */
    clearMarkers() {
        this.markers.forEach(marker => {
            this.map.remove(marker);
        });
        this.markers = [];
    }

    /**
     * 销毁地图实例
     */
    destroy() {
        super.destroy();
        this.clearPolygons();
        this.clearMarkers();
        if (this.map) {
            this.map.destroy();
            this.map = null;
        }
    }
}

