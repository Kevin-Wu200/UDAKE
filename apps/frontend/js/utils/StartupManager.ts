import { I18nDialog } from '../components/I18nDialog.js';
/**
 * 启动流程管理器
 * 协调应用启动的各个方面，包括资源预加载、性能监控、错误处理等
 */

export interface StartupConfig {
    enablePerformanceMonitoring: boolean;
    enableResourcePreload: boolean;
    minDisplayTime: number;
    maxRetries: number;
}

export interface ResourcePreloadConfig {
    scripts?: string[];
    styles?: string[];
    images?: string[];
}

export class StartupManager {
    private static instance: StartupManager | null = null;
    private config: StartupConfig;
    private startupStartTime: number = 0;
    private performanceData: Map<string, number> = new Map();
    private resourceCache: Map<string, any> = new Map();
    private retryCount: number = 0;

    private constructor(config: Partial<StartupConfig> = {}) {
        this.config = {
            enablePerformanceMonitoring: config.enablePerformanceMonitoring ?? true,
            enableResourcePreload: config.enableResourcePreload ?? true,
            minDisplayTime: config.minDisplayTime ?? 2500,
            maxRetries: config.maxRetries ?? 3
        };
    }

    /**
     * 获取单例实例
     */
    public static getInstance(config?: Partial<StartupConfig>): StartupManager {
        if (!StartupManager.instance) {
            StartupManager.instance = new StartupManager(config);
        }
        return StartupManager.instance;
    }

    /**
     * 开始启动流程
     */
    public async start(): Promise<void> {
        this.startupStartTime = Date.now();
        console.log('[StartupManager] 启动流程开始');

        // 记录启动性能
        if (this.config.enablePerformanceMonitoring) {
            this.recordPerformance('startup-start');
        }

        // 预加载资源
        if (this.config.enableResourcePreload) {
            await this.preloadResources();
        }
    }

    /**
     * 完成启动流程
     */
    public async complete(): Promise<void> {
        const endTime = Date.now();
        const totalTime = endTime - this.startupStartTime;

        console.log(`[StartupManager] 启动流程完成，总耗时: ${totalTime}ms`);

        // 记录性能数据
        if (this.config.enablePerformanceMonitoring) {
            this.recordPerformance('startup-complete');
            this.logPerformanceData();
        }

        // 保存性能数据到本地存储（用于分析）
        this.savePerformanceData(totalTime);
    }

    /**
     * 预加载资源
     */
    private async preloadResources(): Promise<void> {
        const preloadConfig: ResourcePreloadConfig = {
            scripts: [
                // 关键脚本
            ],
            styles: [
                // 关键样式
            ],
            images: [
                // 关键图片
            ]
        };

        await this.preloadResourcesConfig(preloadConfig);
    }

    /**
     * 使用配置预加载资源
     */
    public async preloadResourcesConfig(config: ResourcePreloadConfig): Promise<void> {
        const tasks: Promise<void>[] = [];

        // 预加载脚本
        if (config.scripts) {
            tasks.push(
                ...config.scripts.map(url => this.preloadScript(url))
            );
        }

        // 预加载样式
        if (config.styles) {
            tasks.push(
                ...config.styles.map(url => this.preloadStyle(url))
            );
        }

        // 预加载图片
        if (config.images) {
            tasks.push(
                ...config.images.map(url => this.preloadImage(url))
            );
        }

        // 等待所有预加载完成
        await Promise.allSettled(tasks);
    }

    /**
     * 预加载脚本
     */
    private preloadScript(url: string): Promise<void> {
        return new Promise((resolve, reject) => {
            if (this.resourceCache.has(url)) {
                resolve();
                return;
            }

            const link = document.createElement('link');
            link.rel = 'preload';
            link.as = 'script';
            link.href = url;

            link.onload = () => {
                this.resourceCache.set(url, true);
                resolve();
            };

            link.onerror = () => {
                console.warn(`[StartupManager] 脚本预加载失败: ${url}`);
                // 不拒绝，允许继续
                resolve();
            };

            document.head.appendChild(link);
        });
    }

    /**
     * 预加载样式
     */
    private preloadStyle(url: string): Promise<void> {
        return new Promise((resolve, reject) => {
            if (this.resourceCache.has(url)) {
                resolve();
                return;
            }

            const link = document.createElement('link');
            link.rel = 'preload';
            link.as = 'style';
            link.href = url;

            link.onload = () => {
                this.resourceCache.set(url, true);
                resolve();
            };

            link.onerror = () => {
                console.warn(`[StartupManager] 样式预加载失败: ${url}`);
                resolve();
            };

            document.head.appendChild(link);
        });
    }

    /**
     * 预加载图片
     */
    private preloadImage(url: string): Promise<void> {
        return new Promise((resolve, reject) => {
            if (this.resourceCache.has(url)) {
                resolve();
                return;
            }

            const img = new Image();

            img.onload = () => {
                this.resourceCache.set(url, true);
                resolve();
            };

            img.onerror = () => {
                console.warn(`[StartupManager] 图片预加载失败: ${url}`);
                resolve();
            };

            img.src = url;
        });
    }

