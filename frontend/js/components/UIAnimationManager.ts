/**
 * UI交互动画管理器
 * 提供按钮、面板、加载器、通知等UI元素的交互动画效果
 */

// 动画触发类型
export type AnimationTrigger = 'hover' | 'click' | 'focus' | 'load' | 'enter' | 'exit';

// 动画效果类型
export type AnimationEffect = 'scale' | 'rotate' | 'translate' | 'opacity' | 'color' | 'shadow';

// 动画配置
interface AnimationConfig {
    trigger: AnimationTrigger;
    effect: AnimationEffect;
    duration: number;
    delay: number;
    easing: string;
    properties: Record<string, any>;
}

// 动画状态
interface AnimationState {
    isActive: boolean;
    progress: number;
}

export class UIAnimationManager {
    private container: HTMLElement;
    private animations: Map<string, AnimationConfig> = new Map();
    private animationStates: Map<string, AnimationState> = new Map();
    private observers: Map<string, IntersectionObserver> = new Map();
    private isEnabled: boolean = true;

    constructor(container: HTMLElement | string) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)!
            : container;
        this.init();
    }

    private init(): void {
        this.initializeObservers();
    }

    // 动画开关
    public setEnabled(enabled: boolean): void {
        this.isEnabled = enabled;
        if (!enabled) {
            this.cancelAllAnimations();
        }
    }

    public getEnabled(): boolean {
        return this.isEnabled;
    }

    // 注册动画
    public registerAnimation(elementId: string, config: AnimationConfig): void {
        this.animations.set(elementId, config);
        this.animationStates.set(elementId, {
            isActive: false,
            progress: 0
        });

        const element = document.getElementById(elementId);
        if (element) {
            this.bindAnimationEvents(element, config);
        }
    }

    // 注销动画
    public unregisterAnimation(elementId: string): void {
        this.animations.delete(elementId);
        this.animationStates.delete(elementId);

        const observer = this.observers.get(elementId);
        if (observer) {
            observer.disconnect();
            this.observers.delete(elementId);
        }
    }

    // 绑定动画事件
    private bindAnimationEvents(element: HTMLElement, config: AnimationConfig): void {
        switch (config.trigger) {
            case 'hover':
                element.addEventListener('mouseenter', () => this.triggerAnimation(element, config, true));
                element.addEventListener('mouseleave', () => this.triggerAnimation(element, config, false));
                break;
            case 'click':
                element.addEventListener('click', () => this.triggerAnimation(element, config, true));
                break;
            case 'focus':
                element.addEventListener('focus', () => this.triggerAnimation(element, config, true));
                element.addEventListener('blur', () => this.triggerAnimation(element, config, false));
                break;
            case 'load':
                this.triggerAnimation(element, config, true);
                break;
            case 'enter':
            case 'exit':
                this.setupIntersectionObserver(element, config);
                break;
        }
    }

    // 触发动画
    private triggerAnimation(element: HTMLElement, config: AnimationConfig, activate: boolean): void {
        if (!this.isEnabled) return;

        const elementId = element.id;
        const state = this.animationStates.get(elementId);

        if (!state) return;

        state.isActive = activate;
        this.applyAnimation(element, config, activate ? 1 : 0);
    }

    // 应用动画
    private applyAnimation(element: HTMLElement, config: AnimationConfig, progress: number): void {
        const { effect, duration, easing, properties } = config;

        // 设置过渡属性
        element.style.transition = this.getTransitionString(config);

        // 应用效果
        switch (effect) {
            case 'scale':
                this.applyScaleEffect(element, properties, progress);
                break;
            case 'rotate':
                this.applyRotateEffect(element, properties, progress);
                break;
            case 'translate':
                this.applyTranslateEffect(element, properties, progress);
                break;
            case 'opacity':
                this.applyOpacityEffect(element, properties, progress);
                break;
            case 'color':
                this.applyColorEffect(element, properties, progress);
                break;
            case 'shadow':
                this.applyShadowEffect(element, properties, progress);
                break;
        }
    }

    // 缩放效果
    private applyScaleEffect(element: HTMLElement, properties: Record<string, any>, progress: number): void {
        const from = properties.from || 1;
        const to = properties.to || 1.05;
        const scale = from + (to - from) * progress;

        element.style.transform = `scale(${scale})`;
        this.enableHardwareAcceleration(element);
    }

    // 旋转效果
    private applyRotateEffect(element: HTMLElement, properties: Record<string, any>, progress: number): void {
        const from = properties.from || 0;
        const to = properties.to || 180;
        const rotate = from + (to - from) * progress;

        element.style.transform = `rotate(${rotate}deg)`;
        this.enableHardwareAcceleration(element);
    }

    // 平移效果
    private applyTranslateEffect(element: HTMLElement, properties: Record<string, any>, progress: number): void {
        const fromX = properties.fromX || 0;
        const fromY = properties.fromY || 0;
        const toX = properties.toX || 0;
        const toY = properties.toY || 0;

        const x = fromX + (toX - fromX) * progress;
        const y = fromY + (toY - fromY) * progress;

        element.style.transform = `translate(${x}px, ${y}px)`;
        this.enableHardwareAcceleration(element);
    }

    // 透明度效果
    private applyOpacityEffect(element: HTMLElement, properties: Record<string, any>, progress: number): void {
        const from = properties.from || 1;
        const to = properties.to || 0.8;
        const opacity = from + (to - from) * progress;

        element.style.opacity = opacity.toString();
    }

    // 颜色效果
    private applyColorEffect(element: HTMLElement, properties: Record<string, any>, progress: number): void {
        const from = properties.from || '#000000';
        const to = properties.to || '#ffffff';
        const color = this.interpolateColor(from, to, progress);

        element.style.color = color;
    }

    // 阴影效果
    private applyShadowEffect(element: HTMLElement, properties: Record<string, any>, progress: number): void {
        const from = properties.from || 'none';
        const to = properties.to || '0 4px 12px rgba(0, 0, 0, 0.15)';
        const shadow = progress > 0.5 ? to : from;

        element.style.boxShadow = shadow;
    }

    // 颜色插值
    private interpolateColor(from: string, to: string, progress: number): string {
        const fromRGB = this.hexToRGB(from);
        const toRGB = this.hexToRGB(to);

        if (!fromRGB || !toRGB) return to;

        const r = Math.round(fromRGB.r + (toRGB.r - fromRGB.r) * progress);
        const g = Math.round(fromRGB.g + (toRGB.g - fromRGB.g) * progress);
        const b = Math.round(fromRGB.b + (toRGB.b - fromRGB.b) * progress);

        return `rgb(${r}, ${g}, ${b})`;
    }

    // 十六进制转RGB
    private hexToRGB(hex: string): { r: number; g: number; b: number } | null {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : null;
    }

    // 获取过渡字符串
    private getTransitionString(config: AnimationConfig): string {
        const { effect, duration, easing } = config;

        const properties: string[] = [];
        switch (effect) {
            case 'scale':
            case 'rotate':
            case 'translate':
                properties.push('transform');
                break;
            case 'opacity':
                properties.push('opacity');
                break;
            case 'color':
                properties.push('color');
                break;
            case 'shadow':
                properties.push('box-shadow');
                break;
        }

        return properties.map(prop => `${prop} ${duration}ms ${easing}`).join(', ');
    }

    // 启用硬件加速
    private enableHardwareAcceleration(element: HTMLElement): void {
        element.style.transform = element.style.transform + ' translateZ(0)';
        element.style.backfaceVisibility = 'hidden';
        element.style.perspective = '1000px';
    }

    // 设置交叉观察器
    private setupIntersectionObserver(element: HTMLElement, config: AnimationConfig): void {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        this.triggerAnimation(element, config, true);
                    } else if (config.trigger === 'exit') {
                        this.triggerAnimation(element, config, false);
                    }
                });
            },
            {
                threshold: 0.1
            }
        );

        observer.observe(element);
        this.observers.set(element.id, observer);
    }

    // 初始化观察器
    private initializeObservers(): void {
        // 为具有滚动进入动画的元素设置观察器
        const scrollElements = this.container.querySelectorAll('[data-animation="scroll-enter"]');
        scrollElements.forEach(element => {
            this.registerAnimation(element.id, {
                trigger: 'enter',
                effect: 'translate',
                duration: 300,
                delay: 0,
                easing: 'cubic-bezier(0.4, 0.0, 0.2, 1)',
                properties: {
                    fromY: 20,
                    fromOpacity: 0,
                    toY: 0,
                    toOpacity: 1
                }
            });
        });
    }

    // 取消所有动画
    private cancelAllAnimations(): void {
        this.animationStates.forEach((state, elementId) => {
            state.isActive = false;
            const element = document.getElementById(elementId);
            if (element) {
                element.style.transition = 'none';
            }
        });
    }

    // 按钮交互动画
    public setupButtonAnimation(buttonId: string): void {
        this.registerAnimation(buttonId, {
            trigger: 'hover',
            effect: 'scale',
            duration: 200,
            delay: 0,
            easing: 'cubic-bezier(0.4, 0.0, 0.2, 1)',
            properties: {
                from: 1,
                to: 1.02
            }
        });

        this.registerAnimation(buttonId, {
            trigger: 'click',
            effect: 'scale',
            duration: 100,
            delay: 0,
            easing: 'cubic-bezier(0.4, 0.0, 0.2, 1)',
            properties: {
                from: 1,
                to: 0.98
            }
        });
    }

    // 面板展开/收起动画
    public setupPanelAnimation(panelId: string, duration: number = 300): void {
        const panel = document.getElementById(panelId);
        if (!panel) return;

        // 初始状态
        panel.style.overflow = 'hidden';
        panel.style.transition = `max-height ${duration}ms cubic-bezier(0.4, 0.0, 0.2, 1), opacity ${duration}ms cubic-bezier(0.4, 0.0, 0.2, 1)`;

        this.registerAnimation(panelId, {
            trigger: 'click',
            effect: 'translate',
            duration,
            delay: 0,
            easing: 'cubic-bezier(0.4, 0.0, 0.2, 1)',
            properties: {
                fromY: -10,
                fromOpacity: 0,
                toY: 0,
                toOpacity: 1
            }
        });
    }

    // 展开面板
    public expandPanel(panelId: string): void {
        const panel = document.getElementById(panelId);
        if (!panel) return;

        panel.style.maxHeight = panel.scrollHeight + 'px';
        panel.style.opacity = '1';
    }

    // 收起面板
    public collapsePanel(panelId: string): void {
        const panel = document.getElementById(panelId);
        if (!panel) return;

        panel.style.maxHeight = '0px';
        panel.style.opacity = '0';
    }

    // 加载动画
    public createLoadingIndicator(containerId: string, options: {
        type?: 'spinner' | 'pulse' | 'dots';
        size?: number;
        color?: string;
    } = {}): HTMLElement {
        const container = document.getElementById(containerId);
        if (!container) {
            throw new Error(`容器 ${containerId} 不存在`);
        }

        const { type = 'spinner', size = 40, color = '#0071e3' } = options;

        const loader = document.createElement('div');
        loader.className = 'ui-loading-indicator';
        loader.id = `${containerId}-loader`;

        switch (type) {
            case 'spinner':
                loader.innerHTML = `
                    <div class="spinner" style="
                        width: ${size}px;
                        height: ${size}px;
                        border: 3px solid ${color}20;
                        border-top-color: ${color};
                        border-radius: 50%;
                        animation: spin 1s linear infinite;
                    "></div>
                `;
                break;
            case 'pulse':
                loader.innerHTML = `
                    <div class="pulse" style="
                        width: ${size}px;
                        height: ${size}px;
                        background: ${color};
                        border-radius: 50%;
                        animation: pulse 1.5s ease-in-out infinite;
                    "></div>
                `;
                break;
            case 'dots':
                loader.innerHTML = `
                    <div class="dots" style="display: flex; gap: ${size / 4}px;">
                        <div class="dot" style="
                            width: ${size / 3}px;
                            height: ${size / 3}px;
                            background: ${color};
                            border-radius: 50%;
                            animation: dot-bounce 1.4s ease-in-out infinite;
                        "></div>
                        <div class="dot" style="
                            width: ${size / 3}px;
                            height: ${size / 3}px;
                            background: ${color};
                            border-radius: 50%;
                            animation: dot-bounce 1.4s ease-in-out infinite 0.2s;
                        "></div>
                        <div class="dot" style="
                            width: ${size / 3}px;
                            height: ${size / 3}px;
                            background: ${color};
                            border-radius: 50%;
                            animation: dot-bounce 1.4s ease-in-out infinite 0.4s;
                        "></div>
                    </div>
                `;
                break;
        }

        container.appendChild(loader);
        return loader;
    }

    // 移除加载指示器
    public removeLoadingIndicator(containerId: string): void {
        const loader = document.getElementById(`${containerId}-loader`);
        if (loader) {
            loader.remove();
        }
    }

    // 通知动画
    public showNotification(
        message: string,
        type: 'info' | 'success' | 'warning' | 'error' = 'info',
        duration: number = 3000
    ): HTMLElement {
        const notification = document.createElement('div');
        notification.className = `ui-notification ui-notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-message">${message}</span>
            </div>
        `;

        // 添加动画
        notification.style.animation = 'notificationSlideIn 300ms cubic-bezier(0.4, 0.0, 0.2, 1)';

        this.container.appendChild(notification);

        // 自动移除
        setTimeout(() => {
            this.hideNotification(notification);
        }, duration);

        return notification;
    }

    // 隐藏通知
    private hideNotification(notification: HTMLElement): void {
        notification.style.animation = 'notificationSlideOut 300ms cubic-bezier(0.4, 0.0, 0.2, 1)';

        setTimeout(() => {
            notification.remove();
        }, 300);
    }

    // 创建进度条
    public createProgressBar(containerId: string, initialProgress: number = 0): HTMLElement {
        const container = document.getElementById(containerId);
        if (!container) {
            throw new Error(`容器 ${containerId} 不存在`);
        }

        const progressBar = document.createElement('div');
        progressBar.className = 'ui-progress-bar';
        progressBar.id = `${containerId}-progress-bar`;
        progressBar.innerHTML = `
            <div class="progress-track">
                <div class="progress-fill" style="width: ${initialProgress}%"></div>
            </div>
        `;

        container.appendChild(progressBar);
        return progressBar;
    }

    // 更新进度条
    public updateProgressBar(containerId: string, progress: number): void {
        const progressBar = document.getElementById(`${containerId}-progress-bar`);
        if (!progressBar) return;

        const fill = progressBar.querySelector('.progress-fill') as HTMLElement;
        if (fill) {
            fill.style.transition = 'width 300ms cubic-bezier(0.4, 0.0, 0.2, 1)';
            fill.style.width = `${Math.min(100, Math.max(0, progress))}%`;
        }
    }

    // 添加CSS动画关键帧
    public injectAnimationStyles(): void {
        const style = document.createElement('style');
        style.textContent = `
            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }

            @keyframes pulse {
                0%, 100% { transform: scale(1); opacity: 1; }
                50% { transform: scale(0.8); opacity: 0.5; }
            }

            @keyframes dot-bounce {
                0%, 80%, 100% { transform: scale(0); }
                40% { transform: scale(1); }
            }

            @keyframes notificationSlideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }

            @keyframes notificationSlideOut {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(100%);
                    opacity: 0;
                }
            }

            .ui-notification {
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 16px 24px;
                border-radius: 8px;
                background: white;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                z-index: 10000;
                max-width: 400px;
            }

            .ui-notification-info {
                border-left: 4px solid #0071e3;
            }

            .ui-notification-success {
                border-left: 4px solid #34c759;
            }

            .ui-notification-warning {
                border-left: 4px solid #f59e0b;
            }

            .ui-notification-error {
                border-left: 4px solid #ef4444;
            }

            .ui-progress-bar {
                width: 100%;
                height: 8px;
                background: rgba(0, 0, 0, 0.1);
                border-radius: 4px;
                overflow: hidden;
            }

            .progress-track {
                width: 100%;
                height: 100%;
            }

            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #0071e3, #0a84ff);
                border-radius: 4px;
                transition: width 300ms cubic-bezier(0.4, 0.0, 0.2, 1);
            }
        `;

        document.head.appendChild(style);
    }
}