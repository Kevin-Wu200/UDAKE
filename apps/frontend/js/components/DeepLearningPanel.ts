import type { IAPIService } from '../../types/api';
import { SpatialInterpolationPanel } from './SpatialInterpolationPanel.js';
import { AnomalyDetectionPanel } from './AnomalyDetectionPanel.js';
import { SamplingRLPanel } from './SamplingRLPanel.js';
import { SpatiotemporalPredictionPanel } from './SpatiotemporalPredictionPanel.js';

/**
 * 深度学习总面板
 */
export class DeepLearningPanel {
    private section: HTMLElement;
    private container: HTMLElement;
    private apiService: IAPIService;
    private isExpanded: boolean = false;

    private spatialPanel: SpatialInterpolationPanel | null = null;
    private anomalyPanel: AnomalyDetectionPanel | null = null;
    private samplingRLPanel: SamplingRLPanel | null = null;
    private spatiotemporalPanel: SpatiotemporalPredictionPanel | null = null;

    constructor(sectionId: string, containerId: string, apiService: IAPIService) {
        const section = document.getElementById(sectionId);
        const container = document.getElementById(containerId);

        if (!section || !container) {
            throw new Error('深度学习面板容器不存在');
        }

        this.section = section;
        this.container = container;
        this.apiService = apiService;

        this.render();
        this.bindEvents();
        this.initializeSubPanels();
        void this.checkHealth();
    }

    private render(): void {
        this.container.innerHTML = `
            <div class="deep-learning-panel">
                <div class="dl-overview">
                    <div class="dl-overview-left">
                        <span class="dl-status-dot" id="dl-status-dot"></span>
                        <span id="dl-service-status">深度学习服务状态：检测中...</span>
                    </div>
                    <button id="dl-health-check-btn" class="btn btn-secondary btn-sm">刷新状态</button>
                </div>
                <div id="dl-health-detail" class="dl-health-detail"></div>

                <div class="dl-module-list">
                    <section class="dl-module" id="dl-spatial-section"></section>
                    <section class="dl-module" id="dl-anomaly-section"></section>
                    <section class="dl-module" id="dl-sampling-rl-section"></section>
                    <section class="dl-module" id="dl-spatiotemporal-section"></section>
                </div>
            </div>
        `;
    }

    private bindEvents(): void {
        const title = this.section.querySelector('.panel-title') as HTMLElement | null;
        title?.addEventListener('click', () => {
            this.toggleExpanded();
        });

        this.container.querySelector('#dl-health-check-btn')?.addEventListener('click', () => {
            void this.checkHealth();
        });
    }

    private initializeSubPanels(): void {
        const spatialContainer = this.container.querySelector('#dl-spatial-section') as HTMLElement | null;
        const anomalyContainer = this.container.querySelector('#dl-anomaly-section') as HTMLElement | null;
        const samplingRLContainer = this.container.querySelector('#dl-sampling-rl-section') as HTMLElement | null;
        const spatiotemporalContainer = this.container.querySelector('#dl-spatiotemporal-section') as HTMLElement | null;

        if (!spatialContainer || !anomalyContainer || !samplingRLContainer || !spatiotemporalContainer) {
            throw new Error('深度学习子模块容器不完整');
        }

        this.spatialPanel = new SpatialInterpolationPanel(spatialContainer, this.apiService);
        this.anomalyPanel = new AnomalyDetectionPanel(anomalyContainer, this.apiService);
        this.samplingRLPanel = new SamplingRLPanel(samplingRLContainer, this.apiService);
        this.spatiotemporalPanel = new SpatiotemporalPredictionPanel(spatiotemporalContainer, this.apiService);
    }

    private toggleExpanded(force?: boolean): void {
        this.isExpanded = typeof force === 'boolean' ? force : !this.isExpanded;
        this.container.style.display = this.isExpanded ? 'block' : 'none';

        const title = this.section.querySelector('.panel-title') as HTMLElement | null;
        if (title) {
            title.textContent = this.isExpanded ? '深度学习 ▾' : '深度学习 ▸';
        }
    }

    private async checkHealth(): Promise<void> {
        const statusEl = this.container.querySelector('#dl-service-status') as HTMLElement | null;
        const dotEl = this.container.querySelector('#dl-status-dot') as HTMLElement | null;
        const detailEl = this.container.querySelector('#dl-health-detail') as HTMLElement | null;

        if (statusEl) {
            statusEl.textContent = '深度学习服务状态：检测中...';
        }
        if (dotEl) {
            dotEl.className = 'dl-status-dot pending';
        }

        try {
            const health = await this.apiService.health();
            if (statusEl) {
                statusEl.textContent = `深度学习服务状态：${health.status}（device: ${health.device}）`;
            }
            if (dotEl) {
                dotEl.className = 'dl-status-dot online';
            }
            if (detailEl) {
                detailEl.textContent = `模型注册数：${health.registered_models?.length ?? 0}，异常模型：${health.trained_anomaly_models?.length ?? 0}，RL模型：${health.trained_sampling_rl_models?.length ?? 0}`;
            }
        } catch (error) {
            if (statusEl) {
                statusEl.textContent = `深度学习服务状态：不可用 (${error instanceof Error ? error.message : String(error)})`;
            }
            if (dotEl) {
                dotEl.className = 'dl-status-dot offline';
            }
            if (detailEl) {
                detailEl.textContent = '请确认后端已启动且 /api/dl 路由可访问。';
            }
        }
    }

    public destroy(): void {
        this.spatialPanel?.destroy();
        this.anomalyPanel?.destroy();
        this.samplingRLPanel?.destroy();
        this.spatiotemporalPanel?.destroy();
        this.container.innerHTML = '';
    }
}
