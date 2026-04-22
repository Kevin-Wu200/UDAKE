import { KeyboardManager } from '../utils/KeyboardManager.js';
import { HistoryManager } from '../utils/HistoryManager.js';
import { I18n } from '../utils/I18n.js';

const t = (key: string, params?: Record<string, string | number>): string => I18n.t(key, params);

export interface QuickActionShortcut {
    key: string;
    ctrl?: boolean;
    shift?: boolean;
}

export interface QuickActionItem {
    id: string;
    label: string;
    icon: string;
    description: string;
    command: string;
    category: 'project' | 'sampling' | 'interpolation' | 'export' | 'guide' | 'history';
    defaultVisible: boolean;
    shortcut?: QuickActionShortcut;
}

interface QuickActionDefinition extends Omit<QuickActionItem, 'label' | 'description'> {
    labelKey: string;
    descriptionKey: string;
}

interface QuickActionBarState {
    order: string[];
    hidden: string[];
}

const STORAGE_KEY = 'udake_quick_action_bar_state_v1';

function shortcutToText(shortcut?: QuickActionShortcut): string {
    if (!shortcut) {
        return '';
    }

    const keys: string[] = [];
    if (shortcut.ctrl) {
        keys.push('Ctrl');
    }
    if (shortcut.shift) {
        keys.push('Shift');
    }
    keys.push(shortcut.key.length === 1 ? shortcut.key.toUpperCase() : shortcut.key);
    return keys.join(' + ');
}

function getDefaultActions(): QuickActionDefinition[] {
    return [
        {
            id: 'new-project',
            labelKey: 'quickaction.newProject',
            icon: '📁',
            descriptionKey: 'description.newProject',
            command: 'new-project',
            category: 'project',
            defaultVisible: true,
            shortcut: { key: '1', ctrl: true, shift: true }
        },
        {
            id: 'import-data',
            labelKey: 'quickaction.importData',
            icon: '📤',
            descriptionKey: 'description.importData',
            command: 'import-data',
            category: 'project',
            defaultVisible: true,
            shortcut: { key: '2', ctrl: true, shift: true }
        },
        {
            id: 'wizard-import-data',
            labelKey: 'quickaction.importWizard',
            icon: '🧭',
            descriptionKey: 'description.importWizard',
            command: 'wizard-start:data-import',
            category: 'guide',
            defaultVisible: true,
            shortcut: { key: '3', ctrl: true, shift: true }
        },
        {
            id: 'wizard-sampling',
            labelKey: 'quickaction.samplingWizard',
            icon: '📍',
            descriptionKey: 'description.samplingWizard',
            command: 'wizard-start:sampling-optimization',
            category: 'sampling',
            defaultVisible: true,
            shortcut: { key: '4', ctrl: true, shift: true }
        },
        {
            id: 'wizard-interpolation',
            labelKey: 'quickaction.interpolationWizard',
            icon: '🌐',
            descriptionKey: 'description.interpolationWizard',
            command: 'wizard-start:interpolation-analysis',
            category: 'interpolation',
            defaultVisible: true,
            shortcut: { key: '5', ctrl: true, shift: true }
        },
        {
            id: 'wizard-export',
            labelKey: 'quickaction.exportWizard',
            icon: '📦',
            descriptionKey: 'description.exportWizard',
            command: 'wizard-start:result-export',
            category: 'export',
            defaultVisible: true,
            shortcut: { key: '6', ctrl: true, shift: true }
        },
        {
            id: 'wizard-mobile',
            labelKey: 'quickaction.mobileWizard',
            icon: '📱',
            descriptionKey: 'description.mobileWizard',
            command: 'wizard-start:mobile-collection',
            category: 'guide',
            defaultVisible: false,
            shortcut: { key: '7', ctrl: true, shift: true }
        },
        {
            id: 'start-kriging',
            labelKey: 'quickaction.startKriging',
            icon: '▶',
            descriptionKey: 'description.startKriging',
            command: 'start-kriging',
            category: 'interpolation',
            defaultVisible: true,
            shortcut: { key: '8', ctrl: true, shift: true }
        },
        {
            id: 'export-geojson',
            labelKey: 'quickaction.exportGeoJSON',
            icon: '💾',
            descriptionKey: 'description.exportGeoJSON',
            command: 'export-geojson',
            category: 'export',
            defaultVisible: true,
            shortcut: { key: '9', ctrl: true, shift: true }
        },
        {
            id: 'account-info',
            labelKey: 'quickaction.accountInfo',
            icon: '👤',
            descriptionKey: 'description.accountInfo',
            command: 'show-account-info',
            category: 'guide',
            defaultVisible: true,
            shortcut: { key: '0', ctrl: true, shift: true }
        },
        {
            id: 'history-undo',
            labelKey: 'quickaction.undoHistory',
            icon: '↩',
            descriptionKey: 'description.undoHistory',
            command: 'history-undo',
            category: 'history',
            defaultVisible: true,
            shortcut: { key: 'u', ctrl: true, shift: true }
        },
        {
            id: 'history-redo',
            labelKey: 'quickaction.redoHistory',
            icon: '↪',
            descriptionKey: 'description.redoHistory',
            command: 'history-redo',
            category: 'history',
            defaultVisible: true,
            shortcut: { key: 'r', ctrl: true, shift: true }
        },
        {
            id: 'wizard-center',
            labelKey: 'quickaction.wizardCenter',
            icon: '🗂',
            descriptionKey: 'description.wizardCenter',
            command: 'open-wizard-center',
            category: 'guide',
            defaultVisible: true
        }
    ];
}

