import { describe, expect, it } from 'vitest';
import { SpatiotemporalVisualizer } from '../../apps/frontend/js/components/SpatiotemporalVisualizer';

describe('SpatiotemporalVisualizer', () => {
    it('应加载数据并支持区域统计与导出', async () => {
        const host = document.createElement('div');
        const visualizer = new SpatiotemporalVisualizer(host, {
            pollutants: [
                {
                    id: 'pm25',
                    name: 'PM2.5',
                    code: 'PM25',
                    domain: 'atmosphere',
                    unit: 'ug/m3',
                    thresholds: { low: 35, medium: 75, high: 115 },
                    colorStops: ['#1', '#2', '#3', '#4']
                }
            ]
        });

        await visualizer.loadSnapshots([
            {
                timestamp: '2026-01-01T00:00:00Z',
                location: { x: 5, y: 5, z: 0 },
                concentrations: [{ pollutantId: 'pm25', value: 30, unit: 'ug/m3', level: 'low' }],
                uncertainty: 0.1,
                decayRate: { day1: 5, day7: 15, day15: 30 }
            }
        ]);

        const selected = visualizer.selectRegion({ minX: 0, minY: 0, maxX: 10, maxY: 10 });
        expect(selected.length).toBe(1);
        expect(visualizer.exportSelection(selected)).toContain('pm25');
        visualizer.destroy();
    });
});
