/**
 * 性能基准测试脚本
 * 用于监控应用的性能指标，包括 LCP、FID、CLS 等
 */

// 性能指标收集
class PerformanceBenchmark {
    constructor() {
        this.metrics = {};
        this.observers = {};
    }

    /**
     * 初始化性能监控
     */
    init() {
        if (!('performance' in window) || !('PerformanceObserver' in window)) {
            console.warn('Performance API not supported');
            return;
        }

        this.measureNavigationTiming();
        this.observeLCP();
        this.observeFID();
        this.observeCLS();
        this.observeFCP();
        this.observeTTFB();

        // 5秒后输出所有指标
        setTimeout(() => this.report(), 5000);
    }

    /**
     * 测量导航时间
     */
    measureNavigationTiming() {
        const navigation = performance.getEntriesByType('navigation')[0];
        if (navigation) {
            this.metrics.navigation = {
                dns: navigation.domainLookupEnd - navigation.domainLookupStart,
                tcp: navigation.connectEnd - navigation.connectStart,
                request: navigation.responseStart - navigation.requestStart,
                response: navigation.responseEnd - navigation.responseStart,
                domProcessing: navigation.domContentLoadedEventStart - navigation.responseEnd,
                loadComplete: navigation.loadEventEnd - navigation.navigationStart,
            };
        }
    }

    /**
     * 监控最大内容绘制 (LCP)
     */
    observeLCP() {
        try {
            const observer = new PerformanceObserver((list) => {
                const entries = list.getEntries();
                const lastEntry = entries[entries.length - 1];
                this.metrics.lcp = lastEntry.startTime;
                console.log(`LCP: ${lastEntry.startTime.toFixed(2)}ms`);
            });
            observer.observe({ type: 'largest-contentful-paint', buffered: true });
            this.observers.lcp = observer;
        } catch (e) {
            console.warn('LCP observation failed:', e);
        }
    }

