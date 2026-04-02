/**
 * 参数关系图组件
 * 负责展示双参数关系、约束可行域与历史轨迹
 */

export type RelationshipRegionType = 'valid' | 'warning' | 'invalid';

export interface RelationshipAxisConfig {
    key: string;
    label: string;
    min: number;
    max: number;
}

export interface RelationshipConstraintConfig {
    label: string;
    validate: (x: number, y: number) => boolean;
}

export interface RelationshipChartConfig {
    axisX: RelationshipAxisConfig;
    axisY: RelationshipAxisConfig;
    constraint?: RelationshipConstraintConfig;
    maxHistoryPoints?: number;
    onPointSelected?: (x: number, y: number) => void;
}

export class ParameterRelationshipChart {
    private static readonly PADDING = { top: 24, right: 20, bottom: 38, left: 44 };

    private container: HTMLElement;
    private canvas: HTMLCanvasElement;
    private ctx: CanvasRenderingContext2D;
    private config: RelationshipChartConfig;
    private currentPoint: { x: number; y: number } | null = null;
    private historyPoints: Array<{ x: number; y: number }> = [];
    private regionHighlight: RelationshipRegionType | null = null;

    public constructor(container: HTMLElement, config: RelationshipChartConfig) {
        this.container = container;
        this.config = {
            ...config,
            maxHistoryPoints: config.maxHistoryPoints ?? 30
        };

        this.canvas = document.createElement('canvas');
        this.canvas.className = 'parameter-relationship-canvas';
        this.ctx = this.getContext(this.canvas);

        this.container.innerHTML = '';
        this.container.appendChild(this.canvas);

        this.bindEvents();
        this.resize();
    }

    public update(paramX: number, paramY: number): void {
        const normalizedX = this.clamp(paramX, this.config.axisX.min, this.config.axisX.max);
        const normalizedY = this.clamp(paramY, this.config.axisY.min, this.config.axisY.max);

        const previous = this.currentPoint;
        this.currentPoint = { x: normalizedX, y: normalizedY };

        if (!previous || previous.x !== normalizedX || previous.y !== normalizedY) {
            this.historyPoints.push({ x: normalizedX, y: normalizedY });
            const maxHistoryPoints = this.config.maxHistoryPoints ?? 30;
            if (this.historyPoints.length > maxHistoryPoints) {
                this.historyPoints.splice(0, this.historyPoints.length - maxHistoryPoints);
            }
        }

        this.render();
    }

    public highlightRegion(regionType: RelationshipRegionType): void {
        this.regionHighlight = regionType;
        this.render();
    }

    public setAxes(axisX: RelationshipAxisConfig, axisY: RelationshipAxisConfig): void {
        this.config.axisX = axisX;
        this.config.axisY = axisY;
        this.historyPoints = [];
        this.currentPoint = null;
        this.render();
    }

    public setConstraint(constraint?: RelationshipConstraintConfig): void {
        this.config.constraint = constraint;
        this.render();
    }

    public resize(): void {
        const rect = this.container.getBoundingClientRect();
        this.canvas.width = Math.max(280, Math.floor(rect.width || 280));
        this.canvas.height = Math.max(220, Math.floor(rect.height || 220));
        this.render();
    }

    private getContext(canvas: HTMLCanvasElement): CanvasRenderingContext2D {
        const context = canvas.getContext('2d');
        if (!context) {
            throw new Error('无法初始化参数关系图 Canvas 上下文');
        }
        return context;
    }

    private bindEvents(): void {
        window.addEventListener('resize', () => this.resize());

        this.canvas.addEventListener('click', (event) => {
            if (!this.config.onPointSelected) {
                return;
            }
            const rect = this.canvas.getBoundingClientRect();
            const px = event.clientX - rect.left;
            const py = event.clientY - rect.top;
            const point = this.pixelToData(px, py);
            this.config.onPointSelected(point.x, point.y);
        });
    }

    private render(): void {
        const { ctx, canvas } = this;
        const padding = ParameterRelationshipChart.PADDING;
        const width = canvas.width;
        const height = canvas.height;
        const plotWidth = width - padding.left - padding.right;
        const plotHeight = height - padding.top - padding.bottom;

        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, width, height);

