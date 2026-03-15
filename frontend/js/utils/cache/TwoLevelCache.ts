/**
 * 双层缓存实现
 * 内存缓存 + 磁盘缓存，自动提升热门数据
 */

import { SmartCache } from './SmartCache';
import type { CacheConfig, TwoLevelCacheStats, TwoLevelCacheConfig } from '../../types/cache';

export class TwoLevelCache<K = string, V = any> {
  private memoryCache: SmartCache<K, V>;
  private diskCache: SmartCache<K, V>;
  private memoryToDiskPromoter: Map<K, number>;
  private promotionCount: number = 0;
  private enableAutoPromote: boolean;
  private promoteThreshold: number;
  private isDestroyed: boolean = false;

  constructor(
    memoryConfig: Partial<CacheConfig> = {},
    diskConfig: Partial<CacheConfig> = {},
    options?: Partial<TwoLevelCacheConfig>
  ) {
    // 内存缓存：快速访问，容量小
    this.memoryCache = new SmartCache<K, V>({
      maxSize: memoryConfig.maxSize || 50,
      ttl: memoryConfig.ttl || 5 * 60 * 1000, // 5分钟
      strategy: memoryConfig.strategy || 'lru',
      persistence: false,
      enableStats: true
    });

    // 磁盘缓存：慢速访问，容量大
    this.diskCache = new SmartCache<K, V>({
      maxSize: diskConfig.maxSize || 500,
      ttl: diskConfig.ttl || 60 * 60 * 1000, // 1小时
      strategy: diskConfig.strategy || 'lfu',
      persistence: true,
      storageKey: diskConfig.storageKey || 'disk-cache',
      enableStats: true
    });

    // 提升追踪
    this.memoryToDiskPromoter = new Map();
    this.enableAutoPromote = options?.enableAutoPromote !== false;
    this.promoteThreshold = options?.promoteThreshold || 3;

    // 监听内存缓存的访问事件
    this.memoryCache.on('hit', (_event, key) => {
      this._trackAccess(key);
    });
  }

  /**
   * 获取缓存值
   */
  async get(key: K): Promise<V | undefined> {
    if (this.isDestroyed) {
      console.warn('[TwoLevelCache] 缓存已销毁，无法获取值');
      return undefined;
    }

    // 先查内存缓存
    let value = this.memoryCache.get(key);

    if (value !== undefined) {
      return value;
    }

    // 再查磁盘缓存
    value = this.diskCache.get(key);

    if (value !== undefined) {
      // 提升到内存缓存
      if (this.enableAutoPromote) {
        await this.promoteToMemory(key, value);
      }
      return value;
    }

    return undefined;
  }

  /**
   * 设置缓存值
   */
  async set(key: K, value: V): Promise<void> {
    if (this.isDestroyed) {
      console.warn('[TwoLevelCache] 缓存已销毁，无法设置值');
      return;
    }

    // 同时写入两层缓存
    this.memoryCache.set(key, value);
    this.diskCache.set(key, value);

    // 重置访问计数
    this.memoryToDiskPromoter.set(key, 0);
  }

  /**
   * 删除缓存值
   */
  async delete(key: K): Promise<void> {
    if (this.isDestroyed) {
      console.warn('[TwoLevelCache] 缓存已销毁，无法删除值');
      return;
    }

    this.memoryCache.delete(key);
    this.diskCache.delete(key);
    this.memoryToDiskPromoter.delete(key);
  }

  /**
   * 清空所有缓存
   */
  async clear(): Promise<void> {
    if (this.isDestroyed) {
      console.warn('[TwoLevelCache] 缓存已销毁，无法清空');
      return;
    }

    this.memoryCache.clear();
    this.diskCache.clear();
    this.memoryToDiskPromoter.clear();
    this.promotionCount = 0;
  }

  /**
   * 检查键是否存在
   */
  async has(key: K): Promise<boolean> {
    if (this.isDestroyed) {
      return false;
    }

    return this.memoryCache.has(key) || this.diskCache.has(key);
  }

  /**
   * 获取所有键
   */
  keys(): K[] {
    if (this.isDestroyed) {
      return [];
    }

    const memoryKeys = this.memoryCache.keys();
    const diskKeys = this.diskCache.keys();

    // 合并并去重
    const allKeys = new Set<K>([...memoryKeys, ...diskKeys]);
    return Array.from(allKeys);
  }

  /**
   * 获取缓存大小
   */
  size(): number {
    if (this.isDestroyed) {
      return 0;
    }

    const memorySize = this.memoryCache.size();
    const diskSize = this.diskCache.size();

    // 去重计数
    const uniqueKeys = new Set<K>([...this.memoryCache.keys(), ...this.diskCache.keys()]);
    return uniqueKeys.size;
  }

