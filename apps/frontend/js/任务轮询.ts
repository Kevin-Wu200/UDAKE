/**
 * 增强版任务轮询器
 * 动态轮询间隔、进度停滞检测、指数退避、轮询状态可视化、优先级管理
 */

import { IAPIService } from '../types/api';
import { APIService } from './services/API封装';
import { TaskStatus, TaskStatusValue, PollingPriority } from '../types/core';
import {
    ITaskPoller,
    TaskPollerOptions,
    PollingStats,
    PollingMetadata,
    PollingState,
    TaskStatusCallback
} from '../types/task';

/** 默认轮询器配置 */
const DEFAULT_POLLER_OPTIONS: TaskPollerOptions = {
    baseInterval: 1000,      // 初始 1s
    maxInterval: 15000,      // 最大 15s
    minInterval: 500,        // 最小 500ms
    maxRetries: 5,           // 最大重试次数
    stallThreshold: 5        // 连续5次无进度变化视为停滞
};

export class TaskPoller implements ITaskPoller {
    public apiService: IAPIService;
    public taskId: string;
    public onUpdate: TaskStatusCallback;

    // 轮询配置
    private readonly baseInterval: number;
    private readonly maxInterval: number;
    private readonly minInterval: number;
    private readonly maxRetries: number;
    private readonly stallThreshold: number;

    // 轮询状态
    private timerId: number | null = null;
    private isPolling: boolean = false;
    private retryCount: number = 0;
    private currentInterval: number;
    private lastProgress: number = -1;
    private stallCount: number = 0;
    private pollCount: number = 0;
    private startTime: number | null = null;
    private priority: PollingPriority = 'normal';

    constructor(
        apiService: IAPIService,
        taskId: string,
        onUpdate: TaskStatusCallback,
        options?: Partial<TaskPollerOptions>
    ) {
        this.apiService = apiService;
        this.taskId = taskId;
        this.onUpdate = onUpdate;

        // 应用配置
        const config = { ...DEFAULT_POLLER_OPTIONS, ...options };
        this.baseInterval = config.baseInterval!;
        this.maxInterval = config.maxInterval!;
        this.minInterval = config.minInterval!;
        this.maxRetries = config.maxRetries!;
        this.stallThreshold = config.stallThreshold!;

        // 初始化轮询间隔
        this.currentInterval = this.baseInterval;
    }

    /**
     * 设置优先级
     */
    setPriority(priority: PollingPriority): void {
        this.priority = priority;
        this._adjustIntervalByPriority();
    }

    /**
     * 开始轮询
     */
    start(): void {
        if (this.isPolling) {
            console.warn('[轮询] 轮询已在进行中');
            return;
        }

        this.isPolling = true;
        this.retryCount = 0;
        this.pollCount = 0;
        this.stallCount = 0;
        this.lastProgress = -1;
        this.startTime = Date.now();
        this.currentInterval = this.baseInterval;
        this._adjustIntervalByPriority();

        this.poll(); // 立即执行一次
        console.log(`[轮询] 开始轮询任务: ${this.taskId}, 优先级: ${this.priority}`);
    }

    /**
     * 停止轮询
     */
    stop(): void {
        if (this.timerId !== null) {
            clearTimeout(this.timerId);
            this.timerId = null;
        }

        this.isPolling = false;
        const elapsed = this.startTime
            ? ((Date.now() - this.startTime) / 1000).toFixed(1)
            : '0';
        console.log(
            `[轮询] 停止任务: ${this.taskId}, 共轮询 ${this.pollCount} 次, 耗时 ${elapsed}s`
        );
    }

