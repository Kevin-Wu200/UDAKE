/**
 * 任务队列管理器
 * 实现任务的优先级队列管理
 */

import { Task, TaskPriority, TaskQueueOptions } from '../../types/task-manager';

const DEFAULT_QUEUE_OPTIONS: TaskQueueOptions = {
    maxConcurrentTasks: 2,
    maxQueueSize: 100,
    priorityOrder: ['urgent', 'high', 'normal', 'low']
};

export class TaskQueue {
    private queue: Map<string, Task> = new Map();
    private runningTasks: Map<string, Task> = new Map();
    private options: TaskQueueOptions;

    constructor(options?: Partial<TaskQueueOptions>) {
        this.options = { ...DEFAULT_QUEUE_OPTIONS, ...options };
    }

    /**
     * 添加任务到队列
     */
    addTask(task: Task): boolean {
        // 检查队列大小限制
        if (this.queue.size >= this.options.maxQueueSize) {
            console.warn('[TaskQueue] 队列已满，无法添加新任务');
            return false;
        }

        // 检查是否已存在
        if (this.queue.has(task.id) || this.runningTasks.has(task.id)) {
            console.warn(`[TaskQueue] 任务 ${task.id} 已存在`);
            return false;
        }

        this.queue.set(task.id, task);
        console.log(`[TaskQueue] 任务 ${task.id} 已添加到队列，当前队列大小: ${this.queue.size}`);
        return true;
    }

    /**
     * 从队列移除任务
     */
    removeTask(taskId: string): Task | null {
        const task = this.queue.get(taskId);
        if (task) {
            this.queue.delete(taskId);
            console.log(`[TaskQueue] 任务 ${taskId} 已从队列移除`);
            return task;
        }
        return null;
    }

    /**
     * 获取下一个待执行任务
     */
    getNextTask(): Task | null {
        if (this.queue.size === 0) {
            return null;
        }

        // 检查是否达到最大并发数
        if (this.runningTasks.size >= this.options.maxConcurrentTasks) {
            return null;
        }

        // 按优先级获取任务
        for (const priority of this.options.priorityOrder) {
            for (const [id, task] of this.queue.entries()) {
                if (task.priority === priority && task.status === 'pending') {
                    // 从队列移除并添加到运行队列
                    this.queue.delete(id);
                    this.runningTasks.set(id, task);
                    return task;
                }
            }
        }

        return null;
    }

    /**
     * 标记任务为运行中
     */
    markAsRunning(taskId: string): void {
        const task = this.runningTasks.get(taskId);
        if (task) {
            task.status = 'running';
            task.startedAt = Date.now();
        }
    }

    /**
     * 标记任务为已完成
     */
    markAsCompleted(taskId: string, result?: any): void {
        const task = this.runningTasks.get(taskId);
        if (task) {
            task.status = 'completed';
            task.completedAt = Date.now();
            task.result = result;
            task.progress = 100;
            this.runningTasks.delete(taskId);
        }
    }

    /**
     * 标记任务为失败
     */
    markAsFailed(taskId: string, error: string): void {
        const task = this.runningTasks.get(taskId);
        if (task) {
            task.status = 'failed';
            task.completedAt = Date.now();
            task.error = error;
            this.runningTasks.delete(taskId);
        }
    }

    /**
     * 标记任务为暂停
     */
    markAsPaused(taskId: string): void {
        const task = this.runningTasks.get(taskId);
        if (task) {
            task.status = 'paused';
            this.runningTasks.delete(taskId);
            this.queue.set(taskId, task);
        }
    }

    /**
     * 恢复任务
     */
    resumeTask(taskId: string): boolean {
        const task = this.queue.get(taskId);
        if (task && task.status === 'paused') {
            task.status = 'pending';
            return true;
        }
        return false;
    }

    /**
     * 取消任务
     */
    cancelTask(taskId: string): Task | null {
        // 检查运行中的任务
        const runningTask = this.runningTasks.get(taskId);
        if (runningTask) {
            runningTask.status = 'cancelled';
            runningTask.completedAt = Date.now();
            this.runningTasks.delete(taskId);
            return runningTask;
        }

        // 检查队列中的任务
        const queuedTask = this.queue.get(taskId);
        if (queuedTask) {
            queuedTask.status = 'cancelled';
            queuedTask.completedAt = Date.now();
            this.queue.delete(taskId);
            return queuedTask;
        }

        return null;
    }

    /**
     * 获取队列中的所有任务
     */
    getQueuedTasks(): Task[] {
        return Array.from(this.queue.values());
    }

    /**
     * 获取运行中的所有任务
     */
    getRunningTasks(): Task[] {
        return Array.from(this.runningTasks.values());
    }

    /**
     * 获取所有任务
     */
    getAllTasks(): Task[] {
        return [...this.getQueuedTasks(), ...this.getRunningTasks()];
    }

    /**
     * 获取队列大小
     */
    getQueueSize(): number {
        return this.queue.size;
    }

    /**
     * 获取运行中任务数
     */
    getRunningCount(): number {
        return this.runningTasks.size;
    }

    /**
     * 清空队列
     */
    clear(): void {
        this.queue.clear();
        this.runningTasks.clear();
    }

    /**
     * 更新任务优先级
     */
    updatePriority(taskId: string, newPriority: TaskPriority): boolean {
        const task = this.queue.get(taskId);
        if (task) {
            task.priority = newPriority;
            return true;
        }
        return false;
    }

    /**
     * 更新任务进度
     */
    updateProgress(taskId: string, progress: number): void {
        const task = this.runningTasks.get(taskId);
        if (task) {
            task.progress = Math.max(0, Math.min(100, progress));
        }
    }

    /**
     * 获取队列统计
     */
    getStats(): {
        queued: number;
        running: number;
        byPriority: Record<TaskPriority, number>;
    } {
        const allTasks = this.getAllTasks();

        const byPriority: Record<TaskPriority, number> = {
            low: 0,
            normal: 0,
            high: 0,
            urgent: 0
        };

        allTasks.forEach(task => {
            byPriority[task.priority]++;
        });

        return {
            queued: this.queue.size,
            running: this.runningTasks.size,
            byPriority
        };
    }
}

export default TaskQueue;