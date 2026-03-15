/**
 * 数据模型类型定义
 * 定义项目中使用的基本数据结构和类型
 */

/**
 * GeoJSON 几何类型
 */
export type GeoJSONGeometryType = 'Point' | 'LineString' | 'Polygon' | 'MultiPoint' | 'MultiLineString' | 'MultiPolygon';

/**
 * GeoJSON 几何对象
 */
export interface GeoJSONGeometry {
  type: GeoJSONGeometryType;
  coordinates: number[] | number[][] | number[][][] | number[][][][];
}

/**
 * GeoJSON 特征属性
 */
export interface GeoJSONProperties {
  [key: string]: string | number | boolean | null | undefined;
}

/**
 * GeoJSON 特征
 */
export interface GeoJSONFeature {
  type: 'Feature';
  geometry: GeoJSONGeometry;
  properties: GeoJSONProperties;
  id?: string | number;
}

/**
 * GeoJSON 特征集合
 */
export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
  crs?: CRSInfo;
  bbox?: [number, number, number, number];
}

/**
 * 坐标参考系统信息
 */
export interface CRSInfo {
  type: string;
  properties: {
    name: string;
    code?: string;
  };
}

/**
 * 边界框
 */
export interface BoundingBox {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

/**
 * 地图坐标点
 */
export interface MapPoint {
  x: number;
  y: number;
  spatialReference?: string;
}

/**
 * 地理坐标点（经纬度）
 */
export interface GeoPoint {
  longitude: number;
  latitude: number;
  altitude?: number;
}

/**
 * 采样点数据
 */
export interface SamplePoint {
  id: string;
  x: number;
  y: number;
  value: number;
  timestamp?: Date;
  metadata?: Record<string, unknown>;
  properties?: GeoJSONProperties;
}

/**
 * 采样点数据（扩展）
 */
export interface ExtendedSamplePoint extends SamplePoint {
  uncertainty?: number;
  variance?: number;
  confidence?: number;
  quality?: 'high' | 'medium' | 'low';
  source?: string;
}

/**
 * 数据集
 */
export interface Dataset {
  id: string;
  name: string;
  description?: string;
  points: SamplePoint[];
  bounds: BoundingBox;
  crs?: CRSInfo;
  createdAt: Date;
  updatedAt: Date;
  metadata?: Record<string, unknown>;
}

/**
 * 数据集统计信息
 */
export interface DatasetStatistics {
  count: number;
  min: number;
  max: number;
  mean: number;
  std: number;
  variance: number;
  range: number;
}

/**
 * 数据字段信息
 */
export interface FieldInfo {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'date';
  nullable: boolean;
  unique: boolean;
  enum?: string[];
}

/**
 * 数据验证结果
 */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

/**
 * 验证错误
 */
export interface ValidationError {
  field: string;
  message: string;
  value?: unknown;
}

/**
 * 验证警告
 */
export interface ValidationWarning {
  field: string;
  message: string;
  value?: unknown;
  severity: 'low' | 'medium' | 'high';
}

/**
 * 数据转换配置
 */
export interface TransformConfig {
  sourceCRS: string;
  targetCRS: string;
  method: 'forward' | 'inverse';
}

/**
 * 数据导入选项
 */
export interface ImportOptions {
  format: 'geojson' | 'csv' | 'shapefile' | 'json';
  encoding?: string;
  skipInvalid?: boolean;
  validate?: boolean;
  transform?: TransformConfig;
}

/**
 * 数据导出选项
 */
export interface ExportOptions {
  format: 'geojson' | 'csv' | 'json';
  includeMetadata?: boolean;
  precision?: number;
  compress?: boolean;
}

/**
 * 数据过滤器
 */
export interface DataFilter {
  field: string;
  operator: 'eq' | 'ne' | 'gt' | 'lt' | 'gte' | 'lte' | 'in' | 'nin' | 'between';
  value: unknown;
  value2?: unknown; // 用于 'between' 操作符
}

/**
 * 数据排序规则
 */
export interface SortRule {
  field: string;
  order: 'asc' | 'desc';
}

/**
 * 数据分页信息
 */
export interface Pagination {
  page: number;
  pageSize: number;
  total: number;
}

/**
 * 数据查询结果
 */
export interface QueryResult<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}