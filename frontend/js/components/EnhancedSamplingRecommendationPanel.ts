/**
 * 增强的采样推荐面板组件
 * 支持影响优化、实时预览、自定义候选点评估和方案对比
 */
import { APIService } from '../services/API封装.js';
import { I18n } from '../utils/I18n.js';
import type { IMapAdapterExtended } from '../../types/app';

/** 候选点 */
interface CandidatePoint {
    x: number;
    y: number;
    value?: number;
}

/** 评估结果 */
interface EvaluationResult {
    candidate_index: number;
    x: number;
    y: number;
    variance_reduction: number;
    variance_reduction_ratio: number;
    local_improvement: number;
    comprehensive_score: number;
    influence_radius: number;
    error?: string;
}

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

/** 预览结果 */
interface PreviewResult {
    task_id: string;
    new_point: { x: number; y: number; value: number };
    variance_reduction_map: any;
    total_variance_reduction: number;
    variance_reduction_ratio: number;
    influence_radius: number;
    improved_regions: any[];
    quantitative_metrics: {
        rmse_improvement: number;
        variance_reduction_percent: number;
        coverage_area: number;
        average_improvement: number;
    };
}

/** 采样方案 */
interface SamplingPlan {
    plan_id: string;
    name: string;
    points: CandidatePoint[];
}

/** 模拟结果 */
interface SimulationResult {
    plan_id: string;
    name: string;
    n_points: number;
    mean_variance: number;
    max_variance: number;
    total_variance_reduction: number;
    rmse_improvement: number;
}

export class EnhancedSamplingRecommendationPanel {
    private mapEngine: IMapAdapterExtended;
    private apiService: APIService;
    private currentTaskId: string | null;
    private currentRecommendations: Recommendation[];
    private currentStrategy: string;
    private isGenerating: boolean;
    private element: HTMLElement | null;

    constructor(mapEngine: IMapAdapterExtended) {
        this.mapEngine = mapEngine;
        this.apiService = new APIService();
        this.currentTaskId = null;
        this.currentRecommendations = [];
        this.currentStrategy = 'impact_optimized';
        this.isGenerating = false;
        this.element = null;
    }

    /**
     * 初始化面板
     */
    public async initialize(taskId: string): Promise<void> {
        this.currentTaskId = taskId;
        this.render();
        this.attachEventListeners();
    }

    /**
     * 渲染面板UI
     */
    private render(): void {
        const existingPanel = document.getElementById('enhanced-sampling-panel');
        if (existingPanel) {
            existingPanel.remove();
        }

        const panel = document.createElement('div');
        panel.id = 'enhanced-sampling-panel';
        panel.className = 'enhanced-sampling-panel';
        panel.innerHTML = `
            <div class="enhanced-sampling-panel-header">
                <h3>${I18n.t('enhancedRecommendation.title')}</h3>
                <button class="close-btn" id="close-enhanced-panel">&times;</button>
            </div>

            <div class="enhanced-sampling-panel-content">
                <!-- 策略选择器 -->
                <div class="strategy-section">
                    <label for="strategy-selector">${I18n.t('enhancedRecommendation.strategy')}</label>
                    <select id="strategy-selector">
                        <option value="impact_optimized">${I18n.t('enhancedRecommendation.strategies.impact')}</option>
                        <option value="variance_based">${I18n.t('enhancedRecommendation.strategies.variance')}</option>
                        <option value="spatial_coverage">${I18n.t('enhancedRecommendation.strategies.coverage')}</option>
                        <option value="hybrid">${I18n.t('enhancedRecommendation.strategies.hybrid')}</option>
                    </select>
                </div>

                <!-- 推荐设置 -->
                <div class="settings-section">
                    <div class="setting-item">
                        <label for="recommendation-count">${I18n.t('enhancedRecommendation.count')}</label>
                        <input type="number" id="recommendation-count" value="20" min="1" max="100">
                    </div>
                    <div class="setting-item">
                        <label for="enable-preview">
                            <input type="checkbox" id="enable-preview" checked>
                            ${I18n.t('enhancedRecommendation.enablePreview')}
                        </label>
                    </div>
                </div>

                <!-- 操作按钮 -->
                <div class="action-buttons">
                    <button id="generate-btn" class="primary-btn">
                        ${I18n.t('enhancedRecommendation.generate')}
                    </button>
                    <button id="evaluate-candidates-btn" class="secondary-btn">
                        ${I18n.t('enhancedRecommendation.evaluate')}
                    </button>
                    <button id="compare-plans-btn" class="secondary-btn">
                        ${I18n.t('enhancedRecommendation.compare')}
                    </button>
                </div>

                <!-- 加载状态 -->
                <div id="loading-indicator" class="loading-indicator hidden">
                    <div class="spinner"></div>
                    <span>${I18n.t('enhancedRecommendation.generating')}</span>
                </div>

                <!-- 推荐列表 -->
                <div id="recommendations-list" class="recommendations-list">
                    <div class="empty-state">
                        ${I18n.t('enhancedRecommendation.empty')}
                    </div>
                </div>

                <!-- 收益摘要 -->
                <div id="benefits-summary" class="benefits-summary hidden">
                    <h4>${I18n.t('enhancedRecommendation.benefits')}</h4>
                    <div class="benefits-grid">
                        <div class="benefit-item">
                            <span class="benefit-label">${I18n.t('enhancedRecommendation.varianceReduction')}</span>
                            <span class="benefit-value" id="total-variance-reduction">0%</span>
                        </div>
                        <div class="benefit-item">
                            <span class="benefit-label">${I18n.t('enhancedRecommendation.rmseImprovement')}</span>
                            <span class="benefit-value" id="rmse-improvement">0%</span>
                        </div>
                        <div class="benefit-item">
                            <span class="benefit-label">${I18n.t('enhancedRecommendation.coverage')}</span>
                            <span class="benefit-value" id="coverage-area">0 km²</span>
                        </div>
                    </div>
                </div>

                <!-- 预览热力图 -->
                <div id="preview-heatmap" class="preview-heatmap hidden">
                    <h4>${I18n.t('enhancedRecommendation.preview')}</h4>
                    <canvas id="preview-canvas"></canvas>
                </div>
            </div>
        `;

        document.body.appendChild(panel);
        this.element = panel;
    }

