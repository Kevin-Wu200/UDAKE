/**
 * 参数调整面板组件
 * 实现滑块与输入框的双向绑定
 */

export class ParameterAdjustmentPanel {
    private static instance: ParameterAdjustmentPanel;
    private parameters: Map<string, number> = new Map();

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
        this.bindSlider('grid-resolution', 50, 500);
        this.bindSlider('nlags', 6, 24);
        this.bindSlider('nugget', 0, 1);
        this.bindSlider('sill', 0, 10);
        this.bindSlider('range', 0, 100);

        this.loadSavedParameters();
    }

    /**
     * 绑定滑块和输入框的双向同步
     */
    private bindSlider(paramName: string, min: number, max: number): void {
        const slider = document.getElementById(`${paramName}-slider`) as HTMLInputElement;
        const input = document.getElementById(paramName) as HTMLInputElement;
        const valueDisplay = document.getElementById(`${paramName}-value`) as HTMLElement;

        if (!slider || !input) {
            console.warn(`Slider or input not found for parameter: ${paramName}`);
            return;
        }

        // 滑块变化时更新输入框和显示
        slider.addEventListener('input', () => {
            const value = parseFloat(slider.value);
            input.value = slider.value;
            if (valueDisplay) {
                valueDisplay.textContent = slider.value;
            }
            this.parameters.set(paramName, value);
            this.validateParameter(paramName, value, min, max);
        });

        // 输入框变化时更新滑块和显示
        input.addEventListener('input', () => {
            const value = parseFloat(input.value);
            if (!isNaN(value)) {
                slider.value = input.value;
                if (valueDisplay) {
                    valueDisplay.textContent = input.value;
                }
                this.parameters.set(paramName, value);
                this.validateParameter(paramName, value, min, max);
            }
        });

        // 初始化参数值
        const initialValue = parseFloat(input.value);
        this.parameters.set(paramName, initialValue);
    }

    /**
     * 验证参数值是否在有效范围内
     */
    private validateParameter(paramName: string, value: number, min: number, max: number): void {
        const input = document.getElementById(paramName) as HTMLInputElement;

        if (value < min || value > max) {
            input.classList.add('error');
            this.showParameterWarning(paramName, `参数值必须在 ${min} 到 ${max} 之间`);
        } else {
            input.classList.remove('error');
            this.hideParameterWarning(paramName);
        }

        // 特殊验证：基台值应该大于变差值
        if (paramName === 'nugget' || paramName === 'sill') {
            const nugget = this.parameters.get('nugget') || 0;
            const sill = this.parameters.get('sill') || 1;

            if (nugget >= sill) {
                this.showParameterWarning('sill', '基台值应该大于变差值');
            } else {
                this.hideParameterWarning('sill');
            }
        }
    }

    /**
     * 显示参数警告
     */
    private showParameterWarning(paramName: string, message: string): void {
        let warningEl = document.getElementById(`${paramName}-warning`);

        if (!warningEl) {
            warningEl = document.createElement('div');
            warningEl.id = `${paramName}-warning`;
            warningEl.className = 'parameter-warning';
            warningEl.style.cssText = `
                color: #ff3b30;
                font-size: 12px;
                margin-top: 4px;
                display: none;
            `;

            const input = document.getElementById(paramName);
            if (input) {
                input.parentElement?.appendChild(warningEl);
            }
        }

        warningEl.textContent = message;
        warningEl.style.display = 'block';
    }

    /**
     * 隐藏参数警告
     */
    private hideParameterWarning(paramName: string): void {
        const warningEl = document.getElementById(`${paramName}-warning`);
        if (warningEl) {
            warningEl.style.display = 'none';
        }
    }

    /**
     * 获取所有参数值
     */
    public getParameters(): Record<string, number> {
        return Object.fromEntries(this.parameters);
    }

    /**
     * 设置参数值
     */
    public setParameter(paramName: string, value: number): void {
        const slider = document.getElementById(`${paramName}-slider`) as HTMLInputElement;
        const input = document.getElementById(paramName) as HTMLInputElement;
        const valueDisplay = document.getElementById(`${paramName}-value`) as HTMLElement;

        if (slider) {
            slider.value = value.toString();
        }
        if (input) {
            input.value = value.toString();
        }
        if (valueDisplay) {
            valueDisplay.textContent = value.toString();
        }

        this.parameters.set(paramName, value);
    }

    /**
     * 重置所有参数为默认值
     */
    public resetToDefaults(): void {
        this.setParameter('grid-resolution', 100);
        this.setParameter('nlags', 12);
        this.setParameter('nugget', 0);
        this.setParameter('sill', 1);
        this.setParameter('range', 10);
    }

    /**
     * 保存当前参数到 localStorage
     */
    public saveParameters(name: string): void {
        const savedParameters = JSON.parse(localStorage.getItem('savedParameters') || '[]');

        savedParameters.push({
            id: Date.now().toString(),
            name: name || `参数组合 ${savedParameters.length + 1}`,
            parameters: this.getParameters(),
            timestamp: new Date().toISOString()
        });

        localStorage.setItem('savedParameters', JSON.stringify(savedParameters));
    }

    /**
     * 加载保存的参数
     */
    private loadSavedParameters(): void {
        const lastUsed = localStorage.getItem('lastUsedParameters');
        if (lastUsed) {
            try {
                const parameters = JSON.parse(lastUsed);
                Object.entries(parameters).forEach(([key, value]) => {
                    if (typeof value === 'number') {
                        this.setParameter(key, value as number);
                    }
                });
            } catch (error) {
                console.warn('Failed to load saved parameters:', error);
            }
        }
    }

    /**
     * 将当前参数保存为最后使用的参数
     */
    public saveAsLastUsed(): void {
        localStorage.setItem('lastUsedParameters', JSON.stringify(this.getParameters()));
    }

    /**
     * 验证所有参数是否有效
     */
    public validateAll(): { valid: boolean; errors: string[] } {
        const errors: string[] = [];
        const nugget = this.parameters.get('nugget') || 0;
        const sill = this.parameters.get('sill') || 1;

        if (nugget >= sill) {
            errors.push('基台值应该大于变差值');
        }

        return {
            valid: errors.length === 0,
            errors
        };
    }
}