/**
 * 服务注册表
 * 用于管理应用中的服务
 */

import type { ServiceRegistry as ServiceRegistryInterface } from '../types/plugin';

/**
 * 服务信息
 */
interface ServiceInfo {
  instance: any;
  singleton: boolean;
  createdAt: Date;
  dependencies?: string[];
}

/**
 * 服务注册表类
 */
export class ServiceRegistry implements ServiceRegistryInterface {
  private services: Map<string, ServiceInfo> = new Map();
  private pendingResolutions: Set<string> = new Set();
  private resolutionStack: string[] = [];

  /**
   * 注册服务
   * @param name 服务名称
   * @param service 服务实例
   * @param singleton 是否单例
   * @param dependencies 依赖的服务名称列表
   */
  register(
    name: string,
    service: any,
    singleton: boolean = false,
    dependencies?: string[]
  ): void {
    if (this.services.has(name)) {
      console.warn(`[ServiceRegistry] 服务 ${name} 已存在，将被覆盖`);
    }

    // 检查依赖是否存在
    if (dependencies) {
      const missingDeps = dependencies.filter(dep => !this.services.has(dep));
      if (missingDeps.length > 0) {
        throw new Error(`服务 ${name} 的依赖不存在: ${missingDeps.join(', ')}`);
      }
    }

    const serviceInfo: ServiceInfo = {
      instance: service,
      singleton,
      createdAt: new Date(),
      dependencies
    };

    this.services.set(name, serviceInfo);

    console.log(`[ServiceRegistry] 服务 ${name} 已注册${singleton ? ' (单例)' : ''}`);
  }

  /**
   * 注册工厂函数
   * @param name 服务名称
   * @param factory 工厂函数
   * @param singleton 是否单例
   * @param dependencies 依赖的服务名称列表
   */
  registerFactory(
    name: string,
    factory: (...args: any[]) => any,
    singleton: boolean = false,
    dependencies?: string[]
  ): void {
    this.register(name, factory, singleton, dependencies);
  }

  /**
   * 获取服务
   * @param name 服务名称
   * @returns 服务实例
   */
  get(name: string): any {
    const serviceInfo = this.services.get(name);

    if (!serviceInfo) {
      throw new Error(`服务 ${name} 不存在`);
    }

    // 如果是工厂函数，则调用它
    if (typeof serviceInfo.instance === 'function') {
      // 检查循环依赖
      if (this.resolutionStack.includes(name)) {
        throw new Error(
          `检测到循环依赖: ${this.resolutionStack.join(' -> ')} -> ${name}`
        );
      }

      // 如果是单例且已经实例化，返回实例
      if (serviceInfo.singleton && typeof serviceInfo.instance !== 'function') {
        return serviceInfo.instance;
      }

      try {
        this.resolutionStack.push(name);

        // 获取依赖
        const dependencies = serviceInfo.dependencies || [];
        const args = dependencies.map(dep => this.get(dep));

        // 创建实例
        const instance = serviceInfo.instance(...args);

        // 如果是单例，保存实例
        if (serviceInfo.singleton) {
          serviceInfo.instance = instance;
        }

        this.resolutionStack.pop();

        return instance;
      } catch (error) {
        this.resolutionStack.pop();
        throw error;
      }
    }

    return serviceInfo.instance;
  }

  /**
   * 获取单例服务
   * @param name 服务名称
   * @returns 服务实例
   */
  getSingleton(name: string): any {
    const serviceInfo = this.services.get(name);

    if (!serviceInfo) {
      throw new Error(`服务 ${name} 不存在`);
    }

    if (!serviceInfo.singleton) {
      console.warn(`[ServiceRegistry] 服务 ${name} 不是单例`);
    }

    return this.get(name);
  }

  /**
   * 检查服务是否存在
   * @param name 服务名称
   * @returns 是否存在
   */
  has(name: string): boolean {
    return this.services.has(name);
  }

  /**
   * 注销服务
   * @param name 服务名称
   */
  unregister(name: string): void {
    if (!this.services.has(name)) {
      console.warn(`[ServiceRegistry] 服务 ${name} 不存在`);
      return;
    }

    // 检查是否有其他服务依赖此服务
    const dependents = this.getDependents(name);
    if (dependents.length > 0) {
      console.warn(
        `[ServiceRegistry] 服务 ${name} 被以下服务依赖: ${dependents.join(', ')}`
      );
    }

    this.services.delete(name);
    console.log(`[ServiceRegistry] 服务 ${name} 已注销`);
  }

  /**
   * 清除所有服务
   */
  clear(): void {
    this.services.clear();
    console.log('[ServiceRegistry] 所有服务已清除');
  }

  /**
   * 获取所有服务名称
   * @returns 服务名称列表
   */
  getServiceNames(): string[] {
    return Array.from(this.services.keys());
  }

