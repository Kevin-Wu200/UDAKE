import { TiandituEngine } from '../map/core/TiandituEngine.js';
import { ArcGISEngine } from '../map/core/ArcGISEngine.js';
import { GeoUtils } from '../utils/GeoUtils.js';

/**
 * 地图管理器
 * 负责创建和管理地图引擎，处理 reset 按钮和模式切换
 */
export class MapManager {
    constructor() {
        this.mapEngine = null;
        this.initialCenter = null;
        this.initialZoom = null;
        this.geojson = null;
        this.mode = 'normal'; // 'normal' 或 'areaSampling'
        this.resetButton = null;
    }

    /**
     * 初始化地图
     * @param {string} provider - 'tianditu' 或 'arcgis'
     * @param {string} containerId - 容器 ID
     * @param {Object} options - 初始化选项
     */
    async init(provider, containerId, options = {}) {
        // 创建地图引擎
        if (provider === 'tianditu') {
            this.mapEngine = new TiandituEngine(options);
        } else if (provider === 'arcgis') {
            this.mapEngine = new ArcGISEngine(options);
        } else {
            throw new Error(`不支持的地图引擎: ${provider}`);
        }

        // 初始化地图
        await this.mapEngine.init(containerId, options);

        // 保存初始状态
        this.initialCenter = this.mapEngine.getCenter();
        this.initialZoom = this.mapEngine.getZoom();

        // 如果支持自定义 reset，创建 reset 按钮
        if (this.mapEngine.supportsCustomReset) {
            this.createResetButton(containerId);
        }

        console.log(`✅ MapManager 初始化完成，引擎: ${provider}`);
    }

    /**
     * 创建 reset 按钮
     */
    createResetButton(containerId) {
        const container = typeof containerId === 'string'
            ? document.getElementById(containerId)
            : containerId;

        if (!container) return;

        // 创建按钮
        this.resetButton = document.createElement('div');
        this.resetButton.className = 'map-reset-btn';
        this.resetButton.innerHTML = '⟲';
        this.resetButton.title = '重置视图';

        // 样式
        this.resetButton.style.cssText = `
            position: absolute;
            top: 10px;
            right: 10px;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.9);
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 20px;
            color: #333;
            z-index: 1000;
            transition: all 0.2s;
        `;

        // Hover 效果
        this.resetButton.addEventListener('mouseenter', () => {
            this.resetButton.style.background = 'rgba(255, 255, 255, 1)';
            this.resetButton.style.transform = 'scale(1.1)';
        });

        this.resetButton.addEventListener('mouseleave', () => {
            this.resetButton.style.background = 'rgba(255, 255, 255, 0.9)';
            this.resetButton.style.transform = 'scale(1)';
        });

        // 点击事件
        this.resetButton.addEventListener('click', () => {
            this.handleReset();
        });

        container.appendChild(this.resetButton);
    }

    /**
     * 处理 reset 按钮点击
     */
    handleReset() {
        if (this.mode === 'normal') {
            // 普通模式：回到初始位置
            this.mapEngine.setCenter(this.initialCenter);
            this.mapEngine.setZoom(this.initialZoom);
        } else if (this.mode === 'areaSampling' && this.geojson) {
            // 区域采样模式：适配 GeoJSON 范围
            try {
                const bounds = GeoUtils.calculateBoundsFromGeoJSON(this.geojson);
                const expandedBounds = GeoUtils.expandBounds(bounds, 0.1);
                this.mapEngine.fitToBounds(expandedBounds);
            } catch (error) {
                console.error('适配 GeoJSON 范围失败:', error);
                // 回退到初始位置
                this.mapEngine.setCenter(this.initialCenter);
                this.mapEngine.setZoom(this.initialZoom);
            }
        }
    }

    /**
     * 切换到区域采样模式
     * @param {Object} geojson - GeoJSON 数据
     */
    enterAreaSamplingMode(geojson) {
        this.mode = 'areaSampling';
        this.geojson = geojson;

        // 自动适配到 GeoJSON 范围
        try {
            const bounds = GeoUtils.calculateBoundsFromGeoJSON(geojson);
            const expandedBounds = GeoUtils.expandBounds(bounds, 0.1);
            this.mapEngine.fitToBounds(expandedBounds);
        } catch (error) {
            console.error('适配 GeoJSON 范围失败:', error);
        }
    }

    /**
     * 切换到普通模式
     */
    enterNormalMode() {
        this.mode = 'normal';
        this.geojson = null;
    }

    /**
     * 获取地图引擎
     */
    getEngine() {
        return this.mapEngine;
    }

    /**
     * 销毁
     */
    destroy() {
        if (this.resetButton && this.resetButton.parentNode) {
            this.resetButton.parentNode.removeChild(this.resetButton);
        }

        if (this.mapEngine) {
            this.mapEngine.destroy();
        }
    }
}
