/**
 * DroneHUDOverlay 组件
 * 无人机视角 HUD 遮罩: 十字准星、高度计、坐标实时显示
 *
 * 特性:
 * - 中心十字准星(始终跟随相机)
 * - 右下角高度计(实时海拔)
 * - 左上角坐标面板(经纬度 + 置信度)
 * - 左上角飞行模式指示器
 * - 半透明遮罩，不影响地图交互
 */

export interface HUDData {
    /** 当前经度 */
    longitude: number;
    /** 当前纬度 */
    latitude: number;
    /** 当前高度(米) */
    altitude: number;
    /** 相机朝向角(度, 0=北) */
    heading: number;
    /** 相机俯仰角(度, 0=水平, 90=垂直向下) */
    tilt: number;
    /** 当前缩放级别 */
    zoom: number;
    /** 置信度值 [0, 1] */
    confidence: number;
    /** 置信度是否达到解锁阈值 */
    confidenceUnlocked: boolean;
    /** 飞行模式: 'auto'=自动盘旋 | 'manual'=手动操控 */
    flightMode: 'auto' | 'manual';
    /** 自动盘旋圆心经度(仅 auto 模式) */
    orbitCenterLon?: number;
    /** 自动盘旋圆心纬度(仅 auto 模式) */
    orbitCenterLat?: number;
    /** 自动盘旋半径(米, 仅 auto 模式) */
    orbitRadius?: number;
}

export interface DroneHUDConfig {
    container: HTMLElement;
    /** 置信度解锁阈值, 默认 0.85 */
    confidenceThreshold?: number;
}

export class DroneHUDOverlay {
    private container: HTMLElement;
    private overlay!: HTMLElement;
    private crosshair!: HTMLElement;
    private altimeter!: HTMLElement;
    private altimeterBar!: HTMLElement;
    private coordPanel!: HTMLElement;
    private modeIndicator!: HTMLElement;
    private confidenceBar!: HTMLElement;
    private confidenceBarFill!: HTMLElement;
    private confidenceLabel!: HTMLElement;
    private confidenceThreshold: number;
    private data: HUDData | null = null;

    constructor(config: DroneHUDConfig) {
        this.container = config.container;
        this.confidenceThreshold = config.confidenceThreshold ?? 0.85;
        this.createOverlay();
    }

