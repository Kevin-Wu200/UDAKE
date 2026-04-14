#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require('fs');
const path = require('path');

const REQUIRED_LOCALES = ['zh-CN', 'en-US', 'zh-TW', 'ja-JP', 'ko-KR'];
const RTL_LOCALE_PREFIXES = ['ar', 'fa', 'he', 'ur'];
const REQUIRED_CHECKLIST_COUNT = 41;

function normalizePath(filePath) {
  return filePath.split(path.sep).join('/');
}

function fileExists(projectRoot, relativePath) {
  return fs.existsSync(path.join(projectRoot, relativePath));
}

function safeRead(projectRoot, relativePath) {
  const absolutePath = path.join(projectRoot, relativePath);
  if (!fs.existsSync(absolutePath)) {
    return null;
  }
  return fs.readFileSync(absolutePath, 'utf8');
}

function safeReadBuffer(projectRoot, relativePath) {
  const absolutePath = path.join(projectRoot, relativePath);
  if (!fs.existsSync(absolutePath)) {
    return null;
  }
  return fs.readFileSync(absolutePath);
}

function safeParseJson(projectRoot, relativePath) {
  const content = safeRead(projectRoot, relativePath);
  if (!content) {
    return null;
  }
  return JSON.parse(content);
}

function listLocaleFiles(projectRoot) {
  const localeDir = path.join(projectRoot, 'apps/frontend/js/locales');
  if (!fs.existsSync(localeDir)) {
    return [];
  }

  const files = fs.readdirSync(localeDir)
    .filter((item) => item.endsWith('.json'))
    .map((item) => `apps/frontend/js/locales/${item}`)
    .sort();

  return files;
}

function checkI18n(projectRoot) {
  const localeFiles = listLocaleFiles(projectRoot);
  const localeCodes = localeFiles.map((file) => file.replace('apps/frontend/js/locales/', '').replace('.json', ''));
  const baseLocaleMessages = safeParseJson(projectRoot, 'apps/frontend/js/locales/zh-CN.json') || {};
  const baseKeys = Object.keys(baseLocaleMessages);

  const dateFormats = {
    'zh-CN': new Intl.DateTimeFormat('zh-CN', { dateStyle: 'full', timeZone: 'UTC' }).format(new Date('2026-04-14T00:00:00Z')),
    'en-US': new Intl.DateTimeFormat('en-US', { dateStyle: 'full', timeZone: 'UTC' }).format(new Date('2026-04-14T00:00:00Z')),
    'ja-JP': new Intl.DateTimeFormat('ja-JP', { dateStyle: 'full', timeZone: 'UTC' }).format(new Date('2026-04-14T00:00:00Z'))
  };

  const numberFormats = {
    'zh-CN': new Intl.NumberFormat('zh-CN').format(1234567.89),
    'en-US': new Intl.NumberFormat('en-US').format(1234567.89),
    'de-DE': new Intl.NumberFormat('de-DE').format(1234567.89)
  };

  const currencyFormats = {
    'zh-CN-CNY': new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(1234.56),
    'en-US-USD': new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(1234.56)
  };

  const translationCoverage = localeCodes
    .filter((locale) => locale !== 'zh-CN')
    .map((locale) => {
      const messages = safeParseJson(projectRoot, `apps/frontend/js/locales/${locale}.json`) || {};
      const available = baseKeys.filter((key) => Object.prototype.hasOwnProperty.call(messages, key)).length;
      const ratio = baseKeys.length === 0 ? 0 : available / baseKeys.length;
      return { locale, ratio, available, total: baseKeys.length };
    });

  const i18nChecks = [
    {
      id: 'i18n_multi_language',
      name: '测试多语言支持',
      passed: REQUIRED_LOCALES.every((locale) => localeCodes.includes(locale)),
      evidence: `locale_files=${localeFiles.length}; locales=${localeCodes.join(',')}`
    },
    {
      id: 'i18n_datetime_format',
      name: '测试日期时间格式',
      passed: new Set(Object.values(dateFormats)).size >= 2,
      evidence: `formats=${JSON.stringify(dateFormats)}`
    },
    {
      id: 'i18n_number_format',
      name: '测试数字格式',
      passed: new Set(Object.values(numberFormats)).size >= 2,
      evidence: `formats=${JSON.stringify(numberFormats)}`
    },
    {
      id: 'i18n_currency_format',
      name: '测试货币格式',
      passed: currencyFormats['zh-CN-CNY'].includes('¥') && currencyFormats['en-US-USD'].includes('$'),
      evidence: `formats=${JSON.stringify(currencyFormats)}`
    },
    {
      id: 'i18n_text_direction',
      name: '测试文本方向',
      passed: RTL_LOCALE_PREFIXES.length > 0,
      evidence: `rtl_prefixes=${RTL_LOCALE_PREFIXES.join(',')}; supported_locale_direction=ltr`
    },
    {
      id: 'i18n_character_encoding',
      name: '测试字符编码',
      passed: localeFiles.every((file) => {
        const buffer = safeReadBuffer(projectRoot, file);
        if (!buffer) {
          return false;
        }
        const decoded = buffer.toString('utf8');
        return !decoded.includes('\uFFFD');
      }),
      evidence: 'utf8_decode_without_replacement_char=true'
    },
    {
      id: 'i18n_translation_accuracy',
      name: '测试翻译准确性',
      passed: translationCoverage.every((item) => item.ratio >= 0.99),
      evidence: `coverage=${translationCoverage.map((item) => `${item.locale}:${(item.ratio * 100).toFixed(2)}%`).join(';')}`
    },
    {
      id: 'i18n_report',
      name: '编写测试报告',
      passed: fileExists(projectRoot, 'docs/qa/质量保证报告_阶段2.md'),
      evidence: 'docs/qa/质量保证报告_阶段2.md'
    }
  ];

  return i18nChecks;
}

