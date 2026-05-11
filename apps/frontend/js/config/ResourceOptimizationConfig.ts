/**
 * 资源优化配置
 * 定义资源加载策略、缓存策略和预加载规则
 */

export interface ResourceOptimizationConfig {
    // 资源预加载配置
    preload: {
        // 关键 CSS 文件
        criticalCSS: string[];
        // 关键 JavaScript 文件
        criticalJS: string[];
        // 关键字体
        fonts: string[];
        // 关键图片
        images: string[];
    };

    // 懒加载配置
    lazyLoad: {
        // 延迟加载的组件
        components: string[];
        // 延迟加载的模块
        modules: string[];
        // 延迟加载的图片
        images: string[];
    };

    // 缓存策略配置
    cache: {
        // 缓存控制头
        cacheControl: string;
        // 缓存策略
        strategy: 'network-first' | 'cache-first' | 'stale-while-revalidate';
        // 缓存时长（秒）
        maxAge: number;
        // 是否启用离线缓存
        enableOffline: boolean;
    };

    // 性能监控配置
    monitoring: {
        // 是否启用性能监控
        enabled: boolean;
        // 采样率（0-1）
        sampleRate: number;
        // 性能指标阈值
        thresholds: {
            firstContentfulPaint: number; // 首次内容绘制
            largestContentfulPaint: number; // 最大内容绘制
            firstInputDelay: number; // 首次输入延迟
            cumulativeLayoutShift: number; // 累积布局偏移
            timeToInteractive: number; // 可交互时间
        };
    };

    // 网络优化配置
    network: {
        // 是否启用压缩
        enableCompression: boolean;
        // 是否启用 HTTP/2
        enableHTTP2: boolean;
        // 超时时间（毫秒）
        timeout: number;
        // 重试次数
        retryCount: number;
    };
}

/**
 * 默认资源优化配置
 */
export const defaultResourceOptimizationConfig: ResourceOptimizationConfig = {
    preload: {
        criticalCSS: [
            'css/theme-variables.css',
            'css/splash-screen.css',
            'css/skeleton-loader.css',
            'css/layout-styles.css',
            'css/component-styles.css',
            'css/animation-styles.css',
            'css/safari-compat.css'
        ],
        criticalJS: [
            'js/utils/LoadingManager.ts',
            'js/components/SplashScreen.ts',
            'js/utils/LaunchProgressManager.ts',
            'js/utils/StartupManager.ts'
        ],
        fonts: [],
        images: []
    },
    lazyLoad: {
        components: [
            'SamplingRecommendationPanel',
            'EnhancedSamplingRecommendationPanel',
            'VariogramChart',
            'UncertaintyHistogram',
            'CrossValidationScatterChart',
            'SamplingEfficiencyChart',
            'MeasureTool',
            'LayerComparisonPanel',
            'ParameterTabPanel',
            'ParameterHistoryManager',
            'ParameterComparisonPanel',
            'ParameterInfoPanel',
            'ParameterAdjustmentPanel',
            'Kriging3DPanel',
            'DeepLearningPanel',
            'FrontendIntegrationHub'
        ],
        modules: [
            'map/core/GeoSceneEngine',
            'map/core/AMapEngine',
            'adapters/GeoSceneAdapter',
            'adapters/AMapAdapter',
            'workers/compute'
        ],
        images: []
    },
    cache: {
        cacheControl: 'public, max-age=31536000, immutable',
        strategy: 'cache-first',
        maxAge: 31536000, // 1 年
        enableOffline: true
    },
    monitoring: {
        enabled: true,
        sampleRate: 0.1, // 10% 采样率
        thresholds: {
            firstContentfulPaint: 2000, // 2 秒
            largestContentfulPaint: 2500, // 2.5 秒
            firstInputDelay: 100, // 100 毫秒
            cumulativeLayoutShift: 0.1, // 0.1
            timeToInteractive: 3000 // 3 秒
        }
    },
    network: {
        enableCompression: true,
        enableHTTP2: true,
        timeout: 30000, // 30 秒
        retryCount: 3
    }
};

type MemoryPerformance = Performance & {
    memory?: {
        usedJSHeapSize: number;
        totalJSHeapSize: number;
        jsHeapSizeLimit: number;
    };
};

/**
 * 资源优化管理器
 */
