/**
 * 离线功能管理器
 * IndexedDB 数据存储 + 离线模式检测 + 数据同步 + 冲突解决
 */

import { I18n } from './I18n';
import { databaseService, type DatabaseGPSSample } from '../services/DatabaseService.js';

// ========== 类型定义 ==========

interface PendingAction {
    id: string;
    type: 'upload' | 'kriging' | 'export' | 'gps_sync';
    payload: any;
    timestamp: number;
    retries: number;
}

interface SyncResult {
    success: number;
    failed: number;
    conflicts: number;
}

type ConflictStrategy = 'client-wins' | 'server-wins' | 'latest-wins' | 'manual';
type FieldConflictSelection = 'client' | 'server';

interface ConflictDiffItem {
    path: string;
    clientValue: unknown;
    serverValue: unknown;
    suggestion: FieldConflictSelection;
}

interface ConflictContext {
    action: PendingAction;
    clientData: unknown;
    serverData: unknown;
    serverUpdatedAt?: number;
    diff: ConflictDiffItem[];
    suggestedSelection: Record<string, FieldConflictSelection>;
}

interface ConflictResolutionDecision {
    strategy: 'manual' | 'suggested' | 'deferred';
    selection: Record<string, FieldConflictSelection>;
}

interface ConflictHistoryEntry {
    actionId: string;
    actionType: PendingAction['type'];
    strategy: ConflictStrategy | 'suggested';
    resolvedAt: number;
    selectedFields: Record<string, FieldConflictSelection>;
    mergedPreview: unknown;
}

// ========== 常量 ==========

const DB_NAME = 'udake_offline';
const DB_VERSION = 3;
const STORES = {
    projects: 'projects',
    points: 'points',
    results: 'results',
    pendingActions: 'pendingActions',
    gpsSamples: 'gpsSamples',
    settings: 'settings',
} as const;

// ========== OfflineManager ==========

export class OfflineManager {
    private static db: IDBDatabase | null = null;
    private static _storageBackend: 'indexeddb' | 'sqlite' = 'indexeddb';
    private static _sqliteBridge: any = null;
    private static _online: boolean = navigator?.onLine ?? true;
    private static _listeners: Set<(online: boolean) => void> = new Set();
    private static _syncInProgress = false;
    private static _actionHandlers: Map<string, (payload: any) => Promise<void>> = new Map();
    private static _conflictHistory: ConflictHistoryEntry[] = [];
    private static _maxConflictHistorySize = 100;
    private static _maxGpsSamplesPerProject = 5000;
    private static _maxGpsSampleAgeMs = 30 * 24 * 60 * 60 * 1000;
    private static _compressionThresholdBytes = 1024;

    /** 初始化：打开 IndexedDB + 监听网络状态 */
    static async init(): Promise<void> {
        await this._openDB();
        this._bindNetworkEvents();

        // 恢复在线时自动同步
        this.onStatusChange((online) => {
            if (online) this.sync();
        });
    }

    static async evaluateStorageBackends(): Promise<{
        recommended: 'indexeddb' | 'sqlite';
        indexeddb: { available: boolean; score: number };
        sqlite: { available: boolean; score: number };
    }> {
        const indexeddbAvailable = typeof indexedDB !== 'undefined';
        const sqliteBridge = await this._detectSQLiteBridge();
        const sqliteAvailable = Boolean(sqliteBridge);

        const indexeddbScore = indexeddbAvailable ? 82 : 0;
        const sqliteScore = sqliteAvailable ? 90 : 0;
        const recommended = sqliteScore > indexeddbScore ? 'sqlite' : 'indexeddb';
        return {
            recommended,
            indexeddb: { available: indexeddbAvailable, score: indexeddbScore },
            sqlite: { available: sqliteAvailable, score: sqliteScore },
        };
    }

    static async configureStorageBackend(preferred: 'indexeddb' | 'sqlite' = 'indexeddb'): Promise<'indexeddb' | 'sqlite'> {
        if (preferred === 'sqlite') {
            const bridge = await this._detectSQLiteBridge();
            if (bridge) {
                const backend = await databaseService.initialize('sqlite');
                if (backend === 'sqlite') {
                    this._storageBackend = 'sqlite';
                    this._sqliteBridge = bridge;
                    await databaseService.migrateLegacyIndexedDBToSQLite();
                    return 'sqlite';
                }
            }
        }
        await databaseService.initialize('indexeddb');
        this._storageBackend = 'indexeddb';
        return 'indexeddb';
    }

    // ========== 网络状态 ==========

    static get isOnline(): boolean {
        return this._online;
    }

    static onStatusChange(cb: (online: boolean) => void): () => void {
        this._listeners.add(cb);
        return () => { this._listeners.delete(cb); };
    }

    private static _bindNetworkEvents(): void {
        window.addEventListener('online', () => this._setOnline(true));
        window.addEventListener('offline', () => this._setOnline(false));
    }

    private static _setOnline(val: boolean): void {
        if (this._online === val) return;
        this._online = val;
        console.log(`[Offline] 网络状态: ${val ? '在线' : '离线'}`);
        this._listeners.forEach(cb => { try { cb(val); } catch (e) { console.error(e); } });
    }

