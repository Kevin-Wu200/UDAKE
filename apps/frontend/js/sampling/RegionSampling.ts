/**
 * 区域采样组件
 * 支持上传 GeoJSON 边界，仅允许在边界内添加采样点
 * 支持多种地图引擎（ArcGIS、高德地图）
 */

import { CoordinateInput } from './CoordinateInput';
import { ErrorHandler } from '../utils/ErrorHandler';
import { GeoJSONParser } from '../utils/geojsonParser';
import { MapConfig } from '../config/map.config';
import type {
    PointAddedCallback,
    Coordinate,
    CoordinateMode,
    BoundaryPolygon,
    BoundaryLayer
} from '../../types/sampling';
import type { MapAdapter } from '../../types/adapter';

/**
 * 区域采样组件
 * 支持上传 GeoJSON 边界，仅允许在边界内添加采样点
 * 支持多种地图引擎（ArcGIS、高德地图）
 */
export class RegionSampling {
    /** 地图视图或适配器 */
    view: any;

    /** 适配器 */
    adapter: MapAdapter | null;

    /** 点添加回调 */
    onPointAdded: PointAddedCallback | null;

    /** 坐标输入组件 */
    coordinateInput: CoordinateInput | null;

    /** 坐标获取方式 */
    coordinateMode: CoordinateMode;

    /** 边界多边形 */
    boundaryPolygon: BoundaryPolygon | null;

    /** 边界图层 */
    boundaryLayer: BoundaryLayer | null;

    /** 地图提供者 */
    mapProvider: any;

    /**
     * @param viewOrAdapter - MapView 或 MapAdapter
     * @param onPointAdded - 点添加回调
     */
    constructor(viewOrAdapter: any, onPointAdded?: PointAddedCallback) {
        // 兼容旧代码：如果传入的是 view，尝试获取适配器
        if (viewOrAdapter && typeof viewOrAdapter.getEngine === 'function') {
            // 这是一个适配器
            this.adapter = viewOrAdapter;
            this.view = viewOrAdapter.getView();
        } else {
            // 这是一个 view，需要找到对应的适配器
            this.view = viewOrAdapter;
            this.adapter = null; // 将在需要时从全局获取
        }

        this.onPointAdded = onPointAdded || null;
        this.coordinateInput = null;
        this.coordinateMode = 'manual';
        this.boundaryPolygon = null;
        this.boundaryLayer = null;
        this.mapProvider = MapConfig.getProvider();
    }

    /**
     * 创建采样面板
     * @param coordinateMode - 坐标获取方式
     * @returns HTMLElement
     */
    createPanel(coordinateMode: CoordinateMode = 'manual'): HTMLElement {
        this.coordinateMode = coordinateMode;

        const container = document.createElement('div');
        container.className = 'region-sampling-panel';

        container.innerHTML = `
            <div class="panel-header">
                <h3 class="section-title">区域采样</h3>
                <p class="section-description">仅允许在指定区域内添加采样点</p>
            </div>

            <div class="boundary-upload-section">
                <h4 class="section-title" style="font-size: 14px; margin-bottom: 12px;">上传区域边界</h4>
                <div id="boundary-picker" class="file-picker">
                    <span id="boundary-file-name">点击选择 GeoJSON 文件</span>
                    <input type="file"
                           id="boundary-input"
                           accept=".geojson,.json"
                           class="file-input">
                </div>
                <button id="upload-boundary-btn" class="btn btn-primary">上传边界</button>
                <div id="boundary-status" class="status-message" style="display: none;"></div>
            </div>

            <div id="sampling-section" style="display: none; margin-top: 24px;">
                <div class="divider" style="height: 1px; background: var(--border-color); margin: 24px 0;"></div>
            </div>
        `;

        // 绑定边界上传事件
        this.bindBoundaryUploadEvents(container);

        return container;
    }

    /**
     * 绑定边界上传事件
     * @param container
     */
    protected bindBoundaryUploadEvents(container: HTMLElement): void {
        const picker = container.querySelector('#boundary-picker') as HTMLDivElement;
        const fileInput = container.querySelector('#boundary-input') as HTMLInputElement;
        const fileName = container.querySelector('#boundary-file-name') as HTMLSpanElement;
        const uploadBtn = container.querySelector('#upload-boundary-btn') as HTMLButtonElement;

        picker.addEventListener('click', () => {
            fileInput.click();
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files && fileInput.files.length > 0) {
                fileName.textContent = fileInput.files[0].name;
            } else {
                fileName.textContent = '点击选择 GeoJSON 文件';
            }
        });

