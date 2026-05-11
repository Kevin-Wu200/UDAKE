/**
 * 事件绑定器
 * 统一管理应用中的所有事件绑定和解绑，防止内存泄漏
 */

export interface EventHandler {
    target: EventTarget;
    type: string;
    handler: EventListenerOrEventListenerObject;
    options?: AddEventListenerOptions | boolean;
}

export interface EventGroup {
    name: string;
    handlers: EventHandler[];
}

export class EventBinder {
    private eventHandlers: Map<string, EventHandler[]> = new Map();
    private eventGroups: Map<string, EventGroup> = new Map();
    private static instance: EventBinder | null = null;

    private constructor() {}

    /**
     * 获取单例实例
     */
    public static getInstance(): EventBinder {
        if (!EventBinder.instance) {
            EventBinder.instance = new EventBinder();
        }
        return EventBinder.instance;
    }

    /**
     * 绑定DOM事件
     */
    public bind(
        target: EventTarget,
        type: string,
        handler: EventListenerOrEventListenerObject,
        options?: AddEventListenerOptions | boolean
    ): void {
        target.addEventListener(type, handler, options);

        const eventHandler: EventHandler = {
            target,
            type,
            handler,
            options
        };

        this.trackHandler(eventHandler);
    }

    /**
     * 绑定DOM事件（使用选择器）
     */
    public bindBySelector(
        selector: string,
        type: string,
        handler: EventListenerOrEventListenerObject,
        options?: AddEventListenerOptions | boolean,
        retryCount: number = 3
    ): void {
        const element = document.querySelector(selector);
        if (element) {
            this.bind(element, type, handler, options);
        } else if (retryCount > 0) {
            console.debug(`[EventBinder] 元素 ${selector} 尚未就绪，剩余重试次数: ${retryCount}`);
            setTimeout(() => {
                this.bindBySelector(selector, type, handler, options, retryCount - 1);
            }, 500);
        } else {
            console.warn(`[EventBinder] 达到最大重试次数，未找到元素: ${selector}。尝试使用 MutationObserver 监听...`);
            this.observeAndBind(selector, type, handler, options);
        }
    }

