/**
 * 任务管理器
 * 统一管理所有后台任务的创建、执行、监控和管理
 */

import { Task, TaskType, TaskPriority, TaskStatus, TaskManagerOptions, TaskEvent, TaskExecutor, TaskStats } from '../../types/task-manager';
import { TaskQueue } from './TaskQueue';
import { TaskStorage } from './TaskStorage';
import { LocalNotifications } from '@capacitor/local-notifications';
import notificationManager from '../components/NotificationManager';

const DEFAULT_MANAGER_OPTIONS: TaskManagerOptions = {
    enablePersistence: true,
    enableNotifications: true,
    maxRetries: 3,
    taskTimeout: 300000 // 5分钟超时
};

export class TaskManager {
    private static instance: TaskManager;

    private queue: TaskQueue;
    private storage: TaskStorage;
    private options: TaskManagerOptions;
    private executors: Map<TaskType, TaskExecutor> = new Map();
    private eventListeners: Map<string, Set<Function>> = new Map();
    private isRunning: boolean = false;
    private processingInterval: number | null = null;

    private constructor(options?: Partial<TaskManagerOptions>) {
        this.options = { ...DEFAULT_MANAGER_OPTIONS, ...options };
        this.queue = new TaskQueue();
        this.storage = new TaskStorage();

        this.initialize();
    }

    /**
     * 获取单例实例
     */
    public static getInstance(options?: Partial<TaskManagerOptions>): TaskManager {
        if (!TaskManager.instance) {
            TaskManager.instance = new TaskManager(options);
        }
        return TaskManager.instance;
    }

    /**
     * 初始化
     */
    private async initialize(): Promise<void> {
        try {
            // 初始化存储
            if (this.options.enablePersistence) {
                await this.storage.initialize();

                // 加载未完成的任务
                await this.restoreTasks();
            }

            // 初始化本地通知
            if (this.options.enableNotifications) {
                await this.initializeNotifications();
            }

            // 启动任务处理循环
            this.startProcessing();

            console.log('[TaskManager] 初始化完成');
        } catch (error) {
            console.error('[TaskManager] 初始化失败:', error);
        }
    }

    /**
     * 初始化本地通知
     */
    private async initializeNotifications(): Promise<void> {
        try {
            // 请求通知权限
            const permission = await LocalNotifications.requestPermissions();

            if (permission.display !== 'granted') {
                console.warn('[TaskManager] 通知权限未授予');
                return;
            }

            // 监听通知点击事件
            await LocalNotifications.addListener('localNotificationActionPerformed', (action) => {
                console.log('[TaskManager] 通知被点击:', action);
                // 可以在这里处理通知点击事件
            });

            console.log('[TaskManager] 本地通知初始化完成');
        } catch (error) {
            console.error('[TaskManager] 本地通知初始化失败:', error);
        }
    }

    /**
     * 恢复未完成的任务
     */
    private async restoreTasks(): Promise<void> {
        try {
            const tasks = await this.storage.getAllTasks();

            for (const task of tasks) {
                if (task.status === 'pending' || task.status === 'running' || task.status === 'paused') {
                    // 重置运行中的任务为待处理
                    if (task.status === 'running') {
                        task.status = 'pending';
                    }

                    this.queue.addTask(task);
                    console.log(`[TaskManager] 恢复任务: ${task.id}`);
                }
            }

            console.log(`[TaskManager] 恢复了 ${tasks.length} 个任务`);
        } catch (error) {
            console.error('[TaskManager] 恢复任务失败:', error);
        }
    }

    /**
     * 注册任务执行器
     */
    public registerExecutor(type: TaskType, executor: TaskExecutor): void {
        this.executors.set(type, executor);
        console.log(`[TaskManager] 注册执行器: ${type}`);
    }