export class ResourceOptimizationManager {
    private static instance: ResourceOptimizationManager | null = null;
    private config: ResourceOptimizationConfig;
    private performanceObserver: PerformanceObserver | null = null;
    private lazyLoadObserver: IntersectionObserver | null = null;
    private metricReportTimer: number | null = null;
    private memoryCheckTimer: number | null = null;
    private metricBuffer: Array<Record<string, unknown>> = [];
    private lastHeapUsage: number | null = null;

    private readonly moduleLoaders: Record<string, () => Promise<unknown>> = {
        'map/core/GeoSceneEngine': () => import('../map/core/GeoSceneEngine.js'),
        'map/core/AMapEngine': () => import('../map/core/AMapEngine.js'),
        'adapters/GeoSceneAdapter': () => import('../adapters/GeoSceneAdapter.js'),
        'adapters/AMapAdapter': () => import('../adapters/AMapAdapter.js'),
        'workers/compute': () => import('../workers/WorkerPoolManager.js'),
        // 兼容旧模块标识，避免历史调用失败
        'map/core/ArcGISEngine': () => import('../map/core/GeoSceneEngine.js'),
        'adapters/ArcGISAdapter': () => import('../adapters/GeoSceneAdapter.js')
    };

    private readonly componentLoaders: Record<string, () => Promise<unknown>> = {
        SamplingRecommendationPanel: () => import('../components/SamplingRecommendationPanel.js'),
        EnhancedSamplingRecommendationPanel: () => import('../components/EnhancedSamplingRecommendationPanel.js'),
        VariogramChart: () => import('../components/VariogramChart.js'),
        UncertaintyHistogram: () => import('../components/UncertaintyHistogram.js'),
        CrossValidationScatterChart: () => import('../components/CrossValidationScatterChart.js'),
        SamplingEfficiencyChart: () => import('../components/SamplingEfficiencyChart.js'),
        MeasureTool: () => import('../components/MeasureTool.js'),
        LayerComparisonPanel: () => import('../components/LayerComparisonPanel.js'),
        ParameterTabPanel: () => import('../components/ParameterTabPanel.js'),
        ParameterHistoryManager: () => import('../components/ParameterHistoryManager.js'),
        ParameterComparisonPanel: () => import('../components/ParameterComparisonPanel.js'),
        ParameterInfoPanel: () => import('../components/ParameterInfoPanel.js'),
        ParameterAdjustmentPanel: () => import('../components/ParameterAdjustmentPanel.js'),
        Kriging3DPanel: () => import('../components/Kriging3DPanel.js'),
        DeepLearningPanel: () => import('../components/DeepLearningPanel.js'),
        FrontendIntegrationHub: () => import('../components/FrontendIntegrationHub.js')
    };

    private constructor(config: Partial<ResourceOptimizationConfig> = {}) {
        this.config = {
            ...defaultResourceOptimizationConfig,
            ...config
        };
    }

    /**
     * 获取单例实例
     */
    public static getInstance(config?: Partial<ResourceOptimizationConfig>): ResourceOptimizationManager {
        if (!ResourceOptimizationManager.instance) {
            ResourceOptimizationManager.instance = new ResourceOptimizationManager(config);
        }
        return ResourceOptimizationManager.instance;
    }

    /**
     * 初始化资源优化
     */
    public async init(): Promise<void> {
        console.log('[ResourceOptimizationManager] 初始化资源优化');

        // 预加载关键资源
        await this.preloadCriticalResources();

        // 资源级懒加载
        this.initLazyLoading();

        // 空闲预加载策略
        this.preloadOnIdle();

        // 初始化性能监控
        if (this.config.monitoring.enabled) {
            this.initPerformanceMonitoring();
            this.startMetricReporter();
            this.startMemoryLeakMonitoring();
        }

        // 注册 Service Worker（如果支持）
        if (this.config.cache.enableOffline) {
            this.registerServiceWorker();
        }

        this.bindPageLifecycleEvents();
    }

    /**
     * 预加载关键资源
     */
    private async preloadCriticalResources(): Promise<void> {
        const { preload } = this.config;

        // 预加载 CSS
        for (const cssFile of preload.criticalCSS) {
            this.preloadCSS(cssFile);
        }

        // 预加载 JavaScript
        for (const jsFile of preload.criticalJS) {
            this.preloadJS(jsFile);
        }

        // 预加载字体
        for (const fontFile of preload.fonts) {
            this.preloadFont(fontFile);
        }
    }

    /**
     * 预加载 CSS 文件
     */
    private preloadCSS(url: string): void {
        if (document.head.querySelector(`link[rel="preload"][href="${url}"]`)) {
            return;
        }
        const link = document.createElement('link');
        link.rel = 'preload';
        link.as = 'style';
        link.href = url;
        document.head.appendChild(link);
    }

