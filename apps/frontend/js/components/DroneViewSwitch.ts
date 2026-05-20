/**
 * 无人机视角开关组件 (DroneViewSwitch.ts)
 *
 * 在主控制面板中增加"无人机视角"开关及模式选择器
 * 包含:
 * - 无人机视角启用/禁用开关
 * - 飞行模式选择器 (自动盘旋 / 手动操控)
 * - 置信度阈值显示
 */

export type FlightMode = 'auto' | 'manual';

export interface DroneViewSwitchConfig {
    container: HTMLElement;
    /** 置信度解锁阈值, 默认 0.85 */
    confidenceThreshold?: number;
    /** 当前置信度值 */
    confidence?: number;
    /** 是否启用无人机视角 */
    enabled?: boolean;
    /** 当前飞行模式 */
    flightMode?: FlightMode;
    /** 启用状态变化回调 */
    onToggle?: (enabled: boolean) => void;
    /** 飞行模式变化回调 */
    onFlightModeChange?: (mode: FlightMode) => void;
    /** 自动盘旋参数变化回调 */
    onOrbitParamsChange?: (params: { centerLon: number; centerLat: number; radius: number; pitchAngle: number }) => void;
}

export class DroneViewSwitch {
    private config: Required<Omit<DroneViewSwitchConfig, 'onToggle' | 'onFlightModeChange' | 'onOrbitParamsChange'>> & {
        onToggle: (enabled: boolean) => void;
        onFlightModeChange: (mode: FlightMode) => void;
        onOrbitParamsChange: (params: { centerLon: number; centerLat: number; radius: number; pitchAngle: number }) => void;
    };
    private panel: HTMLElement;
    private toggleSwitch!: HTMLElement;
    private modeSelector!: HTMLElement;
    private orbitParamsPanel!: HTMLElement;
    private enabled: boolean;
    private flightMode: FlightMode;

    constructor(config: DroneViewSwitchConfig) {
        this.config = {
            confidenceThreshold: 0.85,
            confidence: 0,
            enabled: false,
            flightMode: 'auto',
            onToggle: () => {},
            onFlightModeChange: () => {},
            onOrbitParamsChange: () => {},
            ...config,
            container: config.container,
        };
        this.enabled = this.config.enabled;
        this.flightMode = this.config.flightMode;
        this.panel = document.createElement('div');
        this.createPanel();
    }

    private createPanel(): void {
        this.panel.className = 'drone-view-switch-panel';
        this.panel.style.cssText = `
            background: var(--panel-bg, rgba(30,30,40,0.95));
            border: 1px solid var(--border-color, rgba(255,255,255,0.1));
            border-radius: 10px;
            padding: 16px;
            font-size: 13px;
            color: #ccc;
            min-width: 220px;
            backdrop-filter: blur(8px);
        `;

        // 标题行
        const header = document.createElement('div');
        header.style.cssText = `
            display: flex; align-items: center; justify-content: space-between;
            margin-bottom: 12px; font-weight: bold; font-size: 14px;
            color: #fff;
        `;
        header.innerHTML = '<span>🛩️ 无人机视角</span>';

        // 开关
        this.toggleSwitch = document.createElement('button');
        this.toggleSwitch.style.cssText = `
            width: 48px; height: 26px; border-radius: 13px;
            border: none; cursor: pointer; transition: background 0.3s;
            position: relative;
            background: ${this.enabled ? '#00cc66' : 'rgba(255,255,255,0.15)'};
        `;
        this.toggleSwitch.innerHTML = `
            <span style="
                display: block; width: 20px; height: 20px; border-radius: 50%;
                background: white; position: absolute; top: 3px;
                left: ${this.enabled ? '25px' : '3px'};
                transition: left 0.3s;
            "></span>
        `;
        this.toggleSwitch.addEventListener('click', () => this.toggleEnabled());
        header.appendChild(this.toggleSwitch);
        this.panel.appendChild(header);

        // 置信度信息行
        const confRow = document.createElement('div');
        confRow.style.cssText = 'margin-bottom: 10px; font-size: 12px; color: #999;';
        confRow.id = 'drone-view-confidence-info';
        confRow.textContent = `置信度: ${Math.round(this.config.confidence * 100)}% (阈值: ${Math.round(this.config.confidenceThreshold * 100)}%)`;
        this.panel.appendChild(confRow);

        // 模式选择器
        this.modeSelector = document.createElement('div');
        this.modeSelector.style.cssText = 'display: flex; gap: 6px; margin-bottom: 10px;';

        const autoBtn = this.createModeButton('auto', '🔄 自动盘旋');
        const manualBtn = this.createModeButton('manual', '🎮 手动操控');
        this.modeSelector.appendChild(autoBtn);
        this.modeSelector.appendChild(manualBtn);
        this.panel.appendChild(this.modeSelector);

        // 自动盘旋参数面板
        this.orbitParamsPanel = document.createElement('div');
        this.orbitParamsPanel.style.cssText = `
            display: ${this.flightMode === 'auto' ? 'block' : 'none'};
            font-size: 12px; padding: 8px;
            background: rgba(0,0,0,0.2);
            border-radius: 6px;
            margin-top: 6px;
        `;
        this.orbitParamsPanel.innerHTML = `
            <div style="margin-bottom:6px;">
                <label style="color:#999;">圆心经度</label>
                <input id="drone-orbit-lon" type="number" step="0.000001" value="116.39"
                    style="width:100%;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);color:#fff;padding:4px;border-radius:4px;margin-top:2px;font-size:12px;">
            </div>
            <div style="margin-bottom:6px;">
                <label style="color:#999;">圆心纬度</label>
                <input id="drone-orbit-lat" type="number" step="0.000001" value="39.90"
                    style="width:100%;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);color:#fff;padding:4px;border-radius:4px;margin-top:2px;font-size:12px;">
            </div>
            <div style="margin-bottom:6px;">
                <label style="color:#999;">盘旋半径 (m)</label>
                <input id="drone-orbit-radius" type="number" step="100" value="500" min="50" max="5000"
                    style="width:100%;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);color:#fff;padding:4px;border-radius:4px;margin-top:2px;font-size:12px;">
            </div>
            <div style="margin-bottom:6px;">
                <label style="color:#999;">俯仰角 (°)</label>
                <input id="drone-orbit-pitch" type="number" step="1" value="45" min="10" max="80"
                    style="width:100%;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);color:#fff;padding:4px;border-radius:4px;margin-top:2px;font-size:12px;">
            </div>
            <button id="drone-orbit-apply"
                style="width:100%;padding:6px;background:rgba(0,255,100,0.2);border:1px solid rgba(0,255,100,0.3);color:#0f0;border-radius:4px;cursor:pointer;font-size:12px;margin-top:4px;">
                应用盘旋参数
            </button>
        `;
        this.panel.appendChild(this.orbitParamsPanel);

        // 绑定盘旋参数应用按钮
        setTimeout(() => {
            const applyBtn = this.panel.querySelector('#drone-orbit-apply');
            if (applyBtn) {
                applyBtn.addEventListener('click', () => this.applyOrbitParams());
            }
        }, 0);

        this.config.container.appendChild(this.panel);
        this.updateEnabledState();
    }

