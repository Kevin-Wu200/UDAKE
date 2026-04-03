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

    it('应覆盖空配置比较与清空逻辑', () => {
        const canvasMock = installCanvasMock();
        const container = document.getElementById('root') as HTMLElement;
        const preview = new ParameterImpactPreview(container);

        expect(preview.comparePreviews([])).toEqual({
            fastestId: null,
            bestQualityId: null,
            lowestMemoryId: null
        });

        preview.clear();
        expect(preview.getLatest()).toBeNull();
        expect(container.textContent).toContain('点击“生成预览”查看参数影响对比');

        canvasMock.restore();
    });

    it('预览图生成失败时应降级为无图结果', async () => {
        const canvasMock = installCanvasMock();
        const container = document.getElementById('root') as HTMLElement;
        const preview = new ParameterImpactPreview(container);
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
        const imageSpy = vi.spyOn(
            preview as unknown as { generatePreviewImage: (cfg: KrigingPreviewConfig, m: unknown) => string },
            'generatePreviewImage'
        ).mockImplementation(() => {
            throw new Error('mock image failed');
        });

        const result = await preview.generatePreview(sampleConfig, '失败降级');
        expect(result.imageDataUrl).toBe('');
        expect(warnSpy).toHaveBeenCalledTimes(1);

        imageSpy.mockRestore();
        warnSpy.mockRestore();
        canvasMock.restore();
    });

    it('无最新图或点击失败时导出应安全返回', async () => {
        const canvasMock = installCanvasMock();
        const container = document.getElementById('root') as HTMLElement;
        const preview = new ParameterImpactPreview(container);
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
        const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {
            throw new Error('mock click error');
        });

        const internal = preview as unknown as { exportLatestPreviewImage: () => void };
        internal.exportLatestPreviewImage();
        expect(clickSpy).not.toHaveBeenCalled();

        await preview.generatePreview(sampleConfig, '可导出');
        internal.exportLatestPreviewImage();
        expect(clickSpy).toHaveBeenCalledTimes(1);
        expect(warnSpy).toHaveBeenCalledTimes(1);

        clickSpy.mockRestore();
        warnSpy.mockRestore();
        canvasMock.restore();
    });
});
