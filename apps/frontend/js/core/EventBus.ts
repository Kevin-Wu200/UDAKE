/**
 * 事件总线
 * 用于插件和应用组件之间的事件通信
 */

import type { EventBus as EventBusInterface } from '../types/plugin';

/**
 * 事件监听器信息
 */
interface EventListener {
  handler: Function;
  once: boolean;
}

/**
 * 事件总线类
 */
export class EventBus implements EventBusInterface {
  private listeners: Map<string, EventListener[]> = new Map();
  private wildcardListeners: EventListener[] = [];
  private history: Map<string, any[]> = new Map();
  private historySize: number = 100;
  private enabled: boolean = true;

  /**
   * 监听事件
   * @param event 事件名称
   * @param handler 事件处理器
   * @returns 取消监听函数
   */
  on(event: string, handler: Function): () => void {
    if (!this.enabled) {
      console.warn('[EventBus] 事件总线已禁用，无法注册监听器');
      return () => {};
    }

    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }

    const listener: EventListener = {
      handler,
      once: false
    };

    this.listeners.get(event)!.push(listener);

    // 返回取消订阅函数
    return () => this.off(event, handler);
  }

  /**
   * 取消监听事件
   * @param event 事件名称
   * @param handler 事件处理器
   */
  off(event: string, handler: Function): void {
    const handlers = this.listeners.get(event);
    if (handlers) {
      const index = handlers.findIndex(l => l.handler === handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    }
  }

  /**
   * 发射事件
   * @param event 事件名称
   * @param data 事件数据
   */
  emit(event: string, data: any): void {
    if (!this.enabled) {
      console.warn('[EventBus] 事件总线已禁用，无法发射事件');
      return;
    }

    // 保存历史记录
    this.saveToHistory(event, data);

    // 执行特定事件的监听器
    const handlers = this.listeners.get(event);
    if (handlers) {
      const toRemove: number[] = [];

      handlers.forEach((listener, index) => {
        try {
          listener.handler(data);

          if (listener.once) {
            toRemove.push(index);
          }
        } catch (error) {
          console.error(`[EventBus] 事件处理器错误 (${event}):`, error);
        }
      });

      // 移除一次性监听器
      toRemove.reverse().forEach(index => {
        handlers.splice(index, 1);
      });
    }

    // 执行通配符监听器
    this.wildcardListeners.forEach(listener => {
      try {
        listener.handler({ event, data });
      } catch (error) {
        console.error(`[EventBus] 通配符监听器错误 (${event}):`, error);
      }
    });
  }

  /**
   * 监听一次性事件
   * @param event 事件名称
   * @param handler 事件处理器
   */
  once(event: string, handler: Function): void {
    if (!this.enabled) {
      console.warn('[EventBus] 事件总线已禁用，无法注册监听器');
      return;
    }

    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }

    const listener: EventListener = {
      handler,
      once: true
    };

    this.listeners.get(event)!.push(listener);
  }

  /**
   * 监听所有事件（通配符）
   * @param handler 事件处理器
   * @returns 取消监听函数
   */
  onAny(handler: Function): () => void {
    if (!this.enabled) {
      console.warn('[EventBus] 事件总线已禁用，无法注册监听器');
      return () => {};
    }

    const listener: EventListener = {
      handler,
      once: false
    };

    this.wildcardListeners.push(listener);

    return () => {
      const index = this.wildcardListeners.indexOf(listener);
      if (index > -1) {
        this.wildcardListeners.splice(index, 1);
      }
    };
  }

  /**
   * 移除特定事件的所有监听器
   * @param event 事件名称
   */
  removeAllListeners(event?: string): void {
    if (event) {
      this.listeners.delete(event);
    } else {
      this.listeners.clear();
      this.wildcardListeners = [];
    }
  }

  /**
   * 清除所有监听器
   */
  clear(): void {
    this.listeners.clear();
    this.wildcardListeners = [];
    this.history.clear();
  }

  /**
   * 获取事件的历史记录
   * @param event 事件名称
   * @returns 历史记录
   */
  getHistory(event: string): any[] {
    return this.history.get(event) || [];
  }

  /**
   * 获取所有事件的历史记录
   * @returns 所有历史记录
   */
  getAllHistory(): Map<string, any[]> {
    return new Map(this.history);
  }

  /**
   * 清除历史记录
   * @param event 事件名称（可选）
   */
  clearHistory(event?: string): void {
    if (event) {
      this.history.delete(event);
    } else {
      this.history.clear();
    }
  }

  /**
   * 获取事件的监听器数量
   * @param event 事件名称
   * @returns 监听器数量
   */
  listenerCount(event: string): number {
    return this.listeners.get(event)?.length || 0;
  }

  /**
   * 获取所有事件名称
   * @returns 事件名称列表
   */
  eventNames(): string[] {
    return Array.from(this.listeners.keys());
  }

  /**
   * 启用事件总线
   */
  enable(): void {
    this.enabled = true;
    console.log('[EventBus] 事件总线已启用');
  }

  /**
   * 禁用事件总线
   */
  disable(): void {
    this.enabled = false;
    console.log('[EventBus] 事件总线已禁用');
  }

  /**
   * 检查事件总线是否启用
   * @returns 是否启用
   */
  isEnabled(): boolean {
    return this.enabled;
  }

  /**
   * 设置历史记录大小
   * @param size 历史记录大小
   */
  setHistorySize(size: number): void {
    this.historySize = size;
  }

  /**
   * 保存事件到历史记录
   * @param event 事件名称
   * @param data 事件数据
   */
  private saveToHistory(event: string, data: any): void {
    if (!this.history.has(event)) {
      this.history.set(event, []);
    }

    const eventHistory = this.history.get(event)!;
    eventHistory.push({
      data,
      timestamp: new Date()
    });

    // 限制历史记录大小
    if (eventHistory.length > this.historySize) {
      eventHistory.shift();
    }
  }

  /**
   * 等待事件触发
   * @param event 事件名称
   * @param timeout 超时时间（毫秒）
   * @returns Promise，在事件触发时resolve
   */
  waitFor(event: string, timeout: number = 5000): Promise<any> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.off(event, handler);
        reject(new Error(`等待事件 ${event} 超时`));
      }, timeout);

      const handler = (data: any) => {
        clearTimeout(timer);
        resolve(data);
      };

      this.once(event, handler);
    });
  }

  /**
   * 批量发射事件
   * @param events 事件列表
   */
  emitBatch(events: Array<{ event: string; data: any }>): void {
    events.forEach(({ event, data }) => {
      this.emit(event, data);
    });
  }

  /**
   * 获取事件总线统计信息
   * @returns 统计信息
   */
  getStats(): {
    eventCount: number;
    totalListeners: number;
    wildcardListeners: number;
    historySize: number;
    enabled: boolean;
  } {
    let totalListeners = 0;

    this.listeners.forEach(handlers => {
      totalListeners += handlers.length;
    });

    return {
      eventCount: this.listeners.size,
      totalListeners,
      wildcardListeners: this.wildcardListeners.length,
      historySize: this.history.size,
      enabled: this.enabled
    };
  }
}