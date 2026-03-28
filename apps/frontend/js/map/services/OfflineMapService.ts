import { SmartCache } from '../../utils/cache/SmartCache.js';

export type OfflineMapDownloadState = 'idle' | 'downloading' | 'paused' | 'completed' | 'failed';

export interface TileCoordinate {
  z: number;
  x: number;
  y: number;
}

export interface OfflineMapRegion {
  id: string;
  name: string;
  bbox: [number, number, number, number];
  minZoom: number;
  maxZoom: number;
  version: string;
  tileTemplate: string;
  state: OfflineMapDownloadState;
  totalTiles: number;
  downloadedTiles: number;
  failedTiles: number;
  createdAt: number;
  updatedAt: number;
}

export interface OfflineMapDownloadProgress {
  taskId: string;
  total: number;
  downloaded: number;
  failed: number;
  percent: number;
  state: OfflineMapDownloadState;
}

export interface OfflineMapStorageStats {
  totalTiles: number;
  totalBytes: number;
  maxBytes: number;
  usageRate: number;
  memoryHitRate: number;
  memoryHits: number;
  diskHits: number;
  misses: number;
}

interface TileRecord {
  id: string;
  z: number;
  x: number;
  y: number;
  version: string;
  blob: Blob;
  contentType: string;
  sizeBytes: number;
  sourceUrl: string;
  createdAt: number;
  lastAccessedAt: number;
  hitCount: number;
}

interface TileMetaRecord {
  id: string;
  z: number;
  x: number;
  y: number;
  version: string;
  sizeBytes: number;
  createdAt: number;
  lastAccessedAt: number;
  hitCount: number;
}

interface InternalDownloadTask {
  id: string;
  regionId: string;
  state: OfflineMapDownloadState;
  queue: TileCoordinate[];
  currentIndex: number;
  downloaded: number;
  failed: number;
  onProgress?: (progress: OfflineMapDownloadProgress) => void;
  running: boolean;
}

const DB_NAME = 'udake_offline_map';
const DB_VERSION = 1;
const STORES = {
  tiles: 'tiles',
  tileMeta: 'tileMeta',
  regions: 'regions',
  settings: 'settings'
} as const;

const SETTING_MAX_BYTES = 'storage_limit_bytes';
const SETTING_TOTAL_BYTES = 'storage_total_bytes';

const DEFAULT_TILE_TEMPLATE = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const DEFAULT_MAX_STORAGE_BYTES = 512 * 1024 * 1024;
const CONCURRENT_DOWNLOADS = 6;

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function lonToTileX(lon: number, zoom: number): number {
  const n = 2 ** zoom;
  return Math.floor(((lon + 180) / 360) * n);
}

function latToTileY(lat: number, zoom: number): number {
  const clamped = clamp(lat, -85.05112878, 85.05112878);
  const rad = (clamped * Math.PI) / 180;
  const n = 2 ** zoom;
  return Math.floor((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) * n / 2);
}

function buildTileKey(version: string, tile: TileCoordinate): string {
  return `${version}:${tile.z}:${tile.x}:${tile.y}`;
}

function applyTemplate(template: string, tile: TileCoordinate): string {
  return template
    .replace('{z}', String(tile.z))
    .replace('{x}', String(tile.x))
    .replace('{y}', String(tile.y));
}

function nowTs(): number {
  return Date.now();
}

export class OfflineMapService {
  private static instance: OfflineMapService;

  private db: IDBDatabase | null = null;
  private initialized = false;
  private memoryCache = new SmartCache<string, Blob>({
    maxSize: 2000,
    ttl: 1000 * 60 * 60 * 24,
    strategy: 'hybrid',
    persistence: false,
    enableAutoCleanup: true
  });
  private tasks: Map<string, InternalDownloadTask> = new Map();
  private memoryHits = 0;
  private diskHits = 0;
  private misses = 0;

  static getInstance(): OfflineMapService {
    if (!OfflineMapService.instance) {
      OfflineMapService.instance = new OfflineMapService();
    }
    return OfflineMapService.instance;
  }

