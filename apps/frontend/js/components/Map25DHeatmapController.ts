import type { SamplingPoint } from '../../types/core';

type MapMode = '2d' | '2.5d';
type GradientPreset = 'classic' | 'warm' | 'cool' | 'viridis';

interface HeatmapDataPoint {
    lng: number;
    lat: number;
    value: number;
    sourceId: string;
    timestamp: number;
}

interface HeatmapDataSource {
    getFrame(frameIndex: number): HeatmapDataPoint[];
    getFrameCount(): number;
    exportGeoJSON(frameIndex: number): {
        type: 'FeatureCollection';
        features: Array<{
            type: 'Feature';
            geometry: { type: 'Point'; coordinates: [number, number] };
            properties: Record<string, string | number>;
        }>;
    };
}

interface ViewportBounds {
    minLng: number;
    minLat: number;
    maxLng: number;
    maxLat: number;
}

interface CameraState {
    rotation: number;
    tilt: number;
    zoom: number;
}

interface HeatmapConfig {
    enabled: boolean;
    radius: number;
    intensity: number;
    gradient: GradientPreset;
    minFilter: number;
    maxFilter: number;
    timeIndex: number;
    autoPlay: boolean;
}

interface ContextProvider {
    getView: () => any;
    getSamplingPoints: () => SamplingPoint[];
}

interface ScreenPoint {
    x: number;
    y: number;
    point: HeatmapDataPoint;
}

class LayerManagerHeatmapDataSource implements HeatmapDataSource {
    private readonly frameCount = 48;
    private readonly getSamplingPoints: () => SamplingPoint[];

    constructor(getSamplingPoints: () => SamplingPoint[]) {
        this.getSamplingPoints = getSamplingPoints;
    }

    getFrame(frameIndex: number): HeatmapDataPoint[] {
        const points = this.getSamplingPoints() || [];
        if (points.length === 0) {
            return [];
        }

        const values = points.map((p) => Number.isFinite(p.value) ? p.value : 0);
        const min = Math.min(...values);
        const max = Math.max(...values);
        const span = Math.max(max - min, 1e-6);
        const phase = ((frameIndex % this.frameCount) / this.frameCount) * Math.PI * 2;
        const timestamp = Date.now();

        return points.map((p, index) => {
            const normalized = (p.value - min) / span;
            const pulse = 0.85 + 0.15 * Math.sin(phase + index * 0.43);
            return {
                lng: p.x,
                lat: p.y,
                value: Math.max(0, Math.min(1, normalized * pulse)),
                sourceId: `sp-${index}`,
                timestamp
            };
        });
    }

    getFrameCount(): number {
        return this.frameCount;
    }

    exportGeoJSON(frameIndex: number): {
        type: 'FeatureCollection';
        features: Array<{
            type: 'Feature';
            geometry: { type: 'Point'; coordinates: [number, number] };
            properties: Record<string, string | number>;
        }>;
    } {
        const frame = this.getFrame(frameIndex);
        return {
            type: 'FeatureCollection',
            features: frame.map((p) => ({
                type: 'Feature',
                geometry: {
                    type: 'Point',
                    coordinates: [p.lng, p.lat]
                },
                properties: {
                    sourceId: p.sourceId,
                    value: Number(p.value.toFixed(6)),
                    timestamp: p.timestamp
                }
            }))
        };
    }
}

export class Map25DHeatmapController {
    private mapContainer: HTMLElement;
    private provider: ContextProvider;
    private dataSource: HeatmapDataSource;

    private layer: HTMLDivElement;
    private canvas: HTMLCanvasElement;
    private ctx: CanvasRenderingContext2D;
    private tooltip: HTMLDivElement;
    private panel: HTMLDivElement;

    private mode: MapMode = '2d';
    private camera: CameraState = { rotation: 32, tilt: 48, zoom: 1 };
    private heatmap: HeatmapConfig = {
        enabled: true,
        radius: 36,
        intensity: 0.9,
        gradient: 'classic',
        minFilter: 0,
        maxFilter: 1,
        timeIndex: 0,
        autoPlay: false
    };

    private panelVisible = false;
    private animationId: number | null = null;
    private dpr = 1;
    private lastFrameAt = 0;
    private fps = 0;

    private screenPoints: ScreenPoint[] = [];
    private lastHoverId: string | null = null;

