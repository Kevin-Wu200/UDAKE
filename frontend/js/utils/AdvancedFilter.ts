/**
 * 高级筛选和搜索组件
 * 多条件筛选、筛选条件保存、全文搜索、搜索高亮、搜索历史
 */

interface FilterCondition {
    field: string;
    operator: 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'contains' | 'between';
    value: any;
    value2?: any; // for 'between'
}

interface SavedFilter {
    name: string;
    conditions: FilterCondition[];
    timestamp: number;
}

const FILTER_STORAGE = 'udake_saved_filters';
const SEARCH_HISTORY_KEY = 'udake_search_history';
const MAX_HISTORY = 20;

export class AdvancedFilter {
    private conditions: FilterCondition[] = [];
    private _onFilter: ((results: any[]) => void) | null = null;
    private _data: any[] = [];

    constructor(data: any[] = [], onFilter?: (results: any[]) => void) {
        this._data = data;
        this._onFilter = onFilter ?? null;
    }

    setData(data: any[]): void {
        this._data = data;
    }

    addCondition(condition: FilterCondition): void {
        this.conditions.push(condition);
    }

    removeCondition(index: number): void {
        this.conditions.splice(index, 1);
    }

    clearConditions(): void {
        this.conditions = [];
    }

    /** 执行筛选 */
    apply(): any[] {
        let results = [...this._data];
        for (const cond of this.conditions) {
            results = results.filter(item => this._matchCondition(item, cond));
        }
        this._onFilter?.(results);
        return results;
    }

    private _matchCondition(item: any, cond: FilterCondition): boolean {
        const val = item[cond.field];
        if (val === undefined || val === null) return false;

        switch (cond.operator) {
            case 'eq': return val == cond.value;
            case 'neq': return val != cond.value;
            case 'gt': return Number(val) > Number(cond.value);
            case 'gte': return Number(val) >= Number(cond.value);
            case 'lt': return Number(val) < Number(cond.value);
            case 'lte': return Number(val) <= Number(cond.value);
            case 'contains': return String(val).toLowerCase().includes(String(cond.value).toLowerCase());
            case 'between': return Number(val) >= Number(cond.value) && Number(val) <= Number(cond.value2);
            default: return true;
        }
    }

    /** 保存筛选条件 */
    saveFilter(name: string): void {
        const saved = AdvancedFilter.getSavedFilters();
        saved.push({ name, conditions: [...this.conditions], timestamp: Date.now() });
        localStorage.setItem(FILTER_STORAGE, JSON.stringify(saved));
    }

    /** 加载已保存的筛选条件 */
    loadFilter(name: string): boolean {
        const saved = AdvancedFilter.getSavedFilters();
        const filter = saved.find(f => f.name === name);
        if (!filter) return false;
        this.conditions = [...filter.conditions];
        return true;
    }

    static getSavedFilters(): SavedFilter[] {
        try {
            const saved = localStorage.getItem(FILTER_STORAGE);
            return saved ? JSON.parse(saved) : [];
        } catch { return []; }
    }

    static deleteSavedFilter(name: string): void {
        const saved = AdvancedFilter.getSavedFilters().filter(f => f.name !== name);
        localStorage.setItem(FILTER_STORAGE, JSON.stringify(saved));
    }

    /** 全文搜索 */
    static search(data: any[], keyword: string, fields?: string[]): any[] {
        if (!keyword.trim()) return data;
        const kw = keyword.toLowerCase();
        AdvancedFilter._addToHistory(keyword);

        return data.filter(item => {
            const searchFields = fields || Object.keys(item);
            return searchFields.some(f => {
                const val = item[f];
                return val !== null && val !== undefined && String(val).toLowerCase().includes(kw);
            });
        });
    }

