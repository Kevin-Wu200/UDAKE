import { beforeEach, describe, expect, it, vi } from 'vitest';
import { VariogramChart } from '../apps/frontend/js/components/VariogramChart.js';
import { ChartService } from '../apps/frontend/js/services/ChartService.js';
import { I18nDialog } from '../apps/frontend/js/components/I18nDialog.js';
import { installCanvasMock } from './canvas-test-utils';

function buildChart(): VariogramChart {
    const container = document.createElement('div');
    document.body.appendChild(container);

    return new VariogramChart({
        container,
        empiricalData: [
            { distance: 5, semivariance: 0.1, count: 4 },
            { distance: 10, semivariance: 0.35, count: 7 },
            { distance: 15, semivariance: 0.52, count: 9 }
        ],
        models: [
            { name: 'spherical-基础', type: 'spherical', nugget: 0.08, sill: 1.1, range: 22, fitScore: 0.8 }
        ],
        selectedModel: 'spherical-基础',
        showLegend: true
    });
}

describe('VariogramChart', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });

    it('应能初始化并实时更新拟合曲线', () => {
        const canvasMock = installCanvasMock();
        const chart = buildChart();

        chart.updateFitting({ modelType: 'gaussian', nugget: 0.12, sill: 1.3, range: 30 });
        const selected = chart.getSelectedModel();

        expect(selected).not.toBeNull();
        expect(selected?.type).toBe('gaussian');
        expect(chart.getModels().length).toBeGreaterThan(0);

        chart.destroy();
        canvasMock.restore();
    });

    it('应能计算拟合质量并给出建议', () => {
        const canvasMock = installCanvasMock();
        const chart = buildChart();

        const quality = chart.calculateFitQuality(
            [
                { distance: 5, semivariance: 0.1 },
                { distance: 10, semivariance: 0.3 }
            ],
            [
                { distance: 5, semivariance: 0.11 },
                { distance: 10, semivariance: 0.28 }
            ]
        );

        expect(quality.r2).toBeGreaterThan(-1);
        expect(quality.rmse).toBeGreaterThanOrEqual(0);
        expect(quality.recommendation.length).toBeGreaterThan(0);

        chart.adjustModelParameter('spherical-基础', 'range', 28);
        chart.selectModel('spherical-基础');

        chart.destroy();
        canvasMock.restore();
    });

    it('导出失败时应触发错误提示', async () => {
        const canvasMock = installCanvasMock();
        const chart = buildChart();

        const exportSpy = vi.spyOn(ChartService, 'exportChartAsImage').mockRejectedValue(new Error('export failed'));
        const alertSpy = vi.spyOn(I18nDialog, 'alert').mockImplementation(() => {});

        await chart.exportAsImage('png');

        expect(exportSpy).toHaveBeenCalledTimes(1);
        expect(alertSpy).toHaveBeenCalledTimes(1);

        exportSpy.mockRestore();
        alertSpy.mockRestore();
        chart.destroy();
        canvasMock.restore();
    });
});
