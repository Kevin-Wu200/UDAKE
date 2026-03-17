import { describe, it, expect, beforeEach, vi } from 'vitest';
import { APIService } from '../frontend/js/services/API封装.js';

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('风险报告接口测试', () => {
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
        risk_index: [
            [0.5, 0.8, 0.6],
            [0.7, 0.9, 0.4],
            [0.3, 0.6, 0.5]
        ],
        x_coords: [120.1, 120.2, 120.3],
        y_coords: [30.1, 30.2, 30.3],
        uncertainty_levels: {
            level_1: { count: 5, percentage: 55.56 },
            level_2: { count: 3, percentage: 33.33 },
            level_3: { count: 1, percentage: 11.11 }
        },
        threshold_analysis: {
            recommended_threshold: 10.8,
            risk_level: 'low',
            coverage: 65.0
        },
        metadata: {
            project_name: '环境监测项目',
            location: '杭州市',
            date: '2026-03-14'
        },
        save_to_file: true
    };

    const validResponse = {
        task_id: 'task-20260314-001',
        report: {
            report_id: 'report-20260314-001',
            task_id: 'task-20260314-001',
            generated_at: '2026-03-14T12:00:00Z',
            summary: {
                total_points: 9,
                mean_risk: 0.6,
                high_risk_percentage: 11.11,
                overall_rating: '低风险'
            },
            risk_assessment: {
                mean_risk_index: 0.6,
                std_risk_index: 0.2,
                risk_distribution: {
                    low: 5,
                    medium: 3,
                    high: 1,
                    critical: 0
                }
            },
            threshold_analysis: {
                recommended_threshold: 10.8,
                risk_level: 'low',
                coverage: 65.0
            },
            spatial_statistics: {
                mean_prediction: 10.9,
                mean_variance: 0.6,
                grid_shape: [3, 3]
            },
            recommendations: [
                '重点关注高风险区域',
                '建议增加采样密度'
            ]
        },
        report_id: 'report-20260314-001',
        generated_at: '2026-03-14T12:00:00Z',
        file_path: '/Users/wuchenkai/UDAKE/backend/app/结果文件/risk_report_task-20260314-001.json',
        message: '风险报告生成完成'
    };

    describe('POST /api/risk/report', () => {
        it('成功生成风险报告', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result).toEqual(validResponse);
            expect(result.task_id).toBe('task-20260314-001');
            expect(result.report).toBeDefined();
            expect(result.report_id).toBeDefined();
            expect(result.generated_at).toBeDefined();
            expect(result.file_path).toBeDefined();
        });

        it('不保存到文件时file_path为null', async () => {
            const requestWithoutSave = {
                ...validRequest,
                save_to_file: false
            };

            const responseWithoutFile = {
                ...validResponse,
                file_path: null
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(responseWithoutFile)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithoutSave)
                }
            );

            expect(result.file_path).toBeNull();
        });

        it('使用默认save_to_file值', async () => {
            const requestWithoutSaveFlag = {
                ...validRequest
            };
            delete requestWithoutSaveFlag.save_to_file;

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithoutSaveFlag)
                }
            );

            expect(result).toBeDefined();
        });

        it('不提供不确定性等级时仍能生成报告', async () => {
            const requestWithoutLevels = {
                ...validRequest
            };
            delete requestWithoutLevels.uncertainty_levels;

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithoutLevels)
                }
            );

            expect(result).toBeDefined();
        });

        it('不提供阈值分析时仍能生成报告', async () => {
            const requestWithoutAnalysis = {
                ...validRequest
            };
            delete requestWithoutAnalysis.threshold_analysis;

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithoutAnalysis)
                }
            );

            expect(result).toBeDefined();
        });

        it('不提供元数据时仍能生成报告', async () => {
            const requestWithoutMetadata = {
                ...validRequest
            };
            delete requestWithoutMetadata.metadata;

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithoutMetadata)
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
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(invalidRequest)
                }
            )).rejects.toThrow('预测结果和方差数据形状不匹配');
        });

        it('预测结果和风险指数形状不匹配时返回400错误', async () => {
            const invalidRequest = {
                ...validRequest,
                risk_index: [
                    [0.5, 0.8],
                    [0.7, 0.9]
                ]
            };

            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                json: () => Promise.resolve({ detail: '预测结果和风险指数形状不匹配' })
            });

            await expect(api.request(
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(invalidRequest)
                }
            )).rejects.toThrow('预测结果和风险指数形状不匹配');
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
                'http://localhost:8000/api/risk/report',
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
                json: () => Promise.resolve({ detail: '风险报告生成失败: 未知错误' })
            });

            await expect(api.request(
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            )).rejects.toThrow('风险报告生成失败');
        });

        it('网络错误时抛出友好消息', async () => {
            mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

            await expect(api.request(
                'http://localhost:8000/api/risk/report',
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
                risk_index: [[0.5]],
                x_coords: [120.1],
                y_coords: [30.1],
                save_to_file: false
            };

            const minimalResponse = {
                task_id: 'task-minimal',
                report: {
                    report_id: 'report-minimal',
                    task_id: 'task-minimal',
                    generated_at: '2026-03-14T12:00:00Z',
                    summary: {
                        total_points: 1,
                        mean_risk: 0.5,
                        high_risk_percentage: 0.0,
                        overall_rating: '低风险'
                    },
                    risk_assessment: {
                        mean_risk_index: 0.5,
                        std_risk_index: 0.0,
                        risk_distribution: {
                            low: 1,
                            medium: 0,
                            high: 0,
                            critical: 0
                        }
                    },
                    threshold_analysis: {},
                    spatial_statistics: {
                        mean_prediction: 10.5,
                        mean_variance: 0.5,
                        grid_shape: [1, 1]
                    },
                    recommendations: []
                },
                report_id: 'report-minimal',
                generated_at: '2026-03-14T12:00:00Z',
                file_path: null,
                message: '风险报告生成完成'
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(minimalResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(minimalRequest)
                }
            );

            expect(result).toBeDefined();
        });

        it('包含完整的元数据信息', async () => {
            const requestWithFullMetadata = {
                ...validRequest,
                metadata: {
                    project_name: '环境监测项目',
                    location: '杭州市',
                    date: '2026-03-14',
                    operator: '张三',
                    notes: '这是测试报告'
                }
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestWithFullMetadata)
                }
            );

            expect(result).toBeDefined();
        });

        it('文件保存失败时仍返回报告', async () => {
            const responseWithFileError = {
                ...validResponse,
                file_path: null
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(responseWithFileError)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.report).toBeDefined();
            expect(result.file_path).toBeNull();
        });
    });

    describe('报告结构验证', () => {
        it('报告包含所有必需字段', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.report).toHaveProperty('report_id');
            expect(result.report).toHaveProperty('task_id');
            expect(result.report).toHaveProperty('generated_at');
            expect(result.report).toHaveProperty('summary');
            expect(result.report).toHaveProperty('risk_assessment');
            expect(result.report).toHaveProperty('spatial_statistics');
            expect(result.report).toHaveProperty('recommendations');
        });

        it('报告ID格式正确', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            const result = await api.request(
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );

            expect(result.report_id).toMatch(/^report-[\d-]+$/);
            expect(result.report.report_id).toBe(result.report_id);
        });
    });

    describe('风险报告不应该被缓存', () => {
        it('POST请求不应该被缓存', async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(validResponse)
            });

            await api.request(
                'http://localhost:8000/api/risk/report',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(validRequest)
                }
            );
            await api.request(
                'http://localhost:8000/api/risk/report',
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