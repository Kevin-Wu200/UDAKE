/**
 * 运行时资源生命周期管理
 * - 追踪定时器
 * - 追踪事件监听器
 * - 支持作用域化资源清理
 */

import { Logger } from './Logger';

type Listener = EventListenerOrEventListenerObject;

interface ListenerRecord {
    target: EventTarget;
    type: string;
    listener: Listener;
    options?: boolean | AddEventListenerOptions;
    capture: boolean;
}

function resolveCapture(options?: boolean | AddEventListenerOptions): boolean {
    if (typeof options === 'boolean') {
        return options;
    }
    return Boolean(options?.capture);
}

export interface LifecycleScope {
    setTimeout: (handler: TimerHandler, timeout?: number, ...args: unknown[]) => number;
    setInterval: (handler: TimerHandler, timeout?: number, ...args: unknown[]) => number;
    addEventListener: (
        target: EventTarget,
        type: string,
        listener: Listener,
        options?: boolean | AddEventListenerOptions
    ) => void;
    clearTimeout: (id: number) => void;
    clearInterval: (id: number) => void;
    cleanup: () => void;
}

export class RuntimeLifecycle {
    private static installed = false;
    private static timeoutIds: Set<number> = new Set();
    private static intervalIds: Set<number> = new Set();
    private static listeners: ListenerRecord[] = [];
    private static scopeId = 0;

    static installGlobalTracking(): void {
        if (this.installed) {
            return;
        }
        if (typeof window === 'undefined') {
            return;
        }

        this.installed = true;

        const originalSetTimeout = window.setTimeout.bind(window);
        const originalSetInterval = window.setInterval.bind(window);
        const originalClearTimeout = window.clearTimeout.bind(window);
        const originalClearInterval = window.clearInterval.bind(window);

        window.setTimeout = ((handler: TimerHandler, timeout?: number, ...args: unknown[]): number => {
            if (typeof handler !== 'function') {
                const id = originalSetTimeout(handler, timeout, ...args);
                this.timeoutIds.add(Number(id));
                return Number(id);
            }

            let timerId = 0;
            const wrapped = (...invokeArgs: unknown[]) => {
                this.timeoutIds.delete(timerId);
                (handler as (...params: unknown[]) => void)(...invokeArgs);
            };
            timerId = Number(originalSetTimeout(wrapped, timeout, ...args));
            this.timeoutIds.add(timerId);
            return timerId;
        }) as typeof window.setTimeout;

        window.setInterval = ((handler: TimerHandler, timeout?: number, ...args: unknown[]): number => {
            const id = Number(originalSetInterval(handler, timeout, ...args));
            this.intervalIds.add(id);
            return id;
        }) as typeof window.setInterval;

        window.clearTimeout = ((id?: number): void => {
            if (typeof id === 'number') {
                this.timeoutIds.delete(id);
            }
            originalClearTimeout(id);
        }) as typeof window.clearTimeout;

        window.clearInterval = ((id?: number): void => {
            if (typeof id === 'number') {
                this.intervalIds.delete(id);
            }
            originalClearInterval(id);
        }) as typeof window.clearInterval;

        const eventTargetPrototype = window.EventTarget?.prototype;
        if (eventTargetPrototype) {
            const originalAddEventListener = eventTargetPrototype.addEventListener;
            const originalRemoveEventListener = eventTargetPrototype.removeEventListener;

            eventTargetPrototype.addEventListener = function (
                type: string,
                listener: Listener,
                options?: boolean | AddEventListenerOptions
            ): void {
                if (listener) {
                    RuntimeLifecycle.listeners.push({
                        target: this,
                        type,
                        listener,
                        options,
                        capture: resolveCapture(options)
                    });
                }
                originalAddEventListener.call(this, type, listener, options);
            };

            eventTargetPrototype.removeEventListener = function (
                type: string,
                listener: Listener,
                options?: boolean | EventListenerOptions
            ): void {
                const capture = resolveCapture(options);
                RuntimeLifecycle.listeners = RuntimeLifecycle.listeners.filter(record => {
                    return !(
                        record.target === this
                        && record.type === type
                        && record.listener === listener
                        && record.capture === capture
                    );
                });
                originalRemoveEventListener.call(this, type, listener, options);
            };
        }

        window.addEventListener('beforeunload', () => {
            RuntimeLifecycle.cleanupAll();
        }, { once: true });

        Logger.info('RuntimeLifecycle', '全局资源追踪已启用');
    }

    static createScope(name: string): LifecycleScope {
        const scopeLabel = `${name}#${++this.scopeId}`;
        const timeoutIds = new Set<number>();
        const intervalIds = new Set<number>();
        const listenerRecords: ListenerRecord[] = [];

        return {
            setTimeout: (handler: TimerHandler, timeout?: number, ...args: unknown[]) => {
                const id = window.setTimeout(handler, timeout, ...args);
                timeoutIds.add(Number(id));
                return Number(id);
            },
            setInterval: (handler: TimerHandler, timeout?: number, ...args: unknown[]) => {
                const id = window.setInterval(handler, timeout, ...args);
                intervalIds.add(Number(id));
                return Number(id);
            },
            addEventListener: (
                target: EventTarget,
                type: string,
                listener: Listener,
                options?: boolean | AddEventListenerOptions
            ) => {
                target.addEventListener(type, listener, options);
                listenerRecords.push({
                    target,
                    type,
                    listener,
                    options,
                    capture: resolveCapture(options)
                });
            },
            clearTimeout: (id: number) => {
                timeoutIds.delete(id);
                window.clearTimeout(id);
            },
            clearInterval: (id: number) => {
                intervalIds.delete(id);
                window.clearInterval(id);
            },
            cleanup: () => {
                timeoutIds.forEach(id => window.clearTimeout(id));
                intervalIds.forEach(id => window.clearInterval(id));
                listenerRecords.forEach(record => {
                    record.target.removeEventListener(record.type, record.listener, record.options as boolean | EventListenerOptions);
                });
                timeoutIds.clear();
                intervalIds.clear();
                listenerRecords.length = 0;
                Logger.debug('RuntimeLifecycle', `作用域资源已清理: ${scopeLabel}`);
            }
        };
    }

    static cleanupAll(): void {
        this.timeoutIds.forEach(id => window.clearTimeout(id));
        this.intervalIds.forEach(id => window.clearInterval(id));

        const listeners = [...this.listeners];
        this.listeners = [];
        listeners.forEach(record => {
            record.target.removeEventListener(record.type, record.listener, record.options as boolean | EventListenerOptions);
        });

        this.timeoutIds.clear();
        this.intervalIds.clear();
        Logger.info('RuntimeLifecycle', '已执行全局资源清理');
    }

    static getSnapshot(): {
        timeouts: number;
        intervals: number;
        listeners: number;
    } {
        return {
            timeouts: this.timeoutIds.size,
            intervals: this.intervalIds.size,
            listeners: this.listeners.length
        };
    }
}
