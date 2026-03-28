/// <reference lib="webworker" />

import type {
    WorkerIncomingMessage,
    WorkerOutgoingMessage
} from './ComputeWorkerTypes.js';

interface NumericPoint {
    x: number;
    y: number;
    value?: number;
    uncertainty?: number;
    timestamp?: string;
    [key: string]: unknown;
}

interface Bounds {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
}

interface RoutePoint {
    id?: string;
    latitude: number;
    longitude: number;
    priority?: number;
    [key: string]: unknown;
}

const canceledTaskIds = new Set<string>();

function postProgress(id: string, progress: number, message?: string): void {
    const payload: WorkerOutgoingMessage = {
        id,
        kind: 'progress',
        progress: Math.max(0, Math.min(100, progress)),
        message
    };
    self.postMessage(payload);
}

function postResult(id: string, result: unknown): void {
    const payload: WorkerOutgoingMessage = {
        id,
        kind: 'result',
        result
    };
    self.postMessage(payload);
}

function postError(id: string, error: unknown): void {
    const payload: WorkerOutgoingMessage = {
        id,
        kind: 'error',
        error: error instanceof Error ? error.message : String(error)
    };
    self.postMessage(payload);
}

function ensureNotCanceled(taskId: string): void {
    if (canceledTaskIds.has(taskId)) {
        throw new Error('任务已取消');
    }
}

function toFiniteNumber(value: unknown): number | null {
    const parsed = typeof value === 'number' ? value : Number(value);
    return Number.isFinite(parsed) ? parsed : null;
}

function computeBounds(points: NumericPoint[]): Bounds {
    let minX = Number.POSITIVE_INFINITY;
    let maxX = Number.NEGATIVE_INFINITY;
    let minY = Number.POSITIVE_INFINITY;
    let maxY = Number.NEGATIVE_INFINITY;

    for (const point of points) {
        minX = Math.min(minX, point.x);
        maxX = Math.max(maxX, point.x);
        minY = Math.min(minY, point.y);
        maxY = Math.max(maxY, point.y);
    }

    return { minX, maxX, minY, maxY };
}

function preprocessData(taskId: string, payload: any): {
    points: NumericPoint[];
    removedCount: number;
    pointCount: number;
    bounds: Bounds;
    statistics: {
        minValue: number;
        maxValue: number;
        meanValue: number;
    };
} {
    const points = Array.isArray(payload?.points) ? payload.points : [];
    const dedupe = payload?.dedupe !== false;
    const normalize = payload?.normalize === true;
    const cleaned: NumericPoint[] = [];
    const seen = new Set<string>();
    let removedCount = 0;

    postProgress(taskId, 5, '开始清洗采样点');

    points.forEach((rawPoint: any, index: number) => {
        if (index % 200 === 0) {
            ensureNotCanceled(taskId);
            const progress = Math.min(45, 5 + (index / Math.max(1, points.length)) * 40);
            postProgress(taskId, progress, '校验采样点坐标与数值');
        }

        const x = toFiniteNumber(rawPoint?.x);
        const y = toFiniteNumber(rawPoint?.y);
        const value = toFiniteNumber(rawPoint?.value);

        if (x === null || y === null || value === null) {
            removedCount += 1;
            return;
        }

        const dedupeKey = `${x.toFixed(6)}:${y.toFixed(6)}`;
        if (dedupe && seen.has(dedupeKey)) {
            removedCount += 1;
            return;
        }
        seen.add(dedupeKey);

        cleaned.push({
            ...rawPoint,
            x,
            y,
            value
        });
    });

    ensureNotCanceled(taskId);

    if (cleaned.length === 0) {
        throw new Error('预处理后没有可用采样点');
    }

    const values = cleaned
        .map((item) => toFiniteNumber(item.value))
        .filter((value): value is number => value !== null);

    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const meanValue = values.reduce((sum, value) => sum + value, 0) / values.length;

    if (normalize && maxValue > minValue) {
        for (const point of cleaned) {
            ensureNotCanceled(taskId);
            const value = toFiniteNumber(point.value) || 0;
            point.normalizedValue = (value - minValue) / (maxValue - minValue);
        }
    }

    const bounds = computeBounds(cleaned);
    postProgress(taskId, 100, '预处理完成');

    return {
        points: cleaned,
        removedCount,
        pointCount: cleaned.length,
        bounds,
        statistics: {
            minValue,
            maxValue,
            meanValue
        }
    };
}