    // ========== IndexedDB ==========

    private static async _detectSQLiteBridge(): Promise<any | null> {
        if (this._sqliteBridge) return this._sqliteBridge;
        const win = window as any;
        const capacitorSQLite = win?.Capacitor?.Plugins?.SQLite;
        if (capacitorSQLite) {
            this._sqliteBridge = capacitorSQLite;
            return capacitorSQLite;
        }
        const legacySQLite = win?.sqlitePlugin;
        if (legacySQLite) {
            this._sqliteBridge = legacySQLite;
            return legacySQLite;
        }
        return null;
    }

    private static _openDB(): Promise<IDBDatabase> {
        return new Promise((resolve, reject) => {
            if (this.db) { resolve(this.db); return; }
            const req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = () => {
                const db = req.result;
                if (!db.objectStoreNames.contains(STORES.projects)) {
                    db.createObjectStore(STORES.projects, { keyPath: 'id' });
                }
                if (!db.objectStoreNames.contains(STORES.points)) {
                    const store = db.createObjectStore(STORES.points, { keyPath: 'id', autoIncrement: true });
                    store.createIndex('projectId', 'projectId', { unique: false });
                }
                if (!db.objectStoreNames.contains(STORES.results)) {
                    db.createObjectStore(STORES.results, { keyPath: 'taskId' });
                }
                if (!db.objectStoreNames.contains(STORES.pendingActions)) {
                    db.createObjectStore(STORES.pendingActions, { keyPath: 'id' });
                }
                if (!db.objectStoreNames.contains(STORES.gpsSamples)) {
                    const gpsStore = db.createObjectStore(STORES.gpsSamples, { keyPath: 'id' });
                    gpsStore.createIndex('projectId', 'projectId', { unique: false });
                    gpsStore.createIndex('updatedAt', 'updatedAt', { unique: false });
                    gpsStore.createIndex('projectUpdated', ['projectId', 'updatedAt'], { unique: false });
                } else {
                    const txn = req.transaction;
                    if (txn) {
                        const gpsStore = txn.objectStore(STORES.gpsSamples);
                        if (!gpsStore.indexNames.contains('projectUpdated')) {
                            gpsStore.createIndex('projectUpdated', ['projectId', 'updatedAt'], { unique: false });
                        }
                    }
                }
                if (!db.objectStoreNames.contains(STORES.settings)) {
                    db.createObjectStore(STORES.settings, { keyPath: 'id' });
                }
            };
            req.onsuccess = () => { this.db = req.result; resolve(this.db); };
            req.onerror = () => reject(req.error);
        });
    }

    private static _tx(storeName: string, mode: IDBTransactionMode = 'readonly'): IDBObjectStore {
        if (!this.db) throw new Error('IndexedDB 未初始化');
        return this.db.transaction(storeName, mode).objectStore(storeName);
    }

