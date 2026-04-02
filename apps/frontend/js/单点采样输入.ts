/**
 * 单点采样输入组件
 * 支持多种坐标格式输入和自动转换
 */

import { ExtendedSamplingPoint, PointAddCallback, MapView } from '../types/app';

/** 坐标格式类型 */
type CoordinateFormat = 'dms' | 'decimal' | 'projected' | 'unknown';

/** 坐标轴类型 */
type CoordinateAxis = 'x' | 'y';

/** 点数据接口 */
interface PointData {
    x: number;
    y: number;
}

export class SinglePointSampling {
    private view: MapView;
    private onPointAdded: PointAddCallback;
    private container: HTMLElement | null = null;

    constructor(view: MapView, onPointAdded: PointAddCallback) {
        this.view = view;
        this.onPointAdded = onPointAdded;
    }

    /**
     * 创建单点采样面板
     */
    createPanel(): HTMLElement {
        const panel = document.createElement('div');
        panel.className = 'panel single-point-panel';
        panel.innerHTML = `
            <h2 class="panel-title">单点采样输入</h2>
            <div class="panel-content">
                <div class="form-group">
                    <label>X 坐标</label>
                    <input type="text" id="point-x" class="input" placeholder="经度或投影X">
                    <span class="error-message" id="error-x"></span>
                </div>
                <div class="form-group">
                    <label>Y 坐标</label>
                    <input type="text" id="point-y" class="input" placeholder="纬度或投影Y">
                    <span class="error-message" id="error-y"></span>
                </div>
                <div class="form-group">
                    <label>Point_Data</label>
                    <input type="text" id="point-data" class="input" placeholder="数值">
                    <span class="error-message" id="error-data"></span>
                </div>
                <button id="add-point-btn" class="btn btn-primary">添加采样点</button>
            </div>
        `;

        this.container = panel;
        this.bindEvents();

        return panel;
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        const addBtn = this.container?.querySelector('#add-point-btn') as HTMLButtonElement;
        if (addBtn) {
            addBtn.addEventListener('click', () => this.handleAddPoint());
        }

        // 清除错误提示
        ['point-x', 'point-y', 'point-data'].forEach((id) => {
            const input = this.container?.querySelector(`#${id}`) as HTMLInputElement;
            if (input) {
                input.addEventListener('input', () => {
                    this.clearError(id);
                });
            }
        });
    }

    /**
     * 处理添加点
     */
    private async handleAddPoint(): Promise<void> {
        const xInput = this.container?.querySelector('#point-x') as HTMLInputElement;
        const yInput = this.container?.querySelector('#point-y') as HTMLInputElement;
        const dataInput = this.container?.querySelector('#point-data') as HTMLInputElement;

        if (!xInput || !yInput || !dataInput) return;

        const xValue = xInput.value.trim();
        const yValue = yInput.value.trim();
        const dataValue = dataInput.value.trim();

        // 验证输入
        let hasError = false;

        if (!xValue) {
            this.showError('point-x', '请输入X坐标');
            hasError = true;
        }

        if (!yValue) {
            this.showError('point-y', '请输入Y坐标');
            hasError = true;
        }

        if (!dataValue) {
            this.showError('point-data', '请输入数值');
            hasError = true;
        } else if (isNaN(parseFloat(dataValue))) {
            this.showError('point-data', '必须为数值类型');
            hasError = true;
        }

        if (hasError) return;

        try {
            // 解析坐标
            const x = await this.parseCoordinate(xValue, 'x');
            const y = await this.parseCoordinate(yValue, 'y');
            const value = parseFloat(dataValue);

            // 创建点
            const point = await this.createPoint(x, y);

            // 回调
            if (this.onPointAdded) {
                await this.onPointAdded({ x: point.x, y: point.y, value, timestamp: new Date().toISOString() });
            }

            // 清空输入
            xInput.value = '';
            yInput.value = '';
            dataInput.value = '';
        } catch (error) {
            console.error('添加点失败:', error);
            const errorMessage = error instanceof Error ? error.message : '未知错误';
            this.showError('point-x', errorMessage);
        }
    }

