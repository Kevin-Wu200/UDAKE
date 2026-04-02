import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { locationService } from '../apps/frontend/js/services/LocationService';

function createBatteryManager(overrides = {}) {
  const manager = new EventTarget();
  Object.assign(manager, {
    level: 0.8,
    charging: false,
    chargingTime: Infinity,
    dischargingTime: 8 * 60 * 60,
    ...overrides
  });
  return manager;
}

function createLocation(overrides = {}) {
  return {
    latitude: 39.9042,
    longitude: 116.4074,
    accuracy: 5,
    altitude: null,
    altitudeAccuracy: null,
    heading: 90,
    speed: 0,
    timestamp: Date.now(),
    ...overrides
  };
}

describe('GPS功耗与实时同步性能', () => {
  let originalGetBattery;

  beforeEach(() => {
    originalGetBattery = navigator.getBattery;
    locationService.stopBatteryMonitoring();
    locationService.configure({
      enableHighAccuracy: true,
      timeout: 10000,
      distanceFilter: 10
    });
    locationService['batteryManager'] = null;
    locationService['batteryStatusCache'] = null;
    locationService['batteryStatusCacheUntil'] = 0;
    locationService.setManualScene(null);
    locationService.setAppState('foreground');
    locationService.setPowerSavingMode(false);
    locationService.enableSceneLearning(true);
    locationService.setSamplingStrategy({
      stationaryIntervalSec: 60,
      walkingIntervalSec: 15,
      cyclingIntervalSec: 10,
      drivingIntervalSec: 5,
      sleepIntervalSec: 90,
      backgroundMinIntervalSec: 30,
      lowPowerIntervalMultiplier: 2,
      movementDistanceThresholdMeters: 5,
      stationarySleepDelaySec: 180
    });
    locationService.resetPerformanceStats();
    locationService['recentMotions'] = [];
    locationService['sleepState'] = { sleeping: false, since: null, reason: null };
    locationService['lastLocation'] = null;
    locationService['smoothingReady'] = false;
  });

  afterEach(() => {
    if (originalGetBattery) {
      Object.defineProperty(navigator, 'getBattery', {
        configurable: true,
        writable: true,
        value: originalGetBattery
      });
    } else {
      delete navigator.getBattery;
    }
    locationService.stopBatteryMonitoring();
    vi.restoreAllMocks();
  });

  it('应支持电池监控API并推送电量变化事件', async () => {
    const battery = createBatteryManager({ level: 0.7, dischargingTime: 7 * 60 * 60 });
    Object.defineProperty(navigator, 'getBattery', {
      configurable: true,
      writable: true,
      value: vi.fn(async () => battery)
    });

    const listener = vi.fn();
    const removeListener = locationService.addBatteryListener(listener);
    const started = await locationService.startBatteryMonitoring();
    expect(started).toBe(true);

    await new Promise(resolve => setTimeout(resolve, 10));
    listener.mockClear();

    battery.level = 0.6;
    battery.dispatchEvent(new Event('levelchange'));

    await new Promise(resolve => setTimeout(resolve, 20));

    expect(listener).toHaveBeenCalled();
    const latest = listener.mock.calls.at(-1)[0];
    expect(latest.supported).toBe(true);
    expect(latest.level).toBeCloseTo(0.6, 2);

    removeListener();
  });

  it('低电量下应进入节能采样策略', async () => {
    const battery = createBatteryManager({
      level: 0.15,
      charging: false,
      dischargingTime: 2.5 * 60 * 60
    });
    Object.defineProperty(navigator, 'getBattery', {
      configurable: true,
      writable: true,
      value: vi.fn(async () => battery)
    });

    const profile = await locationService.optimizeSamplingByBattery(1.6);
    expect(profile.strategy).toBe('power-saving');
    expect(profile.watchOptions.enableHighAccuracy).toBe(false);
    expect(profile.watchOptions.distanceFilter).toBeGreaterThanOrEqual(20);
    expect(profile.expectedBatteryConsumption8h).toBeLessThan(30);
  });

  it('8小时连续追踪耗电估算应低于30%', () => {
    const start = Date.UTC(2026, 2, 30, 0, 0, 0);
    const samples = [
      { timestamp: start, level: 1.0 },
      { timestamp: start + 4 * 60 * 60 * 1000, level: 0.86 },
      { timestamp: start + 8 * 60 * 60 * 1000, level: 0.72 }
    ];

    const consumed = locationService.estimateBatteryConsumption(samples, 8);
    expect(consumed).toBeCloseTo(28, 1);
    expect(consumed).toBeLessThan(30);
  });

  it('应覆盖多场景功耗自动化验证脚本', async () => {
    const scenarios = [
      { name: '城市步行', level: 0.45, charging: false, speed: 1.2, maxConsumption: 30 },
      { name: '静止后台', level: 0.35, charging: false, speed: 0.2, maxConsumption: 26 },
      { name: '低电量应急', level: 0.12, charging: false, speed: 0.8, maxConsumption: 22 }
    ];

    for (const scenario of scenarios) {
      const battery = createBatteryManager({
        level: scenario.level,
        charging: scenario.charging,
        dischargingTime: 6 * 60 * 60
      });
      Object.defineProperty(navigator, 'getBattery', {
        configurable: true,
        writable: true,
        value: vi.fn(async () => battery)
      });
      locationService['batteryManager'] = null;
      locationService['batteryStatusCache'] = null;
      locationService['batteryStatusCacheUntil'] = 0;

      const profile = await locationService.getOptimizedWatchProfile(scenario.speed);
      expect(profile.expectedBatteryConsumption8h).toBeLessThanOrEqual(scenario.maxConsumption);
    }
  });

  it('应根据静止时长进入智能休眠并在移动后唤醒', async () => {
    const battery = createBatteryManager({ level: 0.6, charging: false });
    Object.defineProperty(navigator, 'getBattery', {
      configurable: true,
      writable: true,
      value: vi.fn(async () => battery)
    });

    locationService.setSleepThreshold(60);

    const t0 = Date.UTC(2026, 3, 1, 8, 0, 0);
    const p1 = await locationService['processLocationUpdate'](createLocation({ timestamp: t0 }));
    locationService['lastLocation'] = p1;

    const p2 = await locationService['processLocationUpdate'](createLocation({
      latitude: 39.904201,
      longitude: 116.407401,
      timestamp: t0 + 70_000,
      speed: 0
    }));
    locationService['lastLocation'] = p2;

    let decision = await locationService.getAdaptiveSamplingDecision(0.1, 'foreground');
    expect(decision.shouldSleep).toBe(true);
    expect(decision.intervalSeconds).toBeGreaterThanOrEqual(60);

    const p3 = await locationService['processLocationUpdate'](createLocation({
      latitude: 39.905,
      longitude: 116.408,
      timestamp: t0 + 90_000,
      speed: 1.8
    }));
    locationService['lastLocation'] = p3;

    decision = await locationService.getAdaptiveSamplingDecision(1.8, 'foreground');
    expect(decision.shouldSleep).toBe(false);
  });

  it('应支持场景识别与手动场景覆盖', async () => {
    const battery = createBatteryManager({ level: 0.8, charging: false });
    Object.defineProperty(navigator, 'getBattery', {
      configurable: true,
      writable: true,
      value: vi.fn(async () => battery)
    });

    const autoDriving = await locationService.getAdaptiveSamplingDecision(10, 'foreground');
    expect(autoDriving.scene).toBe('driving');
    expect(autoDriving.intervalSeconds).toBeLessThanOrEqual(6);

    locationService.setManualScene('walking');
    const forcedWalking = await locationService.getAdaptiveSamplingDecision(10, 'foreground');
    expect(forcedWalking.scene).toBe('walking');
    expect(forcedWalking.intervalSeconds).toBeGreaterThanOrEqual(15);
  });

  it('后台场景应限制采样频率', async () => {
    const battery = createBatteryManager({ level: 0.75, charging: false });
    Object.defineProperty(navigator, 'getBattery', {
      configurable: true,
      writable: true,
      value: vi.fn(async () => battery)
    });

    const decision = await locationService.getAdaptiveSamplingDecision(6.5, 'background');
    expect(decision.intervalSeconds).toBeGreaterThanOrEqual(30);
    expect(locationService.shouldCollectBackgroundSample(Date.now() - 10_000)).toBe(false);
    expect(locationService.shouldCollectBackgroundSample(Date.now() - 35_000)).toBe(true);
  });

  it('卡尔曼平滑应降低轨迹抖动并支持位置预测', async () => {
    const base = Date.UTC(2026, 3, 1, 9, 0, 0);
    const noisy = [
      createLocation({ latitude: 39.9042, longitude: 116.4074, speed: 2, heading: 0, timestamp: base }),
      createLocation({ latitude: 39.9049, longitude: 116.4081, speed: 2, heading: 0, timestamp: base + 1000 }),
      createLocation({ latitude: 39.9043, longitude: 116.4076, speed: 2, heading: 0, timestamp: base + 2000 })
    ];

    let last;
    for (const point of noisy) {
      last = await locationService['processLocationUpdate'](point);
      locationService['lastLocation'] = last;
    }

    expect(last.latitude).toBeLessThan(39.9049);
    expect(last.latitude).toBeGreaterThan(39.9042);

    const predicted = locationService.predictNextLocation(5);
    expect(predicted).not.toBeNull();
    expect(predicted.timestamp).toBeGreaterThan(last.timestamp);
  });

  it('应提供可观测的GPS性能监控统计', async () => {
    const t0 = Date.UTC(2026, 3, 1, 10, 0, 0);
    const points = [
      createLocation({ timestamp: t0, speed: 0.6 }),
      createLocation({ latitude: 39.9045, longitude: 116.4078, timestamp: t0 + 1000, speed: 1.1 }),
      createLocation({ latitude: 39.9051, longitude: 116.4085, timestamp: t0 + 2000, speed: 1.5 })
    ];

    for (const p of points) {
      const updated = await locationService['processLocationUpdate'](p);
      locationService['lastLocation'] = updated;
    }

    const stats = locationService.getPerformanceStats();
    expect(stats.totalUpdates).toBe(3);
    expect(stats.totalDistanceMeters).toBeGreaterThan(0);
    expect(stats.averageSpeed).toBeGreaterThan(0.5);
    expect(stats.smoothedUpdates).toBeGreaterThanOrEqual(2);

    locationService.resetPerformanceStats();
    const reset = locationService.getPerformanceStats();
    expect(reset.totalUpdates).toBe(0);
    expect(reset.totalDistanceMeters).toBe(0);
  });
});
