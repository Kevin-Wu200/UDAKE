/**
 * 参数调整面板组件
 * 提供双向绑定、模板管理、智能推荐、实时校验与警告聚合
 */

import { ParameterRelationshipChart } from './ParameterRelationshipChart.js';
import { ParameterImpactPreview, type KrigingPreviewConfig } from './ParameterImpactPreview.js';
import { VariogramChart, type VariogramParams } from './VariogramChart.js';
import { I18n } from '../utils/I18n.js'

const t = (key: string, params?: Record<string, string | number>): string => I18n.t(key, params);

type ParamName = 'grid-resolution' | 'nlags' | 'nugget' | 'sill' | 'range';

type TemplateConfig = {
    id: string;
    name: string;
    description: string;
    params: Record<ParamName, number>;
    method?: 'ordinary' | 'universal' | 'block';
    variogram_model?: 'spherical' | 'exponential' | 'gaussian';
};

type ValidationIssue = {
    level: 'error' | 'warning';
    message: string;
};

type SamplingContextPoint = {
    x: number;
    y: number;
    value?: number;
};

type RelationshipType = 'nugget-sill' | 'range-spatial' | 'grid-performance';

type RelationshipChartViewConfig = {
    id: RelationshipType;
    title: string;
    axisX: { key: string; label: string; min: number; max: number };
    axisY: { key: string; label: string; min: number; max: number };
    constraint: {
        label: string;
        validate: (x: number, y: number) => boolean;
    };
};

const RELATIONSHIP_STORAGE_KEY = 'krigingRelationshipType';

const PARAM_META: Record<ParamName, { min: number; max: number; step: number }> = {
    'grid-resolution': { min: 50, max: 500, step: 10 },
    nlags: { min: 6, max: 24, step: 1 },
    nugget: { min: 0, max: 1, step: 0.05 },
    sill: { min: 0, max: 10, step: 0.1 },
    range: { min: 0, max: 100, step: 1 }
};

const BUILTIN_TEMPLATES: Record<string, TemplateConfig> = {
    'quick-estimate': {
        id: 'quick-estimate',
        name: t('template.config.quick-estimate.name'),
        description: t('template.config.quick-estimate.description'),
        params: {
            'grid-resolution': 80,
            nlags: 8,
            nugget: 0.15,
            sill: 1,
            range: 20
        },
        method: 'ordinary',
        variogram_model: 'spherical'
    },
    'high-precision': {
        id: 'high-precision',
        name: t('template.config.high-precision.name'),
        description: t('template.config.high-precision.description'),
        params: {
            'grid-resolution': 220,
            nlags: 18,
            nugget: 0.05,
            sill: 1.2,
            range: 40
        },
        method: 'universal',
        variogram_model: 'gaussian'
    },
    balanced: {
        id: 'balanced',
        name: t('template.config.balanced.name'),
        description: t('template.config.balanced.description'),
        params: {
            'grid-resolution': 120,
            nlags: 12,
            nugget: 0.1,
            sill: 1,
            range: 30
        },
        method: 'ordinary',
        variogram_model: 'spherical'
    },
    'large-dataset': {
        id: 'large-dataset',
        name: t('template.config.large-dataset.name'),
        description: t('template.config.large-dataset.description'),
        params: {
            'grid-resolution': 90,
            nlags: 10,
            nugget: 0.2,
            sill: 1.2,
            range: 35
        },
        method: 'block',
        variogram_model: 'exponential'
    },
    'terrain-analysis': {
        id: 'terrain-analysis',
        name: t('template.config.terrain-analysis.name'),
        description: t('template.config.terrain-analysis.description'),
        params: {
            'grid-resolution': 150,
            nlags: 14,
            nugget: 0.08,
            sill: 1.1,
            range: 45
        },
        method: 'universal',
        variogram_model: 'gaussian'
    }
};

export class ParameterAdjustmentPanel {
    private static instance: ParameterAdjustmentPanel;

    private parameters: Map<ParamName, number> = new Map();

    private customTemplates: Record<string, TemplateConfig> = {};

    private samplingContext: SamplingContextPoint[] = [];

    private relationshipChart: ParameterRelationshipChart | null = null;

    private impactPreview: ParameterImpactPreview | null = null;

    private variogramChart: VariogramChart | null = null;

    private relationshipType: RelationshipType = 'nugget-sill';

    private currentRelationshipAxisSignature = '';

    private constructor() {
        this.initialize();
    }

    public static getInstance(): ParameterAdjustmentPanel {
        if (!ParameterAdjustmentPanel.instance) {
            ParameterAdjustmentPanel.instance = new ParameterAdjustmentPanel();
        }
        return ParameterAdjustmentPanel.instance;
    }

    private initialize(): void {
        this.relationshipType = this.loadRelationshipType();

        (Object.keys(PARAM_META) as ParamName[]).forEach((paramName) => {
            const meta = PARAM_META[paramName];
            this.bindSlider(paramName, meta.min, meta.max);
        });

        this.loadSavedParameters();
        this.loadCustomTemplates();
        this.bindTemplateControls();
        this.bindConfigApplyEvent();
        this.initializeVisualizationComponents();
        this.bindVisualizationControls();

        this.refreshTemplateSelector();
        this.updateRangeVisualization();
        this.updateWarningPanel();
        this.syncVisualization();
    }

