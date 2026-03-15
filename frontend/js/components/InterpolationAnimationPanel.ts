/**
 * 插值过程动画面板
 * 提供数据插值过程的可视化动画，包括数据加载、变异函数拟合、插值计算等阶段
 */

// 动画控制类型
export type AnimationSpeed = 'slow' | 'normal' | 'fast';
export type AnimationStage = 'loading' | 'variogram' | 'interpolation' | 'result';

// 阶段配置
interface StageConfig {
    stage: AnimationStage;
    name: string;
    icon: string;
    description: string;
}

// 数据点信息
interface DataPoint {
    x: number;
    y: number;
    value: number;
    id: string;
}

// 动画配置
interface AnimationConfig {
    speed: AnimationSpeed;
    isPlaying: boolean;
    currentStage: AnimationStage;
    progress: number;
}

// 动画事件
interface AnimationEvents {
    onStageChange?: (stage: AnimationStage) => void;
    onAnimationComplete?: () => void;
    onProgressUpdate?: (progress: number) => void;
}

export class InterpolationAnimationPanel {
    private container: HTMLElement;
    private overlay!: HTMLElement;
    private panel!: HTMLElement;
    private animationCanvas!: HTMLCanvasElement;
    private ctx!: CanvasRenderingContext2D;
    private animationId: number | null = null;
    private animationConfig: AnimationConfig;
    private stages: StageConfig[];
    private dataPoints: DataPoint[] = [];
    private events: AnimationEvents;
    private variogramPoints: Array<{ distance: number; variance: number }> = [];
    private fittedCurve: Array<{ distance: number; variance: number }> = [];
    private interpolationResult: Array<{ x: number; y: number; value: number }> = [];
    private loadedPointsCount = 0;
    private currentFrame = 0;

