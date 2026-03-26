/**
 * 参数标签页面板组件
 * 整合参数调整、历史记录、对比和说明功能
 */

import { ParameterAdjustmentPanel } from './ParameterAdjustmentPanel.js';
import { ParameterHistoryManager } from './ParameterHistoryManager.js';
import { ParameterComparisonPanel } from './ParameterComparisonPanel.js';
import { ParameterInfoPanel } from './ParameterInfoPanel.js';
import { I18nDialog } from './I18nDialog.js';

export class ParameterTabPanel {
    private static instance: ParameterTabPanel;
    private container: HTMLElement | null = null;
    private activeTab: string = 'adjustment';

    private constructor() {
        this.initialize();
    }

    public static getInstance(): ParameterTabPanel {
        if (!ParameterTabPanel.instance) {
            ParameterTabPanel.instance = new ParameterTabPanel();
        }
        return ParameterTabPanel.instance;
    }

    private initialize(): void {
        this.createContainer();
        this.render();
        this.bindEvents();
    }

    /**
     * 创建容器
     */
    private createContainer(): void {
        const sidebar = document.querySelector('.right-sidebar-content');
        if (!sidebar) {
            console.warn('Right sidebar content not found');
            return;
        }

        this.container = document.createElement('div');
        this.container.className = 'tab-container';
        this.container.innerHTML = `
            <div class="tab-header">
                <button class="tab-btn active" data-tab="adjustment">参数调整</button>
                <button class="tab-btn" data-tab="comparison">参数对比</button>
                <button class="tab-btn" data-tab="history">历史记录</button>
                <button class="tab-btn" data-tab="info">参数说明</button>
            </div>
            <div class="tab-content active" id="tab-adjustment">
                <div id="adjustment-panel-content"></div>
            </div>
            <div class="tab-content" id="tab-comparison">
                <div id="comparison-panel-content"></div>
            </div>
            <div class="tab-content" id="tab-history">
                <div id="history-panel-content"></div>
            </div>
            <div class="tab-content" id="tab-info">
                <div id="info-panel-content"></div>
            </div>
        `;

        sidebar.appendChild(this.container);
    }

    /**
     * 渲染
     */
    private render(): void {
        // 初始化各个子面板
        this.initializeAdjustmentPanel();
        this.initializeComparisonPanel();
        this.initializeHistoryPanel();
        this.initializeInfoPanel();
    }

