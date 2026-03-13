/**
 * 采样建议面板组件
 * 在右侧显示建议的待采样点，按不确定性排序
 */
import { APIService } from '../services/API封装.js';
import { MapConfig } from '../config/map.config.js';

export class SamplingRecommendationPanel {
    /**
     * @param {Object} view - MapView（支持 ArcGIS 和高德地图）
     * @param {Object} layerManager - 图层管理器
     * @param {Function} onRecommendationSelect - 选中建议点回调
     */
    constructor(view, layerManager, onRecommendationSelect) {
        this.view = view;
        this.layerManager = layerManager;
        this.onRecommendationSelect = onRecommendationSelect;
        this.apiService = new APIService();
        this.currentTaskId = null;
        this.recommendations = [];
        this.markers = [];
        this.mapProvider = MapConfig.getProvider();
    }

    /**
     * 创建建议面板
     * @returns {HTMLElement}
     */
    createPanel() {
        const container = document.createElement('div');
        container.className = 'sampling-recommendation-panel';
        container.id = 'sampling-recommendation-panel';

        container.innerHTML = `
            <div class="panel-header">
                <h3 class="section-title">采样建议</h3>
                <p class="section-description">基于不确定性分析的智能采样点推荐</p>
            </div>

            <div class="controls-section">
                <div class="form-group">
                    <label>采样策略</label>
                    <select id="recommendation-strategy" class="select">
                        <option value="hybrid">混合策略（推荐）</option>
                        <option value="variance_based">基于方差优先</option>
                        <option value="spatial_coverage">基于空间覆盖</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>建议点数量</label>
                    <input type="number" id="recommendation-count" class="input" value="20" min="5" max="50">
                </div>

                <button id="generate-recommendations-btn" class="btn btn-primary" disabled>
                    生成建议
                </button>

                <div id="recommendation-status" class="status-message" style="display: none;"></div>
            </div>

            <div id="recommendations-container" style="display: none;">
                <div class="recommendations-header">
                    <span class="recommendations-count">建议点：0</span>
                    <button id="export-recommendations-btn" class="btn btn-export">导出 GeoJSON</button>
                </div>

                <div id="recommendations-list" class="recommendations-list">
                    <!-- 建议点卡片将动态插入这里 -->
                </div>
            </div>
        `;

        // 绑定事件
        this.bindEvents(container);

        return container;
    }

    /**
     * 绑定事件
     * @param {HTMLElement} container
     */
    bindEvents(container) {
        const generateBtn = container.querySelector('#generate-recommendations-btn');
        const strategySelect = container.querySelector('#recommendation-strategy');
        const countInput = container.querySelector('#recommendation-count');
        const exportBtn = container.querySelector('#export-recommendations-btn');

        // 生成建议按钮
        generateBtn.addEventListener('click', () => this.generateRecommendations());

        // 策略和数量变化时自动重新生成
        strategySelect.addEventListener('change', () => {
            if (this.currentTaskId) {
                this.generateRecommendations();
            }
        });

        countInput.addEventListener('change', () => {
            if (this.currentTaskId) {
                this.generateRecommendations();
            }
        });

        // 导出按钮
        exportBtn.addEventListener('click', () => this.exportRecommendations());
    }

    /**
     * 设置当前任务ID
     * @param {string} taskId
     */
    setTaskId(taskId) {
        this.currentTaskId = taskId;
        const generateBtn = document.getElementById('generate-recommendations-btn');

        if (taskId) {
            generateBtn.disabled = false;
            // 自动生成建议
            this.generateRecommendations();
        } else {
            generateBtn.disabled = true;
            this.clearRecommendations();
        }
    }

    /**
     * 生成采样建议
     */
    async generateRecommendations() {
        if (!this.currentTaskId) {
            return;
        }

        const strategy = document.getElementById('recommendation-strategy').value;
        const count = parseInt(document.getElementById('recommendation-count').value);
        const statusDiv = document.getElementById('recommendation-status');

        try {
            statusDiv.style.display = 'block';
            statusDiv.className = 'status-message';
            statusDiv.textContent = '正在生成采样建议...';

            // 调用API
            const response = await this.apiService.post('/sampling-recommendations/generate', {
                task_id: this.currentTaskId,
                strategy: strategy,
                n_recommendations: count
            });

            this.recommendations = response.recommendations || [];

            // 显示建议
            this.displayRecommendations();

            // 在地图上显示标记
            this.displayMarkers();

            statusDiv.className = 'status-message success';
            statusDiv.textContent = `成功生成 ${this.recommendations.length} 个采样建议`;

        } catch (error) {
            console.error('生成采样建议失败:', error);
            statusDiv.className = 'status-message error';
            statusDiv.textContent = `生成失败: ${error.message || '未知错误'}`;
        }
    }

