/**
 * 增强版异常处理和提示系统
 * 统一管理错误提示、用户反馈、重试建议、修复指引、错误日志
 */
import type { ErrorType, ErrorDetail, ErrorLogEntry, ValidationResult } from '../../types/core';
import { I18n } from './I18n';

interface ToastOptions {
    message: string;
    suggestion?: string;
    example?: string;
    type: 'error' | 'success' | 'warning';
    retryable?: boolean;
    onRetry?: () => void;
    duration: number;
}

interface ShowErrorOptions {
    container?: HTMLElement;
    onRetry?: () => void;
    duration?: number;
}

export class ErrorHandler {
    static ErrorTypes: Record<string, ErrorType> = {
        GEOJSON_FORMAT: 'geojson_format',
        COORDINATE_FORMAT: 'coordinate_format',
        POINT_OUT_OF_BOUNDS: 'point_out_of_bounds',
        GEOLOCATION_FAILED: 'geolocation_failed',
        PERMISSION_DENIED: 'permission_denied',
        INVALID_POLYGON: 'invalid_polygon',
        NETWORK_ERROR: 'network_error',
        VALIDATION_ERROR: 'validation_error',
        SERVER_ERROR: 'server_error',
        TIMEOUT_ERROR: 'timeout_error',
        FILE_TOO_LARGE: 'file_too_large',
        UNSUPPORTED_FORMAT: 'unsupported_format',
        INTERPOLATION_FAILED: 'interpolation_failed',
        INSUFFICIENT_POINTS: 'insufficient_points',
        EXPORT_FAILED: 'export_failed'
    };

    private static _fallbackErrorDetails: Record<ErrorType, ErrorDetail> = {
        geojson_format: {
            message: 'GeoJSON 格式错误',
            suggestion: '请确保文件是标准的 GeoJSON 格式，包含 type 和 features 字段。',
            example: '示例: {"type": "FeatureCollection", "features": [...]}'
        },
        coordinate_format: {
            message: '坐标格式错误',
            suggestion: '请输入有效的经纬度坐标，经度范围 -180~180，纬度范围 -90~90。',
            example: '示例: 经度 116.397428, 纬度 39.90923'
        },
        point_out_of_bounds: {
            message: '采样点超出区域边界',
            suggestion: '请确保采样点在已设定的区域边界内，或切换到自由采样模式。'
        },
        geolocation_failed: {
            message: '设备定位失败',
            suggestion: '请检查设备GPS是否开启，或尝试在室外环境重新定位。'
        },
        permission_denied: {
            message: '定位权限被拒绝',
            suggestion: '请在浏览器设置中允许本站访问位置信息，然后刷新页面重试。'
        },
        invalid_polygon: {
            message: '无效的多边形数据',
            suggestion: '仅支持 Polygon 或 MultiPolygon 类型，请检查 GeoJSON 几何类型。'
        },
        network_error: {
            message: '网络连接失败',
            suggestion: '请检查网络连接和后端服务是否正常运行。',
            retryable: true
        },
        validation_error: {
            message: '数据验证失败',
            suggestion: '请检查输入数据是否符合要求。'
        },
        server_error: {
            message: '服务器内部错误',
            suggestion: '服务器处理请求时出错，请稍后重试。如问题持续，请联系管理员。',
            retryable: true
        },
        timeout_error: {
            message: '请求超时',
            suggestion: '服务器响应时间过长，可能是数据量较大。请稍后重试或减小数据规模。',
            retryable: true
        },
        file_too_large: {
            message: '文件过大',
            suggestion: '上传文件不能超过 50MB，请压缩数据或分批上传。'
        },
        unsupported_format: {
            message: '不支持的文件格式',
            suggestion: '仅支持 .geojson 和 .json 格式的文件。'
        },
        interpolation_failed: {
            message: '插值计算失败',
            suggestion: '可能是采样点分布不合理或参数设置有误，请尝试调整变异函数模型或网格分辨率。'
        },
        insufficient_points: {
            message: '采样点不足',
            suggestion: '克里金插值至少需要 3 个采样点，请继续添加采样数据。'
        },
        export_failed: {
            message: '导出失败',
            suggestion: '文件生成出错，请确认插值任务已完成后重试。',
            retryable: true
        }
    };

    static get ErrorDetails(): Record<ErrorType, ErrorDetail> {
        return Object.values(ErrorHandler.ErrorTypes).reduce((acc, type) => {
            acc[type] = ErrorHandler.getErrorDetail(type);
            return acc;
        }, {} as Record<ErrorType, ErrorDetail>);
    }

    private static _t(key: string, fallback: string = ''): string {
        const translated = I18n.t(key);
        return translated === key ? fallback : translated;
    }

