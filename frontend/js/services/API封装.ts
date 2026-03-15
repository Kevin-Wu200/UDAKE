import type {
    CacheEntry,
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
import { errorHandler, ApplicationError, NetworkError, ValidationError, AuthenticationError, NotFoundError, ServerError } from '../utils/errors/ErrorHandler';
import type { AppError, ErrorContext } from '../../types/errors';

interface RequestConfig {
    url: string;
    method?: string;
    body?: BodyInit | null;
    headers?: HeadersInit;
}

export class APIService implements IAPIService {
    public baseURL: string;
    private pendingRequests: Map<string, Promise<unknown>>;
    private cache: TwoLevelCache<string, any>;
    private cacheConfig: Map<string, number>; // 不同端点的TTL配置

    // 重试配置
    private readonly maxRetries: number = 3;
    private readonly retryDelay: number = 1000; // 重试延迟（毫秒）
    private readonly retryableStatusCodes: Set<number> = new Set([408, 429, 500, 502, 503, 504]);

    constructor(baseURL: string = '') {
        this.baseURL = baseURL;
        this.pendingRequests = new Map();
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

        // 配置不同端点的缓存TTL
        this.cacheConfig = new Map([
            ['/api/data/list', 60 * 1000], // 1分钟
            ['/api/config', 10 * 60 * 1000], // 10分钟
            ['/api/tasks', 30 * 1000], // 30秒
            ['/api/results', 5 * 60 * 1000], // 5分钟
            ['/config', 10 * 60 * 1000] // 10分钟
        ]);
    }

    /**
     * 延迟函数
     */
    private _delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    private _getCacheKey(url: string, options: RequestInit = {}): string {
        const method = options.method || 'GET';
        const body = options.body || '';
        const data = JSON.stringify({
            method,
            url,
            body: typeof body === 'string' ? body : JSON.stringify(body)
        });
        // 使用简单的哈希生成键
        let hash = 0;
        for (let i = 0; i < data.length; i++) {
            const char = data.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32bit integer
        }
        return `${method}_${Math.abs(hash)}`;
    }

    private async _getFromCache<T>(key: string): Promise<T | null> {
        const value = await this.cache.get(key);
        if (value !== undefined) {
            console.log(`[缓存] 命中: ${key}`);
            return value as T;
        }
        return null;
    }

    private async _setCache(key: string, data: unknown, customTTL?: number): Promise<void> {
        await this.cache.set(key, data, customTTL);
    }

    public async clearCache(): Promise<void> {
        await this.cache.clear();
        console.log('[缓存] 已清除所有缓存');
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

    private _shouldUseCache(method: string, url: string): boolean {
        // 只缓存GET请求
        if (method !== 'GET') {
            return false;
        }

        // 检查是否在缓存配置中
        for (const [endpoint] of this.cacheConfig) {
            if (url.includes(endpoint)) {
                return true;
            }
        }

        return false;
    }

    private _getCacheTTL(url: string): number {
        for (const [endpoint, ttl] of this.cacheConfig) {
            if (url.includes(endpoint)) {
                return ttl;
            }
        }
        return 5 * 60 * 1000; // 默认5分钟
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
    private convertToAppError(error: any, config: RequestConfig): AppError {
        // Axios 或 Fetch 错误
        if (error.response) {
            // 服务器响应了错误状态码
            const status = error.response.status;
            const data = error.response.data;

            const context: ErrorContext = {
                url: config.url,
                method: config.method || 'GET',
                status,
                timestamp: new Date()
            };

            if (status === 401) {
                return new AuthenticationError(
                    data?.message || '认证失败',
                    data,
                    context,
                    error
                );
            } else if (status === 403) {
                return new AuthenticationError(
                    data?.message || '权限不足',
                    data,
                    context,
                    error
                );
            } else if (status === 404) {
                return new NotFoundError(
                    data?.message || '资源不存在',
                    data,
                    context,
                    error
                );
            } else if (status >= 500) {
                return new ServerError(
                    data?.message || '服务器错误',
                    data,
                    context,
                    error
                );
            } else if (status === 422) {
                return new ValidationError(
                    data?.message || '数据验证失败',
                    data,
                    context,
                    error
                );
            } else {
                return new ApplicationError(
                    'validation' as any,
                    'REQUEST_ERROR',
                    data?.message || `请求错误 (${status})`,
                    'medium' as any,
                    data,
                    context,
                    error
                );
            }
        } else if (error.request) {
            // 请求已发出但没有收到响应
            return new NetworkError(
                '网络连接失败',
                {
                    message: error.message
                },
                {
                    url: config.url,
                    method: config.method || 'GET',
                    timestamp: new Date()
                },
                error
            );
        } else {
            // 其他错误
            return new ApplicationError(
                'unknown' as any,
                'UNKNOWN_ERROR',
                error.message,
                'high' as any,
                {
                    url: config.url,
                    method: config.method || 'GET'
                },
                undefined,
                error
            );
        }
    }

    public async request<T = unknown>(url: string, options: RequestInit = {}): Promise<T> {
        const method = options.method || 'GET';
        const requestKey = `${method}_${url}`;

        // 检查网络状态
        const isOnline = OfflineManager.isOnline;

        // 离线模式处理
        if (!isOnline) {
            if (method === 'GET') {
                // GET 请求：尝试从缓存返回
                const cacheKey = this._getCacheKey(url, options);
                const cached = this._getFromCache<T>(cacheKey);
                if (cached !== null) {
                    console.log(`[离线模式] 从缓存返回数据: ${url}`);
                    return cached;
                }

                // 尝试从 IndexedDB 获取缓存
                const taskIdMatch = url.match(/task-status\/([^\/]+)/);
                if (taskIdMatch) {
                    const taskId = taskIdMatch[1];
                    const cachedResult = await OfflineManager.getCachedResult(taskId);
                    if (cachedResult) {
                        console.log(`[离线模式] 从 IndexedDB 返回结果: ${taskId}`);
                        return cachedResult as T;
                    }
                }

                throw new Error('离线模式：无缓存数据可用');
            } else {
                // POST/PUT/DELETE 请求：加入离线队列
                console.log(`[离线模式] 请求已加入队列: ${method} ${url}`);

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
            console.warn(`请求已在进行中: ${requestKey}`);
            return this.pendingRequests.get(requestKey) as Promise<T>;
        }

        const requestPromise = (async (): Promise<T> => {
            let lastError: Error | null = null;

            // 重试逻辑
            for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
                try {
                    const response = await fetch(url, {
                        ...options,
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
                        const errorData = await response.json().catch(() => ({}));
                        const userMessage = this._getErrorMessage(response.status, response.statusText, errorData.detail);

                        // 检查是否需要重试
                        if (this.retryableStatusCodes.has(response.status) && attempt < this.maxRetries) {
                            console.warn(`请求失败 [${response.status}]，${this.retryDelay}ms 后重试 (${attempt + 1}/${this.maxRetries})`);
                            await this._delay(this.retryDelay * (attempt + 1)); // 指数退避
                            continue;
                        }

                        console.error(`API请求失败 [${response.status}]:`, errorData);
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
                            await OfflineManager.cacheResult(taskId, data);
                        }
                    }

                    return data;

                } catch (error: unknown) {
                    lastError = error instanceof Error ? error : new Error(String(error));

                    // 网络错误也重试
                    if (error instanceof TypeError && error.message.includes('fetch') && attempt < this.maxRetries) {
                        console.warn(`网络连接失败，${this.retryDelay}ms 后重试 (${attempt + 1}/${this.maxRetries})`);
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
