import { BaseMapEngine } from './BaseMapEngine.js';
import { TileCalculator } from './TileCalculator.js';
import { Projection } from './Projection.js';
import { Viewport } from './Viewport.js';

/**
 * 天地图引擎 - 原生 DOM 实现
 * 支持自定义 reset 按钮、左键拖动、WMTS 瓦片渲染
 */
export class TiandituEngine extends BaseMapEngine {
    constructor(options = {}) {
        super();
        this.supportsCustomReset = true;

        // 地图状态
        this.center = options.center || [116.39, 39.9]; // [lng, lat]
        this.zoom = options.zoom || 5;
        this.minZoom = options.minZoom || 1;
        this.maxZoom = options.maxZoom || 18;
        this.type = options.type || 'img'; // 'img' 或 'vec'

        // API Key
        this.apiKey = '66773e61397afa9c511d62fc259f3e70';

        // 容器和视口
        this.container = null;
        this.mapContainer = null;
        this.viewport = null;

        // 瓦片管理
        this.tiles = new Map();
        this.tileServers = ['t0', 't1', 't2', 't3'];
        this.currentServerIndex = 0;
    }

    /**
     * 初始化地图
     */
    async init(container, options = {}) {
        // 获取容器
        if (typeof container === 'string') {
            this.container = document.getElementById(container);
        } else {
            this.container = container;
        }

        if (!this.container) {
            throw new Error('地图容器不存在');
        }

        // 应用选项
        if (options.center) this.center = options.center;
        if (options.zoom !== undefined) this.zoom = options.zoom;

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

        console.log('✅ 天地图引擎初始化完成');
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

        // 左键拖动
        this.container.addEventListener('mousedown', (e) => {
            if (e.button === 0) { // 左键
                this.viewport.startDrag(e.clientX, e.clientY);
                this.container.style.cursor = 'grabbing';
            }
        });

        this.container.addEventListener('mousemove', (e) => {
            const delta = this.viewport.drag(e.clientX, e.clientY);
            if (delta) {
                // 根据拖拽距离更新中心点
                const pixelPerDegree = this.getPixelPerDegree();
                this.center[0] -= delta.deltaX / pixelPerDegree.lng;
                this.center[1] += delta.deltaY / pixelPerDegree.lat;
                this.renderTiles();
                this.triggerMoveCallbacks(this.center);
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
        const lat = n * 256 / 360;
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
        }, 10000);

        img.onload = () => clearTimeout(timeout);
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
            return `http://${server}.tianditu.gov.cn/img_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX=${z}&TILEROW=${y}&TILECOL=${x}&tk=${this.apiKey}`;
        } else {
            return `http://${server}.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX=${z}&TILEROW=${y}&TILECOL=${x}&tk=${this.apiKey}`;
        }
    }

    /**
     * 处理瓦片加载错误
     */
    handleTileError(img, x, y, z, retryCount = 0) {
        if (retryCount < this.tileServers.length) {
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
     * 设置中心点
     */
    setCenter(center) {
        this.center = center;
        this.renderTiles();
        this.triggerMoveCallbacks(center);
    }

    /**
     * 获取中心点
     */
    getCenter() {
        return this.center;
    }

    /**
     * 设置缩放级别
     */
    setZoom(zoom) {
        zoom = Math.max(this.minZoom, Math.min(this.maxZoom, zoom));
        if (zoom !== this.zoom) {
            this.zoom = zoom;
            this.renderTiles();
            this.triggerZoomCallbacks(zoom);
        }
    }

    /**
     * 获取缩放级别
     */
    getZoom() {
        return this.zoom;
    }

    /**
     * 适配到指定边界
     */
    fitToBounds(bounds) {
        const { minLng, minLat, maxLng, maxLat } = bounds;

        // 计算中心点
        const centerLng = (minLng + maxLng) / 2;
        const centerLat = (minLat + maxLat) / 2;

        // 计算合适的缩放级别
        const { width, height } = this.viewport.getSize();
        const lngDiff = maxLng - minLng;
        const latDiff = maxLat - minLat;

        // 简化的缩放级别计算
        let zoom = this.zoom;
        for (let z = this.maxZoom; z >= this.minZoom; z--) {
            const n = Math.pow(2, z);
            const pixelPerDegreeLng = n * 256 / 360;
            const pixelPerDegreeLat = n * 256 / 360;

            const pixelWidth = lngDiff * pixelPerDegreeLng;
            const pixelHeight = latDiff * pixelPerDegreeLat;

            if (pixelWidth < width * 0.8 && pixelHeight < height * 0.8) {
                zoom = z;
                break;
            }
        }

        this.center = [centerLng, centerLat];
        this.zoom = zoom;
        this.renderTiles();
        this.triggerZoomCallbacks(zoom);
        this.triggerMoveCallbacks(this.center);
    }

    /**
     * 销毁地图实例
     */
    destroy() {
        super.destroy();
        if (this.mapContainer && this.mapContainer.parentNode) {
            this.mapContainer.parentNode.removeChild(this.mapContainer);
        }
        this.tiles.clear();
    }
}
