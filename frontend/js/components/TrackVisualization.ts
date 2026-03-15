/**
 * 轨迹可视化组件
 * 在地图上显示轨迹和轨迹点
 */

import { trackManager } from '../services/TrackManager';
import type { Track, TrackPoint } from '../types/sensor';

/**
 * 轨迹可视化类
 */
export class TrackVisualization {
  private map: any; // 地图实例
  private trackLayer: any; // 轨迹图层
  private trackMarkers: Map<string, any> = new Map(); // 轨迹标记
  private currentTrackPolyline: any = null; // 当前轨迹线

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
    trackManager.addTrackUpdateListener((track) => {
      this.updateCurrentTrack(track);
    });

    // 轨迹开始监听
    trackManager.addTrackStartListener((track) => {
      this.onTrackStart(track);
    });

    // 轨迹结束监听
    trackManager.addTrackEndListener((track) => {
      this.onTrackEnd(track);
    });
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

    // 更新轨迹线
    if (typeof AMap !== 'undefined') {
      const path = track.points.map((point) => [
        point.location.longitude,
        point.location.latitude,
      ]);
      this.currentTrackPolyline.setPath(path);
    }

    // 添加最新点的标记
    const lastPoint = track.points[track.points.length - 1];
    this.addTrackMarker(track.id, lastPoint);
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
  public showTrack(trackId: string): void {
    const track = trackManager.getTrack(trackId);
    if (!track || track.points.length === 0) {
      return;
    }

    // 清除之前的轨迹
    this.clearTrack();

    // 创建轨迹线
    if (typeof AMap !== 'undefined') {
      const path = track.points.map((point) => [
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
    const tracks = trackManager.getAllTracks();
    tracks.forEach((track) => {
      this.showTrack(track.id);
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

  /**
   * 清理资源
   */
  public dispose(): void {
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