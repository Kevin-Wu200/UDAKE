/**
 * 位置服务面板组件
 * 提供当前位置显示、轨迹记录控制、地理围栏管理等功能
 */

import { locationService } from '../services/LocationService';
import { trackManager } from '../services/TrackManager';
import { geofenceManager } from '../services/GeofenceManager';
import type { LocationData, Track } from '../types/sensor';
import { I18nDialog } from './I18nDialog.js';

/**
 * 位置服务面板类
 */
export class LocationServicePanel {
  private container: HTMLElement;
  private currentLocation: LocationData | null = null;
  private isRecording: boolean = false;
  private currentTrack: Track | null = null;

  constructor(container: HTMLElement) {
    this.container = container;
    this.render();
    this.initializeListeners();
  }

  /**
   * 渲染面板
   */
  private render(): void {
    this.container.innerHTML = `
      <div class="location-service-panel">
        <div class="panel-header">
          <h3>位置服务</h3>
          <button class="btn-icon close-btn" title="关闭">
            <svg width="16" height="16" viewBox="0 0 16 16">
              <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
            </svg>
          </button>
        </div>

        <div class="panel-content">
          <!-- 当前位置 -->
          <div class="section">
            <h4>当前位置</h4>
            <div class="location-info">
              <div class="location-coordinates">
                <span class="label">纬度:</span>
                <span class="value latitude-value">--</span>
              </div>
              <div class="location-coordinates">
                <span class="label">经度:</span>
                <span class="value longitude-value">--</span>
              </div>
              <div class="location-details">
                <span class="label">精度:</span>
                <span class="value accuracy-value">--</span>
              </div>
              <div class="location-details">
                <span class="label">海拔:</span>
                <span class="value altitude-value">--</span>
              </div>
              <div class="location-details">
                <span class="label">速度:</span>
                <span class="value speed-value">--</span>
              </div>
            </div>
            <div class="location-actions">
              <button class="btn btn-primary" id="get-location-btn">获取位置</button>
              <button class="btn btn-secondary" id="center-on-location-btn">定位到当前位置</button>
            </div>
          </div>

          <!-- 轨迹记录 -->
          <div class="section">
            <h4>轨迹记录</h4>
            <div class="track-info" id="track-info" style="display: none;">
              <div class="track-name">
                <span class="label">轨迹名称:</span>
                <span class="value track-name-value">--</span>
              </div>
              <div class="track-stats">
                <span class="label">点数:</span>
                <span class="value track-points-value">0</span>
              </div>
              <div class="track-stats">
                <span class="label">距离:</span>
                <span class="value track-distance-value">0 m</span>
              </div>
              <div class="track-stats">
                <span class="label">时间:</span>
                <span class="value track-time-value">0:00</span>
              </div>
            </div>
            <div class="track-actions">
              <input type="text" id="track-name-input" placeholder="轨迹名称" class="input-text" />
              <button class="btn btn-success" id="start-track-btn">开始记录</button>
              <button class="btn btn-danger" id="stop-track-btn" style="display: none;">停止记录</button>
            </div>
          </div>

          <!-- 地理围栏 -->
          <div class="section">
            <h4>地理围栏</h4>
            <div class="geofence-list" id="geofence-list">
              <div class="empty-message">暂无地理围栏</div>
            </div>
            <div class="geofence-actions">
              <button class="btn btn-primary" id="add-geofence-btn">添加围栏</button>
            </div>
          </div>
        </div>
      </div>
    `;

    this.attachEventListeners();
  }

  /**
   * 初始化监听器
   */
  private initializeListeners(): void {
    // 位置更新监听
    locationService.addLocationListener((location) => {
      this.updateLocationDisplay(location);
    });

    // 轨迹更新监听
    trackManager.addTrackUpdateListener((track) => {
      this.updateTrackDisplay(track);
    });

    // 轨迹开始监听
    trackManager.addTrackStartListener((track) => {
      this.onTrackStart(track);
    });

    // 轨迹结束监听
    trackManager.addTrackEndListener((track) => {
      this.onTrackEnd(track);
    });

    // 地理围栏事件监听
    geofenceManager.addGeofenceListener((event) => {
      this.onGeofenceEvent(event);
    });
  }

  /**
   * 附加事件监听器
   */
  private attachEventListeners(): void {
    // 关闭按钮
    const closeBtn = this.container.querySelector('.close-btn');
    closeBtn?.addEventListener('click', () => {
      this.container.remove();
    });

    // 获取位置按钮
    const getLocationBtn = this.container.querySelector('#get-location-btn') as HTMLElement;
    getLocationBtn?.addEventListener('click', () => {
      this.handleGetLocation();
    });

    // 定位到当前位置按钮
    const centerOnLocationBtn = this.container.querySelector('#center-on-location-btn') as HTMLElement;
    centerOnLocationBtn?.addEventListener('click', () => {
      this.handleCenterOnLocation();
    });

    // 开始记录按钮
    const startTrackBtn = this.container.querySelector('#start-track-btn') as HTMLElement;
    startTrackBtn?.addEventListener('click', () => {
      this.handleStartTrack();
    });

    // 停止记录按钮
    const stopTrackBtn = this.container.querySelector('#stop-track-btn') as HTMLElement;
    stopTrackBtn?.addEventListener('click', () => {
      this.handleStopTrack();
    });

    // 添加围栏按钮
    const addGeofenceBtn = this.container.querySelector('#add-geofence-btn') as HTMLElement;
    addGeofenceBtn?.addEventListener('click', () => {
      this.handleAddGeofence();
    });
  }

