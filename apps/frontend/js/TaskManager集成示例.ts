/**
 * TaskManager 集成示例
 * 展示如何在主应用中初始化和使用任务管理器
 */

import TaskManager from './managers/TaskManager';
import { TaskType, TaskPriority } from '../types/task-manager';
import {
    InterpolationTaskExecutor,
    SamplingTaskExecutor,
    AnalysisTaskExecutor,
    ExportTaskExecutor,
    ImportTaskExecutor
} from './managers/TaskExecutors';
import { APIService } from './services/API封装';
import { I18n } from './utils/I18n';

const t = (key: string, params?: Record<string, string | number>): string => I18n.t(key, params);

/**
 * 初始化任务管理器
 */
export function initializeTaskManager(apiService: APIService): any {
    const taskManager = (TaskManager as any).getInstance({
        enablePersistence: true,
        enableNotifications: true,
        maxRetries: 3,
        taskTimeout: 300000 // 5分钟
    });

    // 注册任务执行器
    taskManager.registerExecutor('interpolation', new InterpolationTaskExecutor(apiService));
    taskManager.registerExecutor('sampling', new SamplingTaskExecutor(apiService));
    taskManager.registerExecutor('analysis', new AnalysisTaskExecutor(apiService));
    taskManager.registerExecutor('export', new ExportTaskExecutor(apiService));
    taskManager.registerExecutor('import', new ImportTaskExecutor(apiService));

    // 监听任务事件
    setupTaskEventListeners(taskManager);

    console.log('[TaskManagerIntegration] 任务管理器初始化完成');
    return taskManager;
}

/**
 * 设置任务事件监听器
 */
function setupTaskEventListeners(taskManager: any): void {
    // 任务创建
    taskManager.on('created', (event: any) => {
        console.log(`[TaskEvent] 任务创建: ${event.task.id} - ${event.task.name}`);
        // 可以在这里更新UI，显示新任务
    });

    // 任务开始
    taskManager.on('started', (event: any) => {
        console.log(`[TaskEvent] 任务开始: ${event.task.id}`);
        // 可以在这里更新UI，显示任务开始
    });

    // 任务进度更新
    taskManager.on('progress', (event: any) => {
        console.log(`[TaskEvent] 任务进度: ${event.task.id} - ${event.task.progress}%`);
        // 可以在这里更新UI，显示进度条
    });

    // 任务完成
    taskManager.on('completed', (event: any) => {
        console.log(`[TaskEvent] 任务完成: ${event.task.id}`);
        // 可以在这里处理任务完成后的逻辑
    });

    // 任务失败
    taskManager.on('failed', (event: any) => {
        console.error(`[TaskEvent] 任务失败: ${event.task.id} - ${event.task.error}`);
        // 可以在这里处理任务失败后的逻辑
    });

    // 任务取消
    taskManager.on('cancelled', (event: any) => {
        console.log(`[TaskEvent] 任务取消: ${event.task.id}`);
    });

    // 任务暂停
    taskManager.on('paused', (event: any) => {
        console.log(`[TaskEvent] 任务暂停: ${event.task.id}`);
    });

    // 任务恢复
    taskManager.on('resumed', (event: any) => {
        console.log(`[TaskEvent] 任务恢复: ${event.task.id}`);
    });
}

/**
 * 示例：创建空间插值任务
 */
export async function createInterpolationTask(
    taskManager: any,
    data: any,
    options?: {
        name?: string;
        priority?: TaskPriority;
        notifyOnCompletion?: boolean;
    }
) {
    return await taskManager.createTask(
        'interpolation',
        options?.name || t('template.interpolation.name'),
        data,
        {
            description: t('template.interpolation.description'),
            priority: options?.priority || 'normal',
            allowBackgroundExecution: true,
            notifyOnCompletion: options?.notifyOnCompletion ?? true,
            estimatedDuration: 120000 // 2分钟
        }
    );
}

/**
 * 示例：创建采样任务
 */
export async function createSamplingTask(
    taskManager: any,
    data: any,
    options?: {
        name?: string;
        priority?: TaskPriority;
        notifyOnCompletion?: boolean;
    }
) {
    return await taskManager.createTask(
        'sampling',
        options?.name || t('template.sampling.name'),
        data,
        {
            description: t('template.sampling.description'),
            priority: options?.priority || 'normal',
            allowBackgroundExecution: true,
            notifyOnCompletion: options?.notifyOnCompletion ?? true,
            estimatedDuration: 60000 // 1分钟
        }
    );
}

/**
 * 示例：创建数据分析任务
 */
