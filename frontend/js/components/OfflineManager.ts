/**
 * 离线管理器
 * 实现离线数据存储、离线功能、离线状态检测和数据同步
 */

interface OfflineData {
    key: string;
    value: any;
    timestamp: number;
    compressed?: boolean;
}

interface SyncOperation {
    id: string;
    type: 'upload' | 'download' | 'update';
    key: string;
    value: any;
    status: 'pending' | 'syncing' | 'completed' | 'failed';
    timestamp: number;
    retryCount?: number;
}

interface OfflineManagerOptions {
    indexedDBName?: string;
    indexedDBVersion?: number;
    maxStorageSize?: number;
    enableCompression?: boolean;
    autoSync?: boolean;
    syncInterval?: number;
}

class OfflineManager {
    private db: IDBDatabase | null = null;
    private isOnline: boolean = true;
    private syncQueue: SyncOperation[] = [];
    private syncInProgress: boolean = false;
    private syncTimer: number | null = null;
    private eventListeners: Map<string, Set<Function>> = new Map();

    private options: Required<OfflineManagerOptions>;

    constructor(options: OfflineManagerOptions = {}) {
        this.options = {
            indexedDBName: options.indexedDBName || 'UDAKEOffline',
            indexedDBVersion: options.indexedDBVersion || 1,
            maxStorageSize: options.maxStorageSize || 50 * 1024 * 1024, // 50MB
            enableCompression: options.enableCompression ?? false,
            autoSync: options.autoSync ?? true,
            syncInterval: options.syncInterval || 60000, // 1分钟
        };

        this.init();
    }

    /**
     * 初始化
     */
    private async init(): Promise<void> {
        await this.initIndexedDB();
        this.initNetworkDetection();
        this.loadSyncQueue();

        if (this.options.autoSync) {
            this.startAutoSync();
        }
    }

    /**
     * 初始化 IndexedDB
     */
    private async initIndexedDB(): Promise<void> {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.options.indexedDBName, this.options.indexedDBVersion);

            request.onerror = () => {
                console.error('IndexedDB 打开失败:', request.error);
                reject(request.error);
            };

            request.onsuccess = () => {
                this.db = request.result;
                console.log('IndexedDB 初始化成功');
                resolve();
            };

