/**
 * 组件初始化器
 * 负责初始化应用中的所有UI组件和地图交互组件
 */

import { LayerManager } from '../图层管理.js';
import { CoordinateSystemInfo } from '../坐标系统信息.js';
import { SinglePointSampling } from '../单点采样输入.js';
import { SamplingRecommendationPanel } from '../components/SamplingRecommendationPanel.js';
import { EnhancedSamplingRecommendationPanel } from '../components/EnhancedSamplingRecommendationPanel.js';
import { InteractiveSamplingMarkers } from '../components/InteractiveSamplingMarkers.js';
import { SamplingStrategySelector } from '../components/SamplingStrategySelector.js';
import { OnboardingGuide } from '../components/OnboardingGuide.js';
import { QuickActionBar } from '../components/QuickActionBar.js';
import { SmartWizardEngine } from '../components/SmartWizardEngine.js';
import { SmartRecommendationEngine } from '../components/SmartRecommendationEngine.js';
import { PreferencesPanel } from '../components/PreferencesPanel.js';
import { TemplateDownloader } from '../components/TemplateDownloader.js';
import { IndustrySelector } from '../components/IndustrySelector.js';
import { SettingsPanel } from '../components/SettingsPanel.js';
import { LocationCenterButton } from '../components/LocationCenterButton.js';
import { MapTooltip } from '../components/MapTooltip.js';
import { MapLegend } from '../components/MapLegend.js';
import { LayerComparisonPanel } from '../components/LayerComparisonPanel.js';
import { MeasureTool, MeasureResult } from '../components/MeasureTool.js';
import { ParameterAdjustmentPanel } from '../components/ParameterAdjustmentPanel.js';
import { ParameterTabPanel } from '../components/ParameterTabPanel.js';
import CacheManagementPanel from '../components/CacheManagementPanel.js';
import OfflineModeBanner from '../components/OfflineModeBanner.js';
import { HistoryManager } from '../utils/HistoryManager.js';
import { FeedbackCollector } from '../components/FeedbackCollector.js';
import { MapEngineSwitcher } from '../components/MapEngineSwitcher';
import { Map25DHeatmapController } from '../components/Map25DHeatmapController.js';
import { TemplateStorageService } from '../services/TemplateStorageService.js';
import { getMapProvider } from '../地图初始化.js';
import workflowWizardConfig from '../../../../configs/workflow-wizards.json';
import type { DeepLearningPanel } from '../components/DeepLearningPanel.js';

// 导入类型
import {
    IMapAdapterExtended,
    MapView,
    IProject,
    ISamplingComponent,
    ISamplingRecommendationPanel,
    IOnboardingGuide,
    IPreferencesPanel,
    IFeedbackCollector,
    IAPIService,
    SamplingRecommendation
} from '../../types/app';

export interface ComponentConfig {
    apiService: IAPIService;
    layerManager: LayerManager;
    view: MapView;
}

export interface ComponentRegistry {
    // 地图相关组件
    coordSystemInfo: CoordinateSystemInfo;
    singlePointSampling: SinglePointSampling;
    recommendationPanel: ISamplingRecommendationPanel;
    enhancedRecommendationPanel: EnhancedSamplingRecommendationPanel | null;
    interactiveMarkers: InteractiveSamplingMarkers | null;
    strategySelector: SamplingStrategySelector | null;
    mapEngineSwitcher: MapEngineSwitcher;
    locationCenterButton: LocationCenterButton;
    mapTooltip: MapTooltip;
    mapLegend: MapLegend;
    layerComparisonPanel: LayerComparisonPanel;
    measureTool: MeasureTool;
    mapVisualEnhancer: Map25DHeatmapController | null;

    // UI组件
    templateDownloader: any;
    industrySelector: IndustrySelector;
    settingsPanel: SettingsPanel;
    preferencesPanel: IPreferencesPanel | null;
    feedbackCollector: IFeedbackCollector | null;
    onboardingGuide: IOnboardingGuide;
    quickActionBar: QuickActionBar | null;
    wizardEngine: SmartWizardEngine | null;
    recommendationEngine: SmartRecommendationEngine | null;
    cacheManagementPanel: any;
    offlineModeBanner: any;
    deepLearningPanel: DeepLearningPanel | null;

