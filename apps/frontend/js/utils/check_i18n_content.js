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
const EN_US = extractObject('EN_US');
const ZH_TW = extractObject('ZH_TW');
const JA_JP = extractObject('JA_JP');
const KO_KR = extractObject('KO_KR');

const languages = {
    'EN_US': EN_US,
    'ZH_TW': ZH_TW,
    'JA_JP': JA_JP,
    'KO_KR': KO_KR
};

const baseKeys = Object.keys(ZH_CN);

function hasChinese(str) {
    return /[\u4e00-\u9fa5]/.test(str);
}

const report = {};

for (const [langName, langObj] of Object.entries(languages)) {
    const missing = baseKeys.filter(key => !Object.prototype.hasOwnProperty.call(langObj, key));
    const suspect = [];
    if (langName === 'EN_US' || langName === 'JA_JP' || langName === 'KO_KR') {
        for (const [key, value] of Object.entries(langObj)) {
            if (hasChinese(value)) {
                suspect.push(key);
            }
        }
    }
    report[langName] = { missing, suspect };
}

console.log(JSON.stringify(report, null, 2));