    /**
     * 解析坐标
     */
    private async parseCoordinate(value: string, axis: CoordinateAxis): Promise<number> {
        // 检测格式
        const format = this.detectFormat(value);

        switch (format) {
            case 'dms':
                return this.parseDMS(value);
            case 'decimal':
                return parseFloat(value);
            case 'projected':
                return parseFloat(value);
            default:
                throw new Error('坐标格式无法识别');
        }
    }

    /**
     * 检测坐标格式
     */
    private detectFormat(value: string): CoordinateFormat {
        // DMS 格式
        if (value.includes('°') || value.includes("'") || value.includes('"')) {
            return 'dms';
        }

        const num = parseFloat(value);

        if (isNaN(num)) {
            return 'unknown';
        }

        // 经纬度范围
        if (num >= -180 && num <= 180 && Math.abs(num) < 1000) {
            return 'decimal';
        }

        // 投影坐标
        if (Math.abs(num) >= 1000) {
            return 'projected';
        }

        return 'unknown';
    }

    /**
     * 解析 DMS 格式
     */
    private parseDMS(dms: string): number {
        try {
            // 移除方向字母
            let value = dms.replace(/[NSEW]/gi, '').trim();

            // 解析度分秒
            const parts = value.split(/[°'"]/);
            const degrees = parseFloat(parts[0] || '0');
            const minutes = parseFloat(parts[1] || '0');
            const seconds = parseFloat(parts[2] || '0');

            let decimal = degrees + minutes / 60 + seconds / 3600;

            // 处理南纬和西经
            if (dms.match(/[SW]/i)) {
                decimal = -decimal;
            }

            return decimal;
        } catch (error) {
            throw new Error('DMS 格式错误');
        }
    }

    /**
     * 创建点对象
     */
    private async createPoint(x: number, y: number): Promise<PointData> {
        // 动态导入 GeoScene Point 类
        // @ts-ignore
        const Point = (await import('@geoscene/core/geometry/Point')).default;
        // @ts-ignore
        const projection = await import('@geoscene/core/geometry/projection');

        // 检测是否需要转换
        const xFormat = this.detectFormat(String(x));
        const yFormat = this.detectFormat(String(y));

        if (xFormat === 'decimal' || yFormat === 'decimal') {
            // 经纬度，需要转换
            await projection.load();

            const wgs84Point = new Point({
                x: x,
                y: y,
                spatialReference: { wkid: 4326 }
            });

            const projectedPoint = projection.project(wgs84Point, this.view.spatialReference);
            if (!projectedPoint) {
                throw new Error('坐标转换失败');
            }
            // @ts-ignore - projection.project 返回的几何对象包含 x 和 y 属性
            return { x: projectedPoint.x, y: projectedPoint.y };
        } else {
            // 投影坐标，直接使用
            return new Point({
                x: x,
                y: y,
                spatialReference: this.view.spatialReference
            });
        }
    }

    /**
     * 显示错误
     */
    private showError(inputId: string, message: string): void {
        const input = this.container?.querySelector(`#${inputId}`) as HTMLInputElement;
        const errorSpan = this.container?.querySelector(`#error-${inputId.split('-')[1]}`) as HTMLSpanElement;

        if (input && errorSpan) {
            input.style.borderColor = '#ff453a';
            input.style.transition = 'border-color 200ms';
            errorSpan.textContent = message;
            errorSpan.style.display = 'block';
        }
    }

    /**
     * 清除错误
     */
    private clearError(inputId: string): void {
        const input = this.container?.querySelector(`#${inputId}`) as HTMLInputElement;
        const errorSpan = this.container?.querySelector(`#error-${inputId.split('-')[1]}`) as HTMLSpanElement;

        if (input && errorSpan) {
            input.style.borderColor = '';
            errorSpan.textContent = '';
            errorSpan.style.display = 'none';
        }
    }
}
