/**
 * 虚拟摇杆组件 (Joystick.ts)
 * 支持多指触控与动态反馈，用于移动端无人机操控
 *
 * 特性:
 * - 双摇杆独立区域: 左摇杆(水平移动) + 右摇杆(垂直升降)
 * - 死区设置(可配置)
 * - 动态视觉反馈(按压态、回弹动画)
 * - 多指同时触控支持
 */

export interface JoystickState {
    /** X轴偏移量 [-1, 1], 0=中心 */
    x: number;
    /** Y轴偏移量 [-1, 1], 0=中心 */
    y: number;
    /** 是否正在被触控 */
    active: boolean;
    /** 触控点ID (用于多指追踪) */
    pointerId: number | null;
}

export interface JoystickConfig {
    /** 摇杆容器元素 */
    container: HTMLElement;
    /** 摇杆ID标识 */
    id: string;
    /** 摇杆底色圆半径 (px, 默认 60) */
    baseRadius?: number;
    /** 摇杆把手半径 (px, 默认 25) */
    knobRadius?: number;
    /** 死区比例 [0, 1], 默认 0.1 (10%) */
    deadZone?: number;
    /** 摇杆位置: 'left' | 'right' */
    position: 'left' | 'right';
    /** 透明白色底 */
    baseColor?: string;
    /** 把手颜色 */
    knobColor?: string;
    /** 状态变化回调 */
    onChange?: (state: JoystickState) => void;
}

export class Joystick {
    private config: Required<JoystickConfig>;
    private state: JoystickState = { x: 0, y: 0, active: false, pointerId: null };
    private canvas!: HTMLCanvasElement;
    private ctx!: CanvasRenderingContext2D;
    private centerX: number = 0;
    private centerY: number = 0;
    private animFrame: number | null = null;
    /** 回弹动画: 当前把手偏移 */
    private returnX: number = 0;
    private returnY: number = 0;
    private returnActive: boolean = false;

    private boundPointerDown: (e: PointerEvent) => void;
    private boundPointerMove: (e: PointerEvent) => void;
    private boundPointerUp: (e: PointerEvent) => void;
    private boundPointerCancel: (e: PointerEvent) => void;

    constructor(config: JoystickConfig) {
        this.config = {
            baseRadius: 60,
            knobRadius: 25,
            deadZone: 0.1,
            baseColor: 'rgba(255,255,255,0.15)',
            knobColor: 'rgba(255,255,255,0.6)',
            onChange: () => {},
            ...config,
        };

        this.boundPointerDown = this.onPointerDown.bind(this);
        this.boundPointerMove = this.onPointerMove.bind(this);
        this.boundPointerUp = this.onPointerUp.bind(this);
        this.boundPointerCancel = this.onPointerUp.bind(this);

        this.createCanvas();
        this.bindEvents();
        this.startRenderLoop();
    }

    private createCanvas(): void {
        const { baseRadius } = this.config;
        const size = baseRadius * 2 + 20; // 留边距

        this.canvas = document.createElement('canvas');
        this.canvas.width = size;
        this.canvas.height = size;
        this.canvas.style.cssText = `
            position: absolute;
            bottom: 40px;
            ${this.config.position === 'left' ? 'left: 40px;' : 'right: 40px;'}
            width: ${size}px;
            height: ${size}px;
            touch-action: none;
            z-index: 1000;
            pointer-events: auto;
        `;
        this.canvas.setAttribute('data-joystick-id', this.config.id);

        const ctx = this.canvas.getContext('2d');
        if (!ctx) throw new Error('Canvas 2D context 不可用');
        this.ctx = ctx;

        this.centerX = size / 2;
        this.centerY = size / 2;

        this.config.container.appendChild(this.canvas);
    }

    private bindEvents(): void {
        this.canvas.addEventListener('pointerdown', this.boundPointerDown);
        this.canvas.addEventListener('pointermove', this.boundPointerMove);
        this.canvas.addEventListener('pointerup', this.boundPointerUp);
        this.canvas.addEventListener('pointercancel', this.boundPointerCancel);
        this.canvas.addEventListener('pointerleave', this.boundPointerUp);
    }

    private onPointerDown(e: PointerEvent): void {
        e.preventDefault();
        if (this.state.active) return; // 已被其他手指占用

        this.canvas.setPointerCapture(e.pointerId);
        this.state.pointerId = e.pointerId;
        this.state.active = true;
        this.returnActive = false;
        this.updateKnobPosition(e);
    }

    private onPointerMove(e: PointerEvent): void {
        if (!this.state.active || e.pointerId !== this.state.pointerId) return;
        e.preventDefault();
        this.updateKnobPosition(e);
    }

