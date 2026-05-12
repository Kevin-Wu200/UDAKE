import { I18n } from '../utils/I18n';
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

                <section class="dl-rl-visualizations dl-rl-visualizations-phase2">
                    <h5>强化学习可视化组件（第2部分）</h5>
                    <div class="dl-rl-viz-grid">
                        <article class="dl-rl-viz-card">
                            <h6>采样点地图</h6>
                            <div id="dl-rl-sampling-point-map" class="dl-rl-viz-body">
                                <div class="status-message">暂无可视化数据</div>
                            </div>
                        </article>

                        <article class="dl-rl-viz-card">
                            <h6>策略变化趋势图</h6>
                            <div id="dl-rl-strategy-trend" class="dl-rl-viz-body">
                                <div class="status-message">暂无可视化数据</div>
                            </div>
                        </article>

                        <article class="dl-rl-viz-card">
                            <h6>价值函数等高线图</h6>
                            <div id="dl-rl-value-contour" class="dl-rl-viz-body">
                                <div class="status-message">暂无可视化数据</div>
                            </div>
                        </article>

                        <article class="dl-rl-viz-card">
                            <h6>探索轨迹可视化</h6>
                            <div id="dl-rl-exploration-trajectory" class="dl-rl-viz-body">
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
        const rootPayload = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
        const recommendationPayload = this.extractRecommendationPayload(rootPayload);
        this.renderPolicyDistribution(recommendationPayload);
        this.renderActionValueHeatmap(recommendationPayload);
        this.renderRewardBreakdown(recommendationPayload);
        this.renderStateActionTrajectory(recommendationPayload);
        this.renderSamplingPointMap(recommendationPayload);
        this.renderStrategyTrend(rootPayload, recommendationPayload);
        this.renderValueFunctionContour(recommendationPayload);
        this.renderExplorationTrajectory(recommendationPayload);
    }

    private extractRecommendationPayload(rootPayload: Record<string, unknown>): Record<string, unknown> {
        const nested = this.getRecord(rootPayload.recommendation);
        if (Object.keys(nested).length > 0) {
            return nested;
        }
        return rootPayload;
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
            container.innerHTML = '<div class="status-message">' + I18n.t('samplingrl.noPolicyDistribution') + '</div>';
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
            container.innerHTML = '<div class="status-message">' + I18n.t('samplingrl.noActionValueHeatmap') + '</div>';
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
            container.innerHTML = '<div class="status-message">' + I18n.t('samplingrl.noRewardDecomposition') + '</div>';
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
            container.innerHTML = '<div class="status-message">' + I18n.t('samplingrl.noStateActionTrajectory') + '</div>';
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

    private renderSamplingPointMap(payload: Record<string, unknown>): void {
        const container = this.container.querySelector('#dl-rl-sampling-point-map') as HTMLElement | null;
        if (!container) {
            return;
        }
        const recommendations = (Array.isArray(payload.recommendations) ? payload.recommendations : [])
            .map((item) => this.getRecord(item))
            .map((item) => ({
                x: Number(item.x),
                y: Number(item.y),
                source: String(item.source || 'unknown'),
                score: Number(item.score || 0)
            }))
            .filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y));
        const mapData = this.lastUncertaintyMap.length ? this.lastUncertaintyMap : [[1]];
        const rows = mapData.length;
        const cols = mapData[0]?.length || 1;
        const width = 320;
        const height = 210;
        const padding = 16;
        const gridWidth = width - padding * 2;
        const gridHeight = height - padding * 2;
        const flatValues = mapData.flat().filter((value) => Number.isFinite(value));
        const minValue = flatValues.length ? Math.min(...flatValues) : 0;
        const maxValue = flatValues.length ? Math.max(...flatValues) : 1;
        const span = Math.max(1e-8, maxValue - minValue);
        const cellWidth = gridWidth / Math.max(1, cols);
        const cellHeight = gridHeight / Math.max(1, rows);
        const scaleX = (x: number) => padding + Math.max(0, Math.min(1, x)) * gridWidth;
        const scaleY = (y: number) => padding + Math.max(0, Math.min(1, y)) * gridHeight;

        const heatCells = mapData.map((row, r) => row.map((value, c) => {
            const normalized = (value - minValue) / span;
            const alpha = 0.12 + normalized * 0.68;
            return `<rect x="${(padding + c * cellWidth).toFixed(2)}" y="${(padding + r * cellHeight).toFixed(2)}" width="${cellWidth.toFixed(2)}" height="${cellHeight.toFixed(2)}" fill="rgba(14,165,233,${alpha.toFixed(3)})"></rect>`;
        }).join('')).join('');

        const existingPoints = this.lastExistingPoints
            .map((point) => ({ x: Number(point[0]), y: Number(point[1]) }))
            .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
            .map((point) => `<circle class="dl-rl-map-existing" cx="${scaleX(point.x).toFixed(2)}" cy="${scaleY(point.y).toFixed(2)}" r="4"></circle>`)
            .join('');

        const recPoints = recommendations
            .map((point, idx) => {
                const cls = point.source === 'rl' ? 'rl' : 'rule';
                return `
                    <g class="dl-rl-map-recommend ${cls}">
                        <circle cx="${scaleX(point.x).toFixed(2)}" cy="${scaleY(point.y).toFixed(2)}" r="4.6"></circle>
                        <text x="${(scaleX(point.x) + 6).toFixed(2)}" y="${(scaleY(point.y) - 5).toFixed(2)}">${idx + 1}</text>
                    </g>
                `;
            })
            .join('');

        container.innerHTML = `
            <svg class="dl-rl-map-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="采样点地图">
                <rect x="1" y="1" width="${width - 2}" height="${height - 2}" class="dl-rl-map-frame"></rect>
                ${heatCells}
                ${existingPoints}
                ${recPoints}
            </svg>
            <div class="dl-rl-viz-footnote">已有点 ${this.lastExistingPoints.length} · 推荐点 ${recommendations.length}</div>
        `;
    }

    private renderStrategyTrend(rootPayload: Record<string, unknown>, recommendationPayload: Record<string, unknown>): void {
        const container = this.container.querySelector('#dl-rl-strategy-trend') as HTMLElement | null;
        if (!container) {
            return;
        }
        const optimization = this.getRecord(rootPayload.optimization);
        const strategyScores = this.getRecord(optimization.strategy_scores);
        const entries = Object.entries(strategyScores)
            .map(([key, value]) => ({ key, value: Number(value) }))
            .filter((item) => Number.isFinite(item.value));

        if (entries.length > 0) {
            const maxValue = Math.max(...entries.map((item) => item.value), 1e-6);
            container.innerHTML = `
                <div class="dl-rl-strategy-bars">
                    ${entries.map((item) => {
                        const label = item.key === 'rl_only' ? 'RL' : item.key === 'rule_only' ? 'Rule' : 'Hybrid';
                        const width = Math.max(3, Math.round((item.value / maxValue) * 100));
                        return `
                            <div class="dl-rl-strategy-bar-item">
                                <span class="dl-rl-strategy-label">${label}</span>
                                <div class="dl-rl-strategy-track"><div class="dl-rl-strategy-fill" style="width:${width}%"></div></div>
                                <span class="dl-rl-strategy-value">${item.value.toFixed(4)}</span>
                            </div>
                        `;
                    }).join('')}
                </div>
                <div class="dl-rl-viz-footnote">最优策略：${this.escapeHtml(String(optimization.best_strategy || 'unknown'))}</div>
            `;
            return;
        }

        const trainingSummary = this.getRecord(recommendationPayload.training_summary);
        const points = [
            Number(trainingSummary.mean_reward),
            Number(trainingSummary.best_reward),
            Number(trainingSummary.final_reward)
        ].filter((item) => Number.isFinite(item));
        if (points.length === 0) {
            container.innerHTML = '<div class="status-message">' + I18n.t('samplingrl.noPolicyTrend') + '</div>';
            return;
        }
        const width = 300;
        const height = 180;
        const padding = 20;
        const maxV = Math.max(...points, 1e-6);
        const minV = Math.min(...points);
        const span = Math.max(1e-8, maxV - minV);
        const scaleX = (idx: number) => padding + (idx / Math.max(1, points.length - 1)) * (width - padding * 2);
        const scaleY = (v: number) => padding + (1 - (v - minV) / span) * (height - padding * 2);
        const path = points.map((value, idx) => `${idx === 0 ? 'M' : 'L'} ${scaleX(idx).toFixed(2)} ${scaleY(value).toFixed(2)}`).join(' ');
        container.innerHTML = `
            <svg class="dl-rl-trend-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="策略趋势图">
                <path d="${path}" class="dl-rl-trend-line"></path>
                ${points.map((value, idx) => `<circle class="dl-rl-trend-point" cx="${scaleX(idx).toFixed(2)}" cy="${scaleY(value).toFixed(2)}" r="4"></circle>`).join('')}
            </svg>
            <div class="dl-rl-viz-footnote">使用训练摘要近似趋势：均值/最佳/最终奖励</div>
        `;
    }

    private renderValueFunctionContour(payload: Record<string, unknown>): void {
        const container = this.container.querySelector('#dl-rl-value-contour') as HTMLElement | null;
        if (!container) {
            return;
        }
        const explanations = this.getRecord(payload.explanations);
        const actionValue = this.getRecord(explanations.action_value_visualization);
        const regionVisualization = this.getRecord(explanations.sampling_region_visualization);
        const contourSource = Array.isArray(regionVisualization.region_intensity_map)
            ? regionVisualization.region_intensity_map
            : actionValue.value_heatmap;
        const map = this.normalizeHeatmap(Array.isArray(contourSource) ? contourSource : []);
        if (!map.length) {
            container.innerHTML = '<div class="status-message">' + I18n.t('samplingrl.noValueFunctionContour') + '</div>';
            return;
        }
        const width = 320;
        const height = 210;
        const padding = 12;
        const rows = map.length;
        const cols = map[0]?.length || 1;
        const cellWidth = (width - padding * 2) / Math.max(1, cols);
        const cellHeight = (height - padding * 2) / Math.max(1, rows);
        const flat = map.flat();
        const minV = Math.min(...flat);
        const maxV = Math.max(...flat);
        const span = Math.max(1e-8, maxV - minV);
        const bands = [0.2, 0.4, 0.6, 0.8];
        const cells = map.map((row, r) => row.map((value, c) => {
            const normalized = (value - minV) / span;
            let band = 0;
            bands.forEach((threshold, idx) => {
                if (normalized >= threshold) {
                    band = idx + 1;
                }
            });
            return `<rect class="dl-rl-contour-band-${band}" x="${(padding + c * cellWidth).toFixed(2)}" y="${(padding + r * cellHeight).toFixed(2)}" width="${cellWidth.toFixed(2)}" height="${cellHeight.toFixed(2)}"></rect>`;
        }).join('')).join('');
        container.innerHTML = `
            <svg class="dl-rl-contour-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="价值函数等高线图">
                <rect x="1" y="1" width="${width - 2}" height="${height - 2}" class="dl-rl-contour-frame"></rect>
                ${cells}
            </svg>
            <div class="dl-rl-viz-footnote">值域 ${minV.toFixed(4)} - ${maxV.toFixed(4)}</div>
        `;
    }

    private renderExplorationTrajectory(payload: Record<string, unknown>): void {
        const container = this.container.querySelector('#dl-rl-exploration-trajectory') as HTMLElement | null;
        if (!container) {
            return;
        }
        const explanations = this.getRecord(payload.explanations);
        const actionValue = this.getRecord(explanations.action_value_visualization);
        const heatmap = this.normalizeHeatmap(Array.isArray(actionValue.value_heatmap) ? actionValue.value_heatmap : []);
        const maxRow = Math.max(1, heatmap.length - 1);
        const maxCol = Math.max(1, (heatmap[0]?.length || 1) - 1);
        const rawPoints = Array.isArray(actionValue.action_value_points) ? actionValue.action_value_points : [];
        const points = rawPoints
            .map((item, idx) => this.getRecord(item))
            .map((item, idx) => ({
                rank: Number(item.rank || idx + 1),
                x: Number.isFinite(Number(item.x))
                    ? Number(item.x)
                    : Math.max(0, Math.min(1, Number(item.col) / Math.max(1, maxCol))),
                y: Number.isFinite(Number(item.y))
                    ? Number(item.y)
                    : Math.max(0, Math.min(1, Number(item.row) / Math.max(1, maxRow))),
                source: String(item.source || 'unknown')
            }))
            .filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y))
            .sort((a, b) => a.rank - b.rank);

        if (!points.length) {
            container.innerHTML = '<div class="status-message">' + I18n.t('samplingrl.noExplorationTrajectory') + '</div>';
            return;
        }
        const width = 320;
        const height = 210;
        const padding = 14;
        const scaleX = (x: number) => padding + Math.max(0, Math.min(1, x)) * (width - padding * 2);
        const scaleY = (y: number) => padding + Math.max(0, Math.min(1, y)) * (height - padding * 2);
        const path = points.map((point, idx) => `${idx === 0 ? 'M' : 'L'} ${scaleX(point.x).toFixed(2)} ${scaleY(point.y).toFixed(2)}`).join(' ');
        container.innerHTML = `
            <svg class="dl-rl-exploration-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="探索轨迹可视化">
                <rect x="1" y="1" width="${width - 2}" height="${height - 2}" class="dl-rl-exploration-frame"></rect>
                <path d="${path}" class="dl-rl-exploration-line"></path>
                ${points.map((point) => `
                    <g class="dl-rl-exploration-point ${point.source === 'rl' ? 'rl' : 'rule'}">
                        <circle cx="${scaleX(point.x).toFixed(2)}" cy="${scaleY(point.y).toFixed(2)}" r="4"></circle>
                        <text x="${(scaleX(point.x) + 5).toFixed(2)}" y="${(scaleY(point.y) - 4).toFixed(2)}">${point.rank}</text>
                    </g>
                `).join('')}
            </svg>
            <div class="dl-rl-viz-footnote">探索步数 ${points.length}</div>
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
