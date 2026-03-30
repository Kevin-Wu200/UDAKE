export interface MemorySnapshot {
  timestamp: number;
  usedJSHeapSizeMB: number;
  totalJSHeapSizeMB: number;
  jsHeapSizeLimitMB: number;
  usagePercent: number;
}

export interface ResourceCounters {
  eventListeners: number;
  intervals: number;
  timeouts: number;
  trackedClosures: number;
}

export interface LeakDetectionReport {
  hasLeakRisk: boolean;
  averageHeapMB: number;
  maxHeapMB: number;
  growthPerHourMB: number;
  counters: ResourceCounters;
  issues: string[];
}

type GenericEventTarget = {
  addEventListener: (type: string, listener: EventListenerOrEventListenerObject, options?: boolean | AddEventListenerOptions) => void;
  removeEventListener: (type: string, listener: EventListenerOrEventListenerObject, options?: boolean | EventListenerOptions) => void;
};

function bytesToMB(value: number): number {
  return Number((value / (1024 * 1024)).toFixed(2));
}

function nowMs(): number {
  return Date.now();
}

export class MemoryMonitor {
  private snapshots: MemorySnapshot[] = [];
  private samplingTimer: number | null = null;
  private eventListenerCount = 0;
  private trackedIntervals = new Set<number>();
  private trackedTimeouts = new Set<number>();
  private trackedClosures = new Map<string, number>();

  public isSupported(): boolean {
    return typeof performance !== 'undefined' && 'memory' in performance;
  }

  public sampleMemory(): MemorySnapshot | null {
    if (!this.isSupported()) {
      return null;
    }

    const memory = (performance as any).memory;
    const used = Number(memory?.usedJSHeapSize || 0);
    const total = Number(memory?.totalJSHeapSize || 0);
    const limit = Number(memory?.jsHeapSizeLimit || 0);
    if (used <= 0 || total <= 0 || limit <= 0) {
      return null;
    }

    const snapshot: MemorySnapshot = {
      timestamp: nowMs(),
      usedJSHeapSizeMB: bytesToMB(used),
      totalJSHeapSizeMB: bytesToMB(total),
      jsHeapSizeLimitMB: bytesToMB(limit),
      usagePercent: Number(((used / limit) * 100).toFixed(2))
    };
    this.snapshots.push(snapshot);
    if (this.snapshots.length > 2000) {
      this.snapshots.splice(0, this.snapshots.length - 2000);
    }
    return snapshot;
  }

  public startSampling(intervalMs = 5000): void {
    this.stopSampling();
    const safeInterval = Math.max(1000, Math.floor(intervalMs));
    this.sampleMemory();
    this.samplingTimer = window.setInterval(() => {
      this.sampleMemory();
    }, safeInterval);
  }

  public stopSampling(): void {
    if (this.samplingTimer) {
      clearInterval(this.samplingTimer);
      this.samplingTimer = null;
    }
  }

  public getSnapshots(limit = 100): MemorySnapshot[] {
    const safeLimit = Math.max(1, Math.min(5000, Math.floor(limit)));
    return this.snapshots.slice(-safeLimit);
  }

  public clearSnapshots(): void {
    this.snapshots = [];
  }

  public trackEventListener(
    target: GenericEventTarget,
    type: string,
    listener: EventListenerOrEventListenerObject,
    options?: boolean | AddEventListenerOptions
  ): () => void {
    target.addEventListener(type, listener, options);
    this.eventListenerCount += 1;
    let disposed = false;
    return () => {
      if (disposed) {
        return;
      }
      disposed = true;
      target.removeEventListener(type, listener, options as boolean | EventListenerOptions | undefined);
      this.eventListenerCount = Math.max(0, this.eventListenerCount - 1);
    };
  }

  public trackInterval(callback: () => void, intervalMs: number): () => void {
    const id = window.setInterval(callback, intervalMs);
    this.trackedIntervals.add(id);
    return () => {
      clearInterval(id);
      this.trackedIntervals.delete(id);
    };
  }

