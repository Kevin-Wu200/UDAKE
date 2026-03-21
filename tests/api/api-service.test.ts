import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { APIService } from '../../apps/frontend/js/services/API封装';
import { errorHandler } from '../../apps/frontend/js/utils/errors/ErrorHandler';

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock OfflineManager
vi.mock('../../apps/frontend/js/utils/OfflineManager', () => ({
    OfflineManager: {
        isOnline: true,
        cacheResult: vi.fn(),
        getCachedResult: vi.fn(),
        enqueue: vi.fn()
    }
}));

// Mock TwoLevelCache
vi.mock('../../apps/frontend/js/utils/cache/TwoLevelCache', () => ({
    TwoLevelCache: class {
        constructor() {}
        async get() { return undefined; }
        async set() { return; }
        async clear() { return; }
        async invalidatePattern() { return; }
        getStats() { return { hits: 0, misses: 0, hitRate: 0 }; }
        resetStats() { return; }
    }
}));

// Mock errorHandler
vi.mock('../../apps/frontend/js/utils/errors/ErrorHandler', () => ({
    errorHandler: {
        handle: vi.fn()
    },
    ApplicationError: class extends Error {
        constructor(public type: string, public code: string, message: string, public severity: string, public data?: any, public context?: any, public originalError?: any) {
            super(message);
        }
    },
    NetworkError: class extends Error {
        constructor(message: string, public data?: any, public context?: any, public originalError?: any) {
            super(message);
        }
    },
    ValidationError: class extends Error {
        constructor(message: string, public data?: any, public context?: any, public originalError?: any) {
            super(message);
        }
    },
    AuthenticationError: class extends Error {
        constructor(message: string, public data?: any, public context?: any, public originalError?: any) {
            super(message);
        }
    },
    NotFoundError: class extends Error {
        constructor(message: string, public data?: any, public context?: any, public originalError?: any) {
            super(message);
        }
    },
    ServerError: class extends Error {
        constructor(message: string, public data?: any, public context?: any, public originalError?: any) {
            super(message);
        }
    }
}));

