/**
 * 配置管理服务
 * 从后端获取配置信息
 */
import { APIService } from './API封装';

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

export class ConfigService {
    private apiService: APIService;
    private mapConfig: MapConfig | null = null;
    private appConfig: AppConfig | null = null;
    private aiConfig: AIConfig | null = null;
    private allConfig: AllConfig | null = null;

    constructor(apiService: APIService) {
        this.apiService = apiService;
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
        if (this.allConfig) {
            return this.allConfig;
        }

        try {
            const response = await this.apiService.get<{ success: boolean; config: AllConfig }>('/config/all');
            if (response.success && response.config) {
                this.allConfig = response.config;
                return this.allConfig;
            }
            throw new Error('获取所有配置失败');
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
    }

    /**
     * 刷新配置
     */
    async refreshConfig(): Promise<void> {
        this.clearCache();
        await this.getAllConfig();
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