        this.drawGrid(ctx, padding, plotWidth, plotHeight);
        this.drawConstraintRegion(ctx, padding, plotWidth, plotHeight);
        this.drawHistory(ctx, padding, plotWidth, plotHeight);
        this.drawCurrentPoint(ctx, padding, plotWidth, plotHeight);
        this.drawAxes(ctx, padding, plotWidth, plotHeight);
        this.drawConstraintLabel(ctx, width);
    }

    private drawGrid(
        ctx: CanvasRenderingContext2D,
        padding: { top: number; right: number; bottom: number; left: number },
        plotWidth: number,
        plotHeight: number
    ): void {
        ctx.strokeStyle = '#e4e7ec';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
            const x = padding.left + (plotWidth * i) / 4;
            ctx.beginPath();
            ctx.moveTo(x, padding.top);
            ctx.lineTo(x, padding.top + plotHeight);
            ctx.stroke();

            const y = padding.top + (plotHeight * i) / 4;
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(padding.left + plotWidth, y);
            ctx.stroke();
        }
    }

    private drawConstraintRegion(
        ctx: CanvasRenderingContext2D,
        padding: { top: number; right: number; bottom: number; left: number },
        plotWidth: number,
        plotHeight: number
    ): void {
        if (!this.config.constraint) {
            return;
        }

        const validColor = this.regionHighlight === 'invalid' ? 'rgba(250, 160, 120, 0.2)' : 'rgba(82, 196, 26, 0.18)';
        const invalidColor = this.regionHighlight === 'valid' ? 'rgba(245, 63, 63, 0.09)' : 'rgba(245, 63, 63, 0.16)';

        const sampleX = 64;
        const sampleY = 44;
        const cellWidth = plotWidth / sampleX;
        const cellHeight = plotHeight / sampleY;
        const rangeX = Math.max(1e-6, this.config.axisX.max - this.config.axisX.min);
        const rangeY = Math.max(1e-6, this.config.axisY.max - this.config.axisY.min);

        for (let xi = 0; xi < sampleX; xi++) {
            for (let yi = 0; yi < sampleY; yi++) {
                const xRatio = (xi + 0.5) / sampleX;
                const yRatio = (yi + 0.5) / sampleY;
                const valueX = this.config.axisX.min + xRatio * rangeX;
                const valueY = this.config.axisY.max - yRatio * rangeY;
                const isValid = this.config.constraint.validate(valueX, valueY);

                ctx.fillStyle = isValid ? validColor : invalidColor;
                ctx.fillRect(
                    padding.left + xi * cellWidth,
                    padding.top + yi * cellHeight,
                    Math.ceil(cellWidth + 0.8),
                    Math.ceil(cellHeight + 0.8)
                );
            }
        }
    }

    private drawHistory(
        ctx: CanvasRenderingContext2D,
        padding: { top: number; right: number; bottom: number; left: number },
        plotWidth: number,
        plotHeight: number
    ): void {
        if (this.historyPoints.length < 2) {
            return;
        }

        ctx.strokeStyle = '#94a3b8';
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        this.historyPoints.forEach((point, index) => {
            const x = this.dataToPixelX(point.x, padding.left, plotWidth);
            const y = this.dataToPixelY(point.y, padding.top, plotHeight);
            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        ctx.stroke();
    }

    private drawCurrentPoint(
        ctx: CanvasRenderingContext2D,
        padding: { top: number; right: number; bottom: number; left: number },
        plotWidth: number,
        plotHeight: number
    ): void {
        if (!this.currentPoint) {
            return;
        }

        const x = this.dataToPixelX(this.currentPoint.x, padding.left, plotWidth);
        const y = this.dataToPixelY(this.currentPoint.y, padding.top, plotHeight);

        const isValid = this.config.constraint
            ? this.config.constraint.validate(this.currentPoint.x, this.currentPoint.y)
            : true;

        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fillStyle = isValid ? '#1677ff' : '#ff4d4f';
        ctx.fill();

        ctx.beginPath();
        ctx.arc(x, y, 9, 0, Math.PI * 2);
        ctx.strokeStyle = isValid ? 'rgba(22, 119, 255, 0.35)' : 'rgba(255, 77, 79, 0.35)';
        ctx.lineWidth = 3;
        ctx.stroke();
    }

    private drawAxes(
        ctx: CanvasRenderingContext2D,
        padding: { top: number; right: number; bottom: number; left: number },
        plotWidth: number,
        plotHeight: number
    ): void {
        ctx.strokeStyle = '#475467';
        ctx.lineWidth = 1.2;

        ctx.beginPath();
        ctx.moveTo(padding.left, padding.top);
        ctx.lineTo(padding.left, padding.top + plotHeight);
        ctx.lineTo(padding.left + plotWidth, padding.top + plotHeight);
        ctx.stroke();

        ctx.fillStyle = '#344054';
        ctx.font = '12px sans-serif';
        ctx.fillText(this.config.axisY.label, 8, padding.top + 10);
        ctx.fillText(this.config.axisX.label, padding.left + plotWidth - 44, padding.top + plotHeight + 28);
    }

    private drawConstraintLabel(ctx: CanvasRenderingContext2D, width: number): void {
        if (!this.config.constraint) {
            return;
        }

        ctx.fillStyle = '#667085';
        ctx.font = '12px sans-serif';
        const text = `约束: ${this.config.constraint.label}`;
        const metrics = ctx.measureText(text);
        ctx.fillText(text, Math.max(8, width - metrics.width - 8), 16);
    }

    private dataToPixelX(x: number, left: number, plotWidth: number): number {
        const { min, max } = this.config.axisX;
        const ratio = (x - min) / Math.max(1e-6, max - min);
        return left + ratio * plotWidth;
    }

    private dataToPixelY(y: number, top: number, plotHeight: number): number {
        const { min, max } = this.config.axisY;
        const ratio = (y - min) / Math.max(1e-6, max - min);
        return top + plotHeight - ratio * plotHeight;
    }

    private pixelToData(x: number, y: number): { x: number; y: number } {
        const padding = ParameterRelationshipChart.PADDING;
        const plotWidth = this.canvas.width - padding.left - padding.right;
        const plotHeight = this.canvas.height - padding.top - padding.bottom;

        const xRatio = (x - padding.left) / Math.max(1e-6, plotWidth);
        const yRatio = (y - padding.top) / Math.max(1e-6, plotHeight);

        const valueX = this.config.axisX.min + this.clamp(xRatio, 0, 1) * (this.config.axisX.max - this.config.axisX.min);
        const valueY = this.config.axisY.max - this.clamp(yRatio, 0, 1) * (this.config.axisY.max - this.config.axisY.min);

        return {
            x: Number(valueX.toFixed(3)),
            y: Number(valueY.toFixed(3))
        };
    }

    private clamp(value: number, min: number, max: number): number {
        return Math.min(max, Math.max(min, value));
    }
}
