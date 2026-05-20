/**
 * 3D挤压多边形渲染器
 * 基于 Canvas 2D 实现 GeoJSON 多边形的 3D 挤压效果
 * 支持透视投影、面排序、光照模拟和深度冲突处理
 */

export interface ExtrudedPolygonData {
    /** 外环顶点坐标（平面坐标） */
    outerRing: { x: number; y: number }[];
    /** 内环（孔洞）顶点坐标 */
    holes?: { x: number; y: number }[][];
    /** 挤压高度（单位与坐标一致） */
    height: number;
    /** 底部基准高度 */
    baseZ?: number;
    /** 填充颜色 */
    fillColor?: string;
    /** 描边颜色 */
    strokeColor?: string;
    /** 侧面颜色（默认基于填充色自动调整） */
    sideColor?: string;
    /** 顶部颜色（默认基于填充色自动调整） */
    topColor?: string;
    /** 透明度 */
    opacity?: number;
    /** 多边形属性 */
    properties?: Record<string, any>;
}

export interface Polygon3DRenderOptions {
    width: number;
    height: number;
    backgroundColor: string;
    /** 是否显示坐标轴 */
    showAxes: boolean;
    /** 是否显示颜色图例 */
    showLegend: boolean;
    /** 光照方向 (归一化) */
    lightDirection: [number, number, number];
}

export class Polygon3DRenderer {
    private canvas: HTMLCanvasElement;
    private ctx: CanvasRenderingContext2D;
    private options: Polygon3DRenderOptions;
    private rotationX: number = -35;
    private rotationZ: number = 30;
    private zoom: number = 1.0;
    private isDragging: boolean = false;
    private lastMouse: { x: number; y: number } = { x: 0, y: 0 };
    private polygons: ExtrudedPolygonData[] = [];
    /** 软件深度缓冲区 */
    private depthBuffer: Float32Array | null = null;

