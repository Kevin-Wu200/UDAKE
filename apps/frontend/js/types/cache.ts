/**
 * 缓存类型定义
 */

/**
 * 缓存条目
 */
export interface CacheEntry<T> {
  /** 缓存的值 */
  value: T;
  /** 创建时间戳 */
  timestamp: number;
  /** 访问次数 */
  accessCount: number;
  /** 最后访问时间 */
  lastAccessTime: number;
  /** 过期时间 */
  expiresAt: number;
  /** 缓存大小（字节） */
  size?: number;
}

/**
 * 缓存策略接口
 */
export interface CacheStrategy {
  /**
   * 判断是否应该淘汰该条目
   */
  shouldEvict(entry: CacheEntry<any>): boolean;

  /**
   * 访问时的回调
   */
  onAccess(entry: CacheEntry<any>, key: string): void;

  /**
   * 插入时的回调
   */
  onInsert(entry: CacheEntry<any>, key: string): void;

  /**
   * 获取应该淘汰的键
   */
  getEvictionKey(): string | null;
}

/**
 * 缓存配置
 */
export interface CacheConfig {
  /** 最大缓存数量 */
  maxSize: number;
  /** 缓存存活时间（毫秒） */
  ttl: number;
  /** 缓存策略 */
  strategy: 'lru' | 'lfu' | 'time-decay' | 'hybrid';
  /** 是否持久化 */
  persistence?: boolean;
  /** 持久化存储键 */
  storageKey?: string;
  /** 是否启用统计 */
  enableStats?: boolean;
  /** 是否启用自动清理 */
  enableAutoCleanup?: boolean;
  /** 自动清理间隔（毫秒） */
  cleanupInterval?: number;
}

/**
 * 缓存统计信息
 */
export interface CacheStats {
  /** 命中次数 */
  hits: number;
  /** 未命中次数 */
  misses: number;
  /** 当前缓存大小 */
  size: number;
  /** 命中率 */
  hitRate: number;
  /** 淘汰次数 */
  evictionCount: number;
  /** 总请求数 */
  totalRequests: number;
  /** 平均响应时间（毫秒） */
  avgResponseTime: number;
}

/**
 * 缓存事件类型
 */
export type CacheEventType =
  | 'hit'
  | 'miss'
  | 'set'
  | 'delete'
  | 'evict'
  | 'clear'
  | 'expire';

/**
 * 缓存事件监听器
 */
export type CacheEventListener = (
  event: CacheEventType,
  key: string,
  entry?: CacheEntry<any>
) => void;

/**
 * 缓存条目元数据
 */
export interface CacheEntryMetadata {
  /** 创建时间 */
  createdAt: number;
  /** 最后访问时间 */
  lastAccessedAt: number;
  /** 访问次数 */
  accessCount: number;
  /** 过期时间 */
  expiresAt: number;
  /** 是否持久化 */
  isPersisted: boolean;
}

/**
 * 缓存健康状态
 */
export interface CacheHealthStatus {
  /** 是否健康 */
  isHealthy: boolean;
  /** 命中率 */
  hitRate: number;
  /** 内存使用率 */
  memoryUsageRate: number;
  /** 建议操作 */
  recommendations: string[];
}

/**
 * 双层缓存配置
 */
export interface TwoLevelCacheConfig {
  /** 内存缓存配置 */
  memoryConfig: Partial<CacheConfig>;
  /** 磁盘缓存配置 */
  diskConfig: Partial<CacheConfig>;
  /** 是否启用自动提升 */
  enableAutoPromote?: boolean;
  /** 提升阈值（访问次数） */
  promoteThreshold?: number;
}

/**
 * 双层缓存统计信息
 */
export interface TwoLevelCacheStats {
  /** 内存缓存统计 */
  memory: CacheStats;
  /** 磁盘缓存统计 */
  disk: CacheStats;
  /** 总体统计 */
  total: CacheStats;
  /** 提升次数 */
  promotionCount: number;
}