/**
 * 结果过渡动画管理器
 * 提供图层切换、参数调整等的平滑过渡动画效果
 */

// 过渡类型
export type TransitionType = 'fade' | 'slide' | 'scale' | 'rotate' | 'flip';

// 过渡持续时间
export type TransitionDuration = 'fast' | 'normal' | 'slow';

// 缓动函数
export type EasingFunction = 'ease' | 'linear' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'bounce' | 'elastic';

// 图层信息
interface LayerInfo {
    id: string;
    name: string;
    type: 'prediction' | 'uncertainty' | 'overlay';
    visible: boolean;
    opacity: number;
    zIndex: number;
}

// 过渡配置
interface TransitionConfig {
    type: TransitionType;
    duration: TransitionDuration;
    easing: EasingFunction;
    delay: number;
}

// 动画状态
interface AnimationState {
    isAnimating: boolean;
    progress: number;
    currentTransition: string | null;
}

export class TransitionAnimationManager {
    private container: HTMLElement;
    private layers: Map<string, LayerInfo> = new Map();
    private animationState: AnimationState;
    private animationId: number | null = null;
    private transitionQueue: Array<{
        layerId: string;
        config: TransitionConfig;
        from: any;
        to: any;
        onComplete?: () => void;
    }> = [];
    private previewPanel: HTMLElement | null = null;