    /**
     * 使用 MutationObserver 监听 DOM 并在元素出现时绑定
     */
    private observeAndBind(
        selector: string,
        type: string,
        handler: EventListenerOrEventListenerObject,
        options?: AddEventListenerOptions | boolean
    ): void {
        // 先检查一次，防止在创建观察者期间元素已经出现
        const element = document.querySelector(selector);
        if (element) {
            this.bind(element, type, handler, options);
            return;
        }

        const observer = new MutationObserver((mutations, obs) => {
            const el = document.querySelector(selector);
            if (el) {
                this.bind(el, type, handler, options);
                obs.disconnect();
                console.log(`[EventBinder] 通过 MutationObserver 成功绑定元素: ${selector}`);
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        // 15秒后停止监听，避免无限监听占用资源
        setTimeout(() => observer.disconnect(), 15000);
    }

    /**
     * 绑定多个DOM事件（使用选择器）
     */
    public bindAllBySelector(
        selector: string,
        type: string,
        handler: EventListenerOrEventListenerObject,
        options?: AddEventListenerOptions | boolean
    ): void {
        const elements = document.querySelectorAll(selector);
        elements.forEach(element => {
            this.bind(element, type, handler, options);
        });
    }

    /**
     * 绑定全局事件
     */
    public bindGlobal(
        type: string,
        handler: EventListenerOrEventListenerObject,
        options?: AddEventListenerOptions | boolean
    ): void {
        this.bind(window, type, handler, options);
    }

    /**
     * 绑定文档事件
     */
    public bindDocument(
        type: string,
        handler: EventListenerOrEventListenerObject,
        options?: AddEventListenerOptions | boolean
    ): void {
        this.bind(document, type, handler, options);
    }

    /**
     * 创建事件组
     */
    public createGroup(name: string): void {
        if (this.eventGroups.has(name)) {
            console.warn(`[EventBinder] 事件组 ${name} 已存在`);
            return;
        }

        this.eventGroups.set(name, {
            name,
            handlers: []
        });
    }

    /**
     * 绑定到事件组
     */
    public bindToGroup(
        groupName: string,
        target: EventTarget,
        type: string,
        handler: EventListenerOrEventListenerObject,
        options?: AddEventListenerOptions | boolean
    ): void {
        if (!this.eventGroups.has(groupName)) {
            this.createGroup(groupName);
        }

        target.addEventListener(type, handler, options);

        const eventHandler: EventHandler = {
            target,
            type,
            handler,
            options
        };

        const group = this.eventGroups.get(groupName)!;
        group.handlers.push(eventHandler);
        this.trackHandler(eventHandler);
    }

    /**
     * 解绑单个事件
     */
    public unbind(
        target: EventTarget,
        type: string,
        handler: EventListenerOrEventListenerObject,
        options?: AddEventListenerOptions | boolean
    ): void {
        target.removeEventListener(type, handler, options);
        this.removeHandler(target, type, handler);
    }

    /**
     * 解绑DOM事件（使用选择器）
     */
    public unbindBySelector(
        selector: string,
        type: string,
        handler: EventListenerOrEventListenerObject,
        options?: AddEventListenerOptions | boolean
    ): void {
        const element = document.querySelector(selector);
        if (element) {
            this.unbind(element, type, handler, options);
        }
    }

    /**
     * 解绑目标上的所有指定类型事件
     */
    public unbindAll(target: EventTarget, type: string): void {
        const handlers = this.getHandlers(target, type);
        handlers.forEach(h => {
            target.removeEventListener(type, h.handler, h.options);
        });
        this.removeAllHandlers(target, type);
    }

    /**
     * 解绑全局事件
     */
    public unbindGlobal(type: string, handler: EventListenerOrEventListenerObject): void {
        this.unbind(window, type, handler);
    }

    /**
     * 解绑文档事件
     */
    public unbindDocument(type: string, handler: EventListenerOrEventListenerObject): void {
        this.unbind(document, type, handler);
    }

    /**
     * 解绑事件组中的所有事件
     */
    public unbindGroup(groupName: string): void {
        const group = this.eventGroups.get(groupName);
        if (!group) {
            console.warn(`[EventBinder] 事件组 ${groupName} 不存在`);
            return;
        }

        group.handlers.forEach(h => {
            h.target.removeEventListener(h.type, h.handler, h.options);
        });

        // 从全局处理器中移除
        group.handlers.forEach(h => {
            this.removeHandler(h.target, h.type, h.handler);
        });

        // 清空组
        group.handlers = [];
    }

    /**
     * 解绑所有事件
     */
    public unbindAllEvents(): void {
        this.eventHandlers.forEach((handlers, key) => {
            handlers.forEach(h => {
                h.target.removeEventListener(h.type, h.handler, h.options);
            });
        });

        this.eventHandlers.clear();
        this.eventGroups.clear();
    }

    /**
     * 跟踪事件处理器
     */
    private trackHandler(handler: EventHandler): void {
        const key = this.getHandlerKey(handler.target, handler.type);
        if (!this.eventHandlers.has(key)) {
            this.eventHandlers.set(key, []);
        }
        this.eventHandlers.get(key)!.push(handler);
    }

    /**
     * 移除事件处理器
     */
    private removeHandler(target: EventTarget, type: string, handler: EventListenerOrEventListenerObject): void {
        const key = this.getHandlerKey(target, type);
        const handlers = this.eventHandlers.get(key);
        if (handlers) {
            const index = handlers.findIndex(h => h.handler === handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
            if (handlers.length === 0) {
                this.eventHandlers.delete(key);
            }
        }
    }

    /**
     * 获取事件处理器
     */
    private getHandlers(target: EventTarget, type: string): EventHandler[] {
        const key = this.getHandlerKey(target, type);
        return this.eventHandlers.get(key) || [];
    }

    /**
     * 移除所有事件处理器
     */
    private removeAllHandlers(target: EventTarget, type: string): void {
        const key = this.getHandlerKey(target, type);
        this.eventHandlers.delete(key);
    }

    /**
     * 获取处理器键
     */
    private getHandlerKey(target: EventTarget, type: string): string {
        if (target === window) {
            return `window:${type}`;
        } else if (target === document) {
            return `document:${type}`;
        } else {
            return `${(target as HTMLElement).id || (target as HTMLElement).className || 'unknown'}:${type}`;
        }
    }

    /**
     * 获取事件统计信息
     */
    public getStats(): { total: number; byType: Map<string, number>; byTarget: Map<string, number> } {
        const stats = {
            total: 0,
            byType: new Map<string, number>(),
            byTarget: new Map<string, number>()
        };

        this.eventHandlers.forEach((handlers, key) => {
            stats.total += handlers.length;

            const [targetKey, type] = key.split(':');
            stats.byType.set(type, (stats.byType.get(type) || 0) + handlers.length);
            stats.byTarget.set(targetKey, (stats.byTarget.get(targetKey) || 0) + handlers.length);
        });

        return stats;
    }

    /**
     * 清理事件绑定器
     */
    public destroy(): void {
        this.unbindAllEvents();
        EventBinder.instance = null;
    }
}

/**
 * 创建事件绑定器实例
 */
export function createEventBinder(): EventBinder {
    return EventBinder.getInstance();
}