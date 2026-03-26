#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const ROOT = process.cwd();
const I18N_FILE = path.join(ROOT, 'apps/frontend/js/utils/I18n.ts');
const FRONTEND_ROOT = path.join(ROOT, 'apps/frontend');
const REPORT_DIR = path.join(ROOT, 'reports/i18n');
const STRICT = process.argv.includes('--strict');
const STRICT_REQUIRED_LOCALES = new Set(['en-US']);

const KEY_NAME_PATTERN = /^[a-z]+(?:\.[a-zA-Z0-9_-]+)+$/;
const TRANSLATION_ATTR_RE = /data-i18n(?:-(?:title|placeholder|aria-label|value))?=["']([^"']+)["']/g;
const I18N_CALL_RE = /I18n\.(?:t|tv|tp)\(\s*["'`]([^"'`]+)["'`]/g;
const I18N_DIALOG_CALL_RE = /I18nDialog\.(?:alert|confirm|prompt)\(\s*["'`]([^"'`]+)["'`]/g;
const CJK_RE = /[\u3400-\u9fff]/;

function readFileSafe(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch {
    return '';
  }
}

function walkFiles(dir, exts, list = []) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name === 'dist' || entry.name === 'node_modules' || entry.name.startsWith('.')) {
      continue;
    }
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkFiles(fullPath, exts, list);
      continue;
    }
    if (exts.has(path.extname(entry.name))) {
      list.push(fullPath);
    }
  }
  return list;
}

function extractBlockKeys(source, startToken, endToken) {
  const start = source.indexOf(startToken);
  const end = source.indexOf(endToken, start + startToken.length);
  if (start === -1 || end === -1 || end <= start) {
    return [];
  }
  const block = source.slice(start, end);
  const keys = new Set();
  const keyRe = /^\s*'([^']+)'\s*:\s*'/gm;
  let match;
  while ((match = keyRe.exec(block)) !== null) {
    keys.add(match[1]);
  }
  return [...keys];
}

function collectUsedKeys(files) {
  const used = new Set();

  for (const filePath of files) {
    const content = readFileSafe(filePath);
    let match;

    while ((match = I18N_CALL_RE.exec(content)) !== null) {
      const key = match[1];
      used.add(key);
      if (content.slice(Math.max(0, match.index - 20), match.index + 20).includes('I18n.tp')) {
        used.add(`${key}.zero`);
        used.add(`${key}.one`);
        used.add(`${key}.two`);
        used.add(`${key}.few`);
        used.add(`${key}.many`);
        used.add(`${key}.other`);
      }
    }

    while ((match = I18N_DIALOG_CALL_RE.exec(content)) !== null) {
      const key = match[1];
      if (KEY_NAME_PATTERN.test(key)) {
        used.add(key);
      }
    }

    while ((match = TRANSLATION_ATTR_RE.exec(content)) !== null) {
      used.add(match[1]);
    }
  }

  return used;
}