    private createModeButton(mode: FlightMode, label: string): HTMLButtonElement {
        const btn = document.createElement('button');
        const isActive = mode === this.flightMode;
        btn.style.cssText = `
            flex: 1; padding: 7px 4px; border-radius: 6px;
            border: 1px solid ${isActive ? 'rgba(0,255,100,0.5)' : 'rgba(255,255,255,0.1)'};
            background: ${isActive ? 'rgba(0,255,100,0.15)' : 'rgba(255,255,255,0.05)'};
            color: ${isActive ? '#0f0' : '#999'};
            cursor: pointer; font-size: 12px; transition: all 0.2s;
        `;
        btn.textContent = label;
        btn.addEventListener('click', () => {
            this.setFlightMode(mode);
        });
        return btn;
    }

    private toggleEnabled(): void {
        this.enabled = !this.enabled;
        this.updateEnabledState();
        this.config.onToggle(this.enabled);
    }

    private updateEnabledState(): void {
        // 更新开关UI
        const knob = this.toggleSwitch.querySelector('span');
        if (knob) {
            knob.style.left = this.enabled ? '25px' : '3px';
        }
        this.toggleSwitch.style.background = this.enabled ? '#00cc66' : 'rgba(255,255,255,0.15)';

        // 子控件可用性
        this.modeSelector.style.opacity = this.enabled ? '1' : '0.4';
        this.modeSelector.style.pointerEvents = this.enabled ? 'auto' : 'none';
        this.orbitParamsPanel.style.opacity = this.enabled ? '1' : '0.4';
        this.orbitParamsPanel.style.pointerEvents = this.enabled ? 'auto' : 'none';
    }

    private setFlightMode(mode: FlightMode): void {
        this.flightMode = mode;

        // 更新模式按钮
        const buttons = this.modeSelector.querySelectorAll('button');
        const modes: FlightMode[] = ['auto', 'manual'];
        buttons.forEach((btn, i) => {
            const isActive = modes[i] === mode;
            btn.style.background = isActive ? 'rgba(0,255,100,0.15)' : 'rgba(255,255,255,0.05)';
            btn.style.color = isActive ? '#0f0' : '#999';
            btn.style.borderColor = isActive ? 'rgba(0,255,100,0.5)' : 'rgba(255,255,255,0.1)';
        });

        // 显示/隐藏自动盘旋参数
        this.orbitParamsPanel.style.display = mode === 'auto' ? 'block' : 'none';

        this.config.onFlightModeChange(mode);
    }

    private applyOrbitParams(): void {
        const lonEl = this.panel.querySelector('#drone-orbit-lon') as HTMLInputElement;
        const latEl = this.panel.querySelector('#drone-orbit-lat') as HTMLInputElement;
        const radiusEl = this.panel.querySelector('#drone-orbit-radius') as HTMLInputElement;
        const pitchEl = this.panel.querySelector('#drone-orbit-pitch') as HTMLInputElement;

        const params = {
            centerLon: parseFloat(lonEl?.value || '116.39'),
            centerLat: parseFloat(latEl?.value || '39.90'),
            radius: parseFloat(radiusEl?.value || '500'),
            pitchAngle: parseFloat(pitchEl?.value || '45'),
        };

        this.config.onOrbitParamsChange(params);
    }

    /** 更新置信度显示 */
    public updateConfidence(confidence: number): void {
        this.config.confidence = confidence;
        const infoRow = this.panel.querySelector('#drone-view-confidence-info');
        if (infoRow) {
            const unlocked = confidence >= this.config.confidenceThreshold;
            infoRow.innerHTML = `置信度: <span style="color:${unlocked ? '#0f0' : '#f44'}">${Math.round(confidence * 100)}%</span> (阈值: ${Math.round(this.config.confidenceThreshold * 100)}%)`;
        }
    }

    /** 获取当前是否启用 */
    public isEnabled(): boolean {
        return this.enabled;
    }

    /** 获取当前飞行模式 */
    public getFlightMode(): FlightMode {
        return this.flightMode;
    }

    /** 程序化设置开关状态 */
    public setEnabled(enabled: boolean): void {
        if (this.enabled !== enabled) {
            this.toggleEnabled();
        }
    }

    /** 销毁组件 */
    public destroy(): void {
        this.panel.remove();
    }
}
