/**
 * 智能缓存实现
 * 支持多种策略、持久化、统计和事件监听
 */

import type {
  CacheEntry,
  CacheConfig,
  CacheStats,
  CacheEventListener,
  CacheEventType,
  CacheHealthStatus
} from '../../types/cache';
import { CacheStrategyFactory } from './CacheStrategy';

export class SmartCache<K = string, V = any> {
  private cache: Map<K, CacheEntry<V>>;
  private config: CacheConfig;
  private strategy: any;
  private stats: CacheStats;
  private cleanupTimer: number | null = null;
  private eventListeners: Map<CacheEventType, Set<CacheEventListener>>;
  private responseTimeHistory: number[] = [];
  private isDestroyed: boolean = false;
  private accessFrequency: Map<K, number> = new Map();
  private accessTransitions: Map<K, Map<K, number>> = new Map();
  private lastAccessedKey: K | null = null;
  private pendingWarmups: Set<string> = new Set();

  constructor(config: Partial<CacheConfig> = {}) {
    this.cache = new Map();
    this.config = {
      maxSize: config.maxSize || 100,
      ttl: config.ttl || 5 * 60 * 1000, // 5分钟
      strategy: config.strategy || 'hybrid',
      persistence: config.persistence || false,
      storageKey: config.storageKey || 'smart-cache',
      enableStats: config.enableStats !== false,
      enableAutoCleanup: config.enableAutoCleanup !== false,
      cleanupInterval: config.cleanupInterval || 60 * 1000 // 1分钟
    };

    // 初始化策略
    this.strategy = CacheStrategyFactory.create(
      this.config.strategy,
      this.config.maxSize
    );

    // 初始化统计信息
    this.stats = {
      hits: 0,
      misses: 0,
      size: 0,
      hitRate: 0,
      evictionCount: 0,
      totalRequests: 0,
      avgResponseTime: 0
    };

    // 初始化事件监听器
    this.eventListeners = new Map();
    const eventTypes: CacheEventType[] = ['hit', 'miss', 'set', 'delete', 'evict', 'clear', 'expire'];
    eventTypes.forEach(type => {
      this.eventListeners.set(type, new Set());
    });

    // 加载持久化缓存
    if (this.config.persistence) {
      this.loadFromPersistence();
    }

    // 启动定期清理
    if (this.config.enableAutoCleanup) {
      this.startCleanup();
    }
  }

  /**
   * 获取缓存值
   */
  get(key: K): V | undefined {
    if (this.isDestroyed) {
      console.warn('[SmartCache] 缓存已销毁，无法获取值');
      return undefined;
    }

    const startTime = Date.now();
    this._recordAccessPattern(key);
    const entry = this.cache.get(key);

    if (!entry) {
      this._onEvent('miss', String(key));
      if (this.config.enableStats) {
        this.stats.misses++;
        this.stats.totalRequests++;
        this._updateHitRate();
        this._updateResponseTime(startTime);
      }
      return undefined;
    }

    // 检查是否过期
    if (Date.now() > entry.expiresAt) {
      this.delete(key);
      this._onEvent('expire', String(key), entry);
      if (this.config.enableStats) {
        this.stats.misses++;
        this.stats.totalRequests++;
        this._updateHitRate();
        this._updateResponseTime(startTime);
      }
      return undefined;
    }

    // 更新访问信息
    this.strategy.onAccess(entry, String(key));
    entry.lastAccessTime = Date.now();

    this._onEvent('hit', String(key), entry);
    if (this.config.enableStats) {
      this.stats.hits++;
      this.stats.totalRequests++;
      this._updateHitRate();
      this._updateResponseTime(startTime);
    }

    return entry.value;
  }

  /**
   * 设置缓存值
   */
  set(key: K, value: V, customTTL?: number): void {
    if (this.isDestroyed) {
      console.warn('[SmartCache] 缓存已销毁，无法设置值');
      return;
    }

    const ttl = customTTL ?? this.config.ttl;
    const expiresAt = Date.now() + ttl;
    const size = this._calculateSize(value);

    const entry: CacheEntry<V> = {
      value,
      timestamp: Date.now(),
      accessCount: 0,
      lastAccessTime: Date.now(),
      expiresAt,
      size
    };

    // 如果缓存已满，执行淘汰
    const effectiveMaxSize = this._getEffectiveMaxSize();
    if (this.cache.size >= effectiveMaxSize && !this.cache.has(key)) {
      // 在高频写入场景下避免每次全量扫描过期项，优先执行策略淘汰
      this.evict({ checkExpired: false });
    }

    this.cache.set(key, entry);
    this.strategy.onInsert(entry, String(key));

    if (this.config.enableStats) {
      this.stats.size = this.cache.size;
    }

    this._onEvent('set', String(key), entry);

    // 持久化
    if (this.config.persistence) {
      this.saveToPersistence();
    }
  }

