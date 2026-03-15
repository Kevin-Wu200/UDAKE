#!/usr/bin/env node

/**
 * UDAKE 插件创建工具
 * 用于快速创建插件脚手架
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');

// 颜色输出
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m'
};

function log(message, color = colors.reset) {
  console.log(`${color}${message}${colors.reset}`);
}

// 插件类型定义
const PLUGIN_TYPES = {
  'map-engine': '地图引擎',
  'data-importer': '数据导入',
  'interpolation-algorithm': '插值算法',
  'visualization': '可视化',
  'report-generator': '报告生成'
};

// 创建 readline 接口
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

// 问答函数
function question(prompt) {
  return new Promise((resolve) => {
    rl.question(prompt, (answer) => {
      resolve(answer.trim());
    });
  });
}

// 转换为 PascalCase
function toPascalCase(str) {
  return str
    .replace(/[-_\s]+(.)?/g, (_, c) => c ? c.toUpperCase() : '')
    .replace(/^(.)/, c => c.toUpperCase());
}

// 转换为 kebab-case
function toKebabCase(str) {
  return str
    .replace(/([a-z])([A-Z])/g, '$1-$2')
    .replace(/[\s_]+/g, '-')
    .toLowerCase();
}

// 验证插件 ID
function validatePluginId(id) {
  const regex = /^[a-z0-9-]+$/;
  return regex.test(id) && !id.startsWith('-') && !id.endsWith('-');
}

// 验证版本号
function validateVersion(version) {
  const regex = /^\d+\.\d+\.\d+$/;
  return regex.test(version);
}

// 创建目录结构
function createDirectoryStructure(pluginPath) {
  const directories = [
    pluginPath,
    path.join(pluginPath, 'src'),
    path.join(pluginPath, 'tests'),
    path.join(pluginPath, 'docs'),
    path.join(pluginPath, 'examples')
  ];

  directories.forEach(dir => {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
      log(`✓ 创建目录: ${dir}`, colors.green);
    }
  });
}

// 创建 manifest.json
function createManifest(pluginPath, answers) {
  const manifest = {
    id: answers.id,
    name: answers.name,
    version: answers.version,
    description: answers.description,
    author: answers.author,
    type: answers.type,
    main: './src/index.ts',
    loader: 'local',
    config: answers.config || {},
    permissions: answers.permissions || [],
    minAppVersion: '1.0.0'
  };

  const manifestPath = path.join(pluginPath, 'manifest.json');
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  log(`✓ 创建清单: ${manifestPath}`, colors.green);

  return manifest;
}

// 创建主文件
function createMainFile(pluginPath, answers) {
  const className = toPascalCase(answers.name);
  const code = `/**
 * ${answers.name}
 * ${answers.description}
 */

import type {
  Plugin,
  PluginContext,
  PluginType
} from '../../../frontend/js/types/plugin';

/**
 * ${answers.name} 插件配置
 */
interface ${className}Config {
  [key: string]: any;
}

/**
 * ${answers.name} 插件类
 */
export default class ${className} implements Plugin {
  id = '${answers.id}';
  name = '${answers.name}';
  version = '${answers.version}';
  type: PluginType = '${answers.type}' as any;
  description = '${answers.description}';

  private context?: PluginContext;
  private config?: ${className}Config;

  /**
   * 初始化插件
   */
  async initialize(context: PluginContext): Promise<void> {
    this.context = context;
    this.config = context.config as ${className}Config;

    console.log('[${className}] 初始化 ${answers.name} 插件');

    // 注册服务（如果需要）
    // context.app.registerService('${answers.id}', this, true);

    // 监听事件（如果需要）
    // context.events.on('some:event', this.onSomeEvent.bind(this));
  }

  /**
   * 激活插件
   */
  async activate(): Promise<void> {
    console.log('[${className}] 激活 ${answers.name} 插件');

    // 发射激活事件
    this.context?.events.emit('plugin:${answers.id}:activated', {
      plugin: this.id,
      timestamp: new Date()
    });
  }

  /**
   * 停用插件
   */
  async deactivate(): Promise<void> {
    console.log('[${className}] 停用 ${answers.name} 插件');

    // 发射停用事件
    this.context?.events.emit('plugin:${answers.id}:deactivated', {
      plugin: this.id,
      timestamp: new Date()
    });
  }

