/**
 * 新手引导系统
 * 首次访问时自动显示，引导用户了解核心功能
 */

interface GuideStep {
    target: string | null;
    title: string;
    content: string;
    position: 'center' | 'bottom' | 'right';
}

export class OnboardingGuide {
    public currentStep: number;
    public overlay: HTMLDivElement | null;
    public tooltip: HTMLDivElement | null;
    public steps: GuideStep[];
    public readonly STORAGE_KEY: string;
    private resizeHandler: (() => void) | null;
    private scrollHandler: (() => void) | null;

    constructor() {
        this.currentStep = 0;
        this.overlay = null;
        this.tooltip = null;
        this.steps = this._defineSteps();
        this.STORAGE_KEY = 'udake_onboarding_completed';
        this.resizeHandler = null;
        this.scrollHandler = null;
    }

    /**
     * 定义引导步骤
     */
    private _defineSteps(): GuideStep[] {
        return [
            {
                target: null,
                title: '欢迎使用 UDAKE',
                content: '智能不确定性驱动空间决策平台，帮助您进行高效的空间插值分析。接下来将为您介绍核心功能。',
                position: 'center'
            },
            {
                target: '#new-project-btn',
                title: '新建项目',
                content: '点击此按钮创建新的采样项目，支持自由采样和区域采样两种模式。',
                position: 'bottom'
            },
            {
                target: '.sidebar .panel:nth-child(2)',
                title: '数据上传',
                content: '上传 GeoJSON 格式的采样数据文件，系统将自动解析坐标和属性字段。',
                position: 'right'
            },
            {
                target: '#kriging-method',
                title: '插值参数',
                content: '选择克里金方法和变异函数模型，设置网格分辨率后即可开始插值计算。',
                position: 'right'
            },
            {
                target: '#viewDiv',
                title: '地图交互',
                content: '地图区域支持缩放、平移操作，插值完成后可查看预测结果和方差分布。',
                position: 'center'
            }
        ];
    }

    /**
     * 检查是否需要显示引导
     */
    public shouldShow(): boolean {
        return !localStorage.getItem(this.STORAGE_KEY);
    }

    /**
     * 自动检查并启动引导
     */
    public autoStart(): void {
        if (!this.shouldShow()) {
            return;
        }

        let retryCount = 0;
        const maxRetries = 10;

        const tryStart = () => {
            if (!this.shouldShow()) {
                return;
            }

            const splashElement = document.querySelector('.splash-screen') as HTMLElement | null;
            const splashIsVisible = Boolean(
                splashElement &&
                splashElement.style.display !== 'none' &&
                !splashElement.classList.contains('splash-hidden')
            );

            if (!splashIsVisible) {
                this.start();
                return;
            }

            retryCount += 1;
            if (retryCount <= maxRetries) {
                setTimeout(tryStart, 300);
            }
        };

        // 稍等页面稳定后再判断启动条件
        setTimeout(tryStart, 300);
    }

    /**
     * 启动引导
     */
    public start(): void {
        this.currentStep = 0;
        this._createOverlay();
        this._createTooltip();
        this._showStep(0);

        // 添加窗口大小改变监听器
        this.resizeHandler = () => {
            if (this.tooltip && this.overlay) {
                const step = this.steps[this.currentStep];
                this._updateHighlight(step);
                this._positionTooltip(step);
            }
        };
        window.addEventListener('resize', this.resizeHandler);

        // 添加滚动事件监听器（防抖处理）
        let scrollTimeout: number | null = null;
        this.scrollHandler = () => {
            if (scrollTimeout) clearTimeout(scrollTimeout);
            scrollTimeout = window.setTimeout(() => {
                if (this.tooltip && this.overlay) {
                    const step = this.steps[this.currentStep];
                    this._updateHighlight(step);
                    this._positionTooltip(step);
                }
            }, 100);
        };
        window.addEventListener('scroll', this.scrollHandler);
    }

    /**
     * 创建遮罩层
     */
    private _createOverlay(): void {
        if (this.overlay) this.overlay.remove();

        this.overlay = document.createElement('div');
        this.overlay.className = 'onboarding-overlay';
        this.overlay.innerHTML = '<svg class="onboarding-svg" width="100%" height="100%">'
            + '<defs><mask id="onboarding-mask">'
            + '<rect width="100%" height="100%" fill="white"/>'
            + '<rect class="onboarding-hole" rx="12" ry="12" fill="black"/>'
            + '</mask></defs>'
            + '<rect width="100%" height="100%" fill="rgba(0,0,0,0.5)" mask="url(#onboarding-mask)"/>'
            + '</svg>';
        document.body.appendChild(this.overlay);

        // 点击遮罩层关闭
        this.overlay.addEventListener('click', (e: MouseEvent) => {
            if (e.target === this.overlay || (e.target as Element).tagName === 'svg' || (e.target as Element).tagName === 'rect') {
                // 不关闭，只是阻止冒泡
            }
        });
    }

