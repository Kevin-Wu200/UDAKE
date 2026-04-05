import type { PollutantConcentration, PollutantLegendItem } from './pollutant';

export interface STPoint3D {
    x: number;
    y: number;
    z: number;
}

export interface TimeFrameDataPoint {
    id: string;
    position: STPoint3D;
    concentrations: PollutantConcentration[];
    uncertainty: number;
}

export interface TimeFrameData {
    timestamp: string;
    points: TimeFrameDataPoint[];
}

export interface FlowVector {
    from: STPoint3D;
    to: STPoint3D;
    magnitude: number;
}

export interface ViewSnapshot {
    heading: number;
    tilt: number;
    zoom: number;
    center: {
        x: number;
        y: number;
    };
}

export interface VisualizationLayerConfig {
    id: string;
    name: string;
    visible: boolean;
    opacity: number;
    order: number;
    legend: PollutantLegendItem[];
}

export interface VisualizationFrame {
    timestamp: string;
    heatmap: TimeFrameDataPoint[];
    samples: TimeFrameDataPoint[];
    flowVectors: FlowVector[];
}

export interface VisualizationRenderStats {
    renderedPoints: number;
    culledPoints: number;
    lodReductionRatio: number;
    frameTimeMs: number;
}

export interface HoverInfo {
    position: STPoint3D;
    timestamp: string;
    concentrations: PollutantConcentration[];
    uncertainty: number;
}
