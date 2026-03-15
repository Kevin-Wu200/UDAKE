/**
 * 性能优化器
 * 负责位置服务的性能优化，包括数据节流、批处理、智能定位等
 */

import type { LocationData, AccelerometerData, GyroscopeData, OrientationData } from '../types/sensor';

/**
 * 性能优化配置
 */
export interface PerformanceConfig {
  /** 位置更新节流时间（毫秒） */
  locationThrottleTime: number;
  /** 传感器数据节流时间（毫秒） */
  sensorThrottleTime: number;
  /** 轨迹点缓冲区大小 */
  trackBufferSize: number;
  /** 地理围栏检查间隔（毫秒） */
  geofenceCheckInterval: number;
  /** 是否启用智能定位 */
  enableSmartLocation: boolean;
  /** 是否启用数据压缩 */
  enableDataCompression: boolean;
  /** 最大存储轨迹数 */
  maxStoredTracks: number;
  /** 最大存储事件数 */
  maxStoredEvents: number;
}

/**
 * 智能定位策略
 */
export enum SmartLocationStrategy {
  /** 高精度模式（适合导航） */
  HIGH_ACCURACY = 'high_accuracy',
  /** 平衡模式（适合日常使用） */
  BALANCED = 'balanced',
  /** 节能模式（适合后台运行） */
  POWER_SAVING = 'power_saving',
}

/**
 * 性能优化器类
 */
export class PerformanceOptimizer {
  private static instance: PerformanceOptimizer;

  // 配置
  private config: PerformanceConfig = {
    locationThrottleTime: 1000, // 1秒
    sensorThrottleTime: 500, // 0.5秒
    trackBufferSize: 100,
    geofenceCheckInterval: 1000,
    enableSmartLocation: true,
    enableDataCompression: true,
    maxStoredTracks: 50,
    maxStoredEvents: 1000,
  };

  // 节流定时器
  private locationThrottleTimer: number | null = null;
  private sensorThrottleTimer: number | null = null;

  // 缓存数据
  private cachedLocation: LocationData | null = null;
  private cachedSensorData: Map<string, any> = new Map();

  // 回调函数
  private locationCallback: ((data: LocationData) => void) | null = null;
  private sensorCallback: ((type: string, data: any) => void) | null = null;

  // 当前策略
  private currentStrategy: SmartLocationStrategy = SmartLocationStrategy.BALANCED;

  // 活动状态
  private isMoving: boolean = false;
  private lastSpeed: number = 0;

  // 定时器
  private activityCheckTimer: number | null = null;

  private constructor() {}

  /**
   * 获取单例实例
   */
  public static getInstance(): PerformanceOptimizer {
    if (!PerformanceOptimizer.instance) {
      PerformanceOptimizer.instance = new PerformanceOptimizer();
    }
    return PerformanceOptimizer.instance;
  }

