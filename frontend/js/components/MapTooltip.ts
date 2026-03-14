/**
 * 地图悬停提示组件
 * 显示预测值和不确定性等级，支持智能定位和动画效果
 */

import type { MapPoint } from '../../types/app';

/** 不确定性等级 */
export enum UncertaintyLevel {
    VERY_LOW = 1,  // 深绿
    LOW = 2,       // 浅绿
    MEDIUM = 3,    // 蓝色
    HIGH = 4,      // 橙色
    VERY_HIGH = 5  // 深红
}

/** 不确定性等级颜色 */
const UNCERTAINTY_COLORS: Record<UncertaintyLevel, string> = {
    [UncertaintyLevel.VERY_LOW]: '#34c759',
    [UncertaintyLevel.LOW]: '#30d158',
    [UncertaintyLevel.MEDIUM]: '#0a84ff',
    [UncertaintyLevel.HIGH]: '#ff9500',
    [UncertaintyLevel.VERY_HIGH]: '#ff3b30'
};

/** 不确定性等级文本 */
const UNCERTAINTY_TEXTS: Record<UncertaintyLevel, string> = {
    [UncertaintyLevel.VERY_LOW]: '极低',
    [UncertaintyLevel.LOW]: '低',
    [UncertaintyLevel.MEDIUM]: '中等',
    [UncertaintyLevel.HIGH]: '高',
    [UncertaintyLevel.VERY_HIGH]: '极高'
};

/** 提示框数据 */
export interface TooltipData {
    prediction?: number;
    variance?: number;
    uncertaintyLevel?: UncertaintyLevel;
    coordinate: MapPoint;
    additionalInfo?: Record<string, any>;
}

/** 提示框配置 */
export interface TooltipConfig {
    offset?: number;           // 提示框偏移量（像素）
    animationDuration?: number; // 动画时长（毫秒）
    showDelay?: number;        // 显示延迟（毫秒）
    hideDelay?: number;        // 隐藏延迟（毫秒）
    smartPositioning?: boolean; // 是否启用智能定位
}

export class MapTooltip {
    private element: HTMLElement | null;
    private showTimer: ReturnType<typeof setTimeout> | null;
    private hideTimer: ReturnType<typeof setTimeout> | null;
    private isVisible: boolean;
    private config: Required<TooltipConfig>;
    private mapContainer: HTMLElement | null;

    constructor(config: TooltipConfig = {}) {
        this.element = null;
        this.showTimer = null;
        this.hideTimer = null;
        this.isVisible = false;
        this.config = {
            offset: config.offset ?? 15,
            animationDuration: config.animationDuration ?? 200,
            showDelay: config.showDelay ?? 300,
            hideDelay: config.hideDelay ?? 100,
            smartPositioning: config.smartPositioning ?? true
        };
        this.mapContainer = null;
    }

    /**
     * 初始化提示框
     * @param mapContainer - 地图容器元素
     */
    init(mapContainer: HTMLElement): void {
        this.mapContainer = mapContainer;
        this.createTooltip();
        this.addStyles();
    }

    /**
     * 创建提示框元素
     */
    private createTooltip(): void {
        if (!this.mapContainer) return;

        this.element = document.createElement('div');
        this.element.className = 'map-tooltip';
        this.element.style.cssText = `
            position: absolute;
            display: none;
            z-index: 1000;
            pointer-events: none;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            padding: 12px 16px;
            font-size: 13px;
            min-width: 200px;
            max-width: 280px;
            opacity: 0;
            transform: translateY(5px);
            transition: opacity ${this.config.animationDuration}ms ease,
                        transform ${this.config.animationDuration}ms ease;
        `;

        this.mapContainer.appendChild(this.element);
    }