    private bindSlider(paramName: ParamName, min: number, max: number): void {
        const slider = document.getElementById(`${paramName}-slider`) as HTMLInputElement | null;
        const input = document.getElementById(paramName) as HTMLInputElement | null;
        const valueDisplay = document.getElementById(`${paramName}-value`) as HTMLElement | null;

        if (!slider || !input) {
            console.warn(`Slider or input not found for parameter: ${paramName}`);
            return;
        }

        const applyValue = (rawValue: number): void => {
            const value = this.normalizeValue(paramName, rawValue);
            slider.value = String(value);
            input.value = String(value);
            if (valueDisplay) {
                valueDisplay.textContent = String(value);
            }
            this.parameters.set(paramName, value);
            this.validateParameter(paramName, value, min, max);
            if (paramName === 'range') {
                this.updateRangeVisualization();
            }
            this.updateWarningPanel();
            this.syncVisualization();
        };

        slider.addEventListener('input', () => {
            applyValue(parseFloat(slider.value));
        });

        input.addEventListener('input', () => {
            const parsed = parseFloat(input.value);
            if (!Number.isNaN(parsed)) {
                applyValue(parsed);
            }
        });

        const initialValue = parseFloat(input.value);
        this.parameters.set(paramName, Number.isNaN(initialValue) ? min : initialValue);
    }

    private bindTemplateControls(): void {
        const applyBtn = document.getElementById('apply-template-btn') as HTMLButtonElement | null;
        const recommendBtn = document.getElementById('recommend-template-btn') as HTMLButtonElement | null;
        const saveBtn = document.getElementById('save-template-btn') as HTMLButtonElement | null;
        const exportBtn = document.getElementById('export-template-btn') as HTMLButtonElement | null;
        const importBtn = document.getElementById('import-template-btn') as HTMLButtonElement | null;

        applyBtn?.addEventListener('click', () => {
            const select = document.getElementById('kriging-template-select') as HTMLSelectElement | null;
            const templateId = select?.value || 'balanced';
            const applied = this.applyTemplate(templateId);
            this.showTemplateOperationResult(
                applied ? t('template.operate.success') : t('template.operate.warning'),
                applied ? 'success' : 'warning'
            );
        });

        recommendBtn?.addEventListener('click', () => {
            this.recommendParametersFromSampling();
        });

        saveBtn?.addEventListener('click', () => {
            this.saveCurrentAsTemplate();
        });

        exportBtn?.addEventListener('click', () => {
            this.exportTemplates();
        });

        importBtn?.addEventListener('click', () => {
            this.importTemplates();
        });
    }

    private bindConfigApplyEvent(): void {
        document.addEventListener('applyParameterConfig', (event: Event) => {
            const customEvent = event as CustomEvent<{ krigingParams?: Record<string, unknown> }>;
            const params = customEvent.detail?.krigingParams;
            if (!params) {
                return;
            }
            this.applyExternalParameters(params);
        });
    }

    private initializeVisualizationComponents(): void {
        const root = this.ensureVisualizationContainer();
        if (!root) {
            return;
        }

        const relationshipContainer = root.querySelector('#parameter-relationship-chart') as HTMLElement | null;
        const impactContainer = root.querySelector('#parameter-impact-preview') as HTMLElement | null;
        const variogramContainer = root.querySelector('#variogram-fitting-chart') as HTMLElement | null;

        if (relationshipContainer) {
            const config = this.buildRelationshipConfig(this.relationshipType);
            this.relationshipChart = new ParameterRelationshipChart(relationshipContainer, {
                axisX: config.axisX,
                axisY: config.axisY,
                constraint: config.constraint,
                statusResolver: (x, y) => this.resolveRelationshipRegion(this.relationshipType, x, y),
                onPointSelected: (x, y) => this.applyRelationshipSelection(x, y)
            });
            this.currentRelationshipAxisSignature = this.buildRelationshipAxisSignature(config);
            this.updateRelationshipTitle(config.title);
        }

        if (impactContainer) {
            this.impactPreview = new ParameterImpactPreview(impactContainer);
        }

        if (variogramContainer) {
            this.variogramChart = new VariogramChart({
                container: variogramContainer,
                empiricalData: this.buildEmpiricalVariogramData(),
                models: [],
                selectedModel: t('variogram.selectedModel'),
                showLegend: true,
                title: t('variogram.title')
            });
        }
    }

    private bindVisualizationControls(): void {
        const toggleButton = document.getElementById('toggle-kriging-visualization') as HTMLButtonElement | null;
        const panel = document.getElementById('kriging-visualization-panel') as HTMLElement | null;
        const generatePreviewBtn = document.getElementById('generate-impact-preview-btn') as HTMLButtonElement | null;
        const modelSelect = document.getElementById('variogram-model') as HTMLSelectElement | null;
        const relationshipSelect = document.getElementById('relationship-chart-select') as HTMLSelectElement | null;
        const restoreBtn = document.getElementById('restore-recommended-center-btn') as HTMLButtonElement | null;

        toggleButton?.addEventListener('click', () => {
            if (!panel) {
                return;
            }
            const hidden = panel.classList.toggle('collapsed');
            panel.setAttribute('aria-hidden', hidden ? 'true' : 'false');
            toggleButton.textContent = hidden ? t('dialog.visualization.show') : t('dialog.visualization.hide');
        });

        generatePreviewBtn?.addEventListener('click', async () => {
            await this.generateCurrentPreview();
        });

        modelSelect?.addEventListener('change', () => {
            this.syncVisualization();
        });

        relationshipSelect?.addEventListener('change', () => {
            const nextType = relationshipSelect.value as RelationshipType;
            this.setRelationshipType(nextType);
        });

        restoreBtn?.addEventListener('click', () => {
            this.restoreToRecommendedCenter();
        });
    }

