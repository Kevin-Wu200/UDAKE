/**
 * 区域采样组件
 * 支持上传 GeoJSON 边界，仅允许在边界内添加采样点
 */
import { CoordinateInput } from './CoordinateInput.js';
import { ErrorHandler } from '../utils/ErrorHandler.js';
import { GeoJSONParser } from '../utils/geojsonParser.js';

export class RegionSampling {
    /**
     * @param {Object} view - ArcGIS MapView
     * @param {Function} onPointAdded - 点添加回调
     */
    constructor(view, onPointAdded) {
        this.view = view;
        this.onPointAdded = onPointAdded;
        this.coordinateInput = null;
        this.coordinateMode = 'manual';
        this.boundaryPolygon = null;
        this.boundaryLayer = null;
    }

    /**
     * 创建采样面板
     * @param {string} coordinateMode - 坐标获取方式
     * @returns {HTMLElement}
     */
    createPanel(coordinateMode = 'manual') {
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
     * @param {HTMLElement} container
     */
    bindBoundaryUploadEvents(container) {
        const picker = container.querySelector('#boundary-picker');
        const fileInput = container.querySelector('#boundary-input');
        const fileName = container.querySelector('#boundary-file-name');
        const uploadBtn = container.querySelector('#upload-boundary-btn');

        picker.addEventListener('click', () => {
            fileInput.click();
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                fileName.textContent = fileInput.files[0].name;
            } else {
                fileName.textContent = '点击选择 GeoJSON 文件';
            }
        });

        uploadBtn.addEventListener('click', () => this.handleBoundaryUpload(fileInput));
    }

    /**
     * 处理边界上传
     * @param {HTMLInputElement} fileInput
     */
    async handleBoundaryUpload(fileInput) {
        const file = fileInput.files[0];
        const statusDiv = document.getElementById('boundary-status');

        if (!file) {
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.VALIDATION_ERROR,
                '请选择文件',
                statusDiv.parentElement
            );
            return;
        }

        // 验证文件类型
        if (!GeoJSONParser.validateFileType(file)) {
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.GEOJSON_FORMAT,
                '仅支持 .geojson 或 .json 文件',
                statusDiv.parentElement
            );
            return;
        }

        try {
            // 解析 GeoJSON
            const parseResult = await GeoJSONParser.parseFile(file);

            // 验证是否为多边形
            const geometry = parseResult.geojson.features?.[0]?.geometry || parseResult.geojson.geometry;

            const validation = ErrorHandler.validatePolygon(geometry);
            if (!validation.valid) {
                ErrorHandler.showError(
                    ErrorHandler.ErrorTypes.INVALID_POLYGON,
                    validation.error,
                    statusDiv.parentElement
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

            ErrorHandler.showSuccess(
                '边界上传成功',
                statusDiv.parentElement
            );

            // 显示采样输入区域
            this.showSamplingSection();

        } catch (error) {
            console.error('边界上传失败:', error);
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.GEOJSON_FORMAT,
                error.message,
                statusDiv.parentElement
            );
        }
    }

    /**
     * 在地图上显示边界
     * @param {Object} polygon - GeoJSON 多边形
     */
    async displayBoundary(polygon) {
        // 移除旧的边界图层
        if (this.boundaryLayer) {
            this.view.map.remove(this.boundaryLayer);
        }

        // 使用 ArcGIS API 创建图层
        const [Graphic, GraphicsLayer] = await Promise.all([
            window.esri.require('esri/Graphic'),
            window.esri.require('esri/layers/GraphicsLayer')
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
     * @param {Object} geometry
     * @returns {Array}
     */
    getPolygonRings(geometry) {
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
    showSamplingSection() {
        const samplingSection = document.getElementById('sampling-section');
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
        const addBtn = buttonGroup.querySelector('#add-region-point-btn');
        const clearBtn = buttonGroup.querySelector('#clear-region-input-btn');

        addBtn.addEventListener('click', () => this.addPoint());
        clearBtn.addEventListener('click', () => this.clearInput());
    }

    /**
     * 处理坐标变化
     * @param {Object} position
     */
    handleCoordinateChange(position) {
        console.log('坐标已更新:', position);
    }

    /**
     * 添加采样点
     */
    async addPoint() {
        const pointData = this.coordinateInput.getValue();

        if (!pointData) {
            return;
        }

        // 检查点是否在边界内
        if (!this.isPointInBoundary(pointData)) {
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.POINT_OUT_OF_BOUNDS,
                null,
                document.getElementById('region-sampling-status').parentElement
            );
            return;
        }

        try {
            // 触发回调
            if (this.onPointAdded) {
                await this.onPointAdded(pointData);
            }

            ErrorHandler.showSuccess(
                `采样点已添加 (${pointData.longitude.toFixed(6)}, ${pointData.latitude.toFixed(6)})`,
                document.getElementById('region-sampling-status').parentElement
            );

            // 清空输入
            this.clearInput();

        } catch (error) {
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.VALIDATION_ERROR,
                error.message,
                document.getElementById('region-sampling-status').parentElement
            );
        }
    }

    /**
     * 检查点是否在边界内
     * 使用射线法（Ray Casting Algorithm）
     * @param {Object} point
     * @returns {boolean}
     */
    isPointInBoundary(point) {
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
     * @returns {Array}
     */
    getPolygonCoordinates() {
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
    clearInput() {
        if (this.coordinateInput) {
            this.coordinateInput.clear();
        }
    }

    /**
     * 获取边界多边形
     * @returns {Object|null}
     */
    getBoundaryPolygon() {
        return this.boundaryPolygon;
    }

    /**
     * 销毁组件
     */
    destroy() {
        if (this.coordinateInput) {
            this.coordinateInput.destroy();
        }

        if (this.boundaryLayer) {
            this.view.map.remove(this.boundaryLayer);
        }
    }
}