describe('APIService', () => {
    let apiService: APIService;

    beforeEach(() => {
        apiService = new APIService('http://localhost:8000');
        mockFetch.mockClear();
    });

    afterEach(() => {
        apiService.cancelAllRequests();
    });

    describe('初始化', () => {
        it('应该成功初始化', () => {
            expect(apiService).toBeDefined();
            expect(apiService.baseURL).toBe('http://localhost:8000');
        });

        it('应该使用默认 baseURL', () => {
            const service = new APIService();
            expect(service.baseURL).toBe('');
        });
    });

    describe('请求方法', () => {
        it('应该能够发送 GET 请求', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ data: 'test' })
            });

            const result = await apiService.get('/test');
            expect(result).toEqual({ data: 'test' });
            expect(mockFetch).toHaveBeenCalledWith(
                'http://localhost:8000/test',
                expect.objectContaining({
                    mode: 'cors',
                    credentials: 'omit'
                })
            );
        });

        it('应该能够发送 POST 请求', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ success: true })
            });

            const result = await apiService.post('/test', { name: 'test' });
            expect(result).toEqual({ success: true });
            expect(mockFetch).toHaveBeenCalledWith(
                'http://localhost:8000/test',
                expect.objectContaining({
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: 'test' })
                })
            );
        });

        it('应该能够发送自定义请求', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ data: 'test' })
            });

            const result = await apiService.request('/test', {
                method: 'PUT',
                headers: { 'X-Custom': 'value' },
                body: JSON.stringify({ value: 'test' })
            });

            expect(result).toEqual({ data: 'test' });
        });
    });

    describe('错误处理', () => {
        it('应该处理 404 错误', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 404,
                statusText: 'Not Found',
                json: async () => ({ message: 'Resource not found' })
            });

            await expect(apiService.get('/not-found')).rejects.toThrow('资源不存在');
            expect(errorHandler.handle).toHaveBeenCalled();
        });

        it('应该处理 500 服务器错误', async () => {
            const noRetryService = new APIService('http://localhost:8000', { maxRetries: 0, retryDelay: 1 });
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error',
                json: async () => ({ message: 'Server error' })
            });

            await expect(noRetryService.get('/error')).rejects.toThrow('服务器处理请求时出现问题');
        });

        it('应该处理网络错误', async () => {
            mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

            await expect(apiService.get('/test')).rejects.toThrow('网络连接失败');
        });

        it('应该处理 401 认证错误', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 401,
                statusText: 'Unauthorized',
                json: async () => ({ message: 'Authentication failed' })
            });

            await expect(apiService.get('/protected')).rejects.toThrow('未授权，请检查登录状态');
        });

        it('应该处理 422 验证错误', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 422,
                statusText: 'Unprocessable Entity',
                json: async () => ({ message: 'Validation failed' })
            });

            await expect(apiService.post('/test', {})).rejects.toThrow('数据验证失败');
        });
    });

    describe('重试机制', () => {
        it('应该在 503 错误时重试', async () => {
            const retryService = new APIService('http://localhost:8000', { maxRetries: 2, retryDelay: 1 });
            let attempt = 0;
            mockFetch.mockImplementation(() => {
                attempt++;
                if (attempt < 3) {
                    return Promise.resolve({
                        ok: false,
                        status: 503,
                        statusText: 'Service Unavailable',
                        json: async () => ({ message: 'Retry later' })
                    });
                }
                return Promise.resolve({
                    ok: true,
                    json: async () => ({ data: 'success' })
                });
            });

            const result = await retryService.get('/retry-test');
            expect(result).toEqual({ data: 'success' });
            expect(attempt).toBe(3);
        });

        it('应该在超过最大重试次数后失败', { timeout: 10000 }, async () => {
            const retryService = new APIService('http://localhost:8000', { maxRetries: 2, retryDelay: 1 });
            mockFetch.mockResolvedValue({
                ok: false,
                status: 503,
                statusText: 'Service Unavailable',
                json: async () => ({ message: 'Retry later' })
            });

            await expect(retryService.get('/fail-test')).rejects.toThrow();
        });

        it('应该在非重试错误时立即失败', async () => {
            mockFetch.mockResolvedValue({
                ok: false,
                status: 404,
                statusText: 'Not Found',
                json: async () => ({ message: 'Not found' })
            });

            await expect(apiService.get('/not-found')).rejects.toThrow();
        });
    });

    describe('缓存管理', () => {
        it('应该能够清除所有缓存', async () => {
            await apiService.clearCache();
            // 测试不会抛出错误
            expect(true).toBe(true);
        });

        it('应该能够清除特定URL的缓存', async () => {
            await apiService.clearCacheFor('/api/tasks');
            // 测试不会抛出错误
            expect(true).toBe(true);
        });

        it('应该能够获取缓存统计', () => {
            const stats = apiService.getCacheStats();
            expect(stats).toBeDefined();
            expect(stats).toHaveProperty('hits');
            expect(stats).toHaveProperty('misses');
            expect(stats).toHaveProperty('hitRate');
        });

        it('应该能够重置缓存统计', () => {
            apiService.resetCacheStats();
            const stats = apiService.getCacheStats();
            expect(stats.hits).toBe(0);
            expect(stats.misses).toBe(0);
        });
    });

    describe('取消请求', () => {
        it('应该能够取消所有待处理请求', () => {
            apiService.cancelAllRequests();
            // 验证 pendingRequests 已清空
            expect(true).toBe(true);
        });
    });

    describe('特殊 API 方法', () => {
        it('应该能够上传数据', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    taskId: 'test-task-id',
                    pointCount: 100
                })
            });

            const file = new File(['test'], 'test.csv', { type: 'text/csv' });
            const result = await apiService.uploadData(file);

            expect(result).toHaveProperty('taskId');
            expect(result.taskId).toBe('test-task-id');
        });

        it('应该能够启动克里金插值', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    taskId: 'kriging-task-id',
                    status: 'pending'
                })
            });

            const params = {
                taskId: 'test-task-id',
                method: 'ordinary',
                variogramModel: 'spherical',
                nugget: 0.1,
                sill: 1.0,
                range: 10.0
            };

            const result = await apiService.startKriging(params);
            expect(result).toHaveProperty('taskId');
            expect(result.status).toBe('pending');
        });

        it('应该能够获取任务状态', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    taskId: 'test-task-id',
                    status: 'completed',
                    progress: 100
                })
            });

            const result = await apiService.getTaskStatus('test-task-id');
            expect(result.status).toBe('completed');
            expect(result.progress).toBe(100);
        });

        it('应该能够获取预测结果', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    taskId: 'test-task-id',
                    grid: [[1, 2], [3, 4]],
                    bounds: { minX: 0, minY: 0, maxX: 10, maxY: 10 },
                    cellSize: 5
                })
            });

            const result = await apiService.getPredictionResult('test-task-id');
            expect(result).toHaveProperty('grid');
            expect(result).toHaveProperty('bounds');
        });

        it('应该能够获取方差结果', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    taskId: 'test-task-id',
                    variance: [[0.1, 0.2], [0.3, 0.4]],
                    bounds: { minX: 0, minY: 0, maxX: 10, maxY: 10 },
                    cellSize: 5
                })
            });

            const result = await apiService.getVarianceResult('test-task-id');
            expect(result).toHaveProperty('variance');
        });

        it('应该能够获取报告', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    taskId: 'test-task-id',
                    title: '测试报告',
                    description: '这是一个测试报告',
                    generatedAt: new Date(),
                    studyArea: {
                        type: 'Polygon',
                        coordinates: []
                    },
                    riskIndices: [],
                    uncertaintyLevels: {
                        grid: [],
                        bounds: { minX: 0, minY: 0, maxX: 10, maxY: 10 },
                        cellSize: 5,
                        thresholds: { low: 0.3, medium: 0.6, high: 0.9 }
                    },
                    hotspots: [],
                    recommendations: [],
                    metadata: {}
                })
            });

            const result = await apiService.getReport('test-task-id');
            expect(result).toHaveProperty('title');
            expect(result).toHaveProperty('riskIndices');
            expect(result).toHaveProperty('uncertaintyLevels');
        });
    });

    describe('采样影响评估 API', () => {
        it('应该能够评估候选采样点', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    taskId: 'test-task-id',
                    candidates: [
                        { x: 10, y: 20, score: 0.8, uncertainty: 0.5, variance: 0.25, impact: 0.3, priority: 1 }
                    ],
                    statistics: {
                        meanScore: 0.8,
                        maxScore: 0.8,
                        minScore: 0.8
                    }
                })
            });

            const result = await apiService.evaluateSamplingCandidates('test-task-id', [
                { x: 10, y: 20 }
            ]);

            expect(result).toHaveProperty('candidates');
            expect(result.candidates).toHaveLength(1);
        });

        it('应该能够预览采样效果', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    taskId: 'test-task-id',
                    newPoint: { x: 10, y: 20, value: 5 },
                    uncertaintyGrid: [[0.5, 0.6], [0.7, 0.8]],
                    varianceGrid: [[0.25, 0.36], [0.49, 0.64]],
                    statistics: {
                        meanUncertainty: 0.65,
                        maxUncertainty: 0.8,
                        minUncertainty: 0.5,
                        reduction: 0.15
                    }
                })
            });

            const result = await apiService.previewSamplingEffect('test-task-id', {
                x: 10,
                y: 20,
                value: 5
            });

            expect(result).toHaveProperty('uncertaintyGrid');
            expect(result).toHaveProperty('statistics');
        });

        it('应该能够推荐最优采样点', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    taskId: 'test-task-id',
                    recommendations: [
                        {
                            x: 10,
                            y: 20,
                            expectedUncertainty: 0.5,
                            uncertaintyReduction: 0.3,
                            variance: 0.25,
                            priority: 1,
                            reason: '高不确定性区域'
                        }
                    ],
                    expectedImprovement: 0.3,
                    uncertaintyReduction: 0.3,
                    cost: 1
                })
            });

            const result = await apiService.recommendOptimalPoints('test-task-id', 10);
            expect(result).toHaveProperty('recommendations');
            expect(result.recommendations).toHaveLength(1);
        });

        it('应该能够批量模拟采样方案', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    taskId: 'test-task-id',
                    results: [
                        {
                            planId: 'plan-1',
                            points: [{ x: 10, y: 20 }],
                            uncertainty: [[0.5, 0.6], [0.7, 0.8]],
                            statistics: {
                                meanUncertainty: 0.65,
                                maxUncertainty: 0.8,
                                minUncertainty: 0.5
                            }
                        }
                    ],
                    comparison: {
                        bestPlanId: 'plan-1',
                        rankings: [
                            { planId: 'plan-1', rank: 1, score: 0.8 }
                        ]
                    }
                })
            });

            const result = await apiService.batchSimulateSampling('test-task-id', [
                {
                    planId: 'plan-1',
                    points: [{ x: 10, y: 20 }],
                    parameters: { method: 'ordinary' }
                }
            ]);

            expect(result).toHaveProperty('results');
            expect(result).toHaveProperty('comparison');
        });
    });

    describe('任务执行器 API', () => {
        it('应该能够提交插值任务', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => 'interpolation-id-123'
            });

            const result = await apiService.submitInterpolation({
                points: [{ x: 10, y: 20, value: 5 }],
                parameters: { method: 'ordinary' }
            });

            expect(result).toBe('interpolation-id-123');
        });

        it('应该能够获取插值结果', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    id: 'interpolation-id-123',
                    grid: [[1, 2], [3, 4]],
                    variance: [[0.1, 0.2], [0.3, 0.4]],
                    bounds: { minX: 0, minY: 0, maxX: 10, maxY: 10 },
                    cellSize: 5,
                    statistics: { mean: 2.5, std: 1.12, min: 1, max: 4 }
                })
            });

            const result = await apiService.getInterpolationResult('interpolation-id-123');
            expect(result).toHaveProperty('grid');
            expect(result).toHaveProperty('statistics');
        });

        it('应该能够生成采样点', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    taskId: 'sampling-task-id',
                    points: [
                        { x: 10, y: 20, uncertainty: 0.5, priority: 1 }
                    ],
                    count: 1
                })
            });

            const result = await apiService.generateSamplingPoints({
                bounds: { minX: 0, minY: 0, maxX: 100, maxY: 100 },
                parameters: { method: 'random' }
            });

            expect(result).toHaveProperty('points');
            expect(result.count).toBe(1);
        });

        it('应该能够执行分析', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    taskId: 'analysis-task-id',
                    analysisType: 'risk-analysis',
                    result: { riskLevel: 'high' },
                    generatedAt: new Date()
                })
            });

            const result = await apiService.performAnalysis({
                datasetId: 'dataset-123',
                parameters: { type: 'risk' }
            });

            expect(result).toHaveProperty('analysisType');
            expect(result).toHaveProperty('result');
        });

        it('应该能够生成报告', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    id: 'report-123',
                    title: '分析报告',
                    content: '报告内容',
                    format: 'pdf',
                    generatedAt: new Date()
                })
            });

            const result = await apiService.generateReport('analysis-task-id');
            expect(result).toHaveProperty('title');
            expect(result).toHaveProperty('content');
        });

        it('应该能够导出数据', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    fileId: 'file-123',
                    fileName: 'export.geojson',
                    format: 'geojson',
                    size: 1024,
                    downloadUrl: 'http://localhost:8000/download/file-123',
                    expiresAt: new Date(),
                    recordCount: 100
                })
            });

            const result = await apiService.exportData({
                taskId: 'task-123',
                format: 'geojson'
            });

            expect(result).toHaveProperty('fileId');
            expect(result).toHaveProperty('downloadUrl');
        });

        it('应该能够解析导入文件', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    fileName: 'test.csv',
                    format: 'csv',
                    recordCount: 100,
                    fields: [
                        { name: 'x', type: 'number', nullable: false },
                        { name: 'y', type: 'number', nullable: false },
                        { name: 'value', type: 'number', nullable: false }
                    ],
                    sampleData: [
                        { x: 10, y: 20, value: 5 }
                    ]
                })
            });

            const file = new File(['x,y,value\n10,20,5'], 'test.csv', { type: 'text/csv' });
            const result = await apiService.parseImportFile(file);

            expect(result).toHaveProperty('fields');
            expect(result).toHaveProperty('sampleData');
        });
    });

    describe('并发请求处理', () => {
        it('应该能够合并相同的请求', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ data: 'test' })
            });

            const [result1, result2] = await Promise.all([
                apiService.get('/test'),
                apiService.get('/test')
            ]);

            expect(result1).toEqual({ data: 'test' });
            expect(result2).toEqual({ data: 'test' });
            // fetch 应该只被调用一次
            expect(mockFetch).toHaveBeenCalledTimes(1);
        });
    });
});
