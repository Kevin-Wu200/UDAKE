/**
 * 参数建议对比面板组件
 * 显示不同参数组合的交叉验证结果对比
 */

import { ParameterAdjustmentPanel } from './ParameterAdjustmentPanel.js';
import { ParameterHistoryManager } from './ParameterHistoryManager.js';
import { I18nDialog } from './I18nDialog.js';

export interface ParameterScore {
    rmse: number;
    mae: number;
    r2: number;
}

export interface ParameterCombination {
    id: string;
    name: string;
    parameters: Record<string, number>;
    score: ParameterScore;
    isBest: boolean;
}

export class ParameterComparisonPanel {
    private static instance: ParameterComparisonPanel;
    private combinations: ParameterCombination[] = [];
    private container: HTMLElement | null = null;

    private constructor() {
        this.initialize();
    }

    public static getInstance(): ParameterComparisonPanel {
        if (!ParameterComparisonPanel.instance) {
            ParameterComparisonPanel.instance = new ParameterComparisonPanel();
        }
        return ParameterComparisonPanel.instance;
    }

    private initialize(): void {
        this.createContainer();
        this.render();
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
        this.container.className = 'parameter-comparison-panel';
        this.container.innerHTML = `
            <div class="comparison-header">
                <h3 class="comparison-title">参数建议对比</h3>
                <div class="comparison-actions">
                    <button class="btn-small" id="refresh-comparison">刷新</button>
                    <button class="btn-small" id="auto-optimize">自动优化</button>
                </div>
            </div>
            <div id="comparison-table-container"></div>
        `;

        sidebar.appendChild(this.container);

        // 绑定事件
        const refreshBtn = document.getElementById('refresh-comparison');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refresh());
        }

        const autoOptimizeBtn = document.getElementById('auto-optimize');
        if (autoOptimizeBtn) {
            autoOptimizeBtn.addEventListener('click', () => this.autoOptimize());
        }
    }

    /**
     * 渲染对比表格
     */
    private render(): void {
        if (!this.container) return;

        const tableContainer = this.container.querySelector('#comparison-table-container');
        if (!tableContainer) return;

        if (this.combinations.length === 0) {
            tableContainer.innerHTML = `
                <p style="color: var(--text-tertiary); text-align: center; padding: 20px;">
                    暂无参数建议，点击"刷新"获取
                </p>
            `;
            return;
        }

        const table = document.createElement('table');
        table.className = 'comparison-table';
        table.innerHTML = `
            <thead>
                <tr>
                    <th>名称</th>
                    <th>RMSE</th>
                    <th>MAE</th>
                    <th>R²</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                ${this.combinations.map(combo => `
                    <tr class="${combo.isBest ? 'best' : ''}" data-id="${combo.id}">
                        <td>${combo.name}</td>
                        <td class="score-cell ${combo.isBest ? 'best' : ''}">${combo.score.rmse.toFixed(4)}</td>
                        <td class="score-cell">${combo.score.mae.toFixed(4)}</td>
                        <td class="score-cell">${combo.score.r2.toFixed(4)}</td>
                        <td>
                            <button class="btn-small" data-action="apply" data-id="${combo.id}">应用</button>
                            <button class="btn-small" data-action="save" data-id="${combo.id}">保存</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        `;

        tableContainer.innerHTML = '';
        tableContainer.appendChild(table);

        // 绑定表格事件
        table.querySelectorAll('button[data-action]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const target = e.target as HTMLButtonElement;
                const action = target.dataset.action;
                const id = target.dataset.id;

                if (action === 'apply') {
                    this.applyCombination(id!);
                } else if (action === 'save') {
                    this.saveCombination(id!);
                }
            });
        });
    }

    /**
     * 设置参数组合
     */
    public setCombinations(combinations: ParameterCombination[]): void {
        this.combinations = combinations;
        this.markBest();
        this.render();
    }

    /**
     * 标记最佳组合
     */
    private markBest(): void {
        if (this.combinations.length === 0) return;

        // 找到 RMSE 最小的组合
        const bestRMSE = Math.min(...this.combinations.map(c => c.score.rmse));
        this.combinations.forEach(combo => {
            combo.isBest = combo.score.rmse === bestRMSE;
        });
    }

    /**
     * 应用参数组合
     */
    private applyCombination(id: string): void {
        const combo = this.combinations.find(c => c.id === id);
        if (!combo) return;

        const panel = ParameterAdjustmentPanel.getInstance();

        Object.entries(combo.parameters).forEach(([key, value]) => {
            panel.setParameter(key, value);
        });

        I18nDialog.alert('dialog.parameterCombo.applied', { name: combo.name });
    }

    /**
     * 保存参数组合
     */
    private saveCombination(id: string): void {
        const combo = this.combinations.find(c => c.id === id);
        if (!combo) return;

        const manager = ParameterHistoryManager.getInstance();

        manager.addRecord(combo.name, combo.parameters, combo.score);
        I18nDialog.alert('dialog.parameterCombo.saved', { name: combo.name });
    }

    /**
     * 刷新对比数据
     */
    private refresh(): void {
        // 这里应该调用后端API获取新的参数建议
        // 暂时使用模拟数据
        this.generateMockData();
    }

    /**
     * 自动优化参数
     */
    private autoOptimize(): void {
        // 这里应该调用后端API进行参数优化
        // 暂时使用模拟数据
        this.generateMockData();
    }

    /**
     * 生成模拟数据（用于测试）
     */
    private generateMockData(): void {
        const mockCombinations: ParameterCombination[] = [
            {
                id: '1',
                name: '默认参数',
                parameters: {
                    grid_resolution: 100,
                    nlags: 12,
                    nugget: 0,
                    sill: 1,
                    range: 10
                },
                score: {
                    rmse: 0.1234,
                    mae: 0.0987,
                    r2: 0.8765
                },
                isBest: false
            },
            {
                id: '2',
                name: '优化参数1',
                parameters: {
                    grid_resolution: 150,
                    nlags: 15,
                    nugget: 0.1,
                    sill: 1.2,
                    range: 12
                },
                score: {
                    rmse: 0.0987,
                    mae: 0.0765,
                    r2: 0.9012
                },
                isBest: false
            },
            {
                id: '3',
                name: '优化参数2',
                parameters: {
                    grid_resolution: 120,
                    nlags: 14,
                    nugget: 0.05,
                    sill: 1.1,
                    range: 11
                },
                score: {
                    rmse: 0.0876,
                    mae: 0.0654,
                    r2: 0.9234
                },
                isBest: false
            }
        ];

        this.setCombinations(mockCombinations);
    }

    /**
     * 清空数据
     */
    public clear(): void {
        this.combinations = [];
        this.render();
    }
}
