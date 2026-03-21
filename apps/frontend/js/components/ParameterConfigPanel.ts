/**
 * 参数配置面板组件
 * 提供参数配置的管理、预设选择、导入/导出等功能
 */

import { parameterConfigManager } from '../services/ParameterConfigManager';
import type { ParamPresetType } from '../../types/core';

export class ParameterConfigPanel {
    private container: HTMLElement;
    private overlay!: HTMLElement;
    private panel!: HTMLElement;

    constructor(container: HTMLElement | string) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)!
            : container;
        this.init();
    }

    private init(): void {
        this.createPanel();
        this.bindEvents();
        this.loadConfigs();
    }

    private createPanel(): void {
        // 创建遮罩层
        this.overlay = document.createElement('div');
        this.overlay.className = 'param-config-overlay';
        this.overlay.style.display = 'none';

        // 创建参数配置面板
        this.panel = document.createElement('div');
        this.panel.className = 'param-config-panel';
        this.panel.innerHTML = `
            <div class="param-config-content">
                <div class="param-config-header">
                    <h2 class="param-config-title">参数配置管理</h2>
                    <button class="btn btn-icon param-config-close-btn" title="关闭">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>

                <div class="param-config-body">
                    <!-- 预设选择 -->
                    <div class="param-config-section">
                        <h3 class="param-config-section-title">预设配置</h3>
                        <div class="param-config-presets">
                            <button class="param-preset-btn" data-preset="environment">
                                <span class="preset-icon">🌍</span>
                                <span class="preset-name">环境监测</span>
                            </button>
                            <button class="param-preset-btn" data-preset="agriculture">
                                <span class="preset-icon">🌾</span>
                                <span class="preset-name">农业分析</span>
                            </button>
                            <button class="param-preset-btn" data-preset="geology">
                                <span class="preset-icon">🔬</span>
                                <span class="preset-name">地质勘探</span>
                            </button>
                        </div>
                    </div>

                    <!-- 配置列表 -->
                    <div class="param-config-section">
                        <div class="param-config-section-header">
                            <h3 class="param-config-section-title">我的配置</h3>
                            <button class="btn btn-sm btn-primary param-config-create-btn">新建配置</button>
                        </div>
                        <div class="param-config-list">
                            <!-- 配置项将动态生成 -->
                        </div>
                    </div>

                    <!-- 操作按钮 -->
                    <div class="param-config-actions">
                        <button class="btn btn-secondary param-config-export-btn">导出配置</button>
                        <button class="btn btn-secondary param-config-import-btn">导入配置</button>
                        <button class="btn btn-secondary param-config-reset-btn">重置默认</button>
                    </div>
                </div>
            </div>
        `;

        this.overlay.appendChild(this.panel);
        this.container.appendChild(this.overlay);
    }

    private bindEvents(): void {
        const closeBtn = this.panel.querySelector('.param-config-close-btn') as HTMLButtonElement;
        const presetBtns = this.panel.querySelectorAll('.param-preset-btn');
        const createBtn = this.panel.querySelector('.param-config-create-btn') as HTMLButtonElement;
        const exportBtn = this.panel.querySelector('.param-config-export-btn') as HTMLButtonElement;
        const importBtn = this.panel.querySelector('.param-config-import-btn') as HTMLButtonElement;
        const resetBtn = this.panel.querySelector('.param-config-reset-btn') as HTMLButtonElement;

        // 关闭按钮
        closeBtn.addEventListener('click', () => this.hide());

        // 遮罩层点击关闭
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this.hide();
            }
        });

        // ESC 键关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible()) {
                this.hide();
            }
        });

        // 预设按钮
        presetBtns.forEach(btn => {
            (btn as HTMLElement).addEventListener('click', () => {
                const presetType = (btn as HTMLElement).dataset.preset as ParamPresetType;
                this.applyPreset(presetType);
            });
        });

        // 新建配置按钮
        createBtn.addEventListener('click', () => {
            this.createNewConfig();
        });

        // 导出配置按钮
        exportBtn.addEventListener('click', () => {
            this.exportConfigs();
        });

        // 导入配置按钮
        importBtn.addEventListener('click', () => {
            this.importConfigs();
        });

        // 重置按钮
        resetBtn.addEventListener('click', () => {
            this.resetToDefaults();
        });

        // 监听配置变化
        document.addEventListener('parameterConfigChanged', () => {
            this.loadConfigs();
        });
    }

    private loadConfigs(): void {
        const listElement = this.panel.querySelector('.param-config-list') as HTMLElement;
        const configs = parameterConfigManager.getAllConfigs();
        const activeConfigId = parameterConfigManager.getActiveConfig()?.id || null;

        if (Object.keys(configs).length === 0) {
            listElement.innerHTML = `
                <div class="param-config-empty">
                    <p>暂无自定义配置</p>
                    <p class="text-muted">点击"新建配置"创建您的第一个参数配置</p>
                </div>
            `;
            return;
        }

        listElement.innerHTML = Object.entries(configs).map(([id, config]) => `
            <div class="param-config-item ${id === activeConfigId ? 'active' : ''}" data-id="${id}">
                <div class="param-config-info">
                    <h4 class="param-config-name">${config.name}</h4>
                    <p class="param-config-description">${config.description || '无描述'}</p>
                    <span class="param-config-type">${this.getPresetTypeName(config.presetType)}</span>
                </div>
                <div class="param-config-actions">
                    <button class="btn btn-sm btn-secondary param-config-apply-btn" title="应用">应用</button>
                    <button class="btn btn-sm btn-secondary param-config-edit-btn" title="编辑">编辑</button>
                    <button class="btn btn-sm btn-secondary param-config-duplicate-btn" title="复制">复制</button>
                    <button class="btn btn-sm btn-danger param-config-delete-btn" title="删除">删除</button>
                </div>
            </div>
        `).join('');

        // 绑定配置项事件
        listElement.querySelectorAll('.param-config-item').forEach(item => {
            const configId = (item as HTMLElement).dataset.id!;
            
            const applyBtn = item.querySelector('.param-config-apply-btn') as HTMLButtonElement;
            const editBtn = item.querySelector('.param-config-edit-btn') as HTMLButtonElement;
            const duplicateBtn = item.querySelector('.param-config-duplicate-btn') as HTMLButtonElement;
            const deleteBtn = item.querySelector('.param-config-delete-btn') as HTMLButtonElement;

            applyBtn.addEventListener('click', () => this.applyConfig(configId));
            editBtn.addEventListener('click', () => this.editConfig(configId));
            duplicateBtn.addEventListener('click', () => this.duplicateConfig(configId));
            deleteBtn.addEventListener('click', () => this.deleteConfig(configId));
        });
    }

    private getPresetTypeName(type: ParamPresetType): string {
        const names: Record<ParamPresetType, string> = {
            'environment': '环境监测',
            'agriculture': '农业分析',
            'geology': '地质勘探',
            'custom': '自定义'
        };
        return names[type];
    }

    private applyPreset(presetType: ParamPresetType): void {
        const preset = parameterConfigManager.getPreset(presetType);
        parameterConfigManager.applyConfigToPanel(preset);
        
        // 创建一个临时的配置并设置为活动配置
        const configId = parameterConfigManager.createFromPreset(
            presetType,
            `${preset.name} (应用)`,
            `从预设 ${preset.name} 应用`
        );
        parameterConfigManager.setActiveConfig(configId);
        
        this.loadConfigs();
        alert(`已应用 ${preset.name} 预设`);
        this.hide();
    }

    private applyConfig(configId: string): void {
        const config = parameterConfigManager.getConfig(configId);
        if (config) {
            parameterConfigManager.setActiveConfig(configId);
            parameterConfigManager.applyConfigToPanel(config);
            this.loadConfigs();
            alert(`已应用配置: ${config.name}`);
            this.hide();
        }
    }

    private createNewConfig(): void {
        const name = prompt('请输入配置名称：');
        if (!name) return;

        const description = prompt('请输入配置描述（可选）：') || '';
        const presetType = prompt('请选择预设类型（environment/agriculture/geology/custom）：', 'custom') as ParamPresetType;

        try {
            if (presetType === 'custom') {
                // 创建空配置
                const newConfig: any = {
                    id: '',
                    name,
                    description,
                    presetType: 'custom',
                    krigingParams: {
                        points: [],
                        method: 'ordinary',
                        variogram_model: 'spherical',
                        grid_resolution: 100,
                        nlags: 12,
                        nugget: 0,
                        sill: 1,
                        range: 1000,
                        enable_cross_validation: true
                    },
                    createdAt: new Date().toISOString(),
                    updatedAt: new Date().toISOString()
                };
                parameterConfigManager.saveConfig(newConfig);
            } else {
                parameterConfigManager.createFromPreset(presetType, name, description);
            }

            this.loadConfigs();
            alert('配置创建成功');
        } catch (e) {
            alert(`创建配置失败: ${e instanceof Error ? e.message : '未知错误'}`);
        }
    }

    private editConfig(configId: string): void {
        const config = parameterConfigManager.getConfig(configId);
        if (!config) return;

        const newName = prompt('配置名称：', config.name);
        if (newName === null) return;

        const newDescription = prompt('配置描述：', config.description || '');

        try {
            parameterConfigManager.updateConfig(configId, {
                name: newName,
                description: newDescription || undefined
            });
            this.loadConfigs();
            alert('配置更新成功');
        } catch (e) {
            alert(`更新配置失败: ${e instanceof Error ? e.message : '未知错误'}`);
        }
    }

    private duplicateConfig(configId: string): void {
        try {
            const newId = parameterConfigManager.duplicateConfig(configId);
            this.loadConfigs();
            alert('配置复制成功');
        } catch (e) {
            alert(`复制配置失败: ${e instanceof Error ? e.message : '未知错误'}`);
        }
    }

    private deleteConfig(configId: string): void {
        const config = parameterConfigManager.getConfig(configId);
        if (!config) return;

        if (confirm(`确定要删除配置 "${config.name}" 吗？`)) {
            try {
                parameterConfigManager.deleteConfig(configId);
                this.loadConfigs();
                alert('配置删除成功');
            } catch (e) {
                alert(`删除配置失败: ${e instanceof Error ? e.message : '未知错误'}`);
            }
        }
    }

    private exportConfigs(): void {
        try {
            const configsJson = parameterConfigManager.exportAllConfigs();
            const blob = new Blob([configsJson], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            
            const a = document.createElement('a');
            a.href = url;
            a.download = `parameter_configs_${new Date().toISOString().split('T')[0]}.json`;
            a.click();
            
            URL.revokeObjectURL(url);
            alert('配置导出成功');
        } catch (e) {
            alert(`导出配置失败: ${e instanceof Error ? e.message : '未知错误'}`);
        }
    }

    private importConfigs(): void {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';

        input.onchange = (e) => {
            const file = (e.target as HTMLInputElement).files?.[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (event) => {
                try {
                    const configsJson = event.target?.result as string;
                    const result = parameterConfigManager.importConfigs(configsJson);
                    
                    this.loadConfigs();
                    alert(
                        `导入完成：\n成功: ${result.success}\n失败: ${result.failed}` +
                        (result.errors.length > 0 ? `\n错误:\n${result.errors.join('\n')}` : '')
                    );
                } catch (e) {
                    alert(`导入配置失败: ${e instanceof Error ? e.message : '未知错误'}`);
                }
            };
            reader.readAsText(file);
        };

        input.click();
    }

    private resetToDefaults(): void {
        if (confirm('确定要重置为默认配置吗？这将清除所有自定义配置。')) {
            try {
                parameterConfigManager.resetToDefaults();
                this.loadConfigs();
                alert('已重置为默认配置');
            } catch (e) {
                alert(`重置失败: ${e instanceof Error ? e.message : '未知错误'}`);
            }
        }
    }

    public show(): void {
        this.overlay.style.display = 'flex';
        this.loadConfigs();
    }

    public hide(): void {
        this.overlay.style.display = 'none';
    }

    public isVisible(): boolean {
        return this.overlay.style.display === 'flex';
    }

    public toggle(): void {
        if (this.isVisible()) {
            this.hide();
        } else {
            this.show();
        }
    }

    public destroy(): void {
        this.overlay.remove();
    }
}