    /**
     * 附加事件监听器
     */
    private attachEventListeners(): void {
        if (!this.element) return;

        // 关闭按钮
        const closeBtn = this.element.querySelector('#close-enhanced-panel');
        closeBtn?.addEventListener('click', () => this.destroy());

        // 生成按钮
        const generateBtn = this.element.querySelector('#generate-btn');
        generateBtn?.addEventListener('click', () => this.generateRecommendations());

        // 评估候选点按钮
        const evaluateBtn = this.element.querySelector('#evaluate-candidates-btn');
        evaluateBtn?.addEventListener('click', () => this.openCandidateEvaluator());

        // 对比方案按钮
        const compareBtn = this.element.querySelector('#compare-plans-btn');
        compareBtn?.addEventListener('click', () => this.openPlanComparator());

        // 策略选择器
        const strategySelector = this.element.querySelector('#strategy-selector') as HTMLSelectElement;
        strategySelector?.addEventListener('change', (e) => {
            this.currentStrategy = (e.target as HTMLSelectElement).value;
        });
    }

    /**
     * 生成推荐
     */
    public async generateRecommendations(): Promise<void> {
        if (!this.currentTaskId || this.isGenerating) return;

        this.isGenerating = true;
        this.showLoading(true);

        try {
            const countInput = this.element?.querySelector('#recommendation-count') as HTMLInputElement;
            const nRecommendations = parseInt(countInput?.value || '20', 10);

            const response = await this.apiService.post(`/api/sampling-impact/recommend-optimal`, {
                task_id: this.currentTaskId,
                n_recommendations: nRecommendations,
                strategy: this.currentStrategy
            }) as {
                recommendations: Array<{ id: string; x: number; y: number; variance: number; priority: string }>;
                expectedImprovement: number;
                uncertaintyReduction: number;
            };

            this.currentRecommendations = response.recommendations || [];
            this.renderRecommendations();
            this.updateBenefitsSummary();

        } catch (error) {
            console.error('生成推荐失败:', error);
            this.showError(I18n.t('enhancedRecommendation.error'));
        } finally {
            this.isGenerating = false;
            this.showLoading(false);
        }
    }

