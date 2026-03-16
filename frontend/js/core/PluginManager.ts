/**
 * 插件管理器
 * 负责插件的加载、激活、停用和卸载
 */

import type {
  Plugin,
  PluginManifest,
  PluginType,
  PluginInfo,
  PluginContext,
  ServiceRegistry,
  EventBus
} from '../types/plugin';
import { PluginStatus } from '../types/plugin';

/**
 * 插件加载器接口
 */
interface PluginLoader {
  load(mainPath: string): Promise<new () => Plugin>;
}

/**
 * NPM插件加载器
 */
class NpmPluginLoader implements PluginLoader {
  async load(mainPath: string): Promise<new () => Plugin> {
    const module = await import(mainPath);
    return module.default as new () => Plugin;
  }
}

/**
 * 本地插件加载器
 */
class LocalPluginLoader implements PluginLoader {
  async load(mainPath: string): Promise<new () => Plugin> {
    const module = await import(/* @vite-ignore */ mainPath);
    return module.default as new () => Plugin;
  }
}

/**
 * 远程插件加载器
 */
class RemotePluginLoader implements PluginLoader {
  async load(mainPath: string): Promise<new () => Plugin> {
    const response = await fetch(mainPath);
    if (!response.ok) {
      throw new Error(`加载远程插件失败: ${response.statusText}`);
    }
    const code = await response.text();
    const PluginClass = new Function(
      'module',
      'exports',
      code + '\nreturn module.exports.default;'
    )({}, {}) as new () => Plugin;
    return PluginClass;
  }
}

/**
 * 插件管理器类
 */
export class PluginManager {
  private plugins: Map<string, PluginInfo> = new Map();
  private pluginLoaders: Map<string, PluginLoader> = new Map();
  private eventBus: EventBus;
  private serviceRegistry: ServiceRegistry;

  constructor(eventBus: EventBus, serviceRegistry: ServiceRegistry) {
    this.eventBus = eventBus;
    this.serviceRegistry = serviceRegistry;
    this.initializeLoaders();
  }

  /**
   * 初始化插件加载器
   */
  private initializeLoaders(): void {
    this.pluginLoaders.set('npm', new NpmPluginLoader());
    this.pluginLoaders.set('local', new LocalPluginLoader());
    this.pluginLoaders.set('remote', new RemotePluginLoader());
  }

  /**
   * 加载插件
   * @param manifestPath 插件清单路径
   * @returns 插件ID
   */
  async loadPlugin(manifestPath: string): Promise<string> {
    try {
      console.log(`[PluginManager] 开始加载插件: ${manifestPath}`);

      // 加载插件清单
      const manifest = await this.loadManifest(manifestPath);

      // 检查插件是否已加载
      if (this.plugins.has(manifest.id)) {
        console.warn(`[PluginManager] 插件 ${manifest.id} 已经加载`);
        return manifest.id;
      }

      // 检查依赖
      await this.checkDependencies(manifest);

      // 加载插件代码
      const loader = this.getLoader(manifestPath, manifest);
      const PluginClass = await loader.load(this.resolveMainPath(manifestPath, manifest.main));

      // 创建插件实例
      const plugin = new PluginClass();

      // 创建插件信息
      const pluginInfo: PluginInfo = {
        id: manifest.id,
        manifest,
        instance: plugin,
        status: PluginStatus.LOADED,
        loadedAt: new Date()
      };

      this.plugins.set(manifest.id, pluginInfo);

      // 初始化插件
      const context = this.createPluginContext(manifest);
      await plugin.initialize(context);

      console.log(`[PluginManager] 插件 ${manifest.name} (${manifest.id}) 加载成功`);

      // 触发事件
      this.eventBus.emit('plugin:loaded', {
        id: manifest.id,
        manifest,
        timestamp: new Date()
      });

      return manifest.id;
    } catch (error) {
      console.error(`[PluginManager] 加载插件失败: ${error}`);
      this.eventBus.emit('plugin:error', {
        error,
        manifestPath,
        timestamp: new Date()
      });
      throw error;
    }
  }

  /**
   * 激活插件
   * @param pluginId 插件ID
   */
  async activatePlugin(pluginId: string): Promise<void> {
    const pluginInfo = this.plugins.get(pluginId);
    if (!pluginInfo) {
      throw new Error(`插件 ${pluginId} 不存在`);
    }

    if (pluginInfo.status === PluginStatus.ACTIVATED) {
      console.warn(`[PluginManager] 插件 ${pluginId} 已经激活`);
      return;
    }

    try {
      console.log(`[PluginManager] 激活插件: ${pluginId}`);

      await pluginInfo.instance.activate();

      pluginInfo.status = PluginStatus.ACTIVATED;
      pluginInfo.activatedAt = new Date();

      console.log(`[PluginManager] 插件 ${pluginId} 激活成功`);

      // 触发事件
      this.eventBus.emit('plugin:activated', {
        id: pluginId,
        timestamp: new Date()
      });
    } catch (error) {
      console.error(`[PluginManager] 激活插件失败: ${error}`);
      pluginInfo.status = PluginStatus.ERROR;
      pluginInfo.error = error as Error;

      this.eventBus.emit('plugin:error', {
        error,
        pluginId,
        action: 'activate',
        timestamp: new Date()
      });
      throw error;
    }
  }

