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

interface KalmanState {
  estimate: number;
  error: number;
}

export type ActivityScene = 'stationary' | 'walking' | 'cycling' | 'driving';

export interface AdaptiveSamplingStrategy {
  stationaryIntervalSec: number;
  walkingIntervalSec: number;
  cyclingIntervalSec: number;
  drivingIntervalSec: number;
  sleepIntervalSec: number;
  backgroundMinIntervalSec: number;
  lowPowerIntervalMultiplier: number;
  movementDistanceThresholdMeters: number;
  stationarySleepDelaySec: number;
}

export interface AdaptiveSamplingDecision {
  scene: ActivityScene;
  intervalSeconds: number;
  shouldSleep: boolean;
  reason: string[];
  watchOptions: LocationWatchOptions;
}

export interface SleepState {
  sleeping: boolean;
  since: number | null;
  reason: string | null;
}

export interface LocationPerformanceStats {
  totalUpdates: number;
  smoothedUpdates: number;
  skippedComputations: number;
  backgroundSamplesLimited: number;
  sleepTransitions: number;
  lastScene: ActivityScene;
  totalDistanceMeters: number;
  averageSpeed: number;
  batteryWarnings: number;
  lastUpdatedAt: number | null;
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

interface MotionSnapshot {
  latitude: number;
  longitude: number;
  speed: number;
  heading: number | null;
  timestamp: number;
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

  private batteryStatusCache: BatteryStatus | null = null;
  private batteryStatusCacheUntil = 0;

  private kalmanLat: KalmanState = { estimate: 0, error: 1 };
  private kalmanLon: KalmanState = { estimate: 0, error: 1 };
  private processVariance = 1e-4;
  private measurementVariance = 1e-3;
  private smoothingReady = false;

  private appState: 'foreground' | 'background' = 'foreground';
  private lowPowerModeEnabled = false;
  private batteryWarningThreshold = 0.2;
  private manualScene: ActivityScene | null = null;
  private sceneLearningEnabled = true;
  private lastDecisionIntervalSec: number | null = null;

  private strategy: AdaptiveSamplingStrategy = {
    stationaryIntervalSec: 60,
    walkingIntervalSec: 15,
    cyclingIntervalSec: 10,
    drivingIntervalSec: 5,
    sleepIntervalSec: 90,
    backgroundMinIntervalSec: 30,
    lowPowerIntervalMultiplier: 2,
    movementDistanceThresholdMeters: 5,
    stationarySleepDelaySec: 180,
  };

  private sleepState: SleepState = {
    sleeping: false,
    since: null,
    reason: null,
  };

  private recentMotions: MotionSnapshot[] = [];
  private readonly maxMotionSamples = 40;