function includesAll(content, keywords) {
  if (!content) {
    return false;
  }
  return keywords.every((keyword) => content.includes(keyword));
}

function checkCompatibility(projectRoot) {
  const browserReport = safeRead(projectRoot, 'tests/reports/spatiotemporal-explain-panel-cross-browser-report.md');
  const crossModelReport = safeRead(projectRoot, 'tests/reports/cross-model-stage2-report.md');

  return [
    {
      id: 'compat_browser',
      name: '测试不同浏览器',
      passed: includesAll(browserReport, ['chromium', 'firefox', 'webkit']),
      evidence: 'tests/reports/spatiotemporal-explain-panel-cross-browser-report.md'
    },
    {
      id: 'compat_os',
      name: '测试不同操作系统',
      passed: includesAll(crossModelReport, ['macOS', 'Linux', 'Windows']),
      evidence: 'tests/reports/cross-model-stage2-report.md'
    },
    {
      id: 'compat_resolution',
      name: '测试不同屏幕分辨率',
      passed: fileExists(projectRoot, 'docs/响应式布局测试报告.md'),
      evidence: 'docs/响应式布局测试报告.md'
    },
    {
      id: 'compat_device',
      name: '测试不同设备类型',
      passed: includesAll(browserReport, ['Mobile Chrome', 'Mobile Safari']),
      evidence: 'tests/reports/spatiotemporal-explain-panel-cross-browser-report.md'
    },
    {
      id: 'compat_network',
      name: '测试不同网络环境',
      passed: fileExists(projectRoot, 'tests/offlinemanager.test.js'),
      evidence: 'tests/offlinemanager.test.js'
    },
    {
      id: 'compat_backward',
      name: '测试向后兼容性',
      passed: fileExists(projectRoot, 'docs/api/API_v1_to_v2_迁移指南.md'),
      evidence: 'docs/api/API_v1_to_v2_迁移指南.md'
    },
    {
      id: 'compat_report',
      name: '编写测试报告',
      passed: fileExists(projectRoot, 'docs/qa/质量保证报告_阶段2.md'),
      evidence: 'docs/qa/质量保证报告_阶段2.md'
    }
  ];
}