    /**
     * 渲染推荐列表
     */
    private renderRecommendations(): void {
        const listContainer = this.element?.querySelector('#recommendations-list');
        if (!listContainer) return;

        if (this.currentRecommendations.length === 0) {
            listContainer.innerHTML = `
                <div class="empty-state">
                    ${I18n.t('enhancedRecommendation.empty')}
                </div>
            `;
            return;
        }

        listContainer.innerHTML = this.currentRecommendations.map((rec, index) => `
            <div class="recommendation-item" data-index="${index}">
                <div class="recommendation-header">
                    <span class="recommendation-id">#${rec.id}</span>
                    <span class="recommendation-priority priority-${rec.priority}">${rec.priority}</span>
                </div>
                <div class="recommendation-details">
                    <div class="detail-row">
                        <span class="detail-label">${I18n.t('enhancedRecommendation.coordinates')}:</span>
                        <span class="detail-value">(${rec.x.toFixed(4)}, ${rec.y.toFixed(4)})</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">${I18n.t('enhancedRecommendation.variance')}:</span>
                        <span class="detail-value">${rec.variance.toFixed(6)}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">${I18n.t('enhancedRecommendation.score')}:</span>
                        <span class="detail-value">${(rec.comprehensive_score || 0).toFixed(3)}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">${I18n.t('enhancedRecommendation.reason')}:</span>
                        <span class="detail-value">${rec.sampling_reason}</span>
                    </div>
                </div>
                <div class="recommendation-actions">
                    <button class="preview-btn" data-index="${index}">
                        ${I18n.t('enhancedRecommendation.preview')}
                    </button>
                    <button class="select-btn" data-index="${index}">
                        ${I18n.t('enhancedRecommendation.select')}
                    </button>
                </div>
            </div>
        `).join('');

        // 添加事件监听
        listContainer.querySelectorAll('.preview-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const index = parseInt((e.target as HTMLElement).dataset.index || '0', 10);
                this.previewPointEffect(this.currentRecommendations[index]);
            });
        });

        listContainer.querySelectorAll('.select-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const index = parseInt((e.target as HTMLElement).dataset.index || '0', 10);
                this.selectRecommendation(this.currentRecommendations[index]);
            });
        });
    }

    /**
     * 预览点的影响效果
     */
    public async previewPointEffect(point: Recommendation): Promise<void> {
        if (!this.currentTaskId) return;

        try {
            // 估算点的值（如果没有提供）
            const estimatedValue = point.expected_benefit || 0;

            const response: PreviewResult = await this.apiService.post(`/api/sampling-impact/preview-effect`, {
                task_id: this.currentTaskId,
                new_point: {
                    x: point.x,
                    y: point.y,
                    value: estimatedValue
                }
            });

            this.renderPreviewHeatmap(response);
            this.showPreviewSummary(response);

        } catch (error) {
            console.error('预览失败:', error);
            this.showError(I18n.t('enhancedRecommendation.previewError'));
        }
    }

    /**
     * 渲染预览热力图
     */
    private renderPreviewHeatmap(result: PreviewResult): void {
        const heatmapContainer = this.element?.querySelector('#preview-heatmap');
        const canvas = this.element?.querySelector('#preview-canvas') as HTMLCanvasElement;
        if (!heatmapContainer || !canvas) return;

        heatmapContainer.classList.remove('hidden');

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const mapData = result.variance_reduction_map;
        const width = mapData.normalized[0].length;
        const height = mapData.normalized.length;

        canvas.width = width;
        canvas.height = height;

        const imageData = ctx.createImageData(width, height);
        const data = imageData.data;

        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                const value = mapData.normalized[y][x];
                const idx = (y * width + x) * 4;

                // 使用热力图颜色方案：蓝色 -> 绿色 -> 黄色 -> 红色
                const color = this.getHeatmapColor(value);
                data[idx] = color.r;
                data[idx + 1] = color.g;
                data[idx + 2] = color.b;
                data[idx + 3] = 255;
            }
        }

        ctx.putImageData(imageData, 0, 0);
    }

    /**
     * 获取热力图颜色
     */
    private getHeatmapColor(value: number): { r: number; g: number; b: number } {
        // 简单的热力图颜色映射
        if (value < 0.25) {
            return { r: 0, g: 0, b: Math.floor(value * 4 * 255) };
        } else if (value < 0.5) {
            return { r: 0, g: Math.floor((value - 0.25) * 4 * 255), b: 255 };
        } else if (value < 0.75) {
            return { r: Math.floor((value - 0.5) * 4 * 255), g: 255, b: Math.floor((0.75 - value) * 4 * 255) };
        } else {
            return { r: 255, g: Math.floor((1 - value) * 4 * 255), b: 0 };
        }
    }

    /**
     * 显示预览摘要
     */
    private showPreviewSummary(result: PreviewResult): void {
        const metrics = result.quantitative_metrics;
        const summaryHtml = `
            <div class="preview-summary">
                <div class="summary-item">
                    <span>${I18n.t('enhancedRecommendation.varianceReduction')}:</span>
                    <strong>${metrics.variance_reduction_percent.toFixed(2)}%</strong>
                </div>
                <div class="summary-item">
                    <span>${I18n.t('enhancedRecommendation.rmseImprovement')}:</span>
                    <strong>${metrics.rmse_improvement.toFixed(2)}%</strong>
                </div>
                <div class="summary-item">
                    <span>${I18n.t('enhancedRecommendation.influenceRadius')}:</span>
                    <strong>${result.influence_radius.toFixed(2)}m</strong>
                </div>
                <div class="summary-item">
                    <span>${I18n.t('enhancedRecommendation.improvedRegions')}:</span>
                    <strong>${result.improved_regions.length}</strong>
                </div>
            </div>
        `;

        const existingSummary = this.element?.querySelector('.preview-summary');
        if (existingSummary) {
            existingSummary.remove();
        }

        const heatmapContainer = this.element?.querySelector('#preview-heatmap');
        if (heatmapContainer) {
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = summaryHtml;
            const firstChild = tempDiv.firstElementChild;
            if (firstChild) {
                heatmapContainer.appendChild(firstChild);
            }
        }
    }

    /**
     * 更新收益摘要
     */
    private updateBenefitsSummary(): void {
        const summaryContainer = this.element?.querySelector('#benefits-summary');
        if (!summaryContainer) return;

        summaryContainer.classList.remove('hidden');

        // 计算总体收益
        if (this.currentRecommendations.length > 0) {
            const totalVarianceReduction = this.currentRecommendations.reduce(
                (sum, rec) => sum + (rec.variance_reduction || 0),
                0
            );
            const avgRmseImprovement = this.currentRecommendations.reduce(
                (sum, rec) => sum + (rec.comprehensive_score || 0),
                0
            ) / this.currentRecommendations.length;

            document.getElementById('total-variance-reduction')!.textContent =
                `${(totalVarianceReduction * 100).toFixed(2)}%`;
            document.getElementById('rmse-improvement')!.textContent =
                `${(avgRmseImprovement * 100).toFixed(2)}%`;
            document.getElementById('coverage-area')!.textContent =
                `${(this.currentRecommendations.length * 0.01).toFixed(2)} km²`;
        }
    }

    /**
     * 评估自定义候选点
     */
    public async evaluateCustomCandidates(candidates: CandidatePoint[]): Promise<EvaluationResult[]> {
        if (!this.currentTaskId) return [];

        try {
            const response = await this.apiService.post(`/api/sampling-impact/evaluate-candidates`, {
                task_id: this.currentTaskId,
                candidate_points: candidates,
                strategy: this.currentStrategy
            }) as { results: EvaluationResult[] };

            return response.results || [];

        } catch (error) {
            console.error('评估候选点失败:', error);
            return [];
        }
    }

    /**
     * 对比采样方案
     */
    public async compareSamplingPlans(plans: SamplingPlan[]): Promise<SimulationResult[]> {
        if (!this.currentTaskId || plans.length === 0) return [];

        try {
            const response = await this.apiService.post(`/api/sampling-impact/batch-simulate`, {
                task_id: this.currentTaskId,
                sampling_plans: plans
            }) as { results: SimulationResult[] };

            return response.results || [];

        } catch (error) {
            console.error('对比方案失败:', error);
            return [];
        }
    }

    /**
     * 选择推荐点
     */
    private selectRecommendation(rec: Recommendation): void {
        // 在地图上高亮显示该点（使用 addMarker 添加特殊标记）
        if (this.mapEngine) {
            this.mapEngine.addMarker({
                x: rec.x,
                y: rec.y,
                value: rec.variance
            }).catch(error => {
                console.error('高亮标记失败:', error);
            });
        }

        // 触发选择事件
        const event = new CustomEvent('recommendationSelected', {
            detail: rec
        });
        document.dispatchEvent(event);
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
     * 显示/隐藏加载状态
     */
    private showLoading(show: boolean): void {
        const indicator = this.element?.querySelector('#loading-indicator');
        if (indicator) {
            indicator.classList.toggle('hidden', !show);
        }
    }

    /**
     * 显示错误消息
     */
    private showError(message: string): void {
        alert(message);
    }

    /**
     * 打开候选点评估器
     */
    private openCandidateEvaluator(): void {
        // TODO: 实现候选点评估器对话框
        console.log('打开候选点评估器');
    }

    /**
     * 打开方案对比器
     */
    private openPlanComparator(): void {
        // TODO: 实现方案对比器对话框
        console.log('打开方案对比器');
    }

    /**
     * 销毁面板
     */
    public destroy(): void {
        if (this.element) {
            this.element.remove();
            this.element = null;
        }
        this.currentRecommendations = [];
        this.currentTaskId = null;
    }

    /**
     * 更新UI文本
     */
    public updateUIText(): void {
        // 重新渲染面板以更新文本
        if (this.element) {
            this.render();
            this.attachEventListeners();
            if (this.currentRecommendations.length > 0) {
                this.renderRecommendations();
            }
        }
    }
}