interface WorkflowRealtimeEvent {
  type: string;
  payload: Record<string, unknown>;
  raw: unknown;
}

interface WorkflowRealtimeState {
  connectionStatus: 'connecting' | 'connected' | 'disconnected';
  reconnecting: boolean;
  reconnectAttempts: number;
  bufferedMessages: number;
  workflowSubscriptions: string[];
  runSubscriptions: string[];
}

interface BufferedMessage {
  payload: Record<string, unknown>;
  queuedAt: number;
  expireAt: number;
}

interface PendingAck {
  resolve: () => void;
  reject: (reason?: unknown) => void;
  timeoutId: number;
}

type EventHandler = (event: WorkflowRealtimeEvent) => void;
type StateHandler = (state: WorkflowRealtimeState) => void;
type MessageTypeHandler = (event: WorkflowRealtimeEvent) => void;

const ACCESS_TOKEN_KEYS = ['udake_access_token', 'admin_access_token'] as const;
const USER_INFO_KEY = 'udake_user_info';
const LEGACY_USER_KEY = 'admin_login_user';

function randomClientId() {
  return `workflow_admin_${Math.random().toString(36).slice(2, 10)}`;
}

function randomMessageId() {
  return `wsmsg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function resolveBaseApiUrl() {
  const base = (import.meta.env.VITE_API_BASE_URL || '').trim();
  if (!base) {
    return null;
  }
  try {
    return new URL(base, window.location.origin);
  } catch {
    return null;
  }
}

function getCurrentUserIdFromStorage() {
  const rawUser = localStorage.getItem(USER_INFO_KEY);
  if (rawUser) {
    try {
      const parsed = JSON.parse(rawUser) as { userId?: string; email?: string };
      if (parsed.userId) {
        return String(parsed.userId);
      }
      if (parsed.email) {
        return String(parsed.email);
      }
    } catch {
      // ignore
    }
  }
  const legacy = localStorage.getItem(LEGACY_USER_KEY);
  return legacy ? String(legacy) : '';
}

function getAccessTokenFromStorage() {
  for (const key of ACCESS_TOKEN_KEYS) {
    const token = localStorage.getItem(key);
    if (token) {
      return token;
    }
  }
  return '';
}

function resolveWorkflowWsUrl(clientId: string, userId: string, reconnect = false): string | null {
  const apiUrl = resolveBaseApiUrl();
  if (!apiUrl) {
    return null;
  }

  const wsProtocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = new URL(`${wsProtocol}//${apiUrl.host}/ws/${clientId}`);
  if (userId) {
    wsUrl.searchParams.set('user_id', userId);
  }
  wsUrl.searchParams.set('reconnect', reconnect ? '1' : '0');

  const token = getAccessTokenFromStorage();
  if (token) {
    wsUrl.searchParams.set('token', token);
  }
  return wsUrl.toString();
}

export class WorkflowRealtimeService {
  private socket: WebSocket | null = null;
  private readonly clientId = randomClientId();
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private listeners = new Set<EventHandler>();
  private stateListeners = new Set<StateHandler>();
  private messageHandlers = new Map<string, Set<MessageTypeHandler>>();
  private pendingAcks = new Map<string, PendingAck>();
  private started = false;
  private consumerCount = 0;

  private subscribedWorkflowIds = new Set<string>();
  private subscribedRunIds = new Set<string>();

  private outgoingBuffer: BufferedMessage[] = [];
  private processedMessageIds = new Set<string>();
  private processedMessageOrder: string[] = [];

  private reconnectAttempts = 0;
  private readonly maxReconnectAttempts = 8;
  private readonly reconnectBaseDelayMs = 1_000;
  private readonly reconnectMaxDelayMs = 30_000;
  private readonly bufferMaxSize = 300;
  private readonly bufferTtlMs = 5 * 60 * 1000;
  private readonly dedupMaxSize = 2000;

  private state: WorkflowRealtimeState = {
    connectionStatus: 'disconnected',
    reconnecting: false,
    reconnectAttempts: 0,
    bufferedMessages: 0,
    workflowSubscriptions: [],
    runSubscriptions: []
  };

