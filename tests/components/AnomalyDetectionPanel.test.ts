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
});
