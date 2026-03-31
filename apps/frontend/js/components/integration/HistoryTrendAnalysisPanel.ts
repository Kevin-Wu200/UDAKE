import type { HistorySnapshotMetadata, HistoryTrendPayload } from '../../services/API封装.js';
import { APIService } from '../../services/API封装.js';
import notificationManager from '../NotificationManager.js';

interface TrendPoint {
    timestamp: string;
    value: number;
}

interface MannKendallResult {
    tau: number;
    s: number;
    z: number;
    p_value: number;
    has_trend: boolean;
}

interface LinearTrendResult {
    slope: number;
    intercept: number;
    r_squared: number;
    direction: string;
}

interface PeriodicComponent {
    frequency: number;
    period: number;
    amplitude: number;
}

interface AnomalyPoint {
    index: number;
    timestamp: string;
    value: number;
    score: number;
    anomaly_type: string;
}

interface ForecastPoint {
    index: number;
    timestamp: string;
    predicted_value: number;
    lower_bound: number;
    upper_bound: number;
}

interface ForecastEvaluation {
    mae: number;
    mape: number;
    r2: number;
    accuracy: number;
}

interface TrendAnalysisResult {
    dataset_id: string;
    version: number;
    sample_size: number;
    linear_trend: LinearTrendResult;
    mann_kendall: MannKendallResult;
    periodic_components: PeriodicComponent[];
    anomalies: AnomalyPoint[];
    forecast: ForecastPoint[];
    evaluation: ForecastEvaluation;
}

interface SeasonalDecomposition {
    trend: number[];
    seasonal: number[];
    residual: number[];
}

interface EChartsLike {
    init: (el: HTMLElement) => EChartInstance;
}

interface EChartInstance {
    setOption: (option: Record<string, unknown>, opts?: { notMerge?: boolean }) => void;
    resize: () => void;
    dispose: () => void;
}

const LAST_DATASET_KEY = 'udake_history_snapshot_last_dataset_id';

export class HistoryTrendAnalysisPanel {
    private root: HTMLElement | null = null;
    private statusElement: HTMLElement | null = null;
    private datasetInput: HTMLInputElement | null = null;
    private versionSelect: HTMLSelectElement | null = null;
    private alphaInput: HTMLInputElement | null = null;
    private horizonInput: HTMLInputElement | null = null;
    private seasonalInput: HTMLInputElement | null = null;
    private anomalyInput: HTMLInputElement | null = null;

    private metricsHost: HTMLElement | null = null;
    private mannHost: HTMLElement | null = null;
    private fftTableHost: HTMLElement | null = null;

    private linearChartHost: HTMLElement | null = null;
    private fftChartHost: HTMLElement | null = null;
    private seasonalChartHost: HTMLElement | null = null;

    private linearChart: EChartInstance | null = null;
    private fftChart: EChartInstance | null = null;
    private seasonalChart: EChartInstance | null = null;

    private snapshots: HistorySnapshotMetadata[] = [];
    private trendResult: TrendAnalysisResult | null = null;
    private timeSeriesCache: Map<number, TrendPoint[]> = new Map();

    constructor(private readonly apiService: APIService) {}

