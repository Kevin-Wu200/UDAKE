/**
 * 采样建议面板组件
 * 在右侧显示建议的待采样点，按不确定性排序
 */
import { APIService } from '../services/API封装.js';
import { MapConfig } from '../config/map.config.js';
import type { Bounds } from '../../types/core';

import { I18n } from '../utils/I18n.js';

/** 采样建议点 */
interface Recommendation {
    id: number;
    x: number;
    y: number;
    variance: number;
    priority: string;
    uncertainty_level: number;
    distance_to_nearest: number;
    sampling_reason: string;
}

/** 标记条目 */
interface MarkerEntry {
    marker: any;
    rec: Recommendation;
}

export class SamplingRecommendationPanel {
    private view: any;
    private layerManager: any;
    private onRecommendationSelect: ((rec: Recommendation) => void) | null;
    private apiService: APIService;
    private currentTaskId: string | null;
    private recommendations: Recommendation[];
    private markers: MarkerEntry[];
    private mapProvider: string;
    private readonly MAX_VISIBLE_MARKERS: number;
    private markerPool: any[];
    private visibleMarkers: any[];
    private _viewChangeTimer: ReturnType<typeof setTimeout> | null;
    private clusterHint: HTMLDivElement | null;
    private markerLayer: any;

    constructor(view: any, layerManager: any, onRecommendationSelect: ((rec: Recommendation) => void) | null) {
        this.view = view;
        this.layerManager = layerManager;
        this.onRecommendationSelect = onRecommendationSelect;
        this.apiService = new APIService();
        this.currentTaskId = null;
        this.recommendations = [];
        this.markers = [];
        this.mapProvider = MapConfig.getProvider();
        this.MAX_VISIBLE_MARKERS = 50;
        this.markerPool = [];
        this.visibleMarkers = [];
        this._viewChangeTimer = null;
        this.clusterHint = null;
        this.markerLayer = null;
        this._setupViewportListener();
    }

    public updateUIText(): void {
        const panel = document.getElementById('sampling-recommendation-panel');
        if (!panel) return;

        // 更新标题和描述
        const title = panel.querySelector('.section-title');
        if (title) {
            title.textContent = I18n.t('recommendation.title');
        }

        const description = panel.querySelector('.section-description');
        if (description) {
            description.textContent = I18n.t('recommendation.description');
        }

        // 更新标签
        const strategyLabel = panel.querySelector('label[for="recommendation-strategy"]');
        if (strategyLabel) {
            strategyLabel.textContent = I18n.t('recommendation.strategy');
        }

        const countLabel = panel.querySelector('label[for="recommendation-count"]');
        if (countLabel) {
            countLabel.textContent = '建议点数量';
        }

        // 更新按钮
        const generateBtn = panel.querySelector('#generate-recommendations-btn');
        if (generateBtn) {
            generateBtn.textContent = I18n.t('recommendation.generate');
        }

        // 更新下拉选项
        const strategySelect = panel.querySelector('#recommendation-strategy') as HTMLSelectElement;
        if (strategySelect) {
            const options = strategySelect.querySelectorAll('option');
            if (options[0]) options[0].textContent = I18n.t('recommendation.strategy.hybrid');
            if (options[1]) options[1].textContent = '基于方差优先';
            if (options[2]) options[2].textContent = '基于空间覆盖';
        }
    }

