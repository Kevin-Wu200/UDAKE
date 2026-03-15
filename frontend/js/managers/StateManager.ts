/**
 * 状态管理器
 * 提供全局状态管理和订阅机制
 */

export type StateListener<T = any> = (newValue: T, oldValue: T) => void;

export interface StateConfig {
    persist?: boolean;
    persistKey?: string;
    validate?: (value: any) => boolean;
}

export interface StateDefinition {
    key: string;
    defaultValue: any;
    config?: StateConfig;
}

export class StateManager {
    private static instance: StateManager | null = null;
    private state: Map<string, any> = new Map();
    private listeners: Map<string, Set<StateListener>> = new Map();
    private stateConfigs: Map<string, StateConfig> = new Map();
    private history: Map<string, any[]> = new Map();
    private maxHistorySize: number = 50;

    private constructor() {
        this.loadPersistedState();
    }

    /**
     * 获取单例实例
     */
    public static getInstance(): StateManager {
        if (!StateManager.instance) {
            StateManager.instance = new StateManager();
        }
        return StateManager.instance;
    }

    /**
     * 初始化状态定义
     */
    public initializeState(definitions: StateDefinition[]): void {
        definitions.forEach(def => {
            const { key, defaultValue, config } = def;

            // 如果状态不存在，设置默认值
            if (!this.state.has(key)) {
                this.state.set(key, defaultValue);
            }

            // 保存配置
            if (config) {
                this.stateConfigs.set(key, config);
            }

            // 初始化监听器集合
            if (!this.listeners.has(key)) {
                this.listeners.set(key, new Set());
            }

            // 初始化历史记录
            if (!this.history.has(key)) {
                this.history.set(key, []);
            }
        });
    }

    /**
     * 设置状态值
     */
    public setState<T>(key: string, value: T): void {
        const oldValue = this.state.get(key);

        // 验证状态值
        const config = this.stateConfigs.get(key);
        if (config && config.validate && !config.validate(value)) {
            console.warn(`[StateManager] 状态 ${key} 验证失败`);
            return;
        }

        // 设置新值
        this.state.set(key, value);

        // 记录历史
        this.recordHistory(key, value);

        // 通知监听器
        this.notifyListeners(key, value, oldValue);

        // 持久化状态
        if (config && config.persist) {
            this.persistState(key, value);
        }
    }

    /**
     * 获取状态值
     */
    public getState<T>(key: string): T {
        return this.state.get(key) as T;
    }

    /**
     * 获取所有状态
     */
    public getAllState(): Record<string, any> {
        return Object.fromEntries(this.state.entries());
    }

    /**
     * 检查状态是否存在
     */
    public hasState(key: string): boolean {
        return this.state.has(key);
    }

    /**
     * 删除状态
     */
    public removeState(key: string): void {
        const value = this.state.get(key);
        this.state.delete(key);

        // 清除监听器
        this.listeners.delete(key);

        // 清除配置
        this.stateConfigs.delete(key);

        // 清除历史
        this.history.delete(key);

        // 从本地存储中删除
        localStorage.removeItem(`state_${key}`);

        // 通知监听器
        this.notifyListeners(key, null, value);
    }

    /**
     * 订阅状态变化
     */
    public subscribe<T>(key: string, listener: StateListener<T>): () => void {
        if (!this.listeners.has(key)) {
            this.listeners.set(key, new Set());
        }

        this.listeners.get(key)!.add(listener as StateListener);

        // 返回取消订阅函数
        return () => this.unsubscribe(key, listener as StateListener);
    }

    /**
     * 取消订阅
     */
    public unsubscribe(key: string, listener: StateListener): void {
        const listeners = this.listeners.get(key);
        if (listeners) {
            listeners.delete(listener);
        }
    }

    /**
     * 批量更新状态
     */
    public batchUpdate(updates: Record<string, any>): void {
        Object.entries(updates).forEach(([key, value]) => {
            this.setState(key, value);
        });
    }

    /**
     * 重置状态到默认值
     */
    public resetState(key: string): void {
        const config = this.stateConfigs.get(key);
        if (config && config.validate) {
            console.warn(`[StateManager] 无法重置状态 ${key}，没有默认值`);
            return;
        }

        // 从配置中获取默认值或使用 null
        const defaultValue = null;
        this.setState(key, defaultValue);
    }

    /**
     * 重置所有状态
     */
    public resetAllState(): void {
        this.state.forEach((value, key) => {
            this.resetState(key);
        });
    }

