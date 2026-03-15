/**
 * 地理围栏管理器
 * 负责地理围栏的创建、监控和通知
 */

import type { Geofence, GeofenceEvent, LocationData } from '../types/sensor';
import { locationService } from './LocationService';

/**
 * 地理围栏管理器类
 */
export class GeofenceManager {
  private static instance: GeofenceManager;

  // 地理围栏列表
  private geofences: Map<string, Geofence> = new Map();

  // 活动围栏（正在监控的围栏）
  private activeGeofences: Map<string, Geofence> = new Map();

  // 事件列表
  private events: GeofenceEvent[] = new Array<GeofenceEvent>();

  // 位置状态缓存（记录每个围栏的进入/退出状态）
  private geofenceStates: Map<string, { inside: boolean; dwellTime: number }> = new Map();

  // 事件监听器
  private geofenceListeners: Set<(event: GeofenceEvent) => void> = new Set();

  // 是否正在监控
  private isMonitoring: boolean = false;

  // 监控间隔
  private readonly MONITOR_INTERVAL = 1000; // 1秒

  // 监控定时器
  private monitorTimer: number | null = null;

  private constructor() {
    this.loadGeofencesFromStorage();
  }

  /**
   * 获取单例实例
   */
  public static getInstance(): GeofenceManager {
    if (!GeofenceManager.instance) {
      GeofenceManager.instance = new GeofenceManager();
    }
    return GeofenceManager.instance;
  }

  /**
   * 从本地存储加载地理围栏
   */
  private async loadGeofencesFromStorage(): Promise<void> {
    try {
      const stored = localStorage.getItem('udake_geofences');
      if (stored) {
        const geofencesData = JSON.parse(stored);
        geofencesData.forEach((geofenceData: Geofence) => {
          this.geofences.set(geofenceData.id, geofenceData);
        });
      }

      // 加载事件
      const eventsStored = localStorage.getItem('udake_geofence_events');
      if (eventsStored) {
        this.events = JSON.parse(eventsStored);
      }
    } catch (error) {
      console.error('加载地理围栏失败:', error);
    }
  }

  /**
   * 保存地理围栏到本地存储
   */
  private async saveGeofencesToStorage(): Promise<void> {
    try {
      const geofencesData = Array.from(this.geofences.values());
      localStorage.setItem('udake_geofences', JSON.stringify(geofencesData));
    } catch (error) {
      console.error('保存地理围栏失败:', error);
    }
  }

  /**
   * 保存事件到本地存储
   */
  private async saveEventsToStorage(): Promise<void> {
    try {
      // 只保留最近1000个事件
      const recentEvents = this.events.slice(-1000);
      localStorage.setItem('udake_geofence_events', JSON.stringify(recentEvents));
    } catch (error) {
      console.error('保存事件失败:', error);
    }
  }

  /**
   * 创建圆形地理围栏
   */
  public async createCircularGeofence(
    name: string,
    latitude: number,
    longitude: number,
    radius: number,
    options: Partial<Geofence> = {}
  ): Promise<Geofence> {
    const geofence: Geofence = {
      id: `geofence_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name,
      latitude,
      longitude,
      radius,
      type: 'circular',
      enabled: true,
      notifyOnEnter: options.notifyOnEnter ?? true,
      notifyOnExit: options.notifyOnExit ?? true,
      notifyOnDwell: options.notifyOnDwell ?? false,
      dwellDelay: options.dwellDelay || 30000, // 默认30秒
      description: options.description,
    };

    this.geofences.set(geofence.id, geofence);
    await this.saveGeofencesToStorage();

    // 如果围栏已启用，则激活它
    if (geofence.enabled) {
      this.activateGeofence(geofence.id);
    }

    return geofence;
  }

  /**
   * 创建多边形地理围栏
   */
  public async createPolygonGeofence(
    name: string,
    vertices: Array<{ latitude: number; longitude: number }>,
    options: Partial<Geofence> = {}
  ): Promise<Geofence> {
    if (vertices.length < 3) {
      throw new Error('多边形至少需要3个顶点');
    }

    // 计算中心点
    const center = this.calculatePolygonCenter(vertices);

    // 计算最大半径
    const maxRadius = this.calculatePolygonMaxRadius(center, vertices);

    const geofence: Geofence = {
      id: `geofence_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name,
      latitude: center.latitude,
      longitude: center.longitude,
      radius: maxRadius,
      type: 'polygon',
      vertices,
      enabled: true,
      notifyOnEnter: options.notifyOnEnter ?? true,
      notifyOnExit: options.notifyOnExit ?? true,
      notifyOnDwell: options.notifyOnDwell ?? false,
      dwellDelay: options.dwellDelay || 30000,
      description: options.description,
    };

    this.geofences.set(geofence.id, geofence);
    await this.saveGeofencesToStorage();

    // 如果围栏已启用，则激活它
    if (geofence.enabled) {
      this.activateGeofence(geofence.id);
    }

    return geofence;
  }

