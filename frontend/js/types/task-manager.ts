/**
 * 任务管理器类型定义
 */

export type TaskPriority = 'low' | 'normal' | 'high' | 'urgent';
export type TaskStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
export type TaskType = 'interpolation' | 'sampling' | 'analysis' | 'export' | 'import' | 'custom';

export interface Task {
    id: string;
    type: TaskType;
    name: string;
    description?: string;
    priority: TaskPriority;
    status: TaskStatus;
    progress: number; // 0-100
    result?: any;
    error?: string;
    createdAt: number;
    startedAt?: number;
    completedAt?: number;
    estimatedDuration?: number; // 预计时长（毫秒）
    data?: any; // 任务参数数据
    retryCount: number;
    maxRetries: number;
    allowBackgroundExecution: boolean;
    notifyOnCompletion: boolean;
}

export interface TaskQueueOptions {
    maxConcurrentTasks: number;
    maxQueueSize: number;
    priorityOrder: TaskPriority[];
}

export interface TaskExecutor {
    execute(task: Task, onProgress: (progress: number) => void): Promise<any>;
    cancel?(taskId: string): Promise<void>;
}

export interface TaskManagerOptions {
    enablePersistence: boolean;
    enableNotifications: boolean;
    maxRetries: number;
    taskTimeout: number; // 任务超时时间（毫秒）
}

export interface TaskEvent {
    type: 'created' | 'started' | 'paused' | 'resumed' | 'progress' | 'completed' | 'failed' | 'cancelled';
    task: Task;
    timestamp: number;
    data?: any;
}

export interface TaskStats {
    total: number;
    pending: number;
    running: number;
    paused: number;
    completed: number;
    failed: number;
    cancelled: number;
    avgDuration: number;
    successRate: number;
}