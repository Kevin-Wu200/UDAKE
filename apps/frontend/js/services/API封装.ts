import type {
    IAPIService
} from '../../types/api';

import type {
    UploadResponse,
    StartKrigingResponse,
    TaskStatus,
    ResultResponse,
    KrigingParams
} from '../../types/core';

import { OfflineManager } from '../utils/OfflineManager';
import { TwoLevelCache } from '../utils/cache/TwoLevelCache';
import { errorHandler } from '../utils/errors/ErrorHandler';
import { ApplicationError, NetworkError, ValidationError, AuthenticationError, NotFoundError, ServerError } from '../utils/errors/AppError';
import { ErrorSeverity, ErrorType, type AppError, type ErrorContext } from '../types/errors';
import { Logger } from '../utils/Logger';
import { buildCacheKey, getApiCacheTTL, shouldUseApiCache } from '../utils/cache/CachePolicy';
import { AppConfig } from '../config/AppConfig';

interface RequestConfig {
    url: string;
    method?: string;
    body?: BodyInit | null;
    headers?: HeadersInit;
}

interface HttpLikeError {
    response?: {
        status?: number;
        data?: Record<string, unknown>;
    };
    request?: unknown;
    message?: string;
}

export class APIService implements IAPIService {
    public baseURL: string;
    private pendingRequests: Map<string, Promise<unknown>>;
    private cache: TwoLevelCache<string, unknown>;
    private readonly apiVersion: string;
    private readonly apiVersionHeader: string;

    // 重试配置
    private readonly maxRetries: number;
    private readonly retryDelay: number;
    private readonly retryableStatusCodes: Set<number>;

    constructor(baseURL: string = '', options?: { maxRetries?: number; retryDelay?: number }) {
        this.maxRetries = options?.maxRetries ?? 3;
        this.retryDelay = options?.retryDelay ?? 1000;
        this.retryableStatusCodes = new Set([408, 429, 500, 502, 503, 504]);
        this.baseURL = baseURL;
        this.pendingRequests = new Map();
        this.apiVersion = AppConfig.api.version;
        this.apiVersionHeader = AppConfig.api.versionHeader;
        this.cache = new TwoLevelCache(
            {
                maxSize: 100,
                ttl: 5 * 60 * 1000, // 5分钟
                strategy: 'lru'
            },
            {
                maxSize: 500,
                ttl: 60 * 60 * 1000, // 1小时
                strategy: 'lfu',
                storageKey: 'api-cache'
            },
            {
                enableAutoPromote: true,
                promoteThreshold: 3
            }
        );
    }

    /**
     * 延迟函数
     */
    private _delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    private _getCacheKey(url: string, options: RequestInit = {}): string {
        return buildCacheKey({
            namespace: 'api',
            method: options.method || 'GET',
            url,
            body: options.body,
            version: this.apiVersion
        });
    }

    private async _getFromCache<T>(key: string): Promise<T | null> {
        const value = await this.cache.get(key);
        if (value !== undefined) {
            Logger.debug('APIService', `缓存命中: ${key}`);
            return value as T;
        }
        return null;
    }

    private async _setCache(key: string, data: unknown, customTTL?: number): Promise<void> {
        await this.cache.set(key, data, customTTL);
    }

    public async clearCache(): Promise<void> {
        await this.cache.clear();
        Logger.info('APIService', '已清除所有缓存');
    }

    public async clearCacheFor(url: string): Promise<void> {
        await this.cache.invalidatePattern(url);
    }

    public getCacheStats() {
        return this.cache.getStats();
    }

    public resetCacheStats(): void {
        this.cache.resetStats();
    }

    public getApiVersion(): string {
        return this.apiVersion;
    }

    private _buildRequestHeaders(headers?: HeadersInit): Headers {
        const merged = new Headers(headers || {});
        if (!merged.has(this.apiVersionHeader)) {
            merged.set(this.apiVersionHeader, this.apiVersion);
        }
        return merged;
    }

    private _shouldUseCache(method: string, url: string): boolean {
        return shouldUseApiCache(method, url);
    }

    private _getCacheTTL(url: string): number {
        return getApiCacheTTL(url, 5 * 60 * 1000);
    }

    /**
     * 将HTTP状态码转换为用户友好的错误消息
     */
    private _getErrorMessage(status: number, statusText: string, detail?: string): string {
        const errorMessages: Record<number, string> = {
            400: '请求参数错误，请检查输入数据',
            401: '未授权，请检查登录状态',
            403: '访问被拒绝，权限不足',
            404: '请求的资源不存在',
            409: '数据冲突，请检查是否重复提交',
            422: '数据验证失败，请检查输入格式',
            429: '请求过于频繁，请稍后重试',
            500: '服务器处理请求时出现问题，请稍后重试',
            502: '网关错误，请稍后重试',
            503: '服务暂时不可用，请稍后重试',
            504: '请求超时，请稍后重试'
        };

        // 优先使用后端返回的详细信息
        if (detail) {
            return detail;
        }

        // 使用预定义的错误消息
        if (errorMessages[status]) {
            return errorMessages[status];
        }

        // 默认错误消息
        return `请求失败 (${status}): ${statusText}，请稍后重试`;
    }

