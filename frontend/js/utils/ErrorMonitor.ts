/**
 * 错误监控集成模块
 * 使用 Sentry SDK（兼容 GlitchTip 自托管）
 * 提供：错误捕获、上报、用户行为追踪、性能监控
 */

export interface SentryConfig {
    dsn: string;
    environment?: string;
    release?: string;
    tracesSampleRate?: number;
    enabled?: boolean;
    serverName?: string;
}

interface BreadcrumbData {
    category: string;
    message: string;
    level?: 'info' | 'warning' | 'error';
    data?: Record<string, unknown>;
}

interface ErrorContext {
    errorType?: string;
    component?: string;
    action?: string;
    [key: string]: unknown;
}

interface UserData {
    id?: string;
    email?: string;
    name?: string;
}

declare const Sentry: any;

export class ErrorMonitor {
    private static _initialized: boolean = false;
    private static _config: SentryConfig | null = null;
    private static _fallbackLog: Array<{ error: unknown; context: ErrorContext; timestamp: string }> = [];
    private static readonly MAX_FALLBACK_LOG = 100;

    /**
     * 初始化错误监控
     */
    static async init(config: SentryConfig): Promise<void> {
        ErrorMonitor._config = config;

        if (!config.enabled || !config.dsn) {
            console.log('[ErrorMonitor] 错误监控未启用（无 DSN 或 enabled=false）');
            ErrorMonitor._setupFallbackHandlers();
            return;
        }

        try {
            await ErrorMonitor._loadSentrySDK();
            ErrorMonitor._initSentry(config);
            ErrorMonitor._initialized = true;
            console.log('[ErrorMonitor] Sentry 初始化成功');
        } catch (e) {
            console.warn('[ErrorMonitor] Sentry 加载失败，使用本地错误记录', e);
            ErrorMonitor._setupFallbackHandlers();
        }
    }

    /**
     * 动态加载 Sentry SDK
     */
    private static _loadSentrySDK(): Promise<void> {
        return new Promise((resolve, reject) => {
            if (typeof Sentry !== 'undefined') {
                resolve();
                return;
            }

            // 动态加载 Sentry Browser SDK
            const script = document.createElement('script');
            script.src = 'https://browser.sentry-cdn.com/7.108.0/bundle.tracing.min.js';
            script.crossOrigin = 'anonymous';
            script.onload = () => resolve();
            script.onerror = () => reject(new Error('Sentry SDK 加载失败'));
            document.head.appendChild(script);
        });
    }

    /**
     * 初始化 Sentry
     */
    private static _initSentry(config: SentryConfig): void {
        Sentry.init({
            dsn: config.dsn,
            environment: config.environment || 'production',
            release: config.release || 'udake@1.0.0',
            serverName: config.serverName || 'UDAKE-Web',
            tracesSampleRate: config.tracesSampleRate || 0.1,
            beforeSend(event, hint) {
                // 过滤掉第三方脚本错误
                if (event.exception) {
                    const exception = event.exception.values?.[0];
                    if (exception?.stacktrace) {
                        const stacktrace = exception.stacktrace;
                        const hasOwnCode = stacktrace.frames?.some((frame: any) => {
                            const filename = frame.filename;
                            return filename && (filename.includes('/js/') || filename.includes('/css/'));
                        });

                        if (!hasOwnCode) {
                            return null; // 忽略非自身代码错误
                        }
                    }
                }
                return event;
            },
            beforeBreadcrumb(breadcrumb) {
                // 过滤掉不重要的面包屑
                if (breadcrumb.category === 'xhr' && breadcrumb.data?.url) {
                    const url = breadcrumb.data.url as string;
                    // 忽略健康检查和统计接口
                    if (url.includes('/health') || url.includes('/analytics')) {
                        return null;
                    }
                }
                return breadcrumb;
            },
            integrations: [
                new Sentry.BrowserTracing({
                    // 性能追踪配置
                    tracePropagationTargets: [
                        /^https:\/\/localhost:\d+/,
                        /^https:\/\/udake\./,
                        window.location.origin
                    ]
                }),
                new Sentry.Replay({
                    // 会话回放配置
                    maskAllText: true,
                    blockAllMedia: true,
                    sessionSampleRate: 0.1, // 10% 的会话会被录制
                    errorSampleRate: 1.0 // 所有错误的会话都会被录制
                })
            ],
            // 忽略特定错误
            ignoreErrors: [
                'Script error.',
                'Non-Error promise rejection captured',
                'ResizeObserver loop limit exceeded',
                'Network request failed'
            ],
            // 性能采样率
            replaysSessionSampleRate: 0.1,
            replaysOnErrorSampleRate: 1.0
        });

        // 添加用户代理信息
        Sentry.setContext('device', {
            userAgent: navigator.userAgent,
            language: navigator.language,
            platform: navigator.platform,
            screenResolution: `${window.screen.width}x${window.screen.height}`,
            viewport: `${window.innerWidth}x${window.innerHeight}`
        });

        // 添加应用上下文
        Sentry.setContext('app', {
            name: 'UDAKE',
            version: config.release || '1.0.0',
            buildDate: new Date().toISOString()
        });
    }

