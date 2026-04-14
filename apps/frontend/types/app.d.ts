/**
 * UDAKE 应用全局类型定义
 */

import { IAPIService } from './api';
import { IMapAdapter, ILayerManager } from './map';
import {
    ProjectConfig,
    ProjectData,
    TaskStatus,
    SamplingPoint,
    SamplingMode,
    CoordinateMode,
    PollingPriority,
    KrigingParams
} from './core';

// 重新导出核心类型以方便使用
export type {
    ProjectConfig,
    ProjectData,
    TaskStatus,
    SamplingPoint,
    SamplingMode,
    CoordinateMode,
    PollingPriority,
    KrigingParams
} from './core';

// 重新导出 API 类型
export type { IAPIService } from './api';

// 重新导出地图类型
export type { IMapAdapter, ILayerManager } from './map';

// ========== 全局环境 ==========

/** Electron API 接口 */
export interface ElectronAPI {
    getBackendPort: () => Promise<number>;
}

/** Window 扩展 */
declare global {
    interface Window {
        electronAPI?: ElectronAPI;
    }
}

// ========== 应用组件 ==========

/** 表单验证器接口 */
export interface IFormValidator {
    register(fieldId: string, rules: FormValidationRules): void;
    onValidationChange?: (allValid: boolean) => void;
}

/** 表单验证规则 */
export interface FormValidationRules {
    required?: string;
    pattern?: RegExp;
    patternMsg?: string;
    custom?: (value: string) => {
        valid: boolean;
        message?: string;
        level?: 'success' | 'warning' | 'error';
    };
}

/** 历史记录条目 */
export interface HistoryEntry {
    action: string;
    type: string;
    detail: string;
    undoable: boolean;
    timestamp?: number;
}

/** 采样点数据（扩展） */
export interface ExtendedSamplingPoint extends SamplingPoint {
    id?: string;
    timestamp?: string;
}

/** 项目接口 */
export interface IProject {
    points: SamplingPoint[];
    addPoint(point: SamplingPoint): boolean;
    getPointCount(): number;
}

/** 采样组件接口 */
export interface ISamplingComponent {
    destroy(): void;
    createPanel(coordinateMode?: CoordinateMode): HTMLElement;
    coordinateInput?: any;
}

/** 采样建议面板接口 */
export interface ISamplingRecommendationPanel {
    setTaskId(taskId: string): void;
    createPanel(): HTMLElement;
    updateUIText(): void;
}

/** 偏好设置接口 */
export interface IPreferencesPanel {
    show(): void;
}

/** 反馈收集器接口 */
export interface IFeedbackCollector {
    show(): void;
}

/** 模板下载器接口 */
export interface ITemplateDownloader {
    createPanel(): HTMLElement;
}

/** 采样点推荐数据 */
export interface SamplingRecommendation {
    id: number;
    x: number;
    y: number;
    variance: number;
    confidence?: number;
}

/** 采样点选择回调 */
export type RecommendationSelectCallback = (recommendation: SamplingRecommendation) => void;

/** 地图视图接口 */
export interface MapView {
    extent?: {
        xmin: number;
        ymin: number;
        xmax: number;
        ymax: number;
    };
    spatialReference?: {
        wkid?: number;
        latestWkid?: number;
        wkt?: string;
    };
    watch?(name: string, callback: () => void): any;
    on?(event: string, callback: () => void): any;
    getBounds?(): {
        getSouthWest(): { lng: number; lat: number };
        getNorthEast(): { lng: number; lat: number };
    };
    getCenter?(): { lng: number; lat: number };
}

/** 适配器接口（增强） */
export interface IMapAdapterExtended extends IMapAdapter {
    graphicsLayer?: {
        remove?(graphic: any): void;
    };
}

/** 确认对话框选项 */
export interface ConfirmDialogOptions {
    title: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
}

/** 确认对话框接口 */
export interface IConfirmDialog {
    confirm(options: ConfirmDialogOptions): Promise<boolean>;
}

/** 应用配置 */
export interface AppConfig {
    backendPort: number;
    mapEngine: 'geoscene' | 'amap' | (string & {});
    defaultGridResolution: number;
}

/** 插值启动参数 */
export interface KrigingStartParams {
    points: SamplingPoint[];
    method: string;
    variogram_model: string;
    grid_resolution: number;
    enable_cross_validation: boolean;
}

/** 离线队列处理器 */
export type OfflineQueueHandler = (payload: any) => Promise<void>;

/** 地图图形接口 */
export interface MapGraphic {
    attributes?: Record<string, any>;
}

/** 地图点接口 */
export interface MapPoint {
    longitude: number;
    latitude: number;
}

/** 信息面板数据 */
export interface InfoPanelData {
    graphic: MapGraphic;
    mapPoint: MapPoint;
}

/** 文件上传状态 */
export type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

/** 采样点添加回调 */
export type PointAddCallback = (pointData: ExtendedSamplingPoint) => Promise<void>;

/** 项目创建回调 */
export type ProjectCreateCallback = (
    project: IProject,
    config: ProjectConfig
) => void;

/** 数据导入转换数据 */
export interface TransformedData {
    geojson: any;
    data: SamplingPoint[];
}

/** 数据导入回调 */
export type DataImportCallback = (transformedData: TransformedData) => void;

/** 任务状态回调 */
export type TaskStatusCallback = (status: TaskStatus) => void;

/** 偏好设置数据 */
export interface Preferences {
    theme: 'light' | 'dark';
    animationsEnabled: boolean;
    gridResolution: number;
    language?: string;
}

/** 导出选项 */
export type ExportFormat = 'geojson' | 'shp' | 'tif' | 'csv';

/** 导出数据类型 */
export type ExportDataType = 'prediction' | 'variance';

/** 增强导出参数 */
export interface ExportEnhancerParams {
    taskId: string;
    method: string;
    pointCount: number;
    gridResolution: number;
}

/** 键盘快捷键配置 */
export interface KeyboardShortcut {
    key: string;
    description: string;
    handler: () => void;
}

/** 侧边栏状态 */
export type SidebarState = 'open' | 'closed' | 'mobile-open';

/** 加载状态 */
export interface LoadingState {
    text?: string;
    visible: boolean;
}

/** 应用性能标记 */
export interface PerformanceMark {
    name: string;
    startTime: number;
}

/** 错误监控配置 */
export interface ErrorMonitorConfig {
    apikey?: string;
    appversion: string;
    release: string;
    enabled?: boolean;
}

/** 面包屑导航 */
export interface Breadcrumb {
    category: string;
    message: string;
    data?: Record<string, any>;
}
