import { HistoryManager } from '../utils/HistoryManager.js';

interface WizardFieldOption {
    label: string;
    value: string;
}

type WizardFieldType = 'text' | 'number' | 'select' | 'checkbox';

interface WizardFieldDefinition {
    id: string;
    label: string;
    type: WizardFieldType;
    required?: boolean;
    default?: string | number | boolean;
    placeholder?: string;
    min?: number;
    max?: number;
    step?: number;
    options?: WizardFieldOption[];
}

interface WizardRule {
    field?: string;
    equals?: string | number | boolean;
    context?: string;
    text: string;
}

interface WizardHelp {
    doc?: string;
    video?: string;
}

interface WizardStepDefinition {
    id: string;
    title: string;
    description: string;
    fields: WizardFieldDefinition[];
    recommendationRules?: WizardRule[];
    tips?: string[];
    help?: WizardHelp;
}

interface WizardDefinition {
    id: string;
    title: string;
    description: string;
    help?: WizardHelp;
    steps: WizardStepDefinition[];
}

interface WizardConfig {
    version: string;
    wizards: WizardDefinition[];
}

interface WizardRuntimeState {
    status: 'idle' | 'running' | 'completed' | 'skipped';
    wizard: WizardDefinition | null;
    stepIndex: number;
    values: Record<string, string | number | boolean>;
    context: string[];
}

const CUSTOM_WIZARD_STORAGE_KEY = 'udake_custom_wizards_v1';

function isEmptyValue(value: unknown): boolean {
    return value === undefined || value === null || value === '';
}

function asBoolean(value: unknown): boolean {
    if (typeof value === 'boolean') {
        return value;
    }
    if (typeof value === 'string') {
        return value === 'true';
    }
    return Boolean(value);
}

export class SmartWizardEngine {
    private readonly builtinWizards: WizardDefinition[];
    private customWizards: WizardDefinition[];
    private mounted: boolean;
    private host: HTMLElement | null;
    private overlay: HTMLDivElement | null;
    private centerOverlay: HTMLDivElement | null;
    private state: WizardRuntimeState;

    constructor(config: WizardConfig) {
        this.builtinWizards = config.wizards || [];
        this.customWizards = this.loadCustomWizards();
        this.mounted = false;
        this.host = null;
        this.overlay = null;
        this.centerOverlay = null;
        this.state = {
            status: 'idle',
            wizard: null,
            stepIndex: 0,
            values: {},
            context: []
        };
    }

    public mount(host: HTMLElement = document.body): void {
        if (this.mounted) {
            return;
        }
        this.host = host;
        this.mounted = true;
        this.bindGlobalEvents();
    }

    public destroy(): void {
        this.overlay?.remove();
        this.centerOverlay?.remove();
        this.overlay = null;
        this.centerOverlay = null;
        this.host = null;
        this.mounted = false;
    }

    public getWizardList(): WizardDefinition[] {
        return [...this.builtinWizards, ...this.customWizards];
    }

    public getState(): WizardRuntimeState {
        return {
            status: this.state.status,
            wizard: this.state.wizard,
            stepIndex: this.state.stepIndex,
            values: { ...this.state.values },
            context: [...this.state.context]
        };
    }

    public start(wizardId: string, context: string[] = []): boolean {
        const wizard = this.getWizardList().find((item) => item.id === wizardId);
        if (!wizard) {
            return false;
        }

        this.state = {
            status: 'running',
            wizard,
            stepIndex: 0,
            values: this.createInitialValues(wizard),
            context
        };

        this.ensureOverlay();
        this.renderWizard();

        HistoryManager.record({
            action: `启动向导：${wizard.title}`,
            type: 'setting',
            detail: `向导标识 ${wizard.id}`,
            undoable: false
        });

        return true;
    }

