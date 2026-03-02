/**
 * 异常处理和提示系统
 * 统一管理错误提示和用户反馈
 */
export class ErrorHandler {
    /**
     * 错误类型枚举
     */
    static ErrorTypes = {
        GEOJSON_FORMAT: 'geojson_format',
        COORDINATE_FORMAT: 'coordinate_format',
        POINT_OUT_OF_BOUNDS: 'point_out_of_bounds',
        GEOLOCATION_FAILED: 'geolocation_failed',
        PERMISSION_DENIED: 'permission_denied',
        INVALID_POLYGON: 'invalid_polygon',
        NETWORK_ERROR: 'network_error',
        VALIDATION_ERROR: 'validation_error'
    };

    /**
     * 错误消息映射
     */
    static ErrorMessages = {
        [ErrorHandler.ErrorTypes.GEOJSON_FORMAT]: 'GeoJSON 格式错误，请检查文件格式',
        [ErrorHandler.ErrorTypes.COORDINATE_FORMAT]: '坐标格式错误，请输入有效的经纬度',
        [ErrorHandler.ErrorTypes.POINT_OUT_OF_BOUNDS]: '采样点超出区域边界，无法添加',
        [ErrorHandler.ErrorTypes.GEOLOCATION_FAILED]: '设备定位失败，请检查设备设置',
        [ErrorHandler.ErrorTypes.PERMISSION_DENIED]: '定位权限被拒绝，请在浏览器设置中允许定位',
        [ErrorHandler.ErrorTypes.INVALID_POLYGON]: '无效的多边形，仅支持 Polygon 或 MultiPolygon',
        [ErrorHandler.ErrorTypes.NETWORK_ERROR]: '网络请求失败，请检查网络连接',
        [ErrorHandler.ErrorTypes.VALIDATION_ERROR]: '数据验证失败，请检查输入'
    };

    /**
     * 显示错误提示
     * @param {string} errorType - 错误类型
     * @param {string} [customMessage] - 自定义消息
     * @param {HTMLElement} [container] - 容器元素
     */
    static showError(errorType, customMessage = null, container = null) {
        const message = customMessage || ErrorHandler.ErrorMessages[errorType] || '未知错误';

        if (container) {
            ErrorHandler.showInContainer(message, 'error', container);
        } else {
            ErrorHandler.showGlobalNotification(message, 'error');
        }

        console.error(`[${errorType}]`, message);
    }

    /**
     * 显示成功提示
     * @param {string} message - 消息内容
     * @param {HTMLElement} [container] - 容器元素
     */
    static showSuccess(message, container = null) {
        if (container) {
            ErrorHandler.showInContainer(message, 'success', container);
        } else {
            ErrorHandler.showGlobalNotification(message, 'success');
        }
    }

    /**
     * 显示警告提示
     * @param {string} message - 消息内容
     * @param {HTMLElement} [container] - 容器元素
     */
    static showWarning(message, container = null) {
        if (container) {
            ErrorHandler.showInContainer(message, 'warning', container);
        } else {
            ErrorHandler.showGlobalNotification(message, 'warning');
        }
    }

    /**
     * 在容器内显示消息
     * @param {string} message - 消息内容
     * @param {string} type - 消息类型
     * @param {HTMLElement} container - 容器元素
     */
    static showInContainer(message, type, container) {
        let statusDiv = container.querySelector('.status-message');

        if (!statusDiv) {
            statusDiv = document.createElement('div');
            statusDiv.className = 'status-message';
            container.appendChild(statusDiv);
        }

        statusDiv.textContent = message;
        statusDiv.className = `status-message ${type}`;
        statusDiv.style.display = 'block';

        // 3秒后自动隐藏
        setTimeout(() => {
            statusDiv.style.opacity = '0';
            setTimeout(() => {
                statusDiv.style.display = 'none';
                statusDiv.style.opacity = '1';
            }, 200);
        }, 3000);
    }

