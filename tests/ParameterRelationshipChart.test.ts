import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ParameterRelationshipChart } from '../apps/frontend/js/components/ParameterRelationshipChart.js';
import { installCanvasMock } from './canvas-test-utils';

describe('ParameterRelationshipChart', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });

    it('应完成初始化与 update 渲染', () => {
        const canvasMock = installCanvasMock();
        const container = document.createElement('div');
        container.getBoundingClientRect = vi.fn(() => ({ width: 420, height: 260 } as DOMRect));
        document.body.appendChild(container);

        const chart = new ParameterRelationshipChart(container, {
            axisX: { key: 'nugget', label: 'nugget', min: 0, max: 1 },
            axisY: { key: 'sill', label: 'sill', min: 0, max: 10 },
            constraint: { label: 'nugget ≤ sill', validate: (x, y) => x <= y }
        });

        chart.update(0.2, 0.8);
        const inner = chart as unknown as { currentPoint: { x: number; y: number } | null; historyPoints: Array<{ x: number; y: number }> };
        expect(inner.currentPoint).toEqual({ x: 0.2, y: 0.8 });
        expect(inner.historyPoints).toHaveLength(1);

        chart.update(0.2, 0.8);
        expect(inner.historyPoints).toHaveLength(1);

        canvasMock.restore();
    });

    it('应支持 setAxes / setConstraint / highlightRegion 与历史重置', () => {
        const canvasMock = installCanvasMock();
        const container = document.createElement('div');
        container.getBoundingClientRect = vi.fn(() => ({ width: 400, height: 240 } as DOMRect));
        document.body.appendChild(container);

        const chart = new ParameterRelationshipChart(container, {
            axisX: { key: 'nugget', label: 'nugget', min: 0, max: 1 },
            axisY: { key: 'sill', label: 'sill', min: 0, max: 10 },
            constraint: { label: 'nugget ≤ sill', validate: (x, y) => x <= y }
        });

        chart.update(0.3, 0.6);
        chart.highlightRegion('warning');
        chart.setAxes(
            { key: 'range', label: 'range', min: 0, max: 100 },
            { key: 'spatialRange', label: '空间范围', min: 0, max: 200 }
        );
        chart.setConstraint({ label: '推荐范围', validate: (x, y) => x >= y * 0.15 && x <= y * 0.4 });

        const inner = chart as unknown as { historyPoints: Array<{ x: number; y: number }>; currentPoint: { x: number; y: number } | null };
        expect(inner.historyPoints).toHaveLength(0);
        expect(inner.currentPoint).toBeNull();

        canvasMock.restore();
    });

    it('应支持点击交互回传参数点位', () => {
        const canvasMock = installCanvasMock();
        const container = document.createElement('div');
        container.getBoundingClientRect = vi.fn(() => ({ width: 420, height: 260 } as DOMRect));
        document.body.appendChild(container);

        const onPointSelected = vi.fn();
        const chart = new ParameterRelationshipChart(container, {
            axisX: { key: 'gridResolution', label: '网格分辨率', min: 50, max: 500 },
            axisY: { key: 'estimatedTime', label: '预估耗时(s)', min: 0, max: 30 },
            constraint: { label: '推荐耗时 < 10s', validate: (_x, y) => y < 10 },
            onPointSelected
        });

        const canvas = (chart as unknown as { canvas: HTMLCanvasElement }).canvas;
        canvas.getBoundingClientRect = vi.fn(() => ({ left: 0, top: 0, width: 420, height: 260 } as DOMRect));
        canvas.dispatchEvent(new MouseEvent('click', { clientX: 230, clientY: 120 }));

        expect(onPointSelected).toHaveBeenCalledTimes(1);
        const [x, y] = onPointSelected.mock.calls[0] as [number, number];
        expect(x).toBeGreaterThanOrEqual(50);
        expect(x).toBeLessThanOrEqual(500);
        expect(y).toBeGreaterThanOrEqual(0);
        expect(y).toBeLessThanOrEqual(30);

        canvasMock.restore();
    });

    it('应支持悬浮提示并显示状态文本', () => {
        const canvasMock = installCanvasMock();
        const container = document.createElement('div');
        container.getBoundingClientRect = vi.fn(() => ({ width: 420, height: 260 } as DOMRect));
        document.body.appendChild(container);

        const chart = new ParameterRelationshipChart(container, {
            axisX: { key: 'range', label: 'range', min: 0, max: 100 },
            axisY: { key: 'spatialRange', label: '空间范围', min: 0, max: 200 },
            constraint: { label: '推荐范围', validate: (x, y) => x >= y * 0.15 && x <= y * 0.4 },
            statusResolver: (x, y) => (x >= y * 0.15 && x <= y * 0.4 ? 'valid' : 'warning')
        });
        chart.update(10, 180);

        const canvas = (chart as unknown as { canvas: HTMLCanvasElement }).canvas;
        canvas.getBoundingClientRect = vi.fn(() => ({ left: 0, top: 0, width: 420, height: 260 } as DOMRect));
        canvas.dispatchEvent(new MouseEvent('mousemove', { clientX: 220, clientY: 120 }));

        const tooltip = container.querySelector('.parameter-relationship-tooltip') as HTMLDivElement;
        expect(tooltip.style.display).toBe('block');
        expect(tooltip.innerHTML).toContain('状态:');

        canvas.dispatchEvent(new MouseEvent('mouseleave'));
        expect(tooltip.style.display).toBe('none');

        canvasMock.restore();
    });
});