  /**
   * 获取服务信息
   * @param name 服务名称
   * @returns 服务信息
   */
  getServiceInfo(name: string): ServiceInfo | undefined {
    return this.services.get(name);
  }

  /**
   * 获取所有服务信息
   * @returns 所有服务信息
   */
  getAllServicesInfo(): Map<string, ServiceInfo> {
    return new Map(this.services);
  }

  /**
   * 获取依赖某个服务的所有服务
   * @param name 服务名称
   * @returns 依赖的服务名称列表
   */
  getDependents(name: string): string[] {
    const dependents: string[] = [];

    this.services.forEach((serviceInfo, serviceName) => {
      if (serviceInfo.dependencies?.includes(name)) {
        dependents.push(serviceName);
      }
    });

    return dependents;
  }

  /**
   * 检查服务是否是单例
   * @param name 服务名称
   * @returns 是否是单例
   */
  isSingleton(name: string): boolean {
    return this.services.get(name)?.singleton || false;
  }

  /**
   * 替换服务实例
   * @param name 服务名称
   * @param newInstance 新实例
   */
  replaceInstance(name: string, newInstance: any): void {
    const serviceInfo = this.services.get(name);

    if (!serviceInfo) {
      throw new Error(`服务 ${name} 不存在`);
    }

    serviceInfo.instance = newInstance;
    console.log(`[ServiceRegistry] 服务 ${name} 的实例已替换`);
  }

  /**
   * 获取服务注册表统计信息
   * @returns 统计信息
   */
  getStats(): {
    totalServices: number;
    singletonCount: number;
    factoryCount: number;
    servicesWithDependencies: number;
  } {
    let singletonCount = 0;
    let factoryCount = 0;
    let servicesWithDependencies = 0;

    this.services.forEach(serviceInfo => {
      if (serviceInfo.singleton) {
        singletonCount++;
      }
      if (typeof serviceInfo.instance === 'function') {
        factoryCount++;
      }
      if (serviceInfo.dependencies && serviceInfo.dependencies.length > 0) {
        servicesWithDependencies++;
      }
    });

    return {
      totalServices: this.services.size,
      singletonCount,
      factoryCount,
      servicesWithDependencies
    };
  }

  /**
   * 验证服务依赖关系
   * @returns 验证结果
   */
  validateDependencies(): {
    valid: boolean;
    errors: string[];
  } {
    const errors: string[] = [];

    this.services.forEach((serviceInfo, serviceName) => {
      if (serviceInfo.dependencies) {
        serviceInfo.dependencies.forEach(dep => {
          if (!this.services.has(dep)) {
            errors.push(`服务 ${serviceName} 的依赖 ${dep} 不存在`);
          }
        });
      }
    });

    // 检查循环依赖
    const cycle = this.detectCycle();
    if (cycle) {
      errors.push(`检测到循环依赖: ${cycle.join(' -> ')}`);
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  /**
   * 检测循环依赖
   * @returns 循环依赖路径，如果没有则返回null
   */
  private detectCycle(): string[] | null {
    const visited = new Set<string>();
    const recursionStack = new Set<string>();

    const visit = (serviceName: string, path: string[]): string[] | null => {
      if (recursionStack.has(serviceName)) {
        return [...path, serviceName];
      }

      if (visited.has(serviceName)) {
        return null;
      }

      visited.add(serviceName);
      recursionStack.add(serviceName);

      const serviceInfo = this.services.get(serviceName);
      if (serviceInfo?.dependencies) {
        for (const dep of serviceInfo.dependencies) {
          const cycle = visit(dep, [...path, serviceName]);
          if (cycle) {
            return cycle;
          }
        }
      }

      recursionStack.delete(serviceName);
      return null;
    };

    for (const serviceName of this.services.keys()) {
      const cycle = visit(serviceName, []);
      if (cycle) {
        return cycle;
      }
    }

    return null;
  }

  /**
   * 批量注册服务
   * @param services 服务列表
   */
  registerBatch(services: Array<{
    name: string;
    service: any;
    singleton?: boolean;
    dependencies?: string[];
  }>): void {
    services.forEach(({ name, service, singleton, dependencies }) => {
      this.register(name, service, singleton, dependencies);
    });
  }

  /**
   * 别名服务
   * @param originalName 原服务名称
   * @param aliasName 别名
   */
  alias(originalName: string, aliasName: string): void {
    if (!this.services.has(originalName)) {
      throw new Error(`服务 ${originalName} 不存在`);
    }

    if (this.services.has(aliasName)) {
      console.warn(`[ServiceRegistry] 服务 ${aliasName} 已存在，将被覆盖`);
    }

    const serviceInfo = this.services.get(originalName)!;
    this.services.set(aliasName, serviceInfo);

    console.log(`[ServiceRegistry] 服务 ${originalName} 已别名为 ${aliasName}`);
  }
}