export type PollutantDomain = 'atmosphere' | 'water' | 'soil';

export type PollutantLevel = 'low' | 'medium' | 'high' | 'critical';

export type PollutantUnit = 'ug/m3' | 'mg/m3' | 'mg/L' | 'ug/L' | 'ppm' | 'ppb';

export interface PollutantDefinition {
    id: string;
    name: string;
    code: string;
    domain: PollutantDomain;
    unit: PollutantUnit;
    thresholds: {
        low: number;
        medium: number;
        high: number;
    };
    colorStops: string[];
}

export interface PollutantConcentration {
    pollutantId: string;
    value: number;
    unit: PollutantUnit;
    level: PollutantLevel;
}

export interface PollutantLayerState {
    pollutantId: string;
    visible: boolean;
    opacity: number;
    order: number;
}

export interface PollutantLegendItem {
    label: string;
    min: number;
    max: number;
    color: string;
}
