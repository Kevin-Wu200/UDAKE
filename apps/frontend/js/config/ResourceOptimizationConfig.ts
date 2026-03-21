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
            'css/animation-styles.css'
        ],
        criticalJS: [
            'js/utils/LoadingManager.js',
            'js/components/SplashScreen.js',
            'js/utils/LaunchProgressManager.js',
            'js/utils/StartupManager.js'
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
            'ParameterAdjustmentPanel'
        ],
        modules: [
            'map/core/ArcGISEngine',
            'map/core/AMapEngine',
            'adapters/ArcGISAdapter',
            'adapters/AMapAdapter'
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

/**
 * 资源优化管理器
 */
export class ResourceOptimizationManager {
    private static instance: ResourceOptimizationManager | null = null;
    private config: ResourceOptimizationConfig;
    private performanceObserver: PerformanceObserver | null = null;

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

        // 初始化性能监控
        if (this.config.monitoring.enabled) {
            this.initPerformanceMonitoring();
        }

        // 注册 Service Worker（如果支持）
        if (this.config.cache.enableOffline && 'serviceWorker' in navigator) {
            this.registerServiceWorker();
        }
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
    }

    /**
     * 预加载 CSS 文件
     */
    private preloadCSS(url: string): void {
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
        const link = document.createElement('link');
        link.rel = 'preload';
        link.as = 'script';
        link.href = url;
        document.head.appendChild(link);
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
            this.performanceObserver.observe({ entryTypes: ['navigation', 'resource', 'paint', 'largest-contentful-paint', 'first-input', 'layout-shift'] });

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

        // 检查阈值
        switch (entry.entryType) {
            case 'paint':
                if (entry.name === 'first-contentful-paint') {
                    const fcp = entry.startTime;
                    if (fcp > thresholds.firstContentfulPaint) {
                        console.warn(`[Performance] FCP 超过阈值: ${fcp}ms > ${thresholds.firstContentfulPaint}ms`);
                    }
                }
                break;

            case 'largest-contentful-paint':
                const lcp = entry.startTime;
                if (lcp > thresholds.largestContentfulPaint) {
                    console.warn(`[Performance] LCP 超过阈值: ${lcp}ms > ${thresholds.largestContentfulPaint}ms`);
                }
                break;

            case 'first-input':
                const fid = (entry as any).processingStart - entry.startTime;
                if (fid > thresholds.firstInputDelay) {
                    console.warn(`[Performance] FID 超过阈值: ${fid}ms > ${thresholds.firstInputDelay}ms`);
                }
                break;

            case 'layout-shift':
                if (!(entry as any).hadRecentInput) {
                    const cls = (entry as any).value;
                    if (cls > thresholds.cumulativeLayoutShift) {
                        console.warn(`[Performance] CLS 超过阈值: ${cls} > ${thresholds.cumulativeLayoutShift}`);
                    }
                }
                break;
        }
    }

    /**
     * 注册 Service Worker
     */
    private async registerServiceWorker(): Promise<void> {
        try {
            const registration = await navigator.serviceWorker.register('/sw.js');
            console.log('[ResourceOptimizationManager] Service Worker 注册成功:', registration);

            // 等待 Service Worker 激活
            await registration.update();
        } catch (error) {
            console.warn('[ResourceOptimizationManager] Service Worker 注册失败:', error);
        }
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
    }
}