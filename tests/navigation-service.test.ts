import { beforeEach, describe, expect, it, vi } from 'vitest';

import { NavigationService } from '../apps/frontend/js/map/services/NavigationService';

function setOnlineState(online: boolean): void {
    Object.defineProperty(window.navigator, 'onLine', {
        configurable: true,
        value: online
    });
}

describe('NavigationService', () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        setOnlineState(true);
        (window as any).AMap = undefined;
    });

    it('离线路由应支持骑行模式并生成逐向提示', async () => {
        const map = {
            plugin: vi.fn()
        };
        const service = new NavigationService(map as any);

        const route = await service.planRoute('cycling', [116.397, 39.908], [116.407, 39.918], {
            forceOffline: true,
            lowPowerMode: false,
            enableVoice: false
        });

        expect(route.offline).toBe(true);
        expect(route.mode).toBe('cycling');
        expect(route.steps.length).toBeGreaterThan(0);
        expect(route.distanceMeters).toBeGreaterThan(0);
    });

    it('在线规划失败时应自动回退离线引擎', async () => {
        const map = {
            plugin: vi.fn((_plugins: string[], cb: () => void) => cb())
        };
        const service = new NavigationService(map as any);

        (window as any).AMap = {
            Walking: class {
                search(_start: [number, number], _end: [number, number], cb: (status: string, result: any) => void) {
                    cb('error', null);
                }
            }
        };

        const route = await service.planRoute('walking', [121.47, 31.23], [121.49, 31.25], {
            enableVoice: false
        });

        expect(route.offline).toBe(true);
        expect(route.source).toBe('offline-engine');
    });

    it('偏航检测应触发自动重规划', async () => {
        setOnlineState(false);
        const map = {
            plugin: vi.fn()
        };
        const service = new NavigationService(map as any);

        await service.planRoute('walking', [120.0, 30.0], [120.01, 30.01], {
            enableVoice: false
        });

        const rerouteListener = vi.fn();
        service.onReroute(rerouteListener);

        const result = await service.checkDeviationAndReplan([120.2, 30.2]);

        expect(result.deviated).toBe(true);
        expect(result.distanceMeters).toBeGreaterThan(0);
        expect(result.route).toBeTruthy();
        expect(rerouteListener).toHaveBeenCalledTimes(1);
    });

    it('低功耗预加载应减少离线路径采样点', () => {
        const map = {
            plugin: vi.fn()
        };
        const service = new NavigationService(map as any);

        const normal = service.predictivePreloadRoute('walking', [114.0, 22.5], [114.01, 22.51], false);
        const lowPower = service.predictivePreloadRoute('walking', [114.0, 22.5], [114.01, 22.51], true);

        expect(lowPower.polyline.length).toBeLessThan(normal.polyline.length);
        expect(lowPower.offline).toBe(true);
    });
});
