import type { IAPIService } from '../../types/api';

type SpatialSample = [number, number, number];
type SpatialQuery = [number, number];

type NeighborImpact = {
    sampleIndex: number;
    sampleCoord: [number, number];
    sampleValue: number;
    distance: number;
    weight: number;
    contribution: number;
};

type QueryVisualizationRow = {
    queryIndex: number;
    queryCoord: [number, number];
    predicted: number;
    weightedMean: number;
    nearestValue: number;
    consistencyError: number;
    absConsistencyError: number;
    dominantNeighbor: NeighborImpact;
    neighbors: NeighborImpact[];
};

type HistogramData = {
    edges: number[];
    counts: number[];
};

type SpatialVisualizationData = {
    rows: QueryVisualizationRow[];
    selectedQueryIndex: number;
    weightHistogram: HistogramData;
    global: {
        mae: number;
        rmse: number;
        maxAbsError: number;
        meanDominantWeight: number;
    };
};

/**
 * 空间插值神经网络子面板
 */
export class SpatialInterpolationPanel {
    private container: HTMLElement;
    private apiService: IAPIService;
    private lastResult: unknown = null;
    private visualizationData: SpatialVisualizationData | null = null;

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
                    <h4>空间插值神经网络</h4>
                    <p>训练并预测空间连续变量</p>
                </div>

                <div class="dl-form-grid">
                    <label class="dl-field">
                        <span>模型类型</span>
                        <select id="dl-spatial-model" class="select">
                            <option value="gnn">GNN</option>
                            <option value="attention">Attention</option>
                            <option value="residual">Residual</option>
                        </select>
                    </label>
                    <label class="dl-field">
                        <span>训练轮数</span>
                        <input id="dl-spatial-epochs" class="input" type="number" min="1" max="200" value="30">
                    </label>
                    <label class="dl-field">
                        <span>融合比例</span>
                        <input id="dl-spatial-blend" class="input" type="number" min="0" max="1" step="0.05" value="0.6">
                    </label>
                </div>

                <label class="dl-field dl-field-full">
                    <span>训练样本 samples（JSON）</span>
                    <textarea id="dl-spatial-samples" class="dl-textarea" rows="5">[[0,0,1.2],[1,0,1.8],[0,1,2.3],[1,1,2.9],[0.5,0.7,2.1]]</textarea>
                </label>

                <label class="dl-field dl-field-full">
                    <span>预测点 queries（JSON）</span>
                    <textarea id="dl-spatial-queries" class="dl-textarea" rows="3">[[0.2,0.2],[0.8,0.5],[0.3,0.9]]</textarea>
                </label>

                <div class="dl-actions">
                    <button id="dl-spatial-train" class="btn btn-primary">训练模型</button>
                    <button id="dl-spatial-predict" class="btn btn-secondary">执行预测</button>
                    <button id="dl-spatial-export" class="btn btn-export">导出结果</button>
                </div>

                <div id="dl-spatial-status" class="status-message"></div>
                <pre id="dl-spatial-result" class="dl-result">暂无结果</pre>

