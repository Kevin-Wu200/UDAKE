/**
 * 轨迹管理器
 * 负责轨迹的记录、存储、导出和可视化
 */

import type { Track, TrackPoint, LocationData, AccelerometerData, OrientationData } from '../types/sensor';
import { locationService } from './LocationService';
import { sensorManager } from './SensorManager';

/**
 * 轨迹管理器类
 */
export class TrackManager {
  private static instance: TrackManager;

  // 轨迹列表
  private tracks: Map<string, Track> = new Map();

  // 当前正在记录的轨迹
  private currentTrack: Track | null = null;

  // 轨迹点缓冲区
  private pointBuffer: TrackPoint[] = [];

  // 缓冲区大小
  private readonly BUFFER_SIZE = 100;

  // 事件监听器
  private trackUpdateListeners: Set<(track: Track) => void> = new Set();
  private trackStartListeners: Set<(track: Track) => void> = new Set();
  private trackEndListeners: Set<(track: Track) => void> = new Set();

  // 传感器数据
  private lastAccelerometer: AccelerometerData | null = null;
  private lastOrientation: OrientationData | null = null;
  private locationListener: ((location: LocationData) => void) | null = null;
  private flushTimer: number | null = null;
  private minPointDistanceMeters = 3;
  private minPointIntervalMs = 1500;
  private lastAcceptedPointTime = 0;

  private constructor() {
    this.initializeSensorListeners();
    this.loadTracksFromStorage();
  }

  /**
   * 获取单例实例
   */
  public static getInstance(): TrackManager {
    if (!TrackManager.instance) {
      TrackManager.instance = new TrackManager();
    }
    return TrackManager.instance;
  }

  public setSamplingOptimization(options: {
    minPointDistanceMeters?: number;
    minPointIntervalMs?: number;
  }): void {
    if (typeof options.minPointDistanceMeters === 'number') {
      this.minPointDistanceMeters = Math.max(0, options.minPointDistanceMeters);
    }
    if (typeof options.minPointIntervalMs === 'number') {
      this.minPointIntervalMs = Math.max(200, options.minPointIntervalMs);
    }
  }

  /**
   * 初始化传感器监听器
   */
  private initializeSensorListeners(): void {
    // 监听加速度数据
    sensorManager['startAccelerometer']((data) => {
      this.lastAccelerometer = data;
    });

    // 监听方向数据
    sensorManager['startOrientation']((data) => {
      this.lastOrientation = data;
    });
  }

  /**
   * 从本地存储加载轨迹
   */
  private async loadTracksFromStorage(): Promise<void> {
    try {
      const stored = localStorage.getItem('udake_tracks');
      if (stored) {
        const tracksData = JSON.parse(stored);
        tracksData.forEach((trackData: Track) => {
          this.tracks.set(trackData.id, trackData);
        });
      }
    } catch (error) {
      console.error('加载轨迹失败:', error);
    }
  }

  /**
   * 保存轨迹到本地存储
   */
  private async saveTracksToStorage(): Promise<void> {
    try {
      const tracksData = Array.from(this.tracks.values());
      localStorage.setItem('udake_tracks', JSON.stringify(tracksData));
    } catch (error) {
      console.error('保存轨迹失败:', error);
    }
  }

