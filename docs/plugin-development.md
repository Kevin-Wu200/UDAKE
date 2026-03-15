# 插件开发指南

本指南将帮助您了解如何为 UDAKE 开发插件。

## 目录

- [简介](#简介)
- [插件架构](#插件架构)
- [快速开始](#快速开始)
- [插件类型](#插件类型)
- [插件清单](#插件清单)
- [插件接口](#插件接口)
- [事件系统](#事件系统)
- [服务系统](#服务系统)
- [最佳实践](#最佳实践)
- [测试](#测试)
- [发布](#发布)
- [示例](#示例)

## 简介

UDAKE 插件系统允许您扩展应用的功能，而无需修改核心代码。插件可以：

- 添加新的地图引擎
- 实现数据导入/导出功能
- 提供新的插值算法
- 创建可视化组件
- 生成自定义报告

## 插件架构

### 核心组件

- **PluginManager**: 插件管理器，负责插件的加载、激活、停用和卸载
- **EventBus**: 事件总线，用于插件和应用之间的通信
- **ServiceRegistry**: 服务注册表，用于管理应用服务
- **PluginMarket**: 插件市场，用于插件的发现和安装

### 插件生命周期

1. **加载 (Load)**: 从 manifest.json 加载插件信息
2. **初始化 (Initialize)**: 创建插件实例并初始化
3. **激活 (Activate)**: 激活插件功能
4. **停用 (Deactivate)**: 停用插件功能
5. **卸载 (Unload)**: 销毁插件实例

## 快速开始

### 使用脚手架工具

最简单的方法是使用插件脚手架工具：

```bash
node scripts/create-plugin.js
```

按照提示输入插件信息，工具会自动创建插件目录结构和文件。

### 手动创建

1. 创建插件目录：

```bash
mkdir -p plugins/map-engines/my-plugin
```

2. 创建 `manifest.json`:

```json
{
  "id": "my-plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "My awesome plugin",
  "author": "Your Name",
  "type": "map-engine",
  "main": "./src/index.ts",
  "loader": "local",
  "config": {},
  "permissions": [],
  "minAppVersion": "1.0.0"
}
```

3. 创建 `src/index.ts`:

```typescript
import type { Plugin, PluginContext, PluginType } from '../../../frontend/js/types/plugin';

export default class MyPlugin implements Plugin {
  id = 'my-plugin';
  name = 'My Plugin';
  version = '1.0.0';
  type: PluginType = 'map-engine' as any;
  description = 'My awesome plugin';

  private context?: PluginContext;

  async initialize(context: PluginContext): Promise<void> {
    this.context = context;
    console.log('[MyPlugin] 初始化');
  }

  async activate(): Promise<void> {
    console.log('[MyPlugin] 激活');
  }

  async deactivate(): Promise<void> {
    console.log('[MyPlugin] 停用');
  }

  async destroy(): Promise<void> {
    console.log('[MyPlugin] 销毁');
  }
}
```

## 插件类型

### 地图引擎插件 (map-engine)

提供地图渲染和交互功能。

```typescript
interface MapEnginePlugin extends Plugin {
  render(container: HTMLElement, options: RenderOptions): void;
  addLayer(options: LayerOptions): void;
  removeLayer(layerId: string): void;
  zoom(zoom: number): void;
  pan(center: { longitude: number; latitude: number }): void;
}
```

### 数据导入插件 (data-importer)

导入各种格式的数据。

```typescript
interface DataImporterPlugin extends Plugin {
  import(file: File): Promise<ImportResult>;
  importFromString(content: string): Promise<ImportResult>;
  export(data: any): string;
  download(data: any, filename: string): void;
}
```

### 插值算法插件 (interpolation-algorithm)

执行空间插值计算。

```typescript
interface InterpolationAlgorithmPlugin extends Plugin {
  interpolate(points: DataPoint[], options: InterpolationOptions): Promise<InterpolationResult>;
  validate(points: DataPoint[]): boolean;
  getParameters(): Parameter[];
}
```

### 可视化插件 (visualization)

提供数据可视化功能。

```typescript
interface VisualizationPlugin extends Plugin {
  render(data: any, container: HTMLElement, options: RenderOptions): void;
  update(data: any): void;
  export(): string;
  getConfig(): VisualizationConfig;
}
```

### 报告生成插件 (report-generator)

生成分析报告。

```typescript
interface ReportGeneratorPlugin extends Plugin {
  generate(data: ReportData, options: ReportOptions): Promise<ReportResult>;
  export(report: ReportResult, format: ExportFormat): Blob;
  preview(report: ReportResult): string;
}
```

## 插件清单

`manifest.json` 是插件的配置文件，包含以下字段：

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 插件唯一标识符，只能包含小写字母、数字和连字符 |
| `name` | string | 是 | 插件显示名称 |
| `version` | string | 是 | 插件版本，格式为 x.y.z |
| `description` | string | 否 | 插件描述 |
| `author` | string | 否 | 插件作者 |
| `type` | string | 是 | 插件类型 |
| `main` | string | 是 | 插件主文件路径 |
| `loader` | string | 否 | 加载器类型（npm/local/remote） |
| `config` | object | 否 | 插件默认配置 |
| `permissions` | array | 否 | 插件权限列表 |
| `minAppVersion` | string | 否 | 最低应用版本 |
| `dependencies` | array | 否 | 依赖的其他插件ID |

## 插件接口

所有插件必须实现 `Plugin` 接口：

```typescript
interface Plugin {
  id: string;
  name: string;
  version: string;
  description?: string;
  author?: string;
  type: PluginType;
  dependencies?: string[];
  config?: any;

  initialize(context: PluginContext): Promise<void>;
  activate(): Promise<void>;
  deactivate(): Promise<void>;
  destroy(): Promise<void>;
}
```

### PluginContext

插件上下文提供对应用服务的访问：

```typescript
interface PluginContext {
  app: Application;
  services: ServiceRegistry;
  events: EventBus;
  config?: any;
}
```

### Application

应用接口允许插件与应用交互：

```typescript
interface Application {
  registerService(name: string, service: any): void;
  getService(name: string): any;
  emit(event: string, data: any): void;
  on(event: string, handler: Function): () => void;
}
```

## 事件系统

插件可以通过事件总线发送和接收事件。

### 发射事件

```typescript
this.context?.events.emit('my-plugin:ready', {
  timestamp: new Date(),
  data: someData
});
```

### 监听事件

```typescript
// 在 initialize 中监听
this.context?.events.on('map:zoom', (data) => {
  console.log('地图缩放:', data);
});

// 返回取消订阅函数
const unsubscribe = this.context?.events.on('some:event', handler);

// 取消订阅
unsubscribe?.();
```

### 内置事件

- `plugin:loaded` - 插件已加载
- `plugin:activated` - 插件已激活
- `plugin:deactivated` - 插件已停用
- `plugin:unloaded` - 插件已卸载
- `plugin:error` - 插件错误

## 服务系统

插件可以注册和访问应用服务。

### 注册服务

```typescript
this.context?.app.registerService('my-service', {
  doSomething: () => {
    console.log('Doing something');
  }
}, true); // true 表示单例
```

### 获取服务

```typescript
const service = this.context?.app.getService('my-service');
service?.doSomething();
```

### 使用服务注册表

```typescript
const service = this.context?.services.get('my-service');
```

## 最佳实践

### 1. 错误处理

始终使用 try-catch 处理错误：

```typescript
async activate(): Promise<void> {
  try {
    // 插件激活逻辑
  } catch (error) {
    console.error('[MyPlugin] 激活失败:', error);
    throw error;
  }
}
```

### 2. 资源清理

在 `destroy` 方法中清理所有资源：

```typescript
async destroy(): Promise<void> {
  // 清理事件监听器
  this.unsubscribers?.forEach(unsubscribe => unsubscribe());

  // 清理服务
  this.context?.app.getService('some-service')?.cleanup();

  // 清理其他资源
}
```

### 3. 配置管理

使用配置对象而不是硬编码：

```typescript
private config?: MyPluginConfig;

async initialize(context: PluginContext): Promise<void> {
  this.config = {
    timeout: context.config?.timeout || 5000,
    retries: context.config?.retries || 3,
    ...context.config
  };
}
```

### 4. 事件命名

使用命名空间避免冲突：

```typescript
// 好的做法
this.context?.events.emit('my-plugin:ready', data);

// 不好的做法
this.context?.events.emit('ready', data);
```

### 5. 日志记录

使用统一的日志格式：

```typescript
console.log('[MyPlugin] 信息');
console.warn('[MyPlugin] 警告');
console.error('[MyPlugin] 错误');
```

## 测试

### 单元测试

使用 Vitest 进行单元测试：

```typescript
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import MyPlugin from '../src/index';
import { EventBus } from '../../../frontend/js/core/EventBus';
import { ServiceRegistry } from '../../../frontend/js/core/ServiceRegistry';

describe('MyPlugin', () => {
  let plugin: MyPlugin;
  let eventBus: EventBus;
  let serviceRegistry: ServiceRegistry;

  beforeEach(() => {
    eventBus = new EventBus();
    serviceRegistry = new ServiceRegistry();
    plugin = new MyPlugin();
  });

  afterEach(async () => {
    if (plugin) {
      await plugin.destroy();
    }
  });

  it('应该成功初始化', async () => {
    const context = {
      app: {
        registerService: jest.fn(),
        getService: jest.fn(),
        emit: jest.fn(),
        on: jest.fn()
      },
      services: serviceRegistry,
      events: eventBus,
      config: {}
    };

    await plugin.initialize(context);
    expect(plugin.id).toBe('my-plugin');
  });

  it('应该成功激活', async () => {
    const context = {
      app: {
        registerService: jest.fn(),
        getService: jest.fn(),
        emit: jest.fn(),
        on: jest.fn()
      },
      services: serviceRegistry,
      events: eventBus,
      config: {}
    };

    await plugin.initialize(context);
    await plugin.activate();
  });
});
```

### 集成测试

测试插件与应用的集成：

```typescript
import PluginManager from '@/core/PluginManager';
import EventBus from '@/core/EventBus';
import ServiceRegistry from '@/core/ServiceRegistry';

describe('Plugin Integration', () => {
  let pluginManager: PluginManager;
  let eventBus: EventBus;
  let serviceRegistry: ServiceRegistry;

  beforeEach(() => {
    eventBus = new EventBus();
    serviceRegistry = new ServiceRegistry();
    pluginManager = new PluginManager(eventBus, serviceRegistry);
  });

  it('应该成功加载和激活插件', async () => {
    const pluginId = await pluginManager.loadPlugin(
      '/plugins/map-engines/my-plugin/manifest.json'
    );

    expect(pluginId).toBe('my-plugin');
    expect(pluginManager.hasPlugin(pluginId)).toBe(true);

    await pluginManager.activatePlugin(pluginId);
    expect(pluginManager.isPluginActive(pluginId)).toBe(true);
  });
});
```

### 使用测试工具

使用提供的测试工具：

```bash
node scripts/test-plugin.js plugins/map-engines/my-plugin
```

## 发布

### 1. 准备发布

确保您的插件符合以下要求：

- 所有测试通过
- 代码已格式化
- 文档完整
- 清单文件正确

### 2. 构建插件

```bash
npm run build
```

### 3. 发布到插件市场

将插件提交到 UDAKE 插件市场：

```bash
# 插件市场CLI
npm install -g @udake/plugin-publisher
udake-plugin publish
```

### 4. 版本管理

遵循语义化版本控制：

- **主版本号**: 不兼容的 API 修改
- **次版本号**: 向下兼容的功能性新增
- **修订号**: 向下兼容的问题修正

## 示例

### 示例 1: 简单的地图引擎插件

```typescript
import type { Plugin, PluginContext, PluginType } from '../../../frontend/js/types/plugin';

export default class SimpleMapEngine implements Plugin {
  id = 'simple-map';
  name = 'Simple Map Engine';
  version = '1.0.0';
  type: PluginType = 'map-engine' as any;
  description = '简单的地图引擎示例';

  private context?: PluginContext;
  private mapInstance?: any;

  async initialize(context: PluginContext): Promise<void> {
    this.context = context;
    context.app.registerService('map-engine', this, true);
  }

  async activate(): Promise<void> {
    console.log('[SimpleMapEngine] 激活');
  }

  async deactivate(): Promise<void> {
    console.log('[SimpleMapEngine] 停用');
  }

  async destroy(): Promise<void> {
    await this.deactivate();
  }

  render(container: HTMLElement, options: any): void {
    this.mapInstance = { container, ...options };
    console.log('[SimpleMapEngine] 渲染地图');
  }
}
```

### 示例 2: 数据导入插件

```typescript
import type { Plugin, PluginContext, PluginType } from '../../../frontend/js/types/plugin';

interface ImportResult {
  success: boolean;
  data?: any;
  error?: string;
}

export default class CSVImporter implements Plugin {
  id = 'csv-importer';
  name = 'CSV Importer';
  version = '1.0.0';
  type: PluginType = 'data-importer' as any;
  description = 'CSV 数据导入插件';

  private context?: PluginContext;

  async initialize(context: PluginContext): Promise<void> {
    this.context = context;
    context.app.registerService('csv-importer', this, true);
  }

  async activate(): Promise<void> {
    console.log('[CSVImporter] 激活');
  }

  async deactivate(): Promise<void> {
    console.log('[CSVImporter] 停用');
  }

  async destroy(): Promise<void> {
    await this.deactivate();
  }

  async import(file: File): Promise<ImportResult> {
    try {
      const content = await file.text();
      const data = this.parseCSV(content);

      return {
        success: true,
        data
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  private parseCSV(content: string): any[] {
    const lines = content.split('\n');
    const headers = lines[0].split(',');

    return lines.slice(1).map(line => {
      const values = line.split(',');
      return headers.reduce((obj, header, index) => {
        obj[header.trim()] = values[index]?.trim();
        return obj;
      }, {} as any);
    });
  }
}
```

## 支持

如有问题，请查看：

- [插件架构文档](./plugin-architecture.md)
- [示例插件](../plugins/)
- [UDAKE 社区论坛](https://community.udake.io)
- [GitHub Issues](https://github.com/udake/udake/issues)

## 许可证

MIT License