    /**
     * 创建提示框
     */
    private _createTooltip(): void {
        if (this.tooltip) this.tooltip.remove();

        this.tooltip = document.createElement('div');
        this.tooltip.className = 'onboarding-tooltip';
        this.tooltip.setAttribute('role', 'dialog');
        this.tooltip.setAttribute('aria-modal', 'true');
        this.tooltip.setAttribute('aria-label', '新手引导');
        document.body.appendChild(this.tooltip);
    }

    /**
     * 显示指定步骤
     */
    private _showStep(index: number): void {
        const step = this.steps[index];
        if (!step) return;

        const total = this.steps.length;
        const isFirst = index === 0;
        const isLast = index === total - 1;

        // 更新高亮区域
        this._updateHighlight(step);

        // 构建提示框内容
        this.tooltip!.setAttribute('aria-label', `新手引导：${step.title}`);
        this.tooltip!.innerHTML = `
            <div class="onboarding-header">
                <span class="onboarding-step-count" aria-label="步骤 ${index + 1}，共 ${total} 步">${index + 1} / ${total}</span>
            </div>
            <h3 class="onboarding-title">${step.title}</h3>
            <p class="onboarding-content">${step.content}</p>
            <div class="onboarding-progress" role="progressbar" aria-valuenow="${index + 1}" aria-valuemin="1" aria-valuemax="${total}" aria-label="引导进度">
                ${this.steps.map((_: GuideStep, i: number) =>
                    `<span class="onboarding-dot ${i === index ? 'active' : i < index ? 'done' : ''}" aria-hidden="true"></span>`
                ).join('')}
            </div>
            <div class="onboarding-actions">
                <button class="onboarding-btn onboarding-btn-skip" aria-label="跳过引导">跳过</button>
                <div class="onboarding-nav">
                    ${!isFirst ? '<button class="onboarding-btn onboarding-btn-prev" aria-label="上一步">上一步</button>' : ''}
                    <button class="onboarding-btn onboarding-btn-next" aria-label="${isLast ? '完成引导' : '下一步'}">${isLast ? '完成' : '下一步'}</button>
                </div>
            </div>
        `;

        // 定位提示框
        this._positionTooltip(step);

        // 绑定按钮事件
        this.tooltip!.querySelector('.onboarding-btn-skip')!.addEventListener('click', () => this.finish());
        if (!isFirst) {
            this.tooltip!.querySelector('.onboarding-btn-prev')!.addEventListener('click', () => {
                this.currentStep--;
                this._showStep(this.currentStep);
            });
        }
        this.tooltip!.querySelector('.onboarding-btn-next')!.addEventListener('click', () => {
            if (isLast) {
                this.finish();
            } else {
                this.currentStep++;
                this._showStep(this.currentStep);
            }
        });

        // ESC 键关闭引导
        this.tooltip!.addEventListener('keydown', (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                this.finish();
            }
        });

        // 聚焦到下一步按钮
        const nextBtn = this.tooltip!.querySelector('.onboarding-btn-next') as HTMLButtonElement;
        if (nextBtn) nextBtn.focus();

