import type {
    HistorySnapshotCreatePayload,
    HistorySnapshotMetadata,
    HistoryTimeSeriesRecord
} from '../../services/API封装.js';
import { APIService } from '../../services/API封装.js';
import { ConfirmDialog } from '../ConfirmDialog.js';
import notificationManager from '../NotificationManager.js';
import { SkeletonLoader } from '../../utils/SkeletonLoader.js';
import { I18n } from '../../utils/I18n';

interface SnapshotLocalState {
    labelOverrides: Record<string, string>;
    archivedKeys: Record<string, true>;
}

interface SnapshotSummary {
    valueRangeText: string;
    timeSpanText: string;
    sizeText: string;
    descriptionText: string;
}

const LOCAL_STATE_KEY = 'udake_history_snapshot_panel_state_v1';
const LAST_DATASET_KEY = 'udake_history_snapshot_last_dataset_id';
const SNAPSHOT_AUTO_REFRESH_KEY = 'udake_history_snapshot_auto_refresh_sec_v1';
const RETRY_TIMES = 2;

type StatusType = 'success' | 'error' | 'warning';

interface RetryOptions {
    actionName: string;
    retries?: number;
}

export class HistorySnapshotPanel {
    private root: HTMLElement | null = null;
    private listHost: HTMLElement | null = null;
    private detailHost: HTMLElement | null = null;
    private statusElement: HTMLElement | null = null;

    private datasetInput: HTMLInputElement | null = null;
    private filterLabelInput: HTMLInputElement | null = null;
    private filterStartInput: HTMLInputElement | null = null;
    private filterEndInput: HTMLInputElement | null = null;
    private showArchivedCheckbox: HTMLInputElement | null = null;

    private createDatasetInput: HTMLInputElement | null = null;
    private createLabelInput: HTMLInputElement | null = null;
    private createDescriptionInput: HTMLTextAreaElement | null = null;
    private createRecordsInput: HTMLTextAreaElement | null = null;
    private createMetadataInput: HTMLTextAreaElement | null = null;

    private keepLatestInput: HTMLInputElement | null = null;
    private autoRefreshSelect: HTMLSelectElement | null = null;
    private refreshProgressElement: HTMLElement | null = null;
    private shortcutHintElement: HTMLElement | null = null;

    private listSkeleton: HTMLDivElement | null = null;
    private detailSkeleton: HTMLDivElement | null = null;
    private autoRefreshTimer: number | null = null;
    private refreshCountdownTimer: number | null = null;
    private refreshRemainSec = 0;
    private lastRetryAction: (() => Promise<void>) | null = null;
    private retryButtonText = '重试上次失败请求';
    private loading = false;

    private localState: SnapshotLocalState = this.loadLocalState();
    private snapshots: HistorySnapshotMetadata[] = [];
    private filteredSnapshots: HistorySnapshotMetadata[] = [];
    private selectedVersions: Set<number> = new Set();
    private selectedVersion: number | null = null;
    private currentDatasetId = '';

    constructor(private readonly apiService: APIService) {}

    public mount(container: HTMLElement): void {
        this.root = document.createElement('div');
        this.root.className = 'integration-module-panel history-snapshot-panel';
        this.root.innerHTML = `
            <h3 class="integration-module-title">历史快照管理</h3>
            <p class="integration-module-description">支持快照创建、筛选、标签编辑、归档管理、详情查看与删除确认。</p>

            <div class="history-snapshot-form-grid">
                <section class="history-snapshot-card">
                    <h4>快照查询与筛选</h4>
                    <div class="integration-field">
                        <label class="integration-field-label" for="snapshot-dataset-id">数据集 ID</label>
                        <input id="snapshot-dataset-id" class="input integration-input" type="text" placeholder="例如 dataset-001">
                    </div>
                    <div class="integration-actions">
                        <button type="button" class="btn btn-secondary integration-action-btn" data-action="load-list">加载快照列表</button>
                    </div>
                    <div class="history-snapshot-inline-filters">
                        <div class="integration-field">
                            <label class="integration-field-label" for="snapshot-filter-label">标签筛选</label>
                            <input id="snapshot-filter-label" class="input integration-input" type="text" placeholder="按标签关键字筛选">
                        </div>
                        <div class="integration-field">
                            <label class="integration-field-label" for="snapshot-filter-start">开始日期</label>
                            <input id="snapshot-filter-start" class="input integration-input" type="date">
                        </div>
                        <div class="integration-field">
                            <label class="integration-field-label" for="snapshot-filter-end">结束日期</label>
                            <input id="snapshot-filter-end" class="input integration-input" type="date">
                        </div>
                    </div>
                    <label class="checkbox-label history-snapshot-checkbox-inline">
                        <input id="snapshot-show-archived" type="checkbox">
                        <span>显示本地归档快照</span>
                    </label>
                </section>

                <section class="history-snapshot-card">
                    <h4>创建快照</h4>
                    <div class="integration-field">
                        <label class="integration-field-label" for="snapshot-create-dataset-id">数据集 ID</label>
                        <input id="snapshot-create-dataset-id" class="input integration-input" type="text" placeholder="与上方一致">
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="snapshot-create-label">版本标签（可选）</label>
                        <input id="snapshot-create-label" class="input integration-input" type="text" placeholder="例如 baseline-v1">
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="snapshot-create-description">描述（可选）</label>
                        <textarea id="snapshot-create-description" class="input integration-input integration-textarea" rows="3" placeholder="简要描述本次版本变更"></textarea>
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="snapshot-create-records">记录数据 JSON（必填）</label>
                        <textarea id="snapshot-create-records" class="input integration-input integration-textarea" rows="8"></textarea>
                    </div>
                    <div class="integration-field">
                        <label class="integration-field-label" for="snapshot-create-metadata">附加元信息 JSON（可选）</label>
                        <textarea id="snapshot-create-metadata" class="input integration-input integration-textarea" rows="4">{}</textarea>
                    </div>
                    <div class="integration-actions">
                        <button type="button" class="btn btn-secondary integration-action-btn" data-action="sync-dataset">使用查询数据集 ID</button>
                        <button type="button" class="btn btn-primary integration-action-btn" data-action="create-snapshot">创建快照</button>
                    </div>
                </section>
            </div>

            <section class="history-snapshot-card history-archive-card">
                <h4>归档管理</h4>
                <div class="history-snapshot-archive-row">
                    <div class="integration-field history-keep-latest-field">
                        <label class="integration-field-label" for="snapshot-keep-latest">后端归档：保留最新版本数</label>
                        <input id="snapshot-keep-latest" class="input integration-input" type="number" min="1" step="1" value="20">
                    </div>
                    <div class="integration-actions">
                        <button type="button" class="btn btn-secondary integration-action-btn" data-action="archive-backend">归档旧版本（后端）</button>
                    </div>
                </div>
                <div class="integration-actions">
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="archive-local-selected">本地归档选中版本</button>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="restore-local-selected">恢复选中本地归档</button>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="restore-local-all">恢复全部本地归档</button>
                </div>
                <div class="integration-actions">
                    <button type="button" class="btn btn-danger integration-action-btn" data-action="delete-selected">批量删除选中版本</button>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="export-selected">批量导出选中版本(JSON)</button>
                </div>
                <p class="history-archive-hint">说明：本地归档仅影响当前界面显示；后端归档会将旧版本移出服务端活动列表。</p>
            </section>

            <section class="history-snapshot-card">
                <h4>刷新与快捷键</h4>
                <div class="history-snapshot-refresh-row">
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="refresh-list">手动刷新</button>
                    <label class="integration-field">
                        <span class="integration-field-label">自动刷新间隔</span>
                        <select id="snapshot-auto-refresh" class="select integration-input">
                            <option value="0">关闭</option>
                            <option value="10">10 秒</option>
                            <option value="30">30 秒</option>
                            <option value="60">60 秒</option>
                            <option value="120">120 秒</option>
                        </select>
                    </label>
                    <button type="button" class="btn btn-secondary integration-action-btn" data-action="retry-last">重试</button>
                </div>
                <p class="history-archive-hint" data-role="snapshot-refresh-progress">自动刷新已关闭。</p>
                <p class="history-archive-hint" data-role="snapshot-shortcut-hint">快捷键：Alt+R 刷新，Alt+L 加载列表，Alt+Shift+Delete 批量删除，Alt+E 批量导出。</p>
            </section>

            <div class="status-message" data-role="history-snapshot-status"></div>

            <div class="history-snapshot-main">
                <div class="history-snapshot-list" data-role="history-list"></div>
                <div class="history-snapshot-detail" data-role="history-detail"></div>
            </div>
        `;

        container.appendChild(this.root);
        this.bindElements();
        this.bindEvents();
        this.bootstrapDefaultValues();
    }

