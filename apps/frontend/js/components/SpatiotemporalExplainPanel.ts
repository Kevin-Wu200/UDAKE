import type { IAPIService } from '../../types/api';
import { I18n } from '../utils/I18n';

type ExplainMethod = 'lime' | 'shap' | 'hybrid';
type ExplainStatus = 'queued' | 'running' | 'retrying' | 'completed' | 'failed' | 'cancelled';

type ExplainTask = {
    task_id: string;
    status: ExplainStatus;
    state?: string;
    created_at?: string;
    updated_at?: string;
    progress?: number;
    error?: string;
    retry_count?: number;
    max_retries?: number;
    result?: Record<string, unknown> | null;
};

type MonitorPayload = {
    queue_size?: number;
    active_tasks?: number;
    max_concurrent_tasks?: number;
    success_rate?: number;
    error_rate?: number;
    avg_duration_ms?: number;
    retry_count?: number;
    celery_enabled?: boolean;
    cache_backend?: string;
};

/**
 * 时空预测可解释性面板
 * 支持 LIME / SHAP / Hybrid 任务提交、状态管理和可视化展示。
 */
export class SpatiotemporalExplainPanel {
    private container: HTMLElement;
    private apiService: IAPIService;

    private tasks: ExplainTask[] = [];
    private currentTaskId: string | null = null;
    private activeTab: 'lime' | 'shap' | 'compare' | 'spatiotemporal' = 'lime';
    private selectedMethod: ExplainMethod = 'hybrid';
    private autoRefreshTimer: number | null = null;
    private autoRefreshEnabled: boolean = true;
    private filterMethod: 'all' | 'lime' | 'shap' | 'hybrid' = 'all';
    private renderedTaskCount: number = 40;
    private readonly taskBatchSize: number = 40;
    private taskListScrollHandler: (() => void) | null = null;

    constructor(container: HTMLElement, apiService: IAPIService) {
        this.container = container;
        this.apiService = apiService;

        this.render();
        this.bindEvents();
        this.startAutoRefresh();
        void this.refreshMonitor();
    }

    private render(): void {
        this.container.innerHTML = `
            <div class="dl-module-card explain-panel">
                <div class="dl-module-header">
                    <h4>${this.t('explain.panel.title', '模型可解释性增强面板')}</h4>
                    <p>${this.t('explain.panel.subtitle', '提交时空解释任务，查看 LIME / SHAP 可视化与对比分析')}</p>
                </div>

                <div class="explain-method-switch" role="tablist" aria-label="${this.t('explain.method.switchAria', '解释方法切换')}">
                    <button class="btn btn-secondary active" data-method-switch="lime">${this.t('explain.method.lime', 'LIME')}</button>
                    <button class="btn btn-secondary" data-method-switch="shap">${this.t('explain.method.shap', 'SHAP')}</button>
                    <button class="btn btn-secondary" data-method-switch="hybrid">${this.t('explain.method.hybrid', 'Hybrid')}</button>
                </div>

                <div class="explain-layout-grid">
                    <section class="explain-submit-panel">
                        <h5>${this.t('explain.submit.title', '任务提交')}</h5>
                        <div class="dl-form-grid">
                            <label class="dl-field">
                                <span>模型选择</span>
                                <select id="dl-explain-model" class="select">
                                    <option value="st_transformer">ST-Transformer</option>
                                    <option value="gcn_lstm">GCN-LSTM</option>
                                    <option value="convlstm">ConvLSTM</option>
                                    <option value="stgcn">STGCN</option>
                                </select>
                            </label>
                            <label class="dl-field">
                                <span>预测步长</span>
                                <input id="dl-explain-horizon" class="input" type="number" min="1" max="48" value="6">
                            </label>
                            <label class="dl-field">
                                <span>Top-K 特征</span>
                                <input id="dl-explain-topk" class="input" type="number" min="1" max="20" value="5">
                            </label>
                            <label class="dl-field">
                                <span>重试次数</span>
                                <input id="dl-explain-retries" class="input" type="number" min="0" max="3" value="1">
                            </label>
                            <label class="dl-field">
                                <span>批大小</span>
                                <input id="dl-explain-batch" class="input" type="number" min="16" max="4096" value="256">
                            </label>
                            <label class="dl-field">
                                <span>优先级 (0-9)</span>
                                <input id="dl-explain-priority" class="input" type="number" min="0" max="9" value="5">
                            </label>
                        </div>

                        <label class="dl-field dl-field-full">
                            <span>坐标输入 coords（JSON）</span>
                            <textarea id="dl-explain-coords" class="dl-textarea" rows="3">[[120.1,30.2],[120.2,30.3],[120.3,30.4],[120.4,30.5]]</textarea>
                        </label>

                        <label class="dl-field dl-field-full">
                            <span>时间序列输入 series（JSON）</span>
                            <textarea id="dl-explain-series" class="dl-textarea" rows="5">[[[1.0],[1.1],[1.2],[1.3],[1.4],[1.5]],[[0.9],[1.0],[1.1],[1.2],[1.3],[1.4]],[[1.2],[1.3],[1.4],[1.5],[1.6],[1.7]],[[0.8],[0.9],[1.0],[1.1],[1.2],[1.3]]]</textarea>
                        </label>

                        <div class="dl-actions">
                            <button id="dl-explain-submit" class="btn btn-primary">${this.t('explain.action.submit', '提交解释任务')}</button>
                            <button id="dl-explain-monitor" class="btn btn-secondary">${this.t('explain.action.refresh', '刷新队列状态')}</button>
                            <button id="dl-explain-verify" class="btn btn-secondary">${this.t('explain.action.verify', '校验异步后端')}</button>
                        </div>
                        <div id="dl-explain-status" class="status-message" role="status" aria-live="polite"></div>
                        <div id="dl-explain-guide" class="explain-guide">快捷键：<code>Ctrl/Cmd + Enter</code> 提交任务，<code>Ctrl/Cmd + R</code> 刷新任务。</div>
                    </section>

                    <section class="explain-task-panel">
                        <div class="explain-task-header">
                            <h5>${this.t('explain.task.title', '任务状态')}</h5>
                            <div class="explain-task-tools">
                                <select id="dl-explain-filter" class="select">
                                    <option value="all">全部方法</option>
                                    <option value="lime">LIME</option>
                                    <option value="shap">SHAP</option>
                                    <option value="hybrid">Hybrid</option>
                                </select>
                                <label class="checkbox-label">
                                    <input id="dl-explain-auto-refresh" type="checkbox" checked>
                                    自动刷新
                                </label>
                            </div>
                        </div>
                        <div id="dl-explain-monitor-info" class="explain-monitor-info"></div>
                        <div id="dl-explain-task-list" class="explain-task-list"></div>
                    </section>
                </div>

                <section class="explain-result-panel">
                    <div class="explain-result-header">
                        <h5>${this.t('explain.result.title', '解释结果展示')}</h5>
                        <div class="explain-result-tabs">
                            <button class="btn btn-secondary active" data-result-tab="lime">${this.t('explain.result.tab.lime', 'LIME视图')}</button>
                            <button class="btn btn-secondary" data-result-tab="shap">${this.t('explain.result.tab.shap', 'SHAP视图')}</button>
                            <button class="btn btn-secondary" data-result-tab="compare">${this.t('explain.result.tab.compare', '对比分析')}</button>
                            <button class="btn btn-secondary" data-result-tab="spatiotemporal">${this.t('explain.result.tab.spatiotemporal', '时空视图')}</button>
                        </div>
                    </div>

                    <div id="dl-explain-result" class="explain-result-content">
                        <div class="status-message">${this.t('explain.status.emptyResult', '暂无结果，请先提交并完成任务。')}</div>
                    </div>
                </section>
            </div>
        `;
    }

