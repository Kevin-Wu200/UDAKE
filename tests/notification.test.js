import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { NotificationManager } from '../apps/frontend/js/components/NotificationManager.ts';

class MockBrowserNotification {
    static instances = [];
    static permission = 'granted';
    static requestPermission = vi.fn(async () => 'granted');

    constructor(title, options) {
        this.title = title;
        this.options = options;
        this.onclick = null;
        this.onclose = null;
        MockBrowserNotification.instances.push(this);
    }

    close() {}
}

describe('NotificationManager 优先级队列', () => {
    let manager;

    beforeEach(() => {
        vi.useFakeTimers();

        Object.defineProperty(globalThis, 'Notification', {
            configurable: true,
            writable: true,
            value: MockBrowserNotification,
        });

        Object.defineProperty(globalThis, 'localStorage', {
            configurable: true,
            writable: true,
            value: {
                getItem: vi.fn(() => null),
                setItem: vi.fn(),
                removeItem: vi.fn(),
            },
        });

        if (!globalThis.navigator) {
            Object.defineProperty(globalThis, 'navigator', {
                configurable: true,
                writable: true,
                value: {},
            });
        }

        globalThis.navigator.vibrate = vi.fn();
        MockBrowserNotification.instances = [];

        manager = new NotificationManager();
        manager.updateSettings({ sound: false, vibration: false });
        manager.permission = 'granted';
    });

    afterEach(() => {
        manager.destroy();
        vi.useRealTimers();
        vi.restoreAllMocks();
    });

    it('紧急通知应立即显示，不等待队列', () => {
        const received = [];
        manager.on('notification', (notif) => received.push(notif.title));

        manager.show({
            type: 'taskSuccess',
            title: '普通通知',
            body: '普通消息',
            priority: 'normal',
        });

        manager.show({
            type: 'networkError',
            title: '紧急通知',
            body: '网络断开',
            priority: 'urgent',
        });

        expect(received).toEqual(['紧急通知']);
        vi.runAllTimers();
        expect(received).toEqual(['紧急通知', '普通通知']);
    });

    it('队列应按优先级发送而非 FIFO', () => {
        const received = [];
        manager.on('notification', (notif) => received.push(notif.title));

        manager.show({
            type: 'taskSuccess',
            title: '低优先级',
            body: '低',
            priority: 'low',
        });

        manager.show({
            type: 'taskFailure',
            title: '高优先级',
            body: '高',
            priority: 'high',
        });

        manager.show({
            type: 'uploadError',
            title: '普通优先级',
            body: '中',
            priority: 'normal',
        });

        vi.runAllTimers();
        expect(received).toEqual(['高优先级', '普通优先级', '低优先级']);
    });

    it('重复通知应合并去重', () => {
        const received = [];
        manager.on('notification', (notif) => received.push(notif));

        manager.show({
            type: 'taskFailure',
            title: '任务失败',
            body: '任务 A 失败',
            priority: 'high',
        });

        manager.show({
            type: 'taskFailure',
            title: '任务失败',
            body: '任务 A 失败',
            priority: 'high',
        });

        vi.runAllTimers();

        expect(received).toHaveLength(1);
        expect(received[0].mergeCount).toBe(2);
        expect(received[0].body).toContain('合并 2 条');

        const history = manager.getNotificationHistory(10);
        expect(history).toHaveLength(1);
    });
});
