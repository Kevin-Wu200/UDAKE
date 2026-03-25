import { describe, it, expect, beforeEach, vi } from 'vitest';
import { APIService } from '../apps/frontend/js/services/API封装.js';

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

const normalizeTestUrl = (value) => value.endsWith('/') ? value.slice(0, -1) : value;
const TEST_BACKEND_ROOT = (() => {
    const raw = process.env.TEST_BACKEND_URL || process.env.BACKEND_URL || process.env.VITE_API_BASE_URL || 'http://localhost:8000';
    const normalized = normalizeTestUrl(raw);
    return normalized.endsWith('/api') ? normalized.slice(0, -4) : normalized;
})();


describe('APIService', () => {
    let api;

    beforeEach(() => {
        api = new APIService(TEST_BACKEND_ROOT + '/api', { maxRetries: 0 });
        mockFetch.mockReset();
    });

    describe('缓存机制', () => {
        it('GET 请求应该被缓存', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ data: 'test' })
            });

            const url = TEST_BACKEND_ROOT + '/api/config/test';
            const result1 = await api.request(url);
            const result2 = await api.request(url);

            expect(mockFetch).toHaveBeenCalledTimes(1);
            expect(result1).toEqual({ data: 'test' });
            expect(result2).toEqual({ data: 'test' });
        });

        it('POST 请求不应该被缓存', async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ ok: true })
            });

            const url = TEST_BACKEND_ROOT + '/api/test';
            await api.request(url, { method: 'POST', body: '{}' });
            await api.request(url, { method: 'POST', body: '{}' });

            expect(mockFetch).toHaveBeenCalledTimes(2);
        });

        it('clearCache 应该清除所有缓存', async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ data: 1 })
            });

            await api.request(TEST_BACKEND_ROOT + '/api/a');
            api.clearCache();
            await api.request(TEST_BACKEND_ROOT + '/api/a');

            expect(mockFetch).toHaveBeenCalledTimes(2);
        });

        it('clearCacheFor 应该清除指定 URL 的缓存', async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ data: 1 })
            });

            await api.request(TEST_BACKEND_ROOT + '/api/a');
            await api.request(TEST_BACKEND_ROOT + '/api/b');
            api.clearCacheFor('/a');
            await api.request(TEST_BACKEND_ROOT + '/api/a');

            // a 被清除后重新请求，b 仍在缓存
            expect(mockFetch).toHaveBeenCalledTimes(3);
        });

        it('缓存过期后应该重新请求', async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ data: 1 })
            });

            api.cacheTTL = -1; // 立即过期
            await api.request(TEST_BACKEND_ROOT + '/api/test');
            await api.request(TEST_BACKEND_ROOT + '/api/test');

            expect(mockFetch).toHaveBeenCalledTimes(2);
        });

        it('LRU 淘汰应该在超出最大条目数时生效', async () => {
            api.cacheMaxSize = 2;
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ data: 1 })
            });

            await api.request(TEST_BACKEND_ROOT + '/api/a');
            await api.request(TEST_BACKEND_ROOT + '/api/b');
            await api.request(TEST_BACKEND_ROOT + '/api/c');

            // a 应该被淘汰
            mockFetch.mockClear();
            await api.request(TEST_BACKEND_ROOT + '/api/a');
            expect(mockFetch).toHaveBeenCalledTimes(1);
        });
    });

    describe('请求去重', () => {
        it('相同请求应该被去重', async () => {
            let resolvePromise;
            mockFetch.mockImplementation(() => new Promise(resolve => {
                resolvePromise = resolve;
            }));

            const p1 = api.request(TEST_BACKEND_ROOT + '/api/test');
            const p2 = api.request(TEST_BACKEND_ROOT + '/api/test');

            resolvePromise({ ok: true, json: () => Promise.resolve({ data: 1 }) });

            const [r1, r2] = await Promise.all([p1, p2]);
            expect(r1).toEqual(r2);
            expect(mockFetch).toHaveBeenCalledTimes(1);
        });
    });

    describe('错误处理', () => {
        it('HTTP 错误应该抛出异常', async () => {
            // 使用 mockResolvedValueOnce 确保只返回一次，避免重试
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 400, // 使用 400 而不是 500，避免触发重试
                statusText: 'Bad Request',
                json: () => Promise.resolve({ detail: '服务器错误' })
            });

            await expect(api.request(TEST_BACKEND_ROOT + '/api/test'))
                .rejects.toThrow('服务器错误');
        });

        it('网络错误应该抛出友好消息', async () => {
            mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

            await expect(api.request(TEST_BACKEND_ROOT + '/api/test'))
                .rejects.toThrow('网络连接失败，请检查后端服务是否启动');
        });
    });

    describe('便捷方法', () => {
        it('startKriging 应该发送 POST 请求', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ task_id: '123' })
            });

            const result = await api.startKriging({ points: [] });
            expect(result.task_id).toBe('123');
            expect(mockFetch).toHaveBeenCalledWith(
                TEST_BACKEND_ROOT + '/api/start-kriging',
                expect.objectContaining({ method: 'POST' })
            );
        });

        it('getTaskStatus 应该发送 GET 请求', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ status: 'running', progress: 50 })
            });

            const result = await api.getTaskStatus('abc');
            expect(result.status).toBe('running');
        });

        it('cancelAllRequests 应该清空待处理请求', () => {
            api.pendingRequests.set('test', Promise.resolve());
            api.cancelAllRequests();
            expect(api.pendingRequests.size).toBe(0);
        });
    });
});
