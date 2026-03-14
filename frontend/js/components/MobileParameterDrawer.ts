/**
 * 移动端参数调整面板
 * 底部抽屉样式，支持手势拖拽操作
 */

import './config/主题变量';

interface Parameter {
    id: string;
    label: string;
    value: number | string;
    min?: number;
    max?: number;
    step?: number;
    unit?: string;
    type?: 'slider' | 'select' | 'input';
    options?: { label: string; value: string | number }[];
}

interface MobileParameterDrawerOptions {
    parameters: Parameter[];
    onParameterChange?: (parameterId: string, value: any) => void;
    enableDrag?: boolean;
    enableHaptic?: boolean;
}

class MobileParameterDrawer {
    private parameters: Parameter[];
    private onParameterChange?: (parameterId: string, value: any) => void;
    private enableDrag: boolean;
    private enableHaptic: boolean;
    private isOpen: boolean = false;
    private startY: number = 0;
    private currentY: number = 0;
    private dragThreshold: number = 50;

    private elements: {
        drawer: HTMLElement | null;
        handle: HTMLElement | null;
        content: HTMLElement | null;
        overlay: HTMLElement | null;
    } = {
        drawer: null,
        handle: null,
        content: null,
        overlay: null,
    };

    constructor(options: MobileParameterDrawerOptions) {
        this.parameters = options.parameters;
        this.onParameterChange = options.onParameterChange;
        this.enableDrag = options.enableDrag ?? true;
        this.enableHaptic = options.enableHaptic ?? true;
        this.init();
    }

    /**
     * 初始化抽屉
     */
    private init(): void {
        this.createDrawer();
        this.bindEvents();
    }