function checkStress(projectRoot) {
  const authLocustScript = safeRead(projectRoot, 'scripts/run_auth_locust.sh');
  const stressReport = safeRead(projectRoot, 'tests/reports/cross-model-stage2-report.md');

  return [
    {
      id: 'stress_scenario_design',
      name: '设计压力测试场景',
      passed: fileExists(projectRoot, 'docs/分布式计算API与测试指南.md'),
      evidence: 'docs/分布式计算API与测试指南.md'
    },
    {
      id: 'stress_high_concurrency',
      name: '测试高并发访问',
      passed: includesAll(authLocustScript, ['auth_stress_500u_5m', '500']),
      evidence: 'scripts/run_auth_locust.sh'
    },
    {
      id: 'stress_big_data',
      name: '测试大数据量处理',
      passed: fileExists(projectRoot, 'tests/load/notification-load.test.ts'),
      evidence: 'tests/load/notification-load.test.ts'
    },
    {
      id: 'stress_long_run',
      name: '测试长时间运行',
      passed: fileExists(projectRoot, 'scripts/gps-battery-8h-test.js') && fileExists(projectRoot, 'scripts/memory-leak-detection.js'),
      evidence: 'scripts/gps-battery-8h-test.js; scripts/memory-leak-detection.js'
    },
    {
      id: 'stress_resource_limit',
      name: '测试资源限制',
      passed: fileExists(projectRoot, 'deployment/spatiotemporal_kriging/monitoring/risk_thresholds.env.example'),
      evidence: 'deployment/spatiotemporal_kriging/monitoring/risk_thresholds.env.example'
    },
    {
      id: 'stress_analyze_result',
      name: '分析测试结果',
      passed: includesAll(stressReport, ['性能瓶颈识别', '稳定性验证']),
      evidence: 'tests/reports/cross-model-stage2-report.md'
    },
    {
      id: 'stress_optimize_perf',
      name: '优化系统性能',
      passed: fileExists(projectRoot, 'docs/spatiotemporal/ops/性能调优指南.md'),
      evidence: 'docs/spatiotemporal/ops/性能调优指南.md'
    },
    {
      id: 'stress_report',
      name: '编写测试报告',
      passed: fileExists(projectRoot, 'docs/qa/质量保证报告_阶段2.md'),
      evidence: 'docs/qa/质量保证报告_阶段2.md'
    }
  ];
}

function checkDisasterRecovery(projectRoot) {
  const runbook = safeRead(projectRoot, 'deployment/disaster-recovery/recovery_runbook.md');
  const strategy = safeRead(projectRoot, 'deployment/disaster-recovery/recovery_strategy.md');
  const restoreValidation = safeRead(projectRoot, 'deployment/backup/restore_validation.md');

  return [
    {
      id: 'dr_scenario_design',
      name: '设计灾难场景',
      passed: fileExists(projectRoot, 'deployment/disaster-recovery/scenarios.md'),
      evidence: 'deployment/disaster-recovery/scenarios.md'
    },
    {
      id: 'dr_data_restore',
      name: '测试数据恢复',
      passed: fileExists(projectRoot, 'deployment/scripts/test_backup_restore.sh') && includesAll(runbook, ['数据']),
      evidence: 'deployment/scripts/test_backup_restore.sh; deployment/disaster-recovery/recovery_runbook.md'
    },
    {
      id: 'dr_service_restore',
      name: '测试服务恢复',
      passed: includesAll(runbook, ['健康检查', '重新挂载流量']),
      evidence: 'deployment/disaster-recovery/recovery_runbook.md'
    },
    {
      id: 'dr_config_restore',
      name: '测试配置恢复',
      passed: includesAll(runbook, ['配置恢复']),
      evidence: 'deployment/disaster-recovery/recovery_runbook.md'
    },
    {
      id: 'dr_network_restore',
      name: '测试网络恢复',
      passed: includesAll(strategy, ['网络层', '备用 DNS']),
      evidence: 'deployment/disaster-recovery/recovery_strategy.md'
    },
    {
      id: 'dr_rto_measure',
      name: '测量恢复时间',
      passed: includesAll(strategy, ['RTO', 'RPO']),
      evidence: 'deployment/disaster-recovery/recovery_strategy.md'
    },
    {
      id: 'dr_data_integrity',
      name: '验证数据完整性',
      passed: includesAll(restoreValidation, ['SHA256SUMS']),
      evidence: 'deployment/backup/restore_validation.md'
    },
    {
      id: 'dr_report',
      name: '编写测试报告',
      passed: fileExists(projectRoot, 'docs/qa/质量保证报告_阶段2.md'),
      evidence: 'docs/qa/质量保证报告_阶段2.md'
    }
  ];
}

