import { APIService } from '../../services/API封装.js';
import type { PanelConfig, PanelField, PanelOperation } from './ConfigurableApiPanel.js';
import { panelConfigs } from './panelConfigs.js';

type FieldElement = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

type ContributionRow = {
    modelId: string;
    value: number;
    reason: string;
};

type FusionVisualState = {
    weights: Record<string, number>;
    contributions: ContributionRow[];
    strategyName: string;
    weightMethod: string;
    strategySummary: string;
    recommendations: string[];
};

export class ModelFusionPanel {
    private readonly apiService: APIService;
    private readonly config: PanelConfig;

    private mfFieldElements: Map<string, FieldElement> = new Map();
    private mfStatusElement: HTMLElement | null = null;
    private mfResultElement: HTMLElement | null = null;
    private weightVizElement: HTMLElement | null = null;
    private contributionVizElement: HTMLElement | null = null;
    private strategyVizElement: HTMLElement | null = null;
    private recommendationElement: HTMLElement | null = null;

    constructor(apiService: APIService) {
        this.apiService = apiService;
        this.config = panelConfigs.modelFusion;
    }

    public mount(container: HTMLElement): void {
        const config = this.config as PanelConfig;
        const root = document.createElement('div');
        root.className = 'integration-module-panel model-fusion-visual-panel';
        root.setAttribute('data-panel-key', config.key);

        root.appendChild(this.renderHeader(config));
        root.appendChild(this.renderForm(config));
        root.appendChild(this.renderActions(config));

        this.mfStatusElement = document.createElement('div');
        this.mfStatusElement.className = 'status-message';
        this.mfStatusElement.textContent = '可执行融合任务后自动生成解释可视化。';

        this.mfResultElement = document.createElement('pre');
        this.mfResultElement.className = 'integration-result';
        this.mfResultElement.textContent = '等待操作...';

        const visualGrid = document.createElement('div');
        visualGrid.className = 'fusion-visual-grid';
        this.weightVizElement = this.createVizCard('融合权重解释可视化');
        this.contributionVizElement = this.createVizCard('子模型贡献度对比');
        this.strategyVizElement = this.createVizCard('融合策略解释');
        this.recommendationElement = this.createVizCard('模型选择建议');

        visualGrid.appendChild(this.weightVizElement);
        visualGrid.appendChild(this.contributionVizElement);
        visualGrid.appendChild(this.strategyVizElement);
        visualGrid.appendChild(this.recommendationElement);

        root.appendChild(this.mfStatusElement);
        root.appendChild(this.mfResultElement);
        root.appendChild(visualGrid);

        container.appendChild(root);
    }

    private renderHeader(config: PanelConfig): HTMLElement {
        const wrapper = document.createElement('div');

        const title = document.createElement('h3');
        title.className = 'integration-module-title';
        title.textContent = config.title;

        const description = document.createElement('p');
        description.className = 'integration-module-description';
        description.textContent = config.description;

        wrapper.appendChild(title);
        wrapper.appendChild(description);
        return wrapper;
    }

    private renderForm(config: PanelConfig): HTMLElement {
        const form = document.createElement('div');
        form.className = 'integration-form-grid';

        config.fields.forEach((field) => {
            const fieldWrapper = document.createElement('div');
            fieldWrapper.className = 'integration-field';

            const label = document.createElement('label');
            label.className = 'integration-field-label';
            label.textContent = field.label;
            label.setAttribute('for', `${config.key}-${field.key}`);

            const input = this.createFieldElement(field);
            input.id = `${config.key}-${field.key}`;
            this.mfFieldElements.set(field.key, input);

            fieldWrapper.appendChild(label);
            fieldWrapper.appendChild(input);
            form.appendChild(fieldWrapper);
        });

        return form;
    }

    private renderActions(config: PanelConfig): HTMLElement {
        const actions = document.createElement('div');
        actions.className = 'integration-actions';

        config.operations.forEach((operation) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn btn-secondary integration-action-btn';
            button.setAttribute('data-operation-id', operation.id);
            button.textContent = operation.label;
            button.addEventListener('click', () => {
                void this.executeOperation(operation);
            });
            actions.appendChild(button);
        });

