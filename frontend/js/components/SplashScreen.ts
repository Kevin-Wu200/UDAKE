/**
 * 启动画面组件
 * 提供品牌展示、加载状态显示和启动动画
 */

export type SplashScreenStage = 'initializing' | 'loading' | 'ready' | 'error';

export interface SplashScreenOptions {
    showSkipButton?: boolean;
    showProgress?: boolean;
    animationDuration?: number;
    minDisplayTime?: number;
}

export class SplashScreen {
    private static instance: SplashScreen | null = null;
    private element: HTMLDivElement | null = null;
    private logoElement: HTMLDivElement | null = null;
    private textElement: HTMLDivElement | null = null;
    private progressContainer: HTMLDivElement | null = null;
    private progressBar: HTMLDivElement | null = null;
    private progressText: HTMLDivElement | null = null;
    private skipButton: HTMLButtonElement | null = null;
    private currentStage: SplashScreenStage = 'initializing';
    private startTime: number = 0;
    private minDisplayTime: number = 2000;
    private showSkipButton: boolean = false;
    private showProgress: boolean = true;
    private isSkipped: boolean = false;
    private progress: number = 0;
    private onSkipCallback: (() => void) | null = null;
    private onReadyCallback: (() => void) | null = null;

    private constructor(options: SplashScreenOptions = {}) {
        this.showSkipButton = options.showSkipButton ?? false;
        this.showProgress = options.showProgress ?? true;
        this.minDisplayTime = options.minDisplayTime ?? 2000;
        this.create();
    }

    /**
     * 获取单例实例
     */
    public static getInstance(options?: SplashScreenOptions): SplashScreen {
        if (!SplashScreen.instance) {
            SplashScreen.instance = new SplashScreen(options);
        }
        return SplashScreen.instance;
    }

    /**
     * 创建启动画面
     */
    private create(): void {
        const splash = document.createElement('div');
        splash.className = 'splash-screen';
        splash.innerHTML = `
            <div class="splash-background"></div>
            <div class="splash-content">
                <div class="splash-logo">
                    <div class="logo-icon">UDAKE</div>
                </div>
                <div class="splash-text">
                    <div class="app-name">智能不确定性驱动空间决策平台</div>
                    <div class="app-slogan">Intelligent Uncertainty-Driven Spatial Decision Platform</div>
                </div>
                <div class="splash-loading">
                    <div class="splash-spinner"></div>
                    <div class="splash-status">正在初始化...</div>
                </div>
                <div class="splash-progress-container">
                    <div class="splash-progress-bar">
                        <div class="splash-progress-fill"></div>
                    </div>
                    <div class="splash-progress-text">0%</div>
                </div>
                <button class="splash-skip-button" style="display: none;">跳过</button>
            </div>
        `;

        document.body.appendChild(splash);
        this.element = splash;

        // 获取元素引用
        this.logoElement = splash.querySelector('.splash-logo');
        this.textElement = splash.querySelector('.splash-text');
        this.progressContainer = splash.querySelector('.splash-progress-container');
        this.progressBar = splash.querySelector('.splash-progress-fill') as HTMLDivElement;
        this.progressText = splash.querySelector('.splash-progress-text') as HTMLDivElement;
        this.skipButton = splash.querySelector('.splash-skip-button') as HTMLButtonElement;

        // 绑定事件
        this.bindEvents();

        // 设置初始状态
        if (!this.showProgress) {
            this.progressContainer!.style.display = 'none';
        }
        if (this.showSkipButton) {
            this.skipButton!.style.display = 'block';
        }

        // 添加动画类
        requestAnimationFrame(() => {
            splash.classList.add('splash-visible');
        });
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        if (this.skipButton) {
            this.skipButton.addEventListener('click', () => {
                this.skip();
            });
        }
    }

    /**
     * 显示启动画面
     */
    public show(): void {
        if (!this.element) {
            this.create();
        }
        this.startTime = Date.now();
        this.currentStage = 'initializing';
        this.isSkipped = false;
        this.progress = 0;
        this.updateProgress(0);
        this.updateStatus('正在初始化...');
        this.element!.classList.add('splash-visible');
        this.element!.style.display = 'flex';
    }

    /**
     * 更新状态
     */
    public updateStatus(status: string): void {
        const statusElement = this.element?.querySelector('.splash-status');
        if (statusElement) {
            statusElement.textContent = status;
        }
    }

    /**
     * 更新进度
     */
    public updateProgress(percent: number): void {
        this.progress = Math.min(100, Math.max(0, percent));
        if (this.progressBar) {
            this.progressBar.style.width = `${this.progress}%`;
        }
        if (this.progressText) {
            this.progressText.textContent = `${Math.round(this.progress)}%`;
        }
    }

    /**
     * 设置当前阶段
     */
    public setStage(stage: SplashScreenStage): void {
        this.currentStage = stage;

        // 更新加载动画
        const spinner = this.element?.querySelector('.splash-spinner');
        if (spinner) {
            spinner.classList.remove('spinner-paused');
            if (stage === 'ready') {
                spinner.classList.add('spinner-complete');
            } else if (stage === 'error') {
                spinner.classList.add('spinner-error');
            }
        }

        // 更新状态文本
        const statusMessages = {
            'initializing': '正在初始化...',
            'loading': '正在加载资源...',
            'ready': '准备就绪',
            'error': '加载失败'
        };

        this.updateStatus(statusMessages[stage]);
    }

    /**
     * 跳过启动画面
     */
    public skip(): void {
        if (this.isSkipped) return;

        this.isSkipped = true;
        if (this.onSkipCallback) {
            this.onSkipCallback();
        }
        this.hide();
    }

    /**
     * 隐藏启动画面
     */
    public async hide(): Promise<void> {
        if (!this.element) return;

        // 确保至少显示最短时间
        const elapsedTime = Date.now() - this.startTime;
        if (elapsedTime < this.minDisplayTime && !this.isSkipped) {
            await new Promise(resolve => setTimeout(resolve, this.minDisplayTime - elapsedTime));
        }

        // 添加隐藏动画
        this.element.classList.remove('splash-visible');
        this.element.classList.add('splash-hidden');

        // 动画完成后移除元素
        setTimeout(() => {
            if (this.element) {
                this.element.style.display = 'none';
                this.element.remove();
                this.element = null;
            }
        }, 500);

        // 触发就绪回调
        if (this.onReadyCallback) {
            this.onReadyCallback();
        }
    }

    /**
     * 设置跳过回调
     */
    public onSkip(callback: () => void): void {
        this.onSkipCallback = callback;
    }

    /**
     * 设置就绪回调
     */
    public onReady(callback: () => void): void {
        this.onReadyCallback = callback;
    }

    /**
     * 设置显示跳过按钮
     */
    public setShowSkipButton(show: boolean): void {
        this.showSkipButton = show;
        if (this.skipButton) {
            this.skipButton.style.display = show ? 'block' : 'none';
        }
    }

    /**
     * 设置显示进度条
     */
    public setShowProgress(show: boolean): void {
        this.showProgress = show;
        if (this.progressContainer) {
            this.progressContainer.style.display = show ? 'block' : 'none';
        }
    }

    /**
     * 销毁启动画面
     */
    public destroy(): void {
        if (this.element) {
            this.element.remove();
            this.element = null;
        }
        SplashScreen.instance = null;
    }
}