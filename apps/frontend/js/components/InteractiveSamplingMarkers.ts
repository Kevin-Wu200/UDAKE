/**
 * 交互式采样点标记组件
 * 支持优先级颜色编码、预期收益显示、实时拖拽重评估和详细信息弹窗
 */
import type { IMapAdapterExtended } from '../../types/app';

/** 推荐点 */
interface Recommendation {
    id: number;
    x: number;
    y: number;
    variance: number;
    priority: string;
    comprehensive_score?: number;
    variance_reduction?: number;
    local_improvement?: number;
    uncertainty_level: number;
    distance_to_nearest: number;
    sampling_reason: string;
    expected_benefit: number;
}

/** 标记配置 */
interface MarkerConfig {
    size: number;
    showLabel: boolean;
    showScore: boolean;
    enableDrag: boolean;
}

/** 标记条目 */
interface MarkerEntry {
    marker: any;
    recommendation: Recommendation;
    popup: any;
}

export class InteractiveSamplingMarkers {
    private mapEngine: IMapAdapterExtended;
    private markers: Map<number, MarkerEntry>;
    private markerConfig: MarkerConfig;
    private onMarkerClick: ((rec: Recommendation) => void) | null = null;
    private onMarkerDrag: ((rec: Recommendation, newPosition: { x: number; y: number }) => void) | null = null;
    private activeMarkerId: number | null = null;

    constructor(mapEngine: IMapAdapterExtended) {
        this.mapEngine = mapEngine;
        this.markers = new Map();
        this.markerConfig = {
            size: 20,
            showLabel: true,
            showScore: true,
            enableDrag: true
        };
        this.onMarkerDrag = null;
        this.activeMarkerId = null;
    }

    /**
     * 创建推荐标记
     */
    public async createRecommendationMarker(rec: Recommendation): Promise<void> {
        try {
            // 使用 addMarker 方法添加标记
            await this.mapEngine.addMarker({
                x: rec.x,
                y: rec.y,
                value: rec.variance
            });

            // 存储标记信息
            this.markers.set(rec.id, {
                marker: { position: [rec.y, rec.x], data: rec },
                recommendation: rec,
                popup: null
            });
        } catch (error) {
            console.error('创建标记失败:', error);
        }
    }

    /**
     * 高亮标记
     */
    public highlightMarker(markerId: number): void {
        // 重置所有标记
        this.markers.forEach((entry, id) => {
            const element = entry.marker.getElement();
            if (element) {
                element.style.transform = id === markerId ? 'scale(1.3)' : 'scale(1)';
                element.style.boxShadow = id === markerId
                    ? '0 6px 12px rgba(0,0,0,0.5)'
                    : '0 2px 4px rgba(0,0,0,0.3)';
            }
        });

        this.activeMarkerId = markerId;
    }

    /**
     * 移除高亮
     */
    public removeHighlight(): void {
        this.markers.forEach((entry) => {
            const element = entry.marker.getElement();
            if (element) {
                element.style.transform = 'scale(1)';
                element.style.boxShadow = '0 2px 4px rgba(0,0,0,0.3)';
            }
        });

        this.activeMarkerId = null;
    }

    /**
     * 批量创建标记
     */
    public createMarkers(recommendations: Recommendation[]): void {
        // 清除现有标记
        this.clearMarkers();

        // 创建新标记
        recommendations.forEach(rec => {
            this.createRecommendationMarker(rec);
        });
    }

    /**
     * 更新标记
     */
    public updateMarker(rec: Recommendation): void {
        const entry = this.markers.get(rec.id);
        if (entry) {
            // 更新标记位置
            if (entry.marker.setLatLng) {
                entry.marker.setLatLng([rec.y, rec.x]);
            }

            // 更新推荐数据
            entry.recommendation = rec;

            // 暂时不更新弹窗内容
        }
    }

    /**
     * 移除标记
     */
    public removeMarker(markerId: number): void {
        const entry = this.markers.get(markerId);
        if (entry) {
            entry.marker.remove();
            entry.popup.remove();
            this.markers.delete(markerId);
        }
    }

    /**
     * 清除所有标记
     */
    public clearMarkers(): void {
        this.markers.forEach((entry) => {
            entry.marker.remove();
            entry.popup.remove();
        });
        this.markers.clear();
        this.activeMarkerId = null;
    }

    /**
     * 设置标记配置
     */
    public setMarkerConfig(config: Partial<MarkerConfig>): void {
        this.markerConfig = { ...this.markerConfig, ...config };
    }

    /**
     * 设置点击回调
     */
    public setOnMarkerClick(callback: ((rec: Recommendation) => void) | null): void {
        this.onMarkerClick = callback;
    }

    /**
     * 设置拖拽回调
     */
    public setOnMarkerDrag(callback: ((rec: Recommendation, newPosition: { x: number; y: number }) => void) | null): void {
        this.onMarkerDrag = callback;
    }

    /**
     * 获取标记数量
     */
    public getMarkerCount(): number {
        return this.markers.size;
    }

    /**
     * 获取所有标记
     */
    public getAllMarkers(): MarkerEntry[] {
        return Array.from(this.markers.values());
    }

    /**
     * 销毁所有标记
     */
    public destroy(): void {
        this.clearMarkers();
        this.onMarkerClick = null;
        this.onMarkerDrag = null;
    }
}