    /**
     * 预加载 JavaScript 文件
     */
    private preloadJS(url: string): void {
        if (document.head.querySelector(`link[href="${url}"]`)) {
            return;
        }
        const link = document.createElement('link');
        link.rel = 'modulepreload';
        link.href = url;
        document.head.appendChild(link);
    }

    private preloadFont(url: string): void {
        if (document.head.querySelector(`link[rel="preload"][href="${url}"]`)) {
            return;
        }
        const link = document.createElement('link');
        link.rel = 'preload';
        link.as = 'font';
        link.type = 'font/woff2';
        link.crossOrigin = 'anonymous';
        link.href = url;
        document.head.appendChild(link);
    }

    /**
     * 初始化懒加载（图片 + 可视区组件）
     */
    private initLazyLoading(): void {
        this.applyImageLazyAttributes();

        if (!('IntersectionObserver' in window)) {
            this.loadAllLazyElementsImmediately();
            return;
        }

        this.lazyLoadObserver = new IntersectionObserver(
            (entries) => {
                for (const entry of entries) {
                    if (!entry.isIntersecting) {
                        continue;
                    }
                    const element = entry.target as HTMLElement;
                    this.loadLazyElement(element);
                    this.lazyLoadObserver?.unobserve(element);
                }
            },
            {
                rootMargin: '180px 0px',
                threshold: 0.01
            }
        );

        this.observeLazyElements();
    }

    private applyImageLazyAttributes(): void {
        const images = document.querySelectorAll('img');
        images.forEach((image) => {
            if (!image.getAttribute('loading')) {
                image.setAttribute('loading', 'lazy');
            }
            if (!image.getAttribute('decoding')) {
                image.setAttribute('decoding', 'async');
            }
            if (!image.getAttribute('fetchpriority')) {
                image.setAttribute('fetchpriority', 'auto');
            }
            const webpSource = image.getAttribute('data-webp');
            if (webpSource) {
                image.setAttribute('src', webpSource);
            }
        });
    }

    private observeLazyElements(): void {
        if (!this.lazyLoadObserver) {
            return;
        }

        const targets = document.querySelectorAll('[data-lazy-component], [data-lazy-module], [data-src], img[data-src]');
        targets.forEach((target) => this.lazyLoadObserver?.observe(target));
    }

    private loadAllLazyElementsImmediately(): void {
        const targets = document.querySelectorAll<HTMLElement>('[data-lazy-component], [data-lazy-module], [data-src], img[data-src]');
        targets.forEach((target) => this.loadLazyElement(target));
    }

    private loadLazyElement(element: HTMLElement): void {
        const source = element.dataset.src;
        if (source) {
            if (element instanceof HTMLImageElement) {
                element.src = source;
            } else {
                element.style.backgroundImage = `url(${source})`;
            }
            element.removeAttribute('data-src');
        }

        const lazyModule = element.dataset.lazyModule;
        if (lazyModule) {
            const loader = this.moduleLoaders[lazyModule];
            if (loader) {
                void loader().catch((error) => {
                    console.warn(`[ResourceOptimizationManager] 懒加载模块失败: ${lazyModule}`, error);
                });
            }
            element.removeAttribute('data-lazy-module');
        }

        const lazyComponent = element.dataset.lazyComponent;
        if (lazyComponent) {
            const loader = this.componentLoaders[lazyComponent];
            if (loader) {
                void loader()
                    .then((module) => {
                        element.dispatchEvent(new CustomEvent('lazy-component-ready', {
                            detail: {
                                component: lazyComponent,
                                module
                            }
                        }));
                    })
                    .catch((error) => {
                        console.warn(`[ResourceOptimizationManager] 懒加载组件失败: ${lazyComponent}`, error);
                    });
            }
             element.removeAttribute('data-lazy-component');
         }

         element.classList.add('lazy-loaded');
     }