    private bindEvents(): void {
        this.container.querySelectorAll<HTMLButtonElement>('[data-method-switch]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const method = (btn.dataset.methodSwitch || 'hybrid') as ExplainMethod;
                this.selectedMethod = method;
                this.updateMethodSwitch();
                this.setStatus(`已切换提交方法：${method.toUpperCase()}`, 'success');
            });
        });

        this.container.querySelector('#dl-explain-submit')?.addEventListener('click', () => {
            void this.submitTask();
        });
        this.container.querySelector('#dl-explain-monitor')?.addEventListener('click', () => {
            void this.refreshAllTasks();
        });
        this.container.querySelector('#dl-explain-verify')?.addEventListener('click', () => {
            void this.verifyBackend();
        });

        this.container.querySelector('#dl-explain-filter')?.addEventListener('change', (event) => {
            const value = (event.target as HTMLSelectElement).value as 'all' | 'lime' | 'shap' | 'hybrid';
            this.filterMethod = value;
            this.renderedTaskCount = this.taskBatchSize;
            this.renderTaskList();
        });

        this.container.querySelector('#dl-explain-auto-refresh')?.addEventListener('change', (event) => {
            this.autoRefreshEnabled = (event.target as HTMLInputElement).checked;
            if (this.autoRefreshEnabled) {
                this.startAutoRefresh();
            } else {
                this.stopAutoRefresh();
            }
        });

        this.container.querySelectorAll<HTMLButtonElement>('[data-result-tab]').forEach((btn) => {
            btn.addEventListener('click', () => {
                this.activeTab = (btn.dataset.resultTab || 'lime') as typeof this.activeTab;
                this.updateResultTabs();
                this.renderCurrentResult();
            });
        });

        this.container.addEventListener('click', (event) => {
            const target = event.target as HTMLElement;
            const actionButton = target.closest<HTMLButtonElement>('[data-task-action]');
            if (!actionButton) {
                return;
            }

            const taskId = actionButton.dataset.taskId || '';
            const action = actionButton.dataset.taskAction || '';
            if (!taskId || !action) {
                return;
            }

            if (action === 'view') {
                void this.viewTask(taskId);
                return;
            }
            if (action === 'cancel') {
                void this.cancelTask(taskId);
                return;
            }
            if (action === 'delete') {
                void this.deleteTask(taskId);
                return;
            }

            if (action === 'load-more') {
                this.renderedTaskCount += this.taskBatchSize;
                this.renderTaskList();
            }
        });

        this.container.addEventListener('keydown', (event: KeyboardEvent) => {
            if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                event.preventDefault();
                void this.submitTask();
            }

            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'r') {
                event.preventDefault();
                void this.refreshAllTasks();
            }
        });

        this.attachTaskListVirtualScroll();
    }

    private updateMethodSwitch(): void {
        this.container.querySelectorAll<HTMLButtonElement>('[data-method-switch]').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.methodSwitch === this.selectedMethod);
        });
    }

    private updateResultTabs(): void {
        this.container.querySelectorAll<HTMLButtonElement>('[data-result-tab]').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.resultTab === this.activeTab);
        });
    }

    private parseJSONInput<T>(id: string, field: string): T {
        const input = this.container.querySelector(`#${id}`) as HTMLTextAreaElement | null;
        if (!input) {
            throw new Error(`缺少输入项：${field}`);
        }

        try {
            return JSON.parse(input.value) as T;
        } catch {
            throw new Error(`${field} 不是合法 JSON`);
        }
    }

    private validateForm(
        coords: Array<[number, number]>,
        series: number[][][],
        predHorizon: number,
        topK: number,
        maxRetries: number,
        batchSize: number,
        priority: number
    ): void {
        if (!Array.isArray(coords) || coords.length < 2) {
            throw new Error('coords 至少需要 2 个坐标点');
        }
        if (!Array.isArray(series) || series.length !== coords.length) {
            throw new Error('series 与 coords 节点数量必须一致');
        }

        for (let i = 0; i < coords.length; i += 1) {
            const [x, y] = coords[i] || [NaN, NaN];
            if (!Number.isFinite(x) || !Number.isFinite(y)) {
                throw new Error(`coords[${i}] 含非法坐标`);
            }
        }

        for (let i = 0; i < series.length; i += 1) {
            const nodeSeries = series[i];
            if (!Array.isArray(nodeSeries) || nodeSeries.length < 4) {
                throw new Error(`series[${i}] 时间长度不足，至少为 4`);
            }
        }

        if (predHorizon < 1 || predHorizon > 48) {
            throw new Error('pred_horizon 范围应在 1~48');
        }
        if (topK < 1 || topK > 20) {
            throw new Error('top_k 范围应在 1~20');
        }
        if (maxRetries < 0 || maxRetries > 3) {
            throw new Error('max_retries 范围应在 0~3');
        }
        if (batchSize < 16 || batchSize > 4096) {
            throw new Error('batch_size 范围应在 16~4096');
        }
        if (priority < 0 || priority > 9) {
            throw new Error('priority 范围应在 0~9');
        }
    }

    private async submitTask(): Promise<void> {
        try {
            this.setStatus('正在提交解释任务...', 'loading');

            const modelType = (this.container.querySelector('#dl-explain-model') as HTMLSelectElement | null)?.value || 'st_transformer';
            const predHorizon = Number((this.container.querySelector('#dl-explain-horizon') as HTMLInputElement | null)?.value || 6);
            const topK = Number((this.container.querySelector('#dl-explain-topk') as HTMLInputElement | null)?.value || 5);
            const maxRetries = Number((this.container.querySelector('#dl-explain-retries') as HTMLInputElement | null)?.value || 1);
            const batchSize = Number((this.container.querySelector('#dl-explain-batch') as HTMLInputElement | null)?.value || 256);
            const priority = Number((this.container.querySelector('#dl-explain-priority') as HTMLInputElement | null)?.value || 5);

            const coords = this.parseJSONInput<Array<[number, number]>>('dl-explain-coords', 'coords');
            const series = this.parseJSONInput<number[][][]>('dl-explain-series', 'series');

            this.validateForm(coords, series, predHorizon, topK, maxRetries, batchSize, priority);

            const created = await this.apiService.createSpatiotemporalExplainTask({
                model_type: modelType,
                coords,
                series,
                pred_horizon: predHorizon,
                method: this.selectedMethod,
                top_k: topK,
                batch_size: batchSize,
                include_prediction: true,
                priority,
                max_retries: maxRetries
            });

            this.currentTaskId = String(created.task_id);
            this.setStatus(`任务提交成功：${created.task_id}`, 'success');
            await this.refreshTaskById(String(created.task_id));
            await this.refreshMonitor();
        } catch (error) {
            this.setStatus(`提交失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private async refreshTaskById(taskId: string): Promise<void> {
        try {
            const detail = await this.apiService.getSpatiotemporalExplainTask(taskId);
            const normalized = this.normalizeTask(detail as Record<string, unknown>);
            const idx = this.tasks.findIndex(item => item.task_id === taskId);
            if (idx >= 0) {
                this.tasks[idx] = normalized;
            } else {
                this.tasks.unshift(normalized);
            }
            this.sortTasks();
            this.renderTaskList();

            if (this.currentTaskId === taskId) {
                this.renderCurrentResult();
            }
        } catch (error) {
            this.setStatus(`刷新任务失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private normalizeTask(raw: Record<string, unknown>): ExplainTask {
        return {
            task_id: String(raw.task_id || ''),
            status: String(raw.status || 'queued') as ExplainStatus,
            state: typeof raw.state === 'string' ? raw.state : undefined,
            created_at: typeof raw.created_at === 'string' ? raw.created_at : undefined,
            updated_at: typeof raw.updated_at === 'string' ? raw.updated_at : undefined,
            progress: Number(raw.progress || 0),
            error: typeof raw.error === 'string' ? raw.error : undefined,
            retry_count: Number(raw.retry_count || 0),
            max_retries: Number(raw.max_retries || 0),
            result: (raw.result as Record<string, unknown> | undefined) || null
        };
    }

    private sortTasks(): void {
        this.tasks.sort((a, b) => {
            const timeA = new Date(a.updated_at || a.created_at || 0).getTime();
            const timeB = new Date(b.updated_at || b.created_at || 0).getTime();
            return timeB - timeA;
        });
    }

    private statusIcon(status: ExplainStatus): string {
        switch (status) {
            case 'completed':
                return '✓';
            case 'failed':
                return '!';
            case 'cancelled':
                return 'x';
            case 'running':
                return '>'; 
            case 'retrying':
                return '~';
            default:
                return '·';
        }
    }

    private statusLabel(status: ExplainStatus): string {
        switch (status) {
            case 'queued':
                return this.t('explain.status.queued', '排队中');
            case 'running':
                return this.t('explain.status.running', '执行中');
            case 'retrying':
                return this.t('explain.status.retrying', '重试中');
            case 'completed':
                return this.t('explain.status.completed', '已完成');
            case 'failed':
                return this.t('explain.status.failed', '失败');
            case 'cancelled':
                return this.t('explain.status.cancelled', '已取消');
            default:
                return status;
        }
    }

    private progressPercent(task: ExplainTask): number {
        const p = Number(task.progress ?? 0);
        if (p <= 1) {
            return Math.max(0, Math.min(100, Math.round(p * 100)));
        }
        return Math.max(0, Math.min(100, Math.round(p)));
    }

    private detectMethodFromTask(task: ExplainTask): ExplainMethod {
        const result = (task.result || {}) as Record<string, unknown>;
        const methodRaw = result.method;
        if (methodRaw === 'lime' || methodRaw === 'shap' || methodRaw === 'hybrid') {
            return methodRaw;
        }

        const hasLime = typeof result.lime === 'object' && result.lime !== null;
        const hasShap = typeof result.shap === 'object' && result.shap !== null;
        if (hasLime && hasShap) {
            return 'hybrid';
        }
        if (hasShap) {
            return 'shap';
        }
        return 'lime';
    }

    private renderTaskList(): void {
        const list = this.container.querySelector('#dl-explain-task-list') as HTMLElement | null;
        if (!list) {
            return;
        }

        const filtered = this.filterMethod === 'all'
            ? this.tasks
            : this.tasks.filter(task => this.detectMethodFromTask(task) === this.filterMethod);

        if (filtered.length === 0) {
            list.innerHTML = `<div class="status-message">${this.t('explain.status.noTask', '暂无任务')}</div>`;
            return;
        }

        const visibleTasks = filtered.slice(0, this.renderedTaskCount);
        list.innerHTML = visibleTasks.map((task) => {
            const progress = this.progressPercent(task);
            const method = this.detectMethodFromTask(task).toUpperCase();
            return `
                <article class="explain-task-item ${task.status} ${task.task_id === this.currentTaskId ? 'active' : ''}">
                    <div class="explain-task-top">
                        <span class="task-icon">${this.statusIcon(task.status)}</span>
                        <span class="task-id" title="${task.task_id}">${task.task_id.slice(0, 12)}...</span>
                        <span class="task-method">${method}</span>
                        <span class="task-status">${this.statusLabel(task.status)}</span>
                    </div>
                    <div class="explain-task-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}">
                        <div class="explain-task-progress-fill" style="width:${progress}%"></div>
                    </div>
                    <div class="explain-task-meta">
                        <span>${this.t('explain.task.progress', '进度')} ${this.formatNumber(progress)}%</span>
                        <span>${this.t('explain.task.retry', '重试')} ${this.formatNumber(task.retry_count || 0)}/${this.formatNumber(task.max_retries || 0)}</span>
                        <span>${this.formatTime(task.updated_at || task.created_at || '')}</span>
                    </div>
                    ${task.error ? `<div class="status-message error">${task.error}</div>` : ''}
                    <div class="explain-task-actions">
                        <button class="btn btn-secondary" data-task-action="view" data-task-id="${task.task_id}">${this.t('common.view', '查看')}</button>
                        <button class="btn btn-secondary" data-task-action="cancel" data-task-id="${task.task_id}" ${['completed', 'failed', 'cancelled'].includes(task.status) ? 'disabled' : ''}>${this.t('common.cancel', '取消')}</button>
                        <button class="btn btn-secondary" data-task-action="delete" data-task-id="${task.task_id}">${this.t('common.delete', '删除')}</button>
                    </div>
                </article>
            `;
        }).join('');

        if (filtered.length > visibleTasks.length) {
            list.insertAdjacentHTML('beforeend', `
                <div class="status-message">
                    ${this.t('explain.task.partial', '已渲染 {visible}/{total} 条任务', {
                        visible: this.formatNumber(visibleTasks.length),
                        total: this.formatNumber(filtered.length)
                    })}
                    <button class="btn btn-secondary" data-task-action="load-more" data-task-id="load-more">
                        ${this.t('explain.task.loadMore', '加载更多')}
                    </button>
                </div>
            `);
        }
    }

    private async refreshAllTasks(): Promise<void> {
        const taskIds = this.tasks.map(item => item.task_id);
        if (this.currentTaskId && !taskIds.includes(this.currentTaskId)) {
            taskIds.unshift(this.currentTaskId);
        }

        if (taskIds.length === 0) {
            this.setStatus('暂无可刷新任务', 'warning');
            await this.refreshMonitor();
            return;
        }

        await Promise.all(taskIds.slice(0, 20).map(async (id) => {
            await this.refreshTaskById(id);
        }));

        await this.refreshMonitor();
        this.setStatus('任务列表已刷新', 'success');
    }

    private async refreshMonitor(): Promise<void> {
        try {
            const payload = await this.apiService.getSpatiotemporalExplainMonitor();
            this.renderMonitor(payload as MonitorPayload);
        } catch (error) {
            this.setStatus(`监控查询失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private renderMonitor(payload: MonitorPayload): void {
        const monitorEl = this.container.querySelector('#dl-explain-monitor-info') as HTMLElement | null;
        if (!monitorEl) {
            return;
        }

        const successRate = Math.round(Number(payload.success_rate || 0) * 100);
        const errorRate = Math.round(Number(payload.error_rate || 0) * 100);
        const queueSize = Number(payload.queue_size || 0);
        const activeTasks = Number(payload.active_tasks || 0);
        const avgDuration = Number(payload.avg_duration_ms || 0).toFixed(1);

        monitorEl.innerHTML = `
            <div class="monitor-chip">${this.t('explain.monitor.queue', '队列')}: ${this.formatNumber(queueSize)}</div>
            <div class="monitor-chip">${this.t('explain.monitor.active', '执行中')}: ${this.formatNumber(activeTasks)}</div>
            <div class="monitor-chip">${this.t('explain.monitor.successRate', '成功率')}: ${this.formatNumber(successRate)}%</div>
            <div class="monitor-chip">${this.t('explain.monitor.errorRate', '错误率')}: ${this.formatNumber(errorRate)}%</div>
            <div class="monitor-chip">${this.t('explain.monitor.avgDuration', '平均耗时')}: ${this.formatNumber(Number(avgDuration))}ms</div>
            <div class="monitor-chip">${this.t('explain.monitor.cache', '缓存')}: ${payload.cache_backend || 'unknown'}</div>
            <div class="monitor-chip">Celery: ${payload.celery_enabled ? 'on' : 'off'}</div>
        `;
    }

    private async verifyBackend(): Promise<void> {
        try {
            const payload = await this.apiService.verifySpatiotemporalExplainBackend();
            const brokerOk = Boolean((payload as Record<string, unknown>).broker_ok);
            const backendOk = Boolean((payload as Record<string, unknown>).redis_backend_ok);
            if (brokerOk || backendOk) {
                this.setStatus('异步后端校验通过', 'success');
            } else {
                const reason = String((payload as Record<string, unknown>).reason || 'unknown');
                this.setStatus(`异步后端不可用：${reason}`, 'warning');
            }
        } catch (error) {
            this.setStatus(`校验失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private async viewTask(taskId: string): Promise<void> {
        this.currentTaskId = taskId;
        await this.refreshTaskById(taskId);
        this.renderTaskList();
        this.renderCurrentResult();
    }

    private async cancelTask(taskId: string): Promise<void> {
        try {
            await this.apiService.cancelSpatiotemporalExplainTask(taskId);
            this.setStatus(`任务已取消：${taskId}`, 'success');
            await this.refreshTaskById(taskId);
            await this.refreshMonitor();
        } catch (error) {
            this.setStatus(`取消失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private async deleteTask(taskId: string): Promise<void> {
        try {
            await this.apiService.deleteSpatiotemporalExplainTask(taskId);
            this.tasks = this.tasks.filter(task => task.task_id !== taskId);
            if (this.currentTaskId === taskId) {
                this.currentTaskId = this.tasks[0]?.task_id || null;
            }
            this.renderTaskList();
            this.renderCurrentResult();
            await this.refreshMonitor();
            this.setStatus(`任务已删除：${taskId}`, 'success');
        } catch (error) {
            this.setStatus(`删除失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private getCurrentTask(): ExplainTask | null {
        if (!this.currentTaskId) {
            return null;
        }
        return this.tasks.find(task => task.task_id === this.currentTaskId) || null;
    }

    private renderCurrentResult(): void {
        const container = this.container.querySelector('#dl-explain-result') as HTMLElement | null;
        if (!container) {
            return;
        }

        const task = this.getCurrentTask();
        if (!task) {
            container.innerHTML = `<div class="status-message">${this.t('explain.status.selectTask', '请选择任务查看结果。')}</div>`;
            return;
        }
        if (task.status !== 'completed' || !task.result) {
            container.innerHTML = `<div class="status-message">${this.t('explain.status.taskUnavailable', '任务当前状态：{status}，结果尚不可用。', {
                status: this.statusLabel(task.status)
            })}</div>`;
            return;
        }

        const result = task.result as Record<string, unknown>;
        if (this.activeTab === 'lime') {
            container.innerHTML = this.renderLimeResult(result);
            return;
        }
        if (this.activeTab === 'shap') {
            container.innerHTML = this.renderShapResult(result);
            this.bindShapInteractive(container, result);
            return;
        }
        if (this.activeTab === 'compare') {
            container.innerHTML = this.renderCompareResult(result);
            return;
        }

        container.innerHTML = this.renderSpatiotemporalResult(result);
    }

    private renderFeatureBarList(rows: Array<{ name: string; value: number }>, className: string): string {
        if (!rows.length) {
            return '<div class="status-message">暂无特征数据</div>';
        }

        const maxVal = Math.max(...rows.map(item => Math.abs(item.value)), 1);
        return `
            <div class="feature-bar-list ${className}">
                ${rows.map((row) => {
                    const pct = Math.max(2, Math.round((Math.abs(row.value) / maxVal) * 100));
                    const signClass = row.value >= 0 ? 'positive' : 'negative';
                    return `
                        <div class="feature-bar-item ${signClass}">
                            <span class="feature-name">${row.name}</span>
                            <div class="feature-bar-track">
                                <div class="feature-bar-fill" style="width:${pct}%"></div>
                            </div>
                            <span class="feature-value">${row.value.toFixed(4)}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    private parseImportanceRows(raw: unknown): Array<{ name: string; value: number }> {
        if (!Array.isArray(raw)) {
            return [];
        }
        return raw
            .map((item, idx) => {
                if (typeof item === 'object' && item !== null) {
                    const rec = item as Record<string, unknown>;
                    const name = String(rec.feature || rec.feature_name || rec.name || `feature_${idx}`);
                    const value = Number(rec.value ?? rec.importance ?? rec.mean_abs_shap ?? 0);
                    return { name, value };
                }
                if (Array.isArray(item)) {
                    const name = String(item[0] ?? `feature_${idx}`);
                    const value = Number(item[1] ?? 0);
                    return { name, value };
                }
                return { name: `feature_${idx}`, value: Number(item || 0) };
            })
            .filter(item => Number.isFinite(item.value));
    }

    private renderLimeResult(result: Record<string, unknown>): string {
        const lime = (result.lime || {}) as Record<string, unknown>;
        const visualization = (lime.visualization || {}) as Record<string, unknown>;
        const summary = (result.summary || {}) as Record<string, unknown>;

        const featureImportance = this.parseImportanceRows(
            visualization.feature_importance_list || lime.global_feature_importance || []
        );

        const localExplanations = Array.isArray(visualization.local_explanations)
            ? visualization.local_explanations as Array<Record<string, unknown>>
            : [];

        const contributionRows = this.parseContributionRows(lime);

        return `
            <div class="explain-result-grid">
                <section class="result-card">
                    <h6>特征重要性条形图</h6>
                    ${this.renderFeatureBarList(featureImportance.slice(0, 12), 'lime-bars')}
                </section>

                <section class="result-card">
                    <h6>局部预测解释图</h6>
                    ${this.renderLocalExplanationList(localExplanations)}
                </section>

                <section class="result-card">
                    <h6>特征贡献度列表</h6>
                    ${this.renderFeatureBarList(contributionRows.slice(0, 12), 'contribution-bars')}
                </section>

                <section class="result-card">
                    <h6>解释摘要</h6>
                    <div class="summary-card">
                        <p>Top 特征：${Array.isArray(summary.top_features) ? (summary.top_features as string[]).join(' / ') : '无'}</p>
                        <p>LIME 平均置信度：${Number(summary.lime_average_confidence || 0).toFixed(4)}</p>
                        <p>LIME 样本数：${Number(summary.lime_num_samples || 0)}</p>
                        <p class="muted">${String(visualization.summary_text || '暂无摘要文本')}</p>
                    </div>
                </section>
            </div>
        `;
    }

    private parseContributionRows(lime: Record<string, unknown>): Array<{ name: string; value: number }> {
        const batch = Array.isArray(lime.batch_explanations) ? lime.batch_explanations as Array<Record<string, unknown>> : [];
        const contributions: Array<{ name: string; value: number }> = [];
        for (const item of batch) {
            const top = Array.isArray(item.top_contributions) ? item.top_contributions as Array<Record<string, unknown>> : [];
            for (const row of top) {
                const name = String(row.feature_alias || row.feature || row.name || 'feature');
                const value = Number(row.value ?? row.shap_value ?? 0);
                if (Number.isFinite(value)) {
                    contributions.push({ name, value });
                }
            }
        }
        return this.mergeContribution(contributions);
    }

    private mergeContribution(rows: Array<{ name: string; value: number }>): Array<{ name: string; value: number }> {
        const mapper = new Map<string, number>();
        for (const row of rows) {
            mapper.set(row.name, (mapper.get(row.name) || 0) + row.value);
        }
        return Array.from(mapper.entries())
            .map(([name, value]) => ({ name, value }))
            .sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
    }

    private renderLocalExplanationList(rows: Array<Record<string, unknown>>): string {
        if (!rows.length) {
            return '<div class="status-message">暂无局部解释</div>';
        }
        return `
            <div class="local-explain-list">
                ${rows.slice(0, 6).map((item, idx) => {
                    const node = Number(item.node_index ?? idx);
                    const confidence = Number(item.confidence ?? 0).toFixed(4);
                    const fidelity = Number(item.fidelity ?? 0).toFixed(4);
                    const top = Array.isArray(item.top_contributions) ? item.top_contributions as Array<Record<string, unknown>> : [];
                    const topText = top.slice(0, 3).map((f) => `${String(f.feature || f.feature_alias || 'feature')}:${Number(f.value || 0).toFixed(3)}`).join(' ; ');
                    return `
                        <article class="local-explain-item">
                            <header>节点 #${node}</header>
                            <p>置信度 ${confidence} / 拟合度 ${fidelity}</p>
                            <p class="muted">${topText || '无贡献项'}</p>
                        </article>
                    `;
                }).join('')}
            </div>
        `;
    }

    private renderShapResult(result: Record<string, unknown>): string {
        const shap = (result.shap || {}) as Record<string, unknown>;
        const vis = (shap.visualization || {}) as Record<string, unknown>;

        const waterfall = this.parseImportanceRows(vis.waterfall_list || []);
        const ranking = this.parseImportanceRows(vis.feature_ranking || shap.global_feature_importance || []);
        const beeswarm = Array.isArray(vis.beeswarm_data) ? vis.beeswarm_data as Array<Record<string, unknown>> : [];
        const dependence = Array.isArray(vis.dependence_data) ? vis.dependence_data as Array<Record<string, unknown>> : [];
        const summaryStats = Array.isArray(vis.summary_stats) ? vis.summary_stats as Array<Record<string, unknown>> : [];

        return `
            <div class="explain-result-grid">
                <section class="result-card">
                    <h6>SHAP 瀑布图</h6>
                    ${this.renderFeatureBarList(waterfall.slice(0, 12), 'shap-waterfall')}
                </section>

                <section class="result-card">
                    <h6>SHAP 蜂群图</h6>
                    <div class="shap-filter-bar">
                        <label>贡献阈值 <input id="shap-threshold" class="input" type="number" step="0.01" value="0"></label>
                        <label>缩放 <input id="shap-zoom" type="range" min="0.5" max="2" step="0.1" value="1"></label>
                    </div>
                    <div id="shap-beeswarm" class="beeswarm-container">
                        ${this.renderBeeswarmPoints(beeswarm, 0, 1)}
                    </div>
                </section>

                <section class="result-card">
                    <h6>SHAP 依赖图</h6>
                    ${this.renderDependenceList(dependence)}
                </section>

                <section class="result-card">
                    <h6>特征重要性排序图</h6>
                    ${this.renderFeatureBarList(ranking.slice(0, 12), 'shap-ranking')}
                </section>

                <section class="result-card full-width">
                    <h6>SHAP 摘要统计表</h6>
                    ${this.renderSummaryTable(summaryStats)}
                </section>
            </div>
        `;
    }

    private renderBeeswarmPoints(rows: Array<Record<string, unknown>>, threshold: number, zoom: number): string {
        const filtered = rows
            .map((item) => ({
                x: Number(item.feature_value ?? item.x ?? 0),
                y: Number(item.shap_value ?? item.value ?? item.y ?? 0),
                feature: String(item.feature || item.feature_name || 'feature')
            }))
            .filter((row) => Number.isFinite(row.x) && Number.isFinite(row.y))
            .filter((row) => Math.abs(row.y) >= threshold)
            .slice(0, 220);

        if (!filtered.length) {
            return '<div class="status-message">当前筛选条件下无数据</div>';
        }

        const xValues = filtered.map(item => item.x);
        const yValues = filtered.map(item => item.y);
        const xMin = Math.min(...xValues);
        const xMax = Math.max(...xValues);
        const yMin = Math.min(...yValues);
        const yMax = Math.max(...yValues);
        const xSpan = Math.max(1e-6, xMax - xMin);
        const ySpan = Math.max(1e-6, yMax - yMin);

        return filtered.map((row, idx) => {
            const left = ((row.x - xMin) / xSpan) * 100;
            const top = 100 - ((row.y - yMin) / ySpan) * 100;
            const size = Math.max(6, Math.min(14, Math.round(8 * zoom)));
            const cls = row.y >= 0 ? 'positive' : 'negative';
            return `<span class="beeswarm-point ${cls}" title="${row.feature}: ${row.y.toFixed(4)}" style="left:${left}%;top:${top}%;width:${size}px;height:${size}px" data-idx="${idx}"></span>`;
        }).join('');
    }

    private bindShapInteractive(container: HTMLElement, result: Record<string, unknown>): void {
        const shap = (result.shap || {}) as Record<string, unknown>;
        const vis = (shap.visualization || {}) as Record<string, unknown>;
        const beeswarm = Array.isArray(vis.beeswarm_data) ? vis.beeswarm_data as Array<Record<string, unknown>> : [];

        const thresholdInput = container.querySelector('#shap-threshold') as HTMLInputElement | null;
        const zoomInput = container.querySelector('#shap-zoom') as HTMLInputElement | null;
        const target = container.querySelector('#shap-beeswarm') as HTMLElement | null;
        if (!thresholdInput || !zoomInput || !target) {
            return;
        }

        const rerender = (): void => {
            const threshold = Math.max(0, Number(thresholdInput.value || 0));
            const zoom = Math.max(0.5, Number(zoomInput.value || 1));
            target.innerHTML = this.renderBeeswarmPoints(beeswarm, threshold, zoom);
            target.style.transform = `scale(${zoom})`;
            target.style.transformOrigin = 'center center';
        };

        const debouncedRerender = this.createDebounced(rerender, 80);
        thresholdInput.addEventListener('input', debouncedRerender);
        zoomInput.addEventListener('input', debouncedRerender);
    }

    private renderDependenceList(rows: Array<Record<string, unknown>>): string {
        if (!rows.length) {
            return '<div class="status-message">暂无依赖图数据</div>';
        }

        const values = rows.slice(0, 12).map((row) => {
            const feature = String(row.feature || row.feature_name || 'feature');
            const corr = Number(row.correlation ?? row.pearson ?? 0);
            return { feature, corr };
        });

        return `
            <div class="dependence-list">
                ${values.map((item) => {
                    const width = Math.round(Math.min(100, Math.abs(item.corr) * 100));
                    return `
                        <div class="dependence-item">
                            <span>${item.feature}</span>
                            <div class="dependence-track">
                                <div class="dependence-fill ${item.corr >= 0 ? 'positive' : 'negative'}" style="width:${width}%"></div>
                            </div>
                            <span>${item.corr.toFixed(4)}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    private renderSummaryTable(rows: Array<Record<string, unknown>>): string {
        if (!rows.length) {
            return '<div class="status-message">暂无统计数据</div>';
        }

        return `
            <div class="summary-table-wrap">
                <table class="summary-table">
                    <thead>
                        <tr>
                            <th>特征</th>
                            <th>均值</th>
                            <th>方差</th>
                            <th>最大绝对贡献</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows.slice(0, 20).map((row) => `
                            <tr>
                                <td>${String(row.feature || row.feature_name || '-')}</td>
                                <td>${Number(row.mean || 0).toFixed(4)}</td>
                                <td>${Number(row.variance || row.var || 0).toFixed(4)}</td>
                                <td>${Number(row.max_abs || row.max_abs_shap || 0).toFixed(4)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    private renderCompareResult(result: Record<string, unknown>): string {
        const lime = (result.lime || {}) as Record<string, unknown>;
        const shap = (result.shap || {}) as Record<string, unknown>;

        const limeRows = this.parseImportanceRows(lime.global_feature_importance || ((lime.visualization || {}) as Record<string, unknown>).feature_importance_list || []);
        const shapRows = this.parseImportanceRows(shap.global_feature_importance || ((shap.visualization || {}) as Record<string, unknown>).feature_ranking || []);

        const merged = new Map<string, { lime: number; shap: number }>();
        for (const row of limeRows) {
            const value = merged.get(row.name) || { lime: 0, shap: 0 };
            value.lime = row.value;
            merged.set(row.name, value);
        }
        for (const row of shapRows) {
            const value = merged.get(row.name) || { lime: 0, shap: 0 };
            value.shap = row.value;
            merged.set(row.name, value);
        }

        const compared = Array.from(merged.entries())
            .map(([name, value]) => ({
                name,
                lime: value.lime,
                shap: value.shap,
                diff: Math.abs(value.lime - value.shap)
            }))
            .sort((a, b) => b.diff - a.diff)
            .slice(0, 16);

        if (!compared.length) {
            return '<div class="status-message">需要 Hybrid 或至少两个方法结果才能对比。</div>';
        }

        return `
            <div class="explain-result-grid">
                <section class="result-card full-width">
                    <h6>LIME vs SHAP 特征重要性对比图</h6>
                    <div class="compare-chart-list">
                        ${compared.map((row) => {
                            const maxVal = Math.max(1e-6, Math.max(Math.abs(row.lime), Math.abs(row.shap)));
                            const limePct = Math.round((Math.abs(row.lime) / maxVal) * 100);
                            const shapPct = Math.round((Math.abs(row.shap) / maxVal) * 100);
                            return `
                                <div class="compare-item ${row.diff > 0.15 ? 'highlight' : ''}">
                                    <div class="compare-name">${row.name}</div>
                                    <div class="compare-bars">
                                        <div class="compare-bar lime" style="width:${limePct}%">L ${row.lime.toFixed(3)}</div>
                                        <div class="compare-bar shap" style="width:${shapPct}%">S ${row.shap.toFixed(3)}</div>
                                    </div>
                                    <div class="compare-diff">差异 ${row.diff.toFixed(3)}</div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </section>

                <section class="result-card full-width">
                    <h6>解释结果对比表</h6>
                    <div class="summary-table-wrap">
                        <table class="summary-table">
                            <thead>
                                <tr>
                                    <th>特征</th>
                                    <th>LIME</th>
                                    <th>SHAP</th>
                                    <th>绝对差异</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${compared.map((row) => `
                                    <tr class="${row.diff > 0.15 ? 'highlight' : ''}">
                                        <td>${row.name}</td>
                                        <td>${row.lime.toFixed(4)}</td>
                                        <td>${row.shap.toFixed(4)}</td>
                                        <td>${row.diff.toFixed(4)}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </section>
            </div>
        `;
    }

    private renderSpatiotemporalResult(result: Record<string, unknown>): string {
        const summary = (result.summary || {}) as Record<string, unknown>;
        const task = this.getCurrentTask();
        const method = task ? this.detectMethodFromTask(task).toUpperCase() : '-';

        const coordinates = this.parseJSONInputSafe<Array<[number, number]>>('dl-explain-coords', []);
        const series = this.parseJSONInputSafe<number[][][]>('dl-explain-series', []);

        const heatmap = this.buildHeatmapRows(coordinates, result);
        const timeline = this.buildTimelineRows(series);

        return `
            <div class="explain-result-grid">
                <section class="result-card">
                    <h6>空间热力图（近似）</h6>
                    <div class="heatmap-grid">
                        ${heatmap.map((row) => {
                            const opacity = Math.max(0.12, Math.min(1, row.intensity));
                            return `
                                <button class="heatmap-cell" title="${row.label}" style="background: rgba(56, 189, 248, ${opacity});">
                                    ${row.value.toFixed(2)}
                                </button>
                            `;
                        }).join('')}
                    </div>
                </section>

                <section class="result-card">
                    <h6>时间序列图（特征均值）</h6>
                    <div class="timeline-list">
                        ${timeline.map((row) => `
                            <div class="timeline-item">
                                <span>T${row.index}</span>
                                <div class="timeline-track">
                                    <div class="timeline-fill" style="width:${row.width}%"></div>
                                </div>
                                <span>${row.value.toFixed(3)}</span>
                            </div>
                        `).join('')}
                    </div>
                </section>

                <section class="result-card full-width">
                    <h6>时空融合摘要</h6>
                    <div class="summary-card">
                        <p>解释方法：${method}</p>
                        <p>节点数：${Number(summary.n_nodes || coordinates.length || 0)}</p>
                        <p>序列长度：${Number(summary.seq_len || (series[0]?.length || 0))}</p>
                        <p>特征维度：${Number(summary.n_features || (series[0]?.[0]?.length || 0))}</p>
                        <p>Top 特征：${Array.isArray(summary.top_features) ? (summary.top_features as string[]).join(' / ') : '无'}</p>
                    </div>
                </section>
            </div>
        `;
    }

    private parseJSONInputSafe<T>(id: string, fallback: T): T {
        try {
            return this.parseJSONInput<T>(id, id);
        } catch {
            return fallback;
        }
    }

    private buildHeatmapRows(coords: Array<[number, number]>, result: Record<string, unknown>): Array<{ label: string; value: number; intensity: number }> {
        const summary = (result.summary || {}) as Record<string, unknown>;
        const base = Array.isArray(summary.top_features) ? (summary.top_features as string[]).length : 1;

        if (!coords.length) {
            return [{ label: '无坐标', value: 0, intensity: 0.2 }];
        }

        const centerX = coords.reduce((acc, item) => acc + Number(item[0] || 0), 0) / coords.length;
        const centerY = coords.reduce((acc, item) => acc + Number(item[1] || 0), 0) / coords.length;

        return coords.slice(0, 36).map((item, idx) => {
            const dx = Number(item[0]) - centerX;
            const dy = Number(item[1]) - centerY;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const intensity = 1 / (1 + dist * 6);
            return {
                label: `节点${idx} (${item[0]}, ${item[1]})`,
                value: base * intensity,
                intensity
            };
        });
    }

    private buildTimelineRows(series: number[][][]): Array<{ index: number; value: number; width: number }> {
        if (!series.length || !series[0]?.length) {
            return [];
        }

        const steps = series[0].length;
        const values: number[] = [];
        for (let t = 0; t < steps; t += 1) {
            let sum = 0;
            let count = 0;
            for (const node of series) {
                if (!Array.isArray(node[t])) {
                    continue;
                }
                for (const value of node[t]) {
                    const num = Number(value);
                    if (Number.isFinite(num)) {
                        sum += num;
                        count += 1;
                    }
                }
            }
            values.push(count ? sum / count : 0);
        }

        const maxVal = Math.max(...values.map(item => Math.abs(item)), 1e-6);
        return values.slice(0, 60).map((value, index) => ({
            index,
            value,
            width: Math.round((Math.abs(value) / maxVal) * 100)
        }));
    }

    private attachTaskListVirtualScroll(): void {
        const list = this.container.querySelector('#dl-explain-task-list') as HTMLElement | null;
        if (!list) {
            return;
        }
        if (this.taskListScrollHandler) {
            list.removeEventListener('scroll', this.taskListScrollHandler);
        }

        this.taskListScrollHandler = this.createThrottled(() => {
            const nearBottom = list.scrollTop + list.clientHeight >= list.scrollHeight - 48;
            if (!nearBottom) {
                return;
            }
            this.renderedTaskCount += this.taskBatchSize;
            this.renderTaskList();
        }, 160);

        list.addEventListener('scroll', this.taskListScrollHandler);
    }

    private createDebounced(callback: () => void, waitMs: number): () => void {
        let timer: number | null = null;
        return () => {
            if (timer !== null) {
                window.clearTimeout(timer);
            }
            timer = window.setTimeout(() => {
                timer = null;
                callback();
            }, waitMs);
        };
    }

    private createThrottled(callback: () => void, waitMs: number): () => void {
        let lastInvoke = 0;
        return () => {
            const now = Date.now();
            if (now - lastInvoke < waitMs) {
                return;
            }
            lastInvoke = now;
            callback();
        };
    }

    private async pollActiveTasks(): Promise<void> {
        const active = this.tasks.filter(task => ['queued', 'running', 'retrying'].includes(task.status));
        if (!active.length) {
            return;
        }

        await Promise.all(active.slice(0, 10).map(async (task) => {
            await this.refreshTaskById(task.task_id);
        }));
        await this.refreshMonitor();
    }

    private startAutoRefresh(): void {
        if (this.autoRefreshTimer !== null) {
            window.clearInterval(this.autoRefreshTimer);
        }

        this.autoRefreshTimer = window.setInterval(() => {
            if (!this.autoRefreshEnabled) {
                return;
            }
            void this.pollActiveTasks();
        }, 4000);
    }

    private stopAutoRefresh(): void {
        if (this.autoRefreshTimer !== null) {
            window.clearInterval(this.autoRefreshTimer);
            this.autoRefreshTimer = null;
        }
    }

    private setStatus(message: string, type: 'success' | 'warning' | 'error' | 'loading' = 'success'): void {
        const status = this.container.querySelector('#dl-explain-status') as HTMLElement | null;
        if (!status) {
            return;
        }

        status.className = 'status-message';
        if (type !== 'loading') {
            status.classList.add(type);
        }
        status.textContent = message;
    }

    private formatTime(iso: string): string {
        if (!iso) {
            return '-';
        }

        const date = new Date(iso);
        if (Number.isNaN(date.getTime())) {
            return iso;
        }

        return I18n.formatDateTime(date);
    }

    private formatNumber(value: number, options: Intl.NumberFormatOptions = {}): string {
        return I18n.formatNumber(value, options);
    }

    private t(key: string, fallback: string, params?: Record<string, string | number>): string {
        const translated = I18n.t(key, params);
        if (translated === key) {
            if (!params) {
                return fallback;
            }
            return fallback.replace(/\{([a-zA-Z0-9_]+)\}/g, (match, paramName: string) => {
                const value = params[paramName];
                return value === undefined ? match : String(value);
            });
        }
        return translated;
    }

    public destroy(): void {
        this.stopAutoRefresh();
        const list = this.container.querySelector('#dl-explain-task-list') as HTMLElement | null;
        if (list && this.taskListScrollHandler) {
            list.removeEventListener('scroll', this.taskListScrollHandler);
        }
        this.taskListScrollHandler = null;
        this.container.innerHTML = '';
    }
}
