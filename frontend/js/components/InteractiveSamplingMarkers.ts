/**
 * 交互式采样点标记组件
 * 支持优先级颜色编码、预期收益显示、实时拖拽重评估和详细信息弹窗
 */
import { I18n } from '../utils/I18n.js';
import type { MapEngine } from '../config/map.config.js';

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
    private mapEngine: MapEngine;
    private markers: Map<number, MarkerEntry>;
    private markerConfig: MarkerConfig;
    private onMarkerClick: ((rec: Recommendation) => void) | null;
    private onMarkerDrag: ((rec: Recommendation, newPosition: { x: number; y: number }) => void) | null;
    private activeMarkerId: number | null;

    constructor(mapEngine: MapEngine) {
        this.mapEngine = mapEngine;
        this.markers = new Map();
        this.markerConfig = {
            size: 20,
            showLabel: true,
            showScore: true,
            enableDrag: true
        };
        this.onMarkerClick = null;
        this.onMarkerDrag = null;
        this.activeMarkerId = null;
    }

    /**
     * 创建推荐标记
     */
    public createRecommendationMarker(rec: Recommendation): any {
        // 创建自定义标记元素
        const markerElement = this.createMarkerElement(rec);

        // 创建地图标记
        const marker = this.mapEngine.createMarker({
            position: [rec.y, rec.x], // 注意：地图引擎通常使用 [lat, lng] 顺序
            element: markerElement,
            draggable: this.markerConfig.enableDrag
        });

        // 创建信息弹窗
        const popup = this.createPopup(rec);

        // 添加事件监听
        this.attachMarkerEvents(marker, rec, popup);

        // 存储标记
        this.markers.set(rec.id, {
            marker,
            recommendation: rec,
            popup
        });

        return marker;
    }

    /**
     * 创建标记元素
     */
    private createMarkerElement(rec: Recommendation): HTMLElement {
        const element = document.createElement('div');
        element.className = `sampling-marker priority-${rec.priority}`;
        element.style.width = `${this.markerConfig.size}px`;
        element.style.height = `${this.markerConfig.size}px`;
        element.style.position = 'relative';

        // 根据优先级设置颜色
        const color = this.getPriorityColor(rec.priority);
        element.style.backgroundColor = color;
        element.style.borderRadius = '50%';
        element.style.border = '2px solid white';
        element.style.boxShadow = '0 2px 4px rgba(0,0,0,0.3)';
        element.style.cursor = 'pointer';
        element.style.transition = 'transform 0.2s ease, box-shadow 0.2s ease';

        // 添加内圈（表示不确定性等级）
        const innerCircle = document.createElement('div');
        innerCircle.className = 'marker-inner-circle';
        const uncertaintySize = this.markerConfig.size * (1 - rec.uncertainty_level / 5);
        innerCircle.style.width = `${uncertaintySize}px`;
        innerCircle.style.height = `${uncertaintySize}px`;
        innerCircle.style.backgroundColor = 'rgba(255,255,255,0.7)';
        innerCircle.style.borderRadius = '50%';
        innerCircle.style.position = 'absolute';
        innerCircle.style.top = '50%';
        innerCircle.style.left = '50%';
        innerCircle.style.transform = 'translate(-50%, -50%)';
        element.appendChild(innerCircle);

        // 添加评分标签（如果启用）
        if (this.markerConfig.showScore && rec.comprehensive_score !== undefined) {
            const scoreLabel = document.createElement('div');
            scoreLabel.className = 'marker-score';
            scoreLabel.textContent = rec.comprehensive_score.toFixed(2);
            scoreLabel.style.position = 'absolute';
            scoreLabel.style.bottom = '-20px';
            scoreLabel.style.left = '50%';
            scoreLabel.style.transform = 'translateX(-50%)';
            scoreLabel.style.fontSize = '10px';
            scoreLabel.style.fontWeight = 'bold';
            scoreLabel.style.color = color;
            scoreLabel.style.whiteSpace = 'nowrap';
            element.appendChild(scoreLabel);
        }

        // 添加ID标签（如果启用）
        if (this.markerConfig.showLabel) {
            const idLabel = document.createElement('div');
            idLabel.className = 'marker-id';
            idLabel.textContent = `#${rec.id}`;
            idLabel.style.position = 'absolute';
            idLabel.style.top = '-18px';
            idLabel.style.left = '50%';
            idLabel.style.transform = 'translateX(-50%)';
            idLabel.style.fontSize = '11px';
            idLabel.style.fontWeight = 'bold';
            idLabel.style.color = '#333';
            idLabel.style.whiteSpace = 'nowrap';
            element.appendChild(idLabel);
        }

        // 添加动画
        element.addEventListener('mouseenter', () => {
            element.style.transform = 'scale(1.2)';
            element.style.boxShadow = '0 4px 8px rgba(0,0,0,0.4)';
        });

        element.addEventListener('mouseleave', () => {
            if (this.activeMarkerId !== rec.id) {
                element.style.transform = 'scale(1)';
                element.style.boxShadow = '0 2px 4px rgba(0,0,0,0.3)';
            }
        });

        return element;
    }

    /**
     * 创建信息弹窗
     */
    private createPopup(rec: Recommendation): any {
        const popupContent = document.createElement('div');
        popupContent.className = 'marker-popup-content';
        popupContent.innerHTML = `
            <div class="popup-header">
                <span class="popup-title">${I18n.t('marker.title')} #${rec.id}</span>
                <span class="popup-priority priority-${rec.priority}">${rec.priority}</span>
            </div>
            <div class="popup-body">
                <div class="popup-section">
                    <h4>${I18n.t('marker.coordinates')}</h4>
                    <p>X: ${rec.x.toFixed(6)}</p>
                    <p>Y: ${rec.y.toFixed(6)}</p>
                </div>
                <div class="popup-section">
                    <h4>${I18n.t('marker.metrics')}</h4>
                    <p>${I18n.t('marker.variance')}: ${rec.variance.toFixed(6)}</p>
                    <p>${I18n.t('marker.score')}: ${(rec.comprehensive_score || 0).toFixed(3)}</p>
                    ${rec.variance_reduction !== undefined ? `<p>${I18n.t('marker.varianceReduction')}: ${rec.variance_reduction.toFixed(6)}</p>` : ''}
                    ${rec.local_improvement !== undefined ? `<p>${I18n.t('marker.localImprovement')}: ${rec.local_improvement.toFixed(3)}</p>` : ''}
                </div>
                <div class="popup-section">
                    <h4>${I18n.t('marker.analysis')}</h4>
                    <p>${I18n.t('marker.uncertaintyLevel')}: ${rec.uncertainty_level}/5</p>
                    <p>${I18n.t('marker.distanceToNearest')}: ${rec.distance_to_nearest.toFixed(2)}m</p>
                </div>
                <div class="popup-section">
                    <h4>${I18n.t('marker.reason')}</h4>
                    <p>${rec.sampling_reason}</p>
                </div>
                <div class="popup-section">
                    <h4>${I18n.t('marker.expectedBenefit')}</h4>
                    <p class="benefit-value">${rec.expected_benefit.toFixed(6)}</p>
                </div>
            </div>
            <div class="popup-footer">
                <button class="popup-btn preview-btn">${I18n.t('marker.preview')}</button>
                <button class="popup-btn select-btn">${I18n.t('marker.select')}</button>
            </div>
        `;

        // 创建弹窗
        const popup = this.mapEngine.createPopup({
            content: popupContent,
            closeButton: true,
            className: 'sampling-marker-popup'
        });

        // 添加按钮事件
        const previewBtn = popupContent.querySelector('.preview-btn');
        previewBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.triggerPreview(rec);
        });

        const selectBtn = popupContent.querySelector('.select-btn');
        selectBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.triggerSelect(rec);
        });

        return popup;
    }

    /**
     * 附加标记事件
     */
    private attachMarkerEvents(marker: any, rec: Recommendation, popup: any): void {
        // 点击事件
        marker.on('click', (e: any) => {
            this.onMarkerClick?.(rec);
            this.highlightMarker(rec.id);
            popup.open();
        });

        // 悬停事件
        marker.on('mouseover', (e: any) => {
            this.showTooltip(rec, e.originalEvent);
        });

        marker.on('mouseout', (e: any) => {
            this.hideTooltip();
        });

        // 拖拽事件
        if (this.markerConfig.enableDrag) {
            marker.on('dragstart', (e: any) => {
                this.activeMarkerId = rec.id;
            });

            marker.on('drag', (e: any) => {
                const newPosition = {
                    x: e.target.getLatLng().lng,
                    y: e.target.getLatLng().lat
                };
                this.onMarkerDrag?.(rec, newPosition);
            });

            marker.on('dragend', (e: any) => {
                const newPosition = {
                    x: e.target.getLatLng().lng,
                    y: e.target.getLatLng().lat
                };
                this.onMarkerDrag?.(rec, newPosition);
                this.activeMarkerId = null;
            });
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
     * 显示工具提示
     */
    private showTooltip(rec: Recommendation, event: MouseEvent): void {
        // TODO: 实现工具提示
        console.log('Show tooltip for marker', rec.id);
    }

    /**
     * 隐藏工具提示
     */
    private hideTooltip(): void {
        // TODO: 隐藏工具提示
    }

    /**
     * 触发预览
     */
    private triggerPreview(rec: Recommendation): void {
        const event = new CustomEvent('markerPreview', {
            detail: rec
        });
        document.dispatchEvent(event);
    }

    /**
     * 触发选择
     */
    private triggerSelect(rec: Recommendation): void {
        const event = new CustomEvent('markerSelect', {
            detail: rec
        });
        document.dispatchEvent(event);
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
            entry.marker.setLatLng([rec.y, rec.x]);

            // 更新推荐数据
            entry.recommendation = rec;

            // 更新弹窗内容
            entry.popup.setContent(this.createPopup(rec).getContent());
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
     * 获取优先级颜色
     */
    private getPriorityColor(priority: string): string {
        switch (priority) {
            case 'high': return '#ff4444';
            case 'medium': return '#ffbb33';
            case 'low': return '#00C851';
            default: return '#33b5e5';
        }
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