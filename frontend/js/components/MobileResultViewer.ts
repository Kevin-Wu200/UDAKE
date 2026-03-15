/**
 * 移动端结果查看器
 * 全屏视图，支持手势切换和缩放
 */

import './config/主题变量';

interface Result {
    id: string;
    title: string;
    content: string;
    image?: string;
    metadata?: Record<string, any>;
}

interface MobileResultViewerOptions {
    results: Result[];
    enableSwipe?: boolean;
    enablePinchZoom?: boolean;
    enableHaptic?: boolean;
}

class MobileResultViewer {
    private results: Result[];
    private currentIndex: number = 0;
    private enableSwipe: boolean;
    private enablePinchZoom: boolean;
    private enableHaptic: boolean;
    private isOpen: boolean = false;
    private currentScale: number = 1;
    private initialDistance: number = 0;

    private elements: {
        viewer: HTMLElement | null;
        container: HTMLElement | null;
        content: HTMLElement | null;
        closeBtn: HTMLElement | null;
        prevBtn: HTMLElement | null;
        nextBtn: HTMLElement | null;
        dots: HTMLElement[];
    } = {
        viewer: null,
        container: null,
        content: null,
        closeBtn: null,
        prevBtn: null,
        nextBtn: null,
        dots: [],
    };

    constructor(options: MobileResultViewerOptions) {
        this.results = options.results;
        this.enableSwipe = options.enableSwipe ?? true;
        this.enablePinchZoom = options.enablePinchZoom ?? true;
        this.enableHaptic = options.enableHaptic ?? true;
        this.init();
    }

    /**
     * 初始化查看器
     */
    private init(): void {
        this.createViewer();
        this.bindEvents();
    }

    /**
     * 创建查看器
     */
    private createViewer(): void {
        const viewer = document.createElement('div');
        viewer.className = 'mobile-result-viewer mobile-only';
        viewer.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--bg-panel);
            z-index: 9999;
            display: flex;
            flex-direction: column;
            transform: translateY(100%);
            transition: transform 300ms cubic-bezier(0.4, 0.0, 0.2, 1);
        `;

        // 创建头部
        const header = document.createElement('div');
        header.className = 'viewer-header';
        header.style.cssText = `
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px;
            border-bottom: 1px solid var(--border-color);
        `;

        // 关闭按钮
        const closeBtn = document.createElement('button');
        closeBtn.className = 'viewer-close-btn';
        closeBtn.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        `;
        closeBtn.style.cssText = `
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: none;
            background: transparent;
            color: var(--text-primary);
            cursor: pointer;
        `;

        // 标题
        const title = document.createElement('div');
        title.className = 'viewer-title';
        title.textContent = '结果详情';
        title.style.cssText = `
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
        `;

        // 分享按钮
        const shareBtn = document.createElement('button');
        shareBtn.className = 'viewer-share-btn';
        shareBtn.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"></path>
                <polyline points="16 6 12 2 8 6"></polyline>
                <line x1="12" y1="2" x2="12" y2="15"></line>
            </svg>
        `;
        shareBtn.style.cssText = `
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: none;
            background: transparent;
            color: var(--text-primary);
            cursor: pointer;
        `;

        header.appendChild(closeBtn);
        header.appendChild(title);
        header.appendChild(shareBtn);

        viewer.appendChild(header);
        this.elements.closeBtn = closeBtn;

        // 创建内容容器
        const container = document.createElement('div');
        container.className = 'viewer-container';
        container.style.cssText = `
            flex: 1;
            overflow: hidden;
            position: relative;
        `;

        // 创建内容滑动区域
        const content = document.createElement('div');
        content.className = 'viewer-content';
        content.style.cssText = `
            width: 100%;
            height: 100%;
            display: flex;
            transition: transform 300ms ease;
        `;

        // 创建每个结果页面
        this.results.forEach((result, _index) => {
            const page = this.createResultPage(result);
            page.style.cssText = `
                min-width: 100%;
                height: 100%;
                padding: 16px;
                overflow-y: auto;
                transform: scale(${this.currentScale});
                transition: transform 200ms ease;
            `;
            content.appendChild(page);
        });

        container.appendChild(content);
        this.elements.content = content;
        this.elements.container = container;

        // 创建导航按钮
        const prevBtn = document.createElement('button');
        prevBtn.className = 'viewer-prev-btn';
        prevBtn.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="15 18 9 12 15 6"></polyline>
            </svg>
        `;
        prevBtn.style.cssText = `
            position: absolute;
            left: 8px;
            top: 50%;
            transform: translateY(-50%);
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: none;
            background: var(--bg-secondary);
            border-radius: 50%;
            color: var(--text-primary);
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        `;

