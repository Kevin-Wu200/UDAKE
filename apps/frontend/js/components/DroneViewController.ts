/**
 * 无人机视角主控制器 (DroneViewController.ts)
 *
 * 统一管理无人机视角的核心逻辑:
 * - 相机状态管理 (位置、朝向、俯仰、缩放)
 * - 自动盘旋算法 (固定圆心、半径及俯仰角的平滑动画循环)
 * - 桌面端手动操控 (WASD + 鼠标)
 * - 移动端手动操控 (双虚拟摇杆 + 屏幕滑动)
 * - 设备自适应切换
 * - 置信度锁定/解锁逻辑
 * - CameraState 变化通知 (供 SceneRenderer.setCamera 使用)
 *
 * 约束:
 * - 无人机视角下不进行惯性模拟
 * - Canvas 模式下仅限在 3D 点云场景中飞行
 */

import { DroneHUDOverlay, type HUDData } from './DroneHUDOverlay.js';
import { DroneViewSwitch, type FlightMode } from './DroneViewSwitch.js';
import { Joystick, type JoystickState } from './Joystick.js';
import { detectDevice, type DeviceInfo, onDeviceChange } from '../utils/DeviceDetector.js';
import type { ViewSnapshot } from '../../types/visualization';

// ========== 类型定义 ==========

/** 无人机相机状态 */
export interface DroneCameraState {
    /** 相机位置(经度) */
    centerLon: number;
    /** 相机位置(纬度) */
    centerLat: number;
    /** 相机高度(米) */
    altitude: number;
    /** 朝向角(度, 0=北, 正=顺时针) */
    heading: number;
    /** 俯仰角(度, 0=水平, 90=垂直向下) */
    tilt: number;
    /** 缩放级别 */
    zoom: number;
}

/** 自动盘旋参数 */
export interface OrbitParams {
    /** 盘旋圆心经度 */
    centerLon: number;
    /** 盘旋圆心纬度 */
    centerLat: number;
    /** 盘旋半径(米) */
    radius: number;
    /** 俯仰角(度) */
    pitchAngle: number;
    /** 盘旋速度(度/秒) */
    speed?: number;
}

/** 控制器配置 */
export interface DroneViewControllerConfig {
    /** HUD 挂载容器 */
    hudContainer: HTMLElement;
    /** 开关面板挂载容器 */
    switchContainer: HTMLElement;
    /** 摇杆挂载容器(移动端) */
    joystickContainer?: HTMLElement;
    /** 置信度解锁阈值, 默认 0.85 */
    confidenceThreshold?: number;
    /** 初始相机状态 */
    initialCamera?: Partial<DroneCameraState>;
    /** 初始盘旋参数 */
    initialOrbit?: Partial<OrbitParams>;
    /** 相机状态变化回调 (同步到 SceneRenderer) */
    onCameraChange?: (state: DroneCameraState) => void;
    /** 置信度获取函数 */
    getConfidence?: () => number;
}

// ========== 主控制器 ==========

export class DroneViewController {
    private config: Required<DroneViewControllerConfig>;
    private hud: DroneHUDOverlay;
    private switchPanel: DroneViewSwitch;
    private deviceInfo: DeviceInfo;

    // 相机状态
    private camera: DroneCameraState;
    private orbit: OrbitParams;
    private flightMode: FlightMode = 'auto';
    private enabled: boolean = false;

    // 自动盘旋
    private orbitAngle: number = 0; // 当前角度(弧度)
    private orbitAnimFrame: number | null = null;
    private lastOrbitTime: number = 0;

    // 移动端摇杆
    private leftJoystick: Joystick | null = null;
    private rightJoystick: Joystick | null = null;
    private leftJoystickState: JoystickState = { x: 0, y: 0, active: false, pointerId: null };
    private rightJoystickState: JoystickState = { x: 0, y: 0, active: false, pointerId: null };
    private manualAnimFrame: number | null = null;

    // 桌面端键鼠
    private keysDown: Set<string> = new Set();
    private mouseDown: boolean = false;
    private lastMousePos: { x: number; y: number } = { x: 0, y: 0 };
    private boundKeyDown: (e: KeyboardEvent) => void;
    private boundKeyUp: (e: KeyboardEvent) => void;
    private boundMouseDown: (e: MouseEvent) => void;
    private boundMouseUp: (e: MouseEvent) => void;
    private boundMouseMove: (e: MouseEvent) => void;
    private boundWheel: (e: WheelEvent) => void;
    private boundTouchStart: (e: TouchEvent) => void;
    private boundTouchMove: (e: TouchEvent) => void;

