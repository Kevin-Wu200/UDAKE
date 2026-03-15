/**
 * 任务持久化存储管理器
 * 使用 IndexedDB 存储任务数据
 */

import { Task, TaskStatus } from '../../types/task-manager';

const DB_NAME = 'UDAKE_TaskStorage';
const DB_VERSION = 1;
const STORE_NAME = 'tasks';
const HISTORY_STORE_NAME = 'task_history';

export class TaskStorage {
    private db: IDBDatabase | null = null;
    private isInitialized: boolean = false;

    /**
     * 初始化数据库
     */
    async initialize(): Promise<void> {
        if (this.isInitialized) return;

        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);

            request.onerror = () => {
                console.error('[TaskStorage] 打开数据库失败:', request.error);
                reject(request.error);
            };

            request.onsuccess = () => {
                this.db = request.result;
                this.isInitialized = true;
                console.log('[TaskStorage] 数据库初始化成功');
                resolve();
            };

            request.onupgradeneeded = (event) => {
                const db = (event.target as IDBOpenDBRequest).result;

                // 创建任务存储
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    const taskStore = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
                    taskStore.createIndex('status', 'status', { unique: false });
                    taskStore.createIndex('priority', 'priority', { unique: false });
                    taskStore.createIndex('createdAt', 'createdAt', { unique: false });
                    taskStore.createIndex('type', 'type', { unique: false });
                }

                // 创建任务历史存储
                if (!db.objectStoreNames.contains(HISTORY_STORE_NAME)) {
                    const historyStore = db.createObjectStore(HISTORY_STORE_NAME, { keyPath: 'id' });
                    historyStore.createIndex('completedAt', 'completedAt', { unique: false });
                    historyStore.createIndex('status', 'status', { unique: false });
                }
            };
        });
    }

    /**
     * 保存任务
     */
    async saveTask(task: Task): Promise<void> {
        if (!this.db) await this.initialize();

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.put(task);

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * 获取任务
     */
    async getTask(taskId: string): Promise<Task | null> {
        if (!this.db) await this.initialize();

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction([STORE_NAME], 'readonly');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.get(taskId);

            request.onsuccess = () => {
                resolve(request.result || null);
            };
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * 获取所有任务
     */
    async getAllTasks(): Promise<Task[]> {
        if (!this.db) await this.initialize();

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction([STORE_NAME], 'readonly');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.getAll();

            request.onsuccess = () => {
                resolve(request.result || []);
            };
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * 按状态获取任务
     */
    async getTasksByStatus(status: TaskStatus): Promise<Task[]> {
        if (!this.db) await this.initialize();

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction([STORE_NAME], 'readonly');
            const store = transaction.objectStore(STORE_NAME);
            const index = store.index('status');
            const request = index.getAll(status);

            request.onsuccess = () => {
                resolve(request.result || []);
            };
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * 删除任务
     */
    async deleteTask(taskId: string): Promise<void> {
        if (!this.db) await this.initialize();

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.delete(taskId);

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * 批量删除任务
     */
    async deleteTasks(taskIds: string[]): Promise<void> {
        if (!this.db) await this.initialize();

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);

            let completed = 0;
            const total = taskIds.length;

            taskIds.forEach(id => {
                const request = store.delete(id);
                request.onsuccess = () => {
                    completed++;
                    if (completed === total) resolve();
                };
                request.onerror = () => reject(request.error);
            });
        });
    }

    /**
     * 移动任务到历史记录
     */
    async moveToHistory(task: Task): Promise<void> {
        if (!this.db) await this.initialize();

        // 添加完成时间
        const historyTask = {
            ...task,
            completedAt: task.completedAt || Date.now()
        };

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction([STORE_NAME, HISTORY_STORE_NAME], 'readwrite');
            const taskStore = transaction.objectStore(STORE_NAME);
            const historyStore = transaction.objectStore(HISTORY_STORE_NAME);

            // 从任务表删除
            const deleteRequest = taskStore.delete(task.id);

            deleteRequest.onsuccess = () => {
                // 添加到历史表
                const addRequest = historyStore.add(historyTask);

                addRequest.onsuccess = () => resolve();
                addRequest.onerror = () => reject(addRequest.error);
            };

            deleteRequest.onerror = () => reject(deleteRequest.error);
        });
    }

    /**
     * 获取任务历史
     */
    async getTaskHistory(limit: number = 50): Promise<Task[]> {
        if (!this.db) await this.initialize();

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction([HISTORY_STORE_NAME], 'readonly');
            const store = transaction.objectStore(HISTORY_STORE_NAME);
            const index = store.index('completedAt');
            const request = index.openCursor(null, 'prev');

            const results: Task[] = [];

            request.onsuccess = (event) => {
                const cursor = (event.target as IDBRequest).result;

                if (cursor && results.length < limit) {
                    results.push(cursor.value);
                    cursor.continue();
                } else {
                    resolve(results);
                }
            };

            request.onerror = () => reject(request.error);
        });
    }

    /**
     * 清理旧的历史记录
     */
    async cleanupOldHistory(olderThanDays: number = 30): Promise<number> {
        if (!this.db) await this.initialize();

        const cutoffDate = Date.now() - (olderThanDays * 24 * 60 * 60 * 1000);

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction([HISTORY_STORE_NAME], 'readwrite');
            const store = transaction.objectStore(HISTORY_STORE_NAME);
            const index = store.index('completedAt');
            const request = index.openCursor(IDBKeyRange.upperBound(cutoffDate));

            let deletedCount = 0;

            request.onsuccess = (event) => {
                const cursor = (event.target as IDBRequest).result;

                if (cursor) {
                    cursor.delete();
                    deletedCount++;
                    cursor.continue();
                } else {
                    resolve(deletedCount);
                }
            };

            request.onerror = () => reject(request.error);
        });
    }

    /**
     * 清空所有任务
     */
    async clearAllTasks(): Promise<void> {
        if (!this.db) await this.initialize();

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.clear();

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * 清空历史记录
     */
    async clearHistory(): Promise<void> {
        if (!this.db) await this.initialize();

        return new Promise((resolve, reject) => {
            const transaction = this.db!.transaction([HISTORY_STORE_NAME], 'readwrite');
            const store = transaction.objectStore(HISTORY_STORE_NAME);
            const request = store.clear();

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * 获取统计信息
     */
    async getStats(): Promise<{ total: number; byStatus: Record<TaskStatus, number> }> {
        if (!this.db) await this.initialize();

        const tasks = await this.getAllTasks();

        const stats = {
            total: tasks.length,
            byStatus: {} as Record<TaskStatus, number>
        };

        // 初始化所有状态的计数
        const statuses: TaskStatus[] = ['pending', 'running', 'paused', 'completed', 'failed', 'cancelled'];
        statuses.forEach(status => {
            stats.byStatus[status] = 0;
        });

        // 统计各状态任务数
        tasks.forEach(task => {
            stats.byStatus[task.status]++;
        });

        return stats;
    }

    /**
     * 关闭数据库
     */
    close(): void {
        if (this.db) {
            this.db.close();
            this.db = null;
            this.isInitialized = false;
        }
    }
}

export default new TaskStorage();