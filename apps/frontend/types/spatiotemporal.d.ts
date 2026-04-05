import type { PollutantConcentration } from './pollutant';
import type { VisualizationFrame } from './visualization';

export interface STSeriesInput {
    x: number[];
    y: number[];
    z: number[];
    t: number[];
    value: number[];
}

export interface STTrainPayload {
    data: STSeriesInput;
    model_type?: 'separated' | 'product' | 'nonseparable';
    options?: Record<string, unknown>;
}

export interface STPredictPayload {
    model_id: string;
    target_positions: {
        x: number[];
        y: number[];
        z: number[];
    };
    target_times: number[];
    prediction_days?: number;
    options?: Record<string, unknown>;
}

export interface STAutoSelectPayload {
    historical_data: STSeriesInput;
    new_samples: STSeriesInput;
    prediction_results?: Record<string, Array<Record<string, number>>>;
    options?: Record<string, unknown>;
}

export interface STApiResponse<T = unknown> {
    success: boolean;
    message: string;
    data: T;
}

export interface STPredictionSnapshot {
    timestamp: string;
    location: {
        x: number;
        y: number;
        z: number;
    };
    concentrations: PollutantConcentration[];
    uncertainty: number;
    decayRate: {
        day1: number;
        day7: number;
        day15: number;
    };
}

export interface STVisualizationBundle {
    timeline: string[];
    frames: VisualizationFrame[];
    snapshots: STPredictionSnapshot[];
}
