/**
 * 触摸手势管理器
 * 实现地图触摸交互（拖拽、缩放、长按）和手势事件处理
 * 支持三指操作、手势冲突检测、撤销重做等功能
 */

import { Haptics, ImpactStyle } from '@capacitor/haptics';

export type GestureType = 'tap' | 'doubleTap' | 'longPress' | 'swipe' | 'pinch' | 'rotate' | 'tripleFingerPinch' | 'quickSwipe' | 'layerSwipe';

export interface GestureEvent {
    type: GestureType;
    center: { x: number; y: number };
    distance?: number;
    angle?: number;
    direction?: 'up' | 'down' | 'left' | 'right';
    delta?: { x: number; y: number };
    scale?: number;
    rotation?: number;
    velocity?: number;
    layerIndex?: number;
}

export interface GestureCallback {
    (event: GestureEvent): void;
}

interface TouchGestureManagerOptions {
    enableTap?: boolean;
    enableDoubleTap?: boolean;
    enableLongPress?: boolean;
    enableSwipe?: boolean;
    enablePinch?: boolean;
    enableRotate?: boolean;
    enableTripleFingerPinch?: boolean;
    enableQuickSwipe?: boolean;
    enableLayerSwipe?: boolean;
    longPressDelay?: number;
    doubleTapDelay?: number;
    swipeThreshold?: number;
    quickSwipeThreshold?: number;
    enableHaptic?: boolean;
    enableAudioFeedback?: boolean;
    enableUndoRedo?: boolean;
    maxUndoSteps?: number;
    enableGestureConflictDetection?: boolean;
    enableVisualFeedback?: boolean;
}

class TouchGestureManager {
    private options: Required<TouchGestureManagerOptions>;
    private callbacks: Map<GestureType, Set<GestureCallback>> = new Map();
    private element: HTMLElement | null = null;

    // 触摸状态
    private touches: Map<number, Touch> = new Map();
    private startTime: number = 0;
    private startX: number = 0;
    private startY: number = 0;
    private lastTapTime: number = 0;
    private longPressTimer: number | null = null;
    private initialDistance: number = 0;
    private initialAngle: number = 0;
    private initialTripleDistance: number = 0;
    private lastTouchTime: number = 0;
    private gestureStartTime: number = 0;
    private isGestureInProgress: boolean = false;

    // 手势历史和撤销重做
    private gestureHistory: GestureEvent[] = [];
    private undoStack: GestureEvent[] = [];
    private redoStack: GestureEvent[] = [];
    private maxUndoSteps: number = 10;

    // 手势冲突检测
    private gesturePriority: Map<GestureType, number> = new Map();
    private activeGesture: GestureType | null = null;
    private conflictingGestures: Set<GestureType> = new Set();

    // 音频上下文
    private audioContext: AudioContext | null = null;

    // 可视化反馈
    private feedbackElement: HTMLElement | null = null;

    constructor(options: TouchGestureManagerOptions = {}) {
        this.maxUndoSteps = options.maxUndoSteps ?? 10;
        this.options = {
            enableTap: options.enableTap ?? true,
            enableDoubleTap: options.enableDoubleTap ?? true,
            enableLongPress: options.enableLongPress ?? true,
            enableSwipe: options.enableSwipe ?? true,
            enablePinch: options.enablePinch ?? true,
            enableRotate: options.enableRotate ?? true,
            enableTripleFingerPinch: options.enableTripleFingerPinch ?? true,
            enableQuickSwipe: options.enableQuickSwipe ?? true,
            enableLayerSwipe: options.enableLayerSwipe ?? true,
            longPressDelay: options.longPressDelay ?? 500,
            doubleTapDelay: options.doubleTapDelay ?? 300,
            swipeThreshold: options.swipeThreshold ?? 50,
            quickSwipeThreshold: options.quickSwipeThreshold ?? 100,
            enableHaptic: options.enableHaptic ?? true,
            enableAudioFeedback: options.enableAudioFeedback ?? false,
            enableUndoRedo: options.enableUndoRedo ?? true,
            maxUndoSteps: options.maxUndoSteps ?? 10,
            enableGestureConflictDetection: options.enableGestureConflictDetection ?? true,
            enableVisualFeedback: options.enableVisualFeedback ?? true,
        };

        // 初始化手势优先级（数值越高优先级越高）
        this.initializeGesturePriority();
    }

