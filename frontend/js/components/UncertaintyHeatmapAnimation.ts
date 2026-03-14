/**
 * 不确定性热图动画组件
 * 提供不确定性热图的可视化动画，包括采样点添加、不确定性降低等效果
 */

// 不确定性等级
export type UncertaintyLevel = 'very-low' | 'low' | 'medium' | 'high' | 'very-high';

// 采样点信息
interface SamplingPoint {
    id: string;
    x: number;
    y: number;
    uncertainty: number;
    value: number;
    strategy: string;
    order: number;
    level: UncertaintyLevel;
}

// 不确定性网格单元
interface UncertaintyCell {
    x: number;
    y: number;
    uncertainty: number;
    level: UncertaintyLevel;
}

// 动画状态
interface AnimationState {
    isPlaying: boolean;
    currentPoint: number;
    totalPoints: number;
    progress: number;
    selectedStrategy: string;
}

// 动画事件
interface AnimationEvents {
    onPointAdded?: (point: SamplingPoint) => void;
    onUncertaintyChanged?: (reduction: number) => void;
    onAnimationComplete?: () => void;
}

export class UncertaintyHeatmapAnimation {
    private container: HTMLElement;
    private overlay: HTMLElement;
    private panel: HTMLElement;
    private heatmapCanvas: HTMLCanvasElement;
    private ctx: CanvasRenderingContext2D;
    private animationId: number | null = null;
    private animationState: AnimationState;
    private samplingPoints: SamplingPoint[] = [];
    private uncertaintyGrid: UncertaintyCell[][] = [];
    private gridSize = 50;
    private gridWidth = 800;
    private gridHeight = 600;
    private strategies: string[] = ['随机采样', '均匀采样', '自适应采样'];
    private strategyComparison: Map<string, SamplingPoint[]> = new Map();
    private events: AnimationEvents;
    private pulseRadius = 0;
    private cellSize = 0;

