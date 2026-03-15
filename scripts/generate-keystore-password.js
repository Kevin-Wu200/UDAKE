const crypto = require('crypto');

/**
 * 生成安全的 keystore 密码
 * 生成符合 Android keystore 要求的强密码（至少6个字符）
 */
function generateKeystorePassword() {
  // 生成32字节的随机密码，确保足够复杂
  const password = crypto.randomBytes(32).toString('hex');
  console.log('Generated Keystore Password:');
  console.log(password);
  console.log('\n请将此密码添加到 .env 文件中的 KEYSTORE_PASSWORD 和 KEYSTORE_ALIAS_PASSWORD');
  return password;
}

// 如果直接运行此脚本，生成并输出密码
if (require.main === module) {
  generateKeystorePassword();
}

module.exports = { generateKeystorePassword };