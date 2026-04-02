import { describe, it, expect } from 'vitest';
import { CacheManager } from '../apps/frontend/js/utils/cache/CacheManager';

describe('CacheManager', () => {
  it('应能统一创建并管理 two-level 缓存', async () => {
    const manager = new CacheManager();

    const cache = manager.create('api', {
      type: 'two-level',
      memoryConfig: {
        maxSize: 2,
        strategy: 'fifo',
        ttl: 1000
      },
      diskConfig: {
        maxSize: 4,
        strategy: 'lfu',
        ttl: 2000,
        persistence: false
      },
      options: {
        enableAutoPromote: true,
        promoteThreshold: 2
      }
    });

    await cache.set('k1', 'v1');
    await cache.set('k2', 'v2');

    expect(await cache.get('k1')).toBe('v1');
    expect(manager.get('api')).toBeDefined();

    const stats = manager.getAllStats();
    expect(stats.api).toBeDefined();

    await manager.clearAll();
    manager.destroy();
  });
});
