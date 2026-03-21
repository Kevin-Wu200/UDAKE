/**
 * 配置管理服务
 * 从后端获取配置信息，支持配置缓存、更新监听和自动刷新
 */
import { APIService } from './API封装';
import { environmentService } from './EnvironmentService';

export interface MapConfig {
    arcgis: {
        apiKey: string;
        portalUrl: string;
        env: string;
        defaultBasemap: string;
        defaultCenter: [number, number];
        defaultZoom: number;
        isMock: boolean;
    };
    amap: {
        apiKey: string;
        securityCode: string | null;
        defaultCenter: [number, number];
        defaultZoom: number;
    };
    tianditu: {
        apiKey: string;
        token: string | null;
    };
}

export interface AppConfig {
    appName: string;
    version: string;
    debug: boolean;
    corsOrigins: string[];
    maxFileSize: number;
    maxConcurrentTasks: number;
    taskTimeout: number;
}

export interface AIConfig {
    cacheEnabled: boolean;
    maxBatchSize: number;
    modelPath: string | null;
}

export interface AllConfig {
    app: {
        appName: string;
        version: string;
        debug: boolean;
    };
    map: MapConfig;
    ai: AIConfig;
    limits: {
        maxFileSize: number;
        maxConcurrentTasks: number;
        taskTimeout: number;
    };
}

export type ConfigListener = (config: AllConfig) => void;

export interface ConfigCache {
    data: AllConfig;
    timestamp: number;
    ttl: number;
}

export class ConfigService {
    private apiService: APIService;
    private mapConfig: MapConfig | null = null;
    private appConfig: AppConfig | null = null;
    private aiConfig: AIConfig | null = null;
    private allConfig: AllConfig | null = null;
    private configCache: ConfigCache | null = null;
    private listeners: Set<ConfigListener> = new Set();
    private autoRefreshInterval: number | null = null;
    private isSyncing: boolean = false;

    // 配置缓存过期时间（毫秒）
    private readonly CACHE_TTL = 5 * 60 * 1000; // 5分钟

    // 自动刷新间隔（毫秒）
    private readonly AUTO_REFRESH_INTERVAL = 10 * 60 * 1000; // 10分钟

    constructor(apiService: APIService) {
        this.apiService = apiService;
        this.initAutoRefresh();
    }

    /**
     * 初始化自动刷新
     */
    private initAutoRefresh(): void {
        // 只在开发环境启用自动刷新
        if (environmentService.isDevelopment()) {
            this.autoRefreshInterval = window.setInterval(() => {
                this.refreshConfigSilently();
            }, this.AUTO_REFRESH_INTERVAL);

            environmentService.debug('配置自动刷新已启用');
        }
    }

    /**
     * 静默刷新配置（不触发监听器）
     */
    private async refreshConfigSilently(): Promise<void> {
        try {
            const newConfig = await this.fetchAllConfig();
            this.allConfig = newConfig;
            this.configCache = {
                data: newConfig,
                timestamp: Date.now(),
                ttl: this.CACHE_TTL
            };
            environmentService.debug('配置已自动刷新');
        } catch (error) {
            environmentService.error('自动刷新配置失败:', error);
        }
    }

    /**
     * 从后端获取所有配置
     */
    private async fetchAllConfig(): Promise<AllConfig> {
        const response = await this.apiService.get<{ success: boolean; config: AllConfig }>('/config/all');
        if (response.success && response.config) {
            return response.config;
        }
        throw new Error('获取所有配置失败');
    }

    /**
     * 检查缓存是否过期
     */
    private isCacheExpired(): boolean {
        if (!this.configCache) {
            return true;
        }
        const age = Date.now() - this.configCache.timestamp;
        return age > this.configCache.ttl;
    }

    /**
     * 获取地图配置
     */
    async getMapConfig(): Promise<MapConfig> {
        if (this.mapConfig) {
            return this.mapConfig;
        }

        try {
            const response = await this.apiService.get<{ success: boolean; config: MapConfig }>('/config/map');
            if (response.success && response.config) {
                this.mapConfig = response.config;
                return this.mapConfig;
            }
            throw new Error('获取地图配置失败');
        } catch (error) {
            console.error('获取地图配置失败:', error);
            // 返回默认配置
            return {
                arcgis: {
                    apiKey: 'YOUR_ARCGIS_API_KEY_HERE',
                    portalUrl: 'https://www.arcgis.com',
                    env: 'development',
                    defaultBasemap: 'arcgis-topographic',
                    defaultCenter: [139.767125, 35.681236],
                    defaultZoom: 10,
                    isMock: true
                },
                amap: {
                    apiKey: 'YOUR_AMAP_API_KEY_HERE',
                    securityCode: null,
                    defaultCenter: [119.72170376, 30.26262781],
                    defaultZoom: 18
                },
                tianditu: {
                    apiKey: 'YOUR_TIANDITU_API_KEY_HERE',
                    token: null
                }
            };
        }
    }

    /**
     * 获取应用配置
     */
    async getAppConfig(): Promise<AppConfig> {
        if (this.appConfig) {
            return this.appConfig;
        }

        try {
            const response = await this.apiService.get<{ success: boolean; config: AppConfig }>('/config/app');
            if (response.success && response.config) {
                this.appConfig = response.config;
                return this.appConfig;
            }
            throw new Error('获取应用配置失败');
        } catch (error) {
            console.error('获取应用配置失败:', error);
            // 返回默认配置
            return {
                appName: '智能不确定性驱动空间决策平台',
                version: '1.0.0',
                debug: true,
                corsOrigins: ['http://localhost:5173'],
                maxFileSize: 100,
                maxConcurrentTasks: 5,
                taskTimeout: 3600
            };
        }
    }