        const nextBtn = document.createElement('button');
        nextBtn.className = 'viewer-next-btn';
        nextBtn.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
        `;
        nextBtn.style.cssText = `
            position: absolute;
            right: 8px;
            top: 50%;
            transform: translateY(-50%);
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: none;
            background: var(--bg-secondary);
            border-radius: 50%;
            color: var(--text-primary);
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        `;

        container.appendChild(prevBtn);
        container.appendChild(nextBtn);
        this.elements.prevBtn = prevBtn;
        this.elements.nextBtn = nextBtn;

        // 创建底部指示点
        const dotsContainer = document.createElement('div');
        dotsContainer.className = 'viewer-dots';
        dotsContainer.style.cssText = `
            display: flex;
            justify-content: center;
            gap: 8px;
            padding: 16px;
        `;

        this.results.forEach((_, index) => {
            const dot = document.createElement('div');
            dot.className = `viewer-dot ${index === 0 ? 'active' : ''}`;
            dot.style.cssText = `
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: ${index === 0 ? 'var(--primary-color)' : 'var(--border-color)'};
                transition: background 200ms ease;
            `;
            dotsContainer.appendChild(dot);
            this.elements.dots.push(dot);
        });

        viewer.appendChild(container);
        viewer.appendChild(dotsContainer);

        document.body.appendChild(viewer);
        this.elements.viewer = viewer;

        this.updateNavigationButtons();
    }

    /**
     * 创建结果页面
     */
    private createResultPage(result: Result): HTMLElement {
        const page = document.createElement('div');
        page.className = 'result-page';

        // 创建标题
        const title = document.createElement('h2');
        title.textContent = result.title;
        title.style.cssText = `
            font-size: 20px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 16px;
        `;

        page.appendChild(title);

        // 创建图片（如果有）
        if (result.image) {
            const img = document.createElement('img');
            img.src = result.image;
            img.alt = result.title;
            img.style.cssText = `
                width: 100%;
                height: auto;
                border-radius: 12px;
                margin-bottom: 16px;
            `;
            page.appendChild(img);
        }

        // 创建内容
        const content = document.createElement('div');
        content.innerHTML = result.content;
        content.style.cssText = `
            font-size: 14px;
            line-height: 1.6;
            color: var(--text-primary);
        `;

        page.appendChild(content);

        // 创建元数据（如果有）
        if (result.metadata) {
            const metadata = document.createElement('div');
            metadata.className = 'result-metadata';
            metadata.style.cssText = `
                margin-top: 16px;
                padding: 12px;
                background: var(--bg-secondary);
                border-radius: 8px;
            `;

            Object.entries(result.metadata).forEach(([key, value]) => {
                const item = document.createElement('div');
                item.style.cssText = `
                    display: flex;
                    justify-content: space-between;
                    padding: 8px 0;
                    border-bottom: 1px solid var(--border-color);
                    font-size: 13px;
                `;

                const label = document.createElement('span');
                label.textContent = key;
                label.style.cssText = `
                    color: var(--text-secondary);
                `;

                const val = document.createElement('span');
                val.textContent = value.toString();
                val.style.cssText = `
                    color: var(--text-primary);
                    font-weight: 500;
                `;

                item.appendChild(label);
                item.appendChild(val);
                metadata.appendChild(item);
            });

            page.appendChild(metadata);
        }

        return page;
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        if (!this.elements.closeBtn) return;

        // 关闭按钮
        this.elements.closeBtn.addEventListener('click', () => {
            this.close();
        });

        // 导航按钮
        if (this.elements.prevBtn) {
            this.elements.prevBtn.addEventListener('click', () => {
                this.prev();
            });
        }

        if (this.elements.nextBtn) {
            this.elements.nextBtn.addEventListener('click', () => {
                this.next();
            });
        }

        // 滑动手势
        if (this.enableSwipe && this.elements.container) {
            this.setupSwipeGestures();
        }

        // 缩放手势
        if (this.enablePinchZoom && this.elements.content) {
            this.setupPinchZoom();
        }
    }

    /**
     * 设置滑动手势
     */
    private setupSwipeGestures(): void {
        if (!this.elements.container) return;

        let touchStartX = 0;
        let touchStartY = 0;

        this.elements.container.addEventListener('touchstart', (e: TouchEvent) => {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        }, { passive: true });

        this.elements.container.addEventListener('touchend', (e: TouchEvent) => {
            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;

            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;

            // 水平滑动
            if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 50) {
                if (deltaX > 0) {
                    this.prev();
                } else {
                    this.next();
                }
            }
        }, { passive: true });
    }

    /**
     * 设置缩放手势
     */
    private setupPinchZoom(): void {
        if (!this.elements.content) return;

        this.elements.content.addEventListener('touchstart', (e: TouchEvent) => {
            if (e.touches.length === 2) {
                this.initialDistance = this.getDistance(e.touches[0], e.touches[1]);
            }
        }, { passive: true });

        this.elements.content.addEventListener('touchmove', (e: TouchEvent) => {
            if (e.touches.length === 2) {
                const currentDistance = this.getDistance(e.touches[0], e.touches[1]);
                const scale = currentDistance / this.initialDistance;
                this.currentScale = Math.min(Math.max(scale, 1), 3);
                this.updateScale();
            }
        }, { passive: true });

        this.elements.content.addEventListener('touchend', () => {
            this.currentScale = 1;
            this.updateScale();
        });
    }

    /**
     * 计算两点距离
     */
    private getDistance(touch1: Touch, touch2: Touch): number {
        const dx = touch1.clientX - touch2.clientX;
        const dy = touch1.clientY - touch2.clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }

    /**
     * 更新缩放
     */
    private updateScale(): void {
        const pages = this.elements.content?.querySelectorAll('.result-page');
        if (pages) {
            pages.forEach((page) => {
                (page as HTMLElement).style.transform = `scale(${this.currentScale})`;
            });
        }
    }

    /**
     * 更新导航按钮状态
     */
    private updateNavigationButtons(): void {
        if (this.elements.prevBtn) {
            this.elements.prevBtn.style.opacity = this.currentIndex === 0 ? '0.3' : '1';
            this.elements.prevBtn.style.pointerEvents = this.currentIndex === 0 ? 'none' : 'auto';
        }

        if (this.elements.nextBtn) {
            this.elements.nextBtn.style.opacity = this.currentIndex === this.results.length - 1 ? '0.3' : '1';
            this.elements.nextBtn.style.pointerEvents = this.currentIndex === this.results.length - 1 ? 'none' : 'auto';
        }

        // 更新指示点
        this.elements.dots.forEach((dot, index) => {
            if (index === this.currentIndex) {
                dot.style.background = 'var(--primary-color)';
            } else {
                dot.style.background = 'var(--border-color)';
            }
        });

        // 更新内容位置
        if (this.elements.content) {
            this.elements.content.style.transform = `translateX(-${this.currentIndex * 100}%)`;
        }
    }

    /**
     * 触觉反馈
     */
    private hapticFeedback(): void {
        if (!this.enableHaptic) return;

        if ('vibrate' in navigator) {
            navigator.vibrate(10);
        }
    }

    /**
     * 打开查看器
     */
    public open(index: number = 0): void {
        if (this.elements.viewer) {
            this.currentIndex = index;
            this.elements.viewer.style.transform = 'translateY(0)';
            this.isOpen = true;
            this.updateNavigationButtons();
            this.hapticFeedback();
        }
    }

    /**
     * 关闭查看器
     */
    public close(): void {
        if (this.elements.viewer) {
            this.elements.viewer.style.transform = 'translateY(100%)';
            this.isOpen = false;
            this.hapticFeedback();
        }
    }

    /**
     * 上一页
     */
    public prev(): void {
        if (this.currentIndex > 0) {
            this.currentIndex--;
            this.updateNavigationButtons();
            this.hapticFeedback();
        }
    }

    /**
     * 下一页
     */
    public next(): void {
        if (this.currentIndex < this.results.length - 1) {
            this.currentIndex++;
            this.updateNavigationButtons();
            this.hapticFeedback();
        }
    }

    /**
     * 更新结果
     */
    public updateResults(results: Result[]): void {
        this.results = results;
        if (this.elements.content) {
            this.elements.content.innerHTML = '';
            this.elements.dots.forEach(dot => dot.remove());
            this.elements.dots = [];

            this.results.forEach((result, index) => {
                const page = this.createResultPage(result);
                page.style.cssText = `
                    min-width: 100%;
                    height: 100%;
                    padding: 16px;
                    overflow-y: auto;
                    transform: scale(${this.currentScale});
                    transition: transform 200ms ease;
                `;
                this.elements.content?.appendChild(page);

                const dot = document.createElement('div');
                dot.className = `viewer-dot ${index === 0 ? 'active' : ''}`;
                dot.style.cssText = `
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background: ${index === 0 ? 'var(--primary-color)' : 'var(--border-color)'};
                    transition: background 200ms ease;
                `;
                this.elements.dots.push(dot);
            });

            this.currentIndex = 0;
            this.updateNavigationButtons();
        }
    }

    /**
     * 销毁查看器
     */
    public destroy(): void {
        if (this.elements.viewer) {
            this.elements.viewer.remove();
        }
        this.elements.viewer = null;
        this.elements.container = null;
        this.elements.content = null;
        this.elements.closeBtn = null;
        this.elements.prevBtn = null;
        this.elements.nextBtn = null;
        this.elements.dots = [];
    }
}

// 导出
export default MobileResultViewer;