    private ensureVisualizationContainer(): HTMLElement | null {
        let panel = document.getElementById('kriging-visualization-panel') as HTMLElement | null;
        if (panel) {
            return panel;
        }

        const startBtn = document.getElementById('start-kriging-btn');
        const container = startBtn?.parentElement;
        if (!container) {
            return null;
        }

        const section = document.createElement('section');
        section.className = 'kriging-visualization-wrapper';
        section.innerHTML = `
            <div class="kriging-visualization-toolbar">
                <h3>${t('dialog.parameter.visualization.name')}</h3>
                <div class="kriging-template-actions">
                    <button id="generate-impact-preview-btn" class="btn btn-secondary" type="button">${t('dialog.parameter.visualization.generate-preview')}</button>
                    <button id="toggle-kriging-visualization" class="btn btn-secondary" type="button">${t('dialog.visualization.hide')}</button>
                </div>
            </div>
            <div id="kriging-visualization-panel">
                <div class="kriging-visual-card">
                    <div class="kriging-visual-card-head">
                        <div id="parameter-relationship-title" class="kriging-visual-card-title">${t('dialog.parameter.relationship.title')}</div>
                        <div class="kriging-relationship-actions">
                            <span id="relationship-constraint-label" class="relationship-constraint-label">${t('dialog.parameter.relationship.constraint')}nugget ≤ sill</span>
                            <span id="relationship-status-badge" class="relationship-status-badge valid">${t('dialog.parameter.relationship.status.valid')}</span>
                            <button id="restore-recommended-center-btn" class="btn btn-secondary" type="button">${t('dialog.parameter.restore-recommend-center')}</button>
                        </div>
                        <label class="kriging-relationship-switch" for="relationship-chart-select">
                            <span>${t('kriging.relationship.switch-button.title')}</span>
                            <select id="relationship-chart-select">
                                <option value="nugget-sill">nugget-sill${t('kriging.relationship.nugget-sill')}</option>
                                <option value="range-spatial">range-spatial${t('kriging.relationship.range-spatial')}</option>
                                <option value="grid-performance">grid-performance${t('kriging.relationship.grid-performance')}</option>
                            </select>
                        </label>
                    </div>
                    <div id="parameter-relationship-chart" class="kriging-visual-chart"></div>
                </div>
                <div class="kriging-visual-card">
                    <div class="kriging-visual-card-title">${t('kriging.visual-card-title.parameter')}</div>
                    <div id="parameter-impact-preview"></div>
                </div>
                <div class="kriging-visual-card">
                    <div class="kriging-visual-card-title">${t('kriging.visual-card-title.variogram')}</div>
                    <div id="variogram-fitting-chart" class="kriging-variogram-chart"></div>
                </div>
            </div>
        `;

        container.insertBefore(section, startBtn);
        const relationshipSelect = section.querySelector('#relationship-chart-select') as HTMLSelectElement | null;
        if (relationshipSelect) {
            relationshipSelect.value = this.relationshipType;
        }
        panel = section.querySelector('#kriging-visualization-panel') as HTMLElement | null;
        return panel;
    }

    private getCurrentPreviewConfig(): KrigingPreviewConfig {
        const method = (document.getElementById('kriging-method') as HTMLSelectElement | null)?.value;
        const variogramModel = (document.getElementById('variogram-model') as HTMLSelectElement | null)?.value;
        return {
            'grid-resolution': this.parameters.get('grid-resolution') ?? 100,
            nlags: this.parameters.get('nlags') ?? 12,
            nugget: this.parameters.get('nugget') ?? 0,
            sill: this.parameters.get('sill') ?? 1,
            range: this.parameters.get('range') ?? 10,
            method: (method as KrigingPreviewConfig['method']) || 'ordinary',
            variogramModel: (variogramModel as KrigingPreviewConfig['variogramModel']) || 'spherical'
        };
    }

    private async generateCurrentPreview(): Promise<void> {
        if (!this.impactPreview) {
            return;
        }
        await this.impactPreview.generatePreview(this.getCurrentPreviewConfig(), '当前配置');
    }

    private buildEmpiricalVariogramData(): Array<{ distance: number; semivariance: number; count: number }> {
        const range = this.parameters.get('range') ?? 30;
        const sill = this.parameters.get('sill') ?? 1;
        const nugget = this.parameters.get('nugget') ?? 0.1;
        const points: Array<{ distance: number; semivariance: number; count: number }> = [];
        const maxDistance = Math.max(1, range * 1.4);

        for (let i = 1; i <= 12; i++) {
            const distance = Number(((maxDistance / 12) * i).toFixed(2));
            const ratio = distance / Math.max(1, range);
            const trend = ratio <= 1
                ? nugget + (sill - nugget) * (1.5 * ratio - 0.5 * ratio ** 3)
                : sill;
            const noise = ((i % 3) - 1) * Math.max(0.01, sill * 0.025);
            points.push({
                distance,
                semivariance: Number(Math.max(0, trend + noise).toFixed(4)),
                count: 5 + i
            });
        }
        return points;
    }

