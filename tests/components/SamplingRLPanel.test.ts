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
        expect(host.querySelector('#dl-rl-sampling-point-map')).toBeTruthy();
        expect(host.querySelector('#dl-rl-strategy-trend')).toBeTruthy();
        expect(host.querySelector('#dl-rl-value-contour')).toBeTruthy();
        expect(host.querySelector('#dl-rl-exploration-trajectory')).toBeTruthy();

        panel.destroy();
    });

    it('推荐成功后应渲染第1部分和第2部分可视化组件', async () => {
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
        expect(host.querySelector('#dl-rl-sampling-point-map .dl-rl-map-svg')).toBeTruthy();
        expect(host.querySelector('#dl-rl-strategy-trend .status-message')?.textContent || '').toContain('暂无策略趋势数据');
        expect(host.querySelector('#dl-rl-value-contour .dl-rl-contour-svg')).toBeTruthy();
        const explorationSvg = host.querySelector('#dl-rl-exploration-trajectory .dl-rl-exploration-svg');
        const explorationFallback = host.querySelector('#dl-rl-exploration-trajectory .status-message')?.textContent || '';
        expect(Boolean(explorationSvg) || explorationFallback.includes('暂无探索轨迹数据')).toBe(true);

        panel.destroy();
    });

    it('应兼容后端 recommendation 嵌套结构并渲染策略趋势', async () => {
        const api = createApiMock();
        api.recommendSamplingRL.mockResolvedValue({
            model_name: 'ppo',
            recommendation: {
                recommendations: [
                    { x: 0.2, y: 0.3, score: 0.6, source: 'rl' },
                    { x: 0.8, y: 0.7, score: 0.55, source: 'rule_based' }
                ],
                training_summary: {
                    mean_reward: 0.42,
                    best_reward: 0.61,
                    final_reward: 0.58
                },
                explanations: {
                    policy_decision: {
                        source_contribution: [
                            { source: 'rl', count: 1, ratio: 0.5 },
                            { source: 'rule_based', count: 1, ratio: 0.5 }
                        ]
                    },
                    action_value_visualization: {
                        value_heatmap: [
                            [0.1, 0.3, 0.4],
                            [0.2, 0.6, 0.7]
                        ],
                        action_value_points: [
                            { rank: 1, x: 0.2, y: 0.3, row: 0, col: 1, value: 0.7, source: 'rl' },
                            { rank: 2, x: 0.8, y: 0.7, row: 1, col: 2, value: 0.5, source: 'rule_based' }
                        ]
                    },
                    sampling_effect_evaluation: {
                        summary: {
                            uncertainty_reduction_ratio: 0.21,
                            expected_information_gain: 0.13,
                            sampling_efficiency: 0.08
                        }
                    },
                    sampling_density_analysis: {
                        summary: {
                            coverage_ratio: 0.31
                        }
                    },
                    sampling_region_visualization: {
                        region_intensity_map: [
                            [0.1, 0.4, 0.9],
                            [0.2, 0.6, 0.7]
                        ]
                    }
                }
            },
            optimization: {
                best_strategy: 'hybrid',
                strategy_scores: {
                    rl_only: 0.52,
                    rule_only: 0.49,
                    hybrid: 0.58
                }
            }
        });

        const panel = new SamplingRLPanel(host, api as any);
        (host.querySelector('#dl-rl-recommend') as HTMLButtonElement).click();
        await flushPromises();

        expect(host.querySelector('#dl-rl-strategy-trend .dl-rl-strategy-bars')).toBeTruthy();
        expect(host.querySelectorAll('#dl-rl-strategy-trend .dl-rl-strategy-bar-item').length).toBe(3);
        expect(host.querySelector('#dl-rl-value-contour .dl-rl-contour-svg')).toBeTruthy();
        expect(host.querySelector('#dl-rl-exploration-trajectory .dl-rl-exploration-svg')).toBeTruthy();

        panel.destroy();
    });
});