    /**
     * 监控首次输入延迟 (FID)
     */
    observeFID() {
        try {
            const observer = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    this.metrics.fid = entry.processingStart - entry.startTime;
                    console.log(`FID: ${this.metrics.fid.toFixed(2)}ms`);
                    observer.disconnect(); // FID 只需要第一次输入
                }
            });
            observer.observe({ type: 'first-input', buffered: true });
            this.observers.fid = observer;
        } catch (e) {
            console.warn('FID observation failed:', e);
        }
    }

    /**
     * 监控累积布局偏移 (CLS)
     */
    observeCLS() {
        try {
            let clsValue = 0;
            const observer = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (!entry.hadRecentInput) {
                        clsValue += entry.value;
                        this.metrics.cls = clsValue;
                        console.log(`CLS: ${clsValue.toFixed(4)}`);
                    }
                }
            });
            observer.observe({ type: 'layout-shift', buffered: true });
            this.observers.cls = observer;
        } catch (e) {
            console.warn('CLS observation failed:', e);
        }
    }

    /**
     * 监控首次内容绘制 (FCP)
     */
    observeFCP() {
        try {
            const observer = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (entry.name === 'first-contentful-paint') {
                        this.metrics.fcp = entry.startTime;
                        console.log(`FCP: ${entry.startTime.toFixed(2)}ms`);
                        observer.disconnect();
                    }
                }
            });
            observer.observe({ type: 'paint', buffered: true });
            this.observers.fcp = observer;
        } catch (e) {
            console.warn('FCP observation failed:', e);
        }
    }

    /**
     * 监控首字节时间 (TTFB)
     */
    observeTTFB() {
        const navigation = performance.getEntriesByType('navigation')[0];
        if (navigation) {
            this.metrics.ttfb = navigation.responseStart - navigation.requestStart;
            console.log(`TTFB: ${this.metrics.ttfb.toFixed(2)}ms`);
        }
    }

    /**
     * 生成性能报告
     */
    report() {
        console.log('\n===== 性能基准测试报告 =====');
        console.log('时间戳:', new Date().toISOString());
        console.log('用户代理:', navigator.userAgent);
        console.log('\n核心指标:');

        // LCP (目标: <2.5s)
        if (this.metrics.lcp !== undefined) {
            const lcpScore = this.metrics.lcp < 2500 ? '✅ 优秀' : this.metrics.lcp < 4000 ? '⚠️ 需要改进' : '❌ 较差';
            console.log(`LCP (最大内容绘制): ${this.metrics.lcp.toFixed(2)}ms ${lcpScore}`);
        }

        // FID (目标: <100ms)
        if (this.metrics.fid !== undefined) {
            const fidScore = this.metrics.fid < 100 ? '✅ 优秀' : this.metrics.fid < 300 ? '⚠️ 需要改进' : '❌ 较差';
            console.log(`FID (首次输入延迟): ${this.metrics.fid.toFixed(2)}ms ${fidScore}`);
        }

        // CLS (目标: <0.1)
        if (this.metrics.cls !== undefined) {
            const clsScore = this.metrics.cls < 0.1 ? '✅ 优秀' : this.metrics.cls < 0.25 ? '⚠️ 需要改进' : '❌ 较差';
            console.log(`CLS (累积布局偏移): ${this.metrics.cls.toFixed(4)} ${clsScore}`);
        }

        // FCP (目标: <1.8s)
        if (this.metrics.fcp !== undefined) {
            const fcpScore = this.metrics.fcp < 1800 ? '✅ 优秀' : this.metrics.fcp < 3000 ? '⚠️ 需要改进' : '❌ 较差';
            console.log(`FCP (首次内容绘制): ${this.metrics.fcp.toFixed(2)}ms ${fcpScore}`);
        }

        // TTFB (目标: <600ms)
        if (this.metrics.ttfb !== undefined) {
            const ttfbScore = this.metrics.ttfb < 600 ? '✅ 优秀' : this.metrics.ttfb < 1000 ? '⚠️ 需要改进' : '❌ 较差';
            console.log(`TTFB (首字节时间): ${this.metrics.ttfb.toFixed(2)}ms ${ttfbScore}`);
        }

        console.log('\n导航详情:');
        if (this.metrics.navigation) {
            console.log(`DNS 查询: ${this.metrics.navigation.dns.toFixed(2)}ms`);
            console.log(`TCP 连接: ${this.metrics.navigation.tcp.toFixed(2)}ms`);
            console.log(`请求时间: ${this.metrics.navigation.request.toFixed(2)}ms`);
            console.log(`响应时间: ${this.metrics.navigation.response.toFixed(2)}ms`);
            console.log(`DOM 处理: ${this.metrics.navigation.domProcessing.toFixed(2)}ms`);
            console.log(`页面加载完成: ${this.metrics.navigation.loadComplete.toFixed(2)}ms`);
        }

        console.log('\n资源加载:');
        const resources = performance.getEntriesByType('resource');
        const resourcesByType = {};
        resources.forEach(resource => {
            const type = resource.initiatorType;
            if (!resourcesByType[type]) {
                resourcesByType[type] = { count: 0, totalSize: 0, totalTime: 0 };
            }
            resourcesByType[type].count++;
            resourcesByType[type].totalSize += resource.transferSize || 0;
            resourcesByType[type].totalTime += resource.duration;
        });

        Object.entries(resourcesByType).forEach(([type, data]) => {
            const size = (data.totalSize / 1024).toFixed(2);
            const time = data.totalTime.toFixed(2);
            console.log(`${type}: ${data.count} 个资源, 总大小: ${size}KB, 总时间: ${time}ms`);
        });

        console.log('\n===========================\n');

        // 保存到 localStorage
        try {
            const history = JSON.parse(localStorage.getItem('performance_history') || '[]');
            history.push({
                timestamp: Date.now(),
                metrics: this.metrics,
            });
            // 只保留最近 10 条记录
            if (history.length > 10) {
                history.shift();
            }
            localStorage.setItem('performance_history', JSON.stringify(history));
        } catch (e) {
            console.warn('Failed to save performance history:', e);
        }
    }

    /**
     * 获取性能历史记录
     */
    static getHistory() {
        try {
            return JSON.parse(localStorage.getItem('performance_history') || '[]');
        } catch {
            return [];
        }
    }

    /**
     * 清除性能历史记录
     */
    static clearHistory() {
        localStorage.removeItem('performance_history');
    }

    /**
     * 停止所有观察者
     */
    disconnect() {
        Object.values(this.observers).forEach(observer => {
            if (observer && typeof observer.disconnect === 'function') {
                observer.disconnect();
            }
        });
    }
}

// 自动初始化
if (document.readyState === 'complete') {
    const benchmark = new PerformanceBenchmark();
    benchmark.init();
    window.performanceBenchmark = benchmark;
} else {
    window.addEventListener('load', () => {
        const benchmark = new PerformanceBenchmark();
        benchmark.init();
        window.performanceBenchmark = benchmark;
    });
}