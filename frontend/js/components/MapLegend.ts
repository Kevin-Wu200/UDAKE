/**
 * 地图图例组件
 * 支持可折叠、多种颜色方案、位置调整等功能
 */

/** 颜色方案类型 */
export type ColorScheme = 'default' | 'heatmap' | 'rainbow' | 'custom';

/** 图例位置 */
export type LegendPosition = 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';

/** 颜色区间 */
export interface ColorRange {
    min: number;
    max: number;
    color: string;
    label?: string;
}

/** 颜色方案配置 */
export interface ColorSchemeConfig {
    name: string;
    colors: string[];
    labels?: string[];
}

/** 图例配置 */
export interface LegendConfig {
    title: string;
    unit?: string;
    ranges: ColorRange[];
    position?: LegendPosition;
    collapsible?: boolean;
    collapsed?: boolean;
    showValues?: boolean;
}

/** 预设颜色方案 */
const PRESET_COLOR_SCHEMES: Record<ColorScheme, ColorSchemeConfig> = {
    default: {
        name: '默认',
        colors: ['#34c759', '#30d158', '#0a84ff', '#ff9500', '#ff3b30'],
        labels: ['极低', '低', '中等', '高', '极高']
    },
    heatmap: {
        name: '热力图',
        colors: ['#3b82f6', '#8b5cf6', '#ec4899', '#f97316', '#ef4444'],
        labels: ['低', '中低', '中', '中高', '高']
    },
    rainbow: {
        name: '彩虹',
        colors: ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6', '#8b5cf6'],
        labels: ['1', '2', '3', '4', '5', '6']
    },
    custom: {
        name: '自定义',
        colors: [],
        labels: []
    }
};

export class MapLegend {
    private element: HTMLElement | null;
    private config: LegendConfig;
    private currentScheme: ColorScheme;
    private customScheme: ColorSchemeConfig;
    private isCollapsed: boolean;
    private position: LegendPosition;

    constructor(config: LegendConfig) {
        this.element = null;
        this.config = {
            position: 'bottom-right',
            collapsible: true,
            collapsed: false,
            showValues: true,
            ...config
        };
        this.currentScheme = 'default';
        this.customScheme = { name: '自定义', colors: [], labels: [] };
        this.isCollapsed = this.config.collapsed ?? false;
        this.position = this.config.position ?? 'bottom-right';
    }

    /**
     * 创建图例
     * @returns 图例元素
     */
    createLegend(): HTMLElement {
        this.element = document.createElement('div');
        this.element.className = 'map-legend';
        this.element.dataset.position = this.position;

        this.addStyles();
        this.render();

        return this.element;
    }