    /**
     * 初始化参数调整面板
     */
    private initializeAdjustmentPanel(): void {
        const content = document.getElementById('adjustment-panel-content');
        if (!content) return;

        content.innerHTML = `
            <div style="padding: 12px;">
                <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600;">快速操作</h4>
                <div style="display: flex; gap: 8px; margin-bottom: 16px;">
                    <button class="btn-small" id="reset-params">重置默认</button>
                    <button class="btn-small" id="save-params">保存参数</button>
                    <button class="btn-small" id="load-params">加载参数</button>
                </div>
                <div id="param-validation-status"></div>
            </div>
        `;

        // 绑定事件
        const resetBtn = document.getElementById('reset-params');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetParameters());
        }

        const saveBtn = document.getElementById('save-params');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveParameters());
        }

        const loadBtn = document.getElementById('load-params');
        if (loadBtn) {
            loadBtn.addEventListener('click', () => this.loadParameters());
        }
    }

    /**
     * 初始化参数对比面板
     */
    private initializeComparisonPanel(): void {
        const content = document.getElementById('comparison-panel-content');
        if (!content) return;

        content.innerHTML = `
            <div id="comparison-panel-wrapper"></div>
        `;

        // 初始化对比面板
        ParameterComparisonPanel.getInstance();
    }

    /**
     * 初始化历史记录面板
     */
    private initializeHistoryPanel(): void {
        const content = document.getElementById('history-panel-content');
        if (!content) return;

        content.innerHTML = `
            <div style="padding: 12px;">
                <div class="history-controls">
                    <input type="text" class="history-search" id="history-search" placeholder="搜索历史记录...">
                    <button class="btn-small" id="export-history">导出</button>
                    <button class="btn-small" id="import-history">导入</button>
                </div>
                <div id="history-list" class="history-list"></div>
            </div>
        `;

        // 绑定事件
        document.getElementById('history-search')?.addEventListener('input', (e) => {
            this.searchHistory((e.target as HTMLInputElement).value);
        });

        document.getElementById('export-history')?.addEventListener('click', () => {
            this.exportHistory();
        });

        document.getElementById('import-history')?.addEventListener('click', () => {
            this.importHistory();
        });

        this.loadHistoryList();
    }

    /**
     * 初始化参数说明面板
     */
    private initializeInfoPanel(): void {
        const content = document.getElementById('info-panel-content');
        if (!content) return;

        content.innerHTML = `
            <div id="info-panel-wrapper"></div>
        `;

        // 初始化参数说明面板
        ParameterInfoPanel.getInstance();
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        // 标签页切换
        this.container?.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const target = e.target as HTMLElement;
                this.switchTab((target as HTMLButtonElement).dataset.tab || 'adjustment');
            });
        });
    }

    /**
     * 切换标签页
     */
    private switchTab(tabName: string): void {
        this.activeTab = tabName;

        // 更新按钮状态
        this.container?.querySelectorAll('.tab-btn').forEach(btn => {
            if ((btn as HTMLElement).dataset.tab === tabName) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // 更新内容显示
        this.container?.querySelectorAll('.tab-content').forEach(content => {
            if (content.id === `tab-${tabName}`) {
                content.classList.add('active');
            } else {
                content.classList.remove('active');
            }
        });
    }

    /**
     * 重置参数
     */
    private resetParameters(): void {
        const panel = ParameterAdjustmentPanel.getInstance();
        panel.resetToDefaults();
        this.updateValidationStatus();
    }

    /**
     * 保存参数
     */
    private saveParameters(): void {
        const name = I18nDialog.prompt('请输入参数组合名称:');
        if (!name) return;

        const panel = ParameterAdjustmentPanel.getInstance();
        panel.saveParameters(name);

        // 保存到历史记录
        const manager = ParameterHistoryManager.getInstance();
        manager.addRecord(name, panel.getParameters());

        I18nDialog.alert('参数已保存');
        this.loadHistoryList();
    }

    /**
     * 加载参数
     */
    private loadParameters(): void {
        // 切换到历史记录标签页
        this.switchTab('history');
    }

    /**
     * 更新验证状态
     */
    private updateValidationStatus(): void {
        const statusDiv = document.getElementById('param-validation-status');
        if (!statusDiv) return;

        const panel = ParameterAdjustmentPanel.getInstance();
        const validation = panel.validateAll();

        if (validation.valid) {
            statusDiv.innerHTML = `
                <div style="padding: 8px 12px; background-color: rgba(52, 199, 89, 0.1); border-radius: 6px; color: #34c759; font-size: 12px;">
                    ✓ 所有参数有效
                </div>
            `;
        } else {
            statusDiv.innerHTML = `
                <div style="padding: 8px 12px; background-color: rgba(255, 59, 48, 0.1); border-radius: 6px; color: #ff3b30; font-size: 12px;">
                    ✗ ${validation.errors.join('; ')}
                </div>
            `;
        }
    }

    /**
     * 加载历史记录列表
     */
    private loadHistoryList(): void {
        const listDiv = document.getElementById('history-list');
        if (!listDiv) return;

        const manager = ParameterHistoryManager.getInstance();
        const records = manager.getAllRecords();

        if (records.length === 0) {
            listDiv.innerHTML = `
                <p style="color: var(--text-tertiary); text-align: center; padding: 20px;">
                    暂无历史记录
                </p>
            `;
            return;
        }

        listDiv.innerHTML = records.map(record => `
            <div class="history-item ${record.favorite ? 'favorite' : ''}">
                <div class="history-item-header">
                    <span class="history-item-title">${record.name}</span>
                    <div class="history-item-actions">
                        <button class="history-btn-icon ${record.favorite ? 'favorite' : ''}" data-action="favorite" data-id="${record.id}">
                            ${record.favorite ? '★' : '☆'}
                        </button>
                        <button class="history-btn-icon" data-action="apply" data-id="${record.id}">应用</button>
                        <button class="history-btn-icon" data-action="delete" data-id="${record.id}">×</button>
                    </div>
                </div>
                <div class="history-item-body">
                    ${Object.entries(record.parameters).map(([key, value]) => `
                        <div class="history-param-row">
                            <span>${key}:</span>
                            <span class="history-param-value">${value}</span>
                        </div>
                    `).join('')}
                </div>
                <div class="history-item-footer">
                    <span class="history-item-time">${new Date(record.timestamp).toLocaleString()}</span>
                    ${record.score ? `<span class="history-item-score">RMSE: ${record.score.rmse?.toFixed(4)}</span>` : ''}
                </div>
            </div>
        `).join('');

        // 绑定事件
        listDiv.querySelectorAll('button[data-action]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const target = e.target as HTMLButtonElement;
                const action = target.dataset.action;
                const id = target.dataset.id;

                if (action === 'favorite') {
                    manager.toggleFavorite(id!);
                    this.loadHistoryList();
                } else if (action === 'apply') {
                    this.applyHistoryRecord(id!);
                } else if (action === 'delete') {
                    if (I18nDialog.confirm('确定要删除这条记录吗？')) {
                        manager.deleteRecord(id!);
                        this.loadHistoryList();
                    }
                }
            });
        });
    }

    /**
     * 应用历史记录
     */
    private applyHistoryRecord(id: string): void {
        const manager = ParameterHistoryManager.getInstance();
        const record = manager.getRecord(id);

        if (!record) return;

        const panel = ParameterAdjustmentPanel.getInstance();

        Object.entries(record.parameters).forEach(([key, value]) => {
            panel.setParameter(key, value);
        });

        I18nDialog.alert(`已应用参数组合: ${record.name}`);
        this.switchTab('adjustment');
    }

    /**
     * 搜索历史记录
     */
    private searchHistory(query: string): void {
        const manager = ParameterHistoryManager.getInstance();
        const records = manager.searchRecords(query);

        const listDiv = document.getElementById('history-list');
        if (!listDiv) return;

        if (records.length === 0) {
            listDiv.innerHTML = `
                <p style="color: var(--text-tertiary); text-align: center; padding: 20px;">
                    未找到匹配的记录
                </p>
            `;
            return;
        }

        // 重新渲染列表（简化版，实际应该复用loadHistoryList的逻辑）
        this.loadHistoryList();
    }

    /**
     * 导出历史记录
     */
    private exportHistory(): void {
        const manager = ParameterHistoryManager.getInstance();
        const json = manager.exportRecords();

        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `parameter-history-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    /**
     * 导入历史记录
     */
    private importHistory(): void {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';

        input.onchange = (e) => {
            const file = (e.target as HTMLInputElement).files?.[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (event) => {
                const json = event.target?.result as string;
                const manager = ParameterHistoryManager.getInstance();
                const result = manager.importRecords(json);

                I18nDialog.alert(`导入成功: ${result.success} 条，失败: ${result.failed} 条`);
                this.loadHistoryList();
            };
            reader.readAsText(file);
        };

        input.click();
    }
}