  async init(): Promise<void> {
    if (this.initialized) {
      return;
    }
    this.db = await this.openDB();
    this.initialized = true;

    const maxBytes = await this.getSettingNumber(SETTING_MAX_BYTES, DEFAULT_MAX_STORAGE_BYTES);
    await this.setSettingNumber(SETTING_MAX_BYTES, maxBytes);

    const totalBytes = await this.computeTotalBytesFromMeta();
    await this.setSettingNumber(SETTING_TOTAL_BYTES, totalBytes);
  }

  async createRegionDownloadTask(
    params: {
      name: string;
      bbox: [number, number, number, number];
      minZoom: number;
      maxZoom: number;
      version?: string;
      tileTemplate?: string;
    },
    onProgress?: (progress: OfflineMapDownloadProgress) => void
  ): Promise<string> {
    await this.init();

    const version = params.version || 'v1';
    const tileTemplate = params.tileTemplate || DEFAULT_TILE_TEMPLATE;
    const queue = this.generateTiles(params.bbox, params.minZoom, params.maxZoom);
    const id = `offline_region_${nowTs()}_${Math.random().toString(36).slice(2, 8)}`;

    const region: OfflineMapRegion = {
      id,
      name: params.name,
      bbox: params.bbox,
      minZoom: params.minZoom,
      maxZoom: params.maxZoom,
      version,
      tileTemplate,
      state: queue.length === 0 ? 'completed' : 'downloading',
      totalTiles: queue.length,
      downloadedTiles: 0,
      failedTiles: 0,
      createdAt: nowTs(),
      updatedAt: nowTs()
    };
    await this.put(STORES.regions, region);

    const task: InternalDownloadTask = {
      id,
      regionId: id,
      state: region.state,
      queue,
      currentIndex: 0,
      downloaded: 0,
      failed: 0,
      onProgress,
      running: false
    };
    this.tasks.set(id, task);

    if (queue.length > 0) {
      void this.processTask(task, tileTemplate, version);
    }

    return id;
  }

  pauseTask(taskId: string): boolean {
    const task = this.tasks.get(taskId);
    if (!task || task.state !== 'downloading') {
      return false;
    }
    task.state = 'paused';
    this.emitTaskProgress(task);
    void this.updateRegionProgress(task);
    return true;
  }

  async resumeTask(taskId: string): Promise<boolean> {
    const task = this.tasks.get(taskId);
    if (!task || task.state !== 'paused') {
      return false;
    }

    const region = await this.getRegion(task.regionId);
    if (!region) {
      return false;
    }

    task.state = 'downloading';
    task.running = false;
    void this.processTask(task, region.tileTemplate, region.version);
    return true;
  }

  getTaskProgress(taskId: string): OfflineMapDownloadProgress | null {
    const task = this.tasks.get(taskId);
    if (!task) {
      return null;
    }

    return {
      taskId,
      total: task.queue.length,
      downloaded: task.downloaded,
      failed: task.failed,
      percent: task.queue.length > 0 ? ((task.downloaded + task.failed) / task.queue.length) * 100 : 100,
      state: task.state
    };
  }

  async getRegion(regionId: string): Promise<OfflineMapRegion | null> {
    await this.init();
    const row = await this.get<OfflineMapRegion>(STORES.regions, regionId);
    return row || null;
  }

  async listRegions(): Promise<OfflineMapRegion[]> {
    await this.init();
    const rows = await this.getAll<OfflineMapRegion>(STORES.regions);
    return rows.sort((a, b) => b.updatedAt - a.updatedAt);
  }

  async getTile(tile: TileCoordinate, version: string = 'v1'): Promise<Blob | null> {
    await this.init();
    const key = buildTileKey(version, tile);

    const memoryBlob = this.memoryCache.get(key);
    if (memoryBlob) {
      this.memoryHits += 1;
      await this.touchTileMeta(key);
      return memoryBlob;
    }

    const record = await this.get<TileRecord>(STORES.tiles, key);
    if (record?.blob) {
      this.diskHits += 1;
      this.memoryCache.set(key, record.blob);
      await this.touchTileMeta(key);
      return record.blob;
    }

    this.misses += 1;
    return null;
  }

