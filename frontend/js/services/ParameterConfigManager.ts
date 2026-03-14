/**
 * 参数配置管理器
 * 管理克里金插值参数的默认配置、预设和用户自定义配置
 */

import { appStore } from '../store/Store';
import type {
    ParamConfig,
    ParamPresetType,
    KrigingParams
} from '../../types/core';

// ========== 参数配置管理器 ==========

/**
 * 参数配置管理器
 */
export class ParameterConfigManager {
    private static instance: ParameterConfigManager;

    private constructor() {
        this.subscribeToConfigChanges();
    }

    public static getInstance(): ParameterConfigManager {
        if (!ParameterConfigManager.instance) {
            ParameterConfigManager.instance = new ParameterConfigManager();
        }
        return ParameterConfigManager.instance;
    }

    /**
     * 获取当前活动的配置
     */
    getActiveConfig(): ParamConfig | null {
        const activeConfigId = appStore.get('defaultParams.activeConfig');
        if (!activeConfigId) {
            return null;
        }

        const configs = appStore.get('defaultParams.configs');
        return configs[activeConfigId] || null;
    }

    /**
     * 设置活动配置
     */
    setActiveConfig(configId: string): void {
        const configs = appStore.get('defaultParams.configs');
        if (configs[configId]) {
            appStore.set('defaultParams.activeConfig', configId);
        } else {
            throw new Error(`配置 ${configId} 不存在`);
        }
    }

    /**
     * 获取所有配置
     */
    getAllConfigs(): Record<string, ParamConfig> {
        return appStore.get('defaultParams.configs');
    }

    /**
     * 获取配置
     */
    getConfig(configId: string): ParamConfig | null {
        const configs = appStore.get('defaultParams.configs');
        return configs[configId] || null;
    }

    /**
     * 保存配置
     */
    saveConfig(config: ParamConfig): string {
        const configs = appStore.get('defaultParams.configs');
        
        // 如果配置不存在，生成新的 ID
        if (!config.id) {
            config.id = this.generateConfigId();
        }

        // 更新时间戳
        config.updatedAt = new Date().toISOString();

        // 保存配置
        configs[config.id] = config;
        appStore.set('defaultParams.configs', configs);

        return config.id;
    }

    /**
     * 更新配置
     */
    updateConfig(configId: string, updates: Partial<ParamConfig>): void {
        const configs = appStore.get('defaultParams.configs');
        const config = configs[configId];

        if (!config) {
            throw new Error(`配置 ${configId} 不存在`);
        }

        // 合并更新
        const updatedConfig: ParamConfig = {
            ...config,
            ...updates,
            id: configId, // 保持 ID 不变
            updatedAt: new Date().toISOString()
        };

        configs[configId] = updatedConfig;
        appStore.set('defaultParams.configs', configs);
    }

    /**
     * 删除配置
     */
    deleteConfig(configId: string): void {
        const configs = appStore.get('defaultParams.configs');
        
        if (!configs[configId]) {
            throw new Error(`配置 ${configId} 不存在`);
        }

        delete configs[configId];
        appStore.set('defaultParams.configs', configs);

        // 如果删除的是活动配置，清除活动配置
        if (appStore.get('defaultParams.activeConfig') === configId) {
            appStore.set('defaultParams.activeConfig', null);
        }
    }

    /**
     * 获取预设配置
     */
    getPreset(presetType: ParamPresetType): ParamConfig {
        const presets = appStore.get('defaultParams.presets');
        return presets[presetType];
    }

    /**
     * 获取所有预设
     */
    getAllPresets(): Record<ParamPresetType, ParamConfig> {
        return appStore.get('defaultParams.presets');
    }

    /**
     * 从预设创建新配置
     */
    createFromPreset(presetType: ParamPresetType, name: string, description?: string): string {
        const preset = this.getPreset(presetType);
        
        const newConfig: ParamConfig = {
            id: this.generateConfigId(),
            name,
            description: description || `基于 ${preset.name} 的自定义配置`,
            presetType: 'custom',
            krigingParams: JSON.parse(JSON.stringify(preset.krigingParams)),
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };

        return this.saveConfig(newConfig);
    }

    /**
     * 复制配置
     */
    duplicateConfig(configId: string, newName?: string): string {
        const config = this.getConfig(configId);
        
        if (!config) {
            throw new Error(`配置 ${configId} 不存在`);
        }

        const newConfig: ParamConfig = {
            ...JSON.parse(JSON.stringify(config)),
            id: this.generateConfigId(),
            name: newName || `${config.name} (副本)`,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };

        return this.saveConfig(newConfig);
    }