    createPanel(): HTMLDivElement {
        const container = document.createElement('div');
        container.className = 'sampling-recommendation-panel';
        container.id = 'sampling-recommendation-panel';
        container.innerHTML = `
            <div class="panel-header">
                <h3 class="section-title" data-i18n="recommendation.title">${I18n.t('recommendation.title')}</h3>
                <p class="section-description" data-i18n="recommendation.description">${I18n.t('recommendation.description')}</p>
            </div>
            <div class="controls-section">
                <div class="form-group">
                    <label for="recommendation-strategy" data-i18n="recommendation.strategy">${I18n.t('recommendation.strategy')}</label>
                    <select id="recommendation-strategy" class="select">
                        <option value="hybrid">${I18n.t('recommendation.strategy.hybrid')}</option>
                        <option value="variance_based">基于方差优先</option>
                        <option value="spatial_coverage">基于空间覆盖</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="recommendation-count">建议点数量</label>
                    <input type="number" id="recommendation-count" class="input" value="20" min="5" max="50">
                </div>
                <button id="generate-recommendations-btn" class="btn btn-primary" disabled>
                    生成建议
                </button>
                <div id="recommendation-status" class="status-message" role="status" aria-live="polite" style="display: none;"></div>
            </div>
            <div id="recommendations-container" style="display: none;">
                <div class="recommendations-header">
                    <span class="recommendations-count" aria-live="polite">建议点：0</span>
                    <button id="export-recommendations-btn" class="btn btn-export">导出 GeoJSON</button>
                </div>
                <div id="recommendations-list" class="recommendations-list" role="list" aria-label="采样建议列表"></div>
            </div>
        `;
        this.bindEvents(container);
        return container;
    }

    private bindEvents(container: HTMLDivElement): void {
        const generateBtn = container.querySelector('#generate-recommendations-btn') as HTMLButtonElement;
        const strategySelect = container.querySelector('#recommendation-strategy') as HTMLSelectElement;
        const countInput = container.querySelector('#recommendation-count') as HTMLInputElement;
        const exportBtn = container.querySelector('#export-recommendations-btn') as HTMLButtonElement;
        generateBtn.addEventListener('click', () => this.generateRecommendations());
        strategySelect.addEventListener('change', () => {
            if (this.currentTaskId) this.generateRecommendations();
        });
        countInput.addEventListener('change', () => {
            if (this.currentTaskId) this.generateRecommendations();
        });
        exportBtn.addEventListener('click', () => this.exportRecommendations());
    }

    setTaskId(taskId: string | null): void {
        this.currentTaskId = taskId;
        const generateBtn = document.getElementById('generate-recommendations-btn') as HTMLButtonElement | null;
        if (taskId) {
            if (generateBtn) generateBtn.disabled = false;
            this.generateRecommendations();
        } else {
            if (generateBtn) generateBtn.disabled = true;
            this.clearRecommendations();
        }
    }

    async generateRecommendations(): Promise<void> {
        if (!this.currentTaskId) return;
        const strategy = (document.getElementById('recommendation-strategy') as HTMLSelectElement).value;
        const count = parseInt((document.getElementById('recommendation-count') as HTMLInputElement).value);
        const statusDiv = document.getElementById('recommendation-status')!;
        try {
            statusDiv.style.display = 'block';
            statusDiv.className = 'status-message';
            statusDiv.textContent = I18n.t('recommendation.generating');
            const response = await this.apiService.post('/sampling-recommendations/generate', {
                task_id: this.currentTaskId,
                strategy: strategy,
                n_recommendations: count
            }) as { recommendations: Recommendation[] };
            this.recommendations = response.recommendations || [];
            this.displayRecommendations();
            this.displayMarkers();
            statusDiv.className = 'status-message success';
            statusDiv.textContent = I18n.t('recommendation.generated', { count: this.recommendations.length });
        } catch (error) {
            console.error('生成采样建议失败:', error);
            statusDiv.className = 'status-message error';
            statusDiv.textContent = `${I18n.t('recommendation.failed')}: ${(error as Error).message || '未知错误'}`;
        }
    }

    private displayRecommendations(): void {
        const container = document.getElementById('recommendations-container')!;
        const list = document.getElementById('recommendations-list')!;
        const countSpan = document.querySelector('.recommendations-count')!;
        if (this.recommendations.length === 0) {
            (container as HTMLElement).style.display = 'none';
            return;
        }
        (container as HTMLElement).style.display = 'block';
        countSpan.textContent = `建议点：${this.recommendations.length}`;
        list.innerHTML = '';
        const sortedRecommendations = [...this.recommendations].sort((a, b) => b.variance - a.variance);
        sortedRecommendations.forEach((rec, index) => {
            const card = this.createRecommendationCard(rec, index);
            list.appendChild(card);
        });
    }

