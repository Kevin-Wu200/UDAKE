/**
 * 坐标输入组件
 * 支持手动输入和自动获取设备坐标
 */
import { ErrorHandler } from '../utils/ErrorHandler.js';
import { CoordinateParser } from '../utils/CoordinateParser.js';

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
                <input type="text"
                       id="input-longitude"
                       class="input coordinate-input"
                       placeholder="例如: 116.4074 或 116°24.444' 或 116°24'26&quot;"
                       autocomplete="off"
                       spellcheck="false">
                <div class="error-message" id="longitude-error"></div>
            </div>
            <div class="form-group">
                <label>纬度 (Latitude)</label>
                <input type="text"
                       id="input-latitude"
                       class="input coordinate-input"
                       placeholder="例如: 39.9042 或 39°54'15&quot;"
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
        const longitudeInput = panel.querySelector('#input-longitude');
        const latitudeInput = panel.querySelector('#input-latitude');
        const valueInput = panel.querySelector('#input-value');

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
            this.validateCoordinate(e.target.value, 'longitude');
        });

        latitudeInput.addEventListener('input', (e) => {
            this.validateCoordinate(e.target.value, 'latitude');
        });

        valueInput.addEventListener('input', (e) => {
            this.validateSampleValue(e.target.value);
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
     * 验证坐标（使用 CoordinateParser）
     * @param {string} value
     * @param {string} type - 'longitude' | 'latitude'
     * @returns {boolean}
     */
    validateCoordinate(value, type) {
        const result = CoordinateParser.parseCoordinate(value, type);
        const errorDiv = document.getElementById(`${type === 'longitude' ? 'longitude' : 'latitude'}-error`);
        const input = document.getElementById(`input-${type === 'longitude' ? 'longitude' : 'latitude'}`);

        if (!result.valid) {
            input.classList.add('invalid');
            errorDiv.textContent = result.error;
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
            this.state.longitude = result.value;
        } else {
            this.state.latitude_raw = value;
            this.state.latitude = result.value;
        }

        return true;
    }

    /**
     * 验证采样值
     * @param {string} value
     * @returns {boolean}
     */
    validateSampleValue(value) {
        const result = CoordinateParser.parseSampleValue(value);
        const errorDiv = document.getElementById('value-error');
        const input = document.getElementById('input-value');

        if (!result.valid) {
            input.classList.add('invalid');
            errorDiv.textContent = result.error;
            errorDiv.style.display = 'block';

            this.state.sampleValue_raw = value;
            this.state.sampleValue = null;

            return false;
        }

        input.classList.remove('invalid');
        errorDiv.style.display = 'none';

        this.state.sampleValue_raw = value;
        this.state.sampleValue = result.value;

        return true;
    }

    /**
     * 验证经度（已废弃，使用 validateCoordinate）
     * @param {string} value
     * @returns {boolean}
     */
    validateLongitude(value) {
        return this.validateCoordinate(value, 'longitude');
    }

    /**
     * 验证纬度（已废弃，使用 validateCoordinate）
     * @param {string} value
     * @returns {boolean}
     */
    validateLatitude(value) {
        return this.validateCoordinate(value, 'latitude');
    }

    /**
     * 获取当前坐标和值
     * @returns {Object|null}
     */
    getValue() {
        if (this.mode === 'manual') {
            // 验证所有字段
            const longitudeInput = document.getElementById('input-longitude');
            const latitudeInput = document.getElementById('input-latitude');
            const valueInput = document.getElementById('input-value');

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
                longitude: this.state.longitude,
                latitude: this.state.latitude,
                value: this.state.sampleValue
            };

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
                const input = document.getElementById(id);
                if (input) {
                    input.classList.remove('invalid');
                }
            });

            // 清除错误消息
            ['longitude-error', 'latitude-error', 'value-error'].forEach(id => {
                const errorDiv = document.getElementById(id);
                if (errorDiv) {
                    errorDiv.style.display = 'none';
                }
            });

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
