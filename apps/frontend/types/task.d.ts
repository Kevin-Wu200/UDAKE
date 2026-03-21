/**
 * UDAKE 任务类型定义
 */

import { IAPIService } from './api';
import { TaskStatus, TaskStatusValue, PollingPriority } from './core';

// ========== 任务轮询器 ==========

/** 轮询器配置选项 */
export interface TaskPollerOptions {
    baseInterval?: number;      // 基础轮询间隔（毫秒）
    maxInterval?: number;       // 最大轮询间隔（毫秒）
    minInterval?: number;       // 最小轮询间隔（毫秒）
    maxRetries?: number;        // 最大重试次数
    stallThreshold?: number;    // 停滞检测阈值（连续无进度次数）
}

/** 轮询统计信息 */
export interface PollingStats {
    pollCount: number;          // 轮询次数
    startTime: number;          // 开始时间
    elapsed: number;            // 已过时间（毫秒）
    retryCount: number;         // 重试次数
    stalledCount: number;       // 停滞次数
}

/** 轮询元数据 */
export interface PollingMetadata {
    count: number;
    interval: number;
    stalled: boolean;
    elapsed: number;
}

/** 轮询状态 */
export interface PollingState {
    isPolling: boolean;
    timerId: number | null;
    retryCount: number;
    currentInterval: number;
    lastProgress: number;
    stallCount: number;
    pollCount: number;
    startTime: number | null;
    priority: PollingPriority;
}

/** 任务轮询器接口 */
export interface ITaskPoller {
    apiService: IAPIService;
    taskId: string;
    onUpdate: TaskStatusCallback;
    start(): void;
    stop(): void;
    poll(): Promise<void>;
    setPriority(priority: PollingPriority): void;
    reset(): void;
    getState(): PollingState;
}

/** 任务状态回调 */
export type TaskStatusCallback = (status: TaskStatus) => void;

/** 轮询调整策略 */
export interface PollingAdjustmentStrategy {
    checkProgress: (progress: number) => number;
    checkStall: (stalled: boolean) => number;
    checkPriority: (priority: PollingPriority) => number;
}

// ========== 任务管理 ==========

/** 任务队列项 */
export interface TaskQueueItem {
    taskId: string;
    priority: PollingPriority;
    timestamp: number;
    status: TaskStatusValue;
}

/** 任务队列接口 */
export interface ITaskQueue {
    enqueue(item: TaskQueueItem): void;
    dequeue(): TaskQueueItem | null;
    peek(): TaskQueueItem | null;
    size(): number;
    clear(): void;
}

/** 任务管理器接口 */
export interface ITaskManager {
    startPolling(taskId: string, onUpdate: TaskStatusCallback): void;
    stopPolling(taskId: string): void;
    setPriority(taskId: string, priority: PollingPriority): void;
    getTaskStatus(taskId: string): TaskStatus | null;
    getAllTasks(): Map<string, TaskStatus>;
}

/** 任务事件类型 */
export type TaskEventType =
    | 'created'
    | 'started'
    | 'progress'
    | 'completed'
    | 'failed'
    | 'cancelled';

/** 任务事件 */
export interface TaskEvent {
    type: TaskEventType;
    taskId: string;
    timestamp: number;
    data?: any;
}

/** 任务事件监听器 */
export type TaskEventListener = (event: TaskEvent) => void;

/** 任务管理器配置 */
export interface TaskManagerConfig {
    maxConcurrentTasks?: number;
    pollInterval?: number;
    retryAttempts?: number;
    enableEventBus?: boolean;
}

// ========== 任务执行 ==========

/** 任务执行器接口 */
export interface ITaskExecutor {
    execute(taskId: string, params: any): Promise<any>;
    cancel(taskId: string): Promise<boolean>;
    getStatus(taskId: string): TaskStatusValue;
}

/** 执行上下文 */
export interface ExecutionContext {
    taskId: string;
    startTime: number;
    params: any;
    result?: any;
    error?: Error;
}

/** 执行结果 */
export interface ExecutionResult {
    success: boolean;
    result?: any;
    error?: Error;
    duration: number;
}

// ========== 任务状态机 ==========

/** 状态转换 */
export interface StateTransition {
    from: TaskStatusValue;
    to: TaskStatusValue;
    condition?: (state: TaskStatus) => boolean;
}

/** 状态机配置 */
export interface StateMachineConfig {
    initialState: TaskStatusValue;
    transitions: StateTransition[];
    onEnter?: (state: TaskStatusValue) => void;
    onExit?: (state: TaskStatusValue) => void;
}

/** 状态机接口 */
export interface IStateMachine {
    getCurrentState(): TaskStatusValue;
    transition(newState: TaskStatusValue): boolean;
    canTransition(newState: TaskStatusValue): boolean;
    reset(): void;
}

// ========== 任务持久化 ==========

/** 任务存储接口 */
export interface ITaskStorage {
    save(taskId: string, status: TaskStatus): Promise<void>;
    load(taskId: string): Promise<TaskStatus | null>;
    delete(taskId: string): Promise<void>;
    listAll(): Promise<TaskStatus[]>;
}

/** 存储选项 */
export interface StorageOptions {
    ttl?: number;           // 生存时间（毫秒）
    compress?: boolean;     // 是否压缩
    encrypted?: boolean;    // 是否加密
}

// ========== 任务监控 ==========

/** 监控指标 */
export interface TaskMetrics {
    taskId: string;
    totalPolls: number;
    totalRetries: number;
    totalStalls: number;
    averageInterval: number;
    maxInterval: number;
    minInterval: number;
    duration: number;
}

/** 监控器接口 */
export interface ITaskMonitor {
    recordMetric(taskId: string, metric: Partial<TaskMetrics>): void;
    getMetrics(taskId: string): TaskMetrics | null;
    getAllMetrics(): Map<string, TaskMetrics>;
    resetMetrics(taskId: string): void;
    clearAll(): void;
}

/** 告警规则 */
export interface AlertRule {
    condition: (metrics: TaskMetrics) => boolean;
    action: (metrics: TaskMetrics) => void;
    level: 'info' | 'warning' | 'error' | 'critical';
}

/** 告警管理器接口 */
export interface IAlertManager {
    addRule(rule: AlertRule): void;
    removeRule(ruleId: string): void;
    evaluate(taskId: string): void;
    clearAlerts(): void;
}