/**
 * 定位权限管理模块
 * 统一封装浏览器 Geolocation API 的权限检测与请求逻辑
 * 所有定位功能必须通过该模块调用，不允许在业务组件中直接调用 navigator.geolocation
 */
import { ErrorHandler } from './ErrorHandler.js';

/** 权限状态枚举 */
const PermissionStatusEnum = {
    GRANTED: 'granted',
    DENIED: 'denied',
    UNKNOWN: 'unknown'
} as const;

type PermissionStatusValue = typeof PermissionStatusEnum[keyof typeof PermissionStatusEnum];

/** 定位结果 */
interface LocationResult {
    longitude: number;
    latitude: number;
    accuracy: number;
    timestamp: string;
}

/** 定位错误 */
interface LocationError {
    type: 'unsupported' | 'denied' | 'timeout' | 'unavailable' | 'unknown';
    message: string;
}

/** 全局权限状态 */
let locationPermissionStatus: PermissionStatusValue = PermissionStatusEnum.UNKNOWN;

/**
 * 检查当前定位权限状态
 */
async function checkPermission(): Promise<PermissionStatusValue> {
    if (!navigator.geolocation) {
        locationPermissionStatus = PermissionStatusEnum.DENIED;
        return PermissionStatusEnum.DENIED;
    }

    if (navigator.permissions && navigator.permissions.query) {
        try {
            const result = await navigator.permissions.query({ name: 'geolocation' as PermissionName });
            if (result.state === 'granted') {
                locationPermissionStatus = PermissionStatusEnum.GRANTED;
            } else if (result.state === 'denied') {
                locationPermissionStatus = PermissionStatusEnum.DENIED;
            } else {
                locationPermissionStatus = PermissionStatusEnum.UNKNOWN;
            }

            result.addEventListener('change', () => {
                if (result.state === 'granted') {
                    locationPermissionStatus = PermissionStatusEnum.GRANTED;
                } else if (result.state === 'denied') {
                    locationPermissionStatus = PermissionStatusEnum.DENIED;
                } else {
                    locationPermissionStatus = PermissionStatusEnum.UNKNOWN;
                }
            });

            return locationPermissionStatus;
        } catch {
            return PermissionStatusEnum.UNKNOWN;
        }
    }

    return PermissionStatusEnum.UNKNOWN;
}

/**
 * 请求定位权限
 */
async function requestPermission(): Promise<PermissionStatusValue> {
    const status = await checkPermission();

    if (status === PermissionStatusEnum.GRANTED) {
        return PermissionStatusEnum.GRANTED;
    }

    if (status === PermissionStatusEnum.DENIED) {
        return PermissionStatusEnum.DENIED;
    }

    ErrorHandler.showWarning(
        'UDAKE 需要使用设备定位以支持当前位置采样功能。'
    );

    return new Promise<PermissionStatusValue>((resolve) => {
        navigator.geolocation.getCurrentPosition(
            () => {
                locationPermissionStatus = PermissionStatusEnum.GRANTED;
                resolve(PermissionStatusEnum.GRANTED);
            },
            (error) => {
                if (error.code === error.PERMISSION_DENIED) {
                    locationPermissionStatus = PermissionStatusEnum.DENIED;
                    resolve(PermissionStatusEnum.DENIED);
                } else {
                    locationPermissionStatus = PermissionStatusEnum.UNKNOWN;
                    resolve(PermissionStatusEnum.UNKNOWN);
                }
            },
            { enableHighAccuracy: false, timeout: 10000, maximumAge: 0 }
        );
    });
}
/**
 * 获取当前位置
 */
function getCurrentPosition(): Promise<LocationResult> {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject({ type: 'unsupported', message: '当前设备不支持定位功能' } as LocationError);
            return;
        }

        if (locationPermissionStatus === PermissionStatusEnum.DENIED) {
            reject({
                type: 'denied',
                message: '定位权限未授权，无法使用当前位置采样功能，请在系统设置中开启定位权限。'
            } as LocationError);
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                locationPermissionStatus = PermissionStatusEnum.GRANTED;
                resolve({
                    longitude: position.coords.longitude,
                    latitude: position.coords.latitude,
                    accuracy: position.coords.accuracy,
                    timestamp: new Date(position.timestamp).toISOString()
                });
            },
            (error) => {
                if (error.code === error.PERMISSION_DENIED) {
                    locationPermissionStatus = PermissionStatusEnum.DENIED;
                    reject({ type: 'denied', message: '定位权限未授权，无法使用当前位置采样功能，请在系统设置中开启定位权限。' } as LocationError);
                } else if (error.code === error.TIMEOUT) {
                    reject({ type: 'timeout', message: '定位获取超时' } as LocationError);
                } else if (error.code === error.POSITION_UNAVAILABLE) {
                    reject({ type: 'unavailable', message: '设备定位不可用' } as LocationError);
                } else {
                    reject({ type: 'unknown', message: '未知的定位错误' } as LocationError);
                }
            },
            { enableHighAccuracy: false, timeout: 10000, maximumAge: 0 }
        );
    });
}

/**
 * 获取当前权限状态
 */
function getPermissionStatus(): PermissionStatusValue {
    return locationPermissionStatus;
}

export const LocationPermissionManager = {
    PermissionStatus: PermissionStatusEnum,
    checkPermission,
    requestPermission,
    getCurrentPosition,
    getPermissionStatus
};