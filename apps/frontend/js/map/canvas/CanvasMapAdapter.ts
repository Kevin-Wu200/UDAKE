/**
 * Canvas 地图适配器
 * 封装 CanvasMapEngine，实现 MapAdapter 抽象接口
 * 支持矢量绘制、栅格图层和对象拾取
 */
import { MapAdapter } from '../../adapters/MapAdapter';
import { CanvasMapEngine } from './CanvasMapEngine';
import type {
    GeoJSONFeatureCollection,
    SamplingPoint,
    PolygonStyleOptions
} from '../../../types/core';
import type {
    AdapterOptions,
    ClickHandler
} from '../../../types/adapter';
import type { GKCoordinate, CanvasEngineConfig } from '../../../types/map-engine';

/** 图层信息 */
interface CanvasLayer {
    name: string;
    type: 'points' | 'polygon' | 'raster' | 'marker';
    visible: boolean;
    opacity: number;
    zIndex: number;
    data: any;
}

/** 采样点内部表示 */
interface MarkerData {
    gkCoord: GKCoordinate;
    lngLat: [number, number];
    value: number;
    color: number[];
    size: number;
}

/** 多边形内部表示 */
interface PolygonData {
    gkRings: GKCoordinate[][];
    options: PolygonStyleOptions;
}

/** 栅格图层内部表示 */
interface RasterLayerData {
    type: 'prediction' | 'variance';
    image: HTMLImageElement | null;
    gkBounds: { minX: number; minY: number; maxX: number; maxY: number };
    baseUrl: string;
}

/** 采样点点击判定阈值（像素） */
const HIT_THRESHOLD = 12;

/** 默认标记颜色 */
const DEFAULT_MARKER_COLOR = [0, 122, 255, 0.9];
const DEFAULT_MARKER_SIZE = 8;

/** 默认多边形样式 */
const DEFAULT_FILL_COLOR = 'rgba(0, 122, 255, 0.2)';
const DEFAULT_STROKE_COLOR = 'rgba(0, 122, 255, 1)';
const DEFAULT_STROKE_WIDTH = 2;

/**
 * Canvas 地图适配器
 */
export class CanvasMapAdapter extends MapAdapter {
    /** Canvas 引擎 */
    engine: CanvasMapEngine;

    /** 图层存储 */
    private _layers: Map<string, CanvasLayer> = new Map();

    /** 采样点列表 */
    private _samplingPoints: SamplingPoint[] = [];

    /** 标记数据列表 */
    private _markers: MarkerData[] = [];

    /** 点击处理器 */
    private _clickHandler: ClickHandler | null = null;

    /** 是否已初始化 */
    private _initialized: boolean = false;

    /** 容器 ID */
    private _containerId: string = '';

    /** 深色模式标记颜色 */
    private get _markerColor(): number[] {
        return this.engine.isDarkMode()
            ? [0, 188, 212, 0.9]
            : DEFAULT_MARKER_COLOR;
    }

    /** 深色模式描边颜色 */
    private get _strokeColor(): string {
        return this.engine.isDarkMode()
            ? 'rgba(0, 188, 212, 1)'
            : DEFAULT_STROKE_COLOR;
    }

    /** 深色模式填充颜色 */
    private get _fillColor(): string {
        return this.engine.isDarkMode()
            ? 'rgba(0, 188, 212, 0.15)'
            : DEFAULT_FILL_COLOR;
    }

    constructor(config: CanvasEngineConfig = {}) {
        super();
        this.engine = new CanvasMapEngine(config);

        // 设置渲染回调
        this.engine.setRenderCallback(() => this._render());
    }

    /**
     * 初始化地图
     */
    async initMap(containerId: string, options?: AdapterOptions): Promise<any> {
        this._containerId = containerId;

        await this.engine.init(containerId, {
            center: options?.center,
            zoom: options?.zoom
        });

        // 设置点击处理器
        this.engine.setClickHandler((gkCoord, lngLat) => {
            if (this._clickHandler) {
                // 进行拾取测试
                const hit = this._hitTest(gkCoord);
                if (hit) {
                    this._clickHandler(hit, { x: lngLat[0], y: lngLat[1] });
                }
            }
        });

        this._initialized = true;
        console.log('✅ CanvasMapAdapter 初始化完成');
        return this.engine.getMainCanvas();
    }