    /**
     * 记录性能数据
     */
    public recordPerformance(mark: string): void {
        if (!this.config.enablePerformanceMonitoring) return;

        const timestamp = Date.now();
        this.performanceData.set(mark, timestamp);

        // 使用 Performance API
        if (window.performance && window.performance.mark) {
            window.performance.mark(mark);
        }
    }

    /**
     * 测量性能
     */
    public measurePerformance(startMark: string, endMark: string): number | null {
        if (!this.config.enablePerformanceMonitoring) return null;

        const startTime = this.performanceData.get(startMark);
        const endTime = this.performanceData.get(endMark);

        if (startTime && endTime) {
            return endTime - startTime;
        }

        // 尝试使用 Performance API
        if (window.performance && window.performance.measure) {
            try {
                const measure = window.performance.measure(`${startMark}-${endMark}`, startMark, endMark);
                return measure.duration;
            } catch (error) {
                console.warn('[StartupManager] 性能测量失败:', error);
            }
        }

        return null;
    }

    /**
     * 记录性能数据
     */
    private logPerformanceData(): void {
        console.log('[StartupManager] 性能数据:');
        for (const [mark, timestamp] of this.performanceData.entries()) {
            const relativeTime = timestamp - this.startupStartTime;
            console.log(`  ${mark}: +${relativeTime}ms`);
        }
    }

    /**
     * 保存性能数据到本地存储
     */
    private savePerformanceData(totalTime: number): void {
        try {
            const history = this.getPerformanceHistory();
            history.push({
                timestamp: Date.now(),
                totalTime,
                performanceData: Object.fromEntries(this.performanceData)
            });

            // 只保留最近 50 次记录
            if (history.length > 50) {
                history.shift();
            }

            localStorage.setItem('startup-performance', JSON.stringify(history));
        } catch (error) {
            console.warn('[StartupManager] 保存性能数据失败:', error);
        }
    }

    /**
     * 获取性能历史记录
     */
    public getPerformanceHistory(): any[] {
        try {
            const data = localStorage.getItem('startup-performance');
            return data ? JSON.parse(data) : [];
        } catch (error) {
            console.warn('[StartupManager] 获取性能历史失败:', error);
            return [];
        }
    }

    /**
     * 获取平均启动时间
     */
    public getAverageStartupTime(): number {
        const history = this.getPerformanceHistory();
        if (history.length === 0) return 0;

        const total = history.reduce((sum, record) => sum + record.totalTime, 0);
        return Math.round(total / history.length);
    }

    /**
     * 处理启动错误
     */
    public async handleStartupError(error: Error, context: string): Promise<void> {
        console.error(`[StartupManager] 启动错误 (${context}):`, error);

        this.recordPerformance(`error-${context}`);

        // 检查是否应该重试
        if (this.retryCount < this.config.maxRetries) {
            this.retryCount++;
            console.log(`[StartupManager] 准备重试 (${this.retryCount}/${this.config.maxRetries})...`);

            // 延迟重试
            await new Promise(resolve => setTimeout(resolve, 1000 * this.retryCount));
            return;
        }

        // 超过最大重试次数，显示错误页面
        this.showErrorPage(error, context);
    }

    /**
     * 显示错误页面
     */
    private showErrorPage(error: Error, context: string): void {
        console.error('[StartupManager] 启动失败，显示错误页面');

        // 创建错误页面
        const errorPage = document.createElement('div');
        errorPage.className = 'startup-error-page';
        errorPage.innerHTML = `
            <div class="error-content">
                <div class="error-icon">⚠️</div>
                <h1 class="error-title">启动失败</h1>
                <p class="error-message">应用启动过程中遇到错误：${error.message}</p>
                <p class="error-context">错误位置：${context}</p>
                <button class="error-retry-button">重试</button>
                <button class="error-report-button">报告问题</button>
            </div>
        `;

        document.body.appendChild(errorPage);

        // 绑定重试按钮
        const retryButton = errorPage.querySelector('.error-retry-button') as HTMLButtonElement;
        retryButton.addEventListener('click', () => {
            location.reload();
        });

        // 绑定报告按钮
        const reportButton = errorPage.querySelector('.error-report-button') as HTMLButtonElement;
        reportButton.addEventListener('click', () => {
            this.reportError(error, context);
        });
    }

    /**
     * 报告错误
     */
    private reportError(error: Error, context: string): void {
        // 这里可以集成错误报告服务
        console.log('[StartupManager] 报告错误:', error, context);

        // 显示感谢信息
        I18nDialog.alert('感谢您的反馈！我们已记录此错误。');
    }

    /**
     * 获取配置
     */
    public getConfig(): StartupConfig {
        return { ...this.config };
    }

    /**
     * 更新配置
     */
    public updateConfig(config: Partial<StartupConfig>): void {
        this.config = { ...this.config, ...config };
    }

    /**
     * 重置启动管理器
     */
    public reset(): void {
        this.startupStartTime = 0;
        this.performanceData.clear();
        this.resourceCache.clear();
        this.retryCount = 0;
    }

    /**
     * 获取启动时间
     */
    public getStartupTime(): number {
        if (this.startupStartTime === 0) return 0;
        return Date.now() - this.startupStartTime;
    }
}