  /**
   * 计算多边形中心点
   */
  private calculatePolygonCenter(
    vertices: Array<{ latitude: number; longitude: number }>
  ): { latitude: number; longitude: number } {
    let sumLat = 0;
    let sumLon = 0;

    vertices.forEach((vertex) => {
      sumLat += vertex.latitude;
      sumLon += vertex.longitude;
    });

    return {
      latitude: sumLat / vertices.length,
      longitude: sumLon / vertices.length,
    };
  }

  /**
   * 计算多边形最大半径
   */
  private calculatePolygonMaxRadius(
    center: { latitude: number; longitude: number },
    vertices: Array<{ latitude: number; longitude: number }>
  ): number {
    let maxDistance = 0;

    vertices.forEach((vertex) => {
      const distance = locationService.calculateDistance(center, vertex);
      if (distance > maxDistance) {
        maxDistance = distance;
      }
    });

    return maxDistance;
  }

  /**
   * 激活地理围栏
   */
  public activateGeofence(id: string): void {
    const geofence = this.geofences.get(id);
    if (!geofence || !geofence.enabled) {
      return;
    }

    this.activeGeofences.set(id, geofence);
    this.geofenceStates.set(id, { inside: false, dwellTime: 0 });

    // 如果还没有开始监控，则启动监控
    if (!this.isMonitoring) {
      this.startMonitoring();
    }
  }

  /**
   * 停用地理围栏
   */
  public deactivateGeofence(id: string): void {
    this.activeGeofences.delete(id);
    this.geofenceStates.delete(id);

    // 如果没有活动围栏，则停止监控
    if (this.activeGeofences.size === 0) {
      this.stopMonitoring();
    }
  }

  /**
   * 启动监控
   */
  private startMonitoring(): void {
    if (this.isMonitoring) {
      return;
    }

    this.isMonitoring = true;

    // 启动位置监听
    locationService.startWatch();

    // 添加位置监听器
    locationService.addLocationListener((location) => {
      this.checkGeofences(location);
    });

    // 启动定时检查（用于停留检测）
    this.monitorTimer = window.setInterval(() => {
      this.checkDwellGeofences();
    }, this.MONITOR_INTERVAL);
  }

  /**
   * 停止监控
   */
  private stopMonitoring(): void {
    if (!this.isMonitoring) {
      return;
    }

    this.isMonitoring = false;

    // 停止位置监听
    locationService.stopWatch();

    // 清除定时器
    if (this.monitorTimer) {
      clearInterval(this.monitorTimer);
      this.monitorTimer = null;
    }
  }

  /**
   * 检查地理围栏
   */
  private checkGeofences(location: LocationData): void {
    this.activeGeofences.forEach((geofence, id) => {
      const isInside = this.isInsideGeofence(location, geofence);
      const state = this.geofenceStates.get(id);

      if (!state) {
        return;
      }

      // 检查进入事件
      if (isInside && !state.inside && geofence.notifyOnEnter) {
        this.triggerEvent(id, 'enter', location);
        state.inside = true;
        state.dwellTime = 0;
      }

      // 检查退出事件
      if (!isInside && state.inside && geofence.notifyOnExit) {
        this.triggerEvent(id, 'exit', location);
        state.inside = false;
        state.dwellTime = 0;
      }

      // 更新停留时间
      if (isInside && state.inside) {
        state.dwellTime += this.MONITOR_INTERVAL;
      }

      this.geofenceStates.set(id, state);
    });
  }

  /**
   * 检查停留地理围栏
   */
  private checkDwellGeofences(): void {
    this.activeGeofences.forEach((geofence, id) => {
      const state = this.geofenceStates.get(id);
      if (!state || !state.inside || !geofence.notifyOnDwell || !geofence.dwellDelay) {
        return;
      }

      // 检查是否达到停留时间
      if (state.dwellTime >= geofence.dwellDelay) {
        const location = locationService.getLastLocation();
        if (location) {
          this.triggerEvent(id, 'dwell', location);
          // 重置停留时间
          state.dwellTime = 0;
          this.geofenceStates.set(id, state);
        }
      }
    });
  }

