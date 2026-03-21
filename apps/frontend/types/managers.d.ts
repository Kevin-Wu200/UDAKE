/**
 * 管理器类型定义
 */

// ComponentInitializer 相关类型
import { LayerManager } from '../js/图层管理.js';
import { MapView } from './app';
import { IAPIService } from './app';

export interface ComponentConfig {
    apiService: IAPIService;
    layerManager: LayerManager;
    view: MapView;
}

export interface ComponentRegistry {
    // 地图相关组件
    coordSystemInfo: any;
    singlePointSampling: any;
    recommendationPanel: any;
    enhancedRecommendationPanel: any;
    interactiveMarkers: any;
    strategySelector: any;
    mapEngineSwitcher: any;
    locationCenterButton: any;
    mapTooltip: any;
    mapLegend: any;
    layerComparisonPanel: any;
    measureTool: any;

    // UI组件
    templateDownloader: any;
    industrySelector: any;
    settingsPanel: any;
    preferencesPanel: any;
    feedbackCollector: any;
    onboardingGuide: any;
    cacheManagementPanel: any;
    offlineModeBanner: any;

    // 参数组件
    parameterAdjustmentPanel: any;
    parameterTabPanel: any;
}

// EventBinder 相关类型
export interface EventHandler {
    target: EventTarget;
    type: string;
    handler: EventListenerOrEventListenerObject;
    options?: AddEventListenerOptions | boolean;
}

export interface EventGroup {
    name: string;
    handlers: EventHandler[];
}

// StateManager 相关类型
export type StateListener<T = any> = (newValue: T, oldValue: T) => void;

export interface StateConfig {
    persist?: boolean;
    persistKey?: string;
    validate?: (value: any) => boolean;
}

export interface StateDefinition {
    key: string;
    defaultValue: any;
    config?: StateConfig;
}

// StartupManager 相关类型
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

// LaunchProgressManager 相关类型
export interface ProgressStage {
    id: string;
    name: string;
    description: string;
    weight: number;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress: number;
    startTime?: number;
    endTime?: number;
    error?: Error;
}

export interface ProgressCallback {
    onStageStart?: (stage: ProgressStage) => void;
    onStageProgress?: (stage: ProgressStage) => void;
    onStageComplete?: (stage: ProgressStage) => void;
    onStageError?: (stage: ProgressStage) => void;
    onTotalProgress?: (total: number, stages: ProgressStage[]) => void;
    onComplete?: (stages: ProgressStage[]) => void;
    onError?: (error: Error) => void;
}

// SplashScreen 相关类型
export type SplashScreenStage = 'initializing' | 'loading' | 'ready' | 'error';

export interface SplashScreenOptions {
    showProgress?: boolean;
    animationDuration?: number;
    minDisplayTime?: number;
}