    public mount(container: HTMLElement): void {
        this.root = document.createElement('div');
        this.root.className = 'integration-module-panel history-trend-analysis-panel';
        this.root.innerHTML = `
            <h3 class="integration-module-title">趋势分析可视化仪表板</h3>
            <p class="integration-module-description">覆盖线性趋势、置信区间、Mann-Kendall 检验、FFT 周期分析、季节性分解与统计指标。</p>

            <section class="history-trend-card">
                <h4>参数配置</h4>
                <div class="history-trend-param-grid">
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-trend-dataset-id">数据集 ID</label>
                        <input id="history-trend-dataset-id" class="input integration-input" type="text" placeholder="例如 dataset-001">
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-trend-version">版本</label>
                        <select id="history-trend-version" class="select integration-input"></select>
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-trend-alpha">显著性水平 alpha</label>
                        <input id="history-trend-alpha" class="input integration-input" type="number" min="0.001" max="0.5" step="0.001" value="0.05">
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-trend-horizon">预测步数</label>
                        <input id="history-trend-horizon" class="input integration-input" type="number" min="1" max="365" step="1" value="12">
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-trend-seasonal">季节周期（可选）</label>
                        <input id="history-trend-seasonal" class="input integration-input" type="number" min="2" max="365" step="1" placeholder="留空自动推断">
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-trend-anomaly">异常阈值 z-score</label>
                        <input id="history-trend-anomaly" class="input integration-input" type="number" min="1" max="6" step="0.1" value="2.5">
                    </div>
                </div>
                <div class="integration-actions">
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="load-versions">加载版本</button>
                    <button type="button" class="btn btn-primary integration-action-btn" data-action="analyze">执行趋势分析</button>
                </div>
            </section>

            <div class="status-message" data-role="history-trend-status"></div>

            <section class="history-trend-card">
                <h4>趋势统计指标面板</h4>
                <div class="history-trend-metrics" data-role="trend-metrics"></div>
            </section>

            <section class="history-trend-main-grid">
                <section class="history-trend-card">
                    <h4>线性趋势图（含预测与置信区间）</h4>
                    <div class="history-trend-chart" data-role="linear-chart"></div>
                    <p class="history-trend-hint">异常点会在图中标注；趋势线方程为 y = slope * x + intercept。</p>
                </section>

                <section class="history-trend-card">
                    <h4>Mann-Kendall 检验结果</h4>
                    <div class="history-trend-mann" data-role="mann-result"></div>
                </section>
            </section>

            <section class="history-trend-main-grid">
                <section class="history-trend-card">
                    <h4>周期性分析（FFT）</h4>
                    <div class="history-trend-chart" data-role="fft-chart"></div>
                    <div class="history-trend-fft-table" data-role="fft-table"></div>
                </section>

                <section class="history-trend-card">
                    <h4>季节性分解（原始/趋势/季节/残差）</h4>
                    <div class="history-trend-chart history-trend-chart-tall" data-role="seasonal-chart"></div>
                </section>
            </section>
        `;

        container.appendChild(this.root);
        this.bindElements();
        this.bindEvents();
        this.bootstrapDefaults();
        this.renderEmptyState();

        window.addEventListener('resize', this.handleResize);
    }

    private bindElements(): void {
        if (!this.root) {
            return;
        }

        this.statusElement = this.root.querySelector('[data-role="history-trend-status"]');
        this.datasetInput = this.root.querySelector('#history-trend-dataset-id');
        this.versionSelect = this.root.querySelector('#history-trend-version');
        this.alphaInput = this.root.querySelector('#history-trend-alpha');
        this.horizonInput = this.root.querySelector('#history-trend-horizon');
        this.seasonalInput = this.root.querySelector('#history-trend-seasonal');
        this.anomalyInput = this.root.querySelector('#history-trend-anomaly');

        this.metricsHost = this.root.querySelector('[data-role="trend-metrics"]');
        this.mannHost = this.root.querySelector('[data-role="mann-result"]');
        this.fftTableHost = this.root.querySelector('[data-role="fft-table"]');

        this.linearChartHost = this.root.querySelector('[data-role="linear-chart"]');
        this.fftChartHost = this.root.querySelector('[data-role="fft-chart"]');
        this.seasonalChartHost = this.root.querySelector('[data-role="seasonal-chart"]');
    }

    private bindEvents(): void {
        if (!this.root) {
            return;
        }

        this.root.addEventListener('click', async (event: MouseEvent) => {
            const target = event.target as HTMLElement | null;
            if (!target) {
                return;
            }

            const actionEl = target.closest('[data-action]') as HTMLElement | null;
            if (!actionEl) {
                return;
            }

            const action = actionEl.getAttribute('data-action');
            if (!action) {
                return;
            }

            if (action === 'load-versions') {
                await this.handleLoadVersions();
                return;
            }

            if (action === 'analyze') {
                await this.handleAnalyze();
            }
        });
    }

    private bootstrapDefaults(): void {
        if (!this.datasetInput || !this.versionSelect) {
            return;
        }

        const savedDatasetId = this.readStorage(LAST_DATASET_KEY);
        if (savedDatasetId) {
            this.datasetInput.value = savedDatasetId;
        }

        this.renderVersionOptions();
    }

    private async handleLoadVersions(): Promise<void> {
        const datasetId = this.datasetInput?.value.trim() || '';
        if (!datasetId) {
            this.updateStatus('请输入数据集 ID。', 'error');
            return;
        }

        this.updateStatus('正在加载版本列表...', 'info');
        try {
            const response = await this.apiService.listHistorySnapshots(datasetId);
            this.snapshots = Array.isArray(response.versions) ? [...response.versions] : [];
            this.snapshots.sort((a, b) => a.version - b.version);
            this.renderVersionOptions();
            this.writeStorage(LAST_DATASET_KEY, datasetId);
            this.updateStatus(`版本列表加载完成，共 ${this.snapshots.length} 个版本。`, 'success');
        } catch (error) {
            this.snapshots = [];
            this.renderVersionOptions();
            const message = error instanceof Error ? error.message : '加载版本列表失败';
            this.updateStatus(message, 'error');
            notificationManager.show({
                type: 'taskFailure',
                title: '趋势分析版本加载失败',
                body: message
            });
        }
    }

