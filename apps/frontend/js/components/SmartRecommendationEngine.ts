interface Recommendation {
    actionId: string;
    score: number;
    reason: string;
}

interface ActionRecord {
    actionId: string;
    timestamp: number;
    context: string[];
}

interface RecommendationSample {
    history: ActionRecord[];
    context: string[];
    expected: string;
}

interface RecommendationActionMeta {
    id: string;
    label: string;
    command: string;
}

const STORAGE_KEY = 'udake_recommendation_history_v1';
const MAX_HISTORY = 400;

export class SmartRecommendationEngine {
    private readonly actionMap: Map<string, RecommendationActionMeta>;
    private history: ActionRecord[];
    private root: HTMLDivElement | null;
    private listEl: HTMLDivElement | null;
    private hintEl: HTMLParagraphElement | null;
    private collapseBtn: HTMLButtonElement | null;
    private isCollapsed: boolean;

    constructor(actions: RecommendationActionMeta[]) {
        this.actionMap = new Map(actions.map((item) => [item.id, item]));
        this.history = this.loadHistory();
        this.root = null;
        this.listEl = null;
        this.hintEl = null;
        this.collapseBtn = null;
        this.isCollapsed = false;
    }

    public mount(container: HTMLElement): void {
        if (this.root) {
            return;
        }

        this.root = document.createElement('div');
        this.root.className = 'smart-recommendation-panel';
        this.root.innerHTML = `
            <div class="smart-recommendation-header">
                <h3>智能推荐</h3>
                <div class="smart-recommendation-header-tools">
                    <span class="smart-recommendation-score" id="smart-recommendation-score">--</span>
                    <button
                        type="button"
                        class="smart-recommendation-toggle"
                        aria-label="收起或展开智能推荐"
                        aria-expanded="true"
                        title="收起/展开"
                    >▾</button>
                </div>
            </div>
            <div class="smart-recommendation-content">
                <p class="smart-recommendation-hint"></p>
                <div class="smart-recommendation-list"></div>
                <div class="smart-recommendation-help">
                    <a href="${import.meta.env.VITE_OFFICIAL_WEB}/docs/workflow/quick-actions" target="_blank" rel="noreferrer">快捷操作帮助</a>
                    <a href="${import.meta.env.VITE_OFFICIAL_WEB}/videos/tutorials/wizard-overview" target="_blank" rel="noreferrer">向导视频</a>
                </div>
            </div>
        `;

        this.listEl = this.root.querySelector('.smart-recommendation-list');
        this.hintEl = this.root.querySelector('.smart-recommendation-hint');
        this.collapseBtn = this.root.querySelector('.smart-recommendation-toggle');

        container.appendChild(this.root);
        this.bindCollapseToggle();
        this.bindEvents();
        this.render();
    }

    public destroy(): void {
        this.root?.remove();
        this.root = null;
        this.listEl = null;
        this.hintEl = null;
        this.collapseBtn = null;
    }

    public recordAction(actionId: string, context: string[] = this.collectContext()): void {
        this.history.push({ actionId, timestamp: Date.now(), context });
        if (this.history.length > MAX_HISTORY) {
            this.history.splice(0, this.history.length - MAX_HISTORY);
        }
        this.saveHistory();
        this.render();
    }

    public getRecommendations(context: string[] = this.collectContext(), limit = 4): Recommendation[] {
        const actionIds = Array.from(this.actionMap.keys());
        if (actionIds.length === 0) {
            return [];
        }

        const counts = new Map<string, number>();
        const recency = new Map<string, number>();
        const now = Date.now();

        for (const record of this.history) {
            counts.set(record.actionId, (counts.get(record.actionId) || 0) + 1);
            const prevTs = recency.get(record.actionId) || 0;
            recency.set(record.actionId, Math.max(prevTs, record.timestamp));
        }

        const maxCount = Math.max(1, ...Array.from(counts.values()));

        const scored = actionIds.map((actionId) => {
            const frequencyScore = (counts.get(actionId) || 0) / maxCount;
            const lastTs = recency.get(actionId);
            const recencyHours = lastTs ? (now - lastTs) / (1000 * 60 * 60) : 999;
            const recencyScore = Math.max(0, 1 - recencyHours / 48);
            const contextScore = this.getContextScore(actionId, context);
            const beginnerBoost = this.isBeginner() && this.getBeginnerActions().includes(actionId) ? 0.3 : 0;

            const score = frequencyScore * 0.45 + recencyScore * 0.2 + contextScore * 0.35 + beginnerBoost;
            return {
                actionId,
                score,
                reason: this.describeReason(actionId, context, frequencyScore, contextScore)
            };
        });

        return scored
            .sort((a, b) => b.score - a.score)
            .slice(0, limit)
            .filter((item) => item.score > 0.15);
    }

    public evaluateAccuracy(samples: RecommendationSample[]): number {
        if (samples.length === 0) {
            return 0;
        }

        let hit = 0;
        for (const sample of samples) {
            this.history = [...sample.history];
            const result = this.getRecommendations(sample.context, 3);
            if (result.some((item) => item.actionId === sample.expected)) {
                hit += 1;
            }
        }

        return hit / samples.length;
    }