    private createRecommendationCard(rec: Recommendation, index: number): HTMLDivElement {
        const card = document.createElement('div');
        card.className = 'recommendation-card';
        card.dataset.id = String(rec.id);
        card.setAttribute('role', 'listitem');
        card.setAttribute('tabindex', '0');
        card.setAttribute('aria-label', `${I18n.t('recommendation.title')} #${rec.id}, ${I18n.t('recommendation.priority')} ${this.getPriorityText(rec.priority)}, ${I18n.t('recommendation.uncertainty')} ${rec.uncertainty_level}/5`);
        const priorityColor = this.getPriorityColor(rec.priority);
        const priorityText = this.getPriorityText(rec.priority);
        card.innerHTML = `
            <div class="card-header">
                <div class="card-title">
                    <span class="card-number">#${rec.id}</span>
                    <span class="card-priority" style="background-color: ${priorityColor}">
                        ${priorityText}
                    </span>
                </div>
                <div class="card-uncertainty">
                    ${I18n.t('recommendation.uncertainty')}: ${rec.uncertainty_level}/5
                </div>
            </div>
            <div class="card-body">
                <div class="card-info">
                    <span class="info-label">坐标:</span>
                    <span class="info-value">${rec.x.toFixed(6)}, ${rec.y.toFixed(6)}</span>
                </div>
                <div class="card-info">
                    <span class="info-label">方差:</span>
                    <span class="info-value">${rec.variance.toFixed(4)}</span>
                </div>
                <div class="card-info">
                    <span class="info-label">距最近点:</span>
                    <span class="info-value">${rec.distance_to_nearest.toFixed(2)}m</span>
                </div>
                <div class="card-reason">
                    <span class="reason-label">${I18n.t('recommendation.reason')}:</span>
                    <span class="reason-text">${rec.sampling_reason}</span>
                </div>
            </div>
            <div class="card-footer">
                <button class="btn btn-card btn-locate" data-id="${rec.id}">定位</button>
                <button class="btn btn-card btn-select" data-id="${rec.id}">选择此点</button>
            </div>
        `;
        const locateBtn = card.querySelector('.btn-locate')!;
        const selectBtn = card.querySelector('.btn-select')!;
        locateBtn.addEventListener('click', () => this.locateRecommendation(rec));
        selectBtn.addEventListener('click', () => this.selectRecommendation(rec));
        card.addEventListener('mouseenter', () => this.highlightMarker(rec.id, true));
        card.addEventListener('mouseleave', () => this.highlightMarker(rec.id, false));
        card.addEventListener('focus', () => this.highlightMarker(rec.id, true));
        card.addEventListener('blur', () => this.highlightMarker(rec.id, false));
        card.addEventListener('keydown', (e: KeyboardEvent) => {
            if (e.key === 'Enter') {
                this.selectRecommendation(rec);
            }
        });
        return card;
    }

    private getPriorityColor(priority: string): string {
        const colors: Record<string, string> = {
            'high': '#ff3b30',
            'medium': '#ff9500',
            'low': '#34c759'
        };
        return colors[priority] || '#ff9500';
    }

    private getPriorityText(priority: string): string {
        const texts: Record<string, string> = {
            'high': I18n.t('recommendation.priority.high'),
            'medium': I18n.t('recommendation.priority.medium'),
            'low': I18n.t('recommendation.priority.low')
        };
        return texts[priority] || I18n.t('recommendation.priority.medium');
    }

    private _setupViewportListener(): void {
        const view = this.view;
        if (!view) return;
        const onViewChange = (): void => {
            if (this._viewChangeTimer !== null) {
                clearTimeout(this._viewChangeTimer);
            }
            this._viewChangeTimer = setTimeout(() => {
                this._refreshVisibleMarkers();
            }, 200);
        };
        if (view.watch) {
            view.watch('extent', onViewChange);
            view.watch('zoom', onViewChange);
        }
        if (view.on && typeof view.getCenter === 'function') {
            view.on('moveend', onViewChange);
            view.on('zoomend', onViewChange);
        }
    }

