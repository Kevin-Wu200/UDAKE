import type { HistoryComparisonPayload, HistorySnapshotMetadata } from '../../services/API封装.js';
import { APIService } from '../../services/API封装.js';
import { DataComparison } from '../../utils/DataComparison.js';
import { LayerComparisonPanel, LayerType } from '../LayerComparisonPanel.js';
import notificationManager from '../NotificationManager.js';
import { SkeletonLoader } from '../../utils/SkeletonLoader.js';
import { I18n } from '../../utils/I18n';

interface ComparisonDiffItem {
    key: string;
    from_value: number | null;
    to_value: number | null;
    absolute_diff: number;
    relative_diff: number | null;
    timestamp: string | null;
    x: number | null;
    y: number | null;
}

interface ComparisonSummary {
    total_points: number;
    changed_points: number;
    unchanged_points: number;
    avg_absolute_diff: number;
    max_absolute_diff: number;
    min_absolute_diff: number;
}

interface ComparisonHeatmap {
    rows: number;
    cols: number;
    matrix: number[][];
}

interface ComparisonResponse {
    dataset_id: string;
    from_version: number;
    to_version: number;
    summary: ComparisonSummary;
    diffs: ComparisonDiffItem[];
    heatmap: ComparisonHeatmap;
}

interface DiffCellEntry {
    row: number;
    col: number;
    diff: ComparisonDiffItem;
}

type SortKey = 'key' | 'absolute_diff' | 'relative_diff' | 'from_value' | 'to_value' | 'timestamp';
type SortDirection = 'asc' | 'desc';

const DEFAULT_GRID_SIZE = 16;
const COMPARE_AUTO_REFRESH_KEY = 'udake_history_compare_auto_refresh_sec_v1';
const RETRY_TIMES = 2;
type StatusType = 'success' | 'error' | 'warning';

export class HistoryVersionComparisonPanel {
    private root: HTMLElement | null = null;
    private statusElement: HTMLElement | null = null;
    private fromVersionSelect: HTMLSelectElement | null = null;
    private toVersionSelect: HTMLSelectElement | null = null;
    private datasetInput: HTMLInputElement | null = null;
    private gridSizeInput: HTMLInputElement | null = null;
    private thresholdInput: HTMLInputElement | null = null;
    private thresholdRange: HTMLInputElement | null = null;
    private searchInput: HTMLInputElement | null = null;
    private changedOnlyCheckbox: HTMLInputElement | null = null;

    private summaryHost: HTMLElement | null = null;
    private distributionHost: HTMLElement | null = null;
    private tableHost: HTMLElement | null = null;
    private detailHost: HTMLElement | null = null;
    private heatmapHost: HTMLElement | null = null;
    private versionInfoHost: HTMLElement | null = null;
    private autoRefreshSelect: HTMLSelectElement | null = null;
    private refreshProgressElement: HTMLElement | null = null;

    private layerPanelHost: HTMLElement | null = null;
    private layerPanel: LayerComparisonPanel | null = null;

    private currentDatasetId = '';
    private snapshots: HistorySnapshotMetadata[] = [];
    private comparison: ComparisonResponse | null = null;

    private filteredDiffs: ComparisonDiffItem[] = [];
    private selectedDiffKey: string | null = null;
    private highlightedThreshold = 0;
    private sortKey: SortKey = 'absolute_diff';
    private sortDirection: SortDirection = 'desc';

    private cellDiffEntries: DiffCellEntry[] = [];
    private summarySkeleton: HTMLDivElement | null = null;
    private tableSkeleton: HTMLDivElement | null = null;
    private autoRefreshTimer: number | null = null;
    private refreshCountdownTimer: number | null = null;
    private refreshRemainSec = 0;
    private lastRetryAction: (() => Promise<void>) | null = null;
    private loading = false;

    constructor(private readonly apiService: APIService) {}

    public mount(container: HTMLElement): void {
        this.root = document.createElement('div');
        this.root.className = 'integration-module-panel history-version-comparison-panel';
        this.root.innerHTML = `
            <h3 class="integration-module-title">历史版本对比界面</h3>
            <p class="integration-module-description">支持双版本选择、差值高亮、热力图图层控制、统计摘要与 CSV/GeoJSON 导出。</p>

            <section class="history-compare-card">
                <h4>版本选择器</h4>
                <div class="history-compare-selector-grid">
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-compare-dataset-id">数据集 ID</label>
                        <input id="history-compare-dataset-id" class="input integration-input" type="text" placeholder="例如 dataset-001">
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-compare-grid-size">热力图网格</label>
                        <input id="history-compare-grid-size" class="input integration-input" type="number" min="4" max="64" step="1" value="16">
                    </div>
                    <div class="integration-actions history-compare-selector-actions">
                        <button type="button" class="btn btn-secondary integration-action-btn" data-action="load-versions">加载版本</button>
                        <button type="button" class="btn btn-primary integration-action-btn" data-action="run-compare">开始对比</button>
                    </div>
                </div>

                <div class="history-compare-version-pickers">
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-compare-from">基准版本（from）</label>
                        <select id="history-compare-from" class="select integration-input"></select>
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-compare-to">对比版本（to）</label>
                        <select id="history-compare-to" class="select integration-input"></select>
                    </div>
                </div>

                <div class="history-compare-version-info" data-role="version-info"></div>
            </section>

            <section class="history-compare-card">
                <h4>变化高亮与筛选</h4>
                <div class="history-compare-controls-grid">
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-compare-threshold">高亮阈值（绝对差值）</label>
                        <input id="history-compare-threshold" class="input integration-input" type="number" min="0" step="0.0001" value="0">
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-compare-threshold-range">阈值滑杆</label>
                        <input id="history-compare-threshold-range" class="slider" type="range" min="0" max="1" step="0.0001" value="0">
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="history-compare-search">关键字筛选</label>
                        <input id="history-compare-search" class="input integration-input" type="text" placeholder="按点位 key 搜索">
                    </div>
                    <label class="checkbox-label history-compare-checkbox">
                        <input id="history-compare-changed-only" type="checkbox">
                        <span>仅显示变化项（absolute_diff &gt; 0）</span>
                    </label>
                </div>
                <div class="history-compare-sort-row">
                    <span>排序：</span>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="sort-key" data-sort-key="absolute_diff">按绝对差值</button>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="sort-key" data-sort-key="relative_diff">按相对差值</button>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="sort-key" data-sort-key="timestamp">按时间</button>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="toggle-sort-direction">切换升降序</button>
                </div>
            </section>

            <section class="history-compare-card">
                <h4>刷新与快捷键</h4>
                <div class="history-snapshot-refresh-row">
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="refresh-compare">刷新版本与结果</button>
                    <label class="integration-field">
                        <span class="integration-field-label">自动刷新间隔</span>
                        <select id="history-compare-auto-refresh" class="select integration-input">
                            <option value="0">关闭</option>
                            <option value="10">10 秒</option>
                            <option value="30">30 秒</option>
                            <option value="60">60 秒</option>
                            <option value="120">120 秒</option>
                        </select>
                    </label>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="retry-last">重试</button>
                </div>
                <p class="history-archive-hint" data-role="compare-refresh-progress">自动刷新已关闭。</p>
                <p class="history-archive-hint">快捷键：Alt+C 执行对比，Alt+R 刷新，Alt+1 导出 CSV，Alt+2 导出 GeoJSON。</p>
            </section>

            <div class="status-message" data-role="compare-status"></div>

            <section class="history-compare-main-grid">
                <div class="history-compare-main-left">
                    <section class="history-compare-card">
                        <h4>对比统计摘要</h4>
                        <div class="history-compare-summary" data-role="summary"></div>
                        <div class="history-compare-distribution" data-role="distribution"></div>
                    </section>

                    <section class="history-compare-card">
                        <h4>热力图对比（LayerComparison 集成）</h4>
                        <div class="history-compare-layer-panel" data-role="layer-panel"></div>
                        <div class="history-compare-heatmap-wrapper">
                            <div class="history-compare-heatmap-layer" data-layer-id="diff-heatmap"></div>
                            <div class="history-compare-heatmap-layer" data-layer-id="highlight-overlay"></div>
                        </div>
                        <p class="history-compare-hint">点击高亮网格可查看该区域的最大变化点详情。</p>
                    </section>
                </div>

                <div class="history-compare-main-right">
                    <section class="history-compare-card">
                        <h4>变化详情</h4>
                        <div class="history-compare-detail" data-role="detail"></div>
                    </section>

                    <section class="history-compare-card">
                        <h4>对比结果导出</h4>
                        <div class="integration-actions">
                            <button type="button" class="btn btn-secondary integration-action-btn" data-action="export-csv">导出 CSV</button>
                            <button type="button" class="btn btn-secondary integration-action-btn" data-action="export-geojson">导出 GeoJSON</button>
                        </div>
                    </section>
                </div>
            </section>

            <section class="history-compare-card">
                <h4>差值数据表格</h4>
                <div class="history-compare-table-wrap" data-role="table"></div>
            </section>
        `;

        container.appendChild(this.root);
        this.bindElements();
        this.bindEvents();
        this.setupLayerPanel();
        this.bootstrapDefaultDataset();
        this.renderVersionPicker();
        this.renderVersionInfo();
        this.renderSummary();
        this.renderDistribution();
        this.renderTable();
        this.renderDetail();
        this.renderHeatmapLayers();
        this.syncAutoRefreshSelect();
        this.updateAutoRefreshFromSelect();
    }

