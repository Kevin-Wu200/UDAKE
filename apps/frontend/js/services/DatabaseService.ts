/**
 * 统一数据库服务
 * 优先使用 Capacitor SQLite，失败时回退 IndexedDB。
 */

export type StorageBackend = 'sqlite' | 'indexeddb';

export interface DatabaseGPSSample {
  id: string;
  projectId: string;
  latitude: number;
  longitude: number;
  accuracy: number;
  altitude: number | null;
  speed: number | null;
  heading: number | null;
  attributes: Record<string, unknown>;
  collectedAt: number;
  updatedAt: number;
  version: number;
  source: 'mobile' | 'web';
  synced?: boolean;
}

export interface MigrationSummary {
  migrated: number;
  skipped: number;
}

export interface QueryMetric {
  operation: string;
  elapsedMs: number;
  at: number;
  backend: StorageBackend;
}

export interface QueryPerformanceSummary {
  count: number;
  avgMs: number;
  p95Ms: number;
  maxMs: number;
  backend: StorageBackend;
}

const SQLITE_DB_NAME = 'udake_mobile_gps';
const SQLITE_TABLE = 'gps_samples';
const SQLITE_META_TABLE = 'db_meta';
const SQLITE_SCHEMA_VERSION = 2;
const INDEXEDDB_DB_NAME = 'udake_mobile_gps';
const INDEXEDDB_STORE = 'gpsSamples';
const LEGACY_DB_NAME = 'udake_offline';
const LEGACY_STORE = 'gpsSamples';

function nowMs(): number {
  return Date.now();
}

function isBrowser(): boolean {
  return typeof window !== 'undefined';
}

function toRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function toNullableNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function normalizeSample(sample: unknown): DatabaseGPSSample {
  const raw = toRecord(sample);
  const now = nowMs();
  return {
    id: String(raw.id || `gps_${now}_${Math.random().toString(36).slice(2, 8)}`),
    projectId: String(raw.projectId || raw.project_id || 'default_mobile_project'),
    latitude: Number(raw.latitude),
    longitude: Number(raw.longitude),
    accuracy: Number(raw.accuracy || 0),
    altitude: toNullableNumber(raw.altitude),
    speed: toNullableNumber(raw.speed),
    heading: toNullableNumber(raw.heading),
    attributes: (raw.attributes && typeof raw.attributes === 'object' && !Array.isArray(raw.attributes))
      ? (raw.attributes as Record<string, unknown>)
      : {},
    collectedAt: Number(raw.collectedAt || raw.collected_at || now),
    updatedAt: Number(raw.updatedAt || raw.updated_at || now),
    version: Number(raw.version || 1),
    source: raw.source === 'web' ? 'web' : 'mobile',
    synced: Boolean(raw.synced)
  };
}

function extractRows<T>(result: unknown): T[] {
  const raw = toRecord(result);
  if (!result) {
    return [];
  }
  if (Array.isArray(raw.values)) {
    return raw.values as T[];
  }
  if (Array.isArray(raw.rows)) {
    return raw.rows as T[];
  }
  const rowSource = raw.rows as { item?: (index: number) => T; length?: number } | undefined;
  if (rowSource && typeof rowSource.item === 'function' && typeof rowSource.length === 'number') {
    const rows: T[] = [];
    for (let i = 0; i < rowSource.length; i += 1) {
      rows.push(rowSource.item(i));
    }
    return rows;
  }
  return [];
}

export class DatabaseService {
  private static instance: DatabaseService;

  private backend: StorageBackend = 'indexeddb';
  private sqliteBridge: any = null;
  private sqliteConnection: any = null;
  private indexedDB: IDBDatabase | null = null;
  private metrics: QueryMetric[] = [];
  private memoryStore = new Map<string, DatabaseGPSSample>();

  public static getInstance(): DatabaseService {
    if (!DatabaseService.instance) {
      DatabaseService.instance = new DatabaseService();
    }
    return DatabaseService.instance;
  }

