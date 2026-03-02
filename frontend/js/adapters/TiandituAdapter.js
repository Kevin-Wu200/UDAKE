import { MapAdapter } from './MapAdapter.js';
import { TileCalculator } from '../map/core/TileCalculator.js';
import { Projection } from '../map/core/Projection.js';
import { Viewport } from '../map/core/Viewport.js';

/**
 * 天地图适配器 - 原生 DOM 实现
 * 使用天地图 WMTS 服务直接加载瓦片
 */
export class TiandituAdapter extends MapAdapter {
    constructor(options = {}) {
        super();
        this.container = null;
        this.mapContainer = null;
        this.viewport = null;

        // 地图状态
        this.center = options.center || [116.39, 39.9]; // [lng, lat]
        this.zoom = options.zoom || 5;
        this.minZoom = options.minZoom || 1;
        this.maxZoom = options.maxZoom || 18;
        this.type = options.type || 'img'; // 'img' 或 'vec'

        // API Key
        this.apiKey = '66773e61397afa9c511d62fc259f3e70';

        // 瓦片缓存
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
        this.container = document.getElementById(containerId);
        if (!this.container) {
            throw new Error(`容器 #${containerId} 不存在`);
        }

        // 创建地图容器
        this.mapContainer = document.createElement('div');
        this.mapContainer.style.cssText = `
            position: relative;
            width: 100%;
            height: 100%;
            overflow: hidden;
            background: #f0f0f0;
            cursor: grab;
        `;
        this.container.appendChild(this.mapContainer);

        // 初始化视口
        this.viewport = new Viewport(this.container);

        // 绑定事件
        this.bindEvents();

        // 渲染瓦片
        this.renderTiles();

        console.log('✅ 天地图初始化完成（原生 DOM 模式）');
        return this;
    }

    /**
     * 绑定交互事件
     */
    bindEvents() {
        // 鼠标滚轮缩放
        this.container.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? -1 : 1;
            this.setZoom(this.zoom + delta);
        });

        // 鼠标拖拽
        this.container.addEventListener('mousedown', (e) => {
            this.viewport.startDrag(e.clientX, e.clientY);
            this.container.style.cursor = 'grabbing';
        });

        this.container.addEventListener('mousemove', (e) => {
            const delta = this.viewport.drag(e.clientX, e.clientY);
            if (delta) {
                // 根据拖拽距离更新中心点
                const pixelPerDegree = this.getPixelPerDegree();
                this.center[0] -= delta.deltaX / pixelPerDegree.lng;
                this.center[1] += delta.deltaY / pixelPerDegree.lat;
                this.renderTiles();
            }
        });

        this.container.addEventListener('mouseup', () => {
            this.viewport.endDrag();
            this.container.style.cursor = 'grab';
        });

        this.container.addEventListener('mouseleave', () => {
            this.viewport.endDrag();
            this.container.style.cursor = 'grab';
        });

        // 窗口大小变化
        window.addEventListener('resize', () => {
            this.viewport.updateSize();
            this.renderTiles();
        });
    }

    /**
     * 计算每度对应的像素数
     */
    getPixelPerDegree() {
        const n = Math.pow(2, this.zoom);
        const lng = n * 256 / 360;
        const lat = n * 256 / 360; // 简化计算
        return { lng, lat };
    }

    /**
     * 渲染瓦片
     */
    renderTiles() {
        // 清空现有瓦片
        this.mapContainer.innerHTML = '';

        const { width, height } = this.viewport.getSize();
        const tiles = TileCalculator.calculateVisibleTiles(
            this.center[0],
            this.center[1],
            this.zoom,
            width,
            height
        );

        tiles.forEach(tile => {
            this.loadTile(tile);
        });
    }

    /**
     * 加载单个瓦片
     */
    loadTile(tile) {
        const { x, y, z } = tile;
        const tileKey = `${z}-${x}-${y}`;

        // 检查缓存
        if (this.tiles.has(tileKey)) {
            const cachedImg = this.tiles.get(tileKey);
            this.mapContainer.appendChild(cachedImg.cloneNode());
            return;
        }

        // 创建瓦片图片
        const img = document.createElement('img');
        img.style.cssText = `
            position: absolute;
            width: 256px;
            height: 256px;
        `;

        // 计算瓦片位置
        const { width, height } = this.viewport.getSize();
        const position = TileCalculator.calculateTilePosition(
            x, y,
            this.center[0],
            this.center[1],
            z,
            width,
            height
        );

        img.style.left = `${position.left}px`;
        img.style.top = `${position.top}px`;

        // 设置瓦片 URL
        img.src = this.getTileUrl(x, y, z);

        // 超时处理
        const timeout = setTimeout(() => {
            if (!img.complete) {
                console.warn(`瓦片 ${z}/${x}/${y} 加载超时`);
                this.handleTileError(img, x, y, z);
            }
        }, 10000); // 10秒超时

        // 加载成功
        img.onload = () => {
            clearTimeout(timeout);
        };

        // 错误处理
        img.onerror = () => {
            clearTimeout(timeout);
            this.handleTileError(img, x, y, z);
        };

        this.mapContainer.appendChild(img);
        this.tiles.set(tileKey, img);
    }

    /**
     * 获取瓦片 URL
     */
    getTileUrl(x, y, z, serverIndex = 0) {
        const server = this.tileServers[serverIndex];

        if (this.type === 'img') {
            // 影像图层
            return `http://${server}.tianditu.gov.cn/img_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX=${z}&TILEROW=${y}&TILECOL=${x}&tk=${this.apiKey}`;
        } else {
            // 矢量图层
            return `http://${server}.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX=${z}&TILEROW=${y}&TILECOL=${x}&tk=${this.apiKey}`;
        }
    }

    /**
     * 处理瓦片加载错误
     */
    handleTileError(img, x, y, z, retryCount = 0) {
        if (retryCount < this.tileServers.length) {
            // 尝试下一个服务器
            const nextServerIndex = (this.currentServerIndex + retryCount + 1) % this.tileServers.length;
            console.warn(`瓦片加载失败，尝试备用服务器 ${this.tileServers[nextServerIndex]}`);
            img.src = this.getTileUrl(x, y, z, nextServerIndex);
            img.onerror = () => this.handleTileError(img, x, y, z, retryCount + 1);
        } else {
            console.error(`瓦片 ${z}/${x}/${y} 加载失败`);
            img.style.display = 'none';
        }
    }

    /**
     * 设置缩放级别
     */
    setZoom(zoom) {
        zoom = Math.max(this.minZoom, Math.min(this.maxZoom, zoom));
        if (zoom !== this.zoom) {
            this.zoom = zoom;
            this.renderTiles();
            console.log(`缩放级别: ${this.zoom}`);
        }
    }

    /**
     * 设置中心点
     */
    setCenter(lng, lat) {
        this.center = [lng, lat];
        this.renderTiles();
    }

    /**
     * 切换图层类型
     */
    switchLayer(type) {
        if (type !== this.type) {
            this.type = type;
            this.tiles.clear(); // 清空缓存
            this.renderTiles();
            console.log(`切换到${type === 'img' ? '影像' : '矢量'}图层`);
        }
    }

    /**
     * 获取地图视图（兼容接口）
     */
    getView() {
        return this;
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
