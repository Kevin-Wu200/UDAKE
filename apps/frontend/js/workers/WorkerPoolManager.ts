import type {
    WorkerErrorMessage,
    WorkerOutgoingMessage,
    WorkerTaskOptions,
    WorkerTaskPriority,
    WorkerTaskType
} from './ComputeWorkerTypes.js';
import { WorkerTaskScheduler, type ScheduledTask } from './WorkerTaskScheduler.js';

interface WorkerSlot {
    id: number;
    worker: Worker;
    busy: boolean;
    taskId: string | null;
}

interface RunningTask<TResult = unknown> {
    resolve: (value: TResult) => void;
    reject: (reason?: unknown) => void;
    onProgress?: (progress: number, message?: string) => void;
    assignedWorkerId: number;
}

export interface WorkerPoolStats {
    workerCount: number;
    busyWorkers: number;
    queuedTasks: number;
    queuedByPriority: Record<WorkerTaskPriority, number>;
    runningTasks: number;
}

export class WorkerPoolManager {
    private static instance: WorkerPoolManager | null = null;
    private scheduler: WorkerTaskScheduler = new WorkerTaskScheduler();
    private workers: WorkerSlot[] = [];
    private runningTasks: Map<string, RunningTask> = new Map();
    private taskCounter = 0;
    private enabled: boolean;

    private constructor(workerCount?: number) {
        this.enabled = typeof window !== 'undefined' && 'Worker' in window;
        if (!this.enabled) {
            return;
        }

        const defaultWorkerCount = Math.max(
            1,
            Math.min(4, Math.floor((navigator.hardwareConcurrency || 4) / 2))
        );
        const count = Math.max(1, workerCount || defaultWorkerCount);
        this.createWorkers(count);
    }

    public static getInstance(workerCount?: number): WorkerPoolManager {
        if (!WorkerPoolManager.instance) {
            WorkerPoolManager.instance = new WorkerPoolManager(workerCount);
        }
        return WorkerPoolManager.instance;
    }

    public isEnabled(): boolean {
        return this.enabled && this.workers.length > 0;
    }

    public preload(): void {
        if (!this.isEnabled()) {
            return;
        }
        this.dispatch();
    }

    public runTask<TPayload = unknown, TResult = unknown>(
        type: WorkerTaskType,
        payload: TPayload,
        options: WorkerTaskOptions = {}
    ): Promise<TResult> {
        if (!this.isEnabled()) {
            return Promise.reject(new Error('当前环境不支持 WebWorker'));
        }

        const taskId = this.createTaskId(type);
        const priority = options.priority || 'normal';

        return new Promise<TResult>((resolve, reject) => {
            const scheduledTask: ScheduledTask<TPayload, TResult> = {
                id: taskId,
                type,
                payload,
                priority,
                createdAt: Date.now(),
                resolve,
                reject,
                onProgress: options.onProgress
            };

            this.scheduler.enqueue(scheduledTask);
            this.dispatch();
        });
    }

    public cancelTask(taskId: string): boolean {
        const queuedTask = this.scheduler.remove(taskId);
        if (queuedTask) {
            queuedTask.reject(new Error('任务已取消'));
            return true;
        }

        const runningTask = this.runningTasks.get(taskId);
        if (!runningTask) {
            return false;
        }

        const slot = this.workers.find((worker) => worker.id === runningTask.assignedWorkerId);
        if (!slot) {
            this.runningTasks.delete(taskId);
            runningTask.reject(new Error('任务已取消'));
            return true;
        }

        try {
            slot.worker.postMessage({ channel: 'cancel', id: taskId });
            slot.worker.terminate();
        } catch (error) {
            console.warn('[WorkerPoolManager] 取消任务失败:', error);
        } finally {
            this.runningTasks.delete(taskId);
            runningTask.reject(new Error('任务已取消'));
            this.recreateWorker(slot.id);
            this.dispatch();
        }

        return true;
    }