    /**
     * 初始化手势优先级
     */
    private initializeGesturePriority(): void {
        this.gesturePriority.set('longPress', 10);
        this.gesturePriority.set('tripleFingerPinch', 9);
        this.gesturePriority.set('pinch', 8);
        this.gesturePriority.set('rotate', 8);
        this.gesturePriority.set('quickSwipe', 7);
        this.gesturePriority.set('layerSwipe', 7);
        this.gesturePriority.set('swipe', 6);
        this.gesturePriority.set('doubleTap', 5);
        this.gesturePriority.set('tap', 4);
    }

    /**
     * 初始化音频上下文
     */
    private initAudioContext(): void {
        if (!this.options.enableAudioFeedback || this.audioContext) return;

        try {
            this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
        } catch (e) {
            console.warn('音频上下文初始化失败:', e);
        }
    }

    /**
     * 播放触觉反馈声音
     */
    private playTapSound(): void {
        if (!this.audioContext || !this.options.enableAudioFeedback) return;

        try {
            const oscillator = this.audioContext.createOscillator();
            const gainNode = this.audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(this.audioContext.destination);

            oscillator.frequency.value = 800;
            oscillator.type = 'sine';

            gainNode.gain.setValueAtTime(0.1, this.audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + 0.1);

            oscillator.start(this.audioContext.currentTime);
            oscillator.stop(this.audioContext.currentTime + 0.1);
        } catch (e) {
            console.warn('播放声音失败:', e);
        }
    }

    /**
     * 触觉反馈（使用Capacitor Haptics）
     */
    private async hapticFeedback(style: ImpactStyle = ImpactStyle.Light): Promise<void> {
        if (!this.options.enableHaptic) return;

        try {
            await Haptics.impact({ style });
        } catch (e) {
            // 如果Capacitor Haptics不可用，回退到标准vibrate API
            if ('vibrate' in navigator) {
                const pattern = this.getVibrationPattern(style);
                navigator.vibrate(pattern);
            }
        }
    }

    /**
     * 根据ImpactStyle获取震动模式
     */
    private getVibrationPattern(style: ImpactStyle): number | number[] {
        switch (style) {
            case ImpactStyle.Heavy:
                return [50, 10, 50];
            case ImpactStyle.Medium:
                return [30, 10, 30];
            case ImpactStyle.Light:
            default:
                return 10;
        }
    }

    /**
     * 手势成功反馈
     */
    private async gestureSuccessFeedback(gestureType: GestureType): Promise<void> {
        if (!this.options.enableHaptic) return;

        try {
            switch (gestureType) {
                case 'longPress':
                case 'tripleFingerPinch':
                    await Haptics.impact({ style: ImpactStyle.Heavy });
                    break;
                case 'pinch':
                case 'rotate':
                case 'quickSwipe':
                case 'layerSwipe':
                    await Haptics.impact({ style: ImpactStyle.Medium });
                    break;
                case 'tap':
                case 'doubleTap':
                case 'swipe':
                    await Haptics.impact({ style: ImpactStyle.Light });
                    break;
            }
        } catch (e) {
            console.warn('手势反馈失败:', e);
        }
    }

    /**
     * 错误反馈
     */
    private async errorFeedback(): Promise<void> {
        if (!this.options.enableHaptic) return;

        try {
            await Haptics.notification({ type: NotificationType.Error as any });
        } catch (e) {
            if ('vibrate' in navigator) {
                navigator.vibrate([100, 50, 100]);
            }
        }
    }

    /**
     * 触摸反馈（高亮、震动、声音）
     */
    private async touchFeedback(type: 'tap' | 'longPress' | 'swipe' | 'pinch' | 'gestureSuccess' | 'error'): Promise<void> {
        // 触觉反馈
        switch (type) {
            case 'tap':
                await this.hapticFeedback(ImpactStyle.Light);
                break;
            case 'longPress':
                await this.hapticFeedback(ImpactStyle.Heavy);
                break;
            case 'swipe':
                await this.hapticFeedback(ImpactStyle.Medium);
                break;
            case 'pinch':
                await this.hapticFeedback(ImpactStyle.Medium);
                break;
            case 'gestureSuccess':
                await this.hapticFeedback(ImpactStyle.Medium);
                break;
            case 'error':
                await this.errorFeedback();
                break;
        }

        // 音频反馈
        if (type === 'tap') {
            this.playTapSound();
        }

        // 可视化反馈
        if (this.options.enableVisualFeedback) {
            this.showVisualFeedback(type);
        }
    }

