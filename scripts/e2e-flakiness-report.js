#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const resultFiles = [
  'test-results.json',
  'test-results-workflow.json',
  'test-results-auth.json'
].map((file) => path.resolve(process.cwd(), file));

function walkSuites(suite, collector) {
  if (Array.isArray(suite.specs)) {
    for (const spec of suite.specs) {
      for (const test of spec.tests || []) {
        collector.push({
          file: spec.file || suite.file || 'unknown',
          title: `${spec.title || ''}`.trim(),
          status: test.status || 'unknown',
          retries: Number(test.results?.length || 0) - 1
        });
      }
    }
  }

  for (const child of suite.suites || []) {
    walkSuites(child, collector);
  }
}

function loadResults(filePath) {
  if (!fs.existsSync(filePath)) {
    return [];
  }

  const raw = fs.readFileSync(filePath, 'utf8');
  if (!raw.trim()) {
    return [];
  }

  const json = JSON.parse(raw);
  const collector = [];
  for (const suite of json.suites || []) {
    walkSuites(suite, collector);
  }
  return collector;
}

const allTests = resultFiles.flatMap(loadResults);
if (allTests.length === 0) {
  console.log('[e2e-report] no result files found');
  process.exit(0);
}

const flaky = allTests.filter((item) => item.status === 'flaky' || item.retries > 0);
const failed = allTests.filter((item) => item.status === 'failed' || item.status === 'timedOut');

console.log(`[e2e-report] total tests: ${allTests.length}`);
console.log(`[e2e-report] flaky tests: ${flaky.length}`);
console.log(`[e2e-report] failed tests: ${failed.length}`);

if (flaky.length > 0) {
  console.log('[e2e-report] flaky detail:');
  for (const item of flaky) {
    console.log(`- ${item.file} :: ${item.title} (status=${item.status}, retries=${item.retries})`);
  }
}
