import { describe, it, expect, beforeEach, vi } from 'vitest';
import { APIService } from '../frontend/js/services/API封装.js';

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('决策阈值接口测试', () => {
    let api;

    beforeEach(() => {
        api = new APIService('http://localhost:8000/api');
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
        decision_goal: '确定污染物预警阈值',
        risk_tolerance: 0.1
    };

    const validResponse = {
        task_id: 'task-20260314-001',
        decision_goal: '确定污染物预警阈值',
        threshold_analyses: {
            'threshold_10.0': {
                threshold: 10.0,
                coverage: 45.0,
                risk_level: 'low',
                confidence: 0.92
            },
            'threshold_11.0': {
                threshold: 11.0,
                coverage: 65.0,
                risk_level: 'medium',
                confidence: 0.88
            }
        },
        recommended_threshold: 10.8,
        risk_assessment: {
            risk_level: 'low',
            risk_score: 0.15,
            description: '推荐阈值风险较低，适合使用'
        },
        recommendations: [
            {
                threshold: 10.8,
                priority: 'high',
                reason: '平衡了覆盖率和风险',
                expected_accuracy: 0.90
            },
            {
                threshold: 11.0,
                priority: 'medium',
                reason: '保守选择，覆盖率较高',
                expected_accuracy: 0.88
            }
        ],
        message: '决策阈值分析完成'
    };

    describe('POST /api/decision/thresholds', () => {
        it('成功分析决策阈值', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/decision/thresholds',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result).toEqual(validResponse);
            expect(result.task_id).toBe('task-20260314-001');
            expect(result.decision_goal).toBe('确定污染物预警阈值');
            expect(result.threshold_analyses).toBeDefined();
            expect(result.recommended_threshold).toBeDefined();
            expect(result.risk_assessment).toBeDefined();
            expect(result.recommendations).toBeDefined();
        });

        it('使用自定义阈值进行分析', async () => {
            const requestWithThresholds = {
                ...validRequest,
                custom_thresholds: [10.0, 10.5, 11.0, 11.5, 12.0]
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/decision/thresholds',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithThresholds)
                }
            );

            expect(result).toBeDefined();
        });

        it('使用默认风险容忍度', async () => {
            const requestWithoutTolerance = {
                ...validRequest
            };
            delete requestWithoutTolerance.risk_tolerance;

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/decision/thresholds',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithoutTolerance)
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
                'http://localhost:8000/api/decision/thresholds',
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
                'http://localhost:8000/api/decision/thresholds',
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
                json: () => Promise.resolve({ detail: '决策阈值分析失败: 未知错误' })
            });

            await expect(api.request(
                'http://localhost:8000/api/decision/thresholds',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            )).rejects.toThrow('决策阈值分析失败');
        });

        it('网络错误时抛出友好消息', async () => {
            mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

            await expect(api.request(
                'http://localhost:8000/api/decision/thresholds',
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
                decision_goal: '测试目标',
                risk_tolerance: 0.1
            };

            const minimalResponse = {
                task_id: 'task-minimal',
                decision_goal: '测试目标',
                threshold_analyses: {
                    'threshold_10.5': {
                        threshold: 10.5,
                        coverage: 100.0,
                        risk_level: 'low',
                        confidence: 1.0
                    }
                },
                recommended_threshold: 10.5,
                risk_assessment: {
                    risk_level: 'low',
                    risk_score: 0.0,
                    description: '推荐阈值风险较低，适合使用'
                },
                recommendations: [
                    {
                        threshold: 10.5,
                        priority: 'high',
                        reason: '唯一可用阈值',
                        expected_accuracy: 1.0
                    }
                ],
                message: '决策阈值分析完成'
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(minimalResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/decision/thresholds',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(minimalRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('处理风险容忍度边界值（0.0）', async () => {
            const boundaryRequest = {
                ...validRequest,
                risk_tolerance: 0.0
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/decision/thresholds',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(boundaryRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('处理风险容忍度边界值（1.0）', async () => {
            const boundaryRequest = {
                ...validRequest,
                risk_tolerance: 1.0
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/decision/thresholds',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(boundaryRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('处理多个自定义阈值', async () => {
            const requestWithManyThresholds = {
                ...validRequest,
                custom_thresholds: [10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0]
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/decision/thresholds',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithManyThresholds)
                }
            );

            expect(result).toBeDefined();
        });

        it('风险评估：低风险', async () => {
            const lowRiskResponse = {
                ...validResponse,
                risk_assessment: {
                    risk_level: 'low',
                    risk_score: 0.15,
                    description: '推荐阈值风险较低，适合使用'
                }
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(lowRiskResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/decision/thresholds',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.risk_assessment.risk_level).toBe('low');
        });

        it('风险评估：中等风险', async () => {
            const mediumRiskResponse = {
                ...validResponse,
                risk_assessment: {
                    risk_level: 'medium',
                    risk_score: 0.45,
                    description: '推荐阈值风险中等，需谨慎使用'
                }
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mediumRiskResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/decision/thresholds',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.risk_assessment.risk_level).toBe('medium');
        });

        it('风险评估：高风险', async () => {
            const highRiskResponse = {
                ...validResponse,
                risk_assessment: {
                    risk_level: 'high',
                    risk_score: 0.75,
                    description: '推荐阈值风险较高，不推荐使用'
                }
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(highRiskResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/decision/thresholds',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.risk_assessment.risk_level).toBe('high');
        });
    });

    describe('决策阈值不应该被缓存', () => {
        it('POST请求不应该被缓存', async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            await api.request(
                'http://localhost:8000/api/decision/thresholds',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );
            await api.request(
                'http://localhost:8000/api/decision/thresholds',
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