/**
 * 轨迹可视化组件
 * 在地图上显示轨迹和轨迹点
 */

import { trackManager } from '../services/TrackManager';
import type { Track, TrackPoint } from '../types/sensor';

export interface TrackRenderPerformance {
  fps: number;
  renderedPoints: number;
  totalPoints: number;
  lodLevel: 'high' | 'medium' | 'low';
  lastRenderDurationMs: number;
}

/**
 * 轨迹可视化类
 */
export class TrackVisualization {
  private map: any; // 地图实例
  private trackLayer: any; // 轨迹图层
  private trackMarkers: Map<string, any> = new Map(); // 轨迹标记
  private currentTrackPolyline: any = null; // 当前轨迹线
  private updateListener: ((track: Track) => void) | null = null;
  private startListener: ((track: Track) => void) | null = null;
  private endListener: ((track: Track) => void) | null = null;
  private renderTimer: number | null = null;
  private maxRenderablePoints = 4000;
  private fpsSamples: number[] = [];
  private lastRenderTick = 0;
  private renderPerformance: TrackRenderPerformance = {
    fps: 60,
    renderedPoints: 0,
    totalPoints: 0,
    lodLevel: 'high',
    lastRenderDurationMs: 0,
  };

  constructor(map: any) {
    this.map = map;
    this.initializeLayer();
    this.initializeListeners();
  }

  /**
   * 初始化图层
   */
  private initializeLayer(): void {
    // 根据地图引擎类型创建图层
    // 这里需要根据实际使用的地图引擎（高德地图或其他）来调整
    // 以下代码假设使用高德地图
    if (typeof AMap !== 'undefined') {
      this.trackLayer = new AMap.LayerGroup();
      this.map.add(this.trackLayer);
    }
  }

  /**
   * 初始化监听器
   */
  private initializeListeners(): void {
    // 轨迹更新监听
    this.updateListener = (track) => {
      this.updateCurrentTrack(track);
    };
    trackManager.addTrackUpdateListener(this.updateListener);

    // 轨迹开始监听
    this.startListener = (track) => {
      this.onTrackStart(track);
    };
    trackManager.addTrackStartListener(this.startListener);

    // 轨迹结束监听
    this.endListener = (track) => {
      this.onTrackEnd(track);
    };
    trackManager.addTrackEndListener(this.endListener);
  }

  /**
   * 轨迹开始回调
   */
  private onTrackStart(track: Track): void {
    // 创建当前轨迹线
    if (typeof AMap !== 'undefined') {
      this.currentTrackPolyline = new AMap.Polyline({
        path: [],
        strokeColor: '#FF0000',
        strokeWeight: 4,
        strokeOpacity: 0.8,
        showDir: true,
      });
      this.trackLayer.add(this.currentTrackPolyline);
    }
  }

  /**
   * 轨迹结束回调
   */
  private onTrackEnd(track: Track): void {
    // 可以在这里添加完成动画或其他效果
  }

  /**
   * 更新当前轨迹
   */
  private updateCurrentTrack(track: Track): void {
    if (!this.currentTrackPolyline || track.points.length === 0) {
      return;
    }
    if (this.renderTimer) {
      return;
    }
    this.renderTimer = window.setTimeout(() => {
      this.renderTimer = null;
      this.renderCurrentTrack(track);
    }, 120);
  }

  private renderCurrentTrack(track: Track): void {
    const renderStartedAt = performance.now();
    const visiblePoints = this.getVisiblePoints(track.points);
    const { points: lodPoints, lodLevel } = this.applyLOD(visiblePoints);
    const aggregatedPoints = this.aggregateNearbyPoints(lodPoints);

    // 更新轨迹线
    if (typeof AMap !== 'undefined') {
      const path = this.simplifyPath(aggregatedPoints).map((point) => [
        point.location.longitude,
        point.location.latitude,
      ]);
      this.renderPathInChunks(path);
      this.renderPerformance.renderedPoints = path.length;
      this.renderPerformance.totalPoints = track.points.length;
      this.renderPerformance.lodLevel = lodLevel;
    }

    // 添加最新点的标记
    const lastPoint = track.points[track.points.length - 1];
    this.addTrackMarker(track.id, lastPoint);
    this.updateRenderPerformance(performance.now() - renderStartedAt);
  }

