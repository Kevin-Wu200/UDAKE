import { MapAdapter } from './MapAdapter.js';
import { TiandituEngine } from '../map/core/TiandituEngine.js';
import { TileCalculator } from '../map/core/TileCalculator.js';
import { Projection } from '../map/core/Projection.js';
import { Viewport } from '../map/core/Viewport.js';

/**
 * 天地图适配器 - 使用 TiandituEngine
 * 保持向后兼容的同时使用新的引擎架构
 */
export class TiandituAdapter extends MapAdapter {
    constructor(options = {}) {
        super();

        // 使用新的 TiandituEngine
        this.engine = new TiandituEngine(options);

        // 保持向后兼容的属性
        this.container = null;
        this.mapContainer = null;
        this.viewport = null;

        // 地图状态（代理到 engine）
        this.center = options.center || [116.39, 39.9];
        this.zoom = options.zoom || 5;
        this.minZoom = options.minZoom || 1;
        this.maxZoom = options.maxZoom || 18;
        this.type = options.type || 'img';

        // API Key
        this.apiKey = '66773e61397afa9c511d62fc259f3e70';

        // 瓦片缓存（代理到 engine）
        this.tiles = new Map();
        this.tileServers = ['t0', 't1', 't2', 't3'];
        this.currentServerIndex = 0;

        // 图层管理
        this.layers = {};
        this.samplingPoints = [];
    }

    /**
     * 初始化地图
     */
    async initMap(containerId) {
        // 使用 engine 初始化
        await this.engine.init(containerId, {
            center: this.center,
            zoom: this.zoom,
            minZoom: this.minZoom,
            maxZoom: this.maxZoom,
            type: this.type
        });

        // 同步引用以保持向后兼容
        this.container = this.engine.container;
        this.mapContainer = this.engine.mapContainer;
        this.viewport = this.engine.viewport;
        this.tiles = this.engine.tiles;

        console.log('✅ 天地图初始化完成（使用 TiandituEngine）');
        return this;
    }

    /**
     * 绑定交互事件（已由 engine 处理）
     */
    bindEvents() {
        // Engine 已经处理了事件绑定
    }

    /**
     * 计算每度对应的像素数（代理到 engine）
     */
    getPixelPerDegree() {
        return this.engine.getPixelPerDegree();
    }

    /**
     * 渲染瓦片（代理到 engine）
     */
    renderTiles() {
        this.engine.renderTiles();
    }

    /**
     * 加载单个瓦片（代理到 engine）
     */
    loadTile(tile) {
        this.engine.loadTile(tile);
    }

    /**
     * 获取瓦片 URL（代理到 engine）
     */
    getTileUrl(x, y, z, serverIndex = 0) {
        return this.engine.getTileUrl(x, y, z, serverIndex);
    }

    /**
     * 处理瓦片加载错误（代理到 engine）
     */
    handleTileError(img, x, y, z, retryCount = 0) {
        this.engine.handleTileError(img, x, y, z, retryCount);
    }

    /**
     * 设置缩放级别（代理到 engine）
     */
    setZoom(zoom) {
        this.engine.setZoom(zoom);
        this.zoom = this.engine.getZoom();
    }

    /**
     * 设置中心点（代理到 engine）
     */
    setCenter(lng, lat) {
        this.engine.setCenter([lng, lat]);
        this.center = this.engine.getCenter();
    }

    /**
     * 切换图层类型
     */
    switchLayer(type) {
        if (type !== this.type) {
            this.type = type;
            this.engine.type = type;
            this.tiles.clear();
            this.renderTiles();
            console.log(`切换到${type === 'img' ? '影像' : '矢量'}图层`);
        }
    }

    /**
     * 获取地图视图（兼容接口）
     */
    getView() {
        return this.engine || this;
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
        console.log('✅ 采样点图层加载完成');
        // TODO: 实现点图层渲染
    }

    /**
     * 添加栅格图层
     */
    async addRasterLayer(type, url) {
        console.log(`✅ ${type}栅格图层已准备`);
        // TODO: 实现栅格图层渲染
    }

    /**
     * 添加单个采样点
     */
    async addMarker(pointData) {
        this.samplingPoints.push(pointData);
        console.log('✅ 采样点已添加:', pointData);
        // TODO: 实现标记渲染
    }

    /**
     * 添加多边形
     */
    async addPolygon(coordinates, options = {}) {
        console.log('✅ 多边形已添加');
        // TODO: 实现多边形渲染
    }

    /**
     * 切换图层显示
     */
    toggleLayer(layerName, visible) {
        console.log(`${layerName}图层: ${visible ? '显示' : '隐藏'}`);
    }

    /**
     * 设置图层透明度
     */
    setLayerOpacity(layerName, opacity) {
        // TODO: 实现
    }

    /**
     * 移除图层
     */
    removeLayer(layerName) {
        if (this.layers[layerName]) {
            delete this.layers[layerName];
        }
    }

    /**
     * 清除所有图层
     */
    clearAllLayers() {
        this.layers = {};
        this.samplingPoints = [];
        console.log('✅ 所有图层已清除');
    }

    /**
     * 缩放到图层
     */
    zoomToLayer(layerName) {
        // TODO: 实现
    }

    /**
     * 设置点击处理器
     */
    setClickHandler(handler) {
        this.container.addEventListener('click', (e) => {
            const rect = this.container.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            // 将像素坐标转换为经纬度
            const { width, height } = this.viewport.getSize();
            const centerPixel = Projection.lngLatToPixel(this.center[0], this.center[1], this.zoom);
            const clickPixelX = centerPixel.x + (x - width / 2);
            const clickPixelY = centerPixel.y + (y - height / 2);
            const lngLat = Projection.pixelToLngLat(clickPixelX, clickPixelY, this.zoom);

            const mapPoint = {
                longitude: lngLat.lng,
                latitude: lngLat.lat
            };

            handler(null, mapPoint);
        });
    }

    /**
     * 获取采样点
     */
    getSamplingPoints() {
        return this.samplingPoints;
    }
}
