/**
 * 实时地图更新组件
 * Realtime Map Updater Component

实现地图增量更新、热点区域高亮和动画效果
支持多种更新策略和视觉反馈
 */

import { RealtimeInterpolation, RealtimeUpdate, HotspotArea } from './RealtimeInterpolation';

export interface MapUpdateOptions {
    animationDuration: number; // 动画持续时间（毫秒）
    colorScale: string[]; // 颜色渐变
    hotspotColor: string; // 热点颜色
    hotspotIntensityThreshold: number; // 热点强度阈值
    enableAnimations: boolean; // 是否启用动画
    updateStrategy: 'incremental' | 'full' | 'hybrid'; // 更新策略
}

export interface UpdateAnimation {
    id: string;
    startTime: number;
    duration: number;
    affectedArea: {
        minLon: number;
        minLat: number;
        maxLon: number;
        maxLat: number;
    };
    progress: number;
}

export class RealtimeMapUpdater {
    private realtimeInterpolation: RealtimeInterpolation;
    private options: MapUpdateOptions;
    private map: any; // ArcGIS MapView
    private activeAnimations: Map<string, UpdateAnimation> = new Map();
    private heatmapLayer: any = null;
    private hotspotGraphics: Map<string, any> = new Map();
    private isInitialized = false;

    constructor(map: any, options: Partial<MapUpdateOptions> = {}) {
        this.map = map;
        this.realtimeInterpolation = new RealtimeInterpolation();
        this.options = {
            animationDuration: 1000,
            colorScale: ['#00ff00', '#ffff00', '#ff0000'],
            hotspotColor: 'rgba(255, 0, 0, 0.6)',
            hotspotIntensityThreshold: 0.7,
            enableAnimations: true,
            updateStrategy: 'hybrid',
            ...options
        };
    }

    /**
     * 初始化组件
     */
    async initialize(): Promise<void> {
        if (this.isInitialized) {
            return;
        }

        try {
            // 初始化实时插值组件
            await this.realtimeInterpolation.initialize();

            // 注册更新回调
            this.realtimeInterpolation.onUpdate(this.handleUpdate.bind(this));
            this.realtimeInterpolation.onHotspot(this.handleHotspots.bind(this));

            // 创建热力图层
            await this.createHeatmapLayer();

            this.isInitialized = true;
            console.log('实时地图更新组件初始化成功');
        } catch (error) {
            console.error('实时地图更新组件初始化失败:', error);
            throw error;
        }
    }

    /**
     * 处理更新
     */
    private async handleUpdate(update: RealtimeUpdate): Promise<void> {
        if (!this.map) {
            console.warn('地图未初始化');
            return;
        }

        try {
            // 根据更新策略处理更新
            switch (this.options.updateStrategy) {
                case 'incremental':
                    await this.applyIncrementalUpdate(update);
                    break;
                case 'full':
                    await this.applyFullUpdate(update);
                    break;
                case 'hybrid':
                    await this.applyHybridUpdate(update);
                    break;
            }

            // 添加更新动画
            if (this.options.enableAnimations) {
                this.addUpdateAnimation(update);
            }

            console.log('地图更新成功:', update);
        } catch (error) {
            console.error('地图更新失败:', error);
        }
    }

    /**
     * 应用增量更新
     */
    private async applyIncrementalUpdate(update: RealtimeUpdate): Promise<void> {
        // 只更新受影响的区域
        const { minLon, minLat, maxLon, maxLat } = update.affectedArea;

        // 获取增量数据
        const updateData = await this.fetchUpdateData(update.subscriptionId, {
            minLon, minLat, maxLon, maxLat
        });

        // 更新热力图层
        if (this.heatmapLayer && updateData) {
            await this.updateHeatmapLayer(updateData);
        }
    }

    /**
     * 应用全量更新
     */
    private async applyFullUpdate(update: RealtimeUpdate): Promise<void> {
        // 获取全量数据
        const updateData = await this.fetchUpdateData(update.subscriptionId);

        // 更新热力图层
        if (this.heatmapLayer && updateData) {
            await this.updateHeatmapLayer(updateData);
        }
    }