  /**
   * 创建新轨迹
   */
  public async createTrack(name: string, description?: string, setAsCurrent: boolean = false): Promise<Track> {
    const track: Track = {
      id: `track_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name,
      description,
      points: [],
      startTime: Date.now(),
      endTime: null,
      totalDistance: 0,
      averageSpeed: 0,
    };

    this.tracks.set(track.id, track);
    if (setAsCurrent) {
      this.currentTrack = track;
      this.pointBuffer = [];
    }

    await this.saveTracksToStorage();

    // 通知监听器
    this.trackStartListeners.forEach((listener) => {
      try {
        listener(track);
      } catch (error) {
        console.error('轨迹开始监听器错误:', error);
      }
    });

    return track;
  }

  /**
   * 开始记录轨迹
   */
  public async startRecording(name: string, description?: string): Promise<Track | null> {
    // 检查是否已经在记录
    if (this.currentTrack) {
      console.warn('已经在记录轨迹');
      return this.currentTrack;
    }

    // 创建新轨迹
    const track = await this.createTrack(name, description, true);

    // 开始监听位置
    const success = await locationService.startWatch();
    if (!success) {
      console.error('启动位置监听失败');
      return null;
    }

    // 添加位置监听器
    if (this.locationListener) {
      locationService.removeLocationListener(this.locationListener);
    }
    this.locationListener = (location) => {
      this.addTrackPoint(location);
    };
    locationService.addLocationListener(this.locationListener);

    return track;
  }

  /**
   * 停止记录轨迹
   */
  public async stopRecording(): Promise<void> {
    if (!this.currentTrack) {
      console.warn('没有正在记录的轨迹');
      return;
    }

    // 刷新缓冲区
    await this.flushBuffer();

    // 更新轨迹结束时间
    this.currentTrack.endTime = Date.now();

    // 计算统计数据
    this.calculateTrackStatistics(this.currentTrack);

    // 保存到存储
    await this.saveTracksToStorage();

    // 通知监听器
    this.trackEndListeners.forEach((listener) => {
      try {
        listener(this.currentTrack!);
      } catch (error) {
        console.error('轨迹结束监听器错误:', error);
      }
    });

    // 停止位置监听
    if (this.locationListener) {
      locationService.removeLocationListener(this.locationListener);
      this.locationListener = null;
    }
    await locationService.stopWatch();

    // 清理
    if (this.flushTimer) {
      clearTimeout(this.flushTimer);
      this.flushTimer = null;
    }
    this.currentTrack = null;
    this.pointBuffer = [];
    this.lastAcceptedPointTime = 0;
  }

  /**
   * 添加轨迹点
   */
  private addTrackPoint(location: LocationData): void {
    if (!this.currentTrack) {
      return;
    }
    if (!this.shouldAcceptLocation(location)) {
      return;
    }

    const trackPoint: TrackPoint = {
      location,
      accelerometer: this.lastAccelerometer ? { ...this.lastAccelerometer } : undefined,
      orientation: this.lastOrientation ? { ...this.lastOrientation } : undefined,
      index: this.currentTrack.points.length + this.pointBuffer.length,
      timestamp: Date.now(),
    };

    this.pointBuffer.push(trackPoint);
    this.lastAcceptedPointTime = trackPoint.timestamp;

    // 缓冲区满时刷新
    if (this.pointBuffer.length >= this.BUFFER_SIZE) {
      this.flushBuffer();
    } else {
      this.scheduleDeferredFlush();
    }

    // 通知监听器
    this.trackUpdateListeners.forEach((listener) => {
      try {
        listener(this.currentTrack!);
      } catch (error) {
        console.error('轨迹更新监听器错误:', error);
      }
    });
  }

  private shouldAcceptLocation(location: LocationData): boolean {
    const now = Date.now();
    if (this.lastAcceptedPointTime > 0 && now - this.lastAcceptedPointTime < this.minPointIntervalMs) {
      return false;
    }

    const track = this.currentTrack;
    const lastPoint = this.pointBuffer[this.pointBuffer.length - 1]
      || (track?.points.length ? track.points[track.points.length - 1] : null);
    if (!lastPoint) {
      return true;
    }
    const distance = locationService.calculateDistance(lastPoint.location, location);
    return distance >= this.minPointDistanceMeters;
  }

  private scheduleDeferredFlush(): void {
    if (this.flushTimer) {
      return;
    }
    this.flushTimer = window.setTimeout(() => {
      this.flushTimer = null;
      void this.flushBuffer();
    }, 2000);
  }

  /**
   * 刷新缓冲区
   */
  private async flushBuffer(): Promise<void> {
    if (!this.currentTrack || this.pointBuffer.length === 0) {
      return;
    }
    if (this.flushTimer) {
      clearTimeout(this.flushTimer);
      this.flushTimer = null;
    }

    this.currentTrack.points.push(...this.pointBuffer);
    this.pointBuffer = [];

    await this.saveTracksToStorage();
  }

  /**
   * 计算轨迹统计数据
   */
  private calculateTrackStatistics(track: Track): void {
    if (track.points.length < 2) {
      return;
    }

    // 计算总距离
    let totalDistance = 0;
    for (let i = 1; i < track.points.length; i++) {
      const prev = track.points[i - 1].location;
      const curr = track.points[i].location;
      totalDistance += locationService.calculateDistance(prev, curr);
    }
    track.totalDistance = totalDistance;

    // 计算平均速度
    let duration = (track.endTime || Date.now()) - track.startTime;
    if (duration <= 0 && track.points.length >= 2) {
      const firstPointTime = track.points[0].timestamp;
      const lastPointTime = track.points[track.points.length - 1].timestamp;
      duration = Math.max(0, lastPointTime - firstPointTime);
    }
    if (duration > 0) {
      track.averageSpeed = totalDistance / (duration / 1000); // 米/秒
    }
  }

  /**
   * 获取所有轨迹
   */
  public getAllTracks(): Track[] {
    return Array.from(this.tracks.values()).sort((a, b) => b.startTime - a.startTime);
  }

  /**
   * 获取轨迹
   */
  public getTrack(id: string): Track | undefined {
    return this.tracks.get(id);
  }

  /**
   * 删除轨迹
   */
  public async deleteTrack(id: string): Promise<void> {
    this.tracks.delete(id);
    await this.saveTracksToStorage();
  }

  /**
   * 获取当前正在记录的轨迹
   */
  public getCurrentTrack(): Track | null {
    return this.currentTrack;
  }

  /**
   * 检查是否正在记录
   */
  public isRecording(): boolean {
    return this.currentTrack !== null;
  }

  /**
   * 导出轨迹为 GeoJSON
   */
  public exportToGeoJSON(trackId: string): string | null {
    const track = this.tracks.get(trackId);
    if (!track) {
      return null;
    }

    const geoJSON = {
      type: 'Feature',
      properties: {
        name: track.name,
        description: track.description,
        startTime: track.startTime,
        endTime: track.endTime,
        totalDistance: track.totalDistance,
        averageSpeed: track.averageSpeed,
      },
      geometry: {
        type: 'LineString',
        coordinates: track.points.map((point) => [
          point.location.longitude,
          point.location.latitude,
          point.location.altitude || 0,
        ]),
      },
    };

    return JSON.stringify(geoJSON, null, 2);
  }

  /**
   * 导出轨迹为 GPX
   */
  public exportToGPX(trackId: string): string | null {
    const track = this.tracks.get(trackId);
    if (!track) {
      return null;
    }

    const gpx = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="UDAKE" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>${track.name}</name>
    <desc>${track.description || ''}</desc>
    <time>${new Date(track.startTime).toISOString()}</time>
  </metadata>
  <trk>
    <name>${track.name}</name>
    <trkseg>
${track.points
  .map(
    (point) =>
      `      <trkpt lat="${point.location.latitude}" lon="${point.location.longitude}">
        <ele>${point.location.altitude || 0}</ele>
        <time>${new Date(point.timestamp).toISOString()}</time>
        <speed>${point.location.speed || 0}</speed>
      </trkpt>`
  )
  .join('\n')}
    </trkseg>
  </trk>
</gpx>`;

    return gpx;
  }

  /**
   * 导入轨迹
   */
  public async importTrack(data: string, format: 'geojson' | 'gpx'): Promise<Track | null> {
    try {
      if (format === 'geojson') {
        return this.importFromGeoJSON(data);
      } else if (format === 'gpx') {
        return this.importFromGPX(data);
      }
      return null;
    } catch (error) {
      console.error('导入轨迹失败:', error);
      return null;
    }
  }

  /**
   * 从 GeoJSON 导入轨迹
   */
  private importFromGeoJSON(data: string): Track | null {
    const geoJSON = JSON.parse(data);

    if (geoJSON.type !== 'Feature' || geoJSON.geometry.type !== 'LineString') {
      throw new Error('无效的 GeoJSON 格式');
    }

    const track: Track = {
      id: `track_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name: geoJSON.properties.name || '导入的轨迹',
      description: geoJSON.properties.description,
      points: geoJSON.geometry.coordinates.map((coord: number[], index: number) => ({
        location: {
          latitude: coord[1],
          longitude: coord[0],
          altitude: coord[2] || null,
          accuracy: 0,
          altitudeAccuracy: null,
          heading: null,
          speed: null,
          timestamp: Date.now(),
        },
        index,
        timestamp: Date.now(),
      })),
      startTime: geoJSON.properties.startTime || Date.now(),
      endTime: geoJSON.properties.endTime || Date.now(),
      totalDistance: geoJSON.properties.totalDistance || 0,
      averageSpeed: geoJSON.properties.averageSpeed || 0,
    };

    // 重新计算统计数据
    this.calculateTrackStatistics(track);

    this.tracks.set(track.id, track);
    this.saveTracksToStorage();

    return track;
  }

  /**
   * 从 GPX 导入轨迹
   */
  private importFromGPX(data: string): Track | null {
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(data, 'text/xml');

    const trackName = xmlDoc.querySelector('trk > name')?.textContent || '导入的轨迹';
    const trackDesc = xmlDoc.querySelector('trk > desc')?.textContent || undefined;
    const trackPoints = xmlDoc.querySelectorAll('trkpt');

    const points: TrackPoint[] = [];
    trackPoints.forEach((pt, index) => {
      const lat = parseFloat(pt.getAttribute('lat') || '0');
      const lon = parseFloat(pt.getAttribute('lon') || '0');
      const ele = pt.querySelector('ele')?.textContent;
      const time = pt.querySelector('time')?.textContent;
      const speed = pt.querySelector('speed')?.textContent;

      points.push({
        location: {
          latitude: lat,
          longitude: lon,
          altitude: ele ? parseFloat(ele) : null,
          accuracy: 0,
          altitudeAccuracy: null,
          heading: null,
          speed: speed ? parseFloat(speed) : null,
          timestamp: time ? new Date(time).getTime() : Date.now(),
        },
        index,
        timestamp: time ? new Date(time).getTime() : Date.now(),
      });
    });

    if (points.length === 0) {
      throw new Error('GPX 文件中没有轨迹点');
    }

    const track: Track = {
      id: `track_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name: trackName,
      description: trackDesc,
      points,
      startTime: points[0].timestamp,
      endTime: points[points.length - 1].timestamp,
      totalDistance: 0,
      averageSpeed: 0,
    };

    // 计算统计数据
    this.calculateTrackStatistics(track);

    this.tracks.set(track.id, track);
    this.saveTracksToStorage();

    return track;
  }

  /**
   * 添加轨迹更新监听器
   */
  public addTrackUpdateListener(listener: (track: Track) => void): void {
    this.trackUpdateListeners.add(listener);
  }

  /**
   * 移除轨迹更新监听器
   */
  public removeTrackUpdateListener(listener: (track: Track) => void): void {
    this.trackUpdateListeners.delete(listener);
  }

  /**
   * 添加轨迹开始监听器
   */
  public addTrackStartListener(listener: (track: Track) => void): void {
    this.trackStartListeners.add(listener);
  }

  /**
   * 移除轨迹开始监听器
   */
  public removeTrackStartListener(listener: (track: Track) => void): void {
    this.trackStartListeners.delete(listener);
  }

  /**
   * 添加轨迹结束监听器
   */
  public addTrackEndListener(listener: (track: Track) => void): void {
    this.trackEndListeners.add(listener);
  }

  /**
   * 移除轨迹结束监听器
   */
  public removeTrackEndListener(listener: (track: Track) => void): void {
    this.trackEndListeners.delete(listener);
  }

  /**
   * 清理资源
   */
  public dispose(): void {
    if (this.currentTrack) {
      this.stopRecording();
    }
    if (this.locationListener) {
      locationService.removeLocationListener(this.locationListener);
      this.locationListener = null;
    }
    if (this.flushTimer) {
      clearTimeout(this.flushTimer);
      this.flushTimer = null;
    }

    this.trackUpdateListeners.clear();
    this.trackStartListeners.clear();
    this.trackEndListeners.clear();
  }
}

// 导出单例实例
export const trackManager = TrackManager.getInstance();
