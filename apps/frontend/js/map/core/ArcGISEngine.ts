/**
 * ArcGIS 地图引擎
 * 使用 ArcGIS API for JavaScript，内置 Home 控件
 */

import { BaseMapEngine } from './BaseMapEngine';
import type { Bounds, MapInitOptions, ArcGISConfig, IMapView, IMap } from '../../../types/map-engine';

/**
 * ArcGIS 地图引擎
 * 使用 ArcGIS API for JavaScript 实现地图功能
 */
export class ArcGISEngine extends BaseMapEngine {
    /** ArcGIS MapView 实例 */
    view: IMapView | null;

    /** ArcGIS Map 实例 */
    map: IMap | null;

    /** 配置选项 */
    options: ArcGISConfig;

    constructor(options: ArcGISConfig = {}) {
        super();
        this.supportsCustomReset = false;

        this.view = null;
        this.map = null;
        this.options = options;
    }

    /**
     * 初始化地图
     */
    async init(container: HTMLElement | string, options: MapInitOptions = {}): Promise<void> {
        // 合并选项
        const finalOptions = { ...this.options, ...options };

        // 获取容器
        let containerId: string;
        if (typeof container === 'string') {
            containerId = container;
        } else {
            containerId = container.id;
        }

        // 动态加载 ArcGIS 模块
        const [Map, MapView, Home]: [any, any, any] = await Promise.all([
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            import('@geoscene/core/Map').then((m: any) => m.default),
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            import('@geoscene/core/views/MapView').then((m: any) => m.default),
            // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
            import('@geoscene/core/widgets/Home').then((m: any) => m.default)
        ]);

        // 检测深色模式
        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const basemap = finalOptions.basemap || (isDark ? 'dark-gray-vector' : 'gray-vector');

        // 创建地图
        this.map = new Map({
            basemap: basemap as any
        }) as any;

        // 创建视图
        this.view = new MapView({
            container: containerId,
            map: this.map,
            center: finalOptions.center || [116.39, 39.9],
            zoom: finalOptions.zoom || 5,
            constraints: {
                minZoom: finalOptions.minZoom || 1,
                maxZoom: finalOptions.maxZoom || 18
            },
            ui: {
                components: ['attribution']
            }
        }) as any;

        // 添加 Home 控件
        const homeWidget = new Home({ view: this.view }) as any;
        this.view!.ui.add(homeWidget, 'top-left');

        // 监听缩放变化
        this.view!.watch('zoom', (newZoom: number) => {
            this.triggerZoomCallbacks(newZoom);
        });

        // 监听中心点变化
        this.view!.watch('center', (newCenter: any) => {
            if (newCenter) {
                this.triggerMoveCallbacks([newCenter.longitude, newCenter.latitude]);
            }
        });

        // 监听系统深色模式变化
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', (e: MediaQueryListEvent) => {
            if (this.map) {
                this.map.basemap = e.matches ? 'dark-gray-vector' : 'gray-vector';
            }
        });

        await this.view!.when();

        console.log('✅ GeoScene 引擎初始化完成');
    }

    /**
     * 设置中心点
     */
    setCenter(center: [number, number]): void {
        if (this.view) {
            this.view.center = center as any;
        }
    }

    /**
     * 获取中心点
     */
    getCenter(): [number, number] {
        if (this.view && this.view.center) {
            return [this.view.center.longitude, this.view.center.latitude];
        }
        return [0, 0]; // 默认返回中心点
    }

    /**
     * 设置缩放级别
     */
    setZoom(zoom: number): void {
        if (this.view) {
            this.view.zoom = zoom;
        }
    }

    /**
     * 获取缩放级别
     */
    getZoom(): number {
        return this.view ? this.view.zoom : 0;
    }

    /**
     * 适配到指定边界
     */
    async fitToBounds(bounds: Bounds): Promise<void> {
        if (!this.view) return;

        const { minLng, minLat, maxLng, maxLat } = bounds;

        // 动态加载 Extent 模块
        // @ts-ignore - ArcGIS 模块通过 global.d.ts 声明
        const Extent: any = (await import('@geoscene/core/geometry/Extent')).default;

        const extent = new Extent({
            xmin: minLng,
            ymin: minLat,
            xmax: maxLng,
            ymax: maxLat,
            spatialReference: this.view.spatialReference
        });

        await this.view.goTo({ target: extent });
    }

    /**
     * 获取 ArcGIS MapView 实例（用于兼容现有代码）
     */
    getView(): IMapView | null {
        return this.view;
    }

    /**
     * 销毁地图实例
     */
    destroy(): void {
        super.destroy();
        if (this.view) {
            this.view.destroy();
            this.view = null;
        }
        this.map = null;
    }
}
