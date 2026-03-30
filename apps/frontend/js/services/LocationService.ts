/**
 * 位置服务
 * 提供位置获取、监听和权限管理功能
 */

import type { LocationData, LocationWatchOptions } from '../types/sensor';
import { sensorManager } from './SensorManager';

type BatteryEventName = 'levelchange' | 'chargingchange' | 'dischargingtimechange';

interface BatteryManagerLike extends EventTarget {
  level: number;
  charging: boolean;
  chargingTime: number;
  dischargingTime: number;
}

export interface BatteryStatus {
  supported: boolean;
  level: number | null;
  charging: boolean | null;
  chargingTime: number | null;
  dischargingTime: number | null;
  estimatedDischargeMinutes: number | null;
  sampledAt: number;
}

export interface BatteryOptimizationProfile {
  strategy: 'high-accuracy' | 'balanced' | 'power-saving';
  watchOptions: LocationWatchOptions;
  expectedBatteryConsumption8h: number;
}

export interface BatteryUsageSample {
  timestamp: number;
  level: number;
}

/**
 * 位置服务类
 */
export class LocationService {
  private static instance: LocationService;

  // 回调函数列表
  private locationListeners: Set<(data: LocationData) => void> = new Set();
  private errorListeners: Set<(error: Error) => void> = new Set();

  // 最后的位置数据
  private lastLocation: LocationData | null = null;

  // 是否正在监听
  private isWatching: boolean = false;

  // 配置
  private options: LocationWatchOptions = {
    enableHighAccuracy: true,
    timeout: 10000,
    distanceFilter: 10,
  };

  private batteryManager: BatteryManagerLike | null = null;
  private batteryMonitoringActive = false;
  private batteryListeners: Set<(status: BatteryStatus) => void> = new Set();
  private batteryEventHandler = () => {
    this.emitBatteryStatus();
  };

  private constructor() {}

  /**
   * 获取单例实例
   */
  public static getInstance(): LocationService {
    if (!LocationService.instance) {
      LocationService.instance = new LocationService();
    }
    return LocationService.instance;
  }

  /**
   * 配置位置服务
   */
  public configure(options: Partial<LocationWatchOptions>): void {
    this.options = { ...this.options, ...options };
    sensorManager.configure({ location: this.options });
  }

  /**
   * 请求位置权限
   */
  public async requestPermission(): Promise<boolean> {
    return await sensorManager.requestLocationPermission();
  }

  /**
   * 检查位置权限
   */
  public checkPermission(): string {
    return sensorManager.getStatus().locationPermission;
  }

  /**
   * 获取当前位置
   */
  public async getCurrentLocation(): Promise<LocationData> {
    const location = await sensorManager.getCurrentLocation();
    if (!location) {
      throw new Error('无法获取当前位置');
    }
    this.lastLocation = location;
    return location;
  }

  /**
   * 开始监听位置变化
   */
  public async startWatch(): Promise<boolean> {
    if (this.isWatching) {
      console.warn('位置监听已经在运行');
      return true;
    }

    const profile = await this.getOptimizedWatchProfile(this.lastLocation?.speed ?? null);
    this.configure(profile.watchOptions);

    const success = await sensorManager.startLocationWatch((data) => {
      this.lastLocation = data;
      this.notifyLocationListeners(data);
    });

    if (success) {
      this.isWatching = true;
    }

    return success;
  }

  /**
   * 停止监听位置变化
   */
  public async stopWatch(): Promise<void> {
    if (!this.isWatching) {
      return;
    }

    await sensorManager.stopLocationWatch();
    this.isWatching = false;
  }

  /**
   * 是否支持电池 API
   */
  public isBatteryApiSupported(): boolean {
    if (typeof navigator === 'undefined') {
      return false;
    }
    return typeof (navigator as Navigator & { getBattery?: () => Promise<BatteryManagerLike> }).getBattery === 'function';
  }

  /**
   * 获取当前电池状态
   */
  public async getBatteryStatus(): Promise<BatteryStatus> {
    const manager = await this.resolveBatteryManager();
    const now = Date.now();
    if (!manager) {
      return {
        supported: false,
        level: null,
        charging: null,
        chargingTime: null,
        dischargingTime: null,
        estimatedDischargeMinutes: null,
        sampledAt: now
      };
    }

    const dischargingTime = Number.isFinite(manager.dischargingTime) ? manager.dischargingTime : null;
    return {
      supported: true,
      level: Number(manager.level),
      charging: manager.charging,
      chargingTime: Number.isFinite(manager.chargingTime) ? manager.chargingTime : null,
      dischargingTime,
      estimatedDischargeMinutes: dischargingTime ? Math.round(dischargingTime / 60) : null,
      sampledAt: now
    };
  }

