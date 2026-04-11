import type { IAPIService } from '../../types/api';

/**
 * 强化学习采样优化子面板
 */
export class SamplingRLPanel {
    private container: HTMLElement;
    private apiService: IAPIService;
    private lastResult: unknown = null;
    private lastUncertaintyMap: number[][] = [];
    private lastExistingPoints: Array<[number, number]> = [];

    constructor(container: HTMLElement, apiService: IAPIService) {
        this.container = container;
        this.apiService = apiService;
        this.render();
        this.bindEvents();
    }

    private render(): void {
        this.container.innerHTML = `
            <div class="dl-module-card">
                <div class="dl-module-header">
                    <h4>强化学习采样优化</h4>
                    <p>根据不确定性分布推荐高价值采样点</p>
                </div>

                <div class="dl-form-grid">
                    <label class="dl-field">
                        <span>模型类型</span>
                        <select id="dl-rl-model" class="select">
                            <option value="ppo">PPO</option>
                            <option value="dqn">DQN</option>
                            <option value="a2c">A2C</option>
                            <option value="a3c">A3C</option>
                        </select>
                    </label>
                    <label class="dl-field">
                        <span>训练轮数</span>
                        <input id="dl-rl-episodes" class="input" type="number" min="5" max="500" value="30">
                    </label>
                    <label class="dl-field">
                        <span>采样预算</span>
                        <input id="dl-rl-budget" class="input" type="number" min="8" max="200" value="20">
                    </label>
                    <label class="dl-field">
                        <span>推荐点数量</span>
                        <input id="dl-rl-count" class="input" type="number" min="1" max="100" value="10">
                    </label>
                    <label class="dl-field">
                        <span>融合策略</span>
                        <select id="dl-rl-strategy" class="select">
                            <option value="hybrid">Hybrid</option>
                            <option value="rl_only">RL Only</option>
                            <option value="rule_only">Rule Only</option>
                        </select>
                    </label>
                </div>

                <label class="dl-field dl-field-full">
                    <span>不确定性矩阵 uncertainty_map（JSON）</span>
                    <textarea id="dl-rl-map" class="dl-textarea" rows="5">[[0.2,0.4,0.8],[0.3,0.9,0.6],[0.1,0.5,0.7]]</textarea>
                </label>

                <label class="dl-field dl-field-full">
                    <span>已有采样点 existing_points（JSON）</span>
                    <textarea id="dl-rl-points" class="dl-textarea" rows="3">[[0,0],[1,1]]</textarea>
                </label>

                <div class="dl-actions">
                    <button id="dl-rl-train" class="btn btn-primary">训练策略</button>
                    <button id="dl-rl-recommend" class="btn btn-secondary">生成推荐</button>
                    <button id="dl-rl-export" class="btn btn-export">导出结果</button>
                </div>

                <div id="dl-rl-status" class="status-message"></div>
                <pre id="dl-rl-result" class="dl-result">暂无结果</pre>

                <section class="dl-rl-visualizations">
                    <h5>策略可视化分析</h5>
                    <div class="dl-rl-viz-grid">
                        <article class="dl-rl-viz-card">
                            <h6>策略分布图</h6>
                            <div id="dl-rl-policy-distribution" class="dl-rl-viz-body">
                                <div class="status-message">暂无可视化数据</div>
                            </div>
                        </article>

                        <article class="dl-rl-viz-card">
                            <h6>动作价值热图</h6>
                            <div id="dl-rl-action-value-heatmap" class="dl-rl-viz-body">
                                <div class="status-message">暂无可视化数据</div>
                            </div>
                        </article>

                        <article class="dl-rl-viz-card">
                            <h6>奖励分解图</h6>
                            <div id="dl-rl-reward-breakdown" class="dl-rl-viz-body">
                                <div class="status-message">暂无可视化数据</div>
                            </div>
                        </article>

                        <article class="dl-rl-viz-card">
                            <h6>状态-动作轨迹图</h6>
                            <div id="dl-rl-state-action-trajectory" class="dl-rl-viz-body">
                                <div class="status-message">暂无可视化数据</div>
                            </div>
                        </article>
                    </div>
                </section>
            </div>
        `;
    }

