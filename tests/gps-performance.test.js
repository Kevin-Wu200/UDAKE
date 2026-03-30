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

    // 等待初始状态通知完成
    await new Promise(resolve => setTimeout(resolve, 10));
    listener.mockClear();

    // 更新电池值并触发事件
    battery.level = 0.6;
    battery.dispatchEvent(new Event('levelchange'));

    // 等待事件处理完成
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

      const profile = await locationService.getOptimizedWatchProfile(scenario.speed);
      expect(profile.expectedBatteryConsumption8h).toBeLessThanOrEqual(scenario.maxConsumption);
    }
  });
});