    private bindElements(): void {
        if (!this.root) {
            return;
        }

        this.statusElement = this.root.querySelector('[data-role="history-snapshot-status"]');
        this.listHost = this.root.querySelector('[data-role="history-list"]');
        this.detailHost = this.root.querySelector('[data-role="history-detail"]');

        this.datasetInput = this.root.querySelector('#snapshot-dataset-id');
        this.filterLabelInput = this.root.querySelector('#snapshot-filter-label');
        this.filterStartInput = this.root.querySelector('#snapshot-filter-start');
        this.filterEndInput = this.root.querySelector('#snapshot-filter-end');
        this.showArchivedCheckbox = this.root.querySelector('#snapshot-show-archived');

        this.createDatasetInput = this.root.querySelector('#snapshot-create-dataset-id');
        this.createLabelInput = this.root.querySelector('#snapshot-create-label');
        this.createDescriptionInput = this.root.querySelector('#snapshot-create-description');
        this.createRecordsInput = this.root.querySelector('#snapshot-create-records');
        this.createMetadataInput = this.root.querySelector('#snapshot-create-metadata');

        this.keepLatestInput = this.root.querySelector('#snapshot-keep-latest');
        this.autoRefreshSelect = this.root.querySelector('#snapshot-auto-refresh');
        this.refreshProgressElement = this.root.querySelector('[data-role="snapshot-refresh-progress"]');
        this.shortcutHintElement = this.root.querySelector('[data-role="snapshot-shortcut-hint"]');
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

            const actionElement = target.closest('[data-action]') as HTMLElement | null;
            if (!actionElement) {
                return;
            }

            const action = actionElement.getAttribute('data-action');
            if (!action) {
                return;
            }

            if (action === 'load-list') {
                await this.handleLoadList();
                return;
            }
            if (action === 'sync-dataset') {
                this.syncCreateDatasetFromFilter();
                return;
            }
            if (action === 'create-snapshot') {
                await this.handleCreateSnapshot();
                return;
            }
            if (action === 'archive-backend') {
                await this.handleBackendArchive();
                return;
            }
            if (action === 'archive-local-selected') {
                await this.handleLocalArchiveSelected();
                return;
            }
            if (action === 'restore-local-selected') {
                this.handleLocalRestoreSelected();
                return;
            }
            if (action === 'restore-local-all') {
                this.handleLocalRestoreAll();
                return;
            }
            if (action === 'refresh-list') {
                await this.handleRefreshList();
                return;
            }
            if (action === 'retry-last') {
                await this.handleRetryLast();
                return;
            }
            if (action === 'delete-selected') {
                await this.handleDeleteSelected();
                return;
            }
            if (action === 'export-selected') {
                await this.handleExportSelected();
                return;
            }

            const version = Number(actionElement.getAttribute('data-version') || '');
            if (!Number.isFinite(version)) {
                return;
            }

            if (action === 'view-detail') {
                this.selectedVersion = version;
                this.renderDetail();
                this.renderList();
                return;
            }
            if (action === 'edit-label') {
                this.handleEditLabel(version);
                return;
            }
            if (action === 'toggle-archive') {
                this.toggleLocalArchive(version);
                return;
            }
            if (action === 'delete-snapshot') {
                await this.handleDeleteSnapshot(version);
            }
        });

        this.listHost?.addEventListener('change', (event: Event) => {
            const target = event.target as HTMLElement | null;
            if (!(target instanceof HTMLInputElement)) {
                return;
            }
            if (!target.classList.contains('history-select-version')) {
                return;
            }

            const version = Number(target.getAttribute('data-version') || '');
            if (!Number.isFinite(version)) {
                return;
            }

            if (target.checked) {
                this.selectedVersions.add(version);
            } else {
                this.selectedVersions.delete(version);
            }
        });

        const onFilterChanged = (): void => {
            this.applyFilters();
            this.renderList();
            this.renderDetail();
        };

        this.filterLabelInput?.addEventListener('input', onFilterChanged);
        this.filterStartInput?.addEventListener('change', onFilterChanged);
        this.filterEndInput?.addEventListener('change', onFilterChanged);
        this.showArchivedCheckbox?.addEventListener('change', onFilterChanged);

        this.autoRefreshSelect?.addEventListener('change', () => {
            this.updateAutoRefreshFromSelect();
        });

        this.root.tabIndex = 0;
        this.root.addEventListener('keydown', async (event: KeyboardEvent) => {
            if (!event.altKey) {
                return;
            }
            if (event.key.toLowerCase() === 'r') {
                event.preventDefault();
                await this.handleRefreshList();
                return;
            }
            if (event.key.toLowerCase() === 'l') {
                event.preventDefault();
                await this.handleLoadList();
                return;
            }
            if (event.key.toLowerCase() === 'e') {
                event.preventDefault();
                await this.handleExportSelected();
                return;
            }
            if (event.shiftKey && event.key === 'Delete') {
                event.preventDefault();
                await this.handleDeleteSelected();
            }
        });
    }

    private bootstrapDefaultValues(): void {
        const sampleRecords: HistoryTimeSeriesRecord[] = [
            {
                timestamp: '2026-03-01T00:00:00Z',
                value: 10.2,
                point_id: 'P-001',
                x: 120.15,
                y: 30.25
            },
            {
                timestamp: '2026-03-02T00:00:00Z',
                value: 10.8,
                point_id: 'P-001',
                x: 120.15,
                y: 30.25
            }
        ];

        if (this.createRecordsInput) {
            this.createRecordsInput.value = JSON.stringify(sampleRecords, null, 2);
        }

        const lastDatasetId = this.safeReadLocalStorage(LAST_DATASET_KEY);
        if (lastDatasetId) {
            if (this.datasetInput) {
                this.datasetInput.value = lastDatasetId;
            }
            if (this.createDatasetInput) {
                this.createDatasetInput.value = lastDatasetId;
            }
            this.currentDatasetId = lastDatasetId;
            void this.loadSnapshots(lastDatasetId);
            this.syncAutoRefreshSelect();
            this.updateAutoRefreshFromSelect();
            if (this.shortcutHintElement) {
                this.shortcutHintElement.title = '在当前面板聚焦后使用快捷键';
            }
            return;
        }

        this.renderList();
        this.renderDetail();
        this.syncAutoRefreshSelect();
        this.updateAutoRefreshFromSelect();
        if (this.shortcutHintElement) {
            this.shortcutHintElement.title = '在当前面板聚焦后使用快捷键';
        }
    }

    private syncCreateDatasetFromFilter(): void {
        if (!this.datasetInput || !this.createDatasetInput) {
            return;
        }
        this.createDatasetInput.value = this.datasetInput.value.trim();
    }

    private async handleLoadList(): Promise<void> {
        const datasetId = this.datasetInput?.value.trim() || '';
        if (!datasetId) {
            this.setStatus('请先输入数据集 ID。', 'error');
            return;
        }
        await this.loadSnapshots(datasetId);
    }

    private async handleRefreshList(): Promise<void> {
        if (!this.currentDatasetId) {
            this.setStatus('请先加载数据集后再刷新。', 'warning');
            return;
        }
        await this.loadSnapshots(this.currentDatasetId, true);
    }

    private async handleRetryLast(): Promise<void> {
        if (!this.lastRetryAction) {
            this.setStatus('当前没有可重试的失败请求。', 'warning');
            return;
        }
        await this.lastRetryAction();
    }

    private async loadSnapshots(datasetId: string, forceRefresh = false): Promise<void> {
        const statusMessage = forceRefresh ? '正在刷新快照列表...' : '正在加载快照列表...';
        this.setStatus(statusMessage, 'warning');
        this.setLoading(true);
        this.showSkeleton();
        await this.runWithRetry(
            async () => {
                const response = await this.apiService.listHistorySnapshots(datasetId);
                this.currentDatasetId = datasetId;
                this.safeWriteLocalStorage(LAST_DATASET_KEY, datasetId);

                if (this.createDatasetInput && !this.createDatasetInput.value.trim()) {
                    this.createDatasetInput.value = datasetId;
                }

                this.snapshots = [...(response.versions || [])].sort((a, b) => b.version - a.version);
                this.pruneLocalStateForCurrentDataset();

                if (this.snapshots.length === 0) {
                    this.selectedVersion = null;
                } else if (!this.selectedVersion || !this.snapshots.some((item) => item.version === this.selectedVersion)) {
                    this.selectedVersion = this.snapshots[0].version;
                }

                this.selectedVersions.forEach((version) => {
                    if (!this.snapshots.some((item) => item.version === version)) {
                        this.selectedVersions.delete(version);
                    }
                });

                this.applyFilters();
                this.renderList();
                this.renderDetail();
                this.setStatus(`已加载 ${this.snapshots.length} 个快照版本。`, 'success');
                this.lastRetryAction = null;
                this.resetRefreshCountdown();
            },
            { actionName: forceRefresh ? '刷新快照列表' : '加载快照列表', retries: RETRY_TIMES }
        ).catch(() => {
            this.lastRetryAction = async () => this.loadSnapshots(datasetId, forceRefresh);
        }).finally(() => {
            this.setLoading(false);
            this.hideSkeleton();
        });
    }

    private applyFilters(): void {
        const labelKeyword = this.filterLabelInput?.value.trim().toLowerCase() || '';
        const startDateRaw = this.filterStartInput?.value || '';
        const endDateRaw = this.filterEndInput?.value || '';
        const showArchived = Boolean(this.showArchivedCheckbox?.checked);

        const startDate = startDateRaw ? new Date(`${startDateRaw}T00:00:00`) : null;
        const endDate = endDateRaw ? new Date(`${endDateRaw}T23:59:59`) : null;

        this.filteredSnapshots = this.snapshots.filter((snapshot) => {
            const localKey = this.toLocalSnapshotKey(snapshot.dataset_id, snapshot.version);
            if (!showArchived && this.localState.archivedKeys[localKey]) {
                return false;
            }

            const label = this.getDisplayLabel(snapshot).toLowerCase();
            if (labelKeyword && !label.includes(labelKeyword)) {
                return false;
            }

            const createdAt = new Date(snapshot.created_at);
            if (startDate && createdAt < startDate) {
                return false;
            }
            if (endDate && createdAt > endDate) {
                return false;
            }
            return true;
        });
    }

    private async handleCreateSnapshot(): Promise<void> {
        const datasetId = this.createDatasetInput?.value.trim() || '';
        if (!datasetId) {
            this.setStatus('创建快照前请填写数据集 ID。', 'error');
            return;
        }

        let records: HistoryTimeSeriesRecord[] = [];
        try {
            records = this.parseRecordsInput();
        } catch (error) {
            this.setStatus(this.getErrorMessage(error), 'error');
            return;
        }

        let extraMetadata: Record<string, unknown> = {};
        try {
            extraMetadata = this.parseMetadataInput();
        } catch (error) {
            this.setStatus(this.getErrorMessage(error), 'error');
            return;
        }

        const label = this.createLabelInput?.value.trim() || '';
        const description = this.createDescriptionInput?.value.trim() || '';

        const computedMetadata = this.buildSnapshotMetadata(records);
        const payload: HistorySnapshotCreatePayload = {
            dataset_id: datasetId,
            version_label: label || undefined,
            records,
            metadata: {
                ...extraMetadata,
                ...computedMetadata,
                ...(description ? { description } : {})
            }
        };

        this.setStatus('正在创建快照...', 'warning');
        this.setLoading(true);
        await this.runWithRetry(
            async () => {
                await this.apiService.createHistorySnapshot(payload);
                this.notifySuccess('快照创建成功', `数据集 ${datasetId} 已创建新快照。`);
                if (this.datasetInput) {
                    this.datasetInput.value = datasetId;
                }
                await this.loadSnapshots(datasetId, true);
                this.lastRetryAction = null;
            },
            { actionName: '创建快照', retries: RETRY_TIMES }
        ).catch(() => {
            this.lastRetryAction = async () => this.handleCreateSnapshot();
        }).finally(() => {
            this.setLoading(false);
        });
    }

    private async handleBackendArchive(): Promise<void> {
        if (!this.currentDatasetId) {
            this.setStatus('请先加载一个数据集。', 'error');
            return;
        }
        const keepLatest = Number(this.keepLatestInput?.value || '');
        if (!Number.isFinite(keepLatest) || keepLatest < 1) {
            this.setStatus('保留版本数必须是 >= 1 的整数。', 'error');
            return;
        }

        const confirmed = await ConfirmDialog.confirmDanger({
            title: '确认后端归档',
            message: `将仅保留最新 ${Math.floor(keepLatest)} 个版本，其余版本会从服务端活动列表归档。是否继续？`,
            confirmText: '继续归档',
            cancelText: '取消'
        });
        if (!confirmed) {
            return;
        }

        this.setStatus('正在执行后端归档...', 'warning');
        this.setLoading(true);
        await this.runWithRetry(
            async () => {
                const response = await this.apiService.archiveHistorySnapshots({
                    dataset_id: this.currentDatasetId,
                    keep_latest: Math.floor(keepLatest)
                }) as { archived_count?: number; kept_count?: number };

                const archivedCount = Number(response?.archived_count || 0);
                const keptCount = Number(response?.kept_count || 0);
                this.notifySuccess('后端归档完成', `已归档 ${archivedCount} 个版本，保留 ${keptCount} 个版本。`);
                await this.loadSnapshots(this.currentDatasetId, true);
            },
            { actionName: '后端归档', retries: RETRY_TIMES }
        ).catch(() => {
            this.lastRetryAction = async () => this.handleBackendArchive();
        }).finally(() => {
            this.setLoading(false);
        });
    }

    private async handleLocalArchiveSelected(): Promise<void> {
        if (!this.currentDatasetId) {
            this.setStatus('请先加载快照列表。', 'error');
            return;
        }
        if (this.selectedVersions.size === 0) {
            this.setStatus('请先选择要归档的版本。', 'error');
            return;
        }
        const confirmed = await ConfirmDialog.confirm({
            title: '确认本地归档',
            message: `将本地归档 ${this.selectedVersions.size} 个选中版本，仅影响当前界面显示。是否继续？`,
            confirmText: '确认归档',
            cancelText: '取消'
        });
        if (!confirmed) {
            return;
        }

        this.selectedVersions.forEach((version) => {
            const key = this.toLocalSnapshotKey(this.currentDatasetId, version);
            this.localState.archivedKeys[key] = true;
        });
        this.saveLocalState();
        this.applyFilters();
        this.renderList();
        this.renderDetail();
        this.notifySuccess('本地归档完成', `已归档 ${this.selectedVersions.size} 个选中版本。`);
    }

    private handleLocalRestoreSelected(): void {
        if (!this.currentDatasetId) {
            this.setStatus('请先加载快照列表。', 'error');
            return;
        }

        let restoredCount = 0;
        this.selectedVersions.forEach((version) => {
            const key = this.toLocalSnapshotKey(this.currentDatasetId, version);
            if (this.localState.archivedKeys[key]) {
                delete this.localState.archivedKeys[key];
                restoredCount += 1;
            }
        });

        this.saveLocalState();
        this.applyFilters();
        this.renderList();
        this.renderDetail();

        if (restoredCount === 0) {
            this.setStatus('所选版本中没有本地归档项。', 'warning');
            return;
        }
        this.notifySuccess('恢复完成', `已恢复 ${restoredCount} 个本地归档版本。`);
    }

    private handleLocalRestoreAll(): void {
        if (!this.currentDatasetId) {
            this.setStatus('请先加载快照列表。', 'error');
            return;
        }

        const prefix = `${this.currentDatasetId}::`;
        let restoredCount = 0;
        Object.keys(this.localState.archivedKeys).forEach((key) => {
            if (key.startsWith(prefix)) {
                delete this.localState.archivedKeys[key];
                restoredCount += 1;
            }
        });

        this.saveLocalState();
        this.applyFilters();
        this.renderList();
        this.renderDetail();

        if (restoredCount === 0) {
            this.setStatus('当前数据集没有本地归档版本。', 'warning');
            return;
        }
        this.notifySuccess('恢复完成', `已恢复 ${restoredCount} 个本地归档版本。`);
    }

    private handleEditLabel(version: number): void {
        const snapshot = this.snapshots.find((item) => item.version === version);
        if (!snapshot) {
            return;
        }

        const currentLabel = this.getDisplayLabel(snapshot);
        const nextLabel = window.prompt(I18n.t('historysnapshot.editVersionLabel', { version }), currentLabel);
        if (nextLabel === null) {
            return;
        }

        const key = this.toLocalSnapshotKey(snapshot.dataset_id, snapshot.version);
        const trimmed = nextLabel.trim();

        if (!trimmed) {
            delete this.localState.labelOverrides[key];
        } else {
            this.localState.labelOverrides[key] = trimmed;
        }
        this.saveLocalState();
        this.applyFilters();
        this.renderList();
        this.renderDetail();
        this.notifySuccess('标签已更新', `版本 v${version} 标签已实时生效。`);
    }

    private toggleLocalArchive(version: number): void {
        if (!this.currentDatasetId) {
            return;
        }
        const key = this.toLocalSnapshotKey(this.currentDatasetId, version);
        if (this.localState.archivedKeys[key]) {
            delete this.localState.archivedKeys[key];
            this.notifySuccess('已恢复归档', `版本 v${version} 已恢复显示。`);
        } else {
            this.localState.archivedKeys[key] = true;
            this.notifySuccess('已本地归档', `版本 v${version} 已从列表中归档隐藏。`);
        }
        this.saveLocalState();
        this.applyFilters();
        this.renderList();
        this.renderDetail();
    }

    private async handleDeleteSnapshot(version: number): Promise<void> {
        if (!this.currentDatasetId) {
            this.setStatus('请先加载数据集快照列表。', 'error');
            return;
        }

        const check = this.checkDeletionDependency(version);
        if (check.blockedReason) {
            this.setStatus(`无法删除：${check.blockedReason}`, 'error');
            return;
        }

        const warningMessage = check.warnings.length > 0
            ? `\n\n依赖提示：\n- ${check.warnings.join('\n- ')}`
            : '';

        const confirmed = await ConfirmDialog.confirmDanger({
            title: '删除快照',
            message: `确定删除版本 v${version} 吗？该操作不可撤销。${warningMessage}`,
            confirmText: '确认删除',
            cancelText: '取消'
        });
        if (!confirmed) {
            return;
        }

        this.setStatus(`正在删除版本 v${version}...`, 'warning');
        this.setLoading(true);
        await this.runWithRetry(
            async () => {
                await this.apiService.deleteHistorySnapshot(this.currentDatasetId, version);
                const key = this.toLocalSnapshotKey(this.currentDatasetId, version);
                delete this.localState.archivedKeys[key];
                delete this.localState.labelOverrides[key];
                this.saveLocalState();
                this.notifySuccess('删除成功', `版本 v${version} 已删除。`);
                await this.loadSnapshots(this.currentDatasetId, true);
            },
            { actionName: `删除快照 v${version}`, retries: RETRY_TIMES }
        ).catch(() => {
            this.lastRetryAction = async () => this.handleDeleteSnapshot(version);
        }).finally(() => {
            this.setLoading(false);
        });
    }

    private async handleDeleteSelected(): Promise<void> {
        if (!this.currentDatasetId) {
            this.setStatus('请先加载快照列表。', 'error');
            return;
        }
        const versions = Array.from(this.selectedVersions).sort((a, b) => b - a);
        if (versions.length === 0) {
            this.setStatus('请先勾选要删除的版本。', 'warning');
            return;
        }

        const confirmed = await ConfirmDialog.confirmDanger({
            title: '批量删除确认',
            message: `即将删除 ${versions.length} 个版本（${versions.map(v => `v${v}`).join('、')}）。该操作不可撤销。`,
            confirmText: '确认批量删除',
            cancelText: '取消'
        });
        if (!confirmed) {
            return;
        }

        this.setLoading(true);
        this.setStatus(`正在批量删除 ${versions.length} 个版本...`, 'warning');
        const failures: string[] = [];
        for (const version of versions) {
            try {
                await this.apiService.deleteHistorySnapshot(this.currentDatasetId, version);
                const key = this.toLocalSnapshotKey(this.currentDatasetId, version);
                delete this.localState.archivedKeys[key];
                delete this.localState.labelOverrides[key];
            } catch (error) {
                failures.push(`v${version}: ${this.getErrorMessage(error)}`);
            }
        }
        this.saveLocalState();
        this.selectedVersions.clear();
        await this.loadSnapshots(this.currentDatasetId, true);
        this.setLoading(false);

        if (failures.length > 0) {
            this.setStatus(`批量删除完成，但有 ${failures.length} 项失败。`, 'warning');
            this.lastRetryAction = async () => this.handleDeleteSelected();
            return;
        }
        this.notifySuccess('批量删除完成', `已成功删除 ${versions.length} 个版本。`);
        this.lastRetryAction = null;
    }

    private async handleExportSelected(): Promise<void> {
        if (!this.currentDatasetId) {
            this.setStatus('请先加载快照列表。', 'error');
            return;
        }
        const versions = Array.from(this.selectedVersions).sort((a, b) => b - a);
        if (versions.length === 0) {
            this.setStatus('请先勾选要导出的版本。', 'warning');
            return;
        }
        const confirmed = await ConfirmDialog.confirm({
            title: '批量导出确认',
            message: `将导出 ${versions.length} 个版本为 JSON 文件，是否继续？`,
            confirmText: '确认导出',
            cancelText: '取消'
        });
        if (!confirmed) {
            return;
        }

        const payload = {
            dataset_id: this.currentDatasetId,
            selected_versions: versions,
            exported_at: new Date().toISOString(),
            snapshots: this.snapshots.filter((item) => versions.includes(item.version))
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `${this.currentDatasetId}_selected_snapshots.json`;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(url);
        this.notifySuccess('批量导出完成', `已导出 ${versions.length} 个版本。`);
    }

    private checkDeletionDependency(version: number): { blockedReason: string | null; warnings: string[] } {
        const warnings: string[] = [];
        if (this.snapshots.length <= 1) {
            return {
                blockedReason: '当前仅剩一个版本，删除后将无法进行历史对比。',
                warnings
            };
        }

        const latestVersion = this.snapshots.reduce((max, item) => Math.max(max, item.version), 0);
        if (version === latestVersion) {
            warnings.push('该版本是当前最新版本，趋势分析默认依赖最新版本。');
        }

        const selectedCountWithoutCurrent = Array.from(this.selectedVersions).filter((item) => item !== version).length;
        if (selectedCountWithoutCurrent === 0 && this.selectedVersions.has(version)) {
            warnings.push('该版本是当前唯一选中版本，删除后请重新选择归档批次。');
        }

        return { blockedReason: null, warnings };
    }

    private renderList(): void {
        if (!this.listHost) {
            return;
        }

        if (!this.currentDatasetId) {
            this.listHost.innerHTML = '<div class="history-empty">' + I18n.t('historysnapshot.loadDatasetFirst') + '</div>';
            return;
        }

        if (this.filteredSnapshots.length === 0) {
            this.listHost.innerHTML = '<div class="history-empty">' + I18n.t('historysnapshot.noSnapshotsUnderFilter') + '</div>';
            return;
        }

        const rows = this.filteredSnapshots.map((snapshot) => {
            const key = this.toLocalSnapshotKey(snapshot.dataset_id, snapshot.version);
            const localArchived = Boolean(this.localState.archivedKeys[key]);
            const summary = this.getSnapshotSummary(snapshot);
            const checked = this.selectedVersions.has(snapshot.version) ? 'checked' : '';
            const selectedClass = this.selectedVersion === snapshot.version ? 'is-selected' : '';
            const localLabel = this.localState.labelOverrides[key] ? '<span class="history-tag history-tag-local">本地标签</span>' : '';
            const archiveTag = localArchived ? '<span class="history-tag history-tag-archived">本地归档</span>' : '';

            return `
                <tr class="${selectedClass}">
                    <td>
                        <input
                            type="checkbox"
                            class="history-select-version"
                            data-version="${snapshot.version}"
                            ${checked}
                        >
                    </td>
                    <td>v${snapshot.version}</td>
                    <td>
                        <span class="history-version-label">${this.escapeHtml(this.getDisplayLabel(snapshot))}</span>
                        ${localLabel}
                        ${archiveTag}
                    </td>
                    <td>${snapshot.record_count}</td>
                    <td>${summary.sizeText}</td>
                    <td>${this.formatDateTime(snapshot.created_at)}</td>
                    <td class="history-actions-cell">
                        <button type="button" class="btn btn-secondary integration-action-btn" data-action="view-detail" data-version="${snapshot.version}">详情</button>
                        <button type="button" class="btn btn-secondary integration-action-btn" data-action="edit-label" data-version="${snapshot.version}">编辑标签</button>
                        <button type="button" class="btn btn-secondary integration-action-btn" data-action="toggle-archive" data-version="${snapshot.version}">
                            ${localArchived ? '恢复' : '归档'}
                        </button>
                        <button type="button" class="btn btn-danger integration-action-btn" data-action="delete-snapshot" data-version="${snapshot.version}">删除</button>
                    </td>
                </tr>
            `;
        }).join('');

        this.listHost.innerHTML = `
            <div class="history-list-header">
                <h4>快照列表（共 ${this.filteredSnapshots.length} 个）</h4>
            </div>
            <div class="history-table-wrap">
                <table class="history-table">
                    <thead>
                        <tr>
                            <th>选中</th>
                            <th>版本</th>
                            <th>标签</th>
                            <th>记录数</th>
                            <th>大小</th>
                            <th>创建时间</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    }

    private renderDetail(): void {
        if (!this.detailHost) {
            return;
        }

        if (!this.currentDatasetId || this.snapshots.length === 0) {
            this.detailHost.innerHTML = '<div class="history-empty">' + I18n.t('historysnapshot.noSnapshotDetails') + '</div>';
            return;
        }

        const target = this.snapshots.find((snapshot) => snapshot.version === this.selectedVersion) || this.snapshots[0];
        this.selectedVersion = target.version;

        const summary = this.getSnapshotSummary(target);
        const localKey = this.toLocalSnapshotKey(target.dataset_id, target.version);
        const localArchived = Boolean(this.localState.archivedKeys[localKey]);

        this.detailHost.innerHTML = `
            <div class="history-detail-header">
                <h4>快照详情 - v${target.version}</h4>
                <span class="history-tag ${localArchived ? 'history-tag-archived' : 'history-tag-active'}">
                    ${localArchived ? '本地归档' : '活跃'}
                </span>
            </div>
            <dl class="history-detail-list">
                <div><dt>数据集 ID</dt><dd>${this.escapeHtml(target.dataset_id)}</dd></div>
                <div><dt>版本标签</dt><dd>${this.escapeHtml(this.getDisplayLabel(target))}</dd></div>
                <div><dt>创建时间</dt><dd>${this.formatDateTime(target.created_at)}</dd></div>
                <div><dt>记录数量</dt><dd>${target.record_count}</dd></div>
                <div><dt>存储文件</dt><dd>${this.escapeHtml(target.file_name)}</dd></div>
                <div><dt>压缩存储</dt><dd>${target.compressed ? '是' : '否'}</dd></div>
                <div><dt>快照大小</dt><dd>${summary.sizeText}</dd></div>
                <div><dt>数据范围</dt><dd>${summary.valueRangeText}</dd></div>
                <div><dt>时间跨度</dt><dd>${summary.timeSpanText}</dd></div>
                <div><dt>描述信息</dt><dd>${this.escapeHtml(summary.descriptionText)}</dd></div>
            </dl>
        `;
    }

    private parseRecordsInput(): HistoryTimeSeriesRecord[] {
        const raw = this.createRecordsInput?.value.trim() || '';
        if (!raw) {
            throw new Error('记录数据 JSON 不能为空。');
        }

        let parsed: unknown;
        try {
            parsed = JSON.parse(raw);
        } catch {
            throw new Error('记录数据 JSON 格式无效。');
        }

        if (!Array.isArray(parsed) || parsed.length === 0) {
            throw new Error('记录数据必须是非空数组。');
        }

        const records = parsed.map((item, index) => {
            const record = item as Record<string, unknown>;
            const timestampRaw = record.timestamp;
            const valueRaw = record.value;

            if (typeof timestampRaw !== 'string' || !timestampRaw.trim()) {
                throw new Error(`第 ${index + 1} 条记录缺少 timestamp 字段。`);
            }
            if (!this.isValidDate(timestampRaw)) {
                throw new Error(`第 ${index + 1} 条记录 timestamp 非法：${timestampRaw}`);
            }

            const value = Number(valueRaw);
            if (!Number.isFinite(value)) {
                throw new Error(`第 ${index + 1} 条记录 value 必须是数字。`);
            }

            return {
                timestamp: timestampRaw,
                value,
                point_id: typeof record.point_id === 'string' ? record.point_id : undefined,
                x: typeof record.x === 'number' && Number.isFinite(record.x) ? record.x : undefined,
                y: typeof record.y === 'number' && Number.isFinite(record.y) ? record.y : undefined,
                metadata: typeof record.metadata === 'object' && record.metadata !== null
                    ? (record.metadata as Record<string, unknown>)
                    : undefined
            } as HistoryTimeSeriesRecord;
        });

        return records;
    }

    private parseMetadataInput(): Record<string, unknown> {
        const raw = this.createMetadataInput?.value.trim() || '';
        if (!raw) {
            return {};
        }
        let parsed: unknown;
        try {
            parsed = JSON.parse(raw);
        } catch {
            throw new Error('附加元信息 JSON 格式无效。');
        }
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
            throw new Error('附加元信息必须是 JSON 对象。');
        }
        return parsed as Record<string, unknown>;
    }

    private buildSnapshotMetadata(records: HistoryTimeSeriesRecord[]): Record<string, unknown> {
        const values = records.map((item) => item.value).filter((item) => Number.isFinite(item));
        const timestamps = records
            .map((item) => new Date(item.timestamp))
            .filter((date) => !Number.isNaN(date.getTime()))
            .sort((a, b) => a.getTime() - b.getTime());

        const minValue = values.length > 0 ? Math.min(...values) : null;
        const maxValue = values.length > 0 ? Math.max(...values) : null;
        const start = timestamps[0] || null;
        const end = timestamps[timestamps.length - 1] || null;

        const estimatedSizeBytes = new Blob([JSON.stringify(records)]).size;
        const hours = (start && end)
            ? Math.max(0, (end.getTime() - start.getTime()) / (1000 * 60 * 60))
            : null;

        return {
            min_value: minValue,
            max_value: maxValue,
            start_time: start ? start.toISOString() : null,
            end_time: end ? end.toISOString() : null,
            time_span_hours: hours,
            estimated_size_bytes: estimatedSizeBytes
        };
    }

    private getSnapshotSummary(snapshot: HistorySnapshotMetadata): SnapshotSummary {
        const metadata = snapshot.metadata || {};
        const sizeValue = this.pickNumber(metadata, ['estimated_size_bytes', 'size_bytes', 'file_size', 'size']);
        const minValue = this.pickNumber(metadata, ['min_value', 'value_min', 'min']);
        const maxValue = this.pickNumber(metadata, ['max_value', 'value_max', 'max']);
        const startTime = this.pickString(metadata, ['start_time', 'start_timestamp', 'time_start']);
        const endTime = this.pickString(metadata, ['end_time', 'end_timestamp', 'time_end']);
        const timeSpanHours = this.pickNumber(metadata, ['time_span_hours']);
        const description = this.pickString(metadata, ['description', 'desc']) || '无';

        let valueRangeText = '未知';
        if (minValue !== null && maxValue !== null) {
            valueRangeText = `${minValue} ~ ${maxValue}`;
        }

        let timeSpanText = '未知';
        if (startTime && endTime) {
            timeSpanText = `${this.formatDateTime(startTime)} ~ ${this.formatDateTime(endTime)}`;
            if (timeSpanHours !== null) {
                timeSpanText += `（约 ${timeSpanHours.toFixed(2)} 小时）`;
            }
        }

        return {
            valueRangeText,
            timeSpanText,
            sizeText: sizeValue !== null ? this.formatSize(sizeValue) : '未知',
            descriptionText: description
        };
    }

    private getDisplayLabel(snapshot: HistorySnapshotMetadata): string {
        const key = this.toLocalSnapshotKey(snapshot.dataset_id, snapshot.version);
        return this.localState.labelOverrides[key] || snapshot.version_label || `v${snapshot.version}`;
    }

    private toLocalSnapshotKey(datasetId: string, version: number): string {
        return `${datasetId}::${version}`;
    }

    private pruneLocalStateForCurrentDataset(): void {
        if (!this.currentDatasetId) {
            return;
        }
        const alive = new Set(this.snapshots.map((item) => this.toLocalSnapshotKey(item.dataset_id, item.version)));
        let changed = false;

        Object.keys(this.localState.labelOverrides).forEach((key) => {
            if (key.startsWith(`${this.currentDatasetId}::`) && !alive.has(key)) {
                delete this.localState.labelOverrides[key];
                changed = true;
            }
        });

        Object.keys(this.localState.archivedKeys).forEach((key) => {
            if (key.startsWith(`${this.currentDatasetId}::`) && !alive.has(key)) {
                delete this.localState.archivedKeys[key];
                changed = true;
            }
        });

        if (changed) {
            this.saveLocalState();
        }
    }

    private loadLocalState(): SnapshotLocalState {
        const defaults: SnapshotLocalState = {
            labelOverrides: {},
            archivedKeys: {}
        };

        const raw = this.safeReadLocalStorage(LOCAL_STATE_KEY);
        if (!raw) {
            return defaults;
        }

        try {
            const parsed = JSON.parse(raw) as SnapshotLocalState;
            return {
                labelOverrides: parsed.labelOverrides || {},
                archivedKeys: parsed.archivedKeys || {}
            };
        } catch {
            return defaults;
        }
    }

    private saveLocalState(): void {
        this.safeWriteLocalStorage(LOCAL_STATE_KEY, JSON.stringify(this.localState));
    }

    private safeReadLocalStorage(key: string): string | null {
        try {
            return localStorage.getItem(key);
        } catch {
            return null;
        }
    }

    private safeWriteLocalStorage(key: string, value: string): void {
        try {
            localStorage.setItem(key, value);
        } catch {
            // ignore storage errors
        }
    }

    private pickNumber(source: Record<string, unknown>, keys: string[]): number | null {
        for (const key of keys) {
            const value = source[key];
            if (typeof value === 'number' && Number.isFinite(value)) {
                return value;
            }
            if (typeof value === 'string' && value.trim()) {
                const parsed = Number(value);
                if (Number.isFinite(parsed)) {
                    return parsed;
                }
            }
        }
        return null;
    }

    private pickString(source: Record<string, unknown>, keys: string[]): string | null {
        for (const key of keys) {
            const value = source[key];
            if (typeof value === 'string' && value.trim()) {
                return value.trim();
            }
        }
        return null;
    }

    private syncAutoRefreshSelect(): void {
        const interval = Number(this.safeReadLocalStorage(SNAPSHOT_AUTO_REFRESH_KEY) || '0');
        if (this.autoRefreshSelect) {
            this.autoRefreshSelect.value = Number.isFinite(interval) ? String(Math.max(0, interval)) : '0';
        }
    }

    private updateAutoRefreshFromSelect(): void {
        const intervalSec = Number(this.autoRefreshSelect?.value || '0');
        this.safeWriteLocalStorage(SNAPSHOT_AUTO_REFRESH_KEY, String(intervalSec));
        this.stopAutoRefresh();
        if (!Number.isFinite(intervalSec) || intervalSec <= 0) {
            if (this.refreshProgressElement) {
                this.refreshProgressElement.textContent = I18n.t('historysnapshot.autoRefreshOff');
            }
            return;
        }
        this.refreshRemainSec = Math.floor(intervalSec);
        this.autoRefreshTimer = window.setInterval(() => {
            if (!this.loading && this.currentDatasetId) {
                void this.handleRefreshList();
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
                this.refreshProgressElement.textContent = I18n.t('historysnapshot.autoRefreshCountdown', { seconds: this.refreshRemainSec });
            }
            if (this.refreshRemainSec <= 0) {
                this.refreshRemainSec = Math.floor(intervalSec);
            }
        }, 1000);
    }

    private showSkeleton(): void {
        if (!this.listHost || !this.detailHost) {
            return;
        }
        SkeletonLoader.hideByContainer(this.listHost);
        SkeletonLoader.hideByContainer(this.detailHost);
        this.listSkeleton = SkeletonLoader.show(this.listHost, 'list', { lines: 6, showAvatar: false });
        this.detailSkeleton = SkeletonLoader.show(this.detailHost, 'card', {});
    }

    private hideSkeleton(): void {
        SkeletonLoader.hide(this.listSkeleton);
        SkeletonLoader.hide(this.detailSkeleton);
        this.listSkeleton = null;
        this.detailSkeleton = null;
    }

    private async runWithRetry(executor: () => Promise<void>, options: RetryOptions): Promise<void> {
        const retries = options.retries ?? 0;
        for (let attempt = 0; attempt <= retries; attempt += 1) {
            try {
                await executor();
                return;
            } catch (error) {
                const errorMsg = this.getErrorMessage(error);
                if (attempt >= retries || !this.isRetryableError(errorMsg)) {
                    const classified = this.classifyError(errorMsg);
                    this.setStatus(`${options.actionName}失败（${classified}）：${errorMsg}`, 'error');
                    throw error;
                }
                this.setStatus(`${options.actionName}失败，正在第 ${attempt + 1} 次重试...`, 'warning');
                await this.delay(350 * (attempt + 1));
            }
        }
    }

    private isRetryableError(message: string): boolean {
        return /(timeout|timed out|network|fetch|502|503|504|连接|超时|网络)/i.test(message);
    }

    private classifyError(message: string): string {
        if (/(timeout|timed out|超时)/i.test(message)) {
            return '请求超时';
        }
        if (/(network|fetch|连接|断开|offline)/i.test(message)) {
            return '网络异常';
        }
        if (/(401|403)/.test(message)) {
            return '权限不足';
        }
        if (/(404)/.test(message)) {
            return '资源不存在';
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
        const withRetryHint = type === 'error' && this.lastRetryAction
            ? `${message}；可点击“${this.retryButtonText}”。`
            : message;
        this.statusElement.textContent = withRetryHint;
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

    private getErrorMessage(error: unknown): string {
        if (error instanceof Error && error.message) {
            return error.message;
        }
        return String(error || '未知错误');
    }

    private isValidDate(text: string): boolean {
        return !Number.isNaN(new Date(text).getTime());
    }

    private formatDateTime(raw: string): string {
        const date = new Date(raw);
        if (Number.isNaN(date.getTime())) {
            return raw;
        }
        return date.toLocaleString('zh-CN', { hour12: false });
    }

    private formatSize(value: number): string {
        if (!Number.isFinite(value) || value < 0) {
            return '未知';
        }
        const units = ['B', 'KB', 'MB', 'GB'];
        let size = value;
        let index = 0;
        while (size >= 1024 && index < units.length - 1) {
            size /= 1024;
            index += 1;
        }
        return `${size.toFixed(index === 0 ? 0 : 2)} ${units[index]}`;
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
