/**
 * 视口管理模块
 * 负责管理地图视口状态和交互
 */
export class Viewport {
    constructor(container) {
        this.container = container;
        this.width = container.clientWidth;
        this.height = container.clientHeight;
        this.isDragging = false;
        this.lastMouseX = 0;
        this.lastMouseY = 0;
        this.offsetX = 0;
        this.offsetY = 0;
    }

    /**
     * 获取容器尺寸
     */
    getSize() {
        return {
            width: this.width,
            height: this.height
        };
    }

    /**
     * 更新容器尺寸
     */
    updateSize() {
        this.width = this.container.clientWidth;
        this.height = this.container.clientHeight;
    }

    /**
     * 设置拖拽开始
     */
    startDrag(x, y) {
        this.isDragging = true;
        this.lastMouseX = x;
        this.lastMouseY = y;
    }

    /**
     * 处理拖拽移动
     */
    drag(x, y) {
        if (!this.isDragging) return null;

        const deltaX = x - this.lastMouseX;
        const deltaY = y - this.lastMouseY;

        this.lastMouseX = x;
        this.lastMouseY = y;
        this.offsetX += deltaX;
        this.offsetY += deltaY;

        return { deltaX, deltaY };
    }

    /**
     * 结束拖拽
     */
    endDrag() {
        this.isDragging = false;
    }

    /**
     * 重置偏移
     */
    resetOffset() {
        this.offsetX = 0;
        this.offsetY = 0;
    }

    /**
     * 获取当前偏移
     */
    getOffset() {
        return {
            x: this.offsetX,
            y: this.offsetY
        };
    }
}
