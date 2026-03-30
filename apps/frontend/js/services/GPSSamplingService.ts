import type { LocationData } from '../types/sensor.js';
import { locationService } from './LocationService.js';
import { gpsSyncService } from './GPSSyncService.js';
import { OfflineManager } from '../utils/OfflineManager.js';

export interface GPSSamplingPoint {
  id: string;
  projectId: string;
  latitude: number;
  longitude: number;
  accuracy: number;
  altitude: number | null;
  speed: number | null;
  heading: number | null;
  attributes: Record<string, any>;
  collectedAt: number;
  updatedAt: number;
  version: number;
  source: 'mobile' | 'web';
}

export interface GPSCollectOptions {
  projectId: string;
  attributes?: Record<string, any>;
  minAccuracy?: number;
}

export interface GPSBatchCollectOptions extends GPSCollectOptions {
  targetCount: number;
  intervalMs?: number;
  lowPowerMode?: boolean;
  minDistanceMeters?: number;
}

export class GPSSamplingService {
  private static instance: GPSSamplingService;
  private lastCollectedLocation: { latitude: number; longitude: number } | null = null;

  public static getInstance(): GPSSamplingService {
    if (!GPSSamplingService.instance) {
      GPSSamplingService.instance = new GPSSamplingService();
    }
    return GPSSamplingService.instance;
  }

  public async collectSample(options: GPSCollectOptions): Promise<GPSSamplingPoint> {
    const location = await locationService.getCurrentLocation();
    if (!locationService.isValidLocation(location)) {
      throw new Error('GPS 采样失败：当前位置无效');
    }

    const threshold = options.minAccuracy ?? 50;
    if (location.accuracy > threshold) {
      throw new Error(`GPS 精度不足（当前 ±${location.accuracy.toFixed(1)}m，要求 ≤ ${threshold}m）`);
    }

    const sample = this.buildSample(location, options);
    await OfflineManager.saveGPSSample(sample);

    let synced = false;
    if (OfflineManager.isOnline) {
      synced = await gpsSyncService.syncSample(sample);
    }
    if (!synced) {
      await OfflineManager.enqueue({ type: 'gps_sync', payload: sample });
    }

    return sample;
  }

  public async collectBatchSamples(options: GPSBatchCollectOptions): Promise<GPSSamplingPoint[]> {
    const targetCount = Math.max(1, Math.min(5000, Math.floor(options.targetCount || 1)));
    const intervalMs = Math.max(500, Math.floor(options.intervalMs ?? (options.lowPowerMode ? 6000 : 2000)));
    const minDistanceMeters = Math.max(0, Math.floor(options.minDistanceMeters ?? (options.lowPowerMode ? 8 : 2)));
    const minAccuracy = options.lowPowerMode ? Math.max(options.minAccuracy ?? 80, 50) : options.minAccuracy;

    const collected: GPSSamplingPoint[] = [];
    for (let i = 0; i < targetCount; i += 1) {
      const location = await locationService.getCurrentLocation();
      if (!locationService.isValidLocation(location)) {
        continue;
      }
      if (typeof minAccuracy === 'number' && location.accuracy > minAccuracy) {
        continue;
      }
      const sample = this.buildSample(location, options);
      if (this.shouldKeepBatchPoint(sample, minDistanceMeters)) {
        collected.push(sample);
      }
      if (i < targetCount - 1) {
        await new Promise((resolve) => setTimeout(resolve, intervalMs));
      }
    }

    if (collected.length > 0) {
      await OfflineManager.saveGPSSamples(collected);
      if (OfflineManager.isOnline) {
        await gpsSyncService.syncSamples(collected, { adaptive: true, diffSync: true });
      }
    }
    return collected;
  }

  public async getSamples(projectId: string, limit: number = 200): Promise<GPSSamplingPoint[]> {
    const rows = await OfflineManager.getGPSSamples(projectId, limit);
    return rows.map((row: any) => ({
      id: row.id,
      projectId: row.projectId || row.project_id || projectId,
      latitude: Number(row.latitude),
      longitude: Number(row.longitude),
      accuracy: Number(row.accuracy),
      altitude: row.altitude ?? null,
      speed: row.speed ?? null,
      heading: row.heading ?? null,
      attributes: row.attributes || {},
      collectedAt: Number(row.collectedAt || row.collected_at || Date.now()),
      updatedAt: Number(row.updatedAt || row.updated_at || Date.now()),
      version: Number(row.version || 1),
      source: (row.source || 'mobile') as 'mobile' | 'web'
    }));
  }

