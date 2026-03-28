const fs = require('fs');
const path = require('path');

function parseEnvFile(envPath) {
  const envContent = fs.readFileSync(envPath, 'utf-8');
  const envVars = {};

  envContent.split('\n').forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      return;
    }
    const eqIndex = trimmed.indexOf('=');
    if (eqIndex <= 0) {
      return;
    }
    const key = trimmed.slice(0, eqIndex).trim();
    const value = trimmed.slice(eqIndex + 1).trim();
    envVars[key] = value;
  });

  return envVars;
}

function buildApiBaseUrl(envVars) {
  const directApiBase = envVars.VITE_API_BASE_URL || envVars.VITE_API_URL || envVars.BACKEND_URL;
  if (directApiBase) {
    return directApiBase.replace(/\/+$/, '');
  }

  const host = envVars.VITE_BACKEND_HOST || envVars.IPCONFIG || 'localhost';
  const port = envVars.VITE_BACKEND_PORT || envVars.BACKEND_PORT || envVars.PORT || '8000';
  return `http://${host}:${port}`;
}

function updateOneConfig(configPath, envVars) {
  const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));

  // 更新 keystore 密码
  if (config.android && config.android.buildOptions) {
    config.android.buildOptions.keystorePassword = envVars.KEYSTORE_PASSWORD || '';
    config.android.buildOptions.keystoreAliasPassword = envVars.KEYSTORE_ALIAS_PASSWORD || '';
  }

  // 注入移动端可读取的后端地址（供运行时动态解析）
  const apiBaseUrl = buildApiBaseUrl(envVars);
  config.plugins = config.plugins || {};
  config.plugins.UDAKEConfig = {
    ...(config.plugins.UDAKEConfig || {}),
    apiBaseUrl
  };

  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
}

/**
 * 从环境变量加载配置并更新 capacitor.config.json
 */
function updateCapacitorConfig() {
  const configPaths = [
    path.join(__dirname, '..', 'configs', 'capacitor.config.json'),
    path.join(__dirname, '..', 'capacitor.config.json')
  ];
  const envPath = path.join(__dirname, '..', 'configs', 'env', '.env');

  const envVars = parseEnvFile(envPath);

  configPaths.forEach((configPath) => {
    if (fs.existsSync(configPath)) {
      updateOneConfig(configPath, envVars);
      console.log(`✅ 已更新 ${path.relative(path.join(__dirname, '..'), configPath)}`);
    } else {
      console.warn(`⚠️ 未找到配置文件: ${configPath}`);
    }
  });

  const apiBaseUrl = buildApiBaseUrl(envVars);
  console.log(`✅ 移动端后端地址: ${apiBaseUrl}`);
}

// 如果直接运行此脚本，执行更新
if (require.main === module) {
  updateCapacitorConfig();
}

module.exports = { updateCapacitorConfig };
