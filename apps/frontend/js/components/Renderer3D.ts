/**
 * 3D可视化渲染器
 * 基于 Canvas 2D 的轻量级 3D 点云、采样点和表面渲染
 * 支持旋转、缩放、颜色映射、软件深度缓冲区和球体渲染
 */

export interface Render3DOptions {
    width: number;
    height: number;
    backgroundColor: string;
    pointSize: number;
    colorMap: 'rainbow' | 'viridis' | 'hot' | 'cool';
    opacity: number;
    /** 渲染模式: points=点, spheres=球体, surface=表面 */
    renderMode: 'points' | 'spheres' | 'surface';
    /** 是否启用软件深度缓冲区 */
    enableDepthBuffer: boolean;
    /** 光照方向 (归一化) */
    lightDirection: [number, number, number];
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
    /** 软件深度缓冲区 */
    private depthBuffer: Float32Array | null = null;
    /** 光照方向 (归一化) */
    private lightDir: [number, number, number];

    constructor(container: HTMLElement, options?: Partial<Render3DOptions>) {
        this.options = {
            width: container.clientWidth || 400,
            height: container.clientHeight || 400,
            backgroundColor: '#1a1a2e',
            pointSize: 3,
            colorMap: 'rainbow',
            opacity: 0.8,
            renderMode: 'points',
            enableDepthBuffer: true,
            lightDirection: [0.5, 0.3, 0.8],
            ...options,
        };

        // 归一化光照方向
        const [lx, ly, lz] = this.options.lightDirection;
        const len = Math.sqrt(lx * lx + ly * ly + lz * lz);
        this.lightDir = [lx / len, ly / len, lz / len];

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
        // 触摸支持（移动端）
        this.bindTouchEvents();
    }

