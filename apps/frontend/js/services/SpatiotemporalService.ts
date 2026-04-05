import type {
    STApiResponse,
    STAutoSelectPayload,
    STPredictPayload,
    STSeriesInput,
    STTrainPayload
} from '../../types/spatiotemporal';

export interface STIncrementalUpdatePayload {
    model_id: string;
    new_data: STSeriesInput;
}

export interface STCacheWarmupPayload {
    model_id: string;
    payloads: Array<Record<string, unknown>>;
}

export class SpatiotemporalService {
    private readonly baseURL: string;

    constructor(baseURL: string = '/api/spatiotemporal') {
        this.baseURL = baseURL;
    }

    private async request<T>(path: string, init: RequestInit): Promise<STApiResponse<T>> {
        const response = await fetch(`${this.baseURL}${path}`, {
            headers: {
                'Content-Type': 'application/json'
            },
            ...init
        });

        const data = await response.json() as STApiResponse<T>;
        if (!response.ok || !data.success) {
            throw new Error(data.message || `请求失败: ${response.status}`);
        }
        return data;
    }

    train(payload: STTrainPayload): Promise<STApiResponse<Record<string, unknown>>> {
        return this.request<Record<string, unknown>>('/train', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    predict(payload: STPredictPayload): Promise<STApiResponse<Record<string, unknown>>> {
        return this.request<Record<string, unknown>>('/predict', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    autoSelect(payload: STAutoSelectPayload): Promise<STApiResponse<Record<string, unknown>>> {
        return this.request<Record<string, unknown>>('/auto-select', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    incrementalUpdate(payload: STIncrementalUpdatePayload): Promise<STApiResponse<Record<string, unknown>>> {
        return this.request<Record<string, unknown>>('/incremental-update', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    warmupCache(payload: STCacheWarmupPayload): Promise<STApiResponse<Record<string, unknown>>> {
        return this.request<Record<string, unknown>>('/cache/warmup', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    getPerformanceMetrics(): Promise<STApiResponse<Record<string, unknown>>> {
        return this.request<Record<string, unknown>>('/performance/metrics', {
            method: 'GET'
        });
    }
}
