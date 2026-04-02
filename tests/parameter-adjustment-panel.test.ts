import { beforeEach, describe, expect, it } from 'vitest';
import { ParameterAdjustmentPanel } from '../apps/frontend/js/components/ParameterAdjustmentPanel.js';

function buildPanelDOM(): void {
    document.body.innerHTML = `
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
    `;
}

describe('ParameterAdjustmentPanel', () => {
    beforeEach(() => {
        localStorage.clear();
        buildPanelDOM();
        (ParameterAdjustmentPanel as unknown as { instance?: ParameterAdjustmentPanel }).instance = undefined;
    });

    it('应能应用内置模板并同步方法与模型', () => {
        const panel = ParameterAdjustmentPanel.getInstance();
        const applied = panel.applyTemplate('high-precision');

        expect(applied).toBe(true);
        expect((document.getElementById('grid-resolution') as HTMLInputElement).value).toBe('220');
        expect((document.getElementById('kriging-method') as HTMLSelectElement).value).toBe('universal');
        expect((document.getElementById('variogram-model') as HTMLSelectElement).value).toBe('gaussian');
    });

    it('应根据采样上下文执行智能推荐', () => {
        const panel = ParameterAdjustmentPanel.getInstance();
        panel.setSamplingContext([
            { x: 0, y: 0, value: 1.2 },
            { x: 20, y: 15, value: 2.1 },
            { x: 35, y: 40, value: 2.8 },
            { x: 48, y: 55, value: 3.6 },
            { x: 60, y: 66, value: 4.1 }
        ]);

        (document.getElementById('recommend-template-btn') as HTMLButtonElement).click();

        const params = panel.getParameters();
        expect(params['grid-resolution']).toBeGreaterThanOrEqual(70);
        expect(params['range']).toBeGreaterThan(0);
        expect((document.getElementById('variogram-model') as HTMLSelectElement).value).toMatch(/spherical|gaussian|exponential/);
    });

    it('应在块金值大于基台值时返回校验错误', () => {
        const panel = ParameterAdjustmentPanel.getInstance();
        panel.setParameter('nugget', 0.9);
        panel.setParameter('sill', 0.4);

        const result = panel.validateAll();
        expect(result.valid).toBe(false);
        expect(result.errors.join(' ')).toContain('块金值不能大于基台值');
    });
});
