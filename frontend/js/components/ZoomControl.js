/**
 * 缩放控件
 * 右下角动态显示的缩放条
 */
export class ZoomControl {
    constructor(mapEngine, options = {}) {
        this.mapEngine = mapEngine;
        this.minZoom = options.minZoom || 1;
        this.maxZoom = options.maxZoom || 18;
        this.container = null;
        this.zoomBar = null;
        this.zoomThumb = null;
        this.fadeTimeout = null;
    }

    /**
     * 创建缩放控件
     * @param {string|HTMLElement} containerId - 容器 ID 或元素
     */
    create(containerId) {
        const container = typeof containerId === 'string'
            ? document.getElementById(containerId)
            : containerId;

        if (!container) {
            console.error('缩放控件容器不存在');
            return;
        }

        // 创建控件容器
        this.container = document.createElement('div');
        this.container.className = 'zoom-control';
        this.container.style.cssText = `
            position: absolute;
            bottom: 20px;
            right: 20px;
            width: 8px;
            height: 120px;
            background: rgba(255, 255, 255, 0.8);
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            opacity: 0;
            transition: opacity 0.3s;
            z-index: 1000;
        `;

        // 创建缩放条
        this.zoomBar = document.createElement('div');
        this.zoomBar.className = 'zoom-bar';
        this.zoomBar.style.cssText = `
            position: relative;
            width: 100%;
            height: 100%;
            border-radius: 4px;
        `;

        // 创建滑块
        this.zoomThumb = document.createElement('div');
        this.zoomThumb.className = 'zoom-thumb';
        this.zoomThumb.style.cssText = `
            position: absolute;
            left: 50%;
            transform: translateX(-50%);
            width: 16px;
            height: 16px;
            background: #007aff;
            border: 2px solid white;
            border-radius: 50%;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
            transition: top 0.2s;
        `;

        this.zoomBar.appendChild(this.zoomThumb);
        this.container.appendChild(this.zoomBar);
        container.appendChild(this.container);

        // 监听缩放变化
        this.mapEngine.onZoom((zoom) => {
            this.updateThumbPosition(zoom);
            this.showZoomBar();
        });

        // 初始化位置
        const currentZoom = this.mapEngine.getZoom();
        this.updateThumbPosition(currentZoom);

        console.log('✅ 缩放控件创建完成');
    }

    /**
     * 更新滑块位置
     * @param {number} zoom - 当前缩放级别
     */
    updateThumbPosition(zoom) {
        if (!this.zoomThumb) return;

        // 计算位置（从上到下，zoom 越大位置越低）
        const range = this.maxZoom - this.minZoom;
        const position = (this.maxZoom - zoom) / range;
        const barHeight = this.zoomBar.offsetHeight;
        const thumbHeight = this.zoomThumb.offsetHeight;

        // 计算 top 位置（留出滑块半径的空间）
        const top = position * (barHeight - thumbHeight);

        this.zoomThumb.style.top = `${top}px`;
    }

    /**
     * 显示缩放条
     */
    showZoomBar() {
        if (!this.container) return;

        // 显示
        this.container.style.opacity = '1';

        // 清除之前的定时器
        if (this.fadeTimeout) {
            clearTimeout(this.fadeTimeout);
        }

        // 1 秒后淡出
        this.fadeTimeout = setTimeout(() => {
            this.fadeOut();
        }, 1000);
    }

    /**
     * 淡出缩放条
     */
    fadeOut() {
        if (this.container) {
            this.container.style.opacity = '0';
        }
    }

    /**
     * 销毁控件
     */
    destroy() {
        if (this.fadeTimeout) {
            clearTimeout(this.fadeTimeout);
        }

        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }

        this.container = null;
        this.zoomBar = null;
        this.zoomThumb = null;
    }
}
