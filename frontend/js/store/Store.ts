import type { AppState, StateListener } from '../../types/core';

// ========== Store 专用接口 ==========

/** Store 构造选项 */
export interface StoreOptions {
    persistKey?: string | null;
    enableLog?: boolean;
}

/** 变更日志条目 */
export interface ChangeLogEntry {
    key: string;
    oldValue: unknown;
    newValue: unknown;
    timestamp: string;
}

/** 批量更新映射 */
type BatchUpdates<T> = Partial<Record<keyof T, T[keyof T]>> & Record<string, unknown>;

/** 内部变更记录 */
interface BatchChange {
    key: string;
    oldValue: unknown;
    newValue: unknown;
}

// ========== Store 类 ==========

export class Store<S extends Record<string, any> = Record<string, any>> {
    private _state: S;
    private _listeners: Map<string, Set<StateListener>>;
    private _globalListeners: Set<StateListener>;
    private _persistKey: string | null;
    private _enableLog: boolean;
    private _changeLog: ChangeLogEntry[];
    private _maxLogSize: number;

    constructor(initialState: S = {} as S, options: StoreOptions = {}) {
        this._state = { ...initialState };
        this._listeners = new Map();
        this._globalListeners = new Set();
        this._persistKey = options.persistKey ?? null;
        this._enableLog = options.enableLog !== false;
        this._changeLog = [];
        this._maxLogSize = 100;
        if (this._persistKey) {
            this._restore();
        }
    }

    get<T = unknown>(key?: string): T {
        if (!key) return { ...this._state } as unknown as T;
        return key.split('.').reduce<any>((obj, k) => obj?.[k], this._state) as T;
    }

    getState(): S {
        return { ...this._state };
    }

    set<T = unknown>(key: string, value: T): void {
        const oldValue = this.get(key);
        if (oldValue === value) return;

        const keys = key.split('.');
        let target: Record<string, any> = this._state;
        for (let i = 0; i < keys.length - 1; i++) {
            if (target[keys[i]] === undefined || target[keys[i]] === null) target[keys[i]] = {};
            target = target[keys[i]] as Record<string, any>;
        }
        target[keys[keys.length - 1]] = value;

        if (this._enableLog) {
            this._logChange(key, oldValue, value);
        }
        this._notify(key, value, oldValue);
        if (this._persistKey) {
            this._persist();
        }
    }

    batch(updates: BatchUpdates<S>): void {
        const changes: BatchChange[] = [];
        for (const [key, value] of Object.entries(updates)) {
            const oldValue = this.get(key);
            if (oldValue !== value) {
                const keys = key.split('.');
                let target: Record<string, any> = this._state;
                for (let i = 0; i < keys.length - 1; i++) {
                    if (target[keys[i]] === undefined) target[keys[i]] = {};
                    target = target[keys[i]] as Record<string, any>;
                }
                target[keys[keys.length - 1]] = value;
                changes.push({ key, oldValue, newValue: value });
            }
        }
        changes.forEach(({ key, newValue, oldValue }) => {
            if (this._enableLog) this._logChange(key, oldValue, newValue);
            this._notify(key, newValue, oldValue);
        });

        if (this._persistKey && changes.length > 0) {
            this._persist();
        }
    }

    subscribe(key: string, callback: StateListener): () => void {
        if (!this._listeners.has(key)) {
            this._listeners.set(key, new Set());
        }
        this._listeners.get(key)!.add(callback);
        return () => {
            this._listeners.get(key)?.delete(callback);
        };
    }

    subscribeAll(callback: StateListener): () => void {
        this._globalListeners.add(callback);
        return () => {
            this._globalListeners.delete(callback);
        };
    }

    private _notify(key: string, newValue: unknown, oldValue: unknown): void {
        this._listeners.get(key)?.forEach(cb => {
            try { cb(newValue, oldValue, key); } catch (e) { console.error('[Store] 监听器错误:', e); }
        });

        const parts = key.split('.');
        for (let i = parts.length - 1; i > 0; i--) {
            const parentKey = parts.slice(0, i).join('.');
            this._listeners.get(parentKey)?.forEach(cb => {
                try { cb(this.get(parentKey), undefined, key); } catch (e) { console.error('[Store] 监听器错误:', e); }
            });
        }

        this._globalListeners.forEach(cb => {
            try { cb(newValue, oldValue, key); } catch (e) { console.error('[Store] 全局监听器错误:', e); }
        });
    }

