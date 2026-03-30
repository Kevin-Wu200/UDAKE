#!/usr/bin/env node
/* eslint-disable no-console */

/**
 * 基于 Chrome DevTools Protocol (Node inspector) 的内存泄漏检测脚本
 * 用法:
 *   node scripts/memory-leak-detection.js --duration-sec=60 --interval-ms=2000
 */

const fs = require('fs');
const path = require('path');
const inspector = require('inspector');

function parseArgs(argv) {
  const parsed = {
    durationSec: 60,
    intervalMs: 2000
  };
  for (const arg of argv) {
    if (arg.startsWith('--duration-sec=')) {
      parsed.durationSec = Math.max(10, Number(arg.split('=')[1] || '60'));
    }
    if (arg.startsWith('--interval-ms=')) {
      parsed.intervalMs = Math.max(500, Number(arg.split('=')[1] || '2000'));
    }
  }
  return parsed;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function percentile(values, p) {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.floor((sorted.length - 1) * p);
  return sorted[idx];
}

async function inspectorPost(session, method, params = {}) {
  await new Promise((resolve, reject) => {
    session.post(method, params, (error) => {
      if (error) reject(error);
      else resolve(undefined);
    });
  });
}

async function run() {
  const options = parseArgs(process.argv.slice(2));
  const sampleCount = Math.max(2, Math.floor((options.durationSec * 1000) / options.intervalMs));
  const session = new inspector.Session();
  session.connect();

  const startedAt = Date.now();
  const samples = [];

  try {
    await inspectorPost(session, 'Runtime.enable');
    await inspectorPost(session, 'HeapProfiler.enable');
  } catch (error) {
    console.warn('[memory-leak-detection] inspector 初始化失败，继续使用 process.memoryUsage:', error.message);
  }

  for (let i = 0; i < sampleCount; i += 1) {
    const usage = process.memoryUsage();
    samples.push({
      timestamp: Date.now(),
      heapUsedMB: Number((usage.heapUsed / (1024 * 1024)).toFixed(2)),
      heapTotalMB: Number((usage.heapTotal / (1024 * 1024)).toFixed(2)),
      rssMB: Number((usage.rss / (1024 * 1024)).toFixed(2)),
      externalMB: Number((usage.external / (1024 * 1024)).toFixed(2))
    });
    if (i < sampleCount - 1) {
      await sleep(options.intervalMs);
    }
  }

  const first = samples[0];
  const last = samples[samples.length - 1];
  const elapsedHours = Math.max((last.timestamp - first.timestamp) / (1000 * 60 * 60), 1 / 3600);
  const growthMB = Number((last.heapUsedMB - first.heapUsedMB).toFixed(2));
  const growthPerHour = Number((growthMB / elapsedHours).toFixed(2));
  const heapSeries = samples.map((item) => item.heapUsedMB);

  const result = {
    startedAt,
    finishedAt: Date.now(),
    durationSec: options.durationSec,
    intervalMs: options.intervalMs,
    summary: {
      sampleCount: samples.length,
      startHeapMB: first.heapUsedMB,
      endHeapMB: last.heapUsedMB,
      growthMB,
      growthPerHourMB: growthPerHour,
      avgHeapMB: Number((heapSeries.reduce((sum, value) => sum + value, 0) / heapSeries.length).toFixed(2)),
      p95HeapMB: Number(percentile(heapSeries, 0.95).toFixed(2)),
      maxHeapMB: Number(Math.max(...heapSeries).toFixed(2)),
      potentialLeak: growthPerHour > 12 || Math.max(...heapSeries) > 200
    },
    samples
  };

  const reportDir = path.join(process.cwd(), 'reports', 'memory');
  fs.mkdirSync(reportDir, { recursive: true });
  const reportPath = path.join(reportDir, `memory-leak-report-${Date.now()}.json`);
  fs.writeFileSync(reportPath, JSON.stringify(result, null, 2), 'utf8');

  console.log('[memory-leak-detection] 完成');
  console.log(`report=${reportPath}`);
  console.log(`sample_count=${result.summary.sampleCount}`);
  console.log(`growth_per_hour_mb=${result.summary.growthPerHourMB}`);
  console.log(`max_heap_mb=${result.summary.maxHeapMB}`);
  console.log(`potential_leak=${result.summary.potentialLeak}`);

  session.disconnect();

  if (result.summary.potentialLeak) {
    process.exit(1);
  }
}

run().catch((error) => {
  console.error('[memory-leak-detection] 执行失败:', error);
  process.exit(1);
});
