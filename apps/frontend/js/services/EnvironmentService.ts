/**
 * 环境配置服务
 * 提供环境特定的配置信息
 */

export type Environment = 'development' | 'testing' | 'production';

export interface EnvironmentConfig {
  /** 环境标识 */
  env: Environment;
  /** 应用名称 */
  appName: string;
  /** 应用版本 */
  appVersion: string;
  /** API 基础 URL */
  apiBaseUrl: string;
  /** 地图引擎 */
  mapProvider: string;
  /** 是否启用调试 */
  enableDebug: boolean;
  /** 是否启用性能监控 */
  enablePerformanceMonitor: boolean;
  /** 日志级别 */
  logLevel: 'debug' | 'info' | 'warn' | 'error';
}

class EnvironmentService {
  private config: EnvironmentConfig;

  constructor() {
    this.config = this.loadConfig();
  }

  /**
   * 从环境变量加载配置
   */
  private loadConfig(): EnvironmentConfig {
    // 获取环境变量（Vite 会注入以 VITE_ 开头的环境变量）
    const env = (import.meta.env.VITE_APP_ENV || 'development') as Environment;
    const appName = import.meta.env.VITE_APP_NAME || 'UDAKE';
    const appVersion = import.meta.env.VITE_APP_VERSION || '1.0.0';
    const apiBaseUrl =
      import.meta.env.VITE_API_BASE_URL ||
      import.meta.env.VITE_API_URL ||
      'https://172.20.10.2:8443';
    const mapProvider = import.meta.env.VITE_MAP_PROVIDER || 'arcgis';
    const enableDebug = import.meta.env.VITE_ENABLE_DEBUG === 'true';
    const enablePerformanceMonitor = import.meta.env.VITE_ENABLE_PERFORMANCE_MONITOR === 'true';
    const logLevel = (import.meta.env.VITE_LOG_LEVEL || 'info') as 'debug' | 'info' | 'warn' | 'error';

    return {
      env,
      appName,
      appVersion,
      apiBaseUrl,
      mapProvider,
      enableDebug,
      enablePerformanceMonitor,
      logLevel,
    };
  }

  /**
   * 获取当前配置
   */
  getConfig(): EnvironmentConfig {
    return this.config;
  }

  /**
   * 获取环境标识
   */
  getEnvironment(): Environment {
    return this.config.env;
  }

  /**
   * 是否为开发环境
   */
  isDevelopment(): boolean {
    return this.config.env === 'development';
  }

  /**
   * 是否为测试环境
   */
  isTesting(): boolean {
    return this.config.env === 'testing';
  }

  /**
   * 是否为生产环境
   */
  isProduction(): boolean {
    return this.config.env === 'production';
  }

  /**
   * 获取 API 基础 URL
   */
  getApiBaseUrl(): string {
    return this.config.apiBaseUrl;
  }

  /**
   * 是否启用调试
   */
  isDebugEnabled(): boolean {
    return this.config.enableDebug;
  }

  /**
   * 是否启用性能监控
   */
  isPerformanceMonitorEnabled(): boolean {
    return this.config.enablePerformanceMonitor;
  }

  /**
   * 获取日志级别
   */
  getLogLevel(): string {
    return this.config.logLevel;
  }

  /**
   * 记录日志（根据日志级别过滤）
   */
  log(level: 'debug' | 'info' | 'warn' | 'error', ...args: unknown[]): void {
    if (!this.config.enableDebug) {
      return;
    }

    const levels = ['debug', 'info', 'warn', 'error'];
    const currentLevelIndex = levels.indexOf(this.config.logLevel);
    const messageLevelIndex = levels.indexOf(level);

    if (messageLevelIndex >= currentLevelIndex) {
      console[level](...args);
    }
  }

  /**
   * 调试日志
   */
  debug(...args: unknown[]): void {
    this.log('debug', ...args);
  }

  /**
   * 信息日志
   */
  info(...args: unknown[]): void {
    this.log('info', ...args);
  }

  /**
   * 警告日志
   */
  warn(...args: unknown[]): void {
    this.log('warn', ...args);
  }

  /**
   * 错误日志
   */
  error(...args: unknown[]): void {
    this.log('error', ...args);
  }
}

// 创建单例实例
let environmentServiceInstance: EnvironmentService | null = null;

export function getEnvironmentService(): EnvironmentService {
  if (!environmentServiceInstance) {
    environmentServiceInstance = new EnvironmentService();
  }
  return environmentServiceInstance;
}

// 导出默认实例
export const environmentService = getEnvironmentService();

// 导出全局常量
export const APP_ENV = environmentService.getEnvironment();
export const APP_VERSION = environmentService.getConfig().appVersion;
export const APP_NAME = environmentService.getConfig().appName;
export const API_BASE_URL = environmentService.getApiBaseUrl();
export const IS_DEV = environmentService.isDevelopment();
export const IS_TEST = environmentService.isTesting();
export const IS_PROD = environmentService.isProduction();