  /**
   * 启动电池监控
   */
  public async startBatteryMonitoring(): Promise<boolean> {
    const manager = await this.resolveBatteryManager();
    if (!manager) {
      return false;
    }

    if (this.batteryMonitoringActive) {
      return true;
    }

    const events: BatteryEventName[] = ['levelchange', 'chargingchange', 'dischargingtimechange'];
    events.forEach((eventName) => manager.addEventListener(eventName, this.batteryEventHandler));
    this.batteryMonitoringActive = true;
    await this.emitBatteryStatus();
    return true;
  }

  /**
   * 停止电池监控
   */
  public stopBatteryMonitoring(): void {
    if (!this.batteryMonitoringActive || !this.batteryManager) {
      return;
    }
    const events: BatteryEventName[] = ['levelchange', 'chargingchange', 'dischargingtimechange'];
    events.forEach((eventName) => this.batteryManager?.removeEventListener(eventName, this.batteryEventHandler));
    this.batteryMonitoringActive = false;
  }

  public addBatteryListener(listener: (status: BatteryStatus) => void): () => void {
    this.batteryListeners.add(listener);
    this.emitBatteryStatus();
    return () => {
      this.batteryListeners.delete(listener);
    };
  }

  public removeBatteryListener(listener: (status: BatteryStatus) => void): void {
    this.batteryListeners.delete(listener);
  }

  /**
   * 基于电池状态和速度返回建议采样配置
   */
  public async getOptimizedWatchProfile(speedMetersPerSecond?: number | null): Promise<BatteryOptimizationProfile> {
    const batteryStatus = await this.getBatteryStatus();
    const speed = Number(speedMetersPerSecond ?? 0);
    const lowBattery = batteryStatus.supported
      && batteryStatus.charging === false
      && typeof batteryStatus.level === 'number'
      && batteryStatus.level <= 0.2;
    const stationary = speed > 0 && speed <= 0.8;

    if (lowBattery) {
      return {
        strategy: 'power-saving',
        watchOptions: {
          enableHighAccuracy: false,
          timeout: 15000,
          distanceFilter: 25
        },
        expectedBatteryConsumption8h: 18
      };
    }

    if (stationary) {
      return {
        strategy: 'balanced',
        watchOptions: {
          enableHighAccuracy: false,
          timeout: 12000,
          distanceFilter: 12
        },
        expectedBatteryConsumption8h: 24
      };
    }

    return {
      strategy: 'high-accuracy',
      watchOptions: {
        enableHighAccuracy: true,
        timeout: 8000,
        distanceFilter: 6
      },
      expectedBatteryConsumption8h: 29
    };
  }

  public async optimizeSamplingByBattery(speedMetersPerSecond?: number | null): Promise<BatteryOptimizationProfile> {
    const profile = await this.getOptimizedWatchProfile(speedMetersPerSecond);
    this.configure(profile.watchOptions);
    return profile;
  }

  /**
   * 根据历史采样估算固定时长下的耗电百分比
   */
  public estimateBatteryConsumption(samples: BatteryUsageSample[], durationHours = 8): number {
    if (samples.length < 2) {
      return 0;
    }
    const valid = samples
      .filter((sample) => Number.isFinite(sample.level) && Number.isFinite(sample.timestamp))
      .sort((a, b) => a.timestamp - b.timestamp);
    if (valid.length < 2) {
      return 0;
    }

    const first = valid[0];
    const last = valid[valid.length - 1];
    const elapsedHours = Math.max(0.1, (last.timestamp - first.timestamp) / (1000 * 60 * 60));
    const consumed = Math.max(0, (first.level - last.level) * 100);
    const normalized = (consumed / elapsedHours) * durationHours;
    return Number(Math.max(0, Math.min(100, normalized)).toFixed(2));
  }

  /**
   * 添加位置监听器
   */
  public addLocationListener(listener: (data: LocationData) => void): void {
    this.locationListeners.add(listener);

    // 如果有缓存的位置数据，立即通知
    if (this.lastLocation) {
      listener(this.lastLocation);
    }
  }

