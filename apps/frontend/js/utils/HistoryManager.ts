import { I18n } from './I18n.js';

/**
 * 操作历史记录管理器
 * 记录用户操作、支持撤销/重做、历史查看和搜索
 */

interface HistoryEntry {
    id: string;
    action: string;
    type: 'upload' | 'kriging' | 'export' | 'project' | 'point' | 'setting' | 'map';
    detail: string;
    timestamp: number;
    undoable: boolean;
    undoData?: any;
}

type HistoryListener = (entries: HistoryEntry[]) => void;

const STORAGE_KEY = 'udake_history';
const MAX_ENTRIES = 200;

export class HistoryManager {
    private static _entries: HistoryEntry[] = [];
    private static _undoStack: HistoryEntry[] = [];
    private static _redoStack: HistoryEntry[] = [];
    private static _listeners: Set<HistoryListener> = new Set();
    private static _undoHandlers: Map<string, (data: any) => Promise<void>> = new Map();

    static init(): void {
        this._load();
    }

    /** 记录一条操作 */
    static record(entry: Omit<HistoryEntry, 'id' | 'timestamp'>): void {
        const full: HistoryEntry = {
            ...entry,
            id: `${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
            timestamp: Date.now(),
        };
        this._entries.unshift(full);
        if (this._entries.length > MAX_ENTRIES) this._entries.pop();
        if (full.undoable) {
            this._undoStack.push(full);
            this._redoStack.length = 0;
        }
        this._save();
        this._notify();
    }

    /** 撤销最近的可撤销操作 */
    static async undo(): Promise<boolean> {
        const entry = this._undoStack.pop();
        if (!entry) return false;
        const handler = this._undoHandlers.get(entry.type);
        if (handler && entry.undoData) {
            await handler(entry.undoData);
            this._redoStack.push(entry);
            this.record({
                action: I18n.t('history.undoAction', { action: entry.action }),
                type: entry.type,
                detail: I18n.t('history.undone', { action: entry.action }),
                undoable: false,
            });
            return true;
        }
        return false;
    }

    /** 重做 */
    static async redo(): Promise<boolean> {
        const entry = this._redoStack.pop();
        if (!entry) return false;
        this._undoStack.push(entry);
        this.record({
            action: I18n.t('history.redoAction', { action: entry.action }),
            type: entry.type,
            detail: I18n.t('history.redone', { action: entry.action }),
            undoable: false,
        });
        return true;
    }

    /** 注册撤销处理器 */
    static registerUndoHandler(type: string, handler: (data: any) => Promise<void>): void {
        this._undoHandlers.set(type, handler);
    }

    /** 获取所有历史记录 */
    static getAll(): HistoryEntry[] {
        return [...this._entries];
    }

    /** 搜索历史记录 */
    static search(keyword: string): HistoryEntry[] {
        const kw = keyword.toLowerCase();
        return this._entries.filter(e =>
            e.action.toLowerCase().includes(kw) || e.detail.toLowerCase().includes(kw)
        );
    }

    /** 按类型筛选 */
    static filterByType(type: string): HistoryEntry[] {
        return this._entries.filter(e => e.type === type);
    }

    /** 清除所有历史 */
    static clear(): void {
        this._entries = [];
        this._undoStack = [];
        this._redoStack = [];
        this._save();
        this._notify();
    }

    static canUndo(): boolean { return this._undoStack.length > 0; }
    static canRedo(): boolean { return this._redoStack.length > 0; }

    static onChange(cb: HistoryListener): () => void {
        this._listeners.add(cb);
        return () => { this._listeners.delete(cb); };
    }

    /** 创建历史记录面板 */
    static createPanel(): HTMLElement {
        const panel = document.createElement('div');
        panel.className = 'panel';
        panel.id = 'history-panel-' + Date.now();
        panel.innerHTML = `
            <h2 class="panel-title" data-i18n="history.title">${I18n.t('history.title')}</h2>
            <div class="panel-content">
                <div style="display:flex;gap:8px;margin-bottom:8px;">
                    <button class="btn btn-export" id="history-undo-btn" disabled style="flex:1;height:32px;font-size:12px;" data-i18n="history.undo">${I18n.t('history.undo')}</button>
                    <button class="btn btn-export" id="history-redo-btn" disabled style="flex:1;height:32px;font-size:12px;" data-i18n="history.redo">${I18n.t('history.redo')}</button>
                    <button class="btn btn-export" id="history-clear-btn" style="flex:1;height:32px;font-size:12px;" data-i18n="history.clear">${I18n.t('history.clear')}</button>
                </div>
                <div class="history-list" id="history-list">
                    <p style="color:var(--text-tertiary);font-size:13px;" data-i18n="history.empty">${I18n.t('history.empty')}</p>
                </div>
            </div>
        `;

        const listEl = panel.querySelector('#history-list')!;
        const undoBtn = panel.querySelector('#history-undo-btn') as HTMLButtonElement;
        const redoBtn = panel.querySelector('#history-redo-btn') as HTMLButtonElement;
        const clearBtn = panel.querySelector('#history-clear-btn') as HTMLButtonElement;

        const render = () => {
            const entries = this.getAll().slice(0, 20);
            undoBtn.disabled = !this.canUndo();
            redoBtn.disabled = !this.canRedo();
            if (entries.length === 0) {
                listEl.innerHTML = `<p style="color:var(--text-tertiary);font-size:13px;" data-i18n="history.empty">${I18n.t('history.empty')}</p>`;
                return;
            }
            listEl.innerHTML = entries.map(e => {
                const icons: Record<string, string> = {
                    upload: '📤', kriging: '🔬', export: '📥',
                    project: '📁', point: '📍', setting: '⚙️'
                };
                const time = new Date(e.timestamp);
                const timeStr = `${time.getHours().toString().padStart(2,'0')}:${time.getMinutes().toString().padStart(2,'0')}`;
                return `
                    <div class="history-item">
                        <span class="history-icon ${e.type}">${icons[e.type] || '📋'}</span>
                        <div class="history-info">
                            <span class="history-action">${e.action}</span>
                            <span class="history-time">${timeStr}</span>
                        </div>
                    </div>
                `;
            }).join('');
        };

        this.onChange(render);
        render();

        undoBtn.addEventListener('click', () => this.undo());
        redoBtn.addEventListener('click', () => this.redo());
        clearBtn.addEventListener('click', () => this.clear());

        return panel;
    }

    /** 更新所有历史记录面板的UI文本 */
    static updateUIText(): void {
        // 查找所有历史面板
        const panels = document.querySelectorAll('[id^="history-panel-"]');
        panels.forEach(panel => {
            // 更新标题
            const title = panel.querySelector('.panel-title');
            if (title) {
                title.textContent = I18n.t('history.title');
            }

            // 更新按钮文本
            const undoBtn = panel.querySelector('#history-undo-btn');
            if (undoBtn) {
                undoBtn.textContent = I18n.t('history.undo');
            }

            const redoBtn = panel.querySelector('#history-redo-btn');
            if (redoBtn) {
                redoBtn.textContent = I18n.t('history.redo');
            }

            const clearBtn = panel.querySelector('#history-clear-btn');
            if (clearBtn) {
                clearBtn.textContent = I18n.t('history.clear');
            }

            // 更新空状态文本
            const emptyText = panel.querySelector('#history-list p');
            if (emptyText && emptyText.textContent?.includes('operations recorded') || emptyText?.textContent?.includes('操作记录')) {
                emptyText.textContent = I18n.t('history.empty');
            }
        });
    }

    private static _save(): void {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(this._entries.slice(0, MAX_ENTRIES)));
        } catch { /* ignore */ }
    }

    private static _load(): void {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved) this._entries = JSON.parse(saved);
        } catch { /* ignore */ }
    }

    private static _notify(): void {
        const entries = this.getAll();
        this._listeners.forEach(cb => { try { cb(entries); } catch (e) { console.error(e); } });
    }
}
