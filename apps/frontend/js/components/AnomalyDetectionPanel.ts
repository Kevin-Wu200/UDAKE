import type { IAPIService } from '../../types/api';

type SeverityLevel = 'high' | 'medium' | 'low';
type SeverityFilter = SeverityLevel | 'all';
type CompareModelName = 'vae' | 'gcae' | 'gan' | 'contrastive';
type CompareThresholdMethod = 'percentile' | 'statistical' | 'adaptive';
type CompareFocusMetric = 'coverage' | 'anomaly_rate' | 'avg_score';

interface TimeSeriesPoint {
    index: number;
    value: number;
}

interface AnomalyPoint {
    index: number;
    value: number;
    severity: SeverityLevel;
    zScore: number;
}

interface SlidingWindowSummary {
    start: number;
    end: number;
    mean: number;
    anomalyCount: number;
    anomalyRate: number;
}

interface CompareModelResult {
    model: CompareModelName;
    label: string;
    anomalyIndices: number[];
    anomalyCount: number;
    anomalyRate: number;
    coverage: number;
    avgScore: number;
    scoreStd: number;
    threshold: number | null;
}

interface ComparePairwiseStat {
    left: string;
    right: string;
    jaccard: number;
    overlapCount: number;
}

const COMPARE_MODEL_OPTIONS: Array<{ value: CompareModelName; label: string }> = [
    { value: 'vae', label: 'VAE' },
    { value: 'gcae', label: 'GCAE' },
    { value: 'gan', label: 'GAN' },
    { value: 'contrastive', label: 'Contrastive' }
];

/**
 * 异常检测子面板
 */
export class AnomalyDetectionPanel {
    private container: HTMLElement;
    private apiService: IAPIService;
    private lastResult: unknown = null;
    private seriesCache: TimeSeriesPoint[] = [];
    private anomalyCache: AnomalyPoint[] = [];
    private selectedSeverityFilter: SeverityFilter = 'all';

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
                    <h4>异常检测</h4>
                    <p>检测采样数据中的异常点</p>
                </div>

                <div class="dl-form-grid">
                    <label class="dl-field">
                        <span>模型类型</span>
                        <select id="dl-anomaly-model" class="select">
                            <option value="vae">VAE</option>
                            <option value="gcae">GCAE</option>
                            <option value="gan">GAN</option>
                            <option value="contrastive">Contrastive</option>
                            <option value="fusion">Fusion(仅预测)</option>
                        </select>
                    </label>
                    <label class="dl-field">
                        <span>阈值方法</span>
                        <select id="dl-anomaly-threshold" class="select">
                            <option value="percentile">Percentile</option>
                            <option value="statistical">Statistical</option>
                            <option value="adaptive">Adaptive</option>
                        </select>
                    </label>
                    <label class="dl-field">
                        <span>训练轮数</span>
                        <input id="dl-anomaly-epochs" class="input" type="number" min="1" max="300" value="30">
                    </label>
                    <label class="dl-field">
                        <span>Percentile</span>
                        <input id="dl-anomaly-percentile" class="input" type="number" min="50" max="99.9" step="0.1" value="95">
                    </label>
                    <label class="dl-field">
                        <span>k 值</span>
                        <input id="dl-anomaly-k" class="input" type="number" min="1" max="6" step="0.1" value="2.5">
                    </label>
                </div>

                <label class="dl-field dl-field-full">
                    <span>坐标 coords（JSON）</span>
                    <textarea id="dl-anomaly-coords" class="dl-textarea" rows="4">[[0,0],[1,0],[0,1],[1,1],[0.6,0.4],[0.2,0.8]]</textarea>
                </label>

                <label class="dl-field dl-field-full">
                    <span>数值 values（JSON）</span>
                    <textarea id="dl-anomaly-values" class="dl-textarea" rows="3">[1.1,1.2,1.0,8.8,1.3,1.05]</textarea>
                </label>

                <div class="dl-actions">
                    <button id="dl-anomaly-train" class="btn btn-primary">训练模型</button>
                    <button id="dl-anomaly-predict" class="btn btn-secondary">执行检测</button>
                    <button id="dl-anomaly-export" class="btn btn-export">导出结果</button>
                </div>

                <div id="dl-anomaly-status" class="status-message"></div>
                <pre id="dl-anomaly-result" class="dl-result">暂无结果</pre>

                <section class="dl-timeseries-card">
                    <div class="dl-timeseries-header">
                        <h5>时间序列异常标记</h5>
                        <p>支持异常点标记、异常区域高亮、滑动窗口分析、趋势线与异常预测展示</p>
                    </div>
                    <div class="dl-timeseries-controls">
                        <label class="dl-field">
                            <span>分析数据源</span>
                            <select id="dl-anomaly-series-source" class="select">
                                <option value="values">原始值</option>
                                <option value="scores">异常分数</option>
                            </select>
                        </label>
                        <label class="dl-field">
                            <span>滑动窗口</span>
                            <input id="dl-anomaly-window-size" class="input" type="number" min="2" max="32" value="4">
                        </label>
                        <label class="dl-field">
                            <span>趋势线模式</span>
                            <select id="dl-anomaly-trend-mode" class="select">
                                <option value="linear">线性回归</option>
                                <option value="moving_avg">移动平均</option>
                            </select>
                        </label>
                        <label class="dl-field">
                            <span>预测步长</span>
                            <input id="dl-anomaly-forecast-horizon" class="input" type="number" min="1" max="24" value="6">
                        </label>
                        <label class="dl-field">
                            <span>严重级别筛选</span>
                            <select id="dl-anomaly-severity-filter" class="select">
                                <option value="all">全部</option>
                                <option value="high">高风险</option>
                                <option value="medium">中风险</option>
                                <option value="low">低风险</option>
                            </select>
                        </label>
                    </div>
                    <div class="dl-actions">
                        <button id="dl-anomaly-refresh-timeseries" class="btn btn-secondary">刷新时间序列可视化</button>
                    </div>
                    <div id="dl-anomaly-timeseries-summary" class="dl-timeseries-summary">请先执行检测后查看时间序列异常标记。</div>
                    <div id="dl-anomaly-timeseries-legend" class="dl-timeseries-legend" aria-label="时间序列图例"></div>
                    <div id="dl-anomaly-timeseries" class="dl-timeseries-chart" aria-label="时间序列异常可视化"></div>
                    <div id="dl-anomaly-window-analysis" class="dl-window-analysis"></div>
                </section>

