import { resolveRuntimeApiBaseUrl } from './API封装.js';
import { OfflineManager } from '../utils/OfflineManager.js';

export type GPSSyncState = 'idle' | 'connecting' | 'connected' | 'offline' | 'syncing' | 'error';

export interface GPSSyncStatus {
  state: GPSSyncState;
  projectId: string;
  lastSyncAt: number | null;
  lastError: string | null;
  connectionHealth: {
    rttMs: number | null;
    heartbeatIntervalMs: number;
    packetLossRate: number;
    reconnectAttempts: number;
    lastPongAt: number | null;
  };
}

interface PendingAckMessage {
  serialized: string;
  attempts: number;
  timer: number;
  resolve: (value: boolean) => void;
  reject: (reason?: unknown) => void;
}

interface BatchSyncPayload {
  client_id: string;
  project_id: string;
  strategy: 'client-wins' | 'server-wins' | 'latest-wins' | 'manual';
  samples: Array<Record<string, any>>;
  message_id?: string;
  enable_adaptive_batch?: boolean;
  network_rtt_ms?: number;
  network_bandwidth_kbps?: number;
  enable_diff_sync?: boolean;
  diff_base_fingerprint?: string;
  rate_limit_kbps?: number;
}

interface NetworkProfile {
  rttMs: number;
  bandwidthKbps: number;
}

interface BatchSyncOptions {
  strategy?: BatchSyncPayload['strategy'];
  adaptive?: boolean;
  forceHttp?: boolean;
  diffSync?: boolean;
  rateLimitKbps?: number;
}

type CompressionAlgorithm = 'gzip' | 'deflate' | 'br';

const RECONNECT_BASE_DELAY_MS = 3000;
const RECONNECT_MAX_DELAY_MS = 60000;
const RECONNECT_JITTER_RATIO = 0.2;
const ACK_RETRY_BASE_DELAY_MS = 4000;
const ACK_RETRY_MAX_ATTEMPTS = 3;
const COMPRESSION_THRESHOLD_BYTES = 1024;
const MESSAGE_DEDUP_WINDOW_MS = 5 * 60 * 1000;
const ADAPTIVE_BATCH_MIN = 100;
const ADAPTIVE_BATCH_MAX = 2000;

export function calculateBackoffDelay(
  attempt: number,
  baseDelayMs: number = RECONNECT_BASE_DELAY_MS,
  maxDelayMs: number = RECONNECT_MAX_DELAY_MS,
  jitterRatio: number = RECONNECT_JITTER_RATIO
): number {
  const exponential = Math.min(maxDelayMs, baseDelayMs * 2 ** Math.max(0, attempt));
  const jitterFactor = 1 + ((Math.random() * 2 - 1) * jitterRatio);
  return Math.max(baseDelayMs, Math.round(exponential * jitterFactor));
}

function toBase64(bytes: Uint8Array): string {
  let binary = '';
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

function fromBase64(base64: string): Uint8Array {
  const binary = atob(base64);
  const output = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    output[i] = binary.charCodeAt(i);
  }
  return output;
}

