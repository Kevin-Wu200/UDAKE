#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.resolve(__dirname, '..');
const DEFAULT_OUT_DIR = path.join(ROOT_DIR, 'dist', 'domain-replaced');
const DEFAULT_TARGETS = [
  'configs/workflow-wizards.json',
  'docs/系统文档.md',
  'docs/构建部署指南.md'
];

const ENV_FILE_BY_MODE = {
  development: path.join(ROOT_DIR, 'configs', 'env', '.env'),
  production: path.join(ROOT_DIR, 'configs', 'env', '.env.production'),
  testing: path.join(ROOT_DIR, 'configs', 'env', '.env.testing')
};

const REPLACERS = [
  {
    name: 'workflow-docs',
    pattern: /https:\/\/docs\.udake\.local\/workflow\/([^\s"')\]]+)/g,
    replacement: '${OFFICIAL_WEB}/docs/workflow/$1'
  },
  {
    name: 'workflow-videos',
    pattern: /https:\/\/video\.udake\.local\/tutorials\/([^\s"')\]]+)/g,
    replacement: '${OFFICIAL_WEB}/videos/tutorials/$1'
  },
  {
    name: 'community-link',
    pattern: /https:\/\/community\.udake\.io(?=[\/)\s'"\]]|$)/g,
    replacement: '${OFFICIAL_WEB}/community'
  },
  {
    name: 'update-service',
    pattern: /https:\/\/update\.udake\.com\/releases(?=[\/)\s'"\]]|$)/g,
    replacement: '${OFFICIAL_WEB}/updates/releases'
  }
];

function parseArgs(argv) {
  const options = {
    mode: 'production',
    outDir: DEFAULT_OUT_DIR,
    envFile: '',
    targets: [...DEFAULT_TARGETS]
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--mode') {
      options.mode = argv[i + 1] || options.mode;
      i += 1;
      continue;
    }
    if (arg.startsWith('--mode=')) {
      options.mode = arg.split('=')[1] || options.mode;
      continue;
    }
    if (arg === '--out-dir') {
      options.outDir = resolvePath(argv[i + 1] || options.outDir);
      i += 1;
      continue;
    }
    if (arg.startsWith('--out-dir=')) {
      options.outDir = resolvePath(arg.split('=')[1] || options.outDir);
      continue;
    }
    if (arg === '--env-file') {
      options.envFile = resolvePath(argv[i + 1] || '');
      i += 1;
      continue;
    }
    if (arg.startsWith('--env-file=')) {
      options.envFile = resolvePath(arg.split('=')[1] || '');
      continue;
    }
    if (arg === '--targets') {
      const value = argv[i + 1] || '';
      options.targets = parseTargets(value);
      i += 1;
      continue;
    }
    if (arg.startsWith('--targets=')) {
      options.targets = parseTargets(arg.split('=')[1] || '');
    }
  }

  return options;
}

function parseTargets(value) {
  const items = value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
  if (items.length === 0) {
    return [...DEFAULT_TARGETS];
  }
  return items;
}

function resolvePath(targetPath) {
  if (!targetPath) return '';
  return path.isAbsolute(targetPath) ? targetPath : path.join(ROOT_DIR, targetPath);
}

function loadEnvFile(envFilePath) {
  if (!fs.existsSync(envFilePath)) {
    throw new Error(`环境变量文件不存在: ${envFilePath}`);
  }

  const content = fs.readFileSync(envFilePath, 'utf8');
  const env = {};

  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;

    const index = line.indexOf('=');
    if (index <= 0) continue;

    const key = line.slice(0, index).trim();
    const value = line.slice(index + 1).trim();
    env[key] = stripQuotes(value);
  }

  return env;
}

function stripQuotes(value) {
  if (!value) return value;
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

function resolveEnvFile(mode, envFileOverride) {
  if (envFileOverride) {
    return envFileOverride;
  }
  if (!ENV_FILE_BY_MODE[mode]) {
    throw new Error(`不支持的 mode: ${mode}，仅支持 development/production/testing`);
  }
  return ENV_FILE_BY_MODE[mode];
}

function applyReplacers(content) {
  let next = content;
  const countByRule = {};

  for (const rule of REPLACERS) {
    let matched = 0;
    next = next.replace(rule.pattern, (...args) => {
      matched += 1;
      const groups = args.slice(1, -2);
      return buildReplacement(rule.replacement, groups);
    });
    countByRule[rule.name] = matched;
  }

  const total = Object.values(countByRule).reduce((sum, value) => sum + Number(value || 0), 0);
  return {
    content: next,
    countByRule,
    total
  };
}

function buildReplacement(template, groups) {
  return template.replace(/\$(\d+)/g, (_, indexText) => {
    const index = Number(indexText) - 1;
    return groups[index] || '';
  });
}

function ensureRequiredEnv(env) {
  if (!env.OFFICIAL_WEB || !env.ADMIN_WEB) {
    throw new Error('环境变量缺失：OFFICIAL_WEB 与 ADMIN_WEB 必须同时存在');
  }
}

function processSingleTarget(target, outDir) {
  const absoluteTarget = resolvePath(target);
  if (!fs.existsSync(absoluteTarget)) {
    return {
      target,
      skipped: true,
      reason: '文件不存在'
    };
  }

  const source = fs.readFileSync(absoluteTarget, 'utf8');
  const transformed = applyReplacers(source);

  const outFile = path.join(outDir, target);
  fs.mkdirSync(path.dirname(outFile), { recursive: true });
  fs.writeFileSync(outFile, transformed.content, 'utf8');

  return {
    target,
    skipped: false,
    outFile,
    total: transformed.total,
    countByRule: transformed.countByRule,
    changed: source !== transformed.content
  };
}

function run(options) {
  const envFilePath = resolveEnvFile(options.mode, options.envFile);
  const env = loadEnvFile(envFilePath);
  ensureRequiredEnv(env);

  const outDir = resolvePath(options.outDir);
  const results = options.targets.map((target) => processSingleTarget(target, outDir));

  return {
    envFilePath,
    outDir,
    env: {
      OFFICIAL_WEB: env.OFFICIAL_WEB,
      ADMIN_WEB: env.ADMIN_WEB
    },
    results
  };
}

function printReport(report) {
  console.log('[replace-domains]');
  console.log(`envFile=${path.relative(ROOT_DIR, report.envFilePath)}`);
  console.log(`OFFICIAL_WEB=${report.env.OFFICIAL_WEB}`);
  console.log(`ADMIN_WEB=${report.env.ADMIN_WEB}`);
  console.log(`outDir=${path.relative(ROOT_DIR, report.outDir)}`);

  for (const item of report.results) {
    if (item.skipped) {
      console.warn(`- ${item.target}: skipped (${item.reason})`);
      continue;
    }

    console.log(
      `- ${item.target}: replaced=${item.total}, changed=${item.changed}, output=${path.relative(ROOT_DIR, item.outFile)}`
    );
  }
}

function main() {
  try {
    const options = parseArgs(process.argv.slice(2));
    const report = run(options);
    printReport(report);
  } catch (error) {
    console.error(`[replace-domains] 失败: ${error.message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  DEFAULT_TARGETS,
  REPLACERS,
  parseArgs,
  loadEnvFile,
  resolveEnvFile,
  applyReplacers,
  run,
  stripQuotes
};