    private _logChange(key: string, oldValue: unknown, newValue: unknown): void {
        this._changeLog.push({
            key, oldValue, newValue,
            timestamp: new Date().toISOString()
        });
        if (this._changeLog.length > this._maxLogSize) {
            this._changeLog.shift();
        }
        console.log(`[Store] ${key}:`, oldValue, ' → ', newValue);
    }

    getChangeLog(): ChangeLogEntry[] {
        return [...this._changeLog];
    }

    private _persist(): void {
        try {
            localStorage.setItem(this._persistKey!, JSON.stringify(this._state));
        } catch (e) {
            console.warn('[Store] 持久化失败:', e);
        }
    }

    private _restore(): void {
        try {
            const saved = localStorage.getItem(this._persistKey!);
            if (saved) {
                const parsed = JSON.parse(saved) as Partial<S>;
                this._state = { ...this._state, ...parsed };
                console.log('[Store] 已从 localStorage 恢复状态');
            }
        } catch (e) {
            console.warn('[Store] 恢复状态失败:', e);
        }
    }

    reset(initialState: S = {} as S): void {
        this._state = { ...initialState };
        if (this._persistKey) {
            localStorage.removeItem(this._persistKey);
        }
        this._changeLog = [];
    }

    destroy(): void {
        this._listeners.clear();
        this._globalListeners.clear();
        this._changeLog = [];
    }
}

// ========== 全局单例 ==========

export const appStore = new Store<AppState>(
    {
        project: null,
        taskId: null,
        taskStatus: null,
        dataId: null,
        mapEngine: 'arcgis',
        darkMode:
            typeof window !== 'undefined' && window.matchMedia
                ? window.matchMedia('(prefers-color-scheme: dark)').matches
                : false,
        sidebarOpen: true,
        layout: {
            panels: {
                'parameter': { id: 'parameter', visible: true, position: 'left', width: 300 },
                'sampling': { id: 'sampling', visible: true, position: 'right', width: 350 },
                'legend': { id: 'legend', visible: true, position: 'bottom', height: 200 },
                'tools': { id: 'tools', visible: true, position: 'top', height: 60 }
            },
            activeLayout: 'default',
            savedLayouts: {}
        },
        units: {
            coordinateSystem: 'wgs84',
            lengthUnit: 'm',
            areaUnit: 'm2'
        },
        defaultParams: {
            activeConfig: null,
            configs: {},
            presets: {
                'environment': {
                    name: '环境监测预设',
                    description: '适用于环境监测的默认参数配置',
                    presetType: 'environment',
                    krigingParams: {
                        points: [],
                        method: 'ordinary',
                        variogram_model: 'spherical',
                        grid_resolution: 100,
                        nlags: 12,
                        nugget: 0,
                        sill: 1,
                        range: 1000,
                        enable_cross_validation: true
                    },
                    createdAt: new Date().toISOString(),
                    updatedAt: new Date().toISOString()
                },
                'agriculture': {
                    name: '农业分析预设',
                    description: '适用于农业分析的默认参数配置',
                    presetType: 'agriculture',
                    krigingParams: {
                        points: [],
                        method: 'ordinary',
                        variogram_model: 'exponential',
                        grid_resolution: 50,
                        nlags: 15,
                        nugget: 0.1,
                        sill: 1,
                        range: 500,
                        enable_cross_validation: true
                    },
                    createdAt: new Date().toISOString(),
                    updatedAt: new Date().toISOString()
                },
                'geology': {
                    name: '地质勘探预设',
                    description: '适用于地质勘探的默认参数配置',
                    presetType: 'geology',
                    krigingParams: {
                        points: [],
                        method: 'universal',
                        variogram_model: 'gaussian',
                        grid_resolution: 200,
                        nlags: 20,
                        nugget: 0,
                        sill: 1,
                        range: 2000,
                        enable_cross_validation: true
                    },
                    createdAt: new Date().toISOString(),
                    updatedAt: new Date().toISOString()
                },
                'custom': {
                    name: '自定义预设',
                    description: '用户自定义的参数配置',
                    presetType: 'custom',
                    krigingParams: {
                        points: [],
                        method: 'ordinary',
                        variogram_model: 'spherical',
                        grid_resolution: 100,
                        nlags: 12,
                        nugget: 0,
                        sill: 1,
                        range: 1000,
                        enable_cross_validation: true
                    },
                    createdAt: new Date().toISOString(),
                    updatedAt: new Date().toISOString()
                }
            }
        }
    },
    {
        persistKey: 'udake_app_state',
        enableLog: true
    }
);
