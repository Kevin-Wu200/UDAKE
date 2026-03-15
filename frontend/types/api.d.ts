/**
 * API 服务类型定义
 */

import {
    UploadResponse,
    StartKrigingResponse,
    TaskStatus,
    ResultResponse,
    KrigingParams
} from './core';

/** 缓存条目 */
export interface CacheEntry<T = any> {
    data: T;
    timestamp: number;
}

/** API 服务接口 */
export interface IAPIService {
    baseURL: string;
    request<T = any>(url: string, options?: RequestInit): Promise<T>;
    uploadData(file: File): Promise<UploadResponse>;
    startKriging(params: KrigingParams): Promise<StartKrigingResponse>;
    getTaskStatus(taskId: string): Promise<TaskStatus>;
    getPredictionResult(taskId: string): Promise<ResultResponse>;
    getVarianceResult(taskId: string): Promise<ResultResponse>;
    getReport(taskId: string): Promise<any>;
    downloadExportFile(taskId: string, filename: string): Promise<void>;
    clearCache(): void;
    clearCacheFor(url: string): void;
    cancelAllRequests(): void;
    // TaskExecutors 需要的方法
    submitInterpolation(data: any): Promise<string>;
    getInterpolationResult(interpolationId: string): Promise<any>;
    generateSamplingPoints(data: any): Promise<any>;
    performAnalysis(data: any): Promise<any>;
    generateReport(analysisId: string): Promise<any>;
    exportData(data: any): Promise<any>;
    parseImportFile(file: File): Promise<any>;
    importData(data: any): Promise<any>;
}