export class GPSSyncService {
  private static instance: GPSSyncService;
  private websocket: WebSocket | null = null;
  private clientId = `gps_client_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  private projectId = 'default_mobile_project';
  private initialized = false;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private reconnectAttempts = 0;
  private heartbeatIntervalMs = 20000;
  private heartbeatMisses = 0;
  private lastPingAt: number | null = null;
  private lastPongAt: number | null = null;
  private avgRttMs: number | null = null;
  private heartbeatHistory: number[] = [];

  private messageSeq = 0;
  private pendingAck: Map<string, PendingAckMessage> = new Map();
  private processedMessageIds: Map<string, number> = new Map();
  private sampleSnapshots: Map<string, Record<string, any>> = new Map();

  private listeners: Set<(status: GPSSyncStatus) => void> = new Set();
  private enabled = true;
  private status: GPSSyncStatus = {
    state: 'idle',
    projectId: 'default_mobile_project',
    lastSyncAt: null,
    lastError: null,
    connectionHealth: {
      rttMs: null,
      heartbeatIntervalMs: 20000,
      packetLossRate: 0,
      reconnectAttempts: 0,
      lastPongAt: null
    }
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
    listener({ ...this.status, connectionHealth: { ...this.status.connectionHealth } });
    return () => {
      this.listeners.delete(listener);
    };
  }

  public getStatus(): GPSSyncStatus {
    return { ...this.status, connectionHealth: { ...this.status.connectionHealth } };
  }

  public async setProjectId(projectId: string): Promise<void> {
    const normalized = projectId || 'default_mobile_project';
    this.projectId = normalized;
    this.status.projectId = normalized;
    this.emitStatus();
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      await this.sendMessage('subscribe_gps_project', { project_id: this.projectId }, false);
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
        this.reconnectAttempts = 0;
        this.heartbeatMisses = 0;
        this.updateStatus('connected');
        this.startHeartbeat();
        await this.sendMessage('subscribe_gps_project', { project_id: this.projectId }, false);
        resolve();
      };

      socket.onmessage = (event) => {
        void this.handleMessage(event.data);
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

    const normalized = this.normalizeSampleForServer(sample);
    const incremental = this.buildIncrementalPayload(normalized);

    try {
      if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
        const ok = await this.sendMessage(
          'gps_sample_upsert',
          {
            project_id: sample.projectId || this.projectId,
            strategy: 'latest-wins',
            sample: incremental
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
      const batchPayload: BatchSyncPayload = {
        client_id: this.clientId,
        project_id: sample.projectId || this.projectId,
        strategy: 'latest-wins',
        samples: [incremental],
        message_id: `gps_batch_${Date.now()}_${this.messageSeq++}`
      };

      const requestBody = await this.createHttpRequestBody(batchPayload);
      const response = await fetch(`${apiBase}/mobile-gps/sync/batch`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
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

  public async syncSamples(samples: any[], options: BatchSyncOptions = {}): Promise<{ success: number; failed: number; batches: number }> {
    if (!Array.isArray(samples) || samples.length === 0) {
      return { success: 0, failed: 0, batches: 0 };
    }

    const profile = this.estimateNetworkProfile();
    const normalized = samples
      .filter(item => item && typeof item === 'object')
      .map(item => this.buildIncrementalPayload(this.normalizeSampleForServer(item)));
    if (normalized.length === 0) {
      return { success: 0, failed: samples.length, batches: 0 };
    }

    const batchSize = options.adaptive !== false
      ? this.recommendBatchSize(profile, normalized.length)
      : Math.min(ADAPTIVE_BATCH_MAX, Math.max(1, normalized.length));
    const apiBase = resolveRuntimeApiBaseUrl();

    let success = 0;
    let failed = 0;
    let batches = 0;

    for (let start = 0; start < normalized.length; start += batchSize) {
      const chunk = normalized.slice(start, start + batchSize);
      batches += 1;
      const payload: BatchSyncPayload = {
        client_id: this.clientId,
        project_id: chunk[0]?.project_id || this.projectId,
        strategy: options.strategy || 'latest-wins',
        samples: this.optimizeBatchPayload(chunk),
        message_id: `gps_batch_${Date.now()}_${this.messageSeq++}`,
        enable_adaptive_batch: options.adaptive !== false,
        network_rtt_ms: profile.rttMs,
        network_bandwidth_kbps: profile.bandwidthKbps,
        enable_diff_sync: options.diffSync !== false,
        diff_base_fingerprint: this.computeRabinFingerprint(chunk),
        rate_limit_kbps: options.rateLimitKbps
      };

      try {
        if (!options.forceHttp && this.websocket && this.websocket.readyState === WebSocket.OPEN) {
          const ok = await this.sendMessage('gps_batch_upsert', payload, true);
          if (ok) {
            success += chunk.length;
            continue;
          }
        }

        const requestBody = await this.createHttpRequestBody(payload);
        const response = await fetch(`${apiBase}/mobile-gps/sync/batch`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestBody)
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        success += chunk.length;
      } catch (error) {
        console.warn('[GPSSync] 批量同步失败:', error);
        failed += chunk.length;
      }
    }

    if (success > 0) {
      this.markSyncSuccess();
    } else if (failed > 0) {
      this.updateStatus('error', `批量同步失败: ${failed}/${normalized.length}`);
    }
    return { success, failed, batches };
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
    this.pendingAck.clear();
    this.processedMessageIds.clear();
    this.sampleSnapshots.clear();
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
      lastError,
      connectionHealth: {
        ...this.status.connectionHealth,
        rttMs: this.avgRttMs,
        heartbeatIntervalMs: this.heartbeatIntervalMs,
        packetLossRate: this.getPacketLossRate(),
        reconnectAttempts: this.reconnectAttempts,
        lastPongAt: this.lastPongAt
      }
    };
    this.emitStatus();
  }

  private markSyncSuccess(): void {
    this.status = {
      ...this.status,
      state: 'connected',
      projectId: this.projectId,
      lastSyncAt: Date.now(),
      lastError: null,
      connectionHealth: {
        ...this.status.connectionHealth,
        rttMs: this.avgRttMs,
        heartbeatIntervalMs: this.heartbeatIntervalMs,
        packetLossRate: this.getPacketLossRate(),
        reconnectAttempts: this.reconnectAttempts,
        lastPongAt: this.lastPongAt
      }
    };
    this.emitStatus();
  }

  private emitStatus(): void {
    const snapshot: GPSSyncStatus = {
      ...this.status,
      connectionHealth: { ...this.status.connectionHealth }
    };
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

  private estimateNetworkProfile(): NetworkProfile {
    const rttMs = Math.max(60, this.avgRttMs ?? 300);
    const packetLoss = this.getPacketLossRate();
    const healthFactor = Math.max(0.2, 1 - packetLoss);
    const baselineKbps = 4096;
    const bandwidthKbps = Math.max(256, Math.round((baselineKbps / (rttMs / 200)) * healthFactor));
    return { rttMs, bandwidthKbps };
  }

  private recommendBatchSize(profile: NetworkProfile, total: number): number {
    let batch = 1000;
    if (profile.rttMs > 1500) {
      batch = 200;
    } else if (profile.rttMs > 900) {
      batch = 350;
    } else if (profile.rttMs > 500) {
      batch = 500;
    }

    if (profile.bandwidthKbps < 512) {
      batch = Math.min(batch, 200);
    } else if (profile.bandwidthKbps < 1024) {
      batch = Math.min(batch, 350);
    } else if (profile.bandwidthKbps > 5000) {
      batch = Math.max(batch, 1400);
    }

    return Math.max(ADAPTIVE_BATCH_MIN, Math.min(ADAPTIVE_BATCH_MAX, Math.min(total, batch)));
  }

  private optimizeBatchPayload(samples: Array<Record<string, any>>): Array<Record<string, any>> {
    if (samples.length < 2) {
      return samples;
    }
    const deltaEncoded = this.deltaEncodeCoordinates(samples);
    const dictionaryResult = this.compressAttributesDictionary(deltaEncoded);
    return dictionaryResult.records.map((item) => ({
      ...item,
      _dict_keys: dictionaryResult.dictionary
    }));
  }

  private deltaEncodeCoordinates(samples: Array<Record<string, any>>): Array<Record<string, any>> {
    let previousLat: number | null = null;
    let previousLng: number | null = null;
    return samples.map((sample, index) => {
      const lat = Number(sample.latitude);
      const lng = Number(sample.longitude);
      const scaledLat = Math.round(lat * 1e6);
      const scaledLng = Math.round(lng * 1e6);
      if (index === 0 || previousLat === null || previousLng === null) {
        previousLat = scaledLat;
        previousLng = scaledLng;
        return { ...sample, _coord_encoding: 'absolute', latitude: lat, longitude: lng };
      }

      const deltaLat = scaledLat - previousLat;
      const deltaLng = scaledLng - previousLng;
      previousLat = scaledLat;
      previousLng = scaledLng;
      return {
        ...sample,
        _coord_encoding: 'delta',
        latitude_delta: deltaLat,
        longitude_delta: deltaLng,
        latitude: lat,
        longitude: lng
      };
    });
  }

  private compressAttributesDictionary(samples: Array<Record<string, any>>): {
    dictionary: string[];
    records: Array<Record<string, any>>;
  } {
    const dictionarySet = new Set<string>();
    samples.forEach((sample) => {
      const attributes = sample.attributes || {};
      Object.keys(attributes).forEach(key => dictionarySet.add(key));
    });
    const dictionary = Array.from(dictionarySet);
    const keyIndexMap = new Map<string, number>(dictionary.map((key, index) => [key, index]));
    const records = samples.map((sample) => {
      const attributes = sample.attributes || {};
      const packedAttributes: Record<string, any> = {};
      Object.keys(attributes).forEach((key) => {
        const idx = keyIndexMap.get(key);
        packedAttributes[String(idx)] = attributes[key];
      });
      return {
        ...sample,
        attributes: packedAttributes
      };
    });
    return { dictionary, records };
  }

  private buildIncrementalPayload(sample: Record<string, any>): Record<string, any> {
    const sampleId = String(sample.id || `gps_${Date.now()}`);
    const key = `${sample.project_id || this.projectId}:${sampleId}`;
    const previous = this.sampleSnapshots.get(key) || {};

    const changedFields = Object.keys(sample).filter((field) => {
      return JSON.stringify(sample[field]) !== JSON.stringify(previous[field]);
    });

    const serialized = JSON.stringify(sample);
    const fingerprint = this.simpleFingerprint(serialized);

    this.sampleSnapshots.set(key, { ...sample });

    return {
      ...sample,
      id: sampleId,
      changed_fields: changedFields,
      fingerprint,
      fingerprint_rabin: this.computeRabinFingerprint(sample)
    };
  }

  private computeRabinFingerprint(payload: unknown): string {
    const text = JSON.stringify(payload);
    const mod = 2 ** 31 - 1;
    const base = 257;
    let acc = 0;
    for (let i = 0; i < text.length; i += 1) {
      acc = (acc * base + text.charCodeAt(i) + 1) % mod;
    }
    return `rb_${acc.toString(16)}`;
  }

  private simpleFingerprint(input: string): string {
    let hash = 2166136261;
    for (let i = 0; i < input.length; i += 1) {
      hash ^= input.charCodeAt(i);
      hash += (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24);
    }
    return `fp_${(hash >>> 0).toString(16)}`;
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

    const serialized = await this.serializeOutgoingPayload(type, payload);
    this.websocket.send(serialized);

    if (!requireAck || !messageId) {
      return true;
    }

    return new Promise<boolean>((resolve, reject) => {
      const scheduleRetry = (): number => window.setTimeout(() => {
        const pending = this.pendingAck.get(messageId);
        if (!pending) return;
        if (pending.attempts >= ACK_RETRY_MAX_ATTEMPTS) {
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
      }, ACK_RETRY_BASE_DELAY_MS);

      this.pendingAck.set(messageId, {
        serialized,
        attempts: 1,
        timer: scheduleRetry(),
        resolve,
        reject
      });
    });
  }

  private async serializeOutgoingPayload(type: string, payload: Record<string, any>): Promise<string> {
    const raw = JSON.stringify(payload);
    if (raw.length < COMPRESSION_THRESHOLD_BYTES) {
      return raw;
    }

    const algorithm = this.selectCompressionAlgorithm(raw, 'websocket');
    const compressed = await this.tryCompressToBase64(raw, algorithm);
    if (!compressed) {
      return raw;
    }

    return JSON.stringify({
      type: 'compressed_payload',
      message_id: payload.message_id,
      timestamp: payload.timestamp,
      data: {
        original_type: type,
        compression: algorithm,
        encoding: 'base64',
        payload: compressed,
        original_size: raw.length
      }
    });
  }

  private selectCompressionAlgorithm(raw: string, channel: 'websocket' | 'http'): CompressionAlgorithm {
    if (channel === 'http' && raw.length > 64 * 1024) {
      return 'br';
    }
    if (raw.length > 16 * 1024) {
      return 'gzip';
    }
    return 'deflate';
  }

  private async tryCompressToBase64(input: string, algorithm: CompressionAlgorithm = 'gzip'): Promise<string | null> {
    try {
      const CompressionCtor = (globalThis as any).CompressionStream;
      if (!CompressionCtor) {
        return null;
      }

      const stream = new CompressionCtor(algorithm);
      const writer = stream.writable.getWriter();
      await writer.write(new TextEncoder().encode(input));
      await writer.close();

      const compressedArrayBuffer = await new Response(stream.readable).arrayBuffer();
      return toBase64(new Uint8Array(compressedArrayBuffer));
    } catch {
      return null;
    }
  }

  private async tryDecompressFromBase64(base64: string, algorithm: CompressionAlgorithm = 'gzip'): Promise<string | null> {
    try {
      const DecompressionCtor = (globalThis as any).DecompressionStream;
      if (!DecompressionCtor) {
        return null;
      }

      const compressed = fromBase64(base64);
      const stream = new DecompressionCtor(algorithm);
      const writer = stream.writable.getWriter();
      await writer.write(compressed);
      await writer.close();

      const buffer = await new Response(stream.readable).arrayBuffer();
      return new TextDecoder().decode(buffer);
    } catch {
      return null;
    }
  }

  private async handleMessage(rawMessage: any): Promise<void> {
    let message: any;
    try {
      message = typeof rawMessage === 'string' ? JSON.parse(rawMessage) : rawMessage;
    } catch {
      return;
    }

    if (message?.type === 'compressed_payload') {
      const data = message?.data || {};
      if (data?.encoding === 'base64' && typeof data?.payload === 'string') {
        const decompressed = await this.tryDecompressFromBase64(data.payload, data.compression || 'gzip');
        if (decompressed) {
          try {
            const parsed = JSON.parse(decompressed);
            await this.handleParsedMessage(parsed);
          } catch {
            // ignore malformed payload
          }
        }
      }
      return;
    }

    await this.handleParsedMessage(message);
  }

  private async handleParsedMessage(message: any): Promise<void> {
    const incomingMessageId = message?.message_id || message?.data?.message_id || message?.data?.id;

    if (message?.type !== 'ack' && incomingMessageId) {
      await this.sendAck(incomingMessageId);
      if (this.isDuplicateMessage(incomingMessageId)) {
        return;
      }
      this.markMessageProcessed(incomingMessageId);
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
      this.onHeartbeatSuccess();
      return;
    }

    if (message?.type === 'gps_sample_update') {
      const sample = message?.data?.sample || message?.sample;
      if (sample) {
        await OfflineManager.saveGPSSample({
          ...sample,
          projectId: sample.project_id || sample.projectId
        });
      }
    }
  }

  private isDuplicateMessage(messageId: string): boolean {
    this.cleanupProcessedMessageIds();
    return this.processedMessageIds.has(messageId);
  }

  private markMessageProcessed(messageId: string): void {
    this.cleanupProcessedMessageIds();
    this.processedMessageIds.set(messageId, Date.now());
  }

  private cleanupProcessedMessageIds(): void {
    const now = Date.now();
    this.processedMessageIds.forEach((timestamp, key) => {
      if (now - timestamp > MESSAGE_DEDUP_WINDOW_MS) {
        this.processedMessageIds.delete(key);
      }
    });
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
      this.sendHeartbeatPing();
    }, this.heartbeatIntervalMs);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private sendHeartbeatPing(): void {
    if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
      return;
    }

    const now = Date.now();
    if (this.lastPingAt && !this.lastPongAt) {
      if (now - this.lastPingAt >= this.heartbeatIntervalMs * 2) {
        this.heartbeatMisses += 1;
        this.recordHeartbeatResult(false);
      }
    }

    if (this.heartbeatMisses >= 3) {
      this.updateStatus('offline', '心跳连续失败，准备重连');
      this.safeCloseSocket();
      return;
    }

    this.lastPingAt = now;
    this.lastPongAt = null;
    this.websocket.send(
      JSON.stringify({
        type: 'gps_ping',
        data: {
          project_id: this.projectId,
          sent_at: now
        },
        timestamp: new Date(now).toISOString()
      })
    );
  }

  private onHeartbeatSuccess(): void {
    const now = Date.now();
    this.lastPongAt = now;
    this.heartbeatMisses = 0;

    if (this.lastPingAt) {
      const rtt = Math.max(0, now - this.lastPingAt);
      this.avgRttMs = this.avgRttMs === null ? rtt : Math.round(this.avgRttMs * 0.7 + rtt * 0.3);
    }

    this.recordHeartbeatResult(true);
    this.adjustHeartbeatInterval();
    this.updateStatus('connected');
  }

  private recordHeartbeatResult(success: boolean): void {
    this.heartbeatHistory.push(success ? 1 : 0);
    if (this.heartbeatHistory.length > 30) {
      this.heartbeatHistory.shift();
    }
  }

  private getPacketLossRate(): number {
    if (this.heartbeatHistory.length === 0) {
      return 0;
    }
    const failures = this.heartbeatHistory.filter(item => item === 0).length;
    return failures / this.heartbeatHistory.length;
  }

  private adjustHeartbeatInterval(): void {
    const previous = this.heartbeatIntervalMs;

    if (this.avgRttMs === null) {
      this.heartbeatIntervalMs = 20000;
    } else if (this.avgRttMs > 1500) {
      this.heartbeatIntervalMs = 10000;
    } else if (this.avgRttMs > 800) {
      this.heartbeatIntervalMs = 15000;
    } else {
      this.heartbeatIntervalMs = 20000;
    }

    if (previous !== this.heartbeatIntervalMs) {
      this.startHeartbeat();
    }
  }

  private scheduleReconnect(): void {
    if (!this.enabled) {
      return;
    }
    if (this.reconnectTimer) {
      return;
    }

    const delay = calculateBackoffDelay(this.reconnectAttempts);
    this.reconnectAttempts += 1;

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      void this.connect();
    }, delay);
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

  private async createHttpRequestBody(payload: BatchSyncPayload): Promise<Record<string, any>> {
    const serialized = JSON.stringify(payload);
    if (serialized.length < COMPRESSION_THRESHOLD_BYTES) {
      return payload;
    }

    const algorithm = this.selectCompressionAlgorithm(serialized, 'http');
    const compressed = await this.tryCompressToBase64(serialized, algorithm);
    if (!compressed) {
      return payload;
    }

    return {
      message_id: payload.message_id,
      compression: algorithm === 'br' ? 'brotli' : algorithm,
      encoding: 'base64',
      compressed_payload: compressed,
      batch_size: payload.samples.length,
      enable_adaptive_batch: payload.enable_adaptive_batch,
      network_rtt_ms: payload.network_rtt_ms,
      network_bandwidth_kbps: payload.network_bandwidth_kbps,
      enable_diff_sync: payload.enable_diff_sync,
      diff_base_fingerprint: payload.diff_base_fingerprint,
      rate_limit_kbps: payload.rate_limit_kbps
    };
  }
}

export const gpsSyncService = GPSSyncService.getInstance();

export const __gpsSyncInternals = {
  calculateBackoffDelay
};