  /**
   * 配置性能优化器
   */
  public configure(config: Partial<PerformanceConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /**
   * 获取配置
   */
  public getConfig(): PerformanceConfig {
    return { ...this.config };
  }

  /**
   * 节流位置数据
   */
  public throttleLocation(location: LocationData, callback: (data: LocationData) => void): void {
    if (this.locationThrottleTimer) {
      clearTimeout(this.locationThrottleTimer);
    }

    this.cachedLocation = location;

    this.locationThrottleTimer = window.setTimeout(() => {
      if (this.cachedLocation) {
        callback(this.cachedLocation);
        this.cachedLocation = null;
      }
      this.locationThrottleTimer = null;
    }, this.config.locationThrottleTime);
  }

  /**
   * 节流传感器数据
   */
  public throttleSensor(type: string, data: any, callback: (type: string, data: any) => void): void {
    const key = `${type}_${Math.floor(Date.now() / this.config.sensorThrottleTime)}`;

    if (this.cachedSensorData.has(key)) {
      return; // 节流，丢弃重复数据
    }

    this.cachedSensorData.set(key, data);

    // 清理过期缓存
    if (this.cachedSensorData.size > 100) {
      const keysToDelete = Array.from(this.cachedSensorData.keys()).slice(0, 50);
      keysToDelete.forEach((k) => this.cachedSensorData.delete(k));
    }

    callback(type, data);
  }

  /**
   * 设置智能定位策略
   */
  public setSmartLocationStrategy(strategy: SmartLocationStrategy): void {
    this.currentStrategy = strategy;
    this.applyStrategy();
  }

  /**
   * 获取当前策略
   */
  public getCurrentStrategy(): SmartLocationStrategy {
    return this.currentStrategy;
  }

  /**
   * 应用策略
   */
  private applyStrategy(): void {
    switch (this.currentStrategy) {
      case SmartLocationStrategy.HIGH_ACCURACY:
        this.config.locationThrottleTime = 500; // 0.5秒
        this.config.sensorThrottleTime = 200; // 0.2秒
        this.config.geofenceCheckInterval = 500;
        break;

      case SmartLocationStrategy.BALANCED:
        this.config.locationThrottleTime = 1000; // 1秒
        this.config.sensorThrottleTime = 500; // 0.5秒
        this.config.geofenceCheckInterval = 1000;
        break;

      case SmartLocationStrategy.POWER_SAVING:
        this.config.locationThrottleTime = 5000; // 5秒
        this.config.sensorThrottleTime = 2000; // 2秒
        this.config.geofenceCheckInterval = 5000;
        break;
    }
  }

  /**
   * 更新活动状态
   */
  public updateActivityState(speed: number): void {
    this.lastSpeed = speed;
    this.isMoving = speed > 0.5; // 速度大于0.5m/s认为在移动

    // 根据活动状态调整策略
    if (this.config.enableSmartLocation) {
      if (this.isMoving) {
        this.setSmartLocationStrategy(SmartLocationStrategy.HIGH_ACCURACY);
      } else {
        this.setSmartLocationStrategy(SmartLocationStrategy.POWER_SAVING);
      }
    }
  }

  /**
   * 压缩轨迹数据
   */
  public compressTrackData(points: any[]): any[] {
    if (!this.config.enableDataCompression) {
      return points;
    }

    // 使用 Douglas-Peucker 算法简化轨迹
    if (points.length < 3) {
      return points;
    }

    const tolerance = 0.0001; // 约等于11米
    return this.douglasPeucker(points, tolerance);
  }

  /**
   * Douglas-Peucker 算法
   */
  private douglasPeucker(points: any[], tolerance: number): any[] {
    if (points.length <= 2) {
      return points;
    }

    let maxDistance = 0;
    let maxIndex = 0;
    const start = points[0];
    const end = points[points.length - 1];

    for (let i = 1; i < points.length - 1; i++) {
      const distance = this.perpendicularDistance(points[i], start, end);
      if (distance > maxDistance) {
        maxDistance = distance;
        maxIndex = i;
      }
    }

    if (maxDistance > tolerance) {
      const left = this.douglasPeucker(points.slice(0, maxIndex + 1), tolerance);
      const right = this.douglasPeucker(points.slice(maxIndex), tolerance);
      return left.slice(0, -1).concat(right);
    } else {
      return [start, end];
    }
  }

  /**
   * 计算点到线段的垂直距离
   */
  private perpendicularDistance(point: any, start: any, end: any): number {
    const dx = end.location.longitude - start.location.longitude;
    const dy = end.location.latitude - start.location.latitude;

    const mag = Math.sqrt(dx * dx + dy * dy);
    if (mag === 0) {
      return Math.sqrt(
        Math.pow(point.location.longitude - start.location.longitude, 2) +
          Math.pow(point.location.latitude - start.location.latitude, 2)
      );
    }

    const u =
      ((point.location.longitude - start.location.longitude) * dx +
        (point.location.latitude - start.location.latitude) * dy) /
      (mag * mag);

    const closestX = start.location.longitude + u * dx;
    const closestY = start.location.latitude + u * dy;

    return Math.sqrt(
      Math.pow(point.location.longitude - closestX, 2) +
        Math.pow(point.location.latitude - closestY, 2)
    );
  }

  /**
   * 清理旧数据
   */
  public cleanupOldData<T>(data: T[], maxSize: number): T[] {
    if (data.length <= maxSize) {
      return data;
    }

    // 按时间戳排序，保留最新的数据
    return data.slice(-maxSize);
  }

  /**
   * 批量处理数据
   */
  public batchProcess<T>(
    items: T[],
    batchSize: number,
    processor: (batch: T[]) => Promise<void>
  ): Promise<void> {
    const batches: T[][] = [];
    for (let i = 0; i < items.length; i += batchSize) {
      batches.push(items.slice(i, i + batchSize));
    }

    return new Promise((resolve, reject) => {
      let index = 0;

      const processNext = async () => {
        if (index >= batches.length) {
          resolve();
          return;
        }

        try {
          await processor(batches[index]);
          index++;
          setTimeout(processNext, 0); // 避免阻塞主线程
        } catch (error) {
          reject(error);
        }
      };

      processNext();
    });
  }

  /**
   * 优化存储
   */
  public optimizeStorage(): void {
    // 清理 localStorage 中的旧数据
    const keys = Object.keys(localStorage);
    const maxSize = 5 * 1024 * 1024; // 5MB

    keys.forEach((key) => {
      if (key.startsWith('udake_')) {
        const value = localStorage.getItem(key);
        if (value && value.length > maxSize) {
          console.warn(`存储数据过大，已清理: ${key}`);
          localStorage.removeItem(key);
        }
      }
    });
  }

  /**
   * 监控性能
   */
  public monitorPerformance(): PerformanceMetrics {
    const metrics: PerformanceMetrics = {
      memoryUsage: this.getMemoryUsage(),
      storageUsage: this.getStorageUsage(),
      cacheSize: this.cachedSensorData.size,
      bufferSize: this.cachedLocation ? 1 : 0,
    };

    return metrics;
  }

  /**
   * 获取内存使用情况
   */
  private getMemoryUsage(): number {
    if ((performance as any).memory) {
      return (performance as any).memory.usedJSHeapSize;
    }
    return 0;
  }

  /**
   * 获取存储使用情况
   */
  private getStorageUsage(): number {
    let total = 0;
    for (let key in localStorage) {
      if (localStorage.hasOwnProperty(key)) {
        total += localStorage[key].length + key.length;
      }
    }
    return total;
  }

  /**
   * 清理资源
   */
  public dispose(): void {
    if (this.locationThrottleTimer) {
      clearTimeout(this.locationThrottleTimer);
      this.locationThrottleTimer = null;
    }

    if (this.sensorThrottleTimer) {
      clearTimeout(this.sensorThrottleTimer);
      this.sensorThrottleTimer = null;
    }

    if (this.activityCheckTimer) {
      clearInterval(this.activityCheckTimer);
      this.activityCheckTimer = null;
    }

    this.cachedLocation = null;
    this.cachedSensorData.clear();
  }
}

/**
 * 性能指标接口
 */
export interface PerformanceMetrics {
  /** 内存使用（字节） */
  memoryUsage: number;
  /** 存储使用（字节） */
  storageUsage: number;
  /** 缓存大小 */
  cacheSize: number;
  /** 缓冲区大小 */
  bufferSize: number;
}

// 导出单例实例
export const performanceOptimizer = PerformanceOptimizer.getInstance();