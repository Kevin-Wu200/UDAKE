/**
 * 地图引擎切换器组件
 * 允许用户在 ArcGIS 和高德地图之间切换
 */

/**
 * 地图引擎切换器组件
 */
export class MapEngineSwitcher {
    /** 切换按钮元素 */
    private button: HTMLElement | null = null;

    /** 当前地图引擎 */
    private currentProvider: 'geoscene' | 'amap' = 'geoscene';

    /** 切换回调函数 */
    private onSwitch: ((provider: 'geoscene' | 'amap') => Promise<void>) | null = null;

    /** 是否正在切换 */
    private isSwitching: boolean = false;

    constructor(
        currentProvider: 'geoscene' | 'amap' = 'geoscene',
        onSwitch?: (provider: 'geoscene' | 'amap') => Promise<void>
    ) {
        this.currentProvider = currentProvider;
        this.onSwitch = onSwitch || null;
    }

    /**
     * 创建切换按钮
     */
    createButton(): HTMLElement {
        this.button = document.createElement('div');
        this.button.className = 'map-engine-switcher';
        this.button.title = '切换地图引擎';

        // 样式
        this.button.style.cssText = `
            position: absolute;
            top: 16px;
            right: 100px;
            padding: 8px 16px;
            border-radius: 20px;
            background: rgba(255, 255, 255, 0.95);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            color: #333;
            z-index: 9999;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(0, 0, 0, 0.08);
            gap: 6px;
        `;

        // 图标
        const icon = document.createElement('span');
        icon.innerHTML = '🗺️';
        icon.style.fontSize = '16px';

        // 文本
        const text = document.createElement('span');
        text.className = 'switcher-text';
        this.updateButtonText(text);

        // 添加到按钮
        this.button.appendChild(icon);
        this.button.appendChild(text);

        // Hover 效果
        this.button.addEventListener('mouseenter', () => {
            if (!this.isSwitching && this.button) {
                this.button.style.background = 'rgba(255, 255, 255, 1)';
                this.button.style.transform = 'translateY(-2px)';
                this.button.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.2)';
            }
        });

        this.button.addEventListener('mouseleave', () => {
            if (!this.isSwitching && this.button) {
                this.button.style.background = 'rgba(255, 255, 255, 0.95)';
                this.button.style.transform = 'translateY(0)';
                this.button.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.15)';
            }
        });

        // 点击事件
        this.button.addEventListener('click', () => this.handleClick());

        return this.button;
    }

    /**
     * 更新按钮文本
     */
    private updateButtonText(textElement: HTMLElement): void {
        const engineName = this.currentProvider === 'geoscene' ? 'GeoScene' : '高德';
        textElement.textContent = `${engineName}`;
    }

    /**
     * 处理点击事件
     */
    private async handleClick(): Promise<void> {
        if (this.isSwitching || !this.onSwitch) {
            return;
        }

        const newProvider: 'geoscene' | 'amap' = this.currentProvider === 'geoscene' ? 'amap' : 'geoscene';

        // 更新状态
        this.isSwitching = true;
        this.updateButtonState();

        try {
            // 调用切换回调
            await this.onSwitch(newProvider);

            // 更新当前提供商
            this.currentProvider = newProvider;

            // 更新按钮文本
            const textElement = this.button?.querySelector('.switcher-text') as HTMLElement;
            if (textElement) {
                this.updateButtonText(textElement);
            }

            // 显示成功状态
            this.showSuccessState();

            // 2秒后恢复正常状态
            setTimeout(() => {
                this.isSwitching = false;
                this.updateButtonState();
            }, 2000);

        } catch (error) {
            console.error('地图引擎切换失败:', error);
            this.showErrorState();

            // 2秒后恢复正常状态
            setTimeout(() => {
                this.isSwitching = false;
                this.updateButtonState();
            }, 2000);
        }
    }

    /**
     * 更新按钮状态
     */
    private updateButtonState(): void {
        if (!this.button) return;

        if (this.isSwitching) {
            // 切换中状态
            this.button.style.opacity = '0.6';
            this.button.style.cursor = 'not-allowed';
            this.button.style.pointerEvents = 'none';
            this.button.setAttribute('aria-disabled', 'true');
        } else {
            // 正常状态
            this.button.style.opacity = '1';
            this.button.style.cursor = 'pointer';
            this.button.style.pointerEvents = 'auto';
            this.button.removeAttribute('aria-disabled');
        }
    }

    /**
     * 显示成功状态
     */
    private showSuccessState(): void {
        if (!this.button) return;

        const textElement = this.button.querySelector('.switcher-text') as HTMLElement;
        if (textElement) {
            textElement.textContent = '✅ 已切换';
            textElement.style.color = '#10B981';
        }

        this.button.style.borderColor = '#10B981';
    }

    /**
     * 显示错误状态
     */
    private showErrorState(): void {
        if (!this.button) return;

        const textElement = this.button.querySelector('.switcher-text') as HTMLElement;
        if (textElement) {
            textElement.textContent = '❌ 失败';
            textElement.style.color = '#EF4444';
        }

        this.button.style.borderColor = '#EF4444';
    }

    /**
     * 设置切换回调
     */
    setOnSwitch(callback: (provider: 'geoscene' | 'amap') => Promise<void>): void {
        this.onSwitch = callback;
    }

    /**
     * 更新当前提供商
     */
    setCurrentProvider(provider: 'geoscene' | 'amap'): void {
        this.currentProvider = provider;

        const textElement = this.button?.querySelector('.switcher-text') as HTMLElement;
        if (textElement) {
            this.updateButtonText(textElement);
        }
    }

    /**
     * 添加到指定容器
     */
    addToContainer(container: HTMLElement | string): void {
        const containerElement = typeof container === 'string'
            ? document.getElementById(container)
            : container;

        if (!containerElement) {
            console.error('找不到容器元素');
            return;
        }

        console.log('🗺️ 创建地图引擎切换按钮...');
        const button = this.createButton();
        containerElement.appendChild(button);
        console.log('✅ 地图引擎切换按钮已添加到容器');
    }

    /**
     * 销毁组件
     */
    destroy(): void {
        if (this.button && this.button.parentNode) {
            this.button.parentNode.removeChild(this.button);
        }
        this.button = null;
        this.onSwitch = null;
    }
}