  /**
   * 更新位置显示
   */
  private updateLocationDisplay(location: LocationData): void {
    this.currentLocation = location;

    const latitudeEl = this.container.querySelector('.latitude-value') as HTMLElement;
    const longitudeEl = this.container.querySelector('.longitude-value') as HTMLElement;
    const accuracyEl = this.container.querySelector('.accuracy-value') as HTMLElement;
    const altitudeEl = this.container.querySelector('.altitude-value') as HTMLElement;
    const speedEl = this.container.querySelector('.speed-value') as HTMLElement;

    if (latitudeEl) latitudeEl.textContent = location.latitude.toFixed(6);
    if (longitudeEl) longitudeEl.textContent = location.longitude.toFixed(6);
    if (accuracyEl) accuracyEl.textContent = locationService.formatAccuracy(location.accuracy);
    if (altitudeEl) altitudeEl.textContent = location.altitude ? `${location.altitude.toFixed(1)} m` : '--';
    if (speedEl) speedEl.textContent = location.speed ? `${location.speed.toFixed(1)} m/s` : '--';
  }

  /**
   * 更新轨迹显示
   */
  private updateTrackDisplay(track: Track): void {
    const trackPointsEl = this.container.querySelector('.track-points-value') as HTMLElement;
    const trackDistanceEl = this.container.querySelector('.track-distance-value') as HTMLElement;
    const trackTimeEl = this.container.querySelector('.track-time-value') as HTMLElement;

    if (trackPointsEl) trackPointsEl.textContent = track.points.length.toString();
    if (trackDistanceEl) trackDistanceEl.textContent = `${track.totalDistance.toFixed(1)} m`;
    if (trackTimeEl) {
      const duration = (track.endTime || Date.now()) - track.startTime;
      const minutes = Math.floor(duration / 60000);
      const seconds = Math.floor((duration % 60000) / 1000);
      trackTimeEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }
  }

  /**
   * 轨迹开始回调
   */
  private onTrackStart(track: Track): void {
    this.isRecording = true;
    this.currentTrack = track;

    const trackInfo = this.container.querySelector('#track-info') as HTMLElement;
    const startBtn = this.container.querySelector('#start-track-btn') as HTMLElement;
    const stopBtn = this.container.querySelector('#stop-track-btn') as HTMLElement;
    const trackNameInput = this.container.querySelector('#track-name-input') as HTMLInputElement;

    if (trackInfo) trackInfo.style.display = 'block';
    if (startBtn) startBtn.style.display = 'none';
    if (stopBtn) stopBtn.style.display = 'block';
    if (trackNameInput) trackNameInput.disabled = true;

    const trackNameEl = this.container.querySelector('.track-name-value') as HTMLElement;
    if (trackNameEl) trackNameEl.textContent = track.name;
  }

  /**
   * 轨迹结束回调
   */
  private onTrackEnd(track: Track): void {
    this.isRecording = false;
    this.currentTrack = null;

    const startBtn = this.container.querySelector('#start-track-btn') as HTMLElement;
    const stopBtn = this.container.querySelector('#stop-track-btn') as HTMLElement;
    const trackNameInput = this.container.querySelector('#track-name-input') as HTMLInputElement;

    if (startBtn) startBtn.style.display = 'block';
    if (stopBtn) stopBtn.style.display = 'none';
    if (trackNameInput) {
      trackNameInput.disabled = false;
      trackNameInput.value = '';
    }

    I18nDialog.alert('dialog.location.track.recordCompleted', {
      name: track.name,
      points: track.points.length,
      distance: track.totalDistance.toFixed(1),
      speed: track.averageSpeed.toFixed(2)
    });
  }

  /**
   * 地理围栏事件回调
   */
  private onGeofenceEvent(event: any): void {
    const geofence = geofenceManager.getGeofence(event.geofenceId);
    if (!geofence) return;

    let message = '';
    if (event.type === 'enter') {
      message = `进入地理围栏：${geofence.name}`;
    } else if (event.type === 'exit') {
      message = `退出地理围栏：${geofence.name}`;
    } else if (event.type === 'dwell') {
      message = `在地理围栏内停留：${geofence.name}`;
    }

    // 显示通知
    this.showNotification(message);
  }