    /**
     * 创建抽屉
     */
    private createDrawer(): void {
        const mapContainer = document.querySelector('.map-container');
        if (!mapContainer) return;

        // 创建遮罩层
        const overlay = document.createElement('div');
        overlay.className = 'drawer-overlay mobile-only';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 996;
            opacity: 0;
            pointer-events: none;
            transition: opacity 300ms ease;
        `;

        overlay.addEventListener('click', () => {
            this.close();
        });

        document.body.appendChild(overlay);
        this.elements.overlay = overlay;

        // 创建抽屉容器
        const drawer = document.createElement('div');
        drawer.className = 'mobile-parameter-drawer mobile-only';
        drawer.style.cssText = `
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            max-height: 70vh;
            background: var(--bg-panel);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-radius: 20px 20px 0 0;
            z-index: 997;
            transform: translateY(100%);
            transition: transform 300ms cubic-bezier(0.4, 0.0, 0.2, 1);
            display: flex;
            flex-direction: column;
            box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.1);
        `;

        // 创建拖拽手柄
        const handle = document.createElement('div');
        handle.className = 'drawer-handle';
        handle.style.cssText = `
            width: 40px;
            height: 4px;
            background: var(--text-secondary);
            border-radius: 2px;
            margin: 12px auto;
            opacity: 0.5;
        `;

        drawer.appendChild(handle);
        this.elements.handle = handle;

        // 创建标题
        const title = document.createElement('div');
        title.className = 'drawer-title';
        title.textContent = '参数设置';
        title.style.cssText = `
            font-size: 18px;
            font-weight: 600;
            text-align: center;
            padding: 8px 16px 16px;
            color: var(--text-primary);
        `;

        drawer.appendChild(title);

        // 创建内容区域
        const content = document.createElement('div');
        content.className = 'drawer-content';
        content.style.cssText = `
            flex: 1;
            overflow-y: auto;
            padding: 0 16px 24px;
        `;

        this.parameters.forEach((param) => {
            const paramItem = this.createParameterItem(param);
            content.appendChild(paramItem);
        });

        drawer.appendChild(content);
        this.elements.content = content;

        document.body.appendChild(drawer);
        this.elements.drawer = drawer;
    }

    /**
     * 创建参数项
     */
    private createParameterItem(param: Parameter): HTMLElement {
        const item = document.createElement('div');
        item.className = 'parameter-item';
        item.style.cssText = `
            margin-bottom: 16px;
            padding: 16px;
            background: var(--bg-secondary);
            border-radius: 12px;
        `;

        // 创建标签
        const label = document.createElement('label');
        label.className = 'parameter-label';
        label.textContent = param.label;
        label.style.cssText = `
            display: block;
            font-size: 14px;
            font-weight: 500;
            color: var(--text-primary);
            margin-bottom: 8px;
        `;

        item.appendChild(label);

        // 根据类型创建输入控件
        if (param.type === 'slider' && typeof param.value === 'number') {
            const sliderContainer = document.createElement('div');
            sliderContainer.style.cssText = `
                display: flex;
                align-items: center;
                gap: 12px;
            `;

            const slider = document.createElement('input');
            slider.type = 'range';
            slider.min = param.min?.toString() || '0';
            slider.max = param.max?.toString() || '100';
            slider.step = param.step?.toString() || '1';
            slider.value = param.value.toString();
            slider.style.cssText = `
                flex: 1;
                width: 100%;
                height: 6px;
                -webkit-appearance: none;
                appearance: none;
                background: var(--border-color);
                border-radius: 3px;
                outline: none;
            `;

            const valueDisplay = document.createElement('span');
            valueDisplay.className = 'parameter-value';
            valueDisplay.textContent = `${param.value}${param.unit || ''}`;
            valueDisplay.style.cssText = `
                min-width: 60px;
                text-align: right;
                font-size: 14px;
                color: var(--text-secondary);
            `;

            slider.addEventListener('input', (e) => {
                const value = parseFloat((e.target as HTMLInputElement).value);
                valueDisplay.textContent = `${value}${param.unit || ''}`;
                if (this.onParameterChange) {
                    this.onParameterChange(param.id, value);
                }
            });

            sliderContainer.appendChild(slider);
            sliderContainer.appendChild(valueDisplay);
            item.appendChild(sliderContainer);
        } else if (param.type === 'select' && param.options) {
            const select = document.createElement('select');
            select.style.cssText = `
                width: 100%;
                padding: 10px 12px;
                font-size: 16px;
                background: var(--bg-panel);
                color: var(--text-primary);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                outline: none;
            `;

            param.options.forEach((option) => {
                const opt = document.createElement('option');
                opt.value = option.value.toString();
                opt.textContent = option.label;
                if (option.value === param.value) {
                    opt.selected = true;
                }
                select.appendChild(opt);
            });

            select.addEventListener('change', (e) => {
                const value = (e.target as HTMLSelectElement).value;
                if (this.onParameterChange) {
                    this.onParameterChange(param.id, value);
                }
            });

            item.appendChild(select);
        } else {
            const input = document.createElement('input');
            input.type = param.type === 'input' ? 'text' : 'number';
            input.value = param.value.toString();
            input.style.cssText = `
                width: 100%;
                padding: 10px 12px;
                font-size: 16px;
                background: var(--bg-panel);
                color: var(--text-primary);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                outline: none;
            `;

            input.addEventListener('change', (e) => {
                const value = (e.target as HTMLInputElement).value;
                if (this.onParameterChange) {
                    this.onParameterChange(param.id, param.type === 'input' ? value : parseFloat(value));
                }
            });

            item.appendChild(input);
        }

        return item;
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        if (!this.enableDrag || !this.elements.drawer || !this.elements.handle) return;

        let isDragging = false;

        this.elements.handle.addEventListener('touchstart', (e: TouchEvent) => {
            isDragging = true;
            this.startY = e.touches[0].clientY;
            this.currentY = this.startY;
        }, { passive: true });

        document.addEventListener('touchmove', (e: TouchEvent) => {
            if (!isDragging) return;

            this.currentY = e.touches[0].clientY;
            const deltaY = this.currentY - this.startY;

            if (deltaY > 0 && this.elements.drawer) {
                this.elements.drawer.style.transition = 'none';
                this.elements.drawer.style.transform = `translateY(${deltaY}px)`;
            }
        }, { passive: true });

        document.addEventListener('touchend', (e: TouchEvent) => {
            if (!isDragging) return;
            isDragging = false;

            const deltaY = this.currentY - this.startY;

            if (deltaY > this.dragThreshold) {
                this.close();
            } else {
                if (this.elements.drawer) {
                    this.elements.drawer.style.transition = 'transform 300ms cubic-bezier(0.4, 0.0, 0.2, 1)';
                    this.elements.drawer.style.transform = this.isOpen ? 'translateY(0)' : 'translateY(100%)';
                }
            }
        });
    }

    /**
     * 触觉反馈
     */
    private hapticFeedback(): void {
        if (!this.enableHaptic) return;

        if ('vibrate' in navigator) {
            navigator.vibrate(10);
        }
    }

    /**
     * 打开抽屉
     */
    public open(): void {
        if (this.elements.drawer && this.elements.overlay) {
            this.elements.drawer.style.transform = 'translateY(0)';
            this.elements.overlay.style.opacity = '1';
            this.elements.overlay.style.pointerEvents = 'auto';
            this.isOpen = true;
            this.hapticFeedback();
        }
    }

    /**
     * 关闭抽屉
     */
    public close(): void {
        if (this.elements.drawer && this.elements.overlay) {
            this.elements.drawer.style.transform = 'translateY(100%)';
            this.elements.overlay.style.opacity = '0';
            this.elements.overlay.style.pointerEvents = 'none';
            this.isOpen = false;
            this.hapticFeedback();
        }
    }

    /**
     * 切换抽屉状态
     */
    public toggle(): void {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    /**
     * 更新参数
     */
    public updateParameters(parameters: Parameter[]): void {
        this.parameters = parameters;
        if (this.elements.content) {
            this.elements.content.innerHTML = '';
            this.parameters.forEach((param) => {
                const paramItem = this.createParameterItem(param);
                this.elements.content?.appendChild(paramItem);
            });
        }
    }

    /**
     * 销毁抽屉
     */
    public destroy(): void {
        if (this.elements.drawer) {
            this.elements.drawer.remove();
        }
        if (this.elements.overlay) {
            this.elements.overlay.remove();
        }
        this.elements.drawer = null;
        this.elements.handle = null;
        this.elements.content = null;
        this.elements.overlay = null;
    }
}

// 导出
export default MobileParameterDrawer;