    /**
     * 获取AI配置
     */
    async getAIConfig(): Promise<AIConfig> {
        if (this.aiConfig) {
            return this.aiConfig;
        }

        try {
            const response = await this.apiService.get<{ success: boolean; config: AIConfig }>('/config/ai');
            if (response.success && response.config) {
                this.aiConfig = response.config;
                return this.aiConfig;
            }
            throw new Error('获取AI配置失败');
        } catch (error) {
            console.error('获取AI配置失败:', error);
            // 返回默认配置
            return {
                cacheEnabled: true,
                maxBatchSize: 100,
                modelPath: null
            };
        }
    }

    /**
     * 获取所有配置
     */
    async getAllConfig(): Promise<AllConfig> {
        // 检查缓存
        if (this.allConfig && !this.isCacheExpired()) {
            environmentService.debug('使用缓存的配置');
            return this.allConfig;
        }

        try {
            const config = await this.fetchAllConfig();
            this.allConfig = config;
            this.configCache = {
                data: config,
                timestamp: Date.now(),
                ttl: this.CACHE_TTL
            };
            environmentService.debug('从后端获取配置成功');
            return config;
        } catch (error) {
            console.error('获取所有配置失败:', error);
            // 返回默认配置
            return {
                app: {
                    appName: '智能不确定性驱动空间决策平台',
                    version: '1.0.0',
                    debug: true
                },
                map: {
                    arcgis: {
                        apiKey: 'YOUR_ARCGIS_API_KEY_HERE',
                        portalUrl: 'https://www.arcgis.com',
                        env: 'development',
                        defaultBasemap: 'arcgis-topographic',
                        defaultCenter: [139.767125, 35.681236],
                        defaultZoom: 10,
                        isMock: true
                    },
                    amap: {
                        apiKey: 'YOUR_AMAP_API_KEY_HERE',
                        securityCode: null,
                        defaultCenter: [119.72170376, 30.26262781],
                        defaultZoom: 18
                    },
                    tianditu: {
                        apiKey: 'YOUR_TIANDITU_API_KEY_HERE',
                        token: null
                    }
                },
                ai: {
                    cacheEnabled: true,
                    maxBatchSize: 100,
                    modelPath: null
                },
                limits: {
                    maxFileSize: 100,
                    maxConcurrentTasks: 5,
                    taskTimeout: 3600
                }
            };
        }
    }

    /**
     * 清除配置缓存
     */
    clearCache(): void {
        this.mapConfig = null;
        this.appConfig = null;
        this.aiConfig = null;
        this.allConfig = null;
        this.configCache = null;
        environmentService.debug('配置缓存已清除');
    }

    /**
     * 刷新配置
     */
    async refreshConfig(): Promise<void> {
        if (this.isSyncing) {
            environmentService.warn('配置正在同步中，请稍后再试');
            return;
        }

        this.isSyncing = true;
        try {
            const oldConfig = this.allConfig;
            const newConfig = await this.fetchAllConfig();

            this.allConfig = newConfig;
            this.configCache = {
                data: newConfig,
                timestamp: Date.now(),
                ttl: this.CACHE_TTL
            };

            // 触发监听器
            if (JSON.stringify(oldConfig) !== JSON.stringify(newConfig)) {
                this.notifyListeners(newConfig);
                environmentService.info('配置已更新并通知监听器');
            }
        } catch (error) {
            environmentService.error('刷新配置失败:', error);
            throw error;
        } finally {
            this.isSyncing = false;
        }
    }

    /**
     * 添加配置监听器
     */
    addConfigListener(listener: ConfigListener): void {
        this.listeners.add(listener);
        environmentService.debug('配置监听器已添加，当前监听器数量:', this.listeners.size);
    }

    /**
     * 移除配置监听器
     */
    removeConfigListener(listener: ConfigListener): void {
        this.listeners.delete(listener);
        environmentService.debug('配置监听器已移除，当前监听器数量:', this.listeners.size);
    }

    /**
     * 通知所有监听器
     */
    private notifyListeners(config: AllConfig): void {
        this.listeners.forEach(listener => {
            try {
                listener(config);
            } catch (error) {
                environmentService.error('配置监听器执行失败:', error);
            }
        });
    }

    /**
     * 获取配置同步状态
     */
    getSyncStatus(): { isSyncing: boolean; hasCache: boolean; cacheAge: number | null } {
        return {
            isSyncing: this.isSyncing,
            hasCache: this.configCache !== null,
            cacheAge: this.configCache ? Date.now() - this.configCache.timestamp : null
        };
    }

    /**
     * 销毁服务
     */
    destroy(): void {
        if (this.autoRefreshInterval !== null) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
        this.listeners.clear();
        this.clearCache();
        environmentService.debug('配置服务已销毁');
    }
}

// 创建单例实例
let configServiceInstance: ConfigService | null = null;

export function getConfigService(apiService: APIService): ConfigService {
    if (!configServiceInstance) {
        configServiceInstance = new ConfigService(apiService);
    }
    return configServiceInstance;
}

// 销毁配置服务实例（用于测试或清理）
export function destroyConfigService(): void {
    if (configServiceInstance) {
        configServiceInstance.destroy();
        configServiceInstance = null;
    }
}