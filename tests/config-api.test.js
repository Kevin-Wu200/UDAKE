import { describe, it, expect, beforeEach, vi } from 'vitest';
import { APIService } from '../apps/frontend/js/services/API封装.js';

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('配置接口测试', () => {
    let api;

    beforeEach(() => {
        api = new APIService('http://172.20.10.2:8000/api', { maxRetries: 0 });
        mockFetch.mockReset();
    });

    describe('GET /api/config/map', () => {
        it('成功获取地图配置', async () => {
            const mockConfig = {
                success: true,
                config: {
                    arcgis: {
                        apiKey: 'test-arcgis-key',
                        portalUrl: 'https://portal.arcgis.com',
                        env: 'prod',
                        defaultBasemap: 'streets-navigation-vector',
                        defaultCenter: [0, 0],
                        defaultZoom: 12,
                        isMock: false
                    },
                    amap: {
                        apiKey: 'test-amap-key',
                        securityCode: 'test-security-code',
                        defaultCenter: [119.72170376, 30.26262781],
                        defaultZoom: 18
                    },
                    tianditu: {
                        apiKey: 'test-tianditu-key',
                        token: 'test-token'
                    }
                }
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockConfig)
            });

            const result = await api.request('http://172.20.10.2:8000/api/config/map');

            expect(result).toEqual(mockConfig);
            expect(result.success).toBe(true);
            expect(result.config.arcgis).toBeDefined();
            expect(result.config.amap).toBeDefined();
            expect(result.config.tianditu).toBeDefined();
        });

        it('失败时返回错误信息', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error',
                json: () => Promise.resolve({ detail: '获取地图配置失败' })
            });

            await expect(api.request('http://172.20.10.2:8000/api/config/map'))
                .rejects.toThrow('获取地图配置失败');
        });
    });

    describe('GET /api/config/app', () => {
        it('成功获取应用配置', async () => {
            const mockConfig = {
                success: true,
                config: {
                    appName: 'UDAKE',
                    version: '1.0.0',
                    debug: false,
                    corsOrigins: ['http://172.20.10.2:5173'],
                    maxFileSize: 100,
                    maxConcurrentTasks: 5,
                    taskTimeout: 300
                }
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockConfig)
            });

            const result = await api.request('http://172.20.10.2:8000/api/config/app');

            expect(result).toEqual(mockConfig);
            expect(result.config.appName).toBe('UDAKE');
            expect(result.config.version).toBe('1.0.0');
        });

        it('网络错误时抛出友好消息', async () => {
            mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

            await expect(api.request('http://172.20.10.2:8000/api/config/app'))
                .rejects.toThrow('网络连接失败，请检查后端服务是否启动');
        });
    });

    describe('GET /api/config/ai', () => {
        it('成功获取AI配置', async () => {
            const mockConfig = {
                success: true,
                config: {
                    cacheEnabled: true,
                    maxBatchSize: 100,
                    modelPath: '/models'
                }
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockConfig)
            });

            const result = await api.request('http://172.20.10.2:8000/api/config/ai');

            expect(result).toEqual(mockConfig);
            expect(result.config.cacheEnabled).toBe(true);
        });
    });

    describe('GET /api/config/all', () => {
        it('成功获取所有配置', async () => {
            const mockConfig = {
                success: true,
                config: {
                    app: {
                        appName: 'UDAKE',
                        version: '1.0.0',
                        debug: false
                    },
                    map: {
                        arcgis: {
                            apiKey: 'test-key',
                            portalUrl: 'https://portal.arcgis.com',
                            env: 'prod',
                            defaultBasemap: 'streets-navigation-vector',
                            defaultCenter: [0, 0],
                            defaultZoom: 12,
                            isMock: false
                        },
                        amap: {
                            apiKey: 'test-amap-key',
                            securityCode: 'test-security-code',
                            defaultCenter: [119.72170376, 30.26262781],
                            defaultZoom: 18
                        },
                        tianditu: {
                            apiKey: 'test-tianditu-key',
                            token: 'test-token'
                        }
                    },
                    ai: {
                        cacheEnabled: true,
                        maxBatchSize: 100,
                        modelPath: '/models'
                    },
                    limits: {
                        maxFileSize: 100,
                        maxConcurrentTasks: 5,
                        taskTimeout: 300
                    }
                }
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockConfig)
            });

            const result = await api.request('http://172.20.10.2:8000/api/config/all');

            expect(result).toEqual(mockConfig);
            expect(result.config.app).toBeDefined();
            expect(result.config.map).toBeDefined();
            expect(result.config.ai).toBeDefined();
            expect(result.config.limits).toBeDefined();
        });

        it('边界条件：配置包含空值', async () => {
            const mockConfig = {
                success: true,
                config: {
                    app: {
                        appName: 'UDAKE',
                        version: '1.0.0',
                        debug: false
                    },
                    map: {
                        arcgis: null,
                        amap: null,
                        tianditu: null
                    }
                }
            };

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockConfig)
            });

            const result = await api.request('http://172.20.10.2:8000/api/config/all');

            expect(result.config.map.arcgis).toBeNull();
        });
    });

    describe('配置接口缓存机制', () => {
        it('配置接口应该被缓存', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ success: true, config: {} })
            });

            await api.request('http://172.20.10.2:8000/api/config/map');
            await api.request('http://172.20.10.2:8000/api/config/map');

            expect(mockFetch).toHaveBeenCalledTimes(1);
        });

        it('清除缓存后应该重新请求', async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ success: true, config: {} })
            });

            await api.request('http://172.20.10.2:8000/api/config/app');
            api.clearCache();
            await api.request('http://172.20.10.2:8000/api/config/app');

            expect(mockFetch).toHaveBeenCalledTimes(2);
        });
    });
});