/**
 * 自由采样组件
 * 允许任意添加采样点，不进行空间约束检测
 */

import { CoordinateInput } from './CoordinateInput';
import { ErrorHandler } from '../utils/ErrorHandler';
import type {
    PointAddedCallback,
    Coordinate,
    SamplingPointValue,
    CoordinateMode
} from '../../types/sampling';

/**
 * 自由采样组件
 * 允许任意添加采样点，不进行空间约束检测
 */
export class FreeSampling {
    /** 地图视图 */
    view: any;

    /** 点添加回调 */
    onPointAdded: PointAddedCallback | null;

    /** 坐标输入组件 */
    coordinateInput: CoordinateInput | null;

    /** 坐标获取方式 */
    coordinateMode: CoordinateMode;

    /**
     * @param view - MapView（支持 ArcGIS 和高德地图）
     * @param onPointAdded - 点添加回调
     */
    constructor(view: any, onPointAdded?: PointAddedCallback) {
        this.view = view;
        this.onPointAdded = onPointAdded || null;
        this.coordinateInput = null;
        this.coordinateMode = 'manual';
    }

    /**
     * 创建采样面板
     * @param coordinateMode - 坐标获取方式
     * @returns HTMLElement
     */
    createPanel(coordinateMode: CoordinateMode = 'manual'): HTMLElement {
        this.coordinateMode = coordinateMode;

        const container = document.createElement('div');
        container.className = 'free-sampling-panel';

        container.innerHTML = `
            <div class="panel-header">
                <h3 class="section-title">自由采样</h3>
                <p class="section-description">可在任意位置添加采样点</p>
            </div>
        `;

        // 创建坐标输入组件
        this.coordinateInput = new CoordinateInput(
            coordinateMode,
            (position) => this.handleCoordinateChange(position)
        );

        const inputPanel = this.coordinateInput.createPanel();
        container.appendChild(inputPanel);

        // 添加按钮
        const buttonGroup = document.createElement('div');
        buttonGroup.className = 'button-group';
        buttonGroup.style.cssText = 'display: flex; gap: 12px; margin-top: 16px;';

        buttonGroup.innerHTML = `
            <button id="add-point-btn" class="btn btn-primary" style="flex: 1;">添加采样点</button>
            <button id="clear-input-btn" class="btn btn-secondary" style="flex: 1;">清空输入</button>
        `;

        container.appendChild(buttonGroup);

        // 状态消息
        const statusDiv = document.createElement('div');
        statusDiv.id = 'free-sampling-status';
        statusDiv.className = 'status-message';
        statusDiv.style.display = 'none';
        container.appendChild(statusDiv);

        // 绑定事件
        this.bindEvents(container);

        return container;
    }

    /**
     * 绑定事件
     * @param container
     */
    protected bindEvents(container: HTMLElement): void {
        const addBtn = container.querySelector('#add-point-btn') as HTMLButtonElement;
        const clearBtn = container.querySelector('#clear-input-btn') as HTMLButtonElement;

        addBtn.addEventListener('click', () => this.addPoint());
        clearBtn.addEventListener('click', () => this.clearInput());
    }

    /**
     * 处理坐标变化
     * @param position
     */
    protected handleCoordinateChange(position: Coordinate): void {
        console.log('坐标已更新:', position);
    }

    /**
     * 添加采样点
     */
    async addPoint(): Promise<void> {
        if (!this.coordinateInput) {
            return;
        }

        const pointData = this.coordinateInput.getValue();

        if (!pointData) {
            return;
        }

        try {
            // 触发回调
            if (this.onPointAdded) {
                await this.onPointAdded(pointData);
            }

            ErrorHandler.showSuccess(
                `采样点已添加 (${pointData.longitude.toFixed(6)}, ${pointData.latitude.toFixed(6)})`
            );

            // 清空输入
            this.clearInput();

        } catch (error) {
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.VALIDATION_ERROR,
                (error as Error).message
            );
        }
    }

    /**
     * 清空输入
     */
    clearInput(): void {
        if (this.coordinateInput) {
            this.coordinateInput.clear();
        }
    }

    /**
     * 销毁组件
     */
    destroy(): void {
        if (this.coordinateInput) {
            this.coordinateInput.destroy();
        }
    }
}