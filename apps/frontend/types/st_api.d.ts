import type {
    STApiResponse,
    STAutoSelectPayload,
    STPredictPayload,
    STSeriesInput,
    STTrainPayload
} from './spatiotemporal';

export interface STIncrementalUpdatePayload {
    model_id: string;
    new_data: STSeriesInput;
}

export interface STCacheWarmupPayload {
    model_id: string;
    payloads: Array<Record<string, unknown>>;
}

export interface STAPIClient {
    train(payload: STTrainPayload): Promise<STApiResponse<Record<string, unknown>>>;
    predict(payload: STPredictPayload): Promise<STApiResponse<Record<string, unknown>>>;
    autoSelect(payload: STAutoSelectPayload): Promise<STApiResponse<Record<string, unknown>>>;
    incrementalUpdate(payload: STIncrementalUpdatePayload): Promise<STApiResponse<Record<string, unknown>>>;
    warmupCache(payload: STCacheWarmupPayload): Promise<STApiResponse<Record<string, unknown>>>;
    getPerformanceMetrics(): Promise<STApiResponse<Record<string, unknown>>>;
}