    private async handleAnalyze(): Promise<void> {
        const datasetId = this.datasetInput?.value.trim() || '';
        if (!datasetId) {
            this.updateStatus('请输入数据集 ID。', 'error');
            return;
        }

        const payload = this.buildPayload(datasetId);
        if (!payload) {
            return;
        }

        this.updateStatus('正在执行趋势分析并生成图表...', 'info');

        try {
            const raw = await this.apiService.analyzeHistoryTrend(payload);
            const trendResult = this.normalizeTrendResult(raw);
            this.trendResult = trendResult;

            const series = await this.getTimeSeries(datasetId, trendResult.version);
            this.renderDashboard(trendResult, series);

            this.updateStatus(`趋势分析完成（版本 v${trendResult.version}，样本 ${trendResult.sample_size} 条）。`, 'success');
            notificationManager.show({
                type: 'taskSuccess',
                title: '趋势分析完成',
                body: `数据集 ${trendResult.dataset_id} 版本 v${trendResult.version} 已完成分析。`
            });
        } catch (error) {
            const message = error instanceof Error ? error.message : '趋势分析失败';
            this.updateStatus(message, 'error');
            notificationManager.show({
                type: 'taskFailure',
                title: '趋势分析失败',
                body: message
            });
        }
    }

    private buildPayload(datasetId: string): HistoryTrendPayload | null {
        const alpha = Number(this.alphaInput?.value || '0.05');
        const forecastHorizon = Number(this.horizonInput?.value || '12');
        const anomalyThreshold = Number(this.anomalyInput?.value || '2.5');

        if (!Number.isFinite(alpha) || alpha <= 0 || alpha >= 1) {
            this.updateStatus('alpha 必须在 0 和 1 之间。', 'error');
            return null;
        }

        if (!Number.isFinite(forecastHorizon) || forecastHorizon < 1 || forecastHorizon > 365) {
            this.updateStatus('预测步数范围应为 1-365。', 'error');
            return null;
        }

        if (!Number.isFinite(anomalyThreshold) || anomalyThreshold < 1 || anomalyThreshold > 6) {
            this.updateStatus('异常阈值范围应为 1-6。', 'error');
            return null;
        }

        const payload: HistoryTrendPayload = {
            dataset_id: datasetId,
            alpha,
            forecast_horizon: Math.floor(forecastHorizon),
            anomaly_z_threshold: anomalyThreshold
        };

        const versionValue = Number(this.versionSelect?.value || '');
        if (Number.isFinite(versionValue) && versionValue >= 1) {
            payload.version = Math.floor(versionValue);
        }

        const seasonalText = this.seasonalInput?.value.trim() || '';
        if (seasonalText) {
            const seasonalPeriod = Number(seasonalText);
            if (!Number.isFinite(seasonalPeriod) || seasonalPeriod < 2 || seasonalPeriod > 365) {
                this.updateStatus('季节周期范围应为 2-365，或留空自动推断。', 'error');
                return null;
            }
            payload.seasonal_period = Math.floor(seasonalPeriod);
        }

        return payload;
    }

    private renderVersionOptions(): void {
        if (!this.versionSelect) {
            return;
        }

        if (this.snapshots.length === 0) {
            this.versionSelect.innerHTML = '<option value="">最新版本</option>';
            return;
        }

        const options: string[] = ['<option value="">最新版本</option>'];
        this.snapshots.forEach(snapshot => {
            const label = snapshot.version_label || `v${snapshot.version}`;
            options.push(`<option value="${snapshot.version}">${this.escapeHtml(label)} (v${snapshot.version})</option>`);
        });
        this.versionSelect.innerHTML = options.join('');
        this.versionSelect.value = String(this.snapshots[this.snapshots.length - 1].version);
    }