  public async initialize(preferred: StorageBackend = 'sqlite'): Promise<StorageBackend> {
    if (preferred === 'sqlite' && isBrowser()) {
      const bridge = this.detectSQLiteBridge();
      if (bridge) {
        try {
          this.sqliteBridge = bridge;
          await this.ensureSQLiteReady();
          this.backend = 'sqlite';
          return this.backend;
        } catch (error) {
          console.warn('[DatabaseService] SQLite 初始化失败，回退 IndexedDB:', error);
        }
      }
    }

    await this.ensureIndexedDBReady();
    this.backend = 'indexeddb';
    return this.backend;
  }

  public getBackend(): StorageBackend {
    return this.backend;
  }

  public async getSchemaVersion(): Promise<number> {
    if (this.backend !== 'sqlite') {
      return 0;
    }
    await this.ensureSQLiteConnection();
    await this.ensureSQLiteMetaTable();
    return this.readSQLiteSchemaVersion();
  }

  public async migrateLegacyIndexedDBToSQLite(): Promise<MigrationSummary> {
    if (this.backend !== 'sqlite') {
      return { migrated: 0, skipped: 0 };
    }

    const legacyRows = await this.readLegacySamples();
    if (legacyRows.length === 0) {
      return { migrated: 0, skipped: 0 };
    }

    const existingIds = new Set((await this.getAllGPSSamples(200000)).map((row) => row.id));
    let migrated = 0;
    let skipped = 0;

    for (const raw of legacyRows) {
      const sample = normalizeSample(raw);
      if (existingIds.has(sample.id)) {
        skipped += 1;
        continue;
      }
      await this.saveGPSSample(sample);
      migrated += 1;
    }

    return { migrated, skipped };
  }

  public async saveGPSSample(sample: DatabaseGPSSample): Promise<void> {
    const normalized = normalizeSample(sample);
    if (this.backend === 'sqlite') {
      await this.sqliteWriteSample(normalized);
      return;
    }
    await this.idbPut(normalized);
  }

  public async saveGPSSamples(samples: DatabaseGPSSample[]): Promise<void> {
    if (samples.length === 0) {
      return;
    }
    if (this.backend === 'sqlite') {
      for (const sample of samples) {
        await this.sqliteWriteSample(normalizeSample(sample));
      }
      return;
    }
    for (const sample of samples) {
      await this.idbPut(normalizeSample(sample));
    }
  }

  public async getGPSSample(id: string): Promise<DatabaseGPSSample | null> {
    if (this.backend === 'sqlite') {
      const rows = await this.sqliteQuery<any>(
        `SELECT * FROM ${SQLITE_TABLE} WHERE id = ? LIMIT 1`,
        [id],
        'sqlite:getGPSSample'
      );
      return rows.length > 0 ? this.sqliteRowToSample(rows[0]) : null;
    }

    const row = await this.idbGet(id);
    return row ? normalizeSample(row) : null;
  }

