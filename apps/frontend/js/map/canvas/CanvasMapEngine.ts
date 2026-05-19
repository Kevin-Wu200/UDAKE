/**
 * 画布地图引擎
 * 基于 HTML5 Canvas 的纯前端地图渲染引擎
 * 继承 BaseMapEngine，使用 GK 投影进行坐标转换
 */
import { BaseMapEngine } from '../core/BaseMapEngine';
import { GKProjectionService } from './GKProjectionService';
import type {
    Bounds,
    MapInitOptions,
    CanvasEngineConfig,
    CanvasViewportBounds,
    GKCoordinate
} from '../../../types/map-engine';

/** 默认缩放级别的像素/米比例映射 (zoom 0 = 1:500000) */
const ZOOM_SCALE_BASE = 1 / 500000;

/**
 * 画布地图引擎
 */
export class CanvasMapEngine extends BaseMapEngine {
    /** 主画布容器 */
    private container: HTMLElement | null = null;

    /** 主画布（交互层，处理鼠标事件） */
    private mainCanvas: HTMLCanvasElement | null = null;

    /** 离屏画布（渲染层） */
    private offscreenCanvas: HTMLCanvasElement | null = null;

    /** 主画布 2D 上下文 */
    private mainCtx: CanvasRenderingContext2D | null = null;

    /** 离屏画布 2D 上下文 */
    private offscreenCtx: CanvasRenderingContext2D | null = null;

    /** GK 投影服务 */
    projectionService: GKProjectionService;

    /** 当前中心点 GK 坐标 */
    private _centerGK: GKCoordinate = { x: 500000, y: 0 };

    /** 当前缩放级别 */
    private _zoom: number = 5;

    /** 旋转角度（弧度） */
    private _rotation: number = 0;

    /** 最小缩放级别 */
    private _minZoom: number = 1;

    /** 最大缩放级别 */
    private _maxZoom: number = 18;

    /** 引擎配置 */
    private _config: CanvasEngineConfig;

    /** 交互状态 - 是否正在拖拽 */
    private _isDragging: boolean = false;

    /** 交互状态 - 拖拽起始像素坐标 */
    private _dragStart: { x: number; y: number } = { x: 0, y: 0 };

    /** 交互状态 - 拖拽开始时的偏移 */
    private _dragStartOffset: { x: number; y: number } = { x: 0, y: 0 };

    /** 视口偏移（GK 坐标）—— 左上角对应的 GK 坐标 */
    private _offsetX: number = 0;
    private _offsetY: number = 0;

    /** 当前像素/米缩放比例 */
    private _scale: number = 0;

    /** 点击事件处理器 */
    private _clickHandler: ((gkCoord: GKCoordinate, lngLat: [number, number]) => void) | null = null;

    /** 渲染回调（由适配器设置） */
    private _renderCallback: (() => void) | null = null;

    /** 动画帧 ID */
    private _animationFrameId: number | null = null;

    /** 是否需要重绘 */
    private _needsRender: boolean = false;

    /** 是否已初始化 */
    private _initialized: boolean = false;

    /** 深色模式 */
    private _darkMode: boolean = false;

    /** 事件处理器引用（用于清理） */
    private _boundHandlers: {
        onMouseDown: (e: MouseEvent) => void;
        onMouseMove: (e: MouseEvent) => void;
        onMouseUp: (e: MouseEvent) => void;
        onWheel: (e: WheelEvent) => void;
        onClick: (e: MouseEvent) => void;
        onResize: () => void;
        onDarkModeChange: (e: MediaQueryListEvent) => void;
    } | null = null;

    constructor(config: CanvasEngineConfig = {}) {
        super();
        this._config = config;

        this.projectionService = new GKProjectionService(config.projection);

        // 设置初始缩放级别
        this._zoom = config.zoom ?? 5;
        this._minZoom = config.minZoom ?? 1;
        this._maxZoom = config.maxZoom ?? 18;

        // 设置深色模式
        this._darkMode = config.darkMode ??
            (typeof window !== 'undefined' && window.matchMedia
                ? window.matchMedia('(prefers-color-scheme: dark)').matches
                : false);
    }

