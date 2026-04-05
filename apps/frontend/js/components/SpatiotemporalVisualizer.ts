import type { PollutantDefinition } from '../../types/pollutant';
import type { STPredictionSnapshot, STVisualizationBundle } from '../../types/spatiotemporal';
import type { ViewSnapshot, VisualizationFrame, VisualizationRenderStats } from '../../types/visualization';
import { ControlPanel } from './ControlPanel';
import { InfoPanel } from './InfoPanel';
import { PollutantLayerManager } from './PollutantLayerManager';
import { TimeSlider } from './TimeSlider';
import { VisualizationService } from '../services/VisualizationService';

export interface SceneRenderer {
    renderTerrain?: () => void;
    renderHeatmap?: (frame: VisualizationFrame, pollutantIds: string[]) => void;
    renderSamples?: (frame: VisualizationFrame) => void;
    renderFlowArrows?: (frame: VisualizationFrame) => void;
    setCamera?: (view: ViewSnapshot) => void;
}

export interface VisualizerOptions {
    pollutants: PollutantDefinition[];
    renderer?: SceneRenderer;
    visualizationService?: VisualizationService;
}

export interface RegionRect {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
}

export class SpatiotemporalVisualizer {
    private readonly container: HTMLElement;
    private readonly options: VisualizerOptions;
    private readonly service: VisualizationService;

    private readonly timeSlider: TimeSlider;
    private readonly layerManager: PollutantLayerManager;
    private readonly infoPanel: InfoPanel;
    private readonly controlPanel: ControlPanel;

    private data: STVisualizationBundle = { timeline: [], frames: [], snapshots: [] };
    private selectedPollutants: string[];
    private renderRequested = false;
    private camera: ViewSnapshot = { heading: 0, tilt: 45, zoom: 10, center: { x: 0, y: 0 } };
    private savedView: ViewSnapshot | null = null;

    constructor(container: HTMLElement, options: VisualizerOptions) {
        this.container = container;
        this.options = options;
        this.service = options.visualizationService || new VisualizationService();
        this.selectedPollutants = options.pollutants.map(item => item.id);

        this.container.innerHTML = this.template();
        this.timeSlider = new TimeSlider(this.getRequiredElement('st-time-slider-host'), {
            onTimeChange: (timestamp) => this.renderByTimestamp(timestamp)
        });
        this.layerManager = new PollutantLayerManager(this.getRequiredElement('st-layer-manager-host'), options.pollutants, {
            onLayerVisibilityChange: (layerId, visible) => this.onLayerVisibilityChange(layerId, visible),
            onLayerOrderChange: () => this.requestRender()
        });
        this.infoPanel = new InfoPanel(this.getRequiredElement('st-info-host'));
        this.controlPanel = new ControlPanel(this.getRequiredElement('st-control-host'), options.pollutants, {
            onPollutantsChange: (ids) => {
                this.selectedPollutants = ids;
                this.requestRender();
            },
            onTimeSpeedChange: () => this.requestRender(),
            onViewAction: (action) => this.handleViewAction(action)
        });

        this.bindMapInteractions();
        this.options.renderer?.renderTerrain?.();
    }

    async loadBundle(bundle: STVisualizationBundle): Promise<void> {
        this.data = bundle;
        await this.service.loadInChunks(bundle.frames, { chunkSize: 10, preloadCount: 1 }, async (chunk) => {
            chunk.forEach(frame => this.service.cacheFrame(frame));
        });
        this.timeSlider.setTimeline(bundle.timeline);
        this.renderByTimestamp(bundle.timeline[0] || '');
    }

    async loadSnapshots(snapshots: STPredictionSnapshot[]): Promise<void> {
        await this.loadBundle(this.service.toVisualizationBundle(snapshots));
    }

    queryAt(x: number, y: number, z: number): STPredictionSnapshot | null {
        const timestamp = this.timeSlider.getCurrentTime();
        if (!timestamp) {
            return null;
        }
        const candidates = this.data.snapshots.filter(item => item.timestamp === timestamp);
        let best: STPredictionSnapshot | null = null;
        let bestDistance = Number.POSITIVE_INFINITY;
        candidates.forEach(item => {
            const distance = Math.hypot(item.location.x - x, item.location.y - y, item.location.z - z);
            if (distance < bestDistance) {
                bestDistance = distance;
                best = item;
            }
        });

        if (best) {
            this.infoPanel.update(best);
        }

        return best;
    }

    hoverAt(x: number, y: number, z: number): void {
        const hit = this.queryAt(x, y, z);
        if (!hit) {
            this.infoPanel.updateHover('--');
            return;
        }

        const concentrationText = hit.concentrations.map(item => `${item.pollutantId}=${item.value.toFixed(2)}${item.unit}`).join(', ');
        this.infoPanel.updateHover(`${hit.timestamp} | ${concentrationText}`);
    }

    selectRegion(rect: RegionRect): STPredictionSnapshot[] {
        const timestamp = this.timeSlider.getCurrentTime();
        if (!timestamp) {
            return [];
        }

        const selected = this.data.snapshots.filter(item => {
            return item.timestamp === timestamp
                && item.location.x >= rect.minX
                && item.location.x <= rect.maxX
                && item.location.y >= rect.minY
                && item.location.y <= rect.maxY;
        });

        const values = selected
            .flatMap(item => item.concentrations)
            .filter(item => this.selectedPollutants.includes(item.pollutantId))
            .map(item => item.value);

        if (values.length > 0) {
            const sum = values.reduce((acc, curr) => acc + curr, 0);
            this.infoPanel.updateSelectionStats({
                count: values.length,
                mean: sum / values.length,
                min: Math.min(...values),
                max: Math.max(...values)
            });
        }

        return selected;
    }