     /**
      * 空闲时预加载模块，减少用户首次进入时等待
      */
     private preloadOnIdle(): void {
         const preloadTask = async () => {
             const moduleTasks = this.config.lazyLoad.modules
                 .map((name) => this.moduleLoaders[name])
                 .filter((loader): loader is () => Promise<unknown> => Boolean(loader))
                 .map((loader) => loader());

             const componentTasks = this.config.lazyLoad.components
                 .map((name) => this.componentLoaders[name])
                 .filter((loader): loader is () => Promise<unknown> => Boolean(loader))
                 .slice(0, 4)
                 .map((loader) => loader());

             await Promise.allSettled([...moduleTasks, ...componentTasks]);
         };

         if ('requestIdleCallback' in window) {
             requestIdleCallback(() => {
                 void preloadTask();
             }, { timeout: 4000 });
             return;
         }

         setTimeout(() => {
             void preloadTask();
         }, 1200);
     }

     /**
      * 初始化性能监控
      */
     private initPerformanceMonitoring(): void {
         if (!('PerformanceObserver' in window)) {
             console.warn('[ResourceOptimizationManager] PerformanceObserver 不支持');
             return;
         }

         try {
             // 监控核心 Web 性能指标
             this.performanceObserver = new PerformanceObserver((list) => {
                 for (const entry of list.getEntries()) {
                     this.handlePerformanceEntry(entry);
                 }
             });

             // 监控各种性能指标
             this.performanceObserver.observe({
                 entryTypes: ['navigation', 'resource', 'paint', 'largest-contentful-paint', 'first-input', 'layout-shift']
             });

             console.log('[ResourceOptimizationManager] 性能监控已启动');
         } catch (error) {
             console.warn('[ResourceOptimizationManager] 性能监控初始化失败:', error);
         }
     }

     /**
      * 处理性能条目
      */
     private handlePerformanceEntry(entry: PerformanceEntry): void {
         const { thresholds } = this.config.monitoring;
         let vitalName = entry.entryType;
         let vitalValue = entry.startTime;

         // 检查阈值
         switch (entry.entryType) {
             case 'paint':
                 if (entry.name === 'first-contentful-paint') {
                     const fcp = entry.startTime;
                     vitalName = 'fcp';
                     vitalValue = fcp;
                     if (fcp > thresholds.firstContentfulPaint) {
                         console.warn(`[Performance] FCP 超过阈值: ${fcp}ms > ${thresholds.firstContentfulPaint}ms`);
                     }
                 }
                 break;

             case 'largest-contentful-paint': {
                 const lcp = entry.startTime;
                 vitalName = 'lcp';
                 vitalValue = lcp;
                 if (lcp > thresholds.largestContentfulPaint) {
                     console.warn(`[Performance] LCP 超过阈值: ${lcp}ms > ${thresholds.largestContentfulPaint}ms`);
                 }
                 break;
             }

             case 'first-input': {
                 const fid = (entry as any).processingStart - entry.startTime;
                 vitalName = 'fid';
                 vitalValue = fid;
                 if (fid > thresholds.firstInputDelay) {
                     console.warn(`[Performance] FID 超过阈值: ${fid}ms > ${thresholds.firstInputDelay}ms`);
                 }
                 break;
             }

             case 'layout-shift':
                 if (!(entry as any).hadRecentInput) {
                     const cls = (entry as any).value;
                     vitalName = 'cls';
                     vitalValue = cls;
                     if (cls > thresholds.cumulativeLayoutShift) {
                         console.warn(`[Performance] CLS 超过阈值: ${cls} > ${thresholds.cumulativeLayoutShift}`);
                     }
                 }
                 break;
         }

         this.bufferMetric(vitalName, vitalValue, {
             entryType: entry.entryType,
             entryName: entry.name,
             startTime: entry.startTime
         });
     }

     private bufferMetric(name: string, value: number, metadata?: Record<string, unknown>): void {
         if (Math.random() > this.config.monitoring.sampleRate) {
             return;
         }

         this.metricBuffer.push({
             name,
             value,
             ts: Date.now(),
             metadata: metadata || {}
         });

         if (this.metricBuffer.length >= 30) {
             this.flushMetrics();
         }
     }

     private startMetricReporter(): void {
         if (this.metricReportTimer !== null) {
             clearInterval(this.metricReportTimer);
         }

         this.metricReportTimer = window.setInterval(() => {
             this.flushMetrics();
         }, 15000);
     }

     private flushMetrics(): void {
         if (this.metricBuffer.length === 0) {
             return;
         }

         const payload = {
             app: 'udake-frontend',
             page: window.location.pathname,
             userAgent: navigator.userAgent,
             metrics: this.metricBuffer.splice(0, this.metricBuffer.length)
         };

         try {
             const body = JSON.stringify(payload);
             if ('sendBeacon' in navigator) {
                 const blob = new Blob([body], { type: 'application/json' });
                 navigator.sendBeacon('/api/performance/metrics', blob);
             } else {
                 void fetch('/api/performance/metrics', {
                     method: 'POST',
                     headers: {
                         'Content-Type': 'application/json'
                     },
                     body,
                     keepalive: true
                 });
             }
         } catch (error) {
             console.warn('[ResourceOptimizationManager] 性能数据上报失败:', error);
         }
     }