    static getErrorDetail(errorType: ErrorType): ErrorDetail {
        const fallback = ErrorHandler._fallbackErrorDetails[errorType] || { message: '未知错误' };
        const detail: ErrorDetail = {
            message: ErrorHandler._t(`error.${errorType}.message`, fallback.message),
            suggestion: ErrorHandler._t(`error.${errorType}.suggestion`, fallback.suggestion || ''),
            retryable: fallback.retryable
        };

        const example = ErrorHandler._t(`error.${errorType}.example`, fallback.example || '');
        if (example) {
            detail.example = example;
        }
        if (!detail.suggestion) {
            delete detail.suggestion;
        }
        return detail;
    }

    static _errorLog: ErrorLogEntry[] = [];
    static _maxLogSize: number = 200;

    static _log(errorType: ErrorType, message: string, context: Record<string, unknown> = {}): void {
        const entry: ErrorLogEntry = {
            type: errorType,
            message,
            timestamp: new Date().toISOString(),
            url: window.location.href,
            ...context
        };
        ErrorHandler._errorLog.push(entry);
        if (ErrorHandler._errorLog.length > ErrorHandler._maxLogSize) {
            ErrorHandler._errorLog.shift();
        }
        console.error(`[${errorType}]`, message, context);
    }

    static getErrorLog(): ErrorLogEntry[] {
        return [...ErrorHandler._errorLog];
    }

    static clearErrorLog(): void {
        ErrorHandler._errorLog = [];
    }

    static showError(errorType: ErrorType, customMessage: string | null = null, options: ShowErrorOptions = {}): void {
        const detail: ErrorDetail = ErrorHandler.getErrorDetail(errorType);
        const message: string = customMessage || detail.message || ErrorHandler._t('error.common.unknown', '未知错误');
        const suggestion: string = detail.suggestion || '';
        const retryable: boolean = detail.retryable || false;
        const example: string = detail.example || '';

        ErrorHandler._log(errorType, message, { suggestion });

        if (options.container) {
            ErrorHandler.showInContainer(message, 'error', options.container, suggestion);
        } else {
            ErrorHandler._showToast({
                message,
                suggestion,
                example,
                type: 'error',
                retryable: retryable && !!options.onRetry,
                onRetry: options.onRetry,
                duration: options.duration || 5000
            });
        }
    }

    static showSuccess(message: string, container: HTMLElement | null = null): void {
        if (container) {
            ErrorHandler.showInContainer(message, 'success', container);
        } else {
            ErrorHandler._showToast({ message, type: 'success', duration: 3000 });
        }
    }

    static showWarning(message: string, container: HTMLElement | null = null): void {
        if (container) {
            ErrorHandler.showInContainer(message, 'warning', container);
        } else {
            ErrorHandler._showToast({ message, type: 'warning', duration: 4000 });
        }
    }

    static showInContainer(message: string, type: 'error' | 'success' | 'warning', container: HTMLElement, suggestion: string = ''): void {
        let statusDiv: HTMLElement | null = container.querySelector('.status-message');
        if (!statusDiv) {
            statusDiv = document.createElement('div');
            statusDiv.className = 'status-message';
            container.appendChild(statusDiv);
        }

        let html: string = `<span class="status-msg-text">${message}</span>`;
        if (suggestion) {
            html += `<span class="status-msg-hint">${suggestion}</span>`;
        }
        statusDiv.innerHTML = html;
        statusDiv.className = `status-message ${type}`;
        statusDiv.style.display = 'block';

        const div = statusDiv;
        setTimeout(() => {
            div.style.opacity = '0';
            setTimeout(() => {
                div.style.display = 'none';
                div.style.opacity = '1';
            }, 200);
        }, 4000);
    }

    static _showToast({ message, suggestion, example, type, retryable, onRetry, duration }: ToastOptions): void {
        const toast: HTMLDivElement = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const colors: Record<string, string> = {
            error: 'rgba(255, 59, 48, 0.95)',
            success: 'rgba(52, 199, 89, 0.95)',
            warning: 'rgba(255, 149, 0, 0.95)'
        };

        Object.assign(toast.style, {
            position: 'fixed',
            top: '80px',
            right: '32px',
            maxWidth: '400px',
            padding: '16px 20px',
            borderRadius: '14px',
            backgroundColor: colors[type] || colors.error,
            color: 'white',
            fontSize: '14px',
            fontWeight: '500',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.2)',
            zIndex: '10000',
            opacity: '0',
            transform: 'translateX(420px)',
            transition: 'all 300ms cubic-bezier(0.4, 0, 0.2, 1)',
            lineHeight: '1.5'
        });