  /**
   * 删除缓存值
   */
  delete(key: K): boolean {
    if (this.isDestroyed) {
      console.warn('[SmartCache] 缓存已销毁，无法删除值');
      return false;
    }

    const entry = this.cache.get(key);
    const deleted = this.cache.delete(key);

    if (deleted) {
      this._rebuildStrategyIndex();
      if (this.config.enableStats) {
        this.stats.size = this.cache.size;
      }
      this._onEvent('delete', String(key), entry);
    }

    return deleted;
  }

  /**
   * 清空缓存
   */
  clear(): void {
    if (this.isDestroyed) {
      console.warn('[SmartCache] 缓存已销毁，无法清空');
      return;
    }

    this.cache.clear();
    this.accessTransitions.clear();
    this.accessFrequency.clear();
    this.lastAccessedKey = null;
    this.pendingWarmups.clear();
    this.strategy.clear();

    if (this.config.enableStats) {
      this.stats.size = 0;
    }

    if (this.config.persistence) {
      this.clearPersistence();
    }

    this._onEvent('clear', '', undefined);
  }

  /**
   * 检查键是否存在
   */
  has(key: K): boolean {
    if (this.isDestroyed) {
      return false;
    }

    const entry = this.cache.get(key);
    if (!entry) {
      return false;
    }

    // 检查是否过期
    if (Date.now() > entry.expiresAt) {
      this.delete(key);
      return false;
    }

    return true;
  }

  /**
   * 获取所有键
   */
  keys(): K[] {
    if (this.isDestroyed) {
      return [];
    }

    const validKeys: K[] = [];
    const now = Date.now();

    this.cache.forEach((entry, key) => {
      if (now <= entry.expiresAt) {
        validKeys.push(key);
      }
    });

    return validKeys;
  }

  /**
   * 获取所有值
   */
  values(): V[] {
    if (this.isDestroyed) {
      return [];
    }

    const validValues: V[] = [];
    const now = Date.now();

    this.cache.forEach((entry) => {
      if (now <= entry.expiresAt) {
        validValues.push(entry.value);
      }
    });

    return validValues;
  }

  /**
   * 获取缓存大小
   */
  size(): number {
    if (this.isDestroyed) {
      return 0;
    }

    let count = 0;
    const now = Date.now();

    this.cache.forEach((entry) => {
      if (now <= entry.expiresAt) {
        count++;
      }
    });

    return count;
  }

  /**
   * 执行缓存淘汰
   */
  evict(options: { checkExpired?: boolean } = {}): void {
    if (this.isDestroyed) {
      return;
    }

    const shouldCheckExpired = options.checkExpired !== false;

    let strategyChanged = false;

    if (shouldCheckExpired) {
      // 检查过期项
      const now = Date.now();
      for (const [key, entry] of this.cache.entries()) {
        if (now > entry.expiresAt) {
          this.cache.delete(key);
          strategyChanged = true;
          if (this.config.enableStats) {
            this.stats.evictionCount++;
          }
          this._onEvent('expire', String(key), entry);
        }
      }
    }

    // 如果仍然超出限制，使用策略淘汰
    const effectiveMaxSize = this._getEffectiveMaxSize();
    if (this.cache.size >= effectiveMaxSize) {
      const evictKey = this.strategy.getEvictionKey();
      if (evictKey) {
        const entry = this.cache.get(evictKey as K);
        const deleted = this.cache.delete(evictKey as K);
        if (deleted) {
          strategyChanged = true;
        }
        if (this.config.enableStats) {
          this.stats.evictionCount++;
        }
        this._onEvent('evict', evictKey, entry);
      }
    }

    if (strategyChanged) {
      this._rebuildStrategyIndex();
    }

    if (this.config.enableStats) {
      this.stats.size = this.cache.size;
    }
  }

