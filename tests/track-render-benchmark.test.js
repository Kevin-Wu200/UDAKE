import { describe, expect, it } from 'vitest';
import { TrackVisualization } from '../apps/frontend/js/components/TrackVisualization';

function buildTrackPoint(index) {
  return {
    index,
    timestamp: Date.now() + index,
    location: {
      latitude: 39.9 + index * 0.00001,
      longitude: 116.4 + index * 0.00001,
      accuracy: 5,
      altitude: null,
      altitudeAccuracy: null,
      heading: null,
      speed: 1.2,
      timestamp: Date.now() + index
    }
  };
}

describe('轨迹渲染基准测试套件', () => {
  it('应满足 1万/5万/10万 点抽样耗时阈值', () => {
    const visualization = new TrackVisualization({
      add: () => undefined,
      remove: () => undefined,
      getZoom: () => 11,
      getBounds: () => null
    });

    const suites = [
      { size: 10000, maxMs: 400 },
      { size: 50000, maxMs: 1200 },
      { size: 100000, maxMs: 2200 }
    ];

    for (const suite of suites) {
      const points = Array.from({ length: suite.size }, (_, idx) => buildTrackPoint(idx));
      const startedAt = Date.now();
      const simplified = visualization['simplifyPath'](points);
      const elapsed = Date.now() - startedAt;

      expect(simplified.length).toBeLessThanOrEqual(4500);
      expect(elapsed).toBeLessThan(suite.maxMs);
    }

    visualization.dispose();
  });
});
