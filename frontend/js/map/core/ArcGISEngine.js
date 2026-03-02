import { BaseMapEngine } from './BaseMapEngine.js';

/**
 * ArcGIS 地图引擎
 * 使用 ArcGIS API for JavaScript，内置 Home 控件
 */
export class ArcGISEngine extends BaseMapEngine {
    constructor(options = {}) {
        super();
        this.supportsCustomReset = false;

        this.view = null;
        this.map = null;
        this.options = options;
    }

    /**
     * 初始化地图
     */
    async init(container, options = {}) {
        // 合并选项
        const finalOptions = { ...this.options, ...options };

        // 获取容器
        let containerId;
        if (typeof container === 'string') {
            containerId = container;
        } else {
            containerId = container.id;
        }

        // 动态加载 ArcGIS 模块
        const [Map, MapView, Home] = await Promise.all([
            import('https://js.arcgis.com/4.28/@arcgis/core/Map.js'),
            import('https://js.arcgis.com/4.28/@arcgis/core/views/MapView.js'),
            import('https://js.arcgis.com/4.28/@arcgis/core/widgets/Home.js')
        ].map(p => p.then(m => m.default)));

        // 检测深色模式
        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const basemap = isDark ? 'dark-gray-vector' : 'gray-vector';

        // 创建地图
        this.map = new Map({
            basemap: finalOptions.basemap || basemap
        });

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
        });

        // 添加 Home 控件
        const homeWidget = new Home({ view: this.view });
        this.view.ui.add(homeWidget, 'top-left');

        // 监听缩放变化
        this.view.watch('zoom', (newZoom) => {
            this.triggerZoomCallbacks(newZoom);
        });

        // 监听中心点变化
        this.view.watch('center', (newCenter) => {
            if (newCenter) {
                this.triggerMoveCallbacks([newCenter.longitude, newCenter.latitude]);
            }
        });

        // 监听系统深色模式变化
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', (e) => {
            this.map.basemap = e.matches ? 'dark-gray-vector' : 'gray-vector';
        });

        await this.view.when();

        console.log('✅ ArcGIS 引擎初始化完成');
    }

    /**
     * 设置中心点
     */
    setCenter(center) {
        if (this.view) {
            this.view.center = center;
        }
    }

    /**
     * 获取中心点
     */
    getCenter() {
        if (this.view && this.view.center) {
            return [this.view.center.longitude, this.view.center.latitude];
        }
        return null;
    }

    /**
     * 设置缩放级别
     */
    setZoom(zoom) {
        if (this.view) {
            this.view.zoom = zoom;
        }
    }

    /**
     * 获取缩放级别
     */
    getZoom() {
        return this.view ? this.view.zoom : 0;
    }

    /**
     * 适配到指定边界
     */
    async fitToBounds(bounds) {
        if (!this.view) return;

        const { minLng, minLat, maxLng, maxLat } = bounds;

        // 动态加载 Extent 模块
        const Extent = (await import('https://js.arcgis.com/4.28/@arcgis/core/geometry/Extent.js')).default;

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
    getView() {
        return this.view;
    }

    /**
     * 销毁地图实例
     */
    destroy() {
        super.destroy();
        if (this.view) {
            this.view.destroy();
            this.view = null;
        }
        this.map = null;
    }
}