export class QuickActionBar {
    private readonly actions: QuickActionDefinition[];
    private state: QuickActionBarState;
    private root: HTMLDivElement | null;
    private actionsContainer: HTMLDivElement | null;
    private settingsPanel: HTMLDivElement | null;
    private dragActionId: string | null;
    private readonly unsubscribeLocaleChange: (() => void) | null;

    constructor(actions: QuickActionDefinition[] = getDefaultActions()) {
        this.actions = actions;
        this.state = this.loadState();
        this.root = null;
        this.actionsContainer = null;
        this.settingsPanel = null;
        this.dragActionId = null;
        this.unsubscribeLocaleChange = I18n.onChange(() => {
            this.refreshUI();
        });
    }

    public mount(container: HTMLElement): void {
        if (this.root) {
            return;
        }

        this.root = document.createElement('div');
        this.root.className = 'quick-action-bar';

        const title = document.createElement('div');
        title.className = 'quick-action-bar-title';
        title.textContent = t('quickaction.title');

        this.actionsContainer = document.createElement('div');
        this.actionsContainer.className = 'quick-action-list';

        const settingsBtn = document.createElement('button');
        settingsBtn.className = 'quick-action-settings-btn';
        settingsBtn.type = 'button';
        settingsBtn.title = t('quickaction.settings.title');
        settingsBtn.textContent = '⚙';
        settingsBtn.addEventListener('click', () => this.toggleSettingsPanel());

        this.root.append(title, this.actionsContainer, settingsBtn);
        container.appendChild(this.root);

        this.renderActions();
        this.registerShortcuts();
        this.installOutsideClickGuard();
    }

    public getActions(): QuickActionItem[] {
        return this.actions.map((action) => this.resolveAction(action));
    }

    public destroy(): void {
        this.unsubscribeLocaleChange?.();
        this.settingsPanel?.remove();
        this.root?.remove();
        this.settingsPanel = null;
        this.root = null;
        this.actionsContainer = null;
    }

