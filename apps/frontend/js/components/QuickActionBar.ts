import { KeyboardManager } from '../utils/KeyboardManager.js';
import { HistoryManager } from '../utils/HistoryManager.js';

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

function getDefaultActions(): QuickActionItem[] {
    return [
        {
            id: 'new-project',
            label: '新建项目',
            icon: '📁',
            description: '快速创建新的采样项目',
            command: 'new-project',
            category: 'project',
            defaultVisible: true,
            shortcut: { key: '1', ctrl: true, shift: true }
        },
        {
            id: 'import-data',
            label: '导入数据',
            icon: '📤',
            description: '打开文件选择框进行数据导入',
            command: 'import-data',
            category: 'project',
            defaultVisible: true,
            shortcut: { key: '2', ctrl: true, shift: true }
        },
        {
            id: 'wizard-import-data',
            label: '导入向导',
            icon: '🧭',
            description: '打开数据导入向导',
            command: 'wizard-start:data-import',
            category: 'guide',
            defaultVisible: true,
            shortcut: { key: '3', ctrl: true, shift: true }
        },
        {
            id: 'wizard-sampling',
            label: '采样向导',
            icon: '📍',
            description: '打开采样优化向导',
            command: 'wizard-start:sampling-optimization',
            category: 'sampling',
            defaultVisible: true,
            shortcut: { key: '4', ctrl: true, shift: true }
        },
        {
            id: 'wizard-interpolation',
            label: '插值向导',
            icon: '🌐',
            description: '打开插值分析向导',
            command: 'wizard-start:interpolation-analysis',
            category: 'interpolation',
            defaultVisible: true,
            shortcut: { key: '5', ctrl: true, shift: true }
        },
        {
            id: 'wizard-export',
            label: '导出向导',
            icon: '📦',
            description: '打开结果导出向导',
            command: 'wizard-start:result-export',
            category: 'export',
            defaultVisible: true,
            shortcut: { key: '6', ctrl: true, shift: true }
        },
        {
            id: 'wizard-mobile',
            label: '移动采集向导',
            icon: '📱',
            description: '打开移动端采集向导',
            command: 'wizard-start:mobile-collection',
            category: 'guide',
            defaultVisible: false,
            shortcut: { key: '7', ctrl: true, shift: true }
        },
        {
            id: 'start-kriging',
            label: '开始插值',
            icon: '▶',
            description: '执行当前参数下的插值任务',
            command: 'start-kriging',
            category: 'interpolation',
            defaultVisible: true,
            shortcut: { key: '8', ctrl: true, shift: true }
        },
        {
            id: 'export-geojson',
            label: '导出GeoJSON',
            icon: '💾',
            description: '导出预测结果 GeoJSON',
            command: 'export-geojson',
            category: 'export',
            defaultVisible: true,
            shortcut: { key: '9', ctrl: true, shift: true }
        },
        {
            id: 'account-info',
            label: '账户信息',
            icon: '👤',
            description: '查看当前账户和密钥状态',
            command: 'show-account-info',
            category: 'guide',
            defaultVisible: true,
            shortcut: { key: '0', ctrl: true, shift: true }
        },
        {
            id: 'history-undo',
            label: '撤销',
            icon: '↩',
            description: '撤销最近可撤销操作',
            command: 'history-undo',
            category: 'history',
            defaultVisible: true,
            shortcut: { key: 'u', ctrl: true, shift: true }
        },
        {
            id: 'history-redo',
            label: '重做',
            icon: '↪',
            description: '重做最近已撤销操作',
            command: 'history-redo',
            category: 'history',
            defaultVisible: true,
            shortcut: { key: 'r', ctrl: true, shift: true }
        },
        {
            id: 'wizard-center',
            label: '向导中心',
            icon: '🗂',
            description: '打开向导中心并管理自定义向导',
            command: 'open-wizard-center',
            category: 'guide',
            defaultVisible: true
        }
    ];
}

export class QuickActionBar {
    private readonly actions: QuickActionItem[];
    private state: QuickActionBarState;
    private root: HTMLDivElement | null;
    private actionsContainer: HTMLDivElement | null;
    private settingsPanel: HTMLDivElement | null;
    private dragActionId: string | null;

    constructor(actions: QuickActionItem[] = getDefaultActions()) {
        this.actions = actions;
        this.state = this.loadState();
        this.root = null;
        this.actionsContainer = null;
        this.settingsPanel = null;
        this.dragActionId = null;
    }

    public mount(container: HTMLElement): void {
        if (this.root) {
            return;
        }

        this.root = document.createElement('div');
        this.root.className = 'quick-action-bar';

        const title = document.createElement('div');
        title.className = 'quick-action-bar-title';
        title.textContent = '快捷操作栏';

        this.actionsContainer = document.createElement('div');
        this.actionsContainer.className = 'quick-action-list';

        const settingsBtn = document.createElement('button');
        settingsBtn.className = 'quick-action-settings-btn';
        settingsBtn.type = 'button';
        settingsBtn.title = '自定义快捷操作栏';
        settingsBtn.textContent = '⚙';
        settingsBtn.addEventListener('click', () => this.toggleSettingsPanel());

        this.root.append(title, this.actionsContainer, settingsBtn);
        container.appendChild(this.root);

        this.renderActions();
        this.registerShortcuts();
        this.installOutsideClickGuard();
    }

    public getActions(): QuickActionItem[] {
        return [...this.actions];
    }

    public destroy(): void {
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

    private registerShortcuts(): void {
        for (const action of this.actions) {
            if (!action.shortcut) {
                continue;
            }

            KeyboardManager.register({
                key: action.shortcut.key,
                ctrl: action.shortcut.ctrl,
                shift: action.shortcut.shift,
                description: `快捷栏：${action.label}`,
                handler: () => this.triggerAction(action.id, 'shortcut')
            });
        }
    }

    private getVisibleActionIds(): string[] {
        return this.state.order.filter((id) => !this.state.hidden.includes(id));
    }

    private getActionById(actionId: string): QuickActionItem | null {
        return this.actions.find((item) => item.id === actionId) || null;
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
            action: '快捷栏排序调整',
            type: 'setting',
            detail: `已将 ${sourceId} 调整到 ${targetId} 前后位置`,
            undoable: false
        });
    }

    private triggerAction(actionId: string, source: 'click' | 'shortcut' | 'recommendation'): void {
        const action = this.getActionById(actionId);
        if (!action) {
            return;
        }

        HistoryManager.record({
            action: `快捷操作：${action.label}`,
            type: action.category === 'export' ? 'export' : action.category === 'interpolation' ? 'kriging' : 'setting',
            detail: `通过${source === 'click' ? '点击' : source === 'shortcut' ? '快捷键' : '推荐'}触发`,
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
                <strong>自定义快捷操作栏</strong>
                <button type="button" class="quick-action-settings-close">✕</button>
            </div>
            <p class="quick-action-settings-tip">拖拽按钮可排序，勾选开关控制显示。</p>
            <div class="quick-action-settings-list">${listHtml}</div>
            <div class="quick-action-settings-actions">
                <button type="button" class="quick-action-settings-reset">恢复默认</button>
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
