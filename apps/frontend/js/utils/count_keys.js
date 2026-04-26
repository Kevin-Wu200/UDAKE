/* global require */
const fs = require('fs');
const content = fs.readFileSync('I18n.ts', 'utf8');

function countKeys(varName) {
    const regex = new RegExp(`const ${varName}: LocaleMessages = \\{([\\s\\S]*?)\\};`, 'm');
    const match = content.match(regex);
    if (!match) return 0;
    const objText = match[1];
    const lines = objText.split('\n');
    let count = 0;
    lines.forEach(line => {
        if (line.match(/^\s*['"](.+?)['"]\s*:\s*['"](.+?)['"]\s*,?/)) {
            count++;
        }
    });
    return count;
}

console.log('ZH_CN:', countKeys('ZH_CN'));
console.log('EN_US:', countKeys('EN_US'));
console.log('ZH_TW:', countKeys('ZH_TW'));
console.log('JA_JP:', countKeys('JA_JP'));
console.log('KO_KR:', countKeys('KO_KR'));