    /**
     * 显示可视化反馈
     */
    private showVisualFeedback(type: string): void {
        if (!this.element) return;

        // 创建或获取反馈元素
        if (!this.feedbackElement) {
            this.feedbackElement = document.createElement('div');
            this.feedbackElement.style.cssText = `
                position: absolute;
                pointer-events: none;
                border-radius: 50%;
                background: rgba(59, 130, 246, 0.3);
                transform: scale(0);
                transition: transform 0.2s ease-out, opacity 0.2s ease-out;
                z-index: 1000;
            `;
            this.element.appendChild(this.feedbackElement);
        }

        // 根据反馈类型设置大小和颜色
        let size = 50;
        let color = 'rgba(59, 130, 246, 0.3)';

        switch (type) {
            case 'tap':
                size = 40;
                color = 'rgba(59, 130, 246, 0.3)';
                break;
            case 'longPress':
                size = 60;
                color = 'rgba(16, 185, 129, 0.3)';
                break;
            case 'gestureSuccess':
                size = 70;
                color = 'rgba(16, 185, 129, 0.3)';
                break;
            case 'error':
                size = 70;
                color = 'rgba(239, 68, 68, 0.3)';
                break;
        }

        this.feedbackElement.style.width = `${size}px`;
        this.feedbackElement.style.height = `${size}px`;
        this.feedbackElement.style.background = color;

        // 播放动画
        requestAnimationFrame(() => {
            if (this.feedbackElement) {
                this.feedbackElement.style.transform = 'scale(1)';
                this.feedbackElement.style.opacity = '1';

                setTimeout(() => {
                    if (this.feedbackElement) {
                        this.feedbackElement.style.transform = 'scale(1.5)';
                        this.feedbackElement.style.opacity = '0';
                    }
                }, 200);
            }
        });
    }

    /**
     * 绑定到元素
     */
    public bind(element: HTMLElement): void {
        this.unbind();
        this.element = element;

        // 使用被动事件监听器优化性能
        element.addEventListener('touchstart', this.handleTouchStart, { passive: true });
        element.addEventListener('touchmove', this.handleTouchMove, { passive: false });
        element.addEventListener('touchend', this.handleTouchEnd, { passive: true });
        element.addEventListener('touchcancel', this.handleTouchCancel, { passive: true });
    }

    /**
     * 解绑元素
     */
    public unbind(): void {
        if (this.element) {
            this.element.removeEventListener('touchstart', this.handleTouchStart);
            this.element.removeEventListener('touchmove', this.handleTouchMove);
            this.element.removeEventListener('touchend', this.handleTouchEnd);
            this.element.removeEventListener('touchcancel', this.handleTouchCancel);
            this.element = null;
        }
    }

    /**
     * 处理触摸开始
     */
    private handleTouchStart = (e: TouchEvent): void => {
        for (let i = 0; i < e.changedTouches.length; i++) {
            const touch = e.changedTouches[i];
            this.touches.set(touch.identifier, touch);
        }

        this.lastTouchTime = Date.now();
        this.gestureStartTime = this.lastTouchTime;

        // 单指操作
        if (e.touches.length === 1) {
            const touch = e.touches[0];
            this.startTime = Date.now();
            this.startX = touch.clientX;
            this.startY = touch.clientY;

            // 设置长按定时器
            if (this.options.enableLongPress) {
                this.longPressTimer = window.setTimeout(() => {
                    if (this.checkGestureConflict('longPress')) {
                        this.triggerGesture('longPress', {
                            type: 'longPress',
                            center: { x: touch.clientX, y: touch.clientY },
                        });
                        this.touchFeedback('longPress');
                    }
                }, this.options.longPressDelay);
            }
        }
        // 双指操作
        else if (e.touches.length === 2) {
            this.clearLongPress();

            const touch1 = e.touches[0];
            const touch2 = e.touches[1];

            this.initialDistance = this.getDistance(touch1, touch2);
            this.initialAngle = this.getAngle(touch1, touch2);
        }
        // 三指操作
        else if (e.touches.length === 3 && this.options.enableTripleFingerPinch) {
            this.clearLongPress();
            this.activeGesture = 'tripleFingerPinch';
            this.initialTripleDistance = this.getTripleFingerDistance(e.touches);
        }
    };

