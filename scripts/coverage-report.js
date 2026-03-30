#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const frontendSummary = path.join(ROOT, 'coverage', 'coverage-summary.json');
const report = [];

if (fs.existsSync(frontendSummary)) {
  const json = JSON.parse(fs.readFileSync(frontendSummary, 'utf8'));
  const total = json.total || {};
  const lines = Number(total.lines?.pct || 0);
  const branches = Number(total.branches?.pct || 0);
  const functions = Number(total.functions?.pct || 0);
  const statements = Number(total.statements?.pct || 0);
  const score = Number(((lines + branches + functions + statements) / 4).toFixed(2));
  report.push({ scope: 'frontend', lines, branches, functions, statements, score });
}

const backendXml = path.join(ROOT, 'coverage.xml');
if (fs.existsSync(backendXml)) {
  report.push({ scope: 'backend', note: 'coverage.xml 已生成，可由 CI 继续汇总' });
}

if (report.length === 0) {
  console.log('未检测到覆盖率报告文件。请先执行 npm run test:coverage 或 pytest --cov。');
  process.exit(0);
}

console.log('[coverage-report]');
for (const item of report) {
  if (item.scope === 'frontend') {
    console.log(
      `frontend score=${item.score}% lines=${item.lines}% branches=${item.branches}% functions=${item.functions}% statements=${item.statements}%`
    );
  } else {
    console.log(`backend ${item.note}`);
  }
}

const frontend = report.find(item => item.scope === 'frontend');
if (frontend && Number(frontend.score) < 80) {
  console.error(`frontend coverage score ${frontend.score}% is below target 80%`);
  process.exit(1);
}
