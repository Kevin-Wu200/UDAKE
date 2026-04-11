/**
 * UDAKE 主程序
 * 应用程序入口和核心逻辑
 */

import { initializeMap, reinitializeMap } from './地图初始化.js';
import { abortAllAMapLoads } from './config/amap.config.js';
import { LayerManager } from './图层管理.js';
import { TaskPoller } from './任务轮询.js';
import { APIService } from './services/API封装.js';
import { SinglePointSampling } from './单点采样输入.js';
import { GeoJSONParser } from './utils/geojsonParser.js';
import { DataImportModal } from './components/DataImportModal.js';
import { NewProjectModal } from './components/NewProjectModal.js';
import { FreeSampling } from './sampling/FreeSampling.js';
import { RegionSampling } from './sampling/RegionSampling.js';
import { Project } from './models/Project.js';
import { LocationPermissionManager } from './utils/locationPermissionManager.js';
import { ConfirmDialog } from './components/ConfirmDialog.js';
import { LoadingManager } from './utils/LoadingManager.js';
import { ThemeManager } from './utils/ThemeManager.js';
import { OfflineManager } from './utils/OfflineManager.js';
import { ExportEnhancer } from './utils/ExportEnhancer.js';
import { I18n } from './utils/I18n.js';
import { FormValidator } from './utils/FormValidator.js';
import { KeyboardManager } from './utils/KeyboardManager.js';
import { AccessibilityManager } from './utils/AccessibilityManager.js';
import { HistoryManager } from './utils/HistoryManager.js';
import { PerformanceMonitor } from './utils/PerformanceMonitor.js';
import { SplashScreen } from './components/SplashScreen.js';
import { StartupLoader } from './components/StartupLoader.js';
import { StartupDegradationView, type StartupDegradationLevel } from './components/StartupDegradationView.js';
import { LaunchProgressManager } from './utils/LaunchProgressManager.js';
import { FeedbackCollector } from './components/FeedbackCollector.js';
import { PreferencesPanel } from './components/PreferencesPanel.js';
import { StartupManager } from './utils/StartupManager.js';
import { ResourceOptimizationManager } from './config/ResourceOptimizationConfig.js';
import { LanguageSwitcher, languageSwitcherStyles } from './components/LanguageSwitcher.js';
import { CSSFeatureDetector } from './utils/CSSFeatureDetector.js';
import { Logger } from './utils/Logger.js';
import { RuntimeLifecycle } from './utils/RuntimeLifecycle.js';
import { AppConfig } from './config/AppConfig.js';
import { MapConfig } from './config/map.config.js';
import { SkeletonLoader } from './utils/SkeletonLoader.js';
import { ComputationService } from './services/ComputationService.js';
import type { Kriging3DPanel } from './components/Kriging3DPanel.js';
import type { DeepLearningPanel } from './components/DeepLearningPanel.js';
import type { FrontendIntegrationHub } from './components/FrontendIntegrationHub.js';
import {
    getMapEngineDisplayName,
    type MapProvider
} from './map/MapEngineRegistry.js';

// 导入管理器
import { ComponentInitializer } from './managers/ComponentInitializer.js';
import { EventBinder } from './managers/EventBinder.js';
import { StateManager } from './managers/StateManager.js';
import { createStateBridge, type StateBridge } from './store/StateBridge.js';

// 导入类型
import {
    IAPIService,
    IMapAdapterExtended,
    MapView,
    IProject,
    ISamplingComponent,
    TransformedData,
    ProjectConfig,
    TaskStatusCallback,
    FormValidationRules,
    SamplingPoint,
    KrigingParams,
    ExtendedSamplingPoint
} from '../types/app';
import { TaskStatus } from '../types/core';
import type { GeoJSONParseResult } from '../types/geojson';
import type { SamplingPointValue } from '../types/sampling';

function stripApiSuffix(baseUrl: string): string {
    const trimmed = baseUrl.trim().replace(/\/+$/, '');
    return trimmed.endsWith('/api') ? trimmed.slice(0, -4) : trimmed;
}

function resolveFrontendBackendHost(): string {
    return (
        (import.meta.env.VITE_BACKEND_HOST as string) ||
        (import.meta.env.VITE_IPCONFIG as string) ||
        'localhost'
    );
}

function resolveFrontendBackendPort(): string {
    return (
        (import.meta.env.VITE_BACKEND_PORT as string) ||
        '8000'
    );
}

function resolveConfiguredApiBaseUrl(): string {
    return (
        (import.meta.env.VITE_API_BASE_URL as string) ||
        (import.meta.env.VITE_API_URL as string) ||
        `http://${resolveFrontendBackendHost()}:${resolveFrontendBackendPort()}`
    );
}

function buildApiUrl(baseUrl: string, backendPort: number): string {
    const normalizedBaseUrl = stripApiSuffix(baseUrl);

    // Electron 桌面端由本地后端分配端口，移动端直接使用环境变量地址。
    if (!window.electronAPI) {
        return `${normalizedBaseUrl}/api`;
    }

    try {
        const parsed = new URL(normalizedBaseUrl);
        parsed.port = String(backendPort);
        const basePath = parsed.pathname === '/' ? '' : parsed.pathname.replace(/\/+$/, '');
        return `${parsed.origin}${basePath}/api`;
    } catch {
        return `http://${resolveFrontendBackendHost()}:${backendPort}/api`;
    }
}

class StartupStepTimeoutError extends Error {
    public readonly stepName: string;
    public readonly timeoutMs: number;

    constructor(stepName: string, timeoutMs: number) {
        super(`${stepName} 执行超时（>${timeoutMs}ms）`);
        this.name = 'StartupStepTimeoutError';
        this.stepName = stepName;
        this.timeoutMs = timeoutMs;
    }
}

type StartupStepPriority = 'P0' | 'P1' | 'P2';

interface NativeSplashPlugin {
    hide: () => Promise<void>;
}

interface UploadQueuePayload {
    file?: File;
}

interface MapViewWithCamera {
    setCenter?: (center: [number, number]) => void;
    setZoom?: (zoom: number) => void;
}

interface SamplingComponentWithView extends ISamplingComponent {
    view?: MapView | null;
}

interface DataImportModalParseResult {
    fields: string[];
    geojson: GeoJSONParseResult['geojson'];
    crsInfo: {
        projectedName: string;
        projectedEPSG?: string;
        geographicName: string;
        geographicEPSG: string;
    };
}

function isProjectConfig(config: unknown): config is ProjectConfig {
    if (!config || typeof config !== 'object') {
        return false;
    }
    const value = config as Partial<ProjectConfig>;
    return (value.sampling_mode === 'free' || value.sampling_mode === 'region') &&
        (value.coordinate_mode === 'manual' || value.coordinate_mode === 'device');
}

function isKrigingParams(payload: unknown): payload is KrigingParams {
    if (!payload || typeof payload !== 'object') {
        return false;
    }
    const data = payload as Partial<KrigingParams>;
    return Array.isArray(data.points) &&
        typeof data.grid_resolution === 'number' &&
        typeof data.enable_cross_validation === 'boolean' &&
        (data.method === 'ordinary' || data.method === 'universal' || data.method === 'block') &&
        (data.variogram_model === 'spherical' || data.variogram_model === 'exponential' || data.variogram_model === 'gaussian');
}

// 初始化全局工具
Logger.bootstrap();
RuntimeLifecycle.installGlobalTracking();
Logger.info('主程序', '主程序已执行');
ThemeManager.init();
PerformanceMonitor.init();
HistoryManager.init();
I18n.init();
CSSFeatureDetector.init();
PerformanceMonitor.mark('appStart');

class App {
    // 核心服务
    public apiService: IAPIService | null = null;
    public layerManager: LayerManager | null = null;
    public taskPoller: TaskPoller | null = null;

    // 状态
    public currentDataId: string | null = null;
    public currentTaskId: string | null = null;
    public view: MapView | null = null;
    public currentProject: IProject | null = null;
    public samplingComponent: ISamplingComponent | null = null;

    // 切换状态
    private isSwitchingMap: boolean = false;
    private mapSwitchAbortController: AbortController | null = null;
    private mapSwitchSessionId: number = 0;
    private kriging3DPanel: Kriging3DPanel | null = null;
    private deepLearningPanel: DeepLearningPanel | null = null;
    private frontendIntegrationHub: FrontendIntegrationHub | null = null;

    // 管理器
    private componentInitializer: ComponentInitializer;
    private eventBinder: EventBinder;
    private stateManager: StateManager;
    private stateBridge: StateBridge | null = null;

    // 启动相关
    private splashScreen: SplashScreen | null = null;
    private splashScreenHidden: boolean = false;
    private startupLoader: StartupLoader | null = null;
    private startupDegradationView: StartupDegradationView | null = null;
    private launchProgressManager: LaunchProgressManager | null = null;
    private startupManager: StartupManager | null = null;
    private resourceOptimizationManager: ResourceOptimizationManager | null = null;
    private startupTimeoutTimer: number | null = null;
    private startupCompleted: boolean = false;
    private startupHardDeadlineReached: boolean = false;
    private startupHasFunctionalDegradation: boolean = false;
    private startupApiBaseUrl: string = resolveConfiguredApiBaseUrl();
    private startupBackendPort: number = 8000;
    private languageSwitcher: LanguageSwitcher | null = null;
    private accessibilityManager: AccessibilityManager | null = null;
    private lastAnnouncedProgressBucket: number = -1;

    // 工具
    private computationService: ComputationService;
    private formValidator: FormValidator | null = null;
    private locationServiceIntegration: { initialize: () => Promise<void> } | null = null;
    private isSidebarOpen: boolean = true;
    private isSidebarTransitioning: boolean = false;
    private readonly sidebarTransitionMs: number = 300;
    private sidebarTransitionTimer: number | null = null;
    private rightSidebarToggleBound: boolean = false;
    private mobileSidebarViewportSyncBound: boolean = false;

    constructor() {
        Logger.debug('主程序', 'App 构造函数执行');

        // 初始化管理器
        this.componentInitializer = new ComponentInitializer();
        this.eventBinder = EventBinder.getInstance();
        this.stateManager = StateManager.getInstance();
        this.stateBridge = createStateBridge(this.stateManager);
        this.stateBridge.start();
        this.computationService = ComputationService.getInstance();

        I18n.onChange(() => {
            this.updateUIText();
        });

        window.addEventListener('beforeunload', () => {
            this.stateBridge?.stop();
            this.resourceOptimizationManager?.cleanup();
            this.computationService.cleanup();
            this.accessibilityManager?.destroy();
        }, { once: true });

        // 初始化状态
        this.initializeAppState();

        // 开始初始化
        this.init();
    }