    // 参数组件
    parameterAdjustmentPanel: ParameterAdjustmentPanel;
    parameterTabPanel: ParameterTabPanel;
}

export class ComponentInitializer {
    private components: Map<string, any> = new Map();
    private config: ComponentConfig | null = null;

    /**
     * 初始化所有组件
     */
    public async initialize(config: ComponentConfig): Promise<ComponentRegistry> {
        this.config = config;

        console.log('[ComponentInitializer] 开始初始化组件...');

        // 1. 初始化基础UI组件
        await this.initializeBasicComponents();

        // 2. 初始化地图交互组件
        await this.initializeMapInteractionComponents();

        // 3. 初始化参数组件
        await this.initializeParameterComponents();

        // 4. 初始化高级功能组件
        await this.initializeAdvancedComponents();

        console.log('[ComponentInitializer] 组件初始化完成');

        return this.getComponentRegistry();
    }

    /**
     * 初始化基础UI组件
     */
    private async initializeBasicComponents(): Promise<void> {
        console.log('[ComponentInitializer] 初始化基础UI组件...');

        // 应用启动时预热模板目录：首次启动会自动创建 UDAKE_docs。
        if (TemplateStorageService.canUseNativeStorage()) {
            try {
                await TemplateStorageService.ensureInitialized();
            } catch (error) {
                console.warn('[ComponentInitializer] 模板目录初始化失败，将在下载时重试:', error);
            }
        }

        const sidebar = document.querySelector('.sidebar');
        if (!sidebar) {
            console.warn('[ComponentInitializer] 侧边栏不存在');
            return;
        }

        // 创建坐标系统信息组件
        const coordSystemInfo = new CoordinateSystemInfo(this.config!.view);
        const coordPanel = coordSystemInfo.createPanel();
        this.components.set('coordSystemInfo', coordSystemInfo);

        // 创建单点采样输入组件
        const singlePointSampling = new SinglePointSampling(
            this.config!.view,
            async (pointData) => {
                if (this.config!.layerManager) {
                    await this.config!.layerManager.addSamplingPoint(pointData);
                }
            }
        );
        const samplingPanel = singlePointSampling.createPanel();
        this.components.set('singlePointSampling', singlePointSampling);

        // 创建采样建议面板
        const recommendationPanel = new SamplingRecommendationPanel(
            this.config!.view,
            this.config!.layerManager,
            (recommendation: SamplingRecommendation) => this.handleRecommendationSelect(recommendation)
        );
        const recommendationPanelElement = recommendationPanel.createPanel();
        this.components.set('recommendationPanel', recommendationPanel);

        // 初始化增强采样推荐组件（可选）
        if (this.config!.apiService && this.config!.layerManager) {
            const enhancedRecommendationPanel = new EnhancedSamplingRecommendationPanel(
                this.config!.layerManager.adapter
            );
            const interactiveMarkers = new InteractiveSamplingMarkers(this.config!.layerManager.adapter);
            const strategySelector = new SamplingStrategySelector();

            this.components.set('enhancedRecommendationPanel', enhancedRecommendationPanel);
            this.components.set('interactiveMarkers', interactiveMarkers);
            this.components.set('strategySelector', strategySelector);

            // 监听策略变化
            strategySelector.setOnStrategyChange((strategy, config) => {
                console.log('策略变化:', strategy, config);
            });

            // 监听标记点击
            interactiveMarkers.setOnMarkerClick((rec) => {
                console.log('标记点击:', rec);
                enhancedRecommendationPanel.previewPointEffect(rec);
            });

            // 监听标记拖拽
            interactiveMarkers.setOnMarkerDrag((rec, newPosition) => {
                console.log('标记拖拽:', rec, newPosition);
            });
        } else {
            this.components.set('enhancedRecommendationPanel', null);
            this.components.set('interactiveMarkers', null);
            this.components.set('strategySelector', null);
        }

        // 插入到侧边栏
        const firstPanel = sidebar.querySelector('.panel');
        if (firstPanel) {
            sidebar.insertBefore(coordPanel, firstPanel);
        }

        const interpolationPanel = sidebar.querySelectorAll('.panel')[2];
        if (interpolationPanel && interpolationPanel.parentNode) {
            interpolationPanel.parentNode.insertBefore(samplingPanel, interpolationPanel.nextSibling);
        }

        // 添加模板下载面板
        const uploadPanel = sidebar.querySelectorAll('.panel')[1];
        if (uploadPanel && uploadPanel.parentNode) {
            const templatePanel = document.createElement('div');
            templatePanel.className = 'panel';
            templatePanel.appendChild(TemplateDownloader.createPanel());
            uploadPanel.parentNode.insertBefore(templatePanel, uploadPanel.nextSibling);
        }

        // 添加行业选择器面板
        if (uploadPanel && uploadPanel.parentNode) {
            const industryPanel = document.createElement('div');
            industryPanel.className = 'panel';
            industryPanel.innerHTML = `
                <div class="panel-header">
                    <h3>行业配置</h3>
                </div>
                <div id="industry-selector-container"></div>
            `;
            uploadPanel.parentNode.insertBefore(industryPanel, uploadPanel.nextSibling);

            // 初始化行业选择器
            const industrySelector = new IndustrySelector(
                '#industry-selector-container',
                this.config!.apiService?.baseURL || '/api'
            );
            this.components.set('industrySelector', industrySelector);

            // 初始化设置面板
            const settingsPanel = new SettingsPanel('body', {
                onLanguageChange: (language) => {
                    console.log('语言已切换到:', language);
                    this.updateUIText();
                }
            });
            this.components.set('settingsPanel', settingsPanel);

            // 设置行业选择回调
            industrySelector.setIndustrySelectCallback((industry) => {
                console.log('选择了行业:', industry);
            });

            // 设置模板下载回调
            industrySelector.setTemplateDownloadCallback((template) => {
                console.log('下载模板:', template);
            });
        }

        // 添加操作历史面板
        const historyPanel = HistoryManager.createPanel();
        sidebar.appendChild(historyPanel);

        // 将采样建议面板添加到右侧侧边栏
        const rightSidebarContent = document.querySelector('.right-sidebar-content');
        if (rightSidebarContent) {
            rightSidebarContent.appendChild(recommendationPanelElement);
        }

        console.log('[ComponentInitializer] 基础UI组件初始化完成');
    }