    getView(): any {
        return this.engine.getMainCanvas();
    }

    getEngine(): CanvasMapEngine {
        return this.engine;
    }

    // ========== 图层管理 ==========

    async addPointsLayer(geojson: GeoJSONFeatureCollection, layerName: string = 'points'): Promise<void> {
        const points: MarkerData[] = [];

        for (const feature of geojson.features) {
            if (feature.geometry.type === 'Point') {
                const [lng, lat] = feature.geometry.coordinates;
                const gkCoord = this.engine.projectionService.toGK(lng, lat);
                const value = feature.properties?.value ?? 0;
                points.push({
                    gkCoord,
                    lngLat: [lng, lat],
                    value,
                    color: [...this._markerColor],
                    size: DEFAULT_MARKER_SIZE
                });
            }
        }

        this._layers.set(layerName, {
            name: layerName,
            type: 'points',
            visible: true,
            opacity: 1,
            zIndex: 100,
            data: points
        });

        // 自动缩放到图层范围
        if (points.length > 0) {
            this._zoomToMarkers(points);
        }

        this._requestRender();
        console.log(`✅ 添加点图层: ${layerName}, ${points.length} 个点`);
    }

    async addRasterLayer(type: 'prediction' | 'variance', url: string): Promise<void> {
        const layerName = type;

        // 移除旧图层
        if (this._layers.has(layerName)) {
            this.removeLayer(layerName);
        }

        const rasterData: RasterLayerData = {
            type,
            image: null,
            gkBounds: { minX: 0, minY: 0, maxX: 0, maxY: 0 },
            baseUrl: url
        };

        this._layers.set(layerName, {
            name: layerName,
            type: 'raster',
            visible: true,
            opacity: 0.7,
            zIndex: 0,
            data: rasterData
        });

        // 异步加载图像
        try {
            await this._fetchRasterImage(layerName);
        } catch (error) {
            console.error(`❌ 加载栅格图层失败: ${layerName}`, error);
        }

        this._requestRender();
    }

    /**
     * 从 ArcGIS ImageryLayer REST API 获取导出图像
     */
    private async _fetchRasterImage(layerName: string): Promise<void> {
        const layer = this._layers.get(layerName);
        if (!layer || layer.type !== 'raster') return;

        const data = layer.data as RasterLayerData;
        const viewport = this.engine.getViewportBounds();
        const canvasSize = this.engine.getCanvasSize();

        // 构建 ArcGIS Export Image 请求
        const bbox = `${viewport.minX},${viewport.minY},${viewport.maxX},${viewport.maxY}`;
        const size = `${canvasSize.width},${canvasSize.height}`;
        const exportUrl = `${data.baseUrl}/exportImage?` +
            `bbox=${bbox}&bboxSR=3857&imageSR=3857&size=${encodeURIComponent(size)}` +
            `&format=png&transparent=true&f=image`;

        try {
            const response = await fetch(exportUrl);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const blob = await response.blob();
            const imageUrl = URL.createObjectURL(blob);

            const img = new Image();
            await new Promise<void>((resolve, reject) => {
                img.onload = () => resolve();
                img.onerror = () => reject(new Error('图像加载失败'));
                img.src = imageUrl;
            });

            data.image = img;
            data.gkBounds = {
                minX: viewport.minX,
                minY: viewport.minY,
                maxX: viewport.maxX,
                maxY: viewport.maxY
            };

            this._requestRender();
            console.log(`✅ 栅格图层加载完成: ${layerName}`);
        } catch (error) {
            console.error(`❌ 获取栅格图像失败: ${layerName}`, error);
            throw error;
        }
    }