  /**
   * 移除位置监听器
   */
  public removeLocationListener(listener: (data: LocationData) => void): void {
    this.locationListeners.delete(listener);
  }

  /**
   * 添加错误监听器
   */
  public addErrorListener(listener: (error: Error) => void): void {
    this.errorListeners.add(listener);
  }

  /**
   * 移除错误监听器
   */
  public removeErrorListener(listener: (error: Error) => void): void {
    this.errorListeners.delete(listener);
  }

  /**
   * 通知所有位置监听器
   */
  private notifyLocationListeners(data: LocationData): void {
    this.locationListeners.forEach((listener) => {
      try {
        listener(data);
      } catch (error) {
        console.error('位置监听器错误:', error);
      }
    });
  }

  /**
   * 通知所有错误监听器
   */
  private notifyErrorListeners(error: Error): void {
    this.errorListeners.forEach((listener) => {
      try {
        listener(error);
      } catch (err) {
        console.error('错误监听器错误:', err);
      }
    });
  }

  /**
   * 获取最后的位置数据
   */
  public getLastLocation(): LocationData | null {
    return this.lastLocation;
  }

  /**
   * 计算两点之间的距离（Haversine公式）
   */
  public calculateDistance(
    point1: { latitude: number; longitude: number },
    point2: { latitude: number; longitude: number }
  ): number {
    const R = 6371e3; // 地球半径（米）
    const φ1 = (point1.latitude * Math.PI) / 180;
    const φ2 = (point2.latitude * Math.PI) / 180;
    const Δφ = ((point2.latitude - point1.latitude) * Math.PI) / 180;
    const Δλ = ((point2.longitude - point1.longitude) * Math.PI) / 180;

    const a =
      Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
      Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c;
  }

  /**
   * 计算方位角
   */
  public calculateBearing(
    point1: { latitude: number; longitude: number },
    point2: { latitude: number; longitude: number }
  ): number {
    const φ1 = (point1.latitude * Math.PI) / 180;
    const φ2 = (point2.latitude * Math.PI) / 180;
    const Δλ = ((point2.longitude - point1.longitude) * Math.PI) / 180;

    const y = Math.sin(Δλ) * Math.cos(φ2);
    const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);

    const bearing = Math.atan2(y, x);
    return ((bearing * 180) / Math.PI + 360) % 360;
  }

  /**
   * 格式化位置数据
   */
  public formatLocation(location: LocationData): string {
    return `${location.latitude.toFixed(6)}, ${location.longitude.toFixed(6)}`;
  }

  /**
   * 格式化精度
   */
  public formatAccuracy(accuracy: number): string {
    if (accuracy < 10) {
      return `高精度 (±${accuracy.toFixed(1)}m)`;
    } else if (accuracy < 50) {
      return `中等精度 (±${accuracy.toFixed(1)}m)`;
    } else {
      return `低精度 (±${accuracy.toFixed(1)}m)`;
    }
  }

  /**
   * 检查位置数据是否有效
   */
  public isValidLocation(location: LocationData | null): boolean {
    if (!location) {
      return false;
    }

    return (
      location.latitude >= -90 &&
      location.latitude <= 90 &&
      location.longitude >= -180 &&
      location.longitude <= 180 &&
      location.accuracy >= 0
    );
  }

  /**
   * 清理资源
   */
  public dispose(): void {
    this.stopWatch();
    this.stopBatteryMonitoring();
    this.locationListeners.clear();
    this.batteryListeners.clear();
    this.errorListeners.clear();
  }

  private async resolveBatteryManager(): Promise<BatteryManagerLike | null> {
    if (this.batteryManager) {
      return this.batteryManager;
    }
    if (!this.isBatteryApiSupported()) {
      return null;
    }
    try {
      const getBattery = (navigator as Navigator & { getBattery?: () => Promise<BatteryManagerLike> }).getBattery;
      if (!getBattery) {
        return null;
      }
      this.batteryManager = await getBattery.call(navigator);
      return this.batteryManager;
    } catch {
      return null;
    }
  }

  private async emitBatteryStatus(): Promise<void> {
    if (this.batteryListeners.size === 0) {
      return;
    }
    const status = await this.getBatteryStatus();
    this.batteryListeners.forEach((listener) => {
      try {
        listener(status);
      } catch (error) {
        console.error('电池监听器错误:', error);
      }
    });
  }
}

// 导出单例实例
export const locationService = LocationService.getInstance();
