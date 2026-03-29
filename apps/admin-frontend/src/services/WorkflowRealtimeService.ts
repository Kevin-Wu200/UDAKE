interface WorkflowRealtimeEvent {
  type: string;
  payload: Record<string, unknown>;
  raw: unknown;
}

type EventHandler = (event: WorkflowRealtimeEvent) => void;

function randomClientId() {
  return `workflow_admin_${Math.random().toString(36).slice(2, 10)}`;
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

function resolveWorkflowWsUrl(clientId: string): string | null {
  const apiUrl = resolveBaseApiUrl();
  if (!apiUrl) {
    return null;
  }

  const wsProtocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = new URL(`${wsProtocol}//${apiUrl.host}/ws/${clientId}`);
  return wsUrl.toString();
}

export class WorkflowRealtimeService {
  private socket: WebSocket | null = null;

  private readonly clientId = randomClientId();

  private reconnectTimer: number | null = null;

  private heartbeatTimer: number | null = null;

  private listeners = new Set<EventHandler>();

  private started = false;

  start() {
    this.started = true;
    this.connect();
  }

  stop() {
    this.started = false;
    this.clearTimers();
    if (this.socket) {
      this.socket.close();
    }
    this.socket = null;
  }

  subscribe(handler: EventHandler) {
    this.listeners.add(handler);
    return () => {
      this.listeners.delete(handler);
    };
  }

  notify(type: string, payload: Record<string, unknown>, raw: unknown) {
    const event: WorkflowRealtimeEvent = {
      type,
      payload,
      raw
    };

    this.listeners.forEach((listener) => {
      listener(event);
    });
  }

  private connect() {
    if (!this.started) {
      return;
    }

    const url = resolveWorkflowWsUrl(this.clientId);
    if (!url) {
      return;
    }

    try {
      this.socket = new WebSocket(url);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = () => {
      this.clearReconnectTimer();
      this.startHeartbeat();
      this.notify('connected', { client_id: this.clientId }, null);
    };

    this.socket.onmessage = (messageEvent) => {
      try {
        const raw = JSON.parse(messageEvent.data as string) as Record<string, unknown>;
        const type = typeof raw.type === 'string' ? raw.type : 'message';
        this.notify(type, raw, raw);
      } catch {
        this.notify('message', { content: String(messageEvent.data ?? '') }, messageEvent.data);
      }
    };

    this.socket.onclose = () => {
      this.clearHeartbeatTimer();
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
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
        return;
      }
      this.socket.send(
        JSON.stringify({
          type: 'ping',
          data: {
            ts: Date.now()
          }
        })
      );
    }, 20_000);
  }

  private scheduleReconnect() {
    if (!this.started || this.reconnectTimer !== null) {
      return;
    }

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 4_000);
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

  private clearTimers() {
    this.clearReconnectTimer();
    this.clearHeartbeatTimer();
  }
}

export const workflowRealtimeService = new WorkflowRealtimeService();
