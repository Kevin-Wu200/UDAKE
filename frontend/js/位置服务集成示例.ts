/**
 * 位置服务集成示例
 * 展示如何将位置服务、轨迹管理和地理围栏集成到主应用中
 */

import { locationService } from './services/LocationService';
import { trackManager } from './services/TrackManager';
import { geofenceManager } from './services/GeofenceManager';
import { sensorManager } from './services/SensorManager';
import { createLocationServicePanel } from './components/LocationServicePanel';
import { createTrackVisualization } from './components/TrackVisualization';
import { createGeofenceVisualization } from './components/GeofenceVisualization';

/**
 * 位置服务集成类
 */
export class LocationServiceIntegration {
  private locationServicePanel: any = null;
  private trackVisualization: any = null;
  private geofenceVisualization: any = null;
  private map: any = null;
  private isInitialized: boolean = false;

  constructor(map: any) {
    this.map = map;
  }

  /**
   * 初始化位置服务
   */
  public async initialize(): Promise<void> {
    if (this.isInitialized) {
      console.warn('位置服务已经初始化');
      return;
    }

    try {
      console.log('正在初始化位置服务...');

      // 1. 初始化传感器管理器
      await sensorManager.initializeSensors();
      console.log('传感器管理器初始化完成');

      // 2. 请求位置权限
      const permissionGranted = await locationService.requestPermission();
      if (!permissionGranted) {
        console.warn('位置权限被拒绝，部分功能将不可用');
      } else {
        console.log('位置权限已获取');
      }

      // 3. 创建可视化组件
      this.trackVisualization = createTrackVisualization(this.map);
      this.geofenceVisualization = createGeofenceVisualization(this.map);
      console.log('可视化组件创建完成');

      // 4. 显示现有数据
      this.showExistingData();

      // 5. 设置事件监听
      this.setupEventListeners();

      this.isInitialized = true;
      console.log('位置服务初始化完成');
    } catch (error) {
      console.error('初始化位置服务失败:', error);
      throw error;
    }
  }

  /**
   * 显示现有数据
   */
  private showExistingData(): void {
    // 显示所有轨迹
    const tracks = trackManager.getAllTracks();
    console.log(`找到 ${tracks.length} 个轨迹`);

    // 显示所有地理围栏
    const geofences = geofenceManager.getAllGeofences();
    console.log(`找到 ${geofences.length} 个地理围栏`);

    if (geofences.length > 0) {
      this.geofenceVisualization.showAllGeofences();
    }
  }

  /**
   * 设置事件监听
   */
  private setupEventListeners(): void {
    // 监听定位到当前位置事件
    document.addEventListener('centerOnLocation', (e: any) => {
      this.handleCenterOnLocation(e.detail);
    });

    // 监听添加围栏事件
    document.addEventListener('addGeofence', () => {
      this.handleAddGeofence();
    });

    // 监听显示轨迹事件
    document.addEventListener('showTrack', (e: any) => {
      this.handleShowTrack(e.detail);
    });

    // 监听显示所有轨迹事件
    document.addEventListener('showAllTracks', () => {
      this.trackVisualization.showAllTracks();
    });

    // 监听清除轨迹事件
    document.addEventListener('clearTrack', () => {
      this.trackVisualization.clearTrack();
    });
  }

  /**
   * 处理定位到当前位置
   */
  private handleCenterOnLocation(detail: { latitude: number; longitude: number }): void {
    if (!this.map) return;

    // 根据地图引擎类型实现定位
    if (typeof AMap !== 'undefined') {
      this.map.setCenter([detail.longitude, detail.latitude]);
      this.map.setZoom(15);
    }
  }

  /**
   * 处理添加围栏
   */
  private handleAddGeofence(): void {
    // 进入创建围栏模式
    (window as any).isCreatingGeofence = true;
    alert('请在地图上点击以创建圆形围栏');
  }

  /**
   * 处理显示轨迹
   */
  private handleShowTrack(trackId: string): void {
    this.trackVisualization.showTrack(trackId);
  }

  /**
   * 打开位置服务面板
   */
  public openLocationServicePanel(): void {
    if (this.locationServicePanel) {
      console.warn('位置服务面板已经打开');
      return;
    }

    this.locationServicePanel = createLocationServicePanel();
  }

  /**
   * 关闭位置服务面板
   */
  public closeLocationServicePanel(): void {
    if (this.locationServicePanel) {
      this.locationServicePanel.dispose();
      this.locationServicePanel = null;
    }
  }

  /**
   * 开始记录轨迹
   */
  public async startRecording(trackName?: string): Promise<void> {
    const name = trackName || `轨迹_${new Date().toLocaleString()}`;
    const track = await trackManager.startRecording(name);
    if (!track) {
      throw new Error('开始记录轨迹失败');
    }
    console.log('开始记录轨迹:', track.name);
  }

  /**
   * 停止记录轨迹
   */
  public async stopRecording(): Promise<void> {
    await trackManager.stopRecording();
    console.log('停止记录轨迹');
  }

  /**
   * 获取当前位置
   */
  public async getCurrentLocation(): Promise<any> {
    return await locationService.getCurrentLocation();
  }

  /**
   * 创建圆形围栏
   */
  public async createCircularGeofence(
    name: string,
    latitude: number,
    longitude: number,
    radius: number
  ): Promise<any> {
    const geofence = await geofenceManager.createCircularGeofence(name, latitude, longitude, radius);
    this.geofenceVisualization.addGeofence(geofence);
    return geofence;
  }

  /**
   * 导出轨迹为 GeoJSON
   */
  public exportTrackToGeoJSON(trackId: string): string | null {
    return trackManager.exportToGeoJSON(trackId);
  }

  /**
   * 导出轨迹为 GPX
   */
  public exportTrackToGPX(trackId: string): string | null {
    return trackManager.exportToGPX(trackId);
  }

  /**
   * 获取传感器状态
   */
  public getSensorStatus(): any {
    return sensorManager.getStatus();
  }

  /**
   * 配置位置服务
   */
  public configureLocationService(options: any): void {
    locationService.configure(options);
  }

  /**
   * 清理资源
   */
  public dispose(): void {
    this.closeLocationServicePanel();

    if (this.trackVisualization) {
      this.trackVisualization.dispose();
      this.trackVisualization = null;
    }

    if (this.geofenceVisualization) {
      this.geofenceVisualization.dispose();
      this.geofenceVisualization = null;
    }

    sensorManager.dispose();
    locationService.dispose();
    trackManager.dispose();
    geofenceManager.dispose();

    this.isInitialized = false;
  }
}

/**
 * 创建位置服务集成
 */
export function createLocationServiceIntegration(map: any): LocationServiceIntegration {
  return new LocationServiceIntegration(map);
}

// 使用示例：
/*
// 在主程序中初始化
const map = getMapInstance(); // 获取地图实例
const locationIntegration = createLocationServiceIntegration(map);

// 初始化位置服务
await locationIntegration.initialize();

// 打开位置服务面板
locationIntegration.openLocationServicePanel();

// 开始记录轨迹
await locationIntegration.startRecording('我的轨迹');

// 停止记录轨迹
await locationIntegration.stopRecording();

// 创建圆形围栏
await locationIntegration.createCircularGeofence(
  '采样区域',
  39.9042,
  116.4074,
  500
);

// 导出轨迹
const geojson = locationIntegration.exportTrackToGeoJSON('track_id');
console.log(geojson);

// 获取传感器状态
const status = locationIntegration.getSensorStatus();
console.log(status);
*/