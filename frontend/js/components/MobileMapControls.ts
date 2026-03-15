/**
 * 移动端地图控制组件
 * 底部浮动按钮，提供缩放、定位、图层切换等功能
 */

import './config/主题变量';

interface MapControlAction {
    id: string;
    icon: string;
    label: string;
    action: () => void;
    enabled?: boolean;
}

interface MobileMapControlsOptions {
    controls: MapControlAction[];
    position?: 'bottom-left' | 'bottom-right' | 'bottom-center';
    enableHaptic?: boolean;
}

class MobileMapControls {
    private controls: MapControlAction[];
    private position: string;
    private enableHaptic: boolean;
    private elements: HTMLElement[] = [];

    constructor(options: MobileMapControlsOptions) {
        this.controls = options.controls;
        this.position = options.position || 'bottom-right';
        this.enableHaptic = options.enableHaptic ?? true;
        this.init();
    }

    /**
     * 初始化地图控制
     */
    private init(): void {
        this.createControls();
        this.bindEvents();
    }

    /**
     * 创建控制按钮
     */
    private createControls(): void {
        const mapContainer = document.querySelector('.map-container');
        if (!mapContainer) return;

        const controlsContainer = document.createElement('div');
        controlsContainer.className = `mobile-map-controls mobile-only ${this.position}`;

        this.controls.forEach((control) => {
            const button = document.createElement('button');
            button.className = `map-control-btn ${control.enabled === false ? 'disabled' : ''}`;
            button.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    ${control.icon}
                </svg>
                <span class="control-label">${control.label}</span>
            `;
            button.setAttribute('aria-label', control.label);
            button.dataset.controlId = control.id;

            button.addEventListener('click', (e) => {
                e.stopPropagation();
                if (control.enabled !== false) {
                    control.action();
                    this.hapticFeedback();
                }
            });

            button.addEventListener('touchstart', (_e) => {
                if (control.enabled !== false) {
                    button.classList.add('active');
                }
            });

            button.addEventListener('touchend', () => {
                button.classList.remove('active');
            });

            controlsContainer.appendChild(button);
            this.elements.push(button);
        });

        mapContainer.appendChild(controlsContainer);
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        // 阻止控制按钮的默认行为
        this.elements.forEach((element) => {
            element.addEventListener('touchstart', (e) => {
                e.preventDefault();
            }, { passive: false });
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
     * 更新控制按钮状态
     */
    public updateControlState(controlId: string, enabled: boolean): void {
        const button = this.elements.find(el => el.dataset.controlId === controlId);
        if (button) {
            if (enabled) {
                button.classList.remove('disabled');
            } else {
                button.classList.add('disabled');
            }
        }
    }

    /**
     * 更新所有控制
     */
    public updateControls(controls: MapControlAction[]): void {
        this.controls = controls;
        this.elements.forEach(el => el.remove());
        this.elements = [];

        const controlsContainer = document.querySelector('.mobile-map-controls');
        if (controlsContainer) {
            controlsContainer.remove();
        }

        this.createControls();
        this.bindEvents();
    }

    /**
     * 显示控制
     */
    public show(): void {
        const controlsContainer = document.querySelector('.mobile-map-controls');
        if (controlsContainer) {
            (controlsContainer as HTMLElement).style.display = 'flex';
        }
    }

    /**
     * 隐藏控制
     */
    public hide(): void {
        const controlsContainer = document.querySelector('.mobile-map-controls');
        if (controlsContainer) {
            (controlsContainer as HTMLElement).style.display = 'none';
        }
    }

    /**
     * 销毁控制
     */
    public destroy(): void {
        this.elements.forEach(el => el.remove());
        this.elements = [];

        const controlsContainer = document.querySelector('.mobile-map-controls');
        if (controlsContainer) {
            controlsContainer.remove();
        }
    }
}

// 导出
export default MobileMapControls;