    public openWizardCenter(): void {
        if (!this.host) {
            return;
        }

        if (this.centerOverlay) {
            this.centerOverlay.remove();
            this.centerOverlay = null;
            return;
        }

        this.centerOverlay = document.createElement('div');
        this.centerOverlay.className = 'wizard-center-overlay';

        const wizardCards = this.getWizardList().map((wizard) => `
            <article class="wizard-center-card">
                <h4>${wizard.title}</h4>
                <p>${wizard.description}</p>
                <div class="wizard-center-card-actions">
                    <button type="button" data-center-start="${wizard.id}">启动</button>
                    ${this.isCustomWizard(wizard.id) ? `<button type="button" data-center-remove="${wizard.id}">删除</button>` : ''}
                </div>
            </article>
        `).join('');

        this.centerOverlay.innerHTML = `
            <div class="wizard-center-modal" role="dialog" aria-modal="true" aria-label="向导中心">
                <header class="wizard-center-header">
                    <h3>智能向导中心</h3>
                    <button type="button" class="wizard-center-close">✕</button>
                </header>
                <p class="wizard-center-subtitle">可启动系统向导，也可导入自定义向导 JSON。</p>
                <section class="wizard-center-grid">${wizardCards}</section>
                <section class="wizard-center-custom">
                    <h4>导入自定义向导</h4>
                    <p>格式支持单个向导对象或 <code>{"wizards":[...]}</code>。</p>
                    <textarea id="wizard-custom-json" rows="7" placeholder='{"id":"my-flow","title":"我的向导","description":"...","steps":[]}'>
                    </textarea>
                    <div class="wizard-center-card-actions">
                        <button type="button" id="wizard-custom-save">保存自定义向导</button>
                    </div>
                </section>
            </div>
        `;

        this.host.appendChild(this.centerOverlay);

        this.centerOverlay.querySelector('.wizard-center-close')?.addEventListener('click', () => {
            this.centerOverlay?.remove();
            this.centerOverlay = null;
        });

        this.centerOverlay.addEventListener('click', (event) => {
            if (event.target === this.centerOverlay) {
                this.centerOverlay?.remove();
                this.centerOverlay = null;
            }
        });

        this.centerOverlay.querySelectorAll('[data-center-start]').forEach((button) => {
            button.addEventListener('click', (event) => {
                const id = (event.currentTarget as HTMLElement).getAttribute('data-center-start');
                if (!id) {
                    return;
                }
                this.centerOverlay?.remove();
                this.centerOverlay = null;
                this.start(id, this.resolveRuntimeContext());
            });
        });

        this.centerOverlay.querySelectorAll('[data-center-remove]').forEach((button) => {
            button.addEventListener('click', (event) => {
                const id = (event.currentTarget as HTMLElement).getAttribute('data-center-remove');
                if (!id) {
                    return;
                }
                this.customWizards = this.customWizards.filter((item) => item.id !== id);
                this.saveCustomWizards();
                this.refreshWizardCenter();
            });
        });

        this.centerOverlay.querySelector('#wizard-custom-save')?.addEventListener('click', () => {
            const input = this.centerOverlay?.querySelector('#wizard-custom-json') as HTMLTextAreaElement | null;
            if (!input) {
                return;
            }
            this.importCustomWizard(input.value);
            input.value = '';
            this.refreshWizardCenter();
        });
    }

    public importCustomWizard(payload: string): boolean {
        try {
            const parsed = JSON.parse(payload);
            const parsedWizards = Array.isArray(parsed?.wizards)
                ? parsed.wizards
                : [parsed];
            const normalized = parsedWizards.filter((wizard: WizardDefinition) => this.validateWizard(wizard));
            if (normalized.length === 0) {
                return false;
            }

            for (const wizard of normalized) {
                this.customWizards = this.customWizards.filter((item) => item.id !== wizard.id);
                this.customWizards.push(wizard);
            }

            this.saveCustomWizards();
            HistoryManager.record({
                action: '导入自定义向导',
                type: 'setting',
                detail: `新增/更新 ${normalized.length} 个向导`,
                undoable: false
            });
            return true;
        } catch {
            return false;
        }
    }

