/**
 * 图层对比面板组件
 * 提供图层对比、透明度控制和图层切换功能
 */

/** 图层类型枚举 */
export enum LayerType {
    POINTS = 'points',
    PREDICTION = 'prediction',
    VARIANCE = 'variance',
    UNCERTAINTY = 'uncertainty',
    BOUNDARY = 'boundary',
    MARKER = 'marker'
}

/** 图层对比配置 */
export interface LayerComparisonConfig {
    layerId: string;
    layerName: string;
    layerType: LayerType;
    visible: boolean;
    opacity: number;
    zIndex: number;
}

/** 图层对比事件 */
export interface LayerComparisonEvents {
    onVisibilityChange?: (layerId: string, visible: boolean) => void;
    onOpacityChange?: (layerId: string, opacity: number) => void;
    onLayerOrderChange?: (layers: LayerComparisonConfig[]) => void;
}

export class LayerComparisonPanel {
    private container: HTMLElement | null;
    private configs: Map<string, LayerComparisonConfig>;
    private events: LayerComparisonEvents;
    private isCollapsed: boolean;

    constructor(events: LayerComparisonEvents = {}) {
        this.container = null;
        this.configs = new Map();
        this.events = events;
        this.isCollapsed = false;
    }

    /**
     * 创建面板
     */
    createPanel(): HTMLElement {
        this.container = document.createElement('div');
        this.container.className = 'layer-comparison-panel';
        this.container.innerHTML = `
            <div class="panel-header">
                <h3 class="panel-title">图层对比</h3>
                <button class="collapse-btn" aria-label="收起/展开">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M4 6L8 10L12 6" stroke="currentColor" stroke-width="2" fill="none"/>
                    </svg>
                </button>
            </div>
            <div class="panel-content">
                <div class="layers-list" id="layers-list"></div>
                <div class="panel-actions">
                    <button class="btn btn-secondary btn-sm" id="show-all-btn">显示全部</button>
                    <button class="btn btn-secondary btn-sm" id="hide-all-btn">隐藏全部</button>
                    <button class="btn btn-secondary btn-sm" id="reset-opacity-btn">重置透明度</button>
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
        if (document.querySelector('#layer-comparison-styles')) return;

        const style = document.createElement('style');
        style.id = 'layer-comparison-styles';
        style.textContent = `
            .layer-comparison-panel {
                background: var(--bg-primary, #ffffff);
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
                overflow: hidden;
                transition: all 0.3s ease;
            }

            .layer-comparison-panel .panel-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 16px;
                background: var(--bg-secondary, #f5f5f7);
                border-bottom: 1px solid var(--border-color, #e5e5e5);
            }

            .layer-comparison-panel .panel-title {
                margin: 0;
                font-size: 16px;
                font-weight: 600;
                color: var(--text-primary, #1d1d1f);
            }

            .layer-comparison-panel .collapse-btn {
                background: none;
                border: none;
                padding: 4px;
                cursor: pointer;
                color: var(--text-secondary, #86868b);
                transition: transform 0.3s ease;
            }

            .layer-comparison-panel .collapse-btn:hover {
                background: var(--bg-tertiary, #e8e8ed);
                border-radius: 4px;
            }

            .layer-comparison-panel.collapsed .collapse-btn {
                transform: rotate(-90deg);
            }

            .layer-comparison-panel .panel-content {
                padding: 16px;
                max-height: 400px;
                overflow-y: auto;
                transition: max-height 0.3s ease, padding 0.3s ease;
            }

            .layer-comparison-panel.collapsed .panel-content {
                max-height: 0;
                padding: 0 16px;
                overflow: hidden;
            }

            .layer-comparison-panel .layers-list {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }

            .layer-comparison-panel .layer-item {
                background: var(--bg-secondary, #f5f5f7);
                border-radius: 8px;
                padding: 12px;
                transition: all 0.2s ease;
            }

            .layer-comparison-panel .layer-item:hover {
                background: var(--bg-tertiary, #e8e8ed);
            }

            .layer-comparison-panel .layer-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px;
            }

            .layer-comparison-panel .layer-name {
                display: flex;
                align-items: center;
                gap: 8px;
                font-weight: 500;
                color: var(--text-primary, #1d1d1f);
            }

            .layer-comparison-panel .layer-visibility {
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .layer-comparison-panel .visibility-toggle {
                width: 32px;
                height: 20px;
                background: var(--border-color, #e5e5e5);
                border-radius: 10px;
                position: relative;
                cursor: pointer;
                transition: background 0.2s ease;
            }

            .layer-comparison-panel .visibility-toggle.active {
                background: var(--primary-color, #007aff);
            }

            .layer-comparison-panel .visibility-toggle::after {
                content: '';
                position: absolute;
                width: 16px;
                height: 16px;
                background: white;
                border-radius: 50%;
                top: 2px;
                left: 2px;
                transition: transform 0.2s ease;
            }

            .layer-comparison-panel .visibility-toggle.active::after {
                transform: translateX(12px);
            }

            .layer-comparison-panel .layer-opacity {
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .layer-comparison-panel .opacity-label {
                font-size: 12px;
                color: var(--text-secondary, #86868b);
                min-width: 45px;
            }

            .layer-comparison-panel .opacity-slider {
                flex: 1;
                -webkit-appearance: none;
                appearance: none;
                height: 4px;
                background: var(--border-color, #e5e5e5);
                border-radius: 2px;
                outline: none;
                cursor: pointer;
            }

            .layer-comparison-panel .opacity-slider::-webkit-slider-thumb {
                -webkit-appearance: none;
                appearance: none;
                width: 16px;
                height: 16px;
                background: var(--primary-color, #007aff);
                border-radius: 50%;
                cursor: pointer;
                transition: transform 0.1s ease;
            }

            .layer-comparison-panel .opacity-slider::-webkit-slider-thumb:hover {
                transform: scale(1.1);
            }

            .layer-comparison-panel .panel-actions {
                display: flex;
                gap: 8px;
                margin-top: 16px;
                padding-top: 16px;
                border-top: 1px solid var(--border-color, #e5e5e5);
            }

            .layer-comparison-panel .btn-sm {
                padding: 6px 12px;
                font-size: 12px;
                height: 28px;
            }

            .layer-comparison-panel .layer-type-badge {
                font-size: 10px;
                padding: 2px 6px;
                border-radius: 4px;
                background: var(--bg-tertiary, #e8e8ed);
                color: var(--text-tertiary, #aeaeb2);
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        if (!this.container) return;

        const collapseBtn = this.container.querySelector('.collapse-btn');
        const showAllBtn = this.container.querySelector('#show-all-btn');
        const hideAllBtn = this.container.querySelector('#hide-all-btn');
        const resetOpacityBtn = this.container.querySelector('#reset-opacity-btn');

        if (collapseBtn) {
            collapseBtn.addEventListener('click', () => this.toggleCollapse());
        }

        if (showAllBtn) {
            showAllBtn.addEventListener('click', () => this.showAllLayers());
        }

        if (hideAllBtn) {
            hideAllBtn.addEventListener('click', () => this.hideAllLayers());
        }

        if (resetOpacityBtn) {
            resetOpacityBtn.addEventListener('click', () => this.resetAllOpacity());
        }
    }

    /**
     * 切换折叠状态
     */
    private toggleCollapse(): void {
        if (!this.container) return;
        this.isCollapsed = !this.isCollapsed;
        this.container.classList.toggle('collapsed', this.isCollapsed);
    }

    /**
     * 添加图层
     * @param config - 图层配置
     */
    addLayer(config: LayerComparisonConfig): void {
        this.configs.set(config.layerId, config);
        this.renderLayerList();
    }

    /**
     * 移除图层
     * @param layerId - 图层 ID
     */
    removeLayer(layerId: string): void {
        this.configs.delete(layerId);
        this.renderLayerList();
    }

    /**
     * 更新图层配置
     * @param layerId - 图层 ID
     * @param updates - 更新内容
     */
    updateLayer(layerId: string, updates: Partial<LayerComparisonConfig>): void {
        const config = this.configs.get(layerId);
        if (config) {
            const updated = { ...config, ...updates };
            this.configs.set(layerId, updated);
            this.renderLayerList();
        }
    }

    /**
     * 设置图层可见性
     * @param layerId - 图层 ID
     * @param visible - 是否可见
     */
    setLayerVisibility(layerId: string, visible: boolean): void {
        const config = this.configs.get(layerId);
        if (config) {
            config.visible = visible;
            this.configs.set(layerId, config);

            if (this.events.onVisibilityChange) {
                this.events.onVisibilityChange(layerId, visible);
            }

            this.renderLayerList();
        }
    }

    /**
     * 设置图层透明度
     * @param layerId - 图层 ID
     * @param opacity - 透明度 (0-100)
     */
    setLayerOpacity(layerId: string, opacity: number): void {
        const config = this.configs.get(layerId);
        if (config) {
            config.opacity = Math.max(0, Math.min(100, opacity));
            this.configs.set(layerId, config);

            if (this.events.onOpacityChange) {
                this.events.onOpacityChange(layerId, config.opacity);
            }

            this.renderLayerList();
        }
    }

    /**
     * 调整图层顺序
     * @param layerId - 图层 ID
     * @param direction - 方向 ('up' 或 'down')
     */
    moveLayer(layerId: string, direction: 'up' | 'down'): void {
        const configs = Array.from(this.configs.values());
        const index = configs.findIndex(c => c.layerId === layerId);

        if (index === -1) return;

        if (direction === 'up' && index > 0) {
            [configs[index], configs[index - 1]] = [configs[index - 1], configs[index]];
        } else if (direction === 'down' && index < configs.length - 1) {
            [configs[index], configs[index + 1]] = [configs[index + 1], configs[index]];
        }

        // 更新 zIndex
        configs.forEach((config, i) => {
            config.zIndex = configs.length - i;
            this.configs.set(config.layerId, config);
        });

        if (this.events.onLayerOrderChange) {
            this.events.onLayerOrderChange(configs);
        }

        this.renderLayerList();
    }

    /**
     * 显示所有图层
     */
    private showAllLayers(): void {
        this.configs.forEach((config, layerId) => {
            this.setLayerVisibility(layerId, true);
        });
    }

    /**
     * 隐藏所有图层
     */
    private hideAllLayers(): void {
        this.configs.forEach((config, layerId) => {
            this.setLayerVisibility(layerId, false);
        });
    }

    /**
     * 重置所有透明度
     */
    private resetAllOpacity(): void {
        this.configs.forEach((config, layerId) => {
            this.setLayerOpacity(layerId, 100);
        });
    }

    /**
     * 渲染图层列表
     */
    private renderLayerList(): void {
        if (!this.container) return;

        const layersList = this.container.querySelector('#layers-list');
        if (!layersList) return;

        const configs = Array.from(this.configs.values()).sort((a, b) => b.zIndex - a.zIndex);

        layersList.innerHTML = '';

        if (configs.length === 0) {
            layersList.innerHTML = `
                <div style="text-align: center; color: var(--text-tertiary, #aeaeb2); padding: 20px;">
                    暂无图层
                </div>
            `;
            return;
        }

        configs.forEach(config => {
            const layerItem = this.createLayerItem(config);
            layersList.appendChild(layerItem);
        });
    }

    /**
     * 创建图层项
     * @param config - 图层配置
     * @returns 图层项元素
     */
    private createLayerItem(config: LayerComparisonConfig): HTMLElement {
        const item = document.createElement('div');
        item.className = 'layer-item';
        item.dataset.layerId = config.layerId;

        item.innerHTML = `
            <div class="layer-header">
                <div class="layer-name">
                    <span>${config.layerName}</span>
                    <span class="layer-type-badge">${this.getLayerTypeText(config.layerType)}</span>
                </div>
                <div class="layer-visibility">
                    <div class="visibility-toggle ${config.visible ? 'active' : ''}"></div>
                </div>
            </div>
            <div class="layer-opacity">
                <span class="opacity-label">透明度: ${config.opacity}%</span>
                <input type="range" class="opacity-slider" min="0" max="100" value="${config.opacity}">
            </div>
        `;

        // 绑定事件
        const visibilityToggle = item.querySelector('.visibility-toggle') as HTMLElement;
        const opacitySlider = item.querySelector('.opacity-slider') as HTMLInputElement;

        if (visibilityToggle) {
            visibilityToggle.addEventListener('click', () => {
                this.setLayerVisibility(config.layerId, !config.visible);
            });
        }

        if (opacitySlider) {
            opacitySlider.addEventListener('input', (e) => {
                const value = parseInt((e.target as HTMLInputElement).value);
                this.setLayerOpacity(config.layerId, value);
            });
        }

        return item;
    }

    /**
     * 获取图层类型文本
     * @param type - 图层类型
     * @returns 类型文本
     */
    private getLayerTypeText(type: LayerType): string {
        const texts: Record<LayerType, string> = {
            [LayerType.POINTS]: '采样点',
            [LayerType.PREDICTION]: '预测',
            [LayerType.VARIANCE]: '方差',
            [LayerType.UNCERTAINTY]: '不确定性',
            [LayerType.BOUNDARY]: '边界',
            [LayerType.MARKER]: '标记'
        };
        return texts[type] || type;
    }

    /**
     * 获取所有图层配置
     * @returns 图层配置数组
     */
    getAllConfigs(): LayerComparisonConfig[] {
        return Array.from(this.configs.values());
    }

    /**
     * 清除所有图层
     */
    clearAll(): void {
        this.configs.clear();
        this.renderLayerList();
    }

    /**
     * 销毁面板
     */
    destroy(): void {
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
        this.container = null;
        this.configs.clear();
    }
}