    async addMarker(pointData: SamplingPoint): Promise<void> {
        // SamplingPoint 使用 x/y 表示经纬度
        const gkCoord = this.engine.projectionService.toGK(pointData.x, pointData.y);

        const marker: MarkerData = {
            gkCoord,
            lngLat: [pointData.x, pointData.y],
            value: pointData.value,
            color: [...this._markerColor],
            size: DEFAULT_MARKER_SIZE
        };

        this._markers.push(marker);
        this._samplingPoints.push(pointData);

        // 添加到标记图层
        let markerLayer = this._layers.get('__markers__');
        if (!markerLayer) {
            this._layers.set('__markers__', {
                name: '__markers__',
                type: 'marker',
                visible: true,
                opacity: 1,
                zIndex: 200,
                data: []
            });
            markerLayer = this._layers.get('__markers__')!;
        }
        (markerLayer.data as MarkerData[]).push(marker);

        this._requestRender();
    }

    async addPolygon(coordinates: number[][][], options: PolygonStyleOptions = {}): Promise<any> {
        // coordinates: 三维数组 [ring][point][lng, lat]
        const gkRings: GKCoordinate[][] = coordinates.map(ring =>
            ring.map(([lng, lat]) => this.engine.projectionService.toGK(lng, lat))
        );

        const polygonData: PolygonData = {
            gkRings,
            options
        };

        const layerName = `polygon_${Date.now()}`;
        this._layers.set(layerName, {
            name: layerName,
            type: 'polygon',
            visible: true,
            opacity: options.fillOpacity ?? 0.2,
            zIndex: 150,
            data: polygonData
        });

        this._requestRender();
        return { layerName };
    }

    toggleLayer(layerName: string, visible: boolean): void {
        const layer = this._layers.get(layerName);
        if (layer) {
            layer.visible = visible;
            this._requestRender();
        }
    }

    setLayerOpacity(layerName: string, opacity: number): void {
        const layer = this._layers.get(layerName);
        if (layer) {
            layer.opacity = Math.max(0, Math.min(1, opacity));
            if (layer.type === 'polygon') {
                (layer.data as PolygonData).options.fillOpacity = layer.opacity;
            }
            this._requestRender();
        }
    }

    setLayerZIndex(layerName: string, zIndex: number): void {
        const layer = this._layers.get(layerName);
        if (layer) {
            layer.zIndex = zIndex;
            this._requestRender();
        }
    }

    removeLayer(layerName: string): void {
        if (this._layers.has(layerName)) {
            // 清理栅格图层中的 Blob URL
            const layer = this._layers.get(layerName)!;
            if (layer.type === 'raster') {
                const data = layer.data as RasterLayerData;
                if (data.image && data.image.src.startsWith('blob:')) {
                    URL.revokeObjectURL(data.image.src);
                }
            }
            this._layers.delete(layerName);
            this._requestRender();
        }
    }

    clearAllLayers(): void {
        // 清理所有栅格 Blob URL
        for (const [, layer] of this._layers) {
            if (layer.type === 'raster') {
                const data = layer.data as RasterLayerData;
                if (data.image && data.image.src.startsWith('blob:')) {
                    URL.revokeObjectURL(data.image.src);
                }
            }
        }
        this._layers.clear();
        this._markers = [];
        this._samplingPoints = [];
        this._requestRender();
    }