  /**
   * 停用插件
   * @param pluginId 插件ID
   */
  async deactivatePlugin(pluginId: string): Promise<void> {
    const pluginInfo = this.plugins.get(pluginId);
    if (!pluginInfo) {
      throw new Error(`插件 ${pluginId} 不存在`);
    }

    if (pluginInfo.status !== PluginStatus.ACTIVATED) {
      console.warn(`[PluginManager] 插件 ${pluginId} 未激活`);
      return;
    }

    try {
      console.log(`[PluginManager] 停用插件: ${pluginId}`);

      await pluginInfo.instance.deactivate();

      pluginInfo.status = PluginStatus.DEACTIVATED;

      console.log(`[PluginManager] 插件 ${pluginId} 停用成功`);

      // 触发事件
      this.eventBus.emit('plugin:deactivated', {
        id: pluginId,
        timestamp: new Date()
      });
    } catch (error) {
      console.error(`[PluginManager] 停用插件失败: ${error}`);
      pluginInfo.status = PluginStatus.ERROR;
      pluginInfo.error = error as Error;

      this.eventBus.emit('plugin:error', {
        error,
        pluginId,
        action: 'deactivate',
        timestamp: new Date()
      });
      throw error;
    }
  }

  /**
   * 卸载插件
   * @param pluginId 插件ID
   */
  async unloadPlugin(pluginId: string): Promise<void> {
    const pluginInfo = this.plugins.get(pluginId);
    if (!pluginInfo) {
      throw new Error(`插件 ${pluginId} 不存在`);
    }

    try {
      console.log(`[PluginManager] 卸载插件: ${pluginId}`);

      // 如果插件已激活，先停用
      if (pluginInfo.status === PluginStatus.ACTIVATED) {
        await this.deactivatePlugin(pluginId);
      }

      // 销毁插件
      await pluginInfo.instance.destroy();

      // 移除插件
      this.plugins.delete(pluginId);

      console.log(`[PluginManager] 插件 ${pluginId} 卸载成功`);

      // 触发事件
      this.eventBus.emit('plugin:unloaded', {
        id: pluginId,
        timestamp: new Date()
      });
    } catch (error) {
      console.error(`[PluginManager] 卸载插件失败: ${error}`);

      this.eventBus.emit('plugin:error', {
        error,
        pluginId,
        action: 'unload',
        timestamp: new Date()
      });
      throw error;
    }
  }

  /**
   * 获取插件
   * @param pluginId 插件ID
   * @returns 插件实例
   */
  getPlugin(pluginId: string): Plugin | undefined {
    return this.plugins.get(pluginId)?.instance;
  }

  /**
   * 获取插件信息
   * @param pluginId 插件ID
   * @returns 插件信息
   */
  getPluginInfo(pluginId: string): PluginInfo | undefined {
    return this.plugins.get(pluginId);
  }

  /**
   * 获取所有插件
   * @param type 插件类型（可选）
   * @returns 插件列表
   */
  getPlugins(type?: PluginType): Plugin[] {
    if (!type) {
      return Array.from(this.plugins.values()).map(info => info.instance);
    }

    return Array.from(this.plugins.values())
      .filter(info => info.manifest.type === type)
      .map(info => info.instance);
  }

  /**
   * 获取所有插件信息
   * @param type 插件类型（可选）
   * @returns 插件信息列表
   */
  getPluginsInfo(type?: PluginType): PluginInfo[] {
    if (!type) {
      return Array.from(this.plugins.values());
    }

    return Array.from(this.plugins.values()).filter(
      info => info.manifest.type === type
    );
  }

  /**
   * 获取已激活的插件
   * @returns 已激活的插件列表
   */
  getActivePlugins(): Plugin[] {
    return Array.from(this.plugins.values())
      .filter(info => info.status === PluginStatus.ACTIVATED)
      .map(info => info.instance);
  }

  /**
   * 检查插件是否已激活
   * @param pluginId 插件ID
   * @returns 是否已激活
   */
  isPluginActive(pluginId: string): boolean {
    const pluginInfo = this.plugins.get(pluginId);
    return pluginInfo?.status === PluginStatus.ACTIVATED || false;
  }

  /**
   * 检查插件是否存在
   * @param pluginId 插件ID
   * @returns 是否存在
   */
  hasPlugin(pluginId: string): boolean {
    return this.plugins.has(pluginId);
  }