    private async getTimeSeries(datasetId: string, version: number): Promise<TrendPoint[]> {
        if (this.timeSeriesCache.has(version)) {
            return this.timeSeriesCache.get(version) || [];
        }

        const response = await this.apiService.exportHistoryAnalysis({ dataset_id: datasetId, format: 'json' });
        const snapshots = this.extractSnapshotsFromExport(response);
        const target = snapshots.find(item => item.version === version) || snapshots[snapshots.length - 1];

        const points: TrendPoint[] = Array.isArray(target?.records)
            ? target.records
                .map((item: Record<string, unknown>) => {
                    const timestamp = this.asString(item.timestamp);
                    const value = this.asNumber(item.value);
                    if (!timestamp || value === null) {
                        return null;
                    }
                    return { timestamp, value };
                })
                .filter((item): item is TrendPoint => item !== null)
            : [];

        points.sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
        this.timeSeriesCache.set(version, points);
        return points;
    }

    private extractSnapshotsFromExport(raw: Record<string, unknown>): Array<{ version: number; records: Record<string, unknown>[] }> {
        const contentText = this.asString(raw.content);
        if (!contentText) {
            return [];
        }

        let parsed: unknown;
        try {
            parsed = JSON.parse(contentText);
        } catch {
            return [];
        }

        if (!parsed || typeof parsed !== 'object') {
            return [];
        }

        const snapshots = (parsed as { snapshots?: unknown }).snapshots;
        if (!Array.isArray(snapshots)) {
            return [];
        }

        const results: Array<{ version: number; records: Record<string, unknown>[] }> = [];
        snapshots.forEach(item => {
            if (!item || typeof item !== 'object') {
                return;
            }

            const version = this.asNumber((item as { version?: unknown }).version);
            const records = (item as { records?: unknown }).records;
            if (version === null || !Array.isArray(records)) {
                return;
            }

            const normalizedRecords = records.filter(record => record && typeof record === 'object') as Record<string, unknown>[];
            results.push({ version, records: normalizedRecords });
        });

        return results;
    }

    private normalizeTrendResult(raw: Record<string, unknown>): TrendAnalysisResult {
        const datasetId = this.asString(raw.dataset_id) || '';
        const version = this.asNumber(raw.version) || 0;
        const sampleSize = this.asNumber(raw.sample_size) || 0;

        const linearRaw = this.asRecord(raw.linear_trend);
        const mannRaw = this.asRecord(raw.mann_kendall);
        const evalRaw = this.asRecord(raw.evaluation);

        const periodicComponents = Array.isArray(raw.periodic_components)
            ? raw.periodic_components
                .map(item => this.asRecord(item))
                .filter((item): item is Record<string, unknown> => item !== null)
                .map(item => ({
                    frequency: this.asNumber(item.frequency) || 0,
                    period: this.asNumber(item.period) || 0,
                    amplitude: this.asNumber(item.amplitude) || 0
                }))
            : [];

        const anomalies = Array.isArray(raw.anomalies)
            ? raw.anomalies
                .map(item => this.asRecord(item))
                .filter((item): item is Record<string, unknown> => item !== null)
                .map(item => ({
                    index: this.asNumber(item.index) || 0,
                    timestamp: this.asString(item.timestamp) || '',
                    value: this.asNumber(item.value) || 0,
                    score: this.asNumber(item.score) || 0,
                    anomaly_type: this.asString(item.anomaly_type) || 'unknown'
                }))
            : [];

        const forecast = Array.isArray(raw.forecast)
            ? raw.forecast
                .map(item => this.asRecord(item))
                .filter((item): item is Record<string, unknown> => item !== null)
                .map(item => ({
                    index: this.asNumber(item.index) || 0,
                    timestamp: this.asString(item.timestamp) || '',
                    predicted_value: this.asNumber(item.predicted_value) || 0,
                    lower_bound: this.asNumber(item.lower_bound) || 0,
                    upper_bound: this.asNumber(item.upper_bound) || 0
                }))
            : [];

        if (!datasetId || version < 1) {
            throw new Error('趋势分析响应缺少关键字段（dataset_id/version）');
        }

        return {
            dataset_id: datasetId,
            version,
            sample_size: sampleSize,
            linear_trend: {
                slope: this.asNumber(linearRaw?.slope) || 0,
                intercept: this.asNumber(linearRaw?.intercept) || 0,
                r_squared: this.asNumber(linearRaw?.r_squared) || 0,
                direction: this.asString(linearRaw?.direction) || 'stable'
            },
            mann_kendall: {
                tau: this.asNumber(mannRaw?.tau) || 0,
                s: this.asNumber(mannRaw?.s) || 0,
                z: this.asNumber(mannRaw?.z) || 0,
                p_value: this.asNumber(mannRaw?.p_value) || 1,
                has_trend: Boolean(mannRaw?.has_trend)
            },
            periodic_components: periodicComponents,
            anomalies,
            forecast,
            evaluation: {
                mae: this.asNumber(evalRaw?.mae) || 0,
                mape: this.asNumber(evalRaw?.mape) || 0,
                r2: this.asNumber(evalRaw?.r2) || 0,
                accuracy: this.asNumber(evalRaw?.accuracy) || 0
            }
        };
    }