    private buildVariogramParams(): VariogramParams {
        const model = (document.getElementById('variogram-model') as HTMLSelectElement | null)?.value || 'spherical';
        return {
            modelType: (model as VariogramParams['modelType']) || 'spherical',
            nugget: this.parameters.get('nugget') ?? 0,
            sill: this.parameters.get('sill') ?? 1,
            range: this.parameters.get('range') ?? 10
        };
    }

    private buildRelationshipConfig(type: RelationshipType): RelationshipChartViewConfig {
        const spatialRange = this.getSpatialRange();
        const maxSpatialAxis = Math.max(200, Math.ceil(spatialRange * 1.2));

        const configs: Record<RelationshipType, RelationshipChartViewConfig> = {
            'nugget-sill': {
                id: 'nugget-sill',
                title: t('kriging.visual-card-title.type', { type: "nugget-sill"}),
                axisX: { key: 'nugget', label: 'nugget', min: PARAM_META.nugget.min, max: PARAM_META.nugget.max },
                axisY: { key: 'sill', label: 'sill', min: PARAM_META.sill.min, max: PARAM_META.sill.max },
                constraint: {
                    label: 'nugget ≤ sill',
                    validate: (x, y) => x <= y
                }
            },
            'range-spatial': {
                id: 'range-spatial',
                title: t('kriging.visual-card-title.type', { type: "range-spatial" }),
                axisX: { key: 'range', label: 'range', min: PARAM_META.range.min, max: PARAM_META.range.max },
                axisY: { key: 'spatialRange', label: t('kriging.spatial-range'), min: 0, max: maxSpatialAxis },
                constraint: {
                    label: t('kriging.range-spatial.recommend-range'),
                    validate: (x, y) => y <= 0 ? x === 0 : x >= y * 0.15 && x <= y * 0.4
                }
            },
            'grid-performance': {
                id: 'grid-performance',
                title: t('kriging.visual-card-title.type', { type: "grid-performance" }),
                axisX: {
                    key: 'gridResolution',
                    label: t('kriging.gridResolution'),
                    min: PARAM_META['grid-resolution'].min,
                    max: PARAM_META['grid-resolution'].max
                },
                axisY: { key: 'estimatedTime', label: t('common.estimatedTime'), min: 0, max: 30 },
                constraint: {
                    label: t('common.recommendTime', { time: "< 10"}),
                    validate: (_x, y) => y < 10
                }
            }
        };

        return configs[type];
    }

    private buildRelationshipAxisSignature(config: RelationshipChartViewConfig): string {
        return [
            config.id,
            config.axisX.key,
            config.axisX.min,
            config.axisX.max,
            config.axisY.key,
            config.axisY.min,
            config.axisY.max
        ].join('|');
    }

    private applyRelationshipSelection(x: number, y: number): void {
        if (this.relationshipType === 'nugget-sill') {
            this.setParameter('nugget', x);
            this.setParameter('sill', y);
            return;
        }

        if (this.relationshipType === 'range-spatial') {
            this.setParameter('range', x);
            return;
        }

        if (this.relationshipType === 'grid-performance') {
            this.setParameter('grid-resolution', x);
        }
    }

    private updateRelationshipTitle(title: string): void {
        const titleEl = document.getElementById('parameter-relationship-title');
        if (titleEl) {
            titleEl.textContent = title;
        }
    }

    private loadRelationshipType(): RelationshipType {
        const raw = localStorage.getItem(RELATIONSHIP_STORAGE_KEY);
        if (raw === 'nugget-sill' || raw === 'range-spatial' || raw === 'grid-performance') {
            return raw;
        }
        return 'nugget-sill';
    }

    private setRelationshipType(type: RelationshipType): void {
        this.relationshipType = type;
        localStorage.setItem(RELATIONSHIP_STORAGE_KEY, type);
        const select = document.getElementById('relationship-chart-select') as HTMLSelectElement | null;
        if (select) {
            select.value = type;
        }
        this.currentRelationshipAxisSignature = '';
        this.syncVisualization();
    }

    private getSpatialRange(): number {
        if (this.samplingContext.length < 2) {
            return 200;
        }

        const xValues = this.samplingContext.map((point) => point.x);
        const yValues = this.samplingContext.map((point) => point.y);
        const xSpan = Math.max(...xValues) - Math.min(...xValues);
        const ySpan = Math.max(...yValues) - Math.min(...yValues);
        return Number(Math.sqrt((xSpan ** 2) + (ySpan ** 2)).toFixed(3));
    }

    private estimateGridTimeSeconds(gridResolution: number): number {
        const nlags = this.parameters.get('nlags') ?? 12;
        const range = this.parameters.get('range') ?? 30;
        const estimate = gridResolution * 0.032 + nlags * 0.22 + range * 0.06;
        return Number(Math.max(0.2, Math.min(30, estimate)).toFixed(3));
    }

    private getRelationshipPoint(type: RelationshipType): { x: number; y: number; region: 'valid' | 'invalid' | 'warning' } {
        if (type === 'nugget-sill') {
            const x = this.parameters.get('nugget') ?? 0;
            const y = this.parameters.get('sill') ?? 1;
            return { x, y, region: this.resolveRelationshipRegion(type, x, y) };
        }

        if (type === 'range-spatial') {
            const x = this.parameters.get('range') ?? 10;
            const y = this.getSpatialRange();
            return { x, y, region: this.resolveRelationshipRegion(type, x, y) };
        }

        const x = this.parameters.get('grid-resolution') ?? 100;
        const y = this.estimateGridTimeSeconds(x);
        return { x, y, region: this.resolveRelationshipRegion(type, x, y) };
    }

