import { describe, expect, it } from 'vitest';

import { PollutantLayerManager } from '../js/components/PollutantLayerManager';

describe('layer manager smoke', () => {
    it('should be constructable', () => {
        const container = document.createElement('div');
        const manager = new PollutantLayerManager(container, []);
        expect(manager).toBeTruthy();
    });
});
