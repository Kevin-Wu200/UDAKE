/**
 * 坐标相关类型定义
 */

/** 坐标类型 */
export type CoordinateType = 'longitude' | 'latitude';

/** 坐标格式 */
export type CoordinateFormat = 'DD' | 'DDM' | 'DMS';

/** 坐标解析结果 */
export interface CoordinateParseResult {
    valid: boolean;
    value: number | null;
    format: CoordinateFormat | null;
    error: string | null;
}

/** 采样值解析结果 */
export interface SampleValueParseResult {
    valid: boolean;
    value: number | null;
    error: string | null;
}

/** 内部解析结果（无格式信息） */
export interface InternalParseResult {
    valid: boolean;
    value: number | null;
}

/** Web Mercator 坐标 */
export interface MercatorCoordinate {
    x: number;
    y: number;
}

/** WGS-84 坐标 */
export interface WGS84Coordinate {
    lon: number;
    lat: number;
}

/** 空间参考 */
export interface SpatialReference {
    wkid: number;
}

/** 带值的点坐标 */
export interface PointWithValue {
    x: number;
    y: number;
    value: number;
}