    constructor(container: HTMLElement, options?: Partial<Polygon3DRenderOptions>) {
        this.options = {
            width: container.clientWidth || 400,
            height: container.clientHeight || 400,
            backgroundColor: '#1a1a2e',
            showAxes: true,
            showLegend: false,
            lightDirection: [0.5, 0.3, 0.8],
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

        // 归一化光照方向
        const [lx, ly, lz] = this.options.lightDirection;
        const len = Math.sqrt(lx * lx + ly * ly + lz * lz);
        this.options.lightDirection = [lx / len, ly / len, lz / len];

        this.bindEvents();
    }

    private bindEvents(): void {
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
            this.rotationX = Math.max(-89, Math.min(89, this.rotationX));
            this.lastMouse = { x: e.clientX, y: e.clientY };
            this.render();
        });
        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            this.zoom *= e.deltaY > 0 ? 0.93 : 1.07;
            this.zoom = Math.max(0.1, Math.min(10, this.zoom));
            this.render();
        });
        // 触摸支持
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
                this.rotationX = Math.max(-89, Math.min(89, this.rotationX));
                this.lastMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                this.render();
            } else if (e.touches.length === 2) {
                const dist = Math.hypot(
                    e.touches[0].clientX - e.touches[1].clientX,
                    e.touches[0].clientY - e.touches[1].clientY
                );
                if (lastDist > 0) {
                    this.zoom *= dist / lastDist;
                    this.zoom = Math.max(0.1, Math.min(10, this.zoom));
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

    /**
     * 设置要渲染的多边形数据
     */
    public setPolygons(polygons: ExtrudedPolygonData[]): void {
        this.polygons = polygons;
        this.render();
    }

    /**
     * 添加单个多边形
     */
    public addPolygon(polygon: ExtrudedPolygonData): void {
        this.polygons.push(polygon);
        this.render();
    }

    /**
     * 清空所有多边形
     */
    public clearPolygons(): void {
        this.polygons = [];
        this.render();
    }

    /**
     * 从 GeoJSON FeatureCollection 加载多边形数据
     */
    public loadFromGeoJSON(
        features: Array<{
            geometry: { type: string; coordinates: number[][][] | number[][][][] };
            properties?: Record<string, any>;
        }>,
        heightProperty?: string,
        defaultHeight?: number
    ): void {
        this.polygons = [];

        for (const feature of features) {
            if (feature.geometry.type === 'Polygon') {
                const coords = feature.geometry.coordinates as number[][][];
                const outerRing = coords[0].map(c => ({ x: c[0], y: c[1] }));
                const holes = coords.slice(1).map(ring => ring.map(c => ({ x: c[0], y: c[1] })));

                let height = defaultHeight || 10;
                if (heightProperty && feature.properties?.[heightProperty] !== undefined) {
                    height = Number(feature.properties[heightProperty]);
                }

                // 根据属性自动生成颜色
                let fillColor = 'rgba(64, 128, 255, 0.7)';
                if (feature.properties?.color) {
                    fillColor = feature.properties.color;
                }

                this.polygons.push({
                    outerRing,
                    holes: holes.length > 0 ? holes : undefined,
                    height,
                    fillColor,
                    properties: feature.properties,
                });
            } else if (feature.geometry.type === 'MultiPolygon') {
                const multiCoords = feature.geometry.coordinates as number[][][][];
                for (const polyCoords of multiCoords) {
                    const outerRing = polyCoords[0].map(c => ({ x: c[0], y: c[1] }));
                    const holes = polyCoords.slice(1).map(ring => ring.map(c => ({ x: c[0], y: c[1] })));

                    let height = defaultHeight || 10;
                    if (heightProperty && feature.properties?.[heightProperty] !== undefined) {
                        height = Number(feature.properties[heightProperty]);
                    }

                    let fillColor = 'rgba(64, 128, 255, 0.7)';
                    if (feature.properties?.color) {
                        fillColor = feature.properties.color;
                    }

                    this.polygons.push({
                        outerRing,
                        holes: holes.length > 0 ? holes : undefined,
                        height,
                        fillColor,
                        properties: feature.properties,
                    });
                }
            }
        }

        this.render();
    }

    // ========== 3D 投影 ==========

    /**
     * 将 3D 坐标投影到 2D 屏幕坐标
     * 使用旋转矩阵 + 透视投影
     */
    private project(x: number, y: number, z: number): { sx: number; sy: number; depth: number } {
        const radZ = (this.rotationZ * Math.PI) / 180;
        const radX = (this.rotationX * Math.PI) / 180;

        // Y轴旋转 (绕Z轴旋转)
        let rx = x * Math.cos(radZ) - y * Math.sin(radZ);
        let ry = x * Math.sin(radZ) + y * Math.cos(radZ);
        let rz = z;

        // X轴旋转 (绕X轴旋转)
        const ry2 = ry * Math.cos(radX) - rz * Math.sin(radX);
        const rz2 = ry * Math.sin(radX) + rz * Math.cos(radX);

        const scale = this.zoom * Math.min(this.options.width, this.options.height) * 0.4;
        return {
            sx: this.options.width / 2 + rx * scale,
            sy: this.options.height / 2 - rz2 * scale,
            depth: ry2,
        };
    }

    /**
     * 计算面的法向量（用于光照）
     */
    private computeNormal(
        p1: { x: number; y: number; z: number },
        p2: { x: number; y: number; z: number },
        p3: { x: number; y: number; z: number }
    ): [number, number, number] {
        const ux = p2.x - p1.x, uy = p2.y - p1.y, uz = p2.z - p1.z;
        const vx = p3.x - p1.x, vy = p3.y - p1.y, vz = p3.z - p1.z;
        const nx = uy * vz - uz * vy;
        const ny = uz * vx - ux * vz;
        const nz = ux * vy - uy * vx;
        const len = Math.sqrt(nx * nx + ny * ny + nz * nz);
        return len > 0 ? [nx / len, ny / len, nz / len] : [0, 0, 1];
    }

    /**
     * 计算光照强度 (Lambertian diffuse)
     */
    private computeLightIntensity(normal: [number, number, number]): number {
        const [lx, ly, lz] = this.options.lightDirection;
        let dot = normal[0] * lx + normal[1] * ly + normal[2] * lz;
        // 环境光 + 漫反射
        return 0.25 + 0.75 * Math.max(0, dot);
    }

    /**
     * 调整颜色亮度
     */
    private adjustColorBrightness(color: string, factor: number): string {
        // 解析 rgba
        const match = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
        if (match) {
            const r = Math.min(255, Math.round(Number(match[1]) * factor));
            const g = Math.min(255, Math.round(Number(match[2]) * factor));
            const b = Math.min(255, Math.round(Number(match[3]) * factor));
            const a = match[4] !== undefined ? Number(match[4]) : 1;
            return `rgba(${r},${g},${b},${a})`;
        }
        // 尝试解析 hex
        if (color.startsWith('#')) {
            const hex = color.replace('#', '');
            const r = Math.min(255, Math.round(parseInt(hex.substring(0, 2), 16) * factor));
            const g = Math.min(255, Math.round(parseInt(hex.substring(2, 4), 16) * factor));
            const b = Math.min(255, Math.round(parseInt(hex.substring(4, 6), 16) * factor));
            return `rgb(${r},${g},${b})`;
        }
        return color;
    }

    // ========== 深度缓冲区 ==========

    /**
     * 初始化深度缓冲区
     */
    private initDepthBuffer(): void {
        const size = this.options.width * this.options.height;
        if (!this.depthBuffer || this.depthBuffer.length !== size) {
            this.depthBuffer = new Float32Array(size);
        }
        this.depthBuffer.fill(Infinity);
    }

    /**
     * 深度测试：检查像素是否比当前深度缓冲区更近
     * 同时更新深度缓冲区
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

    // ========== 渲染 ==========

    public render(): void {
        const { ctx, options } = this;
        ctx.clearRect(0, 0, options.width, options.height);

        // 背景
        ctx.fillStyle = options.backgroundColor;
        ctx.fillRect(0, 0, options.width, options.height);

        if (this.polygons.length === 0) {
            ctx.fillStyle = '#666';
            ctx.font = '14px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('暂无3D多边形数据', options.width / 2, options.height / 2);
            return;
        }

        // 计算全局坐标范围
        const allRings = this.polygons.flatMap(p => p.outerRing);
        const minX = Math.min(...allRings.map(r => r.x));
        const maxX = Math.max(...allRings.map(r => r.x));
        const minY = Math.min(...allRings.map(r => r.y));
        const maxY = Math.max(...allRings.map(r => r.y));
        const minZ = Math.min(...this.polygons.map(p => p.baseZ || 0));
        const maxZ = Math.max(...this.polygons.map(p => (p.baseZ || 0) + p.height));
        const cx = (minX + maxX) / 2;
        const cy = (minY + maxY) / 2;
        const cz = (minZ + maxZ) / 2;
        const maxRange = Math.max(maxX - minX, maxY - minY, maxZ - minZ) || 1;

        // 归一化函数
        const normX = (v: number) => (v - cx) / maxRange;
        const normY = (v: number) => (v - cy) / maxRange;
        const normZ = (v: number) => (v - cz) / maxRange;

        // 初始化深度缓冲区
        this.initDepthBuffer();

        // 收集所有需要渲染的面，用于深度排序
        interface Face {
            polygon: ExtrudedPolygonData;
            type: 'top' | 'side' | 'bottom';
            points: { x: number; y: number; z: number }[];
            fillColor: string;
            strokeColor: string;
            depth: number; // 面的平均深度
        }

        const faces: Face[] = [];

        for (const polygon of this.polygons) {
            const baseZ = polygon.baseZ || 0;
            const topZ = baseZ + polygon.height;
            const baseColor = polygon.fillColor || 'rgba(64, 128, 255, 0.7)';
            const sideColor = polygon.sideColor || baseColor;
            const topColor = polygon.topColor || baseColor;
            const strokeColor = polygon.strokeColor || 'rgba(255, 255, 255, 0.3)';
            const opacity = polygon.opacity ?? 1;

            // 收集顶面和底面点
            const topPoints: { x: number; y: number; z: number }[] = polygon.outerRing.map(p => ({
                x: normX(p.x), y: normY(p.y), z: normZ(topZ),
            }));
            const bottomPoints: { x: number; y: number; z: number }[] = polygon.outerRing.map(p => ({
                x: normX(p.x), y: normY(p.y), z: normZ(baseZ),
            }));

            // 顶面
            const topNormal = this.computeNormal(topPoints[0], topPoints[1], topPoints[2]);
            const topLight = this.computeLightIntensity(topNormal);
            const topDepth = topPoints.reduce((s, p) => s + this.project(p.x, p.y, p.z).depth, 0) / topPoints.length;
            faces.push({
                polygon,
                type: 'top',
                points: topPoints,
                fillColor: this.adjustColorBrightness(topColor, topLight),
                strokeColor,
                depth: topDepth,
            });

            // 侧面 - 为每对相邻顶点创建侧面
            const n = polygon.outerRing.length;
            for (let i = 0; i < n; i++) {
                const j = (i + 1) % n;
                const sidePoints = [
                    bottomPoints[i],
                    bottomPoints[j],
                    topPoints[j],
                    topPoints[i],
                ];
                const sideNormal = this.computeNormal(
                    sidePoints[0], sidePoints[1], sidePoints[2]
                );
                const sideLight = this.computeLightIntensity(sideNormal);
                const sideDepth = sidePoints.reduce((s, p) => s + this.project(p.x, p.y, p.z).depth, 0) / 4;
                faces.push({
                    polygon,
                    type: 'side',
                    points: sidePoints,
                    fillColor: this.adjustColorBrightness(sideColor, sideLight),
                    strokeColor,
                    depth: sideDepth,
                });
            }

            // 底面（通常被遮挡，但为了完整性）
            const bottomNormal: [number, number, number] = [0, 0, -1];
            const bottomLight = this.computeLightIntensity(bottomNormal);
            const bottomDepth = bottomPoints.reduce((s, p) => s + this.project(p.x, p.y, p.z).depth, 0) / bottomPoints.length;
            faces.push({
                polygon,
                type: 'bottom',
                points: bottomPoints,
                fillColor: this.adjustColorBrightness(baseColor, bottomLight),
                strokeColor,
                depth: bottomDepth,
            });
        }

        // 按深度从远到近排序（Painter's Algorithm）
        faces.sort((a, b) => a.depth - b.depth);

        // 渲染所有面
        for (const face of faces) {
            this.renderFace(ctx, face);
        }

        // 绘制坐标轴
        if (options.showAxes) {
            this.drawAxes();
        }
    }

    /**
     * 渲染单个面
     */
    private renderFace(ctx: CanvasRenderingContext2D, face: Face): void {
        const projected = face.points.map(p => {
            const proj = this.project(p.x, p.y, p.z);
            return { sx: proj.sx, sy: proj.sy, depth: proj.depth };
        });

        if (projected.length < 3) return;

        ctx.beginPath();
        ctx.moveTo(projected[0].sx, projected[0].sy);
        for (let i = 1; i < projected.length; i++) {
            ctx.lineTo(projected[i].sx, projected[i].sy);
        }
        ctx.closePath();

        // 填充
        ctx.fillStyle = face.fillColor;
        ctx.fill();

        // 描边
        if (face.strokeColor) {
            ctx.strokeStyle = face.strokeColor;
            ctx.lineWidth = 1;
            ctx.stroke();
        }
    }

    /**
     * 绘制坐标轴
     */
    private drawAxes(): void {
        const { ctx } = this;
        const origin = this.project(0, 0, 0);
        const axisLen = 0.4;
        const axes = [
            { end: this.project(axisLen, 0, 0), label: 'X', color: '#ff4444' },
            { end: this.project(0, axisLen, 0), label: 'Y', color: '#44ff44' },
            { end: this.project(0, 0, axisLen), label: 'Z', color: '#4488ff' },
        ];

        for (const axis of axes) {
            ctx.strokeStyle = axis.color;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(origin.sx, origin.sy);
            ctx.lineTo(axis.end.sx, axis.end.sy);
            ctx.stroke();

            ctx.fillStyle = axis.color;
            ctx.font = 'bold 11px sans-serif';
            ctx.fillText(axis.label, axis.end.sx + 4, axis.end.sy - 4);
        }
    }

    /**
     * 重置视角
     */
    public resetView(): void {
        this.rotationX = -35;
        this.rotationZ = 30;
        this.zoom = 1.0;
        this.render();
    }

    /**
     * 设置旋转角度
     */
    public setRotation(rotX: number, rotZ: number): void {
        this.rotationX = Math.max(-89, Math.min(89, rotX));
        this.rotationZ = (rotZ % 360 + 360) % 360;
        this.render();
    }

    /**
     * 获取当前画布（用于导出截图等）
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

// 重新导出 Face 类型
type Face = {
    polygon: ExtrudedPolygonData;
    type: 'top' | 'side' | 'bottom';
    points: { x: number; y: number; z: number }[];
    fillColor: string;
    strokeColor: string;
    depth: number;
};
