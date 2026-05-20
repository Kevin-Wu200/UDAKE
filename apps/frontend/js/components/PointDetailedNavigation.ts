/**
 * 点位精确导航组件 (AirTag 模式)
 * 提供全屏沉浸式箭头导航，集成实时位置、罗盘和触觉反馈
 */
import { RuntimeLifecycle, type LifecycleScope } from '../utils/RuntimeLifecycle';
import { Logger } from '../utils/Logger';
import { locationService } from '../services/LocationService';
import { sensorManager } from '../services/SensorManager';
import type {
  LocationData,
  OrientationData,
  NavigationTarget,
  NavigationState,
  NavigationFeedbackLevel,
} from '../types/sensor';

/** 导航反馈颜色等级配置 */
interface FeedbackColorConfig {
  level: NavigationFeedbackLevel;
  color: string;
  label: string;
}

/** 导航组件配置 */
interface NavigationConfig {
  /** 到达判定距离（米），默认 2m */
  arrivalDistanceM: number;
  /** 近距判定距离（米），默认 5m */
  nearDistanceM: number;
  /** 远距判定距离（米），默认 30m */
  farDistanceM: number;
  /** GPS 精度警告阈值（米），默认 20m */
  accuracyWarningM: number;
  /** 震动强度配置 */
  hapticConfig: {
    farIntervalMs: number;
    guidingIntervalMs: number;
    nearIntervalMs: number;
    farDurationMs: number;
    guidingDurationMs: number;
    nearDurationMs: number;
  };
}

const DEFAULT_CONFIG: NavigationConfig = {
  arrivalDistanceM: 2,
  nearDistanceM: 5,
  farDistanceM: 30,
  accuracyWarningM: 20,
  hapticConfig: {
    farIntervalMs: 3000,
    guidingIntervalMs: 1500,
    nearIntervalMs: 500,
    farDurationMs: 30,
    guidingDurationMs: 50,
    nearDurationMs: 100,
  },
};

const FEEDBACK_COLORS: FeedbackColorConfig[] = [
  { level: 'no_signal', color: '#8E8E93', label: '无信号' },
  { level: 'far', color: '#007AFF', label: '远距' },
  { level: 'guiding', color: '#FF9500', label: '引导中' },
  { level: 'near', color: '#FF9500', label: '接近' },
  { level: 'arrived', color: '#34C759', label: '已到达' },
];

/** 箭头SVG路径 - 指向上方的导航箭头，使用CSS变量控制颜色 */
const ARROW_SVG = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120" fill="none">
  <path d="M50 8 L8 88 L50 72 L92 88 Z"
        stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  <line x1="50" y1="88" x2="50" y2="112" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>
