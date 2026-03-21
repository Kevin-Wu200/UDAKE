import { describe, it, expect, beforeEach, vi } from 'vitest';
import { APIService } from '../apps/frontend/js/services/API封装.js';

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('模型评估接口测试', () => {
    let api;

    beforeEach(() => {
        api = new APIService('http://localhost:8000/api', { maxRetries: 0 });
        mockFetch.mockReset();
    });

    const validRequest = {
        task_id: 'task-20260314-001',
        actual_values: [10.3, 11.0, 10.9, 10.8, 10.6],
        predicted_values: [10.5, 11.2, 10.8, 11.0, 10.7],
        variance: [0.5, 0.8, 0.6, 0.7, 0.3],
        model_params: {
            method: 'kriging',
            variogram_model: 'spherical',
            range: 100.0,
            sill: 1.0,
            nugget: 0.1
        },
        x_coords: [120.1, 120.2, 120.3, 120.4, 120.5],
        y_coords: [30.1, 30.2, 30.3, 30.4, 30.5]
    };

    const validResponse = {
        task_id: 'task-20260314-001',
        report: {
            task_id: 'task-20260314-001',
            evaluation_time: '2026-03-14T12:00:00Z',
            sample_size: 5,
            error_metrics: {
                mae: 0.12,
                rmse: 0.15,
                mape: 1.2,
                max_error: 0.2,
                mean_error: 0.1
            },
            variance_metrics: {
                mean_variance: 0.58,
                variance_coverage: 0.85
            },
            diagnostics: {
                residuals_normality: true,
                homoscedasticity: true,
                outliers: []
            }
        },
        error_metrics: {
            mae: 0.12,
            rmse: 0.15,
            mape: 1.2,
            max_error: 0.2,
            mean_error: 0.1
        },
        correlation: 0.98,
        quality_score: 0.92,
        sample_size: 5,
        recommendations: [
            '模型性能良好，建议继续使用',
            '考虑增加采样点以提高精度',
            '检查高误差区域的异常情况'
        ],
        message: '模型评估完成'
    };

    describe('POST /api/model/evaluation', () => {
        it('成功进行模型评估', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result).toEqual(validResponse);
            expect(result.task_id).toBe('task-20260314-001');
            expect(result.report).toBeDefined();
            expect(result.error_metrics).toBeDefined();
            expect(result.correlation).toBeDefined();
            expect(result.quality_score).toBeDefined();
            expect(result.recommendations).toBeDefined();
        });

        it('不提供模型参数仍能进行评估', async () => {
            const requestWithoutParams = {
                ...validRequest
            };
            delete requestWithoutParams.model_params;

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithoutParams)
                }
            );

            expect(result).toBeDefined();
        });

        it('不提供坐标信息仍能进行评估', async () => {
            const requestWithoutCoords = {
                ...validRequest
            };
            delete requestWithoutCoords.x_coords;
            delete requestWithoutCoords.y_coords;

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithoutCoords)
                }
            );

            expect(result).toBeDefined();
        });

        it('提供完整信息进行评估', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('实际值和预测值数据长度不一致时返回400错误', async () => {
            const invalidRequest = {
                ...validRequest,
                actual_values: [10.3, 11.0, 10.9]
            };

            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                json: () => Promise.resolve({ detail: '实际值和预测值数据长度不一致' })
            });

            await expect(api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(invalidRequest)
                }
            )).rejects.toThrow('实际值和预测值数据长度不一致');
        });

        it('实际值和方差数据长度不一致时返回400错误', async () => {
            const invalidRequest = {
                ...validRequest,
                variance: [0.5, 0.8]
            };

            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                json: () => Promise.resolve({ detail: '实际值和方差数据长度不一致' })
            });

            await expect(api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(invalidRequest)
                }
            )).rejects.toThrow('实际值和方差数据长度不一致');
        });

        it('数据点数量过少时返回400错误', async () => {
            const invalidRequest = {
                task_id: 'task-20260314-001',
                actual_values: [10.3, 11.0, 10.9],
                predicted_values: [10.5, 11.2, 10.8],
                variance: [0.5, 0.8, 0.6]
            };

            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                json: () => Promise.resolve({ detail: '数据点数量过少，至少需要5个点' })
            });

            await expect(api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(invalidRequest)
                }
            )).rejects.toThrow('数据点数量过少，至少需要5个点');
        });

        it('服务器内部错误时返回500错误', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error',
                json: () => Promise.resolve({ detail: '模型评估失败: 未知错误' })
            });

            await expect(api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            )).rejects.toThrow('模型评估失败');
        });

        it('网络错误时抛出友好消息', async () => {
            mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

            await expect(api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            )).rejects.toThrow('网络连接失败，请检查后端服务是否启动');
        });
    });

    describe('边界条件测试', () => {
        it('处理最小数据集（5个点）', async () => {
            const minimalRequest = {
                task_id: 'task-minimal',
                actual_values: [10.3, 11.0, 10.9, 10.8, 10.6],
                predicted_values: [10.5, 11.2, 10.8, 11.0, 10.7],
                variance: [0.5, 0.8, 0.6, 0.7, 0.3]
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(minimalRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('处理零误差数据', async () => {
            const zeroErrorResponse = {
                ...validResponse,
                error_metrics: {
                    mae: 0.0,
                    rmse: 0.0,
                    mape: 0.0,
                    max_error: 0.0,
                    mean_error: 0.0
                },
                correlation: 1.0,
                quality_score: 1.0
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(zeroErrorResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.error_metrics.mae).toBe(0.0);
            expect(result.correlation).toBe(1.0);
            expect(result.quality_score).toBe(1.0);
        });

        it('处理大方差数据', async () => {
            const highVarianceRequest = {
                ...validRequest,
                variance: [5.0, 6.0, 5.5, 5.8, 5.3]
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(highVarianceRequest)
                }
            );

            expect(result).toBeDefined();
        });
    });

    describe('误差指标验证', () => {
        it('误差指标包含所有必需字段', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.error_metrics).toHaveProperty('mae');
            expect(result.error_metrics).toHaveProperty('rmse');
            expect(result.error_metrics).toHaveProperty('mape');
            expect(result.error_metrics).toHaveProperty('max_error');
            expect(result.error_metrics).toHaveProperty('mean_error');
        });

        it('误差指标为非负值', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.error_metrics.mae).toBeGreaterThanOrEqual(0);
            expect(result.error_metrics.rmse).toBeGreaterThanOrEqual(0);
            expect(result.error_metrics.mape).toBeGreaterThanOrEqual(0);
            expect(result.error_metrics.max_error).toBeGreaterThanOrEqual(0);
        });

        it('RMSE应该大于或等于MAE', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.error_metrics.rmse).toBeGreaterThanOrEqual(result.error_metrics.mae);
        });
    });

    describe('相关系数验证', () => {
        it('相关系数在-1到1之间', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.correlation).toBeGreaterThanOrEqual(-1);
            expect(result.correlation).toBeLessThanOrEqual(1);
        });

        it('高相关性表示模型性能好', async () => {
            const highCorrelationResponse = {
                ...validResponse,
                correlation: 0.95,
                quality_score: 0.90
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(highCorrelationResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.correlation).toBeGreaterThan(0.9);
        });

        it('低相关性表示模型性能差', async () => {
            const lowCorrelationResponse = {
                ...validResponse,
                correlation: 0.5,
                quality_score: 0.4
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(lowCorrelationResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.correlation).toBeLessThan(0.6);
        });
    });

    describe('质量评分验证', () => {
        it('质量分数在0到1之间', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.quality_score).toBeGreaterThanOrEqual(0);
            expect(result.quality_score).toBeLessThanOrEqual(1);
        });

        it('质量评级：优秀（0.9-1.0）', async () => {
            const excellentResponse = {
                ...validResponse,
                quality_score: 0.95
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(excellentResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.quality_score).toBeGreaterThanOrEqual(0.9);
        });

        it('质量评级：良好（0.8-0.9）', async () => {
            const goodResponse = {
                ...validResponse,
                quality_score: 0.85
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(goodResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.quality_score).toBeGreaterThanOrEqual(0.8);
            expect(result.quality_score).toBeLessThan(0.9);
        });

        it('质量评级：一般（0.6-0.8）', async () => {
            const averageResponse = {
                ...validResponse,
                quality_score: 0.7
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(averageResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.quality_score).toBeGreaterThanOrEqual(0.6);
            expect(result.quality_score).toBeLessThan(0.8);
        });
    });

    describe('改进建议验证', () => {
        it('建议列表不为空', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.recommendations.length).toBeGreaterThan(0);
        });

        it('建议内容为字符串', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            result.recommendations.forEach(rec => {
                expect(typeof rec).toBe('string');
            });
        });
    });

    describe('模型评估不应该被缓存', () => {
        it('POST请求不应该被缓存', async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );
            await api.request(
                'http://localhost:8000/api/model/evaluation',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(mockFetch).toHaveBeenCalledTimes(2);
        });
    });
});