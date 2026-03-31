import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NavigationService } from '../apps/frontend/js/map/services/NavigationService';

function setNavigatorOnline(online) {
  Object.defineProperty(window.navigator, 'onLine', {
    configurable: true,
    value: online
  });
}

describe('导航功能测试', () => {
  let service;

  beforeEach(() => {
    setNavigatorOnline(false);
    service = new NavigationService({
      plugin: vi.fn()
    });
  });

  it('应覆盖驾车/步行/骑行路线规划正确性', async () => {
    const start = [116.397, 39.908];
    const end = [116.407, 39.918];

    const driving = await service.planRoute('driving', start, end, { forceOffline: true, enableVoice: false });
    const walking = await service.planRoute('walking', start, end, { forceOffline: true, enableVoice: false });
    const cycling = await service.planRoute('cycling', start, end, { forceOffline: true, enableVoice: false });

    expect(driving.distanceMeters).toBeGreaterThan(0);
    expect(walking.distanceMeters).toBeGreaterThan(0);
    expect(cycling.distanceMeters).toBeGreaterThan(0);
    expect(driving.steps.length).toBeGreaterThan(0);
    expect(walking.steps.length).toBeGreaterThan(0);
    expect(cycling.steps.length).toBeGreaterThan(0);
  });

  it('应生成逐向导航提示并支持偏航重规划', async () => {
    const route = await service.planRoute(
      'walking',
      [121.47, 31.23],
      [121.49, 31.25],
      { forceOffline: true, enableVoice: false }
    );
    expect(route.steps.some((step) => typeof step.instruction === 'string' && step.instruction.length > 0)).toBe(true);

    const replanned = await service.checkDeviationAndReplan([121.7, 31.6]);
    expect(replanned.deviated).toBe(true);
    expect(replanned.route).toBeTruthy();
  });

  it('应支持导航边界测试（极值坐标）', async () => {
    const route = await service.planRoute(
      'walking',
      [-179.999, 89.999],
      [179.999, -89.999],
      { forceOffline: true, enableVoice: false }
    );
    expect(route.distanceMeters).toBeGreaterThan(0);
    expect(route.polyline.length).toBeGreaterThan(1);
  });

  it('应满足导航性能响应时间小于2秒', async () => {
    const startedAt = Date.now();
    await service.planRoute('walking', [114.05, 22.55], [114.07, 22.58], {
      forceOffline: true,
      enableVoice: false
    });
    const elapsedMs = Date.now() - startedAt;
    expect(elapsedMs).toBeLessThan(2000);
  });

  it('应通过长时间导航稳定性测试与准确率校验', async () => {
    const start = [113.2644, 23.1291];
    const end = [113.3244, 23.1091];
    const rounds = 120;
    let success = 0;

    for (let i = 0; i < rounds; i += 1) {
      const route = await service.planRoute('walking', start, end, {
        forceOffline: true,
        enableVoice: false,
        disableCache: true
      });
      const hasValidGeometry = route.polyline.length >= 2
        && route.start[0] === start[0]
        && route.start[1] === start[1]
        && route.end[0] === end[0]
        && route.end[1] === end[1];
      if (hasValidGeometry && route.distanceMeters > 0 && route.steps.length > 0) {
        success += 1;
      }
    }

    const accuracy = (success / rounds) * 100;
    expect(accuracy).toBeGreaterThanOrEqual(95);
  });

  it('应支持多路线对比（时长差异符合预期）', async () => {
    const start = [116.35, 39.9];
    const end = [116.45, 39.95];

    const driving = await service.planRoute('driving', start, end, { forceOffline: true, enableVoice: false });
    const cycling = await service.planRoute('cycling', start, end, { forceOffline: true, enableVoice: false });
    const walking = await service.planRoute('walking', start, end, { forceOffline: true, enableVoice: false });

    expect(driving.durationSeconds).toBeLessThan(cycling.durationSeconds);
    expect(cycling.durationSeconds).toBeLessThan(walking.durationSeconds);
  });
});
