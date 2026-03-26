/**
 * 任务管理面板
 * 显示任务列表、详情和操作按钮
 */

import { Task, TaskStatus, TaskPriority } from '../../types/task-manager';
import TaskManager from '../managers/TaskManager';
import { I18nDialog } from './I18nDialog.js';

export class TaskManagementPanel {
    private container: HTMLElement;
    private taskManager: any;
    private currentTab: 'active' | 'history' = 'active';
    private selectedTask: Task | null = null;

    constructor(container: HTMLElement) {
        this.container = container;
        this.taskManager = (TaskManager as any).getInstance();
        this.render();
        this.setupEventListeners();
    }

    /**
     * 渲染面板
     */
    private render(): void {
        this.container.innerHTML = `
            <div class="task-management-panel">
                <div class="task-panel-header">
                    <h2>任务管理</h2>
                    <div class="task-tabs">
                        <button class="task-tab active" data-tab="active">
                            <span class="tab-icon">📋</span>
                            <span class="tab-label">当前任务</span>
                            <span class="task-count" id="active-task-count">0</span>
                        </button>
                        <button class="task-tab" data-tab="history">
                            <span class="tab-icon">📜</span>
                            <span class="tab-label">历史记录</span>
                            <span class="task-count" id="history-task-count">0</span>
                        </button>
                    </div>
                    <button class="clear-history-btn" id="clear-history-btn">
                        🗑️ 清空历史
                    </button>
                </div>

                <div class="task-stats" id="task-stats">
                    <!-- 统计信息将在这里动态显示 -->
                </div>

                <div class="task-content">
                    <div class="task-list" id="task-list">
                        <!-- 任务列表将在这里动态显示 -->
                    </div>

                    <div class="task-details" id="task-details">
                        <div class="task-details-empty">
                            <p>选择一个任务查看详情</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.loadTasks();
    }

    /**
     * 设置事件监听
     */
    private setupEventListeners(): void {
        // 标签切换
        const tabs = this.container.querySelectorAll('.task-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.currentTab = (tab as HTMLElement).dataset.tab as 'active' | 'history';
                this.loadTasks();
            });
        });

        // 清空历史
        const clearHistoryBtn = this.container.querySelector('#clear-history-btn') as HTMLElement;
        clearHistoryBtn.addEventListener('click', () => {
            this.clearHistory();
        });

        // 任务管理器事件监听
        this.taskManager.on('created', () => this.loadTasks());
        this.taskManager.on('started', () => this.loadTasks());
        this.taskManager.on('progress', () => this.updateTaskProgress());
        this.taskManager.on('completed', () => this.loadTasks());
        this.taskManager.on('failed', () => this.loadTasks());
        this.taskManager.on('cancelled', () => this.loadTasks());
        this.taskManager.on('paused', () => this.loadTasks());
        this.taskManager.on('resumed', () => this.loadTasks());
    }

    /**
     * 加载任务
     */
    private async loadTasks(): Promise<void> {
        if (this.currentTab === 'active') {
            const tasks = await this.taskManager.getAllTasks();
            this.renderTaskList(tasks.filter((t: Task) =>
                ['pending', 'running', 'paused'].includes(t.status)
            ));
            (this.container.querySelector('#active-task-count') as HTMLElement).textContent =
                tasks.filter((t: Task) => ['pending', 'running', 'paused'].includes(t.status)).length.toString();
        } else {
            const history = await this.taskManager.getTaskHistory();
            this.renderTaskList(history);
            (this.container.querySelector('#history-task-count') as HTMLElement).textContent =
                history.length.toString();
        }

        this.updateStats();
    }

    /**
     * 渲染任务列表
     */
    private renderTaskList(tasks: Task[]): void {
        const taskList = this.container.querySelector('#task-list') as HTMLElement;

        if (tasks.length === 0) {
            taskList.innerHTML = `
                <div class="task-list-empty">
                    <p>${this.currentTab === 'active' ? '暂无运行中的任务' : '暂无历史记录'}</p>
                </div>
            `;
            return;
        }

        taskList.innerHTML = tasks.map(task => `
            <div class="task-item ${task.status} ${task.id === this.selectedTask?.id ? 'selected' : ''}"
                 data-task-id="${task.id}">
                <div class="task-item-header">
                    <span class="task-type-icon">${this.getTaskTypeIcon(task.type)}</span>
                    <span class="task-name">${task.name}</span>
                    <span class="task-status ${task.status}">${this.getStatusLabel(task.status)}</span>
                </div>
                <div class="task-item-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${task.progress}%"></div>
                    </div>
                    <span class="progress-text">${task.progress}%</span>
                </div>
                <div class="task-item-meta">
                    <span class="task-priority ${task.priority}">${task.priority}</span>
                    <span class="task-time">${this.formatTime(task.createdAt)}</span>
                </div>
                <div class="task-actions">
                    ${this.renderTaskActions(task)}
                </div>
            </div>
        `).join('');

        // 添加点击事件
        taskList.querySelectorAll('.task-item').forEach(item => {
            item.addEventListener('click', async (e) => {
                const taskId = (item as HTMLElement).dataset.taskId;
                if (taskId && !(e.target as HTMLElement).closest('.task-action-btn')) {
                    await this.selectTask(taskId);
                }
            });
        });

        // 添加操作按钮事件
        taskList.querySelectorAll('.task-action-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const taskId = (btn as HTMLElement).dataset.taskId;
                const action = (btn as HTMLElement).dataset.action;
                if (taskId && action) {
                    await this.executeTaskAction(taskId, action);
                }
            });
        });
    }

    /**
     * 渲染任务操作按钮
     */
    private renderTaskActions(task: Task): string {
        const actions = [];

        if (task.status === 'running') {
            actions.push(`<button class="task-action-btn" data-task-id="${task.id}" data-action="pause">⏸️ 暂停</button>`);
        }

        if (task.status === 'paused') {
            actions.push(`<button class="task-action-btn" data-task-id="${task.id}" data-action="resume">▶️ 恢复</button>`);
        }

        if (['pending', 'paused'].includes(task.status)) {
            actions.push(`<button class="task-action-btn" data-task-id="${task.id}" data-action="cancel">❌ 取消</button>`);
        }

        if (task.status === 'failed' && task.retryCount < task.maxRetries) {
            actions.push(`<button class="task-action-btn" data-task-id="${task.id}" data-action="retry">🔄 重试</button>`);
        }

        return actions.join('');
    }

    /**
     * 选择任务
     */
    private async selectTask(taskId: string): Promise<void> {
        const task = await this.taskManager.getTask(taskId);
        if (!task) return;

        this.selectedTask = task;
        this.renderTaskDetails(task);

        // 更新选中状态
        this.container.querySelectorAll('.task-item').forEach(item => {
            item.classList.toggle('selected', (item as HTMLElement).dataset.taskId === taskId);
        });
    }

    /**
     * 渲染任务详情
     */
    private renderTaskDetails(task: Task): void {
        const detailsContainer = this.container.querySelector('#task-details') as HTMLElement;

        detailsContainer.innerHTML = `
            <div class="task-details-content">
                <div class="task-details-header">
                    <h3>${task.name}</h3>
                    <span class="task-status ${task.status}">${this.getStatusLabel(task.status)}</span>
                </div>

                <div class="task-details-section">
                    <h4>基本信息</h4>
                    <div class="detail-row">
                        <span class="detail-label">任务ID:</span>
                        <span class="detail-value">${task.id}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">类型:</span>
                        <span class="detail-value">${task.type}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">优先级:</span>
                        <span class="detail-value ${task.priority}">${task.priority}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">创建时间:</span>
                        <span class="detail-value">${this.formatDateTime(task.createdAt)}</span>
                    </div>
                    ${task.startedAt ? `
                    <div class="detail-row">
                        <span class="detail-label">开始时间:</span>
                        <span class="detail-value">${this.formatDateTime(task.startedAt)}</span>
                    </div>
                    ` : ''}
                    ${task.completedAt ? `
                    <div class="detail-row">
                        <span class="detail-label">完成时间:</span>
                        <span class="detail-value">${this.formatDateTime(task.completedAt)}</span>
                    </div>
                    ` : ''}
                    ${task.estimatedDuration ? `
                    <div class="detail-row">
                        <span class="detail-label">预计时长:</span>
                        <span class="detail-value">${this.formatDuration(task.estimatedDuration)}</span>
                    </div>
                    ` : ''}
                </div>

                <div class="task-details-section">
                    <h4>进度</h4>
                    <div class="progress-bar-large">
                        <div class="progress-fill" style="width: ${task.progress}%"></div>
                    </div>
                    <span class="progress-text-large">${task.progress}%</span>
                </div>

                ${task.description ? `
                <div class="task-details-section">
                    <h4>描述</h4>
                    <p class="task-description">${task.description}</p>
                </div>
                ` : ''}

                ${task.error ? `
                <div class="task-details-section">
                    <h4>错误信息</h4>
                    <div class="task-error">${task.error}</div>
                </div>
                ` : ''}

                <div class="task-details-section">
                    <h4>操作</h4>
                    <div class="task-details-actions">
                        ${this.renderDetailActions(task)}
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * 渲染详情操作按钮
     */
    private renderDetailActions(task: Task): string {
        const actions = [];

        if (task.status === 'running') {
            actions.push(`<button class="task-action-btn primary" data-task-id="${task.id}" data-action="pause">⏸️ 暂停任务</button>`);
        }

        if (task.status === 'paused') {
            actions.push(`<button class="task-action-btn primary" data-task-id="${task.id}" data-action="resume">▶️ 恢复任务</button>`);
        }

        if (['pending', 'paused'].includes(task.status)) {
            actions.push(`<button class="task-action-btn danger" data-task-id="${task.id}" data-action="cancel">❌ 取消任务</button>`);
        }

        if (task.status === 'failed') {
            actions.push(`<button class="task-action-btn primary" data-task-id="${task.id}" data-action="retry">🔄 重试任务</button>`);
        }

        if (task.status === 'completed' && task.result) {
            actions.push(`<button class="task-action-btn success" data-task-id="${task.id}" data-action="view-result">📊 查看结果</button>`);
        }

        return actions.join('');
    }

    /**
     * 执行任务操作
     */
    private async executeTaskAction(taskId: string, action: string): Promise<void> {
        switch (action) {
            case 'pause':
                await this.taskManager.pauseTask(taskId);
                break;
            case 'resume':
                await this.taskManager.resumeTask(taskId);
                break;
            case 'cancel':
                await this.taskManager.cancelTask(taskId);
                break;
            case 'retry':
                const task = await this.taskManager.getTask(taskId);
                if (task) {
                    task.status = 'pending';
                    task.retryCount = 0;
                    task.error = undefined;
                    await this.taskManager.resumeTask(taskId);
                }
                break;
            case 'view-result':
                await this.viewTaskResult(taskId);
                break;
        }

        await this.loadTasks();
        if (this.selectedTask?.id === taskId) {
            await this.selectTask(taskId);
        }
    }

    /**
     * 查看任务结果
     */
    private async viewTaskResult(taskId: string): Promise<void> {
        const task = await this.taskManager.getTask(taskId);
        if (!task || !task.result) return;

        console.log('任务结果:', task.result);
        // 这里可以实现结果显示逻辑
        I18nDialog.alert('dialog.task.result', {
            result: JSON.stringify(task.result, null, 2)
        });
    }

    /**
     * 更新任务进度
     */
    private async updateTaskProgress(): Promise<void> {
        const taskItems = this.container.querySelectorAll('.task-item');
        taskItems.forEach(async (item) => {
            const taskId = (item as HTMLElement).dataset.taskId;
            if (!taskId) return;

            const task = await this.taskManager.getTask(taskId);
            if (!task) return;

            // 更新进度条
            const progressFill = item.querySelector('.progress-fill') as HTMLElement;
            const progressText = item.querySelector('.progress-text') as HTMLElement;
            if (progressFill) progressFill.style.width = `${task.progress}%`;
            if (progressText) progressText.textContent = `${task.progress}%`;

            // 更新状态
            const statusElement = item.querySelector('.task-status') as HTMLElement;
            if (statusElement) {
                statusElement.textContent = this.getStatusLabel(task.status);
                statusElement.className = `task-status ${task.status}`;
            }

            // 如果是当前选中的任务，更新详情
            if (this.selectedTask?.id === taskId) {
                await this.selectTask(taskId);
            }
        });
    }

    /**
     * 更新统计信息
     */
    private async updateStats(): Promise<void> {
        const stats = await this.taskManager.getStats();
        const statsContainer = this.container.querySelector('#task-stats') as HTMLElement;

        statsContainer.innerHTML = `
            <div class="stat-item">
                <span class="stat-label">待处理</span>
                <span class="stat-value pending">${stats.pending}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">运行中</span>
                <span class="stat-value running">${stats.running}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">已完成</span>
                <span class="stat-value completed">${stats.completed}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">失败</span>
                <span class="stat-value failed">${stats.failed}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">成功率</span>
                <span class="stat-value success">${stats.successRate.toFixed(1)}%</span>
            </div>
        `;
    }

    /**
     * 清空历史
     */
    private async clearHistory(): Promise<void> {
        if (I18nDialog.confirm('dialog.task.clearHistoryConfirm')) {
            await this.taskManager.clearHistory();
            await this.loadTasks();
        }
    }

    /**
     * 获取任务类型图标
     */
    private getTaskTypeIcon(type: string): string {
        const icons: Record<string, string> = {
            'interpolation': '📈',
            'sampling': '📍',
            'analysis': '🔬',
            'export': '📤',
            'import': '📥',
            'custom': '⚙️'
        };
        return icons[type] || '📋';
    }

    /**
     * 获取状态标签
     */
    private getStatusLabel(status: TaskStatus): string {
        const labels: Record<TaskStatus, string> = {
            'pending': '待处理',
            'running': '运行中',
            'paused': '已暂停',
            'completed': '已完成',
            'failed': '失败',
            'cancelled': '已取消'
        };
        return labels[status] || status;
    }

    /**
     * 格式化时间
     */
    private formatTime(timestamp: number): string {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now.getTime() - date.getTime();

        if (diff < 60000) return '刚刚';
        if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
        return `${Math.floor(diff / 86400000)} 天前`;
    }

    /**
     * 格式化日期时间
     */
    private formatDateTime(timestamp: number): string {
        const date = new Date(timestamp);
        return date.toLocaleString('zh-CN');
    }

    /**
     * 格式化时长
     */
    private formatDuration(milliseconds: number): string {
        const seconds = Math.floor(milliseconds / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);

        if (hours > 0) return `${hours} 小时 ${minutes % 60} 分钟`;
        if (minutes > 0) return `${minutes} 分钟`;
        return `${seconds} 秒`;
    }

    /**
     * 销毁面板
     */
    public destroy(): void {
        this.container.innerHTML = '';
    }
}

export default TaskManagementPanel;