    /**
     * 处理触摸移动
     */
    private handleTouchMove = (e: TouchEvent): void => {
        // 更新触摸点
        for (let i = 0; i < e.changedTouches.length; i++) {
            const touch = e.changedTouches[i];
            this.touches.set(touch.identifier, touch);
        }

        // 清除长按定时器
        this.clearLongPress();

        // 单指操作 - 可能是拖拽
        if (e.touches.length === 1 && this.options.enableSwipe) {
            // 在这里可以添加拖拽逻辑
        }
        // 双指操作 - 缩放和旋转
        else if (e.touches.length === 2) {
            const touch1 = e.touches[0];
            const touch2 = e.touches[1];

            const currentDistance = this.getDistance(touch1, touch2);
            const currentAngle = this.getAngle(touch1, touch2);

            // 触发缩放手势
            if (this.options.enablePinch && currentDistance > 0 && this.checkGestureConflict('pinch')) {
                const scale = currentDistance / this.initialDistance;
                const center = this.getCenter(touch1, touch2);

                this.triggerGesture('pinch', {
                    type: 'pinch',
                    center,
                    distance: currentDistance,
                    scale,
                });
            }

            // 触发旋转手势
            if (this.options.enableRotate && this.checkGestureConflict('rotate')) {
                const rotation = currentAngle - this.initialAngle;
                const center = this.getCenter(touch1, touch2);

                this.triggerGesture('rotate', {
                    type: 'rotate',
                    center,
                    angle: currentAngle,
                    rotation,
                });
            }
        }
        // 三指操作 - 三指捏合
        else if (e.touches.length === 3 && this.options.enableTripleFingerPinch && this.activeGesture === 'tripleFingerPinch') {
            const currentDistance = this.getTripleFingerDistance(e.touches);
            const center = this.getTripleFingerCenter(e.touches);

            if (currentDistance > 0) {
                const scale = currentDistance / this.initialTripleDistance;

                this.triggerGesture('tripleFingerPinch', {
                    type: 'tripleFingerPinch',
                    center,
                    distance: currentDistance,
                    scale,
                });
            }
        }
    };

    /**
     * 处理触摸结束
     */
    private handleTouchEnd = (e: TouchEvent): void => {
        // 移除结束的触摸点
        for (let i = 0; i < e.changedTouches.length; i++) {
            const touch = e.changedTouches[i];
            this.touches.delete(touch.identifier);
        }

        // 清除长按定时器
        this.clearLongPress();

        // 所有触摸点都结束了
        if (this.touches.size === 0 && e.touches.length === 0) {
            const duration = Date.now() - this.startTime;
            const touch = e.changedTouches[0];
            const deltaX = touch.clientX - this.startX;
            const deltaY = touch.clientY - this.startY;
            const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
            const velocity = distance / duration;

            // 检测点击
            if (distance < 10 && duration < 300 && this.options.enableTap) {
                const now = Date.now();
                const timeSinceLastTap = now - this.lastTapTime;

                // 双击
                if (timeSinceLastTap < this.options.doubleTapDelay && this.options.enableDoubleTap) {
                    if (this.checkGestureConflict('doubleTap')) {
                        this.triggerGesture('doubleTap', {
                            type: 'doubleTap',
                            center: { x: touch.clientX, y: touch.clientY },
                        });
                        this.touchFeedback('tap');
                    }
                }
                // 单击
                else {
                    if (this.checkGestureConflict('tap')) {
                        this.triggerGesture('tap', {
                            type: 'tap',
                            center: { x: touch.clientX, y: touch.clientY },
                        });
                        this.touchFeedback('tap');
                    }
                }

                this.lastTapTime = now;
            }
            // 检测快速滑动（速度阈值检测）
            else if (duration < 200 && velocity > 0.5 && this.options.enableQuickSwipe && this.checkGestureConflict('quickSwipe')) {
                const direction = this.getSwipeDirection(deltaX, deltaY);

                this.triggerGesture('quickSwipe', {
                    type: 'quickSwipe',
                    center: { x: touch.clientX, y: touch.clientY },
                    direction,
                    delta: { x: deltaX, y: deltaY },
                    velocity,
                });
                this.touchFeedback('gestureSuccess');
            }
            // 检测普通滑动
            else if (distance >= this.options.swipeThreshold && this.options.enableSwipe && this.checkGestureConflict('swipe')) {
                const direction = this.getSwipeDirection(deltaX, deltaY);

                // 检测是否是图层切换滑动（水平滑动且距离足够长）
                if (this.options.enableLayerSwipe && (direction === 'left' || direction === 'right') && distance > 100) {
                    const layerIndex = direction === 'right' ? 1 : -1;

                    this.triggerGesture('layerSwipe', {
                        type: 'layerSwipe',
                        center: { x: touch.clientX, y: touch.clientY },
                        direction,
                        delta: { x: deltaX, y: deltaY },
                        layerIndex,
                    });
                    this.touchFeedback('gestureSuccess');
                } else {
                    this.triggerGesture('swipe', {
                        type: 'swipe',
                        center: { x: touch.clientX, y: touch.clientY },
                        direction,
                        delta: { x: deltaX, y: deltaY },
                    });
                    this.touchFeedback('swipe');
                }
            }
        }

        // 重置活动手势
        this.activeGesture = null;
    };