    /**
     * 获取状态历史
     */
    public getHistory(key: string): any[] {
        return this.history.get(key) || [];
    }

    /**
     * 撤销状态变化
     */
    public undo(key: string): boolean {
        const history = this.history.get(key);
        if (!history || history.length < 2) {
            return false;
        }

        // 移除当前值
        history.pop();

        // 获取上一个值
        const previousValue = history[history.length - 1];

        // 恢复状态（不记录历史）
        this.state.set(key, previousValue);

        // 通知监听器
        this.notifyListeners(key, previousValue, this.state.get(key));

        return true;
    }

    /**
     * 清空历史记录
     */
    public clearHistory(key: string): void {
        const history = this.history.get(key);
        if (history) {
            history.length = 0;
            history.push(this.state.get(key));
        }
    }

    /**
     * 通知监听器
     */
    private notifyListeners(key: string, newValue: any, oldValue: any): void {
        const listeners = this.listeners.get(key);
        if (listeners) {
            listeners.forEach(listener => {
                try {
                    listener(newValue, oldValue);
                } catch (error) {
                    console.error(`[StateManager] 监听器执行失败 (${key}):`, error);
                }
            });
        }
    }

    /**
     * 记录历史
     */
    private recordHistory(key: string, value: any): void {
        if (!this.history.has(key)) {
            this.history.set(key, []);
        }

        const history = this.history.get(key)!;

        // 如果值发生变化，添加到历史记录
        if (history.length === 0 || history[history.length - 1] !== value) {
            history.push(value);

            // 限制历史记录大小
            if (history.length > this.maxHistorySize) {
                history.shift();
            }
        }
    }

    /**
     * 持久化状态
     */
    private persistState(key: string, value: any): void {
        try {
            const persistKey = `state_${key}`;
            localStorage.setItem(persistKey, JSON.stringify(value));
        } catch (error) {
            console.error(`[StateManager] 持久化状态失败 (${key}):`, error);
        }
    }

    /**
     * 加载持久化状态
     */
    private loadPersistedState(): void {
        // 遍历所有本地存储项
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith('state_')) {
                const stateKey = key.replace('state_', '');
                try {
                    const value = JSON.parse(localStorage.getItem(key) || 'null');
                    this.state.set(stateKey, value);

                    // 初始化历史记录
                    if (!this.history.has(stateKey)) {
                        this.history.set(stateKey, []);
                    }
                    this.history.get(stateKey)!.push(value);
                } catch (error) {
                    console.error(`[StateManager] 加载持久化状态失败 (${stateKey}):`, error);
                }
            }
        }
    }

    /**
     * 导出状态
     */
    public exportState(): string {
        const exportData = {
            state: Object.fromEntries(this.state.entries()),
            timestamp: Date.now()
        };
        return JSON.stringify(exportData);
    }

    /**
     * 导入状态
     */
    public importState(json: string): boolean {
        try {
            const data = JSON.parse(json);
            if (data.state) {
                Object.entries(data.state).forEach(([key, value]) => {
                    this.setState(key, value);
                });
                return true;
            }
            return false;
        } catch (error) {
            console.error('[StateManager] 导入状态失败:', error);
            return false;
        }
    }

    /**
     * 清空所有状态
     */
    public clearAllState(): void {
        this.state.clear();
        this.listeners.clear();
        this.stateConfigs.clear();
        this.history.clear();

        // 清空本地存储中的状态
        for (let i = localStorage.length - 1; i >= 0; i--) {
            const key = localStorage.key(i);
            if (key && key.startsWith('state_')) {
                localStorage.removeItem(key);
            }
        }
    }

    /**
     * 获取状态统计信息
     */
    public getStats(): {
        total: number;
        withListeners: number;
        withHistory: number;
        persisted: number;
    } {
        let withListeners = 0;
        let withHistory = 0;
        let persisted = 0;

        this.state.forEach((value, key) => {
            if (this.listeners.has(key) && this.listeners.get(key)!.size > 0) {
                withListeners++;
            }
            if (this.history.has(key) && this.history.get(key)!.length > 1) {
                withHistory++;
            }
            if (localStorage.getItem(`state_${key}`)) {
                persisted++;
            }
        });

        return {
            total: this.state.size,
            withListeners,
            withHistory,
            persisted
        };
    }

    /**
     * 销毁状态管理器
     */
    public destroy(): void {
        this.clearAllState();
        StateManager.instance = null;
    }
}

/**
 * 创建状态管理器实例
 */
export function createStateManager(): StateManager {
    return StateManager.getInstance();
}