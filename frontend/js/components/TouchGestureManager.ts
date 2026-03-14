/**
 * 触摸手势管理器
 * 实现地图触摸交互（拖拽、缩放、长按）和手势事件处理
 */

import './config/主题变量';

export type GestureType = 'tap' | 'doubleTap' | 'longPress' | 'swipe' | 'pinch' | 'rotate';

export interface GestureEvent {
    type: GestureType;
    center: { x: number; y: number };
    distance?: number;
    angle?: number;
    direction?: 'up' | 'down' | 'left' | 'right';
    delta?: { x: number; y: number };
    scale?: number;
    rotation?: number;
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
    longPressDelay?: number;
    doubleTapDelay?: number;
    swipeThreshold?: number;
    enableHaptic?: boolean;
    enableAudioFeedback?: boolean;
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

    // 音频上下文
    private audioContext: AudioContext | null = null;

    constructor(options: TouchGestureManagerOptions = {}) {
        this.options = {
            enableTap: options.enableTap ?? true,
            enableDoubleTap: options.enableDoubleTap ?? true,
            enableLongPress: options.enableLongPress ?? true,
            enableSwipe: options.enableSwipe ?? true,
            enablePinch: options.enablePinch ?? true,
            enableRotate: options.enableRotate ?? true,
            longPressDelay: options.longPressDelay ?? 500,
            doubleTapDelay: options.doubleTapDelay ?? 300,
            swipeThreshold: options.swipeThreshold ?? 50,
            enableHaptic: options.enableHaptic ?? true,
            enableAudioFeedback: options.enableAudioFeedback ?? false,
        };
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
     * 触觉反馈
     */
    private hapticFeedback(pattern: number | number[] = 10): void {
        if (!this.options.enableHaptic) return;

        if ('vibrate' in navigator) {
            navigator.vibrate(pattern);
        }
    }

    /**
     * 触摸反馈（高亮、震动、声音）
     */
    private touchFeedback(type: 'tap' | 'longPress' | 'swipe' | 'pinch'): void {
        // 触觉反馈
        switch (type) {
            case 'tap':
                this.hapticFeedback(10);
                break;
            case 'longPress':
                this.hapticFeedback([20, 10, 20]);
                break;
            case 'swipe':
                this.hapticFeedback(15);
                break;
            case 'pinch':
                this.hapticFeedback(5);
                break;
        }

        // 音频反馈
        if (type === 'tap') {
            this.playTapSound();
        }
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

        // 单指操作
        if (e.touches.length === 1) {
            const touch = e.touches[0];
            this.startTime = Date.now();
            this.startX = touch.clientX;
            this.startY = touch.clientY;

            // 设置长按定时器
            if (this.options.enableLongPress) {
                this.longPressTimer = window.setTimeout(() => {
                    this.triggerGesture('longPress', {
                        type: 'longPress',
                        center: { x: touch.clientX, y: touch.clientY },
                    });
                    this.touchFeedback('longPress');
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
            if (this.options.enablePinch && currentDistance > 0) {
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
            if (this.options.enableRotate) {
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

            // 检测点击
            if (distance < 10 && duration < 300 && this.options.enableTap) {
                const now = Date.now();
                const timeSinceLastTap = now - this.lastTapTime;

                // 双击
                if (timeSinceLastTap < this.options.doubleTapDelay && this.options.enableDoubleTap) {
                    this.triggerGesture('doubleTap', {
                        type: 'doubleTap',
                        center: { x: touch.clientX, y: touch.clientY },
                    });
                    this.touchFeedback('tap');
                }
                // 单击
                else {
                    this.triggerGesture('tap', {
                        type: 'tap',
                        center: { x: touch.clientX, y: touch.clientY },
                    });
                    this.touchFeedback('tap');
                }

                this.lastTapTime = now;
            }
            // 检测滑动
            else if (distance >= this.options.swipeThreshold && this.options.enableSwipe) {
                const direction = this.getSwipeDirection(deltaX, deltaY);

                this.triggerGesture('swipe', {
                    type: 'swipe',
                    center: { x: touch.clientX, y: touch.clientY },
                    direction,
                    delta: { x: deltaX, y: deltaY },
                });
                this.touchFeedback('swipe');
            }
        }
    };

    /**
     * 处理触摸取消
     */
    private handleTouchCancel = (): void => {
        this.clearLongPress();
        this.touches.clear();
    };

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

        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
    }
}

// 导出
export default TouchGestureManager;