  async warmupRegion(regionId: string, limit: number = 200): Promise<{ loaded: number; skipped: number }> {
    await this.init();
    const region = await this.getRegion(regionId);
    if (!region) {
      return { loaded: 0, skipped: 0 };
    }

    const tiles = this.generateTiles(region.bbox, region.minZoom, region.maxZoom)
      .slice(0, Math.max(1, limit));
    const keys = tiles.map(tile => buildTileKey(region.version, tile));

    return this.memoryCache.warmupByKeys(keys, async (key) => {
      const record = await this.get<TileRecord>(STORES.tiles, key);
      if (record?.blob) {
        await this.touchTileMeta(key);
        return record.blob;
      }
      return undefined;
    }, 1000 * 60 * 60 * 24);
  }

  async checkRegionUpdate(regionId: string, latestVersion: string): Promise<{ needUpdate: boolean; currentVersion?: string }> {
    const region = await this.getRegion(regionId);
    if (!region) {
      return { needUpdate: false };
    }

    return {
      needUpdate: region.version !== latestVersion,
      currentVersion: region.version
    };
  }

  async applyIncrementalUpdate(
    regionId: string,
    changedTiles: TileCoordinate[],
    latestVersion: string,
    onProgress?: (progress: OfflineMapDownloadProgress) => void
  ): Promise<{ updated: number; failed: number }> {
    await this.init();
    const region = await this.getRegion(regionId);
    if (!region || changedTiles.length === 0) {
      return { updated: 0, failed: 0 };
    }

    let updated = 0;
    let failed = 0;

    for (let i = 0; i < changedTiles.length; i += 1) {
      const tile = changedTiles[i];
      const ok = await this.downloadAndStoreTile(tile, region.tileTemplate, latestVersion, true);
      if (ok) {
        updated += 1;
      } else {
        failed += 1;
      }

      if (onProgress) {
        onProgress({
          taskId: regionId,
          total: changedTiles.length,
          downloaded: updated,
          failed,
          percent: ((updated + failed) / changedTiles.length) * 100,
          state: failed > 0 ? 'downloading' : 'downloading'
        });
      }
    }

    await this.put(STORES.regions, {
      ...region,
      version: latestVersion,
      updatedAt: nowTs()
    });

    return { updated, failed };
  }

  async setStorageLimitMB(limitMB: number): Promise<void> {
    const limitBytes = Math.max(50, Math.floor(limitMB)) * 1024 * 1024;
    await this.setSettingNumber(SETTING_MAX_BYTES, limitBytes);
    const totalBytes = await this.getSettingNumber(SETTING_TOTAL_BYTES, 0);
    if (totalBytes > limitBytes) {
      await this.ensureStorageSpace(0);
    }
  }

  async getStorageStats(): Promise<OfflineMapStorageStats> {
    await this.init();
    const totalBytes = await this.getSettingNumber(SETTING_TOTAL_BYTES, 0);
    const maxBytes = await this.getSettingNumber(SETTING_MAX_BYTES, DEFAULT_MAX_STORAGE_BYTES);
    const tileMeta = await this.getAll<TileMetaRecord>(STORES.tileMeta);
    const memoryRequests = this.memoryHits + this.diskHits + this.misses;

    return {
      totalTiles: tileMeta.length,
      totalBytes,
      maxBytes,
      usageRate: maxBytes > 0 ? totalBytes / maxBytes : 0,
      memoryHitRate: memoryRequests > 0 ? this.memoryHits / memoryRequests : 0,
      memoryHits: this.memoryHits,
      diskHits: this.diskHits,
      misses: this.misses
    };
  }

  private async processTask(task: InternalDownloadTask, tileTemplate: string, version: string): Promise<void> {
    if (task.running || task.state !== 'downloading') {
      return;
    }

    task.running = true;
    try {
      while (task.currentIndex < task.queue.length && task.state === 'downloading') {
        const batch = task.queue.slice(task.currentIndex, task.currentIndex + CONCURRENT_DOWNLOADS);
        const results = await Promise.all(batch.map(tile => this.downloadAndStoreTile(tile, tileTemplate, version)));

        for (const ok of results) {
          if (ok) {
            task.downloaded += 1;
          } else {
            task.failed += 1;
          }
        }

        task.currentIndex += batch.length;
        this.emitTaskProgress(task);
        await this.updateRegionProgress(task);
      }

      if (task.state === 'downloading' && task.currentIndex >= task.queue.length) {
        task.state = task.failed > 0 ? 'failed' : 'completed';
        this.emitTaskProgress(task);
        await this.updateRegionProgress(task);
      }
    } finally {
      task.running = false;
    }
  }