  public async getGPSSamples(projectId: string, limit = 500): Promise<DatabaseGPSSample[]> {
    const safeLimit = Math.max(1, Math.min(100000, Math.floor(limit)));

    if (this.backend === 'sqlite') {
      const rows = await this.sqliteQuery<any>(
        `SELECT * FROM ${SQLITE_TABLE} WHERE project_id = ? ORDER BY updated_at DESC LIMIT ?`,
        [projectId, safeLimit],
        'sqlite:getGPSSamples'
      );
      return rows.map((row) => this.sqliteRowToSample(row));
    }

    const rows = await this.idbGetByProject(projectId);
    return rows
      .map((row) => normalizeSample(row))
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, safeLimit);
  }

  public async getAllGPSSamples(limit = 5000): Promise<DatabaseGPSSample[]> {
    const safeLimit = Math.max(1, Math.min(200000, Math.floor(limit)));

    if (this.backend === 'sqlite') {
      const rows = await this.sqliteQuery<any>(
        `SELECT * FROM ${SQLITE_TABLE} ORDER BY updated_at DESC LIMIT ?`,
        [safeLimit],
        'sqlite:getAllGPSSamples'
      );
      return rows.map((row) => this.sqliteRowToSample(row));
    }

    const rows = await this.idbGetAll();
    return rows
      .map((row) => normalizeSample(row))
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, safeLimit);
  }

  public async deleteGPSSample(id: string): Promise<void> {
    if (this.backend === 'sqlite') {
      await this.sqliteRun(
        `DELETE FROM ${SQLITE_TABLE} WHERE id = ?`,
        [id],
        'sqlite:deleteGPSSample'
      );
      return;
    }
    await this.idbDelete(id);
  }

  public async getGPSProjectStats(): Promise<{ total: number; projectCounts: Record<string, number> }> {
    const rows = await this.getAllGPSSamples(200000);
    const projectCounts: Record<string, number> = {};
    rows.forEach((row) => {
      projectCounts[row.projectId] = (projectCounts[row.projectId] || 0) + 1;
    });
    return {
      total: rows.length,
      projectCounts
    };
  }

  public async markSynced(ids: string[]): Promise<void> {
    if (ids.length === 0) {
      return;
    }
    if (this.backend === 'sqlite') {
      for (const id of ids) {
        await this.sqliteRun(
          `UPDATE ${SQLITE_TABLE} SET synced = 1 WHERE id = ?`,
          [id],
          'sqlite:markSynced'
        );
      }
      return;
    }

    for (const id of ids) {
      const current = await this.idbGet(id);
      if (current) {
        await this.idbPut({ ...current, synced: true });
      }
    }
  }

  public async syncToServer(
    syncer: (samples: DatabaseGPSSample[]) => Promise<{ success: number; failed?: number }>
  ): Promise<{ success: number; failed: number; total: number }> {
    const pending = (await this.getAllGPSSamples(200000)).filter((row) => !row.synced);
    if (pending.length === 0) {
      return { success: 0, failed: 0, total: 0 };
    }

    const result = await syncer(pending);
    const success = Math.max(0, Math.min(pending.length, Number(result.success || 0)));
    const failed = Number.isFinite(result.failed) ? Number(result.failed) : pending.length - success;

    if (success > 0) {
      const syncedIds = pending.slice(0, success).map((item) => item.id);
      await this.markSynced(syncedIds);
    }

    return {
      success,
      failed: Math.max(0, failed),
      total: pending.length
    };
  }

  public getQueryPerformanceSummary(): QueryPerformanceSummary {
    if (this.metrics.length === 0) {
      return {
        count: 0,
        avgMs: 0,
        p95Ms: 0,
        maxMs: 0,
        backend: this.backend
      };
    }
    const elapsed = this.metrics.map((item) => item.elapsedMs).sort((a, b) => a - b);
    const total = elapsed.reduce((sum, value) => sum + value, 0);
    const p95 = elapsed[Math.floor((elapsed.length - 1) * 0.95)] || 0;
    return {
      count: elapsed.length,
      avgMs: Number((total / elapsed.length).toFixed(2)),
      p95Ms: Number(p95.toFixed(2)),
      maxMs: Number(elapsed[elapsed.length - 1].toFixed(2)),
      backend: this.backend
    };
  }

  private detectSQLiteBridge(): any | null {
    const win = window as any;
    return win?.Capacitor?.Plugins?.SQLite || win?.sqlitePlugin || null;
  }

  private async ensureSQLiteReady(): Promise<void> {
    await this.ensureSQLiteConnection();
    await this.ensureSQLiteMetaTable();
    await this.runSQLiteMigrations();
  }

  private async ensureSQLiteConnection(): Promise<void> {
    if (this.sqliteConnection) {
      return;
    }
    if (!this.sqliteBridge) {
      throw new Error('SQLite bridge 不可用');
    }

    const bridge = this.sqliteBridge;

    if (typeof bridge.createConnection === 'function') {
      try {
        this.sqliteConnection = await bridge.createConnection({
          database: SQLITE_DB_NAME,
          version: 1,
          encrypted: false,
          mode: 'no-encryption',
          readonly: false
        });
      } catch {
        this.sqliteConnection = await bridge.createConnection(
          SQLITE_DB_NAME,
          false,
          'no-encryption',
          1,
          false
        );
      }
      if (typeof this.sqliteConnection.open === 'function') {
        await this.sqliteConnection.open();
      }
      return;
    }

    this.sqliteConnection = bridge;
  }

  private async sqliteWriteSample(sample: DatabaseGPSSample): Promise<void> {
    await this.sqliteRun(
      `INSERT OR REPLACE INTO ${SQLITE_TABLE}
      (id, project_id, latitude, longitude, accuracy, altitude, speed, heading, attributes, collected_at, updated_at, version, source, synced)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        sample.id,
        sample.projectId,
        sample.latitude,
        sample.longitude,
        sample.accuracy,
        sample.altitude,
        sample.speed,
        sample.heading,
        JSON.stringify(sample.attributes || {}),
        sample.collectedAt,
        sample.updatedAt,
        sample.version,
        sample.source,
        sample.synced ? 1 : 0
      ],
      'sqlite:saveGPSSample'
    );
  }

  private sqliteRowToSample(row: any): DatabaseGPSSample {
    let attributes: Record<string, unknown> = {};
    try {
      const parsed = JSON.parse(String(row.attributes || '{}'));
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        attributes = parsed;
      }
    } catch {
      attributes = {};
    }

    return normalizeSample({
      id: row.id,
      projectId: row.project_id,
      latitude: row.latitude,
      longitude: row.longitude,
      accuracy: row.accuracy,
      altitude: row.altitude,
      speed: row.speed,
      heading: row.heading,
      attributes,
      collectedAt: row.collected_at,
      updatedAt: row.updated_at,
      version: row.version,
      source: row.source,
      synced: Number(row.synced) === 1
    });
  }

  private async sqliteRun(sql: string, values: unknown[], operation: string): Promise<void> {
    await this.ensureSQLiteConnection();
    const startedAt = nowMs();
    const conn = this.sqliteConnection;

    if (typeof conn.run === 'function') {
      await conn.run(sql, values);
      this.pushMetric(operation, nowMs() - startedAt);
      return;
    }
    if (typeof conn.execute === 'function') {
      await conn.execute(sql);
      this.pushMetric(operation, nowMs() - startedAt);
      return;
    }
    if (typeof conn.executeSet === 'function') {
      await conn.executeSet({
        set: [{ statement: sql, values }]
      });
      this.pushMetric(operation, nowMs() - startedAt);
      return;
    }
    if (this.sqliteBridge && typeof this.sqliteBridge.execute === 'function') {
      await this.sqliteBridge.execute({
        database: SQLITE_DB_NAME,
        statements: sql
      });
      this.pushMetric(operation, nowMs() - startedAt);
      return;
    }

    throw new Error('SQLite run API 不可用');
  }

  private async sqliteQuery<T>(sql: string, values: unknown[], operation: string): Promise<T[]> {
    await this.ensureSQLiteConnection();
    const startedAt = nowMs();
    const conn = this.sqliteConnection;
    let result: any = null;

    if (typeof conn.query === 'function') {
      result = await conn.query(sql, values);
      this.pushMetric(operation, nowMs() - startedAt);
      return extractRows<T>(result);
    }
    if (this.sqliteBridge && typeof this.sqliteBridge.query === 'function') {
      result = await this.sqliteBridge.query({
        database: SQLITE_DB_NAME,
        statement: sql,
        values
      });
      this.pushMetric(operation, nowMs() - startedAt);
      return extractRows<T>(result);
    }

    throw new Error('SQLite query API 不可用');
  }

  private pushMetric(operation: string, elapsedMs: number): void {
    this.metrics.push({
      operation,
      elapsedMs,
      at: nowMs(),
      backend: this.backend
    });
    if (this.metrics.length > 5000) {
      this.metrics.splice(0, this.metrics.length - 5000);
    }
  }

  private ensureIndexedDBReady(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.indexedDB) {
        resolve();
        return;
      }
      if (typeof indexedDB === 'undefined') {
        resolve();
        return;
      }
      const request = indexedDB.open(INDEXEDDB_DB_NAME, 1);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(INDEXEDDB_STORE)) {
          const store = db.createObjectStore(INDEXEDDB_STORE, { keyPath: 'id' });
          store.createIndex('projectId', 'projectId', { unique: false });
          store.createIndex('updatedAt', 'updatedAt', { unique: false });
        }
      };
      request.onsuccess = () => {
        this.indexedDB = request.result;
        resolve();
      };
      request.onerror = () => reject(request.error);
    });
  }

  private getIDBStore(mode: IDBTransactionMode): IDBObjectStore {
    if (!this.indexedDB) {
      throw new Error('IndexedDB 未初始化');
    }
    return this.indexedDB.transaction(INDEXEDDB_STORE, mode).objectStore(INDEXEDDB_STORE);
  }

  private idbRequest<T>(request: IDBRequest<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  private async idbPut(sample: DatabaseGPSSample): Promise<void> {
    this.memoryStore.set(sample.id, sample);
    await this.ensureIndexedDBReady();
    if (!this.indexedDB) {
      return;
    }
    const startedAt = nowMs();
    try {
      const store = this.getIDBStore('readwrite');
      await this.idbRequest(store.put(sample));
      this.pushMetric('indexeddb:put', nowMs() - startedAt);
    } catch (error) {
      console.warn('[DatabaseService] IndexedDB put 失败，已保留内存副本:', error);
    }
  }

  private async idbGet(id: string): Promise<any | null> {
    await this.ensureIndexedDBReady();
    if (!this.indexedDB) {
      return this.memoryStore.get(id) || null;
    }
    const startedAt = nowMs();
    try {
      const store = this.getIDBStore('readonly');
      const result = await this.idbRequest(store.get(id));
      this.pushMetric('indexeddb:get', nowMs() - startedAt);
      return result || this.memoryStore.get(id) || null;
    } catch (error) {
      console.warn('[DatabaseService] IndexedDB get 失败，使用内存副本:', error);
      return this.memoryStore.get(id) || null;
    }
  }

  private async idbGetByProject(projectId: string): Promise<any[]> {
    await this.ensureIndexedDBReady();
    if (!this.indexedDB) {
      return Array.from(this.memoryStore.values()).filter((row) => row.projectId === projectId);
    }
    const startedAt = nowMs();
    try {
      const store = this.getIDBStore('readonly');
      const index = store.index('projectId');
      const result = await this.idbRequest(index.getAll(projectId));
      this.pushMetric('indexeddb:getByProject', nowMs() - startedAt);
      if (Array.isArray(result) && result.length > 0) {
        return result;
      }
    } catch (error) {
      console.warn('[DatabaseService] IndexedDB project query 失败，使用内存副本:', error);
    }
    return Array.from(this.memoryStore.values()).filter((row) => row.projectId === projectId);
  }

  private async idbGetAll(): Promise<any[]> {
    await this.ensureIndexedDBReady();
    if (!this.indexedDB) {
      return Array.from(this.memoryStore.values());
    }
    const startedAt = nowMs();
    try {
      const store = this.getIDBStore('readonly');
      const result = await this.idbRequest(store.getAll());
      this.pushMetric('indexeddb:getAll', nowMs() - startedAt);
      if (Array.isArray(result) && result.length > 0) {
        return result;
      }
    } catch (error) {
      console.warn('[DatabaseService] IndexedDB getAll 失败，使用内存副本:', error);
    }
    return Array.from(this.memoryStore.values());
  }

  private async idbDelete(id: string): Promise<void> {
    this.memoryStore.delete(id);
    await this.ensureIndexedDBReady();
    if (!this.indexedDB) {
      return;
    }
    const startedAt = nowMs();
    try {
      const store = this.getIDBStore('readwrite');
      await this.idbRequest(store.delete(id));
      this.pushMetric('indexeddb:delete', nowMs() - startedAt);
    } catch (error) {
      console.warn('[DatabaseService] IndexedDB delete 失败，已清理内存副本:', error);
    }
  }

  private async ensureSQLiteMetaTable(): Promise<void> {
    await this.sqliteRun(
      `CREATE TABLE IF NOT EXISTS ${SQLITE_META_TABLE} (
        key TEXT PRIMARY KEY NOT NULL,
        value TEXT NOT NULL
      )`,
      [],
      'sqlite:createMetaTable'
    );
  }

  private async runSQLiteMigrations(): Promise<void> {
    const currentVersion = await this.readSQLiteSchemaVersion();
    if (currentVersion < 1) {
      await this.sqliteRun(
        `CREATE TABLE IF NOT EXISTS ${SQLITE_TABLE} (
          id TEXT PRIMARY KEY NOT NULL,
          project_id TEXT NOT NULL,
          latitude REAL NOT NULL,
          longitude REAL NOT NULL,
          accuracy REAL NOT NULL,
          altitude REAL,
          speed REAL,
          heading REAL,
          attributes TEXT,
          collected_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL,
          version INTEGER NOT NULL,
          source TEXT NOT NULL,
          synced INTEGER NOT NULL DEFAULT 0
        )`,
        [],
        'sqlite:migration:v1:createTable'
      );
      await this.sqliteRun(
        `CREATE INDEX IF NOT EXISTS idx_${SQLITE_TABLE}_project_updated
          ON ${SQLITE_TABLE} (project_id, updated_at DESC)`,
        [],
        'sqlite:migration:v1:createProjectUpdatedIndex'
      );
    }

    if (currentVersion < 2) {
      await this.sqliteRun(
        `CREATE INDEX IF NOT EXISTS idx_${SQLITE_TABLE}_synced_updated
          ON ${SQLITE_TABLE} (synced, updated_at DESC)`,
        [],
        'sqlite:migration:v2:createSyncedUpdatedIndex'
      );
    }

    if (currentVersion < SQLITE_SCHEMA_VERSION) {
      await this.writeSQLiteSchemaVersion(SQLITE_SCHEMA_VERSION);
    }
  }

  private async readSQLiteSchemaVersion(): Promise<number> {
    const rows = await this.sqliteQuery<{ value: string }>(
      `SELECT value FROM ${SQLITE_META_TABLE} WHERE key = ? LIMIT 1`,
      ['schema_version'],
      'sqlite:readSchemaVersion'
    );
    const version = Number(rows[0]?.value || 0);
    return Number.isFinite(version) ? Math.max(0, Math.floor(version)) : 0;
  }

  private async writeSQLiteSchemaVersion(version: number): Promise<void> {
    await this.sqliteRun(
      `INSERT OR REPLACE INTO ${SQLITE_META_TABLE} (key, value) VALUES (?, ?)`,
      ['schema_version', String(version)],
      'sqlite:writeSchemaVersion'
    );
  }

  private readLegacySamples(): Promise<any[]> {
    return new Promise((resolve) => {
      const req = indexedDB.open(LEGACY_DB_NAME);
      req.onsuccess = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(LEGACY_STORE)) {
          db.close();
          resolve([]);
          return;
        }
        const tx = db.transaction(LEGACY_STORE, 'readonly');
        const store = tx.objectStore(LEGACY_STORE);
        const allReq = store.getAll();
        allReq.onsuccess = () => {
          const rows = Array.isArray(allReq.result) ? allReq.result : [];
          db.close();
          resolve(rows);
        };
        allReq.onerror = () => {
          db.close();
          resolve([]);
        };
      };
      req.onerror = () => resolve([]);
    });
  }
}

export const databaseService = DatabaseService.getInstance();
