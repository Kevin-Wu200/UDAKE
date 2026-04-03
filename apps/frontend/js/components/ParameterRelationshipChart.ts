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
    statusResolver?: (x: number, y: number) => RelationshipRegionType;
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
    private hoveredPoint: { x: number; y: number; source: 'current' | 'history' } | null = null;
    private tooltipEl: HTMLDivElement;

    public constructor(container: HTMLElement, config: RelationshipChartConfig) {
        this.container = container;
        this.config = {
            ...config,
            maxHistoryPoints: config.maxHistoryPoints ?? 30
        };

        this.canvas = document.createElement('canvas');
        this.canvas.className = 'parameter-relationship-canvas';
        this.ctx = this.getContext(this.canvas);
        this.tooltipEl = this.createTooltip();

        this.container.innerHTML = '';
        this.container.appendChild(this.canvas);
        this.container.appendChild(this.tooltipEl);

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

        this.canvas.addEventListener('mousemove', (event) => {
            this.handlePointerMove(event.clientX, event.clientY, false);
        });

        this.canvas.addEventListener('mouseleave', () => {
            this.clearHover();
        });

        this.canvas.addEventListener('touchstart', (event) => {
            if (event.touches.length === 0) {
                return;
            }
            const touch = event.touches[0];
            this.handlePointerMove(touch.clientX, touch.clientY, true);
        }, { passive: true });

        this.canvas.addEventListener('touchmove', (event) => {
            if (event.touches.length === 0) {
                return;
            }
            const touch = event.touches[0];
            this.handlePointerMove(touch.clientX, touch.clientY, true);
        }, { passive: true });

        this.canvas.addEventListener('touchend', () => {
            this.clearHover();
        }, { passive: true });
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
        this.drawHoveredPoint(ctx, padding, plotWidth, plotHeight);
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

        ctx.fillStyle = 'rgba(148, 163, 184, 0.9)';
        this.historyPoints.forEach((point) => {
            const x = this.dataToPixelX(point.x, padding.left, plotWidth);
            const y = this.dataToPixelY(point.y, padding.top, plotHeight);
            ctx.beginPath();
            ctx.arc(x, y, 2.2, 0, Math.PI * 2);
            ctx.fill();
        });
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

    private drawHoveredPoint(
        ctx: CanvasRenderingContext2D,
        padding: { top: number; right: number; bottom: number; left: number },
        plotWidth: number,
        plotHeight: number
    ): void {
        if (!this.hoveredPoint) {
            return;
        }

        const x = this.dataToPixelX(this.hoveredPoint.x, padding.left, plotWidth);
        const y = this.dataToPixelY(this.hoveredPoint.y, padding.top, plotHeight);
        ctx.beginPath();
        ctx.arc(x, y, this.hoveredPoint.source === 'current' ? 11 : 8, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(17, 24, 39, 0.45)';
        ctx.lineWidth = 2;
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

    private createTooltip(): HTMLDivElement {
        const tooltip = document.createElement('div');
        tooltip.className = 'parameter-relationship-tooltip';
        tooltip.style.position = 'absolute';
        tooltip.style.pointerEvents = 'none';
        tooltip.style.display = 'none';
        tooltip.style.background = 'rgba(17, 24, 39, 0.92)';
        tooltip.style.color = '#fff';
        tooltip.style.fontSize = '12px';
        tooltip.style.lineHeight = '1.4';
        tooltip.style.padding = '6px 8px';
        tooltip.style.borderRadius = '6px';
        tooltip.style.whiteSpace = 'nowrap';
        tooltip.style.zIndex = '2';
        if (this.container.style.position === '') {
            this.container.style.position = 'relative';
        }
        return tooltip;
    }

    private handlePointerMove(clientX: number, clientY: number, isTouch: boolean): void {
        const rect = this.canvas.getBoundingClientRect();
        const px = clientX - rect.left;
        const py = clientY - rect.top;
        const nearest = this.findNearestHistoryPoint(px, py);
        const current = this.currentPoint;
        let hover: { x: number; y: number; source: 'current' | 'history' } | null = null;

        if (nearest && nearest.distance <= 10) {
            hover = { x: nearest.point.x, y: nearest.point.y, source: 'history' };
        }

        if (current) {
            const currentX = this.dataToPixelX(current.x, ParameterRelationshipChart.PADDING.left, this.canvas.width - ParameterRelationshipChart.PADDING.left - ParameterRelationshipChart.PADDING.right);
            const currentY = this.dataToPixelY(current.y, ParameterRelationshipChart.PADDING.top, this.canvas.height - ParameterRelationshipChart.PADDING.top - ParameterRelationshipChart.PADDING.bottom);
            const dist = Math.hypot(px - currentX, py - currentY);
            if (dist <= 12 || !hover) {
                hover = { x: current.x, y: current.y, source: 'current' };
            }
        }

        if (!hover && !isTouch) {
            const dataPoint = this.pixelToData(px, py);
            hover = { x: dataPoint.x, y: dataPoint.y, source: 'current' };
        }

        if (!hover) {
            this.clearHover();
            return;
        }

        this.hoveredPoint = hover;
        this.tooltipEl.innerHTML = this.formatTooltip(hover.x, hover.y, hover.source);
        this.tooltipEl.style.display = 'block';
        this.positionTooltip(px, py);
        this.render();
    }

    private clearHover(): void {
        if (!this.hoveredPoint && this.tooltipEl.style.display === 'none') {
            return;
        }
        this.hoveredPoint = null;
        this.tooltipEl.style.display = 'none';
        this.render();
    }

    private findNearestHistoryPoint(px: number, py: number): { point: { x: number; y: number }; distance: number } | null {
        if (this.historyPoints.length === 0) {
            return null;
        }

        const plotWidth = this.canvas.width - ParameterRelationshipChart.PADDING.left - ParameterRelationshipChart.PADDING.right;
        const plotHeight = this.canvas.height - ParameterRelationshipChart.PADDING.top - ParameterRelationshipChart.PADDING.bottom;

        let nearest: { point: { x: number; y: number }; distance: number } | null = null;
        this.historyPoints.forEach((point) => {
            const hx = this.dataToPixelX(point.x, ParameterRelationshipChart.PADDING.left, plotWidth);
            const hy = this.dataToPixelY(point.y, ParameterRelationshipChart.PADDING.top, plotHeight);
            const distance = Math.hypot(px - hx, py - hy);
            if (!nearest || distance < nearest.distance) {
                nearest = { point, distance };
            }
        });

        return nearest;
    }

    private formatTooltip(x: number, y: number, source: 'current' | 'history'): string {
        const status = this.getRegionStatus(x, y);
        const statusLabel = status === 'valid' ? '有效' : status === 'warning' ? '警告' : '无效';
        const prefix = source === 'history' ? '历史轨迹点' : '当前点';
        return `${prefix}<br/>X: ${x.toFixed(3)}<br/>Y: ${y.toFixed(3)}<br/>状态: ${statusLabel}`;
    }

    private getRegionStatus(x: number, y: number): RelationshipRegionType {
        if (this.config.statusResolver) {
            return this.config.statusResolver(x, y);
        }
        if (!this.config.constraint) {
            return 'valid';
        }
        return this.config.constraint.validate(x, y) ? 'valid' : 'invalid';
    }

    private positionTooltip(px: number, py: number): void {
        const offset = 12;
        const tooltipRect = this.tooltipEl.getBoundingClientRect();
        const maxLeft = this.canvas.width - tooltipRect.width - 4;
        const maxTop = this.canvas.height - tooltipRect.height - 4;
        const left = this.clamp(px + offset, 4, Math.max(4, maxLeft));
        const top = this.clamp(py + offset, 4, Math.max(4, maxTop));
        this.tooltipEl.style.left = `${left}px`;
        this.tooltipEl.style.top = `${top}px`;
    }
}
