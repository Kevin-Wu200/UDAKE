import { describe, expect, it } from 'vitest';

import { SpatiotemporalService } from '../js/services/SpatiotemporalService';

describe('spatiotemporal service smoke', () => {
    it('should expose methods', () => {
        const service = new SpatiotemporalService();
        expect(typeof service.train).toBe('function');
        expect(typeof service.predict).toBe('function');
    });
});