    private bindElements(): void {
        if (!this.root) {
            return;
        }

        this.statusElement = this.root.querySelector('[data-role="compare-status"]');
        this.datasetInput = this.root.querySelector('#history-compare-dataset-id');
        this.gridSizeInput = this.root.querySelector('#history-compare-grid-size');
        this.fromVersionSelect = this.root.querySelector('#history-compare-from');
        this.toVersionSelect = this.root.querySelector('#history-compare-to');
        this.thresholdInput = this.root.querySelector('#history-compare-threshold');
        this.thresholdRange = this.root.querySelector('#history-compare-threshold-range');
        this.searchInput = this.root.querySelector('#history-compare-search');
        this.changedOnlyCheckbox = this.root.querySelector('#history-compare-changed-only');

        this.summaryHost = this.root.querySelector('[data-role="summary"]');
        this.distributionHost = this.root.querySelector('[data-role="distribution"]');
        this.tableHost = this.root.querySelector('[data-role="table"]');
        this.detailHost = this.root.querySelector('[data-role="detail"]');
        this.heatmapHost = this.root.querySelector('.history-compare-heatmap-wrapper');
        this.versionInfoHost = this.root.querySelector('[data-role="version-info"]');
        this.layerPanelHost = this.root.querySelector('[data-role="layer-panel"]');
        this.autoRefreshSelect = this.root.querySelector('#history-compare-auto-refresh');
        this.refreshProgressElement = this.root.querySelector('[data-role="compare-refresh-progress"]');
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

            if (action === 'run-compare') {
                await this.handleRunCompare();
                return;
            }

            if (action === 'sort-key') {
                const key = actionEl.getAttribute('data-sort-key') as SortKey | null;
                if (key) {
                    this.sortKey = key;
                    this.applyFilterAndSort();
                }
                return;
            }

            if (action === 'toggle-sort-direction') {
                this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
                this.applyFilterAndSort();
                return;
            }

            if (action === 'export-csv') {
                this.exportCsv();
                return;
            }

            if (action === 'export-geojson') {
                this.exportGeoJson();
                return;
            }
            if (action === 'refresh-compare') {
                await this.handleRefreshCompare();
                return;
            }
            if (action === 'retry-last') {
                await this.handleRetryLast();
                return;
            }

            if (action === 'select-diff') {
                const key = actionEl.getAttribute('data-diff-key') || '';
                this.handleSelectDiff(key);
                return;
            }

            if (action === 'select-cell') {
                const row = Number(actionEl.getAttribute('data-row') || '');
                const col = Number(actionEl.getAttribute('data-col') || '');
                if (Number.isFinite(row) && Number.isFinite(col)) {
                    this.handleSelectCell(row, col);
                }
            }
        });

        this.fromVersionSelect?.addEventListener('change', () => this.renderVersionInfo());
        this.toVersionSelect?.addEventListener('change', () => this.renderVersionInfo());

        const onFilterChanged = (): void => {
            this.applyFilterAndSort();
        };

        this.searchInput?.addEventListener('input', onFilterChanged);
        this.changedOnlyCheckbox?.addEventListener('change', onFilterChanged);

        this.thresholdInput?.addEventListener('input', () => {
            const value = this.parseThreshold(this.thresholdInput?.value || '0');
            this.setThreshold(value, true);
        });

        this.thresholdRange?.addEventListener('input', () => {
            const value = this.parseThreshold(this.thresholdRange?.value || '0');
            this.setThreshold(value, true);
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
            if (key === 'c') {
                event.preventDefault();
                await this.handleRunCompare();
                return;
            }
            if (key === 'r') {
                event.preventDefault();
                await this.handleRefreshCompare();
                return;
            }
            if (key === '1') {
                event.preventDefault();
                this.exportCsv();
                return;
            }
            if (key === '2') {
                event.preventDefault();
                this.exportGeoJson();
            }
        });
    }

    private setupLayerPanel(): void {
        if (!this.layerPanelHost) {
            return;
        }

        this.layerPanel = new LayerComparisonPanel({
            onVisibilityChange: (layerId, visible) => this.applyLayerVisibility(layerId, visible),
            onOpacityChange: (layerId, opacity) => this.applyLayerOpacity(layerId, opacity)
        });

        const panelEl = this.layerPanel.createPanel();
        this.layerPanelHost.appendChild(panelEl);

        this.layerPanel.addLayer({
            layerId: 'diff-heatmap',
            layerName: '差值热力图',
            layerType: LayerType.PREDICTION,
            visible: true,
            opacity: 88,
            zIndex: 2
        });

        this.layerPanel.addLayer({
            layerId: 'highlight-overlay',
            layerName: '变化高亮层',
            layerType: LayerType.MARKER,
            visible: true,
            opacity: 100,
            zIndex: 3
        });

        this.applyLayerVisibility('diff-heatmap', true);
        this.applyLayerVisibility('highlight-overlay', true);
        this.applyLayerOpacity('diff-heatmap', 88);
        this.applyLayerOpacity('highlight-overlay', 100);
    }

    private bootstrapDefaultDataset(): void {
        const lastDatasetId = this.readLocalStorage('udake_history_snapshot_last_dataset_id');
        if (lastDatasetId && this.datasetInput) {
            this.datasetInput.value = lastDatasetId;
            this.currentDatasetId = lastDatasetId;
        }
    }

    private async handleRefreshCompare(): Promise<void> {
        if (!this.currentDatasetId && !(this.datasetInput?.value.trim())) {
            this.setStatus('请先加载版本列表。', 'warning');
            return;
        }
        await this.handleLoadVersions();
        if (this.comparison) {
            await this.handleRunCompare();
        } else {
            this.resetRefreshCountdown();
        }
    }

    private async handleRetryLast(): Promise<void> {
        if (!this.lastRetryAction) {
            this.setStatus('当前没有可重试的失败请求。', 'warning');
            return;
        }
        await this.lastRetryAction();
    }

    private async handleLoadVersions(): Promise<void> {
        const datasetId = this.datasetInput?.value.trim() || '';
        if (!datasetId) {
            this.setStatus('请先输入数据集 ID。', 'error');
            return;
        }

        this.setLoading(true);
        this.setStatus('正在加载版本列表...', 'warning');
        this.showSkeleton();

        await this.runWithRetry(
            async () => {
                const resp = await this.apiService.listHistorySnapshots(datasetId);
                this.currentDatasetId = datasetId;
                this.writeLocalStorage('udake_history_snapshot_last_dataset_id', datasetId);
                this.snapshots = [...(resp.versions || [])].sort((a, b) => b.version - a.version);

                this.renderVersionPicker();
                this.renderVersionInfo();
                this.setStatus(`已加载 ${this.snapshots.length} 个版本。`, 'success');
                this.lastRetryAction = null;
                this.resetRefreshCountdown();
            },
            '加载版本列表'
        ).catch(() => {
            this.lastRetryAction = async () => this.handleLoadVersions();
        }).finally(() => {
            this.setLoading(false);
            this.hideSkeleton();
        });
    }

    private async handleRunCompare(): Promise<void> {
        const datasetId = this.currentDatasetId || this.datasetInput?.value.trim() || '';
        if (!datasetId) {
            this.setStatus('请先加载版本列表。', 'error');
            return;
        }

        const fromVersion = Number(this.fromVersionSelect?.value || '');
        const toVersion = Number(this.toVersionSelect?.value || '');
        if (!Number.isFinite(fromVersion) || !Number.isFinite(toVersion)) {
            this.setStatus('请选择基准版本和对比版本。', 'error');
            return;
        }

        const gridSize = this.normalizeGridSize(this.gridSizeInput?.value || '');

        this.setLoading(true);
        this.setStatus('正在执行版本对比...', 'warning');
        this.showSkeleton();

        const payload: HistoryComparisonPayload = {
            dataset_id: datasetId,
            from_version: fromVersion,
            to_version: toVersion,
            heatmap_grid_size: gridSize
        };

        await this.runWithRetry(
            async () => {
                const raw = await this.apiService.compareHistoryVersions(payload);
                this.comparison = this.normalizeComparisonResponse(raw, payload);
                this.cellDiffEntries = this.buildCellDiffEntries(this.comparison);

                const maxDiff = this.comparison.summary.max_absolute_diff;
                if (this.thresholdRange) {
                    this.thresholdRange.max = String(Math.max(maxDiff, 1));
                    this.thresholdRange.step = maxDiff > 0 && maxDiff < 1 ? '0.0001' : '0.001';
                }

                const suggestedThreshold = maxDiff > 0 ? maxDiff * 0.3 : 0;
                this.setThreshold(suggestedThreshold, false);
                this.applyFilterAndSort();
                this.setStatus(`版本对比完成：v${fromVersion} → v${toVersion}。`, 'success');
                this.lastRetryAction = null;
                this.resetRefreshCountdown();
            },
            '版本对比'
        ).catch(() => {
            this.comparison = null;
            this.cellDiffEntries = [];
            this.applyFilterAndSort();
            this.lastRetryAction = async () => this.handleRunCompare();
        }).finally(() => {
            this.setLoading(false);
            this.hideSkeleton();
        });
    }

    private renderVersionPicker(): void {
        if (!this.fromVersionSelect || !this.toVersionSelect) {
            return;
        }

        if (this.snapshots.length === 0) {
            this.fromVersionSelect.innerHTML = '<option value="">' + I18n.t('historyversion.noVersions') + '</option>';
            this.toVersionSelect.innerHTML = '<option value="">' + I18n.t('historyversion.noVersions') + '</option>';
            return;
        }

        const options = this.snapshots
            .map((snapshot) => {
                const label = snapshot.version_label || `v${snapshot.version}`;
                return `<option value="${snapshot.version}">v${snapshot.version} | ${this.escapeHtml(label)}</option>`;
            })
            .join('');

        this.fromVersionSelect.innerHTML = options;
        this.toVersionSelect.innerHTML = options;

        if (this.snapshots.length >= 2) {
            this.toVersionSelect.value = String(this.snapshots[0].version);
            this.fromVersionSelect.value = String(this.snapshots[1].version);
        } else {
            this.fromVersionSelect.value = String(this.snapshots[0].version);
            this.toVersionSelect.value = String(this.snapshots[0].version);
        }
    }

    private renderVersionInfo(): void {
        if (!this.versionInfoHost) {
            return;
        }

        if (this.snapshots.length === 0) {
            this.versionInfoHost.innerHTML = '<div class="history-empty">' + I18n.t('historyversion.loadVersionListFirst') + '</div>';
            return;
        }

        const fromVersion = Number(this.fromVersionSelect?.value || '');
        const toVersion = Number(this.toVersionSelect?.value || '');

        const fromSnapshot = this.snapshots.find((item) => item.version === fromVersion) || null;
        const toSnapshot = this.snapshots.find((item) => item.version === toVersion) || null;

        this.versionInfoHost.innerHTML = `
            <div class="history-compare-version-card">
                ${this.renderVersionCard('基准版本', fromSnapshot)}
            </div>
            <div class="history-compare-version-card">
                ${this.renderVersionCard('对比版本', toSnapshot)}
            </div>
        `;
    }

    private renderVersionCard(title: string, snapshot: HistorySnapshotMetadata | null): string {
        if (!snapshot) {
            return `<div class="history-empty">${title}未选择</div>`;
        }

        const label = snapshot.version_label || `v${snapshot.version}`;
        return `
            <h5>${this.escapeHtml(title)}：v${snapshot.version}</h5>
            <dl>
                <div><dt>标签</dt><dd>${this.escapeHtml(label)}</dd></div>
                <div><dt>记录数</dt><dd>${snapshot.record_count}</dd></div>
                <div><dt>创建时间</dt><dd>${this.formatDateTime(snapshot.created_at)}</dd></div>
            </dl>
        `;
    }

    private applyFilterAndSort(): void {
        const source = this.comparison?.diffs || [];
        const keyword = (this.searchInput?.value || '').trim().toLowerCase();
        const changedOnly = Boolean(this.changedOnlyCheckbox?.checked);

        const filtered = source.filter((item) => {
            if (changedOnly && !(item.absolute_diff > 1e-12)) {
                return false;
            }
            if (keyword && !item.key.toLowerCase().includes(keyword)) {
                return false;
            }
            return true;
        });

        filtered.sort((a, b) => this.compareDiffItem(a, b));
        this.filteredDiffs = filtered;

        if (this.selectedDiffKey && !this.filteredDiffs.some((item) => item.key === this.selectedDiffKey)) {
            this.selectedDiffKey = null;
        }

        this.renderSummary();
        this.renderDistribution();
        this.renderTable();
        this.renderDetail();
        this.renderHeatmapLayers();
    }

    private compareDiffItem(a: ComparisonDiffItem, b: ComparisonDiffItem): number {
        let cmp = 0;

        if (this.sortKey === 'key') {
            cmp = a.key.localeCompare(b.key, 'zh-CN');
        } else if (this.sortKey === 'timestamp') {
            cmp = this.toTimestamp(a.timestamp) - this.toTimestamp(b.timestamp);
        } else {
            cmp = this.toNumericByKey(a, this.sortKey) - this.toNumericByKey(b, this.sortKey);
        }

        return this.sortDirection === 'asc' ? cmp : -cmp;
    }

    private toNumericByKey(item: ComparisonDiffItem, key: SortKey): number {
        if (key === 'absolute_diff') return item.absolute_diff;
        if (key === 'relative_diff') return item.relative_diff ?? -1;
        if (key === 'from_value') return item.from_value ?? Number.NEGATIVE_INFINITY;
        if (key === 'to_value') return item.to_value ?? Number.NEGATIVE_INFINITY;
        return 0;
    }

    private toTimestamp(value: string | null): number {
        if (!value) {
            return Number.NEGATIVE_INFINITY;
        }
        const ts = new Date(value).getTime();
        return Number.isNaN(ts) ? Number.NEGATIVE_INFINITY : ts;
    }

    private renderSummary(): void {
        if (!this.summaryHost) {
            return;
        }

        if (!this.comparison) {
            this.summaryHost.innerHTML = '<div class="history-empty">' + I18n.t('historyversion.runComparisonForSummary') + '</div>';
            return;
        }

        const summary = this.comparison.summary;
        const ratio = summary.total_points > 0 ? (summary.changed_points / summary.total_points) * 100 : 0;
        const highlightedCount = this.comparison.diffs.filter(
            (item) => item.absolute_diff >= this.highlightedThreshold
        ).length;

        const dataComparison = this.buildDataComparisonResult();

        let dataComparisonSection = '';
        if (dataComparison) {
            const stats = dataComparison.fieldStats.value;
            dataComparisonSection = `
                <div class="history-compare-summary-item">
                    <span class="label">DataComparison 均值变化</span>
                    <span class="value">${stats.diff.meanDiff.toFixed(6)} (${stats.diff.percentChange.toFixed(2)}%)</span>
                </div>
                <div class="history-compare-summary-item">
                    <span class="label">DataComparison 匹配点</span>
                    <span class="value">${dataComparison.matchedPoints}</span>
                </div>
            `;
        }

        this.summaryHost.innerHTML = `
            <div class="history-compare-summary-grid">
                <div class="history-compare-summary-item">
                    <span class="label">总点位数</span>
                    <span class="value">${summary.total_points}</span>
                </div>
                <div class="history-compare-summary-item">
                    <span class="label">变化点位数</span>
                    <span class="value">${summary.changed_points} (${ratio.toFixed(2)}%)</span>
                </div>
                <div class="history-compare-summary-item">
                    <span class="label">未变化点位数</span>
                    <span class="value">${summary.unchanged_points}</span>
                </div>
                <div class="history-compare-summary-item">
                    <span class="label">平均绝对差值</span>
                    <span class="value">${summary.avg_absolute_diff.toFixed(6)}</span>
                </div>
                <div class="history-compare-summary-item">
                    <span class="label">最大/最小绝对差值</span>
                    <span class="value">${summary.max_absolute_diff.toFixed(6)} / ${summary.min_absolute_diff.toFixed(6)}</span>
                </div>
                <div class="history-compare-summary-item">
                    <span class="label">阈值高亮点位数</span>
                    <span class="value">${highlightedCount} (阈值 ${this.highlightedThreshold.toFixed(6)})</span>
                </div>
                ${dataComparisonSection}
            </div>
        `;
    }

    private renderDistribution(): void {
        if (!this.distributionHost) {
            return;
        }

        if (!this.comparison) {
            this.distributionHost.innerHTML = '<div class="history-empty">' + I18n.t('historyversion.runComparisonForDiffDistribution') + '</div>';
            return;
        }

        const values = this.comparison.diffs.map((item) => item.absolute_diff);
        const maxVal = Math.max(...values, 0);
        const bins = 8;
        const counts = new Array<number>(bins).fill(0);

        if (maxVal > 0) {
            values.forEach((value) => {
                const idx = Math.min(bins - 1, Math.floor((value / maxVal) * bins));
                counts[idx] += 1;
            });
        } else {
            counts[0] = values.length;
        }

        const maxCount = Math.max(...counts, 1);

        const bars = counts
            .map((count, idx) => {
                const left = (idx / bins) * maxVal;
                const right = ((idx + 1) / bins) * maxVal;
                const widthPct = (count / maxCount) * 100;
                return `
                <div class="history-compare-distribution-row">
                    <span class="range">${left.toFixed(4)} - ${right.toFixed(4)}</span>
                    <div class="bar-track">
                        <span class="bar-fill" style="width:${widthPct}%"></span>
                    </div>
                    <span class="count">${count}</span>
                </div>
            `;
            })
            .join('');

        this.distributionHost.innerHTML = `
            <h5>变化分布直方图（绝对差值）</h5>
            <div class="history-compare-distribution-list">${bars}</div>
        `;
    }

    private renderTable(): void {
        if (!this.tableHost) {
            return;
        }

        if (!this.comparison) {
            this.tableHost.innerHTML = '<div class="history-empty">' + I18n.t('historyversion.runComparisonForDiffTable') + '</div>';
            return;
        }

        if (this.filteredDiffs.length === 0) {
            this.tableHost.innerHTML = '<div class="history-empty">' + I18n.t('historyversion.noDataUnderFilter') + '</div>';
            return;
        }

        const rows = this.filteredDiffs
            .map((item) => {
                const highlighted = item.absolute_diff >= this.highlightedThreshold;
                const selected = this.selectedDiffKey === item.key;
                const classes = [highlighted ? 'is-highlighted' : '', selected ? 'is-selected' : '']
                    .filter(Boolean)
                    .join(' ');

                return `
                <tr class="${classes}">
                    <td><button type="button" class="history-link-btn" data-action="select-diff" data-diff-key="${this.escapeHtml(item.key)}">${this.escapeHtml(item.key)}</button></td>
                    <td>${this.formatMaybeNumber(item.from_value)}</td>
                    <td>${this.formatMaybeNumber(item.to_value)}</td>
                    <td>${item.absolute_diff.toFixed(6)}</td>
                    <td>${this.formatMaybePercent(item.relative_diff)}</td>
                    <td>${item.timestamp ? this.formatDateTime(item.timestamp) : '-'}</td>
                    <td>${this.formatCoordinates(item.x, item.y)}</td>
                </tr>
            `;
            })
            .join('');

        this.tableHost.innerHTML = `
            <table class="history-table history-compare-table">
                <thead>
                    <tr>
                        <th>点位 key</th>
                        <th>基准值</th>
                        <th>对比值</th>
                        <th>绝对差值</th>
                        <th>相对变化</th>
                        <th>时间</th>
                        <th>坐标</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
            <p class="history-compare-hint">共 ${this.filteredDiffs.length} / ${this.comparison.diffs.length} 条记录，当前排序字段：${this.sortKey} (${this.sortDirection})。</p>
        `;
    }

    private renderDetail(): void {
        if (!this.detailHost) {
            return;
        }

        if (!this.comparison) {
            this.detailHost.innerHTML = '<div class="history-empty">' + I18n.t('historyversion.runComparisonForDetails') + '</div>';
            return;
        }

        let target = this.comparison.diffs[0] || null;
        if (this.selectedDiffKey) {
            target = this.comparison.diffs.find((item) => item.key === this.selectedDiffKey) || target;
        }

        if (!target) {
            this.detailHost.innerHTML = '<div class="history-empty">' + I18n.t('historyversion.noVersions') + '</div>';
            return;
        }

        this.detailHost.innerHTML = `
            <dl class="history-detail-list">
                <div><dt>点位 key</dt><dd>${this.escapeHtml(target.key)}</dd></div>
                <div><dt>基准值</dt><dd>${this.formatMaybeNumber(target.from_value)}</dd></div>
                <div><dt>对比值</dt><dd>${this.formatMaybeNumber(target.to_value)}</dd></div>
                <div><dt>绝对差值</dt><dd>${target.absolute_diff.toFixed(6)}</dd></div>
                <div><dt>相对变化</dt><dd>${this.formatMaybePercent(target.relative_diff)}</dd></div>
                <div><dt>时间</dt><dd>${target.timestamp ? this.formatDateTime(target.timestamp) : '-'}</dd></div>
                <div><dt>坐标</dt><dd>${this.formatCoordinates(target.x, target.y)}</dd></div>
                <div><dt>高亮状态</dt><dd>${target.absolute_diff >= this.highlightedThreshold ? '超过阈值，已高亮' : '未超过阈值'}</dd></div>
            </dl>
        `;
    }

    private renderHeatmapLayers(): void {
        if (!this.heatmapHost || !this.comparison) {
            if (this.heatmapHost) {
                const heatLayer = this.heatmapHost.querySelector('[data-layer-id="diff-heatmap"]');
                const highlightLayer = this.heatmapHost.querySelector('[data-layer-id="highlight-overlay"]');
                if (heatLayer) {
                    heatLayer.innerHTML = '<div class="history-empty">' + I18n.t('historyversion.runComparisonForHeatmap') + '</div>';
                }
                if (highlightLayer) {
                    highlightLayer.innerHTML = '';
                }
            }
            return;
        }

        const heatLayer = this.heatmapHost.querySelector('[data-layer-id="diff-heatmap"]') as HTMLElement | null;
        const highlightLayer = this.heatmapHost.querySelector(
            '[data-layer-id="highlight-overlay"]'
        ) as HTMLElement | null;

        if (!heatLayer || !highlightLayer) {
            return;
        }

        const heatmap = this.comparison.heatmap;
        const maxVal = Math.max(...heatmap.matrix.flat(), 0);

        const heatCells: string[] = [];
        for (let row = 0; row < heatmap.rows; row += 1) {
            for (let col = 0; col < heatmap.cols; col += 1) {
                const value = this.safeMatrixValue(heatmap.matrix, row, col);
                const color = this.getHeatmapColor(value, maxVal);
                heatCells.push(`
                    <div
                        class="history-compare-heat-cell"
                        style="background:${color}"
                        title="行 ${row + 1} / 列 ${col + 1}，差值 ${value.toFixed(6)}"
                    ></div>
                `);
            }
        }

        heatLayer.style.gridTemplateColumns = `repeat(${heatmap.cols}, 1fr)`;
        heatLayer.innerHTML = heatCells.join('');

        const highlightedCells = this.buildHighlightedCells(heatmap);
        highlightLayer.style.gridTemplateColumns = `repeat(${heatmap.cols}, 1fr)`;
        highlightLayer.innerHTML = highlightedCells;

        this.syncLayerStyles();
    }

    private buildHighlightedCells(heatmap: ComparisonHeatmap): string {
        const html: string[] = [];
        const topDiffByCell = this.getTopDiffByCell();

        for (let row = 0; row < heatmap.rows; row += 1) {
            for (let col = 0; col < heatmap.cols; col += 1) {
                const value = this.safeMatrixValue(heatmap.matrix, row, col);
                if (value < this.highlightedThreshold) {
                    html.push('<div class="history-compare-highlight-empty"></div>');
                    continue;
                }

                const key = `${row}:${col}`;
                const topDiff = topDiffByCell.get(key);
                const hint = topDiff
                    ? `${topDiff.key} | 绝对差值 ${topDiff.absolute_diff.toFixed(6)}`
                    : `行 ${row + 1} / 列 ${col + 1}`;

                html.push(`
                    <button
                        type="button"
                        class="history-compare-highlight-cell"
                        data-action="select-cell"
                        data-row="${row}"
                        data-col="${col}"
                        title="${this.escapeHtml(hint)}"
                    >
                        ${value.toFixed(3)}
                    </button>
                `);
            }
        }

        return html.join('');
    }

    private handleSelectDiff(key: string): void {
        this.selectedDiffKey = key;
        this.renderTable();
        this.renderDetail();
    }

    private handleSelectCell(row: number, col: number): void {
        const related = this.cellDiffEntries.filter((entry) => entry.row === row && entry.col === col);
        if (related.length === 0) {
            this.setStatus(`网格 (${row + 1}, ${col + 1}) 没有关联点位。`, 'warning');
            return;
        }

        const topDiff = related.sort((a, b) => b.diff.absolute_diff - a.diff.absolute_diff)[0].diff;
        this.selectedDiffKey = topDiff.key;
        this.setStatus(`已定位网格 (${row + 1}, ${col + 1}) 最大变化点：${topDiff.key}`, 'success');
        this.renderTable();
        this.renderDetail();
    }

    private buildCellDiffEntries(comparison: ComparisonResponse): DiffCellEntry[] {
        const { diffs, heatmap } = comparison;
        const entries: DiffCellEntry[] = [];

        const validWithCoord = diffs.filter((item) => item.x !== null && item.y !== null);
        if (validWithCoord.length > 0) {
            const xs = validWithCoord.map((item) => item.x as number);
            const ys = validWithCoord.map((item) => item.y as number);
            const minX = Math.min(...xs);
            const maxX = Math.max(...xs);
            const minY = Math.min(...ys);
            const maxY = Math.max(...ys);

            const spanX = Math.max(maxX - minX, 1e-12);
            const spanY = Math.max(maxY - minY, 1e-12);

            diffs.forEach((diff, index) => {
                if (diff.x === null || diff.y === null) {
                    const projected = this.projectDiffToRowMid(index, diffs.length, heatmap.rows, heatmap.cols);
                    entries.push({ row: projected.row, col: projected.col, diff });
                    return;
                }

                const col = Math.min(
                    heatmap.cols - 1,
                    Math.max(0, Math.floor(((diff.x - minX) / spanX) * (heatmap.cols - 1)))
                );
                const row = Math.min(
                    heatmap.rows - 1,
                    Math.max(0, Math.floor(((diff.y - minY) / spanY) * (heatmap.rows - 1)))
                );
                entries.push({ row, col, diff });
            });

            return entries;
        }

        diffs.forEach((diff, index) => {
            const projected = this.projectDiffToRowMid(index, diffs.length, heatmap.rows, heatmap.cols);
            entries.push({ row: projected.row, col: projected.col, diff });
        });
        return entries;
    }

    private projectDiffToRowMid(
        index: number,
        total: number,
        rows: number,
        cols: number
    ): { row: number; col: number } {
        const row = Math.floor(rows / 2);
        if (total <= 1) {
            return { row, col: 0 };
        }
        const col = Math.min(cols - 1, Math.max(0, Math.floor((index / (total - 1)) * (cols - 1))));
        return { row, col };
    }

    private getTopDiffByCell(): Map<string, ComparisonDiffItem> {
        const map = new Map<string, ComparisonDiffItem>();
        this.cellDiffEntries.forEach((entry) => {
            const key = `${entry.row}:${entry.col}`;
            const current = map.get(key);
            if (!current || entry.diff.absolute_diff > current.absolute_diff) {
                map.set(key, entry.diff);
            }
        });
        return map;
    }

    private buildDataComparisonResult() {
        if (!this.comparison) {
            return null;
        }

        const pointsA = this.comparison.diffs.map((item, idx) => ({
            x: item.x ?? idx,
            y: item.y ?? 0,
            value: item.from_value ?? 0
        }));

        const pointsB = this.comparison.diffs.map((item, idx) => ({
            x: item.x ?? idx,
            y: item.y ?? 0,
            value: item.to_value ?? 0
        }));

        const comparison = new DataComparison();
        comparison.setDatasets(
            { name: `v${this.comparison.from_version}`, points: pointsA },
            { name: `v${this.comparison.to_version}`, points: pointsB }
        );

        return comparison.compare('value');
    }

    private setThreshold(value: number, fromInput: boolean): void {
        const next = Math.max(0, value);
        this.highlightedThreshold = next;

        if (this.thresholdInput && (!fromInput || document.activeElement !== this.thresholdInput)) {
            this.thresholdInput.value = String(next);
        }
        if (this.thresholdRange && (!fromInput || document.activeElement !== this.thresholdRange)) {
            this.thresholdRange.value = String(next);
        }

        this.renderSummary();
        this.renderTable();
        this.renderDetail();
        this.renderHeatmapLayers();
    }

    private exportCsv(): void {
        if (!this.comparison) {
            this.setStatus('请先执行版本对比再导出。', 'error');
            return;
        }

        const summary = this.comparison.summary;
        const lines: string[] = [
            `# dataset_id,${this.comparison.dataset_id}`,
            `# from_version,${this.comparison.from_version}`,
            `# to_version,${this.comparison.to_version}`,
            `# total_points,${summary.total_points}`,
            `# changed_points,${summary.changed_points}`,
            `# unchanged_points,${summary.unchanged_points}`,
            `# avg_absolute_diff,${summary.avg_absolute_diff}`,
            `# max_absolute_diff,${summary.max_absolute_diff}`,
            `# min_absolute_diff,${summary.min_absolute_diff}`,
            `# highlight_threshold,${this.highlightedThreshold}`,
            'key,from_value,to_value,absolute_diff,relative_diff,timestamp,x,y,is_highlighted'
        ];

        this.comparison.diffs.forEach((item) => {
            const row = [
                this.csvCell(item.key),
                this.csvCell(item.from_value),
                this.csvCell(item.to_value),
                this.csvCell(item.absolute_diff),
                this.csvCell(item.relative_diff),
                this.csvCell(item.timestamp),
                this.csvCell(item.x),
                this.csvCell(item.y),
                this.csvCell(item.absolute_diff >= this.highlightedThreshold)
            ].join(',');
            lines.push(row);
        });

        const csv = lines.join('\n');
        this.downloadBlob(
            new Blob([csv], { type: 'text/csv;charset=utf-8' }),
            `${this.comparison.dataset_id}_v${this.comparison.from_version}_v${this.comparison.to_version}_diff.csv`
        );

        this.notifySuccess('CSV 导出完成', '已导出版本对比 CSV 文件。');
    }

    private exportGeoJson(): void {
        if (!this.comparison) {
            this.setStatus('请先执行版本对比再导出。', 'error');
            return;
        }

        const features = this.comparison.diffs.map((item) => ({
            type: 'Feature',
            geometry:
                item.x !== null && item.y !== null
                    ? {
                          type: 'Point',
                          coordinates: [item.x, item.y]
                      }
                    : null,
            properties: {
                key: item.key,
                from_value: item.from_value,
                to_value: item.to_value,
                absolute_diff: item.absolute_diff,
                relative_diff: item.relative_diff,
                timestamp: item.timestamp,
                is_highlighted: item.absolute_diff >= this.highlightedThreshold
            }
        }));

        const geojson = {
            type: 'FeatureCollection',
            dataset_id: this.comparison.dataset_id,
            from_version: this.comparison.from_version,
            to_version: this.comparison.to_version,
            highlight_threshold: this.highlightedThreshold,
            summary: this.comparison.summary,
            generated_at: new Date().toISOString(),
            features
        };

        const content = JSON.stringify(geojson, null, 2);
        this.downloadBlob(
            new Blob([content], { type: 'application/geo+json' }),
            `${this.comparison.dataset_id}_v${this.comparison.from_version}_v${this.comparison.to_version}_diff.geojson`
        );

        this.notifySuccess('GeoJSON 导出完成', '已导出版本对比 GeoJSON 文件。');
    }

    private downloadBlob(blob: Blob, filename: string): void {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(url);
    }

    private applyLayerVisibility(layerId: string, visible: boolean): void {
        if (!this.root) {
            return;
        }
        const element = this.root.querySelector(`[data-layer-id="${layerId}"]`) as HTMLElement | null;
        if (!element) {
            return;
        }
        element.style.display = visible ? 'grid' : 'none';
    }

    private applyLayerOpacity(layerId: string, opacity: number): void {
        if (!this.root) {
            return;
        }
        const element = this.root.querySelector(`[data-layer-id="${layerId}"]`) as HTMLElement | null;
        if (!element) {
            return;
        }
        element.style.opacity = String(Math.max(0, Math.min(100, opacity)) / 100);
    }

    private syncLayerStyles(): void {
        if (!this.layerPanel) {
            return;
        }
        this.layerPanel.getAllConfigs().forEach((layer) => {
            this.applyLayerVisibility(layer.layerId, layer.visible);
            this.applyLayerOpacity(layer.layerId, layer.opacity);
        });
    }

    private syncAutoRefreshSelect(): void {
        const interval = Number(this.readLocalStorage(COMPARE_AUTO_REFRESH_KEY) || '0');
        if (this.autoRefreshSelect) {
            this.autoRefreshSelect.value = Number.isFinite(interval) ? String(Math.max(0, interval)) : '0';
        }
    }

    private updateAutoRefreshFromSelect(): void {
        const intervalSec = Number(this.autoRefreshSelect?.value || '0');
        this.writeLocalStorage(COMPARE_AUTO_REFRESH_KEY, String(intervalSec));
        this.stopAutoRefresh();
        if (!Number.isFinite(intervalSec) || intervalSec <= 0) {
            if (this.refreshProgressElement) {
                this.refreshProgressElement.textContent = I18n.t('historyversion.autoRefreshOff');
            }
            return;
        }
        this.refreshRemainSec = Math.floor(intervalSec);
        this.autoRefreshTimer = window.setInterval(() => {
            if (!this.loading) {
                void this.handleRefreshCompare();
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
                this.refreshProgressElement.textContent = I18n.t('historyversion.autoRefreshCountdown', { seconds: this.refreshRemainSec });
            }
            if (this.refreshRemainSec <= 0) {
                this.refreshRemainSec = Math.floor(intervalSec);
            }
        }, 1000);
    }

    private showSkeleton(): void {
        if (!this.summaryHost || !this.tableHost) {
            return;
        }
        SkeletonLoader.hideByContainer(this.summaryHost);
        SkeletonLoader.hideByContainer(this.tableHost);
        this.summarySkeleton = SkeletonLoader.show(this.summaryHost, 'card', {});
        this.tableSkeleton = SkeletonLoader.show(this.tableHost, 'list', { lines: 8, showAvatar: false });
    }

    private hideSkeleton(): void {
        SkeletonLoader.hide(this.summarySkeleton);
        SkeletonLoader.hide(this.tableSkeleton);
        this.summarySkeleton = null;
        this.tableSkeleton = null;
    }

    private async runWithRetry(executor: () => Promise<void>, actionName: string): Promise<void> {
        for (let attempt = 0; attempt <= RETRY_TIMES; attempt += 1) {
            try {
                await executor();
                return;
            } catch (error) {
                const message = this.getErrorMessage(error);
                if (attempt >= RETRY_TIMES || !/(timeout|network|fetch|502|503|504|连接|超时|网络)/i.test(message)) {
                    this.setStatus(`${actionName}失败：${this.classifyError(message)}，${message}`, 'error');
                    throw error;
                }
                this.setStatus(`${actionName}失败，正在第 ${attempt + 1} 次重试...`, 'warning');
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

    private setLoading(loading: boolean): void {
        if (!this.root) {
            return;
        }
        this.loading = loading;
        this.root.querySelectorAll('button[data-action]').forEach((button) => {
            (button as HTMLButtonElement).disabled = loading;
        });
    }

    private setStatus(message: string, type: StatusType = 'success'): void {
        if (!this.statusElement) {
            return;
        }
        this.statusElement.className = `status-message ${type}`;
        this.statusElement.textContent = type === 'error' && this.lastRetryAction
            ? `${message}；可点击“重试”。`
            : message;
    }

    private notifySuccess(title: string, body: string): void {
        this.setStatus(body, 'success');
        notificationManager.show({
            type: 'dataUpdate',
            title,
            body,
            priority: 'normal'
        });
    }

    private normalizeComparisonResponse(
        raw: Record<string, unknown>,
        payload: HistoryComparisonPayload
    ): ComparisonResponse {
        const datasetId = typeof raw.dataset_id === 'string' ? raw.dataset_id : payload.dataset_id;
        const fromVersion = this.toFiniteNumber(raw.from_version, payload.from_version);
        const toVersion = this.toFiniteNumber(raw.to_version, payload.to_version);

        const summaryRaw = this.asObject(raw.summary);
        const summary: ComparisonSummary = {
            total_points: this.toFiniteNumber(summaryRaw.total_points, 0),
            changed_points: this.toFiniteNumber(summaryRaw.changed_points, 0),
            unchanged_points: this.toFiniteNumber(summaryRaw.unchanged_points, 0),
            avg_absolute_diff: this.toFiniteNumber(summaryRaw.avg_absolute_diff, 0),
            max_absolute_diff: this.toFiniteNumber(summaryRaw.max_absolute_diff, 0),
            min_absolute_diff: this.toFiniteNumber(summaryRaw.min_absolute_diff, 0)
        };

        const diffsRaw = Array.isArray(raw.diffs) ? raw.diffs : [];
        const diffs = diffsRaw.map((item, index) => this.normalizeDiffItem(item, index));

        const heatmapRaw = this.asObject(raw.heatmap);
        const rows = Math.max(1, this.toFiniteNumber(heatmapRaw.rows, payload.heatmap_grid_size || DEFAULT_GRID_SIZE));
        const cols = Math.max(1, this.toFiniteNumber(heatmapRaw.cols, payload.heatmap_grid_size || DEFAULT_GRID_SIZE));
        const matrix = this.normalizeMatrix(heatmapRaw.matrix, rows, cols);

        return {
            dataset_id: datasetId,
            from_version: fromVersion,
            to_version: toVersion,
            summary,
            diffs,
            heatmap: { rows, cols, matrix }
        };
    }

    private normalizeDiffItem(raw: unknown, index: number): ComparisonDiffItem {
        const item = this.asObject(raw);
        const keyValue = typeof item.key === 'string' && item.key.trim() ? item.key.trim() : `index:${index}`;
        return {
            key: keyValue,
            from_value: this.toNullableFiniteNumber(item.from_value),
            to_value: this.toNullableFiniteNumber(item.to_value),
            absolute_diff: this.toFiniteNumber(item.absolute_diff, 0),
            relative_diff: this.toNullableFiniteNumber(item.relative_diff),
            timestamp: this.toNullableString(item.timestamp),
            x: this.toNullableFiniteNumber(item.x),
            y: this.toNullableFiniteNumber(item.y)
        };
    }

    private normalizeMatrix(raw: unknown, rows: number, cols: number): number[][] {
        if (!Array.isArray(raw)) {
            return new Array(rows).fill(0).map(() => new Array(cols).fill(0));
        }

        const matrix: number[][] = [];
        for (let row = 0; row < rows; row += 1) {
            const rowRaw = Array.isArray(raw[row]) ? (raw[row] as unknown[]) : [];
            const rowValues: number[] = [];
            for (let col = 0; col < cols; col += 1) {
                rowValues.push(this.toFiniteNumber(rowRaw[col], 0));
            }
            matrix.push(rowValues);
        }
        return matrix;
    }

    private normalizeGridSize(raw: string): number {
        const value = Number(raw);
        if (!Number.isFinite(value)) {
            return DEFAULT_GRID_SIZE;
        }
        return Math.max(4, Math.min(64, Math.floor(value)));
    }

    private parseThreshold(raw: string): number {
        const value = Number(raw);
        if (!Number.isFinite(value)) {
            return 0;
        }
        return Math.max(0, value);
    }

    private safeMatrixValue(matrix: number[][], row: number, col: number): number {
        if (!Array.isArray(matrix[row])) {
            return 0;
        }
        const value = matrix[row][col];
        return Number.isFinite(value) ? value : 0;
    }

    private formatDateTime(raw: string): string {
        const date = new Date(raw);
        if (Number.isNaN(date.getTime())) {
            return raw;
        }
        return date.toLocaleString('zh-CN', { hour12: false });
    }

    private formatMaybeNumber(value: number | null): string {
        if (value === null || !Number.isFinite(value)) {
            return '-';
        }
        return value.toFixed(6);
    }

    private formatMaybePercent(value: number | null): string {
        if (value === null || !Number.isFinite(value)) {
            return '-';
        }
        return `${(value * 100).toFixed(2)}%`;
    }

    private formatCoordinates(x: number | null, y: number | null): string {
        if (x === null || y === null) {
            return '-';
        }
        return `${x.toFixed(6)}, ${y.toFixed(6)}`;
    }

    private getHeatmapColor(value: number, maxValue: number): string {
        if (!Number.isFinite(value) || value <= 0 || maxValue <= 0) {
            return 'rgba(56, 189, 248, 0.05)';
        }

        const ratio = Math.min(1, value / maxValue);
        const red = Math.round(255 * ratio);
        const green = Math.round(180 - 140 * ratio);
        const blue = Math.round(80 - 60 * ratio);
        const alpha = 0.12 + ratio * 0.78;
        return `rgba(${red}, ${green}, ${Math.max(0, blue)}, ${alpha.toFixed(3)})`;
    }

    private csvCell(value: unknown): string {
        if (value === null || typeof value === 'undefined') {
            return '';
        }
        const text = String(value);
        if (/[,"\n]/.test(text)) {
            return `"${text.replace(/"/g, '""')}"`;
        }
        return text;
    }

    private asObject(value: unknown): Record<string, unknown> {
        if (!value || typeof value !== 'object' || Array.isArray(value)) {
            return {};
        }
        return value as Record<string, unknown>;
    }

    private toFiniteNumber(value: unknown, fallback: number): number {
        if (typeof value === 'number' && Number.isFinite(value)) {
            return value;
        }
        if (typeof value === 'string' && value.trim()) {
            const parsed = Number(value);
            if (Number.isFinite(parsed)) {
                return parsed;
            }
        }
        return fallback;
    }

    private toNullableFiniteNumber(value: unknown): number | null {
        if (typeof value === 'number' && Number.isFinite(value)) {
            return value;
        }
        if (typeof value === 'string' && value.trim()) {
            const parsed = Number(value);
            if (Number.isFinite(parsed)) {
                return parsed;
            }
        }
        return null;
    }

    private toNullableString(value: unknown): string | null {
        if (typeof value === 'string' && value.trim()) {
            return value;
        }
        return null;
    }

    private getErrorMessage(error: unknown): string {
        if (error instanceof Error && error.message) {
            return error.message;
        }
        return String(error || '未知错误');
    }

    private escapeHtml(value: string): string {
        return value
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    private readLocalStorage(key: string): string | null {
        try {
            return localStorage.getItem(key);
        } catch {
            return null;
        }
    }

    private writeLocalStorage(key: string, value: string): void {
        try {
            localStorage.setItem(key, value);
        } catch {
            // ignore storage errors
        }
    }
}
