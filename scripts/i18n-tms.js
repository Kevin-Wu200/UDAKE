#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const ROOT = process.cwd();
const I18N_FILE = path.join(ROOT, 'apps/frontend/js/utils/I18n.ts');
const LOCALES_DIR = path.join(ROOT, 'apps/frontend/js/locales');
const TMS_ROOT = path.join(ROOT, 'translation-management');
const TMS_SOURCE_DIR = path.join(TMS_ROOT, 'source');
const TMS_REPORT_DIR = path.join(TMS_ROOT, 'reports');

const CMD = process.argv[2];
const STRICT = process.argv.includes('--strict');

function readFileSafe(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch {
    return '';
  }
}

function extractLocaleBlock(source, startToken, endToken) {
  const start = source.indexOf(startToken);
  const end = source.indexOf(endToken, start + startToken.length);
  if (start === -1 || end === -1 || end <= start) {
    return '';
  }
  return source.slice(start, end);
}

function parseLocaleMapFromBlock(block) {
  const map = {};
  const lineRe = /^\s*'([^']+)'\s*:\s*'((?:\\'|[^'])*)',?\s*$/gm;
  let match;
  while ((match = lineRe.exec(block)) !== null) {
    map[match[1]] = match[2].replace(/\\'/g, "'");
  }
  return map;
}

function loadBaseLocales() {
  const source = readFileSafe(I18N_FILE);
  if (!source) {
    throw new Error('未找到 apps/frontend/js/utils/I18n.ts');
  }

  const zhBlock = extractLocaleBlock(source, 'const ZH_CN: LocaleMessages = {', 'const EN_US: LocaleMessages = {');
  const enBlock = extractLocaleBlock(source, 'const EN_US: LocaleMessages = {', '// ========== 语言包注册表 ==========');
  if (!zhBlock || !enBlock) {
    throw new Error('解析 I18n.ts 语言包失败');
  }

  return {
    'zh-CN': parseLocaleMapFromBlock(zhBlock),
    'en-US': parseLocaleMapFromBlock(enBlock)
  };
}

function loadJsonLocale(localeCode) {
  const filePath = path.join(LOCALES_DIR, `${localeCode}.json`);
  const raw = readFileSafe(filePath);
  if (!raw) {
    return {};
  }
  try {
    return JSON.parse(raw);
  } catch {
    throw new Error(`解析语言包失败: ${filePath}`);
  }
}

function sortObjectByKey(input) {
  const sorted = {};
  Object.keys(input)
    .sort()
    .forEach((key) => {
      sorted[key] = input[key];
    });
  return sorted;
}

function cmdExport() {
  const base = loadBaseLocales();
  fs.mkdirSync(TMS_SOURCE_DIR, { recursive: true });

  const zhPath = path.join(TMS_SOURCE_DIR, 'zh-CN.json');
  const enPath = path.join(TMS_SOURCE_DIR, 'en-US.json');
  fs.writeFileSync(zhPath, JSON.stringify(sortObjectByKey(base['zh-CN']), null, 2) + '\n');
  fs.writeFileSync(enPath, JSON.stringify(sortObjectByKey(base['en-US']), null, 2) + '\n');

  const manifest = {
    generatedAt: new Date().toISOString(),
    baseKeyCount: Object.keys(base['zh-CN']).length,
    files: {
      'zh-CN': path.relative(ROOT, zhPath),
      'en-US': path.relative(ROOT, enPath),
      'zh-TW': path.relative(ROOT, path.join(LOCALES_DIR, 'zh-TW.json')),
      'ja-JP': path.relative(ROOT, path.join(LOCALES_DIR, 'ja-JP.json')),
      'ko-KR': path.relative(ROOT, path.join(LOCALES_DIR, 'ko-KR.json'))
    }
  };
  fs.writeFileSync(path.join(TMS_SOURCE_DIR, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  console.log(`[i18n-tms] 导出完成，基准键数: ${manifest.baseKeyCount}`);
}

function cmdValidate() {
  const base = loadBaseLocales();
  const baseKeys = Object.keys(base['zh-CN']);
  const locales = {
    'en-US': base['en-US'],
    'zh-TW': loadJsonLocale('zh-TW'),
    'ja-JP': loadJsonLocale('ja-JP'),
    'ko-KR': loadJsonLocale('ko-KR')
  };

  const results = [];
  let hasMissing = false;
  for (const [locale, data] of Object.entries(locales)) {
    const keys = new Set(Object.keys(data));
    const missing = baseKeys.filter((key) => !keys.has(key));
    const extra = [...keys].filter((key) => !baseKeys.includes(key));
    if (missing.length > 0) {
      hasMissing = true;
    }
    results.push({
      locale,
      total: keys.size,
      missingCount: missing.length,
      extraCount: extra.length,
      missing,
      extra
    });
  }

  fs.mkdirSync(TMS_REPORT_DIR, { recursive: true });
  const reportPath = path.join(TMS_REPORT_DIR, 'validation.json');
  fs.writeFileSync(
    reportPath,
    JSON.stringify(
      {
        generatedAt: new Date().toISOString(),
        baseKeyCount: baseKeys.length,
        results
      },
      null,
      2
    ) + '\n'
  );

  console.log('[i18n-tms] 校验完成: translation-management/reports/validation.json');
  results.forEach((item) => {
    console.log(
      `[i18n-tms] ${item.locale}: missing=${item.missingCount}, extra=${item.extraCount}, total=${item.total}`
    );
  });

  if (STRICT && hasMissing) {
    console.error('[i18n-tms] strict 模式失败: 存在缺失翻译键');
    process.exit(1);
  }
}

function printUsage() {
  console.log('Usage: node scripts/i18n-tms.js <export|validate> [--strict]');
}

if (CMD === 'export') {
  cmdExport();
} else if (CMD === 'validate') {
  cmdValidate();
} else {
  printUsage();
  process.exit(1);
}
