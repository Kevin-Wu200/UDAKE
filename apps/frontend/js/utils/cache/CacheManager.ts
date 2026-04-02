/**
 * 统一缓存管理器
 * 负责注册、监控和生命周期管理不同缓存实例
 */

import type { CacheConfig } from '../../types/cache';
import { SmartCache } from './SmartCache';
import { TwoLevelCache } from './TwoLevelCache';

export interface CacheLike<K = string, V = any> {
  get(key: K): Promise<V | undefined> | V | undefined;
  set(key: K, value: V, ttl?: number): Promise<void> | void;
  delete(key: K): Promise<void | boolean> | void | boolean;
  clear(): Promise<void> | void;
  has?(key: K): Promise<boolean> | boolean;
  keys?(): K[];
  size?(): number;
  getStats?(): unknown;
  resetStats?(): void;
  destroy?(): void;
}

export interface ManagedCacheConfig {
  type: 'smart' | 'two-level';
  memoryConfig?: Partial<CacheConfig>;
  diskConfig?: Partial<CacheConfig>;
  options?: {
    enableAutoPromote?: boolean;
    promoteThreshold?: number;
  };
}

export class CacheManager {
  private caches: Map<string, CacheLike<string, unknown>> = new Map();

  register(name: string, cache: CacheLike<string, unknown>): CacheLike<string, unknown> {
    const existing = this.caches.get(name);
    if (existing?.destroy) {
      existing.destroy();
    }
    this.caches.set(name, cache);
    return cache;
  }

  create(name: string, config: ManagedCacheConfig): CacheLike<string, unknown> {
    if (config.type === 'two-level') {
      const cache = new TwoLevelCache<string, unknown>(
        config.memoryConfig,
        config.diskConfig,
        config.options
      );
      return this.register(name, cache);
    }

    const cache = new SmartCache<string, unknown>(config.memoryConfig);
    return this.register(name, cache);
  }

  get(name: string): CacheLike<string, unknown> | undefined {
    return this.caches.get(name);
  }

  remove(name: string): void {
    const cache = this.caches.get(name);
    if (cache?.destroy) {
      cache.destroy();
    }
    this.caches.delete(name);
  }

  clearAll(): Promise<void[]> {
    return Promise.all(
      Array.from(this.caches.values()).map(cache => Promise.resolve(cache.clear()))
    );
  }

  resetAllStats(): void {
    this.caches.forEach(cache => {
      if (cache.resetStats) {
        cache.resetStats();
      }
    });
  }

  getAllStats(): Record<string, unknown> {
    const result: Record<string, unknown> = {};
    this.caches.forEach((cache, name) => {
      result[name] = cache.getStats ? cache.getStats() : { message: '缓存未提供统计信息' };
    });
    return result;
  }

  destroy(): void {
    this.caches.forEach(cache => {
      if (cache.destroy) {
        cache.destroy();
      }
    });
    this.caches.clear();
  }
}
