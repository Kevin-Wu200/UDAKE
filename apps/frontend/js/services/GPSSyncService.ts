import { resolveRuntimeApiBaseUrl } from './API封装.js';
import { OfflineManager } from '../utils/OfflineManager.js';

export type GPSSyncState = 'idle' | 'connecting' | 'connected' | 'offline' | 'syncing' | 'error';

export interface GPSSyncStatus {
  state: GPSSyncState;
  projectId: string;
  lastSyncAt: number | null;
  lastError: string | null;
}

interface PendingAckMessage {
  serialized: string;
  attempts: number;
  timer: number;
  resolve: (value: boolean) => void;
  reject: (reason?: unknown) => void;
}

export class GPSSyncService {
  private static instance: GPSSyncService;
  private websocket: WebSocket | null = null;
  private clientId = `gps_client_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  private projectId = 'default_mobile_project';
  private initialized = false;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private messageSeq = 0;
  private pendingAck: Map<string, PendingAckMessage> = new Map();
  private listeners: Set<(status: GPSSyncStatus) => void> = new Set();
  private enabled = true;
  private status: GPSSyncStatus = {
    state: 'idle',
    projectId: 'default_mobile_project',
    lastSyncAt: null,
    lastError: null
  };

  private constructor() {}

  public static getInstance(): GPSSyncService {
    if (!GPSSyncService.instance) {
      GPSSyncService.instance = new GPSSyncService();
    }
    return GPSSyncService.instance;
  }

  public async initialize(projectId: string = 'default_mobile_project'): Promise<void> {
    this.enabled = true;
    this.projectId = projectId || 'default_mobile_project';
    this.status.projectId = this.projectId;

    if (!this.initialized) {
      this.initialized = true;
      window.addEventListener('online', () => {
        void this.connect();
      });
      window.addEventListener('offline', () => {
        this.updateStatus('offline', '网络已离线');
        this.safeCloseSocket();
      });
    }

    if (navigator.onLine) {
      await this.connect();
    } else {
      this.updateStatus('offline', '网络离线，等待恢复');
    }
  }

  public onStatusChange(listener: (status: GPSSyncStatus) => void): () => void {
    this.listeners.add(listener);
    listener({ ...this.status });
    return () => {
      this.listeners.delete(listener);
    };
  }

  public getStatus(): GPSSyncStatus {
    return { ...this.status };
  }

  public async setProjectId(projectId: string): Promise<void> {
    const normalized = projectId || 'default_mobile_project';
    this.projectId = normalized;
    this.status.projectId = normalized;
    this.emitStatus();
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      await this.sendMessage(
        'subscribe_gps_project',
        { project_id: this.projectId },
        false
      );
    }
  }

  public async connect(): Promise<void> {
    if (!navigator.onLine) {
      this.updateStatus('offline', '网络离线，无法建立同步连接');
      return;
    }
    if (!this.enabled) {
      return;
    }
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      return;
    }
    if (this.websocket && this.websocket.readyState === WebSocket.CONNECTING) {
      return;
    }

    this.updateStatus('connecting');
    const wsUrl = this.buildWebSocketUrl();

    await new Promise<void>((resolve, reject) => {
      let settled = false;
      const socket = new WebSocket(wsUrl);
      this.websocket = socket;

      const timeout = window.setTimeout(() => {
        if (settled) return;
        settled = true;
        this.updateStatus('error', 'WebSocket 连接超时');
        try {
          socket.close();
        } catch {
          // ignore
        }
        reject(new Error('WebSocket 连接超时'));
      }, 8000);

      socket.onopen = async () => {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        this.updateStatus('connected');
        this.startHeartbeat();
        await this.sendMessage(
          'subscribe_gps_project',
          { project_id: this.projectId },
          false
        );
        resolve();
      };

      socket.onmessage = (event) => {
        this.handleMessage(event.data);
      };

      socket.onerror = () => {
        if (!settled) {
          settled = true;
          clearTimeout(timeout);
          this.updateStatus('error', 'WebSocket 连接失败');
          reject(new Error('WebSocket 连接失败'));
          return;
        }
        this.updateStatus('error', 'WebSocket 发生错误');
      };

      socket.onclose = () => {
        this.stopHeartbeat();
        this.rejectAllPending('连接已关闭');
        if (this.enabled && navigator.onLine) {
          this.updateStatus('offline', '连接中断，准备重连');
          this.scheduleReconnect();
        } else {
          this.updateStatus('offline', '网络离线');
        }
      };
    });
  }

  public async syncSample(sample: any, options: { fromQueue?: boolean } = {}): Promise<boolean> {
    if (!sample || typeof sample !== 'object') {
      if (options.fromQueue) {
        throw new Error('无效的 GPS 采样点数据');
      }
      return false;
    }

    this.updateStatus('syncing');

    try {
      if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
        const ok = await this.sendMessage(
          'gps_sample_upsert',
          {
            project_id: sample.projectId || this.projectId,
            strategy: 'latest-wins',
            sample: this.normalizeSampleForServer(sample)
          },
          true
        );
        if (ok) {
          this.markSyncSuccess();
          return true;
        }
      }
    } catch (error) {
      console.warn('[GPSSync] WebSocket 同步失败，尝试 HTTP 回退:', error);
    }

    try {
      const apiBase = resolveRuntimeApiBaseUrl();
      const response = await fetch(`${apiBase}/mobile-gps/sync/batch`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          client_id: this.clientId,
          project_id: sample.projectId || this.projectId,
          strategy: 'latest-wins',
          samples: [this.normalizeSampleForServer(sample)]
        })
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      this.markSyncSuccess();
      return true;
    } catch (error) {
      this.updateStatus('error', `同步失败: ${(error as Error).message}`);
      if (options.fromQueue) {
        throw error;
      }
      return false;
    }
  }

  public dispose(): void {
    this.enabled = false;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.rejectAllPending('同步服务已关闭');
    this.safeCloseSocket();
    this.listeners.clear();
  }

  private buildWebSocketUrl(): string {
    const apiBase = resolveRuntimeApiBaseUrl();
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    let origin = '';

    if (apiBase.startsWith('http://') || apiBase.startsWith('https://')) {
      const parsed = new URL(apiBase);
      origin = `${parsed.protocol === 'https:' ? 'wss:' : 'ws:'}//${parsed.host}`;
    } else if (apiBase.startsWith('/')) {
      origin = `${wsProtocol}//${window.location.host}`;
    } else {
      origin = `${wsProtocol}//${window.location.host}`;
    }

    return `${origin}/ws/${encodeURIComponent(this.clientId)}`;
  }

  private updateStatus(state: GPSSyncState, lastError: string | null = null): void {
    this.status = {
      ...this.status,
      state,
      projectId: this.projectId,
      lastError
    };
    this.emitStatus();
  }

  private markSyncSuccess(): void {
    this.status = {
      ...this.status,
      state: 'connected',
      projectId: this.projectId,
      lastSyncAt: Date.now(),
      lastError: null
    };
    this.emitStatus();
  }

  private emitStatus(): void {
    const snapshot = { ...this.status };
    this.listeners.forEach((listener) => {
      try {
        listener(snapshot);
      } catch (error) {
        console.error('[GPSSync] 状态监听回调失败:', error);
      }
    });
    if (typeof document !== 'undefined') {
      document.dispatchEvent(new CustomEvent('gps-sync-status', { detail: snapshot }));
    }
  }

  private normalizeSampleForServer(sample: any): Record<string, any> {
    return {
      id: sample.id,
      project_id: sample.projectId || sample.project_id || this.projectId,
      latitude: sample.latitude,
      longitude: sample.longitude,
      accuracy: sample.accuracy,
      altitude: sample.altitude ?? null,
      speed: sample.speed ?? null,
      heading: sample.heading ?? null,
      attributes: sample.attributes || {},
      collected_at: sample.collectedAt || sample.collected_at || Date.now(),
      updated_at: sample.updatedAt || sample.updated_at || Date.now(),
      version: sample.version || 1,
      source: sample.source || 'mobile'
    };
  }

  private async sendMessage(type: string, data: any, requireAck: boolean): Promise<boolean> {
    if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket 未连接');
    }

    const messageId = requireAck ? `gps_msg_${Date.now()}_${this.messageSeq++}` : undefined;
    const payload = {
      type,
      data,
      timestamp: new Date().toISOString(),
      message_id: messageId
    };
    const serialized = JSON.stringify(payload);
    this.websocket.send(serialized);

    if (!requireAck || !messageId) {
      return true;
    }

    return new Promise<boolean>((resolve, reject) => {
      const scheduleRetry = (): number => window.setTimeout(() => {
        const pending = this.pendingAck.get(messageId);
        if (!pending) return;
        if (pending.attempts >= 3) {
          this.pendingAck.delete(messageId);
          reject(new Error('消息 ACK 超时'));
          return;
        }
        pending.attempts += 1;
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
          this.websocket.send(pending.serialized);
        }
        clearTimeout(pending.timer);
        pending.timer = scheduleRetry();
      }, 4000);

      this.pendingAck.set(messageId, {
        serialized,
        attempts: 1,
        timer: scheduleRetry(),
        resolve,
        reject
      });
    });
  }

  private handleMessage(rawMessage: any): void {
    let message: any;
    try {
      message = typeof rawMessage === 'string' ? JSON.parse(rawMessage) : rawMessage;
    } catch {
      return;
    }

    const incomingMessageId = message?.message_id || message?.data?.message_id || message?.data?.id;
    if (message?.type !== 'ack' && incomingMessageId) {
      void this.sendAck(incomingMessageId);
    }

    if (message?.type === 'ack' && incomingMessageId) {
      const pending = this.pendingAck.get(incomingMessageId);
      if (pending) {
        clearTimeout(pending.timer);
        this.pendingAck.delete(incomingMessageId);
        pending.resolve(true);
      }
      return;
    }

    if (message?.type === 'gps_pong') {
      return;
    }

    if (message?.type === 'gps_sample_update') {
      const sample = message?.data?.sample || message?.sample;
      if (sample) {
        void OfflineManager.saveGPSSample({
          ...sample,
          projectId: sample.project_id || sample.projectId
        });
      }
      return;
    }
  }

  private async sendAck(messageId: string): Promise<void> {
    if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
      return;
    }
    this.websocket.send(
      JSON.stringify({
        type: 'ack',
        data: { message_id: messageId },
        timestamp: new Date().toISOString()
      })
    );
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = window.setInterval(() => {
      if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
        return;
      }
      this.websocket.send(
        JSON.stringify({
          type: 'gps_ping',
          data: { project_id: this.projectId },
          timestamp: new Date().toISOString()
        })
      );
    }, 20000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (!this.enabled) {
      return;
    }
    if (this.reconnectTimer) {
      return;
    }
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      void this.connect();
    }, 3000);
  }

  private rejectAllPending(message: string): void {
    this.pendingAck.forEach((pending) => {
      clearTimeout(pending.timer);
      pending.reject(new Error(message));
    });
    this.pendingAck.clear();
  }

  private safeCloseSocket(): void {
    if (this.websocket) {
      try {
        this.websocket.close();
      } catch {
        // ignore
      }
      this.websocket = null;
    }
  }
}

export const gpsSyncService = GPSSyncService.getInstance();
