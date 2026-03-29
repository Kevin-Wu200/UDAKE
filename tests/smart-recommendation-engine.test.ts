import { beforeEach, describe, expect, it } from 'vitest';
import { SmartRecommendationEngine } from '../apps/frontend/js/components/SmartRecommendationEngine.js';

const actions = [
    { id: 'import-data', label: '导入数据', command: 'import-data' },
    { id: 'wizard-import-data', label: '导入向导', command: 'wizard-start:data-import' },
    { id: 'start-kriging', label: '开始插值', command: 'start-kriging' },
    { id: 'wizard-export', label: '导出向导', command: 'wizard-start:result-export' },
    { id: 'export-geojson', label: '导出GeoJSON', command: 'export-geojson' },
    { id: 'show-guide', label: '新手引导', command: 'show-guide' },
    { id: 'wizard-center', label: '向导中心', command: 'open-wizard-center' }
];

describe('SmartRecommendationEngine', () => {
    beforeEach(() => {
        localStorage.clear();
        document.body.innerHTML = `
            <input id="file-input" type="file" />
            <button id="start-kriging-btn"></button>
            <div id="export-panel" style="display:none"></div>
            <div id="mount"></div>
        `;
    });

    it('应能记录行为并输出推荐', () => {
        const engine = new SmartRecommendationEngine(actions);
        engine.mount(document.getElementById('mount') as HTMLElement);

        engine.recordAction('import-data', ['new-user']);
        engine.recordAction('wizard-import-data', ['new-user']);

        const result = engine.getRecommendations(['new-user'], 3);
        expect(result.length).toBeGreaterThan(0);
        expect(result[0].actionId).toBeTruthy();
    });

    it('推荐准确率评估应达到70%以上', () => {
        const now = Date.now();
        const engine = new SmartRecommendationEngine(actions);

        const accuracy = engine.evaluateAccuracy([
            {
                history: [
                    { actionId: 'import-data', timestamp: now - 10000, context: ['new-user'] },
                    { actionId: 'wizard-import-data', timestamp: now - 5000, context: ['new-user'] }
                ],
                context: ['new-user'],
                expected: 'wizard-import-data'
            },
            {
                history: [
                    { actionId: 'start-kriging', timestamp: now - 20000, context: ['has-file', 'can-start-kriging'] },
                    { actionId: 'start-kriging', timestamp: now - 1000, context: ['has-file', 'can-start-kriging'] }
                ],
                context: ['has-file', 'can-start-kriging'],
                expected: 'start-kriging'
            },
            {
                history: [
                    { actionId: 'wizard-export', timestamp: now - 7000, context: ['can-export'] },
                    { actionId: 'export-geojson', timestamp: now - 3000, context: ['can-export'] }
                ],
                context: ['can-export'],
                expected: 'export-geojson'
            },
            {
                history: [
                    { actionId: 'show-guide', timestamp: now - 8000, context: ['new-user'] },
                    { actionId: 'wizard-import-data', timestamp: now - 2000, context: ['new-user'] }
                ],
                context: ['new-user'],
                expected: 'show-guide'
            }
        ]);

        expect(accuracy).toBeGreaterThanOrEqual(0.7);
    });
});