    private renderDashboard(result: TrendAnalysisResult, timeSeries: TrendPoint[]): void {
        this.renderMetrics(result, timeSeries);
        this.renderMannKendall(result);
        this.renderFFT(result);
        this.renderSeasonal(result, timeSeries);
        this.renderLinearTrend(result, timeSeries);
    }

    private renderMetrics(result: TrendAnalysisResult, timeSeries: TrendPoint[]): void {
        if (!this.metricsHost) {
            return;
        }

        const slope = result.linear_trend.slope;
        const directionLabel = this.getDirectionLabel(result.linear_trend.direction);
        const firstValue = timeSeries.length > 0 ? timeSeries[0].value : 0;
        const lastValue = timeSeries.length > 0 ? timeSeries[timeSeries.length - 1].value : 0;
        const changeRate = firstValue !== 0 ? ((lastValue - firstValue) / Math.abs(firstValue)) * 100 : 0;

        const forecastValues = result.forecast.map(item => item.predicted_value);
        const forecastMin = forecastValues.length > 0 ? Math.min(...forecastValues) : 0;
        const forecastMax = forecastValues.length > 0 ? Math.max(...forecastValues) : 0;

        const cards = [
            { label: '趋势方向', value: directionLabel },
            { label: '趋势斜率', value: slope.toFixed(6) },
            { label: 'R²', value: result.linear_trend.r_squared.toFixed(4) },
            { label: '样本数量', value: `${result.sample_size}` },
            { label: '变化率', value: `${changeRate.toFixed(2)}%` },
            { label: '预测范围', value: `${forecastMin.toFixed(4)} ~ ${forecastMax.toFixed(4)}` },
            { label: '异常点数量', value: `${result.anomalies.length}` },
            { label: '预测准确率', value: `${result.evaluation.accuracy.toFixed(2)}%` }
        ];

        this.metricsHost.innerHTML = cards
            .map(
                card => `
                    <div class="history-trend-metric-card">
                        <span class="history-trend-metric-label">${this.escapeHtml(card.label)}</span>
                        <span class="history-trend-metric-value">${this.escapeHtml(card.value)}</span>
                    </div>
                `
            )
            .join('');
    }

    private renderMannKendall(result: TrendAnalysisResult): void {
        if (!this.mannHost) {
            return;
        }

        const mk = result.mann_kendall;
        const trendText = mk.has_trend ? '显著趋势' : '无显著趋势';
        const pClass = mk.p_value < 0.05 ? 'is-significant' : 'is-normal';

        this.mannHost.innerHTML = `
            <div class="history-trend-mann-grid">
                <div><span class="k">Tau</span><span class="v">${mk.tau.toFixed(6)}</span></div>
                <div><span class="k">S</span><span class="v">${mk.s.toFixed(2)}</span></div>
                <div><span class="k">Z</span><span class="v">${mk.z.toFixed(4)}</span></div>
                <div><span class="k">P 值</span><span class="v ${pClass}">${mk.p_value.toExponential(3)}</span></div>
                <div><span class="k">显著性</span><span class="v">${trendText}</span></div>
            </div>
        `;
    }

    private renderFFT(result: TrendAnalysisResult): void {
        if (!this.fftTableHost) {
            return;
        }

        const components = result.periodic_components;
        if (components.length === 0) {
            this.fftTableHost.innerHTML = '<div class="history-empty">未检测到显著周期分量。</div>';
        } else {
            const rows = components
                .map((item, idx) => {
                    return `
                        <tr>
                            <td>${idx + 1}</td>
                            <td>${item.period.toFixed(2)}</td>
                            <td>${item.frequency.toFixed(6)}</td>
                            <td>${item.amplitude.toFixed(6)}</td>
                        </tr>
                    `;
                })
                .join('');

            this.fftTableHost.innerHTML = `
                <table class="history-table history-trend-mini-table">
                    <thead>
                        <tr><th>#</th><th>主周期</th><th>频率</th><th>振幅</th></tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            `;
        }

        const chart = this.ensureChart('fft');
        if (!chart) {
            return;
        }

        chart.setOption(
            {
                tooltip: { trigger: 'axis' },
                grid: { left: 40, right: 20, top: 30, bottom: 40 },
                xAxis: {
                    type: 'category',
                    name: '周期',
                    data: components.map((item, idx) => `P${idx + 1} (${item.period.toFixed(1)})`)
                },
                yAxis: {
                    type: 'value',
                    name: '振幅'
                },
                series: [
                    {
                        type: 'bar',
                        name: 'FFT 振幅',
                        data: components.map(item => Number(item.amplitude.toFixed(6))),
                        itemStyle: { color: '#2563eb' }
                    }
                ]
            },
            { notMerge: true }
        );
    }

