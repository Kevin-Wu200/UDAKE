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
});