    /**
     * 处理触摸取消
     */
    private handleTouchCancel = (): void => {
        this.clearLongPress();
        this.touches.clear();
        this.activeGesture = null;
    };

    /**
     * 计算三指距离
     */
    private getTripleFingerDistance(touches: TouchList): number {
        if (touches.length < 3) return 0;

        const touch1 = touches[0];
        const touch2 = touches[1];
        const touch3 = touches[2];

        const d12 = this.getDistance(touch1, touch2);
        const d23 = this.getDistance(touch2, touch3);
        const d31 = this.getDistance(touch3, touch1);

        return (d12 + d23 + d31) / 3;
    }

    /**
     * 计算三指中心
     */
    private getTripleFingerCenter(touches: TouchList): { x: number; y: number } {
        if (touches.length < 3) return { x: 0, y: 0 };

        let x = 0;
        let y = 0;

        for (let i = 0; i < 3; i++) {
            x += touches[i].clientX;
            y += touches[i].clientY;
        }

        return {
            x: x / 3,
            y: y / 3,
        };
    }

    /**
     * 清除长按定时器
     */
    private clearLongPress(): void {
        if (this.longPressTimer !== null) {
            clearTimeout(this.longPressTimer);
            this.longPressTimer = null;
        }
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
     * 计算两点角度
     */
    private getAngle(touch1: Touch, touch2: Touch): number {
        const dx = touch2.clientX - touch1.clientX;
        const dy = touch2.clientY - touch1.clientY;
        return Math.atan2(dy, dx) * 180 / Math.PI;
    }

    /**
     * 计算两点中心
     */
    private getCenter(touch1: Touch, touch2: Touch): { x: number; y: number } {
        return {
            x: (touch1.clientX + touch2.clientX) / 2,
            y: (touch1.clientY + touch2.clientY) / 2,
        };
    }

    /**
     * 获取滑动方向
     */
    private getSwipeDirection(deltaX: number, deltaY: number): 'up' | 'down' | 'left' | 'right' {
        if (Math.abs(deltaX) > Math.abs(deltaY)) {
            return deltaX > 0 ? 'right' : 'left';
        } else {
            return deltaY > 0 ? 'down' : 'up';
        }
    }

    /**
     * 触发手势回调
     */
    private triggerGesture(type: GestureType, event: GestureEvent): void {
        const callbacks = this.callbacks.get(type);
        if (callbacks) {
            callbacks.forEach(callback => callback(event));
        }

        // 添加到历史记录
        if (this.options.enableUndoRedo) {
            this.addToHistory(event);
        }

        // 标记手势为活动状态
        this.activeGesture = type;
        this.isGestureInProgress = true;

        // 手势完成后重置状态
        setTimeout(() => {
            this.isGestureInProgress = false;
        }, 100);
    }

    /**
     * 检测手势冲突
     */
    private checkGestureConflict(newGesture: GestureType): boolean {
        if (!this.options.enableGestureConflictDetection) return true;

        // 如果没有活动手势，允许新手势
        if (!this.activeGesture || !this.isGestureInProgress) return true;

        // 检查新手势的优先级是否高于活动手势
        const newGesturePriority = this.gesturePriority.get(newGesture) ?? 0;
        const activeGesturePriority = this.gesturePriority.get(this.activeGesture) ?? 0;

        if (newGesturePriority > activeGesturePriority) {
            // 新手势优先级更高，取消活动手势
            return true;
        }

        // 优先级相同或更低，阻止新手势
        return false;
    }

    /**
     * 添加到历史记录
     */
    private addToHistory(event: GestureEvent): void {
        this.gestureHistory.push(event);

        // 限制历史记录长度
        if (this.gestureHistory.length > this.maxUndoSteps) {
            this.gestureHistory.shift();
        }

        // 清空重做栈
        this.redoStack = [];
    }

    /**
     * 撤销上一个手势
     */
    public undo(): GestureEvent | null {
        if (!this.options.enableUndoRedo) return null;

        if (this.gestureHistory.length > 0) {
            const lastGesture = this.gestureHistory.pop();
            if (lastGesture) {
                this.redoStack.push(lastGesture);
                return lastGesture;
            }
        }

        return null;
    }

    /**
     * 重做手势
     */
    public redo(): GestureEvent | null {
        if (!this.options.enableUndoRedo) return null;

        if (this.redoStack.length > 0) {
            const gesture = this.redoStack.pop();
            if (gesture) {
                this.gestureHistory.push(gesture);
                return gesture;
            }
        }

        return null;
    }

    /**
     * 获取历史记录
     */
    public getHistory(): GestureEvent[] {
        return [...this.gestureHistory];
    }

    /**
     * 清空历史记录
     */
    public clearHistory(): void {
        this.gestureHistory = [];
        this.redoStack = [];
    }

    /**
     * 获取活动手势
     */
    public getActiveGesture(): GestureType | null {
        return this.activeGesture;
    }

    /**
     * 设置手势优先级
     */
    public setGesturePriority(gesture: GestureType, priority: number): void {
        this.gesturePriority.set(gesture, priority);
    }

    /**
     * 获取手势优先级
     */
    public getGesturePriority(gesture: GestureType): number {
        return this.gesturePriority.get(gesture) ?? 0;
    }

    /**
     * 添加手势回调
     */
    public on(type: GestureType, callback: GestureCallback): void {
        if (!this.callbacks.has(type)) {
            this.callbacks.set(type, new Set());
        }
        this.callbacks.get(type)!.add(callback);
    }

    /**
     * 移除手势回调
     */
    public off(type: GestureType, callback: GestureCallback): void {
        const callbacks = this.callbacks.get(type);
        if (callbacks) {
            callbacks.delete(callback);
        }
    }

    /**
     * 启用手势类型
     */
    public enable(type: GestureType): void {
        switch (type) {
            case 'tap':
                this.options.enableTap = true;
                break;
            case 'doubleTap':
                this.options.enableDoubleTap = true;
                break;
            case 'longPress':
                this.options.enableLongPress = true;
                break;
            case 'swipe':
                this.options.enableSwipe = true;
                break;
            case 'pinch':
                this.options.enablePinch = true;
                break;
            case 'rotate':
                this.options.enableRotate = true;
                break;
            case 'tripleFingerPinch':
                this.options.enableTripleFingerPinch = true;
                break;
            case 'quickSwipe':
                this.options.enableQuickSwipe = true;
                break;
            case 'layerSwipe':
                this.options.enableLayerSwipe = true;
                break;
        }
    }

    /**
     * 禁用手势类型
     */
    public disable(type: GestureType): void {
        switch (type) {
            case 'tap':
                this.options.enableTap = false;
                break;
            case 'doubleTap':
                this.options.enableDoubleTap = false;
                break;
            case 'longPress':
                this.options.enableLongPress = false;
                break;
            case 'swipe':
                this.options.enableSwipe = false;
                break;
            case 'pinch':
                this.options.enablePinch = false;
                break;
            case 'rotate':
                this.options.enableRotate = false;
                break;
            case 'tripleFingerPinch':
                this.options.enableTripleFingerPinch = false;
                break;
            case 'quickSwipe':
                this.options.enableQuickSwipe = false;
                break;
            case 'layerSwipe':
                this.options.enableLayerSwipe = false;
                break;
        }
    }

    /**
     * 销毁管理器
     */
    public destroy(): void {
        this.unbind();
        this.clearLongPress();
        this.callbacks.clear();
        this.touches.clear();
        this.gestureHistory = [];
        this.undoStack = [];
        this.redoStack = [];
        this.gesturePriority.clear();
        this.activeGesture = null;
        this.isGestureInProgress = false;

        // 移除反馈元素
        if (this.feedbackElement && this.feedbackElement.parentNode) {
            this.feedbackElement.parentNode.removeChild(this.feedbackElement);
            this.feedbackElement = null;
        }

        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
    }
}

// 导出
export default TouchGestureManager;