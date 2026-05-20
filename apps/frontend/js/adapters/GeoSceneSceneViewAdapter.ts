/**
 * GeoScene SceneView 扩展
 * 在 GeoSceneAdapter 基础上增加 3D SceneView 支持,
 * 用于无人机视角的 3D 地形漫游
 *
 * 功能:
 * - SceneView 初始化 (地形+底图)
 * - 2D MapView ↔ 3D SceneView 平滑切换
 * - 插值栅格贴图叠加到地形表面
 * - 相机视角同步 (与 DroneViewController 配合)
 */

import type { ViewSnapshot } from '../../types/visualization';

/** SceneView 相机状态 */
export interface SceneViewCamera {
    /** 经度 */
    longitude: number;
    /** 纬度 */
    latitude: number;
    /** 高度(米) */
    altitude: number;
    /** 朝向角(度) */
    heading: number;
    /** 俯仰角(度) */
    tilt: number;
}

/** SceneView 配置 */
export interface GeoSceneSceneViewConfig {
    /** 挂载容器ID */
    containerId: string;
    /** 初始中心点 */
    center?: [number, number];
    /** 初始缩放 */
    zoom?: number;
    /** 地形服务 URL (可选) */
    terrainUrl?: string;
    /** 是否启用地形高程 */
    enableTerrain?: boolean;
    /** 天空大气效果 */
    enableAtmosphere?: boolean;
}

/** GeoSceneSceneViewAdapter - SceneView 适配器 */
export class GeoSceneSceneViewAdapter {
    /** GeoScene SceneView 实例 */
    private sceneView: any = null;

    /** GeoScene Scene 实例 */
    private scene: any = null;

    /** 配置 */
    private config: GeoSceneSceneViewConfig;

    /** 地形图层 */
    private groundLayer: any = null;

    /** 栅格叠加图层存储 */
    private rasterLayers: Map<string, any> = new Map();

    /** 初始化完成 Promise */
    private readyPromise: Promise<void> | null = null;

    /** 是否已销毁 */
    private destroyed: boolean = false;

    /** 相机变化监听器句柄 */
    private cameraWatchHandle: any = null;

    /** 相机变化回调 */
    private onCameraChanged: ((camera: SceneViewCamera) => void) | null = null;

    constructor(config: GeoSceneSceneViewConfig) {
        this.config = {
            enableTerrain: true,
            enableAtmosphere: true,
            center: [116.39, 39.90],
            zoom: 12,
            ...config,
        };
    }

    /**
     * 初始化 SceneView
     */
    async initialize(): Promise<void> {
        if (this.destroyed) return;
        if (this.readyPromise) return this.readyPromise;

        this.readyPromise = this._doInitialize();
        return this.readyPromise;
    }

    private async _doInitialize(): Promise<void> {
        const { containerId, center, zoom, terrainUrl, enableTerrain, enableAtmosphere } = this.config;

        try {
            // 动态加载 GeoScene 模块
            const [SceneView, WebScene, Ground, ElevationLayer]: [any, any, any, any] = await Promise.all([
                import('@geoscene/core/views/SceneView').then((m: any) => m.default),
                import('@geoscene/core/WebScene').then((m: any) => m.default),
                import('@geoscene/core/Ground').then((m: any) => m.default),
                import('@geoscene/core/layers/ElevationLayer').then((m: any) => m.default),
            ]);

            // 检测深色模式
            const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            const basemap = isDark ? 'dark-gray-vector' : 'gray-vector';

            // 创建 WebScene
            this.scene = new WebScene({
                basemap: basemap,
            });

            // 配置地形
            if (enableTerrain) {
                const elevationLayer = new ElevationLayer({
                    url: terrainUrl || 'https://elevation3d.arcgis.com/arcgis/rest/services/WorldElevation3D/Terrain3D/ImageServer',
                });
                this.groundLayer = new Ground({
                    layers: [elevationLayer],
                });
                this.scene.ground = this.groundLayer;
            }

            // 创建 SceneView
            this.sceneView = new SceneView({
                container: containerId,
                map: this.scene,
                camera: {
                    position: {
                        x: center![0],
                        y: center![1],
                        z: 2000,
                        spatialReference: { wkid: 4326 },
                    },
                    heading: 0,
                    tilt: 45,
                },
                zoom: zoom,
                environment: {
                    atmosphereEnabled: enableAtmosphere,
                    starsEnabled: true,
                },
                ui: {
                    components: ['attribution'],
                },
                // 性能优化
                qualityProfile: 'high',
                popup: { autoOpenEnabled: false },
            });

            await this.sceneView.when();
            console.log('✅ GeoScene SceneView 初始化完成 (3D 地形模式)');

            // 监听相机变化
            this.cameraWatchHandle = this.sceneView.watch('camera', (camera: any) => {
                if (this.onCameraChanged && camera && camera.position) {
                    this.onCameraChanged({
                        longitude: camera.position.longitude,
                        latitude: camera.position.latitude,
                        altitude: camera.position.z,
                        heading: camera.heading,
                        tilt: camera.tilt,
                    });
                }
            });

        } catch (error) {
            console.error('❌ GeoScene SceneView 初始化失败:', error);
            // 回退到无地形模式
            await this._fallbackInitialize();
        }
    }