    constructor(mapContainer: HTMLElement, provider: ContextProvider) {
        this.mapContainer = mapContainer;
        this.provider = provider;
        this.dataSource = new LayerManagerHeatmapDataSource(provider.getSamplingPoints);

        this.layer = document.createElement('div');
        this.layer.className = 'map-visual-enhancement-layer';

        this.canvas = document.createElement('canvas');
        this.canvas.className = 'map-visual-enhancement-canvas';
        const context = this.canvas.getContext('2d');
        if (!context) {
            throw new Error('无法获取 2D canvas 上下文');
        }
        this.ctx = context;
        this.layer.appendChild(this.canvas);

        this.tooltip = document.createElement('div');
        this.tooltip.className = 'map-visual-tooltip';
        this.tooltip.style.display = 'none';
        this.layer.appendChild(this.tooltip);

        this.panel = this.createPanel();

        this.mapContainer.appendChild(this.layer);
        this.mapContainer.appendChild(this.panel);

        this.resize();
        this.bindEvents();
        this.start();
    }

    updateContext(provider: ContextProvider): void {
        this.provider = provider;
        this.dataSource = new LayerManagerHeatmapDataSource(provider.getSamplingPoints);
    }

    togglePanel(forceVisible?: boolean): void {
        this.panelVisible = typeof forceVisible === 'boolean' ? forceVisible : !this.panelVisible;
        this.panel.classList.toggle('visible', this.panelVisible);
    }

