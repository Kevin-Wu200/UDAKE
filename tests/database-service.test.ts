import { beforeEach, describe, expect, it, vi } from 'vitest';
import { databaseService } from '../apps/frontend/js/services/DatabaseService';

function resetDatabaseServiceState(): void {
  (databaseService as any).backend = 'indexeddb';
  (databaseService as any).sqliteBridge = null;
  (databaseService as any).sqliteConnection = null;
  (databaseService as any).metrics = [];
  (databaseService as any).indexedDB = null;
}

async function deleteDb(name: string): Promise<void> {
  await new Promise((resolve) => {
    const req = indexedDB.deleteDatabase(name);
    req.onsuccess = () => resolve(undefined);
    req.onerror = () => resolve(undefined);
    req.onblocked = () => resolve(undefined);
  });
}

describe('DatabaseService', () => {
  beforeEach(async () => {
    resetDatabaseServiceState();
    await deleteDb('udake_mobile_gps');
  });

  it('无 SQLite 插件时应回退到 IndexedDB', async () => {
    (window as any).Capacitor = undefined;
    const backend = await databaseService.initialize('sqlite');
    expect(backend).toBe('indexeddb');
  });

  it('IndexedDB 模式应支持 GPS 样点 CRUD', async () => {
    await databaseService.initialize('indexeddb');
    await databaseService.saveGPSSample({
      id: 's1',
      projectId: 'p1',
      latitude: 39.9,
      longitude: 116.4,
      accuracy: 5,
      altitude: null,
      speed: null,
      heading: null,
      attributes: { source: 'test' },
      collectedAt: Date.now(),
      updatedAt: Date.now(),
      version: 1,
      source: 'mobile',
      synced: false
    });

    const one = await databaseService.getGPSSample('s1');
    expect(one).toBeTruthy();
    expect(one?.projectId).toBe('p1');

    const list = await databaseService.getGPSSamples('p1', 10);
    expect(list).toHaveLength(1);

    await databaseService.deleteGPSSample('s1');
    const removed = await databaseService.getGPSSample('s1');
    expect(removed).toBeNull();
  });

  it('SQLite 模式应可读写并输出查询性能统计', async () => {
    const memoryRows = new Map<string, any>();
    const metaRows = new Map<string, string>();
    const fakeConn = {
      open: vi.fn(async () => undefined),
      run: vi.fn(async (sql: string, values: any[]) => {
        if (/INSERT OR REPLACE/i.test(sql)) {
          const row = {
            id: values[0],
            project_id: values[1],
            latitude: values[2],
            longitude: values[3],
            accuracy: values[4],
            altitude: values[5],
            speed: values[6],
            heading: values[7],
            attributes: values[8],
            collected_at: values[9],
            updated_at: values[10],
            version: values[11],
            source: values[12],
            synced: values[13]
          };
          memoryRows.set(row.id, row);
        }
        if (/DELETE FROM/i.test(sql)) {
          memoryRows.delete(String(values[0]));
        }
        if (/UPDATE .* SET synced = 1/i.test(sql)) {
          const row = memoryRows.get(String(values[0]));
          if (row) {
            row.synced = 1;
            memoryRows.set(String(values[0]), row);
          }
        }
        if (/INSERT OR REPLACE INTO db_meta/i.test(sql)) {
          metaRows.set(String(values[0]), String(values[1]));
        }
      }),
      query: vi.fn(async (sql: string, values: any[]) => {
        if (/FROM db_meta/i.test(sql)) {
          const value = metaRows.get(String(values[0]));
          return { values: value ? [{ value }] : [] };
        }
        if (/WHERE id = \?/i.test(sql)) {
          const row = memoryRows.get(String(values[0]));
          return { values: row ? [row] : [] };
        }
        if (/WHERE project_id = \?/i.test(sql)) {
          const rows = Array.from(memoryRows.values()).filter((row) => row.project_id === values[0]);
          return { values: rows.slice(0, values[1] || rows.length) };
        }
        if (/ORDER BY updated_at DESC LIMIT \?/i.test(sql)) {
          const rows = Array.from(memoryRows.values())
            .sort((a, b) => Number(b.updated_at) - Number(a.updated_at))
            .slice(0, values[0] || 1000);
          return { values: rows };
        }
        return { values: [] };
      })
    };

    (window as any).Capacitor = {
      Plugins: {
        SQLite: {
          createConnection: vi.fn(async () => fakeConn)
        }
      }
    };

    const backend = await databaseService.initialize('sqlite');
    expect(backend).toBe('sqlite');

    await databaseService.saveGPSSample({
      id: 'sqlite-1',
      projectId: 'proj-x',
      latitude: 30.1,
      longitude: 120.1,
      accuracy: 3,
      altitude: null,
      speed: 1.2,
      heading: 90,
      attributes: { env: 'city' },
      collectedAt: Date.now(),
      updatedAt: Date.now(),
      version: 1,
      source: 'mobile',
      synced: false
    });

    const rows = await databaseService.getGPSSamples('proj-x', 20);
    expect(rows).toHaveLength(1);
    expect(rows[0].projectId).toBe('proj-x');

    const perf = databaseService.getQueryPerformanceSummary();
    expect(perf.backend).toBe('sqlite');
    expect(perf.count).toBeGreaterThan(0);

    const schemaVersion = await databaseService.getSchemaVersion();
    expect(schemaVersion).toBeGreaterThanOrEqual(2);
  });

  it('应支持数据库到服务端的同步标记', async () => {
    await databaseService.initialize('indexeddb');
    await databaseService.saveGPSSamples([
      {
        id: 'sync-1',
        projectId: 'proj-sync',
        latitude: 39.9,
        longitude: 116.4,
        accuracy: 5,
        altitude: null,
        speed: null,
        heading: null,
        attributes: {},
        collectedAt: Date.now(),
        updatedAt: Date.now(),
        version: 1,
        source: 'mobile',
        synced: false
      },
      {
        id: 'sync-2',
        projectId: 'proj-sync',
        latitude: 39.91,
        longitude: 116.41,
        accuracy: 5,
        altitude: null,
        speed: null,
        heading: null,
        attributes: {},
        collectedAt: Date.now(),
        updatedAt: Date.now(),
        version: 1,
        source: 'mobile',
        synced: false
      }
    ]);

    const result = await databaseService.syncToServer(async (samples) => {
      expect(samples.length).toBe(2);
      return { success: 2, failed: 0 };
    });
    expect(result.success).toBe(2);

    const all = await databaseService.getAllGPSSamples(10);
    expect(all.every((item) => item.synced)).toBe(true);
  });
});