    /**
     * 初始化应用状态
     */
    private initializeAppState(): void {
        this.stateManager.initializeState([
            { key: 'currentTheme', defaultValue: 'light', config: { persist: true } },
            { key: 'currentLanguage', defaultValue: 'zh-CN', config: { persist: true } },
            { key: 'initialized', defaultValue: false },
            { key: 'currentProjectId', defaultValue: null },
            { key: 'currentTaskId', defaultValue: null }
        ]);
    }

    /**
     * 初始化应用
     */
    async init(): Promise<void> {
        Logger.debug('主程序', 'init 被执行');

        try {
            this.startupCompleted = false;
            this.startupHardDeadlineReached = false;
            this.startupHasFunctionalDegradation = false;
            this.startupDegradationView = new StartupDegradationView();

            // 阶段0：初始化核心管理器
            Logger.debug('主程序', '初始化启动管理器');
            this.startupManager = StartupManager.getInstance({
                enablePerformanceMonitoring: true,
                enableResourcePreload: true,
                minDisplayTime: 2500,
                maxRetries: 3
            });
            await this.startupManager.start();

            // 初始化资源优化管理器
            this.resourceOptimizationManager = ResourceOptimizationManager.getInstance();
            await this.resourceOptimizationManager.init();

            // 初始化启动进度管理器（必须在使用前初始化）
            this.launchProgressManager = LaunchProgressManager.getInstance();
            const defaultStages = LaunchProgressManager.createDefaultStages();
            defaultStages.forEach(stage => {
                this.launchProgressManager!.registerStage(stage);
            });

            // 显示启动画面
            this.splashScreen = SplashScreen.getInstance({
                showProgress: true,
                minDisplayTime: 2500
            });
            this.splashScreenHidden = false;
            this.splashScreen.show();
            this.splashScreen.setStage('loading');

            this.startupLoader = new StartupLoader({
                rotateIntervalMs: 1400,
                onStatusChange: (status) => {
                    if (!this.startupHardDeadlineReached) {
                        this.splashScreen?.updateStatus(status);
                    }
                }
            });
            this.startupLoader.start();

            this.armStartupHardTimeout();
            await this.reportStartupPerformance('startup_begin', {
                platform: window.electronAPI ? 'electron' : 'web'
            });

            // 设置进度回调
            this.launchProgressManager.setCallbacks({
                onStageStart: (stage) => {
                    if (!this.startupHardDeadlineReached) {
                        this.splashScreen?.updateStatus(stage.description);
                    }
                    this.splashScreen?.setStage('loading');
                },
                onTotalProgress: (total) => {
                    this.splashScreen?.updateProgress(total);
                }
            });

            // 方案A：硬编码依赖顺序 + 分阶段超时 + 三级降级
            await this.runPlannedStartupSequence();

            // 阶段1：完成初始化准备
            await this.launchProgressManager.executeStage('initialize', async () => {
                console.log('初始化准备完成');
            });

            // 阶段2：连接后端
            const backendPort = await this.launchProgressManager.executeStage('backend-connection', async (updateProgress) => {
                updateProgress(20);
                updateProgress(80);
                return this.startupBackendPort;
            });

            const configuredApiBaseUrl = this.startupApiBaseUrl;
            const apiURL = buildApiUrl(configuredApiBaseUrl, backendPort);

            // 阶段3：初始化API
            await this.launchProgressManager.executeStage('api-init', async (updateProgress) => {
                console.log('API URL:', apiURL);
                updateProgress(50);
                this.apiService = new APIService(apiURL);
                console.log('API 初始化完成');
                updateProgress(100);
            });

            // 阶段4：加载地图
            await this.launchProgressManager.executeStage('map-load', async (updateProgress) => {
                console.log('准备初始化地图');
                updateProgress(20);
                const mapAdapter = await initializeMap('viewDiv');
                updateProgress(60);
                this.view = mapAdapter.getView();
                this.layerManager = new LayerManager(mapAdapter);
                console.log('地图初始化完成');
                updateProgress(100);
            });

            // 阶段5：初始化组件
            await this.launchProgressManager.executeStage('components-init', async (updateProgress) => {
                console.log('准备初始化组件');
                updateProgress(30);

                // 使用ComponentInitializer初始化所有组件
                await this.componentInitializer.initialize({
                    apiService: this.apiService!,
                    layerManager: this.layerManager!,
                    view: this.view!
                });

                console.log('组件初始化完成');
                updateProgress(100);
            });

            // 阶段6：绑定事件
            await this.launchProgressManager.executeStage('events-bind', async (updateProgress) => {
                console.log('准备绑定事件');
                updateProgress(50);
                this.initializeLanguageSwitcher();
                this.bindEvents();
                this.bindMobileEvents();
                this.initializeAccessibility();
                console.log('bindEvents 调用完成');
                updateProgress(100);
            });

            // 阶段7：检查权限
            await this.launchProgressManager.executeStage('permission-check', async (updateProgress) => {
                console.log('准备检测定位权限');
                updateProgress(50);
                LocationPermissionManager.requestPermission().then(status => {
                    console.log('定位权限状态:', status);
                });
                updateProgress(100);
            });

            // 阶段8：准备就绪
            await this.launchProgressManager.executeStage('ready', async (updateProgress) => {
                console.log('准备就绪');
                updateProgress(100);
            });

            // 设置启动画面为就绪状态
            this.splashScreen?.setStage('ready');
            this.splashScreen?.updateStatus('准备就绪');
            this.splashScreen?.updateProgress(100);
            this.startupLoader?.stop('即将完成...');

            // 隐藏启动画面
            await this.hideAllSplashLayers();

            // 启动画面完全隐藏后再触发新手引导，避免与动画重叠
            if (this.splashScreenHidden) {
                const components = this.componentInitializer.getComponentRegistry();
                components.onboardingGuide.autoStart();
            }

            LoadingManager.hide();
            PerformanceMonitor.mark('appReady');
            PerformanceMonitor.measure('appInitTime', 'appStart', 'appReady');

            // 完成StartupManager
            await this.startupManager.complete();

            // 延迟初始化非关键组件
            this.deferredInitialization();

            // 标记为已初始化
            this.stateManager.setState('initialized', true);
            this.startupCompleted = true;
            this.disarmStartupHardTimeout();

            if (!this.startupHasFunctionalDegradation) {
                this.startupDegradationView?.clear();
            }

            await this.reportStartupPerformance('startup_complete', {
                startupDurationMs: this.startupManager.getStartupTime()
            });

        } catch (error) {
            this.disarmStartupHardTimeout();
            this.startupLoader?.stop('启动失败');

            console.error('启动过程出错:', error);
            this.splashScreen?.setStage('error');
            this.splashScreen?.updateStatus('启动失败，请重试');
            await this.hideNativeSplash();

            const errorMessage = error instanceof Error ? error.message : '未知错误';
            this.startupDegradationView?.show('fatal', {
                title: '启动失败',
                message: `应用启动过程中发生致命错误：${errorMessage}`,
                onRetry: () => window.location.reload()
            });
            await this.reportStartupPerformance('startup_fatal', {
                message: errorMessage
            });

            if (this.startupManager) {
                await this.startupManager.handleStartupError(error as Error, 'app-init');
            } else {
                throw error;
            }
        }
    }

    /**
     * 启动流程：8秒硬超时保护
     */
    private armStartupHardTimeout(): void {
        this.disarmStartupHardTimeout();
        this.startupTimeoutTimer = window.setTimeout(() => {
            void this.handleStartupHardTimeout();
        }, 8000);
    }

    private disarmStartupHardTimeout(): void {
        if (this.startupTimeoutTimer !== null) {
            clearTimeout(this.startupTimeoutTimer);
            this.startupTimeoutTimer = null;
        }
    }

    private async handleStartupHardTimeout(): Promise<void> {
        if (this.startupCompleted || this.startupHardDeadlineReached) {
            return;
        }

        this.startupHardDeadlineReached = true;
        this.startupHasFunctionalDegradation = true;
        this.startupLoader?.stop('启动耗时较长，进入降级模式...');
        this.splashScreen?.updateStatus('启动耗时较长，正在降级加载...');

        this.startupDegradationView?.show('functional', {
            message: '启动超过8秒，已切换为降级模式，核心功能将继续加载。'
        });
        await this.hideAllSplashLayers();

        await this.reportStartupPerformance('startup_timeout', {
            timeoutMs: 8000
        });
    }

    private async hideAllSplashLayers(): Promise<void> {
        const hideTasks: Promise<unknown>[] = [];
        if (!this.splashScreenHidden && this.splashScreen) {
            hideTasks.push(this.splashScreen.hide());
        }
        hideTasks.push(this.hideNativeSplash());
        await Promise.allSettled(hideTasks);
        this.splashScreenHidden = true;
    }

    private getNativeSplashPlugin(): NativeSplashPlugin | null {
        const win = window as unknown as {
            Capacitor?: {
                Plugins?: {
                    SplashScreen?: Partial<NativeSplashPlugin>;
                };
            };
        };
        const plugin = win.Capacitor?.Plugins?.SplashScreen;
        if (plugin && typeof plugin.hide === 'function') {
            return plugin as NativeSplashPlugin;
        }
        return null;
    }

    private async hideNativeSplash(): Promise<void> {
        const plugin = this.getNativeSplashPlugin();
        if (!plugin) {
            return;
        }
        try {
            await plugin.hide();
        } catch (error) {
            console.warn('隐藏原生启动画面失败:', error);
        }
    }

