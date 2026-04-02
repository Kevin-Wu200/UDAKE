import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ParameterAdjustmentPanel } from '../apps/frontend/js/components/ParameterAdjustmentPanel.js';
import { installCanvasMock } from './canvas-test-utils';

function buildPanelDOM(): void {
    document.body.innerHTML = `
        <div id="panel-host">
            <select id="kriging-template-select"></select>
            <button id="apply-template-btn" type="button">应用模板</button>
            <button id="recommend-template-btn" type="button">智能推荐</button>
            <button id="save-template-btn" type="button">保存模板</button>
            <button id="export-template-btn" type="button">导出模板</button>
            <button id="import-template-btn" type="button">导入模板</button>
            <div id="kriging-warning-panel"></div>

            <select id="kriging-method">
                <option value="ordinary">ordinary</option>
                <option value="universal">universal</option>
                <option value="block">block</option>
            </select>
            <select id="variogram-model">
                <option value="spherical">spherical</option>
                <option value="exponential">exponential</option>
                <option value="gaussian">gaussian</option>
            </select>

            <input id="grid-resolution-slider" type="range" min="50" max="500" step="10" value="100" />
            <input id="grid-resolution" type="number" min="50" max="500" step="10" value="100" />
            <span id="grid-resolution-value"></span>

            <input id="nlags-slider" type="range" min="6" max="24" step="1" value="12" />
            <input id="nlags" type="number" min="6" max="24" step="1" value="12" />
            <span id="nlags-value"></span>

            <input id="nugget-slider" type="range" min="0" max="1" step="0.05" value="0" />
            <input id="nugget" type="number" min="0" max="1" step="0.05" value="0" />
            <span id="nugget-value"></span>

            <input id="sill-slider" type="range" min="0" max="10" step="0.1" value="1" />
            <input id="sill" type="number" min="0" max="10" step="0.1" value="1" />
            <span id="sill-value"></span>

            <input id="range-slider" type="range" min="0" max="100" step="1" value="10" />
            <input id="range" type="number" min="0" max="100" step="1" value="10" />
            <span id="range-value"></span>
            <div id="range-visual-bar"></div>

            <button id="start-kriging-btn" type="button">开始</button>
        </div>
    `;
}

describe('ParameterAdjustmentPanel 可视化扩展', () => {
    beforeEach(() => {
        localStorage.clear();
        buildPanelDOM();
        (ParameterAdjustmentPanel as unknown as { instance?: ParameterAdjustmentPanel }).instance = undefined;
    });

    it('应支持关系图类型切换并持久化', () => {
        const canvasMock = installCanvasMock();
        localStorage.setItem('krigingRelationshipType', 'range-spatial');
        const panel = ParameterAdjustmentPanel.getInstance();

        expect(panel).toBeTruthy();
        const select = document.getElementById('relationship-chart-select') as HTMLSelectElement;
        expect(select.value).toBe('range-spatial');

        select.value = 'grid-performance';
        select.dispatchEvent(new Event('change', { bubbles: true }));

        const title = document.getElementById('parameter-relationship-title') as HTMLElement;
        expect(title.textContent).toContain('grid-performance');
        expect(localStorage.getItem('krigingRelationshipType')).toBe('grid-performance');

        canvasMock.restore();
    });

    it('range-spatial 模式应使用采样空间对角线作为 Y 值', () => {
        const canvasMock = installCanvasMock();
        const panel = ParameterAdjustmentPanel.getInstance();
        panel.setSamplingContext([
            { x: 0, y: 0, value: 1 },
            { x: 30, y: 40, value: 2 }
        ]);

        const select = document.getElementById('relationship-chart-select') as HTMLSelectElement;
        select.value = 'range-spatial';
        select.dispatchEvent(new Event('change', { bubbles: true }));

        panel.setParameter('range', 20);
        const relationshipChart = (panel as unknown as { relationshipChart: { currentPoint: { x: number; y: number } | null } }).relationshipChart;

        expect(relationshipChart.currentPoint?.x).toBe(20);
        expect(relationshipChart.currentPoint?.y).toBe(50);

        canvasMock.restore();
    });

    it('grid-performance 模式应映射网格分辨率到预估耗时并支持点击回写', () => {
        const canvasMock = installCanvasMock();
        const panel = ParameterAdjustmentPanel.getInstance();
        const select = document.getElementById('relationship-chart-select') as HTMLSelectElement;

        select.value = 'grid-performance';
        select.dispatchEvent(new Event('change', { bubbles: true }));

        panel.setParameter('grid-resolution', 300);
        const relationshipChart = (panel as unknown as {
            relationshipChart: {
                currentPoint: { x: number; y: number } | null;
                canvas: HTMLCanvasElement;
                regionHighlight: string;
            };
        }).relationshipChart;

        expect(relationshipChart.currentPoint?.x).toBe(300);
        expect(relationshipChart.currentPoint?.y).toBeGreaterThan(0);

        relationshipChart.canvas.getBoundingClientRect = vi.fn(() => ({ left: 0, top: 0, width: 420, height: 260 } as DOMRect));
        relationshipChart.canvas.dispatchEvent(new MouseEvent('click', { clientX: 320, clientY: 130 }));

        const parameters = panel.getParameters();
        expect(parameters['grid-resolution']).toBeGreaterThanOrEqual(50);
        expect(parameters['grid-resolution']).toBeLessThanOrEqual(500);

        canvasMock.restore();
    });
});