    /**
     * 添加样式
     */
    private addStyles(): void {
        if (!document.querySelector('#map-tooltip-styles')) {
            const style = document.createElement('style');
            style.id = 'map-tooltip-styles';
            style.textContent = `
                .map-tooltip .tooltip-header {
                    font-weight: 600;
                    color: var(--text-primary, #1d1d1f);
                    margin-bottom: 8px;
                    font-size: 14px;
                }

                .map-tooltip .tooltip-row {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin: 6px 0;
                    color: var(--text-secondary, #86868b);
                }

                .map-tooltip .tooltip-label {
                    font-weight: 500;
                    color: var(--text-secondary, #86868b);
                }

                .map-tooltip .tooltip-value {
                    font-weight: 600;
                    color: var(--text-primary, #1d1d1f);
                }

                .map-tooltip .tooltip-uncertainty {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    margin-top: 8px;
                    padding-top: 8px;
                    border-top: 1px solid var(--border-color, #e5e5e5);
                }

                .map-tooltip .uncertainty-dot {
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    flex-shrink: 0;
                }

                .map-tooltip .uncertainty-text {
                    font-weight: 500;
                    color: var(--text-primary, #1d1d1f);
                }

                .map-tooltip .coordinate-row {
                    font-size: 12px;
                    color: var(--text-tertiary, #aeaeb2);
                    margin-top: 6px;
                }

                .map-tooltip .additional-info {
                    margin-top: 8px;
                    padding-top: 8px;
                    border-top: 1px solid var(--border-color, #e5e5e5);
                    font-size: 12px;
                    color: var(--text-tertiary, #aeaeb2);
                }
            `;
            document.head.appendChild(style);
        }
    }

    /**
     * 显示提示框
     * @param data - 提示框数据
     * @param screenX - 屏幕X坐标
     * @param screenY - 屏幕Y坐标
     */
    show(data: TooltipData, screenX: number, screenY: number): void {
        if (!this.element || !this.mapContainer) return;

        // 清除之前的定时器
        this.clearTimers();

        this.showTimer = setTimeout(() => {
            if (!this.element) return;

            // 更新内容
            this.updateContent(data);

            // 计算位置
            const position = this.calculatePosition(screenX, screenY);
            this.element.style.left = `${position.x}px`;
            this.element.style.top = `${position.y}px`;
            this.element.style.display = 'block';

            // 强制重排以触发动画
            this.element.offsetHeight;

            // 显示动画
            this.element.style.opacity = '1';
            this.element.style.transform = 'translateY(0)';

            this.isVisible = true;
        }, this.config.showDelay);
    }

    /**
     * 更新提示框内容
     * @param data - 提示框数据
     */
    private updateContent(data: TooltipData): void {
        if (!this.element) return;

        const { prediction, variance, uncertaintyLevel, coordinate, additionalInfo } = data;

        let html = `
            <div class="tooltip-header">预测结果</div>
        `;

        if (prediction !== undefined) {
            html += `
                <div class="tooltip-row">
                    <span class="tooltip-label">预测值:</span>
                    <span class="tooltip-value">${prediction.toFixed(4)}</span>
                </div>
            `;
        }

        if (variance !== undefined) {
            html += `
                <div class="tooltip-row">
                    <span class="tooltip-label">方差:</span>
                    <span class="tooltip-value">${variance.toFixed(4)}</span>
                </div>
            `;
        }

        if (uncertaintyLevel !== undefined) {
            const color = UNCERTAINTY_COLORS[uncertaintyLevel];
            const text = UNCERTAINTY_TEXTS[uncertaintyLevel];

            html += `
                <div class="tooltip-uncertainty">
                    <div class="uncertainty-dot" style="background-color: ${color};"></div>
                    <span class="uncertainty-text">不确定性: ${text}</span>
                </div>
            `;
        }

        html += `
            <div class="coordinate-row">
                坐标: ${coordinate.longitude.toFixed(6)}, ${coordinate.latitude.toFixed(6)}
            </div>
        `;

        if (additionalInfo && Object.keys(additionalInfo).length > 0) {
            html += '<div class="additional-info">';
            Object.entries(additionalInfo).forEach(([key, value]) => {
                html += `
                    <div class="tooltip-row">
                        <span class="tooltip-label">${key}:</span>
                        <span class="tooltip-value">${value}</span>
                    </div>
                `;
            });
            html += '</div>';
        }

        this.element.innerHTML = html;
    }