    /**
     * 显示全局通知
     * @param {string} message - 消息内容
     * @param {string} type - 消息类型
     */
    static showGlobalNotification(message, type) {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;

        // 添加样式
        Object.assign(notification.style, {
            position: 'fixed',
            top: '80px',
            right: '32px',
            padding: '16px 24px',
            borderRadius: '12px',
            backgroundColor: type === 'error' ? 'rgba(255, 59, 48, 0.95)' :
                            type === 'success' ? 'rgba(52, 199, 89, 0.95)' :
                            'rgba(255, 149, 0, 0.95)',
            color: 'white',
            fontSize: '14px',
            fontWeight: '500',
            boxShadow: '0 8px 20px rgba(0, 0, 0, 0.15)',
            zIndex: '10000',
            opacity: '0',
            transform: 'translateX(400px)',
            transition: 'all 300ms cubic-bezier(0.4, 0.0, 0.2, 1)'
        });

        document.body.appendChild(notification);

        // 动画显示
        requestAnimationFrame(() => {
            notification.style.opacity = '1';
            notification.style.transform = 'translateX(0)';
        });

        // 3秒后自动移除
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(400px)';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }

    /**
     * 验证 GeoJSON 格式
     * @param {Object} geojson - GeoJSON 对象
     * @returns {Object} {valid: boolean, error: string}
     */
    static validateGeoJSON(geojson) {
        if (!geojson || typeof geojson !== 'object') {
            return {
                valid: false,
                error: 'GeoJSON 必须是一个对象'
            };
        }

        if (!geojson.type) {
            return {
                valid: false,
                error: 'GeoJSON 缺少 type 字段'
            };
        }

        if (geojson.type === 'FeatureCollection') {
            if (!Array.isArray(geojson.features)) {
                return {
                    valid: false,
                    error: 'FeatureCollection 缺少 features 数组'
                };
            }
        } else if (geojson.type === 'Feature') {
            if (!geojson.geometry) {
                return {
                    valid: false,
                    error: 'Feature 缺少 geometry 字段'
                };
            }
        }

        return { valid: true };
    }

    /**
     * 验证多边形类型
     * @param {Object} geometry - 几何对象
     * @returns {Object} {valid: boolean, error: string}
     */
    static validatePolygon(geometry) {
        if (!geometry || !geometry.type) {
            return {
                valid: false,
                error: '缺少几何类型'
            };
        }

        if (!['Polygon', 'MultiPolygon'].includes(geometry.type)) {
            return {
                valid: false,
                error: `不支持的几何类型: ${geometry.type}，仅支持 Polygon 或 MultiPolygon`
            };
        }

        if (!geometry.coordinates || !Array.isArray(geometry.coordinates)) {
            return {
                valid: false,
                error: '缺少坐标数组'
            };
        }

        return { valid: true };
    }

    /**
     * 验证坐标格式
     * @param {number} longitude - 经度
     * @param {number} latitude - 纬度
     * @returns {Object} {valid: boolean, error: string}
     */
    static validateCoordinates(longitude, latitude) {
        if (typeof longitude !== 'number' || typeof latitude !== 'number') {
            return {
                valid: false,
                error: '经纬度必须是数字'
            };
        }

        if (isNaN(longitude) || isNaN(latitude)) {
            return {
                valid: false,
                error: '经纬度不能是 NaN'
            };
        }

        if (longitude < -180 || longitude > 180) {
            return {
                valid: false,
                error: '经度必须在 -180 到 180 之间'
            };
        }

        if (latitude < -90 || latitude > 90) {
            return {
                valid: false,
                error: '纬度必须在 -90 到 90 之间'
            };
        }

        return { valid: true };
    }

    /**
     * 处理地理定位错误
     * @param {GeolocationPositionError} error - 定位错误对象
     */
    static handleGeolocationError(error) {
        let errorType;
        let message;

        switch (error.code) {
            case error.PERMISSION_DENIED:
                errorType = ErrorHandler.ErrorTypes.PERMISSION_DENIED;
                message = '用户拒绝了定位请求';
                break;
            case error.POSITION_UNAVAILABLE:
                errorType = ErrorHandler.ErrorTypes.GEOLOCATION_FAILED;
                message = '位置信息不可用';
                break;
            case error.TIMEOUT:
                errorType = ErrorHandler.ErrorTypes.GEOLOCATION_FAILED;
                message = '定位请求超时';
                break;
            default:
                errorType = ErrorHandler.ErrorTypes.GEOLOCATION_FAILED;
                message = '未知的定位错误';
        }

        ErrorHandler.showError(errorType, message);
        return { errorType, message };
    }
}
