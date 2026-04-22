#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const ROOT = process.cwd();
const I18N_FILE = path.join(ROOT, 'apps/frontend/js/utils/I18n.ts');
const FRONTEND_ROOT = path.join(ROOT, 'apps/frontend');
const TEST_ROOT = path.join(ROOT, 'tests');
const REPORT_DIR = path.join(ROOT, 'reports/i18n');
const BASELINE_FILE = path.join(ROOT, 'configs/i18n-baseline.json');
const STRICT = process.argv.includes('--strict');
const DEBUG = process.env.I18N_CHECK_DEBUG === '1' || process.argv.includes('--debug');
const STRICT_ALL_LOCALES = process.env.I18N_STRICT_ALL_LOCALES === '1';
const STRICT_REQUIRED_LOCALES = new Set(['en-US']);

const KEY_NAME_PATTERN = /^[a-z]+(?:\.[a-zA-Z0-9_-]+)+$/;
const TRANSLATION_ATTR_RE = /data-i18n(?:-(?:title|placeholder|aria-label|value))?=["']([^"']+)["']/g;
const I18N_CALL_RE = /I18n\.(?:t|tv|tp)\(\s*["'`]([^"'`]+)["'`]/g;
const I18N_DIALOG_CALL_RE = /I18nDialog\.(?:alert|confirm|prompt)\(\s*["'`]([^"'`]+)["'`]/g;
const CJK_RE = /[\u3400-\u9fff]/;
const STRING_LITERAL_RE = /["'`]([^"'`]+)["'`]/g;
const HTML_TAG_RE = /<[^>]*>/g;
const FILE_CACHE = new Map();
let readCount = 0;
let cacheHitCount = 0;

function logDebug(message) {
  if (DEBUG) {
    console.log(`[i18n-check][debug] ${message}`);
  }
}

function readFileSafe(filePath) {
  if (FILE_CACHE.has(filePath)) {
    cacheHitCount += 1;
    return FILE_CACHE.get(filePath);
  }
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    FILE_CACHE.set(filePath, content);
    readCount += 1;
    return content;
  } catch (error) {
    console.error(`[i18n-check] 读取文件失败: ${path.relative(ROOT, filePath)} (${error.message})`);
    FILE_CACHE.set(filePath, '');
    return '';
  }
}

function loadBaseline() {
  try {
    const parsed = JSON.parse(fs.readFileSync(BASELINE_FILE, 'utf8'));
    const reservedUnusedKeys = new Set(Array.isArray(parsed.reservedUnusedKeys) ? parsed.reservedUnusedKeys : []);
    const reviewedHardcoded = new Set(
      Array.isArray(parsed.reviewedHardcoded)
        ? parsed.reviewedHardcoded.map((item) => `${item.file}:${item.line}:${item.text}`)
        : []
    );
    return { reservedUnusedKeys, reviewedHardcoded };
  } catch {
    return { reservedUnusedKeys: new Set(), reviewedHardcoded: new Set() };
  }
}

function walkFiles(dir, exts, list = []) {
  if (!fs.existsSync(dir)) {
    logDebug(`目录不存在，跳过扫描: ${path.relative(ROOT, dir)}`);
    return list;
  }
  let entries = [];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch (error) {
    console.error(`[i18n-check] 读取目录失败: ${path.relative(ROOT, dir)} (${error.message})`);
    return list;
  }
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

function extractLocaleKeys(source, localeCode) {
    const token = `const ${localeCode.replace(/-/g, '_')}: LocaleMessages = {`;
    const start = source.indexOf(token);
    if (start === -1) return new Set();
    
    // Find the end of the block by looking for the next '};'
    const end = source.indexOf('};', start);
    if (end === -1) return new Set();
    
    const block = source.slice(start, end);
    const keys = new Set();
    const keyRe = /^\s*'([^']+)'\s*:/gm;
    let match;
    while ((match = keyRe.exec(block)) !== null) {
        keys.add(match[1]);
    }
    return keys;
}

function collectUsedKeys(files) {
  const used = new Set();

  for (const filePath of files) {
    const content = readFileSafe(filePath);
    I18N_CALL_RE.lastIndex = 0;
    I18N_DIALOG_CALL_RE.lastIndex = 0;
    TRANSLATION_ATTR_RE.lastIndex = 0;
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
    let insideScriptBlock = false;
    let insideStyleBlock = false;

    lines.forEach((line, index) => {
      const lineNo = index + 1;
      const trimmed = line.trim();
      if (!trimmed) {
        return;
      }

      if (ext === '.html') {
        if (trimmed.includes('<script')) {
          insideScriptBlock = true;
        }
        if (trimmed.includes('<style')) {
          insideStyleBlock = true;
        }

        if (insideScriptBlock || insideStyleBlock || trimmed.startsWith('<!--')) {
          if (trimmed.includes('</script>')) {
            insideScriptBlock = false;
          }
          if (trimmed.includes('</style>')) {
            insideStyleBlock = false;
          }
          return;
        }

        if (line.includes('data-i18n')) {
          if (trimmed.includes('</script>')) {
            insideScriptBlock = false;
          }
          if (trimmed.includes('</style>')) {
            insideStyleBlock = false;
          }
          return;
        }

        const visibleText = line.replace(HTML_TAG_RE, ' ').replace(/&nbsp;/g, ' ').trim();
        const cjkNodeMatch = line.match(/>([^<>\n]*[\u3400-\u9fff][^<>\n]*)</);
        if (cjkNodeMatch && cjkNodeMatch[1].trim() && visibleText) {
          htmlHits.push({ file: filePath, line: lineNo, text: cjkNodeMatch[1].trim() });
        }

        const enNodeMatch = line.match(/>([^<>\n]*[A-Za-z]{4,}(?:\s+[A-Za-z]{4,})+[^<>\n]*)</);
        if (enNodeMatch && enNodeMatch[1].trim() && visibleText) {
          htmlHits.push({ file: filePath, line: lineNo, text: enNodeMatch[1].trim() });
        }

        if (trimmed.includes('</script>')) {
          insideScriptBlock = false;
        }
        if (trimmed.includes('</style>')) {
          insideStyleBlock = false;
        }
        return;
      }

      if (
        trimmed.startsWith('//') ||
        trimmed.startsWith('/*') ||
        trimmed.startsWith('*') ||
        trimmed.startsWith('*/')
      ) {
        return;
      }

      const uiLine = /(innerHTML|textContent|insertAdjacentHTML|alert\(|confirm\(|prompt\(|setAttribute\(\s*['"](?:title|placeholder|aria-label|value)['"])/.test(line);
      if (
        !uiLine ||
        line.includes('I18n.t(') ||
        line.includes('I18n.tv(') ||
        line.includes('I18n.tp(') ||
        line.includes('data-i18n') ||
        line.includes('I18nDialog.')
      ) {
        return;
      }

      STRING_LITERAL_RE.lastIndex = 0;
      const literals = [];
      let literalMatch;
      while ((literalMatch = STRING_LITERAL_RE.exec(line)) !== null) {
        literals.push(literalMatch[1]);
      }
      for (const literal of literals) {
        if (!literal || KEY_NAME_PATTERN.test(literal)) {
          continue;
        }
        if (CJK_RE.test(literal)) {
          jsHits.push({ file: filePath, line: lineNo, text: `'${literal}'` });
          return;
        }

        if (/^[A-Za-z][A-Za-z0-9\s,.:!?()\/-]{10,}$/.test(literal)) {
          jsHits.push({ file: filePath, line: lineNo, text: `'${literal}'` });
          return;
        }
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
    const content = readFileSafe(filePath);
    if (!content) {
      return new Set();
    }
    const parsed = JSON.parse(content);
    return new Set(Object.keys(parsed));
  } catch (error) {
    console.error(`[i18n-check] 读取语言包失败: ${path.relative(ROOT, filePath)} (${error.message})`);
    return new Set();
  }
}

function ensureRequiredFiles(filePaths) {
  const missing = filePaths.filter((filePath) => !fs.existsSync(filePath));
  if (missing.length > 0) {
    for (const filePath of missing) {
      console.error(`[i18n-check] 必要文件缺失: ${path.relative(ROOT, filePath)}`);
    }
    return false;
  }
  if (DEBUG) {
    for (const filePath of filePaths) {
      const stat = fs.statSync(filePath);
      logDebug(`文件检查通过: ${path.relative(ROOT, filePath)} (${stat.size} bytes)`);
    }
  }
  return true;
}

function toMarkdown(report) {
  const lines = [];
  lines.push('# 前端国际化检查报告');
  lines.push('');
  lines.push(`- 生成时间: ${report.generatedAt}`);
  lines.push(`- 基准语言总键数: ${report.summary.baseKeyCount}`);
  lines.push(`- 检测到使用键数: ${report.summary.usedKeyCount}`);
  lines.push(`- 未使用键数: ${report.summary.unusedKeyCount}`);
  lines.push(`- 基线保留键数: ${report.summary.baselineUnusedKeyCount}`);
  lines.push(`- 可疑硬编码数: ${report.summary.hardcodedCount}`);
  lines.push(`- 基线忽略硬编码数: ${report.summary.baselineHardcodedCount}`);
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
  logDebug(`运行环境: node=${process.version}, platform=${process.platform}, cwd=${ROOT}`);
  if (!ensureRequiredFiles([I18N_FILE])) {
    process.exit(1);
  }

  const source = readFileSafe(I18N_FILE);
  if (!source.trim()) {
    console.error('[i18n-check] I18n.ts 内容为空或读取失败');
    process.exit(1);
  }

  const baseline = loadBaseline();
  const localeMap = {
    'zh-CN': extractLocaleKeys(source, 'ZH_CN'),
    'en-US': extractLocaleKeys(source, 'EN_US'),
    'zh-TW': extractLocaleKeys(source, 'ZH_TW'),
    'ja-JP': extractLocaleKeys(source, 'JA_JP'),
    'ko-KR': extractLocaleKeys(source, 'KO_KR')
  };

  const appFiles = walkFiles(FRONTEND_ROOT, new Set(['.ts', '.js', '.html']));
  const testFiles = fs.existsSync(TEST_ROOT) ? walkFiles(TEST_ROOT, new Set(['.ts', '.js', '.html'])) : [];
  const scanFiles = [...appFiles, ...testFiles];
  logDebug(`扫描文件数: app=${appFiles.length}, test=${testFiles.length}, total=${scanFiles.length}`);
  const usedKeys = collectUsedKeys(scanFiles);
  const baseKeySet = localeMap['zh-CN'];
  const rawUnusedKeys = [...baseKeySet].filter((key) => !usedKeys.has(key)).sort();
  const unusedKeys = rawUnusedKeys.filter((key) => !baseline.reservedUnusedKeys.has(key));

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

  const hardcodedRaw = collectHardcodedText(appFiles);
  const hardcoded = {
    html: hardcodedRaw.html.filter(
      (item) => !baseline.reviewedHardcoded.has(`${path.relative(ROOT, item.file)}:${item.line}:${item.text}`)
    ),
    js: hardcodedRaw.js.filter(
      (item) => !baseline.reviewedHardcoded.has(`${path.relative(ROOT, item.file)}:${item.line}:${item.text}`)
    )
  };

  const report = {
    generatedAt: new Date().toISOString(),
    summary: {
      baseKeyCount: baseKeySet.size,
      usedKeyCount: usedKeys.size,
      unusedKeyCount: unusedKeys.length,
      baselineUnusedKeyCount: rawUnusedKeys.length - unusedKeys.length,
      hardcodedCount: hardcoded.html.length + hardcoded.js.length
      ,
      baselineHardcodedCount:
        hardcodedRaw.html.length + hardcodedRaw.js.length - (hardcoded.html.length + hardcoded.js.length)
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
  logDebug(`文件读取统计: read=${readCount}, cacheHit=${cacheHitCount}`);

  const hasMissing = coverage.some((item) => {
    if (STRICT_ALL_LOCALES) {
      return item.locale !== 'zh-CN' && item.missingCount > 0;
    }
    return STRICT_REQUIRED_LOCALES.has(item.locale) && item.missingCount > 0;
  });
  if (STRICT && (hasMissing || invalidNaming.length > 0)) {
    const mode = STRICT_ALL_LOCALES ? 'all-locales' : 'required-locales';
    console.error(`[i18n-check] strict 模式失败(${mode}): 存在缺失键或命名问题`);
    process.exit(1);
  }
}

main();