  private emitTaskProgress(task: InternalDownloadTask): void {
    if (!task.onProgress) {
      return;
    }
    const total = task.queue.length;
    task.onProgress({
      taskId: task.id,
      total,
      downloaded: task.downloaded,
      failed: task.failed,
      percent: total > 0 ? ((task.downloaded + task.failed) / total) * 100 : 100,
      state: task.state
    });
  }

  private async updateRegionProgress(task: InternalDownloadTask): Promise<void> {
    const region = await this.get<OfflineMapRegion>(STORES.regions, task.regionId);
    if (!region) {
      return;
    }

    await this.put(STORES.regions, {
      ...region,
      downloadedTiles: task.downloaded,
      failedTiles: task.failed,
      state: task.state,
      updatedAt: nowTs()
    });
  }

  private async downloadAndStoreTile(
    tile: TileCoordinate,
    template: string,
    version: string,
    forceRefresh: boolean = false
  ): Promise<boolean> {
    const tileId = buildTileKey(version, tile);

    if (!forceRefresh) {
      const existed = await this.get<TileRecord>(STORES.tiles, tileId);
      if (existed?.blob) {
        this.memoryCache.set(tileId, existed.blob);
        await this.touchTileMeta(tileId);
        return true;
      }
    }

    const url = applyTemplate(template, tile);

    try {
      const response = await fetch(url, { method: 'GET' });
      if (!response.ok) {
        return false;
      }
      const blob = await response.blob();
      const sizeBytes = blob.size || 0;

      await this.ensureStorageSpace(sizeBytes);

      const record: TileRecord = {
        id: tileId,
        z: tile.z,
        x: tile.x,
        y: tile.y,
        version,
        blob,
        contentType: blob.type || 'image/png',
        sizeBytes,
        sourceUrl: url,
        createdAt: nowTs(),
        lastAccessedAt: nowTs(),
        hitCount: 0
      };

      const meta: TileMetaRecord = {
        id: tileId,
        z: tile.z,
        x: tile.x,
        y: tile.y,
        version,
        sizeBytes,
        createdAt: record.createdAt,
        lastAccessedAt: record.lastAccessedAt,
        hitCount: 0
      };

      await this.put(STORES.tiles, record);
      await this.put(STORES.tileMeta, meta);
      await this.bumpTotalBytes(sizeBytes);
      this.memoryCache.set(tileId, blob);
      return true;
    } catch (error) {
      console.warn('[OfflineMapService] 下载瓦片失败:', tile, error);
      return false;
    }
  }

  private async ensureStorageSpace(incomingBytes: number): Promise<void> {
    const maxBytes = await this.getSettingNumber(SETTING_MAX_BYTES, DEFAULT_MAX_STORAGE_BYTES);
    let totalBytes = await this.getSettingNumber(SETTING_TOTAL_BYTES, 0);

    if (incomingBytes <= 0 || totalBytes + incomingBytes <= maxBytes) {
      return;
    }

    const metaRows = await this.getAll<TileMetaRecord>(STORES.tileMeta);
    metaRows.sort((a, b) => a.lastAccessedAt - b.lastAccessedAt);

    for (const row of metaRows) {
      if (totalBytes + incomingBytes <= maxBytes) {
        break;
      }
      await this.delete(STORES.tiles, row.id);
      await this.delete(STORES.tileMeta, row.id);
      this.memoryCache.delete(row.id);
      totalBytes = Math.max(0, totalBytes - (row.sizeBytes || 0));
    }

    await this.setSettingNumber(SETTING_TOTAL_BYTES, totalBytes);
  }