    private resolveRelationshipRegion(type: RelationshipType, x: number, y: number): 'valid' | 'invalid' | 'warning' {
        if (type === 'nugget-sill') {
            return x <= y ? 'valid' : 'invalid';
        }
        if (type === 'range-spatial') {
            const valid = y <= 0 ? x === 0 : x >= y * 0.15 && x <= y * 0.4;
            return valid ? 'valid' : 'warning';
        }
        return y < 10 ? 'valid' : 'warning';
    }

    private syncVisualization(): void {
        const relationshipConfig = this.buildRelationshipConfig(this.relationshipType);
        const signature = this.buildRelationshipAxisSignature(relationshipConfig);

        if (this.relationshipChart && this.currentRelationshipAxisSignature !== signature) {
            this.relationshipChart.setAxes(relationshipConfig.axisX, relationshipConfig.axisY);
            this.relationshipChart.setConstraint(relationshipConfig.constraint);
            this.currentRelationshipAxisSignature = signature;
        }

        this.updateRelationshipTitle(relationshipConfig.title);
        const relationPoint = this.getRelationshipPoint(this.relationshipType);
        this.relationshipChart?.update(relationPoint.x, relationPoint.y);
        this.relationshipChart?.highlightRegion(relationPoint.region);
        this.updateRelationshipActions(relationshipConfig.constraint?.label || t('dialog.parameter.relationship.constraintRequired'), relationPoint.region);
        this.variogramChart?.updateFitting(this.buildVariogramParams());
    }

    private updateRelationshipActions(constraintLabel: string, region: 'valid' | 'invalid' | 'warning'): void {
        const label = document.getElementById('relationship-constraint-label');
        if (label) {
            label.textContent = `${t('dialog.parameter.relationship.constraint')}${constraintLabel}`;
        }

        const badge = document.getElementById('relationship-status-badge');
        if (badge) {
            badge.className = `relationship-status-badge ${region}`;
            badge.textContent = region === 'valid' ? t('common.valid') : region === 'warning' ? t('common.warning') : t('common.invalid') ;
        }

        const restoreBtn = document.getElementById('restore-recommended-center-btn') as HTMLButtonElement | null;
        if (restoreBtn) {
            restoreBtn.disabled = region === 'valid';
            restoreBtn.textContent = region === 'valid' ? t('dialog.parameter.recommend-center-already-set') : t('dialog.parameter.restore-recommend-center');
        }
    }

    private restoreToRecommendedCenter(): void {
        const config = this.buildRelationshipConfig(this.relationshipType);
        const center = this.calculateRecommendedCenter(config);
        if (!center) {
            this.showTemplateOperationResult(t('dialog.parameter.restore-recommend-center.pointLost'), 'warning');
            return;
        }

        if (this.relationshipType === 'nugget-sill') {
            this.animateParameter('nugget', center.x);
            this.animateParameter('sill', center.y);
            this.showTemplateOperationResult(t('dialog.parameter.restore-recommend-center.success'), 'success');
            return;
        }

        if (this.relationshipType === 'range-spatial') {
            this.animateParameter('range', center.x);
            this.showTemplateOperationResult(t('dialog.parameter.restore-recommend-center.success'), 'success');
            return;
        }

        this.animateParameter('grid-resolution', center.x);
        this.showTemplateOperationResult(t('dialog.parameter.restore-recommend-center.success'), 'success');
    }

    private calculateRecommendedCenter(config: RelationshipChartViewConfig): { x: number; y: number } | null {
        const sampleCount = 30;
        let count = 0;
        let sumX = 0;
        let sumY = 0;
        const rangeX = Math.max(1e-6, config.axisX.max - config.axisX.min);
        const rangeY = Math.max(1e-6, config.axisY.max - config.axisY.min);

        for (let xi = 0; xi <= sampleCount; xi++) {
            for (let yi = 0; yi <= sampleCount; yi++) {
                const x = config.axisX.min + (rangeX * xi) / sampleCount;
                const y = config.axisY.min + (rangeY * yi) / sampleCount;
                if (config.constraint.validate(x, y)) {
                    count += 1;
                    sumX += x;
                    sumY += y;
                }
            }
        }

        if (count === 0) {
            return null;
        }

        return {
            x: sumX / count,
            y: sumY / count
        };
    }

    private animateParameter(paramName: ParamName, targetValue: number): void {
        const sourceValue = this.parameters.get(paramName) ?? targetValue;
        const delta = targetValue - sourceValue;
        if (Math.abs(delta) < 1e-6) {
            this.setParameter(paramName, targetValue);
            return;
        }

        const duration = 280;
        const start = Date.now();
        const frame = (): void => {
            const elapsed = Date.now() - start;
            const progress = Math.max(0, Math.min(1, elapsed / duration));
            const eased = 1 - ((1 - progress) ** 3);
            this.setParameter(paramName, sourceValue + delta * eased);
            if (progress < 1) {
                window.requestAnimationFrame(frame);
            }
        };
        window.requestAnimationFrame(frame);
    }

