import { APIService } from '../services/API封装.js';
import { DataQualityPanel } from './integration/DataQualityPanel.js';
import { HistorySnapshotPanel } from './integration/HistorySnapshotPanel.js';
import { HistoryVersionComparisonPanel } from './integration/HistoryVersionComparisonPanel.js';
import { HistoryTrendAnalysisPanel } from './integration/HistoryTrendAnalysisPanel.js';
import { ModelEvaluationPanel } from './integration/ModelEvaluationPanel.js';
import { UserValidationPanel } from './integration/UserValidationPanel.js';
import { ModelFusionPanel } from './integration/ModelFusionPanel.js';
import { ModelRecommendationPanel } from './integration/ModelRecommendationPanel.js';
import { BatchKrigingPanel } from './integration/BatchKrigingPanel.js';
import { BatchReportPanel } from './integration/BatchReportPanel.js';
import { ParameterTemplatePanel } from './integration/ParameterTemplatePanel.js';
import { ReportGenerationPanel } from './integration/ReportGenerationPanel.js';
import { RiskReportPanel } from './integration/RiskReportPanel.js';
import { PerformanceReportPanel } from './integration/PerformanceReportPanel.js';
import { UncertaintyClassificationPanel } from './integration/UncertaintyClassificationPanel.js';
import { DecisionThresholdPanel } from './integration/DecisionThresholdPanel.js';
import { RiskIndexPanel } from './integration/RiskIndexPanel.js';
import { ResultComparisonPanel } from './integration/ResultComparisonPanel.js';
import { ResultQueryPanel } from './integration/ResultQueryPanel.js';
import { ErrorPredictionPanel } from './integration/ErrorPredictionPanel.js';
import { DataFeedbackPanel } from './integration/DataFeedbackPanel.js';
import { GeneralDataProcessingPanel } from './integration/GeneralDataProcessingPanel.js';
import { TaskQueuePanel } from './integration/TaskQueuePanel.js';
import { GPUAccelerationPanel } from './integration/GPUAccelerationPanel.js';
import MobileNavigation from './MobileNavigation.js';
import MobileInteractionEnhancer from './MobileInteractionEnhancer.js';

interface PanelMountable {
    mount(container: HTMLElement): void;
}

type PanelConstructor = new (apiService: APIService) => PanelMountable;

interface PanelDescriptor {
    id: string;
    title: string;
    ctor: PanelConstructor;
}

export class FrontendIntegrationHub {
    private initialized = false;
    private mobileNavigation: MobileNavigation | null = null;
    private mobileInteractionEnhancer: MobileInteractionEnhancer | null = null;

    private readonly panelDescriptors: PanelDescriptor[] = [
        { id: 'data-quality', title: '数据质量管理', ctor: DataQualityPanel },
        { id: 'history-snapshot', title: '历史快照管理', ctor: HistorySnapshotPanel },
        { id: 'history-version-comparison', title: '历史版本对比', ctor: HistoryVersionComparisonPanel },
        { id: 'history-trend-analysis', title: '趋势分析可视化', ctor: HistoryTrendAnalysisPanel },
        { id: 'model-evaluation', title: '模型评估与优化', ctor: ModelEvaluationPanel },
        { id: 'user-validation', title: '用户验证与自评估', ctor: UserValidationPanel },
        { id: 'model-fusion', title: '模型融合', ctor: ModelFusionPanel },
        { id: 'model-recommendation', title: '模型推荐', ctor: ModelRecommendationPanel },
        { id: 'batch-kriging', title: '批量插值任务', ctor: BatchKrigingPanel },
        { id: 'batch-report', title: '批量报告生成', ctor: BatchReportPanel },
        { id: 'parameter-template', title: '参数批量应用', ctor: ParameterTemplatePanel },
        { id: 'report-generation', title: '报告生成', ctor: ReportGenerationPanel },
        { id: 'risk-report', title: '风险报告', ctor: RiskReportPanel },
        { id: 'performance-report', title: '性能报告', ctor: PerformanceReportPanel },
        { id: 'uncertainty-classification', title: '不确定性分级', ctor: UncertaintyClassificationPanel },
        { id: 'decision-threshold', title: '决策阈值', ctor: DecisionThresholdPanel },
        { id: 'risk-index', title: '风险指数', ctor: RiskIndexPanel },
        { id: 'result-comparison', title: '结果对比分析', ctor: ResultComparisonPanel },
        { id: 'result-query', title: '结果查询', ctor: ResultQueryPanel },
        { id: 'error-prediction', title: '误差预测', ctor: ErrorPredictionPanel },
        { id: 'data-feedback', title: '数据反馈', ctor: DataFeedbackPanel },
        { id: 'general-data-processing', title: '通用数据处理', ctor: GeneralDataProcessingPanel },
        { id: 'task-queue', title: '任务队列管理', ctor: TaskQueuePanel },
        { id: 'gpu-acceleration', title: 'GPU 加速', ctor: GPUAccelerationPanel }
    ];