    // 屏幕滑动(移动端旋转/俯仰)
    private swipeTouchId: number | null = null;
    private lastSwipePos: { x: number; y: number } = { x: 0, y: 0 };

    private removeOrientationListener: (() => void) | null = null;

    constructor(config: DroneViewControllerConfig) {
        this.config = {
            confidenceThreshold: 0.85,
            initialCamera: {},
            initialOrbit: {},
            getConfidence: () => 0,
            onCameraChange: () => {},
            ...config,
            // 以下必须提供
            hudContainer: config.hudContainer,
            switchContainer: config.switchContainer,
            joystickContainer: config.joystickContainer || config.hudContainer,
        };

        this.deviceInfo = detectDevice();

        // 初始化相机状态
        this.camera = {
            centerLon: this.config.initialCamera.centerLon ?? 116.39,
            centerLat: this.config.initialCamera.centerLat ?? 39.90,
            altitude: this.config.initialCamera.altitude ?? 1000,
            heading: this.config.initialCamera.heading ?? 0,
            tilt: this.config.initialCamera.tilt ?? 45,
            zoom: this.config.initialCamera.zoom ?? 10,
        };

        // 初始化盘旋参数
        this.orbit = {
            centerLon: this.config.initialOrbit.centerLon ?? this.camera.centerLon,
            centerLat: this.config.initialOrbit.centerLat ?? this.camera.centerLat,
            radius: this.config.initialOrbit.radius ?? 500,
            pitchAngle: this.config.initialOrbit.pitchAngle ?? 45,
            speed: this.config.initialOrbit.speed ?? 20,
        };

        // 创建子组件
        this.hud = new DroneHUDOverlay({
            container: this.config.hudContainer,
            confidenceThreshold: this.config.confidenceThreshold,
        });
        this.hud.setVisible(false);

        this.switchPanel = new DroneViewSwitch({
            container: this.config.switchContainer,
            confidenceThreshold: this.config.confidenceThreshold,
            confidence: this.getCurrentConfidence(),
            enabled: false,
            flightMode: this.flightMode,
            onToggle: (enabled) => this.onToggle(enabled),
            onFlightModeChange: (mode) => this.onFlightModeChange(mode),
            onOrbitParamsChange: (params) => this.onOrbitParamsChange(params),
        });

        // 绑定控件事件
        this.boundKeyDown = this.onKeyDown.bind(this);
        this.boundKeyUp = this.onKeyUp.bind(this);
        this.boundMouseDown = this.onMouseDown.bind(this);
        this.boundMouseUp = this.onMouseUp.bind(this);
        this.boundMouseMove = this.onMouseMove.bind(this);
        this.boundWheel = this.onWheel.bind(this);
        this.boundTouchStart = this.onTouchStart.bind(this);
        this.boundTouchMove = this.onTouchMove.bind(this);

        // 设备变化监听
        this.removeOrientationListener = onDeviceChange((info) => {
            const wasMobile = this.deviceInfo.type === 'mobile';
            this.deviceInfo = info;
            if (wasMobile !== (info.type === 'mobile') && this.enabled) {
                this.rebindControls();
            }
        });
    }

    // ========== 公共方法 ==========

    /** 获取当前 ViewSnapshot (供 SceneRenderer 使用) */
    public getViewSnapshot(): ViewSnapshot {
        return {
            heading: this.camera.heading,
            tilt: this.camera.tilt,
            zoom: this.camera.zoom,
            center: { x: this.camera.centerLon, y: this.camera.centerLat },
        };
    }

    /** 获取当前相机状态 */
    public getCameraState(): Readonly<DroneCameraState> {
        return this.camera;
    }

    /** 更新置信度值(外部调用) */
    public updateConfidence(confidence: number): void {
        this.switchPanel.updateConfidence(confidence);
        if (this.enabled) {
            const unlocked = confidence >= this.config.confidenceThreshold;
            const hudData = this.buildHUDData();
            hudData.confidence = confidence;
            hudData.confidenceUnlocked = unlocked;
            this.hud.update(hudData);
        }
    }