    /**
     * 方案A：固定依赖顺序
     * 1) loadConfig -> 2) connectBackend -> 3) loadUserData -> 4) initPushService
     */
    private async runPlannedStartupSequence(): Promise<void> {
        await this.executeStartupStep('loadConfig', 'P0', 3000, async () => {
            this.startupApiBaseUrl = resolveConfiguredApiBaseUrl();
            const normalized = stripApiSuffix(this.startupApiBaseUrl);
            if (!normalized) {
                throw new Error('API 基础地址无效');
            }
            return { apiBaseUrl: normalized };
        });

        await this.executeStartupStep('connectBackend', 'P1', 3000, async () => {
            this.startupBackendPort = 8000;
            if (window.electronAPI) {
                this.startupBackendPort = await this.withTimeout(
                    'connectBackend:getBackendPort',
                    2000,
                    () => window.electronAPI!.getBackendPort()
                );
            }

            const runtimeApi = buildApiUrl(this.startupApiBaseUrl, this.startupBackendPort);
            const healthUrl = `${runtimeApi.replace(/\/api$/, '')}/health`;
            await this.withTimeout('connectBackend:health', 2000, async () => {
                const response = await fetch(healthUrl, { method: 'GET', cache: 'no-store' });
                if (!response.ok) {
                    throw new Error(`后端健康检查失败: ${response.status}`);
                }
            });

            return { backendPort: this.startupBackendPort };
        });

        await this.executeStartupStep('loadUserData', 'P1', 3000, async () => {
            const theme = localStorage.getItem('theme');
            const language = localStorage.getItem('udake_locale');
            return {
                hasTheme: Boolean(theme),
                hasLanguage: Boolean(language)
            };
        });

        await this.executeStartupStep('initPushService', 'P2', 8000, async () => {
            if (!('Notification' in window)) {
                return { supported: false };
            }
            return {
                supported: true,
                permission: Notification.permission
            };
        });
    }

    private async executeStartupStep<T>(
        stepName: string,
        priority: StartupStepPriority,
        timeoutMs: number,
        task: () => Promise<T>
    ): Promise<T | null> {
        const startedAt = Date.now();
        try {
            const result = await this.withTimeout(stepName, timeoutMs, task);
            await this.reportStartupPerformance('startup_step_success', {
                stepName,
                priority,
                durationMs: Date.now() - startedAt
            });
            return result;
        } catch (error) {
            const message = error instanceof Error ? error.message : `${stepName} 失败`;
            await this.reportStartupPerformance('startup_step_failed', {
                stepName,
                priority,
                durationMs: Date.now() - startedAt,
                error: message
            });

            if (priority === 'P0') {
                throw error;
            }

            const degradeLevel: StartupDegradationLevel = priority === 'P1' ? 'functional' : 'experience';
            if (degradeLevel === 'functional') {
                this.startupHasFunctionalDegradation = true;
            }
            this.startupDegradationView?.show(degradeLevel, { message });
            return null;
        }
    }

    private withTimeout<T>(stepName: string, timeoutMs: number, task: () => Promise<T>): Promise<T> {
        return new Promise<T>((resolve, reject) => {
            const timerId = window.setTimeout(() => {
                reject(new StartupStepTimeoutError(stepName, timeoutMs));
            }, timeoutMs);

            task()
                .then((result) => {
                    clearTimeout(timerId);
                    resolve(result);
                })
                .catch((error) => {
                    clearTimeout(timerId);
                    reject(error);
                });
        });
    }