function distance(a: RoutePoint | NumericPoint, b: RoutePoint | NumericPoint): number {
    const ax = toFiniteNumber('longitude' in a ? a.longitude : a.x) ?? 0;
    const ay = toFiniteNumber('latitude' in a ? a.latitude : a.y) ?? 0;
    const bx = toFiniteNumber('longitude' in b ? b.longitude : b.x) ?? 0;
    const by = toFiniteNumber('latitude' in b ? b.latitude : b.y) ?? 0;
    const dx = ax - bx;
    const dy = ay - by;
    return Math.sqrt(dx * dx + dy * dy);
}

function routePlan(taskId: string, payload: any): {
    route: RoutePoint[];
    totalDistance: number;
    estimatedDurationSeconds: number;
} {
    const start = payload?.start as RoutePoint | undefined;
    const waypoints = (Array.isArray(payload?.waypoints) ? payload.waypoints : []) as RoutePoint[];
    const end = payload?.end as RoutePoint | undefined;

    if (!start) {
        throw new Error('缺少路径起点');
    }

    const remain = [...waypoints];
    const ordered: RoutePoint[] = [start];
    let current = start;
    let totalDistance = 0;
    const totalSteps = Math.max(1, remain.length);

    for (let step = 0; step < totalSteps; step += 1) {
        ensureNotCanceled(taskId);
        if (remain.length === 0) {
            break;
        }

        let nearestIndex = 0;
        let nearestDistance = Number.POSITIVE_INFINITY;
        for (let i = 0; i < remain.length; i += 1) {
            const d = distance(current, remain[i]);
            if (d < nearestDistance) {
                nearestDistance = d;
                nearestIndex = i;
            }
        }

        const [nearest] = remain.splice(nearestIndex, 1);
        ordered.push(nearest);
        totalDistance += nearestDistance;
        current = nearest;

        const progress = 15 + ((step + 1) / totalSteps) * 70;
        postProgress(taskId, progress, '正在计算最短访问序列');
    }

    if (end) {
        totalDistance += distance(current, end);
        ordered.push(end);
    }

    postProgress(taskId, 100, '路径规划完成');

    return {
        route: ordered,
        totalDistance,
        estimatedDurationSeconds: Math.round((totalDistance / 12) * 3600)
    };
}

function samplingOptimize(taskId: string, payload: any): {
    recommendations: Array<NumericPoint & { score: number; priority: number }>;
    requestedCount: number;
    selectedCount: number;
} {
    const candidates = (Array.isArray(payload?.candidates) ? payload.candidates : []) as NumericPoint[];
    const existingPoints = (Array.isArray(payload?.existingPoints) ? payload.existingPoints : []) as NumericPoint[];
    const requestedCount = Math.max(1, Number(payload?.count || 10));
    const minDistance = Math.max(0, Number(payload?.minDistance || 0));

    if (candidates.length === 0) {
        return { recommendations: [], requestedCount, selectedCount: 0 };
    }

    const scored = candidates.map((candidate, index) => {
        ensureNotCanceled(taskId);
        if (index % 100 === 0) {
            postProgress(taskId, Math.min(50, (index / Math.max(1, candidates.length)) * 50), '正在评估候选采样点');
        }

        const uncertaintyScore = toFiniteNumber(candidate.uncertainty) ?? 0;
        const nearestDistance = existingPoints.length === 0
            ? 1
            : Math.min(...existingPoints.map((point) => distance(candidate, point)));
        const distanceScore = Math.min(1, nearestDistance / Math.max(1, minDistance || nearestDistance));
        const score = uncertaintyScore * 0.7 + distanceScore * 0.3;

        return {
            ...candidate,
            score
        };
    });

    scored.sort((a, b) => b.score - a.score);

    const selected: Array<NumericPoint & { score: number; priority: number }> = [];
    for (const candidate of scored) {
        ensureNotCanceled(taskId);
        if (selected.length >= requestedCount) {
            break;
        }
        const tooClose = selected.some((point) => distance(point, candidate) < minDistance);
        if (tooClose) {
            continue;
        }
        selected.push({
            ...candidate,
            priority: selected.length + 1
        });
    }

    postProgress(taskId, 100, '采样优化完成');

    return {
        recommendations: selected,
        requestedCount,
        selectedCount: selected.length
    };
}