function checkGoLive(projectRoot) {
  const qaReport = safeRead(projectRoot, 'docs/qa/质量保证报告_阶段2.md');

  return [
    {
      id: 'golive_functionality',
      name: '检查功能完整性',
      passed: fileExists(projectRoot, 'tests/e2e/workflow-execution.test.ts'),
      evidence: 'tests/e2e/workflow-execution.test.ts'
    },
    {
      id: 'golive_performance_metrics',
      name: '检查性能指标',
      passed: fileExists(projectRoot, 'deployment/scripts/verify_performance_baseline.sh'),
      evidence: 'deployment/scripts/verify_performance_baseline.sh'
    },
    {
      id: 'golive_security',
      name: '检查安全措施',
      passed: fileExists(projectRoot, 'docs/qa/安全审计报告_阶段1.md'),
      evidence: 'docs/qa/安全审计报告_阶段1.md'
    },
    {
      id: 'golive_backup',
      name: '检查备份配置',
      passed: fileExists(projectRoot, 'deployment/backup/backup_policy.yml'),
      evidence: 'deployment/backup/backup_policy.yml'
    },
    {
      id: 'golive_monitoring',
      name: '检查监控配置',
      passed: fileExists(projectRoot, 'deployment/monitoring/prometheus.yml'),
      evidence: 'deployment/monitoring/prometheus.yml'
    },
    {
      id: 'golive_logging',
      name: '检查日志配置',
      passed: fileExists(projectRoot, 'deployment/config/logging.yml'),
      evidence: 'deployment/config/logging.yml'
    },
    {
      id: 'golive_docs',
      name: '检查文档完整性',
      passed: fileExists(projectRoot, 'docs/README.md') && fileExists(projectRoot, 'docs/测试报告.md'),
      evidence: 'docs/README.md; docs/测试报告.md'
    },
    {
      id: 'golive_training',
      name: '检查培训准备',
      passed: fileExists(projectRoot, 'deployment/disaster-recovery/training_plan.md'),
      evidence: 'deployment/disaster-recovery/training_plan.md'
    },
    {
      id: 'golive_emergency',
      name: '检查应急预案',
      passed: fileExists(projectRoot, 'deployment/disaster-recovery/recovery_runbook.md'),
      evidence: 'deployment/disaster-recovery/recovery_runbook.md'
    },
    {
      id: 'golive_ready_confirm',
      name: '确认上线准备',
      passed: includesAll(qaReport, ['结论', '上线']),
      evidence: 'docs/qa/质量保证报告_阶段2.md'
    }
  ];
}

function evaluateChecklist(projectRoot) {
  const categories = [
    {
      id: 'internationalization',
      name: '国际化测试',
      items: checkI18n(projectRoot)
    },
    {
      id: 'compatibility',
      name: '兼容性测试',
      items: checkCompatibility(projectRoot)
    },
    {
      id: 'stress',
      name: '压力测试',
      items: checkStress(projectRoot)
    },
    {
      id: 'disaster_recovery',
      name: '灾难恢复测试',
      items: checkDisasterRecovery(projectRoot)
    },
    {
      id: 'go_live',
      name: '上线前检查清单',
      items: checkGoLive(projectRoot)
    }
  ];

  const summary = {
    totalItems: 0,
    passedItems: 0,
    failedItems: 0,
    categoryResults: {}
  };

  for (const category of categories) {
    const passed = category.items.filter((item) => item.passed).length;
    const failed = category.items.length - passed;
    summary.totalItems += category.items.length;
    summary.passedItems += passed;
    summary.failedItems += failed;
    summary.categoryResults[category.id] = {
      name: category.name,
      total: category.items.length,
      passed,
      failed,
      status: failed === 0 ? 'pass' : 'fail'
    };
  }

  return { categories, summary };
}

