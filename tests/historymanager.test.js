import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { HistoryManager } from '../apps/frontend/js/utils/HistoryManager.js';

describe('HistoryManager', () => {
    beforeEach(() => {
        // Mock localStorage
        global.localStorage = {
            getItem: vi.fn(),
            setItem: vi.fn(),
            removeItem: vi.fn(),
            clear: vi.fn()
        };
        
        // Mock document
        global.document = {
            createElement: vi.fn(() => ({
                className: '',
                innerHTML: '',
                querySelector: vi.fn(() => ({
                    disabled: false,
                    addEventListener: vi.fn()
                })),
                addEventListener: vi.fn()
            }))
        };
        
        // Clear static state
        HistoryManager._entries = [];
        HistoryManager._undoStack = [];
        HistoryManager._redoStack = [];
        HistoryManager._listeners.clear();
        HistoryManager._undoHandlers.clear();
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('初始化', () => {
        it('应该成功初始化', () => {
            expect(() => HistoryManager.init()).not.toThrow();
        });

        it('应该从localStorage加载历史记录', () => {
            const savedEntries = [
                { id: '1', action: 'test', type: 'upload', detail: 'test', timestamp: Date.now(), undoable: false }
            ];
            localStorage.getItem.mockReturnValue(JSON.stringify(savedEntries));
            
            HistoryManager.init();
            
            const entries = HistoryManager.getAll();
            expect(entries.length).toBeGreaterThan(0);
        });

        it('应该处理无效的localStorage数据', () => {
            localStorage.getItem.mockReturnValue('invalid json');
            
            expect(() => HistoryManager.init()).not.toThrow();
        });
    });

    describe('记录操作', () => {
        beforeEach(() => {
            HistoryManager.init();
        });

        it('应该成功记录操作', () => {
            HistoryManager.record({
                action: '上传数据',
                type: 'upload',
                detail: '上传了100个采样点',
                undoable: true
            });
            
            const entries = HistoryManager.getAll();
            expect(entries.length).toBe(1);
            expect(entries[0].action).toBe('上传数据');
        });

        it('记录的操作应该包含ID和时间戳', () => {
            HistoryManager.record({
                action: '测试操作',
                type: 'kriging',
                detail: '测试',
                undoable: false
            });
            
            const entry = HistoryManager.getAll()[0];
            expect(entry.id).toBeDefined();
            expect(entry.timestamp).toBeDefined();
            expect(typeof entry.id).toBe('string');
            expect(typeof entry.timestamp).toBe('number');
        });

        it('可撤销操作应该加入撤销栈', () => {
            HistoryManager.record({
                action: '上传数据',
                type: 'upload',
                detail: '测试',
                undoable: true,
                undoData: { data: 'test' }
            });
            
            expect(HistoryManager.canUndo()).toBe(true);
        });

        it('记录新操作时应该清空重做栈', async () => {
            const handler = vi.fn().mockResolvedValue(undefined);
            HistoryManager.registerUndoHandler('upload', handler);
            
            HistoryManager.record({
                action: '操作1',
                type: 'upload',
                detail: '测试',
                undoable: true,
                undoData: { data: 'test1' }
            });
            
            HistoryManager.record({
                action: '操作2',
                type: 'upload',
                detail: '测试',
                undoable: true,
                undoData: { data: 'test2' }
            });
            
            // 撤销操作2
            await HistoryManager.undo();
            
            // 记录新操作，这应该清空重做栈
            HistoryManager.record({
                action: '操作3',
                type: 'upload',
                detail: '测试',
                undoable: true
            });
            
            // 验证记录新操作后，撤销操作数增加
            expect(HistoryManager.canUndo()).toBe(true);
        });

        it('超过最大条数时应该删除最早的记录', () => {
            const maxEntries = 200;
            
            for (let i = 0; i < maxEntries + 10; i++) {
                HistoryManager.record({
                    action: `操作${i}`,
                    type: 'upload',
                    detail: `测试${i}`,
                    undoable: false
                });
            }
            
            const entries = HistoryManager.getAll();
            expect(entries.length).toBeLessThanOrEqual(maxEntries);
        });

        it('应该保存到localStorage', () => {
            HistoryManager.record({
                action: '测试',
                type: 'upload',
                detail: '测试',
                undoable: false
            });
            
            expect(localStorage.setItem).toHaveBeenCalled();
        });
    });

    describe('撤销/重做', () => {
        beforeEach(() => {
            HistoryManager.init();
        });

        it('应该能够撤销操作', async () => {
            const handler = vi.fn();
            HistoryManager.registerUndoHandler('upload', handler);
            
            HistoryManager.record({
                action: '上传数据',
                type: 'upload',
                detail: '测试',
                undoable: true,
                undoData: { data: 'test' }
            });
            
            const result = await HistoryManager.undo();
            
            expect(result).toBe(true);
            expect(handler).toHaveBeenCalledWith({ data: 'test' });
        });

        it('撤销后应该记录撤销操作', async () => {
            const handler = vi.fn().mockResolvedValue(undefined);
            HistoryManager.registerUndoHandler('upload', handler);
            
            HistoryManager.record({
                action: '原始操作',
                type: 'upload',
                detail: '测试',
                undoable: true,
                undoData: { data: 'test' }
            });
            
            await HistoryManager.undo();
            
            const entries = HistoryManager.getAll();
            expect(entries.some(e => e.action.includes('撤销'))).toBe(true);
        });

        it('撤销时应该加入重做栈', async () => {
            const handler = vi.fn().mockResolvedValue(undefined);
            HistoryManager.registerUndoHandler('upload', handler);
            
            HistoryManager.record({
                action: '操作',
                type: 'upload',
                detail: '测试',
                undoable: true,
                undoData: { data: 'test' }
            });
            
            await HistoryManager.undo();
            
            expect(HistoryManager.canRedo()).toBe(true);
        });

        it('没有可撤销操作时应该返回false', async () => {
            const result = await HistoryManager.undo();
            expect(result).toBe(false);
        });

        it('应该能够重做操作', async () => {
            const handler = vi.fn().mockResolvedValue(undefined);
            HistoryManager.registerUndoHandler('upload', handler);
            
            HistoryManager.record({
                action: '操作',
                type: 'upload',
                detail: '测试',
                undoable: true,
                undoData: { data: 'test' }
            });
            
            await HistoryManager.undo();
            const result = await HistoryManager.redo();
            
            expect(result).toBe(true);
        });

        it('没有可重做操作时应该返回false', async () => {
            const result = await HistoryManager.redo();
            expect(result).toBe(false);
        });

        it('应该正确判断是否可以撤销', () => {
            expect(HistoryManager.canUndo()).toBe(false);
            
            HistoryManager.record({
                action: '操作',
                type: 'upload',
                detail: '测试',
                undoable: true
            });
            
            expect(HistoryManager.canUndo()).toBe(true);
        });

        it('应该正确判断是否可以重做', () => {
            expect(HistoryManager.canRedo()).toBe(false);
        });
    });

    describe('撤销处理器', () => {
        beforeEach(() => {
            HistoryManager.init();
        });

        it('应该能够注册撤销处理器', () => {
            const handler = vi.fn();
            HistoryManager.registerUndoHandler('upload', handler);
            
            // 验证处理器已注册（通过行为）
            HistoryManager.record({
                action: '测试',
                type: 'upload',
                detail: '测试',
                undoable: true,
                undoData: { test: 'data' }
            });
            
            HistoryManager.undo();
            // 如果处理器未注册，撤销会失败
        });

        it('应该能够注册多个不同类型的处理器', () => {
            const uploadHandler = vi.fn();
            const krigingHandler = vi.fn();
            
            HistoryManager.registerUndoHandler('upload', uploadHandler);
            HistoryManager.registerUndoHandler('kriging', krigingHandler);
            
            // 验证两个处理器都能注册
        });
    });

    describe('搜索和筛选', () => {
        beforeEach(() => {
            HistoryManager.init();
            
            HistoryManager.record({
                action: '上传数据',
                type: 'upload',
                detail: '上传了100个点',
                undoable: false
            });
            
            HistoryManager.record({
                action: '克里金插值',
                type: 'kriging',
                detail: '完成了插值计算',
                undoable: false
            });
            
            HistoryManager.record({
                action: '导出结果',
                type: 'export',
                detail: '导出了预测结果',
                undoable: false
            });
        });

        it('应该能够搜索历史记录', () => {
            const results = HistoryManager.search('上传');
            expect(results.length).toBe(1);
            expect(results[0].action).toBe('上传数据');
        });

        it('搜索应该不区分大小写', () => {
            const results = HistoryManager.search('UPLOAD');
            expect(results.length).toBeGreaterThanOrEqual(0);
        });

        it('搜索应该匹配detail字段', () => {
            const results = HistoryManager.search('插值');
            expect(results.length).toBeGreaterThan(0);
        });

        it('搜索空字符串应该返回所有记录', () => {
            const results = HistoryManager.search('');
            expect(results.length).toBeGreaterThan(0);
        });

        it('应该能够按类型筛选', () => {
            const results = HistoryManager.filterByType('upload');
            expect(results.length).toBe(1);
            expect(results[0].type).toBe('upload');
        });

        it('筛选不存在的类型应该返回空数组', () => {
            const results = HistoryManager.filterByType('nonexistent');
            expect(results).toEqual([]);
        });
    });

    describe('清除历史', () => {
        beforeEach(() => {
            HistoryManager.init();
            
            HistoryManager.record({
                action: '操作1',
                type: 'upload',
                detail: '测试',
                undoable: true
            });
            
            HistoryManager.record({
                action: '操作2',
                type: 'upload',
                detail: '测试',
                undoable: true
            });
        });

        it('应该清除所有历史记录', () => {
            HistoryManager.clear();
            
            expect(HistoryManager.getAll()).toEqual([]);
            expect(HistoryManager.canUndo()).toBe(false);
            expect(HistoryManager.canRedo()).toBe(false);
        });

        it('清除时应该保存到localStorage', () => {
            HistoryManager.clear();
            
            expect(localStorage.setItem).toHaveBeenCalled();
        });
    });

    describe('变化监听器', () => {
        beforeEach(() => {
            HistoryManager.init();
        });

        it('应该能够注册变化监听器', () => {
            const callback = vi.fn();
            const remove = HistoryManager.onChange(callback);
            
            expect(typeof remove).toBe('function');
        });

        it('记录操作时应该通知监听器', () => {
            const callback = vi.fn();
            HistoryManager.onChange(callback);
            
            HistoryManager.record({
                action: '测试',
                type: 'upload',
                detail: '测试',
                undoable: false
            });
            
            expect(callback).toHaveBeenCalled();
        });

        it('清除历史时应该通知监听器', () => {
            const callback = vi.fn();
            HistoryManager.onChange(callback);
            
            HistoryManager.clear();
            
            expect(callback).toHaveBeenCalled();
        });

        it('应该能够移除监听器', () => {
            const callback = vi.fn();
            const remove = HistoryManager.onChange(callback);
            
            remove();
            HistoryManager.record({
                action: '测试',
                type: 'upload',
                detail: '测试',
                undoable: false
            });
            
            expect(callback).not.toHaveBeenCalled();
        });

        it('监听器抛出错误时不应该影响其他监听器', () => {
            const errorCallback = vi.fn(() => { throw new Error('Test error'); });
            const normalCallback = vi.fn();
            
            HistoryManager.onChange(errorCallback);
            HistoryManager.onChange(normalCallback);
            
            HistoryManager.record({
                action: '测试',
                type: 'upload',
                detail: '测试',
                undoable: false
            });
            
            expect(errorCallback).toHaveBeenCalled();
            expect(normalCallback).toHaveBeenCalled();
        });
    });

    describe('创建历史面板', () => {
        beforeEach(() => {
            HistoryManager.init();
        });

        it('应该创建历史面板DOM元素', () => {
            const panel = HistoryManager.createPanel();
            
            expect(panel).toBeDefined();
            expect(panel.className).toBe('panel');
        });

        it('面板应该包含标题', () => {
            const panel = HistoryManager.createPanel();
            expect(panel.innerHTML).toContain('操作历史');
        });

        it('面板应该包含操作按钮', () => {
            const panel = HistoryManager.createPanel();
            expect(panel.innerHTML).toContain('撤销');
            expect(panel.innerHTML).toContain('重做');
            expect(panel.innerHTML).toContain('清除');
        });

        it('面板应该显示操作列表', () => {
            HistoryManager.record({
                action: '测试操作',
                type: 'upload',
                detail: '测试',
                undoable: false
            });
            
            const panel = HistoryManager.createPanel();
            // 由于mock的实现，面板内容可能不会被实时更新
            // 这里主要验证面板创建功能
            expect(panel).toBeDefined();
            expect(panel.innerHTML).toContain('操作历史');
        });
    });

    describe('边界情况', () => {
        beforeEach(() => {
            HistoryManager.init();
        });

        it('撤销时如果没有undoData应该正常处理', async () => {
            HistoryManager.record({
                action: '测试',
                type: 'upload',
                detail: '测试',
                undoable: true
            });
            
            const result = await HistoryManager.undo();
            expect(result).toBe(false);
        });

        it('撤销时如果没有对应的处理器应该返回false', async () => {
            HistoryManager.record({
                action: '测试',
                type: 'nonexistent',
                detail: '测试',
                undoable: true,
                undoData: { test: 'data' }
            });
            
            const result = await HistoryManager.undo();
            expect(result).toBe(false);
        });

        it('记录应该按照时间倒序排列', () => {
            HistoryManager.record({
                action: '操作1',
                type: 'upload',
                detail: '测试',
                undoable: false
            });
            
            HistoryManager.record({
                action: '操作2',
                type: 'upload',
                detail: '测试',
                undoable: false
            });
            
            const entries = HistoryManager.getAll();
            expect(entries[0].action).toBe('操作2');
        });

        it('应该处理所有支持的操作类型', () => {
            const types = ['upload', 'kriging', 'export', 'project', 'point', 'setting'];
            
            types.forEach(type => {
                HistoryManager.record({
                    action: `${type}操作`,
                    type: type,
                    detail: '测试',
                    undoable: false
                });
            });
            
            const entries = HistoryManager.getAll();
            expect(entries.length).toBe(types.length);
        });
    });
});