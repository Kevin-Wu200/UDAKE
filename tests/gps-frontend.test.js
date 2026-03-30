import { describe, it, expect, vi, beforeEach } from 'vitest';
import { offlineMapService, __offlineMapInternals } from '../apps/frontend/js/map/services/OfflineMapService';
import { calculateBackoffDelay } from '../apps/frontend/js/services/GPSSyncService';
import { gpsSyncService } from '../apps/frontend/js/services/GPSSyncService';
import { OfflineManager } from '../apps/frontend/js/utils/OfflineManager.js';

describe('GPS前端能力测试', () => {
  beforeEach(() => {
    global.fetch = vi.fn(async () => ({
      ok: true,
      blob: async () => new Blob(['tile-data'], { type: 'image/png' })
    }));
  });

  it('瓦片工具应正确生成键和URL', () => {
    const tile = { z: 10, x: 843, y: 388 };
    const key = __offlineMapInternals.buildTileKey('v1', tile);
    const url = __offlineMapInternals.applyTemplate('https://a.example.com/{z}/{x}/{y}.png', tile);

    expect(key).toBe('v1:10:843:388');
    expect(url).toBe('https://a.example.com/10/843/388.png');
  });

  it('经纬度转瓦片坐标应输出整数', () => {
    const x = __offlineMapInternals.lonToTileX(116.4074, 12);
    const y = __offlineMapInternals.latToTileY(39.9042, 12);

    expect(Number.isInteger(x)).toBe(true);
    expect(Number.isInteger(y)).toBe(true);
    expect(x).toBeGreaterThan(0);
    expect(y).toBeGreaterThan(0);
  });

  it('应支持离线区域下载任务并产生存储统计', async () => {
    await offlineMapService.init();

    const taskId = await offlineMapService.createRegionDownloadTask({
      name: '测试区域',
      bbox: [116.407, 39.903, 116.408, 39.904],
      minZoom: 16,
      maxZoom: 16,
      version: 'v-test',
      tileTemplate: 'https://a.example.com/{z}/{x}/{y}.png'
    });

    // 下载任务是后台异步执行，这里等待其完成
    const start = Date.now();
    let progress = offlineMapService.getTaskProgress(taskId);
    while (progress && progress.state === 'downloading' && Date.now() - start < 4000) {
      await new Promise((resolve) => setTimeout(resolve, 30));
      progress = offlineMapService.getTaskProgress(taskId);
    }

    const stats = await offlineMapService.getStorageStats();
    expect(progress).not.toBeNull();
    expect(stats.totalTiles).toBeGreaterThanOrEqual(1);
    expect(global.fetch).toHaveBeenCalled();
  });

  it('指数退避应随重试次数上升并限制上限', () => {
    const randomSpy = vi.spyOn(Math, 'random').mockReturnValue(0.5);

    const d1 = calculateBackoffDelay(0, 3000, 60000, 0.2);
    const d2 = calculateBackoffDelay(1, 3000, 60000, 0.2);
    const d5 = calculateBackoffDelay(5, 3000, 60000, 0.2);

    expect(d2).toBeGreaterThanOrEqual(d1);
    expect(d5).toBeLessThanOrEqual(60000);

    randomSpy.mockRestore();
  });

  it('应支持自适应批量同步与传输统计', async () => {
    const samples = Array.from({ length: 25 }, (_, i) => ({
      id: `s-${i}`,
      projectId: 'proj-a',
      latitude: 39.9 + i * 0.00001,
      longitude: 116.4 + i * 0.00001,
      accuracy: 2,
      updatedAt: Date.now() + i,
      collectedAt: Date.now() + i
    }));

    global.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ success: true }) }));
    const result = await gpsSyncService.syncSamples(samples, { forceHttp: true, adaptive: true });

    expect(result.success).toBeGreaterThan(0);
    expect(result.batches).toBeGreaterThan(0);
    expect(global.fetch).toHaveBeenCalled();
  });

  it('离线地图应支持版本元数据与更新调度', async () => {
    await offlineMapService.init();
    const regionId = await offlineMapService.createRegionDownloadTask({
      name: '调度区域',
      bbox: [116.407, 39.903, 116.408, 39.904],
      minZoom: 15,
      maxZoom: 15,
      version: 'v1',
      tileTemplate: 'https://a.example.com/{z}/{x}/{y}.png'
    });

    const meta = await offlineMapService.upsertVersionMeta({
      version: 'v2',
      baseVersion: 'v1',
      schemaVersion: 1,
      mapEngine: 'osm',
      manifestHash: 'm1',
      compatibleVersions: ['v1']
    });
    expect(meta.version).toBe('v2');

    const compatibility = await offlineMapService.checkVersionCompatibility('v1', 'v2');
    expect(compatibility.compatible).toBe(true);

    const schedule = await offlineMapService.scheduleRegionUpdate(regionId, 5, 'v2');
    expect(schedule.enabled).toBe(true);
    const schedules = await offlineMapService.listUpdateSchedules();
    expect(schedules.length).toBeGreaterThan(0);
  });

  it('应支持 IndexedDB/SQLite 方案评估', async () => {
    const result = await OfflineManager.evaluateStorageBackends();
    expect(['indexeddb', 'sqlite']).toContain(result.recommended);
    expect(typeof result.indexeddb.available).toBe('boolean');
    expect(typeof result.sqlite.available).toBe('boolean');
  });
});