  /**
   * 销毁插件
   */
  async destroy(): Promise<void> {
    console.log('[${className}] 销毁 ${answers.name} 插件');

    await this.deactivate();
  }

  /**
   * 获取配置
   */
  getConfig(): ${className}Config | undefined {
    return this.config;
  }

  /**
   * 更新配置
   */
  updateConfig(config: Partial<${className}Config>): void {
    if (this.config) {
      this.config = { ...this.config, ...config };
      console.log('[${className}] 配置已更新');
    }
  }

  // 在这里添加你的插件功能方法
}
`;

  const mainFilePath = path.join(pluginPath, 'src', 'index.ts');
  fs.writeFileSync(mainFilePath, code);
  log(`✓ 创建主文件: ${mainFilePath}`, colors.green);
}

// 创建测试文件
function createTestFile(pluginPath, answers) {
  const className = toPascalCase(answers.name);
  const code = `/**
 * ${answers.name} 插件测试
 */

import ${className} from '../src/index';
import { EventBus } from '../../../frontend/js/core/EventBus';
import { ServiceRegistry } from '../../../frontend/js/core/ServiceRegistry';

describe('${className}', () => {
  let plugin: ${className};
  let eventBus: EventBus;
  let serviceRegistry: ServiceRegistry;

  beforeEach(() => {
    eventBus = new EventBus();
    serviceRegistry = new ServiceRegistry();
    plugin = new ${className}();
  });

  afterEach(async () => {
    if (plugin) {
      await plugin.destroy();
    }
  });

  test('应该成功初始化', async () => {
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
    expect(plugin.id).toBe('${answers.id}');
  });

  test('应该成功激活', async () => {
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
    // 添加激活后的断言
  });

  test('应该成功停用', async () => {
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
    await plugin.deactivate();
    // 添加停用后的断言
  });
});
`;

  const testFilePath = path.join(pluginPath, 'tests', 'index.test.ts');
  fs.writeFileSync(testFilePath, code);
  log(`✓ 创建测试文件: ${testFilePath}`, colors.green);
}

// 创建 README
function createReadme(pluginPath, answers) {
  const code = `# ${answers.name}

${answers.description}

## 基本信息

- **插件 ID**: \`${answers.id}\`
- **版本**: ${answers.version}
- **类型**: ${PLUGIN_TYPES[answers.type]}
- **作者**: ${answers.author}

## 安装

\`\`\`bash
# 本地开发
# 将插件目录复制到项目的 plugins/${answers.type}/${answers.id}/ 目录下
\`\`\`

## 使用

\`\`\`typescript
import PluginManager from '@/core/PluginManager';
import EventBus from '@/core/EventBus';
import ServiceRegistry from '@/core/ServiceRegistry';

// 创建实例
const eventBus = new EventBus();
const serviceRegistry = new ServiceRegistry();
const pluginManager = new PluginManager(eventBus, serviceRegistry);

// 加载插件
await pluginManager.loadPlugin('/plugins/${answers.type}/${answers.id}/manifest.json');

// 激活插件
await pluginManager.activatePlugin('${answers.id}');
\`\`\`

## 配置

插件支持以下配置选项：

\`\`\`json
{
  "config": {
    // 在这里添加你的配置选项
  }
}
\`\`\`

## API

### 初始化

\`\`\`typescript
await plugin.initialize(context);
\`\`\`

### 激活

\`\`\`typescript
await plugin.activate();
\`\`\`

### 停用

\`\`\`typescript
await plugin.deactivate();
\`\`\`

### 销毁

\`\`\`typescript
await plugin.destroy();
\`\`\`

## 开发

\`\`\`bash
# 运行测试
npm test

# 构建插件
npm run build

# 格式化代码
npm run format
\`\`\`

## 事件

插件会发射以下事件：

- \`plugin:${answers.id}:activated\` - 插件激活时
- \`plugin:${answers.id}:deactivated\` - 插件停用时

## 许可证

MIT

## 作者

${answers.author}
`;

  const readmePath = path.join(pluginPath, 'README.md');
  fs.writeFileSync(readmePath, code);
  log(`✓ 创建 README: ${readmePath}`, colors.green);
}

// 创建 .gitignore
function createGitignore(pluginPath) {
  const content = `node_modules/
dist/
*.log
.DS_Store
.env
.vscode/
.idea/
`;

  const gitignorePath = path.join(pluginPath, '.gitignore');
  fs.writeFileSync(gitignorePath, content);
  log(`✓ 创建 .gitignore: ${gitignorePath}`, colors.green);
}

