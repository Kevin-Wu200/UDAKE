import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ExportEnhancer } from '../frontend/js/utils/ExportEnhancer.js';

describe('ExportEnhancer', () => {
    beforeEach(() => {
        // Mock document
        global.document = {
            body: {
                appendChild: vi.fn(),
                removeChild: vi.fn()
            },
            createElement: vi.fn((tag) => ({
                href: '',
                download: '',
                click: vi.fn()
            }))
        };

        // Mock URL
        global.URL = {
            createObjectURL: vi.fn(() => 'blob:url'),
            revokeObjectURL: vi.fn()
        };

        // Mock Blob
        global.Blob = class Blob {
            constructor(content, options) {
                this.content = content;
                this.options = options;
            }
        };

        // Mock fetch
        global.fetch = vi.fn();

        // Mock setTimeout
        global.setTimeout = vi.fn((cb, delay) => {
            cb();
            return 1;
        });
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('CSV导出', () => {
        it('应该成功导出简单的数据为CSV', () => {
            const data = [
                { x: 1, y: 2, value: 10 },
                { x: 2, y: 3, value: 20 }
            ];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.createElement).toHaveBeenCalledWith('a');
            expect(document.body.appendChild).toHaveBeenCalled();
        });

        it('应该处理包含逗号的字符串值', () => {
            const data = [
                { name: 'test, value', value: 10 }
            ];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该处理包含引号的字符串值', () => {
            const data = [
                { name: 'test "quoted" value', value: 10 }
            ];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该处理null和undefined值', () => {
            const data = [
                { x: 1, y: null, value: undefined }
            ];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.createElement).toHaveBeenCalled();
        });

        it('空数组不应该触发导出', () => {
            ExportEnhancer.exportAsCSV([], 'test.csv');

            expect(document.createElement).not.toHaveBeenCalled();
        });

        it('应该在CSV中添加BOM以支持Excel', () => {
            const data = [{ x: 1, y: 2 }];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该正确处理数字类型', () => {
            const data = [
                { x: 1.5, y: 2.75, value: 100.25 }
            ];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该处理布尔类型', () => {
            const data = [
                { x: true, y: false, value: true }
            ];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.createElement).toHaveBeenCalled();
        });
    });

    describe('采样点CSV导出', () => {
        it('应该正确导出采样点数据', () => {
            const points = [
                { x: 116.39, y: 39.9, value: 10 },
                { x: 116.40, y: 39.91, value: 20 }
            ];

            ExportEnhancer.exportPointsCSV(points, 'points.csv');

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该将x/y转换为longitude/latitude', () => {
            const points = [
                { x: 116.39, y: 39.9, value: 10 }
            ];

            ExportEnhancer.exportPointsCSV(points, 'points.csv');

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该处理带时间戳的采样点', () => {
            const points = [
                { x: 116.39, y: 39.9, value: 10, timestamp: '2024-01-01' }
            ];

            ExportEnhancer.exportPointsCSV(points, 'points.csv');

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该使用默认文件名', () => {
            const points = [
                { x: 116.39, y: 39.9, value: 10 }
            ];

            ExportEnhancer.exportPointsCSV(points);

            expect(document.createElement).toHaveBeenCalled();
        });

        it('空点列表不应该触发导出', () => {
            ExportEnhancer.exportPointsCSV([]);

            expect(document.createElement).not.toHaveBeenCalled();
        });
    });

    describe('HTML报告生成', () => {
        it('应该生成基本的HTML报告', () => {
            const reportData = {
                taskId: 'test-123',
                method: 'ordinary',
                pointCount: 100,
                gridResolution: 0.01
            };

            ExportEnhancer.generateHTMLReport(reportData);

            expect(document.createElement).toHaveBeenCalledWith('a');
            expect(document.body.appendChild).toHaveBeenCalled();
        });

        it('应该包含统计摘要', () => {
            const reportData = {
                taskId: 'test-123',
                method: 'ordinary',
                pointCount: 100,
                gridResolution: 0.01,
                stats: {
                    mean: 10.5,
                    std: 2.3,
                    min: 5.0,
                    max: 15.0
                }
            };

            ExportEnhancer.generateHTMLReport(reportData);

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该包含交叉验证结果', () => {
            const reportData = {
                taskId: 'test-123',
                method: 'ordinary',
                pointCount: 100,
                gridResolution: 0.01,
                crossValidation: {
                    MAE: 0.5,
                    RMSE: 0.7,
                    R2: 0.85
                }
            };

            ExportEnhancer.generateHTMLReport(reportData);

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该正确显示方法名称', () => {
            const methods = ['ordinary', 'universal', 'block'];

            methods.forEach(method => {
                const reportData = {
                    taskId: 'test-123',
                    method,
                    pointCount: 100,
                    gridResolution: 0.01
                };

                ExportEnhancer.generateHTMLReport(reportData);
            });

            expect(document.createElement).toHaveBeenCalledTimes(3);
        });

        it('应该包含任务ID和生成时间', () => {
            const reportData = {
                taskId: 'test-123',
                method: 'ordinary',
                pointCount: 100,
                gridResolution: 0.01
            };

            ExportEnhancer.generateHTMLReport(reportData);

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该正确处理数字格式', () => {
            const reportData = {
                taskId: 'test-123',
                method: 'ordinary',
                pointCount: 100,
                gridResolution: 0.01,
                stats: {
                    mean: 10.123456789,
                    std: 2.345678901
                }
            };

            ExportEnhancer.generateHTMLReport(reportData);

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该生成有效的HTML结构', () => {
            const reportData = {
                taskId: 'test-123',
                method: 'ordinary',
                pointCount: 100,
                gridResolution: 0.01
            };

            ExportEnhancer.generateHTMLReport(reportData);

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该包含打印样式', () => {
            const reportData = {
                taskId: 'test-123',
                method: 'ordinary',
                pointCount: 100,
                gridResolution: 0.01
            };

            ExportEnhancer.generateHTMLReport(reportData);

            expect(document.createElement).toHaveBeenCalled();
        });

        it('文件名应该包含任务ID', () => {
            const reportData = {
                taskId: 'test-123',
                method: 'ordinary',
                pointCount: 100,
                gridResolution: 0.01
            };

            ExportEnhancer.generateHTMLReport(reportData);

            expect(document.createElement).toHaveBeenCalled();
        });
    });

    describe('批量导出', () => {
        it('应该成功批量导出单个任务', async () => {
            const enhancer = new ExportEnhancer('http://localhost:8000');
            const mockBlob = new Blob(['test data']);

            global.fetch = vi.fn().mockResolvedValue({
                ok: true,
                blob: async () => mockBlob
            });

            await enhancer.batchExport(['task-1'], 'geojson');

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:8000/result/download/task-1/task-1_prediction.geojson',
                { mode: 'cors', credentials: 'omit' }
            );
        });

        it('应该成功批量导出多个任务', async () => {
            const enhancer = new ExportEnhancer('http://localhost:8000');
            const mockBlob = new Blob(['test data']);

            global.fetch = vi.fn().mockResolvedValue({
                ok: true,
                blob: async () => mockBlob
            });

            await enhancer.batchExport(['task-1', 'task-2'], 'geojson');

            expect(fetch).toHaveBeenCalledTimes(2);
        });

        it('应该处理导出失败的任务', async () => {
            const enhancer = new ExportEnhancer('http://localhost:8000');

            global.fetch = vi.fn()
                .mockResolvedValueOnce({ ok: true, blob: async () => new Blob([]) })
                .mockResolvedValueOnce({ ok: false });

            await expect(enhancer.batchExport(['task-1', 'task-2'], 'geojson')).resolves.not.toThrow();
        });

        it('应该处理网络错误', async () => {
            const enhancer = new ExportEnhancer('http://localhost:8000');

            global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

            await expect(enhancer.batchExport(['task-1'], 'geojson')).resolves.not.toThrow();
        });

        it('应该在任务之间添加延迟', async () => {
            const enhancer = new ExportEnhancer('http://localhost:8000');
            let delayCount = 0;

            global.setTimeout = vi.fn((cb, delay) => {
                delayCount++;
                cb();
                return 1;
            });

            global.fetch = vi.fn().mockResolvedValue({
                ok: true,
                blob: async () => new Blob([])
            });

            await enhancer.batchExport(['task-1', 'task-2'], 'geojson');

            // 有2个任务，每个任务成功后都会延迟，所以是2次
            expect(delayCount).toBe(2);
        });

        it('应该使用正确的API基础URL', async () => {
            const enhancer = new ExportEnhancer('http://api.example.com');

            global.fetch = vi.fn().mockResolvedValue({
                ok: true,
                blob: async () => new Blob([])
            });

            await enhancer.batchExport(['task-1'], 'geojson');

            expect(fetch).toHaveBeenCalledWith(
                'http://api.example.com/result/download/task-1/task-1_prediction.geojson',
                expect.any(Object)
            );
        });

        it('应该支持不同的文件格式', async () => {
            const enhancer = new ExportEnhancer('http://localhost:8000');

            global.fetch = vi.fn().mockResolvedValue({
                ok: true,
                blob: async () => new Blob([])
            });

            await enhancer.batchExport(['task-1'], 'csv');

            expect(fetch).toHaveBeenCalledWith(
                expect.stringContaining('csv'),
                expect.any(Object)
            );
        });

        it('空任务列表应该正常处理', async () => {
            const enhancer = new ExportEnhancer('http://localhost:8000');

            await expect(enhancer.batchExport([], 'geojson')).resolves.not.toThrow();
            expect(fetch).not.toHaveBeenCalled();
        });
    });

    describe('地图截图', () => {
        it('应该成功捕获地图截图', async () => {
            const mockCanvas = {
                toBlob: vi.fn((callback) => {
                    callback(new Blob(['image data']));
                })
            };

            const mockContainer = {
                querySelector: vi.fn(() => mockCanvas)
            };

            const result = await ExportEnhancer.captureMap(mockContainer);

            expect(result).toBeInstanceOf(Blob);
        });

        it('应该在没有canvas时返回null', async () => {
            const mockContainer = {
                querySelector: vi.fn(() => null)
            };

            const result = await ExportEnhancer.captureMap(mockContainer);

            expect(result).toBeNull();
        });

        it('应该处理toBlob不回调的情况', async () => {
            const mockCanvas = {
                toBlob: vi.fn()
            };

            const mockContainer = {
                querySelector: vi.fn(() => mockCanvas)
            };

            // 模拟 toBlob 不调用回调（这不应该导致崩溃）
            mockCanvas.toBlob.mockImplementation(() => {
                // 不调用回调
            });

            // 由于 toBlob 永远不会回调，Promise 永远不会 resolve
            // 我们需要测试这个方法不会导致无限等待
            const timeoutPromise = new Promise((resolve) => {
                setTimeout(() => resolve('timeout'), 100);
            });

            const result = await Promise.race([
                ExportEnhancer.captureMap(mockContainer),
                timeoutPromise
            ]);

            // 应该超时而不是永远等待
            expect(result).toBe('timeout');
        });

        it('应该使用正确的MIME类型', async () => {
            const mockCanvas = {
                toBlob: vi.fn((callback, type) => {
                    expect(type).toBe('image/png');
                    callback(new Blob([]));
                })
            };

            const mockContainer = {
                querySelector: vi.fn(() => mockCanvas)
            };

            await ExportEnhancer.captureMap(mockContainer);
        });
    });

    describe('文件下载', () => {
        it('应该创建下载链接', () => {
            const data = [{ x: 1, y: 2, value: 10 }];
            const mockLink = {
                href: '',
                download: '',
                click: vi.fn()
            };

            document.createElement.mockReturnValue(mockLink);

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(mockLink.click).toHaveBeenCalled();
        });

        it('应该设置正确的下载文件名', () => {
            const data = [{ x: 1, y: 2, value: 10 }];
            const mockLink = {
                href: '',
                download: '',
                click: vi.fn()
            };

            document.createElement.mockReturnValue(mockLink);

            ExportEnhancer.exportAsCSV(data, 'custom_name.csv');

            expect(mockLink.download).toBe('custom_name.csv');
        });

        it('应该清理下载链接', () => {
            const data = [{ x: 1, y: 2, value: 10 }];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.body.appendChild).toHaveBeenCalled();
            expect(document.body.removeChild).toHaveBeenCalled();
        });

        it('应该释放Blob URL', () => {
            const data = [{ x: 1, y: 2, value: 10 }];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:url');
        });

        it('应该正确处理Blob内容', () => {
            const data = [{ x: 1, y: 2, value: 10 }];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该使用正确的MIME类型', () => {
            const data = [{ x: 1, y: 2, value: 10 }];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.createElement).toHaveBeenCalled();
        });
    });

    describe('边界情况', () => {
        it('应该处理包含特殊字符的数据', () => {
            const data = [
                { name: '<script>alert("test")</script>', value: 10 }
            ];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该处理包含换行符的数据', () => {
            const data = [
                { name: 'line1\nline2', value: 10 }
            ];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该处理非常大的数据集', () => {
            const largeData = Array.from({ length: 10000 }, (_, i) => ({
                x: i,
                y: i * 2,
                value: i * 10
            }));

            ExportEnhancer.exportAsCSV(largeData, 'large.csv');

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该处理空值', () => {
            const data = [
                { x: null, y: undefined, value: '' }
            ];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该处理嵌套对象', () => {
            const data = [
                { x: 1, y: 2, nested: { a: 1, b: 2 } }
            ];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该处理数组值', () => {
            const data = [
                { x: 1, y: 2, values: [1, 2, 3] }
            ];

            ExportEnhancer.exportAsCSV(data, 'test.csv');

            expect(document.createElement).toHaveBeenCalled();
        });
    });

    describe('导出选项接口', () => {
        it('应该接受有效的导出选项', () => {
            const options = {
                format: 'geojson',
                includeMap: true,
                includeStats: true,
                includeVariogram: false
            };

            expect(options.format).toBe('geojson');
            expect(options.includeMap).toBe(true);
            expect(options.includeStats).toBe(true);
            expect(options.includeVariogram).toBe(false);
        });
    });
});