/**
 * 位置服务测试文件
 * 测试 GPS 定位、传感器数据采集、轨迹记录等功能
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// 模拟 Capacitor 插件
vi.mock('@capacitor/geolocation', () => ({
  Geolocation: {
    checkPermissions: vi.fn(),
    requestPermissions: vi.fn(),
    getCurrentPosition: vi.fn(),
    watchPosition: vi.fn(),
    clearWatch: vi.fn(),
  },
}));

vi.mock('@capacitor/device', () => ({
  Device: {
    getInfo: vi.fn(),
  },
}));

// 模拟 Web 传感器 API
global.Accelerometer = vi.fn();
global.Gyroscope = vi.fn();
global.AbsoluteOrientationSensor = vi.fn();

describe('位置服务测试', () => {
  let locationService;
  let trackManager;
  let geofenceManager;
  let sensorManager;

  beforeEach(async () => {
    // 动态导入服务
    const { locationService: ls } = await import('../frontend/js/services/LocationService');
    const { trackManager: tm } = await import('../frontend/js/services/TrackManager');
    const { geofenceManager: gm } = await import('../frontend/js/services/GeofenceManager');
    const { sensorManager: sm } = await import('../frontend/js/services/SensorManager');

    locationService = ls;
    trackManager = tm;
    geofenceManager = gm;
    sensorManager = sm;

    // 清理单例残留状态，避免测试间互相污染
    const geofences = geofenceManager.getAllGeofences();
    await Promise.all(geofences.map((geofence) => geofenceManager.deleteGeofence(geofence.id)));
  });

  afterEach(() => {
    // 清理
    vi.clearAllMocks();
  });

  describe('GPS 定位测试', () => {
    it('应该能够请求位置权限', async () => {
      const { Geolocation } = await import('@capacitor/geolocation');
      Geolocation.requestPermissions.mockResolvedValue({
        location: 'granted',
      });

      const granted = await locationService.requestPermission();
      expect(granted).toBe(true);
    });

    it('应该能够获取当前位置', async () => {
      const { Geolocation } = await import('@capacitor/geolocation');
      const mockPosition = {
        coords: {
          latitude: 39.9042,
          longitude: 116.4074,
          accuracy: 10,
          altitude: 50,
          altitudeAccuracy: 5,
          heading: 90,
          speed: 1.5,
        },
        timestamp: Date.now(),
      };

      Geolocation.getCurrentPosition.mockResolvedValue(mockPosition);

      const location = await locationService.getCurrentLocation();
      expect(location.latitude).toBe(39.9042);
      expect(location.longitude).toBe(116.4074);
      expect(location.accuracy).toBe(10);
    });

    it('应该能够计算两点之间的距离', () => {
      const point1 = { latitude: 39.9042, longitude: 116.4074 };
      const point2 = { latitude: 39.9142, longitude: 116.4174 };

      const distance = locationService.calculateDistance(point1, point2);
      expect(distance).toBeGreaterThan(0);
      expect(distance).toBeLessThan(2000); // 应该小于2公里
    });

    it('应该能够计算方位角', () => {
      const point1 = { latitude: 39.9042, longitude: 116.4074 };
      const point2 = { latitude: 39.9142, longitude: 116.4174 };

      const bearing = locationService.calculateBearing(point1, point2);
      expect(bearing).toBeGreaterThanOrEqual(0);
      expect(bearing).toBeLessThan(360);
    });
  });

  describe('传感器数据测试', () => {
    it('应该能够启动加速度传感器', async () => {
      const mockAccelerometer = {
        x: 0.1,
        y: 0.2,
        z: 9.8,
        addEventListener: vi.fn(),
        start: vi.fn(),
      };

      global.Accelerometer.mockImplementation(() => mockAccelerometer);

      let receivedData = null;
      const success = await sensorManager.startAccelerometer((data) => {
        receivedData = data;
      });

      expect(success).toBe(true);
      expect(mockAccelerometer.start).toHaveBeenCalled();
    });

    it('应该能够启动陀螺仪', async () => {
      const mockGyroscope = {
        x: 0.01,
        y: 0.02,
        z: 0.03,
        addEventListener: vi.fn(),
        start: vi.fn(),
      };

      global.Gyroscope.mockImplementation(() => mockGyroscope);

      let receivedData = null;
      const success = await sensorManager.startGyroscope((data) => {
        receivedData = data;
      });

      expect(success).toBe(true);
      expect(mockGyroscope.start).toHaveBeenCalled();
    });

    it('应该能够启动方向传感器', async () => {
      const mockOrientationSensor = {
        quaternion: [0.707, 0, 0, 0.707],
        addEventListener: vi.fn(),
        start: vi.fn(),
      };

      global.AbsoluteOrientationSensor.mockImplementation(() => mockOrientationSensor);

      let receivedData = null;
      const success = await sensorManager.startOrientation((data) => {
        receivedData = data;
      });

      expect(success).toBe(true);
      expect(mockOrientationSensor.start).toHaveBeenCalled();
    });
  });

  describe('轨迹记录测试', () => {
    it('应该能够创建新轨迹', async () => {
      const track = await trackManager.createTrack('测试轨迹', '这是一个测试轨迹');

      expect(track).toBeDefined();
      expect(track.name).toBe('测试轨迹');
      expect(track.description).toBe('这是一个测试轨迹');
      expect(track.points).toHaveLength(0);
      expect(track.startTime).toBeDefined();
    });

    it('应该能够开始记录轨迹', async () => {
      const { Geolocation } = await import('@capacitor/geolocation');

      // 模拟位置监听
      Geolocation.watchPosition.mockImplementation((callback) => {
        setTimeout(() => {
          callback({
            coords: {
              latitude: 39.9042,
              longitude: 116.4074,
              accuracy: 10,
              altitude: 50,
              altitudeAccuracy: 5,
              heading: 90,
              speed: 1.5,
            },
            timestamp: Date.now(),
          });
        }, 100);

        return 'watch-id-1';
      });

      const track = await trackManager.startRecording('测试轨迹');

      expect(track).toBeDefined();
      expect(trackManager.isRecording()).toBe(true);

      await trackManager.stopRecording();
      expect(trackManager.isRecording()).toBe(false);
    });

    it('应该能够导出轨迹为 GeoJSON', async () => {
      const track = await trackManager.createTrack('测试轨迹');
      track.points.push({
        location: {
          latitude: 39.9042,
          longitude: 116.4074,
          accuracy: 10,
          altitude: 50,
          altitudeAccuracy: 5,
          heading: 90,
          speed: 1.5,
          timestamp: Date.now(),
        },
        index: 0,
        timestamp: Date.now(),
      });

      const geojson = trackManager.exportToGeoJSON(track.id);
      expect(geojson).toBeDefined();

      const parsed = JSON.parse(geojson);
      expect(parsed.type).toBe('Feature');
      expect(parsed.geometry.type).toBe('LineString');
      expect(parsed.geometry.coordinates).toHaveLength(1);
    });

    it('应该能够导出轨迹为 GPX', async () => {
      const track = await trackManager.createTrack('测试轨迹');
      track.points.push({
        location: {
          latitude: 39.9042,
          longitude: 116.4074,
          accuracy: 10,
          altitude: 50,
          altitudeAccuracy: 5,
          heading: 90,
          speed: 1.5,
          timestamp: Date.now(),
        },
        index: 0,
        timestamp: Date.now(),
      });

      const gpx = trackManager.exportToGPX(track.id);
      expect(gpx).toBeDefined();
      expect(gpx).toContain('<?xml version="1.0"');
      expect(gpx).toContain('<gpx');
      expect(gpx).toContain('<trkpt');
    });
  });

  describe('地理围栏测试', () => {
    it('应该能够创建圆形地理围栏', async () => {
      const geofence = await geofenceManager.createCircularGeofence(
        '测试围栏',
        39.9042,
        116.4074,
        100
      );

      expect(geofence).toBeDefined();
      expect(geofence.name).toBe('测试围栏');
      expect(geofence.type).toBe('circular');
      expect(geofence.latitude).toBe(39.9042);
      expect(geofence.longitude).toBe(116.4074);
      expect(geofence.radius).toBe(100);
    });

    it('应该能够创建多边形地理围栏', async () => {
      const vertices = [
        { latitude: 39.9042, longitude: 116.4074 },
        { latitude: 39.9142, longitude: 116.4074 },
        { latitude: 39.9142, longitude: 116.4174 },
        { latitude: 39.9042, longitude: 116.4174 },
      ];

      const geofence = await geofenceManager.createPolygonGeofence(
        '多边形围栏',
        vertices
      );

      expect(geofence).toBeDefined();
      expect(geofence.type).toBe('polygon');
      expect(geofence.vertices).toBeDefined();
      expect(geofence.vertices).toHaveLength(4);
    });

    it('应该能够判断位置是否在圆形围栏内', () => {
      const geofence = {
        type: 'circular',
        latitude: 39.9042,
        longitude: 116.4074,
        radius: 100,
      };

      const insideLocation = {
        latitude: 39.9042,
        longitude: 116.4074,
        accuracy: 10,
        altitude: 50,
        altitudeAccuracy: 5,
        heading: 90,
        speed: 1.5,
        timestamp: Date.now(),
      };

      const outsideLocation = {
        latitude: 39.9142,
        longitude: 116.4174,
        accuracy: 10,
        altitude: 50,
        altitudeAccuracy: 5,
        heading: 90,
        speed: 1.5,
        timestamp: Date.now(),
      };

      const isInside = geofenceManager['isInsideCircle'](insideLocation, geofence);
      const isOutside = geofenceManager['isInsideCircle'](outsideLocation, geofence);

      expect(isInside).toBe(true);
      expect(isOutside).toBe(false);
    });

    it('应该能够触发地理围栏事件', async () => {
      await new Promise((resolve, reject) => {
        const timeoutId = setTimeout(() => reject(new Error('地理围栏事件超时')), 1000);

      geofenceManager.addGeofenceListener((event) => {
          try {
            expect(event.type).toBe('enter');
            expect(event.geofenceId).toBeDefined();
            clearTimeout(timeoutId);
            resolve();
          } catch (error) {
            clearTimeout(timeoutId);
            reject(error);
          }
      });

      // 模拟触发事件
      geofenceManager['triggerEvent']('test-geofence-id', 'enter', {
        latitude: 39.9042,
        longitude: 116.4074,
        accuracy: 10,
        altitude: 50,
        altitudeAccuracy: 5,
        heading: 90,
        speed: 1.5,
        timestamp: Date.now(),
      });
      });
    });
  });

  describe('性能测试', () => {
    it('应该能够处理大量轨迹点', async () => {
      const track = await trackManager.createTrack('性能测试轨迹');

      // 添加1000个轨迹点
      for (let i = 0; i < 1000; i++) {
        track.points.push({
          location: {
            latitude: 39.9042 + (i * 0.0001),
            longitude: 116.4074 + (i * 0.0001),
            accuracy: 10,
            altitude: 50,
            altitudeAccuracy: 5,
            heading: 90,
            speed: 1.5,
            timestamp: Date.now() + i * 1000,
          },
          index: i,
          timestamp: Date.now() + i * 1000,
        });
      }

      // 计算统计数据
      trackManager['calculateTrackStatistics'](track);

      expect(track.points).toHaveLength(1000);
      expect(track.totalDistance).toBeGreaterThan(0);
      expect(track.averageSpeed).toBeGreaterThan(0);
    });

    it('应该能够处理多个地理围栏', async () => {
      // 创建10个地理围栏
      for (let i = 0; i < 10; i++) {
        await geofenceManager.createCircularGeofence(
          `围栏${i}`,
          39.9042 + (i * 0.001),
          116.4074 + (i * 0.001),
          100
        );
      }

      const geofences = geofenceManager.getAllGeofences();
      expect(geofences).toHaveLength(10);
    });
  });

  describe('错误处理测试', () => {
    it('应该能够处理位置权限被拒绝的情况', async () => {
      const { Geolocation } = await import('@capacitor/geolocation');
      Geolocation.requestPermissions.mockResolvedValue({
        location: 'denied',
      });

      const granted = await locationService.requestPermission();
      expect(granted).toBe(false);
    });

    it('应该能够处理获取位置失败的情况', async () => {
      const { Geolocation } = await import('@capacitor/geolocation');
      Geolocation.getCurrentPosition.mockRejectedValue(new Error('无法获取位置'));

      await expect(locationService.getCurrentLocation()).rejects.toThrow();
    });

    it('应该能够处理传感器不可用的情况', async () => {
      global.Accelerometer.mockImplementation(() => {
        throw new Error('加速度传感器不可用');
      });

      const success = await sensorManager.startAccelerometer(() => {});
      expect(success).toBe(false);
    });
  });
});

console.log('位置服务测试文件已加载');
