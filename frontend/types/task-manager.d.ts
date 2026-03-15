/**
 * 任务管理器类型定义
 */

// 导入 Task 类型，避免重复定义
import { Task as CoreTask } from './task';

// 重新导出 Task 类型
export type Task = CoreTask;

// ========== 任务类型 ==========

/** 任务类型 */
export type TaskType =
    | 'data-upload'
    | 'kriging'
    | 'interpolation'
    | 'sampling'
    | 'export'
    | 'import'
    | 'analysis'
    | 'sync'
    | 'download'
    | 'custom';

// ========== 任务优先级 ==========

/** 任务优先级 */
export type TaskPriority = 'urgent' | 'high' | 'normal' | 'low';

// ========== 任务状态 ==========

/** 任务状态 */
export type TaskStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';

// ========== 任务管理器配置 ==========

/** 任务管理器选项 */
export interface TaskManagerOptions {
    enablePersistence?: boolean;
    enableNotifications?: boolean;
    maxRetries?: number;
    taskTimeout?: number;
}

// ========== 任务事件 ==========

/** 任务事件 */
export interface TaskEvent {
    type: string;
    taskId: string;
    timestamp: number;
    data?: any;
    task?: Task;
}

// ========== 任务执行器 ==========

/** 任务执行器 */
export interface TaskExecutor {
    execute(taskId: string, params: any): Promise<any>;
    cancel(taskId: string): Promise<boolean>;
}

// ========== 任务统计 ==========

/** 任务统计 */
export interface TaskStats {
    total: number;
    completed: number;
    failed: number;
    running: number;
    pending: number;
    paused?: number;
    cancelled?: number;
    successRate?: number;
    avgDuration?: number;
}

// ========== 任务队列选项 ==========

/** 任务队列选项 */
export interface TaskQueueOptions {
    maxConcurrentTasks?: number;
    maxQueueSize?: number;
    priorityOrder?: TaskPriority[];
}