    /**
     * 初始化地图交互组件
     */
    private async initializeMapInteractionComponents(): Promise<void> {
        console.log('[ComponentInitializer] 初始化地图交互组件...');

        const mapContainer = document.querySelector('.map-container') as HTMLElement;
        if (!mapContainer) {
            console.error('[ComponentInitializer] 找不到地图容器');
            return;
        }

        // 获取地图提供商
        const provider = await getMapProvider();

        // 初始化地图引擎切换器
        const mapEngineSwitcher = new MapEngineSwitcher(
            provider as 'geoscene' | 'amap',
            async (newProvider) => await this.handleMapEngineSwitch(newProvider)
        );
        mapEngineSwitcher.addToContainer(mapContainer);
        this.components.set('mapEngineSwitcher', mapEngineSwitcher);

        // 初始化回到中心按钮
        const locationCenterButton = new LocationCenterButton(() => this.handleLocationCenter());
        locationCenterButton.addToContainer(mapContainer);
        this.components.set('locationCenterButton', locationCenterButton);

        // 初始化地图悬停提示组件
        const mapTooltip = new MapTooltip({
            offset: 15,
            animationDuration: 200,
            showDelay: 300,
            hideDelay: 100,
            smartPositioning: true
        });
        mapTooltip.init(mapContainer);
        this.components.set('mapTooltip', mapTooltip);

        // 初始化地图图例组件
        const mapLegend = new MapLegend({
            title: '预测值',
            unit: '',
            ranges: [
                { min: 0, max: 0.2, color: '#34c759', label: '极低' },
                { min: 0.2, max: 0.4, color: '#30d158', label: '低' },
                { min: 0.4, max: 0.6, color: '#0a84ff', label: '中等' },
                { min: 0.6, max: 0.8, color: '#ff9500', label: '高' },
                { min: 0.8, max: 1.0, color: '#ff3b30', label: '极高' }
            ],
            position: 'bottom-right',
            collapsible: true,
            collapsed: false,
            showValues: true
        });
        const legendElement = mapLegend.createLegend();
        mapContainer.appendChild(legendElement);
        mapLegend.loadFromStorage();
        this.components.set('mapLegend', mapLegend);

        // 初始化图层对比面板
        const layerComparisonPanel = new LayerComparisonPanel({
            onVisibilityChange: (layerId, visible) => {
                if (this.config!.layerManager) {
                    this.config!.layerManager.toggleLayer(layerId, visible);
                }
            },
            onOpacityChange: (layerId, opacity) => {
                if (this.config!.layerManager) {
                    this.config!.layerManager.setLayerOpacity(layerId, opacity / 100);
                }
            },
            onLayerOrderChange: (layers) => {
                if (this.config!.layerManager) {
                    layers.forEach(layer => {
                        this.config!.layerManager!.setLayerZIndex(layer.layerId, layer.zIndex);
                    });
                }
            }
        });
        const comparisonPanel = layerComparisonPanel.createPanel();
        comparisonPanel.style.position = 'absolute';
        comparisonPanel.style.top = '134px';
        comparisonPanel.style.right = '80px';
        comparisonPanel.style.zIndex = '999';
        mapContainer.appendChild(comparisonPanel);
        this.components.set('layerComparisonPanel', layerComparisonPanel);

        // 初始化测量工具
        const measureTool = new MeasureTool(
            {
                defaultUnit: 'm',
                showLabels: true,
                snapToFeatures: false
            },
            {
                onMeasureComplete: (result: MeasureResult) => {
                    console.log('测量完成:', result);
                },
                onMeasureUpdate: (result: MeasureResult) => {
                    console.log('测量更新:', result);
                },
                onMeasureClear: () => {
                    console.log('测量已清除');
                }
            }
        );
        measureTool.init(this.config!.view, provider as 'geoscene' | 'amap');
        const measurePanel = measureTool.createPanel();
        measurePanel.style.display = 'none';
        mapContainer.appendChild(measurePanel);
        this.components.set('measureTool', measureTool);

        // 初始化 2.5D 与热力图增强控制器
        const mapVisualEnhancer = new Map25DHeatmapController(mapContainer, {
            getView: () => this.config?.view,
            getSamplingPoints: () => this.config?.layerManager?.getSamplingPoints() || []
        });
        this.components.set('mapVisualEnhancer', mapVisualEnhancer);

        // 添加工具按钮
        this.addToolbarButtons();

        console.log('[ComponentInitializer] 地图交互组件初始化完成');
    }

