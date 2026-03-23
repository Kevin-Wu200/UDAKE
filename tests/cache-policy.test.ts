import { describe, it, expect } from 'vitest';
import { buildCacheKey, getApiCacheTTL, shouldUseApiCache } from '../apps/frontend/js/utils/cache/CachePolicy';

describe('CachePolicy', () => {
    it('应生成稳定缓存键', () => {
        const key1 = buildCacheKey({
            namespace: 'api',
            method: 'GET',
            url: '/api/config/all',
            version: '2026-03'
        });
        const key2 = buildCacheKey({
            namespace: 'api',
            method: 'GET',
            url: '/api/config/all',
            version: '2026-03'
        });
        expect(key1).toBe(key2);
    });

    it('应识别可缓存接口与TTL', () => {
        expect(shouldUseApiCache('GET', '/api/config/all')).toBe(true);
        expect(getApiCacheTTL('/api/config/all')).toBe(10 * 60 * 1000);

        expect(shouldUseApiCache('POST', '/api/config/all')).toBe(false);
    });
});
