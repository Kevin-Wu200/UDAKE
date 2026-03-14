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
}
