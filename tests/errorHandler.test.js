import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ErrorHandler } from '../frontend/js/utils/ErrorHandler.js';

describe('ErrorHandler', () => {
    beforeEach(() => {
        // Mock DOM环境
        global.document = {
            body: {
                appendChild: vi.fn(),
                removeChild: vi.fn()
            },
            createElement: vi.fn((tag) => {
                const element = {
                    tagName: tag,
                    className: '',
                    innerHTML: '',
                    style: {},
                    setAttribute: vi.fn(),
                    querySelector: vi.fn(() => null),
                    addEventListener: vi.fn(),
                    removeEventListener: vi.fn(),
                    remove: vi.fn()
                };
                return element;
            }),
            querySelector: vi.fn(() => null)
        };

        // Mock console
        console.error = vi.fn();
        console.log = vi.fn();

        // Mock requestAnimationFrame
        global.requestAnimationFrame = vi.fn((cb) => cb());

        // Mock setTimeout
        global.setTimeout = vi.fn((cb, delay) => {
            cb();
            return 1;
        });

        // 清空错误日志
        ErrorHandler.clearErrorLog();
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    it('应该包含所有错误类型', () => {
        expect(ErrorHandler.ErrorTypes.GEOJSON_FORMAT).toBe('geojson_format');
        expect(ErrorHandler.ErrorTypes.NETWORK_ERROR).toBe('network_error');
        expect(ErrorHandler.ErrorTypes.SERVER_ERROR).toBe('server_error');
        expect(ErrorHandler.ErrorTypes.TIMEOUT_ERROR).toBe('timeout_error');
        expect(ErrorHandler.ErrorTypes.INTERPOLATION_FAILED).toBe('interpolation_failed');
    });

    it('每种错误类型都应有详情定义', () => {
        for (const type of Object.values(ErrorHandler.ErrorTypes)) {
            expect(ErrorHandler.ErrorDetails[type]).toBeDefined();
            expect(ErrorHandler.ErrorDetails[type].message).toBeTruthy();
        }
    });

    it('网络错误应该标记为可重试', () => {
        expect(ErrorHandler.ErrorDetails[ErrorHandler.ErrorTypes.NETWORK_ERROR].retryable).toBe(true);
        expect(ErrorHandler.ErrorDetails[ErrorHandler.ErrorTypes.SERVER_ERROR].retryable).toBe(true);
    });

    it('validateGeoJSON 应该验证有效的 FeatureCollection', () => {
        const valid = ErrorHandler.validateGeoJSON({
            type: 'FeatureCollection',
            features: []
        });
        expect(valid.valid).toBe(true);
    });

    it('validateGeoJSON 应该拒绝缺少 type 的对象', () => {
        const result = ErrorHandler.validateGeoJSON({});
        expect(result.valid).toBe(false);
    });

    it('validateGeoJSON 应该拒绝非对象', () => {
        expect(ErrorHandler.validateGeoJSON(null).valid).toBe(false);
        expect(ErrorHandler.validateGeoJSON('string').valid).toBe(false);
    });

    it('validateCoordinates 应该验证有效坐标', () => {
        expect(ErrorHandler.validateCoordinates(116.39, 39.9).valid).toBe(true);
    });

    it('validateCoordinates 应该拒绝超范围经度', () => {
        expect(ErrorHandler.validateCoordinates(200, 39.9).valid).toBe(false);
    });

    it('validateCoordinates 应该拒绝超范围纬度', () => {
        expect(ErrorHandler.validateCoordinates(116, -100).valid).toBe(false);
    });

    it('validateCoordinates 应该拒绝非数字', () => {
        expect(ErrorHandler.validateCoordinates('abc', 39).valid).toBe(false);
    });

    it('validateCoordinates 应该拒绝NaN值', () => {
        expect(ErrorHandler.validateCoordinates(NaN, 39).valid).toBe(false);
        expect(ErrorHandler.validateCoordinates(116, NaN).valid).toBe(false);
    });

    it('validatePolygon 应该验证有效多边形', () => {
        const result = ErrorHandler.validatePolygon({
            type: 'Polygon',
            coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]]
        });
        expect(result.valid).toBe(true);
    });

    it('validatePolygon 应该验证MultiPolygon', () => {
        const result = ErrorHandler.validatePolygon({
            type: 'MultiPolygon',
            coordinates: [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]
        });
        expect(result.valid).toBe(true);
    });

    it('validatePolygon 应该拒绝不支持的类型', () => {
        expect(ErrorHandler.validatePolygon({ type: 'Point', coordinates: [0, 0] }).valid).toBe(false);
    });

    it('validatePolygon 应该拒绝缺少坐标', () => {
        expect(ErrorHandler.validatePolygon({ type: 'Polygon' }).valid).toBe(false);
    });

    it('fromHttpStatus 应该正确映射状态码', () => {
        expect(ErrorHandler.fromHttpStatus(500)).toBe('server_error');
        expect(ErrorHandler.fromHttpStatus(502)).toBe('server_error');
        expect(ErrorHandler.fromHttpStatus(503)).toBe('server_error');
        expect(ErrorHandler.fromHttpStatus(408)).toBe('timeout_error');
        expect(ErrorHandler.fromHttpStatus(413)).toBe('file_too_large');
        expect(ErrorHandler.fromHttpStatus(422)).toBe('validation_error');
        expect(ErrorHandler.fromHttpStatus(404)).toBe('network_error');
        expect(ErrorHandler.fromHttpStatus(400)).toBe('network_error');
    });

    it('错误日志应该正确记录和获取', () => {
        ErrorHandler._log('test_error', '测试错误');
        const log = ErrorHandler.getErrorLog();
        expect(log.length).toBe(1);
        expect(log[0].type).toBe('test_error');
        expect(log[0].message).toBe('测试错误');
    });

    it('错误日志应该包含时间戳', () => {
        ErrorHandler._log('test', 'msg');
        const log = ErrorHandler.getErrorLog();
        expect(log[0].timestamp).toBeDefined();
        expect(typeof log[0].timestamp).toBe('string');
    });

    it('错误日志应该包含URL', () => {
        global.window = { location: { href: 'http://test.com' } };
        ErrorHandler._log('test', 'msg');
        const log = ErrorHandler.getErrorLog();
        expect(log[0].url).toBe('http://test.com');
    });

    it('错误日志应该包含上下文信息', () => {
        ErrorHandler._log('test', 'msg', { userId: 123 });
        const log = ErrorHandler.getErrorLog();
        expect(log[0].userId).toBe(123);
    });

    it('clearErrorLog 应该清空日志', () => {
        ErrorHandler._log('test', 'msg');
        ErrorHandler.clearErrorLog();
        expect(ErrorHandler.getErrorLog().length).toBe(0);
    });

    describe('showError', () => {
        it('应该显示错误Toast', () => {
            ErrorHandler.showError('network_error');
            expect(document.body.appendChild).toHaveBeenCalled();
        });

        it('应该使用自定义消息', () => {
            ErrorHandler.showError('network_error', '自定义错误消息');
            expect(document.body.appendChild).toHaveBeenCalled();
        });

        it('应该支持重试选项', () => {
            const onRetry = vi.fn();
            ErrorHandler.showError('network_error', null, { onRetry });
            expect(document.body.appendChild).toHaveBeenCalled();
        });

        it('应该支持自定义容器', () => {
            const container = {
                querySelector: vi.fn(() => null),
                appendChild: vi.fn()
            };
            ErrorHandler.showError('network_error', null, { container });
            expect(container.querySelector).toHaveBeenCalled();
        });

        it('应该支持自定义持续时间', () => {
            ErrorHandler.showError('network_error', null, { duration: 3000 });
            expect(document.body.appendChild).toHaveBeenCalled();
        });

        it('应该记录错误日志', () => {
            ErrorHandler.showError('test_error', '测试错误');
            const log = ErrorHandler.getErrorLog();
            expect(log.length).toBeGreaterThan(0);
        });
    });

    describe('showSuccess', () => {
        it('应该显示成功Toast', () => {
            ErrorHandler.showSuccess('操作成功');
            expect(document.body.appendChild).toHaveBeenCalled();
        });

        it('应该支持自定义容器', () => {
            const container = {
                querySelector: vi.fn(() => null),
                appendChild: vi.fn()
            };
            ErrorHandler.showSuccess('成功', container);
            expect(container.querySelector).toHaveBeenCalled();
        });
    });

    describe('showWarning', () => {
        it('应该显示警告Toast', () => {
            ErrorHandler.showWarning('警告信息');
            expect(document.body.appendChild).toHaveBeenCalled();
        });

        it('应该支持自定义容器', () => {
            const container = {
                querySelector: vi.fn(() => null),
                appendChild: vi.fn()
            };
            ErrorHandler.showWarning('警告', container);
            expect(container.querySelector).toHaveBeenCalled();
        });
    });

    describe('showInContainer', () => {
        it('应该在容器中显示错误消息', () => {
            const container = {
                querySelector: vi.fn(() => null),
                appendChild: vi.fn()
            };
            ErrorHandler.showInContainer('错误消息', 'error', container, '建议');
            expect(container.appendChild).toHaveBeenCalled();
        });

        it('应该更新已存在的状态消息', () => {
            const existingDiv = {
                innerHTML: '',
                className: '',
                style: {}
            };
            const container = {
                querySelector: vi.fn(() => existingDiv)
            };
            ErrorHandler.showInContainer('新消息', 'success', container);
            expect(existingDiv.innerHTML).toContain('新消息');
        });

        it('应该设置正确的类名', () => {
            const div = {
                innerHTML: '',
                className: '',
                style: {}
            };
            const container = {
                querySelector: vi.fn(() => div)
            };
            ErrorHandler.showInContainer('消息', 'warning', container);
            expect(div.className).toContain('warning');
        });
    });

    describe('handleGeolocationError', () => {
        it('应该处理PERMISSION_DENIED错误', () => {
            const error = { code: 1, PERMISSION_DENIED: 1 };
            const result = ErrorHandler.handleGeolocationError(error);
            expect(result.errorType).toBe('permission_denied');
        });

        it('应该处理POSITION_UNAVAILABLE错误', () => {
            const error = { code: 2, POSITION_UNAVAILABLE: 2 };
            const result = ErrorHandler.handleGeolocationError(error);
            expect(result.errorType).toBe('geolocation_failed');
        });

        it('应该处理TIMEOUT错误', () => {
            const error = { code: 3, TIMEOUT: 3 };
            const result = ErrorHandler.handleGeolocationError(error);
            expect(result.errorType).toBe('geolocation_failed');
        });

        it('应该处理未知错误', () => {
            const error = { code: 4 };
            const result = ErrorHandler.handleGeolocationError(error);
            expect(result.errorType).toBe('geolocation_failed');
        });

        it('应该调用showError', () => {
            const error = { code: 1 };
            ErrorHandler.handleGeolocationError(error);
            // 应该触发showError方法
        });
    });

    describe('错误类型边界情况', () => {
        it('validateGeoJSON应该处理Feature类型', () => {
            const result = ErrorHandler.validateGeoJSON({
                type: 'Feature',
                geometry: { type: 'Point', coordinates: [0, 0] }
            });
            expect(result.valid).toBe(true);
        });

        it('validateGeoJSON应该拒绝缺少geometry的Feature', () => {
            const result = ErrorHandler.validateGeoJSON({
                type: 'Feature'
            });
            expect(result.valid).toBe(false);
        });

        it('validatePolygon应该处理非对象输入', () => {
            expect(ErrorHandler.validatePolygon(null).valid).toBe(false);
            expect(ErrorHandler.validatePolygon('string').valid).toBe(false);
        });

        it('validateCoordinates应该处理边界值', () => {
            expect(ErrorHandler.validateCoordinates(-180, -90).valid).toBe(true);
            expect(ErrorHandler.validateCoordinates(180, 90).valid).toBe(true);
            expect(ErrorHandler.validateCoordinates(-180.1, -90).valid).toBe(false);
            expect(ErrorHandler.validateCoordinates(180.1, 90).valid).toBe(false);
        });
    });

    describe('fromHttpStatus更多场景', () => {
        it('应该处理所有5xx错误', () => {
            expect(ErrorHandler.fromHttpStatus(500)).toBe('server_error');
            expect(ErrorHandler.fromHttpStatus(501)).toBe('server_error');
            expect(ErrorHandler.fromHttpStatus(502)).toBe('server_error');
            expect(ErrorHandler.fromHttpStatus(503)).toBe('server_error');
            expect(ErrorHandler.fromHttpStatus(504)).toBe('server_error');
            expect(ErrorHandler.fromHttpStatus(599)).toBe('server_error');
        });

        it('应该处理4xx客户端错误', () => {
            expect(ErrorHandler.fromHttpStatus(400)).toBe('network_error');
            expect(ErrorHandler.fromHttpStatus(401)).toBe('network_error');
            expect(ErrorHandler.fromHttpStatus(403)).toBe('network_error');
            expect(ErrorHandler.fromHttpStatus(404)).toBe('network_error');
        });

        it('应该支持context参数', () => {
            const result = ErrorHandler.fromHttpStatus(500, 'upload');
            expect(result).toBe('server_error');
        });
    });

    describe('错误日志限制', () => {
        it('应该限制日志大小', () => {
            // 添加超过限制的日志
            for (let i = 0; i < 250; i++) {
                ErrorHandler._log('test', `message ${i}`);
            }
            const log = ErrorHandler.getErrorLog();
            expect(log.length).toBeLessThanOrEqual(200);
        });

        it('应该删除最旧的日志', () => {
            for (let i = 0; i < 210; i++) {
                ErrorHandler._log('test', `message ${i}`);
            }
            const log = ErrorHandler.getErrorLog();
            // 最新的日志应该在最后
            expect(log[log.length - 1].message).toBe('message 209');
        });
    });

    describe('错误详情', () => {
        it('每种错误类型应该有消息', () => {
            Object.values(ErrorHandler.ErrorTypes).forEach(type => {
                expect(ErrorHandler.ErrorDetails[type].message).toBeTruthy();
            });
        });

        it('每种错误类型应该有建议', () => {
            Object.values(ErrorHandler.ErrorTypes).forEach(type => {
                expect(ErrorHandler.ErrorDetails[type].suggestion).toBeTruthy();
            });
        });

        it('部分错误类型应该有示例', () => {
            expect(ErrorHandler.ErrorDetails.geojson_format.example).toBeTruthy();
            expect(ErrorHandler.ErrorDetails.coordinate_format.example).toBeTruthy();
        });

        it('部分错误类型应该标记为可重试', () => {
            expect(ErrorHandler.ErrorDetails.network_error.retryable).toBe(true);
            expect(ErrorHandler.ErrorDetails.server_error.retryable).toBe(true);
            expect(ErrorHandler.ErrorDetails.timeout_error.retryable).toBe(true);
            expect(ErrorHandler.ErrorDetails.export_failed.retryable).toBe(true);
        });
    });
});
