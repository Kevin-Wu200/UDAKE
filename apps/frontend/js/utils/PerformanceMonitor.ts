/**
 * 性能监控模块
 * 用于监控应用性能指标，包括 Core Web Vitals、自定义指标、内存使用等
 */
import { AppConfig } from '../config/AppConfig';

export interface PerformanceMetric {
    name: string;
    duration: number;
    timestamp: number;
    metadata?: any;
}

export interface PerformanceStats {
    count: number;
    total: number;
    average: number;
    min: number;
    max: number;
    p50: number;
    p95: number;
    p99: number;
}

export interface WebVitals {
    lcp?: number; // Largest Contentful Paint
    fid?: number; // First Input Delay
    cls?: number; // Cumulative Layout Shift
    fcp?: number; // First Contentful Paint
    ttfb?: number; // Time to First Byte
}

export interface MemoryUsage {
    usedJSHeapSize: number;
    totalJSHeapSize: number;
    jsHeapSizeLimit: number;
    usagePercent: number;
}

export interface BaselineComparison {
    hasBaseline: boolean;
    baseline?: number;
    current?: number;
    deltaPercent?: number;
    regression: boolean;
}

export class PerformanceMonitor {
    private metrics: Map<string, PerformanceMetric[]> = new Map();
    private observers: PerformanceObserver[] = [];
    private maxMetricsPerName: number = 1000;
    private initialized: boolean = false;
    private baseline: Map<string, number> = new Map();
    private behaviorHandlersBound = false;

    constructor() {
        this.initialize();
    }

    /**
     * 初始化性能监控
     */
    private initialize(): void {
        if (this.initialized) {
            return;
        }

        if (typeof window === 'undefined' || typeof performance === 'undefined') {
            console.warn('[PerformanceMonitor] Performance API not available');
            return;
        }

        try {
            this.initializeObservers();
            if (AppConfig.features.enableBehaviorTracking) {
                this.setupBehaviorTracking();
            }
            this.initialized = true;
            console.log('[PerformanceMonitor] Initialized successfully');
        } catch (error) {
            console.error('[PerformanceMonitor] Initialization failed:', error);
        }
    }

