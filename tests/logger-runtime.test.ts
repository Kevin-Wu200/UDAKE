import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Logger } from '../apps/frontend/js/utils/Logger';
import { RuntimeLifecycle } from '../apps/frontend/js/utils/RuntimeLifecycle';

describe('Logger', () => {
    let infoSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
        infoSpy = vi.spyOn(console, 'info').mockImplementation(() => undefined);
        Logger.setLevel('info');
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('应根据级别过滤日志', () => {
        Logger.setLevel('error');
        Logger.info('Test', '这条日志应被过滤');
        expect(infoSpy).not.toHaveBeenCalled();
    });

    it('应对敏感字段脱敏', () => {
        Logger.info('Test', '输出敏感字段', {
            token: 'secret-token',
            nested: {
                password: '123456'
            }
        });

        expect(infoSpy).toHaveBeenCalled();
        const payload = infoSpy.mock.calls[0][1] as Record<string, unknown>;
        expect(payload.token).toBe('[REDACTED]');
        expect((payload.nested as Record<string, unknown>).password).toBe('[REDACTED]');
    });
});

describe('RuntimeLifecycle', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('应清理作用域定时器与事件监听', () => {
        const scope = RuntimeLifecycle.createScope('test');
        const onInterval = vi.fn();
        const onClick = vi.fn();

        const div = document.createElement('div');
        scope.setInterval(onInterval, 100);
        scope.addEventListener(div, 'click', onClick);

        div.click();
        expect(onClick).toHaveBeenCalledTimes(1);

        vi.advanceTimersByTime(250);
        expect(onInterval).toHaveBeenCalledTimes(2);

        scope.cleanup();

        div.click();
        vi.advanceTimersByTime(300);

        expect(onClick).toHaveBeenCalledTimes(1);
        expect(onInterval).toHaveBeenCalledTimes(2);
    });
});