    /**
     * 初始化地图
     */
    async init(container: HTMLElement | string, options: MapInitOptions = {}): Promise<void> {
        // 合并选项
        const finalOptions = { ...options };
        if (finalOptions.center) {
            this._config.center = finalOptions.center;
        }
        if (finalOptions.zoom) {
            this._zoom = finalOptions.zoom;
        }

        // 获取容器
        if (typeof container === 'string') {
            this.container = document.getElementById(container);
        } else {
            this.container = container;
        }

        if (!this.container) {
            throw new Error('CanvasMapEngine: 找不到容器元素');
        }

        // 确保容器支持定位
        const containerStyle = window.getComputedStyle(this.container);
        if (containerStyle.position === 'static') {
            this.container.style.position = 'relative';
        }

        // 创建主画布（上层，拦截事件）
        this.mainCanvas = document.createElement('canvas');
        this.mainCanvas.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 2;
            cursor: grab;
        `;
        this.container.appendChild(this.mainCanvas);

        // 创建离屏画布
        this.offscreenCanvas = document.createElement('canvas');

        // 获取 2D 上下文
        this.mainCtx = this.mainCanvas.getContext('2d');
        this.offscreenCtx = this.offscreenCanvas.getContext('2d');

        // 设置响应式尺寸
        this._updateCanvasSize();

        // 设置初始中心点
        if (this._config.center) {
            const [lng, lat] = this._config.center;
            this.projectionService.autoConfig(lng);
            this._centerGK = this.projectionService.toGK(lng, lat);
        } else {
            // 默认北京天安门附近
            this.projectionService.autoConfig(116.39);
            this._centerGK = this.projectionService.toGK(116.39, 39.9);
        }

        // 更新缩放比例
        this._updateScale();

        // 计算初始视口偏移
        this._recenterOffset();

        // 绑定交互事件
        this._bindEvents();

        // 监听深色模式变化
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', this._getDarkModeHandler());

        // 开始渲染循环
        this._startRenderLoop();

        this._initialized = true;
        console.log('✅ CanvasMapEngine 初始化完成');
    }

    /**
     * 设置渲染回调
     */
    setRenderCallback(callback: () => void): void {
        this._renderCallback = callback;
        this._requestRender();
    }

    /**
     * 获取主画布
     */
    getMainCanvas(): HTMLCanvasElement | null {
        return this.mainCanvas;
    }

    /**
     * 获取离屏画布上下文
     */
    getOffscreenContext(): CanvasRenderingContext2D | null {
        return this.offscreenCtx;
    }

    /**
     * 获取深色模式状态
     */
    isDarkMode(): boolean {
        return this._darkMode;
    }

    /**
     * 设置深色模式
     */
    setDarkMode(dark: boolean): void {
        if (this._darkMode !== dark) {
            this._darkMode = dark;
            this._requestRender();
        }
    }

    /**
     * 获取视口偏移 X（GK 坐标）
     */
    getOffsetX(): number {
        return this._offsetX;
    }

    /**
     * 获取视口偏移 Y（GK 坐标）
     */
    getOffsetY(): number {
        return this._offsetY;
    }

    /**
     * 获取当前缩放比例（像素/米）
     */
    getScale(): number {
        return this._scale;
    }

    /**
     * 获取画布像素尺寸
     */
    getCanvasSize(): { width: number; height: number } {
        return {
            width: this.mainCanvas?.width ?? 0,
            height: this.mainCanvas?.height ?? 0
        };
    }

    /**
     * 设置点击事件处理器
     */
    setClickHandler(handler: (gkCoord: GKCoordinate, lngLat: [number, number]) => void): void {
        this._clickHandler = handler;
    }

    // ========== BaseMapEngine 抽象方法实现 ==========

    setCenter(center: [number, number]): void {
        const [lng, lat] = center;
        this._centerGK = this.projectionService.toGK(lng, lat);
        this._recenterOffset();
        this._requestRender();
        this.triggerMoveCallbacks(center);
    }

    getCenter(): [number, number] {
        return this.projectionService.fromGK(this._centerGK.x, this._centerGK.y);
    }

    setZoom(zoom: number): void {
        // 限制缩放范围
        this._zoom = Math.max(this._minZoom, Math.min(this._maxZoom, zoom));
        this._updateScale();
        this._recenterOffset();
        this._requestRender();
        this.triggerZoomCallbacks(this._zoom);
    }

    getZoom(): number {
        return this._zoom;
    }

    async fitToBounds(bounds: Bounds): Promise<void> {
        const { minLng, minLat, maxLng, maxLat } = bounds;

        // 转换四个角到 GK
        const sw = this.projectionService.toGK(minLng, minLat);
        const ne = this.projectionService.toGK(maxLng, maxLat);

        const canvasSize = this.getCanvasSize();
        const result = this.projectionService.fitToGKBounds(
            { minX: sw.x, minY: sw.y, maxX: ne.x, maxY: ne.y },
            canvasSize.width,
            canvasSize.height
        );

        this._offsetX = result.offsetX;
        this._offsetY = result.offsetY;
        this._scale = result.scale;

        // 反算缩放级别
        this._zoom = Math.round(Math.log2(this._scale / ZOOM_SCALE_BASE));
        this._zoom = Math.max(this._minZoom, Math.min(this._maxZoom, this._zoom));

        // 更新中心点
        const centerGKX = (sw.x + ne.x) / 2;
        const centerGKY = (sw.y + ne.y) / 2;
        this._centerGK = { x: centerGKX, y: centerGKY };

        this._requestRender();
        this.triggerMoveCallbacks(this.getCenter());
    }

    /**
     * 获取当前视口覆盖的 GK 坐标范围
     */
    getViewportBounds(): CanvasViewportBounds {
        const canvasSize = this.getCanvasSize();
        return {
            minX: this._offsetX,
            minY: this._offsetY,
            maxX: this._offsetX + canvasSize.width / this._scale,
            maxY: this._offsetY + canvasSize.height / this._scale
        };
    }

    /**
     * 请求重绘
     */
    private _requestRender(): void {
        this._needsRender = true;
    }

    /**
     * 开始渲染循环
     */
    private _startRenderLoop(): void {
        const loop = () => {
            if (this._needsRender) {
                this._doRender();
                this._needsRender = false;
            }
            this._animationFrameId = requestAnimationFrame(loop);
        };
        this._animationFrameId = requestAnimationFrame(loop);
    }

    /**
     * 执行渲染
     */
    private _doRender(): void {
        if (!this.mainCtx || !this.offscreenCtx || !this.mainCanvas || !this.offscreenCanvas) return;

        const { width, height } = this.getCanvasSize();

        // 清空主画布
        this.mainCtx.clearRect(0, 0, width, height);

        // 绘制背景色（适配深色模式）
        this.mainCtx.fillStyle = this._darkMode ? '#1a1a2e' : '#f0f0f0';
        this.mainCtx.fillRect(0, 0, width, height);

        // 调用渲染回调（由适配器在离屏画布上绘制内容）
        if (this._renderCallback) {
            this._renderCallback();
        }

        // 将离屏画布绘制到主画布
        this.mainCtx.drawImage(this.offscreenCanvas, 0, 0);
    }

    /**
     * 更新画布尺寸
     */
    private _updateCanvasSize(): void {
        if (!this.container || !this.mainCanvas || !this.offscreenCanvas) return;

        const rect = this.container.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;

        const width = rect.width;
        const height = rect.height;

        // 主画布
        this.mainCanvas.width = width * dpr;
        this.mainCanvas.height = height * dpr;
        this.mainCtx?.scale(dpr, dpr);
        this.mainCanvas.style.width = `${width}px`;
        this.mainCanvas.style.height = `${height}px`;

        // 离屏画布
        this.offscreenCanvas.width = width * dpr;
        this.offscreenCanvas.height = height * dpr;
        this.offscreenCtx?.scale(dpr, dpr);
    }

    /**
     * 更新缩放比例
     */
    private _updateScale(): void {
        this._scale = ZOOM_SCALE_BASE * Math.pow(2, this._zoom);
    }

    /**
     * 根据中心点重新计算视口偏移
     */
    private _recenterOffset(): void {
        const canvasSize = this.getCanvasSize();
        this._offsetX = this._centerGK.x - canvasSize.width / (2 * this._scale);
        this._offsetY = this._centerGK.y - canvasSize.height / (2 * this._scale);
    }

    // ========== 交互事件 ==========

    private _bindEvents(): void {
        if (!this.mainCanvas) return;

        this._boundHandlers = {
            onMouseDown: this._onMouseDown.bind(this),
            onMouseMove: this._onMouseMove.bind(this),
            onMouseUp: this._onMouseUp.bind(this),
            onWheel: this._onWheel.bind(this),
            onClick: this._onClick.bind(this),
            onResize: this._onResize.bind(this),
            onDarkModeChange: this._onDarkModeChange.bind(this)
        };

        this.mainCanvas.addEventListener('mousedown', this._boundHandlers.onMouseDown);
        window.addEventListener('mousemove', this._boundHandlers.onMouseMove);
        window.addEventListener('mouseup', this._boundHandlers.onMouseUp);
        this.mainCanvas.addEventListener('wheel', this._boundHandlers.onWheel, { passive: false });
        this.mainCanvas.addEventListener('click', this._boundHandlers.onClick);
        window.addEventListener('resize', this._boundHandlers.onResize);

        // 触摸事件支持
        this.mainCanvas.addEventListener('touchstart', this._onTouchStart.bind(this), { passive: false });
        this.mainCanvas.addEventListener('touchmove', this._onTouchMove.bind(this), { passive: false });
        this.mainCanvas.addEventListener('touchend', this._onTouchEnd.bind(this));
    }

    private _onMouseDown(e: MouseEvent): void {
        this._isDragging = true;
        this._dragStart = { x: e.clientX, y: e.clientY };
        this._dragStartOffset = { x: this._offsetX, y: this._offsetY };
        if (this.mainCanvas) {
            this.mainCanvas.style.cursor = 'grabbing';
        }
    }

    private _onMouseMove(e: MouseEvent): void {
        if (!this._isDragging) return;

        const dx = e.clientX - this._dragStart.x;
        const dy = e.clientY - this._dragStart.y;

        // 像素偏移转换为 GK 坐标偏移
        this._offsetX = this._dragStartOffset.x - dx / this._scale;
        this._offsetY = this._dragStartOffset.y + dy / this._scale;

        // 更新中心点
        const canvasSize = this.getCanvasSize();
        this._centerGK.x = this._offsetX + canvasSize.width / (2 * this._scale);
        this._centerGK.y = this._offsetY + canvasSize.height / (2 * this._scale);

        this._requestRender();
    }

    private _onMouseUp(_e: MouseEvent): void {
        if (this._isDragging) {
            this._isDragging = false;
            if (this.mainCanvas) {
                this.mainCanvas.style.cursor = 'grab';
            }
        }
    }

    private _onWheel(e: WheelEvent): void {
        e.preventDefault();

        // 获取鼠标在画布上的像素位置
        const rect = this.mainCanvas!.getBoundingClientRect();
        const mousePixelX = e.clientX - rect.left;
        const mousePixelY = e.clientY - rect.top;

        // 缩放前鼠标对应的 GK 坐标
        const canvasSize = this.getCanvasSize();
        const mouseGK = this.projectionService.pixelToGK(
            mousePixelX, mousePixelY,
            this._offsetX, this._offsetY,
            this._scale, canvasSize.height
        );

        // 调整缩放级别
        const delta = e.deltaY > 0 ? -0.5 : 0.5;
        this._zoom = Math.max(this._minZoom, Math.min(this._maxZoom, this._zoom + delta));
        this._updateScale();

        // 保持鼠标指向的 GK 坐标不变
        this._offsetX = mouseGK.x - mousePixelX / this._scale;
        this._offsetY = mouseGK.y - (canvasSize.height - mousePixelY) / this._scale;

        // 更新中心点
        this._centerGK.x = this._offsetX + canvasSize.width / (2 * this._scale);
        this._centerGK.y = this._offsetY + canvasSize.height / (2 * this._scale);

        this.triggerZoomCallbacks(this._zoom);
        this._requestRender();
    }

    private _onClick(e: MouseEvent): void {
        if (!this._clickHandler) return;

        const rect = this.mainCanvas!.getBoundingClientRect();
        const pixelX = e.clientX - rect.left;
        const pixelY = e.clientY - rect.top;
        const canvasSize = this.getCanvasSize();

        const gk = this.projectionService.pixelToGK(
            pixelX, pixelY,
            this._offsetX, this._offsetY,
            this._scale, canvasSize.height
        );

        const lngLat = this.projectionService.fromGK(gk.x, gk.y);
        this._clickHandler(gk, lngLat);
    }

    private _onResize(): void {
        this._updateCanvasSize();
        this._recenterOffset();
        this._requestRender();
    }

    // ========== 触摸事件 ==========

    private _touchStartDistance: number = 0;
    private _touchStartZoom: number = 0;
    private _touchStartCenter: GKCoordinate = { x: 0, y: 0 };

    private _onTouchStart(e: TouchEvent): void {
        if (e.touches.length === 1) {
            // 单指拖拽
            e.preventDefault();
            this._isDragging = true;
            this._dragStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
            this._dragStartOffset = { x: this._offsetX, y: this._offsetY };
        } else if (e.touches.length === 2) {
            // 双指缩放
            e.preventDefault();
            this._isDragging = false;
            const dx = e.touches[1].clientX - e.touches[0].clientX;
            const dy = e.touches[1].clientY - e.touches[0].clientY;
            this._touchStartDistance = Math.sqrt(dx * dx + dy * dy);
            this._touchStartZoom = this._zoom;
            this._touchStartCenter = { ...this._centerGK };
        }
    }

    private _onTouchMove(e: TouchEvent): void {
        if (e.touches.length === 1 && this._isDragging) {
            e.preventDefault();
            const dx = e.touches[0].clientX - this._dragStart.x;
            const dy = e.touches[0].clientY - this._dragStart.y;
            this._offsetX = this._dragStartOffset.x - dx / this._scale;
            this._offsetY = this._dragStartOffset.y + dy / this._scale;
            this._requestRender();
        } else if (e.touches.length === 2) {
            e.preventDefault();
            const dx = e.touches[1].clientX - e.touches[0].clientX;
            const dy = e.touches[1].clientY - e.touches[0].clientY;
            const distance = Math.sqrt(dx * dx + dy * dy);
            const scaleFactor = distance / this._touchStartDistance;

            this._zoom = Math.max(this._minZoom,
                Math.min(this._maxZoom, this._touchStartZoom + Math.log2(scaleFactor)));
            this._updateScale();
            this._recenterOffset();
            this._requestRender();
        }
    }

    private _onTouchEnd(_e: TouchEvent): void {
        this._isDragging = false;
    }

    // ========== 深色模式 ==========

    private _getDarkModeHandler(): (e: MediaQueryListEvent) => void {
        return (e: MediaQueryListEvent) => {
            this._darkMode = e.matches;
            this._requestRender();
        };
    }

    private _onDarkModeChange(e: MediaQueryListEvent): void {
        this._darkMode = e.matches;
        this._requestRender();
    }

    // ========== 销毁 ==========

    destroy(): void {
        super.destroy();

        // 取消动画帧
        if (this._animationFrameId !== null) {
            cancelAnimationFrame(this._animationFrameId);
            this._animationFrameId = null;
        }

        // 移除事件监听
        if (this._boundHandlers && this.mainCanvas) {
            this.mainCanvas.removeEventListener('mousedown', this._boundHandlers.onMouseDown);
            window.removeEventListener('mousemove', this._boundHandlers.onMouseMove);
            window.removeEventListener('mouseup', this._boundHandlers.onMouseUp);
            this.mainCanvas.removeEventListener('wheel', this._boundHandlers.onWheel);
            this.mainCanvas.removeEventListener('click', this._boundHandlers.onClick);
            window.removeEventListener('resize', this._boundHandlers.onResize);
            window.matchMedia('(prefers-color-scheme: dark)')
                .removeEventListener('change', this._boundHandlers.onDarkModeChange);
            this._boundHandlers = null;
        }

        // 移除画布元素
        if (this.mainCanvas && this.mainCanvas.parentNode) {
            this.mainCanvas.parentNode.removeChild(this.mainCanvas);
        }

        this.mainCanvas = null;
        this.offscreenCanvas = null;
        this.mainCtx = null;
        this.offscreenCtx = null;
        this.container = null;
        this._renderCallback = null;
        this._clickHandler = null;
        this._initialized = false;

        console.log('✅ CanvasMapEngine 已销毁');
    }
}