    private onPointerUp(e: PointerEvent): void {
        if (e.pointerId !== this.state.pointerId) return;
        this.releaseKnob();
    }

    private releaseKnob(): void {
        // 启动回弹动画
        this.returnX = this.state.x;
        this.returnY = this.state.y;
        this.returnActive = true;

        this.state.active = false;
        this.state.pointerId = null;
        this.state.x = 0;
        this.state.y = 0;
        this.config.onChange({ ...this.state });
    }

    private updateKnobPosition(e: PointerEvent): void {
        const rect = this.canvas.getBoundingClientRect();
        const dx = e.clientX - rect.left - this.centerX;
        const dy = e.clientY - rect.top - this.centerY;
        const maxDist = this.config.baseRadius - this.config.knobRadius;

        const dist = Math.hypot(dx, dy);
        const clampedDist = Math.min(dist, maxDist);
        const angle = Math.atan2(dy, dx);

        const rawX = clampedDist * Math.cos(angle) / maxDist;
        const rawY = clampedDist * Math.sin(angle) / maxDist;

        // 死区处理
        const deadZone = this.config.deadZone;
        const mag = Math.hypot(rawX, rawY);
        if (mag < deadZone) {
            this.state.x = 0;
            this.state.y = 0;
        } else {
            // 将死区范围重新映射到 [0, 1]
            const remappedMag = (mag - deadZone) / (1 - deadZone);
            const scale = remappedMag / mag;
            this.state.x = rawX * scale;
            this.state.y = rawY * scale;
        }

        this.config.onChange({ ...this.state });
    }

    private startRenderLoop(): void {
        const render = () => {
            this.draw();
            this.animFrame = requestAnimationFrame(render);
        };
        this.animFrame = requestAnimationFrame(render);
    }

    private draw(): void {
        const { ctx, config, centerX, centerY } = this;
        const { baseRadius, knobRadius, baseColor, knobColor } = config;

        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // 回弹动画
        if (this.returnActive) {
            this.returnX *= 0.85;
            this.returnY *= 0.85;
            if (Math.abs(this.returnX) < 0.005 && Math.abs(this.returnY) < 0.005) {
                this.returnX = 0;
                this.returnY = 0;
                this.returnActive = false;
            }
        }

        // 绘制底色圆
        ctx.beginPath();
        ctx.arc(centerX, centerY, baseRadius, 0, Math.PI * 2);
        ctx.fillStyle = baseColor;
        ctx.fill();

        // 底色圆边框
        ctx.strokeStyle = 'rgba(255,255,255,0.25)';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // 计算把手位置
        const maxOffset = baseRadius - knobRadius;
        const offsetX = this.returnActive
            ? this.returnX * maxOffset
            : this.state.x * maxOffset;
        const offsetY = this.returnActive
            ? this.returnY * maxOffset
            : this.state.y * maxOffset;

        const knobX = centerX + offsetX;
        const knobY = centerY + offsetY;

        // 绘制把手
        ctx.beginPath();
        ctx.arc(knobX, knobY, knobRadius, 0, Math.PI * 2);

        // 活跃态更亮
        const activeAlpha = this.state.active ? 0.85 : 0.6;
        ctx.fillStyle = knobColor.replace(/[\d.]+\)$/, `${activeAlpha})`);
        ctx.fill();

        ctx.strokeStyle = 'rgba(255,255,255,0.5)';
        ctx.lineWidth = 2;
        ctx.stroke();

        // 十字参考线
        ctx.strokeStyle = 'rgba(255,255,255,0.1)';
        ctx.lineWidth = 0.5;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(centerX - baseRadius + 10, centerY);
        ctx.lineTo(centerX + baseRadius - 10, centerY);
        ctx.moveTo(centerX, centerY - baseRadius + 10);
        ctx.lineTo(centerX, centerY + baseRadius - 10);
        ctx.stroke();
        ctx.setLineDash([]);
    }

    /** 获取当前摇杆状态 */
    public getState(): Readonly<JoystickState> {
        return this.state;
    }

    /** 设置死区大小 */
    public setDeadZone(value: number): void {
        this.config.deadZone = Math.max(0, Math.min(0.5, value));
    }

    /** 销毁摇杆 */
    public destroy(): void {
        if (this.animFrame) {
            cancelAnimationFrame(this.animFrame);
            this.animFrame = null;
        }
        this.canvas.removeEventListener('pointerdown', this.boundPointerDown);
        this.canvas.removeEventListener('pointermove', this.boundPointerMove);
        this.canvas.removeEventListener('pointerup', this.boundPointerUp);
        this.canvas.removeEventListener('pointercancel', this.boundPointerCancel);
        this.canvas.removeEventListener('pointerleave', this.boundPointerUp);
        this.canvas.remove();
    }
}
