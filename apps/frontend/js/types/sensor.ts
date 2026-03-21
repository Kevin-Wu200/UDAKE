/**
 * 传感器相关类型定义
 */

/**
 * GPS位置数据接口
 */
export interface LocationData {
  /** 纬度 */
  latitude: number;
  /** 经度 */
  longitude: number;
  /** 精度（米） */
  accuracy: number;
  /** 海拔（米） */
  altitude: number | null;
  /** 海拔精度（米） */
  altitudeAccuracy: number | null;
  /** 方向（度，0-360） */
  heading: number | null;
  /** 速度（米/秒） */
  speed: number | null;
  /** 时间戳 */
  timestamp: number;
}

/**
 * 加速度传感器数据接口
 */
export interface AccelerometerData {
  /** X轴加速度 (m/s²) */
  x: number;
  /** Y轴加速度 (m/s²) */
  y: number;
  /** Z轴加速度 (m/s²) */
  z: number;
  /** 时间戳 */
  timestamp: number;
}

/**
 * 陀螺仪传感器数据接口
 */
export interface GyroscopeData {
  /** X轴旋转速度 (rad/s) */
  x: number;
  /** Y轴旋转速度 (rad/s) */
  y: number;
  /** Z轴旋转速度 (rad/s) */
  z: number;
  /** 时间戳 */
  timestamp: number;
}

/**
 * 方向传感器数据接口
 */
export interface OrientationData {
  /** 绝对方向 (度，0-360) */
  absolute: number;
  /** alpha (度，Z轴旋转) */
  alpha: number;
  /** beta (度，X轴旋转) */
  beta: number;
  /** gamma (度，Y轴旋转) */
  gamma: number;
  /** 时间戳 */
  timestamp: number;
}

/**
 * 传感器配置选项
 */
export interface SensorConfig {
  /** 更新频率 (毫秒) */
  updateInterval?: number;
  /** 是否启用 */
  enabled?: boolean;
  /** 数据回调 */
  callback?: (data: any) => void;
  /** 错误回调 */
  errorCallback?: (error: Error) => void;
}

/**
 * 位置监听选项
 */
export interface LocationWatchOptions {
  /** 最小更新距离（米） */
  distanceFilter?: number;
  /** 期望精度 */
  desiredAccuracy?: 'high' | 'medium' | 'low';
  /** 超时时间（毫秒） */
  timeout?: number;
  /** 是否启用高精度 */
  enableHighAccuracy?: boolean;
}

/**
 * 轨迹点接口
 */
export interface TrackPoint {
  /** 位置数据 */
  location: LocationData;
  /** 加速度数据 */
  accelerometer?: AccelerometerData;
  /** 方向数据 */
  orientation?: OrientationData;
  /** 点索引 */
  index: number;
  /** 时间戳 */
  timestamp: number;
}

/**
 * 轨迹接口
 */
export interface Track {
  /** 轨迹ID */
  id: string;
  /** 轨迹名称 */
  name: string;
  /** 轨迹点列表 */
  points: TrackPoint[];
  /** 开始时间 */
  startTime: number;
  /** 结束时间 */
  endTime: number | null;
  /** 总距离（米） */
  totalDistance: number;
  /** 平均速度（米/秒） */
  averageSpeed: number;
  /** 轨迹描述 */
  description?: string;
}

/**
 * 地理围栏接口
 */
export interface Geofence {
  /** 围栏ID */
  id: string;
  /** 围栏名称 */
  name: string;
  /** 中心点纬度 */
  latitude: number;
  /** 中心点经度 */
  longitude: number;
  /** 半径（米） */
  radius: number;
  /** 围栏类型 */
  type: 'circular' | 'polygon';
  /** 多边形顶点（仅当type为polygon时使用） */
  vertices?: Array<{ latitude: number; longitude: number }>;
  /** 是否启用 */
  enabled: boolean;
  /** 触发事件类型 */
  notifyOnEnter: boolean;
  notifyOnExit: boolean;
  notifyOnDwell: boolean;
  /** 停留时间（毫秒） */
  dwellDelay?: number;
  /** 围栏描述 */
  description?: string;
}

/**
 * 地理围栏事件接口
 */
export interface GeofenceEvent {
  /** 事件ID */
  id: string;
  /** 围栏ID */
  geofenceId: string;
  /** 事件类型 */
  type: 'enter' | 'exit' | 'dwell';
  /** 触发时间 */
  timestamp: number;
  /** 触发位置 */
  location: LocationData;
}

/**
 * 传感器状态接口
 */
export interface SensorStatus {
  /** GPS是否可用 */
  gpsAvailable: boolean;
  /** 位置权限状态 */
  locationPermission: 'granted' | 'denied' | 'prompt' | 'prompt-with-rationale';
  /** 加速度传感器是否可用 */
  accelerometerAvailable: boolean;
  /** 陀螺仪传感器是否可用 */
  gyroscopeAvailable: boolean;
  /** 方向传感器是否可用 */
  orientationAvailable: boolean;
  /** 当前位置 */
  currentLocation: LocationData | null;
  /** 是否正在记录轨迹 */
  isRecording: boolean;
  /** 活动轨迹数 */
  activeTracks: number;
  /** 活动围栏数 */
  activeGeofences: number;
}