    /** 高亮搜索结果 */
    static highlight(text: string, keyword: string): string {
        if (!keyword.trim()) return text;
        const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${escaped})`, 'gi');
        return text.replace(regex, '<mark class="search-highlight">$1</mark>');
    }

    /** 获取搜索历史 */
    static getSearchHistory(): string[] {
        try {
            const saved = localStorage.getItem(SEARCH_HISTORY_KEY);
            return saved ? JSON.parse(saved) : [];
        } catch { return []; }
    }

    /** 清除搜索历史 */
    static clearSearchHistory(): void {
        localStorage.removeItem(SEARCH_HISTORY_KEY);
    }

    private static _addToHistory(keyword: string): void {
        const kw = keyword.trim();
        if (!kw) return;
        const history = this.getSearchHistory().filter(h => h !== kw);
        history.unshift(kw);
        if (history.length > MAX_HISTORY) history.pop();
        localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(history));
    }

    /** 创建筛选器 UI 面板 */
    createPanel(): HTMLElement {
        const panel = document.createElement('div');
        panel.className = 'panel filter-panel';
        panel.innerHTML = `
            <h2 class="panel-title">高级筛选</h2>
            <div class="panel-content">
                <div class="filter-search-bar" style="margin-bottom:12px;">
                    <input type="text" class="input filter-search-input" placeholder="搜索..." aria-label="全文搜索" style="width:100%;">
                    <div class="search-history-dropdown" style="display:none;"></div>
                </div>
                <div class="filter-conditions" id="filter-conditions"></div>
                <div style="display:flex;gap:8px;margin-top:8px;">
                    <button class="btn btn-export" id="filter-add" style="flex:1;height:32px;font-size:12px;">添加条件</button>
                    <button class="btn btn-export" id="filter-apply" style="flex:1;height:32px;font-size:12px;">应用筛选</button>
                    <button class="btn btn-export" id="filter-clear" style="flex:1;height:32px;font-size:12px;">清除</button>
                </div>
                <div class="filter-saved" style="margin-top:8px;">
                    <details>
                        <summary style="cursor:pointer;font-size:12px;color:var(--text-secondary);">已保存的筛选</summary>
                        <div id="saved-filters-list" style="margin-top:4px;"></div>
                    </details>
                </div>
            </div>
        `;

        const conditionsEl = panel.querySelector('#filter-conditions')!;
        const searchInput = panel.querySelector('.filter-search-input') as HTMLInputElement;

        // 搜索输入
        let searchTimeout: any;
        searchInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                const results = AdvancedFilter.search(this._data, searchInput.value);
                this._onFilter?.(results);
            }, 300);
        });

        // 搜索历史
        searchInput.addEventListener('focus', () => {
            const history = AdvancedFilter.getSearchHistory();
            const dropdown = panel.querySelector('.search-history-dropdown') as HTMLElement;
            if (history.length > 0) {
                dropdown.style.display = 'block';
                dropdown.innerHTML = history.slice(0, 5).map(h =>
                    `<div class="search-history-item" style="padding:6px 8px;cursor:pointer;font-size:12px;">${h}</div>`
                ).join('');
                dropdown.querySelectorAll('.search-history-item').forEach(item => {
                    item.addEventListener('click', () => {
                        searchInput.value = item.textContent!;
                        searchInput.dispatchEvent(new Event('input'));
                        dropdown.style.display = 'none';
                    });
                });
            }
        });

        searchInput.addEventListener('blur', () => {
            setTimeout(() => {
                (panel.querySelector('.search-history-dropdown') as HTMLElement).style.display = 'none';
            }, 200);
        });

        // 添加条件
        panel.querySelector('#filter-add')!.addEventListener('click', () => {
            const fields = this._data.length > 0 ? Object.keys(this._data[0]) : ['x', 'y', 'value'];
            const row = document.createElement('div');
            row.style.cssText = 'display:flex;gap:4px;margin-bottom:4px;align-items:center;';
            row.innerHTML = `
                <select class="select" style="flex:1;height:28px;font-size:11px;">
                    ${fields.map(f => `<option value="${f}">${f}</option>`).join('')}
                </select>
                <select class="select filter-op" style="width:60px;height:28px;font-size:11px;">
                    <option value="eq">=</option>
                    <option value="gt">&gt;</option>
                    <option value="lt">&lt;</option>
                    <option value="gte">≥</option>
                    <option value="lte">≤</option>
                    <option value="contains">包含</option>
                </select>
                <input type="text" class="input filter-val" style="flex:1;height:28px;font-size:11px;" placeholder="值">
                <button class="filter-remove" style="width:24px;height:24px;border:none;background:none;cursor:pointer;color:var(--text-secondary);">✕</button>
            `;
            row.querySelector('.filter-remove')!.addEventListener('click', () => row.remove());
            conditionsEl.appendChild(row);
        });

        // 应用筛选
        panel.querySelector('#filter-apply')!.addEventListener('click', () => {
            this.clearConditions();
            conditionsEl.querySelectorAll('div').forEach(row => {
                const selects = row.querySelectorAll('select');
                const input = row.querySelector('.filter-val') as HTMLInputElement;
                if (selects.length >= 2 && input?.value) {
                    this.addCondition({
                        field: (selects[0] as HTMLSelectElement).value,
                        operator: (selects[1] as HTMLSelectElement).value as any,
                        value: input.value,
                    });
                }
            });
            this.apply();
        });

        // 清除
        panel.querySelector('#filter-clear')!.addEventListener('click', () => {
            this.clearConditions();
            conditionsEl.innerHTML = '';
            searchInput.value = '';
            this._onFilter?.(this._data);
        });

        return panel;
    }
}
