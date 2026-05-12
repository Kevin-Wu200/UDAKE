import { I18n } from '../utils/I18n';
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
    allNeighbors: NeighborImpact[];
};

type HistogramData = {
    edges: number[];
    counts: number[];
};

type SpatialVisualizationData = {
    rows: QueryVisualizationRow[];
    selectedQueryIndex: number;
    weightHistogram: HistogramData;
    samplePoints: Array<{
        sampleIndex: number;
        coord: [number, number];
        value: number;
    }>;
    queryPoints: Array<{
        queryIndex: number;
        coord: [number, number];
        predicted: number;
    }>;
    valueRange: {
        min: number;
        max: number;
    };
    coordRange: {
        minX: number;
        maxX: number;
        minY: number;
        maxY: number;
    };
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
                        <article class="dl-spatial-viz-panel">
                            <h6>权重热力图</h6>
                            <div id="dl-spatial-heatmap-summary" class="dl-spatial-summary">暂无数据</div>
                            <div id="dl-spatial-heatmap-chart" class="dl-spatial-chart"></div>
                        </article>
                        <article class="dl-spatial-viz-panel">
                            <h6>邻域关系可视化</h6>
                            <div id="dl-spatial-network-summary" class="dl-spatial-summary">暂无数据</div>
                            <div id="dl-spatial-network-chart" class="dl-spatial-chart"></div>
                        </article>
                        <article class="dl-spatial-viz-panel">
                            <h6>空间插值地图展示</h6>
                            <div id="dl-spatial-map-summary" class="dl-spatial-summary">暂无数据</div>
                            <div id="dl-spatial-map-chart" class="dl-spatial-chart"></div>
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
        const samplePoints = samples.map((sample, sampleIndex) => ({
            sampleIndex,
            coord: [sample[0], sample[1]] as [number, number],
            value: this.toFiniteNumber(sample[2], 0)
        }));

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
                neighbors: neighbors.slice(0, 5),
                allNeighbors: neighbors
            });
        }

        if (rows.length === 0) {
            return null;
        }

        const mae = rows.reduce((sum, row) => sum + row.absConsistencyError, 0) / rows.length;
        const rmse = Math.sqrt(rows.reduce((sum, row) => sum + row.consistencyError * row.consistencyError, 0) / rows.length);
        const maxAbsError = Math.max(...rows.map(row => row.absConsistencyError));
        const meanDominantWeight = rows.reduce((sum, row) => sum + row.dominantNeighbor.weight, 0) / rows.length;
        const queryPoints = rows.map(row => ({
            queryIndex: row.queryIndex,
            coord: row.queryCoord,
            predicted: row.predicted
        }));

        const allValues = [...samplePoints.map(point => point.value), ...queryPoints.map(point => point.predicted)];
        const valueRange = {
            min: Math.min(...allValues),
            max: Math.max(...allValues)
        };

        const allCoords = [...samplePoints.map(point => point.coord), ...queryPoints.map(point => point.coord)];
        const xs = allCoords.map(coord => coord[0]);
        const ys = allCoords.map(coord => coord[1]);
        const coordRange = {
            minX: Math.min(...xs),
            maxX: Math.max(...xs),
            minY: Math.min(...ys),
            maxY: Math.max(...ys)
        };

        return {
            rows,
            selectedQueryIndex: 0,
            weightHistogram: this.computeWeightHistogram(allWeights, 10),
            samplePoints,
            queryPoints,
            valueRange,
            coordRange,
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

    private clamp(value: number, min: number, max: number): number {
        return Math.max(min, Math.min(max, value));
    }

    private normalize01(value: number, min: number, max: number): number {
        const span = Math.max(1e-9, max - min);
        return this.clamp((value - min) / span, 0, 1);
    }

    private heatColor(value: number, min: number, max: number): string {
        const t = this.normalize01(value, min, max);
        const hue = 210 - t * 165;
        const lightness = 95 - t * 43;
        return `hsl(${hue.toFixed(0)} 85% ${lightness.toFixed(0)}%)`;
    }

    private valueColor(value: number, min: number, max: number): string {
        const t = this.normalize01(value, min, max);
        const hue = 220 - t * 220;
        return `hsl(${hue.toFixed(0)} 82% 52%)`;
    }

    private renderWeightHeatmap(data: SpatialVisualizationData): string {
        const sampleCount = data.samplePoints.length;
        if (sampleCount === 0 || data.rows.length === 0) {
            return '<div class="dl-spatial-empty">暂无数据</div>';
        }

        const matrix = data.rows.map((row) => {
            const values = Array.from({ length: sampleCount }, () => 0);
            row.allNeighbors.forEach((neighbor) => {
                values[neighbor.sampleIndex] = neighbor.weight;
            });
            return values;
        });

        let matrixMax = 0;
        matrix.forEach((row) => {
            row.forEach((cell) => {
                matrixMax = Math.max(matrixMax, cell);
            });
        });
        const max = Math.max(1e-9, matrixMax);

        const headerCells = data.samplePoints
            .map(point => `<th title="样本 S${point.sampleIndex} (${point.coord[0].toFixed(3)}, ${point.coord[1].toFixed(3)})">S${point.sampleIndex}</th>`)
            .join('');
        const bodyRows = matrix.map((weights, rowIndex) => `
                <tr>
                    <th title="查询点 Q${rowIndex}">Q${rowIndex}</th>
                    ${weights.map((weight, colIndex) => {
                        const color = this.heatColor(weight, 0, max);
                        return `<td class="dl-spatial-heat-cell" style="background:${color};" title="Q${rowIndex}-S${colIndex} 权重 ${weight.toFixed(4)}">${weight.toFixed(3)}</td>`;
                    }).join('')}
                </tr>
            `).join('');

        return `
            <div class="dl-spatial-heatmap-wrap">
                <table class="dl-spatial-heatmap-table">
                    <thead>
                        <tr>
                            <th>Q\\S</th>
                            ${headerCells}
                        </tr>
                    </thead>
                    <tbody>
                        ${bodyRows}
                    </tbody>
                </table>
            </div>
            <div class="dl-spatial-color-legend">
                <span>低权重</span>
                <i class="dl-spatial-color-band"></i>
                <span>高权重</span>
            </div>
        `;
    }

    private buildNeighborhoodRelationSvg(row: QueryVisualizationRow): string {
        const width = 560;
        const height = 220;
        const centerX = width * 0.47;
        const centerY = height * 0.5;
        const radiusBase = Math.min(width, height) * 0.32;
        const neighbors = row.neighbors;
        if (neighbors.length === 0) {
            return '<div class="dl-spatial-empty">暂无邻域数据</div>';
        }

        const lineAndNode = neighbors.map((neighbor, index) => {
            const angle = (Math.PI * 2 * index) / neighbors.length - Math.PI / 2;
            const dynamicRadius = radiusBase - this.clamp(neighbor.weight * 70, 0, 45);
            const nx = centerX + dynamicRadius * Math.cos(angle);
            const ny = centerY + dynamicRadius * Math.sin(angle);
            const strokeWidth = (1.2 + neighbor.weight * 7).toFixed(2);
            const nodeR = (6 + neighbor.weight * 17).toFixed(2);
            return `
                <line x1="${centerX.toFixed(2)}" y1="${centerY.toFixed(2)}" x2="${nx.toFixed(2)}" y2="${ny.toFixed(2)}" class="dl-spatial-network-edge" style="stroke-width:${strokeWidth};"></line>
                <circle cx="${nx.toFixed(2)}" cy="${ny.toFixed(2)}" r="${nodeR}" class="dl-spatial-network-node"></circle>
                <text x="${nx.toFixed(2)}" y="${(ny - Number(nodeR) - 5).toFixed(2)}" class="dl-spatial-network-label">S${neighbor.sampleIndex}</text>
                <text x="${nx.toFixed(2)}" y="${(ny + Number(nodeR) + 12).toFixed(2)}" class="dl-spatial-network-meta">${neighbor.weight.toFixed(3)}</text>
            `;
        }).join('');

        return `
            <svg class="dl-spatial-network-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="邻域关系可视化">
                <circle cx="${centerX.toFixed(2)}" cy="${centerY.toFixed(2)}" r="20" class="dl-spatial-network-center"></circle>
                <text x="${centerX.toFixed(2)}" y="${(centerY + 4).toFixed(2)}" class="dl-spatial-network-center-label">Q${row.queryIndex}</text>
                ${lineAndNode}
            </svg>
        `;
    }

    private buildInterpolationMapSvg(data: SpatialVisualizationData, selected: QueryVisualizationRow): string {
        const width = 560;
        const height = 240;
        const pad = { left: 36, right: 14, top: 12, bottom: 28 };
        const spanX = Math.max(1e-9, data.coordRange.maxX - data.coordRange.minX);
        const spanY = Math.max(1e-9, data.coordRange.maxY - data.coordRange.minY);
        const toX = (x: number): number => pad.left + ((x - data.coordRange.minX) / spanX) * (width - pad.left - pad.right);
        const toY = (y: number): number => pad.top + (1 - (y - data.coordRange.minY) / spanY) * (height - pad.top - pad.bottom);

        const sampleDots = data.samplePoints.map((sample) => {
            const cx = toX(sample.coord[0]).toFixed(2);
            const cy = toY(sample.coord[1]).toFixed(2);
            const fill = this.valueColor(sample.value, data.valueRange.min, data.valueRange.max);
            return `
                <circle cx="${cx}" cy="${cy}" r="6" class="dl-spatial-map-sample" style="fill:${fill};"></circle>
                <text x="${(Number(cx) + 8).toFixed(2)}" y="${(Number(cy) - 6).toFixed(2)}" class="dl-spatial-map-label">S${sample.sampleIndex}</text>
            `;
        }).join('');

        const queryDots = data.queryPoints.map((point) => {
            const cx = toX(point.coord[0]).toFixed(2);
            const cy = toY(point.coord[1]).toFixed(2);
            const fill = this.valueColor(point.predicted, data.valueRange.min, data.valueRange.max);
            const isSelected = point.queryIndex === selected.queryIndex;
            const radius = isSelected ? 8 : 6;
            return `
                <circle cx="${cx}" cy="${cy}" r="${radius}" class="dl-spatial-map-query${isSelected ? ' selected' : ''}" style="fill:${fill};"></circle>
                <text x="${(Number(cx) + 8).toFixed(2)}" y="${(Number(cy) + 12).toFixed(2)}" class="dl-spatial-map-label">Q${point.queryIndex}</text>
            `;
        }).join('');

        const selectedX = toX(selected.queryCoord[0]);
        const selectedY = toY(selected.queryCoord[1]);
        const selectedLinks = selected.neighbors.map((neighbor) => {
            const tx = toX(neighbor.sampleCoord[0]);
            const ty = toY(neighbor.sampleCoord[1]);
            return `
                <line x1="${selectedX.toFixed(2)}" y1="${selectedY.toFixed(2)}" x2="${tx.toFixed(2)}" y2="${ty.toFixed(2)}" class="dl-spatial-map-link" style="stroke-width:${(1 + neighbor.weight * 5).toFixed(2)};"></line>
            `;
        }).join('');

        return `
            <svg class="dl-spatial-map-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="空间插值地图">
                <rect x="${pad.left}" y="${pad.top}" width="${(width - pad.left - pad.right).toFixed(2)}" height="${(height - pad.top - pad.bottom).toFixed(2)}" class="dl-spatial-map-frame"></rect>
                ${selectedLinks}
                ${sampleDots}
                ${queryDots}
            </svg>
            <div class="dl-spatial-legend">
                <span><i class="line-dot weighted"></i>样本点 S</span>
                <span><i class="line-dot predicted"></i>预测点 Q</span>
                <span>颜色表示数值大小</span>
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
        const heatmapSummary = this.container.querySelector('#dl-spatial-heatmap-summary') as HTMLElement | null;
        const heatmapChart = this.container.querySelector('#dl-spatial-heatmap-chart') as HTMLElement | null;
        const networkSummary = this.container.querySelector('#dl-spatial-network-summary') as HTMLElement | null;
        const networkChart = this.container.querySelector('#dl-spatial-network-chart') as HTMLElement | null;
        const mapSummary = this.container.querySelector('#dl-spatial-map-summary') as HTMLElement | null;
        const mapChart = this.container.querySelector('#dl-spatial-map-chart') as HTMLElement | null;

        if (!errorSummary || !errorChart || !weightSummary || !weightChart || !neighborhoodSummary || !neighborhoodChart || !compareSummary || !compareChart || !heatmapSummary || !heatmapChart || !networkSummary || !networkChart || !mapSummary || !mapChart) {
            return;
        }

        const data = this.visualizationData;
        if (!data || data.rows.length === 0) {
            errorSummary.textContent = I18n.t('interpolation.noData');
            errorChart.innerHTML = '<div class="dl-spatial-empty">' + I18n.t('interpolation.runPredictionFirst') + '</div>';
            weightSummary.textContent = I18n.t('interpolation.noData');
            weightChart.innerHTML = '<div class="dl-spatial-empty">' + I18n.t('interpolation.runPredictionFirst') + '</div>';
            neighborhoodSummary.textContent = I18n.t('interpolation.noData');
            neighborhoodChart.innerHTML = '<div class="dl-spatial-empty">' + I18n.t('interpolation.runPredictionFirst') + '</div>';
            compareSummary.textContent = I18n.t('interpolation.noData');
            compareChart.innerHTML = '<div class="dl-spatial-empty">' + I18n.t('interpolation.runPredictionFirst') + '</div>';
            heatmapSummary.textContent = I18n.t('interpolation.noData');
            heatmapChart.innerHTML = '<div class="dl-spatial-empty">' + I18n.t('interpolation.runPredictionFirst') + '</div>';
            networkSummary.textContent = I18n.t('interpolation.noData');
            networkChart.innerHTML = '<div class="dl-spatial-empty">' + I18n.t('interpolation.runPredictionFirst') + '</div>';
            mapSummary.textContent = I18n.t('interpolation.noData');
            mapChart.innerHTML = '<div class="dl-spatial-empty">' + I18n.t('interpolation.runPredictionFirst') + '</div>';
            this.updateQuerySelector();
            return;
        }

        this.updateQuerySelector();
        const selected = data.rows[Math.max(0, Math.min(data.selectedQueryIndex, data.rows.length - 1))];
        const errors = data.rows.map(row => row.absConsistencyError);

        errorSummary.textContent = I18n.t('interpolation.errorSummary', { mae: data.global.mae.toFixed(4), rmse: data.global.rmse.toFixed(4), maxAbs: data.global.maxAbsError.toFixed(4) });
        errorChart.innerHTML = this.renderBarSeries(errors, 120, 'error');

        weightSummary.textContent = I18n.t('interpolation.dominantNeighborWeight', { weight: data.global.meanDominantWeight.toFixed(4), count: data.weightHistogram.counts.reduce((sum, c) => sum + c, 0) });
        weightChart.innerHTML = this.renderHistogram(data.weightHistogram);

        neighborhoodSummary.textContent = I18n.t('interpolation.pointDetail', { index: selected.queryIndex, x: selected.queryCoord[0].toFixed(3), y: selected.queryCoord[1].toFixed(3), weight: selected.dominantNeighbor.weight.toFixed(4) });
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
        compareSummary.textContent = I18n.t('interpolation.pointPrediction', { index: selected.queryIndex, predicted: selected.predicted.toFixed(4), mean: selected.weightedMean.toFixed(4), nearest: selected.nearestValue.toFixed(4) });
        compareChart.innerHTML = this.buildCompareSvg(data.rows);

        const globalMaxWeight = data.rows.reduce((max, row) => Math.max(max, ...row.allNeighbors.map(item => item.weight)), 0);
        heatmapSummary.textContent = I18n.t('interpolation.querySampleStats', { queryCount: data.rows.length, sampleCount: data.samplePoints.length, maxWeight: globalMaxWeight.toFixed(4) });
        heatmapChart.innerHTML = this.renderWeightHeatmap(data);

        const avgDistance = selected.neighbors.length > 0
            ? selected.neighbors.reduce((sum, item) => sum + item.distance, 0) / selected.neighbors.length
            : 0;
        networkSummary.textContent = I18n.t('interpolation.queryPointNeighborDetail', { index: selected.queryIndex, count: selected.neighbors.length, distance: avgDistance.toFixed(4), weight: selected.dominantNeighbor.weight.toFixed(4) });
        networkChart.innerHTML = this.buildNeighborhoodRelationSvg(selected);

        mapSummary.textContent = I18n.t('interpolation.spatialStats', { sampleCount: data.samplePoints.length, queryCount: data.queryPoints.length, min: data.valueRange.min.toFixed(4), max: data.valueRange.max.toFixed(4) });
        mapChart.innerHTML = this.buildInterpolationMapSvg(data, selected);
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