  private simplifyPath(points: TrackPoint[]): TrackPoint[] {
    const zoom = Number(this.map?.getZoom?.() ?? 16);
    if (points.length > 20000) {
      const step = Math.ceil(points.length / this.maxRenderablePoints);
      return points.filter((_, index) => index % step === 0);
    }

    const baseTolerance = zoom >= 17 ? 0.00003 : zoom >= 14 ? 0.00008 : 0.0002;
    const simplified = this.douglasPeucker(points, baseTolerance);

    if (simplified.length <= this.maxRenderablePoints) {
      return simplified;
    }
    const step = Math.ceil(simplified.length / this.maxRenderablePoints);
    const sampled: TrackPoint[] = [];
    for (let i = 0; i < simplified.length; i += step) {
      sampled.push(simplified[i]);
    }
    const last = simplified[simplified.length - 1];
    if (sampled[sampled.length - 1] !== last) {
      sampled.push(last);
    }
    return sampled;
  }

  private renderPathInChunks(path: number[][]): void {
    if (!this.currentTrackPolyline) {
      return;
    }
    if (path.length <= 600) {
      this.currentTrackPolyline.setPath(path);
      return;
    }

    const merged: number[][] = [];
    let cursor = 0;
    const flush = () => {
      const nextChunk = path.slice(cursor, cursor + 600);
      merged.push(...nextChunk);
      this.currentTrackPolyline.setPath(merged);
      cursor += 600;
      if (cursor < path.length) {
        requestAnimationFrame(flush);
      }
    };
    requestAnimationFrame(flush);
  }

  private getVisiblePoints(points: TrackPoint[]): TrackPoint[] {
    const bounds = this.map?.getBounds?.();
    if (!bounds || typeof bounds.contains !== 'function') {
      return points;
    }

    const visible = points.filter((point) => {
      try {
        return bounds.contains([point.location.longitude, point.location.latitude]);
      } catch {
        return true;
      }
    });
    if (visible.length === 0) {
      return points;
    }
    return visible;
  }

  private applyLOD(points: TrackPoint[]): { points: TrackPoint[]; lodLevel: 'high' | 'medium' | 'low' } {
    const zoom = Number(this.map?.getZoom?.() ?? 16);
    if (zoom >= 17) {
      return { points, lodLevel: 'high' };
    }

    if (zoom >= 14) {
      const step = Math.max(1, Math.floor(points.length / 5000));
      return {
        points: step <= 1 ? points : points.filter((_, index) => index % step === 0),
        lodLevel: 'medium'
      };
    }

    const step = Math.max(2, Math.floor(points.length / 1500));
    return {
      points: points.filter((_, index) => index % step === 0),
      lodLevel: 'low'
    };
  }

  private aggregateNearbyPoints(points: TrackPoint[]): TrackPoint[] {
    if (points.length < 3) {
      return points;
    }

    const zoom = Number(this.map?.getZoom?.() ?? 16);
    if (zoom >= 16) {
      return points;
    }

    const precision = zoom >= 14 ? 5 : 4;
    const grouped = new Map<string, TrackPoint>();
    for (const point of points) {
      const latKey = point.location.latitude.toFixed(precision);
      const lngKey = point.location.longitude.toFixed(precision);
      const key = `${latKey}:${lngKey}`;
      const existing = grouped.get(key);
      if (!existing || point.timestamp > existing.timestamp) {
        grouped.set(key, point);
      }
    }

    const aggregated = Array.from(grouped.values()).sort((a, b) => a.timestamp - b.timestamp);
    if (aggregated.length >= 2 && aggregated.length < points.length) {
      return aggregated;
    }
    if (aggregated.length === 1 && points.length >= 2) {
      return [points[0], points[points.length - 1]];
    }
    return points;
  }

  private douglasPeucker(points: TrackPoint[], tolerance: number): TrackPoint[] {
    if (points.length <= 2) {
      return points;
    }

    let maxDistance = 0;
    let splitIndex = 0;
    const start = points[0];
    const end = points[points.length - 1];

    for (let i = 1; i < points.length - 1; i++) {
      const distance = this.perpendicularDistance(points[i], start, end);
      if (distance > maxDistance) {
        maxDistance = distance;
        splitIndex = i;
      }
    }

    if (maxDistance <= tolerance) {
      return [start, end];
    }

    const left = this.douglasPeucker(points.slice(0, splitIndex + 1), tolerance);
    const right = this.douglasPeucker(points.slice(splitIndex), tolerance);
    return left.slice(0, -1).concat(right);
  }

