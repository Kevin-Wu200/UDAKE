import { describe, expect, it } from 'vitest';

import { SpatiotemporalVisualizer } from '../js/components/SpatiotemporalVisualizer';

describe('visualizer smoke', () => {
    it('should be constructable', () => {
        const container = document.createElement('div');
        const visualizer = new SpatiotemporalVisualizer(container, { pollutants: [] });
        expect(visualizer).toBeTruthy();
    });
});