                <section class="dl-compare-card">
                    <div class="dl-timeseries-header">
                        <h5>异常检测结果对比</h5>
                        <p>支持多模型对比、性能指标对比、一致性分析与自定义对比配置</p>
                    </div>
                    <div class="dl-compare-controls">
                        <label class="dl-field">
                            <span>阈值方法</span>
                            <select id="dl-anomaly-compare-threshold" class="select">
                                <option value="percentile">Percentile</option>
                                <option value="statistical">Statistical</option>
                                <option value="adaptive">Adaptive</option>
                            </select>
                        </label>
                        <label class="dl-field">
                            <span>Percentile</span>
                            <input id="dl-anomaly-compare-percentile" class="input" type="number" min="50" max="99.9" step="0.1" value="95">
                        </label>
                        <label class="dl-field">
                            <span>k 值</span>
                            <input id="dl-anomaly-compare-k" class="input" type="number" min="1" max="6" step="0.1" value="2.5">
                        </label>
                        <label class="dl-field">
                            <span>一致性最小模型数</span>
                            <input id="dl-anomaly-compare-consensus-min" class="input" type="number" min="2" max="4" value="2">
                        </label>
                        <label class="dl-field">
                            <span>参考模型</span>
                            <select id="dl-anomaly-compare-reference" class="select">
                                <option value="vae">VAE</option>
                                <option value="gcae">GCAE</option>
                                <option value="gan">GAN</option>
                                <option value="contrastive">Contrastive</option>
                            </select>
                        </label>
                        <label class="dl-field">
                            <span>重点指标</span>
                            <select id="dl-anomaly-compare-focus" class="select">
                                <option value="coverage">覆盖率</option>
                                <option value="anomaly_rate">异常率</option>
                                <option value="avg_score">平均异常分数</option>
                            </select>
                        </label>
                    </div>
                    <div class="dl-compare-model-picker" id="dl-anomaly-compare-model-picker" aria-label="模型选择器">
                        ${COMPARE_MODEL_OPTIONS.map(
                            (item, index) => `
                            <label class="compare-model-chip">
                                <input class="compare-model-checkbox" type="checkbox" value="${item.value}" ${index < 3 ? 'checked' : ''}>
                                <span>${item.label}</span>
                            </label>
                        `
                        ).join('')}
                    </div>
                    <div class="dl-actions">
                        <button id="dl-anomaly-compare-select-all" class="btn btn-secondary">全选模型</button>
                        <button id="dl-anomaly-compare-clear" class="btn btn-secondary">清空选择</button>
                        <button id="dl-anomaly-run-compare" class="btn btn-primary">运行结果对比</button>
                    </div>
                    <div id="dl-anomaly-compare-summary" class="dl-compare-summary">请选择至少两个模型并运行对比。</div>
                    <div id="dl-anomaly-compare-metrics" class="dl-compare-metrics"></div>
                    <div id="dl-anomaly-compare-consistency" class="dl-compare-consistency"></div>
                    <div id="dl-anomaly-compare-table" class="dl-compare-table-wrap"></div>
                </section>
            </div>
        `;
    }

    private bindEvents(): void {
        this.container.querySelector('#dl-anomaly-train')?.addEventListener('click', () => {
            void this.handleTrain();
        });

        this.container.querySelector('#dl-anomaly-predict')?.addEventListener('click', () => {
            void this.handlePredict();
        });

        this.container.querySelector('#dl-anomaly-export')?.addEventListener('click', () => {
            this.exportResult();
        });

        this.container.querySelector('#dl-anomaly-refresh-timeseries')?.addEventListener('click', () => {
            this.renderTimeSeriesVisualization();
        });

        this.container.querySelector('#dl-anomaly-severity-filter')?.addEventListener('change', (event: Event) => {
            const target = event.target as HTMLSelectElement | null;
            const value = target?.value || 'all';
            if (value === 'high' || value === 'medium' || value === 'low') {
                this.selectedSeverityFilter = value;
            } else {
                this.selectedSeverityFilter = 'all';
            }
            this.renderTimeSeriesVisualization();
        });

        this.container.querySelector('#dl-anomaly-run-compare')?.addEventListener('click', () => {
            void this.runCompareAnalysis();
        });

        this.container.querySelector('#dl-anomaly-compare-select-all')?.addEventListener('click', () => {
            this.toggleCompareModelSelection(true);
        });

        this.container.querySelector('#dl-anomaly-compare-clear')?.addEventListener('click', () => {
            this.toggleCompareModelSelection(false);
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
        const status = this.container.querySelector('#dl-anomaly-status') as HTMLElement | null;
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
        const result = this.container.querySelector('#dl-anomaly-result') as HTMLElement | null;
        if (!result) {
            return;
        }
        result.textContent = JSON.stringify(data, null, 2);
    }

    private getModelName(): 'vae' | 'gcae' | 'gan' | 'contrastive' | 'fusion' {
        const model = (this.container.querySelector('#dl-anomaly-model') as HTMLSelectElement | null)?.value || 'vae';
        if (model === 'gcae' || model === 'gan' || model === 'contrastive' || model === 'fusion') {
            return model;
        }
        return 'vae';
    }

    private async handleTrain(): Promise<void> {
        try {
            const modelName = this.getModelName();
            if (modelName === 'fusion') {
                throw new Error('Fusion 模式仅支持预测，不支持训练');
            }

            this.setStatus('正在训练异常检测模型...', 'loading');
            const epochs = Number((this.container.querySelector('#dl-anomaly-epochs') as HTMLInputElement | null)?.value || 30);
            const coords = this.parseJson<Array<[number, number]>>('dl-anomaly-coords', 'coords');
            const values = this.parseJson<number[]>('dl-anomaly-values', 'values');

            const response = await this.apiService.trainAnomaly({
                model_name: modelName,
                coords,
                values,
                epochs
            });

            this.lastResult = response;
            this.setResult(response);
            this.setStatus('异常检测模型训练完成', 'success');
            this.renderTimeSeriesVisualization();
        } catch (error) {
            this.setStatus(`训练失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private async handlePredict(): Promise<void> {
        try {
            this.setStatus('正在执行异常检测...', 'loading');
            const modelName = this.getModelName();
            const thresholdMethod = (this.container.querySelector('#dl-anomaly-threshold') as HTMLSelectElement | null)?.value || 'percentile';
            const percentile = Number((this.container.querySelector('#dl-anomaly-percentile') as HTMLInputElement | null)?.value || 95);
            const k = Number((this.container.querySelector('#dl-anomaly-k') as HTMLInputElement | null)?.value || 2.5);
            const coords = this.parseJson<Array<[number, number]>>('dl-anomaly-coords', 'coords');
            const values = this.parseJson<number[]>('dl-anomaly-values', 'values');

            const response = await this.apiService.predictAnomaly({
                model_name: modelName,
                coords,
                values,
                threshold_method: thresholdMethod as 'statistical' | 'percentile' | 'adaptive',
                percentile,
                k
            });

            this.lastResult = response;
            this.setResult(response);
            this.setStatus('异常检测完成', 'success');
            this.renderTimeSeriesVisualization();
        } catch (error) {
            this.setStatus(`检测失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private renderTimeSeriesVisualization(): void {
        const host = this.container.querySelector('#dl-anomaly-timeseries') as HTMLElement | null;
        const legend = this.container.querySelector('#dl-anomaly-timeseries-legend') as HTMLElement | null;
        const summary = this.container.querySelector('#dl-anomaly-timeseries-summary') as HTMLElement | null;
        const windowHost = this.container.querySelector('#dl-anomaly-window-analysis') as HTMLElement | null;
        if (!host || !legend || !summary || !windowHost) {
            return;
        }

        const dataSource = (this.container.querySelector('#dl-anomaly-series-source') as HTMLSelectElement | null)?.value || 'values';
        const windowSize = this.getNumberInputValue('dl-anomaly-window-size', 4, 2, 32);
        const trendMode = (this.container.querySelector('#dl-anomaly-trend-mode') as HTMLSelectElement | null)?.value || 'linear';
        const horizon = this.getNumberInputValue('dl-anomaly-forecast-horizon', 6, 1, 24);

        const series = this.extractSeriesData(dataSource);
        this.seriesCache = series;
        if (series.length < 2) {
            host.innerHTML = '<div class="status-message">暂无可用于时间序列可视化的数据</div>';
            legend.innerHTML = '';
            summary.textContent = '请先执行检测，或检查输入 values 是否为有效数值数组。';
            windowHost.innerHTML = '';
            return;
        }

        const anomalies = this.extractAnomalyPoints(series);
        this.anomalyCache = anomalies;
        const filteredAnomalies = this.filterAnomaliesBySeverity(anomalies, this.selectedSeverityFilter);
        const anomalySet = new Set<number>(filteredAnomalies.map((item) => item.index));
        const regions = this.buildAnomalyRegions(filteredAnomalies);
        const trendLine = trendMode === 'moving_avg' ? this.computeMovingAverage(series, windowSize) : this.computeLinearTrend(series);
        const forecast = this.computeForecast(series, horizon);
        const windows = this.computeSlidingWindows(series, anomalySet, windowSize);

        host.innerHTML = this.renderSeriesSvg(series, trendLine, forecast, filteredAnomalies, regions);
        legend.innerHTML = this.renderLegend(filteredAnomalies, trendMode, dataSource);
        summary.textContent = this.buildSummaryText(series, filteredAnomalies, windowSize, horizon, dataSource, trendMode);
        windowHost.innerHTML = this.renderWindowAnalysis(windows, windowSize);
    }

    private getNumberInputValue(inputId: string, fallback: number, min: number, max: number): number {
        const raw = Number((this.container.querySelector(`#${inputId}`) as HTMLInputElement | null)?.value || fallback);
        if (!Number.isFinite(raw)) {
            return fallback;
        }
        return Math.min(max, Math.max(min, Math.round(raw)));
    }

    private extractSeriesData(source: string): TimeSeriesPoint[] {
        let values: number[] = [];
        if (source === 'scores') {
            const result = this.lastResult as Record<string, unknown> | null;
            const maybeScores = result ? result.anomaly_scores : null;
            if (Array.isArray(maybeScores)) {
                values = maybeScores
                    .map((item) => Number(item))
                    .filter((item) => Number.isFinite(item));
            }
        }

        if (values.length === 0) {
            try {
                const inputValues = this.parseJson<unknown[]>('dl-anomaly-values', 'values');
                values = inputValues
                    .map((item) => Number(item))
                    .filter((item) => Number.isFinite(item));
            } catch {
                values = [];
            }
        }

        return values.map((value, index) => ({ index, value }));
    }

    private extractAnomalyPoints(series: TimeSeriesPoint[]): AnomalyPoint[] {
        const result = this.lastResult as Record<string, unknown> | null;
        const stdInfo = this.computeStats(series.map((item) => item.value));
        const indexSet = new Set<number>();

        if (result) {
            if (Array.isArray(result.anomaly_indices)) {
                result.anomaly_indices.forEach((value) => {
                    const index = Number(value);
                    if (Number.isInteger(index) && index >= 0 && index < series.length) {
                        indexSet.add(index);
                    }
                });
            }

            const valueAnomalies = (result.value_anomalies || {}) as Record<string, unknown>;
            const anomalyList = valueAnomalies.anomalies;
            if (Array.isArray(anomalyList)) {
                anomalyList.forEach((item) => {
                    if (!item || typeof item !== 'object') {
                        return;
                    }
                    const index = Number((item as Record<string, unknown>).index);
                    if (Number.isInteger(index) && index >= 0 && index < series.length) {
                        indexSet.add(index);
                    }
                });
            }
        }

        if (indexSet.size === 0) {
            const threshold = stdInfo.mean + stdInfo.std * 1.8;
            series.forEach((point) => {
                if (Math.abs(point.value - stdInfo.mean) >= Math.abs(threshold - stdInfo.mean)) {
                    indexSet.add(point.index);
                }
            });
        }

        return Array.from(indexSet)
            .sort((a, b) => a - b)
            .map((index) => {
                const point = series[index];
                const zScore = stdInfo.std > 0 ? (point.value - stdInfo.mean) / stdInfo.std : 0;
                return {
                    index,
                    value: point.value,
                    zScore,
                    severity: this.classifySeverity(Math.abs(zScore))
                };
            });
    }

    private classifySeverity(absZScore: number): SeverityLevel {
        if (absZScore >= 2.5) {
            return 'high';
        }
        if (absZScore >= 1.5) {
            return 'medium';
        }
        return 'low';
    }

    private filterAnomaliesBySeverity(anomalies: AnomalyPoint[], filter: SeverityFilter): AnomalyPoint[] {
        if (filter === 'all') {
            return anomalies;
        }
        return anomalies.filter((item) => item.severity === filter);
    }

    private buildAnomalyRegions(anomalies: AnomalyPoint[]): Array<{ start: number; end: number }> {
        if (anomalies.length === 0) {
            return [];
        }
        const sorted = anomalies.map((item) => item.index).sort((a, b) => a - b);
        const regions: Array<{ start: number; end: number }> = [];
        let start = sorted[0];
        let prev = sorted[0];

        for (let i = 1; i < sorted.length; i++) {
            const current = sorted[i];
            if (current - prev <= 1) {
                prev = current;
                continue;
            }
            regions.push({ start, end: prev });
            start = current;
            prev = current;
        }
        regions.push({ start, end: prev });
        return regions;
    }

    private computeMovingAverage(series: TimeSeriesPoint[], windowSize: number): Array<number | null> {
        const trend: Array<number | null> = [];
        for (let i = 0; i < series.length; i++) {
            const start = Math.max(0, i - windowSize + 1);
            const segment = series.slice(start, i + 1).map((item) => item.value);
            trend.push(segment.reduce((sum, value) => sum + value, 0) / segment.length);
        }
        return trend;
    }

    private computeLinearTrend(series: TimeSeriesPoint[]): Array<number | null> {
        const n = series.length;
        const sumX = series.reduce((sum, item) => sum + item.index, 0);
        const sumY = series.reduce((sum, item) => sum + item.value, 0);
        const sumXY = series.reduce((sum, item) => sum + item.index * item.value, 0);
        const sumXX = series.reduce((sum, item) => sum + item.index * item.index, 0);
        const denominator = n * sumXX - sumX * sumX;
        const slope = denominator === 0 ? 0 : (n * sumXY - sumX * sumY) / denominator;
        const intercept = (sumY - slope * sumX) / Math.max(1, n);
        return series.map((item) => intercept + slope * item.index);
    }

    private computeForecast(series: TimeSeriesPoint[], horizon: number): TimeSeriesPoint[] {
        const trend = this.computeLinearTrend(series);
        const tailValues = trend.filter((item): item is number => typeof item === 'number');
        if (tailValues.length < 2) {
            return [];
        }
        const last = tailValues[tailValues.length - 1];
        const prev = tailValues[tailValues.length - 2];
        const step = last - prev;
        const startIndex = series.length;
        const points: TimeSeriesPoint[] = [];
        for (let i = 0; i < horizon; i++) {
            points.push({
                index: startIndex + i,
                value: last + step * (i + 1)
            });
        }
        return points;
    }

    private computeSlidingWindows(series: TimeSeriesPoint[], anomalySet: Set<number>, windowSize: number): SlidingWindowSummary[] {
        const summaries: SlidingWindowSummary[] = [];
        if (series.length === 0) {
            return summaries;
        }
        for (let start = 0; start < series.length; start += 1) {
            const end = Math.min(series.length - 1, start + windowSize - 1);
            if (end - start + 1 < windowSize && start > 0) {
                break;
            }
            const segment = series.slice(start, end + 1);
            const anomalyCount = segment.reduce((count, item) => count + (anomalySet.has(item.index) ? 1 : 0), 0);
            summaries.push({
                start,
                end,
                mean: segment.reduce((sum, item) => sum + item.value, 0) / Math.max(1, segment.length),
                anomalyCount,
                anomalyRate: anomalyCount / Math.max(1, segment.length)
            });
        }
        return summaries.slice(0, 8);
    }

    private renderSeriesSvg(
        series: TimeSeriesPoint[],
        trend: Array<number | null>,
        forecast: TimeSeriesPoint[],
        anomalies: AnomalyPoint[],
        regions: Array<{ start: number; end: number }>
    ): string {
        const width = 920;
        const height = 260;
        const padding = { top: 12, right: 20, bottom: 26, left: 36 };
        const allSeriesValues = series.map((item) => item.value);
        const allForecastValues = forecast.map((item) => item.value);
        const allValues = [...allSeriesValues, ...allForecastValues];
        const minValue = Math.min(...allValues);
        const maxValue = Math.max(...allValues);
        const valueRange = maxValue - minValue || 1;
        const maxIndex = Math.max(series.length - 1, forecast.length > 0 ? forecast[forecast.length - 1].index : series.length - 1, 1);
        const plotWidth = width - padding.left - padding.right;
        const plotHeight = height - padding.top - padding.bottom;
        const scaleX = (index: number): number => padding.left + (index / maxIndex) * plotWidth;
        const scaleY = (value: number): number => padding.top + (1 - (value - minValue) / valueRange) * plotHeight;

        const linePath = this.buildSvgPath(series, scaleX, scaleY);
        const trendPath = this.buildSvgPathFromValues(trend, scaleX, scaleY);
        const forecastPath = this.buildSvgPath(forecast, scaleX, scaleY);
        const regionRects = regions
            .map((region) => {
                const x1 = scaleX(region.start);
                const x2 = scaleX(region.end + 0.85);
                return `<rect x="${x1.toFixed(2)}" y="${padding.top}" width="${Math.max(4, x2 - x1).toFixed(2)}" height="${plotHeight}" class="series-anomaly-region"></rect>`;
            })
            .join('');

        const anomalyMarks = anomalies
            .map((item) => {
                const cx = scaleX(item.index).toFixed(2);
                const cy = scaleY(item.value).toFixed(2);
                return `<circle cx="${cx}" cy="${cy}" r="4.4" class="series-anomaly-point ${this.getSeverityClass(item.severity)}"><title>t${item.index}: ${item.value.toFixed(4)} (${item.severity})</title></circle>`;
            })
            .join('');

        const forecastMarks = forecast
            .map((item) => `<circle cx="${scaleX(item.index).toFixed(2)}" cy="${scaleY(item.value).toFixed(2)}" r="3.2" class="series-forecast-point"></circle>`)
            .join('');

        return `
            <svg class="series-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="时间序列异常图">
                ${regionRects}
                <line x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}" class="series-axis"></line>
                <line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${height - padding.bottom}" class="series-axis"></line>
                <path d="${linePath}" class="series-line"></path>
                <path d="${trendPath}" class="series-trend-line"></path>
                <path d="${forecastPath}" class="series-forecast-line"></path>
                ${forecastMarks}
                ${anomalyMarks}
                <text x="${padding.left}" y="${padding.top - 2}" class="series-label">max ${maxValue.toFixed(3)}</text>
                <text x="${padding.left}" y="${height - 6}" class="series-label">min ${minValue.toFixed(3)}</text>
            </svg>
        `;
    }

    private buildSvgPath(points: TimeSeriesPoint[], scaleX: (index: number) => number, scaleY: (value: number) => number): string {
        if (points.length === 0) {
            return '';
        }
        return points
            .map((point, index) => `${index === 0 ? 'M' : 'L'}${scaleX(point.index).toFixed(2)},${scaleY(point.value).toFixed(2)}`)
            .join(' ');
    }

    private buildSvgPathFromValues(values: Array<number | null>, scaleX: (index: number) => number, scaleY: (value: number) => number): string {
        let path = '';
        let open = false;
        values.forEach((value, index) => {
            if (typeof value !== 'number') {
                open = false;
                return;
            }
            const cmd = open ? 'L' : 'M';
            path += `${cmd}${scaleX(index).toFixed(2)},${scaleY(value).toFixed(2)} `;
            open = true;
        });
        return path.trim();
    }

    private renderLegend(anomalies: AnomalyPoint[], trendMode: string, source: string): string {
        const high = anomalies.filter((item) => item.severity === 'high').length;
        const medium = anomalies.filter((item) => item.severity === 'medium').length;
        const low = anomalies.filter((item) => item.severity === 'low').length;
        const sourceLabel = source === 'scores' ? '异常分数序列' : '原始值序列';
        const trendLabel = trendMode === 'moving_avg' ? '移动平均趋势线' : '线性回归趋势线';

        return `
            <span class="legend-item"><i class="legend-swatch series-base"></i>${sourceLabel}</span>
            <span class="legend-item"><i class="legend-swatch series-trend"></i>${trendLabel}</span>
            <span class="legend-item"><i class="legend-swatch series-forecast"></i>异常预测</span>
            <span class="legend-item"><i class="legend-swatch severity-high"></i>高风险 ${high}</span>
            <span class="legend-item"><i class="legend-swatch severity-medium"></i>中风险 ${medium}</span>
            <span class="legend-item"><i class="legend-swatch severity-low"></i>低风险 ${low}</span>
        `;
    }

    private buildSummaryText(
        series: TimeSeriesPoint[],
        anomalies: AnomalyPoint[],
        windowSize: number,
        horizon: number,
        source: string,
        trendMode: string
    ): string {
        const ratio = (anomalies.length / Math.max(1, series.length)) * 100;
        const trendLabel = trendMode === 'moving_avg' ? '移动平均趋势' : '线性回归趋势';
        const sourceLabel = source === 'scores' ? '异常分数序列' : '原始值序列';
        return `共 ${series.length} 个时序点，筛选后异常点 ${anomalies.length} 个（${ratio.toFixed(2)}%）。当前模式：${sourceLabel} + ${trendLabel}，滑动窗口 ${windowSize}，预测未来 ${horizon} 步。`;
    }

    private renderWindowAnalysis(windows: SlidingWindowSummary[], windowSize: number): string {
        if (windows.length === 0) {
            return '<div class="status-message">暂无滑动窗口统计</div>';
        }
        const rows = windows
            .map((item) => {
                const tone = item.anomalyRate >= 0.5 ? 'high' : item.anomalyRate >= 0.25 ? 'medium' : 'low';
                return `
                    <tr>
                        <td>[${item.start}-${item.end}]</td>
                        <td>${item.mean.toFixed(4)}</td>
                        <td>${item.anomalyCount}</td>
                        <td><span class="window-rate ${tone}">${(item.anomalyRate * 100).toFixed(1)}%</span></td>
                    </tr>
                `;
            })
            .join('');

        return `
            <div class="dl-window-analysis-title">滑动窗口分析（窗口长度 ${windowSize}）</div>
            <table class="dl-window-analysis-table">
                <thead>
                    <tr>
                        <th>窗口</th>
                        <th>均值</th>
                        <th>异常数</th>
                        <th>异常占比</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `;
    }

    private computeStats(values: number[]): { mean: number; std: number } {
        const mean = values.reduce((sum, value) => sum + value, 0) / Math.max(1, values.length);
        const variance = values.reduce((sum, value) => sum + Math.pow(value - mean, 2), 0) / Math.max(1, values.length);
        return { mean, std: Math.sqrt(variance) };
    }

    private getSeverityClass(level: SeverityLevel): string {
        if (level === 'high') {
            return 'severity-high';
        }
        if (level === 'medium') {
            return 'severity-medium';
        }
        return 'severity-low';
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
        link.download = `anomaly-result-${Date.now()}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        this.setStatus('结果导出成功', 'success');
    }

    private toggleCompareModelSelection(checked: boolean): void {
        this.container.querySelectorAll('.compare-model-checkbox').forEach((node) => {
            const checkbox = node as HTMLInputElement;
            checkbox.checked = checked;
        });
    }

    private getSelectedCompareModels(): CompareModelName[] {
        const selected: CompareModelName[] = [];
        this.container.querySelectorAll('.compare-model-checkbox').forEach((node) => {
            const checkbox = node as HTMLInputElement;
            if (!checkbox.checked) {
                return;
            }
            const value = checkbox.value;
            if (value === 'vae' || value === 'gcae' || value === 'gan' || value === 'contrastive') {
                selected.push(value);
            }
        });
        return selected;
    }

    private getCompareThresholdMethod(): CompareThresholdMethod {
        const raw = (this.container.querySelector('#dl-anomaly-compare-threshold') as HTMLSelectElement | null)?.value;
        if (raw === 'statistical' || raw === 'adaptive') {
            return raw;
        }
        return 'percentile';
    }

    private getCompareFocusMetric(): CompareFocusMetric {
        const raw = (this.container.querySelector('#dl-anomaly-compare-focus') as HTMLSelectElement | null)?.value;
        if (raw === 'anomaly_rate' || raw === 'avg_score') {
            return raw;
        }
        return 'coverage';
    }

    private getCompareLabel(model: CompareModelName): string {
        const match = COMPARE_MODEL_OPTIONS.find((item) => item.value === model);
        return match ? match.label : model.toUpperCase();
    }

    private extractAnomalyIndicesFromResult(result: Record<string, unknown>, limit: number): number[] {
        const indexSet = new Set<number>();
        if (Array.isArray(result.anomaly_indices)) {
            result.anomaly_indices.forEach((item) => {
                const idx = Number(item);
                if (Number.isInteger(idx) && idx >= 0 && idx < limit) {
                    indexSet.add(idx);
                }
            });
        }

        const valueAnomalies = (result.value_anomalies || {}) as Record<string, unknown>;
        if (Array.isArray(valueAnomalies.anomalies)) {
            valueAnomalies.anomalies.forEach((item) => {
                if (!item || typeof item !== 'object') {
                    return;
                }
                const idx = Number((item as Record<string, unknown>).index);
                if (Number.isInteger(idx) && idx >= 0 && idx < limit) {
                    indexSet.add(idx);
                }
            });
        }

        return Array.from(indexSet).sort((a, b) => a - b);
    }

    private estimateThreshold(scores: number[], method: CompareThresholdMethod, percentile: number, k: number): number | null {
        if (scores.length === 0) {
            return null;
        }
        const stats = this.computeStats(scores);
        if (method === 'statistical') {
            return stats.mean + stats.std * k;
        }
        if (method === 'adaptive') {
            const sorted = [...scores].sort((a, b) => a - b);
            const q1 = sorted[Math.max(0, Math.floor(sorted.length * 0.25) - 1)] ?? sorted[0];
            const q3 = sorted[Math.max(0, Math.floor(sorted.length * 0.75) - 1)] ?? sorted[sorted.length - 1];
            return q3 + 0.5 * (q3 - q1);
        }
        const sorted = [...scores].sort((a, b) => a - b);
        const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((percentile / 100) * sorted.length) - 1));
        return sorted[index];
    }

    private buildPairwiseStats(rows: CompareModelResult[]): ComparePairwiseStat[] {
        const output: ComparePairwiseStat[] = [];
        for (let i = 0; i < rows.length; i++) {
            for (let j = i + 1; j < rows.length; j++) {
                const leftSet = new Set<number>(rows[i].anomalyIndices);
                const rightSet = new Set<number>(rows[j].anomalyIndices);
                const intersection = rows[i].anomalyIndices.filter((item) => rightSet.has(item));
                const union = new Set<number>([...leftSet, ...rightSet]);
                output.push({
                    left: rows[i].label,
                    right: rows[j].label,
                    overlapCount: intersection.length,
                    jaccard: union.size > 0 ? intersection.length / union.size : 0
                });
            }
        }
        return output;
    }

    private renderCompareTable(rows: CompareModelResult[]): string {
        if (rows.length === 0) {
            return '<div class="status-message">暂无可展示的模型对比结果</div>';
        }
        const body = rows
            .map((item) => {
                const thresholdLabel = typeof item.threshold === 'number' ? item.threshold.toFixed(4) : '-';
                return `
                    <tr>
                        <td>${item.label}</td>
                        <td>${item.anomalyCount}</td>
                        <td>${(item.anomalyRate * 100).toFixed(2)}%</td>
                        <td>${(item.coverage * 100).toFixed(2)}%</td>
                        <td>${item.avgScore.toFixed(4)}</td>
                        <td>${item.scoreStd.toFixed(4)}</td>
                        <td>${thresholdLabel}</td>
                        <td>${item.anomalyIndices.slice(0, 10).join(', ') || '-'}</td>
                    </tr>
                `;
            })
            .join('');

        return `
            <table class="dl-compare-table">
                <thead>
                    <tr>
                        <th>模型</th>
                        <th>异常数</th>
                        <th>异常率</th>
                        <th>覆盖率</th>
                        <th>平均分</th>
                        <th>分数标准差</th>
                        <th>阈值估计</th>
                        <th>异常索引样本</th>
                    </tr>
                </thead>
                <tbody>${body}</tbody>
            </table>
        `;
    }

    private renderCompareMetrics(rows: CompareModelResult[], focusMetric: CompareFocusMetric): string {
        if (rows.length === 0) {
            return '';
        }
        const union = new Set<number>();
        rows.forEach((item) => item.anomalyIndices.forEach((idx) => union.add(idx)));
        const best = [...rows].sort((a, b) => {
            if (focusMetric === 'avg_score') {
                return b.avgScore - a.avgScore;
            }
            if (focusMetric === 'anomaly_rate') {
                return b.anomalyRate - a.anomalyRate;
            }
            return b.coverage - a.coverage;
        })[0];
        const metricLabel = focusMetric === 'avg_score' ? '平均异常分数' : focusMetric === 'anomaly_rate' ? '异常率' : '覆盖率';
        const avgRate = rows.reduce((sum, item) => sum + item.anomalyRate, 0) / rows.length;

        return `
            <div class="compare-metric-card">
                <div class="compare-metric-key">优选模型（按${metricLabel}）</div>
                <div class="compare-metric-value">${best.label}</div>
            </div>
            <div class="compare-metric-card">
                <div class="compare-metric-key">并集异常点</div>
                <div class="compare-metric-value">${union.size}</div>
            </div>
            <div class="compare-metric-card">
                <div class="compare-metric-key">平均异常率</div>
                <div class="compare-metric-value">${(avgRate * 100).toFixed(2)}%</div>
            </div>
        `;
    }

    private renderConsistency(
        rows: CompareModelResult[],
        pairwise: ComparePairwiseStat[],
        consensusMin: number,
        referenceModel: CompareModelName
    ): string {
        if (rows.length < 2) {
            return '<div class="status-message">至少两个模型才能进行一致性分析</div>';
        }
        const occurrence = new Map<number, number>();
        rows.forEach((item) => {
            item.anomalyIndices.forEach((idx) => {
                occurrence.set(idx, (occurrence.get(idx) || 0) + 1);
            });
        });
        const consensusCount = Array.from(occurrence.values()).filter((count) => count >= consensusMin).length;
        const conflictCount = Array.from(occurrence.values()).filter((count) => count === 1).length;
        const avgJaccard = pairwise.length > 0 ? pairwise.reduce((sum, item) => sum + item.jaccard, 0) / pairwise.length : 0;

        const fallbackRef = rows[0].model;
        const targetRef = rows.some((item) => item.model === referenceModel) ? referenceModel : fallbackRef;
        const refRow = rows.find((item) => item.model === targetRef) as CompareModelResult;
        const refSet = new Set<number>(refRow.anomalyIndices);
        const agreementRows = rows
            .filter((item) => item.model !== targetRef)
            .map((item) => {
                const matched = item.anomalyIndices.filter((idx) => refSet.has(idx)).length;
                const base = Math.max(1, new Set<number>([...item.anomalyIndices, ...refRow.anomalyIndices]).size);
                const ratio = matched / base;
                return `<span class="compare-agree-chip">${item.label} vs ${refRow.label}: ${(ratio * 100).toFixed(1)}%</span>`;
            })
            .join('');

        const pairwiseRows = pairwise
            .map((item) => `<tr><td>${item.left} ↔ ${item.right}</td><td>${item.overlapCount}</td><td>${(item.jaccard * 100).toFixed(2)}%</td></tr>`)
            .join('');

        return `
            <div class="compare-consistency-overview">
                <span class="compare-agree-chip">一致异常点（≥${consensusMin} 模型）：${consensusCount}</span>
                <span class="compare-agree-chip">分歧点（仅单模型命中）：${conflictCount}</span>
                <span class="compare-agree-chip">平均Jaccard：${(avgJaccard * 100).toFixed(2)}%</span>
                <span class="compare-agree-chip">参考模型：${refRow.label}</span>
                ${agreementRows}
            </div>
            <table class="dl-compare-table compare-pairwise-table">
                <thead>
                    <tr>
                        <th>模型对</th>
                        <th>重叠异常点</th>
                        <th>Jaccard</th>
                    </tr>
                </thead>
                <tbody>${pairwiseRows}</tbody>
            </table>
        `;
    }

    private async runCompareAnalysis(): Promise<void> {
        const summary = this.container.querySelector('#dl-anomaly-compare-summary') as HTMLElement | null;
        const metricsHost = this.container.querySelector('#dl-anomaly-compare-metrics') as HTMLElement | null;
        const consistencyHost = this.container.querySelector('#dl-anomaly-compare-consistency') as HTMLElement | null;
        const tableHost = this.container.querySelector('#dl-anomaly-compare-table') as HTMLElement | null;
        if (!summary || !metricsHost || !consistencyHost || !tableHost) {
            return;
        }

        try {
            const selectedModels = this.getSelectedCompareModels();
            if (selectedModels.length < 2) {
                summary.textContent = '请至少选择两个模型后再运行对比。';
                metricsHost.innerHTML = '';
                consistencyHost.innerHTML = '';
                tableHost.innerHTML = '';
                return;
            }

            const coords = this.parseJson<Array<[number, number]>>('dl-anomaly-coords', 'coords');
            const values = this.parseJson<number[]>('dl-anomaly-values', 'values');
            const thresholdMethod = this.getCompareThresholdMethod();
            const percentile = Number((this.container.querySelector('#dl-anomaly-compare-percentile') as HTMLInputElement | null)?.value || 95);
            const k = Number((this.container.querySelector('#dl-anomaly-compare-k') as HTMLInputElement | null)?.value || 2.5);
            const consensusMin = this.getNumberInputValue('dl-anomaly-compare-consensus-min', 2, 2, 4);
            const focusMetric = this.getCompareFocusMetric();
            const referenceModel = ((this.container.querySelector('#dl-anomaly-compare-reference') as HTMLSelectElement | null)?.value ||
                'vae') as CompareModelName;

            this.setStatus(`正在对比 ${selectedModels.length} 个异常检测模型...`, 'loading');
            summary.textContent = '正在运行模型对比，请稍候...';

            const requests = selectedModels.map(async (model) => {
                const response = await this.apiService.predictAnomaly({
                    model_name: model,
                    coords,
                    values,
                    threshold_method: thresholdMethod,
                    percentile,
                    k
                });
                return { model, response: response as Record<string, unknown> };
            });
            const outputs = await Promise.all(requests);

            const rows = outputs.map((item) => {
                const anomalyIndices = this.extractAnomalyIndicesFromResult(item.response, values.length);
                const scores = Array.isArray(item.response.anomaly_scores)
                    ? item.response.anomaly_scores.map((raw) => Number(raw)).filter((score) => Number.isFinite(score))
                    : [];
                const stats = scores.length > 0 ? this.computeStats(scores) : { mean: 0, std: 0 };
                return {
                    model: item.model,
                    label: this.getCompareLabel(item.model),
                    anomalyIndices,
                    anomalyCount: anomalyIndices.length,
                    anomalyRate: anomalyIndices.length / Math.max(1, values.length),
                    coverage: 0,
                    avgScore: stats.mean,
                    scoreStd: stats.std,
                    threshold: this.estimateThreshold(scores, thresholdMethod, percentile, k)
                };
            });

            const union = new Set<number>();
            rows.forEach((item) => item.anomalyIndices.forEach((idx) => union.add(idx)));
            rows.forEach((item) => {
                item.coverage = union.size > 0 ? item.anomalyIndices.length / union.size : 0;
            });

            const pairwise = this.buildPairwiseStats(rows);
            tableHost.innerHTML = this.renderCompareTable(rows);
            metricsHost.innerHTML = this.renderCompareMetrics(rows, focusMetric);
            consistencyHost.innerHTML = this.renderConsistency(rows, pairwise, consensusMin, referenceModel);

            const avgJaccard = pairwise.length > 0 ? pairwise.reduce((sum, item) => sum + item.jaccard, 0) / pairwise.length : 0;
            summary.textContent = `已完成 ${rows.length} 个模型对比：并集异常点 ${union.size} 个，平均两两一致性 ${(avgJaccard * 100).toFixed(
                2
            )}%。`;
            this.setStatus('异常检测结果对比完成', 'success');
        } catch (error) {
            summary.textContent = '模型对比失败，请检查输入参数或后端服务状态。';
            this.setStatus(`对比失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    public destroy(): void {
        this.container.innerHTML = '';
    }
}
