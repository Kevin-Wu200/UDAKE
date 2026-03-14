/**
 * 参数影响可视化说明面板组件
 * 提供参数的详细说明和影响分析
 */

export interface ParameterInfo {
    name: string;
    displayName: string;
    description: string;
    range: { min: number; max: number };
    impact: string;
    warning?: string;
    relatedTo?: string[];
}

export class ParameterInfoPanel {
    private static instance: ParameterInfoPanel;
    private container: HTMLElement | null = null;
    private parameters: Map<string, ParameterInfo> = new Map();

    private constructor() {
        this.initialize();
    }

    public static getInstance(): ParameterInfoPanel {
        if (!ParameterInfoPanel.instance) {
            ParameterInfoPanel.instance = new ParameterInfoPanel();
        }
        return ParameterInfoPanel.instance;
    }

    private initialize(): void {
        this.initializeParameterInfo();
        this.createContainer();
        this.render();
        this.bindEvents();
    }

    /**
     * 初始化参数信息
     */
    private initializeParameterInfo(): void {
        this.parameters.set('grid_resolution', {
            name: 'grid_resolution',
            displayName: '网格分辨率',
            description: '控制输出栅格的精细程度。较大的值会产生更精细的网格，但会增加计算时间和内存使用。',
            range: { min: 50, max: 500 },
            impact: '直接影响输出结果的精度和性能。分辨率越高，细节越丰富，但计算成本也越高。',
            warning: '超过300可能导致计算时间显著增加或内存不足。'
        });

        this.parameters.set('nlags', {
            name: 'nlags',
            displayName: '滞后数',
            description: '变异函数计算时将距离分组的数量。每个滞后代表一个距离范围，用于计算该范围内的变异值。',
            range: { min: 6, max: 24 },
            impact: '影响变异函数的拟合质量。滞后数太少会导致拟合不准确，太多会增加计算负担。',
            relatedTo: ['range']
        });

        this.parameters.set('nugget', {
            name: 'nugget',
            displayName: '变差值',
            description: '表示距离为零时的变异值，通常由测量误差或微观变异引起。也称为"块金效应"。',
            range: { min: 0, max: 1 },
            impact: '影响插值的平滑程度。变差值越大，插值结果越平滑，但可能忽略局部变异。',
            warning: '应该小于基台值(sill)。',
            relatedTo: ['sill']
        });

        this.parameters.set('sill', {
            name: 'sill',
            displayName: '基台值',
            description: '变异函数的渐近值，表示总方差。当距离超过范围值(range)时，变异值趋近于基台值。',
            range: { min: 0, max: 10 },
            impact: '影响插值的整体变化幅度。基台值越大，空间变异越大。',
            warning: '应该大于变差值(nugget)。',
            relatedTo: ['nugget']
        });

        this.parameters.set('range', {
            name: 'range',
            displayName: '范围值',
            description: '变异函数达到基台值时的距离，表示空间相关的最大距离。超过这个距离的点相关性很弱。',
            range: { min: 0, max: 100 },
            impact: '影响插值的影响范围。范围值越大，远距离的点对插值结果影响越大。',
            relatedTo: ['nlags']
        });
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
        this.container.className = 'parameter-info-panel';
        this.container.innerHTML = `
            <div class="info-panel-header">
                <h3 class="info-panel-title">参数说明</h3>
            </div>
            <div id="parameter-info-list"></div>
        `;

        sidebar.appendChild(this.container);
    }