        return actions;
    }

    private createFieldElement(field: PanelField): FieldElement {
        if (field.type === 'textarea' || field.type === 'json') {
            const textarea = document.createElement('textarea');
            textarea.className = 'input integration-input integration-textarea';
            textarea.rows = field.rows || (field.type === 'json' ? 12 : 4);
            if (field.placeholder) {
                textarea.placeholder = field.placeholder;
            }
            if (typeof field.defaultValue !== 'undefined') {
                if (field.type === 'json' && typeof field.defaultValue !== 'string') {
                    textarea.value = JSON.stringify(field.defaultValue, null, 2);
                } else {
                    textarea.value = String(field.defaultValue);
                }
            }
            return textarea;
        }

        if (field.type === 'select') {
            const select = document.createElement('select');
            select.className = 'select integration-input';
            (field.options || []).forEach((option) => {
                const optionElement = document.createElement('option');
                optionElement.value = option.value;
                optionElement.textContent = option.label;
                select.appendChild(optionElement);
            });
            if (typeof field.defaultValue !== 'undefined') {
                select.value = String(field.defaultValue);
            }
            return select;
        }

        const input = document.createElement('input');
        input.className = 'input integration-input';
        input.type = field.type === 'checkbox' ? 'checkbox' : field.type;

        if (field.type === 'checkbox') {
            input.classList.add('integration-checkbox');
            input.checked = Boolean(field.defaultValue);
        } else {
            if (field.placeholder) {
                input.placeholder = field.placeholder;
            }
            if (typeof field.defaultValue !== 'undefined') {
                input.value = String(field.defaultValue);
            }
        }

        return input;
    }

    private getFieldValue(field: PanelField): unknown {
        const element = this.mfFieldElements.get(field.key);
        if (!element) {
            return undefined;
        }

        if (field.type === 'checkbox') {
            return (element as HTMLInputElement).checked;
        }

        const rawValue = element.value.trim();
        if (!rawValue) {
            return '';
        }

        if (field.type === 'number') {
            const numberValue = Number(rawValue);
            return Number.isNaN(numberValue) ? rawValue : numberValue;
        }

        if (field.type === 'json') {
            try {
                return JSON.parse(rawValue);
            } catch {
                throw new Error(`${field.label} 不是有效 JSON`);
            }
        }

        return rawValue;
    }

    private collectInputValues(config: PanelConfig): Record<string, unknown> {
        const values: Record<string, unknown> = {};
        config.fields.forEach((field) => {
            const value = this.getFieldValue(field);
            if (field.required && (value === '' || typeof value === 'undefined')) {
                throw new Error(`${field.label} 为必填项`);
            }
            values[field.key] = value;
        });
        return values;
    }

    private buildPath(template: string, values: Record<string, unknown>): string {
        return template.replace(/:([A-Za-z0-9_]+)/g, (_, key: string) => {
            const value = values[key];
            if (value === '' || value === null || typeof value === 'undefined') {
                throw new Error(`缺少路径参数: ${key}`);
            }
            return encodeURIComponent(String(value));
        });
    }

    private buildBody(operation: PanelOperation, values: Record<string, unknown>): unknown {
        if (operation.bodyFieldAsRoot) {
            return values[operation.bodyFieldAsRoot];
        }

        if (operation.bodyFromFields && operation.bodyFromFields.length > 0) {
            const body: Record<string, unknown> = {};
            operation.bodyFromFields.forEach((fieldKey) => {
                body[fieldKey] = values[fieldKey];
            });
            return body;
        }

        return undefined;
    }

    private setLoading(loading: boolean): void {
        this.mfResultElement?.parentElement?.querySelectorAll('button.integration-action-btn').forEach((button) => {
            (button as HTMLButtonElement).disabled = loading;
        });
    }

    private setStatus(message: string, type: 'success' | 'error' | 'warning' = 'success'): void {
        if (!this.mfStatusElement) {
            return;
        }
        this.mfStatusElement.className = `status-message ${type}`;
        this.mfStatusElement.textContent = message;
    }

    private setResult(data: unknown): void {
        if (this.mfResultElement) {
            this.mfResultElement.textContent = JSON.stringify(data, null, 2);
        }
    }

    private async executeOperation(operation: PanelOperation): Promise<void> {
        const config = this.config as PanelConfig;
        try {
            this.setLoading(true);
            this.setStatus(`正在执行: ${operation.label}`, 'warning');

            const values = this.collectInputValues(config);
            const path = this.buildPath(operation.path, values);
            const url = `${this.apiService.baseURL}${path}`;
            const options: RequestInit = { method: operation.method };

            if (operation.method !== 'GET') {
                const body = this.buildBody(operation, values);
                if (typeof body !== 'undefined') {
                    options.headers = { 'Content-Type': 'application/json' };
                    options.body = JSON.stringify(body);
                }
            }

            const response = await this.apiService.request<unknown>(url, options);
            this.setResult(response);
            this.updateVisualizations(response);
            this.setStatus(`执行成功: ${operation.label}`, 'success');
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            this.setStatus(`执行失败: ${message}`, 'error');
            this.setResult({ error: message, operation: operation.label });
        } finally {
            this.setLoading(false);
        }
    }

    private createVizCard(title: string): HTMLElement {
        const card = document.createElement('section');
        card.className = 'fusion-viz-card';
        card.innerHTML = `
            <h4>${title}</h4>
            <div class="fusion-viz-body"><p class="fusion-viz-empty">暂无数据</p></div>
        `;
        return card;
    }

    private asRecord(value: unknown): Record<string, unknown> | null {
        if (!value || typeof value !== 'object' || Array.isArray(value)) {
            return null;
        }
        return value as Record<string, unknown>;
    }

    private extractWeights(payload: Record<string, unknown>): Record<string, number> {
        const fromResult = this.asRecord(payload.result);
        const fromAnalysis = this.asRecord(payload.analysis);
        const fromWeightFeatures = this.asRecord(fromAnalysis?.weight_features);
        const fromPrediction = this.asRecord(payload.prediction);
        const directWeights = this.asRecord(payload.weights)
            ?? this.asRecord(fromResult?.weights)
            ?? this.asRecord(fromWeightFeatures?.weights)
            ?? this.asRecord(fromPrediction?.weights);

        const weights: Record<string, number> = {};
        if (!directWeights) {
            return weights;
        }

        Object.entries(directWeights).forEach(([modelId, raw]) => {
            const value = typeof raw === 'number' ? raw : Number(raw);
            if (Number.isFinite(value) && value >= 0) {
                weights[modelId] = value;
            }
        });
        return weights;
    }

    private extractContributions(payload: Record<string, unknown>, weights: Record<string, number>): ContributionRow[] {
        const fromAnalysis = this.asRecord(payload.analysis);
        const modelContributions = Array.isArray(fromAnalysis?.model_contributions)
            ? fromAnalysis?.model_contributions
            : Array.isArray(payload.model_contributions)
                ? payload.model_contributions
                : [];

        const fromLime = this.asRecord(payload.lime);
        const fromShap = this.asRecord(payload.shap);
        const ranked = this.asRecord(fromLime?.submodel_contribution_ranking)
            ?? this.asRecord(fromShap?.submodel_contribution_ranking)
            ?? this.asRecord(payload.submodel_contribution_ranking);
        const rankingRows = Array.isArray(ranked?.ranking) ? ranked.ranking : [];

        const rows: ContributionRow[] = [];
        if (modelContributions.length > 0) {
            modelContributions.forEach((item) => {
                const record = this.asRecord(item);
                if (!record) {
                    return;
                }
                const modelId = String(record.model_id ?? record.model ?? 'unknown');
                const contributionRaw = record.mean_abs_contribution ?? record.marginal_gain ?? record.contribution ?? 0;
                const contribution = Number(contributionRaw);
                if (Number.isFinite(contribution)) {
                    rows.push({
                        modelId,
                        value: contribution,
                        reason: '来自融合特征分析'
                    });
                }
            });
        } else if (rankingRows.length > 0) {
            rankingRows.forEach((item) => {
                const record = this.asRecord(item);
                if (!record) {
                    return;
                }
                const modelId = String(record.model_id ?? record.model ?? 'unknown');
                const contribution = Number(record.contribution_score ?? record.score ?? 0);
                if (Number.isFinite(contribution)) {
                    rows.push({
                        modelId,
                        value: contribution,
                        reason: String(record.reason ?? '来自子模型贡献度排序')
                    });
                }
            });
        } else {
            Object.entries(weights).forEach(([modelId, weight]) => {
                rows.push({
                    modelId,
                    value: weight,
                    reason: '未提供贡献明细，按权重近似'
                });
            });
        }

        return rows.sort((a, b) => b.value - a.value);
    }

    private extractStrategy(payload: Record<string, unknown>): { strategyName: string; weightMethod: string; strategySummary: string } {
        const result = this.asRecord(payload.result);
        const analysis = this.asRecord(payload.analysis);
        const strategyFeatures = this.asRecord(analysis?.strategy_features);
        const monitor = this.asRecord(payload.monitor);

        const strategyName = String(
            result?.fusion_strategy
            ?? payload.strategy
            ?? strategyFeatures?.strategy
            ?? monitor?.selected_strategy
            ?? 'unknown'
        );
        const weightMethod = String(
            result?.weight_method
            ?? payload.weight_method
            ?? (this.asRecord(analysis?.weight_features)?.weight_method)
            ?? 'unknown'
        );

        const complexity = strategyFeatures?.complexity ? `复杂度: ${strategyFeatures.complexity}` : '';
        const fusionLevel = strategyFeatures?.fusion_level ? `融合层级: ${strategyFeatures.fusion_level}` : '';
        const dynamicSupport = typeof strategyFeatures?.supports_dynamic_weight === 'boolean'
            ? `动态权重: ${strategyFeatures.supports_dynamic_weight ? '支持' : '不支持'}`
            : '';
        const parts = [complexity, fusionLevel, dynamicSupport].filter((item) => item.length > 0);

        return {
            strategyName,
            weightMethod,
            strategySummary: parts.length > 0 ? parts.join(' | ') : '暂无策略细节，建议执行 /dl/fusion/feature-analysis 或 /dl/fusion/strategy-analysis。'
        };
    }

    private extractRecommendations(payload: Record<string, unknown>, contributions: ContributionRow[]): string[] {
        const recommendations: string[] = [];
        const fromLime = this.asRecord(payload.lime);
        const fromShap = this.asRecord(payload.shap);
        const selection = this.asRecord(fromLime?.submodel_selection_recommendation)
            ?? this.asRecord(fromShap?.submodel_selection_recommendation)
            ?? this.asRecord(payload.submodel_selection_recommendation);

        const recommendedModels = Array.isArray(selection?.recommended_models) ? selection.recommended_models : [];
        recommendedModels.forEach((item) => {
            const record = this.asRecord(item);
            if (!record) {
                return;
            }
            const modelId = String(record.model_id ?? record.model ?? 'unknown');
            const reason = String(record.reason ?? '贡献稳定且收益高');
            recommendations.push(`优先保留 ${modelId}: ${reason}`);
        });

        const strategyRecommend = this.asRecord(payload.recommendation) ?? payload;
        const candidates = Array.isArray(strategyRecommend.candidates) ? strategyRecommend.candidates : [];
        if (candidates.length > 0) {
            const topCandidate = this.asRecord(candidates[0]);
            if (topCandidate) {
                const strategy = String(topCandidate.strategy ?? strategyRecommend.recommended_strategy ?? 'unknown');
                const score = Number(topCandidate.score ?? topCandidate.value ?? 0);
                recommendations.push(`优先尝试策略 ${strategy} (评分 ${score.toFixed(3)})`);
            }
        } else if (typeof strategyRecommend.recommended_strategy === 'string') {
            recommendations.push(`推荐策略: ${strategyRecommend.recommended_strategy}`);
        }

        if (recommendations.length === 0 && contributions.length > 0) {
            const top = contributions[0];
            recommendations.push(`当前贡献最高子模型为 ${top.modelId}，建议保持其主导权重。`);
            if (contributions.length > 1) {
                const tail = contributions[contributions.length - 1];
                recommendations.push(`贡献最低子模型 ${tail.modelId} 可考虑降权或替换。`);
            }
        }

        if (recommendations.length === 0) {
            recommendations.push('暂无可用建议，请先执行融合任务并获取结果。');
        }

        return recommendations.slice(0, 5);
    }

    private normalizeState(raw: unknown): FusionVisualState | null {
        const payload = this.asRecord(raw);
        if (!payload) {
            return null;
        }

        const weights = this.extractWeights(payload);
        const contributions = this.extractContributions(payload, weights);
        const strategy = this.extractStrategy(payload);
        const recommendations = this.extractRecommendations(payload, contributions);

        return {
            weights,
            contributions,
            strategyName: strategy.strategyName,
            weightMethod: strategy.weightMethod,
            strategySummary: strategy.strategySummary,
            recommendations
        };
    }

    private updateVisualizations(raw: unknown): void {
        const state = this.normalizeState(raw);
        if (!state) {
            return;
        }
        this.renderWeightVisualization(state.weights);
        this.renderContributionVisualization(state.contributions);
        this.renderStrategyVisualization(state);
        this.renderRecommendationVisualization(state.recommendations);
    }

    private renderWeightVisualization(weights: Record<string, number>): void {
        if (!this.weightVizElement) {
            return;
        }
        const body = this.weightVizElement.querySelector('.fusion-viz-body') as HTMLElement | null;
        if (!body) {
            return;
        }

        const rows = Object.entries(weights).sort((a, b) => b[1] - a[1]);
        if (rows.length === 0) {
            body.innerHTML = '<p class="fusion-viz-empty">未检测到权重字段。</p>';
            return;
        }

        body.innerHTML = rows.map(([modelId, value]) => {
            const ratio = Math.max(0, Math.min(1, value));
            const percent = `${(ratio * 100).toFixed(1)}%`;
            return `
                <div class="fusion-weight-row">
                    <div class="fusion-row-label"><strong>${modelId}</strong><span>${percent}</span></div>
                    <div class="fusion-weight-track"><div class="fusion-weight-fill" style="width:${ratio * 100}%"></div></div>
                </div>
            `;
        }).join('');
    }

    private renderContributionVisualization(contributions: ContributionRow[]): void {
        if (!this.contributionVizElement) {
            return;
        }
        const body = this.contributionVizElement.querySelector('.fusion-viz-body') as HTMLElement | null;
        if (!body) {
            return;
        }

        if (contributions.length === 0) {
            body.innerHTML = '<p class="fusion-viz-empty">暂无贡献度数据。</p>';
            return;
        }

        const maxValue = Math.max(...contributions.map((item) => item.value), 1e-6);
        body.innerHTML = contributions.map((row) => {
            const ratio = Math.max(0, row.value / maxValue);
            return `
                <div class="fusion-weight-row">
                    <div class="fusion-row-label"><strong>${row.modelId}</strong><span>${row.value.toFixed(4)}</span></div>
                    <div class="fusion-weight-track"><div class="fusion-contribution-fill" style="width:${ratio * 100}%"></div></div>
                    <p class="fusion-row-reason">${row.reason}</p>
                </div>
            `;
        }).join('');
    }

    private renderStrategyVisualization(state: FusionVisualState): void {
        if (!this.strategyVizElement) {
            return;
        }
        const body = this.strategyVizElement.querySelector('.fusion-viz-body') as HTMLElement | null;
        if (!body) {
            return;
        }

        body.innerHTML = `
            <div class="fusion-strategy-meta">
                <span class="fusion-tag">策略: ${state.strategyName}</span>
                <span class="fusion-tag">权重方法: ${state.weightMethod}</span>
            </div>
            <p class="fusion-strategy-summary">${state.strategySummary}</p>
        `;
    }

    private renderRecommendationVisualization(recommendations: string[]): void {
        if (!this.recommendationElement) {
            return;
        }
        const body = this.recommendationElement.querySelector('.fusion-viz-body') as HTMLElement | null;
        if (!body) {
            return;
        }

        body.innerHTML = `
            <ol class="fusion-recommend-list">
                ${recommendations.map((item) => `<li>${item}</li>`).join('')}
            </ol>
        `;
    }
}
