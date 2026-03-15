#!/usr/bin/env node

/**
 * UDAKE 插件测试工具
 * 用于测试插件的功能
 */

const fs = require('fs');
const path = require('path');

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

// 测试结果
class TestResult {
  constructor() {
    this.passed = 0;
    this.failed = 0;
    this.errors = [];
  }

  pass(message) {
    this.passed++;
    log(`  ✓ ${message}`, colors.green);
  }

  fail(message, error) {
    this.failed++;
    this.errors.push({ message, error });
    log(`  ✗ ${message}`, colors.red);
    if (error) {
      log(`    错误: ${error.message}`, colors.red);
    }
  }

  summary() {
    log(`\n📊 测试结果:`, colors.bright);
    log(`  通过: ${this.passed}`, colors.green);
    log(`  失败: ${this.failed}`, this.failed > 0 ? colors.red : colors.green);

    if (this.errors.length > 0) {
      log(`\n❌ 失败的测试:`, colors.red);
      this.errors.forEach((err, index) => {
        log(`  ${index + 1}. ${err.message}`, colors.red);
        log(`     ${err.error.stack}`, colors.red);
      });
    }

    return this.failed === 0;
  }
}

// 验证 manifest.json
function validateManifest(manifestPath) {
  const result = new TestResult();

  log(`\n📝 验证 manifest.json`, colors.bright);

  try {
    const content = fs.readFileSync(manifestPath, 'utf-8');
    const manifest = JSON.parse(content);

    // 检查必需字段
    const requiredFields = ['id', 'name', 'version', 'type', 'main'];
    requiredFields.forEach(field => {
      if (manifest[field]) {
        result.pass(`字段 ${field} 存在`);
      } else {
        result.fail(`字段 ${field} 不存在`);
      }
    });

    // 验证 ID 格式
    const idRegex = /^[a-z0-9-]+$/;
    if (idRegex.test(manifest.id)) {
      result.pass('ID 格式正确');
    } else {
      result.fail('ID 格式不正确，只能包含小写字母、数字和连字符');
    }

    // 验证版本号格式
    const versionRegex = /^\d+\.\d+\.\d+$/;
    if (versionRegex.test(manifest.version)) {
      result.pass('版本号格式正确');
    } else {
      result.fail('版本号格式不正确，应为 x.y.z');
    }

    // 验证类型
    const validTypes = ['map-engine', 'data-importer', 'interpolation-algorithm', 'visualization', 'report-generator'];
    if (validTypes.includes(manifest.type)) {
      result.pass('插件类型有效');
    } else {
      result.fail(`插件类型无效，应为: ${validTypes.join(', ')}`);
    }

    // 验证主文件路径
    const mainFilePath = path.join(path.dirname(manifestPath), manifest.main);
    if (fs.existsSync(mainFilePath)) {
      result.pass('主文件存在');
    } else {
      result.fail(`主文件不存在: ${mainFilePath}`);
    }

    return { valid: result.summary(), manifest };

  } catch (error) {
    result.fail('解析 manifest.json 失败', error);
    result.summary();
    return { valid: false, manifest: null };
  }
}

// 验证主文件
function validateMainFile(mainFilePath, manifest) {
  const result = new TestResult();

  log(`\n📝 验证主文件`, colors.bright);

  try {
    const content = fs.readFileSync(mainFilePath, 'utf-8');

    // 检查是否导出了默认类
    if (content.includes('export default class')) {
      result.pass('导出了默认类');
    } else {
      result.fail('未导出默认类');
    }

    // 检查是否实现了 Plugin 接口
    if (content.includes('implements Plugin')) {
      result.pass('实现了 Plugin 接口');
    } else {
      result.fail('未实现 Plugin 接口');
    }

    // 检查必需的方法
    const requiredMethods = ['initialize', 'activate', 'deactivate', 'destroy'];
    requiredMethods.forEach(method => {
      if (content.includes(`async ${method}`)) {
        result.pass(`方法 ${method} 存在`);
      } else {
        result.fail(`方法 ${method} 不存在`);
      }
    });

    // 检查插件属性
    if (content.includes(`id = '${manifest.id}'`)) {
      result.pass('插件 ID 正确');
    } else {
      result.fail('插件 ID 不正确');
    }

    return result.summary();

  } catch (error) {
    result.fail('读取主文件失败', error);
    result.summary();
    return false;
  }
}

// 验证目录结构
function validateDirectoryStructure(pluginPath) {
  const result = new TestResult();

  log(`\n📝 验证目录结构`, colors.bright);

  const requiredDirs = ['src', 'tests', 'docs'];
  requiredDirs.forEach(dir => {
    const dirPath = path.join(pluginPath, dir);
    if (fs.existsSync(dirPath)) {
      result.pass(`目录 ${dir} 存在`);
    } else {
      result.fail(`目录 ${dir} 不存在`);
    }
  });

  const requiredFiles = ['manifest.json', 'README.md', 'package.json', '.gitignore'];
  requiredFiles.forEach(file => {
    const filePath = path.join(pluginPath, file);
    if (fs.existsSync(filePath)) {
      result.pass(`文件 ${file} 存在`);
    } else {
      result.fail(`文件 ${file} 不存在`);
    }
  });

  return result.summary();
}

// 运行插件测试
function testPlugin(pluginPath) {
  log('\n🧪 开始测试插件\n', colors.bright);

  // 解析插件路径
  const absolutePath = path.resolve(pluginPath);

  // 检查插件目录是否存在
  if (!fs.existsSync(absolutePath)) {
    log(`❌ 插件目录不存在: ${absolutePath}`, colors.red);
    return false;
  }

  log(`📁 插件路径: ${absolutePath}`, colors.cyan);

  // 验证目录结构
  const structureValid = validateDirectoryStructure(absolutePath);

  // 验证 manifest.json
  const manifestPath = path.join(absolutePath, 'manifest.json');
  const { valid: manifestValid, manifest } = validateManifest(manifestPath);

  if (!manifestValid) {
    log('\n❌ manifest.json 验证失败，停止测试', colors.red);
    return false;
  }

  // 验证主文件
  const mainFilePath = path.join(absolutePath, manifest.main);
  const mainFileValid = validateMainFile(mainFilePath, manifest);

  // 总结
  const allValid = structureValid && manifestValid && mainFileValid;

  if (allValid) {
    log('\n✅ 所有测试通过!', colors.green);
  } else {
    log('\n❌ 部分测试失败', colors.red);
  }

  return allValid;
}

// 主函数
function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    log('📖 用法: node test-plugin.js <插件路径>', colors.cyan);
    log('  示例: node test-plugin.js plugins/map-engines/arcgis', colors.reset);
    process.exit(1);
  }

  const pluginPath = args[0];
  const success = testPlugin(pluginPath);

  process.exit(success ? 0 : 1);
}

// 运行
main();