    private static _req<T>(req: IDBRequest<T>): Promise<T> {
        return new Promise((resolve, reject) => {
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    private static _estimateSize(value: unknown): number {
        try {
            return JSON.stringify(value).length;
        } catch {
            return 0;
        }
    }

    private static async _compressText(text: string): Promise<string | null> {
        try {
            const CompressionCtor = (globalThis as any).CompressionStream;
            if (!CompressionCtor) return null;
            const stream = new CompressionCtor('gzip');
            const writer = stream.writable.getWriter();
            await writer.write(new TextEncoder().encode(text));
            await writer.close();
            const buffer = await new Response(stream.readable).arrayBuffer();
            const bytes = new Uint8Array(buffer);
            let binary = '';
            bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
            return btoa(binary);
        } catch {
            return null;
        }
    }

    private static async _decompressText(base64: string): Promise<string | null> {
        try {
            const DecompressionCtor = (globalThis as any).DecompressionStream;
            if (!DecompressionCtor) return null;
            const binary = atob(base64);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) {
                bytes[i] = binary.charCodeAt(i);
            }
            const stream = new DecompressionCtor('gzip');
            const writer = stream.writable.getWriter();
            await writer.write(bytes);
            await writer.close();
            const buffer = await new Response(stream.readable).arrayBuffer();
            return new TextDecoder().decode(buffer);
        } catch {
            return null;
        }
    }

    private static async _prepareStoredPayload(data: Record<string, unknown>): Promise<Record<string, unknown>> {
        const estimated = this._estimateSize(data);
        if (estimated < this._compressionThresholdBytes) return data;
        const attributes = data.attributes as Record<string, unknown> | undefined;
        if (!attributes) return data;
        const serialized = JSON.stringify(attributes);
        const compressed = await this._compressText(serialized);
        if (!compressed) return data;
        return {
            ...data,
            attributes: {},
            _compressedAttributes: compressed,
            _compression: 'gzip-base64'
        };
    }

    private static async _restoreStoredPayload(data: any): Promise<any> {
        if (!data || data._compression !== 'gzip-base64' || !data._compressedAttributes) return data;
        const restored = await this._decompressText(String(data._compressedAttributes));
        if (!restored) return data;
        try {
            return {
                ...data,
                attributes: JSON.parse(restored),
            };
        } catch {
            return data;
        }
    }

    // ========== 数据操作 ==========

    /** 保存项目到本地 */
    static async saveProject(project: any): Promise<void> {
        const store = this._tx(STORES.projects, 'readwrite');
        await this._req(store.put({ ...project, _savedAt: Date.now() }));
    }

    /** 获取本地项目 */
    static async getProject(id: string): Promise<any | null> {
        const store = this._tx(STORES.projects, 'readonly');
        return this._req(store.get(id));
    }

    /** 获取所有本地项目 */
    static async getAllProjects(): Promise<any[]> {
        const store = this._tx(STORES.projects, 'readonly');
        return this._req(store.getAll());
    }

    /** 保存采样点 */
    static async savePoints(projectId: string, points: any[]): Promise<void> {
        const store = this._tx(STORES.points, 'readwrite');
        for (const pt of points) {
            await this._req(store.put({ ...pt, projectId, _savedAt: Date.now() }));
        }
    }

    /** 获取项目的采样点 */
    static async getPoints(projectId: string): Promise<any[]> {
        const store = this._tx(STORES.points, 'readonly');
        const idx = store.index('projectId');
        return this._req(idx.getAll(projectId));
    }

    /** 缓存插值结果 */
    static async cacheResult(taskId: string, result: any): Promise<void> {
        const store = this._tx(STORES.results, 'readwrite');
        await this._req(store.put({ taskId, ...result, _cachedAt: Date.now() }));
    }

    /** 获取缓存的结果 */
    static async getCachedResult(taskId: string): Promise<any | null> {
        const store = this._tx(STORES.results, 'readonly');
        return this._req(store.get(taskId));
    }

    /** 保存单个 GPS 采样点 */
    static async saveGPSSample(sample: any): Promise<void> {
        if (this._storageBackend === 'sqlite') {
            const handled = await this._saveGPSSampleWithSQLite(sample);
            if (handled) return;
        }
        const store = this._tx(STORES.gpsSamples, 'readwrite');
        const now = Date.now();
        const projectId = sample.projectId || sample.project_id || 'default_mobile_project';
        const normalized = await this._prepareStoredPayload({
            ...sample,
            projectId,
            updatedAt: sample.updatedAt || sample.updated_at || now,
            collectedAt: sample.collectedAt || sample.collected_at || now,
            _savedAt: now
        });
        await this._req(
            store.put(normalized)
        );
        await this._cleanupProjectGPSSamples(projectId);
    }

    /** 批量保存 GPS 采样点 */
    static async saveGPSSamples(samples: any[]): Promise<void> {
        if (this._storageBackend === 'sqlite') {
            const backend = await databaseService.initialize('sqlite');
            if (backend === 'sqlite') {
                const now = Date.now();
                const normalized = samples.map((sample) => ({
                    ...sample,
                    projectId: sample.projectId || sample.project_id || 'default_mobile_project',
                    updatedAt: sample.updatedAt || sample.updated_at || now,
                    collectedAt: sample.collectedAt || sample.collected_at || now
                })) as DatabaseGPSSample[];
                await databaseService.saveGPSSamples(normalized);
                const touchedProjects = new Set(normalized.map((item) => item.projectId));
                for (const projectId of touchedProjects) {
                    await this._cleanupProjectGPSSamples(projectId);
                }
                return;
            }
        }
        const store = this._tx(STORES.gpsSamples, 'readwrite');
        const now = Date.now();
        const touchedProjects = new Set<string>();
        for (const sample of samples) {
            const projectId = sample.projectId || sample.project_id || 'default_mobile_project';
            touchedProjects.add(projectId);
            const normalized = await this._prepareStoredPayload({
                ...sample,
                projectId,
                updatedAt: sample.updatedAt || sample.updated_at || now,
                collectedAt: sample.collectedAt || sample.collected_at || now,
                _savedAt: now
            });
            await this._req(
                store.put(normalized)
            );
        }
        for (const projectId of touchedProjects) {
            await this._cleanupProjectGPSSamples(projectId);
        }
    }

    /** 获取单个 GPS 采样点 */
    static async getGPSSample(id: string): Promise<any | null> {
        if (this._storageBackend === 'sqlite') {
            const row = await databaseService.getGPSSample(id);
            return row ? { ...row } : null;
        }
        const store = this._tx(STORES.gpsSamples, 'readonly');
        const row = await this._req(store.get(id));
        return this._restoreStoredPayload(row);
    }

    /** 获取指定项目 GPS 采样点 */
    static async getGPSSamples(projectId: string, limit: number = 500): Promise<any[]> {
        if (this._storageBackend === 'sqlite') {
            return databaseService.getGPSSamples(projectId, limit);
        }
        const store = this._tx(STORES.gpsSamples, 'readonly');
        const idx = store.index('projectId');
        const rows = await this._req(idx.getAll(projectId));
        const restored = await Promise.all(rows.map((item: any) => this._restoreStoredPayload(item)));
        return restored
            .sort((a: any, b: any) => (b.updatedAt || b.collectedAt || 0) - (a.updatedAt || a.collectedAt || 0))
            .slice(0, limit);
    }

    /** 获取所有 GPS 采样点 */
    static async getAllGPSSamples(limit: number = 5000): Promise<any[]> {
        if (this._storageBackend === 'sqlite') {
            return databaseService.getAllGPSSamples(limit);
        }
        const store = this._tx(STORES.gpsSamples, 'readonly');
        const rows = await this._req(store.getAll());
        const restored = await Promise.all(rows.map((item: any) => this._restoreStoredPayload(item)));
        return restored
            .sort((a: any, b: any) => (b.updatedAt || b.collectedAt || 0) - (a.updatedAt || a.collectedAt || 0))
            .slice(0, limit);
    }

    /** 删除 GPS 采样点 */
    static async deleteGPSSample(id: string): Promise<void> {
        if (this._storageBackend === 'sqlite') {
            await databaseService.deleteGPSSample(id);
            return;
        }
        const store = this._tx(STORES.gpsSamples, 'readwrite');
        await this._req(store.delete(id));
    }

    /** 获取 GPS 本地统计 */
    static async getGPSProjectStats(): Promise<{ total: number; projectCounts: Record<string, number> }> {
        if (this._storageBackend === 'sqlite') {
            return databaseService.getGPSProjectStats();
        }
        const rows = await this.getAllGPSSamples();
        const projectCounts: Record<string, number> = {};
        for (const row of rows) {
            const key = row.projectId || 'default_mobile_project';
            projectCounts[key] = (projectCounts[key] || 0) + 1;
        }
        return {
            total: rows.length,
            projectCounts
        };
    }

    private static async _cleanupProjectGPSSamples(projectId: string): Promise<void> {
        if (this._storageBackend === 'sqlite') {
            const rows = await databaseService.getGPSSamples(projectId, 200000);
            const now = Date.now();
            const staleRows = rows.filter((row) => now - Number(row.updatedAt || row.collectedAt || now) > this._maxGpsSampleAgeMs);
            for (const row of staleRows) {
                await databaseService.deleteGPSSample(row.id);
            }
            const activeRows = rows
                .filter((row) => !staleRows.find((stale) => stale.id === row.id))
                .sort((a, b) => Number(b.updatedAt || b.collectedAt || 0) - Number(a.updatedAt || a.collectedAt || 0));
            if (activeRows.length > this._maxGpsSamplesPerProject) {
                const overflow = activeRows.slice(this._maxGpsSamplesPerProject);
                for (const row of overflow) {
                    await databaseService.deleteGPSSample(row.id);
                }
            }
            return;
        }

        const store = this._tx(STORES.gpsSamples, 'readwrite');
        const idx = store.index('projectId');
        const rows: any[] = await this._req(idx.getAll(projectId));
        const now = Date.now();

        const staleRows = rows.filter((row) => now - Number(row.updatedAt || row.collectedAt || now) > this._maxGpsSampleAgeMs);
        for (const row of staleRows) {
            await this._req(store.delete(row.id));
        }

        const activeRows = rows
            .filter((row) => !staleRows.find(stale => stale.id === row.id))
            .sort((a, b) => Number(b.updatedAt || b.collectedAt || 0) - Number(a.updatedAt || a.collectedAt || 0));

        if (activeRows.length > this._maxGpsSamplesPerProject) {
            const overflow = activeRows.slice(this._maxGpsSamplesPerProject);
            for (const row of overflow) {
                await this._req(store.delete(row.id));
            }
        }
    }

    private static async _saveGPSSampleWithSQLite(_sample: any): Promise<boolean> {
        const backend = await databaseService.initialize('sqlite');
        if (backend !== 'sqlite') {
            this._storageBackend = 'indexeddb';
            return false;
        }

        const now = Date.now();
        const sample = {
            ..._sample,
            projectId: _sample.projectId || _sample.project_id || 'default_mobile_project',
            updatedAt: _sample.updatedAt || _sample.updated_at || now,
            collectedAt: _sample.collectedAt || _sample.collected_at || now
        } as DatabaseGPSSample;
        await databaseService.saveGPSSample(sample);
        this._storageBackend = 'sqlite';
        return true;
    }

    static getStorageBackend(): 'indexeddb' | 'sqlite' {
        return this._storageBackend;
    }

    static getStorageQueryPerformance(): {
        count: number;
        avgMs: number;
        p95Ms: number;
        maxMs: number;
        backend: 'indexeddb' | 'sqlite';
    } {
        return databaseService.getQueryPerformanceSummary();
    }

    static async syncSQLiteToServer(
        syncer: (samples: DatabaseGPSSample[]) => Promise<{ success: number; failed?: number }>
    ): Promise<{ success: number; failed: number; total: number }> {
        return databaseService.syncToServer(syncer);
    }

    // ========== 离线队列 ==========

    /** 将操作加入离线队列 */
    static async enqueue(action: Omit<PendingAction, 'id' | 'timestamp' | 'retries'>): Promise<void> {
        const store = this._tx(STORES.pendingActions, 'readwrite');
        const entry: PendingAction = {
            ...action,
            id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            timestamp: Date.now(),
            retries: 0,
        };
        await this._req(store.put(entry));
        console.log(`[Offline] 操作已入队: ${action.type}`);
    }

    /** 获取所有待同步操作 */
    static async getPendingActions(): Promise<PendingAction[]> {
        const store = this._tx(STORES.pendingActions, 'readonly');
        return this._req(store.getAll());
    }

    /** 移除已完成的操作 */
    private static async _removeAction(id: string): Promise<void> {
        const store = this._tx(STORES.pendingActions, 'readwrite');
        await this._req(store.delete(id));
    }

    // ========== 同步 ==========

    /** 同步离线队列到服务器 */
    static async sync(strategy: ConflictStrategy = 'latest-wins'): Promise<SyncResult> {
        if (this._syncInProgress || !this._online) {
            return { success: 0, failed: 0, conflicts: 0 };
        }
        this._syncInProgress = true;
        const result: SyncResult = { success: 0, failed: 0, conflicts: 0 };

        try {
            const actions = await this.getPendingActions();
            if (actions.length === 0) return result;

            console.log(`[Offline] 开始同步 ${actions.length} 个操作...`);

            for (const action of actions) {
                try {
                    await this._executeAction(action, strategy);
                    await this._removeAction(action.id);
                    result.success++;
                } catch (err: any) {
                    if (this._isConflictError(err)) {
                        result.conflicts++;
                        const resolved = await this._resolveConflict(action, strategy, err);
                        if (resolved) {
                            result.success++;
                        } else {
                            result.failed++;
                        }
                    } else {
                        action.retries++;
                        if (action.retries >= 3) {
                            await this._removeAction(action.id);
                            console.warn(`[Offline] 操作重试超限，已丢弃: ${action.id}`);
                        }
                        result.failed++;
                    }
                }
            }
            console.log(`[Offline] 同步完成:`, result);
        } finally {
            this._syncInProgress = false;
        }
        return result;
    }

    private static async _executeAction(action: PendingAction, _strategy: ConflictStrategy, payloadOverride?: any): Promise<void> {
        // 实际的 API 调用由外部注入，这里提供基础框架
        if (this._actionHandlers.has(action.type)) {
            const payload = payloadOverride ?? action.payload;
            await this._actionHandlers.get(action.type)!(payload);
        } else {
            console.warn(`[Offline] 未注册的操作类型: ${action.type}`);
        }
    }

    private static _isConflictError(err: any): boolean {
        if (!err) return false;
        if (typeof err?.code === 'string' && err.code.toLowerCase().includes('conflict')) return true;
        if (err?.response?.status === 409) return true;
        return typeof err?.message === 'string' && err.message.toLowerCase().includes('conflict');
    }

    private static _extractConflictContext(action: PendingAction, err: any): ConflictContext {
        const fallbackServerData = err?.response?.data?.serverData ?? err?.serverData ?? {};
        const fallbackClientData = err?.response?.data?.clientData ?? action.payload;
        const conflictData = err?.conflictData || {};
        const clientData = conflictData.clientData ?? fallbackClientData;
        const serverData = conflictData.serverData ?? fallbackServerData;
        const serverUpdatedAt = conflictData.serverUpdatedAt ?? err?.serverUpdatedAt;
        const diff = this.getConflictDiff(clientData, serverData);
        const suggestedSelection = this.getSmartMergeSuggestion(clientData, serverData, action.timestamp, serverUpdatedAt);

        return {
            action,
            clientData,
            serverData,
            serverUpdatedAt,
            diff,
            suggestedSelection
        };
    }

    private static _isPlainObject(value: unknown): value is Record<string, unknown> {
        return Object.prototype.toString.call(value) === '[object Object]';
    }

    private static _deepEqual(a: unknown, b: unknown): boolean {
        if (a === b) return true;
        if (typeof a !== typeof b) return false;
        if (a === null || b === null) return a === b;

        if (Array.isArray(a) && Array.isArray(b)) {
            if (a.length !== b.length) return false;
            for (let i = 0; i < a.length; i++) {
                if (!this._deepEqual(a[i], b[i])) return false;
            }
            return true;
        }

        if (this._isPlainObject(a) && this._isPlainObject(b)) {
            const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
            for (const key of keys) {
                if (!this._deepEqual(a[key], b[key])) return false;
            }
            return true;
        }

        return false;
    }

    private static _safeStringify(value: unknown): string {
        if (typeof value === 'string') return value;
        try {
            const serialized = JSON.stringify(value);
            return serialized === undefined ? 'null' : serialized;
        } catch {
            return String(value);
        }
    }

    private static _cloneData<T>(value: T): T {
        const serialized = this._safeStringify(value);
        try {
            return JSON.parse(serialized) as T;
        } catch {
            return value;
        }
    }

    private static _setByPath(target: Record<string, unknown>, path: string, value: unknown): void {
        const segments = path.split('.');
        let current: Record<string, unknown> = target;

        for (let i = 0; i < segments.length - 1; i++) {
            const key = segments[i];
            if (!this._isPlainObject(current[key])) {
                current[key] = {};
            }
            current = current[key] as Record<string, unknown>;
        }
        current[segments[segments.length - 1]] = value;
    }

    private static _renderValue(value: unknown): string {
        if (typeof value === 'string') return value;
        if (value === undefined) return 'undefined';
        if (value === null) return 'null';
        return this._safeStringify(value);
    }

    static getConflictDiff(clientData: unknown, serverData: unknown): ConflictDiffItem[] {
        const diffs: ConflictDiffItem[] = [];

        const collect = (clientValue: unknown, serverValue: unknown, path: string): void => {
            if (this._deepEqual(clientValue, serverValue)) return;

            const clientObj = this._isPlainObject(clientValue);
            const serverObj = this._isPlainObject(serverValue);
            if (clientObj && serverObj) {
                const keys = new Set([
                    ...Object.keys(clientValue as Record<string, unknown>),
                    ...Object.keys(serverValue as Record<string, unknown>)
                ]);
                for (const key of keys) {
                    const nextPath = path ? `${path}.${key}` : key;
                    collect((clientValue as Record<string, unknown>)[key], (serverValue as Record<string, unknown>)[key], nextPath);
                }
                return;
            }

            const suggestion = this._getSmartFieldSuggestion(path, clientValue, serverValue, Date.now(), Date.now());
            diffs.push({
                path,
                clientValue,
                serverValue,
                suggestion
            });
        };

        collect(clientData, serverData, '');
        return diffs.filter(item => item.path);
    }

    private static _getSmartFieldSuggestion(
        path: string,
        clientValue: unknown,
        serverValue: unknown,
        clientUpdatedAt?: number,
        serverUpdatedAt?: number
    ): FieldConflictSelection {
        if (clientValue === undefined || clientValue === null || clientValue === '') return 'server';
        if (serverValue === undefined || serverValue === null || serverValue === '') return 'client';

        const timeFieldPattern = /(updatedAt|timestamp|time)$/i;
        if (timeFieldPattern.test(path)) {
            const clientNum = Number(clientValue);
            const serverNum = Number(serverValue);
            if (!Number.isNaN(clientNum) && !Number.isNaN(serverNum)) {
                return clientNum >= serverNum ? 'client' : 'server';
            }
        }

        if (typeof clientValue === 'string' && typeof serverValue === 'string') {
            if (clientValue.length !== serverValue.length) {
                return clientValue.length >= serverValue.length ? 'client' : 'server';
            }
        }

        const clientTs = typeof clientUpdatedAt === 'number' ? clientUpdatedAt : 0;
        const serverTs = typeof serverUpdatedAt === 'number' ? serverUpdatedAt : 0;
        return clientTs >= serverTs ? 'client' : 'server';
    }

    static getSmartMergeSuggestion(
        clientData: unknown,
        serverData: unknown,
        clientUpdatedAt?: number,
        serverUpdatedAt?: number
    ): Record<string, FieldConflictSelection> {
        const diff = this.getConflictDiff(clientData, serverData);
        return diff.reduce((acc, item) => {
            acc[item.path] = this._getSmartFieldSuggestion(
                item.path,
                item.clientValue,
                item.serverValue,
                clientUpdatedAt,
                serverUpdatedAt
            );
            return acc;
        }, {} as Record<string, FieldConflictSelection>);
    }

    static getMergePreview(
        clientData: unknown,
        serverData: unknown,
        selection: Record<string, FieldConflictSelection>
    ): unknown {
        const base = this._isPlainObject(serverData) ? this._cloneData(serverData) : {};
        const preview = this._isPlainObject(base) ? base : {};
        const diff = this.getConflictDiff(clientData, serverData);

        for (const item of diff) {
            const keep = selection[item.path] || item.suggestion;
            const value = keep === 'client' ? item.clientValue : item.serverValue;
            this._setByPath(preview as Record<string, unknown>, item.path, value);
        }

        return preview;
    }

    private static async _openConflictResolver(context: ConflictContext): Promise<ConflictResolutionDecision> {
        if (typeof document === 'undefined' || !document.body) {
            return { strategy: 'suggested', selection: context.suggestedSelection };
        }

        return new Promise((resolve) => {
            const backdrop = document.createElement('div');
            const modal = document.createElement('div');
            const header = document.createElement('div');
            const title = document.createElement('h3');
            const subtitle = document.createElement('p');
            const tableWrap = document.createElement('div');
            const previewWrap = document.createElement('div');
            const previewTitle = document.createElement('div');
            const previewCode = document.createElement('pre');
            const actionWrap = document.createElement('div');
            const btnUseSuggestion = document.createElement('button');
            const btnServer = document.createElement('button');
            const btnConfirm = document.createElement('button');
            const selectors: Map<string, HTMLSelectElement> = new Map();

            backdrop.style.position = 'fixed';
            backdrop.style.inset = '0';
            backdrop.style.zIndex = '20000';
            backdrop.style.background = 'rgba(0, 0, 0, 0.45)';
            backdrop.style.display = 'flex';
            backdrop.style.alignItems = 'center';
            backdrop.style.justifyContent = 'center';
            backdrop.style.padding = '24px';

            modal.style.background = '#ffffff';
            modal.style.width = 'min(960px, 100%)';
            modal.style.maxHeight = '90vh';
            modal.style.borderRadius = '14px';
            modal.style.boxShadow = '0 20px 50px rgba(0, 0, 0, 0.25)';
            modal.style.display = 'flex';
            modal.style.flexDirection = 'column';
            modal.style.overflow = 'hidden';

            header.style.padding = '20px 24px 16px';
            header.style.borderBottom = '1px solid #e5e7eb';
            title.textContent = I18n.t('offline.conflictDetected');
            title.style.margin = '0 0 6px';
            subtitle.textContent = I18n.t('offline.conflictActionType', { actionType: context.action.type });
            subtitle.style.margin = '0';
            subtitle.style.fontSize = '13px';
            subtitle.style.color = '#4b5563';
            header.appendChild(title);
            header.appendChild(subtitle);

            tableWrap.style.padding = '16px 24px';
            tableWrap.style.overflow = 'auto';
            tableWrap.style.maxHeight = '42vh';

            const table = document.createElement('table');
            table.style.width = '100%';
            table.style.borderCollapse = 'collapse';
            table.innerHTML = `
                <thead>
                    <tr>
                        <th style="text-align:left;border-bottom:1px solid #e5e7eb;padding:8px 4px">字段</th>
                        <th style="text-align:left;border-bottom:1px solid #e5e7eb;padding:8px 4px">客户端</th>
                        <th style="text-align:left;border-bottom:1px solid #e5e7eb;padding:8px 4px">服务端</th>
                        <th style="text-align:left;border-bottom:1px solid #e5e7eb;padding:8px 4px">保留</th>
                    </tr>
                </thead>
            `;
            const tbody = document.createElement('tbody');

            const renderPreview = (): void => {
                const selection: Record<string, FieldConflictSelection> = {};
                selectors.forEach((sel, path) => {
                    selection[path] = sel.value as FieldConflictSelection;
                });
                const preview = this.getMergePreview(context.clientData, context.serverData, selection);
                previewCode.textContent = this._safeStringify(preview);
            };

            for (const item of context.diff) {
                const row = document.createElement('tr');
                const fieldCell = document.createElement('td');
                const clientCell = document.createElement('td');
                const serverCell = document.createElement('td');
                const selectCell = document.createElement('td');
                const select = document.createElement('select');
                const defaultChoice = context.suggestedSelection[item.path] || item.suggestion;

                row.style.borderBottom = '1px solid #f3f4f6';
                fieldCell.style.padding = '8px 4px';
                clientCell.style.padding = '8px 4px';
                serverCell.style.padding = '8px 4px';
                selectCell.style.padding = '8px 4px';
                fieldCell.textContent = item.path;
                clientCell.textContent = this._renderValue(item.clientValue);
                serverCell.textContent = this._renderValue(item.serverValue);

                const clientOption = document.createElement('option');
                clientOption.value = 'client';
                clientOption.textContent = I18n.t('offline.clientSide');
                const serverOption = document.createElement('option');
                serverOption.value = 'server';
                serverOption.textContent = I18n.t('offline.serverSide');
                select.appendChild(clientOption);
                select.appendChild(serverOption);
                select.value = defaultChoice;
                select.addEventListener('change', renderPreview);
                select.style.minWidth = '112px';

                selectors.set(item.path, select);
                selectCell.appendChild(select);
                row.appendChild(fieldCell);
                row.appendChild(clientCell);
                row.appendChild(serverCell);
                row.appendChild(selectCell);
                tbody.appendChild(row);
            }
            table.appendChild(tbody);
            tableWrap.appendChild(table);

            previewWrap.style.padding = '0 24px 20px';
            previewTitle.textContent = I18n.t('offline.mergePreview');
            previewTitle.style.fontSize = '13px';
            previewTitle.style.fontWeight = '600';
            previewTitle.style.marginBottom = '8px';
            previewCode.style.margin = '0';
            previewCode.style.padding = '12px';
            previewCode.style.background = '#f9fafb';
            previewCode.style.border = '1px solid #e5e7eb';
            previewCode.style.borderRadius = '8px';
            previewCode.style.maxHeight = '180px';
            previewCode.style.overflow = 'auto';
            previewCode.style.fontSize = '12px';
            previewCode.style.lineHeight = '1.45';
            previewWrap.appendChild(previewTitle);
            previewWrap.appendChild(previewCode);

            actionWrap.style.padding = '16px 24px 24px';
            actionWrap.style.borderTop = '1px solid #e5e7eb';
            actionWrap.style.display = 'flex';
            actionWrap.style.gap = '10px';
            actionWrap.style.justifyContent = 'flex-end';

            btnUseSuggestion.textContent = I18n.t('offline.applySmartSuggestion');
            btnUseSuggestion.style.padding = '8px 14px';
            btnUseSuggestion.style.border = '1px solid #d1d5db';
            btnUseSuggestion.style.background = '#f9fafb';
            btnUseSuggestion.style.borderRadius = '8px';
            btnUseSuggestion.style.cursor = 'pointer';

            btnServer.textContent = I18n.t('offline.keepServerSide');
            btnServer.style.padding = '8px 14px';
            btnServer.style.border = '1px solid #d1d5db';
            btnServer.style.background = '#ffffff';
            btnServer.style.borderRadius = '8px';
            btnServer.style.cursor = 'pointer';

            btnConfirm.textContent = I18n.t('offline.confirmMerge');
            btnConfirm.style.padding = '8px 14px';
            btnConfirm.style.border = 'none';
            btnConfirm.style.background = '#2563eb';
            btnConfirm.style.color = '#ffffff';
            btnConfirm.style.borderRadius = '8px';
            btnConfirm.style.cursor = 'pointer';

            const cleanup = (): void => {
                backdrop.remove();
            };

            btnUseSuggestion.addEventListener('click', () => {
                selectors.forEach((select, path) => {
                    select.value = context.suggestedSelection[path] || 'server';
                });
                renderPreview();
            });

            btnServer.addEventListener('click', () => {
                const selection = context.diff.reduce((acc, item) => {
                    acc[item.path] = 'server';
                    return acc;
                }, {} as Record<string, FieldConflictSelection>);
                cleanup();
                resolve({ strategy: 'manual', selection });
            });

            btnConfirm.addEventListener('click', () => {
                const selection: Record<string, FieldConflictSelection> = {};
                selectors.forEach((select, path) => {
                    selection[path] = select.value as FieldConflictSelection;
                });
                cleanup();
                resolve({ strategy: 'manual', selection });
            });

            backdrop.addEventListener('click', (event) => {
                if (event.target === backdrop) {
                    cleanup();
                    resolve({ strategy: 'deferred', selection: {} });
                }
            });

            actionWrap.appendChild(btnUseSuggestion);
            actionWrap.appendChild(btnServer);
            actionWrap.appendChild(btnConfirm);

            modal.appendChild(header);
            modal.appendChild(tableWrap);
            modal.appendChild(previewWrap);
            modal.appendChild(actionWrap);
            backdrop.appendChild(modal);
            document.body.appendChild(backdrop);

            renderPreview();
        });
    }

    private static _recordConflictHistory(
        action: PendingAction,
        strategy: ConflictStrategy | 'suggested',
        selectedFields: Record<string, FieldConflictSelection>,
        mergedPreview: unknown
    ): void {
        this._conflictHistory.push({
            actionId: action.id,
            actionType: action.type,
            strategy,
            resolvedAt: Date.now(),
            selectedFields,
            mergedPreview
        });

        if (this._conflictHistory.length > this._maxConflictHistorySize) {
            this._conflictHistory.shift();
        }
    }

    static getConflictHistory(): ConflictHistoryEntry[] {
        return this._conflictHistory.map(item => ({
            ...item,
            selectedFields: { ...item.selectedFields },
            mergedPreview: this._cloneData(item.mergedPreview)
        }));
    }

    static clearConflictHistory(): void {
        this._conflictHistory = [];
    }

    private static async _resolveConflict(action: PendingAction, strategy: ConflictStrategy, err: any): Promise<boolean> {
        const context = this._extractConflictContext(action, err);

        switch (strategy) {
            case 'client-wins':
                await this._executeAction(action, strategy, context.clientData);
                await this._removeAction(action.id);
                this._recordConflictHistory(
                    action,
                    strategy,
                    context.diff.reduce((acc, item) => {
                        acc[item.path] = 'client';
                        return acc;
                    }, {} as Record<string, FieldConflictSelection>),
                    context.clientData
                );
                break;
            case 'server-wins':
                await this._removeAction(action.id);
                this._recordConflictHistory(
                    action,
                    strategy,
                    context.diff.reduce((acc, item) => {
                        acc[item.path] = 'server';
                        return acc;
                    }, {} as Record<string, FieldConflictSelection>),
                    context.serverData
                );
                break;
            case 'latest-wins':
                {
                    const selection = this.getSmartMergeSuggestion(
                        context.clientData,
                        context.serverData,
                        action.timestamp,
                        context.serverUpdatedAt
                    );
                    const mergedPayload = this.getMergePreview(context.clientData, context.serverData, selection);
                    await this._executeAction(action, strategy, mergedPayload);
                    await this._removeAction(action.id);
                    this._recordConflictHistory(action, 'suggested', selection, mergedPayload);
                }
                break;
            case 'manual':
                {
                    const decision = await this._openConflictResolver(context);
                    if (decision.strategy === 'deferred') {
                        return false;
                    }
                    const mergedPayload = this.getMergePreview(context.clientData, context.serverData, decision.selection);
                    const allServer = Object.keys(decision.selection).length > 0 &&
                        Object.values(decision.selection).every(value => value === 'server');
                    if (!allServer) {
                        await this._executeAction(action, strategy, mergedPayload);
                    }
                    await this._removeAction(action.id);
                    this._recordConflictHistory(action, strategy, decision.selection, mergedPayload);
                }
                break;
            default:
                await this._removeAction(action.id);
                break;
        }
        return true;
    }

    /** 注册操作处理器 */
    static registerHandler(type: string, handler: (payload: any) => Promise<void>): void {
        this._actionHandlers.set(type, handler);
    }

    /** 获取待同步操作数量 */
    static async getPendingCount(): Promise<number> {
        const actions = await this.getPendingActions();
        return actions.length;
    }

    /** 清除所有离线数据 */
    static async clearAll(): Promise<void> {
        for (const name of Object.values(STORES)) {
            const store = this._tx(name, 'readwrite');
            await this._req(store.clear());
        }
        console.log('[Offline] 已清除所有离线数据');
    }
}