  start() {
    this.consumerCount += 1;
    this.started = true;
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.emitState();
      return;
    }
    this.connect(false);
  }

  stop() {
    this.consumerCount = Math.max(0, this.consumerCount - 1);
    if (this.consumerCount > 0) {
      return;
    }
    this.started = false;
    this.clearTimers();
    this.clearPendingAcks('stopped');
    if (this.socket) {
      this.socket.close();
    }
    this.socket = null;
    this.updateState({ connectionStatus: 'disconnected', reconnecting: false, reconnectAttempts: 0 });
  }

  subscribe(handler: EventHandler) {
    this.listeners.add(handler);
    return () => {
      this.listeners.delete(handler);
    };
  }

  subscribeState(handler: StateHandler) {
    this.stateListeners.add(handler);
    handler({ ...this.state });
    return () => {
      this.stateListeners.delete(handler);
    };
  }

  registerHandler(messageType: string, handler: MessageTypeHandler) {
    const key = String(messageType || '').trim().toLowerCase();
    if (!key) {
      return () => undefined;
    }
    const bucket = this.messageHandlers.get(key) || new Set<MessageTypeHandler>();
    bucket.add(handler);
    this.messageHandlers.set(key, bucket);
    return () => {
      const current = this.messageHandlers.get(key);
      if (!current) {
        return;
      }
      current.delete(handler);
      if (current.size === 0) {
        this.messageHandlers.delete(key);
      }
    };
  }

  setWorkflowSubscription(workflowId?: string | null) {
    const next = (workflowId || '').trim();
    const previous = Array.from(this.subscribedWorkflowIds);
    this.subscribedWorkflowIds.clear();

    if (next) {
      this.subscribedWorkflowIds.add(next);
    }

    previous
      .filter((id) => !this.subscribedWorkflowIds.has(id))
      .forEach((id) => {
        this.publish('unsubscribe_workflow', { workflow_id: id });
      });
    this.subscribedWorkflowIds.forEach((id) => {
      if (!previous.includes(id)) {
        this.publish('subscribe_workflow', { workflow_id: id });
      }
    });
    this.emitState();
  }

  addWorkflowSubscription(workflowId: string) {
    const id = String(workflowId || '').trim();
    if (!id || this.subscribedWorkflowIds.has(id)) {
      return;
    }
    this.subscribedWorkflowIds.add(id);
    this.publish('subscribe_workflow', { workflow_id: id });
    this.emitState();
  }

  removeWorkflowSubscription(workflowId: string) {
    const id = String(workflowId || '').trim();
    if (!id || !this.subscribedWorkflowIds.has(id)) {
      return;
    }
    this.subscribedWorkflowIds.delete(id);
    this.publish('unsubscribe_workflow', { workflow_id: id });
    this.emitState();
  }

  setRunSubscription(runId?: string | null) {
    const next = (runId || '').trim();
    const previous = Array.from(this.subscribedRunIds);
    this.subscribedRunIds.clear();

    if (next) {
      this.subscribedRunIds.add(next);
    }

    previous
      .filter((id) => !this.subscribedRunIds.has(id))
      .forEach((id) => {
        this.publish('unsubscribe_workflow_run', { run_id: id });
      });
    this.subscribedRunIds.forEach((id) => {
      if (!previous.includes(id)) {
        this.publish('subscribe_workflow_run', { run_id: id });
      }
    });
    this.emitState();
  }

  publish(
    type: string,
    payload: Record<string, unknown>,
    options: { waitAck?: boolean; timeoutMs?: number } = {}
  ): Promise<void> | void {
    const messageId = typeof payload.message_id === 'string' ? payload.message_id : randomMessageId();
    const frame: Record<string, unknown> = {
      type,
      message_id: messageId,
      ...payload
    };

    const sent = this.send(frame);
    if (!options.waitAck) {
      return;
    }

    return new Promise<void>((resolve, reject) => {
      const timeoutMs = Math.max(500, options.timeoutMs || 8_000);
      const timeoutId = window.setTimeout(() => {
        this.pendingAcks.delete(messageId);
        reject(new Error('ack timeout'));
      }, timeoutMs);
      this.pendingAcks.set(messageId, {
        resolve,
        reject,
        timeoutId
      });

      if (!sent) {
        // 缓冲后等待重连继续发送，不立即 reject
      }
    });
  }

  private notify(type: string, payload: Record<string, unknown>, raw: unknown) {
    const event: WorkflowRealtimeEvent = { type, payload, raw };
    this.listeners.forEach((listener) => listener(event));

    const handlers = this.messageHandlers.get(type.toLowerCase());
    if (handlers && handlers.size > 0) {
      handlers.forEach((handler) => handler(event));
    }
  }

  private connect(isReconnect: boolean) {
    if (!this.started) {
      return;
    }

    const userId = getCurrentUserIdFromStorage();
    const url = resolveWorkflowWsUrl(this.clientId, userId, isReconnect);
    if (!url) {
      this.scheduleReconnect();
      return;
    }

    this.updateState({
      connectionStatus: 'connecting',
      reconnecting: isReconnect,
      reconnectAttempts: this.reconnectAttempts
    });

    try {
      this.socket = new WebSocket(url);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = () => {
      this.clearReconnectTimer();
      this.reconnectAttempts = 0;
      this.syncSubscriptions();
      this.startHeartbeat();
      this.replayBufferedMessages();
      this.updateState({
        connectionStatus: 'connected',
        reconnecting: false,
        reconnectAttempts: 0
      });
      this.notify('connected', { client_id: this.clientId }, null);
    };

    this.socket.onmessage = (messageEvent) => {
      try {
        const raw = JSON.parse(messageEvent.data as string) as Record<string, unknown>;
        const messageId = typeof raw.message_id === 'string' ? raw.message_id : '';
        if (messageId && this.isDuplicateMessage(messageId)) {
          return;
        }

        const type = typeof raw.type === 'string' ? raw.type : 'message';
        if (type === 'ack') {
          const ackId =
            (typeof raw.message_id === 'string' && raw.message_id) ||
            (typeof raw.ack_id === 'string' && raw.ack_id) ||
            '';
          if (ackId && this.pendingAcks.has(ackId)) {
            const pending = this.pendingAcks.get(ackId);
            if (pending) {
              window.clearTimeout(pending.timeoutId);
              pending.resolve();
              this.pendingAcks.delete(ackId);
            }
          }
        }

        this.notify(type, raw, raw);
      } catch {
        this.notify('message', { content: String(messageEvent.data ?? '') }, messageEvent.data);
      }
    };

    this.socket.onclose = () => {
      this.clearHeartbeatTimer();
      this.updateState({
        connectionStatus: 'disconnected',
        reconnecting: true,
        reconnectAttempts: this.reconnectAttempts
      });
      this.notify('disconnected', {}, null);
      this.scheduleReconnect();
    };

    this.socket.onerror = () => {
      this.notify('error', {}, null);
    };
  }

  private startHeartbeat() {
    this.clearHeartbeatTimer();
    this.heartbeatTimer = window.setInterval(() => {
      this.publish('ping', {
        data: {
          ts: Date.now()
        }
      });
    }, 20_000);
  }

  private syncSubscriptions() {
    this.subscribedWorkflowIds.forEach((workflowId) => {
      this.send({
        type: 'subscribe_workflow',
        workflow_id: workflowId,
        message_id: randomMessageId()
      });
    });

    this.subscribedRunIds.forEach((runId) => {
      this.send({
        type: 'subscribe_workflow_run',
        run_id: runId,
        message_id: randomMessageId()
      });
    });

    const currentUserId = getCurrentUserIdFromStorage();
    if (currentUserId) {
      this.send({
        type: 'subscribe_user_notifications',
        user_id: currentUserId,
        message_id: randomMessageId()
      });
      this.send({
        type: 'subscribe_user_mentions',
        user_id: currentUserId,
        message_id: randomMessageId()
      });
      this.send({
        type: 'subscribe_user_activity',
        user_id: currentUserId,
        message_id: randomMessageId()
      });
    }
  }

  private send(payload: Record<string, unknown>) {
    this.pruneBuffer();
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.bufferOutgoing(payload);
      return false;
    }
    this.socket.send(JSON.stringify(payload));
    return true;
  }

  private bufferOutgoing(payload: Record<string, unknown>) {
    const now = Date.now();
    this.outgoingBuffer.push({
      payload,
      queuedAt: now,
      expireAt: now + this.bufferTtlMs
    });
    if (this.outgoingBuffer.length > this.bufferMaxSize) {
      this.outgoingBuffer = this.outgoingBuffer.slice(-this.bufferMaxSize);
    }
    this.emitState();
  }

  private replayBufferedMessages() {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return;
    }
    this.pruneBuffer();
    this.outgoingBuffer
      .sort((a, b) => a.queuedAt - b.queuedAt)
      .forEach((item) => {
        this.socket?.send(JSON.stringify(item.payload));
      });
    this.outgoingBuffer = [];
    this.emitState();
    this.notify('buffer_replayed', { replayed: true }, null);
  }

  private pruneBuffer() {
    const now = Date.now();
    this.outgoingBuffer = this.outgoingBuffer.filter((item) => item.expireAt >= now);
  }

  private isDuplicateMessage(messageId: string) {
    if (this.processedMessageIds.has(messageId)) {
      return true;
    }
    this.processedMessageIds.add(messageId);
    this.processedMessageOrder.push(messageId);
    if (this.processedMessageOrder.length > this.dedupMaxSize) {
      const stale = this.processedMessageOrder.shift();
      if (stale) {
        this.processedMessageIds.delete(stale);
      }
    }
    return false;
  }

  private scheduleReconnect() {
    if (!this.started || this.reconnectTimer !== null) {
      return;
    }
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.updateState({
        reconnecting: false,
        connectionStatus: 'disconnected',
        reconnectAttempts: this.reconnectAttempts
      });
      this.notify('reconnect_failed', { attempts: this.reconnectAttempts }, null);
      return;
    }

    this.reconnectAttempts += 1;
    const jitter = Math.floor(Math.random() * 200);
    const backoff = Math.min(
      this.reconnectBaseDelayMs * 2 ** (this.reconnectAttempts - 1) + jitter,
      this.reconnectMaxDelayMs
    );
    this.updateState({
      reconnecting: true,
      reconnectAttempts: this.reconnectAttempts,
      connectionStatus: 'disconnected'
    });
    this.notify('reconnecting', { attempt: this.reconnectAttempts, delay_ms: backoff }, null);

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect(true);
    }, backoff);
  }

  private clearReconnectTimer() {
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private clearHeartbeatTimer() {
    if (this.heartbeatTimer !== null) {
      window.clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private clearPendingAcks(reason = 'cancelled') {
    this.pendingAcks.forEach((pending) => {
      window.clearTimeout(pending.timeoutId);
      pending.reject(new Error(reason));
    });
    this.pendingAcks.clear();
  }

  private clearTimers() {
    this.clearReconnectTimer();
    this.clearHeartbeatTimer();
  }

  private updateState(patch: Partial<WorkflowRealtimeState>) {
    this.state = {
      ...this.state,
      ...patch,
      bufferedMessages: this.outgoingBuffer.length,
      workflowSubscriptions: Array.from(this.subscribedWorkflowIds),
      runSubscriptions: Array.from(this.subscribedRunIds)
    };
    this.emitState();
  }

  private emitState() {
    const snapshot: WorkflowRealtimeState = { ...this.state };
    this.stateListeners.forEach((handler) => handler(snapshot));
    this.notify('state_changed', snapshot as unknown as Record<string, unknown>, snapshot);
  }
}

export const workflowRealtimeService = new WorkflowRealtimeService();
