/**
 * 进度详情面板组件
 * 显示任务的详细进度信息，包括阶段进度、分块处理进度和预计剩余时间
 */

import { taskPollingService } from '../services/TaskPollingService';

interface StageInfo {
    stage: string;
    stage_name: string;
    progress: number;
    status: string;
    started_at?: string;
    completed_at?: string;
    duration?: number;
    message?: string;
}

interface BlockProgress {
    current_block: number;
    total_blocks: number;
    processed_blocks: number;
    processing_speed?: number;
    estimated_remaining_time?: number;
}

interface ProgressDetail {
    task_id: string;
    current_stage?: string;
    overall_progress: number;
    stages: StageInfo[];
    block_progress?: BlockProgress;
    estimated_total_time?: number;
    estimated_remaining_time?: number;
    elapsed_time?: number;
    updated_at: string;
}

export class ProgressDetailPanel {
    private container: HTMLElement;
    private overlay: HTMLElement;
    private panel: HTMLElement;
    private taskId: string | null = null;
    private pollingInterval: number | null = null;

    constructor(container: HTMLElement | string) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)!
            : container;
        this.init();
    }

    private init(): void {
        this.createPanel();
        this.bindEvents();
    }

    private createPanel(): void {
        // 创建遮罩层
        this.overlay = document.createElement('div');
        this.overlay.className = 'progress-detail-overlay';
        this.overlay.style.display = 'none';

        // 创建进度详情面板
        this.panel = document.createElement('div');
        this.panel.className = 'progress-detail-panel';
        this.panel.innerHTML = `
            <div class="progress-detail-content">
                <div class="progress-detail-header">
                    <h2 class="progress-detail-title">任务进度详情</h2>
                    <button class="btn btn-icon progress-detail-close-btn" title="关闭">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>

                <div class="progress-detail-body">
                    <!-- 总体进度 -->
                    <div class="progress-section">
                        <h3 class="progress-section-title">总体进度</h3>
                        <div class="overall-progress-container">
                            <div class="progress-bar-wrapper">
                                <div class="progress-bar">
                                    <div class="progress-bar-fill" id="overall-progress-fill" style="width: 0%"></div>
                                </div>
                                <span class="progress-percentage" id="overall-progress-percentage">0%</span>
                            </div>
                            <div class="progress-info">
                                <div class="progress-info-item">
                                    <span class="progress-info-label">已用时间：</span>
                                    <span class="progress-info-value" id="elapsed-time">0秒</span>
                                </div>
                                <div class="progress-info-item">
                                    <span class="progress-info-label">预计剩余：</span>
                                    <span class="progress-info-value" id="estimated-remaining-time">--</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 当前阶段 -->
                    <div class="progress-section">
                        <h3 class="progress-section-title">当前阶段</h3>
                        <div class="current-stage-container" id="current-stage-container">
                            <span class="current-stage-name" id="current-stage-name">--</span>
                            <span class="current-stage-status" id="current-stage-status">--</span>
                        </div>
                    </div>

                    <!-- 阶段流程图 -->
                    <div class="progress-section">
                        <h3 class="progress-section-title">阶段流程</h3>
                        <div class="stages-flow-container" id="stages-flow-container">
                            <!-- 阶段列表将在这里动态生成 -->
                        </div>
                    </div>

                    <!-- 分块处理进度 -->
                    <div class="progress-section" id="block-progress-section" style="display: none;">
                        <h3 class="progress-section-title">分块处理进度</h3>
                        <div class="block-progress-container">
                            <div class="block-progress-info">
                                <div class="block-progress-item">
                                    <span class="block-progress-label">当前块：</span>
                                    <span class="block-progress-value" id="current-block">0</span>
                                </div>
                                <div class="block-progress-item">
                                    <span class="block-progress-label">总块数：</span>
                                    <span class="block-progress-value" id="total-blocks">0</span>
                                </div>
                                <div class="block-progress-item">
                                    <span class="block-progress-label">已处理：</span>
                                    <span class="block-progress-value" id="processed-blocks">0</span>
                                </div>
                                <div class="block-progress-item">
                                    <span class="block-progress-label">处理速度：</span>
                                    <span class="block-progress-value" id="processing-speed">--</span>
                                </div>
                            </div>
                            <div class="block-progress-bar">
                                <div class="block-progress-fill" id="block-progress-fill" style="width: 0%"></div>
                            </div>
                        </div>
                    </div>

                    <!-- 阶段详情列表 -->
                    <div class="progress-section">
                        <h3 class="progress-section-title">阶段详情</h3>
                        <div class="stages-list-container" id="stages-list-container">
                            <!-- 阶段详情将在这里动态生成 -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.overlay.appendChild(this.panel);
        this.container.appendChild(this.overlay);
    }

    private bindEvents(): void {
        const closeBtn = this.panel.querySelector('.progress-detail-close-btn') as HTMLElement;
        closeBtn.addEventListener('click', () => this.hide());

        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this.hide();
            }
        });
    }

    public show(taskId: string): void {
        this.taskId = taskId;
        this.overlay.style.display = 'flex';
        this.startPolling();
    }

    public hide(): void {
        this.stopPolling();
        this.overlay.style.display = 'none';
        this.taskId = null;
    }

    private startPolling(): void {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }

        this.updateProgressDetail(); // 立即更新一次

        this.pollingInterval = window.setInterval(() => {
            this.updateProgressDetail();
        }, 2000); // 每2秒更新一次
    }

    private stopPolling(): void {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }

    private async updateProgressDetail(): Promise<void> {
        if (!this.taskId) return;

        try {
            const response = await fetch(`/api/progress-detail/${this.taskId}`);
            if (!response.ok) {
                throw new Error('获取进度详情失败');
            }

            const data: ProgressDetail = await response.json();
            this.updateUI(data);
        } catch (error) {
            console.error('更新进度详情失败:', error);
        }
    }

    private updateUI(data: ProgressDetail): void {
        // 更新总体进度
        this.updateOverallProgress(data);

        // 更新当前阶段
        this.updateCurrentStage(data);

        // 更新阶段流程图
        this.updateStagesFlow(data);

        // 更新分块处理进度
        this.updateBlockProgress(data);

        // 更新阶段详情列表
        this.updateStagesList(data);
    }

    private updateOverallProgress(data: ProgressDetail): void {
        const fill = document.getElementById('overall-progress-fill') as HTMLElement;
        const percentage = document.getElementById('overall-progress-percentage') as HTMLElement;
        const elapsedTime = document.getElementById('elapsed-time') as HTMLElement;
        const estimatedTime = document.getElementById('estimated-remaining-time') as HTMLElement;

        fill.style.width = `${data.overall_progress}%`;
        percentage.textContent = `${Math.round(data.overall_progress)}%`;

        if (data.elapsed_time) {
            elapsedTime.textContent = this.formatTime(data.elapsed_time);
        }

        if (data.estimated_remaining_time) {
            estimatedTime.textContent = this.formatTime(data.estimated_remaining_time);
        } else {
            estimatedTime.textContent = '--';
        }
    }

    private updateCurrentStage(data: ProgressDetail): void {
        const name = document.getElementById('current-stage-name') as HTMLElement;
        const status = document.getElementById('current-stage-status') as HTMLElement;

        if (data.current_stage) {
            const currentStageInfo = data.stages.find(s => s.stage === data.current_stage);
            if (currentStageInfo) {
                name.textContent = currentStageInfo.stage_name;
                status.textContent = this.getStatusText(currentStageInfo.status);
                status.className = `current-stage-status status-${currentStageInfo.status}`;
            }
        } else {
            name.textContent = '--';
            status.textContent = '--';
        }
    }

    private updateStagesFlow(data: ProgressDetail): void {
        const container = document.getElementById('stages-flow-container') as HTMLElement;
        container.innerHTML = '';

        data.stages.forEach((stage, index) => {
            const stageElement = document.createElement('div');
            stageElement.className = `stage-flow-item status-${stage.status}`;

            if (index < data.stages.length - 1) {
                stageElement.classList.add('has-arrow');
            }

            stageElement.innerHTML = `
                <div class="stage-flow-icon">${this.getStageIcon(stage.status)}</div>
                <div class="stage-flow-name">${stage.stage_name}</div>
                <div class="stage-flow-progress">${Math.round(stage.progress)}%</div>
            `;

            container.appendChild(stageElement);
        });
    }

    private updateBlockProgress(data: ProgressDetail): void {
        const section = document.getElementById('block-progress-section') as HTMLElement;

        if (data.block_progress) {
            section.style.display = 'block';

            const currentBlock = document.getElementById('current-block') as HTMLElement;
            const totalBlocks = document.getElementById('total-blocks') as HTMLElement;
            const processedBlocks = document.getElementById('processed-blocks') as HTMLElement;
            const processingSpeed = document.getElementById('processing-speed') as HTMLElement;
            const fill = document.getElementById('block-progress-fill') as HTMLElement;

            currentBlock.textContent = data.block_progress.current_block.toString();
            totalBlocks.textContent = data.block_progress.total_blocks.toString();
            processedBlocks.textContent = data.block_progress.processed_blocks.toString();

            if (data.block_progress.processing_speed) {
                processingSpeed.textContent = `${data.block_progress.processing_speed.toFixed(2)} 块/秒`;
            } else {
                processingSpeed.textContent = '--';
            }

            const blockProgress = (data.block_progress.processed_blocks / data.block_progress.total_blocks) * 100;
            fill.style.width = `${blockProgress}%`;
        } else {
            section.style.display = 'none';
        }
    }

    private updateStagesList(data: ProgressDetail): void {
        const container = document.getElementById('stages-list-container') as HTMLElement;
        container.innerHTML = '';

        data.stages.forEach(stage => {
            const stageItem = document.createElement('div');
            stageItem.className = `stage-list-item status-${stage.status}`;

            stageItem.innerHTML = `
                <div class="stage-list-header">
                    <span class="stage-list-name">${stage.stage_name}</span>
                    <span class="stage-list-status">${this.getStatusText(stage.status)}</span>
                </div>
                <div class="stage-list-progress-bar">
                    <div class="stage-list-progress-fill" style="width: ${stage.progress}%"></div>
                </div>
                <div class="stage-list-details">
                    <span class="stage-list-progress-text">${Math.round(stage.progress)}%</span>
                    ${stage.duration ? `<span class="stage-list-duration">耗时: ${this.formatTime(stage.duration)}</span>` : ''}
                </div>
                ${stage.message ? `<div class="stage-list-message">${stage.message}</div>` : ''}
            `;

            container.appendChild(stageItem);
        });
    }

    private formatTime(seconds: number): string {
        if (seconds < 60) {
            return `${Math.round(seconds)}秒`;
        } else if (seconds < 3600) {
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = Math.round(seconds % 60);
            return `${minutes}分${remainingSeconds}秒`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            return `${hours}小时${minutes}分`;
        }
    }

    private getStatusText(status: string): string {
        const statusMap: Record<string, string> = {
            'pending': '等待中',
            'running': '进行中',
            'completed': '已完成',
            'failed': '失败'
        };
        return statusMap[status] || status;
    }

    private getStageIcon(status: string): string {
        const iconMap: Record<string, string> = {
            'pending': '○',
            'running': '⟳',
            'completed': '✓',
            'failed': '✗'
        };
        return iconMap[status] || '○';
    }
}