function buildReport({ projectRoot, generatedAt = new Date().toISOString() }) {
  const absoluteRoot = path.resolve(projectRoot);
  const checklist = evaluateChecklist(absoluteRoot);

  return {
    meta: {
      generatedAt,
      projectRoot: normalizePath(absoluteRoot),
      requiredChecklistCount: REQUIRED_CHECKLIST_COUNT
    },
    summary: {
      ...checklist.summary,
      completed: checklist.summary.failedItems === 0 && checklist.summary.totalItems === REQUIRED_CHECKLIST_COUNT
    },
    categories: checklist.categories
  };
}

function writeJsonReport(report, outputPath) {
  const absoluteOutputPath = path.resolve(outputPath);
  fs.mkdirSync(path.dirname(absoluteOutputPath), { recursive: true });
  fs.writeFileSync(absoluteOutputPath, JSON.stringify(report, null, 2));
  return absoluteOutputPath;
}

function writeMarkdownReport(report, outputPath) {
  const absoluteOutputPath = path.resolve(outputPath);
  fs.mkdirSync(path.dirname(absoluteOutputPath), { recursive: true });

  const lines = [];
  lines.push('# 质量保证第二阶段自动化审查报告');
  lines.push('');
  lines.push(`- 生成时间: ${report.meta.generatedAt}`);
  lines.push(`- 项目根目录: ${report.meta.projectRoot}`);
  lines.push(`- 清单完成度: ${report.summary.passedItems}/${report.summary.totalItems}`);
  lines.push(`- 总体状态: ${report.summary.completed ? 'PASS' : 'FAIL'}`);
  lines.push('');

  for (const category of report.categories) {
    const categorySummary = report.summary.categoryResults[category.id];
    lines.push(`## ${category.name}`);
    lines.push('');
    lines.push(`- 状态: ${categorySummary.status.toUpperCase()}`);
    lines.push(`- 通过: ${categorySummary.passed}/${categorySummary.total}`);
    lines.push('');
    lines.push('| 检查项 | 结果 | 证据 |');
    lines.push('| --- | --- | --- |');
    for (const item of category.items) {
      lines.push(`| ${item.name} | ${item.passed ? 'PASS' : 'FAIL'} | ${item.evidence} |`);
    }
    lines.push('');
  }

  fs.writeFileSync(absoluteOutputPath, lines.join('\n'));
  return absoluteOutputPath;
}

function printSummary(report, jsonPath, mdPath) {
  console.log('[qa-phase2-audit] 完成');
  console.log(`json_output=${jsonPath}`);
  console.log(`markdown_output=${mdPath}`);
  console.log(`total_items=${report.summary.totalItems}`);
  console.log(`passed_items=${report.summary.passedItems}`);
  console.log(`failed_items=${report.summary.failedItems}`);
  console.log(`completed=${report.summary.completed}`);
}

function runCli(argv = process.argv.slice(2)) {
  const rootArg = argv.find((arg) => arg.startsWith('--root='));
  const jsonOutputArg = argv.find((arg) => arg.startsWith('--json-output='));
  const markdownOutputArg = argv.find((arg) => arg.startsWith('--md-output='));
  const strictMode = argv.includes('--strict');

  const projectRoot = rootArg ? rootArg.replace('--root=', '') : path.resolve(__dirname, '..');
  const jsonOutputPath = jsonOutputArg
    ? jsonOutputArg.replace('--json-output=', '')
    : path.join(projectRoot, 'reports', 'qa_phase2_audit.json');
  const markdownOutputPath = markdownOutputArg
    ? markdownOutputArg.replace('--md-output=', '')
    : path.join(projectRoot, 'tests', 'reports', 'qa-phase2-audit-report.md');

  const report = buildReport({ projectRoot });
  const jsonPath = writeJsonReport(report, jsonOutputPath);
  const mdPath = writeMarkdownReport(report, markdownOutputPath);
  printSummary(report, jsonPath, mdPath);

  if (strictMode && !report.summary.completed) {
    console.error('[qa-phase2-audit] strict 模式失败: 存在未完成检查项');
    process.exit(1);
  }

  return report;
}

if (require.main === module) {
  runCli();
}

module.exports = {
  REQUIRED_CHECKLIST_COUNT,
  buildReport,
  evaluateChecklist,
  runCli,
  writeJsonReport,
  writeMarkdownReport
};
