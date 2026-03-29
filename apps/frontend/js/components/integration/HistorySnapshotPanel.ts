import type {
    HistorySnapshotCreatePayload,
    HistorySnapshotMetadata,
    HistoryTimeSeriesRecord
} from '../../services/API封装.js';
import { APIService } from '../../services/API封装.js';
import { ConfirmDialog } from '../ConfirmDialog.js';
import notificationManager from '../NotificationManager.js';

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
                <p class="history-archive-hint">说明：本地归档仅影响当前界面显示；后端归档会将旧版本移出服务端活动列表。</p>
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
                this.handleLocalArchiveSelected();
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
            return;
        }

        this.renderList();
        this.renderDetail();
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

    private async loadSnapshots(datasetId: string): Promise<void> {
        this.setStatus('正在加载快照列表...', 'warning');
        this.setLoading(true);
        try {
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
        } catch (error) {
            this.setStatus(`快照列表加载失败：${this.getErrorMessage(error)}`, 'error');
        } finally {
            this.setLoading(false);
        }
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
        try {
            await this.apiService.createHistorySnapshot(payload);
            this.notifySuccess('快照创建成功', `数据集 ${datasetId} 已创建新快照。`);
            if (this.datasetInput) {
                this.datasetInput.value = datasetId;
            }
            await this.loadSnapshots(datasetId);
        } catch (error) {
            this.setStatus(`创建失败：${this.getErrorMessage(error)}`, 'error');
        } finally {
            this.setLoading(false);
        }
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

        this.setStatus('正在执行后端归档...', 'warning');
        this.setLoading(true);
        try {
            const response = await this.apiService.archiveHistorySnapshots({
                dataset_id: this.currentDatasetId,
                keep_latest: Math.floor(keepLatest)
            }) as { archived_count?: number; kept_count?: number };

            const archivedCount = Number(response?.archived_count || 0);
            const keptCount = Number(response?.kept_count || 0);
            this.notifySuccess('后端归档完成', `已归档 ${archivedCount} 个版本，保留 ${keptCount} 个版本。`);
            await this.loadSnapshots(this.currentDatasetId);
        } catch (error) {
            this.setStatus(`后端归档失败：${this.getErrorMessage(error)}`, 'error');
        } finally {
            this.setLoading(false);
        }
    }

    private handleLocalArchiveSelected(): void {
        if (!this.currentDatasetId) {
            this.setStatus('请先加载快照列表。', 'error');
            return;
        }
        if (this.selectedVersions.size === 0) {
            this.setStatus('请先选择要归档的版本。', 'error');
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
        const nextLabel = window.prompt(`编辑版本 v${version} 标签`, currentLabel);
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
        try {
            await this.apiService.deleteHistorySnapshot(this.currentDatasetId, version);
            const key = this.toLocalSnapshotKey(this.currentDatasetId, version);
            delete this.localState.archivedKeys[key];
            delete this.localState.labelOverrides[key];
            this.saveLocalState();
            this.notifySuccess('删除成功', `版本 v${version} 已删除。`);
            await this.loadSnapshots(this.currentDatasetId);
        } catch (error) {
            this.setStatus(`删除失败：${this.getErrorMessage(error)}`, 'error');
        } finally {
            this.setLoading(false);
        }
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
            this.listHost.innerHTML = '<div class="history-empty">请输入并加载数据集后查看快照列表。</div>';
            return;
        }

        if (this.filteredSnapshots.length === 0) {
            this.listHost.innerHTML = '<div class="history-empty">当前筛选条件下没有快照。</div>';
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
            this.detailHost.innerHTML = '<div class="history-empty">暂无快照详情。</div>';
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

    private setLoading(loading: boolean): void {
        if (!this.root) {
            return;
        }
        this.root.querySelectorAll('button[data-action]').forEach((button) => {
            (button as HTMLButtonElement).disabled = loading;
        });
    }

    private setStatus(message: string, type: 'success' | 'error' | 'warning' = 'success'): void {
        if (!this.statusElement) {
            return;
        }
        this.statusElement.className = `status-message ${type}`;
        this.statusElement.textContent = message;
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
