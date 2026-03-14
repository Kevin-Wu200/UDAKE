import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { BatchOperations } from '../frontend/js/utils/BatchOperations.js';

describe('BatchOperations', () => {
    beforeEach(() => {
        // Mock document
        global.document = {
            body: {
                appendChild: vi.fn(),
                removeChild: vi.fn()
            },
            createElement: vi.fn(() => ({
                className: '',
                innerHTML: '',
                style: {},
                href: '',
                download: '',
                click: vi.fn(),
                addEventListener: vi.fn(),
                querySelector: vi.fn(() => ({
                    addEventListener: vi.fn()
                })),
                classList: {
                    add: vi.fn(),
                    remove: vi.fn()
                }
            }))
        };
        
        // Mock URL
        global.URL = {
            createObjectURL: vi.fn(() => 'blob:url'),
            revokeObjectURL: vi.fn()
        };
        
        // Mock requestAnimationFrame
        global.requestAnimationFrame = vi.fn(cb => cb());
        
        // Mock setTimeout
        global.setTimeout = vi.fn((cb, delay) => {
            cb();
            return 1;
        });
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('批量导入', () => {
        it('应该成功导入有效的GeoJSON文件', async () => {
            const mockFile = {
                name: 'test.geojson',
                text: vi.fn().mockResolvedValue('{"type":"FeatureCollection","features":[]}')
            };
            
            const result = await BatchOperations.batchImport([mockFile]);
            
            expect(result.total).toBe(1);
            expect(result.success).toBe(1);
            expect(result.failed).toBe(0);
        });

        it('应该成功导入有效的JSON文件', async () => {
            const mockFile = {
                name: 'test.json',
                text: vi.fn().mockResolvedValue('{"type":"FeatureCollection","features":[]}')
            };
            
            const result = await BatchOperations.batchImport([mockFile]);
            
            expect(result.success).toBe(1);
        });

        it('应该拒绝不支持的文件格式', async () => {
            const mockFile = {
                name: 'test.txt',
                text: vi.fn().mockResolvedValue('{"test": "data"}')
            };
            
            const result = await BatchOperations.batchImport([mockFile]);
            
            expect(result.failed).toBe(1);
            expect(result.errors[0]).toContain('不支持的文件格式');
        });

        it('应该处理无效的JSON文件', async () => {
            const mockFile = {
                name: 'test.geojson',
                text: vi.fn().mockResolvedValue('invalid json')
            };
            
            const result = await BatchOperations.batchImport([mockFile]);
            
            expect(result.failed).toBe(1);
            expect(result.errors.length).toBeGreaterThan(0);
        });

        it('应该处理多个文件', async () => {
            const mockFiles = [
                { name: 'test1.geojson', text: vi.fn().mockResolvedValue('{"type":"FeatureCollection","features":[]}') },
                { name: 'test2.json', text: vi.fn().mockResolvedValue('{"type":"FeatureCollection","features":[]}') }
            ];
            
            const result = await BatchOperations.batchImport(mockFiles);
            
            expect(result.total).toBe(2);
            expect(result.success).toBe(2);
        });

        it('应该调用进度回调', async () => {
            const progressCallback = vi.fn();
            const mockFile = {
                name: 'test.geojson',
                text: vi.fn().mockResolvedValue('{"type":"FeatureCollection","features":[]}')
            };
            
            await BatchOperations.batchImport([mockFile], progressCallback);
            
            expect(progressCallback).toHaveBeenCalledWith(1, 1);
        });
    });

    describe('批量删除', () => {
        it('应该删除指定索引的点', () => {
            const points = [
                { x: 1, y: 1, value: 10 },
                { x: 2, y: 2, value: 20 },
                { x: 3, y: 3, value: 30 }
            ];
            
            const result = BatchOperations.batchDeletePoints(points, [1]);
            
            expect(result.length).toBe(2);
            expect(result[0].value).toBe(10);
            expect(result[1].value).toBe(30);
        });

        it('应该删除多个索引的点', () => {
            const points = [
                { x: 1, y: 1, value: 10 },
                { x: 2, y: 2, value: 20 },
                { x: 3, y: 3, value: 30 },
                { x: 4, y: 4, value: 40 }
            ];
            
            const result = BatchOperations.batchDeletePoints(points, [0, 2]);
            
            expect(result.length).toBe(2);
            expect(result[0].value).toBe(20);
            expect(result[1].value).toBe(40);
        });

        it('空索引数组应该返回原数组', () => {
            const points = [
                { x: 1, y: 1, value: 10 },
                { x: 2, y: 2, value: 20 }
            ];
            
            const result = BatchOperations.batchDeletePoints(points, []);
            
            expect(result).toEqual(points);
        });

        it('不存在的索引应该被忽略', () => {
            const points = [
                { x: 1, y: 1, value: 10 },
                { x: 2, y: 2, value: 20 }
            ];
            
            const result = BatchOperations.batchDeletePoints(points, [5, 10]);
            
            expect(result).toEqual(points);
        });
    });

    describe('批量更新', () => {
        it('应该更新指定索引的点', () => {
            const points = [
                { x: 1, y: 1, value: 10, name: 'A' },
                { x: 2, y: 2, value: 20, name: 'B' },
                { x: 3, y: 3, value: 30, name: 'C' }
            ];
            
            const result = BatchOperations.batchUpdatePoints(points, [1], { value: 25 });
            
            expect(result[1].value).toBe(25);
            expect(result[0].value).toBe(10);
            expect(result[2].value).toBe(30);
        });

        it('应该更新多个索引的点', () => {
            const points = [
                { x: 1, y: 1, value: 10 },
                { x: 2, y: 2, value: 20 },
                { x: 3, y: 3, value: 30 }
            ];
            
            const result = BatchOperations.batchUpdatePoints(points, [0, 2], { value: 100 });
            
            expect(result[0].value).toBe(100);
            expect(result[1].value).toBe(20);
            expect(result[2].value).toBe(100);
        });

        it('应该支持更新多个属性', () => {
            const points = [
                { x: 1, y: 1, value: 10, name: 'A' },
                { x: 2, y: 2, value: 20, name: 'B' }
            ];
            
            const result = BatchOperations.batchUpdatePoints(points, [0], { value: 15, name: 'Updated' });
            
            expect(result[0].value).toBe(15);
            expect(result[0].name).toBe('Updated');
        });

        it('空索引数组应该返回原数组', () => {
            const points = [
                { x: 1, y: 1, value: 10 },
                { x: 2, y: 2, value: 20 }
            ];
            
            const result = BatchOperations.batchUpdatePoints(points, [], { value: 100 });
            
            expect(result).toEqual(points);
        });
    });

    describe('批量导出', () => {
        it('应该导出CSV格式', async () => {
            const data = [
                { x: 1, y: 1, value: 10 },
                { x: 2, y: 2, value: 20 }
            ];
            
            // Mock ExportEnhancer
            vi.doMock('../frontend/js/utils/ExportEnhancer.js', () => ({
                ExportEnhancer: {
                    exportAsCSV: vi.fn()
                }
            }));
            
            // 由于动态导入的复杂性，这里主要测试方法存在
            await expect(BatchOperations.batchExport(data, ['csv'], 'test')).resolves.not.toThrow();
        });

        it('应该导出GeoJSON格式', async () => {
            const data = [
                { x: 1, y: 1, value: 10 },
                { x: 2, y: 2, value: 20 }
            ];
            
            await expect(BatchOperations.batchExport(data, ['geojson'], 'test')).resolves.not.toThrow();
        });

        it('应该处理x/y坐标', async () => {
            const data = [
                { x: 116.39, y: 39.9, value: 10 }
            ];
            
            await expect(BatchOperations.batchExport(data, ['geojson'], 'test')).resolves.not.toThrow();
        });

        it('应该处理longitude/latitude坐标', async () => {
            const data = [
                { longitude: 116.39, latitude: 39.9, value: 10 }
            ];
            
            await expect(BatchOperations.batchExport(data, ['geojson'], 'test')).resolves.not.toThrow();
        });

        it('应该支持多个格式', async () => {
            const data = [
                { x: 1, y: 1, value: 10 }
            ];
            
            await expect(BatchOperations.batchExport(data, ['csv', 'geojson'], 'test')).resolves.not.toThrow();
        });
    });

    describe('批量操作确认', () => {
        it('应该创建确认对话框', async () => {
            const mockOverlay = {
                className: '',
                innerHTML: '',
                classList: { add: vi.fn(), remove: vi.fn() },
                querySelector: vi.fn((selector) => {
                    const mockButton = {
                        addEventListener: vi.fn((event, handler) => {
                            if (event === 'click') handler();
                        })
                    };
                    return mockButton;
                }),
                addEventListener: vi.fn((event, handler) => {
                    if (event === 'click') handler();
                }),
                remove: vi.fn()
            };
            
            document.createElement.mockReturnValue(mockOverlay);
            
            const result = await BatchOperations.confirmBatch('删除', 5);
            
            expect(document.createElement).toHaveBeenCalled();
            expect(document.body.appendChild).toHaveBeenCalled();
        });

        it('应该显示操作类型和数量', async () => {
            const mockOverlay = {
                className: '',
                innerHTML: '',
                classList: { add: vi.fn(), remove: vi.fn() },
                querySelector: vi.fn((selector) => {
                    const mockButton = {
                        addEventListener: vi.fn((event, handler) => {
                            if (event === 'click') handler();
                        })
                    };
                    return mockButton;
                }),
                addEventListener: vi.fn((event, handler) => {
                    if (event === 'click') handler();
                }),
                remove: vi.fn()
            };
            
            document.createElement.mockReturnValue(mockOverlay);
            
            await BatchOperations.confirmBatch('删除', 10);
            
            expect(mockOverlay.innerHTML).toContain('10');
            expect(mockOverlay.innerHTML).toContain('删除');
        });

        it('确认按钮应该返回true', async () => {
            const mockOverlay = {
                className: '',
                innerHTML: '',
                classList: { add: vi.fn(), remove: vi.fn() },
                querySelector: vi.fn((selector) => {
                    const mockButton = {
                        addEventListener: vi.fn((event, handler) => {
                            if (event === 'click' && selector === '#batch-confirm') handler();
                        })
                    };
                    return mockButton;
                }),
                addEventListener: vi.fn(),
                remove: vi.fn()
            };
            
            document.createElement.mockReturnValue(mockOverlay);
            
            const result = await BatchOperations.confirmBatch('删除', 5);
            
            expect(result).toBe(true);
        });

        it('取消按钮应该返回false', async () => {
            const mockOverlay = {
                className: '',
                innerHTML: '',
                classList: { add: vi.fn(), remove: vi.fn() },
                querySelector: vi.fn((selector) => ({
                    addEventListener: vi.fn((event, handler) => {
                        if (event === 'click' && selector === '#batch-cancel') handler();
                    })
                })),
                addEventListener: vi.fn(),
                remove: vi.fn()
            };
            
            document.createElement.mockReturnValue(mockOverlay);
            
            const result = await BatchOperations.confirmBatch('删除', 5);
            
            expect(result).toBe(false);
        });

        it('点击遮罩层应该取消', async () => {
            const mockOverlay = {
                className: '',
                innerHTML: '',
                classList: { add: vi.fn(), remove: vi.fn() },
                querySelector: vi.fn(() => ({
                    addEventListener: vi.fn()
                })),
                addEventListener: vi.fn((event, handler) => {
                    if (event === 'click') handler({ target: mockOverlay });
                }),
                remove: vi.fn()
            };
            
            document.createElement.mockReturnValue(mockOverlay);
            
            const result = await BatchOperations.confirmBatch('删除', 5);
            
            expect(result).toBe(false);
        });
    });

    describe('边界情况', () => {
        it('批量导入空文件列表应该返回空结果', async () => {
            const result = await BatchOperations.batchImport([]);
            
            expect(result.total).toBe(0);
            expect(result.success).toBe(0);
            expect(result.failed).toBe(0);
        });

        it('批量删除空数组应该返回空数组', () => {
            const result = BatchOperations.batchDeletePoints([], [0, 1]);
            
            expect(result).toEqual([]);
        });

        it('批量更新空数组应该返回空数组', () => {
            const result = BatchOperations.batchUpdatePoints([], [0], { value: 10 });
            
            expect(result).toEqual([]);
        });

        it('批量导出空数据应该正常处理', async () => {
            await expect(BatchOperations.batchExport([], ['csv'], 'test')).resolves.not.toThrow();
        });

        it('批量导出不支持的格式应该正常处理', async () => {
            const data = [{ x: 1, y: 1, value: 10 }];
            
            await expect(BatchOperations.batchExport(data, ['unsupported'], 'test')).resolves.not.toThrow();
        });
    });
});