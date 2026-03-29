import { beforeEach, describe, expect, it, vi } from 'vitest';
import wizardConfig from '../configs/workflow-wizards.json';
import { SmartWizardEngine } from '../apps/frontend/js/components/SmartWizardEngine.js';

describe('SmartWizardEngine', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <div id="app"></div>
            <input id="file-input" type="file" />
            <div id="export-panel" style="display:none"></div>
        `;
        localStorage.clear();
    });

    it('应能启动向导并渲染步骤', () => {
        const engine = new SmartWizardEngine(wizardConfig as any);
        engine.mount(document.body);

        const started = engine.start('data-import');
        expect(started).toBe(true);

        const modal = document.querySelector('.smart-wizard-modal');
        expect(modal).toBeTruthy();
        expect(modal?.textContent).toContain('数据导入向导');
    });

    it('应在完成时派发完成事件', () => {
        const engine = new SmartWizardEngine(wizardConfig as any);
        engine.mount(document.body);
        engine.start('data-import');

        const completed = vi.fn();
        document.addEventListener('wizard-completed', completed);

        const internal = engine as any;
        internal.next();
        internal.next();
        internal.complete();

        expect(completed).toHaveBeenCalledTimes(1);
        const detail = completed.mock.calls[0][0].detail;
        expect(detail.wizardId).toBe('data-import');
    });

    it('应支持导入自定义向导', () => {
        const engine = new SmartWizardEngine(wizardConfig as any);
        engine.mount(document.body);

        const ok = engine.importCustomWizard(JSON.stringify({
            id: 'custom-flow',
            title: '自定义流程',
            description: '用于测试',
            steps: [
                {
                    id: 'step-1',
                    title: '步骤1',
                    description: '测试步骤',
                    fields: [
                        { id: 'name', label: '名称', type: 'text', required: true }
                    ]
                }
            ]
        }));

        expect(ok).toBe(true);
        const list = engine.getWizardList();
        expect(list.some((item) => item.id === 'custom-flow')).toBe(true);
    });
});