  private perpendicularDistance(point: TrackPoint, lineStart: TrackPoint, lineEnd: TrackPoint): number {
    const x = point.location.longitude;
    const y = point.location.latitude;
    const x1 = lineStart.location.longitude;
    const y1 = lineStart.location.latitude;
    const x2 = lineEnd.location.longitude;
    const y2 = lineEnd.location.latitude;

    const dx = x2 - x1;
    const dy = y2 - y1;
    if (dx === 0 && dy === 0) {
      return Math.hypot(x - x1, y - y1);
    }

    const numerator = Math.abs(dy * x - dx * y + x2 * y1 - y2 * x1);
    const denominator = Math.sqrt(dx * dx + dy * dy);
    return numerator / denominator;
  }

  private updateRenderPerformance(lastRenderDurationMs: number): void {
    const now = performance.now();
    if (this.lastRenderTick > 0) {
      const delta = now - this.lastRenderTick;
      const fps = delta > 0 ? 1000 / delta : 60;
      this.fpsSamples.push(fps);
      if (this.fpsSamples.length > 30) {
        this.fpsSamples.shift();
      }
      const avgFps = this.fpsSamples.reduce((sum, value) => sum + value, 0) / this.fpsSamples.length;
      this.renderPerformance.fps = Math.round(avgFps);
    }
    this.lastRenderTick = now;
    this.renderPerformance.lastRenderDurationMs = Number(lastRenderDurationMs.toFixed(2));
  }

  /**
   * 添加轨迹标记
   */
  private addTrackMarker(trackId: string, point: TrackPoint): void {
    if (typeof AMap === 'undefined') return;

    const markerId = `${trackId}_${point.index}`;

    // 如果标记已存在，则更新位置
    if (this.trackMarkers.has(markerId)) {
      const marker = this.trackMarkers.get(markerId);
      marker.setPosition([point.location.longitude, point.location.latitude]);
      return;
    }

    // 创建新标记
    const marker = new AMap.Marker({
      position: [point.location.longitude, point.location.latitude],
      title: `轨迹点 ${point.index}`,
      content: this.createMarkerContent(point),
      offset: new AMap.Pixel(-12, -12),
    });

    // 添加点击事件
    marker.on('click', () => {
      this.showPointInfo(point);
    });

    this.trackLayer.add(marker);
    this.trackMarkers.set(markerId, marker);
  }

  /**
   * 创建标记内容
   */
  private createMarkerContent(point: TrackPoint): string {
    const speed = point.location.speed ? `${point.location.speed.toFixed(1)} m/s` : '--';
    const altitude = point.location.altitude ? `${point.location.altitude.toFixed(1)} m` : '--';

    return `
      <div style="
        width: 24px;
        height: 24px;
        background: #FF0000;
        border: 2px solid white;
        border-radius: 50%;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 10px;
        font-weight: bold;
      ">
        ${point.index + 1}
      </div>
    `;
  }

  /**
   * 显示轨迹点信息
   */
  private showPointInfo(point: TrackPoint): void {
    const infoWindow = new AMap.InfoWindow({
      content: `
        <div style="padding: 10px; min-width: 200px;">
          <h4 style="margin: 0 0 10px 0;">轨迹点 ${point.index + 1}</h4>
          <div style="margin-bottom: 5px;">
            <strong>纬度:</strong> ${point.location.latitude.toFixed(6)}
          </div>
          <div style="margin-bottom: 5px;">
            <strong>经度:</strong> ${point.location.longitude.toFixed(6)}
          </div>
          <div style="margin-bottom: 5px;">
            <strong>海拔:</strong> ${point.location.altitude ? point.location.altitude.toFixed(1) + ' m' : '--'}
          </div>
          <div style="margin-bottom: 5px;">
            <strong>速度:</strong> ${point.location.speed ? point.location.speed.toFixed(1) + ' m/s' : '--'}
          </div>
          <div style="margin-bottom: 5px;">
            <strong>精度:</strong> ${point.location.accuracy.toFixed(1)} m
          </div>
          <div style="margin-bottom: 5px;">
            <strong>时间:</strong> ${new Date(point.timestamp).toLocaleString()}
          </div>
        </div>
      `,
      offset: new AMap.Pixel(0, -30),
    });

    infoWindow.open(this.map, [point.location.longitude, point.location.latitude]);
  }

