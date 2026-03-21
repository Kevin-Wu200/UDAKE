/**
 * 高德地图引擎
 * 使用高德 JS API v2.0 实现地图功能
 */

import { BaseMapEngine } from './BaseMapEngine';
import { initAMap } from '../../config/amap.config.js';
import { LocationPermissionManager } from '../../utils/locationPermissionManager.js';
import type { Bounds, MapInitOptions, ZoomCallback, MoveCallback } from '../../../types/map-engine';

// 高德地图全局类型声明
declare global {
    interface Window {
        AMap: any;
    }
}

/**
 * 高德地图引擎
 * 使用高德 JS API v2.0 实现地图功能
 */
export class AMapEngine extends BaseMapEngine {
    /** 地图实例 */
    map: any;

    /** 初始中心点 */
    initialCenter: [number, number] | null;

    /** 初始缩放级别 */
    initialZoom: number | null;

    /** 图层管理 */
    polygons: any[];
    markers: any[];

    /** 定位蓝点标记 */
    locationMarker: any;

    /** 定位监控 ID */
    watchId: number | null;

    /** 定位权限状态 */
    locationPermissionGranted: boolean;

    constructor(options: any = {}) {
        super();
        this.supportsCustomReset = true;

        this.initialCenter = null;
        this.initialZoom = null;
        this.map = null;
        this.polygons = [];
        this.markers = [];
        this.locationMarker = null;
        this.watchId = null;
        this.locationPermissionGranted = false;
    }

    /**
     * 初始化地图
     * 使用新的 amap.config.js 配置
     */
    async init(container: HTMLElement | string, options: MapInitOptions = {}): Promise<void> {
        // 获取容器 ID
        let containerId: string;
        if (typeof container === 'string') {
            containerId = container;
        } else {
            containerId = container.id;
        }

        if (!containerId) {
            throw new Error('地图容器 ID 不存在');
        }

        // 使用新的配置方法初始化地图
        this.map = await initAMap(containerId);

        // 保存初始状态
        this.initialCenter = this.map.getCenter();
        this.initialZoom = this.map.getZoom();

        // 应用自定义配置
        if (options.zoom) {
            this.map.setZoom(options.zoom);
        }
        if (options.center) {
            this.map.setCenter(options.center);
        }

        // 设置地图属性
        this.map.setStatus({
            resizeEnable: true,
            animateEnable: true,
            zoomEnable: true
        });

        // 设置缩放范围
        this.map.setZooms([3, 18]);

        // 绑定事件
        this.map.on('zoomend', () => {
            this.triggerZoomCallbacks(this.map.getZoom());
        });

        this.map.on('moveend', () => {
            const center = this.map.getCenter();
            this.triggerMoveCallbacks([center.lng, center.lat]);
        });

        console.log('✅ 高德地图引擎初始化完成');
    }

    /**
     * 设置中心点
     */
    setCenter(center: [number, number]): void {
        this.map.setCenter(center);
    }

    /**
     * 获取中心点
     */
    getCenter(): [number, number] {
        const center = this.map.getCenter();
        return [center.lng, center.lat];
    }

    /**
     * 设置缩放级别
     */
    setZoom(zoom: number): void {
        this.map.setZoom(zoom);
    }

    /**
     * 获取缩放级别
     */
    getZoom(): number {
        return this.map.getZoom();
    }

    /**
     * 获取定位蓝点位置
     * @returns 定位蓝点位置 [经度, 纬度]，如果不存在则返回 null
     */
    getLocationPosition(): [number, number] | null {
        if (this.locationMarker && this.locationMarker.position) {
            return this.locationMarker.position;
        }
        return null;
    }

    /**
     * 平滑移动到定位蓝点位置
     * @returns 是否成功移动
     */
    panToLocation(): boolean {
        const position = this.getLocationPosition();
        
        if (!position) {
            console.warn('⚠️ 定位蓝点不存在，无法回到中心');
            return false;
        }

        // 平滑移动到定位蓝点位置
        if (this.map && this.map.setCenter) {
            this.map.setCenter(position);
            console.log('✅ 地图已移动到定位蓝点位置:', position);
            return true;
        }

        return false;
    }