    /**
     * 初始化参数组件
     */
    private async initializeParameterComponents(): Promise<void> {
        console.log('[ComponentInitializer] 初始化参数组件...');

        // 初始化参数调整面板
        const parameterAdjustmentPanel = ParameterAdjustmentPanel.getInstance();
        this.components.set('parameterAdjustmentPanel', parameterAdjustmentPanel);

        // 初始化参数标签页面板
        const parameterTabPanel = ParameterTabPanel.getInstance();
        this.components.set('parameterTabPanel', parameterTabPanel);

        console.log('[ComponentInitializer] 参数组件初始化完成');
    }

    /**
     * 初始化高级功能组件
     */
    private async initializeAdvancedComponents(): Promise<void> {
        console.log('[ComponentInitializer] 初始化高级功能组件...');

        // 初始化新手引导
        const onboardingGuide = new OnboardingGuide();
        onboardingGuide.autoStart();
        this.components.set('onboardingGuide', onboardingGuide);

        const mapContainer = document.querySelector('.map-container') as HTMLElement | null;
        const headerQuickActionContainer = document.querySelector('#header-quick-action-container') as HTMLElement | null;
        if (mapContainer) {
            const quickActionBar = new QuickActionBar();
            quickActionBar.mount(headerQuickActionContainer || mapContainer);
            this.components.set('quickActionBar', quickActionBar);

            const recommendationEngine = new SmartRecommendationEngine(
                quickActionBar.getActions().map((action) => ({
                    id: action.id,
                    label: action.label,
                    command: action.command
                }))
            );
            recommendationEngine.mount(mapContainer);
            this.components.set('recommendationEngine', recommendationEngine);
        } else {
            this.components.set('quickActionBar', null);
            this.components.set('recommendationEngine', null);
        }

        const wizardEngine = new SmartWizardEngine(workflowWizardConfig as any);
        wizardEngine.mount(document.body);
        this.components.set('wizardEngine', wizardEngine);

        // 初始化偏好设置面板（延迟初始化）
        this.components.set('preferencesPanel', null);

        // 初始化反馈收集器（延迟初始化）
        this.components.set('feedbackCollector', null);

        // 初始化缓存管理面板
        this.components.set('cacheManagementPanel', CacheManagementPanel);

        // 初始化离线模式横幅
        this.components.set('offlineModeBanner', OfflineModeBanner);
        this.components.set('deepLearningPanel', null);

        console.log('[ComponentInitializer] 高级功能组件初始化完成');
    }

