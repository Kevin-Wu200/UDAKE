/**
 * 缓存策略实现
 * 包括LRU、LFU、时间衰减和混合策略
 */

import type { CacheEntry, CacheStrategy as ICacheStrategy } from '../../types/cache';

/**
 * LRU (Least Recently Used) 策略
 * 淘汰最久未使用的条目
 */
export class LRUStrategy implements ICacheStrategy {
  private accessOrder: Map<string, true>;
  private maxSize: number;

  constructor(maxSize: number = 100) {
    this.accessOrder = new Map();
    this.maxSize = maxSize;
  }

  shouldEvict(entry: CacheEntry<any>): boolean {
    // LRU 在插入时判断，不需要在这里判断
    return false;
  }

  onAccess(entry: CacheEntry<any>, key: string): void {
    this._touch(key);
  }

  onInsert(entry: CacheEntry<any>, key: string): void {
    this._touch(key);
  }

  getEvictionKey(): string | null {
    const oldest = this.accessOrder.keys().next();
    return oldest.done ? null : oldest.value;
  }

  /**
   * 更新最大大小
   */
  updateMaxSize(newSize: number): void {
    this.maxSize = newSize;
  }

  /**
   * 清除策略数据
   */
  clear(): void {
    this.accessOrder.clear();
  }

  private _touch(key: string): void {
    if (this.accessOrder.has(key)) {
      this.accessOrder.delete(key);
    }
    this.accessOrder.set(key, true);
  }
}

/**
 * FIFO (First In First Out) 策略
 * 淘汰最早写入的条目，访问不会改变顺序
 */
export class FIFOStrategy implements ICacheStrategy {
  private insertionOrder: Map<string, true>;
  private maxSize: number;

  constructor(maxSize: number = 100) {
    this.insertionOrder = new Map();
    this.maxSize = maxSize;
  }

  shouldEvict(entry: CacheEntry<any>): boolean {
    return false;
  }

  onAccess(entry: CacheEntry<any>, key: string): void {
    // FIFO 访问不改变淘汰顺序
  }

  onInsert(entry: CacheEntry<any>, key: string): void {
    if (!this.insertionOrder.has(key)) {
      this.insertionOrder.set(key, true);
    }
  }

  getEvictionKey(): string | null {
    const first = this.insertionOrder.keys().next();
    return first.done ? null : first.value;
  }

  updateMaxSize(newSize: number): void {
    this.maxSize = newSize;
  }

  clear(): void {
    this.insertionOrder.clear();
  }
}

/**
 * LFU (Least Frequently Used) 策略
 * 淘汰访问频率最低的条目
 */
export class LFUStrategy implements ICacheStrategy {
  private frequencyMap: Map<string, number>;
  private maxSize: number;

  constructor(maxSize: number = 100) {
    this.frequencyMap = new Map();
    this.maxSize = maxSize;
  }

  shouldEvict(entry: CacheEntry<any>): boolean {
    return false;
  }

  onAccess(entry: CacheEntry<any>, key: string): void {
    const currentFreq = this.frequencyMap.get(key) || 0;
    this.frequencyMap.set(key, currentFreq + 1);
  }

  onInsert(entry: CacheEntry<any>, key: string): void {
    this.frequencyMap.set(key, 1);
  }

  getEvictionKey(): string | null {
    let leastFrequentKey: string | null = null;
    let leastFrequency = Infinity;

    this.frequencyMap.forEach((freq, key) => {
      if (freq < leastFrequency) {
        leastFrequency = freq;
        leastFrequentKey = key;
      }
    });

    return leastFrequentKey;
  }

  /**
   * 获取指定键的访问频率
   */
  getFrequency(key: string): number {
    return this.frequencyMap.get(key) || 0;
  }

  /**
   * 清除策略数据
   */
  clear(): void {
    this.frequencyMap.clear();
  }
}

/**
 * 时间衰减策略
 * 基于访问次数和时间的衰减评分
 */
export class TimeDecayStrategy implements ICacheStrategy {
  private decayRate: number; // 衰减率
  private scoreMap: Map<string, number>;
  private lastAccessMap: Map<string, number>;
  private minScore: number;

  constructor(decayRate: number = 0.95, minScore: number = 0.1) {
    this.decayRate = decayRate;
    this.scoreMap = new Map();
    this.lastAccessMap = new Map();
    this.minScore = minScore;
  }

  shouldEvict(entry: CacheEntry<any>): boolean {
    const key = this._getKey(entry);
    const score = this._calculateScore(entry);
    this.scoreMap.set(key, score);
    return score < this.minScore;
  }

  onAccess(entry: CacheEntry<any>, key: string): void {
    entry.accessCount++;
    entry.lastAccessTime = Date.now();
    this.lastAccessMap.set(key, Date.now());
  }

  onInsert(entry: CacheEntry<any>, key: string): void {
    entry.accessCount = 1;
    entry.lastAccessTime = Date.now();
    this.scoreMap.set(key, 1);
    this.lastAccessMap.set(key, Date.now());
  }

  getEvictionKey(): string | null {
    let lowestScoreKey: string | null = null;
    let lowestScore = Infinity;

    this.scoreMap.forEach((score, key) => {
      if (score < lowestScore) {
        lowestScore = score;
        lowestScoreKey = key;
      }
    });

    return lowestScoreKey;
  }

