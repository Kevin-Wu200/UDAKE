#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require('fs');
const path = require('path');

function parseArgs(argv) {
  const args = {
    reportDir: path.join(process.cwd(), 'reports', 'memory'),
    maxProjected24hMB: 200,
    minProjectionDurationSec: 600
  };
  for (const item of argv) {
    if (item.startsWith('--report-dir=')) {
      args.reportDir = item.split('=')[1] || args.reportDir;
    }
    if (item.startsWith('--max-projected-24h-mb=')) {
      args.maxProjected24hMB = Number(item.split('=')[1] || '200');
    }
    if (item.startsWith('--min-projection-duration-sec=')) {
      args.minProjectionDurationSec = Number(item.split('=')[1] || '600');
    }
  }
  return args;
}

function pickLatestReport(reportDir) {
  if (!fs.existsSync(reportDir)) {
    return null;
  }
  const files = fs.readdirSync(reportDir)
    .filter((name) => name.startsWith('memory-leak-report-') && name.endsWith('.json'))
    .map((name) => ({
      name,
      fullPath: path.join(reportDir, name),
      mtime: fs.statSync(path.join(reportDir, name)).mtimeMs
    }))
    .sort((a, b) => b.mtime - a.mtime);
  return files[0] || null;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const latest = pickLatestReport(args.reportDir);
  if (!latest) {
    console.error('[memory-trend-analysis] 未找到内存报告文件');
    process.exit(1);
  }

  const report = JSON.parse(fs.readFileSync(latest.fullPath, 'utf8'));
  const summary = report.summary || {};
  const durationSec = Number(report.durationSec || 0);
  const endHeapMB = Number(summary.endHeapMB || 0);
  const growthPerHourMB = Number(summary.growthPerHourMB || 0);
  const projected24hMB = Number((endHeapMB + growthPerHourMB * 24).toFixed(2));
  const withinTarget = durationSec < args.minProjectionDurationSec
    ? endHeapMB <= args.maxProjected24hMB
    : projected24hMB <= args.maxProjected24hMB;

  const trend = {
    generatedAt: new Date().toISOString(),
    sourceReport: latest.fullPath,
    durationSec,
    endHeapMB,
    growthPerHourMB,
    projected24hMB,
    maxProjected24hMB: args.maxProjected24hMB,
    withinTarget
  };

  const outPath = path.join(args.reportDir, `memory-trend-${Date.now()}.json`);
  fs.writeFileSync(outPath, JSON.stringify(trend, null, 2), 'utf8');

  console.log('[memory-trend-analysis] 完成');
  console.log(`source_report=${latest.fullPath}`);
  console.log(`projected_24h_mb=${projected24hMB}`);
  console.log(`within_target=${withinTarget}`);
  console.log(`trend_report=${outPath}`);

  if (!withinTarget) {
    process.exit(1);
  }
}

main();