    private _getViewportBounds(): Bounds | null {
        const view = this.view;
        if (view.extent) {
            const ext = view.extent;
            return { minLng: ext.xmin, minLat: ext.ymin, maxLng: ext.xmax, maxLat: ext.ymax };
        }
        if (view.getBounds) {
            const bounds = view.getBounds();
            const sw = bounds.getSouthWest();
            const ne = bounds.getNorthEast();
            return { minLng: sw.lng, minLat: sw.lat, maxLng: ne.lng, maxLat: ne.lat };
        }
        return null;
    }

    private _isInViewport(rec: Recommendation, bounds: Bounds | null): boolean {
        if (!bounds) return true;
        return rec.x >= bounds.minLng && rec.x <= bounds.maxLng &&
               rec.y >= bounds.minLat && rec.y <= bounds.maxLat;
    }

    private _refreshVisibleMarkers(): void {
        if (this.recommendations.length === 0) return;
        if (this.recommendations.length <= this.MAX_VISIBLE_MARKERS) {
            this._updateClusterHint(0);
            return;
        }
        const bounds = this._getViewportBounds();
        const inView = this.recommendations.filter(r => this._isInViewport(r, bounds));
        const toShow = inView.slice(0, this.MAX_VISIBLE_MARKERS);
        const hiddenCount = inView.length - toShow.length;
        this.clearMarkers();
        if (this.mapProvider === 'amap') {
            this._showMarkersAMap(toShow);
        } else {
            this._showMarkersArcGIS(toShow);
        }
        this._updateClusterHint(hiddenCount);
    }

    private _updateClusterHint(hiddenCount: number): void {
        if (!this.clusterHint) {
            this.clusterHint = document.createElement('div');
            this.clusterHint.className = 'cluster-hint recommendation-cluster-hint';
            this.clusterHint.setAttribute('role', 'status');
            this.clusterHint.setAttribute('aria-live', 'polite');
            const mapContainer = document.querySelector('.map-container');
            if (mapContainer) mapContainer.appendChild(this.clusterHint);
        }
        if (hiddenCount > 0) {
            this.clusterHint.textContent = `视口内还有 ${hiddenCount} 个建议点未显示，请放大地图查看`;
            this.clusterHint.style.display = 'block';
        } else {
            this.clusterHint.style.display = 'none';
        }
    }

    async displayMarkers(): Promise<void> {
        this.clearMarkers();
        if (this.recommendations.length === 0) return;
        let toShow = this.recommendations;
        let hiddenCount = 0;
        if (this.recommendations.length > this.MAX_VISIBLE_MARKERS) {
            const bounds = this._getViewportBounds();
            const inView = this.recommendations.filter(r => this._isInViewport(r, bounds));
            toShow = inView.slice(0, this.MAX_VISIBLE_MARKERS);
            hiddenCount = inView.length - toShow.length;
        }
        if (this.mapProvider === 'amap') {
            await this._showMarkersAMap(toShow);
        } else {
            await this._showMarkersArcGIS(toShow);
        }
        this._updateClusterHint(hiddenCount);
    }

    private async _showMarkersAMap(recs: Recommendation[]): Promise<void> {
        for (const rec of recs) {
            const priorityColor = this.getPriorityColor(rec.priority);
            let marker: any;
            if (this.markerPool.length > 0) {
                marker = this.markerPool.pop();
                marker.setPosition([rec.x, rec.y]);
                marker.setContent(`<div class="recommendation-marker" style="background-color: ${priorityColor};" data-id="${rec.id}"></div>`);
            } else {
                marker = new (window as any).AMap.Marker({
                    position: [rec.x, rec.y],
                    content: `<div class="recommendation-marker" style="background-color: ${priorityColor};" data-id="${rec.id}"></div>`,
                    offset: new (window as any).AMap.Pixel(-8, -8),
                    zIndex: 100
                });
            }
            this.view.add(marker);
            this.markers.push({ marker, rec });
            marker.on('click', () => {
                this.selectRecommendation(rec);
            });
        }
    }