    private renderSeasonal(result: TrendAnalysisResult, timeSeries: TrendPoint[]): void {
        const chart = this.ensureChart('seasonal');
        if (!chart) {
            return;
        }

        if (timeSeries.length < 4) {
            chart.setOption(
                {
                    title: {
                        text: '样本不足，无法进行季节性分解',
                        left: 'center',
                        top: 'middle',
                        textStyle: { fontSize: 12 }
                    }
                },
                { notMerge: true }
            );
            return;
        }

        const inferredSeasonal = result.periodic_components[0] ? Math.max(2, Math.round(result.periodic_components[0].period)) : 7;
        const decomposition = this.decomposeSeries(timeSeries.map(item => item.value), inferredSeasonal);
        const labels = timeSeries.map(item => this.formatDateLabel(item.timestamp));

        chart.setOption(
            {
                tooltip: { trigger: 'axis' },
                grid: [
                    { left: 45, right: 20, top: 20, height: '18%' },
                    { left: 45, right: 20, top: '29%', height: '18%' },
                    { left: 45, right: 20, top: '54%', height: '18%' },
                    { left: 45, right: 20, top: '79%', height: '18%' }
                ],
                xAxis: [
                    { type: 'category', data: labels, gridIndex: 0, axisLabel: { show: false } },
                    { type: 'category', data: labels, gridIndex: 1, axisLabel: { show: false } },
                    { type: 'category', data: labels, gridIndex: 2, axisLabel: { show: false } },
                    { type: 'category', data: labels, gridIndex: 3, axisLabel: { rotate: 40, interval: 'auto' } }
                ],
                yAxis: [
                    { type: 'value', gridIndex: 0, name: '原始' },
                    { type: 'value', gridIndex: 1, name: '趋势' },
                    { type: 'value', gridIndex: 2, name: '季节' },
                    { type: 'value', gridIndex: 3, name: '残差' }
                ],
                series: [
                    { type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: timeSeries.map(item => item.value), smooth: true, symbol: 'none', lineStyle: { color: '#1f2937' } },
                    { type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: decomposition.trend, smooth: true, symbol: 'none', lineStyle: { color: '#2563eb' } },
                    { type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: decomposition.seasonal, smooth: true, symbol: 'none', lineStyle: { color: '#16a34a' } },
                    { type: 'line', xAxisIndex: 3, yAxisIndex: 3, data: decomposition.residual, smooth: true, symbol: 'none', lineStyle: { color: '#dc2626' } }
                ]
            },
            { notMerge: true }
        );
    }

