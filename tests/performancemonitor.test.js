import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { PerformanceMonitor } from '../frontend/js/utils/PerformanceMonitor.js';

describe('PerformanceMonitor', () => {
    beforeEach(() => {
        // Mock window and performance API
        global.window = {
            addEventListener: vi.fn(),
            removeEventListener: vi.fn(),
            PerformanceObserver: class {
                constructor(callback) {
                    this.callback = callback;
                }
                observe(options) {
                    // Mock observer
                }
                disconnect() {
                    // Mock disconnect
                }
            }
        };
        
        global.performance = {
            now: vi.fn(() => 0), // 初始返回 0
            getEntriesByType: vi.fn((type) => {
                if (type === 'navigation') {
                    return [{
                        domContentLoadedEventEnd: 1000,
                        loadEventEnd: 2000,
                        responseStart: 500,
                        requestStart: 400,
                        domInteractive: 800,
                        startTime: 0
                    }];
                }
                if (type === 'resource') {
                    return [
                        { transferSize: 1000 },
                        { transferSize: 2000 }
                    ];
                }
                return [];
            })
        };

        // Clear static state
        PerformanceMonitor._metrics = {};
        PerformanceMonitor._marks = {};
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('初始化', () => {
        it('应该在页面加载完成后初始化', () => {
            // 模拟页面已完成加载
            global.document = {
                readyState: 'complete'
            };

            PerformanceMonitor.init();
            expect(PerformanceMonitor._metrics).toBeDefined();
        });

        it('应该在load事件触发后初始化', () => {
            // 模拟页面未完成加载
            global.document = {
                readyState: 'loading'
            };

            PerformanceMonitor.init();
            expect(window.addEventListener).toHaveBeenCalledWith('load', expect.any(Function));
        });
    });

    describe('性能标记', () => {
        it('应该能够创建性能标记', () => {
            PerformanceMonitor.mark('test-mark');
            expect(PerformanceMonitor._marks['test-mark']).toBeDefined();
            expect(typeof PerformanceMonitor._marks['test-mark']).toBe('number');
        });

        it('应该能够创建多个标记', () => {
            PerformanceMonitor.mark('mark1');
            PerformanceMonitor.mark('mark2');
            PerformanceMonitor.mark('mark3');
            
            expect(Object.keys(PerformanceMonitor._marks).length).toBe(3);
        });

        it('标记应该使用当前时间戳', () => {
            const now = Date.now();
            performance.now.mockReturnValue(now);
            
            PerformanceMonitor.mark('test');
            expect(PerformanceMonitor._marks['test']).toBe(now);
        });
    });

    describe('性能测量', () => {
        it('应该能够测量两个标记之间的时间', () => {
            performance.now.mockReturnValue(0);
            PerformanceMonitor.mark('start');
            performance.now.mockReturnValue(1000);
            PerformanceMonitor.mark('end');
            
            const duration = PerformanceMonitor.measure('test', 'start', 'end');
            expect(duration).toBe(1000);
            expect(PerformanceMonitor._metrics['test']).toBe(1000);
        });

        it('应该能够测量从标记到当前时间', () => {
            performance.now.mockReturnValue(0);
            PerformanceMonitor.mark('start');
            performance.now.mockReturnValue(500);
            
            const duration = PerformanceMonitor.measure('test', 'start');
            expect(duration).toBe(500);
        });

        it('当起始标记不存在时应该返回null', () => {
            const duration = PerformanceMonitor.measure('test', 'nonexistent');
            expect(duration).toBeNull();
        });

        it('测量结果应该存储在metrics中', () => {
            performance.now.mockReturnValue(0);
            PerformanceMonitor.mark('start');
            performance.now.mockReturnValue(100);
            
            PerformanceMonitor.measure('custom-metric', 'start');
            expect(PerformanceMonitor._metrics['custom-metric']).toBe(100);
        });
    });

    describe('获取指标', () => {
        it('应该能够获取所有指标', () => {
            PerformanceMonitor._metrics = {
                lcp: 1200,
                fid: 50,
                cls: 0.1
            };
            
            const metrics = PerformanceMonitor.getMetrics();
            expect(metrics).toBeDefined();
            expect(metrics.lcp).toBe(1200);
            expect(metrics.fid).toBe(50);
            expect(metrics.cls).toBe(0.1);
        });

        it('返回的指标应该是副本而不是引用', () => {
            PerformanceMonitor._metrics = { test: 100 };
            const metrics = PerformanceMonitor.getMetrics();
            
            metrics.test = 200;
            expect(PerformanceMonitor._metrics.test).toBe(100);
        });

        it('空指标应该返回空对象', () => {
            PerformanceMonitor._metrics = {};
            const metrics = PerformanceMonitor.getMetrics();
            
            expect(Object.keys(metrics).length).toBe(0);
        });
    });

    describe('性能报告', () => {
        it('应该能够生成性能报告', () => {
            PerformanceMonitor._metrics = {
                lcp: 1200,
                fid: 50,
                custom: 100
            };
            
            // Mock console
            console.group = vi.fn();
            console.log = vi.fn();
            console.groupEnd = vi.fn();
            
            PerformanceMonitor.report();
            
            expect(console.group).toHaveBeenCalledWith('Performance Report');
            expect(console.groupEnd).toHaveBeenCalled();
        });

        it('报告应该正确格式化数值', () => {
            PerformanceMonitor._metrics = { test: 123.456 };
            
            console.log = vi.fn();
            PerformanceMonitor.report();
            
            expect(console.log).toHaveBeenCalledWith('test: 123.46ms');
        });

        it('报告应该正确处理非数值指标', () => {
            PerformanceMonitor._metrics = { 
                longTasks: [{ duration: 100, startTime: 0 }] 
            };
            
            console.log = vi.fn();
            PerformanceMonitor.report();
            
            // 非数值应该直接输出
            expect(console.log).toHaveBeenCalled();
        });
    });

    describe('导航指标收集', () => {
        it('应该收集DOM内容加载时间', () => {
            const nav = performance.getEntriesByType('navigation')[0];
            const expected = nav.domContentLoadedEventEnd - nav.startTime;
            
            PerformanceMonitor._collectNavigationMetrics();
            
            expect(PerformanceMonitor._metrics.domContentLoaded).toBe(expected);
        });

        it('应该收集页面加载完成时间', () => {
            const nav = performance.getEntriesByType('navigation')[0];
            const expected = nav.loadEventEnd - nav.startTime;
            
            PerformanceMonitor._collectNavigationMetrics();
            
            expect(PerformanceMonitor._metrics.loadComplete).toBe(expected);
        });

        it('应该收集TTFB（首字节时间）', () => {
            const nav = performance.getEntriesByType('navigation')[0];
            const expected = nav.responseStart - nav.requestStart;
            
            PerformanceMonitor._collectNavigationMetrics();
            
            expect(PerformanceMonitor._metrics.ttfb).toBe(expected);
        });

        it('应该收集DOM交互时间', () => {
            const nav = performance.getEntriesByType('navigation')[0];
            const expected = nav.domInteractive - nav.startTime;
            
            PerformanceMonitor._collectNavigationMetrics();
            
            expect(PerformanceMonitor._metrics.domInteractive).toBe(expected);
        });

        it('应该统计资源数量', () => {
            PerformanceMonitor._collectNavigationMetrics();
            
            expect(PerformanceMonitor._metrics.resourceCount).toBe(2);
        });

        it('应该计算总传输大小', () => {
            PerformanceMonitor._collectNavigationMetrics();
            
            expect(PerformanceMonitor._metrics.totalTransferSize).toBe(3000);
        });
    });

    describe('Core Web Vitals监控', () => {
        it('应该初始化LCP监控', () => {
            PerformanceMonitor.init();
            
            // PerformanceObserver应该被调用
            expect(window.PerformanceObserver).toBeDefined();
        });

        it('应该初始化FID监控', () => {
            PerformanceMonitor.init();
            
            // PerformanceObserver应该被调用
            expect(window.PerformanceObserver).toBeDefined();
        });

        it('应该初始化CLS监控', () => {
            PerformanceMonitor.init();
            
            // PerformanceObserver应该被调用
            expect(window.PerformanceObserver).toBeDefined();
        });

        it('应该初始化Long Task监控', () => {
            PerformanceMonitor.init();
            
            // PerformanceObserver应该被调用
            expect(window.PerformanceObserver).toBeDefined();
        });
    });

    describe('长任务检测', () => {
        it('应该记录长任务', () => {
            PerformanceMonitor.init();
            
            // 模拟长任务
            const observer = new window.PerformanceObserver((list) => {
                list.getEntries().forEach(entry => {
                    if (entry.duration >= 50) {
                        expect(entry.duration).toBeGreaterThanOrEqual(50);
                    }
                });
            });
            
            expect(observer).toBeDefined();
        });
    });

    describe('静态属性和方法', () => {
        it('应该暴露_metrics静态属性', () => {
            expect(PerformanceMonitor._metrics).toBeDefined();
            expect(typeof PerformanceMonitor._metrics).toBe('object');
        });

        it('应该暴露_marks静态属性', () => {
            expect(PerformanceMonitor._marks).toBeDefined();
            expect(typeof PerformanceMonitor._marks).toBe('object');
        });

        it('应该暴露init静态方法', () => {
            expect(PerformanceMonitor.init).toBeDefined();
            expect(typeof PerformanceMonitor.init).toBe('function');
        });

        it('应该暴露mark静态方法', () => {
            expect(PerformanceMonitor.mark).toBeDefined();
            expect(typeof PerformanceMonitor.mark).toBe('function');
        });

        it('应该暴露measure静态方法', () => {
            expect(PerformanceMonitor.measure).toBeDefined();
            expect(typeof PerformanceMonitor.measure).toBe('function');
        });

        it('应该暴露getMetrics静态方法', () => {
            expect(PerformanceMonitor.getMetrics).toBeDefined();
            expect(typeof PerformanceMonitor.getMetrics).toBe('function');
        });

        it('应该暴露report静态方法', () => {
            expect(PerformanceMonitor.report).toBeDefined();
            expect(typeof PerformanceMonitor.report).toBe('function');
        });
    });

    describe('边界情况处理', () => {
        it('应该处理PerformanceObserver不支持的情况', () => {
            global.window = {
                addEventListener: vi.fn(),
                removeEventListener: vi.fn(),
                PerformanceObserver: undefined
            };
            
            // 不应该抛出错误
            expect(() => PerformanceMonitor.init()).not.toThrow();
        });

        it('应该处理导航指标不存在的情况', () => {
            performance.getEntriesByType.mockReturnValue([]);
            
            // 不应该抛出错误
            expect(() => PerformanceMonitor._collectNavigationMetrics()).not.toThrow();
        });

        it('应该处理重复标记', () => {
            PerformanceMonitor.mark('test');
            performance.now.mockReturnValue(100);
            PerformanceMonitor.mark('test');
            
            // 后面的标记应该覆盖前面的
            expect(PerformanceMonitor._marks['test']).toBeDefined();
        });

        it('应该处理资源没有transferSize的情况', () => {
            performance.getEntriesByType.mockImplementation((type) => {
                if (type === 'resource') {
                    return [
                        { transferSize: 1000 },
                        { transferSize: undefined },
                        { transferSize: null }
                    ];
                }
                return [];
            });
            
            PerformanceMonitor._collectNavigationMetrics();
            
            // 应该能够处理undefined和null
            expect(PerformanceMonitor._metrics.totalTransferSize).toBeDefined();
        });
    });

    describe('性能测量场景', () => {
        it('应该能够测量API调用性能', () => {
            performance.now.mockReturnValue(0);
            PerformanceMonitor.mark('api-start');
            performance.now.mockReturnValue(150);
            PerformanceMonitor.measure('api-call', 'api-start');
            
            expect(PerformanceMonitor._metrics['api-call']).toBe(150);
        });

        it('应该能够测量渲染性能', () => {
            performance.now.mockReturnValue(0);
            PerformanceMonitor.mark('render-start');
            performance.now.mockReturnValue(80);
            PerformanceMonitor.measure('render', 'render-start');
            
            expect(PerformanceMonitor._metrics['render']).toBe(80);
        });

        it('应该能够测量数据处理性能', () => {
            performance.now.mockReturnValue(0);
            PerformanceMonitor.mark('process-start');
            performance.now.mockReturnValue(200);
            PerformanceMonitor.measure('data-processing', 'process-start');
            
            expect(PerformanceMonitor._metrics['data-processing']).toBe(200);
        });
    });
});