    private applyExternalParameters(params: Record<string, unknown>): void {
        const map: Record<ParamName, string> = {
            'grid-resolution': 'grid_resolution',
            nlags: 'nlags',
            nugget: 'nugget',
            sill: 'sill',
            range: 'range'
        };

        (Object.keys(map) as ParamName[]).forEach((paramName) => {
            const apiField = map[paramName];
            const raw = params[apiField];
            if (typeof raw === 'number') {
                this.setParameter(paramName, raw);
            }
        });

        if (params.method && typeof params.method === 'string') {
            this.setSelectValue('kriging-method', params.method);
        }

        if (params.variogram_model && typeof params.variogram_model === 'string') {
            this.setSelectValue('variogram-model', params.variogram_model);
        }

        this.updateWarningPanel();
        this.syncVisualization();
    }

    private setSelectValue(id: string, value: string): void {
        const select = document.getElementById(id) as HTMLSelectElement | null;
        if (!select) {
            return;
        }
        select.value = value;
        select.dispatchEvent(new Event('change', { bubbles: true }));
    }

    private normalizeValue(paramName: ParamName, value: number): number {
        const meta = PARAM_META[paramName];
        const clamped = Math.max(meta.min, Math.min(meta.max, value));
        const precision = meta.step < 1 ? 2 : 0;
        return Number(clamped.toFixed(precision));
    }

    private validateParameter(paramName: ParamName, value: number, min: number, max: number): void {
        const input = document.getElementById(paramName) as HTMLInputElement | null;
        if (!input) {
            return;
        }

        if (value < min || value > max) {
            input.classList.add('error');
            this.showParameterWarning(paramName, t('dialog.parameter.range-required', {
                min: min,
                max: max
            }));
            return;
        }

        input.classList.remove('error');
        this.hideParameterWarning(paramName);

        const nugget = this.parameters.get('nugget') ?? 0;
        const sill = this.parameters.get('sill') ?? 1;
        if (nugget > sill) {
            this.showParameterWarning('nugget', t('dialog.parameter.warning.nugget'));
            this.showParameterWarning('sill', t('dialog.parameter.warning.sill'));
        } else {
            this.hideParameterWarning('nugget');
            this.hideParameterWarning('sill');
        }
    }

    private showParameterWarning(paramName: ParamName, message: string): void {
        let warningEl = document.getElementById(`${paramName}-warning`);

        if (!warningEl) {
            warningEl = document.createElement('div');
            warningEl.id = `${paramName}-warning`;
            warningEl.className = 'parameter-warning';
            const input = document.getElementById(paramName);
            if (input) {
                input.parentElement?.appendChild(warningEl);
            }
        }

        warningEl.textContent = message;
        (warningEl as HTMLElement).style.display = 'block';
    }

    private hideParameterWarning(paramName: ParamName): void {
        const warningEl = document.getElementById(`${paramName}-warning`);
        if (warningEl) {
            (warningEl as HTMLElement).style.display = 'none';
        }
    }

    private updateWarningPanel(): void {
        const warningPanel = document.getElementById('kriging-warning-panel') as HTMLElement | null;
        if (!warningPanel) {
            return;
        }

        const validation = this.validateAll();
        if (validation.errors.length === 0 && validation.warnings.length === 0) {
            warningPanel.style.display = 'none';
            warningPanel.textContent = '';
            warningPanel.className = 'status-message';
            return;
        }

        const errorPrefix = validation.errors.length > 0 ? `${t('common.error')}: ${validation.errors.join('；')}` : '';
        const warningPrefix = validation.warnings.length > 0 ? `${t('common.warning')}: ${validation.warnings.join('；')}` : '';
        const merged = [errorPrefix, warningPrefix].filter(Boolean).join(' | ');

        warningPanel.style.display = 'block';
        warningPanel.textContent = merged;
        warningPanel.className = `status-message ${validation.valid ? 'warning' : 'error'}`;
    }

    private updateRangeVisualization(): void {
        const range = this.parameters.get('range') ?? 10;
        const bar = document.getElementById('range-visual-bar') as HTMLElement | null;
        if (!bar) {
            return;
        }
        const ratio = Math.max(0, Math.min(100, range));
        bar.style.width = `${ratio}%`;
    }

    private collectValidationIssues(): ValidationIssue[] {
        const issues: ValidationIssue[] = [];

        const gridResolution = this.parameters.get('grid-resolution') ?? 100;
        const nlags = this.parameters.get('nlags') ?? 12;
        const nugget = this.parameters.get('nugget') ?? 0;
        const sill = this.parameters.get('sill') ?? 1;
        const range = this.parameters.get('range') ?? 10;

        if (gridResolution <= 0) {
            issues.push({ level: 'error', message: t('dialog.parameter.warning.gird.mustPositive') });
        }

        if (nugget > sill) {
            issues.push({ level: 'error', message: t('dialog.parameter.warning.nugget') });
        }

        if (sill <= 0) {
            issues.push({ level: 'error', message: t('dialog.parameter.warning.sill.mustPositive') });
        }

        if (range <= 0) {
            issues.push({ level: 'error', message: t('dialog.parameter.warning.range.mustPositive') });
        }

        if (range > sill) {
            issues.push({ level: 'warning', message: t('dialog.parameter.warning.range-larger-than-sill') });
        }

        if (this.samplingContext.length > 0) {
            if (gridResolution > 280 && this.samplingContext.length < 20) {
                issues.push({ level: 'warning', message: t('dialog.parameter.warning.fewPoints-and-highGrid') });
            }

            if (nlags > Math.max(6, Math.floor(this.samplingContext.length / 2))) {
                issues.push({ level: 'warning', message: t('dialog.parameter.warning.highNlags') });
            }
        }

        return issues;
    }

