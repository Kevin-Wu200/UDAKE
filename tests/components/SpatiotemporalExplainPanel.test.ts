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

    it('应覆盖状态与方法识别相关分支', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        const panel = new SpatiotemporalExplainPanel(host, api as any);

        expect((panel as any).statusIcon('completed')).toBe('✓');
        expect((panel as any).statusIcon('failed')).toBe('!');
        expect((panel as any).statusIcon('cancelled')).toBe('x');
        expect((panel as any).statusIcon('running')).toBe('>');
        expect((panel as any).statusIcon('retrying')).toBe('~');
        expect((panel as any).statusIcon('queued')).toBe('·');

        expect((panel as any).statusLabel('queued')).toContain('排队');
        expect((panel as any).statusLabel('running')).toContain('执行');
        expect((panel as any).progressPercent({ progress: 0.5 })).toBe(50);
        expect((panel as any).progressPercent({ progress: 150 })).toBe(100);
        expect((panel as any).progressPercent({ progress: -0.1 })).toBe(0);

        expect((panel as any).detectMethodFromTask({ result: { method: 'shap' } })).toBe('shap');
        expect((panel as any).detectMethodFromTask({ result: { lime: {}, shap: {} } })).toBe('hybrid');
        expect((panel as any).detectMethodFromTask({ result: { shap: {} } })).toBe('shap');
        expect((panel as any).detectMethodFromTask({ result: {} })).toBe('lime');

        panel.destroy();
    });

    it('应覆盖特征解析与贡献合并逻辑', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        const panel = new SpatiotemporalExplainPanel(host, api as any);

        const rows = (panel as any).parseImportanceRows([
            { feature: 'f1', value: 0.3 },
            ['f2', -0.2],
            0.1,
            { name: 'bad', value: 'abc' }
        ]);
        expect(rows.length).toBe(3);
        expect(rows[0].name).toBe('f1');

        const merged = (panel as any).mergeContribution([
            { name: 'f1', value: 0.2 },
            { name: 'f1', value: 0.1 },
            { name: 'f2', value: -0.4 }
        ]);
        expect(merged[0].name).toBe('f2');
        expect(merged.find((item: any) => item.name === 'f1')?.value).toBeCloseTo(0.3);

        const contribution = (panel as any).parseContributionRows({
            batch_explanations: [
                { top_contributions: [{ feature: 'f3', value: 0.4 }, { feature_alias: 'f4', shap_value: -0.2 }] }
            ]
        });
        expect(contribution.length).toBe(2);

        panel.destroy();
    });

    it('应覆盖蜂群渲染与依赖表格空态分支', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        const panel = new SpatiotemporalExplainPanel(host, api as any);

        expect((panel as any).renderFeatureBarList([], 'x')).toContain('暂无特征数据');
        expect((panel as any).renderLocalExplanationList([])).toContain('暂无局部解释');
        expect((panel as any).renderDependenceList([])).toContain('暂无依赖图数据');
        expect((panel as any).renderSummaryTable([])).toContain('暂无统计数据');
        expect((panel as any).renderBeeswarmPoints([], 0, 1)).toContain('无数据');

        const beeswarmHtml = (panel as any).renderBeeswarmPoints([
            { feature: 'f1', feature_value: 1, shap_value: 0.12 },
            { feature: 'f2', feature_value: 2, shap_value: -0.11 }
        ], 0.1, 1.2);
        expect(beeswarmHtml).toContain('beeswarm-point');
        expect(beeswarmHtml).toContain('positive');
        expect(beeswarmHtml).toContain('negative');

        panel.destroy();
    });

    it('应覆盖时空视图聚合与安全 JSON 解析分支', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        const panel = new SpatiotemporalExplainPanel(host, api as any);

        const coordsInput = host.querySelector('#dl-explain-coords') as HTMLTextAreaElement;
        coordsInput.value = '{bad';
        const safeCoords = (panel as any).parseJSONInputSafe('dl-explain-coords', []);
        expect(safeCoords).toEqual([]);

        const heatmapFallback = (panel as any).buildHeatmapRows([], { summary: {} });
        expect(heatmapFallback[0].label).toContain('无坐标');

        const heatmap = (panel as any).buildHeatmapRows([[120, 30], [121, 31]], { summary: { top_features: ['a', 'b'] } });
        expect(heatmap.length).toBe(2);
        expect(heatmap[0].intensity).toBeGreaterThan(0);

        const timelineEmpty = (panel as any).buildTimelineRows([]);
        expect(timelineEmpty).toEqual([]);

        const timeline = (panel as any).buildTimelineRows([
            [[1], [2], [3]],
            [[2], [3], [4]]
        ]);
        expect(timeline.length).toBe(3);
        expect(timeline[0].width).toBeGreaterThan(0);

        panel.destroy();
    });

    it('应覆盖刷新空任务与后端校验告警分支', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        api.verifySpatiotemporalExplainBackend.mockResolvedValue({
            broker_ok: false,
            redis_backend_ok: false,
            reason: 'offline'
        });
        const panel = new SpatiotemporalExplainPanel(host, api as any);

        await (panel as any).refreshAllTasks(true);
        expect(host.querySelector('#dl-explain-status')?.textContent).toContain('暂无可刷新任务');

        (host.querySelector('#dl-explain-verify') as HTMLButtonElement).click();
        await flushPromises();
        expect(host.querySelector('#dl-explain-status')?.textContent).toContain('异步后端不可用');

        panel.destroy();
    });

    it('应覆盖数值校验失败分支', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        const panel = new SpatiotemporalExplainPanel(host, api as any);

        (host.querySelector('#dl-explain-horizon') as HTMLInputElement).value = '100';
        (host.querySelector('#dl-explain-submit') as HTMLButtonElement).click();
        await flushPromises();
        expect(host.querySelector('#dl-explain-status')?.textContent).toContain('pred_horizon');

        (host.querySelector('#dl-explain-horizon') as HTMLInputElement).value = '6';
        (host.querySelector('#dl-explain-topk') as HTMLInputElement).value = '30';
        (host.querySelector('#dl-explain-submit') as HTMLButtonElement).click();
        await flushPromises();
        expect(host.querySelector('#dl-explain-status')?.textContent).toContain('top_k');

        (host.querySelector('#dl-explain-topk') as HTMLInputElement).value = '5';
        (host.querySelector('#dl-explain-retries') as HTMLInputElement).value = '-1';
        (host.querySelector('#dl-explain-submit') as HTMLButtonElement).click();
        await flushPromises();
        expect(host.querySelector('#dl-explain-status')?.textContent).toContain('max_retries');

        panel.destroy();
    });

    it('应覆盖国际化回退与销毁分支', async () => {
        I18n.init('en-US');
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        const panel = new SpatiotemporalExplainPanel(host, api as any);

        const translated = (panel as any).t('unknown.key', '回退文本', { count: 3 });
        expect(translated).toContain('回退文本');

        panel.destroy();
        expect(host.innerHTML).toBe('');
    });

    it('应支持导出当前解释结果（JSON/CSV）', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        api.createSpatiotemporalExplainTask.mockResolvedValue({ task_id: 'task-export' });
        api.getSpatiotemporalExplainTask.mockResolvedValue({
            task_id: 'task-export',
            status: 'completed',
            result: {
                method: 'hybrid',
                lime: { visualization: { feature_importance_list: [{ feature: 'f1', value: 0.32 }] } },
                shap: { visualization: { feature_ranking: [{ feature: 'f2', value: 0.18 }] } },
                summary: { n_nodes: 4, seq_len: 6, n_features: 1 }
            }
        });

        const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
        const panel = new SpatiotemporalExplainPanel(host, api as any);
        (host.querySelector('#dl-explain-submit') as HTMLButtonElement).click();
        await flushPromises();

        (host.querySelector('#dl-explain-export') as HTMLButtonElement).click();
        await flushPromises();
        expect(clickSpy).toHaveBeenCalledTimes(1);
        expect(host.querySelector('#dl-explain-status')?.textContent).toContain('导出成功');

        (host.querySelector('#dl-explain-export-format') as HTMLSelectElement).value = 'csv';
        (host.querySelector('[data-result-tab="shap"]') as HTMLButtonElement).click();
        await flushPromises();
        (host.querySelector('#dl-explain-export') as HTMLButtonElement).click();
        await flushPromises();
        expect(clickSpy).toHaveBeenCalledTimes(2);
        expect(host.querySelector('#dl-explain-status')?.textContent).toContain('.csv');

        panel.destroy();
        clickSpy.mockRestore();
    });

    it('应渲染异常分数解释并支持交互筛选', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        api.createSpatiotemporalExplainTask.mockResolvedValue({ task_id: 'task-anomaly' });
        api.getSpatiotemporalExplainTask.mockResolvedValue({
            task_id: 'task-anomaly',
            status: 'completed',
            result: {
                method: 'hybrid',
                lime: {
                    visualization: { feature_importance_list: [{ feature: 'f1', value: 0.3 }] },
                    anomaly_score_explanation: {
                        key_anomaly_nodes: [0, 1, 2],
                        node_scores: { '0': 0.91, '1': 0.56, '2': 0.41 }
                    },
                    anomaly_analysis: {
                        score_summary: [
                            { node_index: 0, deviation: 2.4, percentile: 0.99 },
                            { node_index: 1, deviation: 1.6, percentile: 0.85 },
                            { node_index: 2, deviation: 1.2, percentile: 0.71 }
                        ]
                    }
                },
                shap: {
                    visualization: { feature_ranking: [{ feature: 'f1', value: 0.21 }] },
                    anomaly_score_explanation: { key_anomaly_nodes: [3], node_scores: { '3': 0.66 } },
                    anomaly_analysis: { score_summary: [{ node_index: 3, deviation: 1.3, percentile: 0.78 }] }
                },
                summary: {}
            }
        });

        const panel = new SpatiotemporalExplainPanel(host, api as any);
        (host.querySelector('#dl-explain-submit') as HTMLButtonElement).click();
        await flushPromises();

        expect(host.querySelector('#lime-anomaly-sort')).toBeTruthy();
        expect(host.querySelectorAll('#lime-anomaly-list .anomaly-node-item').length).toBeGreaterThan(0);

        const topN = host.querySelector('#lime-anomaly-topn') as HTMLInputElement;
        topN.value = '1';
        topN.dispatchEvent(new Event('input', { bubbles: true }));
        await flushPromises();
        expect(host.querySelectorAll('#lime-anomaly-list .anomaly-node-item').length).toBe(1);

        (host.querySelector('[data-result-tab="shap"]') as HTMLButtonElement).click();
        await flushPromises();
        expect(host.querySelector('#shap-anomaly-sort')).toBeTruthy();

        panel.destroy();
    });

    it('应渲染异常原因分析并支持分类筛选与详情弹窗', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        api.createSpatiotemporalExplainTask.mockResolvedValue({ task_id: 'task-reason' });
        api.getSpatiotemporalExplainTask.mockResolvedValue({
            task_id: 'task-reason',
            status: 'completed',
            result: {
                method: 'hybrid',
                lime: {
                    anomaly_score_explanation: {
                        anomaly_reasons: [
                            { node_index: 1, reason: '节点1异常由温度突增驱动，重建分量上升。', confidence: 0.91, category: '重建偏差' },
                            { node_index: 2, reason: '节点2异常由判别器输出偏高触发。', confidence: 0.66, category: '判别偏移' }
                        ]
                    },
                    visualization: { feature_importance_list: [] }
                },
                shap: {
                    anomaly_score_explanation: {
                        anomaly_reasons: [
                            { node_index: 3, reason: '节点3异常由嵌入分布漂移触发。', confidence: 0.78, category: '分布漂移' }
                        ]
                    },
                    visualization: { feature_ranking: [] }
                },
                summary: {}
            }
        });

        const panel = new SpatiotemporalExplainPanel(host, api as any);
        (host.querySelector('#dl-explain-submit') as HTMLButtonElement).click();
        await flushPromises();

        expect(host.querySelector('#lime-reason-panel')).toBeTruthy();
        expect(host.querySelectorAll('.reason-item').length).toBeGreaterThan(0);

        const category = host.querySelector('#lime-reason-category') as HTMLSelectElement;
        category.value = '判别偏移';
        category.dispatchEvent(new Event('change', { bubbles: true }));
        await flushPromises();
        expect(host.querySelectorAll('#lime-reason-list .reason-item').length).toBe(1);

        (host.querySelector('#lime-reason-list .reason-detail-btn') as HTMLButtonElement).click();
        await flushPromises();
        expect(host.querySelector('#dl-explain-detail-modal')?.classList.contains('open')).toBe(true);
        expect(host.querySelector('#dl-reason-detail-body')?.textContent).toContain('原因分类');

        (host.querySelector('#dl-reason-detail-close') as HTMLButtonElement).click();
        await flushPromises();
        expect(host.querySelector('#dl-explain-detail-modal')?.classList.contains('open')).toBe(false);

        panel.destroy();
    });

    it('应在对比视图展示异常原因多模型对比并支持TopN调节', async () => {
        const api = createApiMock();
        api.getSpatiotemporalExplainMonitor.mockResolvedValue({});
        api.createSpatiotemporalExplainTask.mockResolvedValue({ task_id: 'task-reason-compare' });
        api.getSpatiotemporalExplainTask.mockResolvedValue({
            task_id: 'task-reason-compare',
            status: 'completed',
            result: {
                method: 'hybrid',
                lime: {
                    anomaly_score_explanation: {
                        anomaly_reasons: [
                            { node_index: 1, reason: '重建误差偏高', confidence: 0.9, category: '重建偏差' },
                            { node_index: 2, reason: '判别器分量偏高', confidence: 0.8, category: '判别偏移' }
                        ]
                    },
                    visualization: { feature_importance_list: [{ feature: 'f1', value: 0.2 }] }
                },
                shap: {
                    anomaly_score_explanation: {
                        anomaly_reasons: [
                            { node_index: 1, reason: '重建误差偏高', confidence: 0.86, category: '重建偏差' },
                            { node_index: 3, reason: '嵌入漂移', confidence: 0.7, category: '表征漂移' }
                        ]
                    },
                    visualization: { feature_ranking: [{ feature: 'f1', value: 0.2 }] }
                },
                summary: {}
            }
        });

        const panel = new SpatiotemporalExplainPanel(host, api as any);
        (host.querySelector('#dl-explain-submit') as HTMLButtonElement).click();
        await flushPromises();
        (host.querySelector('[data-result-tab="compare"]') as HTMLButtonElement).click();
        await flushPromises();

        expect(host.querySelector('#reason-compare-table')).toBeTruthy();
        expect(host.querySelector('#reason-compare-table')?.textContent).toContain('重建偏差');

        const topn = host.querySelector('#reason-compare-topn') as HTMLInputElement;
        topn.value = '1';
        topn.dispatchEvent(new Event('input', { bubbles: true }));
        await flushPromises();
        expect(host.querySelector('#reason-compare-topn-label')?.textContent).toBe('1');

        panel.destroy();
    });
});
