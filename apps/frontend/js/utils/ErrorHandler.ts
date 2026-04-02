/**
 * 增强版异常处理和提示系统
 * 统一管理错误提示、用户反馈、重试建议、修复指引、错误日志
 */
import type { ErrorType, ErrorDetail, ErrorLogEntry, ValidationResult, ErrorLevel } from '../../types/core';
import { I18n } from './I18n';

interface ToastAction {
    key: string;
    label: string;
    primary?: boolean;
    onClick?: () => void;
}

interface ToastOptions {
    message: string;
    suggestion?: string;
    example?: string;
    icon?: string;
    details?: string;
    actions?: ToastAction[];
    type: 'error' | 'success' | 'warning';
    retryable?: boolean;
    onRetry?: () => void;
    duration: number;
}

interface ShowErrorOptions {
    container?: HTMLElement;
    onRetry?: () => void;
    duration?: number;
    details?: string;
    context?: Record<string, unknown>;
    actions?: ToastAction[];
}

interface ErrorStat {
    type: string;
    count: number;
    lastSeenAt: string;
}

type ErrorMiddleware = (
    errorType: ErrorType,
    message: string,
    context: Record<string, unknown>,
    next: () => void
) => void;

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

    static ErrorCodes: Record<ErrorType, string> = {
        geojson_format: 'E-GEOJSON-001',
        coordinate_format: 'E-COORD-001',
        point_out_of_bounds: 'E-POINT-001',
        geolocation_failed: 'E-GEOLOC-001',
        permission_denied: 'E-PERM-001',
        invalid_polygon: 'E-POLY-001',
        network_error: 'E-NET-001',
        validation_error: 'E-VALID-001',
        server_error: 'E-SERVER-001',
        timeout_error: 'E-TIMEOUT-001',
        file_too_large: 'E-FILE-001',
        unsupported_format: 'E-FORMAT-001',
        interpolation_failed: 'E-INTP-001',
        insufficient_points: 'E-POINT-002',
        export_failed: 'E-EXPORT-001'
    };

    static ErrorLevels: Record<ErrorType, ErrorLevel> = {
        geojson_format: 'WARNING',
        coordinate_format: 'WARNING',
        point_out_of_bounds: 'WARNING',
        geolocation_failed: 'SEVERE',
        permission_denied: 'SEVERE',
        invalid_polygon: 'WARNING',
        network_error: 'SEVERE',
        validation_error: 'WARNING',
        server_error: 'FATAL',
        timeout_error: 'SEVERE',
        file_too_large: 'INFO',
        unsupported_format: 'INFO',
        interpolation_failed: 'SEVERE',
        insufficient_points: 'INFO',
        export_failed: 'WARNING'
    };

    private static _fallbackErrorDetails: Record<ErrorType, ErrorDetail> = {
        geojson_format: {
            code: 'E-GEOJSON-001',
            level: 'WARNING',
            icon: '🧩',
            message: 'GeoJSON 格式错误',
            suggestion: '请确保文件是标准的 GeoJSON 格式，包含 type 和 features 字段。',
            solutions: ['检查 GeoJSON 的 type 字段', '确认 FeatureCollection 包含 features 数组'],
            helpLink: '/help/data-format/geojson',
            example: '示例: {"type": "FeatureCollection", "features": [...]}'
        },
        coordinate_format: {
            code: 'E-COORD-001',
            level: 'WARNING',
            icon: '📍',
            message: '坐标格式错误',
            suggestion: '请输入有效的经纬度坐标，经度范围 -180~180，纬度范围 -90~90。',
            solutions: ['检查经纬度是否为数字', '确认经度和纬度范围正确'],
            helpLink: '/help/location/coordinate',
            example: '示例: 经度 116.397428, 纬度 39.90923'
        },
        point_out_of_bounds: {
            code: 'E-POINT-001',
            level: 'WARNING',
            icon: '🗺️',
            message: '采样点超出区域边界',
            suggestion: '请确保采样点在已设定的区域边界内，或切换到自由采样模式。',
            solutions: ['将点位移动到边界内部', '检查边界是否上传正确']
        },
        geolocation_failed: {
            code: 'E-GEOLOC-001',
            level: 'SEVERE',
            icon: '📡',
            message: '设备定位失败',
            suggestion: '请检查设备GPS是否开启，或尝试在室外环境重新定位。',
            solutions: ['开启定位服务', '切换到信号更好的区域后重试']
        },
        permission_denied: {
            code: 'E-PERM-001',
            level: 'SEVERE',
            icon: '🔒',
            message: '定位权限被拒绝',
            suggestion: '请在浏览器设置中允许本站访问位置信息，然后刷新页面重试。',
            solutions: ['打开浏览器权限设置', '允许位置权限后刷新页面']
        },
        invalid_polygon: {
            code: 'E-POLY-001',
            level: 'WARNING',
            icon: '🔷',
            message: '无效的多边形数据',
            suggestion: '仅支持 Polygon 或 MultiPolygon 类型，请检查 GeoJSON 几何类型。',
            solutions: ['确认 geometry.type 为 Polygon 或 MultiPolygon']
        },
        network_error: {
            code: 'E-NET-001',
            level: 'SEVERE',
            icon: '📶',
            message: '网络连接失败',
            suggestion: '请检查网络连接和后端服务是否正常运行。',
            solutions: ['检查网络连接是否正常', '确认后端服务已启动', '点击重试重新发起请求'],
            retryable: true
        },
        validation_error: {
            code: 'E-VALID-001',
            level: 'WARNING',
            icon: '✅',
            message: '数据验证失败',
            suggestion: '请检查输入数据是否符合要求。',
            solutions: ['检查必填项', '按示例数据格式输入']
        },
        server_error: {
            code: 'E-SERVER-001',
            level: 'FATAL',
            icon: '🛠️',
            message: '服务器内部错误',
            suggestion: '服务器处理请求时出错，请稍后重试。如问题持续，请联系管理员。',
            solutions: ['稍后重试', '刷新页面后重试', '联系管理员并附上错误码'],
            retryable: true
        },
        timeout_error: {
            code: 'E-TIMEOUT-001',
            level: 'SEVERE',
            icon: '⏱️',
            message: '请求超时',
            suggestion: '服务器响应时间过长，可能是数据量较大。请稍后重试或减小数据规模。',
            solutions: ['稍后重试', '减少单次处理数据量'],
            retryable: true
        },
        file_too_large: {
            code: 'E-FILE-001',
            level: 'INFO',
            icon: '📦',
            message: '文件过大',
            suggestion: '上传文件不能超过 50MB，请压缩数据或分批上传。',
            solutions: ['压缩文件', '拆分后分批上传']
        },
        unsupported_format: {
            code: 'E-FORMAT-001',
            level: 'INFO',
            icon: '📄',
            message: '不支持的文件格式',
            suggestion: '仅支持 .geojson 和 .json 格式的文件。',
            solutions: ['将文件转换为 .geojson 或 .json']
        },
        interpolation_failed: {
            code: 'E-INTP-001',
            level: 'SEVERE',
            icon: '📉',
            message: '插值计算失败',
            suggestion: '可能是采样点分布不合理或参数设置有误，请尝试调整变异函数模型或网格分辨率。',
            solutions: ['增加采样点数量', '调整参数后重试']
        },
        insufficient_points: {
            code: 'E-POINT-002',
            level: 'INFO',
            icon: '➕',
            message: '采样点不足',
            suggestion: '克里金插值至少需要 3 个采样点，请继续添加采样数据。',
            solutions: ['至少添加 3 个采样点']
        },
        export_failed: {
            code: 'E-EXPORT-001',
            level: 'WARNING',
            icon: '📤',
            message: '导出失败',
            suggestion: '文件生成出错，请确认插值任务已完成后重试。',
            solutions: ['确认任务已完成', '点击重试重新导出'],
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
            code: fallback.code || ErrorHandler.ErrorCodes[errorType],
            level: fallback.level || ErrorHandler.ErrorLevels[errorType],
            icon: ErrorHandler._t(`error.${errorType}.icon`, fallback.icon || ''),
            message: ErrorHandler._t(`error.${errorType}.message`, fallback.message),
            suggestion: ErrorHandler._t(`error.${errorType}.suggestion`, fallback.suggestion || ''),
            retryable: fallback.retryable,
            helpLink: ErrorHandler._t(`error.${errorType}.helpLink`, fallback.helpLink || '')
        };

        const example = ErrorHandler._t(`error.${errorType}.example`, fallback.example || '');
        if (example) {
            detail.example = example;
        }

        if (fallback.solutions && fallback.solutions.length > 0) {
            detail.solutions = fallback.solutions.map((item, index) => ErrorHandler._t(`error.${errorType}.solutions.${index}`, item));
        }

        if (!detail.suggestion) {
            delete detail.suggestion;
        }
        if (!detail.helpLink) {
            delete detail.helpLink;
        }
        return detail;
    }

    static _errorLog: ErrorLogEntry[] = [];
    static _maxLogSize: number = 200;
    private static _stats: Map<string, ErrorStat> = new Map();
    private static _middlewares: ErrorMiddleware[] = [];
    private static _reporter: ((entries: ErrorLogEntry[]) => void) | null = null;

    static use(middleware: ErrorMiddleware): () => void {
        ErrorHandler._middlewares.push(middleware);
        return () => {
            ErrorHandler._middlewares = ErrorHandler._middlewares.filter((item) => item !== middleware);
        };
    }

    static setReporter(reporter: (entries: ErrorLogEntry[]) => void): void {
        ErrorHandler._reporter = reporter;
    }

    static uploadLogs(): void {
        if (ErrorHandler._errorLog.length === 0) {
            return;
        }

        if (ErrorHandler._reporter) {
            ErrorHandler._reporter(ErrorHandler.getErrorLog());
            return;
        }

        if (typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent('app:error:batch-upload', {
                detail: {
                    total: ErrorHandler._errorLog.length,
                    logs: ErrorHandler.getErrorLog(),
                    stats: ErrorHandler.getErrorStats()
                }
            }));
        }
    }

    static getErrorStats(): ErrorStat[] {
        return Array.from(ErrorHandler._stats.values()).sort((a, b) => b.count - a.count);
    }

    static clearErrorStats(): void {
        ErrorHandler._stats.clear();
    }

    static _log(errorType: ErrorType, message: string, context: Record<string, unknown> = {}): void {
        const now = new Date().toISOString();
        const key = String(errorType || 'unknown');
        const stat = ErrorHandler._stats.get(key);
        const nextCount = stat ? stat.count + 1 : 1;

        ErrorHandler._stats.set(key, {
            type: key,
            count: nextCount,
            lastSeenAt: now
        });

        const previous = [...ErrorHandler._errorLog].reverse().find((item) => item.type === errorType && item.message === message);

        const entry: ErrorLogEntry = {
            type: errorType,
            code: ErrorHandler.ErrorCodes[errorType as ErrorType] || undefined,
            level: ErrorHandler.ErrorLevels[errorType as ErrorType] || undefined,
            message,
            timestamp: now,
            firstSeenAt: previous?.firstSeenAt || now,
            lastSeenAt: now,
            count: nextCount,
            url: typeof window !== 'undefined' && window.location ? window.location.href : '',
            stack: context.stack ? String(context.stack) : undefined,
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

    private static _runMiddlewares(errorType: ErrorType, message: string, context: Record<string, unknown>): void {
        let index = -1;
        const dispatch = (current: number): void => {
            if (current <= index) return;
            index = current;

            if (current === ErrorHandler._middlewares.length) {
                ErrorHandler._log(errorType, message, context);
                return;
            }

            const middleware = ErrorHandler._middlewares[current];
            middleware(errorType, message, context, () => dispatch(current + 1));
        };

        dispatch(0);
    }

    static showError(errorType: ErrorType, customMessage: string | null = null, options: ShowErrorOptions = {}): void {
        const detail: ErrorDetail = ErrorHandler.getErrorDetail(errorType);
        const message: string = customMessage || detail.message || ErrorHandler._t('error.common.unknown', '未知错误');
        const suggestion: string = detail.suggestion || '';
        const retryable: boolean = detail.retryable || false;
        const example: string = detail.example || '';
        const icon = detail.icon || ErrorHandler._t('error.common.icon.error', '⚠️');

        const context = {
            suggestion,
            level: detail.level,
            code: detail.code,
            ...options.context
        };

        ErrorHandler._runMiddlewares(errorType, message, context);

        const defaultActions: ToastAction[] = [];
        if (retryable && options.onRetry) {
            defaultActions.push({
                key: 'retry',
                label: ErrorHandler._t('error.common.retryButton', '重试'),
                primary: true,
                onClick: options.onRetry
            });
        }
        if (detail.helpLink) {
            defaultActions.push({
                key: 'help',
                label: ErrorHandler._t('error.common.helpButton', '查看帮助'),
                onClick: () => {
                    if (typeof window !== 'undefined') {
                        window.dispatchEvent(new CustomEvent('app:error:help', {
                            detail: { errorType, helpLink: detail.helpLink }
                        }));
                    }
                }
            });
        }

        if (options.container) {
            ErrorHandler.showInContainer(message, 'error', options.container, suggestion);
        } else {
            ErrorHandler._showToast({
                message,
                suggestion,
                example,
                icon,
                details: options.details,
                actions: [...defaultActions, ...(options.actions || [])],
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
            ErrorHandler._showToast({
                message,
                icon: ErrorHandler._t('error.common.icon.success', '✅'),
                type: 'success',
                duration: 3000
            });
        }
    }

    static showWarning(message: string, container: HTMLElement | null = null): void {
        if (container) {
            ErrorHandler.showInContainer(message, 'warning', container);
        } else {
            ErrorHandler._showToast({
                message,
                icon: ErrorHandler._t('error.common.icon.warning', '⚠️'),
                type: 'warning',
                duration: 4000
            });
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

    static _showToast({ message, suggestion, example, icon, details, actions, type, retryable, onRetry, duration }: ToastOptions): void {
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
            maxWidth: '420px',
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

        let html: string = `<div style="font-weight:600;margin-bottom:4px;display:flex;gap:8px;align-items:flex-start"><span>${icon || ''}</span><span>${message}</span></div>`;
        if (suggestion) html += `<div style="font-size:12px;opacity:0.9">${suggestion}</div>`;

        if (details) {
            const detailLabel = ErrorHandler._t('error.common.detailsButton', '查看详情');
            html += `<button class="toast-detail-toggle" style="margin-top:8px;padding:4px 10px;border:1px solid rgba(255,255,255,0.5);border-radius:6px;background:transparent;color:white;font-size:12px;cursor:pointer">${detailLabel}</button>`;
            html += `<div class="toast-detail-panel" style="display:none;margin-top:8px;font-size:11px;opacity:0.9;white-space:pre-wrap">${details}</div>`;
        }

        if (example) {
            html += `<div style="font-size:11px;opacity:0.75;margin-top:4px;font-family:monospace">${example}</div>`;
        }

        const actionButtons: ToastAction[] = [...(actions || [])];
        if (retryable && onRetry) {
            actionButtons.push({
                key: 'retry',
                label: ErrorHandler._t('error.common.retryButton', '重试'),
                primary: true,
                onClick: onRetry
            });
        }

        if (actionButtons.length > 0) {
            html += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">';
            actionButtons.forEach((action, index) => {
                const background = action.primary ? 'rgba(255,255,255,0.2)' : 'transparent';
                html += `<button data-action-index="${index}" class="toast-action-btn" style="padding:4px 12px;border:1px solid rgba(255,255,255,0.5);border-radius:6px;background:${background};color:white;font-size:12px;cursor:pointer">${action.label}</button>`;
            });
            html += '</div>';
        }

        toast.innerHTML = html;

        document.body.appendChild(toast);

        if (details) {
            toast.querySelector('.toast-detail-toggle')?.addEventListener('click', () => {
                const panel = toast.querySelector('.toast-detail-panel') as HTMLElement | null;
                if (!panel) return;
                panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
            });
        }

        const actionNodes = typeof (toast as unknown as { querySelectorAll?: (selector: string) => unknown[] }).querySelectorAll === 'function'
            ? toast.querySelectorAll('.toast-action-btn')
            : [];

        Array.from(actionNodes || []).forEach((button, index) => {
            (button as HTMLElement).addEventListener?.('click', () => {
                toast.remove();
                actionButtons[index]?.onClick?.();
            });
        });

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

    static async runWithErrorBoundary<T>(task: () => Promise<T>, fallbackValue: T): Promise<T> {
        try {
            return await task();
        } catch (error) {
            const e = error as Error;
            ErrorHandler.showError('server_error', null, {
                details: e.stack || e.message,
                context: {
                    stack: e.stack,
                    source: 'runWithErrorBoundary'
                }
            });
            return fallbackValue;
        }
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

        ErrorHandler.showError(errorType, message, {
            details: `GeolocationErrorCode=${String(error.code)}`,
            context: {
                geoCode: error.code
            }
        });
        return { errorType, message };
    }

    static fromHttpStatus(status: number, context: string = ''): ErrorType {
        if (status >= 500) return 'server_error';
        if (status === 408) return 'timeout_error';
        if (status === 413) return 'file_too_large';
        if (status === 422) return 'validation_error';

        if (context) {
            ErrorHandler._runMiddlewares('network_error', `HTTP ${status} in ${context}`, { status, context });
        }
        return 'network_error';
    }
}