    /**
     * 添加工具栏按钮
     */
    private addToolbarButtons(): void {
        const mapContainer = document.querySelector('.map-container') as HTMLElement | null;
        if (!mapContainer) {
            console.warn('[ComponentInitializer] 找不到地图容器，跳过工具栏初始化');
            return;
        }

        let toolbar = mapContainer.querySelector('.map-toolbar') as HTMLElement | null;
        if (!toolbar) {
            toolbar = document.createElement('div');
            toolbar.className = 'map-toolbar';
            mapContainer.appendChild(toolbar);
        }

        // 添加测量工具按钮
        if (!toolbar.querySelector('[data-toolbar-id="measure"]')) {
            const measureBtn = document.createElement('button');
            measureBtn.className = 'toolbar-btn';
            measureBtn.setAttribute('data-toolbar-id', 'measure');
            measureBtn.title = '测量工具';
            measureBtn.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M2 10h16M10 2v16" stroke="currentColor" stroke-width="2"/>
                </svg>
            `;
            measureBtn.addEventListener('click', () => {
                const panel = document.querySelector('.measure-tool-panel') as HTMLElement;
                if (panel) {
                    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
                }
            });
            toolbar.appendChild(measureBtn);
        }

        // 添加图层对比按钮
        if (!toolbar.querySelector('[data-toolbar-id="layer-comparison"]')) {
            const comparisonBtn = document.createElement('button');
            comparisonBtn.className = 'toolbar-btn';
            comparisonBtn.setAttribute('data-toolbar-id', 'layer-comparison');
            comparisonBtn.title = '图层对比';
            comparisonBtn.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                    <rect x="2" y="2" width="16" height="16" rx="2" stroke="currentColor" stroke-width="2" fill="none"/>
                    <line x1="2" y1="10" x2="18" y2="10" stroke="currentColor" stroke-width="2"/>
                </svg>
            `;
            comparisonBtn.addEventListener('click', () => {
                const panel = document.querySelector('.layer-comparison-panel') as HTMLElement;
                if (panel) {
                    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
                }
            });
            toolbar.appendChild(comparisonBtn);
        }

        const mapVisualEnhancer = this.components.get('mapVisualEnhancer') as Map25DHeatmapController | null;
        mapVisualEnhancer?.attachToolbarButton(toolbar);
    }