function idwPredict(points: NumericPoint[], x: number, y: number, power: number): number {
    let numerator = 0;
    let denominator = 0;

    for (const point of points) {
        const dx = x - point.x;
        const dy = y - point.y;
        const d = Math.sqrt(dx * dx + dy * dy);

        if (d === 0) {
            return point.value ?? 0;
        }

        const weight = 1 / Math.pow(d, power);
        numerator += (point.value ?? 0) * weight;
        denominator += weight;
    }

    return denominator > 0 ? numerator / denominator : 0;
}

function krigingPreview(taskId: string, payload: any): {
    bounds: Bounds;
    resolution: number;
    prediction: Array<{ x: number; y: number; value: number }>;
} {
    const points = (Array.isArray(payload?.points) ? payload.points : []) as NumericPoint[];
    const power = Math.max(1, Math.min(4, Number(payload?.power || 2)));
    const requestedResolution = Math.max(10, Number(payload?.gridResolution || 100));
    const resolution = Math.min(180, requestedResolution);

    if (points.length < 3) {
        throw new Error('预览插值至少需要 3 个采样点');
    }

    const bounds = payload?.bounds && Number.isFinite(payload.bounds.minX)
        ? payload.bounds
        : computeBounds(points);

    const prediction: Array<{ x: number; y: number; value: number }> = [];
    const width = bounds.maxX - bounds.minX || 1;
    const height = bounds.maxY - bounds.minY || 1;

    for (let row = 0; row < resolution; row += 1) {
        ensureNotCanceled(taskId);
        const y = bounds.minY + (row / Math.max(1, resolution - 1)) * height;
        for (let col = 0; col < resolution; col += 1) {
            const x = bounds.minX + (col / Math.max(1, resolution - 1)) * width;
            prediction.push({
                x,
                y,
                value: idwPredict(points, x, y, power)
            });
        }

        const progress = Math.min(98, ((row + 1) / resolution) * 100);
        postProgress(taskId, progress, '正在计算插值网格');
    }

    postProgress(taskId, 100, '插值预览完成');

    return {
        bounds,
        resolution,
        prediction
    };
}

self.onmessage = (event: MessageEvent<WorkerIncomingMessage>) => {
    const data = event.data;
    if (!data || typeof data !== 'object') {
        return;
    }

    if (data.channel === 'cancel') {
        canceledTaskIds.add(data.id);
        return;
    }

    const { id, type, payload } = data;

    try {
        let result: unknown;
        switch (type) {
            case 'dataPreprocess':
                result = preprocessData(id, payload);
                break;
            case 'samplingOptimize':
                result = samplingOptimize(id, payload);
                break;
            case 'routePlan':
                result = routePlan(id, payload);
                break;
            case 'krigingPreview':
                result = krigingPreview(id, payload);
                break;
            default:
                throw new Error(`不支持的任务类型: ${String(type)}`);
        }
        postResult(id, result);
    } catch (error) {
        postError(id, error);
    } finally {
        canceledTaskIds.delete(id);
    }
};

export {};