</svg>`;

const ARRIVED_SVG = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="none">
  <circle cx="50" cy="50" r="40" stroke="currentColor" stroke-width="4"/>
  <path d="M32 50 L45 63 L68 38" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;

export class PointDetailedNavigation {
  private target: NavigationTarget;
  private config: NavigationConfig;
  private lifecycleScope: LifecycleScope;
  private state: NavigationState = 'idle';

  // DOM元素
  private overlayEl: HTMLElement | null = null;
  private arrowRotatorEl: HTMLElement | null = null; // 外层旋转容器
  private arrowInnerEl: HTMLElement | null = null;   // 内层脉冲动画容器
  private arrowEl: HTMLElement | null = null;         // 箭头SVG容器
  private distanceEl: HTMLElement | null = null;
  private infoEl: HTMLElement | null = null;
  private statusEl: HTMLElement | null = null;
  private closeBtnEl: HTMLElement | null = null;
  private accuracyBadgeEl: HTMLElement | null = null;

  // 传感器数据
  private currentLocation: LocationData | null = null;
  private currentHeading: number | null = null;
  private targetBearing: number | null = null;
  private currentDistance: number | null = null;
  private hasCompass: boolean = true;

  // 触觉反馈
  private hapticTimer: number | null = null;
  private lastHapticTime: number = 0;
  private isHapticSupported: boolean;

  // 动画
  private animFrameId: number | null = null;
  private lastRenderTime: number = 0;
  private currentRotateDeg: number = 0;
  private targetRotateDeg: number = 0;

  // 回调
  private onClose: (() => void) | null = null;
  private onArrived: (() => void) | null = null;

  // 位置监听器引用（用于取消订阅）
  private locationListener: ((data: LocationData) => void) | null = null;
  private orientationListener: ((data: OrientationData) => void) | null = null;

  constructor(target: NavigationTarget, config?: Partial<NavigationConfig>) {
    this.target = target;
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.lifecycleScope = RuntimeLifecycle.createScope('PointDetailedNavigation');
    this.isHapticSupported = typeof navigator !== 'undefined' && 'vibrate' in navigator;
  }

  /** 启动导航 */
  public async start(): Promise<void> {
    if (this.state !== 'idle') {
      Logger.warn('PointDetailedNavigation', '导航已在运行中');
      return;
    }

    this.setState('acquiring_signal');
    this.createOverlay();
    this.bindEvents();
    this.startRenderLoop();
    await this.activateSensors();
  }

  /** 停止导航并清理资源 */
  public stop(): void {
    this.setState('idle');
    this.deactivateSensors();
    this.stopRenderLoop();
    this.stopHaptic();
    this.removeOverlay();
    this.lifecycleScope.cleanup();
    this.currentLocation = null;
    this.currentHeading = null;
    this.targetBearing = null;
    this.currentDistance = null;
    Logger.info('PointDetailedNavigation', '导航已停止，资源已释放');
  }

  /** 设置关闭回调 */
  public setOnClose(callback: (() => void) | null): void {
    this.onClose = callback;
  }

  /** 设置到达回调 */
  public setOnArrived(callback: (() => void) | null): void {
    this.onArrived = callback;
  }

  /** 获取当前导航状态 */
  public getState(): NavigationState {
    return this.state;
  }

  /** 获取目标点 */
  public getTarget(): NavigationTarget {
    return this.target;
  }

  // ==================== 传感器激活 ====================

  private async activateSensors(): Promise<void> {
    // 订阅位置更新
    this.locationListener = (data: LocationData) => {
      this.handleLocationUpdate(data);
    };
    locationService.addLocationListener(this.locationListener);

    // 激活罗盘
    const status = sensorManager.getStatus();
    if (status.orientationAvailable) {
      this.orientationListener = (data: OrientationData) => {
        this.currentHeading = data.absolute; // 0-360度
      };
      const started = await sensorManager.startOrientation(this.orientationListener);
      if (!started) {
        this.hasCompass = false;
        Logger.warn('PointDetailedNavigation', '罗盘启动失败，降级为无罗盘模式');
      }
    } else {
      this.hasCompass = false;
      Logger.warn('PointDetailedNavigation', '设备不支持电子罗盘，降级为无罗盘模式');
    }
  }

  private deactivateSensors(): void {
    if (this.locationListener) {
      locationService.removeLocationListener(this.locationListener);
      this.locationListener = null;
    }
    // 只有我们启动的罗盘才关闭
    if (this.hasCompass) {
      sensorManager.stopOrientation();
      this.orientationListener = null;
    }
  }

  private handleLocationUpdate(data: LocationData): void {
    this.currentLocation = data;

    // 检查GPS精度
    if (data.accuracy > this.config.accuracyWarningM) {
      if (this.state !== 'signal_lost') {
        this.setState('signal_lost');
      }
      this.updateAccuracyBadge(data.accuracy);
      return;
    }

    // 恢复导航状态
    if (this.state === 'signal_lost' || this.state === 'acquiring_signal') {
      this.setState('navigating');
    }

    this.currentDistance = locationService.calculateDistance(data, this.target);
    this.targetBearing = locationService.calculateBearing(data, this.target);

    // 检查到达
    if (this.currentDistance <= this.config.arrivalDistanceM && this.state !== 'arrived') {
      this.setState('arrived');
      if (this.onArrived) {
        this.onArrived();
      }
    } else if (this.currentDistance > this.config.arrivalDistanceM && this.state === 'arrived') {
      this.setState('navigating');
    }

    // 更新触觉反馈
    this.updateHaptic();
  }

  // ==================== 渲染循环 ====================

  private startRenderLoop(): void {
    const render = (timestamp: number) => {
      this.render(timestamp);
      this.animFrameId = requestAnimationFrame(render);
    };
    this.animFrameId = requestAnimationFrame(render);
  }

  private stopRenderLoop(): void {
    if (this.animFrameId !== null) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
  }

  private render(timestamp: number): void {
    if (!this.overlayEl || !this.arrowEl) return;

    const delta = timestamp - this.lastRenderTime;
    this.lastRenderTime = timestamp;

    // 计算目标旋转角度
    if (this.hasCompass && this.currentHeading !== null && this.targetBearing !== null) {
      // 相对角度 = 目标方位角 - 设备朝向角
      // 设备"指向"的方向是currentHeading，目标在targetBearing方向
      // 箭头需要旋转的角度 = targetBearing - currentHeading
      let rawAngle = this.targetBearing - this.currentHeading;
      // 标准化到 [-180, 180] 便于判断旋转方向
      if (rawAngle > 180) rawAngle -= 360;
      if (rawAngle < -180) rawAngle += 360;
      this.targetRotateDeg = rawAngle;
    }

    // 平滑插值 (lerp) 实现60fps平滑旋转
    const lerpFactor = 0.12;
    let deltaAngle = this.targetRotateDeg - this.currentRotateDeg;
    // 处理跨越 360° 边界的情况
    if (deltaAngle > 180) deltaAngle -= 360;
    if (deltaAngle < -180) deltaAngle += 360;
    this.currentRotateDeg += deltaAngle * lerpFactor;
    // 保持角度在 [-180, 180]
    if (this.currentRotateDeg > 180) this.currentRotateDeg -= 360;
    if (this.currentRotateDeg < -180) this.currentRotateDeg += 360;

    // 应用CSS变换 - 旋转在外层rotator上
    if (this.arrowRotatorEl) {
      this.arrowRotatorEl.style.transform = `rotate(${this.currentRotateDeg}deg)`;
    }

    // 更新距离显示
    if (this.distanceEl && this.currentDistance !== null) {
      const distText = this.formatDistance(this.currentDistance);
      this.distanceEl.textContent = distText;
    }

    // 更新颜色和脉冲动画
    this.updateVisualFeedback();

    // 更新精度徽章
    if (this.currentLocation) {
      this.updateAccuracyBadge(this.currentLocation.accuracy);
    }
  }

  // ==================== 视觉反馈 ====================

  private updateVisualFeedback(): void {
    if (!this.arrowEl || !this.arrowInnerEl || !this.overlayEl) return;

    const level = this.getFeedbackLevel();
    const config = FEEDBACK_COLORS.find(c => c.level === level)!;

    // 通过CSS变量控制颜色，SVG使用currentColor继承
    this.arrowEl.style.color = config.color;

    // 到达状态切换SVG
    const svgEl = this.arrowEl.querySelector('svg');
    if (svgEl) {
      if (level === 'arrived') {
        if (!this.arrowEl.classList.contains('navigation-arrived')) {
          this.arrowEl.classList.add('navigation-arrived');
          svgEl.innerHTML = ARRIVED_SVG;
        }
      } else {
        if (this.arrowEl.classList.contains('navigation-arrived')) {
          this.arrowEl.classList.remove('navigation-arrived');
          svgEl.innerHTML = ARROW_SVG;
        }
      }
    }

    // 脉冲动画在内层元素上，不干扰外层的旋转transform
    if (this.currentDistance !== null && level !== 'arrived' && level !== 'no_signal') {
      const pulseIntensity = Math.max(0, 1 - this.currentDistance / this.config.farDistanceM);
      const scale = 1 + pulseIntensity * 0.08;
      this.arrowInnerEl.style.setProperty('--pulse-scale', scale.toString());
      this.arrowInnerEl.classList.add('navigation-pulse');
      // 脉冲速度随距离变化
      const animDuration = Math.max(0.6, 2.0 - pulseIntensity * 1.4);
      this.arrowInnerEl.style.setProperty('--pulse-duration', `${animDuration}s`);
    } else {
      this.arrowInnerEl.classList.remove('navigation-pulse');
    }

    // 更新状态标签
    if (this.statusEl) {
      this.statusEl.textContent = config.label;
      this.statusEl.style.color = config.color;
    }

    // 更新覆盖层颜色指示
    this.overlayEl.style.setProperty('--nav-current-color', config.color);
  }

  private getFeedbackLevel(): NavigationFeedbackLevel {
    if (this.state === 'signal_lost' || this.state === 'acquiring_signal') {
      return 'no_signal';
    }
    if (this.state === 'arrived') {
      return 'arrived';
    }
    if (this.currentDistance === null) {
      return 'no_signal';
    }
    if (this.currentDistance <= this.config.arrivalDistanceM) {
      return 'arrived';
    }
    if (this.currentDistance <= this.config.nearDistanceM) {
      return 'near';
    }
    if (this.currentDistance <= this.config.farDistanceM) {
      return 'guiding';
    }
    return 'far';
  }

  // ==================== 触觉反馈 ====================

  private updateHaptic(): void {
    if (!this.isHapticSupported || this.currentDistance === null) return;

    const { hapticConfig } = this.config;
    let intervalMs: number;
    let durationMs: number;

    if (this.currentDistance <= this.config.nearDistanceM) {
      intervalMs = hapticConfig.nearIntervalMs;
      durationMs = hapticConfig.nearDurationMs;
    } else if (this.currentDistance <= this.config.farDistanceM) {
      intervalMs = hapticConfig.guidingIntervalMs;
      durationMs = hapticConfig.guidingDurationMs;
    } else {
      intervalMs = hapticConfig.farIntervalMs;
      durationMs = hapticConfig.farDurationMs;
    }

    const now = Date.now();
    if (now - this.lastHapticTime >= intervalMs) {
      this.lastHapticTime = now;
      this.triggerHaptic(durationMs);
    }
  }

  private triggerHaptic(durationMs: number): void {
    try {
      navigator.vibrate(durationMs);
    } catch {
      // 忽略振动错误
    }
  }

  private startHaptic(): void {
    // 触觉反馈由 updateHaptic 在位置更新时驱动
  }

  private stopHaptic(): void {
    this.lastHapticTime = 0;
    if (this.hapticTimer !== null) {
      clearInterval(this.hapticTimer);
      this.hapticTimer = null;
    }
  }

  // ==================== Overlay 创建 ====================

  private createOverlay(): void {
    // 移除已存在的导航覆盖层
    const existing = document.querySelector('.point-navigation-overlay');
    if (existing) {
      existing.remove();
    }

    this.overlayEl = document.createElement('div');
    this.overlayEl.className = 'point-navigation-overlay';
    this.overlayEl.setAttribute('role', 'dialog');
    this.overlayEl.setAttribute('aria-label', '精准导航');

    this.overlayEl.innerHTML = `
      <div class="navigation-container">
        <!-- 顶部信息栏 -->
        <div class="navigation-header">
          <div class="navigation-target-label">${this.escapeHtml(this.target.label || '目标点')}</div>
          <div class="navigation-accuracy-badge" style="display:none;">
            <span class="accuracy-icon">📡</span>
            <span class="accuracy-text">--</span>
          </div>
        </div>

        <!-- 无罗盘提示 -->
        <div class="navigation-no-compass-hint" style="display:none;">
          <span>🧭</span>
          <span>设备不支持电子罗盘，请使用地图模式</span>
        </div>

        <!-- 等待信号提示 -->
        <div class="navigation-signal-warning" style="display:none;">
          <span>📡</span>
          <span>等待GPS信号增强...</span>
        </div>

        <!-- 中心箭头区域：外层处理旋转，内层处理脉冲 -->
        <div class="navigation-arrow-rotator">
          <div class="navigation-arrow-inner">
            <div class="navigation-arrow">
              ${ARROW_SVG}
            </div>
          </div>
        </div>

        <!-- 底部信息区 -->
        <div class="navigation-footer">
          <div class="navigation-distance">--</div>
          <div class="navigation-status">准备中</div>
        </div>
      </div>

      <!-- 关闭按钮 -->
      <button class="navigation-close-btn" aria-label="退出导航">
        <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    `;

    document.body.appendChild(this.overlayEl);

    // 缓存DOM引用
    this.arrowRotatorEl = this.overlayEl.querySelector('.navigation-arrow-rotator');
    this.arrowInnerEl = this.overlayEl.querySelector('.navigation-arrow-inner');
    this.arrowEl = this.overlayEl.querySelector('.navigation-arrow');
    this.distanceEl = this.overlayEl.querySelector('.navigation-distance');
    this.statusEl = this.overlayEl.querySelector('.navigation-status');
    this.infoEl = this.overlayEl.querySelector('.navigation-target-label');
    this.closeBtnEl = this.overlayEl.querySelector('.navigation-close-btn');
    this.accuracyBadgeEl = this.overlayEl.querySelector('.navigation-accuracy-badge');
  }

  private removeOverlay(): void {
    if (this.overlayEl) {
      this.overlayEl.remove();
      this.overlayEl = null;
      this.arrowRotatorEl = null;
      this.arrowInnerEl = null;
      this.arrowEl = null;
      this.distanceEl = null;
      this.statusEl = null;
      this.infoEl = null;
      this.closeBtnEl = null;
      this.accuracyBadgeEl = null;
    }
  }

  // ==================== 事件绑定 ====================

  private bindEvents(): void {
    if (this.closeBtnEl) {
      this.lifecycleScope.addEventListener(this.closeBtnEl, 'click', () => {
        this.stop();
        if (this.onClose) {
          this.onClose();
        }
      });
    }

    // 键盘ESC退出
    this.lifecycleScope.addEventListener(document, 'keydown', (e: Event) => {
      if ((e as KeyboardEvent).key === 'Escape') {
        this.stop();
        if (this.onClose) {
          this.onClose();
        }
      }
    });
  }

  // ==================== UI更新 ====================

  private setState(newState: NavigationState): void {
    const prevState = this.state;
    this.state = newState;
    Logger.debug('PointDetailedNavigation', `状态变更: ${prevState} -> ${newState}`);

    // 更新信号警告显示
    const signalWarning = this.overlayEl?.querySelector('.navigation-signal-warning') as HTMLElement;
    const noCompassHint = this.overlayEl?.querySelector('.navigation-no-compass-hint') as HTMLElement;

    if (signalWarning) {
      signalWarning.style.display = (newState === 'signal_lost' || newState === 'acquiring_signal') ? 'flex' : 'none';
    }
    if (noCompassHint) {
      noCompassHint.style.display = (!this.hasCompass) ? 'flex' : 'none';
    }
  }

  private updateAccuracyBadge(accuracy: number): void {
    if (!this.accuracyBadgeEl) return;

    const accuracyText = this.accuracyBadgeEl.querySelector('.accuracy-text');
    if (!accuracyText) return;

    this.accuracyBadgeEl.style.display = 'flex';
    accuracyText.textContent = `±${accuracy.toFixed(1)}m`;

    if (accuracy > this.config.accuracyWarningM) {
      this.accuracyBadgeEl.classList.add('accuracy-poor');
    } else {
      this.accuracyBadgeEl.classList.remove('accuracy-poor');
    }
  }

  // ==================== 工具函数 ====================

  private formatDistance(meters: number): string {
    if (meters >= 1000) {
      return `${(meters / 1000).toFixed(1)} km`;
    }
    if (meters >= 1) {
      return `${meters.toFixed(0)} m`;
    }
    return '已到达';
  }

  private escapeHtml(text: string): string {
    const el = document.createElement('span');
    el.textContent = text;
    return el.innerHTML;
  }
}