    private bindEvents(): void {
        document.addEventListener('quick-action-executed', (event) => {
            const detail = (event as CustomEvent<{ actionId: string }>).detail;
            if (!detail?.actionId) {
                return;
            }
            this.recordAction(detail.actionId);
        });

        document.addEventListener('wizard-completed', (event) => {
            const detail = (event as CustomEvent<{ wizardId: string }>).detail;
            if (!detail?.wizardId) {
                return;
            }
            this.recordAction(`wizard:${detail.wizardId}`);
        });
    }

    private bindCollapseToggle(): void {
        if (!this.root || !this.collapseBtn) {
            return;
        }
        this.collapseBtn.addEventListener('click', () => this.toggleCollapse());
    }

    private toggleCollapse(): void {
        if (!this.root || !this.collapseBtn) {
            return;
        }
        this.isCollapsed = !this.isCollapsed;
        this.root.classList.toggle('collapsed', this.isCollapsed);
        this.collapseBtn.setAttribute('aria-expanded', String(!this.isCollapsed));
    }

    private render(): void {
        if (!this.root || !this.listEl || !this.hintEl) {
            return;
        }

        const context = this.collectContext();
        const recommendations = this.getRecommendations(context, 4);
        const confidence = recommendations[0]?.score || 0;

        const scoreEl = this.root.querySelector('#smart-recommendation-score');
        if (scoreEl) {
            scoreEl.textContent = `${Math.round(confidence * 100)}%`;
        }

        if (this.isBeginner()) {
            this.hintEl.textContent = '检测为新手模式：建议先完成“导入向导”与“插值向导”。';
        } else if (context.includes('can-export')) {
            this.hintEl.textContent = '当前结果可导出，推荐优先执行结果导出。';
        } else {
            this.hintEl.textContent = '根据最近操作习惯和当前上下文生成推荐。';
        }

        if (recommendations.length === 0) {
            this.listEl.innerHTML = '<p class="smart-recommendation-empty">暂无推荐，请先进行几次操作。</p>';
            return;
        }

        this.listEl.innerHTML = recommendations.map((item) => {
            const action = this.actionMap.get(item.actionId);
            if (!action) {
                return '';
            }
            return `
                <button class="smart-recommendation-item" type="button" data-recommend-action="${action.id}">
                    <strong>${action.label}</strong>
                    <span>${item.reason}</span>
                </button>
            `;
        }).join('');

        this.listEl.querySelectorAll('[data-recommend-action]').forEach((node) => {
            node.addEventListener('click', (event) => {
                const id = (event.currentTarget as HTMLElement).getAttribute('data-recommend-action');
                if (!id) {
                    return;
                }
                document.dispatchEvent(new CustomEvent('recommendation-action', {
                    detail: { actionId: id }
                }));
            });
        });
    }

    private collectContext(): string[] {
        const context: string[] = [];

        const fileInput = document.getElementById('file-input') as HTMLInputElement | null;
        if (fileInput?.files && fileInput.files.length > 0) {
            context.push('has-file');
        }

        const startButton = document.getElementById('start-kriging-btn') as HTMLButtonElement | null;
        if (startButton && !startButton.disabled) {
            context.push('can-start-kriging');
        }

        const exportPanel = document.getElementById('export-panel');
        if (exportPanel && exportPanel.style.display !== 'none') {
            context.push('can-export');
        }

        if (this.isBeginner()) {
            context.push('new-user');
        }

        return context;
    }

    private isBeginner(): boolean {
        return this.history.length < 8;
    }

    private getBeginnerActions(): string[] {
        return ['wizard-import-data', 'wizard-interpolation', 'account-info'];
    }

    private getContextScore(actionId: string, context: string[]): number {
        if (context.includes('new-user') && this.getBeginnerActions().includes(actionId)) {
            return 0.9;
        }

        if (!context.includes('has-file') && (actionId === 'import-data' || actionId === 'wizard-import-data')) {
            return 0.95;
        }

        if (context.includes('has-file') && context.includes('can-start-kriging') && actionId === 'start-kriging') {
            return 0.92;
        }

        if (context.includes('can-export') && (actionId === 'export-geojson' || actionId === 'wizard-export')) {
            return 0.9;
        }

        if (actionId === 'wizard-center') {
            return 0.35;
        }

        return 0.2;
    }

    private describeReason(actionId: string, context: string[], frequencyScore: number, contextScore: number): string {
        if (context.includes('new-user') && this.getBeginnerActions().includes(actionId)) {
            return '新手模式推荐';
        }
        if (contextScore >= 0.9) {
            return '与当前状态高度匹配';
        }
        if (frequencyScore > 0.6) {
            return '基于高频历史操作';
        }
        return '综合历史与上下文推荐';
    }

    private loadHistory(): ActionRecord[] {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (!stored) {
                return [];
            }
            const parsed = JSON.parse(stored) as ActionRecord[];
            return Array.isArray(parsed) ? parsed.slice(-MAX_HISTORY) : [];
        } catch {
            return [];
        }
    }

    private saveHistory(): void {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(this.history.slice(-MAX_HISTORY)));
        } catch {
            // ignore storage write error
        }
    }
}

export type { RecommendationSample, ActionRecord };