    private bindGlobalEvents(): void {
        document.addEventListener('wizard-start', (event) => {
            const detail = (event as CustomEvent<{ wizardId: string; context?: string[] }>).detail;
            if (!detail?.wizardId) {
                return;
            }
            this.start(detail.wizardId, detail.context || this.resolveRuntimeContext());
        });

        document.addEventListener('open-wizard-center', () => {
            this.openWizardCenter();
        });
    }

    private resolveRuntimeContext(): string[] {
        const context: string[] = [];

        const fileInput = document.getElementById('file-input') as HTMLInputElement | null;
        if (fileInput?.files && fileInput.files.length > 0) {
            context.push('has-file');
        }

        const exportPanel = document.getElementById('export-panel');
        if (exportPanel && exportPanel.style.display !== 'none') {
            context.push('can-export');
        }

        const historyCount = HistoryManager.getAll().length;
        if (historyCount < 8) {
            context.push('new-user');
        }

        return context;
    }

    private refreshWizardCenter(): void {
        this.centerOverlay?.remove();
        this.centerOverlay = null;
        this.openWizardCenter();
    }

    private validateWizard(wizard: WizardDefinition): boolean {
        if (!wizard || !wizard.id || !wizard.title || !Array.isArray(wizard.steps)) {
            return false;
        }

        return wizard.steps.every((step) => Boolean(step.id && step.title && Array.isArray(step.fields)));
    }

    private loadCustomWizards(): WizardDefinition[] {
        try {
            const stored = localStorage.getItem(CUSTOM_WIZARD_STORAGE_KEY);
            if (!stored) {
                return [];
            }
            const parsed = JSON.parse(stored) as WizardDefinition[];
            return Array.isArray(parsed) ? parsed.filter((wizard) => this.validateWizard(wizard)) : [];
        } catch {
            return [];
        }
    }

    private saveCustomWizards(): void {
        try {
            localStorage.setItem(CUSTOM_WIZARD_STORAGE_KEY, JSON.stringify(this.customWizards));
        } catch {
            // ignore
        }
    }

    private isCustomWizard(wizardId: string): boolean {
        return this.customWizards.some((item) => item.id === wizardId);
    }

    private createInitialValues(wizard: WizardDefinition): Record<string, string | number | boolean> {
        const values: Record<string, string | number | boolean> = {};
        wizard.steps.forEach((step) => {
            step.fields.forEach((field) => {
                if (field.default !== undefined) {
                    values[field.id] = field.default;
                }
            });
        });
        return values;
    }

    private ensureOverlay(): void {
        if (!this.host) {
            return;
        }

        if (this.overlay) {
            this.overlay.remove();
        }

        this.overlay = document.createElement('div');
        this.overlay.className = 'smart-wizard-overlay';
        this.host.appendChild(this.overlay);

        this.overlay.addEventListener('click', (event) => {
            if (event.target === this.overlay) {
                this.skip();
            }
        });
    }

