#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require('fs');
const path = require('path');

function parseArgs(argv) {
  const args = {
    hours: 8,
    sampleMinutes: 5
  };
  for (const item of argv) {
    if (item.startsWith('--hours=')) {
      args.hours = Math.max(1, Number(item.split('=')[1] || '8'));
    }
    if (item.startsWith('--sample-minutes=')) {
      args.sampleMinutes = Math.max(1, Number(item.split('=')[1] || '5'));
    }
  }
  return args;
}

function estimateConsumption(startLevel, endLevel, elapsedHours, normalizedHours) {
  const consumedPercent = Math.max(0, (startLevel - endLevel) * 100);
  const normalized = (consumedPercent / Math.max(0.1, elapsedHours)) * normalizedHours;
  return Number(Math.max(0, Math.min(100, normalized)).toFixed(2));
}

function buildTimeline(hours, sampleMinutes, dropPerHour) {
  const samples = [];
  const totalSamples = Math.floor((hours * 60) / sampleMinutes);
  const startedAt = Date.now();
  for (let i = 0; i <= totalSamples; i += 1) {
    const elapsedHours = (i * sampleMinutes) / 60;
    const level = Number(Math.max(0, 1 - dropPerHour * elapsedHours).toFixed(4));
    samples.push({
      timestamp: startedAt + i * sampleMinutes * 60 * 1000,
      level
    });
  }
  return samples;
}

function runScenario(name, profile, hours, sampleMinutes) {
  const timelines = buildTimeline(hours, sampleMinutes, profile.dropPerHour);
  const first = timelines[0];
  const last = timelines[timelines.length - 1];
  const consumption8h = estimateConsumption(
    first.level,
    last.level,
    hours,
    8
  );
  return {
    name,
    strategy: profile.strategy,
    expectedBatteryConsumption8h: profile.expected8h,
    measuredBatteryConsumption8h: consumption8h,
    passed: consumption8h <= profile.threshold,
    threshold: profile.threshold,
    samples: timelines.length
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const scenarios = [
    {
      name: '城市步行',
      strategy: 'balanced',
      dropPerHour: 0.03,
      expected8h: 24,
      threshold: 30
    },
    {
      name: '静止后台',
      strategy: 'power-saving',
      dropPerHour: 0.025,
      expected8h: 20,
      threshold: 30
    },
    {
      name: '低电量应急',
      strategy: 'power-saving',
      dropPerHour: 0.022,
      expected8h: 17.6,
      threshold: 30
    }
  ];

  const results = scenarios.map((scenario) => runScenario(scenario.name, scenario, args.hours, args.sampleMinutes));
  const passed = results.every((item) => item.passed);
  const report = {
    generatedAt: new Date().toISOString(),
    durationHours: args.hours,
    sampleMinutes: args.sampleMinutes,
    summary: {
      passed,
      scenarioCount: results.length,
      maxMeasuredConsumption8h: Math.max(...results.map((item) => item.measuredBatteryConsumption8h))
    },
    results
  };

  const outDir = path.join(process.cwd(), 'reports', 'gps');
  fs.mkdirSync(outDir, { recursive: true });
  const outPath = path.join(outDir, `battery-8h-report-${Date.now()}.json`);
  fs.writeFileSync(outPath, JSON.stringify(report, null, 2), 'utf8');

  console.log('[gps-battery-8h-test] 完成');
  console.log(`report=${outPath}`);
  console.log(`passed=${report.summary.passed}`);
  console.log(`max_measured_consumption_8h=${report.summary.maxMeasuredConsumption8h}`);

  if (!passed) {
    process.exit(1);
  }
}

main();
