/**
 * 地理围栏可视化组件
 * 在地图上显示地理围栏
 */

import { geofenceManager } from '../services/GeofenceManager';
import type { Geofence } from '../types/sensor';
import { I18nDialog } from './I18nDialog.js';

/**
 * 地理围栏可视化类
 */
export class GeofenceVisualization {
  private map: any; // 地图实例
  private geofenceLayer: any; // 地理围栏图层
  private geofenceCircles: Map<string, any> = new Map(); // 圆形围栏
  private geofencePolygons: Map<string, any> = new Map(); // 多边形围栏
  private geofenceLabels: Map<string, any> = new Map(); // 围栏标签

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
    if (typeof AMap !== 'undefined') {
      this.geofenceLayer = new AMap.LayerGroup();
      this.map.add(this.geofenceLayer);
    }
  }

  /**
   * 初始化监听器
   */
  private initializeListeners(): void {
    // 地理围栏事件监听
    geofenceManager.addGeofenceListener((event) => {
      this.onGeofenceEvent(event);
    });

    // 监听地图点击事件，用于创建围栏
    if (typeof AMap !== 'undefined') {
      this.map.on('click', (e: any) => {
        this.handleMapClick(e);
      });
    }
  }

  /**
   * 地理围栏事件回调
   */
  private onGeofenceEvent(event: any): void {
    const geofence = geofenceManager.getGeofence(event.geofenceId);
    if (!geofence) return;

    // 高亮触发事件的围栏
    this.highlightGeofence(geofence.id, event.type);
  }

  /**
   * 高亮地理围栏
   */
  private highlightGeofence(geofenceId: string, eventType: string): void {
    let color = '#2196F3'; // 默认蓝色
    let opacity = 0.3;

    if (eventType === 'enter') {
      color = '#4CAF50'; // 绿色
      opacity = 0.5;
    } else if (eventType === 'exit') {
      color = '#FF9800'; // 橙色
      opacity = 0.5;
    } else if (eventType === 'dwell') {
      color = '#F44336'; // 红色
      opacity = 0.6;
    }

    // 更新圆形围栏
    if (this.geofenceCircles.has(geofenceId)) {
      const circle = this.geofenceCircles.get(geofenceId);
      circle.setOptions({
        fillColor: color,
        fillOpacity: opacity,
      });

      // 2秒后恢复
      setTimeout(() => {
        circle.setOptions({
          fillColor: '#2196F3',
          fillOpacity: 0.3,
        });
      }, 2000);
    }

    // 更新多边形围栏
    if (this.geofencePolygons.has(geofenceId)) {
      const polygon = this.geofencePolygons.get(geofenceId);
      polygon.setOptions({
        fillColor: color,
        fillOpacity: opacity,
      });

      // 2秒后恢复
      setTimeout(() => {
        polygon.setOptions({
          fillColor: '#2196F3',
          fillOpacity: 0.3,
        });
      }, 2000);
    }
  }

  /**
   * 处理地图点击事件
   */
  private handleMapClick(e: any): void {
    // 检查是否处于创建围栏模式
    const isCreatingGeofence = (window as any).isCreatingGeofence;
    if (!isCreatingGeofence) return;

    // 处理围栏创建
    this.handleCreateGeofence(e.lnglat);
  }

  /**
   * 处理创建围栏
   */
  private async handleCreateGeofence(lnglat: any): Promise<void> {
    // 创建一个临时围栏，等待用户输入半径
    const radius = I18nDialog.prompt('请输入围栏半径（米）：', '100');
    if (!radius) return;

    const radiusNum = parseFloat(radius);
    if (isNaN(radiusNum) || radiusNum <= 0) {
      I18nDialog.alert('请输入有效的半径');
      return;
    }

    const name = I18nDialog.prompt('请输入围栏名称：', `围栏_${new Date().toLocaleString()}`);
    if (!name) return;

    try {
      const geofence = await geofenceManager.createCircularGeofence(
        name,
        lnglat.lat,
        lnglat.lng,
        radiusNum
      );

      this.addGeofence(geofence);
      I18nDialog.alert(`地理围栏 "${name}" 创建成功`);

      // 退出创建模式
      (window as any).isCreatingGeofence = false;
    } catch (error) {
      console.error('创建地理围栏失败:', error);
      I18nDialog.alert('创建地理围栏失败：' + (error as Error).message);
    }
  }

  /**
   * 添加地理围栏
   */
  public addGeofence(geofence: Geofence): void {
    if (geofence.type === 'circular') {
      this.addCircularGeofence(geofence);
    } else if (geofence.type === 'polygon') {
      this.addPolygonGeofence(geofence);
    }

    this.addGeofenceLabel(geofence);
  }

  /**
   * 添加圆形围栏
   */
  private addCircularGeofence(geofence: Geofence): void {
    if (typeof AMap === 'undefined') return;

    const circle = new AMap.Circle({
      center: [geofence.longitude, geofence.latitude],
      radius: geofence.radius,
      strokeColor: '#2196F3',
      strokeWeight: 2,
      strokeOpacity: 0.8,
      fillColor: '#2196F3',
      fillOpacity: 0.3,
      zIndex: 100,
    });

    // 添加点击事件
    circle.on('click', () => {
      this.showGeofenceInfo(geofence);
    });

    // 添加右键菜单
    circle.on('rightclick', () => {
      this.showGeofenceContextMenu(geofence);
    });

    this.geofenceLayer.add(circle);
    this.geofenceCircles.set(geofence.id, circle);
  }

  /**
   * 添加多边形围栏
   */
  private addPolygonGeofence(geofence: Geofence): void {
    if (typeof AMap === 'undefined') return;

    if (!geofence.vertices || geofence.vertices.length < 3) {
      console.error('多边形围栏至少需要3个顶点');
      return;
    }

    const path = geofence.vertices.map((vertex) => [vertex.longitude, vertex.latitude]);

    const polygon = new AMap.Polygon({
      path,
      strokeColor: '#2196F3',
      strokeWeight: 2,
      strokeOpacity: 0.8,
      fillColor: '#2196F3',
      fillOpacity: 0.3,
      zIndex: 100,
    });

    // 添加点击事件
    polygon.on('click', () => {
      this.showGeofenceInfo(geofence);
    });

    // 添加右键菜单
    polygon.on('rightclick', () => {
      this.showGeofenceContextMenu(geofence);
    });

    this.geofenceLayer.add(polygon);
    this.geofencePolygons.set(geofence.id, polygon);
  }

  /**
   * 添加围栏标签
   */
  private addGeofenceLabel(geofence: Geofence): void {
    if (typeof AMap === 'undefined') return;

    const label = new AMap.Marker({
      position: [geofence.longitude, geofence.latitude],
      content: `
        <div style="
          background: white;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: bold;
          box-shadow: 0 1px 3px rgba(0,0,0,0.2);
          white-space: nowrap;
        ">
          ${geofence.name}
        </div>
      `,
      offset: new AMap.Pixel(0, 0),
      zIndex: 101,
    });

    this.geofenceLayer.add(label);
    this.geofenceLabels.set(geofence.id, label);
  }

  /**
   * 显示围栏信息
   */
  private showGeofenceInfo(geofence: Geofence): void {
    const infoWindow = new AMap.InfoWindow({
      content: `
        <div style="padding: 10px; min-width: 200px;">
          <h4 style="margin: 0 0 10px 0;">${geofence.name}</h4>
          ${geofence.description ? `<div style="margin-bottom: 10px; color: #666;">${geofence.description}</div>` : ''}
          <div style="margin-bottom: 5px;">
            <strong>类型:</strong> ${geofence.type === 'circular' ? '圆形' : '多边形'}
          </div>
          <div style="margin-bottom: 5px;">
            <strong>中心:</strong> ${geofence.latitude.toFixed(6)}, ${geofence.longitude.toFixed(6)}
          </div>
          <div style="margin-bottom: 5px;">
            <strong>半径:</strong> ${geofence.radius.toFixed(0)} m
          </div>
          <div style="margin-bottom: 5px;">
            <strong>状态:</strong> ${geofence.enabled ? '启用' : '禁用'}
          </div>
          <div style="margin-top: 10px;">
            <button class="btn btn-sm btn-primary edit-geofence-btn" data-id="${geofence.id}">编辑</button>
            <button class="btn btn-sm btn-danger delete-geofence-btn" data-id="${geofence.id}">删除</button>
          </div>
        </div>
      `,
      offset: new AMap.Pixel(0, -30),
    });

    infoWindow.open(this.map, [geofence.longitude, geofence.latitude]);

    // 附加按钮事件
    setTimeout(() => {
      const editBtn = infoWindow.getContent().querySelector('.edit-geofence-btn');
      const deleteBtn = infoWindow.getContent().querySelector('.delete-geofence-btn');

      editBtn?.addEventListener('click', () => {
        this.handleEditGeofence(geofence.id);
        infoWindow.close();
      });

      deleteBtn?.addEventListener('click', () => {
        this.handleDeleteGeofence(geofence.id);
        infoWindow.close();
      });
    }, 100);
  }

  /**
   * 显示围栏右键菜单
   */
  private showGeofenceContextMenu(geofence: Geofence): void {
    // 创建右键菜单
    const menu = document.createElement('div');
    menu.className = 'geofence-context-menu';
    menu.style.cssText = `
      position: absolute;
      background: white;
      border: 1px solid #ddd;
      border-radius: 4px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.2);
      z-index: 1000;
      min-width: 150px;
    `;

    menu.innerHTML = `
      <div class="menu-item" data-action="edit">编辑围栏</div>
      <div class="menu-item" data-action="toggle">启用/禁用</div>
      <div class="menu-item" data-action="delete">删除围栏</div>
    `;

    document.body.appendChild(menu);

    // 定位菜单
    // 这里需要根据点击位置来定位菜单

    // 附加事件
    menu.querySelectorAll('.menu-item').forEach((item) => {
      item.addEventListener('click', (e) => {
        const action = (e.target as HTMLElement).getAttribute('data-action');
        if (action) {
          this.handleContextMenuAction(geofence.id, action);
        }
        menu.remove();
      });
    });

    // 点击其他地方关闭菜单
    setTimeout(() => {
      document.addEventListener('click', () => menu.remove(), { once: true });
    }, 100);
  }

  /**
   * 处理右键菜单操作
   */
  private async handleContextMenuAction(geofenceId: string, action: string): Promise<void> {
    switch (action) {
      case 'edit':
        this.handleEditGeofence(geofenceId);
        break;
      case 'toggle':
        this.handleToggleGeofence(geofenceId);
        break;
      case 'delete':
        this.handleDeleteGeofence(geofenceId);
        break;
    }
  }

  /**
   * 处理编辑围栏
   */
  private handleEditGeofence(geofenceId: string): void {
    const geofence = geofenceManager.getGeofence(geofenceId);
    if (!geofence) return;

    const newName = I18nDialog.prompt('请输入新的围栏名称：', geofence.name);
    if (!newName) return;

    geofenceManager.updateGeofence(geofenceId, { name: newName });
    this.refreshGeofence(geofenceId);
  }

  /**
   * 处理切换围栏状态
   */
  private async handleToggleGeofence(geofenceId: string): Promise<void> {
    const geofence = geofenceManager.getGeofence(geofenceId);
    if (!geofence) return;

    await geofenceManager.updateGeofence(geofenceId, { enabled: !geofence.enabled });
    this.refreshGeofence(geofenceId);
  }

  /**
   * 处理删除围栏
   */
  private async handleDeleteGeofence(geofenceId: string): Promise<void> {
    if (I18nDialog.confirm('确定要删除这个地理围栏吗？')) {
      await geofenceManager.deleteGeofence(geofenceId);
      this.removeGeofence(geofenceId);
    }
  }

  /**
   * 刷新围栏
   */
  private refreshGeofence(geofenceId: string): void {
    this.removeGeofence(geofenceId);
    const geofence = geofenceManager.getGeofence(geofenceId);
    if (geofence) {
      this.addGeofence(geofence);
    }
  }

  /**
   * 移除围栏
   */
  private removeGeofence(geofenceId: string): void {
    // 移除圆形围栏
    if (this.geofenceCircles.has(geofenceId)) {
      const circle = this.geofenceCircles.get(geofenceId);
      this.geofenceLayer.remove(circle);
      this.geofenceCircles.delete(geofenceId);
    }

    // 移除多边形围栏
    if (this.geofencePolygons.has(geofenceId)) {
      const polygon = this.geofencePolygons.get(geofenceId);
      this.geofenceLayer.remove(polygon);
      this.geofencePolygons.delete(geofenceId);
    }

    // 移除标签
    if (this.geofenceLabels.has(geofenceId)) {
      const label = this.geofenceLabels.get(geofenceId);
      this.geofenceLayer.remove(label);
      this.geofenceLabels.delete(geofenceId);
    }
  }

  /**
   * 显示所有围栏
   */
  public showAllGeofences(): void {
    const geofences = geofenceManager.getAllGeofences();
    geofences.forEach((geofence) => {
      this.addGeofence(geofence);
    });
  }

  /**
   * 清除所有围栏
   */
  public clearAllGeofences(): void {
    this.geofenceLayer.clear();
    this.geofenceCircles.clear();
    this.geofencePolygons.clear();
    this.geofenceLabels.clear();
  }

  /**
   * 清理资源
   */
  public dispose(): void {
    this.clearAllGeofences();
    if (this.geofenceLayer) {
      this.map.remove(this.geofenceLayer);
    }
  }
}

/**
 * 创建地理围栏可视化
 */
export function createGeofenceVisualization(map: any): GeofenceVisualization {
  return new GeofenceVisualization(map);
}