    /** 设置相机位置(外部跳转) */
    public setCameraPosition(lon: number, lat: number, altitude?: number): void {
        this.camera.centerLon = lon;
        this.camera.centerLat = lat;
        if (altitude != null) this.camera.altitude = altitude;
        this.notifyCameraChange();
    }

    /** 销毁控制器 */
    public destroy(): void {
        this.stopAutoOrbit();
        this.stopManualLoop();
        this.removeDesktopListeners();
        this.removeMobileJoysticks();
        this.removeOrientationListener?.();
        this.hud.destroy();
        this.switchPanel.destroy();
    }

    // ========== 开关/模式切换 ==========

    private onToggle(enabled: boolean): void {
        const confidence = this.getCurrentConfidence();
        if (enabled && confidence < this.config.confidenceThreshold) {
            console.warn(
                `⚠️ 置信度(${(confidence * 100).toFixed(0)}%)未达解锁阈值` +
                `(${(this.config.confidenceThreshold * 100).toFixed(0)}%)，无法启用无人机视角`
            );
            // 视觉反馈后自动关闭
            setTimeout(() => this.switchPanel.setEnabled(false), 300);
            return;
        }

        this.enabled = enabled;
        if (enabled) {
            this.onEnable();
        } else {
            this.onDisable();
        }
    }

    private onEnable(): void {
        console.log('🛩️ 无人机视角已启用');
        this.hud.setVisible(true);
        this.rebindControls();

        if (this.flightMode === 'auto') {
            this.startAutoOrbit();
        } else {
            this.startManualLoop();
        }

        // 初始 HUD 更新
        this.hud.update(this.buildHUDData());
        this.notifyCameraChange();
    }

    private onDisable(): void {
        console.log('🛩️ 无人机视角已关闭');
        this.hud.setVisible(false);
        this.stopAutoOrbit();
        this.stopManualLoop();
        this.removeDesktopListeners();
        this.removeMobileJoysticks();
    }

    private onFlightModeChange(mode: FlightMode): void {
        this.flightMode = mode;

        if (!this.enabled) return;

        // 切换模式时重置控件
        this.stopAutoOrbit();
        this.stopManualLoop();
        this.removeDesktopListeners();
        this.removeMobileJoysticks();

        if (mode === 'auto') {
            this.orbitAngle = 0;
            this.startAutoOrbit();
        } else {
            this.startManualLoop();
            this.rebindControls();
        }

        this.hud.update(this.buildHUDData());
    }

    private onOrbitParamsChange(params: OrbitParams): void {
        this.orbit = { ...params };
        this.orbitAngle = 0;
        if (this.enabled && this.flightMode === 'auto') {
            this.stopAutoOrbit();
            this.startAutoOrbit();
        }
        console.log('🔄 盘旋参数更新:', this.orbit);
    }

    // ========== 自动盘旋算法 ==========

    private startAutoOrbit(): void {
        this.lastOrbitTime = performance.now();
        this.orbitLoop();
    }

    private stopAutoOrbit(): void {
        if (this.orbitAnimFrame != null) {
            cancelAnimationFrame(this.orbitAnimFrame);
            this.orbitAnimFrame = null;
        }
    }

    /**
     * 自动盘旋循环: 固定圆心、半径及俯仰角的平滑动画
     * 使用 requestAnimationFrame 保证 60fps 平滑度
     */
    private orbitLoop = (): void => {
        if (!this.enabled || this.flightMode !== 'auto') return;

        const now = performance.now();
        const dt = Math.min((now - this.lastOrbitTime) / 1000, 0.1); // 秒, 上限 100ms
        this.lastOrbitTime = now;

        // 角速度 (度/秒 → 弧度/秒)
        const angularSpeed = (this.orbit.speed! * Math.PI) / 180;
        this.orbitAngle += angularSpeed * dt;
        if (this.orbitAngle > Math.PI * 2) this.orbitAngle -= Math.PI * 2;

        // 计算当前盘旋位置
        // 简化: 1度经度 ≈ 111320 * cos(lat) 米, 1度纬度 ≈ 111320 米
        const latRad = (this.orbit.centerLat * Math.PI) / 180;
        const metersPerDegLon = 111320 * Math.cos(latRad);
        const metersPerDegLat = 111320;

        const dLon = (this.orbit.radius * Math.cos(this.orbitAngle)) / metersPerDegLon;
        const dLat = (this.orbit.radius * Math.sin(this.orbitAngle)) / metersPerDegLat;

        this.camera.centerLon = this.orbit.centerLon + dLon;
        this.camera.centerLat = this.orbit.centerLat + dLat;
        this.camera.heading = (this.orbitAngle * 180) / Math.PI + 90; // 朝向始终面向圆心切线方向
        this.camera.tilt = this.orbit.pitchAngle;

        this.hud.update(this.buildHUDData());
        this.notifyCameraChange();

        this.orbitAnimFrame = requestAnimationFrame(this.orbitLoop);
    };

