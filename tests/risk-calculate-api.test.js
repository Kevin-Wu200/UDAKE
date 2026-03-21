import { describe, it, expect, beforeEach, vi } from 'vitest';
import { APIService } from '../apps/frontend/js/services/API封装.js';

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('风险指数接口测试', () => {
    let api;

    beforeEach(() => {
        api = new APIService('http://localhost:8000/api', { maxRetries: 0 });
        mockFetch.mockReset();
    });

    const validRequest = {
        task_id: 'task-20260314-001',
        prediction: [
            [10.5, 11.2, 10.8],
            [11.0, 10.9, 11.3],
            [10.7, 11.1, 10.6]
        ],
        variance: [
            [0.5, 0.8, 0.6],
            [0.7, 0.9, 0.4],
            [0.3, 0.6, 0.5]
        ],
        x_coords: [120.1, 120.2, 120.3],
        y_coords: [30.1, 30.2, 30.3],
        confidence_level: 0.95
    };

    const validResponse = {
        task_id: 'task-20260314-001',
        risk_index: [
            [0.5, 0.8, 0.6],
            [0.7, 0.9, 0.4],
            [0.3, 0.6, 0.5]
        ],
        statistics: {
            mean: 0.6,
            std: 0.2,
            min: 0.3,
            max: 0.9,
            median: 0.6
        },
        risk_levels: {
            low: 5,
            medium: 3,
            high: 1,
            critical: 0
        },
        high_risk_area: 1,
        high_risk_percentage: 11.11,
        risk_rating: '低风险',
        message: '风险指数计算完成'
    };

    describe('POST /api/risk/calculate', () => {
        it('成功计算风险指数', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/calculate',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result).toEqual(validResponse);
            expect(result.task_id).toBe('task-20260314-001');
            expect(result.risk_index).toBeDefined();
            expect(result.statistics).toBeDefined();
            expect(result.risk_levels).toBeDefined();
            expect(result.risk_rating).toBeDefined();
        });

        it('使用自定义阈值计算风险', async () => {
            const requestWithThresholds = {
                ...validRequest,
                threshold_values: {
                    low: 0.3,
                    medium: 0.6,
                    high: 0.9,
                    critical: 1.2
                }
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/calculate',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithThresholds)
                }
            );

            expect(result).toBeDefined();
        });

        it('使用默认置信度水平', async () => {
            const requestWithoutConfidence = {
                ...validRequest
            };
            delete requestWithoutConfidence.confidence_level;

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/calculate',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithoutConfidence)
                }
            );

            expect(result).toBeDefined();
        });

        it('预测结果和方差数据形状不匹配时返回400错误', async () => {
            const invalidRequest = {
                ...validRequest,
                prediction: [
                    [10.5, 11.2],
                    [11.0, 10.9]
                ]
            };

            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                json: () => Promise.resolve({ detail: '预测结果和方差数据形状不匹配' })
            });

            await expect(api.request(
                'http://localhost:8000/api/risk/calculate',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(invalidRequest)
                }
            )).rejects.toThrow('预测结果和方差数据形状不匹配');
        });

        it('坐标与数据形状不匹配时返回400错误', async () => {
            const invalidRequest = {
                ...validRequest,
                x_coords: [120.1, 120.2]
            };

            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                json: () => Promise.resolve({ detail: '坐标与数据形状不匹配' })
            });

            await expect(api.request(
                'http://localhost:8000/api/risk/calculate',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(invalidRequest)
                }
            )).rejects.toThrow('坐标与数据形状不匹配');
        });

        it('服务器内部错误时返回500错误', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error',
                json: () => Promise.resolve({ detail: '风险指数计算失败: 未知错误' })
            });

            await expect(api.request(
                'http://localhost:8000/api/risk/calculate',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            )).rejects.toThrow('风险指数计算失败');
        });

        it('网络错误时抛出友好消息', async () => {
            mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

            await expect(api.request(
                'http://localhost:8000/api/risk/calculate',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            )).rejects.toThrow('网络连接失败，请检查后端服务是否启动');
        });
    });

    describe('边界条件测试', () => {
        it('处理最小数据集（1x1矩阵）', async () => {
            const minimalRequest = {
                task_id: 'task-minimal',
                prediction: [[10.5]],
                variance: [[0.5]],
                x_coords: [120.1],
                y_coords: [30.1],
                confidence_level: 0.95
            };

            const minimalResponse = {
                task_id: 'task-minimal',
                risk_index: [[0.5]],
                statistics: {
                    mean: 0.5,
                    std: 0.0,
                    min: 0.5,
                    max: 0.5,
                    median: 0.5
                },
                risk_levels: {
                    low: 1,
                    medium: 0,
                    high: 0,
                    critical: 0
                },
                high_risk_area: 0,
                high_risk_percentage: 0.0,
                risk_rating: '低风险',
                message: '风险指数计算完成'
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(minimalResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/calculate',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(minimalRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('处理置信度边界值（0.0）', async () => {
            const boundaryRequest = {
                ...validRequest,
                confidence_level: 0.0
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/calculate',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(boundaryRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('处理置信度边界值（1.0）', async () => {
            const boundaryRequest = {
                ...validRequest,
                confidence_level: 1.0
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/calculate',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(boundaryRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('综合风险评级：高风险', async () => {
            const highRiskResponse = {
                ...validResponse,
                high_risk_percentage: 35.0,
                risk_rating: '高风险'
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(highRiskResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/calculate',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.risk_rating).toBe('高风险');
        });

        it('综合风险评级：中等风险', async () => {
            const mediumRiskResponse = {
                ...validResponse,
                high_risk_percentage: 20.0,
                risk_rating: '中等风险'
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mediumRiskResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/calculate',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.risk_rating).toBe('中等风险');
        });

        it('综合风险评级：低风险', async () => {
            const lowRiskResponse = {
                ...validResponse,
                high_risk_percentage: 10.0,
                risk_rating: '低风险'
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(lowRiskResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/calculate',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.risk_rating).toBe('低风险');
        });
    });

    describe('风险指数不应该被缓存', () => {
        it('POST请求不应该被缓存', async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            await api.request(
                'http://localhost:8000/api/risk/calculate',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );
            await api.request(
                'http://localhost:8000/api/risk/calculate',
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