/**
 * 全局类型声明
 * 处理动态导入和缺失的类型定义
 */

// 动态导入 ArcGIS 模块
declare module 'https://js.arcgis.com/4.28/@arcgis/core/Map.js' {
    class Map {
        constructor(options: { basemap: string });
        basemap: string;
        destroy(): void;
    }
    export default Map;
}

declare module 'https://js.arcgis.com/4.28/@arcgis/core/views/MapView.js' {
    import Map from 'https://js.arcgis.com/4.28/@arcgis/core/Map.js';
    class MapView {
        constructor(options: {
            container: string;
            map: Map;
            center?: [number, number];
            zoom?: number;
            constraints?: { minZoom?: number; maxZoom?: number };
            ui?: { components: string[] };
        });
        center: { longitude: number; latitude: number };
        zoom: number;
        spatialReference: any;
        ui: {
            components: string[];
            add(widget: any, position: string): void;
        };
        destroy(): void;
        when(): Promise<void>;
        watch(property: string, callback: (newValue: any) => void): any;
        goTo(options: any): Promise<void>;
    }
    export default MapView;
}

declare module 'https://js.arcgis.com/4.28/@arcgis/core/widgets/Home.js' {
    class Home {
        constructor(options: { view: any });
    }
    export default Home;
}

declare module 'https://js.arcgis.com/4.28/@arcgis/core/geometry/Extent.js' {
    class Extent {
        constructor(options: {
            xmin: number;
            ymin: number;
            xmax: number;
            ymax: number;
            spatialReference: any;
        });
    }
    export default Extent;
}

declare module 'https://js.arcgis.com/4.28/@arcgis/core/layers/GeoJSONLayer.js' {
    class GeoJSONLayer {
        constructor(options: any);
        title: string;
        fullExtent: any;
        visible: boolean;
        opacity: number;
        when(): Promise<void>;
    }
    export default GeoJSONLayer;
}

declare module 'https://js.arcgis.com/4.28/@arcgis/core/layers/ImageryLayer.js' {
    class ImageryLayer {
        constructor(options: any);
        title: string;
        opacity: number;
        when(): Promise<void>;
    }
    export default ImageryLayer;
}

declare module 'https://js.arcgis.com/4.28/@arcgis/core/layers/GraphicsLayer.js' {
    class GraphicsLayer {
        constructor(options: any);
        title: string;
        graphics: any[];
        add(graphic: any): void;
        removeAll(): void;
    }
    export default GraphicsLayer;
}

declare module 'https://js.arcgis.com/4.28/@arcgis/core/Graphic.js' {
    class Graphic {
        constructor(options: any);
        geometry: any;
        symbol: any;
        attributes: any;
    }
    export default Graphic;
}

declare module 'https://js.arcgis.com/4.28/@arcgis/core/geometry/Point.js' {
    class Point {
        constructor(options: any);
    }
    export default Point;
}

declare module 'https://js.arcgis.com/4.28/@arcgis/core/geometry/Polygon.js' {
    class Polygon {
        constructor(options: any);
    }
    export default Polygon;
}

declare module 'https://js.arcgis.com/4.28/@arcgis/core/symbols/SimpleMarkerSymbol.js' {
    class SimpleMarkerSymbol {
        constructor(options: any);
    }
    export default SimpleMarkerSymbol;
}

declare module 'https://js.arcgis.com/4.28/@arcgis/core/symbols/SimpleFillSymbol.js' {
    class SimpleFillSymbol {
        constructor(options: any);
    }
    export default SimpleFillSymbol;
}

declare module 'https://js.arcgis.com/4.28/@arcgis/core/geometry/*' {
    export default any;
}

declare module 'https://js.arcgis.com/4.28/@arcgis/core/geometry/projection.js' {
    export function load(): Promise<void>;
    export function project(geom: any, spatialReference: any): any;
    export default any;
}

// 处理 HTML 扩展
declare global {
    interface HTMLInputElement {
        files: FileList | null;
    }

    interface Element {
        style?: any;
    }
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