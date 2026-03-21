import { describe, it, expect, beforeEach, vi } from 'vitest';
import { APIService } from '../apps/frontend/js/services/API封装.js';

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('误差预测接口测试', () => {
    let api;

    beforeEach(() => {
        api = new APIService('http://localhost:8000/api', { maxRetries: 0 });
        mockFetch.mockReset();
    });

    const validRequest = {
        task_id: 'task-20260314-001',
        x_coords: [120.1, 120.2, 120.3, 120.4, 120.5, 120.6, 120.7, 120.8, 120.9, 121.0],
        y_coords: [30.1, 30.2, 30.3, 30.4, 30.5, 30.6, 30.7, 30.8, 30.9, 31.0],
        predicted_values: [10.5, 11.2, 10.8, 11.0, 10.7, 10.9, 11.1, 10.6, 11.3, 10.8],
        train_model: false
    };

    const validResponse = {
        task_id: 'task-20260314-001',
        predicted_errors: [0.2, 0.1, -0.1, 0.2, 0.1, 0.15, 0.25, 0.05, 0.3, 0.12],
        confidence_scores: [0.85, 0.92, 0.88, 0.90, 0.87, 0.89, 0.86, 0.91, 0.84, 0.88],
        statistics: {
            total_points: 10,
            mean_error: 0.139,
            std_error: 0.13,
            min_error: -0.1,
            max_error: 0.3,
            median_error: 0.145,
            mean_confidence: 0.88
        },
        training_results: null,
        message: '误差预测完成'
    };

    const validTrainingResponse = {
        ...validResponse,
        training_results: {
            model_type: 'random_forest',
            training_score: 0.92,
            feature_importance: {
                x_coordinate: 0.45,
                y_coordinate: 0.35,
                predicted_value: 0.20
            },
            training_samples: 10
        }
    };

    describe('POST /api/error/predict', () => {
        it('成功预测误差（不训练模型）', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result).toEqual(validResponse);
            expect(result.task_id).toBe('task-20260314-001');
            expect(result.predicted_errors).toBeDefined();
            expect(result.confidence_scores).toBeDefined();
            expect(result.statistics).toBeDefined();
            expect(result.training_results).toBeNull();
        });

        it('成功预测误差（训练模型）', async () => {
            const trainingRequest = {
                ...validRequest,
                actual_values: [10.3, 11.0, 10.9, 10.8, 10.6, 10.75, 10.85, 10.55, 11.0, 10.68],
                train_model: true
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validTrainingResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(trainingRequest)
                }
            );

            expect(result.training_results).toBeDefined();
            expect(result.training_results.model_type).toBe('random_forest');
            expect(result.training_results.training_score).toBe(0.92);
        });

        it('使用默认train_model值', async () => {
            const requestWithoutTrainFlag = {
                ...validRequest
            };
            delete requestWithoutTrainFlag.train_model;

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithoutTrainFlag)
                }
            );

            expect(result).toBeDefined();
        });

        it('坐标和预测值数据长度不一致时返回400错误', async () => {
            const invalidRequest = {
                ...validRequest,
                x_coords: [120.1, 120.2, 120.3]
            };

            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                json: () => Promise.resolve({ detail: '坐标和预测值数据长度不一致' })
            });

            await expect(api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(invalidRequest)
                }
            )).rejects.toThrow('坐标和预测值数据长度不一致');
        });

        it('数据点数量过少时返回400错误', async () => {
            const invalidRequest = {
                task_id: 'task-20260314-001',
                x_coords: [120.1, 120.2, 120.3, 120.4],
                y_coords: [30.1, 30.2, 30.3, 30.4],
                predicted_values: [10.5, 11.2, 10.8, 11.0]
            };

            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                json: () => Promise.resolve({ detail: '数据点数量过少，至少需要10个点' })
            });

            await expect(api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(invalidRequest)
                }
            )).rejects.toThrow('数据点数量过少，至少需要10个点');
        });

        it('训练模型时未提供实际值返回400错误', async () => {
            const invalidRequest = {
                ...validRequest,
                train_model: true
            };

            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                json: () => Promise.resolve({ detail: '训练模型需要提供实际值' })
            });

            await expect(api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(invalidRequest)
                }
            )).rejects.toThrow('训练模型需要提供实际值');
        });

        it('实际值和预测值数据长度不一致时返回400错误', async () => {
            const invalidRequest = {
                ...validRequest,
                actual_values: [10.3, 11.0, 10.9, 10.8, 10.6],
                train_model: true
            };

            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                json: () => Promise.resolve({ detail: '实际值和预测值数据长度不一致' })
            });

            await expect(api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(invalidRequest)
                }
            )).rejects.toThrow('实际值和预测值数据长度不一致');
        });

        it('服务器内部错误时返回500错误', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error',
                json: () => Promise.resolve({ detail: '误差预测失败: 未知错误' })
            });

            await expect(api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            )).rejects.toThrow('误差预测失败');
        });

        it('网络错误时抛出友好消息', async () => {
            mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

            await expect(api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            )).rejects.toThrow('网络连接失败，请检查后端服务是否启动');
        });
    });

    describe('边界条件测试', () => {
        it('处理最小数据集（10个点）', async () => {
            const minimalRequest = {
                task_id: 'task-minimal',
                x_coords: [120.1, 120.2, 120.3, 120.4, 120.5, 120.6, 120.7, 120.8, 120.9, 121.0],
                y_coords: [30.1, 30.2, 30.3, 30.4, 30.5, 30.6, 30.7, 30.8, 30.9, 31.0],
                predicted_values: [10.5, 11.2, 10.8, 11.0, 10.7, 10.9, 11.1, 10.6, 11.3, 10.8]
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(minimalRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('预测误差可以是负值', async () => {
            const responseWithNegativeErrors = {
                ...validResponse,
                predicted_errors: [-0.2, 0.1, -0.3, 0.15, -0.05, 0.25, -0.1, 0.05, -0.15, 0.08]
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(responseWithNegativeErrors)
            });

            const result = await api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.predicted_errors).toContain(-0.2);
            expect(result.predicted_errors).toContain(-0.3);
        });
    });

    describe('置信度验证', () => {
        it('置信度分数在0到1之间', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            result.confidence_scores.forEach(score => {
                expect(score).toBeGreaterThanOrEqual(0);
                expect(score).toBeLessThanOrEqual(1);
            });
        });

        it('平均置信度正确计算', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.statistics.mean_confidence).toBeCloseTo(0.88, 1);
        });
    });

    describe('模型训练结果验证', () => {
        it('训练结果包含所有必需字段', async () => {
            const trainingRequest = {
                ...validRequest,
                actual_values: [10.3, 11.0, 10.9, 10.8, 10.6, 10.75, 10.85, 10.55, 11.0, 10.68],
                train_model: true
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validTrainingResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(trainingRequest)
                }
            );

            expect(result.training_results).toHaveProperty('model_type');
            expect(result.training_results).toHaveProperty('training_score');
            expect(result.training_results).toHaveProperty('feature_importance');
            expect(result.training_results).toHaveProperty('training_samples');
        });

        it('特征重要性总和为1', async () => {
            const trainingRequest = {
                ...validRequest,
                actual_values: [10.3, 11.0, 10.9, 10.8, 10.6, 10.75, 10.85, 10.55, 11.0, 10.68],
                train_model: true
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validTrainingResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(trainingRequest)
                }
            );

            const totalImportance = Object.values(result.training_results.feature_importance)
                .reduce((sum, val) => sum + val, 0);
            expect(totalImportance).toBeCloseTo(1.0, 1);
        });

        it('训练分数在0到1之间', async () => {
            const trainingRequest = {
                ...validRequest,
                actual_values: [10.3, 11.0, 10.9, 10.8, 10.6, 10.75, 10.85, 10.55, 11.0, 10.68],
                train_model: true
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validTrainingResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(trainingRequest)
                }
            );

            expect(result.training_results.training_score).toBeGreaterThanOrEqual(0);
            expect(result.training_results.training_score).toBeLessThanOrEqual(1);
        });
    });

    describe('统计信息验证', () => {
        it('统计信息包含所有必需字段', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.statistics).toHaveProperty('total_points');
            expect(result.statistics).toHaveProperty('mean_error');
            expect(result.statistics).toHaveProperty('std_error');
            expect(result.statistics).toHaveProperty('min_error');
            expect(result.statistics).toHaveProperty('max_error');
            expect(result.statistics).toHaveProperty('median_error');
            expect(result.statistics).toHaveProperty('mean_confidence');
        });

        it('统计信息正确计算', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.statistics.total_points).toBe(10);
            expect(result.statistics.mean_error).toBeCloseTo(0.139, 2);
            expect(result.statistics.min_error).toBe(-0.1);
            expect(result.statistics.max_error).toBe(0.3);
        });
    });

    describe('误差预测不应该被缓存', () => {
        it('POST请求不应该被缓存', async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            await api.request(
                'http://localhost:8000/api/error/predict',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );
            await api.request(
                'http://localhost:8000/api/error/predict',
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