    /**
     * 显示建议列表
     */
    displayRecommendations() {
        const container = document.getElementById('recommendations-container');
        const list = document.getElementById('recommendations-list');
        const countSpan = document.querySelector('.recommendations-count');

        if (this.recommendations.length === 0) {
            container.style.display = 'none';
            return;
        }

        container.style.display = 'block';
        countSpan.textContent = `建议点：${this.recommendations.length}`;

        // 清空列表
        list.innerHTML = '';

        // 按不确定性排序（方差从高到低）
        const sortedRecommendations = [...this.recommendations].sort((a, b) => b.variance - a.variance);

        // 创建卡片
        sortedRecommendations.forEach((rec, index) => {
            const card = this.createRecommendationCard(rec, index);
            list.appendChild(card);
        });
    }

    /**
     * 创建建议点卡片
     * @param {Object} rec - 建议点数据
     * @param {number} index - 索引
     * @returns {HTMLElement}
     */
    createRecommendationCard(rec, index) {
        const card = document.createElement('div');
        card.className = 'recommendation-card';
        card.dataset.id = rec.id;

        // 优先级颜色
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
                    不确定性等级：${rec.uncertainty_level}/5
                </div>
            </div>

            <div class="card-body">
                <div class="card-info">
                    <span class="info-label">坐标：</span>
                    <span class="info-value">${rec.x.toFixed(6)}, ${rec.y.toFixed(6)}</span>
                </div>

                <div class="card-info">
                    <span class="info-label">方差：</span>
                    <span class="info-value">${rec.variance.toFixed(4)}</span>
                </div>

                <div class="card-info">
                    <span class="info-label">距最近点：</span>
                    <span class="info-value">${rec.distance_to_nearest.toFixed(2)}m</span>
                </div>

                <div class="card-reason">
                    <span class="reason-label">采样理由：</span>
                    <span class="reason-text">${rec.sampling_reason}</span>
                </div>
            </div>

            <div class="card-footer">
                <button class="btn btn-card btn-locate" data-id="${rec.id}">
                    定位
                </button>
                <button class="btn btn-card btn-select" data-id="${rec.id}">
                    选择此点
                </button>
            </div>
        `;

        // 绑定事件
        const locateBtn = card.querySelector('.btn-locate');
        const selectBtn = card.querySelector('.btn-select');

        locateBtn.addEventListener('click', () => this.locateRecommendation(rec));
        selectBtn.addEventListener('click', () => this.selectRecommendation(rec));

        // 卡片悬停高亮地图标记
        card.addEventListener('mouseenter', () => this.highlightMarker(rec.id, true));
        card.addEventListener('mouseleave', () => this.highlightMarker(rec.id, false));

        return card;
    }

    /**
     * 获取优先级颜色
     * @param {string} priority
     * @returns {string}
     */
    getPriorityColor(priority) {
        const colors = {
            'high': '#ff3b30',
            'medium': '#ff9500',
            'low': '#34c759'
        };
        return colors[priority] || '#ff9500';
    }

    /**
     * 获取优先级文本
     * @param {string} priority
     * @returns {string}
     */
    getPriorityText(priority) {
        const texts = {
            'high': '高',
            'medium': '中',
            'low': '低'
        };
        return texts[priority] || '中';
    }

    /**
     * 在地图上显示标记
     */
    async displayMarkers() {
        // 清除旧标记
        this.clearMarkers();

        if (this.recommendations.length === 0) {
            return;
        }

        if (this.mapProvider === 'amap') {
            await this.displayMarkersAMap();
        } else {
            await this.displayMarkersArcGIS();
        }
    }

    /**
     * 高德地图显示标记
     */
    async displayMarkersAMap() {
        for (const rec of this.recommendations) {
            const priorityColor = this.getPriorityColor(rec.priority);

            const marker = new AMap.Marker({
                position: [rec.x, rec.y],
                content: `<div class="recommendation-marker" style="background-color: ${priorityColor};" data-id="${rec.id}"></div>`,
                offset: new AMap.Pixel(-8, -8),
                zIndex: 100
            });

            this.view.add(marker);
            this.markers.push({ marker, rec });

            // 点击标记
            marker.on('click', () => {
                this.selectRecommendation(rec);
            });
        }
    }

    /**
     * ArcGIS 显示标记
     */
    async displayMarkersArcGIS() {
        const [Graphic, GraphicsLayer, Point, SimpleMarkerSymbol] = await Promise.all([
            window.esri.require('esri/Graphic'),
            window.esri.require('esri/layers/GraphicsLayer'),
            window.esri.require('esri/geometry/Point'),
            window.esri.require('esri/symbols/SimpleMarkerSymbol')
        ]);

        // 创建图层
        const markerLayer = new GraphicsLayer({
            title: '采样建议'
        });

        for (const rec of this.recommendations) {
            const priorityColor = this.getPriorityColor(rec.priority);

            const point = new Point({
                longitude: rec.x,
                latitude: rec.y
            });

            const symbol = new SimpleMarkerSymbol({
                color: priorityColor,
                size: 16,
                outline: {
                    color: [255, 255, 255, 1],
                    width: 2
                }
            });

            const graphic = new Graphic({
                geometry: point,
                symbol: symbol
            });

            markerLayer.add(graphic);
            this.markers.push({ marker: graphic, rec });
        }

        this.view.map.add(markerLayer);
        this.markerLayer = markerLayer;

        // 点击标记
        this.view.on('click', (event) => {
            this.view.hitTest(event).then((response) => {
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

    /**
     * 清除标记
     */
    clearMarkers() {
        if (this.mapProvider === 'amap') {
            this.markers.forEach(({ marker }) => {
                this.view.remove(marker);
            });
        } else if (this.markerLayer) {
            this.view.map.remove(this.markerLayer);
            this.markerLayer = null;
        }

        this.markers = [];
    }

    /**
     * 高亮标记
     * @param {number} id
     * @param {boolean} highlight
     */
    highlightMarker(id, highlight) {
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
            // ArcGIS 实现
            const graphic = markerData.marker;
            if (highlight) {
                graphic.symbol.size = 24;
            } else {
                graphic.symbol.size = 16;
            }
        }
    }

    /**
     * 定位到建议点
     * @param {Object} rec
     */
    locateRecommendation(rec) {
        if (this.mapProvider === 'amap') {
            this.view.setCenter([rec.x, rec.y]);
            this.view.setZoom(15);
        } else {
            this.view.goTo({
                center: [rec.x, rec.y],
                zoom: 15
            });
        }
    }

    /**
     * 选择建议点
     * @param {Object} rec
     */
    selectRecommendation(rec) {
        // 触发回调
        if (this.onRecommendationSelect) {
            this.onRecommendationSelect(rec);
        }

        // 定位到该点
        this.locateRecommendation(rec);

        // 显示选中状态
        const cards = document.querySelectorAll('.recommendation-card');
        cards.forEach(card => {
            if (parseInt(card.dataset.id) === rec.id) {
                card.classList.add('selected');
            } else {
                card.classList.remove('selected');
            }
        });
    }

    /**
     * 导出建议点
     */
    async exportRecommendations() {
        if (!this.currentTaskId) {
            return;
        }

        try {
            const response = await this.apiService.get(`/sampling-recommendations/export/${this.currentTaskId}`);

            // 下载GeoJSON文件
            const blob = new Blob([JSON.stringify(response, null, 2)], { type: 'application/geo+json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `sampling_recommendations_${this.currentTaskId}.geojson`;
            a.click();
            URL.revokeObjectURL(url);

        } catch (error) {
            console.error('导出失败:', error);
            alert('导出失败: ' + (error.message || '未知错误'));
        }
    }

    /**
     * 清空建议
     */
    clearRecommendations() {
        this.recommendations = [];
        this.clearMarkers();

        const container = document.getElementById('recommendations-container');
        if (container) {
            container.style.display = 'none';
        }

        const statusDiv = document.getElementById('recommendation-status');
        if (statusDiv) {
            statusDiv.style.display = 'none';
        }
    }

    /**
     * 销毁组件
     */
    destroy() {
        this.clearRecommendations();
    }
}