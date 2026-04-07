import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SpatiotemporalExplainPanel } from '../../apps/frontend/js/components/SpatiotemporalExplainPanel';
import { I18n } from '../../apps/frontend/js/utils/I18n';

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

async function flushPromises(): Promise<void> {
    await Promise.resolve();
    await Promise.resolve();
}

describe('SpatiotemporalExplainPanel', () => {
    let host: HTMLDivElement;

    beforeEach(() => {
        host = document.createElement('div');
        document.body.innerHTML = '';
        document.body.appendChild(host);
        window.localStorage.clear();
        I18n.init('zh-CN');
    });

    it('应完成基础渲染并显示默认空结果态', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});

        const panel = new SpatiotemporalExplainPanel(host, api as any);
        await flushPromises();

        expect(host.querySelector('.explain-panel h4')?.textContent).toContain('模型可解释性增强面板');
        expect(host.querySelector('#dl-explain-result')?.textContent).toContain('暂无结果');
        expect(api.getSpatiotemporalExplainMonitor).toHaveBeenCalledTimes(1);

        panel.destroy();
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
        await flushPromises();

        expect(api.createSpatiotemporalExplainTask).toHaveBeenCalledTimes(1);
        const payload = api.createSpatiotemporalExplainTask.mock.calls[0][0];
        expect(payload.method).toBe('shap');
        expect(payload.top_k).toBe(5);
        expect(payload.pred_horizon).toBe(6);
        expect(host.querySelector('#dl-explain-status')?.textContent).toContain('任务提交成功');

        panel.destroy();
    });

    it('应支持键盘快捷键提交与刷新', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        api.createSpatiotemporalExplainTask.mockResolvedValue({ task_id: 'task-kb' });
        api.getSpatiotemporalExplainTask.mockResolvedValue({
            task_id: 'task-kb',
            status: 'running',
            progress: 0.2,
            result: { method: 'lime', lime: {} }
        });

        const panel = new SpatiotemporalExplainPanel(host, api as any);
        host.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true, bubbles: true }));
        await flushPromises();

        expect(api.createSpatiotemporalExplainTask).toHaveBeenCalledTimes(1);

        host.dispatchEvent(new KeyboardEvent('keydown', { key: 'r', ctrlKey: true, bubbles: true }));
        await flushPromises();
        expect(api.getSpatiotemporalExplainTask).toHaveBeenCalledWith('task-kb');

        panel.destroy();
    });

    it('表单非法时应展示错误且不发起提交', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        const panel = new SpatiotemporalExplainPanel(host, api as any);

        const coordsInput = host.querySelector('#dl-explain-coords') as HTMLTextAreaElement;
        coordsInput.value = '[[120.1,30.2]]';
        (host.querySelector('#dl-explain-submit') as HTMLButtonElement).click();
        await flushPromises();

        expect(api.createSpatiotemporalExplainTask).not.toHaveBeenCalled();
        expect((host.querySelector('#dl-explain-status') as HTMLElement).textContent).toContain('提交失败');

        panel.destroy();
    });

    it('JSON 非法时应触发错误处理', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        const panel = new SpatiotemporalExplainPanel(host, api as any);

        const seriesInput = host.querySelector('#dl-explain-series') as HTMLTextAreaElement;
        seriesInput.value = '{bad json}';
        (host.querySelector('#dl-explain-submit') as HTMLButtonElement).click();
        await flushPromises();

        expect(api.createSpatiotemporalExplainTask).not.toHaveBeenCalled();
        expect(host.querySelector('#dl-explain-status')?.textContent).toContain('不是合法 JSON');

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
        await flushPromises();

        (host.querySelector('#dl-explain-verify') as HTMLButtonElement).click();
        await flushPromises();
        expect((host.querySelector('#dl-explain-status') as HTMLElement).textContent).toContain('校验通过');

        (host.querySelector('[data-task-action="cancel"]') as HTMLButtonElement).click();
        await flushPromises();
        expect(api.cancelSpatiotemporalExplainTask).toHaveBeenCalledWith('task-2');

        (host.querySelector('[data-task-action="delete"]') as HTMLButtonElement).click();
        await flushPromises();
        expect(api.deleteSpatiotemporalExplainTask).toHaveBeenCalledWith('task-2');

        panel.destroy();
    });

    it('提交接口报错时应显示错误消息', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        api.createSpatiotemporalExplainTask.mockRejectedValue(new Error('backend down'));

        const panel = new SpatiotemporalExplainPanel(host, api as any);
        (host.querySelector('#dl-explain-submit') as HTMLButtonElement).click();
        await flushPromises();

        expect(host.querySelector('#dl-explain-status')?.textContent).toContain('backend down');
        panel.destroy();
    });

    it('应支持任务列表增量渲染和手动加载更多', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        const panel = new SpatiotemporalExplainPanel(host, api as any);

        const tasks = Array.from({ length: 45 }).map((_, idx) => ({
            task_id: `task-${idx}`,
            status: 'running',
            progress: 0.1,
            retry_count: 0,
            max_retries: 1,
            created_at: '2026-04-06T10:00:00Z',
            updated_at: '2026-04-06T10:00:00Z',
            result: { method: 'lime' }
        }));

        (panel as any).tasks = tasks;
        (panel as any).renderedTaskCount = 20;
        (panel as any).renderTaskList();

        const taskItemsBefore = host.querySelectorAll('.explain-task-item');
        expect(taskItemsBefore.length).toBe(20);
        expect(host.textContent).toContain('加载更多');

        (host.querySelector('[data-task-action="load-more"]') as HTMLButtonElement).click();
        const taskItemsAfter = host.querySelectorAll('.explain-task-item');
        expect(taskItemsAfter.length).toBe(45);

        panel.destroy();
    });

    it('应支持暗黑模式切换并持久化用户偏好', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        const panel = new SpatiotemporalExplainPanel(host, api as any);

        const toggle = host.querySelector('#dl-explain-theme-toggle') as HTMLButtonElement;
        toggle.click();
        await flushPromises();

        expect(host.querySelector('.explain-panel')?.classList.contains('theme-dark')).toBe(true);
        expect(window.localStorage.getItem('dl-explain-theme')).toBe('dark');
        expect(toggle.getAttribute('aria-pressed')).toBe('true');

        panel.destroy();
    });

    it('应支持左右方向键切换方法与结果标签', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        const panel = new SpatiotemporalExplainPanel(host, api as any);

        const methodHybrid = host.querySelector('[data-method-switch="hybrid"]') as HTMLButtonElement;
        methodHybrid.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true }));
        expect((panel as any).selectedMethod).toBe('shap');

        const tabLime = host.querySelector('[data-result-tab="lime"]') as HTMLButtonElement;
        tabLime.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
        expect((panel as any).activeTab).toBe('shap');

        panel.destroy();
    });

    it('监控查询应命中短时缓存', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({ queue_size: 3 });
        const panel = new SpatiotemporalExplainPanel(host, api as any);
        await flushPromises();

        await (panel as any).refreshMonitor();
        await (panel as any).refreshMonitor();

        expect(api.getSpatiotemporalExplainMonitor).toHaveBeenCalledTimes(1);
        panel.destroy();
    });

    it('完成任务在LIME/SHAP视图下应渲染图表容器', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        api.createSpatiotemporalExplainTask.mockResolvedValue({ task_id: 'task-chart' });
        api.getSpatiotemporalExplainTask.mockResolvedValue({
            task_id: 'task-chart',
            status: 'completed',
            result: {
                method: 'hybrid',
                lime: { visualization: { feature_importance_list: [{ feature: 'f1', value: 0.3 }] } },
                shap: {
                    visualization: {
                        waterfall_list: [{ feature: 'f1', value: 0.2 }],
                        feature_ranking: [{ feature: 'f1', value: 0.2 }],
                        beeswarm_data: [{ feature: 'f1', feature_value: 1.2, shap_value: 0.1 }]
                    }
                },
                summary: {}
            }
        });

        const panel = new SpatiotemporalExplainPanel(host, api as any);
        (host.querySelector('#dl-explain-submit') as HTMLButtonElement).click();
        await flushPromises();

        expect(host.querySelector('#chart-lime-feature')).toBeTruthy();

        (host.querySelector('[data-result-tab="shap"]') as HTMLButtonElement).click();
        await flushPromises();

        expect(host.querySelector('#chart-shap-waterfall')).toBeTruthy();
        expect(host.querySelector('#chart-shap-beeswarm')).toBeTruthy();
        expect(host.querySelector('#chart-shap-ranking')).toBeTruthy();

        panel.destroy();
    });
});
