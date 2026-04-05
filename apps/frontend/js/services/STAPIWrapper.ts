import type {
    STApiResponse,
    STAutoSelectPayload,
    STPredictPayload,
    STTrainPayload
} from '../../types/spatiotemporal';
import {
    SpatiotemporalService,
    type STCacheWarmupPayload,
    type STIncrementalUpdatePayload
} from './SpatiotemporalService';

export class STAPIWrapper {
    private readonly service: SpatiotemporalService;

    constructor(baseURL: string = '/api/spatiotemporal') {
        this.service = new SpatiotemporalService(baseURL);
    }

    train(payload: STTrainPayload): Promise<STApiResponse<Record<string, unknown>>> {
        return this.service.train(payload);
    }

    predict(payload: STPredictPayload): Promise<STApiResponse<Record<string, unknown>>> {
        return this.service.predict(payload);
    }

    autoSelect(payload: STAutoSelectPayload): Promise<STApiResponse<Record<string, unknown>>> {
        return this.service.autoSelect(payload);
    }

    incrementalUpdate(payload: STIncrementalUpdatePayload): Promise<STApiResponse<Record<string, unknown>>> {
        return this.service.incrementalUpdate(payload);
    }

    warmupCache(payload: STCacheWarmupPayload): Promise<STApiResponse<Record<string, unknown>>> {
        return this.service.warmupCache(payload);
    }

    getPerformanceMetrics(): Promise<STApiResponse<Record<string, unknown>>> {
        return this.service.getPerformanceMetrics();
    }
}
