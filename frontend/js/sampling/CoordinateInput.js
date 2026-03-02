/**
 * 坐标输入组件
 * 支持手动输入和自动获取设备坐标
 */
import { ErrorHandler } from '../utils/ErrorHandler.js';

export class CoordinateInput {
    /**
     * @param {string} mode - 坐标获取方式: 'manual' | 'device'
     * @param {Function} onCoordinateChange - 坐标变化回调
     */
    constructor(mode, onCoordinateChange) {
        this.mode = mode;
        this.onCoordinateChange = onCoordinateChange;
        this.currentPosition = null;
        this.watchId = null;
    }

    /**
     * 创建输入面板
     * @returns {HTMLElement}
     */
    createPanel() {
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
     * @returns {HTMLElement}
     */
    createManualInput() {
        const panel = document.createElement('div');
        panel.className = 'manual-input-panel';

        panel.innerHTML = `
            <div class="form-group">
                <label>经度 (Longitude)</label>
                <input type="number"
                       id="input-longitude"
                       class="input"
                       placeholder="例如: 116.4074"
                       step="0.000001"
                       min="-180"
                       max="180">
                <div class="error-message" id="longitude-error"></div>
            </div>
            <div class="form-group">
                <label>纬度 (Latitude)</label>
                <input type="number"
                       id="input-latitude"
                       class="input"
                       placeholder="例如: 39.9042"
                       step="0.000001"
                       min="-90"
                       max="90">
                <div class="error-message" id="latitude-error"></div>
            </div>
            <div class="form-group">
                <label>采样值</label>
                <input type="number"
                       id="input-value"
                       class="input"
                       placeholder="输入采样值"
                       step="0.01">
                <div class="error-message" id="value-error"></div>
            </div>
        `;

        // 绑定实时验证
        const longitudeInput = panel.querySelector('#input-longitude');
        const latitudeInput = panel.querySelector('#input-latitude');

        longitudeInput.addEventListener('input', () => {
            this.validateLongitude(longitudeInput.value);
        });

        latitudeInput.addEventListener('input', () => {
            this.validateLatitude(latitudeInput.value);
        });

        return panel;
    }

    /**
     * 创建设备定位界面
     * @returns {HTMLElement}
     */
    createDeviceInput() {
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
        const getLocationBtn = panel.querySelector('#get-location-btn');
        getLocationBtn.addEventListener('click', () => {
            this.getCurrentPosition();
        });

        return panel;
    }

    /**
     * 获取当前位置
     */
    getCurrentPosition() {
        if (!navigator.geolocation) {
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.GEOLOCATION_FAILED,
                '您的浏览器不支持地理定位'
            );
            return;
        }

        const statusText = document.getElementById('location-text');
        const statusIcon = document.getElementById('location-status');

        statusText.textContent = '正在获取位置...';
        statusIcon.innerHTML = '<span>⏳</span>';

        navigator.geolocation.getCurrentPosition(
            (position) => this.handlePositionSuccess(position),
            (error) => this.handlePositionError(error),
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    }

    /**
     * 处理定位成功
     * @param {GeolocationPosition} position
     */
    handlePositionSuccess(position) {
        const { longitude, latitude } = position.coords;

        // 强制校验坐标系为 WGS-84
        if (position.coords.accuracy > 100) {
            ErrorHandler.showWarning('定位精度较低，建议重新获取');
        }

        this.currentPosition = {
            longitude,
            latitude,
            accuracy: position.coords.accuracy,
            timestamp: new Date(position.timestamp).toISOString()
        };

        // 更新界面
        const statusText = document.getElementById('location-text');
        const statusIcon = document.getElementById('location-status');
        const coordinateDisplay = document.getElementById('coordinate-display');

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
     * 处理定位失败
     * @param {GeolocationPositionError} error
     */
    handlePositionError(error) {
        const statusText = document.getElementById('location-text');
        const statusIcon = document.getElementById('location-status');

        statusText.textContent = '位置获取失败';
        statusIcon.innerHTML = '<span>❌</span>';

        ErrorHandler.handleGeolocationError(error);
    }

    /**
     * 验证经度
     * @param {string} value
     * @returns {boolean}
     */
    validateLongitude(value) {
        const longitude = parseFloat(value);
        const errorDiv = document.getElementById('longitude-error');

        const validation = ErrorHandler.validateCoordinates(longitude, 0);

        if (!validation.valid) {
            errorDiv.textContent = validation.error;
            errorDiv.style.display = 'block';
            return false;
        }

        errorDiv.style.display = 'none';
        return true;
    }

    /**
     * 验证纬度
     * @param {string} value
     * @returns {boolean}
     */
    validateLatitude(value) {
        const latitude = parseFloat(value);
        const errorDiv = document.getElementById('latitude-error');

        const validation = ErrorHandler.validateCoordinates(0, latitude);

        if (!validation.valid) {
            errorDiv.textContent = validation.error;
            errorDiv.style.display = 'block';
            return false;
        }

        errorDiv.style.display = 'none';
        return true;
    }

    /**
     * 获取当前坐标和值
     * @returns {Object|null}
     */
    getValue() {
        if (this.mode === 'manual') {
            const longitude = parseFloat(document.getElementById('input-longitude').value);
            const latitude = parseFloat(document.getElementById('input-latitude').value);
            const value = parseFloat(document.getElementById('input-value').value);

            const validation = ErrorHandler.validateCoordinates(longitude, latitude);
            if (!validation.valid) {
                ErrorHandler.showError(ErrorHandler.ErrorTypes.COORDINATE_FORMAT, validation.error);
                return null;
            }

            if (isNaN(value)) {
                ErrorHandler.showError(ErrorHandler.ErrorTypes.VALIDATION_ERROR, '请输入有效的采样值');
                return null;
            }

            return { longitude, latitude, value };

        } else if (this.mode === 'device') {
            if (!this.currentPosition) {
                ErrorHandler.showError(ErrorHandler.ErrorTypes.VALIDATION_ERROR, '请先获取位置');
                return null;
            }

            const value = parseFloat(document.getElementById('device-input-value').value);
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
    clear() {
        if (this.mode === 'manual') {
            document.getElementById('input-longitude').value = '';
            document.getElementById('input-latitude').value = '';
            document.getElementById('input-value').value = '';
        } else if (this.mode === 'device') {
            document.getElementById('device-input-value').value = '';
            this.currentPosition = null;

            const statusText = document.getElementById('location-text');
            const statusIcon = document.getElementById('location-status');
            const coordinateDisplay = document.getElementById('coordinate-display');

            statusText.textContent = '准备获取位置';
            statusIcon.innerHTML = '<span>📍</span>';
            coordinateDisplay.style.display = 'none';
        }
    }

    /**
     * 销毁组件
     */
    destroy() {
        if (this.watchId !== null) {
            navigator.geolocation.clearWatch(this.watchId);
        }
    }
}