    /**
     * 获取组件注册表
     */
    public getComponentRegistry(): ComponentRegistry {
        return {
            // 地图相关组件
            coordSystemInfo: this.components.get('coordSystemInfo'),
            singlePointSampling: this.components.get('singlePointSampling'),
            recommendationPanel: this.components.get('recommendationPanel'),
            enhancedRecommendationPanel: this.components.get('enhancedRecommendationPanel'),
            interactiveMarkers: this.components.get('interactiveMarkers'),
            strategySelector: this.components.get('strategySelector'),
            mapEngineSwitcher: this.components.get('mapEngineSwitcher'),
            locationCenterButton: this.components.get('locationCenterButton'),
            mapTooltip: this.components.get('mapTooltip'),
            mapLegend: this.components.get('mapLegend'),
            layerComparisonPanel: this.components.get('layerComparisonPanel'),
            measureTool: this.components.get('measureTool'),
            mapVisualEnhancer: this.components.get('mapVisualEnhancer'),

            // UI组件
            templateDownloader: this.components.get('templateDownloader'),
            industrySelector: this.components.get('industrySelector'),
            settingsPanel: this.components.get('settingsPanel'),
            preferencesPanel: this.components.get('preferencesPanel'),
            feedbackCollector: this.components.get('feedbackCollector'),
            onboardingGuide: this.components.get('onboardingGuide'),
            quickActionBar: this.components.get('quickActionBar'),
            wizardEngine: this.components.get('wizardEngine'),
            recommendationEngine: this.components.get('recommendationEngine'),
            cacheManagementPanel: this.components.get('cacheManagementPanel'),
            offlineModeBanner: this.components.get('offlineModeBanner'),
            deepLearningPanel: this.components.get('deepLearningPanel'),

            // 参数组件
            parameterAdjustmentPanel: this.components.get('parameterAdjustmentPanel'),
            parameterTabPanel: this.components.get('parameterTabPanel')
        };
    }

    /**
     * 获取单个组件
     */
    public getComponent<T>(name: string): T {
        return this.components.get(name) as T;
    }

    /**
     * 注册或覆盖组件实例
     */
    public registerComponent(name: string, component: any): void {
        this.components.set(name, component);
    }

    /**
     * 更新地图上下文（用于地图引擎切换后同步组件）
     */
    public updateMapContext(context: Partial<Pick<ComponentConfig, 'layerManager' | 'view'>>): void {
        if (!this.config) {
            return;
        }

        if (context.layerManager) {
            this.config.layerManager = context.layerManager;
        }
        if (context.view) {
            this.config.view = context.view;
        }

        const mapVisualEnhancer = this.components.get('mapVisualEnhancer') as Map25DHeatmapController | null;
        mapVisualEnhancer?.updateContext({
            getView: () => this.config?.view,
            getSamplingPoints: () => this.config?.layerManager?.getSamplingPoints() || []
        });
    }

    /**
     * 处理建议点选中
     */
    private handleRecommendationSelect(recommendation: SamplingRecommendation): void {
        console.log('选中建议点:', recommendation);
        // 这里可以触发事件或调用回调
        const event = new CustomEvent('recommendation-selected', { detail: recommendation });
        document.dispatchEvent(event);
    }

    /**
     * 处理地图引擎切换
     */
    private async handleMapEngineSwitch(newProvider: 'geoscene' | 'amap'): Promise<void> {
        console.log('切换地图引擎:', newProvider);
        const event = new CustomEvent('map-engine-switch', { detail: newProvider });
        document.dispatchEvent(event);
    }

    /**
     * 处理回到中心
     */
    private handleLocationCenter(): void {
        console.log('回到中心');
        const event = new CustomEvent('location-center');
        document.dispatchEvent(event);
    }

    /**
     * 更新界面文本
     */
    private updateUIText(): void {
        const event = new CustomEvent('update-ui-text');
        document.dispatchEvent(event);
    }

    /**
     * 销毁所有组件
     */
    public destroy(): void {
        console.log('[ComponentInitializer] 销毁所有组件...');

        // 销毁各个组件
        this.components.forEach((component, name) => {
            if (component && typeof component.destroy === 'function') {
                try {
                    component.destroy();
                } catch (error) {
                    console.error(`[ComponentInitializer] 销毁组件 ${name} 失败:`, error);
                }
            }
        });

        this.components.clear();
    }
}
