/**
 * 骨架屏工具
 * 在内容加载时显示占位动画，支持多种类型和自定义配置
 */

export type SkeletonType =
    | 'text'
    | 'panel'
    | 'list'
    | 'card'
    | 'chart'
    | 'map'
    | 'sidebar'
    | 'custom';

export interface SkeletonOptions {
    lines?: number;
    showAvatar?: boolean;
    showTitle?: boolean;
    height?: string;
    animationType?: 'shimmer' | 'pulse' | 'wave';
    theme?: 'light' | 'dark';
    customContent?: string;
}

export class SkeletonLoader {
    private static instances: Map<HTMLElement, HTMLDivElement> = new Map();

    /**
     * 创建文本骨架屏
     */
    static createTextSkeleton(lines: number = 3, options: SkeletonOptions = {}): string {
        const height = options.height || '16px';
        return Array.from({ length: lines }, (_, i) =>
            `<div class="skeleton skeleton-text" style="width: ${80 - i * 10}%; height: ${height};"></div>`
        ).join('');
    }

    /**
     * 创建面板骨架屏
     */
    static createPanelSkeleton(options: SkeletonOptions = {}): string {
        const { showTitle = true } = options;
        return `
            <div class="skeleton-panel">
                ${showTitle ? '<div class="skeleton skeleton-title" style="width: 40%; height: 24px; margin-bottom: 16px;"></div>' : ''}
                <div class="skeleton skeleton-rect" style="margin-bottom: 12px; height: 100px;"></div>
                <div class="skeleton skeleton-text" style="width: 70%;"></div>
                <div class="skeleton skeleton-text" style="width: 50%;"></div>
                <div class="skeleton skeleton-text" style="width: 60%;"></div>
            </div>
        `;
    }

    /**
     * 创建列表骨架屏
     */
    static createListSkeleton(count: number = 3, options: SkeletonOptions = {}): string {
        const { showAvatar = true, showTitle = true } = options;
        return Array.from({ length: count }, () => `
            <div class="skeleton-list-item">
                ${showAvatar ? '<div class="skeleton skeleton-avatar"></div>' : ''}
                <div class="skeleton-list-content">
                    ${showTitle ? '<div class="skeleton skeleton-text" style="width: 60%; height: 18px; margin-bottom: 8px;"></div>' : ''}
                    <div class="skeleton skeleton-text" style="width: 90%;"></div>
                    <div class="skeleton skeleton-text" style="width: 75%;"></div>
                </div>
            </div>
        `).join('');
    }

    /**
     * 创建卡片骨架屏
     */
    static createCardSkeleton(options: SkeletonOptions = {}): string {
        const { showAvatar = true } = options;
        return `
            <div class="skeleton-card">
                <div class="skeleton skeleton-card-image"></div>
                <div class="skeleton-card-content">
                    <div class="skeleton skeleton-text" style="width: 70%; height: 20px; margin-bottom: 12px;"></div>
                    <div class="skeleton skeleton-text" style="width: 90%;"></div>
                    <div class="skeleton skeleton-text" style="width: 85%;"></div>
                </div>
            </div>
        `;
    }

    /**
     * 创建图表骨架屏
     */
    static createChartSkeleton(options: SkeletonOptions = {}): string {
        return `
            <div class="skeleton-chart">
                <div class="skeleton skeleton-chart-title" style="width: 40%; height: 20px; margin-bottom: 16px;"></div>
                <div class="skeleton skeleton-chart-area">
                    <div class="skeleton skeleton-chart-bar" style="height: 60%;"></div>
                    <div class="skeleton skeleton-chart-bar" style="height: 80%;"></div>
                    <div class="skeleton skeleton-chart-bar" style="height: 45%;"></div>
                    <div class="skeleton skeleton-chart-bar" style="height: 90%;"></div>
                    <div class="skeleton skeleton-chart-bar" style="height: 55%;"></div>
                </div>
                <div class="skeleton skeleton-chart-legend">
                    <div class="skeleton skeleton-text" style="width: 20%;"></div>
                    <div class="skeleton skeleton-text" style="width: 20%;"></div>
                    <div class="skeleton skeleton-text" style="width: 20%;"></div>
                </div>
            </div>
        `;
    }

    /**
     * 创建地图骨架屏
     */
    static createMapSkeleton(options: SkeletonOptions = {}): string {
        return `
            <div class="skeleton-map">
                <div class="skeleton-map-background"></div>
                <div class="skeleton-map-marker" style="top: 20%; left: 30%;"></div>
                <div class="skeleton-map-marker" style="top: 50%; left: 60%;"></div>
                <div class="skeleton-map-marker" style="top: 70%; left: 45%;"></div>
                <div class="skeleton-map-controls">
                    <div class="skeleton skeleton-map-control"></div>
                    <div class="skeleton skeleton-map-control"></div>
                </div>
            </div>
        `;
    }

