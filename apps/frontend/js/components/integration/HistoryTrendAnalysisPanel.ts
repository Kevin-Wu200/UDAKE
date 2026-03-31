import type { HistorySnapshotMetadata, HistoryTrendPayload } from '../../services/API封装.js';
import { APIService } from '../../services/API封装.js';
import notificationManager from '../NotificationManager.js';
import { ConfirmDialog } from '../ConfirmDialog.js';
import { SkeletonLoader } from '../../utils/SkeletonLoader.js';

interface TrendPoint {
    timestamp: string;
    value: number;
    point_id?: string;
    x?: number;
    y?: number;
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

type AnomalySeverity = 'high' | 'medium' | 'low';

interface AnomalyViewItem extends AnomalyPoint {
    severity: AnomalySeverity;
    severity_label: string;
    anomaly_type_label: string;
    threshold: number;
    x: number | null;
    y: number | null;
    point_id: string;
}

interface AnomalyCluster {
    id: string;
    centerX: number;
    centerY: number;
    count: number;
    maxScore: number;
}

interface WarningRecord {
    timestamp: string;
    dataset_id: string;
    version: number;
    anomaly_count: number;
    threshold: number;
    level: 'high' | 'normal';
}

interface AnomalySubscriptionConfig {
    enabled: boolean;
    channels: string[];
    frequency: 'realtime' | 'hourly' | 'daily';
    last_notify_at: string;
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
    rmse?: number;
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
    getDataURL?: (opts?: Record<string, unknown>) => string;
    on?: (event: string, handler: (params: Record<string, unknown>) => void) => void;
}

interface ForecastModelResult {
    key: string;
    name: string;
    values: number[];
    evaluation: ForecastEvaluation;
}

interface ReportTemplateItem {
    id: string;
    name: string;
    description: string;
    preview: string;
    builtIn: boolean;
    content?: string;
}

interface ReportConfigState {
    reportTitle: string;
    fromVersion: number;
    toVersion: number;
    analysisType: 'compare' | 'trend' | 'forecast';
    chartType: 'line' | 'bar' | 'area';
    outputFormat: 'pdf' | 'html' | 'word';
    metrics: string[];
}

interface ReportHistoryRecord {
    id: string;
    datasetId: string;
    versionFrom: number;
    versionTo: number;
    title: string;
    templateId: string;
    templateName: string;
    analysisType: string;
    outputFormat: 'pdf' | 'html' | 'word';
    generatedAt: string;
    content: string;
}

interface DownloadHistoryRecord {
    id: string;
    reportId: string;
    format: 'pdf' | 'html' | 'word';
    fileName: string;
    createdAt: string;
}

const LAST_DATASET_KEY = 'udake_history_snapshot_last_dataset_id';
const WARNING_THRESHOLD_KEY = 'udake_history_anomaly_warning_threshold';
const WARNING_HISTORY_KEY = 'udake_history_anomaly_warning_history';
const SUBSCRIPTION_KEY = 'udake_history_anomaly_subscription';
const REPORT_HISTORY_KEY = 'udake_history_analysis_report_history';
const REPORT_DOWNLOAD_HISTORY_KEY = 'udake_history_analysis_report_download_history';
const REPORT_TEMPLATE_KEY = 'udake_history_analysis_report_templates';
const TREND_AUTO_REFRESH_KEY = 'udake_history_trend_auto_refresh_sec_v1';
const RETRY_TIMES = 2;

export class HistoryTrendAnalysisPanel {
    private root: HTMLElement | null = null;
    private statusElement: HTMLElement | null = null;
    private datasetInput: HTMLInputElement | null = null;
    private versionSelect: HTMLSelectElement | null = null;
    private alphaInput: HTMLInputElement | null = null;
    private horizonInput: HTMLInputElement | null = null;
    private seasonalInput: HTMLInputElement | null = null;
    private anomalyInput: HTMLInputElement | null = null;
    private confidenceLevelSelect: HTMLSelectElement | null = null;
    private timelineRangeSelect: HTMLSelectElement | null = null;
    private timelineGranularitySelect: HTMLSelectElement | null = null;
    private autoRefreshSelect: HTMLSelectElement | null = null;
    private refreshProgressElement: HTMLElement | null = null;

    private metricsHost: HTMLElement | null = null;
    private mannHost: HTMLElement | null = null;
    private fftTableHost: HTMLElement | null = null;
    private anomalyListHost: HTMLElement | null = null;
    private anomalyMapHost: HTMLElement | null = null;
    private anomalyMapClusterHost: HTMLElement | null = null;
    private anomalySeriesHost: HTMLElement | null = null;
    private anomalyTrendHost: HTMLElement | null = null;
    private warningStatsHost: HTMLElement | null = null;
    private warningHistoryHost: HTMLElement | null = null;
    private reasonHost: HTMLElement | null = null;
    private subscriptionHost: HTMLElement | null = null;
    private warningThresholdInput: HTMLInputElement | null = null;
    private filterTypeSelect: HTMLSelectElement | null = null;
    private filterSeveritySelect: HTMLSelectElement | null = null;
    private sortSelect: HTMLSelectElement | null = null;
    private modelCompareHost: HTMLElement | null = null;
    private modelVisibilityHost: HTMLElement | null = null;
    private reportHistorySummaryHost: HTMLElement | null = null;
    private reportDownloadSummaryHost: HTMLElement | null = null;

    private linearChartHost: HTMLElement | null = null;
    private fftChartHost: HTMLElement | null = null;
    private seasonalChartHost: HTMLElement | null = null;

    private linearChart: EChartInstance | null = null;
    private fftChart: EChartInstance | null = null;
    private seasonalChart: EChartInstance | null = null;
    private anomalyMapChart: EChartInstance | null = null;
    private anomalySeriesChart: EChartInstance | null = null;
    private anomalyTrendChart: EChartInstance | null = null;
    private reportPreviewChart: EChartInstance | null = null;

    private snapshots: HistorySnapshotMetadata[] = [];
    private trendResult: TrendAnalysisResult | null = null;
    private timeSeriesCache: Map<number, TrendPoint[]> = new Map();
    private anomalyViewItems: AnomalyViewItem[] = [];
    private warningHistory: WarningRecord[] = [];
    private subscriptionConfig: AnomalySubscriptionConfig = {
        enabled: false,
        channels: ['app'],
        frequency: 'realtime',
        last_notify_at: ''
    };
    private currentThreshold = 2.5;
    private currentTimeSeries: TrendPoint[] = [];
    private modelResults: ForecastModelResult[] = [];
    private activeModelKeys: Set<string> = new Set(['server']);
    private reportTemplates: ReportTemplateItem[] = [];
    private reportHistory: ReportHistoryRecord[] = [];
    private reportDownloadHistory: DownloadHistoryRecord[] = [];

    private reportDialogOverlay: HTMLElement | null = null;
    private reportCurrentConfig: ReportConfigState | null = null;
    private reportPreviewZoom = 1;
    private reportPreviewPage: 'summary' | 'metrics' | 'full' = 'summary';
    private reportLatestRecord: ReportHistoryRecord | null = null;
    private chartSkeleton: HTMLDivElement | null = null;
    private metricsSkeleton: HTMLDivElement | null = null;
    private autoRefreshTimer: number | null = null;
    private refreshCountdownTimer: number | null = null;
    private refreshRemainSec = 0;
    private loading = false;
    private lastRetryAction: (() => Promise<void>) | null = null;

    constructor(private readonly apiService: APIService) {}