    private createOverlay(): void {
        // 主遮罩容器
        this.overlay = document.createElement('div');
        this.overlay.id = 'drone-hud-overlay';
        this.overlay.style.cssText = `
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            pointer-events: none;
            z-index: 500;
            overflow: hidden;
        `;

        // ── 十字准星 (中心) ──
        this.crosshair = document.createElement('div');
        this.crosshair.style.cssText = `
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            width: 60px; height: 60px;
        `;
        this.crosshair.innerHTML = `
            <svg width="60" height="60" viewBox="0 0 60 60">
                <!-- 外圆 -->
                <circle cx="30" cy="30" r="22" fill="none" stroke="rgba(0,255,100,0.6)" stroke-width="1.5" stroke-dasharray="4,3"/>
                <!-- 水平线 -->
                <line x1="0" y1="30" x2="12" y2="30" stroke="rgba(0,255,100,0.8)" stroke-width="1.5"/>
                <line x1="48" y1="30" x2="60" y2="30" stroke="rgba(0,255,100,0.8)" stroke-width="1.5"/>
                <!-- 垂直线 -->
                <line x1="30" y1="0" x2="30" y2="12" stroke="rgba(0,255,100,0.8)" stroke-width="1.5"/>
                <line x1="30" y1="48" x2="30" y2="60" stroke="rgba(0,255,100,0.8)" stroke-width="1.5"/>
                <!-- 中心点 -->
                <circle cx="30" cy="30" r="2" fill="rgba(0,255,100,0.9)"/>
            </svg>
        `;
        this.overlay.appendChild(this.crosshair);

        // ── 左上角: 飞行模式指示器 ──
        this.modeIndicator = document.createElement('div');
        this.modeIndicator.style.cssText = `
            position: absolute;
            top: 16px; left: 16px;
            background: rgba(0,0,0,0.55);
            color: #0f0;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            font-weight: bold;
            padding: 6px 12px;
            border-radius: 4px;
            border: 1px solid rgba(0,255,100,0.3);
            letter-spacing: 1px;
        `;
        this.modeIndicator.textContent = '🛩️ AUTO';
        this.overlay.appendChild(this.modeIndicator);

        // ── 左上角第二行: 坐标面板 ──
        this.coordPanel = document.createElement('div');
        this.coordPanel.style.cssText = `
            position: absolute;
            top: 52px; left: 16px;
            background: rgba(0,0,0,0.55);
            color: #0f0;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            padding: 6px 12px;
            border-radius: 4px;
            border: 1px solid rgba(0,255,100,0.3);
            line-height: 1.5;
        `;
        this.coordPanel.innerHTML = `
            <div>LON: --</div>
            <div>LAT: --</div>
            <div>ALT: -- m</div>
            <div>HDG: --°</div>
        `;
        this.overlay.appendChild(this.coordPanel);

        // ── 左上角第三行: 置信度条 ──
        this.confidenceBar = document.createElement('div');
        this.confidenceBar.style.cssText = `
            position: absolute;
            top: 148px; left: 16px;
            width: 180px; height: 6px;
            background: rgba(255,255,255,0.15);
            border-radius: 3px;
            overflow: hidden;
        `;
        this.confidenceBarFill = document.createElement('div');
        this.confidenceBarFill.style.cssText = `
            height: 100%;
            width: 0%;
            background: #ff4444;
            border-radius: 3px;
            transition: width 0.3s, background 0.3s;
        `;
        this.confidenceBar.appendChild(this.confidenceBarFill);
        this.overlay.appendChild(this.confidenceBar);

        this.confidenceLabel = document.createElement('div');
        this.confidenceLabel.style.cssText = `
            position: absolute;
            top: 158px; left: 16px;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            color: rgba(255,255,255,0.7);
        `;
        this.confidenceLabel.textContent = '置信度: --';
        this.overlay.appendChild(this.confidenceLabel);

        // ── 右下角: 高度计 ──
        this.altimeter = document.createElement('div');
        this.altimeter.style.cssText = `
            position: absolute;
            bottom: 24px; right: 24px;
            width: 70px; height: 180px;
            background: rgba(0,0,0,0.55);
            border-radius: 8px;
            border: 1px solid rgba(0,255,100,0.3);
            overflow: hidden;
        `;

        // 高度刻度条(填充效果)
        this.altimeterBar = document.createElement('div');
        this.altimeterBar.style.cssText = `
            position: absolute;
            bottom: 0; left: 0; right: 0;
            height: 0%;
            background: linear-gradient(to top, rgba(0,255,100,0.3), rgba(0,255,100,0.05));
            border-radius: 0 0 8px 8px;
            transition: height 0.2s;
        `;
        this.altimeter.appendChild(this.altimeterBar);

        // 高度标签
        const altLabel = document.createElement('div');
        altLabel.style.cssText = `
            position: absolute;
            bottom: 8px; left: 0; right: 0;
            text-align: center;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            font-weight: bold;
            color: #0f0;
        `;
        altLabel.textContent = 'ALT';
        this.altimeter.appendChild(altLabel);

        const altValue = document.createElement('div');
        altValue.style.cssText = `
            position: absolute;
            bottom: 26px; left: 0; right: 0;
            text-align: center;
            font-family: 'Courier New', monospace;
            font-size: 16px;
            font-weight: bold;
            color: #0f0;
        `;
        altValue.id = 'drone-hud-alt-value';
        altValue.textContent = '--';
        this.altimeter.appendChild(altValue);

        const altUnit = document.createElement('div');
        altUnit.style.cssText = `
            position: absolute;
            bottom: 44px; left: 0; right: 0;
            text-align: center;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            color: rgba(255,255,255,0.5);
        `;
        altUnit.textContent = 'm';
        this.altimeter.appendChild(altUnit);

        this.overlay.appendChild(this.altimeter);

        // 右上角: 相机参数简表
        const camInfo = document.createElement('div');
        camInfo.style.cssText = `
            position: absolute;
            top: 16px; right: 16px;
            background: rgba(0,0,0,0.55);
            color: rgba(255,255,255,0.6);
            font-family: 'Courier New', monospace;
            font-size: 11px;
            padding: 6px 10px;
            border-radius: 4px;
            border: 1px solid rgba(255,255,255,0.1);
            line-height: 1.6;
        `;
        camInfo.innerHTML = `
            <div>TILT: <span id="drone-hud-tilt" style="color:#0f0">--°</span></div>
            <div>ZOOM: <span id="drone-hud-zoom" style="color:#0f0">--</span></div>
            <div>ORBIT: <span id="drone-hud-orbit" style="color:#0f0">--</span></div>
        `;
        this.overlay.appendChild(camInfo);

        this.container.appendChild(this.overlay);
    }

