/**
 * 地图测量工具组件
 * 支持距离测量和面积测量
 */

import type { MapPoint } from '../../types/app';

/** 测量类型 */
export type MeasureType = 'distance' | 'area';

/** 测量单位 */
export type MeasureUnit = 'm' | 'km' | 'm²' | 'km²';

/** 测量点 */
export interface MeasurePoint {
    coordinate: MapPoint;
    marker: any;
    label: HTMLElement | null;
}

/** 测量线段 */
export interface MeasureSegment {
    from: MeasurePoint;
    to: MeasurePoint;
    line: any;
    distance: number;
    label: HTMLElement | null;
}

/** 测量多边形 */
export interface MeasurePolygon {
    points: MeasurePoint[];
    polygon: any;
    area: number;
    label: HTMLElement | null;
}

/** 测量结果 */
export interface MeasureResult {
    type: MeasureType;
    unit: MeasureUnit;
    totalDistance?: number;
    segments?: MeasureSegment[];
    area?: number;
    points: MapPoint[];
}

/** 测量工具配置 */
export interface MeasureToolConfig {
    defaultUnit?: 'm' | 'km';
    showLabels?: boolean;
    snapToFeatures?: boolean;
}

/** 测量工具事件 */
export interface MeasureToolEvents {
    onMeasureComplete?: (result: MeasureResult) => void;
    onMeasureUpdate?: (result: MeasureResult) => void;
    onMeasureClear?: () => void;
}

export class MeasureTool {
    private container: HTMLElement | null;
    private isActive: boolean;
    private currentType: MeasureType | null;
    private points: MeasurePoint[];
    private segments: MeasureSegment[];
    private polygon: MeasurePolygon | null;
    private config: Required<MeasureToolConfig>;
    private events: MeasureToolEvents;
    private mapProvider: string;
    private mapEngine: any;

    constructor(config: MeasureToolConfig = {}, events: MeasureToolEvents = {}) {
        this.container = null;
        this.isActive = false;
        this.currentType = null;
        this.points = [];
        this.segments = [];
        this.polygon = null;
        this.config = {
            defaultUnit: config.defaultUnit ?? 'm',
            showLabels: config.showLabels ?? true,
            snapToFeatures: config.snapToFeatures ?? false
        };
        this.events = events;
        this.mapProvider = 'geoscene'; // 默认值，会在 init 时更新
        this.mapEngine = null;
    }

    /**
     * 初始化测量工具
     * @param mapEngine - 地图引擎实例
     * @param mapProvider - 地图提供商
     */
    init(mapEngine: any, mapProvider: string): void {
        this.mapEngine = mapEngine;
        this.mapProvider = mapProvider;
    }

    /**
     * 创建测量工具面板
     * @returns 面板元素
     */
    createPanel(): HTMLElement {
        this.container = document.createElement('div');
        this.container.className = 'measure-tool-panel';
        this.container.innerHTML = `
            <div class="measure-header">
                <h3 class="measure-title">测量工具</h3>
                <button class="close-btn" aria-label="关闭">✕</button>
            </div>
            <div class="measure-content">
                <div class="measure-type-selector">
                    <button class="measure-type-btn" data-type="distance">
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                            <path d="M2 10h16M10 2v16" stroke="currentColor" stroke-width="2"/>
                        </svg>
                        <span>距离</span>
                    </button>
                    <button class="measure-type-btn" data-type="area">
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                            <rect x="2" y="2" width="16" height="16" rx="2" stroke="currentColor" stroke-width="2" fill="none"/>
                        </svg>
                        <span>面积</span>
                    </button>
                </div>
                <div class="measure-status" id="measure-status"></div>
                <div class="measure-result" id="measure-result" style="display: none;">
                    <div class="result-item" id="total-result"></div>
                    <div class="result-details" id="result-details"></div>
                </div>
                <div class="measure-actions">
                    <button class="btn btn-secondary btn-sm" id="undo-btn" disabled>撤销上一点</button>
                    <button class="btn btn-secondary btn-sm" id="clear-btn" disabled>清除测量</button>
                    <button class="btn btn-primary btn-sm" id="export-btn" disabled>导出结果</button>
                </div>
            </div>
        `;

        this.addStyles();
        this.bindEvents();

        return this.container;
    }