    constructor(container: HTMLElement | string) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)!
            : container;
        this.animationState = {
            isAnimating: false,
            progress: 0,
            currentTransition: null
        };
        this.init();
    }

    private init(): void {
        this.createPreviewPanel();
    }

    private createPreviewPanel(): void {
        this.previewPanel = document.createElement('div');
        this.previewPanel.className = 'transition-preview-panel';
        this.previewPanel.style.display = 'none';
        this.previewPanel.innerHTML = `
            <div class="preview-content">
                <h3 class="preview-title">动画效果预览</h3>
                <div class="preview-options">
                    <div class="preview-option-group">
                        <label class="preview-label">过渡类型：</label>
                        <div class="preview-buttons">
                            <button class="btn btn-small preview-btn active" data-type="fade">淡入淡出</button>
                            <button class="btn btn-small preview-btn" data-type="slide">滑动</button>
                            <button class="btn btn-small preview-btn" data-type="scale">缩放</button>
                            <button class="btn btn-small preview-btn" data-type="rotate">旋转</button>
                            <button class="btn btn-small preview-btn" data-type="flip">翻转</button>
                        </div>
                    </div>
                    <div class="preview-option-group">
                        <label class="preview-label">持续时间：</label>
                        <div class="preview-buttons">
                            <button class="btn btn-small duration-btn" data-duration="fast">快</button>
                            <button class="btn btn-small duration-btn active" data-duration="normal">正常</button>
                            <button class="btn btn-small duration-btn" data-duration="slow">慢</button>
                        </div>
                    </div>
                    <div class="preview-option-group">
                        <label class="preview-label">缓动函数：</label>
                        <div class="preview-buttons">
                            <button class="btn btn-small easing-btn active" data-easing="ease">Ease</button>
                            <button class="btn btn-small easing-btn" data-easing="linear">Linear</button>
                            <button class="btn btn-small easing-btn" data-easing="ease-in">Ease In</button>
                            <button class="btn btn-small easing-btn" data-easing="ease-out">Ease Out</button>
                            <button class="btn btn-small easing-btn" data-easing="ease-in-out">Ease In Out</button>
                            <button class="btn btn-small easing-btn" data-easing="bounce">Bounce</button>
                            <button class="btn btn-small easing-btn" data-easing="elastic">Elastic</button>
                        </div>
                    </div>
                </div>
                <div class="preview-canvas">
                    <div class="preview-element" id="preview-element"></div>
                </div>
                <div class="preview-actions">
                    <button class="btn btn-primary preview-play-btn">播放预览</button>
                    <button class="btn preview-close-btn">关闭</button>
                </div>
            </div>
        `;
        this.container.appendChild(this.previewPanel);
        this.bindPreviewEvents();
    }

    private bindPreviewEvents(): void {
        if (!this.previewPanel) return;

        const previewBtns = this.previewPanel.querySelectorAll('.preview-btn');
        previewBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                previewBtns.forEach(b => b.classList.remove('active'));
                (e.target as HTMLElement).classList.add('active');
            });
        });

        const durationBtns = this.previewPanel.querySelectorAll('.duration-btn');
        durationBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                durationBtns.forEach(b => b.classList.remove('active'));
                (e.target as HTMLElement).classList.add('active');
            });
        });

        const easingBtns = this.previewPanel.querySelectorAll('.easing-btn');
        easingBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                easingBtns.forEach(b => b.classList.remove('active'));
                (e.target as HTMLElement).classList.add('active');
            });
        });

        const playBtn = this.previewPanel.querySelector('.preview-play-btn');
        if (playBtn) {
            playBtn.addEventListener('click', () => this.playPreview());
        }

        const closeBtn = this.previewPanel.querySelector('.preview-close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hidePreview());
        }
    }

    public showPreview(): void {
        if (this.previewPanel) {
            this.previewPanel.style.display = 'block';
        }
    }

    public hidePreview(): void {
        if (this.previewPanel) {
            this.previewPanel.style.display = 'none';
        }
    }

    private playPreview(): void {
        if (!this.previewPanel) return;

        const type = (this.previewPanel.querySelector('.preview-btn.active') as HTMLElement)?.dataset.type as TransitionType || 'fade';
        const duration = (this.previewPanel.querySelector('.duration-btn.active') as HTMLElement)?.dataset.duration as TransitionDuration || 'normal';
        const easing = (this.previewPanel.querySelector('.easing-btn.active') as HTMLElement)?.dataset.easing as EasingFunction || 'ease';

        const element = this.previewPanel.querySelector('#preview-element') as HTMLElement;
        this.animateElement(element, type, duration, easing);
    }

    private animateElement(
        element: HTMLElement,
        type: TransitionType,
        duration: TransitionDuration,
        easing: EasingFunction
    ): void {
        const durationMs = this.getDurationMs(duration);
        const easingFunction = this.getEasingFunction(easing);

        // 重置元素状态
        element.style.transition = 'none';
        element.style.opacity = '1';
        element.style.transform = 'none';

        // 设置初始状态
        this.setInitialState(element, type);

        // 强制重排
        element.offsetHeight;

        // 应用过渡
        element.style.transition = `all ${durationMs}ms ${easingFunction}`;
        this.setFinalState(element, type);

        // 动画结束后重置
        setTimeout(() => {
            element.style.transition = 'none';
            element.style.opacity = '1';
            element.style.transform = 'none';
        }, durationMs);
    }

    private setInitialState(element: HTMLElement, type: TransitionType): void {
        switch (type) {
            case 'fade':
                element.style.opacity = '0';
                break;
            case 'slide':
                element.style.opacity = '0';
                element.style.transform = 'translateX(-20px)';
                break;
            case 'scale':
                element.style.opacity = '0';
                element.style.transform = 'scale(0.8)';
                break;
            case 'rotate':
                element.style.opacity = '0';
                element.style.transform = 'rotate(-10deg) scale(0.9)';
                break;
            case 'flip':
                element.style.transform = 'rotateY(90deg)';
                break;
        }
    }

    private setFinalState(element: HTMLElement, type: TransitionType): void {
        switch (type) {
            case 'fade':
                element.style.opacity = '1';
                break;
            case 'slide':
                element.style.opacity = '1';
                element.style.transform = 'translateX(0)';
                break;
            case 'scale':
                element.style.opacity = '1';
                element.style.transform = 'scale(1)';
                break;
            case 'rotate':
                element.style.opacity = '1';
                element.style.transform = 'rotate(0deg) scale(1)';
                break;
            case 'flip':
                element.style.transform = 'rotateY(0deg)';
                break;
        }
    }

    private getDurationMs(duration: TransitionDuration): number {
        const durationMap: Record<TransitionDuration, number> = {
            'fast': 150,
            'normal': 300,
            'slow': 500
        };
        return durationMap[duration];
    }

    private getEasingFunction(easing: EasingFunction): string {
        const easingMap: Record<EasingFunction, string> = {
            'ease': 'cubic-bezier(0.4, 0.0, 0.2, 1)',
            'linear': 'linear',
            'ease-in': 'cubic-bezier(0.4, 0.0, 1, 1)',
            'ease-out': 'cubic-bezier(0.0, 0.0, 0.2, 1)',
            'ease-in-out': 'cubic-bezier(0.4, 0.0, 0.2, 1)',
            'bounce': 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
            'elastic': 'cubic-bezier(0.175, 0.885, 0.32, 1.275)'
        };
        return easingMap[easing];
    }

    // 图层管理
    public addLayer(layer: LayerInfo): void {
        this.layers.set(layer.id, layer);
    }

    public removeLayer(layerId: string): void {
        this.layers.delete(layerId);
    }

    public getLayer(layerId: string): LayerInfo | undefined {
        return this.layers.get(layerId);
    }

    // 图层切换动画
    public switchLayer(
        fromLayerId: string,
        toLayerId: string,
        config: Partial<TransitionConfig> = {},
        onComplete?: () => void
    ): void {
        const fromLayer = this.layers.get(fromLayerId);
        const toLayer = this.layers.get(toLayerId);

        if (!fromLayer || !toLayer) {
            console.warn('图层不存在');
            return;
        }

        const finalConfig: TransitionConfig = {
            type: config.type || 'fade',
            duration: config.duration || 'normal',
            easing: config.easing || 'ease',
            delay: config.delay || 0
        };

        this.transitionQueue.push({
            layerId: toLayerId,
            config: finalConfig,
            from: { visible: fromLayer.visible, opacity: fromLayer.opacity },
            to: { visible: true, opacity: 1 },
            onComplete
        });

        this.processQueue();
    }

    // 参数调整动画
    public animateParameterChange(
        layerId: string,
        from: any,
        to: any,
        config: Partial<TransitionConfig> = {},
        onComplete?: () => void
    ): void {
        const finalConfig: TransitionConfig = {
            type: config.type || 'fade',
            duration: config.duration || 'normal',
            easing: config.easing || 'ease',
            delay: config.delay || 0
        };

        this.transitionQueue.push({
            layerId,
            config: finalConfig,
            from,
            to,
            onComplete
        });

        this.processQueue();
    }

    private processQueue(): void {
        if (this.animationState.isAnimating || this.transitionQueue.length === 0) {
            return;
        }

        const transition = this.transitionQueue.shift();
        if (!transition) return;

        this.executeTransition(transition);
    }

    private executeTransition(transition: {
        layerId: string;
        config: TransitionConfig;
        from: any;
        to: any;
        onComplete?: () => void;
    }): void {
        this.animationState.isAnimating = true;
        this.animationState.currentTransition = transition.layerId;
        this.animationState.progress = 0;

        const layer = this.layers.get(transition.layerId);
        if (!layer) {
            this.finishTransition(transition);
            return;
        }

        const durationMs = this.getDurationMs(transition.config.duration);
        const easingFunction = this.getEasingFunction(transition.config.easing);

        // 延迟执行
        setTimeout(() => {
            const startTime = performance.now();

            const animate = (currentTime: number) => {
                const elapsed = currentTime - startTime;
                this.animationState.progress = Math.min(elapsed / durationMs, 1);

                const easedProgress = this.applyEasing(this.animationState.progress, transition.config.easing);

                // 应用过渡效果
                this.applyTransition(layer, transition, easedProgress);

                if (this.animationState.progress < 1) {
                    this.animationId = requestAnimationFrame(animate);
                } else {
                    this.finishTransition(transition);
                }
            };

            this.animationId = requestAnimationFrame(animate);
        }, transition.config.delay);
    }

    private applyEasing(progress: number, easing: EasingFunction): number {
        switch (easing) {
            case 'linear':
                return progress;
            case 'ease':
            case 'ease-in-out':
                return progress < 0.5
                    ? 2 * progress * progress
                    : 1 - Math.pow(-2 * progress + 2, 2) / 2;
            case 'ease-in':
                return progress * progress;
            case 'ease-out':
                return 1 - Math.pow(1 - progress, 2);
            case 'bounce':
                if (progress < 1 / 2.75) {
                    return 7.5625 * progress * progress;
                } else if (progress < 2 / 2.75) {
                    return 7.5625 * (progress -= 1.5 / 2.75) * progress + 0.75;
                } else if (progress < 2.5 / 2.75) {
                    return 7.5625 * (progress -= 2.25 / 2.75) * progress + 0.9375;
                } else {
                    return 7.5625 * (progress -= 2.625 / 2.75) * progress + 0.984375;
                }
            case 'elastic':
                if (progress === 0 || progress === 1) return progress;
                return Math.pow(2, -10 * progress) * Math.sin((progress - 0.1) * 5 * Math.PI) + 1;
            default:
                return progress;
        }
    }

    private applyTransition(
        layer: LayerInfo,
        transition: { from: any; to: any; config: TransitionConfig },
        progress: number
    ): void {
        const { from, to, config } = transition;

        switch (config.type) {
            case 'fade':
                layer.opacity = from.opacity + (to.opacity - from.opacity) * progress;
                layer.visible = progress > 0;
                break;
            case 'slide':
                layer.opacity = progress;
                layer.visible = progress > 0;
                break;
            case 'scale':
                layer.opacity = progress;
                layer.visible = progress > 0;
                break;
            case 'rotate':
                layer.opacity = progress;
                layer.visible = progress > 0;
                break;
            case 'flip':
                layer.opacity = progress;
                layer.visible = progress > 0;
                break;
        }
    }

    private finishTransition(transition: { onComplete?: () => void }): void {
        this.animationState.isAnimating = false;
        this.animationState.currentTransition = null;
        this.animationState.progress = 0;

        if (transition.onComplete) {
            transition.onComplete();
        }

        // 处理队列中的下一个过渡
        this.processQueue();
    }

    // 批量图层切换
    public switchLayersSequentially(
        layerIds: string[],
        config: Partial<TransitionConfig> = {},
        onComplete?: () => void
    ): void {
        let completedCount = 0;

        layerIds.forEach((layerId, index) => {
            const delay = index * 100; // 每个图层延迟100ms

            this.switchLayer(
                layerIds[index - 1] || '',
                layerId,
                { ...config, delay },
                () => {
                    completedCount++;
                    if (completedCount === layerIds.length && onComplete) {
                        onComplete();
                    }
                }
            );
        });
    }

    // 取消所有动画
    public cancelAllAnimations(): void {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }

        this.transitionQueue = [];
        this.animationState.isAnimating = false;
        this.animationState.currentTransition = null;
        this.animationState.progress = 0;
    }

    // 获取当前动画状态
    public getAnimationState(): AnimationState {
        return { ...this.animationState };
    }
}