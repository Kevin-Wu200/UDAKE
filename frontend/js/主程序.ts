/**
 * UDAKE 主程序
 * 应用程序入口和核心逻辑
 */

import { initializeMap, getMapProvider, reinitializeMap } from './地图初始化.js';
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
import { HistoryManager } from './utils/HistoryManager.js';
import { PerformanceMonitor } from './utils/PerformanceMonitor.js';
import { SplashScreen } from './components/SplashScreen.js';
import { LaunchProgressManager } from './utils/LaunchProgressManager.js';
import { FeedbackCollector } from './components/FeedbackCollector.js';
import { PreferencesPanel } from './components/PreferencesPanel.js';
import { StartupManager } from './utils/StartupManager.js';
import { ResourceOptimizationManager } from './config/ResourceOptimizationConfig.js';

// 导入管理器
import { ComponentInitializer } from './managers/ComponentInitializer.js';
import { EventBinder } from './managers/EventBinder.js';
import { StateManager } from './managers/StateManager.js';

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

// 初始化全局工具
console.log('主程序已执行');
ThemeManager.init();
PerformanceMonitor.init();
HistoryManager.init();
I18n.init();
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

    // 管理器
    private componentInitializer: ComponentInitializer;
    private eventBinder: EventBinder;
    private stateManager: StateManager;

    // 启动相关
    private splashScreen: SplashScreen | null = null;
    private launchProgressManager: LaunchProgressManager | null = null;
    private startupManager: StartupManager | null = null;
    private resourceOptimizationManager: ResourceOptimizationManager | null = null;

    // 工具
    private formValidator: FormValidator | null = null;
    private locationServiceIntegration: any = null;

    constructor() {
        console.log('App 构造函数执行');

        // 初始化管理器
        this.componentInitializer = new ComponentInitializer();
        this.eventBinder = EventBinder.getInstance();
        this.stateManager = StateManager.getInstance();

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
        console.log('init 被执行');

        try {
            // 阶段0：初始化核心管理器
            console.log('初始化启动管理器');
            this.startupManager = StartupManager.getInstance({
                enablePerformanceMonitoring: true,
                enableResourcePreload: true,
                minDisplayTime: 2500,
                enableSkipButton: true,
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
                showSkipButton: true,
                showProgress: true,
                minDisplayTime: 2500
            });
            this.splashScreen.show();

            // 设置进度回调
            this.launchProgressManager.setCallbacks({
                onStageStart: (stage) => {
                    this.splashScreen?.updateStatus(stage.description);
                    this.splashScreen?.setStage('loading');
                },
                onTotalProgress: (total) => {
                    this.splashScreen?.updateProgress(total);
                }
            });

            // 阶段1：完成初始化准备
            await this.launchProgressManager.executeStage('initialize', async () => {
                console.log('初始化准备完成');
            });

            // 阶段2：连接后端
            const backendPort = await this.launchProgressManager.executeStage('backend-connection', async (updateProgress) => {
                updateProgress(20);
                let port = 8000;

                if (window.electronAPI) {
                    try {
                        port = await window.electronAPI.getBackendPort();
                        console.log('获取端口完成，端口:', port);
                    } catch (error) {
                        console.warn('获取端口失败', error);
                    }
                }

                updateProgress(80);
                return port;
            });

            const apiURL = `http://localhost:${backendPort}/api`;

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
                this.bindEvents();
                this.bindMobileEvents();
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
                console.log('准备初始化新手引导');
                updateProgress(50);
                const components = this.componentInitializer.getComponentRegistry();
                components.onboardingGuide.autoStart();
                updateProgress(100);
            });

            // 设置启动画面为就绪状态
            this.splashScreen?.setStage('ready');
            this.splashScreen?.updateStatus('准备就绪');
            this.splashScreen?.updateProgress(100);

            // 隐藏启动画面
            await this.splashScreen?.hide();

            LoadingManager.hide();
            PerformanceMonitor.mark('appReady');
            PerformanceMonitor.measure('appInitTime', 'appStart', 'appReady');

            // 完成StartupManager
            await this.startupManager.complete();

            // 延迟初始化非关键组件
            this.deferredInitialization();

            // 标记为已初始化
            this.stateManager.setState('initialized', true);

        } catch (error) {
            console.error('启动过程出错:', error);
            this.splashScreen?.setStage('error');
            this.splashScreen?.updateStatus('启动失败，请重试');

            if (this.startupManager) {
                await this.startupManager.handleStartupError(error as Error, 'app-init');
            } else {
                throw error;
            }
        }
    }

    /**
     * 延迟初始化非关键组件
     */
    private deferredInitialization(): void {
        if ('requestIdleCallback' in window) {
            requestIdleCallback(() => {
                this.initializeNonCriticalComponents();
            }, { timeout: 2000 });
        } else {
            setTimeout(() => {
                this.initializeNonCriticalComponents();
            }, 100);
        }
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
            OfflineManager.registerHandler('upload', async (payload: any) => {
                const formData = new FormData();
                formData.append('file', payload.file);
                if (this.apiService) {
                    await this.apiService.request(`${this.apiService.baseURL}/upload-data`, {
                        method: 'POST',
                        body: formData
                    });
                }
            });

            OfflineManager.registerHandler('kriging', async (payload: any) => {
                if (this.apiService) {
                    await this.apiService.startKriging(payload);
                }
            });

            // 初始化缓存管理和离线横幅
            const components = this.componentInitializer.getComponentRegistry();
            await components.cacheManagementPanel.init();
            await components.offlineModeBanner.init();

            // 绑定离线横幅事件
            this.bindOfflineBannerEvents();

            // 初始化缓存状态面板
            this.initializeCacheStatusPanel();

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
        }

        // 侧边栏切换
        this.eventBinder.bindBySelector('#sidebar-toggle', 'click', () => this.toggleRightSidebar());
    }

    /**
     * 切换右侧侧边栏
     */
    private toggleRightSidebar(): void {
        const rightSidebar = document.getElementById('right-sidebar');
        const sidebarToggle = document.getElementById('sidebar-toggle');

        if (rightSidebar && sidebarToggle) {
            if (rightSidebar.classList.contains('hidden')) {
                rightSidebar.classList.remove('hidden');
                sidebarToggle.classList.remove('open');
                sidebarToggle.setAttribute('aria-expanded', 'true');
            } else {
                rightSidebar.classList.add('hidden');
                sidebarToggle.classList.add('open');
                sidebarToggle.setAttribute('aria-expanded', 'false');
            }
        }
    }

    /**
     * 处理新建项目
     */
    public handleNewProject(): void {
        const modal = new NewProjectModal(
            (project, config) => this.onProjectCreated(project, config),
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
                    (pointData: any) => this.handlePointAdded(pointData)
                );
                const panel = this.samplingComponent.createPanel(config.coordinate_mode);
                projectContent.appendChild(panel);
            } else if (config.sampling_mode === 'region') {
                this.samplingComponent = new RegionSampling(
                    this.view!,
                    (pointData: any) => this.handlePointAdded(pointData)
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
    private async handlePointAdded(pointData: ExtendedSamplingPoint): Promise<void> {
        console.log('添加采样点:', pointData);

        if (!this.currentProject) {
            throw new Error('没有当前项目');
        }

        const success = this.currentProject.addPoint(pointData);

        if (!success) {
            throw new Error('采样点超出区域边界');
        }

        if (this.layerManager) {
            await this.layerManager.addSamplingPoint(pointData);
        }

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

            const parseResult = await GeoJSONParser.parseFile(file) as any;
            console.log('GeoJSON 解析成功:', parseResult);

            LoadingManager.hide();

            const modal = new DataImportModal((transformedData) => {
                this.handleDataImport(transformedData as TransformedData);
            }, this.view!);

            modal.show(parseResult);

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
            if (this.layerManager) {
                await this.layerManager.addPointsLayer(transformedData.geojson);

                for (const point of transformedData.data) {
                    await this.layerManager.addSamplingPoint(point);
                }
            }

            this.showStatus(`数据导入成功！点数: ${transformedData.data.length}`, 'success');
            HistoryManager.record({
                action: '导入数据',
                type: 'upload',
                detail: `导入了 ${transformedData.data.length} 个采样点`,
                undoable: false
            });

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
        const adjustmentParams = parameterAdjustmentPanel.getParameters();

        const validation = parameterAdjustmentPanel.validateAll();
        if (!validation.valid) {
            this.showStatus(`参数验证失败: ${validation.errors.join(', ')}`, 'error');
            return;
        }

        const params: KrigingParams = {
            points: samplingPoints,
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
            HistoryManager.record({
                action: '开始插值',
                type: 'kriging',
                detail: `使用 ${params.method} 方法，${samplingPoints.length} 个采样点`,
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
            LoadingManager.show('正在加载结果...');
            await this.loadResults();
            LoadingManager.hide();
        } else if (status.status === 'failed') {
            this.taskPoller?.stop();
            this.showStatus(`任务失败: ${status.error}`, 'error');
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
    private async handleMapEngineSwitch(newProvider: 'arcgis' | 'amap'): Promise<void> {
        // 检查是否正在切换，防止重复切换
        if (this.isSwitchingMap) {
            console.warn('⚠️ 地图引擎正在切换中，请稍候');
            return;
        }

        this.isSwitchingMap = true;

        try {
            LoadingManager.show('正在切换地图引擎...');

            const currentCenter = this.view ? (this.view as any).getCenter?.() : null;
            const currentZoom = this.view ? (this.view as any).getZoom?.() : null;
            const samplingPoints = this.layerManager?.getSamplingPoints() || [];
            const projectPoints = this.currentProject?.points || [];

            if (this.layerManager) {
                this.layerManager.clearAllLayers();
            }

            // 清理旧的iframe，确保完全移除
            const iframes = document.querySelectorAll('iframe[id^="amap-loader-iframe"]');
            iframes.forEach(iframe => {
                if (iframe.parentNode) {
                    iframe.parentNode.removeChild(iframe);
                }
            });

            // 等待DOM完全更新，确保iframe完全清理（增加延迟以确保所有异步操作完成）
            await new Promise(resolve => setTimeout(resolve, 300));

            const mapContainer = document.getElementById('viewDiv');
            if (mapContainer) {
                mapContainer.style.visibility = 'visible';
            }

            const mapAdapter = await reinitializeMap('viewDiv', newProvider);
            this.view = mapAdapter.getView();
            this.layerManager = new LayerManager(mapAdapter);

            if (currentCenter && currentZoom) {
                const center = Array.isArray(currentCenter)
                    ? currentCenter
                    : [currentCenter.lng, currentCenter.lat];
                (this.view as any).setCenter?.(center);
                (this.view as any).setZoom?.(currentZoom);
            }

            const pointsToRestore = projectPoints.length > 0 ? projectPoints : samplingPoints;
            for (const point of pointsToRestore) {
                await this.layerManager.addSamplingPoint(point);
            }

            if (this.samplingComponent) {
                (this.samplingComponent as any).view = this.view;
            }

            LoadingManager.hide();
            this.showStatus(`已切换到 ${newProvider === 'arcgis' ? 'ArcGIS' : '高德'} 地图引擎`, 'success');

            HistoryManager.record({
                action: '切换地图引擎',
                type: 'map',
                detail: `切换到 ${newProvider === 'arcgis' ? 'ArcGIS' : '高德'} 地图引擎`,
                undoable: false
            });

        } catch (error) {
            LoadingManager.hide();
            console.error('地图引擎切换失败:', error);
            const errorMessage = error instanceof Error ? error.message : '未知错误';
            this.showStatus(`切换失败: ${errorMessage}`, 'error');
            throw error;
        } finally {
            // 重置切换状态标志
            this.isSwitchingMap = false;
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

        // 更新导航按钮
        const newProjectBtn = document.getElementById('new-project-btn') as HTMLButtonElement;
        if (newProjectBtn) {
            newProjectBtn.textContent = I18n.t('nav.newProject');
        }

        // 更新面板标题
        const panelTitles = document.querySelectorAll('.panel-title');
        const panelIndex = {
            0: 'panel.project',
            1: 'upload.title',
            2: 'kriging.title',
            3: 'task.title',
            4: 'export.title',
            5: 'layer.title'
        };

        panelTitles.forEach((title, index) => {
            if (title && panelIndex[index]) {
                title.textContent = I18n.t(panelIndex[index]);
            }
        });

        // 更新其他界面文本...
        // (这里省略了其他界面文本更新，因为代码太长)
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
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch(() => {
            // SW 注册失败，静默忽略
        });
    });
}

// 启动应用
const app = new App();
initKeyboardShortcuts(app);