    /**
     * 更新 HUD 显示数据
     */
    public update(data: HUDData): void {
        this.data = data;

        // 坐标面板
        this.coordPanel.innerHTML = `
            <div>LON: ${data.longitude.toFixed(6)}</div>
            <div>LAT: ${data.latitude.toFixed(6)}</div>
            <div>ALT: ${data.altitude.toFixed(1)} m</div>
            <div>HDG: ${data.heading.toFixed(1)}°</div>
        `;

        // 飞行模式
        const modeText = data.flightMode === 'auto' ? '🛩️ AUTO' : '🎮 MANUAL';
        const modeColor = data.flightMode === 'auto' ? '#0ff' : '#ff0';
        this.modeIndicator.textContent = modeText;
        this.modeIndicator.style.color = modeColor;

        // 置信度条
        const confPercent = Math.round(data.confidence * 100);
        this.confidenceBarFill.style.width = `${confPercent}%`;
        this.confidenceBarFill.style.background = data.confidenceUnlocked ? '#00ff64' : '#ff4444';
        this.confidenceLabel.textContent =
            `置信度: ${confPercent}%` +
            (data.confidenceUnlocked ? ' ✅' : ` ⚠️ 需≥${Math.round(this.confidenceThreshold * 100)}%`);

        // 高度计
        const maxAlt = 5000; // 假设最大高度5000m
        const altPercent = Math.min(100, (data.altitude / maxAlt) * 100);
        this.altimeterBar.style.height = `${altPercent}%`;
        const altValue = document.getElementById('drone-hud-alt-value');
        if (altValue) altValue.textContent = data.altitude.toFixed(0);

        // 右上角相机参数
        const tiltEl = document.getElementById('drone-hud-tilt');
        const zoomEl = document.getElementById('drone-hud-zoom');
        const orbitEl = document.getElementById('drone-hud-orbit');
        if (tiltEl) tiltEl.textContent = `${data.tilt.toFixed(1)}°`;
        if (zoomEl) zoomEl.textContent = data.zoom.toFixed(1);
        if (orbitEl) {
            orbitEl.textContent = data.flightMode === 'auto' && data.orbitRadius != null
                ? `R${data.orbitRadius.toFixed(0)}m`
                : '--';
        }
    }

    /**
     * 显示/隐藏 HUD
     */
    public setVisible(visible: boolean): void {
        this.overlay.style.display = visible ? 'block' : 'none';
    }

    /**
     * 获取置信度阈值
     */
    public getConfidenceThreshold(): number {
        return this.confidenceThreshold;
    }

    /**
     * 设置置信度阈值
     */
    public setConfidenceThreshold(threshold: number): void {
        this.confidenceThreshold = Math.max(0, Math.min(1, threshold));
    }

    /**
     * 销毁 HUD
     */
    public destroy(): void {
        this.overlay.remove();
    }
}
