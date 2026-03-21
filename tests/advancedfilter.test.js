import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { AdvancedFilter } from '../apps/frontend/js/utils/AdvancedFilter.js';

describe('AdvancedFilter', () => {
    let filter;
    let testData;

    beforeEach(() => {
        // Mock localStorage
        const localStorageMock = {
            getItem: vi.fn(),
            setItem: vi.fn(),
            removeItem: vi.fn(),
            clear: vi.fn()
        };
        global.localStorage = localStorageMock;

        // Mock document
        global.document = {
            createElement: vi.fn((tag) => ({
                className: '',
                innerHTML: '',
                style: {},
                querySelector: vi.fn(() => ({
                    addEventListener: vi.fn(),
                    value: '',
                    style: {},
                    querySelectorAll: vi.fn(() => [])
                })),
                querySelectorAll: vi.fn(() => []),
                appendChild: vi.fn(),
                remove: vi.fn()
            }))
        };

        // 创建测试数据
        testData = [
            { x: 1, y: 1, value: 10, name: 'Point A' },
            { x: 2, y: 2, value: 20, name: 'Point B' },
            { x: 3, y: 3, value: 30, name: 'Point C' },
            { x: 4, y: 4, value: 40, name: 'Point D' }
        ];

        filter = new AdvancedFilter(testData);
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('条件添加', () => {
        it('应该成功添加筛选条件', () => {
            const condition = {
                field: 'value',
                operator: 'gt',
                value: 15
            };

            filter.addCondition(condition);

            expect(filter.conditions).toHaveLength(1);
            expect(filter.conditions[0]).toEqual(condition);
        });

        it('应该支持添加多个条件', () => {
            filter.addCondition({ field: 'value', operator: 'gt', value: 10 });
            filter.addCondition({ field: 'name', operator: 'contains', value: 'A' });

            expect(filter.conditions).toHaveLength(2);
        });

        it('应该支持不同类型的操作符', () => {
            const operators = ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'contains'];

            operators.forEach(op => {
                filter.addCondition({ field: 'value', operator: op, value: 20 });
            });

            expect(filter.conditions).toHaveLength(operators.length);
        });

        it('应该支持between操作符和两个值', () => {
            const condition = {
                field: 'value',
                operator: 'between',
                value: 10,
                value2: 30
            };

            filter.addCondition(condition);

            expect(filter.conditions[0]).toEqual(condition);
        });
    });

    describe('条件移除', () => {
        it('应该成功移除指定索引的条件', () => {
            filter.addCondition({ field: 'value', operator: 'gt', value: 10 });
            filter.addCondition({ field: 'name', operator: 'contains', value: 'A' });

            filter.removeCondition(0);

            expect(filter.conditions).toHaveLength(1);
            expect(filter.conditions[0].field).toBe('name');
        });

        it('应该处理不存在的索引', () => {
            filter.addCondition({ field: 'value', operator: 'gt', value: 10 });

            expect(() => filter.removeCondition(10)).not.toThrow();
            expect(filter.conditions).toHaveLength(1);
        });

        it('应该处理空条件列表', () => {
            expect(() => filter.removeCondition(0)).not.toThrow();
        });
    });

    describe('条件清除', () => {
        it('应该成功清除所有条件', () => {
            filter.addCondition({ field: 'value', operator: 'gt', value: 10 });
            filter.addCondition({ field: 'name', operator: 'contains', value: 'A' });

            filter.clearConditions();

            expect(filter.conditions).toHaveLength(0);
        });

        it('应该处理空条件列表', () => {
            expect(() => filter.clearConditions()).not.toThrow();
        });
    });

    describe('筛选执行', () => {
        it('应该应用等于条件', () => {
            filter.addCondition({ field: 'value', operator: 'eq', value: 20 });

            const results = filter.apply();

            expect(results).toHaveLength(1);
            expect(results[0].value).toBe(20);
        });

        it('应该应用不等于条件', () => {
            filter.addCondition({ field: 'value', operator: 'neq', value: 20 });

            const results = filter.apply();

            expect(results).toHaveLength(3);
            expect(results.every(r => r.value !== 20)).toBe(true);
        });

        it('应该应用大于条件', () => {
            filter.addCondition({ field: 'value', operator: 'gt', value: 20 });

            const results = filter.apply();

            expect(results).toHaveLength(2);
            expect(results.every(r => r.value > 20)).toBe(true);
        });

        it('应该应用大于等于条件', () => {
            filter.addCondition({ field: 'value', operator: 'gte', value: 20 });

            const results = filter.apply();

            expect(results).toHaveLength(3);
            expect(results.every(r => r.value >= 20)).toBe(true);
        });

        it('应该应用小于条件', () => {
            filter.addCondition({ field: 'value', operator: 'lt', value: 30 });

            const results = filter.apply();

            expect(results).toHaveLength(2);
            expect(results.every(r => r.value < 30)).toBe(true);
        });

        it('应该应用小于等于条件', () => {
            filter.addCondition({ field: 'value', operator: 'lte', value: 30 });

            const results = filter.apply();

            expect(results).toHaveLength(3);
            expect(results.every(r => r.value <= 30)).toBe(true);
        });

        it('应该应用包含条件', () => {
            filter.addCondition({ field: 'name', operator: 'contains', value: 'point' });

            const results = filter.apply();

            expect(results).toHaveLength(4); // 所有点都包含'point'
        });

        it('应该应用包含条件（大小写不敏感）', () => {
            filter.addCondition({ field: 'name', operator: 'contains', value: 'POINT' });

            const results = filter.apply();

            expect(results).toHaveLength(4);
        });

        it('应该应用between条件', () => {
            filter.addCondition({ field: 'value', operator: 'between', value: 15, value2: 35 });

            const results = filter.apply();

            expect(results).toHaveLength(2);
            expect(results.every(r => r.value >= 15 && r.value <= 35)).toBe(true);
        });

        it('应该应用多个条件（AND逻辑）', () => {
            filter.addCondition({ field: 'value', operator: 'gt', value: 15 });
            filter.addCondition({ field: 'value', operator: 'lt', value: 35 });

            const results = filter.apply();

            expect(results).toHaveLength(2);
            expect(results.map(r => r.value)).toEqual([20, 30]);
        });

        it('应该处理不存在字段的条件', () => {
            filter.addCondition({ field: 'nonexistent', operator: 'eq', value: 10 });

            const results = filter.apply();

            expect(results).toHaveLength(0);
        });

        it('应该处理null和undefined值', () => {
            const dataWithNulls = [
                { x: 1, y: 1, value: null, name: 'Point A' },
                { x: 2, y: 2, value: undefined, name: 'Point B' },
                { x: 3, y: 3, value: 30, name: 'Point C' }
            ];

            filter.setData(dataWithNulls);
            filter.addCondition({ field: 'value', operator: 'eq', value: 30 });

            const results = filter.apply();

            expect(results).toHaveLength(1);
            expect(results[0].value).toBe(30);
        });

        it('应该调用筛选回调', () => {
            const callback = vi.fn();
            filter = new AdvancedFilter(testData, callback);

            filter.addCondition({ field: 'value', operator: 'gt', value: 15 });
            filter.apply();

            expect(callback).toHaveBeenCalled();
            expect(callback).toHaveBeenCalledWith(expect.any(Array));
        });

        it('应该处理字符串数值比较', () => {
            const stringData = [
                { x: '1', y: '1', value: '10' },
                { x: '2', y: '2', value: '20' },
                { x: '3', y: '3', value: '30' }
            ];

            filter.setData(stringData);
            filter.addCondition({ field: 'value', operator: 'gt', value: 15 });

            const results = filter.apply();

            expect(results).toHaveLength(2);
        });
    });

    describe('筛选条件保存', () => {
        it('应该成功保存筛选条件', () => {
            filter.addCondition({ field: 'value', operator: 'gt', value: 15 });
            filter.addCondition({ field: 'name', operator: 'contains', value: 'A' });

            filter.saveFilter('test-filter');

            expect(localStorage.setItem).toHaveBeenCalledWith(
                'udake_saved_filters',
                expect.any(String)
            );
        });

        it('应该保存条件的时间戳', () => {
            filter.addCondition({ field: 'value', operator: 'gt', value: 15 });

            const beforeTime = Date.now();
            filter.saveFilter('test-filter');
            const afterTime = Date.now();

            const savedData = JSON.parse(localStorage.setItem.mock.calls[0][1]);
            expect(savedData[0].timestamp).toBeGreaterThanOrEqual(beforeTime);
            expect(savedData[0].timestamp).toBeLessThanOrEqual(afterTime);
        });

        it('应该追加到已保存的筛选条件', () => {
            localStorage.getItem.mockReturnValue(JSON.stringify([
                { name: 'existing-filter', conditions: [], timestamp: Date.now() }
            ]));

            filter.addCondition({ field: 'value', operator: 'gt', value: 15 });
            filter.saveFilter('new-filter');

            const savedData = JSON.parse(localStorage.setItem.mock.calls[0][1]);
            expect(savedData).toHaveLength(2);
        });
    });

    describe('筛选条件加载', () => {
        it('应该成功加载已保存的筛选条件', () => {
            const savedFilter = {
                name: 'test-filter',
                conditions: [
                    { field: 'value', operator: 'gt', value: 15 }
                ],
                timestamp: Date.now()
            };

            localStorage.getItem.mockReturnValue(JSON.stringify([savedFilter]));

            const result = filter.loadFilter('test-filter');

            expect(result).toBe(true);
            expect(filter.conditions).toEqual(savedFilter.conditions);
        });

        it('应该处理不存在的筛选条件', () => {
            localStorage.getItem.mockReturnValue(JSON.stringify([]));

            const result = filter.loadFilter('nonexistent-filter');

            expect(result).toBe(false);
            expect(filter.conditions).toHaveLength(0);
        });

        it('应该处理localStorage错误', () => {
            localStorage.getItem.mockImplementation(() => {
                throw new Error('Storage error');
            });

            const result = filter.loadFilter('test-filter');

            expect(result).toBe(false);
        });
    });

    describe('获取已保存的筛选条件', () => {
        it('应该返回已保存的筛选条件列表', () => {
            const savedFilters = [
                { name: 'filter1', conditions: [], timestamp: Date.now() },
                { name: 'filter2', conditions: [], timestamp: Date.now() }
            ];

            localStorage.getItem.mockReturnValue(JSON.stringify(savedFilters));

            const result = AdvancedFilter.getSavedFilters();

            expect(result).toEqual(savedFilters);
        });

        it('应该处理空的localStorage', () => {
            localStorage.getItem.mockReturnValue(null);

            const result = AdvancedFilter.getSavedFilters();

            expect(result).toEqual([]);
        });

        it('应该处理localStorage错误', () => {
            localStorage.getItem.mockImplementation(() => {
                throw new Error('Storage error');
            });

            const result = AdvancedFilter.getSavedFilters();

            expect(result).toEqual([]);
        });
    });

    describe('删除已保存的筛选条件', () => {
        it('应该成功删除指定的筛选条件', () => {
            const savedFilters = [
                { name: 'filter1', conditions: [], timestamp: Date.now() },
                { name: 'filter2', conditions: [], timestamp: Date.now() }
            ];

            localStorage.getItem.mockReturnValue(JSON.stringify(savedFilters));

            AdvancedFilter.deleteSavedFilter('filter1');

            expect(localStorage.setItem).toHaveBeenCalledWith(
                'udake_saved_filters',
                JSON.stringify([savedFilters[1]])
            );
        });

        it('应该处理不存在的筛选条件', () => {
            const savedFilters = [
                { name: 'filter1', conditions: [], timestamp: Date.now() }
            ];

            localStorage.getItem.mockReturnValue(JSON.stringify(savedFilters));

            AdvancedFilter.deleteSavedFilter('nonexistent-filter');

            expect(localStorage.setItem).toHaveBeenCalledWith(
                'udake_saved_filters',
                JSON.stringify(savedFilters)
            );
        });
    });

    describe('全文搜索', () => {
        it('应该执行全文搜索', () => {
            const results = AdvancedFilter.search(testData, 'Point');

            expect(results).toHaveLength(4);
        });

        it('应该搜索指定字段', () => {
            const results = AdvancedFilter.search(testData, 'A', ['name']);

            expect(results).toHaveLength(1);
            expect(results[0].name).toBe('Point A');
        });

        it('应该处理空关键词', () => {
            const results = AdvancedFilter.search(testData, '');

            expect(results).toEqual(testData);
        });

        it('应该处理空白关键词', () => {
            const results = AdvancedFilter.search(testData, '   ');

            expect(results).toEqual(testData);
        });

        it('应该不区分大小写', () => {
            const results = AdvancedFilter.search(testData, 'POINT A');

            expect(results).toHaveLength(1);
            expect(results[0].name).toBe('Point A');
        });

        it('应该处理null和undefined值', () => {
            const dataWithNulls = [
                { x: 1, y: 1, value: null, name: 'Point A' },
                { x: 2, y: 2, value: undefined, name: 'Point B' },
                { x: 3, y: 3, value: 30, name: 'Point C' }
            ];

            const results = AdvancedFilter.search(dataWithNulls, 'Point');

            expect(results).toHaveLength(3);
        });

        it('应该保存搜索历史', () => {
            AdvancedFilter.search(testData, 'test keyword');

            expect(localStorage.setItem).toHaveBeenCalledWith(
                'udake_search_history',
                expect.any(String)
            );
        });

        it('应该限制历史记录数量', () => {
            localStorage.getItem.mockReturnValue(JSON.stringify(
                Array.from({ length: 20 }, (_, i) => `keyword${i}`)
            ));

            AdvancedFilter.search(testData, 'new keyword');

            const savedHistory = JSON.parse(localStorage.setItem.mock.calls[0][1]);
            expect(savedHistory).toHaveLength(20);
            expect(savedHistory[0]).toBe('new keyword');
        });

        it('应该去除重复的历史记录', () => {
            localStorage.getItem.mockReturnValue(JSON.stringify(['existing keyword']));

            AdvancedFilter.search(testData, 'existing keyword');

            const savedHistory = JSON.parse(localStorage.setItem.mock.calls[0][1]);
            expect(savedHistory).toHaveLength(1);
            expect(savedHistory[0]).toBe('existing keyword');
        });
    });

    describe('搜索高亮', () => {
        it('应该高亮匹配的文本', () => {
            const result = AdvancedFilter.highlight('This is a test', 'test');

            expect(result).toContain('<mark class="search-highlight">test</mark>');
        });

        it('应该处理空关键词', () => {
            const result = AdvancedFilter.highlight('This is a test', '');

            expect(result).toBe('This is a test');
        });

        it('应该处理空白关键词', () => {
            const result = AdvancedFilter.highlight('This is a test', '   ');

            expect(result).toBe('This is a test');
        });

        it('应该不区分大小写', () => {
            const result = AdvancedFilter.highlight('This is a TEST', 'test');

            expect(result).toContain('<mark class="search-highlight">TEST</mark>');
        });

        it('应该高亮所有匹配项', () => {
            const result = AdvancedFilter.highlight('test test test', 'test');

            const matches = result.match(/<mark/g);
            expect(matches).toHaveLength(3);
        });

        it('应该转义特殊字符', () => {
            const result = AdvancedFilter.highlight('test.*test', 'test.*');

            expect(result).toContain('<mark class="search-highlight">test.*</mark>');
        });
    });

    describe('搜索历史', () => {
        it('应该返回搜索历史', () => {
            const history = ['keyword1', 'keyword2', 'keyword3'];
            localStorage.getItem.mockReturnValue(JSON.stringify(history));

            const result = AdvancedFilter.getSearchHistory();

            expect(result).toEqual(history);
        });

        it('应该处理空的localStorage', () => {
            localStorage.getItem.mockReturnValue(null);

            const result = AdvancedFilter.getSearchHistory();

            expect(result).toEqual([]);
        });

        it('应该处理localStorage错误', () => {
            localStorage.getItem.mockImplementation(() => {
                throw new Error('Storage error');
            });

            const result = AdvancedFilter.getSearchHistory();

            expect(result).toEqual([]);
        });

        it('应该清除搜索历史', () => {
            AdvancedFilter.clearSearchHistory();

            expect(localStorage.removeItem).toHaveBeenCalledWith('udake_search_history');
        });
    });

    describe('面板创建', () => {
        it('应该创建有效的面板元素', () => {
            const panel = filter.createPanel();

            expect(panel).toHaveProperty('className');
            expect(panel).toHaveProperty('innerHTML');
        });

        it('应该包含必要的UI元素', () => {
            const panel = filter.createPanel();

            expect(panel.innerHTML).toContain('高级筛选');
            expect(panel.innerHTML).toContain('filter-conditions');
            expect(panel.innerHTML).toContain('filter-add');
            expect(panel.innerHTML).toContain('filter-apply');
            expect(panel.innerHTML).toContain('filter-clear');
        });

        it('应该正确设置面板类名', () => {
            const panel = filter.createPanel();

            expect(panel.className).toBe('panel filter-panel');
        });

        it('应该包含搜索输入框', () => {
            const panel = filter.createPanel();

            expect(panel.innerHTML).toContain('filter-search-input');
        });

        it('应该包含已保存筛选区域', () => {
            const panel = filter.createPanel();

            expect(panel.innerHTML).toContain('saved-filters-list');
        });
    });

    describe('数据设置', () => {
        it('应该成功设置新数据', () => {
            const newData = [
                { x: 5, y: 5, value: 50, name: 'Point E' }
            ];

            filter.setData(newData);

            expect(filter._data).toEqual(newData);
        });

        it('应该处理空数据', () => {
            filter.setData([]);

            expect(filter._data).toEqual([]);
        });
    });

    describe('边界情况', () => {
        it('应该处理大量数据', () => {
            const largeData = Array.from({ length: 10000 }, (_, i) => ({
                x: i,
                y: i,
                value: i * 10,
                name: `Point ${i}`
            }));

            filter.setData(largeData);
            filter.addCondition({ field: 'value', operator: 'gt', value: 5000 });

            const results = filter.apply();

            expect(results.length).toBeGreaterThan(0);
        });

        it('应该处理极端数值', () => {
            const extremeData = [
                { x: 1, y: 1, value: Number.MAX_VALUE },
                { x: 2, y: 2, value: -Number.MAX_VALUE },
                { x: 3, y: 3, value: 0 }
            ];

            filter.setData(extremeData);
            filter.addCondition({ field: 'value', operator: 'gt', value: 0 });

            const results = filter.apply();

            expect(results).toHaveLength(1);
            expect(results[0].value).toBe(Number.MAX_VALUE);
        });

        it('应该处理包含特殊字符的字段值', () => {
            const specialData = [
                { x: 1, y: 1, value: 10, name: 'Point with <script>' },
                { x: 2, y: 2, value: 20, name: 'Point with "quotes"' }
            ];

            filter.setData(specialData);
            filter.addCondition({ field: 'name', operator: 'contains', value: 'script' });

            const results = filter.apply();

            expect(results).toHaveLength(1);
        });

        it('应该处理包含嵌套对象的数据（浅层字段）', () => {
            const nestedData = [
                { x: 1, y: 1, value: 10, metadata: { source: 'manual' } },
                { x: 2, y: 2, value: 20, metadata: { source: 'auto' } }
            ];

            filter.setData(nestedData);
            filter.addCondition({ field: 'value', operator: 'gt', value: 15 });

            const results = filter.apply();

            expect(results).toHaveLength(1);
        });

        it('应该处理数组字段值', () => {
            const arrayData = [
                { x: 1, y: 1, value: 10, tags: ['a', 'b', 'c'] },
                { x: 2, y: 2, value: 20, tags: ['d', 'e', 'f'] }
            ];

            filter.setData(arrayData);
            filter.addCondition({ field: 'tags', operator: 'contains', value: 'a' });

            const results = filter.apply();

            expect(results).toHaveLength(1);
        });
    });

    describe('接口类型', () => {
        it('应该接受符合FilterCondition接口的条件', () => {
            const validCondition = {
                field: 'value',
                operator: 'gt',
                value: 10
            };

            expect(() => filter.addCondition(validCondition)).not.toThrow();
        });

        it('应该接受符合SavedFilter接口的筛选', () => {
            const validFilter = {
                name: 'test-filter',
                conditions: [
                    { field: 'value', operator: 'gt', value: 10 }
                ],
                timestamp: Date.now()
            };

            localStorage.getItem.mockReturnValue(JSON.stringify([validFilter]));

            expect(() => filter.loadFilter('test-filter')).not.toThrow();
        });
    });
});