    // ========== 桌面端手动操控 ==========

    private bindDesktopControls(): void {
        const mapContainer = this.config.hudContainer.parentElement || document.body;
        mapContainer.addEventListener('keydown', this.boundKeyDown);
        mapContainer.addEventListener('keyup', this.boundKeyUp);
        mapContainer.addEventListener('mousedown', this.boundMouseDown);
        window.addEventListener('mouseup', this.boundMouseUp);
        window.addEventListener('mousemove', this.boundMouseMove);
        mapContainer.addEventListener('wheel', this.boundWheel, { passive: false });

        // 设置 tabIndex 以便接收键盘事件
        mapContainer.setAttribute('tabindex', '0');
        mapContainer.focus();
    }

    private removeDesktopListeners(): void {
        const mapContainer = this.config.hudContainer.parentElement || document.body;
        mapContainer.removeEventListener('keydown', this.boundKeyDown);
        mapContainer.removeEventListener('keyup', this.boundKeyUp);
        mapContainer.removeEventListener('mousedown', this.boundMouseDown);
        window.removeEventListener('mouseup', this.boundMouseUp);
        window.removeEventListener('mousemove', this.boundMouseMove);
        mapContainer.removeEventListener('wheel', this.boundWheel);
    }

    private onKeyDown(e: KeyboardEvent): void {
        if (!this.enabled || this.flightMode !== 'manual') return;
        // WASD 控制水平位移
        const key = e.key.toLowerCase();
        if (['w', 'a', 's', 'd', 'q', 'e', 'r', 'f'].includes(key)) {
            e.preventDefault();
            this.keysDown.add(key);
        }
    }

    private onKeyUp(e: KeyboardEvent): void {
        this.keysDown.delete(e.key.toLowerCase());
    }

    private onMouseDown(e: MouseEvent): void {
        if (!this.enabled || this.flightMode !== 'manual') return;
        this.mouseDown = true;
        this.lastMousePos = { x: e.clientX, y: e.clientY };
    }

    private onMouseUp(_e: MouseEvent): void {
        this.mouseDown = false;
    }

    private onMouseMove(e: MouseEvent): void {
        if (!this.enabled || this.flightMode !== 'manual' || !this.mouseDown) return;

        const dx = e.clientX - this.lastMousePos.x;
        const dy = e.clientY - this.lastMousePos.y;
        this.lastMousePos = { x: e.clientX, y: e.clientY };

        // 鼠标控制旋转(Heading)与俯仰(Tilt)
        this.camera.heading += dx * 0.3;
        this.camera.tilt = Math.max(5, Math.min(85, this.camera.tilt - dy * 0.2));

        // 保持 heading 在 [0, 360)
        while (this.camera.heading < 0) this.camera.heading += 360;
        this.camera.heading %= 360;
    }

    private onWheel(e: WheelEvent): void {
        if (!this.enabled || this.flightMode !== 'manual') return;
        e.preventDefault();
        // 滚轮控制高度变化
        this.camera.altitude = Math.max(10, this.camera.altitude + e.deltaY * 5);
    }

