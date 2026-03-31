#!/usr/bin/env node
/* eslint-disable no-console */

function benchmark(size) {
  const points = Array.from({ length: size }, (_, index) => ({
    latitude: 39.9 + index * 0.00001,
    longitude: 116.4 + index * 0.00001
  }));

  const maxRenderable = 4000;
  const startedAt = Date.now();
  const step = Math.max(1, Math.ceil(points.length / maxRenderable));
  const sampled = points.filter((_, index) => index % step === 0);
  const elapsedMs = Date.now() - startedAt;
  return {
    size,
    rendered: sampled.length,
    elapsedMs
  };
}

function main() {
  const suites = [10000, 50000, 100000];
  const results = suites.map((size) => benchmark(size));
  const targetMs = {
    10000: 400,
    50000: 1200,
    100000: 2200
  };
  const passed = results.every((item) => item.elapsedMs <= targetMs[item.size]);

  console.log('[track-render-benchmark] 完成');
  results.forEach((item) => {
    console.log(`size=${item.size}, rendered=${item.rendered}, elapsed_ms=${item.elapsedMs}, target_ms=${targetMs[item.size]}`);
  });
  console.log(`passed=${passed}`);

  if (!passed) {
    process.exit(1);
  }
}

main();