    public getStats(): WorkerPoolStats {
        const schedulerStats = this.scheduler.getStats();
        return {
            workerCount: this.workers.length,
            busyWorkers: this.workers.filter((worker) => worker.busy).length,
            queuedTasks: schedulerStats.queued,
            queuedByPriority: schedulerStats.byPriority,
            runningTasks: this.runningTasks.size
        };
    }

    public cleanup(): void {
        for (const slot of this.workers) {
            try {
                slot.worker.terminate();
            } catch (error) {
                console.warn('[WorkerPoolManager] 销毁 Worker 失败:', error);
            }
        }
        this.workers = [];
        this.runningTasks.clear();
    }

    private createWorkers(count: number): void {
        for (let i = 0; i < count; i += 1) {
            const slot = this.createWorkerSlot(i);
            if (slot) {
                this.workers.push(slot);
            }
        }
    }

    private createWorkerSlot(id: number): WorkerSlot | null {
        try {
            const worker = new Worker(new URL('./compute.worker.ts', import.meta.url), {
                type: 'module',
                name: `udake-worker-${id}`
            });
            const slot: WorkerSlot = {
                id,
                worker,
                busy: false,
                taskId: null
            };
            worker.onmessage = (event: MessageEvent<WorkerOutgoingMessage>) => {
                this.handleWorkerMessage(slot, event.data);
            };
            worker.onerror = (event: ErrorEvent) => {
                this.handleWorkerError(slot, event);
            };
            return slot;
        } catch (error) {
            console.warn('[WorkerPoolManager] 创建 Worker 失败:', error);
            return null;
        }
    }

    private recreateWorker(workerId: number): void {
        const index = this.workers.findIndex((worker) => worker.id === workerId);
        if (index === -1) {
            return;
        }

        const newSlot = this.createWorkerSlot(workerId);
        if (!newSlot) {
            this.workers.splice(index, 1);
            return;
        }
        this.workers[index] = newSlot;
    }

    private dispatch(): void {
        if (!this.isEnabled()) {
            return;
        }

        while (this.scheduler.hasPending()) {
            const idleWorker = this.workers.find((worker) => !worker.busy);
            if (!idleWorker) {
                break;
            }

            const task = this.scheduler.dequeue();
            if (!task) {
                break;
            }

            this.assignTask(idleWorker, task);
        }
    }

    private assignTask(slot: WorkerSlot, task: ScheduledTask): void {
        slot.busy = true;
        slot.taskId = task.id;

        this.runningTasks.set(task.id, {
            resolve: task.resolve,
            reject: task.reject,
            onProgress: task.onProgress,
            assignedWorkerId: slot.id
        });

        slot.worker.postMessage({
            channel: 'task',
            id: task.id,
            type: task.type,
            payload: task.payload
        });
    }

    private handleWorkerMessage(slot: WorkerSlot, message: WorkerOutgoingMessage): void {
        const runningTask = this.runningTasks.get(message.id);
        if (!runningTask) {
            return;
        }

        if (message.kind === 'progress') {
            runningTask.onProgress?.(message.progress, message.message);
            return;
        }

        this.runningTasks.delete(message.id);
        slot.busy = false;
        slot.taskId = null;

        if (message.kind === 'result') {
            runningTask.resolve(message.result);
        } else {
            runningTask.reject(new Error(message.error));
        }

        this.dispatch();
    }

    private handleWorkerError(slot: WorkerSlot, event: ErrorEvent | WorkerErrorMessage): void {
        const taskId = slot.taskId;
        const runningTask = taskId ? this.runningTasks.get(taskId) : null;

        if (taskId && runningTask) {
            this.runningTasks.delete(taskId);
            runningTask.reject(new Error('Worker 执行异常，任务已失败'));
        }

        slot.busy = false;
        slot.taskId = null;
        console.warn('[WorkerPoolManager] Worker 运行错误:', event);
        this.recreateWorker(slot.id);
        this.dispatch();
    }

    private createTaskId(type: WorkerTaskType): string {
        this.taskCounter += 1;
        return `${type}_${Date.now()}_${this.taskCounter}`;
    }
}

export default WorkerPoolManager;
