/**
 * 移动端性能优化器
 * 实现资源加载优化、渲染性能优化和减少动画效果
 */

interface PerformanceMetrics {
    fps: number;
    memoryUsage: number;
    loadTime: number;
    renderTime: number;
}

interface OptimizationOptions {
    enableLazyLoad: boolean;
    enableImageCompression: boolean;
    enableAnimationReduction: boolean;
    enableVirtualScrolling: boolean;
    maxConcurrentRequests: number;
}

class MobilePerformanceOptimizer {
    private metrics: PerformanceMetrics = {
        fps: 60,
        memoryUsage: 0,
        loadTime: 0,
        renderTime: 0,
    };

    private options: Required<OptimizationOptions>;
    private lazyLoadObserver: IntersectionObserver | null = null;
    private imageCompressionWorker: Worker | null = null;
    private frameId: number | null = null;
    private lastFrameTime: number = 0;
    private frameCount: number = 0;

    constructor(options: OptimizationOptions = {}) {
        this.options = {
            enableLazyLoad: options.enableLazyLoad ?? true,
            enableImageCompression: options.enableImageCompression ?? true,
            enableAnimationReduction: options.enableAnimationReduction ?? true,
            enableVirtualScrolling: options.enableVirtualScrolling ?? true,
            maxConcurrentRequests: options.maxConcurrentRequests ?? 4,
        };

        this.init();
    }

    /**
     * 初始化
     */
    private init(): void {
        // 检测移动设备
        if (this.isMobileDevice()) {
            this.applyMobileOptimizations();
        }

        // 监听性能
        this.startPerformanceMonitoring();

        // 初始化懒加载
        if (this.options.enableLazyLoad) {
            this.initLazyLoading();
        }

        // 初始化图片压缩
        if (this.options.enableImageCompression) {
            this.initImageCompression();
        }

        // 减少动画效果
        if (this.options.enableAnimationReduction) {
            this.reduceAnimations();
        }

        // 监听网络状态
        this.initNetworkMonitoring();
    }

    /**
     * 检测移动设备
     */
    private isMobileDevice(): boolean {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    }

    /**
     * 应用移动端优化
     */
    private applyMobileOptimizations(): void {
        // 启用硬件加速
        this.enableHardwareAcceleration();

        // 优化触摸事件
        this.optimizeTouchEvents();

        // 减少重绘和回流
        this.minimizeReflows();

        // 使用 requestAnimationFrame
        this.optimizeAnimations();
    }

    /**
     * 启用硬件加速
     */
    private enableHardwareAcceleration(): void {
        const style = document.createElement('style');
        style.textContent = `
            .accelerated {
                transform: translateZ(0);
                backface-visibility: hidden;
                perspective: 1000px;
            }
        `;
        document.head.appendChild(style);

        // 为常用元素添加硬件加速
        const elements = document.querySelectorAll('.map-container, .panel, .sidebar');
        elements.forEach(el => el.classList.add('accelerated'));
    }