    /**
     * 计算提示框位置（智能定位算法）
     * @param screenX - 屏幕X坐标
     * @param screenY - 屏幕Y坐标
     * @returns 提示框位置
     */
    private calculatePosition(screenX: number, screenY: number): { x: number; y: number } {
        if (!this.mapContainer || !this.element) {
            return { x: screenX, y: screenY };
        }

        const containerRect = this.mapContainer.getBoundingClientRect();
        const tooltipRect = this.element.getBoundingClientRect();

        // 默认位置（右上方）
        let x = screenX + this.config.offset;
        let y = screenY - this.config.offset - tooltipRect.height;

        if (!this.config.smartPositioning) {
            return { x, y };
        }

        // 检查是否超出右边界（考虑右侧侧边栏宽度380px和切换按钮宽度32px）
        const rightSidebarWidth = 80; // 侧边栏宽度 + 切换按钮宽度
        if (x + tooltipRect.width > containerRect.width - rightSidebarWidth) {
            x = screenX - tooltipRect.width - this.config.offset;
        }

        // 检查是否超出左边界
        if (x < 0) {
            x = this.config.offset;
        }

        // 检查是否超出上边界
        if (y < 0) {
            y = screenY + this.config.offset;
        }

        // 检查是否超出下边界
        if (y + tooltipRect.height > containerRect.height) {
            y = containerRect.height - tooltipRect.height - this.config.offset;
        }

        return { x, y };
    }

    /**
     * 隐藏提示框
     */
    hide(): void {
        if (!this.element || !this.isVisible) return;

        this.clearTimers();

        this.hideTimer = setTimeout(() => {
            if (!this.element) return;

            // 隐藏动画
            this.element.style.opacity = '0';
            this.element.style.transform = 'translateY(5px)';

            // 动画结束后隐藏元素
            setTimeout(() => {
                if (this.element) {
                    this.element.style.display = 'none';
                }
                this.isVisible = false;
            }, this.config.animationDuration);
        }, this.config.hideDelay);
    }

    /**
     * 清除定时器
     */
    private clearTimers(): void {
        if (this.showTimer) {
            clearTimeout(this.showTimer);
            this.showTimer = null;
        }
        if (this.hideTimer) {
            clearTimeout(this.hideTimer);
            this.hideTimer = null;
        }
    }

    /**
     * 更新配置
     * @param config - 新配置
     */
    updateConfig(config: Partial<TooltipConfig>): void {
        this.config = {
            ...this.config,
            ...config
        };
    }

    /**
     * 获取不确定性等级颜色
     * @param level - 不确定性等级
     * @returns 颜色
     */
    static getUncertaintyColor(level: UncertaintyLevel): string {
        return UNCERTAINTY_COLORS[level];
    }

    /**
     * 获取不确定性等级文本
     * @param level - 不确定性等级
     * @returns 文本
     */
    static getUncertaintyText(level: UncertaintyLevel): string {
        return UNCERTAINTY_TEXTS[level];
    }

    /**
     * 根据方差计算不确定性等级
     * @param variance - 方差值
     * @param maxVariance - 最大方差值（用于归一化）
     * @returns 不确定性等级
     */
    static calculateUncertaintyLevel(variance: number, maxVariance: number = 1.0): UncertaintyLevel {
        const normalized = Math.min(variance / maxVariance, 1.0);

        if (normalized < 0.2) return UncertaintyLevel.VERY_LOW;
        if (normalized < 0.4) return UncertaintyLevel.LOW;
        if (normalized < 0.6) return UncertaintyLevel.MEDIUM;
        if (normalized < 0.8) return UncertaintyLevel.HIGH;
        return UncertaintyLevel.VERY_HIGH;
    }

    /**
     * 销毁提示框
     */
    destroy(): void {
        this.clearTimers();

        if (this.element && this.element.parentNode) {
            this.element.parentNode.removeChild(this.element);
        }

        this.element = null;
        this.mapContainer = null;
        this.isVisible = false;
    }
}