    public getParameters(): Record<string, number> {
        return Object.fromEntries(this.parameters);
    }

    public setParameter(paramName: string, value: number): void {
        const key = paramName as ParamName;
        if (!PARAM_META[key]) {
            return;
        }

        const normalized = this.normalizeValue(key, value);
        const slider = document.getElementById(`${key}-slider`) as HTMLInputElement | null;
        const input = document.getElementById(key) as HTMLInputElement | null;
        const valueDisplay = document.getElementById(`${key}-value`) as HTMLElement | null;

        if (slider) {
            slider.value = String(normalized);
        }
        if (input) {
            input.value = String(normalized);
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        if (valueDisplay) {
            valueDisplay.textContent = String(normalized);
        }

        this.parameters.set(key, normalized);

        if (key === 'range') {
            this.updateRangeVisualization();
        }

        this.updateWarningPanel();
        this.syncVisualization();
    }

    public resetToDefaults(): void {
        this.applyTemplate('balanced');
    }

    public saveParameters(name: string): void {
        const records = this.getHistoryRecords();
        records.unshift({
            id: Date.now().toString(),
            name: name || t('dialog.parameter.combination', { recordsNum: records.length + 1 }),
            parameters: this.getParameters(),
            timestamp: new Date().toISOString()
        });
        localStorage.setItem('savedParameters', JSON.stringify(records.slice(0, 30)));
    }

    private loadSavedParameters(): void {
        const lastUsed = localStorage.getItem('lastUsedParameters');
        if (!lastUsed) {
            return;
        }

        try {
            const parameters = JSON.parse(lastUsed) as Record<string, unknown>;
            Object.entries(parameters).forEach(([key, value]) => {
                if (typeof value === 'number') {
                    this.setParameter(key, value);
                }
            });
        } catch (error) {
            console.warn('Failed to load saved parameters:', error);
        }
    }

    public saveAsLastUsed(): void {
        localStorage.setItem('lastUsedParameters', JSON.stringify(this.getParameters()));
        this.recordHistory(t('common.nearbyUsed'), this.getParameters());
    }

    public validateAll(): { valid: boolean; errors: string[]; warnings: string[] } {
        const issues = this.collectValidationIssues();
        const errors = issues.filter((item) => item.level === 'error').map((item) => item.message);
        const warnings = issues.filter((item) => item.level === 'warning').map((item) => item.message);

        return {
            valid: errors.length === 0,
            errors,
            warnings
        };
    }

    public setSamplingContext(points: SamplingContextPoint[]): void {
        this.samplingContext = points;
        this.updateWarningPanel();
        this.syncVisualization();
    }

    public applyTemplate(templateId: string): boolean {
        const templates = this.getAllTemplates();
        const template = templates[templateId];
        const fallback = templates.balanced;
        const chosen = template || fallback;
        if (!chosen) {
            return false;
        }

        (Object.entries(chosen.params) as Array<[ParamName, number]>).forEach(([key, value]) => {
            this.setParameter(key, value);
        });

        if (chosen.method) {
            this.setSelectValue('kriging-method', chosen.method);
        }
        if (chosen.variogram_model) {
            this.setSelectValue('variogram-model', chosen.variogram_model);
        }

        this.recordHistory(`${t('template.used')}:${chosen.name}`, this.getParameters());
        return Boolean(template);
    }

    private recommendParametersFromSampling(): void {
        if (this.samplingContext.length === 0) {
            this.showTemplateOperationResult(t('dialog.sampling.contextRequired'), 'warning');
            this.applyTemplate('balanced');
            return;
        }

        const xValues = this.samplingContext.map((point) => point.x);
        const yValues = this.samplingContext.map((point) => point.y);
        const vValues = this.samplingContext.map((point) => point.value).filter((value): value is number => typeof value === 'number');

        const xSpan = Math.max(...xValues) - Math.min(...xValues);
        const ySpan = Math.max(...yValues) - Math.min(...yValues);
        const spatialSpan = Math.sqrt((xSpan ** 2) + (ySpan ** 2));
        const pointCount = this.samplingContext.length;

        const mean = vValues.length > 0
            ? vValues.reduce((sum, value) => sum + value, 0) / vValues.length
            : 0;
        const variance = vValues.length > 1
            ? vValues.reduce((sum, value) => sum + ((value - mean) ** 2), 0) / vValues.length
            : 0.5;

        const range = this.normalizeValue('range', Math.max(12, Math.min(95, spatialSpan * 0.25)));
        const sill = this.normalizeValue('sill', Math.max(0.8, Math.min(8, variance * 1.2 + 0.5)));
        const nugget = this.normalizeValue('nugget', Math.max(0, Math.min(0.8, sill * 0.2)));
        const nlags = this.normalizeValue('nlags', Math.max(8, Math.min(20, Math.floor(pointCount / 8) + 8)));
        const gridResolution = this.normalizeValue('grid-resolution', Math.max(70, Math.min(240, 260 - pointCount * 0.4)));

        this.setParameter('range', range);
        this.setParameter('sill', sill);
        this.setParameter('nugget', Math.min(nugget, sill));
        this.setParameter('nlags', nlags);
        this.setParameter('grid-resolution', gridResolution);

        const model = pointCount > 300 ? 'exponential' : pointCount > 80 ? 'gaussian' : 'spherical';
        const method = pointCount > 500 ? 'block' : pointCount > 180 ? 'universal' : 'ordinary';
        this.setSelectValue('variogram-model', model);
        this.setSelectValue('kriging-method', method);

        this.recordHistory(t('dialog.parameter.intelligent.recommend'), this.getParameters());
        this.showTemplateOperationResult(t('dialog.parameter.intelligent.recommend.success', { pointCount: pointCount}), 'success');
    }

    private saveCurrentAsTemplate(): void {
        const name = window.prompt(t('dialog.parameter.template.nameRequired'));
        if (!name) {
            return;
        }

        const id = `custom-${Date.now()}`;
        const method = (document.getElementById('kriging-method') as HTMLSelectElement | null)?.value;
        const variogram = (document.getElementById('variogram-model') as HTMLSelectElement | null)?.value;
        const template: TemplateConfig = {
            id,
            name,
            description: t('template.config.userCustomize'),
            params: {
                'grid-resolution': this.parameters.get('grid-resolution') ?? 100,
                nlags: this.parameters.get('nlags') ?? 12,
                nugget: this.parameters.get('nugget') ?? 0,
                sill: this.parameters.get('sill') ?? 1,
                range: this.parameters.get('range') ?? 10
            },
            method: (method as TemplateConfig['method']) || 'ordinary',
            variogram_model: (variogram as TemplateConfig['variogram_model']) || 'spherical'
        };

        this.customTemplates[id] = template;
        this.persistCustomTemplates();
        this.refreshTemplateSelector(id);
        this.showTemplateOperationResult(t('template.save.success', { name: name }), 'success');
    }

    private exportTemplates(): void {
        const payload = {
            exportedAt: new Date().toISOString(),
            templates: this.getAllTemplates()
        };

        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `kriging-templates-${Date.now()}.json`;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(url);
        this.showTemplateOperationResult(t('template.export.success'), 'success');
    }

    private importTemplates(): void {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'application/json';

        input.addEventListener('change', async () => {
            const file = input.files?.[0];
            if (!file) {
                return;
            }

            try {
                const text = await file.text();
                const parsed = JSON.parse(text) as { templates?: Record<string, TemplateConfig> };
                const templates = parsed.templates || {};

                Object.entries(templates).forEach(([id, template]) => {
                    if (template && template.params && !BUILTIN_TEMPLATES[id]) {
                        this.customTemplates[id] = template;
                    }
                });

                this.persistCustomTemplates();
                this.refreshTemplateSelector();
                this.showTemplateOperationResult(t('template.import.success'), 'success');
            } catch (error) {
                console.error(t('template.import.failed'), error);
                this.showTemplateOperationResult(t('template.import.failed.fileFormat-incorrect'), 'error');
            }
        });

        input.click();
    }

    private refreshTemplateSelector(selectedId?: string): void {
        const select = document.getElementById('kriging-template-select') as HTMLSelectElement | null;
        if (!select) {
            return;
        }

        const templates = this.getAllTemplates();
        const preferred = selectedId || select.value || 'balanced';
        const templateIds = Object.keys(templates);

        const options: string[] = templateIds.map((templateId) => {
            const template = templates[templateId];
            return `<option value="${templateId}">${template.name}</option>`;
        });

        options.push(`<option value="custom">${t('template.config.customize')}</option>`);
        select.innerHTML = options.join('');

        const finalValue = templateIds.includes(preferred) ? preferred : 'balanced';
        select.value = finalValue;
    }

    private getAllTemplates(): Record<string, TemplateConfig> {
        return {
            ...BUILTIN_TEMPLATES,
            ...this.customTemplates
        };
    }

    private loadCustomTemplates(): void {
        const raw = localStorage.getItem('krigingCustomTemplates');
        if (!raw) {
            return;
        }

        try {
            const parsed = JSON.parse(raw) as Record<string, TemplateConfig>;
            this.customTemplates = parsed;
        } catch (error) {
            console.warn('加载自定义模板失败:', error);
            this.customTemplates = {};
        }
    }

    private persistCustomTemplates(): void {
        localStorage.setItem('krigingCustomTemplates', JSON.stringify(this.customTemplates));
    }

    private getHistoryRecords(): Array<{ id: string; name: string; parameters: Record<string, number>; timestamp: string }> {
        try {
            const raw = localStorage.getItem('savedParameters');
            if (!raw) {
                return [];
            }
            const parsed = JSON.parse(raw) as Array<{ id: string; name: string; parameters: Record<string, number>; timestamp: string }>;
            return Array.isArray(parsed) ? parsed : [];
        } catch {
            return [];
        }
    }

    private recordHistory(actionName: string, parameters: Record<string, number>): void {
        const key = 'parameterHistory';
        const raw = localStorage.getItem(key);
        const records = raw ? (JSON.parse(raw) as Array<{ action: string; parameters: Record<string, number>; timestamp: string }>) : [];
        records.unshift({ action: actionName, parameters, timestamp: new Date().toISOString() });
        localStorage.setItem(key, JSON.stringify(records.slice(0, 50)));
    }

    private showTemplateOperationResult(message: string, type: 'success' | 'warning' | 'error'): void {
        const panel = document.getElementById('kriging-warning-panel') as HTMLElement | null;
        if (!panel) {
            return;
        }
        panel.style.display = 'block';
        panel.className = `status-message ${type}`;
        panel.textContent = message;

        window.setTimeout(() => {
            this.updateWarningPanel();
        }, 2500);
    }
}