    /**
     * 回退初始化 (无地形)
     */
    private async _fallbackInitialize(): Promise<void> {
        const { containerId, center, zoom } = this.config;
        console.warn('⚠️ 使用无地形的 SceneView 回退模式');

        const [SceneView, WebScene]: [any, any] = await Promise.all([
            import('@geoscene/core/views/SceneView').then((m: any) => m.default),
            import('@geoscene/core/WebScene').then((m: any) => m.default),
        ]);

        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        this.scene = new WebScene({
            basemap: isDark ? 'dark-gray-vector' : 'gray-vector',
        });

        this.sceneView = new SceneView({
            container: containerId,
            map: this.scene,
            camera: {
                position: {
                    x: center![0],
                    y: center![1],
                    z: 2000,
                    spatialReference: { wkid: 4326 },
                },
                heading: 0,
                tilt: 45,
            },
            zoom: zoom,
            ui: { components: ['attribution'] },
            qualityProfile: 'medium',
        });

        await this.sceneView.when();
        console.log('✅ GeoScene SceneView 回退模式初始化完成');
    }

    /**
     * 平滑切换相机到目标状态
     * 使用 goTo 实现平滑动画过渡
     */
    async flyToCamera(camera: SceneViewCamera, durationMs: number = 1000): Promise<void> {
        if (!this.sceneView || this.destroyed) return;

        try {
            await this.sceneView.goTo(
                {
                    position: {
                        x: camera.longitude,
                        y: camera.latitude,
                        z: camera.altitude,
                        spatialReference: { wkid: 4326 },
                    },
                    heading: camera.heading,
                    tilt: camera.tilt,
                },
                {
                    duration: durationMs,
                    easing: 'out-expo',
                }
            );
        } catch (error) {
            // goTo 可能因快速连续调用而被中断, 静默处理
        }
    }

    /**
     * 即时设置相机(无动画)
     */
    setCameraImmediate(camera: SceneViewCamera): void {
        if (!this.sceneView || this.destroyed) return;

        this.sceneView.camera = {
            position: {
                x: camera.longitude,
                y: camera.latitude,
                z: camera.altitude,
                spatialReference: { wkid: 4326 },
            },
            heading: camera.heading,
            tilt: camera.tilt,
        };
    }

    /**
     * 从 ViewSnapshot 设置相机
     */
    setCameraFromSnapshot(view: ViewSnapshot, altitude: number): void {
        this.setCameraImmediate({
            longitude: view.center.x,
            latitude: view.center.y,
            altitude: altitude,
            heading: view.heading,
            tilt: view.tilt,
        });
    }

    /**
     * 添加栅格图层叠加到地形表面
     */
    async addRasterOverlay(url: string, layerId: string, opacity: number = 0.7): Promise<void> {
        if (!this.scene || this.destroyed) return;

        try {
            const ImageryLayer: any = (await import('@geoscene/core/layers/ImageryLayer')).default;
            const layer = new ImageryLayer({
                url: url,
                opacity: opacity,
            });

            // 移除旧图层
            this.removeRasterOverlay(layerId);

            this.scene.add(layer);
            this.rasterLayers.set(layerId, layer);

            await layer.when();
            console.log(`✅ 栅格图层 ${layerId} 已叠加到 3D 地形`);
        } catch (error) {
            console.error(`❌ 添加栅格图层 ${layerId} 失败:`, error);
        }
    }

    /**
     * 移除栅格图层
     */
    removeRasterOverlay(layerId: string): void {
        const layer = this.rasterLayers.get(layerId);
        if (layer && this.scene) {
            this.scene.remove(layer);
            this.rasterLayers.delete(layerId);
        }
    }

    /**
     * 设置栅格图层透明度
     */
    setRasterOpacity(layerId: string, opacity: number): void {
        const layer = this.rasterLayers.get(layerId);
        if (layer) {
            layer.opacity = opacity;
        }
    }

    /**
     * 设置相机变化回调
     */
    setOnCameraChanged(callback: ((camera: SceneViewCamera) => void) | null): void {
        this.onCameraChanged = callback;
    }

    /**
     * 获取当前相机状态
     */
    getCurrentCamera(): SceneViewCamera | null {
        if (!this.sceneView || !this.sceneView.camera || !this.sceneView.camera.position) {
            return null;
        }
        const cam = this.sceneView.camera;
        return {
            longitude: cam.position.longitude,
            latitude: cam.position.latitude,
            altitude: cam.position.z,
            heading: cam.heading,
            tilt: cam.tilt,
        };
    }

    /**
     * 获取 SceneView 实例
     */
    getSceneView(): any {
        return this.sceneView;
    }

    /**
     * 获取 Scene 实例
     */
    getScene(): any {
        return this.scene;
    }

    /**
     * 是否已初始化
     */
    isReady(): boolean {
        return this.sceneView != null && !this.destroyed;
    }

    /**
     * 销毁 SceneView
     */
    destroy(): void {
        this.destroyed = true;

        if (this.cameraWatchHandle != null) {
            try { this.cameraWatchHandle.remove(); } catch (_) { /* ignore */ }
            this.cameraWatchHandle = null;
        }

        this.rasterLayers.clear();

        if (this.sceneView) {
            try { this.sceneView.destroy(); } catch (_) { /* ignore */ }
            this.sceneView = null;
        }

        this.scene = null;
        this.groundLayer = null;
        this.readyPromise = null;
    }
}