    private bindEvents(): void {
        this.container.querySelector('#dl-rl-train')?.addEventListener('click', () => {
            void this.handleTrain();
        });

        this.container.querySelector('#dl-rl-recommend')?.addEventListener('click', () => {
            void this.handleRecommend();
        });

        this.container.querySelector('#dl-rl-export')?.addEventListener('click', () => {
            this.exportResult();
        });
    }

    private parseJson<T>(inputId: string, fieldName: string): T {
        const input = this.container.querySelector(`#${inputId}`) as HTMLTextAreaElement | null;
        if (!input) {
            throw new Error(`缺少输入项: ${fieldName}`);
        }

        try {
            return JSON.parse(input.value) as T;
        } catch {
            throw new Error(`${fieldName} 不是合法 JSON`);
        }
    }

    private setStatus(message: string, type: 'success' | 'warning' | 'error' | 'loading' = 'success'): void {
        const status = this.container.querySelector('#dl-rl-status') as HTMLElement | null;
        if (!status) {
            return;
        }
        status.className = 'status-message';
        if (type !== 'loading') {
            status.classList.add(type);
        }
        status.textContent = message;
    }

    private setResult(data: unknown): void {
        const result = this.container.querySelector('#dl-rl-result') as HTMLElement | null;
        if (!result) {
            return;
        }
        result.textContent = JSON.stringify(data, null, 2);
    }

    private getModelName(): 'ppo' | 'dqn' | 'a2c' | 'a3c' {
        const model = (this.container.querySelector('#dl-rl-model') as HTMLSelectElement | null)?.value || 'ppo';
        if (model === 'dqn' || model === 'a2c' || model === 'a3c') {
            return model;
        }
        return 'ppo';
    }

