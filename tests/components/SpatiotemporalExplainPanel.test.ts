import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SpatiotemporalExplainPanel } from '../../apps/frontend/js/components/SpatiotemporalExplainPanel';

function createApiMock() {
    return {
        baseURL: '/api',
        request: vi.fn(),
        uploadData: vi.fn(),
        startKriging: vi.fn(),
        getTaskStatus: vi.fn(),
        getPredictionResult: vi.fn(),
        getVarianceResult: vi.fn(),
        getReport: vi.fn(),
        downloadExportFile: vi.fn(),
        clearCache: vi.fn(),
        clearCacheFor: vi.fn(),
        cancelAllRequests: vi.fn(),
        submitInterpolation: vi.fn(),
        getInterpolationResult: vi.fn(),
        generateSamplingPoints: vi.fn(),
        performAnalysis: vi.fn(),
        generateReport: vi.fn(),
        exportData: vi.fn(),
        parseImportFile: vi.fn(),
        importData: vi.fn(),
        health: vi.fn(),
        trainSpatial: vi.fn(),
        predictSpatial: vi.fn(),
        trainAnomaly: vi.fn(),
        predictAnomaly: vi.fn(),
        trainSamplingRL: vi.fn(),
        recommendSamplingRL: vi.fn(),
        trainSpatiotemporal: vi.fn(),
        predictSpatiotemporal: vi.fn(),
        createSpatiotemporalExplainTask: vi.fn(),
        getSpatiotemporalExplainTask: vi.fn(),
        cancelSpatiotemporalExplainTask: vi.fn(),
        deleteSpatiotemporalExplainTask: vi.fn(),
        getSpatiotemporalExplainMonitor: vi.fn(),
        verifySpatiotemporalExplainBackend: vi.fn()
    };
}

describe('SpatiotemporalExplainPanel', () => {
    let host: HTMLDivElement;

    beforeEach(() => {
        host = document.createElement('div');
        document.body.innerHTML = '';
        document.body.appendChild(host);
    });

    it('应支持方法切换并按选择方法提交任务', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({
            queue_size: 0,
            active_tasks: 0,
            success_rate: 1,
            error_rate: 0,
            avg_duration_ms: 10,
            cache_backend: 'memory',
            celery_enabled: false
        });
        api.createSpatiotemporalExplainTask.mockResolvedValue({ task_id: 'task-1' });
        api.getSpatiotemporalExplainTask.mockResolvedValue({
            task_id: 'task-1',
            status: 'completed',
            result: {
                method: 'shap',
                summary: { top_features: [] },
                shap: { visualization: { feature_ranking: [] } }
            }
        });

        const panel = new SpatiotemporalExplainPanel(host, api as any);
        const shapBtn = host.querySelector('[data-method-switch="shap"]') as HTMLButtonElement;
        shapBtn.click();
        (host.querySelector('#dl-explain-submit') as HTMLButtonElement).click();
        await Promise.resolve();
        await Promise.resolve();

        expect(api.createSpatiotemporalExplainTask).toHaveBeenCalledTimes(1);
        const payload = api.createSpatiotemporalExplainTask.mock.calls[0][0];
        expect(payload.method).toBe('shap');
        expect(payload.top_k).toBe(5);
        expect(payload.pred_horizon).toBe(6);

        panel.destroy();
    });

    it('表单非法时应展示错误且不发起提交', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        const panel = new SpatiotemporalExplainPanel(host, api as any);

        const coordsInput = host.querySelector('#dl-explain-coords') as HTMLTextAreaElement;
        coordsInput.value = '[[120.1,30.2]]';
        (host.querySelector('#dl-explain-submit') as HTMLButtonElement).click();
        await Promise.resolve();

        expect(api.createSpatiotemporalExplainTask).not.toHaveBeenCalled();
        expect((host.querySelector('#dl-explain-status') as HTMLElement).textContent).toContain('提交失败');

        panel.destroy();
    });

    it('应支持后端校验和任务取消删除操作', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({
            queue_size: 1,
            active_tasks: 1,
            success_rate: 1,
            error_rate: 0,
            avg_duration_ms: 20,
            cache_backend: 'memory',
            celery_enabled: false
        });
        api.verifySpatiotemporalExplainBackend.mockResolvedValue({
            broker_ok: false,
            redis_backend_ok: true
        });
        api.createSpatiotemporalExplainTask.mockResolvedValue({ task_id: 'task-2' });
        api.getSpatiotemporalExplainTask.mockResolvedValue({
            task_id: 'task-2',
            status: 'running',
            progress: 0.5,
            retry_count: 0,
            max_retries: 1,
            result: { method: 'hybrid', lime: {}, shap: {} }
        });
        api.cancelSpatiotemporalExplainTask.mockResolvedValue({ cancelled: true });
        api.deleteSpatiotemporalExplainTask.mockResolvedValue({ deleted: true });

        const panel = new SpatiotemporalExplainPanel(host, api as any);
        (host.querySelector('#dl-explain-submit') as HTMLButtonElement).click();
        await Promise.resolve();
        await Promise.resolve();

        (host.querySelector('#dl-explain-verify') as HTMLButtonElement).click();
        await Promise.resolve();
        expect((host.querySelector('#dl-explain-status') as HTMLElement).textContent).toContain('校验通过');

        (host.querySelector('[data-task-action="cancel"]') as HTMLButtonElement).click();
        await Promise.resolve();
        expect(api.cancelSpatiotemporalExplainTask).toHaveBeenCalledWith('task-2');

        (host.querySelector('[data-task-action="delete"]') as HTMLButtonElement).click();
        await Promise.resolve();
        expect(api.deleteSpatiotemporalExplainTask).toHaveBeenCalledWith('task-2');

        panel.destroy();
    });
});
