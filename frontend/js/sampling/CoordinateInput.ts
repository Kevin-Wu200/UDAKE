/**
 * 坐标输入组件
 * 支持手动输入和自动获取设备坐标
 */

import { ErrorHandler } from '../utils/ErrorHandler';
import { CoordinateParser } from '../utils/CoordinateParser';
import { LocationPermissionManager } from '../utils/locationPermissionManager';
import type {
    CoordinateMode,
    Coordinate,
    CoordinateChangeCallback,
    CoordinateInputState,
    SamplingPointValue
} from '../../types/sampling';

/**
 * 坐标输入组件
 * 支持手动输入和自动获取设备坐标
 */
export class CoordinateInput {
    /** 坐标获取方式 */
    mode: CoordinateMode;

    /** 坐标变化回调 */
    onCoordinateChange: CoordinateChangeCallback | null;

    /** 当前位置 */
    currentPosition: Coordinate | null;

    /** 监听 ID（已废弃，保留兼容） */
    watchId: number | null;

    /** 状态 */
    state: CoordinateInputState;

    /**
     * @param mode - 坐标获取方式: 'manual' | 'device'
     * @param onCoordinateChange - 坐标变化回调
     */
    constructor(mode: CoordinateMode, onCoordinateChange?: CoordinateChangeCallback) {
        this.mode = mode;
        this.onCoordinateChange = onCoordinateChange || null;
        this.currentPosition = null;
        this.watchId = null;

        // 状态管理：保存原始输入和解析后的值
        this.state = {
            longitude_raw: '',
            longitude: null,
            latitude_raw: '',
            latitude: null,
            sampleValue_raw: '',
            sampleValue: null
        };
    }

    /**
     * 创建输入面板
     * @returns HTMLElement
     */
    createPanel(): HTMLElement {
        const container = document.createElement('div');
        container.className = 'coordinate-input-panel';

        if (this.mode === 'manual') {
            container.appendChild(this.createManualInput());
        } else if (this.mode === 'device') {
            container.appendChild(this.createDeviceInput());
        }

        return container;
    }

    /**
     * 创建手动输入界面
     * @returns HTMLElement
     */
    protected createManualInput(): HTMLElement {
        const panel = document.createElement('div');
        panel.className = 'manual-input-panel';

        panel.innerHTML = `
            <div class="form-group">
                <label>经度 (Longitude)</label>
                <input type="text"
                       id="input-longitude"
                       class="input coordinate-input"
                       placeholder="例如: 116.4074 或 116°24.444' 或 116°24'26\";"
                       autocomplete="off"
                       spellcheck="false">
                <div class="error-message" id="longitude-error"></div>
            </div>
            <div class="form-group">
                <label>纬度 (Latitude)</label>
                <input type="text"
                       id="input-latitude"
                       class="input coordinate-input"
                       placeholder="例如: 39.9042 或 39°54'15\";"
                       autocomplete="off"
                       spellcheck="false">
                <div class="error-message" id="latitude-error"></div>
            </div>
            <div class="form-group">
                <label>采样值</label>
                <input type="text"
                       id="input-value"
                       class="input coordinate-input"
                       placeholder="输入采样值"
                       autocomplete="off"
                       spellcheck="false">
                <div class="error-message" id="value-error"></div>
            </div>
        `;

        // 绑定实时验证
        const longitudeInput = panel.querySelector('#input-longitude') as HTMLInputElement;
        const latitudeInput = panel.querySelector('#input-latitude') as HTMLInputElement;
        const valueInput = panel.querySelector('#input-value') as HTMLInputElement;

        // 禁止滚轮改变值
        [longitudeInput, latitudeInput, valueInput].forEach(input => {
            input.addEventListener('wheel', e => e.preventDefault());
        });

        // 禁止方向键改变值
        [longitudeInput, latitudeInput, valueInput].forEach(input => {
            input.addEventListener('keydown', e => {
                if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown'].includes(e.key)) {
                    e.preventDefault();
                }
            });
        });

        longitudeInput.addEventListener('input', (e) => {
            this.validateCoordinate((e.target as HTMLInputElement).value, 'longitude');
        });

        latitudeInput.addEventListener('input', (e) => {
            this.validateCoordinate((e.target as HTMLInputElement).value, 'latitude');
        });

        valueInput.addEventListener('input', (e) => {
            this.validateSampleValue((e.target as HTMLInputElement).value);
        });