            request.onupgradeneeded = (event) => {
                const db = (event.target as IDBOpenDBRequest).result;

                // 创建数据存储
                if (!db.objectStoreNames.contains('data')) {
                    const dataStore = db.createObjectStore('data', { keyPath: 'key' });
                    dataStore.createIndex('timestamp', 'timestamp', { unique: false });
                }

                // 创建同步队列
                if (!db.objectStoreNames.contains('syncQueue')) {
                    const syncStore = db.createObjectStore('syncQueue', { keyPath: 'id' });
                    syncStore.createIndex('status', 'status', { unique: false });
                    syncStore.createIndex('timestamp', 'timestamp', { unique: false });
                }

                // 创建历史记录
                if (!db.objectStoreNames.contains('history')) {
                    const historyStore = db.createObjectStore('history', { keyPath: 'id' });
                    historyStore.createIndex('timestamp', 'timestamp', { unique: false });
                }
            };
        });
    }

    /**
     * 初始化网络检测
     */
    private initNetworkDetection(): void {
        this.isOnline = navigator.onLine;

        window.addEventListener('online', () => {
            this.handleOnline();
        });

        window.addEventListener('offline', () => {
            this.handleOffline();
        });
    }

    /**
     * 处理在线事件
     */
    private handleOnline(): void {
        if (!this.isOnline) {
            this.isOnline = true;
            console.log('网络已连接');
            this.emit('online');

            if (this.options.autoSync) {
                this.syncAll();
            }
        }
    }

    /**
     * 处理离线事件
     */
    private handleOffline(): void {
        if (this.isOnline) {
            this.isOnline = false;
            console.log('网络已断开');
            this.emit('offline');
        }
    }

    /**
     * 加载同步队列
     */
    private async loadSyncQueue(): Promise<void> {
        if (!this.db) return;

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction(['syncQueue'], 'readonly');
            const store = transaction.objectStore('syncQueue');
            const request = store.getAll();

            request.onsuccess = () => {
                this.syncQueue = request.result || [];
                resolve();
            };

            request.onerror = () => {
                reject(request.error);
            };
        });
    }

    /**
     * 开始自动同步
     */
    private startAutoSync(): void {
        if (this.syncTimer) {
            clearInterval(this.syncTimer);
        }

        this.syncTimer = window.setInterval(() => {
            if (this.isOnline && !this.syncInProgress) {
                this.syncAll();
            }
        }, this.options.syncInterval);
    }

    /**
     * 停止自动同步
     */
    private stopAutoSync(): void {
        if (this.syncTimer) {
            clearInterval(this.syncTimer);
            this.syncTimer = null;
        }
    }

    /**
     * 保存数据到 IndexedDB
     */
    public async saveData(key: string, value: any): Promise<void> {
        if (!this.db) {
            throw new Error('IndexedDB 未初始化');
        }

        const data: OfflineData = {
            key,
            value,
            timestamp: Date.now(),
            compressed: this.options.enableCompression,
        };

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction(['data'], 'readwrite');
            const store = transaction.objectStore('data');
            const request = store.put(data);

            request.onsuccess = () => {
                console.log(`数据已保存: ${key}`);
                resolve();
            };

            request.onerror = () => {
                console.error(`数据保存失败: ${key}`, request.error);
                reject(request.error);
            };
        });
    }

    /**
     * 从 IndexedDB 读取数据
     */
    public async getData<T = any>(key: string): Promise<T | null> {
        if (!this.db) {
            throw new Error('IndexedDB 未初始化');
        }

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction(['data'], 'readonly');
            const store = transaction.objectStore('data');
            const request = store.get(key);

            request.onsuccess = () => {
                const result = request.result;
                if (result) {
                    resolve(result.value as T);
                } else {
                    resolve(null);
                }
            };

            request.onerror = () => {
                reject(request.error);
            };
        });
    }

    /**
     * 删除数据
     */
    public async deleteData(key: string): Promise<void> {
        if (!this.db) {
            throw new Error('IndexedDB 未初始化');
        }

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction(['data'], 'readwrite');
            const store = transaction.objectStore('data');
            const request = store.delete(key);

            request.onsuccess = () => {
                console.log(`数据已删除: ${key}`);
                resolve();
            };

            request.onerror = () => {
                reject(request.error);
            };
        });
    }

    /**
     * 获取所有数据
     */
    public async getAllData(): Promise<Map<string, any>> {
        if (!this.db) {
            throw new Error('IndexedDB 未初始化');
        }

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction(['data'], 'readonly');
            const store = transaction.objectStore('data');
            const request = store.getAll();

            request.onsuccess = () => {
                const dataMap = new Map<string, any>();
                (request.result || []).forEach((item: OfflineData) => {
                    dataMap.set(item.key, item.value);
                });
                resolve(dataMap);
            };

            request.onerror = () => {
                reject(request.error);
            };
        });
    }

    /**
     * 保存到 localStorage
     */
    public saveToLocalStorage(key: string, value: any): void {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (e) {
            console.error('localStorage 保存失败:', e);
        }
    }

    /**
     * 从 localStorage 读取
     */
    public getFromLocalStorage<T = any>(key: string): T | null {
        try {
            const value = localStorage.getItem(key);
            return value ? JSON.parse(value) : null;
        } catch (e) {
            console.error('localStorage 读取失败:', e);
            return null;
        }
    }

    /**
     * 添加同步操作
     */
    public async addSyncOperation(operation: Omit<SyncOperation, 'id' | 'timestamp' | 'status'>): Promise<void> {
        if (!this.db) {
            throw new Error('IndexedDB 未初始化');
        }

        const syncOp: SyncOperation = {
            id: `sync_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            timestamp: Date.now(),
            status: 'pending',
            ...operation,
        };

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction(['syncQueue'], 'readwrite');
            const store = transaction.objectStore('syncQueue');
            const request = store.add(syncOp);

            request.onsuccess = () => {
                this.syncQueue.push(syncOp);
                resolve();
            };

            request.onerror = () => {
                reject(request.error);
            };
        });
    }

    /**
     * 同步所有数据
     */
    public async syncAll(): Promise<void> {
        if (!this.isOnline || this.syncInProgress || this.syncQueue.length === 0) {
            return;
        }

        this.syncInProgress = true;

        try {
            const pendingOps = this.syncQueue.filter(op => op.status === 'pending');

            for (const op of pendingOps) {
                try {
                    await this.syncOperation(op);
                } catch (e) {
                    console.error('同步操作失败:', op.id, e);
                    // 增加重试计数
                    op.retryCount = (op.retryCount || 0) + 1;

                    // 如果重试次数超过 3 次，标记为失败
                    if (op.retryCount >= 3) {
                        op.status = 'failed';
                        await this.updateSyncOperation(op);
                    }
                }
            }

            // 清理已完成的操作
            await this.cleanupSyncOperations();

            this.emit('sync', { success: true });
        } catch (e) {
            console.error('同步失败:', e);
            this.emit('sync', { success: false, error: e });
        } finally {
            this.syncInProgress = false;
        }
    }

    /**
     * 同步单个操作
     */
    private async syncOperation(operation: SyncOperation): Promise<void> {
        // 更新状态为同步中
        operation.status = 'syncing';
        await this.updateSyncOperation(operation);

        // 这里应该调用实际的同步 API
        // 示例：fetch('/api/sync', { method: 'POST', body: JSON.stringify(operation) })

        // 模拟同步成功
        await new Promise(resolve => setTimeout(resolve, 100));

        operation.status = 'completed';
        await this.updateSyncOperation(operation);
    }

    /**
     * 更新同步操作状态
     */
    private async updateSyncOperation(operation: SyncOperation): Promise<void> {
        if (!this.db) {
            throw new Error('IndexedDB 未初始化');
        }

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction(['syncQueue'], 'readwrite');
            const store = transaction.objectStore('syncQueue');
            const request = store.put(operation);

            request.onsuccess = () => {
                const index = this.syncQueue.findIndex(op => op.id === operation.id);
                if (index !== -1) {
                    this.syncQueue[index] = operation;
                }
                resolve();
            };

            request.onerror = () => {
                reject(request.error);
            };
        });
    }

    /**
     * 清理已完成的同步操作
     */
    private async cleanupSyncOperations(): Promise<void> {
        if (!this.db) {
            throw new Error('IndexedDB 未初始化');
        }

        const completedOps = this.syncQueue.filter(op => op.status === 'completed');

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction(['syncQueue'], 'readwrite');
            const store = transaction.objectStore('syncQueue');

            const promises = completedOps.map(op => {
                return new Promise<void>((res, rej) => {
                    const request = store.delete(op.id);
                    request.onsuccess = () => res();
                    request.onerror = () => rej(request.error);
                });
            });

            Promise.all(promises).then(() => {
                this.syncQueue = this.syncQueue.filter(op => op.status !== 'completed');
                resolve();
            }).catch(reject);
        });
    }

    /**
     * 获取存储使用情况
     */
    public async getStorageUsage(): Promise<{ used: number; total: number }> {
        if (navigator.storage && navigator.storage.estimate) {
            const estimate = await navigator.storage.estimate();
            return {
                used: estimate.usage || 0,
                total: estimate.quota || this.options.maxStorageSize,
            };
        }

        return {
            used: 0,
            total: this.options.maxStorageSize,
        };
    }

    /**
     * 清除所有数据
     */
    public async clearAll(): Promise<void> {
        if (!this.db) {
            throw new Error('IndexedDB 未初始化');
        }

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction(['data', 'syncQueue', 'history'], 'readwrite');
            const dataStore = transaction.objectStore('data');
            const syncStore = transaction.objectStore('syncQueue');
            const historyStore = transaction.objectStore('history');

            const dataRequest = dataStore.clear();
            const syncRequest = syncStore.clear();
            const historyRequest = historyStore.clear();

            transaction.oncomplete = () => {
                this.syncQueue = [];
                resolve();
            };

            transaction.onerror = () => {
                reject(transaction.error);
            };
        });
    }

    /**
     * 检查是否在线
     */
    public isOnlineStatus(): boolean {
        return this.isOnline;
    }

    /**
     * 获取同步状态
     */
    public getSyncStatus(): {
        pending: number;
        syncing: number;
        completed: number;
        failed: number;
    } {
        return {
            pending: this.syncQueue.filter(op => op.status === 'pending').length,
            syncing: this.syncQueue.filter(op => op.status === 'syncing').length,
            completed: this.syncQueue.filter(op => op.status === 'completed').length,
            failed: this.syncQueue.filter(op => op.status === 'failed').length,
        };
    }

    /**
     * 事件监听
     */
    public on(event: 'online' | 'offline' | 'sync', callback: Function): void {
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, new Set());
        }
        this.eventListeners.get(event)!.add(callback);
    }

    /**
     * 移除事件监听
     */
    public off(event: 'online' | 'offline' | 'sync', callback: Function): void {
        const listeners = this.eventListeners.get(event);
        if (listeners) {
            listeners.delete(callback);
        }
    }

    /**
     * 触发事件
     */
    private emit(event: 'online' | 'offline' | 'sync', data?: any): void {
        const listeners = this.eventListeners.get(event);
        if (listeners) {
            listeners.forEach(callback => callback(data));
        }
    }

    /**
     * 销毁管理器
     */
    public destroy(): void {
        this.stopAutoSync();

        if (this.db) {
            this.db.close();
            this.db = null;
        }

        this.eventListeners.clear();
        this.syncQueue = [];
    }
}

// 导出
export default OfflineManager;