  public trackTimeout(callback: () => void, timeoutMs: number): () => void {
    const id = window.setTimeout(() => {
      this.trackedTimeouts.delete(id);
      callback();
    }, timeoutMs);
    this.trackedTimeouts.add(id);
    return () => {
      clearTimeout(id);
      this.trackedTimeouts.delete(id);
    };
  }

  public trackClosure(name: string, estimatedRetainedKB = 0): () => void {
    const key = `${name}_${nowMs()}_${Math.random().toString(36).slice(2, 6)}`;
    this.trackedClosures.set(key, Math.max(0, Number(estimatedRetainedKB)));
    return () => {
      this.trackedClosures.delete(key);
    };
  }

  public getResourceCounters(): ResourceCounters {
    return {
      eventListeners: this.eventListenerCount,
      intervals: this.trackedIntervals.size,
      timeouts: this.trackedTimeouts.size,
      trackedClosures: this.trackedClosures.size
    };
  }

  public detectLeaks(): LeakDetectionReport {
    const snapshots = this.getSnapshots(240);
    const counters = this.getResourceCounters();
    const issues: string[] = [];

    if (snapshots.length < 2) {
      return {
        hasLeakRisk: false,
        averageHeapMB: 0,
        maxHeapMB: 0,
        growthPerHourMB: 0,
        counters,
        issues
      };
    }

    const first = snapshots[0];
    const last = snapshots[snapshots.length - 1];
    const elapsedHours = Math.max((last.timestamp - first.timestamp) / (1000 * 60 * 60), 1 / 60);
    const growth = Number((last.usedJSHeapSizeMB - first.usedJSHeapSizeMB).toFixed(2));
    const growthPerHourMB = Number((growth / elapsedHours).toFixed(2));
    const maxHeapMB = Math.max(...snapshots.map((item) => item.usedJSHeapSizeMB));
    const averageHeapMB = Number(
      (snapshots.reduce((sum, item) => sum + item.usedJSHeapSizeMB, 0) / snapshots.length).toFixed(2)
    );

    if (growthPerHourMB > 12) {
      issues.push(`堆内存增长速度过高: ${growthPerHourMB} MB/h`);
    }
    if (maxHeapMB > 200) {
      issues.push(`堆内存峰值超过目标阈值: ${maxHeapMB} MB`);
    }
    if (counters.eventListeners > 200) {
      issues.push(`事件监听器可能泄漏: ${counters.eventListeners}`);
    }
    if (counters.intervals > 30 || counters.timeouts > 200) {
      issues.push(`定时器数量异常: intervals=${counters.intervals}, timeouts=${counters.timeouts}`);
    }
    if (counters.trackedClosures > 100) {
      issues.push(`闭包保留对象数量过高: ${counters.trackedClosures}`);
    }

    return {
      hasLeakRisk: issues.length > 0,
      averageHeapMB,
      maxHeapMB,
      growthPerHourMB,
      counters,
      issues
    };
  }

  public project24HourMemory(): { projectedMB: number; withinTarget: boolean } {
    const report = this.detectLeaks();
    const latest = this.getSnapshots(1)[0];
    const latestHeap = latest?.usedJSHeapSizeMB || 0;
    const projectedMB = Number((latestHeap + report.growthPerHourMB * 24).toFixed(2));
    return {
      projectedMB,
      withinTarget: projectedMB < 200
    };
  }

  public dispose(): void {
    this.stopSampling();
    this.trackedIntervals.forEach((id) => clearInterval(id));
    this.trackedTimeouts.forEach((id) => clearTimeout(id));
    this.trackedIntervals.clear();
    this.trackedTimeouts.clear();
    this.trackedClosures.clear();
    this.eventListenerCount = 0;
    this.clearSnapshots();
  }
}

export const memoryMonitor = new MemoryMonitor();
