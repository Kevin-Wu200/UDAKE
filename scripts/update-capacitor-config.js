const fs = require('fs');
const path = require('path');

/**
 * 从环境变量加载配置并更新 capacitor.config.json
 */
function updateCapacitorConfig() {
  const configPath = path.join(__dirname, '..', 'configs', 'capacitor.config.json');
  const envPath = path.join(__dirname, '..', 'configs', 'env', '.env');

  // 读取环境变量
  const envContent = fs.readFileSync(envPath, 'utf-8');
  const envVars = {};
  envContent.split('\n').forEach(line => {
    const [key, value] = line.split('=');
    if (key && value) {
      envVars[key.trim()] = value.trim();
    }
  });

  // 读取当前配置
  const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));

  // 更新 keystore 密码
  if (config.android && config.android.buildOptions) {
    config.android.buildOptions.keystorePassword = envVars.KEYSTORE_PASSWORD || '';
    config.android.buildOptions.keystoreAliasPassword = envVars.KEYSTORE_ALIAS_PASSWORD || '';
  }

  // 写回配置文件
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  console.log('✅ Capacitor 配置已更新，环境变量已加载');
}

// 如果直接运行此脚本，执行更新
if (require.main === module) {
  updateCapacitorConfig();
}

module.exports = { updateCapacitorConfig };