    zoomToLayer(layerName: string): void {
        const layer = this._layers.get(layerName);
        if (!layer) return;

        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

        if (layer.type === 'points') {
            const points = layer.data as MarkerData[];
            for (const p of points) {
                minX = Math.min(minX, p.gkCoord.x);
                minY = Math.min(minY, p.gkCoord.y);
                maxX = Math.max(maxX, p.gkCoord.x);
                maxY = Math.max(maxY, p.gkCoord.y);
            }
        } else if (layer.type === 'polygon') {
            const poly = layer.data as PolygonData;
            for (const ring of poly.gkRings) {
                for (const p of ring) {
                    minX = Math.min(minX, p.x);
                    minY = Math.min(minY, p.y);
                    maxX = Math.max(maxX, p.x);
                    maxY = Math.max(maxY, p.y);
                }
            }
        } else if (layer.type === 'raster') {
            return; // 栅格图层不支持缩放到范围
        }

        if (isFinite(minX)) {
            const canvasSize = this.engine.getCanvasSize();
            const result = this.engine.projectionService.fitToGKBounds(
                { minX, minY, maxX, maxY },
                canvasSize.width,
                canvasSize.height
            );
            // 通过设置偏移和比例来模拟 fitToBounds
            // 直接操作引擎内部属性（通过 setCenter 和 setZoom）
            const centerX = (minX + maxX) / 2;
            const centerY = (minY + maxY) / 2;
            const [lng, lat] = this.engine.projectionService.fromGK(centerX, centerY);
            this.engine.setCenter([lng, lat]);

            // 计算合适的缩放级别
            const boundWidth = maxX - minX;
            const boundHeight = maxY - minY;
            const scaleFromBounds = Math.min(
                canvasSize.width / (boundWidth * 1.2),
                canvasSize.height / (boundHeight * 1.2)
            );
            const targetZoom = Math.log2(scaleFromBounds * 500000); // 基于 ZOOM_SCALE_BASE
            this.engine.setZoom(Math.round(targetZoom));
        }
    }

    setClickHandler(handler: ClickHandler): void {
        this._clickHandler = handler;
    }

    getSamplingPoints(): SamplingPoint[] {
        return this._samplingPoints;
    }

    /**
     * 刷新栅格图层（视口变化后重新请求图像）
     */
    async refreshRasterLayers(): Promise<void> {
        const promises: Promise<void>[] = [];
        for (const [name, layer] of this._layers) {
            if (layer.type === 'raster' && layer.visible) {
                promises.push(this._fetchRasterImage(name));
            }
        }
        await Promise.allSettled(promises);
    }

    // ========== 渲染 ==========

    /**
     * 主渲染函数，由引擎的渲染回调触发
     */
    private _render(): void {
        const ctx = this.engine.getOffscreenContext();
        if (!ctx) return;

        const { width, height } = this.engine.getCanvasSize();
        const dpr = window.devicePixelRatio || 1;

        // 清空离屏画布
        ctx.clearRect(0, 0, width, height);

        // 按 zIndex 排序图层
        const sortedLayers = Array.from(this._layers.values())
            .sort((a, b) => a.zIndex - b.zIndex);

        for (const layer of sortedLayers) {
            if (!layer.visible) continue;

            ctx.save();
            ctx.globalAlpha = layer.opacity;

            try {
                switch (layer.type) {
                    case 'raster':
                        this._renderRasterLayer(ctx, layer.data as RasterLayerData, width, height, dpr);
                        break;
                    case 'polygon':
                        this._renderPolygon(ctx, layer.data as PolygonData, width, height);
                        break;
                    case 'points':
                        this._renderMarkers(ctx, layer.data as MarkerData[], width, height, dpr);
                        break;
                    case 'marker':
                        this._renderMarkers(ctx, layer.data as MarkerData[], width, height, dpr);
                        break;
                }
            } catch (error) {
                console.error(`渲染图层 ${layer.name} 失败:`, error);
            }

            ctx.restore();
        }

        // 渲染独立标记（不在图层中的）
        if (!this._layers.has('__markers__') && this._markers.length > 0) {
            ctx.save();
            this._renderMarkers(ctx, this._markers, width, height, dpr);
            ctx.restore();
        }
    }

    /**
     * 渲染栅格图层
     */
    private _renderRasterLayer(
        ctx: CanvasRenderingContext2D,
        data: RasterLayerData,
        width: number,
        height: number,
        _dpr: number
    ): void {
        if (!data.image) return;

        const offsetX = this.engine.getOffsetX();
        const offsetY = this.engine.getOffsetY();
        const scale = this.engine.getScale();

        // 计算图像在画布上的位置和尺寸
        const imgBounds = data.gkBounds;
        const imgPixelX = (imgBounds.minX - offsetX) * scale;
        const imgPixelY = height - (imgBounds.maxY - offsetY) * scale;
        const imgPixelW = (imgBounds.maxX - imgBounds.minX) * scale;
        const imgPixelH = (imgBounds.maxY - imgBounds.minY) * scale;

        ctx.drawImage(data.image, imgPixelX, imgPixelY, imgPixelW, imgPixelH);
    }

