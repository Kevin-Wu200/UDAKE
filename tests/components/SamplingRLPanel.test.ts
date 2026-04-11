import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SamplingRLPanel } from '../../apps/frontend/js/components/SamplingRLPanel';

function createApiMock() {
    return {
        trainSamplingRL: vi.fn(),
        recommendSamplingRL: vi.fn()
    };
}

async function flushPromises(): Promise<void> {
    await Promise.resolve();
    await Promise.resolve();
}

describe('SamplingRLPanel', () => {
    let host: HTMLDivElement;

    beforeEach(() => {
        host = document.createElement('div');
        document.body.innerHTML = '';
        document.body.appendChild(host);
    });

    it('应渲染四类可视化容器', () => {
        const api = createApiMock();
        const panel = new SamplingRLPanel(host, api as any);

        expect(host.querySelector('#dl-rl-policy-distribution')).toBeTruthy();
        expect(host.querySelector('#dl-rl-action-value-heatmap')).toBeTruthy();
        expect(host.querySelector('#dl-rl-reward-breakdown')).toBeTruthy();
        expect(host.querySelector('#dl-rl-state-action-trajectory')).toBeTruthy();

        panel.destroy();
    });

    it('推荐成功后应渲染策略分布、动作价值热图、奖励分解和轨迹图', async () => {
        const api = createApiMock();
        api.recommendSamplingRL.mockResolvedValue({
            model_name: 'ppo',
            recommendations: [
                { x: 0.1, y: 0.2, score: 0.8, source: 'rl' },
                { x: 0.7, y: 0.6, score: 0.5, source: 'rule_based' }
            ],
            explanations: {
                policy_decision: {
                    source_contribution: [
                        { source: 'rl', count: 1, ratio: 0.5 },
                        { source: 'rule_based', count: 1, ratio: 0.5 }
                    ]
                },
                action_value_visualization: {
                    value_heatmap: [
                        [0.1, 0.3],
                        [0.6, 0.9]
                    ],
                    action_value_points: [
                        { rank: 1, row: 0, col: 1, value: 0.7, source: 'rl' },
                        { rank: 2, row: 1, col: 1, value: 0.5, source: 'rule_based' }
                    ]
                },
                sampling_effect_evaluation: {
                    summary: {
                        uncertainty_reduction_ratio: 0.21,
                        expected_information_gain: 0.13,
                        sampling_efficiency: 0.08
                    }
                },
                sampling_point_recommendation: {
                    summary: {
                        mean_novelty_score: 0.42
                    }
                },
                sampling_density_analysis: {
                    summary: {
                        coverage_ratio: 0.31
                    }
                }
            }
        });

        const panel = new SamplingRLPanel(host, api as any);
        (host.querySelector('#dl-rl-recommend') as HTMLButtonElement).click();
        await flushPromises();

        expect(host.querySelectorAll('#dl-rl-policy-distribution .dl-rl-distribution-item').length).toBe(2);
        expect(host.querySelectorAll('#dl-rl-action-value-heatmap .dl-rl-heatmap-cell').length).toBe(4);
        expect(host.querySelectorAll('#dl-rl-reward-breakdown .dl-rl-reward-item').length).toBe(4);
        expect(host.querySelector('#dl-rl-state-action-trajectory .dl-rl-trajectory-svg')).toBeTruthy();

        panel.destroy();
    });
});