  private async touchTileMeta(tileId: string): Promise<void> {
    const meta = await this.get<TileMetaRecord>(STORES.tileMeta, tileId);
    if (!meta) {
      return;
    }

    await this.put(STORES.tileMeta, {
      ...meta,
      lastAccessedAt: nowTs(),
      hitCount: (meta.hitCount || 0) + 1
    });
  }

  private generateTiles(
    bbox: [number, number, number, number],
    minZoom: number,
    maxZoom: number
  ): TileCoordinate[] {
    const [minLng, minLat, maxLng, maxLat] = bbox;
    const tiles: TileCoordinate[] = [];

    for (let z = minZoom; z <= maxZoom; z += 1) {
      const xStart = Math.min(lonToTileX(minLng, z), lonToTileX(maxLng, z));
      const xEnd = Math.max(lonToTileX(minLng, z), lonToTileX(maxLng, z));
      const yStart = Math.min(latToTileY(maxLat, z), latToTileY(minLat, z));
      const yEnd = Math.max(latToTileY(maxLat, z), latToTileY(minLat, z));

      for (let x = xStart; x <= xEnd; x += 1) {
        for (let y = yStart; y <= yEnd; y += 1) {
          tiles.push({ z, x, y });
        }
      }
    }

    return tiles;
  }

  private async openDB(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;

        if (!db.objectStoreNames.contains(STORES.tiles)) {
          db.createObjectStore(STORES.tiles, { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains(STORES.tileMeta)) {
          db.createObjectStore(STORES.tileMeta, { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains(STORES.regions)) {
          db.createObjectStore(STORES.regions, { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains(STORES.settings)) {
          db.createObjectStore(STORES.settings, { keyPath: 'id' });
        }
      };

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error('IndexedDB 打开失败'));
    });
  }

  private getStore(storeName: string, mode: IDBTransactionMode): IDBObjectStore {
    if (!this.db) {
      throw new Error('OfflineMapService 尚未初始化');
    }
    return this.db.transaction(storeName, mode).objectStore(storeName);
  }

  private wrapReq<T>(req: IDBRequest): Promise<T> {
    return new Promise((resolve, reject) => {
      req.onsuccess = (event: any) => {
        resolve((event?.target?.result ?? (req as any).result) as T);
      };
      req.onerror = () => {
        reject(req.error || new Error('IndexedDB 请求失败'));
      };
    });
  }

  private async get<T>(storeName: string, id: string): Promise<T | undefined> {
    const store = this.getStore(storeName, 'readonly');
    return this.wrapReq<T | undefined>(store.get(id));
  }

  private async getAll<T>(storeName: string): Promise<T[]> {
    const store = this.getStore(storeName, 'readonly');
    const rows = await this.wrapReq<T[]>(store.getAll());
    return rows || [];
  }

  private async put<T>(storeName: string, value: T): Promise<void> {
    const store = this.getStore(storeName, 'readwrite');
    await this.wrapReq(store.put(value as any));
  }

  private async delete(storeName: string, id: string): Promise<void> {
    const store = this.getStore(storeName, 'readwrite');
    await this.wrapReq(store.delete(id));
  }

  private async getSettingNumber(key: string, defaultValue: number): Promise<number> {
    const row = await this.get<{ id: string; value: number }>(STORES.settings, key);
    if (!row || typeof row.value !== 'number' || Number.isNaN(row.value)) {
      return defaultValue;
    }
    return row.value;
  }

  private async setSettingNumber(key: string, value: number): Promise<void> {
    await this.put(STORES.settings, { id: key, value });
  }

  private async bumpTotalBytes(delta: number): Promise<void> {
    const current = await this.getSettingNumber(SETTING_TOTAL_BYTES, 0);
    await this.setSettingNumber(SETTING_TOTAL_BYTES, Math.max(0, current + delta));
  }

  private async computeTotalBytesFromMeta(): Promise<number> {
    const rows = await this.getAll<TileMetaRecord>(STORES.tileMeta);
    return rows.reduce((sum, row) => sum + (row.sizeBytes || 0), 0);
  }
}

export const offlineMapService = OfflineMapService.getInstance();

export const __offlineMapInternals = {
  lonToTileX,
  latToTileY,
  buildTileKey,
  applyTemplate
};