    /**
     * 将错误转换为 AppError
     */
    private convertToAppError(error: unknown, config: RequestConfig): AppError {
        const normalizedError = (error || {}) as HttpLikeError;

        // Axios 或 Fetch 错误
        if (normalizedError.response) {
            // 服务器响应了错误状态码
            const status = normalizedError.response.status ?? 500;
            const data = normalizedError.response.data;

            const context: ErrorContext = {
                url: config.url,
                method: config.method || 'GET',
                status,
                timestamp: new Date()
            };

            if (status === 401) {
                return new AuthenticationError(
                    String(data?.message || '认证失败'),
                    data,
                    context
                );
            } else if (status === 403) {
                return new AuthenticationError(
                    String(data?.message || '权限不足'),
                    data,
                    context
                );
            } else if (status === 404) {
                return new NotFoundError(
                    String(data?.message || '资源不存在'),
                    data,
                    context
                );
            } else if (status >= 500) {
                return new ServerError(
                    String(data?.message || '服务器错误'),
                    data,
                    context
                );
            } else if (status === 422) {
                return new ValidationError(
                    String(data?.message || '数据验证失败'),
                    data,
                    context
                );
            } else {
                return new ApplicationError(
                    ErrorType.VALIDATION,
                    'REQUEST_ERROR',
                    String(data?.message || `请求错误 (${status})`),
                    ErrorSeverity.MEDIUM,
                    data,
                    context,
                    error instanceof Error ? error : undefined
                );
            }
        } else if (normalizedError.request) {
            // 请求已发出但没有收到响应
            return new NetworkError(
                '网络连接失败',
                {
                    message: normalizedError.message
                },
                {
                    url: config.url,
                    method: config.method || 'GET',
                    timestamp: new Date()
                }
            );
        } else {
            // 其他错误
            return new ApplicationError(
                ErrorType.UNKNOWN,
                'UNKNOWN_ERROR',
                error instanceof Error ? error.message : String(error),
                ErrorSeverity.HIGH,
                {
                    url: config.url,
                    method: config.method || 'GET'
                },
                undefined,
                error instanceof Error ? error : undefined
            );
        }
    }