    /**
     * 添加样式
     */
    private addStyles(): void {
        if (document.querySelector('#map-legend-styles')) return;

        const style = document.createElement('style');
        style.id = 'map-legend-styles';
        style.textContent = `
            .map-legend {
                position: absolute;
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                padding: 12px;
                z-index: 1000;
                font-size: 12px;
                color: var(--text-primary, #1d1d1f);
                transition: all 0.3s ease;
            }

            @media (prefers-color-scheme: dark) {
                .map-legend {
                    background: rgba(28, 28, 30, 0.95);
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
                }
            }

            .map-legend[data-position="top-left"] {
                top: 60px;
                left: 10px;
            }

            .map-legend[data-position="top-right"] {
                top: 60px;
                right: 80px; /* 380px(侧边栏宽度) + 32px(切换按钮宽度) */
            }

            .map-legend[data-position="bottom-left"] {
                bottom: 20px;
                left: 10px;
            }

            .map-legend[data-position="bottom-right"] {
                bottom: 20px;
                right: 80px; /* 380px(侧边栏宽度) + 32px(切换按钮宽度) */
            }

            .map-legend.collapsed {
                width: auto;
            }

            .map-legend .legend-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px;
            }

            .map-legend .legend-title {
                font-weight: 600;
                font-size: 14px;
                color: var(--text-primary, #1d1d1f);
            }

            .map-legend .legend-controls {
                display: flex;
                gap: 4px;
            }

            .map-legend .legend-btn {
                width: 24px;
                height: 24px;
                border: none;
                background: var(--bg-secondary, #f5f5f7);
                border-radius: 4px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                color: var(--text-secondary, #86868b);
                transition: all 0.2s ease;
            }

            .map-legend .legend-btn:hover {
                background: var(--bg-tertiary, #e8e8ed);
                color: var(--text-primary, #1d1d1f);
            }

            .map-legend .legend-content {
                transition: all 0.3s ease;
                overflow: hidden;
            }

            .map-legend.collapsed .legend-content {
                max-height: 0;
                opacity: 0;
            }

            .map-legend .color-scale {
                display: flex;
                align-items: center;
                gap: 2px;
                height: 20px;
                border-radius: 4px;
                overflow: hidden;
                margin-bottom: 8px;
            }

            .map-legend .color-bar {
                flex: 1;
                height: 100%;
            }

            .map-legend .legend-labels {
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
            }

            .map-legend .legend-label {
                font-size: 11px;
                color: var(--text-secondary, #86868b);
            }

            .map-legend .legend-items {
                display: flex;
                flex-direction: column;
                gap: 4px;
            }

            .map-legend .legend-item {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 4px;
                border-radius: 4px;
                transition: background 0.2s ease;
            }

            .map-legend .legend-item:hover {
                background: var(--bg-secondary, #f5f5f7);
            }

            .map-legend .legend-color {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                flex-shrink: 0;
            }

            .map-legend .legend-item-label {
                flex: 1;
                color: var(--text-primary, #1d1d1f);
            }

            .map-legend .legend-item-value {
                font-weight: 600;
                color: var(--text-primary, #1d1d1f);
            }

            .map-legend .legend-unit {
                font-size: 11px;
                color: var(--text-tertiary, #aeaeb2);
                margin-left: 4px;
            }

            .map-legend .legend-scheme-selector {
                display: flex;
                gap: 8px;
                margin-top: 8px;
                padding-top: 8px;
                border-top: 1px solid var(--border-color, #e5e5e5);
            }

            .map-legend .scheme-btn {
                padding: 4px 8px;
                border: 1px solid var(--border-color, #e5e5e5);
                background: var(--bg-primary, #ffffff);
                color: var(--text-primary, #1d1d1f);
                border-radius: 4px;
                font-size: 11px;
                cursor: pointer;
                transition: all 0.2s ease;
            }

            .map-legend .scheme-btn:hover {
                background: var(--bg-secondary, #f5f5f7);
            }

            .map-legend .scheme-btn.active {
                background: var(--primary-color, #007aff);
                color: white;
                border-color: var(--primary-color, #007aff);
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * 渲染图例
     */
    private render(): void {
        if (!this.element) return;

        const { title, unit, ranges, showValues } = this.config;

        this.element.innerHTML = `
            <div class="legend-header">
                <span class="legend-title">${title}</span>
                <div class="legend-controls">
                    ${this.config.collapsible ? `
                        <button class="legend-btn collapse-btn" title="折叠/展开">
                            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                                <path d="M3 5L7 9L11 5" stroke="currentColor" stroke-width="2" fill="none"/>
                            </svg>
                        </button>
                    ` : ''}
                    <button class="legend-btn position-btn" title="更改位置">
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                            <rect x="2" y="2" width="4" height="4" rx="1"/>
                            <rect x="8" y="2" width="4" height="4" rx="1"/>
                            <rect x="2" y="8" width="4" height="4" rx="1"/>
                            <rect x="8" y="8" width="4" height="4" rx="1"/>
                        </svg>
                    </button>
                </div>
            </div>
            <div class="legend-content">
                ${this.renderColorScale()}
                ${this.renderLegendItems(ranges, showValues ?? false, unit)}
                ${this.renderSchemeSelector()}
            </div>
        `;

        this.bindEvents();
    }

    /**
     * 渲染颜色条
     * @returns 颜色条 HTML
     */
    private renderColorScale(): string {
        const scheme = PRESET_COLOR_SCHEMES[this.currentScheme];
        const colors = this.currentScheme === 'custom' ? this.customScheme.colors : scheme.colors;

        return `
            <div class="color-scale">
                ${colors.map(color => `<div class="color-bar" style="background-color: ${color};"></div>`).join('')}
            </div>
        `;
    }

    /**
     * 渲染图例项
     * @param ranges - 颜色区间
     * @param showValues - 是否显示数值
     * @param unit - 单位
     * @returns 图例项 HTML
     */
    private renderLegendItems(ranges: ColorRange[], showValues: boolean, unit?: string): string {
        if (ranges.length === 0) return '';

        const scheme = PRESET_COLOR_SCHEMES[this.currentScheme];
        const labels = this.currentScheme === 'custom' ? this.customScheme.labels : scheme.labels;

        return `
            <div class="legend-items">
                ${ranges.map((range, index) => `
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: ${range.color};"></div>
                        <span class="legend-item-label">${(labels && labels[index]) || `区间 ${index + 1}`}</span>
                        ${showValues ? `
                            <span class="legend-item-value">
                                ${range.min.toFixed(2)} - ${range.max.toFixed(2)}
                                ${unit ? `<span class="legend-unit">${unit}</span>` : ''}
                            </span>
                        ` : ''}
                    </div>
                `).join('')}
            </div>
        `;
    }

    /**
     * 渲染颜色方案选择器
     * @returns 选择器 HTML
     */
    private renderSchemeSelector(): string {
        return `
            <div class="legend-scheme-selector">
                ${Object.keys(PRESET_COLOR_SCHEMES).map((key) => `
                    <button class="scheme-btn ${key === this.currentScheme ? 'active' : ''}" data-scheme="${key}">
                        ${PRESET_COLOR_SCHEMES[key as ColorScheme].name}
                    </button>
                `).join('')}
            </div>
        `;
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        if (!this.element) return;

        const collapseBtn = this.element.querySelector('.collapse-btn');
        const positionBtn = this.element.querySelector('.position-btn');
        const schemeBtns = this.element.querySelectorAll('.scheme-btn');

        if (collapseBtn) {
            collapseBtn.addEventListener('click', () => this.toggleCollapse());
        }

        if (positionBtn) {
            positionBtn.addEventListener('click', () => this.cyclePosition());
        }

        schemeBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const scheme = (e.target as HTMLElement).dataset.scheme as ColorScheme;
                if (scheme) {
                    this.setColorScheme(scheme);
                }
            });
        });
    }

    /**
     * 切换折叠状态
     */
    private toggleCollapse(): void {
        if (!this.element) return;
        this.isCollapsed = !this.isCollapsed;
        this.element.classList.toggle('collapsed', this.isCollapsed);

        const collapseBtn = this.element.querySelector('.collapse-btn');
        if (collapseBtn) {
            collapseBtn.style.transform = this.isCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)';
        }
    }

    /**
     * 循环切换位置
     */
    private cyclePosition(): void {
        const positions: LegendPosition[] = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];
        const currentIndex = positions.indexOf(this.position);
        const nextIndex = (currentIndex + 1) % positions.length;
        this.setPosition(positions[nextIndex]);
    }

    /**
     * 设置位置
     * @param position - 位置
     */
    setPosition(position: LegendPosition): void {
        this.position = position;
        if (this.element) {
            this.element.dataset.position = position;
        }
    }

    /**
     * 设置颜色方案
     * @param scheme - 颜色方案
     */
    setColorScheme(scheme: ColorScheme): void {
        this.currentScheme = scheme;
        this.render();
    }

    /**
     * 设置自定义颜色方案
     * @param config - 颜色方案配置
     */
    setCustomScheme(config: ColorSchemeConfig): void {
        this.customScheme = config;
        this.currentScheme = 'custom';
        this.render();
    }

    /**
     * 更新图例数据
     * @param config - 图例配置
     */
    updateConfig(config: Partial<LegendConfig>): void {
        this.config = { ...this.config, ...config };
        this.render();
    }

    /**
     * 获取当前颜色方案
     * @returns 颜色方案
     */
    getCurrentScheme(): ColorScheme {
        return this.currentScheme;
    }

    /**
     * 获取所有预设颜色方案
     * @returns 颜色方案配置
     */
    getPresetSchemes(): Record<ColorScheme, ColorSchemeConfig> {
        return PRESET_COLOR_SCHEMES;
    }

    /**
     * 保存当前图例配置到 localStorage
     */
    saveToStorage(): void {
        try {
            const data = {
                position: this.position,
                currentScheme: this.currentScheme,
                customScheme: this.customScheme,
                isCollapsed: this.isCollapsed
            };
            localStorage.setItem('map-legend-config', JSON.stringify(data));
        } catch (error) {
            console.error('保存图例配置失败:', error);
        }
    }

    /**
     * 从 localStorage 加载图例配置
     */
    loadFromStorage(): void {
        try {
            const data = localStorage.getItem('map-legend-config');
            if (data) {
                const config = JSON.parse(data);
                if (config.position) this.setPosition(config.position);
                if (config.currentScheme) this.setColorScheme(config.currentScheme);
                if (config.customScheme) this.customScheme = config.customScheme;
                if (config.isCollapsed) {
                    this.isCollapsed = config.isCollapsed;
                    if (this.element) {
                        this.element.classList.add('collapsed');
                    }
                }
            }
        } catch (error) {
            console.error('加载图例配置失败:', error);
        }
    }

    /**
     * 销毁图例
     */
    destroy(): void {
        if (this.element && this.element.parentNode) {
            this.element.parentNode.removeChild(this.element);
        }
        this.element = null;
    }
}