    private bindTouchEvents(): void {
        let lastDist = 0;
        this.canvas.addEventListener('touchstart', (e) => {
            if (e.touches.length === 1) {
                this.isDragging = true;
                this.lastMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
            } else if (e.touches.length === 2) {
                lastDist = Math.hypot(
                    e.touches[0].clientX - e.touches[1].clientX,
                    e.touches[0].clientY - e.touches[1].clientY
                );
            }
        });
        this.canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            if (e.touches.length === 1 && this.isDragging) {
                const dx = e.touches[0].clientX - this.lastMouse.x;
                const dy = e.touches[0].clientY - this.lastMouse.y;
                this.rotationZ += dx * 0.5;
                this.rotationX += dy * 0.5;
                this.rotationX = Math.max(-90, Math.min(90, this.rotationX));
                this.lastMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                this.render();
            } else if (e.touches.length === 2) {
                const dist = Math.hypot(
                    e.touches[0].clientX - e.touches[1].clientX,
                    e.touches[0].clientY - e.touches[1].clientY
                );
                if (lastDist > 0) {
                    this.zoom *= dist / lastDist;
                    this.zoom = Math.max(0.1, Math.min(5, this.zoom));
                    this.render();
                }
                lastDist = dist;
            }
        }, { passive: false });
        this.canvas.addEventListener('touchend', () => {
            this.isDragging = false;
            lastDist = 0;
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

    private valueToColor(value: number): [number, number, number, number] {
        const t = this.vmax > this.vmin
            ? Math.max(0, Math.min(1, (value - this.vmin) / (this.vmax - this.vmin)))
            : 0.5;

        let r: number, g: number, b: number;

        switch (this.options.colorMap) {
            case 'rainbow':
                r = Math.round(255 * Math.min(1, Math.max(0, 2 - 4 * Math.abs(t - 0.5))));
                g = Math.round(255 * Math.min(1, Math.max(0, 2 * t - 4 * Math.abs(t - 0.75))));
                b = Math.round(255 * Math.min(1, Math.max(0, 2 * (1 - t))));
                break;
            case 'hot':
                r = Math.round(255 * Math.min(1, 3 * t));
                g = Math.round(255 * Math.min(1, 3 * t - 1));
                b = Math.round(255 * Math.min(1, 3 * t - 2));
                break;
            case 'cool':
                r = Math.round(255 * (1 - t));
                g = Math.round(255 * t);
                b = Math.round(255);
                break;
            case 'viridis':
                // 简化 viridis 近似
                r = Math.round(255 * (0.267 + 0.723 * (1 - t) * t * 2.5));
                g = Math.round(255 * (0.004 + 0.873 * Math.sin(t * Math.PI / 2)));
                b = Math.round(255 * (0.329 + 0.329 * (1 - Math.abs(2 * t - 1))));
                break;
            default:
                r = Math.round(255 * Math.min(1, 2 * t));
                g = Math.round(255 * Math.min(1, 2 * (1 - t)));
                b = Math.round(100 + 155 * (1 - Math.abs(2 * t - 1)));
        }

        return [r, g, b, this.options.opacity];
    }

    /**
     * 初始化/重置深度缓冲区
     */
    private initDepthBuffer(): void {
        if (!this.options.enableDepthBuffer) {
            this.depthBuffer = null;
            return;
        }
        const size = this.options.width * this.options.height;
        if (!this.depthBuffer || this.depthBuffer.length !== size) {
            this.depthBuffer = new Float32Array(size);
        }
        this.depthBuffer.fill(Infinity);
    }

    /**
     * 深度测试：检查像素深度并更新缓冲区
     * @returns true 如果通过深度测试（比当前缓冲更近）
     */
    private depthTest(px: number, py: number, depth: number): boolean {
        if (!this.depthBuffer) return true;
        const x = Math.round(px);
        const y = Math.round(py);
        if (x < 0 || x >= this.options.width || y < 0 || y >= this.options.height) return false;
        const idx = y * this.options.width + x;
        if (depth < this.depthBuffer[idx]) {
            this.depthBuffer[idx] = depth;
            return true;
        }
        return false;
    }

    /**
     * 计算球体表面法向量
     */
    private computeSphereNormal(
        px: number, py: number,
        cx: number, cy: number,
        radius: number
    ): [number, number, number] {
        const dx = (px - cx) / radius;
        const dy = (py - cy) / radius;
        const dz2 = 1 - dx * dx - dy * dy;
        const dz = dz2 > 0 ? Math.sqrt(dz2) : 0;
        const len = Math.sqrt(dx * dx + dy * dy + dz * dz);
        return len > 0 ? [dx / len, dy / len, dz / len] : [0, 0, 1];
    }

    /**
     * 绘制3D球体（使用径向渐变模拟光照）
     */
    private drawSphere(
        ctx: CanvasRenderingContext2D,
        sx: number, sy: number,
        radius: number,
        color: [number, number, number, number]
    ): void {
        // 高光偏移（模拟光源方向）
        const [lx, ly, lz] = this.lightDir;
        const highlightX = sx - lx * radius * 0.3;
        const highlightY = sy - ly * radius * 0.3;

        // 基础渐变：从高光到暗面
        const gradient = ctx.createRadialGradient(
            highlightX, highlightY, radius * 0.05,
            sx, sy, radius
        );
        const [r, g, b, a] = color;
        gradient.addColorStop(0, `rgba(${Math.min(255, r + 60)},${Math.min(255, g + 60)},${Math.min(255, b + 60)},${a})`);
        gradient.addColorStop(0.4, `rgba(${r},${g},${b},${a})`);
        gradient.addColorStop(0.8, `rgba(${Math.round(r * 0.5)},${Math.round(g * 0.5)},${Math.round(b * 0.5)},${a})`);
        gradient.addColorStop(1, `rgba(${Math.round(r * 0.2)},${Math.round(g * 0.2)},${Math.round(b * 0.2)},${a})`);

        ctx.beginPath();
        ctx.arc(sx, sy, radius, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();

        // 边缘高光
        const edgeGradient = ctx.createRadialGradient(
            highlightX, highlightY, radius * 0.7,
            sx, sy, radius * 1.05
        );
        edgeGradient.addColorStop(0, 'rgba(255,255,255,0)');
        edgeGradient.addColorStop(1, 'rgba(255,255,255,0.15)');
        ctx.beginPath();
        ctx.arc(sx, sy, radius, 0, Math.PI * 2);
        ctx.fillStyle = edgeGradient;
        ctx.fill();
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

        // 初始化深度缓冲区
        this.initDepthBuffer();

        // 投影并按深度排序
        interface ProjectedPoint {
            sx: number; sy: number; depth: number;
            nx: number; ny: number; nz: number;
            value: number;
        }

        const projected: ProjectedPoint[] = this.points.map(p => {
            const nx = (p.x - cx) / maxRange;
            const ny = (p.y - cy) / maxRange;
            const nz = (p.z - cz) / maxRange;
            const proj = this.project(nx, ny, nz);
            return { ...proj, nx, ny, nz, value: p.value };
        });
        projected.sort((a, b) => a.depth - b.depth);

        // 根据渲染模式绘制
        if (options.renderMode === 'spheres') {
            this.renderSpheres(ctx, projected, options);
        } else if (options.renderMode === 'surface') {
            this.renderSurface(ctx, projected, options);
        } else {
            this.renderPoints(ctx, projected, options);
        }

        // 绘制坐标轴
        this.drawAxes(maxRange);

        // 绘制颜色条
        this.drawColorBar();
    }

    /**
     * 点云渲染模式（带深度测试）
     */
    private renderPoints(
        ctx: CanvasRenderingContext2D,
        projected: Array<{ sx: number; sy: number; depth: number; value: number }>,
        options: Render3DOptions
    ): void {
        for (const p of projected) {
            if (options.enableDepthBuffer && !this.depthTest(p.sx, p.sy, p.depth)) continue;
            const [r, g, b, a] = this.valueToColor(p.value);
            ctx.fillStyle = `rgba(${r},${g},${b},${a})`;
            ctx.beginPath();
            ctx.arc(p.sx, p.sy, options.pointSize, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    /**
     * 球体渲染模式（3D光照球体）
     */
    private renderSpheres(
        ctx: CanvasRenderingContext2D,
        projected: Array<{ sx: number; sy: number; depth: number; nx: number; ny: number; nz: number; value: number }>,
        options: Render3DOptions
    ): void {
        const baseRadius = Math.max(options.pointSize, 3);
        // 根据深度调整球体大小（透视效果）
        for (const p of projected) {
            if (options.enableDepthBuffer && !this.depthTest(p.sx, p.sy, p.depth)) continue;

            const color = this.valueToColor(p.value);
            const radius = baseRadius * (1 + p.nz * 0.3); // 高度越高的点越大
            this.drawSphere(ctx, p.sx, p.sy, radius, color);
        }
    }

    /**
     * 表面渲染模式（基于点云生成表面）
     */
    private renderSurface(
        ctx: CanvasRenderingContext2D,
        projected: Array<{ sx: number; sy: number; depth: number; nx: number; ny: number; nz: number; value: number }>,
        options: Render3DOptions
    ): void {
        // 将投影点按网格分组，绘制三角形表面
        const gridSize = Math.ceil(Math.sqrt(projected.length));
        const cellSize = Math.min(options.width, options.height) / gridSize;

        // 绘制连线网格
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.lineWidth = 0.5;

        // 简单三角剖分：相邻点连线
        for (let i = 0; i < projected.length - 1; i++) {
            const p = projected[i];
            for (let j = i + 1; j < Math.min(i + 4, projected.length); j++) {
                const q = projected[j];
                const dist = Math.hypot(p.sx - q.sx, p.sy - q.sy);
                if (dist < cellSize * 1.5) {
                    ctx.beginPath();
                    ctx.moveTo(p.sx, p.sy);
                    ctx.lineTo(q.sx, q.sy);
                    ctx.stroke();
                }
            }
        }

        // 再叠加点以提高可视化效果
        for (const p of projected) {
            if (options.enableDepthBuffer && !this.depthTest(p.sx, p.sy, p.depth)) continue;
            const [r, g, b, a] = this.valueToColor(p.value);
            ctx.fillStyle = `rgba(${r},${g},${b},${a})`;
            ctx.beginPath();
            ctx.arc(p.sx, p.sy, options.pointSize, 0, Math.PI * 2);
            ctx.fill();
        }
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
            const [r, g, b] = this.valueToColor(val);
            ctx.fillStyle = `rgb(${r},${g},${b})`;
            ctx.fillRect(barX, barY + i, barW, 1);
        }

        ctx.strokeStyle = '#666';
        ctx.lineWidth = 1;
        ctx.strokeRect(barX, barY, barW, barH);

        ctx.fillStyle = '#aaa';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(this.vmax.toFixed(2), barX + barW + 3, barY + 10);
        ctx.fillText(this.vmin.toFixed(2), barX + barW + 3, barY + barH);
    }

    // ========== 公共控制方法 ==========

    /**
     * 重置视角
     */
    public resetView(): void {
        this.rotationX = -30;
        this.rotationZ = 45;
        this.zoom = 1.0;
        this.render();
    }

    /**
     * 设置渲染模式
     */
    public setRenderMode(mode: 'points' | 'spheres' | 'surface'): void {
        this.options.renderMode = mode;
        this.render();
    }

    /**
     * 设置颜色映射
     */
    public setColorMap(map: 'rainbow' | 'viridis' | 'hot' | 'cool'): void {
        this.options.colorMap = map;
        this.render();
    }

    /**
     * 设置球体/点大小
     */
    public setPointSize(size: number): void {
        this.options.pointSize = Math.max(1, Math.min(20, size));
        this.render();
    }

    /**
     * 获取当前画布
     */
    public getCanvas(): HTMLCanvasElement {
        return this.canvas;
    }

    /**
     * 导出为 Data URL
     */
    public toDataURL(type?: string, quality?: number): string {
        return this.canvas.toDataURL(type, quality);
    }

    public destroy(): void {
        this.canvas.remove();
        this.depthBuffer = null;
    }
}
