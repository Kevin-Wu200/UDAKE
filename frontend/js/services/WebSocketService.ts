import { io, Socket } from 'socket.io-client';

export interface WebSocketMessage {
  type: string;
  data?: any;
  timestamp: string;
}

export interface TaskUpdateMessage extends WebSocketMessage {
  type: 'task_update';
  task_id: string;
  data: {
    status: string;
    progress: number;
    result?: any;
    error?: any;
  };
}

export class WebSocketService {
  private socket: Socket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 3000; // 3秒
  private messageHandlers: Map<string, Function[]> = new Map();
  private isConnected = false;
  private errorHandlers: Function[] = [];
  private pendingMessages: Map<string, {
    message: WebSocketMessage;
    resolve: Function;
    reject: Function;
    timeout: NodeJS.Timeout;
  }> = new Map();
  private messageId = 0;
  private messageQueue: WebSocketMessage[] = [];
  private batchTimer: NodeJS.Timeout | null = null;
  private batchSize = 10;
  private batchDelay = 100; // 100ms

  constructor(private url: string) {}

  connect(clientId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.socket = io(this.url, {
          query: { client_id: clientId },
          transports: ['websocket', 'polling'],
          reconnection: true,
          reconnectionDelay: this.reconnectDelay,
          reconnectionAttempts: this.maxReconnectAttempts
        });

        this.socket.on('connect', () => {
          console.log('WebSocket 已连接');
          this.isConnected = true;
          this.reconnectAttempts = 0;
          resolve();
        });

        this.socket.on('disconnect', (reason) => {
          console.log('WebSocket 已断开:', reason);
          this.isConnected = false;
          this.handleDisconnect(reason);
        });

        this.socket.on('connect_error', (error) => {
          console.error('WebSocket 连接错误:', error);
          this.handleConnectError(error);
        });

        this.socket.on('message', (message: WebSocketMessage) => {
          this.handleMessage(message);
        });

        // 监听心跳
        this.socket.on('ping', () => {
          this.socket?.emit('pong');
        });

      } catch (error) {
        reject(error);
      }
    });
  }

  private handleDisconnect(reason: string): void {
    if (reason === 'io server disconnect') {
      // 服务器主动断开，需要手动重连
      this.reconnect();
    }
    // 其他情况会自动重连
  }

  private handleConnectError(error: Error): void {
    this.handleError(error);

    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => {
        this.reconnect();
      }, this.reconnectDelay * this.reconnectAttempts);
    } else {
      console.error('达到最大重连次数，放弃重连');
      this.handleError(new Error('达到最大重连次数'));
    }
  }

  private reconnect(): void {
    console.log('尝试重连...');
    this.socket?.connect();
  }

  private handleError(error: Error): void {
    console.error('WebSocket 错误:', error);
    this.errorHandlers.forEach(handler => handler(error));
  }

  private handleMessage(message: WebSocketMessage): void {
    // 处理确认消息
    if (message.type === 'ack' && message.data?.id) {
      const pending = this.pendingMessages.get(message.data.id);
      if (pending) {
        clearTimeout(pending.timeout);
        this.pendingMessages.delete(message.data.id);
        pending.resolve(message.data);
      }
      return;
    }

    // 发送确认
    if (message.id) {
      this.send({
        type: 'ack',
        data: { id: message.id },
        timestamp: new Date().toISOString()
      });
    }

    // 处理普通消息
    const handlers = this.messageHandlers.get(message.type) || [];
    handlers.forEach(handler => handler(message));
  }

  on(messageType: string, handler: Function): void {
    if (!this.messageHandlers.has(messageType)) {
      this.messageHandlers.set(messageType, []);
    }
    this.messageHandlers.get(messageType)!.push(handler);
  }

  off(messageType: string, handler: Function): void {
    const handlers = this.messageHandlers.get(messageType);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    }
  }

  onError(handler: Function): void {
    this.errorHandlers.push(handler);
  }

  send(message: WebSocketMessage): void {
    if (this.socket && this.isConnected) {
      this.socket.emit('message', message);
    } else {
      console.warn('WebSocket 未连接，无法发送消息');
    }
  }

  async sendWithAck(message: WebSocketMessage, timeout = 10000): Promise<any> {
    return new Promise((resolve, reject) => {
      const id = this.messageId++;
      const messageWithId = { ...message, id };

      this.pendingMessages.set(id.toString(), {
        message: messageWithId,
        resolve,
        reject,
        timeout: setTimeout(() => {
          this.pendingMessages.delete(id.toString());
          reject(new Error('消息确认超时'));
        }, timeout)
      });

      this.send(messageWithId);
    });
  }

  sendBatch(message: WebSocketMessage): void {
    this.messageQueue.push(message);

    if (this.messageQueue.length >= this.batchSize) {
      this.flushBatch();
    } else if (!this.batchTimer) {
      this.batchTimer = setTimeout(() => {
        this.flushBatch();
      }, this.batchDelay);
    }
  }

  private flushBatch(): void {
    if (this.batchTimer) {
      clearTimeout(this.batchTimer);
      this.batchTimer = null;
    }

    if (this.messageQueue.length > 0) {
      const batch = this.messageQueue.splice(0, this.batchSize);
      this.send({
        type: 'batch',
        data: batch,
        timestamp: new Date().toISOString()
      });
    }
  }

  subscribeToTask(taskId: string): void {
    this.send({
      type: 'subscribe_task',
      data: { task_id: taskId },
      timestamp: new Date().toISOString()
    });
  }

  unsubscribeFromTask(taskId: string): void {
    this.send({
      type: 'unsubscribe_task',
      data: { task_id: taskId },
      timestamp: new Date().toISOString()
    });
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
      this.isConnected = false;
      this.messageHandlers.clear();
      this.errorHandlers = [];
      this.pendingMessages.forEach(pending => clearTimeout(pending.timeout));
      this.pendingMessages.clear();
      this.messageQueue = [];
      if (this.batchTimer) {
        clearTimeout(this.batchTimer);
        this.batchTimer = null;
      }
    }
  }

  getConnectionStatus(): boolean {
    return this.isConnected;
  }
}

// 导出单例
export const webSocketService = new WebSocketService(
  (import.meta.env.VITE_WS_URL as string) || 'ws://localhost:8000'
);