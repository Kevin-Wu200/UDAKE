import { beforeEach, describe, expect, it } from 'vitest';
import { MemoryMonitor } from '../apps/frontend/js/utils/MemoryMonitor';

function mockPerformanceMemory(usedMB: number, totalMB = 256, limitMB = 512): void {
  Object.defineProperty(performance, 'memory', {
    configurable: true,
    value: {
      usedJSHeapSize: usedMB * 1024 * 1024,
      totalJSHeapSize: totalMB * 1024 * 1024,
      jsHeapSizeLimit: limitMB * 1024 * 1024
    }
  });
}

describe('MemoryMonitor', () => {
  let monitor: MemoryMonitor;

  beforeEach(() => {
    monitor = new MemoryMonitor();
    monitor.dispose();
    mockPerformanceMemory(80);
  });

  it('应采集 performance.memory 快照', () => {
    const snapshot = monitor.sampleMemory();
    expect(snapshot).not.toBeNull();
    expect(snapshot?.usedJSHeapSizeMB).toBeCloseTo(80, 1);
    expect(snapshot?.usagePercent).toBeGreaterThan(0);
  });

  it('应追踪事件监听器与定时器资源', () => {
    const removeListener = monitor.trackEventListener(window, 'click', () => undefined);
    const clearIntervalFn = monitor.trackInterval(() => undefined, 1000);
    const clearTimeoutFn = monitor.trackTimeout(() => undefined, 1000);
    const releaseClosure = monitor.trackClosure('test-handler', 12);

    let counters = monitor.getResourceCounters();
    expect(counters.eventListeners).toBe(1);
    expect(counters.intervals).toBe(1);
    expect(counters.timeouts).toBe(1);
    expect(counters.trackedClosures).toBe(1);

    removeListener();
    clearIntervalFn();
    clearTimeoutFn();
    releaseClosure();
    counters = monitor.getResourceCounters();
    expect(counters.eventListeners).toBe(0);
    expect(counters.intervals).toBe(0);
    expect(counters.timeouts).toBe(0);
    expect(counters.trackedClosures).toBe(0);
  });

  it('应识别堆内存持续增长的泄漏风险', async () => {
    mockPerformanceMemory(90);
    monitor.sampleMemory();
    await new Promise((resolve) => setTimeout(resolve, 5));
    mockPerformanceMemory(130);
    monitor.sampleMemory();
    await new Promise((resolve) => setTimeout(resolve, 5));
    mockPerformanceMemory(170);
    monitor.sampleMemory();

    const report = monitor.detectLeaks();
    expect(report.hasLeakRisk).toBe(true);
    expect(report.growthPerHourMB).toBeGreaterThan(12);
  });

  it('应提供24小时内存占用投影', async () => {
    mockPerformanceMemory(100);
    monitor.sampleMemory();
    await new Promise((resolve) => setTimeout(resolve, 5));
    mockPerformanceMemory(102);
    monitor.sampleMemory();

    const projection = monitor.project24HourMemory();
    expect(typeof projection.projectedMB).toBe('number');
    expect(projection.projectedMB).toBeGreaterThan(0);
  });
});