  /**
   * 显示通知
   */
  private showNotification(message: string): void {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = 'geofence-notification';
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: #4CAF50;
      color: white;
      padding: 12px 20px;
      border-radius: 4px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.2);
      z-index: 10000;
      animation: slideIn 0.3s ease-out;
    `;

    document.body.appendChild(notification);

    // 3秒后自动移除
    setTimeout(() => {
      notification.style.animation = 'slideOut 0.3s ease-out';
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }

  /**
   * 处理获取位置
   */
  private async handleGetLocation(): Promise<void> {
    try {
      const permission = locationService.checkPermission();
      if (permission !== 'granted') {
        const granted = await locationService.requestPermission();
        if (!granted) {
          I18nDialog.alert('dialog.location.permissionDenied');
          return;
        }
      }

      const location = await locationService.getCurrentLocation();
      this.updateLocationDisplay(location);
    } catch (error) {
      console.error('获取位置失败:', error);
      I18nDialog.alert('dialog.location.getFailed', { error: (error as Error).message });
    }
  }

  /**
   * 处理定位到当前位置
   */
  private async handleCenterOnLocation(): Promise<void> {
    if (!this.currentLocation) {
      I18nDialog.alert('dialog.location.getCurrentFirst');
      return;
    }

    // 触发自定义事件，让地图组件处理
    const event = new CustomEvent('centerOnLocation', {
      detail: {
        latitude: this.currentLocation.latitude,
        longitude: this.currentLocation.longitude,
      },
    });
    document.dispatchEvent(event);
  }

  /**
   * 处理开始记录轨迹
   */
  private async handleStartTrack(): Promise<void> {
    const trackNameInput = this.container.querySelector('#track-name-input') as HTMLInputElement;
    const trackName = trackNameInput?.value.trim() || `轨迹_${new Date().toLocaleString()}`;

    try {
      const track = await trackManager.startRecording(trackName);
      if (!track) {
        I18nDialog.alert('dialog.location.startTrackFailed');
      }
    } catch (error) {
      console.error('开始记录轨迹失败:', error);
      I18nDialog.alert('dialog.location.startTrackFailedWithReason', { error: (error as Error).message });
    }
  }

  /**
   * 处理停止记录轨迹
   */
  private async handleStopTrack(): Promise<void> {
    try {
      await trackManager.stopRecording();
    } catch (error) {
      console.error('停止记录轨迹失败:', error);
      I18nDialog.alert('dialog.location.stopTrackFailed', { error: (error as Error).message });
    }
  }

  /**
   * 处理添加地理围栏
   */
  private handleAddGeofence(): void {
    // 触发自定义事件，让地图组件处理
    const event = new CustomEvent('addGeofence');
    document.dispatchEvent(event);
  }

  /**
   * 更新地理围栏列表
   */
  private updateGeofenceList(): void {
    const geofenceList = this.container.querySelector('#geofence-list') as HTMLElement;
    if (!geofenceList) return;

    const geofences = geofenceManager.getAllGeofences();

    if (geofences.length === 0) {
      geofenceList.innerHTML = '<div class="empty-message">暂无地理围栏</div>';
      return;
    }

    geofenceList.innerHTML = geofences
      .map(
        (geofence) => `
      <div class="geofence-item">
        <div class="geofence-name">${geofence.name}</div>
        <div class="geofence-info">
          <span class="label">类型:</span>
          <span class="value">${geofence.type === 'circular' ? '圆形' : '多边形'}</span>
        </div>
        <div class="geofence-info">
          <span class="label">半径:</span>
          <span class="value">${geofence.radius.toFixed(0)} m</span>
        </div>
        <div class="geofence-actions">
          <button class="btn btn-sm btn-danger delete-geofence-btn" data-id="${geofence.id}">删除</button>
        </div>
      </div>
    `
      )
      .join('');

    // 附加删除按钮事件
    geofenceList.querySelectorAll('.delete-geofence-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const geofenceId = (e.target as HTMLElement).getAttribute('data-id');
        if (geofenceId) {
          this.handleDeleteGeofence(geofenceId);
        }
      });
    });
  }

  /**
   * 处理删除地理围栏
   */
  private async handleDeleteGeofence(geofenceId: string): Promise<void> {
    if (I18nDialog.confirm('dialog.location.deleteGeofenceConfirm')) {
      await geofenceManager.deleteGeofence(geofenceId);
      this.updateGeofenceList();
    }
  }

  /**
   * 清理资源
   */
  public dispose(): void {
    this.container.remove();
  }
}

/**
 * 创建位置服务面板
 */
export function createLocationServicePanel(): LocationServicePanel {
  const container = document.createElement('div');
  container.className = 'location-service-panel-container';
  container.style.cssText = `
    position: fixed;
    top: 80px;
    right: 20px;
    width: 320px;
    max-height: 80vh;
    overflow-y: auto;
    background: white;
    border-radius: 8px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    z-index: 1000;
  `;

  document.body.appendChild(container);
  return new LocationServicePanel(container);
}
