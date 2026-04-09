import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AnomalyDetectionPanel } from '../../apps/frontend/js/components/AnomalyDetectionPanel';

function createApiMock() {
    return {
        predictAnomaly: vi.fn(),
        trainAnomaly: vi.fn()
    };
}

async function flushPromises(): Promise<void> {
    await Promise.resolve();
    await Promise.resolve();
}

describe('AnomalyDetectionPanel 时间序列异常标记', () => {
    let host: HTMLDivElement;

    beforeEach(() => {
        document.body.innerHTML = '';
        host = document.createElement('div');
        document.body.appendChild(host);
    });

    it('应渲染时间序列可视化组件与默认提示', () => {
        const api = createApiMock();
        const panel = new AnomalyDetectionPanel(host, api as any);

        expect(host.querySelector('#dl-anomaly-timeseries')).toBeTruthy();
        expect(host.querySelector('#dl-anomaly-window-analysis')).toBeTruthy();
        expect(host.querySelector('#dl-anomaly-timeseries-summary')?.textContent).toContain('请先执行检测');

        panel.destroy();
    });

    it('执行检测后应展示异常点、异常区域、趋势线和预测曲线', async () => {
        const api = createApiMock();
        api.predictAnomaly.mockResolvedValue({
            anomaly_indices: [2, 3, 5],
            anomaly_scores: [0.02, 0.06, 0.82, 0.88, 0.09, 0.91],
            value_anomalies: {
                anomalies: [
                    { index: 2, value: 1.0, type: 'high' },
                    { index: 3, value: 8.8, type: 'high' },
                    { index: 5, value: 1.05, type: 'high' }
                ]
            }
        });

        const panel = new AnomalyDetectionPanel(host, api as any);
        (host.querySelector('#dl-anomaly-predict') as HTMLButtonElement).click();
        await flushPromises();

        expect(api.predictAnomaly).toHaveBeenCalledTimes(1);
        expect(host.querySelector('.series-svg')).toBeTruthy();
        expect(host.querySelectorAll('.series-anomaly-point').length).toBeGreaterThan(0);
        expect(host.querySelectorAll('.series-anomaly-region').length).toBeGreaterThan(0);
        expect(host.querySelector('.series-trend-line')).toBeTruthy();
        expect(host.querySelector('.series-forecast-line')).toBeTruthy();
        expect(host.querySelector('.dl-window-analysis-table')).toBeTruthy();
        expect(host.querySelector('#dl-anomaly-timeseries-summary')?.textContent).toContain('预测未来');

        panel.destroy();
    });

    it('应兼容后端 prediction 包裹结构并正确绘制异常结果', async () => {
        const api = createApiMock();
        api.predictAnomaly.mockResolvedValue({
            model_name: 'vae',
            prediction: {
                anomaly_indices: [1, 4],
                anomaly_scores: [0.03, 0.79, 0.05, 0.12, 0.86, 0.07],
                value_anomalies: {
                    anomalies: [
                        { index: 1, value: 8.1, type: 'high' },
                        { index: 4, value: 7.9, type: 'high' }
                    ]
                }
            },
            score_preview: [0.03, 0.79, 0.05, 0.12, 0.86, 0.07]
        });

        const panel = new AnomalyDetectionPanel(host, api as any);
        (host.querySelector('#dl-anomaly-predict') as HTMLButtonElement).click();
        await flushPromises();

        expect(api.predictAnomaly).toHaveBeenCalledWith(
            expect.objectContaining({
                model_name: 'vae'
            })
        );
        expect(host.querySelectorAll('.series-anomaly-point').length).toBeGreaterThan(0);
        expect(host.querySelector('#dl-anomaly-timeseries-summary')?.textContent).toContain('异常点');

        panel.destroy();
    });

    it('应兼容 GCAE prediction 包裹结构并正确提取异常分数', async () => {
        const api = createApiMock();
        api.predictAnomaly.mockResolvedValue({
            model_name: 'gcae',
            prediction: {
                anomaly_indices: [0, 5],
                anomaly_scores: [0.91, 0.11, 0.16, 0.21, 0.35, 0.88],
                node_scores: [0.91, 0.11, 0.16, 0.21, 0.35, 0.88],
                value_anomalies: {
                    anomalies: [
                        { index: 0, value: 9.1, type: 'high' },
                        { index: 5, value: 8.8, type: 'high' }
                    ]
                }
            },
            score_preview: [0.91, 0.11, 0.16, 0.21, 0.35, 0.88]
        });

        const panel = new AnomalyDetectionPanel(host, api as any);
        (host.querySelector('#dl-anomaly-model') as HTMLSelectElement).value = 'gcae';
        (host.querySelector('#dl-anomaly-predict') as HTMLButtonElement).click();
        await flushPromises();

        expect(api.predictAnomaly).toHaveBeenCalledWith(
            expect.objectContaining({
                model_name: 'gcae'
            })
        );
        expect(host.querySelectorAll('.series-anomaly-point').length).toBeGreaterThan(0);
        expect(host.querySelector('#dl-anomaly-timeseries-summary')?.textContent).toContain('异常点');

        panel.destroy();
    });

    it('应兼容 GAN prediction 包裹结构并渲染异常结果', async () => {
        const api = createApiMock();
        api.predictAnomaly.mockResolvedValue({
            model_name: 'gan',
            prediction: {
                anomaly_indices: [2, 4],
                anomaly_scores: [0.08, 0.16, 0.89, 0.18, 0.86, 0.14],
                score_components: {
                    discriminator: [0.12, 0.22, 0.92, 0.24, 0.88, 0.19],
                    reconstruction: [0.07, 0.13, 0.83, 0.11, 0.81, 0.09],
                    gradient: [0.05, 0.09, 0.74, 0.08, 0.69, 0.07]
                },
                value_anomalies: {
                    anomalies: [
                        { index: 2, value: 9.0, type: 'high' },
                        { index: 4, value: 8.6, type: 'high' }
                    ]
                }
            },
            score_preview: [0.08, 0.16, 0.89, 0.18, 0.86, 0.14]
        });

        const panel = new AnomalyDetectionPanel(host, api as any);
        (host.querySelector('#dl-anomaly-model') as HTMLSelectElement).value = 'gan';
        (host.querySelector('#dl-anomaly-predict') as HTMLButtonElement).click();
        await flushPromises();

        expect(api.predictAnomaly).toHaveBeenCalledWith(
            expect.objectContaining({
                model_name: 'gan'
            })
        );
        expect(host.querySelectorAll('.series-anomaly-point').length).toBeGreaterThan(0);
        expect(host.querySelector('#dl-anomaly-timeseries-summary')?.textContent).toContain('异常点');

        panel.destroy();
    });

    it('应兼容 Contrastive prediction 包裹结构并渲染异常结果', async () => {
        const api = createApiMock();
        api.predictAnomaly.mockResolvedValue({
            model_name: 'contrastive',
            prediction: {
                anomaly_indices: [1, 3],
                anomaly_scores: [0.09, 0.84, 0.18, 0.87, 0.22, 0.13],
                score_components: {
                    feature_distance: [0.18, 0.86, 0.21, 0.83, 0.29, 0.17],
                    density: [0.11, 0.78, 0.16, 0.74, 0.23, 0.12],
                    nearest_neighbor: [0.08, 0.71, 0.15, 0.69, 0.2, 0.1],
                    bank_similarity: [0.82, 0.13, 0.79, 0.11, 0.76, 0.81]
                },
                value_anomalies: {
                    anomalies: [
                        { index: 1, value: 8.7, type: 'high' },
                        { index: 3, value: 8.9, type: 'high' }
                    ]
                }
            },
            score_preview: [0.09, 0.84, 0.18, 0.87, 0.22, 0.13]
        });

        const panel = new AnomalyDetectionPanel(host, api as any);
        (host.querySelector('#dl-anomaly-model') as HTMLSelectElement).value = 'contrastive';
        (host.querySelector('#dl-anomaly-predict') as HTMLButtonElement).click();
        await flushPromises();

        expect(api.predictAnomaly).toHaveBeenCalledWith(
            expect.objectContaining({
                model_name: 'contrastive'
            })
        );
        expect(host.querySelectorAll('.series-anomaly-point').length).toBeGreaterThan(0);
        expect(host.querySelector('#dl-anomaly-timeseries-summary')?.textContent).toContain('异常点');

        panel.destroy();
    });

    it('应支持严重级别筛选和异常分数数据源切换', async () => {
        const api = createApiMock();
        api.predictAnomaly.mockResolvedValue({
            anomaly_indices: [1, 2, 4],
            anomaly_scores: [0.01, 0.66, 0.93, 0.07, 0.81, 0.05],
            value_anomalies: {
                anomalies: [
                    { index: 1, value: 1.2, type: 'medium' },
                    { index: 2, value: 1.0, type: 'high' },
                    { index: 4, value: 1.3, type: 'medium' }
                ]
            }
        });

        const panel = new AnomalyDetectionPanel(host, api as any);
        (host.querySelector('#dl-anomaly-predict') as HTMLButtonElement).click();
        await flushPromises();

        const beforeCount = host.querySelectorAll('.series-anomaly-point').length;

        const filterSelect = host.querySelector('#dl-anomaly-severity-filter') as HTMLSelectElement;
        filterSelect.value = 'high';
        filterSelect.dispatchEvent(new Event('change', { bubbles: true }));
        await flushPromises();
        const afterCount = host.querySelectorAll('.series-anomaly-point').length;

        const sourceSelect = host.querySelector('#dl-anomaly-series-source') as HTMLSelectElement;
        sourceSelect.value = 'scores';
        const trendSelect = host.querySelector('#dl-anomaly-trend-mode') as HTMLSelectElement;
        trendSelect.value = 'moving_avg';
        (host.querySelector('#dl-anomaly-refresh-timeseries') as HTMLButtonElement).click();
        await flushPromises();

        expect(afterCount).toBeLessThanOrEqual(beforeCount);
        expect(host.querySelector('#dl-anomaly-timeseries-summary')?.textContent).toContain('异常分数序列');
        expect(host.querySelector('#dl-anomaly-timeseries-legend')?.textContent).toContain('移动平均趋势线');

        panel.destroy();
    });

    it('应渲染异常检测结果对比组件', () => {
        const api = createApiMock();
        const panel = new AnomalyDetectionPanel(host, api as any);

        expect(host.querySelector('#dl-anomaly-run-compare')).toBeTruthy();
        expect(host.querySelector('#dl-anomaly-compare-table')).toBeTruthy();
        expect(host.querySelectorAll('.compare-model-checkbox').length).toBe(4);
        expect(host.querySelector('#dl-anomaly-compare-summary')?.textContent).toContain('请选择至少两个模型');

        panel.destroy();
    });

    it('运行模型对比后应展示表格、性能指标与一致性分析', async () => {
        const api = createApiMock();
        api.predictAnomaly.mockImplementation(async (payload: { model_name: string }) => {
            const samples: Record<string, any> = {
                vae: {
                    anomaly_indices: [2, 3],
                    anomaly_scores: [0.1, 0.2, 0.8, 0.9, 0.3, 0.2]
                },
                gcae: {
                    anomaly_indices: [3, 4],
                    anomaly_scores: [0.1, 0.3, 0.4, 0.88, 0.82, 0.2]
                },
                gan: {
                    anomaly_indices: [2, 5],
                    anomaly_scores: [0.2, 0.1, 0.86, 0.3, 0.2, 0.91]
                }
            };
            return samples[payload.model_name];
        });

        const panel = new AnomalyDetectionPanel(host, api as any);
        (host.querySelector('#dl-anomaly-run-compare') as HTMLButtonElement).click();
        await flushPromises();

        expect(api.predictAnomaly).toHaveBeenCalledTimes(3);
        expect(host.querySelector('.dl-compare-table')).toBeTruthy();
        expect(host.querySelector('.compare-metric-card')).toBeTruthy();
        expect(host.querySelector('#dl-anomaly-compare-consistency')?.textContent).toContain('平均Jaccard');
        expect(host.querySelector('#dl-anomaly-compare-summary')?.textContent).toContain('已完成');

        panel.destroy();
    });

    it('应支持模型选择器与自定义对比配置', async () => {
        const api = createApiMock();
        api.predictAnomaly.mockImplementation(async (payload: { model_name: string; threshold_method: string }) => {
            if (payload.model_name === 'gcae') {
                return { anomaly_indices: [1, 4], anomaly_scores: [0.1, 0.8, 0.2, 0.3, 0.85, 0.1] };
            }
            return { anomaly_indices: [2, 4], anomaly_scores: [0.05, 0.1, 0.9, 0.3, 0.87, 0.2] };
        });

        const panel = new AnomalyDetectionPanel(host, api as any);
        const checkboxes = Array.from(host.querySelectorAll('.compare-model-checkbox')) as HTMLInputElement[];
        checkboxes.forEach((box) => {
            box.checked = box.value === 'gcae' || box.value === 'contrastive';
        });
        (host.querySelector('#dl-anomaly-compare-threshold') as HTMLSelectElement).value = 'statistical';
        (host.querySelector('#dl-anomaly-compare-k') as HTMLInputElement).value = '3.2';
        (host.querySelector('#dl-anomaly-compare-consensus-min') as HTMLInputElement).value = '2';
        (host.querySelector('#dl-anomaly-compare-reference') as HTMLSelectElement).value = 'gcae';
        (host.querySelector('#dl-anomaly-compare-focus') as HTMLSelectElement).value = 'anomaly_rate';

        (host.querySelector('#dl-anomaly-run-compare') as HTMLButtonElement).click();
        await flushPromises();

        expect(api.predictAnomaly).toHaveBeenCalledTimes(2);
        expect(api.predictAnomaly).toHaveBeenNthCalledWith(
            1,
            expect.objectContaining({
                model_name: 'gcae',
                threshold_method: 'statistical',
                k: 3.2
            })
        );
        expect(api.predictAnomaly).toHaveBeenNthCalledWith(
            2,
            expect.objectContaining({
                model_name: 'contrastive',
                threshold_method: 'statistical',
                k: 3.2
            })
        );
        expect(host.querySelector('#dl-anomaly-compare-consistency')?.textContent).toContain('参考模型：GCAE');

        panel.destroy();
    });

    it('应支持训练模型、Fusion 训练拦截与错误提示', async () => {
        const api = createApiMock();
        api.trainAnomaly.mockResolvedValue({ model: 'vae', status: 'ok' });

        const panel = new AnomalyDetectionPanel(host, api as any);
        (host.querySelector('#dl-anomaly-train') as HTMLButtonElement).click();
        await flushPromises();

        expect(api.trainAnomaly).toHaveBeenCalledTimes(1);
        expect(api.trainAnomaly).toHaveBeenCalledWith(
            expect.objectContaining({
                model_name: 'vae',
                epochs: 30
            })
        );
        expect(host.querySelector('#dl-anomaly-status')?.textContent).toContain('训练完成');

        (host.querySelector('#dl-anomaly-model') as HTMLSelectElement).value = 'fusion';
        (host.querySelector('#dl-anomaly-train') as HTMLButtonElement).click();
        await flushPromises();
        expect(api.trainAnomaly).toHaveBeenCalledTimes(1);
        expect(host.querySelector('#dl-anomaly-status')?.textContent).toContain('仅支持预测');

        panel.destroy();
    });

    it('导出结果前后应展示不同状态并触发下载', async () => {
        const api = createApiMock();
        api.predictAnomaly.mockResolvedValue({
            anomaly_indices: [1, 3],
            anomaly_scores: [0.1, 0.9, 0.2, 0.88, 0.05, 0.12]
        });

        const createUrlSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock');
        const revokeSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
        const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

        const panel = new AnomalyDetectionPanel(host, api as any);
        (host.querySelector('#dl-anomaly-export') as HTMLButtonElement).click();
        expect(host.querySelector('#dl-anomaly-status')?.textContent).toContain('没有可导出的结果');

        (host.querySelector('#dl-anomaly-predict') as HTMLButtonElement).click();
        await flushPromises();
        (host.querySelector('#dl-anomaly-export') as HTMLButtonElement).click();

        expect(createUrlSpy).toHaveBeenCalledTimes(1);
        expect(clickSpy).toHaveBeenCalledTimes(1);
        expect(revokeSpy).toHaveBeenCalledTimes(1);
        expect(host.querySelector('#dl-anomaly-status')?.textContent).toContain('导出成功');

        panel.destroy();
        createUrlSpy.mockRestore();
        revokeSpy.mockRestore();
        clickSpy.mockRestore();
    });

    it('应支持模型选择全选/清空，且少于两个模型时拒绝对比', async () => {
        const api = createApiMock();
        const panel = new AnomalyDetectionPanel(host, api as any);

        (host.querySelector('#dl-anomaly-compare-clear') as HTMLButtonElement).click();
        const allBoxes = Array.from(host.querySelectorAll('.compare-model-checkbox')) as HTMLInputElement[];
        expect(allBoxes.every((item) => !item.checked)).toBe(true);

        (host.querySelector('#dl-anomaly-run-compare') as HTMLButtonElement).click();
        await flushPromises();
        expect(host.querySelector('#dl-anomaly-compare-summary')?.textContent).toContain('至少选择两个模型');
        expect(api.predictAnomaly).not.toHaveBeenCalled();

        (host.querySelector('#dl-anomaly-compare-select-all') as HTMLButtonElement).click();
        expect(allBoxes.every((item) => item.checked)).toBe(true);

        panel.destroy();
    });

    it('检测与对比失败时应输出错误状态', async () => {
        const api = createApiMock();
        api.predictAnomaly.mockRejectedValueOnce(new Error('predict failed')).mockRejectedValueOnce(new Error('compare failed'));

        const panel = new AnomalyDetectionPanel(host, api as any);
        (host.querySelector('#dl-anomaly-predict') as HTMLButtonElement).click();
        await flushPromises();
        expect(host.querySelector('#dl-anomaly-status')?.textContent).toContain('predict failed');

        const boxes = Array.from(host.querySelectorAll('.compare-model-checkbox')) as HTMLInputElement[];
        boxes.forEach((item, idx) => {
            item.checked = idx < 2;
        });
        (host.querySelector('#dl-anomaly-run-compare') as HTMLButtonElement).click();
        await flushPromises();

        expect(host.querySelector('#dl-anomaly-status')?.textContent).toContain('compare failed');
        expect(host.querySelector('#dl-anomaly-compare-summary')?.textContent).toContain('模型对比失败');

        panel.destroy();
    });
});