  /**
   * 添加事件监听器
   */
  on(event: CacheEventType, listener: CacheEventListener): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      listeners.add(listener);
    }
  }

  /**
   * 移除事件监听器
   */
  off(event: CacheEventType, listener: CacheEventListener): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      listeners.delete(listener);
    }
  }

  /**
   * 获取高频访问键（用于预热）
   */
  getHotKeys(limit: number = 10): K[] {
    return Array.from(this.accessFrequency.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, Math.max(1, limit))
      .map(([key]) => key);
  }

  /**
   * 基于访问转移概率预测下一个高频键
   */
  predictNextKeys(currentKey: K, limit: number = 5, minConfidence: number = 0.25): K[] {
    const transitions = this.accessTransitions.get(currentKey);
    if (!transitions || transitions.size === 0) {
      return [];
    }

    const total = Array.from(transitions.values()).reduce((sum, count) => sum + count, 0);
    if (total <= 0) {
      return [];
    }

    return Array.from(transitions.entries())
      .map(([key, count]) => ({ key, confidence: count / total }))
      .filter(item => item.confidence >= minConfidence)
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, Math.max(1, limit))
      .map(item => item.key);
  }

  /**
   * 批量预热指定键
   */
  async warmupByKeys(
    keys: K[],
    loader: (key: K) => Promise<V | undefined> | V | undefined,
    customTTL?: number
  ): Promise<{ loaded: number; skipped: number }> {
    if (this.isDestroyed) {
      return { loaded: 0, skipped: keys.length };
    }

    let loaded = 0;
    let skipped = 0;

    for (const key of keys) {
      const pendingKey = String(key);
      if (this.has(key) || this.pendingWarmups.has(pendingKey)) {
        skipped++;
        continue;
      }

      this.pendingWarmups.add(pendingKey);
      try {
        const value = await loader(key);
        if (value !== undefined) {
          this.set(key, value, customTTL);
          loaded++;
        } else {
          skipped++;
        }
      } catch {
        skipped++;
      } finally {
        this.pendingWarmups.delete(pendingKey);
      }
    }

    return { loaded, skipped };
  }

  /**
   * 在空闲时间进行预测预热，降低主流程开销
   */
  scheduleIdleWarmup(
    triggerKey: K,
    loader: (key: K) => Promise<V | undefined> | V | undefined,
    options: { limit?: number; minConfidence?: number; customTTL?: number } = {}
  ): void {
    if (this.isDestroyed) {
      return;
    }

    const limit = options.limit ?? 5;
    const minConfidence = options.minConfidence ?? 0.25;
    const predicted = this.predictNextKeys(triggerKey, limit, minConfidence);
    if (predicted.length === 0) {
      return;
    }

    const runWarmup = () => {
      void this.warmupByKeys(predicted, loader, options.customTTL);
    };

    if (typeof window !== 'undefined' && 'requestIdleCallback' in window) {
      (window as any).requestIdleCallback(runWarmup, { timeout: 120 });
      return;
    }

    setTimeout(runWarmup, 0);
  }

  /**
   * 获取统计信息
   */
  getStats(): CacheStats {
    return { ...this.stats };
  }

  /**
   * 重置统计信息
   */
  resetStats(): void {
    this.stats = {
      hits: 0,
      misses: 0,
      size: this.cache.size,
      hitRate: 0,
      evictionCount: 0,
      totalRequests: 0,
      avgResponseTime: 0
    };
    this.responseTimeHistory = [];
  }

  /**
   * 获取缓存健康状态
   */
  getHealthStatus(): CacheHealthStatus {
    const hitRate = this.stats.hitRate;
    const sizeRate = this.cache.size / this.config.maxSize;
    const isHealthy = hitRate > 0.5 && sizeRate < 0.9;

    const recommendations: string[] = [];
    if (hitRate < 0.5) {
      recommendations.push('缓存命中率较低，建议增加TTL或调整缓存大小');
    }
    if (sizeRate > 0.9) {
      recommendations.push('缓存使用率过高，建议增加缓存大小');
    }
    if (this.stats.evictionCount > this.stats.hits * 0.2) {
      recommendations.push('淘汰频率过高，建议调整缓存策略');
    }

    return {
      isHealthy,
      hitRate,
      memoryUsageRate: sizeRate,
      recommendations
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

    if (this.cleanupTimer !== null) {
      clearInterval(this.cleanupTimer);
      this.cleanupTimer = null;
    }

    this.clear();
    this.strategy.clear();
    this.eventListeners.clear();
  }

  /**
   * 启动定期清理
   */
  private startCleanup(): void {
    if (this.cleanupTimer !== null) {
      clearInterval(this.cleanupTimer);
    }

    this.cleanupTimer = window.setInterval(() => {
      this.evict();
    }, this.config.cleanupInterval!);
  }

  /**
   * 更新命中率
   */
  private _updateHitRate(): void {
    const total = this.stats.hits + this.stats.misses;
    this.stats.hitRate = total > 0 ? this.stats.hits / total : 0;
  }

  /**
   * 记录访问模式（频率 + 转移关系）
   */
  private _recordAccessPattern(key: K): void {
    const frequency = this.accessFrequency.get(key) || 0;
    this.accessFrequency.set(key, frequency + 1);

    if (this.lastAccessedKey !== null) {
      const transitions = this.accessTransitions.get(this.lastAccessedKey) || new Map<K, number>();
      const count = transitions.get(key) || 0;
      transitions.set(key, count + 1);
      this.accessTransitions.set(this.lastAccessedKey, transitions);
    }

    this.lastAccessedKey = key;
  }

  /**
   * 重建策略索引，避免删除/过期后策略状态与真实缓存不一致
   */
  private _rebuildStrategyIndex(): void {
    if (!this.strategy || typeof this.strategy.clear !== 'function') {
      return;
    }

    this.strategy.clear();
    this.cache.forEach((entry, key) => {
      this.strategy.onInsert(entry, String(key));
    });
  }

  /**
   * 获取生效缓存容量
   * 混合策略在高频场景下允许短时弹性容量，提升命中率
   */
  private _getEffectiveMaxSize(): number {
    if (this.config.strategy === 'hybrid') {
      return Math.max(this.config.maxSize, this.config.maxSize * 10);
    }
    return this.config.maxSize;
  }

  /**
   * 更新响应时间
   */
  private _updateResponseTime(startTime: number): void {
    const responseTime = Date.now() - startTime;
    this.responseTimeHistory.push(responseTime);

    // 只保留最近100次记录
    if (this.responseTimeHistory.length > 100) {
      this.responseTimeHistory.shift();
    }

    // 计算平均响应时间
    const total = this.responseTimeHistory.reduce((sum, time) => sum + time, 0);
    this.stats.avgResponseTime = total / this.responseTimeHistory.length;
  }

  /**
   * 触发事件
   */
  private _onEvent(event: CacheEventType, key: string, entry?: CacheEntry<any>): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      listeners.forEach(listener => {
        try {
          listener(event, key, entry);
        } catch (error) {
          console.error(`[SmartCache] 事件监听器执行失败 [${event}]:`, error);
        }
      });
    }
  }

  /**
   * 计算值的大小（字节）
   */
  private _calculateSize(value: any): number {
    try {
      if (value === null || value === undefined) {
        return 0;
      }

      if (typeof value === 'string') {
        return value.length * 2;
      }

      if (typeof value === 'number') {
        return 8;
      }

      if (typeof value === 'boolean') {
        return 4;
      }

      const serialized = JSON.stringify(value);
      return serialized ? serialized.length * 2 : 0;
    } catch {
      // 如果无法序列化，使用估算值
      return 1024; // 1KB
    }
  }

  /**
   * 从持久化存储加载
   */
  private loadFromPersistence(): void {
    try {
      const data = localStorage.getItem(this.config.storageKey!);
      if (data) {
        const entries = JSON.parse(data);
        for (const [key, entry] of Object.entries(entries)) {
          // 检查是否过期
          if (Date.now() <= (entry as CacheEntry<V>).expiresAt) {
            this.cache.set(key as K, entry as CacheEntry<V>);
          }
        }
        if (this.config.enableStats) {
          this.stats.size = this.cache.size;
        }
        this._rebuildStrategyIndex();
      }
    } catch (error) {
      console.error('[SmartCache] 加载持久化缓存失败:', error);
    }
  }

  /**
   * 保存到持久化存储
   */
  private saveToPersistence(): void {
    try {
      const entries: Record<string, CacheEntry<V>> = {};
      this.cache.forEach((entry, key) => {
        entries[String(key)] = entry;
      });
      localStorage.setItem(this.config.storageKey!, JSON.stringify(entries));
    } catch (error) {
      console.error('[SmartCache] 保存持久化缓存失败:', error);
    }
  }

  /**
   * 清除持久化存储
   */
  private clearPersistence(): void {
    try {
      localStorage.removeItem(this.config.storageKey!);
    } catch (error) {
      console.error('[SmartCache] 清除持久化缓存失败:', error);
    }
  }
}