  /**
   * 计算衰减评分
   */
  private _calculateScore(entry: CacheEntry<any>): number {
    const age = Date.now() - entry.timestamp;
    const ageInMinutes = age / 60000; // 转换为分钟
    const decayedScore = entry.accessCount * Math.pow(this.decayRate, ageInMinutes);
    return decayedScore;
  }

  /**
   * 获取缓存的键（用于评分映射）
   */
  private _getKey(entry: CacheEntry<any>): string {
    // 这里简化处理，实际应用中可能需要更复杂的键生成逻辑
    return String(entry.timestamp);
  }

  /**
   * 清除策略数据
   */
  clear(): void {
    this.scoreMap.clear();
    this.lastAccessMap.clear();
  }

  /**
   * 更新衰减率
   */
  updateDecayRate(newRate: number): void {
    this.decayRate = newRate;
  }
}

/**
 * 混合策略
 * 结合LRU、LFU和时间衰减策略
 */
export class HybridStrategy implements ICacheStrategy {
  private lru: LRUStrategy;
  private lfu: LFUStrategy;
  private timeDecay: TimeDecayStrategy;
  private maxSize: number;
  private accessMap: Map<string, { lruTime: number; lfuFreq: number; decayScore: number }>;

  constructor(maxSize: number = 100) {
    this.lru = new LRUStrategy(maxSize);
    this.lfu = new LFUStrategy(maxSize);
    this.timeDecay = new TimeDecayStrategy();
    this.maxSize = maxSize;
    this.accessMap = new Map();
  }

  shouldEvict(entry: CacheEntry<any>): boolean {
    // 综合三个策略的判断
    return this.timeDecay.shouldEvict(entry);
  }

  onAccess(entry: CacheEntry<any>, key: string): void {
    this.lru.onAccess(entry, key);
    this.lfu.onAccess(entry, key);
    this.timeDecay.onAccess(entry, key);

    // 更新访问映射
    const accessInfo = this.accessMap.get(key) || {
      lruTime: 0,
      lfuFreq: 0,
      decayScore: 0
    };
    accessInfo.lruTime = Date.now();
    accessInfo.lfuFreq = this.lfu.getFrequency(key);
    this.accessMap.set(key, accessInfo);
  }

  onInsert(entry: CacheEntry<any>, key: string): void {
    this.lru.onInsert(entry, key);
    this.lfu.onInsert(entry, key);
    this.timeDecay.onInsert(entry, key);

    // 初始化访问映射
    this.accessMap.set(key, {
      lruTime: Date.now(),
      lfuFreq: 1,
      decayScore: 1
    });
  }

  getEvictionKey(): string | null {
    // 综合评分淘汰
    let lowestScoreKey: string | null = null;
    let lowestScore = Infinity;

    this.accessMap.forEach((info, key) => {
      // 综合评分：LRU(40%) + LFU(30%) + TimeDecay(30%)
      const lruScore = this._normalizeTime(info.lruTime);
      const lfuScore = this._normalizeFrequency(info.lfuFreq);
      const decayScore = info.decayScore;

      const combinedScore = lruScore * 0.4 + lfuScore * 0.3 + decayScore * 0.3;

      if (combinedScore < lowestScore) {
        lowestScore = combinedScore;
        lowestScoreKey = key;
      }
    });

    return lowestScoreKey;
  }

  /**
   * 归一化时间评分（时间越近，评分越高）
   */
  private _normalizeTime(timestamp: number): number {
    const age = Date.now() - timestamp;
    const maxAge = 3600000; // 1小时
    return Math.max(0, 1 - age / maxAge);
  }

  /**
   * 归一化频率评分（频率越高，评分越高）
   */
  private _normalizeFrequency(freq: number): number {
    const maxFreq = 100;
    return Math.min(1, freq / maxFreq);
  }

  /**
   * 清除策略数据
   */
  clear(): void {
    this.lru.clear();
    this.lfu.clear();
    this.timeDecay.clear();
    this.accessMap.clear();
  }

  /**
   * 获取综合评分
   */
  getScore(key: string): number {
    const info = this.accessMap.get(key);
    if (!info) return 0;

    const lruScore = this._normalizeTime(info.lruTime);
    const lfuScore = this._normalizeFrequency(info.lfuFreq);
    const decayScore = info.decayScore;

    return lruScore * 0.4 + lfuScore * 0.3 + decayScore * 0.3;
  }
}

/**
 * 策略工厂
 */
export class CacheStrategyFactory {
  /**
   * 创建策略实例
   */
  static create(
    strategy: 'lru' | 'fifo' | 'lfu' | 'time-decay' | 'hybrid',
    maxSize: number = 100
  ): ICacheStrategy {
    switch (strategy) {
      case 'lru':
        return new LRUStrategy(maxSize);
      case 'fifo':
        return new FIFOStrategy(maxSize);
      case 'lfu':
        return new LFUStrategy(maxSize);
      case 'time-decay':
        return new TimeDecayStrategy();
      case 'hybrid':
      default:
        return new HybridStrategy(maxSize);
    }
  }
}
