#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require('fs');
const path = require('path');

const DEFAULT_SCAN_ROOTS = [
  'deep_learning',
  'realtime_interpolation',
  'multi_objective_optimization',
  'adaptive_sampling',
  'services',
  'apps',
  'tests',
  'configs',
  'deployment'
];

const CATEGORY_RULES = [
  {
    name: 'core',
    roots: ['deep_learning', 'realtime_interpolation', 'multi_objective_optimization', 'adaptive_sampling']
  },
  {
    name: 'api',
    roots: ['services']
  },
  {
    name: 'frontend',
    roots: ['apps/frontend', 'apps/admin-frontend']
  },
  {
    name: 'tests',
    roots: ['tests']
  },
  {
    name: 'config',
    roots: ['configs', 'deployment']
  }
];

const CODE_EXTENSIONS = new Set([
  '.js',
  '.jsx',
  '.ts',
  '.tsx',
  '.py',
  '.sh',
  '.json',
  '.yml',
  '.yaml',
  '.toml',
  '.ini',
  '.cfg'
]);

const RISK_RULES = [
  {
    id: 'todo_fixme',
    level: 'medium',
    regex: /\b(?:TODO|FIXME|XXX|HACK)\b/g,
    reason: '遗留待办或临时实现标记'
  },
  {
    id: 'dangerous_eval',
    level: 'high',
    regex: /\beval\s*\(/g,
    reason: '可能导致代码注入风险'
  },
  {
    id: 'new_function',
    level: 'high',
    regex: /\bnew\s+Function\s*\(/g,
    reason: '动态代码执行存在安全风险'
  },
  {
    id: 'debug_console',
    level: 'low',
    regex: /\bconsole\.(?:log|debug)\s*\(/g,
    reason: '调试日志可能影响可观测性与信息暴露控制'
  },
  {
    id: 'hardcoded_secret_like',
    level: 'critical',
    regex: /(?:api[_-]?key|token|secret|password)\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}['\"]/gi,
    reason: '疑似硬编码敏感信息'
  }
];

function normalizePath(filePath) {
  return filePath.split(path.sep).join('/');
}

function shouldSkipDir(dirName) {
  return dirName === 'node_modules' || dirName === '.git' || dirName.startsWith('.');
}

function walkFiles(rootDir, out = []) {
  if (!fs.existsSync(rootDir)) {
    return out;
  }
  const entries = fs.readdirSync(rootDir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(rootDir, entry.name);
    if (entry.isDirectory()) {
      if (!shouldSkipDir(entry.name)) {
        walkFiles(fullPath, out);
      }
      continue;
    }

    if (CODE_EXTENSIONS.has(path.extname(entry.name))) {
      out.push(fullPath);
    }
  }
  return out;
}

function detectCategory(normalizedRelativePath) {
  for (const rule of CATEGORY_RULES) {
    if (rule.roots.some((root) => normalizedRelativePath.startsWith(`${root}/`) || normalizedRelativePath === root)) {
      return rule.name;
    }
  }
  return 'other';
}

function collectFindings(content, relativePath, maxPerRule = 5) {
  const findings = [];

  for (const rule of RISK_RULES) {
    const matches = content.match(rule.regex) || [];
    const sample = matches.slice(0, maxPerRule);

    if (matches.length > 0) {
      findings.push({
        id: rule.id,
        level: rule.level,
        reason: rule.reason,
        count: matches.length,
        sample,
        file: relativePath
      });
    }
  }

  return findings;
}

function buildReport({ projectRoot, scanRoots = DEFAULT_SCAN_ROOTS, generatedAt = new Date().toISOString() }) {
  const absoluteRoot = path.resolve(projectRoot);
  const files = [];

  for (const scanRoot of scanRoots) {
    const rootPath = path.join(absoluteRoot, scanRoot);
    walkFiles(rootPath, files);
  }

  const uniqueFiles = Array.from(new Set(files.map((filePath) => path.resolve(filePath))));
  const summaryByCategory = {
    core: { files: 0, findings: 0 },
    api: { files: 0, findings: 0 },
    frontend: { files: 0, findings: 0 },
    tests: { files: 0, findings: 0 },
    config: { files: 0, findings: 0 },
    other: { files: 0, findings: 0 }
  };
  const severityTotals = { critical: 0, high: 0, medium: 0, low: 0 };
  const allFindings = [];

  for (const filePath of uniqueFiles) {
    const relativePath = normalizePath(path.relative(absoluteRoot, filePath));
    const category = detectCategory(relativePath);
    const content = fs.readFileSync(filePath, 'utf8');

    summaryByCategory[category].files += 1;

    const findings = collectFindings(content, relativePath);
    for (const finding of findings) {
      summaryByCategory[category].findings += finding.count;
      severityTotals[finding.level] += finding.count;
      allFindings.push(finding);
    }
  }

  return {
    meta: {
      generatedAt,
      projectRoot: absoluteRoot,
      scanRoots
    },
    summary: {
      scannedFiles: uniqueFiles.length,
      categories: summaryByCategory,
      severity: severityTotals
    },
    findings: allFindings.sort((a, b) => {
      const levelWeight = { critical: 4, high: 3, medium: 2, low: 1 };
      return levelWeight[b.level] - levelWeight[a.level] || b.count - a.count;
    })
  };
}

function writeReport(report, outputPath) {
  const absoluteOutputPath = path.resolve(outputPath);
  const parentDir = path.dirname(absoluteOutputPath);
  fs.mkdirSync(parentDir, { recursive: true });
  fs.writeFileSync(absoluteOutputPath, JSON.stringify(report, null, 2));
  return absoluteOutputPath;
}

function printSummary(report, outputPath) {
  console.log('[qa-phase1-audit] 完成');
  console.log(`output=${outputPath}`);
  console.log(`scanned_files=${report.summary.scannedFiles}`);
  console.log(`severity_critical=${report.summary.severity.critical}`);
  console.log(`severity_high=${report.summary.severity.high}`);
  console.log(`severity_medium=${report.summary.severity.medium}`);
  console.log(`severity_low=${report.summary.severity.low}`);
}

function runCli(argv = process.argv.slice(2)) {
  const rootArg = argv.find((arg) => arg.startsWith('--root='));
  const outputArg = argv.find((arg) => arg.startsWith('--output='));
  const strictMode = argv.includes('--strict');

  const projectRoot = rootArg ? rootArg.replace('--root=', '') : path.resolve(__dirname, '..');
  const outputPath = outputArg
    ? outputArg.replace('--output=', '')
    : path.join(projectRoot, 'reports', 'qa_phase1_audit.json');

  const report = buildReport({ projectRoot });
  const absoluteOutputPath = writeReport(report, outputPath);
  printSummary(report, absoluteOutputPath);

  if (strictMode && (report.summary.severity.critical > 0 || report.summary.severity.high > 0)) {
    console.error('[qa-phase1-audit] strict 模式失败: 检测到 critical/high 级问题');
    process.exit(1);
  }

  return report;
}

if (require.main === module) {
  runCli();
}

module.exports = {
  RISK_RULES,
  buildReport,
  collectFindings,
  detectCategory,
  runCli,
  walkFiles,
  writeReport
};