  public async exportProjectAsGeoJSON(projectId: string): Promise<string> {
    const points = await this.getSamples(projectId, 100000);
    const geojson = {
      type: 'FeatureCollection',
      features: points.map((sample) => ({
        type: 'Feature',
        properties: {
          id: sample.id,
          projectId: sample.projectId,
          accuracy: sample.accuracy,
          altitude: sample.altitude,
          speed: sample.speed,
          heading: sample.heading,
          collectedAt: sample.collectedAt,
          updatedAt: sample.updatedAt,
          version: sample.version,
          source: sample.source,
          ...sample.attributes
        },
        geometry: {
          type: 'Point',
          coordinates: [sample.longitude, sample.latitude, sample.altitude || 0]
        }
      }))
    };
    return JSON.stringify(geojson, null, 2);
  }

  public async exportProjectAsCSV(projectId: string): Promise<string> {
    const points = await this.getSamples(projectId, 100000);
    const baseColumns = [
      'id',
      'projectId',
      'latitude',
      'longitude',
      'accuracy',
      'altitude',
      'speed',
      'heading',
      'collectedAt',
      'updatedAt',
      'version',
      'source'
    ];
    const attributeKeys = new Set<string>();
    points.forEach((point) => {
      Object.keys(point.attributes || {}).forEach((key) => attributeKeys.add(key));
    });

    const columns = [...baseColumns, ...Array.from(attributeKeys)];
    const csvRows = [columns.join(',')];
    points.forEach((point) => {
      const rowValues = columns.map((column) => {
        const value = (point as any)[column] ?? point.attributes?.[column] ?? '';
        const text = typeof value === 'string' ? value : String(value);
        return `"${text.replace(/"/g, '""')}"`;
      });
      csvRows.push(rowValues.join(','));
    });
    return csvRows.join('\n');
  }

  public async downloadExport(projectId: string, format: 'geojson' | 'csv'): Promise<void> {
    const content = format === 'geojson'
      ? await this.exportProjectAsGeoJSON(projectId)
      : await this.exportProjectAsCSV(projectId);
    const mimeType = format === 'geojson' ? 'application/geo+json' : 'text/csv;charset=utf-8';
    const blob = new Blob([content], { type: mimeType });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${projectId}_gps_samples.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  }

  public parseAttributes(raw: string): Record<string, any> {
    const text = raw.trim();
    if (!text) {
      return {};
    }
    try {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed;
      }
      throw new Error('属性格式必须是 JSON 对象');
    } catch (error) {
      throw new Error(`自定义属性解析失败: ${(error as Error).message}`);
    }
  }

  public getAccuracyTag(location: LocationData | null): 'high' | 'medium' | 'low' {
    if (!location) return 'low';
    if (location.accuracy <= 5) return 'high';
    if (location.accuracy <= 15) return 'medium';
    return 'low';
  }

  private buildSample(location: LocationData, options: GPSCollectOptions): GPSSamplingPoint {
    const now = Date.now();
    return {
      id: `gps_${now}_${Math.random().toString(36).slice(2, 8)}`,
      projectId: options.projectId || 'default_mobile_project',
      latitude: location.latitude,
      longitude: location.longitude,
      accuracy: location.accuracy,
      altitude: location.altitude ?? null,
      speed: location.speed ?? null,
      heading: location.heading ?? null,
      attributes: options.attributes || {},
      collectedAt: now,
      updatedAt: now,
      version: 1,
      source: 'mobile'
    };
  }

  private shouldKeepBatchPoint(sample: GPSSamplingPoint, minDistanceMeters: number): boolean {
    if (!this.lastCollectedLocation) {
      this.lastCollectedLocation = { latitude: sample.latitude, longitude: sample.longitude };
      return true;
    }
    const distance = locationService.calculateDistance(this.lastCollectedLocation, {
      latitude: sample.latitude,
      longitude: sample.longitude
    });
    if (distance < minDistanceMeters) {
      return false;
    }
    this.lastCollectedLocation = { latitude: sample.latitude, longitude: sample.longitude };
    return true;
  }
}

export const gpsSamplingService = GPSSamplingService.getInstance();