     private startMemoryLeakMonitoring(): void {
         if (this.memoryCheckTimer !== null) {
             clearInterval(this.memoryCheckTimer);
         }

         this.memoryCheckTimer = window.setInterval(() => {
             const perf = performance as MemoryPerformance;
             const memory = perf.memory;
             if (!memory) {
                 return;
             }

             const usage = memory.usedJSHeapSize;
             if (this.lastHeapUsage !== null) {
                 const growth = usage - this.lastHeapUsage;
                 const growthRate = this.lastHeapUsage > 0
                     ? growth / this.lastHeapUsage
                     : 0;

                 if (growth > 10 * 1024 * 1024 && growthRate > 0.2) {
                     console.warn('[ResourceOptimizationManager] 检测到可疑内存增长', {
                         previous: this.lastHeapUsage,
                         current: usage,
                         growth,
                         growthRate
                     });
                     this.bufferMetric('memory-growth', growth, {
                         growthRate,
                         usedJSHeapSize: usage,
                         totalJSHeapSize: memory.totalJSHeapSize,
                         jsHeapSizeLimit: memory.jsHeapSizeLimit
                     });
                 }
             }

             this.lastHeapUsage = usage;
         }, 30000);
     }

     private bindPageLifecycleEvents(): void {
         window.addEventListener('beforeunload', () => {
             this.flushMetrics();
         }, { once: true });

         document.addEventListener('visibilitychange', () => {
             if (document.visibilityState === 'hidden') {
                 this.flushMetrics();
             }
         }, { passive: true });
     }

     /**
      * 注册 Service Worker
      */
     private async registerServiceWorker(): Promise<void> {
         const protocol = window.location.protocol;
         const hostname = window.location.hostname;
         const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
         const isSupportedProtocol = protocol === 'https:' || isLocalhost;

         if (!('serviceWorker' in navigator)) {
             this.enableLocalOfflineFallback('当前浏览器不支持 Service Worker');
             return;
         }

         if (!isSupportedProtocol || !window.isSecureContext) {
             this.enableLocalOfflineFallback(`当前协议 ${protocol} 不支持 Service Worker`);
             return;
         }

         try {
             const registration = await navigator.serviceWorker.register('/sw.js');
             console.log('[ResourceOptimizationManager] Service Worker 注册成功:', registration);

             // 等待 Service Worker 激活
             await registration.update();
         } catch (error) {
             console.warn('[ResourceOptimizationManager] Service Worker 注册失败:', error);
             this.enableLocalOfflineFallback('Service Worker 注册失败，已启用本地缓存降级');
         }
     }

     /**
      * Service Worker 不可用时启用本地缓存降级方案
      */
     private enableLocalOfflineFallback(reason: string): void {
         try {
             localStorage.setItem('udake-offline-fallback-enabled', 'true');
             localStorage.setItem('udake-offline-fallback-reason', reason);
             localStorage.setItem('udake-offline-fallback-updated-at', String(Date.now()));
         } catch (error) {
             console.warn('[ResourceOptimizationManager] localStorage 降级写入失败:', error);
         }
         console.warn(`[ResourceOptimizationManager] ${reason}`);
     }

     /**
      * 获取配置
      */
     public getConfig(): ResourceOptimizationConfig {
         return { ...this.config };
     }

     /**
      * 更新配置
      */
     public updateConfig(config: Partial<ResourceOptimizationConfig>): void {
         this.config = {
             ...this.config,
             ...config
         };
     }

     /**
      * 清理
      */
     public cleanup(): void {
         if (this.performanceObserver) {
             this.performanceObserver.disconnect();
             this.performanceObserver = null;
         }

         if (this.lazyLoadObserver) {
             this.lazyLoadObserver.disconnect();
             this.lazyLoadObserver = null;
         }

         if (this.metricReportTimer !== null) {
             clearInterval(this.metricReportTimer);
             this.metricReportTimer = null;
         }

         if (this.memoryCheckTimer !== null) {
             clearInterval(this.memoryCheckTimer);
             this.memoryCheckTimer = null;
         }

         this.flushMetrics();
     }
 }