    private loadState(): QuickActionBarState {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                const parsed = JSON.parse(stored) as QuickActionBarState;
                if (Array.isArray(parsed.order) && Array.isArray(parsed.hidden)) {
                    return parsed;
                }
            }
        } catch {
            // ignore malformed storage
        }

        return {
            order: this.actions.map((item) => item.id),
            hidden: this.actions.filter((item) => !item.defaultVisible).map((item) => item.id)
        };
    }

    private saveState(): void {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(this.state));
        } catch {
            // ignore storage error
        }
    }

    private resolveAction(action: QuickActionDefinition): QuickActionItem {
        return {
            ...action,
            label: t(action.labelKey),
            description: t(action.descriptionKey)
        };
    }

    private refreshUI(): void {
        if (!this.root) {
            return;
        }

        const title = this.root.querySelector('.quick-action-bar-title');
        if (title) {
            title.textContent = t('quickaction.title');
        }

        const settingsBtn = this.root.querySelector('.quick-action-settings-btn') as HTMLButtonElement | null;
        if (settingsBtn) {
            settingsBtn.title = t('quickaction.settings.title');
        }

        this.renderActions();

        if (this.settingsPanel) {
            this.hideSettingsPanel();
            this.toggleSettingsPanel();
        }
    }

    private registerShortcuts(): void {
        for (const action of this.actions) {
            const resolvedAction = this.resolveAction(action);
            if (!action.shortcut) {
                continue;
            }

            KeyboardManager.register({
                key: action.shortcut.key,
                ctrl: action.shortcut.ctrl,
                shift: action.shortcut.shift,
                description: `${t('quickaction.label')}${resolvedAction.label}`,
                handler: () => this.triggerAction(action.id, 'shortcut')
            });
        }
    }

    private getVisibleActionIds(): string[] {
        return this.state.order.filter((id) => !this.state.hidden.includes(id));
    }

    private getActionById(actionId: string): QuickActionItem | null {
        const action = this.actions.find((item) => item.id === actionId);
        return action ? this.resolveAction(action) : null;
    }

    private renderActions(): void {
        if (!this.actionsContainer) {
            return;
        }

        this.actionsContainer.innerHTML = '';
        const visibleIds = this.getVisibleActionIds();

        for (const actionId of visibleIds) {
            const action = this.getActionById(actionId);
            if (!action) {
                continue;
            }

            const button = document.createElement('button');
            button.className = 'quick-action-btn';
            button.type = 'button';
            button.draggable = true;
            button.dataset.actionId = action.id;
            button.title = `${action.label}${action.shortcut ? ` (${shortcutToText(action.shortcut)})` : ''}`;
            button.innerHTML = `
                <span class="quick-action-icon" aria-hidden="true">${action.icon}</span>
                <span class="quick-action-label">${action.label}</span>
            `;

            button.addEventListener('click', () => this.triggerAction(action.id, 'click'));
            button.addEventListener('dragstart', (event) => {
                this.dragActionId = action.id;
                if (event.dataTransfer) {
                    event.dataTransfer.effectAllowed = 'move';
                    event.dataTransfer.setData('text/plain', action.id);
                }
                button.classList.add('dragging');
            });
            button.addEventListener('dragend', () => {
                this.dragActionId = null;
                button.classList.remove('dragging');
                this.actionsContainer?.querySelectorAll('.quick-action-btn').forEach((node) => {
                    node.classList.remove('drag-over');
                });
            });
            button.addEventListener('dragover', (event) => {
                event.preventDefault();
                button.classList.add('drag-over');
            });
            button.addEventListener('dragleave', () => {
                button.classList.remove('drag-over');
            });
            button.addEventListener('drop', (event) => {
                event.preventDefault();
                button.classList.remove('drag-over');
                const sourceId = this.dragActionId || event.dataTransfer?.getData('text/plain');
                if (!sourceId || sourceId === action.id) {
                    return;
                }
                this.reorder(sourceId, action.id);
            });

            this.actionsContainer.appendChild(button);
        }
    }

    private reorder(sourceId: string, targetId: string): void {
        const currentOrder = [...this.state.order];
        const sourceIndex = currentOrder.indexOf(sourceId);
        const targetIndex = currentOrder.indexOf(targetId);

        if (sourceIndex < 0 || targetIndex < 0) {
            return;
        }

        currentOrder.splice(sourceIndex, 1);
        currentOrder.splice(targetIndex, 0, sourceId);
        this.state.order = currentOrder;

        this.saveState();
        this.renderActions();

        HistoryManager.record({
            action: t('quickaction.Sequence'),
            type: 'setting',
            detail: t('quickaction.haveSequenced', {
                sourceId,
                targetId
            }),
            undoable: false
        });
    }

    private triggerAction(actionId: string, source: 'click' | 'shortcut' | 'recommendation'): void {
        const action = this.getActionById(actionId);
        if (!action) {
            return;
        }

        HistoryManager.record({
            action: t('quickaction.triggerAction', {
                action: action.label
            }),
            type: action.category === 'export' ? 'export' : action.category === 'interpolation' ? 'kriging' : 'setting',
            detail: t('quickaction.triggeredBy', {
                source: t(
                    source === 'click' ? 'quickaction.source.click'
                    : source === 'shortcut' ? 'quickaction.source.shortcut'
                    : 'quickaction.source.recommend'
                )
            }),
            undoable: false
        });

        document.dispatchEvent(new CustomEvent('quick-action-request', {
            detail: {
                actionId: action.id,
                command: action.command,
                source
            }
        }));

        document.dispatchEvent(new CustomEvent('quick-action-executed', {
            detail: {
                actionId: action.id,
                source
            }
        }));
    }

    private toggleSettingsPanel(): void {
        if (this.settingsPanel) {
            this.hideSettingsPanel();
            return;
        }

        this.settingsPanel = document.createElement('div');
        this.settingsPanel.className = 'quick-action-settings';

        const listHtml = this.state.order.map((actionId) => {
            const action = this.getActionById(actionId);
            if (!action) {
                return '';
            }
            const checked = this.state.hidden.includes(action.id) ? '' : 'checked';
            const shortcutText = shortcutToText(action.shortcut);
            return `
                <label class="quick-action-setting-item">
                    <input type="checkbox" data-action-toggle="${action.id}" ${checked}>
                    <span class="quick-action-setting-title">${action.icon} ${action.label}</span>
                    <span class="quick-action-setting-shortcut">${shortcutText}</span>
                </label>
            `;
        }).join('');

        this.settingsPanel.innerHTML = `
            <div class="quick-action-settings-header">
                <strong>${t('quickaction.settings.title')}</strong>
                <button type="button" class="quick-action-settings-close">✕</button>
            </div>
            <p class="quick-action-settings-tip">${t('quickaction.settings.tip')}</p>
            <div class="quick-action-settings-list">${listHtml}</div>
            <div class="quick-action-settings-actions">
                <button type="button" class="quick-action-settings-reset">${t('quickaction.settings.reset')}</button>
            </div>
        `;

        this.settingsPanel.querySelector('.quick-action-settings-close')?.addEventListener('click', () => {
            this.hideSettingsPanel();
        });

        this.settingsPanel.querySelector('.quick-action-settings-reset')?.addEventListener('click', () => {
            this.state = {
                order: this.actions.map((item) => item.id),
                hidden: this.actions.filter((item) => !item.defaultVisible).map((item) => item.id)
            };
            this.saveState();
            this.hideSettingsPanel();
            this.renderActions();
        });

        this.settingsPanel.querySelectorAll('input[data-action-toggle]').forEach((input) => {
            input.addEventListener('change', (event) => {
                const target = event.currentTarget as HTMLInputElement;
                const id = target.dataset.actionToggle;
                if (!id) {
                    return;
                }

                if (target.checked) {
                    this.state.hidden = this.state.hidden.filter((hiddenId) => hiddenId !== id);
                } else if (!this.state.hidden.includes(id)) {
                    this.state.hidden.push(id);
                }

                this.saveState();
                this.renderActions();
            });
        });

        this.root?.appendChild(this.settingsPanel);
    }

    private hideSettingsPanel(): void {
        this.settingsPanel?.remove();
        this.settingsPanel = null;
    }

    private installOutsideClickGuard(): void {
        document.addEventListener('click', (event) => {
            if (!this.settingsPanel || !this.root) {
                return;
            }
            const target = event.target as Node;
            if (!this.root.contains(target)) {
                this.hideSettingsPanel();
            }
        });

        document.addEventListener('recommendation-action', (event) => {
            const detail = (event as CustomEvent<{ actionId: string }>).detail;
            if (!detail?.actionId) {
                return;
            }
            this.triggerAction(detail.actionId, 'recommendation');
        });
    }
}
