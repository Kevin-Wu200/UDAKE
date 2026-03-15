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

    const ttl = customTTL || this.config.ttl;
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
    if (this.cache.size >= this.config.maxSize && !this.cache.has(key)) {
      this.evict();
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
  evict(): void {
    if (this.isDestroyed) {
      return;
    }

    // 检查过期项
    const now = Date.now();
    for (const [key, entry] of this.cache.entries()) {
      if (now > entry.expiresAt) {
        this.cache.delete(key);
        if (this.config.enableStats) {
          this.stats.evictionCount++;
        }
        this._onEvent('expire', String(key), entry);
      }
    }

    // 如果仍然超出限制，使用策略淘汰
    if (this.cache.size >= this.config.maxSize) {
      const evictKey = this.strategy.getEvictionKey();
      if (evictKey) {
        const entry = this.cache.get(evictKey as K);
        this.cache.delete(evictKey as K);
        if (this.config.enableStats) {
          this.stats.evictionCount++;
        }
        this._onEvent('evict', evictKey, entry);
      }
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
      return new Blob([JSON.stringify(value)]).size;
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