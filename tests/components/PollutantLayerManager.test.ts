import { describe, expect, it } from 'vitest';
import { PollutantLayerManager } from '../../apps/frontend/js/components/PollutantLayerManager';

describe('PollutantLayerManager', () => {
    it('应支持图层顺序调整和图例导出', () => {
        const host = document.createElement('div');
        const manager = new PollutantLayerManager(host, [
            {
                id: 'pm25',
                name: 'PM2.5',
                code: 'PM25',
                domain: 'atmosphere',
                unit: 'ug/m3',
                thresholds: { low: 35, medium: 75, high: 115 },
                colorStops: ['#1', '#2', '#3', '#4']
            },
            {
                id: 'no2',
                name: 'NO2',
                code: 'NO2',
                domain: 'atmosphere',
                unit: 'ug/m3',
                thresholds: { low: 40, medium: 80, high: 120 },
                colorStops: ['#a', '#b', '#c', '#d']
            }
        ]);

        manager.moveLayer('no2', 'up');
        expect(manager.getStates()[0].pollutantId).toBe('no2');

        const legend = manager.exportLegend();
        expect(legend).toContain('PM2.5');
        manager.destroy();
    });
});
