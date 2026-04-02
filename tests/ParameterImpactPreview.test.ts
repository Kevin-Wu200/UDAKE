import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ParameterImpactPreview, type KrigingPreviewConfig } from '../apps/frontend/js/components/ParameterImpactPreview.js';
import { installCanvasMock } from './canvas-test-utils';

const sampleConfig: KrigingPreviewConfig = {
    'grid-resolution': 120,
    nlags: 12,
    nugget: 0.1,
    sill: 1,
    range: 30,
    method: 'ordinary',
    variogramModel: 'spherical'
};

describe('ParameterImpactPreview', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div id="root"></div>';
    });

    it('应完成初始化并生成预览数据', async () => {
        const canvasMock = installCanvasMock();
        const container = document.getElementById('root') as HTMLElement;
        const preview = new ParameterImpactPreview(container);

        const result = await preview.generatePreview(sampleConfig, '当前配置');
        expect(result.metrics.estimatedTimeMs).toBeGreaterThan(0);
        expect(result.metrics.estimatedMemoryMb).toBeGreaterThan(0);
        expect(result.metrics.qualityScore).toBeGreaterThanOrEqual(0);
        expect(result.imageDataUrl).toContain('data:image/png');
        expect(preview.getLatest()?.id).toBe(result.id);

        canvasMock.restore();
    });

    it('应支持 comparePreviews 与指标估算', () => {
        const canvasMock = installCanvasMock();
        const container = document.getElementById('root') as HTMLElement;
        const preview = new ParameterImpactPreview(container);

        const comparison = preview.comparePreviews([
            sampleConfig,
            { ...sampleConfig, 'grid-resolution': 260, range: 45 },
            { ...sampleConfig, nugget: 0.3, sill: 1.5 }
        ]);

        expect(comparison.fastestId).toBeTruthy();
        expect(comparison.bestQualityId).toBeTruthy();
        expect(comparison.lowestMemoryId).toBeTruthy();

        const metrics = (preview as unknown as { estimateMetrics: (cfg: KrigingPreviewConfig) => { estimatedTimeMs: number } }).estimateMetrics(sampleConfig);
        expect(metrics.estimatedTimeMs).toBeGreaterThan(0);

        canvasMock.restore();
    });

    it('应支持导出与缓存上限控制', async () => {
        const canvasMock = installCanvasMock();
        const container = document.getElementById('root') as HTMLElement;
        const preview = new ParameterImpactPreview(container);
        const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

        for (let i = 0; i < 8; i++) {
            await preview.generatePreview({ ...sampleConfig, nlags: sampleConfig.nlags + i }, `配置${i}`);
        }

        const internal = preview as unknown as { previewResults: Map<string, unknown>; exportLatestPreviewImage: () => void };
        expect(internal.previewResults.size).toBe(6);

        internal.exportLatestPreviewImage();
        expect(clickSpy).toHaveBeenCalledTimes(1);

        clickSpy.mockRestore();
        canvasMock.restore();
    });
});
