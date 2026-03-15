/**
 * 传感器管理器
 * 负责管理所有传感器功能，包括GPS定位、加速度传感器、陀螺仪和方向传感器
 */

import { Geolocation } from '@capacitor/geolocation';
import { Device } from '@capacitor/device';
import type {
  SensorConfig,
  LocationData,
  AccelerometerData,
  GyroscopeData,
  OrientationData,
  LocationWatchOptions,
  SensorStatus,
} from '../types/sensor';

/**
 * 传感器管理器类
 */
export class SensorManager {
  private static instance: SensorManager;

  // 传感器状态
  private status: SensorStatus = {
    gpsAvailable: false,
    locationPermission: 'prompt',
    accelerometerAvailable: false,
    gyroscopeAvailable: false,
    orientationAvailable: false,
    currentLocation: null,
    isRecording: false,
    activeTracks: 0,
    activeGeofences: 0,
  };

  // 监听器ID
  private locationWatchId: string | null = null;

  // 回调函数
  private locationCallback: ((data: LocationData) => void) | null = null;
  private accelerometerCallback: ((data: AccelerometerData) => void) | null = null;
  private gyroscopeCallback: ((data: GyroscopeData) => void) | null = null;
  private orientationCallback: ((data: OrientationData) => void) | null = null;

  // 配置
  private config: {
    location: LocationWatchOptions;
    updateInterval: number;
  } = {
    location: {
      enableHighAccuracy: true,
      timeout: 10000,
      distanceFilter: 10,
    },
    updateInterval: 1000,
  };

  // 传感器数据缓存
  private lastAccelerometerData: AccelerometerData | null = null;
  private lastGyroscopeData: GyroscopeData | null = null;
  private lastOrientationData: OrientationData | null = null;

  // Web API 引用
  private accelerometer: Accelerometer | null = null;
  private gyroscope: Gyroscope | null = null;
  private absoluteOrientationSensor: AbsoluteOrientationSensor | null = null;

  private constructor() {
    this.initializeSensors();
  }

  /**
   * 获取单例实例
   */
  public static getInstance(): SensorManager {
    if (!SensorManager.instance) {
      SensorManager.instance = new SensorManager();
    }
    return SensorManager.instance;
  }

  /**
   * 初始化传感器
   */
  public async initializeSensors(): Promise<void> {
    try {
      // 检查位置权限
      const permissionStatus = await Geolocation.checkPermissions();
      this.status.locationPermission = permissionStatus.location as any;

      // 检查设备信息
      const deviceInfo = await Device.getInfo();
      this.status.gpsAvailable = deviceInfo.platform !== 'web';

      // 初始化Web传感器API
      this.initializeWebSensors();
    } catch (error) {
      console.error('初始化传感器失败:', error);
    }
  }

  /**
   * 初始化Web传感器API
   */
  private initializeWebSensors(): void {
    // 检查加速度传感器
    if ('Accelerometer' in window) {
      this.status.accelerometerAvailable = true;
    }

    // 检查陀螺仪
    if ('Gyroscope' in window) {
      this.status.gyroscopeAvailable = true;
    }

    // 检查方向传感器
    if ('AbsoluteOrientationSensor' in window) {
      this.status.orientationAvailable = true;
    }
  }

  /**
   * 请求位置权限
   */
  public async requestLocationPermission(): Promise<boolean> {
    try {
      const permissionStatus = await Geolocation.requestPermissions({
        permissions: ['location'],
      });

      this.status.locationPermission = permissionStatus.location as any;
      return this.status.locationPermission === 'granted';
    } catch (error) {
      console.error('请求位置权限失败:', error);
      return false;
    }
  }

