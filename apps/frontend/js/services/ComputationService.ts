import { WorkerPoolManager } from '../workers/WorkerPoolManager.js';

export interface PreprocessResult<TPoint = any> {
    points: TPoint[];
    removedCount: number;
    pointCount: number;
    bounds: {
        minX: number;
        maxX: number;
        minY: number;
        maxY: number;
    };
    statistics: {
        minValue: number;
        maxValue: number;
        meanValue: number;
    };
}

export class ComputationService {
    private static instance: ComputationService | null = null;
    private workerPool = WorkerPoolManager.getInstance();

    public static getInstance(): ComputationService {
        if (!ComputationService.instance) {
            ComputationService.instance = new ComputationService();
        }
        return ComputationService.instance;
    }

    public preloadWorkers(): void {
        this.workerPool.preload();
    }

    public isWorkerEnabled(): boolean {
        return this.workerPool.isEnabled();
    }

    public async preprocessSamplingPoints<TPoint = any>(
        points: TPoint[],
        onProgress?: (progress: number, message?: string) => void
    ): Promise<PreprocessResult<TPoint>> {
        return this.workerPool.runTask(
            'dataPreprocess',
            {
                points,
                dedupe: true,
                normalize: false
            },
            {
                priority: 'high',
                onProgress
            }
        ) as Promise<PreprocessResult<TPoint>>;
    }

    public async optimizeSamplingCandidates(
        candidates: Array<Record<string, unknown>>,
        existingPoints: Array<Record<string, unknown>>,
        count: number,
        onProgress?: (progress: number, message?: string) => void
    ): Promise<{
        recommendations: Array<Record<string, unknown>>;
        requestedCount: number;
        selectedCount: number;
    }> {
        return this.workerPool.runTask(
            'samplingOptimize',
            {
                candidates,
                existingPoints,
                count
            },
            {
                priority: 'normal',
                onProgress
            }
        ) as Promise<{
            recommendations: Array<Record<string, unknown>>;
            requestedCount: number;
            selectedCount: number;
        }>;
    }

    public async planRouteLocally(
        start: Record<string, unknown>,
        waypoints: Array<Record<string, unknown>>,
        end?: Record<string, unknown>,
        onProgress?: (progress: number, message?: string) => void
    ): Promise<{
        route: Array<Record<string, unknown>>;
        totalDistance: number;
        estimatedDurationSeconds: number;
    }> {
        return this.workerPool.runTask(
            'routePlan',
            {
                start,
                waypoints,
                end
            },
            {
                priority: 'high',
                onProgress
            }
        ) as Promise<{
            route: Array<Record<string, unknown>>;
            totalDistance: number;
            estimatedDurationSeconds: number;
        }>;
    }

    public async previewKriging(
        points: Array<Record<string, unknown>>,
        gridResolution: number,
        bounds?: { minX: number; maxX: number; minY: number; maxY: number },
        onProgress?: (progress: number, message?: string) => void
    ): Promise<{
        bounds: { minX: number; maxX: number; minY: number; maxY: number };
        resolution: number;
        prediction: Array<{ x: number; y: number; value: number }>;
    }> {
        return this.workerPool.runTask(
            'krigingPreview',
            {
                points,
                gridResolution,
                bounds
            },
            {
                priority: 'low',
                onProgress
            }
        ) as Promise<{
            bounds: { minX: number; maxX: number; minY: number; maxY: number };
            resolution: number;
            prediction: Array<{ x: number; y: number; value: number }>;
        }>;
    }

    public cleanup(): void {
        this.workerPool.cleanup();
    }
}

export default ComputationService;