    /**
     * 适配到指定边界
     */
    fitToBounds(bounds: Bounds): void {
        const { minLng, minLat, maxLng, maxLat } = bounds;
        const amapBounds = new (window as any).AMap.Bounds(
            [minLng, minLat],
            [maxLng, maxLat]
        );
        this.map.setBounds(amapBounds);
    }

    /**
     * 添加 Polygon（区域采样）
     */
    addPolygon(geojson: any): void {
        // 清除旧的 polygon
        this.clearPolygons();

        // 解析 GeoJSON
        const coordinates = this.parseGeoJSONCoordinates(geojson);

        if (coordinates.length === 0) {
            console.warn('GeoJSON 无有效坐标');
            return;
        }

        // 创建 Polygon
        coordinates.forEach(path => {
            const polygon = new (window as any).AMap.Polygon({
                path: path,
                strokeColor: '#3366FF',
                strokeWeight: 2,
                strokeOpacity: 0.8,
                fillColor: '#3366FF',
                fillOpacity: 0.2
            });

            this.map.add(polygon);
            this.polygons.push(polygon);
        });

        // 自动适配视图
        if (this.polygons.length > 0) {
            this.map.setFitView(this.polygons);
        }
    }

    /**
     * 解析 GeoJSON 坐标
     */
    parseGeoJSONCoordinates(geojson: any): number[][][] {
        const coordinates: number[][][] = [];

        if (geojson.type === 'FeatureCollection') {
            geojson.features.forEach((feature: any) => {
                const coords = this.extractCoordinates(feature.geometry);
                if (coords) coordinates.push(...coords);
            });
        } else if (geojson.type === 'Feature') {
            const coords = this.extractCoordinates(geojson.geometry);
            if (coords) coordinates.push(...coords);
        } else {
            const coords = this.extractCoordinates(geojson);
            if (coords) coordinates.push(...coords);
        }

        return coordinates;
    }

    /**
     * 提取几何坐标
     */
    extractCoordinates(geometry: any): number[][][] | null {
        if (!geometry) return null;

        switch (geometry.type) {
            case 'Polygon':
                return geometry.coordinates.map((ring: number[][]) =>
                    ring.map(coord => [coord[0], coord[1]])
                );
            case 'MultiPolygon':
                return geometry.coordinates.flatMap((polygon: number[][][]) =>
                    polygon.map(ring => ring.map(coord => [coord[0], coord[1]]))
                );
            default:
                return null;
        }
    }

    /**
     * 清除所有 Polygon
     */
    clearPolygons(): void {
        this.polygons.forEach(polygon => {
            this.map.remove(polygon);
        });
        this.polygons = [];
    }

    /**
     * 添加采样点 Marker
     */
    addMarker(position: [number, number], options: any = {}): any {
        const marker = new (window as any).AMap.Marker({
            position: position,
            icon: options.icon,
            title: options.title,
            extData: options.data
        });

        this.map.add(marker);
        this.markers.push(marker);

        return marker;
    }

    /**
     * 批量添加采样点
     */
    addMarkers(points: any[]): void {
        points.forEach(point => {
            this.addMarker(point.position, point.options);
        });
    }

    /**
     * 清除所有 Marker
     */
    clearMarkers(): void {
        this.markers.forEach(marker => {
            this.map.remove(marker);
        });
        this.markers = [];
    }

    /**
     * 启用定位功能
     * @param requestPermission 是否请求定位权限（首次使用时设为 true）
     * @returns 是否成功启用定位
     */
    async enableLocation(requestPermission: boolean = false): Promise<boolean> {
        // 如果已经授权，直接启用定位
        if (this.locationPermissionGranted) {
            this.addLocationMarker();
            this.watchPosition();
            return true;
        }

        // 如果需要请求权限
        if (requestPermission) {
            // 请求权限
            const status = await LocationPermissionManager.requestPermission();
            
            if (status === LocationPermissionManager.PermissionStatus.GRANTED) {
                this.locationPermissionGranted = true;
                this.addLocationMarker();
                this.watchPosition();
                console.log('✅ 定位功能已启用');
                return true;
            } else {
                console.warn('⚠️ 定位权限未授权，无法显示定位蓝点');
                return false;
            }
        }

        return false;
    }