  private performanceStats: LocationPerformanceStats = {
    totalUpdates: 0,
    smoothedUpdates: 0,
    skippedComputations: 0,
    backgroundSamplesLimited: 0,
    sleepTransitions: 0,
    lastScene: 'stationary',
    totalDistanceMeters: 0,
    averageSpeed: 0,
    batteryWarnings: 0,
    lastUpdatedAt: null,
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

  public setSamplingStrategy(strategy: Partial<AdaptiveSamplingStrategy>): void {
    this.strategy = { ...this.strategy, ...strategy };
  }

  public getSamplingStrategy(): AdaptiveSamplingStrategy {
    return { ...this.strategy };
  }

  public setManualScene(scene: ActivityScene | null): void {
    this.manualScene = scene;
  }

  public setAppState(state: 'foreground' | 'background'): void {
    this.appState = state;
  }

  public enableSceneLearning(enabled: boolean): void {
    this.sceneLearningEnabled = enabled;
  }

  public setPowerSavingMode(enabled: boolean): void {
    this.lowPowerModeEnabled = enabled;
  }

  public setSleepThreshold(seconds: number): void {
    this.strategy = {
      ...this.strategy,
      stationarySleepDelaySec: Math.max(30, Math.floor(seconds)),
    };
  }

  public getSleepState(): SleepState {
    return { ...this.sleepState };
  }

  public getPerformanceStats(): LocationPerformanceStats {
    return { ...this.performanceStats };
  }

  public resetPerformanceStats(): void {
    this.performanceStats = {
      totalUpdates: 0,
      smoothedUpdates: 0,
      skippedComputations: 0,
      backgroundSamplesLimited: 0,
      sleepTransitions: 0,
      lastScene: 'stationary',
      totalDistanceMeters: 0,
      averageSpeed: 0,
      batteryWarnings: 0,
      lastUpdatedAt: null,
    };
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
    const processed = await this.processLocationUpdate(location);
    this.lastLocation = processed;
    return processed;
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
      void this.handleLocationStream(data);
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
  public async getBatteryStatus(forceRefresh = false): Promise<BatteryStatus> {
    if (!forceRefresh && this.batteryStatusCache && Date.now() < this.batteryStatusCacheUntil) {
      return this.batteryStatusCache;
    }

    const manager = await this.resolveBatteryManager();
    const now = Date.now();
    if (!manager) {
      const unsupported = {
        supported: false,
        level: null,
        charging: null,
        chargingTime: null,
        dischargingTime: null,
        estimatedDischargeMinutes: null,
        sampledAt: now,
      };
      this.batteryStatusCache = unsupported;
      this.batteryStatusCacheUntil = now + 8000;
      return unsupported;
    }

    const dischargingTime = Number.isFinite(manager.dischargingTime) ? manager.dischargingTime : null;
    const status: BatteryStatus = {
      supported: true,
      level: Number(manager.level),
      charging: manager.charging,
      chargingTime: Number.isFinite(manager.chargingTime) ? manager.chargingTime : null,
      dischargingTime,
      estimatedDischargeMinutes: dischargingTime ? Math.round(dischargingTime / 60) : null,
      sampledAt: now,
    };

    if (status.charging === false && typeof status.level === 'number' && status.level <= this.batteryWarningThreshold) {
      this.performanceStats.batteryWarnings += 1;
    }

    this.batteryStatusCache = status;
    this.batteryStatusCacheUntil = now + 15000;
    return status;
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
    const decision = await this.getAdaptiveSamplingDecision(speedMetersPerSecond ?? null, this.appState);

    if (decision.shouldSleep) {
      return {
        strategy: 'power-saving',
        watchOptions: decision.watchOptions,
        expectedBatteryConsumption8h: 14,
      };
    }

    if (decision.intervalSeconds >= 30) {
      return {
        strategy: 'power-saving',
        watchOptions: decision.watchOptions,
        expectedBatteryConsumption8h: 18,
      };
    }

    if (decision.intervalSeconds >= 12) {
      return {
        strategy: 'balanced',
        watchOptions: decision.watchOptions,
        expectedBatteryConsumption8h: 24,
      };
    }

    return {
      strategy: 'high-accuracy',
      watchOptions: decision.watchOptions,
      expectedBatteryConsumption8h: 29,
    };
  }

  public async optimizeSamplingByBattery(speedMetersPerSecond?: number | null): Promise<BatteryOptimizationProfile> {
    const profile = await this.getOptimizedWatchProfile(speedMetersPerSecond);
    this.configure(profile.watchOptions);
    return profile;
  }

  public async getAdaptiveSamplingDecision(
    speedMetersPerSecond?: number | null,
    state: 'foreground' | 'background' = this.appState,
  ): Promise<AdaptiveSamplingDecision> {
    const batteryStatus = await this.getBatteryStatus();
    const speed = Math.max(0, Number(speedMetersPerSecond ?? this.lastLocation?.speed ?? 0));
    const scene = this.detectActivityScene(speed);

    let intervalSeconds = this.getSceneInterval(scene);
    const reasons: string[] = [`scene:${scene}`];

    if (this.sleepState.sleeping) {
      intervalSeconds = Math.max(intervalSeconds, this.strategy.sleepIntervalSec);
      reasons.push('sleeping');
    }

    const lowBattery = batteryStatus.supported
      && batteryStatus.charging === false
      && typeof batteryStatus.level === 'number'
      && batteryStatus.level <= 0.2;

    if (lowBattery || this.lowPowerModeEnabled) {
      intervalSeconds = Math.round(intervalSeconds * this.strategy.lowPowerIntervalMultiplier);
      reasons.push(lowBattery ? 'low-battery' : 'power-saving-switch');
    }

    if (state === 'background') {
      intervalSeconds = Math.max(intervalSeconds, this.strategy.backgroundMinIntervalSec);
      reasons.push('background-limited');
      this.performanceStats.backgroundSamplesLimited += 1;
    }

    intervalSeconds = Math.max(3, Math.min(180, intervalSeconds));
    const watchOptions = this.buildWatchOptionsByInterval(intervalSeconds, scene);

    this.performanceStats.lastScene = scene;
    return {
      scene,
      intervalSeconds,
      shouldSleep: this.sleepState.sleeping,
      reason: reasons,
      watchOptions,
    };
  }

  public shouldCollectBackgroundSample(lastCollectedAt: number, now: number = Date.now()): boolean {
    const elapsedSeconds = Math.max(0, (now - lastCollectedAt) / 1000);
    return elapsedSeconds >= this.strategy.backgroundMinIntervalSec;
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

  public predictNextLocation(secondsAhead = 5): LocationData | null {
    if (this.recentMotions.length < 2) {
      return this.lastLocation;
    }

    const recent = this.recentMotions[this.recentMotions.length - 1];
    const speed = Math.max(0, recent.speed);
    const heading = recent.heading ?? this.lastLocation?.heading ?? 0;
    const deltaMeters = speed * Math.max(0, secondsAhead);

    if (deltaMeters <= 0.1 || !this.lastLocation) {
      return this.lastLocation;
    }

    const rad = (heading * Math.PI) / 180;
    const deltaLat = (deltaMeters * Math.cos(rad)) / 111320;
    const latFactor = Math.max(0.0001, Math.cos((this.lastLocation.latitude * Math.PI) / 180));
    const deltaLon = (deltaMeters * Math.sin(rad)) / (111320 * latFactor);

    return {
      ...this.lastLocation,
      latitude: this.lastLocation.latitude + deltaLat,
      longitude: this.lastLocation.longitude + deltaLon,
      timestamp: Date.now() + secondsAhead * 1000,
    };
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
    this.recentMotions = [];
    this.smoothingReady = false;
  }

  private detectActivityScene(speedMetersPerSecond: number): ActivityScene {
    if (this.manualScene) {
      return this.manualScene;
    }
    if (!this.sceneLearningEnabled) {
      return this.performanceStats.lastScene;
    }
    if (speedMetersPerSecond < 0.5) {
      return 'stationary';
    }
    if (speedMetersPerSecond < 2.2) {
      return 'walking';
    }
    if (speedMetersPerSecond < 7) {
      return 'cycling';
    }
    return 'driving';
  }

  private getSceneInterval(scene: ActivityScene): number {
    if (scene === 'stationary') {
      return this.strategy.stationaryIntervalSec;
    }
    if (scene === 'walking') {
      return this.strategy.walkingIntervalSec;
    }
    if (scene === 'cycling') {
      return this.strategy.cyclingIntervalSec;
    }
    return this.strategy.drivingIntervalSec;
  }

  private buildWatchOptionsByInterval(intervalSec: number, scene: ActivityScene): LocationWatchOptions {
    const lowDetail = this.sleepState.sleeping || intervalSec >= 30;
    const desiredAccuracy = lowDetail
      ? 'low'
      : scene === 'walking' || scene === 'cycling'
        ? 'medium'
        : 'high';

    return {
      enableHighAccuracy: !lowDetail,
      timeout: Math.max(5000, intervalSec * 1000),
      distanceFilter: lowDetail ? 20 : scene === 'driving' ? 8 : 5,
      desiredAccuracy,
    };
  }

  private applyKalman(state: KalmanState, measurement: number): number {
    state.error += this.processVariance;
    const kalmanGain = state.error / (state.error + this.measurementVariance);
    state.estimate += kalmanGain * (measurement - state.estimate);
    state.error *= 1 - kalmanGain;
    return state.estimate;
  }

  private applySmoothing(location: LocationData): LocationData {
    if (!this.smoothingReady) {
      this.kalmanLat = { estimate: location.latitude, error: 1 };
      this.kalmanLon = { estimate: location.longitude, error: 1 };
      this.smoothingReady = true;
      return location;
    }

    const smoothLat = this.applyKalman(this.kalmanLat, location.latitude);
    const smoothLon = this.applyKalman(this.kalmanLon, location.longitude);

    this.performanceStats.smoothedUpdates += 1;
    return {
      ...location,
      latitude: Number(smoothLat.toFixed(8)),
      longitude: Number(smoothLon.toFixed(8)),
    };
  }

  private updateSleepState(location: LocationData): void {
    if (!this.lastLocation) {
      this.sleepState = {
        sleeping: false,
        since: null,
        reason: null,
      };
      return;
    }

    const distance = this.calculateDistance(this.lastLocation, location);
    const moving = distance >= this.strategy.movementDistanceThresholdMeters;

    if (moving) {
      if (this.sleepState.sleeping) {
        this.performanceStats.sleepTransitions += 1;
      }
      this.sleepState = {
        sleeping: false,
        since: null,
        reason: null,
      };
      return;
    }

    const since = this.sleepState.since ?? this.lastLocation.timestamp;
    const stillSeconds = Math.max(0, (location.timestamp - since) / 1000);

    if (stillSeconds >= this.strategy.stationarySleepDelaySec) {
      if (!this.sleepState.sleeping) {
        this.performanceStats.sleepTransitions += 1;
      }
      this.sleepState = {
        sleeping: true,
        since,
        reason: 'stationary-detected',
      };
      return;
    }

    this.sleepState = {
      sleeping: false,
      since,
      reason: 'stabilizing',
    };
  }

  private updateMotionHistory(location: LocationData): void {
    this.recentMotions.push({
      latitude: location.latitude,
      longitude: location.longitude,
      speed: Math.max(0, Number(location.speed ?? 0)),
      heading: location.heading ?? null,
      timestamp: location.timestamp,
    });

    if (this.recentMotions.length > this.maxMotionSamples) {
      this.recentMotions.splice(0, this.recentMotions.length - this.maxMotionSamples);
    }
  }

  private updatePerformanceStats(location: LocationData): void {
    this.performanceStats.totalUpdates += 1;
    this.performanceStats.lastUpdatedAt = location.timestamp;

    const validSpeeds = this.recentMotions
      .map((item) => item.speed)
      .filter((value) => Number.isFinite(value));

    if (validSpeeds.length > 0) {
      const total = validSpeeds.reduce((sum, speed) => sum + speed, 0);
      this.performanceStats.averageSpeed = Number((total / validSpeeds.length).toFixed(3));
    }

    if (this.recentMotions.length >= 2) {
      const previous = this.recentMotions[this.recentMotions.length - 2];
      const delta = this.calculateDistance(previous, location);
      this.performanceStats.totalDistanceMeters = Number((this.performanceStats.totalDistanceMeters + delta).toFixed(3));
    }
  }

  private async processLocationUpdate(location: LocationData): Promise<LocationData> {
    const smoothed = this.applySmoothing(location);
    this.updateMotionHistory(smoothed);
    this.updateSleepState(smoothed);
    this.updatePerformanceStats(smoothed);
    return smoothed;
  }

  private async handleLocationStream(data: LocationData): Promise<void> {
    try {
      const processed = await this.processLocationUpdate(data);
      this.lastLocation = processed;
      this.notifyLocationListeners(processed);
      await this.applyAdaptiveSampling(processed);
    } catch (error) {
      this.notifyErrorListeners(error as Error);
    }
  }

  private async applyAdaptiveSampling(location: LocationData): Promise<void> {
    const decision = await this.getAdaptiveSamplingDecision(location.speed ?? 0, this.appState);
    if (this.lastDecisionIntervalSec !== null && Math.abs(decision.intervalSeconds - this.lastDecisionIntervalSec) < 2) {
      this.performanceStats.skippedComputations += 1;
      return;
    }

    this.lastDecisionIntervalSec = decision.intervalSeconds;
    this.configure(decision.watchOptions);
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
    const status = await this.getBatteryStatus(true);
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