    public mount(container: HTMLElement): void {
        this.root = document.createElement('div');
        this.root.className = 'integration-module-panel history-trend-analysis-panel';
        this.root.innerHTML = `
            <h3 class="integration-module-title">趋势分析可视化仪表板</h3>
            <p class="integration-module-description">覆盖线性趋势、异常检测可视化、预测对比导出、预警面板、原因分析与通知订阅。</p>

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
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-trend-confidence">置信水平</label>
                        <select id="history-trend-confidence" class="select integration-input">
                            <option value="0.9">90%</option>
                            <option value="0.95" selected>95%</option>
                            <option value="0.99">99%</option>
                        </select>
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-trend-range">时间范围</label>
                        <select id="history-trend-range" class="select integration-input">
                            <option value="all" selected>全部</option>
                            <option value="30">近 30 天</option>
                            <option value="90">近 90 天</option>
                            <option value="180">近 180 天</option>
                            <option value="365">近 365 天</option>
                        </select>
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-trend-granularity">时间粒度</label>
                        <select id="history-trend-granularity" class="select integration-input">
                            <option value="day" selected>日</option>
                            <option value="week">周</option>
                            <option value="month">月</option>
                        </select>
                    </div>
                </div>
                <div class="integration-actions">
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="load-versions">加载版本</button>
                    <button type="button" class="btn btn-primary integration-action-btn" data-action="analyze">执行趋势分析</button>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="refresh-analysis">刷新分析</button>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="retry-last">重试</button>
                    <button type="button" class="btn btn-primary integration-action-btn" data-action="open-report-dialog">报告生成与导出</button>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="export-forecast-csv">导出预测 CSV</button>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="export-chart-png">导出图表 PNG</button>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="export-report-pdf">导出预测报告（PDF）</button>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="export-all">批量导出</button>
                </div>
                <div class="history-snapshot-refresh-row">
                    <label class="integration-field">
                        <span class="integration-field-label">自动刷新间隔</span>
                        <select id="history-trend-auto-refresh" class="select integration-input">
                            <option value="0">关闭</option>
                            <option value="30">30 秒</option>
                            <option value="60">60 秒</option>
                            <option value="120">120 秒</option>
                        </select>
                    </label>
                    <p class="history-archive-hint" data-role="trend-refresh-progress">自动刷新已关闭。</p>
                    <p class="history-archive-hint">快捷键：Alt+T 执行分析，Alt+R 刷新，Alt+X 批量导出。</p>
                </div>
            </section>

            <div class="status-message" data-role="history-trend-status"></div>

            <section class="history-trend-card">
                <h4>报告历史与下载记录</h4>
                <div class="history-trend-main-grid">
                    <div data-role="report-history-summary"></div>
                    <div data-role="report-download-summary"></div>
                </div>
            </section>

            <section class="history-trend-card">
                <h4>趋势统计指标面板</h4>
                <div class="history-trend-metrics" data-role="trend-metrics"></div>
            </section>

            <section class="history-trend-main-grid">
                <section class="history-trend-card">
                    <h4>多模型预测对比</h4>
                    <div class="history-trend-model-visibility" data-role="model-visibility"></div>
                    <div class="history-trend-model-table" data-role="model-compare"></div>
                </section>
                <section class="history-trend-card">
                    <h4>时间轴控制说明</h4>
                    <p class="history-trend-hint">可通过上方时间范围与粒度切换控制显示窗口，图表底部滑块支持拖拽缩放时间轴。</p>
                    <p class="history-trend-hint">预测步数支持 1-365 调整，切换后重新分析即可更新预测曲线。</p>
                </section>
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

            <section class="history-trend-main-grid">
                <section class="history-trend-card">
                    <h4>异常点列表视图</h4>
                    <div class="history-trend-inline-controls">
                        <select class="select integration-input" data-role="anomaly-filter-type">
                            <option value="all">全部类型</option>
                            <option value="positive">正异常</option>
                            <option value="negative">负异常</option>
                        </select>
                        <select class="select integration-input" data-role="anomaly-filter-severity">
                            <option value="all">全部严重程度</option>
                            <option value="high">高</option>
                            <option value="medium">中</option>
                            <option value="low">低</option>
                        </select>
                        <select class="select integration-input" data-role="anomaly-sort">
                            <option value="score_desc">按异常分数降序</option>
                            <option value="time_desc">按时间倒序</option>
                            <option value="time_asc">按时间正序</option>
                            <option value="value_desc">按异常值降序</option>
                        </select>
                    </div>
                    <div class="history-trend-anomaly-table-wrap" data-role="anomaly-list"></div>
                </section>

                <section class="history-trend-card">
                    <h4>异常点地图标注（坐标视图）</h4>
                    <div class="history-trend-chart" data-role="anomaly-map-chart"></div>
                    <div class="history-trend-cluster-list" data-role="anomaly-clusters"></div>
                </section>
            </section>

            <section class="history-trend-main-grid">
                <section class="history-trend-card">
                    <h4>异常值时间序列图表</h4>
                    <div class="history-trend-chart" data-role="anomaly-series-chart"></div>
                </section>

                <section class="history-trend-card">
                    <h4>异常趋势预警面板</h4>
                    <div class="history-trend-inline-controls">
                        <input class="input integration-input" data-role="warning-threshold" type="number" min="1" max="500" step="1" value="5" placeholder="预警阈值">
                        <button type="button" class="btn btn-secondary integration-action-btn" data-action="save-warning-threshold">保存阈值</button>
                    </div>
                    <div class="history-trend-warning-stats" data-role="warning-stats"></div>
                    <div class="history-trend-chart" data-role="anomaly-trend-chart"></div>
                    <div class="history-trend-warning-history" data-role="warning-history"></div>
                </section>
            </section>

            <section class="history-trend-main-grid">
                <section class="history-trend-card">
                    <h4>异常原因分析展示</h4>
                    <div data-role="anomaly-reasons"></div>
                </section>

                <section class="history-trend-card">
                    <h4>异常通知订阅</h4>
                    <div data-role="anomaly-subscription"></div>
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
        this.confidenceLevelSelect = this.root.querySelector('#history-trend-confidence');
        this.timelineRangeSelect = this.root.querySelector('#history-trend-range');
        this.timelineGranularitySelect = this.root.querySelector('#history-trend-granularity');
        this.autoRefreshSelect = this.root.querySelector('#history-trend-auto-refresh');
        this.refreshProgressElement = this.root.querySelector('[data-role="trend-refresh-progress"]');

        this.metricsHost = this.root.querySelector('[data-role="trend-metrics"]');
        this.mannHost = this.root.querySelector('[data-role="mann-result"]');
        this.fftTableHost = this.root.querySelector('[data-role="fft-table"]');
        this.anomalyListHost = this.root.querySelector('[data-role="anomaly-list"]');
        this.anomalyMapHost = this.root.querySelector('[data-role="anomaly-map-chart"]');
        this.anomalyMapClusterHost = this.root.querySelector('[data-role="anomaly-clusters"]');
        this.anomalySeriesHost = this.root.querySelector('[data-role="anomaly-series-chart"]');
        this.anomalyTrendHost = this.root.querySelector('[data-role="anomaly-trend-chart"]');
        this.warningStatsHost = this.root.querySelector('[data-role="warning-stats"]');
        this.warningHistoryHost = this.root.querySelector('[data-role="warning-history"]');
        this.reasonHost = this.root.querySelector('[data-role="anomaly-reasons"]');
        this.subscriptionHost = this.root.querySelector('[data-role="anomaly-subscription"]');
        this.warningThresholdInput = this.root.querySelector('[data-role="warning-threshold"]');
        this.filterTypeSelect = this.root.querySelector('[data-role="anomaly-filter-type"]');
        this.filterSeveritySelect = this.root.querySelector('[data-role="anomaly-filter-severity"]');
        this.sortSelect = this.root.querySelector('[data-role="anomaly-sort"]');
        this.modelCompareHost = this.root.querySelector('[data-role="model-compare"]');
        this.modelVisibilityHost = this.root.querySelector('[data-role="model-visibility"]');
        this.reportHistorySummaryHost = this.root.querySelector('[data-role="report-history-summary"]');
        this.reportDownloadSummaryHost = this.root.querySelector('[data-role="report-download-summary"]');

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
                return;
            }
            if (action === 'refresh-analysis') {
                await this.handleRefreshAnalysis();
                return;
            }
            if (action === 'retry-last') {
                await this.handleRetryLast();
                return;
            }

            if (action === 'export-forecast-csv') {
                this.exportForecastCsv();
                return;
            }

            if (action === 'open-report-dialog') {
                this.openReportDialog();
                return;
            }

            if (action === 'export-chart-png') {
                this.exportChartPng();
                return;
            }

            if (action === 'export-report-pdf') {
                await this.exportReportPdf();
                return;
            }

            if (action === 'export-all') {
                await this.exportAll();
                return;
            }

            if (action === 'save-warning-threshold') {
                this.saveWarningThreshold();
                return;
            }

            if (action === 'subscribe-anomaly-notification') {
                this.subscribeNotification();
                return;
            }

            if (action === 'unsubscribe-anomaly-notification') {
                this.unsubscribeNotification();
                return;
            }

            if (action === 'focus-anomaly') {
                const rawIndex = actionEl.getAttribute('data-index');
                const index = Number(rawIndex || '-1');
                if (Number.isFinite(index) && index >= 0) {
                    this.focusAnomaly(index);
                }
                return;
            }

            if (action === 'report-history-regenerate') {
                const reportId = actionEl.getAttribute('data-report-id') || '';
                if (reportId) {
                    this.regenerateReportFromHistory(reportId);
                }
                return;
            }

            if (action === 'report-history-delete') {
                const reportId = actionEl.getAttribute('data-report-id') || '';
                if (reportId) {
                    void this.deleteReportHistoryRecord(reportId);
                }
                return;
            }
        });

        this.root.addEventListener('change', (event: Event) => {
            const target = event.target as HTMLElement | null;
            if (target && target.matches('[data-role="model-visible"]')) {
                this.syncModelVisibility();
                this.renderForControls();
                return;
            }
            this.renderAnomalyList();
            if (target && (target === this.timelineRangeSelect || target === this.timelineGranularitySelect || target === this.confidenceLevelSelect)) {
                this.renderForControls();
            }
        });

        this.autoRefreshSelect?.addEventListener('change', () => {
            this.updateAutoRefreshFromSelect();
        });

        this.root.tabIndex = 0;
        this.root.addEventListener('keydown', async (event: KeyboardEvent) => {
            if (!event.altKey) {
                return;
            }
            const key = event.key.toLowerCase();
            if (key === 't') {
                event.preventDefault();
                await this.handleAnalyze();
                return;
            }
            if (key === 'r') {
                event.preventDefault();
                await this.handleRefreshAnalysis();
                return;
            }
            if (key === 'x') {
                event.preventDefault();
                await this.exportAll();
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
        this.warningHistory = this.readWarningHistory();
        this.subscriptionConfig = this.readSubscriptionConfig();
        this.reportTemplates = this.readReportTemplates();
        this.reportHistory = this.readReportHistory();
        this.reportDownloadHistory = this.readDownloadHistory();
        const storedThreshold = Number(this.readStorage(WARNING_THRESHOLD_KEY) || '5');
        if (this.warningThresholdInput && Number.isFinite(storedThreshold) && storedThreshold >= 1) {
            this.warningThresholdInput.value = String(Math.floor(storedThreshold));
        }
        this.syncAutoRefreshSelect();
        this.updateAutoRefreshFromSelect();
        this.renderSubscription();
        this.renderReportSummaries();
    }

    private async handleLoadVersions(): Promise<void> {
        const datasetId = this.datasetInput?.value.trim() || '';
        if (!datasetId) {
            this.updateStatus('请输入数据集 ID。', 'error');
            return;
        }

        this.updateStatus('正在加载版本列表...', 'info');
        this.setLoading(true);
        await this.runWithRetry(
            async () => {
                const response = await this.apiService.listHistorySnapshots(datasetId);
                this.snapshots = Array.isArray(response.versions) ? [...response.versions] : [];
                this.snapshots.sort((a, b) => a.version - b.version);
                this.renderVersionOptions();
                this.writeStorage(LAST_DATASET_KEY, datasetId);
                this.updateStatus(`版本列表加载完成，共 ${this.snapshots.length} 个版本。`, 'success');
                this.lastRetryAction = null;
                this.resetRefreshCountdown();
            },
            '加载版本列表'
        ).catch((error) => {
            this.snapshots = [];
            this.renderVersionOptions();
            const message = error instanceof Error ? error.message : '加载版本列表失败';
            notificationManager.show({
                type: 'taskFailure',
                title: '趋势分析版本加载失败',
                body: message
            });
            this.lastRetryAction = async () => this.handleLoadVersions();
        }).finally(() => {
            this.setLoading(false);
        });
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
        this.currentThreshold = payload.anomaly_z_threshold || 2.5;

        this.updateStatus('正在执行趋势分析并生成图表...', 'info');
        this.setLoading(true);
        this.showSkeleton();
        await this.runWithRetry(
            async () => {
                const raw = await this.apiService.analyzeHistoryTrend(payload);
                const trendResult = this.normalizeTrendResult(raw);
                this.trendResult = trendResult;

                const series = await this.getTimeSeries(datasetId, trendResult.version);
                this.currentTimeSeries = [...series];
                this.modelResults = this.buildModelResults(trendResult, series);
                this.activeModelKeys = new Set(this.modelResults.slice(0, 2).map(item => item.key));
                const displaySeries = this.getFilteredTimeSeries(series);
                this.renderDashboard(trendResult, displaySeries);
                this.renderAnomalyModule(trendResult, series, payload.anomaly_z_threshold || 2.5);
                this.renderModelComparison();
                this.evaluateAndNotifyWarning(trendResult);

                this.updateStatus(`趋势分析完成（版本 v${trendResult.version}，样本 ${trendResult.sample_size} 条）。`, 'success');
                notificationManager.show({
                    type: 'taskSuccess',
                    title: '趋势分析完成',
                    body: `数据集 ${trendResult.dataset_id} 版本 v${trendResult.version} 已完成分析。`
                });
                this.lastRetryAction = null;
                this.resetRefreshCountdown();
            },
            '趋势分析'
        ).catch((error) => {
            const message = error instanceof Error ? error.message : '趋势分析失败';
            notificationManager.show({
                type: 'taskFailure',
                title: '趋势分析失败',
                body: message
            });
            this.lastRetryAction = async () => this.handleAnalyze();
        }).finally(() => {
            this.setLoading(false);
            this.hideSkeleton();
        });
    }

    private async handleRefreshAnalysis(): Promise<void> {
        if (!this.datasetInput?.value.trim()) {
            this.updateStatus('请输入数据集 ID 后再刷新。', 'error');
            return;
        }
        await this.handleLoadVersions();
        await this.handleAnalyze();
    }

    private async handleRetryLast(): Promise<void> {
        if (!this.lastRetryAction) {
            this.updateStatus('当前没有可重试的失败请求。', 'error');
            return;
        }
        await this.lastRetryAction();
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
                    const point: TrendPoint = { timestamp, value };
                    const pointId = this.asString(item.point_id);
                    const x = this.asNumber(item.x);
                    const y = this.asNumber(item.y);
                    if (pointId) {
                        point.point_id = pointId;
                    }
                    if (x !== null) {
                        point.x = x;
                    }
                    if (y !== null) {
                        point.y = y;
                    }
                    return point;
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
                accuracy: this.asNumber(evalRaw?.accuracy) || 0,
                rmse: this.asNumber(evalRaw?.rmse) || 0
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

    private renderForControls(): void {
        if (!this.trendResult) {
            return;
        }
        const filteredSeries = this.getFilteredTimeSeries(this.currentTimeSeries);
        this.renderDashboard(this.trendResult, filteredSeries);
        this.renderModelComparison();
    }

    private renderAnomalyModule(result: TrendAnalysisResult, timeSeries: TrendPoint[], threshold: number): void {
        this.anomalyViewItems = this.buildAnomalyViewItems(result, timeSeries, threshold);
        this.renderAnomalyList();
        this.renderAnomalyMap();
        this.renderAnomalySeries(timeSeries, threshold);
        this.renderWarningPanel(result, timeSeries);
        this.renderAnomalyReasons(result, timeSeries);
        this.renderSubscription();
    }

    private buildAnomalyViewItems(result: TrendAnalysisResult, timeSeries: TrendPoint[], threshold: number): AnomalyViewItem[] {
        return result.anomalies.map(item => {
            const source = timeSeries[item.index] || null;
            const scoreAbs = Math.abs(item.score);
            let severity: AnomalySeverity = 'low';
            if (scoreAbs >= threshold * 1.6) {
                severity = 'high';
            } else if (scoreAbs >= threshold * 1.2) {
                severity = 'medium';
            }

            return {
                ...item,
                severity,
                severity_label: severity === 'high' ? '高' : severity === 'medium' ? '中' : '低',
                anomaly_type_label: this.getAnomalyTypeLabel(item.anomaly_type),
                threshold,
                x: source?.x ?? null,
                y: source?.y ?? null,
                point_id: source?.point_id || '-'
            };
        });
    }

    private renderAnomalyList(): void {
        if (!this.anomalyListHost) {
            return;
        }
        if (this.anomalyViewItems.length === 0) {
            this.anomalyListHost.innerHTML = '<div class="history-empty">未检测到异常点。</div>';
            return;
        }

        const filtered = this.getFilteredAnomalies();
        if (filtered.length === 0) {
            this.anomalyListHost.innerHTML = '<div class="history-empty">当前筛选条件下暂无异常点。</div>';
            return;
        }

        const rows = filtered
            .map(
                item => `
                    <tr>
                        <td>${this.escapeHtml(this.formatDateTimeLabel(item.timestamp))}</td>
                        <td>${item.value.toFixed(4)}</td>
                        <td>${item.threshold.toFixed(2)}</td>
                        <td>${this.escapeHtml(item.anomaly_type_label)}</td>
                        <td><span class="history-anomaly-severity is-${item.severity}">${this.escapeHtml(item.severity_label)}</span></td>
                        <td>${item.score.toFixed(3)}</td>
                        <td>${item.x === null || item.y === null ? '-' : `${item.x.toFixed(4)}, ${item.y.toFixed(4)}`}</td>
                        <td><button type="button" class="history-link-btn" data-action="focus-anomaly" data-index="${item.index}">定位</button></td>
                    </tr>
                `
            )
            .join('');

        this.anomalyListHost.innerHTML = `
            <table class="history-table history-trend-anomaly-table">
                <thead>
                    <tr>
                        <th>时间戳</th>
                        <th>异常值</th>
                        <th>阈值</th>
                        <th>异常类型</th>
                        <th>严重程度</th>
                        <th>z-score</th>
                        <th>坐标</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `;
    }

    private renderAnomalyMap(): void {
        const chart = this.ensureChart('anomalyMap');
        if (!chart) {
            return;
        }

        const points = this.anomalyViewItems.filter(item => item.x !== null && item.y !== null);
        if (points.length === 0) {
            chart.setOption(
                { title: { text: '快照中未包含 x/y 坐标，无法进行地图标注', left: 'center', top: 'middle', textStyle: { fontSize: 12 } } },
                { notMerge: true }
            );
            if (this.anomalyMapClusterHost) {
                this.anomalyMapClusterHost.innerHTML = '<div class="history-empty">暂无可聚合的坐标异常点。</div>';
            }
            return;
        }

        const clusters = this.buildAnomalyClusters(points);
        if (this.anomalyMapClusterHost) {
            if (clusters.length === 0) {
                this.anomalyMapClusterHost.innerHTML = '<div class="history-empty">当前无密集区域聚合。</div>';
            } else {
                const clusterRows = clusters
                    .map(cluster => `<li>聚合 ${cluster.id}: ${cluster.count} 个点，最高分 ${cluster.maxScore.toFixed(2)}</li>`)
                    .join('');
                this.anomalyMapClusterHost.innerHTML = `<ul>${clusterRows}</ul>`;
            }
        }

        const severityWeight = (severity: AnomalySeverity): number => (severity === 'high' ? 3 : severity === 'medium' ? 2 : 1);
        chart.setOption(
            {
                tooltip: {
                    trigger: 'item',
                    formatter: (params: { data?: unknown[] }) => {
                        const data = Array.isArray(params.data) ? params.data : [];
                        const timestamp = String(data[4] || '-');
                        const value = Number(data[2] || 0);
                        const score = Number(data[3] || 0);
                        const severity = String(data[5] || '-');
                        return `时间: ${timestamp}<br/>值: ${value.toFixed(4)}<br/>z-score: ${score.toFixed(3)}<br/>严重程度: ${severity}`;
                    }
                },
                xAxis: { type: 'value', name: 'X' },
                yAxis: { type: 'value', name: 'Y' },
                legend: { top: 4, data: ['异常点', '聚合点'] },
                grid: { left: 45, right: 20, top: 38, bottom: 38 },
                dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 12 }],
                series: [
                    {
                        name: '异常点',
                        type: 'scatter',
                        data: points.map(item => [item.x, item.y, item.value, item.score, this.formatDateTimeLabel(item.timestamp), item.severity_label]),
                        symbolSize: (value: number[]) => 8 + severityWeight(this.getSeverityByScore(Math.abs(Number(value[3] || 0)), this.currentThreshold)) * 3,
                        itemStyle: {
                            color: (params: { data?: unknown[] }) => {
                                const score = Math.abs(Number((params.data || [])[3] || 0));
                                const severity = this.getSeverityByScore(score, this.currentThreshold);
                                return severity === 'high' ? '#dc2626' : severity === 'medium' ? '#f59e0b' : '#2563eb';
                            }
                        }
                    },
                    {
                        name: '聚合点',
                        type: 'scatter',
                        data: clusters.map(cluster => [cluster.centerX, cluster.centerY, cluster.count, cluster.maxScore, cluster.id]),
                        symbolSize: (value: number[]) => 12 + Number(value[2] || 0) * 2,
                        label: { show: true, formatter: '{@[2]}', color: '#111827', fontSize: 10 },
                        itemStyle: { color: 'rgba(22,163,74,0.6)', borderColor: '#166534', borderWidth: 1 }
                    }
                ]
            },
            { notMerge: true }
        );
    }

    private renderAnomalySeries(timeSeries: TrendPoint[], threshold: number): void {
        const chart = this.ensureChart('anomalySeries');
        if (!chart) {
            return;
        }
        if (timeSeries.length === 0) {
            chart.setOption(
                { title: { text: '无时间序列数据', left: 'center', top: 'middle', textStyle: { fontSize: 12 } } },
                { notMerge: true }
            );
            return;
        }

        const values = timeSeries.map(item => item.value);
        const mean = values.reduce((sum, item) => sum + item, 0) / Math.max(1, values.length);
        const std = this.computeStd(values);
        const thresholdUpper = mean + threshold * std;
        const thresholdLower = mean - threshold * std;
        const labels = timeSeries.map(item => this.formatDateLabel(item.timestamp));
        const anomalyIndex = new Set(this.anomalyViewItems.map(item => item.index));
        const anomalyMarks = values
            .map((value, index) => (anomalyIndex.has(index) ? [index, value] : null))
            .filter((item): item is [number, number] => item !== null);

        chart.setOption(
            {
                tooltip: { trigger: 'axis' },
                legend: { top: 4, data: ['原始值', '异常点', '上阈值', '下阈值'] },
                grid: { left: 45, right: 20, top: 36, bottom: 48 },
                dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 12 }],
                xAxis: { type: 'category', data: labels },
                yAxis: { type: 'value', scale: true },
                series: [
                    { name: '原始值', type: 'line', data: values, smooth: true, symbol: 'none', lineStyle: { color: '#1f2937' } },
                    { name: '上阈值', type: 'line', data: Array(values.length).fill(thresholdUpper), symbol: 'none', lineStyle: { color: '#f59e0b', type: 'dashed' } },
                    { name: '下阈值', type: 'line', data: Array(values.length).fill(thresholdLower), symbol: 'none', lineStyle: { color: '#f59e0b', type: 'dashed' } },
                    { name: '异常点', type: 'scatter', data: anomalyMarks, symbolSize: 9, itemStyle: { color: '#dc2626' } }
                ]
            },
            { notMerge: true }
        );
    }

    private renderWarningPanel(result: TrendAnalysisResult, timeSeries: TrendPoint[]): void {
        const warningThreshold = this.getWarningThreshold();
        const highCount = this.anomalyViewItems.filter(item => item.severity === 'high').length;
        const anomalyRate = timeSeries.length > 0 ? (this.anomalyViewItems.length / timeSeries.length) * 100 : 0;

        if (this.warningStatsHost) {
            this.warningStatsHost.innerHTML = `
                <div class="history-trend-warning-card"><span>异常总数</span><strong>${this.anomalyViewItems.length}</strong></div>
                <div class="history-trend-warning-card"><span>高危异常</span><strong>${highCount}</strong></div>
                <div class="history-trend-warning-card"><span>异常占比</span><strong>${anomalyRate.toFixed(2)}%</strong></div>
                <div class="history-trend-warning-card"><span>当前阈值</span><strong>${warningThreshold}</strong></div>
            `;
        }

        this.renderAnomalyTrendChart();
        this.renderWarningHistory();

        if (this.anomalyViewItems.length >= warningThreshold) {
            this.recordWarning({
                timestamp: new Date().toISOString(),
                dataset_id: result.dataset_id,
                version: result.version,
                anomaly_count: this.anomalyViewItems.length,
                threshold: warningThreshold,
                level: highCount > 0 ? 'high' : 'normal'
            });
            this.renderWarningHistory();
        }
    }

    private renderAnomalyTrendChart(): void {
        const chart = this.ensureChart('anomalyTrend');
        if (!chart) {
            return;
        }
        if (this.anomalyViewItems.length === 0) {
            chart.setOption(
                { title: { text: '暂无异常频率趋势', left: 'center', top: 'middle', textStyle: { fontSize: 12 } } },
                { notMerge: true }
            );
            return;
        }

        const dailyMap = new Map<string, number>();
        this.anomalyViewItems.forEach(item => {
            const day = this.formatDateLabel(item.timestamp);
            dailyMap.set(day, (dailyMap.get(day) || 0) + 1);
        });
        const labels = Array.from(dailyMap.keys()).sort();
        const values = labels.map(label => dailyMap.get(label) || 0);

        chart.setOption(
            {
                tooltip: { trigger: 'axis' },
                grid: { left: 45, right: 20, top: 24, bottom: 38 },
                xAxis: { type: 'category', data: labels },
                yAxis: { type: 'value', minInterval: 1, name: '异常次数' },
                series: [{ type: 'line', data: values, smooth: true, itemStyle: { color: '#dc2626' }, areaStyle: { color: 'rgba(220,38,38,0.12)' } }]
            },
            { notMerge: true }
        );
    }

    private renderWarningHistory(): void {
        if (!this.warningHistoryHost) {
            return;
        }
        if (this.warningHistory.length === 0) {
            this.warningHistoryHost.innerHTML = '<div class="history-empty">暂无预警历史记录。</div>';
            return;
        }

        const rows = this.warningHistory
            .slice(0, 8)
            .map(item => `<li>${this.formatDateTimeLabel(item.timestamp)} | ${this.escapeHtml(item.dataset_id)} v${item.version} | 异常 ${item.anomaly_count}/${item.threshold} | 级别 ${item.level === 'high' ? '高' : '一般'}</li>`)
            .join('');
        this.warningHistoryHost.innerHTML = `<ul>${rows}</ul>`;
    }

    private renderAnomalyReasons(result: TrendAnalysisResult, timeSeries: TrendPoint[]): void {
        if (!this.reasonHost) {
            return;
        }

        if (this.anomalyViewItems.length === 0) {
            this.reasonHost.innerHTML = '<div class="history-empty">未检测到异常点，暂无原因分析。</div>';
            return;
        }

        const highCount = this.anomalyViewItems.filter(item => item.severity === 'high').length;
        const positiveCount = this.anomalyViewItems.filter(item => item.anomaly_type === 'positive').length;
        const negativeCount = this.anomalyViewItems.filter(item => item.anomaly_type === 'negative').length;
        const avgValue = timeSeries.length > 0 ? timeSeries.reduce((sum, item) => sum + item.value, 0) / timeSeries.length : 0;
        const latest = this.anomalyViewItems.slice().sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp))[0];

        const reasons = [
            `高危异常占比 ${(highCount / Math.max(1, this.anomalyViewItems.length) * 100).toFixed(1)}%，可能存在突发性扰动或采样设备漂移。`,
            `正异常 ${positiveCount} 个、负异常 ${negativeCount} 个，说明系统偏移方向${positiveCount >= negativeCount ? '偏上行' : '偏下行'}。`,
            `序列均值约 ${avgValue.toFixed(4)}，最近一次异常时间为 ${this.formatDateTimeLabel(latest.timestamp)}。`
        ];

        const measures = [
            '核查异常时段的设备校准和采样环境变化。',
            '结合周期分量复核是否存在季节性导致的误报。',
            '对高危异常点进行人工复测并增加采样密度。'
        ];

        this.reasonHost.innerHTML = `
            <div class="history-trend-reason-grid">
                <div>
                    <h5>可能原因</h5>
                    <ul>${reasons.map(item => `<li>${this.escapeHtml(item)}</li>`).join('')}</ul>
                </div>
                <div>
                    <h5>相关因素与建议</h5>
                    <ul>${measures.map(item => `<li>${this.escapeHtml(item)}</li>`).join('')}</ul>
                </div>
            </div>
        `;
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
            { label: '预测准确率', value: `${result.evaluation.accuracy.toFixed(2)}%` },
            { label: 'RMSE', value: `${(result.evaluation.rmse || 0).toFixed(4)}` },
            { label: 'MAE', value: `${result.evaluation.mae.toFixed(4)}` },
            { label: 'MAPE', value: `${result.evaluation.mape.toFixed(2)}%` }
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

        const labels = this.buildAggregatedLabels(timeSeries);
        const values = timeSeries.map(item => item.value);
        const trendLine = values.map((_, index) => result.linear_trend.slope * index + result.linear_trend.intercept);
        const residualStd = this.computeResidualStd(values, trendLine);
        const confidenceZ = this.getConfidenceZValue();
        const upper = trendLine.map(item => item + residualStd * confidenceZ);
        const lower = trendLine.map(item => item - residualStd * confidenceZ);

        const forecastLabels = result.forecast.map(item => this.formatDateLabel(item.timestamp));
        const serverModel = this.modelResults.find(item => item.key === 'server');
        const forecastValues = serverModel ? serverModel.values : result.forecast.map(item => item.predicted_value);
        const forecastUpper = result.forecast.map(item => {
            const std = Math.max(0, (item.upper_bound - item.lower_bound) / (2 * 1.96));
            return item.predicted_value + std * confidenceZ;
        });
        const forecastLower = result.forecast.map(item => {
            const std = Math.max(0, (item.upper_bound - item.lower_bound) / (2 * 1.96));
            return item.predicted_value - std * confidenceZ;
        });

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
        const modelSeries = this.getActiveModelSeries(values.length);

        chart.setOption(
            {
                tooltip: { trigger: 'axis' },
                legend: {
                    top: 4,
                    data: ['原始值', '趋势线', '趋势置信上界', '趋势置信下界', '预测值', '预测上界', '预测下界', ...modelSeries.map(item => String(item.name || '')), '异常点']
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
                    },
                    ...modelSeries
                ],
                graphic: [
                    {
                        type: 'text',
                        left: 50,
                        top: 28,
                        style: {
                            text: `趋势方程：${equation} | 置信水平 ${Math.round(this.getConfidenceLevel() * 100)}%`,
                            fontSize: 12,
                            fill: '#374151'
                        }
                    }
                ]
            },
            { notMerge: true }
        );
    }

    private getConfidenceLevel(): number {
        const value = Number(this.confidenceLevelSelect?.value || '0.95');
        if (value === 0.9 || value === 0.95 || value === 0.99) {
            return value;
        }
        return 0.95;
    }

    private getConfidenceZValue(): number {
        const level = this.getConfidenceLevel();
        if (level === 0.9) {
            return 1.645;
        }
        if (level === 0.99) {
            return 2.576;
        }
        return 1.96;
    }

    private getFilteredTimeSeries(source: TrendPoint[]): TrendPoint[] {
        if (source.length === 0) {
            return [];
        }
        const rangeValue = this.timelineRangeSelect?.value || 'all';
        let timeFiltered = [...source];
        if (rangeValue !== 'all') {
            const days = Number(rangeValue);
            if (Number.isFinite(days) && days > 0) {
                const maxTs = Date.parse(source[source.length - 1].timestamp);
                const cutoff = maxTs - days * 24 * 60 * 60 * 1000;
                timeFiltered = source.filter(item => {
                    const ts = Date.parse(item.timestamp);
                    return Number.isFinite(ts) && ts >= cutoff;
                });
            }
        }
        return this.aggregateTimeSeries(timeFiltered, this.timelineGranularitySelect?.value || 'day');
    }

    private aggregateTimeSeries(source: TrendPoint[], granularity: string): TrendPoint[] {
        if (granularity === 'day') {
            return [...source];
        }
        const buckets = new Map<string, TrendPoint[]>();
        source.forEach(item => {
            const date = new Date(item.timestamp);
            if (Number.isNaN(date.getTime())) {
                return;
            }
            let bucketKey = '';
            if (granularity === 'week') {
                const start = new Date(date);
                const day = start.getDay();
                const offset = day === 0 ? -6 : 1 - day;
                start.setDate(start.getDate() + offset);
                bucketKey = this.formatDateLabel(start.toISOString());
            } else {
                bucketKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-01`;
            }
            const list = buckets.get(bucketKey) || [];
            list.push(item);
            buckets.set(bucketKey, list);
        });
        return Array.from(buckets.entries())
            .sort((a, b) => Date.parse(a[0]) - Date.parse(b[0]))
            .map(([bucket, items], index) => {
                const avg = items.reduce((sum, item) => sum + item.value, 0) / Math.max(1, items.length);
                return {
                    timestamp: bucket,
                    value: avg,
                    point_id: `agg-${granularity}-${index}`
                };
            });
    }

    private buildAggregatedLabels(timeSeries: TrendPoint[]): string[] {
        return timeSeries.map(item => this.formatDateLabel(item.timestamp));
    }

    private buildModelResults(result: TrendAnalysisResult, timeSeries: TrendPoint[]): ForecastModelResult[] {
        const horizon = result.forecast.length;
        const values = timeSeries.map(item => item.value);
        if (horizon <= 0 || values.length === 0) {
            return [];
        }
        const serverValues = result.forecast.map(item => item.predicted_value);
        const holdout = Math.min(Math.max(3, Math.floor(horizon / 2)), Math.max(3, Math.floor(values.length / 3)));
        const train = values.slice(0, Math.max(1, values.length - holdout));
        const actual = values.slice(Math.max(0, values.length - holdout));
        const linearPred = this.predictLinear(train, holdout);
        const movingAvgPred = this.predictMovingAverage(train, holdout);
        const naivePred = this.predictNaive(train, holdout);
        return [
            {
                key: 'server',
                name: '服务端主模型',
                values: serverValues,
                evaluation: result.evaluation
            },
            {
                key: 'linear',
                name: '线性回归基线',
                values: this.predictLinear(values, horizon),
                evaluation: this.evaluatePredictions(actual, linearPred)
            },
            {
                key: 'moving_avg',
                name: '移动平均基线',
                values: this.predictMovingAverage(values, horizon),
                evaluation: this.evaluatePredictions(actual, movingAvgPred)
            },
            {
                key: 'naive',
                name: '朴素持平基线',
                values: this.predictNaive(values, horizon),
                evaluation: this.evaluatePredictions(actual, naivePred)
            }
        ];
    }

    private predictLinear(values: number[], horizon: number): number[] {
        if (values.length === 0 || horizon <= 0) {
            return [];
        }
        const n = values.length;
        const xMean = (n - 1) / 2;
        const yMean = values.reduce((sum, item) => sum + item, 0) / n;
        let numerator = 0;
        let denominator = 0;
        values.forEach((value, index) => {
            numerator += (index - xMean) * (value - yMean);
            denominator += Math.pow(index - xMean, 2);
        });
        const slope = denominator > 0 ? numerator / denominator : 0;
        const intercept = yMean - slope * xMean;
        return Array.from({ length: horizon }, (_, idx) => intercept + slope * (n + idx));
    }

    private predictMovingAverage(values: number[], horizon: number): number[] {
        if (values.length === 0 || horizon <= 0) {
            return [];
        }
        const windowSize = Math.max(2, Math.min(7, values.length));
        const base = values.slice(values.length - windowSize);
        const avg = base.reduce((sum, item) => sum + item, 0) / base.length;
        return Array(horizon).fill(avg);
    }

    private predictNaive(values: number[], horizon: number): number[] {
        if (values.length === 0 || horizon <= 0) {
            return [];
        }
        return Array(horizon).fill(values[values.length - 1]);
    }

    private evaluatePredictions(actual: number[], predicted: number[]): ForecastEvaluation {
        const length = Math.min(actual.length, predicted.length);
        if (length === 0) {
            return { mae: 0, mape: 0, r2: 0, accuracy: 0, rmse: 0 };
        }
        const actualSlice = actual.slice(0, length);
        const predSlice = predicted.slice(0, length);
        const absErrors = actualSlice.map((item, index) => Math.abs(item - predSlice[index]));
        const squaredErrors = actualSlice.map((item, index) => Math.pow(item - predSlice[index], 2));
        const mae = absErrors.reduce((sum, item) => sum + item, 0) / length;
        const rmse = Math.sqrt(squaredErrors.reduce((sum, item) => sum + item, 0) / length);
        const mapeValues = actualSlice
            .map((item, index) => (Math.abs(item) > 1e-8 ? (Math.abs(item - predSlice[index]) / Math.abs(item)) * 100 : null))
            .filter((item): item is number => item !== null);
        const mape = mapeValues.length > 0 ? mapeValues.reduce((sum, item) => sum + item, 0) / mapeValues.length : 0;
        const meanActual = actualSlice.reduce((sum, item) => sum + item, 0) / length;
        const ssRes = squaredErrors.reduce((sum, item) => sum + item, 0);
        const ssTot = actualSlice.reduce((sum, item) => sum + Math.pow(item - meanActual, 2), 0);
        const r2 = ssTot > 0 ? 1 - ssRes / ssTot : 0;
        const accuracy = Math.max(0, 100 - mape);
        return { mae, mape, r2, accuracy, rmse };
    }

    private renderModelComparison(): void {
        if (!this.modelCompareHost || !this.modelVisibilityHost) {
            return;
        }
        if (this.modelResults.length === 0) {
            this.modelVisibilityHost.innerHTML = '<div class="history-empty">执行趋势分析后展示模型切换。</div>';
            this.modelCompareHost.innerHTML = '<div class="history-empty">执行趋势分析后展示模型性能对比。</div>';
            return;
        }
        const best = this.modelResults
            .slice()
            .sort((a, b) => (a.evaluation.rmse || Number.MAX_VALUE) - (b.evaluation.rmse || Number.MAX_VALUE))[0];
        this.modelVisibilityHost.innerHTML = this.modelResults
            .map(item => {
                const checked = this.activeModelKeys.has(item.key) ? 'checked' : '';
                return `<label><input type="checkbox" data-role="model-visible" value="${this.escapeHtml(item.key)}" ${checked}> ${this.escapeHtml(item.name)}</label>`;
            })
            .join('');
        const rows = this.modelResults
            .map(item => {
                const isBest = item.key === best.key ? 'is-best' : '';
                return `
                    <tr class="${isBest}">
                        <td>${this.escapeHtml(item.name)}${isBest ? '（推荐）' : ''}</td>
                        <td>${(item.evaluation.rmse || 0).toFixed(4)}</td>
                        <td>${item.evaluation.mae.toFixed(4)}</td>
                        <td>${item.evaluation.mape.toFixed(2)}%</td>
                        <td>${item.evaluation.r2.toFixed(4)}</td>
                        <td>${item.evaluation.accuracy.toFixed(2)}%</td>
                    </tr>
                `;
            })
            .join('');
        this.modelCompareHost.innerHTML = `
            <table class="history-table history-trend-model-compare-table">
                <thead>
                    <tr>
                        <th>模型</th>
                        <th>RMSE</th>
                        <th>MAE</th>
                        <th>MAPE</th>
                        <th>R²</th>
                        <th>准确率</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `;
    }

    private syncModelVisibility(): void {
        if (!this.modelVisibilityHost) {
            return;
        }
        const selected = Array.from(this.modelVisibilityHost.querySelectorAll('[data-role="model-visible"]'))
            .filter(node => (node as HTMLInputElement).checked)
            .map(node => (node as HTMLInputElement).value);
        this.activeModelKeys = new Set(selected);
    }

    private getActiveModelSeries(prefixLength: number): Array<Record<string, unknown>> {
        const palette: Record<string, string> = {
            linear: '#7c3aed',
            moving_avg: '#ea580c',
            naive: '#0891b2'
        };
        const padding = Array(prefixLength).fill(null);
        return this.modelResults
            .filter(item => item.key !== 'server' && this.activeModelKeys.has(item.key))
            .map(item => ({
                name: item.name,
                type: 'line',
                data: [...padding, ...item.values],
                smooth: true,
                symbol: 'none',
                lineStyle: { width: 2, type: 'dashed', color: palette[item.key] || '#6b7280' }
            }));
    }

    private exportForecastCsv(): void {
        if (!this.trendResult || this.trendResult.forecast.length === 0) {
            this.updateStatus('暂无预测结果可导出。', 'error');
            return;
        }
        const header = ['timestamp', 'server_prediction', 'lower_bound', 'upper_bound', 'linear_baseline', 'moving_avg_baseline', 'naive_baseline'];
        const modelMap = new Map(this.modelResults.map(item => [item.key, item]));
        const rows = this.trendResult.forecast.map((item, index) => {
            const linear = modelMap.get('linear')?.values[index] ?? '';
            const movingAvg = modelMap.get('moving_avg')?.values[index] ?? '';
            const naive = modelMap.get('naive')?.values[index] ?? '';
            return [item.timestamp, item.predicted_value, item.lower_bound, item.upper_bound, linear, movingAvg, naive].join(',');
        });
        const content = [header.join(','), ...rows].join('\n');
        this.downloadFile(`${this.trendResult.dataset_id}_v${this.trendResult.version}_forecast.csv`, content, 'text/csv;charset=utf-8');
        this.updateStatus('预测 CSV 导出成功。', 'success');
    }

    private exportChartPng(): void {
        if (!this.linearChart?.getDataURL) {
            this.updateStatus('图表尚未渲染，无法导出 PNG。', 'error');
            return;
        }
        const dataUrl = this.linearChart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#ffffff' });
        const anchor = document.createElement('a');
        const result = this.trendResult;
        const fileName = result ? `${result.dataset_id}_v${result.version}_forecast.png` : 'forecast.png';
        anchor.href = dataUrl;
        anchor.download = fileName;
        anchor.click();
        this.updateStatus('预测图表 PNG 导出成功。', 'success');
    }

    private async exportReportPdf(): Promise<void> {
        if (!this.trendResult) {
            this.updateStatus('请先执行趋势分析再导出报告。', 'error');
            return;
        }
        const result = this.trendResult;
        let reportContent = '';
        try {
            const report = await this.apiService.generateHistoryAnalysisReport({
                dataset_id: result.dataset_id,
                from_version: Math.max(1, result.version - 1),
                to_version: result.version,
                forecast_horizon: result.forecast.length
            });
            reportContent = this.asString(report.report) || this.asString(report.content) || '';
        } catch {
            reportContent = '';
        }

        const html = `
            <html>
            <head><title>预测报告</title><style>body{font-family:Arial,sans-serif;padding:24px;color:#111}h1,h2{margin:0 0 12px}pre{white-space:pre-wrap;line-height:1.6;font-size:12px;background:#f8fafc;padding:12px;border:1px solid #e5e7eb;border-radius:6px}</style></head>
            <body>
                <h1>预测结果报告</h1>
                <p>数据集：${this.escapeHtml(result.dataset_id)}，版本：v${result.version}，时间：${this.escapeHtml(new Date().toLocaleString())}</p>
                <h2>关键指标</h2>
                <ul>
                    <li>准确率：${result.evaluation.accuracy.toFixed(2)}%</li>
                    <li>RMSE：${(result.evaluation.rmse || 0).toFixed(4)}</li>
                    <li>MAE：${result.evaluation.mae.toFixed(4)}</li>
                    <li>MAPE：${result.evaluation.mape.toFixed(2)}%</li>
                    <li>R²：${result.evaluation.r2.toFixed(4)}</li>
                </ul>
                <h2>报告正文</h2>
                <pre>${this.escapeHtml(reportContent || '后端未返回文本报告，已导出关键指标与预测图表。')}</pre>
                <p>提示：打开打印对话框后选择“另存为 PDF”。</p>
            </body></html>
        `;
        const printWindow = window.open('', '_blank', 'width=960,height=760');
        if (!printWindow) {
            this.updateStatus('浏览器拦截了弹窗，无法导出 PDF。', 'error');
            return;
        }
        printWindow.document.write(html);
        printWindow.document.close();
        printWindow.focus();
        printWindow.print();
        this.updateStatus('已打开报告打印窗口，请保存为 PDF。', 'success');
    }

    private async exportAll(): Promise<void> {
        this.exportForecastCsv();
        this.exportChartPng();
        await this.exportReportPdf();
    }

    private openReportDialog(): void {
        if (!this.root) {
            return;
        }
        if (!this.trendResult) {
            this.updateStatus('请先执行趋势分析，再生成报告。', 'error');
            return;
        }
        if (!this.reportDialogOverlay) {
            this.reportDialogOverlay = document.createElement('div');
            this.reportDialogOverlay.className = 'modal-overlay history-report-dialog-overlay';
            this.reportDialogOverlay.innerHTML = this.buildReportDialogHtml();
            this.bindReportDialogEvents();
            document.body.appendChild(this.reportDialogOverlay);
        }
        this.renderReportDialog();
        requestAnimationFrame(() => this.reportDialogOverlay?.classList.add('modal-show'));
    }

    private closeReportDialog(): void {
        if (!this.reportDialogOverlay) {
            return;
        }
        this.reportDialogOverlay.classList.remove('modal-show');
        setTimeout(() => {
            this.reportDialogOverlay?.remove();
            this.reportDialogOverlay = null;
            this.reportPreviewChart?.dispose();
            this.reportPreviewChart = null;
        }, 180);
    }

    private buildReportDialogHtml(): string {
        return `
            <div class="modal-content history-report-dialog">
                <h2 class="modal-title">历史分析报告生成与导出</h2>
                <div class="history-report-grid">
                    <section class="history-report-section">
                        <h4>模板与参数</h4>
                        <div class="integration-field">
                            <label class="integration-field-label" for="history-report-template">报告模板</label>
                            <select id="history-report-template" class="select integration-input"></select>
                        </div>
                        <div class="history-report-template-preview" data-role="report-template-preview"></div>
                        <div class="history-report-template-actions">
                            <input id="history-report-template-file" type="file" accept=".txt,.md,.html,.json" class="input integration-input">
                            <button type="button" class="btn btn-secondary" data-action="report-template-upload">上传自定义模板</button>
                            <button type="button" class="btn btn-secondary" data-action="report-template-delete">删除当前自定义模板</button>
                        </div>

                        <div class="history-trend-param-grid">
                            <div class="integration-field">
                                <label class="integration-field-label" for="history-report-title">报告标题</label>
                                <input id="history-report-title" class="input integration-input" type="text" placeholder="请输入报告标题">
                            </div>
                            <div class="integration-field">
                                <label class="integration-field-label" for="history-report-from">起始版本</label>
                                <select id="history-report-from" class="select integration-input"></select>
                            </div>
                            <div class="integration-field">
                                <label class="integration-field-label" for="history-report-to">结束版本</label>
                                <select id="history-report-to" class="select integration-input"></select>
                            </div>
                            <div class="integration-field">
                                <label class="integration-field-label" for="history-report-analysis">分析类型</label>
                                <select id="history-report-analysis" class="select integration-input">
                                    <option value="compare">对比分析</option>
                                    <option value="trend" selected>趋势分析</option>
                                    <option value="forecast">预测分析</option>
                                </select>
                            </div>
                            <div class="integration-field">
                                <label class="integration-field-label" for="history-report-chart">图表类型</label>
                                <select id="history-report-chart" class="select integration-input">
                                    <option value="line" selected>折线图</option>
                                    <option value="bar">柱状图</option>
                                    <option value="area">面积图</option>
                                </select>
                            </div>
                            <div class="integration-field">
                                <label class="integration-field-label" for="history-report-format">输出格式</label>
                                <select id="history-report-format" class="select integration-input">
                                    <option value="pdf" selected>PDF</option>
                                    <option value="html">HTML</option>
                                    <option value="word">Word</option>
                                </select>
                            </div>
                        </div>
                        <div class="history-report-metric-group" data-role="report-metrics-group"></div>

                        <div class="history-report-progress">
                            <div class="history-report-progress-bar"><div class="history-report-progress-fill" data-role="report-progress-fill"></div></div>
                            <span data-role="report-progress-text">等待生成</span>
                        </div>
                        <div class="integration-actions">
                            <button type="button" class="btn btn-primary" data-action="report-generate">生成报告</button>
                            <button type="button" class="btn btn-secondary" data-action="report-download-current">下载当前格式</button>
                            <button type="button" class="btn btn-secondary" data-action="report-download-batch">批量下载(PDF/HTML/Word)</button>
                        </div>
                    </section>

                    <section class="history-report-section">
                        <h4>报告预览</h4>
                        <div class="history-report-preview-controls">
                            <select class="select integration-input" data-role="report-preview-page">
                                <option value="summary">摘要页</option>
                                <option value="metrics">指标页</option>
                                <option value="full">正文页</option>
                            </select>
                            <label class="history-report-zoom-label">缩放
                                <input type="range" min="0.8" max="1.8" step="0.1" value="1" data-role="report-preview-zoom">
                            </label>
                        </div>
                        <div class="history-report-preview-wrap">
                            <div class="history-report-preview-content" data-role="report-preview-content"></div>
                        </div>
                        <div class="history-report-preview-chart" data-role="report-preview-chart"></div>
                    </section>
                </div>

                <section class="history-report-section">
                    <h4>报告生成历史</h4>
                    <div data-role="report-history-list"></div>
                </section>
                <section class="history-report-section">
                    <h4>下载历史</h4>
                    <div class="integration-actions">
                        <button type="button" class="btn btn-secondary" data-action="report-download-history-clear">清空下载历史</button>
                    </div>
                    <div data-role="report-download-history-list"></div>
                </section>
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary" data-action="report-dialog-close">关闭</button>
                </div>
            </div>
        `;
    }

    private bindReportDialogEvents(): void {
        if (!this.reportDialogOverlay) {
            return;
        }
        this.reportDialogOverlay.addEventListener('click', async (event: MouseEvent) => {
            const target = event.target as HTMLElement | null;
            if (!target) {
                return;
            }
            if (target === this.reportDialogOverlay) {
                this.closeReportDialog();
                return;
            }
            const actionEl = target.closest('[data-action]') as HTMLElement | null;
            const action = actionEl?.getAttribute('data-action') || '';
            if (!action) {
                return;
            }
            if (action === 'report-dialog-close') {
                this.closeReportDialog();
                return;
            }
            if (action === 'report-template-upload') {
                await this.uploadReportTemplate();
                return;
            }
            if (action === 'report-template-delete') {
                await this.deleteCurrentTemplate();
                return;
            }
            if (action === 'report-generate') {
                await this.handleGenerateReportFromDialog();
                return;
            }
            if (action === 'report-download-current') {
                await this.downloadCurrentReport(false);
                return;
            }
            if (action === 'report-download-batch') {
                await this.downloadCurrentReport(true);
                return;
            }
            if (action === 'report-history-open') {
                const reportId = actionEl?.getAttribute('data-report-id') || '';
                this.openReportFromHistory(reportId);
                return;
            }
            if (action === 'report-history-regenerate') {
                const reportId = actionEl?.getAttribute('data-report-id') || '';
                this.regenerateReportFromHistory(reportId);
                return;
            }
            if (action === 'report-history-delete') {
                const reportId = actionEl?.getAttribute('data-report-id') || '';
                await this.deleteReportHistoryRecord(reportId);
                return;
            }
            if (action === 'report-download-history-clear') {
                this.reportDownloadHistory = [];
                this.writeStorage(REPORT_DOWNLOAD_HISTORY_KEY, JSON.stringify(this.reportDownloadHistory));
                this.renderReportDownloadHistory();
                this.renderReportSummaries();
            }
        });

        this.reportDialogOverlay.addEventListener('change', () => {
            this.reportCurrentConfig = this.readReportConfigFromDialog();
            this.renderTemplatePreview();
            this.renderReportPreview();
        });
        this.reportDialogOverlay.addEventListener('input', () => {
            this.reportCurrentConfig = this.readReportConfigFromDialog();
            this.renderReportPreview();
        });
    }

    private renderReportDialog(): void {
        if (!this.reportDialogOverlay || !this.trendResult) {
            return;
        }
        const templateSelect = this.reportDialogOverlay.querySelector('#history-report-template') as HTMLSelectElement | null;
        if (templateSelect) {
            templateSelect.innerHTML = this.reportTemplates
                .map(item => `<option value="${this.escapeHtml(item.id)}">${this.escapeHtml(item.name)}${item.builtIn ? '（内置）' : ''}</option>`)
                .join('');
        }

        const fromSelect = this.reportDialogOverlay.querySelector('#history-report-from') as HTMLSelectElement | null;
        const toSelect = this.reportDialogOverlay.querySelector('#history-report-to') as HTMLSelectElement | null;
        const versions = this.snapshots.length > 0 ? this.snapshots.map(item => item.version) : [Math.max(1, this.trendResult.version - 1), this.trendResult.version];
        const options = Array.from(new Set(versions)).sort((a, b) => a - b).map(item => `<option value="${item}">v${item}</option>`).join('');
        if (fromSelect) {
            fromSelect.innerHTML = options;
            fromSelect.value = String(Math.max(1, this.trendResult.version - 1));
        }
        if (toSelect) {
            toSelect.innerHTML = options;
            toSelect.value = String(this.trendResult.version);
        }

        const titleInput = this.reportDialogOverlay.querySelector('#history-report-title') as HTMLInputElement | null;
        if (titleInput) {
            titleInput.value = `${this.trendResult.dataset_id} 历史分析报告 v${this.trendResult.version}`;
        }

        const metricHost = this.reportDialogOverlay.querySelector('[data-role="report-metrics-group"]');
        if (metricHost) {
            metricHost.innerHTML = `
                <label><input type="checkbox" data-role="report-metric" value="accuracy" checked> 准确率</label>
                <label><input type="checkbox" data-role="report-metric" value="rmse" checked> RMSE</label>
                <label><input type="checkbox" data-role="report-metric" value="mae" checked> MAE</label>
                <label><input type="checkbox" data-role="report-metric" value="mape" checked> MAPE</label>
                <label><input type="checkbox" data-role="report-metric" value="r2" checked> R²</label>
                <label><input type="checkbox" data-role="report-metric" value="anomaly_count" checked> 异常点数量</label>
            `;
        }

        this.reportCurrentConfig = this.readReportConfigFromDialog();
        this.renderTemplatePreview();
        this.renderReportPreview();
        this.renderReportHistoryList();
        this.renderReportDownloadHistory();
        this.setReportProgress(0, '等待生成');
    }

    private readReportConfigFromDialog(): ReportConfigState | null {
        if (!this.reportDialogOverlay || !this.trendResult) {
            return null;
        }
        const title = (this.reportDialogOverlay.querySelector('#history-report-title') as HTMLInputElement | null)?.value.trim() || '';
        const fromVersion = Number((this.reportDialogOverlay.querySelector('#history-report-from') as HTMLSelectElement | null)?.value || this.trendResult.version);
        const toVersion = Number((this.reportDialogOverlay.querySelector('#history-report-to') as HTMLSelectElement | null)?.value || this.trendResult.version);
        const analysisTypeRaw = (this.reportDialogOverlay.querySelector('#history-report-analysis') as HTMLSelectElement | null)?.value || 'trend';
        const chartTypeRaw = (this.reportDialogOverlay.querySelector('#history-report-chart') as HTMLSelectElement | null)?.value || 'line';
        const outputFormatRaw = (this.reportDialogOverlay.querySelector('#history-report-format') as HTMLSelectElement | null)?.value || 'pdf';
        const metrics = Array.from(this.reportDialogOverlay.querySelectorAll('[data-role="report-metric"]'))
            .filter(node => (node as HTMLInputElement).checked)
            .map(node => (node as HTMLInputElement).value);

        return {
            reportTitle: title || `${this.trendResult.dataset_id} 历史分析报告`,
            fromVersion: Math.max(1, Math.floor(fromVersion)),
            toVersion: Math.max(1, Math.floor(toVersion)),
            analysisType: analysisTypeRaw === 'compare' || analysisTypeRaw === 'forecast' ? analysisTypeRaw : 'trend',
            chartType: chartTypeRaw === 'bar' || chartTypeRaw === 'area' ? chartTypeRaw : 'line',
            outputFormat: outputFormatRaw === 'html' || outputFormatRaw === 'word' ? outputFormatRaw : 'pdf',
            metrics
        };
    }

    private renderTemplatePreview(): void {
        if (!this.reportDialogOverlay) {
            return;
        }
        const host = this.reportDialogOverlay.querySelector('[data-role="report-template-preview"]');
        const templateId = (this.reportDialogOverlay.querySelector('#history-report-template') as HTMLSelectElement | null)?.value || '';
        const template = this.reportTemplates.find(item => item.id === templateId) || this.reportTemplates[0];
        if (!host || !template) {
            return;
        }
        host.innerHTML = `<strong>${this.escapeHtml(template.name)}</strong><p>${this.escapeHtml(template.description)}</p><p class="history-trend-hint">${this.escapeHtml(template.preview)}</p>`;
    }

    private renderReportPreview(): void {
        if (!this.reportDialogOverlay || !this.trendResult || !this.reportCurrentConfig) {
            return;
        }
        const zoom = Number((this.reportDialogOverlay.querySelector('[data-role="report-preview-zoom"]') as HTMLInputElement | null)?.value || '1');
        this.reportPreviewZoom = Number.isFinite(zoom) ? zoom : 1;
        const pageRaw = (this.reportDialogOverlay.querySelector('[data-role="report-preview-page"]') as HTMLSelectElement | null)?.value || 'summary';
        this.reportPreviewPage = pageRaw === 'metrics' || pageRaw === 'full' ? pageRaw : 'summary';

        const host = this.reportDialogOverlay.querySelector('[data-role="report-preview-content"]') as HTMLElement | null;
        if (!host) {
            return;
        }
        const metricsHtml = this.buildReportMetricsHtml(this.reportCurrentConfig.metrics);
        const summaryHtml = `
            <h3>${this.escapeHtml(this.reportCurrentConfig.reportTitle)}</h3>
            <p>数据集：${this.escapeHtml(this.trendResult.dataset_id)}，版本范围：v${this.reportCurrentConfig.fromVersion} - v${this.reportCurrentConfig.toVersion}</p>
            <p>分析类型：${this.getReportAnalysisTypeLabel(this.reportCurrentConfig.analysisType)}，输出格式：${this.reportCurrentConfig.outputFormat.toUpperCase()}</p>
        `;
        const fullHtml = `
            <h4>分析结论</h4>
            <p>趋势方向：${this.getDirectionLabel(this.trendResult.linear_trend.direction)}，斜率 ${this.trendResult.linear_trend.slope.toFixed(6)}，异常点 ${this.trendResult.anomalies.length} 个。</p>
            <p>预测准确率 ${this.trendResult.evaluation.accuracy.toFixed(2)}%，建议结合高危异常做进一步排查。</p>
        `;
        const content = this.reportPreviewPage === 'summary' ? summaryHtml : this.reportPreviewPage === 'metrics' ? metricsHtml : fullHtml;
        host.style.transform = `scale(${this.reportPreviewZoom})`;
        host.style.transformOrigin = 'top left';
        host.innerHTML = content;
        this.renderReportPreviewChart();
    }

    private renderReportPreviewChart(): void {
        if (!this.reportDialogOverlay || !this.trendResult) {
            return;
        }
        const host = this.reportDialogOverlay.querySelector('[data-role="report-preview-chart"]') as HTMLElement | null;
        const echarts = this.getEcharts();
        if (!host) {
            return;
        }
        if (!echarts) {
            host.innerHTML = '<div class="history-empty">未加载 ECharts，无法展示交互式预览图表。</div>';
            return;
        }
        if (!this.reportPreviewChart) {
            this.reportPreviewChart = echarts.init(host);
        }
        const chartType = this.reportCurrentConfig?.chartType || 'line';
        const labels = this.trendResult.forecast.map(item => this.formatDateLabel(item.timestamp));
        const values = this.trendResult.forecast.map(item => item.predicted_value);
        this.reportPreviewChart.setOption({
            tooltip: { trigger: 'axis' },
            grid: { left: 40, right: 16, top: 16, bottom: 32 },
            xAxis: { type: 'category', data: labels },
            yAxis: { type: 'value', scale: true },
            series: [{
                type: chartType === 'area' ? 'line' : chartType,
                data: values,
                smooth: true,
                areaStyle: chartType === 'area' ? { color: 'rgba(37,99,235,0.18)' } : undefined,
                itemStyle: { color: '#2563eb' }
            }]
        }, { notMerge: true });
    }

    private async handleGenerateReportFromDialog(): Promise<void> {
        if (!this.trendResult || !this.reportDialogOverlay) {
            return;
        }
        const config = this.readReportConfigFromDialog();
        if (!config) {
            return;
        }
        if (config.fromVersion > config.toVersion) {
            this.updateStatus('报告版本范围无效：起始版本不能大于结束版本。', 'error');
            return;
        }
        const templateId = (this.reportDialogOverlay.querySelector('#history-report-template') as HTMLSelectElement | null)?.value || '';
        const template = this.reportTemplates.find(item => item.id === templateId) || this.reportTemplates[0];
        try {
            this.setReportProgress(20, '准备生成报告...');
            const report = await this.apiService.generateHistoryAnalysisReport({
                dataset_id: this.trendResult.dataset_id,
                from_version: config.fromVersion,
                to_version: config.toVersion,
                forecast_horizon: this.trendResult.forecast.length
            });
            this.setReportProgress(80, '后端报告已返回，正在整理...');
            const rawContent = this.asString(report.report) || this.asString(report.content) || '';
            const record: ReportHistoryRecord = {
                id: `report-${Date.now()}`,
                datasetId: this.trendResult.dataset_id,
                versionFrom: config.fromVersion,
                versionTo: config.toVersion,
                title: config.reportTitle,
                templateId: template?.id || 'default',
                templateName: template?.name || '标准模板',
                analysisType: config.analysisType,
                outputFormat: config.outputFormat,
                generatedAt: new Date().toISOString(),
                content: rawContent || `${config.reportTitle}\n\n${this.buildPlainTextMetrics(config.metrics)}`
            };
            this.reportHistory = [record, ...this.reportHistory].slice(0, 60);
            this.writeStorage(REPORT_HISTORY_KEY, JSON.stringify(this.reportHistory));
            this.reportLatestRecord = record;
            this.setReportProgress(100, '报告生成完成');
            this.renderReportHistoryList();
            this.renderReportSummaries();
            this.renderReportPreview();
            this.updateStatus(`报告生成完成：${record.title}`, 'success');
        } catch (error) {
            const message = error instanceof Error ? error.message : '报告生成失败';
            this.setReportProgress(0, '生成失败');
            this.updateStatus(message, 'error');
        }
    }

    private async uploadReportTemplate(): Promise<void> {
        if (!this.reportDialogOverlay) {
            return;
        }
        const input = this.reportDialogOverlay.querySelector('#history-report-template-file') as HTMLInputElement | null;
        const file = input?.files?.[0];
        if (!file) {
            this.updateStatus('请先选择模板文件。', 'error');
            return;
        }
        const content = await file.text();
        const name = file.name.replace(/\.[^.]+$/, '');
        const record: ReportTemplateItem = {
            id: `custom-${Date.now()}`,
            name: name || '自定义模板',
            description: `来自文件 ${file.name}`,
            preview: content.slice(0, 120),
            builtIn: false,
            content
        };
        this.reportTemplates = [...this.reportTemplates, record];
        this.writeStorage(REPORT_TEMPLATE_KEY, JSON.stringify(this.reportTemplates.filter(item => !item.builtIn)));
        this.renderReportDialog();
        const select = this.reportDialogOverlay.querySelector('#history-report-template') as HTMLSelectElement | null;
        if (select) {
            select.value = record.id;
        }
        this.renderTemplatePreview();
        this.updateStatus(`模板上传成功：${record.name}`, 'success');
    }

    private async deleteCurrentTemplate(): Promise<void> {
        if (!this.reportDialogOverlay) {
            return;
        }
        const select = this.reportDialogOverlay.querySelector('#history-report-template') as HTMLSelectElement | null;
        const templateId = select?.value || '';
        const template = this.reportTemplates.find(item => item.id === templateId);
        if (!template) {
            return;
        }
        if (template.builtIn) {
            this.updateStatus('内置模板不支持删除。', 'error');
            return;
        }
        const confirmed = await ConfirmDialog.confirmDanger({
            title: '删除模板',
            message: `确认删除模板「${template.name}」吗？`
        });
        if (!confirmed) {
            return;
        }
        this.reportTemplates = this.reportTemplates.filter(item => item.id !== template.id);
        this.writeStorage(REPORT_TEMPLATE_KEY, JSON.stringify(this.reportTemplates.filter(item => !item.builtIn)));
        this.renderReportDialog();
        this.updateStatus('模板已删除。', 'success');
    }

    private async downloadCurrentReport(batch: boolean): Promise<void> {
        const record = this.reportLatestRecord || this.reportHistory[0];
        if (!record) {
            this.updateStatus('请先生成报告后再下载。', 'error');
            return;
        }
        const config = this.readReportConfigFromDialog() || this.reportCurrentConfig;
        const formats: Array<'pdf' | 'html' | 'word'> = batch ? ['pdf', 'html', 'word'] : [config?.outputFormat || record.outputFormat];
        for (let index = 0; index < formats.length; index += 1) {
            const format = formats[index];
            const percent = Math.round(((index + 1) / formats.length) * 100);
            this.setReportProgress(percent, `下载 ${format.toUpperCase()}...`);
            await this.downloadReportByFormat(record, format);
        }
        this.setReportProgress(100, '下载完成');
        this.renderReportDownloadHistory();
        this.renderReportSummaries();
    }

    private async downloadReportByFormat(record: ReportHistoryRecord, format: 'pdf' | 'html' | 'word'): Promise<void> {
        const safeTitle = record.title.replace(/[^\w\-一-龥]+/g, '_');
        const fileBase = `${safeTitle}_${record.datasetId}_v${record.versionTo}`;
        if (format === 'pdf') {
            const html = this.buildReportDocumentHtml(record);
            const printWindow = window.open('', '_blank', 'width=1080,height=760');
            if (!printWindow) {
                throw new Error('浏览器拦截了弹窗，无法导出 PDF。');
            }
            printWindow.document.write(html);
            printWindow.document.close();
            printWindow.focus();
            printWindow.print();
            this.appendDownloadHistory(record.id, 'pdf', `${fileBase}.pdf`);
            return;
        }
        const html = this.buildReportDocumentHtml(record);
        if (format === 'html') {
            this.downloadFile(`${fileBase}.html`, html, 'text/html;charset=utf-8');
            this.appendDownloadHistory(record.id, 'html', `${fileBase}.html`);
            return;
        }
        this.downloadFile(`${fileBase}.doc`, html, 'application/msword;charset=utf-8');
        this.appendDownloadHistory(record.id, 'word', `${fileBase}.doc`);
    }

    private buildReportDocumentHtml(record: ReportHistoryRecord): string {
        return `
            <html>
            <head>
                <title>${this.escapeHtml(record.title)}</title>
                <style>
                    body{font-family:Arial,sans-serif;padding:24px;color:#111827;line-height:1.7}
                    h1,h2,h3{margin:0 0 10px}
                    .meta{color:#4b5563;font-size:13px}
                    .card{border:1px solid #e5e7eb;border-radius:8px;padding:10px;margin-bottom:10px}
                    pre{white-space:pre-wrap;background:#f8fafc;border:1px solid #e5e7eb;padding:10px;border-radius:8px}
                </style>
            </head>
            <body>
                <h1>${this.escapeHtml(record.title)}</h1>
                <p class="meta">数据集：${this.escapeHtml(record.datasetId)} | 版本范围：v${record.versionFrom} - v${record.versionTo} | 模板：${this.escapeHtml(record.templateName)}</p>
                <p class="meta">分析类型：${this.getReportAnalysisTypeLabel(record.analysisType)} | 生成时间：${this.formatDateTimeLabel(record.generatedAt)}</p>
                <div class="card">
                    <h3>核心指标</h3>
                    ${this.buildReportMetricsHtml(['accuracy', 'rmse', 'mae', 'mape', 'r2', 'anomaly_count'])}
                </div>
                <div class="card">
                    <h3>报告正文</h3>
                    <pre>${this.escapeHtml(record.content || '暂无正文')}</pre>
                </div>
            </body>
            </html>
        `;
    }

    private buildReportMetricsHtml(metrics: string[]): string {
        if (!this.trendResult) {
            return '<p>暂无指标数据</p>';
        }
        const map: Record<string, string> = {
            accuracy: `准确率：${this.trendResult.evaluation.accuracy.toFixed(2)}%`,
            rmse: `RMSE：${(this.trendResult.evaluation.rmse || 0).toFixed(4)}`,
            mae: `MAE：${this.trendResult.evaluation.mae.toFixed(4)}`,
            mape: `MAPE：${this.trendResult.evaluation.mape.toFixed(2)}%`,
            r2: `R²：${this.trendResult.evaluation.r2.toFixed(4)}`,
            anomaly_count: `异常点数量：${this.trendResult.anomalies.length}`
        };
        return `<ul>${metrics.map(item => `<li>${this.escapeHtml(map[item] || item)}</li>`).join('')}</ul>`;
    }

    private buildPlainTextMetrics(metrics: string[]): string {
        const html = this.buildReportMetricsHtml(metrics);
        return html.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
    }

    private setReportProgress(percent: number, text: string): void {
        if (!this.reportDialogOverlay) {
            return;
        }
        const fill = this.reportDialogOverlay.querySelector('[data-role="report-progress-fill"]') as HTMLElement | null;
        const textEl = this.reportDialogOverlay.querySelector('[data-role="report-progress-text"]') as HTMLElement | null;
        if (fill) {
            fill.style.width = `${Math.max(0, Math.min(100, percent))}%`;
        }
        if (textEl) {
            textEl.textContent = text;
        }
    }

    private renderReportHistoryList(): void {
        if (!this.reportDialogOverlay) {
            return;
        }
        const host = this.reportDialogOverlay.querySelector('[data-role="report-history-list"]');
        if (!host) {
            return;
        }
        if (this.reportHistory.length === 0) {
            host.innerHTML = '<div class="history-empty">暂无报告生成历史。</div>';
            return;
        }
        const rows = this.reportHistory.slice(0, 12).map(item => `
            <tr>
                <td>${this.escapeHtml(item.title)}</td>
                <td>${this.escapeHtml(item.datasetId)}</td>
                <td>v${item.versionFrom} - v${item.versionTo}</td>
                <td>${this.getReportAnalysisTypeLabel(item.analysisType)}</td>
                <td>${item.outputFormat.toUpperCase()}</td>
                <td>${this.escapeHtml(this.formatDateTimeLabel(item.generatedAt))}</td>
                <td>
                    <button type="button" class="history-link-btn" data-action="report-history-open" data-report-id="${item.id}">预览</button>
                    <button type="button" class="history-link-btn" data-action="report-history-regenerate" data-report-id="${item.id}">重生成</button>
                    <button type="button" class="history-link-btn" data-action="report-history-delete" data-report-id="${item.id}">删除</button>
                </td>
            </tr>
        `).join('');
        host.innerHTML = `
            <div class="history-trend-anomaly-table-wrap">
                <table class="history-table history-trend-anomaly-table">
                    <thead>
                        <tr><th>标题</th><th>数据集</th><th>版本范围</th><th>类型</th><th>格式</th><th>时间</th><th>操作</th></tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    }

    private renderReportDownloadHistory(): void {
        if (!this.reportDialogOverlay) {
            return;
        }
        const host = this.reportDialogOverlay.querySelector('[data-role="report-download-history-list"]');
        if (!host) {
            return;
        }
        if (this.reportDownloadHistory.length === 0) {
            host.innerHTML = '<div class="history-empty">暂无下载历史。</div>';
            return;
        }
        const list = this.reportDownloadHistory.slice(0, 16).map(item => (
            `<li>${this.formatDateTimeLabel(item.createdAt)} | ${item.format.toUpperCase()} | ${this.escapeHtml(item.fileName)}</li>`
        )).join('');
        host.innerHTML = `<ul>${list}</ul>`;
    }

    private renderReportSummaries(): void {
        if (this.reportHistorySummaryHost) {
            if (this.reportHistory.length === 0) {
                this.reportHistorySummaryHost.innerHTML = '<div class="history-empty">暂无报告生成历史。</div>';
            } else {
                const rows = this.reportHistory.slice(0, 5).map(item => (
                    `<li>${this.escapeHtml(item.title)} | ${this.formatDateTimeLabel(item.generatedAt)} | <button type="button" class="history-link-btn" data-action="report-history-regenerate" data-report-id="${item.id}">重生成</button> <button type="button" class="history-link-btn" data-action="report-history-delete" data-report-id="${item.id}">删除</button></li>`
                )).join('');
                this.reportHistorySummaryHost.innerHTML = `<h5>最近报告</h5><ul>${rows}</ul>`;
            }
        }
        if (this.reportDownloadSummaryHost) {
            if (this.reportDownloadHistory.length === 0) {
                this.reportDownloadSummaryHost.innerHTML = '<div class="history-empty">暂无下载历史。</div>';
            } else {
                const rows = this.reportDownloadHistory.slice(0, 5).map(item => (
                    `<li>${this.formatDateTimeLabel(item.createdAt)} | ${item.format.toUpperCase()} | ${this.escapeHtml(item.fileName)}</li>`
                )).join('');
                this.reportDownloadSummaryHost.innerHTML = `<h5>最近下载</h5><ul>${rows}</ul>`;
            }
        }
    }

    private openReportFromHistory(reportId: string): void {
        const record = this.reportHistory.find(item => item.id === reportId);
        if (!record || !this.reportDialogOverlay) {
            return;
        }
        this.reportLatestRecord = record;
        const titleInput = this.reportDialogOverlay.querySelector('#history-report-title') as HTMLInputElement | null;
        const fromSelect = this.reportDialogOverlay.querySelector('#history-report-from') as HTMLSelectElement | null;
        const toSelect = this.reportDialogOverlay.querySelector('#history-report-to') as HTMLSelectElement | null;
        const formatSelect = this.reportDialogOverlay.querySelector('#history-report-format') as HTMLSelectElement | null;
        const analysisSelect = this.reportDialogOverlay.querySelector('#history-report-analysis') as HTMLSelectElement | null;
        if (titleInput) {
            titleInput.value = record.title;
        }
        if (fromSelect) {
            fromSelect.value = String(record.versionFrom);
        }
        if (toSelect) {
            toSelect.value = String(record.versionTo);
        }
        if (formatSelect) {
            formatSelect.value = record.outputFormat;
        }
        if (analysisSelect) {
            analysisSelect.value = record.analysisType;
        }
        this.reportCurrentConfig = this.readReportConfigFromDialog();
        this.renderReportPreview();
        this.setReportProgress(100, `已载入历史报告：${record.title}`);
    }

    private regenerateReportFromHistory(reportId: string): void {
        const record = this.reportHistory.find(item => item.id === reportId);
        if (!record) {
            return;
        }
        this.openReportDialog();
        this.openReportFromHistory(reportId);
        void this.handleGenerateReportFromDialog();
    }

    private async deleteReportHistoryRecord(reportId: string): Promise<void> {
        const record = this.reportHistory.find(item => item.id === reportId);
        if (!record) {
            return;
        }
        const confirmed = await ConfirmDialog.confirmDanger({
            title: '删除报告历史',
            message: `确认删除报告「${record.title}」吗？`
        });
        if (!confirmed) {
            return;
        }
        this.reportHistory = this.reportHistory.filter(item => item.id !== reportId);
        this.writeStorage(REPORT_HISTORY_KEY, JSON.stringify(this.reportHistory));
        this.renderReportSummaries();
        this.renderReportHistoryList();
        this.updateStatus(`已删除报告：${record.title}`, 'success');
    }

    private appendDownloadHistory(reportId: string, format: 'pdf' | 'html' | 'word', fileName: string): void {
        const record: DownloadHistoryRecord = {
            id: `download-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            reportId,
            format,
            fileName,
            createdAt: new Date().toISOString()
        };
        this.reportDownloadHistory = [record, ...this.reportDownloadHistory].slice(0, 100);
        this.writeStorage(REPORT_DOWNLOAD_HISTORY_KEY, JSON.stringify(this.reportDownloadHistory));
    }

    private readReportTemplates(): ReportTemplateItem[] {
        const builtIn: ReportTemplateItem[] = [
            { id: 'default', name: '标准模板', description: '通用报告模板，包含摘要、指标和结论。', preview: '适用于常规历史趋势与预测结果汇报。', builtIn: true },
            { id: 'compare', name: '版本对比模板', description: '突出版本差异和异常变化。', preview: '侧重 from/to 版本对比和变化统计。', builtIn: true },
            { id: 'executive', name: '管理层简报模板', description: '突出关键结论和建议。', preview: '面向管理层，信息高度压缩。', builtIn: true }
        ];
        const raw = this.readStorage(REPORT_TEMPLATE_KEY);
        if (!raw) {
            return builtIn;
        }
        try {
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) {
                return builtIn;
            }
            const custom = parsed
                .filter(item => item && typeof item === 'object')
                .map(item => {
                    const row = item as Record<string, unknown>;
                    return {
                        id: this.asString(row.id) || '',
                        name: this.asString(row.name) || '自定义模板',
                        description: this.asString(row.description) || '自定义模板',
                        preview: this.asString(row.preview) || '',
                        builtIn: false,
                        content: this.asString(row.content) || ''
                    };
                })
                .filter(item => item.id);
            return [...builtIn, ...custom];
        } catch {
            return builtIn;
        }
    }

    private readReportHistory(): ReportHistoryRecord[] {
        const raw = this.readStorage(REPORT_HISTORY_KEY);
        if (!raw) {
            return [];
        }
        try {
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) {
                return [];
            }
            return parsed
                .filter(item => item && typeof item === 'object')
                .map(item => {
                    const row = item as Record<string, unknown>;
                    const formatRaw = this.asString(row.outputFormat);
                    const format: 'pdf' | 'html' | 'word' = formatRaw === 'html' || formatRaw === 'word' ? formatRaw : 'pdf';
                    return {
                        id: this.asString(row.id) || '',
                        datasetId: this.asString(row.datasetId) || '',
                        versionFrom: this.asNumber(row.versionFrom) || 1,
                        versionTo: this.asNumber(row.versionTo) || 1,
                        title: this.asString(row.title) || '未命名报告',
                        templateId: this.asString(row.templateId) || 'default',
                        templateName: this.asString(row.templateName) || '标准模板',
                        analysisType: this.asString(row.analysisType) || 'trend',
                        outputFormat: format,
                        generatedAt: this.asString(row.generatedAt) || '',
                        content: this.asString(row.content) || ''
                    };
                })
                .filter(item => item.id && item.datasetId);
        } catch {
            return [];
        }
    }

    private readDownloadHistory(): DownloadHistoryRecord[] {
        const raw = this.readStorage(REPORT_DOWNLOAD_HISTORY_KEY);
        if (!raw) {
            return [];
        }
        try {
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) {
                return [];
            }
            return parsed
                .filter(item => item && typeof item === 'object')
                .map(item => {
                    const row = item as Record<string, unknown>;
                    const formatRaw = this.asString(row.format);
                    const format: 'pdf' | 'html' | 'word' = formatRaw === 'html' || formatRaw === 'word' ? formatRaw : 'pdf';
                    return {
                        id: this.asString(row.id) || '',
                        reportId: this.asString(row.reportId) || '',
                        format,
                        fileName: this.asString(row.fileName) || '',
                        createdAt: this.asString(row.createdAt) || ''
                    };
                })
                .filter(item => item.id);
        } catch {
            return [];
        }
    }

    private getReportAnalysisTypeLabel(type: string): string {
        if (type === 'compare') {
            return '对比分析';
        }
        if (type === 'forecast') {
            return '预测分析';
        }
        return '趋势分析';
    }

    private downloadFile(fileName: string, content: string, mimeType: string): void {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = fileName;
        anchor.click();
        URL.revokeObjectURL(url);
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

        if (this.anomalyListHost) {
            this.anomalyListHost.innerHTML = '<div class="history-empty">执行趋势分析后展示异常点列表。</div>';
        }

        if (this.anomalyMapClusterHost) {
            this.anomalyMapClusterHost.innerHTML = '<div class="history-empty">暂无聚合标注。</div>';
        }

        if (this.warningStatsHost) {
            this.warningStatsHost.innerHTML = '<div class="history-empty">执行趋势分析后展示预警统计。</div>';
        }

        if (this.warningHistoryHost) {
            this.warningHistoryHost.innerHTML = '<div class="history-empty">暂无预警历史记录。</div>';
        }

        if (this.reasonHost) {
            this.reasonHost.innerHTML = '<div class="history-empty">执行趋势分析后展示异常原因。</div>';
        }

        if (this.modelVisibilityHost) {
            this.modelVisibilityHost.innerHTML = '<div class="history-empty">执行趋势分析后展示模型切换。</div>';
        }

        if (this.modelCompareHost) {
            this.modelCompareHost.innerHTML = '<div class="history-empty">执行趋势分析后展示模型性能对比。</div>';
        }

        if (this.reportHistorySummaryHost) {
            this.reportHistorySummaryHost.innerHTML = '<div class="history-empty">暂无报告生成历史。</div>';
        }

        if (this.reportDownloadSummaryHost) {
            this.reportDownloadSummaryHost.innerHTML = '<div class="history-empty">暂无下载历史。</div>';
        }
    }

    private ensureChart(type: 'linear' | 'fft' | 'seasonal' | 'anomalyMap' | 'anomalySeries' | 'anomalyTrend'): EChartInstance | null {
        const echarts = this.getEcharts();
        if (!echarts) {
            const host =
                type === 'linear'
                    ? this.linearChartHost
                    : type === 'fft'
                        ? this.fftChartHost
                        : type === 'seasonal'
                            ? this.seasonalChartHost
                            : type === 'anomalyMap'
                                ? this.anomalyMapHost
                                : type === 'anomalySeries'
                                    ? this.anomalySeriesHost
                                    : this.anomalyTrendHost;
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
        if (type === 'seasonal') {
            return this.seasonalChart;
        }

        if (type === 'anomalyMap') {
            if (!this.anomalyMapChart && this.anomalyMapHost) {
                this.anomalyMapChart = echarts.init(this.anomalyMapHost);
            }
            return this.anomalyMapChart;
        }

        if (type === 'anomalySeries') {
            if (!this.anomalySeriesChart && this.anomalySeriesHost) {
                this.anomalySeriesChart = echarts.init(this.anomalySeriesHost);
            }
            return this.anomalySeriesChart;
        }

        if (!this.anomalyTrendChart && this.anomalyTrendHost) {
            this.anomalyTrendChart = echarts.init(this.anomalyTrendHost);
        }
        return this.anomalyTrendChart;
    }

    private getEcharts(): EChartsLike | null {
        const win = window as Window & { echarts?: EChartsLike };
        return win.echarts || null;
    }

    private handleResize = (): void => {
        this.linearChart?.resize();
        this.fftChart?.resize();
        this.seasonalChart?.resize();
        this.anomalyMapChart?.resize();
        this.anomalySeriesChart?.resize();
        this.anomalyTrendChart?.resize();
    };

    private setLoading(loading: boolean): void {
        if (!this.root) {
            return;
        }
        this.loading = loading;
        this.root.querySelectorAll('button[data-action]').forEach((button) => {
            (button as HTMLButtonElement).disabled = loading;
        });
    }

    private syncAutoRefreshSelect(): void {
        const interval = Number(this.readStorage(TREND_AUTO_REFRESH_KEY) || '0');
        if (this.autoRefreshSelect) {
            this.autoRefreshSelect.value = Number.isFinite(interval) ? String(Math.max(0, interval)) : '0';
        }
    }

    private updateAutoRefreshFromSelect(): void {
        const intervalSec = Number(this.autoRefreshSelect?.value || '0');
        this.writeStorage(TREND_AUTO_REFRESH_KEY, String(intervalSec));
        this.stopAutoRefresh();
        if (!Number.isFinite(intervalSec) || intervalSec <= 0) {
            if (this.refreshProgressElement) {
                this.refreshProgressElement.textContent = '自动刷新已关闭。';
            }
            return;
        }
        this.refreshRemainSec = Math.floor(intervalSec);
        this.autoRefreshTimer = window.setInterval(() => {
            if (!this.loading && this.datasetInput?.value.trim()) {
                void this.handleRefreshAnalysis();
            }
        }, Math.floor(intervalSec) * 1000);
        this.resetRefreshCountdown();
    }

    private stopAutoRefresh(): void {
        if (this.autoRefreshTimer !== null) {
            window.clearInterval(this.autoRefreshTimer);
            this.autoRefreshTimer = null;
        }
        if (this.refreshCountdownTimer !== null) {
            window.clearInterval(this.refreshCountdownTimer);
            this.refreshCountdownTimer = null;
        }
    }

    private resetRefreshCountdown(): void {
        if (this.refreshCountdownTimer !== null) {
            window.clearInterval(this.refreshCountdownTimer);
            this.refreshCountdownTimer = null;
        }
        const intervalSec = Number(this.autoRefreshSelect?.value || '0');
        if (!Number.isFinite(intervalSec) || intervalSec <= 0) {
            return;
        }
        this.refreshRemainSec = Math.floor(intervalSec);
        this.refreshCountdownTimer = window.setInterval(() => {
            this.refreshRemainSec = Math.max(0, this.refreshRemainSec - 1);
            if (this.refreshProgressElement) {
                this.refreshProgressElement.textContent = `自动刷新中，${this.refreshRemainSec} 秒后刷新。`;
            }
            if (this.refreshRemainSec <= 0) {
                this.refreshRemainSec = Math.floor(intervalSec);
            }
        }, 1000);
    }

    private showSkeleton(): void {
        if (!this.metricsHost || !this.linearChartHost) {
            return;
        }
        SkeletonLoader.hideByContainer(this.metricsHost);
        SkeletonLoader.hideByContainer(this.linearChartHost);
        this.metricsSkeleton = SkeletonLoader.show(this.metricsHost, 'list', { lines: 5, showAvatar: false });
        this.chartSkeleton = SkeletonLoader.show(this.linearChartHost, 'chart', {});
    }

    private hideSkeleton(): void {
        SkeletonLoader.hide(this.metricsSkeleton);
        SkeletonLoader.hide(this.chartSkeleton);
        this.metricsSkeleton = null;
        this.chartSkeleton = null;
    }

    private async runWithRetry(executor: () => Promise<void>, actionName: string): Promise<void> {
        for (let attempt = 0; attempt <= RETRY_TIMES; attempt += 1) {
            try {
                await executor();
                return;
            } catch (error) {
                const message = error instanceof Error ? error.message : String(error || '未知错误');
                if (attempt >= RETRY_TIMES || !/(timeout|network|fetch|502|503|504|连接|超时|网络)/i.test(message)) {
                    this.updateStatus(`${actionName}失败：${this.classifyError(message)}，${message}`, 'error');
                    throw error;
                }
                this.updateStatus(`${actionName}失败，正在第 ${attempt + 1} 次重试...`, 'info');
                await this.delay(350 * (attempt + 1));
            }
        }
    }

    private classifyError(message: string): string {
        if (/(timeout|timed out|超时)/i.test(message)) {
            return '请求超时';
        }
        if (/(network|fetch|连接|offline|断开)/i.test(message)) {
            return '网络异常';
        }
        if (/(500|502|503|504)/.test(message)) {
            return '服务端错误';
        }
        return '未知错误';
    }

    private delay(ms: number): Promise<void> {
        return new Promise((resolve) => {
            window.setTimeout(resolve, ms);
        });
    }

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
        if (type === 'error' && this.lastRetryAction) {
            this.statusElement.textContent = `${message}；可点击“重试”。`;
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

    private formatDateTimeLabel(timestamp: string): string {
        const date = new Date(timestamp);
        if (Number.isNaN(date.getTime())) {
            return timestamp;
        }
        const yyyy = date.getFullYear();
        const mm = `${date.getMonth() + 1}`.padStart(2, '0');
        const dd = `${date.getDate()}`.padStart(2, '0');
        const hh = `${date.getHours()}`.padStart(2, '0');
        const mi = `${date.getMinutes()}`.padStart(2, '0');
        return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
    }

    private getFilteredAnomalies(): AnomalyViewItem[] {
        const type = this.filterTypeSelect?.value || 'all';
        const severity = this.filterSeveritySelect?.value || 'all';
        const sort = this.sortSelect?.value || 'score_desc';
        const items = this.anomalyViewItems.filter(item => {
            if (type !== 'all' && item.anomaly_type !== type) {
                return false;
            }
            if (severity !== 'all' && item.severity !== severity) {
                return false;
            }
            return true;
        });

        items.sort((a, b) => {
            if (sort === 'time_asc') {
                return Date.parse(a.timestamp) - Date.parse(b.timestamp);
            }
            if (sort === 'time_desc') {
                return Date.parse(b.timestamp) - Date.parse(a.timestamp);
            }
            if (sort === 'value_desc') {
                return b.value - a.value;
            }
            return Math.abs(b.score) - Math.abs(a.score);
        });
        return items;
    }

    private getAnomalyTypeLabel(type: string): string {
        if (type === 'positive') {
            return '正异常';
        }
        if (type === 'negative') {
            return '负异常';
        }
        return '未知';
    }

    private getSeverityByScore(scoreAbs: number, threshold: number): AnomalySeverity {
        if (scoreAbs >= threshold * 1.6) {
            return 'high';
        }
        if (scoreAbs >= threshold * 1.2) {
            return 'medium';
        }
        return 'low';
    }

    private buildAnomalyClusters(points: AnomalyViewItem[]): AnomalyCluster[] {
        if (points.length < 2) {
            return [];
        }
        const xs = points.map(item => item.x || 0);
        const ys = points.map(item => item.y || 0);
        const minX = Math.min(...xs);
        const maxX = Math.max(...xs);
        const minY = Math.min(...ys);
        const maxY = Math.max(...ys);
        const dx = Math.max(1e-6, maxX - minX);
        const dy = Math.max(1e-6, maxY - minY);
        const gridSize = 6;
        const buckets = new Map<string, AnomalyViewItem[]>();

        points.forEach(item => {
            const x = item.x || 0;
            const y = item.y || 0;
            const gx = Math.min(gridSize - 1, Math.floor(((x - minX) / dx) * gridSize));
            const gy = Math.min(gridSize - 1, Math.floor(((y - minY) / dy) * gridSize));
            const key = `${gx}-${gy}`;
            const bucket = buckets.get(key) || [];
            bucket.push(item);
            buckets.set(key, bucket);
        });

        const clusters: AnomalyCluster[] = [];
        buckets.forEach((bucket, key) => {
            if (bucket.length < 2) {
                return;
            }
            const centerX = bucket.reduce((sum, item) => sum + (item.x || 0), 0) / bucket.length;
            const centerY = bucket.reduce((sum, item) => sum + (item.y || 0), 0) / bucket.length;
            const maxScore = Math.max(...bucket.map(item => Math.abs(item.score)));
            clusters.push({
                id: key,
                centerX,
                centerY,
                count: bucket.length,
                maxScore
            });
        });

        return clusters.sort((a, b) => b.count - a.count);
    }

    private computeStd(values: number[]): number {
        if (values.length <= 1) {
            return 0;
        }
        const mean = values.reduce((sum, item) => sum + item, 0) / values.length;
        const variance = values.reduce((sum, item) => sum + Math.pow(item - mean, 2), 0) / (values.length - 1);
        return Math.sqrt(Math.max(0, variance));
    }

    private getWarningThreshold(): number {
        const inputValue = Number(this.warningThresholdInput?.value || '');
        if (Number.isFinite(inputValue) && inputValue >= 1) {
            return Math.floor(inputValue);
        }
        const stored = Number(this.readStorage(WARNING_THRESHOLD_KEY) || '5');
        if (Number.isFinite(stored) && stored >= 1) {
            return Math.floor(stored);
        }
        return 5;
    }

    private saveWarningThreshold(): void {
        const threshold = this.getWarningThreshold();
        this.writeStorage(WARNING_THRESHOLD_KEY, String(threshold));
        this.updateStatus(`异常预警阈值已更新为 ${threshold}。`, 'success');
    }

    private recordWarning(record: WarningRecord): void {
        const latest = this.warningHistory[0];
        if (
            latest &&
            latest.dataset_id === record.dataset_id &&
            latest.version === record.version &&
            latest.anomaly_count === record.anomaly_count &&
            latest.threshold === record.threshold
        ) {
            return;
        }
        this.warningHistory = [record, ...this.warningHistory].slice(0, 60);
        this.writeStorage(WARNING_HISTORY_KEY, JSON.stringify(this.warningHistory));
    }

    private readWarningHistory(): WarningRecord[] {
        const raw = this.readStorage(WARNING_HISTORY_KEY);
        if (!raw) {
            return [];
        }
        try {
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) {
                return [];
            }
            return parsed
                .filter(item => item && typeof item === 'object')
                .map(item => {
                    const record = item as Record<string, unknown>;
                    const level: 'high' | 'normal' = this.asString(record.level) === 'high' ? 'high' : 'normal';
                    return {
                        timestamp: this.asString(record.timestamp) || '',
                        dataset_id: this.asString(record.dataset_id) || '',
                        version: this.asNumber(record.version) || 0,
                        anomaly_count: this.asNumber(record.anomaly_count) || 0,
                        threshold: this.asNumber(record.threshold) || 0,
                        level
                    };
                })
                .filter(item => item.dataset_id && item.version > 0);
        } catch {
            return [];
        }
    }

    private readSubscriptionConfig(): AnomalySubscriptionConfig {
        const raw = this.readStorage(SUBSCRIPTION_KEY);
        if (!raw) {
            return {
                enabled: false,
                channels: ['app'],
                frequency: 'realtime',
                last_notify_at: ''
            };
        }
        try {
            const parsed = JSON.parse(raw) as Partial<AnomalySubscriptionConfig>;
            const frequency = parsed.frequency === 'hourly' || parsed.frequency === 'daily' ? parsed.frequency : 'realtime';
            return {
                enabled: Boolean(parsed.enabled),
                channels: Array.isArray(parsed.channels) ? parsed.channels.filter(item => typeof item === 'string') : ['app'],
                frequency,
                last_notify_at: typeof parsed.last_notify_at === 'string' ? parsed.last_notify_at : ''
            };
        } catch {
            return {
                enabled: false,
                channels: ['app'],
                frequency: 'realtime',
                last_notify_at: ''
            };
        }
    }

    private renderSubscription(): void {
        if (!this.subscriptionHost) {
            return;
        }
        const config = this.subscriptionConfig;
        this.subscriptionHost.innerHTML = `
            <div class="history-trend-subscription-grid">
                <label><input type="checkbox" data-role="sub-channel" value="mail" ${config.channels.includes('mail') ? 'checked' : ''}> 邮件</label>
                <label><input type="checkbox" data-role="sub-channel" value="sms" ${config.channels.includes('sms') ? 'checked' : ''}> 短信</label>
                <label><input type="checkbox" data-role="sub-channel" value="app" ${config.channels.includes('app') ? 'checked' : ''}> 应用内</label>
                <select class="select integration-input" data-role="sub-frequency">
                    <option value="realtime" ${config.frequency === 'realtime' ? 'selected' : ''}>实时</option>
                    <option value="hourly" ${config.frequency === 'hourly' ? 'selected' : ''}>每小时</option>
                    <option value="daily" ${config.frequency === 'daily' ? 'selected' : ''}>每天</option>
                </select>
            </div>
            <div class="integration-actions">
                <button type="button" class="btn btn-primary integration-action-btn" data-action="subscribe-anomaly-notification">订阅异常通知</button>
                <button type="button" class="btn btn-secondary integration-action-btn" data-action="unsubscribe-anomaly-notification">取消订阅</button>
            </div>
            <p class="history-trend-hint">当前状态：${config.enabled ? '已订阅' : '未订阅'}${config.last_notify_at ? `，上次通知 ${this.formatDateTimeLabel(config.last_notify_at)}` : ''}</p>
        `;
    }

    private subscribeNotification(): void {
        if (!this.subscriptionHost) {
            return;
        }
        const channels = Array.from(this.subscriptionHost.querySelectorAll('[data-role="sub-channel"]'))
            .filter(node => (node as HTMLInputElement).checked)
            .map(node => (node as HTMLInputElement).value);
        if (channels.length === 0) {
            this.updateStatus('至少选择一种通知方式。', 'error');
            return;
        }
        const frequencyEl = this.subscriptionHost.querySelector('[data-role="sub-frequency"]') as HTMLSelectElement | null;
        const frequency = frequencyEl?.value === 'hourly' || frequencyEl?.value === 'daily' ? frequencyEl.value : 'realtime';
        this.subscriptionConfig = {
            ...this.subscriptionConfig,
            enabled: true,
            channels,
            frequency
        };
        this.writeStorage(SUBSCRIPTION_KEY, JSON.stringify(this.subscriptionConfig));
        this.renderSubscription();
        this.updateStatus('异常通知订阅已保存。', 'success');
    }

    private unsubscribeNotification(): void {
        this.subscriptionConfig = {
            ...this.subscriptionConfig,
            enabled: false
        };
        this.writeStorage(SUBSCRIPTION_KEY, JSON.stringify(this.subscriptionConfig));
        this.renderSubscription();
        this.updateStatus('已取消异常通知订阅。', 'success');
    }

    private evaluateAndNotifyWarning(result: TrendAnalysisResult): void {
        const threshold = this.getWarningThreshold();
        if (this.anomalyViewItems.length < threshold) {
            return;
        }
        if (!this.subscriptionConfig.enabled || !this.subscriptionConfig.channels.includes('app')) {
            return;
        }
        if (!this.shouldDispatchByFrequency()) {
            return;
        }

        this.subscriptionConfig.last_notify_at = new Date().toISOString();
        this.writeStorage(SUBSCRIPTION_KEY, JSON.stringify(this.subscriptionConfig));
        notificationManager.show({
            type: 'taskFailure',
            title: '异常趋势预警',
            body: `数据集 ${result.dataset_id} v${result.version} 检测到 ${this.anomalyViewItems.length} 个异常点（阈值 ${threshold}）。`,
            priority: 'high'
        });
        this.renderSubscription();
    }

    private shouldDispatchByFrequency(): boolean {
        const frequency = this.subscriptionConfig.frequency;
        const last = this.subscriptionConfig.last_notify_at ? Date.parse(this.subscriptionConfig.last_notify_at) : 0;
        if (!last || Number.isNaN(last)) {
            return true;
        }
        const now = Date.now();
        if (frequency === 'hourly') {
            return now - last >= 60 * 60 * 1000;
        }
        if (frequency === 'daily') {
            return now - last >= 24 * 60 * 60 * 1000;
        }
        return true;
    }

    private focusAnomaly(index: number): void {
        const target = this.anomalyViewItems.find(item => item.index === index);
        if (!target) {
            return;
        }
        this.updateStatus(`异常点定位：${this.formatDateTimeLabel(target.timestamp)}，值 ${target.value.toFixed(4)}，z-score ${target.score.toFixed(3)}。`, 'info');
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
