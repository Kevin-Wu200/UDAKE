/**
 * 缓存系统单元测试
 * 测试SmartCache、TwoLevelCache和缓存策略
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { SmartCache } from '../apps/frontend/js/utils/cache/SmartCache';
import { TwoLevelCache } from '../apps/frontend/js/utils/cache/TwoLevelCache';
import { LRUStrategy, FIFOStrategy, LFUStrategy, TimeDecayStrategy, HybridStrategy } from '../apps/frontend/js/utils/cache/CacheStrategy';

describe('SmartCache', () => {
  let cache;

  beforeEach(() => {
    cache = new SmartCache({
      maxSize: 5,
      ttl: 1000,
      strategy: 'lru',
      persistence: false
    });
  });

  afterEach(() => {
    cache.destroy();
  });

  describe('基础功能', () => {
    it('应该能够设置和获取值', () => {
      cache.set('key1', 'value1');
      expect(cache.get('key1')).toBe('value1');
    });

    it('应该能够删除值', () => {
      cache.set('key1', 'value1');
      cache.delete('key1');
      expect(cache.get('key1')).toBeUndefined();
    });

    it('应该能够清空缓存', () => {
      cache.set('key1', 'value1');
      cache.set('key2', 'value2');
      cache.clear();
      expect(cache.size()).toBe(0);
    });

    it('应该能够检查键是否存在', () => {
      expect(cache.has('key1')).toBe(false);
      cache.set('key1', 'value1');
      expect(cache.has('key1')).toBe(true);
    });

    it('应该能够获取所有键', () => {
      cache.set('key1', 'value1');
      cache.set('key2', 'value2');
      const keys = cache.keys();
      expect(keys).toContain('key1');
      expect(keys).toContain('key2');
    });

    it('应该能够获取所有值', () => {
      cache.set('key1', 'value1');
      cache.set('key2', 'value2');
      const values = cache.values();
      expect(values).toContain('value1');
      expect(values).toContain('value2');
    });
  });

  describe('过期机制', () => {
    it('应该在过期后返回undefined', async () => {
      cache.set('key1', 'value1', 100); // 100ms TTL
      await new Promise(resolve => setTimeout(resolve, 150));
      expect(cache.get('key1')).toBeUndefined();
    });

    it('应该支持自定义TTL', () => {
      cache.set('key1', 'value1', 5000); // 5秒
      cache.set('key2', 'value2', 100); // 100ms
      expect(cache.has('key1')).toBe(true);
      expect(cache.has('key2')).toBe(true);
    });
  });

  describe('容量与策略', () => {
    it('LRU 应淘汰最久未访问的数据', () => {
      const lruCache = new SmartCache({
        maxSize: 2,
        ttl: 5000,
        strategy: 'lru',
        persistence: false
      });

      lruCache.set('a', 'A');
      lruCache.set('b', 'B');
      lruCache.get('a');
      lruCache.set('c', 'C');

      expect(lruCache.get('a')).toBe('A');
      expect(lruCache.get('b')).toBeUndefined();
      expect(lruCache.get('c')).toBe('C');
      lruCache.destroy();
    });

    it('FIFO 应淘汰最早写入的数据', () => {
      const fifoCache = new SmartCache({
        maxSize: 2,
        ttl: 5000,
        strategy: 'fifo',
        persistence: false
      });

      fifoCache.set('a', 'A');
      fifoCache.set('b', 'B');
      fifoCache.get('a');
      fifoCache.set('c', 'C');

      expect(fifoCache.get('a')).toBeUndefined();
      expect(fifoCache.get('b')).toBe('B');
      expect(fifoCache.get('c')).toBe('C');
      fifoCache.destroy();
    });

    it('应遵守内存上限并统计内存占用', () => {
      const memCache = new SmartCache({
        maxSize: 10,
        ttl: 5000,
        strategy: 'lru',
        persistence: false,
        maxMemoryBytes: 120
      });

      memCache.set('a', 'a'.repeat(20)); // 约40字节
      memCache.set('b', 'b'.repeat(20)); // 约40字节
      memCache.set('c', 'c'.repeat(20)); // 约40字节
      memCache.set('d', 'd'.repeat(20)); // 触发回收

      const stats = memCache.getStats();
      expect(stats.memoryUsage).toBeLessThanOrEqual(120);
      expect(stats.maxMemoryBytes).toBe(120);
      memCache.destroy();
    });
  });

  describe('统计信息', () => {
    it('应该正确记录命中和未命中', () => {
      cache.set('key1', 'value1');
      cache.get('key1'); // 命中
      cache.get('key2'); // 未命中

      const stats = cache.getStats();
      expect(stats.hits).toBe(1);
      expect(stats.misses).toBe(1);
      expect(stats.hitRate).toBe(0.5);
    });

    it('应该能够重置统计信息', () => {
      cache.set('key1', 'value1');
      cache.get('key1');
      cache.resetStats();

      const stats = cache.getStats();
      expect(stats.hits).toBe(0);
      expect(stats.misses).toBe(0);
    });
  });

  describe('事件监听', () => {
    it('应该触发hit事件', () => {
      let hitEventTriggered = false;
      cache.on('hit', (event, key) => {
        hitEventTriggered = true;
        expect(key).toBe('key1');
      });

      cache.set('key1', 'value1');
      cache.get('key1');
      expect(hitEventTriggered).toBe(true);
    });

    it('应该触发miss事件', () => {
      let missEventTriggered = false;
      cache.on('miss', (event, key) => {
        missEventTriggered = true;
        expect(key).toBe('key1');
      });

      cache.get('key1');
      expect(missEventTriggered).toBe(true);
    });

    it('应该触发set事件', () => {
      let setEventTriggered = false;
      cache.on('set', (event, key, entry) => {
        setEventTriggered = true;
        expect(key).toBe('key1');
        expect(entry.value).toBe('value1');
      });

      cache.set('key1', 'value1');
      expect(setEventTriggered).toBe(true);
    });

    it('应该触发delete事件', () => {
      let deleteEventTriggered = false;
      cache.on('delete', (event, key) => {
        deleteEventTriggered = true;
        expect(key).toBe('key1');
      });

      cache.set('key1', 'value1');
      cache.delete('key1');
      expect(deleteEventTriggered).toBe(true);
    });

    it('destroy后应停止触发事件并拒绝新增监听器', () => {
      let triggerCount = 0;
      const listener = () => {
        triggerCount++;
      };
      cache.on('set', listener);
      cache.set('k1', 'v1');
      expect(triggerCount).toBe(1);

      cache.destroy();
      cache.on('set', () => {
        triggerCount += 100;
      });
      cache.set('k2', 'v2');
      expect(triggerCount).toBe(1);
    });
  });

  describe('持久化错误处理', () => {
    it('应通过回调和事件上报持久化失败', () => {
      const persistenceErrors = [];
      const eventErrors = [];
      vi.stubGlobal('localStorage', {
        getItem: () => null,
        setItem: () => {
          throw new Error('quota exceeded');
        },
        removeItem: () => {},
        clear: () => {}
      });

      const persistentCache = new SmartCache({
        maxSize: 3,
        ttl: 1000,
        strategy: 'lru',
        persistence: true,
        storageKey: 'smart-cache-test',
        onPersistenceError: (operation, error) => {
          persistenceErrors.push({ operation, error });
        }
      });
      persistentCache.on('persistence-error', (event, key) => {
        eventErrors.push({ event, key });
      });

      persistentCache.set('k1', 'v1');

      const stats = persistentCache.getStats();
      expect(stats.persistenceErrorCount).toBe(1);
      expect(persistenceErrors).toHaveLength(1);
      expect(persistenceErrors[0].operation).toBe('save');
      expect(eventErrors).toContainEqual({ event: 'persistence-error', key: 'save' });

      persistentCache.destroy();
      vi.unstubAllGlobals();
    });
  });

  describe('健康状态', () => {
    it('应该在健康时返回isHealthy=true', () => {
      cache.set('key1', 'value1');
      cache.get('key1'); // 提高命中率

      const health = cache.getHealthStatus();
      expect(health.isHealthy).toBe(true);
    });

    it('应该在命中率低时返回isHealthy=false', () => {
      cache.get('key1');
      cache.get('key2');
      cache.get('key3'); // 0/3 命中率

      const health = cache.getHealthStatus();
      expect(health.isHealthy).toBe(false);
      expect(health.recommendations).toContain('缓存命中率较低，建议增加TTL或调整缓存大小');
    });
  });
});

describe('TwoLevelCache', () => {
  let cache;

  beforeEach(() => {
    cache = new TwoLevelCache(
      {
        maxSize: 3,
        ttl: 1000,
        strategy: 'lru'
      },
      {
        maxSize: 10,
        ttl: 5000,
        strategy: 'lfu',
        persistence: false
      }
    );
  });

  afterEach(() => {
    cache.destroy();
  });

  describe('基础功能', () => {
    it('应该能够设置和获取值', async () => {
      await cache.set('key1', 'value1');
      const value = await cache.get('key1');
      expect(value).toBe('value1');
    });

    it('应该能够删除值', async () => {
      await cache.set('key1', 'value1');
      await cache.delete('key1');
      const value = await cache.get('key1');
      expect(value).toBeUndefined();
    });

    it('应该能够清空缓存', async () => {
      await cache.set('key1', 'value1');
      await cache.set('key2', 'value2');
      await cache.clear();
      const size = cache.size();
      expect(size).toBe(0);
    });

    it('应该能够检查键是否存在', async () => {
      expect(await cache.has('key1')).toBe(false);
      await cache.set('key1', 'value1');
      expect(await cache.has('key1')).toBe(true);
    });
  });

  describe('双层缓存协作', () => {
    it('应该先从内存缓存获取', async () => {
      await cache.set('key1', 'value1');
      const value = await cache.get('key1');

      // 应该从内存缓存获取
      const stats = cache.getStats();
      expect(stats.memory.hits).toBeGreaterThan(0);
    });

    it('应该支持提升数据到内存', async () => {
      await cache.set('key1', 'value1');
      await cache.promoteToMemory('key1');

      const stats = cache.getStats();
      expect(stats.promotionCount).toBeGreaterThan(0);
    });

    it('应该支持降级数据到磁盘', async () => {
      await cache.set('key1', 'value1');
      await cache.demoteToDisk('key1');

      const value = await cache.get('key1');
      expect(value).toBe('value1');
    });
  });

  describe('统计信息', () => {
    it('应该正确记录内存和磁盘缓存统计', async () => {
      await cache.set('key1', 'value1');
      await cache.get('key1');
      await cache.get('key2'); // 未命中

      const stats = cache.getStats();
      expect(stats.memory.hits).toBe(1);
      expect(stats.total.hits).toBe(1);
      // 由于自动提升机制，可能会有额外的未命中
      expect(stats.total.misses).toBeGreaterThanOrEqual(1);
    });

    it('应该能够重置统计信息', async () => {
      await cache.set('key1', 'value1');
      await cache.get('key1');
      cache.resetStats();

      const stats = cache.getStats();
      expect(stats.memory.hits).toBe(0);
      expect(stats.disk.hits).toBe(0);
      expect(stats.total.persistenceErrorCount).toBe(0);
    });
  });

  describe('持久化错误处理', () => {
    it('应统计并通知磁盘层持久化失败', async () => {
      const captured = [];
      vi.stubGlobal('localStorage', {
        getItem: () => null,
        setItem: () => {
          throw new Error('quota exceeded');
        },
        removeItem: () => {},
        clear: () => {}
      });
      const persistentCache = new TwoLevelCache(
        {
          maxSize: 3,
          ttl: 1000,
          strategy: 'lru'
        },
        {
          maxSize: 10,
          ttl: 5000,
          strategy: 'lfu',
          persistence: true
        }
      );
      const unsubscribe = persistentCache.onPersistenceError((operation) => {
        captured.push(operation);
      });

      await persistentCache.set('key-persist', 'value-persist');

      const stats = persistentCache.getStats();
      expect(stats.total.persistenceErrorCount).toBeGreaterThan(0);
      expect(captured).toContain('save');

      unsubscribe();
      persistentCache.destroy();
      vi.unstubAllGlobals();
    });
  });

  describe('命中率优化', () => {
    it('应该通过行为预测预取将命中率提升到85%以上', async () => {
      const dataSource = new Map([
        ['next:1', 'value-next-1']
      ]);
      let loaderCalls = 0;

      cache.configurePrefetch(async (key) => {
        loaderCalls++;
        await new Promise(resolve => setTimeout(resolve, 1));
        return dataSource.get(key);
      }, {
        prefetchBatchSize: 1,
        prefetchMinConfidence: 0.6
      });

      await cache.set('start:1', 'value-start-1');

      // 建立访问模式：start:1 -> next:1
      for (let i = 0; i < 6; i++) {
        await cache.get('start:1');
        await cache.get('next:1');
      }

      await cache.delete('next:1');
      cache.resetStats();

      for (let i = 0; i < 20; i++) {
        await cache.get('start:1');
        await new Promise(resolve => setTimeout(resolve, 5)); // 等待空闲预取调度
        await cache.get('next:1');
      }

      const stats = cache.getStats();
      expect(loaderCalls).toBeGreaterThan(0);
      expect(stats.total.hitRate).toBeGreaterThan(0.85);
    });
  });

  describe('批量操作', () => {
    it('应该支持批量预热', async () => {
      const entries = new Map([
        ['key1', 'value1'],
        ['key2', 'value2'],
        ['key3', 'value3']
      ]);

      await cache.warmup(entries);

      expect(await cache.has('key1')).toBe(true);
      expect(await cache.has('key2')).toBe(true);
      expect(await cache.has('key3')).toBe(true);
    });

    it('应该支持模式匹配失效', async () => {
      await cache.set('user:1', 'user1');
      await cache.set('user:2', 'user2');
      await cache.set('product:1', 'product1');

      await cache.invalidatePattern('user:');

      expect(await cache.has('user:1')).toBe(false);
      expect(await cache.has('user:2')).toBe(false);
      expect(await cache.has('product:1')).toBe(true);
    });
  });
});

describe('缓存策略', () => {
  describe('LRUStrategy', () => {
    it('应该淘汰最久未使用的条目', () => {
      const strategy = new LRUStrategy(3);

      const entry1 = { timestamp: Date.now() - 3000, accessCount: 5, lastAccessTime: Date.now() - 3000, expiresAt: Date.now() + 10000 };
      const entry2 = { timestamp: Date.now() - 2000, accessCount: 3, lastAccessTime: Date.now() - 2000, expiresAt: Date.now() + 10000 };
      const entry3 = { timestamp: Date.now() - 1000, accessCount: 2, lastAccessTime: Date.now() - 1000, expiresAt: Date.now() + 10000 };

      strategy.onInsert(entry1, 'key1');
      strategy.onInsert(entry2, 'key2');
      strategy.onInsert(entry3, 'key3');

      // 访问key3，使其成为最近使用的
      strategy.onAccess(entry3, 'key3');

      const evictKey = strategy.getEvictionKey();
      expect(evictKey).toBe('key1'); // key1是最久未使用的
    });
  });

  describe('FIFOStrategy', () => {
    it('应该返回最早插入的键', () => {
      const strategy = new FIFOStrategy(3);
      const entry1 = { value: 'v1', timestamp: 1, accessCount: 0, lastAccessTime: 1, expiresAt: Date.now() + 1000 };
      const entry2 = { value: 'v2', timestamp: 2, accessCount: 0, lastAccessTime: 2, expiresAt: Date.now() + 1000 };
      const entry3 = { value: 'v3', timestamp: 3, accessCount: 0, lastAccessTime: 3, expiresAt: Date.now() + 1000 };

      strategy.onInsert(entry1, 'key1');
      strategy.onInsert(entry2, 'key2');
      strategy.onAccess(entry1, 'key1');
      strategy.onInsert(entry3, 'key3');

      expect(strategy.getEvictionKey()).toBe('key1');
    });
  });

  describe('LFUStrategy', () => {
    it('应该淘汰访问频率最低的条目', () => {
      const strategy = new LFUStrategy();

      const entry1 = { timestamp: Date.now(), accessCount: 1, lastAccessTime: Date.now(), expiresAt: Date.now() + 10000 };
      const entry2 = { timestamp: Date.now(), accessCount: 3, lastAccessTime: Date.now(), expiresAt: Date.now() + 10000 };
      const entry3 = { timestamp: Date.now(), accessCount: 5, lastAccessTime: Date.now(), expiresAt: Date.now() + 10000 };

      strategy.onInsert(entry1, 'key1');
      strategy.onInsert(entry2, 'key2');
      strategy.onInsert(entry3, 'key3');

      // 访问key2和key3，增加它们的频率
      strategy.onAccess(entry2, 'key2');
      strategy.onAccess(entry3, 'key3');
      strategy.onAccess(entry3, 'key3');

      const evictKey = strategy.getEvictionKey();
      expect(evictKey).toBe('key1'); // key1的访问频率最低
    });
  });

  describe('TimeDecayStrategy', () => {
    it('应该基于时间和访问频率进行淘汰', () => {
      const strategy = new TimeDecayStrategy(0.95, 0.5);

      const oldEntry = {
        timestamp: Date.now() - 3600000, // 1小时前
        accessCount: 10,
        lastAccessTime: Date.now() - 3600000,
        expiresAt: Date.now() + 10000
      };

      const shouldEvict = strategy.shouldEvict(oldEntry);
      expect(shouldEvict).toBe(true);
    });
  });

  describe('HybridStrategy', () => {
    it('应该综合多种策略进行淘汰', () => {
      const strategy = new HybridStrategy(3);

      const entry1 = { timestamp: Date.now() - 3000, accessCount: 1, lastAccessTime: Date.now() - 3000, expiresAt: Date.now() + 10000 };
      const entry2 = { timestamp: Date.now() - 2000, accessCount: 3, lastAccessTime: Date.now() - 2000, expiresAt: Date.now() + 10000 };
      const entry3 = { timestamp: Date.now() - 1000, accessCount: 5, lastAccessTime: Date.now() - 1000, expiresAt: Date.now() + 10000 };

      strategy.onInsert(entry1, 'key1');
      strategy.onInsert(entry2, 'key2');
      strategy.onInsert(entry3, 'key3');

      // 访问key3，使其成为综合评分最高的
      strategy.onAccess(entry3, 'key3');

      const evictKey = strategy.getEvictionKey();
      // key1应该被淘汰（最久未使用且访问频率低）
      expect(evictKey).toBe('key1');
    });
  });
});