        // 添加动画
        this.tooltip!.style.opacity = '0';
        this.tooltip!.style.transform = 'translateY(8px)';
        requestAnimationFrame(() => {
            this.tooltip!.style.transition = 'opacity 240ms ease, transform 240ms ease';
            this.tooltip!.style.opacity = '1';
            this.tooltip!.style.transform = 'translateY(0)';
        });
    }

    /**
     * 更新高亮区域
     */
    private _updateHighlight(step: GuideStep): void {
        const hole = this.overlay!.querySelector('.onboarding-hole') as SVGRectElement;
        if (!step.target || step.position === 'center') {
            hole.setAttribute('width', '0');
            hole.setAttribute('height', '0');
            return;
        }

        const el = document.querySelector(step.target);
        if (!el) {
            hole.setAttribute('width', '0');
            hole.setAttribute('height', '0');
            return;
        }

        const rect = el.getBoundingClientRect();
        const padding = 8;
        hole.setAttribute('x', String(rect.left - padding));
        hole.setAttribute('y', String(rect.top - padding));
        hole.setAttribute('width', String(rect.width + padding * 2));
        hole.setAttribute('height', String(rect.height + padding * 2));
    }

    /**
     * 定位提示框
     */
    private _positionTooltip(step: GuideStep): void {
        const tooltip = this.tooltip!;
        tooltip.style.position = 'fixed';

        if (!step.target || step.position === 'center') {
            tooltip.style.top = '50%';
            tooltip.style.left = '50%';
            tooltip.style.transform = 'translate(-50%, -50%)';
            this._ensureTooltipInViewport();
            return;
        }

        const el = document.querySelector(step.target);
        if (!el) {
            tooltip.style.top = '50%';
            tooltip.style.left = '50%';
            tooltip.style.transform = 'translate(-50%, -50%)';
            this._ensureTooltipInViewport();
            return;
        }

        const rect = el.getBoundingClientRect();
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        const padding = 16;
        const tooltipMinWidth = 280;
        const tooltipMinHeight = 150;

        // 首先定位到默认位置
        switch (step.position) {
            case 'bottom':
                tooltip.style.top = `${rect.bottom + padding}px`;
                tooltip.style.left = `${rect.left + rect.width / 2}px`;
                tooltip.style.transform = 'translate(-50%, 0)';
                break;
            case 'right':
                tooltip.style.top = `${rect.top + rect.height / 2}px`;
                tooltip.style.left = `${rect.right + padding}px`;
                tooltip.style.transform = 'translate(0, -50%)';
                break;
            default:
                tooltip.style.top = `${rect.bottom + padding}px`;
                tooltip.style.left = `${rect.left + rect.width / 2}px`;
                tooltip.style.transform = 'translate(-50%, 0)';
        }

        // 确保提示框在视口内
        this._ensureTooltipInViewport();
    }

    /**
     * 确保提示框在视口内
     */
    private _ensureTooltipInViewport(): void {
        if (!this.tooltip) return;

        // 强制重排以获取实际尺寸
        this.tooltip.style.visibility = 'hidden';
        this.tooltip.style.display = 'block';
        const tooltipRect = this.tooltip.getBoundingClientRect();
        this.tooltip.style.visibility = 'visible';

        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        const padding = 16;
        const margin = 8;

        let top = parseFloat(this.tooltip.style.top);
        let left = parseFloat(this.tooltip.style.left);
        let transform = this.tooltip.style.transform;

        // 检查右边界
        if (left + tooltipRect.width + margin > windowWidth) {
            const maxLeft = windowWidth - tooltipRect.width - margin;
            left = Math.max(padding, maxLeft);
            // 清除 transform 以使用绝对定位
            if (transform.includes('translateX')) {
                transform = transform.replace(/translateX\([^)]+\)/, 'translateX(0)');
            }
        }

        // 检查左边界
        if (left - margin < 0) {
            left = margin;
            // 清除 transform 以使用绝对定位
            if (transform.includes('translateX')) {
                transform = transform.replace(/translateX\([^)]+\)/, 'translateX(0)');
            }
        }

        // 检查下边界
        if (top + tooltipRect.height + margin > windowHeight) {
            // 尝试在上方显示
            const targetSelector = this.steps[this.currentStep].target;
            const targetElement = targetSelector ? document.querySelector(targetSelector) : null;
            if (targetElement) {
                const targetRect = targetElement.getBoundingClientRect();
                top = targetRect.top - tooltipRect.height - padding;
            } else {
                top = windowHeight - tooltipRect.height - margin;
            }
            // 调整 transform
            if (transform.includes('translateY')) {
                transform = transform.replace(/translateY\([^)]+\)/, 'translateY(0)');
            }
        }

        // 检查上边界
        if (top - margin < 0) {
            top = margin;
            // 调整 transform
            if (transform.includes('translateY')) {
                transform = transform.replace(/translateY\([^)]+\)/, 'translateY(0)');
            }
        }

        // 应用修正后的位置
        this.tooltip.style.top = `${top}px`;
        this.tooltip.style.left = `${left}px`;
        this.tooltip.style.transform = transform;
    }

    /**
     * 完成引导
     */
    public finish(): void {
        localStorage.setItem(this.STORAGE_KEY, 'true');

        // 移除窗口大小改变监听器
        if (this.resizeHandler) {
            window.removeEventListener('resize', this.resizeHandler);
            this.resizeHandler = null;
        }

        // 移除滚动监听器
        if (this.scrollHandler) {
            window.removeEventListener('scroll', this.scrollHandler);
            this.scrollHandler = null;
        }

        if (this.overlay) {
            this.overlay.style.opacity = '0';
            this.overlay.style.transition = 'opacity 240ms ease';
        }
        if (this.tooltip) {
            this.tooltip.style.opacity = '0';
            this.tooltip.style.transition = 'opacity 240ms ease';
        }
        setTimeout(() => {
            if (this.overlay) this.overlay.remove();
            if (this.tooltip) this.tooltip.remove();
            this.overlay = null;
            this.tooltip = null;
        }, 250);
    }

    /**
     * 重置引导（允许再次查看）
     */
    public reset(): void {
        localStorage.removeItem(this.STORAGE_KEY);
    }
}
