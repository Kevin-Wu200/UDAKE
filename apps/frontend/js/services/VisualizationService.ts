import type {
    PollutantConcentration,
    PollutantDefinition,
    PollutantLegendItem,
    PollutantUnit
} from '../../types/pollutant';
import type {
    STPredictionSnapshot,
    STVisualizationBundle
} from '../../types/spatiotemporal';
import type {
    FlowVector,
    TimeFrameDataPoint,
    VisualizationFrame
} from '../../types/visualization';

export interface ChunkLoadOptions {
    chunkSize: number;
    preloadCount: number;
}

export class VisualizationService {
    private readonly frameCache: Map<string, VisualizationFrame> = new Map();

    convertUnit(value: number, from: PollutantUnit, to: PollutantUnit): number {
        if (from === to) {
            return value;
        }

        const ugm3ToMgm3 = 0.001;
        const mgm3ToUgm3 = 1000;
        const uglToMgl = 0.001;
        const mglToUgl = 1000;

        if (from === 'ug/m3' && to === 'mg/m3') {
            return value * ugm3ToMgm3;
        }
        if (from === 'mg/m3' && to === 'ug/m3') {
            return value * mgm3ToUgm3;
        }
        if (from === 'ug/L' && to === 'mg/L') {
            return value * uglToMgl;
        }
        if (from === 'mg/L' && to === 'ug/L') {
            return value * mglToUgl;
        }

        return value;
    }

    classifyConcentration(value: number, definition: PollutantDefinition): PollutantConcentration['level'] {
        if (value < definition.thresholds.low) {
            return 'low';
        }
        if (value < definition.thresholds.medium) {
            return 'medium';
        }
        if (value < definition.thresholds.high) {
            return 'high';
        }
        return 'critical';
    }

    buildLegend(definition: PollutantDefinition): PollutantLegendItem[] {
        const [c1, c2, c3, c4] = definition.colorStops;
        return [
            {
                label: '低',
                min: 0,
                max: definition.thresholds.low,
                color: c1 || '#2b83ba'
            },
            {
                label: '中',
                min: definition.thresholds.low,
                max: definition.thresholds.medium,
                color: c2 || '#abdda4'
            },
            {
                label: '高',
                min: definition.thresholds.medium,
                max: definition.thresholds.high,
                color: c3 || '#fdae61'
            },
            {
                label: '极高',
                min: definition.thresholds.high,
                max: Number.POSITIVE_INFINITY,
                color: c4 || '#d7191c'
            }
        ];
    }

    toVisualizationBundle(snapshots: STPredictionSnapshot[]): STVisualizationBundle {
        const timeline = snapshots.map(snapshot => snapshot.timestamp);
        const frames = timeline.map(timestamp => {
            const points = snapshots
                .filter(snapshot => snapshot.timestamp === timestamp)
                .map(snapshot => this.snapshotToPoint(snapshot));
            return this.createFrame(timestamp, points);
        });

        return {
            timeline,
            frames,
            snapshots
        };
    }

    private snapshotToPoint(snapshot: STPredictionSnapshot): TimeFrameDataPoint {
        return {
            id: `${snapshot.timestamp}:${snapshot.location.x}:${snapshot.location.y}:${snapshot.location.z}`,
            position: {
                x: snapshot.location.x,
                y: snapshot.location.y,
                z: snapshot.location.z
            },
            concentrations: snapshot.concentrations,
            uncertainty: snapshot.uncertainty
        };
    }

    createFrame(timestamp: string, points: TimeFrameDataPoint[]): VisualizationFrame {
        const vectors: FlowVector[] = [];
        for (let i = 1; i < points.length; i += 1) {
            vectors.push({
                from: points[i - 1].position,
                to: points[i].position,
                magnitude: Math.hypot(
                    points[i].position.x - points[i - 1].position.x,
                    points[i].position.y - points[i - 1].position.y,
                    points[i].position.z - points[i - 1].position.z
                )
            });
        }

        return {
            timestamp,
            heatmap: points,
            samples: points,
            flowVectors: vectors
        };
    }

    async loadInChunks<T>(items: T[], options: ChunkLoadOptions, onChunk: (chunk: T[]) => Promise<void> | void): Promise<void> {
        const { chunkSize, preloadCount } = options;
        for (let i = 0; i < items.length; i += chunkSize) {
            const chunk = items.slice(i, i + chunkSize);
            await onChunk(chunk);
            const preloadStart = i + chunkSize;
            const preloadEnd = preloadStart + chunkSize * preloadCount;
            const preloadChunk = items.slice(preloadStart, preloadEnd);
            preloadChunk.forEach((_, offset) => {
                const key = `${preloadStart + offset}`;
                this.frameCache.set(key, this.frameCache.get(key) || ({} as VisualizationFrame));
            });
        }
    }

    cacheFrame(frame: VisualizationFrame): void {
        this.frameCache.set(frame.timestamp, frame);
    }

    getCachedFrame(timestamp: string): VisualizationFrame | undefined {
        return this.frameCache.get(timestamp);
    }

    clearCache(): void {
        this.frameCache.clear();
    }
}
