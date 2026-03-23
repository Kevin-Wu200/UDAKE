import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { PerformanceMonitor, performanceMonitor } from '../apps/frontend/js/utils/PerformanceMonitor';

// Mock performance API
const mockPerformance = {
    now: vi.fn(() => Date.now()),
    mark: vi.fn(),
    measure: vi.fn(),
    clearMarks: vi.fn(),
    clearMeasures: vi.fn(),
    getEntries: vi.fn(() => []),
    getEntriesByType: vi.fn(() => []),
    getEntriesByName: vi.fn(() => []),
    memory: {
        usedJSHeapSize: 50 * 1024 * 1024,
        totalJSHeapSize: 100 * 1024 * 1024,
        jsHeapSizeLimit: 200 * 1024 * 1024
    }
};

// Mock PerformanceObserver
class MockPerformanceObserver {
    constructor(private callback: (list: any) => void) {}
    observe(options: any) {}
    disconnect() {}
}

vi.stubGlobal('performance', mockPerformance);
vi.stubGlobal('PerformanceObserver', MockPerformanceObserver);

describe('PerformanceMonitor', () => {
    let monitor: PerformanceMonitor;

    beforeEach(() => {
        monitor = new PerformanceMonitor();
        mockPerformance.now.mockClear();
        mockPerformance.mark.mockClear();
        mockPerformance.measure.mockClear();
        mockPerformance.getEntries.mockClear();
        mockPerformance.getEntriesByType.mockClear();
        mockPerformance.getEntriesByName.mockClear();
    });

    afterEach(() => {
        monitor.destroy();
    });

    describe('初始化', () => {
        it('应该成功初始化', () => {
            expect(monitor).toBeDefined();
        });

        it('应该能够导出单例', () => {
            expect(performanceMonitor).toBeDefined();
            expect(performanceMonitor).toBeInstanceOf(PerformanceMonitor);
        });
    });

    describe('记录指标', () => {
        it('应该能够记录性能指标', () => {
            monitor.recordMetric('test-metric', 100);

            const stats = monitor.getStats('test-metric');
            expect(stats).toBeDefined();
            expect(stats!.count).toBe(1);
            expect(stats!.total).toBe(100);
            expect(stats!.average).toBe(100);
        });

        it('应该能够记录带元数据的指标', () => {
            monitor.recordMetric('test-metric', 100, { key: 'value' });

            const metrics = monitor.exportMetrics();
            const metric = metrics.find(m => m.name === 'test-metric');
            expect(metric).toBeDefined();
            expect(metric!.metadata).toEqual({ key: 'value' });
        });

        it('应该限制每个指标的最大数量', () => {
            const maxMetrics = 1000;

            for (let i = 0; i < maxMetrics + 100; i++) {
                monitor.recordMetric('test-metric', i);
            }

            const stats = monitor.getStats('test-metric');
            expect(stats!.count).toBeLessThanOrEqual(maxMetrics);
        });
    });

    describe('测量功能', () => {
        it('应该能够开始和停止测量', () => {
            mockPerformance.now.mockReturnValueOnce(0).mockReturnValueOnce(100);

            const stopMeasure = monitor.startMeasure('test-measure');
            stopMeasure();

            const stats = monitor.getStats('test-measure');
            expect(stats).toBeDefined();
            expect(stats!.count).toBe(1);
            expect(stats!.total).toBe(100);
        });

        it('应该能够测量同步函数', () => {
            mockPerformance.now.mockReturnValueOnce(0).mockReturnValueOnce(50);

            const stopMeasure = monitor.startMeasure('sync-operation');
            // 执行一些操作
            const result = 1 + 1;
            stopMeasure();

            expect(result).toBe(2);
            const stats = monitor.getStats('sync-operation');
            expect(stats!.count).toBe(1);
        });

        it('应该能够测量异步函数', async () => {
            mockPerformance.now.mockReturnValueOnce(0).mockReturnValueOnce(200);

            const result = await monitor.measureAsync('async-operation', async () => {
                await new Promise(resolve => setTimeout(resolve, 10));
                return 'async-result';
            });

            expect(result).toBe('async-result');
            const stats = monitor.getStats('async-operation');
            expect(stats).toBeDefined();
            expect(stats!.count).toBe(1);
        });

        it('应该在异步函数抛出错误时仍然记录时间', async () => {
            mockPerformance.now.mockReturnValueOnce(0).mockReturnValueOnce(100);

            await expect(
                monitor.measureAsync('failing-operation', async () => {
                    throw new Error('Test error');
                })
            ).rejects.toThrow('Test error');

            const stats = monitor.getStats('failing-operation');
            expect(stats).toBeDefined();
            expect(stats!.count).toBe(1);
        });
    });

    describe('统计信息', () => {
        it('应该能够计算基本统计信息', () => {
            monitor.recordMetric('stats-test', 100);
            monitor.recordMetric('stats-test', 200);
            monitor.recordMetric('stats-test', 300);

            const stats = monitor.getStats('stats-test');
            expect(stats).toBeDefined();
            expect(stats!.count).toBe(3);
            expect(stats!.total).toBe(600);
            expect(stats!.average).toBe(200);
            expect(stats!.min).toBe(100);
            expect(stats!.max).toBe(300);
        });

        it('应该能够计算百分位数', () => {
            // 创建 100 个数据点
            for (let i = 1; i <= 100; i++) {
                monitor.recordMetric('percentile-test', i);
            }

            const stats = monitor.getStats('percentile-test');
            expect(stats).toBeDefined();
            expect(stats!.p50).toBe(50);
            expect(stats!.p95).toBe(95);
            expect(stats!.p99).toBe(99);
        });

        it('应该能够获取所有指标的统计信息', () => {
            monitor.recordMetric('metric-1', 100);
            monitor.recordMetric('metric-2', 200);
            monitor.recordMetric('metric-1', 150);

            const allStats = monitor.getAllStats();
            expect(allStats.size).toBe(2);
            expect(allStats.has('metric-1')).toBe(true);
            expect(allStats.has('metric-2')).toBe(true);
        });

        it('应该为不存在的指标返回 null', () => {
            const stats = monitor.getStats('non-existent');
            expect(stats).toBeNull();
        });
    });

    describe('Core Web Vitals', () => {
        it('应该能够获取 LCP', () => {
            const lcpEntry = { startTime: 1500 };
            mockPerformance.getEntriesByType.mockReturnValueOnce([lcpEntry]);

            const vitals = monitor.getWebVitals();
            expect(vitals.lcp).toBe(1500);
        });

        it('应该能够获取 FID', () => {
            const fidEntry = { startTime: 100, processingStart: 150 };
            mockPerformance.getEntriesByType.mockReturnValueOnce([]).mockReturnValueOnce([fidEntry]);

            const vitals = monitor.getWebVitals();
            expect(vitals.fid).toBe(50);
        });

        it('应该能够获取 CLS', () => {
            const clsEntries = [
                { entryType: 'layout-shift', value: 0.05, hadRecentInput: false },
                { entryType: 'layout-shift', value: 0.03, hadRecentInput: false },
                { entryType: 'layout-shift', value: 0.1, hadRecentInput: true }
            ];
            mockPerformance.getEntries.mockReturnValueOnce(clsEntries);

            const vitals = monitor.getWebVitals();
            expect(vitals.cls).toBeCloseTo(0.08, 2);
        });

        it('应该能够获取 FCP', () => {
            const fcpEntry = { startTime: 800 };
            mockPerformance.getEntriesByName.mockReturnValueOnce([fcpEntry]);

            const vitals = monitor.getWebVitals();
            expect(vitals.fcp).toBe(800);
        });

        it('应该能够获取 TTFB', () => {
            const navEntry = {
                requestStart: 100,
                responseStart: 300
            };
            mockPerformance.getEntriesByType.mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([navEntry]);

            const vitals = monitor.getWebVitals();
            expect(vitals.ttfb).toBe(200);
        });
    });

    describe('内存使用', () => {
        it('应该能够获取内存使用情况', () => {
            const memory = monitor.getMemoryUsage();
            expect(memory).toBeDefined();
            expect(memory!.usedJSHeapSize).toBeGreaterThan(0);
            expect(memory!.totalJSHeapSize).toBeGreaterThan(0);
            expect(memory!.jsHeapSizeLimit).toBeGreaterThan(0);
            expect(memory!.usagePercent).toBeGreaterThan(0);
        });

        it('应该正确计算内存使用率', () => {
            const memory = monitor.getMemoryUsage();
            const expectedPercent = (mockPerformance.memory.usedJSHeapSize / mockPerformance.memory.jsHeapSizeLimit) * 100;
            expect(memory!.usagePercent).toBe(expectedPercent);
        });
    });

    describe('资源统计', () => {
        it('应该能够获取资源统计', () => {
            const resources = [
                { initiatorType: 'script', transferSize: 102400 },
                { initiatorType: 'stylesheet', transferSize: 51200 },
                { initiatorType: 'script', transferSize: 0 } // 缓存
            ];
            mockPerformance.getEntriesByType.mockReturnValueOnce(resources);

            const stats = monitor.getResourceStats();
            expect(stats.totalResources).toBe(3);
            expect(stats.totalSize).toBe(153600);
            expect(stats.cachedResources).toBe(1);
            expect(stats.resourcesByType.size).toBe(2);
        });

        it('应该按类型分组资源', () => {
            const resources = [
                { initiatorType: 'script', transferSize: 102400 },
                { initiatorType: 'stylesheet', transferSize: 51200 },
                { initiatorType: 'script', transferSize: 204800 }
            ];
            mockPerformance.getEntriesByType.mockReturnValueOnce(resources);

            const stats = monitor.getResourceStats();
            const scriptStats = stats.resourcesByType.get('script');
            const styleStats = stats.resourcesByType.get('stylesheet');

            expect(scriptStats).toBeDefined();
            expect(scriptStats!.count).toBe(2);
            expect(scriptStats!.size).toBe(307200);

            expect(styleStats).toBeDefined();
            expect(styleStats!.count).toBe(1);
            expect(styleStats!.size).toBe(51200);
        });
    });

    describe('报告生成', () => {
        it('应该能够生成文本报告', () => {
            monitor.recordMetric('test-metric', 100);

            const report = monitor.generateReport();
            expect(report).toContain('=== 性能监控报告 ===');
            expect(report).toContain('Core Web Vitals');
            expect(report).toContain('test-metric');
        });

        it('应该能够生成 JSON 报告', () => {
            monitor.recordMetric('test-metric', 100);

            const report = monitor.generateJSONReport();
            expect(report).toHaveProperty('timestamp');
            expect(report).toHaveProperty('webVitals');
            expect(report).toHaveProperty('memory');
            expect(report).toHaveProperty('resources');
            expect(report).toHaveProperty('metrics');
        });

        it('应该能够导出所有指标', () => {
            monitor.recordMetric('metric-1', 100, { key: 'value1' });
            monitor.recordMetric('metric-2', 200, { key: 'value2' });

            const metrics = monitor.exportMetrics();
            expect(metrics).toHaveLength(2);
            expect(metrics[0]).toHaveProperty('name');
            expect(metrics[0]).toHaveProperty('duration');
            expect(metrics[0]).toHaveProperty('timestamp');
        });
    });

    describe('性能检查', () => {
        it('应该通过性能检查当所有指标都正常', () => {
            mockPerformance.getEntriesByName.mockReturnValueOnce([{ startTime: 1000 }]); // FCP
            mockPerformance.getEntriesByType.mockReturnValueOnce([{ startTime: 2000 }]) // LCP
                .mockReturnValueOnce([{ startTime: 100, processingStart: 150 }]); // FID

            const result = monitor.checkPerformanceThresholds();
            expect(result.passed).toBe(true);
            expect(result.issues).toHaveLength(0);
        });

        it('应该检测 LCP 过高', () => {
            mockPerformance.getEntriesByName.mockReturnValueOnce([{ startTime: 1000 }]); // FCP
            mockPerformance.getEntriesByType.mockReturnValueOnce([{ startTime: 3000 }]); // LCP

            const result = monitor.checkPerformanceThresholds();
            expect(result.passed).toBe(false);
            expect(result.issues.some(issue => issue.includes('LCP'))).toBe(true);
        });

        it('应该检测 FID 过高', () => {
            mockPerformance.getEntriesByName.mockReturnValueOnce([{ startTime: 1000 }]); // FCP
            mockPerformance.getEntriesByType.mockReturnValueOnce([]) // LCP
                .mockReturnValueOnce([{ startTime: 100, processingStart: 250 }]); // FID

            const result = monitor.checkPerformanceThresholds();
            expect(result.passed).toBe(false);
            expect(result.issues.some(issue => issue.includes('FID'))).toBe(true);
        });

        it('应该检测 CLS 过高', () => {
            mockPerformance.getEntriesByName.mockReturnValueOnce([{ startTime: 1000 }]); // FCP
            mockPerformance.getEntriesByType.mockReturnValueOnce([]) // LCP
                .mockReturnValueOnce([]); // FID
            mockPerformance.getEntries.mockReturnValueOnce([
                { entryType: 'layout-shift', value: 0.15, hadRecentInput: false }
            ]);

            const result = monitor.checkPerformanceThresholds();
            expect(result.passed).toBe(false);
            expect(result.issues.some(issue => issue.includes('CLS'))).toBe(true);
        });

        it('应该检测内存使用率过高', () => {
            mockPerformance.memory.usedJSHeapSize = 180 * 1024 * 1024; // 180MB
            mockPerformance.memory.jsHeapSizeLimit = 200 * 1024 * 1024; // 200MB

            const result = monitor.checkPerformanceThresholds();
            expect(result.passed).toBe(false);
            expect(result.issues.some(issue => issue.includes('内存使用率'))).toBe(true);
        });
    });

    describe('行为追踪与基线', () => {
        it('应支持记录用户行为', () => {
            monitor.trackUserAction('switch-map', { provider: 'amap' });
            const stats = monitor.getStats('user-action:switch-map');
            expect(stats).toBeTruthy();
            expect(stats!.count).toBe(1);
        });

        it('应支持基线对比并识别回归', () => {
            monitor.setBaseline('api-request', 100);
            monitor.recordMetric('api-request', 150);
            monitor.recordMetric('api-request', 170);

            const comparison = monitor.compareWithBaseline('api-request');
            expect(comparison.hasBaseline).toBe(true);
            expect(comparison.regression).toBe(true);
            expect(comparison.deltaPercent).toBeGreaterThan(15);
        });
    });

    describe('清理功能', () => {
        it('应该能够清除所有指标', () => {
            monitor.recordMetric('metric-1', 100);
            monitor.recordMetric('metric-2', 200);

            monitor.clear();

            const allStats = monitor.getAllStats();
            expect(allStats.size).toBe(0);
        });

        it('应该能够清除指定指标的统计数据', () => {
            monitor.recordMetric('metric-1', 100);
            monitor.recordMetric('metric-2', 200);

            monitor.clearMetric('metric-1');

            const stats = monitor.getStats('metric-1');
            expect(stats).toBeNull();
        });

        it('应该能够销毁监控器', () => {
            monitor.recordMetric('test', 100);

            monitor.destroy();

            const stats = monitor.getAllStats();
            expect(stats.size).toBe(0);
        });
    });
});