    constructor(
        private readonly sectionId: string,
        private readonly containerId: string,
        private readonly apiService: APIService
    ) {}

    public init(): void {
        const section = document.getElementById(this.sectionId);
        const container = document.getElementById(this.containerId);

        if (!section || !container) {
            return;
        }

        if (!this.initialized) {
            this.renderPanels(container);
            this.initialized = true;
        }
    }

    private renderPanels(container: HTMLElement, preferredOpenPanelId?: string): void {
        this.mobileInteractionEnhancer?.destroy();
        this.mobileInteractionEnhancer = null;
        container.innerHTML = '';
        container.classList.add('frontend-integration-hub');

        this.panelDescriptors.forEach((descriptor, index) => {
            const details = document.createElement('details');
            details.className = 'integration-detail';
            details.dataset.panelId = descriptor.id;
            details.open = preferredOpenPanelId
                ? descriptor.id === preferredOpenPanelId
                : index === 0;

            const summary = document.createElement('summary');
            summary.className = 'integration-summary';
            summary.textContent = descriptor.title;

            const panelContainer = document.createElement('div');
            panelContainer.className = 'integration-detail-content';
            panelContainer.id = `integration-${descriptor.id}`;

            const panelInstance = new descriptor.ctor(this.apiService);
            panelInstance.mount(panelContainer);

            details.appendChild(summary);
            details.appendChild(panelContainer);
            container.appendChild(details);
        });

        this.mountMobileHistoryNavigation(container);
        this.mountMobileInteractionEnhancer(container);
    }

    private mountMobileHistoryNavigation(container: HTMLElement): void {
        if (this.mobileNavigation) {
            return;
        }

        this.mobileNavigation = new MobileNavigation({
            navItems: [
                {
                    id: 'history-snapshot',
                    label: '快照',
                    icon: '<path d="M12 5v14M5 12h14"></path>',
                    action: () => this.focusPanel(container, 'history-snapshot')
                },
                {
                    id: 'history-version-comparison',
                    label: '对比',
                    icon: '<path d="M4 7h16M4 12h10M4 17h6"></path>',
                    action: () => this.focusPanel(container, 'history-version-comparison')
                },
                {
                    id: 'history-trend-analysis',
                    label: '趋势',
                    icon: '<path d="M4 16l5-5 4 3 7-8"></path>',
                    action: () => this.focusPanel(container, 'history-trend-analysis')
                }
            ],
            enableSwipe: true,
            enableHaptic: true
        });
    }

    private mountMobileInteractionEnhancer(container: HTMLElement): void {
        if (typeof window === 'undefined' || !window.matchMedia('(max-width: 767px)').matches) {
            return;
        }

        this.mobileInteractionEnhancer = new MobileInteractionEnhancer({
            container,
            searchPlaceholder: '搜索功能面板',
            onSearch: (keyword) => this.filterPanels(container, keyword),
            onRefresh: async () => {
                const activePanelId = this.getActivePanelId(container);
                this.renderPanels(container, activePanelId || undefined);
            },
            onLoadMore: async () => {
                this.expandNextCollapsedPanel(container);
            }
        });
    }

    private filterPanels(container: HTMLElement, keyword: string): void {
        const normalized = keyword.trim().toLowerCase();
        const detailsList = Array.from(container.querySelectorAll('.integration-detail')) as HTMLDetailsElement[];

        detailsList.forEach((detail) => {
            const title = detail.querySelector('.integration-summary')?.textContent?.toLowerCase() || '';
            const visible = !normalized || title.includes(normalized);
            detail.style.display = visible ? '' : 'none';
        });
    }

    private getActivePanelId(container: HTMLElement): string | null {
        const detailsList = Array.from(container.querySelectorAll('.integration-detail')) as HTMLDetailsElement[];
        const activePanel = detailsList.find((item) => item.open);
        return activePanel?.dataset.panelId || null;
    }

    private expandNextCollapsedPanel(container: HTMLElement): void {
        const detailsList = Array.from(container.querySelectorAll('.integration-detail')) as HTMLDetailsElement[];
        const nextCollapsed = detailsList.find((item) => !item.open && item.style.display !== 'none');
        if (!nextCollapsed) {
            return;
        }

        nextCollapsed.open = true;
        nextCollapsed.scrollIntoView({
            behavior: 'smooth',
            block: 'end'
        });
    }

    private focusPanel(container: HTMLElement, panelId: string): void {
        const detailsList = Array.from(container.querySelectorAll('.integration-detail')) as HTMLDetailsElement[];
        if (detailsList.length === 0) {
            return;
        }

        detailsList.forEach((item) => {
            item.open = item.dataset.panelId === panelId;
        });

        const target = detailsList.find((item) => item.dataset.panelId === panelId);
        if (!target) {
            return;
        }

        target.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }
}