// 创建 package.json
function createPackageJson(pluginPath, answers) {
  const content = {
    name: `udake-plugin-${answers.id}`,
    version: answers.version,
    description: answers.description,
    main: 'src/index.ts',
    types: 'src/index.ts',
    scripts: {
      test: 'vitest',
      build: 'tsc',
      format: 'prettier --write "src/**/*.ts" "tests/**/*.ts"'
    },
    keywords: [
      'udake',
      'plugin',
      answers.type,
      answers.id
    ],
    author: answers.author,
    license: 'MIT',
    devDependencies: {
      '@types/node': '^20.0.0',
      typescript: '^5.0.0',
      vitest: '^1.0.0',
      prettier: '^3.0.0'
    }
  };

  const packageJsonPath = path.join(pluginPath, 'package.json');
  fs.writeFileSync(packageJsonPath, JSON.stringify(content, null, 2));
  log(`✓ 创建 package.json: ${packageJsonPath}`, colors.green);
}

// 主函数
async function createPlugin() {
  log('\n🚀 UDAKE 插件创建工具\n', colors.bright);

  try {
    // 收集用户输入
    const answers: any = {};

    // 插件 ID
    while (true) {
      answers.id = await question('插件 ID (如: my-plugin): ');
      if (validatePluginId(answers.id)) {
        break;
      }
      log('❌ 无效的插件 ID，只能包含小写字母、数字和连字符', colors.red);
    }

    // 插件名称
    while (true) {
      answers.name = await question('插件名称: ');
      if (answers.name.length > 0) {
        break;
      }
      log('❌ 插件名称不能为空', colors.red);
    }

    // 插件版本
    while (true) {
      const version = await question('插件版本 (1.0.0): ') || '1.0.0';
      if (validateVersion(version)) {
        answers.version = version;
        break;
      }
      log('❌ 无效的版本号，格式应为 x.y.z', colors.red);
    }

    // 插件描述
    answers.description = await question('插件描述: ');

    // 插件作者
    answers.author = await question('插件作者: ');

    // 插件类型
    log('\n可用的插件类型:', colors.cyan);
    Object.entries(PLUGIN_TYPES).forEach(([key, value]) => {
      log(`  - ${key}: ${value}`, colors.reset);
    });

    while (true) {
      const type = await question('插件类型 (map-engine): ') || 'map-engine';
      if (PLUGIN_TYPES[type]) {
        answers.type = type;
        break;
      }
      log('❌ 无效的插件类型', colors.red);
    }

    // 确认信息
    log('\n📋 插件信息:', colors.bright);
    log(`  ID: ${answers.id}`, colors.cyan);
    log(`  名称: ${answers.name}`, colors.cyan);
    log(`  版本: ${answers.version}`, colors.cyan);
    log(`  描述: ${answers.description}`, colors.cyan);
    log(`  作者: ${answers.author}`, colors.cyan);
    log(`  类型: ${PLUGIN_TYPES[answers.type]}`, colors.cyan);

    const confirm = await question('\n确认创建插件? (y/n): ');
    if (confirm.toLowerCase() !== 'y') {
      log('已取消', colors.yellow);
      rl.close();
      return;
    }

    // 创建插件
    const pluginPath = path.join('plugins', answers.type, answers.id);

    log('\n📦 创建插件中...\n', colors.bright);

    createDirectoryStructure(pluginPath);
    createManifest(pluginPath, answers);
    createMainFile(pluginPath, answers);
    createTestFile(pluginPath, answers);
    createReadme(pluginPath, answers);
    createGitignore(pluginPath);
    createPackageJson(pluginPath, answers);

    log('\n✅ 插件创建成功!\n', colors.bright);
    log(`📁 插件路径: ${path.resolve(pluginPath)}`, colors.green);
    log(`\n下一步:`, colors.cyan);
    log(`  1. 进入插件目录: cd ${pluginPath}`, colors.reset);
    log(`  2. 编辑插件代码: vim src/index.ts`, colors.reset);
    log(`  3. 运行测试: npm test`, colors.reset);
    log(`  4. 构建插件: npm run build`, colors.reset);

  } catch (error) {
    log(`\n❌ 创建插件失败: ${error.message}`, colors.red);
  } finally {
    rl.close();
  }
}

// 运行
createPlugin();