  /**
   * 加载插件清单
   * @param manifestPath 清单路径
   * @returns 插件清单
   */
  private async loadManifest(manifestPath: string): Promise<PluginManifest> {
    const response = await fetch(manifestPath);
    if (!response.ok) {
      throw new Error(`加载插件清单失败: ${response.statusText}`);
    }
    return await response.json() as PluginManifest;
  }

  /**
   * 检查插件依赖
   * @param manifest 插件清单
   */
  private async checkDependencies(manifest: PluginManifest): Promise<void> {
    if (!manifest.dependencies || manifest.dependencies.length === 0) {
      return;
    }

    const missingDeps = manifest.dependencies.filter(depId => !this.plugins.has(depId));

    if (missingDeps.length > 0) {
      throw new Error(`缺少依赖插件: ${missingDeps.join(', ')}`);
    }

    // 检查循环依赖
    if (this.hasCircularDependency(manifest.id, manifest.dependencies)) {
      throw new Error(`检测到循环依赖: ${manifest.id}`);
    }
  }

  /**
   * 检查循环依赖
   * @param pluginId 插件ID
   * @param dependencies 依赖列表
   * @returns 是否有循环依赖
   */
  private hasCircularDependency(pluginId: string, dependencies: string[]): boolean {
    const visited = new Set<string>();
    const stack = [...dependencies];

    while (stack.length > 0) {
      const current = stack.pop()!;
      if (current === pluginId) {
        return true;
      }
      if (visited.has(current)) {
        continue;
      }
      visited.add(current);

      const currentInfo = this.plugins.get(current);
      if (currentInfo?.manifest.dependencies) {
        stack.push(...currentInfo.manifest.dependencies);
      }
    }

    return false;
  }

  /**
   * 获取插件加载器
   * @param manifestPath 清单路径
   * @param manifest 插件清单
   * @returns 插件加载器
   */
  private getLoader(manifestPath: string, manifest: PluginManifest): PluginLoader {
    const loaderType = manifest.loader || this.detectLoaderType(manifestPath);
    const loader = this.pluginLoaders.get(loaderType);

    if (!loader) {
      throw new Error(`不支持的加载器类型: ${loaderType}`);
    }

    return loader;
  }

  /**
   * 检测加载器类型
   * @param manifestPath 清单路径
   * @returns 加载器类型
   */
  private detectLoaderType(manifestPath: string): 'npm' | 'local' | 'remote' {
    if (manifestPath.startsWith('http://') || manifestPath.startsWith('https://')) {
      return 'remote';
    } else if (manifestPath.includes('node_modules')) {
      return 'npm';
    } else {
      return 'local';
    }
  }

  /**
   * 解析主文件路径
   * @param manifestPath 清单路径
   * @param mainPath 主文件相对路径
   * @returns 绝对路径
   */
  private resolveMainPath(manifestPath: string, mainPath: string): string {
    const basePath = manifestPath.substring(0, manifestPath.lastIndexOf('/'));
    return `${basePath}/${mainPath}`;
  }

  /**
   * 创建插件上下文
   * @param manifest 插件清单
   * @returns 插件上下文
   */
  private createPluginContext(manifest: PluginManifest): PluginContext {
    return {
      app: {
        registerService: (name: string, service: any) => {
          this.serviceRegistry.register(name, service);
        },
        getService: (name: string) => {
          return this.serviceRegistry.get(name);
        },
        emit: (event: string, data: any) => {
          this.eventBus.emit(event, data);
        },
        on: (event: string, handler: Function) => {
          return this.eventBus.on(event, handler);
        }
      },
      services: this.serviceRegistry,
      events: this.eventBus,
      config: manifest.config
    };
  }

  /**
   * 批量加载插件
   * @param manifestPaths 清单路径列表
   * @returns 插件ID列表
   */
  async loadPlugins(manifestPaths: string[]): Promise<string[]> {
    const results: string[] = [];

    for (const manifestPath of manifestPaths) {
      try {
        const pluginId = await this.loadPlugin(manifestPath);
        results.push(pluginId);
      } catch (error) {
        console.error(`[PluginManager] 加载插件失败 (${manifestPath}):`, error);
      }
    }

    return results;
  }

  /**
   * 批量激活插件
   * @param pluginIds 插件ID列表
   */
  async activatePlugins(pluginIds: string[]): Promise<void> {
    for (const pluginId of pluginIds) {
      try {
        await this.activatePlugin(pluginId);
      } catch (error) {
        console.error(`[PluginManager] 激活插件失败 (${pluginId}):`, error);
      }
    }
  }

  /**
   * 清理所有插件
   */
  async cleanup(): Promise<void> {
    console.log('[PluginManager] 开始清理所有插件');

    const pluginIds = Array.from(this.plugins.keys());

    for (const pluginId of pluginIds) {
      try {
        await this.unloadPlugin(pluginId);
      } catch (error) {
        console.error(`[PluginManager] 卸载插件失败 (${pluginId}):`, error);
      }
    }

    console.log('[PluginManager] 所有插件已清理');
  }
}