    /**
     * 应用混合更新
     */
    private async applyHybridUpdate(update: RealtimeUpdate): Promise<void> {
        // 根据影响区域大小决定使用增量还是全量更新
        const area = this.calculateArea(update.affectedArea);

        if (area < 100) { // 面积小于100平方公里使用增量更新
            await this.applyIncrementalUpdate(update);
        } else {
            await this.applyFullUpdate(update);
        }
    }

    /**
     * 处理热点区域
     */
    private async handleHotspots(hotspots: HotspotArea[]): Promise<void> {
        if (!this.map) {
            console.warn('地图未初始化');
            return;
        }

        try {
            // 移除旧的热点图形
            this.removeOldHotspots(hotspots);

            // 添加新的热点图形
            await this.addHotspotGraphics(hotspots);

            console.log('热点区域更新成功:', hotspots);
        } catch (error) {
            console.error('热点区域更新失败:', error);
        }
    }

    /**
     * 添加热点图形
     */
    private async addHotspotGraphics(hotspots: HotspotArea[]): Promise<void> {
        if (!this.map || !this.map.graphics) {
            return;
        }

        for (const hotspot of hotspots) {
            // 跳过低强度热点
            if (hotspot.intensity < this.options.hotspotIntensityThreshold) {
                continue;
            }

            // 检查是否已存在
            if (this.hotspotGraphics.has(hotspot.id)) {
                // 更新现有热点
                const graphic = this.hotspotGraphics.get(hotspot.id);
                graphic.attributes.intensity = hotspot.intensity;
                graphic.attributes.trend = hotspot.trend;
                continue;
            }

            // 创建新的热点图形
            const circle = {
                type: 'circle',
                center: {
                    longitude: hotspot.center.lon,
                    latitude: hotspot.center.lat
                },
                radius: hotspot.radius * 1000, // 转换为米
            };

            const symbol = {
                type: 'simple-fill',
                color: this.getHotspotColor(hotspot.intensity),
                outline: {
                    color: [255, 255, 255, 0.5],
                    width: 2
                }
            };

            const graphic = {
                geometry: circle,
                symbol: symbol,
                attributes: {
                    id: hotspot.id,
                    intensity: hotspot.intensity,
                    trend: hotspot.trend,
                    name: `热点 ${hotspot.id}`
                },
                popupTemplate: {
                    title: '{name}',
                    content: `
                        <div>
                            <p><strong>强度:</strong> {intensity:.2f}</p>
                            <p><strong>趋势:</strong> {trend}</p>
                            <p><strong>半径:</strong> ${hotspot.radius.toFixed(1)} km</p>
                        </div>
                    `
                }
            };

            // 添加到地图
            this.map.graphics.add(graphic);
            this.hotspotGraphics.set(hotspot.id, graphic);
        }
    }

    /**
     * 移除旧的热点图形
     */
    private removeOldHotspots(currentHotspots: HotspotArea[]): void {
        if (!this.map || !this.map.graphics) {
            return;
        }

        const currentIds = new Set(currentHotspots.map(h => h.id));

        // 移除不存在的热点
        for (const [id, graphic] of this.hotspotGraphics) {
            if (!currentIds.has(id)) {
                this.map.graphics.remove(graphic);
                this.hotspotGraphics.delete(id);
            }
        }
    }

    /**
     * 添加更新动画
     */
    private addUpdateAnimation(update: RealtimeUpdate): void {
        const animationId = `animation_${update.subscriptionId}_${Date.now()}`;
        const animation: UpdateAnimation = {
            id: animationId,
            startTime: Date.now(),
            duration: this.options.animationDuration,
            affectedArea: update.affectedArea,
            progress: 0
        };

        this.activeAnimations.set(animationId, animation);

        // 开始动画
        this.animateUpdate(animation);
    }

    /**
     * 动画更新
     */
    private animateUpdate(animation: UpdateAnimation): void {
        const now = Date.now();
        const elapsed = now - animation.startTime;
        animation.progress = Math.min(elapsed / animation.duration, 1);

        // 创建或更新动画图形
        this.updateAnimationGraphic(animation);

        // 继续动画
        if (animation.progress < 1) {
            requestAnimationFrame(() => this.animateUpdate(animation));
        } else {
            // 移除动画
            this.activeAnimations.delete(animation.id);
            this.removeAnimationGraphic(animation);
        }
    }

