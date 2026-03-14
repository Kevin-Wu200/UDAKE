import { describe, it, expect, beforeEach, vi } from 'vitest';
import { APIService } from '../frontend/js/services/API封装.js';

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('不确定性分级接口测试', () => {
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
        y_coords: [30.1, 30.2, 30.3]
    };

    const validResponse = {
        task_id: 'task-20260314-001',
        statistics: {
            level_1: {
                count: 5,
                percentage: 55.56,
                mean_variance: 0.42,
                description: '低不确定性'
            },
            level_2: {
                count: 3,
                percentage: 33.33,
                mean_variance: 0.77,
                description: '中等不确定性'
            },
            level_3: {
                count: 1,
                percentage: 11.11,
                mean_variance: 0.90,
                description: '高不确定性'
            }
        },
        color_map: {
            1: '#4CAF50',
            2: '#FFC107',
            3: '#FF5722',
            4: '#F44336'
        },
        critical_zones: [
            {
                center: { x: 120.2, y: 30.2 },
                level: 3,
                variance: 0.9,
                area: 100,
                description: '高不确定性区域'
            }
        ],
        message: '不确定性分级完成'
    };

    describe('POST /api/uncertainty/classify', () => {
        it('成功进行不确定性分级', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/uncertainty/classify',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result).toEqual(validResponse);
            expect(result.task_id).toBe('task-20260314-001');
            expect(result.statistics).toBeDefined();
            expect(result.color_map).toBeDefined();
            expect(result.critical_zones).toBeDefined();
        });

        it('使用自定义阈值进行分级', async () => {
            const requestWithThresholds = {
                ...validRequest,
                custom_thresholds: {
                    low: 0.5,
                    medium: 1.0,
                    high: 1.5,
                    critical: 2.0
                }
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/uncertainty/classify',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithThresholds)
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
                'http://localhost:8000/api/uncertainty/classify',
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
                'http://localhost:8000/api/uncertainty/classify',
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
                json: () => Promise.resolve({ detail: '不确定性分级失败: 未知错误' })
            });

            await expect(api.request(
                'http://localhost:8000/api/uncertainty/classify',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            )).rejects.toThrow('不确定性分级失败');
        });

        it('网络错误时抛出友好消息', async () => {
            mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

            await expect(api.request(
                'http://localhost:8000/api/uncertainty/classify',
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
                y_coords: [30.1]
            };

            const minimalResponse = {
                task_id: 'task-minimal',
                statistics: {
                    level_1: {
                        count: 1,
                        percentage: 100,
                        mean_variance: 0.5
                    }
                },
                color_map: {
                    1: '#4CAF50',
                    2: '#FFC107',
                    3: '#FF5722',
                    4: '#F44336'
                },
                critical_zones: [],
                message: '不确定性分级完成'
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(minimalResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/uncertainty/classify',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(minimalRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('处理零方差数据', async () => {
            const zeroVarianceRequest = {
                ...validRequest,
                variance: [
                    [0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0]
                ]
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/uncertainty/classify',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(zeroVarianceRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('处理大方差数据', async () => {
            const highVarianceRequest = {
                ...validRequest,
                variance: [
                    [5.0, 6.0, 5.5],
                    [5.8, 6.2, 5.3],
                    [5.7, 5.9, 5.4]
                ]
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/uncertainty/classify',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(highVarianceRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('关键区域数量限制为100个', async () => {
            const responseWithManyZones = {
                ...validResponse,
                critical_zones: Array(150).fill({
                    center: { x: 120.2, y: 30.2 },
                    level: 3,
                    variance: 0.9,
                    area: 100
                })
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(responseWithManyZones)
            });

            const result = await api.request(
                'http://localhost:8000/api/uncertainty/classify',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.critical_zones.length).toBeLessThanOrEqual(100);
        });
    });

    describe('不确定性分级不应该被缓存', () => {
        it('POST请求不应该被缓存', async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            await api.request(
                'http://localhost:8000/api/uncertainty/classify',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );
            await api.request(
                'http://localhost:8000/api/uncertainty/classify',
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