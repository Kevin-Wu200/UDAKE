import type { WorkerTaskPriority, WorkerTaskType } from './ComputeWorkerTypes.js';

const PRIORITY_ORDER: WorkerTaskPriority[] = ['urgent', 'high', 'normal', 'low'];

export interface ScheduledTask<TPayload = unknown, TResult = unknown> {
    id: string;
    type: WorkerTaskType;
    payload: TPayload;
    priority: WorkerTaskPriority;
    createdAt: number;
    resolve: (value: TResult) => void;
    reject: (reason?: unknown) => void;
    onProgress?: (progress: number, message?: string) => void;
}

export interface SchedulerStats {
    queued: number;
    byPriority: Record<WorkerTaskPriority, number>;
}

export class WorkerTaskScheduler {
    private queues: Map<WorkerTaskPriority, ScheduledTask<any, any>[]> = new Map(
        PRIORITY_ORDER.map((priority) => [priority, []] as const)
    );

    public enqueue(task: ScheduledTask<any, any>): void {
        const queue = this.queues.get(task.priority);
        if (!queue) {
            throw new Error(`不支持的任务优先级: ${task.priority}`);
        }
        queue.push(task);
    }

    public dequeue(): ScheduledTask<any, any> | null {
        for (const priority of PRIORITY_ORDER) {
            const queue = this.queues.get(priority);
            if (queue && queue.length > 0) {
                return queue.shift() || null;
            }
        }
        return null;
    }

    public remove(taskId: string): ScheduledTask<any, any> | null {
        for (const priority of PRIORITY_ORDER) {
            const queue = this.queues.get(priority);
            if (!queue || queue.length === 0) {
                continue;
            }
            const index = queue.findIndex((task) => task.id === taskId);
            if (index >= 0) {
                const [removed] = queue.splice(index, 1);
                return removed || null;
            }
        }
        return null;
    }

    public hasPending(): boolean {
        return PRIORITY_ORDER.some((priority) => {
            const queue = this.queues.get(priority);
            return Boolean(queue && queue.length > 0);
        });
    }

    public getStats(): SchedulerStats {
        const byPriority = PRIORITY_ORDER.reduce((acc, priority) => {
            acc[priority] = this.queues.get(priority)?.length || 0;
            return acc;
        }, {} as Record<WorkerTaskPriority, number>);

        const queued = Object.values(byPriority).reduce((sum, count) => sum + count, 0);

        return { queued, byPriority };
    }
}

export default WorkerTaskScheduler;