    /**
     * 验证克里金参数
     */
    validateKrigingParams(params: KrigingParams): { valid: boolean; errors: string[] } {
        const errors: string[] = [];

        // 验证必需字段
        if (!params.method) {
            errors.push('缺少克里金方法');
        }
        if (!params.variogram_model) {
            errors.push('缺少变异函数模型');
        }
        if (params.grid_resolution === undefined || params.grid_resolution <= 0) {
            errors.push('网格分辨率必须大于 0');
        }

        // 验证可选字段
        if (params.nlags !== undefined && params.nlags < 1) {
            errors.push('滞后数必须大于等于 1');
        }
        if (params.nugget !== undefined && params.nugget < 0) {
            errors.push('块金值必须大于等于 0');
        }
        if (params.sill !== undefined && params.sill <= 0) {
            errors.push('基台值必须大于 0');
        }
        if (params.range !== undefined && params.range <= 0) {
            errors.push('变程必须大于 0');
        }

        return {
            valid: errors.length === 0,
            errors
        };
    }

    /**
     * 导出配置
     */
    exportConfig(configId: string): string {
        const config = this.getConfig(configId);
        
        if (!config) {
            throw new Error(`配置 ${configId} 不存在`);
        }

        return JSON.stringify(config, null, 2);
    }

    /**
     * 导出所有配置
     */
    exportAllConfigs(): string {
        const configs = appStore.get('defaultParams.configs');
        return JSON.stringify(configs, null, 2);
    }

    /**
     * 导入配置
     */
    importConfig(configJson: string): string {
        try {
            const config = JSON.parse(configJson) as ParamConfig;
            
            // 验证配置结构
            if (!config.name || !config.krigingParams) {
                throw new Error('配置格式无效');
            }

            // 验证克里金参数
            const validation = this.validateKrigingParams(config.krigingParams);
            if (!validation.valid) {
                throw new Error(`参数验证失败: ${validation.errors.join(', ')}`);
            }

            // 如果配置已存在，生成新的 ID
            if (config.id && this.getConfig(config.id)) {
                delete config.id;
            }

            // 设置时间戳
            config.createdAt = new Date().toISOString();
            config.updatedAt = new Date().toISOString();

            return this.saveConfig(config);
        } catch (e) {
            throw new Error(`导入配置失败: ${e instanceof Error ? e.message : '未知错误'}`);
        }
    }

    /**
     * 批量导入配置
     */
    importConfigs(configsJson: string): { success: number; failed: number; errors: string[] } {
        try {
            const configs = JSON.parse(configsJson) as Record<string, ParamConfig>;
            
            let success = 0;
            let failed = 0;
            const errors: string[] = [];

            for (const [key, config] of Object.entries(configs)) {
                try {
                    this.importConfig(JSON.stringify(config));
                    success++;
                } catch (e) {
                    failed++;
                    errors.push(`${key}: ${e instanceof Error ? e.message : '未知错误'}`);
                }
            }

            return { success, failed, errors };
        } catch (e) {
            throw new Error(`批量导入失败: ${e instanceof Error ? e.message : '未知错误'}`);
        }
    }

    /**
     * 重置为默认配置
     */
    resetToDefaults(): void {
        appStore.set('defaultParams.activeConfig', null);
        // 注意：不删除用户自定义配置，只清除活动配置
    }

    /**
     * 搜索配置
     */
    searchConfigs(keyword: string): ParamConfig[] {
        const configs = appStore.get('defaultParams.configs');
        const lowerKeyword = keyword.toLowerCase();

        return Object.values(configs).filter(config =>
            config.name.toLowerCase().includes(lowerKeyword) ||
            (config.description && config.description.toLowerCase().includes(lowerKeyword))
        );
    }

    /**
     * 获取配置统计
     */
    getConfigStats(): {
        total: number;
        byType: Record<ParamPresetType | 'custom', number>;
        active: string | null;
    } {
        const configs = appStore.get('defaultParams.configs');
        const configsArray = Object.values(configs);
        
        const byType: Record<ParamPresetType | 'custom', number> = {
            'environment': 0,
            'agriculture': 0,
            'geology': 0,
            'custom': 0
        };

        configsArray.forEach(config => {
            byType[config.presetType]++;
        });

        return {
            total: configsArray.length,
            byType,
            active: appStore.get('defaultParams.activeConfig')
        };
    }

    /**
     * 生成配置 ID
     */
    private generateConfigId(): string {
        return `config_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * 订阅配置变化
     */
    private subscribeToConfigChanges(): void {
        appStore.subscribe('defaultParams', (params) => {
            console.log('参数配置已更新:', params);
        });
    }

    /**
     * 应用配置到参数面板
     */
    applyConfigToPanel(config: ParamConfig): void {
        // 触发自定义事件，通知参数面板更新
        const event = new CustomEvent('applyParameterConfig', {
            detail: config
        });
        document.dispatchEvent(event);
    }
}

// 导出单例实例
export const parameterConfigManager = ParameterConfigManager.getInstance();