    constructor(container: HTMLElement | string, events?: AnimationEvents) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)!
            : container;
        this.events = events || {};
        this.animationState = {
            isPlaying: false,
            currentPoint: 0,
            totalPoints: 20,
            progress: 0,
            selectedStrategy: '自适应采样'
        };
        this.init();
    }

    private init(): void {
        this.createPanel();
        this.bindEvents();
        this.initializeUncertaintyGrid();
    }

    private createPanel(): void {
        // 创建遮罩层
        this.overlay = document.createElement('div');
        this.overlay.className = 'uncertainty-heatmap-overlay';
        this.overlay.style.display = 'none';

        // 创建热图动画面板
        this.panel = document.createElement('div');
        this.panel.className = 'uncertainty-heatmap-panel';
        this.panel.innerHTML = `
            <div class="uncertainty-heatmap-content">
                <div class="heatmap-header">
                    <h2 class="heatmap-title">不确定性热图可视化</h2>
                    <button class="btn btn-icon heatmap-close-btn" title="关闭">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>

                <div class="heatmap-body">
                    <!-- 热图画布 -->
                    <div class="heatmap-canvas-container">
                        <canvas id="uncertainty-heatmap-canvas" class="heatmap-canvas"></canvas>
                        <div class="heatmap-legend">
                            <div class="legend-item" data-level="very-high">
                                <div class="legend-color"></div>
                                <span class="legend-label">极高</span>
                            </div>
                            <div class="legend-item" data-level="high">
                                <div class="legend-color"></div>
                                <span class="legend-label">高</span>
                            </div>
                            <div class="legend-item" data-level="medium">
                                <div class="legend-color"></div>
                                <span class="legend-label">中</span>
                            </div>
                            <div class="legend-item" data-level="low">
                                <div class="legend-color"></div>
                                <span class="legend-label">低</span>
                            </div>
                            <div class="legend-item" data-level="very-low">
                                <div class="legend-color"></div>
                                <span class="legend-label">极低</span>
                            </div>
                        </div>
                    </div>

                    <!-- 采样策略选择 -->
                    <div class="strategy-selector">
                        <h3 class="strategy-title">采样策略</h3>
                        <div class="strategy-buttons">
                            ${this.strategies.map(strategy => `
                                <button class="btn btn-small strategy-btn ${strategy === this.animationState.selectedStrategy ? 'active' : ''}" data-strategy="${strategy}">
                                    ${strategy}
                                </button>
                            `).join('')}
                        </div>
                    </div>

                    <!-- 动画控制 -->
                    <div class="animation-controls">
                        <button class="btn btn-primary animation-play-btn" id="heatmap-play-btn">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                <polygon points="5,3 19,12 5,21"></polygon>
                            </svg>
                            开始采样
                        </button>
                        <button class="btn animation-pause-btn" id="heatmap-pause-btn" style="display: none;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                <rect x="6" y="4" width="4" height="16"></rect>
                                <rect x="14" y="4" width="4" height="16"></rect>
                            </svg>
                            暂停
                        </button>
                        <button class="btn animation-reset-btn" id="heatmap-reset-btn">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path>
                                <path d="M3 3v5h5"></path>
                            </svg>
                            重置
                        </button>
                        <button class="btn animation-compare-btn" id="heatmap-compare-btn">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <rect x="3" y="3" width="7" height="7"></rect>
                                <rect x="14" y="3" width="7" height="7"></rect>
                                <rect x="14" y="14" width="7" height="7"></rect>
                                <rect x="3" y="14" width="7" height="7"></rect>
                            </svg>
                            策略对比
                        </button>
                    </div>

                    <!-- 采样进度 -->
                    <div class="sampling-progress">
                        <div class="progress-info">
                            <span class="progress-label">采样进度：</span>
                            <span class="progress-value" id="sampling-progress-value">0 / 20</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="sampling-progress-fill" style="width: 0%"></div>
                        </div>
                        <div class="uncertainty-reduction">
                            <span class="reduction-label">不确定性降低：</span>
                            <span class="reduction-value" id="uncertainty-reduction-value">0%</span>
                        </div>
                    </div>

                    <!-- 采样点列表 -->
                    <div class="sampling-points-list">
                        <h3 class="points-list-title">采样点列表</h3>
                        <div class="points-list-container" id="points-list-container">
                            <!-- 采样点将在这里动态生成 -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.overlay.appendChild(this.panel);
        this.container.appendChild(this.overlay);

        // 初始化画布
        this.heatmapCanvas = this.panel.querySelector('#uncertainty-heatmap-canvas') as HTMLCanvasElement;
        this.ctx = this.heatmapCanvas.getContext('2d')!;
        this.resizeCanvas();
    }

    private bindEvents(): void {
        const closeBtn = this.panel.querySelector('.heatmap-close-btn') as HTMLElement;
        closeBtn.addEventListener('click', () => this.hide());

        const playBtn = this.panel.querySelector('#heatmap-play-btn') as HTMLElement;
        playBtn.addEventListener('click', () => this.play());

        const pauseBtn = this.panel.querySelector('#heatmap-pause-btn') as HTMLElement;
        pauseBtn.addEventListener('click', () => this.pause());

        const resetBtn = this.panel.querySelector('#heatmap-reset-btn') as HTMLElement;
        resetBtn.addEventListener('click', () => this.reset());

        const compareBtn = this.panel.querySelector('#heatmap-compare-btn') as HTMLElement;
        compareBtn.addEventListener('click', () => this.toggleComparison());

        const strategyBtns = this.panel.querySelectorAll('.strategy-btn');
        strategyBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const strategy = (e.target as HTMLElement).dataset.strategy!;
                this.selectStrategy(strategy);
            });
        });

        this.heatmapCanvas.addEventListener('click', (e) => this.handleCanvasClick(e));
        this.heatmapCanvas.addEventListener('mousemove', (e) => this.handleCanvasHover(e));

        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this.hide();
            }
        });

        window.addEventListener('resize', () => this.resizeCanvas());
    }

    private resizeCanvas(): void {
        const container = this.panel.querySelector('.heatmap-canvas-container') as HTMLElement;
        const rect = container.getBoundingClientRect();
        this.heatmapCanvas.width = rect.width;
        this.heatmapCanvas.height = rect.height;
        this.cellSize = this.heatmapCanvas.width / this.gridSize;
        this.render();
    }

    private initializeUncertaintyGrid(): void {
        this.uncertaintyGrid = [];
        for (let x = 0; x < this.gridSize; x++) {
            this.uncertaintyGrid[x] = [];
            for (let y = 0; y < this.gridSize; y++) {
                // 初始不确定性基于到中心的距离
                const centerX = this.gridSize / 2;
                const centerY = this.gridSize / 2;
                const distance = Math.sqrt(Math.pow(x - centerX, 2) + Math.pow(y - centerY, 2));
                const maxDistance = Math.sqrt(Math.pow(centerX, 2) + Math.pow(centerY, 2));
                const uncertainty = 0.5 + (distance / maxDistance) * 0.5;

                this.uncertaintyGrid[x][y] = {
                    x,
                    y,
                    uncertainty,
                    level: this.getUncertaintyLevel(uncertainty)
                };
            }
        }
    }

    private getUncertaintyLevel(uncertainty: number): UncertaintyLevel {
        if (uncertainty < 0.2) return 'very-low';
        if (uncertainty < 0.4) return 'low';
        if (uncertainty < 0.6) return 'medium';
        if (uncertainty < 0.8) return 'high';
        return 'very-high';
    }

    public show(): void {
        this.overlay.style.display = 'flex';
        this.resizeCanvas();
        this.reset();
    }

    public hide(): void {
        this.pause();
        this.overlay.style.display = 'none';
    }

    public play(): void {
        if (this.animationState.isPlaying) return;

        this.animationState.isPlaying = true;
        this.updateControlButtons();
        this.animate();
    }

    public pause(): void {
        this.animationState.isPlaying = false;
        this.updateControlButtons();
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }

    public reset(): void {
        this.pause();
        this.animationState.currentPoint = 0;
        this.animationState.progress = 0;
        this.samplingPoints = [];
        this.initializeUncertaintyGrid();
        this.updateUI();
        this.render();
        this.clearPointsList();
    }

    public selectStrategy(strategy: string): void {
        this.animationState.selectedStrategy = strategy;
        this.panel.querySelectorAll('.strategy-btn').forEach(btn => {
            btn.classList.toggle('active', (btn as HTMLElement).dataset.strategy === strategy);
        });
        this.reset();
    }

    private toggleComparison(): void {
        // 实现策略对比功能
        console.log('切换到策略对比模式');
    }

    private animate(): void {
        if (!this.animationState.isPlaying) return;

        this.animationId = requestAnimationFrame(() => this.animate());
        this.update();
    }

    private update(): void {
        if (this.animationState.currentPoint < this.animationState.totalPoints) {
            this.addSamplingPoint();
            this.animationState.currentPoint++;
            this.animationState.progress = (this.animationState.currentPoint / this.animationState.totalPoints) * 100;
            this.pulseRadius = 30; // 重置脉冲半径
        } else {
            this.animationState.isPlaying = false;
            this.updateControlButtons();
            if (this.events.onAnimationComplete) {
                this.events.onAnimationComplete();
            }
        }

        this.updateUI();
    }

    private addSamplingPoint(): void {
        const point = this.generateSamplingPoint();
        this.samplingPoints.push(point);
        this.updateUncertaintyGrid(point);
        this.addPointsListItem(point);

        if (this.events.onPointAdded) {
            this.events.onPointAdded(point);
        }
    }

    private generateSamplingPoint(): SamplingPoint {
        let x: number, y: number;

        switch (this.animationState.selectedStrategy) {
            case '随机采样':
                x = Math.random() * this.gridWidth;
                y = Math.random() * this.gridHeight;
                break;
            case '均匀采样':
                const cols = 5;
                const rows = 4;
                const col = this.animationState.currentPoint % cols;
                const row = Math.floor(this.animationState.currentPoint / cols);
                x = (col + 0.5) * (this.gridWidth / cols);
                y = (row + 0.5) * (this.gridHeight / rows);
                break;
            case '自适应采样':
            default:
                // 选择不确定性最高的区域
                const maxUncertaintyCell = this.findMaxUncertaintyCell();
                if (maxUncertaintyCell) {
                    x = maxUncertaintyCell.x * (this.gridWidth / this.gridSize);
                    y = maxUncertaintyCell.y * (this.gridHeight / this.gridSize);
                } else {
                    x = Math.random() * this.gridWidth;
                    y = Math.random() * this.gridHeight;
                }
                break;
        }

        const uncertainty = this.getCellUncertaintyAt(x, y);
        const value = Math.random() * 100;
        const level = this.getUncertaintyLevel(uncertainty);

        return {
            id: `point-${this.animationState.currentPoint}`,
            x,
            y,
            uncertainty,
            value,
            strategy: this.animationState.selectedStrategy,
            order: this.animationState.currentPoint + 1,
            level
        };
    }

    private findMaxUncertaintyCell(): UncertaintyCell | null {
        let maxCell: UncertaintyCell | null = null;
        let maxUncertainty = 0;

        for (let x = 0; x < this.gridSize; x++) {
            for (let y = 0; y < this.gridSize; y++) {
                const cell = this.uncertaintyGrid[x][y];
                if (cell.uncertainty > maxUncertainty) {
                    maxUncertainty = cell.uncertainty;
                    maxCell = cell;
                }
            }
        }

        return maxCell;
    }

    private getCellUncertaintyAt(x: number, y: number): number {
        const gridX = Math.floor((x / this.gridWidth) * this.gridSize);
        const gridY = Math.floor((y / this.gridHeight) * this.gridSize);

        if (gridX >= 0 && gridX < this.gridSize && gridY >= 0 && gridY < this.gridSize) {
            return this.uncertaintyGrid[gridX][gridY].uncertainty;
        }

        return 0;
    }

    private updateUncertaintyGrid(point: SamplingPoint): void {
        const influenceRadius = this.gridSize / 5;
        const gridX = Math.floor((point.x / this.gridWidth) * this.gridSize);
        const gridY = Math.floor((point.y / this.gridHeight) * this.gridSize);

        for (let x = Math.max(0, gridX - influenceRadius); x < Math.min(this.gridSize, gridX + influenceRadius); x++) {
            for (let y = Math.max(0, gridY - influenceRadius); y < Math.min(this.gridSize, gridY + influenceRadius); y++) {
                const distance = Math.sqrt(Math.pow(x - gridX, 2) + Math.pow(y - gridY, 2));
                const influence = Math.max(0, 1 - distance / influenceRadius);

                this.uncertaintyGrid[x][y].uncertainty *= (1 - influence * 0.5);
                this.uncertaintyGrid[x][y].level = this.getUncertaintyLevel(this.uncertaintyGrid[x][y].uncertainty);
            }
        }
    }

    private updateControlButtons(): void {
        const playBtn = this.panel.querySelector('#heatmap-play-btn') as HTMLElement;
        const pauseBtn = this.panel.querySelector('#heatmap-pause-btn') as HTMLElement;
        playBtn.style.display = this.animationState.isPlaying ? 'none' : 'block';
        pauseBtn.style.display = this.animationState.isPlaying ? 'block' : 'none';
    }

    private updateUI(): void {
        const progressValue = this.panel.querySelector('#sampling-progress-value') as HTMLElement;
        const progressFill = this.panel.querySelector('#sampling-progress-fill') as HTMLElement;
        const reductionValue = this.panel.querySelector('#uncertainty-reduction-value') as HTMLElement;

        progressValue.textContent = `${this.animationState.currentPoint} / ${this.animationState.totalPoints}`;
        progressFill.style.width = `${this.animationState.progress}%`;

        // 计算不确定性降低
        const totalUncertainty = this.calculateTotalUncertainty();
        const initialUncertainty = this.calculateInitialUncertainty();
        const reduction = initialUncertainty > 0 ? ((initialUncertainty - totalUncertainty) / initialUncertainty) * 100 : 0;
        reductionValue.textContent = `${reduction.toFixed(1)}%`;

        if (this.events.onUncertaintyChanged) {
            this.events.onUncertaintyChanged(reduction);
        }

        this.render();
    }

    private calculateTotalUncertainty(): number {
        let total = 0;
        for (let x = 0; x < this.gridSize; x++) {
            for (let y = 0; y < this.gridSize; y++) {
                total += this.uncertaintyGrid[x][y].uncertainty;
            }
        }
        return total / (this.gridSize * this.gridSize);
    }

    private calculateInitialUncertainty(): number {
        let total = 0;
        for (let x = 0; x < this.gridSize; x++) {
            for (let y = 0; y < this.gridSize; y++) {
                const centerX = this.gridSize / 2;
                const centerY = this.gridSize / 2;
                const distance = Math.sqrt(Math.pow(x - centerX, 2) + Math.pow(y - centerY, 2));
                const maxDistance = Math.sqrt(Math.pow(centerX, 2) + Math.pow(centerY, 2));
                total += 0.5 + (distance / maxDistance) * 0.5;
            }
        }
        return total / (this.gridSize * this.gridSize);
    }

    private addPointsListItem(point: SamplingPoint): void {
        const container = this.panel.querySelector('#points-list-container') as HTMLElement;
        const item = document.createElement('div');
        item.className = 'points-list-item';
        item.innerHTML = `
            <span class="point-order">${point.order}</span>
            <span class="point-coords">(${point.x.toFixed(0)}, ${point.y.toFixed(0)})</span>
            <span class="point-uncertainty level-${point.level}">${(point.uncertainty * 100).toFixed(1)}%</span>
        `;
        container.appendChild(item);
        container.scrollTop = container.scrollHeight;
    }

    private clearPointsList(): void {
        const container = this.panel.querySelector('#points-list-container') as HTMLElement;
        container.innerHTML = '';
    }

    private handleCanvasClick(e: MouseEvent): void {
        const rect = this.heatmapCanvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // 转换为网格坐标
        const gridX = Math.floor((x / this.heatmapCanvas.width) * this.gridSize);
        const gridY = Math.floor((y / this.heatmapCanvas.height) * this.gridSize);

        if (gridX >= 0 && gridX < this.gridSize && gridY >= 0 && gridY < this.gridSize) {
            const cell = this.uncertaintyGrid[gridX][gridY];
            console.log(`位置 (${gridX}, ${gridY}) 不确定性: ${(cell.uncertainty * 100).toFixed(1)}%`);
        }
    }

    private handleCanvasHover(e: MouseEvent): void {
        const rect = this.heatmapCanvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const gridX = Math.floor((x / this.heatmapCanvas.width) * this.gridSize);
        const gridY = Math.floor((y / this.heatmapCanvas.height) * this.gridSize);

        if (gridX >= 0 && gridX < this.gridSize && gridY >= 0 && gridY < this.gridSize) {
            const cell = this.uncertaintyGrid[gridX][gridY];
            this.heatmapCanvas.title = `位置: (${gridX}, ${gridY})\n不确定性: ${(cell.uncertainty * 100).toFixed(1)}%`;
        }
    }

    private render(): void {
        this.clearCanvas();
        this.renderHeatmap();
        this.renderSamplingPoints();
        this.renderPulseEffect();
    }

    private clearCanvas(): void {
        this.ctx.clearRect(0, 0, this.heatmapCanvas.width, this.heatmapCanvas.height);
    }

    private renderHeatmap(): void {
        for (let x = 0; x < this.gridSize; x++) {
            for (let y = 0; y < this.gridSize; y++) {
                const cell = this.uncertaintyGrid[x][y];
                const color = this.getUncertaintyColor(cell.level);

                this.ctx.fillStyle = color;
                this.ctx.fillRect(
                    x * this.cellSize,
                    y * this.cellSize,
                    this.cellSize + 1,
                    this.cellSize + 1
                );
            }
        }
    }

    private getUncertaintyColor(level: UncertaintyLevel): string {
        const colorMap: Record<UncertaintyLevel, string> = {
            'very-low': '#22c55e',   // 绿色
            'low': '#3b82f6',        // 蓝色
            'medium': '#f59e0b',     // 橙色
            'high': '#ef4444',       // 红色
            'very-high': '#991b1b'   // 深红色
        };
        return colorMap[level];
    }

    private renderSamplingPoints(): void {
        this.samplingPoints.forEach(point => {
            const x = (point.x / this.gridWidth) * this.heatmapCanvas.width;
            const y = (point.y / this.gridHeight) * this.heatmapCanvas.height;

            // 绘制点
            this.ctx.fillStyle = '#ffffff';
            this.ctx.strokeStyle = '#000000';
            this.ctx.lineWidth = 2;
            this.ctx.beginPath();
            this.ctx.arc(x, y, 6, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.stroke();

            // 绘制序号
            this.ctx.fillStyle = '#000000';
            this.ctx.font = 'bold 10px sans-serif';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            this.ctx.fillText(point.order.toString(), x, y);
        });
    }

    private renderPulseEffect(): void {
        if (this.samplingPoints.length > 0 && this.pulseRadius > 0) {
            const lastPoint = this.samplingPoints[this.samplingPoints.length - 1];
            const x = (lastPoint.x / this.gridWidth) * this.heatmapCanvas.width;
            const y = (lastPoint.y / this.gridHeight) * this.heatmapCanvas.height;

            this.ctx.strokeStyle = `rgba(255, 255, 255, ${this.pulseRadius / 30})`;
            this.ctx.lineWidth = 2;
            this.ctx.beginPath();
            this.ctx.arc(x, y, 30 - this.pulseRadius, 0, Math.PI * 2);
            this.ctx.stroke();

            this.pulseRadius -= 0.5;
        }
    }
}