    private async handleTrain(): Promise<void> {
        try {
            this.setStatus('正在训练强化学习采样模型...', 'loading');
            const modelName = this.getModelName();
            const episodes = Number((this.container.querySelector('#dl-rl-episodes') as HTMLInputElement | null)?.value || 30);
            const budget = Number((this.container.querySelector('#dl-rl-budget') as HTMLInputElement | null)?.value || 20);
            const uncertaintyMap = this.parseJson<number[][]>('dl-rl-map', 'uncertainty_map');
            const existingPoints = this.parseJson<Array<[number, number]>>('dl-rl-points', 'existing_points');
            this.lastUncertaintyMap = uncertaintyMap;
            this.lastExistingPoints = existingPoints;

            const response = await this.apiService.trainSamplingRL({
                model_name: modelName,
                uncertainty_map: uncertaintyMap,
                existing_points: existingPoints,
                episodes,
                budget
            });

            this.lastResult = response;
            this.setResult(response);
            this.renderVisualizations(response);
            this.setStatus('强化学习采样模型训练完成', 'success');
        } catch (error) {
            this.setStatus(`训练失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private async handleRecommend(): Promise<void> {
        try {
            this.setStatus('正在生成采样推荐...', 'loading');
            const modelName = this.getModelName();
            const recommendCount = Number((this.container.querySelector('#dl-rl-count') as HTMLInputElement | null)?.value || 10);
            const fusionStrategy = (this.container.querySelector('#dl-rl-strategy') as HTMLSelectElement | null)?.value || 'hybrid';
            const uncertaintyMap = this.parseJson<number[][]>('dl-rl-map', 'uncertainty_map');
            const existingPoints = this.parseJson<Array<[number, number]>>('dl-rl-points', 'existing_points');
            this.lastUncertaintyMap = uncertaintyMap;
            this.lastExistingPoints = existingPoints;

            const response = await this.apiService.recommendSamplingRL({
                model_name: modelName,
                uncertainty_map: uncertaintyMap,
                existing_points: existingPoints,
                n_recommendations: recommendCount,
                fusion_strategy: fusionStrategy as 'rl_only' | 'rule_only' | 'hybrid',
                realtime: true
            });

            this.lastResult = response;
            this.setResult(response);
            this.renderVisualizations(response);
            this.setStatus('采样推荐生成完成', 'success');
        } catch (error) {
            this.setStatus(`推荐失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private renderVisualizations(data: unknown): void {
        const payload = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
        this.renderPolicyDistribution(payload);
        this.renderActionValueHeatmap(payload);
        this.renderRewardBreakdown(payload);
        this.renderStateActionTrajectory(payload);
    }

    private renderPolicyDistribution(payload: Record<string, unknown>): void {
        const container = this.container.querySelector('#dl-rl-policy-distribution') as HTMLElement | null;
        if (!container) {
            return;
        }
        const explanations = this.getRecord(payload.explanations);
        const policyDecision = this.getRecord(explanations.policy_decision);
        const sourceContribution = Array.isArray(policyDecision.source_contribution)
            ? policyDecision.source_contribution as Array<Record<string, unknown>>
            : [];
        const fromSourceContribution = sourceContribution
            .map((item) => {
                const source = String(item.source || 'unknown');
                const ratioRaw = Number(item.ratio);
                const count = Number(item.count || 0);
                const ratio = Number.isFinite(ratioRaw) ? ratioRaw : 0;
                return {
                    label: source === 'rl' ? 'RL策略' : source === 'rule_based' ? '规则策略' : source,
                    ratio: Math.max(0, ratio),
                    count: Math.max(0, count)
                };
            })
            .filter((item) => item.ratio > 0 || item.count > 0);

        const recommendations = Array.isArray(payload.recommendations) ? payload.recommendations as Array<Record<string, unknown>> : [];
        const fromRecommendations = this.aggregateRecommendationSources(recommendations);
        const distribution = fromSourceContribution.length ? fromSourceContribution : fromRecommendations;

        if (!distribution.length) {
            container.innerHTML = '<div class="status-message">暂无策略分布数据</div>';
            return;
        }
        const totalByCount = distribution.reduce((acc, item) => acc + item.count, 0);
        const normalized = distribution.map((item) => {
            if (item.ratio > 0) {
                return item;
            }
            const ratio = totalByCount > 0 ? item.count / totalByCount : 0;
            return { ...item, ratio };
        });
        container.innerHTML = `
            <div class="dl-rl-distribution-list">
                ${normalized.map((item) => {
                    const pct = Math.round(item.ratio * 100);
                    return `
                        <div class="dl-rl-distribution-item">
                            <div class="dl-rl-distribution-head">
                                <span>${this.escapeHtml(item.label)}</span>
                                <span>${pct}% (${item.count})</span>
                            </div>
                            <div class="dl-rl-distribution-track">
                                <div class="dl-rl-distribution-fill" style="width:${Math.max(1, pct)}%"></div>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    private aggregateRecommendationSources(recommendations: Array<Record<string, unknown>>): Array<{ label: string; ratio: number; count: number }> {
        if (!recommendations.length) {
            return [];
        }
        const bucket = new Map<string, number>();
        recommendations.forEach((item) => {
            const source = String(item.source || 'unknown');
            const count = bucket.get(source) || 0;
            bucket.set(source, count + 1);
        });
        const total = recommendations.length;
        return Array.from(bucket.entries()).map(([source, count]) => ({
            label: source === 'rl' ? 'RL策略' : source === 'rule_based' ? '规则策略' : source,
            count,
            ratio: count / Math.max(1, total)
        }));
    }

    private renderActionValueHeatmap(payload: Record<string, unknown>): void {
        const container = this.container.querySelector('#dl-rl-action-value-heatmap') as HTMLElement | null;
        if (!container) {
            return;
        }
        const explanations = this.getRecord(payload.explanations);
        const actionValueVis = this.getRecord(explanations.action_value_visualization);
        const rawHeatmap = Array.isArray(actionValueVis.value_heatmap) ? actionValueVis.value_heatmap : [];
        const heatmap = this.normalizeHeatmap(rawHeatmap);

        if (!heatmap.length) {
            container.innerHTML = '<div class="status-message">暂无动作价值热图数据</div>';
            return;
        }
        const flat = heatmap.flat();
        const min = Math.min(...flat);
        const max = Math.max(...flat);
        const span = Math.max(1e-8, max - min);
        container.innerHTML = `
            <div class="dl-rl-heatmap-grid" style="grid-template-columns: repeat(${Math.max(1, heatmap[0].length)}, minmax(18px, 1fr));">
                ${heatmap.map((row, r) => row.map((value, c) => {
                    const normalized = (value - min) / span;
                    const alpha = Math.max(0.08, Math.min(0.95, 0.15 + normalized * 0.8));
                    return `
                        <button
                            class="dl-rl-heatmap-cell"
                            type="button"
                            title="动作(${r},${c}) 值=${value.toFixed(4)}"
                            style="background: rgba(14, 165, 233, ${alpha});"
                        >${value.toFixed(2)}</button>
                    `;
                }).join('')).join('')}
            </div>
            <div class="dl-rl-viz-footnote">最小值 ${min.toFixed(4)} · 最大值 ${max.toFixed(4)}</div>
        `;
    }

    private normalizeHeatmap(raw: unknown[]): number[][] {
        const rows: number[][] = [];
        raw.forEach((row) => {
            if (!Array.isArray(row)) {
                return;
            }
            const parsed = row
                .map((cell) => Number(cell))
                .filter((cell) => Number.isFinite(cell));
            if (parsed.length > 0) {
                rows.push(parsed);
            }
        });
        if (!rows.length) {
            return [];
        }
        const maxCols = Math.max(...rows.map((row) => row.length));
        return rows.map((row) => {
            if (row.length === maxCols) {
                return row;
            }
            const filled = [...row];
            while (filled.length < maxCols) {
                filled.push(0);
            }
            return filled;
        });
    }

    private renderRewardBreakdown(payload: Record<string, unknown>): void {
        const container = this.container.querySelector('#dl-rl-reward-breakdown') as HTMLElement | null;
        if (!container) {
            return;
        }
        const explanations = this.getRecord(payload.explanations);
        const effectSummary = this.getRecord(this.getRecord(explanations.sampling_effect_evaluation).summary);
        const pointSummary = this.getRecord(this.getRecord(explanations.sampling_point_recommendation).summary);
        const densitySummary = this.getRecord(this.getRecord(explanations.sampling_density_analysis).summary);

        const uncertaintyGain = Number(effectSummary.uncertainty_reduction_ratio ?? pointSummary.mean_uncertainty_at_points ?? 0);
        const infoGain = Number(effectSummary.expected_information_gain ?? pointSummary.mean_novelty_score ?? 0);
        const coverageGain = Number(densitySummary.coverage_ratio ?? 0);
        const costPenalty = Number(effectSummary.sampling_efficiency ?? 0) > 0
            ? -Math.min(1, 1 / Math.max(1e-6, Number(effectSummary.sampling_efficiency)))
            : -0.15;

        const rows = [
            { label: '不确定性收益', value: uncertaintyGain },
            { label: '信息增益', value: infoGain },
            { label: '覆盖收益', value: coverageGain },
            { label: '采样成本惩罚(估计)', value: costPenalty }
        ];

        const hasData = rows.some((row) => Number.isFinite(row.value) && Math.abs(row.value) > 1e-8);
        if (!hasData) {
            container.innerHTML = '<div class="status-message">暂无奖励分解数据</div>';
            return;
        }
        const maxAbs = Math.max(...rows.map((row) => Math.abs(Number(row.value) || 0)), 1e-6);
        container.innerHTML = `
            <div class="dl-rl-reward-list">
                ${rows.map((row) => {
                    const value = Number(row.value) || 0;
                    const width = Math.round((Math.abs(value) / maxAbs) * 100);
                    const sign = value >= 0 ? 'positive' : 'negative';
                    return `
                        <div class="dl-rl-reward-item ${sign}">
                            <span class="dl-rl-reward-label">${this.escapeHtml(row.label)}</span>
                            <div class="dl-rl-reward-track">
                                <div class="dl-rl-reward-fill" style="width:${Math.max(2, width)}%"></div>
                            </div>
                            <span class="dl-rl-reward-value">${value.toFixed(4)}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    private renderStateActionTrajectory(payload: Record<string, unknown>): void {
        const container = this.container.querySelector('#dl-rl-state-action-trajectory') as HTMLElement | null;
        if (!container) {
            return;
        }
        const explanations = this.getRecord(payload.explanations);
        const actionValueVis = this.getRecord(explanations.action_value_visualization);
        const pointsRaw = Array.isArray(actionValueVis.action_value_points)
            ? actionValueVis.action_value_points as Array<Record<string, unknown>>
            : [];
        const points = pointsRaw
            .map((item, idx) => ({
                rank: Number(item.rank || idx + 1),
                row: Number(item.row),
                col: Number(item.col),
                value: Number(item.value ?? 0),
                source: String(item.source || 'unknown')
            }))
            .filter((item) => Number.isFinite(item.row) && Number.isFinite(item.col))
            .sort((a, b) => a.rank - b.rank);

        if (!points.length) {
            container.innerHTML = '<div class="status-message">暂无状态-动作轨迹数据</div>';
            return;
        }
        const maxRow = Math.max(...points.map((point) => point.row), 1);
        const maxCol = Math.max(...points.map((point) => point.col), 1);
        const width = 280;
        const height = 200;
        const padding = 16;
        const scaleX = (col: number) => padding + (col / Math.max(1, maxCol)) * (width - padding * 2);
        const scaleY = (row: number) => padding + (row / Math.max(1, maxRow)) * (height - padding * 2);
        const path = points.map((point, idx) => `${idx === 0 ? 'M' : 'L'} ${scaleX(point.col).toFixed(2)} ${scaleY(point.row).toFixed(2)}`).join(' ');

        container.innerHTML = `
            <svg class="dl-rl-trajectory-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="状态动作轨迹图">
                <rect x="1" y="1" width="${width - 2}" height="${height - 2}" class="dl-rl-trajectory-frame"></rect>
                <path d="${path}" class="dl-rl-trajectory-line"></path>
                ${points.map((point) => {
                    const cx = scaleX(point.col).toFixed(2);
                    const cy = scaleY(point.row).toFixed(2);
                    const cls = point.source === 'rl' ? 'rl' : 'rule';
                    return `
                        <g class="dl-rl-trajectory-point ${cls}">
                            <circle cx="${cx}" cy="${cy}" r="4"></circle>
                            <title>step=${point.rank}, row=${point.row}, col=${point.col}, value=${point.value.toFixed(4)}</title>
                        </g>
                    `;
                }).join('')}
            </svg>
            <div class="dl-rl-viz-footnote">轨迹点数 ${points.length} · 网格 ${maxRow + 1}×${maxCol + 1}</div>
        `;
    }

    private getRecord(value: unknown): Record<string, unknown> {
        if (value && typeof value === 'object' && !Array.isArray(value)) {
            return value as Record<string, unknown>;
        }
        return {};
    }

    private escapeHtml(value: string): string {
        return value
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    private exportResult(): void {
        if (!this.lastResult) {
            this.setStatus('没有可导出的结果，请先训练或推荐', 'warning');
            return;
        }

        const blob = new Blob([JSON.stringify(this.lastResult, null, 2)], {
            type: 'application/json;charset=utf-8'
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `sampling-rl-result-${Date.now()}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        this.setStatus('结果导出成功', 'success');
    }

    public destroy(): void {
        this.container.innerHTML = '';
    }
}