    /**
     * 初始化性能观察器
     */
    private initializeObservers(): void {
        // 监控资源加载
        try {
            const resourceObserver = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (entry.entryType === 'resource') {
                        const resourceEntry = entry as PerformanceResourceTiming;
                        this.recordMetric('resource-load', resourceEntry.duration, {
                            name: resourceEntry.name,
                            type: resourceEntry.initiatorType,
                            size: resourceEntry.transferSize,
                            cached: resourceEntry.transferSize === 0
                        });
                    }
                }
            });
            resourceObserver.observe({ entryTypes: ['resource'] });
            this.observers.push(resourceObserver);
        } catch (error) {
            console.warn('[PerformanceMonitor] Resource observer not supported');
        }

        // 监控长任务
        try {
            const longTaskObserver = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (entry.entryType === 'longtask') {
                        this.recordMetric('long-task', entry.duration, {
                            name: entry.name,
                            startTime: entry.startTime
                        });
                    }
                }
            });
            longTaskObserver.observe({ entryTypes: ['longtask'] });
            this.observers.push(longTaskObserver);
        } catch (error) {
            console.warn('[PerformanceMonitor] Long task observer not supported');
        }

        // 监控测量
        try {
            const measureObserver = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (entry.entryType === 'measure') {
                        this.recordMetric(entry.name, entry.duration);
                    }
                }
            });
            measureObserver.observe({ entryTypes: ['measure'] });
            this.observers.push(measureObserver);
        } catch (error) {
            console.warn('[PerformanceMonitor] Measure observer not supported');
        }

        // 监控导航
        try {
            const navigationObserver = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (entry.entryType === 'navigation') {
                        const navEntry = entry as PerformanceNavigationTiming;
                        this.recordMetric('navigation', navEntry.duration, {
                            domContentLoaded: navEntry.domContentLoadedEventEnd - navEntry.domContentLoadedEventStart,
                            loadComplete: navEntry.loadEventEnd - navEntry.loadEventStart,
                            domInteractive: navEntry.domInteractive - navEntry.fetchStart,
                            firstPaint: navEntry.responseEnd - navEntry.fetchStart
                        });
                    }
                }
            });
            navigationObserver.observe({ entryTypes: ['navigation'] });
            this.observers.push(navigationObserver);
        } catch (error) {
            console.warn('[PerformanceMonitor] Navigation observer not supported');
        }
    }

    /**
     * 追踪基础用户行为（点击、输入、页面可见性）
     */
    private setupBehaviorTracking(): void {
        if (this.behaviorHandlersBound || typeof window === 'undefined' || typeof document === 'undefined') {
            return;
        }

        this.behaviorHandlersBound = true;

        const clickHandler = (event: Event) => {
            const target = event.target as HTMLElement | null;
            const tagName = target?.tagName || 'unknown';
            const id = target?.id || '';
            this.recordMetric('user-click', 1, { tagName, id });
        };

        const inputHandler = (event: Event) => {
            const target = event.target as HTMLElement | null;
            this.recordMetric('user-input', 1, {
                tagName: target?.tagName || 'unknown',
                id: target?.id || ''
            });
        };

        const visibilityHandler = () => {
            this.recordMetric('visibility-change', 1, {
                state: document.visibilityState
            });
        };

        window.addEventListener('click', clickHandler, { passive: true });
        window.addEventListener('input', inputHandler, { passive: true });
        document.addEventListener('visibilitychange', visibilityHandler, { passive: true });
    }

    /**
     * 记录性能指标
     */
    public recordMetric(name: string, duration: number, metadata?: any): void {
        const metric: PerformanceMetric = {
            name,
            duration,
            timestamp: Date.now(),
            metadata
        };

        if (!this.metrics.has(name)) {
            this.metrics.set(name, []);
        }

        const metrics = this.metrics.get(name)!;
        metrics.push(metric);

        // 限制保留的指标数量
        if (metrics.length > this.maxMetricsPerName) {
            metrics.splice(0, metrics.length - this.maxMetricsPerName);
        }
    }

    /**
     * 开始测量
     * 返回一个停止测量的函数
     */
    public startMeasure(name: string): () => void {
        const startTime = performance.now();
        const startMark = `${name}-start-${Date.now()}`;

        try {
            performance.mark(startMark);
        } catch (error) {
            // 如果 performance.mark 不可用，只使用时间戳
        }

        return () => {
            const endTime = performance.now();
            const endMark = `${name}-end-${Date.now()}`;

            try {
                performance.mark(endMark);
                performance.measure(name, startMark, endMark);

                // 清理标记和测量
                performance.clearMarks(startMark);
                performance.clearMarks(endMark);
                performance.clearMeasures(name);
            } catch (error) {
                // 如果 performance API 不可用，使用时间差
            }

            this.recordMetric(name, endTime - startTime);
        };
    }

    /**
     * 测量异步函数的性能
     */
    public async measureAsync<T>(name: string, fn: () => Promise<T>): Promise<T> {
        const stopMeasure = this.startMeasure(name);

        try {
            return await fn();
        } finally {
            stopMeasure();
        }
    }

    /**
     * 获取指定指标的统计信息
     */
    public getStats(name: string): PerformanceStats | null {
        const metrics = this.metrics.get(name);
        if (!metrics || metrics.length === 0) {
            return null;
        }

        const durations = metrics.map(m => m.duration).sort((a, b) => a - b);
        const total = durations.reduce((sum, d) => sum + d, 0);
        const percentile = (p: number): number => {
            const index = Math.floor((durations.length - 1) * p);
            return durations[index];
        };

        return {
            count: durations.length,
            total,
            average: total / durations.length,
            min: durations[0],
            max: durations[durations.length - 1],
            p50: percentile(0.5),
            p95: percentile(0.95),
            p99: percentile(0.99)
        };
    }

    /**
     * 记录一次用户行为（业务层可主动调用）
     */
    public trackUserAction(action: string, metadata?: Record<string, unknown>): void {
        this.recordMetric(`user-action:${action}`, 1, metadata);
    }

    /**
     * 设置性能基线（用于回归比较）
     */
    public setBaseline(metricName: string, expectedDuration: number): void {
        if (!Number.isFinite(expectedDuration) || expectedDuration <= 0) {
            return;
        }
        this.baseline.set(metricName, expectedDuration);
    }

    /**
     * 对比当前指标与基线
     */
    public compareWithBaseline(metricName: string): BaselineComparison {
        const baseline = this.baseline.get(metricName);
        const stats = this.getStats(metricName);

        if (baseline === undefined || !stats) {
            return {
                hasBaseline: false,
                regression: false
            };
        }

        const current = stats.average;
        const deltaPercent = ((current - baseline) / baseline) * 100;
        const regression = deltaPercent > 15;

        return {
            hasBaseline: true,
            baseline,
            current,
            deltaPercent,
            regression
        };
    }

    /**
     * 获取所有指标的统计信息
     */
    public getAllStats(): Map<string, PerformanceStats> {
        const stats = new Map<string, PerformanceStats>();

        for (const name of this.metrics.keys()) {
            const stat = this.getStats(name);
            if (stat) {
                stats.set(name, stat);
            }
        }

        return stats;
    }

    /**
     * 获取 Core Web Vitals
     */
    public getWebVitals(): WebVitals {
        const vitals: WebVitals = {};

        // LCP (Largest Contentful Paint)
        const lcpEntries = performance.getEntriesByType('largest-contentful-paint') as any[];
        if (lcpEntries.length > 0) {
            vitals.lcp = lcpEntries[lcpEntries.length - 1].startTime;
        }

        // FID (First Input Delay)
        const fidEntries = performance.getEntriesByType('first-input') as any[];
        if (fidEntries.length > 0) {
            vitals.fid = fidEntries[0].processingStart - fidEntries[0].startTime;
        }

        // CLS (Cumulative Layout Shift)
        let clsValue = 0;
        const layoutShiftEntries = performance.getEntriesByType('layout-shift') as any[];
        const clsEntries = layoutShiftEntries.length > 0
            ? layoutShiftEntries
            : (performance.getEntries() as any[]);
        for (const entry of clsEntries) {
            if (entry.entryType === 'layout-shift' && !entry.hadRecentInput) {
                clsValue += entry.value;
            }
        }
        vitals.cls = clsValue;

        // FCP (First Contentful Paint)
        const paintEntries = performance.getEntriesByType('paint') as any[];
        const fcpEntry = paintEntries.find((entry: any) => entry.name === 'first-contentful-paint')
            || performance.getEntriesByName('first-contentful-paint', 'paint')[0] as any;
        if (fcpEntry) {
            vitals.fcp = fcpEntry.startTime;
        }

        // TTFB (Time to First Byte)
        const navEntry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
        if (navEntry) {
            vitals.ttfb = navEntry.responseStart - navEntry.requestStart;
        }

        return vitals;
    }

    /**
     * 获取内存使用情况
     */
    public getMemoryUsage(): MemoryUsage | null {
        if ('memory' in performance) {
            const memory = (performance as any).memory;
            return {
                usedJSHeapSize: memory.usedJSHeapSize,
                totalJSHeapSize: memory.totalJSHeapSize,
                jsHeapSizeLimit: memory.jsHeapSizeLimit,
                usagePercent: (memory.usedJSHeapSize / memory.jsHeapSizeLimit) * 100
            };
        }
        return null;
    }

    /**
     * 获取资源加载统计
     */
    public getResourceStats(): {
        totalResources: number;
        totalSize: number;
        cachedResources: number;
        resourcesByType: Map<string, { count: number; size: number }>;
    } {
        const resources = performance.getEntriesByType('resource') as PerformanceResourceTiming[];
        const resourcesByType = new Map<string, { count: number; size: number }>();

        let totalSize = 0;
        let cachedResources = 0;

        for (const resource of resources) {
            const type = resource.initiatorType || 'other';
            const size = Number(resource.transferSize) || 0;

            if (!resourcesByType.has(type)) {
                resourcesByType.set(type, { count: 0, size: 0 });
            }

            const stats = resourcesByType.get(type)!;
            stats.count++;
            stats.size += size;

            totalSize += size;
            if (size === 0) {
                cachedResources++;
            }
        }

        return {
            totalResources: resources.length,
            totalSize,
            cachedResources,
            resourcesByType
        };
    }

    /**
     * 清除所有指标
     */
    public clear(): void {
        this.metrics.clear();
    }

    /**
     * 清除指定名称的指标
     */
    public clearMetric(name: string): void {
        this.metrics.delete(name);
    }

    /**
     * 销毁性能监控器
     */
    public destroy(): void {
        this.observers.forEach(observer => observer.disconnect());
        this.observers = [];
        this.clear();
        this.baseline.clear();
        this.initialized = false;
    }

    /**
     * 生成性能报告
     */
    public generateReport(): string {
        const stats = this.getAllStats();
        const vitals = this.getWebVitals();
        const memory = this.getMemoryUsage();
        const resourceStats = this.getResourceStats();

        let report = '=== 性能监控报告 ===\n';
        report += `生成时间: ${new Date().toLocaleString('zh-CN')}\n\n`;

        // Core Web Vitals
        report += '## Core Web Vitals\n';
        report += `- LCP (Largest Contentful Paint): ${vitals.lcp ? vitals.lcp.toFixed(2) + 'ms' : 'N/A'} (建议 < 2.5s)\n`;
        report += `- FID (First Input Delay): ${vitals.fid ? vitals.fid.toFixed(2) + 'ms' : 'N/A'} (建议 < 100ms)\n`;
        report += `- CLS (Cumulative Layout Shift): ${vitals.cls ? vitals.cls.toFixed(4) : 'N/A'} (建议 < 0.1)\n`;
        report += `- FCP (First Contentful Paint): ${vitals.fcp ? vitals.fcp.toFixed(2) + 'ms' : 'N/A'} (建议 < 1.8s)\n`;
        report += `- TTFB (Time to First Byte): ${vitals.ttfb ? vitals.ttfb.toFixed(2) + 'ms' : 'N/A'} (建议 < 600ms)\n\n`;

        // 内存使用
        if (memory) {
            report += '## 内存使用\n';
            report += `- 已使用: ${(memory.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB\n`;
            report += `- 总计: ${(memory.totalJSHeapSize / 1024 / 1024).toFixed(2)} MB\n`;
            report += `- 限制: ${(memory.jsHeapSizeLimit / 1024 / 1024).toFixed(2)} MB\n`;
            report += `- 使用率: ${memory.usagePercent.toFixed(2)}%\n\n`;
        }

        // 资源加载
        report += '## 资源加载\n';
        report += `- 总资源数: ${resourceStats.totalResources}\n`;
        report += `- 总大小: ${(resourceStats.totalSize / 1024).toFixed(2)} KB\n`;
        report += `- 缓存资源: ${resourceStats.cachedResources} (${((resourceStats.cachedResources / resourceStats.totalResources) * 100).toFixed(1)}%)\n`;
        report += `\n### 按类型统计\n`;
        for (const [type, stats] of resourceStats.resourcesByType.entries()) {
            report += `- ${type}: ${stats.count} 个, ${(stats.size / 1024).toFixed(2)} KB\n`;
        }
        report += '\n';

        // 性能指标统计
        report += '## 性能指标统计\n';
        for (const [name, stat] of stats.entries()) {
            report += `\n### ${name}\n`;
            report += `- 计数: ${stat.count}\n`;
            report += `- 总时长: ${stat.total.toFixed(2)}ms\n`;
            report += `- 平均: ${stat.average.toFixed(2)}ms\n`;
            report += `- 最小: ${stat.min.toFixed(2)}ms\n`;
            report += `- 最大: ${stat.max.toFixed(2)}ms\n`;
            report += `- P50: ${stat.p50.toFixed(2)}ms\n`;
            report += `- P95: ${stat.p95.toFixed(2)}ms\n`;
            report += `- P99: ${stat.p99.toFixed(2)}ms\n`;
        }

        return report;
    }

    /**
     * 生成 JSON 格式的报告
     */
    public generateJSONReport(): object {
        const baselineComparisons = Array.from(this.baseline.keys()).reduce((acc, metricName) => {
            acc[metricName] = this.compareWithBaseline(metricName);
            return acc;
        }, {} as Record<string, BaselineComparison>);

        return {
            timestamp: new Date().toISOString(),
            webVitals: this.getWebVitals(),
            memory: this.getMemoryUsage(),
            resources: this.getResourceStats(),
            metrics: Object.fromEntries(this.getAllStats()),
            baselineComparisons
        };
    }

    /**
     * 导出指标数据
     */
    public exportMetrics(): PerformanceMetric[] {
        const allMetrics: PerformanceMetric[] = [];

        for (const metrics of this.metrics.values()) {
            allMetrics.push(...metrics);
        }

        return allMetrics.sort((a, b) => a.timestamp - b.timestamp);
    }

    /**
     * 检查性能是否达标
     */
    public checkPerformanceThresholds(): {
        passed: boolean;
        issues: string[];
    } {
        const issues: string[] = [];
        const vitals = this.getWebVitals();

        // 检查 LCP
        if (vitals.lcp && vitals.lcp > 2500) {
            issues.push(`LCP 过高: ${vitals.lcp.toFixed(2)}ms (建议 < 2.5s)`);
        }

        // 检查 FID
        if (vitals.fid && vitals.fid > 100) {
            issues.push(`FID 过高: ${vitals.fid.toFixed(2)}ms (建议 < 100ms)`);
        }

        // 检查 CLS
        if (vitals.cls && vitals.cls > 0.1) {
            issues.push(`CLS 过高: ${vitals.cls.toFixed(4)} (建议 < 0.1)`);
        }

        // 检查 FCP
        if (vitals.fcp && vitals.fcp > 1800) {
            issues.push(`FCP 过高: ${vitals.fcp.toFixed(2)}ms (建议 < 1.8s)`);
        }

        // 检查 TTFB
        if (vitals.ttfb && vitals.ttfb > 600) {
            issues.push(`TTFB 过高: ${vitals.ttfb.toFixed(2)}ms (建议 < 600ms)`);
        }

        // 检查内存使用
        const memory = this.getMemoryUsage();
        if (memory && memory.usagePercent > 80) {
            issues.push(`内存使用率过高: ${memory.usagePercent.toFixed(2)}% (建议 < 80%)`);
        }

        return {
            passed: issues.length === 0,
            issues
        };
    }

    // 静态方法委托给单例
    private static instance: PerformanceMonitor | null = null;
    public static _metrics: Record<string, any> = {};
    public static _marks: Record<string, number> = {};

    public static init(): void {
        if (!PerformanceMonitor.instance) {
            PerformanceMonitor.instance = new PerformanceMonitor();
        }

        const initializeLegacyMetrics = () => {
            try {
                PerformanceMonitor._collectNavigationMetrics();
            } catch {
                // ignore
            }
        };

        if (typeof document !== 'undefined' && document.readyState === 'loading' && typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
            window.addEventListener('load', initializeLegacyMetrics);
        } else {
            initializeLegacyMetrics();
        }
    }

    public static mark(name: string): void {
        const now = typeof performance !== 'undefined' && typeof performance.now === 'function'
            ? performance.now()
            : Date.now();
        PerformanceMonitor._marks[name] = now;

        if (typeof performance !== 'undefined' && typeof performance.mark === 'function') {
            performance.mark(name);
        }
    }

    public static measure(name: string, startMark: string, endMark?: string): number | null {
        const start = PerformanceMonitor._marks[startMark];
        if (typeof start !== 'number') {
            return null;
        }

        const end = typeof endMark === 'string' && typeof PerformanceMonitor._marks[endMark] === 'number'
            ? PerformanceMonitor._marks[endMark]
            : (typeof performance !== 'undefined' && typeof performance.now === 'function' ? performance.now() : Date.now());
        const duration = end - start;
        PerformanceMonitor._metrics[name] = duration;

        if (typeof performance !== 'undefined' && typeof performance.measure === 'function') {
            try {
                if (endMark) {
                    performance.measure(name, startMark, endMark);
                } else {
                    performance.measure(name, startMark);
                }
            } catch {
                // ignore
            }
        }

        return duration;
    }

    public static getMetrics(): Record<string, any> {
        return { ...PerformanceMonitor._metrics };
    }

    public static report(): void {
        console.group('Performance Report');
        Object.entries(PerformanceMonitor._metrics).forEach(([key, value]) => {
            if (typeof value === 'number' && Number.isFinite(value)) {
                console.log(`${key}: ${value.toFixed(2)}ms`);
            } else {
                console.log(`${key}:`, value);
            }
        });
        console.groupEnd();
    }

    public static _collectNavigationMetrics(): void {
        if (typeof performance === 'undefined' || typeof performance.getEntriesByType !== 'function') {
            return;
        }

        const navEntries = performance.getEntriesByType('navigation') as PerformanceNavigationTiming[];
        const nav = navEntries[0];
        if (nav) {
            PerformanceMonitor._metrics.domContentLoaded = nav.domContentLoadedEventEnd - nav.startTime;
            PerformanceMonitor._metrics.loadComplete = nav.loadEventEnd - nav.startTime;
            PerformanceMonitor._metrics.ttfb = nav.responseStart - nav.requestStart;
            PerformanceMonitor._metrics.domInteractive = nav.domInteractive - nav.startTime;
        }

        const resources = performance.getEntriesByType('resource') as PerformanceResourceTiming[];
        PerformanceMonitor._metrics.resourceCount = resources.length;
        PerformanceMonitor._metrics.totalTransferSize = resources.reduce((sum, entry) => {
            const size = Number((entry as any).transferSize);
            return sum + (Number.isFinite(size) ? size : 0);
        }, 0);
    }
}

// 导出单例
export const performanceMonitor = new PerformanceMonitor();
