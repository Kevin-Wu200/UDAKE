/**
 * 性能监控工具
 * 收集页面加载、资源加载、交互性能指标
 */

interface LongTaskEntry {
    duration: number;
    startTime: number;
}

interface PerformanceMetrics {
    [key: string]: number | LongTaskEntry[] | undefined;
    longTasks?: LongTaskEntry[];
    lcp?: number;
    fid?: number;
    cls?: number;
    domContentLoaded?: number;
    loadComplete?: number;
    ttfb?: number;
    domInteractive?: number;
    resourceCount?: number;
    totalTransferSize?: number;
}

export class PerformanceMonitor {
    static _metrics: PerformanceMetrics = {};
    static _marks: Record<string, number> = {};

    static init(): void {
        if (document.readyState === 'complete') {
            PerformanceMonitor._collectNavigationMetrics();
        } else {
            window.addEventListener('load', () => {
                PerformanceMonitor._collectNavigationMetrics();
            });
        }

        if ('PerformanceObserver' in window) {
            try {
                const longTaskObserver = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        PerformanceMonitor._metrics.longTasks = PerformanceMonitor._metrics.longTasks || [];
                        PerformanceMonitor._metrics.longTasks.push({
                            duration: entry.duration,
                            startTime: entry.startTime
                        });
                    }
                });
                longTaskObserver.observe({ entryTypes: ['longtask'] });
            } catch {
                // longtask not supported
            }

            try {
                const lcpObserver = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    if (entries.length > 0) {
                        PerformanceMonitor._metrics.lcp = entries[entries.length - 1].startTime;
                    }
                });
                lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });
            } catch {
                // LCP not supported
            }

            try {
                const fidObserver = new PerformanceObserver((list) => {
                    const entries = list.getEntries() as PerformanceEventTiming[];
                    if (entries.length > 0) {
                        PerformanceMonitor._metrics.fid = entries[0].processingStart - entries[0].startTime;
                    }
                });
                fidObserver.observe({ entryTypes: ['first-input'] });
            } catch {
                // FID not supported
            }

            try {
                let clsValue = 0;
                const clsObserver = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries() as any[]) {
                        if (!entry.hadRecentInput) {
                            clsValue += entry.value;
                        }
                    }
                    PerformanceMonitor._metrics.cls = clsValue;
                });
                clsObserver.observe({ entryTypes: ['layout-shift'] });
            } catch {
                // CLS not supported
            }
        }
    }

    static mark(name: string): void {
        PerformanceMonitor._marks[name] = performance.now();
    }

    static measure(name: string, startMark: string, endMark?: string): number | null {
        const start = PerformanceMonitor._marks[startMark];
        const end = endMark ? PerformanceMonitor._marks[endMark] : performance.now();
        if (start !== undefined) {
            const duration = end - start;
            PerformanceMonitor._metrics[name] = duration;
            return duration;
        }
        return null;
    }

    static getMetrics(): PerformanceMetrics {
        return { ...PerformanceMonitor._metrics };
    }

    static report(): void {
        const metrics = PerformanceMonitor.getMetrics();
        console.group('Performance Report');
        for (const [key, value] of Object.entries(metrics)) {
            if (typeof value === 'number') {
                console.log(`${key}: ${value.toFixed(2)}ms`);
            } else {
                console.log(`${key}:`, value);
            }
        }
        console.groupEnd();
    }

    static _collectNavigationMetrics(): void {
        const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
        if (nav) {
            PerformanceMonitor._metrics.domContentLoaded = nav.domContentLoadedEventEnd - nav.startTime;
            PerformanceMonitor._metrics.loadComplete = nav.loadEventEnd - nav.startTime;
            PerformanceMonitor._metrics.ttfb = nav.responseStart - nav.requestStart;
            PerformanceMonitor._metrics.domInteractive = nav.domInteractive - nav.startTime;
        }

        const resources = performance.getEntriesByType('resource') as PerformanceResourceTiming[];
        PerformanceMonitor._metrics.resourceCount = resources.length;
        PerformanceMonitor._metrics.totalTransferSize = resources.reduce((sum, r) => sum + (r.transferSize || 0), 0);
    }
}