  /**
   * 显示轨迹
   */
  public showTrack(trackId: string, clearPrevious: boolean = true): void {
    const track = trackManager.getTrack(trackId);
    if (!track || track.points.length === 0) {
      return;
    }

    // 清除之前的轨迹
    if (clearPrevious) {
      this.clearTrack();
    }

    // 创建轨迹线
    if (typeof AMap !== 'undefined') {
      const path = this.simplifyPath(track.points).map((point) => [
        point.location.longitude,
        point.location.latitude,
      ]);

      const polyline = new AMap.Polyline({
        path,
        strokeColor: '#2196F3',
        strokeWeight: 3,
        strokeOpacity: 0.8,
        showDir: true,
      });

      this.trackLayer.add(polyline);

      // 添加起点和终点标记
      this.addEndpointMarkers(track);
    }
  }

  /**
   * 添加起点和终点标记
   */
  private addEndpointMarkers(track: Track): void {
    if (track.points.length === 0) return;

    const startPoint = track.points[0];
    const endPoint = track.points[track.points.length - 1];

    // 起点标记
    const startMarker = new AMap.Marker({
      position: [startPoint.location.longitude, startPoint.location.latitude],
      title: '起点',
      content: `
        <div style="
          width: 24px;
          height: 24px;
          background: #4CAF50;
          border: 2px solid white;
          border-radius: 50%;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-size: 12px;
          font-weight: bold;
        ">
          S
        </div>
      `,
      offset: new AMap.Pixel(-12, -12),
    });

    // 终点标记
    const endMarker = new AMap.Marker({
      position: [endPoint.location.longitude, endPoint.location.latitude],
      title: '终点',
      content: `
        <div style="
          width: 24px;
          height: 24px;
          background: #F44336;
          border: 2px solid white;
          border-radius: 50%;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-size: 12px;
          font-weight: bold;
        ">
          E
        </div>
      `,
      offset: new AMap.Pixel(-12, -12),
    });

    this.trackLayer.add([startMarker, endMarker]);
  }

  /**
   * 清除轨迹
   */
  public clearTrack(): void {
    if (this.trackLayer) {
      this.trackLayer.clear();
    }
    this.trackMarkers.clear();
    this.currentTrackPolyline = null;
  }

  /**
   * 显示所有轨迹
   */
  public showAllTracks(): void {
    this.clearTrack();
    const tracks = trackManager.getAllTracks();
    tracks.forEach((track) => {
      this.showTrack(track.id, false);
    });
  }

  /**
   * 导出轨迹为图片
   */
  public exportTrackAsImage(trackId: string): void {
    // 使用地图API的截图功能
    if (typeof AMap !== 'undefined') {
      this.map.plugin('AMap.Geolocation', () => {
        // 这里可以根据需要实现截图功能
        console.log('导出轨迹图片:', trackId);
      });
    }
  }

  public getRenderPerformance(): TrackRenderPerformance {
    return { ...this.renderPerformance };
  }

  /**
   * 清理资源
   */
  public dispose(): void {
    if (this.updateListener) {
      trackManager.removeTrackUpdateListener(this.updateListener);
      this.updateListener = null;
    }
    if (this.startListener) {
      trackManager.removeTrackStartListener(this.startListener);
      this.startListener = null;
    }
    if (this.endListener) {
      trackManager.removeTrackEndListener(this.endListener);
      this.endListener = null;
    }
    if (this.renderTimer) {
      clearTimeout(this.renderTimer);
      this.renderTimer = null;
    }
    this.clearTrack();
    if (this.trackLayer) {
      this.map.remove(this.trackLayer);
    }
  }
}

/**
 * 创建轨迹可视化
 */
export function createTrackVisualization(map: any): TrackVisualization {
  return new TrackVisualization(map);
}