function collectHardcodedText(files) {
  const htmlHits = [];
  const jsHits = [];

  for (const filePath of files) {
    const ext = path.extname(filePath);
    const lines = readFileSafe(filePath).split('\n');

    lines.forEach((line, index) => {
      const lineNo = index + 1;

      if (ext === '.html') {
        if (line.includes('data-i18n')) {
          return;
        }

        const cjkNodeMatch = line.match(/>([^<>\n]*[\u3400-\u9fff][^<>\n]*)</);
        if (cjkNodeMatch && cjkNodeMatch[1].trim()) {
          htmlHits.push({ file: filePath, line: lineNo, text: cjkNodeMatch[1].trim() });
        }

        const enNodeMatch = line.match(/>([^<>\n]*[A-Za-z]{4,}(?:\s+[A-Za-z]{4,})+[^<>\n]*)</);
        if (enNodeMatch && enNodeMatch[1].trim()) {
          htmlHits.push({ file: filePath, line: lineNo, text: enNodeMatch[1].trim() });
        }

        return;
      }

      const uiLine = /(innerHTML|textContent|insertAdjacentHTML|alert\(|confirm\(|prompt\(|setAttribute\(\s*['"](?:title|placeholder|aria-label|value)['"])/.test(line);
      if (!uiLine || line.includes('I18n.t(') || line.includes('data-i18n')) {
        return;
      }

      const cjkString = line.match(/["'`][^"'`]*[\u3400-\u9fff][^"'`]*["'`]/);
      if (cjkString) {
        jsHits.push({ file: filePath, line: lineNo, text: cjkString[0] });
        return;
      }

      const enString = line.match(/["'`][A-Za-z][A-Za-z0-9\s,.:!?()\/-]{10,}["'`]/);
      if (enString) {
        jsHits.push({ file: filePath, line: lineNo, text: enString[0] });
      }
    });
  }

  return {
    html: htmlHits,
    js: jsHits
  };
}

function loadJsonLocale(localeCode) {
  const filePath = path.join(ROOT, 'apps/frontend/js/locales', `${localeCode}.json`);
  try {
    const parsed = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    return new Set(Object.keys(parsed));
  } catch {
    return new Set();
  }
}

function toMarkdown(report) {
  const lines = [];
  lines.push('# 前端国际化检查报告');
  lines.push('');
  lines.push(`- 生成时间: ${report.generatedAt}`);
  lines.push(`- 基准语言总键数: ${report.summary.baseKeyCount}`);
  lines.push(`- 检测到使用键数: ${report.summary.usedKeyCount}`);
  lines.push(`- 未使用键数: ${report.summary.unusedKeyCount}`);
  lines.push(`- 可疑硬编码数: ${report.summary.hardcodedCount}`);
  lines.push('');
  lines.push('## 语言覆盖率');
  lines.push('');
  for (const item of report.coverage) {
    lines.push(`- ${item.locale}: ${(item.coverage * 100).toFixed(2)}% (缺失 ${item.missingCount})`);
  }
  lines.push('');
  lines.push('## 命名规范问题');
  lines.push('');
  if (report.invalidNaming.length === 0) {
    lines.push('- 无');
  } else {
    for (const key of report.invalidNaming) {
      lines.push(`- ${key}`);
    }
  }
  lines.push('');
  lines.push('## 未使用翻译键（最多 50 条）');
  lines.push('');
  if (report.unusedKeys.length === 0) {
    lines.push('- 无');
  } else {
    for (const key of report.unusedKeys.slice(0, 50)) {
      lines.push(`- ${key}`);
    }
  }
  lines.push('');
  lines.push('## 可疑硬编码（最多 50 条）');
  lines.push('');
  const hardcoded = [...report.hardcoded.html, ...report.hardcoded.js].slice(0, 50);
  if (hardcoded.length === 0) {
    lines.push('- 无');
  } else {
    for (const item of hardcoded) {
      lines.push(`- ${path.relative(ROOT, item.file)}:${item.line} -> ${item.text}`);
    }
  }
  lines.push('');
  return lines.join('\n');
}

function main() {
  const source = readFileSafe(I18N_FILE);
  if (!source) {
    console.error('[i18n-check] 未找到 I18n.ts');
    process.exit(1);
  }

  const zhKeys = extractBlockKeys(source, 'const ZH_CN', 'const EN_US');
  const enKeys = extractBlockKeys(source, 'const EN_US', '// ========== 语言包注册表 ==========');
  const baseKeySet = new Set(zhKeys);

  const localeMap = {
    'zh-CN': new Set(zhKeys),
    'en-US': new Set(enKeys),
    'zh-TW': loadJsonLocale('zh-TW'),
    'ja-JP': loadJsonLocale('ja-JP'),
    'ko-KR': loadJsonLocale('ko-KR')
  };

  const appFiles = walkFiles(FRONTEND_ROOT, new Set(['.ts', '.js', '.html']));
  const usedKeys = collectUsedKeys(appFiles);
  const unusedKeys = [...baseKeySet].filter((key) => !usedKeys.has(key)).sort();

  const invalidNaming = [...baseKeySet].filter((key) => !KEY_NAME_PATTERN.test(key)).sort();

  const coverage = Object.entries(localeMap).map(([locale, keys]) => {
    if (locale === 'zh-CN') {
      return { locale, coverage: 1, missingCount: 0, missingKeys: [] };
    }
    const missingKeys = [...baseKeySet].filter((key) => !keys.has(key));
    return {
      locale,
      coverage: baseKeySet.size === 0 ? 1 : (baseKeySet.size - missingKeys.length) / baseKeySet.size,
      missingCount: missingKeys.length,
      missingKeys
    };
  });

  const hardcoded = collectHardcodedText(appFiles);

  const report = {
    generatedAt: new Date().toISOString(),
    summary: {
      baseKeyCount: baseKeySet.size,
      usedKeyCount: usedKeys.size,
      unusedKeyCount: unusedKeys.length,
      hardcodedCount: hardcoded.html.length + hardcoded.js.length
    },
    coverage,
    invalidNaming,
    unusedKeys,
    hardcoded
  };

  fs.mkdirSync(REPORT_DIR, { recursive: true });
  fs.writeFileSync(path.join(REPORT_DIR, 'i18n-report.json'), JSON.stringify(report, null, 2));
  fs.writeFileSync(path.join(REPORT_DIR, 'i18n-report.md'), toMarkdown(report));

  console.log('[i18n-check] 报告已生成: reports/i18n/i18n-report.json');
  console.log(`[i18n-check] 覆盖率: ${coverage.map((item) => `${item.locale} ${(item.coverage * 100).toFixed(1)}%`).join(', ')}`);
  console.log(`[i18n-check] 未使用键: ${unusedKeys.length}, 可疑硬编码: ${report.summary.hardcodedCount}`);

  const hasMissing = coverage.some(
    (item) => STRICT_REQUIRED_LOCALES.has(item.locale) && item.missingCount > 0
  );
  if (STRICT && (hasMissing || invalidNaming.length > 0)) {
    console.error('[i18n-check] strict 模式失败: 存在缺失键或命名问题');
    process.exit(1);
  }
}

main();