  /**
   * 提升数据到内存缓存
   */
  async promoteToMemory(key: K, value?: V): Promise<void> {
    if (this.isDestroyed) {
      return;
    }

    if (value === undefined) {
      value = this.diskCache.get(key);
    }

    if (value !== undefined) {
      this.memoryCache.set(key, value);
      this.promotionCount++;
    }
  }

  /**
   * 降级数据到磁盘缓存
   */
  async demoteToDisk(key: K): Promise<void> {
    if (this.isDestroyed) {
      return;
    }

    const value = this.memoryCache.get(key);
    if (value !== undefined) {
      this.diskCache.set(key, value);
      this.memoryCache.delete(key);
      this.memoryToDiskPromoter.set(key, 0);
    }
  }

  /**
   * 获取统计信息
   */
  getStats(): TwoLevelCacheStats {
    const memoryStats = this.memoryCache.getStats();
    const diskStats = this.diskCache.getStats();
    const totalHits = memoryStats.hits + diskStats.hits;
    const totalMisses = memoryStats.misses + diskStats.misses;
    const total = totalHits + totalMisses;

    return {
      memory: memoryStats,
      disk: diskStats,
      total: {
        hits: totalHits,
        misses: totalMisses,
        size: this.size(),
        hitRate: total > 0 ? totalHits / total : 0,
        evictionCount: memoryStats.evictionCount + diskStats.evictionCount,
        totalRequests: memoryStats.totalRequests + diskStats.totalRequests,
        avgResponseTime: this._calculateAvgResponseTime(memoryStats, diskStats)
      },
      promotionCount: this.promotionCount
    };
  }

  /**
   * 重置统计信息
   */
  resetStats(): void {
    this.memoryCache.resetStats();
    this.diskCache.resetStats();
    this.promotionCount = 0;
  }

  /**
   * 批量预热缓存
   */
  async warmup(entries: Map<K, V>): Promise<void> {
    if (this.isDestroyed) {
      console.warn('[TwoLevelCache] 缓存已销毁，无法预热');
      return;
    }

    console.log(`[TwoLevelCache] 开始预热 ${entries.size} 条数据...`);

    for (const [key, value] of entries.entries()) {
      await this.set(key, value);
    }

    console.log('[TwoLevelCache] 预热完成');
  }

  /**
   * 失效匹配模式的缓存
   */
  async invalidatePattern(pattern: string): Promise<void> {
    if (this.isDestroyed) {
      console.warn('[TwoLevelCache] 缓存已销毁，无法失效');
      return;
    }

    const regex = new RegExp(pattern);
    const keys = this.keys();

    for (const key of keys) {
      if (regex.test(String(key))) {
        await this.delete(key);
      }
    }
  }

  /**
   * 获取内存缓存健康状态
   */
  getMemoryHealth() {
    return this.memoryCache.getHealthStatus();
  }

  /**
   * 获取磁盘缓存健康状态
   */
  getDiskHealth() {
    return this.diskCache.getHealthStatus();
  }

  /**
   * 获取提升统计
   */
  getPromotionStats(): {
    totalPromotions: number;
    hotKeys: Array<{ key: K; accessCount: number }>;
  } {
    const hotKeys = Array.from(this.memoryToDiskPromoter.entries())
      .filter(([, count]) => count >= this.promoteThreshold)
      .map(([key, count]) => ({ key, accessCount: count }))
      .sort((a, b) => b.accessCount - a.accessCount)
      .slice(0, 10); // 只返回前10个热门键

    return {
      totalPromotions: this.promotionCount,
      hotKeys
    };
  }

  /**
   * 销毁缓存
   */
  destroy(): void {
    if (this.isDestroyed) {
      return;
    }

    this.isDestroyed = true;
    this.memoryCache.destroy();
    this.diskCache.destroy();
    this.memoryToDiskPromoter.clear();
  }

  /**
   * 追踪访问
   */
  private _trackAccess(key: K): void {
    const currentCount = this.memoryToDiskPromoter.get(key) || 0;
    this.memoryToDiskPromoter.set(key, currentCount + 1);
  }

  /**
   * 计算平均响应时间
   */
  private _calculateAvgResponseTime(
    memoryStats: any,
    diskStats: any
  ): number {
    const totalRequests = memoryStats.totalRequests + diskStats.totalRequests;
    if (totalRequests === 0) return 0;

    const weightedMemory = memoryStats.avgResponseTime * memoryStats.totalRequests;
    const weightedDisk = diskStats.avgResponseTime * diskStats.totalRequests;

    return (weightedMemory + weightedDisk) / totalRequests;
  }
}