export async function createAnalysisTask(
    taskManager: any,
    data: any,
    options?: {
        name?: string;
        priority?: TaskPriority;
        notifyOnCompletion?: boolean;
    }
) {
    return await taskManager.createTask(
        'analysis',
        options?.name || t('template.analysis.name'),
        data,
        {
            description: t('template.analysis.description'),
            priority: options?.priority || 'normal',
            allowBackgroundExecution: true,
            notifyOnCompletion: options?.notifyOnCompletion ?? true,
            estimatedDuration: 180000 // 3分钟
        }
    );
}

/**
 * 示例：创建数据导出任务
 */
export async function createExportTask(
    taskManager: any,
    data: any,
    options?: {
        name?: string;
        priority?: TaskPriority;
        notifyOnCompletion?: boolean;
    }
) {
    return await taskManager.createTask(
        'export',
        options?.name || t('template.export.name'),
        data,
        {
            description: t('template.export.description'),
            priority: options?.priority || 'low',
            allowBackgroundExecution: true,
            notifyOnCompletion: options?.notifyOnCompletion ?? true,
            estimatedDuration: 30000 // 30秒
        }
    );
}

/**
 * 示例：创建数据导入任务
 */
export async function createImportTask(
    taskManager: any,
    file: File,
    options?: {
        name?: string;
        priority?: TaskPriority;
        notifyOnCompletion?: boolean;
    }
) {
    return await taskManager.createTask(
        'import',
        options?.name || t('template.import.name'),
        { file },
        {
            description: t('template.import.description', {
                filename: file.name
            }),
            priority: options?.priority || 'normal',
            allowBackgroundExecution: false, // 导入任务不建议后台执行
            notifyOnCompletion: options?.notifyOnCompletion ?? true,
            estimatedDuration: 60000 // 1分钟
        }
    );
}

/**
 * 示例：批量创建任务
 */
export async function createBatchTasks(
    taskManager: any,
    tasks: Array<{
        type: TaskType;
        name: string;
        data: any;
        priority?: TaskPriority;
    }>
) {
    const createdTasks = [];

    for (const task of tasks) {
        const createdTask = await taskManager.createTask(
            task.type,
            task.name,
            task.data,
            {
                priority: task.priority || 'normal',
                allowBackgroundExecution: true,
                notifyOnCompletion: false // 批量任务不单独通知
            }
        );
        createdTasks.push(createdTask);
    }

    return createdTasks;
}

/**
 * 示例：监控任务状态
 */
export async function monitorTask(
    taskManager: any,
    taskId: string,
    onUpdate?: (task: any) => void
): Promise<any> {
    return new Promise(async (resolve, reject) => {
        const checkInterval = setInterval(async () => {
            const task = await taskManager.getTask(taskId);

            if (!task) {
                clearInterval(checkInterval);
                reject(new Error(t('template.monitor.error.unexist')));
                return;
            }

            // 调用更新回调
            if (onUpdate) {
                onUpdate(task);
            }

            // 检查任务是否完成
            if (task.status === 'completed') {
                clearInterval(checkInterval);
                resolve(task.result);
            } else if (task.status === 'failed') {
                clearInterval(checkInterval);
                reject(new Error(task.error || t('template.monitor.error.failed')));
            } else if (task.status === 'cancelled') {
                clearInterval(checkInterval);
                reject(new Error(t('template.monitor.error.canceled'));
            }
        }, 1000); // 每秒检查一次
    });
}

/**
 * 示例：获取任务统计信息
 */
export async function getTaskStatistics(taskManager: any) {
    const stats = await taskManager.getStats();
    console.log('[TaskStatistics]', {
        总任务数: stats.total,
        待处理: stats.pending,
        运行中: stats.running,
        已完成: stats.completed,
        失败: stats.failed,
        平均时长: `${(stats.avgDuration / 1000).toFixed(2)}秒`,
        成功率: `${stats.successRate.toFixed(1)}%`
    });
    return stats;
}

/**
 * 示例：清理旧的历史记录
 */
export async function cleanupOldTasks(
    taskManager: any,
    olderThanDays: number = 30
) {
    console.log(`[TaskManager] 清理 ${olderThanDays} 天前的历史记录...`);
    await taskManager.clearHistory();
    console.log('[TaskManager] 历史记录已清理');
}

export default {
    initializeTaskManager,
    createInterpolationTask,
    createSamplingTask,
    createAnalysisTask,
    createExportTask,
    createImportTask,
    createBatchTasks,
    monitorTask,
    getTaskStatistics,
    cleanupOldTasks
};