/**
 * 3D可视化渲染器
 * 基于Canvas的轻量级3D点云和切片渲染
 * 支持旋转、缩放、颜色映射
 */

export interface Render3DOptions {
    width: number;
    height: number;
    backgroundColor: string;
    pointSize: number;
    colorMap: 'rainbow' | 'viridis' | 'hot' | 'cool';
    opacity: number;
}

export interface Point3DData {
    x: number;
    y: number;
    z: number;
    value: number;
}

export class Renderer3D {
    private canvas: HTMLCanvasElement;
    private ctx: CanvasRenderingContext2D;
    private options: Render3DOptions;
    private rotationX: number = -30;
    private rotationZ: number = 45;
    private zoom: number = 1.0;
    private isDragging: boolean = false;
    private lastMouse: { x: number; y: number } = { x: 0, y: 0 };
    private points: Point3DData[] = [];
    private vmin: number = 0;
    private vmax: number = 1;

    constructor(container: HTMLElement, options?: Partial<Render3DOptions>) {
        this.options = {
            width: container.clientWidth || 400,
            height: container.clientHeight || 400,
            backgroundColor: '#1a1a2e',
            pointSize: 3,
            colorMap: 'rainbow',
            opacity: 0.8,
            ...options,
        };

        this.canvas = document.createElement('canvas');
        this.canvas.width = this.options.width;
        this.canvas.height = this.options.height;
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.cursor = 'grab';
        container.innerHTML = '';
        container.appendChild(this.canvas);

        const ctx = this.canvas.getContext('2d');
        if (!ctx) throw new Error('Canvas 2D context 不可用');
        this.ctx = ctx;

        this.bindMouseEvents();
    }

    private bindMouseEvents(): void {
        this.canvas.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.lastMouse = { x: e.clientX, y: e.clientY };
            this.canvas.style.cursor = 'grabbing';
        });
        window.addEventListener('mouseup', () => {
            this.isDragging = false;
            this.canvas.style.cursor = 'grab';
        });
        window.addEventListener('mousemove', (e) => {
            if (!this.isDragging) return;
            const dx = e.clientX - this.lastMouse.x;
            const dy = e.clientY - this.lastMouse.y;
            this.rotationZ += dx * 0.5;
            this.rotationX += dy * 0.5;
            this.rotationX = Math.max(-90, Math.min(90, this.rotationX));
            this.lastMouse = { x: e.clientX, y: e.clientY };
            this.render();
        });
        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            this.zoom *= e.deltaY > 0 ? 0.95 : 1.05;
            this.zoom = Math.max(0.1, Math.min(5, this.zoom));
            this.render();
        });
    }

    public setPoints(points: Point3DData[]): void {
        this.points = points;
        if (points.length > 0) {
            this.vmin = Math.min(...points.map(p => p.value));
            this.vmax = Math.max(...points.map(p => p.value));
        }
        this.render();
    }

    public setColorRange(vmin: number, vmax: number): void {
        this.vmin = vmin;
        this.vmax = vmax;
        this.render();
    }

    private project(x: number, y: number, z: number): { sx: number; sy: number; depth: number } {
        const radZ = (this.rotationZ * Math.PI) / 180;
        const radX = (this.rotationX * Math.PI) / 180;

        // Z轴旋转
        let rx = x * Math.cos(radZ) - y * Math.sin(radZ);
        let ry = x * Math.sin(radZ) + y * Math.cos(radZ);
        let rz = z;

        // X轴旋转
        const ry2 = ry * Math.cos(radX) - rz * Math.sin(radX);
        const rz2 = ry * Math.sin(radX) + rz * Math.cos(radX);

        const scale = this.zoom * Math.min(this.options.width, this.options.height) * 0.35;
        return {
            sx: this.options.width / 2 + rx * scale,
            sy: this.options.height / 2 - rz2 * scale,
            depth: ry2,
        };
    }

    private valueToColor(value: number): string {
        const t = this.vmax > this.vmin ? (value - this.vmin) / (this.vmax - this.vmin) : 0.5;
        const r = Math.round(255 * Math.min(1, 2 * t));
        const g = Math.round(255 * Math.min(1, 2 * (1 - t)));
        const b = Math.round(100 + 155 * (1 - Math.abs(2 * t - 1)));
        return `rgba(${r},${g},${b},${this.options.opacity})`;
    }

    public render(): void {
        const { ctx, options } = this;
        ctx.fillStyle = options.backgroundColor;
        ctx.fillRect(0, 0, options.width, options.height);

        if (this.points.length === 0) {
            ctx.fillStyle = '#666';
            ctx.font = '14px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('暂无3D数据', options.width / 2, options.height / 2);
            return;
        }

        // 归一化坐标到[-1, 1]
        const xs = this.points.map(p => p.x);
        const ys = this.points.map(p => p.y);
        const zs = this.points.map(p => p.z);
        const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
        const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
        const cz = (Math.min(...zs) + Math.max(...zs)) / 2;
        const maxRange = Math.max(
            Math.max(...xs) - Math.min(...xs),
            Math.max(...ys) - Math.min(...ys),
            Math.max(...zs) - Math.min(...zs)
        ) || 1;

        // 投影并按深度排序
        const projected = this.points.map(p => {
            const nx = (p.x - cx) / maxRange;
            const ny = (p.y - cy) / maxRange;
            const nz = (p.z - cz) / maxRange;
            const proj = this.project(nx, ny, nz);
            return { ...proj, value: p.value };
        });
        projected.sort((a, b) => a.depth - b.depth);

        // 绘制点
        for (const p of projected) {
            ctx.fillStyle = this.valueToColor(p.value);
            ctx.beginPath();
            ctx.arc(p.sx, p.sy, options.pointSize, 0, Math.PI * 2);
            ctx.fill();
        }

        // 绘制坐标轴
        this.drawAxes(maxRange);

        // 绘制颜色条
        this.drawColorBar();
    }

    private drawAxes(scale: number): void {
        const { ctx, options } = this;
        const origin = this.project(0, 0, 0);
        const axisLen = 0.3;
        const axes = [
            { end: this.project(axisLen, 0, 0), label: 'X', color: '#ff4444' },
            { end: this.project(0, axisLen, 0), label: 'Y', color: '#44ff44' },
            { end: this.project(0, 0, axisLen), label: 'Z', color: '#4444ff' },
        ];

        for (const axis of axes) {
            ctx.strokeStyle = axis.color;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(origin.sx, origin.sy);
            ctx.lineTo(axis.end.sx, axis.end.sy);
            ctx.stroke();

            ctx.fillStyle = axis.color;
            ctx.font = '12px sans-serif';
            ctx.fillText(axis.label, axis.end.sx + 5, axis.end.sy - 5);
        }
    }

    private drawColorBar(): void {
        const { ctx, options } = this;
        const barX = options.width - 30;
        const barY = 20;
        const barW = 15;
        const barH = options.height - 40;

        for (let i = 0; i < barH; i++) {
            const t = 1 - i / barH;
            const val = this.vmin + t * (this.vmax - this.vmin);
            ctx.fillStyle = this.valueToColor(val);
            ctx.fillRect(barX, barY + i, barW, 1);
        }

        ctx.strokeStyle = '#666';
        ctx.strokeRect(barX, barY, barW, barH);

        ctx.fillStyle = '#aaa';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(this.vmax.toFixed(2), barX + barW + 3, barY + 10);
        ctx.fillText(this.vmin.toFixed(2), barX + barW + 3, barY + barH);
    }

    public destroy(): void {
        this.canvas.remove();
    }
}
