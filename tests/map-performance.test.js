import { afterEach, describe, expect, it } from 'vitest';
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

describe('轨迹渲染性能优化', () => {
  const mapStub = {
    add: () => undefined,
    remove: () => undefined,
    getZoom: () => 12,
    getBounds: () => ({
      contains: ([lng, lat]) => lng >= 116.4 && lng <= 116.45 && lat >= 39.9 && lat <= 39.95
    })
  };

  let visualization;

  afterEach(() => {
    visualization?.dispose();
    visualization = null;
  });

  it('应在低缩放级别下应用 LOD 降低渲染点数', () => {
    visualization = new TrackVisualization(mapStub);
    const points = Array.from({ length: 10000 }, (_, index) => buildTrackPoint(index));
    const result = visualization['applyLOD'](points);

    expect(result.lodLevel).toBe('low');
    expect(result.points.length).toBeLessThan(points.length);
  });

  it('应只保留可视区域内轨迹点', () => {
    visualization = new TrackVisualization(mapStub);
    const points = [
      buildTrackPoint(0),
      { ...buildTrackPoint(1), location: { ...buildTrackPoint(1).location, longitude: 130 } },
      buildTrackPoint(2)
    ];
    const visible = visualization['getVisiblePoints'](points);
    expect(visible.length).toBe(2);
  });

  it('10万点轨迹应在2秒内完成抽样简化', () => {
    visualization = new TrackVisualization({
      ...mapStub,
      getZoom: () => 11
    });
    const points = Array.from({ length: 100000 }, (_, index) => buildTrackPoint(index));

    const startedAt = Date.now();
    const simplified = visualization['simplifyPath'](points);
    const elapsedMs = Date.now() - startedAt;

    expect(simplified.length).toBeLessThanOrEqual(4500);
    expect(elapsedMs).toBeLessThan(2000);
  });

  it('应提供 FPS 与渲染耗时监控指标', () => {
    visualization = new TrackVisualization(mapStub);
    visualization['lastRenderTick'] = performance.now() - 16;
    visualization['updateRenderPerformance'](14.2);

    const perf = visualization.getRenderPerformance();
    expect(perf.fps).toBeGreaterThan(0);
    expect(perf.lastRenderDurationMs).toBeCloseTo(14.2, 1);
  });
});