  /**
   * 获取当前位置
   */
  public async getCurrentLocation(): Promise<LocationData | null> {
    try {
      const position = await Geolocation.getCurrentPosition({
        enableHighAccuracy: this.config.location.enableHighAccuracy,
        timeout: this.config.location.timeout,
      });

      const locationData: LocationData = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy,
        altitude: position.coords.altitude,
        altitudeAccuracy: position.coords.altitudeAccuracy,
        heading: position.coords.heading,
        speed: position.coords.speed,
        timestamp: Date.now(),
      };

      this.status.currentLocation = locationData;
      return locationData;
    } catch (error) {
      console.error('获取当前位置失败:', error);
      return null;
    }
  }

  /**
   * 开始监听位置变化
   */
  public async startLocationWatch(callback: (data: LocationData) => void): Promise<boolean> {
    try {
      // 检查权限
      if (this.status.locationPermission !== 'granted') {
        const granted = await this.requestLocationPermission();
        if (!granted) {
          throw new Error('位置权限被拒绝');
        }
      }

      this.locationCallback = callback;

      const watchId = await Geolocation.watchPosition(
        {
          enableHighAccuracy: this.config.location.enableHighAccuracy,
          timeout: this.config.location.timeout,
          distanceFilter: this.config.location.distanceFilter,
        } as any,
        (position, error) => {
          if (error) {
            console.error('位置监听错误:', error);
            return;
          }

          if (position) {
            const locationData: LocationData = {
              latitude: position.coords.latitude,
              longitude: position.coords.longitude,
              accuracy: position.coords.accuracy,
              altitude: position.coords.altitude,
              altitudeAccuracy: position.coords.altitudeAccuracy,
              heading: position.coords.heading,
              speed: position.coords.speed,
              timestamp: Date.now(),
            };

            this.status.currentLocation = locationData;
            if (this.locationCallback) {
              this.locationCallback(locationData);
            }
          }
        }
      );

      this.locationWatchId = watchId;
      this.status.gpsAvailable = true;
      return true;
    } catch (error) {
      console.error('启动位置监听失败:', error);
      return false;
    }
  }

  /**
   * 停止监听位置变化
   */
  public async stopLocationWatch(): Promise<void> {
    if (this.locationWatchId) {
      await Geolocation.clearWatch({ id: this.locationWatchId });
      this.locationWatchId = null;
      this.locationCallback = null;
    }
  }

  /**
   * 开始监听加速度传感器
   */
  public async startAccelerometer(callback: (data: AccelerometerData) => void): Promise<boolean> {
    if (!this.status.accelerometerAvailable) {
      console.warn('加速度传感器不可用');
      return false;
    }

    try {
      this.accelerometer = new Accelerometer({
        frequency: 1000 / this.config.updateInterval,
      });

      this.accelerometerCallback = callback;

      this.accelerometer.addEventListener('reading', () => {
        const data: AccelerometerData = {
          x: this.accelerometer!.x,
          y: this.accelerometer!.y,
          z: this.accelerometer!.z,
          timestamp: Date.now(),
        };

        this.lastAccelerometerData = data;
        if (this.accelerometerCallback) {
          this.accelerometerCallback(data);
        }
      });

      this.accelerometer.start();
      return true;
    } catch (error) {
      console.error('启动加速度传感器失败:', error);
      return false;
    }
  }

  /**
   * 停止监听加速度传感器
   */
  public stopAccelerometer(): void {
    if (this.accelerometer) {
      this.accelerometer.stop();
      this.accelerometer = null;
      this.accelerometerCallback = null;
    }
  }

  /**
   * 开始监听陀螺仪
   */
  public async startGyroscope(callback: (data: GyroscopeData) => void): Promise<boolean> {
    if (!this.status.gyroscopeAvailable) {
      console.warn('陀螺仪不可用');
      return false;
    }

    try {
      this.gyroscope = new Gyroscope({
        frequency: 1000 / this.config.updateInterval,
      });

      this.gyroscopeCallback = callback;

      this.gyroscope.addEventListener('reading', () => {
        const data: GyroscopeData = {
          x: this.gyroscope!.x,
          y: this.gyroscope!.y,
          z: this.gyroscope!.z,
          timestamp: Date.now(),
        };

        this.lastGyroscopeData = data;
        if (this.gyroscopeCallback) {
          this.gyroscopeCallback(data);
        }
      });

      this.gyroscope.start();
      return true;
    } catch (error) {
      console.error('启动陀螺仪失败:', error);
      return false;
    }
  }

  /**
   * 停止监听陀螺仪
   */
  public stopGyroscope(): void {
    if (this.gyroscope) {
      this.gyroscope.stop();
      this.gyroscope = null;
      this.gyroscopeCallback = null;
    }
  }

  /**
   * 开始监听方向传感器
   */
  public async startOrientation(callback: (data: OrientationData) => void): Promise<boolean> {
    if (!this.status.orientationAvailable) {
      console.warn('方向传感器不可用');
      return false;
    }

    try {
      this.absoluteOrientationSensor = new AbsoluteOrientationSensor({
        frequency: 1000 / this.config.updateInterval,
      });

      this.orientationCallback = callback;

      this.absoluteOrientationSensor.addEventListener('reading', () => {
        const quaternion = this.absoluteOrientationSensor!.quaternion;
        // 将四元数转换为欧拉角
        const euler = this.quaternionToEuler(quaternion);

        const data: OrientationData = {
          absolute: euler.yaw,
          alpha: euler.yaw,
          beta: euler.pitch,
          gamma: euler.roll,
          timestamp: Date.now(),
        };

        this.lastOrientationData = data;
        if (this.orientationCallback) {
          this.orientationCallback(data);
        }
      });

      this.absoluteOrientationSensor.start();
      return true;
    } catch (error) {
      console.error('启动方向传感器失败:', error);
      return false;
    }
  }

  /**
   * 停止监听方向传感器
   */
  public stopOrientation(): void {
    if (this.absoluteOrientationSensor) {
      this.absoluteOrientationSensor.stop();
      this.absoluteOrientationSensor = null;
      this.orientationCallback = null;
    }
  }

  /**
   * 四元数转欧拉角
   */
  private quaternionToEuler(quaternion: number[]): { yaw: number; pitch: number; roll: number } {
    const [w, x, y, z] = quaternion;

    // 计算偏航角 (yaw)
    const siny_cosp = 2 * (w * z + x * y);
    const cosy_cosp = 1 - 2 * (y * y + z * z);
    const yaw = Math.atan2(siny_cosp, cosy_cosp);

    // 计算俯仰角 (pitch)
    const sinp = 2 * (w * y - z * x);
    const pitch = Math.abs(sinp) >= 1 ? (Math.sign(sinp) * Math.PI) / 2 : Math.asin(sinp);

    // 计算滚转角 (roll)
    const sinr_cosp = 2 * (w * x + y * z);
    const cosr_cosp = 1 - 2 * (x * x + y * y);
    const roll = Math.atan2(sinr_cosp, cosr_cosp);

    // 转换为角度
    return {
      yaw: ((yaw * 180) / Math.PI + 360) % 360,
      pitch: (pitch * 180) / Math.PI,
      roll: (roll * 180) / Math.PI,
    };
  }

  /**
   * 配置传感器参数
   */
  public configure(options: Partial<typeof this.config>): void {
    this.config = { ...this.config, ...options };
  }

  /**
   * 获取传感器状态
   */
  public getStatus(): SensorStatus {
    return { ...this.status };
  }

  /**
   * 停止所有传感器
   */
  public stopAll(): void {
    this.stopLocationWatch();
    this.stopAccelerometer();
    this.stopGyroscope();
    this.stopOrientation();
  }

  /**
   * 清理资源
   */
  public dispose(): void {
    this.stopAll();
  }
}

// 导出单例实例
export const sensorManager = SensorManager.getInstance();