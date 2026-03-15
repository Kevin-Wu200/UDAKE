/**
 * 位置服务
 * 提供位置获取、监听和权限管理功能
 */

import type { LocationData, LocationWatchOptions } from '../types/sensor';
import { sensorManager } from './SensorManager';

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
    this.locationListeners.clear();
    this.errorListeners.clear();
  }
}

// 导出单例实例
export const locationService = LocationService.getInstance();