    /**
     * 执行轮询
     */
    async poll(): Promise<void> {
        if (!this.isPolling) return;

        this.pollCount++;

        try {
            const status = await this.apiService.getTaskStatus(this.taskId);
            this.retryCount = 0; // 成功则重置重试计数

            // 进度停滞检测
            this._detectStall(status.progress);

            // 动态调整轮询间隔
            this._adjustInterval(status);

            // 附加轮询元数据
            const enrichedStatus: TaskStatus = {
                ...status,
                _polling: {
                    count: this.pollCount,
                    interval: this.currentInterval,
                    stalled: this.stallCount >= this.stallThreshold,
                    elapsed: Date.now() - (this.startTime || Date.now())
                }
            };

            if (this.onUpdate) {
                this.onUpdate(enrichedStatus);
            }

            // 任务完成或失败时停止
            if (status.status === 'completed' || status.status === 'failed') {
                this.stop();
                return;
            }

            // 调度下一次轮询
            this._scheduleNext();
        } catch (error) {
            console.error('[轮询] 请求失败:', error);
            this.retryCount++;

            if (this.retryCount >= this.maxRetries) {
                console.error(`[轮询] 超过最大重试次数，停止轮询`);
                this.stop();
                if (this.onUpdate) {
                    this.onUpdate({
                        status: 'failed',
                        error: `无法连接到服务器，已重试 ${this.maxRetries} 次`,
                        progress: 0,
                        task_id: this.taskId
                    });
                }
                return;
            }

            // 指数退避
            this.currentInterval = Math.min(
                this.currentInterval * Math.pow(1.5, this.retryCount),
                this.maxInterval
            );
            console.log(
                `[轮询] 第 ${this.retryCount} 次重试，间隔: ${this.currentInterval}ms`
            );
            this._scheduleNext();
        }
    }

    /**
     * 调度下一次轮询
     */
    private _scheduleNext(): void {
        this.timerId = window.setTimeout(() => this.poll(), this.currentInterval);
    }

    /**
     * 进度停滞检测
     */
    private _detectStall(progress: number): void {
        if (progress === this.lastProgress) {
            this.stallCount++;
            if (this.stallCount === this.stallThreshold) {
                console.warn(
                    `[轮询] 进度停滞: ${progress}%, 已连续 ${this.stallCount} 次无变化`
                );
            }
        } else {
            this.stallCount = 0;
        }
        this.lastProgress = progress;
    }

    /**
     * 基于进度动态调整轮询间隔
     */
    private _adjustInterval(status: TaskStatus): void {
        const progress = status.progress || 0;

        if (progress < 10) {
            // 刚开始，快速轮询
            this.currentInterval = this.baseInterval;
        } else if (progress < 50) {
            // 中间阶段，适度放慢
            this.currentInterval = this.baseInterval * 1.5;
        } else if (progress < 90) {
            // 后半段，稍慢
            this.currentInterval = this.baseInterval * 2;
        } else {
            // 接近完成，加快轮询
            this.currentInterval = this.baseInterval * 0.8;
        }

        // 停滞时放慢轮询
        if (this.stallCount >= this.stallThreshold) {
            this.currentInterval = Math.min(this.currentInterval * 2, this.maxInterval);
        }

        this._adjustIntervalByPriority();
        this.currentInterval = Math.max(
            this.minInterval,
            Math.min(this.currentInterval, this.maxInterval)
        );
    }

    /**
     * 根据优先级调整间隔
     */
    private _adjustIntervalByPriority(): void {
        switch (this.priority) {
            case 'high':
                this.currentInterval = Math.max(
                    this.minInterval,
                    this.currentInterval * 0.6
                );
                break;
            case 'low':
                this.currentInterval = Math.min(
                    this.maxInterval,
                    this.currentInterval * 2
                );
                break;
        }
    }

    /**
     * 重置轮询器
     */
    reset(): void {
        this.stop();
        this.retryCount = 0;
        this.stallCount = 0;
        this.lastProgress = -1;
        this.pollCount = 0;
        this.currentInterval = this.baseInterval;
    }

    /**
     * 获取轮询状态
     */
    getState(): PollingState {
        return {
            isPolling: this.isPolling,
            timerId: this.timerId,
            retryCount: this.retryCount,
            currentInterval: this.currentInterval,
            lastProgress: this.lastProgress,
            stallCount: this.stallCount,
            pollCount: this.pollCount,
            startTime: this.startTime,
            priority: this.priority
        };
    }
}

// 导出类型以供其他模块使用
export type { TaskPollerOptions, PollingStats, PollingMetadata, PollingState };