    private async _showMarkersArcGIS(recs: Recommendation[]): Promise<void> {
        const [Graphic, GraphicsLayer, Point, SimpleMarkerSymbol] = await Promise.all([
            (window as any).esri.require('esri/Graphic'),
            (window as any).esri.require('esri/layers/GraphicsLayer'),
            (window as any).esri.require('esri/geometry/Point'),
            (window as any).esri.require('esri/symbols/SimpleMarkerSymbol')
        ]);
        const markerLayer = new GraphicsLayer({ title: '采样建议' });
        for (const rec of recs) {
            const priorityColor = this.getPriorityColor(rec.priority);
            const point = new Point({ longitude: rec.x, latitude: rec.y });
            const symbol = new SimpleMarkerSymbol({
                color: priorityColor,
                size: 16,
                outline: { color: [255, 255, 255, 1], width: 2 }
            });
            const graphic = new Graphic({ geometry: point, symbol: symbol });
            markerLayer.add(graphic);
            this.markers.push({ marker: graphic, rec });
        }
        this.view.map.add(markerLayer);
        this.markerLayer = markerLayer;
        this.view.on('click', (event: any) => {
            this.view.hitTest(event).then((response: any) => {
                if (response.results.length > 0) {
                    const graphic = response.results[0].graphic;
                    const markerData = this.markers.find(m => m.marker === graphic);
                    if (markerData) {
                        this.selectRecommendation(markerData.rec);
                    }
                }
            });
        });
    }

    clearMarkers(): void {
        if (this.mapProvider === 'amap') {
            this.markers.forEach(({ marker }) => {
                this.view.remove(marker);
                marker.clearEvents?.('click');
                this.markerPool.push(marker);
            });
        } else if (this.markerLayer) {
            this.view.map.remove(this.markerLayer);
            this.markerLayer = null;
        }
        this.markers = [];
    }

    highlightMarker(id: number, highlight: boolean): void {
        const markerData = this.markers.find(m => m.rec.id === id);
        if (!markerData) return;
        if (this.mapProvider === 'amap') {
            const marker = markerData.marker;
            const content = marker.getContent();
            const markerEl = content.querySelector('.recommendation-marker');
            if (markerEl) {
                markerEl.style.transform = highlight ? 'scale(1.5)' : 'scale(1)';
                markerEl.style.zIndex = highlight ? '200' : '100';
            }
        } else {
            const graphic = markerData.marker;
            if (highlight) {
                graphic.symbol.size = 24;
            } else {
                graphic.symbol.size = 16;
            }
        }
    }

    locateRecommendation(rec: Recommendation): void {
        if (this.mapProvider === 'amap') {
            this.view.setCenter([rec.x, rec.y]);
            this.view.setZoom(15);
        } else {
            this.view.goTo({ center: [rec.x, rec.y], zoom: 15 });
        }
    }

    selectRecommendation(rec: Recommendation): void {
        if (this.onRecommendationSelect) {
            this.onRecommendationSelect(rec);
        }
        this.locateRecommendation(rec);
        const cards = document.querySelectorAll('.recommendation-card');
        cards.forEach(card => {
            if (parseInt((card as HTMLElement).dataset.id!) === rec.id) {
                card.classList.add('selected');
            } else {
                card.classList.remove('selected');
            }
        });
    }

    async exportRecommendations(): Promise<void> {
        if (!this.currentTaskId) return;
        try {
            const response = await this.apiService.get(`/sampling-recommendations/export/${this.currentTaskId}`);
            const blob = new Blob([JSON.stringify(response, null, 2)], { type: 'application/geo+json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `sampling_recommendations_${this.currentTaskId}.geojson`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('导出失败:', error);
            alert('导出失败: ' + ((error as Error).message || '未知错误'));
        }
    }

    clearRecommendations(): void {
        this.recommendations = [];
        this.clearMarkers();
        this.markerPool = [];
        this._updateClusterHint(0);
        const container = document.getElementById('recommendations-container');
        if (container) container.style.display = 'none';
        const statusDiv = document.getElementById('recommendation-status');
        if (statusDiv) statusDiv.style.display = 'none';
    }

    destroy(): void {
        if (this._viewChangeTimer !== null) {
            clearTimeout(this._viewChangeTimer);
        }
        this.clearRecommendations();
        if (this.clusterHint) {
            this.clusterHint.remove();
            this.clusterHint = null;
        }
    }
}