        let html: string = `<div style="font-weight:600;margin-bottom:4px">${message}</div>`;
        if (suggestion) html += `<div style="font-size:12px;opacity:0.9">${suggestion}</div>`;
        if (example) html += `<div style="font-size:11px;opacity:0.75;margin-top:4px;font-family:monospace">${example}</div>`;
        if (retryable && onRetry) {
            const retryLabel = ErrorHandler._t('error.common.retryButton', '重试');
            html += `<button class="toast-retry-btn" style="margin-top:8px;padding:4px 12px;border:1px solid rgba(255,255,255,0.5);border-radius:6px;background:transparent;color:white;font-size:12px;cursor:pointer">${retryLabel}</button>`;
        }
        toast.innerHTML = html;

        document.body.appendChild(toast);

        if (retryable && onRetry) {
            toast.querySelector('.toast-retry-btn')?.addEventListener('click', () => {
                toast.remove();
                onRetry();
            });
        }

        requestAnimationFrame(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(0)';
        });

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(420px)';
            setTimeout(() => toast.remove(), 300);
        }, duration || 5000);
    }

    static validateGeoJSON(geojson: unknown): ValidationResult {
        if (!geojson || typeof geojson !== 'object') {
            return { valid: false, error: ErrorHandler._t('error.validation.geojson_object', 'GeoJSON 必须是一个对象') };
        }
        const obj = geojson as Record<string, unknown>;
        if (!obj.type) {
            return { valid: false, error: ErrorHandler._t('error.validation.geojson_missing_type', 'GeoJSON 缺少 type 字段') };
        }
        if (obj.type === 'FeatureCollection') {
            if (!Array.isArray((obj as any).features)) {
                return { valid: false, error: ErrorHandler._t('error.validation.geojson_missing_features', 'FeatureCollection 缺少 features 数组') };
            }
        } else if (obj.type === 'Feature') {
            if (!(obj as any).geometry) {
                return { valid: false, error: ErrorHandler._t('error.validation.geojson_missing_geometry', 'Feature 缺少 geometry 字段') };
            }
        }
        return { valid: true };
    }

    static validatePolygon(geometry: unknown): ValidationResult {
        if (!geometry || typeof geometry !== 'object') {
            return { valid: false, error: ErrorHandler._t('error.validation.geometry_missing_type', '缺少几何类型') };
        }
        const geo = geometry as Record<string, unknown>;
        if (!geo.type) {
            return { valid: false, error: ErrorHandler._t('error.validation.geometry_missing_type', '缺少几何类型') };
        }
        if (!['Polygon', 'MultiPolygon'].includes(geo.type as string)) {
            return {
                valid: false,
                error: I18n.t('error.validation.geometry_unsupported', { type: String(geo.type) })
            };
        }
        if (!geo.coordinates || !Array.isArray(geo.coordinates)) {
            return { valid: false, error: ErrorHandler._t('error.validation.geometry_missing_coordinates', '缺少坐标数组') };
        }
        return { valid: true };
    }

    static validateCoordinates(longitude: number, latitude: number): ValidationResult {
        if (typeof longitude !== 'number' || typeof latitude !== 'number') {
            return { valid: false, error: ErrorHandler._t('error.validation.coordinates_not_number', '经纬度必须是数字') };
        }
        if (isNaN(longitude) || isNaN(latitude)) {
            return { valid: false, error: ErrorHandler._t('error.validation.coordinates_nan', '经纬度不能是 NaN') };
        }
        if (longitude < -180 || longitude > 180) {
            return { valid: false, error: ErrorHandler._t('error.validation.coordinates_longitude_range', '经度必须在 -180 到 180 之间') };
        }
        if (latitude < -90 || latitude > 90) {
            return { valid: false, error: ErrorHandler._t('error.validation.coordinates_latitude_range', '纬度必须在 -90 到 90 之间') };
        }
        return { valid: true };
    }

    static handleGeolocationError(error: GeolocationPositionError): { errorType: ErrorType; message: string } {
        let errorType: ErrorType;
        let message: string;
        switch (error.code) {
            case error.PERMISSION_DENIED:
                errorType = 'permission_denied';
                message = ErrorHandler._t('error.geolocation.user_denied', '用户拒绝了定位请求');
                break;
            case error.POSITION_UNAVAILABLE:
                errorType = 'geolocation_failed';
                message = ErrorHandler._t('error.geolocation.position_unavailable', '位置信息不可用');
                break;
            case error.TIMEOUT:
                errorType = 'geolocation_failed';
                message = ErrorHandler._t('error.geolocation.timeout', '定位请求超时');
                break;
            default:
                errorType = 'geolocation_failed';
                message = ErrorHandler._t('error.geolocation.unknown', '未知的定位错误');
        }
        ErrorHandler.showError(errorType, message);
        return { errorType, message };
    }

    static fromHttpStatus(status: number, context: string = ''): ErrorType {
        if (status >= 500) return 'server_error';
        if (status === 408) return 'timeout_error';
        if (status === 413) return 'file_too_large';
        if (status === 422) return 'validation_error';
        return 'network_error';
    }
}