    constructor(container: HTMLElement | string, events?: AnimationEvents) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)!
            : container;
        this.events = events || {};
        this.animationConfig = {
            speed: 'normal',
            isPlaying: false,
            currentStage: 'loading',
            progress: 0
        };
        this.stages = [
            { stage: 'loading', name: '数据加载', icon: '📊', description: '加载采样点数据' },
            { stage: 'variogram', name: '变异函数拟合', icon: '📈', description: '拟合变异函数模型' },
            { stage: 'interpolation', name: '插值计算', icon: '🔬', description: '执行克里金插值计算' },
            { stage: 'result', name: '结果生成', icon: '✨', description: '生成预测结果' }
        ];
        this.init();
    }

    private init(): void {
        this.createPanel();
        this.bindEvents();
    }

    private createPanel(): void {
        // 创建遮罩层
        this.overlay = document.createElement('div');
        this.overlay.className = 'interpolation-animation-overlay';
        this.overlay.style.display = 'none';

        // 创建动画面板
        this.panel = document.createElement('div');
        this.panel.className = 'interpolation-animation-panel';
        this.panel.innerHTML = `
            <div class="interpolation-animation-content">
                <div class="animation-header">
                    <h2 class="animation-title">插值过程可视化</h2>
                    <button class="btn btn-icon animation-close-btn" title="关闭">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>

                <div class="animation-body">
                    <!-- 动画画布 -->
                    <div class="animation-canvas-container">
                        <canvas id="interpolation-animation-canvas" class="animation-canvas"></canvas>
                    </div>

                    <!-- 阶段指示器 -->
                    <div class="animation-stages">
                        ${this.stages.map((stage, _index) => `
                            <div class="animation-stage" data-stage="${stage.stage}">
                                <div class="stage-icon">${stage.icon}</div>
                                <div class="stage-name">${stage.name}</div>
                                <div class="stage-progress">
                                    <div class="stage-progress-bar">
                                        <div class="stage-progress-fill"></div>
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>

                    <!-- 当前阶段描述 -->
                    <div class="current-stage-description">
                        <div class="stage-description-icon" id="stage-description-icon">📊</div>
                        <div class="stage-description-text" id="stage-description-text">加载采样点数据</div>
                    </div>

                    <!-- 动画控制 -->
                    <div class="animation-controls">
                        <button class="btn btn-primary animation-play-btn" id="animation-play-btn">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                <polygon points="5,3 19,12 5,21"></polygon>
                            </svg>
                            播放
                        </button>
                        <button class="btn animation-pause-btn" id="animation-pause-btn" style="display: none;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                <rect x="6" y="4" width="4" height="16"></rect>
                                <rect x="14" y="4" width="4" height="16"></rect>
                            </svg>
                            暂停
                        </button>
                        <button class="btn animation-reset-btn" id="animation-reset-btn">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path>
                                <path d="M3 3v5h5"></path>
                            </svg>
                            重置
                        </button>
                        <div class="animation-speed-control">
                            <span class="speed-label">速度：</span>
                            <button class="btn btn-small speed-btn ${this.animationConfig.speed === 'slow' ? 'active' : ''}" data-speed="slow">慢</button>
                            <button class="btn btn-small speed-btn ${this.animationConfig.speed === 'normal' ? 'active' : ''}" data-speed="normal">正常</button>
                            <button class="btn btn-small speed-btn ${this.animationConfig.speed === 'fast' ? 'active' : ''}" data-speed="fast">快</button>
                        </div>
                    </div>

                    <!-- 进度信息 -->
                    <div class="animation-progress-info">
                        <div class="progress-info-item">
                            <span class="progress-info-label">进度：</span>
                            <span class="progress-info-value" id="animation-progress">0%</span>
                        </div>
                        <div class="progress-info-item">
                            <span class="progress-info-label">已加载点数：</span>
                            <span class="progress-info-value" id="loaded-points-count">0</span>
                        </div>
                        <div class="progress-info-item">
                            <span class="progress-info-label">计算速度：</span>
                            <span class="progress-info-value" id="calculation-speed">--</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.overlay.appendChild(this.panel);
        this.container.appendChild(this.overlay);

        // 初始化画布
        this.animationCanvas = this.panel.querySelector('#interpolation-animation-canvas') as HTMLCanvasElement;
        this.ctx = this.animationCanvas.getContext('2d')!;
        this.resizeCanvas();
    }

    private bindEvents(): void {
        const closeBtn = this.panel.querySelector('.animation-close-btn') as HTMLElement;
        closeBtn.addEventListener('click', () => this.hide());

        const playBtn = this.panel.querySelector('#animation-play-btn') as HTMLElement;
        playBtn.addEventListener('click', () => this.play());

        const pauseBtn = this.panel.querySelector('#animation-pause-btn') as HTMLElement;
        pauseBtn.addEventListener('click', () => this.pause());

        const resetBtn = this.panel.querySelector('#animation-reset-btn') as HTMLElement;
        resetBtn.addEventListener('click', () => this.reset());

        const speedBtns = this.panel.querySelectorAll('.speed-btn');
        speedBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const speed = (e.target as HTMLElement).dataset.speed as AnimationSpeed;
                this.setSpeed(speed);
            });
        });

        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this.hide();
            }
        });

        window.addEventListener('resize', () => this.resizeCanvas());
    }

    private resizeCanvas(): void {
        const container = this.panel.querySelector('.animation-canvas-container') as HTMLElement;
        const rect = container.getBoundingClientRect();
        this.animationCanvas.width = rect.width;
        this.animationCanvas.height = rect.height;
    }

    public show(dataPoints?: DataPoint[]): void {
        if (dataPoints) {
            this.dataPoints = dataPoints;
        }
        this.overlay.style.display = 'flex';
        this.resizeCanvas();
        this.reset();
    }

    public hide(): void {
        this.pause();
        this.overlay.style.display = 'none';
    }

    public play(): void {
        if (this.animationConfig.isPlaying) return;

        this.animationConfig.isPlaying = true;
        this.updateControlButtons();
        this.animate();
    }

    public pause(): void {
        this.animationConfig.isPlaying = false;
        this.updateControlButtons();
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }

    public reset(): void {
        this.pause();
        this.animationConfig.currentStage = 'loading';
        this.animationConfig.progress = 0;
        this.loadedPointsCount = 0;
        this.currentFrame = 0;
        this.variogramPoints = [];
        this.fittedCurve = [];
        this.interpolationResult = [];
        this.clearCanvas();
        this.updateUI();
        this.updateStageIndicators();
    }

    public setSpeed(speed: AnimationSpeed): void {
        this.animationConfig.speed = speed;
        this.panel.querySelectorAll('.speed-btn').forEach(btn => {
            btn.classList.toggle('active', (btn as HTMLElement).dataset.speed === speed);
        });
    }

    private updateControlButtons(): void {
        const playBtn = this.panel.querySelector('#animation-play-btn') as HTMLElement;
        const pauseBtn = this.panel.querySelector('#animation-pause-btn') as HTMLElement;
        playBtn.style.display = this.animationConfig.isPlaying ? 'none' : 'block';
        pauseBtn.style.display = this.animationConfig.isPlaying ? 'block' : 'none';
    }

    private animate(): void {
        if (!this.animationConfig.isPlaying) return;

        this.animationId = requestAnimationFrame(() => this.animate());
        this.update();
    }

    private update(): void {
        const speedMultiplier = this.getSpeedMultiplier();

        switch (this.animationConfig.currentStage) {
            case 'loading':
                this.updateLoadingStage(speedMultiplier);
                break;
            case 'variogram':
                this.updateVariogramStage(speedMultiplier);
                break;
            case 'interpolation':
                this.updateInterpolationStage(speedMultiplier);
                break;
            case 'result':
                this.updateResultStage(speedMultiplier);
                break;
        }

        this.updateUI();
    }

    private getSpeedMultiplier(): number {
        const speedMap: Record<AnimationSpeed, number> = {
            'slow': 0.5,
            'normal': 1,
            'fast': 2
        };
        return speedMap[this.animationConfig.speed];
    }

    private updateLoadingStage(speedMultiplier: number): void {
        if (this.loadedPointsCount < this.dataPoints.length) {
            this.loadedPointsCount += Math.ceil(speedMultiplier);
            if (this.loadedPointsCount > this.dataPoints.length) {
                this.loadedPointsCount = this.dataPoints.length;
            }
            this.animationConfig.progress = (this.loadedPointsCount / this.dataPoints.length) * 25;
        } else {
            this.transitionToStage('variogram');
        }
    }

    private updateVariogramStage(_speedMultiplier: number): void {
        // 生成变异函数点
        const totalVariogramPoints = 20;
        const currentProgress = (this.animationConfig.progress - 25) / 25; // 25-50%
        const targetPoints = Math.floor(currentProgress * totalVariogramPoints);

        while (this.variogramPoints.length < targetPoints) {
            const distance = this.variogramPoints.length * 0.5;
            const variance = Math.random() * 0.8 + 0.1;
            this.variogramPoints.push({ distance, variance });
        }

        // 生成拟合曲线
        if (this.variogramPoints.length >= totalVariogramPoints) {
            this.generateFittedCurve();
            this.animationConfig.progress = 50;
            this.transitionToStage('interpolation');
        } else {
            this.animationConfig.progress = 25 + (this.variogramPoints.length / totalVariogramPoints) * 25;
        }
    }

    private generateFittedCurve(): void {
        for (let i = 0; i <= 20; i++) {
            const distance = i * 0.5;
            const variance = 1 - Math.exp(-3 * distance);
            this.fittedCurve.push({ distance, variance });
        }
    }

    private updateInterpolationStage(_speedMultiplier: number): void {
        const gridResolution = 20;
        const totalPoints = gridResolution * gridResolution;
        const currentProgress = (this.animationConfig.progress - 50) / 40; // 50-90%
        const targetPoints = Math.floor(currentProgress * totalPoints);

        while (this.interpolationResult.length < targetPoints) {
            const x = (this.interpolationResult.length % gridResolution) * (800 / gridResolution);
            const y = Math.floor(this.interpolationResult.length / gridResolution) * (600 / gridResolution);
            const value = this.interpolateValue(x, y);
            this.interpolationResult.push({ x, y, value });
        }

        if (this.interpolationResult.length >= totalPoints) {
            this.animationConfig.progress = 90;
            this.transitionToStage('result');
        } else {
            this.animationConfig.progress = 50 + (this.interpolationResult.length / totalPoints) * 40;
        }
    }

    private interpolateValue(x: number, y: number): number {
        // 简化的插值计算
        let sum = 0;
        let weightSum = 0;

        for (const point of this.dataPoints) {
            const distance = Math.sqrt(Math.pow(x - point.x, 2) + Math.pow(y - point.y, 2));
            const weight = 1 / (distance + 0.1);
            sum += point.value * weight;
            weightSum += weight;
        }

        return weightSum > 0 ? sum / weightSum : 0;
    }

    private updateResultStage(speedMultiplier: number): void {
        if (this.animationConfig.progress < 100) {
            this.animationConfig.progress += speedMultiplier * 0.5;
            if (this.animationConfig.progress > 100) {
                this.animationConfig.progress = 100;
            }
        } else {
            this.animationConfig.isPlaying = false;
            this.updateControlButtons();
            if (this.events.onAnimationComplete) {
                this.events.onAnimationComplete();
            }
        }
    }

    private transitionToStage(stage: AnimationStage): void {
        this.animationConfig.currentStage = stage;
        this.updateStageIndicators();
        this.updateStageDescription();

        if (this.events.onStageChange) {
            this.events.onStageChange(stage);
        }
    }

    private updateStageIndicators(): void {
        const stageElements = this.panel.querySelectorAll('.animation-stage');
        stageElements.forEach(el => {
            const stage = (el as HTMLElement).dataset.stage as AnimationStage;
            const stageIndex = this.stages.findIndex(s => s.stage === stage);
            const currentIndex = this.stages.findIndex(s => s.stage === this.animationConfig.currentStage);

            el.classList.remove('active', 'completed');
            if (stage === this.animationConfig.currentStage) {
                el.classList.add('active');
            } else if (stageIndex < currentIndex) {
                el.classList.add('completed');
            }

            // 更新进度条
            const progressBar = el.querySelector('.stage-progress-fill') as HTMLElement;
            let progress = 0;
            if (stage === this.animationConfig.currentStage) {
                progress = this.getStageProgress();
            } else if (stageIndex < currentIndex) {
                progress = 100;
            }
            progressBar.style.width = `${progress}%`;
        });
    }

    private getStageProgress(): number {
        const progress = this.animationConfig.progress;
        if (progress < 25) return (progress / 25) * 100;
        if (progress < 50) return ((progress - 25) / 25) * 100;
        if (progress < 90) return ((progress - 50) / 40) * 100;
        return ((progress - 90) / 10) * 100;
    }

    private updateStageDescription(): void {
        const icon = this.panel.querySelector('#stage-description-icon') as HTMLElement;
        const text = this.panel.querySelector('#stage-description-text') as HTMLElement;
        const currentStageInfo = this.stages.find(s => s.stage === this.animationConfig.currentStage);
        if (currentStageInfo) {
            icon.textContent = currentStageInfo.icon;
            text.textContent = currentStageInfo.description;
        }
    }

    private updateUI(): void {
        const progress = document.getElementById('animation-progress') as HTMLElement;
        const loadedPoints = document.getElementById('loaded-points-count') as HTMLElement;
        const calcSpeed = document.getElementById('calculation-speed') as HTMLElement;

        progress.textContent = `${Math.round(this.animationConfig.progress)}%`;
        loadedPoints.textContent = this.loadedPointsCount.toString();

        // 计算速度（点/秒）
        if (this.interpolationResult.length > 0) {
            const speed = this.interpolationResult.length * this.getSpeedMultiplier();
            calcSpeed.textContent = `${speed.toFixed(0)} 点/秒`;
        } else {
            calcSpeed.textContent = '--';
        }

        if (this.events.onProgressUpdate) {
            this.events.onProgressUpdate(this.animationConfig.progress);
        }

        this.render();
    }

    private clearCanvas(): void {
        this.ctx.clearRect(0, 0, this.animationCanvas.width, this.animationCanvas.height);
    }

    private render(): void {
        this.clearCanvas();

        switch (this.animationConfig.currentStage) {
            case 'loading':
                this.renderLoadingStage();
                break;
            case 'variogram':
                this.renderVariogramStage();
                break;
            case 'interpolation':
                this.renderInterpolationStage();
                break;
            case 'result':
                this.renderResultStage();
                break;
        }
    }

    private renderLoadingStage(): void {
        // 绘制已加载的数据点
        this.ctx.fillStyle = '#3B82F6';
        this.ctx.strokeStyle = '#1E40AF';
        this.ctx.lineWidth = 2;

        for (let i = 0; i < this.loadedPointsCount; i++) {
            const point = this.dataPoints[i];
            const x = (point.x / 800) * this.animationCanvas.width;
            const y = (point.y / 600) * this.animationCanvas.height;

            this.ctx.beginPath();
            this.ctx.arc(x, y, 5, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.stroke();
        }

        // 绘制加载动画效果
        if (this.loadedPointsCount < this.dataPoints.length) {
            const centerX = this.animationCanvas.width / 2;
            const centerY = this.animationCanvas.height / 2;
            const radius = 50;
            const angle = (this.currentFrame * 0.05) % (Math.PI * 2);

            this.ctx.strokeStyle = 'rgba(59, 130, 246, 0.5)';
            this.ctx.lineWidth = 3;
            this.ctx.beginPath();
            this.ctx.arc(centerX, centerY, radius, angle, angle + Math.PI);
            this.ctx.stroke();
        }
    }

    private renderVariogramStage(): void {
        // 绘制变异函数图表
        const chartX = 50;
        const chartY = 50;
        const chartWidth = this.animationCanvas.width - 100;
        const chartHeight = this.animationCanvas.height - 100;

        // 绘制坐标轴
        this.ctx.strokeStyle = '#E5E7EB';
        this.ctx.lineWidth = 1;
        this.ctx.beginPath();
        this.ctx.moveTo(chartX, chartY);
        this.ctx.lineTo(chartX, chartY + chartHeight);
        this.ctx.lineTo(chartX + chartWidth, chartY + chartHeight);
        this.ctx.stroke();

        // 绘制变异函数点
        this.ctx.fillStyle = '#3B82F6';
        for (const point of this.variogramPoints) {
            const x = chartX + (point.distance / 10) * chartWidth;
            const y = chartY + chartHeight - (point.variance / 1.5) * chartHeight;

            this.ctx.beginPath();
            this.ctx.arc(x, y, 4, 0, Math.PI * 2);
            this.ctx.fill();
        }

        // 绘制拟合曲线
        if (this.fittedCurve.length > 0) {
            this.ctx.strokeStyle = '#10B981';
            this.ctx.lineWidth = 2;
            this.ctx.beginPath();

            for (let i = 0; i < this.fittedCurve.length; i++) {
                const point = this.fittedCurve[i];
                const x = chartX + (point.distance / 10) * chartWidth;
                const y = chartY + chartHeight - (point.variance / 1.5) * chartHeight;

                if (i === 0) {
                    this.ctx.moveTo(x, y);
                } else {
                    this.ctx.lineTo(x, y);
                }
            }
            this.ctx.stroke();
        }
    }

    private renderInterpolationStage(): void {
        // 绘制插值结果（从中心向外扩散）
        const centerX = this.animationCanvas.width / 2;
        const centerY = this.animationCanvas.height / 2;
        const maxDistance = Math.sqrt(Math.pow(centerX, 2) + Math.pow(centerY, 2));

        for (const point of this.interpolationResult) {
            const x = (point.x / 800) * this.animationCanvas.width;
            const y = (point.y / 600) * this.animationCanvas.height;
            const distance = Math.sqrt(Math.pow(x - centerX, 2) + Math.pow(y - centerY, 2));
            const normalizedDistance = distance / maxDistance;

            // 根据距离计算颜色
            const hue = 240 - (point.value / 100) * 240;
            const saturation = 70 + normalizedDistance * 30;
            const lightness = 50 + normalizedDistance * 20;

            this.ctx.fillStyle = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
            this.ctx.fillRect(x, y, 4, 4);
        }
    }

    private renderResultStage(): void {
        // 绘制完整的结果
        this.renderInterpolationStage();

        // 添加完成效果
        const centerX = this.animationCanvas.width / 2;
        const centerY = this.animationCanvas.height / 2;
        const radius = Math.min(centerX, centerY) * 0.3;
        const alpha = (this.animationConfig.progress - 90) / 10;

        this.ctx.fillStyle = `rgba(255, 255, 255, ${alpha * 0.3})`;
        this.ctx.beginPath();
        this.ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
        this.ctx.font = 'bold 24px sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText('完成', centerX, centerY);
    }
}