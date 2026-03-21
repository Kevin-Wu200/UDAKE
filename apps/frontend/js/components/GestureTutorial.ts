/**
 * 手势教程和引导系统
 * 提供交互式手势教程和引导功能
 */

export interface GestureTutorialStep {
    id: string;
    title: string;
    description: string;
    gestureType: string;
    icon: string;
    animation?: string;
    priority: number;
}

export interface GestureTutorialOptions {
    autoShow?: boolean;
    dismissible?: boolean;
    showOnFirstLaunch?: boolean;
    showOnDemand?: boolean;
    storageKey?: string;
}

const defaultTutorialSteps: GestureTutorialStep[] = [
    {
        id: 'tap',
        title: '点击',
        description: '点击地图上的任意位置进行选择或标记',
        gestureType: 'tap',
        icon: '👆',
        animation: 'tap',
        priority: 1,
    },
    {
        id: 'doubleTap',
        title: '双击',
        description: '快速双击地图区域进行放大或确认操作',
        gestureType: 'doubleTap',
        icon: '👆👆',
        animation: 'doubleTap',
        priority: 2,
    },
    {
        id: 'longPress',
        title: '长按',
        description: '长按地图位置添加采样点或查看详细信息',
        gestureType: 'longPress',
        icon: '👇',
        animation: 'longPress',
        priority: 3,
    },
    {
        id: 'pinch',
        title: '双指缩放',
        description: '使用双指捏合或分开来缩放地图',
        gestureType: 'pinch',
        icon: '👌',
        animation: 'pinch',
        priority: 4,
    },
    {
        id: 'rotate',
        title: '双指旋转',
        description: '使用双指旋转来调整地图方向',
        gestureType: 'rotate',
        icon: '🔄',
        animation: 'rotate',
        priority: 5,
    },
    {
        id: 'tripleFingerPinch',
        title: '三指缩放',
        description: '使用三指捏合进行更大范围的地图缩放',
        gestureType: 'tripleFingerPinch',
        icon: '✌️👇',
        animation: 'tripleFingerPinch',
        priority: 6,
    },
    {
        id: 'swipe',
        title: '滑动',
        description: '单指滑动来平移地图',
        gestureType: 'swipe',
        icon: '👉',
        animation: 'swipe',
        priority: 7,
    },
    {
        id: 'quickSwipe',
        title: '快速滑动',
        description: '快速滑动切换到不同视图',
        gestureType: 'quickSwipe',
        icon: '💨',
        animation: 'quickSwipe',
        priority: 8,
    },
    {
        id: 'layerSwipe',
        title: '图层切换',
        description: '水平滑动切换不同的图层',
        gestureType: 'layerSwipe',
        icon: '↔️',
        animation: 'layerSwipe',
        priority: 9,
    },
];

class GestureTutorial {
    private options: Required<GestureTutorialOptions>;
    private container: HTMLElement | null = null;
    private currentStepIndex: number = 0;
    private isVisible: boolean = false;
    private steps: GestureTutorialStep[] = [];
    private completedSteps: Set<string> = new Set();

    constructor(options: GestureTutorialOptions = {}) {
        this.options = {
            autoShow: options.autoShow ?? true,
            dismissible: options.dismissible ?? true,
            showOnFirstLaunch: options.showOnFirstLaunch ?? true,
            showOnDemand: options.showOnDemand ?? true,
            storageKey: options.storageKey ?? 'gesture_tutorial_completed',
        };

        this.steps = [...defaultTutorialSteps];
        this.loadCompletedSteps();
    }

    /**
     * 初始化教程
     */
    public init(container: HTMLElement): void {
        this.container = container;

        if (this.options.autoShow && this.shouldShowTutorial()) {
            this.show();
        }
    }

    /**
     * 显示教程
     */
    public show(stepIndex: number = 0): void {
        if (!this.container) return;

        this.currentStepIndex = stepIndex;
        this.isVisible = true;
        this.render();
    }