    private renderLinearTrend(result: TrendAnalysisResult, timeSeries: TrendPoint[]): void {
        const chart = this.ensureChart('linear');
        if (!chart) {
            return;
        }

        if (timeSeries.length === 0) {
            chart.setOption(
                {
                    title: {
                        text: '未获取到原始时间序列，无法绘制趋势线与分解图',
                        left: 'center',
                        top: 'middle',
                        textStyle: { fontSize: 12 }
                    }
                },
                { notMerge: true }
            );
            return;
        }

        const labels = timeSeries.map(item => this.formatDateLabel(item.timestamp));
        const values = timeSeries.map(item => item.value);
        const trendLine = values.map((_, index) => result.linear_trend.slope * index + result.linear_trend.intercept);
        const residualStd = this.computeResidualStd(values, trendLine);
        const upper = trendLine.map(item => item + residualStd * 1.96);
        const lower = trendLine.map(item => item - residualStd * 1.96);

        const forecastLabels = result.forecast.map(item => this.formatDateLabel(item.timestamp));
        const forecastValues = result.forecast.map(item => item.predicted_value);
        const forecastUpper = result.forecast.map(item => item.upper_bound);
        const forecastLower = result.forecast.map(item => item.lower_bound);

        const allLabels = [...labels, ...forecastLabels];

        const padActual = [...values, ...Array(forecastValues.length).fill(null)];
        const padTrend = [...trendLine, ...Array(forecastValues.length).fill(null)];
        const padUpper = [...upper, ...Array(forecastValues.length).fill(null)];
        const padLower = [...lower, ...Array(forecastValues.length).fill(null)];

        const forecastPadding = Array(values.length).fill(null);
        const padForecast = [...forecastPadding, ...forecastValues];
        const padForecastUpper = [...forecastPadding, ...forecastUpper];
        const padForecastLower = [...forecastPadding, ...forecastLower];

        const anomalyByDate = new Map<string, number>();
        result.anomalies.forEach(item => {
            const key = this.formatDateLabel(item.timestamp);
            anomalyByDate.set(key, item.value);
        });

        const anomalyData = allLabels.map((label, idx) => {
            const value = anomalyByDate.get(label);
            if (value === undefined) {
                return null;
            }
            return [idx, value];
        }).filter(item => item !== null);

        const equation = `y = ${result.linear_trend.slope.toFixed(6)}x + ${result.linear_trend.intercept.toFixed(6)}`;

        chart.setOption(
            {
                tooltip: { trigger: 'axis' },
                legend: {
                    top: 4,
                    data: ['原始值', '趋势线', '趋势置信上界', '趋势置信下界', '预测值', '预测上界', '预测下界', '异常点']
                },
                grid: { left: 45, right: 25, top: 48, bottom: 50 },
                dataZoom: [
                    { type: 'inside' },
                    { type: 'slider', height: 18, bottom: 18 }
                ],
                xAxis: { type: 'category', data: allLabels },
                yAxis: { type: 'value', scale: true },
                series: [
                    { name: '原始值', type: 'line', data: padActual, smooth: true, symbol: 'none', lineStyle: { color: '#111827' } },
                    { name: '趋势线', type: 'line', data: padTrend, smooth: true, symbol: 'none', lineStyle: { color: '#2563eb', width: 2 } },
                    { name: '趋势置信上界', type: 'line', data: padUpper, smooth: true, symbol: 'none', lineStyle: { color: '#93c5fd', type: 'dashed' } },
                    {
                        name: '趋势置信下界',
                        type: 'line',
                        data: padLower,
                        smooth: true,
                        symbol: 'none',
                        lineStyle: { color: '#93c5fd', type: 'dashed' },
                        areaStyle: { color: 'rgba(147,197,253,0.18)' }
                    },
                    { name: '预测值', type: 'line', data: padForecast, smooth: true, symbol: 'none', lineStyle: { color: '#16a34a', width: 2 } },
                    { name: '预测上界', type: 'line', data: padForecastUpper, smooth: true, symbol: 'none', lineStyle: { color: '#86efac', type: 'dotted' } },
                    {
                        name: '预测下界',
                        type: 'line',
                        data: padForecastLower,
                        smooth: true,
                        symbol: 'none',
                        lineStyle: { color: '#86efac', type: 'dotted' },
                        areaStyle: { color: 'rgba(134,239,172,0.16)' }
                    },
                    {
                        name: '异常点',
                        type: 'scatter',
                        data: anomalyData,
                        symbolSize: 10,
                        itemStyle: { color: '#dc2626' }
                    }
                ],
                graphic: [
                    {
                        type: 'text',
                        left: 50,
                        top: 28,
                        style: {
                            text: `趋势方程：${equation}`,
                            fontSize: 12,
                            fill: '#374151'
                        }
                    }
                ]
            },
            { notMerge: true }
        );
    }

    private decomposeSeries(values: number[], period: number): SeasonalDecomposition {
        const n = values.length;
        const safePeriod = Math.max(2, Math.min(period, Math.floor(n / 2)));

        const trend = values.map((_, index) => {
            const start = Math.max(0, index - Math.floor(safePeriod / 2));
            const end = Math.min(n, index + Math.ceil(safePeriod / 2));
            const slice = values.slice(start, end);
            return slice.reduce((sum, item) => sum + item, 0) / Math.max(1, slice.length);
        });

        const detrended = values.map((value, index) => value - trend[index]);

        const seasonalBuckets: number[][] = Array.from({ length: safePeriod }, () => []);
        detrended.forEach((value, index) => {
            seasonalBuckets[index % safePeriod].push(value);
        });

        const seasonalPattern = seasonalBuckets.map(bucket => {
            if (bucket.length === 0) {
                return 0;
            }
            return bucket.reduce((sum, item) => sum + item, 0) / bucket.length;
        });

        const seasonal = detrended.map((_, index) => seasonalPattern[index % safePeriod]);
        const residual = values.map((value, index) => value - trend[index] - seasonal[index]);

        return { trend, seasonal, residual };
    }

