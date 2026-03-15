/**
 * 示例任务执行器
 * 演示如何为不同类型的任务创建执行器
 */

import { Task, TaskExecutor } from '../types/task-manager';
import { IAPIService } from '../types/api';

/**
 * 空间插值任务执行器
 */
export class InterpolationTaskExecutor implements TaskExecutor {
    constructor(private apiService: IAPIService) {}

    async execute(task: Task, onProgress: (progress: number) => void): Promise<any> {
        console.log(`[InterpolationTaskExecutor] 开始执行插值任务: ${task.id}`);

        const { data } = task;

        try {
            // 第一步：准备数据 (0-20%)
            onProgress(10);
            await this.delay(500);

            // 第二步：提交插值请求 (20-40%)
            onProgress(30);
            const interpolationId = await this.apiService.submitInterpolation(data);

            // 第三步：等待处理 (40-80%)
            let progress = 40;
            const interval = setInterval(() => {
                progress += 5;
                onProgress(progress);
                if (progress >= 80) clearInterval(interval);
            }, 500);

            // 第四步：获取结果 (80-100%)
            onProgress(90);
            const result = await this.apiService.getInterpolationResult(interpolationId);
            onProgress(100);

            console.log(`[InterpolationTaskExecutor] 插值任务完成: ${task.id}`);
            return result;
        } catch (error) {
            console.error(`[InterpolationTaskExecutor] 插值任务失败: ${task.id}`, error);
            throw error;
        }
    }

    private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

/**
 * 采样任务执行器
 */
export class SamplingTaskExecutor implements TaskExecutor {
    constructor(private apiService: IAPIService) {}

    async execute(task: Task, onProgress: (progress: number) => void): Promise<any> {
        console.log(`[SamplingTaskExecutor] 开始执行采样任务: ${task.id}`);

        const { data } = task;

        try {
            // 第一步：分析采样区域 (0-30%)
            onProgress(15);
            await this.delay(800);

            // 第二步：生成采样点 (30-60%)
            onProgress(45);
            const samplingPoints = await this.apiService.generateSamplingPoints(data);

            // 第三步：验证采样点 (60-80%)
            onProgress(70);
            await this.delay(600);

            // 第四步：返回结果 (80-100%)
            onProgress(90);
            const result = {
                points: samplingPoints,
                statistics: {
                    totalPoints: samplingPoints.length,
                    coverage: data.coverage || 0.95
                }
            };
            onProgress(100);

            console.log(`[SamplingTaskExecutor] 采样任务完成: ${task.id}`);
            return result;
        } catch (error) {
            console.error(`[SamplingTaskExecutor] 采样任务失败: ${task.id}`, error);
            throw error;
        }
    }

    private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

/**
 * 数据分析任务执行器
 */
export class AnalysisTaskExecutor implements TaskExecutor {
    constructor(private apiService: IAPIService) {}

    async execute(task: Task, onProgress: (progress: number) => void): Promise<any> {
        console.log(`[AnalysisTaskExecutor] 开始执行分析任务: ${task.id}`);

        const { data } = task;

        try {
            // 第一步：加载数据 (0-25%)
            onProgress(20);
            await this.delay(1000);

            // 第二步：执行分析 (25-75%)
            onProgress(50);
            const analysisResult = await this.apiService.performAnalysis(data);

            // 第三步：生成报告 (75-100%)
            onProgress(85);
            const report = await this.apiService.generateReport(analysisResult);
            onProgress(100);

            console.log(`[AnalysisTaskExecutor] 分析任务完成: ${task.id}`);
            return report;
        } catch (error) {
            console.error(`[AnalysisTaskExecutor] 分析任务失败: ${task.id}`, error);
            throw error;
        }
    }

    private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

/**
 * 数据导出任务执行器
 */
export class ExportTaskExecutor implements TaskExecutor {
    constructor(private apiService: IAPIService) {}

    async execute(task: Task, onProgress: (progress: number) => void): Promise<any> {
        console.log(`[ExportTaskExecutor] 开始执行导出任务: ${task.id}`);

        const { data } = task;

        try {
            // 第一步：准备导出数据 (0-20%)
            onProgress(15);
            await this.delay(500);

            // 第二步：生成导出文件 (20-80%)
            onProgress(40);
            const exportFile = await this.apiService.exportData(data);

            // 第三步：保存文件 (80-100%)
            onProgress(90);
            await this.delay(300);
            onProgress(100);

            console.log(`[ExportTaskExecutor] 导出任务完成: ${task.id}`);
            return {
                file: exportFile,
                downloadUrl: exportFile.url,
                size: exportFile.size
            };
        } catch (error) {
            console.error(`[ExportTaskExecutor] 导出任务失败: ${task.id}`, error);
            throw error;
        }
    }

    private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async cancel(taskId: string): Promise<void> {
        console.log(`[ExportTaskExecutor] 取消导出任务: ${taskId}`);
        // 实现取消逻辑
    }
}

/**
 * 数据导入任务执行器
 */
export class ImportTaskExecutor implements TaskExecutor {
    constructor(private apiService: IAPIService) {}

    async execute(task: Task, onProgress: (progress: number) => void): Promise<any> {
        console.log(`[ImportTaskExecutor] 开始执行导入任务: ${task.id}`);

        const { data } = task;

        try {
            // 第一步：验证文件 (0-20%)
            onProgress(15);
            await this.delay(500);

            // 第二步：解析文件 (20-60%)
            onProgress(40);
            const parsedData = await this.apiService.parseImportFile(data.file);

            // 第三步：导入数据 (60-90%)
            onProgress(75);
            const importResult = await this.apiService.importData(parsedData);

            // 第四步：完成 (90-100%)
            onProgress(95);
            await this.delay(200);
            onProgress(100);

            console.log(`[ImportTaskExecutor] 导入任务完成: ${task.id}`);
            return importResult;
        } catch (error) {
            console.error(`[ImportTaskExecutor] 导入任务失败: ${task.id}`, error);
            throw error;
        }
    }

    private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async cancel(taskId: string): Promise<void> {
        console.log(`[ImportTaskExecutor] 取消导入任务: ${taskId}`);
        // 实现取消逻辑
    }
}

export default {
    InterpolationTaskExecutor,
    SamplingTaskExecutor,
    AnalysisTaskExecutor,
    ExportTaskExecutor,
    ImportTaskExecutor
};