    /**
     * 渲染多边形
     */
    private _renderPolygon(
        ctx: CanvasRenderingContext2D,
        data: PolygonData,
        width: number,
        height: number
    ): void {
        const offsetX = this.engine.getOffsetX();
        const offsetY = this.engine.getOffsetY();
        const scale = this.engine.getScale();

        const { gkRings, options } = data;

        ctx.beginPath();

        for (let i = 0; i < gkRings.length; i++) {
            const ring = gkRings[i];
            if (ring.length === 0) continue;

            const [px, py] = this._gkToCanvasPixel(ring[0].x, ring[0].y, offsetX, offsetY, scale, height);

            if (i === 0) {
                ctx.moveTo(px, py);
            } else {
                // 内部环（孔）使用逆向路径
                ctx.moveTo(px, py);
            }

            for (let j = 1; j < ring.length; j++) {
                const [x, y] = this._gkToCanvasPixel(ring[j].x, ring[j].y, offsetX, offsetY, scale, height);
                ctx.lineTo(x, y);
            }

            ctx.closePath();
        }

        // 填充
        ctx.fillStyle = typeof options.fillColor === 'string'
            ? options.fillColor
            : this._fillColor;
        ctx.fill();

        // 描边
        ctx.strokeStyle = typeof options.strokeColor === 'string'
            ? options.strokeColor
            : this._strokeColor;
        ctx.lineWidth = (options.strokeWidth ?? DEFAULT_STROKE_WIDTH) * Math.max(0.5, scale / 0.0001);
        ctx.stroke();
    }

    /**
     * 渲染采样点标记
     */
    private _renderMarkers(
        ctx: CanvasRenderingContext2D,
        markers: MarkerData[],
        width: number,
        height: number,
        _dpr: number
    ): void {
        const offsetX = this.engine.getOffsetX();
        const offsetY = this.engine.getOffsetY();
        const scale = this.engine.getScale();

        for (const marker of markers) {
            const [px, py] = this._gkToCanvasPixel(
                marker.gkCoord.x, marker.gkCoord.y,
                offsetX, offsetY, scale, height
            );

            // 裁剪优化：跳过视口外的点
            if (px < -50 || px > width + 50 || py < -50 || py > height + 50) continue;

            const [r, g, b, a] = marker.color;
            const size = Math.max(4, marker.size * Math.min(2, scale / 0.00005));

            // 绘制外圈光晕
            ctx.beginPath();
            ctx.arc(px, py, size + 3, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${a * 0.3})`;
            ctx.fill();

            // 绘制实心圆
            ctx.beginPath();
            ctx.arc(px, py, size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${a})`;
            ctx.fill();

            // 绘制白色边框
            ctx.beginPath();
            ctx.arc(px, py, size, 0, Math.PI * 2);
            ctx.strokeStyle = this.engine.isDarkMode()
                ? 'rgba(30, 30, 46, 0.9)'
                : 'rgba(255, 255, 255, 0.9)';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }
    }

    // ========== 坐标系转换工具 ==========

    private _gkToCanvasPixel(
        gkX: number,
        gkY: number,
        offsetX: number,
        offsetY: number,
        scale: number,
        canvasHeight: number
    ): [number, number] {
        return this.engine.projectionService.gkToPixel(gkX, gkY, offsetX, offsetY, scale, canvasHeight);
    }

    // ========== 对象拾取 ==========