    /**
     * 添加定位蓝点
     */
    private addLocationMarker(): void {
        if (this.locationMarker) {
            return; // 已经存在
        }

        // 创建定位标记（使用高德地图默认样式）
        this.locationMarker = {
            position: this.map.getCenter(),
            id: 'location-marker-' + Date.now()
        };

        // 使用代理对象的 addMarker 方法（不使用 offset，依赖 CSS 自动居中）
        if (this.map.addMarker) {
            this.map.addMarker({
                position: this.locationMarker.position,
                content: '<div style="background-color: #4A90E2; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); transform: translate(-50%, -50%);"></div>',
                zIndex: 9999,
                title: '当前位置'
            });
        } else {
            console.warn('⚠️ map.addMarker 方法不可用，使用备用方案');
            // 备用方案：直接使用 map.add
            try {
                const marker = new (window as any).AMap.Marker({
                    position: this.locationMarker.position,
                    content: '<div style="background-color: #4A90E2; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); transform: translate(-50%, -50%);"></div>',
                    zIndex: 9999,
                    title: '当前位置'
                });
                this.map.add(marker);
                this.locationMarker.marker = marker;
            } catch (error) {
                console.error('❌ 创建定位蓝点失败:', error);
                this.locationMarker = null;
                return;
            }
        }

        console.log('✅ 定位蓝点已添加');
    }

    /**
     * 移除定位蓝点
     */
    private removeLocationMarker(): void {
        if (this.locationMarker) {
            // 如果有实际的 marker 对象，移除它
            if (this.locationMarker.marker && this.map.remove) {
                this.map.remove(this.locationMarker.marker);
            } else if (this.map.removeMarker) {
                // 使用代理对象的 removeMarker 方法
                this.map.removeMarker(this.locationMarker);
            }
            
            this.locationMarker = null;
            console.log('✅ 定位蓝点已移除');
        }
    }

    /**
     * 更新定位蓝点位置
     */
    private updateLocationMarker(lng: number, lat: number): void {
        if (this.locationMarker) {
            this.locationMarker.position = [lng, lat];
            
            // 如果有实际的 marker 对象，更新其位置
            if (this.locationMarker.marker) {
                this.locationMarker.marker.setPosition([lng, lat]);
            } else if (this.map.addMarker) {
                // 重新添加标记（因为无法直接更新）
                this.map.addMarker({
                    position: [lng, lat],
                    content: '<div style="background-color: #4A90E2; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
                    offset: new (window as any).AMap.Pixel(-8, -8),
                    zIndex: 9999,
                    title: '当前位置'
                });
            }
        }
    }

    /**
     * 持续监听位置变化
     */
    private watchPosition(): void {
        if (this.watchId !== null) {
            return; // 已经在监听
        }

        if (!navigator.geolocation) {
            console.warn('⚠️ 当前设备不支持定位功能');
            return;
        }

        this.watchId = navigator.geolocation.watchPosition(
            (position) => {
                const { longitude, latitude } = position.coords;
                this.updateLocationMarker(longitude, latitude);
                
                // 可选：自动移动地图到当前位置
                // this.map.setCenter([longitude, latitude]);
            },
            (error) => {
                console.error('❌ 定位失败:', error);
                if (error.code === error.PERMISSION_DENIED) {
                    this.locationPermissionGranted = false;
                    this.removeLocationMarker();
                    this.stopWatching();
                }
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 5000
            }
        );

        console.log('✅ 开始监听位置变化');
    }

    /**
     * 停止监听位置
     */
    private stopWatching(): void {
        if (this.watchId !== null) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
            console.log('✅ 停止监听位置');
        }
    }

    /**
     * 销毁地图实例
     */
    destroy(): void {
        super.destroy();
        this.clearPolygons();
        this.clearMarkers();
        
        // 清理定位资源
        this.stopWatching();
        this.removeLocationMarker();
        
        if (this.map) {
            this.map.destroy();
            this.map = null;
        }
    }
}