    /**
     * 隐藏教程
     */
    public hide(): void {
        if (this.container) {
            const tutorialOverlay = this.container.querySelector('.gesture-tutorial-overlay');
            if (tutorialOverlay) {
                tutorialOverlay.remove();
            }
        }

        this.isVisible = false;
    }

    /**
     * 切换教程显示状态
     */
    public toggle(): void {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }

    /**
     * 添加自定义步骤
     */
    public addStep(step: GestureTutorialStep): void {
        this.steps.push(step);
        this.steps.sort((a, b) => a.priority - b.priority);
    }

    /**
     * 移除步骤
     */
    public removeStep(stepId: string): void {
        this.steps = this.steps.filter(step => step.id !== stepId);
    }

    /**
     * 获取所有步骤
     */
    public getSteps(): GestureTutorialStep[] {
        return [...this.steps];
    }

    /**
     * 获取当前步骤
     */
    public getCurrentStep(): GestureTutorialStep | null {
        return this.steps[this.currentStepIndex] || null;
    }

    /**
     * 下一步
     */
    public nextStep(): void {
        if (this.currentStepIndex < this.steps.length - 1) {
            this.markStepCompleted(this.steps[this.currentStepIndex].id);
            this.currentStepIndex++;
            this.render();
        } else {
            this.completeTutorial();
        }
    }

    /**
     * 上一步
     */
    public previousStep(): void {
        if (this.currentStepIndex > 0) {
            this.currentStepIndex--;
            this.render();
        }
    }

    /**
     * 跳转到指定步骤
     */
    public goToStep(stepIndex: number): void {
        if (stepIndex >= 0 && stepIndex < this.steps.length) {
            this.currentStepIndex = stepIndex;
            this.render();
        }
    }

    /**
     * 标记步骤为已完成
     */
    private markStepCompleted(stepId: string): void {
        this.completedSteps.add(stepId);
        this.saveCompletedSteps();
    }

    /**
     * 完成教程
     */
    public completeTutorial(): void {
        this.steps.forEach(step => {
            this.completedSteps.add(step.id);
        });
        this.saveCompletedSteps();
        this.hide();
    }

    /**
     * 重置教程
     */
    public resetTutorial(): void {
        this.completedSteps.clear();
        this.saveCompletedSteps();
        this.currentStepIndex = 0;
    }

    /**
     * 检查是否应该显示教程
     */
    private shouldShowTutorial(): boolean {
        if (!this.options.showOnFirstLaunch) return false;

        const hasCompleted = localStorage.getItem(this.options.storageKey) === 'true';
        return !hasCompleted;
    }

    /**
     * 加载已完成的步骤
     */
    private loadCompletedSteps(): void {
        try {
            const data = localStorage.getItem(`${this.options.storageKey}_steps`);
            if (data) {
                const completed = JSON.parse(data);
                this.completedSteps = new Set(completed);
            }
        } catch (e) {
            console.warn('加载教程进度失败:', e);
        }
    }

    /**
     * 保存已完成的步骤
     */
    private saveCompletedSteps(): void {
        try {
            localStorage.setItem(this.options.storageKey, 'true');
            localStorage.setItem(
                `${this.options.storageKey}_steps`,
                JSON.stringify(Array.from(this.completedSteps))
            );
        } catch (e) {
            console.warn('保存教程进度失败:', e);
        }
    }