    private renderWizard(): void {
        if (!this.overlay || !this.state.wizard) {
            return;
        }

        const wizard = this.state.wizard;
        const step = wizard.steps[this.state.stepIndex];
        const total = wizard.steps.length;
        const isLast = this.state.stepIndex === total - 1;
        const progressPercent = Math.round(((this.state.stepIndex + 1) / total) * 100);
        const recommendationText = this.resolveStepRecommendation(step);
        const tips = step.tips || [];
        const help = step.help || wizard.help;

        const fieldsHtml = step.fields.map((field) => this.renderField(field)).join('');
        const tipsHtml = tips.length > 0
            ? `<ul class="smart-wizard-tips">${tips.map((tip) => `<li>${tip}</li>`).join('')}</ul>`
            : '';
        const helpHtml = help
            ? `
                <div class="smart-wizard-help-links">
                    ${help.doc ? `<a href="${help.doc}" target="_blank" rel="noreferrer">帮助文档</a>` : ''}
                    ${help.video ? `<a href="${help.video}" target="_blank" rel="noreferrer">视频教程</a>` : ''}
                </div>
            `
            : '';

        this.overlay.innerHTML = `
            <div class="smart-wizard-modal" role="dialog" aria-modal="true" aria-label="${wizard.title}">
                <header class="smart-wizard-header">
                    <div>
                        <h3>${wizard.title}</h3>
                        <p>${wizard.description}</p>
                    </div>
                    <button type="button" class="smart-wizard-close">✕</button>
                </header>
                <div class="smart-wizard-progress">
                    <span>步骤 ${this.state.stepIndex + 1} / ${total}</span>
                    <div class="smart-wizard-progress-track">
                        <div class="smart-wizard-progress-fill" style="width:${progressPercent}%"></div>
                    </div>
                </div>
                <section class="smart-wizard-step">
                    <h4>${step.title}</h4>
                    <p>${step.description}</p>
                    <div class="smart-wizard-fields">${fieldsHtml}</div>
                    ${recommendationText ? `<div class="smart-wizard-recommendation">💡 ${recommendationText}</div>` : ''}
                    ${tipsHtml}
                    ${helpHtml}
                </section>
                <footer class="smart-wizard-actions">
                    <button type="button" class="smart-wizard-skip">跳过</button>
                    <div class="smart-wizard-main-actions">
                        <button type="button" class="smart-wizard-prev" ${this.state.stepIndex === 0 ? 'disabled' : ''}>上一步</button>
                        <button type="button" class="smart-wizard-next">${isLast ? '完成' : '下一步'}</button>
                    </div>
                </footer>
                <p class="smart-wizard-error" aria-live="polite"></p>
            </div>
        `;

        this.overlay.querySelector('.smart-wizard-close')?.addEventListener('click', () => this.skip());
        this.overlay.querySelector('.smart-wizard-skip')?.addEventListener('click', () => this.skip());
        this.overlay.querySelector('.smart-wizard-prev')?.addEventListener('click', () => this.prev());
        this.overlay.querySelector('.smart-wizard-next')?.addEventListener('click', () => {
            if (isLast) {
                this.complete();
                return;
            }
            this.next();
        });

        this.overlay.querySelectorAll('[data-wizard-field]').forEach((element) => {
            element.addEventListener('input', (event) => this.handleFieldInput(event));
            element.addEventListener('change', (event) => this.handleFieldInput(event));
        });
    }

    private renderField(field: WizardFieldDefinition): string {
        const value = this.state.values[field.id] ?? field.default;
        const requiredMark = field.required ? '<span class="required">*</span>' : '';

        if (field.type === 'checkbox') {
            return `
                <label class="smart-wizard-field checkbox-field">
                    <input
                        type="checkbox"
                        data-wizard-field="${field.id}"
                        ${asBoolean(value) ? 'checked' : ''}
                    >
                    <span>${field.label}${requiredMark}</span>
                </label>
            `;
        }

        if (field.type === 'select') {
            const optionsHtml = (field.options || []).map((option) => `
                <option value="${option.value}" ${String(value) === option.value ? 'selected' : ''}>${option.label}</option>
            `).join('');
            return `
                <label class="smart-wizard-field">
                    <span>${field.label}${requiredMark}</span>
                    <select data-wizard-field="${field.id}">${optionsHtml}</select>
                </label>
            `;
        }

        const inputType = field.type === 'number' ? 'number' : 'text';
        const minAttr = field.min !== undefined ? `min="${field.min}"` : '';
        const maxAttr = field.max !== undefined ? `max="${field.max}"` : '';
        const stepAttr = field.step !== undefined ? `step="${field.step}"` : '';

        return `
            <label class="smart-wizard-field">
                <span>${field.label}${requiredMark}</span>
                <input
                    type="${inputType}"
                    data-wizard-field="${field.id}"
                    value="${value ?? ''}"
                    placeholder="${field.placeholder || ''}"
                    ${minAttr}
                    ${maxAttr}
                    ${stepAttr}
                >
            </label>
        `;
    }