    /**
     * 添加样式
     */
    private addStyles(): void {
        if (document.querySelector('#measure-tool-styles')) return;

        const style = document.createElement('style');
        style.id = 'measure-tool-styles';
        style.textContent = `
            .measure-tool-panel {
                position: absolute;
                top: 70px;
                left: 10px;
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                padding: 16px;
                z-index: 1000;
                min-width: 280px;
            }

            .measure-tool-panel .measure-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 12px;
            }

            .measure-tool-panel .measure-title {
                margin: 0;
                font-size: 16px;
                font-weight: 600;
                color: var(--text-primary, #1d1d1f);
            }

            .measure-tool-panel .close-btn {
                width: 24px;
                height: 24px;
                border: none;
                background: var(--bg-secondary, #f5f5f7);
                border-radius: 4px;
                cursor: pointer;
                color: var(--text-secondary, #86868b);
                transition: all 0.2s ease;
            }

            .measure-tool-panel .close-btn:hover {
                background: var(--bg-tertiary, #e8e8ed);
            }

            .measure-tool-panel .measure-type-selector {
                display: flex;
                gap: 8px;
                margin-bottom: 12px;
            }

            .measure-tool-panel .measure-type-btn {
                flex: 1;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                padding: 10px;
                border: 1px solid var(--border-color, #e5e5e5);
                background: var(--bg-primary, #ffffff);
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.2s ease;
                color: var(--text-primary, #1d1d1f);
            }

            .measure-tool-panel .measure-type-btn:hover {
                background: var(--bg-secondary, #f5f5f7);
            }

            .measure-tool-panel .measure-type-btn.active {
                background: var(--primary-color, #007aff);
                color: white;
                border-color: var(--primary-color, #007aff);
            }

            .measure-tool-panel .measure-status {
                font-size: 13px;
                color: var(--text-secondary, #86868b);
                margin-bottom: 12px;
                min-height: 20px;
            }

            .measure-tool-panel .measure-result {
                background: var(--bg-secondary, #f5f5f7);
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 12px;
            }

            .measure-tool-panel .result-item {
                font-size: 14px;
                font-weight: 600;
                color: var(--text-primary, #1d1d1f);
                margin-bottom: 8px;
            }

            .measure-tool-panel .result-details {
                font-size: 12px;
                color: var(--text-secondary, #86868b);
            }

            .measure-tool-panel .result-detail-item {
                display: flex;
                justify-content: space-between;
                padding: 4px 0;
            }

            .measure-tool-panel .measure-actions {
                display: flex;
                gap: 8px;
            }

            .measure-tool-panel .btn-sm {
                flex: 1;
                padding: 8px 12px;
                font-size: 12px;
                height: 32px;
            }

            /* 测量标记样式 */
            .measure-marker {
                width: 12px;
                height: 12px;
                background: var(--primary-color, #007aff);
                border: 2px solid white;
                border-radius: 50%;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            }

            .measure-label {
                background: rgba(255, 255, 255, 0.9);
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
                color: var(--text-primary, #1d1d1f);
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                white-space: nowrap;
            }

            .measure-line {
                stroke: var(--primary-color, #007aff);
                stroke-width: 2;
                stroke-dasharray: 5, 5;
            }

            .measure-polygon {
                fill: var(--primary-color, #007aff);
                fill-opacity: 0.2;
                stroke: var(--primary-color, #007aff);
                stroke-width: 2;
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        if (!this.container) return;

        const closeBtn = this.container.querySelector('.close-btn');
        const typeBtns = this.container.querySelectorAll('.measure-type-btn');
        const undoBtn = this.container.querySelector('#undo-btn');
        const clearBtn = this.container.querySelector('#clear-btn');
        const exportBtn = this.container.querySelector('#export-btn');

        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.deactivate());
        }

        typeBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const type = (e.currentTarget as HTMLElement).dataset.type as MeasureType;
                if (type) {
                    this.activate(type);
                }
            });
        });

        if (undoBtn) {
            undoBtn.addEventListener('click', () => this.undoLastPoint());
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clear());
        }

        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportResult());
        }
    }

    /**
     * 激活测量工具
     * @param type - 测量类型
     */
    activate(type: MeasureType): void {
        if (this.isActive && this.currentType === type) {
            this.deactivate();
            return;
        }

        this.isActive = true;
        this.currentType = type;

        // 更新 UI
        if (this.container) {
            const typeBtns = this.container.querySelectorAll('.measure-type-btn');
            typeBtns.forEach(btn => {
                btn.classList.toggle('active', (btn as HTMLElement).dataset.type === type);
            });

            const statusDiv = this.container.querySelector('#measure-status') as HTMLElement;
            statusDiv.textContent = type === 'distance' ? '点击地图添加测量点' : '点击地图添加多边形顶点';
        }

        // 设置地图点击事件
        this.setupMapClickHandler();
    }

    /**
     * 停用测量工具
     */
    deactivate(): void {
        this.isActive = false;
        this.currentType = null;

        // 移除地图点击事件
        this.removeMapClickHandler();

        // 更新 UI
        if (this.container) {
            const typeBtns = this.container.querySelectorAll('.measure-type-btn');
            typeBtns.forEach(btn => {
                btn.classList.remove('active');
            });

            const statusDiv = this.container.querySelector('#measure-status') as HTMLElement;
            statusDiv.textContent = '';
        }
    }

    /**
     * 设置地图点击事件处理器
     */
    private setupMapClickHandler(): void {
        if (!this.mapEngine) return;

        const clickHandler = (event: any) => {
            if (!this.isActive) return;

            // 获取点击坐标
            const mapPoint = this.extractMapPoint(event);
            if (!mapPoint) return;

            // 添加测量点
            this.addPoint(mapPoint);
        };

        // 根据不同的地图引擎绑定事件
        if (this.mapProvider === 'geoscene') {
            const view = this.mapEngine.view;
            if (view) {
                view.on('click', clickHandler);
                // 将 clickHandler 保存以便后续移除
                (view as any)._measureClickHandler = clickHandler;
            }
        } else if (this.mapProvider === 'amap') {
            const map = this.mapEngine.map;
            if (map) {
                map.on('click', clickHandler);
                // 将 clickHandler 保存以便后续移除
                (map as any)._measureClickHandler = clickHandler;
            }
        }
    }

    /**
     * 移除地图点击事件处理器
     */
    private removeMapClickHandler(): void {
        if (!this.mapEngine) return;

        if (this.mapProvider === 'geoscene') {
            const view = this.mapEngine.view;
            if (view && (view as any)._measureClickHandler) {
                view.off('click', (view as any)._measureClickHandler);
                delete (view as any)._measureClickHandler;
            }
        } else if (this.mapProvider === 'amap') {
            const map = this.mapEngine.map;
            if (map && (map as any)._measureClickHandler) {
                map.off('click', (map as any)._measureClickHandler);
                delete (map as any)._measureClickHandler;
            }
        }
    }

    /**
     * 从事件中提取地图点
     * @param event - 地图事件
     * @returns 地图点
     */
    private extractMapPoint(event: any): MapPoint | null {
        if (this.mapProvider === 'geoscene') {
            return {
                longitude: event.mapPoint.longitude,
                latitude: event.mapPoint.latitude
            };
        } else if (this.mapProvider === 'amap') {
            return {
                longitude: event.lnglat.lng,
                latitude: event.lnglat.lat
            };
        }
        return null;
    }

    /**
     * 添加测量点
     * @param mapPoint - 地图点
     */
    private addPoint(mapPoint: MapPoint): void {
        // 创建标记
        const marker = this.createMarker(mapPoint);
        const label = this.config.showLabels ? this.createLabel(`${this.points.length + 1}`, mapPoint) : null;

        const point: MeasurePoint = {
            coordinate: mapPoint,
            marker,
            label
        };

        this.points.push(point);

        // 如果是距离测量，添加线段
        if (this.currentType === 'distance' && this.points.length > 1) {
            const prevPoint = this.points[this.points.length - 2];
            const segment = this.createSegment(prevPoint, point);
            this.segments.push(segment);
        }

        // 如果是面积测量，更新多边形
        if (this.currentType === 'area' && this.points.length >= 3) {
            this.updatePolygon();
        }

        // 更新 UI
        this.updateUI();

        // 触发更新事件
        if (this.events.onMeasureUpdate) {
            this.events.onMeasureUpdate(this.getResult());
        }
    }

    /**
     * 创建标记
     * @param mapPoint - 地图点
     * @returns 标记对象
     */
    private createMarker(mapPoint: MapPoint): any {
        if (this.mapProvider === 'geoscene') {
            // 动态导入 ArcGIS 模块
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            return import('@geoscene/core/Graphic').then(({ default: Graphic }) => {
                // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
                return import('@geoscene/core/geometry/Point').then(({ default: Point }) => {
                    // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
                    return import('@geoscene/core/symbols/SimpleMarkerSymbol').then(({ default: SimpleMarkerSymbol }) => {
                        const point = new Point({
                            longitude: mapPoint.longitude,
                            latitude: mapPoint.latitude
                        });

                        const symbol = new SimpleMarkerSymbol({
                            color: [0, 122, 255],
                            size: 12,
                            outline: { color: [255, 255, 255, 1], width: 2 }
                        });

                        const graphic = new Graphic({ geometry: point, symbol: symbol });
                        this.mapEngine.view.graphics.add(graphic);
                        return graphic;
                    });
                });
            });
        } else if (this.mapProvider === 'amap') {
            const marker = new (window as any).AMap.Marker({
                position: [mapPoint.longitude, mapPoint.latitude],
                content: '<div class="measure-marker"></div>',
                offset: new (window as any).AMap.Pixel(-6, -6)
            });
            this.mapEngine.map.add(marker);
            return marker;
        }

        return null;
    }

    /**
     * 创建标签
     * @param text - 标签文本
     * @param mapPoint - 地图点
     * @returns 标签元素
     */
    private createLabel(text: string, mapPoint: MapPoint): HTMLElement | null {
        const label = document.createElement('div');
        label.className = 'measure-label';
        label.textContent = text;

        // 计算屏幕位置
        const screenPosition = this.mapPointToScreen(mapPoint);
        if (screenPosition) {
            label.style.position = 'absolute';
            label.style.left = `${screenPosition.x}px`;
            label.style.top = `${screenPosition.y - 20}px`;
            label.style.zIndex = '1000';

            const mapContainer = document.querySelector('.map-container');
            if (mapContainer) {
                mapContainer.appendChild(label);
            }
        }

        return label;
    }

    /**
     * 创建线段
     * @param from - 起点
     * @param to - 终点
     * @returns 线段对象
     */
    private createSegment(from: MeasurePoint, to: MeasurePoint): MeasureSegment {
        const distance = this.calculateDistance(from.coordinate, to.coordinate);
        const line = this.createLine(from.coordinate, to.coordinate);
        const label = this.config.showLabels ? this.createLabel(this.formatDistance(distance), to.coordinate) : null;

        return {
            from,
            to,
            line,
            distance,
            label
        };
    }

    /**
     * 创建线
     * @param from - 起点
     * @param to - 终点
     * @returns 线对象
     */
    private createLine(from: MapPoint, to: MapPoint): any {
        if (this.mapProvider === 'geoscene') {
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            return import('@geoscene/core/Graphic').then(({ default: Graphic }) => {
                // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
                return import('@geoscene/core/geometry/Polyline').then(({ default: Polyline }) => {
                    // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
                    return import('@geoscene/core/symbols/SimpleLineSymbol').then(({ default: SimpleLineSymbol }) => {
                        const polyline = new Polyline({
                            paths: [[[from.longitude, from.latitude], [to.longitude, to.latitude]]]
                        });

                        const symbol = new SimpleLineSymbol({
                            color: [0, 122, 255],
                            width: 2,
                            style: 'dash'
                        });

                        const graphic = new Graphic({ geometry: polyline, symbol: symbol });
                        this.mapEngine.view.graphics.add(graphic);
                        return graphic;
                    });
                });
            });
        } else if (this.mapProvider === 'amap') {
            const polyline = new (window as any).AMap.Polyline({
                path: [
                    [from.longitude, from.latitude],
                    [to.longitude, to.latitude]
                ],
                strokeColor: '#007aff',
                strokeWeight: 2,
                strokeStyle: 'dashed'
            });
            this.mapEngine.map.add(polyline);
            return polyline;
        }

        return null;
    }

    /**
     * 更新多边形
     */
    private updatePolygon(): void {
        if (this.polygon && this.polygon.polygon) {
            // 移除旧的多边形
            if (this.mapProvider === 'geoscene') {
                this.mapEngine.view.graphics.remove(this.polygon.polygon);
            } else if (this.mapProvider === 'amap') {
                this.mapEngine.map.remove(this.polygon.polygon);
            }
        }

        // 创建新的多边形
        const path = this.points.map(p => [p.coordinate.longitude, p.coordinate.latitude]);
        const polygon = this.createPolygon(path);
        const area = this.calculateArea(this.points.map(p => p.coordinate));
        const label = this.config.showLabels ? this.createLabel(this.formatArea(area), this.points[0].coordinate) : null;

        this.polygon = {
            points: this.points,
            polygon,
            area,
            label
        };
    }

    /**
     * 创建多边形
     * @param path - 路径
     * @returns 多边形对象
     */
    private createPolygon(path: number[][]): any {
        if (this.mapProvider === 'geoscene') {
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            return import('@geoscene/core/Graphic').then(({ default: Graphic }) => {
                // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
                return import('@geoscene/core/geometry/Polygon').then(({ default: Polygon }) => {
                    // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
                    return import('@geoscene/core/symbols/SimpleFillSymbol').then(({ default: SimpleFillSymbol }) => {
                        const polygon = new Polygon({
                            rings: [path]
                        });

                        const symbol = new SimpleFillSymbol({
                            color: [0, 122, 255, 0.2],
                            outline: { color: [0, 122, 255], width: 2 }
                        });

                        const graphic = new Graphic({ geometry: polygon, symbol: symbol });
                        this.mapEngine.view.graphics.add(graphic);
                        return graphic;
                    });
                });
            });
        } else if (this.mapProvider === 'amap') {
            const polygon = new (window as any).AMap.Polygon({
                path: path,
                strokeColor: '#007aff',
                strokeWeight: 2,
                fillColor: '#007aff',
                fillOpacity: 0.2
            });
            this.mapEngine.map.add(polygon);
            return polygon;
        }

        return null;
    }

    /**
     * 计算两点之间的距离（米）
     * @param from - 起点
     * @param to - 终点
     * @returns 距离（米）
     */
    private calculateDistance(from: MapPoint, to: MapPoint): number {
        const R = 6371000; // 地球半径（米）
        const φ1 = from.latitude * Math.PI / 180;
        const φ2 = to.latitude * Math.PI / 180;
        const Δφ = (to.latitude - from.latitude) * Math.PI / 180;
        const Δλ = (to.longitude - from.longitude) * Math.PI / 180;

        const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
                  Math.cos(φ1) * Math.cos(φ2) *
                  Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

        return R * c;
    }

    /**
     * 计算多边形面积（平方米）
     * @param points - 点坐标数组
     * @returns 面积（平方米）
     */
    private calculateArea(points: MapPoint[]): number {
        if (points.length < 3) return 0;

        let area = 0;
        const n = points.length;

        for (let i = 0; i < n; i++) {
            const j = (i + 1) % n;
            area += points[i].latitude * points[j].longitude;
            area -= points[j].latitude * points[i].longitude;
        }

        area = Math.abs(area) / 2;

        // 将度转换为平方米（近似值）
        const avgLat = points.reduce((sum, p) => sum + p.latitude, 0) / n;
        const metersPerDegree = 111320 * Math.cos(avgLat * Math.PI / 180);

        return area * metersPerDegree * metersPerDegree;
    }

    /**
     * 格式化距离
     * @param distance - 距离（米）
     * @returns 格式化的距离
     */
    private formatDistance(distance: number): string {
        if (this.config.defaultUnit === 'km') {
            return `${(distance / 1000).toFixed(2)} km`;
        }
        return `${distance.toFixed(2)} m`;
    }

    /**
     * 格式化面积
     * @param area - 面积（平方米）
     * @returns 格式化的面积
     */
    private formatArea(area: number): string {
        if (area >= 1000000) {
            return `${(area / 1000000).toFixed(2)} km²`;
        }
        return `${area.toFixed(2)} m²`;
    }

    /**
     * 将地图点转换为屏幕坐标
     * @param mapPoint - 地图点
     * @returns 屏幕坐标
     */
    private mapPointToScreen(mapPoint: MapPoint): { x: number; y: number } | null {
        if (!this.mapEngine) return null;

        if (this.mapProvider === 'geoscene') {
            const view = this.mapEngine.view;
            if (view && view.toScreen) {
                const screenPoint = view.toScreen({
                    longitude: mapPoint.longitude,
                    latitude: mapPoint.latitude
                });
                return {
                    x: screenPoint.x,
                    y: screenPoint.y
                };
            }
        } else if (this.mapProvider === 'amap') {
            const map = this.mapEngine.map;
            if (map && map.lnglatToContainer) {
                const containerPoint = map.lnglatToContainer(
                    new (window as any).AMap.LngLat(mapPoint.longitude, mapPoint.latitude)
                );
                return {
                    x: containerPoint.getX(),
                    y: containerPoint.getY()
                };
            }
        }

        return null;
    }

    /**
     * 更新 UI
     */
    private updateUI(): void {
        if (!this.container) return;

        const undoBtn = this.container.querySelector('#undo-btn') as HTMLButtonElement;
        const clearBtn = this.container.querySelector('#clear-btn') as HTMLButtonElement;
        const exportBtn = this.container.querySelector('#export-btn') as HTMLButtonElement;
        const resultDiv = this.container.querySelector('#measure-result') as HTMLElement;
        const totalResult = this.container.querySelector('#total-result') as HTMLElement;
        const resultDetails = this.container.querySelector('#result-details') as HTMLElement;

        // 更新按钮状态
        undoBtn.disabled = this.points.length === 0;
        clearBtn.disabled = this.points.length === 0;
        exportBtn.disabled = this.points.length === 0;

        // 更新结果
        if (this.points.length > 0) {
            resultDiv.style.display = 'block';

            if (this.currentType === 'distance') {
                const totalDistance = this.segments.reduce((sum, seg) => sum + seg.distance, 0);
                totalResult.textContent = `总距离: ${this.formatDistance(totalDistance)}`;

                resultDetails.innerHTML = this.segments.map((seg, i) => `
                    <div class="result-detail-item">
                        <span>线段 ${i + 1}</span>
                        <span>${this.formatDistance(seg.distance)}</span>
                    </div>
                `).join('');
            } else if (this.currentType === 'area' && this.polygon) {
                totalResult.textContent = `面积: ${this.formatArea(this.polygon.area)}`;
                resultDetails.innerHTML = `
                    <div class="result-detail-item">
                        <span>顶点数</span>
                        <span>${this.points.length}</span>
                    </div>
                `;
            }
        } else {
            resultDiv.style.display = 'none';
        }
    }

    /**
     * 撤销上一个点
     */
    private undoLastPoint(): void {
        if (this.points.length === 0) return;

        const lastPoint = this.points.pop();

        // 移除标记和标签
        if (lastPoint) {
            if (lastPoint.marker) {
                if (this.mapProvider === 'geoscene') {
                    this.mapEngine.view.graphics.remove(lastPoint.marker);
                } else if (this.mapProvider === 'amap') {
                    this.mapEngine.map.remove(lastPoint.marker);
                }
            }
            if (lastPoint.label && lastPoint.label.parentNode) {
                lastPoint.label.parentNode.removeChild(lastPoint.label);
            }
        }

        // 如果是距离测量，移除最后一条线段
        if (this.currentType === 'distance' && this.segments.length > 0) {
            const lastSegment = this.segments.pop();
            if (lastSegment) {
                if (lastSegment.line) {
                    if (this.mapProvider === 'geoscene') {
                        this.mapEngine.view.graphics.remove(lastSegment.line);
                    } else if (this.mapProvider === 'amap') {
                        this.mapEngine.map.remove(lastSegment.line);
                    }
                }
                if (lastSegment.label && lastSegment.label.parentNode) {
                    lastSegment.label.parentNode.removeChild(lastSegment.label);
                }
            }
        }

        // 如果是面积测量，更新多边形
        if (this.currentType === 'area' && this.points.length >= 3) {
            this.updatePolygon();
        } else if (this.currentType === 'area' && this.polygon) {
            // 移除多边形
            if (this.polygon.polygon) {
                if (this.mapProvider === 'geoscene') {
                    this.mapEngine.view.graphics.remove(this.polygon.polygon);
                } else if (this.mapProvider === 'amap') {
                    this.mapEngine.map.remove(this.polygon.polygon);
                }
            }
            if (this.polygon.label && this.polygon.label.parentNode) {
                this.polygon.label.parentNode.removeChild(this.polygon.label);
            }
            this.polygon = null;
        }

        // 更新 UI
        this.updateUI();

        // 触发更新事件
        if (this.events.onMeasureUpdate) {
            this.events.onMeasureUpdate(this.getResult());
        }
    }

    /**
     * 清除所有测量
     */
    clear(): void {
        // 移除所有标记
        this.points.forEach(point => {
            if (point.marker) {
                if (this.mapProvider === 'geoscene') {
                    this.mapEngine.view.graphics.remove(point.marker);
                } else if (this.mapProvider === 'amap') {
                    this.mapEngine.map.remove(point.marker);
                }
            }
            if (point.label && point.label.parentNode) {
                point.label.parentNode.removeChild(point.label);
            }
        });

        // 移除所有线段
        this.segments.forEach(segment => {
            if (segment.line) {
                if (this.mapProvider === 'geoscene') {
                    this.mapEngine.view.graphics.remove(segment.line);
                } else if (this.mapProvider === 'amap') {
                    this.mapEngine.map.remove(segment.line);
                }
            }
            if (segment.label && segment.label.parentNode) {
                segment.label.parentNode.removeChild(segment.label);
            }
        });

        // 移除多边形
        if (this.polygon) {
            if (this.polygon.polygon) {
                if (this.mapProvider === 'geoscene') {
                    this.mapEngine.view.graphics.remove(this.polygon.polygon);
                } else if (this.mapProvider === 'amap') {
                    this.mapEngine.map.remove(this.polygon.polygon);
                }
            }
            if (this.polygon.label && this.polygon.label.parentNode) {
                this.polygon.label.parentNode.removeChild(this.polygon.label);
            }
        }

        // 清空数据
        this.points = [];
        this.segments = [];
        this.polygon = null;

        // 更新 UI
        this.updateUI();

        // 触发清除事件
        if (this.events.onMeasureClear) {
            this.events.onMeasureClear();
        }
    }

    /**
     * 获取测量结果
     * @returns 测量结果
     */
    getResult(): MeasureResult {
        const points = this.points.map(p => p.coordinate);

        if (this.currentType === 'distance') {
            const totalDistance = this.segments.reduce((sum, seg) => sum + seg.distance, 0);
            return {
                type: 'distance',
                unit: this.config.defaultUnit === 'km' ? 'km' : 'm',
                totalDistance,
                segments: this.segments,
                points
            };
        } else if (this.currentType === 'area' && this.polygon) {
            return {
                type: 'area',
                unit: this.polygon.area >= 1000000 ? 'km²' : 'm²',
                area: this.polygon.area,
                points
            };
        }

        return {
            type: this.currentType!,
            unit: this.config.defaultUnit === 'km' ? 'km' : 'm',
            points
        };
    }

    /**
     * 导出结果
     */
    private exportResult(): void {
        const result = this.getResult();

        // 创建 CSV 内容
        let csv = '';

        if (result.type === 'distance') {
            csv = '点序号,经度,纬度,距离\n';
            let cumulativeDistance = 0;
            result.points.forEach((point, i) => {
                if (i > 0 && result.segments && result.segments[i - 1]) {
                    cumulativeDistance += result.segments[i - 1].distance;
                }
                csv += `${i + 1},${point.longitude},${point.latitude},${cumulativeDistance.toFixed(2)}\n`;
            });
            csv += `\n总距离,${(result.totalDistance! / (result.unit === 'km' ? 1000 : 1)).toFixed(2)} ${result.unit}\n`;
        } else if (result.type === 'area') {
            csv = '点序号,经度,纬度\n';
            result.points.forEach((point, i) => {
                csv += `${i + 1},${point.longitude},${point.latitude}\n`;
            });
            csv += `\n面积,${(result.area! / (result.unit === 'km²' ? 1000000 : 1)).toFixed(2)} ${result.unit}\n`;
        }

        // 下载文件
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `measure_${result.type}_${Date.now()}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }

    /**
     * 销毁测量工具
     */
    destroy(): void {
        this.clear();
        this.removeMapClickHandler();

        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
        this.container = null;
    }
}