    /**
     * 更新动画图形
     */
    private updateAnimationGraphic(animation: UpdateAnimation): void {
        if (!this.map || !this.map.graphics) {
            return;
        }

        // 创建闪烁效果
        const opacity = 0.5 * Math.sin(animation.progress * Math.PI);

        // 创建或更新动画图形
        let graphic = this.activeAnimations.get(animation.id) as any;
        if (!graphic) {
            // 创建新的动画图形
            const polygon = {
                type: 'polygon',
                rings: [
                    [
                        [animation.affectedArea.minLon, animation.affectedArea.minLat],
                        [animation.affectedArea.maxLon, animation.affectedArea.minLat],
                        [animation.affectedArea.maxLon, animation.affectedArea.maxLat],
                        [animation.affectedArea.minLon, animation.affectedArea.maxLat],
                        [animation.affectedArea.minLon, animation.affectedArea.minLat]
                    ]
                ]
            };

            const symbol = {
                type: 'simple-fill',
                color: [0, 255, 0, opacity],
                outline: {
                    color: [0, 255, 0, 0.8],
                    width: 2
                }
            };

            graphic = {
                geometry: polygon,
                symbol: symbol,
                attributes: {
                    animationId: animation.id
                }
            };

            this.map.graphics.add(graphic);
            this.activeAnimations.set(animation.id, graphic as any);
        } else {
            // 更新现有图形
            graphic.symbol.color[3] = opacity;
        }
    }

    /**
     * 移除动画图形
     */
    private removeAnimationGraphic(animation: UpdateAnimation): void {
        if (!this.map || !this.map.graphics) {
            return;
        }

        const graphic = this.activeAnimations.get(animation.id) as any;
        if (graphic) {
            this.map.graphics.remove(graphic);
        }
    }

    /**
     * 创建热力图层
     */
    private async createHeatmapLayer(): Promise<void> {
        // 这里需要根据实际的地图引擎创建热力图层
        // GeoScene Maps SDK的实现示例
        console.log('创建热力图层');
    }

    /**
     * 更新热力图层
     */
    private async updateHeatmapLayer(data: any): Promise<void> {
        // 这里需要根据实际的地图引擎更新热力图层
        // GeoScene Maps SDK的实现示例
        console.log('更新热力图层:', data);
    }

    /**
     * 获取更新数据
     */
    private async fetchUpdateData(subscriptionId: string, area?: any): Promise<any> {
        // 这里需要从后端API获取更新数据
        // 实现示例
        console.log('获取更新数据:', subscriptionId, area);
        return null;
    }

    /**
     * 计算区域面积
     */
    private calculateArea(area: {
        minLon: number;
        minLat: number;
        maxLon: number;
        maxLat: number;
    }): number {
        // 简化的面积计算（单位：平方公里）
        const width = (area.maxLon - area.minLon) * 111; // 1度约等于111公里
        const height = (area.maxLat - area.minLat) * 111;
        return width * height;
    }

    /**
     * 获取热点颜色
     */
    private getHotspotColor(intensity: number): string {
        // 根据强度返回颜色
        const index = Math.floor(intensity * (this.options.colorScale.length - 1));
        return this.options.colorScale[Math.min(index, this.options.colorScale.length - 1)];
    }

    /**
     * 更新选项
     */
    updateOptions(options: Partial<MapUpdateOptions>): void {
        this.options = { ...this.options, ...options };
    }

    /**
     * 销毁组件
     */
    destroy(): void {
        // 停止实时插值
        this.realtimeInterpolation.destroy();

        // 移除所有热点图形
        if (this.map && this.map.graphics) {
            for (const graphic of this.hotspotGraphics.values()) {
                this.map.graphics.remove(graphic);
            }
        }
        this.hotspotGraphics.clear();

        // 停止所有动画
        for (const animation of this.activeAnimations.values()) {
            this.removeAnimationGraphic(animation);
        }
        this.activeAnimations.clear();

        this.isInitialized = false;
        console.log('实时地图更新组件已销毁');
    }
}

export default RealtimeMapUpdater;
