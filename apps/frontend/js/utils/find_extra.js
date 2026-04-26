/* global require */
const fs = require('fs');
const content = fs.readFileSync('I18n.ts', 'utf8');

function extractObject(varName) {
    const regex = new RegExp(`const ${varName}: LocaleMessages = \\{([\\s\\S]*?)\\};`, 'm');
    const match = content.match(regex);
    if (!match) return {};
    const objText = match[1];
    const lines = objText.split('\n');
    const obj = {};
    lines.forEach(line => {
        const lineMatch = line.match(/^\s*['"](.+?)['"]\s*:\s*['"](.+?)['"]\s*,?/);
        if (lineMatch) {
            obj[lineMatch[1]] = lineMatch[2];
        }
    });
    return obj;
}

const ZH_CN = extractObject('ZH_CN');
const JA_JP = extractObject('JA_JP');

const zhKeys = Object.keys(ZH_CN);
const jaKeys = Object.keys(JA_JP);

console.log('Extra in JA_JP:', jaKeys.filter(k => !zhKeys.includes(k)));
console.log('Missing in JA_JP:', zhKeys.filter(k => !jaKeys.includes(k)));