    /**
     * 基于距离和包含关系的拾取测试
     * 优先级：标记 > 多边形 > 点图层
     */
    private _hitTest(gkCoord: GKCoordinate): any {
        // 1. 检测独立标记（最近优先）
        let nearestMarker: { marker: MarkerData; distance: number } | null = null;

        for (const marker of this._markers) {
            const dist = this.engine.projectionService.distanceBetween(gkCoord, marker.gkCoord);
            const pixelThreshold = HIT_THRESHOLD / this.engine.getScale();
            if (dist < pixelThreshold) {
                if (!nearestMarker || dist < nearestMarker.distance) {
                    nearestMarker = { marker, distance: dist };
                }
            }
        }

        if (nearestMarker) {
            return {
                type: 'marker',
                lngLat: nearestMarker.marker.lngLat,
                value: nearestMarker.marker.value,
                attributes: {
                    x: nearestMarker.marker.lngLat[0],
                    y: nearestMarker.marker.lngLat[1],
                    value: nearestMarker.marker.value
                }
            };
        }

        // 2. 检测多边形（射线法）
        for (const [, layer] of this._layers) {
            if (layer.type === 'polygon' && layer.visible) {
                const data = layer.data as PolygonData;
                if (this._pointInPolygon(gkCoord, data.gkRings[0])) {
                    return {
                        type: 'polygon',
                        layerName: layer.name,
                        options: data.options
                    };
                }
            }
        }

        // 3. 检测点图层
        for (const [, layer] of this._layers) {
            if (layer.type === 'points' && layer.visible) {
                const points = layer.data as MarkerData[];
                for (const point of points) {
                    const dist = this.engine.projectionService.distanceBetween(gkCoord, point.gkCoord);
                    const pixelThreshold = HIT_THRESHOLD / this.engine.getScale();
                    if (dist < pixelThreshold) {
                        return {
                            type: 'point',
                            lngLat: point.lngLat,
                            value: point.value,
                            attributes: {
                                x: point.lngLat[0],
                                y: point.lngLat[1],
                                value: point.value
                            }
                        };
                    }
                }
            }
        }

        return null;
    }

    /**
     * 射线法判断点是否在多边形内
     */
    private _pointInPolygon(point: GKCoordinate, polygon: GKCoordinate[]): boolean {
        let inside = false;
        const n = polygon.length;

        for (let i = 0, j = n - 1; i < n; j = i++) {
            const xi = polygon[i].x, yi = polygon[i].y;
            const xj = polygon[j].x, yj = polygon[j].y;

            const intersect = ((yi > point.y) !== (yj > point.y))
                && (point.x < (xj - xi) * (point.y - yi) / (yj - yi) + xi);

            if (intersect) inside = !inside;
        }

        return inside;
    }

    // ========== 辅助方法 ==========

    private _requestRender(): void {
        // 引擎的渲染回调会自动触发渲染
    }

    /**
     * 缩放到标记点范围
     */
    private _zoomToMarkers(markers: MarkerData[]): void {
        if (markers.length === 0) return;

        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (const m of markers) {
            minX = Math.min(minX, m.gkCoord.x);
            minY = Math.min(minY, m.gkCoord.y);
            maxX = Math.max(maxX, m.gkCoord.x);
            maxY = Math.max(maxY, m.gkCoord.y);
        }

        if (markers.length === 1) {
            // 单个点，直接设置为中心
            this.engine.setCenter(markers[0].lngLat);
            this.engine.setZoom(14);
        } else {
            const centerX = (minX + maxX) / 2;
            const centerY = (minY + maxY) / 2;
            const [lng, lat] = this.engine.projectionService.fromGK(centerX, centerY);
            this.engine.setCenter([lng, lat]);

            const canvasSize = this.engine.getCanvasSize();
            const boundWidth = maxX - minX;
            const boundHeight = maxY - minY;
            const scaleFromBounds = Math.min(
                canvasSize.width / (boundWidth * 1.2),
                canvasSize.height / (boundHeight * 1.2)
            );
            const targetZoom = Math.log2(scaleFromBounds * 500000);
            this.engine.setZoom(Math.min(16, Math.round(targetZoom)));
        }
    }

    // ========== 销毁 ==========

    destroy(): void {
        this.clearAllLayers();
        this._clickHandler = null;
        this.engine.destroy();
        this._initialized = false;
        console.log('✅ CanvasMapAdapter 已销毁');
    }
}
