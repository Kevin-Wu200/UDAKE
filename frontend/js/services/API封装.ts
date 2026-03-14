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

export class APIService implements IAPIService {
    public baseURL: string;
    private pendingRequests: Map<string, Promise<any>>;
    private cache: Map<string, CacheEntry>;
    private cacheMaxSize: number;
    private cacheTTL: number;

    // 重试配置
    private readonly maxRetries: number = 3;
    private readonly retryDelay: number = 1000; // 重试延迟（毫秒）
    private readonly retryableStatusCodes: Set<number> = new Set([408, 429, 500, 502, 503, 504]);

    constructor(baseURL: string = '') {
        this.baseURL = baseURL;
        this.pendingRequests = new Map();
        this.cache = new Map();
        this.cacheMaxSize = 50;
        this.cacheTTL = 5 * 60 * 1000;
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
        return `${method}:${url}:${typeof body === 'string' ? body : ''}`;
    }

    private _getFromCache<T>(key: string): T | null {
        if (!this.cache.has(key)) return null;
        const entry = this.cache.get(key)!;
        if (Date.now() - entry.timestamp > this.cacheTTL) {
            this.cache.delete(key);
            console.log(`[缓存] 已过期: ${key}`);
            return null;
        }
        this.cache.delete(key);
        this.cache.set(key, entry);
        console.log(`[缓存] 命中: ${key}`);
        return entry.data as T;
    }

    private _setCache(key: string, data: unknown): void {
        if (this.cache.size >= this.cacheMaxSize) {
            const oldestKey = this.cache.keys().next().value;
            if (oldestKey !== undefined) {
                this.cache.delete(oldestKey);
                console.log(`[缓存] LRU淘汰: ${oldestKey}`);
            }
        }
        this.cache.set(key, { data, timestamp: Date.now() });
    }

    public clearCache(): void {
        this.cache.clear();
        console.log('[缓存] 已清除所有缓存');
    }

    public clearCacheFor(url: string): void {
        for (const key of this.cache.keys()) {
            if (key.includes(url)) {
                this.cache.delete(key);
            }
        }
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

    public async request<T = any>(url: string, options: RequestInit = {}): Promise<T> {
        const method = options.method || 'GET';
        const requestKey = `${method}_${url}`;
        if (method === 'GET') {
            const cacheKey = this._getCacheKey(url, options);
            const cached = this._getFromCache<T>(cacheKey);
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
                        throw new Error('网络连接失败，请检查后端服务是否启动');
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
                        throw new Error(userMessage);
                    }

                    const data: T = await response.json();
                    if (method === 'GET') {
                        const cacheKey = this._getCacheKey(url, options);
                        this._setCache(cacheKey, data);
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

                    // 非重试错误，直接抛出
                    if (error instanceof TypeError && error.message.includes('fetch')) {
                        throw new Error('网络连接失败，请检查后端服务是否启动');
                    }
                    throw error;
                }
            }

            // 所有重试都失败
            throw lastError || new Error('请求失败，已达到最大重试次数');
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

    public async getReport(taskId: string): Promise<any> {
        return this.request<any>(`${this.baseURL}/result/report/${taskId}`);
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

    public async get<T = any>(url: string): Promise<T> {
        return this.request<T>(`${this.baseURL}${url}`);
    }

    public async post<T = any>(url: string, data: unknown): Promise<T> {
        return this.request<T>(`${this.baseURL}${url}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }

    public cancelAllRequests(): void {
        this.pendingRequests.clear();
    }
}
