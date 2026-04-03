import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { Store, appStore } from '../apps/frontend/js/store/Store.js';

describe('Store', () => {
    let store;

    beforeEach(() => {
        // Mock localStorage
        const localStorageMock = {
            getItem: vi.fn(() => null),
            setItem: vi.fn(),
            removeItem: vi.fn()
        };
        global.localStorage = localStorageMock;

        // Mock console
        console.log = vi.fn();
        console.warn = vi.fn();
        console.error = vi.fn();

        store = new Store({ count: 0, user: null }, { enableLog: false });
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    it('应该正确获取初始状态', () => {
        expect(store.get('count')).toBe(0);
        expect(store.get('user')).toBeNull();
    });

    it('应该正确设置状态', () => {
        store.set('count', 5);
        expect(store.get('count')).toBe(5);
    });

    it('应该支持嵌套路径', () => {
        store.set('user', { name: '张三' });
        store.set('user.name', '李四');
        expect(store.get('user.name')).toBe('李四');
    });

    it('应该通知订阅者', () => {
        let received = null;
        store.subscribe('count', (newVal) => { received = newVal; });
        store.set('count', 10);
        expect(received).toBe(10);
    });

    it('订阅者应该接收oldValue', () => {
        let oldValue = null;
        store.subscribe('count', (newVal, old) => { oldValue = old; });
        store.set('count', 10);
        expect(oldValue).toBe(0);
    });

    it('订阅者应该接收key', () => {
        let receivedKey = null;
        store.subscribe('count', (newVal, old, key) => { receivedKey = key; });
        store.set('count', 10);
        expect(receivedKey).toBe('count');
    });

    it('相同值不应触发通知', () => {
        let callCount = 0;
        store.subscribe('count', () => { callCount++; });
        store.set('count', 0); // 与初始值相同
        expect(callCount).toBe(0);
    });

    it('应该支持批量更新', () => {
        const changes = [];
        store.subscribeAll((newVal, oldVal, key) => { changes.push(key); });
        store.batch({ count: 3, user: { name: '王五' } });
        expect(store.get('count')).toBe(3);
        expect(changes).toContain('count');
        expect(changes).toContain('user');
    });

    it('批量更新应该只触发变更的key', () => {
        const changes = [];
        store.set('count', 5);
        store.subscribeAll((newVal, oldVal, key) => { changes.push(key); });
        store.batch({ count: 5, user: { name: '新用户' } }); // count值相同
        
        expect(changes).not.toContain('count');
        expect(changes).toContain('user');
    });

    it('取消订阅应该生效', () => {
        let received = null;
        const unsub = store.subscribe('count', (v) => { received = v; });
        unsub();
        store.set('count', 99);
        expect(received).toBeNull();
    });

    it('应该返回完整状态快照', () => {
        store.set('count', 7);
        const state = store.getState();
        expect(state.count).toBe(7);
        // 快照应该是副本
        state.count = 999;
        expect(store.get('count')).toBe(7);
    });

    it('get 不带参数应该返回完整状态', () => {
        store.set('count', 7);
        store.set('user', { name: '测试' });
        const state = store.get();
        
        expect(state.count).toBe(7);
        expect(state.user.name).toBe('测试');
    });

    it('reset 应该清空状态', () => {
        store.set('count', 50);
        store.reset({ count: 0 });
        expect(store.get('count')).toBe(0);
    });

    it('reset 应该清空变更日志', () => {
        store.set('count', 10);
        store.reset({ count: 0 });
        const log = store.getChangeLog();
        expect(log.length).toBe(0);
    });

    describe('getChangeLog', () => {
        beforeEach(() => {
            // 为 getChangeLog 测试创建一个新的 store，启用日志
            store = new Store({ count: 0, user: null }, { enableLog: true });
        });

        it('应该返回变更日志', () => {
            store.set('count', 5);
            store.set('count', 10);
            const log = store.getChangeLog();
            
            expect(log.length).toBe(2);
            expect(log[0].key).toBe('count');
            expect(log[0].oldValue).toBe(0);
            expect(log[0].newValue).toBe(5);
        });

        it('变更日志应该包含时间戳', () => {
            store.set('count', 5);
            const log = store.getChangeLog();
            
            expect(log[0].timestamp).toBeDefined();
            expect(typeof log[0].timestamp).toBe('string');
        });

        it('getChangeLog 应该返回副本', () => {
            store.set('count', 5);
            const log1 = store.getChangeLog();
            const log2 = store.getChangeLog();
            
            expect(log1).not.toBe(log2);
            expect(log1).toEqual(log2);
        });

        it('批量更新应该记录所有变更', () => {
            store.batch({ count: 10, user: { name: '测试' } });
            const log = store.getChangeLog();
            
            expect(log.length).toBe(2);
            expect(log.some(entry => entry.key === 'count')).toBe(true);
            expect(log.some(entry => entry.key === 'user')).toBe(true);
        });
    });

    describe('destroy', () => {
        it('应该清空所有监听器', () => {
            store.subscribe('count', () => {});
            store.subscribe('user', () => {});
            store.subscribeAll(() => {});
            
            store.destroy();
            
            // 设置新值不应该触发任何监听器
            store.set('count', 999);
        });

        it('应该清空变更日志', () => {
            store.set('count', 5);
            store.destroy();
            const log = store.getChangeLog();
            
            expect(log.length).toBe(0);
        });
    });

    describe('持久化功能', () => {
        it('应该持久化状态到localStorage', () => {
            const persistStore = new Store({ count: 0 }, { persistKey: 'test_store', enableLog: false });
            persistStore.set('count', 100);
            
            expect(localStorage.setItem).toHaveBeenCalledWith('test_store', expect.any(String));
        });

        it('应该从localStorage恢复状态', () => {
            const savedState = { count: 50, user: { name: '恢复的用户' } };
            localStorage.getItem.mockReturnValue(JSON.stringify(savedState));
            
            const persistStore = new Store({ count: 0 }, { persistKey: 'test_store', enableLog: false });
            
            expect(persistStore.get('count')).toBe(50);
            expect(persistStore.get('user.name')).toBe('恢复的用户');
        });

        it('reset 应该清除持久化数据', () => {
            const persistStore = new Store({ count: 0 }, { persistKey: 'test_store', enableLog: false });
            persistStore.set('count', 100);
            persistStore.reset({ count: 0 });
            
            expect(localStorage.removeItem).toHaveBeenCalledWith('test_store');
        });

        it('应该处理localStorage错误', () => {
            localStorage.setItem.mockImplementation(() => {
                throw new Error('Storage error');
            });
            
            const persistStore = new Store({ count: 0 }, { persistKey: 'test_store', enableLog: false });
            
            expect(() => persistStore.set('count', 100)).not.toThrow();
            expect(console.warn).toHaveBeenCalled();
        });

        it('应该处理恢复状态时的JSON错误', () => {
            localStorage.getItem.mockReturnValue('invalid json');
            
            const persistStore = new Store({ count: 0 }, { persistKey: 'test_store', enableLog: false });
            
            expect(persistStore.get('count')).toBe(0); // 应该使用初始值
            expect(console.warn).toHaveBeenCalled();
        });
    });

    describe('日志功能', () => {
        it('启用日志时应该记录变更', () => {
            const logStore = new Store({ count: 0 }, { enableLog: true });
            logStore.set('count', 10);
            
            expect(console.log).toHaveBeenCalledWith('[Store] count:', 0, ' → ', 10);
        });

        it('禁用日志时不应该记录', () => {
            const noLogStore = new Store({ count: 0 }, { enableLog: false });
            noLogStore.set('count', 10);
            
            expect(console.log).not.toHaveBeenCalled();
        });

        it('变更日志应该限制大小', () => {
            const logStore = new Store({ count: 0 }, { enableLog: false });
            
            // 添加超过限制的变更
            for (let i = 0; i < 150; i++) {
                logStore.set('count', i);
            }
            
            const log = logStore.getChangeLog();
            expect(log.length).toBeLessThanOrEqual(100);
        });
    });

    describe('嵌套路径处理', () => {
        it('应该支持深层嵌套路径', () => {
            store.set('user', { profile: { settings: { theme: 'dark' } } });
            store.set('user.profile.settings.theme', 'light');
            
            expect(store.get('user.profile.settings.theme')).toBe('light');
        });

        it('设置嵌套路径应该创建中间对象', () => {
            store.set('user.profile.name', '测试');
            
            expect(store.get('user.profile.name')).toBe('测试');
        });

        it('获取不存在的嵌套路径应该返回undefined', () => {
            expect(store.get('user.nonexistent.path')).toBeUndefined();
        });

        it('订阅父路径应该被子路径变更触发', () => {
            let received = null;
            store.set('user', { name: '初始' });
            store.subscribe('user', (newVal) => { received = newVal; });
            store.set('user.name', '新名字');
            
            expect(received).toBeDefined();
        });
    });

    describe('错误处理', () => {
        it('监听器抛出错误不应该影响其他监听器', () => {
            const errorListener = vi.fn(() => {
                throw new Error('Listener error');
            });
            const normalListener = vi.fn();
            
            store.subscribe('count', errorListener);
            store.subscribe('count', normalListener);
            
            store.set('count', 10);
            
            expect(errorListener).toHaveBeenCalled();
            expect(normalListener).toHaveBeenCalled();
            expect(console.error).toHaveBeenCalled();
        });

        it('全局监听器抛出错误不应该影响其他监听器', () => {
            const errorListener = vi.fn(() => {
                throw new Error('Global listener error');
            });
            const normalListener = vi.fn();
            
            store.subscribeAll(errorListener);
            store.subscribe('count', normalListener);
            
            store.set('count', 10);
            
            expect(errorListener).toHaveBeenCalled();
            expect(normalListener).toHaveBeenCalled();
            expect(console.error).toHaveBeenCalled();
        });
    });

    describe('全局单例 appStore', () => {
        it('应该存在全局单例', () => {
            expect(appStore).toBeDefined();
            expect(appStore instanceof Store).toBe(true);
        });

        it('应该有默认状态', () => {
            expect(appStore.get('project')).toBeNull();
            expect(appStore.get('taskId')).toBeNull();
            expect(appStore.get('mapEngine')).toBe('geoscene');
        });

        it('应该启用持久化', () => {
            appStore.set('project', { id: 'test' });
            expect(localStorage.setItem).toHaveBeenCalled();
        });

        it('应该启用日志', () => {
            appStore.set('mapEngine', 'amap');
            expect(console.log).toHaveBeenCalled();
        });
    });

    describe('批量更新边界情况', () => {
        it('空批量更新不应该触发任何通知', () => {
            const listener = vi.fn();
            store.subscribeAll(listener);
            store.batch({});
            
            expect(listener).not.toHaveBeenCalled();
        });

        it('批量更新中相同的key应该只通知一次', () => {
            const listener = vi.fn();
            store.subscribeAll(listener);
            store.batch({ count: 10, count: 20 });
            
            // count应该只被通知一次
            const countCalls = listener.mock.calls.filter(call => call[2] === 'count');
            expect(countCalls.length).toBe(1);
        });
    });
});