                <section class="dl-spatial-viz-card">
                    <div class="dl-spatial-viz-header">
                        <h5>插值解释可视化</h5>
                        <div class="dl-spatial-viz-controls">
                            <label for="dl-spatial-query-index">查询点</label>
                            <select id="dl-spatial-query-index" class="select" disabled>
                                <option value="0">Q0</option>
                            </select>
                        </div>
                    </div>
                    <p class="dl-spatial-viz-tip">说明：误差解释采用“预测值 vs 邻域加权均值”的一致性误差。</p>
                    <div class="dl-spatial-viz-grid">
                        <article class="dl-spatial-viz-panel">
                            <h6>插值误差解释可视化</h6>
                            <div id="dl-spatial-error-summary" class="dl-spatial-summary">暂无数据</div>
                            <div id="dl-spatial-error-chart" class="dl-spatial-chart"></div>
                        </article>
                        <article class="dl-spatial-viz-panel">
                            <h6>空间权重分布展示</h6>
                            <div id="dl-spatial-weight-summary" class="dl-spatial-summary">暂无数据</div>
                            <div id="dl-spatial-weight-chart" class="dl-spatial-chart"></div>
                        </article>
                        <article class="dl-spatial-viz-panel">
                            <h6>邻域影响分析</h6>
                            <div id="dl-spatial-neighborhood-summary" class="dl-spatial-summary">暂无数据</div>
                            <div id="dl-spatial-neighborhood-chart" class="dl-spatial-chart"></div>
                        </article>
                        <article class="dl-spatial-viz-panel">
                            <h6>插值结果对比图</h6>
                            <div id="dl-spatial-compare-summary" class="dl-spatial-summary">暂无数据</div>
                            <div id="dl-spatial-compare-chart" class="dl-spatial-chart"></div>
                        </article>
                    </div>
                </section>
            </div>
        `;
    }

    private bindEvents(): void {
        this.container.querySelector('#dl-spatial-train')?.addEventListener('click', () => {
            void this.handleTrain();
        });

        this.container.querySelector('#dl-spatial-predict')?.addEventListener('click', () => {
            void this.handlePredict();
        });

        this.container.querySelector('#dl-spatial-export')?.addEventListener('click', () => {
            this.exportResult();
        });

        this.container.querySelector('#dl-spatial-query-index')?.addEventListener('change', (event) => {
            const target = event.target as HTMLSelectElement;
            const selected = Number(target.value);
            if (this.visualizationData && Number.isFinite(selected)) {
                this.visualizationData.selectedQueryIndex = Math.max(0, Math.min(selected, this.visualizationData.rows.length - 1));
                this.renderVisualizations();
            }
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
        const status = this.container.querySelector('#dl-spatial-status') as HTMLElement | null;
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
        const result = this.container.querySelector('#dl-spatial-result') as HTMLElement | null;
        if (!result) {
            return;
        }
        result.textContent = JSON.stringify(data, null, 2);
    }

    private getModelType(): 'gnn' | 'attention' | 'residual' {
        const model = (this.container.querySelector('#dl-spatial-model') as HTMLSelectElement | null)?.value || 'gnn';
        if (model === 'attention' || model === 'residual') {
            return model;
        }
        return 'gnn';
    }

    private toFiniteNumber(value: unknown, fallback: number = 0): number {
        const n = Number(value);
        return Number.isFinite(n) ? n : fallback;
    }

    private normalizePrediction(prediction: unknown): number[] {
        if (!Array.isArray(prediction)) {
            return [];
        }
        return prediction.map(item => this.toFiniteNumber(item, 0));
    }

    private computeDistance(a: [number, number], b: [number, number]): number {
        const dx = a[0] - b[0];
        const dy = a[1] - b[1];
        return Math.sqrt(dx * dx + dy * dy);
    }

    private computeWeightHistogram(weights: number[], bins: number = 10): HistogramData {
        if (weights.length === 0) {
            return { edges: [], counts: [] };
        }
        const min = Math.min(...weights);
        const max = Math.max(...weights);
        if (Math.abs(max - min) < 1e-12) {
            return {
                edges: [min, max],
                counts: [weights.length]
            };
        }

        const step = (max - min) / bins;
        const edges = Array.from({ length: bins + 1 }, (_, idx) => min + idx * step);
        const counts = Array.from({ length: bins }, () => 0);

        weights.forEach((value) => {
            let index = Math.floor((value - min) / step);
            if (index >= bins) {
                index = bins - 1;
            }
            if (index < 0) {
                index = 0;
            }
            counts[index] += 1;
        });

        return { edges, counts };
    }

    private createVisualizationData(samples: SpatialSample[], queries: SpatialQuery[], prediction: number[]): SpatialVisualizationData | null {
        if (queries.length === 0 || samples.length === 0 || prediction.length === 0) {
            return null;
        }
        const queryCount = Math.min(queries.length, prediction.length);
        const eps = 1e-6;
        const allWeights: number[] = [];
        const rows: QueryVisualizationRow[] = [];

        for (let i = 0; i < queryCount; i += 1) {
            const queryCoord = queries[i];
            const queryPrediction = this.toFiniteNumber(prediction[i], 0);
            const neighborsRaw = samples.map((sample, sampleIndex) => {
                const sampleCoord: [number, number] = [sample[0], sample[1]];
                const sampleValue = this.toFiniteNumber(sample[2], 0);
                const distance = this.computeDistance(queryCoord, sampleCoord);
                const inv = 1 / Math.pow(distance + eps, 2);
                return {
                    sampleIndex,
                    sampleCoord,
                    sampleValue,
                    distance,
                    inv
                };
            });

            const invSum = neighborsRaw.reduce((sum, item) => sum + item.inv, 0) + eps;
            const neighbors = neighborsRaw.map(item => {
                const weight = item.inv / invSum;
                allWeights.push(weight);
                return {
                    sampleIndex: item.sampleIndex,
                    sampleCoord: item.sampleCoord,
                    sampleValue: item.sampleValue,
                    distance: item.distance,
                    weight,
                    contribution: weight * item.sampleValue
                } as NeighborImpact;
            }).sort((a, b) => b.weight - a.weight);

            const weightedMean = neighbors.reduce((sum, item) => sum + item.contribution, 0);
            const nearest = [...neighbors].sort((a, b) => a.distance - b.distance)[0] || neighbors[0];
            const consistencyError = queryPrediction - weightedMean;

            rows.push({
                queryIndex: i,
                queryCoord,
                predicted: queryPrediction,
                weightedMean,
                nearestValue: nearest?.sampleValue ?? 0,
                consistencyError,
                absConsistencyError: Math.abs(consistencyError),
                dominantNeighbor: neighbors[0],
                neighbors: neighbors.slice(0, 5)
            });
        }

        if (rows.length === 0) {
            return null;
        }

        const mae = rows.reduce((sum, row) => sum + row.absConsistencyError, 0) / rows.length;
        const rmse = Math.sqrt(rows.reduce((sum, row) => sum + row.consistencyError * row.consistencyError, 0) / rows.length);
        const maxAbsError = Math.max(...rows.map(row => row.absConsistencyError));
        const meanDominantWeight = rows.reduce((sum, row) => sum + row.dominantNeighbor.weight, 0) / rows.length;

        return {
            rows,
            selectedQueryIndex: 0,
            weightHistogram: this.computeWeightHistogram(allWeights, 10),
            global: {
                mae,
                rmse,
                maxAbsError,
                meanDominantWeight
            }
        };
    }

    private updateQuerySelector(): void {
        const selector = this.container.querySelector('#dl-spatial-query-index') as HTMLSelectElement | null;
        if (!selector) {
            return;
        }
        const data = this.visualizationData;
        if (!data || data.rows.length === 0) {
            selector.innerHTML = '<option value="0">Q0</option>';
            selector.disabled = true;
            return;
        }
        selector.innerHTML = data.rows.map(row => `<option value="${row.queryIndex}">Q${row.queryIndex}</option>`).join('');
        selector.value = String(data.selectedQueryIndex);
        selector.disabled = false;
    }

    private renderBarSeries(values: number[], maxHeight: number, className: string): string {
        if (values.length === 0) {
            return '<div class="dl-spatial-empty">暂无数据</div>';
        }
        const max = Math.max(...values, 1e-9);
        return `
            <div class="dl-spatial-bar-series ${className}">
                ${values.map((value, index) => {
                    const height = Math.max(4, (value / max) * maxHeight);
                    return `
                        <div class="dl-spatial-bar-wrap" title="Q${index}: ${value.toFixed(4)}">
                            <div class="dl-spatial-bar" style="height:${height.toFixed(1)}px;"></div>
                            <span class="dl-spatial-bar-label">${index}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    private renderHistogram(hist: HistogramData): string {
        if (hist.counts.length === 0) {
            return '<div class="dl-spatial-empty">暂无数据</div>';
        }
        const max = Math.max(...hist.counts, 1);
        return `
            <div class="dl-spatial-hist-series">
                ${hist.counts.map((count, index) => {
                    const height = Math.max(4, (count / max) * 120);
                    const left = hist.edges[index];
                    const right = hist.edges[index + 1] ?? left;
                    return `
                        <div class="dl-spatial-bar-wrap" title="[${left.toFixed(4)}, ${right.toFixed(4)}): ${count}">
                            <div class="dl-spatial-bar dl-spatial-hist-bar" style="height:${height.toFixed(1)}px;"></div>
                            <span class="dl-spatial-bar-label">${index + 1}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    private buildCompareSvg(rows: QueryVisualizationRow[]): string {
        if (rows.length === 0) {
            return '<div class="dl-spatial-empty">暂无数据</div>';
        }

        const width = 560;
        const height = 220;
        const pad = { left: 44, right: 12, top: 10, bottom: 28 };
        const xSpan = Math.max(1, rows.length - 1);
        const values = rows.flatMap(row => [row.predicted, row.weightedMean, row.nearestValue]);
        const minY = Math.min(...values);
        const maxY = Math.max(...values);
        const yRange = Math.max(1e-9, maxY - minY);

        const toX = (index: number): number => pad.left + (index / xSpan) * (width - pad.left - pad.right);
        const toY = (value: number): number => pad.top + (1 - (value - minY) / yRange) * (height - pad.top - pad.bottom);
        const line = (list: number[]): string => list.map((value, index) => `${toX(index).toFixed(2)},${toY(value).toFixed(2)}`).join(' ');

        const predicted = rows.map(row => row.predicted);
        const weighted = rows.map(row => row.weightedMean);
        const nearest = rows.map(row => row.nearestValue);

        return `
            <svg class="dl-spatial-compare-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="插值结果对比图">
                <line x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" class="dl-spatial-axis"></line>
                <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" class="dl-spatial-axis"></line>
                <polyline points="${line(predicted)}" class="dl-spatial-line predicted"></polyline>
                <polyline points="${line(weighted)}" class="dl-spatial-line weighted"></polyline>
                <polyline points="${line(nearest)}" class="dl-spatial-line nearest"></polyline>
            </svg>
            <div class="dl-spatial-legend">
                <span><i class="line-dot predicted"></i>预测值</span>
                <span><i class="line-dot weighted"></i>邻域加权均值</span>
                <span><i class="line-dot nearest"></i>最近邻样本值</span>
            </div>
        `;
    }

    private renderVisualizations(): void {
        const errorSummary = this.container.querySelector('#dl-spatial-error-summary') as HTMLElement | null;
        const errorChart = this.container.querySelector('#dl-spatial-error-chart') as HTMLElement | null;
        const weightSummary = this.container.querySelector('#dl-spatial-weight-summary') as HTMLElement | null;
        const weightChart = this.container.querySelector('#dl-spatial-weight-chart') as HTMLElement | null;
        const neighborhoodSummary = this.container.querySelector('#dl-spatial-neighborhood-summary') as HTMLElement | null;
        const neighborhoodChart = this.container.querySelector('#dl-spatial-neighborhood-chart') as HTMLElement | null;
        const compareSummary = this.container.querySelector('#dl-spatial-compare-summary') as HTMLElement | null;
        const compareChart = this.container.querySelector('#dl-spatial-compare-chart') as HTMLElement | null;

        if (!errorSummary || !errorChart || !weightSummary || !weightChart || !neighborhoodSummary || !neighborhoodChart || !compareSummary || !compareChart) {
            return;
        }

        const data = this.visualizationData;
        if (!data || data.rows.length === 0) {
            errorSummary.textContent = '暂无数据';
            errorChart.innerHTML = '<div class="dl-spatial-empty">请先执行预测</div>';
            weightSummary.textContent = '暂无数据';
            weightChart.innerHTML = '<div class="dl-spatial-empty">请先执行预测</div>';
            neighborhoodSummary.textContent = '暂无数据';
            neighborhoodChart.innerHTML = '<div class="dl-spatial-empty">请先执行预测</div>';
            compareSummary.textContent = '暂无数据';
            compareChart.innerHTML = '<div class="dl-spatial-empty">请先执行预测</div>';
            this.updateQuerySelector();
            return;
        }

        this.updateQuerySelector();
        const selected = data.rows[Math.max(0, Math.min(data.selectedQueryIndex, data.rows.length - 1))];
        const errors = data.rows.map(row => row.absConsistencyError);

        errorSummary.textContent = `MAE=${data.global.mae.toFixed(4)} | RMSE=${data.global.rmse.toFixed(4)} | MaxAbs=${data.global.maxAbsError.toFixed(4)}`;
        errorChart.innerHTML = this.renderBarSeries(errors, 120, 'error');

        weightSummary.textContent = `主导邻居平均权重=${data.global.meanDominantWeight.toFixed(4)} | 权重样本数=${data.weightHistogram.counts.reduce((sum, c) => sum + c, 0)}`;
        weightChart.innerHTML = this.renderHistogram(data.weightHistogram);

        neighborhoodSummary.textContent = `Q${selected.queryIndex} 坐标(${selected.queryCoord[0].toFixed(3)}, ${selected.queryCoord[1].toFixed(3)}) | 主导邻居权重=${selected.dominantNeighbor.weight.toFixed(4)}`;
        neighborhoodChart.innerHTML = `
            <div class="dl-spatial-neighbor-list">
                ${selected.neighbors.map((neighbor, idx) => `
                    <div class="dl-spatial-neighbor-item">
                        <div class="dl-spatial-neighbor-head">
                            <span>#${idx + 1} S${neighbor.sampleIndex}</span>
                            <span>权重 ${neighbor.weight.toFixed(4)}</span>
                        </div>
                        <div class="dl-spatial-neighbor-bar">
                            <div class="dl-spatial-neighbor-fill" style="width:${(neighbor.weight * 100).toFixed(2)}%;"></div>
                        </div>
                        <div class="dl-spatial-neighbor-meta">
                            距离 ${neighbor.distance.toFixed(4)} | 值 ${neighbor.sampleValue.toFixed(4)} | 贡献 ${neighbor.contribution.toFixed(4)}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        const delta = selected.predicted - selected.weightedMean;
        compareSummary.textContent = `Q${selected.queryIndex} 预测=${selected.predicted.toFixed(4)} | 邻域均值=${selected.weightedMean.toFixed(4)} | 最近邻=${selected.nearestValue.toFixed(4)} | 偏差=${delta.toFixed(4)}`;
        compareChart.innerHTML = this.buildCompareSvg(data.rows);
    }

    private async handleTrain(): Promise<void> {
        try {
            this.setStatus('正在训练空间插值模型...', 'loading');
            const modelType = this.getModelType();
            const epochs = Number((this.container.querySelector('#dl-spatial-epochs') as HTMLInputElement | null)?.value || 30);
            const samples = this.parseJson<SpatialSample[]>('dl-spatial-samples', 'samples');

            const response = await this.apiService.trainSpatial({
                model_type: modelType,
                samples,
                epochs
            });

            this.lastResult = response;
            this.setResult(response);
            this.setStatus('空间插值模型训练完成', 'success');
        } catch (error) {
            this.setStatus(`训练失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private async handlePredict(): Promise<void> {
        try {
            this.setStatus('正在执行空间预测...', 'loading');
            const modelType = this.getModelType();
            const blendRatio = Number((this.container.querySelector('#dl-spatial-blend') as HTMLInputElement | null)?.value || 0.6);
            const samples = this.parseJson<SpatialSample[]>('dl-spatial-samples', 'samples');
            const queries = this.parseJson<SpatialQuery[]>('dl-spatial-queries', 'queries');

            const response = await this.apiService.predictSpatial({
                model_type: modelType,
                samples,
                queries,
                blend_ratio: blendRatio
            });

            this.lastResult = response;
            this.visualizationData = this.createVisualizationData(samples, queries, this.normalizePrediction((response as { prediction?: unknown })?.prediction));
            this.renderVisualizations();
            this.setResult(response);
            this.setStatus('空间预测完成', 'success');
        } catch (error) {
            this.setStatus(`预测失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private exportResult(): void {
        if (!this.lastResult) {
            this.setStatus('没有可导出的结果，请先训练或预测', 'warning');
            return;
        }

        const blob = new Blob([JSON.stringify(this.lastResult, null, 2)], {
            type: 'application/json;charset=utf-8'
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `spatial-result-${Date.now()}.json`;
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