    /**
     * 渲染教程界面
     */
    private render(): void {
        if (!this.container) return;

        // 移除现有教程
        const existingOverlay = this.container.querySelector('.gesture-tutorial-overlay');
        if (existingOverlay) {
            existingOverlay.remove();
        }

        const currentStep = this.getCurrentStep();
        if (!currentStep) return;

        // 创建教程覆盖层
        const overlay = document.createElement('div');
        overlay.className = 'gesture-tutorial-overlay';
        overlay.innerHTML = `
            <div class="gesture-tutorial-content">
                <div class="gesture-tutorial-header">
                    <h2>手势教程</h2>
                    ${this.options.dismissible ? '<button class="close-button" aria-label="关闭教程">×</button>' : ''}
                </div>

                <div class="gesture-tutorial-body">
                    <div class="gesture-animation-container">
                        <div class="gesture-icon">${currentStep.icon}</div>
                        <div class="gesture-animation ${currentStep.animation}"></div>
                    </div>

                    <div class="gesture-info">
                        <h3>${currentStep.title}</h3>
                        <p>${currentStep.description}</p>
                    </div>

                    <div class="gesture-progress">
                        <div class="progress-dots">
                            ${this.steps.map((_, index) => `
                                <div class="progress-dot ${index === this.currentStepIndex ? 'active' : ''} ${this.completedSteps.has(this.steps[index].id) ? 'completed' : ''}"></div>
                            `).join('')}
                        </div>
                        <div class="progress-text">
                            步骤 ${this.currentStepIndex + 1} / ${this.steps.length}
                        </div>
                    </div>
                </div>

                <div class="gesture-tutorial-footer">
                    <button class="button button-secondary" ${this.currentStepIndex === 0 ? 'disabled' : ''}>
                        上一步
                    </button>
                    <button class="button button-primary">
                        ${this.currentStepIndex === this.steps.length - 1 ? '完成' : '下一步'}
                    </button>
                </div>
            </div>
        `;

        // 添加样式
        this.injectStyles();

        // 绑定事件
        this.bindEvents(overlay);

        this.container.appendChild(overlay);
    }

    /**
     * 绑定事件
     */
    private bindEvents(overlay: HTMLElement): void {
        const closeButton = overlay.querySelector('.close-button') as HTMLElement;
        const previousButton = overlay.querySelector('.button-secondary') as HTMLElement;
        const nextButton = overlay.querySelector('.button-primary') as HTMLElement;
        const progressDots = overlay.querySelectorAll('.progress-dot');

        if (closeButton) {
            closeButton.addEventListener('click', () => this.hide());
        }

        if (previousButton) {
            previousButton.addEventListener('click', () => this.previousStep());
        }

        if (nextButton) {
            nextButton.addEventListener('click', () => this.nextStep());
        }

        progressDots.forEach((dot, index) => {
            dot.addEventListener('click', () => this.goToStep(index));
        });
    }