    /**
     * 桌面端手动操控循环
     * WASD: 水平位移 (无惯性)
     * Q/E: 上下移动
     * R/F: 缩放
     */
    private manualLoop = (): void => {
        if (!this.enabled || this.flightMode !== 'manual') return;

        const moveSpeed = 50; // 米/秒 (基于 50fps 约 1米/帧)
        const altSpeed = 20;
        const zoomSpeed = 0.5;

        // 计算移动方向 (基于当前朝向)
        const headingRad = (this.camera.heading * Math.PI) / 180;
        const forwardX = Math.sin(headingRad);
        const forwardY = Math.cos(headingRad);
        const rightX = Math.cos(headingRad);
        const rightY = -Math.sin(headingRad);

        let dLon = 0;
        let dLat = 0;

        if (this.keysDown.has('w')) { dLon += forwardX * moveSpeed; dLat += forwardY * moveSpeed; }
        if (this.keysDown.has('s')) { dLon -= forwardX * moveSpeed; dLat -= forwardY * moveSpeed; }
        if (this.keysDown.has('d')) { dLon += rightX * moveSpeed; dLat += rightY * moveSpeed; }
        if (this.keysDown.has('a')) { dLon -= rightX * moveSpeed; dLat -= rightY * moveSpeed; }

        if (this.keysDown.has('e')) this.camera.altitude -= altSpeed;
        if (this.keysDown.has('q')) this.camera.altitude = Math.max(10, this.camera.altitude + altSpeed);
        if (this.keysDown.has('r')) this.camera.zoom = Math.min(20, this.camera.zoom + zoomSpeed);
        if (this.keysDown.has('f')) this.camera.zoom = Math.max(1, this.camera.zoom - zoomSpeed);

        // 应用水平位移 (米 → 度)
        if (dLon !== 0 || dLat !== 0) {
            const latRad = (this.camera.centerLat * Math.PI) / 180;
            const metersPerDegLon = 111320 * Math.cos(latRad);
            const metersPerDegLat = 111320;
            this.camera.centerLon += dLon / metersPerDegLon;
            this.camera.centerLat += dLat / metersPerDegLat;
        }

        this.hud.update(this.buildHUDData());
        this.notifyCameraChange();

        this.manualAnimFrame = requestAnimationFrame(this.manualLoop);
    };

    private startManualLoop(): void {
        this.lastOrbitTime = performance.now();
        this.manualAnimFrame = requestAnimationFrame(this.manualLoop);
    }

    private stopManualLoop(): void {
        if (this.manualAnimFrame != null) {
            cancelAnimationFrame(this.manualAnimFrame);
            this.manualAnimFrame = null;
        }
        this.keysDown.clear();
        this.mouseDown = false;
    }

    // ========== 移动端手动操控 ==========

    private bindMobileControls(): void {
        const joystickContainer = this.config.joystickContainer || this.config.hudContainer;

        // 左摇杆: 水平面移动(前后左右)
        this.leftJoystick = new Joystick({
            container: joystickContainer,
            id: 'drone-left',
            position: 'left',
            baseRadius: 55,
            knobRadius: 22,
            deadZone: 0.08,
            onChange: (state) => { this.leftJoystickState = state; },
        });

        // 右摇杆: 垂直高度变化(升降)
        this.rightJoystick = new Joystick({
            container: joystickContainer,
            id: 'drone-right',
            position: 'right',
            baseRadius: 55,
            knobRadius: 22,
            deadZone: 0.08,
            onChange: (state) => { this.rightJoystickState = state; },
        });

        // 屏幕滑动: 控制相机旋转(Heading)与俯仰角(Tilt)
        const mapContainer = this.config.hudContainer.parentElement || document.body;
        mapContainer.addEventListener('touchstart', this.boundTouchStart, { passive: false });
        mapContainer.addEventListener('touchmove', this.boundTouchMove, { passive: false });
    }

    private removeMobileJoysticks(): void {
        this.leftJoystick?.destroy();
        this.leftJoystick = null;
        this.rightJoystick?.destroy();
        this.rightJoystick = null;

        const mapContainer = this.config.hudContainer.parentElement || document.body;
        mapContainer.removeEventListener('touchstart', this.boundTouchStart);
        mapContainer.removeEventListener('touchmove', this.boundTouchMove);
    }

    private onTouchStart(e: TouchEvent): void {
        if (!this.enabled || this.flightMode !== 'manual') return;

        // 忽略摇杆区域的触摸(由 Joystick 自己处理)
        for (let i = 0; i < e.touches.length; i++) {
            const touch = e.touches[i];
            const target = touch.target as HTMLElement;
            if (target?.closest('[data-joystick-id]')) continue;

            // 找到不在摇杆上的触摸作为滑动
            if (this.swipeTouchId == null) {
                this.swipeTouchId = touch.identifier;
                this.lastSwipePos = { x: touch.clientX, y: touch.clientY };
                break;
            }
        }
    }

