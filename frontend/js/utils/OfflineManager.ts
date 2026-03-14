/**
 * 离线功能管理器
 * IndexedDB 数据存储 + 离线模式检测 + 数据同步 + 冲突解决
 */

// ========== 类型定义 ==========

interface PendingAction {
    id: string;
    type: 'upload' | 'kriging' | 'export';
    payload: any;
    timestamp: number;
    retries: number;
}

interface SyncResult {
    success: number;
    failed: number;
    conflicts: number;
}

type ConflictStrategy = 'client-wins' | 'server-wins' | 'latest-wins';

// ========== 常量 ==========

const DB_NAME = 'udake_offline';
const DB_VERSION = 1;
const STORES = {
    projects: 'projects',
    points: 'points',
    results: 'results',
    pendingActions: 'pendingActions',
} as const;

// ========== OfflineManager ==========

export class OfflineManager {
    private static db: IDBDatabase | null = null;
    private static _online: boolean = navigator.onLine;
    private static _listeners: Set<(online: boolean) => void> = new Set();
    private static _syncInProgress = false;
    private static _indicatorEl: HTMLElement | null = null;

    /** 初始化：打开 IndexedDB + 监听网络状态 */
    static async init(): Promise<void> {
        await this._openDB();
        this._bindNetworkEvents();
        this._createIndicator();
        this._updateIndicator();

        // 恢复在线时自动同步
        this.onStatusChange((online) => {
            this._updateIndicator();
            if (online) this.sync();
        });
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

    // ========== UI 指示器 ==========

    private static _createIndicator(): void {
        if (this._indicatorEl) return;
        const el = document.createElement('div');
        el.id = 'offline-indicator';
        el.setAttribute('role', 'status');
        el.setAttribute('aria-live', 'polite');
        el.style.cssText = `
            position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%);
            padding: 8px 20px; border-radius: 20px; font-size: 13px; font-weight: 500;
            z-index: 10000; pointer-events: none;
            transition: opacity 0.3s, transform 0.3s;
            backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        `;
        document.body.appendChild(el);
        this._indicatorEl = el;
    }

    private static _updateIndicator(): void {
        const el = this._indicatorEl;
        if (!el) return;
        if (this._online) {
            el.textContent = '已恢复在线';
            el.style.background = 'rgba(52,199,89,0.9)';
            el.style.color = '#fff';
            el.style.opacity = '1';
            setTimeout(() => { el.style.opacity = '0'; }, 2000);
        } else {
            el.textContent = '当前处于离线模式';
            el.style.background = 'rgba(255,149,0,0.9)';
            el.style.color = '#fff';
            el.style.opacity = '1';
        }
    }

    // ========== IndexedDB ==========

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
                    if (err?.message?.includes('conflict')) {
                        result.conflicts++;
                        await this._resolveConflict(action, strategy);
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

    private static async _executeAction(action: PendingAction, _strategy: ConflictStrategy): Promise<void> {
        // 实际的 API 调用由外部注入，这里提供基础框架
        const handlers = (this as any)._actionHandlers as Map<string, (payload: any) => Promise<void>> | undefined;
        if (handlers?.has(action.type)) {
            await handlers.get(action.type)!(action.payload);
        } else {
            console.warn(`[Offline] 未注册的操作类型: ${action.type}`);
        }
    }

    private static async _resolveConflict(action: PendingAction, strategy: ConflictStrategy): Promise<void> {
        switch (strategy) {
            case 'client-wins':
                // 强制用客户端数据覆盖
                await this._executeAction(action, strategy);
                await this._removeAction(action.id);
                break;
            case 'server-wins':
                // 丢弃客户端操作
                await this._removeAction(action.id);
                break;
            case 'latest-wins':
            default:
                // 比较时间戳，较新的胜出
                await this._removeAction(action.id);
                break;
        }
    }

    /** 注册操作处理器 */
    static registerHandler(type: string, handler: (payload: any) => Promise<void>): void {
        if (!(this as any)._actionHandlers) {
            (this as any)._actionHandlers = new Map();
        }
        (this as any)._actionHandlers.set(type, handler);
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