        uploadBtn.addEventListener('click', () => this.handleBoundaryUpload(fileInput));
    }

    /**
     * 处理边界上传
     * @param fileInput
     */
    async handleBoundaryUpload(fileInput: HTMLInputElement): Promise<void> {
        const file = fileInput.files?.[0];
        const statusDiv = document.getElementById('boundary-status') as HTMLDivElement;

        if (!file) {
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.VALIDATION_ERROR,
                '请选择文件'
            );
            return;
        }

        // 验证文件类型
        if (!GeoJSONParser.validateFileType(file)) {
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.GEOJSON_FORMAT,
                '仅支持 .geojson 或 .json 文件'
            );
            return;
        }

        try {
            // 解析 GeoJSON
            const parseResult = await GeoJSONParser.parseFile(file);

            // 验证是否为多边形
            const geometry = parseResult.geojson.features?.[0]?.geometry || (parseResult.geojson as any).geometry;

            const validation = ErrorHandler.validatePolygon(geometry);
            if (!validation.valid) {
                ErrorHandler.showError(
                    ErrorHandler.ErrorTypes.INVALID_POLYGON,
                    validation.error
                );
                return;
            }

            // 保存边界
            this.boundaryPolygon = {
                type: 'Feature',
                geometry: geometry,
                properties: {}
            };

            // 在地图上显示边界
            await this.displayBoundary(this.boundaryPolygon);

            ErrorHandler.showSuccess('边界上传成功');

            // 显示采样输入区域
            this.showSamplingSection();

        } catch (error) {
            console.error('边界上传失败:', error);
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.GEOJSON_FORMAT,
                (error as Error).message
            );
        }
    }

    /**
     * 在地图上显示边界
     * @param polygon - GeoJSON 多边形
     */
    async displayBoundary(polygon: BoundaryPolygon): Promise<void> {
        // 移除旧的边界图层
        if (this.boundaryLayer) {
            if (this.mapProvider === 'amap') {
                this.view.remove(this.boundaryLayer);
            } else {
                this.view.map.remove(this.boundaryLayer);
            }
        }

        if (this.mapProvider === 'amap') {
            // 高德地图实现
            await this.displayBoundaryAMap(polygon);
        } else {
            // ArcGIS 实现
            await this.displayBoundaryArcGIS(polygon);
        }
    }

    /**
     * 高德地图显示边界
     */
    protected async displayBoundaryAMap(polygon: BoundaryPolygon): Promise<void> {
        const AMap = (window as any).AMap;
        const rings = this.getPolygonRings(polygon.geometry);

        // 转换坐标格式：从 [[[lng, lat], ...]] 到 [[lng, lat], ...]
        const path = rings[0].map(coord => [coord[0], coord[1]]);

        this.boundaryLayer = new AMap.Polygon({
            path: path,
            strokeColor: '#007AFF',
            strokeWeight: 2,
            strokeOpacity: 0.8,
            fillColor: '#007AFF',
            fillOpacity: 0.1
        });

        this.view.add(this.boundaryLayer);

        // 缩放到边界
        this.view.setFitView([this.boundaryLayer], false, [20, 20, 20, 20]);
    }

    /**
     * ArcGIS 显示边界
     */
    protected async displayBoundaryArcGIS(polygon: BoundaryPolygon): Promise<void> {
        // 使用 ArcGIS API 创建图层
        // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
        const [Graphic, GraphicsLayer] = await Promise.all([
            (window as any).esri.require('esri/Graphic'),
            (window as any).esri.require('esri/layers/GraphicsLayer')
        ]);

        // 创建图形
        const graphic = new Graphic({
            geometry: {
                type: 'polygon',
                rings: this.getPolygonRings(polygon.geometry)
            },
            symbol: {
                type: 'simple-fill',
                color: [0, 122, 255, 0.1],
                outline: {
                    color: [0, 122, 255, 1],
                    width: 2
                }
            }
        });

        // 创建图层
        this.boundaryLayer = new GraphicsLayer({
            graphics: [graphic],
            title: '采样区域边界'
        });

        this.view.map.add(this.boundaryLayer);

        // 缩放到边界
        this.view.goTo(graphic.geometry.extent.expand(1.2));
    }

    /**
     * 获取多边形环坐标
     * @param geometry
     * @returns Array
     */
    protected getPolygonRings(geometry: any): number[][][] {
        if (geometry.type === 'Polygon') {
            return geometry.coordinates;
        } else if (geometry.type === 'MultiPolygon') {
            // 对于 MultiPolygon，返回第一个多边形
            return geometry.coordinates[0];
        }
        return [];
    }

    /**
     * 显示采样输入区域
     */
    protected showSamplingSection(): void {
        const samplingSection = document.getElementById('sampling-section');
        if (!samplingSection) return;

        samplingSection.style.display = 'block';

        // 创建坐标输入组件
        this.coordinateInput = new CoordinateInput(
            this.coordinateMode,
            (position) => this.handleCoordinateChange(position)
        );

        const inputPanel = this.coordinateInput.createPanel();
        samplingSection.appendChild(inputPanel);

        // 添加按钮
        const buttonGroup = document.createElement('div');
        buttonGroup.className = 'button-group';
        buttonGroup.style.cssText = 'display: flex; gap: 12px; margin-top: 16px;';

        buttonGroup.innerHTML = `
            <button id="add-region-point-btn" class="btn btn-primary" style="flex: 1;">添加采样点</button>
            <button id="clear-region-input-btn" class="btn btn-secondary" style="flex: 1;">清空输入</button>
        `;

        samplingSection.appendChild(buttonGroup);

        // 状态消息
        const statusDiv = document.createElement('div');
        statusDiv.id = 'region-sampling-status';
        statusDiv.className = 'status-message';
        statusDiv.style.display = 'none';
        samplingSection.appendChild(statusDiv);

        // 绑定事件
        const addBtn = buttonGroup.querySelector('#add-region-point-btn') as HTMLButtonElement;
        const clearBtn = buttonGroup.querySelector('#clear-region-input-btn') as HTMLButtonElement;

        addBtn.addEventListener('click', () => this.addPoint());
        clearBtn.addEventListener('click', () => this.clearInput());
    }

    /**
     * 处理坐标变化
     * @param position
     */
    protected handleCoordinateChange(position: Coordinate): void {
        console.log('坐标已更新:', position);
    }

    /**
     * 添加采样点
     */
    async addPoint(): Promise<void> {
        if (!this.coordinateInput) {
            return;
        }

        const pointData = this.coordinateInput.getValue();

        if (!pointData) {
            return;
        }

        // 检查点是否在边界内
        if (!this.isPointInBoundary(pointData)) {
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.POINT_OUT_OF_BOUNDS,
                null
            );
            return;
        }

        try {
            // 触发回调
            if (this.onPointAdded) {
                await this.onPointAdded(pointData);
            }

            ErrorHandler.showSuccess(
                `采样点已添加 (${pointData.longitude.toFixed(6)}, ${pointData.latitude.toFixed(6)})`
            );

            // 清空输入
            this.clearInput();

        } catch (error) {
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.VALIDATION_ERROR,
                (error as Error).message
            );
        }
    }

    /**
     * 检查点是否在边界内
     * 使用射线法（Ray Casting Algorithm）
     * @param point
     * @returns boolean
     */
    protected isPointInBoundary(point: Coordinate): boolean {
        if (!this.boundaryPolygon) return false;

        const { longitude, latitude } = point;
        const coordinates = this.getPolygonCoordinates();

        let inside = false;
        for (let i = 0, j = coordinates.length - 1; i < coordinates.length; j = i++) {
            const xi = coordinates[i][0], yi = coordinates[i][1];
            const xj = coordinates[j][0], yj = coordinates[j][1];

            const intersect = ((yi > latitude) !== (yj > latitude))
                && (longitude < (xj - xi) * (latitude - yi) / (yj - yi) + xi);
            if (intersect) inside = !inside;
        }

        return inside;
    }

    /**
     * 获取多边形坐标数组
     * @returns Array
     */
    protected getPolygonCoordinates(): number[][] {
        if (!this.boundaryPolygon) return [];

        const geometry = this.boundaryPolygon.geometry;

        if (geometry.type === 'Polygon') {
            return geometry.coordinates[0]; // 外环
        } else if (geometry.type === 'MultiPolygon') {
            return geometry.coordinates[0][0]; // 第一个多边形的外环
        }

        return [];
    }

    /**
     * 清空输入
     */
    clearInput(): void {
        if (this.coordinateInput) {
            this.coordinateInput.clear();
        }
    }

    /**
     * 获取边界多边形
     * @returns Object | null
     */
    getBoundaryPolygon(): BoundaryPolygon | null {
        return this.boundaryPolygon;
    }

    /**
     * 销毁组件
     */
    destroy(): void {
        if (this.coordinateInput) {
            this.coordinateInput.destroy();
        }

        if (this.boundaryLayer) {
            if (this.mapProvider === 'amap') {
                this.view.remove(this.boundaryLayer);
            } else {
                this.view.map.remove(this.boundaryLayer);
            }
        }
    }
}