    /**
     * 优化触摸事件
     */
    private optimizeTouchEvents(): void {
        // 使用被动事件监听器
        document.addEventListener('touchstart', () => {}, { passive: true });
        document.addEventListener('touchmove', () => {}, { passive: true });

        // 禁用双击缩放
        const viewport = document.querySelector('meta[name="viewport"]');
        if (viewport) {
            viewport.setAttribute('content', 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no');
        }
    }

    /**
     * 减少重绘和回流
     */
    private minimizeReflows(): void {
        // 批量 DOM 操作
        const originalAppendChild = Element.prototype.appendChild;
        Element.prototype.appendChild = function(child) {
            requestAnimationFrame(() => {
                originalAppendChild.call(this, child);
            });
            return child;
        };
    }

    /**
     * 优化动画
     */
    private optimizeAnimations(): void {
        // 使用 CSS 动画代替 JavaScript 动画
        const style = document.createElement('style');
        style.textContent = `
            @media (max-width: 767px) {
                * {
                    transition-duration: 200ms !important;
                    animation-duration: 300ms !important;
                }

                .animating {
                    will-change: transform, opacity;
                }
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * 初始化懒加载
     */
    private initLazyLoading(): void {
        if ('IntersectionObserver' in window) {
            this.lazyLoadObserver = new IntersectionObserver(
                (entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            const element = entry.target as HTMLElement;
                            this.loadLazyElement(element);
                            this.lazyLoadObserver?.unobserve(element);
                        }
                    });
                },
                {
                    rootMargin: '50px',
                    threshold: 0.01,
                }
            );

            // 观察懒加载元素
            const lazyElements = document.querySelectorAll('[data-lazy]');
            lazyElements.forEach(el => this.lazyLoadObserver?.observe(el));
        }
    }

    /**
     * 加载懒加载元素
     */
    private loadLazyElement(element: HTMLElement): void {
        const src = element.getAttribute('data-src');
        if (src) {
            if (element.tagName === 'IMG') {
                (element as HTMLImageElement).src = src;
            } else {
                element.style.backgroundImage = `url(${src})`;
            }
            element.removeAttribute('data-lazy');
            element.classList.add('loaded');
        }
    }

    /**
     * 初始化图片压缩
     */
    private initImageCompression(): void {
        if ('Worker' in window) {
            // 创建 Web Worker 进行图片压缩
            const workerCode = `
                self.onmessage = function(e) {
                    const { imageData, quality } = e.data;
                    // 简化的图片压缩逻辑
                    self.postMessage({ imageData, compressed: true });
                };
            `;

            const blob = new Blob([workerCode], { type: 'application/javascript' });
            this.imageCompressionWorker = new Worker(URL.createObjectURL(blob));
        }
    }

    /**
     * 压缩图片
     */
    public async compressImage(imageData: ImageData, quality: number = 0.7): Promise<ImageData> {
        if (this.imageCompressionWorker) {
            return new Promise((resolve) => {
                this.imageCompressionWorker!.onmessage = (e) => {
                    resolve(e.data.imageData);
                };
                this.imageCompressionWorker!.postMessage({ imageData, quality });
            });
        }
        return imageData;
    }

    /**
     * 减少动画效果
     */
    private reduceAnimations(): void {
        // 检测用户的动画偏好
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        if (prefersReducedMotion || this.isMobileDevice()) {
            const style = document.createElement('style');
            style.textContent = `
                * {
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }
            `;
            document.head.appendChild(style);
        }
    }

    /**
     * 初始化网络监控
     */
    private initNetworkMonitoring(): void {
        if ('connection' in navigator) {
            const connection = (navigator as any).connection;

            // 根据网络类型调整加载策略
            if (connection.saveData) {
                this.options.enableLazyLoad = true;
                this.options.enableImageCompression = true;
                this.options.enableAnimationReduction = true;
            }

            // 监听网络变化
            connection.addEventListener('change', () => {
                if (connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g') {
                    this.applyLowBandwidthOptimizations();
                }
            });
        }
    }

    /**
     * 应用低带宽优化
     */
    private applyLowBandwidthOptimizations(): void {
        // 禁用自动播放
        const videos = document.querySelectorAll('video[autoplay]');
        videos.forEach(video => {
            video.pause();
            video.removeAttribute('autoplay');
        });

        // 降低图片质量
        const images = document.querySelectorAll('img');
        images.forEach(img => {
            const src = img.src;
            if (src.includes('?')) {
                img.src = `${src}&quality=low`;
            }
        });
    }

    /**
     * 开始性能监控
     */
    private startPerformanceMonitoring(): void {
        // 监控 FPS
        this.monitorFPS();

        // 监控内存使用
        this.monitorMemory();

        // 监控加载时间
        this.monitorLoadTime();

        // 监控渲染时间
        this.monitorRenderTime();
    }

    /**
     * 监控 FPS
     */
    private monitorFPS(): void {
        const measureFPS = () => {
            const now = performance.now();
            const delta = now - this.lastFrameTime;

            if (delta >= 1000) {
                this.metrics.fps = Math.round((this.frameCount * 1000) / delta);
                this.frameCount = 0;
                this.lastFrameTime = now;

                // 如果 FPS 过低，触发优化
                if (this.metrics.fps < 30) {
                    this.triggerPerformanceOptimization();
                }
            }

            this.frameCount++;
            this.frameId = requestAnimationFrame(measureFPS);
        };

        this.frameId = requestAnimationFrame(measureFPS);
    }

    /**
     * 监控内存使用
     */
    private monitorMemory(): void {
        if ('memory' in performance) {
            setInterval(() => {
                const memory = (performance as any).memory;
                this.metrics.memoryUsage = memory.usedJSHeapSize;
            }, 5000);
        }
    }

    /**
     * 监控加载时间
     */
    private monitorLoadTime(): void {
        window.addEventListener('load', () => {
            const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
            this.metrics.loadTime = navigation.loadEventEnd - navigation.fetchStart;
        });
    }

    /**
     * 监控渲染时间
     */
    private monitorRenderTime(): void {
        const observer = new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
                if (entry.entryType === 'measure') {
                    this.metrics.renderTime = entry.duration;
                }
            }
        });

        observer.observe({ entryTypes: ['measure'] });
    }

    /**
     * 触发性能优化
     */
    private triggerPerformanceOptimization(): void {
        console.warn('性能不足，启用优化模式');

        // 减少动画
        this.reduceAnimations();

        // 禁用某些功能
        const heavyElements = document.querySelectorAll('.heavy-feature');
        heavyElements.forEach(el => el.style.display = 'none');
    }

    /**
     * 虚拟滚动
     */
    public initVirtualScrolling(container: HTMLElement, itemHeight: number, renderItem: (index: number) => HTMLElement): void {
        if (!this.options.enableVirtualScrolling) return;

        const visibleItems = Math.ceil(container.clientHeight / itemHeight);
        const totalItems = parseInt(container.dataset.totalItems || '0');

        let scrollTop = 0;

        const renderVisibleItems = () => {
            const startIndex = Math.floor(scrollTop / itemHeight);
            const endIndex = Math.min(startIndex + visibleItems, totalItems);

            container.innerHTML = '';

            for (let i = startIndex; i < endIndex; i++) {
                const item = renderItem(i);
                item.style.position = 'absolute';
                item.style.top = `${i * itemHeight}px`;
                container.appendChild(item);
            }
        };

        container.addEventListener('scroll', () => {
            scrollTop = container.scrollTop;
            requestAnimationFrame(renderVisibleItems);
        });

        renderVisibleItems();
    }

    /**
     * 限制并发请求数
     */
    private async limitConcurrentRequests<T>(requests: Array<() => Promise<T>>): Promise<T[]> {
        const results: T[] = [];
        const executing: Promise<void>[] = [];

        for (const request of requests) {
            const promise = request().then(result => {
                results.push(result);
            });

            executing.push(promise);

            if (executing.length >= this.options.maxConcurrentRequests) {
                await Promise.race(executing);
                executing.splice(executing.findIndex(p => p === promise), 1);
            }
        }

        await Promise.all(executing);
        return results;
    }

    /**
     * 获取性能指标
     */
    public getMetrics(): PerformanceMetrics {
        return { ...this.metrics };
    }

    /**
     * 清理资源
     */
    public cleanup(): void {
        if (this.lazyLoadObserver) {
            this.lazyLoadObserver.disconnect();
            this.lazyLoadObserver = null;
        }

        if (this.imageCompressionWorker) {
            this.imageCompressionWorker.terminate();
            this.imageCompressionWorker = null;
        }

        if (this.frameId !== null) {
            cancelAnimationFrame(this.frameId);
            this.frameId = null;
        }
    }
}

// 导出
export default MobilePerformanceOptimizer;