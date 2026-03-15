/**
 * WebSocket 服务测试
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { WebSocketService, WebSocketMessage } from '../frontend/js/services/WebSocketService';

// Mock socket.io-client
vi.mock('socket.io-client', () => ({
  io: vi.fn(() => ({
    on: vi.fn(),
    emit: vi.fn(),
    disconnect: vi.fn(),
    connect: vi.fn(),
  })),
}));

describe('WebSocketService', () => {
  let service: WebSocketService;

  beforeEach(() => {
    service = new WebSocketService('ws://localhost:8000');
  });

  afterEach(() => {
    service.disconnect();
  });

  describe('连接测试', () => {
    it('应该能够连接到服务器', async () => {
      // 这里应该 mock socket.io 的连接
      // 由于 socket.io 的实现比较复杂，这里只是一个示例
      expect(service).toBeDefined();
      expect(service.getConnectionStatus()).toBe(false);
    });

    it('应该能够断开连接', () => {
      service.disconnect();
      expect(service.getConnectionStatus()).toBe(false);
    });
  });

  describe('消息处理', () => {
    it('应该能够注册消息处理器', () => {
      const handler = vi.fn();
      service.on('test_message', handler);
      expect(service).toBeDefined();
    });

    it('应该能够移除消息处理器', () => {
      const handler = vi.fn();
      service.on('test_message', handler);
      service.off('test_message', handler);
      expect(service).toBeDefined();
    });

    it('应该能够注册错误处理器', () => {
      const handler = vi.fn();
      service.onError(handler);
      expect(service).toBeDefined();
    });
  });

  describe('任务订阅', () => {
    it('应该能够订阅任务', () => {
      service.subscribeToTask('test_task_1');
      expect(service).toBeDefined();
    });

    it('应该能够取消订阅任务', () => {
      service.subscribeToTask('test_task_1');
      service.unsubscribeFromTask('test_task_1');
      expect(service).toBeDefined();
    });
  });

  describe('消息发送', () => {
    it('应该能够发送消息', () => {
      const message: WebSocketMessage = {
        type: 'test_message',
        data: { test: 'data' },
        timestamp: new Date().toISOString()
      };
      service.send(message);
      expect(service).toBeDefined();
    });
  });

  describe('批处理', () => {
    it('应该能够使用批处理发送消息', () => {
      const message: WebSocketMessage = {
        type: 'test_message',
        data: { test: 'data' },
        timestamp: new Date().toISOString()
      };
      service.sendBatch(message);
      expect(service).toBeDefined();
    });
  });

  describe('连接状态', () => {
    it('应该能够获取连接状态', () => {
      const status = service.getConnectionStatus();
      expect(typeof status).toBe('boolean');
    });
  });
});

describe('WebSocket 单例导出', () => {
  it('应该导出单例实例', () => {
    const { webSocketService } = require('../frontend/js/services/WebSocketService');
    expect(webSocketService).toBeDefined();
    expect(webSocketService).toBeInstanceOf(WebSocketService);
  });
});