    private renderEmptyState(): void {
        if (this.metricsHost) {
            this.metricsHost.innerHTML = '<div class="history-empty">执行趋势分析后展示统计指标。</div>';
        }

        if (this.mannHost) {
            this.mannHost.innerHTML = '<div class="history-empty">执行趋势分析后展示 Mann-Kendall 检验结果。</div>';
        }

        if (this.fftTableHost) {
            this.fftTableHost.innerHTML = '<div class="history-empty">执行趋势分析后展示周期识别结果。</div>';
        }
    }

    private ensureChart(type: 'linear' | 'fft' | 'seasonal'): EChartInstance | null {
        const echarts = this.getEcharts();
        if (!echarts) {
            const host = type === 'linear' ? this.linearChartHost : type === 'fft' ? this.fftChartHost : this.seasonalChartHost;
            if (host) {
                host.innerHTML = '<div class="history-empty">当前环境未加载 ECharts，无法渲染图表。</div>';
            }
            return null;
        }

        if (type === 'linear') {
            if (!this.linearChart && this.linearChartHost) {
                this.linearChart = echarts.init(this.linearChartHost);
            }
            return this.linearChart;
        }

        if (type === 'fft') {
            if (!this.fftChart && this.fftChartHost) {
                this.fftChart = echarts.init(this.fftChartHost);
            }
            return this.fftChart;
        }

        if (!this.seasonalChart && this.seasonalChartHost) {
            this.seasonalChart = echarts.init(this.seasonalChartHost);
        }
        return this.seasonalChart;
    }

    private getEcharts(): EChartsLike | null {
        const win = window as Window & { echarts?: EChartsLike };
        return win.echarts || null;
    }

    private handleResize = (): void => {
        this.linearChart?.resize();
        this.fftChart?.resize();
        this.seasonalChart?.resize();
    };

    private updateStatus(message: string, type: 'info' | 'success' | 'error'): void {
        if (!this.statusElement) {
            return;
        }

        this.statusElement.textContent = message;
        this.statusElement.classList.remove('is-success', 'is-error');
        if (type === 'success') {
            this.statusElement.classList.add('is-success');
        }
        if (type === 'error') {
            this.statusElement.classList.add('is-error');
        }
    }

    private getDirectionLabel(direction: string): string {
        if (direction === 'increasing') {
            return '上升';
        }
        if (direction === 'decreasing') {
            return '下降';
        }
        return '稳定';
    }

    private computeResidualStd(values: number[], trend: number[]): number {
        if (values.length <= 1 || values.length !== trend.length) {
            return 0;
        }

        const residual = values.map((value, index) => value - trend[index]);
        const mean = residual.reduce((sum, item) => sum + item, 0) / residual.length;
        const variance = residual.reduce((sum, item) => sum + Math.pow(item - mean, 2), 0) / (residual.length - 1);
        return Math.sqrt(Math.max(0, variance));
    }

    private formatDateLabel(timestamp: string): string {
        const date = new Date(timestamp);
        if (Number.isNaN(date.getTime())) {
            return timestamp;
        }
        const yyyy = date.getFullYear();
        const mm = `${date.getMonth() + 1}`.padStart(2, '0');
        const dd = `${date.getDate()}`.padStart(2, '0');
        return `${yyyy}-${mm}-${dd}`;
    }

    private asRecord(value: unknown): Record<string, unknown> | null {
        if (!value || typeof value !== 'object' || Array.isArray(value)) {
            return null;
        }
        return value as Record<string, unknown>;
    }

    private asString(value: unknown): string | null {
        return typeof value === 'string' ? value : null;
    }

    private asNumber(value: unknown): number | null {
        if (typeof value === 'number' && Number.isFinite(value)) {
            return value;
        }
        if (typeof value === 'string') {
            const parsed = Number(value);
            return Number.isFinite(parsed) ? parsed : null;
        }
        return null;
    }

    private readStorage(key: string): string {
        try {
            return localStorage.getItem(key) || '';
        } catch {
            return '';
        }
    }

    private writeStorage(key: string, value: string): void {
        try {
            localStorage.setItem(key, value);
        } catch {
            // ignore localStorage errors
        }
    }

    private escapeHtml(value: string): string {
        return value
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
}
