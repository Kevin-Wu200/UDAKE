/**
 * 采样策略选择器组件
 * 支持多种采样策略选择和高级设置
 */
import { I18n } from '../utils/I18n.js';

/** 策略信息 */
interface StrategyInfo {
    id: string;
    name: string;
    description: string;
    icon: string;
    recommended: boolean;
    features: string[];
}

/** 策略配置 */
interface StrategyConfig {
    n_recommendations: number;
    min_distance: number | null;
    enable_preview: boolean;
    threshold_percentile: number;
}

export class SamplingStrategySelector {
    private element: HTMLElement | null;
    private currentStrategy: string;
    private strategyConfig: StrategyConfig;
    private strategies: StrategyInfo[];
    private onStrategyChange: ((strategy: string, config: StrategyConfig) => void) | null;

    constructor() {
        this.element = null;
        this.currentStrategy = 'impact_optimized';
        this.strategyConfig = {
            n_recommendations: 20,
            min_distance: null,
            enable_preview: true,
            threshold_percentile: 75
        };
        this.onStrategyChange = null;
        this.strategies = [
            {
                id: 'impact_optimized',
                name: I18n.t('strategy.impact.name'),
                description: I18n.t('strategy.impact.description'),
                icon: '🎯',
                recommended: true,
                features: [
                    I18n.t('strategy.impact.feature1'),
                    I18n.t('strategy.impact.feature2'),
                    I18n.t('strategy.impact.feature3')
                ]
            },
            {
                id: 'variance_based',
                name: I18n.t('strategy.variance.name'),
                description: I18n.t('strategy.variance.description'),
                icon: '📊',
                recommended: false,
                features: [
                    I18n.t('strategy.variance.feature1'),
                    I18n.t('strategy.variance.feature2'),
                    I18n.t('strategy.variance.feature3')
                ]
            },
            {
                id: 'spatial_coverage',
                name: I18n.t('strategy.coverage.name'),
                description: I18n.t('strategy.coverage.description'),
                icon: '🗺️',
                recommended: false,
                features: [
                    I18n.t('strategy.coverage.feature1'),
                    I18n.t('strategy.coverage.feature2'),
                    I18n.t('strategy.coverage.feature3')
                ]
            },
            {
                id: 'hybrid',
                name: I18n.t('strategy.hybrid.name'),
                description: I18n.t('strategy.hybrid.description'),
                icon: '🔄',
                recommended: false,
                features: [
                    I18n.t('strategy.hybrid.feature1'),
                    I18n.t('strategy.hybrid.feature2'),
                    I18n.t('strategy.hybrid.feature3')
                ]
            }
        ];
    }

    /**
     * 初始化选择器
     */
    public initialize(): void {
        this.render();
        this.attachEventListeners();
    }

    /**
     * 渲染选择器UI
     */
    private render(): void {
        const existingSelector = document.getElementById('strategy-selector-container');
        if (existingSelector) {
            existingSelector.remove();
        }

        const container = document.createElement('div');
        container.id = 'strategy-selector-container';
        container.className = 'strategy-selector-container';
        container.innerHTML = `
            <div class="strategy-selector-header">
                <h3>${I18n.t('strategy.title')}</h3>
                <p class="strategy-description">${I18n.t('strategy.subtitle')}</p>
            </div>

            <div class="strategy-cards-grid">
                ${this.strategies.map(strategy => this.renderStrategyCard(strategy)).join('')}
            </div>

            <div class="strategy-settings">
                <h4>${I18n.t('strategy.advancedSettings')}</h4>
                <div class="settings-grid">
                    <div class="setting-item">
                        <label for="recommendation-count">
                            ${I18n.t('strategy.recommendationCount')}
                        </label>
                        <input
                            type="number"
                            id="recommendation-count"
                            value="${this.strategyConfig.n_recommendations}"
                            min="1"
                            max="100"
                        />
                    </div>
                    <div class="setting-item">
                        <label for="min-distance">
                            ${I18n.t('strategy.minDistance')}
                        </label>
                        <input
                            type="number"
                            id="min-distance"
                            value="${this.strategyConfig.min_distance || ''}"
                            placeholder="${I18n.t('strategy.noLimit')}"
                            min="0"
                        />
                    </div>
                    <div class="setting-item">
                        <label for="threshold-percentile">
                            ${I18n.t('strategy.thresholdPercentile')}
                        </label>
                        <input
                            type="number"
                            id="threshold-percentile"
                            value="${this.strategyConfig.threshold_percentile}"
                            min="0"
                            max="100"
                        />
                    </div>
                    <div class="setting-item">
                        <label class="checkbox-label">
                            <input
                                type="checkbox"
                                id="enable-preview"
                                ${this.strategyConfig.enable_preview ? 'checked' : ''}
                            />
                            ${I18n.t('strategy.enablePreview')}
                        </label>
                    </div>
                </div>
            </div>

            <div class="strategy-action">
                <button id="apply-strategy-btn" class="primary-btn">
                    ${I18n.t('strategy.apply')}
                </button>
            </div>
        `;

        document.body.appendChild(container);
        this.element = container;
    }

