/**
 * 全局类型声明
 * 处理动态导入和缺失的类型定义
 */

// GeoScene SDK 模块声明（通过 npm 包 @geoscene/core 引入）
declare module '@geoscene/core';
declare module '@geoscene/core/*';

// 处理 HTML 扩展
declare global {
    // Node.js process 类型定义（用于浏览器环境）
    interface Process {
        env: {
            NODE_ENV?: string;
            [key: string]: string | undefined;
        };
    }

    var process: Process;

    interface HTMLInputElement {
        files: FileList | null;
    }

    interface Element {
        style?: any;
    }

    // Web 传感器 API 类型定义
    interface Sensor {
        start(): void;
        stop(): void;
        readonly activated: boolean;
        readonly hasReading: boolean;
        onreading: ((this: Sensor, event: Event) => any) | null;
        onerror: ((this: Sensor, event: Event) => any) | null;
        addEventListener(type: string, listener: (this: Sensor, event: Event) => any): void;
        removeEventListener(type: string, listener: (this: Sensor, event: Event) => any): void;
    }

    interface Accelerometer extends Sensor {
        readonly x: number;
        readonly y: number;
        readonly z: number;
        readonly timestamp: number;
    }

    interface Gyroscope extends Sensor {
        readonly x: number;
        readonly y: number;
        readonly z: number;
        readonly timestamp: number;
    }

    interface AbsoluteOrientationSensor extends Sensor {
        readonly quaternion: number[];
        readonly timestamp: number;
    }

    var Accelerometer: {
        prototype: Accelerometer;
        new(options?: { frequency?: number }): Accelerometer;
    };

    var Gyroscope: {
        prototype: Gyroscope;
        new(options?: { frequency?: number }): Gyroscope;
    };

    var AbsoluteOrientationSensor: {
        prototype: AbsoluteOrientationSensor;
        new(options?: { frequency?: number }): AbsoluteOrientationSensor;
    };

    // 高德地图 API 类型定义
    interface AMap {
        InfoWindow: {
            new(options: { content: string; offset?: any; position?: any }): any;
        };
        Marker: {
            new(options: { position: any; icon?: any; title?: string; content?: string; offset?: any; zIndex?: number }): any;
        };
        Polygon: {
            new(options: { path: any[]; strokeColor?: string; fillColor?: string; strokeOpacity?: number; fillOpacity?: number; strokeWeight?: number; zIndex?: number }): any;
        };
        Circle: {
            new(options: { center: any; radius: number; strokeColor?: string; fillColor?: string; strokeWeight?: number; strokeOpacity?: number; fillOpacity?: number; zIndex?: number }): any;
        };
        Text: {
            new(options: { text: string; position: any; style?: any }): any;
        };
        LatLng: {
            new(lng: number, lat: number): any;
        };
        LngLat: {
            new(lng: number, lat: number): any;
        };
        Pixel: {
            new(x: number, y: number): any;
        };
        LayerGroup: {
            new(): any;
            add(layer: any): void;
            clear(): void;
        };
        Polyline: {
            new(options: { path: any[]; strokeColor?: string; strokeWeight?: number; strokeOpacity?: number; showDir?: boolean }): any;
        };
    }

    var AMap: AMap;

    // 通知类型定义
    interface Notification {
        requestPermissions(): Promise<any>;
        schedule(options: any): Promise<any>;
        cancel(options: any): Promise<any>;
    }

    enum NotificationType {
        Success = 'success',
        Warning = 'warning',
        Error = 'error'
    }

    var Notification: Notification;

    // 扩展 PositionOptions 以支持 distanceFilter
    interface CapacitorPositionOptions {
        enableHighAccuracy?: boolean;
        timeout?: number;
        maximumAge?: number;
        distanceFilter?: number;
    }

    // 扩展 Capacitor Geolocation 模块
    namespace CapacitorGeolocation {
        interface WatchPositionCallback {
            (position: any, error?: any): void;
        }

        interface GeolocationPlugin {
            watchPosition(
                callback: WatchPositionCallback,
                options?: CapacitorPositionOptions
            ): Promise<string>;
            clearWatch(id: string): Promise<void>;
        }
    }

    var Geolocation: CapacitorGeolocation.GeolocationPlugin;
}

// 扩展 ThemeManager
declare module './js/utils/ThemeManager.js' {
    export const ThemeManager: {
        init(): void;
        toggle(): void;
        setDark(): void;
        setLight(): void;
    };
}

// 扩展 ErrorHandler
declare module './js/utils/ErrorHandler.js' {
    export const ErrorHandler: {
        showGlobalNotification(message: string, type: string): void;
    };
}

// 扩展 LayerManager
declare module './js/图层管理.js' {
    export class LayerManager {
        constructor(adapter: any, config?: any);
        addPointsLayer(geojson: any, layerName?: string): Promise<void>;
        addRasterLayer(type: string, url: string): Promise<void>;
        toggleLayer(layerName: string, visible: boolean): void;
        setLayerOpacity(layerName: string, opacity: number): void;
        addSamplingPoint(pointData: any): Promise<void>;
        addMarker(pointData: any): Promise<void>;
        getSamplingPoints(): any[];
        samplingPoints: any[];
        removeLayer(layerName: string): void;
        clearAllLayers(): void;
        setupClickHandler(handler: (graphic: any, mapPoint: any) => void): void;
        showInfoPanel(graphic: any, mapPoint: any): void;
        hideInfoPanel(): void;
    }
}

// 扩展 API 封装
declare module './js/services/API封装.js' {
    export class APIService {
        constructor(baseURL: string);
        baseURL: string;
        request<T = any>(url: string, options?: RequestInit): Promise<T>;
        uploadData(file: File): Promise<any>;
        startKriging(params: any): Promise<any>;
        getTaskStatus(taskId: string): Promise<any>;
        getPredictionResult(taskId: string): Promise<any>;
        getVarianceResult(taskId: string): Promise<any>;
        getReport(taskId: string): Promise<any>;
        downloadExportFile(taskId: string, filename: string): Promise<void>;
        clearCache(): void;
        clearCacheFor(url: string): void;
        cancelAllRequests(): void;
    }
}

// 扩展所有模块以支持 default 导出
declare module './js/adapters/*' {
    const content: any;
    export default content;
    export * from './';
}

declare module './js/components/*' {
    const content: any;
    export default content;
    export * from './';
}

declare module './js/managers/*' {
    const content: any;
    export default content;
    export * from './';
}

declare module './js/config/*' {
    const content: any;
    export default content;
    export * from './';
}

export {};
