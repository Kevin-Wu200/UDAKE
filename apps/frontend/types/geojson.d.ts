/**
 * GeoJSON 相关类型定义（符合 RFC 7946）
 */

import type { GeoJSONFeatureCollection } from './core';

/** CRS 信息 */
export interface CRSInfo {
    detected: boolean;
    projectedName: string;
    projectedEPSG: number | null;
    geographicName: string;
    geographicEPSG: number;
}

/** GeoJSON 解析结果 */
export interface GeoJSONParseResult {
    geojson: GeoJSONFeatureCollection;
    crsInfo: CRSInfo;
    fields: string[];
    pointCount: number;
}

/** 字段匹配结果 */
export interface FieldMatchResult {
    x: string | null;
    y: string | null;
    pointData: string | null;
}

/** 字段选择 */
export interface FieldSelection {
    x: string | null;
    y: string | null;
    pointData: string | null;
}

/** 字段验证结果 */
export interface FieldValidationResult {
    valid: boolean;
    errors: Partial<Record<keyof FieldSelection, string>>;
}