    /**
     * 渲染策略卡片
     */
    private renderStrategyCard(strategy: StrategyInfo): string {
        const isSelected = strategy.id === this.currentStrategy;
        const recommendedBadge = strategy.recommended
            ? `<span class="recommended-badge">${I18n.t('strategy.recommended')}</span>`
            : '';

        return `
            <div
                class="strategy-card ${isSelected ? 'selected' : ''}"
                data-strategy="${strategy.id}"
            >
                ${recommendedBadge}
                <div class="strategy-icon">${strategy.icon}</div>
                <div class="strategy-info">
                    <h4 class="strategy-name">${strategy.name}</h4>
                    <p class="strategy-desc">${strategy.description}</p>
                    <ul class="strategy-features">
                        ${strategy.features.map(feature => `
                            <li>${feature}</li>
                        `).join('')}
                    </ul>
                </div>
                <div class="strategy-select-indicator">
                    <div class="indicator-dot"></div>
                </div>
            </div>
        `;
    }

    /**
     * 附加事件监听器
     */
    private attachEventListeners(): void {
        if (!this.element) return;

        // 策略卡片点击
        const strategyCards = this.element.querySelectorAll('.strategy-card');
        strategyCards.forEach(card => {
            card.addEventListener('click', () => {
                const strategyId = card.getAttribute('data-strategy');
                if (strategyId) {
                    this.selectStrategy(strategyId);
                }
            });
        });

        // 应用按钮
        const applyBtn = this.element.querySelector('#apply-strategy-btn');
        applyBtn?.addEventListener('click', () => {
            this.applyStrategy();
        });

        // 设置项变化
        const countInput = this.element.querySelector('#recommendation-count') as HTMLInputElement;
        countInput?.addEventListener('change', (e) => {
            this.strategyConfig.n_recommendations = parseInt((e.target as HTMLInputElement).value, 10);
        });

        const distanceInput = this.element.querySelector('#min-distance') as HTMLInputElement;
        distanceInput?.addEventListener('change', (e) => {
            const value = (e.target as HTMLInputElement).value;
            this.strategyConfig.min_distance = value ? parseFloat(value) : null;
        });

        const thresholdInput = this.element.querySelector('#threshold-percentile') as HTMLInputElement;
        thresholdInput?.addEventListener('change', (e) => {
            this.strategyConfig.threshold_percentile = parseInt((e.target as HTMLInputElement).value, 10);
        });

        const previewCheckbox = this.element.querySelector('#enable-preview') as HTMLInputElement;
        previewCheckbox?.addEventListener('change', (e) => {
            this.strategyConfig.enable_preview = (e.target as HTMLInputElement).checked;
        });
    }

    /**
     * 选择策略
     */
    private selectStrategy(strategyId: string): void {
        this.currentStrategy = strategyId;

        // 更新UI
        if (this.element) {
            const cards = this.element.querySelectorAll('.strategy-card');
            cards.forEach(card => {
                const isSelected = card.getAttribute('data-strategy') === strategyId;
                card.classList.toggle('selected', isSelected);
            });
        }
    }

    /**
     * 应用策略
     */
    private applyStrategy(): void {
        // 触发策略变化事件
        this.onStrategyChange?.(this.currentStrategy, this.strategyConfig);

        // 显示确认消息
        this.showAppliedMessage();
    }

    /**
     * 显示应用确认消息
     */
    private showAppliedMessage(): void {
        const message = document.createElement('div');
        message.className = 'strategy-applied-message';
        message.textContent = I18n.t('strategy.applied', {
            strategy: this.getStrategyName(this.currentStrategy)
        });

        document.body.appendChild(message);

        // 2秒后自动消失
        setTimeout(() => {
            message.remove();
        }, 2000);
    }

    /**
     * 获取策略名称
     */
    private getStrategyName(strategyId: string): string {
        const strategy = this.strategies.find(s => s.id === strategyId);
        return strategy ? strategy.name : strategyId;
    }

    /**
     * 设置策略变化回调
     */
    public setOnStrategyChange(callback: ((strategy: string, config: StrategyConfig) => void) | null): void {
        this.onStrategyChange = callback;
    }

    /**
     * 获取当前策略
     */
    public getCurrentStrategy(): string {
        return this.currentStrategy;
    }

    /**
     * 获取当前配置
     */
    public getCurrentConfig(): StrategyConfig {
        return { ...this.strategyConfig };
    }

    /**
     * 设置策略
     */
    public setStrategy(strategyId: string): void {
        if (this.strategies.some(s => s.id === strategyId)) {
            this.selectStrategy(strategyId);
        }
    }

    /**
     * 设置配置
     */
    public setConfig(config: Partial<StrategyConfig>): void {
        this.strategyConfig = { ...this.strategyConfig, ...config };

        // 更新UI
        if (this.element) {
            const countInput = this.element.querySelector('#recommendation-count') as HTMLInputElement;
            if (countInput) countInput.value = this.strategyConfig.n_recommendations.toString();

            const distanceInput = this.element.querySelector('#min-distance') as HTMLInputElement;
            if (distanceInput) distanceInput.value = this.strategyConfig.min_distance?.toString() || '';

            const thresholdInput = this.element.querySelector('#threshold-percentile') as HTMLInputElement;
            if (thresholdInput) thresholdInput.value = this.strategyConfig.threshold_percentile.toString();

            const previewCheckbox = this.element.querySelector('#enable-preview') as HTMLInputElement;
            if (previewCheckbox) previewCheckbox.checked = this.strategyConfig.enable_preview;
        }
    }

    /**
     * 销毁选择器
     */
    public destroy(): void {
        if (this.element) {
            this.element.remove();
            this.element = null;
        }
        this.onStrategyChange = null;
    }

    /**
     * 更新UI文本
     */
    public updateUIText(): void {
        // 重新渲染以更新文本
        if (this.element) {
            this.render();
            this.attachEventListeners();
            this.selectStrategy(this.currentStrategy);
        }
    }
}