    /**
     * 创建任务
     */
    public async createTask(
        type: TaskType,
        name: string,
        data?: any,
        options?: {
            description?: string;
            priority?: TaskPriority;
            allowBackgroundExecution?: boolean;
            notifyOnCompletion?: boolean;
            estimatedDuration?: number;
        }
    ): Promise<Task> {
        const task: Task = {
            id: `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            type,
            name,
            description: options?.description,
            priority: options?.priority || 'normal',
            status: 'pending',
            progress: 0,
            createdAt: Date.now(),
            estimatedDuration: options?.estimatedDuration,
            data,
            retryCount: 0,
            maxRetries: this.options.maxRetries,
            allowBackgroundExecution: options?.allowBackgroundExecution ?? true,
            notifyOnCompletion: options?.notifyOnCompletion ?? true
        };

        // 添加到队列
        this.queue.addTask(task);

        // 持久化
        if (this.options.enablePersistence) {
            await this.storage.saveTask(task);
        }

        // 触发事件
        this.dispatchEvent('created', task);

        console.log(`[TaskManager] 创建任务: ${task.id} - ${name}`);
        return task;
    }

    /**
     * 启动任务处理循环
     */
    public startProcessing(): void {
        if (this.isRunning) return;

        this.isRunning = true;
        this.processingInterval = window.setInterval(() => {
            this.processNextTask();
        }, 1000);

        console.log('[TaskManager] 任务处理循环已启动');
    }

    /**
     * 停止任务处理循环
     */
    public stopProcessing(): void {
        if (!this.isRunning) return;

        this.isRunning = false;
        if (this.processingInterval) {
            clearInterval(this.processingInterval);
            this.processingInterval = null;
        }

        console.log('[TaskManager] 任务处理循环已停止');
    }

    /**
     * 处理下一个任务
     */
    private async processNextTask(): Promise<void> {
        if (!this.isRunning) return;

        const task = this.queue.getNextTask();
        if (!task) return;

        // 标记为运行中
        this.queue.markAsRunning(task.id);
        await this.storage.saveTask(task);
        this.dispatchEvent('started', task);

        // 执行任务
        try {
            await this.executeTask(task);
        } catch (error) {
            console.error(`[TaskManager] 任务执行失败: ${task.id}`, error);
            await this.handleTaskFailure(task, error);
        }
    }

    /**
     * 执行任务
     */
    private async executeTask(task: Task): Promise<void> {
        const executor = this.executors.get(task.type);
        if (!executor) {
            throw new Error(`没有找到任务类型 ${task.type} 的执行器`);
        }

        console.log(`[TaskManager] 开始执行任务: ${task.id}`);

        // 设置超时
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => {
                reject(new Error(`任务超时: ${this.options.taskTimeout}ms`));
            }, this.options.taskTimeout);
        });

        // 执行任务
        const result = await Promise.race([
            executor.execute(task, (progress) => {
                // 更新进度
                this.queue.updateProgress(task.id, progress);
                task.progress = progress;
                this.storage.saveTask(task);
                this.dispatchEvent('progress', task);
            }),
            timeoutPromise
        ]);

        // 标记为完成
        this.queue.markAsCompleted(task.id, result);
        await this.storage.saveTask(task);
        this.dispatchEvent('completed', task);

        // 发送通知
        if (task.notifyOnCompletion) {
            await this.sendCompletionNotification(task);
        }

        // 移动到历史记录
        await this.storage.moveToHistory(task);

        console.log(`[TaskManager] 任务完成: ${task.id}`);
    }

    /**
     * 处理任务失败
     */
    private async handleTaskFailure(task: Task, error: any): Promise<void> {
        const errorMessage = error?.message || String(error);

        // 检查是否可以重试
        if (task.retryCount < task.maxRetries) {
            task.retryCount++;
            task.status = 'pending';
            task.error = errorMessage;

            // 重新加入队列
            this.queue.addTask(task);
            await this.storage.saveTask(task);

            console.log(`[TaskManager] 任务失败，准备重试 (${task.retryCount}/${task.maxRetries}): ${task.id}`);
        } else {
            // 标记为失败
            this.queue.markAsFailed(task.id, errorMessage);
            await this.storage.saveTask(task);
            this.dispatchEvent('failed', task);

            // 发送失败通知
            if (task.notifyOnCompletion) {
                await this.sendFailureNotification(task, errorMessage);
            }

            // 移动到历史记录
            await this.storage.moveToHistory(task);

            console.error(`[TaskManager] 任务失败: ${task.id} - ${errorMessage}`);
        }
    }

    /**
     * 暂停任务
     */
    public async pauseTask(taskId: string): Promise<boolean> {
        const task = this.queue.getRunningTasks().find(t => t.id === taskId);
        if (!task) {
            console.warn(`[TaskManager] 未找到运行中的任务: ${taskId}`);
            return false;
        }

        this.queue.markAsPaused(taskId);
        await this.storage.saveTask(task);
        this.dispatchEvent('paused', task);

        console.log(`[TaskManager] 任务已暂停: ${taskId}`);
        return true;
    }

    /**
     * 恢复任务
     */
    public async resumeTask(taskId: string): Promise<boolean> {
        const success = this.queue.resumeTask(taskId);
        if (success) {
            const task = this.queue.getQueuedTasks().find(t => t.id === taskId);
            if (task) {
                await this.storage.saveTask(task);
                this.dispatchEvent('resumed', task);
                console.log(`[TaskManager] 任务已恢复: ${taskId}`);
            }
        }
        return success;
    }

    /**
     * 取消任务
     */
    public async cancelTask(taskId: string): Promise<boolean> {
        const task = this.queue.cancelTask(taskId);
        if (!task) {
            console.warn(`[TaskManager] 未找到任务: ${taskId}`);
            return false;
        }

        await this.storage.saveTask(task);
        await this.storage.moveToHistory(task);
        this.dispatchEvent('cancelled', task);

        console.log(`[TaskManager] 任务已取消: ${taskId}`);
        return true;
    }

    /**
     * 获取任务
     */
    public async getTask(taskId: string): Promise<Task | null> {
        let task = this.queue.getAllTasks().find(t => t.id === taskId);
        if (!task && this.options.enablePersistence) {
            task = await this.storage.getTask(taskId);
        }
        return task || null;
    }

    /**
     * 获取所有任务
     */
    public async getAllTasks(): Promise<Task[]> {
        const queueTasks = this.queue.getAllTasks();
        if (this.options.enablePersistence) {
            const storageTasks = await this.storage.getAllTasks();
            // 合并并去重
            const allTasks = new Map<string, Task>();
            queueTasks.forEach(t => allTasks.set(t.id, t));
            storageTasks.forEach(t => allTasks.set(t.id, t));
            return Array.from(allTasks.values());
        }
        return queueTasks;
    }

    /**
     * 获取任务历史
     */
    public async getTaskHistory(limit: number = 50): Promise<Task[]> {
        if (!this.options.enablePersistence) return [];
        return await this.storage.getTaskHistory(limit);
    }

    /**
     * 获取统计信息
     */
    public async getStats(): Promise<TaskStats> {
        const allTasks = await this.getAllTasks();
        const history = await this.getTaskHistory(1000);

        const stats: TaskStats = {
            total: allTasks.length,
            pending: 0,
            running: 0,
            paused: 0,
            completed: 0,
            failed: 0,
            cancelled: 0,
            avgDuration: 0,
            successRate: 0
        };

        // 统计当前任务
        allTasks.forEach(task => {
            stats[task.status]++;
        });

        // 统计历史任务
        const completedTasks = history.filter(t => t.status === 'completed');
        const failedTasks = history.filter(t => t.status === 'failed');

        stats.completed = completedTasks.length;
        stats.failed = failedTasks.length;

        // 计算平均时长
        if (completedTasks.length > 0) {
            const totalDuration = completedTasks.reduce((sum, task) => {
                const duration = (task.completedAt || 0) - (task.startedAt || 0);
                return sum + duration;
            }, 0);
            stats.avgDuration = totalDuration / completedTasks.length;
        }

        // 计算成功率
        const totalFinished = completedTasks.length + failedTasks.length;
        if (totalFinished > 0) {
            stats.successRate = (completedTasks.length / totalFinished) * 100;
        }

        return stats;
    }

    /**
     * 清空历史记录
     */
    public async clearHistory(): Promise<void> {
        if (!this.options.enablePersistence) return;
        await this.storage.clearHistory();
        console.log('[TaskManager] 历史记录已清空');
    }

    /**
     * 发送完成通知
     */
    private async sendCompletionNotification(task: Task): Promise<void> {
        try {
            // 使用 Capacitor 本地通知
            await LocalNotifications.schedule({
                notifications: [
                    {
                        id: parseInt(task.id.split('_')[1]) || Date.now(),
                        title: '任务完成',
                        body: `${task.name} 已成功完成`,
                        schedule: { at: new Date() },
                        sound: 'default',
                        smallIcon: 'ic_stat_icon_config_sample',
                        attachments: []
                    }
                ]
            });

            // 同时使用浏览器通知
            notificationManager.notifyTaskSuccess(task.id, task.name);
        } catch (error) {
            console.error('[TaskManager] 发送完成通知失败:', error);
        }
    }

    /**
     * 发送失败通知
     */
    private async sendFailureNotification(task: Task, error: string): Promise<void> {
        try {
            // 使用 Capacitor 本地通知
            await LocalNotifications.schedule({
                notifications: [
                    {
                        id: parseInt(task.id.split('_')[1]) || Date.now(),
                        title: '任务失败',
                        body: `${task.name} 执行失败: ${error}`,
                        schedule: { at: new Date() },
                        sound: 'default',
                        smallIcon: 'ic_stat_icon_config_sample',
                        attachments: []
                    }
                ]
            });

            // 同时使用浏览器通知
            notificationManager.notifyTaskFailure(task.id, task.name, error);
        } catch (error) {
            console.error('[TaskManager] 发送失败通知失败:', error);
        }
    }

    /**
     * 事件监听
     */
    public on(event: string, callback: Function): void {
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, new Set());
        }
        this.eventListeners.get(event)!.add(callback);
    }

    public off(event: string, callback: Function): void {
        const listeners = this.eventListeners.get(event);
        if (listeners) {
            listeners.delete(callback);
        }
    }

    private dispatchEvent(event: string, task: Task, data?: any): void {
        const taskEvent: TaskEvent = {
            type: event as any,
            taskId: task.id,
            task,
            timestamp: Date.now(),
            data
        };

        const listeners = this.eventListeners.get(event);
        if (listeners) {
            listeners.forEach(callback => callback(taskEvent));
        }
    }

    /**
     * 销毁管理器
     */
    public destroy(): void {
        this.stopProcessing();
        this.queue.clear();
        this.storage.close();
        this.eventListeners.clear();
        console.log('[TaskManager] 管理器已销毁');
    }
}

// 导出单例
export default TaskManager.getInstance();