    private async reportStartupPerformance(
        eventType: string,
        payload: Record<string, unknown>
    ): Promise<void> {
        const endpoint = `${buildApiUrl(this.startupApiBaseUrl, this.startupBackendPort)}/startup/performance`;
        const controller = new AbortController();
        const timerId = window.setTimeout(() => {
            controller.abort();
        }, 1200);

        try {
            await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    eventType,
                    timestamp: new Date().toISOString(),
                    ...payload
                }),
                keepalive: true,
                signal: controller.signal
            });
        } catch {
            // 启动监控上报失败不阻塞主流程
        } finally {
            clearTimeout(timerId);
        }
    }

    /**
     * 延迟初始化非关键组件
     */
    private deferredInitialization(): void {
        if ('requestIdleCallback' in window) {
            requestIdleCallback(() => {
                this.computationService.preloadWorkers();
                this.preloadHeavyPanels();
                this.initializeNonCriticalComponents();
            }, { timeout: 2000 });
        } else {
            setTimeout(() => {
                this.computationService.preloadWorkers();
                this.preloadHeavyPanels();
                this.initializeNonCriticalComponents();
            }, 100);
        }
    }

    /**
     * 空闲时预加载重型功能模块，减少首次打开面板时的等待
     */
    private preloadHeavyPanels(): void {
        const preloadTask = () => Promise.allSettled([
            import('./components/Kriging3DPanel.js'),
            import('./components/DeepLearningPanel.js'),
            import('./components/FrontendIntegrationHub.js')
        ]);

        if ('requestIdleCallback' in window) {
            requestIdleCallback(() => {
                void preloadTask();
            }, { timeout: 5000 });
            return;
        }

        setTimeout(() => {
            void preloadTask();
        }, 1500);
    }

    /**
     * 初始化非关键组件
     */
    private async initializeNonCriticalComponents(): Promise<void> {
        console.log('开始初始化非关键组件...');

        try {
            // 初始化离线管理器
            await OfflineManager.init();
            console.log('[离线管理器] 初始化完成');

            // 注册离线队列处理器
            OfflineManager.registerHandler('upload', async (payload: unknown) => {
                const formData = payload instanceof FormData ? payload : new FormData();
                if (!(payload instanceof FormData)) {
                    const uploadPayload = payload as UploadQueuePayload;
                    if (!uploadPayload.file) {
                        throw new Error('离线上传缺少文件');
                    }
                    formData.append('file', uploadPayload.file);
                }
                if (this.apiService) {
                    await this.apiService.request(`${this.apiService.baseURL}/upload-data`, {
                        method: 'POST',
                        body: formData
                    });
                }
            });

            OfflineManager.registerHandler('kriging', async (payload: unknown) => {
                if (!isKrigingParams(payload)) {
                    throw new Error('离线克里金参数无效');
                }
                if (this.apiService) {
                    await this.apiService.startKriging(payload);
                }
            });

            const { gpsSyncService } = await import('./services/GPSSyncService.js');
            const defaultProjectId = localStorage.getItem('udake_gps_project_id') || 'default_mobile_project';
            await gpsSyncService.initialize(defaultProjectId);
            OfflineManager.registerHandler('gps_sync', async (payload: unknown) => {
                await gpsSyncService.syncSample(payload, { fromQueue: true });
            });

            // 初始化缓存管理和离线横幅
            const components = this.componentInitializer.getComponentRegistry();
            await components.cacheManagementPanel.init();
            await components.offlineModeBanner.init();

            // 绑定离线横幅事件
            this.bindOfflineBannerEvents();

            // 初始化缓存状态面板
            this.initializeCacheStatusPanel();

            // 初始化3D克里金面板
            await this.initializeKriging3DPanel();

            // 初始化深度学习面板
            await this.initializeDeepLearningPanel();

            // 初始化前端功能集成补齐面板
            await this.initializeFrontendIntegrationPanel();

            // 初始化位置服务
            await this.initializeLocationService();

            // 初始化界面文本
            this.updateUIText();

            console.log('非关键组件初始化完成');
        } catch (error) {
            console.error('非关键组件初始化失败:', error);
        }
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        console.log('bindEvents 执行');

        // 使用EventBinder绑定所有事件
        const components = this.componentInitializer.getComponentRegistry();

        // 偏好设置按钮
        this.eventBinder.bindBySelector('#preferences-btn', 'click', () => this.showPreferences());

        // 反馈按钮
        this.eventBinder.bindBySelector('#feedback-btn', 'click', () => {
            const feedbackCollector = components.feedbackCollector;
            if (!feedbackCollector) {
                // 延迟初始化
                const collector = new FeedbackCollector();
                collector.show();
            } else {
                feedbackCollector.show();
            }
        });

        // 主题切换按钮
        this.eventBinder.bindBySelector('#theme-toggle-btn', 'click', () => ThemeManager.toggle());

        // 新建项目按钮
        this.eventBinder.bindBySelector('#new-project-btn', 'click', () => this.handleNewProject());

        // 设置按钮
        this.eventBinder.bindBySelector('#settings-btn', 'click', () => {
            components.settingsPanel.toggle();
        });

        // 再次查看引导按钮
        this.eventBinder.bindBySelector('#show-guide-btn', 'click', () => {
            components.onboardingGuide.reset();
            components.onboardingGuide.start();
        });

        // 文件上传相关
        this.bindFileUploadEvents();

        // 插值开始按钮
        this.eventBinder.bindBySelector('#start-kriging-btn', 'click', () => this.handleStartKriging());

        // 图层控制
        this.bindLayerControlEvents();

        // 导出按钮
        this._bindExportButtons();

        // 监听自定义事件
        this.bindCustomEvents();
    }

    private initializeLanguageSwitcher(): void {
        const container = document.getElementById('language-switcher-container');
        if (!container || this.languageSwitcher) {
            return;
        }

        if (!document.getElementById('language-switcher-style')) {
            const styleEl = document.createElement('style');
            styleEl.id = 'language-switcher-style';
            styleEl.textContent = languageSwitcherStyles;
            document.head.appendChild(styleEl);
        }

        this.languageSwitcher = new LanguageSwitcher(container, () => {
            this.updateUIText();
        });
    }

    /**
     * 绑定文件上传事件
     */
    private bindFileUploadEvents(): void {
        const picker = document.getElementById('file-picker');
        const fileInput = document.getElementById('file-input') as HTMLInputElement;
        const fileName = document.getElementById('file-name');

        if (picker && fileInput) {
            this.eventBinder.bind(picker, 'click', () => {
                fileInput.click();
            });

            this.eventBinder.bind(fileInput, 'change', () => {
                if (fileName && fileInput.files && fileInput.files.length > 0) {
                    fileName.textContent = fileInput.files[0].name;
                }
            });
        }

        // 上传按钮
        this.eventBinder.bindBySelector('#upload-btn', 'click', () => this.handleUpload());

        // 网格分辨率实时校验
        this.eventBinder.bindBySelector('#grid-resolution', 'input', () => this.validateGridResolution());
    }

    /**
     * 绑定图层控制事件
     */
    private bindLayerControlEvents(): void {
        const bindLayerChange = (id: string, layerName: string) => {
            this.eventBinder.bindBySelector(`#${id}`, 'change', (e: Event) => {
                const target = e.target as HTMLInputElement;
                if (this.layerManager) {
                    this.layerManager.toggleLayer(layerName, target.checked);
                }
            });
        };

        bindLayerChange('layer-points', 'points');
        bindLayerChange('layer-prediction', 'prediction');
        bindLayerChange('layer-variance', 'variance');
    }

    /**
     * 绑定自定义事件
     */
    private bindCustomEvents(): void {
        // 地图引擎切换
        this.eventBinder.bind(document, 'map-engine-switch', (e: Event) => {
            const customEvent = e as CustomEvent;
            this.handleMapEngineSwitch(customEvent.detail);
        });

        // 回到中心
        this.eventBinder.bind(document, 'location-center', () => {
            this.handleLocationCenter();
        });

        // 更新界面文本
        this.eventBinder.bind(document, 'update-ui-text', () => {
            this.updateUIText();
        });

        // 快捷操作栏事件
        this.eventBinder.bind(document, 'quick-action-request', (e: Event) => {
            const detail = (e as CustomEvent<{ actionId: string; command: string; source: string }>).detail;
            if (!detail?.command) {
                return;
            }
            this.handleQuickAction(detail.command);
        });

        // 向导完成事件
        this.eventBinder.bind(document, 'wizard-completed', (e: Event) => {
            const detail = (e as CustomEvent<{ wizardId: string; values: Record<string, string | number | boolean> }>).detail;
            if (!detail?.wizardId) {
                return;
            }
            this.handleWizardCompleted(detail.wizardId, detail.values || {});
        });
    }

    /**
     * 绑定移动端事件
     */
    private bindMobileEvents(): void {
        const mobileToggle = document.getElementById('sidebar-mobile-toggle');
        const overlay = document.getElementById('sidebar-overlay');
        const sidebar = document.querySelector('.sidebar');

        if (mobileToggle && overlay && sidebar) {
            this.eventBinder.bind(mobileToggle, 'click', () => {
                const isOpen = sidebar.classList.toggle('mobile-open');
                overlay.classList.toggle('visible');
                mobileToggle.textContent = isOpen ? '✕' : '☰';
                mobileToggle.setAttribute('aria-expanded', String(isOpen));
                overlay.setAttribute('aria-hidden', String(!isOpen));
            });

            this.eventBinder.bind(overlay, 'click', () => {
                sidebar.classList.remove('mobile-open');
                overlay.classList.remove('visible');
                mobileToggle.textContent = '☰';
                mobileToggle.setAttribute('aria-expanded', 'false');
                overlay.setAttribute('aria-hidden', 'true');
            });
            console.log('[Sidebar] 移动端主侧边栏事件绑定成功');
        } else {
            console.warn('[Sidebar] 移动端主侧边栏元素不完整，已跳过绑定');
        }

        // 右侧侧边栏切换按钮（确保在 DOM 可用后再绑定）
        this.bindRightSidebarToggleWhenReady();
        this.bindMobileSidebarViewportSync();
    }

    /**
     * 初始化无障碍增强
     */
    private initializeAccessibility(): void {
        if (this.accessibilityManager) {
            this.accessibilityManager.refresh();
            return;
        }

        this.accessibilityManager = new AccessibilityManager({
            getMapView: () => (this.view as unknown as { getCenter?: () => [number, number] | { lng: number; lat: number }; setCenter?: (center: [number, number]) => void; getZoom?: () => number; setZoom?: (zoom: number) => void }) || null,
            onShowShortcutHelp: () => {
                KeyboardManager.toggleShortcutPanel();
            }
        });
        this.accessibilityManager.init();
    }

    /**
     * 切换右侧侧边栏
     */
    private toggleRightSidebar(): void {
        const rightSidebar = document.getElementById('right-sidebar');
        const sidebarToggle = document.getElementById('sidebar-toggle');

        if (!rightSidebar || !sidebarToggle) {
            console.warn('[Sidebar] 切换失败：未找到 right-sidebar 或 sidebar-toggle');
            return;
        }

        if (this.isSidebarTransitioning) {
            console.log('[Sidebar] 动画进行中，忽略本次点击');
            return;
        }

        const domIsOpen = !rightSidebar.classList.contains('hidden');
        if (domIsOpen !== this.isSidebarOpen) {
            console.warn(`[Sidebar] 状态不一致，使用 DOM 状态纠正：state=${this.isSidebarOpen}, dom=${domIsOpen}`);
            this.isSidebarOpen = domIsOpen;
        }

        const nextOpen = !this.isSidebarOpen;
        console.log(`[Sidebar] 切换前: isSidebarOpen=${this.isSidebarOpen}, rightSidebar.className="${rightSidebar.className}", toggle.className="${sidebarToggle.className}"`);

        this.isSidebarOpen = nextOpen;
        this.isSidebarTransitioning = true;
        rightSidebar.classList.toggle('hidden', !this.isSidebarOpen);
        sidebarToggle.classList.toggle('open', this.isSidebarOpen);
        sidebarToggle.setAttribute('aria-expanded', String(this.isSidebarOpen));

        if (window.innerWidth > 767) {
            rightSidebar.classList.remove('mobile-keyboard-open');
        }

        console.log(`[Sidebar] 切换后: isSidebarOpen=${this.isSidebarOpen}, rightSidebar.className="${rightSidebar.className}", toggle.className="${sidebarToggle.className}"`);

        if (this.sidebarTransitionTimer !== null) {
            window.clearTimeout(this.sidebarTransitionTimer);
        }
        this.sidebarTransitionTimer = window.setTimeout(() => {
            this.isSidebarTransitioning = false;
            this.sidebarTransitionTimer = null;
            console.log(`[Sidebar] 过渡结束，当前状态 isSidebarOpen=${this.isSidebarOpen}`);
        }, this.sidebarTransitionMs);
    }

    private bindRightSidebarToggleWhenReady(): void {
        const bindToggle = () => {
            if (this.rightSidebarToggleBound) {
                return;
            }

            const rightSidebar = document.getElementById('right-sidebar');
            const sidebarToggle = document.getElementById('sidebar-toggle');

            if (!rightSidebar || !sidebarToggle) {
                console.warn('[Sidebar] 右侧侧边栏元素未就绪，稍后重试绑定');
                window.setTimeout(() => this.bindRightSidebarToggleWhenReady(), 100);
                return;
            }

            this.syncRightSidebarState(rightSidebar, sidebarToggle);
            this.eventBinder.bind(sidebarToggle, 'click', () => this.toggleRightSidebar());
            this.rightSidebarToggleBound = true;
            console.log('[Sidebar] 右侧侧边栏切换事件绑定成功');
        };

        if (document.readyState === 'loading') {
            this.eventBinder.bind(document, 'DOMContentLoaded', bindToggle, { once: true });
            return;
        }

        bindToggle();
    }

    private syncRightSidebarState(rightSidebar?: HTMLElement, sidebarToggle?: HTMLElement): void {
        const sidebarElement = rightSidebar ?? document.getElementById('right-sidebar');
        const toggleElement = sidebarToggle ?? document.getElementById('sidebar-toggle');

        if (!sidebarElement || !toggleElement) {
            return;
        }

        this.isSidebarOpen = !sidebarElement.classList.contains('hidden');
        toggleElement.classList.toggle('open', this.isSidebarOpen);
        toggleElement.setAttribute('aria-expanded', String(this.isSidebarOpen));

        console.log(`[Sidebar] 状态同步完成: isSidebarOpen=${this.isSidebarOpen}, aria-expanded=${toggleElement.getAttribute('aria-expanded')}`);
    }

    private bindMobileSidebarViewportSync(): void {
        if (this.mobileSidebarViewportSyncBound) {
            return;
        }

        const updateKeyboardState = () => {
            const rightSidebar = document.getElementById('right-sidebar');
            if (!rightSidebar) {
                return;
            }

            const viewport = window.visualViewport;
            const isMobileLayout = window.innerWidth <= 767;
            const keyboardVisible = Boolean(
                isMobileLayout &&
                viewport &&
                window.innerHeight - viewport.height > 120
            );

            rightSidebar.classList.toggle('mobile-keyboard-open', keyboardVisible && this.isSidebarOpen);
        };

        this.eventBinder.bind(window, 'resize', updateKeyboardState);
        if (window.visualViewport) {
            this.eventBinder.bind(window.visualViewport, 'resize', updateKeyboardState);
            this.eventBinder.bind(window.visualViewport, 'scroll', updateKeyboardState);
        }

        updateKeyboardState();
        this.mobileSidebarViewportSyncBound = true;
        console.log('[Sidebar] 移动端视口/键盘状态监听已绑定');
    }

    private handleQuickAction(command: string): void {
        if (command.startsWith('wizard-start:')) {
            const wizardId = command.split(':')[1];
            const components = this.componentInitializer.getComponentRegistry();
            components.wizardEngine?.start(wizardId);
            return;
        }

        const components = this.componentInitializer.getComponentRegistry();

        switch (command) {
            case 'new-project':
                this.handleNewProject();
                break;
            case 'import-data': {
                const fileInput = document.getElementById('file-input') as HTMLInputElement | null;
                fileInput?.click();
                break;
            }
            case 'start-kriging': {
                const startBtn = document.getElementById('start-kriging-btn') as HTMLButtonElement | null;
                if (startBtn && !startBtn.disabled) {
                    startBtn.click();
                }
                break;
            }
            case 'export-geojson': {
                const exportBtn = document.getElementById('export-prediction-geojson') as HTMLButtonElement | null;
                const exportPanel = document.getElementById('export-panel');
                if (exportBtn && exportPanel && exportPanel.style.display !== 'none') {
                    exportBtn.click();
                }
                break;
            }
            case 'show-guide':
                components.onboardingGuide.reset();
                components.onboardingGuide.start();
                break;
            case 'history-undo':
                void HistoryManager.undo();
                break;
            case 'history-redo':
                void HistoryManager.redo();
                break;
            case 'open-wizard-center':
                components.wizardEngine?.openWizardCenter();
                break;
            default:
                console.warn('未知快捷操作:', command);
        }
    }

    private handleWizardCompleted(
        wizardId: string,
        values: Record<string, string | number | boolean>
    ): void {
        if (wizardId === 'interpolation-analysis') {
            this.applyInterpolationWizardValues(values);
            const autoStart = Boolean(values.autoStart);
            if (autoStart) {
                const startBtn = document.getElementById('start-kriging-btn') as HTMLButtonElement | null;
                if (startBtn && !startBtn.disabled) {
                    startBtn.click();
                }
            }
            return;
        }

        if (wizardId === 'result-export') {
            this.applyExportWizardValues(values);
            return;
        }

        const uploadStatus = document.getElementById('upload-status');
        if (uploadStatus) {
            uploadStatus.textContent = `向导 ${wizardId} 已完成，可继续执行下一步操作。`;
        }
    }

    private applyInterpolationWizardValues(values: Record<string, string | number | boolean>): void {
        const method = values.krigingMethod;
        const variogram = values.variogramModel;
        const gridResolution = values.gridResolution;
        const nlags = values.nlags;
        const range = values.range;

        this.setSelectValue('kriging-method', method);
        this.setSelectValue('variogram-model', variogram);
        this.setNumberInputValue('grid-resolution', gridResolution, 'grid-resolution-slider', 'grid-resolution-value');
        this.setNumberInputValue('nlags', nlags, 'nlags-slider', 'nlags-value');
        this.setNumberInputValue('range', range, 'range-slider', 'range-value');
    }

    private applyExportWizardValues(values: Record<string, string | number | boolean>): void {
        const targetLayer = values.targetLayer === 'variance' ? 'variance' : 'prediction';
        const format = String(values.exportFormat || 'geojson');
        const buttonId = `export-${targetLayer}-${format === 'geojson' ? 'geojson' : format === 'shp' ? 'shp' : 'tif'}`;
        const exportButton = document.getElementById(buttonId) as HTMLButtonElement | null;

        const exportStatus = document.getElementById('export-status');
        if (exportStatus) {
            exportStatus.textContent = `导出向导已完成：目标=${targetLayer}，格式=${format.toUpperCase()}。`;
        }

        if (exportButton) {
            exportButton.click();
        }
    }

    private setSelectValue(elementId: string, value: string | number | boolean | undefined): void {
        if (value === undefined) {
            return;
        }
        const select = document.getElementById(elementId) as HTMLSelectElement | null;
        if (!select) {
            return;
        }
        select.value = String(value);
        select.dispatchEvent(new Event('change', { bubbles: true }));
    }

    private setNumberInputValue(
        inputId: string,
        value: string | number | boolean | undefined,
        sliderId?: string,
        displayId?: string
    ): void {
        if (value === undefined) {
            return;
        }
        const numeric = Number(value);
        if (Number.isNaN(numeric)) {
            return;
        }

        const input = document.getElementById(inputId) as HTMLInputElement | null;
        if (input) {
            input.value = String(numeric);
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
        }

        if (sliderId) {
            const slider = document.getElementById(sliderId) as HTMLInputElement | null;
            if (slider) {
                slider.value = String(numeric);
                slider.dispatchEvent(new Event('input', { bubbles: true }));
                slider.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        if (displayId) {
            const display = document.getElementById(displayId);
            if (display) {
                display.textContent = String(numeric);
            }
        }
    }

    /**
     * 处理新建项目
     */
    public handleNewProject(): void {
        const modal = new NewProjectModal(
            (project: IProject, config: unknown) => {
                if (!isProjectConfig(config)) {
                    throw new Error('项目配置无效');
                }
                this.onProjectCreated(project, config);
            },
            this.view!
        );
        modal.show();
    }

    /**
     * 项目创建完成回调
     */
    private onProjectCreated(project: IProject, config: ProjectConfig): void {
        console.log('项目创建完成:', project);
        HistoryManager.record({
            action: '新建项目',
            type: 'project',
            detail: `创建了${config.sampling_mode === 'free' ? '自由采样' : '区域采样'}项目`,
            undoable: false
        });

        // 保存当前项目
        this.currentProject = project;
        // 使用时间戳作为项目 ID
        this.stateManager.setState('currentProjectId', Date.now().toString());

        // 清理旧的采样组件
        if (this.samplingComponent) {
            this.samplingComponent.destroy();
        }

        // 创建采样组件
        this.createSamplingComponent(config);
    }

    /**
     * 创建采样组件
     */
    private createSamplingComponent(config: ProjectConfig): void {
        const projectPanel = document.getElementById('project-panel');
        const projectContent = document.getElementById('project-content');

        if (projectContent) {
            projectContent.innerHTML = '';

            if (config.sampling_mode === 'free') {
                this.samplingComponent = new FreeSampling(
                    this.view!,
                    (pointData: SamplingPointValue) => this.handlePointAdded(pointData)
                );
                const panel = this.samplingComponent.createPanel(config.coordinate_mode);
                projectContent.appendChild(panel);
            } else if (config.sampling_mode === 'region') {
                this.samplingComponent = new RegionSampling(
                    this.view!,
                    (pointData: SamplingPointValue) => this.handlePointAdded(pointData)
                );
                const panel = this.samplingComponent.createPanel(config.coordinate_mode);
                projectContent.appendChild(panel);
            }
        }

        if (projectPanel) {
            projectPanel.style.display = 'block';
        }
    }

    /**
     * 处理采样点添加
     */
    private async handlePointAdded(pointData: SamplingPointValue): Promise<void> {
        console.log('添加采样点:', pointData);

        if (!this.currentProject) {
            throw new Error('没有当前项目');
        }

        const normalizedPoint: ExtendedSamplingPoint = {
            x: pointData.longitude,
            y: pointData.latitude,
            value: pointData.value,
            timestamp: pointData.timestamp
        };
        const success = this.currentProject.addPoint(normalizedPoint);

        if (!success) {
            throw new Error('采样点超出区域边界');
        }

        if (this.layerManager) {
            await this.layerManager.addSamplingPoint(normalizedPoint);
        }

        const components = this.componentInitializer.getComponentRegistry();
        const allPoints = this.currentProject?.points || this.layerManager?.getSamplingPoints() || [];
        components.parameterAdjustmentPanel.setSamplingContext(allPoints);

        this.validateGridResolution();
    }

    /**
     * 校验网格分辨率输入
     */
    private validateGridResolution(): boolean {
        const input = document.getElementById('grid-resolution') as HTMLInputElement;
        const errorMsg = document.getElementById('grid-resolution-error') as HTMLElement;
        const startBtn = document.getElementById('start-kriging-btn') as HTMLButtonElement;

        if (!input || !errorMsg || !startBtn) return false;

        const value = input.value.trim();
        const validPattern = /^[1-9]\d*$/;

        if (value === '') {
            input.classList.add('error');
            errorMsg.classList.add('show');
            startBtn.disabled = true;
            return false;
        }

        if (!validPattern.test(value)) {
            input.classList.add('error');
            errorMsg.classList.add('show');
            startBtn.disabled = true;
            return false;
        }

        const numValue = parseInt(value, 10);
        if (numValue > 10000) {
            input.classList.add('error');
            errorMsg.classList.add('show');
            startBtn.disabled = true;
            return false;
        }

        input.classList.remove('error');
        errorMsg.classList.remove('show');

        const hasEnoughPoints = (this.currentProject && this.currentProject.getPointCount() >= 3) ||
                                (this.layerManager && this.layerManager.getSamplingPoints().length >= 3);
        startBtn.disabled = !hasEnoughPoints;

        return true;
    }

    /**
     * 处理文件上传
     */
    private async handleUpload(): Promise<void> {
        const fileInput = document.getElementById('file-input') as HTMLInputElement;
        const file = fileInput?.files && fileInput.files.length > 0 ? fileInput.files[0] : null;

        if (!file) {
            this.showStatus('请选择文件', 'error');
            return;
        }

        if (!GeoJSONParser.validateFileType(file)) {
            this.showStatus('仅支持 .geojson 或 .json 文件', 'error');
            return;
        }

        try {
            console.log('开始解析 GeoJSON 文件');
            LoadingManager.show('正在解析文件...');

            const parseResult: GeoJSONParseResult = await GeoJSONParser.parseFile(file);
            console.log('GeoJSON 解析成功:', parseResult);

            LoadingManager.hide();

            const modal = new DataImportModal((transformedData) => {
                this.handleDataImport(transformedData as TransformedData);
            }, this.view!);

            const modalParseResult: DataImportModalParseResult = {
                ...parseResult,
                crsInfo: {
                    projectedName: parseResult.crsInfo.projectedName,
                    projectedEPSG: parseResult.crsInfo.projectedEPSG !== null
                        ? String(parseResult.crsInfo.projectedEPSG)
                        : undefined,
                    geographicName: parseResult.crsInfo.geographicName,
                    geographicEPSG: String(parseResult.crsInfo.geographicEPSG)
                }
            };
            modal.show(modalParseResult);

        } catch (error) {
            console.error('上传失败:', error);
            LoadingManager.hide();
            const errorMessage = error instanceof Error ? error.message : '未知错误';
            this.showStatus(errorMessage, 'error');
        }
    }

    /**
     * 处理数据导入
     */
    private async handleDataImport(transformedData: TransformedData): Promise<void> {
        try {
            let importedPoints = transformedData.data;
            if (this.computationService.isWorkerEnabled()) {
                try {
                    const preprocessResult = await this.computationService.preprocessSamplingPoints(transformedData.data);
                    importedPoints = preprocessResult.points as SamplingPoint[];
                    if (preprocessResult.removedCount > 0) {
                        this.showStatus(`导入时自动过滤 ${preprocessResult.removedCount} 个无效/重复点`, 'warning');
                    }
                } catch (error) {
                    console.warn('[导入] Worker 预处理失败，继续使用原始点:', error);
                }
            }

            if (this.layerManager) {
                await this.layerManager.addPointsLayer(transformedData.geojson);

                for (const point of importedPoints) {
                    await this.layerManager.addSamplingPoint(point);
                }
            }

            this.showStatus(`数据导入成功！点数: ${importedPoints.length}`, 'success');
            HistoryManager.record({
                action: '导入数据',
                type: 'upload',
                detail: `导入了 ${importedPoints.length} 个采样点`,
                undoable: false
            });

            const components = this.componentInitializer.getComponentRegistry();
            components.parameterAdjustmentPanel.setSamplingContext(importedPoints);
            this.validateGridResolution();

        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : '未知错误';
            this.showStatus(`导入失败: ${errorMessage}`, 'error');
        }
    }

    /**
     * 处理开始插值
     */
    private async handleStartKriging(): Promise<void> {
        if (!this.validateGridResolution()) {
            this.showStatus('网格分辨率输入不合法', 'error');
            return;
        }

        let samplingPoints: SamplingPoint[];

        if (this.currentProject && this.currentProject.getPointCount() > 0) {
            samplingPoints = this.currentProject.points;
        } else {
            samplingPoints = this.layerManager?.getSamplingPoints() || [];
        }

        if (!samplingPoints || samplingPoints.length === 0) {
            this.showStatus('请先上传数据或添加采样点', 'error');
            return;
        }

        if (samplingPoints.length < 3) {
            this.showStatus('至少需要 3 个采样点才能进行插值', 'error');
            return;
        }

        const confirmed = await ConfirmDialog.confirm({
            title: '开始插值计算',
            message: `将使用 ${samplingPoints.length} 个采样点进行克里金插值，确认开始？`,
            confirmText: '开始',
            cancelText: '取消'
        });

        if (!confirmed) return;

        const krigingMethodSelect = document.getElementById('kriging-method') as HTMLSelectElement;
        const variogramModelSelect = document.getElementById('variogram-model') as HTMLSelectElement;
        const components = this.componentInitializer.getComponentRegistry();
        const parameterAdjustmentPanel = components.parameterAdjustmentPanel;
        parameterAdjustmentPanel.setSamplingContext(samplingPoints);
        const adjustmentParams = parameterAdjustmentPanel.getParameters();

        const validation = parameterAdjustmentPanel.validateAll();
        if (!validation.valid) {
            this.showStatus(`参数验证失败: ${validation.errors.join(', ')}`, 'error');
            return;
        }

        let processedSamplingPoints = samplingPoints;
        if (this.computationService.isWorkerEnabled()) {
            try {
                LoadingManager.show('正在预处理采样点数据...', { type: 'progress' });
                const preprocessResult = await this.computationService.preprocessSamplingPoints(
                    samplingPoints,
                    (progress, message) => {
                        if (message) {
                            LoadingManager.updateText(message);
                        }
                        LoadingManager.updateProgress(progress);
                    }
                );

                if (preprocessResult.points.length < 3) {
                    LoadingManager.hide();
                    this.showStatus('预处理后可用采样点不足 3 个，无法执行插值', 'error');
                    return;
                }

                processedSamplingPoints = preprocessResult.points as SamplingPoint[];
                if (preprocessResult.removedCount > 0) {
                    this.showStatus(`已自动过滤 ${preprocessResult.removedCount} 个无效/重复采样点`, 'warning');
                }
            } catch (error) {
                console.warn('[Kriging] Worker 预处理失败，回退主线程原始数据:', error);
                this.showStatus('数据预处理失败，已回退为原始采样点继续计算', 'warning');
            } finally {
                LoadingManager.hide();
            }
        }

        const params: KrigingParams = {
            points: processedSamplingPoints,
            method: (krigingMethodSelect?.value || 'ordinary') as 'ordinary' | 'universal' | 'block',
            variogram_model: (variogramModelSelect?.value || 'spherical') as 'spherical' | 'exponential' | 'gaussian',
            grid_resolution: adjustmentParams['grid-resolution'] || 100,
            nlags: adjustmentParams['nlags'],
            nugget: adjustmentParams['nugget'],
            sill: adjustmentParams['sill'],
            range: adjustmentParams['range'],
            enable_cross_validation: true
        };

        parameterAdjustmentPanel.saveAsLastUsed();

        try {
            LoadingManager.show('正在提交插值任务...');
            const response = await this.apiService!.startKriging(params);
            this.currentTaskId = response.task_id;
            this.stateManager.setState('currentTaskId', this.currentTaskId);
            LoadingManager.hide();

            this.showStatus('任务已启动', 'success');
            this.accessibilityManager?.announce('插值任务已启动，正在后台计算。');
            this.lastAnnouncedProgressBucket = -1;
            HistoryManager.record({
                action: '开始插值',
                type: 'kriging',
                detail: `使用 ${params.method} 方法，${processedSamplingPoints.length} 个采样点`,
                undoable: false
            });
            this.startTaskPolling();

        } catch (error) {
            LoadingManager.hide();
            const errorMessage = error instanceof Error ? error.message : '未知错误';
            this.showStatus(`启动失败: ${errorMessage}`, 'error');
        }
    }

    /**
     * 开始任务轮询
     */
    private startTaskPolling(): void {
        if (this.taskPoller) {
            this.taskPoller.stop();
        }

        const callback: TaskStatusCallback = (status) => this.handleTaskUpdate(status);
        this.taskPoller = new TaskPoller(
            this.apiService!,
            this.currentTaskId!,
            callback
        );

        this.taskPoller.start();
    }

    /**
     * 处理任务状态更新
     */
    private async handleTaskUpdate(status: TaskStatus): Promise<void> {
        const statusDiv = document.getElementById('task-status');
        const progressBar = document.getElementById('progress-bar');
        const progressFill = progressBar?.querySelector('.progress-fill');

        if (statusDiv) {
            statusDiv.innerHTML = `
                <p>状态: ${status.status}</p>
                <p>进度: ${status.progress.toFixed(1)}%</p>
            `;
        }

        if (progressBar && progressFill) {
            progressBar.style.display = 'block';
            progressFill.style.width = `${status.progress}%`;
            progressBar.setAttribute('aria-valuenow', String(Math.round(status.progress)));
        }

        if (status.status === 'completed') {
            this.taskPoller?.stop();
            this.showStatus('插值完成！', 'success');
            this.accessibilityManager?.announce('插值任务已完成。');
            LoadingManager.show('正在加载结果...');
            await this.loadResults();
            LoadingManager.hide();
        } else if (status.status === 'failed') {
            this.taskPoller?.stop();
            this.showStatus(`任务失败: ${status.error}`, 'error');
            this.accessibilityManager?.announce(`任务失败：${status.error || '未知错误'}`, 'assertive');
        } else {
            const progressBucket = Math.floor(status.progress / 25);
            if (progressBucket > this.lastAnnouncedProgressBucket) {
                this.lastAnnouncedProgressBucket = progressBucket;
                this.accessibilityManager?.announce(`任务进度 ${Math.round(status.progress)}%`);
            }
        }
    }

    /**
     * 加载结果
     */
    private async loadResults(): Promise<void> {
        try {
            const predictionResult = await this.apiService!.getPredictionResult(this.currentTaskId!);
            const varianceResult = await this.apiService!.getVarianceResult(this.currentTaskId!);

            if (this.layerManager) {
                this.layerManager.addRasterLayer('prediction', predictionResult.geotiff_url);
                this.layerManager.addRasterLayer('variance', varianceResult.geotiff_url);
            }

            const exportPanel = document.getElementById('export-panel');
            if (exportPanel) {
                exportPanel.style.display = 'block';
            }

            const components = this.componentInitializer.getComponentRegistry();
            if (components.recommendationPanel && this.currentTaskId) {
                components.recommendationPanel.setTaskId(this.currentTaskId);
            }

        } catch (error) {
            console.error('加载结果失败:', error);
        }
    }

    /**
     * 处理导出
     */
    private async handleExport(dataType: string, format: string): Promise<void> {
        if (!this.currentTaskId) {
            this.showExportStatus('没有可导出的结果', 'error');
            return;
        }

        const filename = `${this.currentTaskId}_${dataType}.${format}`;
        LoadingManager.show(`正在导出 ${filename}...`);
        this.showExportStatus(`正在下载 ${filename}...`, 'success');

        try {
            await this.apiService!.downloadExportFile(this.currentTaskId, filename);
            LoadingManager.hide();
            this.showExportStatus(`${filename} 下载完成`, 'success');
            HistoryManager.record({
                action: '导出结果',
                type: 'export',
                detail: `导出了 ${filename}`,
                undoable: false
            });
        } catch (error) {
            console.error('导出失败:', error);
            LoadingManager.hide();
            const errorMessage = error instanceof Error ? error.message : '未知错误';
            this.showExportStatus(`导出失败: ${errorMessage}`, 'error');
        }
    }

    /**
     * 绑定导出按钮
     */
    private _bindExportButtons(): void {
        const bindButton = (id: string, dataType: string, format: string) => {
            this.eventBinder.bindBySelector(`#${id}`, 'click', () => {
                this.handleExport(dataType, format);
            });
        };

        bindButton('export-prediction-geojson', 'prediction', 'geojson');
        bindButton('export-prediction-shp', 'prediction', 'shp');
        bindButton('export-prediction-tif', 'prediction', 'tif');
        bindButton('export-variance-geojson', 'variance', 'geojson');
        bindButton('export-variance-shp', 'variance', 'shp');
        bindButton('export-variance-tif', 'variance', 'tif');

        // 增强导出
        this.eventBinder.bindBySelector('#export-csv', 'click', () => {
            const points = this.currentProject?.points || this.layerManager?.getSamplingPoints() || [];
            if (points.length === 0) {
                this.showExportStatus('没有可导出的采样点', 'error');
                return;
            }
            ExportEnhancer.exportPointsCSV(points);
            HistoryManager.record({
                action: '导出CSV',
                type: 'export',
                detail: `导出了 ${points.length} 个采样点`,
                undoable: false
            });
        });

        this.eventBinder.bindBySelector('#export-report', 'click', () => {
            if (!this.currentTaskId) {
                this.showExportStatus('没有可生成报告的任务', 'error');
                return;
            }
            const krigingMethodSelect = document.getElementById('kriging-method') as HTMLSelectElement;
            const gridResolutionInput = document.getElementById('grid-resolution') as HTMLInputElement;
            ExportEnhancer.generateHTMLReport({
                taskId: this.currentTaskId,
                method: krigingMethodSelect?.value || '',
                pointCount: (this.currentProject?.points || this.layerManager?.getSamplingPoints() || []).length,
                gridResolution: parseInt(gridResolutionInput?.value || '10', 10)
            });
            HistoryManager.record({
                action: '生成报告',
                type: 'export',
                detail: `生成了任务 ${this.currentTaskId} 的分析报告`,
                undoable: false
            });
        });
    }

    /**
     * 显示导出状态
     */
    private showExportStatus(message: string, type: string): void {
        const statusDiv = document.getElementById('export-status');
        if (statusDiv) {
            statusDiv.textContent = message;
            statusDiv.className = `status-message ${type}`;
        }
        this.accessibilityManager?.announce(message, type === 'error' ? 'assertive' : 'polite');
    }

    /**
     * 显示状态
     */
    private showStatus(message: string, type: string): void {
        const statusDiv = document.getElementById('upload-status');
        if (statusDiv) {
            statusDiv.textContent = message;
            statusDiv.className = `status-message ${type}`;
        }
        this.accessibilityManager?.announce(message, type === 'error' ? 'assertive' : 'polite');
    }

    /**
     * 显示偏好设置面板
     */
    private showPreferences(): void {
        const components = this.componentInitializer.getComponentRegistry();
        if (!components.preferencesPanel) {
            const callback = (prefs: { theme: 'light' | 'dark' | 'auto'; animationsEnabled: boolean; gridResolution: number }) => {
                if (prefs.theme === 'dark') {
                    ThemeManager.set('dark');
                } else if (prefs.theme === 'light') {
                    ThemeManager.set('light');
                } else if (prefs.theme === 'auto') {
                    ThemeManager.set('auto');
                }

                document.documentElement.style.setProperty(
                    '--transition-fast',
                    prefs.animationsEnabled ? '0.2s ease' : '0s'
                );

                const gridInput = document.getElementById('grid-resolution') as HTMLInputElement;
                if (gridInput && !gridInput.value) {
                    gridInput.value = String(prefs.gridResolution);
                }
            };

            const panel = new PreferencesPanel(callback);
            panel.show();
        } else {
            components.preferencesPanel.show();
        }
    }

    /**
     * 处理地图引擎切换
     */
    private async handleMapEngineSwitch(newProvider: MapProvider): Promise<void> {
        // 检查是否正在切换，防止重复切换
        if (this.isSwitchingMap) {
            Logger.warn('主程序', '地图引擎正在切换中，请稍候');
            return;
        }

        const previousProvider = MapConfig.getProvider() as MapProvider;
        if (newProvider === previousProvider) {
            Logger.info('主程序', `当前已经是 ${getMapEngineDisplayName(newProvider)} 引擎，无需切换`);
            return;
        }

        const newProviderName = getMapEngineDisplayName(newProvider);
        let samplingPoints: SamplingPoint[] = [];
        let projectPoints: SamplingPoint[] = [];
        let currentCenter: [number, number] | { lng: number; lat: number } | null = null;
        let currentZoom: number | null = null;

        this.isSwitchingMap = true;
        this.mapSwitchAbortController?.abort();
        this.mapSwitchAbortController = new AbortController();
        const currentSwitchController = this.mapSwitchAbortController;
        const currentSwitchSession = ++this.mapSwitchSessionId;
        const ensureSwitchAlive = () => {
            if (
                currentSwitchController.signal.aborted ||
                currentSwitchSession !== this.mapSwitchSessionId
            ) {
                throw new DOMException('地图切换已取消', 'AbortError');
            }
        };

        try {
            LoadingManager.show('正在切换地图引擎...');
            ensureSwitchAlive();

            currentCenter = this.view ? (this.view as { getCenter?: () => [number, number] | { lng: number; lat: number } }).getCenter?.() || null : null;
            currentZoom = this.view ? (this.view as { getZoom?: () => number }).getZoom?.() || null : null;
            samplingPoints = this.layerManager?.getSamplingPoints() || [];
            projectPoints = this.currentProject?.points || [];
            const previousAdapter = this.layerManager?.adapter;

            if (this.layerManager) {
                this.layerManager.clearAllLayers();
            }

            // 先销毁旧地图引擎，避免旧 iframe / 事件监听残留导致竞态
            previousAdapter?.destroy?.();
            abortAllAMapLoads();

            // 清理旧的iframe，确保完全移除
            const iframes = document.querySelectorAll('iframe[id^="amap-loader-iframe"]');
            iframes.forEach(iframe => {
                if (iframe.parentNode) {
                    iframe.parentNode.removeChild(iframe);
                }
            });

            // 等待DOM完全更新，确保iframe完全清理（增加延迟以确保所有异步操作完成）
            await new Promise<void>((resolve, reject) => {
                const timeoutId = window.setTimeout(resolve, 300);
                currentSwitchController.signal.addEventListener('abort', () => {
                    clearTimeout(timeoutId);
                    reject(new DOMException('地图切换已取消', 'AbortError'));
                }, { once: true });
            });
            ensureSwitchAlive();

            const mapContainer = document.getElementById('viewDiv');
            if (mapContainer) {
                mapContainer.style.visibility = 'visible';
            }

            const mapAdapter = await Promise.race([
                reinitializeMap('viewDiv', newProvider),
                new Promise<never>((_, reject) => {
                    const timeoutMs = AppConfig.map.switchTimeoutMs;
                    setTimeout(() => reject(new Error(`地图引擎切换超时（${Math.floor(timeoutMs / 1000)}秒）`)), timeoutMs);
                })
            ]);
            ensureSwitchAlive();
            this.view = mapAdapter.getView();
            this.layerManager = new LayerManager(mapAdapter);
            this.componentInitializer.updateMapContext({
                layerManager: this.layerManager,
                view: this.view ?? undefined
            });

            if (currentCenter && currentZoom) {
                const center: [number, number] = Array.isArray(currentCenter)
                    ? [currentCenter[0], currentCenter[1]]
                    : [currentCenter.lng, currentCenter.lat];
                (this.view as MapViewWithCamera).setCenter?.(center);
                (this.view as MapViewWithCamera).setZoom?.(currentZoom);
            }

            const pointsToRestore = projectPoints.length > 0 ? projectPoints : samplingPoints;
            for (const point of pointsToRestore) {
                await this.layerManager.addSamplingPoint(point);
            }

            if (this.samplingComponent) {
                (this.samplingComponent as SamplingComponentWithView).view = this.view;
            }

            LoadingManager.hide();
            this.showStatus(`已切换到 ${newProviderName} 地图引擎`, 'success');

            HistoryManager.record({
                action: '切换地图引擎',
                type: 'map',
                detail: `切换到 ${newProviderName} 地图引擎`,
                undoable: false
            });

        } catch (error) {
            LoadingManager.hide();
            if (error instanceof DOMException && error.name === 'AbortError') {
                Logger.warn('主程序', '地图切换被取消');
                return;
            }
            Logger.error('主程序', '地图引擎切换失败，尝试回滚', error);
            try {
                const rollbackAdapter = await Promise.race([
                    reinitializeMap('viewDiv', previousProvider),
                    new Promise<never>((_, reject) => {
                        const timeoutMs = AppConfig.map.switchTimeoutMs;
                        setTimeout(() => reject(new Error(`地图引擎回滚超时（${Math.floor(timeoutMs / 1000)}秒）`)), timeoutMs);
                    })
                ]);
                this.view = rollbackAdapter.getView();
                this.layerManager = new LayerManager(rollbackAdapter);
                this.componentInitializer.updateMapContext({
                    layerManager: this.layerManager,
                    view: this.view ?? undefined
                });

                if (currentCenter && currentZoom !== null) {
                    const center = Array.isArray(currentCenter) ? currentCenter : [currentCenter.lng, currentCenter.lat];
                    (this.view as { setCenter?: (center: [number, number]) => void }).setCenter?.(center as [number, number]);
                    (this.view as { setZoom?: (zoom: number) => void }).setZoom?.(currentZoom);
                }

                const pointsToRestore = projectPoints.length > 0 ? projectPoints : samplingPoints;
                for (const point of pointsToRestore) {
                    await this.layerManager.addSamplingPoint(point);
                }
            } catch (rollbackError) {
                Logger.error('主程序', '地图引擎回滚失败', rollbackError);
            }
            const errorMessage = error instanceof Error ? error.message : '未知错误';
            this.showStatus(`切换失败: ${errorMessage}`, 'error');
            throw error;
        } finally {
            // 重置切换状态标志
            this.isSwitchingMap = false;
            if (this.mapSwitchAbortController === currentSwitchController) {
                this.mapSwitchAbortController = null;
            }
        }
    }

    /**
     * 处理回到中心
     */
    private async handleLocationCenter(): Promise<void> {
        if (!this.layerManager) {
            console.warn('⚠️ LayerManager 不存在');
            return;
        }

        try {
            const mapAdapter = this.layerManager.adapter;
            if (!mapAdapter) {
                console.warn('⚠️ 地图适配器不存在');
                return;
            }

            const engine = mapAdapter.getEngine();
            if (!engine) {
                console.warn('⚠️ 地图引擎不存在');
                return;
            }

            const { AMapEngine } = await import('./map/core/AMapEngine.js');
            if (engine instanceof AMapEngine) {
                const success = engine.panToLocation();
                if (success) {
                    this.showStatus('已回到当前位置', 'success');
                } else {
                    this.showStatus('定位蓝点不存在，无法回到中心', 'warning');
                }
            } else {
                this.showStatus('当前地图引擎不支持回到中心功能', 'warning');
            }
        } catch (error) {
            console.error('❌ 回到中心失败:', error);
            this.showStatus('回到中心失败', 'error');
        }
    }

    /**
     * 绑定离线横幅事件
     */
    private bindOfflineBannerEvents(): void {
        this.eventBinder.bind(document, 'offline-view-cache', (event) => {
            console.log('查看缓存数据事件触发', event);
            this.handleViewCacheData();
        });

        this.eventBinder.bind(document, 'offline-manage-cache', (event) => {
            console.log('管理缓存事件触发', event);
            this.handleManageCache();
        });
    }

    /**
     * 处理查看缓存数据
     */
    private handleViewCacheData(): void {
        console.log('显示本地缓存数据');

        OfflineManager.getAllProjects().then(projects => {
            console.log('本地项目列表:', projects);
        }).catch(error => {
            console.error('获取本地项目失败:', error);
        });
    }

    /**
     * 处理管理缓存
     */
    private handleManageCache(): void {
        const components = this.componentInitializer.getComponentRegistry();
        if (components.cacheManagementPanel) {
            components.cacheManagementPanel.show();
        }
    }

    /**
     * 初始化3D克里金面板
     */
    private async initializeKriging3DPanel(): Promise<void> {
        const container = document.getElementById('kriging3d-container');
        if (container) {
            const skeleton = SkeletonLoader.show(container, 'panel', { lines: 4 });
            try {
                const module = await import('./components/Kriging3DPanel.js');
                this.kriging3DPanel = new module.Kriging3DPanel('kriging3d-container');
                console.log('3D克里金面板初始化成功');
            } catch (error) {
                console.error('3D克里金面板初始化失败:', error);
                container.innerHTML = '<div class="status-message error">3D 克里金模块加载失败，请稍后重试</div>';
            } finally {
                SkeletonLoader.hide(skeleton);
            }
        }
    }

    /**
     * 初始化深度学习面板
     */
    private async initializeDeepLearningPanel(): Promise<void> {
        const section = document.getElementById('deep-learning-section');
        const container = document.getElementById('deep-learning-container');
        const legacyApiServer = (this as unknown as { apiServer?: IAPIService | null }).apiServer ?? null;
        const panelApiService = this.apiService ?? legacyApiServer;

        if (!section || !container || !panelApiService) {
            console.warn('[深度学习面板] 初始化跳过:', {
                hasSection: Boolean(section),
                hasContainer: Boolean(container),
                hasApiService: Boolean(this.apiService),
                hasLegacyApiServer: Boolean(legacyApiServer)
            });
            return;
        }

        const skeleton = SkeletonLoader.show(container, 'panel', { lines: 5 });
        try {
            const module = await import('./components/DeepLearningPanel.js');
            this.deepLearningPanel = new module.DeepLearningPanel(
                'deep-learning-section',
                'deep-learning-container',
                panelApiService
            );
            this.componentInitializer.registerComponent('deepLearningPanel', this.deepLearningPanel);
            console.log('深度学习面板初始化成功');
        } catch (error) {
            console.error('深度学习面板初始化失败:', error);
            container.innerHTML = '<div class="status-message error">深度学习模块加载失败，请刷新后重试</div>';
        } finally {
            SkeletonLoader.hide(skeleton);
        }
    }

    /**
     * 初始化前端功能集成补齐面板
     */
    private async initializeFrontendIntegrationPanel(): Promise<void> {
        if (!(this.apiService instanceof APIService)) {
            console.warn('[前端功能集成面板] 初始化跳过: APIService 不可用');
            return;
        }

        const container = document.getElementById('frontend-integration-container');
        const skeleton = container ? SkeletonLoader.show(container, 'panel', { lines: 5 }) : null;
        try {
            const module = await import('./components/FrontendIntegrationHub.js');
            this.frontendIntegrationHub = new module.FrontendIntegrationHub(
                'frontend-integration-section',
                'frontend-integration-container',
                this.apiService
            );
            this.frontendIntegrationHub.init();
            console.log('前端功能集成补齐面板初始化成功');
        } catch (error) {
            console.error('前端功能集成补齐面板初始化失败:', error);
            if (container) {
                container.innerHTML = '<div class="status-message error">功能集成模块加载失败，请稍后重试</div>';
            }
        } finally {
            SkeletonLoader.hide(skeleton);
        }
    }

    /**
     * 初始化缓存状态面板
     */
    private initializeCacheStatusPanel(): void {
        this.eventBinder.bindBySelector('#open-cache-management', 'click', () => {
            this.handleManageCache();
        });

        this.updateCacheStatusPanel();

        OfflineManager.onStatusChange((online) => {
            this.updateCacheStatusPanel();
        });

        setInterval(() => {
            this.updateCacheStatusPanel();
        }, 30000);
    }

    /**
     * 更新缓存状态面板
     */
    private async updateCacheStatusPanel(): Promise<void> {
        const networkIcon = document.getElementById('cache-network-icon');
        const networkStatus = document.getElementById('cache-network-status');
        if (networkIcon && networkStatus) {
            const isOnline = OfflineManager.isOnline;
            networkIcon.className = `cache-status-icon ${isOnline ? 'online' : 'offline'}`;
            networkStatus.textContent = isOnline ? '在线' : '离线';
        }

        const storageFill = document.getElementById('cache-storage-fill');
        const storageText = document.getElementById('cache-storage-text');
        if (storageFill && storageText) {
            try {
                const cacheInfo = await this.getCacheInfo();
                const totalSize = cacheInfo.reduce((sum, info) => sum + info.size, 0);
                const maxStorage = 50 * 1024 * 1024;
                const percentage = (totalSize / maxStorage) * 100;

                storageFill.style.width = `${Math.min(percentage, 100)}%`;
                storageFill.className = 'cache-storage-fill';
                if (percentage > 80) {
                    storageFill.classList.add('danger');
                } else if (percentage > 60) {
                    storageFill.classList.add('warning');
                }

                storageText.textContent = `${this.formatBytes(totalSize)} / 50 MB`;
            } catch (error) {
                console.error('更新存储状态失败:', error);
            }
        }

        const pendingCount = document.getElementById('cache-pending-count');
        if (pendingCount) {
            try {
                const count = await OfflineManager.getPendingCount();
                pendingCount.textContent = count.toString();
            } catch (error) {
                console.error('更新待同步数量失败:', error);
            }
        }
    }

    /**
     * 获取缓存信息
     */
    private async getCacheInfo(): Promise<{ name: string; size: number; count: number; description: string }[]> {
        return [
            {
                name: '项目数据',
                size: 1024 * 1024,
                count: 3,
                description: '本地保存的项目信息'
            },
            {
                name: '采样点',
                size: 5 * 1024 * 1024,
                count: 150,
                description: '离线采样的点位数据'
            },
            {
                name: '结果缓存',
                size: 10 * 1024 * 1024,
                count: 8,
                description: '插值和计算结果'
            }
        ];
    }

    /**
     * 格式化字节数
     */
    private formatBytes(bytes: number): string {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * 初始化位置服务
     */
    private async initializeLocationService(): Promise<void> {
        try {
            console.log('开始初始化位置服务...');

            if (!this.view) {
                console.warn('地图未初始化，跳过位置服务初始化');
                return;
            }

            const { createLocationServiceIntegration } = await import('./位置服务集成示例.js');
            this.locationServiceIntegration = createLocationServiceIntegration(this.view);
            await this.locationServiceIntegration.initialize();

            console.log('位置服务初始化成功');
        } catch (error) {
            console.error('位置服务初始化失败:', error);
        }
    }

    /**
     * 更新界面文本
     */
    private updateUIText(): void {
        I18n.applyToDOM(document);
        this.languageSwitcher?.render();
        this.accessibilityManager?.refresh();

        // 更新标题
        const titleZh = document.querySelector('.title-zh');
        const titleEn = document.querySelector('.title-en');
        if (titleZh && titleEn) {
            if (I18n.locale === 'zh-CN') {
                titleZh.style.display = 'inline';
                titleEn.style.display = 'none';
            } else {
                titleZh.style.display = 'none';
                titleEn.style.display = 'inline';
            }
        }
    }
}

/**
 * 按钮涟漪效果
 */
function initRippleEffect(): void {
    document.addEventListener('click', (e) => {
        const target = e.target as HTMLElement;
        const btn = target.closest('.btn');
        if (!btn) return;

        const ripple = document.createElement('span');
        ripple.className = 'btn-ripple';
        const rect = btn.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        ripple.style.width = ripple.style.height = `${size}px`;
        ripple.style.left = `${e.clientX - rect.left - size / 2}px`;
        ripple.style.top = `${e.clientY - rect.top - size / 2}px`;
        btn.appendChild(ripple);
        ripple.addEventListener('animationend', () => ripple.remove());
    });
}

/**
 * 键盘快捷键
 */
function initKeyboardShortcuts(app: App): void {
    KeyboardManager.register({
        key: 'Escape',
        description: '关闭弹窗/侧边栏',
        handler: () => {
            const sidebar = document.querySelector('.sidebar.mobile-open');
            if (sidebar) {
                sidebar.classList.remove('mobile-open');
                const overlay = document.getElementById('sidebar-overlay');
                if (overlay) {
                    overlay.classList.remove('visible');
                    overlay.setAttribute('aria-hidden', 'true');
                }
                const toggle = document.getElementById('sidebar-mobile-toggle');
                if (toggle) {
                    toggle.textContent = '☰';
                    toggle.setAttribute('aria-expanded', 'false');
                }
                return;
            }
            const modal = document.querySelector('.modal-overlay.modal-show');
            if (modal) {
                modal.classList.remove('modal-show');
                setTimeout(() => modal.remove(), 300);
            }
        }
    });

    KeyboardManager.register({
        key: 'n',
        ctrl: true,
        description: '新建项目',
        handler: () => app.handleNewProject()
    });

    KeyboardManager.register({
        key: 'u',
        ctrl: true,
        description: '上传数据',
        handler: () => {
            const fileInput = document.getElementById('file-input') as HTMLInputElement;
            fileInput?.click();
        }
    });

    KeyboardManager.register({
        key: 'Enter',
        ctrl: true,
        description: '开始插值',
        handler: () => {
            const btn = document.getElementById('start-kriging-btn') as HTMLButtonElement;
            if (btn && !btn.disabled) {
                btn.click();
            }
        }
    });

    KeyboardManager.register({
        key: 's',
        ctrl: true,
        description: '导出结果',
        handler: () => {
            const exportPanel = document.getElementById('export-panel');
            if (exportPanel && exportPanel.style.display !== 'none') {
                const exportBtn = document.getElementById('export-prediction-geojson');
                exportBtn?.click();
            }
        }
    });

    KeyboardManager.register({
        key: 'd',
        ctrl: true,
        shift: true,
        description: '切换主题',
        handler: () => ThemeManager.toggle()
    });

    KeyboardManager.register({
        key: 'z',
        ctrl: true,
        description: '撤销',
        handler: () => HistoryManager.undo()
    });

    KeyboardManager.register({
        key: 'z',
        ctrl: true,
        shift: true,
        description: '重做',
        handler: () => HistoryManager.redo()
    });

    KeyboardManager.init();
}

// 初始化交互增强
initRippleEffect();

// 注册 Service Worker
window.addEventListener('load', () => {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
    const isSupportedProtocol = protocol === 'https:' || isLocalhost;
    const canRegisterSW =
        'serviceWorker' in navigator &&
        window.isSecureContext &&
        isSupportedProtocol;

    if (!canRegisterSW) {
        try {
            localStorage.setItem('udake-offline-fallback-enabled', 'true');
            localStorage.setItem(
                'udake-offline-fallback-reason',
                `SW 不可用，协议: ${protocol}, 安全上下文: ${String(window.isSecureContext)}`
            );
        } catch {
            // localStorage 不可用时静默降级
        }
        console.warn('Service Worker 不可用，已启用 localStorage 离线降级');
        return;
    }

    navigator.serviceWorker.register('/sw.js').catch((error) => {
        try {
            localStorage.setItem('udake-offline-fallback-enabled', 'true');
            localStorage.setItem('udake-offline-fallback-reason', 'SW 注册失败');
        } catch {
            // localStorage 不可用时静默降级
        }
        console.warn('Service Worker 注册失败，已启用 localStorage 离线降级:', error);
    });
});

// 启动应用
const app = new App();
initKeyboardShortcuts(app);