    /**
     * 注入样式
     */
    private injectStyles(): void {
        if (document.getElementById('gesture-tutorial-styles')) return;

        const style = document.createElement('style');
        style.id = 'gesture-tutorial-styles';
        style.textContent = `
            .gesture-tutorial-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                animation: fadeIn 0.3s ease-out;
            }

            .gesture-tutorial-content {
                background: var(--background-primary);
                border-radius: 16px;
                padding: 24px;
                max-width: 400px;
                width: 90%;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
                animation: slideUp 0.3s ease-out;
            }

            .gesture-tutorial-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
            }

            .gesture-tutorial-header h2 {
                margin: 0;
                font-size: 20px;
                color: var(--text-primary);
            }

            .close-button {
                background: none;
                border: none;
                font-size: 32px;
                color: var(--text-secondary);
                cursor: pointer;
                padding: 0;
                width: 32px;
                height: 32px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 4px;
                transition: background 0.2s;
            }

            .close-button:hover {
                background: var(--background-secondary);
                color: var(--text-primary);
            }

            .gesture-tutorial-body {
                text-align: center;
                margin-bottom: 24px;
            }

            .gesture-animation-container {
                position: relative;
                width: 120px;
                height: 120px;
                margin: 0 auto 20px;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .gesture-icon {
                font-size: 48px;
                z-index: 1;
            }

            .gesture-animation {
                position: absolute;
                width: 100%;
                height: 100%;
                border-radius: 50%;
                background: var(--accent-color, #3b82f6);
                opacity: 0.2;
                animation: pulse 2s ease-in-out infinite;
            }

            .gesture-animation.tap {
                animation: tapAnimation 0.6s ease-out;
            }

            .gesture-animation.doubleTap {
                animation: doubleTapAnimation 0.8s ease-out;
            }

            .gesture-animation.longPress {
                animation: longPressAnimation 1s ease-out;
            }

            .gesture-animation.pinch {
                animation: pinchAnimation 1.2s ease-in-out infinite;
            }

            .gesture-animation.rotate {
                animation: rotateAnimation 2s linear infinite;
            }

            .gesture-animation.tripleFingerPinch {
                animation: triplePinchAnimation 1.5s ease-in-out infinite;
            }

            .gesture-animation.swipe {
                animation: swipeAnimation 1s ease-out;
            }

            .gesture-animation.quickSwipe {
                animation: quickSwipeAnimation 0.5s ease-out;
            }

            .gesture-animation.layerSwipe {
                animation: layerSwipeAnimation 1.2s ease-out;
            }

            .gesture-info h3 {
                margin: 0 0 8px;
                font-size: 18px;
                color: var(--text-primary);
            }

            .gesture-info p {
                margin: 0;
                font-size: 14px;
                color: var(--text-secondary);
                line-height: 1.5;
            }

            .gesture-progress {
                margin-top: 20px;
            }

            .progress-dots {
                display: flex;
                justify-content: center;
                gap: 8px;
                margin-bottom: 8px;
            }

            .progress-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: var(--border-color);
                cursor: pointer;
                transition: all 0.2s;
            }

            .progress-dot.active {
                background: var(--accent-color, #3b82f6);
                transform: scale(1.2);
            }

            .progress-dot.completed {
                background: var(--success-color, #10b981);
            }

            .progress-text {
                font-size: 12px;
                color: var(--text-secondary);
            }

            .gesture-tutorial-footer {
                display: flex;
                gap: 12px;
                justify-content: flex-end;
            }

            .button {
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                cursor: pointer;
                transition: all 0.2s;
            }

            .button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }

            .button-primary {
                background: var(--accent-color, #3b82f6);
                color: white;
            }

            .button-primary:hover:not(:disabled) {
                background: var(--accent-hover, #2563eb);
            }

            .button-secondary {
                background: var(--background-secondary);
                color: var(--text-primary);
            }

            .button-secondary:hover:not(:disabled) {
                background: var(--background-hover);
            }

            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }

            @keyframes slideUp {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            @keyframes pulse {
                0%, 100% { transform: scale(1); opacity: 0.2; }
                50% { transform: scale(1.1); opacity: 0.3; }
            }

            @keyframes tapAnimation {
                0% { transform: scale(0.5); opacity: 0.5; }
                50% { transform: scale(1.2); opacity: 0.3; }
                100% { transform: scale(1); opacity: 0.2; }
            }

            @keyframes doubleTapAnimation {
                0%, 100% { transform: scale(1); opacity: 0.2; }
                25% { transform: scale(1.2); opacity: 0.3; }
                50% { transform: scale(1); opacity: 0.2; }
                75% { transform: scale(1.2); opacity: 0.3; }
            }

            @keyframes longPressAnimation {
                0% { transform: scale(0.8); opacity: 0.3; }
                100% { transform: scale(1.3); opacity: 0.2; }
            }

            @keyframes pinchAnimation {
                0%, 100% { transform: scale(0.8); }
                50% { transform: scale(1.2); }
            }

            @keyframes rotateAnimation {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }

            @keyframes triplePinchAnimation {
                0%, 100% { transform: scale(0.7); }
                50% { transform: scale(1.3); }
            }

            @keyframes swipeAnimation {
                0% { transform: translateX(-20px); opacity: 0.3; }
                50% { transform: translateX(20px); opacity: 0.4; }
                100% { transform: translateX(0); opacity: 0.2; }
            }

            @keyframes quickSwipeAnimation {
                0% { transform: translateX(-30px); opacity: 0.3; }
                100% { transform: translateX(30px); opacity: 0; }
            }

            @keyframes layerSwipeAnimation {
                0%, 100% { transform: translateX(-10px); opacity: 0.2; }
                50% { transform: translateX(10px); opacity: 0.3; }
            }
        `;

        document.head.appendChild(style);
    }

    /**
     * 销毁教程
     */
    public destroy(): void {
        this.hide();
        const styles = document.getElementById('gesture-tutorial-styles');
        if (styles) {
            styles.remove();
        }
    }
}

export default GestureTutorial;