  /**
   * 检查位置是否在地理围栏内
   */
  private isInsideGeofence(location: LocationData, geofence: Geofence): boolean {
    if (geofence.type === 'circular') {
      return this.isInsideCircle(location, geofence);
    } else if (geofence.type === 'polygon') {
      return this.isInsidePolygon(location, geofence);
    }
    return false;
  }

  /**
   * 检查位置是否在圆形围栏内
   */
  private isInsideCircle(location: LocationData, geofence: Geofence): boolean {
    const distance = locationService.calculateDistance(
      { latitude: location.latitude, longitude: location.longitude },
      { latitude: geofence.latitude, longitude: geofence.longitude }
    );

    return distance <= geofence.radius;
  }

  /**
   * 检查位置是否在多边形围栏内（射线法）
   */
  private isInsidePolygon(location: LocationData, geofence: Geofence): boolean {
    if (!geofence.vertices || geofence.vertices.length < 3) {
      return false;
    }

    const x = location.longitude;
    const y = location.latitude;
    const vertices = geofence.vertices;

    let inside = false;

    for (let i = 0, j = vertices.length - 1; i < vertices.length; j = i++) {
      const xi = vertices[i].longitude;
      const yi = vertices[i].latitude;
      const xj = vertices[j].longitude;
      const yj = vertices[j].latitude;

      const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;

      if (intersect) {
        inside = !inside;
      }
    }

    return inside;
  }

  /**
   * 触发地理围栏事件
   */
  private triggerEvent(geofenceId: string, type: 'enter' | 'exit' | 'dwell', location: LocationData): void {
    const event: GeofenceEvent = {
      id: `event_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      geofenceId,
      type,
      timestamp: Date.now(),
      location,
    };

    this.events.push(event);
    this.saveEventsToStorage();

    // 通知监听器
    this.geofenceListeners.forEach((listener) => {
      try {
        listener(event);
      } catch (error) {
        console.error('地理围栏事件监听器错误:', error);
      }
    });
  }

  /**
   * 获取所有地理围栏
   */
  public getAllGeofences(): Geofence[] {
    return Array.from(this.geofences.values());
  }

  /**
   * 获取地理围栏
   */
  public getGeofence(id: string): Geofence | undefined {
    return this.geofences.get(id);
  }

  /**
   * 更新地理围栏
   */
  public async updateGeofence(id: string, updates: Partial<Geofence>): Promise<void> {
    const geofence = this.geofences.get(id);
    if (!geofence) {
      throw new Error('地理围栏不存在');
    }

    const updatedGeofence = { ...geofence, ...updates };
    this.geofences.set(id, updatedGeofence);
    await this.saveGeofencesToStorage();

    // 如果围栏已启用，重新激活
    if (updatedGeofence.enabled) {
      this.activateGeofence(id);
    } else {
      this.deactivateGeofence(id);
    }
  }

  /**
   * 删除地理围栏
   */
  public async deleteGeofence(id: string): Promise<void> {
    this.deactivateGeofence(id);
    this.geofences.delete(id);
    await this.saveGeofencesToStorage();
  }

  /**
   * 获取所有事件
   */
  public getEvents(geofenceId?: string): GeofenceEvent[] {
    if (geofenceId) {
      return this.events.filter((event) => event.geofenceId === geofenceId);
    }
    return [...this.events];
  }

  /**
   * 清除事件
   */
  public async clearEvents(geofenceId?: string): Promise<void> {
    if (geofenceId) {
      this.events = this.events.filter((event) => event.geofenceId !== geofenceId);
    } else {
      this.events = [];
    }
    await this.saveEventsToStorage();
  }

  /**
   * 添加地理围栏事件监听器
   */
  public addGeofenceListener(listener: (event: GeofenceEvent) => void): void {
    this.geofenceListeners.add(listener);
  }

  /**
   * 移除地理围栏事件监听器
   */
  public removeGeofenceListener(listener: (event: GeofenceEvent) => void): void {
    this.geofenceListeners.delete(listener);
  }

  /**
   * 清理资源
   */
  public dispose(): void {
    this.stopMonitoring();
    this.geofenceListeners.clear();
  }
}

// 导出单例实例
export const geofenceManager = GeofenceManager.getInstance();