    attachToolbarButton(toolbar: HTMLElement): void {
        if (toolbar.querySelector('[data-toolbar-id="map-visual-enhancement"]')) {
            return;
        }

        const button = document.createElement('button');
        button.className = 'toolbar-btn';
        button.setAttribute('data-toolbar-id', 'map-visual-enhancement');
        button.title = '2.5D/热力图';
        button.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 7l9-4 9 4-9 4-9-4z"></path>
                <path d="M3 17l9 4 9-4"></path>
                <path d="M3 12l9 4 9-4"></path>
            </svg>
        `;
        button.addEventListener('click', () => {
            this.togglePanel();
        });
        toolbar.appendChild(button);
    }

    destroy(): void {
        if (this.animationId !== null) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }

        window.removeEventListener('resize', this.resizeHandler);
        this.mapContainer.removeEventListener('mousemove', this.mouseMoveHandler);
        this.mapContainer.removeEventListener('mouseleave', this.mouseLeaveHandler);
        this.mapContainer.removeEventListener('click', this.clickHandler);

        this.panel.remove();
        this.layer.remove();
    }

    private resizeHandler = () => this.resize();

    private mouseMoveHandler = (event: MouseEvent) => this.onMouseMove(event);

    private mouseLeaveHandler = () => this.onMouseLeave();

    private clickHandler = (event: MouseEvent) => this.onClick(event);

    private bindEvents(): void {
        window.addEventListener('resize', this.resizeHandler);
        this.mapContainer.addEventListener('mousemove', this.mouseMoveHandler);
        this.mapContainer.addEventListener('mouseleave', this.mouseLeaveHandler);
        this.mapContainer.addEventListener('click', this.clickHandler);

        const modeBtn = this.panel.querySelector('#mve-mode-btn') as HTMLButtonElement | null;
        modeBtn?.addEventListener('click', () => {
            this.mode = this.mode === '2d' ? '2.5d' : '2d';
            modeBtn.textContent = this.mode === '2d' ? '切换 2.5D' : '切换 2D';
        });

        const heatmapSwitch = this.panel.querySelector('#mve-heatmap-enabled') as HTMLInputElement | null;
        heatmapSwitch?.addEventListener('change', () => {
            this.heatmap.enabled = heatmapSwitch.checked;
        });

        const radiusInput = this.panel.querySelector('#mve-radius') as HTMLInputElement | null;
        const radiusValue = this.panel.querySelector('#mve-radius-value') as HTMLElement | null;
        radiusInput?.addEventListener('input', () => {
            this.heatmap.radius = Number(radiusInput.value);
            if (radiusValue) radiusValue.textContent = radiusInput.value;
        });

        const intensityInput = this.panel.querySelector('#mve-intensity') as HTMLInputElement | null;
        const intensityValue = this.panel.querySelector('#mve-intensity-value') as HTMLElement | null;
        intensityInput?.addEventListener('input', () => {
            this.heatmap.intensity = Number(intensityInput.value);
            if (intensityValue) intensityValue.textContent = intensityInput.value;
        });

        const gradientSelect = this.panel.querySelector('#mve-gradient') as HTMLSelectElement | null;
        gradientSelect?.addEventListener('change', () => {
            const value = gradientSelect.value as GradientPreset;
            this.heatmap.gradient = value;
        });

        const timeSlider = this.panel.querySelector('#mve-time') as HTMLInputElement | null;
        const timeValue = this.panel.querySelector('#mve-time-value') as HTMLElement | null;
        timeSlider?.addEventListener('input', () => {
            this.heatmap.timeIndex = Number(timeSlider.value);
            if (timeValue) timeValue.textContent = timeSlider.value;
        });

        const playBtn = this.panel.querySelector('#mve-play-time') as HTMLButtonElement | null;
        playBtn?.addEventListener('click', () => {
            this.heatmap.autoPlay = !this.heatmap.autoPlay;
            playBtn.textContent = this.heatmap.autoPlay ? '暂停时间轴' : '播放时间轴';
        });

        const minFilterInput = this.panel.querySelector('#mve-filter-min') as HTMLInputElement | null;
        const maxFilterInput = this.panel.querySelector('#mve-filter-max') as HTMLInputElement | null;
        minFilterInput?.addEventListener('input', () => {
            const value = Math.max(0, Math.min(1, Number(minFilterInput.value)));
            this.heatmap.minFilter = value;
            if (maxFilterInput && this.heatmap.maxFilter < value) {
                this.heatmap.maxFilter = value;
                maxFilterInput.value = String(value);
            }
        });
        maxFilterInput?.addEventListener('input', () => {
            const value = Math.max(0, Math.min(1, Number(maxFilterInput.value)));
            this.heatmap.maxFilter = value;
            if (minFilterInput && this.heatmap.minFilter > value) {
                this.heatmap.minFilter = value;
                minFilterInput.value = String(value);
            }
        });

        const rotateInput = this.panel.querySelector('#mve-rotate') as HTMLInputElement | null;
        const tiltInput = this.panel.querySelector('#mve-tilt') as HTMLInputElement | null;
        const zoomInput = this.panel.querySelector('#mve-zoom') as HTMLInputElement | null;
        rotateInput?.addEventListener('input', () => {
            this.camera.rotation = Number(rotateInput.value);
        });
        tiltInput?.addEventListener('input', () => {
            this.camera.tilt = Number(tiltInput.value);
        });
        zoomInput?.addEventListener('input', () => {
            this.camera.zoom = Number(zoomInput.value);
        });

        const exportPngBtn = this.panel.querySelector('#mve-export-png') as HTMLButtonElement | null;
        exportPngBtn?.addEventListener('click', () => this.exportPNG());

        const exportGeoJSONBtn = this.panel.querySelector('#mve-export-geojson') as HTMLButtonElement | null;
        exportGeoJSONBtn?.addEventListener('click', () => this.exportGeoJSON());
    }

    private createPanel(): HTMLDivElement {
        const panel = document.createElement('div');
        panel.className = 'map-visual-enhancement-panel';
        panel.innerHTML = `
            <div class="mve-header">
                <h3>2.5D 地图与交互热力图</h3>
                <button id="mve-close" class="mve-btn mve-btn-light">收起</button>
            </div>
            <div class="mve-grid">
                <div class="mve-group">
                    <label>地图模式</label>
                    <button id="mve-mode-btn" class="mve-btn">切换 2.5D</button>
                </div>
                <div class="mve-group mve-inline">
                    <label><input id="mve-heatmap-enabled" type="checkbox" checked /> 热力图开启</label>
                </div>
                <div class="mve-group">
                    <label>热力半径 <span id="mve-radius-value">36</span></label>
                    <input id="mve-radius" type="range" min="12" max="80" step="1" value="36" />
                </div>
                <div class="mve-group">
                    <label>热力强度 <span id="mve-intensity-value">0.9</span></label>
                    <input id="mve-intensity" type="range" min="0.2" max="2" step="0.1" value="0.9" />
                </div>
                <div class="mve-group">
                    <label>渐变色</label>
                    <select id="mve-gradient">
                        <option value="classic">经典</option>
                        <option value="warm">暖色</option>
                        <option value="cool">冷色</option>
                        <option value="viridis">Viridis</option>
                    </select>
                </div>
                <div class="mve-group">
                    <label>时间帧 <span id="mve-time-value">0</span></label>
                    <input id="mve-time" type="range" min="0" max="47" step="1" value="0" />
                    <button id="mve-play-time" class="mve-btn mve-btn-light">播放时间轴</button>
                </div>
                <div class="mve-group mve-inline">
                    <label>过滤范围</label>
                    <div class="mve-row">
                        <input id="mve-filter-min" type="number" min="0" max="1" step="0.05" value="0" />
                        <input id="mve-filter-max" type="number" min="0" max="1" step="0.05" value="1" />
                    </div>
                </div>
                <div class="mve-group">
                    <label>相机旋转</label>
                    <input id="mve-rotate" type="range" min="0" max="360" step="1" value="32" />
                </div>
                <div class="mve-group">
                    <label>相机倾斜</label>
                    <input id="mve-tilt" type="range" min="20" max="75" step="1" value="48" />
                </div>
                <div class="mve-group">
                    <label>相机缩放</label>
                    <input id="mve-zoom" type="range" min="0.6" max="2" step="0.05" value="1" />
                </div>
                <div class="mve-group mve-inline">
                    <button id="mve-export-png" class="mve-btn">导出 PNG</button>
                    <button id="mve-export-geojson" class="mve-btn mve-btn-light">导出 GeoJSON</button>
                </div>
                <div class="mve-group mve-inline">
                    <span id="mve-selected">点击热力区域查看详情</span>
                    <span id="mve-fps">FPS: --</span>
                </div>
            </div>
        `;

        const closeBtn = panel.querySelector('#mve-close') as HTMLButtonElement | null;
        closeBtn?.addEventListener('click', () => this.togglePanel(false));

        return panel;
    }

    private start(): void {
        const loop = (time: number) => {
            this.animationId = requestAnimationFrame(loop);
            if (time - this.lastFrameAt < 33) {
                return;
            }

            const delta = time - this.lastFrameAt;
            this.lastFrameAt = time;
            this.fps = delta > 0 ? Math.round(1000 / delta) : 0;

            if (this.heatmap.autoPlay) {
                this.heatmap.timeIndex = (this.heatmap.timeIndex + 1) % this.dataSource.getFrameCount();
                const timeSlider = this.panel.querySelector('#mve-time') as HTMLInputElement | null;
                const timeValue = this.panel.querySelector('#mve-time-value') as HTMLElement | null;
                if (timeSlider) {
                    timeSlider.value = String(this.heatmap.timeIndex);
                }
                if (timeValue) {
                    timeValue.textContent = String(this.heatmap.timeIndex);
                }
            }

            this.render();
        };

        this.animationId = requestAnimationFrame(loop);
    }

    private resize(): void {
        const width = Math.max(this.mapContainer.clientWidth, 1);
        const height = Math.max(this.mapContainer.clientHeight, 1);
        this.dpr = Math.max(window.devicePixelRatio || 1, 1);

        this.canvas.width = Math.floor(width * this.dpr);
        this.canvas.height = Math.floor(height * this.dpr);
        this.canvas.style.width = `${width}px`;
        this.canvas.style.height = `${height}px`;

        this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    }

    private render(): void {
        const width = this.mapContainer.clientWidth;
        const height = this.mapContainer.clientHeight;
        this.ctx.clearRect(0, 0, width, height);

        const bounds = this.getBounds();
        if (!bounds) {
            this.screenPoints = [];
            return;
        }

        const frame = this.dataSource.getFrame(this.heatmap.timeIndex).filter((point) => (
            point.value >= this.heatmap.minFilter && point.value <= this.heatmap.maxFilter
        ));

        this.screenPoints = frame
            .map((point) => {
                const projected = this.project(point.lng, point.lat, bounds, width, height);
                return projected ? { x: projected.x, y: projected.y, point } : null;
            })
            .filter((item): item is ScreenPoint => Boolean(item));

        if (this.mode === '2.5d') {
            this.renderInterpolationSurface(frame, bounds, width, height);
            this.renderSamplingColumns(frame, bounds, width, height);
        }

        if (this.heatmap.enabled) {
            this.renderHeatmap(frame, bounds, width, height);
        }

        const fpsLabel = this.panel.querySelector('#mve-fps');
        if (fpsLabel) {
            fpsLabel.textContent = `FPS: ${this.fps}`;
        }
    }

    private renderHeatmap(frame: HeatmapDataPoint[], bounds: ViewportBounds, width: number, height: number): void {
        if (frame.length === 0) {
            return;
        }

        this.ctx.save();
        this.ctx.globalCompositeOperation = 'lighter';

        for (const point of frame) {
            const projected = this.project(point.lng, point.lat, bounds, width, height);
            if (!projected) {
                continue;
            }

            const radius = this.heatmap.radius * (0.7 + point.value * 0.6);
            const gradient = this.ctx.createRadialGradient(projected.x, projected.y, 0, projected.x, projected.y, radius);
            const color = this.getGradientColor(point.value, this.heatmap.gradient, 0.85 * this.heatmap.intensity);
            gradient.addColorStop(0, color);
            gradient.addColorStop(1, 'rgba(0,0,0,0)');

            this.ctx.fillStyle = gradient;
            this.ctx.beginPath();
            this.ctx.arc(projected.x, projected.y, radius, 0, Math.PI * 2);
            this.ctx.fill();
        }

        this.ctx.restore();
    }

    private renderSamplingColumns(frame: HeatmapDataPoint[], bounds: ViewportBounds, width: number, height: number): void {
        const sorted = [...frame].sort((a, b) => a.lat - b.lat);

        for (const point of sorted) {
            const base = this.project(point.lng, point.lat, bounds, width, height);
            if (!base) {
                continue;
            }

            const top = this.transform3D(base.x, base.y, point.value, width, height);
            this.ctx.strokeStyle = this.getGradientColor(point.value, this.heatmap.gradient, 0.75);
            this.ctx.lineWidth = 2;
            this.ctx.beginPath();
            this.ctx.moveTo(base.x, base.y);
            this.ctx.lineTo(top.x, top.y);
            this.ctx.stroke();

            this.ctx.fillStyle = this.getGradientColor(point.value, this.heatmap.gradient, 0.95);
            this.ctx.beginPath();
            this.ctx.arc(top.x, top.y, 3.8, 0, Math.PI * 2);
            this.ctx.fill();
        }
    }

    private renderInterpolationSurface(frame: HeatmapDataPoint[], bounds: ViewportBounds, width: number, height: number): void {
        if (frame.length < 3) {
            return;
        }

        const resolution = this.getSurfaceResolution(frame.length);
        const lonStep = (bounds.maxLng - bounds.minLng) / resolution;
        const latStep = (bounds.maxLat - bounds.minLat) / resolution;

        for (let ix = 0; ix <= resolution; ix++) {
            for (let iy = 0; iy <= resolution; iy++) {
                const lng = bounds.minLng + ix * lonStep;
                const lat = bounds.minLat + iy * latStep;
                const value = this.interpolateIDW(frame, lng, lat);

                const base = this.project(lng, lat, bounds, width, height);
                if (!base) {
                    continue;
                }

                const top = this.transform3D(base.x, base.y, value * 0.85, width, height);
                this.ctx.strokeStyle = this.getGradientColor(value, this.heatmap.gradient, 0.25);
                this.ctx.lineWidth = 1;
                this.ctx.beginPath();
                this.ctx.moveTo(base.x, base.y);
                this.ctx.lineTo(top.x, top.y);
                this.ctx.stroke();
            }
        }
    }

    private interpolateIDW(points: HeatmapDataPoint[], lng: number, lat: number): number {
        let weightSum = 0;
        let valueSum = 0;

        for (const point of points) {
            const dx = point.lng - lng;
            const dy = point.lat - lat;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < 1e-7) {
                return point.value;
            }

            const weight = 1 / Math.pow(distance, 1.8);
            weightSum += weight;
            valueSum += point.value * weight;
        }

        if (weightSum <= 0) {
            return 0;
        }

        return Math.max(0, Math.min(1, valueSum / weightSum));
    }

    private transform3D(x: number, y: number, z: number, width: number, height: number): { x: number; y: number } {
        const cx = width / 2;
        const cy = height / 2;
        const dx = x - cx;
        const dy = y - cy;
        const rad = (this.camera.rotation * Math.PI) / 180;

        const rx = dx * Math.cos(rad) - dy * Math.sin(rad);
        const ry = dx * Math.sin(rad) + dy * Math.cos(rad);

        const tiltScale = Math.cos((this.camera.tilt * Math.PI) / 180);
        const perspective = 1 + (ry / Math.max(height, 1)) * 0.35;

        const tx = cx + rx * this.camera.zoom * perspective;
        const ty = cy + (ry * tiltScale * this.camera.zoom) - z * 160 * this.camera.zoom;

        return { x: tx, y: ty };
    }

    private getSurfaceResolution(pointCount: number): number {
        if (pointCount < 20) return 12;
        if (pointCount < 120) return 16;
        return 20;
    }

    private getBounds(): ViewportBounds | null {
        const view = this.provider.getView?.();
        if (!view) {
            return null;
        }

        if (view.extent && typeof view.extent.xmin === 'number') {
            return {
                minLng: view.extent.xmin,
                minLat: view.extent.ymin,
                maxLng: view.extent.xmax,
                maxLat: view.extent.ymax
            };
        }

        if (typeof view.getBounds === 'function') {
            const bounds = view.getBounds();
            if (bounds?.getSouthWest && bounds?.getNorthEast) {
                const sw = bounds.getSouthWest();
                const ne = bounds.getNorthEast();
                return {
                    minLng: sw.lng,
                    minLat: sw.lat,
                    maxLng: ne.lng,
                    maxLat: ne.lat
                };
            }
        }

        return null;
    }

    private project(lng: number, lat: number, bounds: ViewportBounds, width: number, height: number): { x: number; y: number } | null {
        const lonSpan = bounds.maxLng - bounds.minLng;
        const latSpan = bounds.maxLat - bounds.minLat;
        if (lonSpan <= 0 || latSpan <= 0) {
            return null;
        }

        const x = ((lng - bounds.minLng) / lonSpan) * width;
        const y = height - ((lat - bounds.minLat) / latSpan) * height;
        return { x, y };
    }

    private onMouseMove(event: MouseEvent): void {
        if (!this.heatmap.enabled || this.screenPoints.length === 0) {
            this.hideTooltip();
            return;
        }

        const rect = this.mapContainer.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        const nearest = this.getNearestPoint(x, y, 20);
        if (!nearest) {
            this.hideTooltip();
            return;
        }

        if (this.lastHoverId !== nearest.point.sourceId) {
            this.lastHoverId = nearest.point.sourceId;
        }

        this.tooltip.style.display = 'block';
        this.tooltip.style.left = `${nearest.x + 10}px`;
        this.tooltip.style.top = `${nearest.y + 10}px`;
        this.tooltip.innerHTML = `值: ${(nearest.point.value * 100).toFixed(1)}%<br/>点位: ${nearest.point.sourceId}`;
    }

    private onMouseLeave(): void {
        this.hideTooltip();
    }

    private onClick(event: MouseEvent): void {
        if (!this.heatmap.enabled || this.screenPoints.length === 0) {
            return;
        }

        const rect = this.mapContainer.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        const nearest = this.getNearestPoint(x, y, 26);

        if (!nearest) {
            return;
        }

        const selected = this.panel.querySelector('#mve-selected');
        if (selected) {
            selected.textContent = `选中 ${nearest.point.sourceId} 值 ${(nearest.point.value * 100).toFixed(1)}%`;
        }
    }

    private getNearestPoint(x: number, y: number, threshold: number): ScreenPoint | null {
        let nearest: ScreenPoint | null = null;
        let minDistance = threshold;

        for (const item of this.screenPoints) {
            const dx = item.x - x;
            const dy = item.y - y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            if (distance <= minDistance) {
                minDistance = distance;
                nearest = item;
            }
        }

        return nearest;
    }

    private hideTooltip(): void {
        this.lastHoverId = null;
        this.tooltip.style.display = 'none';
    }

    private exportPNG(): void {
        const link = document.createElement('a');
        link.href = this.canvas.toDataURL('image/png');
        link.download = `heatmap-2_5d-${Date.now()}.png`;
        link.click();
    }

    private exportGeoJSON(): void {
        const geojson = this.dataSource.exportGeoJSON(this.heatmap.timeIndex);
        const blob = new Blob([JSON.stringify(geojson, null, 2)], {
            type: 'application/geo+json'
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `interactive-heatmap-${Date.now()}.geojson`;
        link.click();
        URL.revokeObjectURL(url);
    }

    private getGradientColor(value: number, preset: GradientPreset, alpha: number): string {
        const t = Math.max(0, Math.min(1, value));

        const pick = (r: number, g: number, b: number): string => {
            return `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${Math.max(0, Math.min(1, alpha))})`;
        };

        switch (preset) {
            case 'warm': {
                return pick(255, 80 + 120 * t, 40 + 70 * (1 - t));
            }
            case 'cool': {
                return pick(40 + 100 * (1 - t), 120 + 80 * t, 255);
            }
            case 'viridis': {
                const r = 68 + 185 * t;
                const g = 1 + 230 * t;
                const b = 84 + 40 * (1 - t);
                return pick(r, g, b);
            }
            case 'classic':
            default: {
                const r = 255 * t;
                const g = 255 * (1 - Math.abs(2 * t - 1));
                const b = 255 * (1 - t);
                return pick(r, g, b);
            }
        }
    }
}