    exportSelection(selected: STPredictionSnapshot[]): string {
        return JSON.stringify(selected, null, 2);
    }

    getRenderStats(frame: VisualizationFrame): VisualizationRenderStats {
        const visiblePoints = this.applyFrustumCulling(frame.heatmap);
        const lodPoints = this.applyLOD(visiblePoints);
        return {
            renderedPoints: lodPoints.length,
            culledPoints: frame.heatmap.length - visiblePoints.length,
            lodReductionRatio: frame.heatmap.length > 0 ? 1 - lodPoints.length / frame.heatmap.length : 0,
            frameTimeMs: 0
        };
    }

    private template(): string {
        return `
            <section class="st-visualizer-layout">
                <div id="st-map-host" class="st-map-host">GeoScene 3D 视图</div>
                <div id="st-time-slider-host"></div>
                <div class="st-side-grid">
                    <div id="st-control-host"></div>
                    <div id="st-layer-manager-host"></div>
                    <div id="st-info-host"></div>
                </div>
            </section>
        `;
    }

    private bindMapInteractions(): void {
        const mapHost = this.container.querySelector('#st-map-host') as HTMLElement | null;
        if (!mapHost) {
            return;
        }

        mapHost.addEventListener('click', (event) => {
            const x = event.offsetX;
            const y = event.offsetY;
            this.queryAt(x, y, 0);
        });

        mapHost.addEventListener('mousemove', (event) => {
            const x = event.offsetX;
            const y = event.offsetY;
            this.hoverAt(x, y, 0);
        });
    }

    private onLayerVisibilityChange(layerId: string, visible: boolean): void {
        if (visible && !this.selectedPollutants.includes(layerId)) {
            this.selectedPollutants = [...this.selectedPollutants, layerId];
        }
        if (!visible) {
            this.selectedPollutants = this.selectedPollutants.filter(item => item !== layerId);
        }
        this.requestRender();
    }

    private handleViewAction(action: 'rotate-left' | 'rotate-right' | 'zoom-in' | 'zoom-out' | 'pan-left' | 'pan-right' | 'save' | 'restore'): void {
        switch (action) {
            case 'rotate-left':
                this.camera.heading -= 10;
                break;
            case 'rotate-right':
                this.camera.heading += 10;
                break;
            case 'zoom-in':
                this.camera.zoom += 1;
                break;
            case 'zoom-out':
                this.camera.zoom = Math.max(1, this.camera.zoom - 1);
                break;
            case 'pan-left':
                this.camera.center.x -= 10;
                break;
            case 'pan-right':
                this.camera.center.x += 10;
                break;
            case 'save':
                this.savedView = { ...this.camera, center: { ...this.camera.center } };
                break;
            case 'restore':
                if (this.savedView) {
                    this.camera = { ...this.savedView, center: { ...this.savedView.center } };
                }
                break;
            default:
                break;
        }

        this.options.renderer?.setCamera?.(this.camera);
        this.requestRender();
    }

    private getRequiredElement(id: string): HTMLElement {
        const element = this.container.querySelector(`#${id}`) as HTMLElement | null;
        if (!element) {
            throw new Error(`缺少挂载节点: ${id}`);
        }
        return element;
    }

    private requestRender(): void {
        if (this.renderRequested) {
            return;
        }
        this.renderRequested = true;
        window.requestAnimationFrame(() => {
            this.renderRequested = false;
            const timestamp = this.timeSlider.getCurrentTime();
            if (timestamp) {
                this.renderByTimestamp(timestamp);
            }
        });
    }

    private renderByTimestamp(timestamp: string): void {
        if (!timestamp) {
            return;
        }
        const start = performance.now();
        const frame = this.service.getCachedFrame(timestamp) || this.data.frames.find(item => item.timestamp === timestamp);
        if (!frame) {
            return;
        }

        const visible = this.applyFrustumCulling(frame.heatmap);
        const lodHeatmap = this.applyLOD(visible);
        const renderFrame: VisualizationFrame = {
            ...frame,
            heatmap: lodHeatmap,
            samples: this.applyLOD(frame.samples)
        };

        this.options.renderer?.renderHeatmap?.(renderFrame, this.selectedPollutants);
        this.options.renderer?.renderSamples?.(renderFrame);
        this.options.renderer?.renderFlowArrows?.(renderFrame);

        const latest = this.data.snapshots.find(item => item.timestamp === timestamp);
        if (latest) {
            this.infoPanel.update(latest);
        }

        const stats = this.getRenderStats(renderFrame);
        stats.frameTimeMs = performance.now() - start;
        const mapHost = this.container.querySelector('#st-map-host') as HTMLElement | null;
        if (mapHost) {
            mapHost.dataset.renderStats = JSON.stringify(stats);
        }
    }

    private applyFrustumCulling<T extends { position: { x: number; y: number } }>(points: T[]): T[] {
        const radius = Math.max(100, this.camera.zoom * 20);
        return points.filter(point => {
            const dx = Math.abs(point.position.x - this.camera.center.x);
            const dy = Math.abs(point.position.y - this.camera.center.y);
            return dx <= radius && dy <= radius;
        });
    }

    private applyLOD<T>(points: T[]): T[] {
        const step = this.camera.zoom >= 12 ? 1 : this.camera.zoom >= 8 ? 2 : 4;
        return points.filter((_, index) => index % step === 0);
    }

    destroy(): void {
        this.timeSlider.destroy();
        this.layerManager.destroy();
        this.infoPanel.destroy();
        this.controlPanel.destroy();
        this.container.innerHTML = '';
    }
}