    private onTouchMove(e: TouchEvent): void {
        if (this.swipeTouchId == null) return;
        e.preventDefault();

        for (let i = 0; i < e.touches.length; i++) {
            const touch = e.touches[i];
            if (touch.identifier === this.swipeTouchId) {
                const dx = touch.clientX - this.lastSwipePos.x;
                const dy = touch.clientY - this.lastSwipePos.y;
                this.lastSwipePos = { x: touch.clientX, y: touch.clientY };

                this.camera.heading += dx * 0.3;
                this.camera.tilt = Math.max(5, Math.min(85, this.camera.tilt - dy * 0.2));
                while (this.camera.heading < 0) this.camera.heading += 360;
                this.camera.heading %= 360;
                break;
            }
        }
    }

    /**
     * 移动端手动操控循环(处理摇杆输入)
     */
    private mobileManualLoop = (): void => {
        if (!this.enabled || this.flightMode !== 'manual') return;

        const moveSpeed = 30; // 米/秒
        const altSpeed = 15;

        // 左摇杆: 水平面移动
        const lx = this.leftJoystickState.x;
        const ly = this.leftJoystickState.y;

        if (lx !== 0 || ly !== 0) {
            const headingRad = (this.camera.heading * Math.PI) / 180;

            // Y轴向上 = forward(前), Y轴向下 = backward(后)
            // X轴向右 = right, X轴向左 = left
            const forwardSpeed = -ly * moveSpeed; // 反转Y轴
            const strafeSpeed = lx * moveSpeed;

            const latRad = (this.camera.centerLat * Math.PI) / 180;
            const metersPerDegLon = 111320 * Math.cos(latRad);
            const metersPerDegLat = 111320;

            this.camera.centerLon += (Math.sin(headingRad) * forwardSpeed + Math.cos(headingRad) * strafeSpeed) / metersPerDegLon;
            this.camera.centerLat += (Math.cos(headingRad) * forwardSpeed - Math.sin(headingRad) * strafeSpeed) / metersPerDegLat;
        }

        // 右摇杆: 垂直升降 (Y轴向上=上升)
        const ry = this.rightJoystickState.y;
        if (ry !== 0) {
            this.camera.altitude = Math.max(10, this.camera.altitude - ry * altSpeed);
        }

        // 右摇杆 X轴: 缩放
        const rx = this.rightJoystickState.x;
        if (rx !== 0) {
            this.camera.zoom = Math.max(1, Math.min(20, this.camera.zoom + rx * 0.3));
        }

        this.hud.update(this.buildHUDData());
        this.notifyCameraChange();

        this.manualAnimFrame = requestAnimationFrame(this.mobileManualLoop);
    };

    // ========== 控件绑定管理 ==========

    private rebindControls(): void {
        this.removeDesktopListeners();
        this.removeMobileJoysticks();

        if (this.flightMode !== 'manual') return;

        if (this.deviceInfo.type === 'desktop') {
            console.log('🖥️ 桌面端模式: 绑定键鼠操控');
            this.bindDesktopControls();
            this.stopManualLoop();
            this.manualAnimFrame = requestAnimationFrame(this.manualLoop);
        } else {
            console.log('📱 移动端模式: 绑定双摇杆操控');
            this.bindMobileControls();
            this.stopManualLoop();
            this.manualAnimFrame = requestAnimationFrame(this.mobileManualLoop);
        }
    }

    // ========== 辅助方法 ==========

    private getCurrentConfidence(): number {
        return this.config.getConfidence();
    }

    private buildHUDData(): HUDData {
        const confidence = this.getCurrentConfidence();
        return {
            longitude: this.camera.centerLon,
            latitude: this.camera.centerLat,
            altitude: this.camera.altitude,
            heading: this.camera.heading,
            tilt: this.camera.tilt,
            zoom: this.camera.zoom,
            confidence,
            confidenceUnlocked: confidence >= this.config.confidenceThreshold,
            flightMode: this.flightMode,
            ...(this.flightMode === 'auto' ? {
                orbitCenterLon: this.orbit.centerLon,
                orbitCenterLat: this.orbit.centerLat,
                orbitRadius: this.orbit.radius,
            } : {}),
        };
    }

    private notifyCameraChange(): void {
        this.config.onCameraChange({ ...this.camera });
    }
}
