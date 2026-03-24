import { describe, it, expect, beforeEach, vi } from 'vitest';
import { APIService } from '../apps/frontend/js/services/API封装.js';

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('异常检测接口测试', () => {
    let api;

    beforeEach(() => {
        api = new APIService('http://172.20.10.2:8000/api', { maxRetries: 0 });
        mockFetch.mockReset();
    });

    const validRequest = {
        task_id: 'task-20260314-001',
        x_coords: [120.1, 120.2, 120.3, 120.4, 120.5],
        y_coords: [30.1, 30.2, 30.3, 30.4, 30.5],
        values: [10.5, 11.2, 10.8, 11.0, 10.7],
        detection_method: 'spatial',
        threshold: 3.0,
        contamination: 0.1
    };

    const validResponse = {
        task_id: 'task-20260314-001',
        detection_method: 'spatial',
        spatial_anomalies: {
            anomaly_count: 2,
            anomalies: [
                { x: 120.2, y: 30.2, value: 11.2, type: 'isolation_forest' },
                { x: 120.4, y: 30.4, value: 11.0, type: 'elliptic_envelope' }
            ]
        },
        value_anomalies: null,
        anomaly_scores: [0.1, 0.8, 0.2, 0.7, 0.15],
        statistics: {
            total_points: 5,
            mean: 10.84,
            std: 0.29,
            min: 10.5,
            max: 11.2,
            median: 10.8
        },
        message: '异常检测完成'
    };

    describe('POST /api/anomaly/detect', () => {
        it('成功进行空间异常检测', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result).toEqual(validResponse);
            expect(result.task_id).toBe('task-20260314-001');
            expect(result.detection_method).toBe('spatial');
            expect(result.spatial_anomalies).toBeDefined();
            expect(result.anomaly_scores).toBeDefined();
            expect(result.statistics).toBeDefined();
        });

        it('成功进行值异常检测', async () => {
            const valueRequest = {
                ...validRequest,
                detection_method: 'value'
            };

            const valueResponse = {
                ...validResponse,
                detection_method: 'value',
                spatial_anomalies: null,
                value_anomalies: {
                    upper_threshold: 12.5,
                    lower_threshold: 9.5,
                    anomalies: [
                        { index: 1, value: 11.2, type: 'high' },
                        { index: 3, value: 11.0, type: 'high' }
                    ]
                }
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(valueResponse)
            });

            const result = await api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(valueRequest)
                }
            );

            expect(result.detection_method).toBe('value');
            expect(result.value_anomalies).toBeDefined();
            expect(result.spatial_anomalies).toBeNull();
        });

        it('同时进行空间和值异常检测', async () => {
            const bothRequest = {
                ...validRequest,
                detection_method: 'both'
            };

            const bothResponse = {
                ...validResponse,
                detection_method: 'both',
                value_anomalies: {
                    upper_threshold: 12.5,
                    lower_threshold: 9.5,
                    anomalies: [
                        { index: 1, value: 11.2, type: 'high' }
                    ]
                }
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(bothResponse)
            });

            const result = await api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(bothRequest)
                }
            );

            expect(result.detection_method).toBe('both');
            expect(result.spatial_anomalies).toBeDefined();
            expect(result.value_anomalies).toBeDefined();
        });

        it('使用默认参数', async () => {
            const defaultRequest = {
                task_id: 'task-20260314-001',
                x_coords: [120.1, 120.2, 120.3, 120.4, 120.5],
                y_coords: [30.1, 30.2, 30.3, 30.4, 30.5],
                values: [10.5, 11.2, 10.8, 11.0, 10.7]
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(defaultRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('坐标和数值数据长度不一致时返回400错误', async () => {
            const invalidRequest = {
                ...validRequest,
                x_coords: [120.1, 120.2, 120.3]
            };

            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                json: () => Promise.resolve({ detail: '坐标和数值数据长度不一致' })
            });

            await expect(api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(invalidRequest)
                }
            )).rejects.toThrow('坐标和数值数据长度不一致');
        });

        it('数据点数量过少时返回400错误', async () => {
            const invalidRequest = {
                task_id: 'task-20260314-001',
                x_coords: [120.1, 120.2],
                y_coords: [30.1, 30.2],
                values: [10.5, 11.2]
            };

            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                json: () => Promise.resolve({ detail: '数据点数量过少，至少需要5个点' })
            });

            await expect(api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
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
                json: () => Promise.resolve({ detail: '异常检测失败: 未知错误' })
            });

            await expect(api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            )).rejects.toThrow('异常检测失败');
        });

        it('网络错误时抛出友好消息', async () => {
            mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

            await expect(api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
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
                x_coords: [120.1, 120.2, 120.3, 120.4, 120.5],
                y_coords: [30.1, 30.2, 30.3, 30.4, 30.5],
                values: [10.5, 11.2, 10.8, 11.0, 10.7]
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(minimalRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('处理阈值边界值（1.0）', async () => {
            const boundaryRequest = {
                ...validRequest,
                threshold: 1.0
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(boundaryRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('处理contamination边界值（0.0）', async () => {
            const boundaryRequest = {
                ...validRequest,
                contamination: 0.0
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(boundaryRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('处理contamination边界值（0.5）', async () => {
            const boundaryRequest = {
                ...validRequest,
                contamination: 0.5
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(boundaryRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('处理无异常点的情况', async () => {
            const noAnomalyResponse = {
                ...validResponse,
                spatial_anomalies: {
                    anomaly_count: 0,
                    anomalies: []
                },
                anomaly_scores: [0.1, 0.15, 0.12, 0.13, 0.11]
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(noAnomalyResponse)
            });

            const result = await api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.spatial_anomalies.anomaly_count).toBe(0);
            expect(result.spatial_anomalies.anomalies).toHaveLength(0);
        });

        it('异常分数在0到1之间', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            result.anomaly_scores.forEach(score => {
                expect(score).toBeGreaterThanOrEqual(0);
                expect(score).toBeLessThanOrEqual(1);
            });
        });
    });

    describe('统计信息验证', () => {
        it('统计信息包含所有必需字段', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.statistics).toHaveProperty('total_points');
            expect(result.statistics).toHaveProperty('mean');
            expect(result.statistics).toHaveProperty('std');
            expect(result.statistics).toHaveProperty('min');
            expect(result.statistics).toHaveProperty('max');
            expect(result.statistics).toHaveProperty('median');
        });

        it('统计信息正确计算', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.statistics.total_points).toBe(5);
            expect(result.statistics.mean).toBeCloseTo(10.84, 1);
            expect(result.statistics.min).toBe(10.5);
            expect(result.statistics.max).toBe(11.2);
        });
    });

    describe('异常检测不应该被缓存', () => {
        it('POST请求不应该被缓存', async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            await api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );
            await api.request(
                'http://172.20.10.2:8000/api/anomaly/detect',
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