    /**
     * 创建侧边栏骨架屏
     */
    static createSidebarSkeleton(options: SkeletonOptions = {}): string {
        return `
            <div class="skeleton-sidebar">
                <div class="skeleton skeleton-sidebar-header" style="width: 50%; height: 24px; margin-bottom: 20px;"></div>
                <div class="skeleton skeleton-sidebar-section">
                    <div class="skeleton skeleton-text" style="width: 60%; height: 16px; margin-bottom: 12px;"></div>
                    <div class="skeleton skeleton-text" style="width: 90%;"></div>
                    <div class="skeleton skeleton-text" style="width: 85%;"></div>
                </div>
                <div class="skeleton skeleton-sidebar-section">
                    <div class="skeleton skeleton-text" style="width: 55%; height: 16px; margin-bottom: 12px;"></div>
                    <div class="skeleton skeleton-text" style="width: 80%;"></div>
                    <div class="skeleton skeleton-text" style="width: 75%;"></div>
                    <div class="skeleton skeleton-text" style="width: 90%;"></div>
                </div>
            </div>
        `;
    }

    /**
     * 显示骨架屏
     */
    static show(container: HTMLElement, type: SkeletonType = 'text', options: SkeletonOptions = {}): HTMLDivElement {
        const wrapper = document.createElement('div');
        wrapper.className = 'skeleton-wrapper';
        wrapper.dataset.type = type;

        // 添加动画类型
        const animationType = options.animationType || 'shimmer';
        wrapper.classList.add(`skeleton-${animationType}`);

        // 添加主题
        const theme = options.theme || 'light';
        wrapper.classList.add(`skeleton-${theme}`);

        // 根据类型创建骨架屏
        let content = '';
        switch (type) {
            case 'text':
                content = this.createTextSkeleton(options.lines, options);
                break;
            case 'panel':
                content = this.createPanelSkeleton(options);
                break;
            case 'list':
                content = this.createListSkeleton(options.lines, options);
                break;
            case 'card':
                content = this.createCardSkeleton(options);
                break;
            case 'chart':
                content = this.createChartSkeleton(options);
                break;
            case 'map':
                content = this.createMapSkeleton(options);
                break;
            case 'sidebar':
                content = this.createSidebarSkeleton(options);
                break;
            case 'custom':
                content = options.customContent || '';
                break;
            default:
                content = this.createTextSkeleton(options.lines, options);
        }

        wrapper.innerHTML = content;
        container.appendChild(wrapper);

        // 保存实例
        this.instances.set(container, wrapper);

        // 添加显示动画
        requestAnimationFrame(() => {
            wrapper.classList.add('skeleton-visible');
        });

        return wrapper;
    }

    /**
     * 隐藏骨架屏
     */
    static hide(wrapper: HTMLDivElement | null): void {
        if (wrapper && wrapper.style) {
            wrapper.style.opacity = '0';
            wrapper.classList.remove('skeleton-visible');
            wrapper.classList.add('skeleton-hidden');

            setTimeout(() => {
                // 从映射中移除
                for (const [container, instance] of this.instances.entries()) {
                    if (instance === wrapper) {
                        this.instances.delete(container);
                        break;
                    }
                }
                wrapper.remove();
            }, 200);
        }
    }

    /**
     * 根据容器隐藏骨架屏
     */
    static hideByContainer(container: HTMLElement): void {
        const wrapper = this.instances.get(container);
        if (wrapper) {
            this.hide(wrapper);
        }
    }

    /**
     * 更新骨架屏内容
     */
    static update(wrapper: HTMLDivElement, type: SkeletonType, options: SkeletonOptions = {}): void {
        if (!wrapper) return;

        let content = '';
        switch (type) {
            case 'text':
                content = this.createTextSkeleton(options.lines, options);
                break;
            case 'panel':
                content = this.createPanelSkeleton(options);
                break;
            case 'list':
                content = this.createListSkeleton(options.lines, options);
                break;
            case 'card':
                content = this.createCardSkeleton(options);
                break;
            case 'chart':
                content = this.createChartSkeleton(options);
                break;
            case 'map':
                content = this.createMapSkeleton(options);
                break;
            case 'sidebar':
                content = this.createSidebarSkeleton(options);
                break;
            case 'custom':
                content = options.customContent || '';
                break;
            default:
                content = this.createTextSkeleton(options.lines, options);
        }

        wrapper.innerHTML = content;
        wrapper.dataset.type = type;
    }
}
