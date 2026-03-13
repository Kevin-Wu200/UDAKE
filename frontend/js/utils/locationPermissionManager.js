/**
 * 定位权限管理模块
 * 统一封装浏览器 Geolocation API 的权限检测与请求逻辑
 * 所有定位功能必须通过该模块调用，不允许在业务组件中直接调用 navigator.geolocation
 */
import { ErrorHandler } from './ErrorHandler.js';

/**
 * 权限状态枚举
 */
const PermissionStatus = {
    GRANTED: 'granted',
    DENIED: 'denied',
    UNKNOWN: 'unknown'
};

/**
 * 全局权限状态
 */
let locationPermissionStatus = PermissionStatus.UNKNOWN;

/**
 * 检查当前定位权限状态
 * 使用 navigator.permissions.query 查询 geolocation 权限
 * @returns {Promise<string>} 权限状态: 'granted' | 'denied' | 'unknown'
 */
async function checkPermission() {
    // 浏览器不支持 Geolocation API
    if (!navigator.geolocation) {
        locationPermissionStatus = PermissionStatus.DENIED;
        return PermissionStatus.DENIED;
    }

    // 尝试使用 Permissions API 查询
    if (navigator.permissions && navigator.permissions.query) {
        try {
            const result = await navigator.permissions.query({ name: 'geolocation' });
            if (result.state === 'granted') {
                locationPermissionStatus = PermissionStatus.GRANTED;
            } else if (result.state === 'denied') {
                locationPermissionStatus = PermissionStatus.DENIED;
            } else {
                // prompt 状态，标记为 unknown 等待用户决定
                locationPermissionStatus = PermissionStatus.UNKNOWN;
            }

            // 监听权限状态变化
            result.addEventListener('change', () => {
                if (result.state === 'granted') {
                    locationPermissionStatus = PermissionStatus.GRANTED;
                } else if (result.state === 'denied') {
                    locationPermissionStatus = PermissionStatus.DENIED;
                } else {
                    locationPermissionStatus = PermissionStatus.UNKNOWN;
                }
            });

            return locationPermissionStatus;
        } catch (e) {
            // Permissions API 不可用，保持 unknown
            return PermissionStatus.UNKNOWN;
        }
    }

    return PermissionStatus.UNKNOWN;
}

/**
 * 请求定位权限
 * 在应用启动时调用，若权限为 prompt 则触发一次定位请求以弹出系统授权窗口
 * 首次请求前显示简短说明
 * @returns {Promise<string>} 最终权限状态
 */
async function requestPermission() {
    const status = await checkPermission();

    if (status === PermissionStatus.GRANTED) {
        return PermissionStatus.GRANTED;
    }

    if (status === PermissionStatus.DENIED) {
        return PermissionStatus.DENIED;
    }

    // 状态为 unknown (prompt)，触发一次定位请求以弹出授权窗口
    // 显示简短说明
    ErrorHandler.showGlobalNotification(
        'UDAKE 需要使用设备定位以支持当前位置采样功能。',
        'warning'
    );

    return new Promise((resolve) => {
        navigator.geolocation.getCurrentPosition(
            () => {
                locationPermissionStatus = PermissionStatus.GRANTED;
                resolve(PermissionStatus.GRANTED);
            },
            (error) => {
                if (error.code === error.PERMISSION_DENIED) {
                    locationPermissionStatus = PermissionStatus.DENIED;
                    resolve(PermissionStatus.DENIED);
                } else {
                    // 超时或不可用，但权限本身可能未被拒绝
                    locationPermissionStatus = PermissionStatus.UNKNOWN;
                    resolve(PermissionStatus.UNKNOWN);
                }
            },
            {
                enableHighAccuracy: false,
                timeout: 10000,
                maximumAge: 0
            }
        );
    });
}

/**
 * 获取当前位置
 * 所有业务模块必须通过此方法获取定位，不允许直接调用 navigator.geolocation
 * @returns {Promise<{longitude: number, latitude: number, accuracy: number, timestamp: string}>}
 */
function getCurrentPosition() {
    return new Promise((resolve, reject) => {
        // 浏览器不支持 Geolocation API
        if (!navigator.geolocation) {
            reject({ type: 'unsupported', message: '当前设备不支持定位功能' });
            return;
        }

        // 权限被拒绝
        if (locationPermissionStatus === PermissionStatus.DENIED) {
            reject({
                type: 'denied',
                message: '定位权限未授权，无法使用当前位置采样功能，请在系统设置中开启定位权限。'
            });
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                locationPermissionStatus = PermissionStatus.GRANTED;
                resolve({
                    longitude: position.coords.longitude,
                    latitude: position.coords.latitude,
                    accuracy: position.coords.accuracy,
                    timestamp: new Date(position.timestamp).toISOString()
                });
            },
            (error) => {
                if (error.code === error.PERMISSION_DENIED) {
                    locationPermissionStatus = PermissionStatus.DENIED;
                    reject({
                        type: 'denied',
                        message: '定位权限未授权，无法使用当前位置采样功能，请在系统设置中开启定位权限。'
                    });
                } else if (error.code === error.TIMEOUT) {
                    reject({ type: 'timeout', message: '定位获取超时' });
                } else if (error.code === error.POSITION_UNAVAILABLE) {
                    reject({ type: 'unavailable', message: '设备定位不可用' });
                } else {
                    reject({ type: 'unknown', message: '未知的定位错误' });
                }
            },
            {
                enableHighAccuracy: false,
                timeout: 10000,
                maximumAge: 0
            }
        );
    });
}

/**
 * 获取当前权限状态
 * @returns {string} 'granted' | 'denied' | 'unknown'
 */
function getPermissionStatus() {
    return locationPermissionStatus;
}

export const LocationPermissionManager = {
    PermissionStatus,
    checkPermission,
    requestPermission,
    getCurrentPosition,
    getPermissionStatus
};