    /**
     * 本地回退错误处理（Sentry 不可用时）
     */
    private static _setupFallbackHandlers(): void {
        window.addEventListener('error', (event) => {
            ErrorMonitor._addFallbackLog(event.error || event.message, {
                component: 'window',
                action: 'uncaughtError'
            });
        });

        window.addEventListener('unhandledrejection', (event) => {
            ErrorMonitor._addFallbackLog(event.reason, {
                component: 'promise',
                action: 'unhandledRejection'
            });
        });
    }

    private static _addFallbackLog(error: unknown, context: ErrorContext): void {
        ErrorMonitor._fallbackLog.push({
            error,
            context,
            timestamp: new Date().toISOString()
        });
        if (ErrorMonitor._fallbackLog.length > ErrorMonitor.MAX_FALLBACK_LOG) {
            ErrorMonitor._fallbackLog.shift();
        }
    }

    /**
     * 手动捕获错误
     */
    static captureError(error: Error, context: ErrorContext = {}): void {
        if (ErrorMonitor._initialized) {
            Sentry.withScope((scope: any) => {
                scope.setContext('errorContext', context);
                if (context.errorType) {
                    scope.setTag('errorType', context.errorType);
                }
                if (context.component) {
                    scope.setTag('component', context.component);
                }
                if (context.action) {
                    scope.setTag('action', context.action);
                }
                Sentry.captureException(error);
            });
        } else {
            ErrorMonitor._addFallbackLog(error, context);
            console.error('[ErrorMonitor]', error, context);
        }
    }

    /**
     * 捕获消息
     */
    static captureMessage(message: string, level: 'info' | 'warning' | 'error' = 'info'): void {
        if (ErrorMonitor._initialized) {
            Sentry.withScope((scope: any) => {
                scope.setLevel(level);
                Sentry.captureMessage(message);
            });
        } else {
            console.log(`[ErrorMonitor][${level}]`, message);
        }
    }

    /**
     * 添加面包屑（用户行为追踪）
     */
    static addBreadcrumb(data: BreadcrumbData): void {
        if (ErrorMonitor._initialized) {
            Sentry.addBreadcrumb({
                category: data.category,
                message: data.message,
                level: data.level || 'info',
                data: data.data || {}
            });
        } else {
            console.log(`[ErrorMonitor][Breadcrumb] ${data.category}: ${data.message}`);
        }
    }

    /**
     * 设置用户信息
     */
    static setUser(user: UserData | null): void {
        if (ErrorMonitor._initialized) {
            if (user) {
                Sentry.setUser({
                    id: user.id,
                    email: user.email,
                    username: user.name
                });
            } else {
                Sentry.setUser(null);
            }
        }
    }

    /**
     * 设置标签
     */
    static setTag(key: string, value: string): void {
        if (ErrorMonitor._initialized) {
            Sentry.setTag(key, value);
        }
    }

    /**
     * 设置上下文
     */
    static setContext(key: string, context: Record<string, unknown>): void {
        if (ErrorMonitor._initialized) {
            Sentry.setContext(key, context);
        }
    }

    /**
     * 开始性能追踪
     */
    static startTransaction(name: string, op: string): any {
        if (ErrorMonitor._initialized) {
            return Sentry.startTransaction({
                name,
                op
            });
        }
        return {
            finish: () => {},
            setTag: () => {},
            setData: () => {}
        };
    }

    /**
     * 获取本地错误日志（Sentry 不可用时的回退记录）
     */
    static getFallbackLog(): typeof ErrorMonitor._fallbackLog {
        return [...ErrorMonitor._fallbackLog];
    }

    /**
     * 是否已初始化 Sentry
     */
    static isInitialized(): boolean {
        return ErrorMonitor._initialized;
    }

    /**
     * 获取 Sentry DSN（用于调试）
     */
    static getDSN(): string | null {
        return ErrorMonitor._config?.dsn || null;
    }
}