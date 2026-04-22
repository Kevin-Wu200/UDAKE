/**
 * 字段匹配工具
 * 自动匹配 X、Y、Point_Data 字段
 */
import type { GeoJSONFeatureCollection } from '../../types/core';
import type { FieldMatchResult, FieldSelection, FieldValidationResult } from '../../types/geojson';
import { I18n } from './I18n.js';

export class FieldMatcher {
    /**
     * 匹配字段
     */
    static matchFields(fields: string[]): FieldMatchResult {
        return {
            x: this.matchX(fields),
            y: this.matchY(fields),
            pointData: this.matchPointData(fields)
        };
    }

    /**
     * 匹配 X 字段
     */
    static matchX(fields: string[]): string | null {
        const patterns = ['x', 'lon', 'longitude', 'lng', 'long'];
        return this.findMatch(fields, patterns);
    }

    /**
     * 匹配 Y 字段
     */
    static matchY(fields: string[]): string | null {
        const patterns = ['y', 'lat', 'latitude'];
        return this.findMatch(fields, patterns);
    }

    /**
     * 匹配 Point_Data 字段
     */
    static matchPointData(fields: string[]): string | null {
        const patterns = ['value', 'z', 'data', 'point_data', 'pointdata'];
        return this.findMatch(fields, patterns);
    }

    /**
     * 查找匹配的字段
     */
    static findMatch(fields: string[], patterns: string[]): string | null {
        for (const pattern of patterns) {
            const match = fields.find(field =>
                field.toLowerCase() === pattern.toLowerCase()
            );
            if (match) {
                return match;
            }
        }
        return null;
    }

    /**
     * 验证字段选择
     */
    static validateSelection(selection: FieldSelection): FieldValidationResult {
        const errors: Partial<Record<keyof FieldSelection, string>> = {};

        if (!selection.x) {
            errors.x = I18n.t('dataImport.validation.selectX');
        }
        if (!selection.y) {
            errors.y = I18n.t('dataImport.validation.selectY');
        }
        if (!selection.pointData) {
            errors.pointData = I18n.t('dataImport.validation.selectPointData');
        }

        return {
            valid: Object.keys(errors).length === 0,
            errors
        };
    }

    /**
     * 验证数值字段
     */
    static isNumericField(geojson: GeoJSONFeatureCollection, fieldName: string): boolean {
        const features = geojson.features;

        for (const feature of features) {
            const value = feature.properties[fieldName];
            if (value !== null && value !== undefined) {
                if (isNaN(parseFloat(value))) {
                    return false;
                }
            }
        }

        return true;
    }
}