        return panel;
    }

    /**
     * 创建设备定位界面
     * @returns HTMLElement
     */
    protected createDeviceInput(): HTMLElement {
        const panel = document.createElement('div');
        panel.className = 'device-input-panel';

        panel.innerHTML = `
            <div class="device-status">
                <div class="status-icon" id="location-status">
                    <span>📍</span>
                </div>
                <div class="status-text">
                    <p id="location-text">准备获取位置</p>
                    <p id="coordinate-display" class="coordinate-display"></p>
                </div>
            </div>
            <button id="get-location-btn" class="btn btn-primary">获取当前位置</button>
            <div class="form-group" style="margin-top: 16px;">
                <label>采样值</label>
                <input type="number"
                       id="device-input-value"
                       class="input"
                       placeholder="输入采样值"
                       step="0.01">
            </div>
            <div id="device-status-message"></div>
        `;

        // 绑定获取位置按钮
        const getLocationBtn = panel.querySelector('#get-location-btn') as HTMLButtonElement;
        getLocationBtn.addEventListener('click', () => {
            this.getCurrentPosition();
        });

        return panel;
    }

    /**
     * 获取当前位置
     */
    getCurrentPosition(): void {
        // 检查权限状态
        const permissionStatus = LocationPermissionManager.getPermissionStatus();

        if (permissionStatus === LocationPermissionManager.PermissionStatus.DENIED) {
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.PERMISSION_DENIED,
                '定位权限未授权，无法使用当前位置采样功能，请在系统设置中开启定位权限。'
            );
            return;
        }

        const statusText = document.getElementById('location-text') as HTMLParagraphElement;
        const statusIcon = document.getElementById('location-status') as HTMLDivElement;

        statusText.textContent = '正在获取位置...';
        statusIcon.innerHTML = '<span>⏳</span>';

        // 若权限为 unknown，再次尝试请求权限后获取位置
        if (permissionStatus === LocationPermissionManager.PermissionStatus.UNKNOWN) {
            LocationPermissionManager.requestPermission().then(status => {
                if (status === LocationPermissionManager.PermissionStatus.DENIED) {
                    statusText.textContent = '位置获取失败';
                    statusIcon.innerHTML = '<span>❌</span>';
                    ErrorHandler.showError(
                        ErrorHandler.ErrorTypes.PERMISSION_DENIED,
                        '定位权限未授权，无法使用当前位置采样功能，请在系统设置中开启定位权限。'
                    );
                    return;
                }
                this._doGetPosition();
            });
            return;
        }

        this._doGetPosition();
    }

    /**
     * 执行定位获取（内部方法）
     */
    protected _doGetPosition(): void {
        LocationPermissionManager.getCurrentPosition()
            .then(position => this.handlePositionSuccess(position))
            .catch(error => this._handlePermissionError(error));
    }

    /**
     * 处理权限管理模块返回的错误
     */
    protected _handlePermissionError(error: any): void {
        const statusText = document.getElementById('location-text') as HTMLParagraphElement;
        const statusIcon = document.getElementById('location-status') as HTMLDivElement;

        statusText.textContent = '位置获取失败';
        statusIcon.innerHTML = '<span>❌</span>';

        if (error.type === 'denied') {
            ErrorHandler.showError(ErrorHandler.ErrorTypes.PERMISSION_DENIED, error.message);
        } else if (error.type === 'timeout') {
            ErrorHandler.showError(ErrorHandler.ErrorTypes.GEOLOCATION_FAILED, error.message);
        } else if (error.type === 'unsupported') {
            ErrorHandler.showError(ErrorHandler.ErrorTypes.GEOLOCATION_FAILED, error.message);
        } else {
            ErrorHandler.showError(ErrorHandler.ErrorTypes.GEOLOCATION_FAILED, error.message);
        }
    }

    /**
     * 处理定位成功
     * @param position
     */
    protected handlePositionSuccess(position: Coordinate & { accuracy: number }): void {
        const { longitude, latitude, accuracy } = position;

        // 精度校验
        if (accuracy > 100) {
            ErrorHandler.showWarning('定位精度较低，建议重新获取');
        }

        this.currentPosition = {
            longitude,
            latitude,
            accuracy,
            timestamp: position.timestamp
        };

        // 更新界面
        const statusText = document.getElementById('location-text') as HTMLParagraphElement;
        const statusIcon = document.getElementById('location-status') as HTMLDivElement;
        const coordinateDisplay = document.getElementById('coordinate-display') as HTMLParagraphElement;

        statusText.textContent = '位置获取成功';
        statusIcon.innerHTML = '<span>✅</span>';
        coordinateDisplay.textContent = `经度: ${longitude.toFixed(6)}, 纬度: ${latitude.toFixed(6)}`;
        coordinateDisplay.style.display = 'block';

        // 触发回调
        if (this.onCoordinateChange) {
            this.onCoordinateChange(this.currentPosition);
        }

        ErrorHandler.showSuccess('位置获取成功');
    }

    /**
     * 验证坐标（使用 CoordinateParser）
     * @param value
     * @param type - 'longitude' | 'latitude'
     * @returns boolean
     */
    validateCoordinate(value: string, type: 'longitude' | 'latitude'): boolean {
        const result = CoordinateParser.parseCoordinate(value, type);
        const errorDiv = document.getElementById(`${type === 'longitude' ? 'longitude' : 'latitude'}-error`) as HTMLDivElement;
        const input = document.getElementById(`input-${type === 'longitude' ? 'longitude' : 'latitude'}`) as HTMLInputElement;

        if (!result.valid) {
            input.classList.add('invalid');
            errorDiv.textContent = result.error || '';
            errorDiv.style.display = 'block';

            // 更新状态
            if (type === 'longitude') {
                this.state.longitude_raw = value;
                this.state.longitude = null;
            } else {
                this.state.latitude_raw = value;
                this.state.latitude = null;
            }

            return false;
        }

        input.classList.remove('invalid');
        errorDiv.style.display = 'none';

        // 更新状态：保存解析后的十进制度数
        if (type === 'longitude') {
            this.state.longitude_raw = value;
            this.state.longitude = result.value || null;
        } else {
            this.state.latitude_raw = value;
            this.state.latitude = result.value || null;
        }

        return true;
    }

    /**
     * 验证采样值
     * @param value
     * @returns boolean
     */
    validateSampleValue(value: string): boolean {
        const result = CoordinateParser.parseSampleValue(value);
        const errorDiv = document.getElementById('value-error') as HTMLDivElement;
        const input = document.getElementById('input-value') as HTMLInputElement;

        if (!result.valid) {
            input.classList.add('invalid');
            errorDiv.textContent = result.error || '';
            errorDiv.style.display = 'block';

            this.state.sampleValue_raw = value;
            this.state.sampleValue = null;

            return false;
        }

        input.classList.remove('invalid');
        errorDiv.style.display = 'none';

        this.state.sampleValue_raw = value;
        this.state.sampleValue = result.value || null;

        return true;
    }

    /**
     * 验证经度（已废弃，使用 validateCoordinate）
     * @param value
     * @returns boolean
     */
    validateLongitude(value: string): boolean {
        return this.validateCoordinate(value, 'longitude');
    }

    /**
     * 验证纬度（已废弃，使用 validateCoordinate）
     * @param value
     * @returns boolean
     */
    validateLatitude(value: string): boolean {
        return this.validateCoordinate(value, 'latitude');
    }

    /**
     * 获取当前坐标和值
     * @returns Object | null
     */
    getValue(): SamplingPointValue | null {
        if (this.mode === 'manual') {
            // 验证所有字段
            const longitudeInput = document.getElementById('input-longitude') as HTMLInputElement;
            const latitudeInput = document.getElementById('input-latitude') as HTMLInputElement;
            const valueInput = document.getElementById('input-value') as HTMLInputElement;

            const longitudeValid = this.validateCoordinate(longitudeInput.value, 'longitude');
            const latitudeValid = this.validateCoordinate(latitudeInput.value, 'latitude');
            const valueValid = this.validateSampleValue(valueInput.value);

            // 如果任一字段无效，阻止提交
            if (!longitudeValid || !latitudeValid || !valueValid) {
                ErrorHandler.showError(
                    ErrorHandler.ErrorTypes.VALIDATION_ERROR,
                    '请输入合法的经纬度和采样值'
                );
                return null;
            }

            // 使用状态中保存的十进制度数
            return {
                longitude: this.state.longitude!,
                latitude: this.state.latitude!,
                value: this.state.sampleValue!
            };

        } else if (this.mode === 'device') {
            if (!this.currentPosition) {
                ErrorHandler.showError(ErrorHandler.ErrorTypes.VALIDATION_ERROR, '请先获取位置');
                return null;
            }

            const valueInput = document.getElementById('device-input-value') as HTMLInputElement;
            const value = parseFloat(valueInput.value);
            if (isNaN(value)) {
                ErrorHandler.showError(ErrorHandler.ErrorTypes.VALIDATION_ERROR, '请输入有效的采样值');
                return null;
            }

            return {
                longitude: this.currentPosition.longitude,
                latitude: this.currentPosition.latitude,
                value
            };
        }

        return null;
    }

    /**
     * 清空输入
     */
    clear(): void {
        if (this.mode === 'manual') {
            const longitudeInput = document.getElementById('input-longitude') as HTMLInputElement;
            const latitudeInput = document.getElementById('input-latitude') as HTMLInputElement;
            const valueInput = document.getElementById('input-value') as HTMLInputElement;

            if (longitudeInput) longitudeInput.value = '';
            if (latitudeInput) latitudeInput.value = '';
            if (valueInput) valueInput.value = '';

            // 清空状态
            this.state = {
                longitude_raw: '',
                longitude: null,
                latitude_raw: '',
                latitude: null,
                sampleValue_raw: '',
                sampleValue: null
            };

            // 清除错误样式
            ['input-longitude', 'input-latitude', 'input-value'].forEach(id => {
                const input = document.getElementById(id) as HTMLInputElement;
                if (input) {
                    input.classList.remove('invalid');
                }
            });

            // 清除错误消息
            ['longitude-error', 'latitude-error', 'value-error'].forEach(id => {
                const errorDiv = document.getElementById(id) as HTMLDivElement;
                if (errorDiv) {
                    errorDiv.style.display = 'none';
                }
            });

        } else if (this.mode === 'device') {
            const valueInput = document.getElementById('device-input-value') as HTMLInputElement;
            if (valueInput) valueInput.value = '';

            this.currentPosition = null;

            const statusText = document.getElementById('location-text') as HTMLParagraphElement;
            const statusIcon = document.getElementById('location-status') as HTMLDivElement;
            const coordinateDisplay = document.getElementById('coordinate-display') as HTMLParagraphElement;

            if (statusText) statusText.textContent = '准备获取位置';
            if (statusIcon) statusIcon.innerHTML = '<span>📍</span>';
            if (coordinateDisplay) coordinateDisplay.style.display = 'none';
        }
    }

    /**
     * 设置坐标值
     * @param position - {longitude: number, latitude: number}
     */
    setValue(position: Coordinate): void {
        if (!position || typeof position.longitude !== 'number' || typeof position.latitude !== 'number') {
            console.error('Invalid position:', position);
            return;
        }

        if (this.mode === 'manual') {
            const longitudeInput = document.getElementById('input-longitude') as HTMLInputElement;
            const latitudeInput = document.getElementById('input-latitude') as HTMLInputElement;

            if (longitudeInput && latitudeInput) {
                // 设置输入值（使用十进制度数）
                longitudeInput.value = position.longitude.toFixed(6);
                latitudeInput.value = position.latitude.toFixed(6);

                // 更新状态
                this.state.longitude = position.longitude;
                this.state.latitude = position.latitude;
                this.state.longitude_raw = position.longitude.toFixed(6);
                this.state.latitude_raw = position.latitude.toFixed(6);

                // 清除错误样式
                longitudeInput.classList.remove('invalid');
                latitudeInput.classList.remove('invalid');

                // 清除错误消息
                const longitudeError = document.getElementById('longitude-error') as HTMLDivElement;
                const latitudeError = document.getElementById('latitude-error') as HTMLDivElement;
                if (longitudeError) longitudeError.style.display = 'none';
                if (latitudeError) latitudeError.style.display = 'none';

                // 触发回调
                if (this.onCoordinateChange) {
                    this.onCoordinateChange({
                        longitude: position.longitude,
                        latitude: position.latitude
                    });
                }
            }
        } else if (this.mode === 'device') {
            // 设备模式下，更新当前位置
            this.currentPosition = {
                longitude: position.longitude,
                latitude: position.latitude,
                accuracy: 0,
                timestamp: Date.now().toString()
            };

            const coordinateDisplay = document.getElementById('coordinate-display') as HTMLParagraphElement;
            if (coordinateDisplay) {
                coordinateDisplay.textContent = `经度: ${position.longitude.toFixed(6)}, 纬度: ${position.latitude.toFixed(6)}`;
                coordinateDisplay.style.display = 'block';
            }

            const statusText = document.getElementById('location-text') as HTMLParagraphElement;
            const statusIcon = document.getElementById('location-status') as HTMLDivElement;
            if (statusText) statusText.textContent = '位置已设置';
            if (statusIcon) statusIcon.innerHTML = '<span>✅</span>';
        }
    }

    /**
     * 销毁组件
     */
    destroy(): void {
        // watchId 已不再使用，保留接口兼容
        this.watchId = null;
    }
}