    public async request<T = unknown>(url: string, options: RequestInit = {}): Promise<T> {
        const method = (options.method || 'GET').toUpperCase();
        const requestKey = `${method}_${url}`;
        const headers = this._buildRequestHeaders(options.headers);

        // 检查网络状态
        const isOnline = OfflineManager.isOnline;

        // 离线模式处理
        if (!isOnline) {
            if (method === 'GET') {
                // GET 请求：尝试从缓存返回
                const cacheKey = this._getCacheKey(url, options);
                const cached = await this._getFromCache<T>(cacheKey);
                if (cached !== null) {
                    Logger.info('APIService', `离线模式缓存返回: ${url}`);
                    return cached as T;
                }

                // 尝试从 IndexedDB 获取缓存
                const taskIdMatch = url.match(/task-status\/([^\/]+)/);
                if (taskIdMatch) {
                    const taskId = taskIdMatch[1];
                    try {
                        const cachedResult = await OfflineManager.getCachedResult(taskId);
                        if (cachedResult) {
                            Logger.info('APIService', `离线模式 IndexedDB 返回: ${taskId}`);
                            return cachedResult as T;
                        }
                    } catch { /* IndexedDB 不可用时忽略 */ }
                }

                throw new Error('离线模式：无缓存数据可用');
            } else {
                // POST/PUT/DELETE 请求：加入离线队列
                Logger.info('APIService', `离线模式入队: ${method} ${url}`);

                // 根据URL判断操作类型
                if (url.includes('upload-data')) {
                    await OfflineManager.enqueue({ type: 'upload', payload: options.body });
                } else if (url.includes('start-kriging')) {
                    await OfflineManager.enqueue({ type: 'kriging', payload: JSON.parse(options.body as string) });
                }

                throw new Error('离线模式：操作已加入队列，将在恢复在线后自动执行');
            }
        }

        // 在线模式：检查缓存
        if (method === 'GET' && this._shouldUseCache(method, url)) {
            const cacheKey = this._getCacheKey(url, options);
            const cached = await this._getFromCache<T>(cacheKey);
            if (cached !== null) {
                return cached;
            }
        }

        if (this.pendingRequests.has(requestKey)) {
            Logger.warn('APIService', `请求已在进行中: ${requestKey}`);
            return this.pendingRequests.get(requestKey) as Promise<T>;
        }

        const requestPromise = (async (): Promise<T> => {
            let lastError: Error | null = null;

            // 重试逻辑
            for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
                try {
                    const response = await fetch(url, {
                        ...options,
                        method,
                        headers,
                        mode: 'cors',
                        credentials: 'omit'
                    });

                    if (!response) {
                        const error = new Error('网络连接失败，请检查后端服务是否启动');
                        const appError = this.convertToAppError(error, { url, method });
                        errorHandler.handle(appError);
                        throw appError;
                    }

                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({} as { detail?: string }));
                        const userMessage = this._getErrorMessage(response.status, response.statusText, errorData.detail);

                        // 检查是否需要重试
                        if (this.retryableStatusCodes.has(response.status) && attempt < this.maxRetries) {
                            Logger.warn('APIService', `请求失败 [${response.status}]，${this.retryDelay}ms 后重试 (${attempt + 1}/${this.maxRetries})`);
                            await this._delay(this.retryDelay * (attempt + 1)); // 指数退避
                            continue;
                        }

                        Logger.error('APIService', `API请求失败 [${response.status}]`, errorData);
                        const error = new Error(userMessage);
                        const appError = this.convertToAppError(error, { url, method });
                        errorHandler.handle(appError);
                        throw appError;
                    }

                    const data: T = await response.json();

                    // 缓存 GET 请求结果
                    if (method === 'GET' && this._shouldUseCache(method, url)) {
                        const cacheKey = this._getCacheKey(url, options);
                        const ttl = this._getCacheTTL(url);
                        await this._setCache(cacheKey, data, ttl);
                    }

                    // 缓存任务状态和结果到 IndexedDB
                    if (url.includes('task-status') || url.includes('result')) {
                        const taskIdMatch = url.match(/task-status\/([^\/]+)|result\/prediction\/([^\/]+)/);
                        if (taskIdMatch) {
                            const taskId = taskIdMatch[1] || taskIdMatch[2];
                            try {
                                await OfflineManager.cacheResult(taskId, data);
                            } catch { /* IndexedDB 不可用时忽略 */ }
                        }
                    }

                    return data;

                } catch (error: unknown) {
                    lastError = error instanceof Error ? error : new Error(String(error));

                    // 网络错误也重试
                    if (error instanceof TypeError && error.message.includes('fetch') && attempt < this.maxRetries) {
                        Logger.warn('APIService', `网络失败，${this.retryDelay}ms 后重试 (${attempt + 1}/${this.maxRetries})`);
                        await this._delay(this.retryDelay * (attempt + 1));
                        continue;
                    }

                    // 非重试错误，转换为 AppError 并处理
                    if (error instanceof TypeError && error.message.includes('fetch')) {
                        const appError = this.convertToAppError(new Error('网络连接失败，请检查后端服务是否启动'), { url, method });
                        errorHandler.handle(appError);
                        throw appError;
                    }
                    
                    // 其他错误
                    if (error instanceof ApplicationError) {
                        errorHandler.handle(error);
                    } else {
                        const appError = this.convertToAppError(error instanceof Error ? error : new Error(String(error)), { url, method });
                        errorHandler.handle(appError);
                        throw appError;
                    }
                    throw error;
                }
            }

