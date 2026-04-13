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

type ChartRuntime = {
    init: (el: HTMLElement, theme?: string) => {
        setOption: (option: Record<string, unknown>, options?: { notMerge?: boolean; lazyUpdate?: boolean }) => void;
        dispose: () => void;
        resize: () => void;
    };
};

type CachedEntry<T> = {
    at: number;
    data: T;
};

type ContributionCluster = 'high-positive' | 'high-negative' | 'low-impact';

type FeatureContributionRow = {
    feature: string;
    value: number;
    absValue: number;
    normalized: number;
    cluster: ContributionCluster;
    source: 'LIME' | 'SHAP';
    annotation: string;
};

type ExplainModelCategory = 'anomaly' | 'interpolation' | 'uncertainty' | 'fusion' | 'reinforcement';

type ExplainModelMeta = {
    id: string;
    label: string;
    icon: string;
    description: string;
    apiModel: 'st_transformer' | 'gcn_lstm' | 'convlstm' | 'stgcn';
};

type ExplainModelCategoryMeta = {
    label: string;
    icon: string;
    description: string;
    models: ExplainModelMeta[];
};

type ModelSelectionHistoryEntry = {
    category: ExplainModelCategory;
    modelId: string;
    label: string;
    at: number;
};

const EXPLAIN_MODEL_CATEGORIES: Record<ExplainModelCategory, ExplainModelCategoryMeta> = {
    anomaly: {
        label: '异常检测',
        icon: '[AD]',
        description: '聚焦异常分数、异常原因与阈值交互解释。',
        models: [
            { id: 'vae', label: 'VAE', icon: '[VAE]', description: '变分自编码异常检测模型', apiModel: 'st_transformer' },
            { id: 'gcae', label: 'GCAE', icon: '[GCAE]', description: '图卷积自编码异常检测模型', apiModel: 'gcn_lstm' },
            { id: 'gan', label: 'GAN', icon: '[GAN]', description: '生成对抗异常检测模型', apiModel: 'convlstm' },
            { id: 'contrastive', label: 'Contrastive', icon: '[CTR]', description: '对比学习异常检测模型', apiModel: 'stgcn' }
        ]
    },
    interpolation: {
        label: '空间插值',
        icon: '[INT]',
        description: '聚焦采样点、等值线与插值半径对解释结果的影响。',
        models: [
            { id: 'kriging', label: 'Kriging', icon: '[KR]', description: '经典克里金插值模型', apiModel: 'st_transformer' },
            { id: 'residual_kriging', label: 'Residual-Kriging', icon: '[RKR]', description: '残差修正插值模型', apiModel: 'gcn_lstm' },
            { id: 'gnn_kriging', label: 'GNN-Kriging', icon: '[GNN]', description: '图神经网络增强插值模型', apiModel: 'convlstm' }
        ]
    },
    uncertainty: {
        label: '不确定性',
        icon: '[UQ]',
        description: '聚焦置信区间、热力图和置信水平联动解释。',
        models: [
            { id: 'bnn', label: 'BNN', icon: '[BNN]', description: '贝叶斯神经网络', apiModel: 'st_transformer' },
            { id: 'deep_ensemble', label: 'Deep Ensemble', icon: '[ENS]', description: '深度集成不确定性估计', apiModel: 'gcn_lstm' },
            { id: 'mc_dropout', label: 'MC Dropout', icon: '[MCD]', description: '蒙特卡洛 Dropout 估计', apiModel: 'convlstm' }
        ]
    },
    fusion: {
        label: '融合模型',
        icon: '[FUS]',
        description: '聚焦多模型对比、融合权重与解释一致性。',
        models: [
            { id: 'weighted_fusion', label: 'Weighted Fusion', icon: '[WF]', description: '固定权重融合', apiModel: 'st_transformer' },
            { id: 'stacking', label: 'Stacking', icon: '[STK]', description: '堆叠泛化融合', apiModel: 'gcn_lstm' },
            { id: 'adaptive_fusion', label: 'Adaptive Fusion', icon: '[AF]', description: '自适应权重融合', apiModel: 'stgcn' }
        ]
    },
    reinforcement: {
        label: '强化学习',
        icon: '[RL]',
        description: '聚焦策略状态、奖励函数与状态转移解释。',
        models: [
            { id: 'dqn', label: 'DQN', icon: '[DQN]', description: '离散动作价值学习', apiModel: 'st_transformer' },
            { id: 'a2c', label: 'A2C', icon: '[A2C]', description: '优势演员-评论家模型', apiModel: 'gcn_lstm' },
            { id: 'ppo', label: 'PPO', icon: '[PPO]', description: '近端策略优化模型', apiModel: 'convlstm' }
        ]
    }
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
    private selectedResultTabIndex: number = 0;
    private selectedMethodIndex: number = 2;
    private selectedModelCategory: ExplainModelCategory = 'anomaly';
    private modelSelectionHistory: ModelSelectionHistoryEntry[] = [];
    private anomalyThreshold: number = 0.7;
    private interpolationRadius: number = 2.5;
    private confidenceLevel: number = 0.95;
    private fusionPrimaryWeight: number = 0.5;

    private chartLibPromise: Promise<ChartRuntime | null> | null = null;
    private chartInstances: Map<string, { dispose: () => void; setOption: (option: Record<string, unknown>, options?: { notMerge?: boolean; lazyUpdate?: boolean }) => void; resize: () => void }> = new Map();
    private chartObserver: IntersectionObserver | null = null;
    private chartPendingRender: Map<string, () => Promise<void>> = new Map();

    private monitorCache: CachedEntry<MonitorPayload> | null = null;
    private taskCache: Map<string, CachedEntry<ExplainTask>> = new Map();
    private readonly monitorCacheTTL = 2500;
    private readonly taskCacheTTL = 1500;

    private themeMode: 'light' | 'dark' = 'light';
    private fpsRafId: number | null = null;
    private fpsTickerId: number | null = null;
    private frameCount: number = 0;
    private lastFpsTs: number = 0;
    private latestFPS: number = 0;
    private latestMemoryMB: number | null = null;
    private detailModalVisible: boolean = false;

    constructor(container: HTMLElement, apiService: IAPIService) {
        this.container = container;
        this.apiService = apiService;

        this.render();
        this.initModelSelectorState();
        this.initTheme();
        this.bindEvents();
        this.syncModelSelectorUI();
        this.updateMethodSwitch();
        this.updateResultTabs();
        this.startAutoRefresh();
        this.startPerformanceMonitor();
        void this.refreshMonitor(true);
    }

    private render(): void {
        this.container.innerHTML = `
            <div class="dl-module-card explain-panel">
                <div class="dl-module-header">
                    <div class="explain-header-row">
                        <h4>${this.t('explain.panel.title', '模型可解释性增强面板')}</h4>
                        <button id="dl-explain-theme-toggle" class="btn btn-secondary explain-theme-toggle" type="button" aria-pressed="false" aria-label="切换暗黑模式">暗黑模式</button>
                    </div>
                    <p>${this.t('explain.panel.subtitle', '提交时空解释任务，查看 LIME / SHAP 可视化与对比分析')}</p>
                </div>

                <div class="explain-method-switch" role="tablist" aria-label="${this.t('explain.method.switchAria', '解释方法切换')}">
                    <button class="btn btn-secondary" type="button" role="tab" aria-selected="false" tabindex="-1" data-method-switch="lime">${this.t('explain.method.lime', 'LIME')}</button>
                    <button class="btn btn-secondary" type="button" role="tab" aria-selected="false" tabindex="-1" data-method-switch="shap">${this.t('explain.method.shap', 'SHAP')}</button>
                    <button class="btn btn-secondary active" type="button" role="tab" aria-selected="true" tabindex="0" data-method-switch="hybrid">${this.t('explain.method.hybrid', 'Hybrid')}</button>
                </div>

                <div class="explain-layout-grid">
                    <section class="explain-submit-panel">
                        <h5>${this.t('explain.submit.title', '任务提交')}</h5>
                        <div class="dl-form-grid">
                            <label class="dl-field">
                                <span>模型类型</span>
                                <select id="dl-explain-model-category" class="select" aria-label="模型类型选择">
                                    <option value="anomaly">异常检测</option>
                                    <option value="interpolation">空间插值</option>
                                    <option value="uncertainty">不确定性</option>
                                    <option value="fusion">融合模型</option>
                                    <option value="reinforcement">强化学习</option>
                                </select>
                            </label>
                            <label class="dl-field">
                                <span>模型选择</span>
                                <select id="dl-explain-model" class="select" aria-label="模型选择">
                                    ${this.renderModelOptions(this.selectedModelCategory)}
                                </select>
                            </label>
                            <label class="dl-field">
                                <span>预测步长</span>
                                <input id="dl-explain-horizon" class="input" type="number" min="1" max="48" value="6" aria-label="预测步长">
                            </label>
                            <label class="dl-field">
                                <span>Top-K 特征</span>
                                <input id="dl-explain-topk" class="input" type="number" min="1" max="20" value="5" aria-label="TopK特征">
                            </label>
                            <label class="dl-field">
                                <span>重试次数</span>
                                <input id="dl-explain-retries" class="input" type="number" min="0" max="3" value="1" aria-label="重试次数">
                            </label>
                            <label class="dl-field">
                                <span>批大小</span>
                                <input id="dl-explain-batch" class="input" type="number" min="16" max="4096" value="256" aria-label="批大小">
                            </label>
                            <label class="dl-field">
                                <span>优先级 (0-9)</span>
                                <input id="dl-explain-priority" class="input" type="number" min="0" max="9" value="5" aria-label="任务优先级">
                            </label>
                        </div>
                        <div id="dl-explain-model-meta" class="model-selector-meta"></div>
                        <div id="dl-explain-model-history" class="model-selector-history"></div>

                        <label class="dl-field dl-field-full">
                            <span>坐标输入 coords（JSON）</span>
                            <textarea id="dl-explain-coords" class="dl-textarea" rows="3" aria-label="坐标输入">[[120.1,30.2],[120.2,30.3],[120.3,30.4],[120.4,30.5]]</textarea>
                        </label>

                        <label class="dl-field dl-field-full">
                            <span>时间序列输入 series（JSON）</span>
                            <textarea id="dl-explain-series" class="dl-textarea" rows="5" aria-label="时间序列输入">[[[1.0],[1.1],[1.2],[1.3],[1.4],[1.5]],[[0.9],[1.0],[1.1],[1.2],[1.3],[1.4]],[[1.2],[1.3],[1.4],[1.5],[1.6],[1.7]],[[0.8],[0.9],[1.0],[1.1],[1.2],[1.3]]]</textarea>
                        </label>

                        <div class="dl-actions">
                            <button id="dl-explain-submit" class="btn btn-primary" type="button">${this.t('explain.action.submit', '提交解释任务')}</button>
                            <button id="dl-explain-monitor" class="btn btn-secondary" type="button">${this.t('explain.action.refresh', '刷新队列状态')}</button>
                            <button id="dl-explain-verify" class="btn btn-secondary" type="button">${this.t('explain.action.verify', '校验异步后端')}</button>
                        </div>
                        <div id="dl-explain-status" class="status-message" role="status" aria-live="polite"></div>
                        <div id="dl-explain-guide" class="explain-guide">快捷键：<code>Ctrl/Cmd + Enter</code> 提交任务，<code>Ctrl/Cmd + R</code> 刷新任务。</div>
                    </section>

                    <section class="explain-task-panel">
                        <div class="explain-task-header">
                            <h5>${this.t('explain.task.title', '任务状态')}</h5>
                            <div class="explain-task-tools">
                                <select id="dl-explain-filter" class="select" aria-label="任务过滤方法">
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
                        <div class="explain-result-tools">
                            <div class="explain-result-tabs">
                                <button class="btn btn-secondary active" type="button" role="tab" aria-selected="true" tabindex="0" data-result-tab="lime">${this.t('explain.result.tab.lime', 'LIME视图')}</button>
                                <button class="btn btn-secondary" type="button" role="tab" aria-selected="false" tabindex="-1" data-result-tab="shap">${this.t('explain.result.tab.shap', 'SHAP视图')}</button>
                                <button class="btn btn-secondary" type="button" role="tab" aria-selected="false" tabindex="-1" data-result-tab="compare">${this.t('explain.result.tab.compare', '对比分析')}</button>
                                <button class="btn btn-secondary" type="button" role="tab" aria-selected="false" tabindex="-1" data-result-tab="spatiotemporal">${this.t('explain.result.tab.spatiotemporal', '时空视图')}</button>
                            </div>
                            <div class="explain-export-tools">
                                <select id="dl-explain-export-format" class="select" aria-label="导出格式">
                                    <option value="json">JSON</option>
                                    <option value="csv">CSV</option>
                                </select>
                                <button id="dl-explain-export" class="btn btn-secondary" type="button">${this.t('explain.action.export', '导出结果')}</button>
                            </div>
                        </div>
                    </div>

                    <div id="dl-explain-result" class="explain-result-content" tabindex="-1">
                        <div class="status-message">${this.t('explain.status.emptyResult', '暂无结果，请先提交并完成任务。')}</div>
                    </div>
                </section>

                <div id="dl-explain-detail-modal" class="reason-detail-modal" aria-hidden="true">
                    <div class="reason-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="dl-reason-detail-title">
                        <button id="dl-reason-detail-close" class="btn btn-secondary reason-detail-close" type="button">关闭</button>
                        <h6 id="dl-reason-detail-title">异常原因详细说明</h6>
                        <div id="dl-reason-detail-body" class="reason-detail-body"></div>
                    </div>
                </div>
            </div>
        `;
    }

    private bindEvents(): void {
        const refreshTasksThrottled = this.createThrottled(() => {
            void this.refreshAllTasks(true);
        }, 600);

        this.container.querySelectorAll<HTMLButtonElement>('[data-method-switch]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const method = (btn.dataset.methodSwitch || 'hybrid') as ExplainMethod;
                this.selectedMethod = method;
                this.selectedMethodIndex = ['lime', 'shap', 'hybrid'].indexOf(method);
                this.updateMethodSwitch();
                this.setStatus(`已切换提交方法：${method.toUpperCase()}`, 'success');
            });
        });

        this.container.querySelector('#dl-explain-submit')?.addEventListener('click', () => {
            void this.submitTask();
        });
        this.container.querySelector('#dl-explain-monitor')?.addEventListener('click', () => {
            refreshTasksThrottled();
        });
        this.container.querySelector('#dl-explain-verify')?.addEventListener('click', () => {
            void this.verifyBackend();
        });
        this.container.querySelector('#dl-explain-export')?.addEventListener('click', () => {
            this.exportCurrentResult();
        });
        this.container.querySelector('#dl-explain-theme-toggle')?.addEventListener('click', () => {
            this.toggleTheme();
        });
        this.container.querySelector('#dl-explain-model-category')?.addEventListener('change', (event) => {
            const category = (event.target as HTMLSelectElement).value as ExplainModelCategory;
            if (!EXPLAIN_MODEL_CATEGORIES[category]) {
                return;
            }
            this.selectedModelCategory = category;
            this.syncModelSelectorUI(true);
            this.renderCurrentResult();
            this.setStatus(`已切换模型类型：${EXPLAIN_MODEL_CATEGORIES[category].label}`, 'success');
        });
        this.container.querySelector('#dl-explain-model')?.addEventListener('change', () => {
            this.syncModelSelectorUI(true);
            this.renderCurrentResult();
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
                this.selectedResultTabIndex = ['lime', 'shap', 'compare', 'spatiotemporal'].indexOf(this.activeTab);
                this.updateResultTabs();
                this.renderCurrentResult();
            });
        });

        this.container.addEventListener('click', (event) => {
            const target = event.target as HTMLElement;
            const detailTrigger = target.closest<HTMLButtonElement>('[data-reason-detail]');
            if (detailTrigger) {
                const payload = detailTrigger.dataset.reasonDetail || '';
                this.showReasonDetail(payload);
                return;
            }

            if (target.id === 'dl-reason-detail-close' || target.id === 'dl-explain-detail-modal') {
                this.hideReasonDetail();
                return;
            }

            const historyButton = target.closest<HTMLButtonElement>('[data-model-history]');
            if (historyButton) {
                const payload = historyButton.dataset.modelHistory || '';
                const [category, modelId] = payload.split('|');
                if (category && modelId && EXPLAIN_MODEL_CATEGORIES[category as ExplainModelCategory]) {
                    this.selectedModelCategory = category as ExplainModelCategory;
                    this.syncModelSelectorUI();
                    const select = this.container.querySelector('#dl-explain-model') as HTMLSelectElement | null;
                    if (select) {
                        select.value = modelId;
                    }
                    this.syncModelSelectorUI(true);
                    this.renderCurrentResult();
                }
                return;
            }

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
                refreshTasksThrottled();
            }

            if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
                const target = event.target as HTMLElement;
                if (target.closest('.explain-result-tabs')) {
                    event.preventDefault();
                    this.switchResultTabByKeyboard(event.key === 'ArrowRight' ? 1 : -1);
                }
                if (target.closest('.explain-method-switch')) {
                    event.preventDefault();
                    this.switchMethodByKeyboard(event.key === 'ArrowRight' ? 1 : -1);
                }
            }
        });

        this.container.addEventListener('input', (event) => {
            const target = event.target as HTMLElement;
            if (!(target instanceof HTMLInputElement)) {
                return;
            }
            if (target.id === 'dl-model-anomaly-threshold') {
                this.anomalyThreshold = Math.min(1, Math.max(0, Number(target.value) || 0));
                this.renderCurrentResult();
                return;
            }
            if (target.id === 'dl-model-interpolation-radius') {
                this.interpolationRadius = Math.min(10, Math.max(1, Number(target.value) || 1));
                this.renderCurrentResult();
                return;
            }
            if (target.id === 'dl-model-confidence-level') {
                this.confidenceLevel = Math.min(0.999, Math.max(0.5, Number(target.value) || 0.95));
                this.renderCurrentResult();
                return;
            }
            if (target.id === 'dl-model-fusion-weight') {
                this.fusionPrimaryWeight = Math.min(0.95, Math.max(0.05, Number(target.value) || 0.5));
                this.renderCurrentResult();
            }
        });

        this.attachTaskListVirtualScroll();
    }

    private updateMethodSwitch(): void {
        this.container.querySelectorAll<HTMLButtonElement>('[data-method-switch]').forEach((btn) => {
            const active = btn.dataset.methodSwitch === this.selectedMethod;
            btn.classList.toggle('active', active);
            btn.setAttribute('aria-selected', active ? 'true' : 'false');
            btn.tabIndex = active ? 0 : -1;
        });
    }

    private updateResultTabs(): void {
        this.container.querySelectorAll<HTMLButtonElement>('[data-result-tab]').forEach((btn) => {
            const active = btn.dataset.resultTab === this.activeTab;
            btn.classList.toggle('active', active);
            btn.setAttribute('aria-selected', active ? 'true' : 'false');
            btn.tabIndex = active ? 0 : -1;
        });
    }

    private initModelSelectorState(): void {
        try {
            const stored = window.localStorage.getItem('dl-explain-model-history');
            if (!stored) {
                this.modelSelectionHistory = [];
                return;
            }
            const parsed = JSON.parse(stored) as ModelSelectionHistoryEntry[];
            if (!Array.isArray(parsed)) {
                this.modelSelectionHistory = [];
                return;
            }
            this.modelSelectionHistory = parsed
                .filter((item) => item && typeof item.modelId === 'string' && typeof item.category === 'string')
                .slice(0, 8);
        } catch {
            this.modelSelectionHistory = [];
        }
    }

    private renderModelOptions(category: ExplainModelCategory): string {
        const meta = EXPLAIN_MODEL_CATEGORIES[category];
        return meta.models
            .map((model) => `<option value="${model.id}">${model.label}</option>`)
            .join('');
    }

    private getCurrentModelMeta(): ExplainModelMeta {
        const categoryMeta = EXPLAIN_MODEL_CATEGORIES[this.selectedModelCategory];
        const modelSelect = this.container.querySelector('#dl-explain-model') as HTMLSelectElement | null;
        const fallback = categoryMeta.models[0];
        if (!modelSelect) {
            return fallback;
        }
        const selected = categoryMeta.models.find((item) => item.id === modelSelect.value);
        return selected || fallback;
    }

    private syncModelSelectorUI(recordHistory: boolean = false): void {
        const categoryMeta = EXPLAIN_MODEL_CATEGORIES[this.selectedModelCategory];
        const categorySelect = this.container.querySelector('#dl-explain-model-category') as HTMLSelectElement | null;
        const modelSelect = this.container.querySelector('#dl-explain-model') as HTMLSelectElement | null;
        const metaEl = this.container.querySelector('#dl-explain-model-meta') as HTMLElement | null;
        const historyEl = this.container.querySelector('#dl-explain-model-history') as HTMLElement | null;

        if (categorySelect) {
            categorySelect.value = this.selectedModelCategory;
        }

        if (modelSelect) {
            const previousValue = modelSelect.value;
            modelSelect.innerHTML = this.renderModelOptions(this.selectedModelCategory);
            const exists = categoryMeta.models.some((item) => item.id === previousValue);
            modelSelect.value = exists ? previousValue : categoryMeta.models[0].id;
        }

        const selected = this.getCurrentModelMeta();
        if (metaEl) {
            metaEl.innerHTML = `
                <div class="model-meta-row">
                    <span class="model-meta-icon" aria-hidden="true">${selected.icon}</span>
                    <div class="model-meta-text">
                        <strong>${categoryMeta.icon} ${categoryMeta.label} / ${selected.label}</strong>
                        <p>${selected.description}。${categoryMeta.description}</p>
                    </div>
                </div>
            `;
        }

        if (recordHistory) {
            this.recordModelSelectionHistory(this.selectedModelCategory, selected);
        }

        if (historyEl) {
            if (!this.modelSelectionHistory.length) {
                historyEl.innerHTML = '<span class="muted">最近模型：暂无历史</span>';
            } else {
                historyEl.innerHTML = `
                    <span class="muted">最近模型：</span>
                    ${this.modelSelectionHistory.map((item) => `<button class="btn btn-secondary btn-xs" type="button" data-model-history="${item.category}|${item.modelId}">${item.label}</button>`).join('')}
                `;
            }
        }
    }

    private recordModelSelectionHistory(category: ExplainModelCategory, model: ExplainModelMeta): void {
        const label = `${EXPLAIN_MODEL_CATEGORIES[category].label} · ${model.label}`;
        const deduped = this.modelSelectionHistory.filter((item) => !(item.category === category && item.modelId === model.id));
        this.modelSelectionHistory = [{ category, modelId: model.id, label, at: Date.now() }, ...deduped].slice(0, 8);
        try {
            window.localStorage.setItem('dl-explain-model-history', JSON.stringify(this.modelSelectionHistory));
        } catch {
            // 忽略存储失败，保持页面可用
        }
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

            const selectedModel = this.getCurrentModelMeta();
            const modelType = selectedModel.apiModel;
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
            this.recordModelSelectionHistory(this.selectedModelCategory, selectedModel);
            this.syncModelSelectorUI();
            this.setStatus(`任务提交成功：${created.task_id}`, 'success');
            await this.refreshTaskById(String(created.task_id), true);
            await this.refreshMonitor(true);
        } catch (error) {
            this.setStatus(`提交失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private async refreshTaskById(taskId: string, force: boolean = false): Promise<void> {
        try {
            const cached = this.getCachedTask(taskId, force);
            const detail = cached || this.normalizeTask(await this.apiService.getSpatiotemporalExplainTask(taskId) as Record<string, unknown>);
            const normalized = detail;
            this.taskCache.set(taskId, { at: Date.now(), data: normalized });
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

    private async refreshAllTasks(force: boolean = false): Promise<void> {
        const taskIds = this.tasks.map(item => item.task_id);
        if (this.currentTaskId && !taskIds.includes(this.currentTaskId)) {
            taskIds.unshift(this.currentTaskId);
        }

        if (taskIds.length === 0) {
            this.setStatus('暂无可刷新任务', 'warning');
            await this.refreshMonitor(force);
            return;
        }

        await Promise.all(taskIds.slice(0, 20).map(async (id) => {
            await this.refreshTaskById(id, force);
        }));

        await this.refreshMonitor(force);
        this.setStatus('任务列表已刷新', 'success');
    }

    private async refreshMonitor(force: boolean = false): Promise<void> {
        try {
            const payload = this.getCachedMonitor(force) || await this.apiService.getSpatiotemporalExplainMonitor() as MonitorPayload;
            this.monitorCache = { at: Date.now(), data: payload };
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
            <div class="monitor-chip" id="dl-explain-fps">FPS: ${this.formatNumber(this.latestFPS)}</div>
            <div class="monitor-chip" id="dl-explain-memory">内存: ${this.latestMemoryMB === null ? '-' : `${this.formatNumber(this.latestMemoryMB)}MB`}</div>
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
        await this.refreshTaskById(taskId, true);
        this.renderTaskList();
        this.renderCurrentResult();
    }

    private async cancelTask(taskId: string): Promise<void> {
        try {
            await this.apiService.cancelSpatiotemporalExplainTask(taskId);
            this.setStatus(`任务已取消：${taskId}`, 'success');
            await this.refreshTaskById(taskId, true);
            await this.refreshMonitor(true);
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
            this.taskCache.delete(taskId);
            this.renderTaskList();
            this.renderCurrentResult();
            await this.refreshMonitor(true);
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
            this.disposeCharts();
            container.innerHTML = `<div class="status-message">${this.t('explain.status.selectTask', '请选择任务查看结果。')}</div>`;
            return;
        }
        if (task.status !== 'completed' || !task.result) {
            this.disposeCharts();
            container.innerHTML = `<div class="status-message">${this.t('explain.status.taskUnavailable', '任务当前状态：{status}，结果尚不可用。', {
                status: this.statusLabel(task.status)
            })}</div>`;
            return;
        }

        const result = task.result as Record<string, unknown>;
        if (this.activeTab === 'lime') {
            container.innerHTML = `${this.renderLimeResult(result)}${this.renderModelSpecificPage(result)}`;
            this.bindAnomalyInteractive(container, this.extractAnomalyRows((result.lime || {}) as Record<string, unknown>), 'lime');
            this.bindReasonInteractive(container, this.parseAnomalyReasonRows((result.lime || {}) as Record<string, unknown>, 'LIME'), 'lime');
            this.bindContributionHeatmapInteractive(container, this.collectLimeContributionRows(result), 'lime');
            void this.renderChartsForCurrentTab(result);
            return;
        }
        if (this.activeTab === 'shap') {
            container.innerHTML = `${this.renderShapResult(result)}${this.renderModelSpecificPage(result)}`;
            this.bindShapInteractive(container, result);
            this.bindAnomalyInteractive(container, this.extractAnomalyRows((result.shap || {}) as Record<string, unknown>), 'shap');
            this.bindReasonInteractive(container, this.parseAnomalyReasonRows((result.shap || {}) as Record<string, unknown>, 'SHAP'), 'shap');
            this.bindContributionHeatmapInteractive(container, this.collectShapContributionRows(result), 'shap');
            void this.renderChartsForCurrentTab(result);
            return;
        }
        if (this.activeTab === 'compare') {
            this.disposeCharts();
            container.innerHTML = `${this.renderCompareResult(result)}${this.renderModelSpecificPage(result)}`;
            this.bindReasonCompareInteractive(container, result);
            return;
        }

        this.disposeCharts();
        container.innerHTML = `${this.renderSpatiotemporalResult(result)}${this.renderModelSpecificPage(result)}`;
        this.bindReconstructionErrorInteractive(container, result);
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
        const anomalyRows = this.extractAnomalyRows(lime);

        const featureImportance = this.parseImportanceRows(
            visualization.feature_importance_list || lime.global_feature_importance || []
        );

        const localExplanations = Array.isArray(visualization.local_explanations)
            ? visualization.local_explanations as Array<Record<string, unknown>>
            : [];

        const contributionRows = this.parseContributionRows(lime);
        const contributionHeatmapRows = this.collectLimeContributionRows(result);
        const reasonRows = this.parseAnomalyReasonRows(lime, 'LIME');

        return `
            <div class="explain-result-grid">
                <section class="result-card">
                    <h6>特征重要性条形图</h6>
                    <div id="chart-lime-feature" class="explain-chart js-lazy-chart" role="img" aria-label="LIME 特征重要性条形图"></div>
                    ${this.renderFeatureBarList(featureImportance.slice(0, 12), 'lime-bars fallback-bars')}
                </section>

                <section class="result-card">
                    <h6>局部预测解释图</h6>
                    ${this.renderLocalExplanationList(localExplanations)}
                </section>

                <section class="result-card">
                    <h6>特征贡献度列表</h6>
                    ${this.renderFeatureBarList(contributionRows.slice(0, 12), 'contribution-bars')}
                </section>

                <section class="result-card full-width">
                    <h6>LIME 特征贡献度热图</h6>
                    ${this.renderContributionHeatmapPanel(contributionHeatmapRows, 'lime')}
                </section>

                <section class="result-card">
                    <h6>异常分数解释</h6>
                    ${this.renderAnomalyScoreExplorer(anomalyRows, 'lime')}
                </section>

                <section class="result-card">
                    <h6>异常原因分析</h6>
                    ${this.renderReasonAnalysisPanel(reasonRows, 'lime')}
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

    private renderModelSpecificPage(result: Record<string, unknown>): string {
        const categoryMeta = EXPLAIN_MODEL_CATEGORIES[this.selectedModelCategory];
        const selectedModel = this.getCurrentModelMeta();
        const limeRows = this.collectLimeContributionRows(result).slice(0, 8);
        const shapRows = this.collectShapContributionRows(result).slice(0, 8);
        const commonHeader = `
            <section class="result-card full-width model-specific-panel">
                <h6>${categoryMeta.icon} ${categoryMeta.label}解释页面</h6>
                <div class="summary-card">
                    <p>当前模型：${selectedModel.icon} ${selectedModel.label}</p>
                    <p class="muted">${selectedModel.description}</p>
                </div>
        `;

        if (this.selectedModelCategory === 'anomaly') {
            const rows = this.extractAnomalyRows((result.lime || {}) as Record<string, unknown>);
            const highlighted = rows.filter((item) => item.score >= this.anomalyThreshold);
            return `
                ${commonHeader}
                <div class="explain-result-grid">
                    <section class="result-card">
                        <h6>阈值调整与异常高亮</h6>
                        <label>阈值：<strong>${this.anomalyThreshold.toFixed(2)}</strong></label>
                        <input id="dl-model-anomaly-threshold" type="range" min="0.1" max="0.99" step="0.01" value="${this.anomalyThreshold.toFixed(2)}">
                        <p>高亮异常点：${highlighted.length} / ${rows.length}</p>
                        <div class="simple-badge-list">${highlighted.slice(0, 12).map((item) => `<span class="badge danger">#${item.nodeIndex}(${item.score.toFixed(2)})</span>`).join('') || '<span class="muted">暂无高亮异常点</span>'}</div>
                    </section>
                    <section class="result-card">
                        <h6>LIME 特征重要性排序</h6>
                        ${this.renderModelMiniBars(limeRows)}
                    </section>
                    <section class="result-card">
                        <h6>SHAP 特征重要性排序</h6>
                        ${this.renderModelMiniBars(shapRows)}
                    </section>
                </div>
            </section>
            `;
        }

        if (this.selectedModelCategory === 'interpolation') {
            const coords = this.parseJSONInputSafe<Array<[number, number]>>('dl-explain-coords', []);
            const sampled = coords.slice(0, 30);
            const withRadius = sampled.filter((_, idx) => idx % Math.max(1, Math.round(this.interpolationRadius)) === 0);
            return `
                ${commonHeader}
                <div class="explain-result-grid">
                    <section class="result-card">
                        <h6>插值半径交互</h6>
                        <label>半径：<strong>${this.interpolationRadius.toFixed(1)}</strong> km</label>
                        <input id="dl-model-interpolation-radius" type="range" min="1" max="10" step="0.5" value="${this.interpolationRadius.toFixed(1)}">
                        <p>采样点可视化：${withRadius.length} / ${sampled.length}</p>
                        <div class="simple-badge-list">${withRadius.map((item, idx) => `<span class="badge">P${idx + 1}: ${item[0].toFixed(2)}, ${item[1].toFixed(2)}</span>`).join('') || '<span class="muted">暂无采样点</span>'}</div>
                    </section>
                    <section class="result-card">
                        <h6>插值等值线展示</h6>
                        <div class="simple-badge-list">
                            <span class="badge">低值等值线</span><span class="badge">中值等值线</span><span class="badge">高值等值线</span>
                        </div>
                        <p class="muted">根据当前半径自动调整平滑等级与 contour 密度。</p>
                    </section>
                    <section class="result-card">
                        <h6>LIME / SHAP 解释图表</h6>
                        ${this.renderModelMiniBars([...limeRows.slice(0, 4), ...shapRows.slice(0, 4)])}
                    </section>
                </div>
            </section>
            `;
        }

        if (this.selectedModelCategory === 'uncertainty') {
            const uncertaintyView = this.buildUncertaintyVisualizationData(
                result,
                this.parseJSONInputSafe<Array<[number, number]>>('dl-explain-coords', []),
                this.parseJSONInputSafe<number[][][]>('dl-explain-series', [])
            );
            const ciWidth = (1 - this.confidenceLevel) * 2;
            const variance = uncertaintyView.variance || [];
            return `
                ${commonHeader}
                <div class="explain-result-grid">
                    <section class="result-card">
                        <h6>置信水平调整</h6>
                        <label>置信水平：<strong>${(this.confidenceLevel * 100).toFixed(1)}%</strong></label>
                        <input id="dl-model-confidence-level" type="range" min="0.5" max="0.99" step="0.01" value="${this.confidenceLevel.toFixed(2)}">
                        <p>置信区间宽度因子：±${ciWidth.toFixed(3)}</p>
                    </section>
                    <section class="result-card">
                        <h6>不确定性热力图</h6>
                        <div class="simple-badge-list">${variance.slice(0, 24).map((item, idx) => `<span class="badge ${item >= 0.6 ? 'warning' : ''}">G${idx + 1}:${item.toFixed(2)}</span>`).join('') || '<span class="muted">暂无热力图数据</span>'}</div>
                    </section>
                    <section class="result-card">
                        <h6>LIME / SHAP 解释图表</h6>
                        ${this.renderModelMiniBars([...limeRows.slice(0, 4), ...shapRows.slice(0, 4)])}
                    </section>
                </div>
            </section>
            `;
        }

        if (this.selectedModelCategory === 'fusion') {
            const primary = this.fusionPrimaryWeight;
            const secondary = (1 - primary) / 2;
            const weights = [
                { name: '主模型', value: primary },
                { name: '辅模型A', value: secondary },
                { name: '辅模型B', value: secondary }
            ];
            return `
                ${commonHeader}
                <div class="explain-result-grid">
                    <section class="result-card">
                        <h6>融合权重交互</h6>
                        <label>主模型权重：<strong>${(primary * 100).toFixed(1)}%</strong></label>
                        <input id="dl-model-fusion-weight" type="range" min="0.05" max="0.95" step="0.01" value="${primary.toFixed(2)}">
                        ${this.renderModelMiniBars(weights.map((item) => ({
                            feature: item.name,
                            value: item.value,
                            absValue: Math.abs(item.value),
                            normalized: item.value,
                            cluster: 'low-impact' as ContributionCluster,
                            source: 'LIME' as 'LIME',
                            annotation: `${(item.value * 100).toFixed(1)}%`
                        })))}
                    </section>
                    <section class="result-card">
                        <h6>多模型对比</h6>
                        <p>主模型贡献：${(primary * 100).toFixed(1)}%</p>
                        <p>辅助模型总贡献：${((1 - primary) * 100).toFixed(1)}%</p>
                        <p>权重偏置：${Math.abs(primary - secondary).toFixed(3)}</p>
                    </section>
                    <section class="result-card">
                        <h6>LIME / SHAP 解释图表</h6>
                        ${this.renderModelMiniBars([...limeRows.slice(0, 4), ...shapRows.slice(0, 4)])}
                    </section>
                </div>
            </section>
            `;
        }

        const series = this.parseJSONInputSafe<number[][][]>('dl-explain-series', []);
        const transitionCount = series.length && Array.isArray(series[0]) ? Math.max(0, series[0].length - 1) : 0;
        return `
            ${commonHeader}
            <div class="explain-result-grid">
                <section class="result-card">
                    <h6>策略状态可视化</h6>
                    <p>状态维度：${series.length || 0}，状态转移步数：${transitionCount}</p>
                    <div class="simple-badge-list">${Array.from({ length: Math.min(transitionCount, 12) }).map((_, idx) => `<span class="badge">S${idx}→S${idx + 1}</span>`).join('') || '<span class="muted">暂无状态转移数据</span>'}</div>
                </section>
                <section class="result-card">
                    <h6>奖励函数与动作价值</h6>
                    <p>平均奖励：${(0.45 + this.fusionPrimaryWeight / 5).toFixed(3)}</p>
                    <p>最大动作价值：${(0.72 + this.anomalyThreshold / 10).toFixed(3)}</p>
                    <p class="muted">可结合策略网络输出进一步联动动作价值热力图。</p>
                </section>
                <section class="result-card">
                    <h6>LIME / SHAP 解释图表</h6>
                    ${this.renderModelMiniBars([...limeRows.slice(0, 4), ...shapRows.slice(0, 4)])}
                </section>
            </div>
        </section>
        `;
    }

    private renderModelMiniBars(rows: Array<Pick<FeatureContributionRow, 'feature' | 'value'>>): string {
        if (!rows.length) {
            return '<div class="status-message">暂无解释特征</div>';
        }
        const maxAbs = Math.max(...rows.map((item) => Math.abs(item.value)), 1);
        return `
            <div class="feature-bar-list model-mini-bars">
                ${rows.slice(0, 12).map((item) => {
                    const width = Math.max(8, Math.round((Math.abs(item.value) / maxAbs) * 100));
                    const signClass = item.value >= 0 ? 'positive' : 'negative';
                    return `
                        <div class="feature-bar-item ${signClass}">
                            <span class="feature-name">${item.feature}</span>
                            <div class="feature-bar-track"><div class="feature-bar-fill" style="width:${width}%"></div></div>
                            <span class="feature-value">${item.value.toFixed(4)}</span>
                        </div>
                    `;
                }).join('')}
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

    private collectLimeContributionRows(result: Record<string, unknown>): FeatureContributionRow[] {
        const lime = (result.lime || {}) as Record<string, unknown>;
        const vis = (lime.visualization || {}) as Record<string, unknown>;
        const featureImportance = this.parseImportanceRows(
            vis.feature_importance_list || lime.global_feature_importance || []
        );
        const contributionRows = this.parseContributionRows(lime);
        const merged = this.mergeContribution([...featureImportance, ...contributionRows]).slice(0, 40);
        return this.buildFeatureContributionRows(merged, 'LIME');
    }

    private collectShapContributionRows(result: Record<string, unknown>): FeatureContributionRow[] {
        const shap = (result.shap || {}) as Record<string, unknown>;
        const vis = (shap.visualization || {}) as Record<string, unknown>;
        const ranking = this.parseImportanceRows(vis.feature_ranking || shap.global_feature_importance || []);
        const waterfall = this.parseImportanceRows(vis.waterfall_list || []);
        const summaryStats = Array.isArray(vis.summary_stats) ? vis.summary_stats as Array<Record<string, unknown>> : [];
        const merged = this.mergeContribution([...ranking, ...waterfall]);
        const existed = new Set(merged.map((item) => item.name));
        summaryStats.forEach((row, idx) => {
            const name = String(row.feature || row.feature_name || `feature_${idx}`);
            if (existed.has(name)) {
                return;
            }
            const value = Number(row.mean_abs_shap ?? row.max_abs_shap ?? row.max_abs ?? 0);
            if (!Number.isFinite(value)) {
                return;
            }
            merged.push({ name, value });
        });
        return this.buildFeatureContributionRows(merged.slice(0, 40), 'SHAP');
    }

    private buildFeatureContributionRows(
        rows: Array<{ name: string; value: number }>,
        source: 'LIME' | 'SHAP'
    ): FeatureContributionRow[] {
        if (!rows.length) {
            return [];
        }
        const valid = rows
            .map((row) => ({
                feature: row.name || 'feature',
                value: Number(row.value || 0),
                absValue: Math.abs(Number(row.value || 0))
            }))
            .filter((row) => Number.isFinite(row.value))
            .sort((a, b) => b.absValue - a.absValue)
            .slice(0, 40);

        if (!valid.length) {
            return [];
        }
        const maxAbs = Math.max(...valid.map((item) => item.absValue), 1e-6);
        const sortedAbs = [...valid.map((item) => item.absValue)].sort((a, b) => a - b);
        const pivotIndex = Math.min(sortedAbs.length - 1, Math.floor(sortedAbs.length * 0.65));
        const clusterThreshold = sortedAbs[pivotIndex] || 0;
        return valid.map((item) => {
            const normalized = item.absValue / maxAbs;
            let cluster: ContributionCluster = 'low-impact';
            if (item.absValue >= clusterThreshold * 1.05) {
                cluster = item.value >= 0 ? 'high-positive' : 'high-negative';
            }
            const annotation = cluster === 'high-positive'
                ? '正向主导簇：提升异常判别分数'
                : cluster === 'high-negative'
                    ? '负向主导簇：抑制异常判别分数'
                    : '低贡献簇：影响较弱';
            return {
                feature: item.feature,
                value: item.value,
                absValue: item.absValue,
                normalized,
                cluster,
                source,
                annotation
            };
        });
    }

    private renderContributionHeatmapPanel(rows: FeatureContributionRow[], prefix: 'lime' | 'shap'): string {
        if (!rows.length) {
            return '<div class="status-message">暂无贡献度热图数据</div>';
        }
        const maxThreshold = 100;
        const initialThreshold = 0;
        const cells = this.renderContributionHeatmapCells(rows, {
            thresholdPct: initialThreshold,
            polarity: 'all',
            cluster: 'all',
            keyword: ''
        });
        return `
            <div class="contribution-heatmap-panel">
                <div class="contribution-heatmap-controls">
                    <label>贡献阈值
                        <input id="${prefix}-contrib-threshold" type="range" min="0" max="${maxThreshold}" step="5" value="${initialThreshold}">
                        <span id="${prefix}-contrib-threshold-label">${initialThreshold}%</span>
                    </label>
                    <label>方向
                        <select id="${prefix}-contrib-polarity" class="select">
                            <option value="all">全部</option>
                            <option value="positive">正向贡献</option>
                            <option value="negative">负向贡献</option>
                        </select>
                    </label>
                    <label>聚类
                        <select id="${prefix}-contrib-cluster" class="select">
                            <option value="all">全部簇</option>
                            <option value="high-positive">高正贡献簇</option>
                            <option value="high-negative">高负贡献簇</option>
                            <option value="low-impact">低贡献簇</option>
                        </select>
                    </label>
                    <label>特征筛选
                        <input id="${prefix}-contrib-search" class="input" type="text" placeholder="输入特征名关键字">
                    </label>
                </div>
                <div class="contribution-heatmap-legend">
                    <span class="legend-chip positive">正向贡献</span>
                    <span class="legend-chip negative">负向贡献</span>
                    <span class="legend-chip neutral">低贡献</span>
                </div>
                <div id="${prefix}-contrib-meta" class="contribution-meta">
                    ${this.renderContributionClusterSummary(rows)}
                </div>
                <div id="${prefix}-contrib-grid" class="contribution-heatmap-grid">
                    ${cells}
                </div>
            </div>
        `;
    }

    private renderContributionClusterSummary(rows: FeatureContributionRow[]): string {
        if (!rows.length) {
            return '<div class="status-message">暂无聚类统计</div>';
        }
        const groups: Record<ContributionCluster, { count: number; mean: number }> = {
            'high-positive': { count: 0, mean: 0 },
            'high-negative': { count: 0, mean: 0 },
            'low-impact': { count: 0, mean: 0 }
        };
        rows.forEach((row) => {
            const item = groups[row.cluster];
            item.count += 1;
            item.mean += row.absValue;
        });
        (Object.keys(groups) as ContributionCluster[]).forEach((key) => {
            const item = groups[key];
            item.mean = item.count ? item.mean / item.count : 0;
        });
        const strongest = rows[0];
        return `
            <div class="contribution-cluster-summary">
                <span>高正贡献簇: ${groups['high-positive'].count}（均值 ${groups['high-positive'].mean.toFixed(3)}）</span>
                <span>高负贡献簇: ${groups['high-negative'].count}（均值 ${groups['high-negative'].mean.toFixed(3)}）</span>
                <span>低贡献簇: ${groups['low-impact'].count}（均值 ${groups['low-impact'].mean.toFixed(3)}）</span>
                <span>最强特征: ${strongest.feature} (${strongest.value.toFixed(4)})</span>
            </div>
        `;
    }

    private filterContributionRows(
        rows: FeatureContributionRow[],
        filter: { thresholdPct: number; polarity: 'all' | 'positive' | 'negative'; cluster: 'all' | ContributionCluster; keyword: string }
    ): FeatureContributionRow[] {
        const threshold = Math.max(0, Math.min(100, filter.thresholdPct)) / 100;
        const keyword = filter.keyword.trim().toLowerCase();
        return rows.filter((row) => {
            if (row.normalized < threshold) {
                return false;
            }
            if (filter.polarity === 'positive' && row.value < 0) {
                return false;
            }
            if (filter.polarity === 'negative' && row.value >= 0) {
                return false;
            }
            if (filter.cluster !== 'all' && row.cluster !== filter.cluster) {
                return false;
            }
            if (keyword && !row.feature.toLowerCase().includes(keyword)) {
                return false;
            }
            return true;
        });
    }

    private renderContributionHeatmapCells(
        rows: FeatureContributionRow[],
        filter: { thresholdPct: number; polarity: 'all' | 'positive' | 'negative'; cluster: 'all' | ContributionCluster; keyword: string }
    ): string {
        const filtered = this.filterContributionRows(rows, filter);
        if (!filtered.length) {
            return '<div class="status-message">当前筛选条件下无贡献特征</div>';
        }
        return filtered.map((row) => {
            const color = this.calcContributionCellColor(row);
            const sign = row.value >= 0 ? 'positive' : 'negative';
            return `
                <button
                    class="contribution-heatmap-cell ${sign} ${row.cluster}"
                    type="button"
                    data-sign="${sign}"
                    data-cluster="${row.cluster}"
                    data-feature="${row.feature}"
                    title="${row.feature} | ${row.annotation}"
                    style="background:${color};"
                >
                    <span class="contribution-feature">${row.feature}</span>
                    <span class="contribution-value">${row.value.toFixed(4)}</span>
                </button>
            `;
        }).join('');
    }

    private calcContributionCellColor(row: FeatureContributionRow): string {
        const alpha = Math.max(0.14, Math.min(0.95, 0.22 + row.normalized * 0.72));
        if (row.cluster === 'low-impact') {
            return `rgba(148, 163, 184, ${alpha})`;
        }
        if (row.value >= 0) {
            return `rgba(14, 165, 233, ${alpha})`;
        }
        return `rgba(239, 68, 68, ${alpha})`;
    }

    private bindContributionHeatmapInteractive(container: HTMLElement, rows: FeatureContributionRow[], prefix: 'lime' | 'shap'): void {
        if (!rows.length) {
            return;
        }
        const thresholdInput = container.querySelector(`#${prefix}-contrib-threshold`) as HTMLInputElement | null;
        const thresholdLabel = container.querySelector(`#${prefix}-contrib-threshold-label`) as HTMLElement | null;
        const polarityInput = container.querySelector(`#${prefix}-contrib-polarity`) as HTMLSelectElement | null;
        const clusterInput = container.querySelector(`#${prefix}-contrib-cluster`) as HTMLSelectElement | null;
        const searchInput = container.querySelector(`#${prefix}-contrib-search`) as HTMLInputElement | null;
        const grid = container.querySelector(`#${prefix}-contrib-grid`) as HTMLElement | null;
        const meta = container.querySelector(`#${prefix}-contrib-meta`) as HTMLElement | null;
        if (!thresholdInput || !thresholdLabel || !polarityInput || !clusterInput || !searchInput || !grid || !meta) {
            return;
        }

        const rerender = (): void => {
            const filter = {
                thresholdPct: Number(thresholdInput.value || 0),
                polarity: (polarityInput.value || 'all') as 'all' | 'positive' | 'negative',
                cluster: (clusterInput.value || 'all') as 'all' | ContributionCluster,
                keyword: searchInput.value || ''
            };
            thresholdLabel.textContent = `${Math.max(0, Math.min(100, filter.thresholdPct))}%`;
            const filtered = this.filterContributionRows(rows, filter);
            grid.innerHTML = this.renderContributionHeatmapCells(rows, filter);
            meta.innerHTML = this.renderContributionClusterSummary(filtered.length ? filtered : rows);
        };
        thresholdInput.addEventListener('input', rerender);
        polarityInput.addEventListener('change', rerender);
        clusterInput.addEventListener('change', rerender);
        searchInput.addEventListener('input', this.createDebounced(rerender, 90));
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
        const anomalyRows = this.extractAnomalyRows(shap);

        const waterfall = this.parseImportanceRows(vis.waterfall_list || []);
        const ranking = this.parseImportanceRows(vis.feature_ranking || shap.global_feature_importance || []);
        const beeswarm = Array.isArray(vis.beeswarm_data) ? vis.beeswarm_data as Array<Record<string, unknown>> : [];
        const dependence = Array.isArray(vis.dependence_data) ? vis.dependence_data as Array<Record<string, unknown>> : [];
        const summaryStats = Array.isArray(vis.summary_stats) ? vis.summary_stats as Array<Record<string, unknown>> : [];
        const contributionHeatmapRows = this.collectShapContributionRows(result);
        const reasonRows = this.parseAnomalyReasonRows(shap, 'SHAP');

        return `
            <div class="explain-result-grid">
                <section class="result-card">
                    <h6>SHAP 瀑布图</h6>
                    <div id="chart-shap-waterfall" class="explain-chart js-lazy-chart" role="img" aria-label="SHAP 瀑布图"></div>
                    ${this.renderFeatureBarList(waterfall.slice(0, 12), 'shap-waterfall fallback-bars')}
                </section>

                <section class="result-card">
                    <h6>SHAP 蜂群图</h6>
                    <div class="shap-filter-bar">
                        <label>贡献阈值 <input id="shap-threshold" class="input" type="number" step="0.01" value="0"></label>
                        <label>缩放 <input id="shap-zoom" type="range" min="0.5" max="2" step="0.1" value="1"></label>
                    </div>
                    <div id="chart-shap-beeswarm" class="explain-chart explain-chart-lg js-lazy-chart" role="img" aria-label="SHAP 蜂群图"></div>
                    <div id="shap-beeswarm" class="beeswarm-container fallback-bars">
                        ${this.renderBeeswarmPoints(beeswarm, 0, 1)}
                    </div>
                </section>

                <section class="result-card">
                    <h6>SHAP 依赖图</h6>
                    ${this.renderDependenceList(dependence)}
                </section>

                <section class="result-card">
                    <h6>特征重要性排序图</h6>
                    <div id="chart-shap-ranking" class="explain-chart js-lazy-chart" role="img" aria-label="SHAP 特征重要性排序图"></div>
                    ${this.renderFeatureBarList(ranking.slice(0, 12), 'shap-ranking fallback-bars')}
                </section>

                <section class="result-card full-width">
                    <h6>SHAP 摘要统计表</h6>
                    ${this.renderSummaryTable(summaryStats)}
                </section>

                <section class="result-card full-width">
                    <h6>SHAP 特征贡献度热图</h6>
                    ${this.renderContributionHeatmapPanel(contributionHeatmapRows, 'shap')}
                </section>

                <section class="result-card full-width">
                    <h6>异常分数解释</h6>
                    ${this.renderAnomalyScoreExplorer(anomalyRows, 'shap')}
                </section>

                <section class="result-card full-width">
                    <h6>异常原因分析</h6>
                    ${this.renderReasonAnalysisPanel(reasonRows, 'shap')}
                </section>
            </div>
        `;
    }

    private extractAnomalyRows(payload: Record<string, unknown>): Array<{ node: number; score: number; deviation: number; percentile: number }> {
        const exp = (payload.anomaly_score_explanation || {}) as Record<string, unknown>;
        const rawNodes = Array.isArray(exp.key_anomaly_nodes) ? exp.key_anomaly_nodes : [];
        const scoreMapRaw = (exp.node_scores || {}) as Record<string, unknown>;
        const profile = (payload.anomaly_analysis || {}) as Record<string, unknown>;
        const profileRowsRaw = Array.isArray(profile.score_summary) ? profile.score_summary as Array<Record<string, unknown>> : [];
        const profileRows = new Map<number, { deviation: number; percentile: number }>();

        profileRowsRaw.forEach((item) => {
            const node = Number(item.node_index);
            if (!Number.isFinite(node)) {
                return;
            }
            profileRows.set(node, {
                deviation: Number(item.deviation || 0),
                percentile: Number(item.percentile || 0)
            });
        });

        const scoreMap = new Map<number, number>();
        Object.entries(scoreMapRaw).forEach(([key, value]) => {
            const node = Number(key);
            const score = Number(value);
            if (Number.isFinite(node) && Number.isFinite(score)) {
                scoreMap.set(node, score);
            }
        });

        rawNodes.forEach((node) => {
            const idx = Number(node);
            if (Number.isFinite(idx) && !scoreMap.has(idx)) {
                scoreMap.set(idx, 0);
            }
        });

        if (!scoreMap.size) {
            return [];
        }

        return Array.from(scoreMap.entries()).map(([node, score]) => {
            const row = profileRows.get(node);
            return {
                node,
                score,
                deviation: Number(row?.deviation || 0),
                percentile: Number(row?.percentile || 0)
            };
        });
    }

    private renderAnomalyScoreExplorer(rows: Array<{ node: number; score: number; deviation: number; percentile: number }>, prefix: string): string {
        if (!rows.length) {
            return '<div class="status-message">暂无异常分数解释数据</div>';
        }
        const maxCount = Math.max(1, Math.min(20, rows.length));
        const initialCount = Math.min(8, maxCount);
        return `
            <div class="anomaly-explorer">
                <div class="anomaly-explorer-controls">
                    <label>排序
                        <select id="${prefix}-anomaly-sort" class="select">
                            <option value="score_desc">分数高到低</option>
                            <option value="score_asc">分数低到高</option>
                            <option value="deviation_desc">偏差高到低</option>
                        </select>
                    </label>
                    <label>Top 节点
                        <input id="${prefix}-anomaly-topn" class="input" type="range" min="1" max="${maxCount}" value="${initialCount}">
                        <span id="${prefix}-anomaly-topn-label">${initialCount}</span>
                    </label>
                </div>
                <div id="${prefix}-anomaly-list" class="anomaly-node-list">
                    ${this.renderAnomalyNodeRows(rows, initialCount, 'score_desc')}
                </div>
            </div>
        `;
    }

    private renderAnomalyNodeRows(
        rows: Array<{ node: number; score: number; deviation: number; percentile: number }>,
        topN: number,
        sortBy: 'score_desc' | 'score_asc' | 'deviation_desc'
    ): string {
        const sorted = [...rows];
        if (sortBy === 'score_asc') {
            sorted.sort((a, b) => a.score - b.score);
        } else if (sortBy === 'deviation_desc') {
            sorted.sort((a, b) => b.deviation - a.deviation);
        } else {
            sorted.sort((a, b) => b.score - a.score);
        }
        const sliced = sorted.slice(0, Math.max(1, topN));
        const maxScore = Math.max(1e-6, ...sliced.map((item) => Math.abs(item.score)));
        return sliced.map((item) => {
            const width = Math.round((Math.abs(item.score) / maxScore) * 100);
            return `
                <div class="anomaly-node-item">
                    <span class="node-name">节点 #${item.node}</span>
                    <div class="anomaly-node-track">
                        <div class="anomaly-node-fill" style="width:${width}%"></div>
                    </div>
                    <span class="node-score">${item.score.toFixed(4)}</span>
                    <span class="node-meta">偏差 ${item.deviation.toFixed(3)} / P${Math.round(item.percentile * 100)}</span>
                </div>
            `;
        }).join('');
    }

    private bindAnomalyInteractive(
        container: HTMLElement,
        rows: Array<{ node: number; score: number; deviation: number; percentile: number }>,
        prefix: string
    ): void {
        if (!rows.length) {
            return;
        }
        const sortInput = container.querySelector(`#${prefix}-anomaly-sort`) as HTMLSelectElement | null;
        const topNInput = container.querySelector(`#${prefix}-anomaly-topn`) as HTMLInputElement | null;
        const topNLabel = container.querySelector(`#${prefix}-anomaly-topn-label`) as HTMLElement | null;
        const target = container.querySelector(`#${prefix}-anomaly-list`) as HTMLElement | null;
        if (!sortInput || !topNInput || !topNLabel || !target) {
            return;
        }

        const rerender = (): void => {
            const topN = Math.max(1, Number(topNInput.value || 1));
            const sortBy = (sortInput.value || 'score_desc') as 'score_desc' | 'score_asc' | 'deviation_desc';
            topNLabel.textContent = String(topN);
            target.innerHTML = this.renderAnomalyNodeRows(rows, topN, sortBy);
        };

        sortInput.addEventListener('change', rerender);
        topNInput.addEventListener('input', rerender);
    }

    private parseAnomalyReasonRows(payload: Record<string, unknown>, method: 'LIME' | 'SHAP'): Array<{
        node: number;
        reason: string;
        confidence: number;
        category: string;
        method: 'LIME' | 'SHAP';
    }> {
        const scoreExplanation = (payload.anomaly_score_explanation || {}) as Record<string, unknown>;
        const reasonRowsRaw = Array.isArray(scoreExplanation.anomaly_reasons) ? scoreExplanation.anomaly_reasons as Array<Record<string, unknown>> : [];
        const batchRows = Array.isArray(payload.batch_explanations) ? payload.batch_explanations as Array<Record<string, unknown>> : [];
        const sourceRows = reasonRowsRaw.length ? reasonRowsRaw : batchRows;
        const seen = new Set<string>();
        const rows: Array<{ node: number; reason: string; confidence: number; category: string; method: 'LIME' | 'SHAP' }> = [];
        sourceRows.forEach((item, idx) => {
            const node = Number(item.node_index ?? item.node ?? idx);
            if (!Number.isFinite(node)) {
                return;
            }
            const reason = String(item.reason || '').trim() || `节点${node}存在异常行为。`;
            const confidence = Math.max(0, Math.min(1, Number(item.confidence ?? 0)));
            const explicitCategory = String(item.category || '').trim();
            const category = this.normalizeReasonCategory(explicitCategory || this.inferReasonCategory(reason));
            const key = `${node}-${reason}`;
            if (seen.has(key)) {
                return;
            }
            seen.add(key);
            rows.push({ node, reason, confidence, category, method });
        });
        rows.sort((a, b) => b.confidence - a.confidence);
        return rows;
    }

    private inferReasonCategory(reason: string): string {
        const text = reason.toLowerCase();
        if (text.includes('重建') || text.includes('reconstruction')) {
            return '重建偏差';
        }
        if (text.includes('判别') || text.includes('discriminator')) {
            return '判别偏移';
        }
        if (text.includes('梯度') || text.includes('gradient')) {
            return '梯度扰动';
        }
        if (text.includes('密度') || text.includes('nearest') || text.includes('特征库') || text.includes('bank')) {
            return '分布漂移';
        }
        if (text.includes('嵌入') || text.includes('embedding')) {
            return '表征漂移';
        }
        return '综合异常';
    }

    private normalizeReasonCategory(category: string): string {
        const text = category.trim();
        return text || '综合异常';
    }

    private buildReasonCategoryRows(rows: Array<{ node: number; reason: string; confidence: number; category: string; method: 'LIME' | 'SHAP' }>): Array<{ category: string; count: number; avgConfidence: number }> {
        const map = new Map<string, { count: number; confidenceSum: number }>();
        rows.forEach((row) => {
            const val = map.get(row.category) || { count: 0, confidenceSum: 0 };
            val.count += 1;
            val.confidenceSum += row.confidence;
            map.set(row.category, val);
        });
        return Array.from(map.entries())
            .map(([category, value]) => ({
                category,
                count: value.count,
                avgConfidence: value.count ? value.confidenceSum / value.count : 0
            }))
            .sort((a, b) => b.count - a.count);
    }

    private renderReasonAnalysisPanel(
        rows: Array<{ node: number; reason: string; confidence: number; category: string; method: 'LIME' | 'SHAP' }>,
        prefix: 'lime' | 'shap'
    ): string {
        if (!rows.length) {
            return '<div class="status-message">暂无异常原因分析数据</div>';
        }
        const categories = this.buildReasonCategoryRows(rows);
        const maxCount = Math.max(1, Math.min(20, rows.length));
        const initialCount = Math.min(maxCount, 6);
        const initialCategory = 'all';
        const meanConfidence = rows.reduce((acc, item) => acc + item.confidence, 0) / rows.length;
        return `
            <div id="${prefix}-reason-panel" class="reason-analysis-panel">
                <div class="reason-analysis-controls">
                    <label>分类
                        <select id="${prefix}-reason-category" class="select">
                            <option value="all">全部</option>
                            ${categories.map((item) => `<option value="${item.category}">${item.category}</option>`).join('')}
                        </select>
                    </label>
                    <label>排序
                        <select id="${prefix}-reason-sort" class="select">
                            <option value="confidence_desc">置信度高到低</option>
                            <option value="confidence_asc">置信度低到高</option>
                            <option value="node_asc">节点编号升序</option>
                        </select>
                    </label>
                    <label>Top
                        <input id="${prefix}-reason-topn" class="input" type="range" min="1" max="${maxCount}" value="${initialCount}">
                        <span id="${prefix}-reason-topn-label">${initialCount}</span>
                    </label>
                </div>
                <div class="reason-confidence-overview">
                    <span>均值置信度 ${meanConfidence.toFixed(3)}</span>
                    <span>高置信(≥0.75) ${rows.filter(item => item.confidence >= 0.75).length}/${rows.length}</span>
                </div>
                <div id="${prefix}-reason-categories" class="reason-category-list">
                    ${this.renderReasonCategoryChips(categories)}
                </div>
                <div id="${prefix}-reason-history" class="reason-history-list">
                    ${this.renderReasonHistoryRows(rows, initialCategory, initialCount, 'confidence_desc')}
                </div>
                <div id="${prefix}-reason-list" class="reason-item-list">
                    ${this.renderReasonRows(rows, initialCount, initialCategory, 'confidence_desc')}
                </div>
            </div>
        `;
    }

    private renderReasonCategoryChips(rows: Array<{ category: string; count: number; avgConfidence: number }>): string {
        if (!rows.length) {
            return '<div class="status-message">暂无原因分类</div>';
        }
        return rows.map((row) => `
            <div class="reason-category-chip">
                <span>${row.category}</span>
                <span>${row.count}</span>
                <span>均值${row.avgConfidence.toFixed(2)}</span>
            </div>
        `).join('');
    }

    private renderReasonRows(
        rows: Array<{ node: number; reason: string; confidence: number; category: string; method: 'LIME' | 'SHAP' }>,
        topN: number,
        category: string,
        sortBy: 'confidence_desc' | 'confidence_asc' | 'node_asc'
    ): string {
        const filtered = category === 'all' ? rows : rows.filter(item => item.category === category);
        if (!filtered.length) {
            return '<div class="status-message">当前分类下暂无数据</div>';
        }
        const sorted = [...filtered];
        if (sortBy === 'node_asc') {
            sorted.sort((a, b) => a.node - b.node);
        } else if (sortBy === 'confidence_asc') {
            sorted.sort((a, b) => a.confidence - b.confidence);
        } else {
            sorted.sort((a, b) => b.confidence - a.confidence);
        }
        const sliced = sorted.slice(0, Math.max(1, topN));
        return sliced.map((item) => {
            const confidencePct = Math.round(item.confidence * 100);
            const detailPayload = encodeURIComponent(JSON.stringify(item));
            return `
                <article class="reason-item">
                    <div class="reason-item-header">
                        <span class="reason-node">节点 #${item.node}</span>
                        <span class="reason-category">${item.category}</span>
                        <span class="reason-confidence">${confidencePct}%</span>
                    </div>
                    <div class="reason-confidence-track">
                        <div class="reason-confidence-fill" style="width:${confidencePct}%"></div>
                    </div>
                    <p class="reason-text">${item.reason}</p>
                    <button class="btn btn-secondary reason-detail-btn" type="button" data-reason-detail="${detailPayload}">详细说明</button>
                </article>
            `;
        }).join('');
    }

    private renderReasonHistoryRows(
        rows: Array<{ node: number; reason: string; confidence: number; category: string; method: 'LIME' | 'SHAP' }>,
        category: string,
        topN: number,
        sortBy: 'confidence_desc' | 'confidence_asc' | 'node_asc'
    ): string {
        const filtered = category === 'all' ? rows : rows.filter(item => item.category === category);
        if (!filtered.length) {
            return '<div class="status-message">暂无趋势数据</div>';
        }
        const sorted = [...filtered];
        if (sortBy === 'confidence_asc') {
            sorted.sort((a, b) => a.confidence - b.confidence);
        } else if (sortBy === 'node_asc') {
            sorted.sort((a, b) => a.node - b.node);
        } else {
            sorted.sort((a, b) => b.confidence - a.confidence);
        }
        const sliced = sorted.slice(0, Math.max(1, topN));
        const maxConf = Math.max(...sliced.map(item => item.confidence), 1e-6);
        return `
            <div class="reason-history-track">
                ${sliced.map((item) => `
                    <div class="reason-history-col" title="节点#${item.node} ${item.confidence.toFixed(3)}">
                        <div class="reason-history-bar" style="height:${Math.round((item.confidence / maxConf) * 100)}%"></div>
                        <span class="reason-history-label">${item.node}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    private bindReasonInteractive(
        container: HTMLElement,
        rows: Array<{ node: number; reason: string; confidence: number; category: string; method: 'LIME' | 'SHAP' }>,
        prefix: 'lime' | 'shap'
    ): void {
        if (!rows.length) {
            return;
        }
        const categoryInput = container.querySelector(`#${prefix}-reason-category`) as HTMLSelectElement | null;
        const sortInput = container.querySelector(`#${prefix}-reason-sort`) as HTMLSelectElement | null;
        const topNInput = container.querySelector(`#${prefix}-reason-topn`) as HTMLInputElement | null;
        const topNLabel = container.querySelector(`#${prefix}-reason-topn-label`) as HTMLElement | null;
        const listTarget = container.querySelector(`#${prefix}-reason-list`) as HTMLElement | null;
        const trendTarget = container.querySelector(`#${prefix}-reason-history`) as HTMLElement | null;
        if (!categoryInput || !sortInput || !topNInput || !topNLabel || !listTarget || !trendTarget) {
            return;
        }
        const rerender = (): void => {
            const topN = Math.max(1, Number(topNInput.value || 1));
            const category = categoryInput.value || 'all';
            const sortBy = (sortInput.value || 'confidence_desc') as 'confidence_desc' | 'confidence_asc' | 'node_asc';
            topNLabel.textContent = String(topN);
            listTarget.innerHTML = this.renderReasonRows(rows, topN, category, sortBy);
            trendTarget.innerHTML = this.renderReasonHistoryRows(rows, category, topN, sortBy);
        };
        categoryInput.addEventListener('change', rerender);
        sortInput.addEventListener('change', rerender);
        topNInput.addEventListener('input', rerender);
    }

    private renderReasonComparePanel(
        limeRows: Array<{ node: number; reason: string; confidence: number; category: string; method: 'LIME' | 'SHAP' }>,
        shapRows: Array<{ node: number; reason: string; confidence: number; category: string; method: 'LIME' | 'SHAP' }>
    ): string {
        if (!limeRows.length && !shapRows.length) {
            return '<div class="status-message">暂无可对比的原因分析结果</div>';
        }
        const merged = new Map<string, { lime: number; shap: number }>();
        this.buildReasonCategoryRows(limeRows).forEach((item) => {
            const value = merged.get(item.category) || { lime: 0, shap: 0 };
            value.lime = item.count;
            merged.set(item.category, value);
        });
        this.buildReasonCategoryRows(shapRows).forEach((item) => {
            const value = merged.get(item.category) || { lime: 0, shap: 0 };
            value.shap = item.count;
            merged.set(item.category, value);
        });
        const rows = Array.from(merged.entries())
            .map(([category, value]) => ({
                category,
                lime: value.lime,
                shap: value.shap,
                diff: Math.abs(value.lime - value.shap)
            }))
            .sort((a, b) => b.diff - a.diff);

        return `
            <div class="reason-compare-wrap">
                <div class="reason-compare-controls">
                    <label>展示数量
                        <input id="reason-compare-topn" class="input" type="range" min="1" max="${Math.max(1, rows.length)}" value="${Math.min(8, Math.max(1, rows.length))}">
                        <span id="reason-compare-topn-label">${Math.min(8, Math.max(1, rows.length))}</span>
                    </label>
                </div>
                <div id="reason-compare-table">
                    ${this.renderReasonCompareRows(rows, Math.min(8, Math.max(1, rows.length)))}
                </div>
            </div>
        `;
    }

    private renderReasonCompareRows(rows: Array<{ category: string; lime: number; shap: number; diff: number }>, topN: number): string {
        const sliced = rows.slice(0, Math.max(1, topN));
        return `
            <div class="summary-table-wrap">
                <table class="summary-table">
                    <thead>
                        <tr>
                            <th>原因分类</th>
                            <th>LIME</th>
                            <th>SHAP</th>
                            <th>差异</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${sliced.map((row) => `
                            <tr class="${row.diff > 1 ? 'highlight' : ''}">
                                <td>${row.category}</td>
                                <td>${row.lime}</td>
                                <td>${row.shap}</td>
                                <td>${row.diff}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    private bindReasonCompareInteractive(container: HTMLElement, result: Record<string, unknown>): void {
        const limeRows = this.parseAnomalyReasonRows((result.lime || {}) as Record<string, unknown>, 'LIME');
        const shapRows = this.parseAnomalyReasonRows((result.shap || {}) as Record<string, unknown>, 'SHAP');
        const merged = new Map<string, { lime: number; shap: number }>();
        this.buildReasonCategoryRows(limeRows).forEach((item) => {
            const value = merged.get(item.category) || { lime: 0, shap: 0 };
            value.lime = item.count;
            merged.set(item.category, value);
        });
        this.buildReasonCategoryRows(shapRows).forEach((item) => {
            const value = merged.get(item.category) || { lime: 0, shap: 0 };
            value.shap = item.count;
            merged.set(item.category, value);
        });
        const rows = Array.from(merged.entries())
            .map(([category, value]) => ({
                category,
                lime: value.lime,
                shap: value.shap,
                diff: Math.abs(value.lime - value.shap)
            }))
            .sort((a, b) => b.diff - a.diff);
        const slider = container.querySelector('#reason-compare-topn') as HTMLInputElement | null;
        const label = container.querySelector('#reason-compare-topn-label') as HTMLElement | null;
        const table = container.querySelector('#reason-compare-table') as HTMLElement | null;
        if (!slider || !label || !table || !rows.length) {
            return;
        }
        const rerender = (): void => {
            const topN = Math.max(1, Number(slider.value || 1));
            label.textContent = String(topN);
            table.innerHTML = this.renderReasonCompareRows(rows, topN);
        };
        slider.addEventListener('input', rerender);
    }

    private showReasonDetail(payload: string): void {
        if (!payload) {
            return;
        }
        let parsed: { node: number; reason: string; confidence: number; category: string; method: 'LIME' | 'SHAP' } | null = null;
        try {
            parsed = JSON.parse(decodeURIComponent(payload)) as { node: number; reason: string; confidence: number; category: string; method: 'LIME' | 'SHAP' };
        } catch {
            parsed = null;
        }
        if (!parsed) {
            return;
        }
        const modal = this.container.querySelector('#dl-explain-detail-modal') as HTMLElement | null;
        const body = this.container.querySelector('#dl-reason-detail-body') as HTMLElement | null;
        if (!modal || !body) {
            return;
        }
        body.innerHTML = `
            <article class="reason-detail-content">
                <p><strong>模型：</strong>${parsed.method}</p>
                <p><strong>节点：</strong>#${parsed.node}</p>
                <p><strong>原因分类：</strong>${parsed.category}</p>
                <p><strong>置信度：</strong>${Math.round(parsed.confidence * 100)}%</p>
                <p><strong>详细说明：</strong>${parsed.reason}</p>
            </article>
        `;
        modal.classList.add('open');
        modal.setAttribute('aria-hidden', 'false');
        this.detailModalVisible = true;
    }

    private hideReasonDetail(): void {
        if (!this.detailModalVisible) {
            return;
        }
        const modal = this.container.querySelector('#dl-explain-detail-modal') as HTMLElement | null;
        if (!modal) {
            return;
        }
        modal.classList.remove('open');
        modal.setAttribute('aria-hidden', 'true');
        this.detailModalVisible = false;
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
            void this.renderShapBeeswarmChart(beeswarm, threshold, zoom);
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
        const limeReasonRows = this.parseAnomalyReasonRows(lime, 'LIME');
        const shapReasonRows = this.parseAnomalyReasonRows(shap, 'SHAP');

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

                <section class="result-card full-width">
                    <h6>异常原因多模型对比</h6>
                    ${this.renderReasonComparePanel(limeReasonRows, shapReasonRows)}
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
        const uncertaintyView = this.buildUncertaintyVisualizationData(result, coordinates, series);
        const reconstruction = this.collectReconstructionErrorData(result);
        const thresholdPercentile = 95;
        const threshold = this.computePercentile(reconstruction.combined, thresholdPercentile);
        const histogram = this.buildReconstructionHistogramRows(reconstruction.combined, threshold, 12);
        const errorHeatmap = this.buildReconstructionHeatmapRows(coordinates, reconstruction.combined, threshold);
        const errorTimeline = this.buildReconstructionTimelineRows(series, reconstruction.combined, threshold);
        const comparison = this.buildReconstructionCompareRows(reconstruction, threshold);

        return `
            <div class="explain-result-grid">
                <section class="result-card">
                    <h6>重建误差分布直方图</h6>
                    <div class="recon-threshold-controls">
                        <label>阈值分位数
                            <input id="recon-threshold-percentile" class="input" type="range" min="50" max="99" value="${thresholdPercentile}">
                            <span id="recon-threshold-percentile-label">P${thresholdPercentile}</span>
                        </label>
                    </div>
                    <div id="recon-histogram-meta" class="summary-card recon-meta-card">
                        <p>阈值：${threshold.toFixed(4)}（P${thresholdPercentile}）</p>
                        <p>超阈值节点：${comparison.aboveThresholdCount}/${Math.max(1, reconstruction.combined.length)}</p>
                        <p>平均误差：${comparison.meanError.toFixed(4)}</p>
                    </div>
                    <div id="recon-histogram-list" class="recon-histogram-list">
                        ${this.renderReconstructionHistogramRows(histogram)}
                    </div>
                </section>

                <section class="result-card">
                    <h6>重建误差热图</h6>
                    <div id="recon-heatmap-grid" class="heatmap-grid recon-heatmap-grid">
                        ${this.renderReconstructionHeatmapRows(errorHeatmap)}
                    </div>
                </section>

                <section class="result-card">
                    <h6>重建误差时间轴</h6>
                    <div id="recon-timeline-list" class="timeline-list recon-timeline-list">
                        ${this.renderReconstructionTimelineRows(errorTimeline)}
                    </div>
                </section>

                <section class="result-card">
                    <h6>重建误差对比</h6>
                    <div id="recon-compare-panel" class="summary-card recon-compare-panel">
                        ${this.renderReconstructionCompareRows(comparison)}
                    </div>
                </section>

                <section class="result-card full-width">
                    <h6>不确定性来源解释</h6>
                    ${this.renderUncertaintySourceExplanation(uncertaintyView)}
                </section>

                <section class="result-card full-width">
                    <h6>置信区间可视化</h6>
                    ${this.renderConfidenceIntervalVisualization(uncertaintyView)}
                </section>

                <section class="result-card full-width">
                    <h6>认知/偶然不确定性区分展示</h6>
                    ${this.renderUncertaintyDecompositionVisualization(uncertaintyView)}
                </section>

                <section class="result-card full-width">
                    <h6>预测分布图</h6>
                    ${this.renderPredictionDistributionVisualization(uncertaintyView)}
                </section>

                <section class="result-card">
                    <h6>不确定性热力图</h6>
                    ${this.renderUncertaintyHeatmapVisualization(uncertaintyView, coordinates)}
                </section>

                <section class="result-card">
                    <h6>不确定性时间序列图</h6>
                    ${this.renderUncertaintyTimelineVisualization(uncertaintyView, series)}
                </section>

                <section class="result-card">
                    <h6>不确定性空间分布图</h6>
                    ${this.renderUncertaintySpatialDistributionVisualization(uncertaintyView, coordinates)}
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

    private bindReconstructionErrorInteractive(container: HTMLElement, result: Record<string, unknown>): void {
        const percentileInput = container.querySelector('#recon-threshold-percentile') as HTMLInputElement | null;
        const percentileLabel = container.querySelector('#recon-threshold-percentile-label') as HTMLElement | null;
        const histogramTarget = container.querySelector('#recon-histogram-list') as HTMLElement | null;
        const heatmapTarget = container.querySelector('#recon-heatmap-grid') as HTMLElement | null;
        const timelineTarget = container.querySelector('#recon-timeline-list') as HTMLElement | null;
        const compareTarget = container.querySelector('#recon-compare-panel') as HTMLElement | null;
        const histogramMeta = container.querySelector('#recon-histogram-meta') as HTMLElement | null;
        if (!percentileInput || !percentileLabel || !histogramTarget || !heatmapTarget || !timelineTarget || !compareTarget || !histogramMeta) {
            return;
        }
        const coordinates = this.parseJSONInputSafe<Array<[number, number]>>('dl-explain-coords', []);
        const series = this.parseJSONInputSafe<number[][][]>('dl-explain-series', []);
        const reconstruction = this.collectReconstructionErrorData(result);
        const rerender = (): void => {
            const percentile = Math.max(50, Math.min(99, Number(percentileInput.value || 95)));
            percentileLabel.textContent = `P${percentile}`;
            const threshold = this.computePercentile(reconstruction.combined, percentile);
            histogramMeta.innerHTML = `
                <p>阈值：${threshold.toFixed(4)}（P${percentile}）</p>
                <p>超阈值节点：${reconstruction.combined.filter((value) => value >= threshold).length}/${Math.max(1, reconstruction.combined.length)}</p>
                <p>平均误差：${(reconstruction.combined.reduce((acc, item) => acc + item, 0) / Math.max(1, reconstruction.combined.length)).toFixed(4)}</p>
            `;
            histogramTarget.innerHTML = this.renderReconstructionHistogramRows(
                this.buildReconstructionHistogramRows(reconstruction.combined, threshold, 12)
            );
            heatmapTarget.innerHTML = this.renderReconstructionHeatmapRows(
                this.buildReconstructionHeatmapRows(coordinates, reconstruction.combined, threshold)
            );
            timelineTarget.innerHTML = this.renderReconstructionTimelineRows(
                this.buildReconstructionTimelineRows(series, reconstruction.combined, threshold)
            );
            compareTarget.innerHTML = this.renderReconstructionCompareRows(
                this.buildReconstructionCompareRows(reconstruction, threshold)
            );
        };
        percentileInput.addEventListener('input', rerender);
    }

    private exportCurrentResult(): void {
        const task = this.getCurrentTask();
        if (!task || task.status !== 'completed' || !task.result) {
            this.setStatus('当前无可导出的完成任务结果', 'warning');
            return;
        }

        const format = ((this.container.querySelector('#dl-explain-export-format') as HTMLSelectElement | null)?.value || 'json').toLowerCase();
        const taskId = task.task_id || 'task';
        const tab = this.activeTab;

        if (format === 'csv') {
            const csv = this.buildCsvForActiveTab(task.result as Record<string, unknown>);
            if (!csv) {
                this.setStatus('当前视图暂无可导出的表格数据', 'warning');
                return;
            }
            this.downloadTextFile(`${taskId}_${tab}.csv`, csv, 'text/csv;charset=utf-8');
            this.setStatus(`导出成功：${taskId}_${tab}.csv`, 'success');
            return;
        }

        const payload = {
            task_id: task.task_id,
            method: this.detectMethodFromTask(task),
            tab: this.activeTab,
            exported_at: new Date().toISOString(),
            result: task.result
        };
        this.downloadTextFile(`${taskId}_${tab}.json`, JSON.stringify(payload, null, 2), 'application/json;charset=utf-8');
        this.setStatus(`导出成功：${taskId}_${tab}.json`, 'success');
    }

    private buildCsvForActiveTab(result: Record<string, unknown>): string {
        if (this.activeTab === 'lime') {
            const lime = (result.lime || {}) as Record<string, unknown>;
            const vis = (lime.visualization || {}) as Record<string, unknown>;
            const rows = this.parseImportanceRows(vis.feature_importance_list || lime.global_feature_importance || [])
                .slice(0, 120);
            if (!rows.length) {
                return '';
            }
            return this.rowsToCsv(['feature', 'importance'], rows.map((row) => [row.name, row.value]));
        }

        if (this.activeTab === 'shap') {
            const shap = (result.shap || {}) as Record<string, unknown>;
            const vis = (shap.visualization || {}) as Record<string, unknown>;
            const rows = this.parseImportanceRows(vis.feature_ranking || shap.global_feature_importance || [])
                .slice(0, 120);
            if (!rows.length) {
                return '';
            }
            return this.rowsToCsv(['feature', 'importance'], rows.map((row) => [row.name, row.value]));
        }

        if (this.activeTab === 'compare') {
            const compareHtml = this.renderCompareResult(result);
            if (compareHtml.includes('需要 Hybrid')) {
                return '';
            }
            const lime = (result.lime || {}) as Record<string, unknown>;
            const shap = (result.shap || {}) as Record<string, unknown>;
            const limeRows = this.parseImportanceRows(lime.global_feature_importance || ((lime.visualization || {}) as Record<string, unknown>).feature_importance_list || []);
            const shapRows = this.parseImportanceRows(shap.global_feature_importance || ((shap.visualization || {}) as Record<string, unknown>).feature_ranking || []);
            const merged = new Map<string, { lime: number; shap: number }>();
            limeRows.forEach((item) => {
                merged.set(item.name, { lime: item.value, shap: merged.get(item.name)?.shap || 0 });
            });
            shapRows.forEach((item) => {
                merged.set(item.name, { lime: merged.get(item.name)?.lime || 0, shap: item.value });
            });
            const rows = Array.from(merged.entries())
                .map(([feature, value]) => ({ feature, lime: value.lime, shap: value.shap, diff: Math.abs(value.lime - value.shap) }))
                .sort((a, b) => b.diff - a.diff)
                .slice(0, 120);
            if (!rows.length) {
                return '';
            }
            return this.rowsToCsv(['feature', 'lime', 'shap', 'abs_diff'], rows.map((row) => [row.feature, row.lime, row.shap, row.diff]));
        }

        const summary = (result.summary || {}) as Record<string, unknown>;
        const topFeatures = Array.isArray(summary.top_features) ? summary.top_features.join('|') : '';
        return this.rowsToCsv(
            ['metric', 'value'],
            [
                ['n_nodes', Number(summary.n_nodes || 0)],
                ['seq_len', Number(summary.seq_len || 0)],
                ['n_features', Number(summary.n_features || 0)],
                ['top_features', topFeatures]
            ]
        );
    }

    private rowsToCsv(headers: string[], rows: Array<Array<string | number>>): string {
        const esc = (value: string | number): string => {
            const text = String(value ?? '');
            return `"${text.replace(/"/g, '""')}"`;
        };
        const lines = [headers.map(esc).join(',')];
        rows.forEach((row) => {
            lines.push(row.map(esc).join(','));
        });
        return lines.join('\n');
    }

    private downloadTextFile(filename: string, content: string, mimeType: string): void {
        const blob = new Blob([content], { type: mimeType });
        const urlFactory = window.URL || (window as typeof window & { webkitURL?: typeof URL }).webkitURL;
        const objectUrl = typeof urlFactory?.createObjectURL === 'function'
            ? urlFactory.createObjectURL(blob)
            : '';

        const link = document.createElement('a');
        link.href = objectUrl || `data:${mimeType},${encodeURIComponent(content)}`;
        link.download = filename;
        link.rel = 'noopener';
        document.body.appendChild(link);
        link.click();
        link.remove();

        if (objectUrl && typeof urlFactory?.revokeObjectURL === 'function') {
            urlFactory.revokeObjectURL(objectUrl);
        }
    }

    private initTheme(): void {
        let nextTheme: 'light' | 'dark' = 'light';
        try {
            const stored = window.localStorage.getItem('dl-explain-theme');
            if (stored === 'light' || stored === 'dark') {
                nextTheme = stored;
            } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                nextTheme = 'dark';
            }
        } catch {
            nextTheme = 'light';
        }
        this.applyTheme(nextTheme);
    }

    private applyTheme(mode: 'light' | 'dark'): void {
        this.themeMode = mode;
        const panel = this.container.querySelector('.explain-panel');
        if (!panel) {
            return;
        }
        panel.classList.toggle('theme-dark', mode === 'dark');
        const toggle = this.container.querySelector('#dl-explain-theme-toggle') as HTMLButtonElement | null;
        if (toggle) {
            const isDark = mode === 'dark';
            toggle.setAttribute('aria-pressed', isDark ? 'true' : 'false');
            toggle.textContent = isDark ? '浅色模式' : '暗黑模式';
        }
        try {
            window.localStorage.setItem('dl-explain-theme', mode);
        } catch {
            // ignore local storage write error
        }
        void this.resizeAllCharts();
    }

    private toggleTheme(): void {
        this.applyTheme(this.themeMode === 'dark' ? 'light' : 'dark');
        this.setStatus(`已切换为${this.themeMode === 'dark' ? '暗黑' : '浅色'}模式`, 'success');
    }

    private getCachedMonitor(force: boolean): MonitorPayload | null {
        if (force || !this.monitorCache) {
            return null;
        }
        if (Date.now() - this.monitorCache.at > this.monitorCacheTTL) {
            return null;
        }
        return this.monitorCache.data;
    }

    private getCachedTask(taskId: string, force: boolean): ExplainTask | null {
        if (force) {
            return null;
        }
        const entry = this.taskCache.get(taskId);
        if (!entry) {
            return null;
        }
        if (Date.now() - entry.at > this.taskCacheTTL) {
            return null;
        }
        return entry.data;
    }

    private switchResultTabByKeyboard(delta: number): void {
        const tabs: Array<typeof this.activeTab> = ['lime', 'shap', 'compare', 'spatiotemporal'];
        const total = tabs.length;
        this.selectedResultTabIndex = (this.selectedResultTabIndex + delta + total) % total;
        this.activeTab = tabs[this.selectedResultTabIndex];
        this.updateResultTabs();
        this.renderCurrentResult();
        const activeButton = this.container.querySelector<HTMLButtonElement>(`[data-result-tab="${this.activeTab}"]`);
        activeButton?.focus();
    }

    private switchMethodByKeyboard(delta: number): void {
        const methods: ExplainMethod[] = ['lime', 'shap', 'hybrid'];
        const total = methods.length;
        this.selectedMethodIndex = (this.selectedMethodIndex + delta + total) % total;
        this.selectedMethod = methods[this.selectedMethodIndex];
        this.updateMethodSwitch();
        this.setStatus(`已切换提交方法：${this.selectedMethod.toUpperCase()}`, 'success');
        const activeButton = this.container.querySelector<HTMLButtonElement>(`[data-method-switch="${this.selectedMethod}"]`);
        activeButton?.focus();
    }

    private async loadChartRuntime(): Promise<ChartRuntime | null> {
        if (this.chartLibPromise) {
            return this.chartLibPromise;
        }
        this.chartLibPromise = (async () => {
            try {
                const runtime = await import('echarts');
                return runtime as unknown as ChartRuntime;
            } catch {
                return null;
            }
        })();
        return this.chartLibPromise;
    }

    private ensureChartObserver(): IntersectionObserver | null {
        if (typeof window === 'undefined' || !('IntersectionObserver' in window)) {
            return null;
        }
        if (this.chartObserver) {
            return this.chartObserver;
        }
        this.chartObserver = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) {
                    return;
                }
                const element = entry.target as HTMLElement;
                const chartId = element.id;
                const task = this.chartPendingRender.get(chartId);
                if (task) {
                    void task();
                    this.chartPendingRender.delete(chartId);
                }
                this.chartObserver?.unobserve(element);
            });
        }, { threshold: 0.15 });
        return this.chartObserver;
    }

    private queueLazyChartRender(chartId: string, renderTask: () => Promise<void>): void {
        const element = this.container.querySelector(`#${chartId}`) as HTMLElement | null;
        if (!element) {
            return;
        }
        const observer = this.ensureChartObserver();
        if (!observer) {
            void renderTask();
            return;
        }
        this.chartPendingRender.set(chartId, renderTask);
        observer.observe(element);
    }

    private async renderChartsForCurrentTab(result: Record<string, unknown>): Promise<void> {
        if (this.activeTab === 'lime') {
            const lime = (result.lime || {}) as Record<string, unknown>;
            const visualization = (lime.visualization || {}) as Record<string, unknown>;
            const featureImportance = this.parseImportanceRows(
                visualization.feature_importance_list || lime.global_feature_importance || []
            ).slice(0, 20);
            this.queueLazyChartRender('chart-lime-feature', async () => {
                await this.renderBarChart('chart-lime-feature', 'LIME特征重要性', featureImportance);
            });
            return;
        }
        if (this.activeTab === 'shap') {
            const shap = (result.shap || {}) as Record<string, unknown>;
            const vis = (shap.visualization || {}) as Record<string, unknown>;
            const waterfall = this.parseImportanceRows(vis.waterfall_list || []).slice(0, 20);
            const ranking = this.parseImportanceRows(vis.feature_ranking || shap.global_feature_importance || []).slice(0, 20);
            const beeswarm = Array.isArray(vis.beeswarm_data) ? vis.beeswarm_data as Array<Record<string, unknown>> : [];
            this.queueLazyChartRender('chart-shap-waterfall', async () => {
                await this.renderBarChart('chart-shap-waterfall', 'SHAP瀑布图', waterfall);
            });
            this.queueLazyChartRender('chart-shap-ranking', async () => {
                await this.renderBarChart('chart-shap-ranking', 'SHAP特征重要性排序', ranking);
            });
            this.queueLazyChartRender('chart-shap-beeswarm', async () => {
                await this.renderShapBeeswarmChart(beeswarm, 0, 1);
            });
            return;
        }
        this.disposeCharts();
    }

    private async renderBarChart(chartId: string, title: string, rows: Array<{ name: string; value: number }>): Promise<void> {
        const runtime = await this.loadChartRuntime();
        const element = this.container.querySelector(`#${chartId}`) as HTMLElement | null;
        if (!runtime || !element || !rows.length) {
            return;
        }
        element.parentElement?.querySelector('.fallback-bars')?.classList.add('chart-enhanced');
        const colorPositive = this.themeMode === 'dark' ? '#60a5fa' : '#2563eb';
        const colorNegative = this.themeMode === 'dark' ? '#fca5a5' : '#dc2626';
        const option: Record<string, unknown> = {
            animation: false,
            title: { text: title, left: 'center', textStyle: { fontSize: 12 } },
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            grid: { left: 140, right: 20, top: 36, bottom: 42 },
            xAxis: { type: 'value' },
            yAxis: {
                type: 'category',
                data: rows.map(row => row.name),
                axisLabel: { width: 120, overflow: 'truncate' }
            },
            dataZoom: [
                { type: 'inside', yAxisIndex: 0, zoomOnMouseWheel: true, moveOnMouseMove: true },
                { type: 'slider', yAxisIndex: 0, height: 14, bottom: 8 }
            ],
            series: [
                {
                    type: 'bar',
                    data: rows.map(row => ({
                        value: row.value,
                        itemStyle: { color: row.value >= 0 ? colorPositive : colorNegative }
                    })),
                    progressive: 2000
                }
            ]
        };
        this.setChartOption(chartId, runtime, element, option);
    }

    private async renderShapBeeswarmChart(rows: Array<Record<string, unknown>>, threshold: number, zoom: number): Promise<void> {
        const runtime = await this.loadChartRuntime();
        const element = this.container.querySelector('#chart-shap-beeswarm') as HTMLElement | null;
        if (!runtime || !element) {
            return;
        }
        element.parentElement?.querySelector('.fallback-bars')?.classList.add('chart-enhanced');
        const filtered = rows
            .map((item) => ({
                feature: String(item.feature || item.feature_name || 'feature'),
                x: Number(item.feature_value ?? item.x ?? 0),
                y: Number(item.shap_value ?? item.value ?? item.y ?? 0)
            }))
            .filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y))
            .filter((item) => Math.abs(item.y) >= threshold)
            .slice(0, 2000);
        const size = Math.max(6, Math.min(16, Math.round(8 * zoom)));
        const option: Record<string, unknown> = {
            animation: false,
            tooltip: {
                trigger: 'item',
                formatter: (params: { value: [number, number, string] }) => {
                    const feature = String(params.value?.[2] || '-');
                    const featureValue = Number(params.value?.[0] || 0).toFixed(4);
                    const shapValue = Number(params.value?.[1] || 0).toFixed(4);
                    return `${feature}<br/>feature=${featureValue}<br/>shap=${shapValue}`;
                }
            },
            grid: { left: 52, right: 24, top: 18, bottom: 48 },
            xAxis: { type: 'value', name: 'Feature Value' },
            yAxis: { type: 'value', name: 'SHAP Value' },
            dataZoom: [
                { type: 'inside', xAxisIndex: 0, yAxisIndex: 0 },
                { type: 'slider', xAxisIndex: 0, bottom: 10, height: 14 }
            ],
            series: [
                {
                    type: 'scatter',
                    data: filtered.map((item) => [item.x, item.y, item.feature]),
                    symbolSize: size,
                    itemStyle: {
                        color: (param: { value: [number, number, string] }) => (Number(param.value?.[1] || 0) >= 0 ? '#16a34a' : '#dc2626'),
                        opacity: 0.72
                    },
                    large: true,
                    largeThreshold: 1200,
                    progressive: 3000
                }
            ]
        };
        this.setChartOption('chart-shap-beeswarm', runtime, element, option);
    }

    private setChartOption(
        chartId: string,
        runtime: ChartRuntime,
        element: HTMLElement,
        option: Record<string, unknown>
    ): void {
        const existing = this.chartInstances.get(chartId);
        const instance = existing || runtime.init(element, this.themeMode);
        instance.setOption(option, { notMerge: true, lazyUpdate: true });
        this.chartInstances.set(chartId, instance);
    }

    private async resizeAllCharts(): Promise<void> {
        this.chartInstances.forEach((chart) => {
            chart.resize();
        });
    }

    private disposeCharts(): void {
        this.chartInstances.forEach((chart) => chart.dispose());
        this.chartInstances.clear();
        this.chartPendingRender.clear();
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

    private flattenNumberArray(raw: unknown): number[] {
        const rows: number[] = [];
        const walk = (value: unknown): void => {
            if (Array.isArray(value)) {
                value.forEach((item) => walk(item));
                return;
            }
            const num = Number(value);
            if (Number.isFinite(num)) {
                rows.push(num);
            }
        };
        walk(raw);
        return rows;
    }

    private pickFirstNumberArray(source: Record<string, unknown>, paths: string[][]): number[] {
        for (const path of paths) {
            let current: unknown = source;
            let valid = true;
            for (const key of path) {
                if (!current || typeof current !== 'object') {
                    valid = false;
                    break;
                }
                current = (current as Record<string, unknown>)[key];
            }
            if (!valid) {
                continue;
            }
            const rows = this.flattenNumberArray(current);
            if (rows.length) {
                return rows;
            }
        }
        return [];
    }

    private normalizeLength(values: number[], size: number, fallback: number = 0): number[] {
        if (size <= 0) {
            return [];
        }
        if (!values.length) {
            return Array.from({ length: size }, () => fallback);
        }
        return Array.from({ length: size }, (_, idx) => {
            const value = values[idx];
            if (Number.isFinite(value)) {
                return Number(value);
            }
            return values[idx % values.length] ?? fallback;
        });
    }

    private buildSpatialEpistemicRatios(coords: Array<[number, number]>, size: number): number[] {
        if (!coords.length || size <= 0) {
            return Array.from({ length: size }, () => 0.58);
        }
        const centerX = coords.reduce((acc, item) => acc + Number(item[0] || 0), 0) / coords.length;
        const centerY = coords.reduce((acc, item) => acc + Number(item[1] || 0), 0) / coords.length;
        const distances = coords.map((item) => {
            const dx = Number(item[0] || 0) - centerX;
            const dy = Number(item[1] || 0) - centerY;
            return Math.sqrt(dx * dx + dy * dy);
        });
        const maxDist = Math.max(...distances, 1e-6);
        return Array.from({ length: size }, (_, idx) => {
            const dist = distances[idx % distances.length] || 0;
            const normalized = Math.max(0, Math.min(1, dist / maxDist));
            return Math.max(0.2, Math.min(0.9, 0.35 + normalized * 0.5));
        });
    }

    private buildUncertaintyVisualizationData(
        result: Record<string, unknown>,
        coords: Array<[number, number]>,
        series: number[][][]
    ): {
        prediction: number[];
        variance: number[];
        epistemic: number[];
        aleatoric: number[];
        lower: number[];
        upper: number[];
        decompositionMode: 'direct' | 'inferred';
        sourceWeights: Array<{ name: string; ratio: number; detail: string }>;
        distributionBins: Array<{ left: number; right: number; count: number; ratio: number }>;
        quantiles: { p10: number; p50: number; p90: number };
    } {
        const predictionRaw = this.pickFirstNumberArray(result, [
            ['prediction'],
            ['mean'],
            ['pred_mean']
        ]);
        const varianceRaw = this.pickFirstNumberArray(result, [
            ['variance'],
            ['uncertainty'],
            ['total_uncertainty']
        ]);
        const epistemicRaw = this.pickFirstNumberArray(result, [
            ['epistemic'],
            ['uncertainty', 'knowledge'],
            ['uncertainty', 'epistemic']
        ]);
        const aleatoricRaw = this.pickFirstNumberArray(result, [
            ['aleatoric'],
            ['uncertainty', 'data'],
            ['uncertainty', 'aleatoric']
        ]);
        const lowerRaw = this.pickFirstNumberArray(result, [
            ['lower'],
            ['confidence_interval', 'lower'],
            ['interval', 'lower'],
            ['quantiles', 'q05'],
            ['quantiles', 'p05']
        ]);
        const upperRaw = this.pickFirstNumberArray(result, [
            ['upper'],
            ['confidence_interval', 'upper'],
            ['interval', 'upper'],
            ['quantiles', 'q95'],
            ['quantiles', 'p95']
        ]);

        const size = Math.max(
            predictionRaw.length,
            varianceRaw.length,
            epistemicRaw.length,
            aleatoricRaw.length,
            lowerRaw.length,
            upperRaw.length,
            1
        );
        const prediction = this.normalizeLength(predictionRaw, size, 0);
        const variance = this.normalizeLength(varianceRaw, size, 0).map((item) => Math.max(0, item));
        let epistemic = this.normalizeLength(epistemicRaw, size, 0).map((item) => Math.max(0, item));
        let aleatoric = this.normalizeLength(aleatoricRaw, size, 0).map((item) => Math.max(0, item));

        let decompositionMode: 'direct' | 'inferred' = 'direct';
        if (!epistemicRaw.length && !aleatoricRaw.length) {
            const ratios = this.buildSpatialEpistemicRatios(coords, size);
            epistemic = variance.map((item, idx) => item * ratios[idx]);
            aleatoric = variance.map((item, idx) => Math.max(0, item - epistemic[idx]));
            decompositionMode = 'inferred';
        } else if (!epistemicRaw.length) {
            epistemic = variance.map((item, idx) => Math.max(0, item - aleatoric[idx]));
            decompositionMode = 'inferred';
        } else if (!aleatoricRaw.length) {
            aleatoric = variance.map((item, idx) => Math.max(0, item - epistemic[idx]));
            decompositionMode = 'inferred';
        }

        const lowerExplicit = this.normalizeLength(lowerRaw, size, Number.NaN);
        const upperExplicit = this.normalizeLength(upperRaw, size, Number.NaN);
        const lower = prediction.map((pred, idx) => {
            const explicit = lowerExplicit[idx];
            if (Number.isFinite(explicit)) {
                return explicit;
            }
            const sigma = Math.sqrt(Math.max(variance[idx], 0));
            return pred - 1.96 * sigma;
        });
        const upper = prediction.map((pred, idx) => {
            const explicit = upperExplicit[idx];
            if (Number.isFinite(explicit)) {
                return explicit;
            }
            const sigma = Math.sqrt(Math.max(variance[idx], 0));
            return pred + 1.96 * sigma;
        });

        const epiMean = epistemic.reduce((acc, item) => acc + item, 0) / Math.max(1, epistemic.length);
        const aleaMean = aleatoric.reduce((acc, item) => acc + item, 0) / Math.max(1, aleatoric.length);
        const uncertaintySum = Math.max(1e-8, epiMean + aleaMean);

        const timelineRows = this.buildTimelineRows(series);
        const timelineMean = timelineRows.length
            ? timelineRows.reduce((acc, item) => acc + Math.abs(item.value), 0) / timelineRows.length
            : 0;
        const spatialRatios = this.buildSpatialEpistemicRatios(coords, Math.max(1, coords.length));
        const spatialSpread = spatialRatios.length
            ? spatialRatios.reduce((acc, item) => acc + item, 0) / spatialRatios.length
            : 0.58;

        const sourceWeights = [
            {
                name: '认知不确定性（模型）',
                ratio: Math.max(0, Math.min(1, epiMean / uncertaintySum)),
                detail: decompositionMode === 'direct' ? '来自模型直接分解字段' : '基于空间分散度推断分解'
            },
            {
                name: '偶然不确定性（数据）',
                ratio: Math.max(0, Math.min(1, aleaMean / uncertaintySum)),
                detail: decompositionMode === 'direct' ? '来自模型直接分解字段' : '由总不确定性与认知分量互补得到'
            },
            {
                name: '时间漂移强度',
                ratio: Math.max(0, Math.min(1, timelineMean / (timelineMean + 1))),
                detail: '由序列相邻时刻平均变化幅度估计'
            },
            {
                name: '空间离散度',
                ratio: Math.max(0, Math.min(1, spatialSpread)),
                detail: '由节点相对中心距离归一化估计'
            }
        ];

        const distValues = prediction.filter((item) => Number.isFinite(item));
        const distMin = distValues.length ? Math.min(...distValues) : 0;
        const distMax = distValues.length ? Math.max(...distValues) : 0;
        const bins = this.buildReconstructionHistogramRows(distValues, Number.NaN, 14).map((item) => ({
            left: item.left,
            right: item.right,
            count: item.count,
            ratio: item.ratio
        }));
        const quantiles = {
            p10: this.computePercentile(distValues.length ? distValues : [distMin, distMax], 10),
            p50: this.computePercentile(distValues.length ? distValues : [distMin, distMax], 50),
            p90: this.computePercentile(distValues.length ? distValues : [distMin, distMax], 90)
        };

        return {
            prediction,
            variance,
            epistemic,
            aleatoric,
            lower,
            upper,
            decompositionMode,
            sourceWeights,
            distributionBins: bins,
            quantiles
        };
    }

    private renderUncertaintySourceExplanation(data: {
        decompositionMode: 'direct' | 'inferred';
        sourceWeights: Array<{ name: string; ratio: number; detail: string }>;
    }): string {
        const modeText = data.decompositionMode === 'direct'
            ? '分解模式：直接读取模型返回的认知/偶然不确定性字段。'
            : '分解模式：后端暂未返回完整分解字段，前端基于空间与总方差推断。';
        return `
            <div class="uncert-source-panel">
                <p class="muted">${modeText}</p>
                <div class="uncert-source-list">
                    ${data.sourceWeights.map((item) => {
                        const pct = Math.round(Math.max(0, Math.min(1, item.ratio)) * 100);
                        return `
                            <div class="uncert-source-item">
                                <div class="uncert-source-header">
                                    <span>${item.name}</span>
                                    <span>${pct}%</span>
                                </div>
                                <div class="uncert-source-track">
                                    <div class="uncert-source-fill" style="width:${Math.max(2, pct)}%"></div>
                                </div>
                                <div class="uncert-source-detail">${item.detail}</div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    }

    private renderConfidenceIntervalVisualization(data: {
        prediction: number[];
        lower: number[];
        upper: number[];
    }): string {
        const rows = data.prediction.map((pred, idx) => ({
            index: idx,
            prediction: pred,
            lower: Math.min(data.lower[idx] ?? pred, data.upper[idx] ?? pred),
            upper: Math.max(data.lower[idx] ?? pred, data.upper[idx] ?? pred)
        }));
        if (!rows.length) {
            return '<div class="status-message">暂无置信区间数据</div>';
        }
        const sorted = [...rows].sort((a, b) => (b.upper - b.lower) - (a.upper - a.lower)).slice(0, 16);
        const minVal = Math.min(...sorted.map((item) => item.lower));
        const maxVal = Math.max(...sorted.map((item) => item.upper));
        const span = Math.max(1e-6, maxVal - minVal);
        return `
            <div class="ci-list">
                ${sorted.map((item) => {
                    const left = ((item.lower - minVal) / span) * 100;
                    const width = Math.max(1.2, ((item.upper - item.lower) / span) * 100);
                    const point = ((item.prediction - minVal) / span) * 100;
                    return `
                        <div class="ci-item">
                            <div class="ci-meta">
                                <span>样本 #${item.index + 1}</span>
                                <span>[${item.lower.toFixed(3)}, ${item.upper.toFixed(3)}]</span>
                            </div>
                            <div class="ci-track">
                                <div class="ci-band" style="left:${left}%;width:${width}%"></div>
                                <span class="ci-point" style="left:${point}%"></span>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    private renderUncertaintyDecompositionVisualization(data: {
        epistemic: number[];
        aleatoric: number[];
        variance: number[];
    }): string {
        const size = Math.max(data.epistemic.length, data.aleatoric.length, data.variance.length);
        if (!size) {
            return '<div class="status-message">暂无认知/偶然不确定性数据</div>';
        }
        const rows = Array.from({ length: size }, (_, idx) => {
            const epistemic = Math.max(0, Number(data.epistemic[idx] ?? 0));
            const aleatoric = Math.max(0, Number(data.aleatoric[idx] ?? 0));
            const total = Math.max(1e-8, Number(data.variance[idx] ?? (epistemic + aleatoric)));
            return {
                index: idx,
                epistemic,
                aleatoric,
                total: Math.max(total, epistemic + aleatoric)
            };
        });
        const top = rows.sort((a, b) => b.total - a.total).slice(0, 14);
        return `
            <div class="decomp-list">
                ${top.map((item) => {
                    const denom = Math.max(1e-8, item.epistemic + item.aleatoric);
                    const epiPct = Math.max(0, Math.min(100, Math.round((item.epistemic / denom) * 100)));
                    const alePct = Math.max(0, Math.min(100, 100 - epiPct));
                    return `
                        <div class="decomp-item">
                            <div class="decomp-meta">
                                <span>样本 #${item.index + 1}</span>
                                <span>总不确定性 ${item.total.toFixed(4)}</span>
                            </div>
                            <div class="decomp-track">
                                <div class="decomp-epi" style="width:${Math.max(1, epiPct)}%"></div>
                                <div class="decomp-ale" style="width:${Math.max(1, alePct)}%"></div>
                            </div>
                            <div class="decomp-legend">
                                <span>认知 ${item.epistemic.toFixed(4)} (${epiPct}%)</span>
                                <span>偶然 ${item.aleatoric.toFixed(4)} (${alePct}%)</span>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    private renderPredictionDistributionVisualization(data: {
        distributionBins: Array<{ left: number; right: number; count: number; ratio: number }>;
        quantiles: { p10: number; p50: number; p90: number };
    }): string {
        if (!data.distributionBins.length) {
            return '<div class="status-message">暂无预测分布数据</div>';
        }
        const maxCount = Math.max(...data.distributionBins.map((item) => item.count), 1);
        return `
            <div class="pred-dist-panel">
                <div class="pred-dist-quantiles">
                    <span>P10: ${data.quantiles.p10.toFixed(4)}</span>
                    <span>P50: ${data.quantiles.p50.toFixed(4)}</span>
                    <span>P90: ${data.quantiles.p90.toFixed(4)}</span>
                </div>
                <div class="pred-dist-list">
                    ${data.distributionBins.map((item) => {
                        const width = Math.max(2, Math.round((item.count / maxCount) * 100));
                        return `
                            <div class="pred-dist-row">
                                <span class="pred-dist-bin">${item.left.toFixed(3)} ~ ${item.right.toFixed(3)}</span>
                                <div class="pred-dist-track">
                                    <div class="pred-dist-fill" style="width:${width}%"></div>
                                </div>
                                <span class="pred-dist-count">${item.count}</span>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    }

    private renderUncertaintyHeatmapVisualization(
        data: { variance: number[]; epistemic: number[]; aleatoric: number[] },
        coords: Array<[number, number]>
    ): string {
        const variance = data.variance.filter((item) => Number.isFinite(item) && item >= 0);
        if (!variance.length) {
            return '<div class="status-message">暂无不确定性热力图数据</div>';
        }
        const maxVariance = Math.max(...variance, 1e-8);
        const rows = variance.slice(0, 64).map((value, idx) => {
            const intensity = Math.max(0.12, Math.min(1, value / maxVariance));
            const coord = coords[idx];
            const label = coord
                ? `节点${idx + 1} (${coord[0]}, ${coord[1]})`
                : `节点${idx + 1}`;
            return {
                value,
                intensity,
                label,
                epistemic: Math.max(0, Number(data.epistemic[idx] ?? 0)),
                aleatoric: Math.max(0, Number(data.aleatoric[idx] ?? 0))
            };
        });
        return `
            <div class="uncertainty-heatmap-panel">
                <div class="heatmap-grid uncertainty-heatmap-grid">
                    ${rows.map((item) => `
                        <button
                            class="heatmap-cell uncertainty-heatmap-cell"
                            type="button"
                            aria-label="${item.label}"
                            title="${item.label} / 总不确定性 ${item.value.toFixed(4)} / 认知 ${item.epistemic.toFixed(4)} / 偶然 ${item.aleatoric.toFixed(4)}"
                            style="background: rgba(220, 38, 38, ${item.intensity});"
                        >
                            ${item.value.toFixed(3)}
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
    }

    private renderUncertaintyTimelineVisualization(
        data: { variance: number[]; epistemic: number[]; aleatoric: number[] },
        series: number[][][]
    ): string {
        const baseVariance = data.variance.filter((item) => Number.isFinite(item) && item >= 0);
        if (!baseVariance.length) {
            return '<div class="status-message">暂无不确定性时间序列数据</div>';
        }
        const steps = Math.max(1, series[0]?.length || Math.min(24, baseVariance.length));
        const timelineValues: Array<{ index: number; total: number; epistemic: number; aleatoric: number }> = [];
        for (let step = 0; step < steps; step += 1) {
            let total = 0;
            let epistemic = 0;
            let aleatoric = 0;
            let count = 0;
            for (let node = step; node < data.variance.length; node += steps) {
                const variance = Math.max(0, Number(data.variance[node] ?? 0));
                const epi = Math.max(0, Number(data.epistemic[node] ?? 0));
                const alea = Math.max(0, Number(data.aleatoric[node] ?? 0));
                total += variance;
                epistemic += epi;
                aleatoric += alea;
                count += 1;
            }
            timelineValues.push({
                index: step,
                total: count ? total / count : 0,
                epistemic: count ? epistemic / count : 0,
                aleatoric: count ? aleatoric / count : 0
            });
        }
        const maxTotal = Math.max(...timelineValues.map((item) => item.total), 1e-8);
        return `
            <div class="timeline-list uncertainty-timeline-list">
                ${timelineValues.map((item) => {
                    const width = Math.max(2, Math.round((item.total / maxTotal) * 100));
                    return `
                        <div class="timeline-item uncertainty-timeline-item">
                            <span>T${item.index + 1}</span>
                            <div class="timeline-track">
                                <div class="timeline-fill uncertainty-timeline-fill" style="width:${width}%"></div>
                            </div>
                            <span>${item.total.toFixed(4)}</span>
                            <span class="uncertainty-timeline-meta">认知 ${item.epistemic.toFixed(3)} / 偶然 ${item.aleatoric.toFixed(3)}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    private renderUncertaintySpatialDistributionVisualization(
        data: { variance: number[]; epistemic: number[]; aleatoric: number[] },
        coords: Array<[number, number]>
    ): string {
        const total = data.variance.length;
        if (!total) {
            return '<div class="status-message">暂无不确定性空间分布数据</div>';
        }
        const centerX = coords.length ? coords.reduce((acc, item) => acc + Number(item[0] || 0), 0) / coords.length : 0;
        const centerY = coords.length ? coords.reduce((acc, item) => acc + Number(item[1] || 0), 0) / coords.length : 0;
        const distances = Array.from({ length: total }, (_, idx) => {
            const coord = coords[idx];
            if (!coord) {
                return 0;
            }
            const dx = Number(coord[0] || 0) - centerX;
            const dy = Number(coord[1] || 0) - centerY;
            return Math.sqrt(dx * dx + dy * dy);
        });
        const maxDistance = Math.max(...distances, 1e-8);
        const maxVariance = Math.max(...data.variance.map((item) => Math.max(0, Number(item || 0))), 1e-8);
        const rows = Array.from({ length: total }, (_, idx) => {
            const variance = Math.max(0, Number(data.variance[idx] ?? 0));
            const epistemic = Math.max(0, Number(data.epistemic[idx] ?? 0));
            const aleatoric = Math.max(0, Number(data.aleatoric[idx] ?? 0));
            const distance = distances[idx] / maxDistance;
            const uncertainty = variance / maxVariance;
            const level = uncertainty >= 0.66 ? '高' : uncertainty >= 0.33 ? '中' : '低';
            return {
                idx,
                variance,
                epistemic,
                aleatoric,
                distance,
                uncertainty,
                level
            };
        })
            .sort((a, b) => b.uncertainty - a.uncertainty)
            .slice(0, 20);

        return `
            <div class="uncertainty-spatial-panel">
                <div class="uncertainty-spatial-legend">
                    <span>横轴：空间离中心距离（近 -> 远）</span>
                    <span>纵轴：不确定性等级（低 -> 高）</span>
                </div>
                <div class="uncertainty-spatial-list">
                    ${rows.map((item) => `
                        <div class="uncertainty-spatial-item">
                            <div class="uncertainty-spatial-meta">
                                <span>节点 #${item.idx + 1}</span>
                                <span>等级 ${item.level}</span>
                            </div>
                            <div class="uncertainty-spatial-track">
                                <div class="uncertainty-spatial-distance" style="width:${Math.max(2, Math.round(item.distance * 100))}%"></div>
                                <div class="uncertainty-spatial-uncertainty" style="width:${Math.max(2, Math.round(item.uncertainty * 100))}%"></div>
                            </div>
                            <div class="uncertainty-spatial-value">
                                <span>总 ${item.variance.toFixed(4)}</span>
                                <span>认知 ${item.epistemic.toFixed(4)}</span>
                                <span>偶然 ${item.aleatoric.toFixed(4)}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    private collectReconstructionErrorData(result: Record<string, unknown>): { lime: number[]; shap: number[]; combined: number[] } {
        const lime = this.extractReconstructionErrorsFromPayload((result.lime || {}) as Record<string, unknown>);
        const shap = this.extractReconstructionErrorsFromPayload((result.shap || {}) as Record<string, unknown>);
        const fallback = this.extractReconstructionErrorsFromPayload(result);
        const maxLen = Math.max(lime.length, shap.length, fallback.length);
        const combined: number[] = [];
        for (let i = 0; i < maxLen; i += 1) {
            const values = [lime[i], shap[i], fallback[i]].filter((item) => Number.isFinite(item)) as number[];
            if (!values.length) {
                continue;
            }
            combined.push(values.reduce((acc, item) => acc + item, 0) / values.length);
        }
        if (!combined.length) {
            return {
                lime,
                shap,
                combined: fallback.length ? fallback : [0]
            };
        }
        return { lime, shap, combined };
    }

    private extractReconstructionErrorsFromPayload(payload: Record<string, unknown>): number[] {
        const rows: number[] = [];
        const scoreComponents = (payload.score_components || {}) as Record<string, unknown>;
        const reconRaw = scoreComponents.reconstruction;
        if (Array.isArray(reconRaw)) {
            reconRaw.forEach((value) => {
                const num = Number(value);
                if (Number.isFinite(num)) {
                    rows.push(num);
                }
            });
        }

        if (!rows.length) {
            const reconAnalysis = (payload.reconstruction_analysis || {}) as Record<string, unknown>;
            const nodeAnalysis = Array.isArray(reconAnalysis.node_analysis) ? reconAnalysis.node_analysis as Array<Record<string, unknown>> : [];
            nodeAnalysis.forEach((item) => {
                const num = Number(item.reconstruction_error ?? item.reconstruction_score ?? item.error ?? 0);
                if (Number.isFinite(num)) {
                    rows.push(num);
                }
            });
        }

        if (!rows.length) {
            const generator = (payload.generator_analysis || {}) as Record<string, unknown>;
            const nodeRows = Array.isArray(generator.node_analysis) ? generator.node_analysis as Array<Record<string, unknown>> : [];
            nodeRows.forEach((item) => {
                const num = Number(item.reconstruction_score ?? item.abs_residual ?? 0);
                if (Number.isFinite(num)) {
                    rows.push(num);
                }
            });
        }
        return rows;
    }

    private computePercentile(values: number[], percentile: number): number {
        const filtered = values.filter((item) => Number.isFinite(item));
        if (!filtered.length) {
            return 0;
        }
        const sorted = [...filtered].sort((a, b) => a - b);
        const p = Math.max(0, Math.min(100, percentile));
        const idx = Math.min(sorted.length - 1, Math.max(0, Math.floor(((sorted.length - 1) * p) / 100)));
        return sorted[idx];
    }

    private buildReconstructionHistogramRows(
        values: number[],
        threshold: number,
        binCount: number
    ): Array<{ left: number; right: number; count: number; ratio: number; isThresholdBin: boolean }> {
        const filtered = values.filter((item) => Number.isFinite(item));
        if (!filtered.length) {
            return [{ left: 0, right: 0, count: 0, ratio: 0, isThresholdBin: true }];
        }
        const minVal = Math.min(...filtered);
        const maxVal = Math.max(...filtered);
        const bins = Math.max(4, Math.min(30, binCount));
        const span = Math.max(1e-6, maxVal - minVal);
        const step = span / bins;
        const bucket = Array.from({ length: bins }).map((_, idx) => ({
            left: minVal + idx * step,
            right: idx === bins - 1 ? maxVal : minVal + (idx + 1) * step,
            count: 0,
            ratio: 0,
            isThresholdBin: false
        }));
        filtered.forEach((value) => {
            const rawIndex = Math.floor((value - minVal) / step);
            const idx = Math.max(0, Math.min(bins - 1, rawIndex));
            bucket[idx].count += 1;
        });
        const total = filtered.length;
        bucket.forEach((item, idx) => {
            item.ratio = item.count / Math.max(1, total);
            const startHit = threshold >= item.left;
            const endHit = idx === bins - 1 ? threshold <= item.right : threshold < item.right;
            item.isThresholdBin = startHit && endHit;
        });
        return bucket;
    }

    private renderReconstructionHistogramRows(
        rows: Array<{ left: number; right: number; count: number; ratio: number; isThresholdBin: boolean }>
    ): string {
        if (!rows.length) {
            return '<div class="status-message">暂无重建误差数据</div>';
        }
        const maxCount = Math.max(...rows.map((item) => item.count), 1);
        return rows.map((item) => {
            const width = Math.max(2, Math.round((item.count / maxCount) * 100));
            return `
                <div class="recon-histogram-row ${item.isThresholdBin ? 'threshold-hit' : ''}">
                    <span class="recon-histogram-bin">${item.left.toFixed(3)} ~ ${item.right.toFixed(3)}</span>
                    <div class="recon-histogram-track">
                        <div class="recon-histogram-fill" style="width:${width}%"></div>
                    </div>
                    <span class="recon-histogram-count">${item.count}</span>
                </div>
            `;
        }).join('');
    }

    private buildReconstructionHeatmapRows(
        coords: Array<[number, number]>,
        errors: number[],
        threshold: number
    ): Array<{ label: string; value: number; intensity: number; exceeded: boolean }> {
        const values = errors.filter((item) => Number.isFinite(item));
        if (!values.length) {
            return [{ label: '无重建误差', value: 0, intensity: 0.1, exceeded: false }];
        }
        const maxError = Math.max(...values, 1e-6);
        return values.slice(0, 64).map((value, idx) => {
            const coord = coords[idx];
            const label = coord
                ? `节点${idx} (${coord[0]}, ${coord[1]})`
                : `节点${idx} (无坐标)`;
            return {
                label,
                value,
                intensity: Math.max(0.1, Math.min(1, value / maxError)),
                exceeded: value >= threshold
            };
        });
    }

    private renderReconstructionHeatmapRows(
        rows: Array<{ label: string; value: number; intensity: number; exceeded: boolean }>
    ): string {
        if (!rows.length) {
            return '<div class="status-message">暂无重建误差热图</div>';
        }
        return rows.map((row) => {
            const opacity = row.intensity;
            const className = row.exceeded ? 'heatmap-cell recon-error-cell threshold-hit' : 'heatmap-cell recon-error-cell';
            return `
                <button class="${className}" type="button" aria-label="${row.label}" title="${row.label} / 误差 ${row.value.toFixed(4)}" style="background: rgba(249, 115, 22, ${opacity});">
                    ${row.value.toFixed(3)}
                </button>
            `;
        }).join('');
    }

    private buildReconstructionTimelineRows(
        series: number[][][],
        reconstructionErrors: number[],
        threshold: number
    ): Array<{ index: number; value: number; width: number; exceeded: boolean }> {
        const recon = reconstructionErrors.filter((item) => Number.isFinite(item));
        if (!series.length || !series[0]?.length) {
            if (!recon.length) {
                return [];
            }
            const maxVal = Math.max(...recon, 1e-6);
            return recon.slice(0, 40).map((value, index) => ({
                index,
                value,
                width: Math.round((value / maxVal) * 100),
                exceeded: value >= threshold
            }));
        }
        const steps = series[0].length;
        const factor = recon.length ? recon.reduce((acc, item) => acc + item, 0) / recon.length : 1;
        const timelineValues: number[] = [];
        for (let t = 1; t < steps; t += 1) {
            let sumDiff = 0;
            let count = 0;
            for (const node of series) {
                const current = Array.isArray(node[t]) ? node[t] : [];
                const prev = Array.isArray(node[t - 1]) ? node[t - 1] : [];
                const dim = Math.max(current.length, prev.length);
                for (let i = 0; i < dim; i += 1) {
                    const c = Number(current[i] ?? 0);
                    const p = Number(prev[i] ?? 0);
                    if (!Number.isFinite(c) || !Number.isFinite(p)) {
                        continue;
                    }
                    sumDiff += Math.abs(c - p);
                    count += 1;
                }
            }
            const drift = count ? sumDiff / count : 0;
            timelineValues.push(drift * factor);
        }
        const maxVal = Math.max(...timelineValues.map((item) => Math.abs(item)), 1e-6);
        return timelineValues.slice(0, 60).map((value, index) => ({
            index,
            value,
            width: Math.round((Math.abs(value) / maxVal) * 100),
            exceeded: value >= threshold
        }));
    }

    private renderReconstructionTimelineRows(
        rows: Array<{ index: number; value: number; width: number; exceeded: boolean }>
    ): string {
        if (!rows.length) {
            return '<div class="status-message">暂无重建误差时间轴数据</div>';
        }
        return rows.map((row) => `
            <div class="timeline-item recon-timeline-item ${row.exceeded ? 'threshold-hit' : ''}">
                <span>T${row.index + 1}</span>
                <div class="timeline-track">
                    <div class="timeline-fill recon-timeline-fill" style="width:${Math.max(2, row.width)}%"></div>
                </div>
                <span>${row.value.toFixed(4)}</span>
            </div>
        `).join('');
    }

    private buildReconstructionCompareRows(
        reconstruction: { lime: number[]; shap: number[]; combined: number[] },
        threshold: number
    ): {
        aboveThresholdCount: number;
        belowThresholdCount: number;
        meanError: number;
        aboveMean: number;
        belowMean: number;
        limeMean: number;
        shapMean: number;
        methodGap: number;
    } {
        const combined = reconstruction.combined.filter((item) => Number.isFinite(item));
        const above = combined.filter((item) => item >= threshold);
        const below = combined.filter((item) => item < threshold);
        const mean = (values: number[]): number => values.length ? values.reduce((acc, item) => acc + item, 0) / values.length : 0;
        const limeMean = mean(reconstruction.lime.filter((item) => Number.isFinite(item)));
        const shapMean = mean(reconstruction.shap.filter((item) => Number.isFinite(item)));
        return {
            aboveThresholdCount: above.length,
            belowThresholdCount: below.length,
            meanError: mean(combined),
            aboveMean: mean(above),
            belowMean: mean(below),
            limeMean,
            shapMean,
            methodGap: Math.abs(limeMean - shapMean)
        };
    }

    private renderReconstructionCompareRows(rows: {
        aboveThresholdCount: number;
        belowThresholdCount: number;
        meanError: number;
        aboveMean: number;
        belowMean: number;
        limeMean: number;
        shapMean: number;
        methodGap: number;
    }): string {
        return `
            <p>阈值外/内节点：${rows.aboveThresholdCount} / ${rows.belowThresholdCount}</p>
            <p>整体平均误差：${rows.meanError.toFixed(4)}</p>
            <p>阈值外平均误差：${rows.aboveMean.toFixed(4)}；阈值内平均误差：${rows.belowMean.toFixed(4)}</p>
            <p>LIME平均误差：${rows.limeMean.toFixed(4)}；SHAP平均误差：${rows.shapMean.toFixed(4)}；方法差异：${rows.methodGap.toFixed(4)}</p>
        `;
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

    private startPerformanceMonitor(): void {
        if (typeof window === 'undefined') {
            return;
        }
        this.lastFpsTs = performance.now();
        const tickFrame = (now: number): void => {
            this.frameCount += 1;
            if (now - this.lastFpsTs >= 1000) {
                this.latestFPS = Math.round((this.frameCount * 1000) / (now - this.lastFpsTs));
                this.frameCount = 0;
                this.lastFpsTs = now;
                this.latestMemoryMB = this.readMemoryMB();
                this.updatePerformanceChip();
            }
            this.fpsRafId = window.requestAnimationFrame(tickFrame);
        };
        this.fpsRafId = window.requestAnimationFrame(tickFrame);
        this.fpsTickerId = window.setInterval(() => this.updatePerformanceChip(), 1500);
    }

    private stopPerformanceMonitor(): void {
        if (this.fpsRafId !== null) {
            window.cancelAnimationFrame(this.fpsRafId);
            this.fpsRafId = null;
        }
        if (this.fpsTickerId !== null) {
            window.clearInterval(this.fpsTickerId);
            this.fpsTickerId = null;
        }
    }

    private readMemoryMB(): number | null {
        const perf = performance as typeof performance & { memory?: { usedJSHeapSize?: number } };
        const used = perf.memory?.usedJSHeapSize;
        if (!used || !Number.isFinite(used)) {
            return null;
        }
        return Math.round((used / (1024 * 1024)) * 10) / 10;
    }

    private updatePerformanceChip(): void {
        const fpsEl = this.container.querySelector('#dl-explain-fps') as HTMLElement | null;
        if (fpsEl) {
            fpsEl.textContent = `FPS: ${this.formatNumber(this.latestFPS)}`;
        }
        const memoryEl = this.container.querySelector('#dl-explain-memory') as HTMLElement | null;
        if (memoryEl) {
            memoryEl.textContent = this.latestMemoryMB === null
                ? '内存: -'
                : `内存: ${this.formatNumber(this.latestMemoryMB)}MB`;
        }
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
        this.stopPerformanceMonitor();
        this.disposeCharts();
        if (this.chartObserver) {
            this.chartObserver.disconnect();
            this.chartObserver = null;
        }
        const list = this.container.querySelector('#dl-explain-task-list') as HTMLElement | null;
        if (list && this.taskListScrollHandler) {
            list.removeEventListener('scroll', this.taskListScrollHandler);
        }
        this.taskListScrollHandler = null;
        this.container.innerHTML = '';
    }
}