    /**
     * 渲染参数信息列表
     */
    private render(): void {
        if (!this.container) return;

        const listContainer = this.container.querySelector('#parameter-info-list');
        if (!listContainer) return;

        listContainer.innerHTML = Array.from(this.parameters.values()).map(param => `
            <div class="parameter-info-item" data-param="${param.name}">
                <div class="parameter-info-item-header">
                    <span class="parameter-info-name">${param.displayName}</span>
                    <span class="parameter-info-badge">${param.range.min} - ${param.range.max}</span>
                </div>
                <div class="parameter-info-description">${param.description}</div>
                <div class="parameter-info-range">取值范围: ${param.range.min} ~ ${param.range.max}</div>
                <div class="parameter-info-impact">
                    <strong>影响:</strong> ${param.impact}
                </div>
                ${param.warning ? `
                    <div class="parameter-info-warning">
                        <strong>⚠️ 注意:</strong> ${param.warning}
                    </div>
                ` : ''}
                ${param.relatedTo && param.relatedTo.length > 0 ? `
                    <div class="parameter-info-related" style="font-size: 12px; color: var(--text-tertiary); margin-top: 4px;">
                        <strong>相关参数:</strong> ${param.relatedTo.map(r => this.parameters.get(r)?.displayName || r).join(', ')}
                    </div>
                ` : ''}
            </div>
        `).join('');
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        // 监听参数变化，更新警告状态
        document.querySelectorAll('input[type="range"], input[type="number"]').forEach(input => {
            input.addEventListener('input', () => {
                this.updateWarnings();
            });
        });
    }

    /**
     * 更新警告状态
     */
    private updateWarnings(): void {
        if (!this.container) return;

        // 获取当前参数值
        const gridResolution = parseFloat((document.getElementById('grid-resolution') as HTMLInputElement)?.value || '100');
        const nugget = parseFloat((document.getElementById('nugget') as HTMLInputElement)?.value || '0');
        const sill = parseFloat((document.getElementById('sill') as HTMLInputElement)?.value || '1');

        // 更新网格分辨率警告
        const gridResolutionItem = this.container.querySelector('.parameter-info-item[data-param="grid_resolution"]');
        if (gridResolutionItem && gridResolution > 300) {
            gridResolutionItem.classList.add('warning');
        } else {
            gridResolutionItem?.classList.remove('warning');
        }

        // 更新变差值和基台值警告
        const nuggetItem = this.container.querySelector('.parameter-info-item[data-param="nugget"]');
        const sillItem = this.container.querySelector('.parameter-info-item[data-param="sill"]');

        if (nugget >= sill) {
            nuggetItem?.classList.add('warning');
            sillItem?.classList.add('warning');
        } else {
            nuggetItem?.classList.remove('warning');
            sillItem?.classList.remove('warning');
        }
    }

    /**
     * 获取参数信息
     */
    public getParameterInfo(name: string): ParameterInfo | undefined {
        return this.parameters.get(name);
    }

    /**
     * 获取所有参数信息
     */
    public getAllParameterInfo(): ParameterInfo[] {
        return Array.from(this.parameters.values());
    }

    /**
     * 显示特定参数的详细信息
     */
    public showParameterDetail(name: string): void {
        const param = this.parameters.get(name);
        if (!param) return;

        const item = this.container?.querySelector(`.parameter-info-item[data-param="${name}"]`);
        if (item) {
            item.scrollIntoView({ behavior: 'smooth', block: 'center' });
            item.classList.add('highlight');

            setTimeout(() => {
                item.classList.remove('highlight');
            }, 2000);
        }
    }

    /**
     * 获取参数优化建议
     */
    public getOptimizationSuggestions(parameters: Record<string, number>): string[] {
        const suggestions: string[] = [];

        const gridResolution = parameters.grid_resolution || 100;
        if (gridResolution > 300) {
            suggestions.push('网格分辨率较高，建议降低至200以下以提高性能。');
        }

        const nugget = parameters.nugget || 0;
        const sill = parameters.sill || 1;
        if (nugget >= sill) {
            suggestions.push('变差值应小于基台值，建议调整参数。');
        }

        const nlags = parameters.nlags || 12;
        if (nlags < 10) {
            suggestions.push('滞后数较少，建议增加至12-15以提高拟合精度。');
        }

        return suggestions;
    }
}