            // 所有重试都失败
            if (lastError) {
                const appError = this.convertToAppError(lastError, { url, method });
                errorHandler.handle(appError);
                throw appError;
            }
            throw new Error('请求失败，已达到最大重试次数');
        })();

        this.pendingRequests.set(requestKey, requestPromise);
        requestPromise.finally(() => {
            this.pendingRequests.delete(requestKey);
        });
        return requestPromise;
    }

    public async uploadData(file: File): Promise<UploadResponse> {
        const formData = new FormData();
        formData.append('file', file);
        return this.request<UploadResponse>(`${this.baseURL}/upload-data`, {
            method: 'POST',
            body: formData
        });
    }

    public async startKriging(params: KrigingParams): Promise<StartKrigingResponse> {
        return this.request<StartKrigingResponse>(`${this.baseURL}/start-kriging`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        });
    }

    public async getTaskStatus(taskId: string): Promise<TaskStatus> {
        return this.request<TaskStatus>(`${this.baseURL}/task-status/${taskId}`);
    }

    public async getPredictionResult(taskId: string): Promise<ResultResponse> {
        return this.request<ResultResponse>(`${this.baseURL}/result/prediction/${taskId}`);
    }

    public async getVarianceResult(taskId: string): Promise<ResultResponse> {
        return this.request<ResultResponse>(`${this.baseURL}/result/variance/${taskId}`);
    }

    public async getReport(taskId: string): Promise<{
    taskId: string;
    title: string;
    description?: string;
    generatedAt: Date;
    studyArea: {
        type: string;
        coordinates: unknown;
    };
    riskIndices: Array<{
        value: number;
        level: string;
        factors: Array<{ name: string; weight: number; value: number; description: string }>;
        timestamp: Date;
    }>;
    uncertaintyLevels: {
        grid: string[][];
        bounds: { minX: number; minY: number; maxX: number; maxY: number };
        cellSize: number;
        thresholds: { low: number; medium: number; high: number };
    };
    hotspots: Array<{
        id: string;
        location: { x: number; y: number };
        radius: number;
        riskLevel: number;
        uncertaintyLevel: string;
        priority: string;
    }>;
    recommendations: Array<{
        recommendation: string;
        confidence: number;
        reasoning: string[];
        alternatives: string[];
        riskLevel: { value: number; level: string };
        uncertainty: { value: number; level: string };
    }>;
    metadata: Record<string, unknown>;
}> {
    return this.request<{
        taskId: string;
        title: string;
        description?: string;
        generatedAt: Date;
        studyArea: { type: string; coordinates: unknown };
        riskIndices: Array<{
            value: number;
            level: string;
            factors: Array<{ name: string; weight: number; value: number; description: string }>;
            timestamp: Date;
        }>;
        uncertaintyLevels: {
            grid: string[][];
            bounds: { minX: number; minY: number; maxX: number; maxY: number };
            cellSize: number;
            thresholds: { low: number; medium: number; high: number };
        };
        hotspots: Array<{
            id: string;
            location: { x: number; y: number };
            radius: number;
            riskLevel: number;
            uncertaintyLevel: string;
            priority: string;
        }>;
        recommendations: Array<{
            recommendation: string;
            confidence: number;
            reasoning: string[];
            alternatives: string[];
            riskLevel: { value: number; level: string };
            uncertainty: { value: number; level: string };
        }>;
        metadata: Record<string, unknown>;
    }>(`${this.baseURL}/result/report/${taskId}`);
}

    public async downloadExportFile(taskId: string, filename: string): Promise<void> {
        const url = `${this.baseURL}/result/download/${taskId}/${filename}`;
        const response = await fetch(url, { mode: 'cors', credentials: 'omit' });
        if (!response.ok) {
            throw new Error(`下载失败: HTTP ${response.status}`);
        }
        const blob = await response.blob();
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(link.href);
    }

    public async get<T = unknown>(url: string): Promise<T> {
        return this.request<T>(`${this.baseURL}${url}`);
    }

    public async post<T = unknown>(url: string, data: unknown): Promise<T> {
        return this.request<T>(`${this.baseURL}${url}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    // ==================== 前端功能集成补齐接口 ====================

    // 数据质量
    public async getDataQualityHealth(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/data-quality/health`);
    }

    public async listDataQualityRules(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/data-quality/rules`);
    }

    public async createDataQualityRule(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/data-quality/rules', payload);
    }

    public async updateDataQualityRule(ruleId: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/data-quality/rules/${ruleId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    }

    public async toggleDataQualityRule(ruleId: string, enabled: boolean): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/data-quality/rules/${ruleId}/enabled`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
    }

    public async deleteDataQualityRule(ruleId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/data-quality/rules/${ruleId}`, {
            method: 'DELETE'
        });
    }

    public async evaluateDataQuality(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/data-quality/evaluate', payload);
    }

    public async getDataQualityReport(reportId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/data-quality/reports/${reportId}`);
    }

    public async getDataQualityAnomalies(reportId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/data-quality/reports/${reportId}/anomalies`);
    }

    public async getDataQualitySuggestions(reportId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/data-quality/reports/${reportId}/suggestions`);
    }

    public async exportDataQualityReport(reportId: string, fmt: 'json' | 'markdown' | 'html' = 'json'): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/data-quality/reports/${reportId}/export?fmt=${fmt}`);
    }

    public async getDataQualityHistory(datasetId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/data-quality/history/${datasetId}`);
    }

    // 模型评估与自评估
    public async evaluateModel(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/model/evaluation', payload);
    }

    public async runRealtimeEvaluation(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/evaluation/realtime', payload);
    }

    public async getEvaluationPerformance(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/evaluation/performance`);
    }

    public async getEvaluationErrors(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/evaluation/errors`);
    }

    public async getEvaluationUncertainty(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/evaluation/uncertainty`);
    }

    public async selectBestModel(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/model-selection/select', payload);
    }

    public async getModelSelectionStatus(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/model-selection/status`);
    }

    public async switchModel(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/model-selection/switch', payload);
    }

    public async rollbackModel(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/model-selection/rollback', payload);
    }

    public async triggerOptimization(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/optimization/trigger', payload);
    }

    public async getOptimizationStatus(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/optimization/status`);
    }

    public async cancelOptimization(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/optimization/cancel', payload);
    }

    public async getPerformanceReportSnapshot(windowMinutes: number = 120, sampleSize: number = 200): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(
            `${this.baseURL}/reports/performance?window_minutes=${windowMinutes}&sample_size=${sampleSize}`
        );
    }

    public async getEvaluationReportSnapshot(windowMinutes: number = 120, sampleSize: number = 200): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(
            `${this.baseURL}/reports/evaluation?window_minutes=${windowMinutes}&sample_size=${sampleSize}`
        );
    }

    public async getOptimizationReportSnapshot(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/reports/optimization`);
    }

    public async generateComposedReport(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/reports/generate', payload);
    }

    // 模型融合与推荐
    public async createModelFusionTask(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/fusion/create-task', payload);
    }

    public async getModelFusionTaskStatus(taskId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/fusion/task/${taskId}/status`);
    }

    public async getModelFusionTaskResult(taskId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/fusion/task/${taskId}/result`);
    }

    public async compareFusionStrategies(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/fusion/compare-strategies', payload);
    }

    public async optimizeFusionWeights(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/fusion/optimize-weights', payload);
    }

    public async listFusionTasks(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/fusion/tasks`);
    }

    public async listFusionStrategies(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/fusion/strategies`);
    }

    public async listFusionWeightMethods(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/fusion/weight-methods`);
    }

    public async getFusionStatus(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/fusion/status`);
    }

    public async recommendModelParameters(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/recommend-parameters', payload);
    }

    // 批量处理
    public async startBatchKriging(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/batch-kriging', payload);
    }

    public async getBatchKrigingStatus(batchId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/batch-kriging/${batchId}/status`);
    }

    public async controlBatchKriging(batchId: string, action: string): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>(`/batch-kriging/${batchId}/control`, { action });
    }

    public async getBatchKrigingResults(batchId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/batch-kriging/${batchId}/results`);
    }

    public async listBatchKrigingTasks(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/batch-kriging`);
    }

    public async generateBatchReports(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/batch-reports/generate', payload);
    }

    public async getBatchReportTemplates(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/batch-reports/templates`);
    }

    public async getBatchReportSections(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/batch-reports/sections`);
    }

    public async getBatchReportFormats(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/batch-reports/formats`);
    }

    public async previewBatchReport(batchId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/batch-reports/preview/${batchId}`);
    }

    public async createParameterTemplate(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/parameter-templates', payload);
    }

    public async listParameterTemplates(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/parameter-templates`);
    }

    public async getDefaultParameterTemplates(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/parameter-templates/defaults`);
    }

    public async getParameterTemplate(templateId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/parameter-templates/${templateId}`);
    }

    public async deleteParameterTemplate(templateId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/parameter-templates/${templateId}`, {
            method: 'DELETE'
        });
    }

    public async applyParameterTemplate(templateId: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>(`/parameter-templates/${templateId}/apply`, payload);
    }

    public async validateParameters(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/parameters/validate', payload);
    }

    public async applyParameters(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/parameters/apply', payload);
    }

    public async autoAdjustParameters(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/parameters/auto-adjust', payload);
    }

    // 报告与高级分析
    public async createPerformanceReport(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/performance/report', payload);
    }

    public async getPerformanceTrend(taskId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/performance/trend/${taskId}`);
    }

    public async getPerformanceHistoricalStats(taskType: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/performance/historical-stats/${taskType}`);
    }

    public async classifyUncertainty(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/uncertainty/classify', payload);
    }

    public async analyzeDecisionThreshold(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/decision/thresholds', payload);
    }

    public async calculateRiskIndex(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/risk/calculate', payload);
    }

    public async generateRiskReport(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/risk/report', payload);
    }

    public async getBatchComparison(batchId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/batch-kriging/${batchId}/comparison`);
    }

    public async getBatchComparisonRanking(batchId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/batch-kriging/${batchId}/ranking`);
    }

    public async getBatchComparisonDifference(batchId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/batch-kriging/${batchId}/difference`);
    }

    public async getBatchComparisonSummary(batchId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/batch-kriging/${batchId}/comparison/summary`);
    }

    public async predictError(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/error/predict', payload);
    }

    // 任务队列
    public async createQueueTask(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/queue/tasks', payload);
    }

    public async getQueueTask(taskId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/queue/tasks/${taskId}`);
    }

    public async listQueueTasks(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/queue/tasks`);
    }

    public async controlQueueTask(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/queue/tasks/control', payload);
    }

    public async updateQueueTaskPriority(taskId: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/queue/tasks/${taskId}/priority`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    }

    public async getQueueStatistics(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/queue/statistics`);
    }

    public async startQueue(): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/queue/start', {});
    }

    public async stopQueue(): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/queue/stop', {});
    }

    // GPU
    public async getGPUHealth(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/gpu/health`);
    }

    public async getGPUStatus(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/gpu/status`);
    }

    public async getGPUDevices(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/gpu/devices`);
    }

    public async updateGPUConfig(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/gpu/config`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    }

    public async getGPUMetrics(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/gpu/metrics`);
    }

    public async listGPUTasks(limit: number = 100): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/gpu/tasks?limit=${limit}`);
    }

    public async getGPUTask(taskId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/gpu/tasks/${taskId}`);
    }

    public async gpuMatrixMultiply(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/gpu/compute/matrix/multiply', payload);
    }

    // 数据反馈
    public async getFeedbackHealth(): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/feedback/health`);
    }

    public async submitFeedbackInput(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/feedback/input', payload);
    }

    public async submitFeedbackModification(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
        return this.post<Record<string, unknown>>('/feedback/modification', payload);
    }

    public async queryFeedbackData(datasetId: string): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/feedback/data?dataset_id=${encodeURIComponent(datasetId)}`);
    }

    // ==================== 深度学习模块相关方法 ====================

    /**
     * 检查深度学习服务状态
     */
    public async health(): Promise<{
        status: string;
        device: string;
        cuda_available: boolean;
        mps_available: boolean;
        registered_models: string[];
        trained_anomaly_models: string[];
        trained_sampling_rl_models: string[];
        trained_spatiotemporal_models: string[];
    }> {
        return this.request<{
            status: string;
            device: string;
            cuda_available: boolean;
            mps_available: boolean;
            registered_models: string[];
            trained_anomaly_models: string[];
            trained_sampling_rl_models: string[];
            trained_spatiotemporal_models: string[];
        }>(`${this.baseURL}/dl/health`);
    }

    /**
     * 训练空间插值模型
     */
    public async trainSpatial(data: {
        model_type: 'gnn' | 'attention' | 'residual';
        samples: Array<[number, number, number]>;
        epochs: number;
    }): Promise<{
        model_type: string;
        training: Record<string, unknown>;
        history: Record<string, unknown>;
    }> {
        return this.request<{
            model_type: string;
            training: Record<string, unknown>;
            history: Record<string, unknown>;
        }>(`${this.baseURL}/dl/spatial/train`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    /**
     * 空间插值预测
     */
    public async predictSpatial(data: {
        model_type: 'gnn' | 'attention' | 'residual';
        samples: Array<[number, number, number]>;
        queries: Array<[number, number]>;
        blend_ratio: number;
    }): Promise<{
        model_type: string;
        prediction: number[];
        variance: number[];
        source: string;
        resource: Record<string, unknown>;
    }> {
        return this.request<{
            model_type: string;
            prediction: number[];
            variance: number[];
            source: string;
            resource: Record<string, unknown>;
        }>(`${this.baseURL}/dl/spatial/predict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    /**
     * 训练异常检测模型
     */
    public async trainAnomaly(data: {
        model_name: 'vae' | 'gcae' | 'gan' | 'contrastive';
        coords: Array<[number, number]>;
        values: number[];
        epochs: number;
    }): Promise<{
        model_name: string;
        training: Record<string, unknown>;
        config: Record<string, unknown>;
    }> {
        return this.request<{
            model_name: string;
            training: Record<string, unknown>;
            config: Record<string, unknown>;
        }>(`${this.baseURL}/dl/anomaly/train`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    /**
     * 异常检测预测
     */
    public async predictAnomaly(data: {
        model_name: 'vae' | 'gcae' | 'gan' | 'contrastive' | 'fusion';
        coords: Array<[number, number]>;
        values: number[];
        threshold_method: 'statistical' | 'percentile' | 'adaptive';
        percentile: number;
        k: number;
    }): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/dl/anomaly/predict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    /**
     * 训练强化学习采样模型
     */
    public async trainSamplingRL(data: {
        model_name: 'ppo' | 'dqn' | 'a2c' | 'a3c';
        uncertainty_map: number[][];
        existing_points: Array<[number, number]>;
        episodes: number;
        budget: number;
    }): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/dl/sampling-rl/train`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    /**
     * 强化学习采样推荐
     */
    public async recommendSamplingRL(data: {
        model_name: 'ppo' | 'dqn' | 'a2c' | 'a3c';
        uncertainty_map: number[][];
        existing_points: Array<[number, number]>;
        n_recommendations: number;
        fusion_strategy: 'rl_only' | 'rule_only' | 'hybrid';
        realtime: boolean;
    }): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/dl/sampling-rl/recommend`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    /**
     * 训练时空预测模型
     */
    public async trainSpatiotemporal(data: {
        model_type: 'st_transformer' | 'gcn_lstm' | 'convlstm' | 'stgcn';
        coords: Array<[number, number]>;
        series: number[][][];
        targets?: number[][];
        epochs: number;
        pred_horizon: number;
    }): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/dl/spatiotemporal/train`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    /**
     * 时空预测
     */
    public async predictSpatiotemporal(data: {
        model_type: 'st_transformer' | 'gcn_lstm' | 'convlstm' | 'stgcn';
        coords: Array<[number, number]>;
        series: number[][][];
        pred_horizon: number;
        fusion_strategy: 'concat' | 'add' | 'gating';
        targets?: number[][];
        blend_ratio: number;
        uncertainty_method?: 'mc_dropout' | 'deep_ensemble' | 'bayesian';
        enable_memory_optimization: boolean;
        enable_gpu_acceleration: boolean;
        enable_inference_acceleration: boolean;
        enable_long_sequence_optimization: boolean;
        long_sequence_chunk: number;
    }): Promise<Record<string, unknown>> {
        return this.request<Record<string, unknown>>(`${this.baseURL}/dl/spatiotemporal/predict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    public cancelAllRequests(): void {
        this.pendingRequests.clear();
    }

    // ==================== 采样影响评估相关方法 ====================

    /**
     * 评估候选采样点的影响
     */
    public async evaluateSamplingCandidates(
        taskId: string,
        candidatePoints: Array<{ x: number; y: number }>,
        strategy: string = 'impact_optimized',
        gridResolution: number = 50
    ): Promise<{
        taskId: string;
        candidates: Array<{
            x: number;
            y: number;
            score: number;
            uncertainty: number;
            variance: number;
            impact: number;
            priority: number;
        }>;
        statistics: {
            meanScore: number;
            maxScore: number;
            minScore: number;
        };
    }> {
        return this.request<{ taskId: string; candidates: Array<{ x: number; y: number; score: number; uncertainty: number; variance: number; impact: number; priority: number }>; statistics: { meanScore: number; maxScore: number; minScore: number } }>(
            `${this.baseURL}/api/sampling-impact/evaluate-candidates`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_id: taskId,
                    candidate_points: candidatePoints,
                    strategy: strategy,
                    grid_resolution: gridResolution
                })
            }
        );
    }

    /**
     * 预览添加新采样点后的效果
     */
    public async previewSamplingEffect(
        taskId: string,
        newPoint: { x: number; y: number; value: number },
        gridResolution: number = 50
    ): Promise<{
        taskId: string;
        newPoint: { x: number; y: number; value: number };
        uncertaintyGrid: number[][];
        varianceGrid: number[][];
        statistics: {
            meanUncertainty: number;
            maxUncertainty: number;
            minUncertainty: number;
            reduction: number;
        };
    }> {
        return this.request<{
            taskId: string;
            newPoint: { x: number; y: number; value: number };
            uncertaintyGrid: number[][];
            varianceGrid: number[][];
            statistics: { meanUncertainty: number; maxUncertainty: number; minUncertainty: number; reduction: number };
        }>(`${this.baseURL}/api/sampling-impact/preview-effect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_id: taskId,
                new_point: newPoint,
                grid_resolution: gridResolution
            })
        });
    }

    /**
     * 推荐最优采样点
     */
    public async recommendOptimalPoints(
        taskId: string,
        nRecommendations: number = 20,
        strategy: string = 'impact_optimized',
        constraints: Record<string, unknown> | null = null
    ): Promise<{
        taskId: string;
        recommendations: Array<{
            x: number;
            y: number;
            expectedUncertainty: number;
            uncertaintyReduction: number;
            variance: number;
            priority: number;
            reason: string;
        }>;
        expectedImprovement: number;
        uncertaintyReduction: number;
        cost: number;
    }> {
        return this.request<{
            taskId: string;
            recommendations: Array<{
                x: number;
                y: number;
                expectedUncertainty: number;
                uncertaintyReduction: number;
                variance: number;
                priority: number;
                reason: string;
            }>;
            expectedImprovement: number;
            uncertaintyReduction: number;
            cost: number;
        }>(`${this.baseURL}/api/sampling-impact/recommend-optimal`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_id: taskId,
                n_recommendations: nRecommendations,
                strategy: strategy,
                constraints: constraints
            })
        });
    }

    /**
     * 批量模拟多个采样方案的效果
     */
    public async batchSimulateSampling(
        taskId: string,
        samplingPlans: Array<{
            planId: string;
            points: Array<{ x: number; y: number }>;
            parameters: Record<string, unknown>;
        }>,
        gridResolution: number = 50
    ): Promise<{
        taskId: string;
        results: Array<{
            planId: string;
            points: Array<{ x: number; y: number }>;
            uncertainty: number[][];
            statistics: {
                meanUncertainty: number;
                maxUncertainty: number;
                minUncertainty: number;
            };
        }>;
        comparison: {
            bestPlanId: string;
            rankings: Array<{
                planId: string;
                rank: number;
                score: number;
            }>;
        };
    }> {
        return this.request<{
            taskId: string;
            results: Array<{
                planId: string;
                points: Array<{ x: number; y: number }>;
                uncertainty: number[][];
                statistics: { meanUncertainty: number; maxUncertainty: number; minUncertainty: number };
            }>;
            comparison: {
                bestPlanId: string;
                rankings: Array<{ planId: string; rank: number; score: number }>;
            };
        }>(`${this.baseURL}/api/sampling-impact/batch-simulate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_id: taskId,
                sampling_plans: samplingPlans,
                grid_resolution: gridResolution
            })
        });
    }

    // TaskExecutors 需要的方法实现

    /**
     * 提交插值任务
     */
    public async submitInterpolation(data: {
        points: Array<{ x: number; y: number; value: number }>;
        parameters: Record<string, unknown>;
    }): Promise<string> {
        return this.request<string>(`${this.baseURL}/api/interpolation`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    /**
     * 获取插值结果
     */
    public async getInterpolationResult(interpolationId: string): Promise<{
        id: string;
        grid: number[][];
        variance: number[][];
        bounds: { minX: number; minY: number; maxX: number; maxY: number };
        cellSize: number;
        statistics: { mean: number; std: number; min: number; max: number };
    }> {
        return this.request<{
            id: string;
            grid: number[][];
            variance: number[][];
            bounds: { minX: number; minY: number; maxX: number; maxY: number };
            cellSize: number;
            statistics: { mean: number; std: number; min: number; max: number };
        }>(`${this.baseURL}/api/interpolation/${interpolationId}`);
    }

    /**
     * 生成采样点
     */
    public async generateSamplingPoints(data: {
        bounds?: { minX: number; minY: number; maxX: number; maxY: number };
        existingPoints?: Array<{ x: number; y: number; value: number }>;
        parameters: Record<string, unknown>;
    }): Promise<{
        taskId: string;
        points: Array<{ x: number; y: number; uncertainty?: number; priority?: number }>;
        count: number;
    }> {
        return this.request<{
            taskId: string;
            points: Array<{ x: number; y: number; uncertainty?: number; priority?: number }>;
            count: number;
        }>(`${this.baseURL}/api/sampling`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    /**
     * 执行分析
     */
    public async performAnalysis(data: {
        datasetId?: string;
        grid?: number[][];
        bounds?: { minX: number; minY: number; maxX: number; maxY: number };
        variance?: number[][];
        parameters: Record<string, unknown>;
    }): Promise<{
        taskId: string;
        analysisType: string;
        result: unknown;
        generatedAt: Date;
    }> {
        return this.request<{
            taskId: string;
            analysisType: string;
            result: unknown;
            generatedAt: Date;
        }>(`${this.baseURL}/api/analysis`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    /**
     * 生成报告
     */
    public async generateReport(analysisId: string): Promise<{
        id: string;
        title: string;
        content: string;
        format: string;
        generatedAt: Date;
    }> {
        return this.request<{
            id: string;
            title: string;
            content: string;
            format: string;
            generatedAt: Date;
        }>(`${this.baseURL}/api/analysis/${analysisId}/report`);
    }

    /**
     * 导出数据
     */
    public async exportData(data: {
        taskId?: string;
        datasetId?: string;
        format: 'geojson' | 'csv' | 'json' | 'shapefile';
        options?: {
            includeMetadata?: boolean;
            precision?: number;
            filters?: Array<{ field: string; operator: string; value: unknown }>;
        };
    }): Promise<{
        fileId: string;
        fileName: string;
        format: string;
        size: number;
        downloadUrl: string;
        expiresAt: Date;
        recordCount?: number;
    }> {
        return this.request<{
            fileId: string;
            fileName: string;
            format: string;
            size: number;
            downloadUrl: string;
            expiresAt: Date;
            recordCount?: number;
        }>(`${this.baseURL}/api/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    /**
     * 解析导入文件
     */
    public async parseImportFile(file: File): Promise<{
        fileName: string;
        format: string;
        recordCount: number;
        fields: Array<{
            name: string;
            type: string;
            nullable: boolean;
        }>;
        sampleData: Array<Record<string, unknown>>;
    }> {
        return this.request<{
            fileName: string;
            format: string;
            recordCount: number;
            fields: Array<{ name: string; type: string; nullable: boolean }>;
            sampleData: Array<Record<string, unknown>>;
        }>(`${this.baseURL}/api/import/parse`, {
            method: 'POST',
            body: this._formDataFromFile(file)
        });
    }

    /**
     * 导入数据
     */
    public async importData(data: {
        file?: File;
        url?: string;
        content?: string;
        format: 'geojson' | 'csv' | 'shapefile' | 'json';
        options?: {
            encoding?: string;
            skipInvalid?: boolean;
            validate?: boolean;
            transform?: { sourceCRS: string; targetCRS: string };
        };
    }): Promise<{
        datasetId: string;
        fileName: string;
        recordCount: number;
        bounds: { minX: number; minY: number; maxX: number; maxY: number };
        statistics: { count: number; min: number; max: number; mean: number; std: number };
        validation?: {
            valid: boolean;
            errors: Array<{ field: string; message: string; value: unknown }>;
            warnings: Array<{ field: string; message: string; value: unknown; severity: string }>;
        };
    }> {
        return this.request<{
            datasetId: string;
            fileName: string;
            recordCount: number;
            bounds: { minX: number; minY: number; maxX: number; maxY: number };
            statistics: { count: number; min: number; max: number; mean: number; std: number };
            validation?: {
                valid: boolean;
                errors: Array<{ field: string; message: string; value: unknown }>;
                warnings: Array<{ field: string; message: string; value: unknown; severity: string }>;
            };
        }>(`${this.baseURL}/api/import`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    /**
     * 从文件创建 FormData
     */
    private _formDataFromFile(file: File): FormData {
        const formData = new FormData();
        formData.append('file', file);
        return formData;
    }
}
