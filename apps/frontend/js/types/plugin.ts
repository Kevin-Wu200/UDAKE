/**
 * 插件类型定义
 */

/**
 * 插件类型枚举
 */
export enum PluginType {
  MAP_ENGINE = 'map-engine',
  DATA_IMPORTER = 'data-importer',
  INTERPOLATION_ALGORITHM = 'interpolation-algorithm',
  VISUALIZATION = 'visualization',
  REPORT_GENERATOR = 'report-generator'
}

/**
 * 插件接口
 */
export interface Plugin {
  /** 插件ID */
  id: string;
  /** 插件名称 */
  name: string;
  /** 插件版本 */
  version: string;
  /** 插件描述 */
  description?: string;
  /** 插件作者 */
  author?: string;
  /** 插件类型 */
  type: PluginType;
  /** 依赖的其他插件ID */
  dependencies?: string[];
  /** 插件配置 */
  config?: any;

  /**
   * 初始化插件
   * @param context 插件上下文
   */
  initialize(context: PluginContext): Promise<void>;

  /**
   * 激活插件
   */
  activate(): Promise<void>;

  /**
   * 停用插件
   */
  deactivate(): Promise<void>;

  /**
   * 销毁插件
   */
  destroy(): Promise<void>;
}

/**
 * 插件上下文
 */
export interface PluginContext {
  /** 应用实例 */
  app: Application;
  /** 服务注册表 */
  services: ServiceRegistry;
  /** 事件总线 */
  events: EventBus;
  /** 插件配置 */
  config?: any;
}

/**
 * 应用接口
 */
export interface Application {
  /**
   * 注册服务
   * @param name 服务名称
   * @param service 服务实例
   */
  registerService(name: string, service: any): void;

  /**
   * 获取服务
   * @param name 服务名称
   * @returns 服务实例
   */
  getService(name: string): any;

  /**
   * 发射事件
   * @param event 事件名称
   * @param data 事件数据
   */
  emit(event: string, data: any): void;

  /**
   * 监听事件
   * @param event 事件名称
   * @param handler 事件处理器
   * @returns 取消监听函数
   */
  on(event: string, handler: Function): () => void;
}

/**
 * 服务注册表接口
 */
export interface ServiceRegistry {
  /**
   * 注册服务
   * @param name 服务名称
   * @param service 服务实例
   * @param singleton 是否单例
   */
  register(name: string, service: any, singleton?: boolean): void;

  /**
   * 获取服务
   * @param name 服务名称
   * @returns 服务实例
   */
  get(name: string): any;

  /**
   * 获取单例服务
   * @param name 服务名称
   * @returns 服务实例
   */
  getSingleton(name: string): any;

  /**
   * 检查服务是否存在
   * @param name 服务名称
   * @returns 是否存在
   */
  has(name: string): boolean;

  /**
   * 注销服务
   * @param name 服务名称
   */
  unregister(name: string): void;
}

/**
 * 事件总线接口
 */
export interface EventBus {
  /**
   * 监听事件
   * @param event 事件名称
   * @param handler 事件处理器
   * @returns 取消监听函数
   */
  on(event: string, handler: Function): () => void;

  /**
   * 取消监听事件
   * @param event 事件名称
   * @param handler 事件处理器
   */
  off(event: string, handler: Function): void;

  /**
   * 发射事件
   * @param event 事件名称
   * @param data 事件数据
   */
  emit(event: string, data: any): void;

  /**
   * 监听一次性事件
   * @param event 事件名称
   * @param handler 事件处理器
   */
  once(event: string, handler: Function): void;

  /**
   * 清除所有监听器
   */
  clear(): void;
}

/**
 * 插件清单
 */
export interface PluginManifest {
  /** 插件ID */
  id: string;
  /** 插件名称 */
  name: string;
  /** 插件版本 */
  version: string;
  /** 插件描述 */
  description?: string;
  /** 插件作者 */
  author?: string;
  /** 插件类型 */
  type: PluginType;
  /** 主文件路径 */
  main: string;
  /** 依赖的其他插件ID */
  dependencies?: string[];
  /** 插件配置 */
  config?: any;
  /** 插件加载方式 */
  loader?: 'npm' | 'local' | 'remote';
  /** 插件权限 */
  permissions?: string[];
  /** 最小应用版本 */
  minAppVersion?: string;
}

/**
 * 插件状态
 */
export enum PluginStatus {
  LOADED = 'loaded',
  ACTIVATED = 'activated',
  DEACTIVATED = 'deactivated',
  UNLOADED = 'unloaded',
  ERROR = 'error'
}

/**
 * 插件信息
 */
export interface PluginInfo {
  /** 插件ID */
  id: string;
  /** 插件清单 */
  manifest: PluginManifest;
  /** 插件实例 */
  instance: Plugin;
  /** 插件状态 */
  status: PluginStatus;
  /** 加载时间 */
  loadedAt?: Date;
  /** 激活时间 */
  activatedAt?: Date;
  /** 错误信息 */
  error?: Error;
}