    private handleFieldInput(event: Event): void {
        const element = event.currentTarget as HTMLInputElement | HTMLSelectElement | null;
        if (!element) {
            return;
        }

        const fieldId = element.getAttribute('data-wizard-field');
        if (!fieldId || !this.state.wizard) {
            return;
        }

        const fieldDefinition = this.state.wizard.steps
            .flatMap((step) => step.fields)
            .find((field) => field.id === fieldId);
        if (!fieldDefinition) {
            return;
        }

        if (fieldDefinition.type === 'checkbox') {
            this.state.values[fieldId] = (element as HTMLInputElement).checked;
        } else if (fieldDefinition.type === 'number') {
            const nextValue = Number(element.value);
            this.state.values[fieldId] = Number.isNaN(nextValue) ? 0 : nextValue;
        } else {
            this.state.values[fieldId] = element.value;
        }

        this.renderWizard();
    }

    private resolveStepRecommendation(step: WizardStepDefinition): string {
        const rules = step.recommendationRules || [];
        for (const rule of rules) {
            if (rule.context && this.state.context.includes(rule.context)) {
                return rule.text;
            }

            if (rule.field) {
                const currentValue = this.state.values[rule.field];
                if (rule.equals === undefined || currentValue === rule.equals) {
                    return rule.text;
                }
            }
        }

        if (this.state.context.includes('new-user')) {
            return '首次使用建议逐步确认参数，完成后再批量执行。';
        }

        return '';
    }

    private next(): void {
        if (!this.state.wizard) {
            return;
        }

        const step = this.state.wizard.steps[this.state.stepIndex];
        const error = this.validateStep(step);
        if (error) {
            this.showError(error);
            return;
        }

        this.state.stepIndex += 1;
        this.renderWizard();
    }

    private prev(): void {
        if (this.state.stepIndex <= 0) {
            return;
        }
        this.state.stepIndex -= 1;
        this.renderWizard();
    }

    private complete(): void {
        if (!this.state.wizard) {
            return;
        }

        const step = this.state.wizard.steps[this.state.stepIndex];
        const error = this.validateStep(step);
        if (error) {
            this.showError(error);
            return;
        }

        const wizardId = this.state.wizard.id;
        const values = { ...this.state.values };

        HistoryManager.record({
            action: `完成向导：${this.state.wizard.title}`,
            type: 'setting',
            detail: `共 ${this.state.wizard.steps.length} 步`,
            undoable: false
        });

        this.state.status = 'completed';
        this.overlay?.remove();
        this.overlay = null;

        document.dispatchEvent(new CustomEvent('wizard-completed', {
            detail: {
                wizardId,
                values,
                context: [...this.state.context]
            }
        }));
    }

    private skip(): void {
        if (!this.state.wizard) {
            this.overlay?.remove();
            this.overlay = null;
            return;
        }

        HistoryManager.record({
            action: `跳过向导：${this.state.wizard.title}`,
            type: 'setting',
            detail: '用户手动跳过向导流程',
            undoable: false
        });

        const wizardId = this.state.wizard.id;
        this.state.status = 'skipped';
        this.overlay?.remove();
        this.overlay = null;

        document.dispatchEvent(new CustomEvent('wizard-skipped', {
            detail: {
                wizardId,
                context: [...this.state.context]
            }
        }));
    }

    private validateStep(step: WizardStepDefinition): string {
        for (const field of step.fields) {
            if (!field.required) {
                continue;
            }
            const value = this.state.values[field.id];
            if (isEmptyValue(value)) {
                return `请先填写「${field.label}」`;
            }
        }
        return '';
    }

    private showError(message: string): void {
        const errorEl = this.overlay?.querySelector('.smart-wizard-error') as HTMLElement | null;
        if (errorEl) {
            errorEl.textContent = message;
        }
    }
}
