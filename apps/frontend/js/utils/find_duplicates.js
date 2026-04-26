/* global require */
const fs = require('fs');
const content = fs.readFileSync('I18n.ts', 'utf8');

function findDuplicates(varName) {
    const regex = new RegExp(`const ${varName}: LocaleMessages = \\{([\\s\\S]*?)\\};`, 'm');
    const match = content.match(regex);
    if (!match) return;
    const objText = match[1];
    const lines = objText.split('\n');
    const keys = [];
    lines.forEach(line => {
        const lineMatch = line.match(/^\s*['"](.+?)['"]\s*:\s*['"](.+?)['"]\s*,?/);
        if (lineMatch) {
            keys.push(lineMatch[1]);
        }
    });
    const seen = new Set();
    const dups = [];
    keys.forEach(k => {
        if (seen.has(k)) dups.push(k);
        else seen.add(k);
    });
    console.log(varName, dups);
}

findDuplicates('ZH_CN');
findDuplicates('EN_US');
findDuplicates('ZH_TW');
findDuplicates('JA_JP');
findDuplicates('KO_KR');
